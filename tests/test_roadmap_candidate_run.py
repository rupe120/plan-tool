"""Tests for bounded immutable roadmap candidate proposal storage."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import replace

import pytest

from plan_tool import roadmap_candidate, roadmap_candidate_context, roadmap_candidate_review, roadmap_candidate_run, roadmap_gates, roadmap_versions
from plan_tool.roadmap import STAGES
from plan_tool.roadmap_artifacts import (
    STACK_CONCERNS,
    AttributeDispositionRow,
    ComponentRow,
    ComponentsArtifact,
    ConstraintDisposition,
    ConstraintRow,
    ConstraintsArtifact,
    DecisionRow,
    DecisionStatus,
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
from plan_tool.roadmap_candidate_context import CandidateContextPredecessor, build_candidate_context, candidate_collection_hints
from plan_tool.roadmap_candidate import materialize_candidate, parse_candidate_delta
from plan_tool.roadmap_feedback_ledger import (
    LedgerState,
    LedgerTarget,
    ReviewerFeedbackGroup,
    ReviewerFeedbackItem,
    ReviewerItemState,
    RoadmapFeedbackLedger,
    load_ledger,
    render_ledger,
    roadmap_feedback_ledger_path,
    target_fingerprint,
)
from plan_tool.roadmap_impact_snapshot import RoadmapGateOutcome
from plan_tool.roadmap_revision_publish import (
    publish_roadmap_generation,
    roadmap_writer_guard,
)
from plan_tool.roadmap_versions import (
    AcceptedRoadmapHead,
    PreparedRoadmapVersion,
    RoadmapVersionContent,
    accepted_head_path,
    build_root_enrollment_generation,
    create_root_version,
    load_accepted_version,
    version_directory_path,
)
from plan_tool import run_log as run_log_module
from plan_tool.run_log import read_run_events


_SLUG = "storefront"
_SELECTOR = "domain:feedback-order"


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


@pytest.mark.parametrize("value", ("0x" + "a" * 62, "-" + "a" * 63, "a" * 63 + "_"))
def test_candidate_digest_validator_rejects_non_hex_digest_text(value: str) -> None:
    with pytest.raises(ValueError, match="SHA-256 digest"):
        roadmap_candidate_run._require_digest(value, name="candidate identity")


def test_candidate_evidence_digest_count_tracks_the_stage_inventory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(roadmap_candidate_run, "STAGES", STAGES[:3])
    digests = ("a" * 64, "b" * 64, "c" * 64)

    assert roadmap_candidate_run.CandidateProposalEvidence._requires_artifact_digests(
        digests
    ) == digests


def test_candidate_admission_rejects_parent_slug() -> None:
    with pytest.raises(ValueError, match="slug is invalid"):
        roadmap_candidate_run.CandidateProposalAdmission._requires_slug("..")


@pytest.mark.parametrize(
    ("outcome", "expected"),
    (
        ("stored", 0),
        ("response-rejected", 1),
        ("failed", 1),
        ("refused", 2),
        ("interrupted", 130),
    ),
)
def test_candidate_proposal_outcome_return_codes_are_closed(outcome: str, expected: int) -> None:
    assert roadmap_candidate_run._result_return_code(outcome) == expected  # type: ignore[arg-type]


def test_refused_candidate_proposal_records_its_usage_exit(tmp_path) -> None:
    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
    )

    events = read_run_events(next((tmp_path / ".plan-tool" / "runs" / _SLUG).glob("*.jsonl")))

    assert result.outcome == "refused"
    assert next(event for event in events if event["event"] == "run_end")["rc"] == 2
    terminal = next(event for event in events if event["event"] == "phase_end")
    assert terminal["failure_detail"] == result.detail
    assert terminal["failure_attempt"] is None
    assert terminal["response_capture"] == "not-applicable"
    assert not any(event["event"] == "parse_failure" for event in events)


def _resolved_root(domain_body: str = "domain\n") -> PreparedRoadmapVersion:
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
        body=domain_body,
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
        for stage, artifact in zip(STAGES, (domain, constraints, components, plans), strict=True)
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


def _enroll(tmp_path, domain_body: str = "domain\n") -> PreparedRoadmapVersion:
    root = _resolved_root(domain_body)
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


def _interrupting_invoker(_prompt: str) -> tuple[int, str]:
    """An invoker that reports a first KeyboardInterrupt, for second-interrupt
    (interrupt-during-cleanup) regression tests."""
    raise KeyboardInterrupt


def _raise_interrupt_for_run_log_events(*event_names: str):
    """Build a run_log_module._append_jsonl_line replacement that raises
    KeyboardInterrupt for the named event types and otherwise writes
    normally — for simulating a second interrupt landing during one of the
    finally block's best-effort terminal-record writes."""
    original_append = run_log_module._append_jsonl_line

    def intercept(path, payload):
        if payload.get("event") in event_names:
            raise KeyboardInterrupt
        original_append(path, payload)

    return intercept


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
                            "name": "Customer order",
                            "fields": [],
                        },
                    }
                ]
            }
        }
    )


def test_initial_delta_stores_one_gate_clean_inert_candidate_without_moving_accepted_head(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    head_before = accepted_head_path(tmp_path / "plans", _SLUG).read_bytes()

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _delta_response()),
    )

    assert result.outcome == "stored"
    assert result.candidate is not None
    assert result.candidate.record.predecessor_version_id == root.record.version_id
    assert result.candidate.content.brief_bytes == root.content.brief_bytes
    assert result.candidate.evidence.predecessor_diff.changed_rows[0].after == {
        "id": "entity-order",
        "name": "Customer order",
        "fields": [
            {"name": "customer", "type": "reference", "entity_id": "entity-customer"}
        ],
    }
    assert result.candidate.evidence.gate_evidence == tuple(
        roadmap_candidate_run.CandidateGateEvidence(artifact_key=stage.artifact_key, violations=())
        for stage in STAGES
    )
    assert result.candidate.evidence.review_requirement is None
    assert b'"review_requirement"' not in roadmap_candidate_run.render_candidate_evidence(
        result.candidate.evidence
    )
    assert accepted_head_path(tmp_path / "plans", _SLUG).read_bytes() == head_before
    assert load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG).record == root.record


def test_pre_change_gate_clean_candidate_evidence_replays_with_existing_identity(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)

    stored = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _delta_response()),
    )

    assert stored.candidate is not None
    evidence_path = roadmap_candidate_run.candidate_evidence_path(
        tmp_path / "plans", _SLUG, stored.candidate.version_id
    )
    legacy_bytes = evidence_path.read_bytes()
    assert b'"review_requirement"' not in legacy_bytes
    replayed = roadmap_candidate_run.load_stored_candidate_proposal(
        plans_dir=tmp_path / "plans", slug=_SLUG, candidate_version_id=stored.candidate.version_id
    )

    assert replayed.evidence.review_requirement is None
    assert replayed.evidence.normalized_operations is None
    assert replayed.evidence.operation_classification is None
    assert b'"normalized_operations"' not in legacy_bytes
    assert b'"operation_classification"' not in legacy_bytes
    assert roadmap_candidate_run.render_candidate_evidence(replayed.evidence) == legacy_bytes


# Captured from the selector-era flow at e9a3e30b, before the batch route added identity
# inputs and admission pointer keys. Stored records written then must keep recomputing to
# these values, so the golden is the pre-batch value and never HEAD's own output.
_PRE_BATCH_CANDIDATE_VERSION_ID = "ad11afeba4192ceab3872deb3f5fe39387b310d35516d3e17c96330390683904"
_PRE_BATCH_CONTENT_IDENTITY = "223e5bed16c7ff14bfb348c4c09eeae354f8ccf6bc33a3f7763b5932388ace8f"
_PRE_BATCH_ADMISSION_SHA256 = "aa1a0ed197d553805700bc99aa6a8dc5f380ff471c13e0620a99b7041e00d4ff"
_PRE_BATCH_ADMISSION_KEYS = {
    "candidate_version_id", "capsule", "expansion_available", "feedback",
    "predecessor_version_id", "receipt", "roadmap_slug", "schema_version",
}


def test_selector_era_identity_and_admission_bytes_are_the_values_stored_before_the_batch_route(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A field added for the batch route may not move an identity or a canonical byte
    string that predates it: a stored selector-era candidate is recomputed from its
    stored bytes on every review, replacement and promotion."""
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    plans_dir = tmp_path / "plans"

    # The pinned identities were issued under the 192 KiB ceiling the payload records. Only issuance
    # is patched: reading the stored candidate back must reproduce it under the current ceiling.
    with monkeypatch.context() as issued_then:
        issued_then.setattr(roadmap_candidate_context, "CANDIDATE_CONTEXT_MAX_BYTES", 192 * 1024)
        stored = roadmap_candidate_run.run_initial_candidate_proposal(
            _SLUG, _SELECTOR, repo_root=tmp_path, plans_dir=plans_dir,
            invoker=lambda _prompt: (0, _delta_response()),
        )

    assert stored.candidate is not None
    assert stored.candidate.version_id == _PRE_BATCH_CANDIDATE_VERSION_ID
    assert stored.candidate.evidence.content_identity == _PRE_BATCH_CONTENT_IDENTITY
    admission_bytes = roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG).read_bytes()
    assert hashlib.sha256(admission_bytes).hexdigest() == _PRE_BATCH_ADMISSION_SHA256
    assert set(json.loads(admission_bytes)) == _PRE_BATCH_ADMISSION_KEYS
    admission = roadmap_candidate_run.parse_candidate_admission(admission_bytes)
    assert roadmap_candidate_run.render_candidate_admission(admission) == admission_bytes
    reloaded = roadmap_candidate_run.load_stored_candidate_proposal(
        plans_dir=plans_dir, slug=_SLUG, candidate_version_id=_PRE_BATCH_CANDIDATE_VERSION_ID
    )
    assert reloaded.evidence.content_identity == _PRE_BATCH_CONTENT_IDENTITY


def test_batch_admission_keeps_both_pointer_keys_including_a_null_for_a_released_pointer(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only a selector-era admission omits the pointer keys. A batch admission states its
    pointer explicitly, and a released pointer is an explicit null, never an absent key."""
    root, first = _store_first_batch_candidate(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    live = json.loads(roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG).read_bytes())
    assert live["root_version_id"] == root.record.version_id
    assert live["active_candidate_version_id"] == first.version_id

    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug=_SLUG)
    assert admission is not None
    released_generation = roadmap_candidate_run.build_active_candidate_pointer_release_generation(
        plans_dir=plans_dir, slug=_SLUG, admission=admission
    )
    released = json.loads(released_generation.members[0].new_bytes)
    assert released["root_version_id"] == root.record.version_id
    assert "active_candidate_version_id" in released
    assert released["active_candidate_version_id"] is None


def test_review_required_initial_delta_stores_exact_requirement_without_moving_accepted_head(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    predecessor = load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG)
    assert predecessor is not None
    capsule = build_candidate_context(predecessor, _SELECTOR).capsule
    assert capsule is not None
    expected = materialize_candidate(
        parse_candidate_delta(json.dumps(json.loads(_review_required_delta_response())["delta"])),
        predecessor=predecessor,
        capsule=capsule,
        receipt=capsule.receipt,
    )
    assert expected.review_required is not None
    head_before = accepted_head_path(tmp_path / "plans", _SLUG).read_bytes()

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _review_required_delta_response()),
    )

    assert result.outcome == "stored"
    assert result.candidate is not None
    requirement = result.candidate.evidence.review_requirement
    assert requirement is not None
    assert roadmap_candidate._wire_value(requirement) == roadmap_candidate._wire_value(
        expected.review_required.review_requirement
    )
    assert requirement.initial_disclosed_impact_identity == (
        expected.review_required.review_requirement.initial_disclosed_impact_identity
    )
    assert accepted_head_path(tmp_path / "plans", _SLUG).read_bytes() == head_before
    assert load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG).record == root.record


def test_review_required_candidate_reentry_replays_persisted_requirement_without_backend_call(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    first = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _review_required_delta_response()),
    )
    second = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: pytest.fail("stored review-required candidate must not invoke"),
    )

    assert first.candidate is not None
    assert second.outcome == "stored", second.detail
    assert second.call_count == 0
    assert second.candidate is not None
    assert second.candidate.version_id == first.candidate.version_id
    assert second.candidate.evidence.review_requirement == first.candidate.evidence.review_requirement


def test_candidate_evidence_validation_uses_the_materializer_review_disposition(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    stored = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _review_required_delta_response()),
    )
    assert stored.candidate is not None
    monkeypatch.setattr(
        roadmap_candidate,
        "_candidate_diff_requires_review_requirement",
        lambda _diff: False,
    )

    with pytest.raises(
        roadmap_candidate_run.CandidateProposalError,
        match="candidate review requirement does not match materialization",
    ):
        roadmap_candidate_run.load_stored_candidate_proposal(
            plans_dir=tmp_path / "plans",
            slug=_SLUG,
            candidate_version_id=stored.candidate.version_id,
        )


def test_review_required_storage_replays_repeated_relation_occurrences_without_deduplication(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    extract_relations = roadmap_candidate.extract_declared_relations

    def duplicate_relation_occurrences(**artifacts):
        return tuple(
            duplicate
            for relation in extract_relations(**artifacts)
            for duplicate in (relation, relation)
        )

    monkeypatch.setattr(roadmap_candidate, "extract_declared_relations", duplicate_relation_occurrences)
    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _review_required_delta_response()),
    )

    assert result.candidate is not None
    requirement = result.candidate.evidence.review_requirement
    assert requirement is not None
    relation_atoms = [atom for atom in requirement.impact_atoms if atom.kind == "relation"]
    assert len(relation_atoms) == 2
    dropped = requirement.model_copy(
        update={
            "impact_atoms": tuple(
                atom
                for atom in requirement.impact_atoms
                if atom is not relation_atoms[-1]
            )
        }
    )
    dropped = dropped.model_copy(
        update={
            "initial_disclosed_impact_identity": roadmap_candidate._review_impact_identity(
                reason=dropped.reason,
                predecessor_version_id=dropped.predecessor_version_id,
                selected_feedback=dropped.selected_feedback,
                receipt=dropped.capsule_receipt,
                normalized_operations=dropped.normalized_operations,
                predecessor_diff=dropped.predecessor_diff,
                affected_predecessor_members=dropped.affected_predecessor_members,
                impact_atoms=dropped.impact_atoms,
            )
        }
    )
    evidence_path = roadmap_candidate_run.candidate_evidence_path(
        tmp_path / "plans", _SLUG, result.candidate.version_id
    )
    evidence_path.write_bytes(
        roadmap_candidate_run.render_candidate_evidence(
            result.candidate.evidence.model_copy(update={"review_requirement": dropped})
        )
    )

    with pytest.raises(roadmap_candidate_run.CandidateProposalError, match="review requirement"):
        roadmap_candidate_run.load_stored_candidate_proposal(
            plans_dir=tmp_path / "plans", slug=_SLUG, candidate_version_id=result.candidate.version_id
        )


def test_fixed_roadmap_admission_refuses_different_feedback_before_a_backend_call(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    first = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _delta_response()),
    )

    second = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        "constraints:another-feedback",
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: pytest.fail("a different feedback must not invoke"),
    )

    assert first.outcome == "stored"
    assert second.outcome == "refused"
    assert second.call_count == 0


def test_reentry_returns_the_bound_candidate_without_another_backend_call(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    first = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _delta_response()),
    )
    second = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: pytest.fail("stored candidate re-entry must not invoke"),
    )

    assert first.candidate is not None
    assert second.outcome == "stored"
    assert second.call_count == 0
    assert second.candidate is not None
    assert second.candidate.version_id == first.candidate.version_id


@pytest.mark.parametrize("prior", [64 * 1024, 192 * 1024])
def test_reentry_of_a_lineage_stored_under_an_earlier_ceiling_survives_a_ceiling_raise(
    prior: int, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stored capsule reproduces at its recorded ceiling, so raising the current one must not turn
    a free re-entry into `candidate capsule cannot be reproduced from its predecessor`."""
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    with monkeypatch.context() as issued_then:
        issued_then.setattr(roadmap_candidate_context, "CANDIDATE_CONTEXT_MAX_BYTES", prior)
        first = roadmap_candidate_run.run_initial_candidate_proposal(
            _SLUG, _SELECTOR, repo_root=tmp_path, plans_dir=tmp_path / "plans",
            invoker=lambda _prompt: (0, _delta_response()),
        )

    second = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG, _SELECTOR, repo_root=tmp_path, plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: pytest.fail("stored candidate re-entry must not invoke"),
    )

    assert first.candidate is not None
    assert first.candidate.evidence.capsule.ceiling_bytes == prior
    assert second.outcome == "stored", second.detail
    assert second.call_count == 0
    assert second.candidate is not None
    assert second.candidate.version_id == first.candidate.version_id


def test_valid_inventory_expansion_persists_final_capsule_then_requests_one_delta(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    predecessor = load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG)
    assert predecessor is not None
    capsule = build_candidate_context(predecessor, _SELECTOR).capsule
    assert capsule is not None
    entry = next(item for item in capsule.inventory if item.row_id == "entity-compact")
    replies = iter((json.dumps({"expand": entry.model_dump()}), _delta_response()))
    prompts: list[str] = []

    def invoke(prompt: str) -> tuple[int, str]:
        prompts.append(prompt)
        if len(prompts) == 2:
            stored = roadmap_candidate_run.load_candidate_admission(
                plans_dir=tmp_path / "plans", slug=_SLUG
            )
            assert stored is not None
            assert stored.expansion_available is False
            assert stored.capsule.expansion is not None
        return 0, next(replies)

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=invoke,
    )

    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=tmp_path / "plans", slug=_SLUG)
    assert root.record.version_id == predecessor.record.version_id
    assert result.outcome == "stored"
    assert result.call_count == 2
    assert len(prompts) == 2
    assert admission is not None
    assert admission.expansion_available is False
    assert admission.capsule.expansion is not None
    assert entry.row_id in prompts[1]


def test_failed_expansion_follow_up_reuses_the_persisted_final_capsule(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    predecessor = load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG)
    assert predecessor is not None
    capsule = build_candidate_context(predecessor, _SELECTOR).capsule
    assert capsule is not None
    entry = next(item for item in capsule.inventory if item.row_id == "entity-compact")
    expansion = json.dumps({"expand": entry.model_dump()})
    first_prompts: list[str] = []

    def fail_follow_up(prompt: str) -> tuple[int, str]:
        first_prompts.append(prompt)
        return (0, expansion) if len(first_prompts) == 1 else (1, "")

    first = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=fail_follow_up,
    )
    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=tmp_path / "plans", slug=_SLUG)
    resumed_prompts: list[str] = []

    second = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda prompt: resumed_prompts.append(prompt) or (0, _delta_response()),
    )

    assert first.outcome == "failed"
    assert first.call_count == 2
    assert admission is not None
    assert admission.candidate_version_id is None
    assert admission.expansion_available is False
    assert admission.capsule.expansion is not None
    assert second.outcome == "stored"
    assert second.call_count == 1
    assert resumed_prompts == [first_prompts[1]]


def test_review_required_candidate_after_initial_expansion_binds_final_admitted_capsule(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    predecessor = load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG)
    assert predecessor is not None
    compact_capsule = build_candidate_context(predecessor, _SELECTOR).capsule
    assert compact_capsule is not None
    entry = next(item for item in compact_capsule.inventory if item.row_id == "entity-compact")
    replies = iter(
        (json.dumps({"expand": entry.model_dump()}), _review_required_delta_response())
    )

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, next(replies)),
    )
    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=tmp_path / "plans", slug=_SLUG)

    assert result.candidate is not None
    assert admission is not None
    assert result.candidate.evidence.review_requirement is not None
    assert result.candidate.evidence.capsule == admission.capsule
    assert result.candidate.evidence.receipt == admission.receipt
    assert result.candidate.evidence.capsule.expansion is not None
    assert result.candidate.evidence.capsule != compact_capsule


def test_second_expansion_request_stops_without_a_candidate_or_third_request(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    predecessor = load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG)
    assert predecessor is not None
    capsule = build_candidate_context(predecessor, _SELECTOR).capsule
    assert capsule is not None
    entry = next(item for item in capsule.inventory if item.row_id == "entity-compact")
    expansion = json.dumps({"expand": entry.model_dump()})
    calls: list[str] = []

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda prompt: calls.append(prompt) or (0, expansion),
    )

    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=tmp_path / "plans", slug=_SLUG)
    assert result.outcome == "response-rejected"
    assert result.call_count == 2
    assert len(calls) == 2
    assert admission is not None
    assert admission.candidate_version_id is None
    assert admission.expansion_available is False


@pytest.mark.parametrize(
    "response",
    (
        '{"delta":{"operations":[]},"expand":{}}',
        '{"delta":{"operations":[]},"delta":{"operations":[]}}',
        '{"delta":{"operations":[NaN]}}',
        '{"delta":{"operations":[]}} trailing',
        '{"delta":{"operations":[]},"raw_artifact":"write this"}',
    ),
)
def test_initial_response_requires_exactly_one_closed_disposition(
    tmp_path, monkeypatch: pytest.MonkeyPatch, response: str
) -> None:
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, response),
    )

    assert result.outcome == "response-rejected"
    assert result.call_count == 1
    assert roadmap_candidate_run.load_candidate_admission(
        plans_dir=tmp_path / "plans", slug=_SLUG
    ).candidate_version_id is None


def test_candidate_rejection_records_its_reason_and_exact_response_receipt(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    response = '{"delta":{"operations":[]}} candidate response secret'

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, response),
    )

    log_path = next((tmp_path / ".plan-tool" / "runs" / _SLUG).glob("*.jsonl"))
    events = read_run_events(log_path)
    failure = next(event for event in events if event["event"] == "parse_failure")
    terminal = next(event for event in events if event["event"] == "phase_end")

    assert result.outcome == "response-rejected"
    assert result.detail == "candidate response must not contain trailing text"
    assert failure["phase"] == roadmap_candidate_run.CANDIDATE_PROPOSAL_PHASE
    assert failure["attempt"] == 1
    assert failure["reason"] == result.detail
    assert failure["outcome"] == result.outcome
    assert failure["raw_bytes"] == len(response.encode("utf-8"))
    assert failure["response_digest"] == _digest(response.encode("utf-8"))
    assert failure["response_capture"] == "stored"
    assert (tmp_path / failure["failure_path"]).read_text(encoding="utf-8") == response
    assert terminal["failure_detail"] == result.detail
    assert terminal["failure_response_digest"] == failure["response_digest"]
    assert "candidate response secret" not in log_path.read_text(encoding="utf-8")


def test_candidate_rejection_records_the_closed_delta_parse_reason(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    response = '{"delta":{"operations":[{"op":"remove"}]}}'

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, response),
    )

    log_path = next((tmp_path / ".plan-tool" / "runs" / _SLUG).glob("*.jsonl"))
    events = read_run_events(log_path)
    failure = next(event for event in events if event["event"] == "parse_failure")
    terminal = next(event for event in events if event["event"] == "phase_end")
    expected = "candidate response delta is invalid: candidate operation 'remove' is not allowed"

    assert result.outcome == "response-rejected"
    assert result.detail == expected
    assert failure["reason"] == expected
    assert terminal["failure_detail"] == expected


def test_candidate_rejection_marks_a_missing_response_receipt_without_masking_the_result(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)

    original_write = roadmap_candidate_run.durable_write_bytes

    def fail_receipt_write(path, data: bytes) -> None:
        if "parse-failures" in path.parts:
            raise OSError("receipt disk unavailable")
        original_write(path, data)

    monkeypatch.setattr(
        roadmap_candidate_run,
        "durable_write_bytes",
        fail_receipt_write,
    )
    response = '{"delta":{"operations":[]}} candidate response secret'

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, response),
    )

    log_path = next((tmp_path / ".plan-tool" / "runs" / _SLUG).glob("*.jsonl"))
    events = read_run_events(log_path)
    failure = next(event for event in events if event["event"] == "parse_failure")
    terminal = next(event for event in events if event["event"] == "phase_end")

    assert result.outcome == "response-rejected"
    assert failure["failure_path"] == ""
    assert failure["response_capture"] == "unavailable"
    assert failure["response_digest"] == _digest(response.encode("utf-8"))
    assert terminal["failure_path"] is None
    assert terminal["response_capture"] == "unavailable"


def test_a_second_interrupt_during_receipt_capture_does_not_swallow_the_terminal_record(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)

    original_write = roadmap_candidate_run.durable_write_bytes

    def interrupt_receipt_write(path, data: bytes) -> None:
        if "parse-failures" in path.parts:
            raise KeyboardInterrupt
        original_write(path, data)

    monkeypatch.setattr(roadmap_candidate_run, "durable_write_bytes", interrupt_receipt_write)
    response = '{"delta":{"operations":[]}} candidate response secret'

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, response),
    )

    log_path = next((tmp_path / ".plan-tool" / "runs" / _SLUG).glob("*.jsonl"))
    events = read_run_events(log_path)
    failure = next(event for event in events if event["event"] == "parse_failure")
    terminal = next(event for event in events if event["event"] == "phase_end")

    assert result.outcome == "response-rejected"
    assert failure["response_capture"] == "unavailable"
    assert terminal["response_capture"] == "unavailable"
    assert [event["outcome"] for event in events if event["event"] == "run_end"] == ["response-rejected"]


def test_a_second_interrupt_during_parse_failure_phase_end_or_run_end_does_not_propagate(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each of the three terminal-record writes record_candidate_failure_diagnostics
    and the caller's finally block make is individually guarded — mirroring
    backend_runner.py's `_finalize_interrupted_call` precedent — so a second
    KeyboardInterrupt landing during any one of them still lets the command
    return its already-decided result instead of raising out of the finally
    block and losing whichever of the three writes come after it."""
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    monkeypatch.setattr(
        run_log_module,
        "_append_jsonl_line",
        _raise_interrupt_for_run_log_events("parse_failure", "phase_end", "run_end"),
    )
    response = '{"delta":{"operations":[]}} candidate response secret'

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, response),
    )

    assert result.outcome == "response-rejected"


def test_a_second_interrupt_during_run_interrupted_still_records_the_interrupted_outcome(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A first KeyboardInterrupt during the backend call is caught and reported
    via logger.run_interrupted(...); if a second KeyboardInterrupt lands during
    that report's own write, `result` must still end up "interrupted" (not the
    finally block's "did not finish" -> "failed" fallback), and the second
    interrupt must not escape the function."""
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    monkeypatch.setattr(
        run_log_module, "_append_jsonl_line", _raise_interrupt_for_run_log_events("run_interrupted")
    )

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=_interrupting_invoker,
    )

    log_path = next((tmp_path / ".plan-tool" / "runs" / _SLUG).glob("*.jsonl"))
    events = read_run_events(log_path)

    assert result.outcome == "interrupted"
    assert [event["outcome"] for event in events if event["event"] == "run_end"] == ["interrupted"]


def test_a_second_interrupt_during_failure_diagnostics_setup_still_reaches_phase_end_and_run_end(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """record_candidate_failure_diagnostics's own call in the finally block was
    unguarded even after its *internal* calls were guarded — a second
    KeyboardInterrupt landing in its setup (encode/digest/path-building, before
    either of its own try/except-KeyboardInterrupt-guarded calls) must not
    stop the finally block's phase_end/run_end from still being attempted."""
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    response = '{"delta":{"operations":[]}} candidate response secret'
    original_digest = roadmap_candidate_run._digest

    def interrupt_digest(value: bytes) -> str:
        if value == response.encode("utf-8"):
            raise KeyboardInterrupt
        return original_digest(value)

    monkeypatch.setattr(roadmap_candidate_run, "_digest", interrupt_digest)

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, response),
    )

    log_path = next((tmp_path / ".plan-tool" / "runs" / _SLUG).glob("*.jsonl"))
    events = read_run_events(log_path)

    assert result.outcome == "response-rejected"
    assert [event["outcome"] for event in events if event["event"] == "run_end"] == ["response-rejected"]
    assert not any(event["event"] == "parse_failure" for event in events)
    terminal = next(event for event in events if event["event"] == "phase_end")
    assert terminal["failure_detail"] == result.detail
    assert terminal["failure_attempt"] == 1
    assert terminal["failure_call_count"] == result.call_count
    assert terminal["response_capture"] == "unavailable"


def test_storage_failure_after_a_valid_response_is_not_recorded_as_a_parse_failure(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)

    def fail_store(**_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(roadmap_candidate_run, "_store_candidate", fail_store)

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _delta_response()),
    )

    log_path = next((tmp_path / ".plan-tool" / "runs" / _SLUG).glob("*.jsonl"))
    events = read_run_events(log_path)
    terminal = next(event for event in events if event["event"] == "phase_end")

    assert result.outcome == "failed"
    assert not any(event["event"] == "parse_failure" for event in events)
    assert terminal["response_capture"] == "not-applicable"
    assert not (tmp_path / ".plan-tool" / "parse-failures").exists()


def test_expansion_persist_failure_after_a_valid_response_is_not_recorded_as_a_parse_failure(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    predecessor = load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG)
    assert predecessor is not None
    capsule = build_candidate_context(predecessor, _SELECTOR).capsule
    assert capsule is not None
    entry = next(item for item in capsule.inventory if item.row_id == "entity-compact")
    expansion_response = json.dumps({"expand": entry.model_dump()})

    admission_path = roadmap_candidate_run.candidate_admission_path(tmp_path / "plans", _SLUG)
    original_write = roadmap_candidate_run.durable_write_bytes

    def fail_admission_replace(path, data: bytes) -> None:
        if path == admission_path and path.exists():
            raise OSError("admission disk unavailable")
        original_write(path, data)

    monkeypatch.setattr(roadmap_candidate_run, "durable_write_bytes", fail_admission_replace)

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, expansion_response),
    )

    log_path = next((tmp_path / ".plan-tool" / "runs" / _SLUG).glob("*.jsonl"))
    events = read_run_events(log_path)
    terminal = next(event for event in events if event["event"] == "phase_end")

    assert result.outcome == "failed"
    assert result.call_count == 1
    assert not any(event["event"] == "parse_failure" for event in events)
    assert terminal["response_capture"] == "not-applicable"


def test_materialization_rejection_never_exposes_candidate_storage(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    unauthorized = json.dumps(
        {
            "delta": {
                "operations": [
                    {
                        "op": "replace-row",
                        "feedback_id": "feedback-order",
                        "artifact_key": "domain",
                        "row_type": "entities",
                        "row_id": "entity-compact",
                        "row": {"id": "entity-compact", "name": "Changed", "fields": []},
                    }
                ]
            }
        }
    )

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, unauthorized),
    )

    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=tmp_path / "plans", slug=_SLUG)
    assert result.outcome == "response-rejected"
    assert admission is not None
    assert admission.candidate_version_id is None


def test_candidate_storage_refuses_missing_or_substituted_stored_members(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _delta_response()),
    )
    assert result.candidate is not None
    path = roadmap_candidate_run.candidate_evidence_path(
        tmp_path / "plans", _SLUG, result.candidate.version_id
    )
    path.unlink()

    with pytest.raises(roadmap_candidate_run.CandidateProposalError, match="evidence"):
        roadmap_candidate_run.load_stored_candidate_proposal(
            plans_dir=tmp_path / "plans", slug=_SLUG, candidate_version_id=result.candidate.version_id
        )


def test_candidate_storage_refuses_evidence_that_cannot_be_reproduced(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _delta_response()),
    )
    assert result.candidate is not None
    evidence_path = roadmap_candidate_run.candidate_evidence_path(
        tmp_path / "plans", _SLUG, result.candidate.version_id
    )
    substituted = result.candidate.evidence.model_copy(
        update={
            "predecessor_diff": roadmap_candidate.CandidatePredecessorDiff(
                changed_artifacts=(),
                changed_rows=(),
                added_relations=(),
                removed_relations=(),
            )
        }
    )
    evidence_path.write_bytes(roadmap_candidate_run.render_candidate_evidence(substituted))

    with pytest.raises(roadmap_candidate_run.CandidateProposalError, match="cannot be reproduced"):
        roadmap_candidate_run.load_stored_candidate_proposal(
            plans_dir=tmp_path / "plans", slug=_SLUG, candidate_version_id=result.candidate.version_id
        )


def test_review_required_candidate_evidence_substitution_is_refused_on_load(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _review_required_delta_response()),
    )

    assert result.candidate is not None
    requirement = result.candidate.evidence.review_requirement
    assert requirement is not None
    substituted = requirement.model_copy(
        update={
            "normalized_operations": parse_candidate_delta(
                json.dumps(json.loads(_delta_response())["delta"])
            ).operations,
        }
    )
    substituted = substituted.model_copy(
        update={
            "initial_disclosed_impact_identity": roadmap_candidate._review_impact_identity(
                reason=substituted.reason,
                predecessor_version_id=substituted.predecessor_version_id,
                selected_feedback=substituted.selected_feedback,
                receipt=substituted.capsule_receipt,
                normalized_operations=substituted.normalized_operations,
                predecessor_diff=substituted.predecessor_diff,
                affected_predecessor_members=substituted.affected_predecessor_members,
                impact_atoms=substituted.impact_atoms,
            )
        }
    )
    evidence_path = roadmap_candidate_run.candidate_evidence_path(
        tmp_path / "plans", _SLUG, result.candidate.version_id
    )
    evidence_path.write_bytes(
        roadmap_candidate_run.render_candidate_evidence(
            result.candidate.evidence.model_copy(update={"review_requirement": substituted})
        )
    )

    with pytest.raises(roadmap_candidate_run.CandidateProposalError, match="review requirement"):
        roadmap_candidate_run.load_stored_candidate_proposal(
            plans_dir=tmp_path / "plans", slug=_SLUG, candidate_version_id=result.candidate.version_id
        )


def test_review_required_candidate_evidence_missing_requirement_is_refused_on_load(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _review_required_delta_response()),
    )

    assert result.candidate is not None
    evidence_path = roadmap_candidate_run.candidate_evidence_path(
        tmp_path / "plans", _SLUG, result.candidate.version_id
    )
    evidence_path.write_bytes(
        roadmap_candidate_run.render_candidate_evidence(
            result.candidate.evidence.model_copy(update={"review_requirement": None})
        )
    )

    with pytest.raises(roadmap_candidate_run.CandidateProposalError, match="review requirement"):
        roadmap_candidate_run.load_stored_candidate_proposal(
            plans_dir=tmp_path / "plans", slug=_SLUG, candidate_version_id=result.candidate.version_id
        )


def test_candidate_evidence_refusal_happens_before_candidate_publication(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    published = False

    def reject_candidate(*_args: object, **_kwargs: object) -> None:
        raise roadmap_candidate_run.CandidateProposalError("candidate evidence is not reproducible")

    def record_publication(*_args: object, **_kwargs: object) -> None:
        nonlocal published
        published = True

    monkeypatch.setattr(roadmap_candidate_run, "_validate_candidate_evidence", reject_candidate)
    monkeypatch.setattr(roadmap_candidate_run, "publish_roadmap_generation", record_publication)

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _delta_response()),
    )
    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=tmp_path / "plans", slug=_SLUG)

    assert result.outcome == "failed"
    assert published is False
    assert admission is not None
    assert admission.candidate_version_id is None


def test_review_required_storage_publishes_evidence_and_admission_in_one_generation(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    original_publish = roadmap_candidate_run.publish_roadmap_generation
    generations = []

    def capture_generation(generation, **kwargs) -> None:
        generations.append(generation)
        original_publish(generation, **kwargs)

    monkeypatch.setattr(roadmap_candidate_run, "publish_roadmap_generation", capture_generation)
    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _review_required_delta_response()),
    )

    assert result.candidate is not None
    assert len(generations) == 1
    members = generations[0].members
    evidence_member = next(member for member in members if member.relative_path.endswith("candidate-evidence.json"))
    admission_member = next(
        member for member in members if member.relative_path.endswith("candidate-admission.json")
    )
    assert evidence_member.old_bytes is None
    assert admission_member.old_bytes is not None
    assert roadmap_candidate_run.parse_candidate_admission(admission_member.old_bytes).candidate_version_id is None
    assert (
        roadmap_candidate_run.parse_candidate_admission(admission_member.new_bytes).candidate_version_id
        == result.candidate.version_id
    )


def test_terminal_resolution_rejects_an_unclosed_reason() -> None:
    root = "a" * 64
    receipt = roadmap_candidate_run.CandidateContextBatchReceipt.model_construct(
        root=CandidateContextPredecessor.model_construct(version_id=root),
        source=CandidateContextPredecessor.model_construct(version_id=root),
    )

    with pytest.raises(ValueError):
        roadmap_candidate_run.CandidateTerminalResolution(
            schema_version=1,
            root_version_id=root,
            source_version_id=root,
            candidate_version_id="b" * 64,
            batch_receipt=receipt,
            reason="open",  # type: ignore[arg-type]
        )


def _resolution_for_the_first_batch_candidate(tmp_path, monkeypatch):
    _root, first = _store_first_batch_candidate(tmp_path, monkeypatch)
    return first, roadmap_candidate_run.new_terminal_resolution(first, reason="rejected")


@pytest.mark.parametrize(
    ("field", "value", "detail"),
    (
        ("root_version_id", "not-a-digest", "must be a SHA-256 digest"),
        ("source_version_id", "x", "must be a SHA-256 digest"),
        ("candidate_version_id", "short", "must be a SHA-256 digest"),
        ("root_version_id", "9" * 64, "does not bind its batch receipt"),
        ("source_version_id", "9" * 64, "does not bind its batch receipt"),
    ),
    ids=("root-not-a-digest", "source-not-a-digest", "candidate-not-a-digest",
         "root-disagrees-with-receipt", "source-disagrees-with-receipt"),
)
def test_terminal_resolution_requires_digest_ids_that_agree_with_its_batch_receipt(
    tmp_path, monkeypatch, field: str, value: str, detail: str
) -> None:
    _first, resolution = _resolution_for_the_first_batch_candidate(tmp_path, monkeypatch)

    with pytest.raises(ValueError, match=detail):
        roadmap_candidate_run.CandidateTerminalResolution(**{**resolution.model_dump(), field: value})


@pytest.mark.parametrize(
    "change",
    ({"candidate_version_id": "9" * 64}, {"root_version_id": "9" * 64}),
    ids=("another-candidate", "another-root"),
)
def test_terminal_release_refuses_a_resolution_that_does_not_name_the_candidate_and_root_it_releases(
    tmp_path, monkeypatch, change: dict[str, str]
) -> None:
    """A release clears the pointer and writes history in one generation; the history must be
    about the candidate whose pointer is being cleared."""
    _first, resolution = _resolution_for_the_first_batch_candidate(tmp_path, monkeypatch)
    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=tmp_path / "plans", slug=_SLUG)
    assert admission is not None

    with pytest.raises(
        roadmap_candidate_run.CandidateProposalError, match="does not name the candidate being released"
    ):
        roadmap_candidate_run.build_terminal_resolution_generation(
            plans_dir=tmp_path / "plans", slug=_SLUG, admission=admission,
            resolution=resolution.model_copy(update=change),
        )


def test_bare_pointer_release_generation_clears_only_the_active_pointer(tmp_path) -> None:
    root = "a" * 64
    active = "b" * 64
    admission = roadmap_candidate_run.CandidateProposalAdmission(
        schema_version=1,
        roadmap_slug=_SLUG,
        predecessor_version_id=root,
        expansion_available=False,
        root_version_id=root,
        candidate_version_id=active,
        active_candidate_version_id=active,
    )
    generation = roadmap_candidate_run.build_active_candidate_pointer_release_generation(
        plans_dir=tmp_path / "plans", slug=_SLUG, admission=admission
    )

    released = roadmap_candidate_run.parse_candidate_admission(generation.members[0].new_bytes)

    assert generation.kind == "candidate-pointer-release"
    assert released.root_version_id == root
    assert released.active_candidate_version_id is None
    assert released.candidate_version_id is None


def test_review_required_candidate_evidence_collision_does_not_overwrite_existing_bytes(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    predecessor = load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG)
    assert predecessor is not None
    capsule = build_candidate_context(predecessor, _SELECTOR).capsule
    assert capsule is not None
    materialized = materialize_candidate(
        parse_candidate_delta(json.dumps(json.loads(_review_required_delta_response())["delta"])),
        predecessor=predecessor,
        capsule=capsule,
        receipt=capsule.receipt,
    )
    assert materialized.review_required is not None
    content = RoadmapVersionContent(
        brief_bytes=root.content.brief_bytes,
        artifact_bytes=tuple(member.data for member in materialized.review_required.artifacts),
    )
    record = roadmap_candidate_run.create_candidate_version(
        roadmap_slug=_SLUG,
        predecessor_version_id=root.record.version_id,
        content_identity=materialized.review_required.content_identity,
        review_lineage_identity=roadmap_candidate_run.INITIAL_EMPTY_REVIEW_LINEAGE_ID,
        brief_digest=_digest(content.brief_bytes),
        artifact_digests=tuple(_digest(item) for item in content.artifact_bytes),
    )
    evidence_path = roadmap_candidate_run.candidate_evidence_path(
        tmp_path / "plans", _SLUG, record.version_id
    )
    evidence_path.parent.mkdir(parents=True)
    evidence_path.write_bytes(b"keep-this-existing-evidence")

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _review_required_delta_response()),
    )
    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=tmp_path / "plans", slug=_SLUG)

    assert result.outcome == "failed"
    assert evidence_path.read_bytes() == b"keep-this-existing-evidence"
    assert admission is not None
    assert admission.candidate_version_id is None


def test_candidate_identity_collision_does_not_overwrite_existing_storage(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    predecessor = load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG)
    assert predecessor is not None
    capsule = build_candidate_context(predecessor, _SELECTOR).capsule
    assert capsule is not None
    delta = parse_candidate_delta(json.dumps(json.loads(_delta_response())["delta"]))
    materialized = materialize_candidate(
        delta,
        predecessor=predecessor,
        capsule=capsule,
        receipt=capsule.receipt,
    )
    assert materialized.candidate is not None
    content = RoadmapVersionContent(
        brief_bytes=root.content.brief_bytes,
        artifact_bytes=tuple(member.data for member in materialized.candidate.artifacts),
    )
    record = roadmap_candidate_run.create_candidate_version(
        roadmap_slug=_SLUG,
        predecessor_version_id=root.record.version_id,
        content_identity=materialized.candidate.content_identity,
        review_lineage_identity=roadmap_candidate_run.INITIAL_EMPTY_REVIEW_LINEAGE_ID,
        brief_digest=_digest(content.brief_bytes),
        artifact_digests=tuple(_digest(item) for item in content.artifact_bytes),
    )
    collision_path = version_directory_path(
        tmp_path / "plans", _SLUG, record.version_id
    ) / "version.json"
    collision_path.parent.mkdir(parents=True)
    collision_path.write_bytes(b"keep-this-existing-candidate")

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _delta_response()),
    )

    assert result.outcome == "failed"
    assert collision_path.read_bytes() == b"keep-this-existing-candidate"
    assert load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG).record == root.record


def test_production_candidate_invoker_uses_one_transport_attempt_without_rate_limit_waiting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: dict[str, object] = {}
    monkeypatch.setattr(
        roadmap_candidate_run.shell,
        "claude_invoke",
        lambda prompt, **kwargs: called.update(prompt=prompt, **kwargs) or (0, "{}"),
    )

    assert roadmap_candidate_run.shell_candidate_proposal_invoker("bounded") == (0, "{}")
    assert called == {
        "prompt": "bounded",
        "phase": roadmap_candidate_run.CANDIDATE_PROPOSAL_PHASE,
        "attempt": 1,
        "wait_on_rate_limit": False,
        "max_transient_retries": 1,
    }


def test_candidate_runner_logs_bounded_calls_and_terminal_outcome_without_model_content(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    secret_response = _delta_response().replace("Customer order", "Model response secret")
    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, secret_response),
    )

    log_path = next((tmp_path / ".plan-tool" / "runs" / _SLUG).glob("*.jsonl"))
    events = read_run_events(log_path)
    raw = log_path.read_text()
    assert result.outcome == "stored"
    assert len([event for event in events if event["event"] == "claude_call_start"]) == 1
    assert [
        (event["call_count"], event["expansion_used"])
        for event in events
        if event["event"] == "phase_end"
    ] == [(1, False)]
    assert [event["outcome"] for event in events if event["event"] == "run_end"] == ["stored"]
    assert "Model response secret" not in raw
    assert "Use the customer-facing order name." not in raw


def test_candidate_delta_prompt_renders_only_supplied_variables_and_uses_null_review_pair(tmp_path) -> None:
    root = _enroll(tmp_path)
    predecessor = load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG)
    assert predecessor is not None
    capsule = build_candidate_context(predecessor, _SELECTOR).capsule
    assert capsule is not None

    prompt = roadmap_candidate_run.render_candidate_delta_prompt(
        capsule=capsule, receipt=capsule.receipt, review_pair=None
    )

    assert root.record.version_id == predecessor.record.version_id
    assert "${" not in prompt
    assert "null" in prompt
    assert "Do not inspect repository files" in prompt
    assert "discovery-only" in prompt
    assert "standalone relation or ordering-entry operations" in prompt
    assert "feedback-order" in prompt
    assert "`add-row`, `replace-row`, and\n`remove-row`" in prompt
    assert "Never use `add`, `replace`, or `remove`." in prompt
    assert "artifact collection name, never a Python class name" in prompt
    assert "Do not emit `row_digest`" in prompt


def _prompt_following_invoker(*, selector_reply: str, batch_reply: dict):
    """A stand-in model that answers with the response shape its prompt asks for, so a
    template asking for the wrong shape fails the way a real model would fail."""

    def invoke(prompt: str) -> tuple[int, str]:
        if '{"delta"' in prompt:
            return 0, selector_reply
        if '"responses"' in prompt:
            return 0, json.dumps(batch_reply)
        pytest.fail("the prompt asks for no response shape this test can answer")

    return invoke


def test_selector_era_prompt_requests_the_delta_or_expand_shape_its_parser_accepts(tmp_path) -> None:
    """One template cannot serve two response contracts: the selector-era parser accepts
    exactly one `delta` or `expand` disposition, so its prompt must ask for that."""
    _enroll(tmp_path)
    predecessor = load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG)
    assert predecessor is not None
    capsule = build_candidate_context(predecessor, _SELECTOR).capsule
    assert isinstance(capsule, roadmap_candidate_run.CandidateContextCapsule)
    assert not isinstance(capsule, roadmap_candidate_run.CandidateContextBatchCapsule)

    prompt = roadmap_candidate_run.render_candidate_delta_prompt(
        capsule=capsule, receipt=capsule.receipt
    )

    assert '{"delta"' in prompt and '{"expand"' in prompt
    assert "feedback-order" in prompt
    assert '"responses"' not in prompt and '"derived_feedback"' not in prompt
    roadmap_candidate_run.parse_candidate_proposal_response(
        _delta_response(), capsule=capsule, allow_expansion=True
    )
    with pytest.raises(roadmap_candidate_run.CandidateProposalResponseError):
        roadmap_candidate_run.parse_candidate_proposal_response(
            json.dumps({"operations": [], "responses": [], "derived_feedback": []}),
            capsule=capsule, allow_expansion=True,
        )


def test_batch_prompt_requests_the_unwrapped_batch_shape_and_offers_no_expansion() -> None:
    from tests.test_roadmap_candidate_context import _ledger, _resolved

    root = _resolved()
    capsule = build_candidate_context(root, None, _ledger(root, item_ids=("review",))).capsule
    assert isinstance(capsule, roadmap_candidate_run.CandidateContextBatchCapsule)

    prompt = roadmap_candidate_run.render_candidate_delta_prompt(
        capsule=capsule, receipt=capsule.receipt, source=root
    )

    assert '"responses"' in prompt and '"derived_feedback"' in prompt
    assert '{"delta"' not in prompt and '{"expand"' not in prompt
    assert '"EntityRow":["entities"]' in prompt
    assert '"PatternRow":["system_patterns","component_patterns"]' in prompt
    for row_type in roadmap_candidate.NON_ADDABLE_ROW_TYPES:
        assert f"`{row_type}`" in prompt
    assert "cannot declare the required reached anchor" in prompt


def test_selector_prompt_also_warns_about_non_addable_collections() -> None:
    # The legacy selector flow shares _operation_diagnostics/_parse_operation
    # with the batch flow and rejects the same add-row types, so it must carry
    # the same upfront warning; only the batch template used to.
    from tests.test_roadmap_candidate_context import _capsule, _resolved

    root = _resolved()
    capsule = _capsule(root)
    assert not isinstance(capsule, roadmap_candidate_run.CandidateContextBatchCapsule)

    prompt = roadmap_candidate_run.render_candidate_delta_prompt(capsule=capsule, receipt=capsule.receipt)

    for row_type in roadmap_candidate.NON_ADDABLE_ROW_TYPES:
        assert f"`{row_type}`" in prompt
    assert "cannot declare the required reached anchor" in prompt


def test_stack_row_class_maps_to_its_collection_and_the_non_addable_notice_omits_it() -> None:
    """Deliberate: stack is relationless like hosting yet addable, so the notice
    that warns about unaddable collections must not list it."""
    assert roadmap_candidate_run._DELTA_ROW_TYPES["StackRow"] == "stack"
    notice = roadmap_candidate_run._NON_ADDABLE_COLLECTIONS_NOTICE
    assert "`hosting`" in notice
    assert "`stack`" not in notice


def test_batch_and_selector_prompts_share_the_non_addable_collections_notice() -> None:
    # Both templates reject the same add-row types via the same shared parser
    # logic; the warning prose is one source file, not two copies that could
    # drift apart.
    from tests.test_roadmap_candidate_context import _ledger, _resolved

    root = _resolved()
    batch_capsule = build_candidate_context(root, None, _ledger(root, item_ids=("review",))).capsule
    batch_prompt = roadmap_candidate_run.render_candidate_delta_prompt(
        capsule=batch_capsule, receipt=batch_capsule.receipt, source=root
    )
    selector_capsule = build_candidate_context(root, _SELECTOR).capsule
    selector_prompt = roadmap_candidate_run.render_candidate_delta_prompt(
        capsule=selector_capsule, receipt=selector_capsule.receipt
    )

    def _notice(prompt: str) -> str:
        start = prompt.index("`add-row` is prohibited for")
        end = prompt.index("Do not invent an anchor.") + len("Do not invent an anchor.")
        return prompt[start:end]

    assert _notice(batch_prompt) == _notice(selector_prompt)


def test_selector_prompt_lists_stack_under_constraints_with_no_unresolved_placeholder() -> None:
    """The selector prompt restates the collection list inline, so a collection
    the parser accepts but the prompt omits is never offered to the model."""
    from tests.test_roadmap_candidate_context import _resolved

    root = _resolved()
    capsule = build_candidate_context(root, _SELECTOR).capsule
    prompt = roadmap_candidate_run.render_candidate_delta_prompt(
        capsule=capsule, receipt=capsule.receipt
    )

    constraints_line = next(
        line for line in prompt.splitlines() if line.startswith("- `constraints`:")
    )
    assert "`stack`" in constraints_line
    assert "${" not in prompt


def test_both_candidate_prompts_tell_the_model_a_stack_add_omits_its_prose_amendment() -> None:
    """The contract refuses a supplied ``prose_amendment`` on a prose-less row
    type, so each prompt that offers ``stack`` additions must say to omit it."""
    from tests.test_roadmap_candidate_context import _ledger, _resolved

    root = _resolved()
    selector = build_candidate_context(root, _SELECTOR).capsule
    batch = build_candidate_context(root, None, _ledger(root, item_ids=("review",))).capsule
    selector_prompt = roadmap_candidate_run.render_candidate_delta_prompt(
        capsule=selector, receipt=selector.receipt
    )
    batch_prompt = roadmap_candidate_run.render_candidate_delta_prompt(
        capsule=batch, receipt=batch.receipt, source=root
    )

    for prompt in (selector_prompt, batch_prompt):
        flattened = " ".join(prompt.split())
        assert "`add-row` to `stack`" in flattened
        assert "omits `prose_amendment`" in flattened
        # The first stack add has no issued row to copy, so the prompt carries the shape
        # and every concern name the gate requires (derived, so a new concern fails here).
        for concern in STACK_CONCERNS:
            assert f"`{concern}`" in flattened, concern
        assert "one row for each of the three concerns" in flattened


def test_missing_candidate_prompt_file_is_a_domain_error_not_a_bare_file_not_found(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.test_roadmap_candidate_context import _resolved

    monkeypatch.setattr(roadmap_candidate_run, "prompts_dir", lambda: tmp_path)
    root = _resolved()
    capsule = build_candidate_context(root, _SELECTOR).capsule
    with pytest.raises(roadmap_candidate_run.CandidateProposalError, match="no candidate prompt template"):
        roadmap_candidate_run.render_candidate_delta_prompt(capsule=capsule, receipt=capsule.receipt)


def test_correction_reason_on_a_non_batch_capsule_raises_its_own_specific_message() -> None:
    # Must raise outside template.substitute()'s try/except, or its own
    # ValueError catch would relabel this as "unresolved variables".
    from tests.test_roadmap_candidate_context import _resolved

    root = _resolved()
    capsule = build_candidate_context(root, _SELECTOR).capsule
    with pytest.raises(roadmap_candidate_run.CandidateProposalError, match="requires a ledger batch"):
        roadmap_candidate_run.render_candidate_delta_prompt(
            capsule=capsule, receipt=capsule.receipt, correction_reason="some correction"
        )


def test_batch_prompt_renders_parser_owned_operation_shapes() -> None:
    from tests.test_roadmap_candidate_context import _ledger, _resolved

    root = _resolved()
    capsule = build_candidate_context(root, None, _ledger(root, item_ids=("review",))).capsule
    assert isinstance(capsule, roadmap_candidate_run.CandidateContextBatchCapsule)

    prompt = roadmap_candidate_run.render_candidate_delta_prompt(
        capsule=capsule, receipt=capsule.receipt, source=root
    )

    examples = {
        example["op"]: example
        for body in re.findall(r"```json\n(.*?)\n```", prompt, flags=re.DOTALL)
        if '"op"' in body
        if isinstance((example := json.loads(body)), dict) and "op" in example
    }
    assert {operation: set(example) for operation, example in examples.items()} == {
        "add-row": roadmap_candidate.ADD_ROW_REQUIRED_KEYS | roadmap_candidate.ADD_ROW_OPTIONAL_KEYS,
        "replace-row": roadmap_candidate.REPLACE_ROW_REQUIRED_KEYS | roadmap_candidate.REPLACE_ROW_OPTIONAL_KEYS,
        "remove-row": roadmap_candidate.REMOVE_ROW_REQUIRED_KEYS | roadmap_candidate.REMOVE_ROW_OPTIONAL_KEYS,
        # Unlike the three above, this example is static template text, pinned here against the parser keys.
        "correct-prose": roadmap_candidate.CORRECT_PROSE_REQUIRED_KEYS | roadmap_candidate.CORRECT_PROSE_OPTIONAL_KEYS,
    }


def _batch_prompt_for_correct_prose() -> str:
    from tests.test_roadmap_candidate_context import _ledger, _resolved

    root = _resolved()
    capsule = build_candidate_context(root, None, _ledger(root, item_ids=("review",))).capsule
    return roadmap_candidate_run.render_candidate_delta_prompt(
        capsule=capsule, receipt=capsule.receipt, source=root
    )


def _correct_prose_example(prompt: str) -> dict:
    return next(
        json.loads(body)
        for body in re.findall(r"```json\n(.*?)\n```", prompt, flags=re.DOTALL)
        if '"op":"correct-prose"' in body
    )


def test_batch_prompt_names_every_key_the_correct_prose_parser_requires() -> None:
    prompt = _batch_prompt_for_correct_prose()
    example_text = json.dumps(_correct_prose_example(prompt))
    keys = roadmap_candidate.CORRECT_PROSE_REQUIRED_KEYS | roadmap_candidate.CORRECT_PROSE_OPTIONAL_KEYS
    for key in keys:
        assert f'"{key}"' in example_text
    assert "`correct-prose`" in prompt


def test_batch_prompt_correct_prose_example_has_exactly_the_parser_key_set() -> None:
    example = _correct_prose_example(_batch_prompt_for_correct_prose())
    assert set(example) == (
        roadmap_candidate.CORRECT_PROSE_REQUIRED_KEYS | roadmap_candidate.CORRECT_PROSE_OPTIONAL_KEYS
    )


def test_batch_prompt_correct_prose_example_parses_through_the_real_parser() -> None:
    example = _correct_prose_example(_batch_prompt_for_correct_prose())
    example.update(feedback_id="review", artifact_key="01-domain.md", span_id="span-1")
    delta = parse_candidate_delta(json.dumps({"operations": [example]}))
    assert [operation.op for operation in delta.operations] == ["correct-prose"]


def test_selector_era_prompt_deliberately_does_not_offer_correct_prose() -> None:
    """The selector route issues no shared spans, so offering the operation would only invite a refusal."""
    from tests.test_roadmap_candidate_context import _resolved

    root = _resolved()
    capsule = build_candidate_context(root, _SELECTOR).capsule
    prompt = roadmap_candidate_run.render_candidate_delta_prompt(
        capsule=capsule, receipt=capsule.receipt
    )
    assert "correct-prose" not in prompt


def test_batch_prompt_states_correct_prose_is_an_operation_not_a_response_field() -> None:
    prompt = _batch_prompt_for_correct_prose()
    assert "never as a\nseparate response field" in prompt
    assert "Do not attach prose amendments to `replace-row` or `remove-row`" in prompt


def test_batch_prompt_add_row_example_includes_required_row_owned_prose() -> None:
    from tests.test_roadmap_candidate_context import _ledger, _resolved

    root = _resolved()
    capsule = build_candidate_context(root, None, _ledger(root, item_ids=("review",))).capsule
    prompt = roadmap_candidate_run.render_candidate_delta_prompt(
        capsule=capsule, receipt=capsule.receipt, source=root
    )
    add_row = next(
        json.loads(body)
        for body in re.findall(r"```json\n(.*?)\n```", prompt, flags=re.DOTALL)
        if '"op":"add-row"' in body
    )

    assert add_row["prose_amendment"] == {
        "row_id": "entity-new", "fragment": "Describe entity-new."
    }
    assert "Every eligible `add-row` must include its required `prose_amendment` object" in prompt
    assert "Do not attach prose amendments to `replace-row` or `remove-row`" in prompt


def test_selector_prompt_requires_row_owned_prose_only_in_delta_additions() -> None:
    from tests.test_roadmap_candidate_context import _resolved

    root = _resolved()
    capsule = build_candidate_context(root, _SELECTOR).capsule
    prompt = roadmap_candidate_run.render_candidate_delta_prompt(
        capsule=capsule, receipt=capsule.receipt
    )

    assert "Every eligible `add-row` in a `delta` must include its required" in prompt
    assert "An `expand` response never carries a prose amendment" in prompt
    assert "`{\"delta\":{\"operations\":[...]}}`" in prompt
    assert "`{\"expand\":{\"artifact_key\":\"...\"" in prompt


def test_batch_prompt_states_that_only_a_plans_row_carries_an_ordering_entry() -> None:
    # The examples show ordering null, and materialization refuses a null ordering on a plans row and any
    # ordering on another row type, so the prose beside the examples must state the plans exception.
    from tests.test_roadmap_candidate_context import _ledger, _resolved

    root = _resolved()
    capsule = build_candidate_context(root, None, _ledger(root, item_ids=("review",))).capsule
    prompt = roadmap_candidate_run.render_candidate_delta_prompt(
        capsule=capsule, receipt=capsule.receipt, source=root
    )

    assert "`ordering` is `null` for every row\ntype except `plans`" in prompt
    assert "A `plans` `add-row` or `remove-row` requires an `ordering` object" in prompt
    assert "a removal repeats the\nplan's existing ordering entry exactly" in prompt


def test_batch_prompt_add_row_example_omits_discovery_only_fields() -> None:
    from tests.test_roadmap_candidate_context import _ledger, _resolved

    root = _resolved()
    capsule = build_candidate_context(root, None, _ledger(root, item_ids=("review",))).capsule
    assert isinstance(capsule, roadmap_candidate_run.CandidateContextBatchCapsule)
    prompt = roadmap_candidate_run.render_candidate_delta_prompt(
        capsule=capsule, receipt=capsule.receipt, source=root
    )
    add_row = next(
        json.loads(body)
        for body in re.findall(r"```json\n(.*?)\n```", prompt, flags=re.DOTALL)
        if '"op":"add-row"' in body
    )

    assert add_row["row_type"] == "entities"
    assert "collection" not in add_row and "row_id" not in add_row


def test_batch_prompt_states_decision_source_is_not_writable() -> None:
    from tests.test_roadmap_candidate_context import _ledger, _resolved

    root = _resolved()
    capsule = build_candidate_context(root, None, _ledger(root, item_ids=("review",))).capsule
    assert isinstance(capsule, roadmap_candidate_run.CandidateContextBatchCapsule)
    prompt = roadmap_candidate_run.render_candidate_delta_prompt(
        capsule=capsule, receipt=capsule.receipt, source=root
    )

    assert "`source` is discovery-only\nand is not writable" in prompt


def test_batch_prompt_identifies_both_existing_pattern_collections() -> None:
    from tests.test_roadmap_candidate_context import _artifacts, _ledger, _resolved
    from plan_tool.roadmap_versions import ResolvedRoadmapVersion

    base = _resolved()
    artifacts = list(_artifacts())
    components = artifacts[2]
    assert isinstance(components, ComponentsArtifact)
    artifacts[2] = replace(
        components,
        component_patterns=(PatternRow("pattern-component", "Component pattern", "Keep local state."),),
    )
    artifact_bytes = tuple(stage.render(artifact).encode("utf-8") for stage, artifact in zip(STAGES, artifacts, strict=True))
    record = create_root_version(
        roadmap_slug="storefront", brief_digest=_digest(base.brief_bytes),
        artifact_digests=tuple(_digest(data) for data in artifact_bytes),
    )
    source = ResolvedRoadmapVersion(record, base.brief_bytes, artifact_bytes)
    capsule = build_candidate_context(source, None, _ledger(source, item_ids=("review",))).capsule
    assert isinstance(capsule, roadmap_candidate_run.CandidateContextBatchCapsule)

    prompt = roadmap_candidate_run.render_candidate_delta_prompt(
        capsule=capsule, receipt=capsule.receipt, source=source
    )

    hints = candidate_collection_hints(capsule, source)
    rows = {entry["issued_row"]["id"]: entry["source_collection"] for entry in hints["existing_rows"]}
    assert rows["pattern-order"] == "system_patterns"
    assert rows["pattern-component"] == "component_patterns"
    assert json.dumps(hints, ensure_ascii=False, sort_keys=True, separators=(",", ":")) in prompt
    assert capsule.payload.decode("utf-8") not in prompt.split("Issued batch payload:")[0]


def test_batch_prompt_renders_discovery_hints_separately_from_operation_shapes() -> None:
    from tests.test_roadmap_candidate_context import _ledger, _resolved

    root = _resolved()
    capsule = build_candidate_context(root, None, _ledger(root, item_ids=("review",))).capsule
    assert isinstance(capsule, roadmap_candidate_run.CandidateContextBatchCapsule)
    prompt = roadmap_candidate_run.render_candidate_delta_prompt(
        capsule=capsule, receipt=capsule.receipt, source=root
    )

    hint_data = candidate_collection_hints(capsule, root)
    hints = json.dumps(hint_data, sort_keys=True, separators=(",", ":"))
    operation_keys = set().union(
        roadmap_candidate.ADD_ROW_REQUIRED_KEYS,
        roadmap_candidate.ADD_ROW_OPTIONAL_KEYS,
        roadmap_candidate.REPLACE_ROW_REQUIRED_KEYS,
        roadmap_candidate.REPLACE_ROW_OPTIONAL_KEYS,
        roadmap_candidate.REMOVE_ROW_REQUIRED_KEYS,
        roadmap_candidate.REMOVE_ROW_OPTIONAL_KEYS,
        {"collection"},
    )

    assert hints in prompt
    assert "writable operations,\nnot `existing_rows` discovery records" in prompt
    assert all(set(record).isdisjoint(operation_keys) for record in hint_data["existing_rows"])


def test_batch_prompt_refuses_a_mismatched_immutable_source() -> None:
    from tests.test_roadmap_candidate_context import _ledger, _resolved

    source = _resolved()
    capsule = build_candidate_context(source, None, _ledger(source, item_ids=("review",))).capsule
    assert isinstance(capsule, roadmap_candidate_run.CandidateContextBatchCapsule)

    with pytest.raises(roadmap_candidate_run.CandidateProposalError, match="issued receipt"):
        roadmap_candidate_run.render_candidate_delta_prompt(
            capsule=capsule, receipt=capsule.receipt, source=_resolved(brief=b"another brief\n")
        )


def test_selector_era_proposal_stores_when_the_model_answers_the_shape_its_prompt_asks_for(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG, _SELECTOR, repo_root=tmp_path, plans_dir=tmp_path / "plans",
        invoker=_prompt_following_invoker(selector_reply=_delta_response(), batch_reply=_FIRST_BATCH_DELTA),
    )

    assert result.outcome == "stored", result.detail


def test_batch_proposal_stores_when_the_model_answers_the_shape_its_prompt_asks_for(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_batch_ledger(tmp_path, monkeypatch)

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG, "domain:ignored-by-the-ledger-batch-route", repo_root=tmp_path, plans_dir=tmp_path / "plans",
        invoker=_prompt_following_invoker(selector_reply=_delta_response(), batch_reply=_FIRST_BATCH_DELTA),
    )

    assert result.outcome == "stored", result.detail


# Models whose `row` annotation is `object` are not nullable in practice (a row
# operation always carries a real row); the walk below reports them only because
# `object` admits None, so they are named here as the deliberate exemptions.
_OBJECT_ROW_EXEMPTIONS = frozenset(
    {
        ("CandidateAddRow", "row"),
        ("CandidateReplaceRow", "row"),
        ("CandidateContextFullMember", "row"),
    }
)


def test_no_persisted_evidence_model_has_a_required_nullable_field() -> None:
    """Evidence and question inventories are rendered with exclude_none, which
    drops a None field's key on dump; a `X | None` field with no default then
    fails 'Field required' on reload, so the record refuses as invalid. Walk
    every model reachable from both persisted roots so the next such field
    fails here instead of at a real proposal."""
    import inspect
    import typing

    from pydantic import BaseModel

    from plan_tool import roadmap_candidate_review

    def nested(annotation):
        if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
            yield annotation
            return
        for arg in typing.get_args(annotation):
            yield from nested(arg)

    seen: set[type] = set()
    stack = [
        roadmap_candidate_run.CandidateProposalEvidence,
        roadmap_candidate_review.CandidateQuestionInventory,
    ]
    offenders = []
    while stack:
        model = stack.pop()
        if model in seen:
            continue
        seen.add(model)
        for name, field in model.model_fields.items():
            annotation = field.annotation
            nullable = (
                type(None) in typing.get_args(annotation)
                or annotation is object
                or annotation is typing.Any
            )
            if nullable and field.is_required() and (model.__name__, name) not in _OBJECT_ROW_EXEMPTIONS:
                offenders.append(f"{model.__name__}.{name}: {annotation}")
            stack.extend(nested(annotation))

    assert not offenders, offenders


def test_batch_response_parsing_accepts_the_unwrapped_delta_the_batch_prompt_requests() -> None:
    """The batch prompt (roadmap-candidate-delta.md) tells the model to emit the
    unwrapped {operations, responses, derived_feedback} object and offers no
    expansion. The initial proposal and the review replacement both parse through
    parse_candidate_proposal_response, so a batch capsule must not demand the
    legacy {"delta": ...} wrapper (it refused as 'requires exactly one
    disposition') and must not accept an expansion disposition."""
    from tests.test_roadmap_candidate_context import _ledger, _resolved

    root = _resolved()
    outcome = build_candidate_context(root, None, _ledger(root, item_ids=("review",)))
    capsule = outcome.capsule
    assert isinstance(capsule, roadmap_candidate_run.CandidateContextBatchCapsule)

    unwrapped = json.dumps(
        {"operations": [], "responses": [{"item_id": "review", "response": "ok"}], "derived_feedback": []}
    )
    parsed = roadmap_candidate_run.parse_candidate_proposal_response(
        unwrapped, capsule=capsule, allow_expansion=True
    )
    assert [entry.item_id for entry in parsed.responses] == ["review"]

    with pytest.raises(roadmap_candidate_run.CandidateProposalResponseError):
        roadmap_candidate_run.parse_candidate_proposal_response(
            json.dumps({"delta": {"operations": []}}), capsule=capsule, allow_expansion=True
        )


# --------------------------------------------------------------------------
# Ledger batch path: supersession history
# --------------------------------------------------------------------------


_FIRST_BATCH_DELTA = {
    "operations": [],
    "responses": [{"item_id": "batch-one", "response": "Rename the entity."}],
    "derived_feedback": [{"context_id": "derived-one", "content": "Check naming."}],
}


def _batch_item(resolved, item_id: str, row_id: str) -> ReviewerFeedbackItem:
    target = LedgerTarget(artifact_key="domain", kind=FeedbackTargetKind.ROW, row_id=row_id)
    return ReviewerFeedbackItem(
        item_id=item_id,
        target=target,
        request="Use the customer-facing order name.",
        state=ReviewerItemState.OPEN,
        submitted_against_version_id=resolved.record.version_id,
        target_fingerprint=target_fingerprint(resolved, target),
    )


def _write_open_item_ledger(tmp_path):
    """Give the accepted head a ledger with one open item and return the head."""
    plans_dir = tmp_path / "plans"
    resolved = load_accepted_version(plans_dir=plans_dir, slug=_SLUG)
    ledger = RoadmapFeedbackLedger(
        schema_version=1,
        roadmap_slug=_SLUG,
        ledger_state=LedgerState.LEDGER_NATIVE,
        reviewer_feedback_groups=(
            ReviewerFeedbackGroup(
                predecessor_version_id=resolved.record.version_id,
                items=(_batch_item(resolved, "batch-one", "entity-order"),),
            ),
        ),
        derived_context=(),
    )
    roadmap_feedback_ledger_path(plans_dir, _SLUG).write_bytes(render_ledger(ledger))
    return resolved


def _seed_batch_ledger(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """Enroll a root and give it a ledger with one open item, gates stubbed green."""
    root = _enroll(tmp_path)
    resolved = _write_open_item_ledger(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    return root, resolved


def _store_first_batch_candidate(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """Seed a ledger and store the first batch candidate."""
    root, _resolved = _seed_batch_ledger(tmp_path, monkeypatch)
    first = _run_batch(tmp_path, _FIRST_BATCH_DELTA)
    assert first.outcome == "stored"
    assert first.candidate is not None
    return root, first.candidate


def _run_batch(tmp_path, delta: dict):
    return roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        "domain:ignored-by-the-ledger-batch-route",
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, json.dumps(delta)),
    )


def _approve_structural_candidate(plans_dir, candidate):
    """Approve with the digest the stack view yields, for a test where approval is setup, not the subject."""
    view = roadmap_candidate_review.build_candidate_stack_view(
        plans_dir=plans_dir, slug=_SLUG, candidate=candidate
    )
    return roadmap_candidate_review.decide_structural_candidate(
        _SLUG, candidate.version_id, "approve", plans_dir=plans_dir, confirm_digest=view.digest
    )


_CHANGING_BATCH_DELTA = {
    "operations": [
        {
            "op": "replace-row", "feedback_id": "batch-one", "artifact_key": "domain",
            "row_type": "entities", "row_id": "entity-order",
            "row": {
                "id": "entity-order", "name": "Customer order",
                "fields": [{"name": "customer", "type": "reference", "entity_id": "entity-customer"}],
            },
        }
    ],
    "responses": [{"item_id": "batch-one", "response": "Done."}],
    "derived_feedback": [],
}


def _store_changing_batch_candidate(tmp_path, monkeypatch: pytest.MonkeyPatch):
    _seed_batch_ledger(tmp_path, monkeypatch)
    stored = _run_batch(tmp_path, _CHANGING_BATCH_DELTA)
    assert stored.outcome == "stored", stored.detail
    assert stored.candidate is not None
    return stored.candidate


def test_batch_candidate_evidence_persists_normalized_operations_and_presentation_route(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = _store_changing_batch_candidate(tmp_path, monkeypatch)

    reloaded = _reload_stored_candidate(tmp_path, candidate)

    assert reloaded.evidence.normalized_operations == parse_candidate_delta(
        json.dumps(_CHANGING_BATCH_DELTA)
    ).operations
    assert (
        reloaded.evidence.operation_classification
        is roadmap_candidate.CandidateOperationClassification.PRESENTATION_ONLY
    )


def test_batch_candidate_evidence_persists_normalized_operations_and_structural_route(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_batch_ledger(tmp_path, monkeypatch)
    structural = {
        **_CHANGING_BATCH_DELTA,
        "operations": [
            {
                **_CHANGING_BATCH_DELTA["operations"][0],
                "row": {
                    **_CHANGING_BATCH_DELTA["operations"][0]["row"],
                    "fields": [
                        {
                            "name": "buyer",
                            "type": "reference",
                            "entity_id": "entity-customer",
                        }
                    ],
                },
            }
        ],
    }

    stored = _run_batch(tmp_path, structural)

    assert stored.outcome == "stored", stored.detail
    assert stored.candidate is not None
    reloaded = _reload_stored_candidate(tmp_path, stored.candidate)
    source = load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG)
    source_artifacts = {
        stage.artifact_key: stage.parse(data.decode("utf-8"))
        for stage, data in zip(STAGES, source.artifact_bytes, strict=True)
    }
    candidate_artifacts = {
        stage.artifact_key: stage.parse(data.decode("utf-8"))
        for stage, data in zip(STAGES, reloaded.content.artifact_bytes, strict=True)
    }
    assert roadmap_candidate.extract_declared_relations(**candidate_artifacts) == (
        roadmap_candidate.extract_declared_relations(**source_artifacts)
    )
    assert reloaded.evidence.operation_classification is (
        roadmap_candidate.CandidateOperationClassification.STRUCTURAL
    )


def test_batch_candidate_same_batch_relation_reaches_inert_structural_candidate(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, resolved = _seed_batch_ledger(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    ledger = load_ledger(roadmap_feedback_ledger_path(plans_dir, _SLUG))
    group = ledger.reviewer_feedback_groups[0]
    second_item = _batch_item(resolved, "batch-two", "entity-order")
    roadmap_feedback_ledger_path(plans_dir, _SLUG).write_bytes(
        render_ledger(ledger.model_copy(update={
            "reviewer_feedback_groups": (group.model_copy(update={"items": (*group.items, second_item)}),)
        }))
    )
    accepted_head_before = accepted_head_path(plans_dir, _SLUG).read_bytes()
    delta = {
        "operations": [
            {
                "op": "add-row", "feedback_id": "batch-two", "artifact_key": "domain",
                "row_type": "entities", "row": {
                    "id": "entity-new", "name": "New customer",
                    "fields": [{"name": "order", "type": "reference", "entity_id": "entity-order"}],
                },
             "prose_amendment": {"row_id": "entity-new", "fragment": "Describe entity-new."},},
            {
                "op": "replace-row", "feedback_id": "batch-one", "artifact_key": "domain",
                "row_type": "entities", "row_id": "entity-order", "row": {
                    "id": "entity-order", "name": "Order",
                    "fields": [{"name": "customer", "type": "reference", "entity_id": "entity-new"}],
                },
            },
        ],
        "responses": [
            {"item_id": "batch-one", "response": "Connect the order."},
            {"item_id": "batch-two", "response": "Add the customer."},
        ],
        "derived_feedback": [],
    }

    result = _run_batch(tmp_path, delta)

    assert result.outcome == "stored", result.detail
    assert result.candidate is not None
    assert result.candidate.evidence.operation_classification is roadmap_candidate.CandidateOperationClassification.STRUCTURAL
    assert accepted_head_path(plans_dir, _SLUG).read_bytes() == accepted_head_before
    assert load_accepted_version(plans_dir=plans_dir, slug=_SLUG).record.version_id == root.record.version_id
    items = {
        item.item_id: item
        for item in load_ledger(roadmap_feedback_ledger_path(plans_dir, _SLUG)).reviewer_feedback_groups[0].items
    }
    assert all(items[item_id].state is ReviewerItemState.AWAITING_REVIEW for item_id in ("batch-one", "batch-two"))

    reloaded = _reload_stored_candidate(tmp_path, result.candidate)
    assert reloaded.content.artifact_bytes == result.candidate.content.artifact_bytes
    assert isinstance(reloaded.evidence.normalized_operations[0], roadmap_candidate.CandidateAddRow)
    assert reloaded.evidence.normalized_operations[0].prose_amendment.fragment == "Describe entity-new."
    assert all(items[item_id].proposal.candidate_version_id == result.candidate.version_id for item_id in ("batch-one", "batch-two"))


def test_comparison_binds_a_real_stored_candidates_prose_amendment_to_its_root(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End to end through the real loader: base = the candidate's direct predecessor."""
    from plan_tool.roadmap_compare_run import run_roadmap_comparison
    from plan_tool.roadmap_compare_render import comparison_json_payload

    root, resolved = _seed_batch_ledger(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    ledger = load_ledger(roadmap_feedback_ledger_path(plans_dir, _SLUG))
    group = ledger.reviewer_feedback_groups[0]
    roadmap_feedback_ledger_path(plans_dir, _SLUG).write_bytes(
        render_ledger(ledger.model_copy(update={"reviewer_feedback_groups": (group.model_copy(update={
            "items": (*group.items, _batch_item(resolved, "batch-two", "entity-order"))
        }),)}))
    )
    delta = {
        "operations": [
            {
                "op": "add-row", "feedback_id": "batch-two", "artifact_key": "domain",
                "row_type": "entities", "row": {
                    "id": "entity-new", "name": "New customer",
                    "fields": [{"name": "order", "type": "reference", "entity_id": "entity-order"}],
                },
                "prose_amendment": {"row_id": "entity-new", "fragment": "Describe entity-new."},
            },
            {
                "op": "replace-row", "feedback_id": "batch-one", "artifact_key": "domain",
                "row_type": "entities", "row_id": "entity-order", "row": {
                    "id": "entity-order", "name": "Order",
                    "fields": [{"name": "customer", "type": "reference", "entity_id": "entity-new"}],
                },
            },
        ],
        "responses": [
            {"item_id": "batch-one", "response": "Connect the order."},
            {"item_id": "batch-two", "response": "Add the customer."},
        ],
        "derived_feedback": [],
    }
    stored = _run_batch(tmp_path, delta)
    assert stored.outcome == "stored", stored.detail
    assert stored.candidate is not None

    run = run_roadmap_comparison(
        plans_dir=tmp_path / "plans", slug=_SLUG,
        base_version_id=root.record.version_id, target_version_id=stored.candidate.version_id,
    )

    assert comparison_json_payload(run)["row_linked_prose_amendments"] == {
        "outcome": "bound",
        "items": [{"artifact_key": "domain", "row_id": "entity-new", "fragment": "Describe entity-new."}],
    }


def _edit_stored_evidence(tmp_path, candidate, edit) -> None:
    """Rewrite a stored candidate's evidence with `edit` applied, staying canonical so only
    the edited fact can be what a reload refuses."""
    path = roadmap_candidate_run.candidate_evidence_path(tmp_path / "plans", _SLUG, candidate.version_id)
    data = json.loads(path.read_bytes())
    edit(data)
    path.write_bytes(
        roadmap_candidate_run.render_candidate_evidence(
            roadmap_candidate_run.CandidateProposalEvidence.model_validate_json(json.dumps(data))
        )
    )


def _reload_stored_candidate(tmp_path, candidate):
    return roadmap_candidate_run.load_stored_candidate_proposal(
        plans_dir=tmp_path / "plans", slug=_SLUG, candidate_version_id=candidate.version_id
    )


@pytest.mark.parametrize("missing", ("normalized_operations", "operation_classification"))
def test_batch_candidate_evidence_rejects_incomplete_operation_route_pair(
    tmp_path, monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    candidate = _store_changing_batch_candidate(tmp_path, monkeypatch)
    path = roadmap_candidate_run.candidate_evidence_path(tmp_path / "plans", _SLUG, candidate.version_id)
    payload = json.loads(path.read_bytes())
    payload.pop(missing)
    path.write_bytes(roadmap_candidate_run._canonical_json_bytes(payload))

    with pytest.raises(roadmap_candidate_run.CandidateProposalError, match="evidence is unreadable"):
        _reload_stored_candidate(tmp_path, candidate)


def test_batch_candidate_evidence_rejects_route_that_disagrees_with_stored_operations(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = _store_changing_batch_candidate(tmp_path, monkeypatch)

    _edit_stored_evidence(
        tmp_path,
        candidate,
        lambda data: data.update(operation_classification="structural"),
    )

    with pytest.raises(
        roadmap_candidate_run.CandidateProposalError,
        match="route does not match its stored operations",
    ):
        _reload_stored_candidate(tmp_path, candidate)


def test_batch_candidate_evidence_rejects_tampered_feedback_binding_with_same_artifact_bytes(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = _store_changing_batch_candidate(tmp_path, monkeypatch)
    _edit_stored_evidence(
        tmp_path,
        candidate,
        lambda data: data["normalized_operations"][0].update(feedback_id="not-admitted"),
    )

    with pytest.raises(
        roadmap_candidate_run.CandidateProposalError,
        match="exceed stored reviewer authority",
    ):
        _reload_stored_candidate(tmp_path, candidate)


@pytest.mark.parametrize(
    "edit",
    (
        lambda data: data["predecessor_diff"]["changed_artifacts"][0].update(after_digest="f" * 64),
        lambda data: data["predecessor_diff"]["changed_rows"][0]["after"].update(name="Forged name"),
    ),
    ids=("changed-artifact-digest", "changed-row-content"),
)
def test_batch_candidate_evidence_with_an_edited_predecessor_diff_is_refused_on_reload(
    tmp_path, monkeypatch: pytest.MonkeyPatch, edit
) -> None:
    """The diff is the one stored field the batch flow reads (the question prompt and
    `diff-row` anchors), and it is recomputable from the source and the stored artifacts."""
    candidate = _store_changing_batch_candidate(tmp_path, monkeypatch)
    assert _reload_stored_candidate(tmp_path, candidate).version_id == candidate.version_id

    _edit_stored_evidence(tmp_path, candidate, edit)

    with pytest.raises(roadmap_candidate_run.CandidateProposalError, match="predecessor diff cannot be reproduced"):
        _reload_stored_candidate(tmp_path, candidate)


def test_batch_candidate_evidence_content_identity_is_bound_by_the_stored_record_not_recomputed(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Carve-out: batch evidence carries no response patch, so its content identity cannot be
    recomputed; the stored version record is what binds it, and an edit is refused there."""
    candidate = _store_changing_batch_candidate(tmp_path, monkeypatch)

    _edit_stored_evidence(tmp_path, candidate, lambda data: data.update(content_identity="0" * 64))

    with pytest.raises(roadmap_candidate_run.CandidateProposalError, match="does not bind its stored version"):
        _reload_stored_candidate(tmp_path, candidate)


def _only_run_log(tmp_path):
    log_path = next((tmp_path / ".plan-tool" / "runs" / _SLUG).glob("*.jsonl"))
    events = read_run_events(log_path)
    return log_path, events, next(event for event in events if event["event"] == "phase_end")


def _run_batch_with_reply(tmp_path, reply: str):
    return roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG, "domain:ignored-by-the-ledger-batch-route", repo_root=tmp_path, plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, reply),
    )


_REAL_COMPLETE_GATES = roadmap_candidate.check_complete_roadmap_gates


def _ordering_reference_gate_only(evidence, *, stages=STAGES):
    """The real gates, narrowed to the ordering-reference kind this fixture can isolate."""
    return tuple(
        replace(
            outcome,
            violations=tuple(
                violation
                for violation in outcome.violations
                if violation.kind == roadmap_gates.VIOLATION_UNDEFINED_ORDERING_PLAN_REFERENCE
            ),
        )
        for outcome in _REAL_COMPLETE_GATES(evidence, stages=stages)
    )


def _batch_plan_addition(plan_id: str, depends_on: tuple[str, ...]) -> dict[str, object]:
    return {
        "op": "add-row", "feedback_id": "batch-one", "artifact_key": "plans", "row_type": "plans",
        "row": {
            "id": plan_id, "title": f"Deliver {plan_id}", "disposition": "keep",
            "component_ids": ["component-order"], "draft_seed_path": f"plan-seed-drafts/{plan_id}.md",
            "sizing_rationale": "Keep the slice small.",
        },
        "prose_amendment": {"row_id": plan_id, "fragment": f"Describe {plan_id}."},
        "ordering": {"plan_id": plan_id, "depends_on": list(depends_on)},
    }


def test_unresolved_reference_retry_prompt_names_the_owner_row_relation_and_missing_id(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _ = _seed_batch_ledger(tmp_path, monkeypatch)
    missing = {**_FIRST_BATCH_DELTA, "operations": [_batch_plan_addition("a-plan", ("ghost-plan",))]}
    corrected = {**_FIRST_BATCH_DELTA, "operations": [_batch_plan_addition("a-plan", ())]}
    prompts: list[str] = []
    replies = iter((json.dumps(missing), json.dumps(corrected)))

    def invoke(prompt: str) -> tuple[int, str]:
        prompts.append(prompt)
        return 0, next(replies)

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG, None, repo_root=tmp_path, plans_dir=tmp_path / "plans", invoker=invoke,
    )

    assert result.outcome == "stored", result.detail
    assert result.call_count == 2
    correction = prompts[1].split("Correction for the preceding rejected reply: ", 1)[1]
    assert 'plans row \\"a-plan\\": ordering-depends-on; reference \\"ghost-plan\\" names no plan row it may cite' in correction
    assert "every affected declared relation endpoint requires predecessor membership" not in correction
    assert load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG).record.version_id == root.record.version_id


def test_ordering_cycle_retry_prompt_names_the_cycle_and_its_plans_not_a_missing_reference(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _ = _seed_batch_ledger(tmp_path, monkeypatch)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _ordering_reference_gate_only)
    cyclic = {
        **_FIRST_BATCH_DELTA,
        "operations": [_batch_plan_addition("a-plan", ("b-plan",)), _batch_plan_addition("b-plan", ("a-plan",))],
    }
    corrected = {
        **_FIRST_BATCH_DELTA,
        "operations": [_batch_plan_addition("a-plan", ("b-plan",)), _batch_plan_addition("b-plan", ())],
    }
    prompts: list[str] = []
    replies = iter((json.dumps(cyclic), json.dumps(corrected)))

    def invoke(prompt: str) -> tuple[int, str]:
        prompts.append(prompt)
        return 0, next(replies)

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG, None, repo_root=tmp_path, plans_dir=tmp_path / "plans", invoker=invoke,
    )

    assert result.outcome == "stored", result.detail
    assert result.call_count == 2
    correction = prompts[1].split("Correction for the preceding rejected reply: ", 1)[1]
    assert 'row \\"a-plan\\": undefined-ordering-plan-reference' in correction
    assert 'ordering reference \\"b-plan\\" closes a cycle' in correction
    assert "reference a defined, permitted roadmap row or value" not in correction
    assert load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG).record.version_id == root.record.version_id


def test_ledger_entity_addition_corrects_class_name_and_reaches_structural_review(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _ = _seed_batch_ledger(tmp_path, monkeypatch)
    operation = {
        "op": "add-row", "feedback_id": "batch-one", "artifact_key": "domain",
        "row_type": "entities", "row": {
            "id": "entity-new", "name": "New entity",
            "fields": [{"name": "order", "type": "reference", "entity_id": "entity-order"}],
        },
     "prose_amendment": {"row_id": "entity-new", "fragment": "Describe entity-new."},}
    valid = {**_FIRST_BATCH_DELTA, "operations": [operation]}
    invalid = {**valid, "operations": [{**operation, "row_type": "EntityRow"}]}
    prompts: list[str] = []
    replies = iter((json.dumps(invalid), json.dumps(valid)))

    def invoke(prompt: str) -> tuple[int, str]:
        prompts.append(prompt)
        return 0, next(replies)

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG, None, repo_root=tmp_path, plans_dir=tmp_path / "plans", invoker=invoke,
    )

    assert result.outcome == "stored", result.detail
    assert result.call_count == 2 and result.candidate is not None
    assert result.candidate.evidence.operation_classification is roadmap_candidate.CandidateOperationClassification.STRUCTURAL
    assert "invalid-row-type" in prompts[1]
    assert "entities" in prompts[1]
    assert "Every eligible `add-row` must include its required `prose_amendment` object" in prompts[0]
    assert "including the required row-owned prose amendment for every eligible add-row" in prompts[1]
    assert "\"EntityRow\":[\"entities\"]" in prompts[0]
    assert load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG).record.version_id == root.record.version_id
    view = roadmap_candidate_review.build_candidate_stack_view(
        plans_dir=tmp_path / "plans", slug=_SLUG, candidate=result.candidate
    )
    assert view.digest
    _, events, _ = _only_run_log(tmp_path)
    failures = [event for event in events if event["event"] == "parse_failure"]
    assert [failure["attempt"] for failure in failures] == [1]
    assert (tmp_path / failures[0]["failure_path"]).read_text(encoding="utf-8") == json.dumps(invalid)


def test_malformed_batch_operation_envelope_correction_reaches_inert_structural_candidate(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _ = _seed_batch_ledger(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    accepted_head_before = accepted_head_path(plans_dir, _SLUG).read_bytes()
    valid = _STRUCTURAL_FIRST_BATCH_DELTA
    operation = valid["operations"][0]
    invalid = {
        **valid,
        "operations": [{**operation, "collection": "entities", "row_type": "EntityRow"}],
    }
    prompts: list[str] = []
    replies = iter((json.dumps(invalid), json.dumps(valid)))

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG, None, repo_root=tmp_path, plans_dir=tmp_path / "plans",
        invoker=lambda prompt: (prompts.append(prompt) or (0, next(replies))),
    )

    assert result.outcome == "stored", result.detail
    assert result.call_count == 2 and result.candidate is not None
    assert result.candidate.evidence.operation_classification is roadmap_candidate.CandidateOperationClassification.STRUCTURAL
    assert "candidate replace-row operation has unknown-field collection" in prompts[1]
    assert "candidate row has invalid-row-type EntityRow; use entities" in prompts[1]
    assert accepted_head_path(plans_dir, _SLUG).read_bytes() == accepted_head_before
    assert load_accepted_version(plans_dir=plans_dir, slug=_SLUG).record.version_id == root.record.version_id
    assert roadmap_candidate_review.build_candidate_stack_view(
        plans_dir=plans_dir, slug=_SLUG, candidate=result.candidate
    ).digest


def test_malformed_batch_add_row_envelope_correction_reaches_inert_structural_candidate(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The stored Integration shape: add-row carrying collection, a class-name row_type, and row_id.
    root, _ = _seed_batch_ledger(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    operation = {
        "op": "add-row", "feedback_id": "batch-one", "artifact_key": "domain",
        "row_type": "entities", "row": {
            "id": "entity-new", "name": "New entity",
            "fields": [{"name": "order", "type": "reference", "entity_id": "entity-order"}],
        },
     "prose_amendment": {"row_id": "entity-new", "fragment": "Describe entity-new."},}
    valid = {**_FIRST_BATCH_DELTA, "operations": [operation]}
    invalid = {
        **valid,
        "operations": [
            {**operation, "collection": "entities", "row_type": "EntityRow", "row_id": "entity-new"}
        ],
    }
    prompts: list[str] = []
    replies = iter((json.dumps(invalid), json.dumps(valid)))

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG, None, repo_root=tmp_path, plans_dir=plans_dir,
        invoker=lambda prompt: (prompts.append(prompt) or (0, next(replies))),
    )

    assert result.outcome == "stored", result.detail
    assert result.call_count == 2 and result.candidate is not None
    assert result.candidate.evidence.operation_classification is roadmap_candidate.CandidateOperationClassification.STRUCTURAL
    assert "candidate add-row operation has unknown-field collection, row_id" in prompts[1]
    assert "candidate row has invalid-row-type EntityRow; use entities" in prompts[1]
    assert load_accepted_version(plans_dir=plans_dir, slug=_SLUG).record.version_id == root.record.version_id
    _, events, _ = _only_run_log(tmp_path)
    failures = [event for event in events if event["event"] == "parse_failure"]
    assert [failure["attempt"] for failure in failures] == [1]
    assert (tmp_path / failures[0]["failure_path"]).read_text(encoding="utf-8") == json.dumps(invalid)


def test_malformed_batch_decision_source_correction_reaches_inert_structural_candidate(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _ = _seed_batch_ledger(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    accepted_head_before = accepted_head_path(plans_dir, _SLUG).read_bytes()
    operation = {
        "op": "add-row", "feedback_id": "batch-one", "artifact_key": "domain",
        "row_type": "decisions", "row": {
            "id": "decision-new", "chosen_option": "Keep the entity name.",
            "rejected_alternatives": [], "rationale": "The reviewer requested it.",
            "anchor": "entity-order", "status": "settled",
        },
     "prose_amendment": {"row_id": "decision-new", "fragment": "Describe decision-new."},}
    valid = {**_STRUCTURAL_FIRST_BATCH_DELTA, "operations": [operation]}
    invalid = {
        **valid,
        "operations": [{
            **operation,
            "row_type": "DecisionRow",
            "row": {**operation["row"], "source": "ledger"},
        }],
    }
    prompts: list[str] = []
    replies = iter((json.dumps(invalid), json.dumps(valid)))

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG, None, repo_root=tmp_path, plans_dir=tmp_path / "plans",
        invoker=lambda prompt: (prompts.append(prompt) or (0, next(replies))),
    )

    assert result.outcome == "stored", result.detail
    assert result.call_count == 2 and result.candidate is not None
    assert result.candidate.evidence.operation_classification is roadmap_candidate.CandidateOperationClassification.STRUCTURAL
    assert "candidate row has invalid-row-type DecisionRow; use decisions" in prompts[1]
    assert "decisions row has unknown-field source" in prompts[1]
    assert accepted_head_path(plans_dir, _SLUG).read_bytes() == accepted_head_before
    assert load_accepted_version(plans_dir=plans_dir, slug=_SLUG).record.version_id == root.record.version_id
    assert roadmap_candidate_review.build_candidate_stack_view(
        plans_dir=plans_dir, slug=_SLUG, candidate=result.candidate
    ).digest


def test_batch_gate_correction_identifies_closed_failure_and_stores_candidate(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _ = _seed_batch_ledger(tmp_path, monkeypatch)
    secret = "arbitrary model prose must not be copied"
    valid = _STRUCTURAL_FIRST_BATCH_DELTA
    operation = valid["operations"][0]
    invalid = {**valid, "operations": [{
        **operation,
        "row": {**operation["row"], "fields": []},
    }]}

    def gates(evidence, *, stages=STAGES):
        domain = evidence.artifacts[0]
        order = next(row for row in domain.entities if row.id == "entity-order")
        if not order.fields:
            return (
                RoadmapGateOutcome(stages[0], (
                    roadmap_gates.Violation(
                        roadmap_gates.VIOLATION_ENTITY_WITHOUT_FIELDS,
                        "domain.md", "entity-order", secret,
                    ),
                )),
                *tuple(RoadmapGateOutcome(stage, ()) for stage in stages[1:]),
            )
        return _green_gates(evidence, stages=stages)

    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", gates)
    prompts: list[str] = []

    def invoke(prompt: str) -> tuple[int, str]:
        prompts.append(prompt)
        if len(prompts) == 2:
            assert "entity-without-fields" in prompt
            assert "entity-order" in prompt
            assert "declare at least one named, typed field for the entity" in prompt
            assert secret not in prompt
        return 0, json.dumps(invalid if len(prompts) == 1 else valid)

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG, None, repo_root=tmp_path, plans_dir=tmp_path / "plans", invoker=invoke,
    )
    assert result.outcome == "stored" and result.call_count == 2
    assert result.candidate is not None
    assert load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG).record.version_id == root.record.version_id


def test_non_addable_batch_collection_correction_names_authority_and_stores_replacement(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _ = _seed_batch_ledger(tmp_path, monkeypatch)
    valid = _STRUCTURAL_FIRST_BATCH_DELTA
    invalid = {**valid, "operations": [{
        "op": "add-row", "feedback_id": "batch-one", "artifact_key": "components",
        "row_type": "component_patterns", "row": {"id": "pattern-new"},
     "prose_amendment": {"row_id": "pattern-new", "fragment": "Describe pattern-new."},}]}
    prompts: list[str] = []
    replies = iter((json.dumps(invalid), json.dumps(valid)))
    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG, None, repo_root=tmp_path, plans_dir=tmp_path / "plans",
        invoker=lambda prompt: (prompts.append(prompt) or (0, next(replies))),
    )
    assert result.outcome == "stored" and result.call_count == 2
    assert result.candidate is not None
    assert "component_patterns cannot be added" in prompts[1]
    assert "replace an authorized existing row or omit this operation" in prompts[1]
    assert load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG).record.version_id == root.record.version_id


def test_non_addable_batch_collection_exhausts_two_receipted_attempts_without_storage(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _ = _seed_batch_ledger(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    versions_path = version_directory_path(plans_dir, _SLUG, root.record.version_id).parent
    before = set(versions_path.iterdir())
    invalid = {**_STRUCTURAL_FIRST_BATCH_DELTA, "operations": [{
        "op": "add-row", "feedback_id": "batch-one", "artifact_key": "components",
        "row_type": "component_patterns", "row": {"id": "pattern-new"},
     "prose_amendment": {"row_id": "pattern-new", "fragment": "Describe pattern-new."},}]}
    reply = json.dumps(invalid)
    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG, None, repo_root=tmp_path, plans_dir=plans_dir,
        invoker=lambda _prompt: (0, reply),
    )
    assert result.outcome == "response-rejected" and result.call_count == 2
    assert result.candidate is None
    assert "component_patterns cannot be added" in result.detail
    _, events, _ = _only_run_log(tmp_path)
    failures = [event for event in events if event["event"] == "parse_failure"]
    assert [event["attempt"] for event in failures] == [1, 2]
    assert [event["response_digest"] for event in failures] == [_digest(reply.encode())] * 2
    assert all((tmp_path / event["failure_path"]).read_text(encoding="utf-8") == reply for event in failures)
    assert set(versions_path.iterdir()) == before
    assert load_accepted_version(plans_dir=plans_dir, slug=_SLUG).record.version_id == root.record.version_id


def test_malformed_batch_retry_preserves_first_response_receipt_after_storage(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_batch_ledger(tmp_path, monkeypatch)
    valid = _STRUCTURAL_FIRST_BATCH_DELTA
    invalid = {
        **valid,
        "operations": [{**valid["operations"][0], "collection": "entities", "row_type": "EntityRow"}],
    }
    rejected_reply = json.dumps(invalid)
    replies = iter((rejected_reply, json.dumps(valid)))

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG, None, repo_root=tmp_path, plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, next(replies)),
    )

    assert result.outcome == "stored", result.detail
    assert result.call_count == 2
    _, events, _ = _only_run_log(tmp_path)
    failures = [event for event in events if event["event"] == "parse_failure"]
    assert [failure["attempt"] for failure in failures] == [1]
    assert (tmp_path / failures[0]["failure_path"]).read_bytes() == rejected_reply.encode("utf-8")


def test_malformed_batch_retry_does_not_publish_accepted_head(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _ = _seed_batch_ledger(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    accepted_head_before = accepted_head_path(plans_dir, _SLUG).read_bytes()
    accepted_version_before = load_accepted_version(plans_dir=plans_dir, slug=_SLUG)
    valid = _STRUCTURAL_FIRST_BATCH_DELTA
    invalid = {
        **valid,
        "operations": [{**valid["operations"][0], "collection": "entities", "row_type": "EntityRow"}],
    }
    replies = iter((json.dumps(invalid), json.dumps(valid)))

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG, None, repo_root=tmp_path, plans_dir=plans_dir,
        invoker=lambda _prompt: (0, next(replies)),
    )

    assert result.outcome == "stored", result.detail
    assert result.call_count == 2 and result.candidate is not None
    assert result.candidate.evidence.operation_classification is roadmap_candidate.CandidateOperationClassification.STRUCTURAL
    assert accepted_head_path(plans_dir, _SLUG).read_bytes() == accepted_head_before
    accepted_version_after = load_accepted_version(plans_dir=plans_dir, slug=_SLUG)
    assert accepted_version_after == accepted_version_before
    assert accepted_version_after.record.version_id == root.record.version_id
    assert roadmap_candidate_review.build_candidate_stack_view(
        plans_dir=plans_dir, slug=_SLUG, candidate=result.candidate
    ).digest


def test_ledger_correction_transport_failure_keeps_first_rejection_receipt(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_batch_ledger(tmp_path, monkeypatch)
    replies = iter(((0, '{"operations":[]} malformed'), (1, "backend failure")))
    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG, None, repo_root=tmp_path, plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: next(replies),
    )

    assert (result.outcome, result.call_count) == ("failed", 2)
    _, events, terminal = _only_run_log(tmp_path)
    failures = [event for event in events if event["event"] == "parse_failure"]
    assert failures[0]["attempt"] == 1
    assert (tmp_path / failures[0]["failure_path"]).read_text(encoding="utf-8") == '{"operations":[]} malformed'
    assert terminal["failure_call_count"] == 2


def test_two_rejected_ledger_replies_keep_authority_and_mutable_state_fixed(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _ = _seed_batch_ledger(tmp_path, monkeypatch)
    ledger_path = roadmap_feedback_ledger_path(tmp_path / "plans", _SLUG)
    ledger_before = ledger_path.read_bytes()
    admission_before = roadmap_candidate_run.load_candidate_admission(
        plans_dir=tmp_path / "plans", slug=_SLUG
    )
    versions_path = version_directory_path(tmp_path / "plans", _SLUG, root.record.version_id).parent
    versions_before = set(versions_path.iterdir())
    prompts: list[str] = []
    replies = ('{"operations":[]} first secret', '{"operations":[]} second secret')

    def invoke(prompt: str) -> tuple[int, str]:
        if prompts:
            log_path = next((tmp_path / ".plan-tool" / "runs" / _SLUG).glob("*.jsonl"))
            events = read_run_events(log_path)
            first_failure = next(event for event in events if event["event"] == "parse_failure")
            assert (tmp_path / first_failure["failure_path"]).read_text(encoding="utf-8") == replies[0]
        prompts.append(prompt)
        return 0, replies[len(prompts) - 1]

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG, None, repo_root=tmp_path, plans_dir=tmp_path / "plans", invoker=invoke,
    )

    assert (result.outcome, result.call_count) == ("response-rejected", 2)
    assert len(prompts) == 2
    for marker in ("Issued batch payload:\n\n", "Issued batch receipt:\n\n"):
        assert prompts[0].split(marker, 1)[1].split("\n\n", 1)[0].strip() == prompts[1].split(marker, 1)[1].split("\n\n", 1)[0].strip()
    assert "first secret" not in prompts[1]
    assert ledger_path.read_bytes() == ledger_before
    assert roadmap_candidate_run.load_candidate_admission(plans_dir=tmp_path / "plans", slug=_SLUG) == admission_before
    assert set(versions_path.iterdir()) == versions_before
    log_path, events, terminal = _only_run_log(tmp_path)
    failures = [event for event in events if event["event"] == "parse_failure"]
    assert [event["attempt"] for event in failures] == [1, 2]
    assert [(tmp_path / event["failure_path"]).read_text(encoding="utf-8") for event in failures] == list(replies)
    assert [event["response_digest"] for event in failures] == [_digest(reply.encode()) for reply in replies]
    assert terminal["failure_attempt"] == 2
    assert all(secret not in log_path.read_text(encoding="utf-8") for secret in ("first secret", "second secret"))


def test_a_rejected_batch_reply_records_its_exact_response_receipt_and_failure_attempt(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The batch route reports a rejected reply the way the selector route does: a
    parse-failure receipt holding the exact bytes, and the attempt that produced it."""
    _seed_batch_ledger(tmp_path, monkeypatch)
    reply = '{"operations":[]} candidate response secret'

    result = _run_batch_with_reply(tmp_path, reply)

    log_path, events, terminal = _only_run_log(tmp_path)
    failures = [event for event in events if event["event"] == "parse_failure"]
    assert (result.outcome, result.call_count) == ("response-rejected", 2)
    assert [failure["attempt"] for failure in failures] == [1, 2]
    assert all(failure["reason"] == result.detail for failure in failures)
    assert all(failure["response_capture"] == "stored" for failure in failures)
    assert all(failure["response_digest"] == _digest(reply.encode("utf-8")) for failure in failures)
    assert all((tmp_path / failure["failure_path"]).read_text(encoding="utf-8") == reply for failure in failures)
    assert terminal["failure_attempt"] == 2
    assert terminal["failure_call_count"] == result.call_count
    assert "candidate response secret" not in log_path.read_text(encoding="utf-8")


def test_a_batch_materialization_refusal_records_the_reply_it_refused(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A reply that parses but names an item outside the admitted batch is still a
    rejected response, so its bytes are retained for the operator."""
    _seed_batch_ledger(tmp_path, monkeypatch)
    reply = json.dumps({**_FIRST_BATCH_DELTA, "responses": [{"item_id": "not-admitted", "response": "x"}]})

    result = _run_batch_with_reply(tmp_path, reply)

    _log_path, events, terminal = _only_run_log(tmp_path)
    failure = next(event for event in events if event["event"] == "parse_failure")
    assert result.outcome == "response-rejected"
    assert (tmp_path / failure["failure_path"]).read_text(encoding="utf-8") == reply
    assert terminal["failure_attempt"] == 2


def test_batch_storage_failure_after_a_valid_reply_is_not_recorded_as_a_parse_failure(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Carve-out: once materialization accepts the reply, a later storage failure is not
    the model's fault, so no parse-failure receipt is written for it."""
    _seed_batch_ledger(tmp_path, monkeypatch)

    def fail_store(**_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(roadmap_candidate_run, "_store_batch_candidate", fail_store)

    result = _run_batch_with_reply(tmp_path, json.dumps(_FIRST_BATCH_DELTA))

    _log_path, events, terminal = _only_run_log(tmp_path)
    assert result.outcome == "failed"
    assert not any(event["event"] == "parse_failure" for event in events)
    assert terminal["response_capture"] == "not-applicable"
    assert not (tmp_path / ".plan-tool" / "parse-failures").exists()


def test_a_backend_error_raised_during_the_batch_call_still_counts_the_call(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The call is counted before it is made, so an error that escapes the model call
    reports one call rather than none."""
    _seed_batch_ledger(tmp_path, monkeypatch)

    def broken_backend(_prompt: str) -> tuple[int, str]:
        raise OSError("backend unavailable")

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG, "domain:ignored-by-the-ledger-batch-route", repo_root=tmp_path, plans_dir=tmp_path / "plans",
        invoker=broken_backend,
    )

    _log_path, _events, terminal = _only_run_log(tmp_path)
    assert (result.outcome, result.call_count) == ("failed", 1)
    assert terminal["call_count"] == 1


_SECOND_BATCH_DELTA = {
    "operations": [],
    "responses": [],
    "derived_feedback": [{"context_id": "derived-two", "content": "Check naming again."}],
}


def _snapshot(directory) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def test_a_new_batch_hop_over_a_candidate_stored_under_an_earlier_ceiling_uses_the_current_ceiling(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Integration case: the active candidate was issued under 192 KiB and the follow-up is compiled
    under the current ceiling. The source keeps its ceiling and bytes; the hop records its own."""
    with monkeypatch.context() as issued_then:
        issued_then.setattr(roadmap_candidate_context, "CANDIDATE_CONTEXT_MAX_BYTES", 192 * 1024)
        _root, first = _store_first_batch_candidate(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    before = _snapshot(version_directory_path(plans_dir, _SLUG, first.version_id))

    second = _run_batch(tmp_path, _SECOND_BATCH_DELTA)

    assert first.evidence.batch_receipt.ceiling_bytes == 192 * 1024
    assert second.outcome == "stored", second.detail
    assert second.candidate is not None
    hop_ceiling = second.candidate.evidence.batch_receipt.ceiling_bytes
    assert hop_ceiling == roadmap_candidate_context.CANDIDATE_CONTEXT_MAX_BYTES
    assert hop_ceiling > 192 * 1024  # not inherited from the source candidate
    assert second.candidate.evidence.batch_receipt.source.version_id == first.version_id
    assert _snapshot(version_directory_path(plans_dir, _SLUG, first.version_id)) == before
    reloaded = _reload_stored_candidate(tmp_path, first)
    assert reloaded.evidence.batch_receipt.ceiling_bytes == 192 * 1024


def test_first_batch_candidate_writes_no_supersession_record(tmp_path, monkeypatch) -> None:
    _root, first = _store_first_batch_candidate(tmp_path, monkeypatch)

    assert not roadmap_candidate_run.supersession_path(
        tmp_path / "plans", _SLUG, first.version_id
    ).exists()


def test_successor_records_the_former_active_candidate_as_superseded_and_leaves_it_unmodified(
    tmp_path, monkeypatch
) -> None:
    """History, not a second selector: the pointer names only the successor, the
    former candidate's stored bytes and evidence are untouched, and one new
    immutable record ties the two together in the same generation."""
    root, first = _store_first_batch_candidate(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    before = _snapshot(version_directory_path(plans_dir, _SLUG, first.version_id))
    before_evidence = roadmap_candidate_run.candidate_evidence_path(
        plans_dir, _SLUG, first.version_id
    ).read_bytes()

    second = _run_batch(tmp_path, _SECOND_BATCH_DELTA)

    assert second.outcome == "stored"
    assert second.candidate is not None
    assert second.candidate.version_id != first.version_id
    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug=_SLUG)
    assert admission is not None
    assert admission.active_candidate_version_id == second.candidate.version_id
    assert admission.root_version_id == root.record.version_id

    path = roadmap_candidate_run.supersession_path(plans_dir, _SLUG, first.version_id)
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "root_version_id": root.record.version_id,
        "superseded_candidate_version_id": first.version_id,
        "successor_candidate_version_id": second.candidate.version_id,
    }
    assert not roadmap_candidate_run.supersession_path(
        plans_dir, _SLUG, second.candidate.version_id
    ).exists()
    assert _snapshot(version_directory_path(plans_dir, _SLUG, first.version_id)) == before
    assert (
        roadmap_candidate_run.candidate_evidence_path(plans_dir, _SLUG, first.version_id).read_bytes()
        == before_evidence
    )
    reloaded = roadmap_candidate_run.load_stored_candidate_proposal(
        plans_dir=plans_dir, slug=_SLUG, candidate_version_id=first.version_id
    )
    assert reloaded.evidence.model_dump(mode="json") == first.evidence.model_dump(mode="json")
    derived = load_ledger(roadmap_feedback_ledger_path(plans_dir, _SLUG)).derived_context
    assert {entry.source_version_id for entry in derived} == {
        first.version_id,
        second.candidate.version_id,
    }


def test_existing_supersession_record_refuses_the_successor_and_leaves_the_pointer(
    tmp_path, monkeypatch
) -> None:
    """An immutable record is never overwritten: a pre-existing one fails the
    whole storage generation, so no successor and no pointer change survive."""
    _root, first = _store_first_batch_candidate(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    path = roadmap_candidate_run.supersession_path(plans_dir, _SLUG, first.version_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"pre-existing")
    admission_before = roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG).read_bytes()

    second = _run_batch(tmp_path, _SECOND_BATCH_DELTA)

    assert second.outcome == "refused"
    assert "supersession already exists" in second.detail
    assert path.read_bytes() == b"pre-existing"
    assert (
        roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG).read_bytes()
        == admission_before
    )


def test_supersession_record_requires_digest_identities_and_a_supported_schema() -> None:
    good = {
        "schema_version": 1,
        "root_version_id": "a" * 64,
        "superseded_candidate_version_id": "b" * 64,
        "successor_candidate_version_id": "c" * 64,
    }
    roadmap_candidate_run.CandidateSupersession.model_validate(good)

    for field, value in (
        ("schema_version", 2),
        ("root_version_id", "not-a-digest"),
        ("superseded_candidate_version_id", "B" * 64),
        ("successor_candidate_version_id", ""),
    ):
        with pytest.raises(ValueError):
            roadmap_candidate_run.CandidateSupersession.model_validate({**good, field: value})


def _stored_version_count(plans_dir) -> int:
    namespace = roadmap_candidate_run.version_namespace_path(plans_dir, _SLUG)
    return sum(1 for entry in namespace.iterdir() if entry.is_dir() and len(entry.name) == 64)


def _run_batch_mutating_state_before_storage(tmp_path, mutate):
    """Run one batch whose model call (between batch build and storage) changes state."""

    def invoker(_prompt: str) -> tuple[int, str]:
        mutate()
        return 0, json.dumps(_FIRST_BATCH_DELTA)

    return roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        "domain:ignored-by-the-ledger-batch-route",
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=invoker,
    )


def test_changed_admitted_item_refuses_storage_but_unrelated_ledger_edit_does_not(
    tmp_path, monkeypatch
) -> None:
    _root, resolved = _seed_batch_ledger(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    ledger_path = roadmap_feedback_ledger_path(plans_dir, _SLUG)

    def edit_admitted_item() -> None:
        ledger = load_ledger(ledger_path)
        group = ledger.reviewer_feedback_groups[0]
        edited = group.items[0].model_copy(update={"request": "Changed while the model ran."})
        ledger_path.write_bytes(
            render_ledger(
                ledger.model_copy(
                    update={
                        "reviewer_feedback_groups": (group.model_copy(update={"items": (edited,)}),)
                    }
                )
            )
        )

    refused = _run_batch_mutating_state_before_storage(tmp_path, edit_admitted_item)

    assert refused.outcome == "refused"
    assert refused.detail == "admitted reviewer item changed before storage"
    assert load_ledger(ledger_path).reviewer_feedback_groups[0].items[0].request == (
        "Changed while the model ran."
    )
    assert not roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG).exists()
    assert _stored_version_count(plans_dir) == 1

    # A reviewer edit to an item outside the admitted batch is not a conflict and survives.
    unrelated = _batch_item(resolved, "unrelated", "entity-customer")

    def add_unrelated_item() -> None:
        ledger = load_ledger(ledger_path)
        group = ledger.reviewer_feedback_groups[0]
        ledger_path.write_bytes(
            render_ledger(
                ledger.model_copy(
                    update={
                        "reviewer_feedback_groups": (
                            group.model_copy(update={"items": (*group.items, unrelated)}),
                        )
                    }
                )
            )
        )

    stored = _run_batch_mutating_state_before_storage(tmp_path, add_unrelated_item)

    assert stored.outcome == "stored"
    items = {item.item_id: item for item in load_ledger(ledger_path).reviewer_feedback_groups[0].items}
    assert items["unrelated"] == unrelated
    assert items["batch-one"].state is ReviewerItemState.AWAITING_REVIEW


_STRUCTURAL_FIRST_BATCH_DELTA = {
    "operations": [
        {
            "op": "replace-row", "feedback_id": "batch-one", "artifact_key": "domain",
            "row_type": "entities", "row_id": "entity-order",
            "row": {
                "id": "entity-order", "name": "Order",
                "fields": [{"name": "buyer", "type": "reference", "entity_id": "entity-customer"}],
            },
        }
    ],
    "responses": [{"item_id": "batch-one", "response": "Use buyer."}],
    "derived_feedback": [{"context_id": "derived-one", "content": "Check naming."}],
}


def _stored_files_of(plans_dir, version_id: str) -> dict:
    """Every stored member of one version, evidence included: the bytes a later batch must leave alone."""
    directory = version_directory_path(plans_dir, _SLUG, version_id)
    return {path: path.read_bytes() for path in sorted(directory.rglob("*")) if path.is_file()}


@pytest.mark.parametrize("active_state", ("initial", "approved-not-promoted", "edit-produced"))
def test_a_batch_stacks_on_an_active_structural_candidate_in_every_active_state(
    tmp_path, monkeypatch, active_state: str
) -> None:
    """Structural approval, not proposal, is where structural content is decided: a batch over an active
    structural candidate is stored as its own presentation-only hop above it, with no refusal, because
    the one approval every route to the head requires asks the whole stack. Approval alone does not
    promote and an edit continues on the replacement, so all three active states are pinned; a block
    narrowed to any one of them passes every other test. The first hop carries derived context so a
    second batch has work: without it the batch would end as `no eligible work` and prove nothing."""
    root, _resolved = _seed_batch_ledger(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    first = _run_batch(tmp_path, _STRUCTURAL_FIRST_BATCH_DELTA)
    assert first.outcome == "stored", first.detail
    assert first.candidate is not None
    active = first.candidate
    if active_state == "approved-not-promoted":
        approved = _approve_structural_candidate(plans_dir, active)
        assert approved.outcome == "stored", approved.detail
    elif active_state == "edit-produced":
        edit_delta = json.loads(json.dumps(_STRUCTURAL_FIRST_BATCH_DELTA))
        edit_delta["operations"][0]["row"]["fields"][0]["name"] = "owner"
        edited = roadmap_candidate_review.decide_structural_candidate(
            _SLUG, active.version_id, "edit", correction="Call the field owner.",
            repo_root=tmp_path, plans_dir=plans_dir, invoker=lambda _prompt: (0, json.dumps(edit_delta)),
        )
        assert edited.outcome == "stored", edited.detail
        assert edited.active_candidate is not None
        assert edited.active_candidate.version_id != active.version_id
        active = edited.active_candidate
    assert active.evidence.operation_classification is (
        roadmap_candidate.CandidateOperationClassification.STRUCTURAL
    )
    former_files = _stored_files_of(plans_dir, active.version_id)
    assert former_files, "the former candidate must have stored members, or the unchanged check proves nothing"
    model_calls: list[str] = []

    def second_batch_reply(prompt: str) -> tuple[int, str]:
        model_calls.append(prompt)
        return 0, json.dumps(_SECOND_BATCH_DELTA)

    second = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        "domain:ignored-by-the-ledger-batch-route",
        repo_root=tmp_path,
        plans_dir=plans_dir,
        invoker=second_batch_reply,
    )

    assert second.outcome == "stored", second.detail
    assert second.call_count == 1 and len(model_calls) == 1
    stacked = second.candidate
    assert stacked is not None
    assert stacked.evidence.source_version_id == active.version_id
    assert stacked.evidence.root_version_id == root.record.version_id
    # The hop's own route is presentation-only; the structural change it carries is the hop below it.
    assert stacked.evidence.operation_classification is _PRESENTATION_ONLY
    assert roadmap_candidate_run.candidate_stack_route(
        plans_dir=plans_dir, slug=_SLUG,
        tip_version_id=stacked.version_id, root_version_id=root.record.version_id,
    ).is_structural is True, "the stack must still carry the structural hop, or this proves nothing"
    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug=_SLUG)
    assert admission is not None and admission.active_candidate_version_id == stacked.version_id
    supersession = json.loads(
        roadmap_candidate_run.supersession_path(plans_dir, _SLUG, active.version_id).read_text(encoding="utf-8")
    )
    assert supersession["successor_candidate_version_id"] == stacked.version_id
    assert _stored_files_of(plans_dir, active.version_id) == former_files


@pytest.mark.parametrize("first_hop", ("presentation-only", "route-less-legacy"))
def test_a_second_batch_still_stacks_on_an_active_candidate_that_is_not_structural(
    tmp_path, monkeypatch, first_hop: str
) -> None:
    """Carve-out: stacking never depended on the first hop's route, and a candidate with no stored route
    (batch evidence written before the route existed) is neither structural nor a reason to refuse. It
    would go red if a batch were ever refused on the strength of a route, or its absence."""
    _seed_batch_ledger(tmp_path, monkeypatch)
    first = _run_batch(tmp_path, _FIRST_BATCH_DELTA)
    assert first.outcome == "stored", first.detail
    assert first.candidate is not None
    plans_dir = tmp_path / "plans"
    if first_hop == "route-less-legacy":
        roadmap_candidate_run.candidate_evidence_path(
            plans_dir, _SLUG, first.candidate.version_id
        ).write_bytes(
            roadmap_candidate_run.render_candidate_evidence(
                first.candidate.evidence.model_copy(
                    update={"normalized_operations": None, "operation_classification": None}
                )
            )
        )

    second = _run_batch(tmp_path, _SECOND_BATCH_DELTA)

    assert second.outcome == "stored", second.detail
    assert second.candidate is not None
    assert second.candidate.evidence.source_version_id == first.candidate.version_id


def test_changed_active_pointer_refuses_storage_without_overwriting_ledger_or_history(
    tmp_path, monkeypatch
) -> None:
    root, _resolved = _seed_batch_ledger(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    ledger_path = roadmap_feedback_ledger_path(plans_dir, _SLUG)
    ledger_before = ledger_path.read_bytes()
    foreign = roadmap_candidate_run.CandidateProposalAdmission(
        schema_version=1,
        roadmap_slug=_SLUG,
        predecessor_version_id=root.record.version_id,
        expansion_available=False,
        candidate_version_id="a" * 64,
        root_version_id=root.record.version_id,
        active_candidate_version_id="a" * 64,
    )
    admission_path = roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG)

    def install_foreign_pointer() -> None:
        admission_path.parent.mkdir(parents=True, exist_ok=True)
        admission_path.write_bytes(roadmap_candidate_run.render_candidate_admission(foreign))

    result = _run_batch_mutating_state_before_storage(tmp_path, install_foreign_pointer)

    assert result.outcome == "refused"
    assert result.detail == "candidate processing pair changed before storage"
    assert admission_path.read_bytes() == roadmap_candidate_run.render_candidate_admission(foreign)
    assert ledger_path.read_bytes() == ledger_before
    assert _stored_version_count(plans_dir) == 1


def test_a_ledger_batch_proposal_takes_no_selector_and_logs_no_null_argument(
    tmp_path, monkeypatch
) -> None:
    """The CLI's selector-free proposal passes no selector; the run log must not record one."""
    _root, _resolved = _seed_batch_ledger(tmp_path, monkeypatch)

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        None,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, json.dumps(_FIRST_BATCH_DELTA)),
    )

    assert result.outcome == "stored", result.detail
    events = read_run_events(next((tmp_path / ".plan-tool" / "runs" / _SLUG).glob("*.jsonl")))
    start = next(event for event in events if event["event"] == "run_start")
    assert start["argv"] == ["plan-tool", "roadmap", _SLUG, "--propose-candidate"]


def test_a_ledger_less_roadmap_refuses_a_proposal_without_a_selector(tmp_path) -> None:
    """Only the selector-era route needs a selector; without one it refuses and admits nothing."""
    _enroll(tmp_path)

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        None,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: pytest.fail("a proposal without a selector must refuse before invoking"),
    )

    assert result.outcome == "refused"
    assert roadmap_candidate_run.load_candidate_admission(plans_dir=tmp_path / "plans", slug=_SLUG) is None


def _install_pointer(tmp_path, *, root_version_id: str, active: str | None) -> None:
    pointer = roadmap_candidate_run.CandidateProposalAdmission(
        schema_version=1,
        roadmap_slug=_SLUG,
        predecessor_version_id=root_version_id,
        expansion_available=False,
        candidate_version_id=active,
        root_version_id=root_version_id,
        active_candidate_version_id=active,
    )
    path = roadmap_candidate_run.candidate_admission_path(tmp_path / "plans", _SLUG)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(roadmap_candidate_run.render_candidate_admission(pointer))


def test_a_released_pointer_naming_an_older_root_does_not_block_a_batch_for_the_current_root(
    tmp_path, monkeypatch
) -> None:
    """Promotion releases the pointer but leaves the root it was released under, so a
    pointer with no active candidate cannot be judged stale by its root."""
    root, _resolved = _seed_batch_ledger(tmp_path, monkeypatch)
    _install_pointer(tmp_path, root_version_id="9" * 64, active=None)

    result = _run_batch(tmp_path, _FIRST_BATCH_DELTA)

    assert result.outcome == "stored", result.detail
    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=tmp_path / "plans", slug=_SLUG)
    assert admission is not None
    assert admission.root_version_id == root.record.version_id
    assert admission.active_candidate_version_id == result.candidate.version_id


def _store_selector_candidate_then_seed_ledger(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """A roadmap with an unpromoted selector-era candidate that later gained a ledger."""
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    stored = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG, _SELECTOR, repo_root=tmp_path, plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _delta_response()),
    )
    assert stored.candidate is not None
    _write_open_item_ledger(tmp_path)
    return stored.candidate


def test_a_ledger_batch_refuses_an_unpromoted_selector_era_candidate_and_changes_nothing(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A batch pointer would replace the admission and orphan the selector-era candidate's
    review lineage; the refusal comes before any model call and leaves every byte alone."""
    candidate = _store_selector_candidate_then_seed_ledger(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    admission_path = roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG)
    ledger_path = roadmap_feedback_ledger_path(plans_dir, _SLUG)
    before = (admission_path.read_bytes(), ledger_path.read_bytes())

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        "domain:ignored-by-the-ledger-batch-route",
        repo_root=tmp_path,
        plans_dir=plans_dir,
        invoker=lambda _prompt: pytest.fail("an unpromoted lineage must refuse before invoking"),
    )

    assert (result.outcome, result.detail, result.call_count) == (
        "refused", "unpromoted-candidate-lineage", 0
    )
    assert (admission_path.read_bytes(), ledger_path.read_bytes()) == before
    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug=_SLUG)
    assert admission is not None and admission.candidate_version_id == candidate.version_id


def test_a_selector_era_admission_that_names_no_stored_candidate_does_not_block_a_ledger_batch(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The refusal protects a stored candidate awaiting promotion; an admission naming none
    has nothing to orphan, and refusing it would strand the roadmap (the selector route has
    no release command)."""
    _store_selector_candidate_then_seed_ledger(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug=_SLUG)
    assert admission is not None
    roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG).write_bytes(
        roadmap_candidate_run.render_candidate_admission(
            admission.model_copy(update={"candidate_version_id": None})
        )
    )

    result = _run_batch(tmp_path, _FIRST_BATCH_DELTA)

    assert result.outcome == "stored", result.detail


def test_an_active_pointer_naming_another_root_still_refuses_a_batch(tmp_path, monkeypatch) -> None:
    """The carve-out above is only for a released pointer: a live candidate bound to a
    different root must still stop the batch before any model call."""
    _root, _resolved = _seed_batch_ledger(tmp_path, monkeypatch)
    _install_pointer(tmp_path, root_version_id="9" * 64, active="8" * 64)

    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        "domain:ignored-by-the-ledger-batch-route",
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: pytest.fail("a stale processing pair must refuse before invoking"),
    )

    assert result.outcome == "refused"
    assert result.detail == "candidate processing pair changed"


@pytest.mark.parametrize(
    ("keep_only_evidence", "detail"),
    (
        (False, "candidate version identity collides with existing storage"),
        (True, "candidate evidence identity collides with existing storage"),
    ),
    ids=("version-members", "evidence-only"),
)
def test_identity_collision_with_existing_storage_refuses_without_publishing(
    tmp_path, monkeypatch, keep_only_evidence: bool, detail: str
) -> None:
    """Replaying the same batch after its pointer is cleared reproduces the same
    content-derived identity; the existing bytes must never be overwritten."""
    _root, _resolved = _seed_batch_ledger(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    ledger_path = roadmap_feedback_ledger_path(plans_dir, _SLUG)
    admission_path = roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG)
    ledger_before = ledger_path.read_bytes()
    first = _run_batch(tmp_path, _FIRST_BATCH_DELTA)
    assert first.candidate is not None
    admission_path.unlink()
    ledger_path.write_bytes(ledger_before)
    if keep_only_evidence:
        evidence = roadmap_candidate_run.candidate_evidence_path(
            plans_dir, _SLUG, first.candidate.version_id
        )
        for member in evidence.parent.iterdir():
            if member != evidence:
                member.unlink()

    again = _run_batch(tmp_path, _FIRST_BATCH_DELTA)

    assert again.outcome == "refused"
    assert again.detail == detail
    assert not admission_path.exists()
    assert ledger_path.read_bytes() == ledger_before


def _store_two_hop_chain(tmp_path, monkeypatch):
    """root -> C1 -> C2 through the real batch runner; C2 is the active candidate."""
    root, first = _store_first_batch_candidate(tmp_path, monkeypatch)
    second = _run_batch(tmp_path, _SECOND_BATCH_DELTA)
    assert second.outcome == "stored" and second.candidate is not None
    return root, first, second.candidate


def test_third_batch_from_a_two_hop_active_candidate_stores_and_supersedes_it(
    tmp_path, monkeypatch
) -> None:
    """Successive batches chain candidate to candidate; the source only has to
    trace back to the root through stored candidates, not sit one hop from it."""
    root, first, second = _store_two_hop_chain(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    assert second.record.predecessor_version_id == first.version_id

    third = _run_batch(
        tmp_path,
        {
            "operations": [],
            "responses": [],
            "derived_feedback": [{"context_id": "derived-three", "content": "Third pass."}],
        },
    )

    assert third.outcome == "stored"
    assert third.candidate is not None
    assert third.candidate.record.predecessor_version_id == second.version_id
    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug=_SLUG)
    assert admission is not None
    assert admission.active_candidate_version_id == third.candidate.version_id
    assert admission.root_version_id == root.record.version_id
    for superseded in (first, second):
        assert roadmap_candidate_run.supersession_path(
            plans_dir, _SLUG, superseded.version_id
        ).is_file()


def _set_in(*path_and_value):
    *path, value = path_and_value

    def change(payload: dict) -> None:
        target = payload
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    return change


def _set_receipts_together(payload: dict) -> None:
    payload["receipt"]["ledger_digest"] = "9" * 64
    payload["batch_receipt"]["ledger_digest"] = "9" * 64


def _flip_last_payload_character(payload: dict) -> None:
    text = payload["capsule"]["payload"]
    payload["capsule"]["payload"] = text[:-1] + ("x" if text[-1] != "x" else "y")


@pytest.mark.parametrize(
    ("which", "mutate", "detail"),
    (
        ("first", _set_in("capsule", "reviewer_items", 0, "request", "Edited."), "does not match its stored evidence"),
        ("second", _set_in("capsule", "derived_context", 0, "content", "Edited."), "does not match its stored evidence"),
        ("first", _flip_last_payload_character, "does not match its stored evidence"),
        ("first", _set_in("capsule", "capsule_identity", "9" * 64), "does not match its stored evidence"),
        ("first", _set_in("capsule", "ledger_digest", "9" * 64), "does not match its stored evidence"),
        ("first", _set_receipts_together, "candidate evidence is unreadable"),
    ),
    ids=("capsule-reviewer-item", "capsule-derived-context", "capsule-payload", "capsule-identity",
         "capsule-ledger-digest", "evidence-receipt-without-capsule"),
)
def test_a_stored_batch_candidate_whose_capsule_disagrees_with_its_receipt_is_refused_on_reload(
    tmp_path, monkeypatch, which: str, mutate, detail: str
) -> None:
    """The capsule is the model input a later review or replacement re-sends, and the receipt is what
    identities bind. A capsule edited alone, or a receipt edited alone, must not be trusted on reload."""
    _root, first = _store_first_batch_candidate(tmp_path, monkeypatch)
    second = _run_batch(tmp_path, _SECOND_BATCH_DELTA)
    assert second.candidate is not None
    chosen = first if which == "first" else second.candidate
    plans_dir = tmp_path / "plans"
    path = roadmap_candidate_run.candidate_evidence_path(plans_dir, _SLUG, chosen.version_id)
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutate(payload)
    path.write_bytes(roadmap_candidate_run._canonical_json_bytes(payload))

    with pytest.raises(roadmap_candidate_run.CandidateProposalError, match=detail):
        roadmap_candidate_run.load_stored_candidate_proposal(
            plans_dir=plans_dir, slug=_SLUG, candidate_version_id=chosen.version_id
        )


def test_source_ancestry_walk_lists_predecessors_up_to_and_including_the_root(
    tmp_path, monkeypatch
) -> None:
    root, first, second = _store_two_hop_chain(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    root_id = root.record.version_id

    def walk(source_id: str, declared_root: str = root_id):
        return roadmap_candidate_run.source_ancestry_to_root(
            plans_dir=plans_dir, slug=_SLUG, source_version_id=source_id, root_version_id=declared_root
        )

    assert walk(root_id) == ()
    assert walk(first.version_id) == (root_id,)
    assert walk(second.version_id) == (first.version_id, root_id)
    with pytest.raises(roadmap_candidate_run.CandidateProposalError, match="trace to its declared root"):
        walk(second.version_id, declared_root="e" * 64)
    with pytest.raises(roadmap_candidate_run.CandidateProposalError, match="unreadable"):
        walk("d" * 64)


def test_active_candidate_with_a_missing_ancestor_is_refused_on_reload_not_trusted(
    tmp_path, monkeypatch
) -> None:
    """Deleting a non-adjacent ancestor leaves the source and root loadable, so
    only the ancestry walk can notice the chain no longer reaches the root."""
    _root, first, second = _store_two_hop_chain(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    third = _run_batch(
        tmp_path,
        {
            "operations": [],
            "responses": [],
            "derived_feedback": [{"context_id": "derived-three", "content": "Third pass."}],
        },
    )
    assert third.outcome == "stored" and third.candidate is not None
    assert third.candidate.record.predecessor_version_id == second.version_id
    shutil.rmtree(version_directory_path(plans_dir, _SLUG, first.version_id))

    with pytest.raises(roadmap_candidate_run.CandidateProposalError, match="unreadable"):
        roadmap_candidate_run.load_stored_candidate_proposal(
            plans_dir=plans_dir, slug=_SLUG, candidate_version_id=third.candidate.version_id
        )
    result = _run_batch(tmp_path, _SECOND_BATCH_DELTA)
    assert result.outcome == "failed"


def test_storage_binds_each_stored_proposal_to_the_candidate_that_produced_it(
    tmp_path, monkeypatch
) -> None:
    _root, first = _store_first_batch_candidate(tmp_path, monkeypatch)

    (item,) = load_ledger(
        roadmap_feedback_ledger_path(tmp_path / "plans", _SLUG)
    ).reviewer_feedback_groups[0].items

    assert item.state is ReviewerItemState.AWAITING_REVIEW
    assert item.proposal is not None
    assert item.proposal.response == "Rename the entity."
    assert item.proposal.candidate_version_id == first.version_id


def test_batch_storage_refuses_a_ledger_edit_that_lands_inside_the_publication_window(
    tmp_path, monkeypatch
) -> None:
    """publish_roadmap_generation overwrites members without comparing their recorded
    old bytes, so the storage generation must recheck the ledger itself."""
    _root, _resolved = _seed_batch_ledger(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    ledger_path = roadmap_feedback_ledger_path(plans_dir, _SLUG)
    real_publish = roadmap_candidate_run.publish_roadmap_generation

    def publish_after_a_hand_edit(generation, **kwargs):
        ledger_path.write_bytes(ledger_path.read_bytes() + b"# edited by hand\n")
        return real_publish(generation, **kwargs)

    monkeypatch.setattr(roadmap_candidate_run, "publish_roadmap_generation", publish_after_a_hand_edit)

    result = _run_batch(tmp_path, _FIRST_BATCH_DELTA)

    assert result.outcome == "refused"
    assert result.detail == "feedback ledger changed before storage"
    assert ledger_path.read_bytes().endswith(b"# edited by hand\n")
    assert not roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG).exists()
    assert _stored_version_count(plans_dir) == 1


# --------------------------------------------------------------------------
# Unpromoted stack route: derived from stored hop routes above the recorded root
# --------------------------------------------------------------------------

_STRUCTURAL = roadmap_candidate.CandidateOperationClassification.STRUCTURAL
_PRESENTATION_ONLY = roadmap_candidate.CandidateOperationClassification.PRESENTATION_ONLY


def _stack_hop_delta(number: int, route: str) -> dict:
    """Hop 0 answers the seeded item `batch-one`. A batch may only answer items eligible for its
    source, so a later hop answers an item filed against its source candidate (or none)."""
    item_id = "batch-one" if number == 0 else f"filed-against-hop-{number}"
    derived = [{"context_id": f"derived-hop-{number}", "content": "Check naming."}]
    if route == "structural":
        operation = {**_STRUCTURAL_FIRST_BATCH_DELTA["operations"][0], "feedback_id": item_id}
        responses = [{"item_id": item_id, "response": "Use buyer."}]
        return {"operations": [operation], "responses": responses, "derived_feedback": derived}
    responses = [{"item_id": item_id, "response": "Noted."}] if number == 0 else []
    return {"operations": [], "responses": responses, "derived_feedback": derived}


def _file_feedback_against_candidate(tmp_path, candidate, item_id: str) -> None:
    """Add an open reviewer item on `entity-order` submitted against a stored candidate."""
    plans_dir = tmp_path / "plans"
    ledger_path = roadmap_feedback_ledger_path(plans_dir, _SLUG)
    ledger = load_ledger(ledger_path)
    source = roadmap_candidate_run._load_resolved_version(
        plans_dir=plans_dir, slug=_SLUG, version_id=candidate.version_id
    )
    filed = ReviewerFeedbackGroup(
        predecessor_version_id=candidate.version_id,
        items=(_batch_item(source, item_id, "entity-order"),),
    )
    ledger_path.write_bytes(
        render_ledger(
            ledger.model_copy(update={"reviewer_feedback_groups": (*ledger.reviewer_feedback_groups, filed)})
        )
    )


def _store_stack(tmp_path, monkeypatch, routes):
    """root -> one batch candidate per entry of `routes` ("structural" | "presentation-only"), oldest first.

    Built by the runner alone: each hop is a plain `_run_batch` over the active candidate, and every hop's
    stored route is asserted, so a stack that was not built as named fails here. At most one hop is
    structural.
    """
    assert routes.count("structural") <= 1
    root, _resolved = _seed_batch_ledger(tmp_path, monkeypatch)
    hops = []
    for number, route in enumerate(routes):
        if number and route == "structural":
            _file_feedback_against_candidate(tmp_path, hops[-1], f"filed-against-hop-{number}")
        stored = _run_batch(tmp_path, _stack_hop_delta(number, route))
        assert stored.outcome == "stored", stored.detail
        assert stored.candidate is not None
        assert stored.candidate.evidence.operation_classification is (
            _STRUCTURAL if route == "structural" else _PRESENTATION_ONLY
        )
        hops.append(stored.candidate)
    return root, tuple(hops)


def _stack_route(tmp_path, *, tip_version_id: str, root_version_id: str | None):
    return roadmap_candidate_run.candidate_stack_route(
        plans_dir=tmp_path / "plans", slug=_SLUG,
        tip_version_id=tip_version_id, root_version_id=root_version_id,
    )


def test_stack_route_of_the_root_itself_is_empty_and_reads_nothing(tmp_path) -> None:
    """The root is never a hop, so its stored route (or absence of one) is never read: an id that
    names no stored version, in a plans dir that holds nothing, still yields an empty stack."""
    route = _stack_route(tmp_path, tip_version_id="a" * 64, root_version_id="a" * 64)

    assert route.hops == ()
    assert route.is_structural is False
    assert not (tmp_path / "plans").exists()


def test_stack_route_with_no_recorded_root_is_empty_not_underivable(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Selector-era evidence records no root, so it has no unpromoted stack: an empty answer that is
    distinct from underivable, which the same tip under a root it does not reach would be."""
    candidate = _store_selector_candidate_then_seed_ledger(tmp_path, monkeypatch)
    assert candidate.evidence.root_version_id is None

    route = _stack_route(tmp_path, tip_version_id=candidate.version_id, root_version_id=None)

    assert route.hops == ()
    assert route.is_structural is False
    with pytest.raises(roadmap_candidate_run.CandidateProposalError):
        _stack_route(tmp_path, tip_version_id=candidate.version_id, root_version_id="e" * 64)


def test_hops_are_ordered_oldest_first_end_at_the_tip_and_exclude_the_root(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stack view reads this order, so it is fixed: lowest unpromoted candidate first, tip last."""
    root, stored = _store_stack(
        tmp_path, monkeypatch, ("presentation-only",) * 3
    )

    route = _stack_route(tmp_path, tip_version_id=stored[-1].version_id, root_version_id=root.record.version_id)

    assert tuple(hop.version_id for hop in route.hops) == tuple(hop.version_id for hop in stored)
    assert root.record.version_id not in {hop.version_id for hop in route.hops}


def test_a_structural_hop_below_a_presentation_only_tip_makes_the_stack_structural(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reported defect's shape: the tip's own route is presentation-only, yet the stack it
    carries into the head includes a structural change from the hop below it."""
    root, (structural, tip) = _store_stack(
        tmp_path, monkeypatch, ("structural", "presentation-only")
    )
    assert tip.evidence.operation_classification is _PRESENTATION_ONLY

    route = _stack_route(tmp_path, tip_version_id=tip.version_id, root_version_id=root.record.version_id)

    assert route.is_structural is True
    assert tuple(hop.version_id for hop in route.hops) == (structural.version_id, tip.version_id)


@pytest.mark.parametrize(
    ("routes", "expected"),
    (
        pytest.param(("structural", "presentation-only", "presentation-only"), True, id="bottom"),
        pytest.param(("presentation-only", "structural", "presentation-only"), True, id="middle"),
        pytest.param(("presentation-only", "presentation-only", "structural"), True, id="top"),
        pytest.param(("presentation-only", "presentation-only", "presentation-only"), False, id="none"),
    ),
)
def test_any_hop_position_counts_and_an_all_presentation_stack_is_not_structural(
    tmp_path, monkeypatch: pytest.MonkeyPatch, routes: tuple[str, ...], expected: bool
) -> None:
    """A check of only the tip, or only the lowest hop, passes two of the three structural positions."""
    root, stored = _store_stack(tmp_path, monkeypatch, routes)

    route = _stack_route(tmp_path, tip_version_id=stored[-1].version_id, root_version_id=root.record.version_id)

    assert len(route.hops) == len(routes)
    assert route.is_structural is expected


@pytest.mark.parametrize(
    ("tip_route", "expected"),
    (("presentation-only", False), ("structural", True)),
)
def test_a_hop_with_no_stored_route_contributes_nothing_in_either_direction(
    tmp_path, monkeypatch: pytest.MonkeyPatch, tip_route: str, expected: bool
) -> None:
    """Legacy evidence and an answered replacement store no route. Absence is neither structural nor
    a reason to refuse, and never a reason to read the stack as safe: it stays a hop and changes
    neither answer."""
    root, (routeless, tip) = _store_stack(
        tmp_path, monkeypatch, ("presentation-only", tip_route)
    )
    roadmap_candidate_run.candidate_evidence_path(tmp_path / "plans", _SLUG, routeless.version_id).write_bytes(
        roadmap_candidate_run.render_candidate_evidence(
            routeless.evidence.model_copy(update={"normalized_operations": None, "operation_classification": None})
        )
    )

    route = _stack_route(tmp_path, tip_version_id=tip.version_id, root_version_id=root.record.version_id)

    assert tuple(hop.version_id for hop in route.hops) == (routeless.version_id, tip.version_id)
    assert route.hops[0].evidence.operation_classification is None
    assert route.is_structural is expected


def test_the_root_hops_own_structural_route_is_never_counted(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A previously promoted structural candidate can be the recorded root of the next stack; its
    route was settled by that promotion. Declaring it the root excludes it, while the same tip over
    the enrolled root still counts it."""
    enrolled_root, (structural, tip) = _store_stack(
        tmp_path, monkeypatch, ("structural", "presentation-only")
    )

    above_the_structural_root = _stack_route(
        tmp_path, tip_version_id=tip.version_id, root_version_id=structural.version_id
    )
    above_the_enrolled_root = _stack_route(
        tmp_path, tip_version_id=tip.version_id, root_version_id=enrolled_root.record.version_id
    )

    assert tuple(hop.version_id for hop in above_the_structural_root.hops) == (tip.version_id,)
    assert above_the_structural_root.is_structural is False
    assert above_the_enrolled_root.is_structural is True


def test_stack_route_never_reads_the_current_head_or_the_active_pointer(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The answer must be the same before promotion, after it, and during recovery, so it depends only
    on the two ids passed in; the head and the admission pointer move with promotion."""
    root, (_structural, tip) = _store_stack(
        tmp_path, monkeypatch, ("structural", "presentation-only")
    )
    baseline = _stack_route(tmp_path, tip_version_id=tip.version_id, root_version_id=root.record.version_id)

    def refuse_to_read(**_kwargs):
        pytest.fail("the stack route read the accepted head or the candidate admission pointer")

    monkeypatch.setattr(roadmap_candidate_run, "load_accepted_version", refuse_to_read)
    monkeypatch.setattr(roadmap_versions, "load_accepted_version", refuse_to_read)
    monkeypatch.setattr(roadmap_candidate_run, "load_candidate_admission", refuse_to_read)
    route = _stack_route(tmp_path, tip_version_id=tip.version_id, root_version_id=root.record.version_id)

    assert tuple(hop.version_id for hop in route.hops) == tuple(hop.version_id for hop in baseline.hops)
    assert route.is_structural is baseline.is_structural is True


@pytest.mark.parametrize(
    ("variant", "detail"),
    (
        pytest.param("deleted-lower-hop", "unreadable", id="deleted-lower-hop"),
        pytest.param("forged-lower-hop-route", "route does not match its stored operations", id="forged-lower-hop-route"),
        pytest.param("wrong-declared-root", "trace to its declared root", id="wrong-declared-root"),
        pytest.param("unknown-tip", "unreadable", id="unknown-tip"),
    ),
)
def test_an_unreadable_hop_makes_the_stack_underivable_and_is_never_read_as_not_structural(
    tmp_path, monkeypatch: pytest.MonkeyPatch, variant: str, detail: str
) -> None:
    """Every variant refuses. A silent fallback to "not structural" would let a promotion finish
    without its seed effect. The forged variant leaves the tip loading cleanly, so it fails only if
    each hop, not just the tip, is loaded and validated."""
    root, first, second = _store_two_hop_chain(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    tip_id, root_id = second.version_id, root.record.version_id
    if variant == "deleted-lower-hop":
        shutil.rmtree(version_directory_path(plans_dir, _SLUG, first.version_id))
    elif variant == "forged-lower-hop-route":
        _edit_stored_evidence(tmp_path, first, lambda data: data.update(operation_classification="structural"))
    elif variant == "wrong-declared-root":
        root_id = "e" * 64
    else:
        tip_id = "d" * 64

    with pytest.raises(roadmap_candidate_run.CandidateProposalError, match=detail):
        _stack_route(tmp_path, tip_version_id=tip_id, root_version_id=root_id)


# --------------------------------------------------------------------------
# correct-prose: persistence and replay against the bound predecessor
# --------------------------------------------------------------------------

_ORDER_BLOCK = "entity-order is the customer order.\n"
_CORRECTION_DOMAIN_BODY = f"{_ORDER_BLOCK}\nentity-customer is a buyer.\n"
_CORRECTED_ORDER_BLOCK = "entity-order is the corrected order.\n"
_ADD_INVOICE_OPERATION = {
    "op": "add-row", "feedback_id": "batch-one", "artifact_key": "domain", "row_type": "entities",
    "row": {
        "id": "entity-invoice", "name": "Invoice",
        "fields": [{"name": "order", "type": "reference", "entity_id": "entity-order"}],
    },
    "prose_amendment": {"row_id": "entity-invoice", "fragment": "Describe entity-invoice."},
}


def _issued_order_span_id(tmp_path) -> str:
    resolved = load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG)
    ledger = load_ledger(roadmap_feedback_ledger_path(tmp_path / "plans", _SLUG))
    capsule = build_candidate_context(resolved, None, ledger).capsule
    (span,) = [
        span for member in capsule.full_members for span in member.source_spans if _ORDER_BLOCK in span.text
    ]
    return span.span_id


def _correction_operation(span_id: str) -> dict:
    return {
        "op": "correct-prose", "feedback_id": "batch-one", "artifact_key": "domain",
        "span_id": span_id, "replacement": _CORRECTED_ORDER_BLOCK,
    }


def _correction_delta(tmp_path, *, with_add_row: bool = False) -> dict:
    operations = [_correction_operation(_issued_order_span_id(tmp_path))]
    if with_add_row:
        operations.append(_ADD_INVOICE_OPERATION)
    return {
        "operations": operations,
        "responses": [{"item_id": "batch-one", "response": "Done."}],
        "derived_feedback": [],
    }


def _seed_correction_ledger(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _enroll(tmp_path, _CORRECTION_DOMAIN_BODY)
    _write_open_item_ledger(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)


def _store_correction_candidate(tmp_path, monkeypatch: pytest.MonkeyPatch, *, with_add_row: bool = False):
    _seed_correction_ledger(tmp_path, monkeypatch)
    stored = _run_batch(tmp_path, _correction_delta(tmp_path, with_add_row=with_add_row))
    assert stored.outcome == "stored", stored.detail
    assert stored.candidate is not None
    return stored.candidate


def _source_of(tmp_path):
    return load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG)


def test_stored_correction_candidate_replays_to_its_stored_artifact_bytes(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = _store_correction_candidate(tmp_path, monkeypatch)

    reloaded = _reload_stored_candidate(tmp_path, candidate)
    roadmap_candidate_run._require_reproducible_batch_operations(reloaded, _source_of(tmp_path))

    assert [type(operation) for operation in reloaded.evidence.normalized_operations] == [
        roadmap_candidate.CandidateCorrectProse
    ]
    assert reloaded.evidence.operation_classification is roadmap_candidate.CandidateOperationClassification.STRUCTURAL
    assert _CORRECTED_ORDER_BLOCK.encode() in reloaded.content.artifact_bytes[0]
    assert _ORDER_BLOCK.encode() not in reloaded.content.artifact_bytes[0]


def test_correction_replays_before_add_row_appends_in_the_contract_order(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = _store_correction_candidate(tmp_path, monkeypatch, with_add_row=True)

    reloaded = _reload_stored_candidate(tmp_path, candidate)
    roadmap_candidate_run._require_reproducible_batch_operations(reloaded, _source_of(tmp_path))

    domain_text = reloaded.content.artifact_bytes[0].decode()
    assert domain_text.index(_CORRECTED_ORDER_BLOCK) < domain_text.index("Describe entity-invoice.")


def test_tampered_correction_text_is_refused_on_replay(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    candidate = _store_correction_candidate(tmp_path, monkeypatch)
    _edit_stored_evidence(
        tmp_path,
        candidate,
        lambda data: data["normalized_operations"][0].update(replacement="entity-order is forged.\n"),
    )

    with pytest.raises(roadmap_candidate_run.CandidateProposalError):
        _reload_stored_candidate(tmp_path, candidate)


def test_correction_with_a_span_the_capsule_never_issued_is_refused_on_replay(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = _store_correction_candidate(tmp_path, monkeypatch)
    _edit_stored_evidence(
        tmp_path, candidate, lambda data: data["normalized_operations"][0].update(span_id="span-never-issued")
    )

    with pytest.raises(roadmap_candidate_run.CandidateProposalError, match="exceed stored reviewer authority"):
        _reload_stored_candidate(tmp_path, candidate)


def test_correction_against_a_changed_predecessor_body_is_refused(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = _store_correction_candidate(tmp_path, monkeypatch)
    reloaded = _reload_stored_candidate(tmp_path, candidate)
    artifacts, predecessor_bytes = roadmap_candidate._parse_predecessor_artifacts(_source_of(tmp_path), STAGES)
    drifted = {**artifacts, "domain": replace(artifacts["domain"], body="entity-order was rewritten.\n")}
    monkeypatch.setattr(
        roadmap_candidate, "_parse_predecessor_artifacts", lambda *_args, **_kwargs: (drifted, predecessor_bytes)
    )

    with pytest.raises(roadmap_candidate_run.CandidateProposalError):
        roadmap_candidate_run._require_reproducible_batch_operations(reloaded, _source_of(tmp_path))


def test_correction_operations_round_trip_through_the_reparse_wire_form(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = _store_correction_candidate(tmp_path, monkeypatch)
    stored = candidate.evidence.normalized_operations

    reparsed = parse_candidate_delta(
        json.dumps({"operations": roadmap_candidate._operations_wire_for_reparse(stored)})
    )

    assert reparsed.operations == stored


def test_legacy_candidate_without_route_evidence_still_loads_unchanged(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Carve-out: both route fields None returns early, so pre-route candidates replay as before."""
    candidate = _store_correction_candidate(tmp_path, monkeypatch)
    legacy = replace(
        candidate,
        evidence=candidate.evidence.model_copy(
            update={"normalized_operations": None, "operation_classification": None}
        ),
    )

    assert roadmap_candidate_run._require_reproducible_batch_operations(legacy, _source_of(tmp_path)) is None


def test_selector_era_candidate_never_reaches_correction_replay(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    stored = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG, _SELECTOR, repo_root=tmp_path, plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _delta_response()),
    )
    assert stored.candidate is not None

    def forbid_replay(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("selector-era candidates stay on the non-batch branch")

    monkeypatch.setattr(roadmap_candidate_run, "_require_reproducible_batch_operations", forbid_replay)

    reloaded = _reload_stored_candidate(tmp_path, stored.candidate)

    assert reloaded.evidence.normalized_operations is None


def test_interrupted_correction_publication_leaves_no_partial_candidate(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_correction_ledger(tmp_path, monkeypatch)
    delta = _correction_delta(tmp_path)
    real_publish = roadmap_candidate_run.publish_roadmap_generation

    def interrupted(*_args: object, **_kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(roadmap_candidate_run, "publish_roadmap_generation", interrupted)
    first = _run_batch(tmp_path, delta)
    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=tmp_path / "plans", slug=_SLUG)

    assert first.outcome == "interrupted"
    assert first.candidate is None
    assert admission is None or admission.candidate_version_id is None

    monkeypatch.setattr(roadmap_candidate_run, "publish_roadmap_generation", real_publish)
    second = _run_batch(tmp_path, delta)

    assert second.outcome == "stored", second.detail
    assert second.candidate is not None
    reloaded = _reload_stored_candidate(tmp_path, second.candidate)
    roadmap_candidate_run._require_reproducible_batch_operations(reloaded, _source_of(tmp_path))


def _stored_capsule_with_row(tmp_path, *, row_type: str, row_id: str, wire: object):
    """A capsule as JSON admission loading leaves it: the full member's row is its stored wire dict."""
    _enroll(tmp_path)
    predecessor = load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG)
    assert predecessor is not None
    capsule = build_candidate_context(predecessor, _SELECTOR).capsule
    member = capsule.full_members[0]
    stored = member.model_copy(
        update={
            "identity": member.identity.model_copy(update={"row_type": row_type, "row_id": row_id}),
            "row": wire,
        }
    )
    return capsule.model_copy(update={"full_members": (stored,)})


def _decision_wire(**overrides: object) -> dict[str, object]:
    row = DecisionRow(
        "decision-cart", "server cart", (), "one source of truth", "entity-order", DecisionStatus.SETTLED
    )
    return {**roadmap_candidate._wire_value(row), **overrides}


@pytest.mark.parametrize(
    "wire",
    [
        pytest.param(_decision_wire(), id="authored-source-null"),
        pytest.param(
            _decision_wire(source="00-prior.md", rationale=None, rejected_alternatives=[]), id="inherited"
        ),
    ],
)
def test_stored_decision_rows_restore_although_a_model_delta_may_not_carry_source(tmp_path, wire) -> None:
    """Every stored DecisionRow carries `source`; restoring it must not use the model-delta parser,
    which keeps rejecting `source` (pinned by the unknown-field prompt test above)."""
    capsule = _stored_capsule_with_row(tmp_path, row_type="DecisionRow", row_id="decision-cart", wire=wire)

    restored = roadmap_candidate_run._hydrate_capsule(capsule).full_members[0].row

    assert isinstance(restored, DecisionRow)
    assert roadmap_candidate._wire_value(restored) == wire
    with pytest.raises(roadmap_candidate.CandidateDeltaError, match="unknown-field source"):
        roadmap_candidate._parse_stage_row("decisions", wire)


@pytest.mark.parametrize("source", [None, "00-prior.md"], ids=["authored", "inherited"])
def test_decision_row_survives_the_persisted_evidence_round_trip(tmp_path, source) -> None:
    """Evidence is written with `exclude_none=True` and reloaded as plain dicts; the typed Decision row
    must come back from that persisted form, not only from a hand-built wire dict."""
    row = DecisionRow(
        "decision-cart", "server cart", (), None if source else "why", "entity-order",
        DecisionStatus.SETTLED, source,
    )
    typed = _stored_capsule_with_row(tmp_path, row_type="DecisionRow", row_id="decision-cart", wire=row)
    reloaded = type(typed).model_validate_json(typed.model_dump_json(exclude_none=True))

    assert isinstance(reloaded.full_members[0].row, dict)
    assert roadmap_candidate_run._hydrate_capsule(reloaded).full_members[0].row == row


@pytest.mark.parametrize(
    ("row_id", "wire", "reason"),
    [
        ("decision-cart", _decision_wire(rationale=None), "requires a rationale unless inherited"),
        ("decision-cart", _decision_wire(source=7), "must be a string"),
        ("decision-cart", {**_decision_wire(), "extra": 1}, "unknown-field other"),
        ("decision-cart", {k: v for k, v in _decision_wire().items() if k != "source"}, "missing-field source"),
        ("decision-other", _decision_wire(), "does not match its identity"),
    ],
    ids=["authored-without-rationale", "non-text-source", "extra-field", "missing-source", "identity-mismatch"],
)
def test_malformed_stored_decision_rows_refuse_with_their_location(tmp_path, row_id, wire, reason) -> None:
    capsule = _stored_capsule_with_row(tmp_path, row_type="DecisionRow", row_id=row_id, wire=wire)

    with pytest.raises(roadmap_candidate_run.CandidateProposalError) as excinfo:
        roadmap_candidate_run._hydrate_capsule(capsule)

    assert f"stored capsule row domain {row_id}" in str(excinfo.value)
    assert reason in str(excinfo.value)


def test_stored_non_decision_rows_still_restore_through_the_round_trip_check(tmp_path) -> None:
    _enroll(tmp_path)
    predecessor = load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG)
    assert predecessor is not None
    capsule = build_candidate_context(predecessor, _SELECTOR).capsule
    stored = capsule.model_copy(
        update={
            "full_members": tuple(
                member.model_copy(update={"row": roadmap_candidate._wire_value(member.row)})
                for member in capsule.full_members
            )
        }
    )

    restored = roadmap_candidate_run._hydrate_capsule(stored)

    assert [member.row for member in restored.full_members] == [member.row for member in capsule.full_members]


# --- INDEX.md refresh after every version-store change -------------------------------------------


def _index_path(tmp_path):
    from plan_tool.roadmap_artifacts import roadmap_dir
    from plan_tool.roadmap_index import INDEX_FILENAME

    return roadmap_dir(tmp_path / "plans", _SLUG) / INDEX_FILENAME


def _fresh_index_render(tmp_path) -> str:
    from plan_tool.roadmap_index import (
        collect_index_rows,
        collect_index_stack_lines,
        render_roadmap_index,
    )

    head_version_id, rows = collect_index_rows(tmp_path / "plans", _SLUG)
    stack_lines = collect_index_stack_lines(tmp_path / "plans", _SLUG, head_version_id)
    return render_roadmap_index(_SLUG, head_version_id, rows, stack_lines)


def _index_row_for(tmp_path, version_id: str) -> str:
    (row,) = [
        line for line in _index_path(tmp_path).read_text().splitlines()
        if line.startswith(f"| `{version_id[:8]}`")
    ]
    return row


def test_index_exists_and_lists_the_candidate_after_storing_a_proposal(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _root, candidate = _store_first_batch_candidate(tmp_path, monkeypatch)

    assert _index_path(tmp_path).read_text() == _fresh_index_render(tmp_path)
    assert "| active |" in _index_row_for(tmp_path, candidate.version_id)


def test_index_status_changes_after_terminal_resolution(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _root, candidate = _store_first_batch_candidate(tmp_path, monkeypatch)

    result = roadmap_candidate_review.reject_candidate_review(
        _SLUG, candidate.version_id, plans_dir=tmp_path / "plans"
    )

    assert result.outcome == "stored"
    assert "| rejected |" in _index_row_for(tmp_path, candidate.version_id)
    assert _index_path(tmp_path).read_text() == _fresh_index_render(tmp_path)


def test_index_marks_superseded_candidate_after_replacement(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _root, hops = _store_stack(tmp_path, monkeypatch, ["presentation-only", "presentation-only"])

    assert "| superseded |" in _index_row_for(tmp_path, hops[0].version_id)
    assert "| active |" in _index_row_for(tmp_path, hops[1].version_id)
    assert _index_path(tmp_path).read_text() == _fresh_index_render(tmp_path)


def test_index_is_replaced_whole_not_patched(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A stale or hand-edited INDEX.md is never read or merged: the next commit overwrites every byte."""
    _seed_batch_ledger(tmp_path, monkeypatch)
    _index_path(tmp_path).write_text("junk that must not survive\n")

    stored = _run_batch(tmp_path, _FIRST_BATCH_DELTA)

    assert stored.outcome == "stored"
    assert _index_path(tmp_path).read_text() == _fresh_index_render(tmp_path)
    assert "junk" not in _index_path(tmp_path).read_text()


def test_index_write_failure_warns_and_never_fails_the_command(
    tmp_path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The index is a human aid: a raising write is one stderr warning and the command's result is unchanged."""
    from plan_tool import roadmap

    _seed_batch_ledger(tmp_path, monkeypatch)

    def broken(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(roadmap, "write_roadmap_index", broken)

    stored = _run_batch(tmp_path, _FIRST_BATCH_DELTA)

    warnings = [line for line in capsys.readouterr().err.splitlines() if "INDEX.md" in line]
    assert stored.outcome == "stored"
    assert len(warnings) == 1
    assert "disk full" in warnings[0]


def test_failed_index_write_never_rolls_back_the_committed_version(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from plan_tool import roadmap

    _seed_batch_ledger(tmp_path, monkeypatch)
    monkeypatch.setattr(
        roadmap, "write_roadmap_index", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    stored = _run_batch(tmp_path, _FIRST_BATCH_DELTA)

    assert stored.candidate is not None
    reloaded = roadmap_candidate_run.load_stored_candidate_proposal(
        plans_dir=tmp_path / "plans", slug=_SLUG, candidate_version_id=stored.candidate.version_id
    )
    assert reloaded.record.version_id == stored.candidate.version_id
    assert load_accepted_version(plans_dir=tmp_path / "plans", slug=_SLUG) is not None
    assert not _index_path(tmp_path).exists()


def test_index_is_not_a_generation_member(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """INDEX.md is written after the publish, so no pending-generation journal can replay or delete it."""
    _seed_batch_ledger(tmp_path, monkeypatch)
    published = []
    real_publish = roadmap_candidate_run.publish_roadmap_generation

    def spy(generation, **kwargs):
        published.append(generation)
        return real_publish(generation, **kwargs)

    monkeypatch.setattr(roadmap_candidate_run, "publish_roadmap_generation", spy)

    assert _run_batch(tmp_path, _FIRST_BATCH_DELTA).outcome == "stored"

    assert published
    assert not any("INDEX" in member.relative_path for g in published for member in g.members)


_INDEX_PUBLISH_MODULES = (
    "roadmap.py",
    "roadmap_candidate_run.py",
    "roadmap_candidate_review.py",
    "roadmap_version_promotion.py",
    "roadmap_decision_settlement_enrolled.py",
)


def test_every_publish_call_site_is_followed_by_the_wrapper() -> None:
    """A new commit point added without `refresh_roadmap_index` in the same function fails here."""
    import ast
    from pathlib import Path

    package = Path(roadmap_candidate_run.__file__).parent
    missing = []
    for name in _INDEX_PUBLISH_MODULES:
        tree = ast.parse((package / name).read_text())
        for function in ast.walk(tree):
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            calls = {
                call.func.id
                for call in ast.walk(function)
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
            }
            if "publish_roadmap_generation" in calls and "refresh_roadmap_index" not in calls:
                missing.append(f"{name}:{function.name}")
    assert missing == []
