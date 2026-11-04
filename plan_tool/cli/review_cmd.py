"""Audit command module — the ``reconcile-plan`` / ``reconcile-plan-walk`` /
``verify-all`` verbs.

These handlers answer "is this plan still in sync with the codebase, and
did the done steps hold up?" Naming convention: ``reconcile-*`` verbs may
mutate the plan (their apply path edits plan/detail prose); ``verify-*``
verbs are strictly read-only. None changes step *run-state*.

- ``reconcile-plan`` runs a plan-wide audit: one ``review_plan_full`` claude
  call plus deterministic primitives, persisted as a walkable artifact whose
  apply-walk edits the plan/detail to match code. Aliases: ``reconcile``,
  ``review``.
- ``reconcile-plan-walk`` walks and applies a saved reconcile's findings
  interactively — no claude call. Kind-agnostic despite the name. Aliases:
  ``reconcile-walk``, ``review-walk``.
- ``verify-all`` audits every done step read-only: ``--mode <m>`` sweeps a
  review mode (one claude call per step) via ``run_all_done_steps``, or
  ``--rollup`` aggregates the reconcile prompt into a per-step pass/warn/fail
  verdict via ``verify_plan``. Aliases: ``reconcile-all``, ``review-all``,
  and ``verify`` (which defaults to ``--rollup``).

Import edge is one-directional: ``review_cmd`` imports the cycle-free
leaves (``console`` / ``context`` / ``parser``), the step-15 review-action
factory (``review_actions``), and domain packages — never ``app``. Each
handler reads its claude-driving collaborator (``review_plan_full`` /
``run_all_done_steps`` / ``verify_plan`` / ``walk_recommendations`` /
``refresh_plan``) as its own module global, so a monkeypatch that drives
one of these verbs must target ``plan_tool.cli.review_cmd``. ``app`` re-imports every moved name so
the package surface and any residual bare-name reader keep resolving.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import sys
from pathlib import Path, PureWindowsPath
from typing import Optional

from plan_tool.launcher import (
    LauncherError,
    MUTATING_MODES,
    format_findings_verdict,
    run_all_done_steps,
    summarize_findings,
    verify_plan,
)
from plan_tool.locator import (
    PlanToolContext,
    resolve_plan_for_context,
)
from plan_tool.fingerprint import compute_code_fingerprint
from plan_tool.parser import ParseError, ValidationError, parse_plan
from plan_tool.refresh import refresh_plan
from plan_tool.review import (
    RESTATED_PROPERTY_LABEL,
    ReviewError,
    confidence_label,
    is_pairwise_merge_finding,
    restated_property_or_none,
    review_plan_full,
)
from plan_tool.run_log import RunLogWriter
from plan_tool.review_persistence import (
    AuditInputError,
    AuditInputSnapshot,
    ReviewLoadError,
    SavedReview,
    compute_plan_fingerprint,
    list_saved_reviews,
    load_review,
    plan_reports_dir,
    project_saved_completeness_result,
    save_review,
)

from plan_tool.review_walk import (
    WalkState,
    WalkResponsePolicy,
    stamp_target_signatures,
    walk_recommendations,
)
from plan_tool.style import (
    BOLD,
    color_enabled,
    error,
    info,
    paint,
    render_markdown_for_console,
    warn,
)

from plan_tool.cli.console import _format_relative_age, _print_next_steps
from plan_tool.cli.context import _load_context
from plan_tool.cli.parser import Handler, make_yes_parent
from plan_tool.cli.reconcile import (
    _note_reuse_code_drift,
    _note_reuse_removed_code_files,
)

# The shared review-action builder (step-15 lower leaf). ``cmd_review`` and
# ``cmd_review_walk`` call it with explicit kwargs; it is never patched, so
# the qualified import is safe. ``review_actions`` imports neither
# ``review_cmd`` nor ``app``, so this edge stays cycle-free.
from plan_tool.cli.review_actions import _build_review_action_fn


_REVIEW_SEP = "=" * 62
_FAILED_REVIEW_OUTPUT_CAP = 2_000


def _is_basename_saved_review_id(review_id: str) -> bool:
    """Whether ``review_id`` names one literal sidecar basename.

    Direct walks match an explicit id against paths already returned by the
    canonical listing. Rejecting path-shaped values before that comparison
    keeps an id from becoming a locator for a different plan's artifact on
    either POSIX or Windows-style input.
    """
    if review_id in {"", ".", ".."} or "/" in review_id or "\\" in review_id:
        return False
    posix_path = Path(review_id)
    windows_path = PureWindowsPath(review_id)
    return (
        posix_path.name == review_id
        and not posix_path.is_absolute()
        and windows_path.name == review_id
        and not windows_path.is_absolute()
    )


def _resolved_plan_reports_dir(plan_path: Optional[Path]) -> Optional[Path]:
    """Resolve a non-redirected reports root for direct-walk bounds.

    The root itself is part of the plan binding.  Resolving only the root and
    then checking children against it would let a ``reports/`` symlink point at
    a different plan's otherwise-contained artifacts.  Direct walks are an
    apply path, so require the canonical reports location beside the resolved
    plan to be a real directory before accepting any listed candidate.
    """
    if plan_path is None:
        return None
    try:
        resolved_plan_path = plan_path.resolve(strict=True)
        reports_dir = plan_reports_dir(resolved_plan_path)
        resolved_reports_dir = reports_dir.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    return resolved_reports_dir if resolved_reports_dir == reports_dir else None


def _is_contained_saved_review_candidate(
    candidate: Path, resolved_reports_dir: Optional[Path]
) -> bool:
    """Whether a listed sidecar resolves inside this plan's reports directory."""
    if resolved_reports_dir is None:
        return False
    try:
        candidate.resolve(strict=True).relative_to(resolved_reports_dir)
    except (OSError, RuntimeError, ValueError):
        return False
    return True


def _direct_walk_role_ineligibility(saved: SavedReview) -> Optional[str]:
    """Why a loaded sidecar cannot enter a direct recommendation walk."""
    if saved.is_pre_apply_checkpoint is False:
        return None
    if saved.is_sampler_checkpoint:
        return "is a sampler checkpoint, not a final saved review"
    if saved.is_pre_apply_checkpoint is True:
        return "is a pre-apply checkpoint, not a final saved review"
    return "carries an unknown checkpoint role, not a final saved review"


def _direct_walk_ineligibility(
    saved: SavedReview,
    *,
    plan_path: Optional[Path],
    repo_root: Path,
) -> Optional[str]:
    """Return the final/current gate reason for a direct saved-review walk."""
    role_reason = _direct_walk_role_ineligibility(saved)
    if role_reason is not None:
        return role_reason
    if saved.kind == "completeness" and not project_saved_completeness_result(
        saved, plan_path, repo_root
    ).is_current_final_qualified:
        return (
            "is not current qualified completeness evidence; run "
            "`plan-tool completeness-audit` first"
        )
    return None


def _review_reuse_ineligibility(saved: SavedReview) -> Optional[str]:
    """Why *saved* may not be reused as a plan-wide review — ``None`` if it may.

    Only the loaded payload decides: a ``kind="review"`` sidecar whose
    persisted role is the ordinary final one. A pre-apply completeness
    checkpoint holds findings captured before its apply finished, and an
    unknown role is metadata no reader may trust as final, so both fail
    closed. Returns an operator-facing clause that completes "saved review
    <id> …". See DATA_CONTRACT.md § ``SavedReview`` for the role states.
    """
    if saved.is_sampler_checkpoint:
        return "is a sampler checkpoint, not a final review"
    if saved.is_pre_apply_checkpoint is True:
        return "is a pre-apply audit checkpoint, not a final review"
    if saved.kind != "review":
        return f"is a {saved.kind} sidecar, not a plan-wide review"
    if saved.is_pre_apply_checkpoint is None:
        return "carries an unknown checkpoint role"
    return None


def _prompt_reuse_saved_review(
    ctx: PlanToolContext,
    plan_slug: str,
    args: argparse.Namespace,
    *,
    input_fn=None,
    before_prompt=None,
    plan_path: Optional[Path] = None,
) -> Optional[Path]:
    """When a saved review exists for ``plan_slug``, offer to walk it.

    Returns the saved path when the user accepts, ``None`` when they
    decline or the prompt is suppressed. Suppressed when:

    - ``--dry-run`` (the user wants to inspect the rendered prompt,
      not walk anything);
    - ``--no-walk`` or ``--no-save`` (explicit opt-outs of the
      walkable artifact);
    - ``--step N`` is set (the saved review may not align with a
      step-specific request);
    - ``--no-reuse`` (``reuse is False``) — never look up a sidecar;
    - no saved review on file, or none that is eligible and fresh.

    Eligibility is decided by the loaded payload, never the filename
    (:func:`_review_reuse_ineligibility`): only an ordinary-final
    ``kind="review"`` sidecar can stand in for a fresh audit. Unpinned,
    the ``list_saved_reviews`` newest-first order is scanned one candidate
    at a time and unreadable, checkpoint, unknown-role, and non-review
    saves are skipped, so a partial checkpoint is never walked as a
    plan-wide review. Freshness runs once, on the newest eligible
    candidate: a stale one starts a fresh review rather than widening the
    scan to older saves.

    The ``--reuse`` / ``--no-reuse`` / ``--reuse-id`` tri-state (read via
    ``getattr`` so the helper stays callable from the ``cmd_review``
    namespace without a hard attribute dependency) mirrors the reconcile
    core's tri-state — the plan-wide ``review`` kind has no
    ``resolve_reusable_*`` sibling, so it gates the flags inline. ``--reuse``
    accepts an eligible fresh save with no prompt; the unset default
    auto-accepts under ``--yes`` / non-TTY stdin and otherwise prompts;
    ``--reuse-id`` pins one save by stem — exactly one, so an unresolvable
    stem, an unreadable file, and an ineligible payload each decline with
    their own reason and run fresh instead of falling back to an older save.
    """
    if args.dry_run or args.no_walk or args.no_save:
        return None
    if args.step is not None:
        return None

    # --no-reuse never even looks up a sidecar (hard opt-out).
    reuse = getattr(args, "reuse", None)
    if reuse is False:
        return None
    reuse_id = getattr(args, "reuse_id", None)

    from plan_tool.review_persistence import (
        list_saved_reviews,
        ReviewLoadError as _RLE,
    )

    candidates = list_saved_reviews(plan_slug, ctx.repo_root, plan_path=plan_path)
    if not candidates:
        return None

    if reuse_id is not None:
        # --reuse-id pins the lookup to one save by filename stem. A stem
        # that matches nothing warns and proceeds to a fresh review (never a
        # non-zero exit), mirroring the reconcile core's pinned-miss path.
        pinned = next((p for p in candidates if p.stem == reuse_id), None)
        if pinned is None:
            error(
                f"no saved review matched --reuse-id {reuse_id!r}; "
                f"running a fresh review"
            )
            return None
        candidates = [pinned]

    # --- Eligibility scan (payload, never filename) --------------------
    # A filename locates a sidecar; it is no evidence of the payload's kind
    # or role, so every candidate is loaded before it is trusted. Unpinned,
    # take the newest ordinary-final ``review`` save and skip the rest — an
    # unreadable file can't block reuse of an older final report, and a
    # checkpoint / unknown role / other kind is never walked. A pin names
    # exactly one sidecar: an ineligible one declines with its own reason
    # instead of silently reusing a different save.
    most_recent: Optional[Path] = None
    saved: Optional[SavedReview] = None
    for candidate in candidates:
        try:
            loaded = load_review(candidate)
        except _RLE:
            reason: Optional[str] = "could not be read"
        else:
            reason = _review_reuse_ineligibility(loaded)
            if reason is None:
                most_recent, saved = candidate, loaded
                break
        if reuse_id is not None:
            error(
                f"saved review {reuse_id!r} {reason}; running a fresh review"
            )
            return None
    if saved is None or most_recent is None:
        return None

    # --- Fingerprint-freshness gate -----------------------------------
    # Offer reuse only when the located sidecar still matches disk (saved
    # plan- AND code-fingerprint == current). A stale save declines to a
    # fresh review (return None) — never a non-zero exit. The plan-wide
    # "review" kind has no resolve_reusable_* sibling, so the verdict is
    # computed inline here, mirroring completeness_report.resolve_reusable_audit's
    # changed|deleted|new diff. Best-effort: a malformed plan or a read
    # failure drops to a fresh review rather than crashing the command.
    if plan_path is None:
        return None
    try:
        plan_match = bool(saved.plan_fingerprint) and (
            saved.plan_fingerprint == compute_plan_fingerprint(plan_path)
        )
        drifted_plan = None
        footprint_changed = False
        drifted_code_paths: list[Path] = []
        removed_code_paths: list[Path] = []
        if not saved.code_fingerprint_present:
            # Legacy/never-computed capture: no baseline to diff, so every
            # current file would be a spurious `new` key. Stale, no drift.
            code_match = False
        else:
            drifted_plan = parse_plan(plan_path)
            current = compute_code_fingerprint(
                drifted_plan, plan_path, ctx.repo_root
            )
            from plan_tool.fingerprint import diff_code_fingerprint

            code_diff = diff_code_fingerprint(
                saved.code_fingerprint, current, ctx.repo_root
            )
            code_match = code_diff.match
            drifted_code_paths = list(code_diff.content_drifted)
            # A deleted declared file is footprint membership, not content
            # drift. Its unchanged plan still provides valid ownership for an
            # attributed removal message; a changed plan retains the generic
            # footprint note because its current mapping is not reliable.
            if plan_match:
                removed_code_paths = list(code_diff.footprint_removed)
            footprint_changed = bool(
                code_diff.footprint_added or code_diff.footprint_removed
            )
    except (ParseError, ValidationError, OSError):
        return None
    if not (plan_match and code_match):
        if not code_match:
            if drifted_code_paths and drifted_plan is not None:
                _note_reuse_code_drift(
                    drifted_code_paths, drifted_plan, ctx.repo_root
                )
            if removed_code_paths and drifted_plan is not None:
                _note_reuse_removed_code_files(
                    removed_code_paths, drifted_plan, ctx.repo_root
                )
            if not drifted_code_paths and not removed_code_paths and footprint_changed:
                info(
                    f"saved review is stale (plan footprint changed since "
                    f"{saved.created_at}); running fresh"
                )
        elif not plan_match:
            info(
                f"saved review is stale (plan changed since "
                f"{saved.created_at}); running fresh"
            )
        return None

    n_recs = len(saved.recommendations)
    n_annotated = len(saved.annotations)
    age = _format_relative_age(saved.created_at)
    try:
        rel = most_recent.relative_to(ctx.repo_root.resolve()).as_posix()
    except ValueError:
        rel = str(most_recent)

    print(
        f"\nA saved review for {plan_slug!r} exists ({age}, "
        f"{n_recs} rec(s), {n_annotated} annotated):"
    )
    print(f"  {rel}")
    # Fresh-save dispatch by flag: --reuse accepts with no prompt; the unset
    # default auto-accepts under --yes / non-TTY stdin and otherwise prompts.
    yes = getattr(args, "yes", False)
    if reuse is True or yes or not sys.stdin.isatty():
        prefix = (
            "(--yes)" if yes else "(--reuse)" if reuse is True else "(reuse)"
        )
        verb = "walking" if _review_walk_environment_allows(args) else "reusing"
        print(f"{prefix} {verb} saved review")
        return most_recent
    if input_fn is None:
        # Look up ``builtins.input`` at call time so monkeypatch in
        # tests is honored (a default param ``input_fn=input`` would
        # bind the original builtin at function-definition time and
        # bypass the patch).
        import builtins
        input_fn = builtins.input
    if before_prompt is not None:
        before_prompt()
    answer = input_fn(
        "Walk that one instead of running a fresh review? [y/N] "
    ).strip().lower()
    if answer in ("y", "yes"):
        return most_recent
    return None


def _tty_review_walk_allowed(args: argparse.Namespace) -> bool:
    """Whether cmd_review may start its full terminal walk."""
    return (
        not args.no_walk
        and not args.no_save
        and not args.dry_run
        and sys.stdin.isatty()
    )


def _remote_non_tty_review_walk_allowed(args: argparse.Namespace) -> bool:
    """Whether explicit remote mode may start its restricted headless walk."""
    return (
        not args.no_walk
        and not args.no_save
        and not args.dry_run
        and _is_remote_non_tty_input()
    )


def _is_remote_non_tty_input() -> bool:
    """Whether stdin and the environment select the restricted remote mode."""
    return (
        not sys.stdin.isatty()
        and os.environ.get("PLAN_TOOL_HUMAN_IO") == "remote"
    )


def _review_walk_environment_allows(args: argparse.Namespace) -> bool:
    """Whether cmd_review may start a terminal or restricted remote walk."""
    return (
        _tty_review_walk_allowed(args)
        or _remote_non_tty_review_walk_allowed(args)
    )


def _review_has_promptable_recommendation(
    saved: SavedReview, *, include_info: bool
) -> bool:
    """Whether the normal non-rewalk selection would prompt any finding."""
    for recommendation in saved.recommendations:
        if (
            not include_info
            and (recommendation.severity or "").lower() == "info"
            and not is_pairwise_merge_finding(recommendation)
        ):
            continue
        annotation = saved.annotations.get(recommendation.id)
        if annotation is None or annotation.status == "failed":
            return True
    return False


def _render_saved_review_findings(saved: SavedReview) -> None:
    """Show every saved finding before the restricted remote walk begins."""
    for recommendation in saved.recommendations:
        print(
            f"\n{recommendation.source}/{recommendation.severity}: "
            f"{recommendation.title.strip()} "
            f"[{confidence_label(recommendation.confidence)}]"
        )
        if recommendation.body:
            print(f"  {recommendation.body.strip()}")
        restated = restated_property_or_none(recommendation)
        if restated:
            print(f"  {RESTATED_PROPERTY_LABEL}: {restated}")
        if recommendation.suggested_action:
            print(f"  Suggested action: {recommendation.suggested_action}")


def _render_refresh(outcome, plan_name: str) -> int:
    """Render a :class:`plan_tool.refresh.RefreshOutcome` and return 0.

    A completed refresh is a completed command — exit 0 regardless of how
    many findings the scoped reconcile surfaced (exit-code convention:
    non-zero only on failure-to-complete). Three arms key off the outcome:

    - no drift → "still grounded", no walk pointer (nothing was saved);
    - needs grounding → no baseline existed, a whole-surface reconcile ran;
    - drift → a scoped reconcile ran over the changed files.

    The drift / needs-grounding arms point at ``reconcile-plan-walk`` to
    apply the saved findings, but only when there are findings to walk.
    """
    if not outcome.drifted:
        print(
            f"✓ '{outcome.plan_slug}' is still grounded against the current "
            f"code — nothing to refresh (no Claude call)."
        )
        return 0

    n_files = len(outcome.drifted_files)
    n_findings = outcome.findings
    files_word = "file" if n_files == 1 else "files"
    findings_word = "finding" if n_findings == 1 else "findings"
    scope = (
        f"had no grounding baseline — reconciled the whole declared surface "
        f"({n_files} {files_word})"
        if outcome.needs_grounding
        else f"drifted across {n_files} {files_word} — a scoped reconcile ran"
    )
    if outcome.grounding_path is not None:
        # Zero pending findings: safe to (re-)stamp the baseline.
        stamp = (
            "stamped a baseline grounding sidecar"
            if outcome.needs_grounding
            else "re-stamped the grounding sidecar"
        )
        print(
            f"'{outcome.plan_slug}' {scope}, surfacing {n_findings} "
            f"{findings_word}; {stamp} at {outcome.grounding_path}."
        )
    else:
        # Pending findings: the baseline is deliberately NOT stamped, so the
        # drift gate stays open until a walk applies them — otherwise the next
        # --refresh would read "no drift" and mask the staleness (BACKLOG #68).
        print(
            f"'{outcome.plan_slug}' {scope}, surfacing {n_findings} "
            f"{findings_word}; grounding NOT re-stamped — apply them to clear "
            f"the drift gate (until then, a re-run re-surfaces this drift)."
        )

    if n_findings:
        _print_next_steps(
            "Apply refresh findings:",
            [
                (
                    f"plan-tool reconcile-plan-walk {plan_name}",
                    "step through the saved reconcile findings",
                )
            ],
        )
    return 0


def _audit_sink(run_logger: Optional[RunLogWriter], phase: str):
    """Bind this audit's claude calls to *phase*, or nothing on a dry run.

    ``shell._emit_call_end`` no-ops with no sink installed, so this — not the
    open writer — is what puts an audit's calls in the log.
    """
    if run_logger is None:
        return contextlib.nullcontext()
    return run_logger.bind_shell_sink(phase=phase, attempt=1)


def _run_logged_audit(
    body,
    *,
    args: argparse.Namespace,
    ctx,
    plan_path: Path,
    command: str,
    flags: dict,
    preflight=None,
) -> int:
    """Run one audit handler's body under an open run log.

    These verbs spent Claude with no run log at all — no cost record, no
    ``in-flight.json``, nothing for ``plan-tool runs`` to show (see
    BUG_BACKLOG). The writer is only half of it: ``shell._emit_call_end``
    no-ops unless a sink is installed, so each body still binds one around
    its orchestrator call (``apply_finding`` binds its own).

    ``command`` is the canonical verb, not ``args.command``, so a run under
    an alias (``reconcile``, ``review``) logs under one greppable name. Mirrors
    ``cli/reconcile.py:_cmd_detail_reconcile``: one ``finally`` covering every
    return path, recording the body's real rc.

    ``preflight`` retains no-spend validation ahead of the log, but may call
    the supplied opener when it reaches a blocking interaction. ``--dry-run``
    renders prompts and spends nothing, so it opens no log and the body runs
    with ``None`` — the log exists iff the verb may spend Claude, matching
    ``--refresh`` and ``convergence``.
    """
    if getattr(args, "dry_run", False):
        if preflight is not None:
            preflight_rc = preflight(lambda: None)
            if preflight_rc is not None:
                return preflight_rc
        return body(None)

    run_logger: Optional[RunLogWriter] = None

    def _open_run_log() -> RunLogWriter:
        nonlocal run_logger
        if run_logger is None:
            run_logger = RunLogWriter.start(
                repo_root=ctx.repo_root,
                slug=args.name,
                command=command,
                argv=list(sys.argv[1:]),
                plan_path=plan_path,
                flags=flags,
            )
        return run_logger

    rc = 1
    err_msg: Optional[str] = None
    try:
        if preflight is not None:
            preflight_rc = preflight(_open_run_log)
            if preflight_rc is not None:
                rc = preflight_rc
                return rc
        rc = body(_open_run_log())
        return rc
    except KeyboardInterrupt:
        # Preserve POSIX 130; app's dispatcher catches only ``Exception``.
        rc = 130
        err_msg = "interrupted"
        raise SystemExit(130)
    finally:
        if run_logger is not None:
            run_logger.run_end(
                outcome=("success" if rc == 0 else "error"),
                rc=rc,
                error=err_msg,
            )


def cmd_review(args: argparse.Namespace) -> int:
    """Plan-vs-codebase audit, claude + deterministic primitives (audit).

    Intent: answer "is this plan still in sync with the codebase
    today?" Combines deterministic checks (file existence, deps,
    path-style, looks-already-done heuristic) with a single claude
    semantic review call, and persists the result as a walkable
    artifact under ``plan-details/<slug>/reports/`` so
    :func:`cmd_review_walk` can step through recommendations later
    without re-spending a claude call.

    Three audit verbs answer three different questions:

    - :func:`cmd_validate` → schema valid? (instant, deterministic)
    - :func:`cmd_review` → paths/deps correct + does the plan match the
      code it would edit? (one claude call)
    - :func:`cmd_completeness` → deterministic authoring gaps, then are
      the plan's own concepts correct + complete + unambiguous, grounded in
      the detail bundle + code at HEAD? (1-3 claude calls — the sampled
      conceptual
      audit)

    New audit subcommands should slot into one of those three rows.
    See the table in SKILL.md's "Subcommands at a glance".

    See ``docs/reference/contracts/process.md`` for the pre-execution code-authority
    boundary against ``reconcile-code``.
    """
    ctx = _load_context(args)
    path = resolve_plan_for_context(ctx, args.name)

    # --refresh short-circuits the audit: drift-gate the plan's grounding
    # against the code (no claude call) and reconcile only the changed files.
    # Branch before the reuse prompt / review_plan_full so neither runs.
    # Ahead of the run log too: a no-Claude path opens no log, matching
    # ``convergence``'s no-spend/no-log contract.
    if getattr(args, "refresh", False):
        return _render_refresh(refresh_plan(path, ctx.repo_root), args.name)

    reuse_path: Path | None = None

    def _preflight(open_run_log) -> Optional[int]:
        nonlocal reuse_path
        reuse_path = _prompt_reuse_saved_review(
            ctx, args.name, args, plan_path=path, before_prompt=open_run_log
        )
        if reuse_path is not None:
            return None
        try:
            AuditInputSnapshot.capture(path, ctx.repo_root)
        except AuditInputError as exc:
            error(str(exc))
            return 2
        return None

    return _run_logged_audit(
        lambda run_logger: _cmd_review_body(
            args, ctx, path, run_logger, reuse_path=reuse_path
        ),
        args=args,
        ctx=ctx,
        plan_path=path,
        command="reconcile-plan",
        flags={
            "dry_run": bool(getattr(args, "dry_run", False)),
            "step": getattr(args, "step", None),
            "all": bool(getattr(args, "all", False)),
            "no_save": bool(getattr(args, "no_save", False)),
        },
        preflight=_preflight,
    )


def _cmd_review_body(
    args: argparse.Namespace,
    ctx,
    path: Path,
    run_logger: Optional[RunLogWriter],
    *,
    reuse_path: Path | None,
) -> int:
    """``cmd_review``'s work, under the caller's open run log."""
    if reuse_path is not None:
        try:
            saved = load_review(reuse_path)
        except ReviewLoadError as exc:
            print(f"error loading saved review: {exc}", file=sys.stderr)
            return 1
        # Reuse reaches this path under --reuse / --yes / non-TTY stdin too.
        # Ordinary non-TTY runs report and return; explicit remote mode may
        # enter only its restricted skip-or-quit walk below.
        walk_allowed = _review_walk_environment_allows(args)
        remote_non_tty_walk = _remote_non_tty_review_walk_allowed(args)
        verb = "Walking" if walk_allowed else "Reusing"
        print(f"\n{verb} saved review {reuse_path}")
        if not saved.recommendations:
            print("(saved review has no recommendations to walk)")
            return 0
        if remote_non_tty_walk:
            _render_saved_review_findings(saved)
            if _review_has_promptable_recommendation(
                saved, include_info=args.include_info
            ):
                walk_recommendations(
                    saved,
                    skip_info=not args.include_info,
                    response_policy=WalkResponsePolicy.SKIP_OR_QUIT,
                    render_recommendation=False,
                )
            return 0
        if not walk_allowed:
            warn(
                f"non-interactive stdin: skipping the walk "
                f"({len(saved.recommendations)} finding(s)). Re-run "
                f"`plan-tool reconcile-plan-walk {args.name} --id "
                f"{reuse_path.stem}` on a terminal to walk them."
            )
            for rec in saved.recommendations:
                print(
                    f"  {rec.source}/{rec.severity}: {rec.title.strip()} "
                    f"[{confidence_label(rec.confidence)}]"
                )
            return 0
        state = WalkState()
        action_fn = _build_review_action_fn(
            ctx=ctx,
            plan_path=path,
            plan_name=args.name,
            allow_structural_remedy=getattr(args, "apply_structural", False),
            allow_merge_remedy=getattr(args, "merge_remedy", False),
            allow_reground_remedy=getattr(args, "reground_remedy", False),
            reground_rebaseline=getattr(args, "reground_rebaseline", False),
            saved_plan_fingerprint=saved.plan_fingerprint,
            allow_structural_verdict=True,
            state=state,
            run_logger=run_logger,
        )
        walk_recommendations(
            saved,
            action_fn=action_fn,
            state=state,
            skip_info=not args.include_info,
        )
        return 0

    try:
        # The sink is what lands the audit's claude call in the log; the open
        # writer alone records nothing. Covers the lessons-extraction call in
        # the same phase — coarse, but attributed to the verb that spent it.
        with _audit_sink(run_logger, "reconcile_plan"):
            result = review_plan_full(
                path,
                repo_root=ctx.repo_root,
                plan_name=args.name,
                step_id=args.step,
                dry_run=args.dry_run,
                no_heuristic=args.no_heuristic,
                allow_missing_parent=args.allow_missing_parent,
                extract_lessons=getattr(args, "lessons", False),
                walk_will_run=_tty_review_walk_allowed(args),
            )
    except ReviewError as exc:
        error(str(exc))
        return 2

    # Console-friendly rendering for the report (markers stripped so
    # paths stay clickable); the dry-run output is the raw prompt, not a
    # report — pass it through untouched. save_review below persists the
    # raw markdown either way.
    print(
        result.report if result.dry_run
        else render_markdown_for_console(result.report)
    )

    # Persistence: skip on dry-run (no real report) and when --no-save.
    # The save artifact lets `plan-tool reconcile-plan-walk` step through the
    # recommendations later without re-invoking claude.
    saved_path: Optional[Path] = None
    if not result.dry_run and not args.no_save:
        # Persist a canonical repo-relative POSIX value, not a lexical warning path.
        try:
            plan_rel = path.resolve().relative_to(ctx.repo_root.resolve()).as_posix()
        except ValueError:
            plan_rel = str(path.resolve())
        # ``ReviewResult`` carries no parsed ``Plan``, so parse fresh to
        # capture both staleness axes for the saved sidecar (step 4/5
        # reuse checks).
        plan = parse_plan(path)
        plan_fp = compute_plan_fingerprint(path)
        code_fp = compute_code_fingerprint(plan, path, ctx.repo_root)
        # Stamp each directive finding (re-ground / pairwise merge) with the
        # signature of its own target steps so a later walk can gate precisely.
        stamped_recs = stamp_target_signatures(plan, result.recommendations)
        saved_path = save_review(
            plan_slug=args.name,
            plan_path=plan_rel,
            repo_root=ctx.repo_root,
            report_md=result.report,
            recommendations=stamped_recs,
            plan_fingerprint=plan_fp,
            code_fingerprint=code_fp,
            plan=plan,
        )
        n = len(result.recommendations)
        print(f"\nSaved to {saved_path} ({n} recommendation{'s' if n != 1 else ''})")

    # Walk is on by default. Skip when:
    #   - the user opted out (--no-walk);
    #   - there's no save target (--no-save or --dry-run);
    #   - stdin isn't a TTY unless explicit remote human input is selected.
    #   - the review produced zero recommendations.
    if (
        _review_walk_environment_allows(args)
        and saved_path is not None
    ):
        if not result.recommendations:
            return 0
        loaded = load_review(saved_path)
        if _remote_non_tty_review_walk_allowed(args):
            if _review_has_promptable_recommendation(
                loaded, include_info=args.include_info
            ):
                walk_recommendations(
                    loaded,
                    skip_info=not args.include_info,
                    response_policy=WalkResponsePolicy.SKIP_OR_QUIT,
                    render_recommendation=False,
                )
            return 0
        # The remaining path is a full TTY walk with its existing actions.
        state = WalkState()
        action_fn = _build_review_action_fn(
            ctx=ctx,
            plan_path=path,
            plan_name=args.name,
            allow_structural_remedy=getattr(args, "apply_structural", False),
            allow_merge_remedy=getattr(args, "merge_remedy", False),
            allow_reground_remedy=getattr(args, "reground_remedy", False),
            reground_rebaseline=getattr(args, "reground_rebaseline", False),
            saved_plan_fingerprint=loaded.plan_fingerprint,
            allow_structural_verdict=True,
            state=state,
            run_logger=run_logger,
        )
        walk_recommendations(
            loaded,
            action_fn=action_fn,
            state=state,
            skip_info=not args.include_info,
        )

    return 0


def cmd_review_walk(args: argparse.Namespace) -> int:
    """Walk + apply a saved reconcile's findings — ``reconcile-apply`` (audit).

    Intent: let the operator revisit a previously-saved reconcile (of any
    kind — ``reconcile-plan`` / ``reconcile-code`` / ``detail --reconcile``
    / the automatic drift-reconcile; named for its primary producer but
    kind-agnostic) without re-spending a claude call. Same per-rec
    apply/skip/note/run/quit loop that :func:`cmd_review` and
    :func:`cmd_reconcile_code` run inline; this verb is the standalone apply
    entry point for saved reconcile findings.

    Loads the newest saved final review for ``<name>`` by default,
    skipping unreadable, checkpoint, and unknown-role sidecars;
    ``--id <stem-or-basename>`` picks one eligible specific save; ``--rewalk``
    re-prompts items that already have annotations.

    New "manage previously-saved audit artifacts" subcommands could
    sit alongside this one. Bulk deletion of saved reviews — when it
    arrives — would naturally pair with :func:`cmd_checkpoint`'s
    clear action.
    """
    ctx = _load_context(args)
    # Saved reviews live alongside the selected plan under
    # ``plan-details/<slug>/reports/``. Direct walks own their selection
    # policy instead of using ``resolve_saved_review``: the generic resolver
    # deliberately remains available to recovery readers that may need a
    # pinned checkpoint.
    try:
        plan_path = resolve_plan_for_context(ctx, args.name)
    except Exception:
        plan_path = None

    try:
        candidates = list_saved_reviews(
            args.name, ctx.repo_root, plan_path=plan_path
        )
    except OSError:
        candidates = []
    resolved_reports_dir = _resolved_plan_reports_dir(plan_path)

    saved_path: Optional[Path] = None
    saved: Optional[SavedReview] = None
    skipped_completeness_evidence = False
    if args.id is not None:
        review_id = args.id
        if not _is_basename_saved_review_id(review_id):
            error(
                f"invalid --id {review_id!r}: expected a non-empty saved "
                "review stem or basename"
            )
            return 2
        matching_candidates = [
            candidate
            for candidate in candidates
            if candidate.name == review_id or candidate.stem == review_id
        ]
        if not matching_candidates:
            error(f"no saved review matched --id {review_id!r}")
            return 2
        if len(matching_candidates) > 1:
            error(f"ambiguous --id {review_id!r}: matched multiple saved reviews")
            return 2
        saved_path = matching_candidates[0]
        if not _is_contained_saved_review_candidate(
            saved_path, resolved_reports_dir
        ):
            error(
                f"saved review --id {review_id!r} resolves outside this "
                "plan's reports directory"
            )
            return 2
        try:
            saved = load_review(saved_path)
        except Exception:
            error(f"saved review --id {review_id!r} could not be read")
            return 2
        reason = _direct_walk_ineligibility(
            saved, plan_path=plan_path, repo_root=ctx.repo_root
        )
        if reason is not None:
            if saved.kind == "completeness":
                error(
                    f"saved review --id {review_id!r} {reason}; run "
                    f"`plan-tool completeness-audit {args.name}` first."
                )
                return 2
            error(f"saved review --id {review_id!r} {reason}")
            return 2
    else:
        # The persistence listing is already newest-first. A sidecar earns
        # direct-walk trust only after its resolved location and loaded role
        # both establish that it is this plan's ordinary final artifact.
        for candidate in candidates:
            if not _is_contained_saved_review_candidate(
                candidate, resolved_reports_dir
            ):
                continue
            try:
                loaded = load_review(candidate)
            except Exception:
                # ``load_review`` intentionally exposes a few malformed
                # content-shape errors for existing readers. Here they are
                # all just unreadable candidates, so keep scanning.
                continue
            reason = _direct_walk_ineligibility(
                loaded, plan_path=plan_path, repo_root=ctx.repo_root
            )
            if reason is None:
                saved_path, saved = candidate, loaded
                break
            if loaded.kind == "completeness":
                skipped_completeness_evidence = True
        if saved_path is None or saved is None:
            if skipped_completeness_evidence:
                error(
                    "no eligible saved review is available: no current final "
                    "qualified completeness audit is available; "
                    f"run `plan-tool completeness-audit {args.name}` first."
                )
                return 2
            error(f"no eligible saved review is available for plan {args.name!r}")
            return 2

    assert saved_path is not None
    assert saved is not None
    if not saved.recommendations:
        print(f"No recommendations in {saved_path}.")
        return 0
    # A remote headless walk records only skip annotations. It never builds an
    # action route, so plan/code changes and feedback remain terminal-only.
    if _is_remote_non_tty_input():
        walk_recommendations(
            saved,
            rewalk=args.rewalk,
            skip_info=not args.include_info,
            response_policy=WalkResponsePolicy.SKIP_OR_QUIT,
        )
        return 0

    # The walk is per-finding: every recommendation is a judgement call the
    # operator makes in context, so there is no blanket auto-apply. A
    # non-interactive stdin (CI / pipe) has nobody to answer the prompts, so
    # report the findings and skip the walk rather than block on input.
    if not sys.stdin.isatty():
        warn(
            f"non-interactive stdin: skipping the walk "
            f"({len(saved.recommendations)} finding(s)). Re-run "
            f"`plan-tool reconcile-plan-walk {args.name}` on a terminal to "
            f"walk them."
        )
        for rec in saved.recommendations:
            print(
                f"  {rec.source}/{rec.severity}: {rec.title.strip()} "
                f"[{confidence_label(rec.confidence)}]"
            )
        return 0
    # Wire the action_fn for both review and reconcile saves: review
    # walks use it for reconcile/detail/apply-finding dispatch on
    # apply; reconcile walks use it for apply-finding on each
    # finding. The handler resolves dispatchability per-rec, so giving
    # it to both kinds is safe.
    action_fn = None
    state = WalkState()
    if plan_path is not None:
        action_fn = _build_review_action_fn(
            ctx=ctx,
            plan_path=plan_path,
            plan_name=args.name,
            allow_structural_remedy=getattr(args, "apply_structural", False),
            allow_merge_remedy=getattr(args, "merge_remedy", False),
            allow_reground_remedy=getattr(args, "reground_remedy", False),
            reground_rebaseline=getattr(args, "reground_rebaseline", False),
            saved_plan_fingerprint=saved.plan_fingerprint,
            allow_structural_verdict=True,
            state=state,
        )
    walk_recommendations(
        saved,
        rewalk=args.rewalk,
        action_fn=action_fn,
        state=state,
        skip_info=not args.include_info,
        response_policy=WalkResponsePolicy.FULL,
    )
    return 0


def cmd_review_all(args: argparse.Namespace) -> int:
    """``verify-all --mode <m>`` worker: sweep a review mode over done steps.

    Intent: run a read-only ``--mode <review>`` prompt against every
    step already marked ``done`` — useful right before merging or
    shipping. One claude subprocess per done step (sequential, by
    design — see SKILL.md "Not yet implemented / out of scope" for why
    parallelization isn't planned).

    The sibling shape is ``verify-all --rollup`` (:func:`cmd_verify`),
    which aggregates the reconcile prompt into a single pass/warn/fail
    rollup. Use ``--mode`` when you want the raw report bodies; use
    ``--rollup`` when you want the verdict. Both exit 0 once the audit
    completes — findings live in the output, not the exit code.

    ``--mode run`` is rejected (see ``MUTATING_MODES``) — this verb
    is audit-only. Reached via :func:`cmd_verify_all`.
    """
    ctx = _load_context(args)
    path = resolve_plan_for_context(ctx, args.name)
    return _run_logged_audit(
        lambda run_logger: _cmd_review_all_body(args, ctx, path, run_logger),
        args=args,
        ctx=ctx,
        plan_path=path,
        command="verify-all",
        flags={
            "mode": getattr(args, "mode", None),
            "dry_run": bool(getattr(args, "dry_run", False)),
            "max_steps": getattr(args, "max_steps", None),
        },
    )


def _cmd_review_all_body(
    args: argparse.Namespace, ctx, path: Path,
    run_logger: Optional[RunLogWriter],
) -> int:
    """``cmd_review_all``'s work, under the caller's open run log."""
    try:
        # One claude call per done step, all under this phase.
        with _audit_sink(run_logger, "review_sweep"):
            results = run_all_done_steps(
                path,
                repo_root=ctx.repo_root,
                mode=args.mode,
                max_steps=args.max_steps,
                dry_run=args.dry_run,
            )
    except LauncherError as exc:
        error(str(exc))
        return 2

    m = len(results)

    if args.dry_run:
        for result in results:
            print(_REVIEW_SEP)
            print(f"dry-run · step {result.step_id}: {result.step_title}")
            print(_REVIEW_SEP)
            print(result.stdout)
        return 0

    if m == 0:
        print(f"no done steps in '{args.name}' to review.")
        return 0

    print(_REVIEW_SEP)
    print(f"verify-all {args.name} · mode={args.mode} · {m} done steps")
    print(_REVIEW_SEP)

    verdicts: list[tuple[int, str, int]] = []
    _ra_color = color_enabled(sys.stdout)
    for result in results:
        print(
            "\n"
            + paint(
                f"Step {result.step_id}: {result.step_title}",
                BOLD,
                enabled=_ra_color,
            )
        )
        # Claude's report is markdown; render it console-friendly so
        # paths/commands inside stay clickable and copy-paste clean.
        output = result.stdout
        if result.exit_code != 0 and len(output) > _FAILED_REVIEW_OUTPUT_CAP:
            output = (
                f"[failure output truncated to last {_FAILED_REVIEW_OUTPUT_CAP} characters]\n"
                + output[-_FAILED_REVIEW_OUTPUT_CAP:]
            )
        print(render_markdown_for_console(output))
        if result.exit_code == 0:
            summary = summarize_findings(result.stdout)
            verdict_line = format_findings_verdict(
                result.step_id, summary
            )
            verdicts.append(
                (result.step_id, verdict_line, summary.critical)
            )

    passed = sum(1 for r in results if r.exit_code == 0)
    print(_REVIEW_SEP)
    print(f"summary: {passed} passed / {m} total")
    if verdicts:
        print("findings verdicts:")
        for _step_id, verdict_line, _critical in verdicts:
            print(f"  {verdict_line}")
    print(_REVIEW_SEP)

    # The review completed -- exit 0 regardless of critical findings or
    # individual step exits. The per-step reports and findings verdicts
    # above are what a caller acts on; the exit code only signals whether
    # verify-all itself ran (a LauncherError above returns 2).
    #
    # Opt-in CI gate: --fail-on-findings restores the prior blocking
    # threshold (any non-zero step exit OR any critical finding) as a
    # non-zero rc so a pipeline can stop on it.
    if getattr(args, "fail_on_findings", False):
        has_critical = any(critical > 0 for _, _, critical in verdicts)
        if passed != m or has_critical:
            return 1
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """``verify-all --rollup`` worker: reconcile rollup with pass/warn/fail.

    Intent: give a single roll-up verdict over every done step's
    reconcile, suitable for CI gates that parse the per-step
    ``[OK]/[WARN]/[FAIL]`` lines. Runs the per-step reconcile prompt
    and aggregates one verdict line per step rather than dumping raw
    reports. A completed rollup exits 0 even with failing steps — the
    verdict lives in the report, not the exit code; non-zero means
    the rollup itself couldn't run.

    ``--deep`` extends the rollup with per-acceptance-bullet
    verification (one extra claude call per bullet) — opt-in
    because the cost scales fast.

    Read-only — the rollup never flips a ``done`` step back to
    ``pending`` on a ``[FAIL]`` verdict. That's reserved for manual
    recovery; see RUNBOOK.md "verify reports a `[FAIL]`". Reached via
    :func:`cmd_verify_all` (the ``verify`` alias / ``--rollup``).
    """
    ctx = _load_context(args)
    path = resolve_plan_for_context(ctx, args.name)
    return _run_logged_audit(
        lambda run_logger: _cmd_verify_body(args, ctx, path, run_logger),
        args=args,
        ctx=ctx,
        plan_path=path,
        command="verify-all",
        flags={
            "rollup": True,
            "deep": bool(getattr(args, "deep", False)),
            "dry_run": bool(getattr(args, "dry_run", False)),
            "max_steps": getattr(args, "max_steps", None),
        },
    )


def _cmd_verify_body(
    args: argparse.Namespace, ctx, path: Path,
    run_logger: Optional[RunLogWriter],
) -> int:
    """``cmd_verify``'s work, under the caller's open run log."""
    try:
        # One reconcile call per done step (plus --deep's per-bullet calls),
        # all under this phase.
        with _audit_sink(run_logger, "verify_rollup"):
            verdicts = verify_plan(
                path,
                repo_root=ctx.repo_root,
                max_steps=args.max_steps,
                dry_run=args.dry_run,
                deep=args.deep,
            )
    except LauncherError as exc:
        error(str(exc))
        return 2

    if args.dry_run:
        # verify_plan in dry-run defers to run_all_done_steps which returns
        # rendered prompts in stdout. We print them as-is so the user can
        # inspect what would be sent.
        for v in verdicts:
            print(_REVIEW_SEP)
            print(f"dry-run · step {v.step_id}: {v.step_title}")
            print(_REVIEW_SEP)
            # In dry_run mode the underlying RunResult's stdout *is* the
            # prompt; verify_plan synthesizes a verdict line, but we
            # don't trust it for dry-run output. Skip it here.
        return 0

    if not verdicts:
        # Distinct from "every done step passed" — make the no-op
        # explicit so verify against a freshly-created plan doesn't read
        # exit 0 as confirmation that work was done.
        print(f"nothing to verify (no done steps in '{args.name}')")
        return 0

    label = "verify-all --rollup" + (" --deep" if args.deep else "")
    print(_REVIEW_SEP)
    print(f"{label} {args.name} · {len(verdicts)} done step(s)")
    print(_REVIEW_SEP)
    for v in verdicts:
        marker = {"pass": "[OK]", "warn": "[WARN]", "fail": "[FAIL]"}[v.status]
        print(f"{marker} {v.verdict_line}")
        # When --deep produced bullet results, show each so the user
        # sees per-criterion verdicts under the rolled-up step verdict.
        for br in v.bullet_results:
            sub_marker = {
                "PASS": "  [OK]",
                "FAIL": "  [FAIL]",
                "UNKNOWN": "  [WARN]",
            }.get(br.verdict, "  [WARN]")
            print(f"{sub_marker} {br.verdict}: {br.bullet}")

    n_pass = sum(1 for v in verdicts if v.status == "pass")
    n_warn = sum(1 for v in verdicts if v.status == "warn")
    n_fail = sum(1 for v in verdicts if v.status == "fail")
    print(_REVIEW_SEP)
    print(f"summary: {n_pass} pass / {n_warn} warn / {n_fail} fail")
    print(_REVIEW_SEP)
    # The rollup completed -- exit 0 even when steps failed. The per-step
    # [FAIL] lines and the summary are the verdict a caller reads; the
    # exit code only signals whether verify itself could run.
    #
    # Opt-in CI gate: --fail-on-findings makes any [FAIL] step exit
    # non-zero so a pipeline can stop on it.
    if getattr(args, "fail_on_findings", False) and n_fail > 0:
        return 1
    return 0


def cmd_verify_all(args: argparse.Namespace) -> int:
    """Read-only audit over every done step — ``verify-all`` (audit).

    One command, two shapes (``reconcile-*`` is reserved for plan-mutating
    verbs, so this read-only auditor lives under ``verify-``):

    - ``--mode <m>`` sweeps a read-only review mode (check / optimize /
      document / test / security / lint) across every done step and dumps
      the raw per-step reports — the former ``reconcile-all`` / ``review-all``.
    - ``--rollup`` [``--deep``] runs the reconcile prompt and aggregates one
      ``[OK]/[WARN]/[FAIL]`` verdict per step — the former ``verify`` command.

    ``--mode`` and ``--rollup`` are mutually exclusive; one is required. The
    deprecated ``verify`` alias defaults to ``--rollup`` so its prior
    behavior is preserved. Dispatches to :func:`cmd_review_all` (sweep) or
    :func:`cmd_verify` (rollup), which remain the workers.
    """
    mode = getattr(args, "mode", None)
    # The ``verify`` alias means the rollup; otherwise --rollup opts in.
    rollup = getattr(args, "rollup", False) or (
        args.command == "verify" and mode is None
    )
    if rollup and mode is not None:
        error(
            "--rollup (reconcile verdict) and --mode (review sweep) are "
            "mutually exclusive — pass one or the other"
        )
        return 2
    if rollup:
        return cmd_verify(args)
    if mode is None:
        error(
            "specify --mode <m> to sweep a review mode across done steps, "
            "or --rollup for the reconcile pass/warn/fail verdict"
        )
        return 2
    return cmd_review_all(args)


def register(subparsers) -> dict[str, Handler]:
    """Add the audit subparsers and return their command→handler dispatch map.

    ``reconcile-plan`` / ``reconcile-plan-walk`` / ``verify-all``
    declare ``parents=[yes_parent, ...]``; those parents originate in
    ``app.register``. Per the duplicate-then-defer rule, this command
    module — carved out before ``parser.py`` owns the shared parents —
    rebuilds its own verbatim copies (argparse ``parents=`` copies actions
    by reference, so identical parent objects yield byte-identical
    ``--help``). Consolidation into ``parser.py`` is deferred.
    ``AVAILABLE_MODES`` is imported lazily from the ``plan_tool.cli``
    package surface (not ``app``) so this module keeps no import edge to
    ``app``.
    """
    from plan_tool.cli import AVAILABLE_MODES

    sub = subparsers

    yes_parent = make_yes_parent()

    # Opt-in CI gate inherited by ``verify-all``. By default it
    # exits 0 once it completes -- the report carries the findings.
    # Passing this flag restores the command's own blocking threshold as
    # a non-zero exit (verify-all: a [FAIL] / critical finding) so
    # a CI step can gate on the rc. A run that couldn't complete still
    # exits non-zero regardless of this flag.
    fail_on_findings_parent = argparse.ArgumentParser(add_help=False)
    fail_on_findings_parent.add_argument(
        "--fail-on-findings",
        action="store_true",
        dest="fail_on_findings",
        help=(
            "exit non-zero when the audit's blocking findings are present "
            "(completeness: medium+; verify-all: a [FAIL] / critical "
            "finding; validate: INVALID). Off by default; intended for CI "
            "gates that stop the pipeline on findings."
        ),
    )

    p_review = sub.add_parser(
        "reconcile-plan",
        aliases=["reconcile", "review"],
        help="reconcile the plan against the current codebase (edits the plan)",
        parents=[yes_parent],
    )
    p_review.add_argument(
        "name",
        help="plan name — slug, filename stem (e.g. 1-my-feature), or filename.md",
    )
    review_scope = p_review.add_mutually_exclusive_group()
    review_scope.add_argument(
        "--step",
        type=int,
        default=None,
        help="reconcile one step by id (default: every step in the plan)",
    )
    review_scope.add_argument(
        "--all",
        action="store_true",
        help="reconcile every step in the plan (the explicit default scope)",
    )
    p_review.add_argument(
        "--dry-run",
        action="store_true",
        help="render the claude prompt and print it; do not invoke",
    )
    p_review.add_argument(
        "--refresh",
        action="store_true",
        dest="refresh",
        help=(
            "re-ground the plan against the current code instead of running "
            "a full audit. Gates the plan's grounding fingerprint against the "
            "code with NO claude call; on no drift exits fast (nothing to "
            "do). On drift, runs a reconcile scoped to exactly the changed "
            "files and saves the findings for 'reconcile-plan-walk'; it "
            "re-stamps the grounding sidecar ONLY when that reconcile is clean "
            "(pending findings leave the drift gate open until you apply them, "
            "so a re-run never masks the staleness). Contrast a plain audit (always "
            "spends claude) and 'create --reprocess' (fills placeholder text, "
            "no code involvement)."
        ),
    )
    p_review.add_argument(
        "--no-heuristic",
        action="store_true",
        dest="no_heuristic",
        help=(
            "skip the symbol-token 'looks already done' heuristic. "
            "File-existence, dep, and path-style checks still run; "
            "Claude's semantic review still fires. Use for plans whose "
            "step titles share tokens with existing code structurally "
            "(e.g., refactor plans)."
        ),
    )
    # Default ON for review: a plan legitimately authored before its
    # directories exist shouldn't be flagged MISSING_PARENT by an audit.
    # Pass --no-allow-missing-parent to demand parents already exist.
    p_review.add_argument(
        "--allow-missing-parent",
        action=argparse.BooleanOptionalAction,
        default=True,
        dest="allow_missing_parent",
        help=(
            "treat declared files whose parent directory is missing "
            "under the repo root as expected creators (NEW) instead of "
            "MISSING_PARENT. Silences the per-step warning and the "
            "plan-wide path-style hint; NEW-on-DONE, deps, heuristic, "
            "and the Claude review still fire. Default ON for review -- "
            "pass --no-allow-missing-parent to flag steps whose parent "
            "directories don't exist yet."
        ),
    )
    p_review.add_argument(
        "--no-save",
        action="store_true",
        dest="no_save",
        help=(
            "skip persisting the reconcile under "
            "<plan-dir>/plan-details/<slug>/reports/. By default each "
            "run is saved so 'plan-tool reconcile-plan-walk' can step "
            "through recommendations later. Pass this for one-off "
            "runs that shouldn't clutter the history."
        ),
    )
    p_review.add_argument(
        "--no-walk",
        action="store_true",
        dest="no_walk",
        help=(
            "skip the interactive walk after the report. By default, "
            "when stdin is a TTY and the review produced "
            "recommendations, plan-tool steps through them with "
            "(a)pply/(s)kip/(f)eedback/(q)uit prompts. Pass this for one-shot "
            "reviews or when piping output. Ordinary CI and non-TTY contexts "
            "skip the walk automatically; explicit PLAN_TOOL_HUMAN_IO=remote "
            "instead permits a restricted non-TTY (s)kip/(q)uit walk."
        ),
    )
    p_review.add_argument(
        "--include-info",
        action="store_true",
        dest="include_info",
        help=(
            "walk info-level findings too. By default the interactive "
            "walk skips them — these are the low-confidence heuristic "
            "hints that, on apply, dispatch a reconcile and usually land "
            "no edit (pure token spend). They are still saved to the "
            "reconcile JSON; pass this (or 'reconcile-plan-walk --include-info') to "
            "step through them."
        ),
    )
    p_review.add_argument(
        "--apply-structural",
        action="store_true",
        dest="apply_structural",
        help=(
            "let a recognized structural-directive finding actuate its "
            "bridge on apply instead of only recommending — a pairwise "
            "`merge` directive folds steps via detail.merge_bridge, a "
            "re-ground directive marks already-built steps done via "
            "reground.reground_bridge (both ride a `granularity-merge` "
            "finding, split by directive kind). Recommend-only without it. "
            "A merge directive stays visible under the default info hide, so "
            "--apply-structural alone reaches it; the re-ground directive keeps "
            "its --include-info requirement. Each bridge owns its own safety "
            "checks and TTY confirm; a blanket apply-all never auto-confirms a "
            "fold, an applied merge halts the walk (its renumber invalidates "
            "later saved ids), and a stale saved directive is blocked before "
            "any mutation."
        ),
    )
    p_review.add_argument(
        "--merge",
        action="store_true",
        dest="merge_remedy",
        help=(
            "enable only the merge bridge on apply (the granular counterpart "
            "to --apply-structural, which enables both bridges): a pairwise "
            "`merge` directive folds steps via detail.merge_bridge while a "
            "re-ground directive stays recommend-only. A blanket apply-all "
            "still forces recommend-only. See --apply-structural to enable "
            "both remedies at once."
        ),
    )
    p_review.add_argument(
        "--reground",
        action="store_true",
        dest="reground_remedy",
        help=(
            "enable only the re-ground bridge on apply (the granular "
            "counterpart to --apply-structural, which enables both bridges): a "
            "re-ground directive marks already-built steps done via "
            "reground.reground_bridge while a `merge` directive stays "
            "recommend-only. Still needs --include-info to surface the "
            "info-level re-ground finding at all, and a blanket apply-all still "
            "forces recommend-only. See --apply-structural to enable both "
            "remedies at once."
        ),
    )
    p_review.add_argument(
        "--reground-rebaseline",
        action="store_true",
        dest="reground_rebaseline",
        help=(
            "disposition selector (not a visibility or enable toggle): on "
            "apply, make an actuated re-ground ALSO write a `create "
            "--from-existing` re-baseline seed under docs/implementation-plans/plan-seeds/ for the "
            "flagged already-built steps, in addition to marking them done. "
            "The seed supersedes the plan's remaining scope, so re-create from "
            "it and retire this plan. Still needs the re-ground enabled "
            "(--reground or --apply-structural) and surfaced (--include-info); "
            "on its own it does nothing observable. Without it, an actuated "
            "re-ground only marks the steps done."
        ),
    )
    p_review.add_argument(
        "--lessons",
        action=argparse.BooleanOptionalAction,
        default=False,
        dest="lessons",
        help=(
            "capture lessons learned (default: off). When on, after "
            "the review produces recommendations, a second claude call "
            "distills new general lessons into "
            "~/.plan-tool/lessons/general.md and project-specific "
            "lessons into <repo_root>/.plan-tool/lessons/project.md. "
            "Off by default because it costs an extra claude call; "
            "pass --lessons to opt in. --no-lessons is the explicit "
            "form of the default."
        ),
    )
    p_review.add_argument(
        "--reuse",
        action=argparse.BooleanOptionalAction,
        default=None,
        dest="reuse",
        help=(
            "reuse a saved review's findings instead of running a fresh "
            "claude audit, when the save is eligible and fresh (plan AND "
            "code fingerprints still match). Eligibility is read from the "
            "loaded payload, not the filename: only an ordinary-final "
            "reconcile-plan review qualifies, so the newest-first lookup "
            "skips unreadable sidecars, pre-apply audit checkpoints, "
            "unknown-role payloads, and other kinds (completeness / "
            "reconcile) rather than walking their findings. Default "
            "(unset): prompt interactively, auto-accepting under --yes / "
            "non-TTY stdin — ordinary non-TTY reuse prints the saved findings "
            "and skips the per-finding walk, while explicit "
            "PLAN_TOOL_HUMAN_IO=remote permits a restricted (s)kip/(q)uit "
            "walk for promptable findings. --reuse always reuses an eligible "
            "fresh save; --no-reuse always re-audits. A stale save is never "
            "reused — it declines to a fresh review with a staleness note."
        ),
    )
    p_review.add_argument(
        "--reuse-id",
        default=None,
        dest="reuse_id",
        metavar="STEM",
        help=(
            "pin reuse to a specific saved review by filename stem (the "
            "bare `<ts>` form); default: the newest eligible save for this "
            "plan. The pin is exact: an unmatched stem, an unreadable file, "
            "and an ineligible payload (a checkpoint, an unknown role, or "
            "another kind) each print their own note and fall back to a "
            "fresh review — never to an older save."
        ),
    )

    # ``verify-all`` is the read-only done-step auditor (``reconcile-*`` is
    # reserved for plan-mutating verbs). Two shapes share one command:
    # ``--mode <m>`` sweeps a read-only mode across every done step and dumps
    # the raw reports; ``--rollup`` runs the reconcile prompt and aggregates a
    # per-step pass/warn/fail verdict (the former ``verify`` command, now a
    # deprecated alias that defaults to ``--rollup``). ``--deep`` extends the
    # rollup. ``--mode`` and ``--rollup`` are mutually exclusive.
    _review_modes = tuple(m for m in AVAILABLE_MODES if m not in MUTATING_MODES)
    p_review_all = sub.add_parser(
        "verify-all",
        aliases=["reconcile-all", "review-all", "verify"],
        help=(
            "audit every done step (read-only): --mode sweeps a review mode "
            "and dumps reports; --rollup prints a per-step pass/warn/fail "
            "verdict"
        ),
        parents=[yes_parent, fail_on_findings_parent],
    )
    p_review_all.add_argument(
        "name",
        help="plan name — slug, filename stem (e.g. 1-my-feature), or filename.md",
    )
    p_review_all.add_argument(
        "--mode",
        choices=_review_modes,
        default=None,
        help=(
            "read-only review mode to sweep across every done step "
            "(dumps raw per-step reports). Mutually exclusive with "
            "--rollup; one of the two is required (the 'verify' alias "
            "defaults to --rollup)."
        ),
    )
    p_review_all.add_argument(
        "--rollup",
        action="store_true",
        help=(
            "run the reconcile prompt across done steps and print one "
            "[OK]/[WARN]/[FAIL] verdict per step instead of raw reports "
            "(the former 'verify' command). Mutually exclusive with --mode."
        ),
    )
    p_review_all.add_argument(
        "--deep",
        action="store_true",
        help=(
            "with --rollup, check every acceptance-criteria bullet from "
            "each step's detail file individually (one extra claude call "
            "per bullet; opt-in due to cost)"
        ),
    )
    p_review_all.add_argument(
        "--max-steps",
        type=int,
        default=None,
        dest="max_steps",
        metavar="N",
        help="limit to the last N done steps (default: all)",
    )
    p_review_all.add_argument(
        "--dry-run",
        action="store_true",
        help="render prompts and print them; do not invoke claude",
    )

    # ``reconcile-plan-walk`` walks and applies the saved findings from a
    # reconcile run without re-running the audit. Although it is named for
    # ``reconcile-plan`` (its primary producer), it is kind-agnostic: it also
    # replays ``reconcile-code`` / ``detail --reconcile`` / automatic
    # drift-reconcile findings. Legacy names ``reconcile-walk`` /
    # ``review-walk`` remain as deprecated aliases.
    p_review_walk = sub.add_parser(
        "reconcile-plan-walk",
        aliases=["reconcile-walk", "review-walk"],
        help=(
            "walk and apply the findings from a saved reconcile (any kind: "
            "reconcile-plan / reconcile-code / detail --reconcile), no claude "
            "call; loads the newest eligible final save for <name> by default"
        ),
        parents=[yes_parent],
    )
    p_review_walk.add_argument(
        "name",
        help="plan name — slug, filename stem (e.g. 1-my-feature), or filename.md",
    )
    p_review_walk.add_argument(
        "--id",
        default=None,
        metavar="STEM",
        help=(
            "load exactly one final saved reconcile by a listed filename stem "
            "or basename in the selected plan's reports directory (e.g. "
            "20260505-123456); path-bearing, missing, ambiguous, unreadable, "
            "and non-final ids exit 2 without fallback; default: newest "
            "eligible final"
        ),
    )
    p_review_walk.add_argument(
        "--rewalk",
        action="store_true",
        help=(
            "re-prompt items that already have annotations (default: "
            "skip already-annotated items)"
        ),
    )
    p_review_walk.add_argument(
        "--include-info",
        action="store_true",
        dest="include_info",
        help=(
            "walk info-level findings too (default: skip them — the "
            "low-confidence heuristic hints that usually land no edit "
            "on apply). They remain in the saved reconcile either way."
        ),
    )
    p_review_walk.add_argument(
        "--apply-structural",
        action="store_true",
        dest="apply_structural",
        help=(
            "let a recognized structural-directive finding actuate its "
            "bridge on apply instead of only recommending — a pairwise "
            "`merge` directive folds steps via detail.merge_bridge, a "
            "re-ground directive marks already-built steps done via "
            "reground.reground_bridge (both ride a `granularity-merge` "
            "finding, split by directive kind). Recommend-only without it. "
            "A merge directive stays visible under the default info hide, so "
            "--apply-structural alone reaches it; the re-ground directive keeps "
            "its --include-info requirement. Each bridge owns its own safety "
            "checks and TTY confirm; a blanket apply-all never auto-confirms a "
            "fold, an applied merge halts the walk (its renumber invalidates "
            "later saved ids), and a stale saved directive is blocked before "
            "any mutation."
        ),
    )
    p_review_walk.add_argument(
        "--merge",
        action="store_true",
        dest="merge_remedy",
        help=(
            "enable only the merge bridge on apply (the granular counterpart "
            "to --apply-structural, which enables both bridges): a pairwise "
            "`merge` directive folds steps via detail.merge_bridge while a "
            "re-ground directive stays recommend-only. A blanket apply-all "
            "still forces recommend-only. See --apply-structural to enable "
            "both remedies at once."
        ),
    )
    p_review_walk.add_argument(
        "--reground",
        action="store_true",
        dest="reground_remedy",
        help=(
            "enable only the re-ground bridge on apply (the granular "
            "counterpart to --apply-structural, which enables both bridges): a "
            "re-ground directive marks already-built steps done via "
            "reground.reground_bridge while a `merge` directive stays "
            "recommend-only. Still needs --include-info to surface the "
            "info-level re-ground finding at all, and a blanket apply-all still "
            "forces recommend-only. See --apply-structural to enable both "
            "remedies at once."
        ),
    )
    p_review_walk.add_argument(
        "--reground-rebaseline",
        action="store_true",
        dest="reground_rebaseline",
        help=(
            "disposition selector (not a visibility or enable toggle): on "
            "apply, make an actuated re-ground ALSO write a `create "
            "--from-existing` re-baseline seed under docs/implementation-plans/plan-seeds/ for the "
            "flagged already-built steps, in addition to marking them done. "
            "The seed supersedes the plan's remaining scope, so re-create from "
            "it and retire this plan. Still needs the re-ground enabled "
            "(--reground or --apply-structural) and surfaced (--include-info); "
            "on its own it does nothing observable. Without it, an actuated "
            "re-ground only marks the steps done."
        ),
    )

    # Canonical names: ``reconcile-plan`` (plan-mutating audit),
    # ``reconcile-plan-walk`` (walk + apply saved findings), ``verify-all``
    # (read-only done-step audit). Every other key is a hidden deprecated
    # alias. argparse routes an alias to the same subparser but sets
    # ``args.command`` to the name as typed, so each alias needs its own
    # dispatch entry mapping to the same handler. The package-surface test
    # asserts ``set(dispatch) == choices`` (aliases included).
    # ``verify``/``reconcile-all``/``review-all`` all resolve to
    # ``cmd_verify_all``, which branches on ``--rollup`` (and treats the
    # ``verify`` alias as implying it).
    return {
        "reconcile-plan": cmd_review,
        "reconcile": cmd_review,
        "review": cmd_review,
        "reconcile-plan-walk": cmd_review_walk,
        "reconcile-walk": cmd_review_walk,
        "review-walk": cmd_review_walk,
        "verify-all": cmd_verify_all,
        "reconcile-all": cmd_verify_all,
        "review-all": cmd_verify_all,
        "verify": cmd_verify_all,
    }
