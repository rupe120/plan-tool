from __future__ import annotations

import copy
from dataclasses import replace

import pytest

from plan_tool.concept_bootstrap import (
    bootstrap_concepts,
    carry_forward_decisions,
    empty_concept_headings_message,
    rederive_concepts,
)
from plan_tool.concept_tree import ConceptNode, ConceptTree, RECORD_KIND_DECISION
from plan_tool.parser import parse_body_sections
from plan_tool.schema import Plan


def _plan() -> Plan:
    return Plan.model_validate(
        {
            "title": "Concepts",
            "status": "planning",
            "priority": "medium",
            "steps": [{"id": 1, "title": "Build"}],
        }
    )


def _tree(body: str, fingerprint: str = "one"):
    return bootstrap_concepts(
        _plan(), parse_body_sections(body),
        plan_slug="concepts", plan_fingerprint=fingerprint,
    )


def test_bootstrap_is_deterministic_and_preserves_section_order() -> None:
    body = "## Risks\nFirst\n## Architecture\nSecond\n"
    first = _tree(body)
    assert first == _tree(body)
    assert [node.title for node in first.concepts] == ["risks", "architecture"]
    assert [node.order for node in first.concepts] == [0, 1]


def test_bootstrap_uses_safe_unreviewed_defaults() -> None:
    node = _tree("## Risks\nFirst\n").concepts[0]
    assert node.review_state == "unreviewed"
    assert node.decision == node.rationale == ""


def test_rederive_no_source_change_preserves_current_record() -> None:
    current = _tree("## Risks\nFirst\n")
    current.concepts[0].decision = "Accept"
    current.concepts[0].rationale = "Known"
    current.concepts[0].review_state = "approved"
    result = rederive_concepts(current, _tree("## Risks\nFirst\n", "two"))
    assert not result.conflicts
    assert result.candidate.concepts[0].decision == "Accept"
    assert result.candidate.concepts[0].review_state == "approved"


def test_rederive_source_only_change_updates_derived_fields() -> None:
    result = rederive_concepts(
        _tree("## Risks\nFirst\n"), _tree("## Risks\nSecond\n", "two")
    )
    assert not result.conflicts
    assert result.candidate.concepts[0].source == "Second"


def test_rederive_divergent_change_reports_conflict_without_mutation() -> None:
    current = _tree("## Risks\nFirst\n")
    current.concepts[0].source = "Human"
    before = copy.deepcopy(current)
    result = rederive_concepts(current, _tree("## Risks\nPlan\n", "two"))
    assert [conflict.field for conflict in result.conflicts] == ["source"]
    assert result.candidate.concepts[0].source == "Human"
    assert current == before
    assert result.updated_tree is None


def test_rederive_same_change_on_both_sides_is_not_conflict() -> None:
    current = _tree("## Risks\nFirst\n")
    current.concepts[0].source = "Shared"
    result = rederive_concepts(current, _tree("## Risks\nShared\n", "two"))
    assert not result.conflicts
    assert result.candidate.concepts[0].source == "Shared"


def test_rederive_removal_rules_and_deterministic_addition() -> None:
    current = _tree("## Risks\nFirst\n## Testing\nTests\n")
    safe = rederive_concepts(current, _tree("## Testing\nTests\n", "two"))
    assert not safe.conflicts
    assert [node.title for node in safe.candidate.concepts] == ["testing"]

    reviewed = copy.deepcopy(current)
    reviewed.concepts[0].review_state = "approved"
    blocked = rederive_concepts(reviewed, _tree("## Testing\nTests\n", "two"))
    assert blocked.conflicts[0].reason == "reviewed_removal"
    assert reviewed.concepts[0] in blocked.candidate.concepts

    addition = rederive_concepts(
        _tree("## Risks\nFirst\n"),
        _tree("## Risks\nFirst\n## Testing\nTests\n", "two"),
    )
    assert addition.candidate.concepts[1] == _tree(
        "## Risks\nFirst\n## Testing\nTests\n", "two"
    ).concepts[1]


def test_ids_ignore_review_fields() -> None:
    tree = _tree("## Risks\nFirst\n")
    identifier = tree.concepts[0].id
    changed = replace(tree.concepts[0], review_state="approved", rationale="why")
    assert changed.id == identifier


def _flat_record(node: ConceptNode, decision: str, review_state: str = "unreviewed", rationale: str = "") -> ConceptTree:
    """Build a one-node flat decision record the way ``_review_create_concepts``
    persists a deferral: id/title/order carried over, hierarchy dropped."""
    return ConceptTree(
        plan_slug="concepts",
        plan_fingerprint="saved",
        record_kind=RECORD_KIND_DECISION,
        concepts=[
            ConceptNode(
                id=node.id, title=node.title, order=node.order,
                decision=decision, rationale=rationale, review_state=review_state,
                bucket=node.title,
            )
        ],
    )


def test_carry_forward_overlays_decision_onto_matching_fresh_node() -> None:
    fresh = _tree("## Risks\nFirst\n")
    saved = _flat_record(
        fresh.concepts[0], "defer", review_state="approved", rationale="later",
    )
    candidate = carry_forward_decisions(saved, fresh)
    assert len(candidate.concepts) == 1
    node = candidate.concepts[0]
    assert node.decision == "defer"
    assert node.review_state == "approved"
    assert node.rationale == "later"
    # Fresh's own derived shape survives the overlay.
    assert node.source == fresh.concepts[0].source
    assert node.order == fresh.concepts[0].order


def test_carry_forward_never_conflicts_even_when_already_reviewed() -> None:
    # Unlike rederive_concepts, an already-approved saved decision must not
    # raise/conflict on a plain create re-run (BUG_BACKLOG: it used to,
    # unconditionally, because create fed flat records into rederive_concepts).
    fresh = _tree("## Risks\nFirst\n")
    saved = _flat_record(fresh.concepts[0], "wont_do", review_state="approved")
    candidate = carry_forward_decisions(saved, fresh)
    assert candidate.concepts[0].decision == "wont_do"
    assert candidate.concepts[0].review_state == "approved"


def test_carry_forward_preserves_orphaned_saved_node_when_section_removed() -> None:
    fresh_before = _tree("## Risks\nFirst\n")
    saved = _flat_record(fresh_before.concepts[0], "defer", review_state="unreviewed")
    fresh_after = _tree("## Testing\nTests\n", "two")  # "risks" section is gone
    candidate = carry_forward_decisions(saved, fresh_after)
    ids = {node.id for node in candidate.concepts}
    assert saved.concepts[0].id in ids
    assert fresh_after.concepts[0].id in ids
    assert len(candidate.concepts) == 2
    orphan = next(n for n in candidate.concepts if n.id == saved.concepts[0].id)
    assert orphan.decision == "defer"


def test_carry_forward_new_fresh_section_gets_no_decision() -> None:
    fresh = _tree("## Risks\nFirst\n## Testing\nTests\n")
    saved = _flat_record(fresh.concepts[0], "defer")
    candidate = carry_forward_decisions(saved, fresh)
    testing_node = next(n for n in candidate.concepts if n.title == "testing")
    assert testing_node.decision == ""
    assert testing_node.review_state == "unreviewed"


def test_carry_forward_matched_node_appears_exactly_once() -> None:
    # Guards the id-collision the naive "just append the saved node" fix
    # would hit: a matched section must yield one merged node, not two.
    fresh = _tree("## Risks\nFirst\n")
    saved = _flat_record(fresh.concepts[0], "defer")
    candidate = carry_forward_decisions(saved, fresh)
    matching = [n for n in candidate.concepts if n.id == fresh.concepts[0].id]
    assert len(matching) == 1


def test_empty_concept_headings_message_is_none_for_a_body_with_named_sections() -> None:
    body = "## Risks\nFirst\n## Architecture\nSecond\n"
    assert empty_concept_headings_message(parse_body_sections(body)) is None


def test_empty_concept_headings_message_lists_every_empty_heading_in_order() -> None:
    """``parse_body_sections`` drops trailing ``:``/``.``, so a heading made only
    of them has an empty name and ``concept_id`` would raise a bare
    ``ValueError`` naming nothing. Every command that bootstraps concepts from
    a body shares this one refusal text."""
    body = "## Risks\nA\n## :\nB\n## Architecture\nC\n## .\nD\n"
    message = empty_concept_headings_message(parse_body_sections(body))
    assert message is not None
    assert "no name after normalization" in message
    assert message.index("'## :'") < message.index("'## .'")
    assert "Risks" not in message and "Architecture" not in message


@pytest.mark.parametrize(
    "heading", ["## Notes ##", "## **Notes**", "## \u200b"],
    ids=["closing-hashes", "emphasis", "zero-width-only"],
)
def test_headings_with_a_non_empty_name_are_not_reported_as_empty(heading: str) -> None:
    """Carve-out: these keep a non-empty name (closing hashes and emphasis are
    not stripped; a zero-width space is not whitespace to ``str.split``), so the
    refusal must not widen to them."""
    assert empty_concept_headings_message(parse_body_sections(f"{heading}\nbody\n")) is None
