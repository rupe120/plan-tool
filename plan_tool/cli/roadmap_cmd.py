"""Roadmap command module — the ``roadmap`` verb.

``plan-tool roadmap <slug> --from-existing <concept.md>`` stages a concept brief
through the gated architecture stages and publishes one root version under
``docs/implementation-plans/roadmaps/<slug>/`` — one rung above ``create``. A
failed run keeps its passed stages in a resume directory and the next plain run
continues from them; a roadmap with an accepted head is refused.

``plan-tool roadmap <slug> --apply [-y]`` is a separate apply-only mode: it
reads the accepted version's roadmap artifact, promotes slug-directory draft seeds into
the default seed directory after opt-in confirm (or ``-y``), and prints create handoff
lines against the promoted paths. It never runs the stage table or invokes the
backend.

``plan-tool roadmap <slug> --refresh-seeds`` is the deliberate derived-seed
refresh: roadmap revisions invalidate seeds but never overwrite them. This mode
reprocesses the accepted roadmap against the current
repository, restores a consumed seed when its source sits in ``archive/``, and
writes a before/after report beside the roadmap.

``plan-tool roadmap <slug> --materialize [PLAN_ID]`` selectively regenerates
recoverable draft seeds without running the roadmap stages. With no id it
processes every recoverable plan; with an id it processes only that plan.

``plan-tool roadmap <slug> --accept-seed PLAN_ID`` accepts one validated,
directly edited digest-mismatched draft without invoking the backend. It preserves
the draft bytes and re-syncs the promoted copy only when the seed state records
it published; an unpublished seed's existing destination file is left untouched.

``plan-tool roadmap <slug> --view {summary,walk,ledger,index,seeds,html}
[--mode {current,review}] [--id ROW_ID] [--output PATH]`` is a third inspection
mode: it loads whichever of the four
artifacts of the accepted version parse
(:func:`plan_tool.roadmap_view.load_roadmap`) and prints a compact review
summary or one of five detail views — the traceability walk, the decision
ledger, the reverse citation index, the draft-seed state report, or the
full-content HTML page (:func:`plan_tool.roadmap_html.render_roadmap_html`).
Like
``--apply``, it never runs the stage table or invokes the backend. ``--mode`` selects the design-state artifacts
(``current``, the default) or the review-channel view (``review``, which
additionally surfaces feedback rows and removals); ``--id`` scopes
``--view index`` to one row's citers; ``--output`` names where ``--view
html``'s page goes. All three are meaningful only alongside
``--view`` (``--id`` and ``--output`` only alongside their one view) —
argparse's mutually-exclusive-group machinery cannot express
that, so an explicit pre-dispatch check in ``cmd_roadmap`` rejects the
invalid combinations before any path resolution or disk read.

``html`` bypasses the report banner and writes
:data:`plan_tool.roadmap_html.REVIEW_FILENAME` by default; ``--output -``
prints the document to stdout.

``plan-tool roadmap <slug> --settle-decision SELECTOR --settlement-evidence
SELECTOR --confirm-decision-settlement`` is one exclusive, operator-confirmed
action that moves a single Roadmap-derived ``pending`` decision to
``settled``, bound to a named, live feedback row that cites it. It invokes no
backend and dispatches straight to the enrolled runner; a folder with no
accepted version is refused with the no-published-version error. Accepts no
companion roadmap option.

Deliberately thin: the stage table, the gates, the retry budget, and the
artifact contract all live in :mod:`plan_tool.roadmap` /
:mod:`plan_tool.roadmap_gates` / :mod:`plan_tool.roadmap_artifacts`; ordinary
roadmap views live in :mod:`plan_tool.roadmap_view`. This module owns path
resolution, the exit-code mapping, and the operator summary — the three
things ``run_roadmap`` deliberately does not do.

Stage runs stay non-interactive: no prompt or TTY branch in the stage loop.
``--apply`` is the opt-in confirm surface for seed promotion.

Like every per-intent command module this imports only the cycle-free leaves
(:mod:`plan_tool.cli.console` / :mod:`plan_tool.cli.context` /
:mod:`plan_tool.cli.parser`) and domain packages — never
:mod:`plan_tool.cli.app`. ``cmd_roadmap`` exposes an ``invoker`` keyword seam
so tests pass a stub and never shell out; dispatch calls it with the
``Namespace`` alone.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Literal, Optional

from plan_tool.seed_paths import default_seeds_dir
from plan_tool.cli.console import _short_path, render_roadmap_view
from plan_tool.cli.context import _resolve_cmd_repo_root
from plan_tool.cli.parser import Handler
from plan_tool.create import resolve_output_dir
from plan_tool.fileio import atomic_write_text
from plan_tool.locator import resolve_explicit_plans_dir
from plan_tool.roadmap import (
    stage_resume_directory,
    ACCEPT_OUTCOME_ACCEPTED,
    ACCEPT_OUTCOME_REFUSED,
    APPLY_OUTCOME_APPLIED,
    APPLY_OUTCOME_RECOMMENDED,
    APPLY_OUTCOME_REFUSED,
    FAILURE_AUTHORED_REVIEW_ROWS,
    FAILURE_GATES,
    FAILURE_INVOKE,
    OUTCOME_COMPLETED,
    OUTCOME_COMPLETED_NO_CHANGE,
    OUTCOME_STAGE_INVALID,
    RoadmapApplyResult,
    RoadmapEnvironmentalError,
    RoadmapError,
    RoadmapResult,
    RoadmapRunStartedWriterGuardError,
    RoadmapSeedAcceptResult,
    RoadmapSeedRefreshResult,
    SEED_REFRESH_OUTCOME_APPLIED,
    SEED_REFRESH_OUTCOME_EXHAUSTED,
    SEED_REFRESH_OUTCOME_PARTIAL,
    StageInvoker,
    _materialize_seed_rows,
    _RoadmapCommandLifecycle,
    _roadmap_command_lifecycle,
    _roadmap_writer_owner,
    accept_roadmap_seed,
    apply_roadmap_seeds,
    emit_roadmap_terminal_status,
    is_successful_roadmap_outcome,
    load_accepted_plans_artifact,
    ordered_plan_seed_targets,
    ordering_plans_bijection_error,
    refresh_roadmap_seeds,
    run_roadmap,
    write_seed_refresh_report,
)
from plan_tool.roadmap_artifacts import (
    COMPONENTS_FILENAME,
    CONSTRAINTS_FILENAME,
    DecisionStatus,
    FeedbackState,
    PLANS_FILENAME,
    RoadmapArtifactError,
    load_components_artifact,
    load_constraints_artifact,
    load_plans_artifact,
    parse_components_artifact,
    parse_constraints_artifact,
    resolve_plan_seed_dest,
    roadmap_dir,
)
from plan_tool.roadmap_decision_settlement_enrolled import (
    respond_enrolled_decision_settlement,
    run_enrolled_decision_settlement,
)
from plan_tool.roadmap_decision_settlement_run import DecisionSettlementRunResult
from plan_tool.roadmap_html import render_roadmap_html, review_path
from plan_tool.roadmap_compare_render import (
    render_comparison_json,
    render_patch_comparison,
    render_terminal_comparison,
)
from plan_tool.roadmap_compare_run import RoadmapComparisonRunError, run_roadmap_comparison
from plan_tool.roadmap_stack_summary import (
    candidate_stack_summary_lines,
    pending_anchor_ids,
    stack_summary_lines,
)
from plan_tool.roadmap_seed_manifest import (
    DRAFT_SEED_STATE_CURRENT,
    DRAFT_SEED_STATE_DIGEST_MISMATCHED,
    DRAFT_SEED_STATE_DUPLICATE,
    DRAFT_SEED_STATE_MALFORMED,
    DRAFT_SEED_STATE_MISSING,
    DRAFT_SEED_STATE_PATH_ESCAPING,
    DRAFT_SEED_STATE_STALE,
    NoPublishedRoadmapVersionError,
    classify_draft_seeds,
    leftover_top_level_artifacts,
    no_published_version_message,
    find_orphan_seed_records,
)
from plan_tool.roadmap_revision_publish import (
    RoadmapWriterGuardError,
    RoadmapWriterToken,
    require_roadmap_writer_token,
    roadmap_writer_guard,
)
from plan_tool import roadmap_candidate_narrative
from plan_tool.roadmap_candidate_run import (
    CandidateProposalResult,
    candidate_stack_route,
    load_candidate_admission,
    load_stored_candidate_proposal,
    run_initial_candidate_proposal,
)
from plan_tool.roadmap_candidate import (
    _wire_value,
    candidate_prose_amendment_diffs,
    candidate_prose_correction_diffs,
)
from plan_tool.roadmap_candidate_review import (
    CandidateReviewResult,
    CandidateStackView,
    answer_candidate_question,
    build_candidate_stack_view,
    decide_structural_candidate,
    discard_candidate_review,
    generate_candidate_question,
    reject_candidate_review,
)
from plan_tool.roadmap_diff import RoadmapDiff
from plan_tool.roadmap_versions import (
    VERSION_ARTIFACT_KEYS,
    accepted_head_path,
    load_resolved_stored_version,
    version_namespace_path,
)
from plan_tool.roadmap_feedback_ledger import LedgerTarget
from plan_tool.roadmap_feedback_ledger_run import (
    LedgerActionResult,
    close_reviewer_feedback,
    defer_reviewer_feedback,
    edit_reviewer_feedback,
    reopen_reviewer_feedback,
    retarget_reviewer_feedback,
    submit_reviewer_feedback,
)
from plan_tool.roadmap_version_promotion import (
    PROMOTION_OUTCOME_ALREADY_PROMOTED,
    RoadmapVersionPromotionError,
    promote_review_seal,
)
from plan_tool.roadmap_seed_state import (
    RoadmapSeedStateError,
)
from plan_tool.roadmap_view import (
    LoadedRoadmap,
    MODE_CURRENT,
    MODE_REVIEW,
    load_roadmap,
    render_decision_ledger,
    render_roadmap_summary,
    render_reverse_index,
    render_seed_state_view,
    render_traceability_walk,
    summarize_seed_lifecycle,
)
from plan_tool.style import detail, error, info, note, success, warn

# A pre-flight failure is input-shaped, so it maps to argparse's usage code
# (``cmd_scope_out``'s out-of-order range is the precedent); a stage that
# spent its budget is a verb that ran but did not finish, which is
# ``cmd_annotate``'s 1.
_RC_USAGE = 2
_RC_INCOMPLETE = 1
_RC_PARTIAL = 3

_MATERIALIZE_ALL = object()
_MATERIALIZABLE_STATES = frozenset(
    {
        DRAFT_SEED_STATE_MISSING,
        DRAFT_SEED_STATE_STALE,
        DRAFT_SEED_STATE_MALFORMED,
        DRAFT_SEED_STATE_PATH_ESCAPING,
        DRAFT_SEED_STATE_DIGEST_MISMATCHED,
    }
)

class _TrackRoadmapMode(argparse.Action):
    """Record a broad-mode occurrence while retaining its normal final value."""

    def __call__(self, parser, namespace, values, option_string=None) -> None:
        value = self.const if self.nargs == 0 else values
        occurrences = list(getattr(namespace, "_roadmap_mode_occurrences", ()))
        occurrences.append((option_string or self.option_strings[0], value))
        setattr(namespace, "_roadmap_mode_occurrences", tuple(occurrences))
        setattr(namespace, self.dest, value)


class _TrackExclusiveOption(argparse.Action):
    """Keep every exclusive-option occurrence while exposing its final value."""

    def __call__(self, parser, namespace, values, option_string=None) -> None:
        value = self.const if self.const is not None and values == [] else values
        occurrences_name = f"_{self.dest}_occurrences"
        occurrences = list(getattr(namespace, occurrences_name, ()))
        occurrences.append(value)
        setattr(namespace, occurrences_name, tuple(occurrences))
        setattr(namespace, self.dest, value)


def _restore_broad_mode_usage_group(parser: argparse.ArgumentParser) -> bool:
    """Restore grouped broad-mode usage when argparse exposes its hook."""
    group = parser.add_mutually_exclusive_group()
    group_actions = getattr(group, "_group_actions", None)
    parser_actions = getattr(parser, "_actions", None)
    if not isinstance(group_actions, list) or not isinstance(parser_actions, list):
        return False
    group_actions.extend(
        action for action in parser_actions if isinstance(action, _TrackRoadmapMode)
    )
    return True


def _reject_incompatible_broad_modes(args: argparse.Namespace) -> int | None:
    """Replay argparse's existing broad-mode exclusion after collecting facts."""
    occurrences = getattr(args, "_roadmap_mode_occurrences", ())
    if not occurrences:
        return None

    first_option = occurrences[0][0]
    for option, _value in occurrences[1:]:
        if option == first_option:
            continue
        message = f"argument {option}: not allowed with argument {first_option}"
        parser = getattr(args, "_roadmap_mode_parser", None)
        if parser is None:
            error(message)
            return _RC_USAGE
        _restore_broad_mode_usage_group(parser)
        try:
            parser.error(message)
        except SystemExit as exc:
            return exc.code
    return None


def _roadmap_stage_started(exc: BaseException, *, default: bool) -> bool:
    """Read ``roadmap_stage_started``; each caller names its own default —
    ``True`` for the environmental family (usually already mid-run),
    ``False`` for the domain-refusal family (usually preflight)."""
    return getattr(exc, "roadmap_stage_started", default)


def _materialize_disposition_emitted(exc: BaseException) -> bool:
    """Whether ``_cmd_roadmap_materialize_owned``'s own exception handling
    already emitted a disposition for ``exc`` — the one place this fact's
    attribute name is read, mirroring ``_roadmap_stage_started``."""
    return getattr(exc, "materialize_disposition_emitted", False)


def _mark_materialize_disposition_emitted(exc: BaseException) -> None:
    """The one place this fact's attribute name is set."""
    exc.materialize_disposition_emitted = True


def cmd_roadmap(args: argparse.Namespace, *, invoker: Optional[StageInvoker] = None) -> int:
    """Stage, apply, materialize, or render ``args.slug``'s roadmap artifacts.

    Resolves the repo root via :func:`_resolve_cmd_repo_root` rather than
    ``_load_context``: this verb's primary audience is a project with nothing
    in ``.plan-tool/plans.json`` yet, and manifest-mode context building raises
    ``ManifestError`` on exactly that state.

    With ``--apply``, delegates to :func:`apply_roadmap_seeds` and never calls
    ``run_roadmap``. With ``--accept-seed``, delegates to
    :func:`accept_roadmap_seed` and invokes no backend. With ``--materialize``,
    delegates to :func:`_cmd_roadmap_materialize` and invokes only the standalone seed
    materializer. Ordinary ``--view`` values delegate to
    :func:`_cmd_roadmap_view`, which loads the roadmap off disk. No view calls ``run_roadmap`` or
    ``apply_roadmap_seeds`` or invokes a backend. A stage run takes
    its concept brief from ``--from-existing``.

    ``--mode``, ``--id``, and ``--output`` are meaningful only alongside
    ``--view`` —
    argparse's mutually-exclusive-group machinery cannot express that, so a
    pre-dispatch check here rejects ``--mode``/``--id``/``--output`` without
    ``--view``, ``--id`` with a ``--view`` other than ``index``, and
    ``--output`` with a ``--view`` other than ``html``, ahead of every
    dispatch branch (including ``--apply`` and ``--accept-seed``).

    Returns 2 for a pre-flight failure (bad slug, no supplied brief, a stage
    run beside an accepted head, a headless folder holding pre-head state, a
    brief that changed since the held stages were written, a refused apply
    preflight or seed accept,
    ``--mode``/
    ``--id``/``--output`` supplied without ``--view``, ``--id`` supplied with
    a ``--view`` other than ``index``, ``--output`` supplied with a ``--view``
    other than ``html``, an explicit ``--output`` naming a directory rather
    than a file, an invalid slug under ``--view``, or a ``--view``
    whose roadmap directory does not exist on disk), 1 when a stage exhausted
    its retry budget, an explicit seed regeneration exhausts every plan, an
    output destination could not be written or checked (e.g. permission
    denied on an intermediate directory), or the computed default page
    collides with a directory — grouped with the write failure, not the
    pre-flight rejections above, since all are environmental
    failures-to-complete rather than a fixable bad argument, 3
    when one lands only part of its batch, 130 when an operator's Ctrl-C
    (``KeyboardInterrupt``) lands anywhere in the dispatch (one handler
    covers every branch; the ``run_roadmap``/``apply_roadmap_seeds`` call
    it wraps has already run its own ``run_end``/in-flight cleanup by the
    time this returns), and 0 for a completed run, a recommend-only/applied
    apply, a completed ``--accept-seed``, or a completed ``--view`` render (unconditionally, for any
    combination of absent or unparseable artifacts short of a missing
    roadmap directory), including a run whose artifacts carry ``pending``
    decisions, decisions this revision newly settled, or feedback awaiting
    review.

    See ``docs/reference/contracts/process.md`` for roadmap mode authority boundaries.
    """
    has_decision_settlement = _has_decision_settlement(args)
    has_comparison = _has_roadmap_comparison(args)
    if has_comparison:
        if not _option_occurrences(args, "compare"):
            error("--comparison-base/--comparison-target/--comparison-output require --compare")
            return _RC_USAGE
        if _roadmap_comparison_has_conflict(args):
            error("--compare accepts no companion roadmap options")
            return _RC_USAGE
        repo_root = _resolve_cmd_repo_root(args)
        plans_dir = resolve_explicit_plans_dir(args.plans_dir)
        if plans_dir is None:
            plans_dir = resolve_output_dir(repo_root)
        try:
            return _cmd_roadmap_comparison(args, plans_dir=plans_dir)
        except KeyboardInterrupt:
            error("interrupted")
            return 130
    if _has_candidate_lifecycle_action(args):
        if _candidate_lifecycle_has_conflict(args):
            error("candidate lifecycle actions accept exactly one action with no companion roadmap options")
            return _RC_USAGE
        repo_root = _resolve_cmd_repo_root(args)
        plans_dir = resolve_explicit_plans_dir(args.plans_dir)
        if plans_dir is None:
            plans_dir = resolve_output_dir(repo_root)
        try:
            roadmap_dir(plans_dir, args.slug)
        except (TypeError, ValueError) as exc:
            error(str(exc))
            return _RC_USAGE
        try:
            return _cmd_roadmap_candidate_lifecycle(
                args,
                repo_root=repo_root,
                plans_dir=plans_dir,
                invoker=invoker,
            )
        except KeyboardInterrupt:
            error("interrupted")
            return 130
    if has_decision_settlement:
        repo_root = _resolve_cmd_repo_root(args)
        plans_dir = resolve_explicit_plans_dir(args.plans_dir)
        if plans_dir is None:
            plans_dir = resolve_output_dir(repo_root)
        try:
            return _cmd_roadmap_decision_settlement(args, plans_dir=plans_dir)
        except KeyboardInterrupt:
            error("interrupted")
            return 130
    incompatibility_rc = _reject_incompatible_broad_modes(args)
    if incompatibility_rc is not None:
        return incompatibility_rc

    repo_root, plans_dir = _resolve_roadmap_execution_paths(args)

    if args.view is None:
        if args.mode is not None:
            error("--mode requires --view")
            return _RC_USAGE
        if args.id is not None:
            error("--id requires --view index")
            return _RC_USAGE
        if args.output is not None:
            error("--output requires --view html")
            return _RC_USAGE
    else:
        if args.view != "index" and args.id is not None:
            error("--id is only valid with --view index")
            return _RC_USAGE
        if args.view != "html" and args.output is not None:
            error("--output is only valid with --view html")
            return _RC_USAGE

    # One handler for the whole dispatch: every branch below (stage run,
    # --refresh-seeds, --accept-seed, --materialize, --apply, --view) invokes
    # the backend or reads disk the
    # same non-interactive way, so an operator's Ctrl-C maps to the same
    # clean exit regardless of which one was in flight. ``run_roadmap``,
    # ``refresh_roadmap_seeds``, and ``apply_roadmap_seeds`` have already run
    # their own ``run_end``/in-flight cleanup by the time the exception reaches
    # here.
    try:
        if args.apply:
            return _cmd_roadmap_apply(args, repo_root=repo_root, plans_dir=plans_dir)

        if getattr(args, "refresh_seeds", False):
            return _cmd_roadmap_refresh_seeds(
                args, repo_root=repo_root, plans_dir=plans_dir, invoker=invoker
            )

        if getattr(args, "accept_seed", None) is not None:
            return _cmd_roadmap_accept_seed(args, repo_root=repo_root, plans_dir=plans_dir)

        if getattr(args, "materialize", None) is not None:
            return _cmd_roadmap_materialize(
                args, repo_root=repo_root, plans_dir=plans_dir, invoker=invoker
            )

        if args.view is not None:
            return _cmd_roadmap_view(args, plans_dir=plans_dir, repo_root=repo_root)

        # Only forward the seam when the caller supplied one, so the default
        # dispatch path leaves ``run_roadmap``'s own shell invoker in place.
        extra = {"invoker": invoker} if invoker is not None else {}
        try:
            result = run_roadmap(
                args.slug,
                repo_root=repo_root,
                plans_dir=plans_dir,
                brief_path=args.from_existing,
                status_callback=note,
                **extra,
            )
        except (OSError, RoadmapEnvironmentalError) as exc:
            error(str(exc))
            if _roadmap_stage_started(exc, default=True) is False:
                _emit_roadmap_terminal_disposition(args.slug, "preflight-refused")
                return _RC_USAGE
            _emit_roadmap_terminal_disposition(args.slug, "error")
            return _RC_INCOMPLETE
        except RoadmapRunStartedWriterGuardError as exc:
            error(str(exc))
            _emit_roadmap_terminal_disposition(args.slug, "error")
            return _RC_INCOMPLETE
        except (RoadmapError, RoadmapArtifactError, RoadmapWriterGuardError) as exc:
            error(str(exc))
            if _roadmap_stage_started(exc, default=False):
                _emit_roadmap_terminal_disposition(args.slug, "error")
                return _RC_INCOMPLETE
            _emit_roadmap_terminal_disposition(args.slug, "preflight-refused")
            return _RC_USAGE
        except Exception:
            _emit_roadmap_terminal_disposition(args.slug, "unexpected-error")
            raise

        if is_successful_roadmap_outcome(result.outcome):
            if result.outcome == OUTCOME_COMPLETED:
                _print_completed(
                    result, slug=args.slug, repo_root=repo_root, plans_dir=plans_dir
                )
            else:
                _print_completed_no_change(result, slug=args.slug)
            rc = 0
        elif result.outcome == OUTCOME_STAGE_INVALID:
            _print_invalid(result, slug=args.slug)
            rc = _RC_INCOMPLETE
        else:
            _print_exhausted(result, slug=args.slug, repo_root=repo_root)
            rc = _RC_INCOMPLETE
        # All three blocks are emitted for every outcome. Feedback leads the
        # review channel; newly-settled follows because it is the adjacent
        # decision-authority question.
        for line in _feedback_summary_lines(result):
            detail(line)
        for line in _newly_settled_summary_lines(result):
            detail(line)
        for line in _seed_invalidation_summary_lines(result, slug=args.slug):
            detail(line)
        emit_roadmap_terminal_status(note, slug=args.slug, result=result)
        return rc
    except KeyboardInterrupt:
        error("interrupted")
        return 130


def _emit_roadmap_terminal_disposition(slug: object, disposition: str) -> None:
    """Make one best-effort terminal-status attempt for a non-result exit."""
    emit_roadmap_terminal_status(note, slug=slug, disposition=disposition)


def _resolve_roadmap_execution_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    """Resolve execution paths while preserving an unexpected terminal fact."""
    try:
        repo_root = _resolve_cmd_repo_root(args)
        plans_dir = resolve_explicit_plans_dir(args.plans_dir)
        if plans_dir is None:
            plans_dir = resolve_output_dir(repo_root)
        return repo_root, plans_dir
    except Exception:
        _emit_roadmap_terminal_disposition(args.slug, "unexpected-error")
        raise


def _has_decision_settlement(args: argparse.Namespace) -> bool:
    """Whether any part of the confirmed decision-settlement triple appeared."""
    return bool(
        _option_occurrences(args, "settle_decision")
        or _option_occurrences(args, "settlement_evidence")
        or _option_occurrences(args, "confirm_decision_settlement")
    )


def _has_roadmap_comparison(args: argparse.Namespace) -> bool:
    """Whether any comparison selector or output choice appeared."""
    return any(
        _option_occurrences(args, name) for name in ("compare", "comparison_base", "comparison_target")
    ) or bool(getattr(args, "_comparison_output_occurrences", ())) or getattr(
        args, "comparison_output", "cards"
    ) != "cards"


def _has_candidate_lifecycle_action(args: argparse.Namespace) -> bool:
    """Whether any ledger or candidate lifecycle input appeared."""
    return _selector_free_revise_feedback_selected(args) or any(
        _option_occurrences(args, name)
        for name in (
            "propose_candidate",
            "submit_feedback",
            "retarget_feedback",
            "edit_feedback",
            "defer_feedback",
            "close_feedback",
            "reopen_ledger_feedback",
            "feedback_target",
            "feedback_request",
            "review_candidate",
            "answer_question",
            "reject_candidate",
            "discard_candidate",
            "decide_candidate",
            "candidate_decision",
            "candidate_correction",
            "confirm_stack_digest",
            "answer",
            "promote_review_seal",
            "respond_decision_settlement",
            "decision_settlement_yes",
            "decision_settlement_no",
        )
    )


def _selector_free_revise_feedback_selected(args: argparse.Namespace) -> bool:
    """Recognize only the parser's zero-argument ordinary-feedback action."""
    occurrences = _option_occurrences(args, "revise_feedback")
    return bool(occurrences) and all(value is True for value in occurrences)


def _option_occurrences(args: argparse.Namespace, name: str) -> tuple[object, ...]:
    """Read one option's parser history, with a direct-call fallback."""
    occurrences = tuple(getattr(args, f"_{name}_occurrences", ()))
    if occurrences:
        return occurrences
    value = getattr(args, name, None)
    return () if value is None else (value,)


def _view_occurrences(args: argparse.Namespace) -> tuple[object, ...]:
    """Read every view request, including direct-call fallbacks."""
    occurrences = tuple(
        value
        for option, value in getattr(args, "_roadmap_mode_occurrences", ())
        if option == "--view"
    )
    if occurrences:
        return occurrences
    value = getattr(args, "view", None)
    return () if value is None else (value,)


def _broad_mode_companions_present(args: argparse.Namespace) -> tuple[bool, ...]:
    """Whether any ordinary broad-mode companion flag was supplied.

    Shared by every exclusive-mode conflict predicate below; each caller
    layers its own mode-specific sibling checks (the *other* exclusive modes
    it must also reject) on top of this common set, so a new exclusive mode
    only has to be added to each sibling predicate once, not reinvented here.
    """
    return (
        args.from_existing is not None,
        args.apply,
        getattr(args, "refresh_seeds", False),
        getattr(args, "accept_seed", None) is not None,
        getattr(args, "materialize", None) is not None,
        args.yes,
        args.mode is not None,
        args.id is not None,
        args.output is not None,
    )


def _roadmap_comparison_has_conflict(args: argparse.Namespace) -> bool:
    """Require one comparison request with only its closed selectors."""
    return any(
        (
            len(_option_occurrences(args, "compare")) != 1,
            len(_option_occurrences(args, "comparison_base")) > 1,
            len(_option_occurrences(args, "comparison_target")) > 1,
            len(_option_occurrences(args, "comparison_output")) > 1,
            getattr(args, "comparison_output", "cards") not in {"cards", "patch", "json"},
            bool(_view_occurrences(args)),
            _has_decision_settlement(args),
            _has_candidate_lifecycle_action(args),
            getattr(args, "revise_feedback", None) is not None,
            *_broad_mode_companions_present(args),
        )
    )


def _cmd_roadmap_comparison(args: argparse.Namespace, *, plans_dir: Path) -> int:
    """Run one bound comparison and print the selected renderer unchanged."""
    renderers = {
        "cards": render_terminal_comparison,
        "patch": render_patch_comparison,
        "json": render_comparison_json,
    }
    try:
        comparison = run_roadmap_comparison(
            plans_dir=plans_dir,
            slug=args.slug,
            base_version_id=args.comparison_base,
            target_version_id=args.comparison_target,
        )
        output = renderers[args.comparison_output](comparison)
    except (RoadmapComparisonRunError, RoadmapArtifactError, KeyError, ValueError, TypeError) as exc:
        error(str(exc))
        return _RC_USAGE
    print(output, end="")
    return 0


def _candidate_lifecycle_has_conflict(args: argparse.Namespace) -> bool:
    """Require one exact lifecycle transition before resolving any paths."""
    action_occurrences = {
        name: _option_occurrences(args, name)
        for name in (
            "propose_candidate",
            "submit_feedback",
            "retarget_feedback",
            "edit_feedback",
            "defer_feedback",
            "close_feedback",
            "reopen_ledger_feedback",
            "review_candidate",
            "answer_question",
            "reject_candidate",
            "discard_candidate",
            "decide_candidate",
            "promote_review_seal",
            "respond_decision_settlement",
        )
    }
    if _selector_free_revise_feedback_selected(args):
        action_occurrences["revise_feedback"] = (True,)
    answer_occurrences = _option_occurrences(args, "answer")
    target_occurrences = _option_occurrences(args, "feedback_target")
    request_occurrences = _option_occurrences(args, "feedback_request")
    yes_occurrences = _option_occurrences(args, "decision_settlement_yes")
    no_occurrences = _option_occurrences(args, "decision_settlement_no")
    candidate_decision_occurrences = _option_occurrences(args, "candidate_decision")
    candidate_correction_occurrences = _option_occurrences(args, "candidate_correction")
    confirm_digest_occurrences = _option_occurrences(args, "confirm_stack_digest")
    selected_actions = tuple(
        name for name, occurrences in action_occurrences.items() if occurrences
    )
    answering = bool(action_occurrences["answer_question"])
    submitting = bool(action_occurrences["submit_feedback"])
    retargeting = bool(action_occurrences["retarget_feedback"])
    editing = bool(action_occurrences["edit_feedback"])
    responding = bool(action_occurrences["respond_decision_settlement"])
    deciding_candidate = bool(action_occurrences["decide_candidate"])
    return any(
        (
            len(selected_actions) != 1,
            any(len(occurrences) != 1 for occurrences in action_occurrences.values() if occurrences),
            (len(answer_occurrences) != 1) if answering else bool(answer_occurrences),
            (len(target_occurrences) != 1) if submitting or retargeting else bool(target_occurrences),
            (len(request_occurrences) != 1) if submitting else bool(request_occurrences),
            editing and not (len(request_occurrences) == 1 or len(target_occurrences) == 1),
            editing and len(request_occurrences) > 1,
            editing and len(target_occurrences) > 1,
            (len(yes_occurrences) + len(no_occurrences) != 1) if responding else bool(yes_occurrences or no_occurrences),
            deciding_candidate and len(candidate_decision_occurrences) != 1,
            not deciding_candidate and bool(candidate_decision_occurrences),
            deciding_candidate and candidate_decision_occurrences == ("edit",) and (
                len(candidate_correction_occurrences) != 1
                or not bool(candidate_correction_occurrences[-1])
            ),
            deciding_candidate and candidate_decision_occurrences != ("edit",)
            and bool(candidate_correction_occurrences),
            len(confirm_digest_occurrences) > 1,
            bool(confirm_digest_occurrences)
            and not (deciding_candidate and candidate_decision_occurrences == ("approve",)),
            _has_decision_settlement(args),
            bool(_view_occurrences(args)),
            *_broad_mode_companions_present(args),
        )
    )


def _revise_feedback_has_conflict(args: argparse.Namespace) -> bool:
    """Compatibility predicate for retired selector-bound route assertions."""
    return _candidate_lifecycle_has_conflict(args)


def _cmd_roadmap_candidate_lifecycle(
    args: argparse.Namespace,
    *,
    repo_root: Path,
    plans_dir: Path,
    invoker: Optional[StageInvoker],
) -> int:
    """Route one preflight-approved ledger or candidate lifecycle action."""
    if _selector_free_revise_feedback_selected(args) or _option_occurrences(args, "propose_candidate"):
        return _cmd_roadmap_propose_candidate(
            args, repo_root=repo_root, plans_dir=plans_dir, invoker=invoker
        )
    if any(_option_occurrences(args, name) for name in (
        "submit_feedback", "retarget_feedback", "edit_feedback",
        "defer_feedback", "close_feedback", "reopen_ledger_feedback",
    )):
        return _cmd_roadmap_feedback_ledger(args, plans_dir=plans_dir)
    if _option_occurrences(args, "review_candidate"):
        return _cmd_roadmap_review_candidate(
            args, repo_root=repo_root, plans_dir=plans_dir, invoker=invoker
        )
    if _option_occurrences(args, "answer_question"):
        return _cmd_roadmap_answer_candidate_question(
            args, repo_root=repo_root, plans_dir=plans_dir, invoker=invoker
        )
    if _option_occurrences(args, "reject_candidate"):
        return _cmd_roadmap_candidate_resolution(args, plans_dir=plans_dir, reject=True)
    if _option_occurrences(args, "discard_candidate"):
        return _cmd_roadmap_candidate_resolution(args, plans_dir=plans_dir, reject=False)
    if _option_occurrences(args, "decide_candidate"):
        return _cmd_roadmap_structural_candidate_decision(
            args, repo_root=repo_root, plans_dir=plans_dir, invoker=invoker
        )
    if _option_occurrences(args, "respond_decision_settlement"):
        return _cmd_roadmap_decision_settlement_response(args, plans_dir=plans_dir)
    return _cmd_roadmap_promote_review_seal(args, plans_dir=plans_dir)


def _cmd_roadmap_propose_candidate(
    args: argparse.Namespace,
    *,
    repo_root: Path,
    plans_dir: Path,
    invoker: Optional[StageInvoker],
) -> int:
    """Delegate one selector-free batch proposal to its bounded domain runner."""
    try:
        result = run_initial_candidate_proposal(
            args.slug,
            None,
            repo_root=repo_root,
            plans_dir=plans_dir,
            invoker=invoker,
        )
    except ValueError as exc:
        error(str(exc))
        return _RC_USAGE
    stack_view: Optional[CandidateStackView] = None
    stack_error: Optional[Exception] = None
    if result.candidate is not None:
        # The derivation gates the build, so a stack with no structural hop prints today's output and
        # gains no failure mode beyond an unreadable hop; the proposal is already stored, so a failure
        # here cannot refuse it.
        try:
            if candidate_stack_route(
                plans_dir=plans_dir, slug=args.slug,
                tip_version_id=result.candidate.version_id,
                root_version_id=result.candidate.evidence.root_version_id,
            ).is_structural:
                stack_view = build_candidate_stack_view(
                    plans_dir=plans_dir, slug=args.slug, candidate=result.candidate
                )
        except (ValueError, OSError) as exc:
            stack_error = exc
    evidence_failures: list[Exception] = []

    def show_evidence() -> None:
        failure = _print_narrative_evidence_or_unavailable(
            plans_dir=plans_dir, slug=args.slug, initial=result.candidate, content=result.candidate.content
        )
        _print_candidate_stack_callout(
            plans_dir=plans_dir, slug=args.slug, initial=result.candidate, content=result.candidate.content
        )
        if failure is not None:
            evidence_failures.append(failure)

    _render_candidate_proposal_result(result, stack_view=stack_view, after_diff=show_evidence)
    evidence_error = evidence_failures[0] if evidence_failures else None
    if stack_error is not None:
        error(str(stack_error))
    if evidence_error is not None:
        error(str(evidence_error))
    if stack_error is not None or evidence_error is not None:
        return _RC_INCOMPLETE
    return _candidate_model_result_status(result.outcome)


def _parse_ledger_target(value: object) -> LedgerTarget:
    """Parse the compact CLI target selector without inspecting roadmap data."""
    if not isinstance(value, str):
        raise ValueError("feedback target is required")
    parts = value.split(":", 2)
    if len(parts) not in {2, 3}:
        raise ValueError("feedback target must be ARTIFACT:KIND[:ROW_ID]")
    return LedgerTarget(artifact_key=parts[0], kind=parts[1], row_id=parts[2] if len(parts) == 3 else None)


def _cmd_roadmap_feedback_ledger(args: argparse.Namespace, *, plans_dir: Path) -> int:
    """Forward one focused reviewer mutation to its ledger owner."""
    try:
        if _option_occurrences(args, "submit_feedback"):
            result = submit_reviewer_feedback(
                plans_dir=plans_dir, slug=args.slug,
                item_id=_option_occurrences(args, "submit_feedback")[-1],
                target=_parse_ledger_target(_option_occurrences(args, "feedback_target")[-1]),
                request=_option_occurrences(args, "feedback_request")[-1],
            )
        elif _option_occurrences(args, "retarget_feedback"):
            result = retarget_reviewer_feedback(
                plans_dir=plans_dir, slug=args.slug,
                item_id=_option_occurrences(args, "retarget_feedback")[-1],
                target=_parse_ledger_target(_option_occurrences(args, "feedback_target")[-1]),
            )
        elif _option_occurrences(args, "edit_feedback"):
            target_values = _option_occurrences(args, "feedback_target")
            request_values = _option_occurrences(args, "feedback_request")
            result = edit_reviewer_feedback(
                plans_dir=plans_dir, slug=args.slug,
                item_id=_option_occurrences(args, "edit_feedback")[-1],
                target=_parse_ledger_target(target_values[-1]) if target_values else None,
                request=request_values[-1] if request_values else None,
            )
        else:
            action = next((name for name in ("defer_feedback", "close_feedback", "reopen_ledger_feedback")
                           if _option_occurrences(args, name)), None)
            assert action is not None
            runners = {
                "defer_feedback": defer_reviewer_feedback,
                "close_feedback": close_reviewer_feedback,
                "reopen_ledger_feedback": reopen_reviewer_feedback,
            }
            result = runners[action](plans_dir=plans_dir, slug=args.slug, item_id=_option_occurrences(args, action)[-1])
    except (ValueError, OSError, RoadmapWriterGuardError) as exc:
        error(str(exc))
        return _RC_USAGE
    _render_ledger_action_result(result)
    return 0 if result.result == "updated" else _RC_USAGE


def _render_ledger_action_result(result: LedgerActionResult) -> None:
    """Render only the ledger owner's closed operation result."""
    print(f"feedback ledger: {result.result}")


def _cmd_roadmap_candidate_resolution(args: argparse.Namespace, *, plans_dir: Path, reject: bool) -> int:
    """Release only the exact active candidate through its review owner."""
    candidate_id = _option_occurrences(args, "reject_candidate" if reject else "discard_candidate")[-1]
    try:
        result = (reject_candidate_review if reject else discard_candidate_review)(
            args.slug, candidate_id, plans_dir=plans_dir
        )
    except ValueError as exc:
        error(str(exc))
        return _RC_USAGE
    print(f"candidate {'rejection' if reject else 'discard'}: {result.outcome}")
    if result.detail:
        print(f"reason: {result.detail}")
    return _candidate_model_result_status(result.outcome)


def _cmd_roadmap_structural_candidate_decision(
    args: argparse.Namespace,
    *,
    repo_root: Path,
    plans_dir: Path,
    invoker: Optional[StageInvoker],
) -> int:
    """Show one structural candidate's whole stack before applying its one decision.

    Approve is two invocations: without ``--confirm-stack-digest`` it prints the stack and its digest and
    writes nothing; with it, the library compares the digest under the writer guard before sealing.
    Edit and reject print the same stack first, take no confirm, and reject adds what it drops; an edit
    then prints its stored replacement's stack.
    See docs/implementation-plans/archive/2-roadmap-stack-aware-approval.md § "Architecture" (Digest).
    """
    candidate_id = _option_occurrences(args, "decide_candidate")[-1]
    decision = _option_occurrences(args, "candidate_decision")[-1]
    correction_values = _option_occurrences(args, "candidate_correction")
    correction = correction_values[-1] if correction_values else None
    confirm_values = _option_occurrences(args, "confirm_stack_digest")
    confirm_digest = confirm_values[-1] if confirm_values else None
    try:
        candidate = load_stored_candidate_proposal(
            plans_dir=plans_dir, slug=args.slug, candidate_version_id=candidate_id
        )
        admission = load_candidate_admission(plans_dir=plans_dir, slug=args.slug)
    except (ValueError, OSError) as exc:
        error(str(exc))
        return _RC_USAGE

    evidence = candidate.evidence
    if evidence.batch_receipt is None or evidence.normalized_operations is None:
        error("candidate is not a stored structural proposal")
        return _RC_USAGE
    try:
        stack_is_structural = candidate_stack_route(
            plans_dir=plans_dir, slug=args.slug,
            tip_version_id=candidate_id, root_version_id=evidence.root_version_id,
        ).is_structural
    except (ValueError, OSError) as exc:
        error(f"candidate stack route is underivable: {exc}")
        return _RC_USAGE
    if not stack_is_structural:
        error("candidate is not a stored structural proposal")
        return _RC_USAGE
    if admission is None or admission.candidate_version_id != candidate_id:
        error("candidate review accepts only the admitted initial candidate")
        return _RC_USAGE

    if decision == "approve":
        try:
            view = build_candidate_stack_view(plans_dir=plans_dir, slug=args.slug, candidate=candidate)
        except (ValueError, OSError) as exc:
            error(str(exc))
            return _RC_USAGE
        _render_structural_candidate_stack(view)
        # A new approval needs this same computation, so a failure here cannot proceed anyway; an
        # already-sealed candidate also stops here, a deliberate fail-closed choice on a corrupt store.
        try:
            _render_narrative_evidence(
                _compute_narrative_evidence(
                    plans_dir=plans_dir, slug=args.slug, initial=candidate, content=candidate.content
                )
            )
        except (ValueError, OSError, RoadmapArtifactError) as exc:
            error(str(exc))
            return _RC_USAGE
        # Outside the try above: display only, so it can never turn into a refusal.
        _print_candidate_stack_callout(
            plans_dir=plans_dir, slug=args.slug, initial=candidate, content=candidate.content
        )
        print(f"stack digest: {view.digest}")
        if confirm_digest is None:
            _render_unconfirmed_structural_approval(view.digest)
            return _RC_USAGE
    else:
        try:
            view = build_candidate_stack_view(plans_dir=plans_dir, slug=args.slug, candidate=candidate)
        except (ValueError, OSError) as exc:
            error(str(exc))
            return _RC_USAGE
        _render_structural_candidate_stack(view)
        # Edit and reject must not be trapped by a display failure: it prints "unavailable" and goes on.
        _print_narrative_evidence_or_unavailable(
            plans_dir=plans_dir, slug=args.slug, initial=candidate, content=candidate.content
        )
        _print_candidate_stack_callout(
            plans_dir=plans_dir, slug=args.slug, initial=candidate, content=candidate.content
        )
        if decision == "reject":
            _render_structural_reject_effect(view)
    result = decide_structural_candidate(
        args.slug,
        candidate_id,
        decision,
        plans_dir=plans_dir,
        repo_root=repo_root if decision == "edit" else None,
        correction=correction,
        invoker=invoker,
        confirm_digest=confirm_digest,
    )
    # An edit has already published its replacement, so a view failure here reports the write rather than
    # refusing; the exit is not 0 because the operator was not shown what the replacement covers.
    replacement_view: Optional[CandidateStackView] = None
    replacement_view_error: Optional[Exception] = None
    if result.active_candidate is not None:
        try:
            replacement_view = build_candidate_stack_view(
                plans_dir=plans_dir, slug=args.slug, candidate=result.active_candidate
            )
        except (ValueError, OSError) as exc:
            replacement_view_error = exc
    _render_structural_candidate_decision_result(result, decision=decision, replacement_view=replacement_view)
    if replacement_view_error is not None:
        error(str(replacement_view_error))
        return _RC_INCOMPLETE
    if result.outcome != "stored":
        return _candidate_model_result_status(result.outcome)
    if decision == "approve":
        assert result.seal is not None
        return _cmd_roadmap_promote_review_seal_id(
            args, plans_dir=plans_dir, seal_id=result.seal.seal_id
        )
    return 0


def _cmd_roadmap_decision_settlement_response(args: argparse.Namespace, *, plans_dir: Path) -> int:
    """Pass one explicit confirmation receipt and response to its owner."""
    final_name = _option_occurrences(args, "respond_decision_settlement")[-1]
    affirmative = bool(_option_occurrences(args, "decision_settlement_yes"))
    result = respond_enrolled_decision_settlement(
        args.slug, final_name, affirmative, plans_dir=plans_dir
    )
    _render_decision_settlement_result(result)
    return result.status


def _cmd_roadmap_review_candidate(
    args: argparse.Namespace,
    *,
    repo_root: Path,
    plans_dir: Path,
    invoker: Optional[StageInvoker],
) -> int:
    """Delegate one initial-candidate question request to review storage."""
    candidate_version_id = _option_occurrences(args, "review_candidate")[-1]
    try:
        result = generate_candidate_question(
            args.slug,
            candidate_version_id,
            repo_root=repo_root,
            plans_dir=plans_dir,
            invoker=invoker,
        )
    except ValueError as exc:
        error(str(exc))
        return _RC_USAGE
    _render_candidate_review_result(result)
    if result.initial_candidate is not None:
        evidence_error = _print_narrative_evidence_or_unavailable(
            plans_dir=plans_dir, slug=args.slug,
            initial=result.initial_candidate, content=result.initial_candidate.content,
        )
        _print_candidate_stack_callout(
            plans_dir=plans_dir, slug=args.slug,
            initial=result.initial_candidate, content=result.initial_candidate.content,
        )
        if evidence_error is not None:
            error(str(evidence_error))
            return _RC_INCOMPLETE
    return _candidate_model_result_status(result.outcome)


def _cmd_roadmap_answer_candidate_question(
    args: argparse.Namespace,
    *,
    repo_root: Path,
    plans_dir: Path,
    invoker: Optional[StageInvoker],
) -> int:
    """Delegate one exact stored-question answer and replacement request."""
    question_id = _option_occurrences(args, "answer_question")[-1]
    answer_text = _option_occurrences(args, "answer")[-1]
    try:
        result = answer_candidate_question(
            args.slug,
            question_id,
            answer_text,
            repo_root=repo_root,
            plans_dir=plans_dir,
            invoker=invoker,
        )
    except ValueError as exc:
        error(str(exc))
        return _RC_USAGE
    evidence_failures: list[Exception] = []

    def show_evidence() -> None:
        # The replacement's content, judged against the initial candidate's predecessor as approval does.
        failure = _print_narrative_evidence_or_unavailable(
            plans_dir=plans_dir, slug=args.slug,
            initial=result.initial_candidate, content=result.replacement.content,
        )
        _print_candidate_stack_callout(
            plans_dir=plans_dir, slug=args.slug,
            initial=result.initial_candidate, content=result.replacement.content,
        )
        if failure is not None:
            evidence_failures.append(failure)

    shows = result.initial_candidate is not None and result.replacement is not None
    _render_candidate_answer_result(result, after_diff=show_evidence if shows else None)
    if evidence_failures:
        error(str(evidence_failures[0]))
        return _RC_INCOMPLETE
    return _candidate_model_result_status(result.outcome)


def _cmd_roadmap_promote_review_seal(args: argparse.Namespace, *, plans_dir: Path) -> int:
    """Hold the existing writer guard through exact review-seal promotion."""
    return _cmd_roadmap_promote_review_seal_id(
        args, plans_dir=plans_dir, seal_id=_option_occurrences(args, "promote_review_seal")[-1]
    )


def _cmd_roadmap_promote_review_seal_id(
    args: argparse.Namespace, *, plans_dir: Path, seal_id: str
) -> int:
    """Promote one already-selected exact review seal through the writer guard."""
    try:
        with roadmap_writer_guard(plans_dir, args.slug) as writer_token:
            promoted = promote_review_seal(
                plans_dir=plans_dir,
                slug=args.slug,
                seal_id=seal_id,
                writer_token=writer_token,
            )
    except (RoadmapVersionPromotionError, RoadmapWriterGuardError, RoadmapArtifactError, ValueError) as exc:
        error(str(exc))
        return _RC_USAGE
    except OSError as exc:
        error(str(exc))
        return _RC_INCOMPLETE
    if promoted.outcome == PROMOTION_OUTCOME_ALREADY_PROMOTED:
        print(f"already promoted version: {promoted.version_id}")
    else:
        print(f"promoted version: {promoted.version_id}")
    return 0


def _candidate_model_result_status(outcome: str) -> int:
    """Map closed proposal and review outcomes to established CLI exits."""
    if outcome == "stored":
        return 0
    if outcome in {"response-rejected", "failed"}:
        return _RC_INCOMPLETE
    if outcome == "refused":
        return _RC_USAGE
    if outcome == "interrupted":
        return 130
    return _RC_INCOMPLETE


def _render_candidate_proposal_result(
    result: CandidateProposalResult,
    *,
    stack_view: Optional[CandidateStackView],
    after_diff: Optional[Callable[[], None]] = None,
) -> None:
    """Render proposal facts without exposing candidate content.

    ``stack_view`` is the caller's whole stack when it carries a structural hop, else ``None``.
    ``after_diff`` prints the narrative evidence between the diff and the stack's closing choices line.
    """
    print(f"candidate proposal: {result.outcome}")
    if result.candidate is not None:
        print(f"candidate: {result.candidate.version_id}")
        print(f"predecessor: {result.candidate.record.predecessor_version_id}")
        print("predecessor diff: " + _render_stored_value(result.candidate.evidence.predecessor_diff))
        if after_diff is not None:
            after_diff()
        if stack_view is not None:
            _render_structural_candidate_stack(stack_view)
    elif result.detail:
        print(f"reason: {result.detail}")


def _render_candidate_review_result(result: CandidateReviewResult) -> None:
    """Render the stored candidate, predecessor diff, and stored question facts."""
    print(f"candidate review: {result.outcome}")
    if result.initial_candidate is not None:
        print(f"candidate: {result.initial_candidate.version_id}")
        print(f"predecessor: {result.initial_candidate.record.predecessor_version_id}")
    if result.question_inventory is not None:
        requirement = getattr(result.question_inventory, "review_requirement", None)
        question = result.question_inventory.question
        print("predecessor diff: " + _render_stored_value(result.question_inventory.predecessor_diff))
        if requirement is not None:
            print("review requirement: " + _render_stored_value(requirement))
        print(f"question: {question.question_id}")
        print("anchor: " + _render_stored_value(question.anchor))
        print(f"text: {question.question_text}")
    elif result.detail:
        print(f"reason: {result.detail}")


def _render_candidate_answer_result(
    result: CandidateReviewResult, *, after_diff: Optional[Callable[[], None]] = None
) -> None:
    """Render only the stored replacement comparison and its immutable seal.

    ``after_diff`` prints the narrative evidence before the seal line.
    """
    print(f"candidate answer: {result.outcome}")
    if result.replacement is not None:
        print(f"replacement: {result.replacement.version_id}")
        print("predecessor diff: " + _render_stored_value(result.replacement.evidence.predecessor_diff))
        if after_diff is not None:
            after_diff()
    if result.seal is not None:
        print(f"review seal: {result.seal.seal_id}")
    elif result.detail:
        print(f"reason: {result.detail}")


def _render_structural_candidate_disclosure(candidate: object) -> None:
    """Render persisted structural facts without consulting mutable roadmap state."""
    record = getattr(candidate, "record")
    evidence = getattr(candidate, "evidence")
    receipt = getattr(evidence, "batch_receipt", None)
    diff = getattr(evidence, "predecessor_diff")
    print("structural proposal: stored")
    print("stored route: " + _render_stored_value(getattr(evidence, "operation_classification", None)))
    print(f"candidate: {getattr(candidate, 'version_id')}")
    print(f"source: {getattr(record, 'predecessor_version_id')}")
    print("accepted root: " + _render_stored_value(getattr(evidence, "root_version_id", None)))
    print("batch receipt: " + _render_stored_value(getattr(receipt, "capsule_identity", None)))
    print("selected feedback: " + _render_stored_value(getattr(receipt, "reviewer_items", ())))
    print("typed operations: " + _render_stored_value(getattr(evidence, "normalized_operations", ())))
    _print_prose_amendment_diffs(getattr(evidence, "normalized_operations", None))
    _print_prose_correction_diffs(
        getattr(evidence, "normalized_operations", None), getattr(evidence, "capsule", None)
    )
    print("affected artifacts: " + _render_stored_value(diff.changed_artifacts))
    print("affected rows and before/after values: " + _render_stored_value(diff.changed_rows))
    print("added relations: " + _render_stored_value(diff.added_relations))
    print("removed relations: " + _render_stored_value(diff.removed_relations))
    print("ordering effects: " + _render_stored_value(tuple(row for row in diff.changed_rows if row.row_type == "ordering")))
    print("promotion effects: accepted head advances; active candidate releases; enrolled seed state invalidates")
    print("non-goals: unlisted artifact bytes, unrelated feedback, and seed bodies remain unchanged")
    print("choices: approve, edit, reject")


def _render_structural_candidate_stack(view: CandidateStackView) -> None:
    """Render the whole stack behind one structural decision, ending in the top candidate's disclosure.

    A pure render of ``view``: it reads no stored state and never prints the digest.
    """
    *lower_hops, top = view.hops
    print(f"candidate stack: accepted root {view.root_version_id}; hops above it: {len(view.hops)}")
    for number, hop in enumerate(lower_hops, start=1):
        evidence = hop.evidence
        receipt = evidence.batch_receipt
        route = evidence.operation_classification
        print(f"stack hop {number} of {len(view.hops)}: {hop.version_id}")
        print("  stored route: " + ("no stored route" if route is None else _render_stored_value(route)))
        print("  batch receipt: " + _render_stored_value(None if receipt is None else receipt.capsule_identity))
        print("  selected feedback: " + _render_stored_value(() if receipt is None else receipt.reviewer_items))
        print("  typed operations: " + _render_stored_value(evidence.normalized_operations))
        _print_prose_amendment_diffs(evidence.normalized_operations, prefix="  ")
        _print_prose_correction_diffs(
            evidence.normalized_operations, getattr(evidence, "capsule", None), prefix="  "
        )
        _print_diff_lines(evidence.predecessor_diff, prefix="  ")
    if lower_hops:
        print("cumulative diff, accepted root to top candidate:")
        _print_diff_lines(view.cumulative_diff, prefix="  ")
    else:
        print("cumulative diff, accepted root to top candidate: equals the top candidate's own diff (one hop)")
    print(
        "stack promotion effects: hops promoted together: "
        + _render_stored_value(view.promoted_version_ids)
        + "; structural hops that invalidate enrolled seed state: "
        + _render_stored_value(view.structural_version_ids)
    )
    _render_structural_candidate_disclosure(top)


def _print_diff_lines(diff: RoadmapDiff, *, prefix: str) -> None:
    """Print a diff's five labeled lines, labeled as the structural disclosure labels them."""
    print(f"{prefix}affected artifacts: " + _render_stored_value(diff.changed_artifacts))
    print(f"{prefix}affected rows and before/after values: " + _render_stored_value(diff.changed_rows))
    print(f"{prefix}added relations: " + _render_stored_value(diff.added_relations))
    print(f"{prefix}removed relations: " + _render_stored_value(diff.removed_relations))
    print(
        f"{prefix}ordering effects: "
        + _render_stored_value(tuple(row for row in diff.changed_rows if row.row_type == "ordering"))
    )


def _print_prose_amendment_diffs(operations: object, *, prefix: str = "") -> None:
    """Print persisted add-row fragments without reconstructing artifact prose.

    Prints unconditionally, an explicit ``[]`` when empty, matching every sibling
    field in these two rendering functions rather than omitting the line.
    """
    records = candidate_prose_amendment_diffs(operations)
    print(f"{prefix}row-linked prose amendments: " + _render_stored_value(records))


def _print_prose_correction_diffs(operations: object, capsule: object, *, prefix: str = "") -> None:
    """Print each correct-prose operation's complete stored before and after text.

    Prints an explicit ``[]`` when there are none; text comes from stored evidence only.
    """
    records = candidate_prose_correction_diffs(operations, capsule)  # type: ignore[arg-type]
    if not records:
        print(f"{prefix}prose corrections: []")
        return
    print(f"{prefix}prose corrections: {len(records)}")
    for record in records:
        print(f"{prefix}  correction artifact key: {record.artifact_key}")
        print(f"{prefix}  correction owning row ids: " + _render_stored_value(record.owning_row_ids))
        print(f"{prefix}  correction before text: " + _render_stored_value(record.before))
        print(f"{prefix}  correction after text: " + _render_stored_value(record.after))


def _render_unconfirmed_structural_approval(digest: str) -> None:
    """Say that nothing was sealed and which flag value confirms the stack just printed."""
    print("structural decision: approve confirmation-required")
    print(
        "reason: nothing is sealed until the stack above is confirmed; "
        f"re-run the same command with --confirm-stack-digest {digest}"
    )


def _render_structural_reject_effect(view: CandidateStackView) -> None:
    """Say that reject drops every unpromoted hop, not only the top candidate."""
    print(
        "reject effect: the active candidate is released and nothing is promoted; "
        f"every unpromoted hop above accepted root {view.root_version_id} is dropped: "
        + _render_stored_value(tuple(hop.version_id for hop in view.hops))
        + "; the dropped hops stay stored as history"
    )


def _render_structural_candidate_decision_result(
    result: CandidateReviewResult, *, decision: str, replacement_view: Optional[CandidateStackView]
) -> None:
    """Render closed structural decisions apart from proposal and promotion results.

    ``replacement_view`` is the stored replacement's whole stack; ``None`` prints the replacement's id alone.
    """
    print(f"structural decision: {decision} {result.outcome}")
    if result.active_candidate is not None:
        print(f"replacement: {result.active_candidate.version_id}")
        if replacement_view is not None:
            _render_structural_candidate_stack(replacement_view)
    if result.seal is not None:
        print(f"review seal: {result.seal.seal_id}")
    if result.detail:
        print(f"reason: {result.detail}")


def _compute_narrative_evidence(
    *, plans_dir: Path, slug: str, initial: object, content: object
) -> roadmap_candidate_narrative.CandidateNarrativeEvidence:
    """Recompute a candidate's narrative evidence as the approval refusal does; nothing is stored.

    ``initial`` supplies the predecessor and batch marker; ``content`` is the text under review, which
    differs from ``initial.content`` for an answer-bound replacement.
    """
    evidence = getattr(initial, "evidence")
    predecessor = load_resolved_stored_version(
        plans_dir=plans_dir, slug=slug, version_id=evidence.predecessor_version_id
    )
    return roadmap_candidate_narrative.candidate_narrative_evidence_from_bytes(
        dict(zip(VERSION_ARTIFACT_KEYS, getattr(content, "artifact_bytes"), strict=True)),
        predecessor,
        feedback_free=evidence.batch_receipt is not None,
    )


def _render_narrative_evidence(evidence: roadmap_candidate_narrative.CandidateNarrativeEvidence) -> None:
    """Print the narrative evidence block; an explicit ``none`` when there is nothing to show."""
    marked = [("blocking", f) for f in evidence.blocking_findings] + [
        ("non-blocking", f) for f in evidence.evidence_items
    ]
    if not marked:
        print("narrative evidence: none")
        return
    print(
        f"narrative evidence: {len(evidence.blocking_findings)} blocking, "
        f"{len(evidence.evidence_items)} non-blocking"
    )
    for marker, finding in marked:
        print(f"  [{marker}] artifact: {finding.artifact}")
        print(f"    row or span: row '{finding.row_id}', body line {finding.line}, offsets {finding.start}-{finding.end}")
        print(f"    defect class: {finding.kind}")
        print("    excerpt: " + _render_stored_value(finding.excerpt))
        print("    correction path: " + "; or ".join(finding.correction_path))


def _print_candidate_stack_callout(
    *, plans_dir: Path, slug: str, initial: object, content: object
) -> None:
    """Print the stack callout beside the narrative evidence; display only, never raises.

    Separate from the evidence so it adds no defect class and no approval block.
    """
    try:
        evidence = getattr(initial, "evidence")
        predecessor = load_resolved_stored_version(
            plans_dir=plans_dir, slug=slug, version_id=evidence.predecessor_version_id
        )
        candidate_bytes = dict(
            zip(VERSION_ARTIFACT_KEYS, getattr(content, "artifact_bytes"), strict=True)
        )
        predecessor_bytes = dict(zip(VERSION_ARTIFACT_KEYS, predecessor.artifact_bytes, strict=True))
        lines = candidate_stack_summary_lines(
            parse_constraints_artifact(candidate_bytes["constraints"].decode("utf-8")),
            parse_constraints_artifact(predecessor_bytes["constraints"].decode("utf-8")),
            parse_components_artifact(candidate_bytes["components"].decode("utf-8")).stores,
        )
    except (ValueError, OSError, KeyError, AttributeError, RoadmapArtifactError) as exc:
        print("stack: unavailable")
        print(f"reason: {exc}")
        return
    print("stack:")
    for line in lines:
        print(f"  {line}")


def _print_narrative_evidence_or_unavailable(
    *, plans_dir: Path, slug: str, initial: object, content: object
) -> Optional[Exception]:
    """Print the evidence block, or ``narrative evidence: unavailable`` with the reason; never silence.

    Returns the failure so a caller whose record is already stored can report it.
    """
    try:
        evidence = _compute_narrative_evidence(
            plans_dir=plans_dir, slug=slug, initial=initial, content=content
        )
    except (ValueError, OSError, RoadmapArtifactError) as exc:
        print("narrative evidence: unavailable")
        print(f"reason: {exc}")
        return exc
    _render_narrative_evidence(evidence)
    return None


def _render_stored_value(value: object) -> str:
    """Render a domain record as stable data without recomputing it from disk."""
    return json.dumps(_wire_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _decision_settlement_has_conflict(args: argparse.Namespace) -> bool:
    """Require one confirmed decision/evidence pair with no companion action."""
    return any(
        (
            len(_option_occurrences(args, "settle_decision")) != 1,
            len(_option_occurrences(args, "settlement_evidence")) != 1,
            len(_option_occurrences(args, "confirm_decision_settlement")) != 1,
            bool(_view_occurrences(args)),
            _has_candidate_lifecycle_action(args),
            getattr(args, "revise_feedback", None) is not None,
            *_broad_mode_companions_present(args),
        )
    )


def _cmd_roadmap_decision_settlement(args: argparse.Namespace, *, plans_dir: Path) -> int:
    """Settle one confirmed decision through the enrolled runner."""
    decisions = _option_occurrences(args, "settle_decision")
    evidence = _option_occurrences(args, "settlement_evidence")
    confirmations = _option_occurrences(args, "confirm_decision_settlement")
    result = run_enrolled_decision_settlement(
        args.slug,
        decisions[-1] if decisions else None,
        evidence[-1] if evidence else None,
        confirmations[-1] if confirmations else None,
        plans_dir=plans_dir,
        mode_rejected=_decision_settlement_has_conflict(args),
    )
    _render_decision_settlement_result(result)
    if result.refusal == "no-published-version":
        error(no_published_version_message(plans_dir, args.slug))
    return result.status


def _render_decision_settlement_result(result: DecisionSettlementRunResult) -> None:
    """Render only the settlement runner's redacted terminal facts."""
    print(f"decision settlement: {result.outcome}")
    if result.refusal is not None:
        print(f"reason: {result.refusal}")
    if result.receipt_id is not None:
        print(f"receipt: {result.receipt_id}")
    confirmation_evidence_final = getattr(result, "confirmation_evidence_final", None)
    if confirmation_evidence_final is not None:
        print(f"confirmation evidence: {confirmation_evidence_final}")


def _warn_leftover_top_level_artifacts(plans_dir: Path, slug: str) -> None:
    """Name top-level ``0N-*.md`` files beside an accepted head as inert leftovers.

    No command reads them, but an agentic reader opening the bare filename a
    draft seed cites would ground on a superseded roadmap. Existence only;
    stderr, so a rendered view or ``--output`` page is unaffected. Silent
    without an accepted head (that refusal already names them).
    """
    try:
        folder = roadmap_dir(plans_dir, slug)
    except (TypeError, ValueError):
        return
    if not accepted_head_path(plans_dir, slug).exists():
        return
    names = leftover_top_level_artifacts(folder)
    if not names:
        return
    subject, verb = ("files", "are") if len(names) > 1 else ("file", "is")
    warn(
        f"roadmap {slug}: top-level {subject} {', '.join(names)} {verb} beside an "
        "accepted head. No command reads "
        f"{'them' if len(names) > 1 else 'it'}, and "
        f"{'they' if len(names) > 1 else 'it'} may hold a superseded roadmap; the "
        f"accepted version is under {version_namespace_path(plans_dir, slug)}. "
        "Delete the leftover so no reader grounds on it "
        "(docs/how-to/roadmap.md section 1)."
    )


def _cmd_roadmap_apply(args: argparse.Namespace, *, repo_root: Path, plans_dir: Path) -> int:
    _warn_leftover_top_level_artifacts(plans_dir, args.slug)
    try:
        result = apply_roadmap_seeds(
            args.slug,
            repo_root=repo_root,
            plans_dir=plans_dir,
            allow_apply=True,
            yes=args.yes,
        )
    except (RoadmapError, RoadmapArtifactError) as exc:
        error(str(exc))
        return _RC_USAGE

    _render_apply_result(result, slug=args.slug, repo_root=repo_root)
    if result.outcome == APPLY_OUTCOME_REFUSED:
        return _RC_USAGE
    return 0


def _cmd_roadmap_refresh_seeds(
    args: argparse.Namespace,
    *,
    repo_root: Path,
    plans_dir: Path,
    invoker: Optional[StageInvoker],
) -> int:
    """Run the explicit code-aware refresh without touching roadmap stages."""
    extra = {"invoker": invoker} if invoker is not None else {}
    _warn_leftover_top_level_artifacts(plans_dir, args.slug)
    try:
        result = refresh_roadmap_seeds(args.slug, repo_root=repo_root, plans_dir=plans_dir, **extra)
    except (RoadmapError, RoadmapArtifactError) as exc:
        error(str(exc))
        return _RC_USAGE

    _render_seed_refresh_result(result, repo_root=repo_root)
    if result.outcome == SEED_REFRESH_OUTCOME_APPLIED:
        return 0
    if result.outcome == SEED_REFRESH_OUTCOME_PARTIAL:
        return _RC_PARTIAL
    return _RC_INCOMPLETE


def _cmd_roadmap_accept_seed(args: argparse.Namespace, *, repo_root: Path, plans_dir: Path) -> int:
    """Accept one directly edited draft without re-running roadmap stages."""
    _warn_leftover_top_level_artifacts(plans_dir, args.slug)
    try:
        result = accept_roadmap_seed(
            args.slug,
            args.accept_seed,
            repo_root=repo_root,
            plans_dir=plans_dir,
        )
    except (RoadmapError, RoadmapArtifactError) as exc:
        error(str(exc))
        return _RC_USAGE

    _render_accept_result(result, slug=args.slug, repo_root=repo_root)
    if result.outcome == ACCEPT_OUTCOME_ACCEPTED:
        return 0
    return _RC_USAGE


def _cmd_roadmap_materialize(
    args: argparse.Namespace,
    *,
    repo_root: Path,
    plans_dir: Path,
    invoker: Optional[StageInvoker],
) -> int:
    """Regenerate selected draft seeds under one batch writer guard."""
    _warn_leftover_top_level_artifacts(plans_dir, args.slug)
    # "Already handled" is a tag on the exception itself, not inferred from
    # entry/return timing — a fresh teardown failure never carries it.
    owned_call_entered = False
    try:
        with _roadmap_writer_owner(plans_dir, args.slug) as writer_token:
            owned_call_entered = True
            return _cmd_roadmap_materialize_owned(
                args,
                repo_root=repo_root,
                plans_dir=plans_dir,
                invoker=invoker,
                writer_token=writer_token,
            )
    except (RoadmapError, RoadmapArtifactError) as exc:
        if _materialize_disposition_emitted(exc):
            raise
        if owned_call_entered:
            # A fresh failure from the writer guard's own machinery, after
            # real work was already underway or complete — not an
            # unattempted preflight refusal.
            _emit_roadmap_terminal_disposition(args.slug, "unexpected-error")
            raise
        # ``_roadmap_writer_owner`` converts a bad-slug ``ValueError`` to
        # ``RoadmapError`` before acquiring the guard; every other roadmap
        # dispatch branch gives that the same clean usage-error treatment.
        error(str(exc))
        # Writer acquisition happens before the owned batch lifecycle. Create
        # the matrix-required preflight record without claiming any row work.
        try:
            with _roadmap_command_lifecycle(
                repo_root=repo_root,
                plans_dir=plans_dir,
                slug=args.slug,
                run_logger=None,
                flags={"mode": "materialize"},
                context={
                    "roadmap_action": "materialize",
                    "roadmap_slug": args.slug,
                    "requested_plan_id": (
                        None if args.materialize is _MATERIALIZE_ALL else args.materialize
                    ),
                    "active_plan_id": None,
                    "seed_attempt": None,
                    "backend_attempt": None,
                    "backend_child_started": False,
                },
            ) as lifecycle:
                lifecycle.complete(outcome="preflight-refused", rc=_RC_USAGE)
        except (RoadmapError, OSError):
            # Can't own a run record either way; retain the clean CLI
            # refusal above without manufacturing a second failure.
            pass
        _emit_roadmap_terminal_disposition(args.slug, "preflight-refused")
        return _RC_USAGE
    except Exception as exc:
        if not _materialize_disposition_emitted(exc):
            _emit_roadmap_terminal_disposition(args.slug, "unexpected-error")
        raise


def _refuse_materialize_preflight(lifecycle: _RoadmapCommandLifecycle, slug: str) -> int:
    """Complete the owned lifecycle and emit the shared preflight refusal,
    so a new branch can't drift by copying five siblings' calls by eye."""
    lifecycle.complete(outcome="preflight-refused", rc=_RC_USAGE)
    _emit_roadmap_terminal_disposition(slug, "preflight-refused")
    return _RC_USAGE


def _cmd_roadmap_materialize_owned(
    args: argparse.Namespace,
    *,
    repo_root: Path,
    plans_dir: Path,
    invoker: Optional[StageInvoker],
    writer_token: RoadmapWriterToken,
) -> int:
    """Regenerate only draft seeds whose current classification is recoverable."""
    target = args.materialize
    requested_plan_id = None if target is _MATERIALIZE_ALL else target
    context = {
        "roadmap_action": "materialize",
        "roadmap_slug": args.slug,
        "requested_plan_id": requested_plan_id,
        "active_plan_id": None,
        "seed_attempt": None,
        "backend_attempt": None,
        "backend_child_started": False,
    }
    try:
        with _roadmap_command_lifecycle(
            repo_root=repo_root,
            plans_dir=plans_dir,
            slug=args.slug,
            run_logger=None,
            flags={"mode": "materialize"},
            context=context,
        ) as lifecycle:
            run_logger = lifecycle.run_logger
            try:
                try:
                    require_roadmap_writer_token(
                        writer_token, plans_dir=plans_dir, slug=args.slug
                    )
                except RoadmapWriterGuardError as exc:
                    error(str(exc))
                    return _refuse_materialize_preflight(lifecycle, args.slug)
                try:
                    artifact = load_accepted_plans_artifact(plans_dir=plans_dir, slug=args.slug)
                except (RoadmapError, RoadmapArtifactError) as exc:
                    error(str(exc))
                    return _refuse_materialize_preflight(lifecycle, args.slug)

                try:
                    classifications = classify_draft_seeds(
                        artifact, plans_dir=plans_dir, slug=args.slug
                    )
                except RoadmapSeedStateError as exc:
                    error(str(exc))
                    return _refuse_materialize_preflight(lifecycle, args.slug)

                if target is _MATERIALIZE_ALL:
                    plan_ids = [
                        row.id
                        for row in artifact.plans
                        if (classification := classifications.get(row.id)) is not None
                        and classification.state in _MATERIALIZABLE_STATES
                    ]
                else:
                    classification = classifications.get(target)
                    if classification is None:
                        error(f"roadmap {args.slug}: no such plan in this roadmap: {target!r}")
                        return _refuse_materialize_preflight(lifecycle, args.slug)
                    if classification.state not in _MATERIALIZABLE_STATES:
                        detail_suffix = (
                            f" ({classification.detail})" if classification.detail else ""
                        )
                        error(
                            f"roadmap {args.slug}: plan {target!r} classifies as "
                            f"{classification.state!r} — nothing to materialize{detail_suffix}"
                        )
                        return _refuse_materialize_preflight(lifecycle, args.slug)
                    plan_ids = [target]

                if not plan_ids:
                    info(f"roadmap {args.slug}: nothing to materialize — every draft is current")
                    lifecycle.complete(outcome="no-op", rc=0)
                    _emit_roadmap_terminal_disposition(args.slug, "no-op")
                    return 0

                selected_plan_ids = set(plan_ids)
                selected_rows = [row for row in artifact.plans if row.id in selected_plan_ids]
                changes: list = []
                failures: list = []
                try:
                    _materialize_seed_rows(
                        args.slug,
                        selected_rows,
                        repo_root=repo_root,
                        plans_dir=plans_dir,
                        run_logger=run_logger,
                        changes=changes,
                        failures=failures,
                        invoker=invoker,
                        writer_token=writer_token,
                    )
                except (RoadmapError, RoadmapArtifactError) as exc:
                    # A row can fail after earlier rows already succeeded and
                    # wrote files — report what landed instead of discarding
                    # it, and reserve "preflight-refused" for when nothing
                    # ran at all.
                    error(str(exc))
                    if changes or failures:
                        report_path = write_seed_refresh_report(
                            args.slug, changes, failures, plans_dir=plans_dir
                        )
                        result = RoadmapSeedRefreshResult(
                            outcome=SEED_REFRESH_OUTCOME_PARTIAL,
                            changes=tuple(changes),
                            failures=tuple(failures),
                            report_path=report_path,
                        )
                        _render_seed_refresh_result(
                            result, repo_root=repo_root, verb="materialized"
                        )
                        lifecycle.complete(outcome="error", rc=1)
                        _emit_roadmap_terminal_disposition(args.slug, "error")
                        return _RC_PARTIAL
                    return _refuse_materialize_preflight(lifecycle, args.slug)

                report_path = write_seed_refresh_report(
                    args.slug, changes, failures, plans_dir=plans_dir
                )
                if not failures:
                    outcome = SEED_REFRESH_OUTCOME_APPLIED
                    lifecycle_outcome = "completed"
                    rc = 0
                elif changes:
                    outcome = SEED_REFRESH_OUTCOME_PARTIAL
                    lifecycle_outcome = "partial"
                    rc = _RC_PARTIAL
                else:
                    outcome = SEED_REFRESH_OUTCOME_EXHAUSTED
                    lifecycle_outcome = "exhausted"
                    rc = _RC_INCOMPLETE
                result = RoadmapSeedRefreshResult(
                    outcome=outcome,
                    changes=tuple(changes),
                    failures=tuple(failures),
                    report_path=report_path,
                )
                _render_seed_refresh_result(result, repo_root=repo_root, verb="materialized")
                lifecycle.complete(outcome=lifecycle_outcome, rc=rc)
                _emit_roadmap_terminal_disposition(args.slug, lifecycle_outcome)
                return rc
            except KeyboardInterrupt:
                lifecycle.complete(outcome="interrupted", rc=130)
                raise
            except BaseException as exc:
                # Covers a non-Exception escape (SystemExit, GeneratorExit)
                # too — not a silent skip. The persisted disposition is a
                # fixed string, never str(exc): the run-log record must not
                # expose exception-derived text.
                if lifecycle.outcome is None:
                    lifecycle.complete(outcome="error", rc=1)
                _emit_roadmap_terminal_disposition(args.slug, "unexpected-error")
                _mark_materialize_disposition_emitted(exc)
                raise
    except (RoadmapError, RoadmapArtifactError) as exc:
        if _materialize_disposition_emitted(exc):
            raise
        # In practice this is the lifecycle's own slug validation — every
        # RoadmapError/RoadmapArtifactError the command body can raise is
        # already caught above. Kept as an outer net rather than relied on.
        error(str(exc))
        return _RC_USAGE


def _cmd_roadmap_view(
    args: argparse.Namespace, *, plans_dir: Path, repo_root: Optional[Path] = None
) -> int:
    """Render one of the six inspection views over ``args.slug``'s roadmap.

    Never calls ``run_roadmap`` or ``apply_roadmap_seeds``; html only writes
    its derived page. Other artifact state renders as a diagnostic.
    """
    effective_mode = args.mode or MODE_CURRENT
    try:
        loaded: LoadedRoadmap = load_roadmap(plans_dir, args.slug, mode=effective_mode)
    except (ValueError, NoPublishedRoadmapVersionError) as exc:
        error(str(exc))
        return _RC_USAGE
    _warn_leftover_top_level_artifacts(plans_dir, args.slug)

    if args.view == "summary":
        if loaded.plans is None:
            seed_lifecycle = summarize_seed_lifecycle(loaded)
        else:
            try:
                classifications = classify_draft_seeds(
                    loaded.plans, plans_dir=plans_dir, slug=loaded.slug
                )
                seed_lifecycle = summarize_seed_lifecycle(loaded, classifications)
            except RoadmapSeedStateError as exc:
                seed_lifecycle = summarize_seed_lifecycle(loaded, unavailable_reason=str(exc))
        text = render_roadmap_summary(loaded, seed_lifecycle)
    elif args.view == "seeds":
        try:
            classifications = (
                classify_draft_seeds(loaded.plans, plans_dir=plans_dir, slug=loaded.slug)
                if loaded.plans is not None
                else {}
            )
            orphans = (
                find_orphan_seed_records(loaded.plans, plans_dir=plans_dir, slug=loaded.slug)
                if loaded.plans is not None
                else ()
            )
            text = render_seed_state_view(loaded, classifications, orphans)
        except RoadmapSeedStateError as exc:
            text = render_seed_state_view(loaded, {}, (), unavailable_reason=str(exc))
    elif args.view == "walk":
        unavailable_reason: Optional[str] = None
        try:
            classifications = (
                classify_draft_seeds(loaded.plans, plans_dir=plans_dir, slug=loaded.slug)
                if loaded.plans is not None
                else {}
            )
        except RoadmapSeedStateError as exc:
            classifications = {}
            unavailable_reason = str(exc)
        text = render_traceability_walk(
            loaded, plans_dir, classifications, unavailable_reason=unavailable_reason
        )
    elif args.view == "ledger":
        text = render_decision_ledger(loaded)
    elif args.view == "html":
        # Defaults to writing a file, unlike every other view — see the
        # module docstring. ``--output -`` is the stdout escape hatch.
        out = args.output
        if out == "-":
            print(render_roadmap_html(loaded), end="")
            return 0
        if out is None:
            destination = review_path(plans_dir, args.slug)
            label = "the default review page"
            shown = str(destination)
        else:
            label = "--output"
            shown = out
            try:
                destination = Path(out).expanduser()
            except RuntimeError as exc:
                error(f"{label} is not a usable file path: {shown}: {exc}")
                return _RC_USAGE
        # Checked before the render, so a bad destination fails without
        # paying for it. Left unchecked, "." and "/" raise ValueError
        # (crash handler) while ".." and an existing dir raise OSError
        # (reported as a write failure) — different codes for the same
        # mistake. A trailing separator on a not-yet-existing path is
        # checked on the raw string: Path() drops it before .name /
        # .is_dir() ever see it.
        try:
            # is_dir() stats the path and can itself raise OSError
            # (EACCES on an unreadable parent), unlike its neighbors.
            is_directory = destination.is_dir()
        except OSError as exc:
            error(f"could not check {label} destination {shown}: {exc}")
            return _RC_INCOMPLETE
        if is_directory or (
            out is not None and (not destination.name or out.endswith(("/", os.sep)))
        ):
            error(f"{label} must name a file, not a directory: {shown}")
            # An explicit path is malformed input, while a directory where
            # the computed default belongs is an environmental collision.
            return _RC_INCOMPLETE if out is None else _RC_USAGE
        document = render_roadmap_html(loaded)
        try:
            atomic_write_text(destination, document)
        except ValueError as exc:
            # Backstop for a path the check above cannot see through (a null
            # byte, a platform-specific illegal name).
            error(f"{label} is not a usable file path: {shown}: {exc}")
            return _RC_INCOMPLETE if out is None else _RC_USAGE
        except OSError as exc:
            # The arguments were valid and the document rendered; only the
            # disk write failed. That is a failure-to-complete (1), not the
            # pre-flight rejection (2) this verb's other --output errors are.
            error(f"could not write {_short_path(destination, repo_root)}: {exc}")
            return _RC_INCOMPLETE
        print(f"Wrote roadmap page: {_short_path(destination, repo_root)}")
        return 0
    else:
        text = render_reverse_index(loaded, args.id)

    print(render_roadmap_view(args.view, text, stream=sys.stdout))
    return 0


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def _render_seed_refresh_result(
    result: RoadmapSeedRefreshResult, *, repo_root: Path, verb: str = "refreshed"
) -> None:
    """Summarize an explicit refresh; full diffs remain in its report file."""
    if result.changes:
        changed = sum(change.action != "unchanged" for change in result.changes)
        success(f"roadmap seeds: {verb} {changed} of {len(result.changes)} tracked file(s)")
        for change in result.changes:
            detail(f"  {change.plan_id}: {change.action} {_short_path(change.target, repo_root)}")
        if result.report_path is not None:
            detail(f"  differences: {_short_path(result.report_path, repo_root)}")

    for failure in result.failures:
        error(
            f"roadmap seeds: {failure.plan_id}: refresh exhausted its retry budget "
            f"({failure.failure_kind} failure)"
        )
        for violation in failure.violations:
            error(f"  {violation.message}")
        if failure.failure_detail:
            error(f"  unusable reply: {failure.failure_detail}")


def _render_apply_result(result: RoadmapApplyResult, *, slug: str, repo_root: Path) -> None:
    _render_apply_outcome(result, slug=slug, repo_root=repo_root)
    for plan_id, dest in result.skipped:
        detail(f"  {plan_id}: already published, skipped ({_short_path(dest, repo_root)})")
    for stale in result.stale_published:
        remedy = (
            f"--accept-seed {stale.plan_id}"
            if stale.state == DRAFT_SEED_STATE_DIGEST_MISMATCHED
            else "--refresh-seeds"
        )
        warn(
            f"{stale.plan_id}: published seed's draft is {stale.state}; its "
            f"published seed copy may be out of date (see {remedy})"
        )


def _render_apply_outcome(result: RoadmapApplyResult, *, slug: str, repo_root: Path) -> None:
    if result.outcome == APPLY_OUTCOME_RECOMMENDED and not result.targets:
        info(f"roadmap {slug}: no unpublished seed to promote.")
        return
    if result.outcome == APPLY_OUTCOME_APPLIED:
        success(f"roadmap {slug}: promoted {len(result.promotions)} seed(s) to docs/implementation-plans/plan-seeds/")
        for plan_id, _source, dest in result.promotions:
            detail(f"  {plan_id}: {_short_path(dest, repo_root)}")
        for line in _promoted_create_handoff_lines(result, repo_root=repo_root):
            detail(line)
        return

    if result.outcome == APPLY_OUTCOME_REFUSED:
        error(f"roadmap {slug}: refusing seed promotion — nothing was copied")
        if result.bijection_error:
            error(f"  {result.bijection_error}")
        for path in result.collisions:
            error(f"  destination already exists: {_short_path(path, repo_root)}")
        source_by_plan_id = {plan_id: source for plan_id, source, _dest in result.targets}
        for refused in result.refused_drafts:
            source = source_by_plan_id.get(refused.plan_id)
            source_text = _short_path(source, repo_root) if source is not None else "<unknown>"
            detail_suffix = f": {refused.detail}" if refused.detail else ""
            error(f"  {refused.plan_id}: {source_text}: {refused.state}{detail_suffix}")
        return

    info(
        f"roadmap {slug}: draft seeds are ready to promote, but nothing was "
        f"written (recommend-only)."
    )
    for plan_id, source, dest in result.targets:
        detail(f"  {plan_id}: {_short_path(source, repo_root)} → {_short_path(dest, repo_root)}")
    detail(
        "To actuate interactively:\n"
        f"  plan-tool roadmap {slug} --apply\n"
        "Add -y for the deliberate non-interactive apply path "
        "(--apply -y copies without a TTY confirm)."
    )


def _render_accept_result(result: RoadmapSeedAcceptResult, *, slug: str, repo_root: Path) -> None:
    """Render the accepted or refused result of one directly edited draft."""
    if result.outcome == ACCEPT_OUTCOME_ACCEPTED:
        success(f"roadmap {slug}: accepted directly edited draft for {result.plan_id}")
        if result.target is not None:
            detail(f"  accepted draft: {_short_path(result.target, repo_root)}")
        if result.promoted_target is not None:
            detail(f"  re-synced promoted seed: {_short_path(result.promoted_target, repo_root)}")
            detail(
                f"plan-tool create {result.plan_id} --from-existing "
                f"{_short_path(result.promoted_target, repo_root)}"
            )
        else:
            existing = resolve_plan_seed_dest(default_seeds_dir(repo_root), result.plan_id)
            if existing.exists():
                detail(
                    f"  left untouched: {_short_path(existing, repo_root)} "
                    "(this seed is not recorded as published, so the file is not "
                    "the tool's; --apply refuses it as a collision)"
                )
        return

    error(f"roadmap {slug}: refusing seed acceptance for {result.plan_id}")
    if result.violations:
        for violation in result.violations:
            error(f"  {violation.message}")
        return
    if result.state is None:
        error(f"  no such plan in this roadmap: {result.plan_id!r}")
        return

    detail_suffix = f": {result.detail}" if result.detail else ""
    error(f"  draft classifies as {result.state!r}{detail_suffix}")
    if result.state in {
        DRAFT_SEED_STATE_MISSING,
        DRAFT_SEED_STATE_STALE,
        DRAFT_SEED_STATE_MALFORMED,
        DRAFT_SEED_STATE_PATH_ESCAPING,
    }:
        detail(f"plan-tool roadmap {slug} --materialize {result.plan_id}")


def _promoted_create_handoff_lines(result: RoadmapApplyResult, *, repo_root: Path) -> list[str]:
    return [
        f"plan-tool create {plan_id} --from-existing {_short_path(dest, repo_root)}"
        for plan_id, _source, dest in result.promotions
    ]


def _print_completed(
    result: RoadmapResult, *, slug: str, repo_root: Path, plans_dir: Path
) -> None:
    """Summarize a completed run: what it wrote, what it left pending.

    The feedback and newly-settled summaries are deliberately *not* here —
    ``cmd_roadmap`` emits both for every outcome.
    """
    success(f"roadmap {slug}: wrote {len(result.artifacts)} artifact(s)")
    for path in result.artifacts:
        detail(_short_path(path, repo_root))
    for line in _create_handoff_lines(
        result, slug=slug, repo_root=repo_root, plans_dir=plans_dir
    ):
        detail(line)
    for line in _stack_summary_output_lines(result):
        # The producer's blank separators and bullets are Markdown for INDEX.md.
        print(f"  {line}")
    if result.pending_decisions:
        detail(
            f"{result.pending_decisions} pending decision(s) in the artifacts "
            f"above — the run still completed. Settle one with "
            f"--settle-decision, or record a further request with "
            f"--submit-feedback; the published version is not edited in place"
        )


def _print_completed_no_change(result: RoadmapResult, *, slug: str) -> None:
    """Report a successful re-gate that deliberately published nothing."""
    success(f"roadmap {slug}: re-gated without artifact changes")
    if result.stages_run:
        detail("feedback-free re-entry re-gates canonical artifacts without rewriting them")


def _stack_summary_output_lines(result: RoadmapResult) -> list[str]:
    """The stack summary for a first run's written constraints; empty if it wrote none."""
    written = {path.name: path for path in result.artifacts}
    constraints_file = written.get(CONSTRAINTS_FILENAME)
    if constraints_file is None:
        return []
    try:
        constraints = load_constraints_artifact(constraints_file)
        components_file = written.get(COMPONENTS_FILENAME)
        components_decisions = (
            load_components_artifact(components_file).decisions
            if components_file is not None
            else ()
        )
        plans_file = _plans_artifact_path(result)
        plans_decisions = (
            load_plans_artifact(plans_file).decisions if plans_file is not None else ()
        )
    except RoadmapArtifactError as exc:
        error(f"cannot print stack summary: {exc}")
        return []
    pending = pending_anchor_ids(
        constraints.decisions, components_decisions, plans_decisions
    )
    return stack_summary_lines(constraints, pending)


def _plans_artifact_path(result: RoadmapResult) -> Path | None:
    """The written ``04-roadmap.md`` path, if this run produced one."""
    for path in result.artifacts:
        if path.name == PLANS_FILENAME:
            return path
    return None


def _create_handoff_lines(
    result: RoadmapResult, *, slug: str, repo_root: Path, plans_dir: Path
) -> list[str]:
    """Ordered ``plan-tool create --from-existing`` lines after stage 4 lands.

    ``plans_dir`` is the configured plans directory; the plans artifact sits in
    the version store, whose depth below it varies, so it is never derived.
    """
    plans_file = _plans_artifact_path(result)
    if plans_file is None:
        return []
    try:
        artifact = load_plans_artifact(plans_file)
    except RoadmapArtifactError as exc:
        error(f"cannot print create handoff: {exc}")
        return []
    bijection_error = ordering_plans_bijection_error(artifact)
    if bijection_error is not None:
        error(f"cannot print create handoff: {bijection_error}")
        return []
    try:
        classifications = classify_draft_seeds(artifact, plans_dir=plans_dir, slug=slug)
    except RoadmapSeedStateError as exc:
        error(f"cannot print create handoff: {exc}")
        return []
    lines: list[str] = []
    for plan_id, source, _dest in ordered_plan_seed_targets(
        plans_dir, slug, artifact, repo_root=repo_root
    ):
        classification = classifications.get(plan_id)
        if classification is not None and classification.state == DRAFT_SEED_STATE_CURRENT:
            lines.append(
                f"plan-tool create {plan_id} --from-existing {_short_path(source, repo_root)}"
            )
        else:
            state_desc = classification.state if classification is not None else "unavailable"
            lines.append(
                f"roadmap plan '{plan_id}' is not seed-ready "
                f"({state_desc}) — run `plan-tool roadmap {slug} "
                f"--materialize {plan_id}` or `plan-tool roadmap {slug} "
                "--refresh-seeds`"
            )
    return lines


def _feedback_summary_lines(result: RoadmapResult) -> list[str]:
    """Tell an operator how many feedback rows await them, and what to do next.

    The whole block is one count plus the actions a reviewer takes **in their
    editor**. Closing, deferring, and ordinary reopening remain reviewer edits;
    the tool judges no response.

    The two states the reviewer *types* come from
    :class:`~plan_tool.roadmap_artifacts.FeedbackState` rather than from
    spellings written here. This advice tells them to put a literal into YAML
    that the artifact parser then has to accept, so a rename in the leaf would
    otherwise make this module's advice wrong with nothing red firing.

    An empty list when nothing awaits review, so a first run — which cannot
    have a predecessor and so cannot have answered anything — prints exactly
    what it printed before this block existed, with no caller-side check.
    """
    count = result.feedback_awaiting_review
    if not count:
        return []
    return [
        f"{count} feedback row(s) await your review — each carries the model's "
        f"'proposed_response' beside the request it answers",
        f"close one by deleting the row (git keeps the record), reopen it by "
        f"setting 'state' back to '{FeedbackState.OPEN.value}' and clearing or "
        f"replacing the response, or park it by setting 'state' to "
        f"'{FeedbackState.DEFERRED.value}', which keeps the row in the file "
        f"and stops sending it as active guidance",
        "close, defer, and ordinary reopening remain reviewer edits",
        "when a response asks you a question rather than proposing a change, "
        "amend that row's 'request' in place to answer it before you reopen "
        "it — the request is immutable to the model, not to you, and "
        "reopening it unchanged only re-asks the same thing",
    ]


def _seed_invalidation_summary_lines(result: RoadmapResult, *, slug: str) -> list[str]:
    """Route stale derived seeds through explicit regeneration surfaces."""
    if not result.invalidated_seed_count:
        return []
    return [
        f"{result.invalidated_seed_count} derived roadmap seed(s) are stale "
        "after the revision and were left unchanged",
        f"run `plan-tool roadmap {slug} --materialize` or `plan-tool roadmap "
        f"{slug} --refresh-seeds` to regenerate them; until then, "
        "`create --from-existing` asks you to confirm using the stale seed",
    ]


def _newly_settled_summary_lines(result: RoadmapResult) -> list[str]:
    """Name decision ids this revision settled and the predecessor had not.

    Deliver, don't verify: settling may be the reviewer's own request deciding
    the question, and refusing that case burns a stage attempt. Naming the ids
    puts the fence authority in front of the operator; confirming or setting
    ``pending`` is their edit.

    The status a reviewer types comes from
    :class:`~plan_tool.roadmap_artifacts.DecisionStatus` rather than a spelling
    written here, for the reason :func:`_feedback_summary_lines` gives: this
    advice puts a literal into YAML the artifact parser then has to accept, so
    a rename in the leaf would otherwise make it wrong with nothing red firing.

    Empty when a run settled nothing the predecessor had not — including every
    first run, which has no predecessor to differ from.
    """
    ids = result.newly_settled_decisions
    if not ids:
        return []
    named = ", ".join(f"'{decision_id}'" for decision_id in ids)
    return [
        f"{len(ids)} decision(s) newly settled by this revision ({named}) — "
        f"each is either a row the prior version did not carry, or one it "
        f"carried as '{DecisionStatus.PENDING.value}'",
        f"confirm each in place, or set its status to "
        f"'{DecisionStatus.PENDING.value}' — a settled fence is yours to "
        f"confer, and the next revision pins these with the same force as one "
        f"you settled yourself",
    ]


def _print_invalid(result: RoadmapResult, *, slug: str) -> None:
    """Report source or no-op gate refusal without retry-exhaustion advice."""
    error(f"roadmap {slug}: stage {result.failed_stage} is invalid")
    if result.failure_detail:
        error(f"  {result.failure_detail}")
    for violation in result.violations:
        error(f"  {violation.message}")


def _print_exhausted(result: RoadmapResult, *, slug: str, repo_root: Path) -> None:
    """Report the stage that spent its budget, and why.

    The body branches on the failure kind: quoting an empty violation list at
    a backend that never answered reads as "the model disagreed with the
    gates", and sending that operator to edit their brief points them at the
    wrong file — so the fix-the-brief suggestion is gates-only. An authored-
    review-rows exhaustion needs its own arm for the same reason and one more:
    it is the only kind whose cause is in neither the brief nor the artifact,
    so without a line saying so the operator goes looking in a file that is
    fine. The result carries no ids for the rows the reply invented — only the
    reply head — so the arm names the defect rather than the rows.
    """
    kind = result.failure_kind or "unknown"
    error(
        f"roadmap {slug}: stage {result.failed_stage} exhausted its retry budget ({kind} failure)"
    )
    print(
        f"  the stages that passed are held; the next plain run resumes at stage "
        f"{result.failed_stage}",
        file=sys.stderr,
    )

    if kind == FAILURE_GATES:
        for violation in result.violations:
            print(f"- {violation.message}", file=sys.stderr)
        print(
            "If the concept brief is the cause, edit it, delete "
            f"{stage_resume_directory(repo_root, slug)} (this discards every held stage; "
            "the next run restarts at stage 1), and run again.",
            file=sys.stderr,
        )
        return

    if kind == FAILURE_AUTHORED_REVIEW_ROWS:
        print(
            "  every attempt authored 'feedback' or 'removals' rows you never "
            "wrote — those collections record what a human asked for, and a "
            "first run has none",
            file=sys.stderr,
        )
        print(
            "  nothing you wrote caused this and there is nothing there to fix; "
            "run again",
            file=sys.stderr,
        )

    if kind == FAILURE_INVOKE:
        print(f"  backend exit code {result.failure_rc}", file=sys.stderr)
    if result.failure_detail:
        print(f"  unusable reply: {result.failure_detail}", file=sys.stderr)


def register(subparsers) -> dict[str, Handler]:
    """Add the ``roadmap`` subparser and return its handler map."""
    # Deliberately NOT parser.make_yes_parent(): with --apply this is a
    # second opt-in that bypasses the TTY confirm in apply_roadmap_seeds and may
    # copy unattended, and the help text has to say so.
    yes_parent = argparse.ArgumentParser(add_help=False)
    yes_parent.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help=(
            "skip the interactive promote confirmation (relevant only with "
            "--apply): the deliberate second opt-in that may copy seeds into "
            "docs/implementation-plans/plan-seeds/ without a TTY. Useful for scripted/unattended runs."
        ),
    )
    p = subparsers.add_parser(
        "roadmap",
        help=(
            "stage a concept brief into gated architecture artifacts under "
            "docs/implementation-plans/roadmaps/<slug>/ (one rung above "
            "create); use --apply to promote draft seeds into docs/implementation-plans/plan-seeds/ or "
            "--refresh-seeds to regenerate invalidated seeds"
        ),
        parents=[yes_parent],
    )
    p.add_argument(
        "slug",
        help=(
            "roadmap slug — names the roadmaps/<slug>/ directory the "
            "artifacts land in. Required: this verb has no interactive slug "
            "confirmation to fall back on."
        ),
    )
    p.add_argument(
        "--from-existing",
        type=Path,
        required=False,
        default=None,
        dest="from_existing",
        metavar="PATH",
        help=(
            "path to the concept brief a first stage run grounds a new roadmap "
            "in. A run that failed part-way holds its passed stages and the "
            "next run resumes from them, but only for the same brief content. "
            "Refused beside an accepted head. Not used with --apply."
        ),
    )
    # Broad modes collect each occurrence first so exclusive routes can inspect
    # them later. Typed exclusive actions stay separate from those broad modes.
    p.add_argument(
        "--apply",
        action=_TrackRoadmapMode,
        nargs=0,
        const=True,
        default=False,
        help=(
            "apply-only mode: read the accepted version's roadmap and promote draft "
            "seeds into docs/implementation-plans/plan-seeds/ after confirm (or -y). Does not run "
            "stages or invoke the backend."
        ),
    )
    p.add_argument(
        "--refresh-seeds",
        action=_TrackRoadmapMode,
        nargs=0,
        const=True,
        default=False,
        dest="refresh_seeds",
        help=(
            "explicitly regenerate roadmap-derived seeds against the current "
            "codebase, restoring a consumed or archived seed at its original "
            "path when needed. Writes a before/after difference report; does "
            "not rewrite any roadmap artifact."
        ),
    )
    p.add_argument(
        "--accept-seed",
        action=_TrackRoadmapMode,
        default=None,
        metavar="PLAN_ID",
        help=(
            "accept one validated directly edited digest-mismatched draft as "
            "current without regenerating it or running roadmap stages."
        ),
    )
    p.add_argument(
        "--materialize",
        action=_TrackRoadmapMode,
        nargs="?",
        const=_MATERIALIZE_ALL,
        default=None,
        metavar="PLAN_ID",
        help=(
            "explicitly regenerate every recoverable draft seed, or only "
            "PLAN_ID when supplied. Skips current drafts and refuses "
            "duplicate plan rows; writes the seed refresh difference report."
        ),
    )
    p.add_argument(
        "--view",
        action=_TrackRoadmapMode,
        choices=[
            "summary",
            "walk",
            "ledger",
            "index",
            "seeds",
            "html",
        ],
        default=None,
        help=(
            "inspection mode: render a compact review summary, traceability "
            "walk, decision ledger, reverse citation index, or draft-seed "
            "state report over the accepted version and print it; or a "
            "self-contained, print-formatted HTML page carrying every "
            "parsed row of all four artifacts with its resolvable "
            "references linked and dangling or ambiguous ones marked, "
            "written to <roadmap-dir>/review.html by default. "
            "Runs no stage and invokes no backend; does not require "
            "--from-existing. --mode and --id refine views; --output "
            "refines html."
        ),
    )
    p.add_argument(
        "--output",
        default=None,
        metavar="PATH",
        help=(
            "valid only with --view html: write the rendered page to PATH "
            "and print the path, or to <roadmap-dir>/review.html when "
            "omitted (the html view writes a file by default — it is meant "
            "to be opened and printed, not piped). PATH of '-' prints to "
            "stdout instead of writing, matching every other view's "
            "default. Creates missing parent directories and overwrites an "
            "existing file; touches no other roadmap state — no artifact, "
            "lifecycle sidecar, or run log."
        ),
    )
    p.add_argument(
        "--compare",
        action=_TrackExclusiveOption,
        nargs=0,
        const=True,
        default=None,
        help=(
            "compare the accepted-head roadmap version (or --comparison-base) "
            "with the active candidate (or --comparison-target). When no "
            "candidate is active, requires --comparison-target; a roadmap "
            "with no accepted head is refused. Accepts no companion "
            "roadmap options and never writes roadmap state."
        ),
    )
    p.add_argument(
        "--comparison-base",
        action=_TrackExclusiveOption,
        default=None,
        metavar="VERSION_ID",
        help=(
            "stored immutable version to use as the comparison base instead "
            "of the accepted head; valid only with --compare."
        ),
    )
    p.add_argument(
        "--comparison-target",
        action=_TrackExclusiveOption,
        default=None,
        metavar="VERSION_ID",
        help=(
            "stored immutable version to use as the comparison target instead "
            "of the active candidate; valid only with --compare."
        ),
    )
    p.add_argument(
        "--comparison-output",
        action=_TrackExclusiveOption,
        choices=["cards", "patch", "json"],
        default="cards",
        help=(
            "comparison presentation: cards (default), complete Git patch, "
            "or deterministic JSON; valid only with --compare."
        ),
    )
    p.set_defaults(
        _roadmap_mode_occurrences=(),
        _settle_decision_occurrences=(),
        _settlement_evidence_occurrences=(),
        _confirm_decision_settlement_occurrences=(),
        _revise_feedback_occurrences=(),
        _propose_candidate_occurrences=(),
        _submit_feedback_occurrences=(),
        _retarget_feedback_occurrences=(),
        _edit_feedback_occurrences=(),
        _defer_feedback_occurrences=(),
        _close_feedback_occurrences=(),
        _reopen_ledger_feedback_occurrences=(),
        _feedback_target_occurrences=(),
        _feedback_request_occurrences=(),
        _review_candidate_occurrences=(),
        _answer_question_occurrences=(),
        _answer_occurrences=(),
        _reject_candidate_occurrences=(),
        _discard_candidate_occurrences=(),
        _decide_candidate_occurrences=(),
        _candidate_decision_occurrences=(),
        _candidate_correction_occurrences=(),
        _confirm_stack_digest_occurrences=(),
        _promote_review_seal_occurrences=(),
        _respond_decision_settlement_occurrences=(),
        _decision_settlement_yes_occurrences=(),
        _decision_settlement_no_occurrences=(),
        _compare_occurrences=(),
        _comparison_base_occurrences=(),
        _comparison_target_occurrences=(),
        _comparison_output_occurrences=(),
        _roadmap_mode_parser=p,
    )
    p.add_argument(
        "--revise-feedback",
        action=_TrackExclusiveOption,
        nargs=0,
        const=True,
        default=None,
        help=(
            "build one inert candidate from the current eligible ledger batch. "
            "Accepts no feedback selector or companion roadmap option."
        ),
    )
    p.add_argument(
        "--propose-candidate",
        action=_TrackExclusiveOption,
        nargs=0,
        const=True,
        default=None,
        help=(
            "build or re-enter the one admitted inert candidate from the current "
            "eligible ledger batch. Prints the candidate's narrative evidence. "
            "Accepts no selector or companion roadmap option."
        ),
    )
    p.add_argument("--submit-feedback", action=_TrackExclusiveOption, default=None, metavar="ITEM_ID",
                   help="submit one reviewer ledger item with --feedback-target and --feedback-request.")
    p.add_argument("--retarget-feedback", action=_TrackExclusiveOption, default=None, metavar="ITEM_ID",
                   help="retarget one ledger item with --feedback-target.")
    p.add_argument("--edit-feedback", action=_TrackExclusiveOption, default=None, metavar="ITEM_ID",
                   help="edit one ledger item with --feedback-target and/or --feedback-request.")
    p.add_argument("--defer-feedback", action=_TrackExclusiveOption, default=None, metavar="ITEM_ID",
                   help="defer one reviewer ledger item.")
    p.add_argument("--close-feedback", action=_TrackExclusiveOption, default=None, metavar="ITEM_ID",
                   help="close one reviewer ledger item.")
    p.add_argument("--reopen-ledger-feedback", action=_TrackExclusiveOption, default=None, metavar="ITEM_ID",
                   help="reopen one retained reviewer ledger item.")
    p.add_argument("--feedback-target", action=_TrackExclusiveOption, default=None, metavar="ARTIFACT:KIND[:ROW_ID]",
                   help="target for one ledger submit, retarget, or edit action.")
    p.add_argument("--feedback-request", action=_TrackExclusiveOption, default=None, metavar="TEXT",
                   help="request text for one ledger submit or edit action.")
    p.add_argument(
        "--review-candidate",
        action=_TrackExclusiveOption,
        default=None,
        metavar="INITIAL_CANDIDATE_VERSION_ID",
        help=(
            "request or return the stored review question for one initial "
            "candidate and print its narrative evidence. Accepts no companion roadmap option."
        ),
    )
    p.add_argument(
        "--answer-question",
        action=_TrackExclusiveOption,
        default=None,
        metavar="QUESTION_ID",
        help=(
            "record exactly one stored-question answer with --answer and "
            "materialize its sealed replacement, printing the replacement's narrative evidence."
        ),
    )
    p.add_argument(
        "--answer",
        action=_TrackExclusiveOption,
        default=None,
        metavar="TEXT",
        help=(
            "exact opaque reviewer answer for --answer-question. Required "
            "exactly once and not valid on its own."
        ),
    )
    p.add_argument("--reject-candidate", action=_TrackExclusiveOption, default=None, metavar="CANDIDATE_VERSION_ID",
                   help="reject and release exactly the active candidate.")
    p.add_argument("--discard-candidate", action=_TrackExclusiveOption, default=None, metavar="CANDIDATE_VERSION_ID",
                   help="discard and release exactly the active candidate.")
    p.add_argument(
        "--decide-candidate",
        action=_TrackExclusiveOption,
        default=None,
        metavar="CANDIDATE_VERSION_ID",
        help=(
            "disclose and decide one active structural candidate with --candidate-decision. "
            "Every decision prints the candidate's narrative evidence before it runs. "
            "Approve prints the candidate's whole stack and its digest and writes nothing until "
            "--confirm-stack-digest supplies that digest."
        ),
    )
    p.add_argument(
        "--candidate-decision",
        action=_TrackExclusiveOption,
        choices=("approve", "edit", "reject"),
        default=None,
        metavar="CHOICE",
        help=(
            "one structural candidate choice: approve, edit, or reject; valid only with --decide-candidate. "
            "Approve is confirmed with --confirm-stack-digest."
        ),
    )
    p.add_argument(
        "--candidate-correction",
        action=_TrackExclusiveOption,
        default=None,
        metavar="TEXT",
        help="one correction for --decide-candidate --candidate-decision edit.",
    )
    p.add_argument(
        "--confirm-stack-digest",
        action=_TrackExclusiveOption,
        default=None,
        metavar="DIGEST",
        help=(
            "the stack digest printed by --decide-candidate --candidate-decision approve, exactly as "
            "printed. Valid only with that pair and needed exactly once; approve refuses with no "
            "write when it differs from the digest recomputed at confirm time. -y is not confirmation."
        ),
    )
    p.add_argument(
        "--promote-review-seal",
        action=_TrackExclusiveOption,
        default=None,
        metavar="REVIEW_SEAL_ID",
        help=(
            "promote exactly one sealed candidate through the accepted-head writer guard; "
            "a structural approval already at the accepted head reports already promoted. "
            "Accepts no companion roadmap option or backend."
        ),
    )
    p.add_argument(
        "--settle-decision",
        action=_TrackExclusiveOption,
        default=None,
        metavar="SELECTOR",
        help=(
            "settle one selected pending Roadmap-derived decision to settled, "
            "only with exactly one --settlement-evidence and one "
            "--confirm-decision-settlement. Accepts no companion roadmap "
            "options and invokes no backend."
        ),
    )
    p.add_argument(
        "--settlement-evidence",
        action=_TrackExclusiveOption,
        default=None,
        metavar="SELECTOR",
        help=(
            "named, live feedback row citing --settle-decision's selected "
            "decision. Required exactly once alongside --settle-decision."
        ),
    )
    p.add_argument(
        "--confirm-decision-settlement",
        action=_TrackExclusiveOption,
        nargs=0,
        const=True,
        default=None,
        help=(
            "explicitly confirm --settle-decision for one selected decision. "
            "Required exactly once; -y is not confirmation."
        ),
    )
    p.add_argument("--respond-decision-settlement", action=_TrackExclusiveOption, default=None, metavar="RECEIPT_FINAL",
                   help="apply one exact enrolled settlement confirmation receipt.")
    p.add_argument("--decision-settlement-yes", action=_TrackExclusiveOption, nargs=0, const=True, default=None,
                   help="affirm --respond-decision-settlement.")
    p.add_argument("--decision-settlement-no", action=_TrackExclusiveOption, nargs=0, const=True, default=None,
                   help="decline --respond-decision-settlement.")
    p.add_argument(
        "--mode",
        choices=[MODE_CURRENT, MODE_REVIEW],
        default=None,
        help=(
            f"valid only with --view: render the design-state roadmap "
            f"({MODE_CURRENT!r}, the default) or the review-channel roadmap "
            f"({MODE_REVIEW!r}, which also surfaces feedback rows and "
            f"removals). Rejected without --view."
        ),
    )
    p.add_argument(
        "--id",
        default=None,
        metavar="ROW_ID",
        help=(
            "valid only with --view index: the row id to query, printing "
            "just that id's citers. Omit for the full citation map. Rejected "
            "with any other --view value."
        ),
    )
    return {"roadmap": cmd_roadmap}
