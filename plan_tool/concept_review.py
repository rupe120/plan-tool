"""Pure, scope-aware review operations for concept decision records."""

from __future__ import annotations

import copy
from collections.abc import Iterable, Mapping

from plan_tool.concept_tree import ConceptTree


CONCEPT_DECISIONS = frozenset({"include", "defer", "wont_do"})
_SIGNOFF_DECISION_KEY = "signoff_decision"
_SIGNOFF_SOURCE_STATE_KEY = "signoff_source_state"


class ConceptReviewError(ValueError):
    """Base class for a rejected concept review request."""


class InvalidConceptScopeError(ConceptReviewError):
    """The requested scope or decision payload is invalid."""


class IncompleteConceptReviewError(ConceptReviewError):
    """The decision payload does not cover every scoped concept exactly once."""


class StaleConceptReviewError(ConceptReviewError):
    """The reviewer acted against a different source state."""


def _decision_items(
    decisions: Mapping[str, str] | Iterable[tuple[str, str]],
) -> list[tuple[str, str]]:
    if isinstance(decisions, Mapping):
        return list(decisions.items())
    try:
        return list(decisions)
    except TypeError as exc:
        raise InvalidConceptScopeError("decisions must be a mapping or pair iterable") from exc


def _validate_request(
    tree: ConceptTree,
    scope: Iterable[str],
    decisions: Mapping[str, str] | Iterable[tuple[str, str]],
    expected_source_state: str,
) -> tuple[list[str], dict[str, str]]:
    if expected_source_state != tree.plan_fingerprint:
        raise StaleConceptReviewError("expected source state is stale")

    try:
        scoped_ids = list(scope)
    except TypeError as exc:
        raise InvalidConceptScopeError("scope must be an iterable of concept IDs") from exc
    if not scoped_ids:
        raise InvalidConceptScopeError("concept scope must not be empty")
    if any(not isinstance(concept_id, str) for concept_id in scoped_ids):
        raise InvalidConceptScopeError("concept scope must contain string IDs")
    if len(set(scoped_ids)) != len(scoped_ids):
        raise InvalidConceptScopeError("concept scope contains duplicate IDs")

    known_ids = {node.id for node in tree.concepts}
    unknown_ids = set(scoped_ids) - known_ids
    if unknown_ids:
        raise InvalidConceptScopeError("concept scope contains an unknown ID")

    items = _decision_items(decisions)
    if any(not isinstance(item, tuple) or len(item) != 2 for item in items):
        raise InvalidConceptScopeError("decisions must contain concept ID and state pairs")
    decision_ids = [concept_id for concept_id, _ in items]
    if any(not isinstance(concept_id, str) for concept_id in decision_ids):
        raise InvalidConceptScopeError("decision IDs must be strings")
    if len(set(decision_ids)) != len(decision_ids):
        raise InvalidConceptScopeError("decision payload contains duplicate IDs")

    scoped_set = set(scoped_ids)
    if set(decision_ids) - scoped_set:
        raise InvalidConceptScopeError("decision payload contains an ID outside the scope")
    if scoped_set - set(decision_ids):
        raise IncompleteConceptReviewError("every scoped concept requires a decision")

    decision_by_id = dict(items)
    if any(
        not isinstance(state, str) or state not in CONCEPT_DECISIONS
        for state in decision_by_id.values()
    ):
        raise InvalidConceptScopeError("decision payload contains an unknown state")
    return scoped_ids, decision_by_id


def _clear_signoff(node_metadata: dict[str, str]) -> None:
    node_metadata.pop(_SIGNOFF_DECISION_KEY, None)
    node_metadata.pop(_SIGNOFF_SOURCE_STATE_KEY, None)


def review_concept_scope(
    tree: ConceptTree,
    concept_ids: Iterable[str],
    decisions: Mapping[str, str] | Iterable[tuple[str, str]],
    expected_source_state: str,
    *,
    sign_off: bool = False,
) -> ConceptTree:
    """Apply a complete decision set to exactly ``concept_ids``.

    Validation completes before a deep-copied candidate is changed, so every
    rejected request leaves the supplied record untouched.
    """
    scoped_ids, decision_by_id = _validate_request(
        tree, concept_ids, decisions, expected_source_state
    )
    scoped_set = set(scoped_ids)
    updated = copy.deepcopy(tree)
    for node in updated.concepts:
        if node.id not in scoped_set:
            continue
        requested_decision = decision_by_id[node.id]
        decision_changed = node.decision != requested_decision
        if decision_changed:
            node.decision = requested_decision
            node.review_state = "unreviewed"
            _clear_signoff(node.source_metadata)
        if sign_off:
            node.review_state = "approved"
            node.source_metadata[_SIGNOFF_DECISION_KEY] = requested_decision
            node.source_metadata[_SIGNOFF_SOURCE_STATE_KEY] = tree.plan_fingerprint
    return updated


# Short aliases keep error handling readable for later orchestration layers.
InvalidScopeError = InvalidConceptScopeError
IncompleteReviewError = IncompleteConceptReviewError
StaleReviewError = StaleConceptReviewError
