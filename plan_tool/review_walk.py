"""Interactive walk-through over a saved review's recommendations.

The walk loop takes a :class:`SavedReview`, presents each
recommendation to the user, and records a per-recommendation
:class:`Annotation` (done / skip / note). Annotations persist after
each response so a Ctrl-C mid-walk loses only the in-flight prompt.

The loop is dependency-injected for tests:
- ``input_fn`` defaults to :func:`input` for terminal prompts;
- ``human_input_provider`` optionally replaces the per-walk provider;
- ``output_fn`` defaults to a stdout-printing function;
- ``persist_fn`` defaults to
  :func:`plan_tool.review_persistence.update_annotation`.

Tests inject fakes for all three to exercise the loop deterministically.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import sys
import textwrap
import uuid
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable, Optional

from plan_tool.detail_artifacts import DetailFormatError
from plan_tool.granularity import GRANULARITY_SPLIT_SOURCE
from plan_tool.human_io import (
    HumanInputProvider,
    HumanInputRequest,
    make_human_input_provider,
)
from plan_tool.schema import Plan
from plan_tool.parser import UnsupportedPlanFormatVersionError
from plan_tool.review import AUDIT_FIX_SOURCES as _AUDIT_FIX_SOURCES
from plan_tool.review import (
    RESTATED_PROPERTY_LABEL,
    MergeAction,
    Recommendation,
    confidence_label,
    is_pairwise_merge_finding,
    is_structural,
    parse_merge_action,
    restated_property_or_none,
    severity_label,
)
from plan_tool.review_persistence import (
    Annotation,
    SavedReview,
    update_annotation,
)

# Sentinel title for a target id absent from the plan (deleted or renumbered
# past the end). Distinct from any real title so a missing id hashes
# differently than a present one and never silently collides.
_ABSENT_TARGET = "\x00<absent>\x00"


def compute_target_signature(plan: Plan, target_ids: Iterable[int]) -> str:
    """Hash a directive's target steps' identity into one SHA-256 digest.

    Covers just the ``(id → title + change_type)`` identity of the given
    target ids — not step bodies or the whole plan — so a renumber that makes
    a target id name a different step trips the digest while an unrelated edit
    elsewhere does not. ``change_type`` is a second stable identity dimension,
    making a same-title collision require *also* a same change_type.

    Pure and order-independent: ids are sorted and deduped, and a target id
    absent from ``plan`` hashes to a distinct sentinel rather than raising.
    Precision, not full safety: two steps sharing title+change_type collide, so
    a renumber can read as fresh — the bridges' own target re-validation catches
    most such cases but not all; a stable per-step identity is the full fix
    (BACKLOG #105). Consumed by ``review_actions._saved_directive_is_stale``.
    """
    identity = {s.id: (s.title, s.change_type) for s in plan.steps}
    parts = []
    for step_id in sorted(set(target_ids)):
        title, change_type = identity.get(step_id, (_ABSENT_TARGET, None))
        ct = change_type.value if change_type is not None else ""
        parts.append(f"{step_id}\x1f{title}\x1f{ct}")
    canonical = "\x1e".join(parts)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class WalkState:
    """Mutable state shared between the walk loop and its action handler.

    ``yes_to_all`` is the "fast-forward" flag set by the walk's
    ``aa``/``apply-all`` choice or by the apply-finding "keep these
    changes? [a=all]" choice. Once True, the walk auto-applies remaining
    recommendations without prompting and the CLI's apply-finding
    handler auto-keeps applied diffs without re-asking. Initialize with
    ``yes_to_all=True`` to mirror the effect of ``--yes`` from the very
    first prompt.

    Per-finding drift halt signals. The CLI's
    reconcile-iteration ``_dispatch_apply_finding`` writes these
    when a per-finding drift check fires; ``walk_recommendations``
    checks ``halt_requested`` after each rec's annotation persists
    and breaks the for-loop. ``_iterate_reconcile_loop`` inspects
    the halt fields after the walk returns to decide between the
    merge-continue path (``halt_merged=True``: user merged sidecars;
    record progress + continue) and the legacy halt path
    (``halt_merged=False``: auto-reconcile + emit scope-guard plan +
    return). All halt fields are inert outside reconcile-iteration
    (non-reconcile walks never set them; the walker's break check
    just sees ``halt_requested=False``).

    ``work_landed_in_loop`` tracks whether any apply has kept its
    edits within the current iteration loop. Used by per-finding
    pre-apply drift checks to pick ``"before"`` / ``"during"``
    phrasing without recomputing from ``iter_scope_guard``'s
    snapshots. Reset by the iteration body, not by individual recs.
    """

    yes_to_all: bool = False
    # Set by an action handler during an apply to force the rec's
    # annotation to ``skip`` instead of ``applied`` — e.g. the
    # file-check create/fix sub-prompt records ``skip`` when the user
    # answers "no, the path is wrong" (no edit landed, so "applied"
    # would mislead a later walk). Reset before every action_fn apply
    # call so it never leaks across recs; honored in both the
    # interactive apply branch and ``_auto_apply``.
    apply_skip: bool = False
    # Set by an action handler when the apply *attempt itself errored out*
    # (Claude exited non-zero / a launcher error, snapshot restored — no
    # edit landed), as opposed to ``apply_skip``'s deliberate no-op. Drives
    # a non-terminal ``status="failed"`` annotation so the gap is re-prompted
    # on the next walk (without --rewalk) instead of silently treated as
    # resolved. Reset before every action_fn apply call, like ``apply_skip``.
    apply_failed: bool = False
    # Free-text steering the operator typed via the walk's ``(f)eedback``
    # choice, consumed by the apply handler on the *next* apply: it's
    # injected into the ``apply-finding`` prompt as authoritative guidance
    # so Claude makes the edit the way the operator asked, then cleared so
    # it never leaks onto a sibling rec. Empty string = no pending feedback.
    pending_feedback: str = ""
    halt_requested: bool = False
    halt_merged: bool = False
    halt_apply_landed: bool = False
    halt_finding_id: str = ""
    halt_drifted: list = field(default_factory=list)
    work_landed_in_loop: bool = False
    # Ids of structural findings (merge fold / re-ground mark-done) actuated
    # during THIS walk session. Both rewrite the plan (changing its
    # fingerprint), so the walk's r/run-then-apply re-dispatch would otherwise
    # trip the fingerprint stale-guard and mislabel the *completed* remedy. This
    # explicit signal distinguishes "our own apply changed the plan" (resolve)
    # from an out-of-band renumber (downgrade) — which the fingerprint alone
    # cannot. One set for both: a rec is either a merge or a re-ground directive
    # (never both) and ``rec.id`` is unique, so their ids never collide.
    applied_structural_finding_ids: set = field(default_factory=set)

    def reset_halt(self) -> None:
        """Clear the halt-signal fields. Called by the iteration body
        after handling a halt so subsequent iterations start fresh.
        """
        self.halt_requested = False
        self.halt_merged = False
        self.halt_apply_landed = False
        self.halt_finding_id = ""
        self.halt_drifted = []


@dataclass(frozen=True)
class StructuralOutcomeEffects:
    """The shared post-dispatch ``WalkState`` tail for one structural-dispatch
    outcome, described declaratively so the four structural dispatchers in
    ``review_actions`` state their disposition once instead of hand-setting the
    fields per outcome branch.

    ``resolved`` is the "terminal-applied?" dimension: ``True`` means the
    outcome settled the finding (mutated the plan, or a genuine noop whose
    desired end state already holds) so the walk should record ``applied``
    (leave ``apply_skip`` False); ``False`` means the finding was not resolved,
    so ``apply_skip`` is set and the walk records ``skip``.

    ``record_finding_id`` adds ``rec.id`` to
    ``applied_structural_finding_ids`` — set by the plan-rewriting merge/
    re-ground applies so an r-then-a re-dispatch resolves via that session
    signal instead of the fingerprint stale-guard.

    ``halt`` sets ``halt_requested`` + ``halt_apply_landed`` together — set by
    merge-applied (always) and escalation-applied under ``halt_on_applied``,
    because a landed split/fold renumbers the plan and later saved findings'
    step ids go stale.
    """

    resolved: bool
    record_finding_id: bool = False
    halt: bool = False


def apply_structural_outcome(
    state: WalkState,
    rec: Recommendation,
    effects: StructuralOutcomeEffects,
) -> None:
    """Apply the shared ``WalkState`` side-effect tail for one
    structural-dispatch outcome.

    Owns only the three fields all four structural dispatchers share. Sets
    ``apply_skip`` (only ever to ``True`` — the walk owns the reset before each
    action call), records ``rec.id``, and raises the halt pair, per ``effects``.
    Never reads or writes ``apply_failed``, ``pending_feedback``,
    ``yes_to_all``, or the other halt fields — those stay with their owners.
    """
    if not effects.resolved:
        state.apply_skip = True
    if effects.record_finding_id:
        state.applied_structural_finding_ids.add(rec.id)
    if effects.halt:
        state.halt_requested = True
        state.halt_apply_landed = True


def structural_apply_allowed(opt_in: bool, state: WalkState) -> bool:
    """The shared apply-or-recommend gate for the three bridge dispatchers.

    Returns ``True`` only when the caller opted in (``opt_in``) AND no blanket
    fast-forward is active (``state.yes_to_all`` is False). The escalate/
    reground/merge dispatchers each pass their own opt-in token — ``allow_split``
    for escalation, ``allow_structural_remedy`` for reground/merge — so the two
    tokens stay per-dispatcher; the helper owns only the one rule they share: a
    ``-y`` fast-forward must never auto-confirm an irreversible structure
    mutation. The bridge still owns the TTY confirm (``prompt_fn`` / ``yes``).

    ``_dispatch_file_check_create`` deliberately does NOT route through this
    helper — it inverts the rule (auto-applies ``create`` under ``yes_to_all``).
    """
    return opt_in and not state.yes_to_all


InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]
PersistFn = Callable[[Path, str, Annotation], None]
# Action handler invoked when the walk auto-dispatches an apply or the
# user presses ``r``. Receives the current recommendation; returns an
# optional message to render after the action runs (e.g., "ran reconcile
# on step 3; 2 bullet findings"). When the action returns ``None`` the
# walk just resumes silently.
ActionFn = Callable[[Recommendation], Optional[str]]


class WalkResponsePolicy(Enum):
    """The annotation responses a caller permits for one walk."""

    FULL = "full"
    SKIP_OR_QUIT = "skip-or-quit"


# Suggested-action shapes the walk knows how to dispatch automatically
# when the user applies a recommendation. The walk doesn't *run* these
# itself — the CLI's ``_build_review_action_fn`` does — but it owns
# the pattern definitions so the predicate (``has_recognized_action``)
# and the dispatcher (which extracts step_id and --force) can't drift.
_DETAIL_PAT = re.compile(
    r"plan-tool\s+detail\s+\S+\s+--step\s+(\d+)(\s+--force\b)?"
)
# Detail-side reconcile (audit plan/detail against code; reuses
# apply_finding to land plan edits). Distinct from ``_DETAIL_PAT``
# because the ``--reconcile`` token between ``\S+`` (plan name) and
# ``--step`` makes the authoring pattern miss this shape.
_DETAIL_RECONCILE_PAT = re.compile(
    r"plan-tool\s+detail\s+\S+\s+--reconcile\s+--step\s+(\d+)"
)

# Sources whose ``suggested_action`` mentions a dispatchable command
# only as a SECONDARY option (e.g., "add an entry to LESSONS.md, OR
# run reconcile…"). Auto-dispatching the secondary option would mark
# the rec applied while leaving the user's primary recommended fix
# unaddressed — and reconcile is read-only, so it can't fix the gap
# the rec was flagging. Exclude these sources so apply falls back to
# acknowledgment-only and the user handles the manual edit.
_SECONDARY_DISPATCH_SOURCES = frozenset({"lessons-coverage"})

# Sources whose ``body`` is freeform prose describing a plan-file edit
# (e.g., "step 3 status should be flipped from done → current"). These
# don't have a deterministic command shape — applying them goes through
# Claude via ``apply_finding`` instead. ``detail-reconcile`` covers
# plan-side audit findings produced by ``plan-tool detail --reconcile``
# (they describe plan/detail-file edits); ``claude`` covers semantic
# findings the review's Claude pass surfaces; ``plan-completeness`` covers
# the conceptual coverage-gap findings from the completeness audit.
# Plan-correctness requires explicit caller opt-in via extra_apply_sources;
# generic review/reconcile walks must not auto-apply design findings.
_APPLY_AS_FINDING_SOURCES = frozenset(
    {"detail-reconcile", "claude", "plan-completeness"}
)


def should_apply_as_finding(
    rec: Recommendation,
    *,
    extra_sources: frozenset[str] = frozenset(),
) -> bool:
    """True when ``rec.source`` indicates the apply path should invoke
    Claude-driven finding-application (``apply_finding``) rather than
    a deterministic command dispatcher.

    Distinct from :func:`recognized_action`: this covers recs whose
    ``suggested_action`` is ``None`` but whose ``body`` describes a
    concrete plan-file edit. The walk treats both as "auto-dispatchable
    on apply" via :func:`is_dispatchable`.

    ``extra_sources`` widens the base set for a specific caller. Sources
    with dedicated actuators require a caller-owned mutation or redirect.

    A structural source (:func:`plan_tool.review.is_structural` —
    ``granularity-split`` / ``structural-split``) is *never* an
    apply-finding: its only correct fix is a step split routed through the
    escalate-to-split bridge, not a Claude prose edit. Excluding it here
    keeps a ``granularity-split`` finding out of the ``apply_finding`` route
    even once a caller opts the source into ``extra_apply_sources`` for its
    dedicated split-escalation dispatch (:func:`split_escalation_target`).
    """
    if is_structural(rec):
        return False
    return rec.source in _APPLY_AS_FINDING_SOURCES or rec.source in extra_sources


def file_check_create_target(rec: Recommendation) -> Optional[str]:
    """Repo-relative path a MISSING_PARENT file-check finding can resolve
    by moving from the step's ``files:`` into ``creates:`` on apply.

    Returns the path when ``rec`` is the "declared file path doesn't
    resolve — parent dir doesn't exist" finding (``source == "file-check"``
    with ``file_path`` set), else ``None``. The file-check NEW-on-DONE
    shapes leave ``file_path`` unset — their resolution is a reconcile,
    not a path move — so they don't qualify and apply still falls back
    to acknowledgment-only for them.
    """
    if rec.source == "file-check" and rec.file_path:
        return rec.file_path
    return None


def merge_remedy_target(rec: Recommendation) -> Optional[MergeAction]:
    """The parsed structural-remedy directive a ``granularity-merge`` finding
    carries, or ``None``.

    Keys on the parsed *directive*, not the ``granularity-merge`` source
    string: :func:`review.parse_merge_action` source-guards internally and
    anchors on the exact ``→ (merge|reground) steps:`` marker, so a non-None
    result already means "this is a routable directive finding" (a re-ground
    or a structural merge). The dispatcher (``review_actions``) branches on the
    returned ``MergeAction.kind`` — never the source — so a re-ground can't be
    conflated with a structural merge.
    """
    return parse_merge_action(rec)


def split_escalation_target(
    rec: Recommendation,
    *,
    extra_apply_sources: frozenset[str] = frozenset(),
) -> bool:
    """True when ``rec`` is the ``medium`` ``granularity-split`` MIXED-STEP
    finding that apply should route to the escalate-to-split bridge.

    Gated on the caller opt-in exactly like ``plan-correctness``: dispatchable
    only when the caller passes ``granularity-split`` in ``extra_apply_sources``
    so a generic reconcile/review walk that
    loads a completeness sidecar as its newest save never auto-dispatches it.

    Keys on ``severity == "medium"`` — the mixed-step signal — never
    ``severity`` alone: the deterministic ``info`` split detectors emit the
    same ``granularity-split`` source, and dispatching a low-confidence ``info``
    hint to the split bridge would over-mutate. ``step_id`` is not gated here (a
    ``medium`` rec always carries one; the router surfaces a missing id as a
    re-decompose message). The mutation itself stays gated by ``allow_split`` at
    the bridge — this only decides auto-dispatch.
    """
    return (
        rec.source == GRANULARITY_SPLIT_SOURCE
        and rec.severity == "medium"
        and GRANULARITY_SPLIT_SOURCE in extra_apply_sources
    )


def directive_target_ids(rec: Recommendation) -> Optional[tuple[int, ...]]:
    """The ordered step ids a directive-carrying finding targets, or ``None``.

    One shared recovery so the ids hashed at stamp time
    (:func:`stamp_target_signatures`) and the ids the staleness guards recompute
    (``review_actions._saved_directive_is_stale`` and the split escalation guard)
    can never diverge — both sides call this, never re-derive ids their own way.

    Covers the three directive shapes the guards check:
    - merge / re-ground: ``merge_remedy_target(rec).step_ids`` (the parsed
      ``→ (merge|reground) steps: …`` marker — sorted already);
    - ``medium`` ``granularity-split`` MIXED-STEP: ``(rec.step_id,)``.

    Keys on ``source`` + ``severity`` + ``step_id`` only — dispatch-independent,
    so a ``medium`` split is stampable regardless of ``extra_apply_sources``
    (unlike :func:`split_escalation_target`, which decides *dispatch*). Returns
    ``None`` for every non-directive rec, the ``info`` split hints, and the
    gapped merge advisory (no marker) — the guards read none of their signatures.
    """
    action = merge_remedy_target(rec)
    if action is not None:
        return action.step_ids
    if (
        rec.source == GRANULARITY_SPLIT_SOURCE
        and rec.severity == "medium"
        and rec.step_id is not None
    ):
        return (rec.step_id,)
    return None


def stamp_target_signatures(
    plan: Plan, recs: Iterable[Recommendation]
) -> list[Recommendation]:
    """Return ``recs`` with ``target_signature`` set on every directive-carrying
    rec, computed over that directive's own target steps.

    Pure reshaping of a list — no I/O, no invoker, no Claude. ``Recommendation``
    is frozen, so a stamped rec is a fresh :func:`dataclasses.replace` copy;
    non-directive recs pass through as the same object. The recovered ids go
    straight to :func:`compute_target_signature` (which sorts + dedupes), so the
    stamp and the guards hash the identical canonical form.
    """
    stamped: list[Recommendation] = []
    for rec in recs:
        ids = directive_target_ids(rec)
        if ids is None:
            stamped.append(rec)
        else:
            stamped.append(
                replace(
                    rec,
                    target_signature=compute_target_signature(plan, ids),
                )
            )
    return stamped


def is_dispatchable(
    rec: Recommendation,
    *,
    extra_apply_sources: frozenset[str] = frozenset(),
) -> bool:
    """True when apply should auto-dispatch ``rec`` rather than just
    record an annotation.

    Five paths qualify:

    - The rec's ``suggested_action`` matches a recognized command
      pattern (reconcile/detail) — :func:`recognized_action` returns
      a descriptor.
    - The rec's source indicates it should be applied via
      ``apply_finding`` (reconcile-kind findings, claude semantic
      findings) — :func:`should_apply_as_finding` returns True.
    - The rec is a MISSING_PARENT file-check finding whose path apply
      can move into ``creates:`` — :func:`file_check_create_target`
      returns a path.
    - The rec is a ``granularity-merge`` finding carrying a structural-
      remedy directive (re-ground or merge) — :func:`merge_remedy_target`
      returns a parsed ``MergeAction``.
    - The rec is the ``medium`` ``granularity-split`` MIXED-STEP finding
      and the caller opted the source into ``extra_apply_sources`` —
      :func:`split_escalation_target` returns True (routes to the
      escalate-to-split bridge, not ``apply_finding``).

    ``extra_apply_sources`` is forwarded to :func:`should_apply_as_finding`
    so a specific walk can widen the apply-eligible sources without affecting
    the generic reconcile/review walks. The caller-supplied ``action_fn`` must
    agree with that widened source set; for saved audit families whose edits
    are not plan-file ``apply_finding`` work, pass a command-local callback
    that handles or deliberately no-ops the source.
    """
    if recognized_action(rec) is not None:
        return True
    if should_apply_as_finding(rec, extra_sources=extra_apply_sources):
        return True
    if file_check_create_target(rec) is not None:
        return True
    if merge_remedy_target(rec) is not None:
        return True
    if split_escalation_target(rec, extra_apply_sources=extra_apply_sources):
        return True
    return False


@dataclass(frozen=True)
class RecognizedAction:
    """Parsed parameters for a suggested action the walk can auto-dispatch.

    Returned by :func:`recognized_action` when the rec's
    ``suggested_action`` matches a known pattern. ``kind`` selects the
    dispatcher; ``step_id`` is the target step; ``force`` is only
    meaningful for ``kind="detail"`` (always False for
    ``"detail-reconcile"`` — it has no skip-when-exists check to
    override).
    """

    kind: str  # "detail" | "detail-reconcile"
    step_id: int
    force: bool = False


def recognized_action(rec: Recommendation) -> Optional[RecognizedAction]:
    """Parse ``rec.suggested_action`` into a dispatcher descriptor.

    Returns ``None`` for recs with no suggested action and for shapes
    the handler can't run (deps, files-coherence drift, free-form
    claude findings, etc.) — apply falls back to acknowledgment-only
    for those.

    Single source of truth for both the apply-time predicate
    (``has_recognized_action``) and the CLI's action handler so the
    walk can't claim a rec is dispatchable while the handler fails to
    parse it.
    """
    if not rec.suggested_action:
        return None
    if rec.source in _SECONDARY_DISPATCH_SOURCES:
        # Pattern would match, but the command is a secondary option —
        # auto-dispatch would mark the rec applied without addressing
        # the user's primary recommended fix.
        return None
    # ``_DETAIL_RECONCILE_PAT`` must be tried before ``_DETAIL_PAT`` so
    # a future loosening of either pattern can't silently mis-dispatch
    # ``detail --reconcile`` shapes through the authoring handler.
    m = _DETAIL_RECONCILE_PAT.search(rec.suggested_action)
    if m is not None:
        return RecognizedAction(
            kind="detail-reconcile", step_id=int(m.group(1))
        )
    m = _DETAIL_PAT.search(rec.suggested_action)
    if m is not None:
        # Reverse flag order: `detail X --step N --reconcile` matches
        # _DETAIL_PAT (which only anchors --reconcile *before* --step), so
        # detect the token independent of position to avoid misrouting an
        # audit action through the authoring handler.
        if "--reconcile" in rec.suggested_action:
            return RecognizedAction(
                kind="detail-reconcile", step_id=int(m.group(1))
            )
        return RecognizedAction(
            kind="detail",
            step_id=int(m.group(1)),
            force=m.group(2) is not None,
        )
    return None


def has_recognized_action(rec: Recommendation) -> bool:
    """Convenience predicate over :func:`recognized_action`."""
    return recognized_action(rec) is not None


HELP_TEXT = (
    "  a / apply — apply this recommendation. When the suggested action is\n"
    "              recognized (reconcile or detail) the walk runs it now;\n"
    "              otherwise the rec is recorded as 'applied' for you to\n"
    "              address manually.\n"
    "  <Enter>  — same as apply — the default assumes you'll address each\n"
    "              rec the walk surfaces. Use 's' to skip explicitly.\n"
    "  aa / apply-all — apply this rec and auto-apply every remaining rec\n"
    "              in this walk without prompting. Also silences the\n"
    "              apply-finding 'keep these changes?' confirmation for\n"
    "              the rest of the session. Equivalent to retroactively\n"
    "              passing --yes.\n"
    "  s / skip  — mark as skip (won't re-prompt unless --rewalk)\n"
    "  f / feedback — type guidance for how to apply this rec; it's both\n"
    "              recorded as a note AND fed into the next apply so Claude\n"
    "              makes the edit the way you described (re-prompts for\n"
    "              status after). 'n'/'note' are aliases.\n"
    "  r / run   — execute the recommendation's suggested action and re-\n"
    "              prompt for status — useful when you want to inspect the\n"
    "              outcome before committing to applied/skip.\n"
    "  q / quit  — exit the walk; previously-marked items keep their state\n"
    "  ? / help  — print this help\n\n"
    "Items already marked applied or skipped are not re-prompted; pass\n"
    "--rewalk to revisit them."
)


@dataclass(frozen=True)
class WalkResult:
    """Summary of one walk session.

    ``answered`` is the count of items that received a status this run
    (excludes items that were already annotated and not re-prompted).
    ``quit_early`` is True when the user typed ``q`` before reaching the
    end of the list.
    """

    answered: int
    quit_early: bool


def _default_output(line: str) -> None:
    print(line)


def walk_recommendations(
    saved: SavedReview,
    *,
    input_fn: InputFn = input,
    human_input_provider: Optional[HumanInputProvider] = None,
    output_fn: OutputFn = _default_output,
    persist_fn: PersistFn = update_annotation,
    rewalk: bool = False,
    action_fn: Optional[ActionFn] = None,
    state: Optional[WalkState] = None,
    skip_info: bool = False,
    extra_apply_sources: frozenset[str] = frozenset(),
    response_policy: WalkResponsePolicy = WalkResponsePolicy.FULL,
    render_recommendation: bool = True,
) -> WalkResult:
    """Iterate over ``saved.recommendations``, prompting per item.

    Skips items already in ``saved.annotations`` unless ``rewalk=True``.
    Annotations persist via ``persist_fn`` after each user response so
    Ctrl-C between prompts loses only the in-flight question.

    ``human_input_provider`` optionally injects the provider shared by every
    command and feedback read. Otherwise the provider is selected from ``input_fn``.

    The saved file path lives on ``saved.path``; raises ``ValueError``
    when ``saved.path`` is ``None`` (the in-memory ``SavedReview``
    didn't come from ``load_review``). This protects against silently
    losing annotations.

    ``action_fn`` powers two keys:

    - ``r`` (run): always invokes ``action_fn(rec)`` then re-prompts
      for status — the inspect-then-decide path.
    - apply (Enter / ``a``): invokes ``action_fn(rec)`` only when
      :func:`is_dispatchable` is True (recognized command shapes, base
      apply-as-finding sources, caller-supplied extra apply sources, and
      deterministic structural/file fixes), then marks the rec applied.
      For unrecognized shapes, apply records the annotation only.

    When ``action_fn`` is ``None``, ``r`` surfaces a "no action handler
    registered" notice and apply always falls back to annotation-only.
    The CLI passes a real handler (``_build_review_action_fn``) that
    dispatches reconcile/detail invocations and generic plan-file findings.
    Callers that opt additional saved-audit sources into dispatchability
    should supply a handler that owns those sources instead of relying on the
    generic action builder.

    Triage asymmetry note (session 4 follow-up): the iteration loop
    (``cli._iterate_reconcile_loop``) applies an impact-weighted
    triage filter to its in-memory view of ``saved.recommendations``
    before walking, so deferred recs don't consume tokens on
    apply_finding. ``walk_recommendations`` does NOT filter -- the
    on-disk JSON is intentionally complete (apply + deferred) so
    later ``plan-tool reconcile-plan-walk`` invocations see every finding
    the operator may want to handle manually. If a deferred rec is
    visible here that the iteration loop skipped, that's by design:
    reconcile-plan-walk is the manual-override path. Use ``--no-triage`` at
    the iterate call site to disable the filter upstream.

    ``skip_info`` hides ``info``-severity recommendations from the walk
    (the low-confidence heuristic hints that, on apply, typically
    dispatch a reconcile and land no edit — pure token spend), except a
    pairwise ``granularity-merge`` finding
    (:func:`plan_tool.review.is_pairwise_merge_finding`), which stays visible
    because it is part of the structural-remedy surface, not a heuristic hint —
    both the dispatchable contiguous pair and the gapped recommend-only
    advisory (a ``reground`` directive keeps its ``--include-info`` requirement). The
    on-disk JSON stays complete: the info recs are still saved and a
    later ``reconcile-plan-walk --include-info`` surfaces them. Off by default
    so reconcile-iteration walks (whose findings carry real severities)
    are unaffected; the ``review`` and ``reconcile-plan-walk`` CLI entry points
    pass it through with their default-skip behavior.

    ``response_policy`` defaults to the full annotation menu. Callers can opt
    into ``SKIP_OR_QUIT`` to accept only skip or quit responses; every other
    normalized response exits the walk before action or feedback handling.
    """
    if saved.path is None:
        raise ValueError(
            "walk_recommendations requires a SavedReview loaded from disk "
            "(saved.path must be set so annotations can persist)"
        )

    if state is None:
        state = WalkState()

    def provider_for_prompt() -> HumanInputProvider:
        nonlocal human_input_provider
        if human_input_provider is None:
            human_input_provider = make_human_input_provider(input_fn)
        return human_input_provider

    answered = 0
    recs = saved.recommendations
    skipped_info = 0
    if skip_info:
        # A pairwise ``granularity-merge`` finding is part of the targeted
        # structural walk surface even at ``info`` severity (they stay ``info``),
        # so keep it visible under the default hide — whether it carries a
        # dispatchable ``merge`` directive (contiguous pair) or is the gapped
        # recommend-only advisory (no marker). The plan-wide ``reground``
        # directive keeps requiring ``--include-info`` (its shipped contract);
        # every other directive-less info finding honors the default hide too.
        visible = [
            r for r in recs
            if (r.severity or "").lower() != "info" or is_pairwise_merge_finding(r)
        ]
        skipped_info = len(recs) - len(visible)
        recs = visible
    total = len(recs)
    label = saved.kind if saved.kind != "review" else "review"
    output_fn(
        f"\nWalking {total} {label} recommendation(s) for plan {saved.plan_slug!r}."
    )
    output_fn(f"Saved {label}: {saved.path}\n")
    if skipped_info:
        output_fn(
            f"(skipping {skipped_info} info-level finding(s); "
            f"pass --include-info to walk them)\n"
        )

    for idx, rec in enumerate(recs, start=1):
        if not rewalk and rec.id in saved.annotations:
            existing = saved.annotations[rec.id]
            # A ``failed`` apply (the attempt errored out, no edit landed)
            # is NOT a terminal answer: fall through to re-prompt it without
            # --rewalk so a transient apply failure is retried rather than
            # silently treated as resolved. Terminal statuses
            # (applied / skip / open) pre-skip as before.
            if existing.status != "failed":
                output_fn(
                    f"[{idx}/{total}] {rec.title}\n"
                    f"    ({confidence_label(rec.confidence)}; already "
                    f"{existing.status}; skipping — pass --rewalk to revisit)"
                )
                continue
            output_fn(
                f"    (rec {rec.id} previously failed to apply; retrying)"
            )

        if render_recommendation:
            output_fn(_format_recommendation(idx, total, rec))

        if state.yes_to_all and response_policy is WalkResponsePolicy.FULL:
            annotation = _auto_apply(
                rec, action_fn=action_fn, output_fn=output_fn, state=state,
                extra_apply_sources=extra_apply_sources,
            )
            if annotation is None:
                # Auto-apply path declined (action failed → state.yes_to_all
                # was cleared); fall through to the normal prompt so the
                # user can skip / note / quit on this rec.
                annotation = _prompt_for_annotation(
                    human_input_provider=provider_for_prompt(),
                    output_fn=output_fn,
                    rec=rec,
                    action_fn=action_fn,
                    state=state,
                    extra_apply_sources=extra_apply_sources,
                    response_policy=response_policy,
                )
                if annotation is None:
                    output_fn("Quit. Previously-marked items keep their state.")
                    return WalkResult(answered=answered, quit_early=True)
        else:
            annotation = _prompt_for_annotation(
                human_input_provider=provider_for_prompt(),
                output_fn=output_fn,
                rec=rec,
                action_fn=action_fn,
                state=state,
                extra_apply_sources=extra_apply_sources,
                response_policy=response_policy,
            )
            if annotation is None:
                output_fn("Quit. Previously-marked items keep their state.")
                return WalkResult(answered=answered, quit_early=True)

        persist_fn(saved.path, rec.id, annotation)
        saved.annotations[rec.id] = annotation
        answered += 1

        # Per-finding halt signal. The CLI's
        # reconcile-iteration action_fn sets ``halt_requested`` when a
        # per-finding drift check fires; break here so the iteration
        # body can inspect the halt fields and pick the merge-continue
        # vs. drift-halt path. Persistence of the current rec's
        # annotation already happened above so the on-disk record
        # reflects the in-flight finding's outcome. Non-reconcile walks
        # never set this flag and behave unchanged.
        if state.halt_requested:
            break

    output_fn(f"\nDone. {answered} item(s) annotated this session.")
    return WalkResult(answered=answered, quit_early=False)


def _auto_apply(
    rec: Recommendation,
    *,
    action_fn: Optional[ActionFn],
    output_fn: OutputFn,
    state: WalkState,
    extra_apply_sources: frozenset[str] = frozenset(),
) -> Optional[Annotation]:
    """Apply ``rec`` without prompting (used by the ``apply-all`` mode).

    Returns the resulting Annotation, or ``None`` when the action raises —
    in which case ``state.yes_to_all`` is cleared so the caller can fall
    back to the interactive prompt for this rec (and stop auto-applying
    the remaining ones until the user re-opts in). Caller-supplied
    ``extra_apply_sources`` use the same dispatch predicate as the
    interactive apply branch, so they must be paired with an action handler
    that can safely handle those sources.
    """
    output_fn("  (apply-all) auto-applying")
    msg: Optional[str] = None
    if action_fn is not None and is_dispatchable(
        rec, extra_apply_sources=extra_apply_sources
    ):
        state.apply_skip = False
        state.apply_failed = False
        try:
            msg = action_fn(rec)
        except (DetailFormatError, UnsupportedPlanFormatVersionError):
            raise
        except Exception as exc:  # pragma: no cover - surfaced to user
            output_fn(f"  action failed: {exc}")
            output_fn("  (apply-all) disabled; falling back to prompt")
            state.yes_to_all = False
            return None
        if msg:
            output_fn(f"  {msg}")
    note = msg.strip() if msg else ""
    # The apply attempt errored out (Claude non-zero / launcher error, no
    # edit landed). Record a non-terminal "failed" so the next walk
    # re-prompts it rather than treating it as resolved. Checked before
    # ``apply_skip`` (a genuine failure is never a deliberate no-op).
    if state.apply_failed:
        return Annotation(status="failed", note=note)
    # An action handler may downgrade this apply to a skip (e.g. the
    # file-check create/fix prompt when the path is wrong). No edit
    # landed, so record skip rather than a misleading "applied".
    if state.apply_skip:
        return Annotation(status="skip", note=note)
    # when action_fn signaled halt because the apply
    # was SKIPPED (pre-apply drift -- no claude tokens spent, no
    # edits landed), persist the rec as "skip" not "applied". The
    # "applied" status would otherwise mislead future reconcile-plan-walk
    # invocations into believing the rec had been resolved. Post-
    # apply drift halts keep "applied" (the edits did land).
    if state.halt_requested and not state.halt_apply_landed:
        return Annotation(status="skip", note=note, halt_reason="drift")
    return Annotation(status="applied", note=note)


# ANSI styling for the walk. Disabled outside a TTY (so captured/piped
# output stays plain) and when ``NO_COLOR`` is set; ``PLAN_TOOL_FORCE_COLOR``
# forces it on for demos. Tests capture via a fake ``output_fn`` (no TTY),
# so they see plain text and can assert on substrings like ``[HIGH]``.
_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
# Severity → badge style. Critical is inverted (white-on-red) so it can't
# be skimmed past; the rest tint the bracketed tag.
_SEVERITY_STYLE = {
    "CRITICAL": "\033[1;97;41m",
    "HIGH": "\033[1;31m",
    "MEDIUM": "\033[33m",
    "LOW": "\033[36m",
    "INFO": "\033[2m",
}
# Inline `code` spans — highlighted after wrapping so the ANSI bytes don't
# throw off the wrap width.
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")


def _color_enabled() -> bool:
    if os.environ.get("PLAN_TOOL_FORCE_COLOR"):
        return True
    if os.environ.get("NO_COLOR"):
        return False
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


def _term_width() -> int:
    # Cap so lines stay readable on ultra-wide terminals.
    return min(shutil.get_terminal_size((80, 24)).columns, 100)


def _wrap(text: str, indent: str, width: int) -> list[str]:
    """Wrap ``text`` to ``width`` and prefix each line with ``indent``.

    ``break_long_words=False`` keeps unbroken tokens (file paths, flags)
    intact rather than chopping them mid-string.
    """
    body_width = max(20, width - len(indent))
    wrapped = textwrap.wrap(
        text.strip(),
        width=body_width,
        break_long_words=False,
        break_on_hyphens=False,
    )
    return [indent + line for line in wrapped]


def _format_recommendation(idx: int, total: int, rec: Recommendation) -> str:
    """Build the multi-line block shown for one recommendation."""
    color = _color_enabled()
    width = _term_width()

    def paint(text: str, style: str) -> str:
        return f"{style}{text}{_RESET}" if color else text

    def highlight_code(text: str) -> str:
        if not color:
            return text
        return _INLINE_CODE_RE.sub(
            lambda m: f"{_BOLD}`{m.group(1)}`{_RESET}", text
        )

    sev = severity_label(rec.severity)
    sev_style = _SEVERITY_STYLE.get(sev, _DIM)

    source = f"source: {rec.source} · {confidence_label(rec.confidence)}"
    if rec.step_id is not None:
        source += f" · step {rec.step_id}"
    # Surface the triage pair so a low/low wording fix isn't triaged with the
    # same weight as its severity token — a MEDIUM whose fix is one sentence
    # reads differently once impact/complexity are on the line.
    if rec.impact or rec.complexity:
        source += (
            f" · impact {rec.impact or '?'} · complexity {rec.complexity or '?'}"
        )

    lines = [
        "",
        paint("─" * width, _DIM),
        f"{paint(f'[{idx}/{total}]', _DIM)} "
        f"{paint(f'[{sev}]', sev_style)} {paint(rec.title, _BOLD)}",
        paint(f"  {source}", _DIM),
        "",
    ]
    lines += [highlight_code(line) for line in _wrap(rec.body, "  ", width)]
    restated = restated_property_or_none(rec)
    if restated:
        # Distinct styling from the "will apply"/"suggested" action label
        # below so it doesn't read as an instruction.
        lines += ["", paint(f"  {RESTATED_PROPERTY_LABEL}", _DIM)]
        lines += [
            highlight_code(line) for line in _wrap(restated, "    ", width)
        ]
    if rec.suggested_action:
        # For plan-audit findings the action IS the edit apply will make,
        # so label it "will apply" to spell out what selecting (a)pply does.
        # Other sources carry a follow-up command/check, not a guaranteed
        # apply, so they keep the softer "suggested" label. Same source set
        # that feeds apply's targeted-fix injection (``audit_targeted_fix``).
        label = "will apply" if rec.source in _AUDIT_FIX_SOURCES else "suggested"
        lines += ["", paint(f"  {label}", _BOLD)]
        lines += [
            highlight_code(line)
            for line in _wrap(rec.suggested_action, "    ", width)
        ]
    return "\n".join(lines)


def _prompt_for_annotation(
    *,
    human_input_provider: HumanInputProvider,
    output_fn: OutputFn,
    rec: Recommendation,
    action_fn: Optional[ActionFn] = None,
    state: Optional[WalkState] = None,
    extra_apply_sources: frozenset[str] = frozenset(),
    response_policy: WalkResponsePolicy = WalkResponsePolicy.FULL,
) -> Optional[Annotation]:
    """Prompt the user for a status; loop on invalid input.

    Returns ``None`` when the user quits. The ``feedback`` flow asks for
    free-text guidance, records it as the rec's note AND stashes it on
    ``state.pending_feedback`` to steer the next apply, then re-prompts
    for a final status (apply / skip) so feedback alone doesn't leave an
    item in limbo. (``note`` is a back-compat alias for ``feedback``.)

    Apply (Enter / ``a``) auto-dispatches when the rec's suggested action
    is recognized (reconcile or detail) AND an ``action_fn`` is wired:
    the walk invokes the action and marks the rec applied with the
    action's return message as the note. When the action raises, the
    error surfaces and the walk re-prompts so the user can pick a
    different status. For recs without a recognized action, apply
    records the annotation only.

    The ``run`` flow invokes ``action_fn(rec)`` and then re-prompts for
    status — useful when the user wants to inspect the action's outcome
    before committing to applied/skip.
    """
    if state is None:
        state = WalkState()
    pending_note = ""
    while True:
        # ``[default]`` after (a)pply advertises the Enter-default — the
        # walk assumes the user will act on each rec they're shown.
        # Items the user has *already* annotated applied or skipped
        # don't reach this prompt at all (the loop above pre-skips them
        # unless --rewalk is set).
        prompt = (
            "  (s)kip / (q)uit > "
            if response_policy is WalkResponsePolicy.SKIP_OR_QUIT
            else (
                "  (a)pply [default] / (s)kip / (f)eedback / (r)un / "
                "(aa) apply-all / (q)uit / (?) help > "
            )
        )
        raw = (
            _request_human_input(
                human_input_provider,
                prompt_id="review-walk.annotation",
                prompt=prompt,
            )
            .strip()
            .lower()
        )
        if response_policy is WalkResponsePolicy.SKIP_OR_QUIT:
            if raw in ("s", "skip"):
                return Annotation(status="skip", note="")
            return None
        # Fast-forward intent: apply this rec, then auto-apply every
        # remaining rec. We defer flipping ``state.yes_to_all`` until
        # the apply on *this* rec actually succeeds — a failure here
        # means we couldn't even get the first one right, so blindly
        # auto-applying the rest is the wrong call.
        enable_apply_all = raw in ("aa", "apply-all", "all")
        if enable_apply_all:
            raw = "a"  # fall through to the apply path for this rec
        if raw in ("", "a", "apply", "d", "done"):
            # Accept ``d`` / ``done`` for backward compatibility with
            # walk muscle-memory; the canonical key is ``a``.
            if action_fn is not None and is_dispatchable(
                rec, extra_apply_sources=extra_apply_sources
            ):
                state.apply_skip = False
                state.apply_failed = False
                try:
                    msg = action_fn(rec)
                except (DetailFormatError, UnsupportedPlanFormatVersionError):
                    raise
                except Exception as exc:  # pragma: no cover - surfaced to user
                    output_fn(f"  action failed: {exc}")
                    # Re-prompt so the user can skip/note instead of
                    # falsely recording an applied status on a failed run.
                    continue
                if msg:
                    output_fn(f"  {msg}")
                if enable_apply_all:
                    state.yes_to_all = True
                    output_fn(
                        "  (apply-all) enabled — remaining recs will be "
                        "auto-applied"
                    )
                # User-entered note (via 'n' before applying) wins over
                # the action's return message — preserves intent when
                # the user has already captured context.
                note = pending_note or (msg.strip() if msg else "")
                # The apply attempt errored out (no edit landed): record a
                # non-terminal "failed" so the next walk re-prompts it.
                # Checked before ``apply_skip`` (a failure is never a no-op).
                if state.apply_failed:
                    return Annotation(status="failed", note=note)
                # An action handler may downgrade this apply to a skip
                # (file-check create/fix "path is wrong" branch): no
                # edit landed, so record skip.
                if state.apply_skip:
                    return Annotation(status="skip", note=note)
                # pre-apply drift halt → "skip" status
                # (no apply landed). Post-apply drift halt or normal
                # apply → "applied" status. Same logic as ``_auto_apply``.
                if state.halt_requested and not state.halt_apply_landed:
                    return Annotation(
                        status="skip", note=note, halt_reason="drift"
                    )
                return Annotation(status="applied", note=note)
            if enable_apply_all:
                state.yes_to_all = True
                output_fn(
                    "  (apply-all) enabled — remaining recs will be "
                    "auto-applied"
                )
            return Annotation(status="applied", note=pending_note)
        if raw in ("s", "skip"):
            return Annotation(status="skip", note=pending_note)
        if raw in ("q", "quit"):
            return None
        if raw in ("?", "help"):
            output_fn(HELP_TEXT)
            continue
        if raw in ("f", "feedback", "n", "note"):
            # ``n``/``note`` kept as aliases for walk muscle-memory; the
            # canonical key is ``f``. The text is dual-purpose: it's
            # recorded as the rec's annotation (the old note behavior) AND
            # stashed as steering for the next apply, so selecting feedback
            # then apply makes Claude edit the way the operator described.
            feedback = _request_human_input(
                human_input_provider,
                prompt_id="review-walk.feedback",
                prompt="  feedback: ",
            )
            pending_note = feedback.strip()
            state.pending_feedback = pending_note
            output_fn(f"  feedback noted (steers the next apply): {pending_note}")
            # Loop back to the status prompt so the user picks apply/skip.
            continue
        if raw in ("r", "run"):
            if action_fn is None:
                output_fn(
                    "  no action handler registered for this walk; "
                    "use 'd' or 's' to mark, or run the suggested action "
                    "in another shell"
                )
                continue
            try:
                msg = action_fn(rec)
            except (DetailFormatError, UnsupportedPlanFormatVersionError):
                raise
            except Exception as exc:  # pragma: no cover - surfaced to user
                output_fn(f"  action failed: {exc}")
                continue
            if msg:
                output_fn(f"  {msg}")
            # Re-prompt for status — the action ran, but the user still
            # needs to mark the item done/skip in *this* walk.
            continue
        output_fn("  unrecognized input; type ? for help")


def _request_human_input(
    provider: HumanInputProvider,
    *,
    prompt_id: str,
    prompt: str,
) -> str:
    """Return one provider-supplied response for a fresh walk prompt."""
    return provider(
        HumanInputRequest(
            request_id=uuid.uuid4().hex,
            prompt_id=prompt_id,
            prompt=prompt,
        )
    ).text
