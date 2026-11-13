"""CLI orchestration for scoped concept review and synchronization."""

from __future__ import annotations

import argparse

from plan_tool.cli.context import _load_context
from plan_tool.cli.parser import Handler
from plan_tool.concept_bootstrap import (
    bootstrap_concepts,
    empty_concept_headings_message,
    rederive_concepts,
)
from plan_tool.concept_review import (
    CONCEPT_DECISIONS,
    ConceptReviewError,
    review_concept_scope,
)
from plan_tool.concept_sync import SyncStatus, synchronize_concepts
from plan_tool.concept_tree import (
    RECORD_KIND_DECISION,
    InvalidConceptTreeError,
    StaleConceptTreeError,
    load_concepts,
)
from plan_tool.locator import resolve_plan_for_context, slug_from_filename
from plan_tool.parser import parse_body_sections, parse_plan, split_plan_document
from plan_tool.review_persistence import compute_plan_fingerprint
from plan_tool.scope_fence import _fenced_code_spans
from plan_tool.style import success, warn


SCOPE_REVIEW_CONFLICT_EXIT = 3
SCOPE_REVIEW_INVALID_STATE_EXIT = 4


def _decision(value: str) -> tuple[str, str]:
    concept_id, separator, decision = value.partition("=")
    if not separator or not concept_id or decision not in CONCEPT_DECISIONS:
        choices = ", ".join(sorted(CONCEPT_DECISIONS))
        raise argparse.ArgumentTypeError(
            f"expected CONCEPT_ID=DECISION, where DECISION is one of: {choices}"
        )
    return concept_id, decision


def _sign_off_decision_record(
    source_plan_text: str,
    original_tree,
    concept_ids: list[str],
    decisions: list[tuple[str, str]],
):
    """Confirm scoped decisions on a flat record, or return a refusal exit code.

    Returns the reviewed :class:`ConceptTree` on success, or one of the
    ``SCOPE_REVIEW_*`` exit-code ints on a refusal (nothing is written).
    A flat record's only currency question is whether a scoped node's ``bucket``
    still names a current body section — a gone bucket only *warns* here (so a
    missing-bucket decision stays confirmable), never blocks. All refusal checks
    run before any candidate is built, so a rejected request writes nothing.
    """
    # A flat decision record can hold only defer/wont_do; refuse include up front
    # with an actionable message rather than an opaque tree-validation error.
    for concept, decision in decisions:
        if decision == "include":
            warn(
                f"scope-review cannot record an `include` decision for `{concept}` "
                "on a decision record (only defer/wont_do); no changes were written."
            )
            return SCOPE_REVIEW_INVALID_STATE_EXIT

    # Same normalized H2 name lookup review.check_concept_coverage uses, so the
    # confirm gate and the surfaced concept-bucket-missing finding never disagree.
    section_names = {
        section.name
        for section in parse_body_sections(
            split_plan_document(source_plan_text).body,
            ignore_fenced_code=True,
        )
    }
    nodes_by_id = {node.id: node for node in original_tree.concepts}
    for concept in concept_ids:
        node = nodes_by_id.get(concept)
        if node is None:
            warn(
                f"scope-review scope contains unknown concept `{concept}`; "
                "no changes were written."
            )
            return SCOPE_REVIEW_INVALID_STATE_EXIT
        if node.bucket not in section_names:
            warn(
                f"scope-review: concept `{concept}` is parked under bucket "
                f"`{node.bucket}`, which no longer names a plan body section; "
                "signing off the decision anyway."
            )

    # Passing the record's own stored fingerprint as expected_source_state makes
    # the whole-bundle staleness check a no-op — the per-bucket gate above is the
    # real currency check. The full record is the candidate, so review_concept_scope
    # signs off only the scoped nodes and leaves every unscoped node untouched.
    try:
        return review_concept_scope(
            original_tree,
            concept_ids,
            decisions,
            original_tree.plan_fingerprint,
            sign_off=True,
        )
    except ConceptReviewError as exc:
        warn(f"scope-review invalid state for requested scope: {exc}; no changes were written.")
        return SCOPE_REVIEW_INVALID_STATE_EXIT


def cmd_scope_review(args: argparse.Namespace) -> int:
    """Review exactly the requested concepts and synchronize accepted state."""
    context = _load_context(args)
    plan_path = resolve_plan_for_context(context, args.name)
    source_plan_text = plan_path.read_bytes().decode("utf-8")
    if _fenced_code_spans(
        split_plan_document(source_plan_text).body
    ).unmatched_opening is not None:
        warn(
            f"{plan_path}: unmatched opening code fence; add a matching closing "
            "fence before running scope-review. No changes were written."
        )
        return SCOPE_REVIEW_INVALID_STATE_EXIT
    plan = parse_plan(plan_path)
    fingerprint = compute_plan_fingerprint(plan_path)
    slug = slug_from_filename(plan_path)
    assert slug is not None

    try:
        original_tree = load_concepts(plan_path, fingerprint)
    except (InvalidConceptTreeError, StaleConceptTreeError) as exc:
        warn(f"scope-review invalid state: {exc}. Repair or remove the concept record explicitly; no changes were written.")
        return SCOPE_REVIEW_INVALID_STATE_EXIT

    if original_tree is None:
        warn(
            "scope-review has no concept record to confirm; "
            "`create`/`detail` produce the pending decisions it signs off. "
            "No changes were written."
        )
        return SCOPE_REVIEW_INVALID_STATE_EXIT

    concept_ids = list(args.concept)
    decisions = list(args.decision)

    if original_tree.record_kind == RECORD_KIND_DECISION:
        outcome = _sign_off_decision_record(
            source_plan_text, original_tree, concept_ids, decisions
        )
        if isinstance(outcome, int):
            return outcome
        reviewed_tree = outcome
    else:
        # Legacy full-tree record: re-derive the whole tree from the current
        # plan body and review the candidate (dual-mode — kept for records
        # written before the flat decision-record shape; see plan #131).
        sections = parse_body_sections(
            split_plan_document(source_plan_text).body,
            ignore_fenced_code=True,
        )
        message = empty_concept_headings_message(sections)
        if message is not None:
            warn(f"{plan_path}: {message} No changes were written.")
            return SCOPE_REVIEW_INVALID_STATE_EXIT
        fresh_tree = bootstrap_concepts(
            plan,
            sections,
            plan_slug=slug,
            plan_fingerprint=fingerprint,
        )
        derivation = rederive_concepts(original_tree, fresh_tree)
        if derivation.conflicts:
            for conflict in derivation.conflicts:
                warn(
                    f"scope-review conflict for {conflict.concept_id} "
                    f"({conflict.field}: {conflict.reason})"
                )
            warn("No changes were written.")
            return SCOPE_REVIEW_CONFLICT_EXIT
        try:
            reviewed_tree = review_concept_scope(
                derivation.candidate,
                concept_ids,
                decisions,
                fingerprint,
                sign_off=True,
            )
        except ConceptReviewError as exc:
            warn(f"scope-review invalid state for requested scope: {exc}; no changes were written.")
            return SCOPE_REVIEW_INVALID_STATE_EXIT

    result = synchronize_concepts(
        plan_path,
        plan,
        original_tree,
        reviewed_tree,
        source_plan_text=source_plan_text,
    )
    if not result.succeeded:
        conflict_statuses = {SyncStatus.SOURCE_DIVERGENCE, SyncStatus.MAPPING_CONFLICT}
        exit_code = (
            SCOPE_REVIEW_CONFLICT_EXIT
            if result.status in conflict_statuses
            else SCOPE_REVIEW_INVALID_STATE_EXIT
        )
        if result.rollback_error:
            warn(
                f"scope-review {result.status.value}: {result.message}; "
                f"rollback failed ({result.rollback_error}); repository state may be partial."
            )
        else:
            warn(
                f"scope-review {result.status.value}: {result.message}; "
                "no changes were written."
            )
        return exit_code

    success(
        f"reviewed {len(concept_ids)} concept(s) in {slug} and synchronized the concept record and plan."
    )
    return 0


def register(subparsers) -> dict[str, Handler]:
    """Register the mutating ``scope-review`` command."""
    parser = subparsers.add_parser(
        "scope-review",
        help="review and sign off scoped concept decisions, then synchronize them to the plan",
        description=(
            "Review and sign off an explicit concept scope, then synchronize "
            "accepted decisions to the concept record and plan Markdown. "
            f"Exit {SCOPE_REVIEW_CONFLICT_EXIT} means conflict; exit "
            f"{SCOPE_REVIEW_INVALID_STATE_EXIT} means invalid state."
        ),
    )
    parser.add_argument(
        "name",
        help="plan name — slug, filename stem, or filename.md",
    )
    parser.add_argument(
        "--concept",
        action="append",
        required=True,
        metavar="CONCEPT_ID",
        help="concept ID in the exact review scope (repeat for a grouped scope)",
    )
    parser.add_argument(
        "--decision",
        action="append",
        required=True,
        type=_decision,
        metavar="CONCEPT_ID=DECISION",
        help="scoped decision: include, defer, or wont_do (repeat once per concept)",
    )
    return {"scope-review": cmd_scope_review}
