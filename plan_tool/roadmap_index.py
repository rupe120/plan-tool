"""Render the roadmap folder's ``INDEX.md``: the accepted head and every version's status.

A leaf over the version store. It must not import the roadmap orchestrator or
the candidate-run module (the orchestrator imports this one); the candidate
record names below are mirrored and pinned by ``tests/test_roadmap_index.py``.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from plan_tool.fileio import atomic_write_text
from plan_tool.roadmap_artifacts import (
    RoadmapArtifactError,
    parse_components_artifact,
    parse_plans_artifact,
    parse_constraints_artifact,
    roadmap_dir,
)
from plan_tool.roadmap_stack_summary import pending_anchor_ids, stack_summary_lines
from plan_tool.roadmap_versions import (
    ROADMAP_VERSION_NAMESPACE_DIRNAME,
    STORED_VERSION_RECORD_FILENAME,
    VERSION_ARTIFACT_KEYS,
    RoadmapVersionError,
    artifact_member_name,
    load_accepted_head,
    load_resolved_stored_version,
    load_stored_version,
    version_namespace_path,
)

INDEX_FILENAME: Final[str] = "INDEX.md"

# Mirrors of the candidate-record names in the candidate-run module.
ADMISSION_FILENAME: Final[str] = "candidate-admission.json"
EVIDENCE_FILENAME: Final[str] = "candidate-evidence.json"
SUPERSESSIONS_DIRECTORY: Final[str] = "candidate-supersessions"
TERMINAL_RESOLUTIONS_DIRECTORY: Final[str] = "candidate-terminal-resolutions"

_TERMINAL_REASONS: Final[tuple[str, ...]] = ("rejected", "discarded", "settled")
_SHORT_ID_LENGTH: Final[int] = 8

STATUS_ACCEPTED_HEAD: Final[str] = "accepted head"
STATUS_PROMOTED: Final[str] = "promoted"
STATUS_ACTIVE: Final[str] = "active"
STATUS_SUPERSEDED: Final[str] = "superseded"
STATUS_UNRECORDED: Final[str] = "unrecorded"


class RoadmapIndexNoHeadError(RoadmapVersionError):
    """The roadmap has no accepted head, so there is nothing to index."""


@dataclass(frozen=True)
class IndexVersionRow:
    """One stored version as the index lists it, already in lineage order."""

    version_id: str
    kind: str
    status: str
    predecessor_version_id: str | None
    answered_feedback_ids: tuple[str, ...]


def classify_version_status(
    version_id: str,
    *,
    head_version_id: str,
    promoted_ancestor_ids: frozenset[str],
    active_candidate_version_id: str | None,
    terminal_reason: str | None,
    is_superseded: bool,
) -> str:
    """Return the one status for a version; the first matching rule wins."""
    if version_id == head_version_id:
        return STATUS_ACCEPTED_HEAD
    # Outranks superseded: a stack hop superseded when the stack grew is still promoted.
    if version_id in promoted_ancestor_ids:
        return STATUS_PROMOTED
    if version_id == active_candidate_version_id:
        return STATUS_ACTIVE
    if terminal_reason is not None:
        return terminal_reason
    if is_superseded:
        return STATUS_SUPERSEDED
    return STATUS_UNRECORDED


def render_roadmap_index(
    slug: str,
    head_version_id: str,
    rows: Sequence[IndexVersionRow],
    stack_lines: Sequence[str],
) -> str:
    """Return the INDEX.md text; ``rows`` are listed in the order given.

    ``stack_lines`` are ``stack_summary_lines`` output, placed verbatim.
    """
    lines = [
        f"# Roadmap `{slug}`",
        "",
        "## Accepted head",
        "",
        f"Version `{head_version_id[:_SHORT_ID_LENGTH]}`.",
        "",
    ]
    for artifact_key in VERSION_ARTIFACT_KEYS:
        target = f"{ROADMAP_VERSION_NAMESPACE_DIRNAME}/{head_version_id}/{artifact_member_name(artifact_key)}"
        lines.append(f"- [{artifact_key}]({target})")
    lines += ["", "## Stack", "", *stack_lines]
    lines += [
        "",
        "## Versions",
        "",
        "| Version | Kind | Status | Predecessor | Answered feedback |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        predecessor = (
            f"`{row.predecessor_version_id[:_SHORT_ID_LENGTH]}`"
            if row.predecessor_version_id is not None
            else "—"
        )
        feedback = ", ".join(row.answered_feedback_ids) if row.answered_feedback_ids else "none"
        lines.append(
            f"| `{row.version_id[:_SHORT_ID_LENGTH]}` | {row.kind} | {row.status} "
            f"| {predecessor} | {feedback} |"
        )
    return "\n".join(lines) + "\n"


def collect_index_rows(plans_dir: Path, slug: str) -> tuple[str, tuple[IndexVersionRow, ...]]:
    """Read the store and return ``(head_version_id, rows in lineage order)``."""
    head = load_accepted_head(plans_dir=plans_dir, slug=slug)
    if head is None:
        raise RoadmapIndexNoHeadError(f"roadmap {slug!r} has no accepted head")
    namespace = version_namespace_path(plans_dir, slug)
    records = {}
    for entry in sorted(namespace.iterdir()):
        if entry.is_dir() and (entry / STORED_VERSION_RECORD_FILENAME).is_file():
            records[entry.name] = load_stored_version(
                plans_dir=plans_dir, slug=slug, version_id=entry.name
            )

    ancestors: set[str] = set()
    cursor = records[head.version_id].predecessor_version_id if head.version_id in records else None
    while cursor is not None and cursor not in ancestors:
        ancestors.add(cursor)
        parent = records.get(cursor)
        cursor = parent.predecessor_version_id if parent is not None else None

    active_id = _read_active_candidate_id(namespace)
    rows = []
    for version_id, record in records.items():
        rows.append(
            IndexVersionRow(
                version_id=version_id,
                kind=record.version_kind,
                status=classify_version_status(
                    version_id,
                    head_version_id=head.version_id,
                    promoted_ancestor_ids=frozenset(ancestors),
                    active_candidate_version_id=active_id,
                    terminal_reason=_read_terminal_reason(namespace, version_id),
                    is_superseded=(namespace / SUPERSESSIONS_DIRECTORY / f"{version_id}.json").is_file(),
                ),
                predecessor_version_id=record.predecessor_version_id,
                answered_feedback_ids=_read_answered_feedback_ids(namespace / version_id),
            )
        )
    depths = {version_id: _chain_depth(version_id, records) for version_id in records}
    rows.sort(key=lambda row: (depths[row.version_id], row.version_id))
    return head.version_id, tuple(rows)


def collect_index_stack_lines(plans_dir: Path, slug: str, head_version_id: str) -> list[str]:
    """Summarize the head's stack; an unparseable member raises, never reads "not recorded"."""
    resolved = load_resolved_stored_version(
        plans_dir=plans_dir, slug=slug, version_id=head_version_id
    )
    by_key = dict(zip(resolved.artifact_keys, resolved.artifact_bytes, strict=True))
    try:
        constraints = parse_constraints_artifact(by_key["constraints"].decode("utf-8"))
        components = parse_components_artifact(by_key["components"].decode("utf-8"))
        plans_decisions = (
            parse_plans_artifact(by_key["plans"].decode("utf-8")).decisions
            if "plans" in by_key
            else ()
        )
    except RoadmapArtifactError as exc:
        raise RoadmapVersionError(f"accepted head artifact is unparseable: {exc}") from exc
    pending = pending_anchor_ids(
        constraints.decisions, components.decisions, plans_decisions
    )
    return stack_summary_lines(constraints, pending)


def write_roadmap_index(plans_dir: Path, slug: str) -> Path:
    """Replace ``<roadmap folder>/INDEX.md`` whole and return its path."""
    head_version_id, rows = collect_index_rows(plans_dir, slug)
    stack_lines = collect_index_stack_lines(plans_dir, slug, head_version_id)
    path = roadmap_dir(plans_dir, slug) / INDEX_FILENAME
    atomic_write_text(path, render_roadmap_index(slug, head_version_id, rows, stack_lines))
    return path


def _chain_depth(version_id: str, records: dict[str, Any]) -> int:
    depth = 0
    seen = {version_id}
    cursor = records[version_id].predecessor_version_id
    while cursor is not None and cursor in records and cursor not in seen:
        seen.add(cursor)
        depth += 1
        cursor = records[cursor].predecessor_version_id
    return depth


def _read_json_object(path: Path, *, description: str) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise RoadmapVersionError(f"{description} is unreadable") from exc
    if not isinstance(data, dict):
        raise RoadmapVersionError(f"{description} is not a JSON object")
    return data


def _read_active_candidate_id(namespace: Path) -> str | None:
    admission = _read_json_object(namespace / ADMISSION_FILENAME, description="candidate admission")
    if admission is None:
        return None
    active = admission.get("active_candidate_version_id")
    if active is not None and not isinstance(active, str):
        raise RoadmapVersionError("candidate admission active pointer is malformed")
    return active


def _read_terminal_reason(namespace: Path, version_id: str) -> str | None:
    record = _read_json_object(
        namespace / TERMINAL_RESOLUTIONS_DIRECTORY / f"{version_id}.json",
        description="candidate terminal resolution",
    )
    if record is None:
        return None
    reason = record.get("reason")
    if reason not in _TERMINAL_REASONS:
        raise RoadmapVersionError("candidate terminal resolution reason is malformed")
    return reason


def _read_answered_feedback_ids(version_directory: Path) -> tuple[str, ...]:
    evidence = _read_json_object(
        version_directory / EVIDENCE_FILENAME, description="candidate evidence"
    )
    if evidence is None:
        return ()
    batch_receipt = evidence.get("batch_receipt")
    if isinstance(batch_receipt, dict):
        items = batch_receipt.get("reviewer_items")
        if not isinstance(items, list) or not all(
            isinstance(item, dict) and isinstance(item.get("item_id"), str) for item in items
        ):
            raise RoadmapVersionError("candidate evidence reviewer items are malformed")
        return tuple(item["item_id"] for item in items)
    feedback = evidence.get("feedback")
    if isinstance(feedback, dict):
        feedback_id = feedback.get("feedback_id")
        if not isinstance(feedback_id, str):
            raise RoadmapVersionError("candidate evidence feedback is malformed")
        return (feedback_id,)
    return ()
