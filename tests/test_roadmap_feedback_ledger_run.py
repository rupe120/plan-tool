"""Focused behavior tests for guarded mutable ledger operations."""

from __future__ import annotations

import hashlib

import pytest

from plan_tool import roadmap_candidate_run
from plan_tool import roadmap_feedback_ledger_run as ledger_run
from plan_tool.roadmap_candidate_context import build_candidate_context
from plan_tool.roadmap import STAGES
from plan_tool.roadmap_artifacts import (
    ComponentsArtifact,
    ConstraintsArtifact,
    DomainArtifact,
    EntityRow,
    FeedbackTargetKind,
    PlansArtifact,
)
from plan_tool.roadmap_feedback_ledger import (
    LEGACY_BLANK_REQUEST_MARKER, LedgerState, LedgerTarget, LegacyFeedbackSource,
    ProposalFields,
    ReviewerFeedbackGroup, ReviewerFeedbackItem, ReviewerItemState, RoadmapFeedbackLedger,
    RoadmapFeedbackLedgerError,
    eligible_reviewer_items, load_ledger, render_ledger,
    roadmap_feedback_ledger_path, target_fingerprint,
)
from plan_tool.roadmap_revision_publish import publish_roadmap_generation, roadmap_writer_guard
from plan_tool.roadmap_versions import (
    PreparedRoadmapVersion, RoadmapVersionContent, build_root_enrollment_generation,
    create_root_version, load_accepted_version, version_namespace_path,
)


_VERSION_A = "a" * 64
_VERSION_B = "b" * 64
_FINGERPRINT = "c" * 64


def _item(item_id: str, *, version: str = _VERSION_A, state: ReviewerItemState = ReviewerItemState.OPEN):
    return ReviewerFeedbackItem(
        item_id=item_id,
        target=LedgerTarget(artifact_key="domain", kind=FeedbackTargetKind.ARTIFACT),
        request="Clarify this boundary.", state=state,
        submitted_against_version_id=version, target_fingerprint=_FINGERPRINT,
        proposal=None if state is ReviewerItemState.CLOSED else ProposalFields(response="Live proposal."),
    )


def _ledger(*items: ReviewerFeedbackItem) -> RoadmapFeedbackLedger:
    return RoadmapFeedbackLedger(
        schema_version=1, roadmap_slug="ledger-run", ledger_state=LedgerState.LEDGER_NATIVE,
        reviewer_feedback_groups=(ReviewerFeedbackGroup(predecessor_version_id=_VERSION_A, items=items),),
        derived_context=(),
    )


def test_request_or_target_edit_reopens_and_clears_live_proposal():
    original = _item("review-1", state=ReviewerItemState.DEFERRED)
    edited = ledger_run.edit_reviewer_item(original, request="Use the explicit boundary.")

    assert edited.state is ReviewerItemState.OPEN
    assert edited.proposal is None
    assert edited.item_id == original.item_id


def test_close_retains_identity_and_clears_live_proposal():
    closed = ledger_run.close_reviewer_item(_item("review-1"))

    assert closed.item_id == "review-1"
    assert closed.state is ReviewerItemState.CLOSED
    assert closed.proposal is None


def test_retarget_grouping_preserves_identity_and_moves_item_to_new_predecessor():
    original = _item("review-1")
    retargeted = original.model_copy(update={"submitted_against_version_id": _VERSION_B})
    groups = ledger_run._groups_for_items((retargeted,), existing=_ledger(original).reviewer_feedback_groups)

    assert groups == (ReviewerFeedbackGroup(predecessor_version_id=_VERSION_B, items=(retargeted,)),)
    assert groups[0].items[0].item_id == original.item_id


def test_grouped_render_orders_current_processing_pair_before_stable_history(monkeypatch, tmp_path):
    current, historical = _item("current", version=_VERSION_B), _item("history")
    ledger = RoadmapFeedbackLedger(
        schema_version=1, roadmap_slug="ledger-run", ledger_state=LedgerState.LEDGER_NATIVE,
        reviewer_feedback_groups=(
            ReviewerFeedbackGroup(predecessor_version_id=_VERSION_A, items=(historical,)),
            ReviewerFeedbackGroup(predecessor_version_id=_VERSION_B, items=(current,)),
        ), derived_context=(),
    )
    monkeypatch.setattr(ledger_run, "load_ledger", lambda *_a, **_k: ledger)
    monkeypatch.setattr(ledger_run, "_processing_source", lambda *_a: type("Source", (), {"record": type("Record", (), {"version_id": _VERSION_B})()})())

    sections = ledger_run.render_predecessor_groups(plans_dir=tmp_path, slug="ledger-run")

    assert [section.predecessor_version_id for section in sections] == [_VERSION_B, _VERSION_A]
    assert sections[0].current_processing_pair is True


_ROW_TARGET = LedgerTarget(artifact_key="domain", kind=FeedbackTargetKind.ROW, row_id="entity-order")
_ARTIFACT_TARGET = LedgerTarget(artifact_key="domain", kind=FeedbackTargetKind.ARTIFACT)
_SLUG = "legacy"


def _root_artifacts():
    """The four feedback-free artifacts an immutable root stores."""
    return (
        DomainArtifact(
            entities=(EntityRow("entity-order", "Order", ()),),
            business_rules=(), workflows=(), decisions=(), body="# Domain\n",
            feedback=(), removals=(),
        ),
        ConstraintsArtifact(
            dispositions=(), constraints=(), decisions=(), body="constraints\n",
            hosting=(), feedback=(),
        ),
        ComponentsArtifact(
            system_patterns=(), component_patterns=(), components=(), decisions=(),
            body="components\n", stores=(), feedback=(),
        ),
        PlansArtifact(plans=(), ordering=(), assumptions=(), decisions=(), body="plans\n", feedback=()),
    )


def _legacy_source_item(
    accepted, item_id: str, *, request: str, state: ReviewerItemState, proposal: ProposalFields | None = None,
) -> ReviewerFeedbackItem:
    """One ledger item that records the embedded row it was imported from."""
    return ReviewerFeedbackItem(
        item_id=item_id, target=_ROW_TARGET, request=request, state=state,
        submitted_against_version_id=accepted.record.version_id,
        target_fingerprint=target_fingerprint(accepted, _ROW_TARGET), proposal=proposal,
        legacy_source=LegacyFeedbackSource(artifact_key="domain", feedback_id=item_id),
    )


def _native_roadmap(plans_dir, slug: str = _SLUG, *, items=None):
    """A ledger-native roadmap: an immutable root plus a ledger of reviewer items.

    The default items are an answered one (``fb-answered``) and an open one (``fb-open``).
    Returns the ledger path.
    """
    rendered = tuple(
        stage.render(artifact).encode("utf-8")
        for stage, artifact in zip(STAGES, _root_artifacts(), strict=True)
    )
    brief = b"Recorded brief\n"
    root = PreparedRoadmapVersion(
        record=create_root_version(
            roadmap_slug=slug,
            brief_digest=hashlib.sha256(brief).hexdigest(),
            artifact_digests=tuple(hashlib.sha256(data).hexdigest() for data in rendered),
        ),
        content=RoadmapVersionContent(brief_bytes=brief, artifact_bytes=rendered),
    )
    with roadmap_writer_guard(plans_dir, slug) as token:
        publish_roadmap_generation(
            build_root_enrollment_generation(root, plans_dir=plans_dir, slug=slug),
            plans_dir=plans_dir, slug=slug, writer_token=token,
        )
    accepted = load_accepted_version(plans_dir=plans_dir, slug=slug)
    if items is None:
        items = (
            _legacy_source_item(
                accepted, "fb-answered", request="Rename it.", state=ReviewerItemState.AWAITING_REVIEW,
                proposal=ProposalFields(response="Call it a customer order."),
            ),
            _legacy_source_item(
                accepted, "fb-open", request="Also confirm the id.", state=ReviewerItemState.OPEN,
            ),
        )
    ledger = RoadmapFeedbackLedger(
        schema_version=1, roadmap_slug=slug, ledger_state=LedgerState.LEDGER_NATIVE,
        reviewer_feedback_groups=(
            ReviewerFeedbackGroup(predecessor_version_id=accepted.record.version_id, items=tuple(items)),
        ),
        derived_context=(),
    )
    path = roadmap_feedback_ledger_path(plans_dir, slug)
    path.write_bytes(render_ledger(ledger))
    return path


def _tree(directory) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def _reviewer_actions(slug: str, plans_dir):
    base = {"plans_dir": plans_dir, "slug": slug}
    return {
        "submit": lambda: ledger_run.submit_reviewer_feedback(
            **base, item_id="new-item", target=_ROW_TARGET, request="One more."),
        "edit": lambda: ledger_run.edit_reviewer_feedback(**base, item_id="fb-open", request="Reworded."),
        "retarget": lambda: ledger_run.retarget_reviewer_feedback(
            **base, item_id="fb-open", target=_ARTIFACT_TARGET),
        "defer": lambda: ledger_run.defer_reviewer_feedback(**base, item_id="fb-open"),
        "close": lambda: ledger_run.close_reviewer_feedback(**base, item_id="fb-open"),
        "reopen": lambda: ledger_run.reopen_reviewer_feedback(**base, item_id="fb-answered"),
    }


def _publish_after_writing(monkeypatch, path, data: bytes) -> None:
    """Land a reviewer's hand edit after the action loaded the ledger but before it publishes."""
    real_publish = ledger_run.publish_roadmap_generation

    def publish_after_the_edit(generation, **kwargs):
        path.write_bytes(data)
        return real_publish(generation, **kwargs)

    monkeypatch.setattr(ledger_run, "publish_roadmap_generation", publish_after_the_edit)


def test_a_hand_edit_landing_between_load_and_publication_refuses_the_action_and_keeps_the_edit(
    tmp_path, monkeypatch
):
    """publish_roadmap_generation never compares a member's old bytes with the file, so the
    action must, or a reviewer's edit made in that window is silently overwritten."""
    path = _native_roadmap(tmp_path)
    accepted = load_accepted_version(plans_dir=tmp_path, slug=_SLUG)
    hand_added = ledger_run._append_item(
        load_ledger(path),
        ReviewerFeedbackItem(
            item_id="hand-added", target=_ROW_TARGET, request="Added by hand.",
            state=ReviewerItemState.OPEN, submitted_against_version_id=accepted.record.version_id,
            target_fingerprint=target_fingerprint(accepted, _ROW_TARGET),
        ),
    )
    hand_bytes = render_ledger(hand_added)
    _publish_after_writing(monkeypatch, path, hand_bytes)

    with pytest.raises(ledger_run.RoadmapFeedbackLedgerRunError, match="changed before publication"):
        _reviewer_actions(_SLUG, tmp_path)["submit"]()

    assert path.read_bytes() == hand_bytes


@pytest.mark.parametrize("action", ("submit", "edit", "retarget", "defer", "close", "reopen"))
def test_every_reviewer_action_refuses_a_removed_migration_pending_ledger_without_writing(tmp_path, action):
    """The pre-ledger migration state is no longer modelled: a ledger file that still names it
    fails on read with the successor-slug remedy, and no action rewrites it."""
    path = _native_roadmap(tmp_path)
    path.write_text(
        path.read_text(encoding="utf-8").replace("ledger-native", "migration-pending"), encoding="utf-8"
    )
    before = path.read_bytes()

    with pytest.raises(RoadmapFeedbackLedgerError, match="successor slug"):
        _reviewer_actions(_SLUG, tmp_path)[action]()

    assert path.read_bytes() == before


def test_reviewer_actions_refuse_a_changed_processing_pair_without_writing(tmp_path):
    """An active pointer bound to another root means the pair the item would be checked against moved."""
    path = _native_roadmap(tmp_path)
    pointer = roadmap_candidate_run.CandidateProposalAdmission(
        schema_version=1, roadmap_slug=_SLUG, predecessor_version_id="9" * 64,
        expansion_available=False, candidate_version_id="8" * 64,
        root_version_id="9" * 64, active_candidate_version_id="8" * 64,
    )
    pointer_path = roadmap_candidate_run.candidate_admission_path(tmp_path, _SLUG)
    pointer_path.write_bytes(roadmap_candidate_run.render_candidate_admission(pointer))
    before = path.read_bytes()

    with pytest.raises(ledger_run.RoadmapFeedbackLedgerRunError, match="candidate processing pair changed"):
        _reviewer_actions(_SLUG, tmp_path)["submit"]()

    assert path.read_bytes() == before


def test_submit_and_retarget_bind_the_item_to_the_processing_source_and_move_its_group(tmp_path):
    path = _native_roadmap(tmp_path)
    accepted = load_accepted_version(plans_dir=tmp_path, slug=_SLUG)

    _reviewer_actions(_SLUG, tmp_path)["submit"]()
    submitted = {
        item.item_id: (group.predecessor_version_id, item)
        for group in load_ledger(path).reviewer_feedback_groups for item in group.items
    }
    version, item = submitted["new-item"]
    assert version == accepted.record.version_id == item.submitted_against_version_id
    assert item.target_fingerprint == target_fingerprint(accepted, _ROW_TARGET)
    assert item.state is ReviewerItemState.OPEN

    _reviewer_actions(_SLUG, tmp_path)["retarget"]()
    retargeted = next(
        item for group in load_ledger(path).reviewer_feedback_groups
        for item in group.items if item.item_id == "fb-open"
    )
    assert retargeted.target == _ARTIFACT_TARGET
    assert retargeted.target_fingerprint == target_fingerprint(accepted, _ARTIFACT_TARGET)
    assert retargeted.submitted_against_version_id == accepted.record.version_id


@pytest.mark.parametrize("action", ("submit", "edit", "retarget", "defer", "close", "reopen"))
def test_a_reviewer_action_changes_only_the_ledger_and_no_immutable_state(tmp_path, action):
    ledger_path = _native_roadmap(tmp_path)
    roadmap_root = version_namespace_path(tmp_path, _SLUG).parent
    before = _tree(roadmap_root)

    result = _reviewer_actions(_SLUG, tmp_path)[action]()

    assert result.result == "updated"
    after = _tree(roadmap_root)
    changed = {name for name in before.keys() | after.keys() if before.get(name) != after.get(name)}
    assert changed == {ledger_path.relative_to(roadmap_root).as_posix()}


# --- the blank-request marker an imported item may still carry ---


def _blank_marker_roadmap(plans_dir, *, with_control: bool = True):
    """A ledger whose ``fb-blank`` item is closed, carries the marker, and records its source."""
    root_only = _native_roadmap(plans_dir, items=())
    accepted = load_accepted_version(plans_dir=plans_dir, slug=_SLUG)
    items = [
        _legacy_source_item(
            accepted, "fb-blank", request=LEGACY_BLANK_REQUEST_MARKER, state=ReviewerItemState.CLOSED,
        )
    ]
    if with_control:
        items.append(
            _legacy_source_item(
                accepted, "fb-control", request="Keep this eligible.", state=ReviewerItemState.OPEN,
                proposal=None,
            )
        )
    ledger = load_ledger(root_only)
    group = ledger.reviewer_feedback_groups[0].model_copy(update={"items": tuple(items)})
    root_only.write_bytes(render_ledger(ledger.model_copy(update={"reviewer_feedback_groups": (group,)})))
    return root_only


@pytest.mark.parametrize("act", ["reopen", "edit-target-only", "retarget"])
def test_a_blank_request_marker_item_cannot_leave_closed_without_new_request_text(tmp_path, act):
    """Invariant: the tool never makes the marker reviewer text. Reopen, and the target-only edit and retarget
    (which also force ``open``), refuse rather than make the marker the request a model sees."""
    path = _blank_marker_roadmap(tmp_path)
    before = path.read_bytes()
    base = {"plans_dir": tmp_path, "slug": _SLUG, "item_id": "fb-blank"}
    action = {
        "reopen": lambda: ledger_run.reopen_reviewer_feedback(**base),
        "edit-target-only": lambda: ledger_run.edit_reviewer_feedback(**base, target=_ARTIFACT_TARGET),
        "retarget": lambda: ledger_run.retarget_reviewer_feedback(**base, target=_ARTIFACT_TARGET),
    }[act]

    with pytest.raises(RoadmapFeedbackLedgerError, match="needs non-blank request text before it can be open") as refusal:
        action()

    message = str(refusal.value)
    assert "'fb-blank'" in message
    for pydantic_residue in ("validation error", "input_value", "errors.pydantic.dev"):
        assert pydantic_residue not in message
    assert path.read_bytes() == before


@pytest.mark.parametrize("blank_edit", ["   ", "\n\t "], ids=["spaces", "mixed-whitespace"])
def test_an_edit_that_supplies_only_whitespace_cannot_open_a_blank_request_marker_item(tmp_path, blank_edit):
    """The predicate for no request text is ``not request.strip()``, so an edit that
    swaps the marker for whitespace must refuse too rather than open an item with a blank request."""
    path = _blank_marker_roadmap(tmp_path)
    before = path.read_bytes()

    with pytest.raises(RoadmapFeedbackLedgerError, match="non-blank request text"):
        ledger_run.edit_reviewer_feedback(plans_dir=tmp_path, slug=_SLUG, item_id="fb-blank", request=blank_edit)

    assert path.read_bytes() == before


@pytest.mark.parametrize("item_id", ["fb-blank", "fb-control"], ids=["marker-item", "item-with-real-text"])
@pytest.mark.parametrize("blank_edit", ["", "   "], ids=["empty", "spaces"])
def test_a_blank_edit_cannot_open_any_imported_item_and_refuses_with_the_named_error(tmp_path, item_id, blank_edit):
    """Scope pin: the rule covers every imported item, not only the marker item, and an empty
    edit gets the same named refusal as whitespace rather than the schema's validation dump."""
    path = _blank_marker_roadmap(tmp_path)
    before = path.read_bytes()

    with pytest.raises(RoadmapFeedbackLedgerError, match="would have no request text") as refusal:
        ledger_run.edit_reviewer_feedback(plans_dir=tmp_path, slug=_SLUG, item_id=item_id, request=blank_edit)

    message = str(refusal.value)
    assert f"'{item_id}'" in message
    for pydantic_residue in ("validation error", "input_value", "errors.pydantic.dev"):
        assert pydantic_residue not in message
    assert path.read_bytes() == before


def test_a_blank_request_marker_item_becomes_eligible_once_a_reviewer_supplies_request_text(tmp_path):
    """The exit the refusal names: an edit that supplies text replaces the marker, keeps the
    source, and makes the item a real reviewer request."""
    path = _blank_marker_roadmap(tmp_path)

    ledger_run.edit_reviewer_feedback(plans_dir=tmp_path, slug=_SLUG, item_id="fb-blank", request="Now say it.")

    ledger = load_ledger(path)
    root = load_accepted_version(plans_dir=tmp_path, slug=_SLUG)
    items = {item.item_id: item for group in ledger.reviewer_feedback_groups for item in group.items}
    assert items["fb-blank"].request == "Now say it." and items["fb-blank"].state is ReviewerItemState.OPEN
    assert items["fb-blank"].legacy_source == LegacyFeedbackSource(artifact_key="domain", feedback_id="fb-blank")
    assert "fb-blank" in [item.item_id for item in eligible_reviewer_items(ledger, root)]


def test_a_marker_item_hand_edited_to_open_still_loads_and_the_named_exit_still_runs(tmp_path):
    """The guard is at the actions, not in the schema: a loaded ledger always parses, so a hand
    edit never leaves the roadmap unable to run the edit that supplies request text."""
    path = _blank_marker_roadmap(tmp_path)
    ledger = load_ledger(path)
    groups = tuple(
        group.model_copy(update={"items": tuple(
            item.model_copy(update={"state": ReviewerItemState.OPEN}) if item.item_id == "fb-blank" else item
            for item in group.items
        )})
        for group in ledger.reviewer_feedback_groups
    )
    path.write_bytes(render_ledger(ledger.model_copy(update={"reviewer_feedback_groups": groups})))

    reloaded = {item.item_id: item for group in load_ledger(path).reviewer_feedback_groups for item in group.items}
    assert reloaded["fb-blank"].state is ReviewerItemState.OPEN

    ledger_run.edit_reviewer_feedback(plans_dir=tmp_path, slug=_SLUG, item_id="fb-blank", request="Now say it.")

    fixed = {item.item_id: item for group in load_ledger(path).reviewer_feedback_groups for item in group.items}
    assert fixed["fb-blank"].request == "Now say it."


def test_a_native_item_whose_own_words_equal_the_marker_text_can_still_be_reopened(tmp_path):
    """Carve-out: the refusal keys on the marker and a ``legacy_source``, so a reviewer who
    wrote that exact sentence themselves keeps an ordinary item."""
    _blank_marker_roadmap(tmp_path)
    base = {"plans_dir": tmp_path, "slug": _SLUG}
    ledger_run.submit_reviewer_feedback(
        **base, item_id="native-marker", target=_ARTIFACT_TARGET, request=LEGACY_BLANK_REQUEST_MARKER
    )
    ledger_run.close_reviewer_feedback(**base, item_id="native-marker")

    result = ledger_run.reopen_reviewer_feedback(**base, item_id="native-marker")

    assert result.result == "updated"


def test_a_ledger_holding_only_a_blank_request_item_has_no_batch_work(tmp_path):
    path = _blank_marker_roadmap(tmp_path, with_control=False)
    ledger = load_ledger(path)
    root = load_accepted_version(plans_dir=tmp_path, slug=_SLUG)

    outcome = build_candidate_context(root, None, ledger)

    assert outcome.capsule is None and outcome.no_work is not None


def test_a_blank_request_marker_never_reaches_a_batch_context(tmp_path):
    path = _blank_marker_roadmap(tmp_path)
    ledger = load_ledger(path)
    root = load_accepted_version(plans_dir=tmp_path, slug=_SLUG)

    capsule = build_candidate_context(root, None, ledger).capsule

    assert capsule is not None
    assert LEGACY_BLANK_REQUEST_MARKER not in capsule.model_dump_json()


def test_an_imported_item_keeps_its_source_through_every_reviewer_action_and_a_native_item_has_none(tmp_path):
    path = _native_roadmap(tmp_path)
    ledger_run.submit_reviewer_feedback(
        plans_dir=tmp_path, slug=_SLUG, item_id="native-1", target=_ARTIFACT_TARGET, request="Clarify."
    )
    ledger_run.defer_reviewer_feedback(plans_dir=tmp_path, slug=_SLUG, item_id="fb-open")
    ledger_run.edit_reviewer_feedback(plans_dir=tmp_path, slug=_SLUG, item_id="fb-answered", request="Reworded.")
    ledger_run.retarget_reviewer_feedback(plans_dir=tmp_path, slug=_SLUG, item_id="fb-open", target=_ARTIFACT_TARGET)
    ledger_run.close_reviewer_feedback(plans_dir=tmp_path, slug=_SLUG, item_id="fb-answered")

    ledger = load_ledger(path)
    items = {item.item_id: item for group in ledger.reviewer_feedback_groups for item in group.items}
    assert items["fb-open"].legacy_source == LegacyFeedbackSource(artifact_key="domain", feedback_id="fb-open")
    assert items["fb-answered"].legacy_source == LegacyFeedbackSource(artifact_key="domain", feedback_id="fb-answered")
    assert items["native-1"].legacy_source is None
    assert b"legacy_source: null" in path.read_bytes()
