"""Pure typed merger for one bounded feedback revision."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace

from plan_tool.roadmap_artifacts import (
    AssumptionRow,
    BusinessRuleRow,
    ComponentRow,
    ComponentsArtifact,
    ConstraintRow,
    DecisionRow,
    DomainArtifact,
    FeedbackRow,
    FeedbackState,
    FeedbackTargetKind,
    HostingRow,
    PlanRow,
    PlansArtifact,
    RoadmapArtifact,
    StageRow,
    WorkflowRow,
    append_plan_ordering_entry,
    append_removal_record,
    append_stage_row,
    remove_plan_ordering_entry,
    remove_stage_row,
    replace_design_row,
    replace_stage_row,
    stage_collection_accepts_add,
    stage_row_edit_preserves_fixed_fields,
    stage_row_collections,
)
from plan_tool.roadmap_revision import (
    AddRowOperation,
    AppendRowProseAmendment,
    DeleteRowProseAmendment,
    EditRowOperation,
    RemoveRowWithRecordOperation,
    ReplaceRowPresentationOperation,
    ReplaceRowProseAmendment,
    RespondFeedbackOperation,
    RevisionOperations,
    RevisionPreflight,
    StageFeedbackAuthority,
    StageLiveRow,
    StageMaterialOperation,
    StageProseSpan,
    StageRespondFeedbackOperation,
    StageRevisionContext,
    StageRevisionOperations,
    contains_whole_row_id,
    stage_row_operation_policy,
    stage_prose_span_id,
)
from plan_tool.roadmap_relations import (
    ARTIFACT_KEY_BY_TYPE,
    declared_relation_ids_for_row,
    extract_declared_relations,
    same_declared_row_relations,
)


class RevisionMergeError(ValueError):
    """A parsed revision operation cannot safely merge into its selected artifact."""


class StageRevisionSourceError(RevisionMergeError):
    """The source no longer matches the stage context the reply bound."""


def merge_stage_revision(
    artifact: RoadmapArtifact,
    context: StageRevisionContext,
    operations: StageRevisionOperations,
) -> RoadmapArtifact:
    """Build one fully-bound stage candidate without reading, writing, or gating."""
    if not isinstance(context, StageRevisionContext):
        raise RevisionMergeError("stage revision merge requires bounded stage context")
    if not isinstance(operations, StageRevisionOperations):
        raise RevisionMergeError("stage revision merge requires parsed stage operations")

    source = _verify_stage_source(artifact, context)
    removal_ids = _verify_stage_operations(artifact, context, operations, source)

    candidate = artifact
    for operation in operations.material_operations:
        candidate = _apply_stage_material_operation(candidate, operation)
    _reject_surviving_removal_references(context, candidate, removal_ids)

    body = _apply_stage_prose_amendments(artifact, context, operations, source)
    if body != artifact.body:
        candidate = replace(candidate, body=body)
    return _apply_stage_responses(candidate, context, operations)


def merge_stage_feedback_revision(
    artifact: RoadmapArtifact,
    context: StageRevisionContext,
    operations: StageRevisionOperations,
) -> RoadmapArtifact:
    """Return the closed stage-envelope candidate for ``artifact``."""
    return merge_stage_revision(artifact, context, operations)


def merge_feedback_revision(
    artifact: RoadmapArtifact,
    preflight: RevisionPreflight,
    operations: RevisionOperations,
) -> RoadmapArtifact:
    """Return the one-artifact candidate described by ``operations``."""
    if not isinstance(preflight, RevisionPreflight):
        raise RevisionMergeError("revision merge requires selected preflight context")
    if not isinstance(operations, RevisionOperations):
        raise RevisionMergeError("revision merge requires parsed revision operations")

    selected_feedback = _selected_feedback(artifact, preflight)
    response = _response_for_selected_feedback(operations, preflight)
    candidate = artifact

    if operations.replacement is not None:
        replacement = _replacement_for_selected_target(operations, preflight)
        try:
            candidate = replace_design_row(
                candidate,
                collection=preflight.target_collection,
                row_id=preflight.target_row_id,
                field=replacement.field,
                value=replacement.value,
            )
        except ValueError as exc:
            raise RevisionMergeError(
                f"selected target row {preflight.target_row_id!r} cannot be replaced"
            ) from exc

    updated_feedback = replace(
        selected_feedback,
        state=FeedbackState.AWAITING_REVIEW,
        proposed_response=response.proposed_response,
        feedback_reopen=None,
    )
    feedback = tuple(
        updated_feedback if row.id == preflight.feedback_id else row for row in candidate.feedback
    )
    return replace(candidate, feedback=feedback)


def _selected_feedback(artifact: RoadmapArtifact, preflight: RevisionPreflight) -> FeedbackRow:
    selected = [row for row in artifact.feedback if row.id == preflight.feedback_id]
    if len(selected) != 1:
        raise RevisionMergeError(
            f"selected feedback {preflight.feedback_id!r} must occur exactly once"
        )

    feedback = selected[0]
    if (
        feedback.state is not FeedbackState.OPEN
        or feedback.state is not preflight.feedback_state
        or feedback.proposed_response is not None
        or feedback.target.kind is not FeedbackTargetKind.ROW
        or feedback.target.row_id != preflight.target_row_id
        or feedback.request != preflight.feedback_request
    ):
        raise RevisionMergeError(
            f"selected feedback {preflight.feedback_id!r} no longer matches its selection"
        )
    return feedback


def _response_for_selected_feedback(
    operations: RevisionOperations, preflight: RevisionPreflight
) -> RespondFeedbackOperation:
    response = operations.response
    if not isinstance(response, RespondFeedbackOperation):
        raise RevisionMergeError(
            f"selected feedback {preflight.feedback_id!r} requires one response"
        )
    if response.feedback_id != preflight.feedback_id:
        raise RevisionMergeError(
            f"feedback response names {response.feedback_id!r}, not selected feedback "
            f"{preflight.feedback_id!r}"
        )
    if (
        not response.proposed_response
        or response.proposed_response != response.proposed_response.strip()
    ):
        raise RevisionMergeError(
            f"selected feedback {preflight.feedback_id!r} requires a nonempty response"
        )
    return response


def _replacement_for_selected_target(
    operations: RevisionOperations, preflight: RevisionPreflight
) -> ReplaceRowPresentationOperation:
    replacement = operations.replacement
    if not isinstance(replacement, ReplaceRowPresentationOperation):
        raise RevisionMergeError(
            f"selected target row {preflight.target_row_id!r} requires a valid replacement"
        )
    if replacement.row_id != preflight.target_row_id:
        raise RevisionMergeError(
            f"presentation replacement names {replacement.row_id!r}, not selected "
            f"target row {preflight.target_row_id!r}"
        )
    allowed_fields = {item.field for item in preflight.allowed_text_fields}
    if replacement.field not in allowed_fields:
        raise RevisionMergeError(
            f"presentation field {replacement.field!r} is not allowed for selected "
            f"target row {preflight.target_row_id!r}"
        )
    if not replacement.value or replacement.value != replacement.value.strip():
        raise RevisionMergeError(
            f"selected target row {preflight.target_row_id!r} requires a nonempty replacement value"
        )
    return replacement


# Stage-envelope merger ----------------------------------------------------


def _verify_stage_source(
    artifact: RoadmapArtifact, context: StageRevisionContext
) -> tuple[dict[str, StageLiveRow], dict[str, StageProseSpan]]:
    """Recheck every source fact the typed stage envelope binds."""
    if _artifact_key(artifact) != context.artifact_key:
        raise StageRevisionSourceError(
            "stage context artifact key no longer matches the loaded artifact"
        )

    active_feedback = tuple(row for row in artifact.feedback if row.state is FeedbackState.OPEN)
    expected_feedback_ids = tuple(item.feedback_id for item in context.active_feedback)
    actual_feedback_ids = tuple(row.id for row in active_feedback)
    if actual_feedback_ids != expected_feedback_ids:
        raise StageRevisionSourceError(
            "active feedback no longer matches the stage context in predecessor order"
        )
    rows_by_id: dict[str, list[tuple[str, StageRow]]] = {}
    for collection, rows in stage_row_collections(artifact).items():
        for row in rows:
            rows_by_id.setdefault(row.id, []).append((collection, row))

    live_rows: dict[str, StageLiveRow] = {}
    for live in context.live_rows:
        if live.row_id in live_rows:
            raise StageRevisionSourceError(f"stage context repeats live row {live.row_id!r}")
        matches = rows_by_id.get(live.row_id, ())
        if len(matches) != 1:
            raise StageRevisionSourceError(
                f"context-bound row {live.row_id!r} no longer occurs exactly once"
            )
        collection, current = matches[0]
        if collection != live.row_type or current != live.row:
            raise StageRevisionSourceError(
                f"context-bound row {live.row_id!r} no longer matches its source facts"
            )
        live_rows[live.row_id] = live

    for feedback, authority in zip(active_feedback, context.active_feedback, strict=True):
        _verify_feedback_authority(feedback, authority, live_rows)

    if isinstance(artifact, PlansArtifact) and artifact.ordering != context.ordering_entries:
        raise StageRevisionSourceError("plan ordering no longer matches the stage context")
    if not isinstance(artifact, PlansArtifact) and context.ordering_entries:
        raise StageRevisionSourceError("only a plans artifact may carry stage ordering facts")

    spans = _verify_stage_prose_spans(artifact.body, context, live_rows, rows_by_id)
    return live_rows, spans


def _artifact_key(artifact: RoadmapArtifact) -> str:
    try:
        return ARTIFACT_KEY_BY_TYPE[type(artifact)]
    except KeyError as exc:
        raise StageRevisionSourceError(
            f"unknown roadmap artifact type {type(artifact).__name__}"
        ) from exc


def _verify_feedback_authority(
    feedback: FeedbackRow,
    authority: StageFeedbackAuthority,
    live_rows: Mapping[str, StageLiveRow],
) -> None:
    if (
        feedback.id != authority.feedback_id
        or feedback.target != authority.target
        or feedback.request != authority.request
        or feedback.proposed_response is not None
    ):
        raise StageRevisionSourceError(
            f"active feedback {authority.feedback_id!r} no longer matches its context"
        )
    if authority.target is None:
        raise StageRevisionSourceError(
            f"active feedback {authority.feedback_id!r} has no context target"
        )
    if authority.target.kind is FeedbackTargetKind.ARTIFACT:
        if not authority.allow_add or authority.target_row_id is not None:
            raise StageRevisionSourceError(
                f"artifact feedback {authority.feedback_id!r} has invalid add authority"
            )
        return
    if authority.target.kind is not FeedbackTargetKind.ROW:
        raise StageRevisionSourceError(
            f"row feedback {authority.feedback_id!r} has invalid target authority"
        )
    if authority.target_row_id is None:
        if (
            authority.target_row_type is not None
            or authority.allow_add
            or authority.allow_edit
            or authority.allow_remove
        ):
            raise StageRevisionSourceError(
                f"unresolved feedback {authority.feedback_id!r} has material authority"
            )
        return
    if authority.target_row_type is None:
        raise StageRevisionSourceError(
            f"row feedback {authority.feedback_id!r} has invalid target authority"
        )
    policy = stage_row_operation_policy(authority.target_row_type)
    target = live_rows.get(authority.target_row_id)
    if target is None:
        raise StageRevisionSourceError(
            f"row feedback {authority.feedback_id!r} has no live context target"
        )
    material_allowed = not (policy.allow_prose and target.prose_span_id is None)
    if (
        authority.target.row_id != authority.target_row_id
        or authority.allow_edit is not material_allowed
        or authority.allow_add
        or authority.allow_remove is not (material_allowed and policy.allow_remove)
    ):
        raise StageRevisionSourceError(
            f"row feedback {authority.feedback_id!r} has invalid target authority"
        )


def _verify_stage_prose_spans(
    body: str,
    context: StageRevisionContext,
    live_rows: dict[str, StageLiveRow],
    rows_by_id: dict[str, list[tuple[str, StageRow]]],
) -> dict[str, StageProseSpan]:
    """Validate the exact source spans before a body byte may change."""
    spans: dict[str, StageProseSpan] = {}
    occupied: list[tuple[int, int]] = []
    for span in context.prose_spans:
        if span.span_id in spans:
            raise StageRevisionSourceError(
                f"stage context repeats prose span {span.span_id!r}"
            )
        live = live_rows.get(span.row_id)
        if live is None or live.prose_span_id != span.span_id:
            raise StageRevisionSourceError(
                f"prose span {span.span_id!r} is not issued for its selected row"
            )
        if not stage_row_operation_policy(live.row_type).allow_prose:
            raise StageRevisionSourceError(
                f"identity-only row {span.row_id!r} may not own a prose span"
            )
        if (
            span.start < 0
            or span.end < span.start
            or body[span.start : span.end] != span.text
            or span.span_id != stage_prose_span_id(span.row_id, span.text)
            or not contains_whole_row_id(span.text, span.row_id)
        ):
            raise StageRevisionSourceError(
                f"prose span {span.span_id!r} is stale against the loaded artifact"
            )
        if any(start < span.end and span.start < end for start, end in occupied):
            raise StageRevisionSourceError(f"prose span {span.span_id!r} overlaps another span")
        for other_id in rows_by_id:
            if other_id != span.row_id and contains_whole_row_id(span.text, other_id):
                raise StageRevisionSourceError(
                    f"prose span {span.span_id!r} shares unselected row {other_id!r}"
                )
        spans[span.span_id] = span
        occupied.append((span.start, span.end))
    return spans


def _verify_stage_operations(
    artifact: RoadmapArtifact,
    context: StageRevisionContext,
    operations: StageRevisionOperations,
    live_rows: tuple[dict[str, StageLiveRow], dict[str, StageProseSpan]],
) -> frozenset[str]:
    """Reject every stale, broad, or relation-changing operation before merging."""
    rows, _spans = live_rows
    authorities = {item.feedback_id: item for item in context.active_feedback}
    if len(authorities) != len(context.active_feedback):
        raise RevisionMergeError("stage context repeats active feedback authority")

    expected_responses = tuple(item.feedback_id for item in context.active_feedback)
    actual_responses = tuple(
        response.feedback_id
        for response in operations.responses
        if isinstance(response, StageRespondFeedbackOperation)
    )
    if len(actual_responses) != len(operations.responses) or actual_responses != expected_responses:
        raise RevisionMergeError(
            "stage responses must name every active feedback item in predecessor order"
        )
    for response in operations.responses:
        if not isinstance(response, StageRespondFeedbackOperation) or not _is_trimmed_text(
            response.proposed_response
        ):
            raise RevisionMergeError("stage feedback responses require nonempty trimmed text")

    all_rows = {
        row.id
        for collection_rows in stage_row_collections(artifact).values()
        for row in collection_rows
    }
    material_feedback_ids: set[str] = set()
    material_row_ids: set[str] = set()
    removals: set[str] = set()
    for operation in operations.material_operations:
        if not isinstance(
            operation,
            (AddRowOperation, EditRowOperation, RemoveRowWithRecordOperation),
        ):
            raise RevisionMergeError("stage envelope contains an unsupported material operation")
        authority = authorities.get(operation.feedback_id)
        if authority is None or operation.feedback_id in material_feedback_ids:
            raise RevisionMergeError(
                f"stage feedback {operation.feedback_id!r} has invalid material authority"
            )
        material_feedback_ids.add(operation.feedback_id)
        if isinstance(operation, AddRowOperation):
            _verify_stage_addition(artifact, context, operation, authority, all_rows)
            row_id = operation.row.id
        elif isinstance(operation, EditRowOperation):
            _verify_stage_edit(operation, authority, rows)
            row_id = operation.row_id
        else:
            _verify_stage_removal(artifact, operation, authority, rows)
            row_id = operation.row_id
            removals.add(row_id)
        if row_id in material_row_ids:
            raise RevisionMergeError(f"stage row {row_id!r} has more than one material operation")
        material_row_ids.add(row_id)

    return frozenset(removals)


def _verify_stage_addition(
    artifact: RoadmapArtifact,
    context: StageRevisionContext,
    operation: AddRowOperation,
    authority: StageFeedbackAuthority,
    all_rows: set[str],
) -> None:
    if (
        not authority.allow_add
        or authority.target is None
        or authority.target.kind is not FeedbackTargetKind.ARTIFACT
        or not stage_collection_accepts_add(artifact, operation.row_type)
        or not stage_row_operation_policy(operation.row_type).allow_add
        or operation.row.id in all_rows
        or operation.row.id in context.carried_removal_ids
    ):
        raise RevisionMergeError(
            f"stage row addition {operation.row.id!r} no longer matches its authority"
        )
    try:
        append_stage_row(artifact, collection=operation.row_type, row=operation.row)
    except ValueError as exc:
        raise RevisionMergeError(
            f"stage row addition {operation.row.id!r} has an invalid collection or row type"
        ) from exc
    if not set(declared_relation_ids_for_row(operation.row)) <= context.predecessor_relation_ids:
        raise RevisionMergeError(
            f"added row {operation.row.id!r} names a relation outside predecessor facts"
        )
    _verify_addition_ordering(artifact, context, operation)


def _verify_addition_ordering(
    artifact: RoadmapArtifact,
    context: StageRevisionContext,
    operation: AddRowOperation,
) -> None:
    if not stage_row_operation_policy(operation.row_type).requires_ordering_companion:
        if operation.ordering is not None:
            raise RevisionMergeError("only an added plan row may carry ordering")
        return
    if not isinstance(artifact, PlansArtifact) or not isinstance(operation.row, PlanRow):
        raise RevisionMergeError("a plan addition requires a plans artifact and PlanRow")
    ordering = operation.ordering
    if (
        ordering is None
        or ordering.plan_id != operation.row.id
        or any(entry.plan_id == ordering.plan_id for entry in artifact.ordering)
    ):
        raise RevisionMergeError(
            f"added plan {operation.row.id!r} requires one new matching ordering entry"
        )
    allowed = set(context.predecessor_plan_ids)
    if not set((*ordering.depends_on, *ordering.assumption_targets)) <= allowed:
        raise RevisionMergeError(
            f"ordering for added plan {operation.row.id!r} names a non-predecessor plan"
        )


def _verify_stage_edit(
    operation: EditRowOperation,
    authority: StageFeedbackAuthority,
    live_rows: dict[str, StageLiveRow],
) -> None:
    target = _verify_target_operation(operation, authority, live_rows)
    if operation.row.id != operation.row_id or type(operation.row) is not type(target.row):
        raise RevisionMergeError(
            f"stage row edit {operation.row_id!r} does not preserve its typed identity"
        )
    if not same_declared_row_relations(target.row, operation.row):
        raise RevisionMergeError(f"stage row edit {operation.row_id!r} changes a declared relation")
    if not stage_row_edit_preserves_fixed_fields(
        target.row, operation.row, row_type=operation.row_type
    ):
        fixed = ", ".join(
            repr(field)
            for field in stage_row_operation_policy(operation.row_type).immutable_fields
        )
        raise RevisionMergeError(
            f"{operation.row_type} edit {operation.row_id!r} changes its fixed field {fixed}"
        )


def _verify_stage_removal(
    artifact: RoadmapArtifact,
    operation: RemoveRowWithRecordOperation,
    authority: StageFeedbackAuthority,
    live_rows: dict[str, StageLiveRow],
) -> None:
    _verify_target_operation(operation, authority, live_rows)
    if not stage_row_operation_policy(operation.row_type).allow_remove:
        raise RevisionMergeError(f"{operation.row_type} rows are never removable")
    record = operation.removal_record
    if (
        record.removed_id != operation.row_id
        or not _is_nonblank_text(record.rationale)
        or operation.feedback_id not in record.feedback_ids
        or not record.feedback_ids
        or any(not _is_nonblank_text(item) for item in record.feedback_ids)
        or any(existing.removed_id == operation.row_id for existing in artifact.removals)
    ):
        raise RevisionMergeError(
            f"stage removal {operation.row_id!r} has invalid continuity evidence"
        )


def _verify_target_operation(
    operation: EditRowOperation | RemoveRowWithRecordOperation,
    authority: StageFeedbackAuthority,
    live_rows: dict[str, StageLiveRow],
) -> StageLiveRow:
    if (
        not (
            authority.allow_edit
            if isinstance(operation, EditRowOperation)
            else authority.allow_remove
        )
        or authority.target_row_id != operation.row_id
        or authority.target_row_type != operation.row_type
    ):
        raise RevisionMergeError(
            f"stage operation for {operation.row_id!r} no longer matches its authority"
        )
    target = live_rows.get(operation.row_id)
    if target is None or target.row_type != operation.row_type:
        raise RevisionMergeError(
            f"stage target row {operation.row_id!r} no longer matches its context"
        )
    return target


def _reject_surviving_removal_references(
    context: StageRevisionContext,
    candidate: RoadmapArtifact,
    removal_ids: frozenset[str],
) -> None:
    """Reject a deletion when a frozen or newly-added fact still names it."""
    candidate_relations = extract_declared_relations(
        **{_artifact_key(candidate): candidate}
    )
    for removed_id in removal_ids:
        for relation in (*context.relations, *candidate_relations):
            if relation.endpoint_id == removed_id and relation.owner_id not in removal_ids:
                raise RevisionMergeError(
                    f"stage removal {removed_id!r} leaves relation owner "
                    f"{relation.owner_id!r} referring to it"
                )


def _apply_stage_material_operation(
    artifact: RoadmapArtifact, operation: StageMaterialOperation
) -> RoadmapArtifact:
    if isinstance(operation, AddRowOperation):
        candidate = append_stage_row(artifact, collection=operation.row_type, row=operation.row)
        if stage_row_operation_policy(operation.row_type).requires_ordering_companion:
            assert isinstance(candidate, PlansArtifact)
            assert operation.ordering is not None
            return append_plan_ordering_entry(candidate, operation.ordering)
        return candidate
    if isinstance(operation, EditRowOperation):
        return replace_stage_row(
            artifact,
            collection=operation.row_type,
            row_id=operation.row_id,
            row=operation.row,
        )
    candidate = remove_stage_row(artifact, collection=operation.row_type, row_id=operation.row_id)
    if stage_row_operation_policy(operation.row_type).requires_ordering_companion:
        assert isinstance(candidate, PlansArtifact)
        try:
            candidate = remove_plan_ordering_entry(candidate, plan_id=operation.row_id)
        except ValueError as exc:
            raise RevisionMergeError(
                f"plan removal {operation.row_id!r} requires exactly one ordering companion"
            ) from exc
    return append_removal_record(candidate, operation.removal_record)


def _apply_stage_prose_amendments(
    artifact: RoadmapArtifact,
    context: StageRevisionContext,
    operations: StageRevisionOperations,
    source: tuple[dict[str, StageLiveRow], dict[str, StageProseSpan]],
) -> str:
    """Apply only exact source spans, then append admitted row fragments."""
    _live_rows, spans = source
    replacements: list[tuple[StageProseSpan, str]] = []
    append_fragments: list[str] = []
    for operation in operations.material_operations:
        amendment = operation.prose_amendment
        if not stage_row_operation_policy(operation.row_type).allow_prose:
            if amendment is not None:
                raise RevisionMergeError(
                    f"identity-only row {operation.row_id if not isinstance(operation, AddRowOperation) else operation.row.id!r} may not amend prose"
                )
            continue
        row_id = operation.row.id if isinstance(operation, AddRowOperation) else operation.row_id
        if isinstance(operation, AddRowOperation):
            if not isinstance(amendment, AppendRowProseAmendment) or amendment.row_id != row_id:
                raise RevisionMergeError(
                    f"added row {row_id!r} requires its own append-only prose fragment"
                )
            if not _is_nonblank_text(amendment.fragment) or not contains_whole_row_id(
                amendment.fragment, row_id
            ):
                raise RevisionMergeError(
                    f"appended prose for {row_id!r} is not its admitted row fragment"
                )
            append_fragments.append(amendment.fragment)
            continue
        if isinstance(operation, EditRowOperation):
            if not isinstance(amendment, ReplaceRowProseAmendment):
                raise RevisionMergeError(
                    f"edited row {row_id!r} requires an issued prose replacement"
                )
            replacement = amendment.replacement
        else:
            if not isinstance(amendment, DeleteRowProseAmendment):
                raise RevisionMergeError(
                    f"removed row {row_id!r} requires an issued prose deletion"
                )
            replacement = ""
        span = spans.get(amendment.span_id)
        if span is None or amendment.row_id != row_id or span.row_id != row_id:
            raise RevisionMergeError(
                f"prose amendment for {row_id!r} does not name its issued span"
            )
        if isinstance(amendment, ReplaceRowProseAmendment) and not _is_nonblank_text(replacement):
            raise RevisionMergeError(
                f"prose replacement for {row_id!r} must be nonempty trimmed text"
            )
        replacements.append((span, replacement))

    body = splice_exact_spans(
        artifact.body, [(span.start, span.end, replacement) for span, replacement in replacements]
    )
    return append_row_prose_fragments(body, append_fragments)


def splice_exact_spans(body: str, edits: Iterable[tuple[int, int, str]]) -> str:
    """Splice `(start, end, replacement)` edits into `body`, refusing overlapping ranges."""
    edit_list = list(edits)
    ranges = sorted((start, end) for start, end, _replacement in edit_list)
    if any(
        start < prior_end for (prior_start, prior_end), (start, _end) in zip(ranges, ranges[1:])
    ):
        raise RevisionMergeError("stage prose amendments overlap")
    for start, end, replacement in sorted(edit_list, key=lambda item: item[0], reverse=True):
        body = f"{body[:start]}{replacement}{body[end:]}"
    return body


def append_row_prose_fragments(body: str, fragments: Iterable[str]) -> str:
    """Append row-owned prose fragments with the established body spacing."""
    for fragment in fragments:
        if not body or body.endswith("\n\n"):
            body += fragment
        elif body.endswith("\n"):
            body += f"\n{fragment}"
        else:
            body += f"\n\n{fragment}"
    return body


def _apply_stage_responses(
    artifact: RoadmapArtifact,
    context: StageRevisionContext,
    operations: StageRevisionOperations,
) -> RoadmapArtifact:
    responses = {response.feedback_id: response for response in operations.responses}
    feedback = tuple(
        replace(
            row,
            state=FeedbackState.AWAITING_REVIEW,
            proposed_response=responses[row.id].proposed_response,
            feedback_reopen=None,
        )
        if row.id in responses
        else row
        for row in artifact.feedback
    )
    if len(responses) != len(context.active_feedback):
        raise RevisionMergeError("stage response set changed during merge")
    return replace(artifact, feedback=feedback)


def _is_trimmed_text(value: str) -> bool:
    return bool(value) and value == value.strip()


def _is_nonblank_text(value: str) -> bool:
    return bool(value.strip())
