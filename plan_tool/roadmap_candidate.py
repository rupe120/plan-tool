"""Pure assembly of one capsule-authorized immutable roadmap candidate."""

from __future__ import annotations

import enum
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence, Set
from dataclasses import fields, is_dataclass, replace
from typing import Final, Literal, NamedTuple, TypeAlias, cast

from pydantic import BaseModel, ConfigDict, model_validator

from plan_tool.roadmap import STAGES, RoadmapStage
from plan_tool.roadmap_artifacts import (
    AssumptionRow,
    AttributeDispositionRow,
    BusinessRuleRow,
    ComponentRow,
    ConstraintDisposition,
    ConstraintRow,
    ConstraintsArtifact,
    DecisionRow,
    DecisionStatus,
    EntityRow,
    FieldRow,
    FieldType,
    HostingRow,
    OrderingEntry,
    PatternRow,
    PlanDisposition,
    PlanRow,
    PlansArtifact,
    RejectedAlternative,
    ResearchDisclosure,
    RoadmapArtifact,
    RoadmapArtifactError,
    REVIEW_ROW_KEYS,
    StackRow,
    StageRow,
    StoreRow,
    WorkflowRow,
    append_plan_ordering_entry,
    append_stage_row,
    remove_plan_ordering_entry,
    remove_stage_row,
    replace_stage_row,
    stage_row_edit_preserves_fixed_fields,
    stage_row_operation_policy,
    stage_row_collections,
)
from plan_tool.roadmap_candidate_context import (
    CandidateContextBatchCapsule,
    CandidateContextBatchReceipt,
    CandidateContextCapsule,
    CandidateContextFeedback,
    CandidateContextFullMember,
    CandidateContextReceipt,
    CandidateContextSourceSpan,
    expand_candidate_context,
    rebuild_candidate_context_at_recorded_ceiling,
)
from plan_tool.roadmap_feedback import is_receipt_safe_id
from plan_tool.roadmap_feedback_ledger import ReviewerItemSnapshot
from plan_tool.roadmap_diff import (
    CandidatePredecessorDiff,
    artifact_row_diffs as _artifact_row_diffs,
    build_roadmap_diff as _build_predecessor_diff,
    ordered_stage_collections as _ordered_stage_collections,
    relation_occurrence_diffs,
)
from plan_tool.roadmap_impact_snapshot import (
    CompleteRoadmapGateEvidence,
    RoadmapGateOutcome,
    RoadmapImpactSnapshotError,
    check_complete_roadmap_gates,
)
from plan_tool import roadmap_gates
from plan_tool.roadmap_relations import (
    RelationKind,
    RoadmapRelation,
    extract_declared_relations,
)
from plan_tool.project_config import HARD_MAX_PROSE_AMENDMENT_BYTES
from plan_tool.roadmap_revision import (
    TEXT_FIELDS_BY_ROW_TYPE,
    contains_whole_row_id,
    project_row_owned_prose_spans,
    stage_prose_span_id,
)
from plan_tool.roadmap_revision_patch import (
    RevisionMergeError,
    append_row_prose_fragments,
    splice_exact_spans,
)
from plan_tool.roadmap_versions import ResolvedRoadmapVersion


class CandidateDeltaError(ValueError):
    """A model response is outside the closed candidate-delta contract."""


class _FrozenCandidateRecord(BaseModel):
    """Closed immutable records returned by the candidate boundary."""

    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, arbitrary_types_allowed=True
    )


class CandidateAddRow(_FrozenCandidateRecord):
    """One typed row addition and its possible inseparable plan ordering slot."""

    op: Literal["add-row"] = "add-row"
    feedback_id: str
    artifact_key: str
    row_type: str
    row: object
    prose_amendment: "CandidateAddRowProseAmendment | None" = None
    ordering: OrderingEntry | None = None


class CandidateAddRowProseAmendment(_FrozenCandidateRecord):
    """The bounded append-only prose owned by one candidate row addition."""

    row_id: str
    fragment: str


class CandidateProseAmendmentDiff(_FrozenCandidateRecord):
    """One persisted add-row prose fragment shown during structural review."""

    artifact_key: str
    row_id: str
    fragment: str


class CandidateProseCorrectionDiff(_FrozenCandidateRecord):
    """One correct-prose operation's stored before text and after text, shown during structural review."""

    artifact_key: str
    span_id: str
    owning_row_ids: tuple[str, ...]
    # None only when the stored capsule no longer carries the issued span.
    before: str | None
    after: str


class CandidateReplaceRow(_FrozenCandidateRecord):
    """One typed replacement of a complete predecessor row."""

    op: Literal["replace-row"] = "replace-row"
    feedback_id: str
    artifact_key: str
    row_type: str
    row_id: str
    row: object


class CandidateRemoveRow(_FrozenCandidateRecord):
    """One typed removal and its possible inseparable plan ordering removal."""

    op: Literal["remove-row"] = "remove-row"
    feedback_id: str
    artifact_key: str
    row_type: str
    row_id: str
    ordering: OrderingEntry | None = None


class CandidateCorrectProse(_FrozenCandidateRecord):
    """One replacement of an issued shared-narrative span; no typed-row change.

    The model names only the span and its replacement. Span text, digest, owning
    rows, and offsets come from the capsule and predecessor, never from the model.
    """

    op: Literal["correct-prose"] = "correct-prose"
    feedback_id: str
    artifact_key: str
    span_id: str
    replacement: str


CandidateDeltaOperation: TypeAlias = (
    CandidateAddRow | CandidateReplaceRow | CandidateRemoveRow | CandidateCorrectProse
)


def candidate_prose_amendment_diffs(
    operations: Sequence[object] | None,
) -> tuple[CandidateProseAmendmentDiff, ...]:
    """Project admitted add-row fragments in their normalized operation order."""
    if operations is None:
        return ()
    return tuple(
        CandidateProseAmendmentDiff(
            artifact_key=operation.artifact_key,
            row_id=operation.prose_amendment.row_id,
            fragment=operation.prose_amendment.fragment,
        )
        for operation in operations
        if isinstance(operation, CandidateAddRow) and operation.prose_amendment is not None
    )


def candidate_prose_correction_diffs(
    operations: Sequence[object] | None, capsule: object | None
) -> tuple[CandidateProseCorrectionDiff, ...]:
    """Project correct-prose operations with the capsule's stored span text as the before text.

    Reads stored evidence only; the live artifact is never consulted.
    """
    if operations is None:
        return ()
    issued: dict[tuple[str, str], CandidateContextSourceSpan] = {}
    for member in getattr(capsule, "full_members", ()):
        for span in member.source_spans:
            issued[(member.identity.artifact_key, span.span_id)] = span
    diffs = []
    for operation in operations:
        if not isinstance(operation, CandidateCorrectProse):
            continue
        span = issued.get((operation.artifact_key, operation.span_id))
        diffs.append(
            CandidateProseCorrectionDiff(
                artifact_key=operation.artifact_key,
                span_id=operation.span_id,
                owning_row_ids=() if span is None else (span.owning_row_ids or (span.row_id,)),
                before=None if span is None else span.text,
                after=operation.replacement,
            )
        )
    return tuple(diffs)


class CandidateOperationClassification(enum.StrEnum):
    """The presentation boundary crossed by validated candidate operations."""

    PRESENTATION_ONLY = "presentation-only"
    STRUCTURAL = "structural"

_RELATIONLESS_ADD_ROW_TYPES: Final[frozenset[str]] = frozenset(
    {
        "dispositions",
        "hosting",
        "system_patterns",
        "component_patterns",
        "stores",
    }
)

# Addable rows that declare no relation, so no reached anchor is required.
# Deliberately not in the set above: `stack` is the one relationless collection
# a candidate may add to (it introduces the stack on a roadmap that has none).
_ANCHORLESS_ADD_ROW_TYPES: Final[frozenset[str]] = frozenset({"stack"})

NON_ADDABLE_ROW_TYPES: Final[tuple[str, ...]] = tuple(sorted(_RELATIONLESS_ADD_ROW_TYPES))


def _add_row_anchor_diagnostic(row_type: str, schema: str) -> str:
    if row_type == "PatternRow":  # one class, two collections: never pick one for the model
        schema = "system_patterns or component_patterns"
    return (
        "candidate add-row type cannot declare the required reached anchor: "
        f"{schema} cannot be added; replace an authorized existing row or omit this operation"
    )


class CandidateDelta(_FrozenCandidateRecord):
    """The one closed, inert material input accepted from model output."""

    operations: tuple[CandidateDeltaOperation, ...]
    responses: tuple["CandidateResponse", ...] = ()
    derived_feedback: tuple["CandidateDerivedFeedback", ...] = ()


class CandidateResponse(_FrozenCandidateRecord):
    """One model response to one immutable reviewer-item snapshot."""

    item_id: str
    response: str


class CandidateDerivedFeedback(_FrozenCandidateRecord):
    """One newly derived feedback entry before storage assigns its revision."""

    context_id: str
    content: str


class CandidateResponsePatch(_FrozenCandidateRecord):
    """The inert, exact reviewer-item patch for a later ledger writer."""

    entries: tuple["CandidateResponsePatchEntry", ...]


class CandidateResponsePatchEntry(_FrozenCandidateRecord):
    """One patch response bound to the complete issued reviewer snapshot."""

    item: ReviewerItemSnapshot
    response: str


class CandidateArtifact(_FrozenCandidateRecord):
    """One complete in-memory stage member returned on a green candidate."""

    artifact_key: str
    data: bytes
    text: str
    artifact: object
    digest: str


class GateCleanCandidate(_FrozenCandidateRecord):
    """A complete gate-clean candidate with no lifecycle side effect."""

    predecessor_version_id: str
    selected_feedback: CandidateContextFeedback
    capsule_receipt: CandidateContextReceipt
    artifacts: tuple[CandidateArtifact, ...]
    gate_outcomes: tuple[RoadmapGateOutcome, ...]
    predecessor_diff: CandidatePredecessorDiff
    impact_atoms: tuple[CandidateImpactAtom, ...]
    operation_classification: CandidateOperationClassification
    content_identity: str


class BatchGateCleanCandidate(_FrozenCandidateRecord):
    """A gate-clean candidate assembled from one immutable reviewer batch."""

    root_version_id: str
    predecessor_version_id: str
    capsule_receipt: CandidateContextBatchReceipt
    artifacts: tuple[CandidateArtifact, ...]
    gate_outcomes: tuple[RoadmapGateOutcome, ...]
    predecessor_diff: CandidatePredecessorDiff
    impact_atoms: tuple[CandidateImpactAtom, ...]
    response_patch: CandidateResponsePatch
    derived_feedback: tuple[CandidateDerivedFeedback, ...]
    normalized_operations: tuple[CandidateDeltaOperation, ...]
    operation_classification: CandidateOperationClassification
    content_identity: str


CandidateReviewReason: TypeAlias = Literal["declared-relation-impact"]


class CandidateRowImpactAtom(_FrozenCandidateRecord):
    """One relation-independent changed row retained for impact containment."""

    kind: Literal["row"] = "row"
    artifact_key: str
    row_type: str
    row_id: str
    before: object | None = None
    after: object | None = None


class CandidateRelationImpactAtom(_FrozenCandidateRecord):
    """One source-ordered unmatched declared-relation occurrence."""

    kind: Literal["relation"] = "relation"
    direction: Literal["added", "removed"]
    source_index: int
    relation: RoadmapRelation


CandidateImpactAtom: TypeAlias = CandidateRowImpactAtom | CandidateRelationImpactAtom


class CandidateReviewRequirement(_FrozenCandidateRecord):
    """The closed initial disclosure that requires one later human review."""

    schema_version: Literal[1] = 1
    reason: CandidateReviewReason
    predecessor_version_id: str
    selected_feedback: CandidateContextFeedback
    capsule_receipt: CandidateContextReceipt
    normalized_operations: tuple[CandidateDeltaOperation, ...]
    predecessor_diff: CandidatePredecessorDiff
    affected_predecessor_members: tuple[CandidateContextFullMember, ...]
    impact_atoms: tuple[CandidateImpactAtom, ...]
    initial_disclosed_impact_identity: str

    @model_validator(mode="after")
    def _requires_exact_initial_impact_identity(self) -> CandidateReviewRequirement:
        if not any(isinstance(atom, CandidateRelationImpactAtom) for atom in self.impact_atoms):
            raise ValueError("review requirement must disclose a declared relation impact")
        expected = _review_impact_identity(
            reason=self.reason,
            predecessor_version_id=self.predecessor_version_id,
            selected_feedback=self.selected_feedback,
            receipt=self.capsule_receipt,
            normalized_operations=self.normalized_operations,
            predecessor_diff=self.predecessor_diff,
            affected_predecessor_members=self.affected_predecessor_members,
            impact_atoms=self.impact_atoms,
        )
        if self.initial_disclosed_impact_identity != expected:
            raise ValueError("review requirement identity does not bind its initial disclosure")
        return self


class ReviewRequiredCandidate(_FrozenCandidateRecord):
    """A complete inert candidate whose exact impact needs human review."""

    predecessor_version_id: str
    selected_feedback: CandidateContextFeedback
    capsule_receipt: CandidateContextReceipt
    artifacts: tuple[CandidateArtifact, ...]
    gate_outcomes: tuple[RoadmapGateOutcome, ...]
    predecessor_diff: CandidatePredecessorDiff
    operation_classification: CandidateOperationClassification
    content_identity: str
    review_requirement: CandidateReviewRequirement

    @model_validator(mode="after")
    def _requires_requirement_to_bind_candidate_evidence(self) -> ReviewRequiredCandidate:
        requirement = self.review_requirement
        if (
            requirement.predecessor_version_id != self.predecessor_version_id
            or requirement.selected_feedback != self.selected_feedback
            or requirement.capsule_receipt != self.capsule_receipt
            or requirement.predecessor_diff != self.predecessor_diff
        ):
            raise ValueError("review requirement must bind its review-required candidate")
        return self


CandidateRefusalReason: TypeAlias = Literal[
    "invalid-delta",
    "invalid-predecessor",
    "invalid-capsule",
    "invalid-bindings",
    "invalid-operation",
    "unauthorized-existing-row",
    "unauthorized-addition",
    "relation-authority",
    "render-mismatch",
    "gate-failed",
]


class CandidateRefusal(_FrozenCandidateRecord):
    """A fail-closed result that never exposes a partial assembled candidate."""

    reason: CandidateRefusalReason
    detail: str


class CandidateMaterializationResult(_FrozenCandidateRecord):
    """Exactly one gate-clean candidate, review-required candidate, or refusal."""

    candidate: GateCleanCandidate | None = None
    batch_candidate: BatchGateCleanCandidate | None = None
    review_required: ReviewRequiredCandidate | None = None
    refusal: CandidateRefusal | None = None

    @model_validator(mode="after")
    def _requires_exactly_one_outcome(self) -> CandidateMaterializationResult:
        if sum(
            outcome is not None
            for outcome in (self.candidate, self.batch_candidate, self.review_required, self.refusal)
        ) != 1:
            raise ValueError("candidate materialization requires exactly one outcome")
        return self


_ROW_TYPE_NAMES: Final[frozenset[str]] = frozenset(
    {
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
    }
)

ADD_ROW_REQUIRED_KEYS: Final[frozenset[str]] = frozenset(
    {"op", "feedback_id", "artifact_key", "row_type", "row", "prose_amendment"}
)
ADD_ROW_OPTIONAL_KEYS: Final[frozenset[str]] = frozenset({"ordering"})
REPLACE_ROW_REQUIRED_KEYS: Final[frozenset[str]] = frozenset(
    {"op", "feedback_id", "artifact_key", "row_type", "row_id", "row"}
)
REPLACE_ROW_OPTIONAL_KEYS: Final[frozenset[str]] = frozenset()
REMOVE_ROW_REQUIRED_KEYS: Final[frozenset[str]] = frozenset(
    {"op", "feedback_id", "artifact_key", "row_type", "row_id"}
)
REMOVE_ROW_OPTIONAL_KEYS: Final[frozenset[str]] = frozenset({"ordering"})
CORRECT_PROSE_REQUIRED_KEYS: Final[frozenset[str]] = frozenset(
    {"op", "feedback_id", "artifact_key", "span_id", "replacement"}
)
CORRECT_PROSE_OPTIONAL_KEYS: Final[frozenset[str]] = frozenset()
# Candidate-local: equal to the add-row fragment limit today, but defined here so
# neither limit follows the other (ROADMAP_FORMAT.md § Shared-narrative correction).
CORRECT_PROSE_MAX_REPLACEMENT_BYTES: Final[int] = 4 * 1024
_OPERATION_FIELD_NAMES: Final[frozenset[str]] = frozenset().union(
    ADD_ROW_REQUIRED_KEYS,
    ADD_ROW_OPTIONAL_KEYS,
    REPLACE_ROW_REQUIRED_KEYS,
    REPLACE_ROW_OPTIONAL_KEYS,
    REMOVE_ROW_REQUIRED_KEYS,
    REMOVE_ROW_OPTIONAL_KEYS,
    CORRECT_PROSE_REQUIRED_KEYS,
    CORRECT_PROSE_OPTIONAL_KEYS,
)
_DISCOVERY_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {"collection", "source_collection", "issued_row", "row_digest"}
)
_OPERATION_REPORTABLE_NAMES: Final[frozenset[str]] = (
    _OPERATION_FIELD_NAMES | _DISCOVERY_FIELD_NAMES
)
_ROOT_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {"operations", "responses", "derived_feedback"}
)

_ROW_TYPE_BY_CLASS_NAME: Final[dict[str, str]] = {
    "EntityRow": "entities",
    "BusinessRuleRow": "business_rules",
    "WorkflowRow": "workflows",
    "DecisionRow": "decisions",
    "AttributeDispositionRow": "dispositions",
    "ConstraintRow": "constraints",
    "HostingRow": "hosting",
    "PatternRow": "system_patterns",
    "StoreRow": "stores",
    "StackRow": "stack",
    "ComponentRow": "components",
    "PlanRow": "plans",
    "AssumptionRow": "assumptions",
}


def parse_candidate_delta(response_text: str) -> CandidateDelta:
    """Parse one closed JSON delta without accepting executable or text edits."""
    payload = _decode_single_json_object(response_text)
    keys = set(payload)
    _require_keys(
        payload,
        required={"operations"},
        optional={"responses", "derived_feedback"},
        context="candidate delta root",
        known=_ROOT_FIELD_NAMES,
    )
    if keys != {"operations"}:
        _require_keys(
            payload,
            required=_ROOT_FIELD_NAMES,
            context="candidate delta root",
            known=_ROOT_FIELD_NAMES,
        )
    if not isinstance(payload["operations"], list):
        raise CandidateDeltaError("candidate delta root must contain exactly an operations array")
    diagnostics = [
        diagnostic
        for value in payload["operations"]
        for diagnostic in _operation_diagnostics(value)
    ]
    if diagnostics:
        raise CandidateDeltaError(
            diagnostics[0]
            if len(diagnostics) == 1
            else "candidate delta has " + "; ".join(diagnostics)
        )
    operations = tuple(_parse_operation(value) for value in payload["operations"])
    if keys == {"operations"}:
        return CandidateDelta(operations=operations)
    if not isinstance(payload["responses"], list) or not isinstance(payload["derived_feedback"], list):
        raise CandidateDeltaError("candidate response fields must be arrays")
    responses = tuple(_parse_response(value) for value in payload["responses"])
    derived_feedback = tuple(_parse_derived_feedback(value) for value in payload["derived_feedback"])
    if len({entry.item_id for entry in responses}) != len(responses):
        raise CandidateDeltaError("candidate responses must not repeat a reviewer item")
    if len({entry.context_id for entry in derived_feedback}) != len(derived_feedback):
        raise CandidateDeltaError("candidate derived feedback must not repeat a context id")
    return CandidateDelta(
        operations=operations, responses=responses, derived_feedback=derived_feedback
    )


def _parse_response(value: object) -> CandidateResponse:
    record = _mapping(value, "candidate response")
    _require_keys(record, required={"item_id", "response"}, context="candidate response")
    return CandidateResponse(item_id=_text(record, "item_id"), response=_text(record, "response"))


def _parse_derived_feedback(value: object) -> CandidateDerivedFeedback:
    record = _mapping(value, "candidate derived feedback")
    _require_keys(
        record,
        required={"context_id", "content"},
        context="candidate derived feedback",
    )
    return CandidateDerivedFeedback(
        context_id=_text(record, "context_id"), content=_text(record, "content")
    )


def _add_row_key_contract(row_type: object) -> tuple[frozenset[str], frozenset[str]]:
    """The add-row keys for ``row_type``: a prose-less collection (policy
    ``allow_prose=False``) makes ``prose_amendment`` optional so it can be
    refused when supplied rather than demanded."""
    if type(row_type) is str and not stage_row_operation_policy(row_type).allow_prose:
        return (
            ADD_ROW_REQUIRED_KEYS - {"prose_amendment"},
            ADD_ROW_OPTIONAL_KEYS | {"prose_amendment"},
        )
    return ADD_ROW_REQUIRED_KEYS, ADD_ROW_OPTIONAL_KEYS


def _parse_add_row_prose_amendment(
    value: object, row: StageRow, row_type: str
) -> CandidateAddRowProseAmendment:
    """Bind one bounded append fragment to the row an addition creates."""
    if value is None and not stage_row_operation_policy(row_type).allow_prose:
        raise CandidateDeltaError(f"{row_type} rows cannot carry a prose amendment")
    record = _mapping(value, "candidate add-row prose amendment")
    _require_keys(
        record,
        required={"row_id", "fragment"},
        context="candidate add-row prose amendment",
    )
    if not stage_row_operation_policy(row_type).allow_prose:
        raise CandidateDeltaError(f"{row_type} rows cannot carry a prose amendment")
    row_id = _text(record, "row_id")
    fragment = _text(record, "fragment")
    if row_id != row.id:
        raise CandidateDeltaError("candidate prose amendment must name its added row id")
    if not fragment.strip():
        raise CandidateDeltaError("candidate prose amendment fragment must be nonblank")
    if not contains_whole_row_id(fragment, row.id):
        raise CandidateDeltaError("candidate prose amendment fragment must name its added row id")
    if len(fragment.encode("utf-8")) > HARD_MAX_PROSE_AMENDMENT_BYTES:
        raise CandidateDeltaError("candidate prose amendment fragment exceeds the fixed byte limit")
    return CandidateAddRowProseAmendment(row_id=row_id, fragment=fragment)


def _correct_prose_replacement_problem(replacement: str) -> str | None:
    """Return the parse- and materialize-time refusal for one replacement, if any."""
    if not replacement.strip():
        return "candidate correct-prose replacement must be nonblank"
    if len(replacement.encode("utf-8")) > CORRECT_PROSE_MAX_REPLACEMENT_BYTES:
        return "candidate correct-prose replacement exceeds the byte ceiling"
    return None


def _parse_correct_prose(record: Mapping[str, object]) -> CandidateCorrectProse:
    _require_keys(
        record,
        required=CORRECT_PROSE_REQUIRED_KEYS,
        optional=CORRECT_PROSE_OPTIONAL_KEYS,
        context="candidate correct-prose operation",
        known=_OPERATION_REPORTABLE_NAMES,
    )
    replacement = _text(record, "replacement")
    problem = _correct_prose_replacement_problem(replacement)
    if problem is not None:
        raise CandidateDeltaError(problem)
    return CandidateCorrectProse(
        feedback_id=_text(record, "feedback_id"),
        artifact_key=_text(record, "artifact_key"),
        span_id=_text(record, "span_id"),
        replacement=replacement,
    )


def _operation_diagnostics(value: object) -> list[str]:
    """Return safe closed-envelope diagnostics without accepting an operation."""
    try:
        record = _mapping(value, "candidate operation")
    except CandidateDeltaError as exc:
        return [str(exc)]
    if "op" not in record:
        return _key_diagnostics(
            record,
            required={"op"},
            optional=_OPERATION_FIELD_NAMES - {"op"},
            context="candidate operation",
            known=_OPERATION_REPORTABLE_NAMES,
        )
    if type(record["op"]) is not str:
        return ["candidate field 'op' must be a string"]
    operation = cast(str, record["op"])
    contracts = {
        "add-row": _add_row_key_contract(record.get("row_type")),
        "replace-row": (REPLACE_ROW_REQUIRED_KEYS, REPLACE_ROW_OPTIONAL_KEYS),
        "remove-row": (REMOVE_ROW_REQUIRED_KEYS, REMOVE_ROW_OPTIONAL_KEYS),
        "correct-prose": (CORRECT_PROSE_REQUIRED_KEYS, CORRECT_PROSE_OPTIONAL_KEYS),
    }
    if operation not in contracts:
        return [f"candidate operation {operation!r} is not allowed"]
    required, optional = contracts[operation]
    diagnostics = _key_diagnostics(
        record,
        required=required,
        optional=optional,
        context=f"candidate {operation} operation",
        known=_OPERATION_REPORTABLE_NAMES,
    )
    if operation == "correct-prose":
        if not diagnostics:
            try:
                _parse_correct_prose(record)
            except CandidateDeltaError as exc:
                diagnostics.append(str(exc))
        return diagnostics
    row_type = record.get("row_type")
    if type(row_type) is not str:
        if "row_type" in record:
            diagnostics.append("candidate field 'row_type' must be a string")
        return diagnostics
    row_schema = _diagnostic_row_schema(cast(str, row_type))
    if row_type not in _ROW_TYPE_NAMES:
        diagnostics.append(_invalid_row_type_diagnostic(cast(str, row_type), row_schema))
    if operation == "add-row" and row_schema in _RELATIONLESS_ADD_ROW_TYPES:
        diagnostics.append(_add_row_anchor_diagnostic(cast(str, row_type), row_schema))
    if row_schema is not None and "row" in required | optional and "row" in record:
        row: StageRow | None = None
        try:
            row = _parse_stage_row(row_schema, record["row"])
        except CandidateDeltaError as exc:
            diagnostics.append(str(exc))
        if row is not None and operation == "add-row" and "prose_amendment" in record:
            try:
                _parse_add_row_prose_amendment(record["prose_amendment"], row, row_schema)
            except CandidateDeltaError as exc:
                diagnostics.append(str(exc))
    return diagnostics


def _diagnostic_row_schema(row_type: str) -> str | None:
    """Choose a schema for diagnostics without widening accepted row types."""
    if row_type in _ROW_TYPE_NAMES:
        return row_type
    return _ROW_TYPE_BY_CLASS_NAME.get(row_type)


def _invalid_row_type_diagnostic(row_type: str, schema: str | None) -> str:
    if schema is None:
        return "candidate row has invalid-row-type; use a supported collection row_type"
    if row_type == "PatternRow":  # one class, two collections: never pick one for the model
        schema = "system_patterns or component_patterns"
    return f"candidate row has invalid-row-type {row_type}; use {schema}"


_KNOWN_GATE_KINDS: Final[frozenset[str]] = frozenset(
    value for name, value in vars(roadmap_gates).items()
    if name.startswith("VIOLATION_") and isinstance(value, str)
)

# duplicate-* kinds whose message means "drop the extras", not "rename the
# id" — see BACKLOG #431 for the classification's known maintenance cost.
_DROP_EXTRA_ROWS_GATE_KINDS: Final[frozenset[str]] = frozenset(
    {
        roadmap_gates.VIOLATION_DUPLICATE_INHERITED_DECISION,
        roadmap_gates.VIOLATION_DUPLICATE_FEEDBACK_ID,
        roadmap_gates.VIOLATION_DUPLICATE_STORE_REFERENCE,
        roadmap_gates.VIOLATION_DUPLICATE_STACK_CONCERN,
        roadmap_gates.VIOLATION_ORDERING_PLAN_ID_DUPLICATE,
    }
)

def _gate_correction(outcomes: tuple[RoadmapGateOutcome, ...]) -> str:
    """Use closed gate facts, never a violation's model-content-bearing message.
    Location prefers ``violation.artifact``: see ``check_duplicate_row_ids``."""
    corrections: list[str] = []
    for outcome in outcomes:
        for violation in outcome.violations:
            kind = getattr(violation, "kind", None)
            artifact = getattr(violation, "artifact", None)
            location = artifact if isinstance(artifact, str) and artifact else outcome.stage.artifact_key
            if kind not in _KNOWN_GATE_KINDS:
                # Degrade this one violation, not the corrections already
                # assembled for its siblings in the same call.
                corrections.append(
                    f"{location}: an unrecognized gate violation; "
                    "repair this stage's rows and declared relations"
                )
                continue
            row_id = getattr(violation, "row_id", None)
            quoted_row_id = _quoted_safe_id(row_id)
            identity = f" row {quoted_row_id}" if quoted_row_id else " (row identity unavailable)"
            ordering_condition = (
                _ordering_reference_condition(violation)
                if kind == roadmap_gates.VIOLATION_UNDEFINED_ORDERING_PLAN_REFERENCE
                else None
            )
            if ordering_condition is not None:
                condition = ordering_condition
            elif kind.startswith(("undefined-", "unresolved-", "unknown-")):
                condition = "reference a defined, permitted roadmap row or value"
            elif kind == "entity-without-fields":
                condition = "declare at least one named, typed field for the entity"
            elif kind.startswith(("uncovered-", "undischarged-", "no-assumption-consumer")):
                condition = "supply the required downstream coverage or consumer"
            elif kind.startswith("redundant-") or kind in _DROP_EXTRA_ROWS_GATE_KINDS:
                # Checked ahead of "duplicate-" below, its rename-shaped sibling.
                condition = "keep exactly one row for this value and drop the rest"
            elif kind.startswith("duplicate-"):
                condition = "keep the named identifier unique in its required scope"
            elif kind.startswith(
                (
                    "missing-",
                    "no-",
                    "empty-",
                    "blank-",
                    "undescribed-",
                    "unanchored-",
                    "uncited-",
                    "unreasoned-",
                    "undisposed-",
                )
            ):
                condition = "supply the required nonempty row, field, or relation"
            elif kind.startswith(("dropped-", "altered-")):
                condition = "preserve the required carried row or value"
            elif kind == roadmap_gates.VIOLATION_STACK_ROW_STATE:
                condition = "give the row exactly one of a nonblank choice or open: true"
            else:
                condition = "repair this gate's named row and its declared relations"
            corrections.append(f"{location}{identity}: {kind}; {condition}")
    return "roadmap gates failed: " + "; ".join(corrections) if corrections else (
        "the complete assembled candidate does not pass roadmap gates"
    )


def _quoted_safe_id(value: object) -> str | None:
    """The one place a gate id is echoed into a retry correction: validated, then quoted."""
    return json.dumps(value, ensure_ascii=True) if is_receipt_safe_id(value) else None


def _ordering_reference_condition(violation: object) -> str | None:
    """Closed wording per ordering-reference defect; ``None`` keeps the generic one."""
    defect = getattr(violation, "reference_defect", None)
    quoted_reference = _quoted_safe_id(getattr(violation, "referenced_id", None))
    reference = (
        f"ordering reference {quoted_reference}"
        if quoted_reference
        else "an ordering reference (identity unavailable)"
    )
    if defect == roadmap_gates.ORDERING_REFERENCE_ABSENT:
        return f"{reference} names no plan row; add that plan or drop the reference"
    if defect == roadmap_gates.ORDERING_REFERENCE_CYCLE:
        return (
            f"{reference} closes a cycle: it already reaches this plan through depends_on "
            "or assumption_targets; drop this reference, or another reference on the same cycle"
        )
    if defect == roadmap_gates.ORDERING_REFERENCE_NOT_EARLIER:
        return f"{reference} is defined but not earlier in ordering; it must come before this plan"
    return None


def materialize_candidate(
    delta: CandidateDelta,
    *,
    predecessor: ResolvedRoadmapVersion,
    capsule: CandidateContextCapsule,
    receipt: CandidateContextReceipt,
) -> CandidateMaterializationResult:
    """Apply only capsule-authorized typed changes to one immutable predecessor."""
    stages = STAGES
    if not isinstance(delta, CandidateDelta) or not _delta_is_well_formed(delta):
        return _refuse(
            "invalid-delta", "candidate materialization requires one parsed closed delta"
        )

    verified = _verify_bindings(
        predecessor=predecessor,
        capsule=capsule,
        receipt=receipt,
        stages=stages,
    )
    if isinstance(verified, CandidateRefusal):
        return CandidateMaterializationResult(refusal=verified)
    predecessor_artifacts, predecessor_bytes = verified

    is_batch = isinstance(capsule, CandidateContextBatchCapsule)
    response_patch: CandidateResponsePatch | None = None
    if is_batch:
        response_patch = _validate_batch_response(delta, capsule)
        if isinstance(response_patch, CandidateRefusal):
            return CandidateMaterializationResult(refusal=response_patch)
    elif delta.responses or delta.derived_feedback:
        return _refuse("invalid-delta", "response material requires an issued reviewer batch")

    authority = _full_member_authority(capsule)
    feedback_ids = (
        tuple(item.item_id for item in capsule.reviewer_items)
        if is_batch
        else (cast(CandidateContextFeedback, capsule.feedback).feedback_id,)
    )
    # Corrections have no row target, so _prepare_operations keeps its row-only contract.
    row_operations = tuple(
        operation
        for operation in delta.operations
        if not isinstance(operation, CandidateCorrectProse)
    )
    prepared = _prepare_operations(
        row_operations,
        predecessor_artifacts=predecessor_artifacts,
        stages=stages,
    )
    if isinstance(prepared, CandidateRefusal):
        return CandidateMaterializationResult(refusal=prepared)

    validated = _validate_operation_authority(
        prepared,
        predecessor_artifacts=predecessor_artifacts,
        authority=authority,
        feedback_ids=feedback_ids,
    )
    if validated is not None:
        return CandidateMaterializationResult(refusal=validated)

    corrections = _resolve_corrections(
        tuple(
            operation
            for operation in delta.operations
            if isinstance(operation, CandidateCorrectProse)
        ),
        row_operations=prepared,
        predecessor_artifacts=predecessor_artifacts,
        capsule=capsule,
        feedback_ids=feedback_ids,
        stages=stages,
    )
    if isinstance(corrections, CandidateRefusal):
        return CandidateMaterializationResult(refusal=corrections)
    normalized_operations = (*prepared, *(resolved.operation for resolved in corrections))

    # A correction is structural: it is not a row replacement.
    operation_classification = _classify_validated_operations(
        normalized_operations, predecessor_artifacts=predecessor_artifacts
    )

    try:
        candidate_artifacts = _apply_operations_in_contract_order(
            predecessor_artifacts, prepared, corrections
        )
    except (AttributeError, RevisionMergeError, TypeError, ValueError) as exc:
        return _refuse("invalid-operation", str(exc))

    relation_atoms = _relation_occurrence_atoms(
        before=extract_declared_relations(**predecessor_artifacts),
        after=extract_declared_relations(**candidate_artifacts),
    )
    relation_refusal = _validate_relation_authority(
        predecessor_artifacts=predecessor_artifacts,
        candidate_artifacts=candidate_artifacts,
        operations=prepared,
        authority=authority,
        capsule=capsule,
    )
    if relation_refusal is not None:
        return CandidateMaterializationResult(refusal=relation_refusal)

    assembled = _assemble_candidate_artifacts(
        predecessor_artifacts=predecessor_artifacts,
        candidate_artifacts=candidate_artifacts,
        predecessor_bytes=predecessor_bytes,
        stages=stages,
        feedback_free=is_batch,
    )
    if isinstance(assembled, CandidateRefusal):
        return CandidateMaterializationResult(refusal=assembled)

    evidence = CompleteRoadmapGateEvidence(
        artifact_keys=tuple(member.artifact_key for member in assembled),
        artifact_texts=tuple(member.text for member in assembled),
        artifacts=tuple(member.artifact for member in assembled),
        artifact_digests=tuple(member.digest for member in assembled),
        brief_bytes=predecessor.brief_bytes,
    )
    try:
        outcomes = check_complete_roadmap_gates(evidence, stages=stages)
    except RoadmapImpactSnapshotError as exc:
        return _refuse("render-mismatch", str(exc))
    if (
        len(outcomes) != len(stages)
        or any(outcome.stage is not stage for outcome, stage in zip(outcomes, stages, strict=True))
        or any(outcome.violations for outcome in outcomes)
    ):
        return _refuse("gate-failed", _gate_correction(outcomes))

    predecessor_diff = _build_predecessor_diff(
        predecessor_artifacts=predecessor_artifacts,
        candidate_artifacts=candidate_artifacts,
        predecessor_bytes=predecessor_bytes,
        candidate_artifacts_bytes=tuple(member.data for member in assembled),
        stages=stages,
    )
    # The derived set is unordered; id order keeps the identity and the stored set independent of the model's.
    derived_feedback = tuple(sorted(delta.derived_feedback, key=lambda entry: entry.context_id))
    content_identity = _content_identity(
        predecessor_version_id=predecessor.record.version_id,
        selected_feedback=capsule.feedback,
        receipt=receipt,
        artifacts=assembled,
        predecessor_diff=predecessor_diff,
        response_patch=response_patch,
        derived_feedback=derived_feedback,
    )
    if is_batch:
        assert response_patch is not None
        return CandidateMaterializationResult(
            batch_candidate=BatchGateCleanCandidate(
                root_version_id=capsule.root.version_id,
                predecessor_version_id=predecessor.record.version_id,
                capsule_receipt=cast(CandidateContextBatchReceipt, receipt),
                artifacts=assembled,
                gate_outcomes=outcomes,
                predecessor_diff=predecessor_diff,
                impact_atoms=_candidate_impact_atoms(predecessor_diff, relation_atoms),
                response_patch=response_patch,
                derived_feedback=derived_feedback,
                normalized_operations=normalized_operations,
                operation_classification=operation_classification,
                content_identity=content_identity,
            )
        )
    impact_atoms = _candidate_impact_atoms(predecessor_diff, relation_atoms)
    if _has_reviewable_existing_row_relation_impact(prepared, relation_atoms):
        requirement = _build_review_requirement(
            predecessor_version_id=predecessor.record.version_id,
            selected_feedback=capsule.feedback,
            receipt=receipt,
            normalized_operations=normalized_operations,
            predecessor_diff=predecessor_diff,
            affected_predecessor_members=_affected_predecessor_members(
                capsule=capsule,
                predecessor_diff=predecessor_diff,
                relation_atoms=relation_atoms,
                predecessor_rows=_predecessor_row_identities(predecessor_artifacts),
            ),
            impact_atoms=impact_atoms,
        )
        return CandidateMaterializationResult(
            review_required=ReviewRequiredCandidate(
                predecessor_version_id=predecessor.record.version_id,
                selected_feedback=capsule.feedback,
                capsule_receipt=receipt,
                artifacts=assembled,
                gate_outcomes=outcomes,
                predecessor_diff=predecessor_diff,
                operation_classification=operation_classification,
                content_identity=content_identity,
                review_requirement=requirement,
            )
        )
    return CandidateMaterializationResult(
        candidate=GateCleanCandidate(
            predecessor_version_id=predecessor.record.version_id,
            selected_feedback=capsule.feedback,
            capsule_receipt=receipt,
            artifacts=assembled,
            gate_outcomes=outcomes,
            predecessor_diff=predecessor_diff,
            impact_atoms=impact_atoms,
            operation_classification=operation_classification,
            content_identity=content_identity,
        )
    )


def _decode_single_json_object(response_text: str) -> dict[str, object]:
    if not isinstance(response_text, str):
        raise CandidateDeltaError("candidate delta must be JSON text")
    decoder = json.JSONDecoder(
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_constant,
    )
    start = len(response_text) - len(response_text.lstrip(" \t\r\n"))
    try:
        payload, end = decoder.raw_decode(response_text, start)
    except (CandidateDeltaError, json.JSONDecodeError) as exc:
        raise CandidateDeltaError("candidate delta must be one unfenced JSON object") from exc
    if response_text[end:].strip(" \t\r\n"):
        raise CandidateDeltaError("candidate delta must not contain trailing data")
    if not isinstance(payload, dict):
        raise CandidateDeltaError("candidate delta root must be a JSON object")
    return cast(dict[str, object], payload)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise CandidateDeltaError(f"candidate delta has duplicate JSON key {key!r}")
        value[key] = item
    return value


def _reject_constant(value: str) -> None:
    raise CandidateDeltaError(f"candidate delta cannot use JSON constant {value!r}")


def _parse_operation(value: object) -> CandidateDeltaOperation:
    record = _mapping(value, "candidate operation")
    operation = _text(record, "op")
    if operation == "add-row":
        add_required, add_optional = _add_row_key_contract(record.get("row_type"))
        _require_keys(
            record,
            required=add_required,
            optional=add_optional,
            context="candidate add-row operation",
            known=_OPERATION_REPORTABLE_NAMES,
        )
        row_type = _text(record, "row_type")
        # _operation_diagnostics already rejects this; no second check needed.
        row = _parse_stage_row(row_type, record["row"])
        return CandidateAddRow(
            feedback_id=_text(record, "feedback_id"),
            artifact_key=_text(record, "artifact_key"),
            row_type=row_type,
            row=row,
            # A prose-less collection (policy allow_prose=False) may omit it;
            # a supplied one still reaches the parser's "cannot carry" refusal.
            prose_amendment=(
                _parse_add_row_prose_amendment(record["prose_amendment"], row, row_type)
                if "prose_amendment" in record
                else None
            ),
            ordering=_parse_optional_ordering(record.get("ordering")),
        )
    if operation == "replace-row":
        _require_keys(
            record,
            required=REPLACE_ROW_REQUIRED_KEYS,
            optional=REPLACE_ROW_OPTIONAL_KEYS,
            context="candidate replace-row operation",
            known=_OPERATION_REPORTABLE_NAMES,
        )
        row_type = _text(record, "row_type")
        row = _parse_stage_row(row_type, record["row"])
        row_id = _text(record, "row_id")
        if getattr(row, "id", None) != row_id:
            raise CandidateDeltaError("candidate replacement row id must match its row_id")
        return CandidateReplaceRow(
            feedback_id=_text(record, "feedback_id"),
            artifact_key=_text(record, "artifact_key"),
            row_type=row_type,
            row_id=row_id,
            row=row,
        )
    if operation == "remove-row":
        _require_keys(
            record,
            required=REMOVE_ROW_REQUIRED_KEYS,
            optional=REMOVE_ROW_OPTIONAL_KEYS,
            context="candidate remove-row operation",
            known=_OPERATION_REPORTABLE_NAMES,
        )
        return CandidateRemoveRow(
            feedback_id=_text(record, "feedback_id"),
            artifact_key=_text(record, "artifact_key"),
            row_type=_text(record, "row_type"),
            row_id=_text(record, "row_id"),
            ordering=_parse_optional_ordering(record.get("ordering")),
        )
    if operation == "correct-prose":
        return _parse_correct_prose(record)
    raise CandidateDeltaError(f"candidate operation {operation!r} is not allowed")


def _parse_stage_row(row_type: str, value: object) -> StageRow:
    if row_type not in _ROW_TYPE_NAMES:
        raise CandidateDeltaError(f"candidate row type {row_type!r} is not allowed")
    record = _mapping(value, f"{row_type} row")
    if row_type == "entities":
        _require_keys(record, required={"id", "name", "fields"}, context="entities row")
        return EntityRow(
            _text(record, "id"),
            _text(record, "name"),
            tuple(_parse_field(item) for item in _list(record, "fields")),
        )
    if row_type == "business_rules":
        _require_keys(record, required={"id", "statement", "entity_ids"}, context="business rules row")
        return BusinessRuleRow(
            _text(record, "id"), _text(record, "statement"), _text_tuple(record, "entity_ids")
        )
    if row_type == "workflows":
        _require_keys(record, required={"id", "name", "entity_ids"}, context="workflows row")
        return WorkflowRow(
            _text(record, "id"), _text(record, "name"), _text_tuple(record, "entity_ids")
        )
    if row_type == "decisions":
        _require_keys(
            record,
            required={
                "id",
                "chosen_option",
                "rejected_alternatives",
                "rationale",
                "anchor",
                "status",
            },
            context="decisions row",
            known=frozenset(field.name for field in fields(DecisionRow)),
        )
        return DecisionRow(
            _text(record, "id"),
            _text(record, "chosen_option"),
            tuple(
                _parse_rejected_alternative(item) for item in _list(record, "rejected_alternatives")
            ),
            _text(record, "rationale"),
            _text(record, "anchor"),
            _enum_value(DecisionStatus, _text(record, "status"), "decision status"),
        )
    if row_type == "dispositions":
        _require_keys(record, required={"id", "attribute", "disposition"}, context="dispositions row")
        return AttributeDispositionRow(
            _text(record, "id"),
            _text(record, "attribute"),
            _enum_value(
                ConstraintDisposition,
                _text(record, "disposition"),
                "constraint disposition",
            ),
        )
    if row_type == "constraints":
        _require_keys(record, required={"id", "statement", "attribute", "anchor_ids"}, context="constraints row")
        return ConstraintRow(
            _text(record, "id"),
            _text(record, "statement"),
            _text(record, "attribute"),
            _text_tuple(record, "anchor_ids"),
        )
    if row_type == "hosting":
        _require_keys(
            record,
            required={"id", "facet", "value"},
            optional={"product", "description", "research_disclosure"},
            context="hosting row",
        )
        disclosure = _nullable_text(record, "research_disclosure")
        return HostingRow(
            _text(record, "id"),
            _text(record, "facet"),
            _text(record, "value"),
            _nullable_text(record, "product"),
            _nullable_text(record, "description"),
            None
            if disclosure is None
            else _enum_value(ResearchDisclosure, disclosure, "research disclosure"),
        )
    if row_type in {"system_patterns", "component_patterns"}:
        _require_keys(record, required={"id", "name", "statement"}, context="patterns row")
        return PatternRow(_text(record, "id"), _text(record, "name"), _text(record, "statement"))
    if row_type == "stores":
        _require_keys(
            record,
            required={"id", "category", "sharing"},
            optional={"product", "description", "research_disclosure"},
            context="stores row",
        )
        disclosure = _nullable_text(record, "research_disclosure")
        return StoreRow(
            _text(record, "id"),
            _text(record, "category"),
            _text(record, "sharing"),
            _nullable_text(record, "product"),
            _nullable_text(record, "description"),
            None
            if disclosure is None
            else _enum_value(ResearchDisclosure, disclosure, "research disclosure"),
        )
    if row_type == "stack":
        _require_keys(
            record,
            required={"id", "concern"},
            optional={"choice", "open"},
            context="stack row",
        )
        is_open = record.get("open", False)
        if type(is_open) is not bool:
            raise CandidateDeltaError("candidate field 'open' must be a boolean")
        return StackRow(
            _text(record, "id"),
            _text(record, "concern"),
            _nullable_text(record, "choice"),
            is_open,
        )
    if row_type == "components":
        _require_keys(
            record,
            required={"id", "name", "entity_ids", "pattern_ids"},
            optional={"constraint_ids", "store_ids"},
            context="components row",
        )
        return ComponentRow(
            _text(record, "id"),
            _text(record, "name"),
            _text_tuple(record, "entity_ids"),
            _text_tuple(record, "pattern_ids"),
            _text_tuple(record, "constraint_ids", default=()),
            _text_tuple(record, "store_ids", default=()),
        )
    if row_type == "plans":
        _require_keys(
            record,
            required={
                "id",
                "title",
                "disposition",
                "component_ids",
                "draft_seed_path",
                "sizing_rationale",
            },
            optional={"intent", "non_goals"},
            context="plans row",
        )
        return PlanRow(
            _text(record, "id"),
            _text(record, "title"),
            _enum_value(PlanDisposition, _text(record, "disposition"), "plan disposition"),
            _text_tuple(record, "component_ids"),
            _text(record, "draft_seed_path"),
            _text(record, "sizing_rationale"),
            _text(record, "intent", default=""),
            _text_tuple(record, "non_goals", default=()),
        )
    assert row_type == "assumptions"
    _require_keys(record, required={"id", "statement", "consuming_plan_ids"}, context="assumptions row")
    return AssumptionRow(
        _text(record, "id"), _text(record, "statement"), _text_tuple(record, "consuming_plan_ids")
    )


def _restore_stored_stage_row(row_type: str, value: object) -> StageRow:
    """Rebuild a row this tool persisted; admits canonical fields a model delta may not author."""
    row = _restore_stored_decision_row(value) if row_type == "decisions" else _parse_stage_row(row_type, value)
    if _wire_value(row) != value:
        raise CandidateDeltaError(f"stored {row_type} row does not round-trip to its stored form")
    return row


def _restore_stored_decision_row(value: object) -> DecisionRow:
    record = _mapping(value, "stored decisions row")
    _require_keys(
        record,
        required={field.name for field in fields(DecisionRow)},
        context="stored decisions row",
    )
    source = _nullable_text(record, "source")
    rationale = _nullable_text(record, "rationale")
    # Mirrors the artifact parser: only an inherited decision may omit its rationale.
    if rationale is None and source is None:
        raise CandidateDeltaError("stored decisions row requires a rationale unless inherited")
    return DecisionRow(
        _text(record, "id"),
        _text(record, "chosen_option"),
        tuple(_parse_rejected_alternative(item) for item in _list(record, "rejected_alternatives")),
        rationale,
        _text(record, "anchor"),
        _enum_value(DecisionStatus, _text(record, "status"), "decision status"),
        source,
    )


def _parse_field(value: object) -> FieldRow:
    record = _mapping(value, "entity field")
    _require_keys(
        record,
        required={"name", "type"},
        optional={"entity_id"},
        context="entity field",
    )
    entity_id = _nullable_text(record, "entity_id")
    return FieldRow(
        _text(record, "name"),
        _enum_value(FieldType, _text(record, "type"), "field type"),
        entity_id,
    )


def _parse_rejected_alternative(value: object) -> RejectedAlternative:
    record = _mapping(value, "rejected alternative")
    _require_keys(record, required={"option", "reason"}, context="rejected alternative")
    return RejectedAlternative(_text(record, "option"), _text(record, "reason"))


def _parse_optional_ordering(value: object) -> OrderingEntry | None:
    if value is None:
        return None
    record = _mapping(value, "ordering entry")
    _require_keys(
        record,
        required={"plan_id"},
        optional={"depends_on", "assumption_targets"},
        context="ordering entry",
    )
    return OrderingEntry(
        _text(record, "plan_id"),
        _text_tuple(record, "depends_on", default=()),
        _text_tuple(record, "assumption_targets", default=()),
    )


def _mapping(value: object, description: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(type(key) is str for key in value):
        raise CandidateDeltaError(f"{description} must be a JSON object")
    return cast(dict[str, object], value)


def _require_keys(
    record: Mapping[str, object],
    *,
    required: Set[str],
    optional: Set[str] = frozenset(),
    context: str = "candidate record",
    known: Set[str] | None = None,
) -> None:
    """Reject incomplete records without reflecting arbitrary field names."""
    diagnostics = _key_diagnostics(
        record, required=required, optional=optional, context=context, known=known
    )
    if diagnostics:
        raise CandidateDeltaError(diagnostics[0])


def _key_diagnostics(
    record: Mapping[str, object],
    *,
    required: Set[str],
    optional: Set[str] = frozenset(),
    context: str = "candidate record",
    known: Set[str] | None = None,
) -> list[str]:
    """Render closed field diagnostics for an otherwise untrusted record."""
    keys = set(record)
    missing = required - keys
    unknown = keys - required - optional
    if not missing and not unknown:
        return []
    reportable = required | optional if known is None else known
    diagnostics: list[str] = []
    if missing:
        diagnostics.append("missing-field " + ", ".join(sorted(missing)))
    if unknown:
        named_unknown = sorted(unknown & reportable)
        if unknown - reportable:
            named_unknown.append("other")
        diagnostics.append("unknown-field " + ", ".join(named_unknown))
    return [f"{context} has {'; '.join(diagnostics)}"]


def _text(record: Mapping[str, object], field: str, *, default: str | None = None) -> str:
    if field not in record:
        if default is None:
            raise CandidateDeltaError(f"candidate record requires {field!r}")
        return default
    value = record[field]
    if type(value) is not str:
        raise CandidateDeltaError(f"candidate field {field!r} must be a string")
    return value


def _nullable_text(record: Mapping[str, object], field: str) -> str | None:
    if field not in record or record[field] is None:
        return None
    return _text(record, field)


def _list(record: Mapping[str, object], field: str) -> list[object]:
    value = record.get(field)
    if not isinstance(value, list):
        raise CandidateDeltaError(f"candidate field {field!r} must be an array")
    return cast(list[object], value)


def _text_tuple(
    record: Mapping[str, object], field: str, *, default: tuple[str, ...] | None = None
) -> tuple[str, ...]:
    if field not in record:
        if default is None:
            raise CandidateDeltaError(f"candidate record requires {field!r}")
        return default
    value = _list(record, field)
    if any(type(item) is not str for item in value):
        raise CandidateDeltaError(f"candidate field {field!r} must contain only strings")
    return tuple(cast(str, item) for item in value)


_EnumValue: TypeAlias = (
    DecisionStatus | ConstraintDisposition | FieldType | PlanDisposition | ResearchDisclosure
)

_STAGE_ROW_TYPES: Final[tuple[type[StageRow], ...]] = (
    EntityRow,
    BusinessRuleRow,
    WorkflowRow,
    DecisionRow,
    AttributeDispositionRow,
    ConstraintRow,
    HostingRow,
    PatternRow,
    StoreRow,
    StackRow,
    ComponentRow,
    PlanRow,
    AssumptionRow,
)


def _enum_value(enum_type: type[_EnumValue], value: str, description: str) -> _EnumValue:
    try:
        return enum_type(value)
    except ValueError as exc:
        raise CandidateDeltaError(f"candidate {description} is not allowed") from exc


def _delta_is_well_formed(delta: CandidateDelta) -> bool:
    if not isinstance(delta.operations, tuple) or not isinstance(delta.responses, tuple) or not isinstance(delta.derived_feedback, tuple):
        return False
    if any(not isinstance(entry, CandidateResponse) or not entry.item_id or not entry.response for entry in delta.responses):
        return False
    if any(not isinstance(entry, CandidateDerivedFeedback) or not entry.context_id or not entry.content for entry in delta.derived_feedback):
        return False
    if len({entry.item_id for entry in delta.responses}) != len(delta.responses):
        return False
    if len({entry.context_id for entry in delta.derived_feedback}) != len(delta.derived_feedback):
        return False
    for operation in delta.operations:
        if not isinstance(
            operation,
            (CandidateAddRow, CandidateReplaceRow, CandidateRemoveRow, CandidateCorrectProse),
        ):
            return False
        if isinstance(operation, CandidateCorrectProse):
            # Shape only; content limits are re-checked in _resolve_corrections.
            if (
                operation.op != "correct-prose"
                or not isinstance(operation.feedback_id, str)
                or not isinstance(operation.artifact_key, str)
                or not isinstance(operation.span_id, str)
                or not isinstance(operation.replacement, str)
            ):
                return False
            continue
        if (
            not isinstance(operation.feedback_id, str)
            or not isinstance(operation.artifact_key, str)
            or not isinstance(operation.row_type, str)
        ):
            return False
        if isinstance(operation, CandidateAddRow):
            # Shape only, like the sibling branches below: content was already
            # enforced by _parse_add_row_prose_amendment at parse time.
            if (
                operation.op != "add-row"
                or type(operation.row) not in _STAGE_ROW_TYPES
                or not (
                    isinstance(operation.prose_amendment, CandidateAddRowProseAmendment)
                    or (
                        operation.prose_amendment is None
                        and not stage_row_operation_policy(operation.row_type).allow_prose
                    )
                )
                or (
                    operation.ordering is not None
                    and not isinstance(operation.ordering, OrderingEntry)
                )
            ):
                return False
        elif isinstance(operation, CandidateReplaceRow):
            if (
                operation.op != "replace-row"
                or not isinstance(operation.row_id, str)
                or type(operation.row) not in _STAGE_ROW_TYPES
            ):
                return False
        elif (
            operation.op != "remove-row"
            or not isinstance(operation.row_id, str)
            or (
                operation.ordering is not None and not isinstance(operation.ordering, OrderingEntry)
            )
        ):
            return False
    return True


def _verify_bindings(
    *,
    predecessor: object,
    capsule: object,
    receipt: object,
    stages: Sequence[RoadmapStage],
) -> tuple[dict[str, RoadmapArtifact], tuple[bytes, ...]] | CandidateRefusal:
    if not isinstance(predecessor, ResolvedRoadmapVersion):
        return _refusal(
            "invalid-predecessor", "candidate requires resolved immutable predecessor bytes"
        )
    if (
        not isinstance(capsule, CandidateContextCapsule)
        or not isinstance(receipt, CandidateContextReceipt)
        or not isinstance(capsule.receipt, CandidateContextReceipt)
        or not isinstance(stages, Sequence)
        or not all(isinstance(stage, RoadmapStage) for stage in stages)
    ):
        return _refusal("invalid-capsule", "candidate requires an issued capsule and receipt")
    if receipt != capsule.receipt:
        return _refusal("invalid-bindings", "supplied receipt does not match the issued capsule")
    expected_keys = tuple(stage.artifact_key for stage in stages)
    if (
        expected_keys != tuple(stage.artifact_key for stage in STAGES)
        or predecessor.artifact_keys != expected_keys
        or len(predecessor.artifact_bytes) != len(stages)
    ):
        return _refusal(
            "invalid-predecessor", "predecessor stage order does not match the stage table"
        )

    if isinstance(capsule, CandidateContextBatchCapsule):
        if (
            not isinstance(receipt, CandidateContextBatchReceipt)
            or capsule.root != receipt.root
            or capsule.source != receipt.source
            or capsule.reviewer_items != receipt.reviewer_items
            or capsule.derived_context != receipt.derived_context
            or capsule.ledger_digest != receipt.ledger_digest
            or predecessor.record.version_id != capsule.source.version_id
            or capsule.predecessor != capsule.source
            or capsule.root.roadmap_slug != capsule.source.roadmap_slug
        ):
            return _refusal("invalid-bindings", "batch root, source, and receipt must bind exactly")
        # Batch capsules have no embedded artifact feedback.  Their item snapshots
        # and receipt are the only response authority; storage rechecks live state.
        return _parse_predecessor_artifacts(predecessor, stages)
    if not isinstance(capsule.feedback, CandidateContextFeedback):
        return _refusal("invalid-capsule", "legacy capsule requires selected feedback")

    selector = f"{capsule.feedback.artifact_key}:{capsule.feedback.feedback_id}"
    initial = rebuild_candidate_context_at_recorded_ceiling(
        predecessor, selector, recorded_ceiling_bytes=capsule.ceiling_bytes
    )
    if initial.capsule is None:
        if initial.refusal is not None and initial.refusal.reason == "invalid-capsule":
            return _refusal("invalid-capsule", initial.refusal.detail)
        return _refusal("invalid-predecessor", "predecessor cannot reproduce the selected context")
    expected_capsule = initial.capsule
    if capsule.expansion is not None:
        expanded = expand_candidate_context(
            predecessor,
            expected_capsule,
            capsule.expansion.inventory_entry,
        )
        if expanded.capsule is None:
            return _refusal("invalid-capsule", "capsule expansion cannot be reproduced")
        expected_capsule = expanded.capsule
    if capsule != expected_capsule or receipt != expected_capsule.receipt:
        return _refusal(
            "invalid-bindings",
            "capsule, receipt, predecessor, and selected feedback must bind exactly",
        )

    return _parse_predecessor_artifacts(predecessor, stages)


def _parse_predecessor_artifacts(
    predecessor: ResolvedRoadmapVersion, stages: Sequence[RoadmapStage]
) -> tuple[dict[str, RoadmapArtifact], tuple[bytes, ...]] | CandidateRefusal:
    artifacts: dict[str, RoadmapArtifact] = {}
    bytes_by_stage: list[bytes] = []
    try:
        for stage, data, member in zip(
            stages,
            predecessor.artifact_bytes,
            predecessor.record.artifact_members,
            strict=True,
        ):
            if not isinstance(data, bytes) or member.artifact_key != stage.artifact_key:
                return _refusal(
                    "invalid-predecessor", "predecessor artifact members do not bind stages"
                )
            if hashlib.sha256(data).hexdigest() != member.digest:
                return _refusal(
                    "invalid-predecessor", "predecessor bytes do not match stored digests"
                )
            text = data.decode("utf-8")
            artifact = cast(RoadmapArtifact, stage.parse(text))
            artifacts[stage.artifact_key] = artifact
            bytes_by_stage.append(data)
    except (AttributeError, RoadmapArtifactError, TypeError, UnicodeDecodeError, ValueError):
        return _refusal("invalid-predecessor", "predecessor stored artifacts cannot be parsed")
    return artifacts, tuple(bytes_by_stage)


def _validate_batch_response(
    delta: CandidateDelta, capsule: CandidateContextBatchCapsule
) -> CandidateResponsePatch | CandidateRefusal:
    """Require one response for every issued snapshot, without reading a ledger."""
    snapshots = capsule.reviewer_items
    expected_ids = tuple(item.item_id for item in snapshots)
    if len(set(expected_ids)) != len(expected_ids):
        return _refusal("invalid-bindings", "issued reviewer batch has duplicate item ids")
    if set(entry.item_id for entry in delta.responses) != set(expected_ids):
        return _refusal("invalid-bindings", "responses must cover all and only admitted reviewer items")
    by_id = {entry.item_id: entry for entry in delta.responses}
    return CandidateResponsePatch(
        entries=tuple(
            CandidateResponsePatchEntry(item=item, response=by_id[item.item_id].response)
            for item in snapshots
        )
    )


def _full_member_authority(
    capsule: CandidateContextCapsule,
) -> dict[tuple[str, str, str], object]:
    return {
        (
            member.identity.artifact_key,
            member.identity.row_type,
            member.identity.row_id,
        ): member.row
        for member in capsule.full_members
    }


def _prepare_operations(
    operations: tuple[CandidateDeltaOperation, ...],
    *,
    predecessor_artifacts: Mapping[str, RoadmapArtifact],
    stages: Sequence[RoadmapStage],
) -> tuple[CandidateDeltaOperation, ...] | CandidateRefusal:
    stage_indexes = {stage.artifact_key: index for index, stage in enumerate(stages)}
    collection_indexes: dict[str, dict[str, int]] = {}
    for stage in stages:
        collection_indexes[stage.artifact_key] = {
            collection: index
            for index, (collection, _rows) in enumerate(
                _ordered_stage_collections(predecessor_artifacts[stage.artifact_key])
            )
        }
        artifact = predecessor_artifacts[stage.artifact_key]
        if isinstance(artifact, ConstraintsArtifact) and artifact.stack is None:
            # An add may introduce the unrecorded stack; it sorts last, as when recorded.
            collection_indexes[stage.artifact_key]["stack"] = len(
                collection_indexes[stage.artifact_key]
            )

    targeted_rows: set[tuple[str, str, str]] = set()
    for operation in operations:
        if (
            operation.artifact_key not in stage_indexes
            or operation.artifact_key not in predecessor_artifacts
            or operation.row_type not in collection_indexes[operation.artifact_key]
        ):
            return _refusal(
                "invalid-operation", "candidate operation targets no stage row collection"
            )
        target_id = operation.row.id if isinstance(operation, CandidateAddRow) else operation.row_id
        target = (operation.artifact_key, operation.row_type, target_id)
        if target in targeted_rows:
            return _refusal("invalid-operation", "candidate delta cannot target one row twice")
        targeted_rows.add(target)
        if isinstance(operation, CandidateAddRow):
            if type(operation.row) is not _expected_row_type(operation.row_type):
                return _refusal("invalid-operation", "candidate addition has the wrong typed row")
        elif isinstance(operation, CandidateReplaceRow):
            if type(operation.row) is not _expected_row_type(operation.row_type):
                return _refusal(
                    "invalid-operation", "candidate replacement has the wrong typed row"
                )

    def sort_key(operation: CandidateDeltaOperation) -> tuple[int, int, str, int]:
        target_id = operation.row.id if isinstance(operation, CandidateAddRow) else operation.row_id
        return (
            stage_indexes[operation.artifact_key],
            collection_indexes[operation.artifact_key][operation.row_type],
            target_id,
            0
            if isinstance(operation, CandidateRemoveRow)
            else 1
            if isinstance(operation, CandidateReplaceRow)
            else 2,
        )

    return _order_plan_additions_by_dependency(tuple(sorted(operations, key=sort_key)))


def _order_plan_additions_by_dependency(
    operations: tuple[CandidateDeltaOperation, ...],
) -> tuple[CandidateDeltaOperation, ...]:
    """Put each added plan after the added plans its ordering entry references
    (``depends_on`` and ``assumption_targets``, which the ordering gate requires
    earlier), since each addition appends its entry. Taking the smallest ready id
    keeps an already-valid id order unchanged. Only mutually reachable plans (a
    cycle) are placed by id among themselves, so every reference left not earlier
    lies on a cycle, and the ordering gate refuses it."""
    slots = [
        index
        for index, operation in enumerate(operations)
        if isinstance(operation, CandidateAddRow) and operation.row_type == "plans"
    ]
    additions = {
        cast(PlanRow, operation.row).id: operation
        for operation in (cast(CandidateAddRow, operations[index]) for index in slots)
    }
    references = {
        plan_id: {
            referenced_id
            for referenced_id in (
                (*operation.ordering.depends_on, *operation.ordering.assumption_targets)
                if operation.ordering
                else ()
            )
            if referenced_id in additions
        }
        for plan_id, operation in additions.items()
    }
    reachable: dict[str, set[str]] = {}
    for plan_id in references:
        seen: set[str] = set()
        frontier = list(references[plan_id])
        while frontier:
            referenced_id = frontier.pop()
            if referenced_id not in seen:
                seen.add(referenced_id)
                frontier.extend(references[referenced_id])
        reachable[plan_id] = seen
    groups = {
        plan_id: frozenset(
            {plan_id} | {other for other in reachable[plan_id] if plan_id in reachable[other]}
        )
        for plan_id in references
    }
    pending = {
        group: {groups[referenced_id] for member in group for referenced_id in references[member]} - {group}
        for group in set(groups.values())
    }
    ordered: list[str] = []
    while pending:
        group = min((group for group, needed in pending.items() if not needed), key=min)
        ordered.extend(sorted(group))
        del pending[group]
        for needed in pending.values():
            needed.discard(group)
    result = list(operations)
    for index, plan_id in zip(slots, ordered, strict=True):
        result[index] = additions[plan_id]
    return tuple(result)


def _expected_row_type(row_type: str) -> type[StageRow]:
    types: Mapping[str, type[StageRow]] = {
        "entities": EntityRow,
        "business_rules": BusinessRuleRow,
        "workflows": WorkflowRow,
        "decisions": DecisionRow,
        "dispositions": AttributeDispositionRow,
        "constraints": ConstraintRow,
        "hosting": HostingRow,
        "system_patterns": PatternRow,
        "component_patterns": PatternRow,
        "stores": StoreRow,
        "stack": StackRow,
        "components": ComponentRow,
        "plans": PlanRow,
        "assumptions": AssumptionRow,
    }
    return types[row_type]


def _validate_operation_authority(
    operations: tuple[CandidateDeltaOperation, ...],
    *,
    predecessor_artifacts: Mapping[str, RoadmapArtifact],
    authority: Mapping[tuple[str, str, str], object],
    feedback_ids: tuple[str, ...] | None = None,
    selected_feedback: CandidateContextFeedback | None = None,
) -> CandidateRefusal | None:
    if feedback_ids is None:
        if selected_feedback is None:
            return _refusal("invalid-bindings", "candidate operation authority has no reviewer binding")
        feedback_ids = (selected_feedback.feedback_id,)
    for operation in operations:
        if operation.feedback_id not in feedback_ids:
            return _refusal(
                "invalid-bindings", "every candidate operation must bind an admitted reviewer item"
            )
        artifact = predecessor_artifacts[operation.artifact_key]
        if isinstance(operation, CandidateAddRow):
            if operation.row_type == "decisions" and operation.row.source is not None:
                return _refusal("invalid-operation", "candidate cannot add an inherited decision")
            if operation.row_type == "plans":
                if operation.ordering is None or operation.ordering.plan_id != operation.row.id:
                    return _refusal(
                        "invalid-operation",
                        "a plan addition requires its matching ordering entry",
                    )
            elif operation.ordering is not None:
                return _refusal(
                    "invalid-operation",
                    "only a plan addition may carry an ordering entry",
                )
            continue

        existing = _find_existing_row(artifact, operation.row_type, operation.row_id)
        if isinstance(existing, CandidateRefusal):
            return existing
        if isinstance(existing, DecisionRow) and existing.source is not None:
            return _refusal("invalid-operation", "candidate cannot change an inherited decision")
        authority_key = (
            operation.artifact_key,
            type(existing).__name__,
            operation.row_id,
        )
        if authority.get(authority_key) != existing:
            return _refusal(
                "unauthorized-existing-row",
                "existing rows require exact full-content capsule membership",
            )
        if isinstance(operation, CandidateReplaceRow):
            if not stage_row_edit_preserves_fixed_fields(
                existing, cast(StageRow, operation.row), row_type=operation.row_type
            ):
                fixed = ", ".join(
                    repr(field)
                    for field in stage_row_operation_policy(operation.row_type).immutable_fields
                )
                return _refusal(
                    "invalid-operation",
                    f"{operation.row_type} replacement {operation.row_id!r} changes its "
                    f"fixed field {fixed}",
                )
            continue

        if operation.row_type == "plans":
            if operation.ordering is None or operation.ordering.plan_id != operation.row_id:
                return _refusal(
                    "invalid-operation",
                    "a plan removal requires its matching ordering entry",
                )
            try:
                current_ordering = _find_ordering_entry(
                    cast(PlansArtifact, artifact), operation.row_id
                )
            except (TypeError, ValueError):
                return _refusal(
                    "invalid-operation",
                    "plan removal requires one exact predecessor ordering entry",
                )
            if operation.ordering != current_ordering:
                return _refusal(
                    "invalid-operation",
                    "plan removal ordering entry must match the predecessor exactly",
                )
        elif operation.ordering is not None:
            return _refusal(
                "invalid-operation",
                "only a plan removal may carry an ordering entry",
            )
    return None


def _find_existing_row(
    artifact: RoadmapArtifact, row_type: str, row_id: str
) -> StageRow | CandidateRefusal:
    try:
        rows = stage_row_collections(artifact)[row_type]
    except KeyError:
        return _refusal("invalid-operation", "candidate operation targets no stage row collection")
    matches = tuple(row for row in rows if row.id == row_id)
    if len(matches) != 1:
        return _refusal(
            "invalid-operation", "candidate operation must target exactly one predecessor row"
        )
    return matches[0]


def _classify_validated_operations(
    operations: tuple[CandidateDeltaOperation, ...],
    *,
    predecessor_artifacts: Mapping[str, RoadmapArtifact],
) -> CandidateOperationClassification:
    """Classify validated operations without changing their authority or outcome."""
    for operation in operations:
        if not isinstance(operation, CandidateReplaceRow):
            return CandidateOperationClassification.STRUCTURAL
        predecessor = _find_existing_row(
            predecessor_artifacts[operation.artifact_key], operation.row_type, operation.row_id
        )
        assert not isinstance(predecessor, CandidateRefusal)
        allowed_fields = TEXT_FIELDS_BY_ROW_TYPE.get(operation.row_type, ())
        changed_fields = {
            field.name
            for field in fields(predecessor)
            if getattr(predecessor, field.name) != getattr(operation.row, field.name)
        }
        if not changed_fields.issubset(allowed_fields):
            return CandidateOperationClassification.STRUCTURAL
    return CandidateOperationClassification.PRESENTATION_ONLY


def _find_ordering_entry(artifact: PlansArtifact, plan_id: str) -> OrderingEntry:
    matches = tuple(entry for entry in artifact.ordering if entry.plan_id == plan_id)
    if len(matches) != 1:
        raise ValueError("plan ordering entry must occur exactly once")
    return matches[0]


def _apply_operation(
    artifact: RoadmapArtifact, operation: CandidateDeltaOperation
) -> RoadmapArtifact:
    if isinstance(operation, CandidateAddRow):
        result = append_stage_row(
            artifact, collection=operation.row_type, row=cast(StageRow, operation.row)
        )
        if operation.row_type == "plans":
            return append_plan_ordering_entry(
                cast(PlansArtifact, result), cast(OrderingEntry, operation.ordering)
            )
        return result
    if isinstance(operation, CandidateReplaceRow):
        return replace_stage_row(
            artifact,
            collection=operation.row_type,
            row_id=operation.row_id,
            row=cast(StageRow, operation.row),
        )
    result = remove_stage_row(artifact, collection=operation.row_type, row_id=operation.row_id)
    if operation.row_type == "plans":
        return remove_plan_ordering_entry(cast(PlansArtifact, result), plan_id=operation.row_id)
    return result


class _ResolvedCorrection(NamedTuple):
    """One correction bound to the predecessor offsets of the span it names."""

    operation: CandidateCorrectProse
    stage_index: int
    start: int
    end: int


def _resolve_corrections(
    corrections: tuple[CandidateCorrectProse, ...],
    *,
    row_operations: tuple[CandidateDeltaOperation, ...],
    predecessor_artifacts: Mapping[str, RoadmapArtifact],
    capsule: CandidateContextCapsule,
    feedback_ids: tuple[str, ...],
    stages: Sequence[RoadmapStage],
) -> tuple[_ResolvedCorrection, ...] | CandidateRefusal:
    """Bind each correction to its capsule-issued span; the model supplies only the id.

    Refusal details lead with the value ROADMAP_FORMAT.md § Shared-narrative
    correction names, so an operator can tell the cases apart.
    """
    if not corrections:
        return ()
    stage_indexes = {stage.artifact_key: index for index, stage in enumerate(stages)}
    members_by_artifact: dict[str, set[str]] = {}
    issued: dict[tuple[str, str], CandidateContextSourceSpan] = {}
    for member in capsule.full_members:
        artifact_key = member.identity.artifact_key
        members_by_artifact.setdefault(artifact_key, set()).add(member.identity.row_id)
        for span in member.source_spans:
            issued[(artifact_key, span.span_id)] = span

    seen: set[tuple[str, str]] = set()
    resolved: list[_ResolvedCorrection] = []
    for operation in corrections:
        if operation.feedback_id not in feedback_ids:
            return _refusal(
                "invalid-bindings", "unauthorized: a correction must bind an admitted reviewer item"
            )
        if operation.artifact_key not in stage_indexes or operation.artifact_key not in predecessor_artifacts:
            return _refusal("invalid-operation", "unknown: a correction targets no stage artifact")
        problem = _correct_prose_replacement_problem(operation.replacement)
        if problem is not None:
            return _refusal("invalid-operation", f"oversized: {problem}")
        key = (operation.artifact_key, operation.span_id)
        if key in seen:
            return _refusal("invalid-operation", "duplicate: two corrections target one span")
        seen.add(key)
        span = issued.get(key)
        if span is None:
            return _refusal("invalid-operation", "unknown: the span id names no issued span")
        owners = span.owning_row_ids or (span.row_id,)
        visible_ids = members_by_artifact.get(operation.artifact_key, set())
        if any(owner not in visible_ids for owner in owners):
            return _refusal(
                "invalid-bindings",
                "unauthorized: every owning row of a span must be a full capsule member",
            )
        artifact = predecessor_artifacts[operation.artifact_key]
        matches = [
            candidate
            for candidate in project_row_owned_prose_spans(artifact, visible_ids)
            if candidate.span_id == span.span_id
        ]
        if len(matches) > 1:
            return _refusal("invalid-operation", "ambiguous: the issued span text occurs more than once")
        if (
            not matches
            or matches[0].text != span.text
            or hashlib.sha256(span.text.encode("utf-8")).hexdigest() != span.digest
            or stage_prose_span_id(owners[0], span.text, owning_row_ids=owners) != span.span_id
            or tuple(sorted(matches[0].owning_row_ids)) != tuple(sorted(owners))
        ):
            return _refusal("invalid-operation", "stale: the span no longer matches the predecessor body")
        for row_operation in row_operations:
            target_id = (
                row_operation.row.id
                if isinstance(row_operation, CandidateAddRow)
                else cast(CandidateReplaceRow | CandidateRemoveRow, row_operation).row_id
            )
            if row_operation.artifact_key == operation.artifact_key and target_id in owners:
                return _refusal(
                    "invalid-operation",
                    "owning-set-interaction: a candidate cannot change a row in a corrected span's owning set",
                )
        resolved.append(
            _ResolvedCorrection(
                operation, stage_indexes[operation.artifact_key], matches[0].start, matches[0].end
            )
        )

    resolved.sort(key=lambda item: (item.stage_index, item.start, item.operation.span_id))
    for artifact_key in {item.operation.artifact_key for item in resolved}:
        try:  # the shared splice owns the overlap rule; the result is discarded here
            splice_exact_spans(
                predecessor_artifacts[artifact_key].body,
                [
                    (item.start, item.end, item.operation.replacement)
                    for item in resolved
                    if item.operation.artifact_key == artifact_key
                ],
            )
        except RevisionMergeError:
            return _refusal("invalid-operation", "overlapping: two corrections cover intersecting spans")
    return tuple(resolved)


def _with_span_line_ending(replacement: str, span_text: str) -> str:
    """Give the replacement the span's own trailing newlines so the blank separator survives."""
    return replacement.rstrip("\n") + span_text[len(span_text.rstrip("\n")) :]


def _apply_corrections(
    artifacts: Mapping[str, RoadmapArtifact],
    corrections: Sequence[_ResolvedCorrection],
    *,
    predecessor_artifacts: Mapping[str, RoadmapArtifact],
) -> dict[str, RoadmapArtifact]:
    """Splice corrections into the predecessor body, before any add-row fragment appends."""
    corrected = dict(artifacts)
    for artifact_key in dict.fromkeys(item.operation.artifact_key for item in corrections):
        artifact = corrected[artifact_key]
        if artifact.body != predecessor_artifacts[artifact_key].body:
            raise ValueError("a correction's offsets bind the predecessor body, which changed")
        corrected[artifact_key] = replace(
            artifact,
            body=splice_exact_spans(
                artifact.body,
                [
                    (
                        item.start,
                        item.end,
                        _with_span_line_ending(
                            item.operation.replacement, artifact.body[item.start : item.end]
                        ),
                    )
                    for item in corrections
                    if item.operation.artifact_key == artifact_key
                ],
            ),
        )
    return corrected


def _apply_operations_in_contract_order(
    predecessor_artifacts: Mapping[str, RoadmapArtifact],
    prepared: Sequence[CandidateDeltaOperation],
    corrections: Sequence[_ResolvedCorrection],
) -> dict[str, RoadmapArtifact]:
    """Apply typed-row operations, then corrections, then add-row appends.

    Materialization and stored-candidate replay share this one body so they cannot drift.
    """
    artifacts = dict(predecessor_artifacts)
    for operation in prepared:
        artifacts[operation.artifact_key] = _apply_operation(
            artifacts[operation.artifact_key], operation
        )
    artifacts = _apply_corrections(
        artifacts, corrections, predecessor_artifacts=predecessor_artifacts
    )
    return _append_added_row_prose(artifacts, prepared)


def _append_added_row_prose(
    artifacts: Mapping[str, RoadmapArtifact], operations: Sequence[CandidateDeltaOperation]
) -> dict[str, RoadmapArtifact]:
    """Append validated addition fragments in the normalized operation order."""
    amended = dict(artifacts)
    for operation in operations:
        if not isinstance(operation, CandidateAddRow) or operation.prose_amendment is None:
            continue
        artifact = amended[operation.artifact_key]
        amended[operation.artifact_key] = replace(
            artifact,
            body=append_row_prose_fragments(artifact.body, (operation.prose_amendment.fragment,)),
        )
    return amended


def _validate_relation_authority(
    *,
    predecessor_artifacts: Mapping[str, RoadmapArtifact],
    candidate_artifacts: Mapping[str, RoadmapArtifact],
    operations: tuple[CandidateDeltaOperation, ...],
    authority: Mapping[tuple[str, str, str], object],
    capsule: CandidateContextCapsule,
) -> CandidateRefusal | None:
    before = extract_declared_relations(**predecessor_artifacts)
    after = extract_declared_relations(**candidate_artifacts)
    relation_atoms = _relation_occurrence_atoms(before=before, after=after)
    added = tuple(
        atom.relation for atom in relation_atoms if atom.direction == "added"
    )
    removed = tuple(
        atom.relation for atom in relation_atoms if atom.direction == "removed"
    )

    removed_rows = {
        (operation.artifact_key, operation.row_id)
        for operation in operations
        if isinstance(operation, CandidateRemoveRow)
    }
    added_rows = {
        (operation.artifact_key, operation.row.id)
        for operation in operations
        if isinstance(operation, CandidateAddRow)
    }
    # A stack row declares no relation, so it has no anchor to reach: the add
    # is authorized by its feedback alone (stack totality is a gate's job).
    anchorless_added_rows = {
        (operation.artifact_key, operation.row.id)
        for operation in operations
        if isinstance(operation, CandidateAddRow) and operation.row_type in _ANCHORLESS_ADD_ROW_TYPES
    }
    replaced_rows = {
        (operation.artifact_key, operation.row_id)
        for operation in operations
        if isinstance(operation, CandidateReplaceRow)
    }
    for artifact_key, row_id in removed_rows:
        if any(_relation_touches(relation, artifact_key, row_id) for relation in after):
            return _refusal(
                "relation-authority",
                "removing a row must remove every incident declared relation",
            )
    if any(
        (relation.owner_artifact_key, relation.owner_id) not in added_rows | replaced_rows
        for relation in added
    ):
        return _refusal(
            "relation-authority",
            "declared relations require an authorized owning operation",
        )
    if any(
        (relation.owner_artifact_key, relation.owner_id) not in removed_rows | replaced_rows
        for relation in removed
    ):
        return _refusal(
            "relation-authority",
            "declared relations require an authorized owning operation",
        )

    predecessor_rows = _predecessor_row_identities(predecessor_artifacts)
    candidate_rows = _predecessor_row_identities(candidate_artifacts)
    for relation in (*added, *removed):
        owner_identity = tuple(
            identity
            for identity in predecessor_rows.get(relation.owner_id, ())
            if identity[0] == relation.owner_artifact_key
        )
        endpoint_identities = predecessor_rows.get(relation.endpoint_id, ())
        same_batch_endpoint = _same_batch_added_endpoint_identity(
            relation,
            operations=operations,
            candidate_rows=candidate_rows,
        )
        if not endpoint_identities and not (
            isinstance(capsule, CandidateContextBatchCapsule)
            and same_batch_endpoint is not None
        ):
            return _refusal(
                "unauthorized-addition"
                if (relation.owner_artifact_key, relation.owner_id) in added_rows
                else "relation-authority",
                _unresolved_relation_detail(
                    relation, batch=isinstance(capsule, CandidateContextBatchCapsule)
                ),
            )
        if (
            not owner_identity
            and (relation.owner_artifact_key, relation.owner_id) not in added_rows
        ):
            return _refusal(
                "relation-authority",
                "every affected declared relation endpoint requires predecessor membership",
            )
        for identity in _predecessor_relation_members(relation, predecessor_rows):
            if identity not in authority:
                return _refusal(
                    "relation-authority",
                    "every affected predecessor relation endpoint requires full membership",
                )

    evidence_nodes = {
        (node.artifact_key, node.row_id)
        for evidence in capsule.relation_evidence
        for node in (evidence.owner, evidence.endpoint)
    }
    reached_members = {
        (member.identity.artifact_key, member.identity.row_type, member.identity.row_id)
        for member in capsule.full_members
        if any(
            reason in {"feedback-closure", "inventory-expansion"}
            for reason in member.inclusion_reasons
        )
    }
    return _refuse_unanchored_additions(
        operations=operations,
        added=added,
        anchorless_added_rows=anchorless_added_rows,
        predecessor_rows=predecessor_rows,
        candidate_rows=candidate_rows,
        reached_members=reached_members,
        evidence_nodes=evidence_nodes,
        batch=isinstance(capsule, CandidateContextBatchCapsule),
    )


def _refuse_unanchored_additions(
    *,
    operations: tuple[CandidateDeltaOperation, ...],
    added: tuple[RoadmapRelation, ...],
    anchorless_added_rows: set[tuple[str, str]],
    predecessor_rows: Mapping[str, tuple[tuple[str, str, str], ...]],
    candidate_rows: Mapping[str, tuple[tuple[str, str, str], ...]],
    reached_members: set[tuple[str, str, str]],
    evidence_nodes: set[tuple[str, str]],
    batch: bool,
) -> CandidateRefusal | None:
    """Refuse an added row that no reached predecessor row grounds.

    The reached set grows from reached predecessor rows: an added row is reached by an
    outgoing relation to a reached predecessor row or to a reached added row, or by an
    incoming relation from a reached predecessor owner. A group of added rows that only
    cite each other never enters it. See ROADMAP_FORMAT.md § "Candidate row anchors"."""

    def reached_predecessor(identity: tuple[str, str, str]) -> bool:
        return identity in reached_members or (identity[0], identity[2]) in evidence_nodes

    def added_endpoint(relation: RoadmapRelation) -> tuple[str, str] | None:
        identity = (
            _same_batch_added_endpoint_identity(
                relation, operations=operations, candidate_rows=candidate_rows
            )
            if batch
            else None
        )
        return None if identity is None else (identity[0], identity[2])

    added_order = tuple(
        dict.fromkeys(
            (operation.artifact_key, operation.row.id)
            for operation in operations
            if isinstance(operation, CandidateAddRow)
        )
    )
    added_keys = set(added_order)
    added_endpoints = {id(relation): added_endpoint(relation) for relation in added}
    outgoing: dict[tuple[str, str], list[RoadmapRelation]] = {}
    for relation in added:
        outgoing.setdefault((relation.owner_artifact_key, relation.owner_id), []).append(relation)

    def grounded_in_predecessor(relation: RoadmapRelation) -> bool:
        # An added owner never lends its own id: a colliding predecessor row is not its anchor.
        members = (
            predecessor_rows.get(relation.endpoint_id, ())
            if (relation.owner_artifact_key, relation.owner_id) in added_keys
            else _predecessor_relation_members(relation, predecessor_rows)
        )
        return any(reached_predecessor(identity) for identity in members)

    # An existing reached owner that now cites an added row grounds that row. `added_endpoint`
    # is None off the batch route, so a single-feedback candidate never reaches this rule.
    reached_added = set(anchorless_added_rows)
    for relation in added:
        target = added_endpoints[id(relation)]
        if target is None or (relation.owner_artifact_key, relation.owner_id) in added_keys:
            continue
        if any(
            identity[0] == relation.owner_artifact_key and reached_predecessor(identity)
            for identity in predecessor_rows.get(relation.owner_id, ())
        ):
            reached_added.add(target)
    changed = True
    while changed:
        changed = False
        for key in added_order:
            if key in reached_added:
                continue
            if any(
                grounded_in_predecessor(relation) or added_endpoints[id(relation)] in reached_added
                for relation in outgoing.get(key, ())
            ):
                reached_added.add(key)
                changed = True

    for key in added_order:
        if key in anchorless_added_rows:
            continue
        if key not in reached_added:
            return _refusal(
                "unauthorized-addition",
                f"{key[0]} row {_quoted_safe_id(key[1]) or '(row identity unavailable)'}: "
                "an added row requires a reached context anchor — relate it to a reached "
                "existing row, or have a reached existing row relate to it",
            )
        for relation in outgoing.get(key, ()):
            if (
                not grounded_in_predecessor(relation)
                and added_endpoints[id(relation)] not in reached_added
            ):
                return _refusal(
                    "unauthorized-addition",
                    f"{relation.owner_artifact_key} row "
                    f"{_quoted_safe_id(relation.owner_id) or '(row identity unavailable)'}: "
                    f"{relation.kind.value}; each added row relation requires a reached "
                    f"context anchor — reference "
                    f"{_quoted_safe_id(relation.endpoint_id) or '(identity unavailable)'} "
                    "is not a reached row",
                )
    return None


_RELATION_ENDPOINT_IDENTITIES: Final[Mapping[RelationKind, tuple[tuple[str, str], ...]]] = {
    RelationKind.FIELD_ENTITY: (("domain", "EntityRow"),),
    RelationKind.BUSINESS_RULE_ENTITY: (("domain", "EntityRow"),),
    RelationKind.WORKFLOW_ENTITY: (("domain", "EntityRow"),),
    RelationKind.COMPONENT_ENTITY: (("domain", "EntityRow"),),
    RelationKind.COMPONENT_PATTERN: (("components", "PatternRow"),),
    RelationKind.COMPONENT_CONSTRAINT: (("constraints", "ConstraintRow"),),
    RelationKind.COMPONENT_STORE: (("components", "StoreRow"),),
    RelationKind.PLAN_COMPONENT: (("components", "ComponentRow"),),
    RelationKind.ORDERING_DEPENDS_ON: (("plans", "PlanRow"),),
    RelationKind.ORDERING_ASSUMPTION_TARGET: (("plans", "PlanRow"),),
    RelationKind.ASSUMPTION_CONSUMING_PLAN: (("plans", "PlanRow"),),
    # A constraint's anchor_ids resolve against three domain row types, not
    # one (see check_constraint_anchors' `anchorable` set) — every accepted
    # type has to be listed, or a same-batch addition of the omitted type(s)
    # would authorize by row id alone with no type/artifact check.
    RelationKind.CONSTRAINT_ANCHOR: (
        ("domain", "EntityRow"),
        ("domain", "BusinessRuleRow"),
        ("domain", "WorkflowRow"),
    ),
    # RelationKind.DECISION_ANCHOR is deliberately absent: check_decision_records'
    # `resolvable` set spans every row carried by the envelope, across
    # whichever artifacts are in scope for the stage — not a fixed
    # (artifact, row type) pair — so the any-row-any-artifact fallback below
    # already matches its real resolution semantics.
}


_ROW_TYPE_PHRASE: Final[Mapping[str, str]] = {
    "EntityRow": "entity",
    "BusinessRuleRow": "business rule",
    "WorkflowRow": "workflow",
    "PatternRow": "pattern",
    "ConstraintRow": "constraint",
    "StoreRow": "store",
    "ComponentRow": "component",
    "PlanRow": "plan",
}


def _unresolved_relation_detail(relation: RoadmapRelation, *, batch: bool) -> str:
    """Closed wording for a relation citing an id no permitted row defines.

    Only the relation kind (an enum value), the artifact key (a code constant), and
    validated ids are echoed; the expected row type comes from the endpoint table.
    A batch may cite a row added in the same batch; a single-feedback candidate may not."""
    expected = _RELATION_ENDPOINT_IDENTITIES.get(relation.kind)
    # A type without a phrase is omitted, degrading to "row": a refusal must never raise.
    # test_every_endpoint_table_row_type_has_a_phrase... requires full coverage.
    phrases = [
        _ROW_TYPE_PHRASE[row_type]
        for _artifact_key, row_type in expected or ()
        if row_type in _ROW_TYPE_PHRASE
    ]
    if len(phrases) > 2:
        kind_phrase = f"{', '.join(phrases[:-1])}, or {phrases[-1]}"
    else:
        kind_phrase = " or ".join(phrases)
    wanted = f"{kind_phrase} row" if kind_phrase else "row"
    owner = _quoted_safe_id(relation.owner_id)
    endpoint = _quoted_safe_id(relation.endpoint_id)
    remedy = (
        f"cite an existing {wanted}, add that {wanted} in this batch (an added row must be "
        f"grounded in a reached row), or drop the reference"
        if batch
        else f"cite an existing {wanted}, or drop the reference "
        f"(a row added in this same candidate cannot be cited)"
    )
    return (
        f"{relation.owner_artifact_key} row {owner or '(row identity unavailable)'}: "
        f"{relation.kind.value}; reference {endpoint or '(identity unavailable)'} "
        f"names no {wanted} it may cite — {remedy}"
    )


def _same_batch_added_endpoint_identity(
    relation: RoadmapRelation,
    *,
    operations: tuple[CandidateDeltaOperation, ...],
    candidate_rows: Mapping[str, tuple[tuple[str, str, str], ...]],
) -> tuple[str, str, str] | None:
    """Return an exact added endpoint that matches this relation's typed target."""
    expected = _RELATION_ENDPOINT_IDENTITIES.get(relation.kind)
    identities = (
        tuple(
            (artifact_key, row_type, relation.endpoint_id)
            for artifact_key, row_type in expected
        )
        if expected is not None
        else candidate_rows.get(relation.endpoint_id, ())
    )
    exact_additions = tuple(
        identity
        for identity in identities
        if any(
            isinstance(operation, CandidateAddRow)
            and (operation.artifact_key, type(operation.row).__name__, operation.row.id) == identity
            for operation in operations
        )
    )
    if len(exact_additions) != 1:
        return None
    identity = exact_additions[0]
    return identity if identity in candidate_rows.get(relation.endpoint_id, ()) else None


def _relation_occurrence_atoms(
    *, before: tuple[RoadmapRelation, ...], after: tuple[RoadmapRelation, ...]
) -> tuple[CandidateRelationImpactAtom, ...]:
    """Return unmatched relation occurrences without collapsing duplicates."""
    return tuple(
        CandidateRelationImpactAtom(
            direction=occurrence.direction,
            source_index=occurrence.source_index,
            relation=occurrence.relation,
        )
        for occurrence in relation_occurrence_diffs(before=before, after=after)
    )


def _candidate_impact_atoms(
    predecessor_diff: CandidatePredecessorDiff,
    relation_atoms: tuple[CandidateRelationImpactAtom, ...],
) -> tuple[CandidateImpactAtom, ...]:
    """Return the one ordered atom stream used for identity and containment."""
    row_atoms = tuple(
        CandidateRowImpactAtom(
            artifact_key=row.artifact_key,
            row_type=row.row_type,
            row_id=row.row_id,
            before=_project_declared_relations(row.before),
            after=_project_declared_relations(row.after),
        )
        for row in predecessor_diff.changed_rows
    )
    return (*row_atoms, *relation_atoms)


def candidate_impact_atoms_for_diff(
    predecessor_diff: CandidatePredecessorDiff,
    *,
    before_relations: tuple[RoadmapRelation, ...],
    after_relations: tuple[RoadmapRelation, ...],
) -> tuple[CandidateImpactAtom, ...]:
    """Recompute the complete impact stream from typed predecessor and candidate facts."""
    return _candidate_impact_atoms(
        predecessor_diff,
        _relation_occurrence_atoms(before=before_relations, after=after_relations),
    )


def candidate_impact_identity(impact_atoms: tuple[CandidateImpactAtom, ...]) -> str:
    """Return the immutable identity for one replacement's derived impact stream."""
    return hashlib.sha256(
        _canonical_json_bytes({"schema_version": 1, "impact_atoms": _wire_value(impact_atoms)})
    ).hexdigest()


def review_requirement_contains_impact(
    requirement: CandidateReviewRequirement,
    replacement_impact_atoms: tuple[CandidateImpactAtom, ...],
) -> bool:
    """Require each replacement atom no more often than its disclosed counterpart."""
    disclosed_counts = Counter(_containment_atom_key(atom) for atom in requirement.impact_atoms)
    replacement_counts = Counter(_containment_atom_key(atom) for atom in replacement_impact_atoms)
    return all(count <= disclosed_counts[key] for key, count in replacement_counts.items())


def _containment_atom_key(atom: CandidateImpactAtom) -> bytes:
    """Ignore a relation occurrence's retained source position for multiset containment."""
    if isinstance(atom, CandidateRelationImpactAtom):
        return _canonical_json_bytes(
            {
                "kind": atom.kind,
                "direction": atom.direction,
                "relation": _wire_value(atom.relation),
            }
        )
    return _canonical_json_bytes(_wire_value(atom))


def _candidate_diff_requires_review_requirement(diff: CandidatePredecessorDiff) -> bool:
    """Recognize the one declared-relation impact that requires review."""
    replaced_rows = {
        (row.artifact_key, row.row_id)
        for row in diff.changed_rows
        if row.before is not None and row.after is not None
    }
    return any(
        (relation.relation.owner_artifact_key, relation.relation.owner_id) in replaced_rows
        for relation in (*diff.added_relations, *diff.removed_relations)
    )


def _project_declared_relations(value: object | None) -> object | None:
    """Retain only row facts independent of declared relation values."""
    if value is None:
        return None
    if isinstance(value, EntityRow):
        return replace(
            value,
            fields=tuple(
                replace(field, entity_id=None)
                if field.type is FieldType.REFERENCE
                else field
                for field in value.fields
            ),
        )
    if isinstance(value, BusinessRuleRow | WorkflowRow):
        return replace(value, entity_ids=())
    if isinstance(value, DecisionRow):
        return replace(value, anchor="")
    if isinstance(value, ConstraintRow):
        return replace(value, anchor_ids=())
    if isinstance(value, ComponentRow):
        return replace(
            value,
            entity_ids=(),
            pattern_ids=(),
            constraint_ids=(),
            store_ids=(),
        )
    if isinstance(value, PlanRow):
        return replace(value, component_ids=())
    if isinstance(value, OrderingEntry):
        return replace(value, depends_on=(), assumption_targets=())
    if isinstance(value, AssumptionRow):
        return replace(value, consuming_plan_ids=())
    return value


def _has_reviewable_existing_row_relation_impact(
    operations: tuple[CandidateDeltaOperation, ...],
    relation_atoms: tuple[CandidateRelationImpactAtom, ...],
) -> bool:
    """Limit the first review reason to impacts owned by surviving rows."""
    replacement_rows = {
        (operation.artifact_key, operation.row_id)
        for operation in operations
        if isinstance(operation, CandidateReplaceRow)
    }
    return any(
        (atom.relation.owner_artifact_key, atom.relation.owner_id) in replacement_rows
        for atom in relation_atoms
    )


def _affected_predecessor_members(
    *,
    capsule: CandidateContextCapsule,
    predecessor_diff: CandidatePredecessorDiff,
    relation_atoms: tuple[CandidateRelationImpactAtom, ...],
    predecessor_rows: Mapping[str, tuple[tuple[str, str, str], ...]],
) -> tuple[CandidateContextFullMember, ...]:
    """Return every changed or relation-affected predecessor member in capsule order."""
    affected: list[tuple[str, str, str]] = []
    for row in predecessor_diff.changed_rows:
        if row.before is not None:
            affected.extend(
                identity
                for identity in predecessor_rows.get(row.row_id, ())
                if identity[0] == row.artifact_key and identity not in affected
            )
    for atom in relation_atoms:
        for identity in _predecessor_relation_members(atom.relation, predecessor_rows):
            if identity not in affected:
                affected.append(identity)
    return tuple(
        member
        for member in capsule.full_members
        if (
            member.identity.artifact_key,
            member.identity.row_type,
            member.identity.row_id,
        )
        in affected
    )


def _relation_touches(relation: RoadmapRelation, artifact_key: str, row_id: str) -> bool:
    return (
        relation.owner_artifact_key == artifact_key and relation.owner_id == row_id
    ) or relation.endpoint_id == row_id


def _predecessor_row_identities(
    artifacts: Mapping[str, RoadmapArtifact],
) -> dict[str, tuple[tuple[str, str, str], ...]]:
    identities: dict[str, list[tuple[str, str, str]]] = {}
    for artifact_key, artifact in artifacts.items():
        for _row_type, rows in _ordered_stage_collections(artifact):
            for row in rows:
                identities.setdefault(row.id, []).append((artifact_key, type(row).__name__, row.id))
    return {row_id: tuple(values) for row_id, values in identities.items()}


def _predecessor_relation_members(
    relation: RoadmapRelation,
    predecessor_rows: Mapping[str, tuple[tuple[str, str, str], ...]],
) -> tuple[tuple[str, str, str], ...]:
    owner = tuple(
        identity
        for identity in predecessor_rows.get(relation.owner_id, ())
        if identity[0] == relation.owner_artifact_key
    )
    return (*owner, *predecessor_rows.get(relation.endpoint_id, ()))


def _assemble_candidate_artifacts(
    *,
    predecessor_artifacts: Mapping[str, RoadmapArtifact],
    candidate_artifacts: Mapping[str, RoadmapArtifact],
    predecessor_bytes: tuple[bytes, ...],
    stages: Sequence[RoadmapStage],
    feedback_free: bool = False,
) -> tuple[CandidateArtifact, ...] | CandidateRefusal:
    assembled: list[CandidateArtifact] = []
    try:
        for stage, raw_bytes in zip(stages, predecessor_bytes, strict=True):
            before = predecessor_artifacts[stage.artifact_key]
            after = candidate_artifacts[stage.artifact_key]
            if feedback_free:
                # Review rows are mutable ledger data.  The stage renderer owns
                # their wire shape, so removing them before rendering proves no
                # reviewer lifecycle value can enter an immutable successor.
                after = replace(after, feedback=(), removals=())
            if before == after:
                data = raw_bytes
                text = data.decode("utf-8")
            else:
                text = stage.render(after)
                data = text.encode("utf-8")
                rendered = stage.parse(text)
                if rendered != after:
                    return _refusal(
                        "render-mismatch",
                        "a changed stage must render and reparse to its retained artifact",
                    )
                if feedback_free and any(getattr(rendered, key) for key in REVIEW_ROW_KEYS):
                    return _refusal(
                        "render-mismatch", "successor artifact retains a reviewer-owned collection"
                    )
            assembled.append(
                CandidateArtifact(
                    artifact_key=stage.artifact_key,
                    data=data,
                    text=text,
                    artifact=after,
                    digest=hashlib.sha256(data).hexdigest(),
                )
            )
    except (AttributeError, RoadmapArtifactError, TypeError, UnicodeError, ValueError):
        return _refusal(
            "render-mismatch", "candidate stage rendering cannot bind complete UTF-8 evidence"
        )
    return tuple(assembled)


def _content_identity(
    *,
    predecessor_version_id: str,
    selected_feedback: CandidateContextFeedback | None,
    receipt: CandidateContextReceipt,
    artifacts: tuple[CandidateArtifact, ...],
    predecessor_diff: CandidatePredecessorDiff,
    response_patch: CandidateResponsePatch | None = None,
    derived_feedback: tuple[CandidateDerivedFeedback, ...] = (),
) -> str:
    preimage = {
        "schema_version": 1,
        "predecessor_version_id": predecessor_version_id,
        "selected_feedback": None if selected_feedback is None else {
            "artifact_key": selected_feedback.artifact_key,
            "feedback_id": selected_feedback.feedback_id,
            "digest": selected_feedback.digest,
        },
        "capsule_receipt": _wire_value(receipt),
        "artifact_digests": [
            {"artifact_key": artifact.artifact_key, "digest": artifact.digest}
            for artifact in artifacts
        ],
        "predecessor_diff": _wire_value(predecessor_diff),
    }
    # Only a batch candidate binds these; selector-era identities were minted without them.
    if response_patch is not None:
        preimage["response_patch"] = _wire_value(response_patch)
        preimage["derived_feedback"] = _wire_value(derived_feedback)
    return hashlib.sha256(_canonical_json_bytes(preimage)).hexdigest()


def _build_review_requirement(
    *,
    predecessor_version_id: str,
    selected_feedback: CandidateContextFeedback,
    receipt: CandidateContextReceipt,
    normalized_operations: tuple[CandidateDeltaOperation, ...],
    predecessor_diff: CandidatePredecessorDiff,
    affected_predecessor_members: tuple[CandidateContextFullMember, ...],
    impact_atoms: tuple[CandidateImpactAtom, ...],
) -> CandidateReviewRequirement:
    """Bind one initial declared-relation disclosure before it is stored."""
    reason: CandidateReviewReason = "declared-relation-impact"
    return CandidateReviewRequirement(
        reason=reason,
        predecessor_version_id=predecessor_version_id,
        selected_feedback=selected_feedback,
        capsule_receipt=receipt,
        normalized_operations=normalized_operations,
        predecessor_diff=predecessor_diff,
        affected_predecessor_members=affected_predecessor_members,
        impact_atoms=impact_atoms,
        initial_disclosed_impact_identity=_review_impact_identity(
            reason=reason,
            predecessor_version_id=predecessor_version_id,
            selected_feedback=selected_feedback,
            receipt=receipt,
            normalized_operations=normalized_operations,
            predecessor_diff=predecessor_diff,
            affected_predecessor_members=affected_predecessor_members,
            impact_atoms=impact_atoms,
        ),
    )


def _review_impact_identity(
    *,
    reason: CandidateReviewReason,
    predecessor_version_id: str,
    selected_feedback: CandidateContextFeedback,
    receipt: CandidateContextReceipt,
    normalized_operations: tuple[CandidateDeltaOperation, ...],
    predecessor_diff: CandidatePredecessorDiff,
    affected_predecessor_members: tuple[CandidateContextFullMember, ...],
    impact_atoms: tuple[CandidateImpactAtom, ...],
) -> str:
    """Return the reproducible identity for one disclosed review impact."""
    preimage = {
        "schema_version": 1,
        "reason": reason,
        "predecessor_version_id": predecessor_version_id,
        "selected_feedback": _wire_value(selected_feedback),
        "capsule_receipt": _wire_value(receipt),
        "normalized_operations": _wire_value(normalized_operations),
        "predecessor_diff": _wire_value(predecessor_diff),
        "affected_predecessor_members": _wire_value(affected_predecessor_members),
        "impact_atoms": _wire_value(impact_atoms),
    }
    return hashlib.sha256(_canonical_json_bytes(preimage)).hexdigest()


def _wire_value(value: object) -> object:
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, BaseModel):
        return {
            name: _wire_value(getattr(value, name))
            for name in value.__class__.model_fields
            # Mirrors roadmap_candidate_context._wire_value: single-owner and legacy spans omit it.
            if not (name == "owning_row_ids" and getattr(value, name) is None)
        }
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _wire_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple | list):
        return [_wire_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _wire_value(item) for key, item in value.items()}
    if value is None or type(value) in {str, int, float, bool}:
        return value
    raise TypeError(f"candidate identity cannot encode {type(value).__name__}")


def _operations_wire_for_reparse(operations: object) -> object:
    """Wire form of parsed operations that the strict parser accepts back.

    `DecisionRow.source` is discovery-only, so a parsed `decisions` row carries `source=None`
    that the parser refuses as an input field; an add-row to a prose-less collection carries
    `prose_amendment=None`, which the parser cannot read back. Identity and digests keep
    `_wire_value`.
    """
    wire = _wire_value(operations)
    for operation in wire if isinstance(wire, list) else ():
        if isinstance(operation, dict) and operation.get("prose_amendment", 0) is None:
            operation.pop("prose_amendment")
        row = operation.get("row") if isinstance(operation, dict) else None
        if isinstance(row, dict) and operation.get("row_type") == "decisions" and row.get("source") is None:
            row.pop("source", None)
    return wire


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _refusal(reason: CandidateRefusalReason, detail: str) -> CandidateRefusal:
    return CandidateRefusal(reason=reason, detail=detail)


def _refuse(reason: CandidateRefusalReason, detail: str) -> CandidateMaterializationResult:
    return CandidateMaterializationResult(refusal=_refusal(reason, detail))
