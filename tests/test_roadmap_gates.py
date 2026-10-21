"""Tests for the roadmap response gates.

Plain unit tests: the module drives no orchestrator, touches no disk, and has
no backend seam, so the suite runs under ``conftest.py``'s autouse gate with no
``allow_real_claude`` opt-out.

Fixtures are built by constructing step 1's row dataclasses directly rather
than by parsing text, so a frontmatter-format change cannot redden the gate
suite. ``test_gates_accept_a_parsed_conforming_artifact`` and its revision
sibling are the two deliberate exceptions — they exist to prove the two
modules fit together, on a first run and on a re-run.
"""

from __future__ import annotations

import inspect
import re
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from plan_tool.roadmap_artifacts import (
    AttributeDispositionRow,
    AssumptionRow,
    BusinessRuleRow,
    COMPONENTS_FILENAME,
    CONSTRAINTS_FILENAME,
    ComponentRow,
    ComponentsArtifact,
    ConstraintDisposition,
    ConstraintRow,
    ConstraintsArtifact,
    DOMAIN_FILENAME,
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
    HOSTING_FACETS,
    HostingRow,
    OrderingEntry,
    PLAN_ID_SLUG_RE,
    PLANS_FILENAME,
    PatternRow,
    PlanDisposition,
    PlanRow,
    PlansArtifact,
    STACK_CONCERNS,
    StackRow,
    QUALITY_ATTRIBUTES,
    RejectedAlternative,
    RemovalRecord,
    StoreRow,
    WorkflowRow,
    components_design_rows,
    design_row_collections,
    parse_constraints_artifact,
    parse_domain_artifact,
    parse_components_artifact,
    parse_plans_artifact,
    render_components_artifact,
    render_constraints_artifact,
    plans_design_rows,
    settle_pending_decision,
)
from plan_tool.roadmap_gates import (
    COMPONENTS_GATES,
    CONSTRAINTS_GATES,
    DOMAIN_GATES,
    PLANS_GATES,
    HOSTING_FACET_VALUES,
    ORDERING_REFERENCE_ABSENT,
    ORDERING_REFERENCE_CYCLE,
    ORDERING_REFERENCE_NOT_EARLIER,
    STORE_CATEGORIES,
    STORE_SHARING_MODELS,
    VIOLATION_ALTERED_CARRIED_RESPONSE,
    VIOLATION_ALTERED_FEEDBACK_SOURCE,
    VIOLATION_ALTERED_SETTLED_DECISION,
    VIOLATION_ALTERED_INHERITED_DECISION,
    VIOLATION_BLANK_PLAN_INTENT,
    VIOLATION_BLANK_RATIONALE,
    VIOLATION_BLANK_REMOVAL_RATIONALE,
    VIOLATION_CONSTRAINT_ON_NOT_LOAD_BEARING,
    VIOLATION_DISALLOWED_FEEDBACK_STATE,
    VIOLATION_DRAFT_SEED_PROVENANCE,
    VIOLATION_DUPLICATE_DRAFT_SEED_BASENAME,
    VIOLATION_DROPPED_DESIGN_ROW,
    VIOLATION_DROPPED_FEEDBACK,
    VIOLATION_DROPPED_SETTLED_DECISION,
    VIOLATION_DUPLICATE_INHERITED_DECISION,
    VIOLATION_INHERITED_DECISION_NONLOCAL_ANCHOR,
    VIOLATION_INHERITED_DECISION_AMBIGUOUS_SOURCE,
    VIOLATION_INHERITED_DECISION_UNKNOWN_SOURCE,
    VIOLATION_INHERITED_DECISION_UNCONFIRMED,
    VIOLATION_INHERITED_DECISION_WRONG_ARTIFACT,
    VIOLATION_MISSING_INHERITED_DECISION,
    VIOLATION_DUPLICATE_FEEDBACK_ID,
    VIOLATION_DUPLICATE_FIELD_NAME,
    VIOLATION_DUPLICATE_ROW_ID,
    VIOLATION_EMPTY_ARTIFACT,
    VIOLATION_EMPTY_PATTERN_COLLECTION,
    VIOLATION_ENTITY_WITHOUT_FIELDS,
    VIOLATION_FIELD_REFERENCE_TARGET,
    VIOLATION_HOSTING_TOPOLOGY_COHERENCE,
    VIOLATION_INVALID_PLAN_ID_SLUG,
    VIOLATION_MISSING_HOSTING_FACET,
    VIOLATION_MISSING_DRAFT_SEED_ARTIFACT_REFERENCE,
    VIOLATION_MISSING_DRAFT_SEED_RISKS,
    VIOLATION_MISSING_ORDERING_PLAN_ID,
    VIOLATION_NO_ASSUMPTION_CONSUMER,
    VIOLATION_NO_COMPONENT_REFERENCE,
    VIOLATION_NO_ENTITY_REFERENCE,
    VIOLATION_NO_PLAN_NON_GOALS,
    VIOLATION_NO_PATTERN_REFERENCE,
    VIOLATION_NO_REJECTED_ALTERNATIVE,
    VIOLATION_ORDERING_PLAN_ID_DUPLICATE,
    VIOLATION_REDUNDANT_DISPOSITION,
    VIOLATION_REDUNDANT_HOSTING_FACET,
    VIOLATION_REMOVAL_NAMES_A_PRESENT_ROW,
    VIOLATION_REMOVAL_WITHOUT_A_PREDECESSOR_ROW,
    VIOLATION_UNANCHORED_CONSTRAINT,
    VIOLATION_UNCITED_REMOVAL,
    VIOLATION_UNDEFINED_ASSUMPTION_PLAN_REFERENCE,
    VIOLATION_UNDEFINED_COMPONENT_REFERENCE,
    VIOLATION_UNDEFINED_CONSTRAINT_REFERENCE,
    VIOLATION_UNDEFINED_ENTITY_REFERENCE,
    VIOLATION_UNDEFINED_ORDERING_PLAN_REFERENCE,
    VIOLATION_UNDEFINED_PATTERN_REFERENCE,
    VIOLATION_UNDEFINED_STORE_REFERENCE,
    VIOLATION_UNDEFINED_SEED_COMPONENT_REFERENCE,
    VIOLATION_UNDESCRIBED_ROW,
    VIOLATION_UNDISCHARGED_PRIORITIZED_CONSTRAINT,
    VIOLATION_UNCOVERED_COMPONENT,
    VIOLATION_UNCOVERED_ENTITY,
    VIOLATION_UNCOVERED_STORE,
    VIOLATION_UNDISPOSED_ATTRIBUTE,
    VIOLATION_UNKNOWN_CONSTRAINT_ATTRIBUTE,
    VIOLATION_UNKNOWN_DISPOSED_ATTRIBUTE,
    VIOLATION_UNKNOWN_HOSTING_FACET,
    VIOLATION_UNKNOWN_HOSTING_VALUE,
    VIOLATION_UNKNOWN_STORE_CATEGORY,
    VIOLATION_UNKNOWN_STORE_SHARING,
    VIOLATION_DUPLICATE_STORE_REFERENCE,
    VIOLATION_NO_STORE_REFERENCE,
    VIOLATION_SHARED_IN_PROCESS_STORE,
    VIOLATION_UNREASONED_ALTERNATIVE,
    VIOLATION_UNRESOLVED_CONSTRAINT_ANCHOR,
    VIOLATION_UNRESOLVED_DECISION_ANCHOR,
    VIOLATION_UNRESOLVED_FEEDBACK_TARGET,
    VIOLATION_UNRESOLVED_REMOVAL_CITATION,
    ArtifactEnvelope,
    _envelope_rows,
    _rows_of,
    check_artifact_non_empty,
    check_attribute_totality,
    check_assumption_plan_references,
    check_component_constraint_references,
    check_component_entity_references,
    check_component_pattern_references,
    check_component_plan_coverage,
    check_constraint_anchors,
    check_decision_records,
    check_inherited_decisions,
    check_design_row_continuity,
    check_draft_seed_bundle_alignment,
    check_duplicate_row_ids,
    check_entity_component_coverage,
    check_entity_fields,
    check_entity_references,
    check_feedback_integrity,
    check_hosting_topology_coherence,
    check_hosting_totality,
    check_hosting_value_membership,
    find_duplicate_draft_seed_basenames,
    check_inventory_has_prose,
    check_stack_totality,
    VIOLATION_DUPLICATE_STACK_CONCERN,
    VIOLATION_DUPLICATE_STACK_ID,
    VIOLATION_MISSING_STACK_CONCERN,
    VIOLATION_STACK_ROW_STATE,
    VIOLATION_UNKNOWN_STACK_CONCERN,
    _continuity_rows,
    feedback_target_ids,
    check_plan_component_references,
    check_plan_review_context,
    check_plan_ordering_totality,
    check_prioritized_constraint_discharge,
    check_settled_decisions,
    check_store_coverage,
    check_store_definitions,
    check_store_value_membership,
    HISTORY_MARKER_END,
    HISTORY_MARKER_START,
    NARRATIVE_REMOVED_ID_AMBIGUOUS_REFERENCE,
    NARRATIVE_UNCLOSED_FENCE_UNREAD,
    NARRATIVE_REMOVED_ID_IN_LIVE_PROSE,
    check_removed_ids_in_live_prose,
    design_row_ids,
    run_components_gates,
    run_constraints_gates,
    run_domain_gates,
    run_plans_gates,
    validate_draft_seed_content,
)
from plan_tool.roadmap_source import (
    CarriedDecision,
    CarriedDecisions,
    ConfirmedAnswer,
    RejectedAlternative as CarriedRejectedAlternative,
)
from plan_tool.roadmap_relations import RelationKind
from plan_tool.roadmap_revision import TEXT_FIELDS_BY_ROW_TYPE

MODULE_PATH = Path(__file__).resolve().parents[1] / "plan_tool" / "roadmap_gates.py"

_PLAN_RELATION_GATES = (
    check_plan_review_context,
    check_plan_component_references,
    check_component_plan_coverage,
    check_draft_seed_bundle_alignment,
    check_plan_ordering_totality,
    check_assumption_plan_references,
)

_RELATION_GATE_OWNERS = {
    RelationKind.FIELD_ENTITY: check_entity_references,
    RelationKind.BUSINESS_RULE_ENTITY: check_entity_references,
    RelationKind.WORKFLOW_ENTITY: check_entity_references,
    RelationKind.DECISION_ANCHOR: check_decision_records,
    RelationKind.CONSTRAINT_ANCHOR: check_constraint_anchors,
    RelationKind.COMPONENT_ENTITY: check_component_entity_references,
    RelationKind.COMPONENT_PATTERN: check_component_pattern_references,
    RelationKind.COMPONENT_CONSTRAINT: check_component_constraint_references,
    RelationKind.COMPONENT_STORE: check_store_definitions,
    RelationKind.PLAN_COMPONENT: check_plan_component_references,
    RelationKind.ORDERING_DEPENDS_ON: check_plan_ordering_totality,
    RelationKind.ORDERING_ASSUMPTION_TARGET: check_plan_ordering_totality,
    RelationKind.ASSUMPTION_CONSUMING_PLAN: check_assumption_plan_references,
}


def test_every_declared_relation_kind_has_an_existing_gate_owner() -> None:
    """Keep the extractor's complete relation inventory tied to gate ownership."""
    gate_sets = (DOMAIN_GATES, CONSTRAINTS_GATES, COMPONENTS_GATES, PLANS_GATES)
    available_gates = {gate for gate_set in gate_sets for gate in gate_set}

    assert set(_RELATION_GATE_OWNERS) == set(RelationKind)
    assert set(_RELATION_GATE_OWNERS.values()) <= available_gates


# --------------------------------------------------------------------------
# Fixture builders
# --------------------------------------------------------------------------


def prose_naming(*row_ids: str) -> str:
    """A body that names each id once — the least the prose gate accepts."""
    described = "\n\n".join(f"{row_id} is described here." for row_id in row_ids)
    return f"# Roadmap stage\n\n{described}\n"


ENTITY_ORDER = EntityRow(
    id="entity-1",
    name="Order",
    fields=(
        FieldRow(name="placed_at", type=FieldType.TIMESTAMP),
        FieldRow(name="customer", type=FieldType.REFERENCE, entity_id="entity-2"),
    ),
)
ENTITY_CUSTOMER = EntityRow(
    id="entity-2",
    name="Customer",
    fields=(FieldRow(name="email", type=FieldType.TEXT),),
)
RULE_ONE_CUSTOMER = BusinessRuleRow(
    id="rule-1",
    statement="An order belongs to exactly one customer.",
    entity_ids=("entity-1", "entity-2"),
)
WORKFLOW_PLACE_ORDER = WorkflowRow(id="workflow-1", name="Place an order", entity_ids=("entity-1",))
DOMAIN_DECISION = DecisionRow(
    id="decision-1",
    chosen_option="Keep the cart inside the order aggregate.",
    rejected_alternatives=(
        RejectedAlternative(
            option="A separate cart entity.",
            reason="Two lifecycles to reconcile for no downstream reader.",
        ),
    ),
    rationale="One aggregate keeps checkout atomic.",
    anchor="entity-1",
    status=DecisionStatus.PENDING,
)

# Cycle the three dispositions across the shipped attribute list: the default
# set stays total whatever that list holds, and exercises all three values.
_DISPOSITION_CYCLE = (
    ConstraintDisposition.PRIORITIZED,
    ConstraintDisposition.TRADED_AWAY,
    ConstraintDisposition.NOT_LOAD_BEARING,
)


def disposition_row(attribute: str, index: int) -> AttributeDispositionRow:
    return AttributeDispositionRow(
        id=f"attribute-{attribute}",
        attribute=attribute,
        disposition=_DISPOSITION_CYCLE[index % len(_DISPOSITION_CYCLE)],
    )


ALL_DISPOSITIONS = tuple(
    disposition_row(attribute, index) for index, attribute in enumerate(QUALITY_ATTRIBUTES)
)
PRIORITIZED_ATTRIBUTE = QUALITY_ATTRIBUTES[0]
TRADED_AWAY_ATTRIBUTE = QUALITY_ATTRIBUTES[1]
NOT_LOAD_BEARING_ATTRIBUTE = QUALITY_ATTRIBUTES[2]

CONSTRAINT_LATENCY = ConstraintRow(
    id="constraint-1",
    statement="Checkout completes within 300ms at the median.",
    attribute=PRIORITIZED_ATTRIBUTE,
    anchor_ids=("entity-1", "workflow-1"),
)
CONSTRAINTS_DECISION = DecisionRow(
    id="decision-2",
    chosen_option="Spend replication headroom to keep checkout fast.",
    rejected_alternatives=(
        RejectedAlternative(
            option="Multi-region replication.",
            reason="Adds write latency to the one path that cannot afford it.",
        ),
    ),
    rationale="A slow checkout loses the order outright.",
    anchor=f"attribute-{PRIORITIZED_ATTRIBUTE}",
    status=DecisionStatus.SETTLED,
)
HOSTING_ROWS = (
    HostingRow(id="hosting-compute", facet="compute", value="per-request"),
    HostingRow(id="hosting-model", facet="model", value="pool"),
    HostingRow(id="hosting-topology", facet="topology", value="single-unit"),
)

# A domain decision the reviewer has accepted, so a revision may no longer
# re-decide it.
SETTLED_DOMAIN_DECISION = replace(DOMAIN_DECISION, status=DecisionStatus.SETTLED)

FEEDBACK_REQUEST = "Split the order entity: fulfilment does not belong in it."
FEEDBACK_RESPONSE = "Fulfilment moves to its own entity in the next revision."

ARTIFACT_TARGET = FeedbackTarget(kind=FeedbackTargetKind.ARTIFACT)


def row_target(row_id: str) -> FeedbackTarget:
    return FeedbackTarget(kind=FeedbackTargetKind.ROW, row_id=row_id)


def feedback_row(
    row_id: str = "feedback-1",
    *,
    target: FeedbackTarget = ARTIFACT_TARGET,
    request: str = FEEDBACK_REQUEST,
    state: FeedbackState = FeedbackState.OPEN,
    proposed_response=None,
) -> FeedbackRow:
    """One reviewer redirect, ``open`` unless a state is passed in."""
    return FeedbackRow(
        id=row_id,
        target=target,
        request=request,
        state=state,
        proposed_response=proposed_response,
    )


def answered(row: FeedbackRow, response: str = FEEDBACK_RESPONSE) -> FeedbackRow:
    """``row`` after the one move a revision may make on its own."""
    return replace(row, state=FeedbackState.AWAITING_REVIEW, proposed_response=response)


def removal(
    removed_id: str,
    *,
    rationale="The reviewer asked for this row to go.",
    feedback_ids=("feedback-1",),
) -> RemovalRecord:
    return RemovalRecord(
        removed_id=removed_id,
        rationale=rationale,
        feedback_ids=tuple(feedback_ids),
    )


OPEN_FEEDBACK = feedback_row()


def make_domain(
    *,
    entities=(ENTITY_ORDER, ENTITY_CUSTOMER),
    business_rules=(RULE_ONE_CUSTOMER,),
    workflows=(WORKFLOW_PLACE_ORDER,),
    decisions=(DOMAIN_DECISION,),
    feedback=(),
    removals=(),
    body=None,
) -> DomainArtifact:
    """A domain artifact whose body names every *design* row unless one is
    passed in — feedback and removal rows stay out of the prose inventory."""
    rows = (*entities, *business_rules, *workflows, *decisions)
    return DomainArtifact(
        entities=tuple(entities),
        business_rules=tuple(business_rules),
        workflows=tuple(workflows),
        decisions=tuple(decisions),
        body=prose_naming(*(row.id for row in rows)) if body is None else body,
        feedback=tuple(feedback),
        removals=tuple(removals),
    )


def make_constraints(
    *,
    hosting=HOSTING_ROWS,
    stack=None,
    dispositions=ALL_DISPOSITIONS,
    constraints=(CONSTRAINT_LATENCY,),
    decisions=(CONSTRAINTS_DECISION,),
    feedback=(),
    removals=(),
    body=None,
) -> ConstraintsArtifact:
    rows = (*dispositions, *constraints, *decisions)
    return ConstraintsArtifact(
        dispositions=tuple(dispositions),
        constraints=tuple(constraints),
        decisions=tuple(decisions),
        body=prose_naming(*(row.id for row in rows)) if body is None else body,
        hosting=tuple(hosting),
        stack=None if stack is None else tuple(stack),
        feedback=tuple(feedback),
        removals=tuple(removals),
    )


def domain_envelope(*, predecessor=None, **kwargs) -> ArtifactEnvelope:
    """A domain-stage envelope: ``01-domain.md`` is the artifact under check."""
    return ArtifactEnvelope(domain=make_domain(**kwargs), predecessor=predecessor)


def constraints_envelope(*, domain=None, predecessor=None, **kwargs) -> ArtifactEnvelope:
    """A constraints-stage envelope: the domain is upstream, the constraints
    artifact is under check."""
    return ArtifactEnvelope(
        domain=make_domain() if domain is None else domain,
        constraints=make_constraints(**kwargs),
        predecessor=predecessor,
    )


SYSTEM_PATTERN = PatternRow(
    id="system-pattern-1",
    name="Layered checkout",
    statement="Checkout flows through a dedicated service boundary.",
)
COMPONENT_PATTERN = PatternRow(
    id="component-pattern-1",
    name="Aggregate root",
    statement="Each component owns one consistency boundary.",
)
COMPONENT_ONE = ComponentRow(
    id="component-1",
    name="Order fulfilment",
    entity_ids=("entity-1", "entity-2"),
    pattern_ids=("system-pattern-1", "component-pattern-1"),
    constraint_ids=("constraint-1",),
    store_ids=("store-1",),
)
STORE_ONE = StoreRow(id="store-1", category="relational", sharing="pool")
COMPONENTS_DECISION = DecisionRow(
    id="decision-3",
    chosen_option="Split fulfilment from the order aggregate.",
    rejected_alternatives=(
        RejectedAlternative(
            option="Keep fulfilment inside the order entity.",
            reason="Two lifecycles in one aggregate complicate checkout.",
        ),
    ),
    rationale="Fulfilment scales on a different axis than checkout.",
    anchor="constraint-1",
    status=DecisionStatus.PENDING,
)


def make_components(
    *,
    system_patterns=(SYSTEM_PATTERN,),
    component_patterns=(COMPONENT_PATTERN,),
    stores=(STORE_ONE,),
    components=(COMPONENT_ONE,),
    decisions=(COMPONENTS_DECISION,),
    feedback=(),
    removals=(),
    body=None,
) -> ComponentsArtifact:
    rows = (*system_patterns, *component_patterns, *components, *decisions)
    return ComponentsArtifact(
        system_patterns=tuple(system_patterns),
        component_patterns=tuple(component_patterns),
        components=tuple(components),
        decisions=tuple(decisions),
        body=prose_naming(*(row.id for row in rows)) if body is None else body,
        stores=tuple(stores),
        feedback=tuple(feedback),
        removals=tuple(removals),
    )


def components_envelope(
    *, domain=None, constraints=None, predecessor=None, **kwargs
) -> ArtifactEnvelope:
    """A components-stage envelope: domain and constraints are upstream."""
    return ArtifactEnvelope(
        domain=make_domain() if domain is None else domain,
        constraints=make_constraints() if constraints is None else constraints,
        components=make_components(**kwargs),
        predecessor=predecessor,
    )


PLAN_ONE = PlanRow(
    id="plan-1",
    title="Order fulfilment plan",
    disposition=PlanDisposition.KEEP,
    component_ids=("component-1",),
    draft_seed_path="plan-seeds/order-fulfilment.md",
    sizing_rationale="One component maps to one plan.",
    intent="Make fulfilment independently operable after checkout completes.",
    non_goals=("Changing checkout's order creation flow.",),
)
ASSUMPTION_ONE = AssumptionRow(
    id="assumption-1",
    statement="Checkout completes before fulfilment starts.",
    consuming_plan_ids=("plan-1",),
)
ORDERING_ONE = OrderingEntry(
    plan_id="plan-1",
    depends_on=(),
    assumption_targets=(),
)
PLANS_DECISION = DecisionRow(
    id="decision-4",
    chosen_option="Keep fulfilment as a separate plan.",
    rejected_alternatives=(
        RejectedAlternative(
            option="Merge into checkout.",
            reason="Different scaling axes.",
        ),
    ),
    rationale="Fulfilment scales independently.",
    anchor="plan-1",
    status=DecisionStatus.PENDING,
)


def draft_seed_text(
    component_ids: tuple[str, ...] = (),
    *,
    cross_cutting: bool = False,
) -> str:
    lines = ["---"]
    if component_ids:
        lines.append("roadmap_components:")
        for component_id in component_ids:
            lines.append(f"- {component_id}")
    else:
        lines.append("roadmap_components: []")
    if cross_cutting:
        lines.append("cross_cutting: true")
    lines.extend(
        [
            "---",
            "# Draft seed",
            "",
            "## Risks",
            "",
            "- A risk the accepted roadmap already states.",
            "",
            "## References",
            "",
            f"- `{DOMAIN_FILENAME}`",
            f"- `{CONSTRAINTS_FILENAME}`",
            f"- `{COMPONENTS_FILENAME}`",
            f"- `{PLANS_FILENAME}`",
            "",
        ]
    )
    return "\n".join(lines)


def make_plans(
    *,
    plans=(PLAN_ONE,),
    ordering=(ORDERING_ONE,),
    assumptions=(ASSUMPTION_ONE,),
    decisions=(PLANS_DECISION,),
    feedback=(),
    removals=(),
    body=None,
) -> PlansArtifact:
    design_rows = (*plans, *assumptions, *decisions)
    return PlansArtifact(
        plans=tuple(plans),
        ordering=tuple(ordering),
        assumptions=tuple(assumptions),
        decisions=tuple(decisions),
        body=prose_naming(*(row.id for row in design_rows)) if body is None else body,
        feedback=tuple(feedback),
        removals=tuple(removals),
    )


def plans_envelope(
    *,
    domain=None,
    constraints=None,
    components=None,
    predecessor=None,
    **kwargs,
) -> ArtifactEnvelope:
    """A plans-stage envelope: domain, constraints, and components are upstream."""
    plans = make_plans(**kwargs)
    return ArtifactEnvelope(
        domain=make_domain() if domain is None else domain,
        constraints=make_constraints() if constraints is None else constraints,
        components=make_components() if components is None else components,
        plans=plans,
        predecessor=predecessor,
    )


def kinds(violations) -> list[str]:
    return [violation.kind for violation in violations]


# --------------------------------------------------------------------------
# Components envelope and row helpers
# --------------------------------------------------------------------------


def test_artifact_under_check_returns_components_when_present() -> None:
    envelope = components_envelope()
    assert envelope.artifact_under_check is envelope.components


def test_filename_under_check_returns_components_filename() -> None:
    envelope = components_envelope()
    assert envelope.filename_under_check == COMPONENTS_FILENAME


def test_domain_and_constraints_envelopes_unchanged() -> None:
    domain_only = domain_envelope()
    assert domain_only.artifact_under_check is domain_only.domain
    assert domain_only.filename_under_check == DOMAIN_FILENAME

    constraints_only = constraints_envelope()
    assert constraints_only.artifact_under_check is constraints_only.constraints
    assert constraints_only.filename_under_check == CONSTRAINTS_FILENAME


def test_design_row_ids_includes_component_and_pattern_ids() -> None:
    artifact = make_components()
    ids = design_row_ids(artifact)
    assert ids == {
        "system-pattern-1",
        "component-pattern-1",
        "component-1",
        "decision-3",
    }


def test_envelope_rows_lists_three_artifacts_upstream_first() -> None:
    envelope = components_envelope()
    filenames = [filename for filename, _rows in _envelope_rows(envelope)]
    assert filenames == [DOMAIN_FILENAME, CONSTRAINTS_FILENAME, COMPONENTS_FILENAME]


def test_components_rows_match_step_one_enumerator() -> None:
    artifact = make_components()
    assert _rows_of(artifact) == components_design_rows(artifact)


def test_id_shared_across_components_and_domain_violates() -> None:
    envelope = components_envelope(
        components=(replace(COMPONENT_ONE, id="entity-1"),),
    )
    (violation,) = check_duplicate_row_ids(envelope)
    assert violation.kind == VIOLATION_DUPLICATE_ROW_ID
    assert violation.row_id == "entity-1"
    assert violation.artifact == COMPONENTS_FILENAME


def test_duplicate_store_definition_violates_the_global_id_gate() -> None:
    duplicate = StoreRow(id="store-1", category="document", sharing="silo")
    envelope = components_envelope(stores=(STORE_ONE, duplicate))

    (violation,) = check_duplicate_row_ids(envelope)

    assert violation.kind == VIOLATION_DUPLICATE_ROW_ID
    assert violation.row_id == "store-1"
    assert violation.artifact == COMPONENTS_FILENAME


def test_store_id_colliding_with_a_design_row_violates_the_global_id_gate() -> None:
    colliding = StoreRow(id="component-1", category="document", sharing="pool")
    envelope = components_envelope(
        components=(replace(COMPONENT_ONE, store_ids=(colliding.id,)),),
        stores=(colliding,),
    )

    (violation,) = check_duplicate_row_ids(envelope)

    assert violation.kind == VIOLATION_DUPLICATE_ROW_ID
    assert violation.row_id == colliding.id


def test_store_id_colliding_with_hosting_violates_the_global_id_gate() -> None:
    colliding = StoreRow(id="hosting-compute", category="key-value", sharing="bridge")
    envelope = components_envelope(
        components=(replace(COMPONENT_ONE, store_ids=(colliding.id,)),),
        stores=(colliding,),
    )

    (violation,) = check_duplicate_row_ids(envelope)

    assert violation.kind == VIOLATION_DUPLICATE_ROW_ID
    assert violation.row_id == colliding.id
    assert CONSTRAINTS_FILENAME in violation.message
    assert COMPONENTS_FILENAME in violation.message


def test_decision_anchor_on_components_resolves_upstream_constraint_id() -> None:
    envelope = components_envelope(decisions=(replace(COMPONENTS_DECISION, anchor="constraint-1"),))
    assert check_decision_records(envelope) == []


def test_decision_unresolved_anchor_hint_on_components_names_component_and_pattern_ids() -> None:
    envelope = components_envelope(decisions=(replace(COMPONENTS_DECISION, anchor="missing-id"),))
    (violation,) = check_decision_records(envelope)
    assert violation.kind == VIOLATION_UNRESOLVED_DECISION_ANCHOR
    assert "component" in violation.message
    assert "pattern" in violation.message


def test_artifact_non_empty_requires_component_rows() -> None:
    empty = components_envelope(components=())
    (violation,) = check_artifact_non_empty(empty)
    assert violation.kind == VIOLATION_EMPTY_ARTIFACT
    assert violation.artifact == COMPONENTS_FILENAME
    assert "components" in violation.message
    assert "pattern ids it applies" in violation.message
    assert "discharge" not in violation.message

    populated = components_envelope()
    assert check_artifact_non_empty(populated) == []


def test_artifact_non_empty_still_requires_constraints_on_constraints_stage() -> None:
    envelope = constraints_envelope(dispositions=ALL_DISPOSITIONS, constraints=())
    (violation,) = check_artifact_non_empty(envelope)
    assert violation.kind == VIOLATION_EMPTY_ARTIFACT
    assert violation.artifact == CONSTRAINTS_FILENAME


def test_design_row_continuity_on_components_predecessor() -> None:
    predecessor = make_components()
    envelope = components_envelope(
        components=(),
        predecessor=predecessor,
    )
    (violation,) = check_design_row_continuity(envelope)
    assert violation.kind == VIOLATION_DROPPED_DESIGN_ROW
    assert violation.row_id == "component-1"
    assert violation.artifact == COMPONENTS_FILENAME


def test_feedback_integrity_on_components_envelope() -> None:
    asked = feedback_row()
    envelope = components_envelope(
        feedback=(answered(asked),),
        predecessor=make_components(feedback=(asked,)),
    )
    assert check_feedback_integrity(envelope) == []


# --------------------------------------------------------------------------
# Plans envelope and row helpers
# --------------------------------------------------------------------------


def test_artifact_under_check_returns_plans_when_present() -> None:
    envelope = plans_envelope()
    assert envelope.artifact_under_check is envelope.plans
    assert envelope.artifact_under_check is not envelope.components


def test_filename_under_check_returns_plans_filename() -> None:
    envelope = plans_envelope()
    assert envelope.filename_under_check == PLANS_FILENAME


def test_domain_constraints_and_components_envelopes_unchanged() -> None:
    domain_only = domain_envelope()
    assert domain_only.artifact_under_check is domain_only.domain
    assert domain_only.filename_under_check == DOMAIN_FILENAME

    constraints_only = constraints_envelope()
    assert constraints_only.artifact_under_check is constraints_only.constraints
    assert constraints_only.filename_under_check == CONSTRAINTS_FILENAME

    components_only = components_envelope()
    assert components_only.artifact_under_check is components_only.components
    assert components_only.filename_under_check == COMPONENTS_FILENAME


def test_design_row_ids_includes_plan_assumption_and_decision_ids() -> None:
    artifact = make_plans()
    ids = design_row_ids(artifact)
    assert ids == {"plan-1", "assumption-1", "decision-4"}
    # Ordering references plan ids but mints none — row count matches inventories only.
    assert len(_rows_of(artifact)) == (
        len(artifact.plans) + len(artifact.assumptions) + len(artifact.decisions)
    )


def test_envelope_rows_lists_four_artifacts_upstream_first() -> None:
    envelope = plans_envelope()
    filenames = [filename for filename, _rows in _envelope_rows(envelope)]
    assert filenames == [
        DOMAIN_FILENAME,
        CONSTRAINTS_FILENAME,
        COMPONENTS_FILENAME,
        PLANS_FILENAME,
    ]


def test_plans_rows_match_step_one_enumerator() -> None:
    artifact = make_plans()
    assert _rows_of(artifact) == plans_design_rows(artifact)


def test_ordering_entries_absent_from_plans_design_rows() -> None:
    """Ordering references plan ids but contributes no design rows of its own."""
    plan_two = replace(PLAN_ONE, id="plan-2", title="Checkout plan")
    artifact = make_plans(
        plans=(PLAN_ONE, plan_two),
        ordering=(
            ORDERING_ONE,
            OrderingEntry(plan_id="plan-2", depends_on=("plan-1",)),
        ),
    )
    rows = plans_design_rows(artifact)
    assert len(rows) == 4
    assert {row_id for _label, row_id in rows} == {
        "plan-1",
        "plan-2",
        "assumption-1",
        "decision-4",
    }
    assert all(label in ("plan", "assumption", "decision") for label, _ in rows)


def test_id_shared_across_plans_and_components_violates() -> None:
    envelope = plans_envelope(
        components=make_components(
            components=(replace(COMPONENT_ONE, id="plan-1"),),
        ),
    )
    (violation,) = check_duplicate_row_ids(envelope)
    assert violation.kind == VIOLATION_DUPLICATE_ROW_ID
    assert violation.row_id == "plan-1"
    assert violation.artifact == PLANS_FILENAME


def test_decision_anchor_on_plans_resolves_plan_id() -> None:
    envelope = plans_envelope(decisions=(replace(PLANS_DECISION, anchor="plan-1"),))
    assert check_decision_records(envelope) == []


def test_decision_unresolved_anchor_hint_on_plans_names_plan_and_assumption_ids() -> None:
    envelope = plans_envelope(decisions=(replace(PLANS_DECISION, anchor="missing-id"),))
    (violation,) = check_decision_records(envelope)
    assert violation.kind == VIOLATION_UNRESOLVED_DECISION_ANCHOR
    assert "plan" in violation.message
    assert "assumption" in violation.message


def test_artifact_non_empty_requires_plan_rows() -> None:
    empty = plans_envelope(plans=())
    (violation,) = check_artifact_non_empty(empty)
    assert violation.kind == VIOLATION_EMPTY_ARTIFACT
    assert violation.artifact == PLANS_FILENAME
    assert "plans" in violation.message

    populated = plans_envelope()
    assert check_artifact_non_empty(populated) == []


def test_artifact_non_empty_still_requires_components_on_components_stage() -> None:
    envelope = components_envelope(
        system_patterns=(SYSTEM_PATTERN,),
        component_patterns=(COMPONENT_PATTERN,),
        components=(),
    )
    (violation,) = check_artifact_non_empty(envelope)
    assert violation.kind == VIOLATION_EMPTY_ARTIFACT
    assert violation.artifact == COMPONENTS_FILENAME


def test_design_row_continuity_on_plans_predecessor() -> None:
    predecessor = make_plans()
    envelope = plans_envelope(
        assumptions=(),
        predecessor=predecessor,
    )
    (violation,) = check_design_row_continuity(envelope)
    assert violation.kind == VIOLATION_DROPPED_DESIGN_ROW
    assert violation.row_id == "assumption-1"
    assert violation.artifact == PLANS_FILENAME


def test_feedback_integrity_on_plans_envelope() -> None:
    asked = feedback_row()
    envelope = plans_envelope(
        feedback=(answered(asked),),
        predecessor=make_plans(feedback=(asked,)),
    )
    assert check_feedback_integrity(envelope) == []


def test_predecessor_feedback_preflight_resolves_plan_id() -> None:
    artifact = make_plans()
    assert "plan-1" in design_row_ids(artifact)


# --------------------------------------------------------------------------
# Plans relation gates
# --------------------------------------------------------------------------


def test_run_plans_gates_clears_a_conforming_envelope() -> None:
    assert run_plans_gates(plans_envelope()) == []


def test_plans_gates_tuple_includes_relation_gates_in_order() -> None:
    start = PLANS_GATES.index(check_plan_review_context)
    end = PLANS_GATES.index(check_assumption_plan_references)
    assert PLANS_GATES[start : end + 1] == _PLAN_RELATION_GATES


def test_plan_relation_gates_are_inert_off_plans_stage() -> None:
    for gate in _PLAN_RELATION_GATES:
        assert gate(components_envelope()) == []
        assert gate(constraints_envelope()) == []


def test_plan_with_defined_component_ids_passes() -> None:
    assert check_plan_component_references(plans_envelope()) == []


def test_plan_review_context_requires_an_intent_and_non_goals() -> None:
    envelope = plans_envelope(
        plans=(replace(PLAN_ONE, intent="   ", non_goals=()),),
    )

    violations = check_plan_review_context(envelope)

    assert [violation.kind for violation in violations] == [
        VIOLATION_BLANK_PLAN_INTENT,
        VIOLATION_NO_PLAN_NON_GOALS,
    ]
    assert {violation.row_id for violation in violations} == {"plan-1"}


def test_plan_review_context_accepts_authored_outcome_and_boundaries() -> None:
    assert check_plan_review_context(plans_envelope()) == []


def test_plan_with_empty_component_ids_violates() -> None:
    envelope = plans_envelope(
        plans=(replace(PLAN_ONE, component_ids=()),),
    )
    (violation,) = check_plan_component_references(envelope)
    assert violation.kind == VIOLATION_NO_COMPONENT_REFERENCE
    assert violation.row_id == "plan-1"


def test_plan_referencing_undefined_component_violates() -> None:
    envelope = plans_envelope(
        plans=(replace(PLAN_ONE, component_ids=("component-9",)),),
    )
    (violation,) = check_plan_component_references(envelope)
    assert violation.kind == VIOLATION_UNDEFINED_COMPONENT_REFERENCE
    assert "component-9" in violation.message


def test_every_undefined_component_reference_on_plans_is_reported() -> None:
    envelope = plans_envelope(
        plans=(replace(PLAN_ONE, component_ids=("component-8", "component-9")),),
    )
    violations = check_plan_component_references(envelope)
    assert len(violations) == 2
    assert {violation.kind for violation in violations} == {VIOLATION_UNDEFINED_COMPONENT_REFERENCE}


def test_cross_cutting_plan_may_omit_component_ids() -> None:
    envelope = plans_envelope(
        plans=(
            replace(
                PLAN_ONE,
                disposition=PlanDisposition.CROSS_CUTTING,
                component_ids=(),
            ),
        ),
    )
    assert check_plan_component_references(envelope) == []


def test_cross_cutting_plan_with_undefined_component_violates() -> None:
    envelope = plans_envelope(
        plans=(
            replace(
                PLAN_ONE,
                disposition=PlanDisposition.CROSS_CUTTING,
                component_ids=("component-9",),
            ),
        ),
    )
    (violation,) = check_plan_component_references(envelope)
    assert violation.kind == VIOLATION_UNDEFINED_COMPONENT_REFERENCE


def test_component_covered_by_plan_passes() -> None:
    assert check_component_plan_coverage(plans_envelope()) == []


def test_uncovered_component_violates() -> None:
    envelope = plans_envelope(plans=(replace(PLAN_ONE, component_ids=()),))
    (violation,) = check_component_plan_coverage(envelope)
    assert violation.kind == VIOLATION_UNCOVERED_COMPONENT
    assert violation.row_id is None
    assert "component-1" in violation.message
    assert violation.artifact == COMPONENTS_FILENAME


def test_cross_cutting_plan_does_not_cover_component() -> None:
    envelope = plans_envelope(
        plans=(
            replace(
                PLAN_ONE,
                disposition=PlanDisposition.CROSS_CUTTING,
                component_ids=(),
            ),
        ),
    )
    (violation,) = check_component_plan_coverage(envelope)
    assert violation.kind == VIOLATION_UNCOVERED_COMPONENT
    assert "component-1" in violation.message


def test_validate_draft_seed_content_accepts_matching_components() -> None:
    assert validate_draft_seed_content(draft_seed_text(PLAN_ONE.component_ids), plan=PLAN_ONE) == []


def test_validate_draft_seed_content_accepts_complete_body_references() -> None:
    assert validate_draft_seed_content(draft_seed_text(), plan=PLAN_ONE) == []


def test_draft_seed_unmatched_opening_fence_is_a_materialization_violation() -> None:
    (violation,) = validate_draft_seed_content(
        draft_seed_text() + "\n```\n", plan=PLAN_ONE
    )
    assert violation.kind == "draft-seed-unmatched-fence"
    assert PLAN_ONE.id in violation.message


def test_validate_draft_seed_content_accepts_crlf_body_references() -> None:
    assert (
        validate_draft_seed_content(draft_seed_text().replace("\n", "\r\n"), plan=PLAN_ONE)
        == []
    )


@pytest.mark.parametrize(
    "missing_filename",
    (DOMAIN_FILENAME, CONSTRAINTS_FILENAME, COMPONENTS_FILENAME, PLANS_FILENAME),
)
def test_validate_draft_seed_content_reports_each_missing_accepted_artifact_reference(
    missing_filename: str,
) -> None:
    text = draft_seed_text().replace(f"- `{missing_filename}`\n", "")

    (violation,) = validate_draft_seed_content(text, plan=PLAN_ONE)

    assert violation.kind == VIOLATION_MISSING_DRAFT_SEED_ARTIFACT_REFERENCE
    assert missing_filename in violation.message
    assert PLAN_ONE.id in violation.message
    assert Path(PLAN_ONE.draft_seed_path).name in violation.message
    assert "References" in violation.message


def test_validate_draft_seed_content_does_not_count_frontmatter_or_non_references_mentions() -> None:
    text = """---
roadmap_components:
- component-1
sources:
- 01-domain.md
- 02-constraints.md
- 03-components.md
- 04-roadmap.md
---
# Draft seed

## Risks

- A risk the accepted roadmap already states.

## Context

01-domain.md 02-constraints.md 03-components.md 04-roadmap.md
"""

    violations = validate_draft_seed_content(text, plan=PLAN_ONE)
    accepted_filenames = (
        DOMAIN_FILENAME,
        CONSTRAINTS_FILENAME,
        COMPONENTS_FILENAME,
        PLANS_FILENAME,
    )

    assert [violation.kind for violation in violations] == [
        VIOLATION_MISSING_DRAFT_SEED_ARTIFACT_REFERENCE,
    ] * 4
    assert [
        next(filename for filename in accepted_filenames if filename in violation.message)
        for violation in violations
    ] == list(accepted_filenames)


def _risks_violations(text: str) -> list:
    return [
        violation
        for violation in validate_draft_seed_content(text, plan=PLAN_ONE)
        if violation.kind == VIOLATION_MISSING_DRAFT_SEED_RISKS
    ]


def test_draft_seed_without_a_risks_section_is_refused_naming_the_remedy() -> None:
    text = draft_seed_text().replace(
        "## Risks\n\n- A risk the accepted roadmap already states.\n\n", ""
    )

    (violation,) = _risks_violations(text)

    assert violation.row_id == PLAN_ONE.id
    assert "## Risks" in violation.message
    assert "Stop / defer" in violation.message


def test_draft_seed_with_an_empty_risks_section_is_refused() -> None:
    text = draft_seed_text().replace("- A risk the accepted roadmap already states.\n", "")

    assert len(_risks_violations(text)) == 1


def test_draft_seed_risks_inside_a_fence_does_not_count() -> None:
    # Deliberately: a fenced example is not the section. Presence is the only
    # observable; what a risk says is a semantic property this gate never judges.
    text = draft_seed_text().replace(
        "## Risks\n\n- A risk the accepted roadmap already states.\n",
        "## Risks\n\n```\n- fenced only\n```\n",
    )

    assert len(_risks_violations(text)) == 1


def test_draft_seed_with_a_todo_placeholder_risks_section_is_refused() -> None:
    # The repo's existing placeholder vocabulary (`_(TODO)_`, `TODO`), reused
    # from scope_fence rather than a second list. `TBD`/`None.` are real
    # statements and pass (next test).
    text = draft_seed_text().replace(
        "- A risk the accepted roadmap already states.", "_(TODO)_"
    )

    assert len(_risks_violations(text)) == 1


def test_draft_seed_with_any_nonempty_risks_text_passes() -> None:
    # Deliberately not judged: the content. `create` refuses unsourced risks.
    text = draft_seed_text().replace("A risk the accepted roadmap already states.", "None.")

    assert _risks_violations(text) == []


def test_validate_draft_seed_content_does_not_count_fenced_references() -> None:
    text = """---
roadmap_components:
- component-1
---
# Draft seed

## Risks

- A risk the accepted roadmap already states.

```markdown
## References
- 01-domain.md
- 02-constraints.md
- 03-components.md
- 04-roadmap.md
```
"""

    violations = validate_draft_seed_content(text, plan=PLAN_ONE)

    assert [violation.kind for violation in violations] == [
        VIOLATION_MISSING_DRAFT_SEED_ARTIFACT_REFERENCE,
    ] * 4


def test_validate_draft_seed_content_does_not_count_fenced_content_inside_a_real_references_section() -> (
    None
):
    """A real, unfenced ``## References`` heading whose only body content is
    a fenced example that happens to mention the filenames must not satisfy
    the gate — only fenced *headings* being ignored is not enough; fenced
    *content* inside a real section must not count as a reference either."""
    text = """---
roadmap_components:
- component-1
---
# Draft seed

## Risks

- A risk the accepted roadmap already states.

## References

Example, not a real reference list:
```
cat 01-domain.md
cat 02-constraints.md
cat 03-components.md
cat 04-roadmap.md
```
"""

    violations = validate_draft_seed_content(text, plan=PLAN_ONE)

    assert [violation.kind for violation in violations] == [
        VIOLATION_MISSING_DRAFT_SEED_ARTIFACT_REFERENCE,
    ] * 4


def test_validate_draft_seed_content_rejects_unparseable_provenance() -> None:
    (violation,) = validate_draft_seed_content("---\n---\n# Seed\n", plan=PLAN_ONE)

    assert violation.kind == VIOLATION_DRAFT_SEED_PROVENANCE
    assert violation.row_id == PLAN_ONE.id


def test_validate_draft_seed_content_rejects_component_not_on_plan_row() -> None:
    (violation,) = validate_draft_seed_content(draft_seed_text(("component-9",)), plan=PLAN_ONE)

    assert violation.kind == VIOLATION_UNDEFINED_SEED_COMPONENT_REFERENCE
    assert violation.row_id == PLAN_ONE.id
    assert "component-9" in violation.message


def test_validate_draft_seed_content_allows_cross_cutting_flag() -> None:
    cross_cutting_plan = replace(
        PLAN_ONE,
        disposition=PlanDisposition.CROSS_CUTTING,
        component_ids=(),
    )

    assert (
        validate_draft_seed_content(draft_seed_text(cross_cutting=True), plan=cross_cutting_plan)
        == []
    )


def test_plan_row_draft_seed_basenames_are_unique() -> None:
    assert check_draft_seed_bundle_alignment(plans_envelope()) == []


def test_duplicate_draft_seed_basename_across_plan_rows_violates() -> None:
    plan_two = replace(PLAN_ONE, id="plan-2", title="Second plan")
    envelope = plans_envelope(
        plans=(PLAN_ONE, plan_two),
        ordering=(
            ORDERING_ONE,
            OrderingEntry(plan_id="plan-2"),
        ),
    )
    violations = check_draft_seed_bundle_alignment(envelope)
    assert len(violations) == 2
    assert all(
        violation.kind == VIOLATION_DUPLICATE_DRAFT_SEED_BASENAME for violation in violations
    )


def test_find_duplicate_draft_seed_basenames_flags_shared_basename() -> None:
    plans = (
        replace(PLAN_ONE, draft_seed_path="plan-seed-drafts/order-core.md"),
        replace(
            PLAN_ONE,
            id="plan-2",
            title="Second plan",
            draft_seed_path="plan-seed-drafts/order-core.md",
        ),
    )

    violations = find_duplicate_draft_seed_basenames(plans)

    assert [violation.kind for violation in violations] == [
        VIOLATION_DUPLICATE_DRAFT_SEED_BASENAME,
        VIOLATION_DUPLICATE_DRAFT_SEED_BASENAME,
    ]
    assert [violation.row_id for violation in violations] == ["plan-1", "plan-2"]


def test_find_duplicate_draft_seed_basenames_names_the_other_row_when_ids_also_collide() -> None:
    plans = (
        replace(PLAN_ONE, draft_seed_path="plan-seed-drafts/order-core.md"),
        replace(PLAN_ONE, draft_seed_path="plan-seed-drafts/order-core.md"),
    )

    violations = find_duplicate_draft_seed_basenames(plans)

    assert len(violations) == 2
    for violation in violations:
        assert "1 other plan row(s) (plan-1)" in violation.message


def test_find_duplicate_draft_seed_basenames_allows_distinct_prefixes() -> None:
    plans = (
        replace(PLAN_ONE, draft_seed_path="seeds/order-core.md"),
        replace(
            PLAN_ONE,
            id="plan-2",
            title="Second plan",
            draft_seed_path="plan-seed-drafts/order-core.md",
        ),
    )

    assert find_duplicate_draft_seed_basenames(plans) == []


def test_find_duplicate_draft_seed_basenames_is_empty_for_unique_paths() -> None:
    plans = (
        replace(PLAN_ONE, draft_seed_path="plan-seed-drafts/order-core.md"),
        replace(
            PLAN_ONE,
            id="plan-2",
            title="Second plan",
            draft_seed_path="plan-seed-drafts/second-plan.md",
        ),
    )

    assert find_duplicate_draft_seed_basenames(plans) == []


def test_ordering_lists_every_plan_id_once_passes() -> None:
    assert check_plan_ordering_totality(plans_envelope()) == []


def test_ordering_missing_plan_id_violates() -> None:
    plan_two = replace(PLAN_ONE, id="plan-2", title="Second plan")
    envelope = plans_envelope(
        plans=(PLAN_ONE, plan_two),
        ordering=(ORDERING_ONE,),
    )
    (violation,) = check_plan_ordering_totality(envelope)
    assert violation.kind == VIOLATION_MISSING_ORDERING_PLAN_ID
    assert violation.row_id == "plan-2"


def test_ordering_unknown_plan_id_entry_violates() -> None:
    envelope = plans_envelope(
        ordering=(OrderingEntry(plan_id="plan-9"),),
    )
    violations = [
        violation
        for violation in check_plan_ordering_totality(envelope)
        if violation.kind == VIOLATION_UNDEFINED_ORDERING_PLAN_REFERENCE
        and violation.row_id == "plan-9"
    ]
    assert len(violations) == 1


def test_ordering_duplicate_plan_id_reported_once() -> None:
    envelope = plans_envelope(
        ordering=(ORDERING_ONE, ORDERING_ONE),
    )
    violations = [
        violation
        for violation in check_plan_ordering_totality(envelope)
        if violation.kind == VIOLATION_ORDERING_PLAN_ID_DUPLICATE
    ]
    assert len(violations) == 1
    assert violations[0].row_id == "plan-1"


def test_ordering_depends_on_unknown_plan_violates() -> None:
    envelope = plans_envelope(
        ordering=(OrderingEntry(plan_id="plan-1", depends_on=("plan-9",)),),
    )
    (violation,) = [
        violation
        for violation in check_plan_ordering_totality(envelope)
        if "depends_on" in violation.message
    ]
    assert violation.kind == VIOLATION_UNDEFINED_ORDERING_PLAN_REFERENCE


def test_ordering_assumption_target_unknown_plan_violates() -> None:
    envelope = plans_envelope(
        ordering=(OrderingEntry(plan_id="plan-1", assumption_targets=("plan-9",)),),
    )
    (violation,) = [
        violation
        for violation in check_plan_ordering_totality(envelope)
        if "assumption_targets" in violation.message
    ]
    assert violation.kind == VIOLATION_UNDEFINED_ORDERING_PLAN_REFERENCE


def test_ordering_depends_on_must_appear_earlier_in_sequence() -> None:
    plan_two = replace(PLAN_ONE, id="plan-2", title="Second plan")
    envelope = plans_envelope(
        plans=(PLAN_ONE, plan_two),
        ordering=(
            OrderingEntry(plan_id="plan-1", depends_on=("plan-2",)),
            OrderingEntry(plan_id="plan-2"),
        ),
    )
    (violation,) = [
        violation
        for violation in check_plan_ordering_totality(envelope)
        if "earlier" in violation.message and "depends_on" in violation.message
    ]
    assert violation.kind == VIOLATION_UNDEFINED_ORDERING_PLAN_REFERENCE
    assert violation.row_id == "plan-1"


@pytest.mark.parametrize(
    ("ordering", "expected"),
    (
        pytest.param(
            (ORDERING_ONE, OrderingEntry(plan_id="plan-9")),
            ("plan-9", "plan-9", ORDERING_REFERENCE_ABSENT),
            id="entry-names-no-plan-row",
        ),
        pytest.param(
            (OrderingEntry(plan_id="plan-1", depends_on=("plan-9",)), OrderingEntry(plan_id="plan-2")),
            ("plan-1", "plan-9", ORDERING_REFERENCE_ABSENT),
            id="depends-on-absent",
        ),
        pytest.param(
            (OrderingEntry(plan_id="plan-1", assumption_targets=("plan-9",)), OrderingEntry(plan_id="plan-2")),
            ("plan-1", "plan-9", ORDERING_REFERENCE_ABSENT),
            id="assumption-target-absent",
        ),
        pytest.param(
            (OrderingEntry(plan_id="plan-1", depends_on=("plan-2",)), OrderingEntry(plan_id="plan-2")),
            ("plan-1", "plan-2", ORDERING_REFERENCE_NOT_EARLIER),
            id="depends-on-not-earlier",
        ),
        pytest.param(
            (OrderingEntry(plan_id="plan-1", assumption_targets=("plan-2",)), OrderingEntry(plan_id="plan-2")),
            ("plan-1", "plan-2", ORDERING_REFERENCE_NOT_EARLIER),
            id="assumption-target-not-earlier",
        ),
        pytest.param(
            (OrderingEntry(plan_id="plan-1", depends_on=("plan-2",)), OrderingEntry(plan_id="plan-2", depends_on=("plan-1",))),
            ("plan-1", "plan-2", ORDERING_REFERENCE_CYCLE),
            id="depends-on-cycle",
        ),
        pytest.param(
            (
                OrderingEntry(plan_id="plan-1", assumption_targets=("plan-2",)),
                OrderingEntry(plan_id="plan-2", depends_on=("plan-1",)),
            ),
            ("plan-1", "plan-2", ORDERING_REFERENCE_CYCLE),
            id="assumption-target-cycle",
        ),
        pytest.param(
            (
                OrderingEntry(plan_id="plan-1", depends_on=("plan-2",)),
                OrderingEntry(plan_id="plan-2", assumption_targets=("plan-1",)),
            ),
            ("plan-1", "plan-2", ORDERING_REFERENCE_CYCLE),
            id="cycle-closed-by-an-assumption-target-edge",
        ),
    ),
)
def test_ordering_reference_violation_carries_its_target_and_closed_defect(
    ordering: tuple[OrderingEntry, ...], expected: tuple[str, str, str]
) -> None:
    # Candidate retries may not echo ``message``; these fields are what tells the cases apart.
    plan_two = replace(PLAN_ONE, id="plan-2", title="Second plan")
    envelope = plans_envelope(plans=(PLAN_ONE, plan_two), ordering=ordering)

    (violation,) = [
        violation
        for violation in check_plan_ordering_totality(envelope)
        if violation.kind == VIOLATION_UNDEFINED_ORDERING_PLAN_REFERENCE
    ]

    assert (violation.row_id, violation.referenced_id, violation.reference_defect) == expected


@pytest.mark.parametrize("field", ("depends_on", "assumption_targets"))
def test_ordering_reference_to_a_plan_with_no_ordering_entry_reports_the_missing_slot_not_a_crash(
    field: str,
) -> None:
    # plan-1 is a defined plan but has no ordering entry; plan-2 cites it. The gate must
    # report the missing slot once rather than look up a position that does not exist.
    plan_two = replace(PLAN_ONE, id="plan-2", title="Second plan")
    envelope = plans_envelope(
        plans=(PLAN_ONE, plan_two),
        ordering=(OrderingEntry(plan_id="plan-2", **{field: ("plan-1",)}),),
    )

    violations = check_plan_ordering_totality(envelope)

    assert [(violation.kind, violation.row_id) for violation in violations] == [
        (VIOLATION_MISSING_ORDERING_PLAN_ID, "plan-1")
    ]


def test_ordering_cycle_message_tells_the_model_to_drop_a_reference_not_to_move_one() -> None:
    # Stage retries feed Violation.message back as their correction. No order satisfies a
    # cycle, so "move X above Y" would only shift the violation onto the other reference.
    plan_two = replace(PLAN_ONE, id="plan-2", title="Second plan")
    cyclic = plans_envelope(
        plans=(PLAN_ONE, plan_two),
        ordering=(
            OrderingEntry(plan_id="plan-1", depends_on=("plan-2",)),
            OrderingEntry(plan_id="plan-2", depends_on=("plan-1",)),
        ),
    )
    forward = plans_envelope(
        plans=(PLAN_ONE, plan_two),
        ordering=(OrderingEntry(plan_id="plan-1", depends_on=("plan-2",)), OrderingEntry(plan_id="plan-2")),
    )

    (cycle_violation,) = check_plan_ordering_totality(cyclic)
    (forward_violation,) = check_plan_ordering_totality(forward)

    assert cycle_violation.reference_defect == ORDERING_REFERENCE_CYCLE
    assert "move" not in cycle_violation.message
    assert "drop this dependency, or another reference on the same cycle" in cycle_violation.message
    assert forward_violation.reference_defect == ORDERING_REFERENCE_NOT_EARLIER
    assert "move 'plan-2' above 'plan-1'" in forward_violation.message


def test_plan_id_must_match_slug_re() -> None:
    envelope = plans_envelope(
        plans=(replace(PLAN_ONE, id="Plan_One"),),
        ordering=(OrderingEntry(plan_id="Plan_One"),),
    )
    (violation,) = [
        violation
        for violation in check_plan_ordering_totality(envelope)
        if violation.kind == VIOLATION_INVALID_PLAN_ID_SLUG
    ]
    assert violation.row_id == "Plan_One"


def test_valid_slug_plan_id_passes_slug_check() -> None:
    envelope = plans_envelope(
        plans=(
            replace(
                PLAN_ONE,
                id="order-core",
                draft_seed_path="plan-seeds/order-core-plan.md",
            ),
        ),
        ordering=(OrderingEntry(plan_id="order-core"),),
    )
    violations = [
        violation
        for violation in check_plan_ordering_totality(envelope)
        if violation.kind == VIOLATION_INVALID_PLAN_ID_SLUG
    ]
    assert violations == []
    assert PLAN_ID_SLUG_RE.fullmatch("order-core")


def test_assumption_consuming_defined_plan_passes() -> None:
    assert check_assumption_plan_references(plans_envelope()) == []


def test_assumption_with_empty_consumers_violates() -> None:
    envelope = plans_envelope(
        assumptions=(replace(ASSUMPTION_ONE, consuming_plan_ids=()),),
    )
    (violation,) = check_assumption_plan_references(envelope)
    assert violation.kind == VIOLATION_NO_ASSUMPTION_CONSUMER
    assert violation.row_id == "assumption-1"
    assert "consuming" in violation.message


def test_assumption_consuming_unknown_plan_violates() -> None:
    envelope = plans_envelope(
        assumptions=(replace(ASSUMPTION_ONE, consuming_plan_ids=("plan-9",)),),
    )
    (violation,) = check_assumption_plan_references(envelope)
    assert violation.kind == VIOLATION_UNDEFINED_ASSUMPTION_PLAN_REFERENCE
    assert violation.row_id == "assumption-1"
    assert "plan-9" in violation.message


def test_duplicate_plan_and_component_id_violates() -> None:
    envelope = plans_envelope(
        components=make_components(
            components=(replace(COMPONENT_ONE, id="plan-1"),),
        ),
    )
    (violation,) = check_duplicate_row_ids(envelope)
    assert violation.kind == VIOLATION_DUPLICATE_ROW_ID
    assert violation.row_id == "plan-1"


def test_inventory_has_prose_on_plans_artifact() -> None:
    envelope = plans_envelope(body="# Roadmap stage\n\nNo ids named here.\n")
    violations = check_inventory_has_prose(envelope)
    assert violations
    assert all(violation.kind == VIOLATION_UNDESCRIBED_ROW for violation in violations)
    assert violations[0].artifact == PLANS_FILENAME


# --------------------------------------------------------------------------
# Components traceability gates
# --------------------------------------------------------------------------


def test_component_referencing_defined_entities_passes() -> None:
    assert check_component_entity_references(components_envelope()) == []


def test_component_with_empty_entity_ids_violates() -> None:
    envelope = components_envelope(components=(replace(COMPONENT_ONE, entity_ids=()),))
    (violation,) = check_component_entity_references(envelope)
    assert violation.kind == VIOLATION_NO_ENTITY_REFERENCE
    assert violation.row_id == "component-1"
    assert violation.artifact == COMPONENTS_FILENAME


def test_component_referencing_undefined_entity_violates() -> None:
    envelope = components_envelope(components=(replace(COMPONENT_ONE, entity_ids=("entity-9",)),))
    (violation,) = check_component_entity_references(envelope)
    assert violation.kind == VIOLATION_UNDEFINED_ENTITY_REFERENCE
    assert "entity-9" in violation.message
    assert DOMAIN_FILENAME in violation.message


def test_every_undefined_entity_reference_on_components_is_reported() -> None:
    envelope = components_envelope(
        components=(replace(COMPONENT_ONE, entity_ids=("entity-8", "entity-9")),)
    )
    violations = check_component_entity_references(envelope)
    assert kinds(violations) == [VIOLATION_UNDEFINED_ENTITY_REFERENCE] * 2
    assert [("entity-8" in v.message, "entity-9" in v.message) for v in violations] == [
        (True, False),
        (False, True),
    ]


def test_full_entity_coverage_passes() -> None:
    assert check_entity_component_coverage(components_envelope()) == []


def test_orphan_entity_violates() -> None:
    envelope = components_envelope(components=(replace(COMPONENT_ONE, entity_ids=("entity-1",)),))
    (violation,) = check_entity_component_coverage(envelope)
    assert violation.kind == VIOLATION_UNCOVERED_ENTITY
    assert violation.row_id is None
    assert "entity-2" in violation.message
    assert DOMAIN_FILENAME in violation.message


def test_every_orphan_entity_is_reported() -> None:
    entity_three = EntityRow(
        id="entity-3",
        name="Cart",
        fields=(FieldRow(name="items", type=FieldType.TEXT),),
    )
    envelope = components_envelope(
        domain=make_domain(entities=(ENTITY_ORDER, ENTITY_CUSTOMER, entity_three)),
        components=(replace(COMPONENT_ONE, entity_ids=("entity-1",)),),
    )
    violations = check_entity_component_coverage(envelope)
    assert kinds(violations) == [VIOLATION_UNCOVERED_ENTITY] * 2
    assert {"entity-2", "entity-3"} == {v.message.split("'")[1] for v in violations}


def test_two_components_may_own_the_same_entity_id() -> None:
    """Ownership is **coverage, not exclusivity** — the deliberate carve-out.

    Nothing in the shipped gate set forbids a shared entity id, and the prompt
    tells the model an entity belongs to "at least one" component. Pinned here
    because a rule this easy to tighten into a partition check would otherwise
    widen with the whole suite still green.
    """
    shared = replace(COMPONENT_ONE, entity_ids=("entity-1", "entity-2"))
    second = ComponentRow(
        id="component-2",
        name="Billing",
        entity_ids=("entity-2",),
        pattern_ids=("system-pattern-1",),
        constraint_ids=(),
        store_ids=("store-1",),
    )
    envelope = components_envelope(components=(shared, second))

    assert check_entity_component_coverage(envelope) == []
    assert run_components_gates(envelope) == []


def test_components_with_defined_patterns_passes() -> None:
    assert check_component_pattern_references(components_envelope()) == []


def test_empty_system_patterns_collection_violates() -> None:
    envelope = components_envelope(system_patterns=())
    assert any(
        v.kind == VIOLATION_EMPTY_PATTERN_COLLECTION and "system_patterns" in v.message
        for v in check_component_pattern_references(envelope)
    )


def test_empty_component_patterns_collection_violates() -> None:
    envelope = components_envelope(component_patterns=())
    assert any(
        v.kind == VIOLATION_EMPTY_PATTERN_COLLECTION and "component_patterns" in v.message
        for v in check_component_pattern_references(envelope)
    )


def test_component_with_empty_pattern_ids_violates() -> None:
    envelope = components_envelope(components=(replace(COMPONENT_ONE, pattern_ids=()),))
    (violation,) = [
        v
        for v in check_component_pattern_references(envelope)
        if v.kind == VIOLATION_NO_PATTERN_REFERENCE
    ]
    assert violation.row_id == "component-1"


def test_component_referencing_undefined_pattern_violates() -> None:
    envelope = components_envelope(components=(replace(COMPONENT_ONE, pattern_ids=("pattern-9",)),))
    (violation,) = [
        v
        for v in check_component_pattern_references(envelope)
        if v.kind == VIOLATION_UNDEFINED_PATTERN_REFERENCE
    ]
    assert "pattern-9" in violation.message


def test_pattern_id_resolves_across_both_collections() -> None:
    envelope = components_envelope(
        components=(replace(COMPONENT_ONE, pattern_ids=("system-pattern-1",)),)
    )
    assert check_component_pattern_references(envelope) == []


def test_component_citing_defined_constraints_passes() -> None:
    assert check_component_constraint_references(components_envelope()) == []


def test_component_with_empty_constraint_ids_passes() -> None:
    envelope = components_envelope(components=(replace(COMPONENT_ONE, constraint_ids=()),))
    assert check_component_constraint_references(envelope) == []


def test_component_referencing_undefined_constraint_violates() -> None:
    envelope = components_envelope(
        components=(replace(COMPONENT_ONE, constraint_ids=("constraint-9",)),)
    )
    (violation,) = check_component_constraint_references(envelope)
    assert violation.kind == VIOLATION_UNDEFINED_CONSTRAINT_REFERENCE


def test_component_constraint_gates_skip_only_missing_constraints() -> None:
    missing_constraints = ArtifactEnvelope(
        domain=make_domain(),
        components=make_components(
            components=(replace(COMPONENT_ONE, constraint_ids=("constraint-9",)),)
        ),
    )
    assert check_component_constraint_references(missing_constraints) == []
    assert check_prioritized_constraint_discharge(missing_constraints) == []

    complete = components_envelope(
        components=(replace(COMPONENT_ONE, constraint_ids=("constraint-9",)),)
    )
    assert kinds(check_component_constraint_references(complete)) == [
        VIOLATION_UNDEFINED_CONSTRAINT_REFERENCE
    ]
    assert kinds(check_prioritized_constraint_discharge(complete)) == [
        VIOLATION_UNDISCHARGED_PRIORITIZED_CONSTRAINT
    ]


def test_constraint_reference_violation_names_both_ids() -> None:
    envelope = components_envelope(
        components=(replace(COMPONENT_ONE, constraint_ids=("constraint-9",)),)
    )
    (violation,) = check_component_constraint_references(envelope)
    assert "component-1" in violation.message
    assert "constraint-9" in violation.message
    assert CONSTRAINTS_FILENAME in violation.message


def test_prioritized_constraint_discharged_by_a_component_passes() -> None:
    assert check_prioritized_constraint_discharge(components_envelope()) == []


def test_prioritized_constraint_with_no_discharger_violates() -> None:
    envelope = components_envelope(components=(replace(COMPONENT_ONE, constraint_ids=()),))
    (violation,) = check_prioritized_constraint_discharge(envelope)
    assert violation.kind == VIOLATION_UNDISCHARGED_PRIORITIZED_CONSTRAINT
    assert violation.row_id == "constraint-1"


def test_traded_away_constraint_without_discharger_passes() -> None:
    traded = ConstraintRow(
        id="constraint-traded",
        statement="Prefer single-region writes.",
        attribute=TRADED_AWAY_ATTRIBUTE,
        anchor_ids=("entity-1",),
    )
    envelope = components_envelope(
        constraints=make_constraints(
            constraints=(CONSTRAINT_LATENCY, traded),
        ),
        components=(replace(COMPONENT_ONE, constraint_ids=("constraint-1",)),),
    )
    assert check_prioritized_constraint_discharge(envelope) == []


def test_not_load_bearing_constraint_is_rejected_before_component_discharge() -> None:
    not_load_bearing = ConstraintRow(
        id="constraint-nlb",
        statement="Reliability is out of scope here.",
        attribute=NOT_LOAD_BEARING_ATTRIBUTE,
        anchor_ids=("entity-1",),
    )
    constraints = make_constraints(
        constraints=(CONSTRAINT_LATENCY, not_load_bearing),
    )

    assert kinds(
        run_constraints_gates(constraints_envelope(constraints=constraints.constraints))
    ) == [VIOLATION_CONSTRAINT_ON_NOT_LOAD_BEARING]

    components = components_envelope(
        constraints=constraints,
        components=(replace(COMPONENT_ONE, constraint_ids=("constraint-1",)),),
    )
    assert check_prioritized_constraint_discharge(components) == []


def test_run_components_gates_clears_a_conforming_envelope() -> None:
    assert run_components_gates(components_envelope()) == []


def test_component_with_a_distinct_in_process_store_passes() -> None:
    in_process = StoreRow(id="store-local", category="in-process", sharing="silo")
    envelope = components_envelope(
        components=(replace(COMPONENT_ONE, store_ids=(in_process.id,)),),
        stores=(in_process,),
    )

    assert run_components_gates(envelope) == []


def test_component_without_store_reference_violates() -> None:
    envelope = components_envelope(
        components=(replace(COMPONENT_ONE, store_ids=()),),
    )

    (violation,) = check_store_definitions(envelope)

    assert violation.kind == VIOLATION_NO_STORE_REFERENCE
    assert violation.row_id == "component-1"
    assert "in-process" in violation.message


def test_component_referencing_undefined_store_violates() -> None:
    envelope = components_envelope(
        components=(replace(COMPONENT_ONE, store_ids=("store-missing",)),),
        stores=(),
    )

    (violation,) = check_store_definitions(envelope)

    assert violation.kind == VIOLATION_UNDEFINED_STORE_REFERENCE
    assert violation.row_id == "component-1"
    assert "store-missing" in violation.message


def test_component_repeating_a_store_reference_violates_its_definition_gate() -> None:
    envelope = components_envelope(
        components=(replace(COMPONENT_ONE, store_ids=("store-1", "store-1")),),
    )

    (violation,) = check_store_definitions(envelope)

    assert violation.kind == VIOLATION_DUPLICATE_STORE_REFERENCE
    assert violation.row_id == "component-1"
    assert "store-1" in violation.message


def test_component_repeating_an_undefined_store_reports_both_violation_kinds() -> None:
    envelope = components_envelope(
        components=(replace(COMPONENT_ONE, store_ids=("store-missing", "store-missing")),),
        stores=(),
    )

    violations = check_store_definitions(envelope)

    assert kinds(violations) == [
        VIOLATION_UNDEFINED_STORE_REFERENCE,
        VIOLATION_DUPLICATE_STORE_REFERENCE,
    ]


def test_component_repeating_a_store_reference_three_times_reports_one_duplicate() -> None:
    envelope = components_envelope(
        components=(replace(COMPONENT_ONE, store_ids=("store-1", "store-1", "store-1")),),
    )

    (violation,) = check_store_definitions(envelope)

    assert violation.kind == VIOLATION_DUPLICATE_STORE_REFERENCE


def test_in_process_store_cannot_be_shared_between_components() -> None:
    in_process = StoreRow(id="store-local", category="in-process", sharing="silo")
    second = ComponentRow(
        id="component-2",
        name="Billing",
        entity_ids=("entity-2",),
        pattern_ids=("system-pattern-1",),
        store_ids=(in_process.id,),
    )
    envelope = components_envelope(
        components=(
            replace(COMPONENT_ONE, store_ids=(in_process.id,)),
            second,
        ),
        stores=(in_process,),
    )

    (violation,) = check_store_definitions(envelope)

    assert violation.kind == VIOLATION_SHARED_IN_PROCESS_STORE
    assert violation.row_id == "component-2"
    assert "component-1" in violation.message


def test_component_repeating_its_own_in_process_store_reference_reports_only_duplicate() -> None:
    """A repeat of one component's own in-process store is a naming mistake,
    not a sharing violation — the second occurrence never reaches the
    ownership check."""
    in_process = StoreRow(id="store-local", category="in-process", sharing="silo")
    envelope = components_envelope(
        components=(replace(COMPONENT_ONE, store_ids=(in_process.id, in_process.id)),),
        stores=(in_process,),
    )

    (violation,) = check_store_definitions(envelope)

    assert violation.kind == VIOLATION_DUPLICATE_STORE_REFERENCE


def test_durable_store_may_be_shared_between_components() -> None:
    second = ComponentRow(
        id="component-2",
        name="Billing",
        entity_ids=("entity-2",),
        pattern_ids=("system-pattern-1",),
        store_ids=("store-1",),
    )
    envelope = components_envelope(components=(COMPONENT_ONE, second))

    assert check_store_definitions(envelope) == []


def test_components_may_use_different_valid_stores_without_comparison() -> None:
    second_store = StoreRow(id="store-2", category="document", sharing="bridge")
    second = ComponentRow(
        id="component-2",
        name="Billing",
        entity_ids=("entity-2",),
        pattern_ids=("system-pattern-1",),
        store_ids=(second_store.id,),
    )
    envelope = components_envelope(
        components=(COMPONENT_ONE, second),
        stores=(STORE_ONE, second_store),
    )

    assert run_components_gates(envelope) == []


def test_unreferenced_store_violates_coverage() -> None:
    unused = StoreRow(id="store-unused", category="object", sharing="bridge")
    envelope = components_envelope(stores=(STORE_ONE, unused))

    (violation,) = check_store_coverage(envelope)

    assert violation.kind == VIOLATION_UNCOVERED_STORE
    assert violation.row_id == unused.id
    assert unused.id in violation.message


def test_store_category_and_sharing_membership_use_the_closed_vocabularies() -> None:
    unknown = StoreRow(
        id="store-unknown",
        category="filesystem",
        sharing="self-hosted",
    )
    artifact = make_components(
        components=(replace(COMPONENT_ONE, store_ids=(unknown.id,)),),
        stores=(unknown,),
    )
    parsed = parse_components_artifact(render_components_artifact(artifact))
    envelope = ArtifactEnvelope(
        domain=make_domain(),
        constraints=make_constraints(),
        components=parsed,
    )

    violations = check_store_value_membership(envelope)

    assert kinds(violations) == [
        VIOLATION_UNKNOWN_STORE_CATEGORY,
        VIOLATION_UNKNOWN_STORE_SHARING,
    ]
    assert all(violation.row_id == unknown.id for violation in violations)
    assert all(unknown.id in violation.message for violation in violations)
    assert STORE_CATEGORIES == (
        "in-process",
        "relational",
        "document",
        "key-value",
        "object",
    )
    assert STORE_SHARING_MODELS == ("silo", "pool", "bridge")
    assert ", ".join(STORE_CATEGORIES) in violations[0].message
    assert ", ".join(STORE_SHARING_MODELS) in violations[1].message


def test_store_gates_do_not_compare_hosting_and_store_tenancy() -> None:
    silo = StoreRow(id="store-silo", category="relational", sharing="silo")
    envelope = components_envelope(
        constraints=make_constraints(
            hosting=(
                HostingRow(id="hosting-compute", facet="compute", value="per-request"),
                HostingRow(id="hosting-model", facet="model", value="pool"),
                HostingRow(id="hosting-topology", facet="topology", value="single-unit"),
            )
        ),
        components=(replace(COMPONENT_ONE, store_ids=(silo.id,)),),
        stores=(silo,),
    )

    assert check_store_definitions(envelope) == []
    assert check_store_coverage(envelope) == []
    assert check_store_value_membership(envelope) == []


def test_store_gates_allow_a_pooled_store_for_a_self_hosted_application() -> None:
    envelope = components_envelope(
        constraints=make_constraints(
            hosting=(
                HostingRow(id="hosting-compute", facet="compute", value="per-request"),
                HostingRow(id="hosting-model", facet="model", value="self-hosted"),
                HostingRow(id="hosting-topology", facet="topology", value="single-unit"),
            )
        )
    )

    assert check_store_definitions(envelope) == []
    assert check_store_coverage(envelope) == []
    assert check_store_value_membership(envelope) == []


def test_store_gates_ignore_an_unusable_hosting_block() -> None:
    without_hosting = components_envelope(constraints=make_constraints(hosting=()))
    for gate in (
        check_store_definitions,
        check_store_coverage,
        check_store_value_membership,
    ):
        assert gate(without_hosting) == []


def test_components_gates_tuple_includes_traceability_gates_in_order() -> None:
    expected = (
        check_component_entity_references,
        check_entity_component_coverage,
        check_component_pattern_references,
        check_component_constraint_references,
        check_prioritized_constraint_discharge,
        check_store_definitions,
        check_store_coverage,
        check_store_value_membership,
    )
    start = COMPONENTS_GATES.index(check_component_entity_references)
    assert COMPONENTS_GATES[start : start + len(expected)] == expected


def test_run_domain_gates_and_run_constraints_gates_unchanged() -> None:
    assert run_domain_gates(domain_envelope()) == []
    assert run_constraints_gates(constraints_envelope()) == []


def test_traceability_gates_are_inert_off_components_stage() -> None:
    envelope = constraints_envelope()
    for gate in (
        check_component_entity_references,
        check_entity_component_coverage,
        check_component_pattern_references,
        check_component_constraint_references,
        check_prioritized_constraint_discharge,
        check_store_definitions,
        check_store_coverage,
        check_store_value_membership,
    ):
        assert gate(envelope) == []


# --------------------------------------------------------------------------
# Workflow-reference gate
# --------------------------------------------------------------------------


def test_workflow_referencing_defined_entities_passes() -> None:
    assert check_entity_references(domain_envelope()) == []


def test_workflow_referencing_undefined_entity_violates() -> None:
    envelope = domain_envelope(workflows=(replace(WORKFLOW_PLACE_ORDER, entity_ids=("entity-9",)),))
    assert kinds(check_entity_references(envelope)) == [VIOLATION_UNDEFINED_ENTITY_REFERENCE]


def test_workflow_violation_message_names_both_ids() -> None:
    envelope = domain_envelope(workflows=(replace(WORKFLOW_PLACE_ORDER, entity_ids=("entity-9",)),))
    (violation,) = check_entity_references(envelope)
    assert "workflow-1" in violation.message
    assert "entity-9" in violation.message
    assert violation.row_id == "workflow-1"
    assert violation.artifact == DOMAIN_FILENAME


def test_workflow_with_no_entity_references_violates() -> None:
    """An empty reference list is the shape the rule exists to catch, not a
    pass."""
    envelope = domain_envelope(workflows=(replace(WORKFLOW_PLACE_ORDER, entity_ids=()),))
    (violation,) = check_entity_references(envelope)
    assert violation.kind == VIOLATION_NO_ENTITY_REFERENCE
    assert "workflow-1" in violation.message


def test_every_undefined_reference_is_reported() -> None:
    envelope = domain_envelope(
        workflows=(replace(WORKFLOW_PLACE_ORDER, entity_ids=("entity-8", "entity-9")),)
    )
    violations = check_entity_references(envelope)
    assert kinds(violations) == [VIOLATION_UNDEFINED_ENTITY_REFERENCE] * 2
    assert [("entity-8" in v.message, "entity-9" in v.message) for v in violations] == [
        (True, False),
        (False, True),
    ]


def test_business_rule_with_no_entity_references_violates() -> None:
    """Rules are in scope alongside workflows: a rule connected to no entity
    is a legal constraint anchor that breaks the traceability chain."""
    envelope = domain_envelope(business_rules=(replace(RULE_ONE_CUSTOMER, entity_ids=()),))
    (violation,) = check_entity_references(envelope)
    assert violation.kind == VIOLATION_NO_ENTITY_REFERENCE
    assert violation.row_id == "rule-1"


# --------------------------------------------------------------------------
# Entity-fields gate
# --------------------------------------------------------------------------


def test_entities_with_fields_pass() -> None:
    assert check_entity_fields(domain_envelope()) == []


def test_entity_without_fields_violates() -> None:
    envelope = domain_envelope(entities=(replace(ENTITY_ORDER, fields=()), ENTITY_CUSTOMER))

    violations = check_entity_fields(envelope)

    assert kinds(violations) == [VIOLATION_ENTITY_WITHOUT_FIELDS]
    assert violations[0].row_id == "entity-1"


def test_every_fieldless_entity_is_reported_not_just_the_first() -> None:
    envelope = domain_envelope(
        entities=(
            replace(ENTITY_ORDER, fields=()),
            replace(ENTITY_CUSTOMER, fields=()),
        )
    )

    assert [v.row_id for v in check_entity_fields(envelope)] == [
        "entity-1",
        "entity-2",
    ]


def test_duplicate_field_name_within_an_entity_violates() -> None:
    envelope = domain_envelope(
        entities=(
            replace(
                ENTITY_ORDER,
                fields=(
                    FieldRow(name="total", type=FieldType.NUMBER),
                    FieldRow(name="total", type=FieldType.TEXT),
                ),
            ),
            ENTITY_CUSTOMER,
        )
    )

    violations = check_entity_fields(envelope)

    assert kinds(violations) == [VIOLATION_DUPLICATE_FIELD_NAME]
    assert "total" in violations[0].message


def test_a_thrice_declared_field_is_reported_once_not_twice() -> None:
    """One violation per duplicated name, matching check_duplicate_row_ids —
    every extra correction is retry budget spent on a defect already named."""
    envelope = domain_envelope(
        entities=(
            replace(
                ENTITY_ORDER,
                fields=tuple(FieldRow(name="total", type=FieldType.NUMBER) for _ in range(3)),
            ),
            ENTITY_CUSTOMER,
        )
    )

    violations = check_entity_fields(envelope)

    assert kinds(violations) == [VIOLATION_DUPLICATE_FIELD_NAME]
    assert "3 times" in violations[0].message


def test_the_same_field_name_in_two_entities_passes() -> None:
    """Uniqueness is per entity — two entities may both hold an ``id``."""
    envelope = domain_envelope(
        entities=(
            replace(ENTITY_ORDER, fields=(FieldRow(name="id", type=FieldType.TEXT),)),
            replace(ENTITY_CUSTOMER, fields=(FieldRow(name="id", type=FieldType.TEXT),)),
        )
    )

    assert check_entity_fields(envelope) == []


def test_reference_field_without_a_target_violates() -> None:
    envelope = domain_envelope(
        entities=(
            replace(
                ENTITY_ORDER,
                fields=(FieldRow(name="customer", type=FieldType.REFERENCE),),
            ),
            ENTITY_CUSTOMER,
        )
    )

    violations = check_entity_fields(envelope)

    assert kinds(violations) == [VIOLATION_FIELD_REFERENCE_TARGET]


def test_non_reference_field_carrying_a_target_violates() -> None:
    envelope = domain_envelope(
        entities=(
            replace(
                ENTITY_ORDER,
                fields=(FieldRow(name="customer", type=FieldType.TEXT, entity_id="entity-2"),),
            ),
            ENTITY_CUSTOMER,
        )
    )

    violations = check_entity_fields(envelope)

    assert kinds(violations) == [VIOLATION_FIELD_REFERENCE_TARGET]


def test_reference_field_to_a_defined_entity_passes() -> None:
    # ENTITY_ORDER's customer field points at entity-2, which is defined here.
    assert check_entity_references(domain_envelope()) == []


def test_reference_field_to_an_undefined_entity_violates() -> None:
    envelope = domain_envelope(
        entities=(
            replace(
                ENTITY_ORDER,
                fields=(FieldRow(name="customer", type=FieldType.REFERENCE, entity_id="entity-9"),),
            ),
            ENTITY_CUSTOMER,
        )
    )

    violations = check_entity_references(envelope)

    assert kinds(violations) == [VIOLATION_UNDEFINED_ENTITY_REFERENCE]
    assert violations[0].row_id == "entity-1"
    assert "entity-9" in violations[0].message


def test_a_targetless_reference_is_reported_once_not_by_both_gates() -> None:
    """One defect, one correction: the shape gate owns a missing target, so
    the resolution gate stays silent about it."""
    envelope = domain_envelope(
        entities=(
            replace(
                ENTITY_ORDER,
                fields=(FieldRow(name="customer", type=FieldType.REFERENCE),),
            ),
            ENTITY_CUSTOMER,
        )
    )

    assert check_entity_references(envelope) == []
    assert len(check_entity_fields(envelope)) == 1


# --------------------------------------------------------------------------
# Duplicate-id gate
# --------------------------------------------------------------------------


def test_unique_row_ids_pass() -> None:
    assert check_duplicate_row_ids(constraints_envelope()) == []


def test_duplicate_entity_id_violates_naming_the_id() -> None:
    envelope = domain_envelope(entities=(ENTITY_ORDER, replace(ENTITY_CUSTOMER, id="entity-1")))
    (violation,) = check_duplicate_row_ids(envelope)
    assert violation.kind == VIOLATION_DUPLICATE_ROW_ID
    assert violation.row_id == "entity-1"
    assert "entity-1" in violation.message
    assert "hosting" not in violation.message
    assert "store" not in violation.message


def test_duplicate_id_reported_once_per_id() -> None:
    envelope = domain_envelope(
        entities=(
            ENTITY_ORDER,
            replace(ENTITY_CUSTOMER, id="entity-1"),
            EntityRow(
                id="entity-1",
                name="Order again",
                fields=(FieldRow(name="total", type=FieldType.NUMBER),),
            ),
        )
    )
    violations = check_duplicate_row_ids(envelope)
    assert len(violations) == 1
    assert "3 rows" in violations[0].message


def test_id_shared_across_row_kinds_violates() -> None:
    """Anchors resolve against the union of every anchorable row kind, so a
    collision between kinds is as ambiguous as one within a kind. Hosting and
    store ids share this same duplicate-id protection without being anchors
    themselves — see test_hosting_ids_are_unique_but_do_not_enter_design_row_resolution."""
    envelope = domain_envelope(
        entities=(
            EntityRow(
                id="shared",
                name="Order",
                fields=(FieldRow(name="total", type=FieldType.NUMBER),),
            ),
            ENTITY_CUSTOMER,
        ),
        business_rules=(replace(RULE_ONE_CUSTOMER, entity_ids=("shared",)),),
        workflows=(replace(WORKFLOW_PLACE_ORDER, id="shared", entity_ids=("shared",)),),
        decisions=(replace(DOMAIN_DECISION, anchor="shared"),),
    )
    (violation,) = check_duplicate_row_ids(envelope)
    assert violation.row_id == "shared"


def test_id_shared_across_artifacts_violates() -> None:
    """A decision anchor resolves against the artifact under check *and* its
    upstream, so uniqueness has to span both or the ambiguity just moves up."""
    envelope = ArtifactEnvelope(
        domain=make_domain(
            workflows=(replace(WORKFLOW_PLACE_ORDER, id="checkout"),),
            decisions=(replace(DOMAIN_DECISION, anchor="checkout"),),
        ),
        constraints=make_constraints(constraints=(replace(CONSTRAINT_LATENCY, id="checkout"),)),
    )
    (violation,) = check_duplicate_row_ids(envelope)
    assert violation.row_id == "checkout"


def test_cross_artifact_collision_names_both_artifacts() -> None:
    envelope = ArtifactEnvelope(
        domain=make_domain(workflows=(replace(WORKFLOW_PLACE_ORDER, id="checkout"),)),
        constraints=make_constraints(constraints=(replace(CONSTRAINT_LATENCY, id="checkout"),)),
    )
    (violation,) = check_duplicate_row_ids(envelope)
    assert DOMAIN_FILENAME in violation.message
    assert CONSTRAINTS_FILENAME in violation.message
    assert "hosting" not in violation.message
    assert "store" not in violation.message
    # Reported against the side the retried stage can rename.
    assert violation.artifact == CONSTRAINTS_FILENAME


# --------------------------------------------------------------------------
# Hosting gates
# --------------------------------------------------------------------------


def test_complete_concrete_hosting_answers_clear_the_constraints_gate_set() -> None:
    assert run_constraints_gates(constraints_envelope()) == []


@pytest.mark.parametrize("facet", HOSTING_FACETS)
def test_missing_hosting_facet_violates_naming_the_facet(facet: str) -> None:
    envelope = constraints_envelope(
        hosting=tuple(row for row in HOSTING_ROWS if row.facet != facet)
    )

    (violation,) = check_hosting_totality(envelope)

    assert violation.kind == VIOLATION_MISSING_HOSTING_FACET
    assert violation.row_id is None
    assert facet in violation.message


def test_duplicate_hosting_facet_violates_naming_its_rows() -> None:
    duplicate = replace(HOSTING_ROWS[0], id="hosting-compute-again")
    envelope = constraints_envelope(hosting=(*HOSTING_ROWS, duplicate))

    (violation,) = check_hosting_totality(envelope)

    assert violation.kind == VIOLATION_REDUNDANT_HOSTING_FACET
    assert violation.row_id == "hosting-compute"
    assert "hosting-compute-again" in violation.message


def test_unknown_hosting_facet_violates_after_parsing() -> None:
    envelope = constraints_envelope(
        hosting=(replace(HOSTING_ROWS[0], facet="platform"), *HOSTING_ROWS[1:])
    )

    violations = check_hosting_totality(envelope)

    assert kinds(violations) == [
        VIOLATION_MISSING_HOSTING_FACET,
        VIOLATION_UNKNOWN_HOSTING_FACET,
    ]
    assert violations[-1].row_id == "hosting-compute"


def test_hosting_value_outside_its_vocabulary_parses_then_violates() -> None:
    artifact = parse_constraints_artifact(
        render_constraints_artifact(
            make_constraints(
                hosting=(
                    replace(HOSTING_ROWS[0], value="vendor-serverless"),
                    *HOSTING_ROWS[1:],
                )
            )
        )
    )

    (violation,) = check_hosting_value_membership(
        ArtifactEnvelope(domain=make_domain(), constraints=artifact)
    )

    assert violation.kind == VIOLATION_UNKNOWN_HOSTING_VALUE
    assert violation.row_id == "hosting-compute"
    assert "vendor-serverless" in violation.message


def test_hosting_vocabulary_matches_the_fixed_facet_mapping() -> None:
    assert HOSTING_FACET_VALUES == {
        "compute": ("per-request", "managed-containers", "long-lived", "mixed"),
        "model": ("self-hosted", "silo", "pool", "bridge"),
        "topology": ("single-unit", "multi-unit"),
    }
    assert tuple(HOSTING_FACET_VALUES) == HOSTING_FACETS
    assert all(
        len(values) == len(set(values))
        and all(value not in {"pending", "undecided"} for value in values)
        for values in HOSTING_FACET_VALUES.values()
    )


def test_mixed_compute_requires_multi_unit_topology_without_judging_stores() -> None:
    envelope = constraints_envelope(
        hosting=(
            replace(HOSTING_ROWS[0], value="mixed"),
            HOSTING_ROWS[1],
            replace(HOSTING_ROWS[2], value="multi-unit"),
        )
    )

    assert check_hosting_topology_coherence(envelope) == []
    assert check_hosting_value_membership(envelope) == []


def test_mixed_compute_with_single_unit_topology_violates() -> None:
    envelope = constraints_envelope(
        hosting=(replace(HOSTING_ROWS[0], value="mixed"), *HOSTING_ROWS[1:])
    )

    (violation,) = check_hosting_topology_coherence(envelope)

    assert violation.kind == VIOLATION_HOSTING_TOPOLOGY_COHERENCE
    assert violation.row_id == "hosting-compute"


def test_bridge_model_requires_multi_unit_topology() -> None:
    coherent = constraints_envelope(
        hosting=(
            HOSTING_ROWS[0],
            replace(HOSTING_ROWS[1], value="bridge"),
            replace(HOSTING_ROWS[2], value="multi-unit"),
        )
    )
    incoherent = constraints_envelope(
        hosting=(HOSTING_ROWS[0], replace(HOSTING_ROWS[1], value="bridge"), *HOSTING_ROWS[2:])
    )

    assert check_hosting_topology_coherence(coherent) == []
    (violation,) = check_hosting_topology_coherence(incoherent)
    assert violation.kind == VIOLATION_HOSTING_TOPOLOGY_COHERENCE
    assert violation.row_id == "hosting-model"


def test_topology_coherence_guard_skips_when_topology_row_is_absent() -> None:
    envelope = constraints_envelope(hosting=(HOSTING_ROWS[0], HOSTING_ROWS[1]))

    assert check_hosting_topology_coherence(envelope) == []


def test_topology_coherence_guard_skips_when_topology_row_is_duplicated() -> None:
    envelope = constraints_envelope(
        hosting=(
            replace(HOSTING_ROWS[0], value="mixed"),
            HOSTING_ROWS[1],
            HOSTING_ROWS[2],
            replace(HOSTING_ROWS[2], id="hosting-topology-2"),
        )
    )

    assert check_hosting_topology_coherence(envelope) == []


def test_topology_coherence_guard_skips_when_topology_value_is_unrecognized() -> None:
    envelope = constraints_envelope(
        hosting=(
            replace(HOSTING_ROWS[0], value="mixed"),
            HOSTING_ROWS[1],
            replace(HOSTING_ROWS[2], value="pending"),
        )
    )

    assert check_hosting_topology_coherence(envelope) == []


@pytest.mark.parametrize("model", ("pool", "self-hosted"))
def test_vendor_operated_and_self_hosted_models_are_distinct_valid_answers(
    model: str,
) -> None:
    envelope = constraints_envelope(
        hosting=(HOSTING_ROWS[0], replace(HOSTING_ROWS[1], value=model), HOSTING_ROWS[2])
    )

    assert check_hosting_value_membership(envelope) == []


def test_hosting_ids_stay_out_of_local_design_resolution_but_are_feedback_targets() -> None:
    artifact = make_constraints(
        hosting=(replace(HOSTING_ROWS[0], id="constraint-1"), *HOSTING_ROWS[1:])
    )
    envelope = ArtifactEnvelope(domain=make_domain(), constraints=artifact)

    (duplicate,) = check_duplicate_row_ids(envelope)

    assert duplicate.kind == VIOLATION_DUPLICATE_ROW_ID
    assert duplicate.row_id == "constraint-1"
    assert "hosting-compute" not in design_row_ids(make_constraints())
    unresolved = check_decision_records(
        constraints_envelope(decisions=(replace(CONSTRAINTS_DECISION, anchor="hosting-compute"),))
    )
    assert kinds(unresolved) == [VIOLATION_UNRESOLVED_DECISION_ANCHOR]
    feedback = feedback_row(target=row_target("hosting-compute"))
    feedback_violations = check_feedback_integrity(
        constraints_envelope(feedback=(feedback,), predecessor=make_constraints())
    )
    assert feedback_violations == []


def test_store_ids_stay_out_of_local_design_resolution_but_are_feedback_targets() -> None:
    envelope = components_envelope(stores=(replace(STORE_ONE, id="constraint-1"),))

    (duplicate,) = check_duplicate_row_ids(envelope)

    assert duplicate.kind == VIOLATION_DUPLICATE_ROW_ID
    assert duplicate.row_id == "constraint-1"
    assert "store-1" not in design_row_ids(make_components())
    unresolved = check_decision_records(
        components_envelope(decisions=(replace(COMPONENTS_DECISION, anchor="store-1"),))
    )
    assert kinds(unresolved) == [VIOLATION_UNRESOLVED_DECISION_ANCHOR]
    feedback = feedback_row(target=row_target("store-1"))
    feedback_violations = check_feedback_integrity(
        components_envelope(feedback=(feedback,), predecessor=make_components())
    )
    assert feedback_violations == []


# --------------------------------------------------------------------------
# Attribute-totality gate
# --------------------------------------------------------------------------


def test_every_attribute_disposed_exactly_once_passes() -> None:
    assert check_attribute_totality(constraints_envelope()) == []


def test_missing_attribute_violates_naming_it() -> None:
    dropped = QUALITY_ATTRIBUTES[-1]
    envelope = constraints_envelope(dispositions=ALL_DISPOSITIONS[:-1])
    (violation,) = check_attribute_totality(envelope)
    assert violation.kind == VIOLATION_UNDISPOSED_ATTRIBUTE
    assert violation.row_id is None
    assert dropped in violation.message


def test_duplicate_attribute_disposition_violates() -> None:
    extra = replace(ALL_DISPOSITIONS[0], id="attribute-again")
    envelope = constraints_envelope(dispositions=(*ALL_DISPOSITIONS, extra))
    (violation,) = check_attribute_totality(envelope)
    assert violation.kind == VIOLATION_REDUNDANT_DISPOSITION
    assert "attribute-again" in violation.message
    assert PRIORITIZED_ATTRIBUTE in violation.message


def test_not_load_bearing_counts_as_a_disposition() -> None:
    """The honest answer for an attribute nobody ranks on satisfies totality —
    it is never read as an omission."""
    disposed_not_load_bearing = [
        row.attribute
        for row in ALL_DISPOSITIONS
        if row.disposition == ConstraintDisposition.NOT_LOAD_BEARING
    ]
    assert disposed_not_load_bearing
    assert check_attribute_totality(constraints_envelope()) == []


def test_attribute_outside_the_shipped_list_violates() -> None:
    extra = AttributeDispositionRow(
        id="attribute-throughput",
        attribute="throughput",
        disposition=ConstraintDisposition.PRIORITIZED,
    )
    envelope = constraints_envelope(dispositions=(*ALL_DISPOSITIONS, extra))
    (violation,) = check_attribute_totality(envelope)
    assert violation.kind == VIOLATION_UNKNOWN_DISPOSED_ATTRIBUTE
    assert violation.row_id == "attribute-throughput"
    assert "throughput" in violation.message


def test_constraint_row_naming_an_unknown_attribute_violates() -> None:
    envelope = constraints_envelope(
        constraints=(replace(CONSTRAINT_LATENCY, attribute="throughput"),)
    )
    (violation,) = check_attribute_totality(envelope)
    assert violation.kind == VIOLATION_UNKNOWN_CONSTRAINT_ATTRIBUTE
    assert violation.row_id == "constraint-1"
    assert "throughput" in violation.message


def test_constraint_row_attribute_is_validated_even_when_dispositions_are_complete() -> None:
    """Nothing else validates a constraint's ``attribute``: the anchor gate
    reads only anchor ids and the non-empty gate only counts rows."""
    envelope = constraints_envelope(
        dispositions=ALL_DISPOSITIONS,
        constraints=(replace(CONSTRAINT_LATENCY, attribute="throughput"),),
    )
    assert kinds(check_attribute_totality(envelope)) == [VIOLATION_UNKNOWN_CONSTRAINT_ATTRIBUTE]


def test_constraint_serving_a_not_load_bearing_attribute_violates() -> None:
    envelope = constraints_envelope(
        constraints=(replace(CONSTRAINT_LATENCY, attribute=NOT_LOAD_BEARING_ATTRIBUTE),)
    )
    (violation,) = check_attribute_totality(envelope)
    assert violation.kind == VIOLATION_CONSTRAINT_ON_NOT_LOAD_BEARING
    assert violation.row_id == "constraint-1"
    assert NOT_LOAD_BEARING_ATTRIBUTE in violation.message


def test_constraint_serving_a_traded_away_attribute_passes() -> None:
    """The arm above stops at ``not-load-bearing``: spending an attribute
    knowingly and bounding how much you spend are coherent together, so this
    pairing is the shape the gate must *not* reject.

    Pins a carve stated in three places — ``roadmap-constraints.md``'s rule 3,
    this gate's docstring, and ``ROADMAP_FORMAT.md`` § "Relations — return
    violations" — and asserted by none until now. Widening the arm to include
    ``TRADED_AWAY`` passed the full suite on 2026-08-04.
    """
    envelope = constraints_envelope(
        constraints=(replace(CONSTRAINT_LATENCY, attribute=TRADED_AWAY_ATTRIBUTE),)
    )
    assert check_attribute_totality(envelope) == []


# --------------------------------------------------------------------------
# Cross-artifact anchor gate
# --------------------------------------------------------------------------


def test_constraint_anchored_to_a_defined_entity_passes() -> None:
    envelope = constraints_envelope(
        constraints=(replace(CONSTRAINT_LATENCY, anchor_ids=("entity-1",)),)
    )
    assert check_constraint_anchors(envelope) == []


def test_constraint_anchored_to_a_rule_or_workflow_id_passes() -> None:
    """The anchor target set is the union of the three domain row kinds."""
    envelope = constraints_envelope(
        constraints=(replace(CONSTRAINT_LATENCY, anchor_ids=("rule-1", "workflow-1")),)
    )
    assert check_constraint_anchors(envelope) == []


def test_constraint_anchored_to_an_unknown_id_violates() -> None:
    envelope = constraints_envelope(
        constraints=(replace(CONSTRAINT_LATENCY, anchor_ids=("entity-9",)),)
    )
    (violation,) = check_constraint_anchors(envelope)
    assert violation.kind == VIOLATION_UNRESOLVED_CONSTRAINT_ANCHOR
    assert "constraint-1" in violation.message
    assert "entity-9" in violation.message
    assert DOMAIN_FILENAME in violation.message


def test_constraint_with_no_anchor_violates() -> None:
    envelope = constraints_envelope(constraints=(replace(CONSTRAINT_LATENCY, anchor_ids=()),))
    (violation,) = check_constraint_anchors(envelope)
    assert violation.kind == VIOLATION_UNANCHORED_CONSTRAINT
    assert violation.row_id == "constraint-1"


def test_anchor_gate_judges_the_domain_artifact_it_is_given() -> None:
    """It resolves against whatever domain it is handed rather than reading
    one, which is what lets a resumed stage run re-decide it against a freshly
    loaded domain."""
    assert check_constraint_anchors(constraints_envelope()) == []

    without_the_anchored_entity = make_domain(entities=(ENTITY_CUSTOMER,))
    envelope = constraints_envelope(domain=without_the_anchored_entity)
    (violation,) = check_constraint_anchors(envelope)
    assert violation.kind == VIOLATION_UNRESOLVED_CONSTRAINT_ANCHOR
    assert "entity-1" in violation.message


# --------------------------------------------------------------------------
# Decision-record gate
# --------------------------------------------------------------------------


def test_decision_with_alternatives_and_rationale_passes() -> None:
    assert check_decision_records(domain_envelope()) == []


def test_decision_with_no_rejected_alternative_violates() -> None:
    envelope = domain_envelope(decisions=(replace(DOMAIN_DECISION, rejected_alternatives=()),))
    (violation,) = check_decision_records(envelope)
    assert violation.kind == VIOLATION_NO_REJECTED_ALTERNATIVE
    assert "decision-1" in violation.message


def test_decision_with_blank_rationale_violates() -> None:
    envelope = domain_envelope(decisions=(replace(DOMAIN_DECISION, rationale="   "),))
    (violation,) = check_decision_records(envelope)
    assert violation.kind == VIOLATION_BLANK_RATIONALE
    assert violation.row_id == "decision-1"


def test_alternative_without_a_reason_violates() -> None:
    unreasoned = RejectedAlternative(option="A separate cart entity.", reason=" ")
    envelope = domain_envelope(
        decisions=(replace(DOMAIN_DECISION, rejected_alternatives=(unreasoned,)),)
    )
    (violation,) = check_decision_records(envelope)
    assert violation.kind == VIOLATION_UNREASONED_ALTERNATIVE
    assert "A separate cart entity." in violation.message


def test_pending_decision_is_not_a_violation() -> None:
    """Pending is the plan's review channel; gating on it would fail the verb
    on exactly the artifacts it exists to produce."""
    envelope = domain_envelope(decisions=(replace(DOMAIN_DECISION, status=DecisionStatus.PENDING),))
    assert check_decision_records(envelope) == []


def test_settled_and_pending_decisions_are_judged_alike() -> None:
    defective = replace(DOMAIN_DECISION, rejected_alternatives=())
    pending = domain_envelope(decisions=(replace(defective, status=DecisionStatus.PENDING),))
    settled = domain_envelope(decisions=(replace(defective, status=DecisionStatus.SETTLED),))
    assert kinds(check_decision_records(pending)) == [VIOLATION_NO_REJECTED_ALTERNATIVE]
    assert kinds(check_decision_records(pending)) == kinds(check_decision_records(settled))


def test_decision_gate_runs_over_both_artifacts() -> None:
    """One gate serves both stages: a constraints-artifact decision is judged
    by the same rules as a domain one, and reported against its own file."""
    domain_side = domain_envelope(decisions=(replace(DOMAIN_DECISION, rejected_alternatives=()),))
    constraints_side = constraints_envelope(
        decisions=(replace(CONSTRAINTS_DECISION, rejected_alternatives=()),)
    )
    (from_domain,) = check_decision_records(domain_side)
    (from_constraints,) = check_decision_records(constraints_side)
    assert from_domain.kind == from_constraints.kind == VIOLATION_NO_REJECTED_ALTERNATIVE
    assert from_domain.artifact == DOMAIN_FILENAME
    assert from_constraints.artifact == CONSTRAINTS_FILENAME


def test_decision_with_unresolvable_anchor_violates() -> None:
    envelope = domain_envelope(decisions=(replace(DOMAIN_DECISION, anchor="entity-9"),))
    (violation,) = check_decision_records(envelope)
    assert violation.kind == VIOLATION_UNRESOLVED_DECISION_ANCHOR
    assert "decision-1" in violation.message
    assert "entity-9" in violation.message


def test_pending_decision_still_needs_a_resolving_anchor() -> None:
    """Pending exempts the status check, not the anchor: the review channel is
    the reason the anchor exists."""
    envelope = domain_envelope(
        decisions=(replace(DOMAIN_DECISION, anchor="entity-9", status=DecisionStatus.PENDING),)
    )
    assert kinds(check_decision_records(envelope)) == [VIOLATION_UNRESOLVED_DECISION_ANCHOR]


def test_constraints_decision_anchoring_to_a_domain_id_resolves() -> None:
    """The case the envelope signature exists for."""
    envelope = constraints_envelope(decisions=(replace(CONSTRAINTS_DECISION, anchor="workflow-1"),))
    assert check_decision_records(envelope) == []


def test_constraints_decision_with_an_id_in_neither_artifact_violates() -> None:
    envelope = constraints_envelope(decisions=(replace(CONSTRAINTS_DECISION, anchor="entity-9"),))
    (violation,) = check_decision_records(envelope)
    assert violation.kind == VIOLATION_UNRESOLVED_DECISION_ANCHOR
    assert CONSTRAINTS_FILENAME in violation.message
    assert DOMAIN_FILENAME in violation.message


def test_decision_anchored_to_a_disposition_row_id_resolves() -> None:
    """The only spelling that puts a quality attribute in the anchor space."""
    envelope = constraints_envelope(
        decisions=(replace(CONSTRAINTS_DECISION, anchor=f"attribute-{PRIORITIZED_ATTRIBUTE}"),)
    )
    assert check_decision_records(envelope) == []


def test_decision_anchored_to_a_bare_attribute_name_violates() -> None:
    """Attribute names are a constant, not rows, so a bare name resolves
    nowhere and is reported like any other dangling anchor."""
    envelope = constraints_envelope(
        decisions=(replace(CONSTRAINTS_DECISION, anchor=PRIORITIZED_ATTRIBUTE),)
    )
    (violation,) = check_decision_records(envelope)
    assert violation.kind == VIOLATION_UNRESOLVED_DECISION_ANCHOR
    assert PRIORITIZED_ATTRIBUTE in violation.message


def inherited_domain_source(*, owner: str = "domain") -> CarriedDecisions:
    """One current source record matching ``DOMAIN_DECISION`` exactly."""
    return CarriedDecisions(
        confirmed_answers=(
            ConfirmedAnswer(id="answer-cart", answer=DOMAIN_DECISION.chosen_option),
        ),
        decisions=(
            CarriedDecision(
                id=DOMAIN_DECISION.id,
                owner=owner,
                anchor=DOMAIN_DECISION.anchor,
                chosen_option=DOMAIN_DECISION.chosen_option,
                source="answer-cart",
                rationale=DOMAIN_DECISION.rationale,
                rejected_alternatives=tuple(
                    CarriedRejectedAlternative(option=item.option, reason=item.reason)
                    for item in DOMAIN_DECISION.rejected_alternatives
                ),
            ),
        ),
    )


def inherited_domain_envelope(
    *, decision=DOMAIN_DECISION, source=None, status=DecisionStatus.SETTLED, citation="answer-cart"
) -> ArtifactEnvelope:
    """A domain gate call with one current, confirmed carried-decision source."""
    inherited = replace(decision, status=status, source=citation)
    return replace(
        domain_envelope(decisions=(inherited,)),
        carried_decisions=inherited_domain_source() if source is None else source,
    )


def test_inherited_decision_owned_by_current_artifact_with_confirmed_citation_passes() -> None:
    envelope = inherited_domain_envelope()
    assert check_decision_records(envelope) == []
    assert check_inherited_decisions(envelope) == []


def test_roadmap_derived_decision_keeps_existing_deliberation_requirements() -> None:
    sparse = replace(DOMAIN_DECISION, rationale="", rejected_alternatives=())
    inherited = inherited_domain_envelope(
        decision=replace(sparse, rationale=None),
        source=replace(
            inherited_domain_source(),
            decisions=(replace(inherited_domain_source().decisions[0], rationale=None, rejected_alternatives=()),),
        ),
    )

    assert check_decision_records(inherited) == []
    assert check_inherited_decisions(inherited) == []
    assert set(kinds(check_decision_records(domain_envelope(decisions=(sparse,))))) == {
        VIOLATION_NO_REJECTED_ALTERNATIVE,
        VIOLATION_BLANK_RATIONALE,
    }


@pytest.mark.parametrize(
    ("owner", "decision", "anchor", "envelope_factory", "gate_runner"),
    (
        ("components", COMPONENTS_DECISION, "component-1", components_envelope, run_components_gates),
        ("plans", PLANS_DECISION, "plan-1", plans_envelope, run_plans_gates),
    ),
)
def test_inherited_decision_gate_runs_in_every_stage_gate_set(
    owner, decision, anchor, envelope_factory, gate_runner
) -> None:
    inherited = replace(decision, status=DecisionStatus.SETTLED, source="answer-owned", anchor=anchor)
    source = CarriedDecisions(
        confirmed_answers=(ConfirmedAnswer(id="answer-owned", answer=inherited.chosen_option),),
        decisions=(
            CarriedDecision(
                id=inherited.id,
                owner=owner,
                anchor=anchor,
                chosen_option=inherited.chosen_option,
                source="answer-owned",
                rationale=inherited.rationale,
                rejected_alternatives=tuple(
                    CarriedRejectedAlternative(option=item.option, reason=item.reason)
                    for item in inherited.rejected_alternatives
                ),
            ),
        ),
    )
    envelope = replace(envelope_factory(decisions=(inherited,)), carried_decisions=source)

    assert check_inherited_decisions(envelope) == []
    assert not any(violation.kind.startswith("inherited-") for violation in gate_runner(envelope))
    changed = replace(envelope, carried_decisions=replace(source, decisions=(replace(source.decisions[0], anchor="missing"),)))
    assert VIOLATION_ALTERED_INHERITED_DECISION in kinds(gate_runner(changed))


def test_inherited_decision_requires_settled_status() -> None:
    envelope = inherited_domain_envelope(status=DecisionStatus.PENDING)
    assert VIOLATION_INHERITED_DECISION_UNCONFIRMED in kinds(check_inherited_decisions(envelope))


def test_inherited_decision_requires_its_owning_artifact() -> None:
    envelope = inherited_domain_envelope(source=inherited_domain_source(owner="constraints"))
    assert VIOLATION_INHERITED_DECISION_WRONG_ARTIFACT in kinds(check_inherited_decisions(envelope))


def test_inherited_decision_anchor_must_exist_in_its_owning_artifact() -> None:
    source = inherited_domain_source()
    source = replace(source, decisions=(replace(source.decisions[0], anchor="attribute-latency"),))
    envelope = inherited_domain_envelope(decision=replace(DOMAIN_DECISION, anchor="attribute-latency"), source=source)
    assert VIOLATION_INHERITED_DECISION_NONLOCAL_ANCHOR in kinds(check_inherited_decisions(envelope))


def test_every_carried_decision_owned_by_the_artifact_must_appear_once() -> None:
    missing = replace(domain_envelope(), carried_decisions=inherited_domain_source())
    assert VIOLATION_MISSING_INHERITED_DECISION in kinds(check_inherited_decisions(missing))

    inherited = replace(DOMAIN_DECISION, status=DecisionStatus.SETTLED, source="answer-cart")
    duplicate = replace(
        domain_envelope(decisions=(inherited, inherited)), carried_decisions=inherited_domain_source()
    )
    assert VIOLATION_DUPLICATE_INHERITED_DECISION in kinds(check_inherited_decisions(duplicate))


def test_inherited_decision_mutating_approved_fields_refuses() -> None:
    envelope = inherited_domain_envelope(decision=replace(DOMAIN_DECISION, chosen_option="Changed"))
    assert VIOLATION_ALTERED_INHERITED_DECISION in kinds(check_inherited_decisions(envelope))


def test_inherited_decision_with_missing_ambiguous_or_unconfirmed_citation_refuses() -> None:
    missing = inherited_domain_envelope(citation="missing")
    assert VIOLATION_INHERITED_DECISION_UNKNOWN_SOURCE in kinds(check_inherited_decisions(missing))

    source = inherited_domain_source()
    ambiguous = replace(source, decisions=(source.decisions[0], source.decisions[0]))
    assert VIOLATION_INHERITED_DECISION_AMBIGUOUS_SOURCE in kinds(
        check_inherited_decisions(inherited_domain_envelope(source=ambiguous))
    )

    unconfirmed = replace(source, confirmed_answers=())
    assert VIOLATION_INHERITED_DECISION_UNKNOWN_SOURCE in kinds(
        check_inherited_decisions(inherited_domain_envelope(source=unconfirmed))
    )


def test_rebind_current_source_rejects_existing_inherited_row_with_stale_citation() -> None:
    previous = inherited_domain_source()
    current = replace(
        previous,
        confirmed_answers=(
            ConfirmedAnswer(id="answer-new", answer=DOMAIN_DECISION.chosen_option),
        ),
        decisions=(replace(previous.decisions[0], source="answer-new"),),
    )

    violations = check_inherited_decisions(inherited_domain_envelope(source=current))

    assert VIOLATION_INHERITED_DECISION_UNKNOWN_SOURCE in kinds(violations)


def test_inherited_deliberation_must_equal_source_or_be_absent() -> None:
    source = inherited_domain_source()
    no_deliberation = replace(
        source,
        decisions=(replace(source.decisions[0], rationale=None, rejected_alternatives=()),),
    )
    matching = inherited_domain_envelope(
        decision=replace(DOMAIN_DECISION, rationale=None, rejected_alternatives=()), source=no_deliberation
    )
    assert check_inherited_decisions(matching) == []
    invented = inherited_domain_envelope(source=no_deliberation)
    assert VIOLATION_ALTERED_INHERITED_DECISION in kinds(check_inherited_decisions(invented))


def test_inherited_decision_gate_is_registered_for_every_stage() -> None:
    for gates in (DOMAIN_GATES, CONSTRAINTS_GATES, COMPONENTS_GATES, PLANS_GATES):
        assert check_inherited_decisions in gates


def test_legacy_envelope_without_carried_decisions_keeps_existing_gate_results() -> None:
    envelope = domain_envelope(decisions=(replace(DOMAIN_DECISION, rejected_alternatives=()),))
    assert kinds(check_decision_records(envelope)) == [VIOLATION_NO_REJECTED_ALTERNATIVE]
    assert check_inherited_decisions(envelope) == []


# --- The anchor hint is retry text, so it is pinned as prose ---------------
#
# The hint is assembled from whatever rows the envelope carries, which is what
# lets one gate serve three stages — and is also what let it degrade to "a
# entity id, workflow id in 01-domain.md" with no test going red. Each case
# below pins the whole clause, not a substring of it.


def _anchor_hint(envelope) -> str:
    """The one unresolved-anchor message ``envelope`` produces."""
    (violation,) = check_decision_records(envelope)
    assert violation.kind == VIOLATION_UNRESOLVED_DECISION_ANCHOR
    return violation.message


_QUALITY_ATTRIBUTE_CLAUSE = (
    "a quality attribute is reachable only through its disposition row's id, never by its bare name"
)


def test_domain_anchor_hint_lists_every_kind_with_a_terminal_conjunction() -> None:
    envelope = domain_envelope(decisions=(replace(DOMAIN_DECISION, anchor="missing-id"),))
    message = _anchor_hint(envelope)

    assert (
        "anchor it to an entity, business rule, workflow, or decision id in 01-domain.md" in message
    )
    assert "which no row in 01-domain.md defines" in message
    # The domain stage cannot reach a disposition row, so the attribute
    # clarification would name a row kind the artifact has no access to.
    assert _QUALITY_ATTRIBUTE_CLAUSE not in message


def test_constraints_anchor_hint_names_both_artifacts_and_the_attribute_trap() -> None:
    envelope = constraints_envelope(decisions=(replace(CONSTRAINTS_DECISION, anchor="missing-id"),))
    message = _anchor_hint(envelope)

    assert "which no row in 01-domain.md or 02-constraints.md defines" in message
    assert (
        "anchor it to an entity, business rule, workflow, or decision id "
        "in 01-domain.md; or to a disposition, constraint, or decision id "
        "in 02-constraints.md" in message
    )
    assert _QUALITY_ATTRIBUTE_CLAUSE in message


def test_components_anchor_hint_names_three_artifacts_and_keeps_the_trap() -> None:
    """The attribute clause is keyed on the constraints artifact being
    reachable, not on which stage runs — the components stage resolves anchors
    against `02-constraints.md` too, so a bare attribute name is just as wrong
    there."""
    envelope = components_envelope(decisions=(replace(COMPONENTS_DECISION, anchor="missing-id"),))
    message = _anchor_hint(envelope)

    assert "which no row in 01-domain.md, 02-constraints.md, or 03-components.md defines" in message
    assert (
        "; or to a system pattern, component pattern, component, or decision "
        "id in 03-components.md" in message
    )
    assert _QUALITY_ATTRIBUTE_CLAUSE in message


def test_anchor_hint_omits_a_kind_the_artifact_declares_no_rows_of() -> None:
    """Kinds come from the rows present, so a domain with no business rules is
    never told to anchor to one — and the conjunction still lands."""
    envelope = domain_envelope(
        business_rules=(),
        workflows=(),
        decisions=(replace(DOMAIN_DECISION, anchor="missing-id"),),
    )
    message = _anchor_hint(envelope)

    assert "anchor it to an entity or decision id in 01-domain.md" in message
    assert "business rule" not in message
    assert "workflow" not in message


# --------------------------------------------------------------------------
# Non-empty gate
# --------------------------------------------------------------------------


def test_domain_with_no_entities_violates() -> None:
    envelope = domain_envelope(entities=())
    (violation,) = check_artifact_non_empty(envelope)
    assert violation.kind == VIOLATION_EMPTY_ARTIFACT
    assert violation.artifact == DOMAIN_FILENAME
    assert "entities" in violation.message


def test_domain_with_no_workflows_violates() -> None:
    envelope = domain_envelope(workflows=())
    (violation,) = check_artifact_non_empty(envelope)
    assert violation.kind == VIOLATION_EMPTY_ARTIFACT
    assert "workflows" in violation.message


def test_constraints_with_dispositions_but_no_constraint_rows_violates() -> None:
    """The degenerate artifact the retry loop drifts toward: a full
    disposition set and nothing that ranks anything."""
    envelope = constraints_envelope(dispositions=ALL_DISPOSITIONS, constraints=())
    (violation,) = check_artifact_non_empty(envelope)
    assert violation.kind == VIOLATION_EMPTY_ARTIFACT
    assert violation.artifact == CONSTRAINTS_FILENAME


def test_populated_artifacts_pass_the_non_empty_gate() -> None:
    assert check_artifact_non_empty(domain_envelope()) == []
    assert check_artifact_non_empty(constraints_envelope()) == []


# --------------------------------------------------------------------------
# Inventory-prose gate
# --------------------------------------------------------------------------


def test_every_row_id_mentioned_in_prose_passes() -> None:
    assert check_inventory_has_prose(domain_envelope()) == []
    assert check_inventory_has_prose(constraints_envelope()) == []


def test_row_id_absent_from_prose_violates() -> None:
    envelope = domain_envelope(body=prose_naming("entity-1", "entity-2", "rule-1", "workflow-1"))
    (violation,) = check_inventory_has_prose(envelope)
    assert violation.kind == VIOLATION_UNDESCRIBED_ROW
    assert violation.row_id == "decision-1"


def test_prose_gate_judges_presence_not_quality() -> None:
    """Decidable on ids: the gate never rates the prose, only whether the row
    was described at all."""
    envelope = domain_envelope(
        body="entity-1 entity-2 rule-1 workflow-1 decision-1",
    )
    assert check_inventory_has_prose(envelope) == []


def test_a_longer_id_sharing_a_prefix_does_not_discharge_a_shorter_one() -> None:
    entity_ten = EntityRow(
        id="entity-10",
        name="Refund",
        fields=(FieldRow(name="amount", type=FieldType.NUMBER),),
    )
    envelope = domain_envelope(
        entities=(ENTITY_ORDER, entity_ten),
        business_rules=(replace(RULE_ONE_CUSTOMER, entity_ids=("entity-1",)),),
        body=prose_naming("entity-10", "rule-1", "workflow-1", "decision-1"),
    )
    (violation,) = check_inventory_has_prose(envelope)
    assert violation.row_id == "entity-1"


@pytest.mark.parametrize(
    "body, described",
    [
        ("entity-1 is the order.", True),
        ("The order is `entity-1`.", True),
        ("See entity-1, then stop.", True),
        ("entity-10 is the refund.", False),
        ("entity-1-extra is something else.", False),
        ("my-entity-1 is something else.", False),
    ],
)
def test_row_id_matched_as_a_whole_token(body: str, described: bool) -> None:
    envelope = domain_envelope(
        entities=(ENTITY_ORDER,),
        business_rules=(),
        workflows=(),
        decisions=(),
        body=body,
    )
    assert (check_inventory_has_prose(envelope) == []) is described


# --------------------------------------------------------------------------
# Design-row continuity gate
# --------------------------------------------------------------------------


def test_unchanged_revision_passes_continuity() -> None:
    assert check_design_row_continuity(domain_envelope(predecessor=make_domain())) == []


def test_dropped_design_row_violates() -> None:
    envelope = domain_envelope(workflows=(), predecessor=make_domain())

    (violation,) = check_design_row_continuity(envelope)

    assert violation.kind == VIOLATION_DROPPED_DESIGN_ROW
    assert violation.row_id == "workflow-1"
    assert "workflow-1" in violation.message
    assert violation.artifact == DOMAIN_FILENAME


def test_every_dropped_row_is_reported_not_just_the_first() -> None:
    envelope = domain_envelope(business_rules=(), workflows=(), predecessor=make_domain())

    assert [v.row_id for v in check_design_row_continuity(envelope)] == [
        "rule-1",
        "workflow-1",
    ]


def test_dropped_row_with_a_cited_removal_passes() -> None:
    """The sanctioned path: the drop is declared, reasoned, and traced to the
    reviewer request that asked for it."""
    envelope = domain_envelope(
        workflows=(),
        feedback=(answered(OPEN_FEEDBACK),),
        removals=(removal("workflow-1"),),
        predecessor=make_domain(feedback=(OPEN_FEEDBACK,)),
    )

    assert check_design_row_continuity(envelope) == []


def test_store_removal_continuity_does_not_widen_local_design_row_selection() -> None:
    """A current-format store removal remains continuity evidence only.

    Stores are stage identities, not local presentation rows, so this coverage
    keeps the gate-specific enumeration separate from the local selector.
    """
    feedback = feedback_row(target=row_target(STORE_ONE.id))
    predecessor = make_components(components=(), stores=(STORE_ONE,), feedback=(feedback,))
    envelope = components_envelope(
        components=(),
        stores=(),
        feedback=(answered(feedback),),
        removals=(removal(STORE_ONE.id),),
        predecessor=predecessor,
    )

    assert check_design_row_continuity(envelope) == []
    assert "stores" not in design_row_collections(envelope.components)
    assert "stores" not in TEXT_FIELDS_BY_ROW_TYPE


def test_hosting_removal_continuity_does_not_widen_local_design_row_selection() -> None:
    """Hosting rows are continuity identities, not local presentation rows."""
    feedback = feedback_row(target=row_target(HOSTING_ROWS[0].id))
    predecessor = make_constraints(feedback=(feedback,))
    envelope = constraints_envelope(
        hosting=HOSTING_ROWS[1:],
        feedback=(answered(feedback),),
        removals=(removal(HOSTING_ROWS[0].id),),
        predecessor=predecessor,
    )

    assert check_design_row_continuity(envelope) == []
    assert "hosting" not in design_row_collections(envelope.constraints)
    assert "hosting" not in TEXT_FIELDS_BY_ROW_TYPE


def test_removal_with_a_blank_rationale_violates() -> None:
    envelope = domain_envelope(workflows=(), removals=(removal("workflow-1", rationale="   "),))

    (violation,) = check_design_row_continuity(envelope)

    assert violation.kind == VIOLATION_BLANK_REMOVAL_RATIONALE
    assert violation.row_id == "workflow-1"


def test_removal_citing_no_feedback_violates() -> None:
    envelope = domain_envelope(workflows=(), removals=(removal("workflow-1", feedback_ids=()),))

    assert kinds(check_design_row_continuity(envelope)) == [VIOLATION_UNCITED_REMOVAL]


def test_removal_naming_a_row_the_revision_still_declares_violates() -> None:
    envelope = domain_envelope(removals=(removal("workflow-1"),))

    (violation,) = check_design_row_continuity(envelope)

    assert violation.kind == VIOLATION_REMOVAL_NAMES_A_PRESENT_ROW
    assert violation.row_id == "workflow-1"


def test_removal_citing_an_unknown_feedback_id_violates() -> None:
    """Citations resolve against the predecessor's feedback: a removal is
    authorized by what the reviewer wrote, not by what the revision invents."""
    envelope = domain_envelope(
        workflows=(),
        feedback=(answered(OPEN_FEEDBACK),),
        removals=(removal("workflow-1", feedback_ids=("feedback-9",)),),
        predecessor=make_domain(feedback=(OPEN_FEEDBACK,)),
    )

    (violation,) = check_design_row_continuity(envelope)

    assert violation.kind == VIOLATION_UNRESOLVED_REMOVAL_CITATION
    assert violation.row_id == "workflow-1"
    assert "feedback-9" in violation.message


@pytest.mark.parametrize("state", [FeedbackState.AWAITING_REVIEW, FeedbackState.DEFERRED])
def test_removal_citing_a_feedback_row_that_was_not_open_violates(state) -> None:
    """Only an ``open`` row is active guidance: a deferred one the reviewer
    parked and an awaiting-review one the model already answered authorize
    nothing."""
    parked = feedback_row(state=state, proposed_response=FEEDBACK_RESPONSE)
    envelope = domain_envelope(
        workflows=(),
        feedback=(parked,),
        removals=(removal("workflow-1"),),
        predecessor=make_domain(feedback=(parked,)),
    )

    assert kinds(check_design_row_continuity(envelope)) == [VIOLATION_UNRESOLVED_REMOVAL_CITATION]


def test_new_removal_naming_a_row_the_predecessor_never_had_violates() -> None:
    envelope = domain_envelope(
        feedback=(answered(OPEN_FEEDBACK),),
        removals=(removal("entity-9"),),
        predecessor=make_domain(feedback=(OPEN_FEEDBACK,)),
    )

    (violation,) = check_design_row_continuity(envelope)

    assert violation.kind == VIOLATION_REMOVAL_WITHOUT_A_PREDECESSOR_ROW
    assert violation.row_id == "entity-9"


# A drop that landed last run, whose feedback row the reviewer has since closed
# by deleting it — the ordinary shape of the run after a sanctioned removal.
CARRIED_REMOVAL = removal("workflow-1")
PREDECESSOR_AFTER_A_REMOVAL = make_domain(workflows=(), removals=(CARRIED_REMOVAL,))


def test_a_removal_carried_from_the_predecessor_is_not_rejudged() -> None:
    """Feedback is transient, so re-judging a carried citation would turn an
    ordinary human close into a violation nobody can fix."""
    envelope = domain_envelope(
        workflows=(),
        removals=(CARRIED_REMOVAL,),
        predecessor=PREDECESSOR_AFTER_A_REMOVAL,
    )

    assert check_design_row_continuity(envelope) == []


def test_a_hand_edited_carried_removal_is_rejudged() -> None:
    """Identity is the whole record, not ``removed_id``: reworded, it meets
    both predecessor rules — its subject is no longer a predecessor row, and
    its citation names feedback the reviewer has closed."""
    envelope = domain_envelope(
        workflows=(),
        removals=(replace(CARRIED_REMOVAL, rationale="Reworded after the fact."),),
        predecessor=PREDECESSOR_AFTER_A_REMOVAL,
    )

    assert set(kinds(check_design_row_continuity(envelope))) == {
        VIOLATION_REMOVAL_WITHOUT_A_PREDECESSOR_ROW,
        VIOLATION_UNRESOLVED_REMOVAL_CITATION,
    }


@pytest.mark.parametrize("cited", [True, False], ids=["cited-removal", "no-removal"])
def test_removing_a_row_a_settled_decision_anchors_to_violates(cited: bool) -> None:
    """The transitive block: gate 3 pins the anchor, so a cited removal is not
    enough, and the message names the un-settle rather than leaving the stage
    to oscillate with ``check_decision_records``' re-anchor advice.

    The uncovered drop takes the same arm on purpose — telling it to add a
    cited removal would spend an attempt discovering the block."""
    pinned = replace(SETTLED_DOMAIN_DECISION, anchor="workflow-1")
    envelope = domain_envelope(
        workflows=(),
        decisions=(pinned,),
        feedback=(answered(OPEN_FEEDBACK),),
        removals=(removal("workflow-1"),) if cited else (),
        predecessor=make_domain(decisions=(pinned,), feedback=(OPEN_FEEDBACK,)),
    )

    (violation,) = check_design_row_continuity(envelope)

    assert violation.kind == VIOLATION_DROPPED_DESIGN_ROW
    assert violation.row_id == "workflow-1"
    assert "decision-1" in violation.message
    assert DecisionStatus.PENDING.value in violation.message
    # Never the ordinary drop's remedy, which this row may not take.
    assert "record its removal" not in violation.message


def test_a_dropped_settled_decision_is_reported_once_not_by_both_gates() -> None:
    """One defect, one correction: continuity would offer the removal path the
    settled-choice gate forbids in the same prompt."""
    envelope = domain_envelope(
        decisions=(), predecessor=make_domain(decisions=(SETTLED_DOMAIN_DECISION,))
    )

    assert check_design_row_continuity(envelope) == []
    assert kinds(check_settled_decisions(envelope)) == [VIOLATION_DROPPED_SETTLED_DECISION]


def test_predecessor_derived_continuity_is_inert_without_a_predecessor() -> None:
    assert check_design_row_continuity(domain_envelope(workflows=())) == []


# --------------------------------------------------------------------------
# Feedback-integrity gate
# --------------------------------------------------------------------------


def test_carried_feedback_answered_with_a_response_passes() -> None:
    """The headline flow: a row-targeted request answered, beside one the
    reviewer parked and the revision left alone."""
    parked = feedback_row(
        "feedback-2",
        target=row_target("entity-2"),
        request="Leave the customer entity for later.",
        state=FeedbackState.DEFERRED,
        proposed_response="Deferred at the reviewer's request.",
    )
    asked = feedback_row(target=row_target("entity-1"))
    envelope = domain_envelope(
        feedback=(answered(asked), parked),
        predecessor=make_domain(feedback=(asked, parked)),
    )

    assert check_feedback_integrity(envelope) == []


def test_deleted_feedback_row_violates() -> None:
    """Only the reviewer closes feedback, by deleting the row before a run."""
    envelope = domain_envelope(predecessor=make_domain(feedback=(OPEN_FEEDBACK,)))

    (violation,) = check_feedback_integrity(envelope)

    assert violation.kind == VIOLATION_DROPPED_FEEDBACK
    assert violation.row_id == "feedback-1"


def test_altered_request_violates() -> None:
    rewritten = replace(answered(OPEN_FEEDBACK), request="Something the reviewer never wrote.")
    envelope = domain_envelope(
        feedback=(rewritten,), predecessor=make_domain(feedback=(OPEN_FEEDBACK,))
    )

    (violation,) = check_feedback_integrity(envelope)

    assert violation.kind == VIOLATION_ALTERED_FEEDBACK_SOURCE
    assert "request" in violation.message


def test_altered_target_violates() -> None:
    retargeted = replace(answered(OPEN_FEEDBACK), target=row_target("entity-1"))
    envelope = domain_envelope(
        feedback=(retargeted,), predecessor=make_domain(feedback=(OPEN_FEEDBACK,))
    )

    (violation,) = check_feedback_integrity(envelope)

    assert violation.kind == VIOLATION_ALTERED_FEEDBACK_SOURCE
    assert "target" in violation.message


def test_trailing_whitespace_in_a_request_is_not_an_alteration() -> None:
    """A ``request: |`` block round-trips through the renderer as a scalar
    carrying a trailing newline; the same visible words are the same request."""
    written = feedback_row(request="Split the order entity.\nFulfilment is its own.\n")
    re_emitted = replace(
        answered(written), request="Split the order entity.   \nFulfilment is its own."
    )
    envelope = domain_envelope(feedback=(re_emitted,), predecessor=make_domain(feedback=(written,)))

    assert check_feedback_integrity(envelope) == []


def test_open_feedback_left_open_violates() -> None:
    """Every active item owes a response."""
    envelope = domain_envelope(
        feedback=(OPEN_FEEDBACK,), predecessor=make_domain(feedback=(OPEN_FEEDBACK,))
    )

    (violation,) = check_feedback_integrity(envelope)

    assert violation.kind == VIOLATION_DISALLOWED_FEEDBACK_STATE
    assert violation.row_id == "feedback-1"
    assert FeedbackState.AWAITING_REVIEW.value in violation.message


def test_open_becoming_awaiting_review_passes() -> None:
    """The one allowed move — and the response it carries is newly written, so
    the carried-response rule keys on the *predecessor's* state, not this one."""
    envelope = domain_envelope(
        feedback=(answered(OPEN_FEEDBACK),),
        predecessor=make_domain(feedback=(OPEN_FEEDBACK,)),
    )

    assert check_feedback_integrity(envelope) == []


def test_open_becoming_deferred_violates() -> None:
    """Deferring is the reviewer's, done in the editor before the run."""
    deferred = replace(OPEN_FEEDBACK, state=FeedbackState.DEFERRED)
    envelope = domain_envelope(
        feedback=(deferred,), predecessor=make_domain(feedback=(OPEN_FEEDBACK,))
    )

    assert kinds(check_feedback_integrity(envelope)) == [VIOLATION_DISALLOWED_FEEDBACK_STATE]


def test_awaiting_review_reverted_to_open_violates() -> None:
    """Reopening is the reviewer's too."""
    offered = answered(OPEN_FEEDBACK)
    envelope = domain_envelope(
        feedback=(replace(offered, state=FeedbackState.OPEN),),
        predecessor=make_domain(feedback=(offered,)),
    )

    assert kinds(check_feedback_integrity(envelope)) == [VIOLATION_DISALLOWED_FEEDBACK_STATE]


def test_awaiting_review_response_rewritten_violates() -> None:
    offered = answered(OPEN_FEEDBACK)
    envelope = domain_envelope(
        feedback=(replace(offered, proposed_response="A different answer."),),
        predecessor=make_domain(feedback=(offered,)),
    )

    (violation,) = check_feedback_integrity(envelope)

    assert violation.kind == VIOLATION_ALTERED_CARRIED_RESPONSE
    assert violation.row_id == "feedback-1"


DEFERRED_FEEDBACK = feedback_row(
    state=FeedbackState.DEFERRED, proposed_response="Parked by the reviewer."
)


def test_deferred_row_carried_unchanged_passes() -> None:
    envelope = domain_envelope(
        feedback=(DEFERRED_FEEDBACK,),
        predecessor=make_domain(feedback=(DEFERRED_FEEDBACK,)),
    )

    assert check_feedback_integrity(envelope) == []


def test_deferred_row_altered_violates() -> None:
    """A parked row is not active guidance, so any edit to it is unrequested."""
    envelope = domain_envelope(
        feedback=(replace(DEFERRED_FEEDBACK, proposed_response="Answered anyway."),),
        predecessor=make_domain(feedback=(DEFERRED_FEEDBACK,)),
    )

    assert kinds(check_feedback_integrity(envelope)) == [VIOLATION_ALTERED_CARRIED_RESPONSE]


def test_duplicate_feedback_ids_violate_once_per_id() -> None:
    envelope = domain_envelope(
        feedback=(
            OPEN_FEEDBACK,
            replace(OPEN_FEEDBACK, request="A second request."),
            replace(OPEN_FEEDBACK, request="A third request."),
        )
    )

    violations = check_feedback_integrity(envelope)

    assert kinds(violations) == [VIOLATION_DUPLICATE_FEEDBACK_ID]
    assert violations[0].row_id == "feedback-1"
    assert "3 rows" in violations[0].message


def test_a_feedback_id_may_equal_a_design_row_id() -> None:
    """Two namespaces: a removal's citations resolve against feedback rows and
    an anchor against design rows, so nothing resolves against their union."""
    collides = feedback_row("entity-1")
    envelope = domain_envelope(
        feedback=(answered(collides),), predecessor=make_domain(feedback=(collides,))
    )

    assert check_feedback_integrity(envelope) == []
    assert check_duplicate_row_ids(envelope) == []


def test_row_target_naming_a_predecessor_row_resolves() -> None:
    envelope = domain_envelope(
        feedback=(feedback_row("feedback-2", target=row_target("entity-1")),),
        predecessor=make_domain(),
    )

    assert check_feedback_integrity(envelope) == []


def test_row_target_may_name_a_row_the_revision_removed() -> None:
    """The case predecessor-scoped resolution exists for: feedback asks for the
    removal of the row it names, and the revision performs it."""
    envelope = domain_envelope(
        workflows=(),
        feedback=(
            answered(OPEN_FEEDBACK),
            feedback_row("feedback-2", target=row_target("workflow-1")),
        ),
        removals=(removal("workflow-1"),),
        predecessor=make_domain(feedback=(OPEN_FEEDBACK,)),
    )

    assert check_feedback_integrity(envelope) == []


def test_row_target_may_name_a_row_the_predecessor_already_removed() -> None:
    """The predecessor's ``removed_id``s are in the resolvable set, so a run
    after a sanctioned drop does not deadlock on the row that asked for it."""
    envelope = domain_envelope(
        workflows=(),
        feedback=(feedback_row("feedback-2", target=row_target("workflow-1")),),
        removals=(CARRIED_REMOVAL,),
        predecessor=PREDECESSOR_AFTER_A_REMOVAL,
    )

    assert check_feedback_integrity(envelope) == []


def test_a_carried_feedback_row_with_a_dangling_target_violates() -> None:
    """A carried reviewer request must still name predecessor evidence."""
    dangling = feedback_row(target=row_target("workflow-1"))
    envelope = domain_envelope(
        workflows=(),
        feedback=(answered(dangling),),
        predecessor=make_domain(workflows=(), feedback=(dangling,)),
    )

    assert kinds(check_feedback_integrity(envelope)) == [VIOLATION_UNRESOLVED_FEEDBACK_TARGET]


def test_row_target_naming_an_id_the_predecessor_never_had_violates() -> None:
    candidate_target = EntityRow("entity-9", "Candidate-only", ())
    envelope = domain_envelope(
        entities=(ENTITY_ORDER, candidate_target),
        feedback=(feedback_row("feedback-2", target=row_target(candidate_target.id)),),
        predecessor=make_domain(),
    )

    (violation,) = check_feedback_integrity(envelope)

    assert violation.kind == VIOLATION_UNRESOLVED_FEEDBACK_TARGET
    assert violation.row_id == "feedback-2"
    assert candidate_target.id in violation.message


def test_artifact_target_needs_no_row_id() -> None:
    envelope = domain_envelope(feedback=(feedback_row("feedback-2"),), predecessor=make_domain())

    assert check_feedback_integrity(envelope) == []


def test_response_text_is_never_judged() -> None:
    """Whether a response answers the request, how long it is, and whether it
    merely repeats the request back are all outside what a gate can see."""
    parroted = answered(OPEN_FEEDBACK, response=OPEN_FEEDBACK.request)
    envelope = domain_envelope(
        feedback=(parroted,), predecessor=make_domain(feedback=(OPEN_FEEDBACK,))
    )

    assert check_feedback_integrity(envelope) == []


def test_feedback_integrity_is_inert_without_a_predecessor() -> None:
    envelope = domain_envelope(
        feedback=(feedback_row(target=row_target("entity-9")),),
    )

    assert check_feedback_integrity(envelope) == []


SENTINEL_REQUEST = "SENTINELREQUEST the reviewer typed into the artifact"
SENTINEL_RESPONSE = "SENTINELRESPONSE the model offered back"


def test_no_violation_message_quotes_feedback_or_response_text() -> None:
    """Messages are written verbatim into the run log, which must carry no
    feedback or response text — so an alteration names the row and the field,
    never the words expected back."""
    asked = feedback_row(request=SENTINEL_REQUEST)
    offered = feedback_row(
        "feedback-2",
        request=SENTINEL_REQUEST,
        state=FeedbackState.AWAITING_REVIEW,
        proposed_response=SENTINEL_RESPONSE,
    )
    parked = feedback_row("feedback-3", request=SENTINEL_REQUEST, state=FeedbackState.DEFERRED)
    envelope = domain_envelope(
        workflows=(),
        decisions=(),
        feedback=(
            replace(asked, request="Rewritten by the model."),
            replace(offered, proposed_response="Rewritten by the model."),
            feedback_row("feedback-4", target=row_target("entity-9"), request=SENTINEL_REQUEST),
        ),
        removals=(removal("workflow-1", feedback_ids=("feedback-3",)),),
        predecessor=make_domain(
            decisions=(SETTLED_DOMAIN_DECISION,), feedback=(asked, offered, parked)
        ),
    )

    violations = run_domain_gates(envelope)

    assert violations
    for violation in violations:
        assert SENTINEL_REQUEST not in violation.message
        assert SENTINEL_RESPONSE not in violation.message


# --------------------------------------------------------------------------
# Settled-choice gate
# --------------------------------------------------------------------------


def _settled_revision(**changes) -> ArtifactEnvelope:
    """A revision carrying the settled decision with ``changes`` applied."""
    return domain_envelope(
        decisions=(replace(SETTLED_DOMAIN_DECISION, **changes),),
        predecessor=make_domain(decisions=(SETTLED_DOMAIN_DECISION,)),
    )


def test_settled_decision_carried_unchanged_passes() -> None:
    assert check_settled_decisions(_settled_revision()) == []


def test_changed_chosen_option_on_a_settled_decision_violates() -> None:
    envelope = _settled_revision(chosen_option="A separate cart entity after all.")

    (violation,) = check_settled_decisions(envelope)

    assert violation.kind == VIOLATION_ALTERED_SETTLED_DECISION
    assert violation.row_id == "decision-1"
    assert "chosen_option" in violation.message


def test_changed_anchor_on_a_settled_decision_violates() -> None:
    envelope = _settled_revision(anchor="entity-2")

    (violation,) = check_settled_decisions(envelope)

    assert violation.kind == VIOLATION_ALTERED_SETTLED_DECISION
    assert "anchor" in violation.message


def test_settled_becoming_pending_violates() -> None:
    """Un-settling is the reviewer's move."""
    envelope = _settled_revision(status=DecisionStatus.PENDING)

    (violation,) = check_settled_decisions(envelope)

    assert violation.kind == VIOLATION_ALTERED_SETTLED_DECISION
    assert "status" in violation.message


def test_check_settled_decisions_refuses_drift_on_a_row_the_settlement_route_settled() -> None:
    """``settle_pending_decision`` is the same artifact-building primitive every
    decision-settlement lineage's writer calls to produce
    ``DecisionSettlementCandidate.settled_artifact``. This gate must protect
    that route's actual output, not only a hand-authored already-settled row
    (the other cases in this section all build ``SETTLED_DOMAIN_DECISION`` by
    hand via ``replace``)."""
    settled = settle_pending_decision(make_domain(), decision_id=DOMAIN_DECISION.id)
    settled_row = next(row for row in settled.decisions if row.id == DOMAIN_DECISION.id)
    assert settled_row.status is DecisionStatus.SETTLED

    envelope = domain_envelope(
        decisions=(replace(settled_row, status=DecisionStatus.PENDING),),
        predecessor=settled,
    )

    (violation,) = check_settled_decisions(envelope)

    assert violation.kind == VIOLATION_ALTERED_SETTLED_DECISION
    assert violation.row_id == DOMAIN_DECISION.id
    assert "status" in violation.message


def test_settled_decision_removed_violates_even_with_a_cited_removal() -> None:
    envelope = domain_envelope(
        decisions=(),
        feedback=(answered(OPEN_FEEDBACK),),
        removals=(removal("decision-1"),),
        predecessor=make_domain(decisions=(SETTLED_DOMAIN_DECISION,), feedback=(OPEN_FEEDBACK,)),
    )

    (violation,) = check_settled_decisions(envelope)

    assert violation.kind == VIOLATION_DROPPED_SETTLED_DECISION
    assert violation.row_id == "decision-1"


def test_settled_decision_rationale_may_change() -> None:
    """Whether a reworded rationale means the same thing is not decidable
    here, and an equality check on prose would fail on formatting alone."""
    envelope = _settled_revision(rationale="One aggregate keeps checkout atomic!")

    assert check_settled_decisions(envelope) == []


def test_settled_decision_alternatives_may_change() -> None:
    envelope = _settled_revision(
        rejected_alternatives=(
            RejectedAlternative(option="A cart service.", reason="Another hop."),
        )
    )

    assert check_settled_decisions(envelope) == []


def test_pending_predecessor_decision_is_unpinned() -> None:
    """Only a settled choice is pinned: a pending one is exactly what the
    review channel exists to let a revision revisit.

    Settling it is deliberately not a violation either — the reviewer's own
    request may be what decided the question — so the fence-authority question
    is reported instead, by ``RoadmapResult.newly_settled_decisions``.
    """
    envelope = domain_envelope(
        decisions=(
            replace(
                DOMAIN_DECISION,
                chosen_option="A separate cart entity after all.",
                anchor="entity-2",
                status=DecisionStatus.SETTLED,
            ),
        ),
        predecessor=make_domain(),
    )

    assert check_settled_decisions(envelope) == []


@pytest.mark.parametrize(
    "envelope",
    [
        domain_envelope(
            decisions=(), predecessor=make_domain(decisions=(SETTLED_DOMAIN_DECISION,))
        ),
        domain_envelope(
            decisions=(replace(SETTLED_DOMAIN_DECISION, anchor="entity-2"),),
            predecessor=make_domain(decisions=(SETTLED_DOMAIN_DECISION,)),
        ),
    ],
    ids=["dropped", "altered"],
)
def test_settled_message_names_the_un_settle_action(envelope) -> None:
    """The model cannot un-settle a decision itself, so a message stating only
    the rule would leave it with no move and spend the whole retry budget."""
    (violation,) = check_settled_decisions(envelope)

    assert DecisionStatus.PENDING.value in violation.message
    assert "proposed_response" in violation.message


def test_settled_finality_is_inert_without_a_predecessor() -> None:
    assert check_settled_decisions(domain_envelope(decisions=())) == []


# --------------------------------------------------------------------------
# Gate sets and ordering
# --------------------------------------------------------------------------


# The gates that shipped before the revision gates, in declared order — the
# list a no-predecessor envelope must still produce exactly.
_DOMAIN_KINDS_WITHOUT_A_PREDECESSOR = [
    VIOLATION_EMPTY_ARTIFACT,
    VIOLATION_DUPLICATE_ROW_ID,
    VIOLATION_ENTITY_WITHOUT_FIELDS,
    VIOLATION_UNDEFINED_ENTITY_REFERENCE,
    VIOLATION_NO_REJECTED_ALTERNATIVE,
    VIOLATION_UNDESCRIBED_ROW,
]

_CONSTRAINTS_KINDS_WITHOUT_A_PREDECESSOR = {
    VIOLATION_DUPLICATE_ROW_ID,
    VIOLATION_UNKNOWN_HOSTING_FACET,
    VIOLATION_UNKNOWN_HOSTING_VALUE,
    VIOLATION_HOSTING_TOPOLOGY_COHERENCE,
    VIOLATION_UNDISPOSED_ATTRIBUTE,
    VIOLATION_UNRESOLVED_CONSTRAINT_ANCHOR,
    VIOLATION_BLANK_RATIONALE,
    VIOLATION_UNDESCRIBED_ROW,
}

# A settled decision the revision drops, so the settled-choice gate fires once.
PINNED_DOMAIN_DECISION = replace(SETTLED_DOMAIN_DECISION, id="decision-9")


def _domain_breaking_every_gate() -> ArtifactEnvelope:
    # Each revision gate is tripped by a *predecessor-derived* rule alone, so
    # stripping the predecessor restores exactly the pre-revision kind list:
    # the predecessor declares one row the revision drops, holds the open
    # feedback row the revision leaves unanswered, and settles a decision the
    # revision does not carry.
    predecessor = make_domain(
        entities=(replace(ENTITY_ORDER, fields=(FieldRow(name="total", type=FieldType.NUMBER),)),),
        decisions=(DOMAIN_DECISION, PINNED_DOMAIN_DECISION),
        feedback=(OPEN_FEEDBACK,),
    )
    return domain_envelope(
        # One violation per gate, so the count assertion below stays honest:
        # the first entity's fields resolve (no stray reference), the second
        # has none at all, and the duplicate id is what trips the id gate.
        entities=(
            replace(
                ENTITY_ORDER,
                fields=(FieldRow(name="total", type=FieldType.NUMBER),),
            ),
            EntityRow(id="entity-1", name="Order again", fields=()),
        ),
        business_rules=(replace(RULE_ONE_CUSTOMER, entity_ids=("entity-9",)),),
        workflows=(),
        decisions=(replace(DOMAIN_DECISION, rejected_alternatives=()),),
        feedback=(OPEN_FEEDBACK,),
        body=prose_naming("entity-1", "rule-1"),
        predecessor=predecessor,
    )


def test_domain_gate_set_runs_every_domain_gate() -> None:
    violations = run_domain_gates(_domain_breaking_every_gate())
    assert set(kinds(violations)) == {
        *_DOMAIN_KINDS_WITHOUT_A_PREDECESSOR,
        VIOLATION_DROPPED_DESIGN_ROW,
        VIOLATION_DISALLOWED_FEEDBACK_STATE,
        VIOLATION_DROPPED_SETTLED_DECISION,
    }
    # The inherited-source gate is intentionally inert on this legacy envelope.
    assert len(violations) == len(DOMAIN_GATES) - 1


PINNED_CONSTRAINTS_DECISION = replace(CONSTRAINTS_DECISION, id="decision-9")


def _constraints_breaking_every_gate_but_non_empty() -> ArtifactEnvelope:
    # The constraint's id collides with a disposition row's, so one artifact
    # trips the duplicate, totality, anchor, decision, and prose gates at once.
    kept = ALL_DISPOSITIONS[:-1]
    colliding = ConstraintRow(
        id=kept[0].id,
        statement="Checkout completes within 300ms at the median.",
        attribute=PRIORITIZED_ATTRIBUTE,
        anchor_ids=("entity-9",),
    )
    hosting = (
        replace(HOSTING_ROWS[0], value="vendor-serverless"),
        replace(HOSTING_ROWS[1], value="bridge"),
        HOSTING_ROWS[2],
        HostingRow(id="hosting-platform", facet="platform", value="custom"),
    )
    # As on the domain side, the three revision gates are tripped only by
    # predecessor-derived rules: the dropped disposition row, the unanswered
    # open feedback, and the settled decision the revision does not carry.
    # ``decision-2`` is settled in both and differs only in its rationale,
    # which the settled-choice gate deliberately does not compare.
    predecessor = make_constraints(
        dispositions=ALL_DISPOSITIONS,
        constraints=(colliding,),
        decisions=(CONSTRAINTS_DECISION, PINNED_CONSTRAINTS_DECISION),
        feedback=(OPEN_FEEDBACK,),
    )
    return constraints_envelope(
        hosting=hosting,
        dispositions=kept,
        constraints=(colliding,),
        decisions=(replace(CONSTRAINTS_DECISION, rationale="  "),),
        feedback=(OPEN_FEEDBACK,),
        body=prose_naming(*(row.id for row in kept)),
        predecessor=predecessor,
    )


def test_constraints_gate_set_runs_every_constraints_gate() -> None:
    """Two envelopes, because an artifact cannot both carry a broken
    constraint row and carry none at all."""
    populated = run_constraints_gates(_constraints_breaking_every_gate_but_non_empty())
    emptied = run_constraints_gates(constraints_envelope(constraints=()))
    assert set(kinds(populated)) == {
        *_CONSTRAINTS_KINDS_WITHOUT_A_PREDECESSOR,
        VIOLATION_DROPPED_DESIGN_ROW,
        VIOLATION_DISALLOWED_FEEDBACK_STATE,
        VIOLATION_DROPPED_SETTLED_DECISION,
    }
    assert VIOLATION_EMPTY_ARTIFACT in kinds(emptied)
    # Two gates are intentionally inert on this legacy envelope: the inherited-source
    # gate, and stack totality, which binds only an artifact that carries the
    # collection (this one has none).
    assert len(set(kinds(populated)) | {VIOLATION_EMPTY_ARTIFACT}) == len(CONSTRAINTS_GATES) - 2


def test_both_gate_sets_share_one_call_shape() -> None:
    """The stage table holds a gate set as a value, so a differing signature
    would put knowledge of which gate needs what back into the orchestrator."""
    assert inspect.signature(run_domain_gates) == inspect.signature(run_constraints_gates)
    assert inspect.signature(run_domain_gates) == inspect.signature(run_components_gates)
    assert run_domain_gates(domain_envelope()) == []
    assert run_constraints_gates(constraints_envelope()) == []
    assert run_components_gates(components_envelope()) == []


def test_violation_order_is_stable() -> None:
    domain = _domain_breaking_every_gate()
    constraints = _constraints_breaking_every_gate_but_non_empty()
    assert run_domain_gates(domain) == run_domain_gates(domain)
    assert run_constraints_gates(constraints) == run_constraints_gates(constraints)
    # Gate order first, then row order as parsed. The revision gates are
    # appended, so the kinds that shipped before them keep their sequence.
    assert kinds(run_domain_gates(domain)) == [
        *_DOMAIN_KINDS_WITHOUT_A_PREDECESSOR,
        VIOLATION_DROPPED_DESIGN_ROW,
        VIOLATION_DISALLOWED_FEEDBACK_STATE,
        VIOLATION_DROPPED_SETTLED_DECISION,
    ]


def test_clean_artifacts_yield_no_violations() -> None:
    assert run_domain_gates(domain_envelope()) == []
    assert run_constraints_gates(constraints_envelope()) == []


def test_new_gates_are_inert_on_a_first_run() -> None:
    """The main regression guard. A first run has no predecessor, and the
    below-stage re-gating pass builds its envelopes without one, so both sets
    return exactly the violations they returned before the revision gates."""
    domain = replace(_domain_breaking_every_gate(), predecessor=None)
    constraints = replace(_constraints_breaking_every_gate_but_non_empty(), predecessor=None)

    assert kinds(run_domain_gates(domain)) == _DOMAIN_KINDS_WITHOUT_A_PREDECESSOR
    assert (
        set(kinds(run_constraints_gates(constraints))) == _CONSTRAINTS_KINDS_WITHOUT_A_PREDECESSOR
    )


def test_clean_revision_yields_no_violations() -> None:
    """A revision that keeps every row, the reviewer's words, and every settled
    commitment, and answers the one open request."""
    domain = domain_envelope(
        feedback=(answered(OPEN_FEEDBACK),),
        predecessor=make_domain(feedback=(OPEN_FEEDBACK,)),
    )
    constraints = constraints_envelope(
        feedback=(answered(OPEN_FEEDBACK),),
        predecessor=make_constraints(feedback=(OPEN_FEEDBACK,)),
    )

    assert run_domain_gates(domain) == []
    assert run_constraints_gates(constraints) == []


def test_predecessor_defaults_to_none() -> None:
    """What keeps ``roadmap.py``'s ``_build_envelope`` — which fills only the
    ``artifact_key``-named slots — compiling untouched."""
    assert ArtifactEnvelope(domain=make_domain()).predecessor is None
    assert (
        ArtifactEnvelope(domain=make_domain(), constraints=make_constraints()).predecessor is None
    )


def test_feedback_and_removal_rows_stay_out_of_the_prose_and_duplicate_id_gates() -> None:
    """Review rows are not design rows: demanding prose for a reviewer's
    request, or folding feedback ids into the design-row namespace, would make
    the two design-row gates report on rows the model does not author."""
    envelope = domain_envelope(
        feedback=(feedback_row(), feedback_row("entity-1")),
        removals=(removal("entity-9"),),
    )

    assert check_inventory_has_prose(envelope) == []
    assert check_duplicate_row_ids(envelope) == []


@pytest.mark.parametrize(
    "gate, envelope, expects_row_ids",
    [
        (
            check_entity_references,
            domain_envelope(workflows=(replace(WORKFLOW_PLACE_ORDER, entity_ids=("entity-9",)),)),
            True,
        ),
        (
            check_duplicate_row_ids,
            domain_envelope(entities=(ENTITY_ORDER, replace(ENTITY_CUSTOMER, id="entity-1"))),
            True,
        ),
        (
            check_attribute_totality,
            constraints_envelope(
                constraints=(replace(CONSTRAINT_LATENCY, attribute="throughput"),)
            ),
            True,
        ),
        (
            check_constraint_anchors,
            constraints_envelope(
                constraints=(replace(CONSTRAINT_LATENCY, anchor_ids=("entity-9",)),)
            ),
            True,
        ),
        (
            check_decision_records,
            domain_envelope(decisions=(replace(DOMAIN_DECISION, rationale=""),)),
            True,
        ),
        (
            check_inventory_has_prose,
            domain_envelope(body="# Nothing described here"),
            True,
        ),
        (check_artifact_non_empty, domain_envelope(entities=()), False),
        (
            check_design_row_continuity,
            domain_envelope(workflows=(), predecessor=make_domain()),
            True,
        ),
        (
            check_feedback_integrity,
            domain_envelope(
                feedback=(OPEN_FEEDBACK,),
                predecessor=make_domain(feedback=(OPEN_FEEDBACK,)),
            ),
            True,
        ),
        (
            check_settled_decisions,
            domain_envelope(
                decisions=(),
                predecessor=make_domain(decisions=(SETTLED_DOMAIN_DECISION,)),
            ),
            True,
        ),
    ],
    ids=[
        "entity-references",
        "duplicate-row-ids",
        "attribute-totality",
        "constraint-anchors",
        "decision-records",
        "inventory-prose",
        "non-empty",
        "design-row-continuity",
        "feedback-integrity",
        "settled-decisions",
    ],
)
def test_every_violation_names_its_row_id(gate, envelope, expects_row_ids) -> None:
    """Every message survives being quoted into a retry prompt: it names the
    artifact, and the offending row's id whenever there is a row. The
    non-empty gate's defect is an *absent* row set, so it names the artifact
    alone."""
    violations = gate(envelope)
    assert violations
    for violation in violations:
        assert violation.artifact in violation.message
        if expects_row_ids:
            assert violation.row_id
            assert violation.row_id in violation.message
        else:
            assert violation.row_id is None


CONFORMING_DOMAIN_TEXT = """---
entities:
- id: entity-1
  name: Order
  fields:
  - name: placed_at
    type: timestamp
  - name: customer
    type: reference
    entity_id: entity-2
- id: entity-2
  name: Customer
  fields:
  - name: email
    type: text
business_rules:
- id: rule-1
  statement: An order belongs to exactly one customer.
  entity_ids:
  - entity-1
  - entity-2
workflows:
- id: workflow-1
  name: Place an order
  entity_ids:
  - entity-1
decisions:
- id: decision-1
  chosen_option: Keep the cart inside the order aggregate.
  rejected_alternatives:
  - option: A separate cart entity.
    reason: Two lifecycles to reconcile for no downstream reader.
  rationale: One aggregate keeps checkout atomic.
  anchor: entity-1
  status: pending
---
# Domain

entity-1 is the order a customer places; entity-2 is that customer.

rule-1 binds the two. workflow-1 walks an order from cart to payment.

decision-1 records why the cart lives inside the order aggregate.
"""

CONFORMING_CONSTRAINTS_TEXT = """---
hosting:
- id: hosting-compute
  facet: compute
  value: per-request
- id: hosting-model
  facet: model
  value: pool
- id: hosting-topology
  facet: topology
  value: single-unit
dispositions:
- id: attribute-performance
  attribute: performance
  disposition: prioritized
- id: attribute-scalability
  attribute: scalability
  disposition: traded-away
- id: attribute-security
  attribute: security
  disposition: prioritized
- id: attribute-availability
  attribute: availability
  disposition: traded-away
- id: attribute-maintainability
  attribute: maintainability
  disposition: prioritized
- id: attribute-fault-tolerance
  attribute: fault-tolerance
  disposition: not-load-bearing
- id: attribute-reliability
  attribute: reliability
  disposition: not-load-bearing
constraints:
- id: constraint-1
  statement: Checkout completes within 300ms at the median.
  attribute: performance
  anchor_ids:
  - entity-1
  - workflow-1
decisions:
- id: decision-2
  chosen_option: Spend replication headroom to keep checkout fast.
  rejected_alternatives:
  - option: Multi-region replication.
    reason: Adds write latency to the one path that cannot afford it.
  rationale: A slow checkout loses the order outright.
  anchor: attribute-performance
  status: settled
---
# Constraints

attribute-performance and attribute-security are what this roadmap spends on.

attribute-scalability and attribute-availability are traded away for them.

attribute-maintainability stays prioritized so the tradeoffs can be revisited.

attribute-fault-tolerance and attribute-reliability are not load-bearing here.

constraint-1 holds checkout latency down. decision-2 says what that cost.
"""

CONFORMING_COMPONENTS_TEXT = """---
system_patterns:
- id: system-pattern-1
  name: Layered checkout
  statement: Checkout flows through a dedicated service boundary.
component_patterns:
- id: component-pattern-1
  name: Aggregate root
  statement: Each component owns one consistency boundary.
stores:
- id: store-1
  category: relational
  sharing: pool
components:
- id: component-1
  name: Order fulfilment
  entity_ids:
  - entity-1
  - entity-2
  pattern_ids:
  - system-pattern-1
  - component-pattern-1
  constraint_ids:
  - constraint-1
  store_ids:
  - store-1
decisions:
- id: decision-3
  chosen_option: Split fulfilment from the order aggregate.
  rejected_alternatives:
  - option: Keep fulfilment inside the order entity.
    reason: Two lifecycles in one aggregate complicate checkout.
  rationale: Fulfilment scales on a different axis than checkout.
  anchor: constraint-1
  status: pending
---
# Components

system-pattern-1 spans checkout. component-pattern-1 bounds each slice.

component-1 owns entity-1 and entity-2 and discharges constraint-1.

decision-3 records why fulfilment is its own component.
"""

CONFORMING_PLANS_TEXT = """---
plans:
- id: plan-order-core
  title: Order fulfilment plan
  intent: Make fulfilment independently operable after checkout completes.
  non_goals:
  - Changing checkout's order creation flow.
  disposition: keep
  component_ids:
  - component-1
  draft_seed_path: seeds/order-core.md
  sizing_rationale: One component maps to one plan.
ordering:
- plan_id: plan-order-core
  depends_on: []
  assumption_targets: []
assumptions:
- id: assumption-1
  statement: Checkout completes before fulfilment starts.
  consuming_plan_ids:
  - plan-order-core
decisions:
- id: decision-4
  chosen_option: Keep fulfilment as a separate plan.
  rejected_alternatives:
  - option: Merge into checkout.
    reason: Different scaling axes.
  rationale: Fulfilment scales independently.
  anchor: plan-order-core
  status: pending
---
# Plans

plan-order-core covers component-1 for fulfilment.

assumption-1 says checkout stays ahead of fulfilment.

decision-4 records why fulfilment is its own plan.
"""


def test_gates_accept_a_parsed_conforming_artifact() -> None:
    """The one test that crosses the module boundary: parse conforming text
    with step 1's parser and run both gate sets over the result."""
    domain = parse_domain_artifact(CONFORMING_DOMAIN_TEXT)
    constraints = parse_constraints_artifact(CONFORMING_CONSTRAINTS_TEXT)
    assert run_domain_gates(ArtifactEnvelope(domain=domain)) == []
    assert run_constraints_gates(ArtifactEnvelope(domain=domain, constraints=constraints)) == []


def test_gates_accept_a_parsed_conforming_components_artifact() -> None:
    """The third module-boundary case: parse conforming components text with
    upstream domain and constraints and run the components gate set."""
    domain = parse_domain_artifact(CONFORMING_DOMAIN_TEXT)
    constraints = parse_constraints_artifact(CONFORMING_CONSTRAINTS_TEXT)
    components = parse_components_artifact(CONFORMING_COMPONENTS_TEXT)
    assert (
        run_components_gates(
            ArtifactEnvelope(domain=domain, constraints=constraints, components=components)
        )
        == []
    )


def test_gates_accept_a_parsed_conforming_plans_artifact() -> None:
    """The fourth module-boundary case parses a conforming plans artifact."""
    domain = parse_domain_artifact(CONFORMING_DOMAIN_TEXT)
    constraints = parse_constraints_artifact(CONFORMING_CONSTRAINTS_TEXT)
    components = parse_components_artifact(CONFORMING_COMPONENTS_TEXT)
    plans = parse_plans_artifact(CONFORMING_PLANS_TEXT)
    assert (
        run_plans_gates(
            ArtifactEnvelope(
                domain=domain,
                constraints=constraints,
                components=components,
                plans=plans,
            )
        )
        == []
    )


# The same conforming artifacts carrying one reviewer request, before and after
# the revision answers it. Spliced in ahead of the closing fence rather than
# re-spelled, so predecessor and revision carry byte-identical request text.
_DOMAIN_FEEDBACK = """feedback:
- id: feedback-1
  target:
    kind: row
    row_id: entity-2
  request: Say what a customer record leaves out.
  state: {state}
"""
_DOMAIN_RESPONSE = "  proposed_response: entity-2 holds contact details only.\n"

_CONSTRAINTS_FEEDBACK = """feedback:
- id: feedback-1
  target:
    kind: artifact
  request: Say why maintainability outranks reliability here.
  state: {state}
"""
_CONSTRAINTS_RESPONSE = "  proposed_response: The roadmap expects churn, not uptime pressure.\n"


def _with_feedback(text: str, *, heading: str, block: str) -> str:
    return text.replace(f"---\n{heading}", f"{block}---\n{heading}")


PREDECESSOR_DOMAIN_TEXT = _with_feedback(
    CONFORMING_DOMAIN_TEXT,
    heading="# Domain",
    block=_DOMAIN_FEEDBACK.format(state="open"),
)
REVISED_DOMAIN_TEXT = _with_feedback(
    CONFORMING_DOMAIN_TEXT,
    heading="# Domain",
    block=_DOMAIN_FEEDBACK.format(state="awaiting-review") + _DOMAIN_RESPONSE,
)
PREDECESSOR_CONSTRAINTS_TEXT = _with_feedback(
    CONFORMING_CONSTRAINTS_TEXT,
    heading="# Constraints",
    block=_CONSTRAINTS_FEEDBACK.format(state="open"),
)
REVISED_CONSTRAINTS_TEXT = _with_feedback(
    CONFORMING_CONSTRAINTS_TEXT,
    heading="# Constraints",
    block=_CONSTRAINTS_FEEDBACK.format(state="awaiting-review") + _CONSTRAINTS_RESPONSE,
)


def test_gates_accept_a_parsed_conforming_revision() -> None:
    """The second module-boundary case: feedback-bearing text parsed by step
    1's parser, judged as a revision of its own predecessor."""
    domain = parse_domain_artifact(REVISED_DOMAIN_TEXT)
    constraints = parse_constraints_artifact(REVISED_CONSTRAINTS_TEXT)

    assert (
        run_domain_gates(
            ArtifactEnvelope(
                domain=domain,
                predecessor=parse_domain_artifact(PREDECESSOR_DOMAIN_TEXT),
            )
        )
        == []
    )
    assert (
        run_constraints_gates(
            ArtifactEnvelope(
                domain=domain,
                constraints=constraints,
                predecessor=parse_constraints_artifact(PREDECESSOR_CONSTRAINTS_TEXT),
            )
        )
        == []
    )


# --------------------------------------------------------------------------
# Layering
# --------------------------------------------------------------------------


def test_module_imports_only_the_artifact_leaf() -> None:
    """The gates sit directly above the artifact contract and below the
    orchestrator, plus ``scope_fence`` for its canonical frontmatter-stripping
    and fence-aware H2 extraction — itself stdlib-only, so it adds no cycle
    risk. The source grep catches a lazy import inside a function; the
    subprocess catches a transitive one. A stub ``plan_tool`` package stands in
    for the real one, whose ``__init__`` eagerly imports orchestrators that
    would mask the answer."""
    source = MODULE_PATH.read_text()
    assert re.findall(r"(?m)^\s*(?:from|import) (plan_tool\S*)", source) == [
        "plan_tool.scope_fence",
        "plan_tool.roadmap_artifacts",
    ]

    code = (
        "import sys, types\n"
        "pkg = types.ModuleType('plan_tool')\n"
        f"pkg.__path__ = [{str(MODULE_PATH.parent)!r}]\n"
        "sys.modules['plan_tool'] = pkg\n"
        "import plan_tool.roadmap_gates\n"
        "leaked = sorted(m for m in sys.modules if m.startswith('plan_tool.')"
        " and m not in ('plan_tool.roadmap_gates', 'plan_tool.roadmap_artifacts',"
        " 'plan_tool.scope_fence'))\n"
        "assert not leaked, leaked\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_module_touches_no_filesystem_and_no_subprocess() -> None:
    """Step 4 reads the artifacts; these gates only judge what it read."""
    source = MODULE_PATH.read_text()
    for token in ("invoker", "subprocess", "open(", "read_text"):
        assert token not in source


# --------------------------------------------------------------------------
# The removed-id-in-live-prose narrative check (not a stage gate)
# --------------------------------------------------------------------------

_INTEGRATION_PARAGRAPH = Path(__file__).parent / "fixtures" / "roadmap" / "integration-decisions-paragraph.md"
_REMOVED = "decision-gone"


def _removal(row_id: str = _REMOVED) -> RemovalRecord:
    return RemovalRecord(removed_id=row_id, rationale="Dropped.", feedback_ids=())


def _narrative_envelope(body: str, *, removals=(), predecessor=None) -> ArtifactEnvelope:
    return domain_envelope(body=body, removals=tuple(removals), predecessor=predecessor)


def _marked(*lines: str) -> str:
    return "\n".join(lines) + "\n"


def test_integration_decisions_paragraph_reports_the_removed_decision_reference() -> None:
    paragraph = _INTEGRATION_PARAGRAPH.read_bytes().decode("utf-8")
    removed = "decision-exclude-repo-browsing"
    envelope = _narrative_envelope(paragraph, removals=[_removal(removed)])
    (found,) = check_removed_ids_in_live_prose(envelope)
    assert found.kind == NARRATIVE_REMOVED_ID_IN_LIVE_PROSE
    assert found.artifact == DOMAIN_FILENAME
    assert found.row_id == removed
    assert paragraph[found.start : found.end] == removed


def test_removed_id_in_plain_prose_is_reported_with_artifact_id_and_span() -> None:
    body = f"First line.\nSecond names {_REMOVED} here.\n"
    (found,) = check_removed_ids_in_live_prose(_narrative_envelope(body, removals=[_removal()]))
    assert (found.artifact, found.row_id, found.line) == (DOMAIN_FILENAME, _REMOVED, 2)
    assert body[found.start : found.end] == _REMOVED
    assert found.excerpt == f"Second names {_REMOVED} here."


def test_every_occurrence_is_reported_once_each() -> None:
    body = f"{_REMOVED} once.\n\nAnd {_REMOVED} twice.\n"
    found = check_removed_ids_in_live_prose(_narrative_envelope(body, removals=[_removal()]))
    assert [ref.line for ref in found] == [1, 3]


def test_whole_token_match_ignores_longer_ids() -> None:
    body = f"Only {_REMOVED}-extra and pre-{_REMOVED} appear.\n"
    assert check_removed_ids_in_live_prose(_narrative_envelope(body, removals=[_removal()])) == []


@pytest.mark.parametrize(
    ("body", "reported_lines"),
    [
        pytest.param(
            _marked(HISTORY_MARKER_START, _REMOVED, HISTORY_MARKER_END),
            [],
            id="between-markers-is-excluded",
        ),
        pytest.param(
            _marked(HISTORY_MARKER_START, "old.", HISTORY_MARKER_END, _REMOVED),
            [4],
            id="after-the-end-marker-is-reported",
        ),
        pytest.param(
            _marked(HISTORY_MARKER_START, _REMOVED, "after."),
            [2],
            id="unclosed-start-excludes-nothing",
        ),
        pytest.param(
            _marked(HISTORY_MARKER_START, HISTORY_MARKER_START, HISTORY_MARKER_END, _REMOVED),
            [4],
            id="nested-start-does-not-reopen-and-first-end-closes",
        ),
        pytest.param(
            _marked("```", HISTORY_MARKER_START, "```", _REMOVED, HISTORY_MARKER_END),
            [4],
            id="fenced-start-marker-is-quoted-text",
        ),
        pytest.param(_marked("```", _REMOVED, "```"), [], id="fenced-token-is-not-live-prose"),
        pytest.param(_marked("~~~", _REMOVED, "~~~"), [], id="tilde-fenced-token-is-not-live-prose"),
        pytest.param(
            _marked(f"Text {HISTORY_MARKER_START} then", _REMOVED, HISTORY_MARKER_END),
            [2],
            id="marker-embedded-in-a-sentence-is-not-a-marker",
        ),
    ],
)
def test_marker_and_fence_handling(body: str, reported_lines: list[int]) -> None:
    found = check_removed_ids_in_live_prose(_narrative_envelope(body, removals=[_removal()]))
    assert [ref.line for ref in found] == reported_lines


def test_excerpt_windows_around_the_match_on_a_long_line() -> None:
    """The reviewer must see the defect, so a match past the excerpt limit is still inside the excerpt."""
    body = "x" * 400 + f" {_REMOVED} " + "y" * 200 + "\n"
    (found,) = check_removed_ids_in_live_prose(_narrative_envelope(body, removals=[_removal()]))

    assert _REMOVED in found.excerpt
    assert len(found.excerpt) <= 160


@pytest.mark.parametrize(
    ("text", "names_it"),
    [
        ("x entity-1 y", True),
        ("entity-1", True),
        ("entity-1.", True),
        ("entity-10", False),
        ("my-entity-1", False),
        ("entity-1_extra", False),
        ("entity-1-extra", False),
    ],
)
def test_narrative_gate_and_row_span_issuance_agree_on_whole_token_ids_for_ascii_boundaries(
    text: str, names_it: bool
) -> None:
    """Two matchers decide whether prose names an id; they must not disagree on ASCII id boundaries."""
    from plan_tool.roadmap_gates import _prose_names_id
    from plan_tool.roadmap_revision import contains_whole_row_id

    assert _prose_names_id(text, "entity-1") is names_it
    assert contains_whole_row_id(text, "entity-1") is names_it


@pytest.mark.parametrize(
    ("body", "reported"),
    [
        pytest.param(f"a\n```x```\n{_REMOVED}\n", True, id="inline-triple-backtick-line-is-not-a-fence"),
        pytest.param(f"a\n    ```\n{_REMOVED}\n    ```\n", True, id="four-space-indented-fence-is-not-a-fence"),
        pytest.param(f"a\n   ```\n{_REMOVED}\n   ```\n", False, id="three-space-indented-fence-is-a-fence"),
    ],
)
def test_the_check_uses_the_scope_fence_scanner_rules(body: str, reported: bool) -> None:
    """Pins which scanner decides what a fence is (ROADMAP_FORMAT.md names scope_fence); a switch to another scanner turns this red."""
    found = check_removed_ids_in_live_prose(_narrative_envelope(body, removals=[_removal()]))

    assert bool(found) is reported


@pytest.mark.parametrize(
    ("body", "kinds"),
    [
        pytest.param(f"```\n{_REMOVED}\n", [NARRATIVE_UNCLOSED_FENCE_UNREAD], id="unclosed-fence-hiding-a-removed-id"),
        pytest.param(f"~~~\nprose\n{_REMOVED}\n", [NARRATIVE_UNCLOSED_FENCE_UNREAD], id="unclosed-tilde-fence"),
        pytest.param("```\nnothing removed here\n", [], id="unclosed-fence-hiding-nothing-is-not-reported"),
        pytest.param(f"```\n{_REMOVED}\n```\n", [], id="closed-fence-stays-quoted-text"),
        pytest.param(f"Names {_REMOVED}.\n```\n{_REMOVED}\n", [NARRATIVE_REMOVED_ID_IN_LIVE_PROSE, NARRATIVE_UNCLOSED_FENCE_UNREAD], id="live-hit-before-the-opener-still-blocks"),
    ],
)
def test_unclosed_fence_is_reported_when_it_hides_a_removed_id(body: str, kinds: list[str]) -> None:
    """An unclosed fence runs to end of text; the unread tail must never read as a clean 'none'."""
    found = check_removed_ids_in_live_prose(_narrative_envelope(body, removals=[_removal()]))

    assert sorted(ref.kind for ref in found) == sorted(kinds)


def test_frontmatter_alternatives_are_not_scanned() -> None:
    decision = replace(
        DOMAIN_DECISION,
        rejected_alternatives=(RejectedAlternative(option=f"Use {_REMOVED}.", reason="Rejected."),),
    )
    envelope = domain_envelope(
        decisions=(decision,), removals=(_removal(),), body=prose_naming("decision-1")
    )
    assert check_removed_ids_in_live_prose(envelope) == []


def test_removed_id_that_is_also_a_present_row_is_ambiguous_not_live() -> None:
    envelope = domain_envelope(
        removals=(_removal("decision-1"),),
        body=prose_naming("entity-1", "entity-2", "decision-1"),
    )
    found = check_removed_ids_in_live_prose(envelope)
    assert {ref.kind for ref in found} == {NARRATIVE_REMOVED_ID_AMBIGUOUS_REFERENCE}
    assert found


def test_removed_ids_are_checked_per_artifact() -> None:
    """A removal is judged against the artifact that records it, never a sibling's body."""
    domain = make_domain(body="Clean domain prose.\n", removals=(_removal(),))
    constraints = make_constraints(body=f"{_REMOVED} lives in constraints prose.\n")
    assert check_removed_ids_in_live_prose(ArtifactEnvelope(domain=domain)) == []
    # The artifact under check is constraints, which records no removal of its own.
    assert check_removed_ids_in_live_prose(ArtifactEnvelope(domain=domain, constraints=constraints)) == []


def test_pruned_removal_record_is_no_longer_checked() -> None:
    """Pruning a carried record is a deliberate reviewer bypass: the row comes back into live use."""
    predecessor = make_domain(removals=(_removal(),))
    envelope = _narrative_envelope(f"{_REMOVED} is live again.\n", predecessor=predecessor)
    assert check_removed_ids_in_live_prose(envelope) == []


def test_candidate_added_removal_is_checked() -> None:
    envelope = _narrative_envelope(
        f"Still says {_REMOVED}.\n", removals=[_removal()], predecessor=make_domain()
    )
    assert len(check_removed_ids_in_live_prose(envelope)) == 1


def test_feedback_free_candidate_is_checked_against_predecessor_removals() -> None:
    predecessor = make_domain(removals=(_removal(),))
    envelope = _narrative_envelope(f"Names {_REMOVED}.\n", predecessor=predecessor)
    found = check_removed_ids_in_live_prose(envelope, feedback_free=True)
    assert [ref.row_id for ref in found] == [_REMOVED]


def test_default_does_not_read_predecessor_removals() -> None:
    """Without feedback_free a predecessor-only removal is a pruned record, not a check target."""
    predecessor = make_domain(removals=(_removal(),))
    envelope = _narrative_envelope(f"Names {_REMOVED}.\n", predecessor=predecessor)
    assert check_removed_ids_in_live_prose(envelope) == []


def test_check_is_not_in_any_stage_gate_tuple() -> None:
    """The narrative check is evidence, not a stage gate: no stage run may evaluate it."""
    for gates in (DOMAIN_GATES, CONSTRAINTS_GATES, COMPONENTS_GATES, PLANS_GATES):
        assert check_removed_ids_in_live_prose not in gates
    source = MODULE_PATH.read_text()
    for name in ("run_domain_gates", "run_constraints_gates", "run_components_gates", "run_plans_gates"):
        body = source.split(f"def {name}(", 1)[1].split("\ndef ", 1)[0]
        assert "removed_ids_in_live_prose" not in body


def test_valid_no_change_reconciliation_reports_nothing() -> None:
    envelope = _narrative_envelope("Names nothing removed.\n", removals=[_removal()])
    assert check_removed_ids_in_live_prose(envelope) == []


# --------------------------------------------------------------------------
# Stack gate
# --------------------------------------------------------------------------


def _stack_row(concern: str, *, row_id: str | None = None, **kwargs) -> StackRow:
    if not kwargs:
        kwargs = {"choice": "Some choice."}
    return StackRow(id=row_id or f"stack-{concern}", concern=concern, **kwargs)


def _full_stack() -> tuple[StackRow, ...]:
    return tuple(_stack_row(concern) for concern in STACK_CONCERNS)


def _stack_decision(anchor: str, *, status=DecisionStatus.PENDING) -> DecisionRow:
    return replace(CONSTRAINTS_DECISION, id="decision-9", anchor=anchor, status=status)


def test_stack_gate_inert_when_collection_absent() -> None:
    # Absence is never refused, so accepted stack-less versions and a first run
    # that omitted the collection stay valid on every envelope path.
    assert check_stack_totality(constraints_envelope(stack=None)) == []
    assert run_constraints_gates(constraints_envelope(stack=None)) == []


def test_present_empty_stack_is_refused() -> None:
    violations = check_stack_totality(constraints_envelope(stack=()))
    assert [v.kind for v in violations] == [VIOLATION_MISSING_STACK_CONCERN] * len(STACK_CONCERNS)
    for concern in STACK_CONCERNS:
        assert any(f"'{concern}'" in v.message for v in violations)


def test_partial_stack_is_refused_and_names_the_missing_concern() -> None:
    envelope = constraints_envelope(stack=_full_stack()[:2])
    (violation,) = check_stack_totality(envelope)
    assert violation.kind == VIOLATION_MISSING_STACK_CONCERN
    assert f"'{STACK_CONCERNS[2]}'" in violation.message


def test_open_concern_satisfies_totality() -> None:
    stack = (*_full_stack()[:2], _stack_row(STACK_CONCERNS[2], open=True, choice=None))
    assert check_stack_totality(constraints_envelope(stack=stack)) == []


def test_gate_does_not_read_choice_text() -> None:
    stack = tuple(
        _stack_row(c, choice="anything at all, unlike any hosting product")
        for c in STACK_CONCERNS
    )
    assert check_stack_totality(constraints_envelope(stack=stack)) == []


def test_missing_concern_message_says_open_is_allowed() -> None:
    (violation, *_rest) = check_stack_totality(constraints_envelope(stack=()))
    assert "`open`" in violation.message


def test_unknown_concern_is_reported_with_the_row_id() -> None:
    stack = (*_full_stack(), _stack_row("observability", row_id="stack-obs"))
    (violation,) = check_stack_totality(constraints_envelope(stack=stack))
    assert violation.kind == VIOLATION_UNKNOWN_STACK_CONCERN
    assert violation.row_id == "stack-obs"
    assert "'observability'" in violation.message


def test_same_id_and_same_concern_is_one_duplicate_id_not_a_duplicate_concern() -> None:
    stack = (*_full_stack(), _stack_row(STACK_CONCERNS[0], row_id="stack-platform"))
    (violation,) = check_stack_totality(constraints_envelope(stack=stack))
    assert violation.kind == VIOLATION_DUPLICATE_STACK_ID
    assert violation.row_id == "stack-platform"


def test_duplicate_stack_id_reported_once_per_id() -> None:
    stack = tuple(_stack_row(c, row_id="stack-x") for c in STACK_CONCERNS)
    violations = [
        v
        for v in check_stack_totality(constraints_envelope(stack=stack))
        if v.kind == VIOLATION_DUPLICATE_STACK_ID
    ]
    assert len(violations) == 1
    assert "3 rows" in violations[0].message


def test_second_row_for_the_same_concern_is_reported_as_a_duplicate_concern() -> None:
    extra = _stack_row(STACK_CONCERNS[0], row_id="stack-platform-2")
    (violation,) = check_stack_totality(constraints_envelope(stack=(*_full_stack(), extra)))
    assert violation.kind == VIOLATION_DUPLICATE_STACK_CONCERN
    assert f"'{STACK_CONCERNS[0]}'" in violation.message
    assert "stack-platform," in violation.message and "stack-platform-2" in violation.message


@pytest.mark.parametrize(
    "row",
    [
        StackRow(id="stack-platform", concern="platform", choice="x", open=True),
        StackRow(id="stack-platform", concern="platform"),
        StackRow(id="stack-platform", concern="platform", choice="   "),
        StackRow(id="stack-platform", concern="platform", choice=""),
    ],
    ids=["both", "neither", "blank-choice", "empty-choice"],
)
def test_stack_row_with_both_or_neither_choice_and_open_is_reported(row: StackRow) -> None:
    stack = (row, *_full_stack()[1:])
    (violation,) = check_stack_totality(constraints_envelope(stack=stack))
    assert violation.kind == VIOLATION_STACK_ROW_STATE
    assert violation.row_id == "stack-platform"


def test_stack_row_needs_no_prose_naming_and_is_not_a_design_row_id() -> None:
    envelope = constraints_envelope(stack=_full_stack())
    assert check_inventory_has_prose(envelope) == []
    assert not design_row_ids(envelope.constraints) & {r.id for r in _full_stack()}


def test_stack_id_is_a_feedback_target_and_a_continuity_identity() -> None:
    artifact = make_constraints(stack=_full_stack())
    stack_ids = {r.id for r in _full_stack()}
    assert stack_ids <= feedback_target_ids(artifact)
    assert stack_ids <= {row_id for _label, row_id in _continuity_rows(artifact)}


def test_stack_id_colliding_with_a_domain_or_constraint_id_is_reported_once() -> None:
    stack = (_stack_row("platform", row_id="constraint-1"), *_full_stack()[1:])
    (violation,) = check_duplicate_row_ids(constraints_envelope(stack=stack))
    assert violation.kind == VIOLATION_DUPLICATE_ROW_ID
    assert violation.row_id == "constraint-1"


def test_decision_anchored_to_a_stack_row_resolves_in_constraints() -> None:
    envelope = constraints_envelope(
        stack=_full_stack(), decisions=(_stack_decision("stack-platform"),)
    )
    assert check_decision_records(envelope) == []


def test_decision_anchored_to_an_open_stack_row_is_accepted() -> None:
    stack = (_stack_row("platform", open=True, choice=None), *_full_stack()[1:])
    envelope = constraints_envelope(stack=stack, decisions=(_stack_decision("stack-platform"),))
    assert check_decision_records(envelope) == []


def test_components_stage_resolves_a_decision_anchor_to_a_stack_row() -> None:
    envelope = components_envelope(
        constraints=make_constraints(stack=_full_stack()),
        decisions=(replace(COMPONENTS_DECISION, anchor="stack-platform"),),
    )
    assert check_decision_records(envelope) == []
