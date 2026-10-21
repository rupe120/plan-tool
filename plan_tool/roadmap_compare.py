"""Pure comparison facts that bind typed roadmap deltas to raw patch evidence."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

from plan_tool.roadmap_artifacts import (
    AssumptionRow,
    BusinessRuleRow,
    ComponentRow,
    ConstraintRow,
    DecisionRow,
    EntityRow,
    FieldRow,
    FieldType,
    OrderingEntry,
    PlanRow,
    WorkflowRow,
)
from plan_tool.roadmap_diff import RoadmapDiff, RoadmapRelationDiff, RoadmapRowDiff
from plan_tool.roadmap_versions import VERSION_ARTIFACT_KEYS


class _FrozenComparisonRecord(BaseModel):
    """Closed immutable records emitted by the presentation-neutral comparison leaf."""

    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, arbitrary_types_allowed=True
    )


class ComparisonField(_FrozenComparisonRecord):
    """One non-relation field whose typed value differs between shared endpoints."""

    name: str
    before: object | None
    after: object | None


class ComparisonCard(_FrozenComparisonRecord):
    """One stable-id roadmap concept with complete typed endpoints."""

    artifact_key: str
    row_type: str
    row_id: str
    change_kind: Literal["added", "removed", "changed"]
    before: object | None
    after: object | None
    changed_fields: tuple[ComparisonField, ...]


class RawPatchEvidence(_FrozenComparisonRecord):
    """The complete, untouched unified patch for one fixed artifact pair."""

    artifact_key: str
    patch: str


class UnmappedRawEvidence(_FrozenComparisonRecord):
    """A byte-changed artifact with no corresponding typed comparison fact."""

    artifact_key: str


class ComparisonProseAmendment(_FrozenComparisonRecord):
    """One candidate-bound prose fragment included in this comparison."""

    artifact_key: str
    row_id: str
    fragment: str


class ComparisonProseAmendmentEvidence(_FrozenComparisonRecord):
    """Whether candidate provenance can bind prose fragments to this pair."""

    outcome: Literal["bound", "not-applicable", "not-directly-bound", "no-operation-evidence"]
    amendments: tuple[ComparisonProseAmendment, ...]


class RoadmapComparison(_FrozenComparisonRecord):
    """Ordered comparison facts and exact raw evidence for one snapshot pair."""

    cards: tuple[ComparisonCard, ...]
    added_relations: tuple[RoadmapRelationDiff, ...]
    removed_relations: tuple[RoadmapRelationDiff, ...]
    raw_evidence: tuple[RawPatchEvidence, ...]
    unmapped_raw_evidence: tuple[UnmappedRawEvidence, ...]
    prose_amendment_evidence: ComparisonProseAmendmentEvidence
    raw_evidence_identity: str


_RELATION_FIELD_NAMES: dict[type[object], frozenset[str]] = {
    BusinessRuleRow: frozenset({"entity_ids"}),
    WorkflowRow: frozenset({"entity_ids"}),
    DecisionRow: frozenset({"anchor"}),
    ConstraintRow: frozenset({"anchor_ids"}),
    ComponentRow: frozenset(
        {"entity_ids", "pattern_ids", "constraint_ids", "store_ids"}
    ),
    PlanRow: frozenset({"component_ids"}),
    OrderingEntry: frozenset({"depends_on", "assumption_targets"}),
    AssumptionRow: frozenset({"consuming_plan_ids"}),
}


def build_roadmap_comparison(
    *,
    typed_diff: RoadmapDiff,
    raw_patches: Mapping[str, str],
    prose_amendment_evidence: ComparisonProseAmendmentEvidence | None = None,
) -> RoadmapComparison:
    """Bind one shared typed diff to complete patches in inventory order.

    The caller supplies every fixed artifact pair, including unchanged pairs
    whose patch is empty. This leaf deliberately does not validate whether a
    patch was collected correctly; Git collection owns that boundary.
    """
    raw_evidence = _ordered_raw_evidence(raw_patches)
    cards = tuple(
        card
        for row_diff in typed_diff.changed_rows
        if (card := _card_for_row_diff(row_diff)) is not None
    )
    typed_artifacts = {row.artifact_key for row in typed_diff.changed_rows}
    typed_artifacts.update(
        item.relation.owner_artifact_key
        for item in (*typed_diff.added_relations, *typed_diff.removed_relations)
    )
    unmapped = tuple(
        UnmappedRawEvidence(artifact_key=item.artifact_key)
        for item in typed_diff.changed_artifacts
        if item.artifact_key not in typed_artifacts
    )
    return RoadmapComparison(
        cards=cards,
        added_relations=typed_diff.added_relations,
        removed_relations=typed_diff.removed_relations,
        raw_evidence=raw_evidence,
        unmapped_raw_evidence=unmapped,
        prose_amendment_evidence=(
            prose_amendment_evidence
            if prose_amendment_evidence is not None
            else ComparisonProseAmendmentEvidence(outcome="not-applicable", amendments=())
        ),
        raw_evidence_identity=raw_evidence_identity(raw_evidence),
    )


def raw_evidence_identity(raw_evidence: tuple[RawPatchEvidence, ...]) -> str:
    """Hash framed artifact bindings without normalizing supplied patch text."""
    digest = hashlib.sha256()
    for evidence in raw_evidence:
        _update_framed(digest, evidence.artifact_key.encode("utf-8"))
        _update_framed(digest, evidence.patch.encode("utf-8"))
    return digest.hexdigest()


def _ordered_raw_evidence(raw_patches: Mapping[str, str]) -> tuple[RawPatchEvidence, ...]:
    inventory_keys = VERSION_ARTIFACT_KEYS
    if set(raw_patches) != set(inventory_keys):
        raise ValueError("raw patches must bind exactly the fixed artifact inventory")
    if any(not isinstance(raw_patches[key], str) for key in inventory_keys):
        raise TypeError("raw patches must be text")
    return tuple(
        RawPatchEvidence(artifact_key=key, patch=raw_patches[key])
        for key in inventory_keys
    )


def _card_for_row_diff(row_diff: RoadmapRowDiff) -> ComparisonCard | None:
    if row_diff.before is None:
        return ComparisonCard(
            artifact_key=row_diff.artifact_key, row_type=row_diff.row_type,
            row_id=row_diff.row_id, change_kind="added", before=None, after=row_diff.after,
            changed_fields=_all_projected_fields(row_diff.after, direction="added"),
        )
    if row_diff.after is None:
        return ComparisonCard(
            artifact_key=row_diff.artifact_key, row_type=row_diff.row_type,
            row_id=row_diff.row_id, change_kind="removed", before=row_diff.before, after=None,
            changed_fields=_all_projected_fields(row_diff.before, direction="removed"),
        )
    changed_fields = _changed_projected_fields(row_diff.before, row_diff.after)
    if not changed_fields and row_diff.row_type != "ordering":
        return None
    return ComparisonCard(
        artifact_key=row_diff.artifact_key, row_type=row_diff.row_type,
        row_id=row_diff.row_id, change_kind="changed", before=row_diff.before,
        after=row_diff.after, changed_fields=changed_fields,
    )


def _all_projected_fields(
    row: object, *, direction: Literal["added", "removed"]
) -> tuple[ComparisonField, ...]:
    """Represent every non-relation field on a one-sided concept endpoint."""
    return tuple(
        ComparisonField(
            name=name,
            before=value if direction == "removed" else None,
            after=value if direction == "added" else None,
        )
        for name, value in _projected_field_values(row)
    )


def _changed_projected_fields(before: object, after: object) -> tuple[ComparisonField, ...]:
    before_values = dict(_projected_field_values(before))
    after_values = dict(_projected_field_values(after))
    is_entity = isinstance(before, EntityRow)
    return tuple(
        ComparisonField(name=name, before=value, after=after_values.get(name))
        for name, value in before_values.items()
        if _stripped_for_comparison(is_entity, name, value)
        != _stripped_for_comparison(is_entity, name, after_values.get(name))
    )


def _projected_field_values(row: object) -> tuple[tuple[str, object], ...]:
    if not is_dataclass(row):
        raise TypeError(f"roadmap comparison row must be a dataclass, got {type(row).__name__}")
    relation_fields = _RELATION_FIELD_NAMES.get(type(row), frozenset())
    return tuple(
        (field.name, getattr(row, field.name))
        for field in fields(row)
        if field.name not in relation_fields
    )


def _stripped_for_comparison(is_entity: bool, name: str, value: object) -> object:
    """Ignore ``FieldRow.entity_id`` only where ``_row_relation_specs`` treats
    it as a relation — never for the value actually displayed. See
    docs/ARCHITECTURE.md's "Read-only snapshot comparison" for the why."""
    if is_entity and name == "fields":
        return tuple(
            FieldRow(item.name, item.type)
            if item.type is FieldType.REFERENCE
            else item
            for item in value
        )
    return value


def _update_framed(digest: object, value: bytes) -> None:
    digest.update(len(value).to_bytes(8, "big"))
    digest.update(value)
