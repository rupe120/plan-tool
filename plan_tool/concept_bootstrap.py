"""Pure, deterministic derivation of concept records from plan sections."""

from __future__ import annotations

import copy
import json
import unicodedata
from dataclasses import asdict, dataclass, field, replace
from typing import Iterable

from plan_tool.concept_tree import ConceptNode, ConceptTree, concept_id
from plan_tool.parser import BodySection
from plan_tool.schema import Plan


_BASELINE_KEY = "derived_baseline"
_SOURCE_KEY = "source_key"
_DERIVED_FIELDS = ("title", "parent_path", "order", "source")


def canonical_source_key(section: BodySection, parent_path: Iterable[str] = ()) -> str:
    """Return the canonical positional identity used by every derivation."""
    components = [*parent_path, section.name]
    normalized = [
        " ".join(unicodedata.normalize("NFKC", value).split())
        for value in components
    ]
    return "/".join(
        f"{len(value.encode('utf-8'))}:{value}" for value in normalized
    )


def _derived_values(node: ConceptNode) -> dict[str, object]:
    return {name: copy.deepcopy(getattr(node, name)) for name in _DERIVED_FIELDS}


def _metadata(source_key: str, baseline: dict[str, object]) -> dict[str, str]:
    return {
        _SOURCE_KEY: source_key,
        _BASELINE_KEY: json.dumps(baseline, sort_keys=True, separators=(",", ":")),
    }


def _baseline(node: ConceptNode) -> dict[str, object]:
    raw = node.source_metadata.get(_BASELINE_KEY)
    if raw is None:
        return _derived_values(node)
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return _derived_values(node)
    return value if isinstance(value, dict) else _derived_values(node)


def bootstrap_concepts(
    plan: Plan,
    sections: Iterable[BodySection],
    *,
    plan_slug: str,
    plan_fingerprint: str,
) -> ConceptTree:
    """Build a deterministic, unreviewed concept tree without persistence."""
    if not isinstance(plan, Plan):
        raise TypeError("plan must be a validated Plan")
    concepts: list[ConceptNode] = []
    for section in sections:
        source_key = canonical_source_key(section)
        node = ConceptNode(
            id=concept_id(section.name, []),
            title=section.name,
            order=section.order,
            source=section.body,
        )
        node.source_metadata = _metadata(source_key, _derived_values(node))
        concepts.append(node)
    return ConceptTree(
        plan_slug=plan_slug,
        plan_fingerprint=plan_fingerprint,
        concepts=concepts,
    )


@dataclass(frozen=True)
class ConceptConflict:
    """A divergent three-way edit, retaining values needed for reporting."""

    concept_id: str
    source_key: str
    field: str
    baseline: object
    current: object
    derived: object
    reason: str = "divergent_change"


@dataclass
class RederivationResult:
    """A complete candidate and every conflict found while deriving it."""

    candidate: ConceptTree
    conflicts: list[ConceptConflict] = field(default_factory=list)

    @property
    def updated_tree(self) -> ConceptTree | None:
        return None if self.conflicts else self.candidate


def _source_key(node: ConceptNode) -> str:
    return node.source_metadata.get(_SOURCE_KEY, node.id)


def _merge_node(
    current: ConceptNode, fresh: ConceptNode
) -> tuple[ConceptNode, list[ConceptConflict]]:
    baseline = _baseline(current)
    merged = copy.deepcopy(current)
    conflicts: list[ConceptConflict] = []
    for name in _DERIVED_FIELDS:
        ancestor = baseline.get(name, getattr(current, name))
        current_value = getattr(current, name)
        fresh_value = getattr(fresh, name)
        current_changed = current_value != ancestor
        source_changed = fresh_value != ancestor
        if source_changed and current_changed and current_value != fresh_value:
            conflicts.append(
                ConceptConflict(
                    concept_id=current.id,
                    source_key=_source_key(current),
                    field=name,
                    baseline=copy.deepcopy(ancestor),
                    current=copy.deepcopy(current_value),
                    derived=copy.deepcopy(fresh_value),
                )
            )
        elif source_changed and not current_changed:
            setattr(merged, name, copy.deepcopy(fresh_value))
    if not conflicts:
        metadata = copy.deepcopy(current.source_metadata)
        metadata.update(_metadata(_source_key(fresh), _derived_values(fresh)))
        merged.source_metadata = metadata
    return merged, conflicts


def rederive_concepts(current: ConceptTree, fresh: ConceptTree) -> RederivationResult:
    """Three-way merge a fresh derivation without mutating ``current``."""
    current_by_key = {_source_key(node): node for node in current.concepts}
    fresh_by_key = {_source_key(node): node for node in fresh.concepts}
    candidate_nodes: list[ConceptNode] = []
    conflicts: list[ConceptConflict] = []

    for fresh_node in fresh.concepts:
        current_node = current_by_key.get(_source_key(fresh_node))
        if current_node is None:
            candidate_nodes.append(copy.deepcopy(fresh_node))
            continue
        merged, node_conflicts = _merge_node(current_node, fresh_node)
        candidate_nodes.append(merged)
        conflicts.extend(node_conflicts)

    for current_node in current.concepts:
        if _source_key(current_node) in fresh_by_key:
            continue
        changed = _derived_values(current_node) != _baseline(current_node)
        reviewed = current_node.review_state != "unreviewed"
        if changed or reviewed:
            conflicts.append(
                ConceptConflict(
                    concept_id=current_node.id,
                    source_key=_source_key(current_node),
                    field="concept",
                    baseline=_baseline(current_node),
                    current=asdict(current_node),
                    derived=None,
                    reason="reviewed_removal" if reviewed else "edited_removal",
                )
            )
            candidate_nodes.append(copy.deepcopy(current_node))

    candidate = replace(
        copy.deepcopy(current),
        plan_slug=fresh.plan_slug,
        plan_fingerprint=fresh.plan_fingerprint,
        schema_version=fresh.schema_version,
        concepts=candidate_nodes,
    )
    return RederivationResult(candidate=candidate, conflicts=conflicts)


def carry_forward_decisions(saved: ConceptTree, fresh: ConceptTree) -> ConceptTree:
    """Overlay a flat decision record's defer/wont_do decisions onto a fresh
    bootstrap, matched by id — a plain carry-forward, not a three-way merge
    (a decision record tracks no baseline and never conflicts).

    Returns a pre-review candidate for ``_review_create_concepts``, not a
    directly-persistable record — ``record_kind`` is inherited from
    ``fresh`` (matching the no-saved-tree branch's own convention), and
    ``_review_create_concepts`` stamps the final record_kind.
    """
    saved_by_id = {node.id: node for node in saved.concepts}
    fresh_ids = {node.id for node in fresh.concepts}
    candidate_nodes: list[ConceptNode] = []
    for fresh_node in fresh.concepts:
        saved_node = saved_by_id.get(fresh_node.id)
        if saved_node is None:
            candidate_nodes.append(copy.deepcopy(fresh_node))
            continue
        merged = copy.deepcopy(fresh_node)
        merged.decision = saved_node.decision
        merged.rationale = saved_node.rationale
        merged.review_state = saved_node.review_state
        candidate_nodes.append(merged)
    for saved_node in saved.concepts:
        if saved_node.id not in fresh_ids:
            candidate_nodes.append(copy.deepcopy(saved_node))
    return ConceptTree(
        plan_slug=fresh.plan_slug,
        plan_fingerprint=fresh.plan_fingerprint,
        concepts=candidate_nodes,
        schema_version=fresh.schema_version,
        record_kind=fresh.record_kind,
    )


# Explicit aliases keep the public operation names discoverable to callers.
bootstrap_concept_tree = bootstrap_concepts
rederive_concept_tree = rederive_concepts
