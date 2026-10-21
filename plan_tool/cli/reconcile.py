"""Reconcile-engine internals shared by the run / detail / review verbs.

A non-command leaf module: it registers no subparsers and is absent from
``app.COMMAND_MODULES``. The ``run``, ``detail --reconcile`` and ``review``
handlers call this engine as a library -- carving it out here breaks the
import cycle that a per-command home would re-create.

Holds the three saved-reconcile reuse families (find / ask / prompt / walk
for ``reconcile`` / ``detail_reconcile`` / ``run_reconcile``), the
``_iterate_reconcile_loop`` convergence driver, the reconcile-phase walk
wrappers, and the drift-halt / scope-guard / auto-reconcile emitters.

``_build_review_action_fn`` is imported at module top; the reverse edge
(:mod:`plan_tool.cli.review_actions` -> this module) resolves lazily inside
the action closures, so the two-module cycle is broken one-directionally
and this stays the upper of the two leaves.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Optional

if TYPE_CHECKING:
    from plan_tool.scope_guard import ReconcileScopeGuard

from plan_tool.convergence import (
    ConvergenceState,
    IterativeBudget,
    is_blocking_impact,
    record_iteration,
    should_continue,
    touch,
)
from plan_tool.detail_artifacts import (
    DetailFormatError,
    require_supported_detail_format_version,
    resolve_detail_artifact,
)
from plan_tool.launcher import (
    FindingsSummary,
    LauncherError,
    findings_output_is_valid,
    format_findings_verdict,
    resolve_step,
    run_step,
    selected_reconcile_plan_fingerprint_changed,
    summarize_findings,
)
from plan_tool.fingerprint import compute_code_fingerprint, diff_code_fingerprint
from plan_tool.locator import PlanToolContext
from plan_tool.parser import (
    ParseError,
    ValidationError,
    parse_plan,
)
from plan_tool.review_persistence import (
    ReviewLoadError,
    SavedReview,
    compute_plan_fingerprint,
    list_saved_reviews,
    load_review,
    save_review,
)
from plan_tool.review import confidence_label
from plan_tool.review_walk import (
    WalkState,
    stamp_target_signatures,
    walk_recommendations,
)
from plan_tool.run_log import RunLogWriter
from plan_tool.schema import ChangeType, Plan, Step, StepStatus
from plan_tool.pathutil import literal_path, normalize_declared_path
from plan_tool.style import error, info, tool
from plan_tool.telemetry_analysis import build_low_impact_demotion_lookup
from plan_tool.cli.console import _format_relative_age
from plan_tool.cli.review_actions import _build_review_action_fn


# --------------------------------------------------------------------------
# Saved-reconcile reuse engine — one kind-descriptor family
# --------------------------------------------------------------------------
#
# The two reconcile directions (``detail-reconcile``, ``run-reconcile``)
# share one find/ask/prompt/walk machinery that differs only along the axes
# captured by ``ReconcileKind``. The four parametrized cores below do the
# work; the named wrappers further down stay bound as one-line delegators so
# by-name imports (``from plan_tool.cli import _walk_saved_run_reconcile``)
# keep resolving. Adding a direction is one ``_RECONCILE_KINDS`` row.


@dataclass(frozen=True)
class ReconcileKind:
    """Every axis on which the three saved-reconcile families diverge.

    ``noun`` is the label substituted into all operator-facing wording.
    ``accepted_kinds`` / ``name_includes`` / ``name_excludes`` select which
    on-disk saves a lookup will match. ``honor_no_walk_no_save`` is the
    prompt-suppression policy. ``phase_kind`` is the ``saved_reconcile_reuse``
    phase tag (omitted from the event when ``None``). ``walk_verb`` /
    ``empty_message`` are the walk's two distinct lines, and
    ``replay_redirects_only`` selects the walk strategy (interactive walk vs
    redirect-only replay).
    """

    noun: str
    accepted_kinds: frozenset
    name_includes: str
    name_excludes: tuple
    honor_no_walk_no_save: bool
    phase_kind: Optional[str]
    walk_verb: str
    empty_message: str
    replay_redirects_only: bool


@dataclass(frozen=True)
class CompletedSiblingContext:
    """Ownership evidence supplied to a selected fresh code reconciliation.

    The selected step's own detail and footprint remain the reconciliation
    contract. This records only completed siblings' *non-shared* normalized
    declared paths. It does not inspect sibling details or make broader
    ownership claims.
    """

    prompt: str
    contextual_sibling_count: int
    completed_sibling_count: int = 0


@dataclass(frozen=True)
class SelectedRunReconcileSnapshot:
    """One selected target, its readable detail, and its plan fingerprint."""

    plan: Plan
    step: Step
    plan_fingerprint: str


ReconcileSweepOutcome = Literal["audited", "reused", "rendered", "skipped"]


@dataclass
class ReconcileSweepProgress:
    """Counts the distinct outcomes of a code-reconcile sweep."""

    audited: int = 0
    reused: int = 0
    rendered: int = 0
    skipped: int = 0

    def record(self, outcome: Optional[ReconcileSweepOutcome]) -> None:
        if outcome is None:
            return
        if outcome == "audited":
            self.audited += 1
        elif outcome == "reused":
            self.reused += 1
        elif outcome == "rendered":
            self.rendered += 1
        elif outcome == "skipped":
            self.skipped += 1
        else:
            raise ValueError(f"unknown reconcile sweep outcome: {outcome}")


@dataclass(frozen=True)
class ReconcileStepResult:
    """The outcome a single code-reconcile invocation reports to a sweep."""

    rc: int
    outcome: Optional[ReconcileSweepOutcome] = None


_RECONCILE_PLAN_READ_ERRORS = (ParseError, ValidationError, OSError)


def _try_parse_reconcile_plan(plan_path: Path) -> tuple[Optional[Plan], Optional[str]]:
    """Read a plan for a best-effort reconcile preflight."""
    try:
        return parse_plan(plan_path), None
    except _RECONCILE_PLAN_READ_ERRORS as exc:
        return None, str(exc)


def _load_reconcile_sweep_step(
    plan_path: Path, step_id: int
) -> tuple[Optional[Plan], Optional[Step], Optional[str]]:
    """Read the current plan and locate one sweep target."""
    plan, parse_error = _try_parse_reconcile_plan(plan_path)
    if plan is None:
        return None, None, parse_error
    return plan, next((step for step in plan.steps if step.id == step_id), None), None


def _build_completed_sibling_context(
    plan: Plan, selected_step: Step
) -> CompletedSiblingContext:
    """Render completed sibling ownership outside ``selected_step``'s scope.

    A sibling's shared files intentionally stay out of this block: they are
    still subject to the selected step's canonical reconciliation. Only the
    normalized declared paths participate; sibling detail is irrelevant.
    """
    selected_paths = {
        normalized
        for path in selected_step.all_files
        if (normalized := normalize_declared_path(path))
    }
    siblings = [
        step
        for step in plan.steps
        if step.id != selected_step.id and step.status is StepStatus.DONE
    ]
    if not siblings:
        return CompletedSiblingContext("", 0, completed_sibling_count=0)

    entries: list[str] = []
    for sibling in siblings:
        seen_paths: set[str] = set()
        sibling_only_paths = []
        for path in sibling.all_files:
            normalized = normalize_declared_path(path)
            if (
                normalized
                and normalized not in selected_paths
                and normalized not in seen_paths
            ):
                sibling_only_paths.append(normalized)
                seen_paths.add(normalized)
        if not sibling_only_paths:
            # Every sibling path is shared with the selected step, so the
            # selected contract must remain able to report a real mismatch.
            continue

        entry = [
            f'### Completed step {sibling.id} — {sibling.title}',
            "Declared sibling-owned paths outside the selected footprint:",
            *[f"- `{path}`" for path in sibling_only_paths],
        ]
        entries.append("\n".join(entry))

    if not entries:
        return CompletedSiblingContext("", 0, completed_sibling_count=len(siblings))

    sections = [
        "## Completed sibling ownership context — higher-priority rule",
        (
            "Completed sibling-owned paths outside the selected footprint are "
            "context only. Do not call them selected-step drift or recommend "
            "removing them merely because they are outside the selected step's "
            "declared files. Continue to report genuine selected-step mismatches, "
            "including mismatches in shared files. This rule takes precedence "
            "over the general cross-cutting-drift instruction."
        ),
        "\n\n".join(entries),
    ]
    return CompletedSiblingContext(
        prompt="\n\n".join(sections),
        contextual_sibling_count=len(entries),
        completed_sibling_count=len(siblings),
    )


def _read_selected_run_reconcile_detail(
    plan_path: Path,
    plan: Plan,
    step: Step,
    repo_root: Path,
) -> None:
    """Require the selected run-grade detail before prompt assembly."""
    resolution = resolve_detail_artifact(plan_path, plan, step, repo_root)
    if not resolution.on_disk:
        raise LauncherError(
            f"selected step {step.id} ({step.title}) needs a readable detail "
            f"at `{resolution.path}` before run-reconcile"
        )
    try:
        text = resolution.path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise LauncherError(
            f"selected step {step.id} ({step.title}) has unreadable detail "
            f"at `{resolution.path}`: {exc}"
        ) from exc
    try:
        require_supported_detail_format_version(text, path=resolution.path)
    except DetailFormatError as exc:
        raise LauncherError(
            f"selected step {step.id} ({step.title}): {exc}"
        ) from exc


def _verify_selected_run_reconcile_snapshot(
    plan_path: Path,
    plan: Plan,
    step: Step,
    repo_root: Path,
) -> SelectedRunReconcileSnapshot:
    """Validate and fingerprint one already-parsed selected reconcile input."""
    if step.status is not StepStatus.DONE:
        raise LauncherError(
            f"selected step {step.id} ({step.title}) must be DONE for "
            f"run-reconcile (status: {step.status.value})"
        )
    _read_selected_run_reconcile_detail(plan_path, plan, step, repo_root)
    return SelectedRunReconcileSnapshot(
        plan=plan,
        step=step,
        plan_fingerprint=compute_plan_fingerprint(plan_path),
    )


def _load_selected_run_reconcile_snapshot(
    plan_path: Path,
    step_id: int,
    repo_root: Path,
) -> SelectedRunReconcileSnapshot:
    """Parse, select, validate, and fingerprint one fresh reconcile input."""
    plan, parse_error = _try_parse_reconcile_plan(plan_path)
    if plan is None:
        raise LauncherError(parse_error or "could not read plan")
    try:
        step = resolve_step(plan, step_id)
    except LauncherError as exc:
        raise LauncherError(f"selected run-reconcile target: {exc}") from exc
    return _verify_selected_run_reconcile_snapshot(
        plan_path, plan, step, repo_root
    )


def _format_completed_sibling_context_report(
    verdict: str,
    summary: FindingsSummary,
    context: CompletedSiblingContext,
) -> str:
    """Add a durable ownership/outcome note to a run-reconcile save."""
    if context.contextual_sibling_count:
        context_line = (
            "Completed-sibling context informed this classification: "
            f"{context.contextual_sibling_count} of {context.completed_sibling_count} "
            "completed sibling step(s) supplied non-shared declared paths."
        )
    elif context.completed_sibling_count:
        context_line = (
            "Completed-sibling context: "
            f"{context.completed_sibling_count} completed sibling step(s) "
            "existed but none supplied non-shared declared paths."
        )
    else:
        context_line = (
            "Completed-sibling context: no other completed steps were "
            "available for this selected reconciliation."
        )

    if not summary.parsed:
        outcome = (
            "Selected-step outcome: scoped — the backend emitted no parseable "
            "findings block, so no clean or drift verdict is claimed."
        )
    elif summary.total:
        outcome = (
            "Selected-step outcome: selected-step drift was reported in "
            f"{summary.total} finding(s)."
        )
    else:
        outcome = "Selected-step outcome: clean — no selected-step drift was reported."
    return "\n\n".join(
        part for part in (verdict, context_line, outcome) if part
    )


_RECONCILE_KINDS: dict[str, ReconcileKind] = {
    "detail-reconcile": ReconcileKind(
        noun="detail-reconcile",
        accepted_kinds=frozenset({"detail-reconcile"}),
        name_includes="-detail-reconcile",
        name_excludes=(),
        # The detail subparser defines neither ``--no-walk`` nor ``--no-save``
        # (the detail-reconcile path always persists + walks).
        honor_no_walk_no_save=False,
        phase_kind="detail-reconcile",
        walk_verb="Walking",
        empty_message=(
            "(saved detail-reconcile has no recommendations to walk)"
        ),
        replay_redirects_only=False,
    ),
    "run-reconcile": ReconcileKind(
        noun="run-reconcile",
        accepted_kinds=frozenset({"run-reconcile"}),
        name_includes="-run-reconcile",
        name_excludes=(),
        honor_no_walk_no_save=True,
        phase_kind="run-reconcile",
        walk_verb="Replaying",
        # Note: no trailing "to walk" — run-reconcile replays redirects, it
        # never enters the interactive walk.
        empty_message="(saved run-reconcile has no recommendations)",
        replay_redirects_only=True,
    ),
}


@dataclass
class ReusableReconcile:
    """A located saved reconcile sidecar plus its freshness verdict.

    The reconcile-family sibling of
    :class:`plan_tool.completeness_report.ReusableAudit`, minus that type's
    correctness/conceptual axis split (reconcile saves are single-axis).
    Produced by :func:`resolve_reusable_reconcile`. ``fresh`` is the headline
    (``plan_match and code_match``); ``plan_match`` / ``code_match`` are
    exposed separately so a consumer can tell plan-side staleness, code
    *content* staleness (``drifted_code`` non-empty), and footprint membership
    churn (``footprint_added`` / ``footprint_removed`` — never a content-drift
    reconcile note). ``drifted_code`` is absolute, resolved, sorted content
    digest changes only.
    """

    saved: SavedReview  # the loaded sidecar (carries both fingerprints)
    fresh: bool  # plan_match and code_match
    plan_match: bool  # saved plan fingerprint non-empty and == current
    code_match: bool  # code fingerprint present and saved→current maps identical
    drifted_code: list[Path]  # abs resolved sorted paths with content digest changes
    footprint_added: list[Path] = field(default_factory=list)
    footprint_removed: list[Path] = field(default_factory=list)


def resolve_reusable_reconcile(
    plan_name: str,
    repo_root: Path,
    *,
    plan_path: Path,
    review_id: Optional[str] = None,
    kind_filter: str,
) -> Optional[ReusableReconcile]:
    """Locate the newest reconcile sidecar of ``kind_filter`` (or the one
    pinned by ``review_id``), recompute both fingerprints against current
    disk, and return a :class:`ReusableReconcile` freshness verdict — or
    ``None`` when no sidecar resolves.

    The reconcile-family analog of
    :func:`plan_tool.completeness_report.resolve_reusable_audit`: it reuses
    :func:`compute_plan_fingerprint`, :func:`compute_code_fingerprint`, and
    the :func:`list_saved_reviews` locator rather than re-globbing or
    re-hashing. It issues zero Claude calls and reads only from disk.

    ``kind_filter`` names a key in :data:`_RECONCILE_KINDS`
    (``"detail-reconcile"`` or ``"run-reconcile"``); its descriptor's
    ``name_includes`` / ``name_excludes`` / ``accepted_kinds`` single-source
    the suffix match with the live :func:`_find_saved_for_step` machinery.
    ``plan_name`` threads straight through as the ``plan_slug`` the
    persistence locators key on.

    ``review_id`` pins a specific sidecar by stem — the bare ``<ts>`` or the
    full ``<ts>-<kind_filter>`` form. An unresolvable id returns ``None``.
    Without an id, the newest matching sidecar wins.

    Freshness gates on the saved ``code_fingerprint_present`` marker, never
    on ``code_fingerprint`` dict-truthiness: a never-computed (legacy)
    capture is stale, while a computed-but-empty map (no in-scope code
    surface) stays reusable on a plan-only match. The saved→current code
    diff is deletion-aware — unlike the live-edit
    :func:`plan_tool.drift_detection.check_drift`, a file hashed at save time
    that has since vanished is genuine staleness across the save/reload
    boundary.

    Scope note: this picks the newest kind-matching sidecar *plan-wide*
    (matching ``resolve_reusable_audit``'s scope), so the returned
    ``SavedReview`` may belong to a different ``step_id`` than the one being
    reconciled. A consumer that replays these findings MUST filter to the
    current ``step_id`` first — see the live :func:`_find_saved_for_step`,
    which carries that filter.
    """
    kind = _RECONCILE_KINDS[kind_filter]
    candidates = [
        p
        for p in list_saved_reviews(plan_name, repo_root, plan_path=plan_path)
        if kind.name_includes in p.name
        and not any(excl in p.name for excl in kind.name_excludes)
    ]
    if review_id is not None:
        wanted = {review_id, f"{review_id}-{kind_filter}"}
        candidates = [p for p in candidates if p.stem in wanted]
    if not candidates:
        return None
    try:
        saved = load_review(candidates[0])
    except ReviewLoadError:
        return None
    if saved.kind not in kind.accepted_kinds:
        return None

    # --- Plan verdict --------------------------------------------------
    current_plan_fp = compute_plan_fingerprint(plan_path)
    plan_match = bool(saved.plan_fingerprint) and (
        saved.plan_fingerprint == current_plan_fp
    )

    # --- Code verdict (content vs footprint membership) ----------------
    if not saved.code_fingerprint_present:
        # Legacy/never-computed capture: no baseline to diff against, so
        # every current file would be a spurious `new` key. Stale, no drift.
        code_match = False
        drifted_code: list[Path] = []
        footprint_added: list[Path] = []
        footprint_removed: list[Path] = []
    else:
        plan = parse_plan(plan_path)
        current_code_fp = compute_code_fingerprint(plan, plan_path, repo_root)
        code_diff = diff_code_fingerprint(
            saved.code_fingerprint, current_code_fp, repo_root
        )
        code_match = code_diff.match
        # Content-only for reconcile messaging — footprint membership is
        # plan metadata churn, not a reconcile-plan trigger.
        drifted_code = list(code_diff.content_drifted)
        footprint_added = list(code_diff.footprint_added)
        footprint_removed = list(code_diff.footprint_removed)

    return ReusableReconcile(
        saved=saved,
        fresh=plan_match and code_match,
        plan_match=plan_match,
        code_match=code_match,
        drifted_code=drifted_code,
        footprint_added=footprint_added,
        footprint_removed=footprint_removed,
    )


def _find_saved_for_step(
    kind: ReconcileKind,
    plan_slug: str,
    repo_root: Path,
    *,
    step_id: int,
    plan_path: Optional[Path] = None,
    reuse_id: Optional[str] = None,
):
    """Return ``(path, SavedReview)`` for the newest save of ``kind``
    matching ``step_id``, or ``None`` when none exists or can be loaded.

    Reconcile saves are step-specific (the JSON's ``step_id`` field
    identifies the audited step); a save for step 3 is not relevant when
    the caller is now reconciling step 5. ``list_saved_reviews`` returns
    newest-first, so the first candidate passing the filename pre-filter
    (``name_includes`` present, no ``name_excludes`` substring) and the
    ``accepted_kinds`` check is the freshest match.

    ``reuse_id`` pins the lookup to a specific sidecar by filename stem —
    the bare ``<ts>`` or the full ``<ts>-<kind.noun>`` form (mirrors
    :func:`resolve_reusable_reconcile`'s id-match). A set ``reuse_id`` that
    matches no candidate returns ``None`` so the caller can distinguish a
    pinned miss (warn-and-proceed) from "no save on file".
    """
    from plan_tool.review_persistence import (
        list_saved_reviews,
        ReviewLoadError as _RLE,
    )

    candidates = list_saved_reviews(plan_slug, repo_root, plan_path=plan_path)
    if not candidates:
        return None
    wanted = (
        {reuse_id, f"{reuse_id}-{kind.noun}"} if reuse_id is not None else None
    )
    for p in candidates:
        if kind.name_includes not in p.name:
            continue
        if any(excl in p.name for excl in kind.name_excludes):
            continue
        if wanted is not None and p.stem not in wanted:
            continue
        try:
            saved = load_review(p)
        except _RLE:
            continue
        if saved.kind in kind.accepted_kinds and saved.step_id == step_id:
            return (p, saved)
    return None


def _ask_reuse_saved(
    kind: ReconcileKind,
    saved_path: Path,
    saved,
    plan_slug: str,
    *,
    repo_root: Path,
    input_fn=None,
) -> bool:
    """Print the saved review's metadata, prompt the user to reuse it.

    Returns True on ``y`` / ``yes``, False otherwise (default no — the
    saved review can be stale after code changes, so reuse is opt-in). The
    ``kind.noun`` is named explicitly so the operator can tell which
    direction they're replaying when several kinds exist for the same step.
    """
    n_recs = len(saved.recommendations)
    n_annotated = len(saved.annotations)
    age = _format_relative_age(saved.created_at)
    try:
        rel = saved_path.relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        rel = str(saved_path)
    print(
        f"\nA saved {kind.noun} for {plan_slug!r} step {saved.step_id} "
        f"exists ({age}, {n_recs} rec(s), {n_annotated} annotated):"
    )
    print(f"  {rel}")
    if input_fn is None:
        # Look up ``builtins.input`` at call time so monkeypatch in tests
        # is honored.
        import builtins
        input_fn = builtins.input
    answer = input_fn(
        f"Walk that one instead of running a fresh {kind.noun}? [y/N] "
    ).strip().lower()
    return answer in ("y", "yes")


def _prompt_reuse_saved(
    kind: ReconcileKind,
    ctx: PlanToolContext,
    plan_slug: str,
    args: argparse.Namespace,
    *,
    step_id: int,
    input_fn=None,
    plan_path: Optional[Path] = None,
) -> Optional[Path]:
    """Offer to walk a saved review of ``kind`` instead of a fresh claude run.

    Suppressed under ``--dry-run`` and under ``--no-walk`` / ``--no-save``
    when ``kind.honor_no_walk_no_save`` is set (the detail direction defines
    neither flag). Returns the saved path when reuse is accepted, ``None``
    otherwise.

    The ``--reuse`` / ``--no-reuse`` / ``--reuse-id`` tri-state (read via
    ``getattr`` so the same core serves the run namespace, where the flags
    are declared, and the detail namespace, where they are absent and
    default to ``None``) mirrors ``completeness-audit``'s ``--reuse-audit``
    family:

    - ``--no-reuse`` (``reuse is False``) — never look up a sidecar.
    - ``--reuse-id STEM`` — pin the lookup to one save by filename stem; an
      unresolvable stem warns and proceeds to a fresh audit.
    - the freshness gate declines any stale save to a fresh audit.
    - on a fresh save: ``--reuse`` accepts with no prompt; the unset default
      auto-accepts under ``--yes`` / non-TTY stdin and otherwise prompts.
    """
    if args.dry_run:
        return None
    if kind.honor_no_walk_no_save and (
        getattr(args, "no_walk", False) or getattr(args, "no_save", False)
    ):
        return None

    # --no-reuse never even looks up a sidecar (hard opt-out, before any
    # disk read). Mirrors completeness_cmd._resolve_audit_reuse step 1.
    reuse = getattr(args, "reuse", None)
    if reuse is False:
        return None
    reuse_id = getattr(args, "reuse_id", None)

    matched = _find_saved_for_step(
        kind, plan_slug, ctx.repo_root,
        step_id=step_id, plan_path=plan_path, reuse_id=reuse_id,
    )
    if matched is None:
        # A pinned --reuse-id that resolves to nothing warns and proceeds to
        # a fresh audit (never a non-zero exit); an unpinned miss is the
        # normal first-run path.
        if reuse_id is not None:
            error(
                f"no saved {kind.noun} matched --reuse-id {reuse_id!r}; "
                f"running a fresh {kind.noun}"
            )
        return None

    saved_path, saved = matched

    # --- Fingerprint-freshness gate -----------------------------------
    # Offer reuse only when the located sidecar still describes disk
    # (saved plan- AND code-fingerprint == current). A stale save declines
    # to a fresh audit (return None) — never a non-zero exit. The gate
    # precedes BOTH the --yes fast path and the interactive prompt, so
    # --yes accepts only a fresh save. Best-effort: a malformed plan or a
    # read failure drops to a fresh audit rather than crashing the command.
    if plan_path is None:
        return None
    try:
        ru = resolve_reusable_reconcile(
            plan_slug,
            ctx.repo_root,
            plan_path=plan_path,
            review_id=saved_path.stem,
            kind_filter=kind.noun,
        )
    except _RECONCILE_PLAN_READ_ERRORS:
        return None
    if ru is None:
        return None
    if not ru.fresh:
        # A deletion from an otherwise unchanged plan remains attributable to
        # the step that declares it, but it is footprint membership rather
        # than a content edit. Keep those messages and their follow-up hints
        # separate; only real content drift warrants reconcile guidance.
        removed_code = []
        if ru.plan_match:
            removed_code = list(ru.footprint_removed)
        if not ru.code_match and (ru.drifted_code or removed_code):
            drifted_plan, _ = _try_parse_reconcile_plan(plan_path)
            if drifted_plan is not None:
                if ru.drifted_code:
                    _note_reuse_code_drift(
                        ru.drifted_code, drifted_plan, ctx.repo_root
                    )
                if removed_code:
                    _note_reuse_removed_code_files(
                        removed_code, drifted_plan, ctx.repo_root
                    )
        elif not ru.code_match and (
            ru.footprint_added or ru.footprint_removed
        ):
            info(
                f"saved {kind.noun} for step {saved.step_id} is stale "
                f"(plan footprint changed: {len(ru.footprint_added)} added, "
                f"{len(ru.footprint_removed)} removed since {saved.created_at}); "
                f"running fresh"
            )
        elif not ru.plan_match:
            info(
                f"saved {kind.noun} for step {saved.step_id} is stale "
                f"(plan changed since {saved.created_at}); running fresh"
            )
        return None

    # --- Fresh-save dispatch by flag ----------------------------------
    # The gate above confirmed the located save still matches disk.
    #   --reuse                 → accept with no prompt (explicit force).
    #   unset + --yes/non-TTY   → auto-accept a fresh save (non-interactive).
    #   unset + TTY             → interactive prompt.
    yes = getattr(args, "yes", False)
    if reuse is True or yes or not sys.stdin.isatty():
        n_recs = len(saved.recommendations)
        age = _format_relative_age(saved.created_at)
        try:
            rel = saved_path.relative_to(ctx.repo_root.resolve()).as_posix()
        except ValueError:
            rel = str(saved_path)
        prefix = "(--yes)" if yes else "(--reuse)" if reuse is True else "(reuse)"
        print(
            f"\n{prefix} walking saved {kind.noun} for {plan_slug!r} "
            f"step {saved.step_id} ({age}, {n_recs} rec(s)): {rel}"
        )
        return saved_path
    if not _ask_reuse_saved(
        kind, saved_path, saved, plan_slug,
        repo_root=ctx.repo_root, input_fn=input_fn,
    ):
        return None
    return saved_path


def _note_reuse_code_drift(
    drifted_code, plan, repo_root, *, loop_name: str = "reconcile",
) -> None:
    """Attributed staleness note for a code-drifted reconcile save.

    Lists the drifted code files grouped by owning step (the step's
    ``N: title`` printed once as a header) via
    :func:`_print_grouped_drift_files`, then closes with the
    ``detail --reconcile`` recovery hint. A detected code change that
    re-runs the audit is normal operation, not a problem, so it emits at
    info level (no revert, no rc change). Shared by the reconcile core
    (same module) and ``review_cmd``'s plan-wide review gate. The
    ``detail --reconcile`` hint is correct *here* — this is the reconcile
    audit's own sidecar, which that command refreshes. Contrast
    ``completeness_cmd._note_code_drift``, which prints no hint: its
    staleness is on the completeness sidecar, untouched by ``reconcile``.
    """
    from plan_tool.scope_guard import build_file_to_step_map
    from plan_tool.drift_detection import reconcile_drift_hint

    file_to_step = build_file_to_step_map(plan, repo_root)
    info(
        f"saved audit is stale ({len(drifted_code)} code file(s) changed "
        f"since the audit); running fresh. Drifted files:"
    )
    _print_grouped_drift_files(drifted_code, repo_root, file_to_step)
    tool(reconcile_drift_hint(loop_name), stream=sys.stderr)


def _note_reuse_removed_code_files(removed_code, plan, repo_root) -> None:
    """Report declared files removed from a saved audit's footprint.

    The current, unchanged plan still maps each path to its owning step, so
    the operator gets an actionable attribution. This is intentionally not a
    content-drift message and has no recovery hint: a fresh audit already
    observes the removal, while a reconcile command cannot restore a deleted
    implementation file.
    """
    from plan_tool.scope_guard import build_file_to_step_map

    file_to_step = build_file_to_step_map(plan, repo_root)
    info(
        f"saved audit is stale ({len(removed_code)} declared code file(s) "
        f"removed since the audit); running fresh. Removed files:"
    )
    _print_grouped_drift_files(removed_code, repo_root, file_to_step)


def _walk_saved(
    kind: ReconcileKind,
    *,
    ctx: PlanToolContext,
    path: Path,
    plan_name: str,
    reuse_path: Path,
    yes: bool,
    run_logger: RunLogWriter,
) -> int:
    """Load + walk (or redirect-replay) a saved review of ``kind``.

    Returns the rc the caller should propagate: 1 when the saved file
    fails to load, else 0. The ``saved_reconcile_reuse`` phase brackets the
    reuse so run-log consumers can answer "did this reuse a saved review
    (no claude call) or run a fresh one?" by the absence of any
    ``claude_call_start`` event inside the phase.

    Two walk strategies: ``replay_redirects_only`` re-surfaces the saved
    ``[REDIRECT]`` blocks (run-reconcile findings carried inline code edits
    that already landed, so there is nothing to apply); otherwise the saved
    recommendations are walked interactively through ``_build_review_action_fn``.
    """
    if kind.phase_kind is None:
        run_logger.phase_start(
            "saved_reconcile_reuse", path=str(reuse_path),
        )
    else:
        run_logger.phase_start(
            "saved_reconcile_reuse", path=str(reuse_path),
            kind=kind.phase_kind,
        )
    phase_t0 = time.monotonic()
    outcome = "success"
    try:
        try:
            saved = load_review(reuse_path)
        except ReviewLoadError as exc:
            print(
                f"error loading saved {kind.noun}: {exc}",
                file=sys.stderr,
            )
            outcome = "error"
            return 1
        print(f"\n{kind.walk_verb} saved {kind.noun} {reuse_path}")
        if not saved.recommendations:
            print(kind.empty_message)
            return 0
        if kind.replay_redirects_only:
            # Re-print one two-line [REDIRECT] block per finding whose root
            # cause was attributed to the plan/detail. No apply walk — the
            # code edits already landed on the original audit call.
            for rec in saved.recommendations:
                if rec.redirect is None:
                    continue
                reason = rec.redirect.reason or "(unspecified)"
                print(
                    f"[REDIRECT] step {rec.step_id} finding {rec.id} "
                    f"[{confidence_label(rec.confidence)}]: {reason}",
                    file=sys.stderr,
                )
                print(
                    f"next: plan-tool detail {plan_name} --reconcile "
                    f"--step {rec.step_id}",
                    file=sys.stderr,
                )
            return 0
        state = WalkState(yes_to_all=yes)
        action_fn = _build_review_action_fn(
            ctx=ctx,
            plan_path=path,
            plan_name=plan_name,
            allow_structural_verdict=True,
            state=state,
            run_logger=run_logger,
        )
        walk_recommendations(saved, action_fn=action_fn, state=state)
        return 0
    finally:
        run_logger.phase_end(
            "saved_reconcile_reuse",
            duration_ms=int((time.monotonic() - phase_t0) * 1000),
            outcome=outcome,
        )


def _save_and_walk_reconcile(
    *,
    args: argparse.Namespace,
    ctx: PlanToolContext,
    plan_path: Path,
    step_id: int,
    stdout: str,
    report: str,
    run_logger: Optional[RunLogWriter] = None,
    budget: IterativeBudget = IterativeBudget(enabled=False),
    kind: str = "detail-reconcile",
) -> None:
    """Persist reconcile findings and walk them interactively.

    No-op when ``--no-save`` is set (skip persistence; implies no walk
    since the walker requires a saved path). Walk is also skipped on
    non-TTY stdin and when the recommendations list is empty.

    When ``run_logger`` is supplied, the actual walk loop is bracketed
    by ``reconcile_walk`` phase events so consumers can attribute
    apply-finding sub-calls to the walk that produced them. A
    ``--no-walk`` reconcile emits no phase events here (no work
    happened to time).

    ``budget`` drives the post-walk iteration loop (step 4). The
    default ``IterativeBudget(enabled=False)`` makes ``should_continue``
    short-circuit immediately so production behaviour stays unchanged
    until step 5 plumbs ``--iterate``. The loop is only invoked when
    the iteration-0 walk branch fires (TTY or ``-y``, non-empty recs,
    not ``--no-walk``) — otherwise there's no walk to iterate around.

    ``kind`` selects the save's producer label (and the recs' source
    tag). ``"detail-reconcile"`` (default) is the plan/detail-side audit
    invoked via ``plan-tool detail --reconcile``. It persists to
    ``*-detail-reconcile.json`` so listings and reuse-lookups can
    distinguish it. New kinds should keep the same on-disk shape.
    """
    from plan_tool.review import extract_reconcile_recommendations

    # ``--no-save`` / ``--no-walk`` are defined on the run subparser but
    # not on the detail subparser (the detail-reconcile path always
    # persists + walks). Default both to ``False`` when the namespace
    # doesn't carry them so a shared helper can serve both call sites.
    no_save = getattr(args, "no_save", False)
    no_walk = getattr(args, "no_walk", False)

    if no_save:
        return

    recs = extract_reconcile_recommendations(
        stdout, step_id=step_id, source=kind
    )

    # Persist a canonical repo-relative POSIX value, not a lexical warning path.
    try:
        plan_rel = plan_path.resolve().relative_to(ctx.repo_root.resolve()).as_posix()
    except ValueError:
        plan_rel = str(plan_path.resolve())

    # Capture both staleness axes so the saved sidecar can be reuse-checked
    # later (step 4/5). ``compute_plan_fingerprint`` is a pure file hash;
    # ``compute_code_fingerprint`` hashes the step's watched code surface.
    plan = parse_plan(plan_path)
    plan_fp = compute_plan_fingerprint(plan_path)
    code_fp = compute_code_fingerprint(plan, plan_path, ctx.repo_root)

    # No-op today (reconcile recs carry no directive), wired for the uniform
    # "stamp before save" rule: a future directive producer in this lane gets
    # stamped automatically rather than silently saving an unstamped directive.
    stamped_recs = stamp_target_signatures(plan, recs)
    saved_path = save_review(
        plan_slug=args.name,
        plan_path=plan_rel,
        repo_root=ctx.repo_root,
        report_md=report,
        recommendations=stamped_recs,
        kind=kind,
        step_id=step_id,
        plan_fingerprint=plan_fp,
        code_fingerprint=code_fp,
        # An absent recommendation clears a calibration origin only when the
        # raw code-side report itself was parseable. Legacy/malformed output
        # remains an unresolved observation rather than a false clean pass.
        outcome_evidence_valid=findings_output_is_valid(stdout),
        plan=plan,
    )
    n = len(recs)
    print(
        f"\nSaved {kind} to {saved_path} "
        f"({n} recommendation{'s' if n != 1 else ''})"
    )

    if (
        not no_walk
        and recs
        and (args.yes or sys.stdin.isatty())
    ):
        loaded = load_review(saved_path)
        # Reconcile-kind recs source="reconcile" with body describing a
        # plan edit. Apply on those should run apply_finding; provide
        # the action handler so that path is wired.
        state = WalkState(yes_to_all=args.yes)
        action_fn = _build_review_action_fn(
            ctx=ctx,
            plan_path=plan_path,
            plan_name=args.name,
            allow_structural_verdict=True,
            state=state,
            run_logger=run_logger,
        )
        _walk_with_reconcile_phase(
            loaded, action_fn, state,
            run_logger=run_logger, step_id=step_id,
        )
        _iterate_reconcile_loop(
            args=args,
            ctx=ctx,
            plan_path=plan_path,
            step_id=step_id,
            initial_recs=recs,
            state=state,
            budget=budget,
            run_logger=run_logger,
        )


def _cmd_detail_reconcile(
    args: argparse.Namespace,
    *,
    ctx: PlanToolContext,
    plan_path: Path,
) -> int:
    """Audit one step's plan/detail markdown against the code on disk.

    Distinct from :func:`cmd_detail`'s authoring branch: this path is
    read-only on the repo, renders ``prompts/detail-reconcile.md`` (the
    code-is-canonical direction), and walks any findings through the
    same ``apply_finding`` dispatcher used by ``plan-tool run --mode
    reconcile``. Treats the produced ``SavedReview`` as
    ``kind="detail-reconcile"`` so listings and reuse-lookups stay
    scoped to the detail-side audit.

    ``--step`` selects one step (the prompt is per-step); ``--all``
    dispatches to :func:`_cmd_detail_reconcile_all`, which loops the
    same per-step audit over every not-yet-done step. One of the two
    is required. Re-uses any pre-existing ``*-detail-reconcile.json``
    save for the same step when the user accepts the reuse prompt —
    mirrors ``cmd_run``'s reconcile reuse heuristic so we don't spend
    a fresh claude call when one already landed.

    The actual audit logic lives in :func:`_run_detail_reconcile_path`
    so the step-5 deprecation alias for ``plan-tool run --mode
    reconcile`` can dispatch into the same code path under its own
    ``command="run"`` run-log slug without double-logging.
    """
    from plan_tool.detail import _plan_slug as _detail_plan_slug

    if getattr(args, "all", False):
        return _cmd_detail_reconcile_all(args, ctx=ctx, plan_path=plan_path)

    if args.step is None:
        error(
            "--reconcile requires --step or --all (the audit prompt "
            "is per-step; --all sweeps it across every not-yet-done "
            "step)"
        )
        return 2

    run_logger = RunLogWriter.start(
        repo_root=ctx.repo_root,
        slug=_detail_plan_slug(plan_path),
        command="detail-reconcile",
        argv=list(sys.argv[1:]),
        plan_path=plan_path,
        step_filter=args.step,
        flags={
            "dry_run": args.dry_run,
            "step": args.step,
        },
    )
    rc = 1
    err_msg: Optional[str] = None
    try:
        rc, err_msg = _run_detail_reconcile_path(
            args=args,
            ctx=ctx,
            plan_path=plan_path,
            run_logger=run_logger,
            budget=IterativeBudget(enabled=False),
        )
        return rc
    except KeyboardInterrupt:
        # Preserve POSIX 130; app's dispatcher catches only ``Exception``.
        rc = 130
        err_msg = "interrupted"
        raise SystemExit(130)
    finally:
        run_logger.run_end(
            outcome=("success" if rc == 0 else "error"),
            rc=rc,
            error=err_msg,
        )


def _cmd_detail_reconcile_all(
    args: argparse.Namespace,
    *,
    ctx: PlanToolContext,
    plan_path: Path,
) -> int:
    """Sweep the detail-reconcile audit across every not-yet-done step.

    ``plan-tool detail <name> --reconcile --all`` runs the per-step
    code-is-truth audit (:func:`_run_detail_reconcile_path`) once per
    step whose ``status`` is not ``done``. Done steps are skipped by
    design: their detail files are historical records of work already
    delivered, so re-auditing them against code that has since moved
    on produces churn, not signal. The valuable targets are the
    remaining (pending / current / blocked) steps whose detail may
    have drifted from the evolving codebase before they execute.

    One :class:`RunLogWriter` per audited step (mirrors
    ``_cmd_run_sweep``'s one-log-per-step shape; the sweep itself
    produces no aggregating log). The plan is re-parsed before each
    step because the previous step's finding walk may have edited it —
    a step that became ``done`` mid-sweep is skipped with a note.

    Halt-on-failure: the first non-zero per-step rc ends the sweep
    and is returned unchanged (matches ``run --all``'s contract).
    Unlike ``run --all``, ``-y`` is NOT implied — on a TTY the
    operator walks each step's findings interactively; non-TTY runs
    without ``-y`` still save findings but skip the walk (same as the
    single-step path).
    """
    from plan_tool.detail import _plan_slug as _detail_plan_slug

    if args.step is not None:
        error(
            "--all and --step are mutually exclusive "
            "(--all sweeps every not-yet-done step; --step picks one)."
        )
        return 2

    if getattr(args, "reuse_id", None) is not None:
        error(
            "--reuse-id is mutually exclusive with --all (a saved "
            "detail-reconcile pins to one step; --all sweeps every step)."
        )
        return 2

    plan, parse_error = _try_parse_reconcile_plan(plan_path)
    if plan is None:
        error(parse_error or "could not read plan")
        return 2

    target_ids = [s.id for s in plan.steps if s.status != StepStatus.DONE]
    done_count = len(plan.steps) - len(target_ids)
    if not target_ids:
        print(
            f"all {len(plan.steps)} step(s) in '{args.name}' are done; "
            f"nothing to reconcile."
        )
        return 0
    print(
        f"detail-reconcile sweep: {len(target_ids)} step(s) to audit "
        f"({done_count} done step(s) skipped)."
    )

    audited = 0
    for sweep_index, step_id in enumerate(target_ids):
        current_plan, current, parse_error = _load_reconcile_sweep_step(
            plan_path, step_id
        )
        if current_plan is None:
            message = parse_error or "could not read plan"
            _record_detail_reconcile_preflight_failure(
                args,
                ctx=ctx,
                plan_path=plan_path,
                step_id=step_id,
                sweep_index=sweep_index,
                message=message,
            )
            error(message)
            print(
                f"sweep halted: step {step_id} audit exited 2.",
                file=sys.stderr,
            )
            return 2
        if current is None:
            print(
                f"skipping step {step_id}: removed from plan mid-sweep.",
                file=sys.stderr,
            )
            continue
        if current.status == StepStatus.DONE:
            print(
                f"skipping step {step_id}: marked done mid-sweep.",
                file=sys.stderr,
            )
            continue

        args.step = step_id
        run_logger = RunLogWriter.start(
            repo_root=ctx.repo_root,
            slug=_detail_plan_slug(plan_path),
            command="detail-reconcile",
            argv=list(sys.argv[1:]),
            plan_path=plan_path,
            step_filter=step_id,
            flags={
                "dry_run": args.dry_run,
                "step": step_id,
                "all": True,
                "sweep_index": sweep_index,
            },
        )
        rc = 1
        err_msg: Optional[str] = None
        try:
            rc, err_msg = _run_detail_reconcile_path(
                args=args,
                ctx=ctx,
                plan_path=plan_path,
                run_logger=run_logger,
                budget=IterativeBudget(enabled=False),
            )
        except KeyboardInterrupt:
            # Preserve POSIX 130; app's dispatcher catches only ``Exception``.
            rc = 130
            err_msg = "interrupted"
            raise SystemExit(130)
        finally:
            run_logger.run_end(
                outcome=("success" if rc == 0 else "error"),
                rc=rc,
                error=err_msg,
            )
        if rc != 0:
            print(
                f"sweep halted: step {step_id} audit exited {rc}.",
                file=sys.stderr,
            )
            return rc
        audited += 1

    print(f"detail-reconcile sweep complete: {audited} step(s) audited.")
    return 0


def _record_detail_reconcile_preflight_failure(
    args: argparse.Namespace,
    *,
    ctx: PlanToolContext,
    plan_path: Path,
    step_id: int,
    sweep_index: int,
    message: str,
) -> None:
    """Persist a detail sweep step that fails before its audit can start."""
    from plan_tool.detail import _plan_slug as _detail_plan_slug

    run_logger = RunLogWriter.start(
        repo_root=ctx.repo_root,
        slug=_detail_plan_slug(plan_path),
        command="detail-reconcile",
        argv=list(sys.argv[1:]),
        plan_path=plan_path,
        step_filter=step_id,
        flags={
            "dry_run": args.dry_run,
            "step": step_id,
            "all": True,
            "sweep_index": sweep_index,
        },
    )
    run_logger.run_end(outcome="error", rc=2, error=message)


def _run_detail_reconcile_path(
    *,
    args: argparse.Namespace,
    ctx: PlanToolContext,
    plan_path: Path,
    run_logger: RunLogWriter,
    budget: IterativeBudget = IterativeBudget(enabled=False),
) -> tuple[int, Optional[str]]:
    """Plan/detail-side reconcile body shared by detail and the alias.

    Returns ``(rc, err_msg)`` so the caller can record a single
    ``run_end`` against the run logger it owns. Step-3's
    :func:`_cmd_detail_reconcile` and step-5's ``plan-tool run --mode
    reconcile`` deprecation alias inside :func:`cmd_run` both call
    this; the alias passes its own ``command="run"`` ``RunLogWriter``
    so ``plan-tool runs list`` still shows the invocation under the
    operator's original verb (no double-log under
    ``command="detail-reconcile"``).

    Assumes the caller has already validated that the args namespace
    carries ``step``, ``dry_run``, ``yes``, and ``name`` -- the run
    subparser and the detail subparser both produce these. ``no_save``
    and ``no_walk`` are only on the run subparser; ``_save_and_walk_-
    reconcile`` reads them via ``getattr(..., False)`` so omission is
    silently treated as off (matches the detail subparser's behaviour
    of always persisting + walking).

    ``budget`` controls the post-walk iteration loop. The default
    ``IterativeBudget(enabled=False)`` matches :func:`_cmd_detail_-
    reconcile`'s historical behaviour (no iteration after a detail-side
    audit). The deprecation alias in :func:`cmd_run` passes
    ``_build_run_budget(args)`` so legacy ``plan-tool run --mode
    reconcile --iterate`` invocations keep iterating during the
    transition window.
    """
    if args.step is None:
        error(
            "--reconcile requires --step or --all (the audit prompt "
            "is per-step; --all sweeps it across every not-yet-done "
            "step)"
        )
        return 2, None

    rc = 1
    err_msg: Optional[str] = None

    # Resolve the step ourselves so the reuse prompt can key off the
    # right ``step_id``. Failures fall through silently — ``run_step``
    # will surface the same error with a better message.
    plan, _ = _try_parse_reconcile_plan(plan_path)
    try:
        target_step = resolve_step(plan, args.step) if plan is not None else None
    except LauncherError:
        target_step = None

    if target_step is not None:
        reuse_path = _prompt_reuse_saved_detail_reconcile(
            ctx, args.name, args, step_id=target_step.id, plan_path=plan_path
        )
        if reuse_path is not None:
            rc = _walk_saved_detail_reconcile(
                ctx=ctx,
                path=plan_path,
                plan_name=args.name,
                reuse_path=reuse_path,
                yes=args.yes,
                run_logger=run_logger,
            )
            return rc, err_msg

    try:
        result = run_step(
            plan_path,
            repo_root=ctx.repo_root,
            step_id=args.step,
            mode="detail-reconcile",
            dry_run=args.dry_run,
            allow_missing_parent=getattr(args, "allow_missing_parent", False),
            run_logger=run_logger,
        )
    except (LauncherError, OSError) as exc:
        err_msg = str(exc)
        error(str(exc))
        return 2, err_msg

    if args.dry_run:
        return 0, err_msg

    if result.exit_code != 0:
        # Populate err_msg so the caller's run_logger.run_end records the
        # real reason instead of None (the user saw this on stderr;
        # `plan-tool runs show` should too).
        err_msg = f"step {result.step_id} exited with code {result.exit_code}"
        print(f"{err_msg}; plan unchanged.", file=sys.stderr)
        return result.exit_code, err_msg

    summary = summarize_findings(result.stdout)
    verdict = format_findings_verdict(result.step_id, summary)
    print(
        f"mode 'detail-reconcile' finished for step {result.step_id}. "
        f"Plan unchanged."
    )
    print(verdict)

    _save_and_walk_reconcile(
        args=args,
        ctx=ctx,
        plan_path=plan_path,
        step_id=result.step_id,
        stdout=result.stdout,
        report=verdict,
        run_logger=run_logger,
        budget=budget,
        kind="detail-reconcile",
    )

    # Audit completed -- exit 0 even with critical findings; the verdict
    # and saved artifact carry the result. (A non-zero claude exit is
    # handled on the ``result.exit_code`` branch above.)
    rc = 0
    return rc, err_msg


def _walk_saved_detail_reconcile(
    *,
    ctx: PlanToolContext,
    path: Path,
    plan_name: str,
    reuse_path: Path,
    yes: bool,
    run_logger: RunLogWriter,
) -> int:
    """Load + walk a saved detail-reconcile (``detail --reconcile`` save)."""
    return _walk_saved(
        _RECONCILE_KINDS["detail-reconcile"],
        ctx=ctx, path=path, plan_name=plan_name,
        reuse_path=reuse_path, yes=yes, run_logger=run_logger,
    )


def _start_run_reconcile_log(
    args: argparse.Namespace,
    *,
    ctx: PlanToolContext,
    plan_path: Path,
    step_id: Optional[int],
    sweep_index: Optional[int],
) -> RunLogWriter:
    """Open the run log for one code-reconcile attempt."""
    return RunLogWriter.start(
        repo_root=ctx.repo_root,
        slug=args.name,
        command="run-reconcile",
        argv=list(sys.argv[1:]),
        plan_path=plan_path,
        step_filter=step_id,
        flags={
            "dry_run": args.dry_run,
            "no_save": getattr(args, "no_save", False),
            "no_walk": getattr(args, "no_walk", False),
            "yes": args.yes,
            "allow_missing_parent": args.allow_missing_parent,
            "all": sweep_index is not None,
            "sweep_index": sweep_index,
        },
    )


def _record_run_reconcile_preflight_failure(
    args: argparse.Namespace,
    *,
    ctx: PlanToolContext,
    plan_path: Path,
    step_id: int,
    sweep_index: int,
    message: str,
) -> None:
    """Persist a sweep step that fails before its audit can start."""
    run_logger = _start_run_reconcile_log(
        args,
        ctx=ctx,
        plan_path=plan_path,
        step_id=step_id,
        sweep_index=sweep_index,
    )
    run_logger.run_end(outcome="error", rc=2, error=message)


def _cmd_run_reconcile(
    args: argparse.Namespace,
    *,
    ctx: PlanToolContext,
    plan_path: Path,
) -> int:
    """Audit code against the plan/detail (plan is canonical).

    The audit and the apply happen in one claude call, not in a
    per-finding apply loop modeled on :func:`_dispatch_apply_finding`.
    ``prompts/run-reconcile.md`` is authored as an audit-and-edit
    prompt: claude is told to read the plan/detail, edit code where it
    diverges from plan intent, and emit ``## Redirect`` for findings
    whose root cause is in the plan. The launcher's
    ``shell_invoker`` runs claude with ``--permission-mode acceptEdits``
    — that subprocess IS the "file-write machinery" referenced in the
    plan; Edit/Write tool calls land the code edits inline.

    By contrast, :func:`launcher.apply_finding` snapshots plan +
    detail, runs the apply-finding prompt, and offers per-finding
    diff/keep/revert. The run-reconcile path does none of that — code
    edits are an inline side effect of the audit, and the only
    per-finding decision the CLI makes is whether to short-circuit a
    plan-rooted finding with ``[REDIRECT]``.

    Completed audits return rc=0 even for redirects and critical findings;
    sweeps halt only when an audit itself fails to complete.
    The ``[REDIRECT]`` two-line stderr format is the operator-facing
    contract; do not change without updating the integration test in
    step 8. The save artifact is ``<ts>-run-reconcile.json`` under
    ``plan-details/<slug>/reports/`` with top-level ``kind="run-reconcile"``.
    """
    if getattr(args, "all", False):
        return _cmd_run_reconcile_all(args, ctx=ctx, plan_path=plan_path)

    return _run_run_reconcile_step(
        args,
        ctx=ctx,
        plan_path=plan_path,
    ).rc


def _reuse_saved_run_reconcile_result(
    args: argparse.Namespace,
    *,
    ctx: PlanToolContext,
    plan_path: Path,
    step_id: int,
    run_logger: RunLogWriter,
) -> Optional[ReconcileStepResult]:
    """Offer to reuse a saved run-reconcile for ``step_id``.

    Returns the walked outcome, or ``None`` when reuse was declined/unfresh
    and the caller should fall through to a real audit.
    """
    reuse_path = _prompt_reuse_saved_run_reconcile(
        ctx, args.name, args, step_id=step_id, plan_path=plan_path
    )
    if reuse_path is None:
        return None
    rc = _walk_saved_run_reconcile(
        ctx=ctx,
        path=plan_path,
        plan_name=args.name,
        reuse_path=reuse_path,
        yes=args.yes,
        run_logger=run_logger,
    )
    return ReconcileStepResult(rc, outcome="reused" if rc == 0 else None)


def _run_run_reconcile_step(
    args: argparse.Namespace,
    *,
    ctx: PlanToolContext,
    plan_path: Path,
    sweep_index: Optional[int] = None,
    preloaded_plan: Optional[Plan] = None,
    preloaded_step: Optional[Step] = None,
) -> ReconcileStepResult:
    """Run and log one code-reconcile step, returning its sweep outcome."""
    run_logger = _start_run_reconcile_log(
        args,
        ctx=ctx,
        plan_path=plan_path,
        step_id=args.step,
        sweep_index=sweep_index,
    )

    rc = 1
    err_msg: Optional[str] = None
    try:
        selected_snapshot: Optional[SelectedRunReconcileSnapshot] = None
        # The stricter DONE/snapshot gate applies only to an explicit
        # `--step N` selection. Sweeps, and a bare call with no `--step`
        # (default current/next-runnable resolution), retain the older,
        # ungated behavior — that default can never resolve to a DONE step.
        if sweep_index is None and args.step is not None:
            reuse_is_possible = (
                not args.dry_run
                and not getattr(args, "no_walk", False)
                and not getattr(args, "no_save", False)
                and getattr(args, "reuse", None) is not False
            )
            if reuse_is_possible:
                # Reuse needs only a target id to replay a fresh saved result.
                # It intentionally bypasses fresh context construction.
                plan, parse_error = _try_parse_reconcile_plan(plan_path)
                if plan is None:
                    raise LauncherError(parse_error or "could not read plan")
                try:
                    target_step = resolve_step(plan, args.step)
                except LauncherError as exc:
                    raise LauncherError(
                        f"selected run-reconcile target: {exc}"
                    ) from exc
                reuse_result = _reuse_saved_run_reconcile_result(
                    args,
                    ctx=ctx,
                    plan_path=plan_path,
                    step_id=target_step.id,
                    run_logger=run_logger,
                )
                if reuse_result is not None:
                    return reuse_result
                # Re-parse fresh: an operator can edit the plan while the
                # prompt above blocks on input(), and the snapshot's
                # fingerprint must be grounded in the same read as `plan`.
                selected_snapshot = _load_selected_run_reconcile_snapshot(
                    plan_path, args.step, ctx.repo_root
                )
            else:
                selected_snapshot = _load_selected_run_reconcile_snapshot(
                    plan_path, args.step, ctx.repo_root
                )
            plan = selected_snapshot.plan
            target_step = selected_snapshot.step
        else:
            # Sweeps retain their existing all-code-step behavior. They use
            # completed siblings as context when available, but only an
            # explicit selected reconciliation receives the stricter gate.
            plan = preloaded_plan
            target_step = preloaded_step
            if plan is None:
                plan, _ = _try_parse_reconcile_plan(plan_path)
            if plan is not None and target_step is None:
                try:
                    target_step = resolve_step(plan, args.step)
                except LauncherError:
                    target_step = None

            if target_step is not None:
                reuse_result = _reuse_saved_run_reconcile_result(
                    args,
                    ctx=ctx,
                    plan_path=plan_path,
                    step_id=target_step.id,
                    run_logger=run_logger,
                )
                if reuse_result is not None:
                    return reuse_result

        completed_sibling_context = (
            _build_completed_sibling_context(plan, target_step)
            if plan is not None and target_step is not None
            else CompletedSiblingContext("", 0)
        )

        if selected_snapshot is not None and selected_reconcile_plan_fingerprint_changed(
            plan_path, selected_snapshot.plan_fingerprint
        ):
            err_msg = (
                "selected run-reconcile plan snapshot changed before backend "
                "invocation; retry the command"
            )
            error(err_msg)
            rc = 2
            return ReconcileStepResult(rc)

        try:
            result = run_step(
                plan_path,
                repo_root=ctx.repo_root,
                step_id=args.step,
                mode="run-reconcile",
                dry_run=args.dry_run,
                allow_missing_parent=args.allow_missing_parent,
                run_logger=run_logger,
                completed_sibling_context=completed_sibling_context.prompt,
                selected_reconcile_plan_snapshot=(
                    selected_snapshot.plan if selected_snapshot is not None else None
                ),
                selected_reconcile_plan_fingerprint=(
                    selected_snapshot.plan_fingerprint
                    if selected_snapshot is not None
                    else None
                ),
                reject_high_selected_reconcile_budget=selected_snapshot is not None,
            )
        except (LauncherError, OSError) as exc:
            err_msg = str(exc)
            error(str(exc))
            rc = 2
            return ReconcileStepResult(rc)

        if args.dry_run:
            rc = 0
            return ReconcileStepResult(rc, outcome="rendered")

        if result.exit_code != 0:
            print(
                f"step {result.step_id} exited with code {result.exit_code}; "
                f"plan unchanged.",
                file=sys.stderr,
            )
            rc = result.exit_code
            return ReconcileStepResult(rc)

        summary = summarize_findings(result.stdout)
        verdict = format_findings_verdict(result.step_id, summary)
        saved_report = _format_completed_sibling_context_report(
            verdict, summary, completed_sibling_context
        )
        print(
            f"mode 'run-reconcile' finished for step {result.step_id}. "
            f"Plan unchanged."
        )
        print(verdict)

        _save_and_walk_run_reconcile(
            args=args,
            ctx=ctx,
            plan_path=plan_path,
            step_id=result.step_id,
            stdout=result.stdout,
            report=saved_report,
            run_logger=run_logger,
        )
        # Audit completed -- exit 0 even when a redirect was surfaced or a
        # critical code finding was reported. Those are results the
        # operator acts on (re-route to ``detail --reconcile`` for a
        # redirect, or address the critical finding); the printed verdict
        # and saved artifact carry them, not the exit code. A genuine
        # non-zero claude exit is handled on the branch above.
        rc = 0
        return ReconcileStepResult(rc, outcome="audited")
    except LauncherError as exc:
        err_msg = str(exc)
        error(err_msg)
        rc = 2
        return ReconcileStepResult(rc)
    except KeyboardInterrupt:
        # Preserve POSIX 130; app's dispatcher catches only ``Exception``.
        rc = 130
        err_msg = "interrupted"
        raise SystemExit(130)
    finally:
        run_logger.run_end(
            outcome=("success" if rc == 0 else "error"),
            rc=rc,
            error=err_msg,
        )


def _cmd_run_reconcile_all(
    args: argparse.Namespace,
    *,
    ctx: PlanToolContext,
    plan_path: Path,
) -> int:
    """Sweep the plan-canonical reconcile across every code step."""
    # Defend direct callers that bypass argparse's mutual-exclusion check.
    if args.step is not None:
        error(
            "--all and --step are mutually exclusive "
            "(--all sweeps every plan step; --step picks one)."
        )
        return 2

    if getattr(args, "reuse_id", None) is not None:
        error(
            "--reuse-id is mutually exclusive with --all (a saved "
            "run-reconcile pins to one step; --all sweeps every step)."
        )
        return 2

    plan, parse_error = _try_parse_reconcile_plan(plan_path)
    if plan is None:
        error(parse_error or "could not read plan")
        return 2

    target_ids = [
        step.id for step in plan.steps if step.change_type != ChangeType.NON_CODE
    ]
    skipped = len(plan.steps) - len(target_ids)
    if not target_ids:
        print(f"no code steps in '{args.name}' to reconcile.")
        return 0

    print(
        f"reconcile-code sweep: {len(target_ids)} step(s) to audit"
        + (f" ({skipped} non-code step(s) skipped)" if skipped else "")
        + "."
    )
    progress = ReconcileSweepProgress()
    for sweep_index, step_id in enumerate(target_ids):
        current_plan, current, parse_error = _load_reconcile_sweep_step(
            plan_path, step_id
        )
        if current_plan is None:
            message = parse_error or "could not read plan"
            _record_run_reconcile_preflight_failure(
                args,
                ctx=ctx,
                plan_path=plan_path,
                step_id=step_id,
                sweep_index=sweep_index,
                message=message,
            )
            error(message)
            print(
                f"sweep halted: step {step_id} audit exited 2.",
                file=sys.stderr,
            )
            return 2
        if current is None:
            progress.record("skipped")
            print(
                f"skipping step {step_id}: removed from plan mid-sweep.",
                file=sys.stderr,
            )
            continue
        if current.change_type == ChangeType.NON_CODE:
            progress.record("skipped")
            print(
                f"skipping step {step_id}: reclassified as non-code mid-sweep.",
                file=sys.stderr,
            )
            continue

        step_args = argparse.Namespace(
            **(vars(args) | {"step": step_id, "all": False})
        )
        result = _run_run_reconcile_step(
            step_args,
            ctx=ctx,
            plan_path=plan_path,
            sweep_index=sweep_index,
            preloaded_plan=current_plan,
            preloaded_step=current,
        )
        progress.record(result.outcome)
        if result.rc != 0:
            print(
                f"sweep halted: step {step_id} audit exited {result.rc}.",
                file=sys.stderr,
            )
            return result.rc

    outcomes = [f"{progress.audited} step(s) audited"]
    if progress.reused:
        outcomes.append(f"{progress.reused} saved audit(s) reused")
    if progress.rendered:
        outcomes.append(f"{progress.rendered} step(s) rendered (dry-run)")
    if progress.skipped:
        outcomes.append(f"{progress.skipped} step(s) skipped during sweep")
    print(f"reconcile-code sweep complete: {', '.join(outcomes)}.")
    return 0


def _save_and_walk_run_reconcile(
    *,
    args: argparse.Namespace,
    ctx: PlanToolContext,
    plan_path: Path,
    step_id: int,
    stdout: str,
    report: str,
    run_logger: Optional[RunLogWriter] = None,
) -> int:
    """Persist run-reconcile findings and emit ``[REDIRECT]`` lines.

    Sibling of :func:`_save_and_walk_reconcile` but with two
    departures: (1) recs are extracted via
    :func:`review.extract_run_reconcile_recommendations` so each rec
    carries ``source="run-reconcile"`` and an optional ``Redirect``;
    (2) no interactive walk is offered because the audit already
    landed code edits inline — every finding whose ``redirect`` is
    populated is surfaced on stderr with the canonical
    ``[REDIRECT]`` two-line block instead of being dispatched
    through ``_build_review_action_fn``.

    Returns the number of redirect findings surfaced so the caller
    can fold that into the exit-code calculation. No-op (returns 0)
    when ``--no-save`` is set; the save is what makes
    ``plan-tool reconcile-plan-walk`` replay possible later, so without it
    there is nothing to walk and nothing to count.
    """
    from plan_tool.review import extract_run_reconcile_recommendations

    no_save = getattr(args, "no_save", False)
    if no_save:
        return 0

    recs = extract_run_reconcile_recommendations(stdout, step_id=step_id)

    # Persist a canonical repo-relative POSIX value, not a lexical warning path.
    try:
        plan_rel = plan_path.resolve().relative_to(ctx.repo_root.resolve()).as_posix()
    except ValueError:
        plan_rel = str(plan_path.resolve())

    # Capture both staleness axes (plan-side digest + code-side path→hash map)
    # so a later reuse check can tell whether either moved underneath the save.
    plan = parse_plan(plan_path)
    plan_fp = compute_plan_fingerprint(plan_path)
    code_fp = compute_code_fingerprint(plan, plan_path, ctx.repo_root)

    # No-op today (run-reconcile recs carry no directive), wired for the uniform
    # "stamp before save" rule — see ``_save_and_walk_reconcile``.
    stamped_recs = stamp_target_signatures(plan, recs)
    saved_path = save_review(
        plan_slug=args.name,
        plan_path=plan_rel,
        repo_root=ctx.repo_root,
        report_md=report,
        recommendations=stamped_recs,
        kind="run-reconcile",
        step_id=step_id,
        plan_fingerprint=plan_fp,
        code_fingerprint=code_fp,
        plan=plan,
    )
    n = len(recs)
    print(
        f"\nSaved run-reconcile to {saved_path} "
        f"({n} recommendation{'s' if n != 1 else ''})"
    )

    # Emit one two-line [REDIRECT] block per finding whose root cause
    # claude attributed to the plan/detail rather than the code. The
    # ``next:`` line is constructed CLI-side from ``args.name`` +
    # ``rec.step_id`` rather than echoed from claude's
    # ``Suggested next:`` field so the operator gets a deterministic
    # command (prompt drift on the suggested-next wording can't break
    # this contract; step 8's integration test pins the format).
    redirect_count = 0
    for rec in recs:
        if rec.redirect is None:
            continue
        redirect_count += 1
        reason = rec.redirect.reason or "(unspecified)"
        print(
            f"[REDIRECT] step {rec.step_id} finding {rec.id} "
            f"[{confidence_label(rec.confidence)}]: {reason}",
            file=sys.stderr,
        )
        print(
            f"next: plan-tool detail {args.name} --reconcile "
            f"--step {rec.step_id}",
            file=sys.stderr,
        )
    return redirect_count


def _print_attributed_files(
    paths,
    repo_root,
    file_to_step,
    *,
    file=None,
    max_listed: int = 10,
) -> None:
    """Print a bulleted list of paths to stderr, annotated with their
    owning step's id and title when ``file_to_step`` resolves the
    path. Used for scope-guard out-of-scope warnings so operators see
    which step a flagged file belongs to without consulting the plan
    (sibling).

    Reuses :func:`drift_detection.render_attributed_path_line` for
    the line format so it matches drift warnings.
    """
    from plan_tool.drift_detection import render_attributed_path_line

    out = file if file is not None else sys.stderr
    paths_list = list(paths)
    for p in paths_list[:max_listed]:
        line = render_attributed_path_line(p, repo_root, file_to_step)
        print(f"  - {line}", file=out)
    if len(paths_list) > max_listed:
        print(
            f"  - ... and {len(paths_list) - max_listed} more",
            file=out,
        )


def _print_grouped_drift_files(
    paths,
    repo_root,
    file_to_step,
    *,
    file=None,
    max_listed: int = 10,
) -> None:
    """Like :func:`_print_attributed_files`, but group the paths by their
    owning step so a shared step title prints once as a header instead of
    being echoed on every file line. When several changed files belong to
    the same step, the flat form repeats that step's (often long) title
    per file; grouping collapses it to::

        step 5: <title>
          - a.py
          - b.py

    Files that don't resolve to a step are listed bare. ``max_listed`` caps
    the total number of file lines across all groups.
    """
    out = file if file is not None else sys.stderr
    paths_list = list(paths)
    shown = paths_list[:max_listed]

    def _step_of(p, rel):
        step_info = file_to_step.get(p.resolve()) if p.is_absolute() else None
        if step_info is None:
            # Callers don't always pass resolved paths; try the rel form too.
            step_info = file_to_step.get((repo_root / rel).resolve())
        return step_info

    # Preserve first-seen order of steps and of files within each step.
    groups: dict = {}
    order: list = []
    for p in shown:
        rel = literal_path(p, repo_root)
        key = _step_of(p, rel)  # (step_id, title) tuple, or None when unowned
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(rel)

    for key in order:
        rels = groups[key]
        if key is None:
            for rel in rels:
                print(f"  - {rel}", file=out)
            continue
        step_id, step_title = key
        print(f"  step {step_id}: {step_title}", file=out)
        for rel in rels:
            print(f"    - {rel}", file=out)
    if len(paths_list) > max_listed:
        print(f"  - ... and {len(paths_list) - max_listed} more", file=out)


def _emit_drift_halt_warning(
    drifted: list,
    *,
    phase: str,
    finding_id: str,
    ctx_repo_root,
    file_to_step=None,
) -> None:
    """Thin wrapper around :func:`drift_detection.emit_drift_halt_warning`.

    Kept as a private helper to preserve the in-process call surface
    cli.py call sites depend on (``ctx_repo_root`` instead of the
    library's ``repo_root`` kwarg name). When ``file_to_step`` is
    provided, each drifted-file line is suffixed with the owning
    step's id and title.
    """
    from plan_tool.drift_detection import emit_drift_halt_warning

    emit_drift_halt_warning(
        drifted,
        phase=phase,
        finding_id=finding_id,
        repo_root=ctx_repo_root,
        file_to_step=file_to_step,
    )


def _run_auto_reconcile_on_drift(*args, **kwargs) -> int:
    """Thin re-export of :func:`auto_reconcile.run_auto_reconcile_on_drift`.

    Kept for the existing test suite that imports
    ``plan_tool.cli._run_auto_reconcile_on_drift``. New call sites
    should import from ``plan_tool.auto_reconcile`` directly.
    """
    from plan_tool.auto_reconcile import run_auto_reconcile_on_drift

    return run_auto_reconcile_on_drift(*args, **kwargs)


def _emit_scope_guard_plan(
    scope_buffer,
    *,
    plan_path: Path,
    plan_slug: str,
    ctx: PlanToolContext,
) -> None:
    """Write follow-up implementation-plan stubs from the scope guard
    buffer, when non-empty.

    Each record is classified by :func:`classify_plan_scope` against
    its own touched files, then records are partitioned by
    destination so a buffer spanning multiple skills/agents/project
    emits multiple plans -- one per scope. Skill plans land in
    ``.agents/skills/<skill>/implementation-plans/``, agent plans in
    ``.agents/<agent>/implementation-plans/``, project plans in
    ``docs/implementation-plans/``. Plan id auto-increments from the
    highest numeric prefix in the destination dir.
    """
    from plan_tool.scope_guard import (
        ScopeGuardBuffer,
        classify_plan_scope,
        write_out_of_scope_plan,
    )

    if scope_buffer.is_empty():
        return

    # Bucket records by classification of their touched files.
    # bucket_key: tuple (kind, str(plans_dir)) -- the dir is the
    # source of truth so identical kinds in different repos don't collide.
    buckets: dict[tuple[str, Path], ScopeGuardBuffer] = {}
    for rec in scope_buffer.records:
        kind, plans_dir = classify_plan_scope(
            rec.out_of_scope_files, ctx.repo_root
        )
        key = (kind, plans_dir)
        if key not in buckets:
            buckets[key] = ScopeGuardBuffer()
        buckets[key].add(rec)

    for (kind, plans_dir), bucket in buckets.items():
        plans_dir.mkdir(parents=True, exist_ok=True)
        existing_ids: list[int] = []
        for p in plans_dir.glob("[0-9]*-*.md"):
            stem_prefix = p.name.split("-", 1)[0]
            if stem_prefix.isdigit():
                existing_ids.append(int(stem_prefix))
        next_id = (max(existing_ids) if existing_ids else 0) + 1
        new_plan_path = write_out_of_scope_plan(
            bucket,
            source_plan_slug=plan_slug,
            output_dir=plans_dir,
            next_id=next_id,
        )
        if new_plan_path is not None:
            rel = literal_path(new_plan_path, ctx.repo_root)
            print(
                f"plan-tool: wrote {len(bucket.records)} "
                f"out-of-scope finding(s) ({kind} scope) to {rel}",
                file=sys.stderr,
            )


def _iterate_reconcile_loop(
    *,
    args: argparse.Namespace,
    ctx: PlanToolContext,
    plan_path: Path,
    step_id: int,
    initial_recs: list,
    state: WalkState,
    budget: IterativeBudget,
    run_logger: Optional[RunLogWriter] = None,
) -> None:
    """Run reconcile-mode iteration passes until convergence, marginal
    stop, or budget exhaustion.

    Iteration 0 is the caller's just-completed save+walk; this helper
    starts at iteration 1. Each iteration calls ``run_step`` in
    reconcile mode, saves the new findings to a fresh ``-reconcile.json``,
    and walks them with the shared ``WalkState``. The loop terminates
    when ``should_continue`` returns False; the stop reason is printed.

    No-op when ``budget.enabled`` is False — production ``cmd_run``
    hits this path until step 5 wires ``--iterate``.
    """
    if not budget.enabled:
        return

    from plan_tool.parser import parse_plan as _parse_plan
    from plan_tool.review import extract_reconcile_recommendations
    from plan_tool.scope_guard import (
        ScopeGuardBuffer,
        compute_in_scope_paths,
        compute_plan_tool_artifact_paths,
        compute_snapshot_dirs,
        write_out_of_scope_plan,
    )
    calibration_lookup = build_low_impact_demotion_lookup(ctx.repo_root)

    # Scope guard setup: compute in-scope file set + snapshot dirs from
    # the plan's current shape, then accumulate a buffer across all
    # iterations. Per-finding pre/post snapshots run inside the
    # walk's action_fn dispatcher -- the loop here only
    # holds the dirs/in-scope set and the shared ``scope_buffer``
    # accumulator; ``evaluate_apply_scope`` / ``revert_out_of_scope``
    # are dispatched from ``_dispatch_apply_finding`` via
    # ``reconcile_scope_guard`` per finding.
    scope_plan = _parse_plan(plan_path)
    scope_in_scope = compute_in_scope_paths(scope_plan, plan_path, ctx.repo_root)
    scope_ignored_artifacts = compute_plan_tool_artifact_paths(
        plan_path, ctx.repo_root
    )
    scope_dirs = compute_snapshot_dirs(scope_in_scope, ctx.repo_root)
    scope_buffer = ScopeGuardBuffer()

    # Acquire the per-repo iteration lock. Same one cmd_completeness
    # uses -- the lockfile is global to the repo's .plan-tool/ state.
    # Release happens at every return path of this helper (alongside
    # the scope-guard plan emit) so a crashed iteration doesn't leak
    # the lock indefinitely.
    # File->step map enriches drift warnings with the owning step's id +
    # title. ``iteration_session`` releases the lock + emits the drift
    # warning + restores the SIGINT handler on EVERY exit path -- each
    # early ``return`` below, a clean finish, or an unexpected exception
    # escaping the loop -- so a crash leaves no stale lockfile.
    from plan_tool.scope_guard import (
        build_file_to_step_map,
        compute_drift_watched_paths as _cdwp,
    )
    _file_to_step = build_file_to_step_map(scope_plan, ctx.repo_root)
    _watched_paths = _cdwp(scope_plan, plan_path, ctx.repo_root)

    from plan_tool.drift_detection import iteration_session
    with iteration_session(
        ctx.repo_root,
        enabled=True,
        slug=args.name,
        command="run-reconcile",
        loop_name="reconcile",
        watched_paths=_watched_paths,
        file_to_step=_file_to_step,
    ) as _iter_lock:
            conv_state = ConvergenceState(budget=budget)
            # Iteration 0 = caller's walk. Seed previous_finding_ids with that
            # iteration's recs so the first should_continue() comparison after
            # record_iteration measures iteration-1-vs-0 overlap, not 1-vs-empty.
            record_iteration(conv_state, [r.id for r in initial_recs])
            conv_state.has_blocking_findings = any(
                is_blocking_impact(
                    r, demote_low_impact_medium=calibration_lookup,
                )
                for r in initial_recs
            )

            # Track severity of findings raised in the most recent iteration.
            # When the loop exits via ``max_iterations`` AND the final round
            # raised HIGH or CRITICAL findings, emit a warning + non-zero exit
            # hint: the loop ran out of rounds while serious work was still
            # landing, so more likely-serious issues remain unfixed. Seeded
            # from iteration 0's recs so a one-shot --iterate run that
            # exhausts max_iterations=1 with critical findings still triggers
            # the warning.
            last_iter_high_critical = [
                r for r in initial_recs
                if r.severity.lower() in ("critical", "high")
            ]

            # Tracks whether any in-loop iteration has actually spent tokens.
            # Used by the pre-iteration drift check to decide between "before"
            # phrasing (first iteration, nothing kept) and "during" phrasing
            # (prior iteration's edits are KEPT; halting the next round). The
            # caller's iteration-0 walk doesn't count here -- those tokens
            # were spent before this loop took the iteration lock, and any
            # drift then would have been a pre-loop edit, not mid-iteration.
            #
            # tracked on ``state.work_landed_in_loop`` instead
            # of a local flag so the action_fn can flip it after each kept
            # apply (per-finding granularity). Reset here to clear any
            # carryover from prior callers using the same ``WalkState``.
            # ``reset_halt()`` clears the per-finding halt-signal fields for
            # the same reason -- if a caller's prior ``_iterate_reconcile_loop``
            # invocation halted mid-walk, ``halt_requested`` may still be
            # True; the walker would then break on the very first rec of
            # this fresh invocation. Defensive even though production
            # callers always pass a fresh ``WalkState``.
            state.work_landed_in_loop = False
            state.reset_halt()

            # When -y or non-TTY, force apply-all so iteration N's walk doesn't
            # block on per-rec prompts the user isn't there to answer. Set
            # *after* iteration 0's walk so the user's interactive TTY pass
            # isn't short-circuited.
            if args.yes or not sys.stdin.isatty():
                state.yes_to_all = True

            while True:
                cont, reason = should_continue(conv_state)
                if not cont:
                    if budget.enabled:
                        print(
                            f"\nreconcile iteration loop halted after "
                            f"{conv_state.iteration} pass(es): {reason}"
                        )
                        # Safety warning: loop exhausted ``max_iterations``
                        # while the final round was still raising HIGH or
                        # CRITICAL findings. More serious work likely remains.
                        # The warning is informational here -- the apply layer
                        # may have landed all of them, or they may have been
                        # refused; either way the human reviewer should look
                        # before declaring the loop output trustworthy.
                        if reason == "max_iterations" and last_iter_high_critical:
                            severities = sorted(
                                {r.severity.upper() for r in last_iter_high_critical}
                            )
                            print(
                                f"\nplan-tool: WARNING: reconcile loop exhausted "
                                f"max_iterations={budget.max_iterations} for "
                                f"step {step_id} with "
                                f"{len(last_iter_high_critical)} "
                                f"{'/'.join(severities)} finding(s) raised in "
                                f"the final round. More serious work likely "
                                f"remains unfixed -- raise --max-iterations or "
                                f"review the final iteration's findings "
                                f"manually before treating this output as "
                                f"converged.",
                                file=sys.stderr,
                            )
                        elif reason == "time_budget_exceeded":
                            # Parity with create/detail/completeness (#123): the
                            # cooperative cap stopped this cleanly at a pass
                            # boundary — point the operator at the resume path.
                            # The reconcile loop lives on `detail --reconcile`
                            # (`run --iterate` is a no-op — see run_cmd.py).
                            print(
                                f"plan-tool: time budget reached — reconcile "
                                f"stopped cleanly for step {step_id} "
                                f"(applied passes are durable). Re-run "
                                f"`plan-tool detail {args.name} --reconcile "
                                f"--iterate` to continue, or raise --time-budget.",
                                file=sys.stderr,
                            )
                    _emit_scope_guard_plan(
                        scope_buffer,
                        plan_path=plan_path,
                        plan_slug=args.name,
                        ctx=ctx,
                    )
                    return

                # Pre-iteration drift check (task #30 -> #33). Halt before
                # spending claude tokens on this iteration's run_step + walk
                # if a watched (step.files) file was edited between iterations.
                # Phase wording: "before" when nothing has landed yet this loop
                # (first pass), "during" once any prior apply (in this or a
                # past iteration) is kept on disk. Reads
                # ``state.work_landed_in_loop`` -- the action_fn flips that
                # to True after each per-finding apply lands,
                # so the same source drives both the iteration-boundary
                # check here AND the per-finding pre-apply check inside
                # ``_dispatch_apply_finding``.
                if not getattr(args, "allow_drift", False):
                    from plan_tool.drift_detection import check_drift as _check_drift
                    pre_drifted = _check_drift(_iter_lock)
                    if pre_drifted:
                        _emit_drift_halt_warning(
                            pre_drifted,
                            phase=(
                                "during"
                                if state.work_landed_in_loop
                                else "before"
                            ),
                            finding_id=(
                                f"reconcile-iter{conv_state.iteration + 1}-"
                                f"step{step_id}"
                            ),
                            ctx_repo_root=ctx.repo_root,
                            file_to_step=_file_to_step,
                        )
                        if getattr(args, "auto_reconcile_on_drift", True):
                            from plan_tool.auto_reconcile import (
                                run_auto_reconcile_on_drift,
                            )
                            run_auto_reconcile_on_drift(
                                drifted=pre_drifted,
                                file_to_step=_file_to_step,
                                plan_path=plan_path,
                                plan_slug=args.name,
                                repo_root=ctx.repo_root,
                                run_logger=run_logger,
                            )
                        _emit_scope_guard_plan(
                            scope_buffer,
                            plan_path=plan_path,
                            plan_slug=args.name,
                            ctx=ctx,
                        )
                        return

                print(
                    f"\n→ detail-reconcile iteration {conv_state.iteration + 1}"
                    f"/{budget.max_iterations} for step {step_id}…"
                )
                try:
                    result = run_step(
                        plan_path,
                        repo_root=ctx.repo_root,
                        step_id=step_id,
                        mode="detail-reconcile",
                        dry_run=False,
                        run_logger=run_logger,
                    )
                except LauncherError as exc:
                    print(
                        f"detail-reconcile iteration launcher error: {exc}",
                        file=sys.stderr,
                    )
                    _emit_scope_guard_plan(
                        scope_buffer,
                        plan_path=plan_path,
                        plan_slug=args.name,
                        ctx=ctx,
                    )
                    return
                # detail-reconcile claude call returned: debounce the deadline timer.
                touch(conv_state)
                if result.exit_code != 0:
                    print(
                        f"detail-reconcile iteration exited with code "
                        f"{result.exit_code}; halting loop",
                        file=sys.stderr,
                    )
                    _emit_scope_guard_plan(
                        scope_buffer,
                        plan_path=plan_path,
                        plan_slug=args.name,
                        ctx=ctx,
                    )
                    return

                recs = extract_reconcile_recommendations(
                    result.stdout, step_id=step_id, source="detail-reconcile",
                )
                # Persist a canonical repo-relative POSIX value, not a lexical warning path.
                try:
                    plan_rel = plan_path.resolve().relative_to(
                        ctx.repo_root.resolve()
                    ).as_posix()
                except ValueError:
                    plan_rel = str(plan_path.resolve())
                summary = summarize_findings(result.stdout)
                report = format_findings_verdict(step_id, summary)
                # Reuse the already-parsed ``scope_plan`` for the code axis:
                # the loop edits plan/detail prose, but the watched code
                # surface excludes those files, so the step structure
                # ``scope_plan`` carries is stable across iterations. Hash the
                # plan bundle fresh each pass so the plan axis tracks the
                # current detail bytes.
                plan_fp = compute_plan_fingerprint(plan_path)
                code_fp = compute_code_fingerprint(
                    scope_plan, plan_path, ctx.repo_root
                )
                # No-op today (detail-reconcile recs carry no directive), wired
                # for the uniform "stamp before save" rule — see
                # ``_save_and_walk_reconcile``.
                stamped_recs = stamp_target_signatures(scope_plan, recs)
                saved_path = save_review(
                    plan_slug=args.name,
                    plan_path=plan_rel,
                    repo_root=ctx.repo_root,
                    report_md=report,
                    recommendations=stamped_recs,
                    kind="detail-reconcile",
                    step_id=step_id,
                    plan_fingerprint=plan_fp,
                    code_fingerprint=code_fp,
                    plan=scope_plan,
                )
                print(
                    f"  saved iteration {conv_state.iteration + 1} detail-reconcile "
                    f"to {saved_path} ({len(recs)} rec(s))"
                )

                # Initialize per-iteration scope-guard handle to None so the
                # post-walk drift branch's collision-sidecar wiring can
                # reference it unconditionally. The real instance is built
                # inside the ``if recs:`` walk branch below; an empty-rec
                # iteration leaves it None, and the sidecar branch falls
                # through to legacy halt (no applies happened, no merged
                # baseline to feed the sidecar).
                iter_scope_guard: Optional["ReconcileScopeGuard"] = None

                if recs:
                    loaded = load_review(saved_path)
                    # Impact-weighted triage (session 4 follow-up). The
                    # reconcile prompt asks claude to emit Impact +
                    # Complexity in each finding's ``## Decision`` block;
                    # ``extract_reconcile_recommendations`` propagates those
                    # to the rec. Skip applies whose complexity strictly
                    # exceeds their impact -- those findings are reported
                    # on stderr and stay out of the walk so the iteration
                    # converges faster when only triaged findings remain.
                    # ``--no-triage`` disables this filter (apply every
                    # finding regardless of triage tags).
                    from plan_tool.review import (
                        emit_triage_summary,
                        partition_findings_for_triage,
                    )
                    open_apply, open_deferred = partition_findings_for_triage(
                        loaded.recommendations,
                        triage_enabled=getattr(args, "triage", True),
                        include_info=getattr(args, "include_info", False),
                    )
                    emit_triage_summary(
                        open_deferred,
                        iteration_label=(
                            f"detail-reconcile iter {conv_state.iteration + 1} "
                            f"step {step_id}"
                        ),
                    )
                    # Short-circuit when EVERY rec was triaged-deferred:
                    # walking an empty rec list is a no-op but the next
                    # iteration's run_step would still spend tokens, so
                    # halt the iteration loop here. Mirrors the peer
                    # short-circuits in cmd_completeness / create.py /
                    # detail.py. The legacy "marginal" convergence check
                    # would eventually catch the same case, but only after
                    # one wasted reconcile call.
                    if not open_apply and open_deferred:
                        print(
                            f"plan-tool: detail-reconcile iteration halting for "
                            f"step {step_id} -- all "
                            f"{len(open_deferred)} remaining finding(s) "
                            f"are triaged-deferred. Apply manually or "
                            f"pass --no-triage to force-apply.",
                            file=sys.stderr,
                        )
                        return
                    # Replace the walk's rec set with the apply-eligible
                    # subset. Reassigning ``loaded.recommendations`` is safe
                    # because ``SavedReview`` is mutable by design (the
                    # walk loop already mutates ``annotations``). The on-
                    # disk JSON still carries the full set (deferred + apply)
                    # so downstream `reconcile-plan-walk` invocations see everything.
                    loaded.recommendations = open_apply
                    # Per-finding scope guard. Replaces the
                    # legacy per-iteration evaluate_apply_scope wrapper around
                    # the entire walk. The action_fn dispatcher snapshots
                    # scope_dirs before each apply_finding and runs
                    # evaluate_apply_scope → revert_out_of_scope →
                    # scope_buffer.add per finding in its finally block, so
                    # ``scope_buffer`` accumulates one (or more) record per
                    # rec that introduced an out-of-scope edit, with the
                    # rec's own ``finding_id`` for attribution.
                    #
                    # ``apply_pre_snapshots`` is cleared per iteration so the
                    # post-walk drift halt's merged-baseline composition
                    # (consumed by ``handle_drift_collision``) reflects only
                    # the current iteration's applies. Without this clear,
                    # the merged baseline would carry stale entries from
                    # prior iterations and ``save_collision_sidecars`` could
                    # restore files to a pre-loop state.
                    from plan_tool.scope_guard import (
                        ReconcileScopeGuard as _ReconcileScopeGuard,
                    )
                    iter_scope_guard = _ReconcileScopeGuard(
                        scope_dirs=scope_dirs,
                        in_scope=scope_in_scope,
                        scope_buffer=scope_buffer,
                        file_to_step=_file_to_step,
                        repo_root=ctx.repo_root,
                        ignored_artifact_paths=scope_ignored_artifacts,
                        # Per-finding drift halt context. The action_fn
                        # uses these to run pre/post check_drift against
                        # ``iter_lock`` between/after each apply_finding. When
                        # ``iter_lock`` is None the drift checks short-circuit;
                        # ``allow_drift`` mirrors the CLI flag's gate on the
                        # iteration-level pre/post checks.
                        iter_lock=_iter_lock,
                        allow_drift=getattr(args, "allow_drift", False),
                        collision_sidecar_enabled=getattr(
                            args, "collision_sidecar", True,
                        ),
                    )
                    action_fn = _build_review_action_fn(
                        ctx=ctx,
                        plan_path=plan_path,
                        plan_name=args.name,
                        allow_structural_verdict=True,
                        state=state,
                        run_logger=run_logger,
                        reconcile_scope_guard=iter_scope_guard,
                    )
                    _walk_with_reconcile_phase(
                        loaded, action_fn, state,
                        run_logger=run_logger, step_id=step_id,
                    )
                    # walk_with_reconcile_phase dispatches per-finding
                    # apply_finding calls (each 10-15 min). Touch after the
                    # walk returns so the deadline debounces on the entire
                    # apply-phase as a unit of progress.
                    touch(conv_state)

                    # Per-finding drift halt signal. action_fn
                    # set state.halt_requested when a per-finding pre- or
                    # post-apply drift check fired. Two paths:
                    #
                    # 1. ``halt_merged=True``: user merged the change-collision
                    #    sidecar. refresh_snapshot has already run inside
                    #    action_fn, so the lock's content-hash baseline reflects
                    #    the merged state. Record this iteration's progress and
                    #    ``continue`` to the next while-pass which will collect
                    #    fresh findings against the merged tree.
                    #
                    # 2. ``halt_merged=False``: drift detected, no merge (pre-
                    #    apply drift, or user declined sidecar merge, or
                    #    headless / EOF). Run auto-reconcile + emit scope-guard
                    #    plan + cleanup + return. Mirrors cmd_completeness's
                    #    drift-halt path.
                    #
                    # ``state.reset_halt()`` clears the signal fields so the
                    # next iteration starts clean (state is shared across all
                    # iterations of this helper).
                    if state.halt_requested:
                        halt_drifted = list(state.halt_drifted)
                        halt_merged = state.halt_merged
                        state.reset_halt()
                        if halt_merged:
                            # ``state.work_landed_in_loop`` was flipped to
                            # True by action_fn after the apply that
                            # preceded this drift halt -- the next
                            # iteration's pre-iter drift check picks
                            # "during" phrasing correctly.
                            record_iteration(
                                conv_state, [r.id for r in recs],
                            )
                            conv_state.has_blocking_findings = any(
                                is_blocking_impact(
                                    r,
                                    demote_low_impact_medium=calibration_lookup,
                                )
                                for r in recs
                            )
                            last_iter_high_critical = [
                                r for r in recs
                                if r.severity.lower() in ("critical", "high")
                            ]
                            continue
                        if getattr(args, "auto_reconcile_on_drift", True):
                            from plan_tool.auto_reconcile import (
                                run_auto_reconcile_on_drift,
                            )
                            run_auto_reconcile_on_drift(
                                drifted=halt_drifted,
                                file_to_step=_file_to_step,
                                plan_path=plan_path,
                                plan_slug=args.name,
                                repo_root=ctx.repo_root,
                                run_logger=run_logger,
                            )
                        _emit_scope_guard_plan(
                            scope_buffer,
                            plan_path=plan_path,
                            plan_slug=args.name,
                            ctx=ctx,
                        )
                        return

                # Post-walk drift check (task #30 -> #33). The walk's
                # apply_finding edits are KEPT (claude tokens already spent;
                # the edits may still be useful) -- halt the next iteration to
                # prevent compounding the issue. Mirrors cmd_completeness's
                # post-apply check.
                if not getattr(args, "allow_drift", False):
                    from plan_tool.drift_detection import check_drift as _check_drift
                    post_drifted = _check_drift(_iter_lock)
                    if post_drifted:
                        _emit_drift_halt_warning(
                            post_drifted,
                            phase="during",
                            finding_id=(
                                f"reconcile-iter{conv_state.iteration + 1}-"
                                f"step{step_id}"
                            ),
                            ctx_repo_root=ctx.repo_root,
                            file_to_step=_file_to_step,
                        )
                        # Change-collision sidecar (sub-deliverable
                        # 3). The walk's per-finding scope guard already ran
                        # inside the action_fn dispatcher, so each
                        # ``apply_finding`` call's ``pre_snapshot`` was recorded
                        # on ``iter_scope_guard``. At iteration granularity,
                        # the merged first-seen-per-path baseline approximates
                        # the plan+detail state at iteration start -- exactly
                        # what ``handle_drift_collision`` needs to write
                        # sidecars + restore originals.
                        #
                        # On merge-continue (returns True), refresh the lock's
                        # content-hash snapshot so the NEXT iteration's pre-
                        # apply drift check compares against the merged state
                        # (mirrors cmd_completeness Bug 1 from session-4
                        # review); per-finding scope-eval has already run, so
                        # no additional revert/buffer.add work is needed
                        # here. The ``continue`` loops back to the while
                        # head so the next iteration re-collects findings
                        # against the merged state.
                        if (
                            getattr(args, "collision_sidecar", True)
                            and iter_scope_guard is not None
                        ):
                            from plan_tool.change_collision import (
                                handle_drift_collision,
                            )
                            merged_baseline = (
                                iter_scope_guard.merged_apply_pre_snapshot()
                            )
                            if merged_baseline and handle_drift_collision(
                                merged_baseline,
                                repo_root=ctx.repo_root,
                                yes=args.yes,
                            ):
                                from plan_tool.drift_detection import (
                                    refresh_snapshot,
                                )
                                refresh_snapshot(_iter_lock)
                                # Record this iteration's progress so the
                                # convergence check sees forward motion;
                                # without this the loop's marginal/overlap
                                # detector would compare against the prior
                                # iteration's recs only. ``state.work_landed_in_loop``
                                # was set by action_fn after the apply that
                                # preceded this drift -- next pre-iter check
                                # picks "during" phrasing.
                                record_iteration(
                                    conv_state, [r.id for r in recs],
                                )
                                conv_state.has_blocking_findings = any(
                                    is_blocking_impact(
                                        r,
                                        demote_low_impact_medium=calibration_lookup,
                                    )
                                    for r in recs
                                )
                                last_iter_high_critical = [
                                    r for r in recs
                                    if r.severity.lower() in ("critical", "high")
                                ]
                                continue
                        if getattr(args, "auto_reconcile_on_drift", True):
                            from plan_tool.auto_reconcile import (
                                run_auto_reconcile_on_drift,
                            )
                            run_auto_reconcile_on_drift(
                                drifted=post_drifted,
                                file_to_step=_file_to_step,
                                plan_path=plan_path,
                                plan_slug=args.name,
                                repo_root=ctx.repo_root,
                                run_logger=run_logger,
                            )
                        _emit_scope_guard_plan(
                            scope_buffer,
                            plan_path=plan_path,
                            plan_slug=args.name,
                            ctx=ctx,
                        )
                        return

                # ``state.work_landed_in_loop`` is now flipped
                # inside the action_fn after each kept apply, so we don't
                # set a local flag here. The next pre-iter drift check
                # reads ``state.work_landed_in_loop`` directly.

                record_iteration(conv_state, [r.id for r in recs])
                conv_state.has_blocking_findings = any(
                    is_blocking_impact(
                        r, demote_low_impact_medium=calibration_lookup,
                    )
                    for r in recs
                )
                # Refresh the HIGH/CRITICAL window so the max_iterations
                # safety warning fires off the most recent round's findings,
                # not iteration 0's.
                last_iter_high_critical = [
                    r for r in recs if r.severity.lower() in ("critical", "high")
                ]


def _walk_with_reconcile_phase(
    saved,
    action_fn,
    state: WalkState,
    *,
    run_logger: Optional[RunLogWriter],
    step_id: Optional[int],
) -> None:
    """Run ``walk_recommendations`` wrapped in a ``reconcile_walk`` phase.

    When ``run_logger`` is None this is a transparent passthrough so
    callers that don't bind a logger (``cmd_review``, ``cmd_review_walk``)
    keep working unchanged.
    """
    if run_logger is None:
        walk_recommendations(saved, action_fn=action_fn, state=state)
        return
    run_logger.phase_start(
        "reconcile_walk",
        step_id=step_id,
        rec_count=len(saved.recommendations),
    )
    walk_t0 = time.monotonic()
    outcome = "success"
    try:
        walk_recommendations(saved, action_fn=action_fn, state=state)
    except Exception:
        outcome = "error"
        raise
    finally:
        run_logger.phase_end(
            "reconcile_walk",
            duration_ms=int((time.monotonic() - walk_t0) * 1000),
            outcome=outcome,
        )


def _find_saved_detail_reconcile_for_step(
    plan_slug: str, repo_root: Path, *, step_id: int,
    plan_path: Optional[Path] = None,
):
    """Newest detail-reconcile save (``*-detail-reconcile.json``) for ``step_id``."""
    return _find_saved_for_step(
        _RECONCILE_KINDS["detail-reconcile"], plan_slug, repo_root,
        step_id=step_id, plan_path=plan_path,
    )


def _ask_reuse_saved_detail_reconcile(
    saved_path: Path,
    saved,
    plan_slug: str,
    *,
    repo_root: Path,
    input_fn=None,
) -> bool:
    """Prompt to reuse a saved detail-reconcile (default no)."""
    return _ask_reuse_saved(
        _RECONCILE_KINDS["detail-reconcile"], saved_path, saved, plan_slug,
        repo_root=repo_root, input_fn=input_fn,
    )


def _prompt_reuse_saved_detail_reconcile(
    ctx: PlanToolContext,
    plan_slug: str,
    args: argparse.Namespace,
    *,
    step_id: int,
    input_fn=None,
    plan_path: Optional[Path] = None,
) -> Optional[Path]:
    """Offer to walk a saved detail-reconcile instead of a fresh claude run."""
    return _prompt_reuse_saved(
        _RECONCILE_KINDS["detail-reconcile"], ctx, plan_slug, args,
        step_id=step_id, input_fn=input_fn, plan_path=plan_path,
    )


def _find_saved_run_reconcile_for_step(
    plan_slug: str, repo_root: Path, *, step_id: int,
    plan_path: Optional[Path] = None,
):
    """Newest run-reconcile save (``*-run-reconcile.json``) for ``step_id``."""
    return _find_saved_for_step(
        _RECONCILE_KINDS["run-reconcile"], plan_slug, repo_root,
        step_id=step_id, plan_path=plan_path,
    )


def _ask_reuse_saved_run_reconcile(
    saved_path: Path,
    saved,
    plan_slug: str,
    *,
    repo_root: Path,
    input_fn=None,
) -> bool:
    """Prompt to reuse a saved run-reconcile (default no)."""
    return _ask_reuse_saved(
        _RECONCILE_KINDS["run-reconcile"], saved_path, saved, plan_slug,
        repo_root=repo_root, input_fn=input_fn,
    )


def _prompt_reuse_saved_run_reconcile(
    ctx: PlanToolContext,
    plan_slug: str,
    args: argparse.Namespace,
    *,
    step_id: int,
    input_fn=None,
    plan_path: Optional[Path] = None,
) -> Optional[Path]:
    """Offer to walk a saved run-reconcile instead of a fresh claude run."""
    return _prompt_reuse_saved(
        _RECONCILE_KINDS["run-reconcile"], ctx, plan_slug, args,
        step_id=step_id, input_fn=input_fn, plan_path=plan_path,
    )


def _walk_saved_run_reconcile(
    *,
    ctx: PlanToolContext,
    path: Path,
    plan_name: str,
    reuse_path: Path,
    yes: bool,
    run_logger: RunLogWriter,
) -> int:
    """Load + redirect-replay a saved run-reconcile (no interactive walk)."""
    return _walk_saved(
        _RECONCILE_KINDS["run-reconcile"],
        ctx=ctx, path=path, plan_name=plan_name,
        reuse_path=reuse_path, yes=yes, run_logger=run_logger,
    )
