"""Tests for the pure roadmap impact-relation closure."""

from __future__ import annotations

import inspect
import re
import subprocess
import sys
from pathlib import Path

import pytest

from plan_tool.roadmap_artifacts import (
    BusinessRuleRow,
    ComponentRow,
    ComponentsArtifact,
    ConstraintRow,
    ConstraintsArtifact,
    DomainArtifact,
    EntityRow,
    FeedbackRow,
    FeedbackState,
    FeedbackTarget,
    FeedbackTargetKind,
    PlanDisposition,
    PlanRow,
    PlansArtifact,
    RemovalRecord,
    StoreRow,
)
from plan_tool.roadmap_impact_relations import (
    ImpactTarget,
    resolve_impact_closure,
)
from plan_tool.roadmap_relations import (
    ARTIFACT_KEY_COMPONENTS,
    ARTIFACT_KEY_CONSTRAINTS,
    ARTIFACT_KEY_DOMAIN,
    ARTIFACT_KEY_PLANS,
    ArtifactKey,
    RelationKind,
    RoadmapRelation,
)


MODULE_PATH = Path(__file__).resolve().parents[1] / "plan_tool" / "roadmap_impact_relations.py"


def _artifacts(
    *,
    domain_ids: tuple[str, ...] = ("domain-a", "domain-b", "domain-isolated"),
    business_rule_ids: tuple[str, ...] = (),
    constraint_ids: tuple[str, ...] = ("constraint-a",),
    component_ids: tuple[str, ...] = ("component-a",),
    plan_ids: tuple[str, ...] = ("plan-a",),
) -> tuple[DomainArtifact, ConstraintsArtifact, ComponentsArtifact, PlansArtifact]:
    return (
        DomainArtifact(
            entities=tuple(
                EntityRow(id=row_id, name=row_id, fields=()) for row_id in domain_ids
            ),
            business_rules=tuple(
                BusinessRuleRow(id=row_id, statement=row_id, entity_ids=())
                for row_id in business_rule_ids
            ),
            workflows=(),
            decisions=(),
            body="domain",
        ),
        ConstraintsArtifact(
            dispositions=(),
            constraints=tuple(
                ConstraintRow(
                    id=row_id,
                    statement=row_id,
                    attribute="performance",
                    anchor_ids=(),
                )
                for row_id in constraint_ids
            ),
            decisions=(),
            body="constraints",
        ),
        ComponentsArtifact(
            system_patterns=(),
            component_patterns=(),
            components=tuple(
                ComponentRow(
                    id=row_id,
                    name=row_id,
                    entity_ids=(),
                    pattern_ids=(),
                )
                for row_id in component_ids
            ),
            decisions=(),
            body="components",
        ),
        PlansArtifact(
            plans=tuple(
                PlanRow(
                    id=row_id,
                    title=row_id,
                    disposition=PlanDisposition.KEEP,
                    component_ids=(),
                    draft_seed_path=f"plan-seed-drafts/{row_id}.md",
                    sizing_rationale=row_id,
                )
                for row_id in plan_ids
            ),
            ordering=(),
            assumptions=(),
            decisions=(),
            body="plans",
        ),
    )


def _relation(
    owner_id: str,
    endpoint_id: str,
    owner_artifact_key: ArtifactKey = ARTIFACT_KEY_DOMAIN,
) -> RoadmapRelation:
    return RoadmapRelation(
        kind=RelationKind.BUSINESS_RULE_ENTITY,
        owner_id=owner_id,
        endpoint_id=endpoint_id,
        owner_artifact_key=owner_artifact_key,
    )


def _resolve(
    target: ImpactTarget,
    relations: tuple[RoadmapRelation, ...],
    artifacts: tuple[DomainArtifact, ConstraintsArtifact, ComponentsArtifact, PlansArtifact]
    | None = None,
):
    domain, constraints, components, plans = artifacts or _artifacts()
    return resolve_impact_closure(
        target,
        domain=domain,
        constraints=constraints,
        components=components,
        plans=plans,
        relations=relations,
    )


def _node_keys(closure) -> list[tuple[str, str]]:
    return [(node.artifact_key, node.row_id) for node in closure.nodes]


def test_row_target_expands_over_incoming_and_outgoing_declared_relations() -> None:
    closure = _resolve(
        ImpactTarget(FeedbackTargetKind.ROW, ARTIFACT_KEY_DOMAIN, "domain-a"),
        (
            _relation("domain-a", "domain-b"),
            _relation("constraint-a", "domain-a", ARTIFACT_KEY_CONSTRAINTS),
        ),
    )

    assert closure.verdict == "complete"
    assert _node_keys(closure) == [
        (ARTIFACT_KEY_DOMAIN, "domain-a"),
        (ARTIFACT_KEY_DOMAIN, "domain-b"),
        (ARTIFACT_KEY_CONSTRAINTS, "constraint-a"),
    ]
    assert [
        (evidence.relation.owner_id, evidence.relation.endpoint_id)
        for evidence in closure.relations
    ] == [("domain-a", "domain-b"), ("constraint-a", "domain-a")]
    assert [(evidence.owner.row_id, evidence.endpoint.row_id) for evidence in closure.relations] == [
        ("domain-a", "domain-b"),
        ("constraint-a", "domain-a"),
    ]


def test_artifact_target_roots_every_stable_design_row_including_an_isolated_row() -> None:
    closure = _resolve(
        ImpactTarget(FeedbackTargetKind.ARTIFACT, ARTIFACT_KEY_DOMAIN),
        (),
    )

    assert closure.verdict == "complete"
    assert _node_keys(closure) == [
        (ARTIFACT_KEY_DOMAIN, "domain-a"),
        (ARTIFACT_KEY_DOMAIN, "domain-b"),
        (ARTIFACT_KEY_DOMAIN, "domain-isolated"),
    ]
    assert closure.relations == ()
    assert closure.artifact_keys == (ARTIFACT_KEY_DOMAIN,)


def test_closure_visits_each_node_once_and_keeps_cyclic_relation_evidence() -> None:
    closure = _resolve(
        ImpactTarget(FeedbackTargetKind.ROW, ARTIFACT_KEY_DOMAIN, "domain-a"),
        (
            _relation("domain-a", "domain-b"),
            _relation("domain-b", "domain-isolated"),
            _relation("domain-isolated", "domain-a"),
        ),
    )

    assert closure.verdict == "complete"
    assert _node_keys(closure) == [
        (ARTIFACT_KEY_DOMAIN, "domain-a"),
        (ARTIFACT_KEY_DOMAIN, "domain-b"),
        (ARTIFACT_KEY_DOMAIN, "domain-isolated"),
    ]
    assert [evidence.source_index for evidence in closure.relations] == [0, 1, 2]


def test_repeated_declared_relations_remain_distinct_closure_evidence() -> None:
    repeated_relation = _relation("domain-a", "domain-b")

    closure = _resolve(
        ImpactTarget(FeedbackTargetKind.ROW, ARTIFACT_KEY_DOMAIN, "domain-a"),
        (repeated_relation, repeated_relation),
    )

    assert closure.verdict == "complete"
    assert [evidence.source_index for evidence in closure.relations] == [0, 1]
    assert [evidence.relation for evidence in closure.relations] == [
        repeated_relation,
        repeated_relation,
    ]


def test_component_store_relation_includes_a_store_as_an_impact_only_node() -> None:
    domain, constraints, _components, plans = _artifacts()
    store = StoreRow(id="store-a", category="relational", sharing="pool")
    components = ComponentsArtifact(
        system_patterns=(),
        component_patterns=(),
        components=(
            ComponentRow(
                id="component-a",
                name="component-a",
                entity_ids=(),
                pattern_ids=(),
                store_ids=(store.id,),
            ),
        ),
        stores=(store,),
        decisions=(),
        body="components",
    )
    relation = RoadmapRelation(
        kind=RelationKind.COMPONENT_STORE,
        owner_id="component-a",
        endpoint_id=store.id,
        owner_artifact_key=ARTIFACT_KEY_COMPONENTS,
    )

    closure = _resolve(
        ImpactTarget(FeedbackTargetKind.ROW, ARTIFACT_KEY_COMPONENTS, "component-a"),
        (relation,),
        (domain, constraints, components, plans),
    )
    assert closure.verdict == "complete"
    assert _node_keys(closure) == [
        (ARTIFACT_KEY_COMPONENTS, "component-a"),
        (ARTIFACT_KEY_COMPONENTS, "store-a"),
    ]
    assert _resolve(
        ImpactTarget(FeedbackTargetKind.ROW, ARTIFACT_KEY_COMPONENTS, "store-a"),
        (relation,),
        (domain, constraints, components, plans),
    ).verdict == "target-not-live-in-selected-artifact"


def test_reached_mapping_failures_report_every_unmappable_relation() -> None:
    domain, constraints, components, plans = _artifacts(domain_ids=("domain-a", "domain-b"))
    first_failure = _relation("domain-a", "missing")
    expansion = _relation("domain-a", "domain-b")
    downstream_failure = _relation("domain-b", "another-missing")

    closure = _resolve(
        ImpactTarget(FeedbackTargetKind.ROW, ARTIFACT_KEY_DOMAIN, "domain-a"),
        (first_failure, expansion, downstream_failure),
        (domain, constraints, components, plans),
    )

    assert closure.verdict == "unmappable-relation"
    assert [
        (
            failure.source_index,
            failure.relation,
            failure.owner_match_count,
            failure.endpoint_match_count,
        )
        for failure in closure.mapping_failures
    ] == [
        (0, first_failure, 1, 0),
        (2, downstream_failure, 1, 0),
    ]


def test_closure_projects_nodes_relations_and_artifacts_in_canonical_order() -> None:
    artifacts = _artifacts(
        domain_ids=("domain-z", "domain-a"),
        business_rule_ids=("domain-rule",),
        constraint_ids=("constraint-b",),
        component_ids=("component-c",),
        plan_ids=("plan-d",),
    )
    closure = _resolve(
        ImpactTarget(FeedbackTargetKind.ROW, ARTIFACT_KEY_DOMAIN, "domain-a"),
        (
            _relation("component-c", "domain-a", ARTIFACT_KEY_COMPONENTS),
            _relation("domain-rule", "domain-a"),
            _relation("domain-a", "constraint-b"),
            _relation("plan-d", "component-c", ARTIFACT_KEY_PLANS),
        ),
        artifacts,
    )

    assert _node_keys(closure) == [
        (ARTIFACT_KEY_DOMAIN, "domain-a"),
        (ARTIFACT_KEY_DOMAIN, "domain-rule"),
        (ARTIFACT_KEY_CONSTRAINTS, "constraint-b"),
        (ARTIFACT_KEY_COMPONENTS, "component-c"),
        (ARTIFACT_KEY_PLANS, "plan-d"),
    ]
    assert [evidence.source_index for evidence in closure.relations] == [0, 1, 2, 3]
    assert closure.artifact_keys == (
        ARTIFACT_KEY_DOMAIN,
        ARTIFACT_KEY_CONSTRAINTS,
        ARTIFACT_KEY_COMPONENTS,
        ARTIFACT_KEY_PLANS,
    )


@pytest.mark.parametrize(
    "endpoint_id, domain_ids",
    [("missing", ("domain-a",)), ("duplicate", ("domain-a", "duplicate"))],
)
def test_unmappable_or_ambiguous_relation_returns_no_partial_closure(
    endpoint_id: str, domain_ids: tuple[str, ...]
) -> None:
    artifacts = _artifacts(
        domain_ids=domain_ids,
        constraint_ids=("duplicate",) if endpoint_id == "duplicate" else (),
    )

    closure = _resolve(
        ImpactTarget(FeedbackTargetKind.ROW, ARTIFACT_KEY_DOMAIN, "domain-a"),
        (_relation("domain-a", endpoint_id),),
        artifacts,
    )

    assert closure.verdict == "unmappable-relation"
    assert closure.nodes == ()
    assert closure.relations == ()
    assert closure.artifact_keys == ()
    assert [
        (
            failure.source_index,
            failure.owner_match_count,
            failure.endpoint_match_count,
        )
        for failure in closure.mapping_failures
    ] == [(0, 1, 0 if endpoint_id == "missing" else 2)]


def test_disconnected_unmappable_relation_does_not_block_the_selected_component() -> None:
    relations = (
        _relation("domain-a", "domain-b"),
        _relation("constraint-a", "missing", ARTIFACT_KEY_CONSTRAINTS),
    )
    target = ImpactTarget(FeedbackTargetKind.ROW, ARTIFACT_KEY_DOMAIN, "domain-a")

    closure = _resolve(target, relations)
    incident_failure = _resolve(target, (*relations, _relation("domain-b", "missing")))

    assert closure.verdict == "complete"
    assert [evidence.source_index for evidence in closure.relations] == [0]
    assert incident_failure.verdict == "unmappable-relation"
    assert incident_failure.nodes == ()


def test_row_target_must_be_live_in_its_selected_artifact() -> None:
    wrong_artifact = _resolve(
        ImpactTarget(FeedbackTargetKind.ROW, ARTIFACT_KEY_CONSTRAINTS, "domain-a"),
        (),
    )
    missing_row = _resolve(
        ImpactTarget(FeedbackTargetKind.ROW, ARTIFACT_KEY_DOMAIN, "missing"),
        (),
    )

    assert wrong_artifact.verdict == "target-not-live-in-selected-artifact"
    assert missing_row.verdict == "target-not-live-in-selected-artifact"
    malformed = _resolve(
        ImpactTarget(FeedbackTargetKind.ARTIFACT, ARTIFACT_KEY_DOMAIN, "domain-a"),
        (),
    )

    assert wrong_artifact.nodes == missing_row.nodes == malformed.nodes == ()
    assert malformed.verdict == "invalid-target"


def test_feedback_removals_seed_data_and_receipt_reason_cannot_expand_closure() -> None:
    domain, constraints, components, plans = _artifacts()
    reviewed_domain = DomainArtifact(
        entities=domain.entities,
        business_rules=domain.business_rules,
        workflows=domain.workflows,
        decisions=domain.decisions,
        body="review prose cannot add closure members",
        feedback=(
            FeedbackRow(
                id="feedback-1",
                target=FeedbackTarget(FeedbackTargetKind.ROW, "domain-isolated"),
                request="Review the isolated row.",
                state=FeedbackState.OPEN,
            ),
        ),
        removals=(
            RemovalRecord(
                removed_id="removed-row",
                rationale="A review record is not a design relation.",
                feedback_ids=("feedback-1",),
            ),
        ),
    )

    closure = _resolve(
        ImpactTarget(FeedbackTargetKind.ROW, ARTIFACT_KEY_DOMAIN, "domain-a"),
        (_relation("domain-a", "domain-b"),),
        (reviewed_domain, constraints, components, plans),
    )

    assert _node_keys(closure) == [
        (ARTIFACT_KEY_DOMAIN, "domain-a"),
        (ARTIFACT_KEY_DOMAIN, "domain-b"),
    ]
    assert "reason" not in inspect.signature(resolve_impact_closure).parameters


def test_impact_relations_module_imports_only_artifact_and_relation_contracts() -> None:
    source = MODULE_PATH.read_text()
    assert re.findall(r"(?m)^\s*(?:from|import) (plan_tool\S*)", source) == [
        "plan_tool.roadmap_artifacts",
        "plan_tool.roadmap_relations",
    ]

    code = (
        "import sys, types\n"
        "pkg = types.ModuleType('plan_tool')\n"
        f"pkg.__path__ = [{str(MODULE_PATH.parent)!r}]\n"
        "sys.modules['plan_tool'] = pkg\n"
        "import plan_tool.roadmap_impact_relations\n"
        "allowed = {'plan_tool.roadmap_impact_relations', "
        "'plan_tool.roadmap_artifacts', 'plan_tool.roadmap_relations'}\n"
        "leaked = sorted(m for m in sys.modules if m.startswith('plan_tool.') "
        "and m not in allowed)\n"
        "assert not leaked, leaked\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
