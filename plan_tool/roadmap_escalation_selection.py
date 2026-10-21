"""Pure receipt-safe selection for one canonical roadmap artifact."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, TypeAlias, cast

from plan_tool.roadmap_artifacts import (
    FeedbackState,
    FeedbackTargetKind,
    RoadmapArtifact,
    RoadmapArtifactError,
    design_row_collections,
)
from plan_tool.roadmap_feedback import (
    FeedbackSelector,
    is_receipt_safe_id,
    matching_feedback_rows,
)


ReceiptReason: TypeAlias = Literal[
    "prose",
    "row-structure",
    "collection-structure",
    "relationship-semantics",
    "decision-semantics",
    "cross-artifact-impact",
]
RejectedReceiptSelectionVerdict: TypeAlias = Literal[
    "missing-feedback",
    "duplicate-feedback",
    "not-open",
    "already-responded",
    "identifier-rejected",
    "missing-or-ambiguous-target",
    "target-not-live-in-selected-artifact",
]
ReceiptSelectionVerdict: TypeAlias = RejectedReceiptSelectionVerdict | Literal[
    "accepted"
]

RECEIPT_REASONS: tuple[ReceiptReason, ...] = (
    "prose",
    "row-structure",
    "collection-structure",
    "relationship-semantics",
    "decision-semantics",
    "cross-artifact-impact",
)


@dataclass(frozen=True)
class ReceiptSafeSelector:
    """A shared selector admitted for receipt persistence and logging."""

    artifact_key: str
    feedback_id: str


@dataclass(frozen=True)
class CanonicalArtifactSnapshot:
    """One parsed artifact bound to render-canonical raw source bytes."""

    artifact: RoadmapArtifact
    source_digest: str


@dataclass(frozen=True)
class UndecodableArtifactSnapshot:
    """Source bytes that do not form strict UTF-8 and therefore have no digest."""


@dataclass(frozen=True)
class UnparsableArtifactSnapshot:
    """Strict UTF-8 source whose parser rejected its exact text."""

    source_digest: str


@dataclass(frozen=True)
class NoncanonicalArtifactSnapshot:
    """Parsed source whose renderer bytes differ from the supplied bytes."""

    source_digest: str
    artifact: RoadmapArtifact | None = field(default=None, compare=False, repr=False)


ArtifactSnapshot: TypeAlias = (
    CanonicalArtifactSnapshot
    | UndecodableArtifactSnapshot
    | UnparsableArtifactSnapshot
    | NoncanonicalArtifactSnapshot
)

ParsedArtifactSnapshot: TypeAlias = (
    CanonicalArtifactSnapshot | NoncanonicalArtifactSnapshot
)


@dataclass(frozen=True)
class ReceiptTarget:
    """One receipt-safe artifact or design-row target."""

    kind: FeedbackTargetKind
    id: str


@dataclass(frozen=True)
class ReceiptSelection:
    """One selected-artifact receipt verdict with only receipt-safe facts."""

    verdict: ReceiptSelectionVerdict
    selector: ReceiptSafeSelector
    reason: ReceiptReason
    source_digest: str
    reopen_nonce: str | None = None
    feedback_state: FeedbackState | None = None
    target: ReceiptTarget | None = None


def admit_receipt_selector(
    selector: FeedbackSelector,
) -> ReceiptSafeSelector | None:
    """Return a selector only when both persisted identifiers are receipt-safe."""
    if not (
        is_receipt_safe_id(selector.artifact_key)
        and is_receipt_safe_id(selector.feedback_id)
    ):
        return None
    return ReceiptSafeSelector(
        artifact_key=selector.artifact_key,
        feedback_id=selector.feedback_id,
    )


def parse_receipt_reason(value: object) -> ReceiptReason | None:
    """Return one closed receipt reason without rewriting its chosen value."""
    if isinstance(value, str) and value in RECEIPT_REASONS:
        return cast(ReceiptReason, value)
    return None


def canonical_artifact_snapshot(
    source_bytes: bytes,
    parse_artifact: Callable[[str], RoadmapArtifact],
    render_artifact: Callable[[RoadmapArtifact], str],
) -> ArtifactSnapshot:
    """Parse and render-check one raw source snapshot without normalizing it."""
    try:
        source_text = source_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return UndecodableArtifactSnapshot()

    source_digest = hashlib.sha256(source_bytes).hexdigest()
    try:
        artifact = parse_artifact(source_text)
    except RoadmapArtifactError:
        return UnparsableArtifactSnapshot(source_digest=source_digest)

    if render_artifact(artifact).encode("utf-8") != source_bytes:
        return NoncanonicalArtifactSnapshot(
            source_digest=source_digest,
            artifact=artifact,
        )
    return CanonicalArtifactSnapshot(artifact=artifact, source_digest=source_digest)


def select_receipt_feedback(
    snapshot: ParsedArtifactSnapshot,
    selector: ReceiptSafeSelector,
    reason: ReceiptReason,
) -> ReceiptSelection:
    """Return the first receipt verdict from the selected artifact alone."""
    _require_receipt_safe_selector(selector)
    _require_receipt_reason(reason)
    selected = matching_feedback_rows(snapshot.artifact, _shared_selector(selector))
    if not selected:
        return _rejected_selection("missing-feedback", snapshot, selector, reason)
    if len(selected) > 1:
        return _rejected_selection("duplicate-feedback", snapshot, selector, reason)

    feedback = selected[0]
    if feedback.state is not FeedbackState.OPEN:
        return _rejected_selection("not-open", snapshot, selector, reason)
    if feedback.proposed_response is not None:
        return _rejected_selection("already-responded", snapshot, selector, reason)

    if feedback.target.kind is FeedbackTargetKind.ARTIFACT:
        target = ReceiptTarget(FeedbackTargetKind.ARTIFACT, selector.artifact_key)
    else:
        target_row_id = feedback.target.row_id
        if target_row_id is None or not is_receipt_safe_id(target_row_id):
            return _rejected_selection("identifier-rejected", snapshot, selector, reason)
        matches = tuple(
            row
            for rows in design_row_collections(snapshot.artifact).values()
            for row in rows
            if row.id == target_row_id
        )
        if len(matches) > 1:
            return _rejected_selection(
                "missing-or-ambiguous-target", snapshot, selector, reason
            )
        if not matches:
            return _rejected_selection(
                "target-not-live-in-selected-artifact", snapshot, selector, reason
            )
        target = ReceiptTarget(FeedbackTargetKind.ROW, target_row_id)

    return ReceiptSelection(
        verdict="accepted",
        selector=selector,
        reason=reason,
        source_digest=snapshot.source_digest,
        reopen_nonce=(
            feedback.feedback_reopen.nonce
            if feedback.feedback_reopen is not None
            else None
        ),
        feedback_state=feedback.state,
        target=target,
    )


def _shared_selector(selector: ReceiptSafeSelector) -> FeedbackSelector:
    """Adapt the receipt-only type to the shared artifact-local lookup."""
    return FeedbackSelector(selector.artifact_key, selector.feedback_id)


def _require_receipt_safe_selector(selector: ReceiptSafeSelector) -> None:
    """Reject an invalid caller-created wrapper without reclassifying it here."""
    if not (
        is_receipt_safe_id(selector.artifact_key)
        and is_receipt_safe_id(selector.feedback_id)
    ):
        raise ValueError("receipt selection requires a receipt-safe selector")


def _require_receipt_reason(reason: ReceiptReason) -> None:
    """Reject an invalid caller-created reason without recording it as a fact."""
    if parse_receipt_reason(reason) is None:
        raise ValueError("receipt selection requires a closed receipt reason")


def _rejected_selection(
    verdict: RejectedReceiptSelectionVerdict,
    snapshot: CanonicalArtifactSnapshot,
    selector: ReceiptSafeSelector,
    reason: ReceiptReason,
) -> ReceiptSelection:
    return ReceiptSelection(
        verdict=verdict,
        selector=selector,
        reason=reason,
        source_digest=snapshot.source_digest,
    )
