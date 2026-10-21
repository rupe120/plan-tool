"""Tests for the roadmap artifact contract leaf.

Plain unit tests: the module drives no orchestrator, crosses no module
boundary, and has no backend seam, so the suite runs under ``conftest.py``'s
autouse gate with no ``allow_real_claude`` opt-out.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from plan_tool.create import SLUG_RE
from plan_tool.roadmap_artifacts import (
    AttributeDispositionRow,
    COMPONENTS_FILENAME,
    COMPONENTS_ROW_KEYS,
    CONSTRAINTS_FILENAME,
    CONSTRAINTS_ROW_KEYS,
    ComponentRow,
    ConstraintDisposition,
    ConstraintsArtifact,
    DRAFT_SEEDS_DIRNAME,
    DRAFT_SEED_CROSS_CUTTING_KEY,
    DRAFT_SEED_ROADMAP_COMPONENTS_KEY,
    DOMAIN_FILENAME,
    DOMAIN_ROW_KEYS,
    DecisionStatus,
    DraftSeedProvenance,
    EntityRow,
    FeedbackReopenRecord,
    FeedbackRow,
    FeedbackState,
    FeedbackTarget,
    FeedbackTargetKind,
    HARD_MAX_ACTIVE_FEEDBACK_ITEMS,
    HARD_MAX_PROSE_AMENDMENT_BYTES,
    HARD_MAX_RESPONSE_BYTES,
    FieldRow,
    FieldType,
    HOSTING_FACETS,
    HostingRow,
    STACK_CONCERNS,
    StackRow,
    OrderingEntry,
    PLANS_FILENAME,
    PLANS_ROW_KEYS,
    PLAN_ID_SLUG_RE,
    PatternRow,
    PlanDisposition,
    PlanRow,
    AssumptionRow,
    QUALITY_ATTRIBUTES,
    REVIEW_ROW_KEYS,
    ROADMAP_DIRNAME,
    RemovalRecord,
    ResearchDisclosure,
    RoadmapArtifactError,
    StoreRow,
    components_design_rows,
    components_path,
    constraints_path,
    domain_path,
    draft_seeds_dir,
    load_components_artifact,
    load_constraints_artifact,
    load_domain_artifact,
    load_plans_artifact,
    parse_components_artifact,
    parse_constraints_artifact,
    parse_domain_artifact,
    parse_draft_seed_provenance,
    parse_plans_artifact,
    plans_design_rows,
    plans_path,
    render_components_artifact,
    render_constraints_artifact,
    render_domain_artifact,
    render_draft_seed_provenance,
    render_plans_artifact,
    append_plan_ordering_entry,
    append_removal_record,
    append_stage_row,
    design_row_collections,
    impact_node_collections,
    remove_plan_ordering_entry,
    remove_stage_row,
    replace_design_row,
    replace_stage_row,
    resolve_draft_seed_path,
    resolve_plan_seed_dest,
    roadmap_dir,
    roadmap_relative_stage_path,
    settle_pending_decision,
    stage_collection_participates_in_impact,
    stage_row_edit_preserves_fixed_fields,
    stage_row_collections,
    stage_row_operation_policy,
)

MODULE_PATH = Path(__file__).resolve().parents[1] / "plan_tool" / "roadmap_artifacts.py"

DOMAIN_BODY = """# Domain

entity-1 is the order a customer places. entity-2 is the customer who places it.

rule-1 binds the two. workflow-1 walks an order from cart to payment.

decision-1 records why the cart lives inside the order aggregate.
"""

DOMAIN_TEXT = f"""---
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
{DOMAIN_BODY}"""

CONSTRAINTS_BODY = """# Constraints

attribute-performance through attribute-reliability rank the seven attributes.

constraint-1 holds checkout latency down. decision-2 says what that cost.
"""

CONSTRAINTS_TEXT = f"""---
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
  chosen_option: Spend availability to keep checkout fast.
  rejected_alternatives:
  - option: Multi-region replication.
    reason: Adds write latency to the one path that cannot afford it.
  rationale: A slow checkout loses the order outright.
  anchor: attribute-performance
  status: settled
---
{CONSTRAINTS_BODY}"""

COMPONENTS_BODY = """# Components

component-order owns entity-1 and entity-2 through pattern-cqrs.

system-pattern-event-sourcing names the cross-cutting write model.
"""

COMPONENTS_TEXT = f"""---
system_patterns:
- id: system-pattern-event-sourcing
  name: Event sourcing
  statement: Domain events are the system of record for state changes.
component_patterns:
- id: pattern-cqrs
  name: CQRS
  statement: Commands and queries follow separate paths through the order slice.
stores:
- id: store-orders
  category: relational
  sharing: component-owned
  product: PostgreSQL
components:
- id: component-order
  name: Order slice
  entity_ids:
  - entity-1
  - entity-2
  pattern_ids:
  - pattern-cqrs
  - system-pattern-event-sourcing
  constraint_ids:
  - constraint-1
  store_ids:
  - store-orders
decisions:
- id: decision-3
  chosen_option: One component owns the checkout path end to end.
  rejected_alternatives:
  - option: Split cart and payment into separate components.
    reason: Two lifecycles to reconcile for no downstream reader.
  rationale: Checkout is one aggregate boundary.
  anchor: component-order
  status: pending
---
{COMPONENTS_BODY}"""

PLANS_BODY = """# Plans

plan-order-core keeps component-order as one plan. plan-auth is cross-cutting.

assumption-1 says checkout stays in plan-order-core until auth lands.
"""

PLANS_TEXT = f"""---
plans:
- id: plan-order-core
  title: Order core
  intent: Let checkout create the order before authentication is required.
  non_goals:
  - Authentication plumbing shared across all slices.
  disposition: keep
  component_ids:
  - component-order
  draft_seed_path: seeds/order-core.md
  sizing_rationale: One component, one plan.
- id: plan-auth
  title: Auth plumbing
  intent: Provide shared authentication boundaries to every delivery slice.
  non_goals:
  - Checkout-specific order creation behavior.
  disposition: cross-cutting
  draft_seed_path: seeds/auth.md
  sizing_rationale: Shared across slices.
ordering:
- plan_id: plan-order-core
  depends_on: []
  assumption_targets:
  - plan-auth
- plan_id: plan-auth
assumptions:
- id: assumption-1
  statement: Checkout stays in plan-order-core until auth lands.
  consuming_plan_ids:
  - plan-order-core
decisions:
- id: decision-4
  chosen_option: Ship auth as a cross-cutting plan.
  rejected_alternatives:
  - option: Fold auth into every slice.
    reason: Duplicates the same plumbing five times.
  rationale: One auth plan keeps the hand-off readable.
  anchor: plan-auth
  status: pending
---
{PLANS_BODY}"""


def _domain_frontmatter() -> dict:
    """The conforming domain fixture's frontmatter, as a mutable mapping."""
    return yaml.safe_load(DOMAIN_TEXT.split("---\n")[1])


def _constraints_frontmatter() -> dict:
    return yaml.safe_load(CONSTRAINTS_TEXT.split("---\n")[1])


def _domain_text(frontmatter: dict, body: str = DOMAIN_BODY) -> str:
    return f"---\n{yaml.safe_dump(frontmatter, sort_keys=False)}---\n{body}"


def _constraints_text(frontmatter: dict, body: str = CONSTRAINTS_BODY) -> str:
    return f"---\n{yaml.safe_dump(frontmatter, sort_keys=False)}---\n{body}"


def _constraints_text_with_pending_decision() -> str:
    """``CONSTRAINTS_TEXT``'s only decision (``decision-2``) starts ``settled``;
    flip it to ``pending`` so a settlement test has a row to work with."""
    frontmatter = _constraints_frontmatter()
    frontmatter["decisions"][0]["status"] = "pending"
    return _constraints_text(frontmatter)


def _components_frontmatter() -> dict:
    return yaml.safe_load(COMPONENTS_TEXT.split("---\n")[1])


def _components_text(frontmatter: dict, body: str = COMPONENTS_BODY) -> str:
    return f"---\n{yaml.safe_dump(frontmatter, sort_keys=False)}---\n{body}"


def _plans_frontmatter() -> dict:
    return yaml.safe_load(PLANS_TEXT.split("---\n")[1])


def _plans_text(frontmatter: dict, body: str = PLANS_BODY) -> str:
    return f"---\n{yaml.safe_dump(frontmatter, sort_keys=False)}---\n{body}"


def _plans_with_feedback(*rows: dict) -> str:
    frontmatter = _plans_frontmatter()
    frontmatter["feedback"] = list(rows)
    return _plans_text(frontmatter)


def _plans_with_removal(record: dict) -> str:
    frontmatter = _plans_frontmatter()
    frontmatter["removals"] = [record]
    return _plans_text(frontmatter)


def _reviewed_plans_frontmatter() -> dict:
    frontmatter = _plans_frontmatter()
    frontmatter["feedback"] = [
        _feedback_row(
            target={"kind": "row", "row_id": "plan-order-core"},
            request="Split payment into its own plan.",
        ),
        _feedback_row(
            id="feedback-2",
            target={"kind": "artifact"},
            request="Name the cross-cutting auth plan.",
            state="awaiting-review",
            proposed_response="Added plan-auth.",
        ),
    ]
    frontmatter["removals"] = [
        _removal_record(
            removed_id="assumption-1",
            rationale="The reviewer asked to drop the auth dependency.",
            feedback_ids=["feedback-1"],
        )
    ]
    return frontmatter


# The review collections are spliced in through these rather than written into
# DOMAIN_TEXT / CONSTRAINTS_TEXT: those two fixtures stay feedback-free, which
# is what proves an unreviewed artifact still renders exactly its design keys.


def _feedback_row(**changes) -> dict:
    """One conforming ``open`` feedback row, with ``changes`` applied."""
    row = {
        "id": "feedback-1",
        "target": {"kind": "row", "row_id": "entity-1"},
        "request": "Split the cart out of the order entity.",
        "state": "open",
    }
    row.update(changes)
    return row


def _feedback_reopen_record(**changes) -> dict:
    """One complete, redacted record for an explicitly confirmed reopen."""
    record = {
        "selector": {"artifact_key": "domain", "feedback_id": "feedback-1"},
        "reason": "operator-confirmed-evidence-unavailable",
        "nonce": "A" * 43,
        "recorded_at": "2026-08-27T14:15:16.123456Z",
    }
    record.update(changes)
    return record


def _removal_record(**changes) -> dict:
    """One conforming removal record, with ``changes`` applied."""
    record = {
        "removed_id": "workflow-1",
        "rationale": "The cart split moved this path onto the cart entity.",
        "feedback_ids": ["feedback-1"],
    }
    record.update(changes)
    return record


def _domain_with_feedback(*rows: dict) -> str:
    """Domain text carrying exactly ``rows`` as its feedback collection."""
    frontmatter = _domain_frontmatter()
    frontmatter["feedback"] = list(rows)
    return _domain_text(frontmatter)


def _domain_with_removal(record: dict) -> str:
    frontmatter = _domain_frontmatter()
    frontmatter["removals"] = [record]
    return _domain_text(frontmatter)


def _components_with_feedback(*rows: dict) -> str:
    frontmatter = _components_frontmatter()
    frontmatter["feedback"] = list(rows)
    return _components_text(frontmatter)


def _components_with_removal(record: dict) -> str:
    frontmatter = _components_frontmatter()
    frontmatter["removals"] = [record]
    return _components_text(frontmatter)


def _reviewed_components_frontmatter() -> dict:
    frontmatter = _components_frontmatter()
    frontmatter["feedback"] = [
        _feedback_row(
            target={"kind": "row", "row_id": "component-order"},
            request="Split payment into its own component.",
        ),
        _feedback_row(
            id="feedback-2",
            target={"kind": "artifact"},
            request="Name the system pattern that owns writes.",
            state="awaiting-review",
            proposed_response="Added system-pattern-event-sourcing.",
        ),
    ]
    frontmatter["removals"] = [
        _removal_record(
            removed_id="pattern-cqrs",
            rationale="The reviewer asked to drop CQRS from this slice.",
            feedback_ids=["feedback-1"],
        )
    ]
    return frontmatter


def _reviewed_domain_frontmatter() -> dict:
    """The conforming domain fixture plus both review collections."""
    frontmatter = _domain_frontmatter()
    frontmatter["feedback"] = [
        _feedback_row(),
        _feedback_row(
            id="feedback-2",
            target={"kind": "artifact"},
            request="Name the workflow that captures payment.",
            state="awaiting-review",
            proposed_response="Added workflow-2 to cover payment capture.",
        ),
    ]
    frontmatter["removals"] = [_removal_record()]
    return frontmatter


def _reviewed_constraints_frontmatter() -> dict:
    """The conforming constraints fixture plus both review collections."""
    frontmatter = _constraints_frontmatter()
    frontmatter["feedback"] = [
        _feedback_row(
            target={"kind": "row", "row_id": "constraint-1"},
            request="Loosen the checkout budget to 500ms.",
        ),
        _feedback_row(
            id="feedback-2",
            target={"kind": "artifact"},
            request="Say what the availability trade bought.",
            state="deferred",
        ),
    ]
    frontmatter["removals"] = [
        _removal_record(
            removed_id="attribute-reliability",
            rationale="Folded into fault-tolerance at the reviewer's request.",
            feedback_ids=["feedback-2"],
        )
    ]
    return frontmatter


# --------------------------------------------------------------------------
# Paths and slugs
# --------------------------------------------------------------------------


def test_roadmap_dir_sits_under_the_given_plans_dir(tmp_path: Path) -> None:
    assert roadmap_dir(tmp_path, "checkout") == tmp_path / ROADMAP_DIRNAME / "checkout"


def test_stage_path_is_normalized_posix_relative_to_roadmap_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    absolute_plans_dir = tmp_path / "workspace" / "plans"
    slug = "checkout"

    absolute = roadmap_relative_stage_path(
        absolute_plans_dir, slug, domain_path(absolute_plans_dir, slug)
    )
    monkeypatch.chdir(tmp_path)
    relative_plans_dir = Path("workspace") / "plans"
    relative = roadmap_relative_stage_path(
        relative_plans_dir, slug, domain_path(relative_plans_dir, slug)
    )
    dot_normalized = roadmap_relative_stage_path(
        Path("workspace") / "." / "plans",
        slug,
        domain_path(Path("workspace") / "." / "plans", slug),
    )

    assert absolute == relative == dot_normalized == DOMAIN_FILENAME


def test_stage_path_rejects_a_path_outside_the_roadmap_root(tmp_path: Path) -> None:
    with pytest.raises(RoadmapArtifactError):
        roadmap_relative_stage_path(tmp_path, "checkout", tmp_path / "outside.md")


def test_domain_and_constraints_paths_share_the_roadmap_dir(tmp_path: Path) -> None:
    domain = domain_path(tmp_path, "checkout")
    constraints = constraints_path(tmp_path, "checkout")
    assert domain.parent == constraints.parent == roadmap_dir(tmp_path, "checkout")
    assert domain.name == DOMAIN_FILENAME
    assert constraints.name == CONSTRAINTS_FILENAME


def test_paths_follow_an_arbitrary_plans_dir(tmp_path: Path) -> None:
    """No default plans directory is baked in — both artifacts move with the
    directory the caller resolved."""
    elsewhere = tmp_path / "somewhere" / "else"
    assert domain_path(elsewhere, "checkout") == (
        elsewhere / ROADMAP_DIRNAME / "checkout" / DOMAIN_FILENAME
    )
    assert constraints_path(elsewhere, "checkout") == (
        elsewhere / ROADMAP_DIRNAME / "checkout" / CONSTRAINTS_FILENAME
    )
    assert components_path(elsewhere, "checkout") == (
        elsewhere / ROADMAP_DIRNAME / "checkout" / COMPONENTS_FILENAME
    )
    assert domain_path(elsewhere, "checkout").is_relative_to(elsewhere)


def test_components_path_sits_under_the_roadmap_dir(tmp_path: Path) -> None:
    assert components_path(tmp_path, "checkout") == (
        tmp_path / ROADMAP_DIRNAME / "checkout" / COMPONENTS_FILENAME
    )


def test_components_path_follows_an_arbitrary_plans_dir(tmp_path: Path) -> None:
    elsewhere = tmp_path / "somewhere" / "else"
    assert components_path(elsewhere, "checkout") == (
        elsewhere / ROADMAP_DIRNAME / "checkout" / COMPONENTS_FILENAME
    )
    assert components_path(elsewhere, "checkout").is_relative_to(elsewhere)


@pytest.mark.parametrize("slug", ["a/b", "a\\b", "/abs"])
def test_slug_with_a_path_separator_is_rejected(tmp_path: Path, slug: str) -> None:
    with pytest.raises(ValueError) as exc:
        roadmap_dir(tmp_path, slug)
    assert repr(slug) in str(exc.value)


@pytest.mark.parametrize("slug", ["..", "../escape", "nested/../escape"])
def test_slug_with_a_parent_traversal_component_is_rejected(tmp_path: Path, slug: str) -> None:
    with pytest.raises(ValueError):
        domain_path(tmp_path, slug)


@pytest.mark.parametrize("slug", ["", "   ", "\t"])
def test_empty_or_whitespace_slug_is_rejected(tmp_path: Path, slug: str) -> None:
    with pytest.raises(ValueError) as exc:
        constraints_path(tmp_path, slug)
    assert repr(slug) in str(exc.value)


def test_roadmap_subdir_is_not_matched_by_a_top_level_md_glob(tmp_path: Path) -> None:
    """Plan discovery globs ``*.md`` at the top level only, so nesting the
    artifacts is what keeps them invisible to it."""
    (tmp_path / "2-a-plan.md").write_text("plan", encoding="utf-8")
    artifact = domain_path(tmp_path, "checkout")
    artifact.parent.mkdir(parents=True)
    artifact.write_text(DOMAIN_TEXT, encoding="utf-8")

    assert [p.name for p in tmp_path.glob("*.md")] == ["2-a-plan.md"]


# --------------------------------------------------------------------------
# Closed vocabularies
# --------------------------------------------------------------------------


def test_decision_status_members() -> None:
    assert [member.value for member in DecisionStatus] == ["settled", "pending"]


def test_constraint_disposition_includes_not_load_bearing() -> None:
    values = [member.value for member in ConstraintDisposition]
    assert values == ["prioritized", "traded-away", "not-load-bearing"]


def test_quality_attribute_list_is_ordered_and_has_no_duplicates() -> None:
    assert QUALITY_ATTRIBUTES == (
        "performance",
        "scalability",
        "security",
        "availability",
        "maintainability",
        "fault-tolerance",
        "reliability",
    )
    assert len(set(QUALITY_ATTRIBUTES)) == len(QUALITY_ATTRIBUTES)


def test_unknown_decision_status_raises_naming_the_value() -> None:
    frontmatter = _domain_frontmatter()
    frontmatter["decisions"][0]["status"] = "confirmed"
    with pytest.raises(RoadmapArtifactError) as exc:
        parse_domain_artifact(_domain_text(frontmatter))
    message = str(exc.value)
    assert "confirmed" in message
    assert "decision-1" in message


def test_unknown_disposition_raises_naming_the_value() -> None:
    frontmatter = _constraints_frontmatter()
    frontmatter["dispositions"][0]["disposition"] = "nice-to-have"
    with pytest.raises(RoadmapArtifactError) as exc:
        parse_constraints_artifact(_constraints_text(frontmatter))
    message = str(exc.value)
    assert "nice-to-have" in message
    assert "attribute-performance" in message


# --------------------------------------------------------------------------
# Domain artifact parsing
# --------------------------------------------------------------------------


def test_conforming_domain_body_parses_every_row_kind() -> None:
    artifact = parse_domain_artifact(DOMAIN_TEXT)

    assert [row.id for row in artifact.entities] == ["entity-1", "entity-2"]
    assert artifact.entities[0].name == "Order"
    assert [row.id for row in artifact.business_rules] == ["rule-1"]
    assert artifact.business_rules[0].entity_ids == ("entity-1", "entity-2")
    assert [row.id for row in artifact.workflows] == ["workflow-1"]
    assert artifact.workflows[0].entity_ids == ("entity-1",)

    decision = artifact.decisions[0]
    assert decision.id == "decision-1"
    assert decision.status is DecisionStatus.PENDING
    assert decision.anchor == "entity-1"
    assert decision.rejected_alternatives[0].option == "A separate cart entity."
    assert "no downstream reader" in decision.rejected_alternatives[0].reason
    assert decision.rationale.startswith("One aggregate")


def test_missing_opening_fence_raises() -> None:
    with pytest.raises(RoadmapArtifactError) as exc:
        parse_domain_artifact("# Domain\n\nNo frontmatter here.\n")
    assert "line 1" in str(exc.value)


def test_unclosed_frontmatter_fence_raises() -> None:
    with pytest.raises(RoadmapArtifactError) as exc:
        parse_domain_artifact("---\nentities: []\n\n# Domain\n")
    assert "closing fence" in str(exc.value)


def test_malformed_yaml_raises_and_names_the_path(tmp_path: Path) -> None:
    path = tmp_path / DOMAIN_FILENAME
    path.write_text("---\nentities: [unclosed\n---\n# Domain\n", encoding="utf-8")

    with pytest.raises(RoadmapArtifactError) as exc:
        load_domain_artifact(path)
    assert exc.value.path == path
    assert str(path) in str(exc.value)


def test_malformed_feedback_scalar_suggests_a_block_scalar_repair() -> None:
    malformed = """\
---
feedback:
- id: fb-1
  target:
    kind: artifact
  request: 'Keep plan-tool''s guarantee and explain the roadmap's model-authored content.'
  state: open
---
# Domain
"""

    with pytest.raises(RoadmapArtifactError) as exc:
        parse_domain_artifact(malformed)

    assert "line 5" in str(exc.value)
    assert "request: >-" in str(exc.value)
    assert "<your request>" in str(exc.value)


def test_malformed_feedback_with_trailing_tab_suggests_a_block_scalar_repair() -> None:
    malformed = """\
---
feedback:\t
- id: fb-1
  target:
    kind: artifact
  request: "Repair this request."
  state: open
---
# Domain
"""

    with pytest.raises(RoadmapArtifactError) as exc:
        parse_domain_artifact(malformed)

    assert "request: >-" in str(exc.value)


def test_undecodable_bytes_raise_roadmap_artifact_error_naming_the_path(
    tmp_path: Path,
) -> None:
    path = tmp_path / DOMAIN_FILENAME
    path.write_bytes(b"\xff\xfe not valid utf-8")

    with pytest.raises(RoadmapArtifactError) as exc:
        load_domain_artifact(path)
    assert exc.value.path == path
    assert str(path) in str(exc.value)


def test_missing_required_row_key_raises_naming_the_row() -> None:
    frontmatter = _domain_frontmatter()
    del frontmatter["workflows"][0]["entity_ids"]
    with pytest.raises(RoadmapArtifactError) as exc:
        parse_domain_artifact(_domain_text(frontmatter))
    message = str(exc.value)
    assert "workflow-1" in message
    assert "entity_ids" in message

    without_id = _domain_frontmatter()
    del without_id["workflows"][0]["id"]
    with pytest.raises(RoadmapArtifactError) as exc:
        parse_domain_artifact(_domain_text(without_id))
    assert "'workflows' row 0" in str(exc.value)


def test_wrong_type_for_a_row_collection_raises() -> None:
    frontmatter = _domain_frontmatter()
    frontmatter["entities"] = "entity-1"
    with pytest.raises(RoadmapArtifactError) as exc:
        parse_domain_artifact(_domain_text(frontmatter))
    assert "'entities' must be a list of rows" in str(exc.value)


def test_duplicate_row_ids_survive_as_separate_rows() -> None:
    """Rows stay an ordered tuple so the duplicate-id gate has both to report."""
    frontmatter = _domain_frontmatter()
    frontmatter["entities"].append(
        {"id": "entity-1", "name": "Order (again)", "fields": [{"name": "total", "type": "number"}]}
    )

    artifact = parse_domain_artifact(_domain_text(frontmatter))
    assert [row.id for row in artifact.entities] == [
        "entity-1",
        "entity-2",
        "entity-1",
    ]


def test_prose_body_is_preserved_unchanged() -> None:
    body = "# Domain\n\n\nentity-1 stands alone.\n\n---\n\nA trailing rule.\n"
    artifact = parse_domain_artifact(_domain_text(_domain_frontmatter(), body))
    assert artifact.body == body


# --------------------------------------------------------------------------
# Constraints artifact parsing
# --------------------------------------------------------------------------


def test_conforming_constraints_body_parses_attributes_and_constraints() -> None:
    artifact = parse_constraints_artifact(CONSTRAINTS_TEXT)

    assert [row.attribute for row in artifact.dispositions] == list(QUALITY_ATTRIBUTES)
    assert artifact.dispositions[0].id == "attribute-performance"
    assert artifact.dispositions[0].disposition is ConstraintDisposition.PRIORITIZED
    assert artifact.dispositions[-1].disposition is (ConstraintDisposition.NOT_LOAD_BEARING)

    constraint = artifact.constraints[0]
    assert constraint.id == "constraint-1"
    assert constraint.attribute == "performance"
    assert constraint.anchor_ids == ("entity-1", "workflow-1")
    assert artifact.decisions[0].status is DecisionStatus.SETTLED


def test_constraint_anchor_ids_parse_without_being_resolved() -> None:
    """Resolution is a gate; the parser only checks the ids are ids."""
    frontmatter = _constraints_frontmatter()
    frontmatter["constraints"][0]["anchor_ids"] = ["entity-999"]

    artifact = parse_constraints_artifact(_constraints_text(frontmatter))
    assert artifact.constraints[0].anchor_ids == ("entity-999",)


def test_attribute_missing_from_the_body_still_parses() -> None:
    frontmatter = _constraints_frontmatter()
    frontmatter["dispositions"] = frontmatter["dispositions"][:3]

    artifact = parse_constraints_artifact(_constraints_text(frontmatter))
    assert len(artifact.dispositions) == 3


def test_unknown_frontmatter_keys_are_ignored_not_rejected() -> None:
    """The schema is open: an extra key must not cost a stage a retry."""
    frontmatter = _constraints_frontmatter()
    frontmatter["notes"] = "an operator's aside"
    frontmatter["constraints"][0]["owner"] = "platform"

    artifact = parse_constraints_artifact(_constraints_text(frontmatter))
    assert artifact.constraints[0].id == "constraint-1"
    assert "owner" not in render_constraints_artifact(artifact)


def test_decision_with_no_rejected_alternative_still_parses() -> None:
    frontmatter = _constraints_frontmatter()
    frontmatter["decisions"][0]["rejected_alternatives"] = []

    artifact = parse_constraints_artifact(_constraints_text(frontmatter))
    assert artifact.decisions[0].rejected_alternatives == ()


@pytest.mark.parametrize("field", ("rationale", "rejected_alternatives"))
def test_roadmap_derived_decision_requires_existing_deliberation_fields(field: str) -> None:
    frontmatter = _domain_frontmatter()
    del frontmatter["decisions"][0][field]

    with pytest.raises(RoadmapArtifactError, match=field):
        parse_domain_artifact(_domain_text(frontmatter))


def test_inherited_decision_parses_with_a_source_citation() -> None:
    frontmatter = _domain_frontmatter()
    decision = frontmatter["decisions"][0]
    decision["source"] = "answer-cart-ownership"
    del decision["rationale"]
    del decision["rejected_alternatives"]

    parsed = parse_domain_artifact(_domain_text(frontmatter)).decisions[0]

    assert parsed.source == "answer-cart-ownership"
    assert parsed.rationale is None
    assert parsed.rejected_alternatives == ()


@pytest.mark.parametrize("field", ("source", "rationale"))
def test_decision_null_citation_or_deliberation_refuses(field: str) -> None:
    frontmatter = _domain_frontmatter()
    frontmatter["decisions"][0]["source"] = "answer-cart-ownership"
    frontmatter["decisions"][0][field] = None

    with pytest.raises(RoadmapArtifactError, match=field):
        parse_domain_artifact(_domain_text(frontmatter))


def test_inherited_decision_renders_source_without_null_or_generated_fields() -> None:
    frontmatter = _domain_frontmatter()
    decision = frontmatter["decisions"][0]
    decision["source"] = "answer-cart-ownership"
    del decision["rationale"]
    del decision["rejected_alternatives"]

    rendered = yaml.safe_load(
        render_domain_artifact(parse_domain_artifact(_domain_text(frontmatter))).split("---\n")[1]
    )["decisions"][0]

    assert rendered["source"] == "answer-cart-ownership"
    assert "rationale" not in rendered
    assert "rejected_alternatives" not in rendered


def test_roadmap_derived_decision_renders_without_source_key() -> None:
    rendered = yaml.safe_load(
        render_domain_artifact(parse_domain_artifact(DOMAIN_TEXT)).split("---\n")[1]
    )["decisions"][0]

    assert "source" not in rendered


def test_inherited_decision_with_unresolved_or_unconfirmed_source_still_parses() -> None:
    frontmatter = _domain_frontmatter()
    decision = frontmatter["decisions"][0]
    decision["source"] = "unconfirmed-answer"
    del decision["rationale"]
    del decision["rejected_alternatives"]

    assert parse_domain_artifact(_domain_text(frontmatter)).decisions[0].source == (
        "unconfirmed-answer"
    )


# --------------------------------------------------------------------------
# Entity fields
# --------------------------------------------------------------------------


def test_entity_fields_parse_into_typed_rows() -> None:
    artifact = parse_domain_artifact(DOMAIN_TEXT)

    assert artifact.entities[0].fields == (
        FieldRow(name="placed_at", type=FieldType.TIMESTAMP),
        FieldRow(name="customer", type=FieldType.REFERENCE, entity_id="entity-2"),
    )
    assert artifact.entities[1].fields == (FieldRow(name="email", type=FieldType.TEXT),)


def test_a_missing_fields_key_is_a_parse_error() -> None:
    frontmatter = _domain_frontmatter()
    del frontmatter["entities"][0]["fields"]

    with pytest.raises(RoadmapArtifactError) as excinfo:
        parse_domain_artifact(_domain_text(frontmatter))

    assert "missing required key 'fields'" in str(excinfo.value)


def test_a_present_but_empty_fields_list_parses() -> None:
    """Empty parses so the *gate* reports it against the row — a parse error
    would name no row for the retry to fix."""
    frontmatter = _domain_frontmatter()
    frontmatter["entities"][0]["fields"] = []

    artifact = parse_domain_artifact(_domain_text(frontmatter))

    assert artifact.entities[0].fields == ()


def test_an_unknown_field_type_is_a_parse_error_naming_the_vocabulary() -> None:
    frontmatter = _domain_frontmatter()
    frontmatter["entities"][0]["fields"] = [{"name": "total", "type": "varchar(255)"}]

    with pytest.raises(RoadmapArtifactError) as excinfo:
        parse_domain_artifact(_domain_text(frontmatter))

    message = str(excinfo.value)
    assert "varchar(255)" in message
    assert all(member.value in message for member in FieldType)


def test_a_field_missing_its_type_names_the_field_not_the_entity_row() -> None:
    """The message is retry text: naming only the entity reads as if the
    *entity* were missing a `type`, which is not the edit to make."""
    frontmatter = _domain_frontmatter()
    frontmatter["entities"][0]["fields"] = [{"name": "total"}]

    with pytest.raises(RoadmapArtifactError) as excinfo:
        parse_domain_artifact(_domain_text(frontmatter))

    message = str(excinfo.value)
    assert "field 'total'" in message
    assert "missing required key 'type'" in message


@pytest.mark.parametrize("name", ["", "   ", None, 7])
def test_a_blank_or_untyped_field_name_is_a_parse_error(name) -> None:
    """A nameless field would satisfy the presence gate while telling a
    downstream plan nothing — so the name is identifier-like, not prose."""
    frontmatter = _domain_frontmatter()
    frontmatter["entities"][0]["fields"] = [{"name": name, "type": "text"}]

    with pytest.raises(RoadmapArtifactError) as excinfo:
        parse_domain_artifact(_domain_text(frontmatter))

    assert "non-empty string 'name'" in str(excinfo.value)


def test_a_non_list_fields_value_is_a_parse_error() -> None:
    frontmatter = _domain_frontmatter()
    frontmatter["entities"][0]["fields"] = "placed_at"

    with pytest.raises(RoadmapArtifactError) as excinfo:
        parse_domain_artifact(_domain_text(frontmatter))

    assert "must be a list of rows" in str(excinfo.value)


def test_a_non_mapping_field_entry_is_a_parse_error() -> None:
    frontmatter = _domain_frontmatter()
    frontmatter["entities"][0]["fields"] = ["placed_at"]

    with pytest.raises(RoadmapArtifactError) as excinfo:
        parse_domain_artifact(_domain_text(frontmatter))

    assert "must be a mapping" in str(excinfo.value)


@pytest.mark.parametrize("entity_id", ["", "   ", 7])
def test_a_field_entity_id_that_is_not_a_non_empty_string_is_a_parse_error(
    entity_id,
) -> None:
    frontmatter = _domain_frontmatter()
    frontmatter["entities"][0]["fields"] = [
        {"name": "customer", "type": "reference", "entity_id": entity_id}
    ]

    with pytest.raises(RoadmapArtifactError) as excinfo:
        parse_domain_artifact(_domain_text(frontmatter))

    assert "'entity_id'" in str(excinfo.value)


def test_field_type_vocabulary_has_no_collection_member() -> None:
    """A to-many needs an element type to mean anything; cardinality is a
    plan's decision. Deliberate — see FieldType's docstring."""
    assert "collection" not in {member.value for member in FieldType}


def test_a_non_reference_field_renders_without_an_entity_id_key() -> None:
    artifact = parse_domain_artifact(DOMAIN_TEXT)

    rendered = render_domain_artifact(artifact)

    assert "  - name: email\n    type: text\n" in rendered
    assert "entity_id: null" not in rendered


# --------------------------------------------------------------------------
# Round-trip
# --------------------------------------------------------------------------


def test_domain_artifact_round_trips_through_render_and_parse() -> None:
    artifact = parse_domain_artifact(DOMAIN_TEXT)
    assert parse_domain_artifact(render_domain_artifact(artifact)) == artifact


def test_constraints_artifact_round_trips_through_render_and_parse() -> None:
    artifact = parse_constraints_artifact(CONSTRAINTS_TEXT)
    rendered = render_constraints_artifact(artifact)
    assert parse_constraints_artifact(rendered) == artifact


def test_decision_rows_round_trip_for_inherited_and_roadmap_derived_forms() -> None:
    frontmatter = _domain_frontmatter()
    inherited = dict(frontmatter["decisions"][0])
    inherited.update({"id": "decision-inherited", "source": "answer-cart-ownership"})
    frontmatter["decisions"].append(inherited)
    sparse_inherited = dict(inherited, id="decision-inherited-sparse")
    del sparse_inherited["rationale"]
    del sparse_inherited["rejected_alternatives"]
    frontmatter["decisions"].append(sparse_inherited)

    artifact = parse_domain_artifact(_domain_text(frontmatter))

    assert parse_domain_artifact(render_domain_artifact(artifact)) == artifact


def test_legacy_decision_artifact_parses_and_renders_unchanged() -> None:
    artifact = parse_domain_artifact(DOMAIN_TEXT)
    rendered = render_domain_artifact(artifact)

    assert parse_domain_artifact(rendered).decisions == artifact.decisions
    assert yaml.safe_load(rendered.split("---\n")[1])["decisions"] == _domain_frontmatter()[
        "decisions"
    ]


def test_hosting_rows_round_trip_and_render_before_other_constraints_rows() -> None:
    frontmatter = _constraints_frontmatter()
    frontmatter["hosting"] = [
        {
            "id": "hosting-compute",
            "facet": "compute",
            "value": "managed-cloud",
            "product": "Cloud Run",
        },
        {"id": "hosting-model", "facet": "model", "value": "managed-api"},
        {"id": "hosting-topology", "facet": "topology", "value": "single-region"},
    ]

    artifact = parse_constraints_artifact(_constraints_text(frontmatter))
    rendered = render_constraints_artifact(artifact)
    rendered_frontmatter = yaml.safe_load(rendered.split("---\n")[1])

    assert artifact.hosting == (
        HostingRow(
            id="hosting-compute",
            facet="compute",
            value="managed-cloud",
            product="Cloud Run",
        ),
        HostingRow(id="hosting-model", facet="model", value="managed-api"),
        HostingRow(id="hosting-topology", facet="topology", value="single-region"),
    )
    assert tuple(rendered_frontmatter) == CONSTRAINTS_ROW_KEYS
    assert parse_constraints_artifact(rendered) == artifact


def test_absent_hosting_collection_parses_as_an_empty_tuple() -> None:
    assert parse_constraints_artifact(CONSTRAINTS_TEXT).hosting == ()


@pytest.mark.parametrize("field", ["id", "facet", "value"])
def test_hosting_row_requires_each_structural_field(field: str) -> None:
    frontmatter = _constraints_frontmatter()
    hosting = {
        "id": "hosting-compute",
        "facet": "compute",
        "value": "managed-cloud",
    }
    del hosting[field]
    frontmatter["hosting"] = [hosting]

    with pytest.raises(RoadmapArtifactError, match=r"hosting.*hosting-compute|hosting.*row 0"):
        parse_constraints_artifact(_constraints_text(frontmatter))


@pytest.mark.parametrize(
    ("facet", "value"),
    [("future-facet", "managed-cloud"), ("compute", "future-value")],
)
def test_unknown_hosting_facet_or_value_remains_parseable(facet: str, value: str) -> None:
    frontmatter = _constraints_frontmatter()
    frontmatter["hosting"] = [{"id": "hosting-future", "facet": facet, "value": value}]

    artifact = parse_constraints_artifact(_constraints_text(frontmatter))

    assert artifact.hosting == (HostingRow(id="hosting-future", facet=facet, value=value),)


def test_unknown_hosting_facet_with_product_remains_parseable() -> None:
    frontmatter = _constraints_frontmatter()
    frontmatter["hosting"] = [
        {
            "id": "hosting-future",
            "facet": "future-facet",
            "value": "managed-cloud",
            "product": "Future Product",
        }
    ]

    artifact = parse_constraints_artifact(_constraints_text(frontmatter))

    assert artifact.hosting == (
        HostingRow(
            id="hosting-future",
            facet="future-facet",
            value="managed-cloud",
            product="Future Product",
        ),
    )


def test_hosting_compute_product_round_trips_and_absent_product_is_omitted() -> None:
    artifact = ConstraintsArtifact(
        dispositions=(),
        constraints=(),
        decisions=(),
        body="",
        hosting=(
            HostingRow(
                id="hosting-compute",
                facet="compute",
                value="managed-cloud",
                product="Cloud Run",
            ),
            HostingRow(id="hosting-model", facet="model", value="managed-api"),
        ),
    )

    rendered = render_constraints_artifact(artifact)
    rendered_frontmatter = yaml.safe_load(rendered.split("---\n")[1])

    assert "product: Cloud Run" in rendered
    assert "product: null" not in rendered
    assert "product" not in rendered_frontmatter["hosting"][1]
    assert parse_constraints_artifact(rendered) == artifact


def test_existing_product_only_rows_keep_product_and_default_description() -> None:
    hosting = HostingRow("hosting-compute", "compute", "managed-cloud", "Cloud Run")
    store = StoreRow("store-orders", "relational", "component-owned", "PostgreSQL")

    assert hosting.product == "Cloud Run"
    assert hosting.description is None
    assert hosting.research_disclosure is None
    assert store.product == "PostgreSQL"
    assert store.description is None
    assert store.research_disclosure is None


def test_hosting_and_store_descriptions_round_trip_and_omit_none() -> None:
    constraints_frontmatter = _constraints_frontmatter()
    constraints_frontmatter["hosting"] = [
        {
            "id": "hosting-compute",
            "facet": "compute",
            "value": "managed-cloud",
            "description": "Internal platform runtime.",
        },
        {
            "id": "hosting-model",
            "facet": "model",
            "value": "managed-api",
            "description": None,
        },
        {
            "id": "hosting-topology",
            "facet": "topology",
            "value": "single-region",
        },
    ]
    components_frontmatter = _components_frontmatter()
    components_frontmatter["stores"] = [
        {
            "id": "store-orders",
            "category": "relational",
            "sharing": "component-owned",
            "description": "The orders team operates this internal store.",
        },
        {
            "id": "store-audit",
            "category": "document",
            "sharing": "shared",
            "description": None,
        },
        {
            "id": "store-cache",
            "category": "key-value",
            "sharing": "shared",
        },
    ]

    constraints = parse_constraints_artifact(_constraints_text(constraints_frontmatter))
    components = parse_components_artifact(_components_text(components_frontmatter))
    rendered_constraints = render_constraints_artifact(constraints)
    rendered_components = render_components_artifact(components)
    hosting_rows = yaml.safe_load(rendered_constraints.split("---\n")[1])["hosting"]
    store_rows = yaml.safe_load(rendered_components.split("---\n")[1])["stores"]

    assert constraints.hosting[0].description == "Internal platform runtime."
    assert components.stores[0].description == "The orders team operates this internal store."
    assert "description" not in hosting_rows[1]
    assert "description" not in hosting_rows[2]
    assert "description" not in store_rows[1]
    assert "description" not in store_rows[2]
    assert parse_constraints_artifact(rendered_constraints) == constraints
    assert parse_components_artifact(rendered_components) == components


def test_optional_description_preserves_whitespace_and_rejects_non_strings() -> None:
    whitespace = " \t "
    constraints_frontmatter = _constraints_frontmatter()
    constraints_frontmatter["hosting"] = [
        {
            "id": "hosting-compute",
            "facet": "compute",
            "value": "managed-cloud",
            "description": whitespace,
        }
    ]
    components_frontmatter = _components_frontmatter()
    components_frontmatter["stores"][0]["description"] = whitespace

    constraints = parse_constraints_artifact(_constraints_text(constraints_frontmatter))
    components = parse_components_artifact(_components_text(components_frontmatter))

    assert parse_constraints_artifact(
        render_constraints_artifact(constraints)
    ).hosting[0].description == whitespace
    assert parse_components_artifact(
        render_components_artifact(components)
    ).stores[0].description == whitespace

    constraints_frontmatter["hosting"][0]["description"] = 1
    components_frontmatter["stores"][0]["description"] = []
    with pytest.raises(RoadmapArtifactError, match=r"hosting-compute.*description.*string"):
        parse_constraints_artifact(_constraints_text(constraints_frontmatter))
    with pytest.raises(RoadmapArtifactError, match=r"store-orders.*description.*string"):
        parse_components_artifact(_components_text(components_frontmatter))


def test_research_disclosure_round_trips_and_rejects_invalid_values() -> None:
    constraints_frontmatter = _constraints_frontmatter()
    constraints_frontmatter["hosting"] = [
        {
            "id": "hosting-compute",
            "facet": "compute",
            "value": "managed-cloud",
            "product": "Cloud Run",
            "research_disclosure": "external",
        },
        {
            "id": "hosting-model",
            "facet": "model",
            "value": "managed-api",
            "research_disclosure": "local",
        },
        {
            "id": "hosting-topology",
            "facet": "topology",
            "value": "single-region",
            "research_disclosure": None,
        },
    ]
    components_frontmatter = _components_frontmatter()
    components_frontmatter["stores"] = [
        {
            "id": "store-orders",
            "category": "relational",
            "sharing": "component-owned",
            "product": "PostgreSQL",
            "research_disclosure": "external",
        },
        {
            "id": "store-audit",
            "category": "document",
            "sharing": "shared",
            "research_disclosure": "local",
        },
        {
            "id": "store-cache",
            "category": "key-value",
            "sharing": "shared",
            "research_disclosure": None,
        },
    ]

    constraints = parse_constraints_artifact(_constraints_text(constraints_frontmatter))
    components = parse_components_artifact(_components_text(components_frontmatter))
    hosting_rows = yaml.safe_load(render_constraints_artifact(constraints).split("---\n")[1])["hosting"]
    store_rows = yaml.safe_load(render_components_artifact(components).split("---\n")[1])["stores"]

    assert constraints.hosting[0].research_disclosure is ResearchDisclosure.EXTERNAL
    assert constraints.hosting[1].research_disclosure is ResearchDisclosure.LOCAL
    assert constraints.hosting[2].research_disclosure is None
    assert components.stores[0].research_disclosure is ResearchDisclosure.EXTERNAL
    assert components.stores[1].research_disclosure is ResearchDisclosure.LOCAL
    assert components.stores[2].research_disclosure is None
    assert "research_disclosure" not in hosting_rows[2]
    assert "research_disclosure" not in store_rows[2]
    assert parse_constraints_artifact(render_constraints_artifact(constraints)) == constraints
    assert parse_components_artifact(render_components_artifact(components)) == components

    constraints_frontmatter["hosting"][0]["research_disclosure"] = "partner"
    components_frontmatter["stores"][0]["research_disclosure"] = []
    with pytest.raises(
        RoadmapArtifactError, match=r"hosting-compute.*research_disclosure.*external.*local"
    ):
        parse_constraints_artifact(_constraints_text(constraints_frontmatter))
    with pytest.raises(RoadmapArtifactError, match=r"store-orders.*research_disclosure.*string"):
        parse_components_artifact(_components_text(components_frontmatter))


@pytest.mark.parametrize("facet", ["model", "topology"])
def test_hosting_product_on_a_known_non_compute_facet_is_a_parse_error(
    facet: str,
) -> None:
    frontmatter = _constraints_frontmatter()
    frontmatter["hosting"] = [
        {
            "id": f"hosting-{facet}",
            "facet": facet,
            "value": "managed",
            "product": "named-product",
        }
    ]

    with pytest.raises(RoadmapArtifactError, match=rf"hosting-{facet}.*product"):
        parse_constraints_artifact(_constraints_text(frontmatter))


def test_hosting_facet_constant_names_the_fixed_facets_without_parsing_them() -> None:
    assert HOSTING_FACETS == ("compute", "model", "topology")


def test_rendered_enum_values_are_plain_strings() -> None:
    rendered = render_domain_artifact(parse_domain_artifact(DOMAIN_TEXT))
    assert "status: pending" in rendered
    assert "DecisionStatus" not in rendered
    assert "!!python" not in rendered

    constraints = render_constraints_artifact(parse_constraints_artifact(CONSTRAINTS_TEXT))
    assert "disposition: not-load-bearing" in constraints
    assert "ConstraintDisposition" not in constraints
    assert parse_constraints_artifact(constraints).dispositions[0] == (
        AttributeDispositionRow(
            id="attribute-performance",
            attribute="performance",
            disposition=ConstraintDisposition.PRIORITIZED,
        )
    )


def test_row_key_constants_match_the_rendered_frontmatter() -> None:
    """The stage prompts pin against these, so they have to be the keys the
    renderer actually writes and the parser actually reads."""
    domain = yaml.safe_load(
        render_domain_artifact(parse_domain_artifact(DOMAIN_TEXT)).split("---\n")[1]
    )
    assert tuple(domain) == DOMAIN_ROW_KEYS

    constraints = yaml.safe_load(
        render_constraints_artifact(parse_constraints_artifact(CONSTRAINTS_TEXT)).split("---\n")[1]
    )
    assert tuple(constraints) == CONSTRAINTS_ROW_KEYS


def test_constraints_artifact_loads_from_disk(tmp_path: Path) -> None:
    """The path form of the parser, which the orchestrator drives."""
    path = constraints_path(tmp_path, "checkout")
    path.parent.mkdir(parents=True)
    path.write_text(CONSTRAINTS_TEXT, encoding="utf-8")

    assert load_constraints_artifact(path) == parse_constraints_artifact(CONSTRAINTS_TEXT)


# --------------------------------------------------------------------------
# Review collections: feedback and removals
# --------------------------------------------------------------------------


def test_feedback_state_members() -> None:
    assert [member.value for member in FeedbackState] == [
        "open",
        "awaiting-review",
        "deferred",
    ]


def test_replace_design_row_rebuilds_only_the_selected_tuple_entry() -> None:
    artifact = parse_domain_artifact(_domain_text(_reviewed_domain_frontmatter()))

    candidate = replace_design_row(
        artifact,
        collection="entities",
        row_id="entity-1",
        field="name",
        value="Customer order",
    )

    assert candidate is not artifact
    assert [row.id for row in candidate.entities] == ["entity-1", "entity-2"]
    assert candidate.entities[0].name == "Customer order"
    assert candidate.entities[0].fields == artifact.entities[0].fields
    assert candidate.entities[1] is artifact.entities[1]
    assert candidate.business_rules == artifact.business_rules
    assert candidate.workflows == artifact.workflows
    assert candidate.decisions == artifact.decisions
    assert candidate.feedback == artifact.feedback
    assert candidate.removals == artifact.removals
    assert candidate.body == artifact.body


@pytest.mark.parametrize(
    ("parser", "text", "collection", "row_id", "field"),
    (
        (parse_domain_artifact, DOMAIN_TEXT, "entities", "entity-1", "name"),
        (
            parse_constraints_artifact,
            CONSTRAINTS_TEXT,
            "constraints",
            "constraint-1",
            "statement",
        ),
        (
            parse_components_artifact,
            COMPONENTS_TEXT,
            "components",
            "component-order",
            "name",
        ),
        (parse_plans_artifact, PLANS_TEXT, "plans", "plan-order-core", "title"),
    ),
)
def test_replace_design_row_handles_each_supported_artifact_shape(
    parser, text: str, collection: str, row_id: str, field: str
) -> None:
    artifact = parser(text)

    candidate = replace_design_row(
        artifact,
        collection=collection,
        row_id=row_id,
        field=field,
        value="Revised presentation",
    )

    source_rows = getattr(artifact, collection)
    candidate_rows = getattr(candidate, collection)
    assert type(candidate) is type(artifact)
    assert [row.id for row in candidate_rows] == [row.id for row in source_rows]
    assert getattr(candidate_rows[0], field) == "Revised presentation"


def test_replace_design_row_rejects_a_str_backed_enum_field() -> None:
    """``DecisionStatus`` is a ``str, enum.Enum`` — ``isinstance(..., str)``
    alone would accept it, bypassing the closed-vocabulary check the enum
    exists to enforce."""
    artifact = parse_domain_artifact(DOMAIN_TEXT)
    decision_id = artifact.decisions[0].id

    with pytest.raises(ValueError, match="no replaceable text field"):
        replace_design_row(
            artifact,
            collection="decisions",
            row_id=decision_id,
            field="status",
            value="not-a-real-status",
        )


def test_replace_design_row_refuses_status_even_when_the_value_is_a_real_member() -> None:
    """``settle_pending_decision`` is the only status-changing route in this
    leaf — a syntactically valid member value must not slip through
    ``replace_design_row`` just because it names a real ``DecisionStatus``."""
    artifact = parse_domain_artifact(DOMAIN_TEXT)
    decision_id = artifact.decisions[0].id

    with pytest.raises(ValueError, match="no replaceable text field"):
        replace_design_row(
            artifact,
            collection="decisions",
            row_id=decision_id,
            field="status",
            value="settled",
        )


# --------------------------------------------------------------------------
# Decision settlement
# --------------------------------------------------------------------------


def test_settle_pending_decision_changes_only_the_selected_rows_status() -> None:
    frontmatter = _reviewed_domain_frontmatter()
    frontmatter["decisions"] = [
        *frontmatter["decisions"],
        dict(
            frontmatter["decisions"][0],
            id="decision-2",
            chosen_option="Keep customer as its own aggregate.",
            status="settled",
        ),
    ]
    artifact = parse_domain_artifact(_domain_text(frontmatter))

    settled = settle_pending_decision(artifact, decision_id="decision-1")

    original = artifact.decisions[0]
    updated = settled.decisions[0]
    assert settled is not artifact
    assert updated.status is DecisionStatus.SETTLED
    assert updated.id == original.id
    assert updated.chosen_option == original.chosen_option
    assert updated.rejected_alternatives == original.rejected_alternatives
    assert updated.rationale == original.rationale
    assert updated.anchor == original.anchor
    assert updated.source == original.source
    assert settled.decisions[1] is artifact.decisions[1]
    assert settled.entities is artifact.entities
    assert settled.business_rules is artifact.business_rules
    assert settled.workflows is artifact.workflows
    assert settled.feedback is artifact.feedback
    assert settled.removals is artifact.removals
    assert settled.body == artifact.body


@pytest.mark.parametrize(
    ("parser", "render", "text", "decision_id"),
    (
        (parse_domain_artifact, render_domain_artifact, DOMAIN_TEXT, "decision-1"),
        (
            parse_constraints_artifact,
            render_constraints_artifact,
            _constraints_text_with_pending_decision(),
            "decision-2",
        ),
        (
            parse_components_artifact,
            render_components_artifact,
            COMPONENTS_TEXT,
            "decision-3",
        ),
        (parse_plans_artifact, render_plans_artifact, PLANS_TEXT, "decision-4"),
    ),
)
def test_settle_pending_decision_changes_exactly_one_rendered_line(
    parser, render, text: str, decision_id: str
) -> None:
    """The field-preservation contract later steps build on: settling a
    decision changes exactly the one rendered ``status`` line."""
    artifact = parser(text)
    before_lines = render(artifact).splitlines()

    settled = settle_pending_decision(artifact, decision_id=decision_id)
    after_text = render(settled)
    after_lines = after_text.splitlines()

    assert len(before_lines) == len(after_lines)
    differing = [
        (before, after)
        for before, after in zip(before_lines, after_lines)
        if before != after
    ]
    assert len(differing) == 1
    before_line, after_line = differing[0]
    assert before_line.strip() == "status: pending"
    assert after_line.strip() == "status: settled"
    assert parser(after_text) == settled


def test_settle_refuses_an_unknown_decision_id() -> None:
    artifact = parse_domain_artifact(DOMAIN_TEXT)

    with pytest.raises(ValueError, match=r"decision 'no-such-decision'.*found 0"):
        settle_pending_decision(artifact, decision_id="no-such-decision")


def test_settle_refuses_a_duplicated_decision_id_rather_than_settling_the_first() -> None:
    frontmatter = _domain_frontmatter()
    frontmatter["decisions"] = [
        *frontmatter["decisions"],
        dict(frontmatter["decisions"][0]),
    ]
    artifact = parse_domain_artifact(_domain_text(frontmatter))

    with pytest.raises(ValueError, match="found 2"):
        settle_pending_decision(artifact, decision_id="decision-1")


@pytest.mark.parametrize("status", ["settled", "pending"])
def test_settle_refuses_an_inherited_decision_before_checking_its_status(
    status: str,
) -> None:
    """An inherited row is normally settled; checking status before source
    would misreport a rejected inherited-pending row as "already settled"
    instead of naming the real reason."""
    frontmatter = _domain_frontmatter()
    frontmatter["decisions"] = [
        *frontmatter["decisions"],
        dict(
            frontmatter["decisions"][0],
            id="decision-inherited",
            source="answer-cart-ownership",
            status=status,
        ),
    ]
    artifact = parse_domain_artifact(_domain_text(frontmatter))

    with pytest.raises(ValueError, match="inherited") as excinfo:
        settle_pending_decision(artifact, decision_id="decision-inherited")

    assert "pending" not in str(excinfo.value)


def test_settle_refuses_an_already_settled_decision_rather_than_returning_it_unchanged() -> (
    None
):
    artifact = parse_constraints_artifact(CONSTRAINTS_TEXT)  # decision-2 is settled

    with pytest.raises(ValueError, match="not pending"):
        settle_pending_decision(artifact, decision_id="decision-2")


def test_settle_never_touches_feedback_targeting_the_decision() -> None:
    frontmatter = _domain_frontmatter()
    frontmatter["feedback"] = [
        _feedback_row(
            target={"kind": "row", "row_id": "decision-1"},
            state="awaiting-review",
            proposed_response="Keep the cart inside the order aggregate.",
        )
    ]
    artifact = parse_domain_artifact(_domain_text(frontmatter))

    settled = settle_pending_decision(artifact, decision_id="decision-1")

    assert settled.feedback is artifact.feedback
    assert settled.feedback[0].state is FeedbackState.AWAITING_REVIEW


def test_stage_artifact_mutations_replace_or_remove_only_the_named_tuple_entry() -> None:
    artifact = parse_domain_artifact(_domain_text(_reviewed_domain_frontmatter()))
    replacement = EntityRow(
        id="entity-1",
        name="Customer order",
        fields=artifact.entities[0].fields,
    )

    replaced = replace_stage_row(
        artifact,
        collection="entities",
        row_id="entity-1",
        row=replacement,
    )
    candidate = remove_stage_row(replaced, collection="entities", row_id="entity-2")

    assert candidate.entities == (replacement,)
    assert replaced.entities[1] is artifact.entities[1]
    assert candidate.business_rules is artifact.business_rules
    assert candidate.feedback is artifact.feedback
    assert candidate.removals is artifact.removals
    assert candidate.body == artifact.body


def test_stage_artifact_mutations_append_only_matching_plan_ordering_and_removal() -> None:
    artifact = parse_plans_artifact(PLANS_TEXT)
    plan = PlanRow(
        id="plan-added",
        title="Add the bounded route",
        disposition=PlanDisposition.KEEP,
        component_ids=(artifact.plans[0].component_ids[0],),
        draft_seed_path="seeds/plan-added.md",
        sizing_rationale="One focused delivery slice.",
    )
    ordering = OrderingEntry(plan_id=plan.id, depends_on=(artifact.plans[0].id,))

    candidate = append_stage_row(artifact, collection="plans", row=plan)
    candidate = append_plan_ordering_entry(candidate, ordering)
    candidate = append_removal_record(
        candidate, RemovalRecord("removed-row", "The reviewer retired it.", ("feedback-1",))
    )
    without_added_ordering = remove_plan_ordering_entry(candidate, plan_id=plan.id)

    assert candidate.plans[:-1] == artifact.plans
    assert candidate.plans[-1] is plan
    assert candidate.ordering[:-1] == artifact.ordering
    assert candidate.ordering[-1] is ordering
    assert candidate.removals[-1].removed_id == "removed-row"
    assert without_added_ordering.ordering == artifact.ordering


def test_stage_artifact_mutations_keep_hosting_and_stores_out_of_design_row_collections() -> None:
    constraints = parse_constraints_artifact(CONSTRAINTS_TEXT)
    components = parse_components_artifact(COMPONENTS_TEXT)

    assert "hosting" in stage_row_collections(constraints)
    assert "hosting" not in design_row_collections(constraints)
    assert "hosting" not in impact_node_collections(constraints)
    assert stage_collection_participates_in_impact("hosting") is False
    assert tuple(impact_node_collections(constraints)) == tuple(
        collection
        for collection in stage_row_collections(constraints)
        if stage_collection_participates_in_impact(collection)
    )
    assert "stores" in stage_row_collections(components)
    assert "stores" not in design_row_collections(components)
    assert "stores" in impact_node_collections(components)
    assert stage_collection_participates_in_impact("stores") is True

    with pytest.raises(ValueError, match="never added"):
        append_stage_row(
            constraints,
            collection="hosting",
            row=HostingRow("hosting-extra", "compute", "per-request"),
        )
    with pytest.raises(ValueError, match="never removed"):
        remove_stage_row(constraints, collection="hosting", row_id="hosting-compute")

    policy = stage_row_operation_policy("hosting")
    assert policy.allow_add is False
    assert policy.allow_remove is False
    assert policy.immutable_fields == ("facet",)
    hosting = HostingRow("hosting-compute", "compute", "per-request")
    assert stage_row_edit_preserves_fixed_fields(
        hosting,
        HostingRow("hosting-compute", "compute", "managed"),
        row_type="hosting",
    )
    assert not stage_row_edit_preserves_fixed_fields(
        hosting,
        HostingRow("hosting-compute", "runtime", "managed"),
        row_type="hosting",
    )


def test_feedback_target_kind_members() -> None:
    assert [member.value for member in FeedbackTargetKind] == ["artifact", "row"]


def test_conforming_feedback_and_removals_parse_into_typed_rows() -> None:
    artifact = parse_domain_artifact(_domain_text(_reviewed_domain_frontmatter()))

    assert artifact.feedback[0] == FeedbackRow(
        id="feedback-1",
        target=FeedbackTarget(kind=FeedbackTargetKind.ROW, row_id="entity-1"),
        request="Split the cart out of the order entity.",
        state=FeedbackState.OPEN,
    )
    assert artifact.feedback[1].target == FeedbackTarget(kind=FeedbackTargetKind.ARTIFACT)
    assert artifact.feedback[1].state is FeedbackState.AWAITING_REVIEW
    assert artifact.feedback[1].proposed_response.startswith("Added workflow-2")
    assert artifact.removals == (
        RemovalRecord(
            removed_id="workflow-1",
            rationale="The cart split moved this path onto the cart entity.",
            feedback_ids=("feedback-1",),
        ),
    )


def test_unknown_feedback_state_raises_naming_the_value() -> None:
    with pytest.raises(RoadmapArtifactError) as exc:
        parse_domain_artifact(_domain_with_feedback(_feedback_row(state="closed")))

    message = str(exc.value)
    assert "closed" in message
    assert "feedback-1" in message
    assert all(member.value in message for member in FeedbackState)


def test_unknown_target_kind_raises_naming_the_value() -> None:
    with pytest.raises(RoadmapArtifactError) as exc:
        parse_domain_artifact(_domain_with_feedback(_feedback_row(target={"kind": "step"})))

    message = str(exc.value)
    assert "step" in message
    assert "feedback-1" in message
    assert all(member.value in message for member in FeedbackTargetKind)


def test_row_target_without_a_row_id_raises() -> None:
    with pytest.raises(RoadmapArtifactError) as exc:
        parse_domain_artifact(_domain_with_feedback(_feedback_row(target={"kind": "row"})))

    message = str(exc.value)
    assert "feedback-1" in message
    assert "'row_id'" in message


def test_artifact_target_with_a_row_id_raises() -> None:
    """A tag disagreeing with its payload has no defensible reading, so there
    is nothing for a gate to report against."""
    with pytest.raises(RoadmapArtifactError) as exc:
        parse_domain_artifact(
            _domain_with_feedback(_feedback_row(target={"kind": "artifact", "row_id": "entity-1"}))
        )

    message = str(exc.value)
    assert "feedback-1" in message
    assert "'row_id'" in message


@pytest.mark.parametrize("row_id", ["", "   ", 7])
def test_blank_target_row_id_raises(row_id) -> None:
    """``row_id`` is identifier-like, not prose."""
    with pytest.raises(RoadmapArtifactError) as exc:
        parse_domain_artifact(
            _domain_with_feedback(_feedback_row(target={"kind": "row", "row_id": row_id}))
        )

    assert "non-empty string 'row_id'" in str(exc.value)


def test_target_that_is_not_a_mapping_raises() -> None:
    with pytest.raises(RoadmapArtifactError) as exc:
        parse_domain_artifact(_domain_with_feedback(_feedback_row(target="entity-1")))

    message = str(exc.value)
    assert "feedback-1" in message
    assert "must be a mapping, got str" in message


def test_awaiting_review_without_a_response_raises() -> None:
    """The state is *defined* by carrying a response."""
    with pytest.raises(RoadmapArtifactError) as exc:
        parse_domain_artifact(_domain_with_feedback(_feedback_row(state="awaiting-review")))

    message = str(exc.value)
    assert "feedback-1" in message
    assert "proposed_response" in message


@pytest.mark.parametrize("response", ["", "   ", None])
def test_awaiting_review_with_a_blank_response_raises(response) -> None:
    with pytest.raises(RoadmapArtifactError) as exc:
        parse_domain_artifact(
            _domain_with_feedback(
                _feedback_row(state="awaiting-review", proposed_response=response)
            )
        )

    assert "proposed_response" in str(exc.value)


@pytest.mark.parametrize("key", ["id", "request", "state", "target"])
def test_feedback_missing_a_required_key_raises(key: str) -> None:
    row = _feedback_row()
    del row[key]

    with pytest.raises(RoadmapArtifactError) as exc:
        parse_domain_artifact(_domain_with_feedback(row))

    assert f"'{key}'" in str(exc.value)


def test_feedback_reopen_record_parses_and_round_trips() -> None:
    artifact = parse_domain_artifact(
        _domain_with_feedback(_feedback_row(feedback_reopen=_feedback_reopen_record()))
    )

    record = artifact.feedback[0].feedback_reopen
    assert record == FeedbackReopenRecord(
        selector={"artifact_key": "domain", "feedback_id": "feedback-1"},
        reason="operator-confirmed-evidence-unavailable",
        nonce="A" * 43,
        recorded_at="2026-08-27T14:15:16.123456Z",
    )
    assert parse_domain_artifact(render_domain_artifact(artifact)) == artifact


def test_feedback_reopen_record_copies_its_selector_and_remains_hashable() -> None:
    selector = {"artifact_key": "domain", "feedback_id": "feedback-1"}
    record = FeedbackReopenRecord(
        selector=selector,
        reason="operator-confirmed-evidence-unavailable",
        nonce="A" * 43,
        recorded_at="2026-08-27T14:15:16.123456Z",
    )
    same_record = FeedbackReopenRecord(
        selector=dict(selector),
        reason=record.reason,
        nonce=record.nonce,
        recorded_at=record.recorded_at,
    )
    selector["artifact_key"] = "constraints"

    assert dict(record.selector) == {"artifact_key": "domain", "feedback_id": "feedback-1"}
    assert hash(record) == hash(same_record)
    assert isinstance(
        hash(
            FeedbackRow(
                "feedback-1",
                FeedbackTarget(FeedbackTargetKind.ARTIFACT),
                "Reopen this review.",
                FeedbackState.OPEN,
                feedback_reopen=record,
            )
        ),
        int,
    )
    with pytest.raises(TypeError):
        record.selector["artifact_key"] = "components"  # type: ignore[index]


@pytest.mark.parametrize(
    ("field", "value", "expected_field"),
    [
        ("selector", None, "selector"),
        ("selector", "", "selector"),
        ("selector", {"artifact_key": "", "feedback_id": "feedback-1"}, "selector.artifact_key"),
        ("reason", "", "reason"),
        ("reason", 7, "reason"),
        ("nonce", "", "nonce"),
        ("nonce", "A" * 42, "nonce"),
        ("nonce", 7, "nonce"),
        ("recorded_at", "", "recorded_at"),
        ("recorded_at", "2026-08-27T14:15:16Z", "recorded_at"),
        ("recorded_at", 7, "recorded_at"),
        ("recorded_at", "2026-02-30T14:15:16.123456Z", "recorded_at"),
    ],
)
def test_feedback_reopen_record_requires_complete_redacted_shape(
    field: str, value: object, expected_field: str
) -> None:
    record = _feedback_reopen_record(**{field: value})

    with pytest.raises(RoadmapArtifactError) as exc:
        parse_domain_artifact(_domain_with_feedback(_feedback_row(feedback_reopen=record)))

    message = str(exc.value)
    assert "feedback-1" in message
    assert expected_field in message


@pytest.mark.parametrize("field", ("selector", "reason", "nonce", "recorded_at"))
def test_feedback_reopen_record_rejects_missing_required_fields(field: str) -> None:
    record = _feedback_reopen_record()
    del record[field]

    with pytest.raises(RoadmapArtifactError) as exc:
        parse_domain_artifact(_domain_with_feedback(_feedback_row(feedback_reopen=record)))

    assert field in str(exc.value)


@pytest.mark.parametrize(
    "field", ("response", "proposed_response", "digest", "evidence", "path", "attestation")
)
def test_feedback_reopen_record_rejects_response_evidence_and_freeform_fields(
    field: str,
) -> None:
    record = _feedback_reopen_record(**{field: "retained metadata is forbidden"})

    with pytest.raises(RoadmapArtifactError) as exc:
        parse_domain_artifact(_domain_with_feedback(_feedback_row(feedback_reopen=record)))

    message = str(exc.value)
    assert "feedback-1" in message
    assert field in message


def test_feedback_reopen_record_rejects_extra_selector_fields() -> None:
    record = _feedback_reopen_record(
        selector={
            "artifact_key": "domain",
            "feedback_id": "feedback-1",
            "evidence": "not retained",
        }
    )

    with pytest.raises(RoadmapArtifactError) as exc:
        parse_domain_artifact(_domain_with_feedback(_feedback_row(feedback_reopen=record)))

    assert "selector" in str(exc.value)
    assert "evidence" in str(exc.value)


def test_non_list_feedback_collection_raises() -> None:
    frontmatter = _domain_frontmatter()
    frontmatter["feedback"] = "split the cart out"

    with pytest.raises(RoadmapArtifactError) as exc:
        parse_domain_artifact(_domain_text(frontmatter))

    assert "'feedback' must be a list of rows" in str(exc.value)


@pytest.mark.parametrize("key", ["removed_id", "rationale", "feedback_ids"])
def test_removal_missing_a_required_key_raises(key: str) -> None:
    record = _removal_record()
    del record[key]

    with pytest.raises(RoadmapArtifactError) as exc:
        parse_domain_artifact(_domain_with_removal(record))

    assert f"'{key}'" in str(exc.value)


@pytest.mark.parametrize("feedback_ids", [[""], ["   "], [7]])
def test_removal_feedback_ids_must_hold_non_empty_strings(feedback_ids) -> None:
    with pytest.raises(RoadmapArtifactError) as exc:
        parse_domain_artifact(_domain_with_removal(_removal_record(feedback_ids=feedback_ids)))

    message = str(exc.value)
    assert "workflow-1" in message
    assert "non-empty id strings" in message


# Deliberate non-checks: each is a *relation*, and the gates own it. Parsing
# has to succeed or the gate has nothing to report against.


def test_row_target_naming_an_undefined_id_parses() -> None:
    artifact = parse_domain_artifact(
        _domain_with_feedback(_feedback_row(target={"kind": "row", "row_id": "entity-999"}))
    )

    assert artifact.feedback[0].target.row_id == "entity-999"


def test_open_feedback_may_carry_a_stale_response() -> None:
    """Reopening keeps the prior response readable beside the request."""
    artifact = parse_domain_artifact(
        _domain_with_feedback(_feedback_row(state="open", proposed_response="Added a Cart entity."))
    )

    assert artifact.feedback[0].state is FeedbackState.OPEN
    assert artifact.feedback[0].proposed_response == "Added a Cart entity."


def test_deferred_feedback_may_carry_a_response() -> None:
    artifact = parse_domain_artifact(
        _domain_with_feedback(
            _feedback_row(state="deferred", proposed_response="Added a Cart entity.")
        )
    )

    assert artifact.feedback[0].state is FeedbackState.DEFERRED
    assert artifact.feedback[0].proposed_response == "Added a Cart entity."


def test_duplicate_feedback_ids_survive_as_separate_rows() -> None:
    """The duplicate gate needs both rows, so feedback is an ordered tuple."""
    artifact = parse_domain_artifact(
        _domain_with_feedback(
            _feedback_row(),
            _feedback_row(request="And name the cart's owner."),
        )
    )

    assert [row.id for row in artifact.feedback] == ["feedback-1", "feedback-1"]
    assert artifact.feedback[1].request == "And name the cart's owner."


def test_blank_request_and_blank_rationale_parse() -> None:
    """Prose emptiness stays a gate's judgment — see ``_text_at``."""
    frontmatter = _domain_frontmatter()
    frontmatter["feedback"] = [_feedback_row(request="")]
    frontmatter["removals"] = [_removal_record(rationale="")]

    artifact = parse_domain_artifact(_domain_text(frontmatter))

    assert artifact.feedback[0].request == ""
    assert artifact.removals[0].rationale == ""


def test_removal_citing_no_feedback_parses() -> None:
    """ "Cites at least one" is the continuity gate's finding."""
    artifact = parse_domain_artifact(_domain_with_removal(_removal_record(feedback_ids=[])))

    assert artifact.removals[0].feedback_ids == ()


def test_removal_naming_a_row_the_artifact_still_declares_parses() -> None:
    artifact = parse_domain_artifact(_domain_with_removal(_removal_record(removed_id="entity-1")))

    assert artifact.removals[0].removed_id == "entity-1"
    assert [row.id for row in artifact.entities] == ["entity-1", "entity-2"]


# Rendering and round-trip.


def test_domain_feedback_and_removals_round_trip() -> None:
    artifact = parse_domain_artifact(_domain_text(_reviewed_domain_frontmatter()))
    assert parse_domain_artifact(render_domain_artifact(artifact)) == artifact


def test_constraints_feedback_and_removals_round_trip() -> None:
    artifact = parse_constraints_artifact(_constraints_text(_reviewed_constraints_frontmatter()))
    assert parse_constraints_artifact(render_constraints_artifact(artifact)) == artifact


def test_absent_review_collections_render_no_new_key() -> None:
    """An unreviewed artifact renders exactly its design keys.

    Judged against the *parsed* frontmatter rather than the raw text: the
    no-review key below shows a commented ``feedback:`` stub, so a substring
    check would read the reviewer's guidance as a collection. Stricter than
    the substring form it replaces — it pins the whole key tuple and its
    order, not the absence of two words.
    """
    domain = parse_domain_artifact(DOMAIN_TEXT)
    constraints = parse_constraints_artifact(CONSTRAINTS_TEXT)

    assert domain.feedback == () and domain.removals == ()
    assert constraints.feedback == () and constraints.removals == ()
    for rendered, design_keys in (
        (render_domain_artifact(domain), DOMAIN_ROW_KEYS),
        (render_constraints_artifact(constraints), CONSTRAINTS_ROW_KEYS),
    ):
        assert tuple(yaml.safe_load(rendered.split("---\n")[1])) == design_keys


def test_an_unreviewed_artifact_renders_the_how_to_start_key() -> None:
    """``_FEEDBACK_KEY_COMMENT`` is anchored to a ``feedback:`` line, so it
    cannot reach the one reviewer who most needs it: the one with no feedback
    row yet. Both artifacts carry the other half."""
    for rendered in (
        render_domain_artifact(parse_domain_artifact(DOMAIN_TEXT)),
        render_constraints_artifact(parse_constraints_artifact(CONSTRAINTS_TEXT)),
    ):
        assert "# No review on this artifact yet." in rendered
        assert "# feedback:" in rendered


def test_the_two_reviewer_keys_never_render_together() -> None:
    reviewed = render_domain_artifact(
        parse_domain_artifact(_domain_text(_reviewed_domain_frontmatter()))
    )
    unreviewed = render_domain_artifact(parse_domain_artifact(DOMAIN_TEXT))
    started, answered = "# No review on this artifact yet.", "# Your review."

    assert started in unreviewed and answered not in unreviewed
    assert answered in reviewed and started not in reviewed


def test_rendered_feedback_comments_state_stage_limits_and_split_action() -> None:
    reviewed = render_domain_artifact(
        parse_domain_artifact(_domain_text(_reviewed_domain_frontmatter()))
    )
    unreviewed = render_domain_artifact(parse_domain_artifact(DOMAIN_TEXT))

    for rendered in (reviewed, unreviewed):
        assert f"{HARD_MAX_ACTIVE_FEEDBACK_ITEMS} open items" in rendered
        assert f"{HARD_MAX_RESPONSE_BYTES // 1024} KiB total" in rendered
        assert f"{HARD_MAX_PROSE_AMENDMENT_BYTES // 1024} KiB per" in rendered
        assert "one material change per item" in rendered
        assert "Split larger feedback" in rendered
        assert "stricter numeric caps" in rendered


def test_the_how_to_start_key_uncomments_into_a_row_that_travels() -> None:
    """A reviewer who follows the key literally gets a row the next run sends.

    This is the claim the key makes, so it is the one worth pinning: a schema
    change that leaves the stub behind reddens here rather than in a
    reviewer's editor, where the only symptom is a parse error on their own
    file.
    """
    rendered = render_domain_artifact(parse_domain_artifact(DOMAIN_TEXT))
    lines = rendered.splitlines()
    start = lines.index("# feedback:")
    end = lines.index("---", start)

    uncommented = "\n".join(
        re.sub(r"^# ?", "", line) if start <= i < end else line for i, line in enumerate(lines)
    )
    filled = (
        uncommented.replace("<the id this request is about>", "entity-1").replace(
            "<what you want changed, in your own words>", "Call it an Order."
        )
        + "\n"
    )

    (row,) = parse_domain_artifact(filled).feedback
    assert row.id == "fb-1"
    assert row.target.kind is FeedbackTargetKind.ROW
    assert row.target.row_id == "entity-1"
    assert row.request == "Call it an Order."
    # The only state that reaches the model, which is what the key promises.
    assert row.state is FeedbackState.OPEN


def test_review_keys_render_after_the_design_keys() -> None:
    artifact = parse_domain_artifact(_domain_text(_reviewed_domain_frontmatter()))

    rendered = yaml.safe_load(render_domain_artifact(artifact).split("---\n")[1])

    assert tuple(rendered) == DOMAIN_ROW_KEYS + REVIEW_ROW_KEYS


def test_artifact_target_renders_without_a_row_id_key() -> None:
    artifact = parse_domain_artifact(_domain_text(_reviewed_domain_frontmatter()))

    assert "row_id: null" not in render_domain_artifact(artifact)


def test_absent_proposed_response_renders_no_key() -> None:
    artifact = parse_domain_artifact(_domain_with_feedback(_feedback_row()))

    # The *key*, not the substring: the reviewer key rendered above `feedback:`
    # names the field in prose, and a row omitting it is what this pins.
    rendered = render_domain_artifact(artifact)
    assert not [
        line for line in rendered.splitlines() if line.strip().startswith("proposed_response:")
    ], rendered


def test_feedback_without_feedback_reopen_remains_legacy_compatible() -> None:
    artifact = parse_domain_artifact(_domain_with_feedback(_feedback_row()))

    assert artifact.feedback[0].feedback_reopen is None
    assert yaml.safe_load(render_domain_artifact(artifact).split("---\n")[1])["feedback"] == [
        _feedback_row()
    ]


def test_feedback_reopen_record_is_omitted_when_absent() -> None:
    rendered = render_domain_artifact(
        parse_domain_artifact(_domain_with_feedback(_feedback_row()))
    )
    frontmatter = yaml.safe_load(rendered.split("---\n")[1])

    assert "feedback_reopen" not in frontmatter["feedback"][0]


def test_rendered_feedback_guidance_names_only_the_confirmed_reopen_exception() -> None:
    legacy = render_domain_artifact(parse_domain_artifact(_domain_with_feedback(_feedback_row())))
    reopened = render_domain_artifact(
        parse_domain_artifact(
            _domain_with_feedback(_feedback_row(feedback_reopen=_feedback_reopen_record()))
        )
    )

    assert "# Only you move a row out of `awaiting-review`." in legacy
    assert "--reopen-feedback" not in legacy
    assert "Ordinary close, defer, and reopen actions" in reopened
    assert "explicitly confirmed operator `--reopen-feedback` action" in reopened
    assert "a stage reply never reopens a row" in reopened


def test_legacy_feedback_guidance_retains_its_exact_bytes() -> None:
    legacy = render_domain_artifact(
        parse_domain_artifact(_domain_with_feedback(_feedback_row()))
    )
    unreviewed = render_domain_artifact(parse_domain_artifact(DOMAIN_TEXT))
    expected = f"""\
# Your review. Set `state` on a row to one of:
#   open             send this request back to the model on the next run
#   awaiting-review  the model has answered — read its `proposed_response`
#   deferred         park it: kept in this file, no longer sent
# Close a row by deleting it; git keeps the record. If a response asks you a
# question, edit that row's `request` to answer it, then set `state: open`.
# Only you move a row out of `awaiting-review`.
# A stage reply handles at most {HARD_MAX_ACTIVE_FEEDBACK_ITEMS} open items, {HARD_MAX_RESPONSE_BYTES // 1024} KiB total, and {HARD_MAX_PROSE_AMENDMENT_BYTES // 1024} KiB per
# row-prose amendment, with one material change per item. Split larger feedback;
# this project may set stricter numeric caps.
feedback:"""

    assert expected in legacy
    assert f"""\
# No review on this artifact yet. To ask for a change, say it here rather than
# making a direct edit to the rows: uncomment the lines from `feedback:` down, fill
# them in, and re-run this artifact's own stage with --from-stage. The model
# answers in `proposed_response`, leaves your `request` untouched, and never
# writes one of these rows itself.
# A stage reply handles at most {HARD_MAX_ACTIVE_FEEDBACK_ITEMS} open items, {HARD_MAX_RESPONSE_BYTES // 1024} KiB total, and {HARD_MAX_PROSE_AMENDMENT_BYTES // 1024} KiB per
# row-prose amendment, with one material change per item. Split larger feedback;
# this project may set stricter numeric caps.
# feedback:
# - id: fb-1
#   target:
#     kind: row              # or `artifact` for the whole file, and no row_id
#     row_id: <the id this request is about>
#   request: >-
#     <what you want changed, in your own words>
#   state: open              # the only state that is sent to the model
""" in unreviewed


def test_rendered_feedback_enum_values_are_plain_strings() -> None:
    rendered = render_domain_artifact(
        parse_domain_artifact(_domain_text(_reviewed_domain_frontmatter()))
    )

    assert "state: open" in rendered
    assert "kind: row" in rendered
    assert "FeedbackState" not in rendered
    assert "FeedbackTargetKind" not in rendered
    assert "!!python" not in rendered


def test_a_multi_line_request_round_trips_by_value() -> None:
    """``safe_dump`` re-styles a literal block as a quoted continuation; the
    *value* is what survives, and that is what a later immutability check
    compares."""
    request = "Split the cart out.\n\nIt owns its own lifecycle.\n"
    artifact = parse_domain_artifact(_domain_with_feedback(_feedback_row(request=request)))

    assert artifact.feedback[0].request == request
    assert parse_domain_artifact(render_domain_artifact(artifact)) == artifact


def test_review_row_keys_match_the_rendered_frontmatter() -> None:
    """The constant is the wire truth, not a hand-copied list."""
    domain = yaml.safe_load(
        render_domain_artifact(
            parse_domain_artifact(_domain_text(_reviewed_domain_frontmatter()))
        ).split("---\n")[1]
    )
    assert tuple(k for k in domain if k not in DOMAIN_ROW_KEYS) == REVIEW_ROW_KEYS

    constraints = yaml.safe_load(
        render_constraints_artifact(
            parse_constraints_artifact(_constraints_text(_reviewed_constraints_frontmatter()))
        ).split("---\n")[1]
    )
    assert tuple(k for k in constraints if k not in CONSTRAINTS_ROW_KEYS) == REVIEW_ROW_KEYS


def test_design_row_key_constants_exclude_the_review_keys() -> None:
    """The design tuples are pinned against the stage prompts, which never ask
    a model to author a reviewer's feedback."""
    for key in REVIEW_ROW_KEYS:
        assert key not in DOMAIN_ROW_KEYS
        assert key not in CONSTRAINTS_ROW_KEYS
        assert key not in COMPONENTS_ROW_KEYS


# --------------------------------------------------------------------------
# Components artifact
# --------------------------------------------------------------------------


def test_components_row_key_constants_match_the_rendered_frontmatter() -> None:
    components = yaml.safe_load(
        render_components_artifact(parse_components_artifact(COMPONENTS_TEXT)).split("---\n")[1]
    )
    assert tuple(components) == COMPONENTS_ROW_KEYS
    for key in REVIEW_ROW_KEYS:
        assert key not in COMPONENTS_ROW_KEYS


def test_components_design_rows_exclude_stores() -> None:
    artifact = parse_components_artifact(COMPONENTS_TEXT)

    assert components_design_rows(artifact) == (
        ("system pattern", "system-pattern-event-sourcing"),
        ("component pattern", "pattern-cqrs"),
        ("component", "component-order"),
        ("decision", "decision-3"),
    )


def test_conforming_components_body_parses_every_row_kind() -> None:
    artifact = parse_components_artifact(COMPONENTS_TEXT)

    assert artifact.system_patterns[0] == PatternRow(
        id="system-pattern-event-sourcing",
        name="Event sourcing",
        statement="Domain events are the system of record for state changes.",
    )
    assert artifact.component_patterns[0].id == "pattern-cqrs"
    assert artifact.stores == (
        StoreRow(
            id="store-orders",
            category="relational",
            sharing="component-owned",
            product="PostgreSQL",
        ),
    )
    assert artifact.components[0] == ComponentRow(
        id="component-order",
        name="Order slice",
        entity_ids=("entity-1", "entity-2"),
        pattern_ids=("pattern-cqrs", "system-pattern-event-sourcing"),
        constraint_ids=("constraint-1",),
        store_ids=("store-orders",),
    )
    assert artifact.decisions[0].id == "decision-3"
    assert artifact.decisions[0].status is DecisionStatus.PENDING


def test_missing_opening_fence_raises_on_components() -> None:
    with pytest.raises(RoadmapArtifactError) as exc:
        parse_components_artifact("# Components\n\nNo frontmatter here.\n")
    assert "line 1" in str(exc.value)


def test_malformed_yaml_raises_and_names_the_path_for_components(
    tmp_path: Path,
) -> None:
    path = tmp_path / COMPONENTS_FILENAME
    path.write_text("---\ncomponents: [unclosed\n---\n# Components\n", encoding="utf-8")

    with pytest.raises(RoadmapArtifactError) as exc:
        load_components_artifact(path)
    assert exc.value.path == path
    assert str(path) in str(exc.value)


def test_missing_required_component_row_key_raises_naming_the_row() -> None:
    frontmatter = _components_frontmatter()
    del frontmatter["components"][0]["entity_ids"]
    with pytest.raises(RoadmapArtifactError) as exc:
        parse_components_artifact(_components_text(frontmatter))
    message = str(exc.value)
    assert "component-order" in message
    assert "entity_ids" in message


def test_wrong_type_for_a_components_row_collection_raises() -> None:
    frontmatter = _components_frontmatter()
    frontmatter["components"] = "component-order"
    with pytest.raises(RoadmapArtifactError) as exc:
        parse_components_artifact(_components_text(frontmatter))
    assert "'components' must be a list of rows" in str(exc.value)


def test_unknown_frontmatter_keys_are_ignored_on_components() -> None:
    frontmatter = _components_frontmatter()
    frontmatter["notes"] = "an operator's aside"
    frontmatter["components"][0]["owner"] = "platform"

    artifact = parse_components_artifact(_components_text(frontmatter))
    assert artifact.components[0].id == "component-order"
    assert "owner" not in render_components_artifact(artifact)


def test_duplicate_component_row_ids_survive_as_separate_rows() -> None:
    frontmatter = _components_frontmatter()
    frontmatter["components"].append(
        {
            "id": "component-order",
            "name": "Order slice (again)",
            "entity_ids": ["entity-1"],
            "pattern_ids": ["pattern-cqrs"],
        }
    )

    artifact = parse_components_artifact(_components_text(frontmatter))
    assert [row.id for row in artifact.components] == [
        "component-order",
        "component-order",
    ]


def test_entity_id_not_in_domain_still_parses() -> None:
    frontmatter = _components_frontmatter()
    frontmatter["components"][0]["entity_ids"] = ["entity-missing"]

    artifact = parse_components_artifact(_components_text(frontmatter))
    assert artifact.components[0].entity_ids == ("entity-missing",)


def test_pattern_id_not_in_artifact_still_parses() -> None:
    frontmatter = _components_frontmatter()
    frontmatter["components"][0]["pattern_ids"] = ["pattern-missing"]

    artifact = parse_components_artifact(_components_text(frontmatter))
    assert artifact.components[0].pattern_ids == ("pattern-missing",)


def test_constraint_id_not_in_constraints_still_parses() -> None:
    frontmatter = _components_frontmatter()
    frontmatter["components"][0]["constraint_ids"] = ["constraint-missing"]

    artifact = parse_components_artifact(_components_text(frontmatter))
    assert artifact.components[0].constraint_ids == ("constraint-missing",)


def test_store_id_not_in_store_definitions_still_parses() -> None:
    frontmatter = _components_frontmatter()
    frontmatter["components"][0]["store_ids"] = ["store-missing"]

    artifact = parse_components_artifact(_components_text(frontmatter))

    assert artifact.components[0].store_ids == ("store-missing",)


def test_missing_stores_collection_parses_as_empty() -> None:
    frontmatter = _components_frontmatter()
    del frontmatter["stores"]

    artifact = parse_components_artifact(_components_text(frontmatter))

    assert artifact.stores == ()


@pytest.mark.parametrize("store_ids", [None, []], ids=["omitted", "empty"])
def test_omitted_or_empty_component_store_ids_parse_as_empty(store_ids) -> None:
    frontmatter = _components_frontmatter()
    if store_ids is None:
        del frontmatter["components"][0]["store_ids"]
    else:
        frontmatter["components"][0]["store_ids"] = store_ids

    artifact = parse_components_artifact(_components_text(frontmatter))

    assert artifact.components[0].store_ids == ()


def test_required_and_optional_component_id_lists_have_distinct_presence_rules() -> None:
    required = _components_frontmatter()
    del required["components"][0]["entity_ids"]

    with pytest.raises(RoadmapArtifactError, match="missing required key 'entity_ids'"):
        parse_components_artifact(_components_text(required))

    optional = _components_frontmatter()
    del optional["components"][0]["constraint_ids"]

    artifact = parse_components_artifact(_components_text(optional))
    assert artifact.components[0].constraint_ids == ()


@pytest.mark.parametrize("field", ["id", "category", "sharing"])
def test_store_missing_required_field_raises_naming_the_row(field: str) -> None:
    frontmatter = _components_frontmatter()
    del frontmatter["stores"][0][field]

    with pytest.raises(RoadmapArtifactError) as exc:
        parse_components_artifact(_components_text(frontmatter))

    message = str(exc.value)
    if field == "id":
        assert "'stores' row 0" in message
    else:
        assert "store-orders" in message
    assert field in message


@pytest.mark.parametrize(
    ("field", "value"),
    [("category", "eventual"), ("sharing", "everywhere")],
)
def test_unknown_store_category_and_sharing_values_still_parse(field: str, value: str) -> None:
    frontmatter = _components_frontmatter()
    frontmatter["stores"][0][field] = value

    artifact = parse_components_artifact(_components_text(frontmatter))

    assert getattr(artifact.stores[0], field) == value


def test_store_product_renders_only_when_present() -> None:
    frontmatter = _components_frontmatter()
    del frontmatter["stores"][0]["product"]

    rendered = render_components_artifact(parse_components_artifact(_components_text(frontmatter)))

    parsed = yaml.safe_load(rendered.split("---\n")[1])
    assert "product" not in parsed["stores"][0]


def test_component_with_empty_entity_ids_still_parses() -> None:
    frontmatter = _components_frontmatter()
    frontmatter["components"][0]["entity_ids"] = []

    artifact = parse_components_artifact(_components_text(frontmatter))
    assert artifact.components[0].entity_ids == ()


def test_component_with_empty_pattern_ids_still_parses() -> None:
    frontmatter = _components_frontmatter()
    frontmatter["components"][0]["pattern_ids"] = []

    artifact = parse_components_artifact(_components_text(frontmatter))
    assert artifact.components[0].pattern_ids == ()


def test_feedback_targeting_an_undefined_component_id_parses() -> None:
    artifact = parse_components_artifact(
        _components_with_feedback(
            _feedback_row(target={"kind": "row", "row_id": "component-missing"})
        )
    )

    assert artifact.feedback[0].target.row_id == "component-missing"


def test_stores_and_store_ids_round_trip_in_rendered_key_order() -> None:
    artifact = parse_components_artifact(COMPONENTS_TEXT)
    rendered = render_components_artifact(artifact)

    assert tuple(yaml.safe_load(rendered.split("---\n")[1])) == COMPONENTS_ROW_KEYS
    assert parse_components_artifact(rendered) == artifact


def test_components_feedback_and_removals_round_trip() -> None:
    artifact = parse_components_artifact(_components_text(_reviewed_components_frontmatter()))
    assert parse_components_artifact(render_components_artifact(artifact)) == artifact


def test_absent_review_collections_render_no_new_key_on_components() -> None:
    artifact = parse_components_artifact(COMPONENTS_TEXT)

    assert artifact.feedback == () and artifact.removals == ()
    rendered = render_components_artifact(artifact)
    assert tuple(yaml.safe_load(rendered.split("---\n")[1])) == COMPONENTS_ROW_KEYS


def test_both_pattern_collections_render_even_when_empty() -> None:
    frontmatter = {
        "system_patterns": [],
        "component_patterns": [],
        "components": [],
        "decisions": [],
    }
    rendered = render_components_artifact(
        parse_components_artifact(_components_text(frontmatter, body="# Components\n"))
    )

    parsed = yaml.safe_load(rendered.split("---\n")[1])
    assert "system_patterns" in parsed
    assert "component_patterns" in parsed
    assert parsed["system_patterns"] == []
    assert parsed["component_patterns"] == []


# --------------------------------------------------------------------------
# Plans artifact
# --------------------------------------------------------------------------


def test_plan_disposition_members() -> None:
    assert [member.value for member in PlanDisposition] == [
        "keep",
        "merge",
        "split",
        "cross-cutting",
    ]


def test_plan_id_slug_re_matches_create_slug_re() -> None:
    assert PLAN_ID_SLUG_RE.pattern == SLUG_RE.pattern


def test_plans_path_and_draft_seeds_dir_under_roadmap_slug(tmp_path: Path) -> None:
    slug_dir = roadmap_dir(tmp_path, "checkout")
    assert plans_path(tmp_path, "checkout") == slug_dir / PLANS_FILENAME
    assert draft_seeds_dir(tmp_path, "checkout") == slug_dir / DRAFT_SEEDS_DIRNAME


def test_resolve_draft_seed_path_accepts_the_new_prefix(tmp_path: Path) -> None:
    assert (
        resolve_draft_seed_path(tmp_path, "checkout", f"{DRAFT_SEEDS_DIRNAME}/x.md")
        == roadmap_dir(tmp_path, "checkout") / DRAFT_SEEDS_DIRNAME / "x.md"
    )


def test_resolve_draft_seed_path_still_accepts_the_legacy_prefix(tmp_path: Path) -> None:
    assert resolve_draft_seed_path(tmp_path, "checkout", "seeds/x.md") == (
        roadmap_dir(tmp_path, "checkout") / "seeds" / "x.md"
    )


@pytest.mark.parametrize(
    "relative_path",
    ["", "   ", "/abs/seeds/x.md", "seeds/../escape.md", "plan-seeds/x.md", ".."],
)
def test_resolve_draft_seed_path_rejects_unsafe_relative_paths(
    tmp_path: Path, relative_path: str
) -> None:
    with pytest.raises(RoadmapArtifactError):
        resolve_draft_seed_path(tmp_path, "checkout", relative_path)


def test_plans_row_key_constants_match_rendered_frontmatter() -> None:
    plans = yaml.safe_load(
        render_plans_artifact(parse_plans_artifact(PLANS_TEXT)).split("---\n")[1]
    )
    assert tuple(plans) == PLANS_ROW_KEYS


def test_design_row_key_constants_exclude_review_keys_on_plans() -> None:
    for key in REVIEW_ROW_KEYS:
        assert key not in PLANS_ROW_KEYS


def test_plans_design_rows_lists_plan_assumption_and_decision_kinds() -> None:
    artifact = parse_plans_artifact(PLANS_TEXT)

    assert plans_design_rows(artifact) == (
        ("plan", "plan-order-core"),
        ("plan", "plan-auth"),
        ("assumption", "assumption-1"),
        ("decision", "decision-4"),
    )


def test_conforming_plans_body_parses_every_row_kind() -> None:
    artifact = parse_plans_artifact(PLANS_TEXT)

    assert artifact.plans[0] == PlanRow(
        id="plan-order-core",
        title="Order core",
        disposition=PlanDisposition.KEEP,
        component_ids=("component-order",),
        draft_seed_path="seeds/order-core.md",
        sizing_rationale="One component, one plan.",
        intent="Let checkout create the order before authentication is required.",
        non_goals=("Authentication plumbing shared across all slices.",),
    )
    assert artifact.plans[1].disposition is PlanDisposition.CROSS_CUTTING
    assert artifact.plans[1].component_ids == ()
    assert artifact.plans[1].intent == (
        "Provide shared authentication boundaries to every delivery slice."
    )
    assert artifact.plans[1].non_goals == ("Checkout-specific order creation behavior.",)

    assert artifact.ordering == (
        OrderingEntry(
            plan_id="plan-order-core",
            depends_on=(),
            assumption_targets=("plan-auth",),
        ),
        OrderingEntry(plan_id="plan-auth"),
    )
    assert artifact.assumptions[0].id == "assumption-1"
    assert artifact.assumptions[0].consuming_plan_ids == ("plan-order-core",)
    assert artifact.decisions[0].id == "decision-4"
    assert artifact.decisions[0].status is DecisionStatus.PENDING


def test_plans_artifact_round_trips_through_render_and_parse() -> None:
    artifact = parse_plans_artifact(PLANS_TEXT)
    assert parse_plans_artifact(render_plans_artifact(artifact)) == artifact


def test_plans_feedback_and_removals_round_trip() -> None:
    artifact = parse_plans_artifact(_plans_text(_reviewed_plans_frontmatter()))
    assert parse_plans_artifact(render_plans_artifact(artifact)) == artifact


def test_duplicate_plan_row_ids_survive_as_separate_rows() -> None:
    frontmatter = _plans_frontmatter()
    frontmatter["plans"].append(
        {
            "id": "plan-order-core",
            "title": "Order core (again)",
            "disposition": "merge",
            "component_ids": ["component-order"],
            "draft_seed_path": "seeds/order-core-again.md",
            "sizing_rationale": "",
        }
    )

    artifact = parse_plans_artifact(_plans_text(frontmatter))
    assert [row.id for row in artifact.plans] == [
        "plan-order-core",
        "plan-auth",
        "plan-order-core",
    ]


def test_unknown_plan_disposition_raises_naming_vocabulary() -> None:
    frontmatter = _plans_frontmatter()
    frontmatter["plans"][0]["disposition"] = "combine"
    with pytest.raises(RoadmapArtifactError) as exc:
        parse_plans_artifact(_plans_text(frontmatter))
    message = str(exc.value)
    assert "combine" in message
    assert "plan-order-core" in message
    assert all(member.value in message for member in PlanDisposition)


def test_missing_required_plan_row_key_raises_naming_row() -> None:
    frontmatter = _plans_frontmatter()
    del frontmatter["plans"][0]["draft_seed_path"]
    with pytest.raises(RoadmapArtifactError) as exc:
        parse_plans_artifact(_plans_text(frontmatter))
    message = str(exc.value)
    assert "plan-order-core" in message
    assert "draft_seed_path" in message


def test_legacy_plan_without_review_context_still_parses() -> None:
    frontmatter = _plans_frontmatter()
    del frontmatter["plans"][0]["intent"]
    del frontmatter["plans"][0]["non_goals"]

    artifact = parse_plans_artifact(_plans_text(frontmatter))

    assert artifact.plans[0].intent == ""
    assert artifact.plans[0].non_goals == ()
    rendered_frontmatter = yaml.safe_load(render_plans_artifact(artifact).split("---\n")[1])
    assert "intent" not in rendered_frontmatter["plans"][0]
    assert "non_goals" not in rendered_frontmatter["plans"][0]


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("intent", ["not prose"], "must be a string"),
        ("non_goals", "not a list", "must be a list of strings"),
        ("non_goals", [""], "must hold non-empty strings"),
    ],
)
def test_malformed_plan_review_context_raises_naming_field(
    field: str, value: object, expected: str
) -> None:
    frontmatter = _plans_frontmatter()
    frontmatter["plans"][0][field] = value

    with pytest.raises(RoadmapArtifactError) as exc:
        parse_plans_artifact(_plans_text(frontmatter))

    assert field in str(exc.value)
    assert expected in str(exc.value)


def test_component_id_not_in_components_still_parses() -> None:
    frontmatter = _plans_frontmatter()
    frontmatter["plans"][0]["component_ids"] = ["component-missing"]

    artifact = parse_plans_artifact(_plans_text(frontmatter))
    assert artifact.plans[0].component_ids == ("component-missing",)


def test_ordering_referencing_unknown_plan_id_still_parses() -> None:
    frontmatter = _plans_frontmatter()
    frontmatter["ordering"].append({"plan_id": "plan-missing"})

    artifact = parse_plans_artifact(_plans_text(frontmatter))
    assert artifact.ordering[-1].plan_id == "plan-missing"


def test_ordering_depends_on_unknown_plan_id_still_parses() -> None:
    frontmatter = _plans_frontmatter()
    frontmatter["ordering"][0]["depends_on"] = ["plan-missing"]

    artifact = parse_plans_artifact(_plans_text(frontmatter))
    assert artifact.ordering[0].depends_on == ("plan-missing",)


def test_ordering_assumption_targets_unknown_plan_id_still_parses() -> None:
    frontmatter = _plans_frontmatter()
    frontmatter["ordering"][0]["assumption_targets"] = ["plan-missing"]

    artifact = parse_plans_artifact(_plans_text(frontmatter))
    assert artifact.ordering[0].assumption_targets == ("plan-missing",)


def test_plan_absent_from_ordering_still_parses() -> None:
    """Ordering totality is a relation gate — the parser must not refuse it."""
    frontmatter = _plans_frontmatter()
    frontmatter["ordering"] = [frontmatter["ordering"][0]]

    artifact = parse_plans_artifact(_plans_text(frontmatter))
    assert {plan.id for plan in artifact.plans} == {
        "plan-order-core",
        "plan-auth",
    }
    assert [entry.plan_id for entry in artifact.ordering] == ["plan-order-core"]


def test_cross_cutting_plan_with_component_ids_still_parses() -> None:
    frontmatter = _plans_frontmatter()
    frontmatter["plans"][1]["component_ids"] = ["component-order"]

    artifact = parse_plans_artifact(_plans_text(frontmatter))
    assert artifact.plans[1].disposition.value == "cross-cutting"
    assert artifact.plans[1].component_ids == ("component-order",)


def test_assumption_consuming_unknown_plan_id_still_parses() -> None:
    frontmatter = _plans_frontmatter()
    frontmatter["assumptions"][0]["consuming_plan_ids"] = ["plan-missing"]

    artifact = parse_plans_artifact(_plans_text(frontmatter))
    assert artifact.assumptions[0].consuming_plan_ids == ("plan-missing",)


def test_duplicate_assumption_ids_survive_as_separate_rows() -> None:
    frontmatter = _plans_frontmatter()
    frontmatter["assumptions"].append(dict(frontmatter["assumptions"][0]))

    artifact = parse_plans_artifact(_plans_text(frontmatter))
    assert [row.id for row in artifact.assumptions] == [
        "assumption-1",
        "assumption-1",
    ]


def test_duplicate_decision_ids_on_plans_survive_as_separate_rows() -> None:
    frontmatter = _plans_frontmatter()
    frontmatter["decisions"].append(dict(frontmatter["decisions"][0]))

    artifact = parse_plans_artifact(_plans_text(frontmatter))
    assert [row.id for row in artifact.decisions] == [
        frontmatter["decisions"][0]["id"],
        frontmatter["decisions"][0]["id"],
    ]


def test_plan_id_not_matching_slug_re_still_parses() -> None:
    frontmatter = _plans_frontmatter()
    frontmatter["plans"][0]["id"] = "Bad_Slug"

    artifact = parse_plans_artifact(_plans_text(frontmatter))
    assert artifact.plans[0].id == "Bad_Slug"


def test_duplicate_ordering_plan_ids_survive() -> None:
    frontmatter = _plans_frontmatter()
    frontmatter["ordering"].append({"plan_id": "plan-order-core"})

    artifact = parse_plans_artifact(_plans_text(frontmatter))
    assert [entry.plan_id for entry in artifact.ordering] == [
        "plan-order-core",
        "plan-auth",
        "plan-order-core",
    ]


def test_unknown_frontmatter_keys_ignored_on_plans() -> None:
    frontmatter = _plans_frontmatter()
    frontmatter["notes"] = "an operator's aside"
    frontmatter["plans"][0]["owner"] = "platform"

    artifact = parse_plans_artifact(_plans_text(frontmatter))
    assert artifact.plans[0].id == "plan-order-core"
    assert "owner" not in render_plans_artifact(artifact)


def test_malformed_yaml_raises_and_names_path_for_plans(tmp_path: Path) -> None:
    path = tmp_path / PLANS_FILENAME
    path.write_text("---\nplans: [unclosed\n---\n# Plans\n", encoding="utf-8")

    with pytest.raises(RoadmapArtifactError) as exc:
        load_plans_artifact(path)
    assert exc.value.path == path
    assert str(path) in str(exc.value)


def test_parse_draft_seed_provenance_requires_roadmap_components() -> None:
    with pytest.raises(RoadmapArtifactError) as exc:
        parse_draft_seed_provenance("---\n---\n")
    assert DRAFT_SEED_ROADMAP_COMPONENTS_KEY in str(exc.value)


def test_parse_draft_seed_provenance_accepts_cross_cutting_flag() -> None:
    text = render_draft_seed_provenance(
        DraftSeedProvenance(
            roadmap_components=("component-order",),
            cross_cutting=True,
        )
    )

    provenance = parse_draft_seed_provenance(text)
    assert provenance.roadmap_components == ("component-order",)
    assert provenance.cross_cutting is True


def test_draft_seed_provenance_unknown_component_id_still_parses() -> None:
    text = f"""---
{DRAFT_SEED_ROADMAP_COMPONENTS_KEY}:
- component-missing
---
"""

    provenance = parse_draft_seed_provenance(text)
    assert provenance.roadmap_components == ("component-missing",)


# --------------------------------------------------------------------------
# Layering
# --------------------------------------------------------------------------


def test_leaf_imports_no_first_party_module() -> None:
    """Consumers import the contract at module load, so it must pull in no
    sibling. A stub ``plan_tool`` package stands in for the real one, whose
    ``__init__`` eagerly imports orchestrators that would mask the answer."""
    assert re.search(r"(?m)^(from|import) plan_tool", MODULE_PATH.read_text()) is None

    code = (
        "import sys, types\n"
        "pkg = types.ModuleType('plan_tool')\n"
        f"pkg.__path__ = [{str(MODULE_PATH.parent)!r}]\n"
        "sys.modules['plan_tool'] = pkg\n"
        "import plan_tool.roadmap_artifacts\n"
        "leaked = [m for m in sys.modules if m.startswith('plan_tool.')"
        " and m != 'plan_tool.roadmap_artifacts']\n"
        "assert not leaked, leaked\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_leaf_declares_no_invoker_seam() -> None:
    """Pure functions of their inputs: nothing here shells out or takes a
    Claude-invoking callable."""
    source = MODULE_PATH.read_text()
    for token in ("invoker", "subprocess"):
        assert token not in source


@pytest.mark.parametrize("bad_id", ["../../../escaped", "sub/dir", "Plan_One", "trailing-", ""])
def test_no_promotion_destination_for_a_non_slug_plan_id(bad_id: str) -> None:
    """The write-side mirror of ``_validate_draft_seed_path``.

    ``roadmap --apply`` runs no gates, so a traversal id would otherwise
    build a destination outside ``plan-seeds/``.
    """
    with pytest.raises(RoadmapArtifactError):
        resolve_plan_seed_dest(Path("/repo/plan-seeds"), bad_id)


def test_promotion_destination_for_a_valid_slug_plan_id() -> None:
    """The carve-out: an ordinary create-compatible slug still resolves."""
    dest = resolve_plan_seed_dest(Path("/repo/plan-seeds"), "order-core-2")

    assert dest == Path("/repo/plan-seeds/order-core-2.md")


# --------------------------------------------------------------------------
# Constraints stack collection: missing (None) is distinct from empty (())
# --------------------------------------------------------------------------

_STACK_ROWS = [
    {"id": "stack-1", "concern": "platform", "choice": "AWS Lambda"},
    {"id": "stack-2", "concern": "store-engine", "open": True},
]


def _stack_text(stack) -> str:
    frontmatter = _constraints_frontmatter()
    frontmatter["stack"] = stack
    return _constraints_text(frontmatter)


def _rendered_frontmatter(artifact: ConstraintsArtifact) -> dict:
    return yaml.safe_load(render_constraints_artifact(artifact).split("---\n")[1])


def test_constraints_without_stack_key_parses_to_none() -> None:
    assert parse_constraints_artifact(CONSTRAINTS_TEXT).stack is None


def test_constraints_with_empty_stack_list_parses_to_empty_tuple() -> None:
    assert parse_constraints_artifact(_stack_text([])).stack == ()


def test_stack_null_is_read_as_not_recorded() -> None:
    assert parse_constraints_artifact(_stack_text(None)).stack is None


def test_stackless_constraints_render_has_no_stack_key() -> None:
    artifact = parse_constraints_artifact(CONSTRAINTS_TEXT)
    assert tuple(_rendered_frontmatter(artifact)) == CONSTRAINTS_ROW_KEYS


def test_stackless_constraints_text_rerenders_byte_identically() -> None:
    """Accepted versions are digested as text; a stack-less one must not change."""
    first = render_constraints_artifact(parse_constraints_artifact(CONSTRAINTS_TEXT))
    again = render_constraints_artifact(parse_constraints_artifact(first))
    assert again == first
    assert "stack" not in first


def test_empty_stack_survives_round_trip_as_present() -> None:
    """Render keys on `is not None`, not truthiness, so `stack: []` is kept."""
    artifact = parse_constraints_artifact(_stack_text([]))
    rendered = render_constraints_artifact(artifact)
    assert _rendered_frontmatter(artifact)["stack"] == []
    assert parse_constraints_artifact(rendered).stack == ()


def test_stack_rows_round_trip_choice_and_open() -> None:
    artifact = parse_constraints_artifact(_stack_text(_STACK_ROWS))
    assert artifact.stack == (
        StackRow(id="stack-1", concern="platform", choice="AWS Lambda"),
        StackRow(id="stack-2", concern="store-engine", open=True),
    )
    assert _rendered_frontmatter(artifact)["stack"] == _STACK_ROWS
    assert parse_constraints_artifact(render_constraints_artifact(artifact)) == artifact


@pytest.mark.parametrize(
    "row",
    [
        {"id": "stack-9", "concern": "platform", "choice": "x", "open": True},
        {"id": "stack-9", "concern": "platform"},
    ],
    ids=["both", "neither"],
)
def test_stack_row_choice_open_combination_parses_for_the_gate_to_refuse(row) -> None:
    """The parser checks types only; `stack-row-state` owns exactly-one, so a
    both/neither row reaches the gate on every route instead of dying in the parser."""
    artifact = parse_constraints_artifact(_stack_text([row]))
    assert [r.id for r in artifact.stack] == ["stack-9"]


@pytest.mark.parametrize(
    "stack",
    [
        "not-a-list",
        ["not-a-mapping"],
        [{"id": "stack-9", "choice": "x"}],
        [{"id": "stack-9", "concern": "platform", "choice": 3}],
        [{"id": "stack-9", "concern": "platform", "open": "yes"}],
    ],
)
def test_stack_wrong_types_raise(stack) -> None:
    with pytest.raises(RoadmapArtifactError):
        parse_constraints_artifact(_stack_text(stack))


def test_unknown_concern_and_duplicate_ids_parse_without_raising() -> None:
    """Both are gate findings, not parse errors: shape here, relations in gates."""
    rows = [
        {"id": "stack-1", "concern": "message-bus", "open": True},
        {"id": "stack-1", "concern": "platform", "open": True},
    ]
    artifact = parse_constraints_artifact(_stack_text(rows))
    assert [r.concern for r in artifact.stack] == ["message-bus", "platform"]
    assert "message-bus" not in STACK_CONCERNS


def test_stack_rows_keep_source_order_without_collapsing() -> None:
    rows = [
        {"id": "stack-2", "concern": "platform", "open": True},
        {"id": "stack-1", "concern": "platform", "open": True},
        {"id": "stack-2", "concern": "store-engine", "open": True},
    ]
    artifact = parse_constraints_artifact(_stack_text(rows))
    assert [r.id for r in artifact.stack] == ["stack-2", "stack-1", "stack-2"]
