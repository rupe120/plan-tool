"""Pure shared feedback selector and lookup primitives."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from typing import Literal, TypeAlias

from plan_tool.roadmap_artifacts import RECEIPT_SAFE_ID_RE, FeedbackRow, RoadmapArtifact


@dataclass(frozen=True)
class FeedbackSelector:
    """One configured artifact key and one feedback identifier."""

    artifact_key: str
    feedback_id: str


@dataclass(frozen=True)
class MalformedFeedbackSelector:
    """A selector that does not satisfy the shared grammar."""

    reason: Literal["not-string", "missing-separator", "invalid-parts"]


@dataclass(frozen=True)
class UnknownFeedbackArtifact:
    """A syntactically valid selector whose artifact key is not configured."""

    artifact_key: str


FeedbackSelectorParseOutcome: TypeAlias = (
    FeedbackSelector | MalformedFeedbackSelector | UnknownFeedbackArtifact
)


def is_receipt_safe_id(value: object) -> bool:
    """Return whether one persisted receipt identifier has the closed grammar."""
    return isinstance(value, str) and RECEIPT_SAFE_ID_RE.fullmatch(value) is not None


def parse_feedback_selector(
    value: object, artifact_keys: Collection[str]
) -> FeedbackSelectorParseOutcome:
    """Parse one ``<artifact-key>:<feedback-id>`` selector without policy."""
    if not isinstance(value, str):
        return MalformedFeedbackSelector("not-string")
    if ":" not in value:
        return MalformedFeedbackSelector("missing-separator")
    artifact_key, feedback_id = value.split(":", 1)
    if not artifact_key or not feedback_id.strip() or ":" in feedback_id:
        return MalformedFeedbackSelector("invalid-parts")
    if artifact_key not in artifact_keys:
        return UnknownFeedbackArtifact(artifact_key)
    return FeedbackSelector(artifact_key=artifact_key, feedback_id=feedback_id)


def matching_feedback_rows(
    artifact: RoadmapArtifact, selector: FeedbackSelector
) -> tuple[FeedbackRow, ...]:
    """Return every selected-artifact feedback row matching the selector."""
    return tuple(row for row in artifact.feedback if row.id == selector.feedback_id)
