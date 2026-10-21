"""Tests for the roadmap-view resolver.

Plain unit tests: the module drives no orchestrator, touches no disk, and has
no backend seam. Fixtures are built by constructing step 1's row dataclasses
directly rather than by parsing text, matching ``tests/test_roadmap_gates.py``'s
stated fixture policy.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from plan_tool.roadmap_artifacts import (
    AssumptionRow,
    AttributeDispositionRow,
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
    DraftSeedProvenance,
    EntityRow,
    FeedbackRow,
    FeedbackState,
    FeedbackTarget,
    FeedbackTargetKind,
    FieldRow,
    FieldType,
    HostingRow,
    OrderingEntry,
    PLANS_FILENAME,
    PatternRow,
    PlanDisposition,
    PlanRow,
    PlansArtifact,
    RejectedAlternative,
    RemovalRecord,
    StackRow,
    StoreRow,
    WorkflowRow,
    components_path,
    constraints_path,
    domain_path,
    plans_path,
    render_components_artifact,
    render_constraints_artifact,
    render_domain_artifact,
    render_draft_seed_provenance,
    render_plans_artifact,
    resolve_draft_seed_path,
    roadmap_dir,
)
from plan_tool.roadmap_gates import feedback_target_ids
from plan_tool.roadmap_seed_manifest import (
    DRAFT_SEED_STATE_CURRENT,
    DRAFT_SEED_STATE_DIGEST_MISMATCHED,
    DRAFT_SEED_STATE_DUPLICATE,
    DRAFT_SEED_STATE_MALFORMED,
    DRAFT_SEED_STATE_MISSING,
    DRAFT_SEED_STATE_PATH_ESCAPING,
    DRAFT_SEED_STATE_STALE,
    DraftSeedClassification,
    ORPHAN_SEED_RECORD_FILE,
    ORPHAN_SEED_RECORD_SIDECAR_ENTRY,
    NoPublishedRoadmapVersionError,
    OrphanSeedRecord,
    classify_draft_seeds,
)
from plan_tool.roadmap_seed_state import (
    digest_text,
    empty_seed_state,
    seed_state_path,
    write_seed_state,
)
from plan_tool.roadmap_versions import (
    INITIAL_EMPTY_REVIEW_LINEAGE_ID,
    ROADMAP_VERSION_SCHEMA_VERSION,
    AcceptedRoadmapHead,
    PreparedRoadmapVersion,
    RoadmapVersionContent,
    RoadmapVersionError,
    accepted_head_path,
    create_candidate_version,
    create_root_version,
    render_accepted_head,
    stored_version_members,
    version_directory_path,
)
from plan_tool import roadmap_view
from plan_tool.roadmap_view import (
    MODE_CURRENT,
    MODE_REVIEW,
    RESOLUTION_AMBIGUOUS,
    RESOLUTION_ARTIFACT_SCOPE,
    RESOLUTION_DANGLING,
    RESOLUTION_OUT_OF_SCOPE_FOR_MODE,
    RESOLUTION_RESOLVED,
    SEED_TRACKING_TRACKED,
    Citation,
    build_citation_map,
    build_design_row_index,
    build_removal_index,
    display_label,
    load_roadmap,
    render_decision_ledger,
    render_roadmap_summary,
    render_reverse_index,
    render_seed_state_view,
    render_traceability_walk as _render_traceability_walk,
    resolve_citation_subject,
    resolve_feedback_target,
    resolve_id,
    summarize_seed_lifecycle,
)

MODULE_PATH = Path(__file__).resolve().parents[1] / "plan_tool" / "roadmap_view.py"
SLUG = "acme-roadmap"


# --------------------------------------------------------------------------
# Fixture builders
# --------------------------------------------------------------------------


def entity_row(id="entity-1", name="Order") -> EntityRow:
    return EntityRow(id=id, name=name, fields=())


def workflow_row(id="workflow-1", name="Place order", entity_ids=()) -> WorkflowRow:
    return WorkflowRow(id=id, name=name, entity_ids=tuple(entity_ids))


def component_row(
    id="component-1",
    name="Ordering",
    entity_ids=(),
    pattern_ids=(),
    constraint_ids=(),
    store_ids=(),
) -> ComponentRow:
    return ComponentRow(
        id=id,
        name=name,
        entity_ids=tuple(entity_ids),
        pattern_ids=tuple(pattern_ids),
        constraint_ids=tuple(constraint_ids),
        store_ids=tuple(store_ids),
    )


def hosting_row(
    id="hosting-1", facet="compute", value="managed-containers", product=None
) -> HostingRow:
    return HostingRow(id=id, facet=facet, value=value, product=product)


def store_row(id="store-1", category="relational", sharing="pool", product=None) -> StoreRow:
    return StoreRow(id=id, category=category, sharing=sharing, product=product)


def business_rule_row(
    id="rule-1", statement="An order belongs to one customer.", entity_ids=()
) -> BusinessRuleRow:
    return BusinessRuleRow(id=id, statement=statement, entity_ids=tuple(entity_ids))


def constraint_row(
    id="constraint-1",
    statement="Checkout completes within 300ms.",
    attribute="performance",
    anchor_ids=(),
) -> ConstraintRow:
    return ConstraintRow(
        id=id, statement=statement, attribute=attribute, anchor_ids=tuple(anchor_ids)
    )


def assumption_row(
    id="assumption-1", statement="Payments settle same-day.", consuming_plan_ids=()
) -> AssumptionRow:
    return AssumptionRow(
        id=id, statement=statement, consuming_plan_ids=tuple(consuming_plan_ids)
    )


def plan_row(
    id="plan-1",
    title="Ordering service",
    component_ids=(),
    disposition=PlanDisposition.KEEP,
    draft_seed_path=None,
    intent="Make the ordering workflow available to callers.",
    non_goals=("Changing authentication policy.",),
) -> PlanRow:
    return PlanRow(
        id=id,
        title=title,
        disposition=disposition,
        component_ids=tuple(component_ids),
        draft_seed_path=draft_seed_path or f"seeds/{id}.md",
        sizing_rationale="One component, one plan.",
        intent=intent,
        non_goals=tuple(non_goals),
    )


def draft_seed_classifications(
    **states: str,
) -> dict[str, DraftSeedClassification]:
    return {
        plan_id: DraftSeedClassification(plan_id=plan_id, state=state)
        for plan_id, state in states.items()
    }


def render_traceability_walk(
    loaded, plans_dir: Path, classifications: dict[str, DraftSeedClassification] | None = None
) -> str:
    """Supply current states for legacy walk fixtures outside seed tests."""
    if classifications is None:
        plans = loaded.plans.plans if loaded.plans is not None else ()
        classifications = draft_seed_classifications(
            **{plan.id: DRAFT_SEED_STATE_CURRENT for plan in plans}
        )
    return _render_traceability_walk(loaded, plans_dir, classifications)


def decision_row(
    id="decision-1",
    chosen_option="Keep the cart inside the order aggregate.",
    anchor="entity-1",
    status=DecisionStatus.PENDING,
    rejected_alternatives=(),
    rationale="Keeps checkout atomic.",
) -> DecisionRow:
    return DecisionRow(
        id=id,
        chosen_option=chosen_option,
        rejected_alternatives=tuple(rejected_alternatives),
        rationale=rationale,
        anchor=anchor,
        status=status,
    )


def feedback_row(
    id="feedback-1", request="Split the order entity.", target=None
) -> FeedbackRow:
    return FeedbackRow(
        id=id,
        target=target or FeedbackTarget(kind=FeedbackTargetKind.ARTIFACT),
        request=request,
        state=FeedbackState.OPEN,
    )


def disposition_row(
    id="attribute-performance",
    attribute="performance",
    disposition=ConstraintDisposition.PRIORITIZED,
) -> AttributeDispositionRow:
    return AttributeDispositionRow(id=id, attribute=attribute, disposition=disposition)


def pattern_row(id="pattern-1", name="Command") -> PatternRow:
    return PatternRow(
        id=id, name=name, statement="Encapsulate a request as an object."
    )


def removal_record(
    removed_id="entity-1",
    rationale="No longer needed.",
    feedback_ids=("feedback-1",),
) -> RemovalRecord:
    return RemovalRecord(
        removed_id=removed_id, rationale=rationale, feedback_ids=tuple(feedback_ids)
    )


def domain_artifact(**overrides) -> DomainArtifact:
    defaults = dict(
        entities=(), business_rules=(), workflows=(), decisions=(),
        body="", feedback=(), removals=(),
    )
    defaults.update(overrides)
    return DomainArtifact(**defaults)


def constraints_artifact(**overrides) -> ConstraintsArtifact:
    defaults = dict(
        dispositions=(), constraints=(), decisions=(),
        body="", feedback=(), removals=(),
    )
    defaults.update(overrides)
    return ConstraintsArtifact(**defaults)


def components_artifact(**overrides) -> ComponentsArtifact:
    defaults = dict(
        system_patterns=(), component_patterns=(), components=(), decisions=(),
        body="", feedback=(), removals=(),
    )
    defaults.update(overrides)
    return ComponentsArtifact(**defaults)


def plans_artifact(**overrides) -> PlansArtifact:
    defaults = dict(
        plans=(), ordering=(), assumptions=(), decisions=(),
        body="", feedback=(), removals=(),
    )
    defaults.update(overrides)
    return PlansArtifact(**defaults)


class _ExplodingMapping(dict):
    """A mapping that fails the test if a caller ever consults it."""

    def get(self, *args, **kwargs):
        raise AssertionError("must not be consulted")


def write_domain(plans_dir: Path, artifact: DomainArtifact) -> Path:
    path = domain_path(plans_dir, SLUG)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_domain_artifact(artifact), encoding="utf-8")
    return path


def write_constraints(plans_dir: Path, artifact: ConstraintsArtifact) -> Path:
    path = constraints_path(plans_dir, SLUG)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_constraints_artifact(artifact), encoding="utf-8")
    return path


def write_components(plans_dir: Path, artifact: ComponentsArtifact) -> Path:
    path = components_path(plans_dir, SLUG)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_components_artifact(artifact), encoding="utf-8")
    return path


def write_plans(plans_dir: Path, artifact: PlansArtifact) -> Path:
    path = plans_path(plans_dir, SLUG)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_plans_artifact(artifact), encoding="utf-8")
    return path


def write_draft_seed(
    plans_dir: Path, plan: PlanRow, provenance: DraftSeedProvenance
) -> Path:
    path = resolve_draft_seed_path(plans_dir, SLUG, plan.draft_seed_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_draft_seed_provenance(provenance), encoding="utf-8")
    return path


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _version_content(
    *,
    domain: DomainArtifact,
    constraints: ConstraintsArtifact,
    components: ComponentsArtifact,
    plans: PlansArtifact,
) -> RoadmapVersionContent:
    return RoadmapVersionContent(
        brief_bytes=b"recorded brief\n",
        artifact_bytes=(
            render_domain_artifact(domain).encode("utf-8"),
            render_constraints_artifact(constraints).encode("utf-8"),
            render_components_artifact(components).encode("utf-8"),
            render_plans_artifact(plans).encode("utf-8"),
        ),
    )


def _prepared_root_version(
    *,
    domain: DomainArtifact,
    constraints: ConstraintsArtifact,
    components: ComponentsArtifact,
    plans: PlansArtifact,
) -> PreparedRoadmapVersion:
    content = _version_content(
        domain=domain,
        constraints=constraints,
        components=components,
        plans=plans,
    )
    return PreparedRoadmapVersion(
        record=create_root_version(
            roadmap_slug=SLUG,
            brief_digest=_digest(content.brief_bytes),
            artifact_digests=tuple(_digest(data) for data in content.artifact_bytes),
        ),
        content=content,
    )


def _prepared_candidate_version(
    predecessor: PreparedRoadmapVersion,
    *,
    domain: DomainArtifact,
    constraints: ConstraintsArtifact,
    components: ComponentsArtifact,
    plans: PlansArtifact,
) -> PreparedRoadmapVersion:
    content = _version_content(
        domain=domain,
        constraints=constraints,
        components=components,
        plans=plans,
    )
    return PreparedRoadmapVersion(
        record=create_candidate_version(
            roadmap_slug=SLUG,
            predecessor_version_id=predecessor.record.version_id,
            content_identity=_digest(b"candidate content"),
            review_lineage_identity=INITIAL_EMPTY_REVIEW_LINEAGE_ID,
            brief_digest=_digest(content.brief_bytes),
            artifact_digests=tuple(_digest(data) for data in content.artifact_bytes),
        ),
        content=content,
    )


def _store_version(tmp_path: Path, prepared: PreparedRoadmapVersion) -> None:
    version_dir = version_directory_path(tmp_path, SLUG, prepared.record.version_id)
    for member in stored_version_members(prepared):
        path = version_dir / member.member_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(member.data)


def _select_accepted_version(tmp_path: Path, prepared: PreparedRoadmapVersion) -> None:
    path = accepted_head_path(tmp_path, SLUG)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        render_accepted_head(
            AcceptedRoadmapHead(
                schema_version=ROADMAP_VERSION_SCHEMA_VERSION,
                roadmap_slug=SLUG,
                version_id=prepared.record.version_id,
            )
        )
    )


# --------------------------------------------------------------------------
# display_label
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "row, kind, expected",
    [
        (entity_row(name="Order"), None, "Order"),
        (workflow_row(name="Place order"), None, "Place order"),
        (component_row(name="Ordering"), None, "Ordering"),
        (
            business_rule_row(statement="An order belongs to one customer."),
            None,
            "An order belongs to one customer.",
        ),
        (
            constraint_row(statement="Checkout completes within 300ms."),
            None,
            "Checkout completes within 300ms.",
        ),
        (
            assumption_row(statement="Payments settle same-day."),
            None,
            "Payments settle same-day.",
        ),
        (plan_row(title="Ordering service"), None, "Ordering service"),
        (
            decision_row(chosen_option="Keep the cart inside the order aggregate."),
            None,
            "Keep the cart inside the order aggregate.",
        ),
        (
            feedback_row(request="Split the order entity."),
            None,
            "Split the order entity.",
        ),
        (
            disposition_row(
                attribute="performance", disposition=ConstraintDisposition.PRIORITIZED
            ),
            None,
            "performance: prioritized",
        ),
        (pattern_row(name="Command"), "system pattern", "system pattern: Command"),
        (
            pattern_row(name="Command"),
            "component pattern",
            "component pattern: Command",
        ),
        (
            hosting_row(product="Cloud Run"),
            None,
            "hosting compute: managed-containers (Cloud Run)",
        ),
        (
            store_row(product="PostgreSQL"),
            None,
            "store: relational, pool (PostgreSQL)",
        ),
        (
            StackRow("stack-platform", "platform", choice="managed containers"),
            None,
            "stack platform: managed containers",
        ),
        (StackRow("stack-engine", "store-engine", open=True), None, "stack store-engine: open"),
        # Parse accepts a row with neither; the gate refuses it, but a view must not print "None".
        (StackRow("stack-engine", "store-engine"), None, "stack store-engine: no choice"),
    ],
)
def test_display_label_by_row_kind(row, kind, expected) -> None:
    assert display_label(row, kind=kind) == expected


def test_pattern_label_names_its_scope() -> None:
    row = pattern_row(id="pattern-1", name="Shared name")
    system_label = display_label(row, kind="system pattern")
    component_label = display_label(row, kind="component pattern")
    assert system_label != component_label


def test_pattern_label_without_kind_raises() -> None:
    with pytest.raises(ValueError):
        display_label(pattern_row())


def test_disposition_label_uses_the_plain_value() -> None:
    row = disposition_row(
        attribute="performance", disposition=ConstraintDisposition.PRIORITIZED
    )
    label = display_label(row)
    assert "prioritized" in label
    assert "ConstraintDisposition" not in label


def test_removal_label_reads_as_a_tombstone() -> None:
    record = removal_record(removed_id="entity-1", rationale="No longer needed.")
    label = display_label(record)
    assert "entity-1" in label
    assert "No longer needed." in label
    assert "removed" in label.lower()
    assert label != display_label(entity_row(id="entity-1", name="entity-1"))


# --------------------------------------------------------------------------
# build_design_row_index / build_removal_index
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwarg, artifact",
    [
        (
            "domain",
            domain_artifact(
                entities=(entity_row(),),
                business_rules=(business_rule_row(),),
                workflows=(workflow_row(),),
                decisions=(decision_row(),),
            ),
        ),
        (
            "constraints",
            constraints_artifact(
                dispositions=(disposition_row(),),
                constraints=(constraint_row(),),
                decisions=(decision_row(id="decision-2"),),
                hosting=(hosting_row(),),
            ),
        ),
        (
            "components",
            components_artifact(
                system_patterns=(pattern_row(id="pattern-1"),),
                component_patterns=(pattern_row(id="pattern-2"),),
                stores=(store_row(),),
                components=(component_row(),),
                decisions=(decision_row(id="decision-3"),),
            ),
        ),
        (
            "plans",
            plans_artifact(
                plans=(plan_row(),),
                assumptions=(assumption_row(),),
                decisions=(decision_row(id="decision-4"),),
            ),
        ),
    ],
)
def test_build_design_row_index_matches_feedback_target_ids(kwarg, artifact) -> None:
    index = build_design_row_index(**{kwarg: artifact})
    assert set(index.keys()) == feedback_target_ids(artifact)


def test_build_design_row_index_tolerates_no_artifacts() -> None:
    assert build_design_row_index() == {}


def test_ambiguous_matches_render_in_stage_then_source_order() -> None:
    domain = domain_artifact(
        entities=(entity_row(id="shared-1", name="Domain entity"),)
    )
    constraints = constraints_artifact(
        constraints=(constraint_row(id="shared-1", statement="Constraints statement"),)
    )
    index = build_design_row_index(domain=domain, constraints=constraints)
    resolution = resolve_id("shared-1", index)
    assert resolution.status == RESOLUTION_AMBIGUOUS
    assert resolution.matches == ("Domain entity", "Constraints statement")


def test_build_removal_index_tolerates_no_artifacts() -> None:
    assert build_removal_index() == {}


def test_build_removal_index_collects_every_record_under_a_colliding_id() -> None:
    domain = domain_artifact(
        removals=(removal_record(removed_id="shared", rationale="Domain reason"),)
    )
    constraints = constraints_artifact(
        removals=(
            removal_record(removed_id="shared", rationale="Constraints reason"),
        )
    )
    index = build_removal_index(domain=domain, constraints=constraints)
    assert len(index["shared"]) == 2
    assert {record.rationale for record in index["shared"]} == {
        "Domain reason",
        "Constraints reason",
    }


# --------------------------------------------------------------------------
# resolve_id
# --------------------------------------------------------------------------


def test_resolve_id_returns_dangling_for_an_undeclared_id() -> None:
    index = build_design_row_index(domain=domain_artifact(entities=(entity_row(),)))
    resolution = resolve_id("nonexistent", index)
    assert resolution.status == RESOLUTION_DANGLING
    assert resolution.text == "⚠ undefined: nonexistent"


def test_resolve_id_returns_resolved_with_the_display_label() -> None:
    index = build_design_row_index(
        domain=domain_artifact(entities=(entity_row(id="entity-1", name="Order"),))
    )
    resolution = resolve_id("entity-1", index)
    assert resolution.status == RESOLUTION_RESOLVED
    assert resolution.text == "Order"


def test_resolve_id_returns_ambiguous_naming_every_match() -> None:
    domain = domain_artifact(
        entities=(entity_row(id="dup", name="Entity label"),),
        workflows=(workflow_row(id="dup", name="Workflow label"),),
    )
    index = build_design_row_index(domain=domain)
    resolution = resolve_id("dup", index)
    assert resolution.status == RESOLUTION_AMBIGUOUS
    assert resolution.text == "⚠ ambiguous: dup"
    assert resolution.matches == ("Entity label", "Workflow label")


# --------------------------------------------------------------------------
# resolve_feedback_target
# --------------------------------------------------------------------------


def test_resolve_feedback_target_artifact_scope_is_not_dangling() -> None:
    target = FeedbackTarget(kind=FeedbackTargetKind.ARTIFACT)
    resolution = resolve_feedback_target(
        target, index=_ExplodingMapping(), removals=_ExplodingMapping()
    )
    assert resolution.status == RESOLUTION_ARTIFACT_SCOPE


def test_resolve_feedback_target_row_kind_resolves_against_design_rows() -> None:
    domain = domain_artifact(entities=(entity_row(id="entity-1", name="Order"),))
    index = build_design_row_index(domain=domain)
    target = FeedbackTarget(kind=FeedbackTargetKind.ROW, row_id="entity-1")
    resolution = resolve_feedback_target(target, index=index, removals={})
    assert resolution.status == RESOLUTION_RESOLVED
    assert resolution.text == "Order"


def test_resolve_feedback_target_through_a_removal_is_resolved_not_dangling() -> None:
    domain = domain_artifact(
        removals=(removal_record(removed_id="entity-1", rationale="Dropped after review."),)
    )
    index = build_design_row_index(domain=domain)
    removals = build_removal_index(domain=domain)
    target = FeedbackTarget(kind=FeedbackTargetKind.ROW, row_id="entity-1")
    resolution = resolve_feedback_target(target, index=index, removals=removals)
    assert resolution.status == RESOLUTION_RESOLVED
    assert "entity-1" in resolution.text
    assert "Dropped after review." in resolution.text


def test_resolve_feedback_target_unresolvable_row_id_is_dangling() -> None:
    target = FeedbackTarget(kind=FeedbackTargetKind.ROW, row_id="nonexistent")
    resolution = resolve_feedback_target(target, index={}, removals={})
    assert resolution.status == RESOLUTION_DANGLING


def test_resolve_feedback_target_removal_collision_is_ambiguous_naming_every_tombstone() -> None:
    domain = domain_artifact(
        removals=(removal_record(removed_id="shared", rationale="Domain reason"),)
    )
    constraints = constraints_artifact(
        removals=(
            removal_record(removed_id="shared", rationale="Constraints reason"),
        )
    )
    index = build_design_row_index(domain=domain, constraints=constraints)
    removals = build_removal_index(domain=domain, constraints=constraints)
    target = FeedbackTarget(kind=FeedbackTargetKind.ROW, row_id="shared")
    resolution = resolve_feedback_target(target, index=index, removals=removals)
    assert resolution.status == RESOLUTION_AMBIGUOUS
    assert len(resolution.matches) == 2
    assert all("shared" in label for label in resolution.matches)


# --------------------------------------------------------------------------
# load_roadmap
# --------------------------------------------------------------------------


def _loaded(tmp_path: Path, *, mode: str = MODE_CURRENT, **artifacts):
    """Write the given artifacts and load them back as a ``LoadedRoadmap``.

    Shared by the citation-map / reverse-index tests below, mirroring
    ``load_roadmap``'s own tmp_path-and-artifacts pattern rather than
    hand-building a ``LoadedRoadmap``.
    """
    _write_subset(tmp_path, **artifacts)
    return load_roadmap(tmp_path, SLUG, mode=mode)


def _write_subset(tmp_path: Path, **artifacts) -> None:
    """Publish an accepted root holding the given artifacts; omitted ones are empty.

    The version store is the only thing ``load_roadmap`` reads, so a fixture
    "subset" is the given members over empty defaults, never a missing file. A
    ``bytes`` value is stored verbatim, which is how a test plants a member that
    does not parse.
    """
    defaults = {
        "domain": domain_artifact,
        "constraints": constraints_artifact,
        "components": components_artifact,
        "plans": plans_artifact,
    }
    renderers = {
        "domain": render_domain_artifact,
        "constraints": render_constraints_artifact,
        "components": render_components_artifact,
        "plans": render_plans_artifact,
    }
    members: list[bytes] = []
    for key in defaults:
        value = artifacts.get(key)
        if value is None:
            value = defaults[key]()
        members.append(value if isinstance(value, bytes) else renderers[key](value).encode("utf-8"))
    content = RoadmapVersionContent(brief_bytes=b"recorded brief\n", artifact_bytes=tuple(members))
    stored = PreparedRoadmapVersion(
        record=create_root_version(
            roadmap_slug=SLUG,
            brief_digest=_digest(content.brief_bytes),
            artifact_digests=tuple(_digest(data) for data in content.artifact_bytes),
        ),
        content=content,
    )
    _store_version(tmp_path, stored)
    _select_accepted_version(tmp_path, stored)


_BROKEN_MEMBER = b"not a roadmap artifact at all"


def test_load_roadmap_parses_all_four_when_present(tmp_path: Path) -> None:
    _write_subset(
        tmp_path,
        domain=domain_artifact(entities=(entity_row(),)),
        constraints=constraints_artifact(constraints=(constraint_row(),)),
        components=components_artifact(components=(component_row(),)),
        plans=plans_artifact(plans=(plan_row(),)),
    )

    loaded = load_roadmap(tmp_path, SLUG)

    assert loaded.directory_exists is True
    assert loaded.domain is not None
    assert loaded.constraints is not None
    assert loaded.components is not None
    assert loaded.plans is not None
    assert loaded.absent == ()
    assert loaded.unparseable == ()


def test_load_roadmap_reads_the_complete_bundle_selected_by_the_accepted_head(
    tmp_path: Path,
) -> None:
    stored = _prepared_root_version(
        domain=domain_artifact(entities=(entity_row(name="Stored order"),)),
        constraints=constraints_artifact(
            constraints=(constraint_row(statement="Stored constraint."),)
        ),
        components=components_artifact(
            components=(component_row(name="Stored component"),)
        ),
        plans=plans_artifact(plans=(plan_row(title="Stored plan"),)),
    )
    _store_version(tmp_path, stored)
    _select_accepted_version(tmp_path, stored)
    write_domain(tmp_path, domain_artifact(entities=(entity_row(name="Live order"),)))
    write_constraints(
        tmp_path, constraints_artifact(constraints=(constraint_row(statement="Live constraint."),))
    )
    write_components(
        tmp_path, components_artifact(components=(component_row(name="Live component"),))
    )
    write_plans(tmp_path, plans_artifact(plans=(plan_row(title="Live plan"),)))

    loaded = load_roadmap(tmp_path, SLUG)

    assert loaded.domain is not None
    assert loaded.constraints is not None
    assert loaded.components is not None
    assert loaded.plans is not None
    assert loaded.domain.entities[0].name == "Stored order"
    assert loaded.constraints.constraints[0].statement == "Stored constraint."
    assert loaded.components.components[0].name == "Stored component"
    assert loaded.plans.plans[0].title == "Stored plan"


def test_load_roadmap_module_holds_no_top_level_artifact_loader_or_path_helper() -> None:
    """Deliberate carve-out: the unversioned fallback's loaders and paths are gone, not dormant."""
    for name in (
        "load_domain_artifact",
        "load_constraints_artifact",
        "load_components_artifact",
        "load_plans_artifact",
        "domain_path",
        "constraints_path",
        "components_path",
        "plans_path",
    ):
        assert not hasattr(roadmap_view, name), name


def test_load_roadmap_observes_the_candidate_selected_after_promotion(
    tmp_path: Path,
) -> None:
    root = _prepared_root_version(
        domain=domain_artifact(entities=(entity_row(name="Root order"),)),
        constraints=constraints_artifact(),
        components=components_artifact(),
        plans=plans_artifact(),
    )
    candidate = _prepared_candidate_version(
        root,
        domain=domain_artifact(entities=(entity_row(name="Promoted order"),)),
        constraints=constraints_artifact(),
        components=components_artifact(),
        plans=plans_artifact(),
    )
    _store_version(tmp_path, root)
    _store_version(tmp_path, candidate)
    _select_accepted_version(tmp_path, root)
    root_members_before = {
        member.member_name: (
            version_directory_path(tmp_path, SLUG, root.record.version_id)
            / member.member_name
        ).read_bytes()
        for member in stored_version_members(root)
    }

    before_promotion = load_roadmap(tmp_path, SLUG)
    _select_accepted_version(tmp_path, candidate)
    after_promotion = load_roadmap(tmp_path, SLUG)

    assert before_promotion.domain is not None
    assert after_promotion.domain is not None
    assert before_promotion.domain.entities[0].name == "Root order"
    assert after_promotion.domain.entities[0].name == "Promoted order"
    assert {
        member.member_name: (
            version_directory_path(tmp_path, SLUG, root.record.version_id)
            / member.member_name
        ).read_bytes()
        for member in stored_version_members(root)
    } == root_members_before


def test_load_roadmap_corrupt_head_is_not_reported_as_no_head(
    tmp_path: Path,
) -> None:
    write_domain(tmp_path, domain_artifact(entities=(entity_row(name="Live order"),)))
    head = accepted_head_path(tmp_path, SLUG)
    head.parent.mkdir(parents=True, exist_ok=True)
    head.write_bytes(b"invalid accepted head")

    with pytest.raises(RoadmapVersionError, match="accepted-head selector"):
        load_roadmap(tmp_path, SLUG)


def test_load_roadmap_degrades_an_unparseable_accepted_member_without_live_fallback(
    tmp_path: Path,
) -> None:
    valid = _prepared_root_version(
        domain=domain_artifact(entities=(entity_row(name="Stored order"),)),
        constraints=constraints_artifact(),
        components=components_artifact(),
        plans=plans_artifact(),
    )
    content = RoadmapVersionContent(
        brief_bytes=valid.content.brief_bytes,
        artifact_bytes=(b"not a roadmap artifact", *valid.content.artifact_bytes[1:]),
    )
    invalid = PreparedRoadmapVersion(
        record=create_root_version(
            roadmap_slug=SLUG,
            brief_digest=_digest(content.brief_bytes),
            artifact_digests=tuple(_digest(data) for data in content.artifact_bytes),
        ),
        content=content,
    )
    _store_version(tmp_path, invalid)
    _select_accepted_version(tmp_path, invalid)
    write_domain(tmp_path, domain_artifact(entities=(entity_row(name="Live order"),)))

    loaded = load_roadmap(tmp_path, SLUG)

    assert loaded.domain is None
    assert loaded.constraints is not None
    assert loaded.absent == ()
    assert [item.filename for item in loaded.unparseable] == [DOMAIN_FILENAME]


def test_current_and_review_modes_share_the_accepted_head_bundle(tmp_path: Path) -> None:
    stored = _prepared_root_version(
        domain=domain_artifact(
            entities=(entity_row(name="Stored order"),),
            feedback=(feedback_row(),),
            removals=(removal_record(),),
        ),
        constraints=constraints_artifact(),
        components=components_artifact(),
        plans=plans_artifact(),
    )
    _store_version(tmp_path, stored)
    _select_accepted_version(tmp_path, stored)

    current = load_roadmap(tmp_path, SLUG, mode=MODE_CURRENT)
    review = load_roadmap(tmp_path, SLUG, mode=MODE_REVIEW)

    assert current.domain == review.domain
    assert current.constraints == review.constraints
    assert current.components == review.components
    assert current.plans == review.plans
    assert current.design_row_index == review.design_row_index
    assert current.feedback_index == {}
    assert current.removal_index == {}
    assert set(review.feedback_index) == {"feedback-1"}
    assert set(review.removal_index) == {"entity-1"}


def test_load_roadmap_without_accepted_head_raises_no_published_version(
    tmp_path: Path,
) -> None:
    """Deliberate: top-level artifact files never stand in for a missing head."""
    for write, artifact in (
        (write_domain, domain_artifact(entities=(entity_row(),))),
        (write_constraints, constraints_artifact()),
        (write_components, components_artifact()),
        (write_plans, plans_artifact()),
    ):
        write(tmp_path, artifact)

    with pytest.raises(NoPublishedRoadmapVersionError, match="no published version"):
        load_roadmap(tmp_path, SLUG)


def test_load_roadmap_without_a_roadmap_directory_or_with_an_empty_one_raises_no_published_version(
    tmp_path: Path,
) -> None:
    with pytest.raises(NoPublishedRoadmapVersionError):
        load_roadmap(tmp_path, SLUG)

    roadmap_dir(tmp_path, SLUG).mkdir(parents=True)
    with pytest.raises(NoPublishedRoadmapVersionError):
        load_roadmap(tmp_path, SLUG)


def test_load_roadmap_ignores_top_level_artifacts_when_head_exists(tmp_path: Path) -> None:
    """Stale top-level files differ from the head; the loaded roadmap shows the head."""
    _write_subset(tmp_path, domain=domain_artifact(entities=(entity_row(name="Stored order"),)))
    write_domain(tmp_path, domain_artifact(entities=(entity_row(name="Top-level order"),)))
    write_plans(tmp_path, plans_artifact(plans=(plan_row(title="Top-level plan"),)))

    loaded = load_roadmap(tmp_path, SLUG)

    assert loaded.domain is not None
    assert loaded.domain.entities[0].name == "Stored order"
    assert loaded.plans is not None
    assert loaded.plans.plans == ()


def test_unparseable_member_does_not_hide_other_artifacts(tmp_path: Path) -> None:
    """Deliberate read-only-view tolerance: members parse independently."""
    _write_subset(
        tmp_path,
        domain=domain_artifact(entities=(entity_row(),)),
        constraints=_BROKEN_MEMBER,
        components=components_artifact(components=(component_row(),)),
        plans=plans_artifact(plans=(plan_row(),)),
    )

    loaded = load_roadmap(tmp_path, SLUG)

    assert loaded.constraints is None
    assert loaded.absent == ()
    assert len(loaded.unparseable) == 1
    assert loaded.unparseable[0].filename == CONSTRAINTS_FILENAME
    assert loaded.domain is not None
    assert loaded.components is not None
    assert loaded.plans is not None


def test_version_store_refuses_to_hold_an_undecodable_member_so_the_view_never_sees_one(
    tmp_path: Path,
) -> None:
    """Deliberate: an undecodable member is unreachable through ``load_roadmap``.

    The unversioned reader had to degrade on non-UTF-8 files; the version store
    rejects them at creation, so the only broken-member case left is a member
    that decodes but does not parse.
    """
    with pytest.raises(RoadmapVersionError, match="strict UTF-8"):
        _write_subset(tmp_path, constraints=b"\xff\xfe not valid utf-8")


def test_load_roadmap_propagates_invalid_slug(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_roadmap(tmp_path, "bad/slug")


@pytest.mark.parametrize(
    "subset",
    [
        ("domain",),
        ("domain", "plans"),
        ("constraints", "components"),
        ("domain", "constraints", "components", "plans"),
    ],
)
def test_design_row_index_matches_feedback_target_ids_for_every_parsed_artifact(
    tmp_path: Path, subset
) -> None:
    fixtures = {
        "domain": domain_artifact(
            entities=(entity_row(),), decisions=(decision_row(id="decision-domain"),)
        ),
        "constraints": constraints_artifact(
            constraints=(constraint_row(),),
            decisions=(decision_row(id="decision-constraints"),),
        ),
        "components": components_artifact(
            components=(component_row(),),
            decisions=(decision_row(id="decision-components"),),
        ),
        "plans": plans_artifact(
            plans=(plan_row(),), decisions=(decision_row(id="decision-plans"),)
        ),
    }
    _write_subset(tmp_path, **{key: fixtures[key] for key in subset})

    loaded = load_roadmap(tmp_path, SLUG)

    expected_ids: set = set()
    for key in subset:
        artifact = getattr(loaded, key)
        assert artifact is not None
        expected_ids |= feedback_target_ids(artifact)
    assert set(loaded.design_row_index.keys()) == expected_ids


def test_design_row_index_is_mode_independent(tmp_path: Path) -> None:
    _write_subset(
        tmp_path,
        domain=domain_artifact(entities=(entity_row(),)),
        constraints=constraints_artifact(constraints=(constraint_row(),)),
    )

    current = load_roadmap(tmp_path, SLUG, mode=MODE_CURRENT)
    review = load_roadmap(tmp_path, SLUG, mode=MODE_REVIEW)

    assert current.design_row_index == review.design_row_index


def test_current_mode_exposes_no_feedback_and_no_removal(tmp_path: Path) -> None:
    _write_subset(
        tmp_path,
        domain=domain_artifact(
            entities=(entity_row(),),
            feedback=(feedback_row(),),
            removals=(removal_record(),),
        ),
    )

    loaded = load_roadmap(tmp_path, SLUG, mode=MODE_CURRENT)

    assert loaded.feedback_index == {}
    assert loaded.removal_index == {}


def test_review_mode_exposes_feedback_and_removal(tmp_path: Path) -> None:
    _write_subset(
        tmp_path,
        domain=domain_artifact(
            entities=(entity_row(),),
            feedback=(feedback_row(),),
            removals=(removal_record(),),
        ),
    )

    loaded = load_roadmap(tmp_path, SLUG, mode=MODE_REVIEW)

    assert set(loaded.feedback_index.keys()) == {"feedback-1"}
    assert set(loaded.removal_index.keys()) == {"entity-1"}


def test_feedback_index_orders_stage_then_source(tmp_path: Path) -> None:
    _write_subset(
        tmp_path,
        domain=domain_artifact(
            entities=(entity_row(),),
            feedback=(
                feedback_row(id="fb-domain-1"),
                feedback_row(id="fb-domain-2"),
            ),
        ),
        constraints=constraints_artifact(
            constraints=(constraint_row(),),
            feedback=(feedback_row(id="fb-constraints-1"),),
        ),
    )

    loaded = load_roadmap(tmp_path, SLUG, mode=MODE_REVIEW)

    assert list(loaded.feedback_index.keys()) == [
        "fb-domain-1",
        "fb-domain-2",
        "fb-constraints-1",
    ]


def test_feedback_index_preserves_both_rows_on_a_cross_artifact_id_collision(
    tmp_path: Path,
) -> None:
    _write_subset(
        tmp_path,
        domain=domain_artifact(
            entities=(entity_row(),),
            feedback=(feedback_row(id="shared", request="Domain request."),),
        ),
        constraints=constraints_artifact(
            constraints=(constraint_row(),),
            feedback=(feedback_row(id="shared", request="Constraints request."),),
        ),
    )

    loaded = load_roadmap(tmp_path, SLUG, mode=MODE_REVIEW)

    rows = loaded.feedback_index["shared"]
    assert len(rows) == 2
    assert {row.request for row in rows} == {"Domain request.", "Constraints request."}


def test_removal_index_matches_build_removal_index(tmp_path: Path) -> None:
    _write_subset(
        tmp_path,
        domain=domain_artifact(
            entities=(entity_row(),),
            removals=(removal_record(removed_id="entity-old", feedback_ids=()),),
        ),
        constraints=constraints_artifact(
            constraints=(constraint_row(),),
            removals=(removal_record(removed_id="constraint-old", feedback_ids=()),),
        ),
    )

    loaded = load_roadmap(tmp_path, SLUG, mode=MODE_REVIEW)

    expected = build_removal_index(domain=loaded.domain, constraints=loaded.constraints)
    assert loaded.removal_index == expected


# --------------------------------------------------------------------------
# build_citation_map
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "loaded_kwargs, target_id, citer_label",
    [
        (
            dict(
                domain=domain_artifact(
                    entities=(entity_row(id="entity-1", name="Order"),),
                    business_rules=(
                        business_rule_row(id="rule-1", entity_ids=("entity-1",)),
                    ),
                )
            ),
            "entity-1",
            "An order belongs to one customer.",
        ),
        (
            dict(
                domain=domain_artifact(
                    entities=(entity_row(id="entity-1", name="Order"),),
                    workflows=(
                        workflow_row(id="workflow-1", entity_ids=("entity-1",)),
                    ),
                )
            ),
            "entity-1",
            "Place order",
        ),
        (
            dict(
                constraints=constraints_artifact(
                    constraints=(
                        constraint_row(id="constraint-1", anchor_ids=("rule-1",)),
                    ),
                )
            ),
            "rule-1",
            "Checkout completes within 300ms.",
        ),
        (
            dict(
                components=components_artifact(
                    components=(
                        component_row(id="component-1", entity_ids=("entity-1",)),
                    ),
                )
            ),
            "entity-1",
            "Ordering",
        ),
        (
            dict(
                components=components_artifact(
                    components=(
                        component_row(id="component-1", store_ids=("store-1",)),
                    ),
                    stores=(store_row(id="store-1"),),
                )
            ),
            "store-1",
            "Ordering",
        ),
        (
            dict(
                components=components_artifact(
                    components=(
                        component_row(id="component-1", pattern_ids=("pattern-1",)),
                    ),
                )
            ),
            "pattern-1",
            "Ordering",
        ),
        (
            dict(
                components=components_artifact(
                    components=(
                        component_row(
                            id="component-1", constraint_ids=("constraint-1",)
                        ),
                    ),
                )
            ),
            "constraint-1",
            "Ordering",
        ),
        (
            dict(
                plans=plans_artifact(
                    plans=(plan_row(id="plan-1", component_ids=("component-1",)),),
                )
            ),
            "component-1",
            "Ordering service",
        ),
        (
            dict(
                domain=domain_artifact(
                    entities=(entity_row(id="entity-1", name="Order"),),
                    decisions=(decision_row(id="decision-1", anchor="entity-1"),),
                )
            ),
            "entity-1",
            "Keep the cart inside the order aggregate.",
        ),
    ],
    ids=[
        "business_rule.entity_ids",
        "workflow.entity_ids",
        "constraint.anchor_ids",
        "component.entity_ids",
        "component.pattern_ids",
        "component.constraint_ids",
        "component.store_ids",
        "plan.component_ids",
        "decision.anchor",
    ],
)
def test_citation_map_finds_citers_for_each_design_row_field(
    tmp_path: Path, loaded_kwargs, target_id, citer_label
) -> None:
    loaded = _loaded(tmp_path, **loaded_kwargs)
    citation_map = build_citation_map(loaded)
    assert citer_label in [citation.label for citation in citation_map[target_id]]


def test_citation_map_walks_decisions_on_every_artifact(tmp_path: Path) -> None:
    loaded = _loaded(
        tmp_path,
        domain=domain_artifact(
            entities=(entity_row(),),
            decisions=(decision_row(id="decision-domain", anchor="anchor-domain"),),
        ),
        constraints=constraints_artifact(
            constraints=(constraint_row(),),
            decisions=(
                decision_row(id="decision-constraints", anchor="anchor-constraints"),
            ),
        ),
        components=components_artifact(
            components=(component_row(),),
            decisions=(
                decision_row(id="decision-components", anchor="anchor-components"),
            ),
        ),
        plans=plans_artifact(
            plans=(plan_row(),),
            decisions=(decision_row(id="decision-plans", anchor="anchor-plans"),),
        ),
    )
    citation_map = build_citation_map(loaded)
    for anchor in (
        "anchor-domain",
        "anchor-constraints",
        "anchor-components",
        "anchor-plans",
    ):
        assert anchor in citation_map
        assert citation_map[anchor][0].field == "anchor"


def test_citation_map_finds_assumption_citers_of_consuming_plan_ids(
    tmp_path: Path,
) -> None:
    loaded = _loaded(
        tmp_path,
        plans=plans_artifact(
            plans=(plan_row(id="plan-1"),),
            assumptions=(
                assumption_row(
                    id="assumption-1",
                    statement="Payments settle same-day.",
                    consuming_plan_ids=("plan-1",),
                ),
            ),
        ),
    )
    citation_map = build_citation_map(loaded)
    citers = citation_map["plan-1"]
    assert any(
        citation.label == "Payments settle same-day."
        and citation.field == "consuming_plan_ids"
        for citation in citers
    )


def test_citation_map_keeps_walk_owned_relations_excluded(tmp_path: Path) -> None:
    loaded = _loaded(
        tmp_path,
        domain=domain_artifact(
            entities=(
                EntityRow(
                    id="entity-1",
                    name="Order",
                    fields=(
                        FieldRow(
                            name="customer",
                            type=FieldType.REFERENCE,
                            entity_id="entity-2",
                        ),
                    ),
                ),
                entity_row(id="entity-2", name="Customer"),
            ),
        ),
        plans=plans_artifact(
            plans=(
                plan_row(id="plan-1"),
                plan_row(id="plan-2", title="Fulfillment"),
            ),
            ordering=(
                OrderingEntry(
                    plan_id="plan-1",
                    depends_on=("plan-2",),
                    assumption_targets=("plan-2",),
                ),
            ),
        ),
    )
    citation_map = build_citation_map(loaded)
    assert "entity-2" not in citation_map
    assert "plan-2" not in citation_map


# --------------------------------------------------------------------------
# review-mode-only citation edges
# --------------------------------------------------------------------------


def test_review_mode_adds_feedback_target_citers(tmp_path: Path) -> None:
    domain = domain_artifact(
        entities=(entity_row(id="entity-1", name="Order"),),
        feedback=(
            feedback_row(
                id="feedback-1",
                request="Split the order entity.",
                target=FeedbackTarget(kind=FeedbackTargetKind.ROW, row_id="entity-1"),
            ),
        ),
    )

    review = _loaded(tmp_path, mode=MODE_REVIEW, domain=domain)
    review_citers = build_citation_map(review)["entity-1"]
    assert any(
        citation.label == "Split the order entity." and citation.field == "row_id"
        for citation in review_citers
    )

    current = _loaded(tmp_path, mode=MODE_CURRENT, domain=domain)
    current_citers = build_citation_map(current).get("entity-1", ())
    assert not any(citation.field == "row_id" for citation in current_citers)


def test_review_mode_adds_removal_feedback_citers(tmp_path: Path) -> None:
    domain = domain_artifact(
        entities=(entity_row(id="entity-1", name="Order"),),
        removals=(
            removal_record(
                removed_id="entity-old",
                rationale="Superseded by entity-1.",
                feedback_ids=("feedback-1",),
            ),
        ),
    )

    review = _loaded(tmp_path, mode=MODE_REVIEW, domain=domain)
    review_citers = build_citation_map(review)["feedback-1"]
    assert any(citation.field == "feedback_ids" for citation in review_citers)

    current = _loaded(tmp_path, mode=MODE_CURRENT, domain=domain)
    current_citers = build_citation_map(current).get("feedback-1", ())
    assert not any(citation.field == "feedback_ids" for citation in current_citers)


def test_artifact_scope_feedback_produces_no_citation_edge(tmp_path: Path) -> None:
    domain = domain_artifact(
        entities=(entity_row(id="entity-1", name="Order"),),
        feedback=(
            feedback_row(
                id="feedback-1",
                request="Reconsider this whole file.",
                target=FeedbackTarget(kind=FeedbackTargetKind.ARTIFACT),
            ),
        ),
    )

    for mode in (MODE_CURRENT, MODE_REVIEW):
        loaded = _loaded(tmp_path, mode=mode, domain=domain)
        citation_map = build_citation_map(loaded)
        for citers in citation_map.values():
            assert all(citation.field != "row_id" for citation in citers)


# --------------------------------------------------------------------------
# resolve_citation_subject
# --------------------------------------------------------------------------


def test_resolve_citation_subject_undeclared_id_is_undeclared(tmp_path: Path) -> None:
    loaded = _loaded(tmp_path, domain=domain_artifact(entities=(entity_row(),)))
    resolution = resolve_citation_subject("nonexistent", loaded)
    assert resolution.status == RESOLUTION_DANGLING


def test_resolve_citation_subject_declared_id_with_no_citers_is_stated_empty(
    tmp_path: Path,
) -> None:
    loaded = _loaded(
        tmp_path, domain=domain_artifact(entities=(entity_row(id="entity-1"),))
    )
    resolution = resolve_citation_subject("entity-1", loaded)
    citation_map = build_citation_map(loaded)
    assert resolution.status == RESOLUTION_RESOLVED
    assert citation_map.get("entity-1", ()) == ()


def test_resolve_citation_subject_ambiguous_id_names_every_match(
    tmp_path: Path,
) -> None:
    loaded = _loaded(
        tmp_path,
        domain=domain_artifact(
            entities=(entity_row(id="dup", name="Entity label"),),
            workflows=(workflow_row(id="dup", name="Workflow label"),),
        ),
    )
    resolution = resolve_citation_subject("dup", loaded)
    assert resolution.status == RESOLUTION_AMBIGUOUS
    assert resolution.matches == ("Entity label", "Workflow label")


def test_resolve_citation_subject_feedback_id_three_outcomes(tmp_path: Path) -> None:
    domain = domain_artifact(
        entities=(entity_row(),),
        feedback=(feedback_row(id="feedback-1", request="Split the entity."),),
    )

    review = _loaded(tmp_path, mode=MODE_REVIEW, domain=domain)
    review_resolution = resolve_citation_subject("feedback-1", review)
    assert review_resolution.status == RESOLUTION_RESOLVED
    assert review_resolution.text == "Split the entity."

    current = _loaded(tmp_path, mode=MODE_CURRENT, domain=domain)
    current_resolution = resolve_citation_subject("feedback-1", current)
    assert current_resolution.status == RESOLUTION_OUT_OF_SCOPE_FOR_MODE
    assert current_resolution.status not in (RESOLUTION_RESOLVED, RESOLUTION_DANGLING)

    undeclared_resolution = resolve_citation_subject("nonexistent", current)
    assert undeclared_resolution.status == RESOLUTION_DANGLING


def test_resolve_citation_subject_removed_id_resolves_through_the_removal_index(
    tmp_path: Path,
) -> None:
    loaded = _loaded(
        tmp_path,
        mode=MODE_REVIEW,
        domain=domain_artifact(
            entities=(entity_row(id="entity-1"),),
            removals=(
                removal_record(
                    removed_id="entity-old", rationale="Dropped after review."
                ),
            ),
        ),
    )
    resolution = resolve_citation_subject("entity-old", loaded)
    assert resolution.status == RESOLUTION_RESOLVED
    assert "entity-old" in resolution.text
    assert "Dropped after review." in resolution.text


def test_resolve_citation_subject_removed_id_is_out_of_scope_under_current_mode(
    tmp_path: Path,
) -> None:
    domain = domain_artifact(
        entities=(entity_row(),),
        removals=(
            removal_record(removed_id="entity-old", rationale="Dropped after review."),
        ),
    )

    current = _loaded(tmp_path, mode=MODE_CURRENT, domain=domain)
    current_resolution = resolve_citation_subject("entity-old", current)
    assert current_resolution.status == RESOLUTION_OUT_OF_SCOPE_FOR_MODE
    assert current_resolution.status not in (RESOLUTION_RESOLVED, RESOLUTION_DANGLING)

    undeclared_resolution = resolve_citation_subject("nonexistent", current)
    assert undeclared_resolution.status == RESOLUTION_DANGLING


def test_resolve_citation_subject_removal_collision_is_ambiguous(
    tmp_path: Path,
) -> None:
    loaded = _loaded(
        tmp_path,
        mode=MODE_REVIEW,
        domain=domain_artifact(
            entities=(entity_row(),),
            removals=(removal_record(removed_id="shared", rationale="Domain reason"),),
        ),
        constraints=constraints_artifact(
            constraints=(constraint_row(),),
            removals=(
                removal_record(removed_id="shared", rationale="Constraints reason"),
            ),
        ),
    )
    resolution = resolve_citation_subject("shared", loaded)
    assert resolution.status == RESOLUTION_AMBIGUOUS
    assert len(resolution.matches) == 2
    assert all("shared" in label for label in resolution.matches)


def test_resolve_citation_subject_feedback_collision_is_ambiguous(
    tmp_path: Path,
) -> None:
    loaded = _loaded(
        tmp_path,
        mode=MODE_REVIEW,
        domain=domain_artifact(
            entities=(entity_row(),),
            feedback=(feedback_row(id="shared", request="Domain request."),),
        ),
        constraints=constraints_artifact(
            constraints=(constraint_row(),),
            feedback=(feedback_row(id="shared", request="Constraints request."),),
        ),
    )
    resolution = resolve_citation_subject("shared", loaded)
    assert resolution.status == RESOLUTION_AMBIGUOUS
    assert set(resolution.matches) == {"Domain request.", "Constraints request."}


def test_resolve_citation_subject_design_row_wins_over_a_same_id_feedback_row(
    tmp_path: Path,
) -> None:
    loaded = _loaded(
        tmp_path,
        mode=MODE_REVIEW,
        domain=domain_artifact(
            entities=(entity_row(id="shared", name="Order"),),
            feedback=(feedback_row(id="shared", request="Split the order entity."),),
        ),
    )
    resolution = resolve_citation_subject("shared", loaded)
    assert resolution.status == RESOLUTION_RESOLVED
    assert resolution.text == "Order"


# --------------------------------------------------------------------------
# render_reverse_index
# --------------------------------------------------------------------------


def test_full_map_lists_every_declared_id_including_uncited_ones(
    tmp_path: Path,
) -> None:
    domain = domain_artifact(
        entities=(entity_row(id="entity-1", name="Order"),),
        feedback=(feedback_row(id="feedback-1", request="Split the entity."),),
    )

    review = _loaded(tmp_path, mode=MODE_REVIEW, domain=domain)
    text = render_reverse_index(review)
    assert "entity-1" in text
    assert "feedback-1" in text
    assert "nothing cites this" in text

    current = _loaded(tmp_path, mode=MODE_CURRENT, domain=domain)
    current_text = render_reverse_index(current)
    assert "entity-1" in current_text
    assert "feedback-1" not in current_text


def test_full_map_labels_same_named_patterns_by_scope(tmp_path: Path) -> None:
    loaded = _loaded(
        tmp_path,
        components=components_artifact(
            system_patterns=(pattern_row(id="pattern-system", name="Command"),),
            component_patterns=(pattern_row(id="pattern-component", name="Command"),),
        ),
    )
    text = render_reverse_index(loaded)
    assert "system pattern: Command" in text
    assert "component pattern: Command" in text


def test_citer_labels_match_display_label_exactly(tmp_path: Path) -> None:
    loaded = _loaded(
        tmp_path,
        domain=domain_artifact(
            entities=(entity_row(id="entity-1", name="Order"),),
            business_rules=(
                business_rule_row(
                    id="rule-1",
                    statement="An order belongs to one customer.",
                    entity_ids=("entity-1",),
                ),
            ),
        ),
    )
    citation_map = build_citation_map(loaded)
    rule = loaded.domain.business_rules[0]
    citation = citation_map["entity-1"][0]
    assert citation.label == display_label(rule)


def test_citation_map_and_full_map_render_in_stage_then_source_order(
    tmp_path: Path,
) -> None:
    loaded = _loaded(
        tmp_path,
        domain=domain_artifact(
            business_rules=(
                business_rule_row(
                    id="rule-domain", statement="Domain rule.", entity_ids=("shared",)
                ),
            ),
        ),
        constraints=constraints_artifact(
            constraints=(
                constraint_row(
                    id="constraint-constraints",
                    statement="Constraints statement.",
                    anchor_ids=("shared",),
                ),
            ),
        ),
        components=components_artifact(
            components=(
                component_row(
                    id="component-components",
                    name="Components component.",
                    entity_ids=("shared",),
                ),
            ),
        ),
    )
    citation_map = build_citation_map(loaded)
    labels = [citation.label for citation in citation_map["shared"]]
    assert labels == ["Domain rule.", "Constraints statement.", "Components component."]

    text = render_reverse_index(loaded)
    domain_pos = text.index("rule-domain:")
    constraints_pos = text.index("constraint-constraints:")
    components_pos = text.index("component-components:")
    assert domain_pos < constraints_pos < components_pos


def test_reverse_index_render_names_its_mode_and_the_unparseable_files(
    tmp_path: Path,
) -> None:
    _write_subset(tmp_path, domain=domain_artifact(entities=(entity_row(),)), constraints=_BROKEN_MEMBER)

    loaded = load_roadmap(tmp_path, SLUG, mode=MODE_REVIEW)
    text = render_reverse_index(loaded)

    assert MODE_REVIEW in text
    assert CONSTRAINTS_FILENAME in text
    # Stored members are never absent, so only the broken one is named.
    assert COMPONENTS_FILENAME not in text
    assert PLANS_FILENAME not in text


def test_reverse_index_render_is_the_same_on_repeat_calls(tmp_path: Path) -> None:
    loaded = _loaded(
        tmp_path,
        mode=MODE_REVIEW,
        domain=domain_artifact(
            entities=(entity_row(),),
            business_rules=(business_rule_row(entity_ids=("entity-1",)),),
            feedback=(feedback_row(),),
            removals=(removal_record(),),
        ),
    )
    assert render_reverse_index(loaded) == render_reverse_index(loaded)
    assert render_reverse_index(loaded, "entity-1") == render_reverse_index(
        loaded, "entity-1"
    )


def test_reverse_index_render_has_no_removals_heading_or_list(tmp_path: Path) -> None:
    loaded = _loaded(
        tmp_path,
        mode=MODE_REVIEW,
        domain=domain_artifact(
            entities=(entity_row(),),
            feedback=(
                feedback_row(id="feedback-1", request="Remove the entity."),
            ),
            removals=(
                removal_record(
                    removed_id="entity-old",
                    rationale="No longer needed.",
                    feedback_ids=("feedback-1",),
                ),
            ),
        ),
    )
    text = render_reverse_index(loaded)
    lowered = text.lower()
    assert "removals" not in lowered
    assert "removal:" not in lowered
    assert "entity-old" in text
    assert "No longer needed." in text


def test_reverse_index_full_listing_renders_a_colliding_feedback_id_once(
    tmp_path: Path,
) -> None:
    loaded = _loaded(
        tmp_path,
        mode=MODE_REVIEW,
        domain=domain_artifact(
            entities=(entity_row(id="shared-id", name="Order"),),
            feedback=(feedback_row(id="shared-id", request="Rename the order."),),
        ),
    )
    text = render_reverse_index(loaded)
    assert text.count("shared-id:") == 1


# --------------------------------------------------------------------------
# build_citation_map — kind
# --------------------------------------------------------------------------


def test_citation_carries_the_citer_kind(tmp_path: Path) -> None:
    loaded = _loaded(
        tmp_path,
        domain=domain_artifact(
            entities=(entity_row(id="entity-1", name="Order"),),
            business_rules=(
                business_rule_row(id="rule-1", entity_ids=("entity-1",)),
            ),
        ),
    )
    citation_map = build_citation_map(loaded)
    citation = citation_map["entity-1"][0]
    citer_entry = loaded.design_row_index["rule-1"][0]
    assert citation.kind == citer_entry.kind


# --------------------------------------------------------------------------
# render_traceability_walk
# --------------------------------------------------------------------------


def test_walk_orders_plans_by_ordering_sequence(tmp_path: Path) -> None:
    plans = plans_artifact(
        plans=(
            plan_row(id="plan-a", title="Plan A"),
            plan_row(id="plan-b", title="Plan B"),
        ),
        ordering=(
            OrderingEntry(plan_id="plan-b"),
            OrderingEntry(plan_id="plan-a"),
        ),
    )
    loaded = _loaded(tmp_path, plans=plans)
    text = render_traceability_walk(loaded, tmp_path)
    assert text.index("Plan B") < text.index("Plan A")


def test_walk_notes_an_unavailable_reason_and_still_renders_the_rest(
    tmp_path: Path,
) -> None:
    plans = plans_artifact(
        plans=(plan_row(id="plan-a", title="Plan A"),),
        ordering=(OrderingEntry(plan_id="plan-a"),),
    )
    loaded = _loaded(tmp_path, plans=plans)

    text = _render_traceability_walk(
        loaded, tmp_path, {}, unavailable_reason="bad sidecar"
    )

    assert "seed states unavailable: bad sidecar" in text
    assert "Plan A" in text


def test_walk_leads_with_intent_delivery_shape_and_non_goals(tmp_path: Path) -> None:
    plans = plans_artifact(
        plans=(
            plan_row(
                id="plan-platform",
                title="Platform foundations",
                disposition=PlanDisposition.CROSS_CUTTING,
                component_ids=(),
                intent="Give every delivery slice a shared deployment baseline.",
                non_goals=("Implementing any product-specific workflow.",),
            ),
        ),
        ordering=(OrderingEntry(plan_id="plan-platform"),),
    )
    loaded = _loaded(tmp_path, plans=plans)

    text = render_traceability_walk(loaded, tmp_path)

    assert "intent:\n    Give every delivery slice a shared deployment baseline." in text
    assert "delivery shape: cross-cutting (component ownership is not required)" in text
    assert "non-goals:\n    - Implementing any product-specific workflow." in text
    assert text.index("intent:") < text.index("depends_on:")


def test_walk_annotates_legacy_plan_rows_without_review_context(tmp_path: Path) -> None:
    plans = plans_artifact(
        plans=(plan_row(intent="", non_goals=()),),
        ordering=(OrderingEntry(plan_id="plan-1"),),
    )
    loaded = _loaded(tmp_path, plans=plans)

    text = render_traceability_walk(loaded, tmp_path)

    assert "⚠ intent not recorded" in text
    assert "⚠ non-goals not recorded" in text


def test_walk_appends_unordered_plan_row_after_the_sequence(tmp_path: Path) -> None:
    plans = plans_artifact(
        plans=(
            plan_row(id="plan-a", title="Plan A"),
            plan_row(id="plan-b", title="Plan B"),
        ),
        ordering=(OrderingEntry(plan_id="plan-a"),),
    )
    loaded = _loaded(tmp_path, plans=plans)
    text = render_traceability_walk(loaded, tmp_path)
    assert "⚠ not in ordering: Plan B" in text
    assert text.index("Plan A") < text.index("⚠ not in ordering: Plan B")


def test_walk_marks_ordering_entry_naming_no_plan_row_as_dangling(
    tmp_path: Path,
) -> None:
    plans = plans_artifact(
        plans=(plan_row(id="plan-a", title="Plan A"),),
        ordering=(
            OrderingEntry(plan_id="plan-a"),
            OrderingEntry(plan_id="ghost-plan"),
        ),
    )
    loaded = _loaded(tmp_path, plans=plans)
    text = render_traceability_walk(loaded, tmp_path)
    assert resolve_id("ghost-plan", loaded.design_row_index).text in text


def test_walk_marks_ordering_entry_resolving_to_a_non_plan_row(
    tmp_path: Path,
) -> None:
    plans = plans_artifact(
        plans=(plan_row(id="plan-a", title="Plan A"),),
        ordering=(
            OrderingEntry(plan_id="assumption-1"),
            OrderingEntry(plan_id="plan-a"),
        ),
        assumptions=(assumption_row(id="assumption-1", statement="Single device."),),
    )
    loaded = _loaded(tmp_path, plans=plans)

    text = render_traceability_walk(loaded, tmp_path)

    assert "⚠ ordering entry does not name a plan: Single device." in text


def test_walk_marks_repeated_dangling_ordering_entry_with_its_own_diagnostic(
    tmp_path: Path,
) -> None:
    # A repeated malformed id keeps its own diagnostic rather than collapsing
    # into a generic "duplicate ordering entry" with no mention that the id
    # is also undefined -- mirrors roadmap_html.py's ``_plans_block``.
    plans = plans_artifact(
        plans=(),
        ordering=(
            OrderingEntry(plan_id="ghost-plan"),
            OrderingEntry(plan_id="ghost-plan"),
        ),
    )
    loaded = _loaded(tmp_path, plans=plans)
    text = render_traceability_walk(loaded, tmp_path)
    assert "⚠ undefined: ghost-plan" in text
    assert "repeated, ⚠ undefined: ghost-plan" in text
    # The genuinely generic case (a repeat of an id that DOES resolve to a
    # real plan) is unaffected by this branch.
    assert "⚠ duplicate ordering entry:" not in text


def test_walk_marks_repeated_resolved_to_non_plan_ordering_entry(
    tmp_path: Path,
) -> None:
    plans = plans_artifact(
        plans=(plan_row(id="plan-a", title="Plan A"),),
        ordering=(
            OrderingEntry(plan_id="assumption-1"),
            OrderingEntry(plan_id="assumption-1"),
            OrderingEntry(plan_id="plan-a"),
        ),
        assumptions=(assumption_row(id="assumption-1", statement="Single device."),),
    )
    loaded = _loaded(tmp_path, plans=plans)

    text = render_traceability_walk(loaded, tmp_path)

    assert "⚠ ordering entry does not name a plan: Single device." in text
    assert (
        "⚠ ordering entry does not name a plan (repeated): Single device."
        in text
    )


def test_walk_marks_repeated_ordering_entry_as_duplicate_not_a_second_render(
    tmp_path: Path,
) -> None:
    plans = plans_artifact(
        plans=(plan_row(id="plan-a", title="Plan A"),),
        ordering=(
            OrderingEntry(plan_id="plan-a"),
            OrderingEntry(plan_id="plan-a"),
        ),
    )
    loaded = _loaded(tmp_path, plans=plans)
    text = render_traceability_walk(loaded, tmp_path)
    assert "⚠ duplicate ordering entry: Plan A" in text
    # A second full render would repeat the plan's own draft-seed marker.
    assert text.count("plan-a.md") == 1


def test_walk_colliding_plan_ids_render_ambiguous_not_a_silent_collapse(
    tmp_path: Path,
) -> None:
    plans = plans_artifact(
        plans=(
            plan_row(id="dup-plan", title="Plan A"),
            plan_row(id="dup-plan", title="Plan B"),
        ),
        ordering=(OrderingEntry(plan_id="dup-plan"),),
    )
    loaded = _loaded(tmp_path, plans=plans)
    text = render_traceability_walk(loaded, tmp_path)
    assert "⚠ ambiguous: dup-plan" in text
    assert "Plan A" in text
    assert "Plan B" in text
    assert "⚠ not in ordering" not in text


def test_walk_colliding_plan_ids_absent_from_ordering_render_one_ambiguous_marker(
    tmp_path: Path,
) -> None:
    plans = plans_artifact(
        plans=(
            plan_row(id="dup-plan", title="Plan A"),
            plan_row(id="dup-plan", title="Plan B"),
        ),
        ordering=(),
    )
    loaded = _loaded(tmp_path, plans=plans)
    text = render_traceability_walk(loaded, tmp_path)
    assert text.count("dup-plan") == 1
    assert "Plan A" in text
    assert "Plan B" in text
    assert text.count("⚠ not in ordering: Plan A") == 0
    assert text.count("⚠ not in ordering: Plan B") == 0


def test_walk_resolves_component_ids_and_opens_their_entity_pattern_constraint_lists(
    tmp_path: Path,
) -> None:
    domain = domain_artifact(entities=(entity_row(id="entity-1", name="Order"),))
    constraints = constraints_artifact(
        constraints=(
            constraint_row(
                id="constraint-1", statement="Checkout completes within 300ms."
            ),
        )
    )
    components = components_artifact(
        system_patterns=(pattern_row(id="pattern-1", name="Command"),),
        components=(
            component_row(
                id="component-1",
                name="Ordering",
                entity_ids=("entity-1",),
                pattern_ids=("pattern-1",),
                constraint_ids=("constraint-1",),
            ),
        ),
    )
    plans = plans_artifact(
        plans=(plan_row(id="plan-1", component_ids=("component-1",)),),
        ordering=(OrderingEntry(plan_id="plan-1"),),
    )
    loaded = _loaded(
        tmp_path, domain=domain, constraints=constraints, components=components, plans=plans
    )
    text = render_traceability_walk(loaded, tmp_path)
    assert "Ordering" in text
    assert "Order" in text
    assert "system pattern: Command" in text
    assert "Checkout completes within 300ms." in text


def test_walk_finds_governing_business_rules_and_workflows_for_an_entity(
    tmp_path: Path,
) -> None:
    domain = domain_artifact(
        entities=(entity_row(id="entity-1", name="Order"),),
        business_rules=(
            business_rule_row(
                id="rule-1",
                statement="An order belongs to one customer.",
                entity_ids=("entity-1",),
            ),
        ),
        workflows=(
            workflow_row(id="workflow-1", name="Place order", entity_ids=("entity-1",)),
        ),
    )
    components = components_artifact(
        components=(component_row(id="component-1", entity_ids=("entity-1",)),)
    )
    plans = plans_artifact(
        plans=(plan_row(id="plan-1", component_ids=("component-1",)),),
        ordering=(OrderingEntry(plan_id="plan-1"),),
    )
    loaded = _loaded(tmp_path, domain=domain, components=components, plans=plans)
    text = render_traceability_walk(loaded, tmp_path)
    assert "An order belongs to one customer." in text
    assert "Place order" in text


def test_walk_excludes_non_governing_citers_from_the_entity_section(
    tmp_path: Path,
) -> None:
    domain = domain_artifact(
        entities=(entity_row(id="entity-1", name="Order"),),
        decisions=(
            decision_row(
                id="decision-x", chosen_option="Unrelated decision.", anchor="entity-1"
            ),
        ),
    )
    constraints = constraints_artifact(
        constraints=(
            constraint_row(
                id="constraint-x",
                statement="Unrelated constraint.",
                anchor_ids=("entity-1",),
            ),
        )
    )
    components = components_artifact(
        components=(
            component_row(id="component-1", name="Ordering", entity_ids=("entity-1",)),
            component_row(
                id="component-2", name="Shadow component", entity_ids=("entity-1",)
            ),
        )
    )
    plans = plans_artifact(
        plans=(plan_row(id="plan-1", component_ids=("component-1",)),),
        ordering=(OrderingEntry(plan_id="plan-1"),),
    )
    loaded = _loaded(
        tmp_path, domain=domain, constraints=constraints, components=components, plans=plans
    )
    text = render_traceability_walk(loaded, tmp_path)
    assert "Shadow component" not in text
    assert "Unrelated constraint." not in text
    assert "Unrelated decision." not in text


def test_walk_resolves_pattern_ids_naming_scope(tmp_path: Path) -> None:
    components = components_artifact(
        system_patterns=(pattern_row(id="pattern-system", name="Command"),),
        component_patterns=(pattern_row(id="pattern-component", name="Command"),),
        components=(
            component_row(
                id="component-1", pattern_ids=("pattern-system", "pattern-component")
            ),
        ),
    )
    plans = plans_artifact(
        plans=(plan_row(id="plan-1", component_ids=("component-1",)),),
        ordering=(OrderingEntry(plan_id="plan-1"),),
    )
    loaded = _loaded(tmp_path, components=components, plans=plans)
    text = render_traceability_walk(loaded, tmp_path)
    assert "system pattern: Command" in text
    assert "component pattern: Command" in text


def test_walk_resolves_constraint_ids_as_leaves(tmp_path: Path) -> None:
    constraints = constraints_artifact(
        constraints=(
            constraint_row(
                id="constraint-1",
                statement="Checkout completes within 300ms.",
                anchor_ids=("entity-x",),
            ),
        )
    )
    components = components_artifact(
        components=(component_row(id="component-1", constraint_ids=("constraint-1",)),)
    )
    plans = plans_artifact(
        plans=(plan_row(id="plan-1", component_ids=("component-1",)),),
        ordering=(OrderingEntry(plan_id="plan-1"),),
    )
    loaded = _loaded(tmp_path, constraints=constraints, components=components, plans=plans)
    text = render_traceability_walk(loaded, tmp_path)
    assert "Checkout completes within 300ms." in text
    assert "entity-x" not in text


def test_walk_prints_field_row_entity_id_target_without_expanding_it(
    tmp_path: Path,
) -> None:
    domain = domain_artifact(
        entities=(
            EntityRow(
                id="entity-1",
                name="Order",
                fields=(
                    FieldRow(
                        name="customer", type=FieldType.REFERENCE, entity_id="entity-2"
                    ),
                ),
            ),
            EntityRow(id="entity-2", name="Customer", fields=()),
        ),
        business_rules=(
            business_rule_row(
                id="rule-2", statement="Customer rule.", entity_ids=("entity-2",)
            ),
        ),
    )
    components = components_artifact(
        components=(component_row(id="component-1", entity_ids=("entity-1",)),)
    )
    plans = plans_artifact(
        plans=(plan_row(id="plan-1", component_ids=("component-1",)),),
        ordering=(OrderingEntry(plan_id="plan-1"),),
    )
    loaded = _loaded(tmp_path, domain=domain, components=components, plans=plans)
    text = render_traceability_walk(loaded, tmp_path)
    assert "customer: Customer" in text
    # entity-2's own governs-list is not re-rendered through the field target.
    assert "Customer rule." not in text


def test_walk_reference_field_with_no_entity_id_is_not_a_fake_dangling_marker(
    tmp_path: Path,
) -> None:
    domain = domain_artifact(
        entities=(
            EntityRow(
                id="entity-1",
                name="Order",
                fields=(
                    FieldRow(name="customer", type=FieldType.REFERENCE, entity_id=None),
                ),
            ),
        )
    )
    components = components_artifact(
        components=(component_row(id="component-1", entity_ids=("entity-1",)),)
    )
    plans = plans_artifact(
        plans=(plan_row(id="plan-1", component_ids=("component-1",)),),
        ordering=(OrderingEntry(plan_id="plan-1"),),
    )
    loaded = _loaded(tmp_path, domain=domain, components=components, plans=plans)
    text = render_traceability_walk(loaded, tmp_path)
    assert "⚠ missing entity_id: customer" in text
    assert "⚠ undefined: None" not in text


def test_walk_prints_depends_on_and_assumption_targets_resolved(tmp_path: Path) -> None:
    plans = plans_artifact(
        plans=(
            plan_row(id="plan-a", title="Plan A"),
            plan_row(id="plan-b", title="Plan B"),
            plan_row(id="plan-c", title="Plan C"),
        ),
        ordering=(
            OrderingEntry(plan_id="plan-a"),
            OrderingEntry(plan_id="plan-b"),
            OrderingEntry(
                plan_id="plan-c",
                depends_on=("plan-a",),
                assumption_targets=("plan-b",),
            ),
        ),
    )
    loaded = _loaded(tmp_path, plans=plans)
    text = render_traceability_walk(loaded, tmp_path)
    assert re.search(r"depends_on:\s*\n\s*- Plan A", text)
    assert re.search(r"assumption_targets:\s*\n\s*- Plan B", text)


def test_walk_prints_assumptions_naming_this_plan_via_the_citation_map(
    tmp_path: Path,
) -> None:
    plans = plans_artifact(
        plans=(plan_row(id="plan-1", title="Plan One"),),
        ordering=(OrderingEntry(plan_id="plan-1"),),
        assumptions=(
            assumption_row(
                id="assumption-1",
                statement="Payments settle same-day.",
                consuming_plan_ids=("plan-1",),
            ),
        ),
    )
    loaded = _loaded(tmp_path, plans=plans)
    text = render_traceability_walk(loaded, tmp_path)
    assert re.search(r"assumptions:\s*\n\s*- Payments settle same-day\.", text)


@pytest.mark.parametrize("kind", ["component_ids", "entity_ids", "pattern_ids"])
def test_walk_dangling_and_ambiguous_references_are_leaves(
    tmp_path: Path, kind
) -> None:
    def build(ref_id, *, ambiguous):
        kwargs = {}
        if ambiguous:
            kwargs["domain"] = domain_artifact(
                entities=(entity_row(id=ref_id, name="Dup entity"),)
            )
            kwargs["constraints"] = constraints_artifact(
                constraints=(
                    constraint_row(id=ref_id, statement="Dup constraint."),
                )
            )
        if kind == "component_ids":
            kwargs["plans"] = plans_artifact(
                plans=(plan_row(id="plan-1", component_ids=(ref_id,)),),
                ordering=(OrderingEntry(plan_id="plan-1"),),
            )
        else:
            field = "entity_ids" if kind == "entity_ids" else "pattern_ids"
            kwargs["components"] = components_artifact(
                components=(component_row(id="component-1", **{field: (ref_id,)}),)
            )
            kwargs["plans"] = plans_artifact(
                plans=(plan_row(id="plan-1", component_ids=("component-1",)),),
                ordering=(OrderingEntry(plan_id="plan-1"),),
            )
        return kwargs

    forbidden = {"component_ids": "entities:", "entity_ids": "governs:"}.get(kind)

    dangling_dir = tmp_path / "dangling"
    dangling = _loaded(dangling_dir, **build("ghost-ref", ambiguous=False))
    dangling_text = render_traceability_walk(dangling, dangling_dir)
    assert "⚠ undefined: ghost-ref" in dangling_text
    if forbidden:
        assert forbidden not in dangling_text

    ambiguous_dir = tmp_path / "ambiguous"
    ambiguous = _loaded(ambiguous_dir, **build("dup-ref", ambiguous=True))
    ambiguous_text = render_traceability_walk(ambiguous, ambiguous_dir)
    assert "⚠ ambiguous: dup-ref" in ambiguous_text
    if forbidden:
        assert forbidden not in ambiguous_text


def test_walk_component_ids_naming_a_uniquely_resolved_non_component_row_is_a_leaf(
    tmp_path: Path,
) -> None:
    domain = domain_artifact(entities=(entity_row(id="shared-id", name="Order"),))
    plans = plans_artifact(
        plans=(plan_row(id="plan-1", component_ids=("shared-id",)),),
        ordering=(OrderingEntry(plan_id="plan-1"),),
    )
    loaded = _loaded(tmp_path, domain=domain, plans=plans)
    text = render_traceability_walk(loaded, tmp_path)
    assert "⚠ wrong kind: shared-id is a entity, not component" in text
    assert "entities:" not in text
    assert "- Order" not in text


def test_walk_entity_ids_naming_a_uniquely_resolved_non_entity_row_is_a_leaf(
    tmp_path: Path,
) -> None:
    constraints = constraints_artifact(
        constraints=(constraint_row(id="shared-id", statement="Dup-kind constraint."),)
    )
    components = components_artifact(
        components=(component_row(id="component-1", entity_ids=("shared-id",)),)
    )
    plans = plans_artifact(
        plans=(plan_row(id="plan-1", component_ids=("component-1",)),),
        ordering=(OrderingEntry(plan_id="plan-1"),),
    )
    loaded = _loaded(tmp_path, constraints=constraints, components=components, plans=plans)
    text = render_traceability_walk(loaded, tmp_path)
    assert "⚠ wrong kind: shared-id is a constraint, not entity" in text
    assert "governs:" not in text
    assert "- Dup-kind constraint." not in text


def test_walk_reference_field_naming_a_non_entity_row_uses_the_kind_marker(
    tmp_path: Path,
) -> None:
    constraints = constraints_artifact(
        constraints=(constraint_row(id="shared-id", statement="Not an entity."),)
    )
    domain = domain_artifact(
        entities=(
            EntityRow(
                id="entity-1",
                name="Order",
                fields=(
                    FieldRow(
                        name="target",
                        type=FieldType.REFERENCE,
                        entity_id="shared-id",
                    ),
                ),
            ),
        )
    )
    components = components_artifact(
        components=(component_row(id="component-1", entity_ids=("entity-1",)),)
    )
    plans = plans_artifact(
        plans=(plan_row(id="plan-1", component_ids=("component-1",)),),
        ordering=(OrderingEntry(plan_id="plan-1"),),
    )
    loaded = _loaded(
        tmp_path, domain=domain, constraints=constraints, components=components, plans=plans
    )
    text = render_traceability_walk(loaded, tmp_path)
    assert "target: ⚠ wrong kind: shared-id is a constraint, not entity" in text
    assert "Not an entity." not in text


def test_walk_prints_seed_path_and_provenance_for_a_current_seed(
    tmp_path: Path,
) -> None:
    plan = plan_row(id="plan-1", title="Plan One")
    plans = plans_artifact(plans=(plan,), ordering=(OrderingEntry(plan_id="plan-1"),))
    loaded = _loaded(tmp_path, plans=plans)
    write_draft_seed(
        tmp_path,
        plan,
        DraftSeedProvenance(roadmap_components=("component-1", "component-2")),
    )
    text = render_traceability_walk(
        loaded,
        tmp_path,
        draft_seed_classifications(**{plan.id: DRAFT_SEED_STATE_CURRENT}),
    )
    assert "draft seed: seeds/plan-1.md" in text
    assert re.search(r"roadmap_components:\s*\n\s*- component-1", text)
    assert "component-2" in text


@pytest.mark.parametrize(
    "state",
    (
        DRAFT_SEED_STATE_MISSING,
        DRAFT_SEED_STATE_STALE,
        DRAFT_SEED_STATE_MALFORMED,
        DRAFT_SEED_STATE_PATH_ESCAPING,
        DRAFT_SEED_STATE_DUPLICATE,
        DRAFT_SEED_STATE_DIGEST_MISMATCHED,
    ),
)
def test_walk_names_each_non_current_state_from_the_classification(
    tmp_path: Path, state: str
) -> None:
    plan = plan_row(id="plan-1", title="Plan One")
    plans = plans_artifact(plans=(plan,), ordering=(OrderingEntry(plan_id="plan-1"),))
    loaded = _loaded(tmp_path, plans=plans)
    seed_path = resolve_draft_seed_path(tmp_path, SLUG, plan.draft_seed_path)
    seed_path.parent.mkdir(parents=True, exist_ok=True)
    seed_path.write_text("valid-looking file\n", encoding="utf-8")

    text = render_traceability_walk(
        loaded,
        tmp_path,
        {
            plan.id: DraftSeedClassification(
                plan_id=plan.id,
                state=state,
                detail=f"detail for {state}",
            )
        },
    )

    assert f"draft seed {state}: {plan.draft_seed_path}" in text
    assert f"detail for {state}" in text


def test_walk_current_seed_whose_file_vanished_degrades_to_a_marker_not_a_raise(
    tmp_path: Path,
) -> None:
    plan = plan_row(id="plan-1", title="Plan One")
    plans = plans_artifact(plans=(plan,), ordering=(OrderingEntry(plan_id="plan-1"),))
    loaded = _loaded(tmp_path, plans=plans)

    text = render_traceability_walk(
        loaded,
        tmp_path,
        draft_seed_classifications(**{plan.id: DRAFT_SEED_STATE_CURRENT}),
    )

    assert f"current draft seed unreadable: {plan.draft_seed_path}" in text


def test_walk_plan_missing_from_the_classification_map_renders_a_marker(
    tmp_path: Path,
) -> None:
    plan = plan_row(id="plan-1", title="Plan One")
    loaded = _loaded(
        tmp_path,
        plans=plans_artifact(plans=(plan,), ordering=(OrderingEntry(plan_id=plan.id),)),
    )

    text = render_traceability_walk(loaded, tmp_path, {})

    assert f"draft seed classification unavailable: {plan.draft_seed_path}" in text


def test_walk_and_seeds_view_agree_on_one_drafts_state_word(tmp_path: Path) -> None:
    plan = plan_row(id="plan-1", title="Plan One")
    loaded = _loaded(
        tmp_path,
        plans=plans_artifact(plans=(plan,), ordering=(OrderingEntry(plan_id=plan.id),)),
    )
    classifications = draft_seed_classifications(
        **{plan.id: DRAFT_SEED_STATE_DIGEST_MISMATCHED}
    )

    walk = render_traceability_walk(loaded, tmp_path, classifications)
    seeds = render_seed_state_view(loaded, classifications, ())

    assert f"draft seed {DRAFT_SEED_STATE_DIGEST_MISMATCHED}" in walk
    assert f"{plan.id}: {DRAFT_SEED_STATE_DIGEST_MISMATCHED}" in seeds


def test_walk_cross_cutting_plan_with_no_components_renders_an_explicit_empty_list(
    tmp_path: Path,
) -> None:
    plan = plan_row(
        id="plan-1",
        title="Cross-cutting work",
        disposition=PlanDisposition.CROSS_CUTTING,
        component_ids=(),
    )
    plans = plans_artifact(plans=(plan,), ordering=(OrderingEntry(plan_id="plan-1"),))
    loaded = _loaded(tmp_path, plans=plans)
    text = render_traceability_walk(loaded, tmp_path)
    assert re.search(r"components:\s*\n\s*\(none\)", text)


def test_walk_body_is_the_same_under_both_modes(tmp_path: Path) -> None:
    domain = domain_artifact(
        entities=(entity_row(id="entity-1", name="Order"),),
        feedback=(feedback_row(id="feedback-1"),),
        removals=(removal_record(removed_id="entity-old"),),
    )
    components = components_artifact(
        components=(component_row(id="component-1", entity_ids=("entity-1",)),)
    )
    plans = plans_artifact(
        plans=(plan_row(id="plan-1", component_ids=("component-1",)),),
        ordering=(OrderingEntry(plan_id="plan-1"),),
    )
    _write_subset(tmp_path, domain=domain, components=components, plans=plans)

    current = load_roadmap(tmp_path, SLUG, mode=MODE_CURRENT)
    review = load_roadmap(tmp_path, SLUG, mode=MODE_REVIEW)

    current_text = render_traceability_walk(current, tmp_path)
    review_text = render_traceability_walk(review, tmp_path)

    current_body = current_text.split("\n", 1)[1]
    review_body = review_text.split("\n", 1)[1]
    assert current_body == review_body


def test_walk_render_is_the_same_on_repeat_calls(tmp_path: Path) -> None:
    loaded = _loaded(
        tmp_path,
        domain=domain_artifact(entities=(entity_row(id="entity-1"),)),
        components=components_artifact(
            components=(component_row(id="component-1", entity_ids=("entity-1",)),)
        ),
        plans=plans_artifact(
            plans=(plan_row(id="plan-1", component_ids=("component-1",)),),
            ordering=(OrderingEntry(plan_id="plan-1"),),
        ),
    )
    assert render_traceability_walk(loaded, tmp_path) == render_traceability_walk(
        loaded, tmp_path
    )


def test_walk_render_names_its_mode_and_the_unparseable_files(
    tmp_path: Path,
) -> None:
    _write_subset(tmp_path, domain=domain_artifact(entities=(entity_row(),)), constraints=_BROKEN_MEMBER)

    loaded = load_roadmap(tmp_path, SLUG, mode=MODE_REVIEW)
    text = render_traceability_walk(loaded, tmp_path)

    assert MODE_REVIEW in text
    assert CONSTRAINTS_FILENAME in text
    # Stored members are never absent, so only the broken one is named.
    assert COMPONENTS_FILENAME not in text
    assert PLANS_FILENAME not in text


def test_walk_on_a_partial_roadmap_resolves_every_reference_as_dangling(
    tmp_path: Path,
) -> None:
    """Domain is absent; the components artifact and the plan that names it
    are the only artifacts present, so an entity id a component names and a
    component id a plan names that was never declared both dangle, with no
    exception raised."""
    components = components_artifact(
        components=(component_row(id="component-1", entity_ids=("entity-ghost",)),)
    )
    plans = plans_artifact(
        plans=(
            plan_row(id="plan-1", component_ids=("component-1", "component-ghost")),
        ),
        ordering=(OrderingEntry(plan_id="plan-1"),),
    )
    loaded = _loaded(tmp_path, components=components, plans=plans)

    text = render_traceability_walk(loaded, tmp_path)

    assert "⚠ undefined: entity-ghost" in text
    assert "⚠ undefined: component-ghost" in text


# --------------------------------------------------------------------------
# render_seed_state_view
# --------------------------------------------------------------------------


def test_seeds_view_prints_one_line_per_plan_row_with_its_state(tmp_path: Path) -> None:
    states = (
        DRAFT_SEED_STATE_CURRENT,
        DRAFT_SEED_STATE_MISSING,
        DRAFT_SEED_STATE_STALE,
        DRAFT_SEED_STATE_MALFORMED,
        DRAFT_SEED_STATE_PATH_ESCAPING,
        DRAFT_SEED_STATE_DUPLICATE,
        DRAFT_SEED_STATE_DIGEST_MISMATCHED,
    )
    plans = tuple(plan_row(id=f"plan-{index}") for index in range(len(states)))
    loaded = _loaded(tmp_path, plans=plans_artifact(plans=plans))
    classifications = {
        plan.id: DraftSeedClassification(
            plan_id=plan.id,
            state=state,
            detail=f"detail for {state}",
        )
        for plan, state in zip(plans, states, strict=True)
    }

    text = render_seed_state_view(loaded, classifications, ())

    positions = []
    for plan, state in zip(plans, states, strict=True):
        line = f"{plan.id}: {state} — detail for {state}"
        assert line in text
        positions.append(text.index(line))
    assert positions == sorted(positions)


def test_seeds_view_states_use_the_classifier_constants(tmp_path: Path) -> None:
    states = (
        DRAFT_SEED_STATE_CURRENT,
        DRAFT_SEED_STATE_MISSING,
        DRAFT_SEED_STATE_STALE,
        DRAFT_SEED_STATE_MALFORMED,
        DRAFT_SEED_STATE_PATH_ESCAPING,
        DRAFT_SEED_STATE_DUPLICATE,
        DRAFT_SEED_STATE_DIGEST_MISMATCHED,
    )
    plans = tuple(plan_row(id=f"plan-{index}") for index in range(len(states)))
    loaded = _loaded(tmp_path, plans=plans_artifact(plans=plans))
    classifications = draft_seed_classifications(
        **{plan.id: state for plan, state in zip(plans, states, strict=True)}
    )

    text = render_seed_state_view(loaded, classifications, ())

    for plan, state in zip(plans, states, strict=True):
        assert f"{plan.id}: {state}" in text


def test_seeds_view_non_current_lines_name_the_same_remedy_as_the_summary(
    tmp_path: Path,
) -> None:
    plan = plan_row(id="plan-repair")
    loaded = _loaded(tmp_path, plans=plans_artifact(plans=(plan,)))
    classifications = draft_seed_classifications(
        **{plan.id: DRAFT_SEED_STATE_MISSING}
    )

    seeds = render_seed_state_view(loaded, classifications, ())
    summary = render_roadmap_summary(
        loaded, summarize_seed_lifecycle(loaded, classifications)
    )
    remedy = f"materialize with plan-tool roadmap {SLUG} --materialize {plan.id}"

    assert remedy in seeds
    assert remedy in summary


def test_seeds_view_renders_sidecar_and_file_orphans_in_their_own_sections(
    tmp_path: Path,
) -> None:
    loaded = _loaded(tmp_path, plans=plans_artifact())
    orphans = (
        OrphanSeedRecord(
            kind=ORPHAN_SEED_RECORD_SIDECAR_ENTRY, plan_id="retired-plan"
        ),
        OrphanSeedRecord(
            kind=ORPHAN_SEED_RECORD_FILE, path=Path("seeds/orphan.md")
        ),
    )

    text = render_seed_state_view(loaded, {}, orphans)

    assert "sidecar entries naming no plan row:\n    - retired-plan" in text
    assert "files naming no plan row:\n    - seeds/orphan.md" in text


def test_seeds_view_empty_orphan_sections_are_stated_not_dropped(tmp_path: Path) -> None:
    loaded = _loaded(tmp_path, plans=plans_artifact())

    text = render_seed_state_view(loaded, {}, ())

    assert "sidecar entries naming no plan row:\n    (none)" in text
    assert "files naming no plan row:\n    (none)" in text


def test_seeds_view_unreadable_plans_artifact_reports_unavailable_not_empty(
    tmp_path: Path,
) -> None:
    loaded = _loaded(tmp_path, plans=_BROKEN_MEMBER)

    text = render_seed_state_view(loaded, {}, ())

    assert "seed states unavailable: 04-roadmap.md is unparseable" in text
    assert "seeds:" not in text
    assert "orphans:" not in text


def test_seeds_view_names_its_mode_and_the_unparseable_files(
    tmp_path: Path,
) -> None:
    _write_subset(tmp_path, domain=domain_artifact(entities=(entity_row(),)), constraints=_BROKEN_MEMBER)
    loaded = load_roadmap(tmp_path, SLUG, mode=MODE_REVIEW)

    text = render_seed_state_view(loaded, {}, ())

    assert MODE_REVIEW in text
    assert CONSTRAINTS_FILENAME in text
    # Stored members are never absent, so only the broken one is named.
    assert COMPONENTS_FILENAME not in text
    assert PLANS_FILENAME not in text


def test_seeds_view_render_is_the_same_on_repeat_calls(tmp_path: Path) -> None:
    plan = plan_row(id="plan-repeat")
    loaded = _loaded(tmp_path, plans=plans_artifact(plans=(plan,)))
    classifications = draft_seed_classifications(
        **{plan.id: DRAFT_SEED_STATE_CURRENT}
    )
    orphans = (
        OrphanSeedRecord(
            kind=ORPHAN_SEED_RECORD_FILE, path=Path("plan-seed-drafts/orphan.md")
        ),
    )

    assert render_seed_state_view(loaded, classifications, orphans) == render_seed_state_view(
        loaded, classifications, orphans
    )


# --------------------------------------------------------------------------
# render_decision_ledger
# --------------------------------------------------------------------------


def test_ledger_lists_every_decision_across_all_four_artifacts_exactly_once(
    tmp_path: Path,
) -> None:
    loaded = _loaded(
        tmp_path,
        domain=domain_artifact(
            decisions=(
                decision_row(id="decision-domain", chosen_option="Domain decision."),
            )
        ),
        constraints=constraints_artifact(
            decisions=(
                decision_row(
                    id="decision-constraints", chosen_option="Constraints decision."
                ),
            )
        ),
        components=components_artifact(
            decisions=(
                decision_row(
                    id="decision-components", chosen_option="Components decision."
                ),
            )
        ),
        plans=plans_artifact(
            decisions=(
                decision_row(id="decision-plans", chosen_option="Plans decision."),
            )
        ),
    )
    text = render_decision_ledger(loaded)
    for option in (
        "Domain decision.",
        "Constraints decision.",
        "Components decision.",
        "Plans decision.",
    ):
        assert text.count(option) == 1


def test_ledger_groups_decisions_by_status(tmp_path: Path) -> None:
    domain = domain_artifact(
        decisions=(
            decision_row(
                id="decision-settled",
                chosen_option="Settled decision.",
                status=DecisionStatus.SETTLED,
            ),
            decision_row(
                id="decision-pending",
                chosen_option="Pending decision.",
                status=DecisionStatus.PENDING,
            ),
        )
    )
    for mode in (MODE_CURRENT, MODE_REVIEW):
        loaded = _loaded(tmp_path / mode, mode=mode, domain=domain)
        text = render_decision_ledger(loaded)
        settled_section, pending_section = text.split("pending:", 1)
        assert "Settled decision." in settled_section
        assert "Pending decision." not in settled_section
        assert "Pending decision." in pending_section
        assert "Settled decision." not in pending_section


def test_ledger_decisions_order_stage_then_source(tmp_path: Path) -> None:
    loaded = _loaded(
        tmp_path,
        domain=domain_artifact(
            decisions=(
                decision_row(
                    id="decision-domain-1", chosen_option="Domain decision one."
                ),
                decision_row(
                    id="decision-domain-2", chosen_option="Domain decision two."
                ),
            )
        ),
        constraints=constraints_artifact(
            decisions=(
                decision_row(
                    id="decision-constraints", chosen_option="Constraints decision."
                ),
            )
        ),
    )
    text = render_decision_ledger(loaded)
    assert (
        text.index("Domain decision one.")
        < text.index("Domain decision two.")
        < text.index("Constraints decision.")
    )


def test_ledger_resolves_decision_anchor_to_a_label(tmp_path: Path) -> None:
    loaded = _loaded(
        tmp_path,
        domain=domain_artifact(
            entities=(entity_row(id="entity-1", name="Order"),),
            decisions=(decision_row(id="decision-1", anchor="entity-1"),),
        ),
    )
    text = render_decision_ledger(loaded)
    assert "anchor: Order" in text


def test_ledger_prints_rejected_alternatives_and_rationale(tmp_path: Path) -> None:
    loaded = _loaded(
        tmp_path,
        domain=domain_artifact(
            entities=(entity_row(id="entity-1"),),
            decisions=(
                decision_row(
                    id="decision-1",
                    chosen_option="Keep the cart inside the order aggregate.",
                    rationale="Keeps checkout atomic.",
                    rejected_alternatives=(
                        RejectedAlternative(
                            option="Separate cart service.",
                            reason="Adds a network hop.",
                        ),
                    ),
                ),
            ),
        ),
    )
    text = render_decision_ledger(loaded)
    assert "Keep the cart inside the order aggregate." in text
    assert "Keeps checkout atomic." in text
    assert "Separate cart service." in text
    assert "Adds a network hop." in text


def test_ledger_renders_absent_inherited_rationale_without_python_none(tmp_path: Path) -> None:
    inherited = replace(
        decision_row(id="decision-1"),
        source="answer-cart",
        rationale=None,
        rejected_alternatives=(),
        status=DecisionStatus.SETTLED,
    )
    loaded = _loaded(
        tmp_path,
        domain=domain_artifact(
            entities=(entity_row(id="entity-1"),), decisions=(inherited,)
        ),
    )

    text = render_decision_ledger(loaded)

    assert "source: answer-cart" in text
    assert "rationale: (none)" in text
    assert "rationale: None" not in text


def test_ledger_dangling_decision_anchor_renders_the_marker(tmp_path: Path) -> None:
    loaded = _loaded(
        tmp_path,
        domain=domain_artifact(
            decisions=(decision_row(id="decision-1", anchor="nonexistent"),),
        ),
    )
    text = render_decision_ledger(loaded)
    assert "⚠ undefined: nonexistent" in text


def test_ledger_ambiguous_decision_anchor_names_every_match(tmp_path: Path) -> None:
    loaded = _loaded(
        tmp_path,
        domain=domain_artifact(
            entities=(entity_row(id="dup", name="Entity label"),),
            workflows=(workflow_row(id="dup", name="Workflow label"),),
            decisions=(decision_row(id="decision-1", anchor="dup"),),
        ),
    )
    text = render_decision_ledger(loaded)
    assert "⚠ ambiguous: dup" in text
    assert "Entity label" in text
    assert "Workflow label" in text


def test_ledger_settled_decision_anchor_with_a_hand_edited_dangling_reference_renders_as_dangling(
    tmp_path: Path,
) -> None:
    loaded = _loaded(
        tmp_path,
        mode=MODE_REVIEW,
        domain=domain_artifact(
            decisions=(
                decision_row(
                    id="decision-1", anchor="entity-old", status=DecisionStatus.SETTLED
                ),
            ),
            removals=(
                removal_record(
                    removed_id="entity-old", rationale="Dropped after review."
                ),
            ),
        ),
    )
    text = render_decision_ledger(loaded)
    assert "⚠ undefined: entity-old" in text
    assert "Dropped after review." not in text


def test_ledger_current_mode_pending_group_has_no_feedback_or_removal(
    tmp_path: Path,
) -> None:
    loaded = _loaded(
        tmp_path,
        mode=MODE_CURRENT,
        domain=domain_artifact(
            decisions=(decision_row(id="decision-1", status=DecisionStatus.PENDING),),
            feedback=(
                feedback_row(id="feedback-1", request="Split the order entity."),
            ),
            removals=(
                removal_record(removed_id="entity-old", rationale="No longer needed."),
            ),
        ),
    )
    text = render_decision_ledger(loaded)
    assert "Split the order entity." not in text
    assert "No longer needed." not in text


def test_ledger_review_mode_adds_unclosed_feedback_to_pending(tmp_path: Path) -> None:
    loaded = _loaded(
        tmp_path,
        mode=MODE_REVIEW,
        domain=domain_artifact(
            feedback=(
                feedback_row(id="feedback-1", request="Split the order entity."),
            ),
        ),
    )
    text = render_decision_ledger(loaded)
    pending_section = text.split("pending:", 1)[1]
    assert "Split the order entity." in pending_section


@pytest.mark.parametrize(
    "state",
    [FeedbackState.OPEN, FeedbackState.AWAITING_REVIEW, FeedbackState.DEFERRED],
)
def test_ledger_all_three_unclosed_feedback_states_reach_the_pending_group(
    tmp_path: Path, state
) -> None:
    row = FeedbackRow(
        id="feedback-1",
        target=FeedbackTarget(kind=FeedbackTargetKind.ARTIFACT),
        request="Reconsider this whole file.",
        state=state,
        proposed_response=(
            "Proposed response." if state is FeedbackState.AWAITING_REVIEW else None
        ),
    )
    loaded = _loaded(tmp_path, mode=MODE_REVIEW, domain=domain_artifact(feedback=(row,)))
    text = render_decision_ledger(loaded)
    assert "Reconsider this whole file." in text


def test_ledger_feedback_target_resolving_a_live_row_prints_its_label(
    tmp_path: Path,
) -> None:
    loaded = _loaded(
        tmp_path,
        mode=MODE_REVIEW,
        domain=domain_artifact(
            entities=(entity_row(id="entity-1", name="Order"),),
            feedback=(
                feedback_row(
                    id="feedback-1",
                    request="Split the order entity.",
                    target=FeedbackTarget(
                        kind=FeedbackTargetKind.ROW, row_id="entity-1"
                    ),
                ),
            ),
        ),
    )
    text = render_decision_ledger(loaded)
    assert "target: Order" in text


def test_ledger_feedback_target_artifact_scope_prints_as_artifact_scope(
    tmp_path: Path,
) -> None:
    loaded = _loaded(
        tmp_path,
        mode=MODE_REVIEW,
        domain=domain_artifact(
            feedback=(
                feedback_row(
                    id="feedback-1",
                    request="Reconsider this whole file.",
                    target=FeedbackTarget(kind=FeedbackTargetKind.ARTIFACT),
                ),
            ),
        ),
    )
    text = render_decision_ledger(loaded)
    assert "target: the whole artifact" in text
    assert "⚠ undefined:" not in text


def test_ledger_feedback_target_through_a_removal_renders_the_tombstone(
    tmp_path: Path,
) -> None:
    loaded = _loaded(
        tmp_path,
        mode=MODE_REVIEW,
        domain=domain_artifact(
            feedback=(
                feedback_row(
                    id="feedback-1",
                    request="Reconsider the removed entity.",
                    target=FeedbackTarget(
                        kind=FeedbackTargetKind.ROW, row_id="entity-old"
                    ),
                ),
            ),
            removals=(
                removal_record(
                    removed_id="entity-old",
                    rationale="Dropped after review.",
                    feedback_ids=("feedback-1",),
                ),
            ),
        ),
    )
    text = render_decision_ledger(loaded)
    assert "Reconsider the removed entity." in text
    assert "entity-old" in text
    assert "Dropped after review." in text
    assert "⚠ undefined: entity-old" not in text


def test_ledger_feedback_target_genuinely_dangling_renders_the_marker(
    tmp_path: Path,
) -> None:
    loaded = _loaded(
        tmp_path,
        mode=MODE_REVIEW,
        domain=domain_artifact(
            feedback=(
                feedback_row(
                    id="feedback-1",
                    request="Reconsider ghost row.",
                    target=FeedbackTarget(
                        kind=FeedbackTargetKind.ROW, row_id="ghost-row"
                    ),
                ),
            ),
        ),
    )
    text = render_decision_ledger(loaded)
    assert "⚠ undefined: ghost-row" in text


def test_ledger_removal_whose_citing_feedback_is_closed_renders_in_no_view(
    tmp_path: Path,
) -> None:
    loaded = _loaded(
        tmp_path,
        mode=MODE_REVIEW,
        domain=domain_artifact(
            # The feedback row that cited this removal has since been closed
            # (deleted from the artifact), so it is absent from feedback_index.
            removals=(
                removal_record(
                    removed_id="entity-old",
                    rationale="Dropped after review.",
                    feedback_ids=("feedback-1",),
                ),
            ),
        ),
    )
    text = render_decision_ledger(loaded)
    assert "entity-old" not in text
    assert "Dropped after review." not in text


def test_ledger_removal_rendering_names_only_the_id_and_rationale(
    tmp_path: Path,
) -> None:
    loaded = _loaded(
        tmp_path,
        mode=MODE_REVIEW,
        domain=domain_artifact(
            entities=(entity_row(id="entity-kept", name="Kept entity"),),
            feedback=(
                feedback_row(
                    id="feedback-1",
                    request="Reconsider the removed entity.",
                    target=FeedbackTarget(
                        kind=FeedbackTargetKind.ROW, row_id="entity-removed"
                    ),
                ),
            ),
            removals=(
                removal_record(
                    removed_id="entity-removed",
                    rationale="Superseded by entity-kept.",
                    feedback_ids=("feedback-1",),
                ),
            ),
        ),
    )
    text = render_decision_ledger(loaded)
    assert "entity-removed" in text
    assert "Superseded by entity-kept." in text


def test_ledger_removal_never_appears_under_its_own_heading(tmp_path: Path) -> None:
    loaded = _loaded(
        tmp_path,
        mode=MODE_REVIEW,
        domain=domain_artifact(
            feedback=(
                feedback_row(
                    id="feedback-1",
                    request="Reconsider the removed entity.",
                    target=FeedbackTarget(
                        kind=FeedbackTargetKind.ROW, row_id="entity-old"
                    ),
                ),
            ),
            removals=(
                removal_record(
                    removed_id="entity-old",
                    rationale="No longer needed.",
                    feedback_ids=("feedback-1",),
                ),
            ),
        ),
    )
    text = render_decision_ledger(loaded)
    lowered = text.lower()
    assert "removals:" not in lowered
    assert "removal:" not in lowered


def test_ledger_pending_decision_renders_in_both_modes(tmp_path: Path) -> None:
    domain = domain_artifact(
        decisions=(decision_row(id="decision-1", chosen_option="Pending decision."),),
    )
    for mode in (MODE_CURRENT, MODE_REVIEW):
        loaded = _loaded(tmp_path / mode, mode=mode, domain=domain)
        text = render_decision_ledger(loaded)
        pending_section = text.split("pending:", 1)[1]
        assert "Pending decision." in pending_section


def test_ledger_pending_feedback_orders_after_pending_decisions_in_stage_then_source_order(
    tmp_path: Path,
) -> None:
    loaded = _loaded(
        tmp_path,
        mode=MODE_REVIEW,
        domain=domain_artifact(
            decisions=(
                decision_row(id="decision-1", chosen_option="Pending decision."),
            ),
            feedback=(
                feedback_row(id="feedback-1", request="Split the order entity."),
            ),
        ),
    )
    text = render_decision_ledger(loaded)
    assert text.index("Pending decision.") < text.index("Split the order entity.")


def test_ledger_render_names_its_mode_and_the_unparseable_files(
    tmp_path: Path,
) -> None:
    _write_subset(tmp_path, domain=domain_artifact(decisions=(decision_row(),)), constraints=_BROKEN_MEMBER)

    loaded = load_roadmap(tmp_path, SLUG, mode=MODE_REVIEW)
    text = render_decision_ledger(loaded)

    assert MODE_REVIEW in text
    assert CONSTRAINTS_FILENAME in text
    # Stored members are never absent, so only the broken one is named.
    assert COMPONENTS_FILENAME not in text
    assert PLANS_FILENAME not in text


def test_ledger_render_is_the_same_on_repeat_calls(tmp_path: Path) -> None:
    loaded = _loaded(
        tmp_path,
        mode=MODE_REVIEW,
        domain=domain_artifact(
            entities=(entity_row(id="entity-1"),),
            decisions=(decision_row(id="decision-1", anchor="entity-1"),),
            feedback=(feedback_row(),),
            removals=(removal_record(),),
        ),
    )
    assert render_decision_ledger(loaded) == render_decision_ledger(loaded)


def test_ledger_on_a_domain_only_roadmap_lists_only_domain_decisions(
    tmp_path: Path,
) -> None:
    loaded = _loaded(
        tmp_path,
        domain=domain_artifact(
            decisions=(
                decision_row(id="decision-1", chosen_option="Domain decision."),
            ),
        ),
    )
    text = render_decision_ledger(loaded)
    assert "Domain decision." in text
    assert CONSTRAINTS_FILENAME not in text
    assert COMPONENTS_FILENAME not in text
    assert PLANS_FILENAME not in text


# --------------------------------------------------------------------------
# render_roadmap_summary
# --------------------------------------------------------------------------


def test_summary_reports_compact_counts_and_actionable_review_queue(
    tmp_path: Path,
) -> None:
    loaded = _loaded(
        tmp_path,
        mode=MODE_REVIEW,
        domain=domain_artifact(
            entities=(entity_row(id="entity-1"),),
            business_rules=(business_rule_row(entity_ids=("entity-missing",)),),
            decisions=(
                decision_row(
                    id="decision-pending",
                    chosen_option="Choose the payment boundary.",
                ),
            ),
            feedback=(
                feedback_row(
                    id="feedback-open", request="Review the payment boundary."
                ),
            ),
        ),
        components=components_artifact(components=(component_row(),)),
        plans=plans_artifact(plans=(plan_row(id="plan-checkout"),)),
    )
    lifecycle = summarize_seed_lifecycle(
        loaded, draft_seed_classifications(**{"plan-checkout": DRAFT_SEED_STATE_STALE})
    )

    text = render_roadmap_summary(loaded, lifecycle)

    assert "artifacts:" in text
    assert "4/4 readable" in text
    assert "1 entities · 1 components · 1 plans" in text
    assert "0 settled · 1 pending" in text
    assert "1 open · 0 awaiting review · 0 deferred" in text
    assert "0 current · 1 invalidated" in text
    assert "indexed references:" in text
    assert "1 dangling · 0 ambiguous" in text
    assert "seed plan-checkout is stale" in text
    assert "plan-tool roadmap acme-roadmap --materialize plan-checkout" in text
    assert "indexed reference entity-missing is undefined" in text
    assert (
        "plan-tool roadmap acme-roadmap --view index --id entity-missing "
        "--mode review"
    ) in text
    assert "pending decision decision-pending" in text
    assert "open feedback feedback-open" in text


def test_summary_reports_missing_plan_review_context_with_a_ledger_feedback_route(
    tmp_path: Path,
) -> None:
    loaded = _loaded(
        tmp_path,
        plans=plans_artifact(plans=(plan_row(id="plan-legacy", intent="", non_goals=()),)),
    )

    text = render_roadmap_summary(
        loaded,
        summarize_seed_lifecycle(
            loaded, draft_seed_classifications(**{"plan-legacy": DRAFT_SEED_STATE_CURRENT})
        ),
    )

    assert "plan review context:\n  0/1 intent recorded · 0/1 non-goal lists recorded" in text
    assert "plan plan-legacy has no intent, non-goals" in text
    assert "plan-tool roadmap acme-roadmap --submit-feedback ITEM_ID" in text
    assert "--feedback-target plans:artifact" in text
    assert "plan-tool roadmap acme-roadmap --propose-candidate" in text
    assert "--from-stage" not in text


def test_summary_hides_feedback_in_current_mode_and_surfaces_it_in_review_mode(
    tmp_path: Path,
) -> None:
    domain = domain_artifact(
        feedback=(feedback_row(id="feedback-1", request="Review this boundary."),),
    )
    current = _loaded(tmp_path / "current", mode=MODE_CURRENT, domain=domain)
    review = _loaded(tmp_path / "review", mode=MODE_REVIEW, domain=domain)

    current_text = render_roadmap_summary(
        current, summarize_seed_lifecycle(current)
    )
    review_text = render_roadmap_summary(review, summarize_seed_lifecycle(review))

    assert "hidden in current mode" in current_text
    assert "Review this boundary." not in current_text
    assert "1 open · 0 awaiting review · 0 deferred" in review_text
    assert "Review this boundary." in review_text


def test_summary_caps_attention_queue_and_reports_the_remainder(tmp_path: Path) -> None:
    loaded = _loaded(
        tmp_path,
        domain=domain_artifact(
            decisions=(
                decision_row(id="decision-1", anchor="missing-1"),
                decision_row(id="decision-2", anchor="missing-2"),
                decision_row(id="decision-3", anchor="missing-3"),
            )
        ),
    )

    text = render_roadmap_summary(loaded, summarize_seed_lifecycle(loaded))

    assert text.count("⚠ ") == 5
    assert "… 2 additional item(s)" in text


def test_summary_marks_a_malformed_lifecycle_sidecar_unavailable(tmp_path: Path) -> None:
    loaded = _loaded(tmp_path, plans=plans_artifact(plans=(plan_row(),)))

    lifecycle = summarize_seed_lifecycle(
        loaded, unavailable_reason="seed lifecycle state is malformed"
    )
    text = render_roadmap_summary(loaded, lifecycle)

    assert "seeds:\n  unavailable: seed lifecycle state is malformed" in text
    assert "seed lifecycle state is unavailable" in text


@pytest.mark.parametrize(
    ("state", "current_count", "invalidated_count"),
    [
        (DRAFT_SEED_STATE_CURRENT, 1, 0),
        (DRAFT_SEED_STATE_MISSING, 0, 1),
        (DRAFT_SEED_STATE_STALE, 0, 1),
        (DRAFT_SEED_STATE_MALFORMED, 0, 1),
        (DRAFT_SEED_STATE_PATH_ESCAPING, 0, 1),
        (DRAFT_SEED_STATE_DUPLICATE, 0, 1),
        (DRAFT_SEED_STATE_DIGEST_MISMATCHED, 0, 1),
    ],
)
def test_summary_folds_every_non_current_state_into_invalidated(
    tmp_path: Path, state: str, current_count: int, invalidated_count: int
) -> None:
    plan = plan_row(id="plan-seed")
    loaded = _loaded(tmp_path, plans=plans_artifact(plans=(plan,)))

    lifecycle = summarize_seed_lifecycle(
        loaded, draft_seed_classifications(**{plan.id: state})
    )

    assert len(lifecycle.current_plan_ids) == current_count
    assert len(lifecycle.invalidated_plan_ids) == invalidated_count


def test_summary_seed_counts_have_exactly_two_buckets(tmp_path: Path) -> None:
    plans = (plan_row(id="plan-current"), plan_row(id="plan-missing"))
    loaded = _loaded(tmp_path, plans=plans_artifact(plans=plans))

    text = render_roadmap_summary(
        loaded,
        summarize_seed_lifecycle(
            loaded,
            draft_seed_classifications(
                **{
                    "plan-current": DRAFT_SEED_STATE_CURRENT,
                    "plan-missing": DRAFT_SEED_STATE_MISSING,
                }
            ),
        ),
    )

    assert "seeds:\n  1 current · 1 invalidated" in text
    assert "untracked" not in text


@pytest.mark.parametrize(
    "state",
    (
        DRAFT_SEED_STATE_MISSING,
        DRAFT_SEED_STATE_STALE,
        DRAFT_SEED_STATE_MALFORMED,
        DRAFT_SEED_STATE_PATH_ESCAPING,
    ),
)
def test_attention_recommends_materialize_for_each_regenerable_state(
    tmp_path: Path, state: str
) -> None:
    plan = plan_row(id="plan-repair")
    loaded = _loaded(tmp_path, plans=plans_artifact(plans=(plan,)))

    text = render_roadmap_summary(
        loaded,
        summarize_seed_lifecycle(
            loaded, draft_seed_classifications(**{plan.id: state})
        ),
    )

    assert f"seed {plan.id} is {state}" in text
    assert f"--materialize {plan.id}" in text


def test_attention_digest_mismatched_offers_accept_or_discard(tmp_path: Path) -> None:
    plan = plan_row(id="plan-edited")
    loaded = _loaded(tmp_path, plans=plans_artifact(plans=(plan,)))

    text = render_roadmap_summary(
        loaded,
        summarize_seed_lifecycle(
            loaded,
            draft_seed_classifications(
                **{plan.id: DRAFT_SEED_STATE_DIGEST_MISMATCHED}
            ),
        ),
    )

    assert "digest-mismatched" in text
    assert "review the draft diff" in text
    assert f"--accept-seed {plan.id}" in text
    assert f"--materialize {plan.id}" in text


def test_attention_duplicate_recommends_a_roadmap_revision_not_regeneration(
    tmp_path: Path,
) -> None:
    plan = plan_row(id="plan-collision")
    loaded = _loaded(tmp_path, plans=plans_artifact(plans=(plan,)))
    classifications = {
        plan.id: DraftSeedClassification(
            plan_id=plan.id,
            state=DRAFT_SEED_STATE_DUPLICATE,
            detail="collides with plan-sibling",
        )
    }

    text = render_roadmap_summary(
        loaded, summarize_seed_lifecycle(loaded, classifications)
    )

    assert "duplicate: collides with plan-sibling" in text
    assert "draft_seed_path basenames collide" in text
    assert "roadmap revision" in text
    assert "--materialize" not in text
    assert "--refresh-seeds" not in text


def test_attention_never_recommends_refresh_seeds_per_plan(tmp_path: Path) -> None:
    states = {
        "plan-missing": DRAFT_SEED_STATE_MISSING,
        "plan-stale": DRAFT_SEED_STATE_STALE,
        "plan-malformed": DRAFT_SEED_STATE_MALFORMED,
        "plan-path": DRAFT_SEED_STATE_PATH_ESCAPING,
        "plan-edited": DRAFT_SEED_STATE_DIGEST_MISMATCHED,
        "plan-duplicate": DRAFT_SEED_STATE_DUPLICATE,
    }
    loaded = _loaded(
        tmp_path,
        plans=plans_artifact(plans=tuple(plan_row(id=plan_id) for plan_id in states)),
    )

    text = render_roadmap_summary(
        loaded,
        summarize_seed_lifecycle(loaded, draft_seed_classifications(**states)),
    )

    assert "--refresh-seeds" not in text


def test_summary_unreadable_stage_four_stays_unavailable(tmp_path: Path) -> None:
    loaded = _loaded(tmp_path, plans=_BROKEN_MEMBER)

    text = render_roadmap_summary(loaded, summarize_seed_lifecycle(loaded))

    assert "seeds:\n  unavailable: 04-roadmap.md is not readable" in text


def test_summary_folds_a_real_classifier_result(tmp_path: Path) -> None:
    plan = plan_row(id="plan-classified")
    loaded = _loaded(tmp_path, plans=plans_artifact(plans=(plan,)))
    source = write_draft_seed(
        tmp_path, plan, DraftSeedProvenance(roadmap_components=plan.component_ids)
    )
    state = empty_seed_state()
    state["seeds"][plan.id] = {
        "draft_seed_path": plan.draft_seed_path,
        "status": "current",
        "digest": digest_text(source.read_text(encoding="utf-8")),
        "published": False,
    }
    write_seed_state(seed_state_path(roadmap_dir(tmp_path, SLUG)), state)
    source.write_text(
        source.read_text(encoding="utf-8") + "hand edit\n", encoding="utf-8"
    )

    classifications = classify_draft_seeds(loaded.plans, plans_dir=tmp_path, slug=SLUG)
    lifecycle = summarize_seed_lifecycle(loaded, classifications)

    assert classifications[plan.id].state == DRAFT_SEED_STATE_DIGEST_MISMATCHED
    assert lifecycle.invalidated_plan_ids == (plan.id,)
    assert lifecycle.classifications is classifications


def test_summary_treats_a_missing_per_plan_classification_as_invalidated(
    tmp_path: Path,
) -> None:
    plan = plan_row(id="plan-unclassified")
    loaded = _loaded(tmp_path, plans=plans_artifact(plans=(plan,)))

    lifecycle = summarize_seed_lifecycle(loaded, {})

    assert lifecycle.tracking == SEED_TRACKING_TRACKED
    assert lifecycle.current_plan_ids == ()
    assert lifecycle.invalidated_plan_ids == (plan.id,)


# --------------------------------------------------------------------------
# Leaf-module hygiene
# --------------------------------------------------------------------------


def test_module_imports_only_the_artifact_gates_relations_seed_manifest_and_version_leaves() -> None:
    """Mirrors ``tests/test_roadmap_gates.py:test_module_imports_only_the_artifact_leaf``:
    the source grep catches a lazy import inside a function; the subprocess
    catches a transitive one."""
    source = MODULE_PATH.read_text()
    assert re.findall(r"(?m)^\s*(?:from|import) (plan_tool\S*)", source) == [
        "plan_tool.roadmap_artifacts",
        "plan_tool.roadmap_gates",
        "plan_tool.roadmap_relations",
        "plan_tool.roadmap_seed_manifest",
        "plan_tool.roadmap_versions",
    ]

    code = (
        "import sys, types\n"
        "pkg = types.ModuleType('plan_tool')\n"
        f"pkg.__path__ = [{str(MODULE_PATH.parent)!r}]\n"
        "sys.modules['plan_tool'] = pkg\n"
        "import plan_tool.roadmap_view\n"
        "leaked = sorted(m for m in sys.modules if m.startswith('plan_tool.')"
        " and m not in ('plan_tool.roadmap_view', 'plan_tool.roadmap_artifacts',"
        " 'plan_tool.roadmap_gates', 'plan_tool.roadmap_relations',"
        " 'plan_tool.roadmap_seed_manifest',"
        " 'plan_tool.roadmap_seed_state', 'plan_tool.roadmap_versions',"
        " 'plan_tool.roadmap_source_identity', 'plan_tool.roadmap_json',"
        " 'plan_tool.scope_fence'))\n"
        "assert not leaked, leaked\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_module_reads_disk_only_through_the_artifact_loaders_and_the_draft_seed_read() -> (
    None
):
    """This module reads live disk state only through the artifact loaders
    and its draft-seed helper; accepted version storage stays behind its
    dedicated reader contract."""
    source = MODULE_PATH.read_text()
    for token in ("invoker", "subprocess", "open("):
        assert token not in source
    assert source.count("read_text(") == 1


def test_a_decision_anchored_to_a_stack_row_resolves_instead_of_reading_undefined() -> None:
    """The gates accept a stack id as a decision anchor and the pending concept
    depends on it, so the review views must resolve it to the row's label."""
    stack = StackRow("stack-platform", "platform", open=True)
    constraints = constraints_artifact(stack=(stack,))

    index = build_design_row_index(constraints=constraints)
    resolution = resolve_id("stack-platform", index)

    assert resolution.status == RESOLUTION_RESOLVED
    assert resolution.text == "stack platform: open"
