"""Pure typed comparisons for corresponding roadmap artifact snapshots."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict

from plan_tool.roadmap import RoadmapStage
from plan_tool.roadmap_artifacts import (
    OrderingEntry,
    PlansArtifact,
    RoadmapArtifact,
    StageRow,
    stage_row_collections,
)
from plan_tool.roadmap_relations import RoadmapRelation, extract_declared_relations


class _FrozenDiffRecord(BaseModel):
    """Closed immutable records emitted by the comparison boundary."""

    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, arbitrary_types_allowed=True
    )


class RoadmapArtifactDiff(_FrozenDiffRecord):
    """The raw identities for one artifact whose bytes differ."""

    artifact_key: str
    before_digest: str
    after_digest: str


class RoadmapRowDiff(_FrozenDiffRecord):
    """One source-ordered stable-id row delta with complete typed values."""

    artifact_key: str
    row_type: str
    row_id: str
    before: object | None = None
    after: object | None = None


class RoadmapRelationDiff(_FrozenDiffRecord):
    """One declared relation admitted or removed by row membership."""

    relation: RoadmapRelation


class RoadmapDiff(_FrozenDiffRecord):
    """The deterministic structural comparison between two roadmap snapshots."""

    changed_artifacts: tuple[RoadmapArtifactDiff, ...]
    changed_rows: tuple[RoadmapRowDiff, ...]
    added_relations: tuple[RoadmapRelationDiff, ...]
    removed_relations: tuple[RoadmapRelationDiff, ...]


class RelationOccurrenceDiff(_FrozenDiffRecord):
    """One unmatched declared relation occurrence in its source order."""

    direction: Literal["added", "removed"]
    source_index: int
    relation: RoadmapRelation


def build_roadmap_diff(
    *,
    predecessor_artifacts: Mapping[str, RoadmapArtifact],
    candidate_artifacts: Mapping[str, RoadmapArtifact],
    predecessor_bytes: tuple[bytes, ...],
    candidate_artifacts_bytes: tuple[bytes, ...],
    stages: Sequence[RoadmapStage],
) -> RoadmapDiff:
    """Compare corresponding artifacts, bytes, rows, ordering, and relations."""
    changed_artifacts: list[RoadmapArtifactDiff] = []
    changed_rows: list[RoadmapRowDiff] = []
    for stage, before_bytes, after_bytes in zip(
        stages, predecessor_bytes, candidate_artifacts_bytes, strict=True
    ):
        before = predecessor_artifacts[stage.artifact_key]
        after = candidate_artifacts[stage.artifact_key]
        if before_bytes != after_bytes:
            changed_artifacts.append(
                RoadmapArtifactDiff(
                    artifact_key=stage.artifact_key,
                    before_digest=hashlib.sha256(before_bytes).hexdigest(),
                    after_digest=hashlib.sha256(after_bytes).hexdigest(),
                )
            )
        changed_rows.extend(artifact_row_diffs(stage.artifact_key, before, after))

    occurrences = relation_occurrence_diffs(
        before=extract_declared_relations(**predecessor_artifacts),
        after=extract_declared_relations(**candidate_artifacts),
    )
    return RoadmapDiff(
        changed_artifacts=tuple(changed_artifacts),
        changed_rows=tuple(changed_rows),
        added_relations=tuple(
            RoadmapRelationDiff(relation=occurrence.relation)
            for occurrence in occurrences
            if occurrence.direction == "added"
        ),
        removed_relations=tuple(
            RoadmapRelationDiff(relation=occurrence.relation)
            for occurrence in occurrences
            if occurrence.direction == "removed"
        ),
    )


def relation_occurrence_diffs(
    *, before: tuple[RoadmapRelation, ...], after: tuple[RoadmapRelation, ...]
) -> tuple[RelationOccurrenceDiff, ...]:
    """Return unmatched relation occurrences without collapsing duplicates."""
    unmatched_before = list(enumerate(before))
    added: list[RelationOccurrenceDiff] = []
    for after_index, relation in enumerate(after):
        match_index = next(
            (
                index
                for index, (_before_index, candidate) in enumerate(unmatched_before)
                if same_declared_relation_occurrence(candidate, relation)
            ),
            None,
        )
        if match_index is None:
            added.append(
                RelationOccurrenceDiff(
                    direction="added", source_index=after_index, relation=relation
                )
            )
        else:
            unmatched_before.pop(match_index)
    removed = tuple(
        RelationOccurrenceDiff(
            direction="removed", source_index=before_index, relation=relation
        )
        for before_index, relation in unmatched_before
    )
    return (*removed, *added)


def same_declared_relation_occurrence(left: RoadmapRelation, right: RoadmapRelation) -> bool:
    """Compare one relation occurrence without conflating its source position."""
    return (
        left.kind is right.kind
        and left.owner_id == right.owner_id
        and left.endpoint_id == right.endpoint_id
        and left.owner_artifact_key == right.owner_artifact_key
        and left.direction is right.direction
    )


def _diff_by_id(
    before: Sequence[object], after: Sequence[object], *, id_of: Callable[[object], str]
) -> list[tuple[str, object | None, object | None]]:
    """Return ``(id, before, after)`` for every removed, changed, or added
    member, base then target source order — the shared shape both
    ``artifact_row_diffs`` and ``_ordering_diffs`` bind to a ``RoadmapRowDiff``."""
    before_by_id = {id_of(row): row for row in before}
    after_by_id = {id_of(row): row for row in after}
    diffs = [
        (id_of(row), row, after_by_id.get(id_of(row)))
        for row in before
        if after_by_id.get(id_of(row)) is None or after_by_id[id_of(row)] != row
    ]
    diffs.extend((id_of(row), None, row) for row in after if id_of(row) not in before_by_id)
    return diffs


def artifact_row_diffs(
    artifact_key: str, before: RoadmapArtifact, after: RoadmapArtifact
) -> tuple[RoadmapRowDiff, ...]:
    """Return stable-id row changes in base then target source order."""
    diffs: list[RoadmapRowDiff] = []
    before_collections = dict(ordered_stage_collections(before))
    after_collections = dict(ordered_stage_collections(after))
    # Paired by name: an unrecorded stack is absent from one side, not an empty collection.
    for row_type in (*before_collections, *(n for n in after_collections if n not in before_collections)):
        before_rows = before_collections.get(row_type, ())
        after_rows = after_collections.get(row_type, ())
        diffs.extend(
            RoadmapRowDiff(artifact_key=artifact_key, row_type=row_type, row_id=row_id, before=b, after=a)
            for row_id, b, a in _diff_by_id(before_rows, after_rows, id_of=lambda row: row.id)
        )
    if isinstance(before, PlansArtifact) and isinstance(after, PlansArtifact):
        diffs.extend(_ordering_diffs(artifact_key, before.ordering, after.ordering))
    return tuple(diffs)


def _ordering_diffs(
    artifact_key: str, before: tuple[OrderingEntry, ...], after: tuple[OrderingEntry, ...]
) -> tuple[RoadmapRowDiff, ...]:
    return tuple(
        RoadmapRowDiff(artifact_key=artifact_key, row_type="ordering", row_id=row_id, before=b, after=a)
        for row_id, b, a in _diff_by_id(before, after, id_of=lambda entry: entry.plan_id)
    )


def ordered_stage_collections(
    artifact: RoadmapArtifact,
) -> tuple[tuple[str, tuple[StageRow, ...]], ...]:
    """Return the fixed source order used for roadmap row comparisons.

    See docs/ARCHITECTURE.md's "Read-only snapshot comparison" for why this
    keeps its own fail-closed type guard alongside delegating the rest.
    """
    if not isinstance(artifact, RoadmapArtifact):
        raise TypeError(f"roadmap artifact has unsupported type {type(artifact).__name__}")
    return tuple(stage_row_collections(artifact).items())


# Candidate consumers retain this name while the shared module stays policy-free.
CandidatePredecessorDiff = RoadmapDiff
