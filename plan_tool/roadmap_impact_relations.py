"""Pure declared-relation closure for one roadmap impact target."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from plan_tool.roadmap_artifacts import (
    ComponentsArtifact,
    ConstraintsArtifact,
    DomainArtifact,
    FeedbackTargetKind,
    PlansArtifact,
    RoadmapArtifact,
    design_row_collections,
    impact_node_collections,
)
from plan_tool.roadmap_relations import ARTIFACT_KEYS, ArtifactKey, RoadmapRelation


ImpactClosureVerdict: TypeAlias = Literal[
    "complete",
    "invalid-target",
    "target-not-live-in-selected-artifact",
    "unmappable-relation",
]


@dataclass(frozen=True)
class ImpactTarget:
    """One selected artifact or one selected row within an artifact."""

    kind: FeedbackTargetKind
    artifact_key: ArtifactKey
    row_id: str | None = None


@dataclass(frozen=True)
class ImpactNode:
    """One reached stable graph row, with its owning artifact provenance."""

    artifact_key: ArtifactKey
    row_id: str


@dataclass(frozen=True)
class ImpactRelationEvidence:
    """One reached source relation, kept in its declared direction."""

    source_index: int
    relation: RoadmapRelation
    owner: ImpactNode
    endpoint: ImpactNode


@dataclass(frozen=True)
class ImpactRelationMappingFailure:
    """One declared relation the impact graph cannot map uniquely."""

    source_index: int
    relation: RoadmapRelation
    owner_match_count: int
    endpoint_match_count: int


@dataclass(frozen=True)
class ImpactClosure:
    """The immutable declared-design closure for one selected target."""

    verdict: ImpactClosureVerdict
    nodes: tuple[ImpactNode, ...] = ()
    relations: tuple[ImpactRelationEvidence, ...] = ()
    artifact_keys: tuple[ArtifactKey, ...] = ()
    mapping_failures: tuple[ImpactRelationMappingFailure, ...] = ()


def resolve_impact_closure(
    target: ImpactTarget,
    *,
    domain: DomainArtifact,
    constraints: ConstraintsArtifact,
    components: ComponentsArtifact,
    plans: PlansArtifact,
    relations: tuple[RoadmapRelation, ...],
) -> ImpactClosure:
    """Return the deterministic bidirectional declared closure for ``target``.

    Relation validity is a caller precondition. Only an invalid relation that
    touches this target's growing component rejects the result.
    """
    artifacts = _artifacts_by_key(domain, constraints, components, plans)
    if not _is_well_formed_target(target, artifacts):
        return ImpactClosure(verdict="invalid-target")

    stable_nodes = _stable_nodes(artifacts)
    nodes_by_key = _nodes_by_key(stable_nodes)
    nodes_by_row_id = _nodes_by_row_id(stable_nodes)
    design_node_keys = _design_node_keys(artifacts)
    design_nodes_by_key = {
        key: nodes for key, nodes in nodes_by_key.items() if key in design_node_keys
    }
    root_nodes = _root_nodes(target, design_nodes_by_key)
    if root_nodes is None:
        return ImpactClosure(verdict="target-not-live-in-selected-artifact")

    reached_keys = {(_node.artifact_key, _node.row_id) for _node in root_nodes}
    evidence_by_source_index: dict[int, ImpactRelationEvidence] = {}
    failures_by_source_index: dict[int, ImpactRelationMappingFailure] = {}

    expanded = True
    while expanded:
        expanded = False
        for source_index, relation in enumerate(relations):
            if not _relation_touches_reached(relation, reached_keys):
                continue

            mapped_relation = _map_relation(
                source_index, relation, nodes_by_key, nodes_by_row_id
            )
            if isinstance(mapped_relation, ImpactRelationMappingFailure):
                failures_by_source_index.setdefault(source_index, mapped_relation)
                continue
            owner = mapped_relation.owner
            endpoint = mapped_relation.endpoint

            evidence_by_source_index.setdefault(
                source_index,
                mapped_relation,
            )
            for node in (owner, endpoint):
                node_key = (node.artifact_key, node.row_id)
                if node_key not in reached_keys:
                    reached_keys.add(node_key)
                    expanded = True

    if failures_by_source_index:
        return ImpactClosure(
            verdict="unmappable-relation",
            mapping_failures=tuple(
                failures_by_source_index[source_index]
                for source_index in range(len(relations))
                if source_index in failures_by_source_index
            ),
        )

    reached_nodes = _project_nodes(stable_nodes, reached_keys)
    reached_relations = tuple(
        evidence_by_source_index[source_index]
        for source_index in range(len(relations))
        if source_index in evidence_by_source_index
    )
    return ImpactClosure(
        verdict="complete",
        nodes=reached_nodes,
        relations=reached_relations,
        artifact_keys=_project_artifact_keys(reached_nodes),
    )


def _artifacts_by_key(
    domain: DomainArtifact,
    constraints: ConstraintsArtifact,
    components: ComponentsArtifact,
    plans: PlansArtifact,
) -> dict[ArtifactKey, RoadmapArtifact]:
    return {
        "domain": domain,
        "constraints": constraints,
        "components": components,
        "plans": plans,
    }


def _is_well_formed_target(
    target: object,
    artifacts: dict[ArtifactKey, RoadmapArtifact],
) -> bool:
    if (
        not isinstance(target, ImpactTarget)
        or not isinstance(target.artifact_key, str)
        or target.artifact_key not in artifacts
    ):
        return False
    if target.kind is FeedbackTargetKind.ARTIFACT:
        return target.row_id is None
    if target.kind is FeedbackTargetKind.ROW:
        return isinstance(target.row_id, str) and bool(target.row_id.strip())
    return False


def _stable_nodes(
    artifacts: dict[ArtifactKey, RoadmapArtifact],
) -> tuple[ImpactNode, ...]:
    return tuple(
        ImpactNode(artifact_key=artifact_key, row_id=row.id)
        for artifact_key in ARTIFACT_KEYS
        for rows in impact_node_collections(artifacts[artifact_key]).values()
        for row in rows
    )


def _design_node_keys(
    artifacts: dict[ArtifactKey, RoadmapArtifact],
) -> set[tuple[ArtifactKey, str]]:
    return {
        (artifact_key, row.id)
        for artifact_key in ARTIFACT_KEYS
        for rows in design_row_collections(artifacts[artifact_key]).values()
        for row in rows
    }


def _nodes_by_key(
    nodes: tuple[ImpactNode, ...],
) -> dict[tuple[ArtifactKey, str], tuple[ImpactNode, ...]]:
    # Gates ensure unique row ids; retain grouped matches for direct callers.
    grouped: dict[tuple[ArtifactKey, str], list[ImpactNode]] = {}
    for node in nodes:
        grouped.setdefault((node.artifact_key, node.row_id), []).append(node)
    return {key: tuple(matches) for key, matches in grouped.items()}


def _nodes_by_row_id(
    nodes: tuple[ImpactNode, ...],
) -> dict[str, tuple[ImpactNode, ...]]:
    grouped: dict[str, list[ImpactNode]] = {}
    for node in nodes:
        grouped.setdefault(node.row_id, []).append(node)
    return {row_id: tuple(matches) for row_id, matches in grouped.items()}


def _root_nodes(
    target: ImpactTarget,
    design_nodes_by_key: dict[tuple[ArtifactKey, str], tuple[ImpactNode, ...]],
) -> tuple[ImpactNode, ...] | None:
    if target.kind is FeedbackTargetKind.ARTIFACT:
        return tuple(
            node
            for (artifact_key, _row_id), nodes in design_nodes_by_key.items()
            if artifact_key == target.artifact_key
            for node in nodes
        )

    matches = design_nodes_by_key.get((target.artifact_key, target.row_id), ())
    if len(matches) != 1:
        return None
    return matches


def _map_relation(
    source_index: int,
    relation: RoadmapRelation,
    nodes_by_key: dict[tuple[ArtifactKey, str], tuple[ImpactNode, ...]],
    nodes_by_row_id: dict[str, tuple[ImpactNode, ...]],
) -> ImpactRelationEvidence | ImpactRelationMappingFailure:
    owner_matches = nodes_by_key.get((relation.owner_artifact_key, relation.owner_id), ())
    endpoint_matches = nodes_by_row_id.get(relation.endpoint_id, ())
    if len(owner_matches) != 1 or len(endpoint_matches) != 1:
        return ImpactRelationMappingFailure(
            source_index=source_index,
            relation=relation,
            owner_match_count=len(owner_matches),
            endpoint_match_count=len(endpoint_matches),
        )
    return ImpactRelationEvidence(
        source_index=source_index,
        relation=relation,
        owner=owner_matches[0],
        endpoint=endpoint_matches[0],
    )


def _relation_touches_reached(
    relation: RoadmapRelation,
    reached_keys: set[tuple[ArtifactKey, str]],
) -> bool:
    return (
        (relation.owner_artifact_key, relation.owner_id) in reached_keys
        or any(row_id == relation.endpoint_id for _, row_id in reached_keys)
    )


def _project_nodes(
    stable_nodes: tuple[ImpactNode, ...],
    reached_keys: set[tuple[ArtifactKey, str]],
) -> tuple[ImpactNode, ...]:
    projected: list[ImpactNode] = []
    seen_keys: set[tuple[ArtifactKey, str]] = set()
    for node in stable_nodes:
        node_key = (node.artifact_key, node.row_id)
        if node_key in reached_keys and node_key not in seen_keys:
            projected.append(node)
            seen_keys.add(node_key)
    return tuple(projected)


def _project_artifact_keys(nodes: tuple[ImpactNode, ...]) -> tuple[ArtifactKey, ...]:
    artifact_keys: list[ArtifactKey] = []
    for node in nodes:
        if node.artifact_key not in artifact_keys:
            artifact_keys.append(node.artifact_key)
    return tuple(artifact_keys)
