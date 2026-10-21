from __future__ import annotations

import copy

import pytest

from plan_tool.concept_review import (
    IncompleteConceptReviewError,
    InvalidConceptScopeError,
    StaleConceptReviewError,
    review_concept_scope,
)
from plan_tool.concept_tree import ConceptNode, ConceptTree, concept_id


def _node(title: str, parents: list[str] | None = None, **values: object) -> ConceptNode:
    parent_path = parents or []
    defaults: dict[str, object] = {
        "id": concept_id(title, parent_path), "title": title,
        "parent_path": parent_path,
    }
    defaults.update(values)
    return ConceptNode(**defaults)  # type: ignore[arg-type]


def _tree() -> ConceptTree:
    return ConceptTree(
        plan_slug="review", plan_fingerprint="source-one",
        concepts=[
            _node("Parent", source_metadata={"derived": "parent"}),
            _node("Child", ["Parent"], source_metadata={"derived": "child"}),
            _node("Sibling", source_metadata={"derived": "sibling"}),
        ],
    )


def _review(tree: ConceptTree, ids: list[str], decisions: object, **options: object) -> ConceptTree:
    return review_concept_scope(
        tree, ids, decisions, "source-one", **options  # type: ignore[arg-type]
    )


def test_review_accepts_include_defer_and_wont_do() -> None:
    tree = _tree()
    ids = [node.id for node in tree.concepts]
    updated = _review(tree, ids, dict(zip(ids, ["include", "defer", "wont_do"])))
    assert [node.decision for node in updated.concepts] == ["include", "defer", "wont_do"]


def test_review_updates_only_selected_scope() -> None:
    tree = _tree()
    untouched = copy.deepcopy(tree.concepts[1:])
    updated = _review(tree, [tree.concepts[0].id], {tree.concepts[0].id: "include"})
    assert updated.concepts[1:] == untouched


def test_parent_scope_does_not_include_descendants() -> None:
    tree = _tree()
    updated = _review(
        tree, [tree.concepts[0].id], {tree.concepts[0].id: "defer"}, sign_off=True
    )
    assert updated.concepts[0].review_state == "approved"
    assert updated.concepts[1] == tree.concepts[1]


@pytest.mark.parametrize("scope", [[], ["missing"]])
def test_empty_or_unknown_scope_is_rejected_atomically(scope: list[str]) -> None:
    tree = _tree()
    before = copy.deepcopy(tree)
    with pytest.raises(InvalidConceptScopeError):
        _review(tree, scope, {})
    assert tree == before


def test_duplicate_scope_id_is_rejected() -> None:
    tree = _tree()
    identifier = tree.concepts[0].id
    with pytest.raises(InvalidConceptScopeError):
        _review(tree, [identifier, identifier], {identifier: "include"})


def test_unknown_review_state_is_rejected_atomically() -> None:
    tree = _tree()
    before = copy.deepcopy(tree)
    with pytest.raises(InvalidConceptScopeError):
        _review(tree, [tree.concepts[0].id], {tree.concepts[0].id: "maybe"})
    assert tree == before


def test_unhashable_review_state_is_rejected_atomically() -> None:
    tree = _tree()
    before = copy.deepcopy(tree)
    with pytest.raises(InvalidConceptScopeError):
        _review(
            tree,
            [tree.concepts[0].id],
            [(tree.concepts[0].id, [])],  # type: ignore[list-item]
        )
    assert tree == before


def test_decision_outside_scope_is_rejected() -> None:
    tree = _tree()
    with pytest.raises(InvalidConceptScopeError):
        _review(tree, [tree.concepts[0].id], {
            tree.concepts[0].id: "include", tree.concepts[1].id: "defer",
        })


def test_incomplete_scope_cannot_be_signed_off() -> None:
    tree = _tree()
    ids = [node.id for node in tree.concepts[:2]]
    with pytest.raises(IncompleteConceptReviewError):
        _review(tree, ids, {ids[0]: "include"}, sign_off=True)


def test_stale_source_state_cannot_be_reviewed_or_signed_off() -> None:
    tree = _tree()
    before = copy.deepcopy(tree)
    with pytest.raises(StaleConceptReviewError):
        review_concept_scope(
            tree, [tree.concepts[0].id], {tree.concepts[0].id: "include"},
            "source-old", sign_off=True,
        )
    assert tree == before


def test_signoff_marks_exactly_the_selected_scope() -> None:
    tree = _tree()
    selected = [tree.concepts[0].id, tree.concepts[2].id]
    updated = _review(
        tree, selected, {selected[0]: "include", selected[1]: "wont_do"},
        sign_off=True,
    )
    assert [node.review_state for node in updated.concepts] == [
        "approved", "unreviewed", "approved",
    ]
    assert updated.concepts[0].source_metadata["signoff_source_state"] == "source-one"
    assert updated.concepts[1] == tree.concepts[1]


def test_state_change_invalidates_prior_signoff() -> None:
    tree = _tree()
    node = tree.concepts[0]
    node.decision = "include"
    node.review_state = "approved"
    node.source_metadata.update(
        signoff_decision="include", signoff_source_state="source-one"
    )
    updated = _review(tree, [node.id], {node.id: "defer"})
    assert updated.concepts[0].review_state == "unreviewed"
    assert "signoff_decision" not in updated.concepts[0].source_metadata
    assert "signoff_source_state" not in updated.concepts[0].source_metadata


def test_unsigned_review_does_not_forge_signoff() -> None:
    tree = _tree()
    node = tree.concepts[0]
    updated = _review(tree, [node.id], {node.id: "include"})
    assert updated.concepts[0].review_state == "unreviewed"
    assert updated.concepts[0].source_metadata == {"derived": "parent"}


def test_reapplying_same_state_does_not_refresh_approval() -> None:
    tree = _tree()
    node = tree.concepts[0]
    node.decision = "include"
    node.review_state = "approved"
    node.source_metadata.update(
        signoff_decision="include", signoff_source_state="source-one", signed_at="fixed"
    )
    updated = _review(tree, [node.id], {node.id: "include"})
    assert updated.concepts[0] == node


def test_duplicate_decision_is_rejected_and_input_remains_unchanged() -> None:
    tree = _tree()
    before = copy.deepcopy(tree)
    identifier = tree.concepts[0].id
    with pytest.raises(InvalidConceptScopeError):
        _review(tree, [identifier], [(identifier, "include"), (identifier, "defer")])
    assert tree == before
