"""The shared review-action builder.

``_build_review_action_fn`` returns the ``action(rec)`` callback that the
reconcile walks (in :mod:`plan_tool.cli.reconcile`) and ``cmd_review`` (still
resident in the package's ``app`` module) both drive. It is the lower of the
two review/reconcile leaves: it carries no module-top ``import reconcile`` --
its ``_dispatch_detail_reconcile`` closure resolves the reconcile reuse
helpers through a function-body
``from plan_tool.cli import reconcile`` at action-walk time, keeping this
module import-light and the ``reconcile -> review_actions`` edge
one-directional.

Like :mod:`plan_tool.cli.reconcile` it registers no subparsers and is
absent from ``app.COMMAND_MODULES``.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from typing import Callable, Sequence

    from plan_tool.review import CarriedFinding
    from plan_tool.scope_guard import ReconcileScopeGuard

from plan_tool.fingerprint import compute_code_fingerprint
from plan_tool.launcher import LauncherError
from plan_tool.locator import PlanToolContext
from plan_tool.parser import ParseError, ValidationError, parse_plan, write_plan
from plan_tool.review import confidence_label
from plan_tool.review_persistence import (
    compute_plan_fingerprint,
    load_review,
    save_review,
)
from plan_tool.review_walk import (
    StructuralOutcomeEffects,
    WalkState,
    apply_structural_outcome,
    stamp_target_signatures,
    structural_apply_allowed,
)
from plan_tool.run_log import RunLogWriter
from plan_tool.style import colorize_diff, warn


_COMMAND_LOCAL_APPLY_SOURCES = frozenset({"data-contract"})


def _build_review_action_fn(
    *,
    ctx: PlanToolContext,
    plan_path: Path,
    plan_name: str,
    yes: bool = False,
    allow_split: bool = False,
    allow_structural_remedy: bool = False,
    allow_merge_remedy: bool = False,
    allow_reground_remedy: bool = False,
    reground_rebaseline: bool = False,
    saved_plan_fingerprint: str = "",
    allow_structural_verdict: bool = False,
    state: Optional[WalkState] = None,
    run_logger: Optional[RunLogWriter] = None,
    reconcile_scope_guard: Optional["ReconcileScopeGuard"] = None,
    carried_findings: "Sequence[CarriedFinding] | Callable[[], Sequence[CarriedFinding]]" = (),
    extra_apply_sources: frozenset[str] = frozenset(),
):
    """Return an action_fn for reconcile-plan-walk that dispatches recognized
    suggested actions on the user's behalf.

    The walk passes the current Recommendation; this handler inspects
    its ``suggested_action`` and dispatches:

    - ``plan-tool detail <name> --step N [--force]`` → invoke
      ``generate_detail`` to (re)write the per-step detail markdown and
      update the plan's ``step.detail`` pointer.
    - ``plan-tool detail <name> --reconcile --step N`` → run the
      detail-side audit against that step (mode=``detail-reconcile``),
      persist findings as ``kind="detail-reconcile"``, walk them via
      ``apply_finding``.

    Returns a short one-line message describing what happened, or a
    no-op notice when the suggested action isn't a shape this handler
    knows how to dispatch.

    When ``reconcile_scope_guard`` is a ``ReconcileScopeGuard`` instance
   , ``_dispatch_apply_finding`` wraps every successful
    ``apply_finding`` call with a pre/post snapshot pair and runs
    ``evaluate_apply_scope`` → ``revert_out_of_scope`` →
    ``scope_buffer.add`` per finding. The guard also records each
    ``apply_finding.pre_snapshot`` so a post-walk drift halt's
    collision-sidecar wiring has the merged iteration-start baseline.
    ``None`` (the default) leaves the dispatcher unchanged, matching
    every call site outside ``_iterate_reconcile_loop``.

    ``allow_structural_remedy`` (default ``False``) is the walk-level *umbrella*
    opt-in that lets a ``granularity-merge`` directive finding actuate its
    structural bridge — a re-ground directive → ``reground_bridge`` (mark-done),
    a merge directive → ``merge_bridge`` (fold steps) — instead of only
    recommending. ``allow_merge_remedy`` / ``allow_reground_remedy`` (both
    default ``False``) are the *per-remedy* opt-ins: each enables only its own
    bridge, so an operator can trust the tool to fold merges while eyeballing
    every re-ground (or the reverse). Each dispatcher's effective opt-in is the
    umbrella OR its own flag, so the umbrella still means "both on" and every
    caller that omits the granular flags behaves exactly as before. Dedicated —
    never overloads ``allow_split`` (which defaults ON in the detail-reconcile
    walk and gates the *inverse* structural operation). All three are forced off
    under ``state.yes_to_all`` so a blanket fast-forward never auto-confirms.

    ``reground_rebaseline`` (default ``False``) is a **disposition selector**,
    not an enable toggle: it changes *how* an actuated re-ground behaves —
    ``reground_bridge`` also writes a ``create --from-existing`` re-baseline seed
    for the flagged already-built steps rather than only marking them done — and
    never changes *whether* the re-ground actuates (that stays gated on the
    enable opt-in above and, being an ``info`` finding, ``--include-info``). It
    is deliberately **not** forwarded into the ``_dispatch_detail_reconcile``
    sub-walk: unlike the enable opt-ins (which thread uniformly for parity), a
    disposition only selects a behavior for a remedy the recursion can never
    surface, so it stays scoped to this top-level walk.

    ``carried_findings`` is advisory apply-prompt context — the findings
    accumulated this run — forwarded verbatim to every ``apply_finding``
    call ``_dispatch_apply_finding`` makes (and inherited by the nested
    detail-reconcile subwalks). It is either a static ``Sequence`` or a
    zero-arg provider resolved immediately before each apply, so a replay
    caller that accumulates verdicts mid-walk sees the latest set on each
    dispatch. Defaults to ``()`` so every caller outside completeness is
    unchanged.

    ``extra_apply_sources`` is accepted so callers and the walker can share a
    routing vocabulary for additional saved-audit sources. Sources with their
    own command-local actuator, such as ``data-contract``, are intentionally
    not dispatched here; those commands must provide their own action callback.
    """
    from plan_tool.detail import DetailError as _DetailError, generate_detail
    from plan_tool.launcher import (
        DeferredApplyVerdict,
        apply_finding,
        escalate_to_split,
        revert_apply_if_parse_broken,
        run_step as _run_step,
    )
    from plan_tool.launcher import _restore_text_files as _revert_snapshot
    from plan_tool.review import (
        MERGE_ACTION_MERGE,
        audit_targeted_fix,
        extract_reconcile_recommendations,
        format_recommendation_for_apply,
    )
    from plan_tool.review_walk import (
        compute_target_signature,
        directive_target_ids,
        file_check_create_target,
        merge_remedy_target,
        recognized_action,
        should_apply_as_finding,
        split_escalation_target,
    )

    # Single source of truth for "fast-forward" mode. When ``state`` was
    # passed in by the caller, reuse it so the walk and the action
    # handler share one flag (toggling it from either side propagates).
    # Otherwise seed a fresh one from the explicit ``yes`` flag so
    # ``--yes`` callers get fast-forward from the very first prompt.
    if state is None:
        state = WalkState(yes_to_all=yes)

    # Per-remedy opt-in resolution: the umbrella ``allow_structural_remedy``
    # enables both bridges; each granular flag enables only its own. Computing
    # ``umbrella OR own flag`` once keeps the umbrella meaning "both on" while
    # letting a single remedy be turned on in isolation.
    _merge_opt_in = allow_structural_remedy or allow_merge_remedy
    _reground_opt_in = allow_structural_remedy or allow_reground_remedy

    # Hoist the plan fingerprint once for the whole walk so every per-finding
    # ``apply_finding`` apply-verdict telemetry line carries the same join key
    # without re-hashing per rec. Best-effort: a compute failure degrades to "".
    try:
        _apply_verdict_plan_fp = compute_plan_fingerprint(plan_path)
    except Exception:
        _apply_verdict_plan_fp = ""

    def _coarse_plan_is_stale() -> bool:
        """The legacy whole-plan fingerprint check: stale when a non-empty
        saved fingerprint no longer matches the plan on disk. Used as the
        fallback floor only for findings with no per-directive signal
        (unstamped or non-directive). NOT the parse-failure path: a stamped
        directive whose plan won't parse returns stale directly (see
        ``_saved_directive_is_stale``), because this floor reads an empty
        fingerprint as not-stale and would let the bridge crash on a gone plan."""
        return bool(saved_plan_fingerprint) and (
            saved_plan_fingerprint != compute_plan_fingerprint(plan_path)
        )

    def _saved_directive_is_stale(rec) -> bool:
        """True when this directive finding's **own target steps** changed on
        disk since the finding was computed — so its saved step ids may now
        name different steps and the mutating bridge must be downgraded to
        recommend-only.

        The single freshness contract both structural-remedy dispatchers gate
        on before any mutating bridge call, so merge and re-ground can never
        drift to different staleness rules. Unlike the whole-plan fingerprint,
        this compares only the directive's targets — recovered through
        :func:`directive_target_ids` and re-hashed with
        :func:`compute_target_signature` against the ``target_signature`` the
        finding was stamped with — so an unrelated edit elsewhere in a
        mixed-finding walk no longer downgrades a still-valid directive.

        Where there's no per-directive signal (non-directive rec, or an
        unstamped legacy finding), fall back to the coarse whole-plan check. For
        a stamped directive, re-hash its targets — but if the plan is
        missing/unreadable/corrupt, return **stale** (recommend-only), NOT the
        coarse fallback: an empty ``saved_plan_fingerprint`` (the
        reconcile/completeness-apply lanes pass none) would read as not-stale
        there, so the dispatcher would proceed and the bridge's own re-parse of
        the gone plan would crash the walk. Returning stale keeps the bridge
        from ever being reached with a gone plan.
        """
        target_ids = directive_target_ids(rec)
        if target_ids is None or rec.target_signature is None:
            return _coarse_plan_is_stale()
        try:
            plan = parse_plan(plan_path)
        except (
            FileNotFoundError, OSError, UnicodeDecodeError,
            ParseError, ValidationError,
        ):
            return True
        recomputed = compute_target_signature(plan, target_ids)
        return recomputed != rec.target_signature

    def _dispatch_detail_reconcile(step_id: int) -> str:
        # The reconcile reuse helpers live in the upper leaf
        # ``plan_tool.cli.reconcile``; resolve them lazily here at
        # action-walk time to keep the ``reconcile -> review_actions``
        # edge one-directional.
        from plan_tool.cli import reconcile

        # Detail-side reconcile (audit plan/detail vs code on disk). Keys
        # off the ``detail-reconcile`` save kind so a run-side reconcile
        # save can't be offered for replay against this audit.
        if state.yes_to_all or sys.stdin.isatty():
            existing = reconcile._find_saved_detail_reconcile_for_step(
                plan_name, ctx.repo_root, step_id=step_id, plan_path=plan_path
            )
            if existing is not None:
                saved_path, saved = existing
                reuse = (
                    state.yes_to_all
                    or reconcile._ask_reuse_saved_detail_reconcile(
                        saved_path, saved, plan_name,
                        repo_root=ctx.repo_root,
                    )
                )
                if reuse:
                    if not saved.recommendations:
                        return (
                            f"reused saved detail-reconcile for step "
                            f"{step_id} ({saved_path}); "
                            f"0 recommendations to walk"
                        )
                    print(
                        f"\n→ entering detail-reconcile walk for step "
                        f"{step_id} ({len(saved.recommendations)} rec(s))"
                    )
                    sub_action_fn = _build_review_action_fn(
                        ctx=ctx,
                        plan_path=plan_path,
                        plan_name=plan_name,
                        allow_split=allow_split,
                        allow_structural_remedy=allow_structural_remedy,
                        allow_merge_remedy=allow_merge_remedy,
                        allow_reground_remedy=allow_reground_remedy,
                        allow_structural_verdict=allow_structural_verdict,
                        state=state,
                        run_logger=run_logger,
                        carried_findings=carried_findings,
                                )
                    reconcile._walk_with_reconcile_phase(
                        saved, sub_action_fn, state,
                        run_logger=run_logger,
                        step_id=step_id,
                    )
                    return (
                        f"← returning to review walk for plan "
                        f"{plan_name!r} (used saved detail-reconcile)"
                    )

        print(f"\n→ running detail-reconcile on step {step_id}…\n")
        try:
            sub_result = _run_step(
                plan_path,
                repo_root=ctx.repo_root,
                step_id=step_id,
                mode="detail-reconcile",
                dry_run=False,
                run_logger=run_logger,
            )
        except LauncherError as exc:
            return f"detail-reconcile launcher error: {exc}"
        if sub_result.exit_code != 0:
            return f"detail-reconcile exited with code {sub_result.exit_code}"

        sub_recs = extract_reconcile_recommendations(
            sub_result.stdout, step_id=step_id, source="detail-reconcile"
        )
        # Persist a canonical repo-relative POSIX value, not a lexical warning path.
        try:
            plan_rel = plan_path.resolve().relative_to(
                ctx.repo_root.resolve()
            ).as_posix()
        except ValueError:
            plan_rel = str(plan_path.resolve())

        # Capture both staleness axes so the sub-reconcile sidecar matches
        # the rest of the reconcile family (step 4/5 reuse checks).
        sub_plan = parse_plan(plan_path)
        plan_fp = compute_plan_fingerprint(plan_path)
        code_fp = compute_code_fingerprint(sub_plan, plan_path, ctx.repo_root)

        # No-op today (detail-reconcile recs carry no directive), wired for the
        # uniform "stamp before save" rule so a future directive producer in
        # this lane is stamped automatically instead of saving it unstamped.
        stamped_sub_recs = stamp_target_signatures(sub_plan, sub_recs)
        sub_saved_path = save_review(
            plan_slug=plan_name,
            plan_path=plan_rel,
            repo_root=ctx.repo_root,
            report_md=f"detail-reconcile · step {step_id}",
            recommendations=stamped_sub_recs,
            kind="detail-reconcile",
            step_id=step_id,
            plan_fingerprint=plan_fp,
            code_fingerprint=code_fp,
            plan=sub_plan,
        )
        if not sub_recs:
            return (
                f"detail-reconcile on step {step_id} produced 0 "
                f"recommendations (saved to {sub_saved_path})"
            )

        if not sys.stdin.isatty():
            # Non-TTY: the dispatched reconcile can't walk interactively.
            # Don't let the saved findings become a silent orphan — warn
            # loudly with the exact resume command so the operator sees
            # unapplied work instead of a one-line note buried in output.
            resume = f"plan-tool reconcile-plan-walk {plan_name} --id {sub_saved_path.stem}"
            warn(
                f"detail-reconcile on step {step_id} saved "
                f"{len(sub_recs)} finding(s) to {sub_saved_path} but the "
                f"walk was skipped (non-TTY) — they are NOT applied. "
                f"Apply them with: {resume}"
            )
            return (
                f"detail-reconcile on step {step_id}: {len(sub_recs)} "
                f"finding(s) saved, NOT applied (non-TTY walk skipped) — "
                f"resume: {resume}"
            )

        sub_loaded = load_review(sub_saved_path)
        print(
            f"\n→ entering detail-reconcile walk for step {step_id} "
            f"({len(sub_recs)} rec(s))"
        )
        sub_action_fn = _build_review_action_fn(
            ctx=ctx, plan_path=plan_path, plan_name=plan_name,
            allow_split=allow_split,
            allow_structural_remedy=allow_structural_remedy,
            allow_merge_remedy=allow_merge_remedy,
            allow_reground_remedy=allow_reground_remedy,
            allow_structural_verdict=allow_structural_verdict,
            state=state, run_logger=run_logger,
            carried_findings=carried_findings,
        )
        reconcile._walk_with_reconcile_phase(
            sub_loaded, sub_action_fn, state,
            run_logger=run_logger,
            step_id=step_id,
        )
        return f"← returning to review walk for plan {plan_name!r}"

    def _dispatch_detail(step_id: int, *, force: bool) -> str:
        # No outer phase wrap here: ``generate_detail`` (step 4) already
        # emits its own ``detail-step-NN`` phase events. Adding a
        # ``detail_dispatch`` frame would be a one-line wrapper around
        # that tree; the timing is recoverable by summing the detail
        # phases.
        flag_label = " --force" if force else ""
        print(f"\n→ running plan-tool detail --step {step_id}{flag_label}…\n")
        try:
            results = generate_detail(
                plan_path,
                repo_root=ctx.repo_root,
                step_id=step_id,
                force=force,
                dry_run=False,
                run_logger=run_logger,
            )
        except _DetailError as exc:
            return f"detail error: {exc}"
        if not results:
            return f"detail produced no result for step {step_id}"
        result = results[0]
        if result.written:
            try:
                rel = result.output_path.resolve().relative_to(
                    ctx.repo_root.resolve()
                ).as_posix()
            except ValueError:
                rel = str(result.output_path)
            return f"wrote detail for step {step_id} to {rel}"
        reason = result.skipped_reason or "no reason recorded"
        return f"detail for step {step_id} skipped: {reason}"

    def _dispatch_apply_finding(rec) -> str:
        """Run Claude to apply the finding, show the diff and any
        correctness/completeness regressions or fixes the edit
        produced, then ask the user whether to keep the changes.
        Reverts on rejection or on a non-zero/UNKNOWN-verdict run.

        Wraps the entire body in a ``apply_finding_dispatch`` phase
        when a run_logger is bound, so the phase timing covers
        snapshot + diff + delta work alongside the claude call(s)
        from ``apply_finding`` itself. The phase outcome captures the
        user's keep/revert decision (``"success"`` / ``"reverted"``
        / ``"error"``).

        When ``reconcile_scope_guard`` is set (per-finding scope guard
        for ``_iterate_reconcile_loop``), captures a
        pre-apply ``snapshot_subtrees`` of the in-scope dirs and runs
        ``evaluate_apply_scope`` against the post-apply state in the
        ``finally`` block whenever the apply landed (phase_outcome ==
        "success" AND ``result is not None``). Reverted/error paths
        skip the scope eval -- they leave the tree at pre-apply state,
        so there are no out-of-scope edits to record.

        Per-finding drift halts: when the guard also
        carries ``iter_lock`` (with ``allow_drift=False``), this
        dispatcher additionally runs ``check_drift`` BEFORE
        ``apply_finding`` (to skip a likely-spurious claude call) and
        AFTER (to surface drift introduced during this finding's
        apply). On drift the dispatcher emits the drift-halt warning,
        sets ``state.halt_requested = True`` so the walker breaks,
        and signals merge-vs-halt via ``state.halt_merged``. The
        iteration body inspects those signals after the walk
        returns. ``state.work_landed_in_loop`` flips to True after
        each kept apply so subsequent per-finding pre-checks use
        ``"during"`` phrasing.
        """
        target_step_id = rec.step_id  # may be None for plan-wide claude recs
        print(
            f"\n→ applying finding to plan "
            f"(step {target_step_id if target_step_id is not None else '?'})…\n"
        )

        # Per-finding pre-apply drift check. Fires
        # only in reconcile-iteration mode (``reconcile_scope_guard``
        # set AND ``iter_lock`` populated AND drift not opted out).
        # On drift: emit_drift_halt_warning + signal halt to walker;
        # return a skip message without spending apply_finding tokens
        # (Lesson 2: don't waste tokens on a likely-spurious apply).
        if (
            reconcile_scope_guard is not None
            and reconcile_scope_guard.iter_lock is not None
            and not reconcile_scope_guard.allow_drift
            and state is not None
        ):
            from plan_tool.drift_detection import check_drift as _check_drift
            # Lazy: the halt emitter lives in reconcile.py, which imports
            # this module at module level — a top-level import here would
            # be a cycle. Call-time resolution also honors test patches
            # on plan_tool.cli.reconcile.
            from plan_tool.cli.reconcile import _emit_drift_halt_warning
            _pre_drifted = _check_drift(reconcile_scope_guard.iter_lock)
            if _pre_drifted:
                _emit_drift_halt_warning(
                    _pre_drifted,
                    phase=(
                        "during"
                        if state.work_landed_in_loop
                        else "before"
                    ),
                    finding_id=rec.id,
                    ctx_repo_root=reconcile_scope_guard.repo_root,
                    file_to_step=reconcile_scope_guard.file_to_step,
                )
                state.halt_requested = True
                state.halt_merged = False
                # apply_finding did NOT run -- no claude tokens spent,
                # no edits on disk. The walker uses this to persist
                # the rec as "skip" instead of "applied" so future
                # ``cmd_review_walk`` invocations don't see the rec
                # as resolved (finding-correctness fix).
                state.halt_apply_landed = False
                state.halt_finding_id = rec.id
                state.halt_drifted = list(_pre_drifted)
                # Skip apply_finding entirely -- the iteration body's
                # halt-signal branch runs auto_reconcile / scope-guard
                # plan emit / cleanup. The walker breaks after this
                # rec's annotation persists.
                return (
                    f"apply-finding skipped on pre-apply drift "
                    f"({len(_pre_drifted)} file(s)); iteration "
                    f"halting"
                )

        # Per-finding scope-guard snapshot. Taken BEFORE
        # apply_finding fires so the post-apply diff captures exactly
        # claude's edits. No-op closure when ``reconcile_scope_guard``
        # is None (every non-reconcile-iteration caller).
        scope_pre_snap: Optional[dict] = None
        if reconcile_scope_guard is not None:
            from plan_tool.scope_guard import snapshot_subtrees as _snap_subtrees
            scope_pre_snap = _snap_subtrees(reconcile_scope_guard.scope_dirs)

        if run_logger is not None:
            run_logger.phase_start(
                "apply_finding_dispatch",
                step_id=target_step_id,
            )
        phase_t0 = time.monotonic()
        phase_outcome = "success"
        result = None  # bound below; referenced from finally for #14 scope eval
        # Consume any operator feedback the walk stashed via its
        # ``(f)eedback`` choice: it steers THIS apply only, so read-and-
        # clear up front so it never leaks onto the next rec (or a retry
        # after a non-drift re-prompt). ``state`` is always bound inside
        # the builder; guard defensively anyway.
        operator_feedback = ""
        deferred_verdict: Optional[DeferredApplyVerdict] = None

        def _observe_verdict(outcome: DeferredApplyVerdict) -> None:
            nonlocal deferred_verdict
            deferred_verdict = outcome

        def _record_deferred_verdict() -> None:
            if deferred_verdict is None:
                return
            from plan_tool.telemetry import record_apply_verdict
            try:
                record_apply_verdict(
                    ctx.repo_root,
                    plan_slug=plan_name,
                    verdict=deferred_verdict.verdict,
                    step_id=str(deferred_verdict.step_id),
                    anchor=rec.anchor or "",
                    plan_fingerprint=_apply_verdict_plan_fp,
                )
            except Exception:
                pass

        def _record_invocation_failure() -> None:
            # Success-like verdicts remain deferred until the operator keeps
            # the edit. Invocation failures have no edit to accept or reject,
            # so persist them before the dispatcher's early failure returns.
            if (
                deferred_verdict is not None
                and deferred_verdict.verdict == "INVOCATION-FAILED"
            ):
                _record_deferred_verdict()

        if state is not None and state.pending_feedback:
            operator_feedback = state.pending_feedback
            state.pending_feedback = ""

        # Resolve the carried context just before applying so a dynamic
        # replay provider reflects verdicts recorded by earlier findings
        # in the same walk; a static sequence passes through verbatim.
        _carried = carried_findings() if callable(carried_findings) else carried_findings

        try:
            try:
                result = apply_finding(
                    plan_path,
                    repo_root=ctx.repo_root,
                    finding_body=format_recommendation_for_apply(rec),
                    targeted_fix=audit_targeted_fix(rec),
                    operator_feedback=operator_feedback or None,
                    carried_findings=_carried,
                    step_id=target_step_id,
                    plan_name=plan_name,
                    dry_run=False,
                    allow_structural_verdict=allow_structural_verdict,
                    run_logger=run_logger,
                    anchor=(rec.anchor or ""),
                    plan_fingerprint=_apply_verdict_plan_fp,
                    record_verdict=False,
                    verdict_observer=_observe_verdict,
                )
                # Surface this apply's verdict on the shared walk state so a
                # replay caller can accumulate it into the carried context for
                # later findings (the only channel that distinguishes a fresh
                # BLOCKED/BLOCKED-STRUCTURAL from a saved-annotation skip).
                if state is not None:
                    state.last_apply_verdict = result.verdict
                # Record this apply's launcher pre_snapshot so the
                # iteration loop's post-walk drift halt has a merged
                # baseline to feed the collision-sidecar (# sub-deliverable 3). Recorded before any keep/revert
                # branch -- save_collision_sidecars skips paths whose
                # current content matches the snapshot, so recording
                # even for revert paths is safe (those files restore
                # to match the snapshot → skipped on sidecar pass).
                if reconcile_scope_guard is not None:
                    reconcile_scope_guard.record_apply(result.pre_snapshot)
            except LauncherError as exc:
                phase_outcome = "error"
                _record_invocation_failure()
                # The apply attempt errored out, no edit landed — signal the
                # walk to record a non-terminal ``failed`` (not ``applied``;
                # a bare return reads as applied) so the gap is re-prompted
                # on the next walk rather than silently treated as resolved.
                state.apply_failed = True
                # No trustworthy verdict; a replay caller must treat this
                # as untrusted (open), not a deliberate skip.
                state.last_apply_verdict = "UNKNOWN"
                return f"apply-finding launcher error: {exc}"

            if result.exit_code != 0:
                phase_outcome = "error"
                _record_invocation_failure()
                # Apply failed and the snapshot was restored — the plan is
                # unchanged, so the walk records a non-terminal ``failed``
                # (re-prompted next walk), not ``applied`` or a terminal
                # ``skip`` that would drop the gap silently.
                state.apply_failed = True
                return (
                    f"apply-finding exited with code {result.exit_code}; "
                    "snapshot restored"
                )

            if result.verdict == "BLOCKED-STRUCTURAL":
                # The only correct fix is to split the step, which an apply
                # edit can't do. Revert any partial prose edit first
                # (apply_finding reverts only on a non-zero exit, not on a
                # non-APPLIED verdict), set phase_outcome="reverted" so the
                # finally scope-guard/drift eval never fires against the
                # bridge's out-of-scope plan/detail write, then route to the
                # escalate_to_split bridge. Ordered BEFORE the
                # ("BLOCKED", "NOT-APPLICABLE") arm: BLOCKED-STRUCTURAL isn't
                # in that tuple, so without this arm it would fall through to
                # the empty-diff no-op (a structural verdict carries no diff)
                # and report the wrong message.
                _revert_snapshot(result.pre_snapshot)
                phase_outcome = "reverted"
                state.apply_skip = True
                return _dispatch_structural_escalation(rec)

            if result.verdict in ("BLOCKED", "NOT-APPLICABLE"):
                # Claude declined to make the edit. The snapshot is
                # unchanged when nothing was attempted, but defensively
                # revert in case any partial edits slipped through.
                _revert_snapshot(result.pre_snapshot)
                note = result.summary or "(no summary)"
                phase_outcome = "reverted"
                state.apply_skip = True
                return f"apply-finding {result.verdict}: {note}"

            if not result.diff_text:
                # APPLIED with empty diff — Claude says it changed
                # something but nothing actually moved. Treat as a no-op.
                state.apply_skip = True
                return (
                    "apply-finding reported APPLIED but the plan file "
                    "didn't change; nothing to keep"
                )

            # Show the diff and any validation delta from the
            # correctness/completeness primitives.
            print("\n## Proposed plan edit\n")
            print(colorize_diff(result.diff_text))
            if result.summary:
                print(f"\nSummary: {result.summary}")
            if result.introduced_findings or result.resolved_findings:
                print("\nValidation:")
                for r in result.resolved_findings:
                    print(
                        f"  ✓ resolves {r.severity.upper()}: {r.title} "
                        f"[{confidence_label(r.confidence)}]"
                    )
                for r in result.introduced_findings:
                    print(
                        f"  ✗ introduces {r.severity.upper()}: {r.title} "
                        f"[{confidence_label(r.confidence)}]"
                    )
            # Hard-revert on post-edit parse failure: keeping the change
            # poisons the plan file so every subsequent apply in the walk
            # dies at parse_plan, wedging the loop. Override the user's
            # keep/revert choice — the rec stays unapplied for manual
            # handling.
            parse_broken = revert_apply_if_parse_broken(result)
            if parse_broken:
                phase_outcome = "reverted"
                state.apply_skip = True
                return (
                    "reverted apply-finding edits: post-edit plan failed "
                    "to parse (keeping would wedge the walk); rec left "
                    "for manual review"
                )
            if not sys.stdin.isatty():
                # Non-interactive: keep the change (no way to ask). The
                # outer flow normally suppresses apply auto-dispatch in
                # non-TTY contexts, so reaching this branch implies an
                # explicit non-interactive caller (e.g., a scripted apply).
                _record_deferred_verdict()
                return (
                    f"applied finding (non-TTY: kept without confirmation; "
                    f"summary: {result.summary})"
                )

            # Soft warning — default still keeps. The user sees the
            # regression and decides; a strict default-revert would
            # over-block legitimate edits like flipping done→current
            # (which legitimately surfaces a lessons-coverage finding
            # because that step is no longer done).
            if state.yes_to_all:
                answer = "y"
            else:
                import builtins
                prompt_label = "Keep these changes? [Y/n/a=all] "
                if result.introduced_findings:
                    n = len(result.introduced_findings)
                    prompt_label = (
                        f"Keep these changes despite {n} new "
                        f"finding{'s' if n != 1 else ''}? [Y/n/a=all] "
                    )
                answer = builtins.input(prompt_label).strip().lower()
                if answer in ("a", "all"):
                    state.yes_to_all = True
                    print(
                        "  (apply-all) enabled — remaining apply-finding "
                        "prompts and walk recs will auto-keep"
                    )
                    answer = "y"
            if answer in ("n", "no"):
                _revert_snapshot(result.pre_snapshot)
                phase_outcome = "reverted"
                state.apply_skip = True
                return (
                    "reverted apply-finding edits; rec left for manual review"
                )
            msg = f"applied finding: {result.summary}"
            if result.introduced_findings:
                msg += f" (kept despite {len(result.introduced_findings)} new finding(s))"
            _record_deferred_verdict()
            return msg
        finally:
            if run_logger is not None:
                run_logger.phase_end(
                    "apply_finding_dispatch",
                    duration_ms=int((time.monotonic() - phase_t0) * 1000),
                    outcome=phase_outcome,
                    step_id=target_step_id,
                )
            # Per-finding scope guard. Runs only when the
            # apply landed (phase_outcome == "success" — covers the
            # APPLIED+kept path as well as the APPLIED+empty-diff
            # no-op). The revert / launcher-error / non-zero-exit /
            # BLOCKED / NOT-APPLICABLE / parse-broken paths set
            # phase_outcome to "reverted" or "error" earlier and leave
            # the tree at the pre-apply state, so there are no
            # out-of-scope edits to evaluate.
            #
            # Mirrors cmd_completeness's per-finding scope-eval pattern
            # (cli.py ~5176-5212) with attribution prints driven by
            # ``reconcile_scope_guard.file_to_step``. ``scope_pre_snap``
            # is guaranteed non-None whenever
            # ``reconcile_scope_guard is not None`` because it's taken
            # at the top of the dispatcher before the try/except.
            if (
                reconcile_scope_guard is not None
                and scope_pre_snap is not None
                and phase_outcome == "success"
                and result is not None
            ):
                from plan_tool.scope_guard import (
                    evaluate_apply_scope as _eval_scope,
                    revert_out_of_scope as _revert_scope,
                    snapshot_subtrees as _snap_subtrees,
                )
                _scope_post_snap = _snap_subtrees(
                    reconcile_scope_guard.scope_dirs,
                )
                _scope_records = _eval_scope(
                    finding_id=rec.id,
                    finding_body=rec.body,
                    step_id=rec.step_id,
                    pre_snapshot=scope_pre_snap,
                    post_snapshot=_scope_post_snap,
                    in_scope_paths=reconcile_scope_guard.in_scope,
                    repo_root=reconcile_scope_guard.repo_root,
                    ignored_artifact_paths=(
                        reconcile_scope_guard.ignored_artifact_paths
                    ),
                )
                # Lazy: lives in reconcile.py, which imports this module
                # at module level (cycle); call-time binding also honors
                # test patches on plan_tool.cli.reconcile.
                from plan_tool.cli.reconcile import _print_attributed_files
                for r in _scope_records:
                    if r.impact_status == "reverted":
                        _revert_scope(r, scope_pre_snap)
                        print(
                            f"plan-tool: reverted out-of-scope code "
                            f"edit(s) from finding {r.finding_id} "
                            f"({len(r.out_of_scope_files)} file(s)):",
                            file=sys.stderr,
                        )
                        _print_attributed_files(
                            r.out_of_scope_files,
                            reconcile_scope_guard.repo_root,
                            reconcile_scope_guard.file_to_step,
                        )
                    elif r.impact_status == "kept-by-impact":
                        print(
                            f"plan-tool: kept out-of-scope code "
                            f"edit(s) from finding {r.finding_id} "
                            f"(referenced by in-scope file, "
                            f"{len(r.out_of_scope_files)} file(s)):",
                            file=sys.stderr,
                        )
                        _print_attributed_files(
                            r.out_of_scope_files,
                            reconcile_scope_guard.repo_root,
                            reconcile_scope_guard.file_to_step,
                        )
                    reconcile_scope_guard.scope_buffer.add(r)

            # Per-finding post-apply drift check + collision sidecar
            #. Runs only when the apply landed
            # (phase_outcome == "success") AND we're in reconcile-
            # iteration mode (guard + iter_lock present + drift not
            # opted out). Token preservation (Lesson 2) requires
            # KEEPING claude's edits on disk OR funneling them to a
            # sidecar -- no automatic revert here.
            #
            # On drift detected post-apply:
            # - emit warning with "during" phase (apply just landed)
            # - if collision-sidecar enabled, invoke
            #   ``handle_drift_collision`` with THIS apply's
            #   ``result.pre_snapshot`` (plan + step.detail). On
            #   merge-continue, refresh the lock's hash baseline so
            #   the next per-finding pre-check sees the merged state
            #   as clean. On declined / headless / EOF, fall through
            #   to the legacy halt path (iteration body runs
            #   auto-reconcile + scope-guard plan emit).
            # - signal halt via WalkState so the walker breaks. The
            #   iteration body inspects ``halt_merged`` to pick
            #   merge-continue vs. legacy halt.
            #
            # Mark ``work_landed_in_loop`` AFTER the drift branch:
            # if drift halted us, the flag's "during" semantics
            # still applies for the next loop pass; if not, the
            # next per-finding pre-check sees "during" correctly.
            if (
                reconcile_scope_guard is not None
                and reconcile_scope_guard.iter_lock is not None
                and not reconcile_scope_guard.allow_drift
                and phase_outcome == "success"
                and result is not None
                and state is not None
            ):
                from plan_tool.drift_detection import check_drift as _check_drift
                # Lazy for the same cycle/patch reasons as the pre-check.
                from plan_tool.cli.reconcile import _emit_drift_halt_warning
                _post_drifted = _check_drift(
                    reconcile_scope_guard.iter_lock,
                )
                if _post_drifted:
                    _emit_drift_halt_warning(
                        _post_drifted,
                        phase="during",
                        finding_id=rec.id,
                        ctx_repo_root=reconcile_scope_guard.repo_root,
                        file_to_step=reconcile_scope_guard.file_to_step,
                    )
                    merged = False
                    if reconcile_scope_guard.collision_sidecar_enabled:
                        from plan_tool.change_collision import (
                            handle_drift_collision,
                        )
                        if handle_drift_collision(
                            result.pre_snapshot,
                            repo_root=reconcile_scope_guard.repo_root,
                            yes=state.yes_to_all,
                        ):
                            from plan_tool.drift_detection import (
                                refresh_snapshot,
                            )
                            refresh_snapshot(
                                reconcile_scope_guard.iter_lock,
                            )
                            merged = True
                    state.halt_requested = True
                    state.halt_merged = merged
                    # apply_finding DID run -- claude tokens spent,
                    # edits landed (kept either on the original file
                    # in legacy mode or as a sidecar in collision-
                    # sidecar mode). The walker uses this to persist
                    # the rec as "applied" so the saved review
                    # reflects the work that occurred (# finding-correctness fix).
                    state.halt_apply_landed = True
                    state.halt_finding_id = rec.id
                    state.halt_drifted = list(_post_drifted)
            # Mark that THIS loop has now landed at least one
            # successful apply. Used by per-finding pre-apply drift
            # checks AND by the iteration body's pre-iter drift
            # check to pick "before" vs "during" phrasing. Set even
            # on the drift-halt branch above (the apply itself did
            # land; the halt is about subsequent applies).
            if (
                state is not None
                and phase_outcome == "success"
                and result is not None
            ):
                state.work_landed_in_loop = True

    def _dispatch_structural_escalation(
        rec, *, halt_on_applied: bool = False, guard_saved_directive: bool = False
    ) -> str:
        """Route a structural verdict/finding to the ``escalate_to_split``
        bridge — the only correct fix is a step split, which an apply edit
        can't do.

        Two callers: a ``BLOCKED-STRUCTURAL`` apply verdict (from
        ``_dispatch_apply_finding``) and the persisted ``medium``
        ``granularity-split`` MIXED-STEP finding (from ``action``). Both reuse
        the same bridge call and five-outcome status mapping.

        Always passes ``prompt_fn=None`` so the sole apply path is a
        genuine interactive ``input`` confirm on a TTY (a non-TTY
        auto-declines → recommend). Under ``state.yes_to_all`` it forces
        ``allow_split=False`` (recommend-only): a blanket fast-forward must
        not auto-confirm an irreversible structure mutation, unlike the
        reversible prose apply in ``_dispatch_apply_finding``.

        Maps each of the five ``EscalateResult.outcome`` values to a
        one-line walk status. On a landed ``applied`` split in
        reconcile-iteration mode it refreshes the drift baseline so the
        legitimate split is not re-detected as drift by the next finding's
        pre-apply ``check_drift``.

        ``halt_on_applied`` (set only by the ``granularity-split`` router
        branch) breaks the completeness-apply walk after an ``applied`` split:
        the 1→2 renumber makes every later saved finding's ``step_id`` stale.
        The ``BLOCKED-STRUCTURAL`` caller keeps the default (``False``) so the
        reconcile lane's post-split behavior is unchanged.

        ``guard_saved_directive`` (also set only by the ``granularity-split``
        router branch) runs the shared ``_saved_directive_is_stale(rec)`` check
        before the mutating bridge call: when this saved split finding's own
        target step changed on disk since it was computed, downgrade to
        recommend-only rather than escalate against a moved step id — mirroring
        the pre-apply guard ``_dispatch_reground_remedy`` /
        ``_dispatch_merge_remedy`` already carry. A separate concern from
        ``halt_on_applied`` (pre-apply refusal vs post-apply halt); kept a
        dedicated flag so the ``BLOCKED-STRUCTURAL`` verdict caller — a live
        verdict, not a persisted directive — never runs it.
        """
        # The split-proposer seam (Callable[[str], str], returns raw Claude
        # text) — the shape escalate_to_split.invoker expects, NOT launcher's
        # run-step Invoker. Body-local to keep this leaf import-light.
        from plan_tool.create import shell_claude_invoker

        # Plan-level structural verdicts (no target step — e.g.
        # plan-correctness / plan-completeness) name no concrete step.
        # escalate_to_split needs a step to split, and step_by_id(None)
        # would KeyError → a confusing "step None not found". Surface as an
        # operator-level re-decompose signal instead (invariant 1: never
        # silently drop the verdict).
        if rec.step_id is None:
            # Nothing mutated — record as skipped, not "applied" (else the walk
            # pre-skips it on re-runs). Mirrors the sibling reground/merge no-op
            # outcomes; idempotent for the BLOCKED-STRUCTURAL caller.
            apply_structural_outcome(
                state, rec, StructuralOutcomeEffects(resolved=False)
            )
            return (
                f"plan-level structural verdict on {rec.id}: no single "
                f"target step to split — re-decompose through a "
                f"session-directed edit"
            )

        # Pre-apply stale-directive guard (the shared
        # ``_saved_directive_is_stale`` freshness contract, as re-ground and
        # merge carry). Only the ``granularity-split`` router branch opts in
        # (``guard_saved_directive=True``); the ``BLOCKED-STRUCTURAL`` verdict
        # caller keeps the default off. Runs before ``escalate_to_split`` and
        # regardless of ``allow_split`` — a directive whose target step moved
        # is refused with the re-run message even in recommend-only mode.
        if guard_saved_directive and _saved_directive_is_stale(rec):
            apply_structural_outcome(
                state, rec, StructuralOutcomeEffects(resolved=False)
            )
            return (
                f"split escalation skipped for step {rec.step_id}: the plan "
                "changed since this finding was computed, so its step id may no "
                "longer name the mixed step. Re-run the diagnosis "
                "(completeness-audit) to regenerate it, then re-walk."
            )

        result = escalate_to_split(
            plan_path,
            step_id=rec.step_id,
            repo_root=ctx.repo_root,
            invoker=shell_claude_invoker,
            allow_split=structural_apply_allowed(allow_split, state),
            prompt_fn=None,
        )

        if result.outcome == "applied":
            # The renumbered plan + new detail files genuinely persisted.
            # In reconcile-iteration mode the "reverted" disposition leaves
            # the drift baseline untouched, so the next finding's pre-apply
            # check_drift would see the split's files as uncommitted drift
            # and halt spuriously. Refresh the baseline (same iter_lock
            # refresh_snapshot the collision-merge branch calls).
            if (
                reconcile_scope_guard is not None
                and reconcile_scope_guard.iter_lock is not None
            ):
                from plan_tool.drift_detection import refresh_snapshot
                refresh_snapshot(reconcile_scope_guard.iter_lock)
            # The split renumbered every step from the target onward under
            # ``halt_on_applied``, so every remaining saved finding's step_id is
            # now stale — the kernel halt keeps this rec ``applied`` past the
            # break. A resolved outcome; escalation never records the finding id.
            apply_structural_outcome(
                state,
                rec,
                StructuralOutcomeEffects(resolved=True, halt=halt_on_applied),
            )
            msg = (
                f"escalated structural finding: applied a 2-step split at "
                f"step {result.target_id}"
            )
            if halt_on_applied:
                msg += (
                    " — walk halted (the split renumbered the plan); re-run "
                    "the diagnosis (completeness-audit) and re-walk for any "
                    "remaining findings"
                )
            return msg
        # No split landed on any of the remaining outcomes — record the finding
        # as skipped, not "applied" (an "applied" annotation pre-skips it on the
        # next run and the required split is silently lost). Mirrors
        # _dispatch_reground_remedy / _dispatch_merge_remedy.
        apply_structural_outcome(
            state, rec, StructuralOutcomeEffects(resolved=False)
        )
        if result.outcome == "recommended":
            return (
                f"escalated structural finding to a split recommendation: "
                f"{result.recommendation.suggested_action}"
            )
        if result.outcome == "unsafe":
            # recommendation is None here (the recommended split would
            # itself be blocked by the same steps) — do not dereference it.
            return (
                f"structural escalation unsafe — downstream steps "
                f"{result.blocking} are not PENDING; resolve them, then run "
                f"plan-tool split"
            )
        if result.outcome == "proposal-unusable":
            return "structural escalation: split proposal unusable; left as-is"
        # step-missing
        return (
            f"structural escalation: step {rec.step_id} not found; "
            f"nothing escalated"
        )

    def _dispatch_reground_remedy(rec) -> str:
        """Route a ``granularity-merge`` re-ground finding to the
        ``reground_bridge`` actuator — the code-grounded remedy for a plan whose
        decomposition is stale relative to HEAD.

        The ``reground_rebaseline`` builder kwarg selects the bridge's
        *disposition*: off (default) marks the flagged already-built steps
        ``done``; on additionally writes a ``create --from-existing`` re-baseline
        seed under the default seed directory for them. The disposition never changes
        *whether* the re-ground actuates (the enable opt-in gate below is
        unchanged); ``repo_root=ctx.repo_root`` is forwarded unconditionally
        since the mark-done arm ignores it.

        Dispatch is driven by the parsed directive *kind* (step 4's
        ``parse_merge_action``), never the ``granularity-merge`` source, so a
        re-ground is never conflated with a (deferred) structural merge. Only a
        ``reground`` kind actuates; a ``merge`` kind (which no wired producer
        emits here) or a directive-less rec falls through to the manual-run
        notice — the merge dispatch branch ships with the deferred merge bridge.

        The bridge owns the whole apply-or-recommend gate. The walk supplies
        only the opt-in token (the re-ground effective opt-in ``_reground_opt_in``
        — the umbrella ``allow_structural_remedy`` OR the granular
        ``allow_reground_remedy`` — AND not a blanket ``yes_to_all``: a
        fast-forward must not auto-confirm an irreversible structure mutation,
        mirroring ``_dispatch_structural_escalation``) and forwards ``yes=False``
        so the sole apply path is a genuine TTY confirm.
        The directive's step ids are the only complete target set
        (``rec.step_id`` is ``None`` for a re-ground finding). Before actuating
        we guard **pre-apply** staleness: if this directive's own target steps
        changed since the finding was computed (its stamped ``target_signature``
        no longer matches the recomputed one), the saved ids now name different
        steps and ``mark_steps_done`` would flip the wrong ones to done — so we
        downgrade to recommend-only. (``mark_steps_done`` keeping every id only
        covers *post*-apply stability for a later directive, not this
        staleness.)
        """
        from plan_tool.reground import (
            DISPOSITION_MARK_DONE,
            DISPOSITION_REBASELINE,
            reground_bridge,
        )
        from plan_tool.review import MERGE_ACTION_REGROUND, parse_merge_action

        manual = (
            "suggested action isn't a recognized reconcile or detail "
            "invocation; run it manually in another shell"
        )
        directive = parse_merge_action(rec)
        if directive is None or directive.kind != MERGE_ACTION_REGROUND:
            # A stray call (the walk's r/run key dispatches even non-
            # dispatchable recs) or the deferred merge kind: nothing is
            # actuated here, so record ``skip`` — never mark a finding resolved
            # without an edit (the deferred merge bridge would otherwise land
            # here and silently drop a merge finding).
            apply_structural_outcome(
                state, rec, StructuralOutcomeEffects(resolved=False)
            )
            return manual

        step_ids = list(directive.step_ids)
        ids_str = ", ".join(str(i) for i in step_ids)

        # Defect-B fix (explicit session signal, not the ambiguous fingerprint):
        # a re-ground actuated earlier in THIS walk — via the r/run key — rewrote
        # the plan, so its fingerprint no longer matches and the stale-guard
        # below would misfire on the r-then-a re-dispatch, mislabelling the
        # *completed* re-ground. If we already applied this finding this session
        # it is done — resolve it before the stale-guard.
        if rec.id in state.applied_structural_finding_ids:
            return f"re-ground noop — steps {ids_str} already done"

        # Pre-apply stale-directive guard (the shared
        # ``_saved_directive_is_stale`` freshness contract): when this
        # directive's own target steps have changed on disk since the finding
        # was computed, its ids may name different steps now — refuse to mark
        # blind, downgrade to recommend-only. Runs BEFORE the bridge's noop
        # disposition, so a
        # genuinely-stale finding whose ids coincidentally now land on DONE
        # steps is still downgraded, not silently swallowed as resolved.
        if _saved_directive_is_stale(rec):
            apply_structural_outcome(
                state, rec, StructuralOutcomeEffects(resolved=False)
            )
            return (
                f"re-ground skipped for steps {ids_str}: the plan changed since "
                "this finding was computed, so its step ids may no longer name "
                "the already-built steps. Re-run the diagnosis (reconcile-plan "
                "or completeness-audit) to regenerate it, then re-walk."
            )

        result = reground_bridge(
            plan_path,
            step_ids=step_ids,
            allow_reground=structural_apply_allowed(_reground_opt_in, state),
            yes=False,
            disposition=(
                DISPOSITION_REBASELINE
                if reground_rebaseline
                else DISPOSITION_MARK_DONE
            ),
            repo_root=ctx.repo_root,
        )

        if result.outcome == "applied":
            # The bridge mutated the plan — a resolved outcome (the walk records
            # ``applied``). Record the finding id so an r-then-a re-dispatch
            # resolves via the session signal above instead of tripping the
            # (now-changed) stale-guard. Re-ground never halts.
            apply_structural_outcome(
                state,
                rec,
                StructuralOutcomeEffects(resolved=True, record_finding_id=True),
            )
            marked = ", ".join(str(i) for i in result.marked_ids)
            msg = f"re-grounded steps {marked} to done"
            if result.completed:
                msg += "; plan complete"
            elif result.new_current_id is not None:
                msg += f"; step {result.new_current_id} is now current"
            if result.seed_path is not None:
                # Re-baseline disposition: the seed carries the flagged steps as
                # done-context PLUS every remaining committed step as scope to
                # re-plan, so it supersedes this plan's remaining scope. Point
                # the operator at re-creating from it and retiring this plan so
                # two live plans never claim the same unbuilt work.
                msg += (
                    f"; re-baseline seed written to {result.seed_path} — it "
                    f"supersedes this plan's remaining scope, so re-create from "
                    f"it (plan-tool create --from-existing {result.seed_path}) "
                    f"and archive/retire this plan once the re-decompose lands"
                )
            return msg

        if result.outcome == "noop":
            # A *genuine* noop — the plan is fresh (the stale-guard passed) and
            # every named step is already ``done``, so the re-ground's desired
            # end state already holds and the finding is resolved, not skipped.
            # (The r-then-a re-dispatch of a re-ground we applied this session is
            # handled earlier by ``applied_structural_finding_ids``, before the
            # stale-guard — it never reaches here.)
            apply_structural_outcome(
                state, rec, StructuralOutcomeEffects(resolved=True)
            )
            return f"re-ground noop — steps {ids_str} already done"

        # recommended / unsafe / step-missing landed no edit — record ``skip``
        # so the finding isn't marked resolved (mirrors
        # ``_dispatch_file_check_create`` when nothing moved).
        apply_structural_outcome(
            state, rec, StructuralOutcomeEffects(resolved=False)
        )
        if result.outcome == "recommended":
            return (
                f"re-ground recommended for steps {ids_str}: pass "
                f"--reground or --apply-structural (with --include-info) and "
                f"confirm on a TTY to mark them done"
            )
        if result.outcome == "unsafe":
            blockers = ", ".join(str(i) for i in result.blocking)
            return (
                f"re-ground unsafe — steps {blockers} are parked "
                f"(deferred/wont-do); resolve them before re-grounding"
            )
        # step-missing
        blockers = ", ".join(str(i) for i in result.blocking)
        return f"re-ground: step(s) {blockers} not in plan; nothing marked"

    def _dispatch_merge_remedy(rec) -> str:
        """Route a ``granularity-merge`` *merge* finding to the ``merge_bridge``
        (fold-steps) actuator — the structural remedy for adjacent dependent
        steps fragmented too finely.

        Dispatch is driven by the parsed directive *kind* (``MERGE_ACTION_MERGE``
        from step 4's ``parse_merge_action``), never the ``granularity-merge``
        source, so a merge is never conflated with a re-ground. Only a ``merge``
        kind actuates; a ``reground`` kind or a directive-less rec falls through
        to the manual-run notice (re-ground has its own dispatcher). Re-checked
        internally because the walk's ``(r)un`` key can call ``action`` on a rec
        that never passed ``is_dispatchable``.

        The bridge owns the whole apply-or-recommend gate — validity, safety, and
        the TTY confirm. The walk supplies only the opt-in token (the merge
        effective opt-in ``_merge_opt_in`` — the umbrella
        ``allow_structural_remedy`` OR the granular ``allow_merge_remedy`` — AND
        not a blanket ``yes_to_all``: a fast-forward must not auto-confirm an
        irreversible fold, mirroring ``_dispatch_reground_remedy`` /
        ``_dispatch_structural_escalation``) and forwards ``yes=False`` so the
        sole apply path is a genuine TTY confirm.
        The directive's step ids are the authoritative target set —
        ``rec.step_id`` holds only the low member id, so it under-names the fold.

        Before actuating, guards **pre-apply** staleness via the shared
        ``_saved_directive_is_stale`` freshness contract (the same gate
        ``_dispatch_reground_remedy`` uses — merge and re-ground share one rule):
        if this directive's own target steps changed since the finding was
        computed, the saved ids may now name different steps, so ``merge_bridge``
        would fold the wrong ones — downgrade to recommend-only. ``merge_bridge``
        still re-parses the plan and owns merge *safety*
        (pending/canonical/uniform), but safety can't tell that valid-looking
        ids mean something else now.
        """
        from plan_tool.detail import merge_bridge
        from plan_tool.review import parse_merge_action

        manual = (
            "suggested action isn't a recognized reconcile or detail "
            "invocation; run it manually in another shell"
        )
        directive = parse_merge_action(rec)
        if directive is None or directive.kind != MERGE_ACTION_MERGE:
            # A stray call (the walk's r/run key dispatches even non-
            # dispatchable recs) or a re-ground kind routed here by mistake:
            # nothing is actuated, so record ``skip`` — never mark a finding
            # resolved without an edit.
            apply_structural_outcome(
                state, rec, StructuralOutcomeEffects(resolved=False)
            )
            return manual

        merge_ids = list(directive.step_ids)
        ids_str = ", ".join(str(i) for i in merge_ids)

        # A merge actuated earlier in THIS walk (via the r/run key) folded the
        # plan and changed its fingerprint, so the stale-guard below would
        # misfire on an r-then-a re-dispatch and mislabel the *completed* merge
        # as skipped. Mirror ``_dispatch_reground_remedy``'s session signal: if
        # we already applied this finding this session it is done — resolve it
        # before the stale-guard. (Belt-and-suspenders with the applied-branch
        # halt below, which already breaks the walk after the first merge.)
        if rec.id in state.applied_structural_finding_ids:
            return f"merge noop — steps {ids_str} already folded"

        # Pre-apply stale-directive guard — the same
        # ``_saved_directive_is_stale`` contract the re-ground dispatcher gates
        # on, so a stale saved merge directive can't fold the wrong steps after
        # the plan was edited/renumbered. Runs BEFORE ``merge_bridge`` so a
        # genuinely-stale finding whose ids coincidentally still look foldable
        # is downgraded, not actuated.
        if _saved_directive_is_stale(rec):
            apply_structural_outcome(
                state, rec, StructuralOutcomeEffects(resolved=False)
            )
            return (
                f"merge skipped for steps {ids_str}: the plan changed since "
                "this finding was computed, so its step ids may no longer name "
                "the intended steps. Re-run the diagnosis (reconcile-plan or "
                "completeness-audit) to regenerate it, then re-walk."
            )

        result = merge_bridge(
            plan_path,
            merge_ids=merge_ids,
            allow_merge=structural_apply_allowed(_merge_opt_in, state),
            yes=False,
            repo_root=ctx.repo_root,
            run_logger=run_logger,
        )

        if result.outcome == "applied":
            # The fold renumbered the plan on disk — a resolved outcome (records
            # ``applied``). Record the id so an r-then-a re-dispatch resolves via
            # the session signal, and halt the walk so later saved recs (which
            # still carry pre-merge step ids) can't edit the wrong step;
            # ``halt_apply_landed`` (via the kernel halt) keeps this rec
            # ``applied`` past the break.
            apply_structural_outcome(
                state,
                rec,
                StructuralOutcomeEffects(
                    resolved=True, record_finding_id=True, halt=True
                ),
            )
            # The renumber invalidates every remaining saved rec's step ids, so
            # the walk stops here; the operator re-runs the diagnosis (whose
            # fingerprint the fold just changed) and re-walks for the rest.
            halted = (
                " — walk halted (the merge renumbered the plan); re-run the "
                "diagnosis and re-walk for any remaining findings"
            )
            if result.apply_error:
                # Fold persisted but re-authoring the merged step failed; the
                # plan is folded-but-unauthored. Still ``applied`` (the
                # structural fold landed), but tell the operator to finish it.
                return (
                    f"merged steps {ids_str} but re-authoring the merged step "
                    f"failed ({result.apply_error}); complete it with "
                    f"`plan-tool detail {plan_name} --step <merged-id>`{halted}"
                )
            merged = result.merge_result
            if merged is not None:
                folded = ", ".join(str(i) for i in merged.folded_ids)
                return (
                    f"merged steps {folded} into step {merged.merged_id} "
                    f"({merged.merged_title!r}){halted}"
                )
            return f"merged steps {ids_str}{halted}"

        # recommended / unsafe / invalid landed no edit — record ``skip`` so the
        # finding isn't marked resolved (mirrors ``_dispatch_reground_remedy``).
        apply_structural_outcome(
            state, rec, StructuralOutcomeEffects(resolved=False)
        )
        if result.outcome == "recommended":
            # No ``--include-info``: a pairwise merge finding stays visible under
            # the default info hide (``is_pairwise_merge_finding`` carve-out), so
            # only ``--apply-structural`` + a TTY confirm are needed to fold.
            return (
                f"merge recommended for steps {ids_str}: pass "
                f"--merge or --apply-structural and confirm on a TTY to fold "
                f"them"
            )
        if result.outcome == "unsafe":
            blockers = ", ".join(str(i) for i in result.blocking_ids)
            return (
                f"merge unsafe — steps {blockers} are done; "
                f"restructure via re-plan instead"
            )
        # invalid
        return (
            f"merge invalid for steps {ids_str}: the requested set can't be "
            f"folded (need >=2 pending, canonically-numbered, uniform-scope "
            f"steps)"
        )

    def _dispatch_file_check_create(rec):
        """Resolve a MISSING_PARENT file-check finding deterministically.

        Two outcomes, chosen by an inline prompt:

        - ``(c)reate`` — the step legitimately produces the file: move
          the path from the step's ``files:`` into ``creates:`` and
          write the plan. A ``creates:`` path is expected to be absent
          until the step runs, so the doesn't-resolve finding stops
          firing for good.
        - ``(f)ix`` (or anything else) — the path is a typo/stale ref:
          flip ``state.apply_skip`` so the walk records ``skip`` (no
          edit landed) and the user fixes the path through a direct edit.

        Apply-all (``state.yes_to_all``) auto-picks ``create`` without
        prompting — consistent with "apply everything".
        """
        path = file_check_create_target(rec)
        if path is None:  # defensive: action() only routes qualifying recs
            return "not a movable file-check finding"
        step_id = rec.step_id

        if state.yes_to_all:
            # Inverts the bridges' fast-forward gate: -y auto-applies create;
            # see structural_apply_allowed's docstring for why file-check is
            # deliberately excluded from that helper.
            choice = "c"
        else:
            import builtins
            print(
                f"\n  This path's parent dir doesn't exist. Does step "
                f"{step_id} create `{path}`?"
            )
            print("  (c) yes, legit new file  -> move it to `creates:`")
            print("  (f) no, path is wrong    -> leave a note, skip")
            choice = builtins.input("  (c)reate / (f)ix > ").strip().lower()

        if choice not in ("c", "create"):
            apply_structural_outcome(
                state, rec, StructuralOutcomeEffects(resolved=False)
            )
            return (
                f"left step {step_id}'s files: unchanged — fix or remove "
                f"the path `{path}` in the plan"
            )

        try:
            plan = parse_plan(plan_path)
        except (ParseError, ValidationError) as exc:
            apply_structural_outcome(
                state, rec, StructuralOutcomeEffects(resolved=False)
            )
            return f"could not read plan to edit: {exc}"
        step = next((s for s in plan.steps if s.id == step_id), None)
        if step is None:
            apply_structural_outcome(
                state, rec, StructuralOutcomeEffects(resolved=False)
            )
            return f"step {step_id} not found in plan; nothing moved"
        moved = False
        if path in step.files:
            step.files = [f for f in step.files if f != path]
            moved = True
        if path not in step.creates:
            step.creates.append(path)
            moved = True
        if not moved:
            # The path already resolves as ``creates:`` — a resolved outcome
            # (nothing to write, but the finding is settled).
            apply_structural_outcome(
                state, rec, StructuralOutcomeEffects(resolved=True)
            )
            return (
                f"`{path}` already declared under step {step_id}'s "
                f"creates:; nothing to do"
            )
        write_plan(plan_path, plan)
        apply_structural_outcome(
            state, rec, StructuralOutcomeEffects(resolved=True)
        )
        return (
            f"moved `{path}` from files: to creates: on step {step_id}; "
            f"plan written"
        )

    def action(rec):
        if rec.source in _COMMAND_LOCAL_APPLY_SOURCES:
            if not rec.suggested_action:
                return "no suggested action on this recommendation"
            return (
                "suggested action isn't a recognized reconcile or detail "
                "invocation; run it manually in another shell"
            )
        descriptor = recognized_action(rec)
        if descriptor is not None:
            if descriptor.kind == "detail-reconcile":
                return _dispatch_detail_reconcile(descriptor.step_id)
            if descriptor.kind == "detail":
                return _dispatch_detail(
                    descriptor.step_id, force=descriptor.force
                )
            # Defensive: a new dispatcher kind was added to
            # recognized_action without a matching branch here.
            raise AssertionError(
                f"unhandled recognized action kind: {descriptor.kind!r}"
            )
        if split_escalation_target(
            rec, extra_apply_sources=extra_apply_sources
        ):
            # A ``medium`` ``granularity-split`` MIXED-STEP finding: route to
            # the escalate-to-split bridge as a structural dispatch, never an
            # ``apply_finding`` Claude edit. Placed BEFORE the
            # ``should_apply_as_finding`` branch so it can't burn an apply
            # attempt first (``should_apply_as_finding`` also excludes
            # structural sources, so this ordering is belt-and-suspenders).
            # ``halt_on_applied`` stops the completeness-apply walk after an
            # applied split renumbers the plan; ``guard_saved_directive`` refuses
            # a saved split whose target step moved since it was computed.
            return _dispatch_structural_escalation(
                rec, halt_on_applied=True, guard_saved_directive=True
            )
        if should_apply_as_finding(rec, extra_sources=extra_apply_sources):
            return _dispatch_apply_finding(rec)
        if file_check_create_target(rec) is not None:
            return _dispatch_file_check_create(rec)
        merge_directive = merge_remedy_target(rec)
        if merge_directive is not None:
            # Split by directive kind — never the shared ``granularity-merge``
            # source — so a merge and a re-ground reach their own bridge.
            if merge_directive.kind == MERGE_ACTION_MERGE:
                return _dispatch_merge_remedy(rec)
            return _dispatch_reground_remedy(rec)
        if not rec.suggested_action:
            return "no suggested action on this recommendation"
        return (
            "suggested action isn't a recognized reconcile or detail "
            "invocation; run it manually in another shell"
        )

    return action
