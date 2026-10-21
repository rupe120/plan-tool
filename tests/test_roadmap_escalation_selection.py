"""Tests for pure receipt-safe roadmap escalation selection."""

from __future__ import annotations

import hashlib

import pytest

from plan_tool import roadmap_escalation_selection
from plan_tool.roadmap_artifacts import (
    DomainArtifact,
    EntityRow,
    FeedbackReopenRecord,
    FeedbackRow,
    FeedbackState,
    FeedbackTarget,
    FeedbackTargetKind,
    RemovalRecord,
    parse_domain_artifact,
    render_domain_artifact,
)
from plan_tool.roadmap_escalation_selection import (
    CanonicalArtifactSnapshot,
    NoncanonicalArtifactSnapshot,
    RECEIPT_REASONS,
    ReceiptSafeSelector,
    ReceiptTarget,
    UndecodableArtifactSnapshot,
    UnparsableArtifactSnapshot,
    admit_receipt_selector,
    canonical_artifact_snapshot,
    parse_receipt_reason,
    select_receipt_feedback,
)
from plan_tool.roadmap_feedback import FeedbackSelector


_SELECTOR = ReceiptSafeSelector("domain", "feedback-order")
_REASON = "row-structure"
_TARGET_ID = "entity-order"
_REOPEN_NONCE = "A" * 43


def _feedback(
    *,
    feedback_id: str = _SELECTOR.feedback_id,
    target: FeedbackTarget | None = None,
    state: FeedbackState = FeedbackState.OPEN,
    proposed_response: str | None = None,
    feedback_reopen: FeedbackReopenRecord | None = None,
) -> FeedbackRow:
    return FeedbackRow(
        id=feedback_id,
        target=target or FeedbackTarget(FeedbackTargetKind.ROW, _TARGET_ID),
        request="This prose must not enter receipt selection facts.",
        state=state,
        proposed_response=proposed_response,
        feedback_reopen=feedback_reopen,
    )


def _artifact(
    *,
    feedback: tuple[FeedbackRow, ...] = (_feedback(),),
    entities: tuple[EntityRow, ...] = (EntityRow(_TARGET_ID, "Order", ()),),
    removals: tuple[RemovalRecord, ...] = (),
) -> DomainArtifact:
    return DomainArtifact(
        entities=entities,
        business_rules=(),
        workflows=(),
        decisions=(),
        body="# Domain\n",
        feedback=feedback,
        removals=removals,
    )


def _snapshot(**kwargs: object) -> CanonicalArtifactSnapshot:
    source = render_domain_artifact(_artifact(**kwargs)).encode("utf-8")
    snapshot = canonical_artifact_snapshot(
        source, parse_domain_artifact, render_domain_artifact
    )
    assert isinstance(snapshot, CanonicalArtifactSnapshot)
    return snapshot


def _selection(**kwargs: object):
    return select_receipt_feedback(_snapshot(**kwargs), _SELECTOR, _REASON)


def test_canonical_snapshot_binds_parsed_artifact_and_digest_to_the_original_raw_bytes() -> None:
    artifact = _artifact()
    source = render_domain_artifact(artifact).encode("utf-8")

    snapshot = canonical_artifact_snapshot(
        source, parse_domain_artifact, render_domain_artifact
    )

    assert snapshot == CanonicalArtifactSnapshot(
        artifact=artifact, source_digest=hashlib.sha256(source).hexdigest()
    )


def test_canonical_snapshot_rejects_non_utf8_before_exposing_a_digest() -> None:
    snapshot = canonical_artifact_snapshot(
        b"\xff", parse_domain_artifact, render_domain_artifact
    )

    assert isinstance(snapshot, UndecodableArtifactSnapshot)
    assert vars(snapshot) == {}


def test_canonical_snapshot_retains_raw_digest_for_parse_and_render_canonicality_rejections() -> None:
    malformed = b"not an artifact"
    noncanonical = render_domain_artifact(_artifact()).replace("\n", "\r\n").encode(
        "utf-8"
    )

    malformed_snapshot = canonical_artifact_snapshot(
        malformed, parse_domain_artifact, render_domain_artifact
    )
    noncanonical_snapshot = canonical_artifact_snapshot(
        noncanonical, parse_domain_artifact, render_domain_artifact
    )

    assert malformed_snapshot == UnparsableArtifactSnapshot(
        hashlib.sha256(malformed).hexdigest()
    )
    assert noncanonical_snapshot == NoncanonicalArtifactSnapshot(
        hashlib.sha256(noncanonical).hexdigest()
    )
    assert noncanonical_snapshot.artifact == parse_domain_artifact(
        noncanonical.decode("utf-8")
    )


def test_canonical_snapshot_lets_a_real_parser_bug_propagate_instead_of_hiding_it() -> None:
    def buggy_parse(_text: str) -> DomainArtifact:
        raise AttributeError("boom")

    try:
        canonical_artifact_snapshot(b"anything", buggy_parse, render_domain_artifact)
    except AttributeError as exc:
        assert "boom" in str(exc)
    else:
        raise AssertionError("a real parser bug must not be reclassified as unparsable")


def test_canonical_snapshot_lets_a_real_renderer_bug_propagate_instead_of_hiding_it() -> None:
    def buggy_render(_artifact: DomainArtifact) -> str:
        raise AttributeError("boom")

    source = render_domain_artifact(_artifact()).encode("utf-8")
    try:
        canonical_artifact_snapshot(source, parse_domain_artifact, buggy_render)
    except AttributeError as exc:
        assert "boom" in str(exc)
    else:
        raise AssertionError("a real renderer bug must not be silently swallowed")


def test_canonical_snapshot_rejects_crlf_without_normalizing_source_bytes() -> None:
    source = render_domain_artifact(_artifact()).replace("\n", "\r\n").encode("utf-8")

    snapshot = canonical_artifact_snapshot(
        source, parse_domain_artifact, render_domain_artifact
    )

    assert isinstance(snapshot, NoncanonicalArtifactSnapshot)
    assert snapshot.source_digest == hashlib.sha256(source).hexdigest()


def test_reason_accepts_each_closed_receipt_reason_without_reclassification() -> None:
    for reason in RECEIPT_REASONS:
        assert parse_receipt_reason(reason) == reason
        result = select_receipt_feedback(_snapshot(), _SELECTOR, reason)

        assert result.verdict == "accepted"
        assert result.reason == reason
        assert result.target == ReceiptTarget(FeedbackTargetKind.ROW, _TARGET_ID)


def test_reason_rejects_values_outside_the_closed_vocabulary() -> None:
    for reason in (None, "", " prose", "prose ", "unknown"):
        assert parse_receipt_reason(reason) is None


def test_selection_reports_missing_and_duplicate_feedback_before_lifecycle_checks() -> None:
    missing = _selection(feedback=())
    duplicate = _selection(feedback=(_feedback(), _feedback()))

    assert missing.verdict == "missing-feedback"
    assert duplicate.verdict == "duplicate-feedback"
    assert missing.target is None
    assert duplicate.target is None


def test_selection_checks_non_open_state_before_existing_response() -> None:
    result = _selection(
        feedback=(
            _feedback(
                state=FeedbackState.DEFERRED,
                proposed_response="Already addressed.",
            ),
        )
    )

    assert result.verdict == "not-open"


def test_selection_rejects_an_open_row_with_a_proposed_response() -> None:
    result = _selection(feedback=(_feedback(proposed_response="Already addressed."),))

    assert result.verdict == "already-responded"


def test_selection_accepts_an_artifact_target_without_local_revision_allowlist_checks() -> None:
    result = _selection(
        feedback=(
            _feedback(target=FeedbackTarget(FeedbackTargetKind.ARTIFACT)),
        )
    )

    assert result.verdict == "accepted"
    assert result.feedback_state is FeedbackState.OPEN
    assert result.target is not None
    assert result.target.kind is FeedbackTargetKind.ARTIFACT
    assert result.target.id == _SELECTOR.artifact_key
    assert "request" not in vars(result)


def test_selection_copies_reopen_nonce_from_the_selected_row() -> None:
    result = _selection(
        feedback=(
            _feedback(
                feedback_reopen=FeedbackReopenRecord(
                    selector={"artifact_key": "domain", "feedback_id": _SELECTOR.feedback_id},
                    reason="operator-confirmed-evidence-unavailable",
                    nonce=_REOPEN_NONCE,
                    recorded_at="2026-08-27T12:00:00.000000Z",
                )
            ),
        )
    )

    assert result.verdict == "accepted"
    assert result.reopen_nonce == _REOPEN_NONCE
    assert "request" not in vars(result)
    assert "proposed_response" not in vars(result)


def test_receipt_safe_selector_rejects_before_reason_source_or_feedback_lookup() -> None:
    unsafe = FeedbackSelector("domain", "feedback request")

    assert admit_receipt_selector(unsafe) is None


def test_selection_rejects_unsafe_row_target_before_recording_target_facts() -> None:
    result = _selection(
        feedback=(
            _feedback(
                target=FeedbackTarget(FeedbackTargetKind.ROW, "target request")
            ),
        )
    )

    assert result.verdict == "identifier-rejected"
    assert result.target is None


def test_selection_reports_ambiguous_and_missing_live_row_targets_in_selected_artifact() -> None:
    ambiguous = _selection(
        entities=(
            EntityRow(_TARGET_ID, "Order", ()),
            EntityRow(_TARGET_ID, "Other order", ()),
        )
    )
    removal_only = _selection(
        feedback=(
            _feedback(target=FeedbackTarget(FeedbackTargetKind.ROW, "removed-order")),
        ),
        entities=(),
        removals=(RemovalRecord("removed-order", "Removed", (_SELECTOR.feedback_id,)),),
    )

    assert ambiguous.verdict == "missing-or-ambiguous-target"
    assert removal_only.verdict == "target-not-live-in-selected-artifact"


def test_selection_never_uses_another_artifact_to_make_a_row_target_live() -> None:
    result = _selection(
        feedback=(
            _feedback(target=FeedbackTarget(FeedbackTargetKind.ROW, "entity-other")),
        ),
        entities=(),
    )

    assert result.verdict == "target-not-live-in-selected-artifact"


def test_baseline_backed_source_admission_is_gone() -> None:
    """Selection judges one parsed snapshot; no stage-baseline admission wraps it."""
    assert not hasattr(roadmap_escalation_selection, "admit_versioned_artifact_source")
    assert not hasattr(roadmap_escalation_selection, "VersionedArtifactAdmission")
