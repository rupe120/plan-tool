"""Tests for the typed one-artifact feedback revision merger."""

from __future__ import annotations

from dataclasses import fields, replace
from typing import cast

import pytest

from plan_tool.roadmap_artifacts import (
    AssumptionRow,
    AttributeDispositionRow,
    BusinessRuleRow,
    ComponentRow,
    ComponentsArtifact,
    ConstraintDisposition,
    ConstraintRow,
    ConstraintsArtifact,
    DecisionRow,
    DecisionStatus,
    DomainArtifact,
    FeedbackReopenRecord,
    EntityRow,
    FeedbackRow,
    FeedbackState,
    FeedbackTarget,
    FeedbackTargetKind,
    FieldRow,
    FieldType,
    HostingRow,
    OrderingEntry,
    PatternRow,
    PlanDisposition,
    PlanRow,
    PlansArtifact,
    RemovalRecord,
    RoadmapArtifact,
    StackRow,
    StoreRow,
    WorkflowRow,
)
from plan_tool.roadmap_revision import (
    AddRowOperation,
    AppendRowProseAmendment,
    DeleteRowProseAmendment,
    EditRowOperation,
    RemoveRowWithRecordOperation,
    ReplaceRowProseAmendment,
    StageRespondFeedbackOperation,
    StageRevisionOperations,
    TEXT_FIELDS_BY_ROW_TYPE,
    FeedbackSelector,
    ReplaceRowPresentationOperation,
    RespondFeedbackOperation,
    RevisionOperations,
    RevisionPreflight,
    TextFieldValue,
    build_stage_revision_context,
)
from plan_tool.roadmap_revision_patch import (
    RevisionMergeError,
    _apply_stage_prose_amendments,
    _artifact_key,
    append_row_prose_fragments,
    merge_feedback_revision,
    merge_stage_revision,
    splice_exact_spans,
)


_TARGET_ID = "target-row"
_FEEDBACK_ID = "selected-feedback"
_RESPONSE = "The requested bounded change is ready for review."


def _feedback(
    feedback_id: str,
    *,
    state: FeedbackState = FeedbackState.OPEN,
    proposed_response: str | None = None,
    feedback_reopen: FeedbackReopenRecord | None = None,
) -> FeedbackRow:
    return FeedbackRow(
        id=feedback_id,
        target=FeedbackTarget(FeedbackTargetKind.ROW, _TARGET_ID),
        request=f"Request {feedback_id}.",
        state=state,
        proposed_response=proposed_response,
        feedback_reopen=feedback_reopen,
    )


def _feedback_reopen_record() -> FeedbackReopenRecord:
    return FeedbackReopenRecord(
        selector={"artifact_key": "domain", "feedback_id": _FEEDBACK_ID},
        reason="operator-confirmed-evidence-unavailable",
        nonce="A" * 43,
        recorded_at="2026-08-27T14:15:16.123456Z",
    )


def _artifact_for_collection(collection: str) -> RoadmapArtifact:
    feedback = (
        _feedback(_FEEDBACK_ID),
        _feedback(
            "other-feedback",
            state=FeedbackState.AWAITING_REVIEW,
            proposed_response="An earlier response remains under review.",
        ),
    )
    review_data = {
        "body": "# Artifact prose\n\nKeep every byte.\n",
        "feedback": feedback,
        "removals": (RemovalRecord("removed-row", "Already removed.", ("old",)),),
    }
    if collection == "entities":
        return DomainArtifact(
            entities=(
                EntityRow(
                    _TARGET_ID,
                    "Original entity",
                    (FieldRow("owner", FieldType.REFERENCE, "owner-row"),),
                ),
                EntityRow("sibling-entity", "Sibling entity", ()),
            ),
            business_rules=(),
            workflows=(),
            decisions=(),
            **review_data,
        )
    if collection == "business_rules":
        return DomainArtifact(
            entities=(),
            business_rules=(
                BusinessRuleRow(_TARGET_ID, "Original rule.", ("owner-row",)),
            ),
            workflows=(),
            decisions=(),
            **review_data,
        )
    if collection == "workflows":
        return DomainArtifact(
            entities=(),
            business_rules=(),
            workflows=(WorkflowRow(_TARGET_ID, "Original workflow", ("owner-row",)),),
            decisions=(),
            **review_data,
        )
    if collection == "decisions":
        return DomainArtifact(
            entities=(),
            business_rules=(),
            workflows=(),
            decisions=(
                DecisionRow(
                    _TARGET_ID,
                    "Keep the choice.",
                    (),
                    "Original rationale.",
                    "owner-row",
                    DecisionStatus.SETTLED,
                ),
            ),
            **review_data,
        )
    if collection == "dispositions":
        return ConstraintsArtifact(
            dispositions=(
                AttributeDispositionRow(
                    _TARGET_ID,
                    "performance",
                    ConstraintDisposition.PRIORITIZED,
                ),
            ),
            constraints=(),
            decisions=(),
            **review_data,
        )
    if collection == "constraints":
        return ConstraintsArtifact(
            dispositions=(),
            constraints=(
                ConstraintRow(
                    _TARGET_ID,
                    "Original constraint.",
                    "performance",
                    ("owner-row",),
                ),
            ),
            decisions=(),
            **review_data,
        )
    if collection in {"system_patterns", "component_patterns"}:
        return ComponentsArtifact(
            system_patterns=(
                PatternRow(_TARGET_ID, "Original pattern", "Original statement."),
            )
            if collection == "system_patterns"
            else (),
            component_patterns=(
                PatternRow(_TARGET_ID, "Original pattern", "Original statement."),
            )
            if collection == "component_patterns"
            else (),
            components=(),
            decisions=(),
            **review_data,
        )
    if collection == "components":
        return ComponentsArtifact(
            system_patterns=(),
            component_patterns=(),
            components=(
                ComponentRow(
                    _TARGET_ID,
                    "Original component",
                    ("owner-row",),
                    ("pattern-row",),
                    ("constraint-row",),
                ),
            ),
            decisions=(),
            **review_data,
        )
    if collection == "plans":
        return PlansArtifact(
            plans=(
                PlanRow(
                    _TARGET_ID,
                    "Original plan",
                    PlanDisposition.KEEP,
                    ("component-row",),
                    "seeds/target-row.md",
                    "Original sizing rationale.",
                ),
            ),
            ordering=(),
            assumptions=(),
            decisions=(),
            **review_data,
        )
    if collection == "assumptions":
        return PlansArtifact(
            plans=(),
            ordering=(),
            assumptions=(
                AssumptionRow(_TARGET_ID, "Original assumption.", ("plan-row",)),
            ),
            decisions=(),
            **review_data,
        )
    raise AssertionError(f"unsupported test collection: {collection}")


def _source(collection: str) -> tuple[RoadmapArtifact, RevisionPreflight]:
    artifact = _artifact_for_collection(collection)
    target_row = getattr(artifact, collection)[0]
    allowed_text_fields = tuple(
        TextFieldValue(field, getattr(target_row, field))
        for field in TEXT_FIELDS_BY_ROW_TYPE[collection]
    )
    return artifact, RevisionPreflight(
        selector=FeedbackSelector("selected-artifact", _FEEDBACK_ID),
        feedback_request=artifact.feedback[0].request,
        feedback_state=FeedbackState.OPEN,
        target_row_id=_TARGET_ID,
        target_collection=collection,
        allowed_text_fields=allowed_text_fields,
        relation_data=(),
    )


def _operations(
    *,
    replacement: ReplaceRowPresentationOperation | None = None,
    response: RespondFeedbackOperation | None = None,
) -> RevisionOperations:
    return RevisionOperations(
        replacement=replacement,
        response=response
        or RespondFeedbackOperation(
            op="respond-feedback",
            feedback_id=_FEEDBACK_ID,
            proposed_response=_RESPONSE,
        ),
    )


def _replacement(field: str, **overrides: str) -> ReplaceRowPresentationOperation:
    values = {
        "op": "replace-row-presentation",
        "row_id": _TARGET_ID,
        "field": field,
        "value": "Revised presentation",
    } | overrides
    return ReplaceRowPresentationOperation(**values)


def test_merge_replacement_and_response_updates_the_selected_pair() -> None:
    artifact, preflight = _source("entities")

    candidate = merge_feedback_revision(
        artifact,
        preflight,
        _operations(replacement=_replacement("name")),
    )

    assert candidate.entities[0].name == "Revised presentation"
    assert candidate.entities[0].fields == artifact.entities[0].fields
    assert candidate.feedback[0] == FeedbackRow(
        id=_FEEDBACK_ID,
        target=artifact.feedback[0].target,
        request=artifact.feedback[0].request,
        state=FeedbackState.AWAITING_REVIEW,
        proposed_response=_RESPONSE,
    )


def test_merge_response_without_replacement_keeps_the_target_row_unchanged() -> None:
    artifact, preflight = _source("entities")

    candidate = merge_feedback_revision(artifact, preflight, _operations())

    assert candidate.entities is artifact.entities
    assert candidate.entities[0] is artifact.entities[0]
    assert candidate.feedback[0].state is FeedbackState.AWAITING_REVIEW


def test_merge_response_clears_the_prior_current_artifact_reopen_record() -> None:
    artifact, preflight = _source("entities")
    artifact = replace(
        artifact,
        feedback=(
            replace(artifact.feedback[0], feedback_reopen=_feedback_reopen_record()),
            *artifact.feedback[1:],
        ),
    )

    candidate = merge_feedback_revision(artifact, preflight, _operations())

    assert candidate.feedback[0].state is FeedbackState.AWAITING_REVIEW
    assert candidate.feedback[0].proposed_response == _RESPONSE
    assert candidate.feedback[0].feedback_reopen is None


@pytest.mark.parametrize(
    ("collection", "field"),
    tuple(
        (collection, field)
        for collection, fields_for_collection in TEXT_FIELDS_BY_ROW_TYPE.items()
        for field in fields_for_collection
    ),
)
def test_merge_accepts_every_allowed_target_field(
    collection: str, field: str
) -> None:
    artifact, preflight = _source(collection)

    candidate = merge_feedback_revision(
        artifact,
        preflight,
        _operations(replacement=_replacement(field)),
    )

    source_row = getattr(artifact, collection)[0]
    candidate_row = getattr(candidate, collection)[0]
    assert getattr(candidate_row, field) == "Revised presentation"
    for row_field in fields(source_row):
        if row_field.name != field:
            assert getattr(candidate_row, row_field.name) == getattr(
                source_row, row_field.name
            )


def test_merge_rejects_a_row_id_other_than_the_selected_target() -> None:
    artifact, preflight = _source("entities")

    with pytest.raises(RevisionMergeError, match="other-row"):
        merge_feedback_revision(
            artifact,
            preflight,
            _operations(replacement=_replacement("name", row_id="other-row")),
        )


def test_merge_rejects_a_feedback_id_other_than_the_selected_feedback() -> None:
    artifact, preflight = _source("entities")

    with pytest.raises(RevisionMergeError, match="other-feedback"):
        merge_feedback_revision(
            artifact,
            preflight,
            _operations(
                response=RespondFeedbackOperation(
                    op="respond-feedback",
                    feedback_id="other-feedback",
                    proposed_response=_RESPONSE,
                )
            ),
        )


@pytest.mark.parametrize(
    ("collection", "field"),
    (("entities", "fields"), ("dispositions", "attribute")),
)
def test_merge_rejects_a_disallowed_or_non_targetable_field(
    collection: str, field: str
) -> None:
    artifact, preflight = _source(collection)

    with pytest.raises(RevisionMergeError, match=_TARGET_ID):
        merge_feedback_revision(
            artifact,
            preflight,
            _operations(replacement=_replacement(field)),
        )


def test_merge_requires_the_selected_feedback_response() -> None:
    artifact, preflight = _source("entities")
    operations = RevisionOperations(
        replacement=_replacement("name"),
        response=None,  # type: ignore[arg-type]
    )

    with pytest.raises(RevisionMergeError, match=_FEEDBACK_ID):
        merge_feedback_revision(artifact, preflight, operations)


def test_merge_preserves_unselected_feedback_and_artifact_prose() -> None:
    artifact, preflight = _source("components")

    candidate = merge_feedback_revision(
        artifact,
        preflight,
        _operations(replacement=_replacement("name")),
    )

    assert candidate.feedback[1] is artifact.feedback[1]
    assert candidate.removals is artifact.removals
    assert candidate.body == artifact.body
    assert candidate.components[0].entity_ids == artifact.components[0].entity_ids
    assert candidate.components[0].pattern_ids == artifact.components[0].pattern_ids
    assert candidate.components[0].constraint_ids == artifact.components[0].constraint_ids


def test_merge_does_not_mutate_the_loaded_artifact() -> None:
    artifact, preflight = _source("entities")
    source_name = artifact.entities[0].name
    source_feedback = artifact.feedback[0]

    candidate = merge_feedback_revision(
        artifact,
        preflight,
        _operations(replacement=_replacement("name")),
    )

    assert candidate is not artifact
    assert artifact.entities[0].name == source_name
    assert artifact.feedback[0] is source_feedback
    assert artifact.feedback[0].state is FeedbackState.OPEN


# --------------------------------------------------------------------------
# Stage-envelope merger
# --------------------------------------------------------------------------


def _stage_feedback(
    feedback_id: str,
    target: FeedbackTarget,
    request: str,
    *,
    state: FeedbackState = FeedbackState.OPEN,
) -> FeedbackRow:
    return FeedbackRow(feedback_id, target, request, state)


def _stage_domain_artifact() -> DomainArtifact:
    return DomainArtifact(
        entities=(
            EntityRow(
                "target-row",
                "Original target",
                (FieldRow("owner", FieldType.REFERENCE, "sibling-row"),),
            ),
            EntityRow("sibling-row", "Unselected sibling", ()),
        ),
        business_rules=(),
        workflows=(),
        decisions=(),
        body=(
            "# Domain\n\n"
            "target-row is the selected domain item.\n\n"
            "sibling-row is the unselected domain item.\n"
        ),
        feedback=(
            _stage_feedback(
                "edit-feedback",
                FeedbackTarget(FeedbackTargetKind.ROW, "target-row"),
                "Clarify the target row.",
            ),
            _stage_feedback(
                "add-feedback",
                FeedbackTarget(FeedbackTargetKind.ARTIFACT),
                "Add the missing companion row.",
            ),
            _stage_feedback(
                "deferred-feedback",
                FeedbackTarget(FeedbackTargetKind.ROW, "sibling-row"),
                "Keep this reviewer item untouched.",
                state=FeedbackState.DEFERRED,
            ),
        ),
        removals=(RemovalRecord("carried-removal", "Already considered.", ("old",)),),
    )


def _stage_domain_operations(
    artifact: DomainArtifact,
) -> tuple[object, StageRevisionOperations]:
    context = build_stage_revision_context(artifact)
    span = next(item for item in context.prose_spans if item.row_id == "target-row")
    replacement = replace(artifact.entities[0], name="Clarified target")
    addition = EntityRow("added-row", "Added row", ())
    operations = StageRevisionOperations(
        material_operations=(
            EditRowOperation(
                "edit-feedback",
                "entities",
                "target-row",
                replacement,
                ReplaceRowProseAmendment(
                    "target-row",
                    span.span_id,
                    "target-row now describes the clarified item.",
                ),
            ),
            AddRowOperation(
                "add-feedback",
                "entities",
                addition,
                AppendRowProseAmendment(
                    "added-row", "\n\nadded-row describes the new companion.\n"
                ),
                None,
            ),
        ),
        responses=(
            StageRespondFeedbackOperation(
                "edit-feedback", "The target wording is clarified."
            ),
            StageRespondFeedbackOperation(
                "add-feedback", "The companion row is added."),
        ),
    )
    return context, operations


def test_stage_merge_applies_material_operations_before_feedback_responses() -> None:
    artifact = _stage_domain_artifact()
    context, operations = _stage_domain_operations(artifact)

    candidate = merge_stage_revision(artifact, context, operations)

    assert candidate.entities[0].name == "Clarified target"
    assert candidate.entities[1] is artifact.entities[1]
    assert candidate.entities[2].id == "added-row"
    assert candidate.feedback[0].state is FeedbackState.AWAITING_REVIEW
    assert candidate.feedback[1].state is FeedbackState.AWAITING_REVIEW
    assert candidate.feedback[2] is artifact.feedback[2]


def test_stage_merge_response_clears_the_prior_current_artifact_reopen_record() -> None:
    artifact = _stage_domain_artifact()
    artifact = replace(
        artifact,
        feedback=(
            replace(artifact.feedback[0], feedback_reopen=_feedback_reopen_record()),
            *artifact.feedback[1:],
        ),
    )
    context, operations = _stage_domain_operations(artifact)

    candidate = merge_stage_revision(artifact, context, operations)

    assert candidate.feedback[0].state is FeedbackState.AWAITING_REVIEW
    assert candidate.feedback[0].feedback_reopen is None


@pytest.mark.parametrize(
    ("body", "expected"),
    (
        ("", "row-added is documented."),
        ("Existing prose", "Existing prose\n\nrow-added is documented."),
        ("Existing prose\n", "Existing prose\n\nrow-added is documented."),
        ("Existing prose\n\n", "Existing prose\n\nrow-added is documented."),
    ),
)
def test_append_row_prose_fragments_preserves_existing_spacing_rules(
    body: str, expected: str
) -> None:
    assert append_row_prose_fragments(body, ("row-added is documented.",)) == expected


def test_append_row_prose_fragments_keeps_fragment_order_and_text() -> None:
    fragments = ("row-one keeps its leading space.", "\nrow-two keeps its leading newline.\n")

    assert append_row_prose_fragments("", fragments) == (
        "row-one keeps its leading space.\n\n\nrow-two keeps its leading newline.\n"
    )


def test_stage_merge_separates_each_appended_row_prose_block() -> None:
    artifact = DomainArtifact(
        entities=(),
        business_rules=(),
        workflows=(),
        decisions=(),
        body="# Domain\n\nThe checkout flow remains active.\n",
        feedback=(
            _stage_feedback(
                "add-one",
                FeedbackTarget(FeedbackTargetKind.ARTIFACT),
                "Add the refunds entity.",
            ),
            _stage_feedback(
                "add-two",
                FeedbackTarget(FeedbackTargetKind.ARTIFACT),
                "Add the returns entity.",
            ),
        ),
    )
    context = build_stage_revision_context(artifact)
    operations = StageRevisionOperations(
        material_operations=(
            AddRowOperation(
                "add-one",
                "entities",
                EntityRow("row-one", "Refunds", ()),
                AppendRowProseAmendment("row-one", "row-one handles refunds.\n"),
                None,
            ),
            AddRowOperation(
                "add-two",
                "entities",
                EntityRow("row-two", "Returns", ()),
                AppendRowProseAmendment("row-two", "row-two handles returns.\n"),
                None,
            ),
        ),
        responses=(
            StageRespondFeedbackOperation("add-one", "Refunds are proposed for review."),
            StageRespondFeedbackOperation("add-two", "Returns are proposed for review."),
        ),
    )

    candidate = merge_stage_revision(artifact, context, operations)
    next_feedback = tuple(
        replace(
            row,
            state=FeedbackState.OPEN,
            proposed_response=None,
            target=FeedbackTarget(FeedbackTargetKind.ROW, row_id),
        )
        for row, row_id in zip(candidate.feedback, ("row-one", "row-two"), strict=True)
    )

    next_context = build_stage_revision_context(replace(candidate, feedback=next_feedback))

    assert {span.row_id for span in next_context.prose_spans} == {"row-one", "row-two"}
    assert "active.\n\nrow-one" in candidate.body
    assert "refunds.\n\nrow-two" in candidate.body


@pytest.mark.parametrize(
    "artifact",
    (
        ConstraintsArtifact(
            dispositions=(),
            constraints=(),
            decisions=(),
            hosting=(HostingRow("hosting-primary", "region", "us-east-1"),),
            body="# Constraints\n",
            feedback=(
                _stage_feedback(
                    "hosting-feedback",
                    FeedbackTarget(FeedbackTargetKind.ROW, "hosting-primary"),
                    "Confirm the chosen hosting region.",
                ),
            ),
        ),
        ComponentsArtifact(
            system_patterns=(),
            component_patterns=(),
            components=(),
            decisions=(),
            stores=(StoreRow("store-primary", "relational", "shared"),),
            body="# Components\n",
            feedback=(
                _stage_feedback(
                    "store-feedback",
                    FeedbackTarget(FeedbackTargetKind.ROW, "store-primary"),
                    "Confirm the shared store choice.",
                ),
            ),
        ),
    ),
)
def test_stage_merge_accepts_response_only_for_identity_only_feedback_targets(
    artifact: ConstraintsArtifact | ComponentsArtifact,
) -> None:
    context = build_stage_revision_context(artifact)
    feedback = artifact.feedback[0]
    operations = StageRevisionOperations(
        material_operations=(),
        responses=(
            StageRespondFeedbackOperation(
                feedback.id,
                "The existing choice is retained for review.",
            ),
        ),
    )

    candidate = merge_stage_revision(artifact, context, operations)

    assert candidate.feedback[0].state is FeedbackState.AWAITING_REVIEW
    assert candidate.feedback[0].proposed_response == "The existing choice is retained for review."


def _stack_constraints(stack: tuple[StackRow, ...] | None) -> ConstraintsArtifact:
    return ConstraintsArtifact(
        dispositions=(),
        constraints=(),
        decisions=(),
        hosting=(HostingRow("hosting-primary", "region", "us-east-1"),),
        stack=stack,
        body="# Constraints\n\nUntouched body.\n",
        feedback=(
            _stage_feedback(
                "stack-feedback",
                FeedbackTarget(FeedbackTargetKind.ROW, "stack-platform"),
                "Settle the platform.",
            ),
        ),
    )


_STACK_ROWS = (
    StackRow("stack-platform", "platform", choice="managed"),
    StackRow("stack-engine", "store-engine", open=True),
)


def _stack_edit(artifact: ConstraintsArtifact, row: StackRow) -> StageRevisionOperations:
    return StageRevisionOperations(
        material_operations=(
            EditRowOperation("stack-feedback", "stack", "stack-platform", row, None),
        ),
        responses=(StageRespondFeedbackOperation("stack-feedback", "The platform is settled."),),
    )


def test_stack_edit_that_changes_concern_is_a_merge_error() -> None:
    """The fixed ``concern`` field is enforced by the patch layer, not only by
    the parser, so widening the fixed-field check to skip ``stack`` fails here."""
    artifact = _stack_constraints(_STACK_ROWS)
    context = build_stage_revision_context(artifact)
    moved = replace(_STACK_ROWS[0], concern="language-runtime")

    with pytest.raises(RevisionMergeError, match="concern"):
        merge_stage_revision(artifact, context, _stack_edit(artifact, moved))


def test_stack_edit_preserves_every_other_row_and_the_body() -> None:
    artifact = _stack_constraints(_STACK_ROWS)
    context = build_stage_revision_context(artifact)
    edited = replace(_STACK_ROWS[0], choice=None, open=True)

    candidate = merge_stage_revision(artifact, context, _stack_edit(artifact, edited))

    assert candidate.stack == (edited, _STACK_ROWS[1])
    assert candidate.stack[1] is artifact.stack[1]
    assert candidate.hosting is artifact.hosting
    assert candidate.body == artifact.body


def test_absent_stack_stays_absent_after_an_unrelated_edit() -> None:
    """``None`` means "not recorded"; a merge must never turn it into ``()``."""
    artifact = replace(
        _stack_constraints(None),
        feedback=(
            _stage_feedback(
                "hosting-feedback",
                FeedbackTarget(FeedbackTargetKind.ROW, "hosting-primary"),
                "Confirm the chosen hosting region.",
            ),
        ),
    )
    context = build_stage_revision_context(artifact)
    operations = StageRevisionOperations(
        material_operations=(),
        responses=(StageRespondFeedbackOperation("hosting-feedback", "Retained."),),
    )

    candidate = merge_stage_revision(artifact, context, operations)

    assert candidate.stack is None


def test_stage_merge_returns_no_candidate_when_any_context_bound_operation_fails() -> None:
    artifact = _stage_domain_artifact()
    context, operations = _stage_domain_operations(artifact)
    invalid = replace(
        operations,
        material_operations=(
            *operations.material_operations[:-1],
            replace(operations.material_operations[-1], feedback_id="unknown-feedback"),
        ),
    )

    with pytest.raises(RevisionMergeError, match="unknown-feedback"):
        merge_stage_revision(artifact, context, invalid)

    assert artifact == _stage_domain_artifact()


def test_stage_merge_preserves_unselected_rows_feedback_removals_and_body_bytes() -> None:
    artifact = _stage_domain_artifact()
    context, operations = _stage_domain_operations(artifact)

    candidate = merge_stage_revision(artifact, context, operations)

    assert candidate.entities[1] is artifact.entities[1]
    assert candidate.feedback[2] is artifact.feedback[2]
    assert candidate.removals is artifact.removals
    assert "sibling-row is the unselected domain item.\n" in candidate.body
    assert candidate.body.startswith("# Domain\n\n")


@pytest.mark.parametrize("failure", ("stale", "cross-target", "identity-only"))
def test_stage_merge_applies_only_issued_row_owned_prose_spans(failure: str) -> None:
    artifact = _stage_domain_artifact()
    context, operations = _stage_domain_operations(artifact)

    if failure == "stale":
        span = context.prose_spans[0]
        context = replace(context, prose_spans=(replace(span, text="stale source"),))
    elif failure == "cross-target":
        edit = operations.material_operations[0]
        assert isinstance(edit, EditRowOperation)
        operations = replace(
            operations,
            material_operations=(
                replace(
                    edit,
                    prose_amendment=ReplaceRowProseAmendment(
                        "sibling-row", edit.prose_amendment.span_id, "Wrong target."
                    ),
                ),
                operations.material_operations[1],
            ),
        )
    else:
        store = StoreRow("store-row", "relational", "shared")
        store_artifact = ComponentsArtifact(
            system_patterns=(),
            component_patterns=(),
            components=(),
            decisions=(),
            stores=(store,),
            body="# Components\n",
            feedback=(
                _stage_feedback(
                    "store-feedback",
                    FeedbackTarget(FeedbackTargetKind.ROW, store.id),
                    "Remove the obsolete store.",
                ),
            ),
        )
        store_context = build_stage_revision_context(store_artifact)
        store_operations = StageRevisionOperations(
            material_operations=(
                RemoveRowWithRecordOperation(
                    "store-feedback",
                    "stores",
                    store.id,
                    RemovalRecord(store.id, "The store no longer serves a component.", ("store-feedback",)),
                    DeleteRowProseAmendment(store.id, "invented-span"),
                ),
            ),
            responses=(
                StageRespondFeedbackOperation("store-feedback", "The obsolete store is removed."),
            ),
        )
        with pytest.raises(RevisionMergeError, match="identity-only"):
            merge_stage_revision(store_artifact, store_context, store_operations)
        return

    with pytest.raises(RevisionMergeError):
        merge_stage_revision(artifact, context, operations)


def test_splice_exact_spans_replaces_and_deletes_by_offset() -> None:
    assert splice_exact_spans("abcdefghij", [(0, 2, "XY"), (4, 7, "")]) == "XYcdhij"


def test_splice_exact_spans_applies_edits_independent_of_input_order() -> None:
    edits = [(0, 2, "XYZ"), (4, 6, ""), (8, 9, "Q")]

    assert splice_exact_spans("abcdefghij", edits) == splice_exact_spans(
        "abcdefghij", list(reversed(edits))
    )
    assert splice_exact_spans("abcdefghij", edits) == "XYZcdghQj"


def test_splice_exact_spans_allows_adjacent_ranges() -> None:
    # Deliberate boundary: only start < prior_end is an overlap; touching ranges are fine.
    assert splice_exact_spans("abcdef", [(0, 3, "X"), (3, 6, "Y")]) == "XY"


def test_splice_exact_spans_refuses_overlap_with_stage_message() -> None:
    with pytest.raises(RevisionMergeError) as raised:
        splice_exact_spans("abcdef", [(0, 4, "X"), (3, 6, "Y")])

    assert str(raised.value) == "stage prose amendments overlap"


def test_splice_exact_spans_refuses_overlap_before_changing_anything() -> None:
    body = "abcdef"
    result: list[str] = []

    with pytest.raises(RevisionMergeError):
        result.append(splice_exact_spans(body, [(0, 4, "X"), (3, 6, "Y")]))

    assert result == []
    assert body == "abcdef"


def test_splice_exact_spans_with_no_edits_returns_body_unchanged() -> None:
    assert splice_exact_spans("abcdef", []) == "abcdef"


def test_stage_amendments_on_overlapping_spans_still_refuse_with_stage_message() -> None:
    # Source verification normally rejects overlapping issued spans first, so drive the
    # amendment step directly: the splice helper's refusal is the backstop it must keep.
    artifact = _stage_domain_artifact()
    context, operations = _stage_domain_operations(artifact)
    edit = operations.material_operations[0]
    assert isinstance(edit, EditRowOperation)
    first = next(item for item in context.prose_spans if item.row_id == "target-row")
    second = replace(first, row_id="sibling-row", span_id="overlap-span", start=first.start + 1)
    overlapping = StageRevisionOperations(
        material_operations=(
            edit,
            replace(
                edit,
                row_id="sibling-row",
                prose_amendment=ReplaceRowProseAmendment("sibling-row", "overlap-span", "Other."),
            ),
        ),
        responses=(),
    )

    with pytest.raises(RevisionMergeError) as raised:
        _apply_stage_prose_amendments(
            artifact,
            context,
            overlapping,
            ({}, {first.span_id: first, "overlap-span": second}),
        )

    assert str(raised.value) == "stage prose amendments overlap"


def _plan_row(plan_id: str, *, component_ids: tuple[str, ...] = ()) -> PlanRow:
    return PlanRow(
        plan_id,
        f"Plan {plan_id}",
        PlanDisposition.KEEP,
        component_ids,
        f"seeds/{plan_id}.md",
        "One bounded plan.",
    )


def test_stage_merge_adds_and_removes_only_the_matching_plan_ordering_entry() -> None:
    removed = _plan_row("plan-removed")
    retained = _plan_row("plan-retained")
    artifact = PlansArtifact(
        plans=(removed, retained),
        ordering=(
            OrderingEntry("plan-removed"),
            OrderingEntry("plan-retained"),
        ),
        assumptions=(),
        decisions=(),
        body=(
            "# Plans\n\nplan-removed is retired.\n\n"
            "plan-retained remains.\n"
        ),
        feedback=(
            _stage_feedback(
                "remove-feedback",
                FeedbackTarget(FeedbackTargetKind.ROW, removed.id),
                "Remove the superseded plan.",
            ),
            _stage_feedback(
                "add-feedback",
                FeedbackTarget(FeedbackTargetKind.ARTIFACT),
                "Add the replacement plan.",
            ),
        ),
    )
    context = build_stage_revision_context(artifact)
    span = next(item for item in context.prose_spans if item.row_id == removed.id)
    added = _plan_row("plan-added")
    operations = StageRevisionOperations(
        material_operations=(
            RemoveRowWithRecordOperation(
                "remove-feedback",
                "plans",
                removed.id,
                RemovalRecord(removed.id, "The reviewer retired this plan.", ("remove-feedback",)),
                DeleteRowProseAmendment(removed.id, span.span_id),
            ),
            AddRowOperation(
                "add-feedback",
                "plans",
                added,
                AppendRowProseAmendment(added.id, "\n\nplan-added replaces the retired plan.\n"),
                OrderingEntry(added.id, depends_on=(retained.id,)),
            ),
        ),
        responses=(
            StageRespondFeedbackOperation("remove-feedback", "The superseded plan is removed."),
            StageRespondFeedbackOperation("add-feedback", "The replacement plan is added."),
        ),
    )

    candidate = merge_stage_revision(artifact, context, operations)

    assert [row.id for row in candidate.plans] == [retained.id, added.id]
    assert candidate.ordering == (OrderingEntry(retained.id), OrderingEntry(added.id, depends_on=(retained.id,)))
    assert candidate.removals[-1] == operations.material_operations[0].removal_record


def test_stage_merge_reports_a_missing_plan_ordering_companion_as_a_revision_error() -> None:
    removed = _plan_row("plan-removed")
    artifact = PlansArtifact(
        plans=(removed,),
        ordering=(),
        assumptions=(),
        decisions=(),
        body="# Plans\n\nplan-removed is retired.\n",
        feedback=(
            _stage_feedback(
                "remove-feedback",
                FeedbackTarget(FeedbackTargetKind.ROW, removed.id),
                "Remove the superseded plan.",
            ),
        ),
    )
    context = build_stage_revision_context(artifact)
    span = context.prose_spans[0]
    operations = StageRevisionOperations(
        material_operations=(
            RemoveRowWithRecordOperation(
                "remove-feedback",
                "plans",
                removed.id,
                RemovalRecord(removed.id, "The reviewer retired this plan.", ("remove-feedback",)),
                DeleteRowProseAmendment(removed.id, span.span_id),
            ),
        ),
        responses=(StageRespondFeedbackOperation("remove-feedback", "The plan is removed."),),
    )

    with pytest.raises(RevisionMergeError, match="exactly one ordering companion"):
        merge_stage_revision(artifact, context, operations)


def test_stage_merge_rejects_removal_with_surviving_references() -> None:
    removed = _plan_row("plan-removed")
    dependent = _plan_row("plan-dependent")
    artifact = PlansArtifact(
        plans=(removed, dependent),
        ordering=(OrderingEntry(removed.id), OrderingEntry(dependent.id, depends_on=(removed.id,))),
        assumptions=(AssumptionRow("assumption-1", "Depends on the retired plan.", (removed.id,)),),
        decisions=(DecisionRow("decision-1", "Keep", (), "The plan remains anchored.", removed.id, DecisionStatus.PENDING),),
        body="# Plans\n\nplan-removed is currently present.\n",
        feedback=(
            _stage_feedback(
                "remove-feedback",
                FeedbackTarget(FeedbackTargetKind.ROW, removed.id),
                "Remove the plan.",
            ),
        ),
    )
    context = build_stage_revision_context(artifact)
    span = context.prose_spans[0]
    operations = StageRevisionOperations(
        material_operations=(
            RemoveRowWithRecordOperation(
                "remove-feedback",
                "plans",
                removed.id,
                RemovalRecord(removed.id, "The reviewer retired this plan.", ("remove-feedback",)),
                DeleteRowProseAmendment(removed.id, span.span_id),
            ),
        ),
        responses=(StageRespondFeedbackOperation("remove-feedback", "The plan is removed."),),
    )

    with pytest.raises(RevisionMergeError, match="relation owner"):
        merge_stage_revision(artifact, context, operations)


def test_stage_merge_rejects_a_new_ordering_relation_to_a_removed_plan() -> None:
    removed = _plan_row("plan-removed")
    retained = _plan_row("plan-retained")
    artifact = PlansArtifact(
        plans=(removed, retained),
        ordering=(OrderingEntry(removed.id), OrderingEntry(retained.id)),
        assumptions=(),
        decisions=(),
        body="# Plans\n\nplan-removed is retired.\n",
        feedback=(
            _stage_feedback(
                "remove-feedback",
                FeedbackTarget(FeedbackTargetKind.ROW, removed.id),
                "Remove the superseded plan.",
            ),
            _stage_feedback(
                "add-feedback",
                FeedbackTarget(FeedbackTargetKind.ARTIFACT),
                "Add the replacement plan.",
            ),
        ),
    )
    context = build_stage_revision_context(artifact)
    span = context.prose_spans[0]
    added = _plan_row("plan-added")
    operations = StageRevisionOperations(
        material_operations=(
            RemoveRowWithRecordOperation(
                "remove-feedback",
                "plans",
                removed.id,
                RemovalRecord(removed.id, "The reviewer retired this plan.", ("remove-feedback",)),
                DeleteRowProseAmendment(removed.id, span.span_id),
            ),
            AddRowOperation(
                "add-feedback",
                "plans",
                added,
                AppendRowProseAmendment(added.id, "plan-added replaces the retired plan.\n"),
                OrderingEntry(added.id, depends_on=(removed.id,)),
            ),
        ),
        responses=(
            StageRespondFeedbackOperation("remove-feedback", "The retired plan is removed."),
            StageRespondFeedbackOperation("add-feedback", "The replacement plan is added."),
        ),
    )

    with pytest.raises(RevisionMergeError, match="plan-added"):
        merge_stage_revision(artifact, context, operations)


def test_stage_merge_rejects_an_unknown_artifact_type() -> None:
    with pytest.raises(RevisionMergeError, match="unknown roadmap artifact type"):
        _artifact_key(cast(RoadmapArtifact, object()))


def test_stage_merge_rejects_store_removal_when_a_component_still_names_it() -> None:
    store = StoreRow("store-retired", "relational", "pool")
    component = ComponentRow(
        "component-1", "Current component", (), (), store_ids=(store.id,)
    )
    artifact = ComponentsArtifact(
        system_patterns=(),
        component_patterns=(),
        components=(component,),
        decisions=(),
        stores=(store,),
        body="# Components\n",
        feedback=(
            _stage_feedback(
                "remove-feedback",
                FeedbackTarget(FeedbackTargetKind.ROW, store.id),
                "Remove the retired store.",
            ),
        ),
    )
    context = build_stage_revision_context(artifact)
    operations = StageRevisionOperations(
        material_operations=(
            RemoveRowWithRecordOperation(
                "remove-feedback",
                "stores",
                store.id,
                RemovalRecord(store.id, "The store is retired.", ("remove-feedback",)),
                None,
            ),
        ),
        responses=(StageRespondFeedbackOperation("remove-feedback", "The store is removed."),),
    )

    with pytest.raises(RevisionMergeError, match="component-1"):
        merge_stage_revision(artifact, context, operations)


def test_stage_merge_preserves_every_existing_relation_field() -> None:
    artifact = _stage_domain_artifact()
    context, operations = _stage_domain_operations(artifact)
    edit = operations.material_operations[0]
    assert isinstance(edit, EditRowOperation)
    retargeted = replace(
        edit,
        row=EntityRow(
            "target-row",
            "Clarified target",
            (FieldRow("owner", FieldType.REFERENCE, "added-row"),),
        ),
    )
    operations = replace(
        operations,
        material_operations=(retargeted, operations.material_operations[1]),
    )

    with pytest.raises(RevisionMergeError, match="declared relation"):
        merge_stage_revision(artifact, context, operations)


def test_stage_merge_retains_current_format_removal_evidence() -> None:
    artifact = _stage_domain_artifact()
    target = artifact.entities[0]
    artifact = replace(
        artifact,
        feedback=(
            _stage_feedback(
                "remove-feedback",
                FeedbackTarget(FeedbackTargetKind.ROW, target.id),
                "Remove the obsolete row.",
            ),
        ),
    )
    context = build_stage_revision_context(artifact)
    span = context.prose_spans[0]
    record = RemovalRecord(target.id, "The reviewer retired the obsolete row.", ("remove-feedback",))
    operations = StageRevisionOperations(
        material_operations=(
            RemoveRowWithRecordOperation(
                "remove-feedback",
                "entities",
                target.id,
                record,
                DeleteRowProseAmendment(target.id, span.span_id),
            ),
        ),
        responses=(StageRespondFeedbackOperation("remove-feedback", "The obsolete row is removed."),),
    )

    candidate = merge_stage_revision(artifact, context, operations)

    assert candidate.removals == (*artifact.removals, record)


def test_stage_merge_answers_feedback_targeting_a_carried_removal_without_material_change() -> None:
    artifact = DomainArtifact(
        entities=(),
        business_rules=(),
        workflows=(),
        decisions=(),
        body="# Domain\n",
        feedback=(
            _stage_feedback(
                "removal-feedback",
                FeedbackTarget(FeedbackTargetKind.ROW, "removed-row"),
                "Explain the earlier removal.",
            ),
        ),
        removals=(RemovalRecord("removed-row", "The row was retired.", ("old-feedback",)),),
    )
    context = build_stage_revision_context(artifact)
    operations = StageRevisionOperations(
        material_operations=(),
        responses=(
            StageRespondFeedbackOperation(
                "removal-feedback", "The record now explains the earlier removal."
            ),
        ),
    )

    candidate = merge_stage_revision(artifact, context, operations)

    assert candidate.feedback[0].state is FeedbackState.AWAITING_REVIEW
    assert candidate.removals is artifact.removals
