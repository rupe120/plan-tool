"""Tests for selector-only promotion of one sealed immutable candidate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from plan_tool import (
    roadmap_candidate,
    roadmap_candidate_review,
    roadmap_candidate_run,
    roadmap_revision_publish,
    roadmap_version_promotion,
)
from plan_tool.roadmap import STAGES
from plan_tool.roadmap_artifacts import (
    AttributeDispositionRow,
    ComponentRow,
    ComponentsArtifact,
    ConstraintDisposition,
    ConstraintRow,
    ConstraintsArtifact,
    DomainArtifact,
    EntityRow,
    FeedbackRow,
    FeedbackState,
    FeedbackTarget,
    FeedbackTargetKind,
    FieldRow,
    FieldType,
    OrderingEntry,
    PatternRow,
    PlanDisposition,
    PlanRow,
    PlansArtifact,
)
from plan_tool.roadmap_feedback_ledger import roadmap_feedback_ledger_path
from plan_tool.roadmap_impact_snapshot import RoadmapGateOutcome
from plan_tool.roadmap_gates import Violation
from plan_tool.roadmap_revision_publish import (
    RoadmapPublicationRecoveryError,
    RoadmapWriterGuardError,
    publish_roadmap_generation,
    recover_roadmap_publication,
    roadmap_writer_guard,
)
from plan_tool.roadmap_source_identity import PendingGeneration, pending_generation_path, render_pending_generation
from plan_tool.roadmap_seed_state import load_seed_state, seed_state_path, write_seed_state
from plan_tool.roadmap_versions import (
    ROADMAP_VERSION_SCHEMA_VERSION,
    AcceptedRoadmapHead,
    PreparedRoadmapVersion,
    RoadmapVersionContent,
    accepted_head_path,
    build_root_enrollment_generation,
    create_root_version,
    load_accepted_version,
    render_accepted_head,
    stored_artifact_path,
    stored_brief_path,
    version_namespace_path,
)
from tests.test_roadmap_candidate_review import (
    _BATCH_ANSWER,
    _batch_question_response,
    _batch_replacement_response,
    _batch_review,
    _confirming_digest,
    _request_batch_replacement,
    _structural_batch_delta,
)
from tests.test_roadmap_candidate_run import (
    _FIRST_BATCH_DELTA,
    _SECOND_BATCH_DELTA,
    _approve_structural_candidate,
    _edit_stored_evidence,
    _run_batch,
    _seed_batch_ledger,
    _store_stack,
    _write_open_item_ledger,
)


_SLUG = "storefront"
_SELECTOR = "domain:feedback-order"
_PRESENTATION_ONLY = roadmap_candidate.CandidateOperationClassification.PRESENTATION_ONLY


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _root() -> PreparedRoadmapVersion:
    domain = DomainArtifact(
        entities=(
            EntityRow(
                "entity-order",
                "Order",
                (FieldRow("customer", FieldType.REFERENCE, "entity-customer"),),
            ),
            EntityRow("entity-customer", "Customer", ()),
            EntityRow("entity-compact", "Compact", ()),
        ),
        business_rules=(),
        workflows=(),
        decisions=(),
        body="domain\n",
        feedback=(
            FeedbackRow(
                "feedback-order",
                FeedbackTarget(FeedbackTargetKind.ROW, "entity-order"),
                "Use the customer-facing order name.",
                FeedbackState.OPEN,
            ),
        ),
    )
    constraints = ConstraintsArtifact(
        dispositions=(
            AttributeDispositionRow(
                "disposition-security", "security", ConstraintDisposition.PRIORITIZED
            ),
        ),
        constraints=(
            ConstraintRow("constraint-order", "Protect orders.", "security", ("entity-order",)),
        ),
        decisions=(),
        body="constraints\n",
    )
    components = ComponentsArtifact(
        system_patterns=(PatternRow("pattern-order", "Order", "Keep orders coherent."),),
        component_patterns=(),
        components=(
            ComponentRow(
                "component-order",
                "Order service",
                ("entity-order",),
                ("pattern-order",),
                ("constraint-order",),
            ),
        ),
        decisions=(),
        body="components\n",
    )
    plans = PlansArtifact(
        plans=(
            PlanRow(
                "plan-order",
                "Deliver orders",
                PlanDisposition.KEEP,
                ("component-order",),
                "plan-seed-drafts/plan-order.md",
                "Keep the slice small.",
            ),
        ),
        ordering=(OrderingEntry("plan-order"),),
        assumptions=(),
        decisions=(),
        body="plans\n",
    )
    artifact_bytes = tuple(
        stage.render(artifact).encode("utf-8")
        for stage, artifact in zip(
            STAGES, (domain, constraints, components, plans), strict=True
        )
    )
    brief_bytes = b"Recorded brief\n"
    return PreparedRoadmapVersion(
        record=create_root_version(
            roadmap_slug=_SLUG,
            brief_digest=_digest(brief_bytes),
            artifact_digests=tuple(_digest(value) for value in artifact_bytes),
        ),
        content=RoadmapVersionContent(brief_bytes=brief_bytes, artifact_bytes=artifact_bytes),
    )


def _enroll(tmp_path: Path) -> PreparedRoadmapVersion:
    root = _root()
    with roadmap_writer_guard(tmp_path / "plans", _SLUG) as token:
        publish_roadmap_generation(
            build_root_enrollment_generation(root, plans_dir=tmp_path / "plans", slug=_SLUG),
            plans_dir=tmp_path / "plans",
            slug=_SLUG,
            writer_token=token,
        )
    return root


def _green_gates(_evidence, *, stages=STAGES):
    return tuple(RoadmapGateOutcome(stage, ()) for stage in stages)


def _delta_response() -> str:
    return json.dumps(
        {
            "delta": {
                "operations": [
                    {
                        "op": "replace-row",
                        "feedback_id": "feedback-order",
                        "artifact_key": "domain",
                        "row_type": "entities",
                        "row_id": "entity-order",
                        "row": {
                            "id": "entity-order",
                            "name": "Customer order",
                            "fields": [
                                {
                                    "name": "customer",
                                    "type": "reference",
                                    "entity_id": "entity-customer",
                                }
                            ],
                        },
                    }
                ]
            }
        }
    )


def _review_required_delta_response() -> str:
    return json.dumps(
        {
            "delta": {
                "operations": [
                    {
                        "op": "replace-row",
                        "feedback_id": "feedback-order",
                        "artifact_key": "domain",
                        "row_type": "entities",
                        "row_id": "entity-order",
                        "row": {
                            "id": "entity-order",
                            "name": "Order",
                            "fields": [],
                        },
                    }
                ]
            }
        }
    )


def _eliminated_review_requirement_delta_response() -> str:
    return _delta_response().replace("Customer order", "Order")


def _question_response() -> str:
    return json.dumps(
        {
            "anchor": {
                "kind": "diff-row",
                "artifact_key": "domain",
                "row_type": "entities",
                "row_id": "entity-order",
            },
            "question": "Should the customer-facing name use this exact spelling?",
        }
    )


def _sealed_replacement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    monkeypatch.setattr(
        roadmap_version_promotion, "check_complete_roadmap_gates", _green_gates
    )
    initial_result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _delta_response()),
    )
    assert initial_result.candidate is not None
    initial = initial_result.candidate
    question_result = roadmap_candidate_review.generate_candidate_question(
        _SLUG,
        initial.version_id,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _question_response()),
    )
    assert question_result.question_inventory is not None
    replacement_result = roadmap_candidate_review.answer_candidate_question(
        _SLUG,
        question_result.question_inventory.question.question_id,
        "Use the conventional spelling.",
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _delta_response()),
    )
    assert replacement_result.replacement is not None
    assert replacement_result.seal is not None
    return root, initial, replacement_result.replacement, replacement_result.seal


def _sealed_review_required_replacement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    monkeypatch.setattr(
        roadmap_version_promotion, "check_complete_roadmap_gates", _green_gates
    )
    initial_result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _review_required_delta_response()),
    )
    assert initial_result.candidate is not None
    initial = initial_result.candidate
    question_result = roadmap_candidate_review.generate_candidate_question(
        _SLUG,
        initial.version_id,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _question_response()),
    )
    assert question_result.question_inventory is not None
    replacement_result = roadmap_candidate_review.answer_candidate_question(
        _SLUG,
        question_result.question_inventory.question.question_id,
        "Restore the relation.",
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _eliminated_review_requirement_delta_response()),
    )
    assert replacement_result.replacement is not None
    assert replacement_result.seal is not None
    return root, initial, replacement_result.replacement, replacement_result.seal


def _promote(tmp_path: Path, seal_id: str):
    with roadmap_writer_guard(tmp_path / "plans", _SLUG) as token:
        return roadmap_version_promotion.promote_review_seal(
            plans_dir=tmp_path / "plans",
            slug=_SLUG,
            seal_id=seal_id,
            writer_token=token,
        )


def test_promotion_replaces_only_the_accepted_head_selector_for_the_exact_sealed_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _initial, replacement, seal = _sealed_replacement(tmp_path, monkeypatch)

    promoted = _promote(tmp_path, seal.seal_id)
    accepted = load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG)

    assert promoted.version_id == replacement.version_id
    assert accepted is not None
    assert accepted.record.version_id == replacement.version_id
    assert accepted.record.predecessor_version_id == root.record.version_id


def test_review_required_contained_replacement_promotes_only_after_its_exact_seal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _initial, replacement, seal = _sealed_review_required_replacement(tmp_path, monkeypatch)

    promoted = _promote(tmp_path, seal.seal_id)
    accepted = load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG)

    assert promoted.version_id == replacement.version_id
    assert accepted is not None
    assert accepted.record.version_id == replacement.version_id
    assert accepted.record.version_id != root.record.version_id


def test_promotion_refuses_uncontained_review_required_replacement_and_preserves_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, initial, replacement, seal = _sealed_review_required_replacement(tmp_path, monkeypatch)
    requirement = initial.evidence.review_requirement
    assert requirement is not None
    evidence = replacement.evidence.model_copy(
        update={
            "replacement_impact_atoms": requirement.impact_atoms,
            "replacement_impact_identity": roadmap_candidate.candidate_impact_identity(
                requirement.impact_atoms
            ),
        }
    )
    evidence_path = roadmap_candidate_review.replacement_evidence_path(
        tmp_path / "plans", _SLUG, replacement.version_id
    )
    evidence_path.write_bytes(roadmap_candidate_review.render_replacement_evidence(evidence))

    with pytest.raises(roadmap_version_promotion.RoadmapVersionPromotionError, match="impact"):
        _promote(tmp_path, seal.seal_id)

    accepted = load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG)
    assert accepted is not None
    assert accepted.record.version_id == root.record.version_id


def test_promotion_preserves_every_existing_stored_version_and_review_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _root_version, _initial, _replacement, seal = _sealed_replacement(tmp_path, monkeypatch)
    namespace = version_namespace_path(tmp_path / "plans", _SLUG)
    selector = accepted_head_path(tmp_path / "plans", _SLUG)
    before = {
        path.relative_to(namespace): path.read_bytes()
        for path in namespace.rglob("*")
        if path.is_file() and path != selector
    }

    _promote(tmp_path, seal.seal_id)

    after = {
        path.relative_to(namespace): path.read_bytes()
        for path in namespace.rglob("*")
        if path.is_file() and path != selector
    }
    assert after == before


@pytest.mark.parametrize(
    "record_name",
    (
        "admission",
        "question",
        "answer",
        "binding",
        "initial-evidence",
        "replacement-evidence",
    ),
)
def test_promotion_requires_one_complete_exact_review_seal_lineage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, record_name: str
) -> None:
    root, initial, replacement, seal = _sealed_replacement(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    paths = {
        "admission": roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG),
        "question": roadmap_candidate_review.question_inventory_path(
            plans_dir, _SLUG, initial.version_id
        ),
        "answer": roadmap_candidate_review.reviewer_answer_path(plans_dir, _SLUG, initial.version_id),
        "binding": roadmap_candidate_review.replacement_binding_path(
            plans_dir, _SLUG, initial.version_id
        ),
        "initial-evidence": roadmap_candidate_run.candidate_evidence_path(
            plans_dir, _SLUG, initial.version_id
        ),
        "replacement-evidence": roadmap_candidate_review.replacement_evidence_path(
            plans_dir, _SLUG, replacement.version_id
        ),
    }
    paths[record_name].write_bytes(b"not immutable review evidence")

    with pytest.raises(roadmap_version_promotion.RoadmapVersionPromotionError):
        _promote(tmp_path, seal.seal_id)

    accepted = load_accepted_version(plans_dir=plans_dir, slug=_SLUG)
    assert accepted is not None
    assert accepted.record.version_id == root.record.version_id


def test_promotion_refuses_a_candidate_version_other_than_the_one_bound_by_the_review_seal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _initial, replacement, seal = _sealed_replacement(tmp_path, monkeypatch)
    original_loader = roadmap_version_promotion.roadmap_candidate_review.load_stored_candidate_review_replacement
    substituted_record = replacement.record.model_copy(update={"version_id": "0" * 64})
    substituted = roadmap_candidate_review.StoredCandidateReviewReplacement(
        record=substituted_record,
        content=replacement.content,
        evidence=replacement.evidence,
    )

    def substitute_candidate(**_kwargs):
        return substituted

    monkeypatch.setattr(
        roadmap_version_promotion.roadmap_candidate_review,
        "load_stored_candidate_review_replacement",
        substitute_candidate,
    )
    with pytest.raises(roadmap_version_promotion.RoadmapVersionPromotionError):
        _promote(tmp_path, seal.seal_id)
    monkeypatch.setattr(
        roadmap_version_promotion.roadmap_candidate_review,
        "load_stored_candidate_review_replacement",
        original_loader,
    )

    accepted = load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG)
    assert accepted is not None
    assert accepted.record.version_id == root.record.version_id


def test_promotion_rechecks_complete_stored_candidate_bytes_raw_brief_and_gates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _initial, replacement, seal = _sealed_replacement(tmp_path, monkeypatch)
    brief_path = stored_brief_path(tmp_path / "plans", _SLUG, replacement.version_id)
    original_brief = brief_path.read_bytes()
    brief_path.write_bytes(b"changed recorded brief")

    with pytest.raises(roadmap_version_promotion.RoadmapVersionPromotionError):
        _promote(tmp_path, seal.seal_id)

    brief_path.write_bytes(original_brief)
    artifact_path = stored_artifact_path(
        tmp_path / "plans", _SLUG, replacement.version_id, "domain"
    )
    original_bytes = artifact_path.read_bytes()
    artifact_path.write_bytes(b"malformed candidate artifact")

    with pytest.raises(roadmap_version_promotion.RoadmapVersionPromotionError):
        _promote(tmp_path, seal.seal_id)

    artifact_path.write_bytes(original_bytes)

    def gate_failure(_evidence, *, stages):
        return (
            RoadmapGateOutcome(
                stages[0],
                (Violation("test-gate-failure", "01-domain.md", None, "gate failed"),),
            ),
            *(RoadmapGateOutcome(stage, ()) for stage in stages[1:]),
        )

    monkeypatch.setattr(roadmap_version_promotion, "check_complete_roadmap_gates", gate_failure)
    with pytest.raises(roadmap_version_promotion.RoadmapVersionPromotionError):
        _promote(tmp_path, seal.seal_id)

    accepted = load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG)
    assert accepted is not None
    assert accepted.record.version_id == root.record.version_id


def test_promotion_uses_one_complete_stage_ordered_gate_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _root_version, _initial, replacement, seal = _sealed_replacement(tmp_path, monkeypatch)
    observed: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
    original_gates = roadmap_version_promotion.check_complete_roadmap_gates

    def observe_gates(evidence, *, stages):
        observed.append((evidence.artifact_keys, evidence.artifact_texts))
        return original_gates(evidence, stages=stages)

    monkeypatch.setattr(roadmap_version_promotion, "check_complete_roadmap_gates", observe_gates)
    _promote(tmp_path, seal.seal_id)

    assert observed == [
        (
            tuple(stage.artifact_key for stage in STAGES),
            tuple(data.decode("utf-8") for data in replacement.content.artifact_bytes),
        )
    ]


def test_promotion_requires_the_current_head_to_match_the_sealed_candidate_predecessor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, initial, _replacement, seal = _sealed_replacement(tmp_path, monkeypatch)
    selector = accepted_head_path(tmp_path / "plans", _SLUG)
    selector.write_bytes(
        render_accepted_head(
            AcceptedRoadmapHead(
                schema_version=ROADMAP_VERSION_SCHEMA_VERSION,
                roadmap_slug=_SLUG,
                version_id=initial.version_id,
            )
        )
    )

    with pytest.raises(roadmap_version_promotion.StaleRoadmapVersionPromotionError):
        _promote(tmp_path, seal.seal_id)

    accepted = load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG)
    assert accepted is not None
    assert accepted.record.version_id == initial.version_id
    assert accepted.record.version_id != root.record.version_id


def test_promotion_rechecks_head_predecessor_inside_the_journal_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _root_version, initial, _replacement, seal = _sealed_replacement(tmp_path, monkeypatch)
    original_publish = roadmap_version_promotion.publish_roadmap_generation
    selector = accepted_head_path(tmp_path / "plans", _SLUG)
    journal = pending_generation_path(selector.parent.parent)

    def change_head_before_replace(generation, **kwargs):
        recheck = kwargs.pop("before_replace")

        def final_recheck() -> None:
            selector.write_bytes(
                render_accepted_head(
                    AcceptedRoadmapHead(
                        schema_version=ROADMAP_VERSION_SCHEMA_VERSION,
                        roadmap_slug=_SLUG,
                        version_id=initial.version_id,
                    )
                )
            )
            recheck()

        return original_publish(generation, before_replace=final_recheck, **kwargs)

    monkeypatch.setattr(
        roadmap_version_promotion, "publish_roadmap_generation", change_head_before_replace
    )
    with pytest.raises(roadmap_version_promotion.StaleRoadmapVersionPromotionError):
        _promote(tmp_path, seal.seal_id)

    assert selector.read_bytes() == render_accepted_head(
        AcceptedRoadmapHead(
            schema_version=ROADMAP_VERSION_SCHEMA_VERSION,
            roadmap_slug=_SLUG,
            version_id=initial.version_id,
        )
    )
    assert not journal.exists()


def test_promotion_requires_an_active_matching_writer_token_and_writes_only_the_selector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _root_version, _initial, _replacement, seal = _sealed_replacement(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    selector = accepted_head_path(plans_dir, _SLUG)
    before = selector.read_bytes()
    with pytest.raises(RoadmapWriterGuardError):
        roadmap_version_promotion.promote_review_seal(
            plans_dir=plans_dir,
            slug=_SLUG,
            seal_id=seal.seal_id,
            writer_token=None,  # type: ignore[arg-type]
        )
    with roadmap_writer_guard(plans_dir, _SLUG) as inactive:
        pass
    with pytest.raises(RoadmapWriterGuardError):
        roadmap_version_promotion.promote_review_seal(
            plans_dir=plans_dir,
            slug=_SLUG,
            seal_id=seal.seal_id,
            writer_token=inactive,
        )
    with roadmap_writer_guard(plans_dir, "other") as foreign:
        with pytest.raises(RoadmapWriterGuardError):
            roadmap_version_promotion.promote_review_seal(
                plans_dir=plans_dir,
                slug=_SLUG,
                seal_id=seal.seal_id,
                writer_token=foreign,
            )
    assert selector.read_bytes() == before

    published: list[object] = []
    original_publish = roadmap_version_promotion.publish_roadmap_generation

    def capture_generation(generation, **kwargs):
        published.append(generation)
        return original_publish(generation, **kwargs)

    monkeypatch.setattr(roadmap_version_promotion, "publish_roadmap_generation", capture_generation)
    _promote(tmp_path, seal.seal_id)

    assert len(published) == 1
    assert published[0].members == (
        published[0].members[0],
    )
    assert published[0].members[0].relative_path == ".roadmap-versions/accepted-head.json"


def test_promotion_has_no_model_or_candidate_regeneration_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _root_version, _initial, _replacement, seal = _sealed_replacement(tmp_path, monkeypatch)

    monkeypatch.setattr(
        roadmap_candidate,
        "materialize_candidate",
        lambda *_args, **_kwargs: pytest.fail("promotion must not materialize a candidate"),
    )
    monkeypatch.setattr(
        roadmap_candidate_review,
        "_invoke_replacement",
        lambda *_args, **_kwargs: pytest.fail("promotion must not invoke a model"),
    )
    _promote(tmp_path, seal.seal_id)


def test_promoted_head_keeps_the_fixed_roadmap_admission_terminal_without_an_extra_member(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _root_version, initial, _replacement, seal = _sealed_replacement(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    admission_path = roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG)
    initial_evidence_path = roadmap_candidate_run.candidate_evidence_path(
        plans_dir, _SLUG, initial.version_id
    )
    admission_before = admission_path.read_bytes()
    initial_evidence_before = initial_evidence_path.read_bytes()

    _promote(tmp_path, seal.seal_id)

    assert admission_path.read_bytes() == admission_before
    assert initial_evidence_path.read_bytes() == initial_evidence_before


def test_promotion_does_not_read_or_rewrite_the_live_feedback_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep later mutable ledger bytes outside sealed promotion authority."""
    _root_version, _initial, _replacement, seal = _sealed_replacement(tmp_path, monkeypatch)
    ledger_path = roadmap_feedback_ledger_path(tmp_path / "plans", _SLUG)
    ledger_path.write_bytes(b"later reviewer edit")

    _promote(tmp_path, seal.seal_id)

    assert ledger_path.read_bytes() == b"later reviewer edit"


# --------------------------------------------------------------------------
# Ledger-batch replacement promotion
# --------------------------------------------------------------------------


def _sealed_batch_replacement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A real ledger-batch candidate, reviewed, replaced and sealed (the pointer names the replacement)."""
    monkeypatch.setattr(roadmap_version_promotion, "check_complete_roadmap_gates", _green_gates)
    root, initial, inventory = _batch_review(tmp_path, monkeypatch)
    stored = _request_batch_replacement(tmp_path, inventory)
    assert stored.replacement is not None, stored.detail
    sealed = roadmap_candidate_review.seal_review(
        _SLUG, stored.replacement.version_id, plans_dir=tmp_path / "plans"
    )
    assert sealed.seal is not None, sealed.detail
    return root, initial, stored.replacement, sealed.seal


def _direct_structural_approval(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Create and directly approve one active structural batch candidate."""
    monkeypatch.setattr(roadmap_version_promotion, "check_complete_roadmap_gates", _green_gates)
    root, _resolved = _seed_batch_ledger(tmp_path, monkeypatch)
    delta = {
        "operations": [{
            "op": "replace-row", "feedback_id": "batch-one", "artifact_key": "domain",
            "row_type": "entities", "row_id": "entity-order",
            "row": {"id": "entity-order", "name": "Order", "fields": [{
                "name": "buyer", "type": "reference", "entity_id": "entity-customer",
            }]},
        }],
        "responses": [{"item_id": "batch-one", "response": "Use buyer."}],
        "derived_feedback": [],
    }
    proposed = _run_batch(tmp_path, delta)
    assert proposed.candidate is not None, proposed.detail
    approved = _approve_structural_candidate(tmp_path / "plans", proposed.candidate)
    assert approved.seal is not None, approved.detail
    return root, proposed.candidate, approved.seal


_OWN_STRUCTURAL_TOP = "own-structural-top"
_PRESENTATION_ONLY_TOP_OVER_STRUCTURAL_HOP = "presentation-only-top-over-structural-hop"
_STACK_SHAPES = (_OWN_STRUCTURAL_TOP, _PRESENTATION_ONLY_TOP_OVER_STRUCTURAL_HOP)

# A replacement over a stack's top must classify presentation-only, or the answered route refuses it first.
_PRESENTATION_ONLY_ANSWER_DELTA = {
    "operations": [],
    "responses": [],
    "derived_feedback": [{"context_id": "derived-answered", "content": "Confirmed."}],
}


def _structural_stack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Root -> C1 (structural) -> C2 (presentation-only, the active tip), through the batch runner."""
    monkeypatch.setattr(roadmap_version_promotion, "check_complete_roadmap_gates", _green_gates)
    root, (structural, top) = _store_stack(
        tmp_path, monkeypatch, ("structural", "presentation-only")
    )
    # A helper that built the wrong stack would let every case built on it pass without testing anything.
    assert top.evidence.operation_classification is _PRESENTATION_ONLY
    assert roadmap_candidate_run.candidate_stack_route(
        plans_dir=tmp_path / "plans", slug=_SLUG,
        tip_version_id=top.version_id, root_version_id=root.record.version_id,
    ).is_structural
    return root, structural, top


def _stacked_structural_approval(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Approve the presentation-only top of a stack whose lower hop is structural."""
    root, structural, top = _structural_stack(tmp_path, monkeypatch)
    approved = _approve_structural_candidate(tmp_path / "plans", top)
    assert approved.seal is not None, approved.detail
    return root, structural, top, approved.seal


def _structural_approval_over(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shape: str):
    """(root, promoted candidate, seal) for each shape a structural change reaches the head through."""
    if shape == _OWN_STRUCTURAL_TOP:
        return _direct_structural_approval(tmp_path, monkeypatch)
    assert shape == _PRESENTATION_ONLY_TOP_OVER_STRUCTURAL_HOP
    root, _structural, top, seal = _stacked_structural_approval(tmp_path, monkeypatch)
    return root, top, seal


def _receipt_anchored_question(top) -> str:
    """A question anchored on the first row the tip's receipt names (a stack tip may name no reviewer item)."""
    receipt = top.evidence.batch_receipt
    kind, anchored = (
        ("inventory", receipt.inventory[0]) if receipt.inventory
        else ("full-member", receipt.full_members[0].identity)
    )
    return json.dumps({
        "anchor": {
            "kind": kind, "artifact_key": anchored.artifact_key,
            "row_type": anchored.row_type, "row_id": anchored.row_id,
        },
        "question": "Should the customer-facing name use this exact spelling?",
    })


def _answer_over_the_active_tip(tmp_path: Path, tip, *, question: str, replacement: str):
    """Ask, answer and seal the answered route over `tip`; the caller decides which guards are live."""
    plans_dir = tmp_path / "plans"
    asked = roadmap_candidate_review.generate_candidate_question(
        _SLUG, tip.version_id, repo_root=tmp_path, plans_dir=plans_dir,
        invoker=lambda _prompt: (0, question),
    )
    assert asked.question_inventory is not None, asked.detail
    answered = roadmap_candidate_review.answer_candidate_question(
        _SLUG, asked.question_inventory.question.question_id, _BATCH_ANSWER,
        repo_root=tmp_path, plans_dir=plans_dir, invoker=lambda _prompt: (0, replacement),
    )
    assert answered.seal is not None, answered.detail
    return answered


def _capture_promotion_generation(monkeypatch: pytest.MonkeyPatch) -> list[PendingGeneration]:
    """Record every generation the promotion writer publishes, still publishing it."""
    captured: list[PendingGeneration] = []
    real_publish = roadmap_version_promotion.publish_roadmap_generation

    def spy(generation, **kwargs):
        captured.append(generation)
        return real_publish(generation, **kwargs)

    monkeypatch.setattr(roadmap_version_promotion, "publish_roadmap_generation", spy)
    return captured


def _recover_journal(plans_dir: Path, generation: PendingGeneration) -> Path:
    """Put `generation` back as a pending journal, run recovery, and return the journal path."""
    journal = pending_generation_path(version_namespace_path(plans_dir, _SLUG).parent)
    journal.write_bytes(render_pending_generation(generation))
    with roadmap_writer_guard(plans_dir, _SLUG) as token:
        recover_roadmap_publication(plans_dir=plans_dir, slug=_SLUG, writer_token=token)
    return journal


@pytest.mark.parametrize("shape", _STACK_SHAPES)
def test_answered_seal_cannot_promote_a_structural_initial_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shape: str
) -> None:
    """A structural change in the reviewed candidate's stack, its own hop or a lower one, needs a
    structural decision: the answered seal is refused whichever hop carries it."""
    monkeypatch.setattr(roadmap_version_promotion, "check_complete_roadmap_gates", _green_gates)
    if shape == _OWN_STRUCTURAL_TOP:
        _seed_batch_ledger(tmp_path, monkeypatch)
        proposed = _run_batch(tmp_path, _structural_batch_delta())
        assert proposed.candidate is not None
        reviewed, question, replacement = proposed.candidate, _batch_question_response(), _batch_replacement_response()
    else:
        _root, _structural, reviewed = _structural_stack(tmp_path, monkeypatch)
        question, replacement = _receipt_anchored_question(reviewed), json.dumps(_PRESENTATION_ONLY_ANSWER_DELTA)
    plans_dir = tmp_path / "plans"
    # Simulate a seal issued before the answered route gained its entry guard.
    with monkeypatch.context() as old_route:
        old_route.setattr(
            roadmap_candidate_review, "_require_answered_review_route", lambda _candidate, **_keywords: None
        )
        answered = _answer_over_the_active_tip(tmp_path, reviewed, question=question, replacement=replacement)
    before = _tree(plans_dir)
    with pytest.raises(roadmap_version_promotion.RoadmapVersionPromotionError, match="--decide-candidate"):
        _promote(tmp_path, answered.seal.seal_id)
    assert _tree(plans_dir) == before


def test_seal_requirement_holds_at_the_boundary_when_the_review_guards_are_bypassed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The boundary asks the promoted candidate's own stack, independently of the loader guards: with
    both review-side guards stubbed out for the whole flow, an answered seal over a stack that carries a
    lower structural hop is still refused, and promotion writes nothing."""
    _root, _structural, top = _structural_stack(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    monkeypatch.setattr(
        roadmap_candidate_review, "_require_answered_review_route", lambda _candidate, **_keywords: None
    )
    monkeypatch.setattr(
        roadmap_candidate_review, "_require_structural_candidate", lambda _candidate, **_keywords: None
    )
    answered = _answer_over_the_active_tip(
        tmp_path, top, question=_receipt_anchored_question(top),
        replacement=json.dumps(_PRESENTATION_ONLY_ANSWER_DELTA),
    )
    assert answered.seal.decision != "structural-approval"
    before = _tree(plans_dir)

    with pytest.raises(roadmap_version_promotion.RoadmapVersionPromotionError, match="--decide-candidate"):
        _promote(tmp_path, answered.seal.seal_id)

    assert _tree(plans_dir) == before


@pytest.mark.parametrize("guards", ("review-guards-live", "review-guards-bypassed"))
def test_promotion_refuses_an_underivable_stack_as_a_promotion_error_with_no_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, guards: str
) -> None:
    """An underivable stack is a refusal, never "not structural" and never a raw candidate error. The
    forged lower hop leaves the approved top loading cleanly, so only the stack derivation refuses; the
    bypassed variant pins that the boundary's own derivation runs inside the promotion error mapping."""
    _root, structural, _top, seal = _stacked_structural_approval(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    _edit_stored_evidence(
        tmp_path, structural, lambda data: data.update(operation_classification="presentation-only")
    )
    before = _tree(plans_dir)

    with monkeypatch.context() as patched:
        if guards == "review-guards-bypassed":
            patched.setattr(
                roadmap_candidate_review, "_require_structural_candidate", lambda _candidate, **_keywords: None
            )
            patched.setattr(
                roadmap_candidate_review, "_require_answered_review_route", lambda _candidate, **_keywords: None
            )
        with pytest.raises(
            roadmap_version_promotion.RoadmapVersionPromotionError,
            match="route does not match its stored operations",
        ):
            _promote(tmp_path, seal.seal_id)

    assert _tree(plans_dir) == before


def test_route_less_batch_candidate_keeps_the_answered_route_through_promotion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guards key on a stored STRUCTURAL route, never on absence: batch evidence written before the
    route existed is not structural-eligible, but it keeps its reviewed nonstructural path from
    question through promotion. This reaches both the entry guards and the promotion guard."""
    monkeypatch.setattr(roadmap_version_promotion, "check_complete_roadmap_gates", _green_gates)
    root, _resolved = _seed_batch_ledger(tmp_path, monkeypatch)
    proposed = _run_batch(tmp_path, _FIRST_BATCH_DELTA)
    assert proposed.candidate is not None
    plans_dir = tmp_path / "plans"
    roadmap_candidate_run.candidate_evidence_path(
        plans_dir, _SLUG, proposed.candidate.version_id
    ).write_bytes(
        roadmap_candidate_run.render_candidate_evidence(
            proposed.candidate.evidence.model_copy(
                update={"normalized_operations": None, "operation_classification": None}
            )
        )
    )
    asked = roadmap_candidate_review.generate_candidate_question(
        _SLUG, proposed.candidate.version_id, repo_root=tmp_path, plans_dir=plans_dir,
        invoker=lambda _prompt: (0, _batch_question_response()),
    )
    assert asked.question_inventory is not None, asked.detail
    answered = roadmap_candidate_review.answer_candidate_question(
        _SLUG, asked.question_inventory.question.question_id, _BATCH_ANSWER,
        repo_root=tmp_path, plans_dir=plans_dir,
        invoker=lambda _prompt: (0, _batch_replacement_response()),
    )
    assert answered.seal is not None, answered.detail
    assert answered.seal.decision != "structural-approval"

    promoted = _promote(tmp_path, answered.seal.seal_id)

    accepted = load_accepted_version(plans_dir=plans_dir, slug=_SLUG)
    assert accepted is not None
    assert accepted.record.version_id == promoted.version_id
    assert accepted.record.predecessor_version_id == root.record.version_id


def _sealed_two_hop_replacement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Root -> C1 (changes the entity) -> C2 (source C1) -> R2 (predecessor C1), sealed."""
    monkeypatch.setattr(roadmap_version_promotion, "check_complete_roadmap_gates", _green_gates)
    plans_dir = tmp_path / "plans"
    root, _resolved = _seed_batch_ledger(tmp_path, monkeypatch)
    first = _run_batch(tmp_path, json.loads(_batch_replacement_response()))
    assert first.candidate is not None, first.detail
    second = _run_batch(tmp_path, _SECOND_BATCH_DELTA)
    assert second.candidate is not None, second.detail
    asked = roadmap_candidate_review.generate_candidate_question(
        _SLUG,
        second.candidate.version_id,
        repo_root=tmp_path,
        plans_dir=plans_dir,
        invoker=lambda _prompt: (
            0,
            json.dumps(
                {
                    "anchor": {
                        "kind": "derived-context",
                        "artifact_key": "derived-context",
                        "row_type": "row",
                        "row_id": "derived-replacement",
                    },
                    "question": "Is the settled spelling still right?",
                }
            ),
        ),
    )
    assert asked.question_inventory is not None, asked.detail
    question_id = asked.question_inventory.question.question_id
    recorded = roadmap_candidate_review.record_reviewer_answer(
        _SLUG, question_id, "Yes, keep it.", plans_dir=plans_dir
    )
    assert recorded.answer is not None, recorded.detail
    stored = roadmap_candidate_review.request_replacement(
        _SLUG,
        question_id,
        "Yes, keep it.",
        repo_root=tmp_path,
        plans_dir=plans_dir,
        invoker=lambda _prompt: (
            0,
            json.dumps(
                {
                    "operations": [],
                    "responses": [],
                    "derived_feedback": [{"context_id": "derived-hop", "content": "Confirmed."}],
                }
            ),
        ),
    )
    assert stored.replacement is not None, stored.detail
    sealed = roadmap_candidate_review.seal_review(
        _SLUG, stored.replacement.version_id, plans_dir=plans_dir
    )
    assert sealed.seal is not None, sealed.detail
    return root, first.candidate, second.candidate, stored.replacement, sealed.seal


# INDEX.md is a derived human aid rewritten by every committing command; these
# snapshots compare version-store state, not that file (covered in its own tests).
_INDEX_NAME = "INDEX.md"


def _tree(directory: Path) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file() and path.name != _INDEX_NAME
    }


def _forge_seal(tmp_path: Path, seal, **changes):
    """Write a well-formed seal (its id recomputed) whose named fields differ from the real one."""
    values = {**seal.model_dump(), **changes, "seal_id": "0" * 64}
    draft = roadmap_candidate_review.CandidateReviewSeal.model_construct(**values)
    values["seal_id"] = roadmap_candidate_review._identity(
        roadmap_candidate_review._seal_preimage(draft)
    )
    forged = roadmap_candidate_review.CandidateReviewSeal(**values)
    path = roadmap_candidate_review.review_seal_path(tmp_path / "plans", _SLUG, forged.seal_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(roadmap_candidate_review.render_review_seal(forged))
    return forged


def _tamper_replacement_evidence(tmp_path: Path, replacement, mutate) -> None:
    path = roadmap_candidate_review.replacement_evidence_path(
        tmp_path / "plans", _SLUG, replacement.version_id
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutate(payload)
    path.write_bytes(roadmap_candidate_review._canonical_json_bytes(payload))


def test_promotion_promotes_a_sealed_batch_replacement_and_moves_only_the_selector_and_the_pointer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Promotion consumes the active replacement; no stored version, record or ledger byte moves."""
    root, _initial, replacement, seal = _sealed_batch_replacement(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    roadmap_root = version_namespace_path(plans_dir, _SLUG).parent
    before = _tree(roadmap_root)

    promoted = _promote(tmp_path, seal.seal_id)

    accepted = load_accepted_version(plans_dir=plans_dir, slug=_SLUG)
    assert promoted.version_id == replacement.version_id
    assert accepted is not None and accepted.record.version_id == replacement.version_id
    released = roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug=_SLUG)
    assert released is not None
    assert released.root_version_id == root.record.version_id
    assert (released.active_candidate_version_id, released.candidate_version_id) == (None, None)
    after = _tree(roadmap_root)
    changed = {name for name in before.keys() | after.keys() if before.get(name) != after.get(name)}
    assert changed == {
        accepted_head_path(plans_dir, _SLUG).relative_to(roadmap_root).as_posix(),
        roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG).relative_to(roadmap_root).as_posix(),
    }
    assert not (version_namespace_path(plans_dir, _SLUG) / "candidate-terminal-resolutions").exists()


def test_promotion_publishes_the_selector_and_the_pointer_release_in_one_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Release the root's active slot with the selector, not as terminal history."""
    _root, _initial, _replacement, seal = _sealed_batch_replacement(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    captured = []
    real_publish = roadmap_version_promotion.publish_roadmap_generation

    def spy(generation, **kwargs):
        captured.append(generation)
        return real_publish(generation, **kwargs)

    monkeypatch.setattr(roadmap_version_promotion, "publish_roadmap_generation", spy)

    _promote(tmp_path, seal.seal_id)

    (generation,) = captured
    roadmap_root = version_namespace_path(plans_dir, _SLUG).parent
    assert generation.kind == "review-seal-promotion"
    assert {member.relative_path for member in generation.members} == {
        accepted_head_path(plans_dir, _SLUG).relative_to(roadmap_root).as_posix(),
        roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG).relative_to(roadmap_root).as_posix(),
    }


@pytest.mark.parametrize("shape", _STACK_SHAPES)
def test_promotion_promotes_the_directly_approved_initial_structural_candidate_with_seed_invalidation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shape: str
) -> None:
    """Direct approval promotes its displayed bytes and invalidates tracked seeds atomically, whether the
    structural change is the top's own or sits in a hop below a presentation-only top."""
    root, candidate, seal = _structural_approval_over(tmp_path, monkeypatch, shape)
    plans_dir = tmp_path / "plans"
    roadmap_root = version_namespace_path(plans_dir, _SLUG).parent
    draft = roadmap_root / "plan-seed-drafts" / "plan-order.md"
    draft.parent.mkdir(parents=True)
    draft.write_bytes(b"draft bytes\n")
    state_file = seed_state_path(roadmap_root)
    write_seed_state(
        state_file,
        {"version": 1, "seeds": {"plan-order": {
            "draft_seed_path": "plan-seed-drafts/plan-order.md",
            "status": "current",
            "digest": "a" * 64,
            "published": False,
        }}},
    )
    captured = []
    real_publish = roadmap_version_promotion.publish_roadmap_generation

    def spy(generation, **kwargs):
        captured.append(generation)
        return real_publish(generation, **kwargs)

    monkeypatch.setattr(roadmap_version_promotion, "publish_roadmap_generation", spy)
    promoted = _promote(tmp_path, seal.seal_id)

    assert promoted.version_id == candidate.version_id
    assert load_accepted_version(plans_dir=plans_dir, slug=_SLUG).record.version_id == candidate.version_id
    assert draft.read_bytes() == b"draft bytes\n"
    assert load_seed_state(state_file)["seeds"]["plan-order"]["status"] == "invalidated"
    (generation,) = captured
    assert {member.relative_path for member in generation.members} == {
        accepted_head_path(plans_dir, _SLUG).relative_to(roadmap_root).as_posix(),
        roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG).relative_to(roadmap_root).as_posix(),
        state_file.relative_to(roadmap_root).as_posix(),
    }
    assert not (version_namespace_path(plans_dir, _SLUG) / "candidate-terminal-resolutions").exists()
    assert root.record.version_id != promoted.version_id


@pytest.mark.parametrize("shape", _STACK_SHAPES)
def test_completed_direct_structural_promotion_recovery_requires_exact_three_members(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shape: str
) -> None:
    """Recovery drops only a completed selector, pointer-release, and seed generation. The seed member
    is demanded of a presentation-only top over a structural hop exactly as of an own-structural top."""
    _root, _candidate, seal = _structural_approval_over(tmp_path, monkeypatch, shape)
    plans_dir = tmp_path / "plans"
    captured: list[PendingGeneration] = []
    real_publish = roadmap_version_promotion.publish_roadmap_generation

    def spy(generation, **kwargs):
        captured.append(generation)
        return real_publish(generation, **kwargs)

    monkeypatch.setattr(roadmap_version_promotion, "publish_roadmap_generation", spy)
    _promote(tmp_path, seal.seal_id)
    (generation,) = captured
    assert len(generation.members) == 3
    journal = pending_generation_path(version_namespace_path(plans_dir, _SLUG).parent)
    journal.write_bytes(render_pending_generation(generation))
    with roadmap_writer_guard(plans_dir, _SLUG) as token:
        recover_roadmap_publication(plans_dir=plans_dir, slug=_SLUG, writer_token=token)
    assert not journal.exists()

    for members in (
        (generation.members[0], generation.members[2]),
        (generation.members[0], generation.members[2], generation.members[1]),
        (generation.members[0], generation.members[1]),
    ):
        incomplete = PendingGeneration(kind=generation.kind, members=members)
        journal.write_bytes(render_pending_generation(incomplete))
        with roadmap_writer_guard(plans_dir, _SLUG) as token:
            with pytest.raises(RoadmapPublicationRecoveryError):
                recover_roadmap_publication(plans_dir=plans_dir, slug=_SLUG, writer_token=token)
        assert journal.exists()
        journal.unlink()


def test_promotion_refuses_a_changed_structural_approval_before_replacing_any_member(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An approval that changes in the journal window cannot publish a partial generation."""
    root, _candidate, seal = _direct_structural_approval(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    selector = accepted_head_path(plans_dir, _SLUG)
    admission_path = roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG)
    seal_path = roadmap_candidate_review.review_seal_path(plans_dir, _SLUG, seal.seal_id)
    journal = pending_generation_path(version_namespace_path(plans_dir, _SLUG).parent)
    before_selector = selector.read_bytes()
    before_admission = admission_path.read_bytes()
    real_publish = roadmap_version_promotion.publish_roadmap_generation

    def change_approval_before_replace(generation, **kwargs):
        recheck = kwargs.pop("before_replace")

        def final_recheck() -> None:
            seal_path.write_bytes(b"changed approval")
            recheck()

        return real_publish(generation, before_replace=final_recheck, **kwargs)

    monkeypatch.setattr(
        roadmap_version_promotion, "publish_roadmap_generation", change_approval_before_replace
    )
    with pytest.raises(
        roadmap_version_promotion.StaleRoadmapVersionPromotionError,
        match="review seal changed",
    ):
        _promote(tmp_path, seal.seal_id)

    assert selector.read_bytes() == before_selector
    assert admission_path.read_bytes() == before_admission
    assert load_accepted_version(plans_dir=plans_dir, slug=_SLUG).record.version_id == root.record.version_id
    assert not journal.exists()


def test_promotion_ignores_a_later_reviewer_edit_to_the_live_ledger_of_a_batch_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _root, _initial, replacement, seal = _sealed_batch_replacement(tmp_path, monkeypatch)
    ledger_path = roadmap_feedback_ledger_path(tmp_path / "plans", _SLUG)
    ledger_path.write_bytes(b"later reviewer edit")

    promoted = _promote(tmp_path, seal.seal_id)

    assert promoted.version_id == replacement.version_id
    assert ledger_path.read_bytes() == b"later reviewer edit"


def test_promotion_diffs_a_multi_hop_replacement_against_its_source_not_the_accepted_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R2's predecessor is the first candidate, two records above the root."""
    root, first, _second, replacement, seal = _sealed_two_hop_replacement(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    assert replacement.record.predecessor_version_id == first.version_id
    assert first.record.predecessor_version_id == root.record.version_id
    assert replacement.content.artifact_bytes != root.content.artifact_bytes

    promoted = _promote(tmp_path, seal.seal_id)

    assert promoted.version_id == replacement.version_id
    accepted = load_accepted_version(plans_dir=plans_dir, slug=_SLUG)
    assert accepted is not None and accepted.record.version_id == replacement.version_id


def test_promotion_refuses_a_sealed_replacement_that_a_later_batch_has_superseded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _initial, replacement, seal = _sealed_batch_replacement(tmp_path, monkeypatch)
    later = _run_batch(tmp_path, _SECOND_BATCH_DELTA)
    assert later.candidate is not None, later.detail

    with pytest.raises(
        roadmap_version_promotion.RoadmapVersionPromotionError, match="active replacement candidate"
    ):
        _promote(tmp_path, seal.seal_id)

    accepted = load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG)
    assert accepted is not None and accepted.record.version_id == root.record.version_id
    assert replacement.version_id != later.candidate.version_id


def _rewrite_supersession(
    successor: str | None = None, root: str | None = None, superseded: str | None = None
):
    def rewrite(path: Path) -> None:
        record = json.loads(path.read_text(encoding="utf-8"))
        if successor is not None:
            record["successor_candidate_version_id"] = successor
        if root is not None:
            record["root_version_id"] = root
        if superseded is not None:
            record["superseded_candidate_version_id"] = superseded
        path.write_bytes(roadmap_candidate_run._canonical_json_bytes(record))

    return rewrite


@pytest.mark.parametrize(
    ("mutate", "message"),
    (
        (lambda path: path.unlink(), "candidate supersession is unreadable"),
        (_rewrite_supersession(successor="9" * 64), "not the recorded successor"),
        (_rewrite_supersession(root="8" * 64), "not the recorded successor"),
        (
            _rewrite_supersession(superseded="7" * 64),
            "does not match its requested identity",
        ),
    ),
    ids=("record-missing", "names-another-successor", "names-another-root", "filed-under-another-candidate"),
)
def test_promotion_requires_the_supersession_record_of_the_reviewed_candidate_to_name_the_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutate, message: str
) -> None:
    _root, initial, _replacement, seal = _sealed_batch_replacement(tmp_path, monkeypatch)
    mutate(roadmap_candidate_run.supersession_path(tmp_path / "plans", _SLUG, initial.version_id))

    with pytest.raises(roadmap_version_promotion.RoadmapVersionPromotionError, match=message):
        _promote(tmp_path, seal.seal_id)


@pytest.mark.parametrize(
    "field", ("root_version_id", "source_version_id", "batch_receipt_identity")
)
def test_promotion_refuses_a_seal_whose_batch_binding_disagrees_with_the_replacement_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    _root, _initial, _replacement, seal = _sealed_batch_replacement(tmp_path, monkeypatch)
    forged = _forge_seal(tmp_path, seal, **{field: "d" * 64})

    with pytest.raises(
        roadmap_version_promotion.RoadmapVersionPromotionError,
        match="does not bind the exact replacement candidate evidence",
    ):
        _promote(tmp_path, forged.seal_id)


def test_promotion_refuses_a_seal_without_a_batch_binding_over_a_ledger_batch_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Before the swap the reviewed candidate is still active; a selector-shaped seal cannot claim it."""
    monkeypatch.setattr(roadmap_version_promotion, "check_complete_roadmap_gates", _green_gates)
    _root, initial, inventory = _batch_review(tmp_path, monkeypatch)
    stored = _request_batch_replacement(tmp_path, inventory)
    assert stored.replacement is not None, stored.detail
    answer = roadmap_candidate_review.parse_reviewer_answer(
        roadmap_candidate_review.reviewer_answer_path(
            tmp_path / "plans", _SLUG, initial.version_id
        ).read_bytes()
    )
    real = roadmap_candidate_review._new_seal(
        initial=initial, inventory=inventory, answer=answer, replacement=stored.replacement
    )
    forged = _forge_seal(
        tmp_path, real, root_version_id=None, source_version_id=None, batch_receipt_identity=None
    )

    with pytest.raises(
        roadmap_version_promotion.RoadmapVersionPromotionError,
        match="disagree on ledger batch lineage",
    ):
        _promote(tmp_path, forged.seal_id)


@pytest.mark.parametrize(
    "mutate",
    (
        lambda payload: payload["response_patch"]["entries"][0].update({"response": "Tampered."}),
        lambda payload: payload["derived_feedback"][0].update({"content": "Tampered."}),
    ),
    ids=("response-text", "derived-context"),
)
def test_promotion_refuses_a_batch_replacement_whose_persisted_responses_no_longer_reproduce_its_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutate
) -> None:
    """The batch identity binds the response patch and derived set, so editing either is caught."""
    root, _initial, replacement, seal = _sealed_batch_replacement(tmp_path, monkeypatch)
    _tamper_replacement_evidence(tmp_path, replacement, mutate)

    with pytest.raises(
        roadmap_version_promotion.RoadmapVersionPromotionError,
        match="content identity or predecessor diff is not reproducible",
    ):
        _promote(tmp_path, seal.seal_id)

    accepted = load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG)
    assert accepted is not None and accepted.record.version_id == root.record.version_id


def test_promotion_of_a_batch_replacement_requires_the_current_head_to_be_the_declared_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _root, initial, _replacement, seal = _sealed_batch_replacement(tmp_path, monkeypatch)
    accepted_head_path(tmp_path / "plans", _SLUG).write_bytes(
        render_accepted_head(
            AcceptedRoadmapHead(
                schema_version=ROADMAP_VERSION_SCHEMA_VERSION,
                roadmap_slug=_SLUG,
                version_id=initial.version_id,
            )
        )
    )

    with pytest.raises(roadmap_version_promotion.StaleRoadmapVersionPromotionError):
        _promote(tmp_path, seal.seal_id)


def test_promotion_of_a_batch_replacement_rechecks_the_active_pointer_inside_the_journal_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _initial, _replacement, seal = _sealed_batch_replacement(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    admission_path = roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG)
    released = roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug=_SLUG).model_copy(
        update={"candidate_version_id": None, "active_candidate_version_id": None}
    )
    real_publish = roadmap_version_promotion.publish_roadmap_generation

    def release_pointer_before_replace(generation, **kwargs):
        recheck = kwargs.pop("before_replace")

        def final_recheck() -> None:
            admission_path.write_bytes(roadmap_candidate_run.render_candidate_admission(released))
            recheck()

        return real_publish(generation, before_replace=final_recheck, **kwargs)

    monkeypatch.setattr(
        roadmap_version_promotion, "publish_roadmap_generation", release_pointer_before_replace
    )

    with pytest.raises(
        roadmap_version_promotion.StaleRoadmapVersionPromotionError,
        match="active candidate pointer changed",
    ):
        _promote(tmp_path, seal.seal_id)

    accepted = load_accepted_version(plans_dir=plans_dir, slug=_SLUG)
    assert accepted is not None and accepted.record.version_id == root.record.version_id


def test_a_ledger_batch_can_follow_a_promoted_selector_era_lineage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The unpromoted-lineage refusal ends with the promotion it waits for: once the head
    has moved past the selector-era admission's predecessor, a ledger batch stores."""
    _root, _initial, replacement, seal = _sealed_replacement(tmp_path, monkeypatch)
    _promote(tmp_path, seal.seal_id)
    _write_open_item_ledger(tmp_path)

    later = _run_batch(tmp_path, _FIRST_BATCH_DELTA)

    assert later.outcome == "stored", later.detail
    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=tmp_path / "plans", slug=_SLUG)
    assert admission is not None
    assert admission.root_version_id == replacement.version_id
    assert later.candidate is not None
    assert admission.active_candidate_version_id == later.candidate.version_id


def test_a_batch_candidate_can_be_created_for_the_promoted_root_immediately_after_promotion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Promotion frees the active slot for the new root, not only for the old one."""
    root, _initial, replacement, seal = _sealed_batch_replacement(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    _promote(tmp_path, seal.seal_id)

    later = _run_batch(tmp_path, _SECOND_BATCH_DELTA)

    assert later.outcome == "stored", later.detail
    assert later.candidate is not None
    assert later.candidate.record.predecessor_version_id == replacement.version_id
    assert later.candidate.evidence.root_version_id == replacement.version_id
    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug=_SLUG)
    assert admission is not None
    assert admission.root_version_id == replacement.version_id
    assert admission.active_candidate_version_id == later.candidate.version_id
    assert root.record.version_id != replacement.version_id
    assert not roadmap_candidate_run.supersession_path(plans_dir, _SLUG, replacement.version_id).exists()


def test_direct_structural_promotion_becomes_the_next_feedback_predecessor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The next ordinary batch starts from the directly approved structural head."""
    _root, candidate, seal = _direct_structural_approval(tmp_path, monkeypatch)
    _promote(tmp_path, seal.seal_id)
    _write_open_item_ledger(tmp_path)

    later = _run_batch(tmp_path, _FIRST_BATCH_DELTA)

    assert later.outcome == "stored", later.detail
    assert later.candidate is not None
    assert later.candidate.record.predecessor_version_id == candidate.version_id
    assert later.candidate.evidence.root_version_id == candidate.version_id


def test_edited_structural_candidate_needs_its_own_approval_before_promotion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An edit supersedes the displayed candidate's seal, then promotes only its own seal."""
    root, initial, initial_seal = _direct_structural_approval(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    edited_delta = {
        "operations": [{
            "op": "replace-row", "feedback_id": "batch-one", "artifact_key": "domain",
            "row_type": "entities", "row_id": "entity-order",
            "row": {"id": "entity-order", "name": "Order", "fields": [{
                "name": "owner", "type": "reference", "entity_id": "entity-customer",
            }]},
        }],
        "responses": [{"item_id": "batch-one", "response": "Use owner."}],
        "derived_feedback": [],
    }
    edited = roadmap_candidate_review.decide_structural_candidate(
        _SLUG, initial.version_id, "edit", correction="Use owner.", repo_root=tmp_path,
        plans_dir=plans_dir, invoker=lambda _prompt: (0, json.dumps(edited_delta)),
    )
    assert edited.outcome == "stored", edited.detail
    assert edited.active_candidate is not None
    with pytest.raises(roadmap_version_promotion.RoadmapVersionPromotionError):
        _promote(tmp_path, initial_seal.seal_id)
    assert load_accepted_version(plans_dir=plans_dir, slug=_SLUG).record.version_id == root.record.version_id

    approved = _approve_structural_candidate(plans_dir, edited.active_candidate)
    assert approved.seal is not None, approved.detail
    promoted = _promote(tmp_path, approved.seal.seal_id)
    assert promoted.version_id == edited.active_candidate.version_id


@pytest.mark.parametrize("condition", ("absent", "malformed", "rejected"))
def test_direct_structural_promotion_refusal_changes_no_publication_member(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, condition: str
) -> None:
    _root, candidate, seal = _direct_structural_approval(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    seal_id = seal.seal_id
    if condition == "absent":
        seal_id = "f" * 64
    elif condition == "malformed":
        roadmap_candidate_review.review_seal_path(plans_dir, _SLUG, seal_id).write_bytes(b"invalid seal")
    else:
        rejected = roadmap_candidate_review.decide_structural_candidate(
            _SLUG, candidate.version_id, "reject", plans_dir=plans_dir
        )
        assert rejected.outcome == "stored"

    root = version_namespace_path(plans_dir, _SLUG).parent
    members = (
        accepted_head_path(plans_dir, _SLUG),
        roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG),
        seed_state_path(root),
    )
    before = tuple(path.read_bytes() if path.exists() else None for path in members)
    with pytest.raises(roadmap_version_promotion.RoadmapVersionPromotionError):
        _promote(tmp_path, seal_id)
    assert tuple(path.read_bytes() if path.exists() else None for path in members) == before


def test_repromoting_a_confirmed_structural_approval_reports_already_promoted_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A completed confirmation is idempotent instead of demanding its released active pointer."""
    _root, candidate, seal = _direct_structural_approval(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"

    first = _promote(tmp_path, seal.seal_id)
    members = (
        accepted_head_path(plans_dir, _SLUG),
        roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG),
    )
    before = tuple(path.read_bytes() if path.exists() else None for path in members)

    repeated = _promote(tmp_path, seal.seal_id)

    assert first.outcome == "promoted"
    assert repeated.outcome == "already-promoted"
    assert repeated.version_id == candidate.version_id
    assert tuple(path.read_bytes() if path.exists() else None for path in members) == before


def test_already_promoted_result_carries_a_genuine_accepted_head_not_the_stored_version_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`.head` is declared `AcceptedRoadmapHead`; a `StoredRoadmapVersion` (its accepted-record type) is a different,
    unrelated model and would make `render_accepted_head(result.head)` raise for any future caller that trusts the
    declared type."""
    _root, _candidate, seal = _direct_structural_approval(tmp_path, monkeypatch)
    _promote(tmp_path, seal.seal_id)

    repeated = _promote(tmp_path, seal.seal_id)

    assert repeated.outcome == "already-promoted"
    assert type(repeated.head) is AcceptedRoadmapHead
    render_accepted_head(repeated.head)  # raises RoadmapVersionError for anything but AcceptedRoadmapHead


def test_repromoting_refuses_a_seal_whose_content_identity_disagrees_with_the_accepted_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A matching version id alone does not authorize the already-promoted shortcut: the exhaustive binding
    check shared with `_load_complete_directly_approved_candidate` (`_require_seal_binds_structural_candidate`)
    runs before the shortcut returns, so a seal whose claimed content identity disagrees is refused with the
    same precise message the active-candidate slow path raises for the identical mismatch."""
    _root, _candidate, seal = _direct_structural_approval(tmp_path, monkeypatch)
    _promote(tmp_path, seal.seal_id)
    forged = _forge_seal(tmp_path, seal, approved_content_identity="d" * 64)

    with pytest.raises(
        roadmap_version_promotion.RoadmapVersionPromotionError,
        match="does not bind the exact active candidate",
    ):
        _promote(tmp_path, forged.seal_id)


@pytest.mark.parametrize(
    "field", ("final_capsule_identity", "root_version_id", "source_version_id", "batch_receipt_identity")
)
def test_repromoting_refuses_a_seal_whose_capsule_or_batch_binding_disagrees_with_the_promoted_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    """A correct version id and content identity alone do not authorize the already-promoted shortcut: it
    loads the promoted candidate and runs the same exhaustive binding check the active-candidate slow path
    runs, so a seal with a forged capsule identity or root/source/batch lineage field is refused rather than
    silently confirmed — those fields live only on the candidate's evidence, not on the promoted
    `StoredRoadmapVersion`, so nothing else in the shortcut's cheap checks could have caught this."""
    _root, _candidate, seal = _direct_structural_approval(tmp_path, monkeypatch)
    _promote(tmp_path, seal.seal_id)
    forged = _forge_seal(tmp_path, seal, **{field: "d" * 64})

    with pytest.raises(
        roadmap_version_promotion.RoadmapVersionPromotionError,
        match="does not bind the exact active candidate",
    ):
        _promote(tmp_path, forged.seal_id)


def test_repromoting_refuses_while_a_prior_publication_journal_is_still_dangling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The already-promoted shortcut only reads the accepted-head selector, which is always the journal's
    first member and so can be durably applied before a crash leaves trailing members (the active-candidate
    release, the seed-invalidation effect) unwritten. A version-id/content-identity match alone cannot tell
    a clean promotion from an interrupted one, so the shortcut must not fire while a journal is dangling.

    This case promotes cleanly first (releasing the active-candidate pointer) before re-adding the journal,
    so falling through lands on the earlier active-candidate-binding refusal, not on
    `publish_roadmap_generation`'s own journal-exists recovery raise — that more specific path, reached only
    when the pointer is *not yet* released, is covered separately by the crash-mid-publish test below. What
    this test actually pins is narrower but still real: the `load_pending_generation(...) is None` guard is
    load-bearing here too (confirmed by mutation — deleting it makes this case return a false
    'already-promoted' instead of raising)."""
    _root, _candidate, seal = _direct_structural_approval(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    captured: list[PendingGeneration] = []
    real_publish = roadmap_version_promotion.publish_roadmap_generation

    def spy(generation, **kwargs):
        captured.append(generation)
        return real_publish(generation, **kwargs)

    monkeypatch.setattr(roadmap_version_promotion, "publish_roadmap_generation", spy)
    _promote(tmp_path, seal.seal_id)
    (generation,) = captured
    journal = pending_generation_path(version_namespace_path(plans_dir, _SLUG).parent)
    assert not journal.exists()
    # Writing the captured generation back post-hoc, after a real full promotion, is a cheaper
    # proxy for "a journal is dangling" — not a faithful crash simulation (the real crash-mid-publish
    # case, where the admission pointer is not yet released, is covered separately below).
    journal.write_bytes(render_pending_generation(generation))

    with pytest.raises(roadmap_version_promotion.RoadmapVersionPromotionError):
        _promote(tmp_path, seal.seal_id)

    assert journal.exists()


def test_repromoting_recovers_a_true_crash_between_the_selector_and_the_active_candidate_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A faithful simulation of the crash the journal check exists for: `_replace_generation_members` writes
    the accepted-head selector (member[0]) and then dies before the active-candidate-release member. Unlike
    the post-hoc dangling-journal case above, the admission pointer here is genuinely still active, so the
    shortcut's version-id/content-identity/binding checks would all pass — only the journal check stands
    between this state and a false 'already promoted' success.

    The retry does not reach `publish_roadmap_generation`'s own journal-exists raise: the selector having
    already advanced to the candidate makes `_require_current_active_processing_pair`'s staleness check
    (the candidate's recorded predecessor is the *old* root, but the accepted head is now the candidate
    itself) fire first, on the normal path the shortcut falls through to — itself a correct, if earlier,
    refusal. Reaching the journal-exists raise specifically would need a scenario where the ledger's
    consistency checks all still pass despite a dangling journal, which this interrupted-selector crash
    cannot produce by construction. What this test actually proves is the property that matters: the crash
    state is refused, not silently confirmed."""
    _root, candidate, seal = _direct_structural_approval(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    admission_path = roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG)
    before_admission = admission_path.read_bytes()
    real_replace = roadmap_revision_publish._replace_generation_members

    def crash_after_the_selector_member(root, members, values):
        real_replace(root, members[:1], values[:1])
        raise RuntimeError("simulated crash mid-publish")

    monkeypatch.setattr(
        roadmap_revision_publish, "_replace_generation_members", crash_after_the_selector_member
    )
    with pytest.raises(RuntimeError, match="simulated crash"):
        _promote(tmp_path, seal.seal_id)

    journal = pending_generation_path(version_namespace_path(plans_dir, _SLUG).parent)
    assert journal.exists()
    assert admission_path.read_bytes() == before_admission
    assert load_accepted_version(plans_dir=plans_dir, slug=_SLUG).record.version_id == candidate.version_id

    monkeypatch.setattr(roadmap_revision_publish, "_replace_generation_members", real_replace)
    with pytest.raises(
        roadmap_version_promotion.StaleRoadmapVersionPromotionError,
        match="no longer matches the current root and active candidate",
    ):
        _promote(tmp_path, seal.seal_id)

    assert journal.exists()


# --------------------------------------------------------------------------
# Stack-aware promotion boundary and recovery: carve-outs and agreement
# --------------------------------------------------------------------------


def test_all_presentation_stack_promotion_journals_no_seed_member_and_recovers_with_two_members(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Carve-out: a stack with no structural hop keeps the answered route and its journal exactly as before,
    selector and pointer release with no seed member, so a boundary that demanded a seed member of every
    multi-hop stack fails here."""
    _root, _first, _second, _replacement, seal = _sealed_two_hop_replacement(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    captured = _capture_promotion_generation(monkeypatch)

    _promote(tmp_path, seal.seal_id)

    (generation,) = captured
    roadmap_root = version_namespace_path(plans_dir, _SLUG).parent
    assert [member.relative_path for member in generation.members] == [
        accepted_head_path(plans_dir, _SLUG).relative_to(roadmap_root).as_posix(),
        roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG).relative_to(roadmap_root).as_posix(),
    ]
    assert not _recover_journal(plans_dir, generation).exists()


def test_a_stack_rooted_at_a_promoted_structural_candidate_does_not_count_the_roots_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Carve-out: a structural candidate that was already promoted is settled, so it can be the recorded
    root of the next stack without making that stack structural. Counting the root's route, or walking
    past the recorded root, would demand a structural seal and a seed member here that no decision can
    supply: the answered replacement must promote with selector and release only."""
    _root, structural, seal = _direct_structural_approval(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    _promote(tmp_path, seal.seal_id)
    _write_open_item_ledger(tmp_path)
    reviewed = _run_batch(tmp_path, _FIRST_BATCH_DELTA)
    assert reviewed.candidate is not None, reviewed.detail
    assert reviewed.candidate.evidence.root_version_id == structural.version_id
    asked = roadmap_candidate_review.generate_candidate_question(
        _SLUG, reviewed.candidate.version_id, repo_root=tmp_path, plans_dir=plans_dir,
        invoker=lambda _prompt: (0, _batch_question_response()),
    )
    assert asked.question_inventory is not None, asked.detail
    recorded = roadmap_candidate_review.record_reviewer_answer(
        _SLUG, asked.question_inventory.question.question_id, _BATCH_ANSWER, plans_dir=plans_dir
    )
    assert recorded.answer is not None, recorded.detail
    replaced = _request_batch_replacement(
        tmp_path, asked.question_inventory,
        invoker=lambda _prompt: (0, json.dumps({
            "operations": [],
            "responses": [{"item_id": "batch-one", "response": _BATCH_ANSWER}],
            "derived_feedback": [{"context_id": "derived-answered", "content": "Confirmed."}],
        })),
    )
    assert replaced.replacement is not None, replaced.detail
    sealed = roadmap_candidate_review.seal_review(
        _SLUG, replaced.replacement.version_id, plans_dir=plans_dir
    )
    assert sealed.seal is not None, sealed.detail
    captured = _capture_promotion_generation(monkeypatch)

    promoted = _promote(tmp_path, sealed.seal.seal_id)

    assert promoted.version_id == replaced.replacement.version_id
    (generation,) = captured
    assert len(generation.members) == 2
    assert generation.members[0].relative_path == (
        accepted_head_path(plans_dir, _SLUG).relative_to(version_namespace_path(plans_dir, _SLUG).parent).as_posix()
    )
    assert not _recover_journal(plans_dir, generation).exists()


def test_writer_and_recovery_derive_from_the_same_tip_and_recorded_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The writer and the recovery predicate cannot disagree because they ask one derivation the same
    two questions: the promoted candidate's own version id and its recorded root. After promotion the head
    is the tip itself, so a recovery that took the head as its root would ask (tip, tip), an empty stack,
    and read a structural stack as not structural; the recorded root differs from the head at recovery time."""
    root, _structural, top, seal = _stacked_structural_approval(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    asked: list[tuple[str, str | None]] = []
    real_derivation = roadmap_candidate_run.candidate_stack_route

    def spy(**keywords):
        asked.append((keywords["tip_version_id"], keywords["root_version_id"]))
        return real_derivation(**keywords)

    monkeypatch.setattr(roadmap_candidate_run, "candidate_stack_route", spy)
    captured = _capture_promotion_generation(monkeypatch)
    expected_question = (top.version_id, root.record.version_id)

    _promote(tmp_path, seal.seal_id)

    assert asked and set(asked) == {expected_question}
    asked.clear()
    (generation,) = captured
    head = load_accepted_version(plans_dir=plans_dir, slug=_SLUG)
    assert head is not None and head.record.version_id == top.version_id != root.record.version_id
    assert not _recover_journal(plans_dir, generation).exists()
    assert asked and set(asked) == {expected_question}


# --------------------------------------------------------------------------
# End to end: a runner-built C1-structural / C2-presentation-only stack on every route to the head
# --------------------------------------------------------------------------

_DIGEST_REFUSALS = (
    roadmap_candidate_review._APPROVAL_DIGEST_REQUIRED,
    roadmap_candidate_review._APPROVAL_DIGEST_MISMATCH,
)


def _track_a_current_seed(plans_dir: Path) -> Path:
    """Track one current, unpublished seed under the roadmap and return its seed-state file."""
    roadmap_root = version_namespace_path(plans_dir, _SLUG).parent
    draft = roadmap_root / "plan-seed-drafts" / "plan-order.md"
    draft.parent.mkdir(parents=True)
    draft.write_bytes(b"draft bytes\n")
    state_file = seed_state_path(roadmap_root)
    write_seed_state(
        state_file,
        {"version": 1, "seeds": {"plan-order": {
            "draft_seed_path": "plan-seed-drafts/plan-order.md",
            "status": "current",
            "digest": "a" * 64,
            "published": False,
        }}},
    )
    return state_file


def _assert_head_moved_only_under_a_confirmed_structural_approval(
    plans_dir: Path, *, top, seal, generation: PendingGeneration, state_file: Path
) -> None:
    """The plan's binary observable, read from stored facts and never from content: the head is the top,
    the seal that moved it is a structural approval of that top, and the one journal it was published in
    carried the seed-state member that invalidated every tracked seed."""
    roadmap_root = version_namespace_path(plans_dir, _SLUG).parent
    head = load_accepted_version(plans_dir=plans_dir, slug=_SLUG)
    assert head is not None and head.record.version_id == top.version_id
    assert (seal.decision, seal.approved_candidate_version_id) == ("structural-approval", top.version_id)
    assert {member.relative_path for member in generation.members} == {
        accepted_head_path(plans_dir, _SLUG).relative_to(roadmap_root).as_posix(),
        roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG).relative_to(roadmap_root).as_posix(),
        state_file.relative_to(roadmap_root).as_posix(),
    }
    assert load_seed_state(state_file)["seeds"]["plan-order"]["status"] == "invalidated"


def _assert_nothing_published(plans_dir: Path, *, before: dict[str, bytes], root) -> None:
    """A refused route leaves the head, the pointer, the seed state, and the journal alone. All four live
    in the plans tree, so byte equality of the tree is the check; the head and journal are named too so a
    failure says which one moved."""
    head = load_accepted_version(plans_dir=plans_dir, slug=_SLUG)
    assert head is not None and head.record.version_id == root.record.version_id
    assert not pending_generation_path(version_namespace_path(plans_dir, _SLUG).parent).exists()
    assert _tree(plans_dir) == before


def test_direct_route_promotes_a_runner_built_structural_stack_only_under_a_confirmed_approval_of_its_top(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The shape of the reported defect, built by the runner alone: C1 changes a field (structural) and C2,
    the presentation-only top, is what the head receives. C1's own decisions end once C2 is stacked, so the
    head moves only through a `structural-approval` seal on C2, and that promotion carries the seed-state
    effect of C1's change even though C2's own route is presentation-only."""
    root, structural, top = _structural_stack(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    state_file = _track_a_current_seed(plans_dir)
    before_decisions = _tree(plans_dir)
    for decision in ("approve", "edit", "reject"):
        superseded = roadmap_candidate_review.decide_structural_candidate(
            _SLUG, structural.version_id, decision, plans_dir=plans_dir, repo_root=tmp_path,
            correction="Use owner.",
            invoker=lambda _prompt: pytest.fail("a superseded hop reached the backend"),
            confirm_digest=_confirming_digest(plans_dir, structural) if decision == "approve" else None,
        )
        assert superseded.outcome == "refused", (decision, superseded.detail)
        assert superseded.seal is None
        assert superseded.detail not in _DIGEST_REFUSALS, "refused as superseded, not for the digest"
    _assert_nothing_published(plans_dir, before=before_decisions, root=root)

    approved = _approve_structural_candidate(plans_dir, top)
    assert approved.seal is not None, approved.detail
    captured = _capture_promotion_generation(monkeypatch)
    promoted = _promote(tmp_path, approved.seal.seal_id)

    assert promoted.version_id == top.version_id
    (generation,) = captured
    _assert_head_moved_only_under_a_confirmed_structural_approval(
        plans_dir, top=top, seal=approved.seal, generation=generation, state_file=state_file
    )
    head_domain = stored_artifact_path(plans_dir, _SLUG, top.version_id, "domain").read_text(encoding="utf-8")
    root_domain = stored_artifact_path(plans_dir, _SLUG, root.record.version_id, "domain").read_text(encoding="utf-8")
    assert "buyer" in head_domain and "buyer" not in root_domain, "the head must carry C1's change"


def test_answered_route_cannot_carry_a_runner_built_structural_hop_into_the_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The answered route is closed to this stack at both ends. Its entry refuses and names the decision
    command without reaching a backend; and a seal minted past the entry guard, which stands for one
    issued before the guard existed, is refused at the promotion boundary, so nothing publishes. This
    repeats the boundary case above on purpose, as one walk over a stack the runner built."""
    root, _structural, top = _structural_stack(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    state_file = _track_a_current_seed(plans_dir)
    before_entry = _tree(plans_dir)

    asked = roadmap_candidate_review.generate_candidate_question(
        _SLUG, top.version_id, repo_root=tmp_path, plans_dir=plans_dir,
        invoker=lambda _prompt: pytest.fail("a structural stack invoked the answered-route backend"),
    )

    assert asked.outcome == "refused"
    assert "--decide-candidate" in asked.detail
    _assert_nothing_published(plans_dir, before=before_entry, root=root)
    with monkeypatch.context() as before_the_entry_guard:
        before_the_entry_guard.setattr(
            roadmap_candidate_review, "_require_answered_review_route", lambda _candidate, **_keywords: None
        )
        answered = _answer_over_the_active_tip(
            tmp_path, top, question=_receipt_anchored_question(top),
            replacement=json.dumps(_PRESENTATION_ONLY_ANSWER_DELTA),
        )
    assert answered.seal.decision != "structural-approval"
    before_promotion = _tree(plans_dir)
    captured = _capture_promotion_generation(monkeypatch)

    with pytest.raises(roadmap_version_promotion.RoadmapVersionPromotionError, match="--decide-candidate"):
        _promote(tmp_path, answered.seal.seal_id)

    assert captured == [], "the writer must refuse before it publishes anything"
    _assert_nothing_published(plans_dir, before=before_promotion, root=root)
    assert load_seed_state(state_file)["seeds"]["plan-order"]["status"] == "current"


def _stack_edited_above_its_approval(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """C1 (structural) -> C2 (presentation-only), C2 approved, then C2 edited into E2.

    The edit sources E2 from C2's own source, so E2's hops are C1 and E2 and C2 is not among them.
    """
    root, structural, top, top_seal = _stacked_structural_approval(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    # Differs from C2's stored delta: an identical one would reproduce C2's identity and collide with it.
    reply = {
        "operations": [], "responses": [],
        "derived_feedback": [{"context_id": "derived-edit", "content": "Edited."}],
    }
    edited = roadmap_candidate_review.decide_structural_candidate(
        _SLUG, top.version_id, "edit", correction="Tighten the wording.",
        repo_root=tmp_path, plans_dir=plans_dir, invoker=lambda _prompt: (0, json.dumps(reply)),
    )
    assert edited.outcome == "stored", edited.detail
    replacement = edited.active_candidate
    assert replacement is not None
    # A helper that built a different shape would let every case built on it pass without testing anything.
    assert replacement.record.predecessor_version_id == structural.version_id
    assert replacement.evidence.operation_classification is _PRESENTATION_ONLY
    assert roadmap_candidate_run.candidate_stack_route(
        plans_dir=plans_dir, slug=_SLUG,
        tip_version_id=replacement.version_id, root_version_id=root.record.version_id,
    ).is_structural
    return root, structural, top, top_seal, replacement


def test_edited_route_promotes_a_structural_stack_only_under_the_replacements_own_confirmed_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An edit issues no seal and ends the edited candidate's: C2's approval cannot promote E2, and C2's
    stack digest does not confirm E2's different stack. E2 reaches the head only under its own confirmed
    approval, and that promotion journals the seed member exactly as the direct route's does."""
    root, _structural, top, top_seal, replacement = _stack_edited_above_its_approval(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    state_file = _track_a_current_seed(plans_dir)
    top_seal_path = roadmap_candidate_review.review_seal_path(plans_dir, _SLUG, top_seal.seal_id)
    assert list(top_seal_path.parent.iterdir()) == [top_seal_path], "the edit must issue no seal for E2"
    before = _tree(plans_dir)

    with pytest.raises(
        roadmap_version_promotion.RoadmapVersionPromotionError, match="does not bind the active candidate"
    ):
        _promote(tmp_path, top_seal.seal_id)
    wrong_stack = roadmap_candidate_review.decide_structural_candidate(
        _SLUG, replacement.version_id, "approve", plans_dir=plans_dir,
        confirm_digest=_confirming_digest(plans_dir, top),
    )

    assert wrong_stack.outcome == "refused"
    assert wrong_stack.detail == roadmap_candidate_review._APPROVAL_DIGEST_MISMATCH
    _assert_nothing_published(plans_dir, before=before, root=root)
    approved = _approve_structural_candidate(plans_dir, replacement)
    assert approved.seal is not None, approved.detail
    captured = _capture_promotion_generation(monkeypatch)
    promoted = _promote(tmp_path, approved.seal.seal_id)

    assert promoted.version_id == replacement.version_id
    (generation,) = captured
    _assert_head_moved_only_under_a_confirmed_structural_approval(
        plans_dir, top=replacement, seal=approved.seal, generation=generation, state_file=state_file
    )


@pytest.mark.parametrize("promoted_top", ("direct-top", "edited-top"))
def test_recovery_of_a_completed_structural_stack_promotion_requires_the_seed_member(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, promoted_top: str
) -> None:
    """Recovery drops a journal whose every member is already at its new bytes, and refuses one that omits
    the seed member, leaving it in place. It is asked over both chain shapes a promoted top can have: hops
    C1 and C2 for the directly approved top, and C1 and E2 for an edited one, where C2 is not a hop."""
    plans_dir = tmp_path / "plans"
    if promoted_top == "direct-top":
        _root, _structural, _top, seal = _stacked_structural_approval(tmp_path, monkeypatch)
    else:
        _root, _structural, _top, _old_seal, replacement = _stack_edited_above_its_approval(tmp_path, monkeypatch)
        approved = _approve_structural_candidate(plans_dir, replacement)
        assert approved.seal is not None, approved.detail
        seal = approved.seal
    captured = _capture_promotion_generation(monkeypatch)
    _promote(tmp_path, seal.seal_id)
    (generation,) = captured
    assert len(generation.members) == 3, "selector, pointer release, and seed member"
    after_promotion = _tree(plans_dir)

    journal = _recover_journal(plans_dir, generation)

    assert not journal.exists()
    assert _tree(plans_dir) == after_promotion
    seedless = PendingGeneration(kind=generation.kind, members=generation.members[:2])
    journal.write_bytes(render_pending_generation(seedless))
    with roadmap_writer_guard(plans_dir, _SLUG) as token:
        with pytest.raises(RoadmapPublicationRecoveryError):
            recover_roadmap_publication(plans_dir=plans_dir, slug=_SLUG, writer_token=token)
    assert journal.read_bytes() == render_pending_generation(seedless)


def test_an_approval_of_a_lower_hop_cannot_promote_after_a_later_batch_stacks_on_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The state the retired block used to prevent, now reachable: C1 is approved and then C2 stacks above
    it. An approval never carries forward to a hop stacked after it, so C1's seal cannot promote, C1's
    digest does not confirm C2's larger stack, and C2 reaches the head only under its own confirmation."""
    monkeypatch.setattr(roadmap_version_promotion, "check_complete_roadmap_gates", _green_gates)
    root, (structural,) = _store_stack(tmp_path, monkeypatch, ("structural",))
    plans_dir = tmp_path / "plans"
    lower_digest = _confirming_digest(plans_dir, structural)
    lower = _approve_structural_candidate(plans_dir, structural)
    assert lower.seal is not None, lower.detail
    stacked = _run_batch(tmp_path, _SECOND_BATCH_DELTA)
    assert stacked.outcome == "stored", stacked.detail
    assert stacked.candidate is not None
    top = stacked.candidate
    assert top.evidence.source_version_id == structural.version_id
    assert top.evidence.operation_classification is _PRESENTATION_ONLY
    before = _tree(plans_dir)

    with pytest.raises(
        roadmap_version_promotion.RoadmapVersionPromotionError, match="does not bind the active candidate"
    ):
        _promote(tmp_path, lower.seal.seal_id)
    stale = roadmap_candidate_review.decide_structural_candidate(
        _SLUG, top.version_id, "approve", plans_dir=plans_dir, confirm_digest=lower_digest
    )

    assert stale.outcome == "refused"
    assert stale.detail == roadmap_candidate_review._APPROVAL_DIGEST_MISMATCH
    _assert_nothing_published(plans_dir, before=before, root=root)
    approved = _approve_structural_candidate(plans_dir, top)
    assert approved.seal is not None, approved.detail
    captured = _capture_promotion_generation(monkeypatch)
    promoted = _promote(tmp_path, approved.seal.seal_id)
    assert promoted.version_id == top.version_id
    (generation,) = captured
    assert len(generation.members) == 3, "C2's promotion journals the seed member for C1's change"


# --- INDEX.md refresh after promotion -------------------------------------------------------------


def _promotion_index_path(tmp_path: Path) -> Path:
    from plan_tool.roadmap_artifacts import roadmap_dir
    from plan_tool.roadmap_index import INDEX_FILENAME

    return roadmap_dir(tmp_path / "plans", _SLUG) / INDEX_FILENAME


def _promotion_index_render(tmp_path: Path) -> str:
    from plan_tool.roadmap_index import (
        collect_index_rows,
        collect_index_stack_lines,
        render_roadmap_index,
    )

    head_version_id, rows = collect_index_rows(tmp_path / "plans", _SLUG)
    stack_lines = collect_index_stack_lines(tmp_path / "plans", _SLUG, head_version_id)
    return render_roadmap_index(_SLUG, head_version_id, rows, stack_lines)


def test_index_shows_new_head_after_promotion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _root, _initial, replacement, seal = _sealed_replacement(tmp_path, monkeypatch)

    result = _promote(tmp_path, seal.seal_id)

    text = _promotion_index_path(tmp_path).read_text()
    assert result.outcome == "promoted"
    assert text == _promotion_index_render(tmp_path)
    assert f"Version `{replacement.version_id[:8]}`." in text


def test_already_promoted_result_still_refreshes_the_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A crash between the promotion publish and the index write heals on the idempotent retry."""
    _root, _candidate, seal = _direct_structural_approval(tmp_path, monkeypatch)
    _promote(tmp_path, seal.seal_id)
    _promotion_index_path(tmp_path).unlink()

    repeated = _promote(tmp_path, seal.seal_id)

    assert repeated.outcome == "already-promoted"
    assert _promotion_index_path(tmp_path).read_text() == _promotion_index_render(tmp_path)


def test_index_write_failure_never_fails_or_rolls_back_a_promotion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from plan_tool import roadmap

    _root, _initial, replacement, seal = _sealed_replacement(tmp_path, monkeypatch)
    _promotion_index_path(tmp_path).unlink(missing_ok=True)

    def broken(*_args, **_kwargs):
        raise OSError("read-only filesystem")

    monkeypatch.setattr(roadmap, "write_roadmap_index", broken)

    result = _promote(tmp_path, seal.seal_id)

    warnings = [line for line in capsys.readouterr().err.splitlines() if "INDEX.md" in line]
    assert result.outcome == "promoted"
    assert len(warnings) == 1
    accepted = load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG)
    assert accepted is not None
    assert accepted.record.version_id == replacement.version_id


def test_promotion_generation_names_no_index_member(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """INDEX.md is written after the publish, never as a generation member crash recovery could replay."""
    _root, _initial, _replacement, seal = _sealed_replacement(tmp_path, monkeypatch)
    captured = _capture_promotion_generation(monkeypatch)

    _promote(tmp_path, seal.seal_id)

    assert captured
    assert not any("INDEX" in member.relative_path for g in captured for member in g.members)
