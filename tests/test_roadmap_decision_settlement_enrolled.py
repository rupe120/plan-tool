"""Tests for confirmed, enrolled decision-settlement execution."""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import get_args

import pytest

from plan_tool import roadmap_candidate, roadmap_candidate_review, roadmap_candidate_run
from plan_tool import roadmap_decision_settlement as decision_settlement_module
from plan_tool import roadmap_decision_settlement_enrolled as enrolled_module
from plan_tool import roadmap_revision_publish, roadmap_version_promotion
from plan_tool.cli.gitcommit import commit_receipt
from plan_tool.roadmap import STAGES
from plan_tool.roadmap_artifacts import (
    ComponentsArtifact,
    ConstraintsArtifact,
    DecisionRow,
    DecisionStatus,
    DomainArtifact,
    EntityRow,
    FeedbackRow,
    FeedbackState,
    FeedbackTarget,
    FeedbackTargetKind,
    PlansArtifact,
    RejectedAlternative,
    domain_path,
    RoadmapArtifactError,
    parse_domain_artifact,
    render_domain_artifact,
    roadmap_dir,
)
from plan_tool.roadmap_candidate_context import CandidateContextBatchCapsule, build_candidate_context
from plan_tool.roadmap_candidate_run import (
    candidate_admission_path,
    load_candidate_admission,
    new_terminal_resolution,
    render_candidate_terminal_resolution,
    run_initial_candidate_proposal,
    terminal_resolution_path,
)
from plan_tool.roadmap_decision_settlement import (
    build_decision_settlement_candidate,
    resolve_decision_settlement_selector,
)
from plan_tool.roadmap_decision_settlement_enrolled import (
    DECISION_SETTLEMENT_NO_REVIEW_LINEAGE_ID,
    decision_settlement_content_identity,
    respond_enrolled_decision_settlement,
    run_enrolled_decision_settlement,
)
from plan_tool.roadmap_decision_settlement_receipt import (
    DECISION_SETTLEMENT_RECEIPT_SUCCESS_OUTCOMES,
    DecisionSettlementReceiptOutcome,
    DecisionSettlementReceiptPublication,
    decision_settlement_receipt_proves_completion,
    parse_decision_settlement_receipt,
)
from plan_tool.roadmap_decision_settlement_run import (
    DecisionSettlementRunRefusal,
    DecisionSettlementRunResult,
)
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
from plan_tool.roadmap_impact_snapshot import RoadmapGateOutcome, RoadmapImpactSnapshotError
from plan_tool.roadmap_revision_publish import (
    pending_generation_path,
    publish_roadmap_generation,
    roadmap_writer_guard,
)
from plan_tool.roadmap_seed_state import seed_state_path
from plan_tool.roadmap_source_identity import (
    GenerationMember,
    PendingGeneration,
    load_pending_generation,
    render_pending_generation,
)
from plan_tool.roadmap_versions import (
    ROADMAP_VERSION_NAMESPACE_DIRNAME,
    ROADMAP_VERSION_SCHEMA_VERSION,
    INITIAL_EMPTY_REVIEW_LINEAGE_ID,
    AcceptedRoadmapHead,
    PreparedRoadmapVersion,
    RoadmapVersionContent,
    accepted_head_path,
    build_root_enrollment_generation,
    create_candidate_version,
    create_root_version,
    load_accepted_version,
    render_accepted_head,
    version_directory_path,
)


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "plan_tool" / "roadmap_decision_settlement_enrolled.py"
)
_SLUG = "demo"
_DOMAIN_STAGE = STAGES[0]
_GIT_TEMPLATE: Path | None = None


# --------------------------------------------------------------------------
# Fixture builders
# --------------------------------------------------------------------------


def _decision(
    id_: str = "decision-1",
    *,
    anchor: str = "entity-order",
    status: DecisionStatus = DecisionStatus.PENDING,
    source: str | None = None,
) -> DecisionRow:
    return DecisionRow(
        id=id_,
        chosen_option="Use the order-centric model.",
        rejected_alternatives=(
            ()
            if source is not None
            else (RejectedAlternative("Use a cart-centric model.", "Rejected for clarity."),)
        ),
        rationale=None if source is not None else "Keeps the domain simple.",
        anchor=anchor,
        status=status,
        source=source,
    )


def _feedback(
    id_: str = "feedback-1",
    *,
    target: FeedbackTarget | None = None,
    request: str = "Confirm the order-centric model.",
    state: FeedbackState = FeedbackState.OPEN,
    proposed_response: str | None = None,
) -> FeedbackRow:
    return FeedbackRow(
        id=id_,
        target=target if target is not None else FeedbackTarget(FeedbackTargetKind.ROW, "decision-1"),
        request=request,
        state=state,
        proposed_response=proposed_response,
    )


def _domain(
    *,
    entities: tuple[EntityRow, ...] = (EntityRow("entity-order", "Order", ()),),
    decisions: tuple[DecisionRow, ...] | None = None,
    feedback: tuple[FeedbackRow, ...] | None = None,
    body: str = "# Domain\n",
) -> DomainArtifact:
    return DomainArtifact(
        entities=entities,
        business_rules=(),
        workflows=(),
        decisions=(_decision(),) if decisions is None else decisions,
        body=body,
        feedback=(_feedback(),) if feedback is None else feedback,
    )


def _other_stage_artifacts() -> tuple[ConstraintsArtifact, ComponentsArtifact, PlansArtifact]:
    return (
        ConstraintsArtifact(dispositions=(), constraints=(), decisions=(), body="constraints\n"),
        ComponentsArtifact(
            system_patterns=(), component_patterns=(), components=(), decisions=(), body="components\n"
        ),
        PlansArtifact(plans=(), ordering=(), assumptions=(), decisions=(), body="plans\n"),
    )


def _prepared_root(domain: DomainArtifact | None = None) -> PreparedRoadmapVersion:
    artifacts = (domain if domain is not None else _domain(), *_other_stage_artifacts())
    artifact_bytes = tuple(
        stage.render(artifact).encode("utf-8") for stage, artifact in zip(STAGES, artifacts)
    )
    return _prepared_root_from_bytes(artifact_bytes)


def _prepared_root_from_bytes(
    artifact_bytes: tuple[bytes, bytes, bytes, bytes], *, brief_bytes: bytes = b"Recorded brief\n"
) -> PreparedRoadmapVersion:
    return PreparedRoadmapVersion(
        record=create_root_version(
            roadmap_slug=_SLUG,
            brief_digest=hashlib.sha256(brief_bytes).hexdigest(),
            artifact_digests=tuple(hashlib.sha256(b).hexdigest() for b in artifact_bytes),
        ),
        content=RoadmapVersionContent(brief_bytes=brief_bytes, artifact_bytes=artifact_bytes),
    )


def _publish_root(plans_dir: Path, root: PreparedRoadmapVersion) -> None:
    with roadmap_writer_guard(plans_dir, _SLUG) as token:
        publish_roadmap_generation(
            build_root_enrollment_generation(root, plans_dir=plans_dir, slug=_SLUG),
            plans_dir=plans_dir,
            slug=_SLUG,
            writer_token=token,
        )


def _enroll(plans_dir: Path, domain: DomainArtifact | None = None) -> PreparedRoadmapVersion:
    root = _prepared_root(domain)
    _publish_root(plans_dir, root)
    return root


def _store_active_candidate_pair(plans_dir: Path, root: PreparedRoadmapVersion) -> str:
    """Install a step-5-shaped pointer without adding candidate test machinery."""
    candidate_id = "a" * 64
    admission = roadmap_candidate_run.CandidateProposalAdmission(
        schema_version=1,
        roadmap_slug=_SLUG,
        predecessor_version_id=root.record.version_id,
        expansion_available=False,
        candidate_version_id=candidate_id,
        root_version_id=root.record.version_id,
        active_candidate_version_id=candidate_id,
    )
    path = candidate_admission_path(plans_dir, _SLUG)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(roadmap_candidate_run.render_candidate_admission(admission))
    return candidate_id


_BATCH_DELTA = {
    "operations": [],
    "responses": [{"item_id": "batch-order", "response": "Rename the entity."}],
    "derived_feedback": [{"context_id": "derived-order", "content": "Check naming."}],
}


def _open_ledger_item(resolved, item_id: str, row_id: str, *, request: str = "Review this row."):
    target = LedgerTarget(artifact_key="domain", kind=FeedbackTargetKind.ROW, row_id=row_id)
    return ReviewerFeedbackItem(
        item_id=item_id,
        target=target,
        request=request,
        state=ReviewerItemState.OPEN,
        submitted_against_version_id=resolved.record.version_id,
        target_fingerprint=target_fingerprint(resolved, target),
    )


def _add_open_ledger_item(plans_dir: Path, item: ReviewerFeedbackItem) -> None:
    """Append one item to the ledger, creating it (ledger-native) when absent."""
    path = roadmap_feedback_ledger_path(plans_dir, _SLUG)
    ledger = (
        load_ledger(path)
        if path.exists()
        else RoadmapFeedbackLedger(
            schema_version=1,
            roadmap_slug=_SLUG,
            ledger_state=LedgerState.LEDGER_NATIVE,
            reviewer_feedback_groups=(),
            derived_context=(),
        )
    )
    groups = list(ledger.reviewer_feedback_groups)
    for index, group in enumerate(groups):
        if group.predecessor_version_id == item.submitted_against_version_id:
            groups[index] = group.model_copy(update={"items": (*group.items, item)})
            break
    else:
        groups.append(
            ReviewerFeedbackGroup(
                predecessor_version_id=item.submitted_against_version_id, items=(item,)
            )
        )
    path.write_bytes(
        render_ledger(ledger.model_copy(update={"reviewer_feedback_groups": tuple(groups)}))
    )


def _store_real_active_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[PreparedRoadmapVersion, roadmap_candidate_run.StoredCandidateProposal]:
    """Store a genuine ledger-batch candidate through step 5's own runner.

    Unlike ``_store_active_candidate_pair`` this leaves a candidate version that
    ``load_stored_candidate_proposal`` can read. It also leaves a second open
    item (the settlement evidence) added *after* storage: storage moves the
    admitted item to ``awaiting-review``, so it can no longer be evidence.
    """
    root = _enroll(tmp_path)
    resolved = load_accepted_version(plans_dir=tmp_path, slug=_SLUG)
    _add_open_ledger_item(tmp_path, _open_ledger_item(resolved, "batch-order", "entity-order"))
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    stored = run_initial_candidate_proposal(
        _SLUG,
        "domain:ignored-by-the-ledger-batch-route",
        repo_root=tmp_path,
        plans_dir=tmp_path,
        invoker=lambda _prompt: (0, json.dumps(_BATCH_DELTA)),
    )
    assert stored.outcome == "stored"
    assert stored.candidate is not None
    _add_open_ledger_item(
        tmp_path,
        _open_ledger_item(
            resolved, "feedback-1", "decision-1", request="Confirm the order-centric model."
        ),
    )
    return root, stored.candidate


def _child_version(predecessor: PreparedRoadmapVersion) -> PreparedRoadmapVersion:
    """Build an ordinary child candidate with the predecessor's own content.

    Bypasses the whole model-authored review chain: this is scaffolding for
    simulating what promotion leaves on the accepted head, not a test of
    promotion itself.
    """
    child_record = create_candidate_version(
        roadmap_slug=_SLUG,
        predecessor_version_id=predecessor.record.version_id,
        content_identity="b" * 64,
        review_lineage_identity="c" * 64,
        brief_digest=predecessor.record.brief_digest,
        artifact_digests=tuple(member.digest for member in predecessor.record.artifact_members),
    )
    return PreparedRoadmapVersion(record=child_record, content=predecessor.content)


def _promote_head_to_child(plans_dir: Path, predecessor: PreparedRoadmapVersion) -> str:
    """Leave the accepted head naming a child version, the state promotion leaves.

    Safe to call standalone, under its own writer lease.
    """
    from plan_tool.roadmap_versions import stored_version_members

    prepared_child = _child_version(predecessor)
    root = roadmap_dir(plans_dir, _SLUG)
    version_dir = version_directory_path(plans_dir, _SLUG, prepared_child.record.version_id)
    members = [
        GenerationMember((version_dir / m.member_name).relative_to(root).as_posix(), None, m.data)
        for m in stored_version_members(prepared_child)
    ]
    selector_path = accepted_head_path(plans_dir, _SLUG)
    old_selector_bytes = selector_path.read_bytes()
    new_head = AcceptedRoadmapHead(
        schema_version=ROADMAP_VERSION_SCHEMA_VERSION,
        roadmap_slug=_SLUG,
        version_id=prepared_child.record.version_id,
    )
    members.append(
        GenerationMember(
            selector_path.relative_to(root).as_posix(), old_selector_bytes, render_accepted_head(new_head)
        )
    )
    with roadmap_writer_guard(plans_dir, _SLUG) as token:
        publish_roadmap_generation(
            PendingGeneration(kind="test-child-promotion", members=tuple(members)),
            plans_dir=plans_dir,
            slug=_SLUG,
            writer_token=token,
        )
    return prepared_child.record.version_id


def _swap_head_to_child_without_a_new_lock(plans_dir: Path, predecessor: PreparedRoadmapVersion) -> str:
    """Simulate a concurrent head move landing while this process already
    holds the writer lock (e.g. inside a receipt-commit callback) — plain
    writes, no nested ``roadmap_writer_guard``/``publish_roadmap_generation``,
    since re-acquiring the same advisory lock from the same process deadlocks.
    """
    from plan_tool.roadmap_versions import stored_version_members

    prepared_child = _child_version(predecessor)
    version_dir = version_directory_path(plans_dir, _SLUG, prepared_child.record.version_id)
    version_dir.mkdir(parents=True, exist_ok=True)
    for member in stored_version_members(prepared_child):
        (version_dir / member.member_name).write_bytes(member.data)
    new_head = AcceptedRoadmapHead(
        schema_version=ROADMAP_VERSION_SCHEMA_VERSION,
        roadmap_slug=_SLUG,
        version_id=prepared_child.record.version_id,
    )
    accepted_head_path(plans_dir, _SLUG).write_bytes(render_accepted_head(new_head))
    return prepared_child.record.version_id


def _delta_response() -> str:
    payload = {
        "delta": {
            "operations": [
                {
                    "op": "replace-row",
                    "feedback_id": "feedback-1",
                    "artifact_key": "domain",
                    "row_type": "entities",
                    "row_id": "entity-order",
                    "row": {"id": "entity-order", "name": "Customer order", "fields": []},
                }
            ]
        }
    }
    return json.dumps(payload)


def _reject_admission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch | None) -> None:
    run_initial_candidate_proposal(
        _SLUG,
        "domain:feedback-1",
        repo_root=tmp_path,
        plans_dir=tmp_path,
        invoker=lambda _prompt: (0, "not json"),
    )


def _store_admission_awaiting_question(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    run_initial_candidate_proposal(
        _SLUG,
        "domain:feedback-1",
        repo_root=tmp_path,
        plans_dir=tmp_path,
        invoker=lambda _prompt: (0, _delta_response()),
    )


def _green_gates(_evidence, *, stages=STAGES):
    return tuple(RoadmapGateOutcome(stage, ()) for stage in stages)


def _evidence_dir(plans_dir: Path) -> Path:
    return roadmap_dir(plans_dir, _SLUG) / ".plan-tool" / "evidence" / "decision-settlements"


def _versions_dir(plans_dir: Path) -> Path:
    return roadmap_dir(plans_dir, _SLUG) / ROADMAP_VERSION_NAMESPACE_DIRNAME


# INDEX.md is a derived human aid rewritten by every committing command; these
# snapshots compare version-store state, not that file (covered in its own tests).
_INDEX_NAME = "INDEX.md"


def _snapshot_tree(root: Path) -> dict[str, bytes]:
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != _INDEX_NAME
    }


def _run(
    tmp_path: Path,
    *,
    decision: object = "domain:decision-1",
    evidence: object = "domain:feedback-1",
    confirmation: object = True,
    mode_rejected: bool = False,
    receipt_committer=None,
    stages=STAGES,
) -> DecisionSettlementRunResult:
    return run_enrolled_decision_settlement(
        _SLUG,
        decision,
        evidence,
        confirmation,
        plans_dir=tmp_path,
        stages=stages,
        mode_rejected=mode_rejected,
        receipt_committer=receipt_committer,
    )


@pytest.fixture(scope="session", autouse=True)
def _empty_git_template(tmp_path_factory: pytest.TempPathFactory):
    """Provide isolated settlement worktrees with local identity."""
    global _GIT_TEMPLATE
    root = tmp_path_factory.mktemp("settlement-git-template")
    for command in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "Test User"],
    ):
        subprocess.run(command, cwd=root, check=True, capture_output=True)
    _GIT_TEMPLATE = root / ".git"
    yield
    _GIT_TEMPLATE = None


@pytest.fixture(autouse=True)
def _writer_worktree(tmp_path: Path) -> None:
    """Give settlement lifecycle cases a controllable shared-history boundary."""
    assert _GIT_TEMPLATE is not None
    shutil.copytree(_GIT_TEMPLATE, tmp_path / ".git")


@pytest.fixture(autouse=True)
def _stub_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Real gate content isn't this module's concern; only its wiring is."""
    monkeypatch.setattr(enrolled_module, "check_complete_roadmap_gates", _green_gates)


# --------------------------------------------------------------------------
# Refusals before the lease
# --------------------------------------------------------------------------


@pytest.mark.parametrize("confirmation", (None, False, "yes"))
def test_missing_or_non_true_confirmation_refuses_before_any_filesystem_access(
    tmp_path: Path, confirmation: object
) -> None:
    result = _run(tmp_path, confirmation=confirmation)

    assert result.outcome == "preflight-rejected"
    assert result.status == 2
    assert result.refusal == "confirmation-required"
    assert not roadmap_revision_publish.roadmap_writer_lock_path(tmp_path, _SLUG).exists()
    assert not _evidence_dir(tmp_path).exists()


def test_mode_rejected_refuses_before_any_filesystem_access(tmp_path: Path) -> None:
    result = _run(tmp_path, mode_rejected=True)

    assert result.outcome == "preflight-rejected"
    assert result.refusal == "mode-rejected"
    assert not roadmap_revision_publish.roadmap_writer_lock_path(tmp_path, _SLUG).exists()


def test_invalid_slug_is_mode_rejected(tmp_path: Path) -> None:
    result = run_enrolled_decision_settlement(
        "nested/slug", "domain:decision-1", "domain:feedback-1", True, plans_dir=tmp_path
    )

    assert result.outcome == "preflight-rejected"
    assert result.refusal == "mode-rejected"


# --------------------------------------------------------------------------
# Lineage and recovery
# --------------------------------------------------------------------------


def test_roadmap_with_no_accepted_head_is_refused_before_recovery_and_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def recovery_is_unexpected(*_args: object, **_kwargs: object) -> None:
        pytest.fail("a roadmap with no accepted head must not run recovery")

    def build_is_unexpected(*_args: object, **_kwargs: object) -> None:
        pytest.fail("a roadmap with no accepted head must not build a settlement candidate")

    monkeypatch.setattr(enrolled_module, "recover_roadmap_publication", recovery_is_unexpected)
    monkeypatch.setattr(enrolled_module, "build_decision_settlement_candidate", build_is_unexpected)

    result = _run(tmp_path)

    assert result.outcome == "preflight-rejected"
    assert result.refusal == "no-published-version"


def test_invalid_accepted_head_is_write_failed_before_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selector_path = accepted_head_path(tmp_path, _SLUG)
    selector_path.parent.mkdir(parents=True, exist_ok=True)
    selector_path.write_bytes(b"not json")

    def recovery_is_unexpected(*_args: object, **_kwargs: object) -> None:
        pytest.fail("an invalid accepted head must not reach recovery")

    monkeypatch.setattr(enrolled_module, "recover_roadmap_publication", recovery_is_unexpected)

    result = _run(tmp_path)

    assert result.outcome == "write-failed"
    assert result.status == 1


@pytest.mark.parametrize(
    "attr, error_type",
    (
        (
            "build_decision_settlement_candidate",
            decision_settlement_module.DecisionSettlementSourceCorruptError,
        ),
        (
            "build_decision_settlement_receipt",
            enrolled_module.DecisionSettlementReceiptError,
        ),
        (
            "check_complete_roadmap_gates",
            RoadmapImpactSnapshotError,
        ),
    ),
)
def test_internal_consistency_errors_propagate_instead_of_becoming_a_generic_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, attr: str, error_type: type[Exception]
) -> None:
    """None is a plain ValueError: the runner's catch-all would otherwise
    fold any of them into a generic write-failed and discard the
    diagnostic — including a corrupt sibling artifact member surfaced only
    while building gate evidence from the whole accepted version."""
    _enroll(tmp_path)

    def boom(*_args: object, **_kwargs: object) -> None:
        raise error_type("boom")

    monkeypatch.setattr(enrolled_module, attr, boom)

    with pytest.raises(error_type):
        _run(tmp_path)


def test_corrupt_candidate_admission_record_propagates_instead_of_becoming_a_generic_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A CandidateProposalError from a corrupt admission record must not be
    folded into a generic write-failed by the runner's catch-all — this is
    the same swallowing-bug class as the source-corrupt and receipt errors
    above, reached through _admission_blocks_settlement instead."""
    _enroll(tmp_path)

    def boom(*_args: object, **_kwargs: object) -> None:
        raise roadmap_candidate_run.CandidateProposalError("boom")

    monkeypatch.setattr(enrolled_module, "load_candidate_admission", boom)

    with pytest.raises(roadmap_candidate_run.CandidateProposalError):
        _run(tmp_path)


def test_completed_settlement_journal_left_behind_is_dropped_and_the_retry_is_decision_not_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    captured: dict[str, PendingGeneration] = {}
    real_publish = enrolled_module.publish_roadmap_generation

    def _spy(generation: PendingGeneration, **kwargs: object):
        captured["generation"] = generation
        return real_publish(generation, **kwargs)

    monkeypatch.setattr(enrolled_module, "publish_roadmap_generation", _spy)

    first = _run(tmp_path)
    assert first.outcome == "settled"

    root = roadmap_dir(tmp_path, _SLUG)
    journal = pending_generation_path(root)
    assert not journal.exists()
    journal.write_bytes(render_pending_generation(captured["generation"]))
    journal_rel = journal.relative_to(root).as_posix()
    before = _snapshot_tree(root)

    second = _run(tmp_path)

    assert second.outcome == "preflight-rejected"
    assert second.refusal == "decision-not-pending"
    assert not journal.exists()
    after = _snapshot_tree(root)
    assert after == {k: v for k, v in before.items() if k != journal_rel}


def test_settlement_interrupted_mid_write_is_write_failed_and_the_retry_is_journal_unrecoverable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    real_write = roadmap_revision_publish.durable_write_bytes
    calls = {"count": 0}

    def _flaky(path: Path, data: bytes) -> None:
        calls["count"] += 1
        if calls["count"] == 4:  # the third version-storage member (record, brief, domain, ...)
            raise OSError("disk full")
        real_write(path, data)

    monkeypatch.setattr(roadmap_revision_publish, "durable_write_bytes", _flaky)

    first = _run(tmp_path)
    assert first.outcome == "write-failed"
    assert first.status == 1
    assert first.receipt_id is not None

    root = roadmap_dir(tmp_path, _SLUG)
    journal = pending_generation_path(root)
    assert journal.exists()
    before = _snapshot_tree(root)

    monkeypatch.setattr(roadmap_revision_publish, "durable_write_bytes", real_write)
    second = _run(tmp_path)

    assert second.outcome == "preflight-rejected"
    assert second.refusal == "journal-unrecoverable"
    assert journal.exists()
    assert _snapshot_tree(root) == before


def test_non_version_owned_journal_is_journal_unrecoverable(tmp_path: Path) -> None:
    _enroll(tmp_path)
    root = roadmap_dir(tmp_path, _SLUG)
    journal = pending_generation_path(root)
    journal_bytes = render_pending_generation(
        PendingGeneration(
            kind="stage-publication",
            members=(GenerationMember("some-file.md", b"old", b"new"),),
        )
    )
    journal.write_bytes(journal_bytes)

    result = _run(tmp_path)

    assert result.outcome == "preflight-rejected"
    assert result.refusal == "journal-unrecoverable"
    assert journal.read_bytes() == journal_bytes


# --------------------------------------------------------------------------
# Preflight wiring
# --------------------------------------------------------------------------


def _source_not_canonical_setup(tmp_path: Path) -> None:
    domain = _domain()
    canonical_text = _DOMAIN_STAGE.render(domain)
    presentation_bytes = canonical_text.encode("utf-8").replace(
        b"entities:\n", b"entities: # presentation\n", 1
    )
    other = tuple(
        stage.render(artifact).encode("utf-8")
        for stage, artifact in zip(STAGES[1:], _other_stage_artifacts())
    )
    _publish_root(tmp_path, _prepared_root_from_bytes((presentation_bytes, *other)))


def _missing_feedback_present_only_on_disk_setup(tmp_path: Path) -> None:
    _enroll(tmp_path, _domain(feedback=()))
    stage_path = domain_path(tmp_path, _SLUG)
    stage_path.parent.mkdir(parents=True, exist_ok=True)
    stage_path.write_text(render_domain_artifact(_domain()), encoding="utf-8")


def _closed_ledger_evidence_setup(tmp_path: Path) -> None:
    _enroll(tmp_path)
    resolved = load_accepted_version(plans_dir=tmp_path, slug=_SLUG)
    closed = _open_ledger_item(resolved, "feedback-1", "decision-1").model_copy(
        update={"state": ReviewerItemState.CLOSED}
    )
    _add_open_ledger_item(tmp_path, closed)


_PREFLIGHT_REFUSAL_CASES = {
    "malformed-decision-selector": (
        "domain-decision-1",
        "domain:feedback-1",
        lambda tmp_path: _enroll(tmp_path),
    ),
    "missing-decision": (
        "domain:decision-1",
        "domain:feedback-1",
        lambda tmp_path: _enroll(tmp_path, _domain(decisions=())),
    ),
    "inherited-decision": (
        "domain:decision-1",
        "domain:feedback-1",
        lambda tmp_path: _enroll(tmp_path, _domain(decisions=(_decision(source="constraints"),))),
    ),
    "decision-not-pending": (
        "domain:decision-1",
        "domain:feedback-1",
        lambda tmp_path: _enroll(tmp_path, _domain(decisions=(_decision(status=DecisionStatus.SETTLED),))),
    ),
    "feedback-not-targeting-decision": (
        "domain:decision-1",
        "domain:feedback-1",
        lambda tmp_path: _enroll(
            tmp_path, _domain(feedback=(_feedback(target=FeedbackTarget(FeedbackTargetKind.ARTIFACT)),))
        ),
    ),
    "empty-request": (
        "domain:decision-1",
        "domain:feedback-1",
        lambda tmp_path: _enroll(tmp_path, _domain(feedback=(_feedback(request="   "),))),
    ),
    "source-not-canonical": ("domain:decision-1", "domain:feedback-1", _source_not_canonical_setup),
    "missing-feedback": (
        "domain:decision-1",
        "domain:feedback-1",
        _missing_feedback_present_only_on_disk_setup,
    ),
    "feedback-not-eligible": (
        "domain:decision-1",
        "domain:feedback-1",
        _closed_ledger_evidence_setup,
    ),
}


@pytest.mark.parametrize(
    "verdict", list(_PREFLIGHT_REFUSAL_CASES), ids=list(_PREFLIGHT_REFUSAL_CASES)
)
def test_preflight_refusals_are_reported_verbatim_and_store_no_version(
    tmp_path: Path, verdict: str
) -> None:
    decision_value, evidence_value, setup = _PREFLIGHT_REFUSAL_CASES[verdict]
    setup(tmp_path)
    before = _snapshot_tree(_versions_dir(tmp_path))

    result = _run(tmp_path, decision=decision_value, evidence=evidence_value)

    assert result.outcome == "preflight-rejected"
    assert result.refusal == verdict
    assert not _evidence_dir(tmp_path).exists()
    assert _snapshot_tree(_versions_dir(tmp_path)) == before


# --------------------------------------------------------------------------
# Candidate lineage (plan case 13)
# --------------------------------------------------------------------------


def test_active_candidate_returns_durable_confirmation_request_without_settlement_write(
    tmp_path: Path,
) -> None:
    root = _enroll(tmp_path)
    candidate_id = _store_active_candidate_pair(tmp_path, root)
    before = _snapshot_tree(roadmap_dir(tmp_path, _SLUG))

    result = _run(tmp_path)

    assert result.refusal == "confirmation-required"
    assert result.receipt_id is None
    assert result.accepted_version_id == root.record.version_id
    assert result.active_candidate_version_id == candidate_id
    final_name = result.confirmation_evidence_final
    stored = enrolled_module.read_evidence_final(
        roadmap_dir(tmp_path, _SLUG), enrolled_module.EvidenceNamespace.DECISION_SETTLEMENTS, final_name
    )
    assert stored.data is not None
    assert enrolled_module._parse_confirmation_evidence(stored.data, final_name) is not None
    after = _snapshot_tree(roadmap_dir(tmp_path, _SLUG))
    assert {key: value for key, value in after.items() if key not in before} == {
        f".plan-tool/evidence/decision-settlements/{final_name}": stored.data
    }


def test_declined_confirmation_evidence_preserves_all_managed_state(tmp_path: Path) -> None:
    root = _enroll(tmp_path)
    _store_active_candidate_pair(tmp_path, root)
    request = _run(tmp_path)
    before = _snapshot_tree(roadmap_dir(tmp_path, _SLUG))

    result = respond_enrolled_decision_settlement(
        _SLUG,
        request.confirmation_evidence_final,
        False,
        plans_dir=tmp_path,
    )

    assert result.refusal == "confirmation-required"
    assert _snapshot_tree(roadmap_dir(tmp_path, _SLUG)) == before


def test_affirmed_settlement_releases_the_active_candidate_and_records_it_as_settled_in_one_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, candidate = _store_real_active_candidate(tmp_path, monkeypatch)
    request = _run(tmp_path)
    assert request.refusal == "confirmation-required"
    assert request.active_candidate_version_id == candidate.version_id
    captured: list[PendingGeneration] = []
    real_publish = enrolled_module.publish_roadmap_generation

    def _spy(generation: PendingGeneration, **kwargs: object):
        captured.append(generation)
        return real_publish(generation, **kwargs)

    monkeypatch.setattr(enrolled_module, "publish_roadmap_generation", _spy)

    result = respond_enrolled_decision_settlement(
        _SLUG, request.confirmation_evidence_final, True, plans_dir=tmp_path
    )

    assert result.outcome == "settled"
    accepted = load_accepted_version(plans_dir=tmp_path, slug=_SLUG)
    assert accepted.record.version_id != root.record.version_id
    assert accepted.record.predecessor_version_id == root.record.version_id
    admission = load_candidate_admission(plans_dir=tmp_path, slug=_SLUG)
    assert admission is not None
    assert admission.active_candidate_version_id is None
    assert admission.root_version_id == root.record.version_id

    terminal = terminal_resolution_path(tmp_path, _SLUG, candidate.version_id)
    record = json.loads(terminal.read_text(encoding="utf-8"))
    assert record["reason"] == "settled"
    assert record["candidate_version_id"] == candidate.version_id
    assert record["root_version_id"] == root.record.version_id
    assert terminal.read_bytes() == render_candidate_terminal_resolution(
        new_terminal_resolution(candidate, reason="settled")
    )
    # The released candidate is history, never deleted or promoted.
    assert version_directory_path(tmp_path, _SLUG, candidate.version_id).is_dir()

    # One generation carries the pointer release, the terminal record and the
    # head swap together: a crash cannot leave the pointer released without the
    # settled record, or the record without the swap.
    assert len(captured) == 1
    root_dir = roadmap_dir(tmp_path, _SLUG)
    paths = [member.relative_path for member in captured[0].members]
    assert candidate_admission_path(tmp_path, _SLUG).relative_to(root_dir).as_posix() in paths
    assert terminal.relative_to(root_dir).as_posix() in paths
    assert paths[-1] == accepted_head_path(tmp_path, _SLUG).relative_to(root_dir).as_posix()


def _released_pointer(admission):
    return admission.model_copy(update={"candidate_version_id": None, "active_candidate_version_id": None})


@pytest.mark.parametrize("drift", ("rejected", "discarded", "pointer-swapped"))
def test_a_candidate_released_or_replaced_between_request_and_response_refuses_before_any_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, drift: str
) -> None:
    """The confirmation binds the exact active candidate the operator saw. If that candidate is
    released or the pointer moves before the response, the response must not settle or leave a receipt."""
    _root, candidate = _store_real_active_candidate(tmp_path, monkeypatch)
    request = _run(tmp_path)
    assert request.refusal == "confirmation-required"
    if drift == "rejected":
        roadmap_candidate_review.reject_candidate_review(_SLUG, candidate.version_id, plans_dir=tmp_path)
    elif drift == "discarded":
        roadmap_candidate_review.discard_candidate_review(_SLUG, candidate.version_id, plans_dir=tmp_path)
    else:
        pointer = load_candidate_admission(plans_dir=tmp_path, slug=_SLUG)
        candidate_admission_path(tmp_path, _SLUG).write_bytes(
            roadmap_candidate_run.render_candidate_admission(
                pointer.model_copy(update={"candidate_version_id": "8" * 64, "active_candidate_version_id": "8" * 64})
            )
        )
    before = _snapshot_tree(roadmap_dir(tmp_path, _SLUG))

    result = respond_enrolled_decision_settlement(
        _SLUG, request.confirmation_evidence_final, True, plans_dir=tmp_path
    )

    assert result.outcome == "preflight-rejected"
    assert result.refusal == "confirmation-required"
    assert result.receipt_id is None
    assert _snapshot_tree(roadmap_dir(tmp_path, _SLUG)) == before


def test_a_candidate_released_inside_the_publication_window_refuses_and_writes_no_terminal_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The recheck inside the journal window is the last guard: a release that lands after the
    receipt is committed must stop the swap, and the receipt stays as evidence of the attempt."""
    _root, candidate = _store_real_active_candidate(tmp_path, monkeypatch)
    request = _run(tmp_path)
    pointer = load_candidate_admission(plans_dir=tmp_path, slug=_SLUG)
    head_before = accepted_head_path(tmp_path, _SLUG).read_bytes()
    real_publish = enrolled_module.publish_roadmap_generation

    def publish_after_the_release(generation: PendingGeneration, **kwargs: object):
        candidate_admission_path(tmp_path, _SLUG).write_bytes(
            roadmap_candidate_run.render_candidate_admission(_released_pointer(pointer))
        )
        return real_publish(generation, **kwargs)

    monkeypatch.setattr(enrolled_module, "publish_roadmap_generation", publish_after_the_release)

    result = respond_enrolled_decision_settlement(
        _SLUG, request.confirmation_evidence_final, True, plans_dir=tmp_path
    )

    assert result.outcome == "preflight-rejected"
    assert result.refusal == "source-changed"
    assert result.receipt_id is not None
    assert accepted_head_path(tmp_path, _SLUG).read_bytes() == head_before
    assert not terminal_resolution_path(tmp_path, _SLUG, candidate.version_id).exists()


def test_settled_root_owns_no_derived_context_from_the_released_candidate_and_the_ledger_is_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Derived context is keyed by ``source_version_id``, so a settled root
    starts empty by construction and settlement must not write the ledger."""
    _root, candidate = _store_real_active_candidate(tmp_path, monkeypatch)
    ledger_path = roadmap_feedback_ledger_path(tmp_path, _SLUG)
    before = ledger_path.read_bytes()
    assert [
        entry.context_id
        for entry in load_ledger(ledger_path).derived_context
        if entry.source_version_id == candidate.version_id
    ] == ["derived-order"]
    request = _run(tmp_path)

    result = respond_enrolled_decision_settlement(
        _SLUG, request.confirmation_evidence_final, True, plans_dir=tmp_path
    )

    assert result.outcome == "settled"
    assert ledger_path.read_bytes() == before
    settled = load_accepted_version(plans_dir=tmp_path, slug=_SLUG)
    _add_open_ledger_item(tmp_path, _open_ledger_item(settled, "after-settlement", "entity-order"))
    context = build_candidate_context(settled, None, load_ledger(ledger_path))
    assert isinstance(context.capsule, CandidateContextBatchCapsule)
    assert context.capsule.derived_context == ()
    assert [item.item_id for item in context.capsule.reviewer_items] == ["after-settlement"]


@pytest.mark.parametrize(
    "make_admission",
    (_reject_admission, _store_admission_awaiting_question),
    ids=("response-rejected", "stored-awaiting-question"),
)
def test_unpromoted_lineage_on_the_current_head_refuses_before_any_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_admission
) -> None:
    _enroll(tmp_path)
    make_admission(tmp_path, monkeypatch)

    def build_is_unexpected(*_args: object, **_kwargs: object) -> None:
        pytest.fail("a blocked lineage must refuse before step 2's build")

    monkeypatch.setattr(enrolled_module, "build_decision_settlement_candidate", build_is_unexpected)

    result = _run(tmp_path)

    assert result.outcome == "preflight-rejected"
    assert result.refusal == "unpromoted-candidate-lineage"
    assert not _evidence_dir(tmp_path).exists()


def test_unpromoted_lineage_refusal_has_no_age_limit(tmp_path: Path) -> None:
    _enroll(tmp_path)
    _reject_admission(tmp_path, None)
    admission_path = candidate_admission_path(tmp_path, _SLUG)
    old_time = time.time() - 60 * 60 * 24 * 365 * 10
    os.utime(admission_path, (old_time, old_time))

    result = _run(tmp_path)

    assert result.outcome == "preflight-rejected"
    assert result.refusal == "unpromoted-candidate-lineage"


@pytest.mark.parametrize(
    "release", ("reject_candidate_review", "discard_candidate_review"), ids=("rejected", "discarded")
)
def test_a_batch_pointer_released_by_rejection_or_discard_is_not_an_unpromoted_lineage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, release: str
) -> None:
    """Only a selector-era admission can carry an unpromoted lineage. A ledger-batch pointer
    is judged by its active candidate, so one released by rejection or discard names
    nothing and must not block settlement (its root equals the head, like a legacy one)."""
    _root, candidate = _store_real_active_candidate(tmp_path, monkeypatch)
    released = getattr(roadmap_candidate_review, release)(
        _SLUG, candidate.version_id, plans_dir=tmp_path
    )
    assert released.outcome == "stored", released.detail
    admission_before = candidate_admission_path(tmp_path, _SLUG).read_bytes()

    result = _run(tmp_path)

    assert result.outcome == "settled", (result.outcome, result.refusal)
    assert candidate_admission_path(tmp_path, _SLUG).read_bytes() == admission_before


def test_refusal_clears_once_the_head_moves_past_the_admissions_predecessor(tmp_path: Path) -> None:
    root = _enroll(tmp_path)
    _reject_admission(tmp_path, None)
    admission_before = candidate_admission_path(tmp_path, _SLUG).read_bytes()
    _promote_head_to_child(tmp_path, root)

    result = _run(tmp_path)

    assert result.outcome == "settled"
    assert candidate_admission_path(tmp_path, _SLUG).read_bytes() == admission_before


def test_runner_offers_no_way_to_abandon_or_override_a_lineage(tmp_path: Path) -> None:
    signature = inspect.signature(run_enrolled_decision_settlement)
    assert set(signature.parameters) == {
        "slug",
        "decision_value",
        "evidence_value",
        "confirmation",
        "plans_dir",
        "stages",
        "mode_rejected",
        "receipt_committer",
    }

    _enroll(tmp_path)
    _reject_admission(tmp_path, None)
    admission_before = candidate_admission_path(tmp_path, _SLUG).read_bytes()

    result = _run(tmp_path)

    assert result.outcome == "preflight-rejected"
    assert result.refusal == "unpromoted-candidate-lineage"
    assert candidate_admission_path(tmp_path, _SLUG).read_bytes() == admission_before


# --------------------------------------------------------------------------
# Gates (plan case 14)
# --------------------------------------------------------------------------


def test_gate_violation_on_the_settled_content_refuses_before_any_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from plan_tool.roadmap_gates import Violation

    _enroll(tmp_path)
    root = roadmap_dir(tmp_path, _SLUG)
    before = _snapshot_tree(root)

    def _failing(_evidence, *, stages=STAGES):
        return tuple(
            RoadmapGateOutcome(
                stage,
                (Violation("plans", "04-roadmap.md", None, "injected failure"),)
                if stage.artifact_key == "plans"
                else (),
            )
            for stage in stages
        )

    monkeypatch.setattr(enrolled_module, "check_complete_roadmap_gates", _failing)

    result = _run(tmp_path)

    assert result.outcome == "preflight-rejected"
    assert result.refusal == "settled-content-fails-gates"
    assert result.receipt_id is None
    assert not _evidence_dir(tmp_path).exists()
    assert _snapshot_tree(root) == before


def test_gate_walk_sees_the_settled_bytes_and_the_accepted_brief(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _enroll(tmp_path)
    observed: dict[str, object] = {}

    def _spy(evidence, *, stages=STAGES):
        observed["texts"] = evidence.artifact_texts
        observed["brief"] = evidence.brief_bytes
        return tuple(RoadmapGateOutcome(stage, ()) for stage in stages)

    monkeypatch.setattr(enrolled_module, "check_complete_roadmap_gates", _spy)

    result = _run(tmp_path)

    assert result.outcome == "settled"
    assert "status: settled" in observed["texts"][0]
    assert observed["brief"] == root.content.brief_bytes


# --------------------------------------------------------------------------
# The settlement version
# --------------------------------------------------------------------------


def test_no_review_sentinel_is_a_fixed_sha256_distinct_from_the_initial_review_lineage() -> None:
    """A dedicated 'no review occurred' sentinel, never the pipeline's 'awaiting review' one."""
    assert re.fullmatch(r"[0-9a-f]{64}", DECISION_SETTLEMENT_NO_REVIEW_LINEAGE_ID)
    assert DECISION_SETTLEMENT_NO_REVIEW_LINEAGE_ID != INITIAL_EMPTY_REVIEW_LINEAGE_ID


def test_settlement_version_is_a_candidate_record_with_the_no_review_sentinel_and_the_old_head_as_predecessor(
    tmp_path: Path,
) -> None:
    root = _enroll(tmp_path)

    result = _run(tmp_path)

    assert result.outcome == "settled"
    accepted = load_accepted_version(plans_dir=tmp_path, slug=_SLUG)
    assert accepted.record.version_kind == "candidate"
    assert accepted.record.predecessor_version_id == root.record.version_id
    assert accepted.record.review_lineage_identity == DECISION_SETTLEMENT_NO_REVIEW_LINEAGE_ID


_BASE_IDENTITY_KWARGS = {
    "predecessor_version_id": "a" * 64,
    "artifact_key": "domain",
    "decision_id": "decision-1",
    "feedback_id": "feedback-1",
    "evidence_digest": "b" * 64,
}


@pytest.mark.parametrize("field", list(_BASE_IDENTITY_KWARGS))
def test_content_identity_is_the_settlement_recipe_over_its_named_inputs(field: str) -> None:
    baseline = decision_settlement_content_identity(**_BASE_IDENTITY_KWARGS)
    changed = dict(_BASE_IDENTITY_KWARGS)
    changed[field] = "plans" if field == "artifact_key" else "c" * 64
    assert decision_settlement_content_identity(**changed) != baseline


def test_settlement_version_directory_holds_only_the_six_stored_members(tmp_path: Path) -> None:
    _enroll(tmp_path)

    result = _run(tmp_path)

    assert result.outcome == "settled"
    accepted = load_accepted_version(plans_dir=tmp_path, slug=_SLUG)
    version_dir = version_directory_path(tmp_path, _SLUG, accepted.record.version_id)
    names = {p.name for p in version_dir.iterdir()}
    assert names == {
        "version.json",
        "brief.md",
        "01-domain.md",
        "02-constraints.md",
        "03-components.md",
        "04-roadmap.md",
    }
    assert not candidate_admission_path(tmp_path, _SLUG).exists()


def test_new_version_changes_only_the_selected_status_line(tmp_path: Path) -> None:
    root = _enroll(tmp_path)
    before_lines = root.content.artifact_bytes[0].splitlines(keepends=True)

    result = _run(tmp_path)

    assert result.outcome == "settled"
    accepted = load_accepted_version(plans_dir=tmp_path, slug=_SLUG)
    after_lines = accepted.artifact_bytes[0].splitlines(keepends=True)
    assert len(before_lines) == len(after_lines)
    changed = [i for i, (b, a) in enumerate(zip(before_lines, after_lines)) if b != a]
    assert len(changed) == 1
    assert (
        before_lines[changed[0]].replace(b"status: pending", b"status: settled")
        == after_lines[changed[0]]
    )
    for index in range(1, 4):
        assert accepted.artifact_bytes[index] == root.content.artifact_bytes[index]
    assert accepted.brief_bytes == root.content.brief_bytes


def test_cited_feedback_row_is_unchanged_in_the_new_version(tmp_path: Path) -> None:
    cited = _feedback(state=FeedbackState.AWAITING_REVIEW, proposed_response="Keep this response.")
    _enroll(tmp_path, _domain(feedback=(cited,)))

    result = _run(tmp_path)

    assert result.outcome == "settled"
    accepted = load_accepted_version(plans_dir=tmp_path, slug=_SLUG)
    published = parse_domain_artifact(accepted.artifact_bytes[0].decode("utf-8"))
    assert published.feedback == (cited,)


@pytest.mark.parametrize(
    "loader_name, error_type",
    (
        ("proposal", roadmap_candidate_run.CandidateProposalError),
        ("review-replacement", roadmap_candidate_review.CandidateReviewError),
    ),
)
def test_settlement_version_is_refused_by_both_model_pipeline_loaders(
    tmp_path: Path, loader_name: str, error_type: type[Exception]
) -> None:
    _enroll(tmp_path)
    result = _run(tmp_path)
    assert result.outcome == "settled"
    accepted = load_accepted_version(plans_dir=tmp_path, slug=_SLUG)

    with pytest.raises(error_type):
        if loader_name == "proposal":
            roadmap_candidate_run.load_stored_candidate_proposal(
                plans_dir=tmp_path, slug=_SLUG, candidate_version_id=accepted.record.version_id
            )
        else:
            roadmap_candidate_review.load_stored_candidate_review_replacement(
                plans_dir=tmp_path, slug=_SLUG, candidate_version_id=accepted.record.version_id
            )


def test_existing_member_at_the_settlement_version_path_is_never_overwritten(tmp_path: Path) -> None:
    _enroll(tmp_path)
    accepted = load_accepted_version(plans_dir=tmp_path, slug=_SLUG)
    selector = resolve_decision_settlement_selector(
        "domain:decision-1",
        "domain:feedback-1",
        artifact_keys=tuple(stage.artifact_key for stage in STAGES),
    )
    candidate = build_decision_settlement_candidate(
        selector, plans_dir=tmp_path, slug=_SLUG, stages=STAGES
    )
    prepared = enrolled_module._build_settlement_version(slug=_SLUG, accepted=accepted, candidate=candidate)
    collision_path = version_directory_path(tmp_path, _SLUG, prepared.record.version_id) / "version.json"
    collision_path.parent.mkdir(parents=True, exist_ok=True)
    collision_path.write_bytes(b"pre-existing")
    head_before = accepted_head_path(tmp_path, _SLUG).read_bytes()

    result = _run(tmp_path)

    assert result.outcome == "write-failed"
    assert result.receipt_id is None
    assert collision_path.read_bytes() == b"pre-existing"
    assert accepted_head_path(tmp_path, _SLUG).read_bytes() == head_before


def test_prior_stored_versions_are_never_modified_or_removed(tmp_path: Path) -> None:
    """The selector is the one deliberate exception — swapping it is the point."""
    _enroll(tmp_path)
    versions_dir = _versions_dir(tmp_path)
    selector_rel = accepted_head_path(tmp_path, _SLUG).relative_to(versions_dir).as_posix()
    before = _snapshot_tree(versions_dir)

    result = _run(tmp_path)

    assert result.outcome == "settled"
    after = _snapshot_tree(versions_dir)
    for path, data in before.items():
        if path == selector_rel:
            continue
        assert after.get(path) == data


def test_top_level_stage_files_baselines_and_seed_state_are_untouched(tmp_path: Path) -> None:
    _enroll(tmp_path)
    root = roadmap_dir(tmp_path, _SLUG)
    stage_file = domain_path(tmp_path, _SLUG)
    baselines_dir = root / ".roadmap-baselines"
    state_file = seed_state_path(root)
    assert not stage_file.exists()
    assert not baselines_dir.exists()
    assert not state_file.exists()

    result = _run(tmp_path)

    assert result.outcome == "settled"
    assert not stage_file.exists()
    assert not baselines_dir.exists()
    assert not state_file.exists()


# --------------------------------------------------------------------------
# The swap
# --------------------------------------------------------------------------


def test_version_members_and_selector_swap_publish_as_one_decision_settlement_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    old_selector_bytes = accepted_head_path(tmp_path, _SLUG).read_bytes()
    captured: list[PendingGeneration] = []
    real_publish = enrolled_module.publish_roadmap_generation

    def _spy(generation: PendingGeneration, **kwargs: object):
        captured.append(generation)
        return real_publish(generation, **kwargs)

    monkeypatch.setattr(enrolled_module, "publish_roadmap_generation", _spy)

    result = _run(tmp_path)

    assert result.outcome == "settled"
    assert len(captured) == 1
    generation = captured[0]
    assert generation.kind == roadmap_revision_publish.DECISION_SETTLEMENT_GENERATION_KIND
    assert len(generation.members) == 7
    for member in generation.members[:-1]:
        assert member.old_bytes is None
    selector_member = generation.members[-1]
    assert selector_member.old_bytes == old_selector_bytes


def test_head_names_the_new_version_after_settlement(tmp_path: Path) -> None:
    root = _enroll(tmp_path)

    result = _run(tmp_path)

    assert result.outcome == "settled"
    accepted = load_accepted_version(plans_dir=tmp_path, slug=_SLUG)
    assert accepted.record.version_id != root.record.version_id
    assert accepted.record.predecessor_version_id == root.record.version_id


def test_post_receipt_recheck_reports_unpromoted_lineage_over_source_changed_when_both_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pins the post-receipt recheck's precedence, matching the preflight
    checks above it: admission-blocks before currency. Without this, a
    future reorder or merge of the two `if` blocks would silently change
    which refusal an operator sees when both conditions trip during the
    same receipt-commit window, and no other test would catch it — every
    existing unpromoted-lineage test only exercises the pre-receipt check,
    and the only existing post-commit-window test never has a candidate
    admission in place."""
    _enroll(tmp_path)
    admission_calls = {"count": 0}

    def admission_blocks_after_the_receipt(*_args: object, **_kwargs: object) -> bool:
        admission_calls["count"] += 1
        return admission_calls["count"] > 1

    def currency_check_is_unreached(*_args: object, **_kwargs: object) -> bool:
        pytest.fail("admission-blocks must be checked before currency, not after")

    monkeypatch.setattr(
        enrolled_module, "_admission_blocks_settlement", admission_blocks_after_the_receipt
    )
    monkeypatch.setattr(
        enrolled_module, "decision_settlement_candidate_is_current", currency_check_is_unreached
    )

    result = _run(tmp_path)

    assert result.outcome == "preflight-rejected"
    assert result.refusal == "unpromoted-candidate-lineage"
    assert result.receipt_id is not None
    assert admission_calls["count"] == 2


def test_head_move_during_the_receipt_commit_refuses_as_source_changed(tmp_path: Path) -> None:
    root = _enroll(tmp_path)
    child_id_box: dict[str, str] = {}

    def committer(repo_root: Path, receipt_path: Path, subject: str) -> tuple[int, str]:
        child_id_box["id"] = _swap_head_to_child_without_a_new_lock(tmp_path, root)
        return commit_receipt(repo_root, receipt_path, subject)

    result = _run(tmp_path, receipt_committer=committer)

    assert result.outcome == "preflight-rejected"
    assert result.refusal == "source-changed"
    assert result.receipt_id is not None
    version_dirs = {p.name for p in _versions_dir(tmp_path).iterdir() if p.is_dir()}
    assert version_dirs == {root.record.version_id, child_id_box["id"]}


def _reword_ledger_item(plans_dir: Path, item_id: str, request: str) -> None:
    """A hand edit of one ledger item's request, as a reviewer editing the file would make."""
    path = roadmap_feedback_ledger_path(plans_dir, _SLUG)
    ledger = load_ledger(path)
    groups = tuple(
        group.model_copy(update={"items": tuple(
            item.model_copy(update={"request": request}) if item.item_id == item_id else item
            for item in group.items
        )})
        for group in ledger.reviewer_feedback_groups
    )
    path.write_bytes(render_ledger(ledger.model_copy(update={"reviewer_feedback_groups": groups})))


def test_a_request_edit_to_the_cited_ledger_item_during_the_receipt_commit_refuses_as_source_changed(
    tmp_path: Path,
) -> None:
    """The receipt binds the evidence digest of the request the reviewer wrote; an edit that
    keeps the item eligible must not settle under a digest the ledger no longer matches."""
    _enroll(tmp_path, _domain(feedback=()))
    resolved = load_accepted_version(plans_dir=tmp_path, slug=_SLUG)
    _add_open_ledger_item(
        tmp_path, _open_ledger_item(resolved, "feedback-1", "decision-1", request="Confirm the order-centric model.")
    )
    head_before = accepted_head_path(tmp_path, _SLUG).read_bytes()

    def committer(repo_root: Path, receipt_path: Path, subject: str) -> tuple[int, str]:
        _reword_ledger_item(tmp_path, "feedback-1", "A different reviewer request.")
        return commit_receipt(repo_root, receipt_path, subject)

    result = _run(tmp_path, receipt_committer=committer)

    assert result.outcome == "preflight-rejected"
    assert result.refusal == "source-changed"
    assert result.receipt_id is not None
    assert accepted_head_path(tmp_path, _SLUG).read_bytes() == head_before


def test_head_move_inside_the_journal_window_refuses_and_leaves_no_journal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    root = roadmap_dir(tmp_path, _SLUG)
    journal_path = pending_generation_path(root)
    selector_path = accepted_head_path(tmp_path, _SLUG)
    real_durable_write = roadmap_revision_publish.durable_write_bytes

    def mutating_write(path: Path, data: bytes) -> None:
        real_durable_write(path, data)
        if Path(path) == journal_path:
            selector_path.write_bytes(b"mutated-while-journal-open")

    monkeypatch.setattr(roadmap_revision_publish, "durable_write_bytes", mutating_write)

    result = _run(tmp_path)

    assert result.outcome == "preflight-rejected"
    assert result.refusal == "source-changed"
    assert not journal_path.exists()


def test_accepted_head_is_written_only_inside_the_decision_settlement_journal_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    root = roadmap_dir(tmp_path, _SLUG)
    journal_path = pending_generation_path(root)
    selector_path = accepted_head_path(tmp_path, _SLUG)
    real_durable_write = roadmap_revision_publish.durable_write_bytes
    observed: list[str | None] = []

    def _spy(path: Path, data: bytes) -> None:
        if Path(path) == selector_path:
            journal = load_pending_generation(journal_path)
            observed.append(journal.kind if journal is not None else None)
        real_durable_write(path, data)

    monkeypatch.setattr(roadmap_revision_publish, "durable_write_bytes", _spy)

    result = _run(tmp_path)

    assert result.outcome == "settled"
    assert observed == [roadmap_revision_publish.DECISION_SETTLEMENT_GENERATION_KIND]


def test_no_call_reaches_promotion_or_the_model_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)

    def _fail(*_args: object, **_kwargs: object) -> None:
        pytest.fail("settlement must not reach the model-authored pipeline")

    monkeypatch.setattr(roadmap_version_promotion, "promote_review_seal", _fail)
    monkeypatch.setattr(roadmap_version_promotion, "_load_complete_sealed_candidate", _fail)
    monkeypatch.setattr(roadmap_candidate_run, "load_stored_candidate_proposal", _fail)
    monkeypatch.setattr(roadmap_candidate_review, "load_stored_candidate_review_replacement", _fail)
    monkeypatch.setattr(roadmap_candidate, "_content_identity", _fail)

    result = _run(tmp_path)

    assert result.outcome == "settled"


# --------------------------------------------------------------------------
# Receipt ordering
# --------------------------------------------------------------------------


def test_receipt_is_committed_to_head_before_the_generation_is_published(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    real_publish = enrolled_module.publish_roadmap_generation
    observed: dict[str, object] = {}

    def _spy(generation: PendingGeneration, **kwargs: object):
        shown = subprocess.run(
            ["git", "show", "--format=", "--name-only", "HEAD"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        observed["head_paths"] = shown.stdout.splitlines()
        return real_publish(generation, **kwargs)

    monkeypatch.setattr(enrolled_module, "publish_roadmap_generation", _spy)

    result = _run(tmp_path)

    assert result.outcome == "settled"
    receipt_path = _evidence_dir(tmp_path) / result.receipt_id
    assert receipt_path.relative_to(tmp_path).as_posix() in observed["head_paths"]


def test_receipt_names_the_stored_version_and_proves_completion(tmp_path: Path) -> None:
    _enroll(tmp_path)

    result = _run(tmp_path)

    assert result.outcome == "settled"
    accepted = load_accepted_version(plans_dir=tmp_path, slug=_SLUG)
    receipt_final = _evidence_dir(tmp_path) / result.receipt_id
    receipt = parse_decision_settlement_receipt(
        receipt_final.read_bytes(), expected_final_name=result.receipt_id
    )
    assert receipt.resulting_version_id == accepted.record.version_id
    assert decision_settlement_receipt_proves_completion(
        receipt, plans_dir=tmp_path, slug=_SLUG, stages=STAGES
    )


_RECEIPT_FAILURE_OUTCOMES = tuple(
    sorted(set(get_args(DecisionSettlementReceiptOutcome)) - DECISION_SETTLEMENT_RECEIPT_SUCCESS_OUTCOMES)
)


@pytest.mark.parametrize("outcome", _RECEIPT_FAILURE_OUTCOMES)
def test_each_non_success_receipt_outcome_stops_before_any_version_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    _enroll(tmp_path)
    before = _snapshot_tree(_versions_dir(tmp_path))
    calls: list[int] = []

    monkeypatch.setattr(
        enrolled_module,
        "publish_decision_settlement_receipt",
        lambda *_a, **_k: DecisionSettlementReceiptPublication(outcome=outcome, receipt_id=None),
    )
    monkeypatch.setattr(enrolled_module, "publish_roadmap_generation", lambda *_a, **_k: calls.append(1))

    result = _run(tmp_path)

    assert result.outcome == "receipt-rejected"
    assert result.refusal == outcome
    assert result.status == 1
    assert result.receipt_id is None
    assert calls == []
    assert _snapshot_tree(_versions_dir(tmp_path)) == before


def test_commit_failure_then_retry_settles_with_the_same_receipt_and_version_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)
    real_create = enrolled_module.create_candidate_version
    created_ids: list[str] = []

    def _spy_create(**kwargs: object):
        record = real_create(**kwargs)
        created_ids.append(record.version_id)
        return record

    monkeypatch.setattr(enrolled_module, "create_candidate_version", _spy_create)

    first = _run(tmp_path, receipt_committer=lambda *_a: (1, "hook rejected"))
    assert first.outcome == "receipt-rejected"
    assert first.refusal == "commit-failed"

    real_publish = enrolled_module.publish_decision_settlement_receipt
    observed: dict[str, str] = {}

    def _spy(*args: object, **kwargs: object):
        publication = real_publish(*args, **kwargs)
        observed["outcome"] = publication.outcome
        return publication

    monkeypatch.setattr(enrolled_module, "publish_decision_settlement_receipt", _spy)

    second = _run(tmp_path)

    assert second.outcome == "settled"
    assert observed["outcome"] == "committed-existing"
    assert second.receipt_id is not None
    assert len(created_ids) == 2
    assert created_ids[0] == created_ids[1]
    assert len(list(_evidence_dir(tmp_path).iterdir())) == 1


# --------------------------------------------------------------------------
# Result and module rules
# --------------------------------------------------------------------------


def test_result_is_the_shared_redacted_run_result(tmp_path: Path) -> None:
    artifact = _domain()
    _enroll(tmp_path, artifact)

    result = _run(tmp_path)

    assert result.outcome == "settled"
    assert isinstance(result, DecisionSettlementRunResult)
    fields = {field.name for field in dataclasses.fields(DecisionSettlementRunResult)}
    assert fields == {"outcome", "status", "refusal", "receipt_id"}
    rendered = repr(result)
    assert artifact.decisions[0].rationale not in rendered
    assert artifact.feedback[0].request not in rendered


def _literal_members(tp: object) -> set[str]:
    members: set[str] = set()
    for arg in get_args(tp):
        if get_args(arg):
            members |= _literal_members(arg)
        else:
            members.add(arg)
    return members


def test_shared_refusal_vocabulary_includes_all_three_enrolled_only_verdicts() -> None:
    """DecisionSettlementRunResult is one shared type both runners construct
    through the same _result, so its refusal vocabulary must already
    contain every verdict either runner can produce — no separate
    enrolled-only alias or wrapper constructor."""
    members = _literal_members(DecisionSettlementRunRefusal)
    assert {
        "no-published-version",
        "unpromoted-candidate-lineage",
        "settled-content-fails-gates",
    } <= members


def test_a_malformed_sibling_stage_artifact_is_named_not_left_to_escape_unhandled() -> None:
    """``RoadmapArtifactError`` from a malformed sibling stage's own parse
    (e.g. bad frontmatter) must be wrapped into ``RoadmapImpactSnapshotError``,
    matching the identical stage.parse loop in roadmap_impact_snapshot.py —
    not propagate unhandled past the command dispatcher."""

    def raising_parse(_text: str) -> DomainArtifact:
        raise RoadmapArtifactError("malformed frontmatter")

    stage = dataclasses.replace(_DOMAIN_STAGE, parse=raising_parse)

    with pytest.raises(RoadmapImpactSnapshotError):
        enrolled_module._parse_settlement_artifacts(("text",), stages=(stage,))


def test_keyboard_interrupt_reports_interrupted_and_releases_the_lease(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enroll(tmp_path)

    def raise_interrupt(*_args: object, **_kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(enrolled_module, "recover_roadmap_publication", raise_interrupt)

    result = _run(tmp_path)

    assert result.outcome == "interrupted"
    assert result.status == 130

    with roadmap_writer_guard(tmp_path, _SLUG):
        pass


_SETTLEMENT_MODULE_PATHS = {
    "select": Path(__file__).resolve().parents[1] / "plan_tool" / "roadmap_decision_settlement.py",
    "receipt": Path(__file__).resolve().parents[1]
    / "plan_tool"
    / "roadmap_decision_settlement_receipt.py",
    "run": Path(__file__).resolve().parents[1] / "plan_tool" / "roadmap_decision_settlement_run.py",
    "enrolled": MODULE_PATH,
}


@pytest.mark.parametrize("name", list(_SETTLEMENT_MODULE_PATHS), ids=list(_SETTLEMENT_MODULE_PATHS))
def test_settlement_modules_have_no_direct_write_route_to_the_accepted_head(name: str) -> None:
    """Root enrollment and review-seal promotion are deliberately out of this scan's scope."""
    source = _SETTLEMENT_MODULE_PATHS[name].read_text(encoding="utf-8")
    for banned in ("write_bytes(", "write_text(", "durable_write", ".unlink("):
        assert banned not in source, (name, banned)
    if name == "enrolled":
        assert "accepted_head_path" in source
        assert "render_accepted_head" in source
        assert source.count("publish_roadmap_generation(") == 1
    else:
        assert "accepted_head_path" not in source
        assert "render_accepted_head" not in source
