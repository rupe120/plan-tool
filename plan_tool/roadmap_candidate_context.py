"""Immutable, byte-bounded proposal context for one roadmap feedback lineage."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
from typing import Final, Literal, TypeAlias, cast

from pydantic import BaseModel, ConfigDict, model_validator

from plan_tool.roadmap import STAGES
from plan_tool.roadmap_artifacts import (
    AssumptionRow,
    AttributeDispositionRow,
    BusinessRuleRow,
    ComponentRow,
    ConstraintRow,
    DecisionRow,
    DecisionStatus,
    EntityRow,
    FeedbackRow,
    FeedbackState,
    FeedbackTargetKind,
    PatternRow,
    PlanRow,
    RoadmapArtifact,
    RoadmapArtifactError,
    ComponentsArtifact,
    ConstraintsArtifact,
    DesignRow,
    DomainArtifact,
    PlansArtifact,
    StackRow,
    StageRow,
    StoreRow,
    WorkflowRow,
    design_row_collections,
    impact_node_collections,
    stage_row_collections,
    _STAGE_ROW_TYPE_BY_COLLECTION,
)
from plan_tool.roadmap_feedback import (
    FeedbackSelector,
    MalformedFeedbackSelector,
    UnknownFeedbackArtifact,
    matching_feedback_rows,
    parse_feedback_selector,
)
from plan_tool.roadmap_feedback_ledger import (
    DerivedFeedbackContext,
    ReviewerItemSnapshot,
    RoadmapFeedbackLedger,
    RoadmapFeedbackLedgerError,
    eligible_reviewer_items,
    item_snapshot,
    ledger_digest,
)
from plan_tool.roadmap_impact_relations import (
    ImpactClosure,
    ImpactNode,
    ImpactRelationEvidence,
    ImpactTarget,
    resolve_impact_closure,
)
from plan_tool.roadmap_json import unwrap_enum_value
from plan_tool.roadmap_relations import ARTIFACT_KEYS, ArtifactKey, RoadmapRelation, extract_declared_relations
from plan_tool.roadmap_revision import StageProseSpan, project_row_owned_prose_spans
from plan_tool.roadmap_versions import (
    ResolvedRoadmapVersion,
    StoredRoadmapVersion,
    VERSION_ARTIFACT_KEYS,
    sha256_digests,
)


_LEGACY_CANDIDATE_CONTEXT_MAX_BYTES: Final[int] = 64 * 1024
_PRIOR_CANDIDATE_CONTEXT_MAX_BYTES: Final[int] = 192 * 1024
CANDIDATE_CONTEXT_MAX_BYTES: Final[int] = 384 * 1024
_SUPPORTED_CANDIDATE_CONTEXT_CEILINGS: Final[frozenset[int]] = frozenset(
    (
        _LEGACY_CANDIDATE_CONTEXT_MAX_BYTES,
        _PRIOR_CANDIDATE_CONTEXT_MAX_BYTES,
        CANDIDATE_CONTEXT_MAX_BYTES,
    )
)
_CONTEXT_SCHEMA_VERSION: Final[int] = 1
# Batch payloads carry each shared source span once in a table; single-owner spans stay inline.
# Selector payloads stay at 1: stored ones are verified by exact recompilation, so their bytes cannot change.
_BATCH_CONTEXT_SCHEMA_VERSION: Final[int] = 2


def is_supported_candidate_context_ceiling(value: object) -> bool:
    """Keep prior immutable capsule records readable across a ceiling increase."""
    return type(value) is int and value in _SUPPORTED_CANDIDATE_CONTEXT_CEILINGS

# A member can enter through more than one fixed source.  The sequence below
# is the public receipt order, independent of the order closures were resolved.
_MEMBER_REASON_ORDER: Final[tuple[str, ...]] = (
    "feedback-closure",
    "inventory-expansion",
    "settled-decision",
)


class _FrozenContextRecord(BaseModel):
    """Closed value record shared by the capsule's inspectable facts."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, arbitrary_types_allowed=True)


class CandidateContextArtifactBinding(_FrozenContextRecord):
    """One exact stored stage member included in a predecessor identity."""

    artifact_key: str
    digest: str


class CandidateContextPredecessor(_FrozenContextRecord):
    """The immutable version bindings this context may read."""

    roadmap_slug: str
    version_id: str
    brief_digest: str
    artifacts: tuple[CandidateContextArtifactBinding, ...]


class CandidateContextMemberIdentity(_FrozenContextRecord):
    """One stable design-row identity without any authority by itself."""

    artifact_key: str
    row_type: str
    row_id: str


class CandidateContextSourceSpan(_FrozenContextRecord):
    """One exact source block admitted with a full row."""

    row_id: str
    span_id: str
    text: str
    digest: str
    # Set only on a shared span; absent on single-owner and legacy records.
    owning_row_ids: tuple[str, ...] | None = None


class CandidateContextSourceSpanReceipt(_FrozenContextRecord):
    """One source-span binding without returning its prose a second time."""

    row_id: str
    span_id: str
    digest: str
    owning_row_ids: tuple[str, ...] | None = None


class CandidateContextFeedbackTarget(_FrozenContextRecord):
    """The target facts carried by the one selected reviewer request."""

    kind: str
    row_id: str | None = None


class CandidateContextFeedback(_FrozenContextRecord):
    """One selected open feedback row, reduced to its immutable request facts."""

    artifact_key: str
    feedback_id: str
    target: CandidateContextFeedbackTarget
    request: str
    state: str
    digest: str


class CandidateContextFullMember(_FrozenContextRecord):
    """One complete typed row issued as proposal context."""

    identity: CandidateContextMemberIdentity
    row: object
    row_digest: str
    source_spans: tuple[CandidateContextSourceSpan, ...]
    inclusion_reasons: tuple[str, ...]


class CandidateContextInventoryEntry(_FrozenContextRecord):
    """Compact discovery metadata for one omitted row, never edit authority."""

    artifact_key: str
    row_type: str
    row_id: str
    label: str
    digest: str

    @property
    def identity(self) -> CandidateContextMemberIdentity:
        """Return the stable identity the expansion route resolves."""
        return CandidateContextMemberIdentity(
            artifact_key=self.artifact_key,
            row_type=self.row_type,
            row_id=self.row_id,
        )


class CandidateContextRelationNode(_FrozenContextRecord):
    """One row endpoint named by declared relation evidence."""

    artifact_key: str
    row_id: str


class CandidateContextRelationEvidence(_FrozenContextRecord):
    """One declared relation reached by the selected closure."""

    source_index: int
    kind: str
    direction: str
    owner: CandidateContextRelationNode
    endpoint: CandidateContextRelationNode


class CandidateContextMemberReceipt(_FrozenContextRecord):
    """The content bindings for one full member without returning its body."""

    identity: CandidateContextMemberIdentity
    row_digest: str
    inclusion_reasons: tuple[str, ...]
    source_spans: tuple[CandidateContextSourceSpanReceipt, ...]


class CandidateContextExpansion(_FrozenContextRecord):
    """The one expansion fact that binds the final capsule to its parent."""

    parent_capsule_identity: str
    inventory_entry: CandidateContextInventoryEntry


class CandidateContextReceipt(_FrozenContextRecord):
    """Inspectable bindings for one exact closed model-facing payload."""

    schema_version: int
    predecessor: CandidateContextPredecessor
    feedback: CandidateContextFeedback
    full_members: tuple[CandidateContextMemberReceipt, ...]
    relation_evidence: tuple[CandidateContextRelationEvidence, ...]
    inventory: tuple[CandidateContextInventoryEntry, ...]
    ceiling_bytes: int
    payload_bytes: int
    payload_digest: str
    capsule_identity: str
    expansion: CandidateContextExpansion | None = None


class CandidateContextCapsule(_FrozenContextRecord):
    """One issued immutable context capsule and the bytes a model receives."""

    predecessor: CandidateContextPredecessor
    brief: str
    feedback: CandidateContextFeedback
    full_members: tuple[CandidateContextFullMember, ...]
    relation_evidence: tuple[CandidateContextRelationEvidence, ...]
    inventory: tuple[CandidateContextInventoryEntry, ...]
    ceiling_bytes: int
    payload: bytes
    capsule_identity: str
    receipt: CandidateContextReceipt
    expansion: CandidateContextExpansion | None = None


class CandidateContextBatchReceipt(CandidateContextReceipt):
    """Receipt facts for a batch that does not select one embedded feedback row."""

    feedback: CandidateContextFeedback | None = None
    root: CandidateContextPredecessor
    source: CandidateContextPredecessor
    ledger_digest: str
    reviewer_items: tuple[ReviewerItemSnapshot, ...]
    derived_context: tuple[DerivedFeedbackContext, ...]


class CandidateContextBatchCapsule(CandidateContextCapsule):
    """Model payload and immutable evidence for one root/source ledger batch."""

    feedback: CandidateContextFeedback | None = None
    root: CandidateContextPredecessor
    source: CandidateContextPredecessor
    ledger_digest: str
    reviewer_items: tuple[ReviewerItemSnapshot, ...]
    derived_context: tuple[DerivedFeedbackContext, ...]
    receipt: CandidateContextBatchReceipt


def candidate_collection_hints(
    capsule: CandidateContextBatchCapsule, source: ResolvedRoadmapVersion
) -> dict[str, object]:
    """Derive prompt syntax from the exact source without changing issued evidence."""
    verified = _verify_predecessor(source)
    if isinstance(verified, CandidateContextRefusal) or verified.identity != capsule.receipt.source:
        raise ValueError("candidate prompt source does not match its issued receipt")
    if capsule.source != capsule.receipt.source:
        raise ValueError("candidate prompt capsule has inconsistent source bindings")

    actual: dict[tuple[str, str, str], tuple[str, str]] = {}
    for artifact_key, artifact in verified.artifacts.items():
        for collection, rows in stage_row_collections(artifact).items():
            for row in rows:
                key = (artifact_key, type(row).__name__, row.id)
                if key in actual:
                    raise ValueError("candidate prompt source row has ambiguous collection")
                actual[key] = (collection, _row_digest(row))

    references: list[dict[str, object]] = []
    for member in capsule.full_members:
        identity = member.identity
        key = (identity.artifact_key, identity.row_type, identity.row_id)
        entry = actual.get(key)
        if entry is None or entry[1] != member.row_digest:
            raise ValueError("candidate prompt row does not match its issued source")
        references.append(
            {
                "issued_row": {"artifact": key[0], "class": key[1], "id": key[2]},
                "source_collection": entry[0],
            }
        )
    for item in capsule.inventory:
        key = (item.artifact_key, item.row_type, item.row_id)
        entry = actual.get(key)
        if entry is None or entry[1] != item.digest:
            raise ValueError("candidate prompt inventory does not match its issued source")
        references.append(
            {
                "issued_row": {"artifact": key[0], "class": key[1], "id": key[2]},
                "source_collection": entry[0],
            }
        )

    vocabulary: dict[str, list[str]] = {}
    for collection, row_class in _STAGE_ROW_TYPE_BY_COLLECTION.items():
        vocabulary.setdefault(row_class.__name__, []).append(collection)
    return {"valid_collections_by_class": vocabulary, "existing_rows": references}


CandidateContextRefusalReason: TypeAlias = Literal[
    "invalid-predecessor",
    "malformed-feedback-selector",
    "unknown-feedback-artifact",
    "feedback-not-found",
    "duplicate-feedback",
    "feedback-not-open",
    "incomplete-closure",
    "payload-over-budget",
    "invalid-capsule",
    "already-expanded",
    "predecessor-mismatch",
    "invalid-expansion-entry",
    "invalid-ledger",
    "invalid-processing-pair",
]


class CandidateContextRefusal(_FrozenContextRecord):
    """A fail-closed result that never carries a partial capsule."""

    reason: CandidateContextRefusalReason
    detail: str
    ceiling_bytes: int | None = None
    measured_payload_bytes: int | None = None
    full_members: tuple[CandidateContextMemberReceipt, ...] = ()
    reviewer_items: tuple[ReviewerItemSnapshot, ...] = ()
    derived_context: tuple[DerivedFeedbackContext, ...] = ()


class CandidateContextNoWork(_FrozenContextRecord):
    """A complete batch with no model-facing inputs and no write authority."""

    root: CandidateContextPredecessor
    source: CandidateContextPredecessor
    ledger_digest: str


class CandidateContextResult(_FrozenContextRecord):
    """Exactly one completed capsule or structured refusal."""

    capsule: CandidateContextCapsule | CandidateContextBatchCapsule | None = None
    refusal: CandidateContextRefusal | None = None
    no_work: CandidateContextNoWork | None = None

    @model_validator(mode="after")
    def _requires_exactly_one_outcome(self) -> CandidateContextResult:
        if sum(value is not None for value in (self.capsule, self.refusal, self.no_work)) != 1:
            raise ValueError("candidate context requires exactly one outcome")
        return self


@dataclass(frozen=True)
class _VerifiedPredecessor:
    """Parsed stored members retained only while this pure compiler runs."""

    identity: CandidateContextPredecessor
    record: StoredRoadmapVersion
    brief: str
    artifacts: dict[ArtifactKey, RoadmapArtifact]


def build_candidate_context(
    accepted_root: ResolvedRoadmapVersion,
    active_candidate: ResolvedRoadmapVersion | object | None = None,
    ledger: RoadmapFeedbackLedger | None = None,
    *,
    source_ancestry: tuple[str, ...] | None = None,
) -> CandidateContextResult:
    """Build a root-bound batch, retaining the selector form for old callers.

    ``source_ancestry`` is the caller-walked chain of stored predecessor ids from
    the active candidate's immediate predecessor up to the root, inclusive. This
    pure builder reads no store, so without it only a candidate whose direct
    predecessor is the root is accepted.
    """
    if ledger is not None:
        return _build_context_batch(
            accepted_root, active_candidate, ledger, source_ancestry=source_ancestry
        )

    # The selector form remains readable while callers move to the ledger batch.
    return _build_selector_context(accepted_root, active_candidate, CANDIDATE_CONTEXT_MAX_BYTES)


def rebuild_candidate_context_at_recorded_ceiling(
    predecessor: ResolvedRoadmapVersion,
    feedback_selector: object,
    *,
    recorded_ceiling_bytes: object,
) -> CandidateContextResult:
    """Reproduce a stored selector capsule at the ceiling it was issued under.

    Every ceiling is baked into the payload and its digest, so a lineage issued
    under an earlier ceiling reproduces only at that value. New contexts still
    take no caller ceiling: use ``build_candidate_context``.
    """
    if not is_supported_candidate_context_ceiling(recorded_ceiling_bytes):
        return _refused(_refusal("invalid-capsule", "recorded context ceiling is not a supported value"))
    return _build_selector_context(predecessor, feedback_selector, cast(int, recorded_ceiling_bytes))


def _build_selector_context(
    predecessor: ResolvedRoadmapVersion, feedback_selector: object, ceiling_bytes: int
) -> CandidateContextResult:
    verified = _verify_predecessor(predecessor)
    if isinstance(verified, CandidateContextRefusal):
        return _refused(verified)
    selected = _select_feedback(verified, feedback_selector)
    if isinstance(selected, CandidateContextRefusal):
        return _refused(selected)
    selector, feedback = selected
    return _compile_context(
        verified,
        selector=selector,
        feedback=feedback,
        expansion=None,
        ceiling_bytes=ceiling_bytes,
    )


def _build_context_batch(
    accepted_root: object,
    active_candidate: object,
    ledger: RoadmapFeedbackLedger,
    *,
    source_ancestry: tuple[str, ...] | None = None,
) -> CandidateContextResult:
    """Compile one immutable reviewer/derived-context batch from one source pair."""
    if not isinstance(ledger, RoadmapFeedbackLedger):
        return _refused(_refusal("invalid-ledger", "context requires a validated feedback ledger"))

    root = _verify_predecessor(accepted_root)
    if isinstance(root, CandidateContextRefusal):
        return _refused(root)
    source_input = accepted_root if active_candidate is None else active_candidate
    source = _verify_predecessor(source_input)
    if isinstance(source, CandidateContextRefusal):
        return _refused(source)
    if not _source_descends_from_root(root, source, source_ancestry):
        return _refused(
            _refusal("invalid-processing-pair", "source is not the root or a candidate that descends from it")
        )
    if ledger.roadmap_slug != root.identity.roadmap_slug:
        return _refused(_refusal("invalid-ledger", "ledger roadmap does not match accepted root"))

    try:
        reviewer_items = tuple(item_snapshot(item) for item in eligible_reviewer_items(ledger, source_input))
        derived_context = tuple(
            entry for entry in ledger.derived_context
            if entry.source_version_id == source.identity.version_id
        )
        digest = ledger_digest(ledger)
    except (RoadmapFeedbackLedgerError, TypeError, ValueError):
        return _refused(_refusal("invalid-ledger", "ledger cannot supply a consistent batch"))

    if not reviewer_items and not derived_context:
        return CandidateContextResult(
            no_work=CandidateContextNoWork(
                root=root.identity, source=source.identity, ledger_digest=digest
            )
        )
    return _compile_batch_context(
        root=root,
        source=source,
        ledger_digest_value=digest,
        reviewer_items=reviewer_items,
        derived_context=derived_context,
    )


def _source_descends_from_root(
    root: _VerifiedPredecessor,
    source: _VerifiedPredecessor,
    source_ancestry: tuple[str, ...] | None,
) -> bool:
    if root.identity.roadmap_slug != source.identity.roadmap_slug:
        return False
    if source.identity.version_id == root.identity.version_id:
        return source_ancestry in (None, ())
    record = source.record
    if record.version_kind != "candidate":
        return False
    chain = (record.predecessor_version_id,) if source_ancestry is None else source_ancestry
    return (
        bool(chain)
        and chain[0] == record.predecessor_version_id
        and chain[-1] == root.identity.version_id
        and len(set(chain)) == len(chain)
        and source.identity.version_id not in chain
    )


def _compile_batch_context(
    *,
    root: _VerifiedPredecessor,
    source: _VerifiedPredecessor,
    ledger_digest_value: str,
    reviewer_items: tuple[ReviewerItemSnapshot, ...],
    derived_context: tuple[DerivedFeedbackContext, ...],
) -> CandidateContextResult:
    """Project source-local roadmap context for every immutable reviewer input."""
    relations = extract_declared_relations(**source.artifacts)
    closures: list[ImpactClosure] = []
    for item in reviewer_items:
        closure = _resolve_closure(
            ImpactTarget(
                kind=item.target.kind,
                artifact_key=cast(ArtifactKey, item.target.artifact_key),
                row_id=item.target.row_id,
            ),
            source.artifacts,
            relations,
        )
        if isinstance(closure, CandidateContextRefusal):
            return _refused(closure)
        closures.append(closure)
    full_member_keys = {
        (node.artifact_key, node.row_id) for closure in closures for node in closure.nodes
    }
    settled_member_keys = {
        (artifact_key, row.id)
        for artifact_key in ARTIFACT_KEYS
        for row in source.artifacts[artifact_key].decisions
        if row.status is DecisionStatus.SETTLED
    }
    full_member_keys.update(settled_member_keys)
    reasons: dict[tuple[ArtifactKey, str], tuple[str, ...]] = {
        key: ("feedback-closure",) for key in full_member_keys if key not in settled_member_keys
    }
    for key in settled_member_keys:
        reasons[key] = (("feedback-closure", "settled-decision") if key in reasons else ("settled-decision",))
    evidence_by_index = {
        evidence.source_index: evidence for closure in closures for evidence in closure.relations
    }
    relation_evidence = tuple(_relation_facts(evidence_by_index[index]) for index in sorted(evidence_by_index))
    full_members, inventory = _project_members(
        source.artifacts, full_member_keys=full_member_keys, reasons_by_key=reasons
    )
    payload = _render_batch_payload(
        root=root.identity, source=source.identity, brief=source.brief,
        ledger_digest_value=ledger_digest_value, reviewer_items=reviewer_items,
        derived_context=derived_context, full_members=full_members,
        relation_evidence=relation_evidence, inventory=inventory,
    )
    measured_bytes = len(payload)
    member_receipts = _member_receipts(full_members)
    if measured_bytes > CANDIDATE_CONTEXT_MAX_BYTES:
        return _refused(_refusal(
            "payload-over-budget", "full canonical batch payload exceeds the fixed context ceiling",
            ceiling_bytes=CANDIDATE_CONTEXT_MAX_BYTES, measured_payload_bytes=measured_bytes,
            full_members=member_receipts, reviewer_items=reviewer_items,
            derived_context=derived_context,
        ))
    identity = _digest_bytes(payload)
    receipt = CandidateContextBatchReceipt(
        schema_version=_BATCH_CONTEXT_SCHEMA_VERSION, predecessor=source.identity,
        root=root.identity, source=source.identity, ledger_digest=ledger_digest_value,
        reviewer_items=reviewer_items, derived_context=derived_context,
        full_members=member_receipts, relation_evidence=relation_evidence, inventory=inventory,
        ceiling_bytes=CANDIDATE_CONTEXT_MAX_BYTES, payload_bytes=measured_bytes,
        payload_digest=identity, capsule_identity=identity,
    )
    return CandidateContextResult(capsule=CandidateContextBatchCapsule(
        predecessor=source.identity, brief=source.brief, root=root.identity, source=source.identity,
        ledger_digest=ledger_digest_value, reviewer_items=reviewer_items, derived_context=derived_context,
        full_members=full_members, relation_evidence=relation_evidence, inventory=inventory,
        ceiling_bytes=CANDIDATE_CONTEXT_MAX_BYTES, payload=payload, capsule_identity=identity,
        receipt=receipt,
    ))


def expand_candidate_context(
    predecessor: ResolvedRoadmapVersion,
    capsule: CandidateContextCapsule,
    selected_inventory_entry: CandidateContextInventoryEntry,
) -> CandidateContextResult:
    """Spend the capsule's one inventory expansion against the same predecessor."""
    if not isinstance(capsule, CandidateContextCapsule) or not _capsule_is_intact(capsule):
        return _refused(_refusal("invalid-capsule", "capsule facts do not bind its payload"))
    if capsule.expansion is not None:
        return _refused(_refusal("already-expanded", "a candidate lineage has one expansion"))
    if (
        not isinstance(selected_inventory_entry, CandidateContextInventoryEntry)
        or selected_inventory_entry not in capsule.inventory
    ):
        return _refused(
            _refusal("invalid-expansion-entry", "entry is not an exact initial inventory item")
        )

    verified = _verify_predecessor(predecessor)
    if isinstance(verified, CandidateContextRefusal):
        return _refused(verified)
    if verified.identity != capsule.predecessor:
        return _refused(
            _refusal("predecessor-mismatch", "expansion must use the capsule predecessor")
        )

    selected = _select_feedback(verified, f"{capsule.feedback.artifact_key}:{capsule.feedback.feedback_id}")
    if isinstance(selected, CandidateContextRefusal):
        return _refused(selected)
    selector, feedback = selected
    expected_initial = _compile_context(
        verified,
        selector=selector,
        feedback=feedback,
        expansion=None,
        ceiling_bytes=capsule.ceiling_bytes,
    )
    if expected_initial.capsule is None:
        assert expected_initial.refusal is not None
        return _refused(expected_initial.refusal)
    if capsule != expected_initial.capsule:
        return _refused(_refusal("invalid-capsule", "capsule is not this predecessor's initial context"))
    expansion_target = _target_for_member(selected_inventory_entry)
    expansion = CandidateContextExpansion(
        parent_capsule_identity=capsule.capsule_identity,
        inventory_entry=selected_inventory_entry,
    )
    return _compile_context(
        verified,
        selector=selector,
        feedback=feedback,
        expansion=expansion,
        expansion_target=expansion_target,
        ceiling_bytes=capsule.ceiling_bytes,
    )


def _compile_context(
    verified: _VerifiedPredecessor,
    *,
    selector: FeedbackSelector,
    feedback: FeedbackRow,
    expansion: CandidateContextExpansion | None,
    ceiling_bytes: int,
    expansion_target: ImpactTarget | None = None,
) -> CandidateContextResult:
    feedback_target = ImpactTarget(
        kind=feedback.target.kind,
        artifact_key=cast(ArtifactKey, selector.artifact_key),
        row_id=feedback.target.row_id,
    )
    relations = extract_declared_relations(**verified.artifacts)
    feedback_closure = _resolve_closure(feedback_target, verified.artifacts, relations)
    if isinstance(feedback_closure, CandidateContextRefusal):
        return _refused(feedback_closure)

    expansion_closure: ImpactClosure | None = None
    if expansion_target is not None:
        expansion_closure = _resolve_closure(expansion_target, verified.artifacts, relations)
        if isinstance(expansion_closure, CandidateContextRefusal):
            return _refused(expansion_closure)

    full_member_keys = {
        (node.artifact_key, node.row_id) for node in feedback_closure.nodes
    }
    if expansion_closure is not None:
        full_member_keys.update((node.artifact_key, node.row_id) for node in expansion_closure.nodes)
    settled_member_keys = {
        (artifact_key, row.id)
        for artifact_key in ARTIFACT_KEYS
        for row in verified.artifacts[artifact_key].decisions
        if row.status is DecisionStatus.SETTLED
    }
    full_member_keys.update(settled_member_keys)

    reasons_by_key = _member_reasons(
        feedback_closure=feedback_closure,
        expansion_closure=expansion_closure,
        settled_member_keys=settled_member_keys,
    )
    relation_evidence = _ordered_relation_evidence(feedback_closure, expansion_closure)
    full_members, inventory = _project_members(
        verified.artifacts,
        full_member_keys=full_member_keys,
        reasons_by_key=reasons_by_key,
    )
    feedback_facts = _feedback_facts(selector, feedback)
    payload = _render_payload(
        predecessor=verified.identity,
        brief=verified.brief,
        feedback=feedback_facts,
        full_members=full_members,
        relation_evidence=relation_evidence,
        inventory=inventory,
        expansion=expansion,
        ceiling_bytes=ceiling_bytes,
    )
    measured_bytes = len(payload)
    member_receipts = _member_receipts(full_members)
    if measured_bytes > ceiling_bytes:
        return _refused(
            _refusal(
                "payload-over-budget",
                "full canonical payload exceeds the fixed context ceiling",
                ceiling_bytes=ceiling_bytes,
                measured_payload_bytes=measured_bytes,
                full_members=member_receipts,
            )
        )

    identity = _digest_bytes(payload)
    receipt = CandidateContextReceipt(
        schema_version=_CONTEXT_SCHEMA_VERSION,
        predecessor=verified.identity,
        feedback=feedback_facts,
        full_members=member_receipts,
        relation_evidence=relation_evidence,
        inventory=inventory,
        ceiling_bytes=ceiling_bytes,
        payload_bytes=measured_bytes,
        payload_digest=identity,
        capsule_identity=identity,
        expansion=expansion,
    )
    return CandidateContextResult(
        capsule=CandidateContextCapsule(
            predecessor=verified.identity,
            brief=verified.brief,
            feedback=feedback_facts,
            full_members=full_members,
            relation_evidence=relation_evidence,
            inventory=inventory,
            ceiling_bytes=ceiling_bytes,
            payload=payload,
            capsule_identity=identity,
            receipt=receipt,
            expansion=expansion,
        )
    )


def _verify_predecessor(
    predecessor: object,
) -> _VerifiedPredecessor | CandidateContextRefusal:
    """Validate and parse only the exact bytes supplied by the caller."""
    if not isinstance(predecessor, ResolvedRoadmapVersion):
        return _refusal("invalid-predecessor", "context requires resolved immutable content")
    record = predecessor.record
    if not isinstance(record, StoredRoadmapVersion):
        return _refusal("invalid-predecessor", "predecessor record has the wrong type")
    try:
        StoredRoadmapVersion.model_validate(record.model_dump(mode="json"))
    except (TypeError, ValueError):
        return _refusal("invalid-predecessor", "predecessor record is not self-consistent")
    if not isinstance(predecessor.brief_bytes, bytes) or not isinstance(
        predecessor.artifact_bytes, tuple
    ):
        return _refusal("invalid-predecessor", "predecessor content has the wrong shape")
    expected_keys = tuple(stage.artifact_key for stage in STAGES)
    expected_members = VERSION_ARTIFACT_KEYS
    if (
        expected_keys != expected_members
        or predecessor.artifact_keys != expected_keys
        or len(predecessor.artifact_bytes) != len(STAGES)
    ):
        return _refusal("invalid-predecessor", "predecessor artifact order is not configured")
    if _digest_bytes(predecessor.brief_bytes) != record.brief_digest:
        return _refusal("invalid-predecessor", "recorded brief digest does not match its bytes")
    try:
        brief = predecessor.brief_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return _refusal("invalid-predecessor", "recorded brief is not strict UTF-8")
    if any(not isinstance(data, bytes) for data in predecessor.artifact_bytes):
        return _refusal("invalid-predecessor", "stored artifact content must be bytes")
    artifact_digests = sha256_digests(predecessor.artifact_bytes)
    if artifact_digests != tuple(member.digest for member in record.artifact_members):
        return _refusal("invalid-predecessor", "stored artifact bytes do not match their bindings")

    artifacts: dict[ArtifactKey, RoadmapArtifact] = {}
    try:
        for stage, data in zip(STAGES, predecessor.artifact_bytes, strict=True):
            parsed = stage.parse(data.decode("utf-8"))
            artifact_key = cast(ArtifactKey, stage.artifact_key)
            artifacts[artifact_key] = cast(RoadmapArtifact, parsed)
    except (RoadmapArtifactError, UnicodeDecodeError, TypeError, ValueError):
        return _refusal("invalid-predecessor", "stored artifact content cannot be parsed")
    if tuple(artifacts) != ARTIFACT_KEYS or not all(
        _is_roadmap_artifact(artifact) for artifact in artifacts.values()
    ):
        return _refusal("invalid-predecessor", "stored artifacts have unsupported parsed values")
    if _has_duplicate_design_identities(artifacts):
        return _refusal("invalid-predecessor", "design row identities must be unique per artifact")
    return _VerifiedPredecessor(
        identity=CandidateContextPredecessor(
            roadmap_slug=record.roadmap_slug,
            version_id=record.version_id,
            brief_digest=record.brief_digest,
            artifacts=tuple(
                CandidateContextArtifactBinding(
                    artifact_key=member.artifact_key,
                    digest=member.digest,
                )
                for member in record.artifact_members
            ),
        ),
        record=record,
        brief=brief,
        artifacts=artifacts,
    )


def _is_roadmap_artifact(value: object) -> bool:
    return isinstance(
        value,
        (DomainArtifact, ConstraintsArtifact, ComponentsArtifact, PlansArtifact),
    )


def _has_duplicate_design_identities(artifacts: Mapping[ArtifactKey, RoadmapArtifact]) -> bool:
    # Publication gates already enforce cross-collection row-id uniqueness.
    for artifact_key in ARTIFACT_KEYS:
        rows = tuple(
            row for collection in design_row_collections(artifacts[artifact_key]).values() for row in collection
        )
        if len({row.id for row in rows}) != len(rows):
            return True
    return False


def _select_feedback(
    verified: _VerifiedPredecessor, feedback_selector: object
) -> tuple[FeedbackSelector, FeedbackRow] | CandidateContextRefusal:
    parsed = parse_feedback_selector(feedback_selector, ARTIFACT_KEYS)
    if isinstance(parsed, MalformedFeedbackSelector):
        return _refusal("malformed-feedback-selector", parsed.reason)
    if isinstance(parsed, UnknownFeedbackArtifact):
        return _refusal("unknown-feedback-artifact", parsed.artifact_key)
    matches = matching_feedback_rows(verified.artifacts[cast(ArtifactKey, parsed.artifact_key)], parsed)
    if not matches:
        return _refusal("feedback-not-found", "selector has no matching stored feedback row")
    if len(matches) != 1:
        return _refusal("duplicate-feedback", "selector matches more than one stored feedback row")
    feedback = matches[0]
    if feedback.state is not FeedbackState.OPEN:
        return _refusal("feedback-not-open", "selected feedback is not open")
    return parsed, feedback


def _resolve_closure(
    target: ImpactTarget,
    artifacts: Mapping[ArtifactKey, RoadmapArtifact],
    relations: tuple[RoadmapRelation, ...],
) -> ImpactClosure | CandidateContextRefusal:
    closure = resolve_impact_closure(
        target,
        domain=cast(object, artifacts["domain"]),
        constraints=cast(object, artifacts["constraints"]),
        components=cast(object, artifacts["components"]),
        plans=cast(object, artifacts["plans"]),
        relations=relations,
    )
    if closure.verdict != "complete":
        return _refusal("incomplete-closure", closure.verdict)
    return closure


def _member_reasons(
    *,
    feedback_closure: ImpactClosure,
    expansion_closure: ImpactClosure | None,
    settled_member_keys: set[tuple[ArtifactKey, str]],
) -> dict[tuple[ArtifactKey, str], tuple[str, ...]]:
    reasons: dict[tuple[ArtifactKey, str], set[str]] = {}
    for node in feedback_closure.nodes:
        reasons.setdefault((node.artifact_key, node.row_id), set()).add("feedback-closure")
    if expansion_closure is not None:
        for node in expansion_closure.nodes:
            reasons.setdefault((node.artifact_key, node.row_id), set()).add("inventory-expansion")
    for key in settled_member_keys:
        reasons.setdefault(key, set()).add("settled-decision")
    return {
        key: tuple(reason for reason in _MEMBER_REASON_ORDER if reason in member_reasons)
        for key, member_reasons in reasons.items()
    }


def _ordered_relation_evidence(
    feedback_closure: ImpactClosure,
    expansion_closure: ImpactClosure | None,
) -> tuple[CandidateContextRelationEvidence, ...]:
    evidence_by_index: dict[int, ImpactRelationEvidence] = {
        evidence.source_index: evidence for evidence in feedback_closure.relations
    }
    if expansion_closure is not None:
        for evidence in expansion_closure.relations:
            evidence_by_index.setdefault(evidence.source_index, evidence)
    return tuple(
        _relation_facts(evidence_by_index[index]) for index in sorted(evidence_by_index)
    )


def _relation_facts(evidence: ImpactRelationEvidence) -> CandidateContextRelationEvidence:
    relation = evidence.relation
    return CandidateContextRelationEvidence(
        source_index=evidence.source_index,
        kind=relation.kind.value,
        direction=relation.direction.value,
        owner=_relation_node(evidence.owner),
        endpoint=_relation_node(evidence.endpoint),
    )


def _project_members(
    artifacts: Mapping[ArtifactKey, RoadmapArtifact],
    *,
    full_member_keys: set[tuple[ArtifactKey, str]],
    reasons_by_key: Mapping[tuple[ArtifactKey, str], tuple[str, ...]],
) -> tuple[tuple[CandidateContextFullMember, ...], tuple[CandidateContextInventoryEntry, ...]]:
    full_members: list[CandidateContextFullMember] = []
    inventory: list[CandidateContextInventoryEntry] = []
    for artifact_key in ARTIFACT_KEYS:
        artifact = artifacts[artifact_key]
        rows = tuple(
            row for collection in impact_node_collections(artifact).values() for row in collection
        )
        selected_ids = {row.id for row in rows if (artifact_key, row.id) in full_member_keys}
        spans_by_row: dict[str, list[CandidateContextSourceSpan]] = {}
        for span in project_row_owned_prose_spans(artifact, selected_ids):
            facts = _source_span_facts(span)
            for owner_id in span.owning_row_ids:
                spans_by_row.setdefault(owner_id, []).append(facts)
        for row in rows:
            identity = _row_identity(artifact_key, row)
            key = (artifact_key, row.id)
            digest = _row_digest(row)
            if key in full_member_keys:
                full_members.append(
                    CandidateContextFullMember(
                        identity=identity,
                        row=row,
                        row_digest=digest,
                        source_spans=tuple(spans_by_row.get(row.id, ())),
                        inclusion_reasons=reasons_by_key[key],
                    )
                )
                continue
            if isinstance(row, (StoreRow, StackRow)):
                continue
            inventory.append(
                CandidateContextInventoryEntry(
                    artifact_key=identity.artifact_key,
                    row_type=identity.row_type,
                    row_id=identity.row_id,
                    label=_row_label(row),
                    digest=digest,
                )
            )
    return tuple(full_members), tuple(inventory)


def _row_identity(artifact_key: ArtifactKey, row: StageRow) -> CandidateContextMemberIdentity:
    return CandidateContextMemberIdentity(
        artifact_key=artifact_key,
        row_type=type(row).__name__,
        row_id=row.id,
    )


def _relation_node(node: ImpactNode) -> CandidateContextRelationNode:
    return CandidateContextRelationNode(
        artifact_key=node.artifact_key,
        row_id=node.row_id,
    )


def _target_for_member(entry: CandidateContextInventoryEntry) -> ImpactTarget:
    return ImpactTarget(
        kind=FeedbackTargetKind.ROW,
        artifact_key=cast(ArtifactKey, entry.artifact_key),
        row_id=entry.row_id,
    )


def _source_span_facts(span: StageProseSpan) -> CandidateContextSourceSpan:
    return CandidateContextSourceSpan(
        row_id=span.row_id,
        span_id=span.span_id,
        text=span.text,
        digest=_digest_text(span.text),
        owning_row_ids=span.owning_row_ids if span.is_shared else None,
    )


def _feedback_facts(selector: FeedbackSelector, feedback: FeedbackRow) -> CandidateContextFeedback:
    target = CandidateContextFeedbackTarget(
        kind=feedback.target.kind.value,
        row_id=feedback.target.row_id,
    )
    feedback_payload = {
        "artifact_key": selector.artifact_key,
        "feedback_id": feedback.id,
        "target": _wire_value(target),
        "request": feedback.request,
        "state": feedback.state.value,
    }
    return CandidateContextFeedback(
        artifact_key=selector.artifact_key,
        feedback_id=feedback.id,
        target=target,
        request=feedback.request,
        state=feedback.state.value,
        digest=_digest_bytes(_canonical_json_bytes(feedback_payload)),
    )


def _member_receipts(
    full_members: Sequence[CandidateContextFullMember],
) -> tuple[CandidateContextMemberReceipt, ...]:
    return tuple(
        CandidateContextMemberReceipt(
            identity=member.identity,
            row_digest=member.row_digest,
            inclusion_reasons=member.inclusion_reasons,
            source_spans=tuple(
                CandidateContextSourceSpanReceipt(
                    row_id=span.row_id,
                    span_id=span.span_id,
                    digest=span.digest,
                    owning_row_ids=span.owning_row_ids,
                )
                for span in member.source_spans
            ),
        )
        for member in full_members
    )


def _render_payload(
    *,
    predecessor: CandidateContextPredecessor,
    brief: str,
    feedback: CandidateContextFeedback,
    full_members: tuple[CandidateContextFullMember, ...],
    relation_evidence: tuple[CandidateContextRelationEvidence, ...],
    inventory: tuple[CandidateContextInventoryEntry, ...],
    expansion: CandidateContextExpansion | None,
    ceiling_bytes: int,
) -> bytes:
    """Render the one closed model payload before measuring or identifying it."""
    return _canonical_json_bytes(
        {
            "schema_version": _CONTEXT_SCHEMA_VERSION,
            "predecessor": _wire_value(predecessor),
            "brief": brief,
            "feedback": _wire_value(feedback),
            "full_members": [
                {
                    "identity": _wire_value(member.identity),
                    "row": _wire_value(member.row),
                    "row_digest": member.row_digest,
                    "source_spans": _wire_value(member.source_spans),
                    "inclusion_reasons": list(member.inclusion_reasons),
                }
                for member in full_members
            ],
            "relation_evidence": _wire_value(relation_evidence),
            "inventory": _wire_value(inventory),
            "ceiling_bytes": ceiling_bytes,
            "expansion": _wire_value(expansion),
        }
    )


def _render_batch_payload(
    *,
    root: CandidateContextPredecessor,
    source: CandidateContextPredecessor,
    brief: str,
    ledger_digest_value: str,
    reviewer_items: tuple[ReviewerItemSnapshot, ...],
    derived_context: tuple[DerivedFeedbackContext, ...],
    full_members: tuple[CandidateContextFullMember, ...],
    relation_evidence: tuple[CandidateContextRelationEvidence, ...],
    inventory: tuple[CandidateContextInventoryEntry, ...],
) -> bytes:
    """Render the whole ordered batch before enforcing the shared byte ceiling."""
    return _canonical_json_bytes({
        "schema_version": _BATCH_CONTEXT_SCHEMA_VERSION,
        "root": _wire_value(root),
        "source": _wire_value(source),
        "brief": brief,
        "ledger_digest": ledger_digest_value,
        "reviewer_items": _wire_value(reviewer_items),
        "derived_context": _wire_value(derived_context),
        "full_members": [
            {
                "identity": _wire_value(member.identity), "row": _wire_value(member.row),
                "row_digest": member.row_digest,
                "source_spans": _wire_value(
                    tuple(span for span in member.source_spans if span.owning_row_ids is None)
                ),
                **_shared_span_id_wire(member),
                "inclusion_reasons": list(member.inclusion_reasons),
            }
            for member in full_members
        ],
        "shared_source_spans": _shared_span_table(full_members),
        "relation_evidence": _wire_value(relation_evidence),
        "inventory": _wire_value(inventory),
        "ceiling_bytes": CANDIDATE_CONTEXT_MAX_BYTES,
    })


def _shared_span_id_wire(member: CandidateContextFullMember) -> dict[str, list[str]]:
    """A member's shared spans by id; absent when it has none, so unshared batches keep schema-1 size."""
    ids = [span.span_id for span in member.source_spans if span.owning_row_ids is not None]
    return {"shared_source_span_ids": ids} if ids else {}


def _shared_span_table(full_members: Sequence[CandidateContextFullMember]) -> list[object]:
    """Each shared span once, in first-owner order; it was repeated per owner. Single-owner spans stay inline."""
    table: dict[tuple[str, str], object] = {}
    for member in full_members:
        artifact_key = member.identity.artifact_key
        for span in member.source_spans:
            if span.owning_row_ids is not None:
                table.setdefault(
                    (artifact_key, span.span_id), {"artifact_key": artifact_key, **_wire_value(span)}
                )
    return list(table.values())


def _capsule_is_intact(capsule: CandidateContextCapsule) -> bool:
    if (
        not is_supported_candidate_context_ceiling(capsule.ceiling_bytes)
        or capsule.receipt.ceiling_bytes != capsule.ceiling_bytes
        or capsule.receipt.payload_bytes != len(capsule.payload)
    ):
        return False
    payload_digest = _digest_bytes(capsule.payload)
    if (
        payload_digest != capsule.capsule_identity
        or payload_digest != capsule.receipt.payload_digest
        or payload_digest != capsule.receipt.capsule_identity
    ):
        return False
    common_facts = (
        capsule.predecessor == capsule.receipt.predecessor
        and capsule.feedback == capsule.receipt.feedback
        and capsule.relation_evidence == capsule.receipt.relation_evidence
        and capsule.inventory == capsule.receipt.inventory
        and capsule.expansion == capsule.receipt.expansion
        and _member_receipts(capsule.full_members) == capsule.receipt.full_members
    )
    if not common_facts:
        return False
    if not isinstance(capsule, CandidateContextBatchCapsule):
        return capsule.feedback is not None and capsule.feedback == capsule.receipt.feedback
    return (
        capsule.feedback is None
        and capsule.root == capsule.receipt.root
        and capsule.source == capsule.receipt.source
        and capsule.ledger_digest == capsule.receipt.ledger_digest
        and capsule.reviewer_items == capsule.receipt.reviewer_items
        and capsule.derived_context == capsule.receipt.derived_context
    )


def _row_label(row: DesignRow) -> str:
    if isinstance(row, (EntityRow, WorkflowRow, PatternRow, ComponentRow)):
        return row.name
    if isinstance(row, (BusinessRuleRow, ConstraintRow, AssumptionRow)):
        return row.statement
    if isinstance(row, DecisionRow):
        return row.chosen_option
    if isinstance(row, AttributeDispositionRow):
        return row.attribute
    if isinstance(row, PlanRow):
        return row.title
    raise TypeError(f"unsupported impact row type: {type(row).__name__}")


def _row_digest(row: StageRow) -> str:
    return _digest_bytes(
        _canonical_json_bytes({"row_type": type(row).__name__, "row": _wire_value(row)})
    )


def _wire_value(value: object) -> object:
    """Recursively project dataclass and record values onto JSON wire values."""
    unwrapped = unwrap_enum_value(value)
    if unwrapped is not value:
        return _wire_value(unwrapped)
    if isinstance(value, BaseModel):
        return {
            name: _wire_value(getattr(value, name))
            for name in value.__class__.model_fields
            # Single-owner and legacy spans omit the owning set to keep their bytes unchanged.
            if not (name == "owning_row_ids" and getattr(value, name) is None)
        }
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _wire_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple | list):
        return [_wire_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _wire_value(item) for key, item in value.items()}
    if value is None or isinstance(value, str | int | float | bool):
        return value
    raise TypeError(f"candidate context cannot encode {type(value).__name__}")


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _digest_text(value: str) -> str:
    return _digest_bytes(value.encode("utf-8"))


def _digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _refusal(
    reason: CandidateContextRefusalReason,
    detail: str,
    *,
    ceiling_bytes: int | None = None,
    measured_payload_bytes: int | None = None,
    full_members: tuple[CandidateContextMemberReceipt, ...] = (),
    reviewer_items: tuple[ReviewerItemSnapshot, ...] = (),
    derived_context: tuple[DerivedFeedbackContext, ...] = (),
) -> CandidateContextRefusal:
    return CandidateContextRefusal(
        reason=reason,
        detail=detail,
        ceiling_bytes=(
            ceiling_bytes if measured_payload_bytes is not None else None
        ),
        measured_payload_bytes=measured_payload_bytes,
        full_members=full_members,
        reviewer_items=reviewer_items,
        derived_context=derived_context,
    )


def _refused(refusal: CandidateContextRefusal) -> CandidateContextResult:
    return CandidateContextResult(refusal=refusal)
