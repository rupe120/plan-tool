"""Read-only preflight for settling one Roadmap-derived pending decision.

See docs/ARCHITECTURE.md's "Decision-settlement receipts" entry for the
full design; this leaf writes nothing, takes no lock, and never imports
``plan_tool.roadmap`` or the writer layer above it.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal, Protocol, TypeAlias

from plan_tool.checkpoint import compute_input_hash
from plan_tool.roadmap_artifacts import (
    DecisionStatus,
    FeedbackTargetKind,
    RoadmapArtifact,
    design_row_collections,
    settle_pending_decision,
)
from plan_tool.roadmap_escalation_selection import (
    NoncanonicalArtifactSnapshot,
    UndecodableArtifactSnapshot,
    UnparsableArtifactSnapshot,
    canonical_artifact_snapshot,
)
from plan_tool.roadmap_feedback import (
    FeedbackSelector,
    MalformedFeedbackSelector,
    UnknownFeedbackArtifact,
    is_receipt_safe_id,
    matching_feedback_rows,
    parse_feedback_selector,
)
from plan_tool.roadmap_feedback_ledger import (
    RoadmapFeedbackLedger,
    RoadmapFeedbackLedgerError,
    eligible_reviewer_items,
    load_ledger,
    roadmap_feedback_ledger_path,
)
from plan_tool.roadmap_source_identity import feedback_snapshot
from plan_tool.roadmap_versions import ResolvedRoadmapVersion, load_accepted_version


DecisionSettlementRefusalVerdict: TypeAlias = Literal[
    "malformed-decision-selector",
    "unknown-artifact",
    "missing-decision",
    "inherited-decision",
    "decision-not-pending",
    "duplicate-decision",
    "duplicate-feedback",
    "malformed-evidence-selector",
    "evidence-artifact-mismatch",
    "missing-feedback",
    "feedback-not-targeting-decision",
    "empty-request",
    # Ledger-backed (enrolled) evidence only: the cited item exists but is not
    # open, not submitted against this accepted version, or its target
    # fingerprint no longer matches.
    "feedback-not-eligible",
    "no-published-version",
    "source-not-canonical",
    "unsafe-selector",
    # Not returned by this module: rebuilt here for runners (steps 4/5),
    # which report it when the currency check below returns ``False``.
    "source-changed",
]


class _DecisionSettlementStage(Protocol):
    """The narrow stage shape this leaf needs."""

    artifact_key: str
    parse: Callable[[str], RoadmapArtifact]
    render: Callable[[RoadmapArtifact], str]


@dataclass(frozen=True)
class DecisionSettlementSelector:
    """One receipt-safe decision id paired with its cited evidence row id."""

    artifact_key: str
    decision_id: str
    feedback_id: str


@dataclass(frozen=True)
class DecisionSettlementCandidate:
    """A current, provably safe settlement bound to exact canonical bytes."""

    selector: DecisionSettlementSelector
    accepted_version_id: str | None
    source_digest: str
    evidence_digest: str
    settled_artifact: RoadmapArtifact
    settled_bytes: bytes
    settled_digest: str


@dataclass(frozen=True)
class DecisionSettlementRefusal:
    """A redacted reason one settlement request cannot proceed."""

    verdict: DecisionSettlementRefusalVerdict


DecisionSettlementSelectorResult: TypeAlias = (
    DecisionSettlementSelector | DecisionSettlementRefusal
)
DecisionSettlementCandidateResult: TypeAlias = (
    DecisionSettlementCandidate | DecisionSettlementRefusal
)


def resolve_decision_settlement_selector(
    decision_value: object,
    evidence_value: object,
    *,
    artifact_keys: Collection[str],
) -> DecisionSettlementSelectorResult:
    """Parse a ``<artifact-key>:<id>`` decision and evidence selector pair.

    Pure: no filesystem access. The evidence selector always names the
    decision's own artifact, so an evidence key that differs from the
    decision's — including one naming an unconfigured artifact — is a
    mismatch, not a separate unknown-artifact case.
    """
    parsed_decision = parse_feedback_selector(decision_value, artifact_keys)
    if isinstance(parsed_decision, MalformedFeedbackSelector):
        return _refuse("malformed-decision-selector")
    if isinstance(parsed_decision, UnknownFeedbackArtifact):
        return _refuse("unknown-artifact")

    parsed_evidence = parse_feedback_selector(evidence_value, artifact_keys)
    if isinstance(parsed_evidence, MalformedFeedbackSelector):
        return _refuse("malformed-evidence-selector")
    if (
        isinstance(parsed_evidence, UnknownFeedbackArtifact)
        or parsed_evidence.artifact_key != parsed_decision.artifact_key
    ):
        return _refuse("evidence-artifact-mismatch")

    selector = DecisionSettlementSelector(
        artifact_key=parsed_decision.artifact_key,
        decision_id=parsed_decision.feedback_id,
        feedback_id=parsed_evidence.feedback_id,
    )
    if not _selector_is_receipt_safe(selector):
        return _refuse("unsafe-selector")
    return selector


class DecisionSettlementSourceCorruptError(RuntimeError):
    """An enrolled roadmap's accepted-version member or feedback ledger is corrupt.

    Deliberately not a ``ValueError``/``RoadmapVersionError``: both
    runners' catch-all treats those as an ordinary, expected refusal (a
    malformed accepted-head *selector*, or an existing-member write
    collision, both already tested as such) and folds them into a generic
    ``write-failed`` outcome. A corrupt version *member* is a broken store,
    not an operator refusal, so it must propagate to the top-level
    unexpected-error handler instead.
    """


def build_decision_settlement_candidate(
    selector: DecisionSettlementSelector,
    *,
    plans_dir: Path,
    slug: str,
    stages: Sequence[_DecisionSettlementStage],
) -> DecisionSettlementCandidateResult:
    """Bind one current, evidence-viable settlement to exact canonical bytes.

    Reads only the accepted version, never a stage file or baseline; a folder
    with no accepted head is refused as ``no-published-version`` before any
    other read. A roadmap that has a feedback ledger takes its evidence from a
    ledger item; every other roadmap takes it from embedded feedback rows. Lets a corrupt
    accepted-version member or ledger
    (:class:`DecisionSettlementSourceCorruptError`) propagate
    unchanged — that is a broken store, not an operator refusal. A malformed
    accepted-head *selector* is a different, already-ordinary refusal: it
    surfaces through ``load_accepted_version`` itself and both runners
    already fold it into their generic ``write-failed`` outcome.
    """
    if not _selector_is_receipt_safe(selector):
        return _refuse("unsafe-selector")

    stage = next(
        (item for item in stages if item.artifact_key == selector.artifact_key), None
    )
    if stage is None:
        raise ValueError(f"no configured stage for artifact key {selector.artifact_key!r}")

    accepted_version = load_accepted_version(plans_dir=plans_dir, slug=slug)
    if accepted_version is None:
        return _refuse("no-published-version")
    ledger: RoadmapFeedbackLedger | None = None
    # A ledger-less roadmap stays on its embedded-feedback evidence and is not
    # migrated; the same existence test selects step 5's batch route.
    ledger_path = roadmap_feedback_ledger_path(plans_dir, slug)
    if ledger_path.exists():
        try:
            ledger = load_ledger(ledger_path)
        except RoadmapFeedbackLedgerError as exc:
            raise DecisionSettlementSourceCorruptError(
                "the roadmap's feedback ledger is corrupt"
            ) from exc
    if selector.artifact_key not in accepted_version.artifact_keys:
        raise ValueError(
            f"artifact key {selector.artifact_key!r} is not part of the "
            "accepted version's own inventory"
        )
    member_index = accepted_version.artifact_keys.index(selector.artifact_key)
    source_bytes = accepted_version.artifact_bytes[member_index]
    snapshot = canonical_artifact_snapshot(source_bytes, stage.parse, stage.render)
    if isinstance(snapshot, (UndecodableArtifactSnapshot, UnparsableArtifactSnapshot)):
        raise DecisionSettlementSourceCorruptError(
            f"accepted version member for artifact key {selector.artifact_key!r} "
            "is corrupt"
        )
    if isinstance(snapshot, NoncanonicalArtifactSnapshot):
        return _refuse("source-not-canonical")
    artifact = snapshot.artifact
    source_digest = snapshot.source_digest
    accepted_version_id = accepted_version.record.version_id

    decision = next(
        (row for row in artifact.decisions if row.id == selector.decision_id), None
    )
    if decision is None:
        return _refuse("missing-decision")
    all_matches = sum(
        1
        for rows in design_row_collections(artifact).values()
        for row in rows
        if row.id == selector.decision_id
    )
    if all_matches != 1:
        return _refuse("duplicate-decision")
    if decision.source is not None:
        return _refuse("inherited-decision")
    if decision.status is not DecisionStatus.PENDING:
        return _refuse("decision-not-pending")

    if ledger is not None:
        assert accepted_version is not None
        evidence = _ledger_evidence_digest(selector, accepted_version, ledger)
    else:
        evidence = _embedded_evidence_digest(selector, artifact)
    if isinstance(evidence, DecisionSettlementRefusal):
        return evidence
    evidence_digest = evidence

    settled_artifact = settle_pending_decision(artifact, decision_id=selector.decision_id)
    settled_bytes = stage.render(settled_artifact).encode("utf-8")
    _require_single_status_line_change(source_bytes, settled_bytes)

    return DecisionSettlementCandidate(
        selector=selector,
        accepted_version_id=accepted_version_id,
        source_digest=source_digest,
        evidence_digest=evidence_digest,
        settled_artifact=settled_artifact,
        settled_bytes=settled_bytes,
        settled_digest=hashlib.sha256(settled_bytes).hexdigest(),
    )


def _embedded_evidence_digest(
    selector: DecisionSettlementSelector, artifact: RoadmapArtifact
) -> str | DecisionSettlementRefusal:
    evidence_rows = matching_feedback_rows(
        artifact, FeedbackSelector(selector.artifact_key, selector.feedback_id)
    )
    if not evidence_rows:
        return _refuse("missing-feedback")
    if len(evidence_rows) > 1:
        return _refuse("duplicate-feedback")
    evidence_row = evidence_rows[0]
    target = evidence_row.target
    if not (
        target.kind is FeedbackTargetKind.ROW and target.row_id == selector.decision_id
    ):
        return _refuse("feedback-not-targeting-decision")
    if not evidence_row.request.strip():
        return _refuse("empty-request")
    return feedback_snapshot(replace(artifact, feedback=(evidence_row,))).digest


def _ledger_evidence_digest(
    selector: DecisionSettlementSelector,
    accepted_version: ResolvedRoadmapVersion,
    ledger: RoadmapFeedbackLedger,
) -> str | DecisionSettlementRefusal:
    """Bind the cited ledger item, which must still be eligible for this source.

    An id and shape match is not enough: a ledger item outlives the accepted
    source it was submitted against, so it must also be ``open``, submitted
    against ``accepted_version``, and carry a target fingerprint that still
    matches. Item ids are unique across the ledger, so there is no
    ``duplicate-feedback`` case here.
    """
    item = next(
        (
            entry
            for group in ledger.reviewer_feedback_groups
            for entry in group.items
            if entry.item_id == selector.feedback_id
        ),
        None,
    )
    if item is None:
        return _refuse("missing-feedback")
    target = item.target
    if not (
        target.kind is FeedbackTargetKind.ROW
        and target.row_id == selector.decision_id
        and target.artifact_key == selector.artifact_key
    ):
        return _refuse("feedback-not-targeting-decision")
    if not item.request.strip():
        return _refuse("empty-request")
    if item not in eligible_reviewer_items(ledger, accepted_version):
        return _refuse("feedback-not-eligible")
    # Reviewer-authored fields only: a model proposal is never settlement evidence.
    return compute_input_hash(
        {
            "item_id": item.item_id,
            "target": target.model_dump(mode="json"),
            "request": item.request,
            "submitted_against_version_id": item.submitted_against_version_id,
            "target_fingerprint": item.target_fingerprint,
        }
    )


def decision_settlement_candidate_is_current(
    candidate: DecisionSettlementCandidate | object,
    *,
    plans_dir: Path,
    slug: str,
    stages: Sequence[_DecisionSettlementStage],
) -> bool:
    """Require a fresh rebuild binding the same lineage, source bytes, and evidence.

    A digest-only check would miss a new accepted head that leaves the
    selected member's own bytes unchanged, so both the lineage
    (``accepted_version_id``) and the exact source bytes (``source_digest``)
    must still match. Ledger evidence lives outside those bytes, so the
    evidence digest must match too.
    """
    if not isinstance(candidate, DecisionSettlementCandidate):
        return False
    rebuilt = build_decision_settlement_candidate(
        candidate.selector, plans_dir=plans_dir, slug=slug, stages=stages
    )
    return (
        isinstance(rebuilt, DecisionSettlementCandidate)
        and rebuilt.accepted_version_id == candidate.accepted_version_id
        and rebuilt.source_digest == candidate.source_digest
        and rebuilt.evidence_digest == candidate.evidence_digest
    )


class DecisionSettlementContentIntegrityError(RuntimeError):
    """The settled render broke step 1's single-status-line contract.

    Deliberately not a ``ValueError``: both runners' catch-all treats a
    ``ValueError`` as an ordinary, expected refusal and folds it into a
    generic ``write-failed`` outcome, discarding its message. This signals a
    real bug in settlement rendering, not an expected runtime failure, so it
    must propagate to the top-level unexpected-error handler instead.
    """


def _require_single_status_line_change(source_bytes: bytes, settled_bytes: bytes) -> None:
    """Require the settled render to differ from its source in exactly one
    line, and that line to change only ``status: pending`` to ``status:
    settled`` — the byte-level check backstopping step 1's own contract."""
    source_lines = source_bytes.decode("utf-8").splitlines(keepends=True)
    settled_lines = settled_bytes.decode("utf-8").splitlines(keepends=True)
    if len(source_lines) != len(settled_lines):
        raise DecisionSettlementContentIntegrityError(
            "settlement changed more than the decision's status line"
        )
    changed = [
        index
        for index, (before, after) in enumerate(
            zip(source_lines, settled_lines, strict=True)
        )
        if before != after
    ]
    if len(changed) != 1:
        raise DecisionSettlementContentIntegrityError(
            "settlement changed more than the decision's status line"
        )
    before, after = source_lines[changed[0]], settled_lines[changed[0]]
    expected_after = before.replace(
        f"status: {DecisionStatus.PENDING.value}", f"status: {DecisionStatus.SETTLED.value}", 1
    )
    if expected_after == before or after != expected_after:
        raise DecisionSettlementContentIntegrityError(
            "settlement changed a line other than the decision's status"
        )


def _selector_is_receipt_safe(selector: DecisionSettlementSelector) -> bool:
    return (
        is_receipt_safe_id(selector.artifact_key)
        and is_receipt_safe_id(selector.decision_id)
        and is_receipt_safe_id(selector.feedback_id)
    )


def _refuse(verdict: DecisionSettlementRefusalVerdict) -> DecisionSettlementRefusal:
    return DecisionSettlementRefusal(verdict=verdict)
