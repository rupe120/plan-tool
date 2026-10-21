"""Direct contract tests for typed roadmap snapshot comparison."""

from __future__ import annotations

import pytest

from plan_tool.roadmap import STAGES
from plan_tool.roadmap_artifacts import (
    BusinessRuleRow,
    DomainArtifact,
    EntityRow,
    FieldRow,
    FieldType,
    OrderingEntry,
    PlanDisposition,
    PlanRow,
    PlansArtifact,
)
from plan_tool.roadmap_diff import (
    artifact_row_diffs,
    build_roadmap_diff,
    ordered_stage_collections,
    relation_occurrence_diffs,
)
from plan_tool.roadmap_relations import RelationKind, RoadmapRelation


def _domain(*entities: EntityRow, rules: tuple[BusinessRuleRow, ...] = ()) -> DomainArtifact:
    return DomainArtifact(
        entities=entities, business_rules=rules, workflows=(), decisions=(), body="domain\n"
    )


def _domain_diff(before: DomainArtifact, after: DomainArtifact, before_bytes: bytes = b"before", after_bytes: bytes = b"after"):
    return build_roadmap_diff(
        predecessor_artifacts={"domain": before},
        candidate_artifacts={"domain": after},
        predecessor_bytes=(before_bytes,),
        candidate_artifacts_bytes=(after_bytes,),
        stages=STAGES[:1],
    )


def test_identical_artifacts_have_no_typed_or_artifact_diffs() -> None:
    artifact = _domain(EntityRow("entity-order", "Order", ()))

    diff = _domain_diff(artifact, artifact, b"same", b"same")

    assert diff.changed_artifacts == ()
    assert diff.changed_rows == ()
    assert diff.added_relations == ()
    assert diff.removed_relations == ()


def test_changed_row_reports_complete_before_and_after_values() -> None:
    before = _domain(EntityRow("entity-order", "Order", ()))
    after = _domain(EntityRow("entity-order", "Purchase order", ()))

    diff = _domain_diff(before, after)

    assert diff.changed_artifacts[0].artifact_key == "domain"
    assert diff.changed_rows[0].before == before.entities[0]
    assert diff.changed_rows[0].after == after.entities[0]


def test_removed_and_added_stable_ids_remain_distinct_row_diffs() -> None:
    diff = _domain_diff(
        _domain(EntityRow("entity-order", "Order", ())),
        _domain(EntityRow("entity-purchase", "Order", ())),
    )

    assert [(row.row_id, row.before is None, row.after is None) for row in diff.changed_rows] == [
        ("entity-order", False, True),
        ("entity-purchase", True, False),
    ]


def test_plan_ordering_change_is_retained_as_a_typed_diff() -> None:
    plan = PlanRow("plan-order", "Order", PlanDisposition.KEEP, (), "draft.md", "Bound it.")
    before = PlansArtifact((plan,), (OrderingEntry(plan.id),), (), (), "plans\n")
    after = PlansArtifact((plan,), (OrderingEntry(plan.id, depends_on=("plan-other",)),), (), (), "plans\n")

    diffs = artifact_row_diffs("plans", before, after)

    assert [(row.row_type, row.row_id) for row in diffs] == [("ordering", plan.id)]


def test_relation_only_change_retains_candidate_row_diff_and_relation_occurrence() -> None:
    before = _domain(EntityRow("entity-order", "Order", (FieldRow("customer", FieldType.REFERENCE, "customer"),)))
    after = _domain(EntityRow("entity-order", "Order", (FieldRow("customer", FieldType.REFERENCE, "account"),)))

    diff = _domain_diff(before, after)

    assert [row.row_id for row in diff.changed_rows] == ["entity-order"]
    assert [item.relation.endpoint_id for item in diff.added_relations] == ["account"]
    assert [item.relation.endpoint_id for item in diff.removed_relations] == ["customer"]


def test_repeated_relation_occurrences_are_not_collapsed() -> None:
    relation = RoadmapRelation(RelationKind.BUSINESS_RULE_ENTITY, "rule", "entity", "domain")

    diffs = relation_occurrence_diffs(before=(), after=(relation, relation))

    assert [(item.direction, item.source_index) for item in diffs] == [("added", 0), ("added", 1)]


def test_row_diff_order_follows_base_then_target_source_order() -> None:
    before = _domain(EntityRow("removed", "Removed", ()), EntityRow("changed", "Old", ()))
    after = _domain(EntityRow("changed", "New", ()), EntityRow("added", "Added", ()))

    diff = _domain_diff(before, after)

    assert [row.row_id for row in diff.changed_rows] == ["removed", "changed", "added"]


def test_ordered_stage_collections_refuses_an_unsupported_artifact_type() -> None:
    """Kept as its own fail-closed guard rather than trusting
    stage_row_collections's permissive fallback (see docs/ARCHITECTURE.md) —
    pin that the guard actually fires, not just that the docstring says so."""
    with pytest.raises(TypeError, match="unsupported type"):
        ordered_stage_collections(object())


@pytest.mark.parametrize("side", ["before", "after"])
def test_row_diff_with_an_absent_side_round_trips_when_none_is_excluded(side: str) -> None:
    """An added row has no `before` and a removed row no `after`; evidence is
    rendered with exclude_none, so the absent side must reload from its default
    rather than fail 'Field required' (an added/removed-row candidate otherwise
    refuses as 'candidate proposal evidence is invalid')."""
    import json

    from plan_tool.roadmap_artifacts import EntityRow
    from plan_tool.roadmap_diff import RoadmapRowDiff

    row = EntityRow("entity-order", "Order", ())
    sides = {"before": row, "after": row, side: None}
    diff = RoadmapRowDiff(
        artifact_key="domain", row_type="entities", row_id="entity-order", **sides
    )
    dumped = json.dumps(diff.model_dump(mode="json", exclude_none=True))
    assert getattr(RoadmapRowDiff.model_validate_json(dumped), side) is None


def test_a_stack_less_artifact_diffs_against_a_stack_bearing_one_by_collection_name() -> None:
    """An unrecorded stack is absent from one side's collections, not an empty
    collection, so pairing collections by position would raise. Each added
    stack row is reported once, and an identical stack-less pair reports nothing."""
    from plan_tool.roadmap_artifacts import ConstraintsArtifact, StackRow

    stackless = ConstraintsArtifact(dispositions=(), constraints=(), decisions=(), body="b")
    rows = (StackRow("stack-platform", "platform", choice="managed"),)
    stacked = ConstraintsArtifact(
        dispositions=(), constraints=(), decisions=(), body="b", stack=rows
    )

    forward = artifact_row_diffs("constraints", stackless, stacked)
    backward = artifact_row_diffs("constraints", stacked, stackless)

    assert [(d.row_type, d.row_id, d.before, d.after) for d in forward] == [
        ("stack", "stack-platform", None, rows[0])
    ]
    assert [(d.row_type, d.row_id, d.before, d.after) for d in backward] == [
        ("stack", "stack-platform", rows[0], None)
    ]
    assert artifact_row_diffs("constraints", stackless, stackless) == ()
