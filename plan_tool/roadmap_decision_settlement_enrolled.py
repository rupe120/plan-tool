"""Settle one confirmed Roadmap-derived pending decision on the accepted version.

See docs/ARCHITECTURE.md's "Decision-settlement receipts" entry for the
full design.
"""

from __future__ import annotations

from collections.abc import Sequence
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from plan_tool.checkpoint import compute_input_hash
from plan_tool.roadmap import STAGES, RoadmapStage, refresh_roadmap_index
from plan_tool.roadmap_artifacts import RoadmapArtifactError, roadmap_dir
from plan_tool.roadmap_candidate_run import (
    CandidateProposalAdmission,
    CandidateProposalError,
    build_terminal_resolution_generation,
    load_candidate_admission,
    load_stored_candidate_proposal,
    new_terminal_resolution,
)
from plan_tool.roadmap_decision_settlement import (
    DecisionSettlementCandidate,
    DecisionSettlementRefusal,
    build_decision_settlement_candidate,
    decision_settlement_candidate_is_current,
    resolve_decision_settlement_selector,
)
from plan_tool.roadmap_decision_settlement_receipt import (
    DECISION_SETTLEMENT_RECEIPT_SUCCESS_OUTCOMES,
    DecisionSettlementReceiptError,
    ReceiptCommitter,
    build_decision_settlement_receipt,
    publish_decision_settlement_receipt,
)
from plan_tool.roadmap_decision_settlement_run import (
    DecisionSettlementRunResult,
    _result,
)
from plan_tool.roadmap_impact_snapshot import (
    CompleteRoadmapGateEvidence,
    RoadmapGateOutcome,
    RoadmapImpactSnapshotError,
    check_complete_roadmap_gates,
)
from plan_tool.roadmap_evidence_store import (
    EVIDENCE_CREATED,
    EVIDENCE_EXISTING,
    EvidenceNamespace,
    publish_evidence,
    read_evidence_final,
)
from plan_tool.roadmap_revision_publish import (
    DECISION_SETTLEMENT_GENERATION_KIND,
    RoadmapPublicationRecoveryError,
    RoadmapRevisionPublishError,
    RoadmapWriterGuardError,
    publish_roadmap_generation,
    recover_roadmap_publication,
    roadmap_writer_guard,
)
from plan_tool.roadmap_source_identity import GenerationMember, PendingGeneration
from plan_tool.roadmap_versions import (
    ROADMAP_VERSION_SCHEMA_VERSION,
    AcceptedRoadmapHead,
    PreparedRoadmapVersion,
    ResolvedRoadmapVersion,
    RoadmapVersionContent,
    RoadmapVersionError,
    accepted_head_path,
    create_candidate_version,
    load_accepted_head,
    load_accepted_version,
    parse_accepted_head,
    render_accepted_head,
    stored_version_members,
    version_directory_path,
)


class _StaleEnrolledDecisionSettlementSource(RuntimeError):
    """The accepted head moved since the settlement candidate was pinned."""


@dataclass(frozen=True)
class _ConfirmedActiveCandidateBinding:
    """The exact request facts an affirmative response is allowed to release."""

    accepted_version_id: str
    candidate_version_id: str
    settlement_identity: str
    decision_selector: str
    evidence_selector: str


def _confirmation_result(
    result: DecisionSettlementRunResult,
    *,
    final_name: str,
    binding: _ConfirmedActiveCandidateBinding,
) -> DecisionSettlementRunResult:
    """Expose the request facts without widening the shared legacy result type."""
    # The shared result remains intentionally redacted for the old CLI route.
    # Enrolled callers opt into these additional, immutable response facts.
    object.__setattr__(result, "confirmation_evidence_final", final_name)
    object.__setattr__(result, "accepted_version_id", binding.accepted_version_id)
    object.__setattr__(result, "active_candidate_version_id", binding.candidate_version_id)
    object.__setattr__(result, "settlement_identity", binding.settlement_identity)
    return result


def _confirmation_bytes(binding: _ConfirmedActiveCandidateBinding) -> bytes:
    return json.dumps(
        {
            "accepted_version_id": binding.accepted_version_id,
            "active_candidate_version_id": binding.candidate_version_id,
            "kind": "enrolled-decision-settlement-confirmation-evidence",
            "schema_version": 1,
            "settlement_identity": binding.settlement_identity,
            "decision_selector": binding.decision_selector,
            "evidence_selector": binding.evidence_selector,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _parse_confirmation_evidence(data: object, final_name: object) -> _ConfirmedActiveCandidateBinding | None:
    """Decode one exact confirmation-evidence receipt, refusing all malformed data."""
    if not isinstance(data, bytes) or not isinstance(final_name, str):
        return None
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict) or set(value) != {
        "accepted_version_id", "active_candidate_version_id", "kind", "schema_version",
        "settlement_identity", "decision_selector", "evidence_selector",
    }:
        return None
    if value.get("kind") != "enrolled-decision-settlement-confirmation-evidence" or value.get("schema_version") != 1:
        return None
    fields = ("accepted_version_id", "active_candidate_version_id", "settlement_identity")
    if any(not isinstance(value.get(field), str) or len(value[field]) != 64 for field in fields):
        return None
    selectors = (value.get("decision_selector"), value.get("evidence_selector"))
    if any(not isinstance(value, str) for value in selectors):
        return None
    binding = _ConfirmedActiveCandidateBinding(*(value[field] for field in fields), *selectors)
    return binding if hashlib.sha256(data).hexdigest() == final_name else None


def respond_enrolled_decision_settlement(
    slug: str,
    confirmation_evidence_final: object,
    affirmative: object,
    *,
    plans_dir: Path,
    stages: Sequence[RoadmapStage] = STAGES,
    mode_rejected: bool = False,
    receipt_committer: ReceiptCommitter | None = None,
) -> DecisionSettlementRunResult:
    """Apply an exact affirmative confirmation-evidence receipt, if still bound."""
    if affirmative is not True or mode_rejected:
        return _result("preflight-rejected", "confirmation-required")
    try:
        stored = read_evidence_final(
            roadmap_dir(plans_dir, slug), EvidenceNamespace.DECISION_SETTLEMENTS,
            confirmation_evidence_final,
        )
    except (OSError, TypeError, ValueError):
        return _result("preflight-rejected", "confirmation-required")
    binding = _parse_confirmation_evidence(stored.data, confirmation_evidence_final)
    if binding is None:
        return _result("preflight-rejected", "confirmation-required")
    return run_enrolled_decision_settlement(
        slug,
        # These selectors are re-derived from the bound settlement candidate;
        # no caller-supplied selector can substitute evidence after approval.
        binding.decision_selector,
        binding.evidence_selector,
        binding,
        plans_dir=plans_dir,
        stages=stages,
        mode_rejected=False,
        receipt_committer=receipt_committer,
    )


def decision_settlement_content_identity(
    *,
    predecessor_version_id: str,
    artifact_key: str,
    decision_id: str,
    feedback_id: str,
    evidence_digest: str,
) -> str:
    """Return the settlement-owned content identity for one candidate version.

    Pure: independent of the model-authored candidate pipeline's own content
    identity, which hashes a capsule receipt this route never produces.
    """
    return compute_input_hash(
        {
            "schema_version": 1,
            "route": DECISION_SETTLEMENT_GENERATION_KIND,
            "predecessor_version_id": predecessor_version_id,
            "artifact_key": artifact_key,
            "decision_id": decision_id,
            "feedback_id": feedback_id,
            "evidence_digest": evidence_digest,
        }
    )


# States "no review occurred" for this route's candidate lineage, distinct
# from the model-authored pipeline's own "proposed, awaiting review"
# sentinel. Derived rather than hand-typed so the generation-kind literal
# lives in exactly one place (roadmap_revision_publish's own constant).
DECISION_SETTLEMENT_NO_REVIEW_LINEAGE_ID = compute_input_hash(
    {
        "review_lineage_version": 1,
        "review": "none",
        "route": DECISION_SETTLEMENT_GENERATION_KIND,
    }
)


def run_enrolled_decision_settlement(
    slug: str,
    decision_value: object,
    evidence_value: object,
    confirmation: object,
    *,
    plans_dir: Path,
    stages: Sequence[RoadmapStage] = STAGES,
    mode_rejected: bool = False,
    receipt_committer: ReceiptCommitter | None = None,
) -> DecisionSettlementRunResult:
    """Settle one confirmed, current decision on an enrolled roadmap.

    Commits step 3's receipt before the settlement version and selector swap
    publish, under one writer lease. Refuses ``unpromoted-candidate-lineage``
    whenever the current accepted head still carries an admitted candidate
    lineage that has not yet been promoted past it — regardless of that
    lineage's age or response state — and rechecks that refusal, along with
    source currency, once more inside the same lease after the receipt is
    committed.
    """
    confirmed_binding = (
        confirmation if isinstance(confirmation, _ConfirmedActiveCandidateBinding) else None
    )
    if confirmation is not True and confirmed_binding is None:
        return _result("preflight-rejected", "confirmation-required")
    if mode_rejected:
        return _result("preflight-rejected", "mode-rejected")
    try:
        roadmap_dir(plans_dir, slug)
    except (TypeError, ValueError):
        return _result("preflight-rejected", "mode-rejected")
    if receipt_committer is None:
        # Programmatic callers retain the CLI's scoped default without coupling
        # normal command wiring to a second receipt path.
        from plan_tool.cli.gitcommit import commit_receipt

        receipt_committer = commit_receipt

    receipt_id: str | None = None
    try:
        with roadmap_writer_guard(plans_dir, slug) as writer_token:
            if load_accepted_head(plans_dir=plans_dir, slug=slug) is None:
                # A cheap selector-only check, not the full digest-verified
                # read load_accepted_version does: this gate only needs "is
                # there an accepted head", and every later step that needs the
                # resolved content already calls load_accepted_version for real.
                return _result("preflight-rejected", "no-published-version")

            try:
                recover_roadmap_publication(
                    plans_dir=plans_dir, slug=slug, writer_token=writer_token
                )
            except RoadmapPublicationRecoveryError:
                return _result("preflight-rejected", "journal-unrecoverable")
            # Recovery may have completed a dangling publish.
            refresh_roadmap_index(plans_dir, slug)

            selector_result = resolve_decision_settlement_selector(
                decision_value,
                evidence_value,
                artifact_keys=tuple(stage.artifact_key for stage in stages),
            )
            if isinstance(selector_result, DecisionSettlementRefusal):
                return _result("preflight-rejected", selector_result.verdict)

            # Older single-feedback admissions have no step-5 processing
            # pair and retain their original hard refusal.  Only the pair
            # record is eligible for the request/response release below.
            admission_before_build = load_candidate_admission(plans_dir=plans_dir, slug=slug)
            admission_blocks = _admission_blocks_settlement(plans_dir=plans_dir, slug=slug)
            legacy_lineage = (
                admission_before_build is not None
                and admission_before_build.root_version_id is None
                and admission_blocks
            )
            if legacy_lineage:
                return _result("preflight-rejected", "unpromoted-candidate-lineage")

            candidate_result = build_decision_settlement_candidate(
                selector_result, plans_dir=plans_dir, slug=slug, stages=stages
            )
            if isinstance(candidate_result, DecisionSettlementRefusal):
                return _result("preflight-rejected", candidate_result.verdict)

            selector_path = accepted_head_path(plans_dir, slug)
            try:
                old_selector_bytes = selector_path.read_bytes()
            except OSError as exc:
                raise _StaleEnrolledDecisionSettlementSource from exc
            parsed_selector = parse_accepted_head(old_selector_bytes)
            fresh_accepted = load_accepted_version(plans_dir=plans_dir, slug=slug)
            if (
                fresh_accepted is None
                or parsed_selector.version_id != candidate_result.accepted_version_id
                or fresh_accepted.record.version_id != candidate_result.accepted_version_id
            ):
                raise _StaleEnrolledDecisionSettlementSource(
                    "accepted head changed since the settlement candidate was built"
                )

            active_admission = _active_candidate_admission(
                plans_dir=plans_dir, slug=slug, accepted_version_id=fresh_accepted.record.version_id
            )
            if active_admission is not None:
                assert active_admission.active_candidate_version_id is not None
                binding = _settlement_confirmation_binding(candidate_result, active_admission)
                if confirmed_binding is None:
                    confirmation_bytes = _confirmation_bytes(binding)
                    final_name = hashlib.sha256(confirmation_bytes).hexdigest()
                    stored = publish_evidence(
                        roadmap_dir(plans_dir, slug), EvidenceNamespace.DECISION_SETTLEMENTS,
                        final_name, confirmation_bytes,
                    )
                    if stored.outcome not in {EVIDENCE_CREATED, EVIDENCE_EXISTING} or stored.data != confirmation_bytes:
                        return _result("write-failed")
                    return _confirmation_result(
                        _result("preflight-rejected", "confirmation-required"),
                        final_name=final_name, binding=binding,
                    )
                if confirmed_binding != binding:
                    return _result("preflight-rejected", "confirmation-required")
            elif confirmed_binding is not None:
                return _result("preflight-rejected", "confirmation-required")
            elif confirmation is not True:
                return _result("preflight-rejected", "confirmation-required")

            prepared = _build_settlement_version(
                slug=slug, accepted=fresh_accepted, candidate=candidate_result
            )

            gate_outcomes = check_complete_roadmap_gates(
                _settlement_gate_evidence(
                    prepared, brief_bytes=fresh_accepted.brief_bytes, stages=stages
                ),
                stages=stages,
            )
            if len(gate_outcomes) != len(stages) or any(
                not isinstance(outcome, RoadmapGateOutcome)
                or outcome.stage is not stage
                or outcome.violations
                for outcome, stage in zip(gate_outcomes, stages, strict=True)
            ):
                return _result("preflight-rejected", "settled-content-fails-gates")

            root = roadmap_dir(plans_dir, slug)
            generation = _build_settlement_generation(
                plans_dir=plans_dir,
                slug=slug,
                prepared=prepared,
                old_selector_bytes=old_selector_bytes,
            )
            if active_admission is not None:
                # The released candidate never becomes the root, so its history
                # gets the same immutable terminal record rejection and discard
                # write, with reason ``settled``. The new root's derived-context
                # set needs no write: entries are keyed by ``source_version_id``,
                # so a root nothing has stored against selects an empty set and
                # never inherits the released candidate's.
                released_candidate = load_stored_candidate_proposal(
                    plans_dir=plans_dir,
                    slug=slug,
                    candidate_version_id=active_admission.active_candidate_version_id,
                )
                release = build_terminal_resolution_generation(
                    plans_dir=plans_dir,
                    slug=slug,
                    admission=active_admission,
                    resolution=new_terminal_resolution(released_candidate, reason="settled"),
                )
                generation = PendingGeneration(
                    kind=generation.kind,
                    members=(*generation.members[:-1], *release.members, generation.members[-1]),
                )

            receipt = build_decision_settlement_receipt(
                candidate_result, resulting_version_id=prepared.record.version_id
            )
            publication = publish_decision_settlement_receipt(
                receipt,
                plans_dir=plans_dir,
                slug=slug,
                receipt_committer=receipt_committer,
            )
            if publication.outcome not in DECISION_SETTLEMENT_RECEIPT_SUCCESS_OUTCOMES:
                return _result("receipt-rejected", publication.outcome)
            receipt_id = publication.receipt_id

            if active_admission is None and _admission_blocks_settlement(plans_dir=plans_dir, slug=slug):
                return _result(
                    "preflight-rejected", "unpromoted-candidate-lineage", receipt_id=receipt_id
                )
            if active_admission is not None and _active_candidate_admission(
                plans_dir=plans_dir, slug=slug,
                accepted_version_id=candidate_result.accepted_version_id,
            ) != active_admission:
                return _result("preflight-rejected", "confirmation-required", receipt_id=receipt_id)
            if not decision_settlement_candidate_is_current(
                candidate_result, plans_dir=plans_dir, slug=slug, stages=stages
            ):
                return _result(
                    "preflight-rejected", "source-changed", receipt_id=receipt_id
                )

            def _before_replace() -> None:
                try:
                    current_selector_bytes = selector_path.read_bytes()
                except OSError as exc:
                    raise _StaleEnrolledDecisionSettlementSource from exc
                if current_selector_bytes != old_selector_bytes:
                    raise _StaleEnrolledDecisionSettlementSource(
                        "accepted head changed inside the publication window"
                    )
                if active_admission is not None and _active_candidate_admission(
                    plans_dir=plans_dir, slug=slug,
                    accepted_version_id=candidate_result.accepted_version_id,
                ) != active_admission:
                    raise _StaleEnrolledDecisionSettlementSource(
                        "active candidate changed inside the publication window"
                    )
                for member in generation.members[:-1]:
                    if member.old_bytes is None:
                        _reject_existing_member(root / member.relative_path)

            publish_roadmap_generation(
                generation,
                plans_dir=plans_dir,
                slug=slug,
                writer_token=writer_token,
                before_replace=_before_replace,
            )
            refresh_roadmap_index(plans_dir, slug)
    except _StaleEnrolledDecisionSettlementSource:
        return _result("preflight-rejected", "source-changed", receipt_id=receipt_id)
    except KeyboardInterrupt:
        return _result("interrupted", receipt_id=receipt_id)
    except (
        DecisionSettlementReceiptError,
        CandidateProposalError,
        RoadmapImpactSnapshotError,
    ):
        # Each is an internal-consistency bug, a corrupt admission record,
        # or a corrupt sibling artifact member (surfaced while building
        # gate evidence from the whole accepted version, not just the
        # member being settled) — must not fold into the generic
        # write-failed below. RoadmapVersionError stays out of this
        # carve-out on purpose; see BUG_BACKLOG's "settlement folds a
        # corrupt sibling artifact member into an ordinary write-failed
        # refusal".
        raise
    except (
        OSError,
        RoadmapArtifactError,
        RoadmapRevisionPublishError,
        RoadmapWriterGuardError,
        ValueError,
    ):
        return _result("write-failed", receipt_id=receipt_id)
    return _result("settled", receipt_id=receipt_id)


def _admission_blocks_settlement(*, plans_dir: Path, slug: str) -> bool:
    """Whether the current accepted head still carries an unpromoted selector-era lineage.

    A comparison with the current head only: neither the admission's age nor
    whether it already carries a stored (possibly response-rejected) request
    changes the answer. Clears once the head advances past the admission's
    ``predecessor_version_id`` — the observable effect of promotion. A ledger-batch
    pointer (``root_version_id`` set) never blocks: it is judged by its active
    candidate, so one released by rejection or discard names no lineage.
    """
    admission = load_candidate_admission(plans_dir=plans_dir, slug=slug)
    if admission is None or admission.root_version_id is not None:
        return False
    head = load_accepted_head(plans_dir=plans_dir, slug=slug)
    return head is not None and admission.predecessor_version_id == head.version_id


def _active_candidate_admission(
    *, plans_dir: Path, slug: str, accepted_version_id: str
) -> CandidateProposalAdmission | None:
    """Return only step 5's current processing pair, never a legacy admission."""
    admission = load_candidate_admission(plans_dir=plans_dir, slug=slug)
    if (
        admission is None
        or admission.root_version_id != accepted_version_id
        or admission.active_candidate_version_id is None
    ):
        return None
    return admission


def _settlement_confirmation_binding(
    candidate: DecisionSettlementCandidate, admission: CandidateProposalAdmission
) -> _ConfirmedActiveCandidateBinding:
    """Bind one response to the exact source, active candidate, and settlement."""
    assert admission.active_candidate_version_id is not None
    identity = decision_settlement_content_identity(
        predecessor_version_id=candidate.accepted_version_id,
        artifact_key=candidate.selector.artifact_key,
        decision_id=candidate.selector.decision_id,
        feedback_id=candidate.selector.feedback_id,
        evidence_digest=candidate.evidence_digest,
    )
    return _ConfirmedActiveCandidateBinding(
        candidate.accepted_version_id,
        admission.active_candidate_version_id,
        identity,
        f"{candidate.selector.artifact_key}:{candidate.selector.decision_id}",
        f"{candidate.selector.artifact_key}:{candidate.selector.feedback_id}",
    )


def _build_settlement_version(
    *, slug: str, accepted: ResolvedRoadmapVersion, candidate: DecisionSettlementCandidate
) -> PreparedRoadmapVersion:
    """Build the settled candidate version: one member replaced, rest kept."""
    member_index = accepted.artifact_keys.index(candidate.selector.artifact_key)
    artifact_bytes = tuple(
        candidate.settled_bytes if index == member_index else data
        for index, data in enumerate(accepted.artifact_bytes)
    )
    content = RoadmapVersionContent(brief_bytes=accepted.brief_bytes, artifact_bytes=artifact_bytes)
    record = create_candidate_version(
        roadmap_slug=slug,
        predecessor_version_id=accepted.record.version_id,
        content_identity=decision_settlement_content_identity(
            predecessor_version_id=accepted.record.version_id,
            artifact_key=candidate.selector.artifact_key,
            decision_id=candidate.selector.decision_id,
            feedback_id=candidate.selector.feedback_id,
            evidence_digest=candidate.evidence_digest,
        ),
        review_lineage_identity=DECISION_SETTLEMENT_NO_REVIEW_LINEAGE_ID,
        brief_digest=accepted.record.brief_digest,
        # Reuse each unchanged member's already-verified digest (parallel to
        # artifact_bytes, same fixed VERSION_ARTIFACT_INVENTORY order) and
        # the changed member's already-computed settled_digest, rather than
        # re-hashing every member's bytes a second time.
        artifact_digests=tuple(
            candidate.settled_digest if index == member_index else member.digest
            for index, member in enumerate(accepted.record.artifact_members)
        ),
    )
    return PreparedRoadmapVersion(record=record, content=content)


def _settlement_gate_evidence(
    prepared: PreparedRoadmapVersion, *, brief_bytes: bytes, stages: Sequence[RoadmapStage]
) -> CompleteRoadmapGateEvidence:
    texts = tuple(data.decode("utf-8") for data in prepared.content.artifact_bytes)
    return CompleteRoadmapGateEvidence(
        artifact_keys=tuple(stage.artifact_key for stage in stages),
        artifact_texts=texts,
        artifacts=_parse_settlement_artifacts(texts, stages=stages),
        artifact_digests=tuple(member.digest for member in prepared.record.artifact_members),
        brief_bytes=brief_bytes,
    )


def _parse_settlement_artifacts(
    texts: tuple[str, ...], *, stages: Sequence[RoadmapStage]
) -> tuple[Any, ...]:
    parsed: list[Any] = []
    for stage, text in zip(stages, texts, strict=True):
        try:
            parsed.append(stage.parse(text))
        except (
            AttributeError,
            RoadmapArtifactError,
            TypeError,
            UnicodeError,
            ValueError,
        ) as exc:
            raise RoadmapImpactSnapshotError(
                f"settlement artifact for stage {stage.artifact_key} cannot be parsed"
            ) from exc
    return tuple(parsed)


def _build_settlement_generation(
    *, plans_dir: Path, slug: str, prepared: PreparedRoadmapVersion, old_selector_bytes: bytes
) -> PendingGeneration:
    """Build the six stored-version members, then the selector swap, last."""
    root = roadmap_dir(plans_dir, slug)
    version_dir = version_directory_path(plans_dir, slug, prepared.record.version_id)
    members: list[GenerationMember] = []
    for member in stored_version_members(prepared):
        path = version_dir / member.member_name
        _reject_existing_member(path)
        members.append(GenerationMember(path.relative_to(root).as_posix(), None, member.data))
    selector_path = accepted_head_path(plans_dir, slug)
    new_head = AcceptedRoadmapHead(
        schema_version=ROADMAP_VERSION_SCHEMA_VERSION,
        roadmap_slug=slug,
        version_id=prepared.record.version_id,
    )
    members.append(
        GenerationMember(
            selector_path.relative_to(root).as_posix(),
            old_selector_bytes,
            render_accepted_head(new_head),
        )
    )
    return PendingGeneration(kind=DECISION_SETTLEMENT_GENERATION_KIND, members=tuple(members))


def _reject_existing_member(path: Path) -> None:
    try:
        path.read_bytes()
    except FileNotFoundError:
        if path.is_symlink():
            raise RoadmapVersionError(
                f"decision settlement member {path} is a dangling symlink"
            ) from None
        return
    except OSError as exc:
        raise RoadmapVersionError(f"cannot read decision settlement member at {path}") from exc
    raise RoadmapVersionError(f"decision settlement cannot replace stored version members: {path}")
