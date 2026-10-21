"""Focused contract tests for reviewer-owned roadmap feedback ledgers."""

from __future__ import annotations

import hashlib

import pytest

import plan_tool.roadmap_feedback_ledger as ledger_module
from plan_tool.roadmap_artifacts import (
    DomainArtifact,
    EntityRow,
    FeedbackRow,
    FeedbackState,
    FeedbackTarget,
    FeedbackTargetKind,
    render_domain_artifact,
)
from plan_tool.roadmap_feedback_ledger import (
    DerivedFeedbackContext,
    LedgerState,
    LedgerTarget,
    LegacyFeedbackSource,
    ProposalFields,
    ReviewerFeedbackGroup,
    ReviewerFeedbackItem,
    ReviewerItemState,
    RoadmapFeedbackLedger,
    RoadmapFeedbackLedgerError,
    close_reviewer_item,
    defer_reviewer_item,
    edit_reviewer_item,
    eligible_reviewer_items,
    item_snapshot,
    ledger_digest,
    load_ledger,
    parse_ledger,
    render_ledger,
    reopen_reviewer_item,
    roadmap_feedback_ledger_path,
    target_fingerprint,
    unresolved_target_fingerprint,
)
from plan_tool.roadmap_versions import ResolvedRoadmapVersion, create_root_version


_VERSION = "a" * 64
_FINGERPRINT = "b" * 64


def _item(*, item_id: str = "review-1", state: ReviewerItemState = ReviewerItemState.OPEN):
    return ReviewerFeedbackItem(
        item_id=item_id,
        target=LedgerTarget(artifact_key="domain", kind=FeedbackTargetKind.ARTIFACT),
        request="Clarify the domain boundary.",
        state=state,
        submitted_against_version_id=_VERSION,
        target_fingerprint=_FINGERPRINT,
        proposal=ProposalFields(response="A live proposal.") if state is not ReviewerItemState.CLOSED else None,
    )


def _ledger(*, items=(), state=LedgerState.LEDGER_NATIVE, derived_context=()):
    return RoadmapFeedbackLedger(
        schema_version=1,
        roadmap_slug="feedback-ledger",
        ledger_state=state,
        reviewer_feedback_groups=(
            ReviewerFeedbackGroup(predecessor_version_id=_VERSION, items=tuple(items)),
        ),
        derived_context=tuple(derived_context),
    )


def test_ledger_round_trips_through_one_closed_canonical_schema():
    ledger = _ledger(items=(_item(),))

    assert parse_ledger(render_ledger(ledger).decode("utf-8")) == ledger
    with pytest.raises(RoadmapFeedbackLedgerError, match="malformed"):
        parse_ledger(render_ledger(ledger).decode("utf-8") + "unexpected: value\n")


def test_ledger_rejects_noncanonical_serialization():
    text = render_ledger(_ledger(items=(_item(),))).decode("utf-8")

    with pytest.raises(RoadmapFeedbackLedgerError, match="canonical"):
        parse_ledger("\n" + text)


def test_ledger_digest_is_stable_for_unchanged_canonical_bytes():
    assert ledger_digest(_ledger(items=(_item(),))) == ledger_digest(_ledger(items=(_item(),)))


def test_proposal_names_the_candidate_that_produced_it_or_explicitly_none():
    """A bound proposal carries its stored candidate; ``None`` marks one no stored
    candidate produced (migrated from a legacy embedded row) and renders explicitly."""
    bound = ProposalFields(response="Rename it.", candidate_version_id=_VERSION)
    unbound = ProposalFields(response="Rename it.")

    rendered = render_ledger(_ledger(items=(_item().model_copy(update={"proposal": bound}),))).decode()
    assert f"candidate_version_id: {_VERSION}" in rendered
    assert parse_ledger(rendered).reviewer_feedback_groups[0].items[0].proposal == bound
    unbound_rendered = render_ledger(
        _ledger(items=(_item().model_copy(update={"proposal": unbound}),))
    ).decode()
    assert "candidate_version_id: null" in unbound_rendered
    assert parse_ledger(unbound_rendered).reviewer_feedback_groups[0].items[0].proposal == unbound
    for invalid in ("not-a-digest", "A" * 64, ""):
        with pytest.raises(ValueError):
            ProposalFields(response="Rename it.", candidate_version_id=invalid)


def test_item_names_the_legacy_row_it_was_imported_from_or_explicitly_none():
    """A migrated item records the embedded row it came from; a reviewer-created item
    renders an explicit ``null`` so the two are told apart in place."""
    source = LegacyFeedbackSource(artifact_key="domain", feedback_id="F1")

    assert "legacy_source: null" in render_ledger(_ledger(items=(_item(),))).decode()
    migrated = render_ledger(_ledger(items=(_item().model_copy(update={"legacy_source": source}),))).decode()
    assert parse_ledger(migrated).reviewer_feedback_groups[0].items[0].legacy_source == source
    for unconfigured in ("unknown", ""):
        with pytest.raises(ValueError):
            LegacyFeedbackSource(artifact_key=unconfigured, feedback_id="F1")


def test_reviewer_item_id_survives_defer_close_reopen_and_retarget():
    item = _item()
    retargeted = edit_reviewer_item(
        reopen_reviewer_item(close_reviewer_item(defer_reviewer_item(item))),
        target=LedgerTarget(artifact_key="plans", kind=FeedbackTargetKind.ARTIFACT),
    )

    assert retargeted.item_id == item.item_id
    assert retargeted.state is ReviewerItemState.OPEN
    assert retargeted.proposal is None


def test_closing_item_clears_live_proposal_fields_and_preserves_item():
    closed = close_reviewer_item(_item())

    assert closed.state is ReviewerItemState.CLOSED
    assert closed.proposal is None
    assert closed.item_id == "review-1"


def test_editing_retained_ineligible_item_clears_proposal_and_restores_open():
    edited = edit_reviewer_item(defer_reviewer_item(_item()), request="Use another boundary.")

    assert edited.state is ReviewerItemState.OPEN
    assert edited.proposal is None
    assert edited.item_id == "review-1"


def test_target_fingerprint_binds_exact_artifact_or_row_content():
    domain = b"---\nentities:\n- id: order\n  name: Order\n  fields: []\nbusiness_rules: []\nworkflows: []\ndecisions: []\n---\n# Domain\n"
    source = _source_with_domain(domain)
    artifact = LedgerTarget(artifact_key="domain", kind=FeedbackTargetKind.ARTIFACT)
    row = LedgerTarget(artifact_key="domain", kind=FeedbackTargetKind.ROW, row_id="order")

    assert target_fingerprint(source, artifact) != target_fingerprint(source, row)
    duplicate = _source_with_domain(domain.replace(b"business_rules: []", b"business_rules:\n- id: order\n  statement: Duplicate\n  entity_ids: []"))
    with pytest.raises(RoadmapFeedbackLedgerError, match="exactly one"):
        target_fingerprint(duplicate, row)


def _domain_with_feedback_row(feedback_id: str, *, entity_id: str = "order") -> bytes:
    artifact = DomainArtifact(
        entities=(EntityRow(entity_id, "Order", ()),),
        business_rules=(),
        workflows=(),
        decisions=(),
        body="# Domain\n",
        feedback=(
            FeedbackRow(
                feedback_id,
                FeedbackTarget(FeedbackTargetKind.ROW, entity_id),
                "Rename it.",
                FeedbackState.OPEN,
            ),
        ),
    )
    return render_domain_artifact(artifact).encode("utf-8")


def test_row_target_resolves_only_design_rows_not_embedded_feedback_rows():
    """A row target must name a design row, the universe the impact-closure
    resolver treats as live. Fingerprinting an embedded feedback row would mark
    the item eligible and then refuse the whole batch as ``incomplete-closure``."""
    source = _source_with_domain(_domain_with_feedback_row("fb-order"))
    design_row = LedgerTarget(artifact_key="domain", kind=FeedbackTargetKind.ROW, row_id="order")
    feedback_row = LedgerTarget(artifact_key="domain", kind=FeedbackTargetKind.ROW, row_id="fb-order")

    assert target_fingerprint(source, design_row)
    with pytest.raises(RoadmapFeedbackLedgerError, match="exactly one"):
        target_fingerprint(source, feedback_row)


def test_embedded_feedback_row_sharing_a_design_row_id_does_not_make_the_target_ambiguous():
    source = _source_with_domain(_domain_with_feedback_row("order"))
    design_row = LedgerTarget(artifact_key="domain", kind=FeedbackTargetKind.ROW, row_id="order")

    assert target_fingerprint(source, design_row)


def test_eligible_open_item_requires_matching_predecessor_and_target_fingerprint():
    source = _source_with_domain(b"---\nentities: []\nbusiness_rules: []\nworkflows: []\ndecisions: []\n---\n# Domain\n")
    target = LedgerTarget(artifact_key="domain", kind=FeedbackTargetKind.ARTIFACT)
    item = _item().model_copy(update={"target": target, "target_fingerprint": target_fingerprint(source, target), "submitted_against_version_id": source.record.version_id})
    ledger = RoadmapFeedbackLedger(
        schema_version=1, roadmap_slug="feedback-ledger", ledger_state=LedgerState.LEDGER_NATIVE,
        reviewer_feedback_groups=(ReviewerFeedbackGroup(predecessor_version_id=source.record.version_id, items=(item,)),), derived_context=(),
    )

    assert eligible_reviewer_items(ledger, source) == (item,)
    assert eligible_reviewer_items(_ledger(items=(_item(),)), source) == ()


def test_eligibility_parses_each_artifact_once_however_many_items_target_it(monkeypatch):
    """Fingerprinting an item needs the parsed artifact, and parsing is the cost, so one
    eligibility pass must not repeat it per item; the result must not change."""
    entities = tuple(EntityRow(f"entity-{number}", "Thing", ()) for number in range(10))
    domain = DomainArtifact(entities=entities, business_rules=(), workflows=(), decisions=(), body="# Domain\n")
    source = _source_with_domain(render_domain_artifact(domain).encode("utf-8"))
    targets = tuple(
        LedgerTarget(artifact_key="domain", kind=FeedbackTargetKind.ROW, row_id=entity.id) for entity in entities
    )
    items = tuple(
        _item(item_id=f"review-{index}").model_copy(update={
            "target": target, "target_fingerprint": target_fingerprint(source, target),
            "submitted_against_version_id": source.record.version_id,
        })
        for index, target in enumerate(targets)
    )
    ledger = RoadmapFeedbackLedger(
        schema_version=1, roadmap_slug="feedback-ledger", ledger_state=LedgerState.LEDGER_NATIVE,
        reviewer_feedback_groups=(ReviewerFeedbackGroup(predecessor_version_id=source.record.version_id, items=items),),
        derived_context=(),
    )
    parses: list[str] = []
    real_parse = ledger_module.parse_domain_artifact
    monkeypatch.setattr(ledger_module, "parse_domain_artifact", lambda text: parses.append(text) or real_parse(text))

    assert eligible_reviewer_items(ledger, source) == items
    assert len(parses) == 1


def test_derived_context_is_distinct_from_reviewer_created_items():
    ledger = _ledger(derived_context=(DerivedFeedbackContext(source_version_id=_VERSION, context_id="context-1", content="Derived context."),))

    assert ledger.derived_context[0].context_id == "context-1"
    assert ledger.reviewer_feedback_groups[0].items == ()


def test_item_snapshot_ignores_unrelated_ledger_item_edit():
    first, second = _item(), _item(item_id="review-2")
    before = _ledger(items=(first, second))
    after = _ledger(items=(first, edit_reviewer_item(second, request="Changed only this item.")))

    assert item_snapshot(first) == item_snapshot(after.reviewer_feedback_groups[0].items[0])
    assert ledger_digest(before) != ledger_digest(after)


def test_item_snapshot_leaves_out_the_legacy_source_because_it_is_bookkeeping_not_model_facing_evidence():
    imported = _item().model_copy(update={"legacy_source": LegacyFeedbackSource(artifact_key="domain", feedback_id="F1")})

    assert item_snapshot(imported) == item_snapshot(_item())
    assert "legacy_source" not in item_snapshot(imported).model_dump()


def test_unresolved_target_fingerprint_requires_a_resolved_roadmap_version():
    with pytest.raises(RoadmapFeedbackLedgerError, match="resolved roadmap version"):
        unresolved_target_fingerprint(object(), LedgerTarget(artifact_key="domain", kind=FeedbackTargetKind.ARTIFACT))


def test_ledger_path_uses_resolved_plans_dir_and_safe_roadmap_slug(tmp_path):
    assert roadmap_feedback_ledger_path(tmp_path / "plans", "safe-roadmap") == tmp_path / "plans" / "roadmaps" / "safe-roadmap" / "feedback-ledger.yaml"
    with pytest.raises(ValueError):
        roadmap_feedback_ledger_path(tmp_path, "../escape")


def test_migration_pending_ledger_is_refused_with_the_successor_slug_remedy(tmp_path):
    """The removed state is recognized only to name its remedy; the file is never rewritten."""
    path = tmp_path / "feedback-ledger.yaml"
    text = render_ledger(_ledger()).decode("utf-8").replace("ledger-native", "migration-pending")
    path.write_text(text, encoding="utf-8")

    with pytest.raises(RoadmapFeedbackLedgerError, match="successor slug"):
        load_ledger(path)

    assert path.read_text(encoding="utf-8") == text
    assert [state.value for state in LedgerState] == ["ledger-native"]


def _source_with_domain(domain: bytes) -> ResolvedRoadmapVersion:
    artifacts = (domain, b"constraints", b"components", b"plans")
    record = create_root_version(
        roadmap_slug="feedback-ledger",
        brief_digest=hashlib.sha256(b"brief").hexdigest(),
        artifact_digests=tuple(hashlib.sha256(artifact).hexdigest() for artifact in artifacts),
    )
    return ResolvedRoadmapVersion(record=record, brief_bytes=b"brief", artifact_bytes=artifacts)
