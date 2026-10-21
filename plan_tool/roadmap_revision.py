"""Pure contract for one bounded, same-artifact feedback revision."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, fields, replace
from types import MappingProxyType
from typing import Annotated, Any, Final, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, ValidationError as PydanticValidationError

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
    EntityRow,
    FeedbackRow,
    FieldRow,
    FieldType,
    FeedbackState,
    FeedbackTarget,
    FeedbackTargetKind,
    HostingRow,
    OrderingEntry,
    PatternRow,
    PlanDisposition,
    PlanRow,
    PlansArtifact,
    ResearchDisclosure,
    RejectedAlternative,
    RemovalRecord,
    StackRow,
    StoreRow,
    WorkflowRow,
    design_row_collections,
    stage_row_collections,
    stage_row_edit_preserves_fixed_fields,
    stage_row_operation_policy,
)
from plan_tool.roadmap_feedback import (
    FeedbackSelector,
    MalformedFeedbackSelector,
    UnknownFeedbackArtifact,
    matching_feedback_rows,
    parse_feedback_selector as parse_shared_feedback_selector,
)
from plan_tool.roadmap_gates import feedback_target_ids
from plan_tool.roadmap_relations import (
    ARTIFACT_KEYS,
    ARTIFACT_KEY_BY_TYPE,
    declared_relation_ids_for_row,
    RoadmapRelation,
    extract_declared_relations,
    same_declared_row_relations,
    select_declared_relations_for_ids,
)
from plan_tool.project_config import (
    HARD_MAX_ACTIVE_FEEDBACK_ITEMS,
    HARD_MAX_PROSE_AMENDMENT_BYTES,
    HARD_MAX_RESPONSE_BYTES,
    StageFeedbackLimits,
)


class RevisionContractError(ValueError):
    """The selected feedback or its bounded response violates this contract."""


class RenderCanonicalMismatch(RevisionContractError):
    """The selected artifact does not round-trip through parse/render exactly.

    Its own subtype rather than a shared ``RevisionContractError`` message:
    an ``isinstance`` check on a dedicated type is a robust discriminator where
    matching a substring of the exception's message text is not.
    """


class StageRevisionLimitError(RevisionContractError):
    """A stage budget is invalid input, never a correction candidate."""

    invalid = True
    retryable = False

    def __init__(
        self,
        *,
        label: str,
        measured: int,
        limit: int,
        feedback_id: str | None = None,
    ) -> None:
        self.label = label
        self.measured = measured
        self.limit = limit
        self.feedback_id = feedback_id
        self.action = STAGE_SPLIT_FEEDBACK_ACTION
        feedback = f" for feedback {feedback_id!r}" if feedback_id is not None else ""
        super().__init__(
            f"{label}{feedback} is {measured}, above the effective limit {limit}; {self.action}"
        )


@dataclass(frozen=True)
class TextFieldValue:
    """A target row's patchable presentation field and its current value."""

    field: str
    value: str


@dataclass(frozen=True)
class RelationValue:
    """One immutable target-row value outside the presentation patch surface."""

    field: str
    value: object


@dataclass(frozen=True)
class RevisionPreflight:
    """The bounded context a local revision may use after canonical input checks."""

    selector: FeedbackSelector
    feedback_request: str
    feedback_state: FeedbackState
    target_row_id: str
    target_collection: str
    allowed_text_fields: tuple[TextFieldValue, ...]
    relation_data: tuple[RelationValue, ...]

    @property
    def artifact_key(self) -> str:
        """Return the selected stage-derived artifact key."""
        return self.selector.artifact_key

    @property
    def feedback_id(self) -> str:
        """Return the selected feedback id."""
        return self.selector.feedback_id

    @property
    def target_row_type(self) -> str:
        """Return the selected row collection's type name."""
        return self.target_collection

    @property
    def allowed_fields(self) -> tuple[TextFieldValue, ...]:
        """Return the target's patchable presentation values."""
        return self.allowed_text_fields


# The only local presentation surface. A collection absent from this table is
# not a targetable design-row collection.
TEXT_FIELDS_BY_ROW_TYPE: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "entities": ("name",),
        "business_rules": ("statement",),
        "workflows": ("name",),
        "decisions": ("rationale",),
        "dispositions": (),
        "constraints": ("statement",),
        "system_patterns": ("name", "statement"),
        "component_patterns": ("name", "statement"),
        "components": ("name",),
        "plans": ("title", "sizing_rationale"),
        "assumptions": ("statement",),
    }
)

# Kept in code so ROADMAP_FORMAT.md's executable example has one owner.
REVISION_OPERATION_EXAMPLE_JSON: Final[str] = """{
  \"operations\": [
    {
      \"op\": \"replace-row-presentation\",
      \"row_id\": \"row-to-revise\",
      \"field\": \"name\",
      \"value\": \"Revised presentation\"
    },
    {
      \"op\": \"respond-feedback\",
      \"feedback_id\": \"feedback-to-answer\",
      \"proposed_response\": \"The selected request now has a bounded response.\"
    }
  ]
}"""


Artifact: TypeAlias = DomainArtifact | ConstraintsArtifact | ComponentsArtifact | PlansArtifact
DesignRow: TypeAlias = (
    EntityRow
    | BusinessRuleRow
    | WorkflowRow
    | DecisionRow
    | AttributeDispositionRow
    | ConstraintRow
    | PatternRow
    | ComponentRow
    | PlanRow
    | AssumptionRow
)
ParseArtifact: TypeAlias = Callable[[str], Artifact]
RenderArtifact: TypeAlias = Callable[[Artifact], str]


def parse_feedback_selector(value: object, artifact_keys: Collection[str]) -> FeedbackSelector:
    """Adapt shared selector outcomes to the local revision error contract."""
    outcome = parse_shared_feedback_selector(value, artifact_keys)
    if isinstance(outcome, FeedbackSelector):
        return outcome
    if isinstance(outcome, UnknownFeedbackArtifact):
        raise RevisionContractError(f"unknown roadmap artifact key: {outcome.artifact_key!r}")
    if outcome.reason == "not-string":
        raise RevisionContractError("feedback selector must be a string")
    if outcome.reason == "missing-separator":
        raise RevisionContractError("feedback selector must use '<artifact-key>:<feedback-id>'")
    assert isinstance(outcome, MalformedFeedbackSelector)
    raise RevisionContractError(
        "feedback selector must contain one non-empty artifact key and one colon-free feedback id"
    )


def preflight_feedback_revision(
    selector: FeedbackSelector,
    artifact_text: str,
    parse_artifact: ParseArtifact,
    render_artifact: RenderArtifact,
) -> RevisionPreflight:
    """Prove one selected feedback row can use the bounded local path."""
    artifact = parse_artifact(artifact_text)
    if render_artifact(artifact) != artifact_text:
        raise RenderCanonicalMismatch(
            "selected artifact is not render-canonical; local revision preserves "
            "only exact parser-renderer output"
        )

    _validate_retained_feedback(artifact)
    selected = matching_feedback_rows(artifact, selector)
    if len(selected) != 1:
        raise RevisionContractError(
            f"feedback id {selector.feedback_id!r} does not identify exactly one row"
        )
    feedback = selected[0]
    if feedback.state is not FeedbackState.OPEN:
        raise RevisionContractError(
            f"selected feedback {feedback.id!r} must be open, not {feedback.state.value!r}"
        )
    if feedback.proposed_response is not None:
        raise RevisionContractError(
            f"selected feedback {feedback.id!r} already has a proposed response"
        )
    if feedback.target.kind is not FeedbackTargetKind.ROW:
        raise RevisionContractError(f"selected feedback {feedback.id!r} must target one design row")
    if feedback.target.row_id is None:  # The artifact parser normally prevents this.
        raise RevisionContractError(f"selected feedback {feedback.id!r} has no target row id")

    target_rows = [
        (collection, row)
        for collection, row in _design_rows_by_collection(artifact)
        if row.id == feedback.target.row_id
    ]
    if len(target_rows) != 1:
        raise RevisionContractError(
            f"selected feedback {feedback.id!r} must target exactly one live "
            f"design row, found {len(target_rows)} for {feedback.target.row_id!r}"
        )
    collection, target_row = target_rows[0]
    if collection == "decisions" and isinstance(target_row, DecisionRow) and target_row.source is not None:
        raise RevisionContractError(
            f"selected feedback {feedback.id!r} targets inherited decision "
            f"{target_row.id!r}; local revision cannot change its approved content"
        )
    try:
        allowed_fields = TEXT_FIELDS_BY_ROW_TYPE[collection]
    except KeyError as exc:
        # ``collection`` came from ``design_row_collections`` (via
        # ``_design_rows_by_collection``); this table is hand-maintained
        # separately and covers the same collections today, but nothing
        # enforces that they stay in sync. A typed rejection here, not an
        # uncaught ``KeyError``, is what a future drift should surface as.
        raise RevisionContractError(
            f"design-row collection {collection!r} has no local revision text-field contract"
        ) from exc
    return RevisionPreflight(
        selector=selector,
        feedback_request=feedback.request,
        feedback_state=feedback.state,
        target_row_id=target_row.id,
        target_collection=collection,
        allowed_text_fields=tuple(
            TextFieldValue(field=field, value=getattr(target_row, field))
            for field in allowed_fields
        ),
        relation_data=tuple(
            RelationValue(field=field.name, value=getattr(target_row, field.name))
            for field in fields(target_row)
            if field.name not in {"id", *allowed_fields}
        ),
    )


def _validate_retained_feedback(artifact: Artifact) -> None:
    """Validate every retained feedback target against the candidate artifact.

    The publish gate separately gives newly added feedback predecessor-scoped
    authority, so a model cannot invent a reviewer request after the fact.
    """
    counts: dict[str, int] = {}
    for feedback in artifact.feedback:
        counts[feedback.id] = counts.get(feedback.id, 0) + 1
    duplicates = sorted(row_id for row_id, count in counts.items() if count > 1)
    if duplicates:
        raise RevisionContractError(
            "retained feedback ids must be unique: "
            + ", ".join(repr(row_id) for row_id in duplicates)
        )

    resolvable_ids = feedback_target_ids(artifact) | {
        removal.removed_id for removal in artifact.removals
    }
    dangling = sorted(
        feedback.id
        for feedback in artifact.feedback
        if feedback.target.kind is FeedbackTargetKind.ROW
        and feedback.target.row_id not in resolvable_ids
    )
    if dangling:
        raise RevisionContractError(
            "retained row-targeted feedback has no live row or recorded removal: "
            + ", ".join(repr(row_id) for row_id in dangling)
        )


def _design_rows_by_collection(
    artifact: Artifact,
) -> tuple[tuple[str, DesignRow], ...]:
    """Return local targetable rows in their artifact render order.

    Delegates to :func:`roadmap_artifacts.design_row_collections` rather than
    its own ``isinstance`` table — see that function's docstring for why a
    second copy would drift.
    """
    return tuple(
        (collection, row)
        for collection, rows in design_row_collections(artifact).items()
        for row in rows
    )


class ReplaceRowPresentationOperation(BaseModel):
    """The optional one-field presentation update."""

    model_config = ConfigDict(extra="forbid", use_enum_values=False, strict=True, frozen=True)

    op: Literal["replace-row-presentation"]
    row_id: str
    field: str
    value: str


class RespondFeedbackOperation(BaseModel):
    """The required final answer to the selected reviewer request."""

    model_config = ConfigDict(extra="forbid", use_enum_values=False, strict=True, frozen=True)

    op: Literal["respond-feedback"]
    feedback_id: str
    proposed_response: str


Operation: TypeAlias = ReplaceRowPresentationOperation | RespondFeedbackOperation


class _RevisionEnvelope(BaseModel):
    """Closed root shape before each operation receives its closed model."""

    model_config = ConfigDict(extra="forbid", use_enum_values=False, strict=True)

    operations: list[object]


@dataclass(frozen=True)
class RevisionOperations:
    """The legal optional replacement plus required feedback response."""

    replacement: ReplaceRowPresentationOperation | None
    response: RespondFeedbackOperation

    @property
    def operations(self) -> tuple[Operation, ...]:
        """Return the records in the only permitted order."""
        if self.replacement is None:
            return (self.response,)
        return (self.replacement, self.response)


def parse_revision_operations(
    response_text: str, preflight: RevisionPreflight
) -> RevisionOperations:
    """Parse and bind the two-operation JSON response to one preflight."""
    payload = _decode_single_json_object(response_text)
    try:
        envelope = _RevisionEnvelope.model_validate(payload)
    except PydanticValidationError as exc:
        raise RevisionContractError(f"invalid revision operation envelope: {exc}") from exc

    records = envelope.operations
    if not all(isinstance(record, dict) for record in records):
        raise RevisionContractError("revision operations must be an array of JSON objects")

    operation_names = [record.get("op") for record in records]
    replacement: ReplaceRowPresentationOperation | None = None
    if operation_names == ["respond-feedback"]:
        response = _validate_response(records[0], preflight)
    elif operation_names == ["replace-row-presentation", "respond-feedback"]:
        replacement = _validate_replacement(records[0], preflight)
        response = _validate_response(records[1], preflight)
    else:
        raise RevisionContractError(
            "revision operations must contain an optional "
            "'replace-row-presentation' followed by one final 'respond-feedback'"
        )
    return RevisionOperations(replacement=replacement, response=response)


def _decode_single_json_object(response_text: str) -> dict[str, object]:
    if not isinstance(response_text, str):
        raise RevisionContractError("revision response must be a JSON string")
    decoder = json.JSONDecoder(
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_constant,
    )
    start = len(response_text) - len(response_text.lstrip(" \t\r\n"))
    try:
        payload, end = decoder.raw_decode(response_text, start)
    except (json.JSONDecodeError, RevisionContractError) as exc:
        raise RevisionContractError("revision response must be one unfenced JSON object") from exc
    if response_text[end:].strip(" \t\r\n"):
        raise RevisionContractError("revision response must not contain trailing data")
    if not isinstance(payload, dict):
        raise RevisionContractError("revision response root must be a JSON object")
    if set(payload) != {"operations"}:
        raise RevisionContractError("revision response root must contain exactly 'operations'")
    if not isinstance(payload["operations"], list):
        raise RevisionContractError("revision response 'operations' must be an array")
    return payload


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RevisionContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise RevisionContractError(f"non-standard JSON constant: {value}")


def _validate_replacement(
    raw: dict[str, object], preflight: RevisionPreflight
) -> ReplaceRowPresentationOperation:
    try:
        operation = ReplaceRowPresentationOperation.model_validate(raw)
    except PydanticValidationError as exc:
        raise RevisionContractError(f"invalid presentation replacement: {exc}") from exc
    if operation.row_id != preflight.target_row_id:
        raise RevisionContractError("presentation replacement must name the selected target row")
    allowed_fields = {field.field for field in preflight.allowed_text_fields}
    if operation.field not in allowed_fields:
        raise RevisionContractError(
            f"presentation replacement field {operation.field!r} is not allowed "
            f"for {preflight.target_collection!r}"
        )
    _require_trimmed_text(operation.value, "presentation replacement value")
    return operation


def _validate_response(
    raw: dict[str, object], preflight: RevisionPreflight
) -> RespondFeedbackOperation:
    try:
        operation = RespondFeedbackOperation.model_validate(raw)
    except PydanticValidationError as exc:
        raise RevisionContractError(f"invalid feedback response: {exc}") from exc
    if operation.feedback_id != preflight.feedback_id:
        raise RevisionContractError("feedback response must name the selected feedback row")
    _require_trimmed_text(operation.proposed_response, "proposed response")
    return operation


def _require_trimmed_text(value: str, label: str) -> None:
    if not value or value != value.strip():
        raise RevisionContractError(
            f"{label} must be a non-blank string without surrounding whitespace"
        )


# --------------------------------------------------------------------------
# Stage feedback revision contract
# --------------------------------------------------------------------------


STAGE_MAX_ACTIVE_FEEDBACK_ITEMS: Final[int] = HARD_MAX_ACTIVE_FEEDBACK_ITEMS
STAGE_MAX_RESPONSE_BYTES: Final[int] = HARD_MAX_RESPONSE_BYTES
STAGE_MAX_PROSE_AMENDMENT_BYTES: Final[int] = HARD_MAX_PROSE_AMENDMENT_BYTES
STAGE_MAX_MATERIAL_OPERATIONS_PER_FEEDBACK: Final[int] = 1
STAGE_SPLIT_FEEDBACK_ACTION: Final[str] = "split the feedback into smaller requests"
STAGE_OPERATION_KINDS: Final[tuple[str, ...]] = (
    "add-row",
    "edit-row",
    "remove-row-with-record",
    "respond-feedback",
)

StageArtifactKey: TypeAlias = Literal["domain", "constraints", "components", "plans"]
StageRowType: TypeAlias = Literal[
    "entities",
    "business_rules",
    "workflows",
    "decisions",
    "dispositions",
    "constraints",
    "hosting",
    "system_patterns",
    "component_patterns",
    "stores",
    "stack",
    "components",
    "plans",
    "assumptions",
]
StageRow: TypeAlias = (
    EntityRow
    | BusinessRuleRow
    | WorkflowRow
    | DecisionRow
    | AttributeDispositionRow
    | ConstraintRow
    | HostingRow
    | PatternRow
    | StoreRow
    | StackRow
    | ComponentRow
    | PlanRow
    | AssumptionRow
)

_STAGE_ADD_ROW_TYPES: Final[Mapping[StageArtifactKey, frozenset[str]]] = MappingProxyType(
    {
        "domain": frozenset({"entities", "business_rules", "workflows", "decisions"}),
        "constraints": frozenset({"dispositions", "constraints", "decisions", "stack"}),
        "components": frozenset(
            {
                "system_patterns",
                "component_patterns",
                "stores",
                "components",
                "decisions",
            }
        ),
        "plans": frozenset({"plans", "assumptions", "decisions"}),
    }
)


class _StageWireModel(BaseModel):
    """Closed mutable-input wire shape before conversion to frozen records."""

    model_config = ConfigDict(extra="forbid", use_enum_values=False, strict=True, frozen=True)


class FieldRowPayload(_StageWireModel):
    name: str
    type: Literal["text", "number", "boolean", "timestamp", "enum", "reference"]
    entity_id: str | None = None

    def to_row(self) -> FieldRow:
        return FieldRow(name=self.name, type=FieldType(self.type), entity_id=self.entity_id)


class RejectedAlternativePayload(_StageWireModel):
    option: str
    reason: str

    def to_row(self) -> RejectedAlternative:
        return RejectedAlternative(option=self.option, reason=self.reason)


class EntityRowPayload(_StageWireModel):
    id: str
    name: str
    fields: list[FieldRowPayload]

    def to_row(self) -> EntityRow:
        return EntityRow(self.id, self.name, tuple(field.to_row() for field in self.fields))


class BusinessRuleRowPayload(_StageWireModel):
    id: str
    statement: str
    entity_ids: list[str]

    def to_row(self) -> BusinessRuleRow:
        return BusinessRuleRow(self.id, self.statement, tuple(self.entity_ids))


class WorkflowRowPayload(_StageWireModel):
    id: str
    name: str
    entity_ids: list[str]

    def to_row(self) -> WorkflowRow:
        return WorkflowRow(self.id, self.name, tuple(self.entity_ids))


class DecisionRowPayload(_StageWireModel):
    id: str
    chosen_option: str
    rejected_alternatives: list[RejectedAlternativePayload]
    rationale: str
    anchor: str
    status: Literal["settled", "pending"]

    def to_row(self) -> DecisionRow:
        return DecisionRow(
            self.id,
            self.chosen_option,
            tuple(item.to_row() for item in self.rejected_alternatives),
            self.rationale,
            self.anchor,
            DecisionStatus(self.status),
        )


class AttributeDispositionRowPayload(_StageWireModel):
    id: str
    attribute: str
    disposition: Literal["prioritized", "traded-away", "not-load-bearing"]

    def to_row(self) -> AttributeDispositionRow:
        return AttributeDispositionRow(
            self.id, self.attribute, ConstraintDisposition(self.disposition)
        )


class ConstraintRowPayload(_StageWireModel):
    id: str
    statement: str
    attribute: str
    anchor_ids: list[str]

    def to_row(self) -> ConstraintRow:
        return ConstraintRow(self.id, self.statement, self.attribute, tuple(self.anchor_ids))


class HostingRowPayload(_StageWireModel):
    id: str
    facet: str
    value: str
    product: str | None = None
    description: str | None = None
    research_disclosure: Literal["external", "local"] | None = None

    def to_row(self) -> HostingRow:
        return HostingRow(
            self.id,
            self.facet,
            self.value,
            self.product,
            self.description,
            (
                None
                if self.research_disclosure is None
                else ResearchDisclosure(self.research_disclosure)
            ),
        )


class PatternRowPayload(_StageWireModel):
    id: str
    name: str
    statement: str

    def to_row(self) -> PatternRow:
        return PatternRow(self.id, self.name, self.statement)


class StoreRowPayload(_StageWireModel):
    id: str
    category: str
    sharing: str
    product: str | None = None
    description: str | None = None
    research_disclosure: Literal["external", "local"] | None = None

    def to_row(self) -> StoreRow:
        return StoreRow(
            self.id,
            self.category,
            self.sharing,
            self.product,
            self.description,
            (
                None
                if self.research_disclosure is None
                else ResearchDisclosure(self.research_disclosure)
            ),
        )


class ComponentRowPayload(_StageWireModel):
    id: str
    name: str
    entity_ids: list[str]
    pattern_ids: list[str]
    constraint_ids: list[str] = Field(default_factory=list)
    store_ids: list[str] = Field(default_factory=list)

    def to_row(self) -> ComponentRow:
        return ComponentRow(
            self.id,
            self.name,
            tuple(self.entity_ids),
            tuple(self.pattern_ids),
            tuple(self.constraint_ids),
            tuple(self.store_ids),
        )


class PlanRowPayload(_StageWireModel):
    id: str
    title: str
    disposition: Literal["keep", "merge", "split", "cross-cutting"]
    component_ids: list[str]
    draft_seed_path: str
    sizing_rationale: str
    intent: str = ""
    non_goals: list[str] = Field(default_factory=list)

    def to_row(self) -> PlanRow:
        return PlanRow(
            self.id,
            self.title,
            PlanDisposition(self.disposition),
            tuple(self.component_ids),
            self.draft_seed_path,
            self.sizing_rationale,
            self.intent,
            tuple(self.non_goals),
        )


class AssumptionRowPayload(_StageWireModel):
    id: str
    statement: str
    consuming_plan_ids: list[str]

    def to_row(self) -> AssumptionRow:
        return AssumptionRow(self.id, self.statement, tuple(self.consuming_plan_ids))


class OrderingEntryPayload(_StageWireModel):
    plan_id: str
    depends_on: list[str] = Field(default_factory=list)
    assumption_targets: list[str] = Field(default_factory=list)

    def to_row(self) -> OrderingEntry:
        return OrderingEntry(self.plan_id, tuple(self.depends_on), tuple(self.assumption_targets))


class RemovalRecordPayload(_StageWireModel):
    removed_id: str
    rationale: str
    feedback_ids: list[str]

    def to_row(self) -> RemovalRecord:
        return RemovalRecord(self.removed_id, self.rationale, tuple(self.feedback_ids))


class StackRowPayload(_StageWireModel):
    id: str
    concern: str
    choice: str | None = None
    open: bool = False

    def to_row(self) -> StackRow:
        return StackRow(self.id, self.concern, self.choice, self.open)


RowPayload: TypeAlias = (
    EntityRowPayload
    | BusinessRuleRowPayload
    | WorkflowRowPayload
    | DecisionRowPayload
    | AttributeDispositionRowPayload
    | ConstraintRowPayload
    | HostingRowPayload
    | PatternRowPayload
    | StoreRowPayload
    | StackRowPayload
    | ComponentRowPayload
    | PlanRowPayload
    | AssumptionRowPayload
)

_PAYLOAD_BY_ROW_TYPE: Final[Mapping[str, type[RowPayload]]] = MappingProxyType(
    {
        "entities": EntityRowPayload,
        "business_rules": BusinessRuleRowPayload,
        "workflows": WorkflowRowPayload,
        "decisions": DecisionRowPayload,
        "dispositions": AttributeDispositionRowPayload,
        "constraints": ConstraintRowPayload,
        "hosting": HostingRowPayload,
        "system_patterns": PatternRowPayload,
        "component_patterns": PatternRowPayload,
        "stores": StoreRowPayload,
        "stack": StackRowPayload,
        "components": ComponentRowPayload,
        "plans": PlanRowPayload,
        "assumptions": AssumptionRowPayload,
    }
)


class ReplaceRowProseAmendmentPayload(_StageWireModel):
    action: Literal["replace"]
    row_id: str
    span_id: str
    replacement: str


class DeleteRowProseAmendmentPayload(_StageWireModel):
    action: Literal["delete"]
    row_id: str
    span_id: str


class AppendRowProseAmendmentPayload(_StageWireModel):
    action: Literal["append"]
    row_id: str
    fragment: str


RowProseAmendmentPayload: TypeAlias = (
    ReplaceRowProseAmendmentPayload
    | DeleteRowProseAmendmentPayload
    | AppendRowProseAmendmentPayload
)


@dataclass(frozen=True)
class ReplaceRowProseAmendment:
    """Replace exactly one context-issued row-owned prose span."""

    row_id: str
    span_id: str
    replacement: str


@dataclass(frozen=True)
class DeleteRowProseAmendment:
    """Delete exactly one context-issued row-owned prose span."""

    row_id: str
    span_id: str


@dataclass(frozen=True)
class AppendRowProseAmendment:
    """Append one prose fragment associated with a newly added row."""

    row_id: str
    fragment: str


RowProseAmendment: TypeAlias = (
    ReplaceRowProseAmendment | DeleteRowProseAmendment | AppendRowProseAmendment
)


class AddRowOperationPayload(_StageWireModel):
    op: Literal["add-row"]
    feedback_id: str
    row_type: str
    row: object
    prose_amendment: AppendRowProseAmendmentPayload | None = None
    ordering: OrderingEntryPayload | None = None


class EditRowOperationPayload(_StageWireModel):
    op: Literal["edit-row"]
    feedback_id: str
    row_type: str
    row_id: str
    row: object
    prose_amendment: ReplaceRowProseAmendmentPayload | None = None


class RemoveRowWithRecordOperationPayload(_StageWireModel):
    op: Literal["remove-row-with-record"]
    feedback_id: str
    row_type: str
    row_id: str
    removal_record: RemovalRecordPayload
    prose_amendment: DeleteRowProseAmendmentPayload | None = None


class StageRespondFeedbackOperationPayload(_StageWireModel):
    op: Literal["respond-feedback"]
    feedback_id: str
    proposed_response: str


StageOperationPayload: TypeAlias = (
    AddRowOperationPayload
    | EditRowOperationPayload
    | RemoveRowWithRecordOperationPayload
    | StageRespondFeedbackOperationPayload
)


class _StageRevisionEnvelope(_StageWireModel):
    """Closed stage root; concrete records select through ``op``."""

    operations: list[
        Annotated[
            AddRowOperationPayload
            | EditRowOperationPayload
            | RemoveRowWithRecordOperationPayload
            | StageRespondFeedbackOperationPayload,
            Field(discriminator="op"),
        ]
    ]


@dataclass(frozen=True)
class AddRowOperation:
    """One typed row addition, optionally with its required plan ordering slot."""

    feedback_id: str
    row_type: StageRowType
    row: StageRow
    prose_amendment: AppendRowProseAmendment | None
    ordering: OrderingEntry | None
    op: Literal["add-row"] = "add-row"


@dataclass(frozen=True)
class EditRowOperation:
    """One typed replacement of an existing row without relation authority."""

    feedback_id: str
    row_type: StageRowType
    row_id: str
    row: StageRow
    prose_amendment: ReplaceRowProseAmendment | None
    op: Literal["edit-row"] = "edit-row"


@dataclass(frozen=True)
class RemoveRowWithRecordOperation:
    """One typed live-row removal with its continuity record."""

    feedback_id: str
    row_type: StageRowType
    row_id: str
    removal_record: RemovalRecord
    prose_amendment: DeleteRowProseAmendment | None
    op: Literal["remove-row-with-record"] = "remove-row-with-record"


@dataclass(frozen=True)
class StageRespondFeedbackOperation:
    """The proposed response for one active predecessor feedback item."""

    feedback_id: str
    proposed_response: str
    op: Literal["respond-feedback"] = "respond-feedback"


StageMaterialOperation: TypeAlias = (
    AddRowOperation | EditRowOperation | RemoveRowWithRecordOperation
)
StageOperation: TypeAlias = StageMaterialOperation | StageRespondFeedbackOperation


@dataclass(frozen=True)
class StageFeedbackAuthority:
    """One active feedback id and its closed material-operation authority."""

    feedback_id: str
    allow_add: bool = False
    target_row_id: str | None = None
    target_row_type: StageRowType | None = None
    allow_edit: bool = False
    allow_remove: bool = False
    target: FeedbackTarget | None = None
    request: str = ""

    @property
    def allowed_operation_kinds(self) -> tuple[str, ...]:
        """Return the closed operation vocabulary admitted for this request."""
        return tuple(
            operation
            for operation, allowed in (
                ("add-row", self.allow_add),
                ("edit-row", self.allow_edit),
                ("remove-row-with-record", self.allow_remove),
                ("respond-feedback", True),
            )
            if allowed
        )


@dataclass(frozen=True)
class StageLiveRow:
    """One context-selected existing row and its immutable stage facts."""

    row_type: StageRowType
    row: StageRow
    prose_span_id: str | None = None

    @property
    def row_id(self) -> str:
        return self.row.id


@dataclass(frozen=True)
class StageProseSpan:
    """One context-issued, row-owned source block without its surrounding body.

    A shared block carries every live row it names in ``owning_row_ids`` (sorted);
    ``row_id`` is the first of them.  A single-owner span owns only ``row_id``.
    """

    row_id: str
    span_id: str
    text: str
    start: int
    end: int
    owning_row_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.owning_row_ids:
            object.__setattr__(self, "owning_row_ids", (self.row_id,))

    @property
    def is_shared(self) -> bool:
        return len(self.owning_row_ids) > 1


@dataclass(frozen=True)
class StageRevisionContext:
    """The bounded source facts a later stage-context builder supplies."""

    artifact_key: StageArtifactKey
    active_feedback: tuple[StageFeedbackAuthority, ...]
    live_rows: tuple[StageLiveRow, ...]
    predecessor_relation_ids: frozenset[str]
    predecessor_plan_ids: tuple[str, ...]
    carried_removal_ids: frozenset[str] = frozenset()
    inherited_decision_ids: frozenset[str] = frozenset()
    limits: StageFeedbackLimits = StageFeedbackLimits()
    relations: tuple[RoadmapRelation, ...] = ()
    prose_spans: tuple[StageProseSpan, ...] = ()
    ordering_entries: tuple[OrderingEntry, ...] = ()

    @property
    def predecessor_reference_ids(self) -> frozenset[str]:
        """Return the frozen ids every added relation may name."""
        return self.predecessor_relation_ids

    @property
    def incident_relations(self) -> tuple[RoadmapRelation, ...]:
        """Return selected live rows' ordered incoming and outgoing relations."""
        return self.relations


def build_stage_revision_context(
    artifact: Artifact,
    upstream_artifacts: Mapping[StageArtifactKey, Artifact] | Sequence[Artifact] = (),
    limits: StageFeedbackLimits = StageFeedbackLimits(),
    *,
    artifact_key: StageArtifactKey | None = None,
) -> StageRevisionContext:
    """Project one stage's active revision facts without retaining artifact text."""
    actual_key = _stage_artifact_key(artifact)
    if artifact_key is not None and artifact_key != actual_key:
        raise RevisionContractError(
            f"stage artifact key {artifact_key!r} does not match its typed artifact"
        )
    ordered_upstream = _ordered_upstream_artifacts(actual_key, upstream_artifacts)
    all_artifacts = (*ordered_upstream, (actual_key, artifact))
    live_rows = _stage_rows_by_collection(artifact)
    live_by_id: dict[str, list[tuple[StageRowType, StageRow]]] = {}
    for row_type, row in live_rows:
        live_by_id.setdefault(row.id, []).append((row_type, row))
    removals_by_id: dict[str, list[RemovalRecord]] = {}
    for removal in artifact.removals:
        removals_by_id.setdefault(removal.removed_id, []).append(removal)

    _validate_stage_feedback_targets(artifact.feedback, live_by_id, removals_by_id)
    active_feedback: list[StageFeedbackAuthority] = []
    selected_live_ids: set[str] = set()
    for feedback in artifact.feedback:
        if feedback.state is not FeedbackState.OPEN:
            continue
        if feedback.target.kind is FeedbackTargetKind.ARTIFACT:
            active_feedback.append(
                StageFeedbackAuthority(
                    feedback.id,
                    allow_add=True,
                    target=feedback.target,
                    request=feedback.request,
                )
            )
            continue

        assert feedback.target.row_id is not None
        target_id = feedback.target.row_id
        live_matches = live_by_id.get(target_id, [])
        if live_matches:
            row_type, _row = live_matches[0]
            selected_live_ids.add(target_id)
            active_feedback.append(
                StageFeedbackAuthority(
                    feedback.id,
                    target_row_id=target_id,
                    target_row_type=row_type,
                    allow_edit=True,
                    allow_remove=stage_row_operation_policy(row_type).allow_remove,
                    target=feedback.target,
                    request=feedback.request,
                )
            )
            continue

        active_feedback.append(
            StageFeedbackAuthority(
                feedback.id,
                target=feedback.target,
                request=feedback.request,
            )
        )

    spans = _select_row_owned_prose_spans(
        artifact.body,
        all_live_ids=frozenset(live_by_id),
        selected_rows=(
            (row_type, row) for row_type, row in live_rows if row.id in selected_live_ids
        ),
    )
    span_ids = {span.row_id: span.span_id for span in spans}
    active_feedback = [
        replace(authority, allow_edit=False, allow_remove=False)
        if (
            authority.target_row_id is not None
            and authority.target_row_type is not None
            and authority.target_row_id not in span_ids
            and stage_row_operation_policy(authority.target_row_type).allow_prose
        )
        else authority
        for authority in active_feedback
    ]
    selected_live_rows = tuple(
        StageLiveRow(row_type, row, span_ids.get(row.id))
        for row_type, row in live_rows
        if row.id in selected_live_ids
    )
    predecessor_ids = frozenset(
        row.id
        for _key, context_artifact in all_artifacts
        for _row_type, row in _stage_rows_by_collection(context_artifact)
    )
    carried_removal_ids = frozenset(
        removal.removed_id
        for _key, context_artifact in all_artifacts
        for removal in context_artifact.removals
    )
    inherited_decision_ids = frozenset(
        row.id
        for row_type, row in live_rows
        if row_type == "decisions" and isinstance(row, DecisionRow) and row.source is not None
    )
    relations = select_declared_relations_for_ids(
        _extract_context_relations(all_artifacts), selected_live_ids
    )
    predecessor_plan_ids = (
        tuple(row.id for row in artifact.plans) if isinstance(artifact, PlansArtifact) else ()
    )
    ordering_entries = artifact.ordering if isinstance(artifact, PlansArtifact) else ()
    context = StageRevisionContext(
        artifact_key=actual_key,
        active_feedback=tuple(active_feedback),
        live_rows=selected_live_rows,
        predecessor_relation_ids=predecessor_ids,
        predecessor_plan_ids=predecessor_plan_ids,
        carried_removal_ids=carried_removal_ids,
        inherited_decision_ids=inherited_decision_ids,
        limits=limits,
        relations=relations,
        prose_spans=spans,
        ordering_entries=ordering_entries,
    )
    _validate_stage_context(context)
    return context


def _stage_artifact_key(artifact: Artifact) -> StageArtifactKey:
    """Return the relation-stage key that belongs to one typed artifact."""
    try:
        return ARTIFACT_KEY_BY_TYPE[type(artifact)]  # type: ignore[return-value]
    except KeyError as exc:
        raise RevisionContractError("unsupported stage artifact type") from exc


def _ordered_upstream_artifacts(
    current_key: StageArtifactKey,
    upstream_artifacts: Mapping[StageArtifactKey, Artifact] | Sequence[Artifact],
) -> tuple[tuple[StageArtifactKey, Artifact], ...]:
    """Normalize typed upstream artifacts and refuse current or downstream input."""
    current_index = ARTIFACT_KEYS.index(current_key)
    if isinstance(upstream_artifacts, Mapping):
        pairs = tuple(
            (key, artifact)
            for key in ARTIFACT_KEYS[:current_index]
            if (artifact := upstream_artifacts.get(key)) is not None
        )
        unexpected = set(upstream_artifacts) - set(ARTIFACT_KEYS[:current_index])
        if unexpected:
            raise RevisionContractError(
                "stage context may not use current or downstream artifacts: "
                + ", ".join(repr(key) for key in sorted(unexpected))
            )
    else:
        pairs = tuple((_stage_artifact_key(artifact), artifact) for artifact in upstream_artifacts)
        expected_order = tuple(key for key, _artifact in pairs)
        if expected_order != tuple(sorted(expected_order, key=ARTIFACT_KEYS.index)):
            raise RevisionContractError("upstream artifacts must be in stage order")

    keys = tuple(key for key, _artifact in pairs)
    if len(keys) != len(set(keys)):
        raise RevisionContractError("stage context upstream artifacts must be unique")
    for key, artifact in pairs:
        if key not in ARTIFACT_KEYS[:current_index]:
            raise RevisionContractError(
                f"stage context may not use {key!r} from this stage or downstream"
            )
        if _stage_artifact_key(artifact) != key:
            raise RevisionContractError(
                f"upstream artifact {key!r} does not match its typed artifact"
            )
    return pairs  # type: ignore[return-value]


def _stage_rows_by_collection(
    artifact: Artifact,
) -> tuple[tuple[StageRowType, StageRow], ...]:
    """Return every live stage row, including identity-only rows."""
    return tuple(
        (collection, row)
        for collection, collection_rows in stage_row_collections(artifact).items()
        for row in collection_rows
    )  # type: ignore[return-value]


def _validate_stage_feedback_targets(
    feedback: tuple[FeedbackRow, ...],
    live_by_id: Mapping[str, list[tuple[StageRowType, StageRow]]],
    removals_by_id: Mapping[str, list[RemovalRecord]],
) -> None:
    """Require every retained row target to resolve to exactly one current fact."""
    counts: dict[str, int] = {}
    for row in feedback:
        counts[row.id] = counts.get(row.id, 0) + 1
    duplicates = sorted(row_id for row_id, count in counts.items() if count > 1)
    if duplicates:
        raise RevisionContractError(
            "retained feedback ids must be unique: "
            + ", ".join(repr(row_id) for row_id in duplicates)
        )
    for row in feedback:
        if row.target.kind is FeedbackTargetKind.ARTIFACT:
            continue
        if row.target.row_id is None:
            raise RevisionContractError(f"feedback {row.id!r} has no target row id")
        target_id = row.target.row_id
        matches = len(live_by_id.get(target_id, ())) + len(removals_by_id.get(target_id, ()))
        if matches != 1:
            raise RevisionContractError(
                f"feedback {row.id!r} must target exactly one live row or recorded "
                f"removal, found {matches} for {target_id!r}"
            )


def _extract_context_relations(
    artifacts: Sequence[tuple[StageArtifactKey, Artifact]],
) -> tuple[RoadmapRelation, ...]:
    """Extract the current/upstream relation inventory in stage order."""
    by_key = dict(artifacts)
    return extract_declared_relations(
        domain=by_key.get("domain"),  # type: ignore[arg-type]
        constraints=by_key.get("constraints"),  # type: ignore[arg-type]
        components=by_key.get("components"),  # type: ignore[arg-type]
        plans=by_key.get("plans"),  # type: ignore[arg-type]
    )


def _select_row_owned_prose_spans(
    body: str,
    *,
    all_live_ids: frozenset[str],
    selected_rows: Collection[tuple[StageRowType, StageRow]],
) -> tuple[StageProseSpan, ...]:
    """Issue spans only for blank-line blocks owned by one selected row."""
    blocks = _prose_blocks(body)
    if len(blocks) < 2:
        return ()
    spans: list[StageProseSpan] = []
    issued_ranges: list[tuple[int, int]] = []
    for row_type, row in selected_rows:
        if not stage_row_operation_policy(row_type).allow_prose:
            continue
        for match in blocks:
            text = match.group(0)
            if not contains_whole_row_id(text, row.id):
                continue
            if any(
                other_id != row.id and contains_whole_row_id(text, other_id)
                for other_id in all_live_ids
            ):
                continue
            start, end = match.span()
            if any(
                start < other_end and other_start < end for other_start, other_end in issued_ranges
            ):
                continue
            spans.append(
                StageProseSpan(
                    row.id,
                    stage_prose_span_id(row.id, text),
                    text,
                    start,
                    end,
                )
            )
            issued_ranges.append((start, end))
            break
    return tuple(spans)


# A selector capsule repeats a shared span once per owner (a batch capsule issues it once),
# and the correction replacement ceiling (roadmap_candidate.CORRECT_PROSE_MAX_REPLACEMENT_BYTES)
# cannot re-express a larger block, so a larger shared block is not issued.
SHARED_SPAN_MAX_BYTES: Final[int] = 4 * 1024


def project_row_owned_prose_spans(
    artifact: Artifact, selected_row_ids: Collection[str]
) -> tuple[StageProseSpan, ...]:
    """Return every blank-line block owned by visible live rows, in source order.

    A block naming several live rows is one shared span bound to all of them,
    issued only when each is selected and unambiguous.  A removed-row reference
    is not a live row, so it neither joins nor is required of the owning set.
    This projection is read-only.  The local revision context deliberately
    retains its narrower first-block, prose-editable-row selection above.
    """
    selected_ids = frozenset(selected_row_ids)
    if not selected_ids:
        return ()
    live_counts: dict[str, int] = {}
    for _row_type, row in _design_rows_by_collection(artifact):
        live_counts[row.id] = live_counts.get(row.id, 0) + 1

    spans: list[StageProseSpan] = []
    for match in _prose_blocks(artifact.body):
        text = match.group(0)
        owners = tuple(
            sorted(row_id for row_id in live_counts if contains_whole_row_id(text, row_id))
        )
        if not owners:
            continue
        if any(live_counts[row_id] != 1 or row_id not in selected_ids for row_id in owners):
            continue
        if len(owners) > 1 and len(text.encode("utf-8")) > SHARED_SPAN_MAX_BYTES:
            continue
        start, end = match.span()
        spans.append(
            StageProseSpan(
                owners[0],
                stage_prose_span_id(owners[0], text, owning_row_ids=owners),
                text,
                start,
                end,
                owners,
            )
        )
    return tuple(spans)


def _prose_blocks(body: str) -> tuple[re.Match[str], ...]:
    """Return non-blank, blank-line-delimited source blocks in body order."""
    return tuple(re.finditer(r"(?ms)^(?![ \t]*$).+?(?=^[ \t]*$|\Z)", body))


def contains_whole_row_id(text: str, row_id: str) -> bool:
    """Match an id without admitting an identifier that merely contains it."""
    token = re.escape(row_id)
    return re.search(rf"(?<![\w-]){token}(?![\w-])", text) is not None


def stage_prose_span_id(
    row_id: str, text: str, *, owning_row_ids: Sequence[str] = ()
) -> str:
    """Bind an opaque token to the exact owning rows and source text it authorizes.

    A single owner keeps the ``row_id``-and-text binding; a shared span binds its
    whole sorted owning set, so editing the set changes the id.
    """
    owners = sorted(owning_row_ids)
    if len(owners) > 1:
        key = "\n".join(owners)
        digest = hashlib.sha256(f"shared\0{key}\0{text}".encode("utf-8")).hexdigest()
    else:
        digest = hashlib.sha256(f"{row_id}\0{text}".encode("utf-8")).hexdigest()
    return f"row-prose-{digest}"


@dataclass(frozen=True)
class StageRevisionOperations:
    """The material prefix and complete ordered response suffix of one reply."""

    material_operations: tuple[StageMaterialOperation, ...]
    responses: tuple[StageRespondFeedbackOperation, ...]

    @property
    def operations(self) -> tuple[StageOperation, ...]:
        return (*self.material_operations, *self.responses)


def parse_stage_revision_operations(
    response_text: str, context: StageRevisionContext
) -> StageRevisionOperations:
    """Parse and bind one closed stage envelope before a merge can inspect it."""
    _validate_stage_context(context)
    if not isinstance(response_text, str):
        raise RevisionContractError("stage response must be text")
    raw_size = len(response_text.encode("utf-8"))
    if raw_size > context.limits.max_response_bytes:
        raise StageRevisionLimitError(
            label="stage response",
            measured=raw_size,
            limit=context.limits.max_response_bytes,
        )
    payload = _decode_single_json_object(response_text)
    try:
        envelope = _StageRevisionEnvelope.model_validate(payload)
    except PydanticValidationError as exc:
        raise RevisionContractError(f"invalid stage revision operation envelope: {exc}") from exc

    authorities = {item.feedback_id: item for item in context.active_feedback}
    live_rows = {item.row_id: item for item in context.live_rows}
    material: list[StageMaterialOperation] = []
    responses: list[StageRespondFeedbackOperation] = []
    saw_response = False
    material_feedback_counts: dict[str, int] = {}
    material_row_ids: set[str] = set()

    for wire in envelope.operations:
        if isinstance(wire, StageRespondFeedbackOperationPayload):
            saw_response = True
            responses.append(_bind_stage_response(wire, authorities))
            continue
        if saw_response:
            raise RevisionContractError(
                "stage material operations must appear before feedback responses"
            )
        material_count = material_feedback_counts.get(wire.feedback_id, 0) + 1
        if material_count > STAGE_MAX_MATERIAL_OPERATIONS_PER_FEEDBACK:
            raise StageRevisionLimitError(
                label="material operations",
                measured=material_count,
                limit=STAGE_MAX_MATERIAL_OPERATIONS_PER_FEEDBACK,
                feedback_id=wire.feedback_id,
            )
        operation = _bind_material_operation(
            wire, context, authorities, live_rows, material_row_ids
        )
        material_feedback_counts[operation.feedback_id] = material_count
        target_row_id = (
            operation.row.id if isinstance(operation, AddRowOperation) else operation.row_id
        )
        if target_row_id in material_row_ids:
            raise RevisionContractError(
                f"stage row {target_row_id!r} already has a material operation in this envelope"
            )
        material_row_ids.add(target_row_id)
        material.append(operation)

    _validate_stage_response_coverage(responses, context.active_feedback)
    return StageRevisionOperations(tuple(material), tuple(responses))


def _validate_stage_context(context: StageRevisionContext) -> None:
    limits = context.limits
    if (
        limits.max_active_feedback_items > STAGE_MAX_ACTIVE_FEEDBACK_ITEMS
        or limits.max_response_bytes > STAGE_MAX_RESPONSE_BYTES
        or limits.max_prose_amendment_bytes > STAGE_MAX_PROSE_AMENDMENT_BYTES
        or limits.max_active_feedback_items < 1
        or limits.max_response_bytes < 1
        or limits.max_prose_amendment_bytes < 1
        or limits.max_prose_amendment_bytes > limits.max_response_bytes
    ):
        raise RevisionContractError("stage feedback limits exceed the closed hard ceilings")
    if len(context.active_feedback) > limits.max_active_feedback_items:
        raise StageRevisionLimitError(
            label="active feedback items",
            measured=len(context.active_feedback),
            limit=limits.max_active_feedback_items,
        )
    feedback_ids = [item.feedback_id for item in context.active_feedback]
    if len(feedback_ids) != len(set(feedback_ids)):
        raise RevisionContractError("stage context active feedback ids must be unique")
    row_ids = [item.row_id for item in context.live_rows]
    if len(row_ids) != len(set(row_ids)):
        raise RevisionContractError("stage context live row ids must be unique")


def _bind_stage_response(
    wire: StageRespondFeedbackOperationPayload,
    authorities: Mapping[str, StageFeedbackAuthority],
) -> StageRespondFeedbackOperation:
    if wire.feedback_id not in authorities:
        raise RevisionContractError(f"stage response names inactive feedback {wire.feedback_id!r}")
    _require_trimmed_text(wire.proposed_response, "stage proposed response")
    return StageRespondFeedbackOperation(wire.feedback_id, wire.proposed_response)


def _bind_material_operation(
    wire: AddRowOperationPayload | EditRowOperationPayload | RemoveRowWithRecordOperationPayload,
    context: StageRevisionContext,
    authorities: Mapping[str, StageFeedbackAuthority],
    live_rows: Mapping[str, StageLiveRow],
    material_row_ids: set[str],
) -> StageMaterialOperation:
    authority = authorities.get(wire.feedback_id)
    if authority is None:
        raise RevisionContractError(
            f"stage material operation names inactive feedback {wire.feedback_id!r}"
        )
    if isinstance(wire, AddRowOperationPayload):
        return _bind_add_operation(wire, context, authority)
    if isinstance(wire, EditRowOperationPayload):
        return _bind_edit_operation(wire, context, authority, live_rows, material_row_ids)
    return _bind_remove_operation(wire, authority, live_rows, material_row_ids)


def _bind_add_operation(
    wire: AddRowOperationPayload,
    context: StageRevisionContext,
    authority: StageFeedbackAuthority,
) -> AddRowOperation:
    if not authority.allow_add:
        raise RevisionContractError(
            f"feedback {wire.feedback_id!r} does not authorize a row addition"
        )
    row_type = _stage_row_type(wire.row_type)
    if not stage_row_operation_policy(row_type).allow_add:
        raise RevisionContractError(f"{row_type} rows are never addable")
    if row_type not in _STAGE_ADD_ROW_TYPES[context.artifact_key]:
        raise RevisionContractError(
            f"row type {row_type!r} is not addable for {context.artifact_key!r}"
        )
    row = _decode_row_payload(wire.row, row_type)
    if row_type == "decisions" and row.id in context.inherited_decision_ids:
        raise RevisionContractError(f"inherited decision {row.id!r} cannot be added by feedback")
    _validate_stage_row(row, row_type)
    if row.id in context.predecessor_relation_ids:
        raise RevisionContractError(
            f"added row id {row.id!r} already names a frozen live row"
        )
    if row.id in context.carried_removal_ids:
        raise RevisionContractError(f"added row id {row.id!r} names a carried removal")
    _validate_added_row_relations(row, context.predecessor_relation_ids)
    prose = _bind_add_prose(wire.prose_amendment, row, row_type, context.limits, wire.feedback_id)
    ordering = wire.ordering.to_row() if wire.ordering is not None else None
    policy = stage_row_operation_policy(row_type)
    _validate_ordering_companion(row_type, row, ordering, context.predecessor_plan_ids)
    if not policy.requires_ordering_companion and ordering is not None:
        raise RevisionContractError("only an added plan row may carry an ordering companion")
    return AddRowOperation(wire.feedback_id, row_type, row, prose, ordering)


def _bind_edit_operation(
    wire: EditRowOperationPayload,
    context: StageRevisionContext,
    authority: StageFeedbackAuthority,
    live_rows: Mapping[str, StageLiveRow],
    material_row_ids: set[str],
) -> EditRowOperation:
    if not authority.allow_edit:
        raise RevisionContractError(f"feedback {wire.feedback_id!r} does not authorize a row edit")
    row_type = _stage_row_type(wire.row_type)
    target = _resolve_live_target(wire.row_id, row_type, authority, live_rows, material_row_ids)
    if row_type == "decisions" and isinstance(target.row, DecisionRow) and target.row.source is not None:
        raise RevisionContractError(f"inherited decision {target.row_id!r} cannot be edited by feedback")
    row = _decode_row_payload(wire.row, row_type)
    row = _preserve_omitted_row_metadata(target.row, row, wire.row)
    _validate_stage_row(row, row_type)
    if row.id != wire.row_id:
        raise RevisionContractError("stage row edit payload id must match its live row_id")
    _validate_unchanged_relations(target.row, row)
    if not stage_row_edit_preserves_fixed_fields(target.row, row, row_type=row_type):
        raise RevisionContractError(_fixed_field_edit_message(row_type))
    prose = _bind_edit_prose(
        wire.prose_amendment, target, row_type, context.limits, wire.feedback_id
    )
    return EditRowOperation(wire.feedback_id, row_type, wire.row_id, row, prose)


def _fixed_field_edit_message(row_type: str) -> str:
    fixed = ", ".join(repr(field) for field in stage_row_operation_policy(row_type).immutable_fields)
    return f"a {row_type} edit must preserve its fixed field {fixed}"


def _bind_remove_operation(
    wire: RemoveRowWithRecordOperationPayload,
    authority: StageFeedbackAuthority,
    live_rows: Mapping[str, StageLiveRow],
    material_row_ids: set[str],
) -> RemoveRowWithRecordOperation:
    if not authority.allow_remove:
        raise RevisionContractError(
            f"feedback {wire.feedback_id!r} does not authorize a row removal"
        )
    row_type = _stage_row_type(wire.row_type)
    target = _resolve_live_target(wire.row_id, row_type, authority, live_rows, material_row_ids)
    if row_type == "decisions" and isinstance(target.row, DecisionRow) and target.row.source is not None:
        raise RevisionContractError(f"inherited decision {target.row_id!r} cannot be removed by feedback")
    if not stage_row_operation_policy(row_type).allow_remove:
        raise RevisionContractError(f"{row_type} rows are never removable")
    record = wire.removal_record.to_row()
    _validate_removal_record(record)
    if record.removed_id != target.row_id:
        raise RevisionContractError("removal record removed_id must match its live row_id")
    if wire.feedback_id not in record.feedback_ids:
        raise RevisionContractError("removal record must cite its authorizing feedback id")
    prose = _bind_remove_prose(wire.prose_amendment, target, row_type, wire.feedback_id)
    return RemoveRowWithRecordOperation(wire.feedback_id, row_type, wire.row_id, record, prose)


def _resolve_live_target(
    row_id: str,
    row_type: StageRowType,
    authority: StageFeedbackAuthority,
    live_rows: Mapping[str, StageLiveRow],
    material_row_ids: set[str],
) -> StageLiveRow:
    if row_id in material_row_ids:
        raise RevisionContractError(
            f"stage row {row_id!r} already has a material operation in this envelope"
        )
    if authority.target_row_id != row_id or authority.target_row_type != row_type:
        raise RevisionContractError(
            f"feedback {authority.feedback_id!r} does not authorize row {row_id!r}"
        )
    target = live_rows.get(row_id)
    if target is None:
        raise RevisionContractError(f"stage row {row_id!r} is not a live context row")
    if target.row_type != row_type:
        raise RevisionContractError(f"stage row {row_id!r} has a different row type")
    return target


def _stage_row_type(value: str) -> StageRowType:
    if value not in _PAYLOAD_BY_ROW_TYPE:
        raise RevisionContractError(f"unknown stage row type: {value!r}")
    return value  # type: ignore[return-value]


def _decode_row_payload(raw: object, row_type: StageRowType) -> StageRow:
    if not isinstance(raw, dict):
        raise RevisionContractError(f"{row_type!r} row payload must be a JSON object")
    payload_type = _PAYLOAD_BY_ROW_TYPE[row_type]
    try:
        payload = payload_type.model_validate(raw)
    except PydanticValidationError as exc:
        raise RevisionContractError(f"invalid {row_type!r} row payload: {exc}") from exc
    return payload.to_row()


def _preserve_omitted_row_metadata(
    existing: StageRow, replacement: StageRow, raw: dict[str, object]
) -> StageRow:
    """Omission keeps row metadata; explicit null clears its stored value."""
    if isinstance(existing, HostingRow) and isinstance(replacement, HostingRow):
        return replace(
            replacement,
            **{
                field: getattr(existing, field)
                for field in ("product", "description", "research_disclosure")
                if field not in raw
            },
        )
    if isinstance(existing, StoreRow) and isinstance(replacement, StoreRow):
        return replace(
            replacement,
            **{
                field: getattr(existing, field)
                for field in ("product", "description", "research_disclosure")
                if field not in raw
            },
        )
    return replacement


def _validate_stage_row(row: StageRow, row_type: StageRowType) -> None:
    _require_nonblank(row.id, f"{row_type} row id")
    for relation_id in declared_relation_ids_for_row(row):
        _require_nonblank(relation_id, f"{row_type} relation id")
    if isinstance(row, EntityRow):
        for field in row.fields:
            _require_nonblank(field.name, "field name")
    if isinstance(row, PlanRow):
        _validate_draft_seed_path(row.draft_seed_path)


def _validate_draft_seed_path(value: str) -> None:
    if not value or value.startswith(("/", "\\")):
        raise RevisionContractError("plan draft_seed_path must be a non-empty relative path")
    parts = value.replace("\\", "/").split("/")
    if ".." in parts or not parts or parts[0] not in {"plan-seed-drafts", "seeds"}:
        raise RevisionContractError(
            "plan draft_seed_path must remain below plan-seed-drafts/ or seeds/"
        )


def _validate_added_row_relations(row: StageRow, predecessor_ids: frozenset[str]) -> None:
    missing = sorted(set(declared_relation_ids_for_row(row)) - predecessor_ids)
    if missing:
        raise RevisionContractError(
            "added row relations must name frozen predecessor ids only: "
            + ", ".join(repr(item) for item in missing)
        )


def _validate_unchanged_relations(existing: StageRow, replacement: StageRow) -> None:
    if not same_declared_row_relations(existing, replacement):
        raise RevisionContractError("a stage row edit must preserve every declared relation")


def _bind_add_prose(
    payload: AppendRowProseAmendmentPayload | None,
    row: StageRow,
    row_type: StageRowType,
    limits: StageFeedbackLimits,
    feedback_id: str,
) -> AppendRowProseAmendment | None:
    if not stage_row_operation_policy(row_type).allow_prose:
        if payload is not None:
            raise RevisionContractError(f"{row_type} rows cannot carry a prose amendment")
        return None
    if payload is None:
        raise RevisionContractError(
            f"{row_type} row additions require one row-owned prose amendment"
        )
    if payload.row_id != row.id:
        raise RevisionContractError("appended prose amendment must name its added row id")
    _require_nonblank(payload.fragment, "appended prose amendment fragment")
    if not contains_whole_row_id(payload.fragment, row.id):
        raise RevisionContractError("appended prose amendment fragment must name its added row id")
    _validate_prose_bytes(payload.fragment, limits, feedback_id)
    return AppendRowProseAmendment(payload.row_id, payload.fragment)


def _bind_edit_prose(
    payload: ReplaceRowProseAmendmentPayload | None,
    target: StageLiveRow,
    row_type: StageRowType,
    limits: StageFeedbackLimits,
    feedback_id: str,
) -> ReplaceRowProseAmendment | None:
    if not stage_row_operation_policy(row_type).allow_prose:
        if payload is not None:
            raise RevisionContractError(f"{row_type} rows cannot carry a prose amendment")
        return None
    if payload is None:
        raise RevisionContractError(f"{row_type} row edits require one row-owned prose amendment")
    if payload.row_id != target.row_id or payload.span_id != target.prose_span_id:
        raise RevisionContractError("row prose amendment must name its context-issued row span")
    _require_nonblank(payload.replacement, "row prose replacement")
    if not contains_whole_row_id(payload.replacement, target.row_id):
        raise RevisionContractError("row prose replacement must name its edited row id")
    _validate_prose_bytes(payload.replacement, limits, feedback_id)
    return ReplaceRowProseAmendment(payload.row_id, payload.span_id, payload.replacement)


def _bind_remove_prose(
    payload: DeleteRowProseAmendmentPayload | None,
    target: StageLiveRow,
    row_type: StageRowType,
    feedback_id: str,
) -> DeleteRowProseAmendment | None:
    if not stage_row_operation_policy(row_type).allow_prose:
        if payload is not None:
            raise RevisionContractError(f"{row_type} rows cannot carry a prose amendment")
        return None
    if payload is None:
        raise RevisionContractError(
            f"{row_type} row removals require one row-owned prose amendment"
        )
    if payload.row_id != target.row_id or payload.span_id != target.prose_span_id:
        raise RevisionContractError("row prose amendment must name its context-issued row span")
    return DeleteRowProseAmendment(payload.row_id, payload.span_id)


def _validate_prose_bytes(value: str, limits: StageFeedbackLimits, feedback_id: str) -> None:
    measured = len(value.encode("utf-8"))
    if measured > limits.max_prose_amendment_bytes:
        raise StageRevisionLimitError(
            label="row prose amendment",
            measured=measured,
            limit=limits.max_prose_amendment_bytes,
            feedback_id=feedback_id,
        )


def _validate_ordering_companion(
    row_type: StageRowType,
    row: StageRow,
    ordering: OrderingEntry | None,
    predecessor_plan_ids: tuple[str, ...],
) -> None:
    if not stage_row_operation_policy(row_type).requires_ordering_companion:
        return
    assert isinstance(row, PlanRow)
    if ordering is None:
        raise RevisionContractError("an added plan row requires exactly one ordering companion")
    if ordering.plan_id != row.id:
        raise RevisionContractError("plan ordering companion must name the added plan id")
    allowed = set(predecessor_plan_ids)
    invalid = sorted(set((*ordering.depends_on, *ordering.assumption_targets)) - allowed)
    if invalid:
        raise RevisionContractError(
            "plan ordering companion may name only earlier predecessor plan ids: "
            + ", ".join(repr(item) for item in invalid)
        )


def _validate_removal_record(record: RemovalRecord) -> None:
    _require_nonblank(record.removed_id, "removal record removed_id")
    _require_nonblank(record.rationale, "removal record rationale")
    if not record.feedback_ids:
        raise RevisionContractError("removal record must cite at least one feedback id")
    for feedback_id in record.feedback_ids:
        _require_nonblank(feedback_id, "removal record feedback id")


def _validate_stage_response_coverage(
    responses: list[StageRespondFeedbackOperation],
    authorities: tuple[StageFeedbackAuthority, ...],
) -> None:
    expected = tuple(item.feedback_id for item in authorities)
    actual = tuple(item.feedback_id for item in responses)
    if actual != expected:
        raise RevisionContractError(
            "stage responses must contain exactly one response for each active "
            "feedback id in predecessor order"
        )


def _require_nonblank(value: str, label: str) -> None:
    if not value.strip():
        raise RevisionContractError(f"{label} must be a non-blank string")
