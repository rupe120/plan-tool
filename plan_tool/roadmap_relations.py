"""Typed, ordered declared-design relations for roadmap artifacts."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from collections.abc import Collection, Iterable
from typing import Literal, Mapping, Optional

from plan_tool.roadmap_artifacts import (
    AssumptionRow,
    BusinessRuleRow,
    ComponentRow,
    ComponentsArtifact,
    ConstraintRow,
    ConstraintsArtifact,
    DecisionRow,
    DomainArtifact,
    EntityRow,
    FieldType,
    OrderingEntry,
    PlanRow,
    PlansArtifact,
    WorkflowRow,
)


class RelationKind(str, enum.Enum):
    """The closed vocabulary of declared design relation fields."""

    FIELD_ENTITY = "field-entity"
    BUSINESS_RULE_ENTITY = "business-rule-entity"
    WORKFLOW_ENTITY = "workflow-entity"
    DECISION_ANCHOR = "decision-anchor"
    CONSTRAINT_ANCHOR = "constraint-anchor"
    COMPONENT_ENTITY = "component-entity"
    COMPONENT_PATTERN = "component-pattern"
    COMPONENT_CONSTRAINT = "component-constraint"
    COMPONENT_STORE = "component-store"
    PLAN_COMPONENT = "plan-component"
    ORDERING_DEPENDS_ON = "ordering-depends-on"
    ORDERING_ASSUMPTION_TARGET = "ordering-assumption-target"
    ASSUMPTION_CONSUMING_PLAN = "assumption-consuming-plan"


class RelationDirection(str, enum.Enum):
    """The declared direction every relation record preserves."""

    OWNER_TO_ENDPOINT = "owner-to-endpoint"


ArtifactKey = Literal["domain", "constraints", "components", "plans"]

ARTIFACT_KEY_DOMAIN: ArtifactKey = "domain"
ARTIFACT_KEY_CONSTRAINTS: ArtifactKey = "constraints"
ARTIFACT_KEY_COMPONENTS: ArtifactKey = "components"
ARTIFACT_KEY_PLANS: ArtifactKey = "plans"
ARTIFACT_KEYS: tuple[ArtifactKey, ...] = (
    ARTIFACT_KEY_DOMAIN,
    ARTIFACT_KEY_CONSTRAINTS,
    ARTIFACT_KEY_COMPONENTS,
    ARTIFACT_KEY_PLANS,
)

ARTIFACT_KEY_BY_TYPE: Mapping[type[object], ArtifactKey] = {
    DomainArtifact: ARTIFACT_KEY_DOMAIN,
    ConstraintsArtifact: ARTIFACT_KEY_CONSTRAINTS,
    ComponentsArtifact: ARTIFACT_KEY_COMPONENTS,
    PlansArtifact: ARTIFACT_KEY_PLANS,
}


@dataclass(frozen=True)
class RoadmapRelation:
    """One relation declared by a stable design row.

    ``owner_row_index`` preserves the owning row's source position for views
    that continue rendering malformed artifacts with duplicate ids.
    """

    kind: RelationKind
    owner_id: str
    endpoint_id: str
    owner_artifact_key: ArtifactKey
    direction: RelationDirection = RelationDirection.OWNER_TO_ENDPOINT
    owner_row_index: int = 0


def _records_for_ids(
    *,
    kind: RelationKind,
    owner_id: str,
    endpoint_ids: tuple[str, ...],
    owner_artifact_key: ArtifactKey,
    owner_row_index: int,
) -> tuple[RoadmapRelation, ...]:
    """Return one owner-to-endpoint record per declared endpoint."""
    return tuple(
        RoadmapRelation(
            kind=kind,
            owner_id=owner_id,
            endpoint_id=endpoint_id,
            owner_artifact_key=owner_artifact_key,
            owner_row_index=owner_row_index,
        )
        for endpoint_id in endpoint_ids
    )


def _row_relation_specs(
    row: object,
) -> tuple[tuple[RelationKind, tuple[str, ...]], ...]:
    """Return one row's relation fields in their declared field order."""
    if isinstance(row, EntityRow):
        return tuple(
            (RelationKind.FIELD_ENTITY, (field.entity_id,))
            for field in row.fields
            if field.type is FieldType.REFERENCE and field.entity_id is not None
        )
    if isinstance(row, BusinessRuleRow):
        return ((RelationKind.BUSINESS_RULE_ENTITY, row.entity_ids),)
    if isinstance(row, WorkflowRow):
        return ((RelationKind.WORKFLOW_ENTITY, row.entity_ids),)
    if isinstance(row, DecisionRow):
        return ((RelationKind.DECISION_ANCHOR, (row.anchor,)),)
    if isinstance(row, ConstraintRow):
        return ((RelationKind.CONSTRAINT_ANCHOR, row.anchor_ids),)
    if isinstance(row, ComponentRow):
        return (
            (RelationKind.COMPONENT_ENTITY, row.entity_ids),
            (RelationKind.COMPONENT_PATTERN, row.pattern_ids),
            (RelationKind.COMPONENT_CONSTRAINT, row.constraint_ids),
            (RelationKind.COMPONENT_STORE, row.store_ids),
        )
    if isinstance(row, PlanRow):
        return ((RelationKind.PLAN_COMPONENT, row.component_ids),)
    if isinstance(row, OrderingEntry):
        return (
            (RelationKind.ORDERING_DEPENDS_ON, row.depends_on),
            (RelationKind.ORDERING_ASSUMPTION_TARGET, row.assumption_targets),
        )
    if isinstance(row, AssumptionRow):
        return ((RelationKind.ASSUMPTION_CONSUMING_PLAN, row.consuming_plan_ids),)
    return ()


def _row_relation_records(
    row: object,
    *,
    owner_artifact_key: ArtifactKey,
    owner_row_index: int,
) -> tuple[RoadmapRelation, ...]:
    owner_id = row.plan_id if isinstance(row, OrderingEntry) else row.id
    return tuple(
        record
        for kind, endpoint_ids in _row_relation_specs(row)
        for record in _records_for_ids(
            kind=kind,
            owner_id=owner_id,
            endpoint_ids=endpoint_ids,
            owner_artifact_key=owner_artifact_key,
            owner_row_index=owner_row_index,
        )
    )


def declared_relation_ids_for_row(row: object) -> tuple[str, ...]:
    """Return a row's declared relation endpoints in canonical field order."""
    return tuple(
        endpoint_id
        for _kind, endpoint_ids in _row_relation_specs(row)
        for endpoint_id in endpoint_ids
    )


def declared_relation_signature_for_row(row: object) -> object:
    """Return the exact immutable relation shape of one editable row."""
    if isinstance(row, EntityRow):
        return tuple((field.name, field.type, field.entity_id) for field in row.fields)
    return _row_relation_specs(row)


def same_declared_row_relations(existing: object, replacement: object) -> bool:
    """Whether a typed row edit leaves every declared relation unchanged."""
    return type(existing) is type(replacement) and (
        declared_relation_signature_for_row(existing)
        == declared_relation_signature_for_row(replacement)
    )


def _component_records(row: ComponentRow, row_index: int) -> tuple[RoadmapRelation, ...]:
    """Return a component's declared relations in frontmatter field order."""
    return _row_relation_records(
        row,
        owner_artifact_key=ARTIFACT_KEY_COMPONENTS,
        owner_row_index=row_index,
    )


def extract_declared_relations(
    *,
    domain: Optional[DomainArtifact] = None,
    constraints: Optional[ConstraintsArtifact] = None,
    components: Optional[ComponentsArtifact] = None,
    plans: Optional[PlansArtifact] = None,
) -> tuple[RoadmapRelation, ...]:
    """Return every declared design relation in stage and source order.

    The parsed artifacts remain authoritative: this extractor neither reads
    files nor decides whether any identifier resolves.
    """
    relations: list[RoadmapRelation] = []

    if domain is not None:
        for entity_index, entity in enumerate(domain.entities):
            relations.extend(
                _row_relation_records(
                    entity,
                    owner_artifact_key=ARTIFACT_KEY_DOMAIN,
                    owner_row_index=entity_index,
                )
            )
        for row_index, row in enumerate(domain.business_rules):
            relations.extend(
                _row_relation_records(
                    row, owner_artifact_key=ARTIFACT_KEY_DOMAIN, owner_row_index=row_index
                )
            )
        for row_index, row in enumerate(domain.workflows):
            relations.extend(
                _row_relation_records(
                    row, owner_artifact_key=ARTIFACT_KEY_DOMAIN, owner_row_index=row_index
                )
            )
        for row_index, row in enumerate(domain.decisions):
            relations.extend(
                _row_relation_records(
                    row, owner_artifact_key=ARTIFACT_KEY_DOMAIN, owner_row_index=row_index
                )
            )

    if constraints is not None:
        for row_index, row in enumerate(constraints.constraints):
            relations.extend(
                _row_relation_records(
                    row, owner_artifact_key=ARTIFACT_KEY_CONSTRAINTS, owner_row_index=row_index
                )
            )
        for row_index, row in enumerate(constraints.decisions):
            relations.extend(
                _row_relation_records(
                    row, owner_artifact_key=ARTIFACT_KEY_CONSTRAINTS, owner_row_index=row_index
                )
            )

    if components is not None:
        for row_index, row in enumerate(components.components):
            relations.extend(_component_records(row, row_index))
        for row_index, row in enumerate(components.decisions):
            relations.extend(
                _row_relation_records(
                    row, owner_artifact_key=ARTIFACT_KEY_COMPONENTS, owner_row_index=row_index
                )
            )

    if plans is not None:
        for row_index, row in enumerate(plans.plans):
            relations.extend(
                _row_relation_records(
                    row, owner_artifact_key=ARTIFACT_KEY_PLANS, owner_row_index=row_index
                )
            )
        for row_index, entry in enumerate(plans.ordering):
            relations.extend(
                _row_relation_records(
                    entry, owner_artifact_key=ARTIFACT_KEY_PLANS, owner_row_index=row_index
                )
            )
        for row_index, row in enumerate(plans.assumptions):
            relations.extend(
                _row_relation_records(
                    row, owner_artifact_key=ARTIFACT_KEY_PLANS, owner_row_index=row_index
                )
            )
        for row_index, row in enumerate(plans.decisions):
            relations.extend(
                _row_relation_records(
                    row, owner_artifact_key=ARTIFACT_KEY_PLANS, owner_row_index=row_index
                )
            )

    return tuple(relations)


def select_declared_relations_for_ids(
    relations: Iterable[RoadmapRelation], row_ids: Collection[str]
) -> tuple[RoadmapRelation, ...]:
    """Return ordered relation records that touch any selected row id."""
    selected_ids = frozenset(row_ids)
    return tuple(
        relation
        for relation in relations
        if relation.owner_id in selected_ids or relation.endpoint_id in selected_ids
    )
