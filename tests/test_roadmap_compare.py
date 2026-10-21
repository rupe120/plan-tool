"""Contracts for typed roadmap comparison facts and complete raw evidence."""

from __future__ import annotations

import typing

import pytest

from plan_tool.roadmap import STAGES
from plan_tool.roadmap_artifacts import (
    AssumptionRow, AttributeDispositionRow, BusinessRuleRow, ComponentRow,
    ConstraintDisposition, ConstraintRow, DecisionRow, DecisionStatus,
    DomainArtifact, EntityRow, FieldRow, FieldType, HostingRow, OrderingEntry,
    PatternRow, PlanDisposition, PlanRow, PlansArtifact, StackRow, StageRow, StoreRow, WorkflowRow,
)
from plan_tool.roadmap_compare import (
    _RELATION_FIELD_NAMES,
    _stripped_for_comparison,
    build_roadmap_comparison,
)
from plan_tool.roadmap_diff import build_roadmap_diff
from plan_tool.roadmap_relations import _row_relation_specs


def _domain(*entities: EntityRow) -> DomainArtifact:
    return DomainArtifact(entities, (), (), (), "domain\n")


def _patches(**overrides: str) -> dict[str, str]:
    return {key: overrides.get(key, "") for key in ("domain", "constraints", "components", "plans")}


def _comparison(before: DomainArtifact, after: DomainArtifact, *, before_bytes: bytes = b"before", after_bytes: bytes = b"after", patches: dict[str, str] | None = None):
    diff = build_roadmap_diff(predecessor_artifacts={"domain": before}, candidate_artifacts={"domain": after}, predecessor_bytes=(before_bytes,), candidate_artifacts_bytes=(after_bytes,), stages=STAGES[:1])
    return build_roadmap_comparison(typed_diff=diff, raw_patches=patches or _patches(domain="patch"))


def test_changed_row_becomes_one_card_with_complete_endpoints() -> None:
    before = _domain(EntityRow("order", "Order", ()))
    after = _domain(EntityRow("order", "Purchase", ()))

    comparison = _comparison(before, after)

    assert comparison.cards[0].change_kind == "changed"
    assert comparison.cards[0].before == before.entities[0]
    assert comparison.cards[0].after == after.entities[0]
    assert comparison.cards[0].changed_fields[0].name == "name"


def test_stable_id_change_remains_removed_then_added_cards() -> None:
    comparison = _comparison(_domain(EntityRow("old", "Order", ())), _domain(EntityRow("new", "Order", ())))

    assert [(card.row_id, card.change_kind) for card in comparison.cards] == [("old", "removed"), ("new", "added")]


def test_card_order_uses_shared_base_then_target_order() -> None:
    comparison = _comparison(_domain(EntityRow("removed", "Removed", ()), EntityRow("changed", "Old", ())), _domain(EntityRow("changed", "New", ()), EntityRow("added", "Added", ())))

    assert [card.row_id for card in comparison.cards] == ["removed", "changed", "added"]


def test_ordering_entry_is_a_separate_comparison_card() -> None:
    plan = PlanRow("plan", "Plan", PlanDisposition.KEEP, (), "plan.md", "Bound it.")
    before = PlansArtifact((plan,), (OrderingEntry("plan"),), (), (), "plans\n")
    after = PlansArtifact((plan,), (OrderingEntry("plan", depends_on=("other",)),), (), (), "plans\n")
    diff = build_roadmap_diff(predecessor_artifacts={"plans": before}, candidate_artifacts={"plans": after}, predecessor_bytes=(b"before",), candidate_artifacts_bytes=(b"after",), stages=STAGES[3:])

    comparison = build_roadmap_comparison(typed_diff=diff, raw_patches=_patches(plans="patch"))

    assert [(card.row_type, card.row_id) for card in comparison.cards] == [("ordering", "plan")]


def test_changed_card_excludes_declared_relation_fields() -> None:
    before = _domain(EntityRow("order", "Order", (FieldRow("customer", FieldType.REFERENCE, "customer"),)))
    after = _domain(EntityRow("order", "Purchase", (FieldRow("customer", FieldType.REFERENCE, "account"),)))

    comparison = _comparison(before, after)

    assert [field.name for field in comparison.cards[0].changed_fields] == ["name"]


def test_changed_card_keeps_the_real_entity_id_when_fields_changes_for_another_reason() -> None:
    """A field rename (not a relation change) must still show the real,
    unmasked ``entity_id`` in the displayed field — not the value stripped
    for equality-only comparison against the separately reported relation diff."""
    before = _domain(EntityRow("order", "Order", (FieldRow("customer", FieldType.REFERENCE, "acct1"),)))
    after = _domain(EntityRow("order", "Order", (FieldRow("cust", FieldType.REFERENCE, "acct1"),)))

    comparison = _comparison(before, after)

    changed = {field.name: field for field in comparison.cards[0].changed_fields}
    assert changed["fields"].before == before.entities[0].fields
    assert changed["fields"].after == after.entities[0].fields
    assert changed["fields"].before[0].entity_id == "acct1"
    assert changed["fields"].after[0].entity_id == "acct1"


def test_non_reference_field_entity_id_change_still_produces_a_card() -> None:
    """A field's parser-unenforced stray ``entity_id`` on a non-REFERENCE
    type is not captured by ``_row_relation_specs`` as a relation (it only
    fires for REFERENCE), so it must not be stripped from comparison either
    — stripping it regardless of type would make the change invisible:
    no card, no relation, not even unmapped raw evidence."""
    before = _domain(EntityRow("order", "Order", (FieldRow("note", FieldType.TEXT, "stray-1"),)))
    after = _domain(EntityRow("order", "Order", (FieldRow("note", FieldType.TEXT, "stray-2"),)))

    comparison = _comparison(before, after)

    assert [card.row_id for card in comparison.cards] == ["order"]
    assert comparison.cards[0].changed_fields[0].name == "fields"
    assert comparison.added_relations == ()
    assert comparison.removed_relations == ()


def test_entity_field_stripping_matches_relation_specs_exactly_by_field_type() -> None:
    """The nested per-field relation rule (``FieldRow.entity_id``, only for
    REFERENCE fields) is EntityRow's own parity case, distinct from the
    other 8 row types' top-level ``_RELATION_FIELD_NAMES`` entries — pinned
    separately since it can't share their generic parametrization."""
    row = EntityRow(
        "e1", "Entity",
        (
            FieldRow("ref", FieldType.REFERENCE, "sentinel-reference-target"),
            FieldRow("note", FieldType.TEXT, "sentinel-stray-entity-id"),
        ),
    )

    endpoint_ids = _endpoint_ids(row)
    assert endpoint_ids == {"sentinel-reference-target"}

    stripped = _stripped_for_comparison(True, "fields", row.fields)
    surviving_entity_ids = {field.entity_id for field in stripped if field.entity_id is not None}
    assert surviving_entity_ids == {"sentinel-stray-entity-id"}
    assert surviving_entity_ids.isdisjoint(endpoint_ids)


def test_relation_only_change_has_no_card_and_keeps_duplicate_occurrences() -> None:
    before = _domain(EntityRow("order", "Order", (FieldRow("customer", FieldType.REFERENCE, "customer"), FieldRow("billing", FieldType.REFERENCE, "customer"))))
    after = _domain(EntityRow("order", "Order", (FieldRow("customer", FieldType.REFERENCE, "account"), FieldRow("billing", FieldType.REFERENCE, "account"))))

    comparison = _comparison(before, after)

    assert comparison.cards == ()
    assert [item.relation.endpoint_id for item in comparison.added_relations] == ["account", "account"]
    assert [item.relation.endpoint_id for item in comparison.removed_relations] == ["customer", "customer"]


def test_reference_field_entity_id_from_none_is_also_a_relation_only_change() -> None:
    """A REFERENCE field's entity_id transitioning from None (unset) to a
    real target is not a special case — it's a relation-only change like any
    other retarget: no card, but a genuine added relation, not silently
    dropped everywhere."""
    before = _domain(EntityRow("order", "Order", (FieldRow("customer", FieldType.REFERENCE, None),)))
    after = _domain(EntityRow("order", "Order", (FieldRow("customer", FieldType.REFERENCE, "account-1"),)))

    comparison = _comparison(before, after)

    assert comparison.cards == ()
    assert [item.relation.endpoint_id for item in comparison.added_relations] == ["account-1"]
    assert comparison.removed_relations == ()


def test_raw_only_byte_change_is_reported_as_unmapped() -> None:
    artifact = _domain(EntityRow("order", "Order", ()))

    comparison = _comparison(artifact, artifact, before_bytes=b"old prose", after_bytes=b"new prose")

    assert comparison.cards == ()
    assert comparison.unmapped_raw_evidence[0].artifact_key == "domain"


def test_mixed_typed_and_raw_byte_change_preserves_complete_patch_without_partition() -> None:
    comparison = _comparison(_domain(EntityRow("order", "Order", ())), _domain(EntityRow("order", "Purchase", ())), patches=_patches(domain="- Order\n+ Purchase\n+ comment"))

    assert comparison.cards[0].row_id == "order"
    assert comparison.raw_evidence[0].patch == "- Order\n+ Purchase\n+ comment"
    assert comparison.unmapped_raw_evidence == ()


def test_raw_evidence_identity_changes_with_patch_bytes_or_artifact_binding() -> None:
    artifact = _domain(EntityRow("order", "Order", ()))
    first = _comparison(artifact, artifact, patches=_patches(domain="one"))
    altered = _comparison(artifact, artifact, patches=_patches(domain="two"))
    rebound = _comparison(artifact, artifact, patches=_patches(constraints="one"))

    assert first.raw_evidence_identity != altered.raw_evidence_identity
    assert first.raw_evidence_identity != rebound.raw_evidence_identity


def test_raw_evidence_identity_is_deterministic_in_inventory_order() -> None:
    artifact = _domain(EntityRow("order", "Order", ()))
    ordered = _comparison(artifact, artifact, patches={"domain": "d", "constraints": "c", "components": "o", "plans": "p"})
    reversed_input = _comparison(artifact, artifact, patches={"plans": "p", "components": "o", "constraints": "c", "domain": "d"})

    assert ordered.raw_evidence_identity == reversed_input.raw_evidence_identity


def _endpoint_ids(row: object) -> set[str]:
    return {
        endpoint_id
        for _kind, endpoint_ids in _row_relation_specs(row)
        for endpoint_id in endpoint_ids
    }


def _relation_field_values(row: object) -> set[str]:
    values: set[str] = set()
    for name in _RELATION_FIELD_NAMES.get(type(row), frozenset()):
        value = getattr(row, name)
        values.update(value) if isinstance(value, tuple) else values.add(value)
    return values


@pytest.mark.parametrize(
    "row",
    (
        BusinessRuleRow("br1", "stmt", entity_ids=("sentinel-entity",)),
        WorkflowRow("wf1", "name", entity_ids=("sentinel-entity",)),
        DecisionRow("d1", "chosen", (), None, "sentinel-anchor", DecisionStatus.PENDING),
        ConstraintRow("c1", "stmt", "attr", anchor_ids=("sentinel-anchor",)),
        ComponentRow(
            "comp1", "name",
            entity_ids=("sentinel-entity",), pattern_ids=("sentinel-pattern",),
            constraint_ids=("sentinel-constraint",), store_ids=("sentinel-store",),
        ),
        PlanRow(
            "p1", "title", PlanDisposition.KEEP, component_ids=("sentinel-component",),
            draft_seed_path="path", sizing_rationale="r",
        ),
        OrderingEntry("plan1", depends_on=("sentinel-dep",), assumption_targets=("sentinel-target",)),
        AssumptionRow("a1", "stmt", consuming_plan_ids=("sentinel-consumer",)),
    ),
)
def test_relation_field_names_matches_declared_relation_specs(row: object) -> None:
    """``_RELATION_FIELD_NAMES`` (used to strip relation fields from displayed
    comparison facts) must name exactly the fields ``_row_relation_specs``
    (the single source of truth for declared relations) actually reads — a
    drift here would double-report a relation change, or silently leak one
    into a comparison card's ``changed_fields``."""
    assert _relation_field_values(row) == _endpoint_ids(row)


def test_relation_field_names_covers_every_stage_row_type() -> None:
    """The parametrized test above checks the *values* it's given for each
    listed row type, but a hand-written list can't notice a whole new
    ``StageRow`` member added to the schema without a matching entry here —
    derive the type set from ``StageRow`` itself so that gap fails closed."""
    covered = set(_RELATION_FIELD_NAMES) | {EntityRow}
    no_relations_instances = {
        AttributeDispositionRow: AttributeDispositionRow("q1", "performance", ConstraintDisposition.PRIORITIZED),
        PatternRow: PatternRow("pat1", "Pattern", "statement"),
        HostingRow: HostingRow("h1", "facet", "value"),
        StoreRow: StoreRow("s1", "category", "sharing"),
        StackRow: StackRow("st1", "platform", choice="managed"),
    }
    for row_type in typing.get_args(StageRow):
        if row_type in covered:
            continue
        assert row_type in no_relations_instances, (
            f"{row_type.__name__} is a new StageRow member with no relation "
            "coverage decision — add it to _RELATION_FIELD_NAMES (with a "
            "parametrize case above) or to no_relations_instances here."
        )
        assert _row_relation_specs(no_relations_instances[row_type]) == ()
