"""Guarded publication of reviewed concept decisions and their plan effects."""

from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Callable

from pydantic import ValidationError as PydanticValidationError

from plan_tool.concept_tree import (
    ConceptNode,
    ConceptTree,
    InvalidConceptTreeError,
    _validate_tree,
    concepts_path,
)
from plan_tool.parser import (
    parse_body_sections,
    refresh_plan_provenance,
    render_plan_text,
    replace_body_sections,
    split_plan_document,
)
from plan_tool.response_contract import coerce_response_id
from plan_tool.schema import Plan, StepScope
from plan_tool.scope_fence import _fenced_code_spans


class SyncStatus(str, Enum):
    SUCCESS = "success"
    SOURCE_DIVERGENCE = "source_divergence"
    MAPPING_CONFLICT = "mapping_conflict"
    INVALID_STATE = "invalid_state"
    PUBLICATION_FAILURE = "publication_failure"


@dataclass(frozen=True)
class ConceptSyncResult:
    status: SyncStatus
    message: str = ""
    plan_fingerprint: str | None = None
    rollback_error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status is SyncStatus.SUCCESS


Publisher = Callable[[Path, str], None]
_DECISION_SCOPE = {
    "include": StepScope.COMMITTED,
    "defer": StepScope.DEFERRED,
    "wont_do": StepScope.WONT_DO,
}


def _accepted_decisions(tree: ConceptTree) -> list[ConceptNode]:
    return [node for node in tree.concepts if node.review_state == "approved"]


def render_scope_decisions(tree: ConceptTree) -> dict[str, str]:
    """Render accepted parked decisions in deterministic tree order."""
    rendered = {"deferred": [], "out of scope": []}
    target = {"defer": "deferred", "wont_do": "out of scope"}
    for node in sorted(tree.concepts, key=lambda item: (item.order, item.parent_path, item.id)):
        if node.review_state != "approved" or node.decision not in target:
            continue
        # One line each: a heading- or fence-looking line inside a title or
        # rationale would otherwise start a document-level boundary.
        title = " ".join(node.title.split())
        rationale = " ".join(node.rationale.split())
        suffix = f" — {rationale}" if rationale else ""
        rendered[target[node.decision]].append(
            f"{'  ' * len(node.parent_path)}- {title}{suffix}"
        )
    return {name: "\n".join(lines) for name, lines in rendered.items()}


def _mapped_scopes(tree: ConceptTree, plan: Plan) -> tuple[dict[int, StepScope] | None, str]:
    known_ids = {step.id for step in plan.steps}
    mapped: dict[int, StepScope] = {}
    for node in _accepted_decisions(tree):
        if node.decision not in _DECISION_SCOPE:
            return None, f"approved concept {node.id} has unknown decision {node.decision!r}"
        raw_step_id = node.source_metadata.get("step_id")
        if raw_step_id is None:
            continue
        step_id = coerce_response_id(raw_step_id)
        if step_id is None:
            return None, f"concept {node.id} has invalid step_id mapping {raw_step_id!r}"
        if step_id not in known_ids:
            return None, f"concept {node.id} maps to unknown step {step_id}"
        scope = _DECISION_SCOPE[node.decision]
        if step_id in mapped and mapped[step_id] is not scope:
            return None, f"step {step_id} has conflicting concept decisions"
        mapped[step_id] = scope
    return mapped, ""


def _fingerprint(plan_path: Path, staged_plan: bytes) -> str:
    """Apply compute_plan_fingerprint framing to staged plan bytes."""
    from plan_tool.locator import slug_from_filename

    digest = hashlib.sha256(staged_plan)
    slug = slug_from_filename(plan_path)
    assert slug is not None
    for detail in sorted((plan_path.parent / "plan-details" / slug).glob("*.md"), key=lambda p: p.name):
        digest.update(detail.name.encode("utf-8"))
        digest.update(b"\0")
        with contextlib.suppress(OSError):
            digest.update(detail.read_bytes())
    return digest.hexdigest()


def _atomic_publish(target: Path, text: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="", dir=target.parent,
        prefix=f".{target.name}.", suffix=".tmp", delete=False,
    )
    temporary_path = Path(temporary.name)
    try:
        with temporary:
            temporary.write(text)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, target)
    except BaseException:
        with contextlib.suppress(OSError):
            temporary_path.unlink()
        raise


def _restore(path: Path, old_text: str | None, publish: Publisher) -> None:
    if old_text is None:
        with contextlib.suppress(FileNotFoundError):
            path.unlink()
    else:
        publish(path, old_text)


def synchronize_concepts(
    plan_path: str | Path,
    plan_snapshot: Plan,
    original_tree: ConceptTree | None,
    reviewed_tree: ConceptTree,
    *,
    source_plan_text: str | None = None,
    publish: Publisher = _atomic_publish,
) -> ConceptSyncResult:
    """Synchronize one reviewed snapshot, or leave both artifacts unchanged.

    ``source_plan_text`` is the exact Markdown paired with ``plan_snapshot``.
    Supplying it enables owned-body compare-and-swap while still allowing
    concurrent edits outside the two owned sections to flow through.
    """
    path = Path(plan_path)
    sidecar = concepts_path(path)
    try:
        _validate_tree(reviewed_tree)
    except (InvalidConceptTreeError, TypeError, ValueError) as exc:
        return ConceptSyncResult(SyncStatus.INVALID_STATE, str(exc))

    mapping, mapping_error = _mapped_scopes(reviewed_tree, plan_snapshot)
    if mapping is None:
        status = SyncStatus.INVALID_STATE if "unknown decision" in mapping_error else SyncStatus.MAPPING_CONFLICT
        return ConceptSyncResult(status, mapping_error)

    try:
        current_plan_text = path.read_bytes().decode("utf-8")
        current_sidecar_text = sidecar.read_text(encoding="utf-8") if sidecar.exists() else None
    except (OSError, UnicodeDecodeError) as exc:
        return ConceptSyncResult(SyncStatus.SOURCE_DIVERGENCE, str(exc))

    source_text = source_plan_text if source_plan_text is not None else current_plan_text
    try:
        source_document = split_plan_document(source_text)
        current_document = split_plan_document(current_plan_text)
    except Exception as exc:  # malformed current source is invalid input
        return ConceptSyncResult(SyncStatus.INVALID_STATE, str(exc))
    if _fenced_code_spans(source_document.body).unmatched_opening is not None:
        return ConceptSyncResult(
            SyncStatus.INVALID_STATE,
            f"{path}: source snapshot has an unmatched opening code fence; "
            "add a matching closing fence before synchronizing concepts",
        )
    if _fenced_code_spans(current_document.body).unmatched_opening is not None:
        return ConceptSyncResult(
            SyncStatus.INVALID_STATE,
            f"{path}: plan body has an unmatched opening code fence; "
            "add a matching closing fence before synchronizing concepts",
        )
    source_owned = {
        section.name: section.body
        for section in parse_body_sections(
            source_document.body, ignore_fenced_code=True
        )
        if section.name in {"deferred", "out of scope"}
    }
    current_owned = {
        section.name: section.body
        for section in parse_body_sections(
            current_document.body, ignore_fenced_code=True
        )
        if section.name in {"deferred", "out of scope"}
    }
    if source_document.frontmatter_yaml != current_document.frontmatter_yaml or source_owned != current_owned:
        return ConceptSyncResult(SyncStatus.SOURCE_DIVERGENCE, "plan frontmatter or owned sections changed")

    expected_sidecar = (
        None
        if original_tree is None
        else json.dumps(asdict(original_tree), indent=2, allow_nan=False) + "\n"
    )
    if current_sidecar_text != expected_sidecar:
        return ConceptSyncResult(SyncStatus.SOURCE_DIVERGENCE, "concept record changed")

    plan_data = copy.deepcopy(plan_snapshot).model_dump(exclude_none=True)
    for step in plan_data["steps"]:
        if step["id"] in mapping:
            step["scope"] = mapping[step["id"]]
    try:
        updated_plan = Plan.model_validate(plan_data)
    except PydanticValidationError as exc:
        return ConceptSyncResult(SyncStatus.INVALID_STATE, str(exc))

    body = replace_body_sections(
        current_document.body,
        render_scope_decisions(reviewed_tree),
        ignore_fenced_code=True,
    )
    try:
        final_plan_text = render_plan_text(updated_plan, body)
        fingerprint = _fingerprint(path, final_plan_text.encode("utf-8"))
        final_tree = replace(copy.deepcopy(reviewed_tree), plan_fingerprint=fingerprint)
        _validate_tree(final_tree)
        final_sidecar_text = json.dumps(asdict(final_tree), indent=2, allow_nan=False) + "\n"
    except (InvalidConceptTreeError, ValueError, TypeError) as exc:
        return ConceptSyncResult(SyncStatus.INVALID_STATE, str(exc))

    published: list[Path] = []
    try:
        publish(sidecar, final_sidecar_text)
        published.append(sidecar)
        publish(path, final_plan_text)
        published.append(path)
    except BaseException as exc:
        rollback_errors: list[str] = []
        for target, old in ((path, current_plan_text), (sidecar, current_sidecar_text)):
            if target not in published:
                continue
            try:
                _restore(target, old, publish)
            except BaseException as rollback_exc:
                rollback_errors.append(f"{target}: {rollback_exc}")
        if path in published and not rollback_errors:
            refresh_plan_provenance(path, current_plan_text)
        return ConceptSyncResult(
            SyncStatus.PUBLICATION_FAILURE, str(exc),
            rollback_error="; ".join(rollback_errors) or None,
        )

    refresh_plan_provenance(path, final_plan_text)
    return ConceptSyncResult(SyncStatus.SUCCESS, plan_fingerprint=fingerprint)
