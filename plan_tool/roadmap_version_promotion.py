"""Promote one exact sealed roadmap candidate by changing only its selector."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from plan_tool import roadmap_candidate, roadmap_candidate_review, roadmap_candidate_run
from plan_tool.roadmap import STAGES, refresh_roadmap_index
from plan_tool.roadmap_artifacts import roadmap_dir
from plan_tool.roadmap_impact_snapshot import (
    CompleteRoadmapGateEvidence,
    RoadmapGateOutcome,
    RoadmapImpactSnapshotError,
    check_complete_roadmap_gates,
)
from plan_tool.roadmap_revision_publish import (
    RoadmapWriterToken,
    build_enrolled_promotion_seed_state_member,
    publish_roadmap_generation,
    require_roadmap_writer_token,
)
from plan_tool.roadmap_source_identity import (
    GenerationMember,
    PendingGeneration,
    load_pending_generation,
    pending_generation_path,
)
from plan_tool.roadmap_versions import (
    ROADMAP_VERSION_SCHEMA_VERSION,
    AcceptedRoadmapHead,
    ResolvedRoadmapVersion,
    RoadmapVersionError,
    accepted_head_path,
    load_accepted_head,
    load_accepted_version,
    parse_accepted_head,
    render_accepted_head,
)


class RoadmapVersionPromotionError(ValueError):
    """A seal cannot safely move the accepted roadmap version."""


class StaleRoadmapVersionPromotionError(RoadmapVersionPromotionError):
    """The seal's predecessor is no longer the accepted version."""


PROMOTION_OUTCOME_PROMOTED = "promoted"
PROMOTION_OUTCOME_ALREADY_PROMOTED = "already-promoted"

ReviewSealPromotionOutcome = Literal["promoted", "already-promoted"]


@dataclass(frozen=True)
class ReviewSealPromotionResult:
    """The accepted head and whether this call had already promoted it."""

    head: AcceptedRoadmapHead
    outcome: ReviewSealPromotionOutcome

    @property
    def version_id(self) -> str:
        """Keep callers focused on the selected immutable version."""
        return self.head.version_id


def promote_review_seal(
    *,
    plans_dir: Path,
    slug: str,
    seal_id: str,
    writer_token: RoadmapWriterToken,
) -> ReviewSealPromotionResult:
    """Promote only the exact candidate named by one immutable review seal."""
    require_roadmap_writer_token(writer_token, plans_dir=plans_dir, slug=slug)

    try:
        seal = roadmap_candidate_review.load_review_seal(
            plans_dir=plans_dir, slug=slug, seal_id=seal_id
        )
        accepted, accepted_selector, old_selector_bytes = _load_current_accepted_version(
            plans_dir=plans_dir, slug=slug
        )
        if (
            seal.decision == "structural-approval"
            and seal.approved_candidate_version_id == accepted.record.version_id
            # A dangling journal means a prior publication never finished; fall through so the
            # normal path's recovery surfaces it instead of a false already-promoted success.
            and load_pending_generation(pending_generation_path(roadmap_dir(plans_dir, slug))) is None
        ):
            # The version-id match above only narrows to "plausibly already promoted"; the
            # exhaustive check below is what actually authorizes the shortcut.
            already_promoted_candidate = roadmap_candidate_run.load_stored_candidate_proposal(
                plans_dir=plans_dir, slug=slug, candidate_version_id=accepted.record.version_id
            )
            _require_seal_binds_structural_candidate(seal, already_promoted_candidate, slug=slug)
            # An earlier run may have died after its publish and before its index write.
            refresh_roadmap_index(plans_dir, slug)
            return ReviewSealPromotionResult(
                head=accepted_selector,
                outcome=PROMOTION_OUTCOME_ALREADY_PROMOTED,
            )
        candidate, admission, initial = _load_complete_sealed_candidate(
            plans_dir=plans_dir, slug=slug, seal=seal
        )
        source = _require_current_active_processing_pair(
            candidate=candidate,
            admission=admission,
            accepted=accepted,
            initial=initial,
            plans_dir=plans_dir,
            slug=slug,
        )
        _recheck_stored_candidate(
            candidate=candidate,
            source=source,
            initial=initial,
        )
        stack_is_structural = _promoted_stack_is_structural(
            plans_dir=plans_dir, slug=slug, candidate=candidate
        )
        if stack_is_structural and seal.decision != "structural-approval":
            raise RoadmapVersionPromotionError("structural candidate requires --decide-candidate")
    except (
        roadmap_candidate_review.CandidateReviewError,
        roadmap_candidate_run.CandidateProposalError,
        RoadmapImpactSnapshotError,
        RoadmapVersionError,
        OSError,
        UnicodeError,
        ValueError,
    ) as exc:
        if isinstance(exc, RoadmapVersionPromotionError):
            raise
        raise RoadmapVersionPromotionError(str(exc)) from exc

    promoted_head = AcceptedRoadmapHead(
        schema_version=ROADMAP_VERSION_SCHEMA_VERSION,
        roadmap_slug=slug,
        version_id=candidate.record.version_id,
    )
    selector_path = accepted_head_path(plans_dir, slug)
    release = (
        roadmap_candidate_run.build_active_candidate_pointer_release_generation(
            plans_dir=plans_dir, slug=slug, admission=admission
        )
        if admission.root_version_id is not None
        else None
    )
    seed_member = _structural_promotion_seed_member(
        plans_dir=plans_dir,
        slug=slug,
        candidate=candidate,
        stack_is_structural=stack_is_structural,
        writer_token=writer_token,
    )
    generation = PendingGeneration(
        kind="review-seal-promotion",
        members=(
            GenerationMember(
                selector_path.relative_to(selector_path.parent.parent).as_posix(),
                old_selector_bytes,
                render_accepted_head(promoted_head),
            ),
        ) + (() if release is None else release.members) + (() if seed_member is None else (seed_member,)),
    )

    def final_recheck() -> None:
        try:
            current = load_accepted_head(plans_dir=plans_dir, slug=slug)
        except RoadmapVersionError as exc:
            raise StaleRoadmapVersionPromotionError(
                "accepted-head selector changed before promotion"
            ) from exc
        if (
            current is None
            or current.version_id != accepted.record.version_id
            or render_accepted_head(current) != old_selector_bytes
        ):
            raise StaleRoadmapVersionPromotionError(
                "accepted-head selector no longer names the sealed candidate root"
            )
        if admission.root_version_id is not None:
            current_admission = roadmap_candidate_run.load_candidate_admission(
                plans_dir=plans_dir, slug=slug
            )
            if current_admission != admission:
                raise StaleRoadmapVersionPromotionError(
                    "active candidate pointer changed before promotion"
                )
        try:
            current_seal = roadmap_candidate_review.load_review_seal(
                plans_dir=plans_dir, slug=slug, seal_id=seal_id
            )
        except (roadmap_candidate_review.CandidateReviewError, OSError, ValueError) as exc:
            raise StaleRoadmapVersionPromotionError(
                "review seal changed before promotion"
            ) from exc
        if current_seal != seal:
            raise StaleRoadmapVersionPromotionError("review seal changed before promotion")

    publish_roadmap_generation(
        generation,
        plans_dir=plans_dir,
        slug=slug,
        writer_token=writer_token,
        before_replace=final_recheck,
    )
    refresh_roadmap_index(plans_dir, slug)
    return ReviewSealPromotionResult(head=promoted_head, outcome=PROMOTION_OUTCOME_PROMOTED)


def _load_current_accepted_version(
    *, plans_dir: Path, slug: str
) -> tuple[ResolvedRoadmapVersion, AcceptedRoadmapHead, bytes]:
    accepted = load_accepted_version(plans_dir=plans_dir, slug=slug)
    if accepted is None:
        raise RoadmapVersionPromotionError("promotion requires an accepted roadmap head")
    selector_path = accepted_head_path(plans_dir, slug)
    selector_bytes = selector_path.read_bytes()
    selector = parse_accepted_head(selector_bytes)
    if selector.version_id != accepted.record.version_id:
        raise StaleRoadmapVersionPromotionError(
            "accepted-head selector changed while promotion was loading"
        )
    return accepted, selector, selector_bytes


def _load_complete_sealed_candidate(
    *,
    plans_dir: Path,
    slug: str,
    seal: roadmap_candidate_review.CandidateReviewSeal,
) -> tuple[
    roadmap_candidate_review.StoredCandidateReviewReplacement | roadmap_candidate_run.StoredCandidateProposal,
    roadmap_candidate_run.CandidateProposalAdmission,
    roadmap_candidate_run.StoredCandidateProposal,
]:
    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug=slug)
    if admission is None:
        raise RoadmapVersionPromotionError(
            "review seal does not bind the immutable admitted initial candidate"
        )
    if seal.decision == "structural-approval":
        return _load_complete_directly_approved_candidate(
            plans_dir=plans_dir, slug=slug, seal=seal, admission=admission
        )

    is_batch = seal.batch_receipt_identity is not None
    if is_batch:
        initial = _load_reviewed_batch_candidate(
            plans_dir=plans_dir, slug=slug, seal=seal, admission=admission
        )
    else:
        if admission.candidate_version_id != seal.initial_candidate_version_id:
            raise RoadmapVersionPromotionError(
                "review seal does not bind the immutable admitted initial candidate"
            )
        initial = roadmap_candidate_run.load_stored_candidate_proposal(
            plans_dir=plans_dir,
            slug=slug,
            candidate_version_id=seal.initial_candidate_version_id,
        )
    if (initial.evidence.batch_receipt is not None) != is_batch:
        raise RoadmapVersionPromotionError(
            "review seal and reviewed candidate disagree on ledger batch lineage"
        )
    if is_batch:
        roadmap_candidate_review._require_answered_review_route(initial, plans_dir=plans_dir, slug=slug)
    else:
        roadmap_candidate_review._validate_initial_candidate(
            initial, admission=admission, slug=slug
        )

    inventory = _load_question_inventory(plans_dir=plans_dir, slug=slug, initial=initial)
    answer = _load_reviewer_answer(plans_dir=plans_dir, slug=slug, initial=initial)
    roadmap_candidate_review._validate_inventory(inventory, initial=initial)
    roadmap_candidate_review._validate_answer(answer, inventory=inventory)
    binding = _load_replacement_binding(plans_dir=plans_dir, slug=slug, initial=initial)
    candidate = roadmap_candidate_review.load_stored_candidate_review_replacement(
        plans_dir=plans_dir,
        slug=slug,
        candidate_version_id=seal.replacement_candidate_version_id,
    )
    roadmap_candidate_review._validate_replacement(
        candidate,
        plans_dir=plans_dir,
        slug=slug,
        initial=initial,
        inventory=inventory,
        answer=answer,
    )
    _require_replacement_binding(
        binding=binding,
        candidate=candidate,
        inventory=inventory,
        answer=answer,
        initial=initial,
    )
    if not is_batch:
        _require_final_capsule_binding(
            plans_dir=plans_dir,
            slug=slug,
            candidate=candidate,
            initial=initial,
        )
    _require_seal_bindings(
        seal=seal,
        candidate=candidate,
        initial=initial,
        inventory=inventory,
        answer=answer,
    )
    return candidate, admission, initial


def _load_complete_directly_approved_candidate(
    *,
    plans_dir: Path,
    slug: str,
    seal: roadmap_candidate_review.CandidateReviewSeal,
    admission: roadmap_candidate_run.CandidateProposalAdmission,
) -> tuple[
    roadmap_candidate_run.StoredCandidateProposal,
    roadmap_candidate_run.CandidateProposalAdmission,
    roadmap_candidate_run.StoredCandidateProposal,
]:
    """Load the active structural candidate named by a direct approval seal."""
    candidate_version_id = seal.approved_candidate_version_id
    if candidate_version_id is None or admission.candidate_version_id != candidate_version_id:
        raise RoadmapVersionPromotionError(
            "structural approval does not bind the active candidate"
        )
    candidate = roadmap_candidate_run.load_stored_candidate_proposal(
        plans_dir=plans_dir, slug=slug, candidate_version_id=candidate_version_id
    )
    roadmap_candidate_review._validate_initial_candidate(candidate, admission=admission, slug=slug)
    roadmap_candidate_review._require_structural_candidate(candidate, plans_dir=plans_dir, slug=slug)
    _require_seal_binds_structural_candidate(seal, candidate, slug=slug)
    return candidate, admission, candidate


def _require_seal_binds_structural_candidate(
    seal: roadmap_candidate_review.CandidateReviewSeal,
    candidate: roadmap_candidate_run.StoredCandidateProposal,
    *,
    slug: str,
) -> None:
    """Raise unless every binding field a structural-approval seal carries names this exact candidate.

    Shared by the active-candidate slow path and the already-promoted shortcut above, so a seal that
    lies about any bound field (root/source/batch lineage, the final capsule) is refused the same way
    regardless of which path reaches it.
    """
    evidence = candidate.evidence
    capsule_identity = cast(Any, evidence.capsule).capsule_identity
    batch_binding = (
        evidence.root_version_id,
        evidence.source_version_id,
        None if evidence.batch_receipt is None else evidence.batch_receipt.capsule_identity,
    )
    if (
        seal.roadmap_slug != slug
        or seal.initial_candidate_version_id != candidate.version_id
        or seal.approved_candidate_version_id != candidate.version_id
        or seal.approved_content_identity != candidate.record.content_identity
        or seal.final_capsule_identity != capsule_identity
        or (seal.root_version_id, seal.source_version_id, seal.batch_receipt_identity)
        != batch_binding
    ):
        raise RoadmapVersionPromotionError(
            "structural approval does not bind the exact active candidate"
        )


def _promoted_stack_is_structural(
    *,
    plans_dir: Path,
    slug: str,
    candidate: roadmap_candidate_review.StoredCandidateReviewReplacement
    | roadmap_candidate_run.StoredCandidateProposal,
) -> bool:
    """Whether the promoted candidate's unpromoted stack stores a STRUCTURAL route.

    Recovery asks the same question with the same two ids (`_selected_promotion_is_structural`).
    See docs/implementation-plans/archive/2-roadmap-stack-aware-approval.md § "Architecture" (Stack route).
    """
    return roadmap_candidate_run.candidate_stack_route(
        plans_dir=plans_dir, slug=slug,
        tip_version_id=candidate.version_id, root_version_id=candidate.evidence.root_version_id,
    ).is_structural


def _structural_promotion_seed_member(
    *,
    plans_dir: Path,
    slug: str,
    candidate: roadmap_candidate_review.StoredCandidateReviewReplacement
    | roadmap_candidate_run.StoredCandidateProposal,
    stack_is_structural: bool,
    writer_token: RoadmapWriterToken,
) -> GenerationMember | None:
    """Attach seed invalidation to every promotion whose unpromoted stack is structural."""
    if not stack_is_structural:
        return None
    try:
        promoted_plans = STAGES[-1].parse(candidate.content.artifact_bytes[-1].decode("utf-8"))
    except (AttributeError, IndexError, UnicodeError, ValueError) as exc:
        raise RoadmapVersionPromotionError(
            "approved structural candidate has an unreadable plans artifact"
        ) from exc
    return build_enrolled_promotion_seed_state_member(
        plans_dir=plans_dir,
        slug=slug,
        promoted_plans=promoted_plans,
        writer_token=writer_token,
    )


def _load_reviewed_batch_candidate(
    *,
    plans_dir: Path,
    slug: str,
    seal: roadmap_candidate_review.CandidateReviewSeal,
    admission: roadmap_candidate_run.CandidateProposalAdmission,
) -> roadmap_candidate_run.StoredCandidateProposal:
    """Load the reviewed candidate as history once its sealed replacement is the active one."""
    if (
        admission.root_version_id is None
        or admission.active_candidate_version_id != seal.replacement_candidate_version_id
    ):
        raise RoadmapVersionPromotionError(
            "review seal does not bind the active replacement candidate"
        )
    initial = roadmap_candidate_run.load_stored_candidate_proposal(
        plans_dir=plans_dir,
        slug=slug,
        candidate_version_id=seal.initial_candidate_version_id,
    )
    supersession = roadmap_candidate_run.load_candidate_supersession(
        plans_dir=plans_dir, slug=slug, superseded_candidate_version_id=initial.version_id
    )
    if (
        supersession.root_version_id != admission.root_version_id
        or supersession.successor_candidate_version_id != seal.replacement_candidate_version_id
    ):
        raise RoadmapVersionPromotionError(
            "review seal replacement is not the recorded successor of the reviewed candidate"
        )
    return initial


def _load_question_inventory(
    *,
    plans_dir: Path,
    slug: str,
    initial: roadmap_candidate_run.StoredCandidateProposal,
) -> roadmap_candidate_review.CandidateQuestionInventory:
    path = roadmap_candidate_review.question_inventory_path(plans_dir, slug, initial.version_id)
    try:
        return roadmap_candidate_review.parse_question_inventory(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise RoadmapVersionPromotionError("candidate question inventory is unreadable") from exc


def _load_reviewer_answer(
    *,
    plans_dir: Path,
    slug: str,
    initial: roadmap_candidate_run.StoredCandidateProposal,
) -> roadmap_candidate_review.CandidateReviewAnswer:
    path = roadmap_candidate_review.reviewer_answer_path(plans_dir, slug, initial.version_id)
    try:
        return roadmap_candidate_review.parse_reviewer_answer(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise RoadmapVersionPromotionError("candidate reviewer answer is unreadable") from exc


def _load_replacement_binding(
    *,
    plans_dir: Path,
    slug: str,
    initial: roadmap_candidate_run.StoredCandidateProposal,
) -> roadmap_candidate_review.CandidateReviewReplacementBinding:
    path = roadmap_candidate_review.replacement_binding_path(plans_dir, slug, initial.version_id)
    try:
        return roadmap_candidate_review.parse_replacement_binding(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise RoadmapVersionPromotionError("candidate replacement binding is unreadable") from exc


def _require_replacement_binding(
    *,
    binding: roadmap_candidate_review.CandidateReviewReplacementBinding,
    candidate: roadmap_candidate_review.StoredCandidateReviewReplacement,
    inventory: roadmap_candidate_review.CandidateQuestionInventory,
    answer: roadmap_candidate_review.CandidateReviewAnswer,
    initial: roadmap_candidate_run.StoredCandidateProposal,
) -> None:
    if (
        binding.initial_candidate_version_id != initial.version_id
        or binding.inventory_id != inventory.inventory_id
        or binding.question_id != inventory.question.question_id
        or binding.answer_id != answer.answer_id
        or binding.candidate_version_id != candidate.version_id
    ):
        raise RoadmapVersionPromotionError(
            "candidate replacement binding does not name the sealed review lineage"
        )


def _require_final_capsule_binding(
    *,
    plans_dir: Path,
    slug: str,
    candidate: roadmap_candidate_review.StoredCandidateReviewReplacement,
    initial: roadmap_candidate_run.StoredCandidateProposal,
) -> None:
    path = roadmap_candidate_review.replacement_state_path(plans_dir, slug, initial.version_id)
    if not path.exists() and not path.is_symlink():
        if (
            candidate.evidence.capsule != initial.evidence.capsule
            or candidate.evidence.receipt != initial.evidence.receipt
        ):
            raise RoadmapVersionPromotionError(
                "replacement final capsule is not the immutable admitted capsule"
            )
        return
    try:
        state = roadmap_candidate_review.parse_replacement_state(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise RoadmapVersionPromotionError("candidate replacement state is unreadable") from exc
    if (
        state.initial_candidate_version_id != initial.version_id
        or state.initial_content_identity != initial.evidence.content_identity
        or state.predecessor_version_id != initial.evidence.predecessor_version_id
        or state.feedback != initial.evidence.feedback
        or state.capsule != candidate.evidence.capsule
        or state.receipt != candidate.evidence.receipt
    ):
        raise RoadmapVersionPromotionError(
            "replacement final capsule does not bind the sealed candidate"
        )


def _require_seal_bindings(
    *,
    seal: roadmap_candidate_review.CandidateReviewSeal,
    candidate: roadmap_candidate_review.StoredCandidateReviewReplacement,
    initial: roadmap_candidate_run.StoredCandidateProposal,
    inventory: roadmap_candidate_review.CandidateQuestionInventory,
    answer: roadmap_candidate_review.CandidateReviewAnswer,
) -> None:
    evidence = candidate.evidence
    if seal.batch_receipt_identity is None:
        final_capsule_identity = cast(Any, evidence.capsule).capsule_identity
        expected_batch_binding: tuple[str | None, ...] = (None, None, None)
    else:
        # A batch replacement's capsule is the reviewed candidate's own.
        final_capsule_identity = cast(Any, initial.evidence.capsule).capsule_identity
        expected_batch_binding = (
            evidence.root_version_id,
            evidence.source_version_id,
            evidence.batch_receipt_identity,
        )
    if (
        seal.roadmap_slug != initial.record.roadmap_slug
        or seal.initial_candidate_version_id != initial.version_id
        or seal.question_inventory_id != inventory.inventory_id
        or seal.answer_ids != (answer.answer_id,)
        or seal.replacement_candidate_version_id != candidate.version_id
        or seal.replacement_content_identity != candidate.record.content_identity
        or seal.answer_incorporation_id != evidence.answer_incorporation.incorporation_id
        or seal.final_capsule_identity != final_capsule_identity
        or (seal.root_version_id, seal.source_version_id, seal.batch_receipt_identity)
        != expected_batch_binding
        or evidence.candidate_version_id != candidate.version_id
        or evidence.content_identity != candidate.record.content_identity
        or evidence.answer_incorporation.inventory_id != inventory.inventory_id
        or evidence.answer_incorporation.question_id != inventory.question.question_id
        or evidence.answer_incorporation.answer_id != answer.answer_id
    ):
        raise RoadmapVersionPromotionError(
            "review seal does not bind the exact replacement candidate evidence"
        )


def _require_current_active_processing_pair(
    *,
    candidate: roadmap_candidate_review.StoredCandidateReviewReplacement
    | roadmap_candidate_run.StoredCandidateProposal,
    admission: roadmap_candidate_run.CandidateProposalAdmission,
    accepted: ResolvedRoadmapVersion,
    initial: roadmap_candidate_run.StoredCandidateProposal,
    plans_dir: Path,
    slug: str,
) -> ResolvedRoadmapVersion:
    """Bind a sealed replacement to the current root and the active candidate.

    A ledger batch's active candidate is the sealed replacement itself; the reviewed
    candidate it superseded is history.
    """
    if admission.root_version_id is None:
        if candidate.record.predecessor_version_id != accepted.record.version_id:
            raise StaleRoadmapVersionPromotionError(
                "sealed candidate predecessor is not the current accepted roadmap head"
            )
        return accepted
    evidence = initial.evidence
    if (
        admission.root_version_id != accepted.record.version_id
        or admission.predecessor_version_id != accepted.record.version_id
        or admission.active_candidate_version_id != candidate.version_id
        or admission.candidate_version_id != candidate.version_id
        or evidence.batch_receipt is None
        or evidence.root_version_id != accepted.record.version_id
        or evidence.source_version_id != evidence.predecessor_version_id
        or evidence.batch_receipt.root.version_id != accepted.record.version_id
        or evidence.batch_receipt.source.version_id != evidence.source_version_id
        or candidate.record.predecessor_version_id != evidence.source_version_id
    ):
        raise StaleRoadmapVersionPromotionError(
            "sealed candidate no longer matches the current root and active candidate"
        )
    source = roadmap_candidate_run._load_resolved_version(
        plans_dir=plans_dir, slug=slug, version_id=evidence.source_version_id
    )
    if source.record.version_id == accepted.record.version_id:
        return accepted
    roadmap_candidate_run.source_ancestry_to_root(
        plans_dir=plans_dir,
        slug=slug,
        source_version_id=source.record.version_id,
        root_version_id=accepted.record.version_id,
    )
    return source


def _recheck_stored_candidate(
    *,
    candidate: roadmap_candidate_review.StoredCandidateReviewReplacement
    | roadmap_candidate_run.StoredCandidateProposal,
    source: ResolvedRoadmapVersion,
    initial: roadmap_candidate_run.StoredCandidateProposal,
) -> None:
    evidence = candidate.evidence
    if (
        hashlib.sha256(candidate.content.brief_bytes).hexdigest() != candidate.record.brief_digest
        or evidence.raw_brief_digest != candidate.record.brief_digest
        or candidate.content.brief_bytes != source.brief_bytes
        or evidence.artifact_digests
        != tuple(member.digest for member in candidate.record.artifact_members)
        or evidence.predecessor_version_id != source.record.version_id
    ):
        raise RoadmapVersionPromotionError(
            "sealed candidate raw bytes do not match their immutable evidence"
        )

    predecessor_artifacts = _parse_stored_artifacts(source.artifact_bytes)
    candidate_artifacts = _parse_stored_artifacts(candidate.content.artifact_bytes)
    candidate_members = tuple(
        roadmap_candidate.CandidateArtifact(
            artifact_key=stage.artifact_key,
            data=data,
            text=text,
            artifact=artifact,
            digest=hashlib.sha256(data).hexdigest(),
        )
        for stage, data, text, artifact in zip(
            STAGES,
            candidate.content.artifact_bytes,
            tuple(data.decode("utf-8") for data in candidate.content.artifact_bytes),
            candidate_artifacts,
            strict=True,
        )
    )
    expected_diff = roadmap_candidate._build_predecessor_diff(
        predecessor_artifacts={
            stage.artifact_key: artifact
            for stage, artifact in zip(STAGES, predecessor_artifacts, strict=True)
        },
        candidate_artifacts={
            stage.artifact_key: artifact
            for stage, artifact in zip(STAGES, candidate_artifacts, strict=True)
        },
        predecessor_bytes=source.artifact_bytes,
        candidate_artifacts_bytes=candidate.content.artifact_bytes,
        stages=STAGES,
    )
    identity_inputs: dict[str, Any]
    requires_reproducible_content_identity = True
    if isinstance(candidate, roadmap_candidate_run.StoredCandidateProposal):
        if evidence.batch_receipt is not None:
            roadmap_candidate_run._require_reproducible_batch_diff(candidate, source)
            roadmap_candidate_run._require_reproducible_batch_operations(candidate, source)
            requires_reproducible_content_identity = False
        identity_inputs = {"selected_feedback": evidence.feedback, "receipt": evidence.receipt}
    elif evidence.batch_receipt_identity is None:
        identity_inputs = {"selected_feedback": evidence.feedback, "receipt": evidence.receipt}
    else:
        # A batch identity binds the responses and derived context it produced,
        # so a tampered persisted patch can never reproduce the recorded identity.
        identity_inputs = {
            "selected_feedback": None,
            "receipt": initial.evidence.batch_receipt,
            "response_patch": evidence.response_patch,
            "derived_feedback": evidence.derived_feedback,
        }
    expected_content_identity = roadmap_candidate._content_identity(
        predecessor_version_id=source.record.version_id,
        artifacts=candidate_members,
        predecessor_diff=expected_diff,
        **identity_inputs,
    )
    if roadmap_candidate._wire_value(evidence.predecessor_diff) != roadmap_candidate._wire_value(
        expected_diff
    ) or (
        requires_reproducible_content_identity
        and (
            evidence.content_identity != expected_content_identity
            or candidate.record.content_identity != expected_content_identity
        )
    ):
        raise RoadmapVersionPromotionError(
            "sealed candidate content identity or predecessor diff is not reproducible"
        )

    gate_evidence = CompleteRoadmapGateEvidence(
        artifact_keys=tuple(stage.artifact_key for stage in STAGES),
        artifact_texts=tuple(member.text for member in candidate_members),
        artifacts=tuple(member.artifact for member in candidate_members),
        artifact_digests=tuple(member.digest for member in candidate_members),
        brief_bytes=candidate.content.brief_bytes,
    )
    outcomes = check_complete_roadmap_gates(gate_evidence, stages=STAGES)
    if (
        len(outcomes) != len(STAGES)
        or any(
            not isinstance(outcome, RoadmapGateOutcome)
            or outcome.stage is not stage
            or outcome.violations
            for outcome, stage in zip(outcomes, STAGES, strict=True)
        )
    ):
        raise RoadmapVersionPromotionError(
            "sealed candidate does not pass the complete stored roadmap gate walk"
        )
    expected_gate_evidence = tuple(
        roadmap_candidate_run.CandidateGateEvidence(
            artifact_key=outcome.stage.artifact_key,
            violations=tuple(violation.message for violation in outcome.violations),
        )
        for outcome in outcomes
    )
    if evidence.gate_evidence != expected_gate_evidence:
        raise RoadmapVersionPromotionError(
            "sealed candidate does not pass the complete stored roadmap gate walk"
        )


def _parse_stored_artifacts(artifact_bytes: tuple[bytes, ...]) -> tuple[object, ...]:
    if len(artifact_bytes) != len(STAGES):
        raise RoadmapVersionPromotionError(
            "stored candidate does not retain every roadmap stage artifact"
        )
    parsed: list[object] = []
    for stage, data in zip(STAGES, artifact_bytes, strict=True):
        try:
            text = data.decode("utf-8")
            parsed.append(stage.parse(text))
        except (AttributeError, TypeError, UnicodeError, ValueError) as exc:
            raise RoadmapVersionPromotionError(
                f"stored artifact for stage {stage.artifact_key} is unreadable"
            ) from exc
    return tuple(parsed)
