"""Guarded reviewer mutations of the feedback ledger."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from plan_tool.roadmap_candidate_run import load_candidate_admission
from plan_tool.roadmap_feedback_ledger import (
    LedgerTarget, ReviewerFeedbackGroup,
    ReviewerFeedbackItem, ReviewerItemState, RoadmapFeedbackLedger,
    close_reviewer_item, defer_reviewer_item,
    edit_reviewer_item, load_ledger, render_ledger, reopen_reviewer_item,
    roadmap_feedback_ledger_path, target_fingerprint,
)
from plan_tool.roadmap_revision_publish import (
    RoadmapRevisionPublishError, RoadmapWriterGuardError, publish_roadmap_generation,
    roadmap_writer_guard,
)
from plan_tool.roadmap_source_identity import GenerationMember, PendingGeneration
from plan_tool.roadmap_versions import (
    ResolvedRoadmapVersion, RoadmapVersionError, load_accepted_version,
    load_resolved_stored_version,
)


class RoadmapFeedbackLedgerRunError(ValueError):
    """A ledger action cannot safely change the reviewer-owned ledger."""


@dataclass(frozen=True)
class LedgerActionResult:
    """The durable outcome of one ledger action."""

    result: Literal["updated"]
    ledger: RoadmapFeedbackLedger | None = None


@dataclass(frozen=True)
class PredecessorLedgerSection:
    """One display section, ordered independently from persisted group order."""

    predecessor_version_id: str
    items: tuple[ReviewerFeedbackItem, ...]
    current_processing_pair: bool


def submit_reviewer_feedback(*, plans_dir: Path, slug: str, item_id: str, target: LedgerTarget,
                             request: str) -> LedgerActionResult:
    """Append one reviewer-created item bound to the current processing source."""
    return _mutate(plans_dir, slug, lambda ledger, source: _append_item(
        ledger, ReviewerFeedbackItem(item_id=item_id, target=target, request=request,
        state=ReviewerItemState.OPEN, submitted_against_version_id=source.record.version_id,
        target_fingerprint=target_fingerprint(source, target))))


def retarget_reviewer_feedback(*, plans_dir: Path, slug: str, item_id: str,
                               target: LedgerTarget) -> LedgerActionResult:
    """Move an existing item to the current predecessor without changing its id."""
    def change(item: ReviewerFeedbackItem, source: ResolvedRoadmapVersion) -> ReviewerFeedbackItem:
        edited = edit_reviewer_item(item, target=target)
        return edited.model_copy(update={"submitted_against_version_id": source.record.version_id,
                                         "target_fingerprint": target_fingerprint(source, target)})
    return _mutate_item(plans_dir, slug, item_id, change)


def edit_reviewer_feedback(*, plans_dir: Path, slug: str, item_id: str,
                           request: str | None = None, target: LedgerTarget | None = None) -> LedgerActionResult:
    """Edit request or target; target edits are rebound to the processing source."""
    if request is None and target is None:
        raise RoadmapFeedbackLedgerRunError("reviewer edit requires a request or target")
    def change(item: ReviewerFeedbackItem, source: ResolvedRoadmapVersion) -> ReviewerFeedbackItem:
        edited = edit_reviewer_item(item, request=request, target=target)
        if target is None:
            return edited
        return edited.model_copy(update={"submitted_against_version_id": source.record.version_id,
                                         "target_fingerprint": target_fingerprint(source, target)})
    return _mutate_item(plans_dir, slug, item_id, change)


def defer_reviewer_feedback(*, plans_dir: Path, slug: str, item_id: str) -> LedgerActionResult:
    return _mutate_item(plans_dir, slug, item_id, lambda item, _source: defer_reviewer_item(item))


def close_reviewer_feedback(*, plans_dir: Path, slug: str, item_id: str) -> LedgerActionResult:
    return _mutate_item(plans_dir, slug, item_id, lambda item, _source: close_reviewer_item(item))


def reopen_reviewer_feedback(*, plans_dir: Path, slug: str, item_id: str) -> LedgerActionResult:
    return _mutate_item(plans_dir, slug, item_id, lambda item, _source: reopen_reviewer_item(item))


def render_predecessor_groups(*, plans_dir: Path, slug: str) -> tuple[PredecessorLedgerSection, ...]:
    """Return current processing source first, followed by stable historical groups."""
    ledger = load_ledger(roadmap_feedback_ledger_path(plans_dir, slug))
    current = _processing_source(plans_dir, slug).record.version_id
    groups = {group.predecessor_version_id: group.items for group in ledger.reviewer_feedback_groups}
    ordered = [current, *sorted(key for key in groups if key != current)]
    return tuple(PredecessorLedgerSection(key, groups.get(key, ()), key == current) for key in ordered)


def _mutate_item(plans_dir: Path, slug: str, item_id: str, change):
    return _mutate(plans_dir, slug, lambda ledger, source: _replace_item(ledger, item_id, change, source))


def _mutate(plans_dir: Path, slug: str, change) -> LedgerActionResult:
    path = roadmap_feedback_ledger_path(plans_dir, slug)
    with roadmap_writer_guard(plans_dir, slug) as token:
        ledger = load_ledger(path)
        source = _processing_source(plans_dir, slug)
        updated = change(ledger, source)
        _publish_ledger(path, ledger, updated, plans_dir, slug, token, "feedback-ledger-edit")
        return LedgerActionResult("updated", updated)


def _publish_ledger(path, old, new, plans_dir, slug, token, kind, recheck=None) -> None:
    root = path.parent
    old_bytes = render_ledger(old)
    generation = PendingGeneration(kind=kind, members=(GenerationMember(path.relative_to(root).as_posix(), old_bytes, render_ledger(new)),))

    def before_replace() -> None:
        # publish_roadmap_generation never compares a member's old bytes with the file, so a
        # reviewer's hand edit made since this ledger was loaded is only caught here.
        if path.read_bytes() != old_bytes:
            raise RoadmapFeedbackLedgerRunError("feedback ledger changed before publication")
        if recheck is not None:
            recheck()

    try:
        publish_roadmap_generation(generation, plans_dir=plans_dir, slug=slug, writer_token=token, before_replace=before_replace)
    except (OSError, RoadmapRevisionPublishError, RoadmapWriterGuardError) as exc:
        raise RoadmapFeedbackLedgerRunError(str(exc)) from exc


def _append_item(ledger: RoadmapFeedbackLedger, item: ReviewerFeedbackItem) -> RoadmapFeedbackLedger:
    if any(old.item_id == item.item_id for group in ledger.reviewer_feedback_groups for old in group.items):
        raise RoadmapFeedbackLedgerRunError("reviewer item id already exists")
    return ledger.model_copy(update={"reviewer_feedback_groups": _groups_for_items(
        (*_all_items(ledger), item), existing=ledger.reviewer_feedback_groups)})


def _replace_item(ledger, item_id, change, source):
    items = list(_all_items(ledger))
    for index, item in enumerate(items):
        if item.item_id == item_id:
            items[index] = change(item, source)
            return ledger.model_copy(update={"reviewer_feedback_groups": _groups_for_items(items, existing=ledger.reviewer_feedback_groups)})
    raise RoadmapFeedbackLedgerRunError("reviewer item does not exist")


def _all_items(ledger):
    return tuple(item for group in ledger.reviewer_feedback_groups for item in group.items)


def _groups_for_items(items, *, existing=()):
    order = [group.predecessor_version_id for group in existing]
    grouped = {}
    for item in items:
        grouped.setdefault(item.submitted_against_version_id, []).append(item)
        if item.submitted_against_version_id not in order:
            order.append(item.submitted_against_version_id)
    return tuple(ReviewerFeedbackGroup(predecessor_version_id=key, items=tuple(grouped[key])) for key in order if key in grouped)


def _accepted_root(plans_dir: Path, slug: str) -> ResolvedRoadmapVersion:
    root = load_accepted_version(plans_dir=plans_dir, slug=slug)
    if root is None:
        raise RoadmapFeedbackLedgerRunError("roadmap has no accepted immutable predecessor")
    return root


def _processing_source(plans_dir: Path, slug: str) -> ResolvedRoadmapVersion:
    root = _accepted_root(plans_dir, slug)
    admission = load_candidate_admission(plans_dir=plans_dir, slug=slug)
    if admission is None or admission.active_candidate_version_id is None:
        return root
    if admission.root_version_id != root.record.version_id:
        raise RoadmapFeedbackLedgerRunError("candidate processing pair changed")
    try:
        return load_resolved_stored_version(plans_dir=plans_dir, slug=slug, version_id=admission.active_candidate_version_id)
    except RoadmapVersionError as exc:
        raise RoadmapFeedbackLedgerRunError("active candidate is unreadable") from exc

