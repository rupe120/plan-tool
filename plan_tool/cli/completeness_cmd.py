"""Conceptual-completeness command module — the ``completeness-audit`` /
``completeness-apply`` verbs.

Two handlers answer "is this plan correct, complete, and unambiguous?"

- ``completeness-audit`` (``cmd_completeness``)
  layers deterministic well-formedness checks (body sections, detail
  files, dep/path resolution, lessons coverage — no claude call) under a
  multi-pass conceptual audit of the plan's own concepts grounded in the
  per-step detail bundle, and optionally drives an ``--iterate``
  convergence loop that applies open findings and re-audits.
- ``completeness-apply`` (``cmd_completeness_apply``) replays the saved
  audit's ``plan-correctness`` and ``plan-completeness`` findings through
  the gap walker.

``cmd_completeness`` is orchestration only: parse / banner / budget, then
delegation to named phase helpers — ``_run_deterministic_checks`` (the
well-formedness battery, no-claude except the opt-in per-step MIXED-STEP
purity pass), ``_sample_conceptual_audit`` (the single audit call), and the
``--iterate`` convergence loop and pure rendering/persistence phases in
:mod:`plan_tool.cli.completeness_phases`
(``_run_iterate_convergence_loop`` / ``_render_completeness_json`` /
``_render_grouped_report`` / ``_persist_and_present_report``).

Import edge is one-directional: this module imports the cycle-free leaves
(``context`` / ``parser`` / ``completeness_phases``), the step-15
reconcile engine (``reconcile``), and domain packages — never ``app``.
Each handler's
claude-driving collaborator (``walk_recommendations``) is a module global
of :mod:`plan_tool.cli.completeness_phases`, so a monkeypatch that drives
``completeness-apply``'s walk must target
``plan_tool.cli.completeness_phases``; the body-local domain imports
(``plan_tool.review.*``, ``plan_tool.launcher.apply_finding``) stay the
monkeypatch seams the legacy suites rely on. ``app`` re-imports every moved
name so the package surface and ``authoring.cmd_detail``'s
``app.cmd_completeness`` forward-call keep resolving.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from plan_tool.convergence import (
    DEFAULT_ITERATION_BUDGET_SECONDS,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_MAX_STALL_ROUNDS,
    is_blocking,
)
from plan_tool.create import CreateError
from plan_tool.review_persistence import AuditInputError
from plan_tool.detail_artifacts import derive_jira_detail_path
from plan_tool.jira_grade import (
    GRADE_DEFAULT,
    GRADE_JIRA,
    GRADE_RUN,
    JIRA_GRADE_VALUES,
)
from plan_tool.locator import resolve_plan_for_context
from plan_tool.pathutil import literal_path
from plan_tool.parser import (
    ParseError,
    UnsupportedPlanFormatVersionError,
    ValidationError,
    parse_plan,
)
from plan_tool.review import AUDIT_DEFAULT_DRY_ROUNDS
from plan_tool.review_persistence import audit_coverage_qualifies_sample
from plan_tool.style import (
    error,
    info,
    success,
    warn,
)

from plan_tool.cli.context import _load_context, _resolve_iterative_budget
from plan_tool.cli.gitcommit import commit_all, working_tree_dirty
from plan_tool.cli.parser import Handler, make_yes_parent
from plan_tool.cli.reconcile import _print_grouped_drift_files
from plan_tool.cli import completeness_phases

# _finding_progress_label and _fmt_finding_counts have no call site in this
# file -- they're imported so app.py can re-import them transitively from
# this module (app.py:273-274). Do not drop either as "dead": app.py's
# import breaks if this file stops re-exporting them.
from plan_tool.cli.completeness_phases import (
    _IterateOutcome,
    _REMAP_STOP_FOR_CONCEPTUAL_BAR,
    HALT_DRIFT_REASONS,
    _completeness_detail_grade,
    _conceptual_bar_from_audit_recs,
    _coverage_input_from_reusable_audit,
    _effective_audit_passes,
    _finding_progress_label,
    _fmt_finding_counts,
    _persist_and_present_report,
    _render_completeness_json,
    _render_grouped_report,
    _resolve_apply_walk_targets,
    _resolve_plan_for_report,
    _resolve_saved_completeness_audit,
    _run_apply_walk,
    _run_deterministic_checks,
    _sample_conceptual_audit,
    _sampled_bundle_status,
    _split_conceptual_recs,
    _warn_audit_incomplete,
    _warn_if_audit_incomplete,
    compute_conceptual_bar_blocking_ids,
    derive_audit_stage,
)
from plan_tool.review_persistence import STALE_REVISION_STATUSES
from plan_tool.completeness_report import (
    DeterministicArmFinding,
    UNTRUSTED_PERSISTENT,
    UNTRUSTED_STALE_REVISION,
    UNTRUSTED_TRANSIENT,
    blocking_verdict_from_gate,
)


def cmd_completeness_apply(args: argparse.Namespace) -> int:
    """Walk the conceptual gaps from a saved audit and apply gap-closing
    edits, one finding at a time — and deterministically resolve the
    audit's files-coherence drift (see :func:`_apply_files_coherence`),
    the structural subset ``apply_finding`` can't touch because it edits
    prose, not frontmatter.

    Walks BOTH conceptual sources — ``plan-correctness`` (design gaps,
    including material ambiguity) first, then ``plan-completeness`` (what's
    missing). Under the
    read-only-audit split (#85) the ``completeness-audit --iterate`` loop
    applies only its deterministic well-formedness findings and persists
    both conceptual sources *unapplied*, so this verb is the sole mutator
    of the conceptual gap map.

    Pairs with ``plan-tool completeness-audit`` (which finds the gaps
    and saves them to
    ``plan-details/<slug>/reports/<ts>-completeness.json``).
    This verb does NOT re-run the audit — it replays the saved findings
    and routes each through ``apply_finding`` so Claude proposes a
    focused edit per gap.

    Always interactive: one propose-then-confirm prompt per gap, so the
    operator reviews each conceptual issue in context. There is no
    blanket auto-apply — the value of this verb is the per-gap context it
    surfaces, and that only pays off with a human in the loop. On a
    non-interactive stdin (CI / pipe) the conceptual walk is skipped and
    the gaps are reported instead. ``--anchor <slug>`` (repeatable)
    restricts the walk to specific gaps by their ``[anchor-slug]``.

    The deterministic files-coherence fix (adding cited real-file paths
    to a step's ``allowed_mentions:``) is mechanical, not conceptual, so
    it runs without a prompt when a complete detail bundle exists. On a
    bare plan only ``plan-correctness`` gaps are walked; other saved
    sources are reported as withheld until detail exists.

    See ``docs/reference/contracts/process.md`` for the audit/apply authority split.
    """
    warn(
        "completeness-apply is going away (BACKLOG #376): walking findings "
        "one gap at a time is slower than reading the whole report at once, "
        "and the slow pace obscures whether the plan is actually converging "
        "-- read the saved report and make a session-directed edit to the "
        "plan/detail files "
        "instead."
    )
    ctx = _load_context(args)
    # ``--commit`` clean-tree gate up front (fail fast before loading the
    # saved audit): the end-of-run ``git add -A`` must not fold in
    # pre-existing changes.
    if getattr(args, "commit", False) and working_tree_dirty(ctx.repo_root):
        error(
            "--commit requires a clean working tree (commit or stash your "
            "changes first)."
        )
        return 2

    resolution = _resolve_saved_completeness_audit(args, ctx)
    if not resolution.ok:
        error(resolution.message)
        return resolution.rc
    plan_path = resolution.plan_path
    saved_path = resolution.saved_path
    saved = resolution.saved
    pre_apply_advisory_display = resolution.pre_apply_advisory_display

    # Keep the one parent-process presenter to hand to the parallel lane too;
    # its idempotence prevents a worker/replay duplicate.
    advisory_presented = False

    def _present_pre_apply_advisory() -> None:
        nonlocal advisory_presented
        if advisory_presented or pre_apply_advisory_display is None:
            return
        from plan_tool.completeness_report import render_audit_shape_advisory_console

        print(render_audit_shape_advisory_console(pre_apply_advisory_display))
        advisory_presented = True

    _present_pre_apply_advisory()

    # Freshness gate (BACKLOG #61 slice 3): this verb replays a *saved* sidecar,
    # so warn if the detail bundle drifted since the audit — those findings may
    # no longer match the changed detail files. The walk is interactive, so the
    # operator skips stale gaps per-finding after this flag.
    if resolution.drifted_detail:
        warn(
            f"this saved completeness audit may be stale — "
            f"{len(resolution.drifted_detail)} detail file(s) changed since it "
            f"was saved ({saved.created_at}); its findings may no longer match "
            f"those files. Re-run `plan-tool completeness-audit "
            f"{args.name}` for current findings before applying."
        )

    targets = _resolve_apply_walk_targets(
        saved, args=args, ctx=ctx, plan_path=plan_path,
    )
    if not targets.ok:
        if targets.message is not None:
            error(targets.message)
        return targets.rc

    return _run_apply_walk(
        targets.walk_recs,
        targets.conceptual_walk_recs,
        saved=saved,
        saved_path=saved_path,
        plan_path=plan_path,
        ctx=ctx,
        args=args,
        parallel=targets.parallel,
        plan_is_bare=targets.plan_is_bare,
        pre_apply_presentation=_present_pre_apply_advisory,
    )


def _completeness_commit_subject(slug: str) -> str:
    """Commit subject for a ``completeness-audit --commit --iterate`` run
    (pure, so a test can assert the format without shelling out)."""
    return f"plan({slug}): completeness — applied audit findings"


def _reject_grade_conflicts(args, detail_grade: str) -> Optional[int]:
    """Reject flags whose machinery is grounded on the run-grade bundle.

    Returns ``2`` (after printing the redirect) for ``--grade jira``
    combined with ``--iterate`` or an explicit reuse request, else
    ``None``. Called before the reuse lookup, the run log, and any claude
    call, so a rejected invocation spends nothing and leaves no state.
    """
    if detail_grade != GRADE_JIRA:
        return None
    if getattr(args, "iterate", False):
        error(
            f"--grade {GRADE_JIRA} is mutually exclusive with --iterate: the "
            "apply loop's checkpoint, drift watch, and commit machinery all "
            "act on the run-grade bundle. Audit at jira grade without "
            "--iterate, or converge the run-grade bundle first."
        )
        return 2
    if getattr(args, "reuse_audit", None) is True or getattr(
        args, "reuse_audit_id", None
    ):
        error(
            f"--grade {GRADE_JIRA} cannot reuse a saved audit: every saved "
            "audit is grounded on the run-grade bundle and carries no grade "
            "marker, so its freshness check (plan + code fingerprints) would "
            "call it fresh for this run. Drop --reuse-audit/--reuse-audit-id "
            "to audit fresh at jira grade."
        )
        return 2
    return None


def _jira_grounding_line(plan, plan_path: Path, repo_root: Path) -> str:
    """The banner line naming the jira-grade bundle this audit reads.

    The directory comes from :func:`derive_jira_detail_path` rather than a
    second copy of the layout, so the line can never name a directory the
    resolver does not use. A step-less plan gets the bare label. Deliberately
    POSIX-always, unlike this file's :func:`literal_path` use — not a
    lexical-warning path.
    """
    label = "plan-tool: grounding: jira-grade detail bundle"
    if not plan.steps:
        return label
    jira_dir = derive_jira_detail_path(plan_path, plan, plan.steps[0]).parent
    try:
        shown = jira_dir.relative_to(repo_root).as_posix()
    except ValueError:
        shown = jira_dir.as_posix()
    return f"{label} ({shown}/)"


def _print_stale_detail_preflight(plan, plan_path: Path) -> None:
    """Print `status`'s stale-detail warning here too, before any Claude
    call — a stale-detail contradiction otherwise reads as a design defect
    once the conceptual pass finds it (BACKLOG #165)."""
    from plan_tool.grounding import stale_detail_warning

    warning = stale_detail_warning(plan, plan_path)
    if warning:
        print(f"plan-tool: {warning}", file=sys.stderr)


def _warn_sidecar_suppressed() -> None:
    """Announce what a jira-grade audit did not persist.

    Bound to the audit *completing*, not to the report write: the ``--json``
    path returns before any report is written, so an operator would otherwise
    see a normal-looking audit that silently persisted nothing. Documenting
    the suppression in a reference doc is not exposure — this line is.
    """
    warn(
        "no findings sidecar written for this jira-grade audit — no audit "
        "history, no --reuse-audit, and no `plan-tool convergence` for this "
        "grade. The markdown report is still saved."
    )


def _accept_reuse(ru, *, advisory_out=None, coverage_out=None) -> list:
    """Announce reuse and return the saved correctness+conceptual union
    (correctness first, matching ``cmd_completeness``'s downstream axis
    split).

    ``coverage_out`` mirrors ``advisory_out`` so the findings-only return
    contract stays stable.  Its value is the known-or-unknown coverage result
    exposed by :class:`plan_tool.completeness_report.ReusableAudit`, never a
    second read of the saved sidecar.
    """
    recs = list(ru.correctness_recs) + list(ru.conceptual_recs)
    print(
        f"plan-tool: reusing saved conceptual audit ({len(recs)} finding(s)) "
        f"— skipping the conceptual Claude call",
        file=sys.stderr,
    )
    if advisory_out is not None:
        advisory_out[:] = [getattr(ru.saved, "audit_shape_advisory", None)]
    if coverage_out is not None:
        coverage_out[:] = [ru.audit_coverage]
    return recs


def _coverage_for_sidecar(coverage):
    """Keep missing legacy provenance absent when a later sidecar is written."""
    from plan_tool.review_persistence import normalize_audit_coverage

    return coverage if normalize_audit_coverage(coverage) is not None else None


def _note_code_drift(drifted_code, plan, ctx) -> None:
    """Attributed staleness note: list the drifted code files grouped by
    owning step (the step's ``N: title`` printed once as a header). Detecting
    drift and re-running the audit is normal operation, not a problem — so it
    emits at info level (no revert, no rc change).

    No recovery hint is printed: the staleness self-heals. This run already
    re-audits against current code, and ``--commit`` rewrites the sidecar's
    code fingerprint, so the message does not recur. (The old ``detail
    --reconcile`` hint was misleading — that command never touches the
    completeness sidecar this check reads, so it could not clear the note.)"""
    from plan_tool.scope_guard import build_file_to_step_map

    file_to_step = build_file_to_step_map(plan, ctx.repo_root)
    info(
        f"saved conceptual audit is stale ({len(drifted_code)} code "
        f"file(s) changed since the audit); re-running. Drifted files:"
    )
    _print_grouped_drift_files(drifted_code, ctx.repo_root, file_to_step)


def _note_removed_code_files(removed_code, plan, ctx) -> None:
    """Attribute deleted declared files without treating them as code drift.

    The saved sidecar is stale and needs a fresh audit, but the deletion does
    not justify a reconcile-plan suggestion: it is a footprint membership
    change, not a content edit. The unchanged plan still supplies the
    file-to-step mapping needed to name the missing file precisely.
    """
    from plan_tool.scope_guard import build_file_to_step_map

    file_to_step = build_file_to_step_map(plan, ctx.repo_root)
    info(
        f"saved conceptual audit is stale ({len(removed_code)} declared code "
        f"file(s) removed since the audit); re-running. Removed files:"
    )
    _print_grouped_drift_files(removed_code, ctx.repo_root, file_to_step)


def _resolve_audit_reuse(
    plan,
    path,
    ctx,
    args,
    *,
    drift_out=None,
    advisory_out=None,
    coverage_out=None,
    audit_input_snapshot=None,
) -> Optional[list]:
    """Map (flag state, freshness verdict, TTY) → reuse-or-fresh.

    Returns the saved correctness+conceptual rec union (correctness
    first) to substitute for a fresh conceptual audit, or ``None`` to
    audit fresh. A stale or missing save always declines to a fresh
    audit — never a non-zero exit (failure-to-complete only).

    ``drift_out`` is an optional single-element mutable list the caller
    passes to learn whether code drifted under the plan since its last
    audit (the same ``not ru.code_match and ru.drifted_code`` condition
    that fires :func:`_note_code_drift`). When supplied, ``drift_out[0]``
    is set to that boolean so the report renderers can surface a
    ``reconcile-plan`` suggestion (BACKLOG #65). Kept an out-param so the
    return type/contract the reuse-policy tests assert on is unchanged.
    ``coverage_out`` follows the same additive pattern as ``advisory_out``:
    accepted reuse stores the :class:`ReusableAudit` coverage result in its
    sole element, while every fresh-audit path leaves it untouched.
    """
    # 1) Hard opt-out: --no-reuse-audit never even looks up a sidecar.
    if getattr(args, "reuse_audit", None) is False:
        return None

    # 2) Look up the newest (or pinned) saved completeness audit. Body-local
    # so the test monkeypatch on ``plan_tool.completeness_report`` intercepts.
    from plan_tool.completeness_report import resolve_reusable_audit

    ru = resolve_reusable_audit(
        args.name,
        ctx.repo_root,
        plan_path=path,
        review_id=getattr(args, "reuse_audit_id", None),
        audit_input_snapshot=audit_input_snapshot,
    )

    # 3) Miss. An explicit --reuse-audit-id that matched nothing is a
    # user-facing note; an unpinned miss is the normal first-run path.
    if ru is None:
        reuse_id = getattr(args, "reuse_audit_id", None)
        if reuse_id:
            error(
                f"no saved completeness audit matched --reuse-audit-id "
                f"{reuse_id!r}; running a fresh audit"
            )
        return None

    # 4) Stale → decline + fall back to fresh. Both axes report at info
    # level: a detected code/plan change that triggers a re-audit is normal
    # operation (useful to surface, not a problem). Code-side drift gets the
    # step-grouped file list; plan-side drift gets a one-line note.
    if not ru.fresh:
        # An otherwise unchanged plan retains valid ownership for a deleted
        # declared file, so name it by step. Keep removals separate from
        # actual content drift: only content changes set ``drift_out`` and
        # later surface a reconcile-plan recommendation.
        removed_code = []
        if ru.plan_match:
            removed_code = list(ru.footprint_removed)
        if not ru.code_match:
            if ru.drifted_code:
                if drift_out is not None:
                    drift_out[0] = True
                _note_code_drift(ru.drifted_code, plan, ctx)
            if removed_code:
                _note_removed_code_files(removed_code, plan, ctx)
            if not ru.drifted_code and not removed_code and (
                ru.footprint_added or ru.footprint_removed
            ):
                info(
                    f"saved conceptual audit is stale (plan footprint changed: "
                    f"{len(ru.footprint_added)} added, "
                    f"{len(ru.footprint_removed)} removed since the audit); "
                    f"re-running"
                )
        elif not ru.plan_match:
            info(
                f"saved conceptual audit is stale (plan changed since "
                f"{ru.saved.created_at}); re-running"
            )
        return None

    # 5) Fresh → decide by flag.
    reuse_flag = getattr(args, "reuse_audit", None)

    def _reuse_is_explicit() -> bool:
        return reuse_flag is True or getattr(args, "reuse_audit_id", None) is not None

    if reuse_flag is True:
        # Explicit --reuse-audit always wins, even over --audit-passes N and
        # weak conformance evidence -- the operator asked for this exact
        # save on purpose.
        return _accept_reuse(
            ru, advisory_out=advisory_out, coverage_out=coverage_out
        )

    # reuse_flag is None (prompt). An explicit --audit-passes N means the
    # operator asked for a fresh audit — suppress the auto-accept/prompt
    # and re-audit. (Subordinate to --reuse-audit above; ahead of
    # auto-accept below.) The default pass count leaves audit_passes
    # None, so it does NOT trigger this.
    if getattr(args, "audit_passes", None) is not None:
        return None

    # Force non-interactive (auto-accept) under --yes, --json (machine
    # output mustn't be corrupted by a prompt), or a non-TTY stdin.
    non_interactive = (
        getattr(args, "yes", False)
        or getattr(args, "json", False)
        or not sys.stdin.isatty()
    )
    if non_interactive:
        # Auto-accept paths decline weak conformance evidence and audit
        # fresh instead -- no human is present to judge a non-qualifying
        # sample, so default to the safer re-audit. An explicit
        # --reuse-audit-id still wins (the operator pinned this exact
        # review on purpose). This check must not gate the interactive
        # prompt below: a human at a live TTY should still be asked and
        # can decide for themselves, the same as any other saved audit.
        if (
            not audit_coverage_qualifies_sample(ru.audit_coverage)
            and not _reuse_is_explicit()
        ):
            _warn_audit_incomplete(reuse=True)
            return None
        return _accept_reuse(
            ru, advisory_out=advisory_out, coverage_out=coverage_out
        )

    # Interactive prompt, default Yes. ``builtins.input`` looked up at call
    # time so tests can monkeypatch it (mirrors reconcile._ask_reuse_saved).
    import builtins

    answer = builtins.input(
        f"Reuse saved conceptual audit from {ru.saved.created_at}? [Y/n] "
    ).strip().lower()
    if answer in ("", "y", "yes"):
        return _accept_reuse(
            ru, advisory_out=advisory_out, coverage_out=coverage_out
        )
    return None


def _convergence_loop_advisory_lines(
    path: Path,
    *,
    detail_grade: str,
    audit_stage: str,
) -> list[str]:
    """Loop-pattern advisory lines for completeness stderr."""
    from plan_tool.convergence_diagnosis import (
        _impact_recurrence_lines,
        compose_mechanism_edit_drift_advisory_lines,
        diagnose_convergence,
        load_report_history,
    )

    history = load_report_history(path)
    diagnosis = diagnose_convergence(
        history,
        audit_stage=audit_stage,
        classify_domain=lambda f: f.domain or "unknown",
        mechanism_advisory_grade=detail_grade,
    )
    lines: list[str] = []
    if diagnosis.impact_recurrence is not None:
        lines.extend(
            _impact_recurrence_lines(
                diagnosis.impact_recurrence, window=diagnosis.window
            )
        )
    lines.extend(
        compose_mechanism_edit_drift_advisory_lines(
            diagnosis.bare_mechanism_findings, diagnosis.edit_drift
        )
    )
    return lines


def _emit_convergence_loop_advisories(
    path: Path,
    *,
    detail_grade: str,
    report_path: Path | None,
    skip_sidecar_write: bool,
    audit_coverage,
    audit_stage: str,
) -> None:
    """Print recommend-only loop advisories after a run-grade sidecar write."""
    from plan_tool.review_persistence import (
        audit_coverage_withholds_final_findings_sidecar,
    )

    if detail_grade == GRADE_JIRA:
        return
    if (
        skip_sidecar_write
        or audit_coverage_withholds_final_findings_sidecar(audit_coverage)
        or report_path is None
    ):
        return
    for line in _convergence_loop_advisory_lines(
        path,
        detail_grade=detail_grade,
        audit_stage=audit_stage,
    ):
        print(line, file=sys.stderr)


def finalize_completeness_run(
    plan,
    path: Path,
    ctx,
    args: argparse.Namespace,
    *,
    budget,
    outcome: _IterateOutcome,
    reused_audit_recs,
    code_drifted: bool,
    audit_passes: int,
    audit_dry_rounds: int,
    run_logger=None,
    detail_grade: str = GRADE_RUN,
    reused_audit_advisory=None,
    reused_audit_coverage=None,
    bundle_status,
    audit_stage: str,
    audit_input_snapshot=None,
    sampled_audit_stage: str | None = None,
) -> int:
    """Deterministic checks, conceptual audit reuse, report persist, and
    optional commit — shared tail for audit-only and ``--iterate`` runs.

    When the iterate loop halted (``outcome.early_exit_code``), still writes
    the completeness report (including ``## Halt``) before returning rc=2.

    ``run_logger`` is the caller's open :class:`RunLogWriter`, threaded in so
    this tail's purity calls land in the run log; ``None`` keeps the previous
    unlogged behavior for callers that own no log.

    ``detail_grade`` grounds the conceptual audit and the bundle-status the
    report reads, selects the deterministic battery through the registry's
    grade policy, and decides which report surfaces are suppressed. It also
    forces the MIXED-STEP purity pass off at jira grade: that verdict is
    defined on run-grade implementation detail, so running it would mix a
    run-grade judgment into a jira-grade report."""
    plan = _resolve_plan_for_report(path, outcome, plan)
    audit_input_snapshot = (
        outcome.audit_input_snapshot
        if outcome.audit_input_snapshot is not None
        else audit_input_snapshot
    )
    sampled_audit_stage = outcome.audit_stage or sampled_audit_stage

    # The main audit runs the per-step MIXED-STEP purity pass (claude) only
    # under ``--purity``; the pre-apply checkpoint never does, so the pass
    # fires at most once per audit even under ``--iterate``.
    # The sink is what puts those calls in the run log — extending the log's
    # lifetime alone would keep in-flight.json alive but still record nothing.
    if run_logger is not None:
        run_logger.install_call_end_sink(phase="purity_scan", attempt=1)
    try:
        det = _run_deterministic_checks(
            plan, path, ctx, plan_name=args.name, quiet=budget.enabled,
            # The advisory per-step purity pass is opt-in via --purity
            # (BACKLOG #210: zero reported findings, 87.5% call timeouts). The
            # getattr default matches the flag's, so callers that build args
            # without it also get the pass off. Jira grade forces it off
            # regardless — the purity verdict reads the run-grade body.
            run_purity=(
                getattr(args, "purity", False) and detail_grade != GRADE_JIRA
            ),
            detail_grade=detail_grade,
        )
    finally:
        if run_logger is not None:
            run_logger.uninstall_call_end_sink()

    _noniter_budget: dict = {}
    fresh_audit_advisory = None
    if outcome.audit_recs is not None:
        audit_recs = outcome.audit_recs
        fresh_audit_advisory = outcome.audit_shape_advisory
        selected_audit_coverage = outcome.budget
    elif reused_audit_recs is not None:
        audit_recs = reused_audit_recs
        fresh_audit_advisory = reused_audit_advisory
        selected_audit_coverage = _coverage_input_from_reusable_audit(
            reused_audit_coverage
        )
    else:
        captured_advisory: list = []
        resumed_from_checkpoint: list[bool] = []
        audit_recs = _sample_conceptual_audit(
            plan, path, ctx,
            max_passes=audit_passes,
            dry_rounds=audit_dry_rounds,
            budget_report=_noniter_budget,
            detail_grade=detail_grade,
            bundle_status=bundle_status,
            advisory_out=captured_advisory,
            audit_input_snapshot=audit_input_snapshot,
            require_audit_input_snapshot=True,
            resumed_from_checkpoint_out=resumed_from_checkpoint,
        )
        fresh_audit_advisory = captured_advisory[0] if captured_advisory else None
        selected_audit_coverage = _noniter_budget
        outcome.resumed_from_sampler_checkpoint = bool(
            resumed_from_checkpoint and resumed_from_checkpoint[0]
        )
    # Recomputed fresh against this call's ``audit_stage`` rather than reused
    # from ``outcome`` verbatim: the iterate loop's conceptual audit runs
    # once, early, so ``outcome``'s own bar ids were computed against
    # whatever bundle_status/audit_stage held *before* the loop's
    # deterministic apply rounds ran. If a round's apply changed which
    # steps count as detailed (e.g. authored a missing detail file),
    # ``bundle_status``/``audit_stage`` are refreshed post-loop in
    # ``cmd_completeness``, and reusing the frozen ``outcome`` value here
    # would silently gate this report/JSON on the stale pre-loop stage.
    # ``audit_incomplete`` is stage-independent (pure function of
    # ``selected_audit_coverage``), so it always reproduces ``outcome``'s
    # value when the loop ran; only warn here for the non-iterate path --
    # the iterate loop already warns once internally when it computes this.
    result_audit_stage = sampled_audit_stage or audit_stage
    conceptual_bar_blocking_ids, audit_incomplete = _conceptual_bar_from_audit_recs(
        audit_recs,
        audit_stage=result_audit_stage,
        coverage=selected_audit_coverage,
    )
    if outcome.audit_recs is None:
        _warn_if_audit_incomplete(
            selected_audit_coverage, reuse=reused_audit_recs is not None
        )
    correctness_recs, conceptual_recs = _split_conceptual_recs(audit_recs)
    blocking_deterministic = _blocking_deterministic_findings(
        path_style_hint=det.path_style_hint,
        dep_issues=det.dep_issues,
        body_issues=det.body_issues,
        detail_cov_issues=det.detail_cov_issues,
        detail_body_issues=det.detail_body_issues,
        lessons_issues=det.lessons_issues,
        data_contract_recs=det.data_contract_recs,
        self_consistency_recs=det.self_consistency_recs,
        purity_coverage_recs=det.purity_coverage_recs,
    )
    has_blocking = _completeness_has_blocking_findings(
        audit_recs=audit_recs,
        audit_stage=result_audit_stage,
        conceptual_bar_blocking_ids=conceptual_bar_blocking_ids,
        blocking_deterministic=blocking_deterministic,
    )
    finalize_not_clean = not _completeness_finalize_is_clean(
        audit_incomplete=audit_incomplete,
        has_blocking=has_blocking,
        stop_reason=outcome.stop_reason,
    )
    _qualified_result = classify_qualified_audit_result(
        audit_completed=audit_input_snapshot is not None,
        audit_capture=audit_input_snapshot,
        audit_stage=sampled_audit_stage,
        coverage=selected_audit_coverage,
        coverage_is_legacy_unknown=(
            reused_audit_recs is not None
            and (
                not isinstance(reused_audit_coverage, dict)
                or reused_audit_coverage.get("evidence_status") != "observed"
            )
        ),
        revision_current=(
            audit_input_snapshot.matches_disk(path, ctx.repo_root)
            if audit_input_snapshot is not None
            else None
        ),
        has_blocking=has_blocking,
        stop_reason=outcome.stop_reason,
        deferred_recs=outcome.deferred_recs.values(),
        conceptual_bar_blocking_ids=conceptual_bar_blocking_ids,
        result_bearing_findings=_has_result_bearing_findings(det, audit_recs),
        finalize_clean=not finalize_not_clean,
    )
    outcome.qualified_result = _qualified_result
    # Trust follows the gate: an unqualified result, or an empty set with an
    # unclean stop, reads as incomplete (it keeps the ids it computed). The
    # gate's ids are () on an incomplete audit; the verdict names the stage
    # bar's ids over the saved findings so the gaps to close stay visible.
    verdict_blocking_ids = (
        compute_conceptual_bar_blocking_ids(
            audit_recs, audit_stage=result_audit_stage
        )
        if audit_incomplete and audit_recs
        else conceptual_bar_blocking_ids
    )
    blocking_verdict = blocking_verdict_from_gate(
        verdict_blocking_ids,
        blocking_deterministic,
        untrusted_cause=_verdict_untrusted_cause(
            audit_incomplete=audit_incomplete,
            stop_reason=outcome.stop_reason,
            qualified_headline=_qualified_result.headline,
            revision_status=_qualified_result.revision_status,
            coverage_status=_qualified_result.coverage,
            blocking_set_nonempty=bool(
                conceptual_bar_blocking_ids or blocking_deterministic
            ),
            halt_reason=outcome.halt_reason,
        ),
    )
    bundle_sink = getattr(args, "_bundle_status_sink", None)
    if isinstance(bundle_sink, list):
        bundle_sink.append(bundle_status)
    verdict_sink = getattr(args, "_blocking_verdict_sink", None)
    if isinstance(verdict_sink, list):
        verdict_sink.append(blocking_verdict)

    # Provenance for both output paths, computed once here because the
    # ``--json`` branch below returns before the report is written.
    detail_bundle_fingerprint = None
    if detail_grade == GRADE_JIRA:
        from plan_tool.fingerprint import audit_input_detail_fingerprint

        detail_bundle_fingerprint = (
            audit_input_detail_fingerprint(audit_input_snapshot, ctx.repo_root)
            if audit_input_snapshot is not None
            else None
        )
        # Bound to the audit completing, so it fires exactly once on either
        # path — the ``--json`` branch returns a few lines below.
        _warn_sidecar_suppressed()

    # Preserve the stored payload verbatim, even if it has gone stale since
    # capture. The checkpoint lane is the sole pre-persistence drift guard;
    # every renderer below makes its own exact source-snapshot freshness check
    # and suppresses a stale advisory without rewriting the saved review.
    from plan_tool.completeness_report import prepare_audit_shape_advisory_display

    audit_shape_advisory_display = prepare_audit_shape_advisory_display(
        None if detail_grade == GRADE_JIRA else fresh_audit_advisory,
        plan=plan,
        plan_path=path,
        repo_root=ctx.repo_root,
        detail_grade=detail_grade,
    )

    if args.json:
        # Plan-mass snapshot (#238), computed only on this path — the
        # markdown path's own copy lives in ``completeness_phases.py`` (that
        # function returns before this one reaches it, so there is no shared
        # point to hoist a single computation to without new plumbing). Same
        # jira-grade fence: detail-bundle bytes are a run-grade-path
        # measurement. ``compute_plan_mass_best_effort`` is the one shared
        # failure policy for every #238 CLI call site.
        plan_mass_json = None
        if detail_grade != GRADE_JIRA:
            from plan_tool.completeness_report import (
                compute_plan_mass_best_effort,
                plan_mass_to_json,
            )

            mass = compute_plan_mass_best_effort(plan, path, ctx.repo_root)
            if mass is not None:
                plan_mass_json = plan_mass_to_json(mass)

        rc = _render_completeness_json(
            args,
            det,
            audit_recs,
            has_blocking=has_blocking,
            budget=selected_audit_coverage,
            halt_reason=outcome.halt_reason,
            early_exit_code=outcome.early_exit_code,
            detail_grade=detail_grade,
            detail_bundle_fingerprint=detail_bundle_fingerprint,
            audit_shape_advisory_display=audit_shape_advisory_display,
            plan_mass=plan_mass_json,
            audit_stage=audit_stage,
            audit_incomplete=audit_incomplete,
            conceptual_bar_blocking_ids=conceptual_bar_blocking_ids,
            stop_reason=outcome.stop_reason,
            finalize_not_clean=finalize_not_clean,
            qualified_result=_qualified_result,
        )
        if outcome.early_exit_code is not None:
            return outcome.early_exit_code
        return rc

    grouped_md = _render_grouped_report(
        plan, args, det,
        correctness_recs=correctness_recs,
        conceptual_recs=conceptual_recs,
        audit_recs=audit_recs,
        iterate_enabled=budget.enabled,
        bundle_status=bundle_status,
        budget=selected_audit_coverage,
        detail_grade=detail_grade,
        detail_bundle_fingerprint=detail_bundle_fingerprint,
        audit_shape_advisory_display=audit_shape_advisory_display,
        resumed_from_sampler_checkpoint=outcome.resumed_from_sampler_checkpoint,
        qualified_result=_qualified_result,
        verdict=blocking_verdict,
    )
    skip_sidecar_write = reused_audit_recs is not None and not budget.enabled
    report_path = _persist_and_present_report(
        plan, path, args, ctx,
        iterate_enabled=budget.enabled,
        outcome=outcome,
        correctness_recs=correctness_recs,
        conceptual_recs=conceptual_recs,
        grouped_md=grouped_md,
        smell_recs=det.smell_recs,
        data_contract_recs=det.data_contract_recs,
        data_contract_payloads=det.data_contract_payloads,
        code_drifted=code_drifted,
        skip_sidecar_write=skip_sidecar_write,
        halt_reason=outcome.halt_reason,
        bundle_status=bundle_status,
        detail_grade=detail_grade,
        audit_shape_advisory=(
            None if detail_grade == GRADE_JIRA else fresh_audit_advisory
        ),
        audit_shape_advisory_display=audit_shape_advisory_display,
        audit_coverage=_coverage_for_sidecar(selected_audit_coverage),
        audit_input_snapshot=audit_input_snapshot,
        audit_stage=sampled_audit_stage,
        verdict=blocking_verdict,
    )
    _emit_convergence_loop_advisories(
        path,
        detail_grade=detail_grade,
        report_path=report_path,
        skip_sidecar_write=skip_sidecar_write,
        audit_coverage=selected_audit_coverage,
        audit_stage=audit_stage,
    )

    if getattr(args, "commit", False) and not args.json and budget.enabled:
        from plan_tool.detail import _plan_slug as _detail_plan_slug
        commit_rc, tail = commit_all(
            ctx.repo_root, _completeness_commit_subject(_detail_plan_slug(path))
        )
        if commit_rc == 0:
            success("committed completeness edits")
        else:
            error(
                f"git commit failed (rc={commit_rc})"
                + (f": {tail}" if tail else "")
            )
            return 1

    if outcome.early_exit_code is not None:
        return outcome.early_exit_code

    if getattr(args, "fail_on_findings", False) and not _completeness_finalize_is_clean(
        audit_incomplete=audit_incomplete,
        has_blocking=has_blocking,
        stop_reason=outcome.stop_reason,
    ):
        return 1
    return 0


def cmd_completeness(args: argparse.Namespace) -> int:
    """Conceptual audit of the plan: is it correct, complete, and unambiguous?

    Two layers. First, deterministic primitives confirm the plan
    document is well-formed — missing/placeholder body sections, steps
    without detail files, detail-vs-files drift, lessons coverage — with
    no claude call. Then the conceptual audit
    (:func:`audit_plan_until_stable` running :func:`check_plan_audit`
    until findings run dry, --audit-passes / --audit-dry-rounds) reads
    the plan grounded in the per-step detail bundle where present (a bare
    step — no detail file yet — is judged at the plan/concept level), may
    Read/Grep the repo at HEAD, and judges the plan's own concepts on two
    persisted axes: correctness (sound, internally consistent ideas, including
    material ambiguity that would permit conflicting implementations) and
    completeness (no orphaned concepts, uncovered risks, or dangling
    acceptance criteria the bundle doesn't already resolve). This is the
    *Conceptual* axis — distinct from ``detail`` (Coverage: plan ⊇ code)
    and ``run``/``verify`` (Fulfillment: code ⊇ plan).

    Three audit verbs answer three different questions; see
    :func:`cmd_review` for the comparison table. New deterministic
    coverage checks belong here; correctness-vs-completeness
    primitives both flow through this report (correctness first by
    convention so structural blockers surface ahead of authoring
    gaps).

    Orchestration only: parse / banner / budget resolution, then delegate
    to the phase helpers — the ``--iterate`` convergence loop, the
    deterministic battery, the conceptual audit, and the
    json/grouped/persist rendering — and return the resulting rc.

    See ``docs/reference/contracts/process.md`` for this audit's plan-subject boundary.
    """
    ctx = _load_context(args)
    path = resolve_plan_for_context(ctx, args.name)

    try:
        plan = parse_plan(path)
    except UnsupportedPlanFormatVersionError:
        raise
    except (ParseError, ValidationError) as exc:
        error(f"failed to parse plan: {exc}")
        return 2

    # Grade selection and its guards come first: everything they reject is
    # built on run-grade grounding, so rejecting here spends no claude call,
    # runs no reuse lookup, and opens no run log.
    detail_grade = _completeness_detail_grade(args)
    grade_conflict_rc = _reject_grade_conflicts(args, detail_grade)
    if grade_conflict_rc is not None:
        return grade_conflict_rc

    # Capture the exact plan/detail inputs before a reuse lookup or conceptual
    # audit can inspect them. A failed capture is explicit no-evidence state;
    # do not infer a later stage from disk as though it had been sampled.
    from plan_tool.review_persistence import AuditInputSnapshot

    audit_capture_failed = False
    try:
        audit_input_snapshot = AuditInputSnapshot.capture(
            path, ctx.repo_root, detail_grade=detail_grade
        )
    except AuditInputError as exc:
        error(str(exc))
        return 2
    except Exception:  # noqa: BLE001 — finalization reports no sampled evidence
        audit_input_snapshot = None
        audit_capture_failed = True
    else:
        # Every post-capture decision must use the exact plan the conceptual
        # prompt and saved revision represent.  A concurrent edit between the
        # initial parse and capture is therefore one coherent newer sample,
        # never an old parsed plan paired with newer captured detail bytes.
        plan = audit_input_snapshot.plan

    # Echo the request before any long-running work starts. The
    # conceptual audit below shells out to claude for minutes per
    # pass; without this banner the command sits silent until the
    # first pass's findings return. stderr keeps --json stdout
    # parseable (same channel the audit's own progress lines use).
    _audit_passes = _effective_audit_passes(args)
    _audit_dry = getattr(args, "audit_dry_rounds", AUDIT_DEFAULT_DRY_ROUNDS)
    _plan_display = literal_path(path, ctx.repo_root)
    print(
        f"plan-tool: completeness-audit '{args.name}' — {plan.title}\n"
        f"plan-tool: {len(plan.steps)} step(s) · {_plan_display}",
        file=sys.stderr,
    )
    if detail_grade == GRADE_JIRA:
        # Name the grounding whenever it is not the default: which bytes the
        # judge read decides how every finding should be read.
        print(
            _jira_grounding_line(plan, path, ctx.repo_root), file=sys.stderr
        )

    _print_stale_detail_preflight(plan, path)

    # Saved-audit reuse decision — computed once (so the prompt fires at
    # most once regardless of the iterate/audit-only branch). Non-``None``
    # is the saved correctness+conceptual rec union to substitute for a
    # fresh conceptual audit; ``None`` means "audit fresh". The
    # deterministic battery below is never gated by this — only the
    # conceptual axis is reused.
    # Capture whether the saved audit was stale because code moved under the
    # plan (the ``_note_code_drift`` condition) so the end-of-run report can
    # recommend ``reconcile-plan`` when a critical/high finding is also present
    # (BACKLOG #65). A single-element list out-param keeps the reuse return
    # contract (and its tests) unchanged.
    # Skipped entirely under jira grade: every saved sidecar is run-grade-
    # grounded, and its freshness verdict reads only the plan and code
    # fingerprints — both grade-independent — so an unprompted reuse would
    # silently substitute the other grade's judgments. An *explicit* reuse
    # request is rejected up front instead of skipped.
    if detail_grade == GRADE_JIRA or audit_input_snapshot is None:
        reused_audit_recs = None
        reused_audit_advisory = None
        reused_audit_coverage = None
        code_drifted = False
    else:
        _drift_out = [False]
        _reused_advisory_out = [None]
        _reused_coverage_out = [None]
        reused_audit_recs = _resolve_audit_reuse(
            plan,
            path,
            ctx,
            args,
            drift_out=_drift_out,
            advisory_out=_reused_advisory_out,
            coverage_out=_reused_coverage_out,
            audit_input_snapshot=audit_input_snapshot,
        )
        reused_audit_advisory = _reused_advisory_out[0]
        reused_audit_coverage = _reused_coverage_out[0]
        code_drifted = _drift_out[0]

    from plan_tool.review import audit_detail_bundle_status

    bundle_status = audit_detail_bundle_status(
        plan, path, ctx.repo_root, detail_grade=detail_grade
    )
    audit_stage = derive_audit_stage(bundle_status)
    sampled_audit_stage = None
    if audit_input_snapshot is not None:
        sampled_bundle_status = _sampled_bundle_status(audit_input_snapshot)
        sampled_audit_stage = derive_audit_stage(sampled_bundle_status)

    # --iterate: drive a convergence loop that applies each open
    # deterministic finding via claude (same primitive cmd_create's
    # post-write loop uses) and re-audits until findings stabilize or
    # the budget is exhausted. Re-parses the plan after each round so
    # the final report below reflects the post-iteration state.
    try:
        budget = _resolve_iterative_budget(args)
    except CreateError as exc:
        error(str(exc))
        return 2

    # ``--commit`` (human runs only) gates up front: it commits the edits the
    # --iterate loop applies, so it's meaningless without --iterate, and the
    # end-of-run ``git add -A`` must not fold in pre-existing changes.
    if getattr(args, "commit", False) and not args.json:
        if not budget.enabled:
            error(
                "--commit requires --iterate (an audit-only run applies no "
                "plan edits to commit)."
            )
            return 2
        if working_tree_dirty(ctx.repo_root):
            error(
                "--commit requires a clean working tree (commit or stash "
                "your changes first)."
            )
            return 2

    # When enabled, the loop audits the plan's concepts exactly once (up
    # front) and hands the result back so the report below reuses it
    # instead of spending a second claude call; it also returns the final
    # re-parsed plan so the report reflects post-iteration state. An
    # early_exit_code carries a loop-internal halt (drift/parse/lock) out
    # as this command's own rc. In audit-only mode an empty outcome stands
    # in (audit_recs is None -> audit fresh below).
    # Open a run log for the iterate loop UNLESS this is a nested tail
    # call (detail/split own the parent log — see _run_completeness_tail).
    _iter_run_logger = None
    if budget.enabled and not getattr(args, "_suppress_run_log", False):
        from plan_tool.detail import _plan_slug as _detail_plan_slug
        from plan_tool.run_log import RunLogWriter

        _iter_run_logger = RunLogWriter.start(
            repo_root=ctx.repo_root,
            slug=_detail_plan_slug(path),
            command="completeness",
            argv=list(sys.argv[1:]),
            plan_path=path,
            flags={
                "iterate": True,
                "include_info": bool(getattr(args, "include_info", False)),
            },
        )
    # One ``finally`` over the loop *and* the finalize tail: finalize runs the
    # per-step purity pass (claude), so closing the log after the loop alone
    # reported ``run_end``/torn-down in-flight.json on a run still spending
    # tokens for the whole tail. rc is the command's real rc (finalize's),
    # not the loop's — a halt surfaces as rc=2 from finalize either way.
    _run_rc = 1
    try:
        if budget.enabled:
            outcome = completeness_phases._run_iterate_convergence_loop(
                plan, path, ctx, args, budget,
                bundle_status=bundle_status,
                audit_stage=audit_stage,
                audit_input_snapshot=audit_input_snapshot,
                audit_capture_failed=audit_capture_failed,
                sampled_audit_stage=sampled_audit_stage,
                detail_grade=detail_grade,
                reused_audit_recs=reused_audit_recs,
                reused_audit_advisory=reused_audit_advisory,
                reused_audit_coverage=reused_audit_coverage,
                run_logger=_iter_run_logger,
                code_drifted=code_drifted,
            )
            if outcome.plan is not None:
                plan = outcome.plan
                # Re-derive rather than reuse the pre-loop snapshot: a
                # deterministic apply round (or interleaved detail
                # authoring) can change which steps count as detailed, and
                # the report/JSON below must reflect the plan's state now,
                # not its state when the loop started. Cheap and no Claude
                # call either way (audit_detail_bundle_status is a pure
                # filesystem presence check).
                bundle_status = audit_detail_bundle_status(
                    plan, path, ctx.repo_root, detail_grade=detail_grade
                )
                audit_stage = derive_audit_stage(bundle_status)
        else:
            outcome = _IterateOutcome(
                audit_input_snapshot=audit_input_snapshot,
                audit_stage=sampled_audit_stage,
                audit_capture_failed=audit_input_snapshot is None,
            )

        _run_rc = finalize_completeness_run(
            plan, path, ctx, args,
            budget=budget,
            outcome=outcome,
            reused_audit_recs=reused_audit_recs,
            reused_audit_advisory=reused_audit_advisory,
            reused_audit_coverage=reused_audit_coverage,
            code_drifted=code_drifted,
            audit_passes=_audit_passes,
            audit_dry_rounds=_audit_dry,
            run_logger=_iter_run_logger,
            detail_grade=detail_grade,
            bundle_status=bundle_status,
            audit_stage=audit_stage,
            audit_input_snapshot=audit_input_snapshot,
            sampled_audit_stage=sampled_audit_stage,
        )
        return _run_rc
    finally:
        if _iter_run_logger is not None:
            _iter_run_logger.run_end(
                outcome=("success" if _run_rc == 0 else "error"),
                rc=_run_rc,
            )


_CLEAN_ELIGIBLE_STOP_REASONS = _REMAP_STOP_FOR_CONCEPTUAL_BAR
"""Same stop-reason set the mid-run remap treats as candidates for
``terminal_hand_apply``: finalize's clean check and the mid-run remap must
agree on which stop reasons are eligible, or the two halves of one run can
disagree about whether it converged. Aliased, not independently redefined,
so a future added stop-reason can't update one without the other."""


def _verdict_untrusted_cause(
    *,
    audit_incomplete: bool,
    stop_reason: str | None,
    qualified_headline: str,
    revision_status: str,
    coverage_status: str = "",
    blocking_set_nonempty: bool = False,
    halt_reason: str | None = None,
) -> str:
    """Why the blocking verdict is not a trusted ``set`` (``""`` when it is).

    First match wins; the order and the reasons are in
    docs/how-to/pipeline/audit.md § "One blocking set drives every next step".
    """
    no_evidence = qualified_headline == QUALIFIED_RESULT_NO_EVIDENCE
    if no_evidence and (
        revision_status in STALE_REVISION_STATUSES
        or coverage_status == _LEGACY_UNKNOWN_COVERAGE
    ):
        return UNTRUSTED_STALE_REVISION
    if audit_incomplete or no_evidence:
        return UNTRUSTED_PERSISTENT
    if blocking_set_nonempty:
        return ""
    if halt_reason is not None:
        return (
            UNTRUSTED_TRANSIENT if halt_reason in HALT_DRIFT_REASONS
            else UNTRUSTED_PERSISTENT
        )
    if (
        stop_reason not in _HAND_APPLY_STOP_REASONS
        and not _stop_reason_is_clean_eligible(stop_reason)
    ):
        return UNTRUSTED_TRANSIENT
    if (
        stop_reason in _HAND_APPLY_STOP_REASONS
        or qualified_headline == QUALIFIED_RESULT_AWAITING_ACTION
    ):
        return UNTRUSTED_PERSISTENT
    return ""


# Legacy coverage was never observed, so a fresh audit observes it anew.
_LEGACY_UNKNOWN_COVERAGE = "unknown-legacy"


# Stops that wait on a person rather than a retry: re-auditing reproduces them.
_HAND_APPLY_STOP_REASONS = frozenset({"terminal_hand_apply", "manual_fix_blocking_findings"})


def _stop_reason_is_clean_eligible(stop_reason: str | None) -> bool:
    """True when an iterate ``stop_reason`` does not deny finalize clean."""
    if stop_reason is None:
        return True
    if stop_reason in _CLEAN_ELIGIBLE_STOP_REASONS:
        return True
    return False


def _completeness_finalize_is_clean(
    *,
    audit_incomplete: bool,
    has_blocking: bool,
    stop_reason: str | None,
) -> bool:
    """True when finalize may treat the run as clean (``--fail-on-findings`` off).

    Takes ``audit_incomplete`` rather than re-deriving it from a coverage
    object: at every call site, ``audit_incomplete`` was itself computed as
    ``not audit_coverage_qualifies_sample(coverage)`` (now also ``or
    budget_limited``, see ``_conceptual_bar_from_audit_recs``) on the exact
    same coverage this function would otherwise re-check, so a second,
    independent qualifies-sample check here could never disagree.
    """
    if audit_incomplete or has_blocking:
        return False
    return _stop_reason_is_clean_eligible(stop_reason)


QUALIFIED_RESULT_NO_EVIDENCE = "no-qualified-current-evidence"
QUALIFIED_RESULT_AWAITING_ACTION = "awaiting-human-action"
QUALIFIED_RESULT_ADVISORY = "advisory-only"
QUALIFIED_RESULT_CLEAN = "clean"


@dataclass(frozen=True)
class QualifiedAuditResult:
    """One ordered final decision plus the facts a later renderer exposes."""

    headline: str
    stage: str
    coverage: str
    revision_status: str
    audit_revision: dict[str, object] | None

    def as_dict(self) -> dict[str, object]:
        """Return the stable JSON/persistence representation."""
        return {
            "headline": self.headline,
            "stage": self.stage,
            "coverage": self.coverage,
            "revision_status": self.revision_status,
            "audit_revision": self.audit_revision,
        }


def _has_result_bearing_findings(det, audit_recs) -> bool:
    """Return whether a surfaced finding, rather than report metadata, remains."""
    return any(
        (
            det.path_style_hint is not None,
            bool(det.dep_issues),
            bool(det.body_issues),
            bool(det.detail_cov_issues),
            bool(det.detail_body_issues),
            bool(det.files_coh_issues),
            bool(det.lessons_issues),
            bool(det.smell_recs),
            bool(det.self_consistency_recs),
            bool(det.data_contract_recs),
            bool(det.purity_coverage_recs),
            bool(audit_recs),
        )
    )


def _deferred_remainder_is_explicitly_advisory(
    deferred_recs, *, audit_stage: str, conceptual_bar_blocking_ids: tuple[str, ...]
) -> bool:
    """Recognize only explicitly advisory deferred work as an advisory stop."""
    from plan_tool.review import is_apply_eligible

    deferred = list(deferred_recs)
    if not deferred:
        return False
    for rec in deferred:
        # A structural/manual fix remains a human-action stop even if its
        # producer labels the observation informational.
        if not is_apply_eligible(rec):
            return False
        if rec.severity.lower() in {"info", "nit"}:
            continue
        # Material apply/triage deferrals require a person.
        return False
    return True


def classify_qualified_audit_result(
    *,
    audit_completed: bool,
    audit_capture,
    audit_stage: str | None,
    coverage,
    coverage_is_legacy_unknown: bool,
    revision_current: bool | None,
    has_blocking: bool,
    stop_reason: str | None,
    deferred_recs=(),
    conceptual_bar_blocking_ids: tuple[str, ...] = (),
    result_bearing_findings: bool = False,
    finalize_clean: bool = True,
) -> QualifiedAuditResult:
    """Classify final audit evidence from explicit facts in precedence order."""
    if audit_capture is None or not audit_completed:
        return QualifiedAuditResult(
            QUALIFIED_RESULT_NO_EVIDENCE,
            "not-sampled",
            "not-sampled",
            "not-sampled",
            None,
        )

    from plan_tool.review_persistence import audit_coverage_qualifies_sample

    coverage_confirmed = audit_coverage_qualifies_sample(coverage) and not bool(
        isinstance(coverage, dict) and coverage.get("budget_limited")
    )
    coverage_status = (
        "unknown-legacy"
        if coverage_is_legacy_unknown
        else ("confirmed" if coverage_confirmed else "unconfirmed")
    )
    revision_status = (
        "current" if revision_current is True
        else ("unknown-legacy" if revision_current is None else "stale")
    )
    if (
        coverage_is_legacy_unknown
        or not coverage_confirmed
        or revision_current is not True
    ):
        return QualifiedAuditResult(
            QUALIFIED_RESULT_NO_EVIDENCE,
            audit_stage or "not-sampled",
            coverage_status,
            revision_status,
            audit_capture.revision,
        )

    deferred = list(deferred_recs)
    stop_all_advisory = (
        stop_reason == "all_auto_apply_findings_deferred"
        and _deferred_remainder_is_explicitly_advisory(
            deferred,
            audit_stage=audit_stage or "detail",
            conceptual_bar_blocking_ids=conceptual_bar_blocking_ids,
        )
    )
    stop_requires_action = (
        stop_reason is not None
        and stop_reason not in {"converged", "no_blocking_findings"}
        and not stop_all_advisory
    )
    if has_blocking or stop_requires_action or not finalize_clean:
        return QualifiedAuditResult(
            QUALIFIED_RESULT_AWAITING_ACTION,
            audit_stage or "not-sampled",
            coverage_status,
            revision_status,
            audit_capture.revision,
        )
    if result_bearing_findings:
        return QualifiedAuditResult(
            QUALIFIED_RESULT_ADVISORY,
            audit_stage or "not-sampled",
            coverage_status,
            revision_status,
            audit_capture.revision,
        )
    return QualifiedAuditResult(
        QUALIFIED_RESULT_CLEAN,
        audit_stage or "not-sampled",
        coverage_status,
        revision_status,
        audit_capture.revision,
    )


def _blocking_deterministic_findings(
    *,
    path_style_hint,
    dep_issues,
    body_issues,
    detail_cov_issues,
    detail_body_issues,
    lessons_issues,
    data_contract_recs=(),
    self_consistency_recs=(),
    purity_coverage_recs=(),
) -> tuple:
    """The deterministic arms that block the gate, collected once.

    Medium+ recommendation arms contribute their own blocking findings; each
    issue-object arm contributes one synthetic ``<arm>`` finding. The gate's
    bool and the next-step verdict both read this one collection, so they
    cannot disagree."""
    blocking: list = []

    def _arm(arm: str, count: int) -> None:
        text = f"{count} blocking {arm} finding(s) in the deterministic checks"
        blocking.append(
            DeterministicArmFinding(
                id=f"deterministic-{arm}",
                source=arm,
                severity="medium",
                step_id=None,
                title=text,
                body=text,
            )
        )

    if path_style_hint is not None:
        _arm("path-style-mismatch", 1)
    if dep_issues:
        _arm("deps", len(dep_issues))
    if body_issues:
        _arm("body-completeness", len(body_issues))
    missing = [i for i in detail_cov_issues if i.kind == "missing_on_disk"]
    if missing:
        _arm("detail-coverage", len(missing))
    if detail_body_issues:
        _arm("detail-body", len(detail_body_issues))
    if lessons_issues:
        _arm("lessons-coverage", len(lessons_issues))
    for recs in (data_contract_recs, self_consistency_recs, purity_coverage_recs):
        blocking.extend(r for r in recs if is_blocking(r.severity))
    return tuple(blocking)


_UNSET_ARM = object()


def _completeness_has_blocking_findings(
    *,
    path_style_hint=_UNSET_ARM,
    dep_issues=_UNSET_ARM,
    body_issues=_UNSET_ARM,
    detail_cov_issues=_UNSET_ARM,
    detail_body_issues=_UNSET_ARM,
    lessons_issues=_UNSET_ARM,
    data_contract_recs=_UNSET_ARM,
    self_consistency_recs=_UNSET_ARM,
    purity_coverage_recs=_UNSET_ARM,
    audit_recs=(),
    audit_stage: str,
    conceptual_bar_blocking_ids: Optional[tuple[str, ...]] = None,
    blocking_deterministic=None,
) -> bool:
    """True when any finding blocks finalize / ``--json`` / ``--fail-on-findings``.

    Pass ``blocking_deterministic`` (the collected arms), or every raw arm; an
    omitted arm is a ``TypeError``, never a silent "nothing blocks".

    Deterministic arms use the legacy medium+ threshold. Conceptual
    ``audit_recs`` use the stage bar via ``is_blocking_finding`` (medium
    demotes only when ``classify_finding_domain`` returns ``"docs"``;
    bare-stage ``plan-completeness`` medium is a separate unconditional
    non-block). Surfaced in ``--json`` as ``has_blocking_findings``.
    Data-contract drift blocks at medium+; self-consistency and
    purity-coverage errors likewise; smells never gate.
    Files-coherence diagnostics render as INFO/NIT and deliberately remain
    outside this blocking gate.

    ``conceptual_bar_blocking_ids``, when given, is used as-is for the
    conceptual arm instead of recomputing it from ``audit_recs`` --
    ``finalize_completeness_run`` already has it from
    ``_conceptual_bar_from_audit_recs`` and passes it through so the
    stage-bar/domain-classify pass doesn't run over the same ``audit_recs``
    a second time. Defaults to ``None`` so every other caller (including
    this function's own direct unit tests) keeps exercising the recompute.
    """
    if blocking_deterministic is None:
        if _UNSET_ARM in (
            path_style_hint, dep_issues, body_issues,
            detail_cov_issues, detail_body_issues, lessons_issues,
            data_contract_recs, self_consistency_recs, purity_coverage_recs,
        ):
            raise TypeError(
                "_completeness_has_blocking_findings needs blocking_deterministic "
                "or every deterministic arm"
            )
        blocking_deterministic = _blocking_deterministic_findings(
            path_style_hint=path_style_hint,
            dep_issues=dep_issues,
            body_issues=body_issues,
            detail_cov_issues=detail_cov_issues,
            detail_body_issues=detail_body_issues,
            lessons_issues=lessons_issues,
            data_contract_recs=data_contract_recs,
            self_consistency_recs=self_consistency_recs,
            purity_coverage_recs=purity_coverage_recs,
        )
    if blocking_deterministic:
        return True
    if conceptual_bar_blocking_ids is not None:
        if conceptual_bar_blocking_ids:
            return True
    elif audit_recs and compute_conceptual_bar_blocking_ids(
        audit_recs, audit_stage=audit_stage
    ):
        return True
    return False


def register(subparsers) -> dict[str, Handler]:
    """Add the completeness subparsers and return their dispatch map.

    ``completeness-audit`` (aliased ``completeness``) and
    ``completeness-apply`` declare ``parents=[yes_parent, ...]``; those
    parents currently originate in ``app.register``. Per the
    duplicate-then-defer rule, this command module — carved out before
    ``parser.py`` owns the shared parents — rebuilds its own verbatim
    copies (argparse ``parents=`` copies actions by reference, so identical
    parent objects yield byte-identical ``--help``). Consolidation into
    ``parser.py`` is deferred.

    ``completeness-audit`` dispatches to ``cmd_completeness``;
    ``completeness-apply`` is the paired walker.
    """
    sub = subparsers

    yes_parent = make_yes_parent()

    # Opt-in CI gate inherited by the audit subcommands (validate /
    # verify-all / completeness). By default these exit 0 once
    # they complete -- the report carries the findings. Passing this flag
    # restores each command's own blocking threshold as a non-zero exit
    # (completeness: medium+ findings; verify-all: a [FAIL] /
    # critical finding; validate: an INVALID verdict) so a CI step can
    # gate on the rc. A run that couldn't complete still exits non-zero
    # regardless of this flag.
    fail_on_findings_parent = argparse.ArgumentParser(add_help=False)
    fail_on_findings_parent.add_argument(
        "--fail-on-findings",
        action="store_true",
        dest="fail_on_findings",
        help=(
            "exit non-zero when the audit's blocking findings are present "
            "(completeness: stage-bar-aware blocking, incomplete audit "
            "samples, or ineligible iterate stop; verify-all: a [FAIL] / "
            "critical finding; validate: INVALID). Off by default; intended "
            "for CI gates that stop the pipeline on findings."
        ),
    )

    # Shared iteration-loop flags inherited by the
    # create/completeness/detail/run subparsers. The loops themselves
    # live in steps 2–4 of the iterative-correctness plan; this parent
    # is just the CLI surface.
    #
    # NOTE: ``--iterate`` / ``--no-iterate`` is *intentionally* NOT
    # added here. Argparse's ``parents=`` mechanism copies actions by
    # reference, and ``set_defaults`` mutates the shared action's
    # ``default`` attribute -- so a single ``parent`` entry can't
    # express "default ON for create, default OFF for the others."
    # Each subparser adds its own ``--iterate`` action below with the
    # subcommand-appropriate default. The remaining iteration flags
    # (--max-iterations, --iteration-budget, etc.) share
    # the same defaults across subcommands and stay here.
    iterate_parent = argparse.ArgumentParser(add_help=False)
    iterate_parent.add_argument(
        "--max-iterations",
        type=int,
        default=DEFAULT_MAX_ITERATIONS,
        dest="max_iterations",
        metavar="N",
        help=(
            f"cap the convergence loop at N iterations even if findings "
            f"keep changing (default: {DEFAULT_MAX_ITERATIONS}). Ignored "
            f"when --no-iterate is set."
        ),
    )
    iterate_parent.add_argument(
        "--iteration-budget",
        type=int,
        default=DEFAULT_ITERATION_BUDGET_SECONDS,
        dest="iteration_budget",
        metavar="SECONDS",
        help=(
            f"debounced no-progress deadline in seconds: stop the "
            f"convergence loop only once SECONDS pass with no forward "
            f"progress at all (default: {DEFAULT_ITERATION_BUDGET_SECONDS}). "
            f"Resets on every round and every apply_finding call, so one "
            f"long claude call — even 15-20+ minutes — never trips it on "
            f"its own; see --time-budget for a true total-elapsed cap. "
            f"Ignored when --no-iterate is set."
        ),
    )
    iterate_parent.add_argument(
        "--time-budget",
        type=int,
        default=None,
        dest="time_budget",
        metavar="SECONDS",
        help=(
            "cooperative wall-clock cap (#123): stop the convergence loop "
            "cleanly at the next round boundary once SECONDS of total elapsed "
            "time pass — even while still converging — so a long op lands "
            "before an external execution ceiling instead of being killed "
            "mid-call. Exits 0 with a resume hint. Unlike --iteration-budget "
            "(a no-progress stall deadline), this is a hard total-elapsed cap. "
            "Falls back to PLAN_TOOL_TIME_BUDGET; default off. Ignored under "
            "--no-iterate."
        ),
    )
    iterate_parent.add_argument(
        "--max-stall-rounds",
        type=int,
        default=DEFAULT_MAX_STALL_ROUNDS,
        dest="max_stall_rounds",
        metavar="N",
        help=(
            f"stop the convergence loop after N consecutive rounds whose "
            f"open-finding count fails to shrink (default: "
            f"{DEFAULT_MAX_STALL_ROUNDS}). This is the ID-agnostic "
            f"backstop for a subjective claude audit that re-phrases the "
            f"same findings each round (fresh ids defeat the marginal / "
            f"converged checks). Pass 0 to disable. Ignored when "
            f"--no-iterate is set."
        ),
    )
    iterate_parent.add_argument(
        "--allow-drift",
        action="store_true",
        dest="allow_drift",
        help=(
            "opt back into the legacy 'warn but proceed' behavior when a "
            "watched file's content changes mid-iteration. Default: the "
            "loop checks drift BEFORE each apply (halts without spending "
            "claude tokens if drift detected) AND AFTER (keeps the "
            "apply's edits but halts subsequent applies if drift "
            "happened during the apply call). Token-preserving by "
            "design -- no revert, just halt + flag for `git diff` "
            "review (task #30). Pass --allow-drift only when you're "
            "sure the drift is expected (e.g. an automated formatter "
            "touching files in step.files during iteration)."
        ),
    )
    iterate_parent.add_argument(
        "--no-auto-reconcile-on-drift",
        action="store_false",
        dest="auto_reconcile_on_drift",
        default=True,
        help=(
            "skip the auto-reconcile pass that fires when drift halts "
            "the iteration loop. Default: when drift is detected, "
            "plan-tool runs `reconcile` against the step(s) that own "
            "the drifted file(s), saves the findings, and prints a "
            "structured summary inline with the halt (Lesson 13: "
            "audit beats observe). Pass this flag to suppress that "
            "extra claude call -- useful in CI runs that prefer a "
            "minimal stderr footprint, or when you'll inspect drift "
            "manually via `git diff` and `plan-tool run --mode "
            "reconcile`."
        ),
    )
    iterate_parent.add_argument(
        "--no-triage",
        action="store_false",
        dest="triage",
        default=True,
        help=(
            "skip the impact-weighted triage gate on findings. "
            "Default: when a finding carries impact/complexity tags "
            "(the plan-audit prompt's trailing "
            "``(impact=…, complexity=…)`` on conceptual findings; the "
            "reconcile prompt's ``Impact:`` / ``Complexity:`` fields), "
            "the iteration loop skips applies whose complexity "
            "strictly exceeds their impact (low+medium, low+high, "
            "medium+high) -- those findings are reported on stderr "
            "and dropped from the open-set so convergence "
            "short-circuits when only triaged findings remain. "
            "Findings without triage tags (deterministic checks, "
            "untagged output) default to apply. Pass this flag to "
            "force-apply every finding regardless of triage tags -- "
            "useful for completeness sweeps where you want to land "
            "every applicable edit."
        ),
    )
    iterate_parent.add_argument(
        "--purity",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "run the optional per-step MIXED-STEP purity Claude battery in "
            "phase 1. Default: OFF. Returned medium ``granularity-split`` "
            "hints remain advisory, while a scan that fails or is skipped "
            "after the battery budget expires is a blocking coverage gap. "
            "The ``PLAN_TOOL_PURITY_CLAUDE_TIMEOUT`` and "
            "``PLAN_TOOL_PURITY_SCAN_BUDGET`` environment settings bound "
            "each call and the full battery. Off keeps the fast deterministic "
            "checks and conceptual audit passes. ``--no-purity`` remains "
            "accepted and is now a no-op."
        ),
    )
    iterate_parent.add_argument(
        "--include-info",
        action="store_true",
        dest="include_info",
        default=False,
        help=(
            "apply info-severity findings too. Default: info findings "
            "are advisory (a concept too vague to audit, a heuristic "
            "hit, a detail-only path) and are excluded from the apply "
            "loop -- they're still reported in the deferred summary, "
            "just not auto-applied. Pass this to spend claude tokens "
            "applying them as well."
        ),
    )
    iterate_parent.add_argument(
        "--no-collision-sidecar",
        action="store_false",
        dest="collision_sidecar",
        default=True,
        help=(
            "skip the change-collision sidecar pause when drift fires "
            "during apply_finding. Default: when drift is detected "
            "post-apply, plan-tool saves claude's edits to "
            "`<stem>-change-collision<ext>` next to each modified "
            "original, restores originals to pre-apply state, and "
            "pauses interactively for the user to merge with their "
            "preferred tool (vimdiff, `code --diff`, meld, etc.). "
            "Pressing Enter at the prompt continues the iteration "
            "loop against the merged state; Ctrl-D / typing 'abort' "
            "halts as today. Pass this flag to revert to the legacy "
            "'keep claude's edits on disk, review via git diff' "
            "behavior -- useful when scripting or piping to a CI "
            "consumer that doesn't expect sidecar files. Headless "
            "runs (-y or non-TTY) auto-skip the pause and fall "
            "through to halt regardless of this flag, since there's "
            "no human to merge."
        ),
    )

    p_completeness = sub.add_parser(
        "completeness-audit",
        help=(
            "conceptual audit of a plan: deterministic authoring-gap "
            "checks (body sections, detail files, lessons) plus a claude "
            "call judging whether the plan's own concepts are correct, "
            "complete, and unambiguous (grounded in the per-step detail bundle "
            "where present + "
            "code at HEAD; a bare plan with no detail yet is audited at the "
            "plan/concept level). Conceptual gaps are reported for a "
            "session-directed edit, not applied by a tool command. A "
            "completed audit exits 0; findings "
            "are in the report (and --json exposes stage-aware "
            "has_blocking_findings, conceptual_bar_blocking_ids, and "
            "audit_incomplete), or use --fail-on-findings to gate CI on "
            "bar-aware blockers and incomplete audit samples. With "
            "--iterate, applies the deterministic well-formedness findings "
            "and converges on them; conceptual ambiguity is reported with "
            "correctness, and both it and completeness gaps are persisted "
            "unapplied for a session-directed edit (#85)."
        ),
        parents=[yes_parent, iterate_parent, fail_on_findings_parent],
    )
    p_completeness.add_argument(
        "--iterate",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "after the audit, run the same apply-findings / re-audit "
            "convergence loop the other subcommands use (shared "
            "ConvergenceState + iteration lock + scope guard): apply each "
            "open finding via claude and re-audit until findings converge "
            "or --max-iterations / --iteration-budget is hit. Before the "
            "first apply this saves a pre-apply checkpoint report under the "
            "usual <ts>-completeness names, marked in its payload as "
            "crash-recovery evidence so it is skipped by --reuse-audit and "
            "by convergence history; the run's final report is written after "
            "the loop and is the eligible one. Default off -- pass --iterate "
            "to opt in or --no-iterate to assert it stays off."
        ),
    )
    p_completeness.add_argument(
        "name",
        help="plan name — slug, filename stem (e.g. 1-my-feature), or filename.md",
    )
    p_completeness.add_argument(
        "--json",
        action="store_true",
        help=(
            "emit machine-readable JSON instead of the grouped markdown "
            "report. Top-level keys include stage (bare|detail), "
            "audit_incomplete, conceptual_bar_blocking_ids (null when "
            "incomplete), and bar-aware has_blocking_findings (not flat "
            "medium+ on conceptual findings). The payload includes a "
            "top-level coverage block (budget_limited, optionally "
            "early_stop_reason for a terminal plan quota, "
            "passes_used, cap, "
            "conforming_pass_count, failed_or_malformed_pass_count, "
            "recommendation_kind, recommended_passes, recommendation_advice, "
            "confirmation_kind) so machine consumers can distinguish a clean "
            "audit from pass-cap and terminal-plan-quota coverage-unconfirmed "
            "stops. A terminal plan quota ends conceptual sampling for that "
            "invocation, reports early_stop_reason: plan-quota, and writes no "
            "ordinary final reusable findings sidecar. The three "
            "recommendation fields are retained as null compatibility keys; "
            "a fresh run-grade arm-clustering result appears separately as "
            "audit_shape_advisory with non-routing keep-or-carve evidence."
        ),
    )
    p_completeness.add_argument(
        "--audit-passes",
        type=int,
        # ``None`` (not the numeric default) is the sentinel
        # ``_resolve_audit_reuse`` reads to tell an explicit ``--audit-passes
        # N`` (forces a fresh audit, suppressing reuse auto-accept) from the
        # unset default (the static 3, reuse-eligible). Every consumer
        # coalesces via ``_effective_audit_passes``.
        default=None,
        dest="audit_passes",
        metavar="N",
        help=(
            "how many full, independent conceptual-audit passes to run, "
            "unioning findings by stable id so one report captures the stable "
            "set rather than a single pass's subset (default: 3). Each pass is "
            "a complete audit over the whole plan + code at HEAD — extra "
            "passes re-roll the LLM's non-determinism, they do not cover more "
            "of the plan, so the count is static, not scaled by plan size. 1 "
            "reproduces the legacy single-call behavior; higher trades claude "
            "calls for coverage. Passing this explicitly forces a fresh audit "
            "even when a reusable saved audit exists (unless --reuse-audit is "
            "set)."
        ),
    )
    # Deprecated alias of --audit-passes (same ``audit_passes`` dest). The
    # concept was renamed from "sample" to "pass" because each is a full
    # independent audit pass, not a subset of the plan.
    p_completeness.add_argument(
        "--audit-samples",
        type=int,
        default=None,
        dest="audit_passes",
        metavar="N",
        help="(deprecated alias of --audit-passes)",
    )
    p_completeness.add_argument(
        "--reuse-audit",
        action=argparse.BooleanOptionalAction,
        default=None,
        dest="reuse_audit",
        help=(
            "reuse the saved conceptual audit's findings instead of "
            "re-running the claude call, when the saved audit is fresh "
            "(plan AND code fingerprints still match). Default (unset): "
            "prompt interactively, auto-accepting under --yes / --json / "
            "non-TTY stdin. --reuse-audit always reuses a fresh save (even "
            "over an explicit --audit-passes); --no-reuse-audit always "
            "re-audits. A stale save is never reused — it declines to a "
            "fresh audit with a staleness note. Only an ordinary final "
            "sidecar is eligible: the newest save is skipped when its payload "
            "marks it a pre-apply checkpoint, carries an unrecognized role, "
            "or is not a completeness payload despite the filename, and the "
            "next eligible final is used instead."
        ),
    )
    p_completeness.add_argument(
        "--reuse-audit-id",
        default=None,
        dest="reuse_audit_id",
        metavar="STEM",
        help=(
            "pin reuse to a specific saved completeness audit by filename "
            "stem (the bare `<ts>` or full `<ts>-completeness` form); "
            "default: newest eligible `-completeness.json` for this plan. "
            "This stays an exact selection request: an id naming a pre-apply "
            "checkpoint, an unrecognized role, or a non-completeness payload "
            "supplies no reusable findings and never silently falls back to "
            "an older report. An unresolved or ineligible id prints a note "
            "and runs a fresh audit; no sidecar needs renaming."
        ),
    )
    p_completeness.add_argument(
        "--audit-dry-rounds",
        type=int,
        default=AUDIT_DEFAULT_DRY_ROUNDS,
        dest="audit_dry_rounds",
        metavar="N",
        help=(
            f"stop early after N consecutive audit passes surface no "
            f"new finding (default: {AUDIT_DEFAULT_DRY_ROUNDS}); capped by "
            f"--audit-passes. The default 1 stops on the first no-new pass; "
            f"raise it to require a streak of confirming dry passes (treating "
            f"a single dry pass as noise) at the cost of extra Claude calls. "
            f"Cost scales with how long the plan keeps discovering, bounded "
            f"by the --audit-passes hard cap."
        ),
    )
    p_completeness.add_argument(
        "--grade",
        choices=JIRA_GRADE_VALUES,
        default=GRADE_DEFAULT,
        dest="grade",
        help=(
            f"which detail bundle grounds the conceptual audit (default: "
            f"{GRADE_DEFAULT}). `{GRADE_JIRA}` reads the compact jira-grade "
            "artifacts under plan-details/<plan_slug>/jira/ and tells the "
            "judge to apply that contract, so a missing file list or test "
            "roster is not read as a gap; the run-grade detail file is never "
            "substituted. Mutually exclusive with --iterate, --reuse-audit, "
            "and --reuse-audit-id (all grounded on the run-grade bundle), "
            "and it turns the MIXED-STEP purity pass off (that verdict reads "
            "the run-grade body), making --no-purity a no-op."
        ),
    )
    p_completeness.add_argument(
        "--commit",
        action="store_true",
        dest="commit",
        help=(
            "after a clean --iterate run that applied findings, stage all "
            "changes (git add -A) and create one commit with subject "
            "'plan(<slug>): completeness — applied audit findings'. Requires "
            "--iterate (an audit-only run makes no plan edits) and a clean "
            "working tree up front; off by default; ignored with --json."
        ),
    )

    p_completeness_apply = sub.add_parser(
        "completeness-apply",
        help=(
            "DEPRECATED, going away (BACKLOG #376) — walking findings one "
            "gap at a time is slow and obscures the convergence signal; "
            "read the saved report and make a session-directed edit to the "
            "plan/detail files "
            "instead. "
            "walk the conceptual gaps from the most recent saved "
            "`completeness-audit` and apply gap-closing edits via claude, one "
            "finding at a time, AND deterministically clear files-coherence "
            "drift (no claude: add cited real-file paths to the step's "
            "allowed_mentions). Walks BOTH conceptual sources — "
            "plan-correctness (including material ambiguity) first, then "
            "plan-completeness — which the audit "
            "persists unapplied (read-only-audit split, #85). Pairs with "
            "completeness-audit; does NOT re-run the audit. A current saved "
            "arm-clustering advisory prints once as a non-blocking keep-or-"
            "carve prompt before serial work or parallel worker provisioning; "
            "a stale advisory is hidden without changing the saved walk. Always "
            "interactive: one per-gap confirm so you review each conceptual "
            "issue in context (no blanket auto-apply). On a bare plan only "
            "plan-correctness gaps are walked; other saved sources are "
            "reported as withheld until detail exists. The deterministic "
            "files-coherence fix runs only when a complete detail bundle "
            "exists. On a non-interactive stdin the walk is skipped and "
            "the gaps are reported. "
            "`--anchor <slug>` (repeatable) restricts to specific gaps."
        ),
        parents=[yes_parent],
    )
    p_completeness_apply.add_argument(
        "name",
        help="plan name — slug, filename stem (e.g. 1-my-feature), or filename.md",
    )
    p_completeness_apply.add_argument(
        "--id",
        default=None,
        metavar="STEM",
        help=(
            "load a specific saved completeness audit by filename stem "
            "(e.g. 20260505-123456-completeness); default: newest "
            "`-completeness.json` for this plan"
        ),
    )
    p_completeness_apply.add_argument(
        "--anchor",
        action="append",
        default=[],
        metavar="SLUG",
        help=(
            "address one gap by its `[anchor-slug]` (from the report). "
            "Repeatable to target several gaps. Default: walk all gaps."
        ),
    )
    p_completeness_apply.add_argument(
        "--rewalk",
        action="store_true",
        help=(
            "re-prompt items that already have annotations (default: "
            "skip already-annotated items)"
        ),
    )
    p_completeness_apply.add_argument(
        "--include-info",
        action="store_true",
        dest="include_info",
        help="walk info-level gaps too (default: skip them)",
    )
    p_completeness_apply.add_argument(
        "--apply-structural",
        action="store_true",
        dest="apply_structural",
        help=(
            "opt the serial walk into *applying* a medium granularity-split "
            "step split (via escalate_to_split) on a safe plan with an "
            "interactive confirm; without it (or under -y, or --jobs > 1) the "
            "split finding is recommend-only. Independent of --include-info: "
            "the medium split is walked regardless of it."
        ),
    )
    p_completeness_apply.add_argument(
        "--commit",
        action="store_true",
        dest="commit",
        help=(
            "after applying gap-closing edits, stage all changes (git add "
            "-A) and create one commit with subject 'plan(<slug>): "
            "completeness — applied N gap(s)'. Requires a clean working tree "
            "up front; off by default; only commits when a gap was applied."
        ),
    )
    from plan_tool.cli.authoring import _positive_int

    p_completeness_apply.add_argument(
        "--jobs",
        type=_positive_int,
        default=1,
        dest="jobs",
        metavar="N",
        help=(
            "apply up to N gaps concurrently in isolated worktrees (explicit "
            "integer >= 1; default 1 = the interactive per-gap walk; there is "
            "no 0/auto mode). N>1 is NON-INTERACTIVE and requires -y (it "
            "bypasses the per-gap confirm), a clean working tree (isolation is "
            "off HEAD), and applies both conceptual sources (including "
            "ambiguity under correctness) correctness-first. "
            "A single --anchor gap degrades to serial (nothing to parallelize)."
        ),
    )

    return {
        "completeness-audit": cmd_completeness,
        "completeness-apply": cmd_completeness_apply,
    }
