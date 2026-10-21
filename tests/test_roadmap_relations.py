"""Tests for the declared roadmap design-relation inventory."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

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
    FeedbackState,
    FeedbackTarget,
    FeedbackTargetKind,
    FieldRow,
    FieldType,
    OrderingEntry,
    PatternRow,
    PlanDisposition,
    PlanRow,
    PlansArtifact,
    RejectedAlternative,
    RemovalRecord,
    WorkflowRow,
)
from plan_tool.roadmap_relations import (
    ARTIFACT_KEY_COMPONENTS,
    ARTIFACT_KEY_CONSTRAINTS,
    ARTIFACT_KEY_DOMAIN,
    ARTIFACT_KEY_PLANS,
    RelationDirection,
    RelationKind,
    declared_relation_ids_for_row,
    declared_relation_signature_for_row,
    extract_declared_relations,
    same_declared_row_relations,
    select_declared_relations_for_ids,
)

MODULE_PATH = Path(__file__).resolve().parents[1] / "plan_tool" / "roadmap_relations.py"


def decision(id: str, anchor: str) -> DecisionRow:
    return DecisionRow(
        id=id,
        chosen_option=f"Choose {id}.",
        rejected_alternatives=(RejectedAlternative(option="Other", reason="It does not fit."),),
        rationale="It fits the declared design.",
        anchor=anchor,
        status=DecisionStatus.PENDING,
    )


def relation_fixture() -> tuple[
    DomainArtifact, ConstraintsArtifact, ComponentsArtifact, PlansArtifact
]:
    domain = DomainArtifact(
        entities=(
            EntityRow(
                id="entity-order",
                name="Order",
                fields=(
                    FieldRow(
                        name="customer",
                        type=FieldType.REFERENCE,
                        entity_id="entity-customer",
                    ),
                    FieldRow(name="placed_at", type=FieldType.TIMESTAMP),
                ),
            ),
            EntityRow(id="entity-customer", name="Customer", fields=()),
        ),
        business_rules=(
            BusinessRuleRow(
                id="rule-order",
                statement="Orders have customers.",
                entity_ids=("entity-order", "entity-customer"),
            ),
        ),
        workflows=(
            WorkflowRow(
                id="workflow-order",
                name="Place order",
                entity_ids=("entity-order",),
            ),
        ),
        decisions=(decision("decision-domain", "entity-order"),),
        body="domain",
    )
    constraints = ConstraintsArtifact(
        dispositions=(
            AttributeDispositionRow(
                id="attribute-performance",
                attribute="performance",
                disposition=ConstraintDisposition.PRIORITIZED,
            ),
        ),
        constraints=(
            ConstraintRow(
                id="constraint-latency",
                statement="Orders return promptly.",
                attribute="performance",
                anchor_ids=("entity-order", "workflow-order"),
            ),
        ),
        decisions=(decision("decision-constraints", "constraint-latency"),),
        body="constraints",
    )
    components = ComponentsArtifact(
        system_patterns=(
            PatternRow(
                id="pattern-system",
                name="Layered",
                statement="Keep layers separate.",
            ),
        ),
        component_patterns=(
            PatternRow(
                id="pattern-component",
                name="Aggregate",
                statement="Keep writes cohesive.",
            ),
        ),
        components=(
            ComponentRow(
                id="component-orders",
                name="Orders",
                entity_ids=("entity-order", "entity-customer"),
                pattern_ids=("pattern-system", "pattern-component"),
                constraint_ids=("constraint-latency",),
                store_ids=("store-orders", "store-orders"),
            ),
        ),
        decisions=(decision("decision-components", "component-orders"),),
        body="components",
    )
    plans = PlansArtifact(
        plans=(
            PlanRow(
                id="plan-orders",
                title="Orders",
                disposition=PlanDisposition.KEEP,
                component_ids=("component-orders",),
                draft_seed_path="plan-seed-drafts/orders.md",
                sizing_rationale="One component.",
            ),
            PlanRow(
                id="plan-foundation",
                title="Foundation",
                disposition=PlanDisposition.KEEP,
                component_ids=(),
                draft_seed_path="plan-seed-drafts/foundation.md",
                sizing_rationale="Prepares the dependency.",
            ),
        ),
        ordering=(
            OrderingEntry(
                plan_id="plan-orders",
                depends_on=("plan-foundation",),
                assumption_targets=("plan-foundation",),
            ),
        ),
        assumptions=(
            AssumptionRow(
                id="assumption-orders",
                statement="Foundation lands first.",
                consuming_plan_ids=("plan-orders",),
            ),
        ),
        decisions=(decision("decision-plans", "plan-orders"),),
        body="plans",
    )
    return domain, constraints, components, plans


def extract_fixture_relations():
    domain, constraints, components, plans = relation_fixture()
    return extract_declared_relations(
        domain=domain,
        constraints=constraints,
        components=components,
        plans=plans,
    )


def test_extracts_every_declared_design_relation_kind() -> None:
    relations = extract_fixture_relations()

    assert {relation.kind for relation in relations} == set(RelationKind)


def test_row_relation_ids_share_the_extractor_field_mapping() -> None:
    domain, constraints, components, plans = relation_fixture()
    relations = extract_declared_relations(
        domain=domain,
        constraints=constraints,
        components=components,
        plans=plans,
    )
    rows = (
        (domain.entities[0], ARTIFACT_KEY_DOMAIN, (RelationKind.FIELD_ENTITY,)),
        (domain.business_rules[0], ARTIFACT_KEY_DOMAIN, (RelationKind.BUSINESS_RULE_ENTITY,)),
        (constraints.constraints[0], ARTIFACT_KEY_CONSTRAINTS, (RelationKind.CONSTRAINT_ANCHOR,)),
        (
            components.components[0],
            ARTIFACT_KEY_COMPONENTS,
            (
                RelationKind.COMPONENT_ENTITY,
                RelationKind.COMPONENT_PATTERN,
                RelationKind.COMPONENT_CONSTRAINT,
                RelationKind.COMPONENT_STORE,
            ),
        ),
        (plans.plans[0], ARTIFACT_KEY_PLANS, (RelationKind.PLAN_COMPONENT,)),
        (
            plans.ordering[0],
            ARTIFACT_KEY_PLANS,
            (
                RelationKind.ORDERING_DEPENDS_ON,
                RelationKind.ORDERING_ASSUMPTION_TARGET,
            ),
        ),
        (plans.assumptions[0], ARTIFACT_KEY_PLANS, (RelationKind.ASSUMPTION_CONSUMING_PLAN,)),
    )

    for row, artifact_key, relation_kinds in rows:
        owner_id = row.plan_id if isinstance(row, OrderingEntry) else row.id
        expected = tuple(
            relation.endpoint_id
            for relation in relations
            if (
                relation.owner_id == owner_id
                and relation.owner_artifact_key == artifact_key
                and relation.kind in relation_kinds
            )
        )
        assert declared_relation_ids_for_row(row) == expected
    assert all(relation.direction is RelationDirection.OWNER_TO_ENDPOINT for relation in relations)


def test_relation_signature_keeps_field_types_and_relation_collections_distinct() -> None:
    text_field = EntityRow("entity-order", "Order", (FieldRow("id", FieldType.TEXT),))
    number_field = EntityRow("entity-order", "Order", (FieldRow("id", FieldType.NUMBER),))
    component_entity = ComponentRow(
        "component-order", "Orders", ("shared-id",), (), (), ()
    )
    component_pattern = ComponentRow(
        "component-order", "Orders", (), ("shared-id",), (), ()
    )

    assert declared_relation_signature_for_row(text_field) != declared_relation_signature_for_row(
        number_field
    )
    assert declared_relation_signature_for_row(
        component_entity
    ) != declared_relation_signature_for_row(component_pattern)
    assert same_declared_row_relations(text_field, text_field)
    assert not same_declared_row_relations(text_field, number_field)
    assert not same_declared_row_relations(text_field, component_entity)


def test_reference_field_relation_is_owned_by_its_entity() -> None:
    relation = next(
        relation
        for relation in extract_fixture_relations()
        if relation.kind is RelationKind.FIELD_ENTITY
    )

    assert relation.owner_id == "entity-order"
    assert relation.endpoint_id == "entity-customer"
    assert relation.owner_artifact_key == ARTIFACT_KEY_DOMAIN


def test_ordering_relations_are_owned_by_the_named_plan() -> None:
    relations = [
        relation
        for relation in extract_fixture_relations()
        if relation.kind
        in {
            RelationKind.ORDERING_DEPENDS_ON,
            RelationKind.ORDERING_ASSUMPTION_TARGET,
        }
    ]

    assert [(relation.kind, relation.owner_id, relation.endpoint_id) for relation in relations] == [
        (RelationKind.ORDERING_DEPENDS_ON, "plan-orders", "plan-foundation"),
        (
            RelationKind.ORDERING_ASSUMPTION_TARGET,
            "plan-orders",
            "plan-foundation",
        ),
    ]
    assert all(relation.owner_artifact_key == ARTIFACT_KEY_PLANS for relation in relations)


def test_decision_anchors_are_emitted_from_each_artifact() -> None:
    decision_relations = [
        relation
        for relation in extract_fixture_relations()
        if relation.kind is RelationKind.DECISION_ANCHOR
    ]

    assert [relation.owner_artifact_key for relation in decision_relations] == [
        ARTIFACT_KEY_DOMAIN,
        ARTIFACT_KEY_CONSTRAINTS,
        ARTIFACT_KEY_COMPONENTS,
        ARTIFACT_KEY_PLANS,
    ]


def test_relations_preserve_stage_collection_row_and_tuple_order() -> None:
    relations = extract_fixture_relations()

    assert [
        (relation.owner_artifact_key, relation.kind, relation.owner_id, relation.endpoint_id)
        for relation in relations
    ] == [
        (ARTIFACT_KEY_DOMAIN, RelationKind.FIELD_ENTITY, "entity-order", "entity-customer"),
        (ARTIFACT_KEY_DOMAIN, RelationKind.BUSINESS_RULE_ENTITY, "rule-order", "entity-order"),
        (ARTIFACT_KEY_DOMAIN, RelationKind.BUSINESS_RULE_ENTITY, "rule-order", "entity-customer"),
        (ARTIFACT_KEY_DOMAIN, RelationKind.WORKFLOW_ENTITY, "workflow-order", "entity-order"),
        (ARTIFACT_KEY_DOMAIN, RelationKind.DECISION_ANCHOR, "decision-domain", "entity-order"),
        (
            ARTIFACT_KEY_CONSTRAINTS,
            RelationKind.CONSTRAINT_ANCHOR,
            "constraint-latency",
            "entity-order",
        ),
        (
            ARTIFACT_KEY_CONSTRAINTS,
            RelationKind.CONSTRAINT_ANCHOR,
            "constraint-latency",
            "workflow-order",
        ),
        (
            ARTIFACT_KEY_CONSTRAINTS,
            RelationKind.DECISION_ANCHOR,
            "decision-constraints",
            "constraint-latency",
        ),
        (
            ARTIFACT_KEY_COMPONENTS,
            RelationKind.COMPONENT_ENTITY,
            "component-orders",
            "entity-order",
        ),
        (
            ARTIFACT_KEY_COMPONENTS,
            RelationKind.COMPONENT_ENTITY,
            "component-orders",
            "entity-customer",
        ),
        (
            ARTIFACT_KEY_COMPONENTS,
            RelationKind.COMPONENT_PATTERN,
            "component-orders",
            "pattern-system",
        ),
        (
            ARTIFACT_KEY_COMPONENTS,
            RelationKind.COMPONENT_PATTERN,
            "component-orders",
            "pattern-component",
        ),
        (
            ARTIFACT_KEY_COMPONENTS,
            RelationKind.COMPONENT_CONSTRAINT,
            "component-orders",
            "constraint-latency",
        ),
        (ARTIFACT_KEY_COMPONENTS, RelationKind.COMPONENT_STORE, "component-orders", "store-orders"),
        (ARTIFACT_KEY_COMPONENTS, RelationKind.COMPONENT_STORE, "component-orders", "store-orders"),
        (
            ARTIFACT_KEY_COMPONENTS,
            RelationKind.DECISION_ANCHOR,
            "decision-components",
            "component-orders",
        ),
        (ARTIFACT_KEY_PLANS, RelationKind.PLAN_COMPONENT, "plan-orders", "component-orders"),
        (ARTIFACT_KEY_PLANS, RelationKind.ORDERING_DEPENDS_ON, "plan-orders", "plan-foundation"),
        (
            ARTIFACT_KEY_PLANS,
            RelationKind.ORDERING_ASSUMPTION_TARGET,
            "plan-orders",
            "plan-foundation",
        ),
        (
            ARTIFACT_KEY_PLANS,
            RelationKind.ASSUMPTION_CONSUMING_PLAN,
            "assumption-orders",
            "plan-orders",
        ),
        (ARTIFACT_KEY_PLANS, RelationKind.DECISION_ANCHOR, "decision-plans", "plan-orders"),
    ]


def test_repeated_declared_endpoint_is_not_deduplicated() -> None:
    domain = DomainArtifact(
        entities=(),
        business_rules=(
            BusinessRuleRow(
                id="rule-repeat",
                statement="Repeat on purpose.",
                entity_ids=("entity-order", "entity-order"),
            ),
        ),
        workflows=(),
        decisions=(),
        body="domain",
    )

    relations = extract_declared_relations(domain=domain)

    assert [relation.endpoint_id for relation in relations] == [
        "entity-order",
        "entity-order",
    ]


def test_select_declared_relations_for_ids_preserves_order_direction_and_duplicates() -> None:
    relations = extract_fixture_relations()
    selected = select_declared_relations_for_ids(
        relations, {"component-orders", "store-orders", "entity-order"}
    )

    assert [(relation.kind, relation.owner_id, relation.endpoint_id) for relation in selected] == [
        (RelationKind.FIELD_ENTITY, "entity-order", "entity-customer"),
        (RelationKind.BUSINESS_RULE_ENTITY, "rule-order", "entity-order"),
        (RelationKind.WORKFLOW_ENTITY, "workflow-order", "entity-order"),
        (RelationKind.DECISION_ANCHOR, "decision-domain", "entity-order"),
        (RelationKind.CONSTRAINT_ANCHOR, "constraint-latency", "entity-order"),
        (RelationKind.COMPONENT_ENTITY, "component-orders", "entity-order"),
        (RelationKind.COMPONENT_ENTITY, "component-orders", "entity-customer"),
        (RelationKind.COMPONENT_PATTERN, "component-orders", "pattern-system"),
        (RelationKind.COMPONENT_PATTERN, "component-orders", "pattern-component"),
        (RelationKind.COMPONENT_CONSTRAINT, "component-orders", "constraint-latency"),
        (RelationKind.COMPONENT_STORE, "component-orders", "store-orders"),
        (RelationKind.COMPONENT_STORE, "component-orders", "store-orders"),
        (RelationKind.DECISION_ANCHOR, "decision-components", "component-orders"),
        (RelationKind.PLAN_COMPONENT, "plan-orders", "component-orders"),
    ]
    assert all(relation.direction is RelationDirection.OWNER_TO_ENDPOINT for relation in selected)


def test_relation_extraction_excludes_review_and_seed_sidecars() -> None:
    base_domain = DomainArtifact(
        entities=(
            EntityRow(
                id="entity-order",
                name="Order",
                fields=(
                    FieldRow(
                        name="customer",
                        type=FieldType.REFERENCE,
                        entity_id="entity-customer",
                    ),
                ),
            ),
        ),
        business_rules=(),
        workflows=(),
        decisions=(),
        body="domain",
    )
    reviewed_domain = DomainArtifact(
        entities=base_domain.entities,
        business_rules=base_domain.business_rules,
        workflows=base_domain.workflows,
        decisions=base_domain.decisions,
        body="changed body and provenance notes",
        feedback=(
            FeedbackRow(
                id="feedback-1",
                target=FeedbackTarget(
                    kind=FeedbackTargetKind.ROW,
                    row_id="entity-order",
                ),
                request="Split the entity.",
                state=FeedbackState.AWAITING_REVIEW,
            ),
        ),
        removals=(
            RemovalRecord(
                removed_id="entity-old",
                rationale="No longer needed.",
                feedback_ids=("feedback-1",),
            ),
        ),
    )
    sidecar_plans = PlansArtifact(
        plans=(
            PlanRow(
                id="plan-sidecar",
                title="Sidecar-only plan",
                disposition=PlanDisposition.KEEP,
                component_ids=(),
                draft_seed_path="plan-seed-drafts/sidecar.md",
                sizing_rationale="Its seed path is not a relation.",
            ),
        ),
        ordering=(),
        assumptions=(),
        decisions=(),
        body="seed provenance belongs outside the relation inventory",
        feedback=(
            FeedbackRow(
                id="feedback-plan",
                target=FeedbackTarget(
                    kind=FeedbackTargetKind.ARTIFACT,
                ),
                request="Refresh the draft seed.",
                state=FeedbackState.OPEN,
            ),
        ),
        removals=(
            RemovalRecord(
                removed_id="plan-old",
                rationale="The seed replaced it.",
                feedback_ids=("feedback-plan",),
            ),
        ),
    )

    assert extract_declared_relations(
        domain=reviewed_domain,
        plans=sidecar_plans,
    ) == extract_declared_relations(domain=base_domain)


def test_extraction_retains_untrusted_identifiers_without_external_output() -> None:
    domain = DomainArtifact(
        entities=(),
        business_rules=(
            BusinessRuleRow(
                id="rule-untrusted",
                statement="Keep the raw declaration.",
                entity_ids=("../not-receipt-safe",),
            ),
        ),
        workflows=(),
        decisions=(),
        body="domain",
    )

    relations = extract_declared_relations(domain=domain)

    assert relations[0].endpoint_id == "../not-receipt-safe"


def test_relation_context_helper_keeps_roadmap_relations_a_leaf() -> None:
    source = MODULE_PATH.read_text()
    assert re.findall(r"(?m)^\s*(?:from|import) (plan_tool\S*)", source) == [
        "plan_tool.roadmap_artifacts"
    ]

    code = (
        "import sys, types\n"
        "pkg = types.ModuleType('plan_tool')\n"
        f"pkg.__path__ = [{str(MODULE_PATH.parent)!r}]\n"
        "sys.modules['plan_tool'] = pkg\n"
        "import plan_tool.roadmap_relations\n"
        "leaked = sorted(m for m in sys.modules if m.startswith('plan_tool.')"
        " and m not in ('plan_tool.roadmap_relations', 'plan_tool.roadmap_artifacts'))\n"
        "assert not leaked, leaked\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
