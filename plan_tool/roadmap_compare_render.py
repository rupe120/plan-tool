"""Render one bound roadmap comparison without changing its comparison facts.

The JSON field order is fixed by the literal dictionaries in this module. Lists
retain the bound comparison or fixed inventory order; JSON uses compact UTF-8
safe separators and a trailing newline.
"""

from __future__ import annotations

import enum
import json
from dataclasses import fields, is_dataclass
from typing import Mapping

from plan_tool.roadmap_artifacts import OrderingEntry, PatternRow
from plan_tool.roadmap_compare import ComparisonCard
from plan_tool.roadmap_compare_run import (
    RoadmapComparisonRun,
    RoadmapComparisonSnapshot,
    RoadmapGitPatch,
)
from plan_tool.roadmap_diff import RoadmapRelationDiff, ordered_stage_collections
from plan_tool.roadmap_view import KIND_COMPONENT_PATTERN, KIND_SYSTEM_PATTERN, display_label
from plan_tool.roadmap_versions import VERSION_ARTIFACT_KEYS


_DISPLAY_KINDS = {
    "system_patterns": KIND_SYSTEM_PATTERN,
    "component_patterns": KIND_COMPONENT_PATTERN,
}


def render_terminal_comparison(run: RoadmapComparisonRun) -> str:
    """Render the bound snapshots and typed comparison as a terminal report."""
    payload = comparison_json_payload(run)
    lines = [
        "Roadmap comparison",
        *_terminal_snapshot_lines("Base", payload["base"]),
        *_terminal_snapshot_lines("Target", payload["target"]),
        "Artifacts:",
    ]
    for artifact in payload["artifacts"]:
        lines.append(
            f"- {artifact['artifact_key']}: {artifact['evidence_outcome']} "
            f"(base {artifact['base_digest']}, target {artifact['target_digest']})"
        )
    lines.append("Cards:")
    lines.extend(_terminal_card_lines(card) for card in payload["cards"])
    lines.append("Relations:")
    lines.extend(_terminal_relation_lines(relation) for relation in payload["relations"])
    prose_evidence = payload["row_linked_prose_amendments"]
    lines.append(f"Row-linked prose amendments: {prose_evidence['outcome']}")
    lines.extend(
        f"- {item['artifact_key']}/{item['row_id']}: {json.dumps(item['fragment'], ensure_ascii=False)}"
        for item in prose_evidence["items"]
    )
    lines.append("Unmapped raw evidence:")
    lines.extend(f"- {item['artifact_key']}" for item in payload["unmapped_raw_evidence"])
    lines.append(f"Raw evidence identity: {payload['raw_evidence_identity']}")
    return "\n".join(lines) + "\n"


def _patch_by_artifact_key(patches: tuple[RoadmapGitPatch, ...]) -> dict[str, RoadmapGitPatch]:
    """Validate ``patches`` binds exactly ``VERSION_ARTIFACT_INVENTORY`` once
    each, and index by key — the shared check both renderers below need."""
    inventory_keys = VERSION_ARTIFACT_KEYS
    by_key = {patch.artifact_key: patch for patch in patches}
    if len(by_key) != len(patches) or set(by_key) != set(inventory_keys):
        raise ValueError("comparison patches must bind exactly the fixed artifact inventory")
    return by_key


def render_patch_comparison(run: RoadmapComparisonRun) -> str:
    """Return the retained Git output in configured artifact order, unchanged."""
    by_key = _patch_by_artifact_key(run.patches)
    inventory = VERSION_ARTIFACT_KEYS
    return "".join(by_key[key].patch for key in inventory)


def render_comparison_json(run: RoadmapComparisonRun) -> str:
    """Return the deterministic JSON projection of one bound comparison."""
    return json.dumps(
        comparison_json_payload(run), ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ) + "\n"


def comparison_json_payload(run: RoadmapComparisonRun) -> dict[str, object]:
    """Project bound facts in the documented field and collection order."""
    patch_by_key = _patch_by_artifact_key(run.patches)
    inventory = VERSION_ARTIFACT_KEYS
    base_digests = dict(zip(run.base.artifact_keys, run.base.artifact_digests, strict=True))
    target_digests = dict(zip(run.target.artifact_keys, run.target.artifact_digests, strict=True))
    return {
        "base": _snapshot_payload(run.base),
        "target": _snapshot_payload(run.target),
        "artifacts": [
            {
                "artifact_key": key,
                "evidence_outcome": "identical" if patch_by_key[key].status == 0 else "differing",
                "base_digest": base_digests[key],
                "target_digest": target_digests[key],
            }
            for key in inventory
        ],
        "cards": [_card_payload(card) for card in run.comparison.cards],
        "relations": [
            *[_relation_payload("added", item) for item in run.comparison.added_relations],
            *[_relation_payload("removed", item) for item in run.comparison.removed_relations],
        ],
        "row_linked_prose_amendments": {
            "outcome": run.comparison.prose_amendment_evidence.outcome,
            "items": [
                {
                    "artifact_key": item.artifact_key,
                    "row_id": item.row_id,
                    "fragment": item.fragment,
                }
                for item in run.comparison.prose_amendment_evidence.amendments
            ],
        },
        "unmapped_raw_evidence": [
            {"artifact_key": item.artifact_key}
            for item in run.comparison.unmapped_raw_evidence
        ],
        "raw_evidence_identity": run.comparison.raw_evidence_identity,
        "raw_evidence": [
            {"artifact_key": item.artifact_key, "patch": item.patch}
            for item in run.comparison.raw_evidence
        ],
    }


def _snapshot_payload(snapshot: RoadmapComparisonSnapshot) -> dict[str, object]:
    return {
        "kind": snapshot.kind,
        "version_id": snapshot.version_id,
        "brief_digest": snapshot.brief_digest,
        "artifact_count": len(snapshot.artifact_keys),
        "concept_count": sum(
            len(rows) for artifact in snapshot.parsed_artifacts.values()
            for _row_type, rows in ordered_stage_collections(artifact)
        ),
        "artifact_digests": [
            {"artifact_key": key, "digest": digest}
            for key, digest in zip(snapshot.artifact_keys, snapshot.artifact_digests, strict=True)
        ],
    }


def _card_payload(card: ComparisonCard) -> dict[str, object]:
    endpoint = card.after if card.after is not None else card.before
    return {
        "artifact_key": card.artifact_key,
        "row_kind": card.row_type,
        "stable_id": card.row_id,
        "change_kind": card.change_kind,
        "label": _display_label(endpoint, card.row_type),
        "before": _json_value(card.before),
        "after": _json_value(card.after),
        "changed_fields": [
            {"name": field.name, "before": _json_value(field.before), "after": _json_value(field.after)}
            for field in card.changed_fields
        ],
    }


def _display_label(row: object | None, row_kind: str) -> str | None:
    if row is None or isinstance(row, OrderingEntry):
        return None
    kind = _DISPLAY_KINDS.get(row_kind)
    if isinstance(row, PatternRow) and kind is None:
        raise ValueError(f"pattern card has unsupported row kind {row_kind!r}")
    return display_label(row, kind=kind)


def _relation_payload(direction: str, item: RoadmapRelationDiff) -> dict[str, object]:
    relation = item.relation
    return {
        "change_kind": direction,
        "kind": relation.kind.value,
        "owner_id": relation.owner_id,
        "endpoint_id": relation.endpoint_id,
        "owner_artifact_key": relation.owner_artifact_key,
        "direction": relation.direction.value,
        "owner_row_index": relation.owner_row_index,
    }


def _json_value(value: object) -> object:
    """Convert only explicit typed values into JSON-safe values."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, enum.Enum):
        return _json_value(value.value)
    if is_dataclass(value):
        return {field.name: _json_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("comparison mappings must have string keys")
        return {key: _json_value(value[key]) for key in sorted(value)}
    raise TypeError(f"comparison value is not JSON-safe: {type(value).__name__}")


def _terminal_snapshot_lines(name: str, snapshot: dict[str, object]) -> tuple[str, str]:
    return (
        f"{name}: kind={snapshot['kind']} version_id={snapshot['version_id']} "
        f"brief_digest={snapshot['brief_digest']}",
        f"{name} counts: artifacts={snapshot['artifact_count']} concepts={snapshot['concept_count']}",
    )


def _terminal_card_lines(card: dict[str, object]) -> str:
    fields = card["changed_fields"]
    fields_text = json.dumps(fields, ensure_ascii=False, separators=(",", ":"))
    return (
        f"- {card['change_kind']} {card['artifact_key']}/{card['row_kind']} "
        f"{card['stable_id']}: {card['label']} before={json.dumps(card['before'], ensure_ascii=False)} "
        f"after={json.dumps(card['after'], ensure_ascii=False)} fields={fields_text}"
    )


def _terminal_relation_lines(relation: dict[str, object]) -> str:
    return (
        f"- {relation['change_kind']} {relation['kind']} {relation['owner_id']} -> "
        f"{relation['endpoint_id']} ({relation['owner_artifact_key']} "
        f"occurrence {relation['owner_row_index']})"
    )
