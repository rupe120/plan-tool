"""Tests for shared roadmap feedback selector primitives."""

from __future__ import annotations

from plan_tool.roadmap import STAGES
from plan_tool.roadmap_artifacts import (
    DomainArtifact,
    FeedbackRow,
    FeedbackState,
    FeedbackTarget,
    FeedbackTargetKind,
)
from plan_tool.roadmap_feedback import (
    FeedbackSelector,
    MalformedFeedbackSelector,
    UnknownFeedbackArtifact,
    is_receipt_safe_id,
    matching_feedback_rows,
    parse_feedback_selector,
)


_ARTIFACT_KEYS = tuple(stage.artifact_key for stage in STAGES)


def _feedback(feedback_id: str) -> FeedbackRow:
    return FeedbackRow(
        id=feedback_id,
        target=FeedbackTarget(FeedbackTargetKind.ARTIFACT),
        request="Review this artifact.",
        state=FeedbackState.OPEN,
    )


def _artifact(feedback: tuple[FeedbackRow, ...]) -> DomainArtifact:
    return DomainArtifact(
        entities=(),
        business_rules=(),
        workflows=(),
        decisions=(),
        body="# Domain\n",
        feedback=feedback,
    )


def test_parse_feedback_selector_accepts_configured_stage_keys_and_preserves_feedback_id() -> None:
    for artifact_key in _ARTIFACT_KEYS:
        outcome = parse_feedback_selector(
            f"{artifact_key}: feedback-1 ", _ARTIFACT_KEYS
        )

        assert outcome == FeedbackSelector(artifact_key, " feedback-1 ")


def test_parse_feedback_selector_distinguishes_malformed_syntax_from_unknown_configured_artifact() -> None:
    malformed_outcomes = [
        parse_feedback_selector(value, _ARTIFACT_KEYS)
        for value in (
            None,
            "domain",
            ":feedback-1",
            "domain:",
            "domain:   ",
            "domain:one:two",
        )
    ]
    for outcome in malformed_outcomes:
        assert isinstance(outcome, MalformedFeedbackSelector)
        assert set(vars(outcome)) == {"reason"}

    outcome = parse_feedback_selector("unknown:feedback-1", _ARTIFACT_KEYS)

    assert outcome == UnknownFeedbackArtifact("unknown")
    assert vars(outcome) == {"artifact_key": "unknown"}


def test_receipt_safe_id_accepts_the_closed_ascii_grammar() -> None:
    assert is_receipt_safe_id("a")
    assert is_receipt_safe_id("A0._-")
    assert is_receipt_safe_id("a" + "0" * 127)


def test_receipt_safe_id_rejects_empty_non_ascii_bad_prefix_invalid_character_and_overlong_values() -> None:
    for value in ("", " review", ".review", "-review", "review name", "café", "a" * 129):
        assert not is_receipt_safe_id(value)


def test_selector_parser_preserves_its_broader_existing_grammar() -> None:
    outcome = parse_feedback_selector("domain:review request", _ARTIFACT_KEYS)

    assert outcome == FeedbackSelector("domain", "review request")
    assert not is_receipt_safe_id(outcome.feedback_id)


def test_matching_feedback_rows_preserves_zero_one_and_many_candidates_in_artifact_order() -> None:
    first = _feedback("first")
    selected_first = _feedback("selected")
    selected_second = _feedback("selected")
    artifact = _artifact((first, selected_first, selected_second))

    assert matching_feedback_rows(artifact, FeedbackSelector("domain", "missing")) == ()
    assert matching_feedback_rows(artifact, FeedbackSelector("domain", "first")) == (first,)
    assert matching_feedback_rows(artifact, FeedbackSelector("domain", "selected")) == (
        selected_first,
        selected_second,
    )
