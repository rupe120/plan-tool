"""Tests for the immutable decision-settlement receipt record and lifecycle."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import get_args

import pytest

from plan_tool import roadmap_decision_settlement_receipt as receipt_module
from plan_tool import roadmap_escalation_run as escalation_run
from plan_tool.checkpoint import compute_input_hash
from plan_tool.cli.gitcommit import commit_receipt
from plan_tool.roadmap import STAGES
from plan_tool.roadmap_artifacts import (
    DecisionRow,
    DecisionStatus,
    DomainArtifact,
    FeedbackRow,
    FeedbackState,
    FeedbackTarget,
    FeedbackTargetKind,
    domain_path,
    parse_domain_artifact,
    render_domain_artifact,
    roadmap_dir,
)
from plan_tool.roadmap_decision_settlement import (
    DecisionSettlementCandidate,
    DecisionSettlementSelector,
    build_decision_settlement_candidate,
)
from plan_tool.roadmap_decision_settlement_receipt import (
    DECISION_SETTLEMENT_RECEIPT_SCHEMA_VERSION,
    DECISION_SETTLEMENT_RECEIPT_SUCCESS_OUTCOMES,
    DecisionSettlementReceiptError,
    DecisionSettlementReceiptOutcome,
    build_decision_settlement_receipt,
    decision_settlement_receipt_path,
    decision_settlement_receipt_proves_completion,
    parse_decision_settlement_receipt,
    publish_decision_settlement_receipt,
    render_decision_settlement_receipt,
)
from plan_tool.roadmap_evidence_store import (
    EVIDENCE_INVALID_INPUT,
    EVIDENCE_WRITE_FAILED,
    EvidenceNamespace,
    EvidencePublishResult,
)
from plan_tool.roadmap_source_identity import (
    GenerationMember,
    PendingGeneration,
    pending_generation_path,
    render_pending_generation,
)
from plan_tool.roadmap_versions import (
    ROADMAP_VERSION_SCHEMA_VERSION,
    STORED_VERSION_RECORD_FILENAME,
    AcceptedRoadmapHead,
    INITIAL_EMPTY_REVIEW_LINEAGE_ID,
    PreparedRoadmapVersion,
    RoadmapVersionContent,
    RoadmapVersionError,
    StoredRoadmapVersion,
    accepted_head_path,
    create_candidate_version,
    create_root_version,
    render_accepted_head,
    stored_version_members,
    version_directory_path,
)


_SLUG = "decision-settlement-receipt"
_GIT_TEMPLATE: Path | None = None


# --------------------------------------------------------------------------
# Fixture helpers
# --------------------------------------------------------------------------


def _candidate(
    *,
    artifact_key: str = "domain",
    decision_id: str = "decision-1",
    feedback_id: str = "feedback-1",
    accepted_version_id: str | None = "a" * 64,
    source_digest: str = "1" * 64,
    evidence_digest: str = "2" * 64,
    settled_digest: str = "3" * 64,
) -> DecisionSettlementCandidate:
    return DecisionSettlementCandidate(
        selector=DecisionSettlementSelector(artifact_key, decision_id, feedback_id),
        accepted_version_id=accepted_version_id,
        source_digest=source_digest,
        evidence_digest=evidence_digest,
        settled_artifact=None,  # unused by this module
        settled_bytes=b"",  # unused by this module
        settled_digest=settled_digest,
    )


def _semantic_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": DECISION_SETTLEMENT_RECEIPT_SCHEMA_VERSION,
        "artifact_key": "domain",
        "decision_id": "decision-1",
        "feedback_id": "feedback-1",
        "lineage": "enrolled",
        "predecessor_digest": "1" * 64,
        "predecessor_version_id": "a" * 64,
        "evidence_digest": "2" * 64,
        "resulting_artifact_digest": "3" * 64,
        "resulting_version_id": "b" * 64,
    }
    payload.update(overrides)
    return payload


def _self_consistent_payload(**overrides: object) -> dict[str, object]:
    semantic = _semantic_payload(**overrides)
    return {**semantic, "receipt_id": compute_input_hash(semantic)}


def _legacy_unenrolled_receipt(candidate: DecisionSettlementCandidate):
    """A stored pre-version-store receipt: ``lineage: unenrolled``, no version bindings."""
    payload = _self_consistent_payload(
        lineage="unenrolled",
        artifact_key=candidate.selector.artifact_key,
        decision_id=candidate.selector.decision_id,
        feedback_id=candidate.selector.feedback_id,
        predecessor_digest=candidate.source_digest,
        evidence_digest=candidate.evidence_digest,
        resulting_artifact_digest=candidate.settled_digest,
        predecessor_version_id=None,
        resulting_version_id=None,
    )
    return parse_decision_settlement_receipt(
        _payload_bytes(payload), expected_final_name=payload["receipt_id"]
    )


def _payload_bytes(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )


def _write_domain_stage(tmp_path: Path, data: bytes) -> None:
    path = domain_path(tmp_path, _SLUG)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _prepare_roadmap_dir(tmp_path: Path) -> Path:
    root = roadmap_dir(tmp_path, _SLUG)
    root.mkdir(parents=True)
    return root


def _store_prepared_version(tmp_path: Path, prepared: PreparedRoadmapVersion) -> StoredRoadmapVersion:
    version_dir = version_directory_path(tmp_path, _SLUG, prepared.record.version_id)
    for member in stored_version_members(prepared):
        path = version_dir / member.member_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(member.data)
    return prepared.record


def _store_root_version(tmp_path: Path, domain_bytes: bytes) -> StoredRoadmapVersion:
    content = RoadmapVersionContent(brief_bytes=b"brief\n", artifact_bytes=(domain_bytes, b"", b"", b""))
    record = create_root_version(
        roadmap_slug=_SLUG,
        brief_digest=hashlib.sha256(content.brief_bytes).hexdigest(),
        artifact_digests=tuple(hashlib.sha256(data).hexdigest() for data in content.artifact_bytes),
    )
    return _store_prepared_version(tmp_path, PreparedRoadmapVersion(record=record, content=content))


def _store_candidate_version(
    tmp_path: Path, *, predecessor_version_id: str, domain_bytes: bytes
) -> StoredRoadmapVersion:
    content = RoadmapVersionContent(brief_bytes=b"brief\n", artifact_bytes=(domain_bytes, b"", b"", b""))
    record = create_candidate_version(
        roadmap_slug=_SLUG,
        predecessor_version_id=predecessor_version_id,
        content_identity=hashlib.sha256(domain_bytes + b"-content").hexdigest(),
        review_lineage_identity=INITIAL_EMPTY_REVIEW_LINEAGE_ID,
        brief_digest=hashlib.sha256(content.brief_bytes).hexdigest(),
        artifact_digests=tuple(hashlib.sha256(data).hexdigest() for data in content.artifact_bytes),
    )
    return _store_prepared_version(tmp_path, PreparedRoadmapVersion(record=record, content=content))


def _select_accepted_version(tmp_path: Path, version_id: str) -> None:
    path = accepted_head_path(tmp_path, _SLUG)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        render_accepted_head(
            AcceptedRoadmapHead(
                schema_version=ROADMAP_VERSION_SCHEMA_VERSION,
                roadmap_slug=_SLUG,
                version_id=version_id,
            )
        )
    )


@pytest.fixture(scope="session", autouse=True)
def _empty_git_template(tmp_path_factory: pytest.TempPathFactory):
    """Provide isolated receipt worktrees with local identity."""
    global _GIT_TEMPLATE
    root = tmp_path_factory.mktemp("receipt-git-template")
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
def _receipt_worktree(tmp_path: Path) -> None:
    """Give publication lifecycle cases a controllable shared-history boundary."""
    assert _GIT_TEMPLATE is not None
    shutil.copytree(_GIT_TEMPLATE, tmp_path / ".git")


# --------------------------------------------------------------------------
# Record (pure)
# --------------------------------------------------------------------------


def test_receipt_id_is_the_hash_of_its_semantic_fields() -> None:
    receipt = build_decision_settlement_receipt(_candidate(), resulting_version_id="b" * 64)

    expected = compute_input_hash(_semantic_payload())
    assert receipt.receipt_id == expected
    assert receipt.final_name == expected


def test_semantic_fields_returns_exactly_the_base_models_own_fields() -> None:
    """_semantic_fields must return exactly _DecisionSettlementSemanticFields'
    own declared fields (derived from model_fields, not hand-listed, so a
    future field added there is automatically picked up) and must exclude
    DecisionSettlementReceipt's own extra receipt_id field even when called
    on that wider subtype — receipt_id is what this dict's hash computes,
    so including it would make the id self-referential."""
    receipt = build_decision_settlement_receipt(_candidate(), resulting_version_id="b" * 64)

    fields = receipt_module._semantic_fields(receipt)

    assert set(fields) == set(receipt_module._DecisionSettlementSemanticFields.model_fields)
    assert "receipt_id" not in fields


def test_same_candidate_renders_the_same_bytes_every_time() -> None:
    candidate = _candidate()
    first = render_decision_settlement_receipt(
        build_decision_settlement_receipt(candidate, resulting_version_id="b" * 64)
    )
    second = render_decision_settlement_receipt(
        build_decision_settlement_receipt(candidate, resulting_version_id="b" * 64)
    )

    assert first == second
    assert b"created_at" not in first


@pytest.mark.parametrize(
    "override",
    [
        {"decision_id": "decision-2"},
        {"feedback_id": "feedback-2"},
        {"artifact_key": "constraints"},
        {"source_digest": "4" * 64},
        {"evidence_digest": "5" * 64},
        {"settled_digest": "6" * 64},
    ],
    ids=[
        "decision_id",
        "feedback_id",
        "artifact_key",
        "predecessor_digest",
        "evidence_digest",
        "resulting_artifact_digest",
    ],
)
def test_changing_any_recorded_fact_changes_the_final_name(override: dict[str, object]) -> None:
    base = build_decision_settlement_receipt(_candidate(), resulting_version_id="b" * 64)
    changed = build_decision_settlement_receipt(_candidate(**override), resulting_version_id="b" * 64)

    assert changed.final_name != base.final_name


def test_changing_lineage_or_version_bindings_changes_the_final_name() -> None:
    legacy = _legacy_unenrolled_receipt(_candidate())
    enrolled = build_decision_settlement_receipt(_candidate(), resulting_version_id="b" * 64)
    rebound = build_decision_settlement_receipt(
        _candidate(accepted_version_id="7" * 64), resulting_version_id="8" * 64
    )

    assert len({legacy.final_name, enrolled.final_name, rebound.final_name}) == 3


def test_legacy_unenrolled_receipt_keeps_explicit_null_version_bindings() -> None:
    receipt = _legacy_unenrolled_receipt(_candidate())

    rendered = render_decision_settlement_receipt(receipt).decode("utf-8")

    assert '"predecessor_version_id":null' in rendered
    assert '"resulting_version_id":null' in rendered


def test_builder_always_produces_enrolled_lineage_with_both_version_bindings() -> None:
    receipt = build_decision_settlement_receipt(_candidate(), resulting_version_id="b" * 64)

    assert receipt.lineage == "enrolled"
    assert (receipt.predecessor_version_id, receipt.resulting_version_id) == ("a" * 64, "b" * 64)


@pytest.mark.parametrize(
    "candidate_kwargs, resulting_version_id",
    [
        ({"accepted_version_id": None}, "9" * 64),
        ({}, None),
        ({}, "not-a-digest"),
    ],
    ids=[
        "candidate-without-accepted-version-id",
        "no-resulting-version-id",
        "non-digest-resulting-version-id",
    ],
)
def test_builder_never_produces_an_unenrolled_receipt_and_refuses_missing_bindings(
    candidate_kwargs: dict[str, object], resulting_version_id: str | None
) -> None:
    with pytest.raises(DecisionSettlementReceiptError):
        build_decision_settlement_receipt(
            _candidate(**candidate_kwargs), resulting_version_id=resulting_version_id
        )


@pytest.mark.parametrize("kind", ["legacy-unenrolled", "enrolled"])
def test_render_then_parse_returns_the_same_receipt(kind: str) -> None:
    receipt = (
        _legacy_unenrolled_receipt(_candidate())
        if kind == "legacy-unenrolled"
        else build_decision_settlement_receipt(_candidate(), resulting_version_id="b" * 64)
    )
    data = render_decision_settlement_receipt(receipt)

    parsed = parse_decision_settlement_receipt(data, expected_final_name=receipt.final_name)

    assert parsed == receipt


_VALID_PAYLOAD = _self_consistent_payload()
_ANOTHER_RECEIPTS_PAYLOAD = _self_consistent_payload(decision_id="decision-2")
_WRONG_RECEIPT_ID_PAYLOAD = {**_VALID_PAYLOAD, "receipt_id": "0" * 64}
_UNSAFE_ID_PAYLOAD = _self_consistent_payload(decision_id="unsafe id")
_WRONG_NULLS_PAYLOAD = _self_consistent_payload(
    predecessor_version_id=None, resulting_version_id=None
)
_FLOAT_TEXT = _payload_bytes(_VALID_PAYLOAD).decode("utf-8").replace(
    f'"schema_version":{DECISION_SETTLEMENT_RECEIPT_SCHEMA_VERSION}',
    f'"schema_version":{DECISION_SETTLEMENT_RECEIPT_SCHEMA_VERSION}.0',
    1,
)
_NON_FINITE_TEXT = _payload_bytes(_VALID_PAYLOAD).decode("utf-8").replace(
    f'"schema_version":{DECISION_SETTLEMENT_RECEIPT_SCHEMA_VERSION}',
    '"schema_version":NaN',
    1,
)

_MALFORMED_RECEIPTS: dict[str, bytes] = {
    "not-json": b"not JSON",
    "duplicate-member": b'{"schema_version":1,"schema_version":1}',
    "unknown-field": _payload_bytes({**_VALID_PAYLOAD, "extra": "nope"}),
    "wrong-receipt-id": _payload_bytes(_WRONG_RECEIPT_ID_PAYLOAD),
    "unsafe-id": _payload_bytes(_UNSAFE_ID_PAYLOAD),
    "wrong-nulls-for-lineage": _payload_bytes(_WRONG_NULLS_PAYLOAD),
    "float": _FLOAT_TEXT.encode("utf-8"),
    "non-finite-constant": _NON_FINITE_TEXT.encode("utf-8"),
}


@pytest.mark.parametrize(
    "payload", _MALFORMED_RECEIPTS.values(), ids=list(_MALFORMED_RECEIPTS.keys())
)
def test_parse_rejects_malformed_receipts(payload: bytes) -> None:
    with pytest.raises(DecisionSettlementReceiptError):
        parse_decision_settlement_receipt(payload, expected_final_name=_VALID_PAYLOAD["receipt_id"])


def test_parse_rejects_a_receipt_under_a_different_final_name() -> None:
    data = _payload_bytes(_VALID_PAYLOAD)

    with pytest.raises(DecisionSettlementReceiptError):
        parse_decision_settlement_receipt(data, expected_final_name="f" * 64)


def test_receipt_bytes_carry_no_row_prose() -> None:
    receipt = build_decision_settlement_receipt(_candidate(), resulting_version_id="b" * 64)

    data = render_decision_settlement_receipt(receipt)

    for forbidden in (b"REVIEWER REQUEST", b"proposed_response", b"rationale", b"request"):
        assert forbidden not in data


# --------------------------------------------------------------------------
# Publication
# --------------------------------------------------------------------------


def test_fresh_receipt_is_committed_before_created(tmp_path: Path) -> None:
    root = _prepare_roadmap_dir(tmp_path)
    receipt = build_decision_settlement_receipt(_candidate(), resulting_version_id="b" * 64)

    result = publish_decision_settlement_receipt(
        receipt, plans_dir=tmp_path, slug=_SLUG, receipt_committer=commit_receipt
    )

    assert result.outcome == "created"
    assert result.receipt_id == receipt.receipt_id
    final_path = decision_settlement_receipt_path(root, receipt.final_name)
    shown = subprocess.run(
        ["git", "show", "--format=", "--name-only", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert shown.stdout.splitlines() == [final_path.relative_to(tmp_path).as_posix()]
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", str(final_path)],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert status.stdout == ""


def test_retry_with_the_same_inputs_reuses_the_committed_final_without_a_second_commit(
    tmp_path: Path,
) -> None:
    _prepare_roadmap_dir(tmp_path)
    receipt = build_decision_settlement_receipt(_candidate(), resulting_version_id="b" * 64)
    calls: list[tuple[Path, Path, str]] = []

    def counting_committer(repo_root: Path, receipt_path: Path, subject: str) -> tuple[int, str]:
        calls.append((repo_root, receipt_path, subject))
        return commit_receipt(repo_root, receipt_path, subject)

    first = publish_decision_settlement_receipt(
        receipt, plans_dir=tmp_path, slug=_SLUG, receipt_committer=counting_committer
    )
    second = publish_decision_settlement_receipt(
        receipt, plans_dir=tmp_path, slug=_SLUG, receipt_committer=counting_committer
    )

    assert first.outcome == "created"
    assert second.outcome == "reused"
    assert second.receipt_id == receipt.receipt_id
    assert len(calls) == 1


def test_commit_failure_keeps_the_local_final_and_a_retry_resumes_as_committed_existing(
    tmp_path: Path,
) -> None:
    root = _prepare_roadmap_dir(tmp_path)
    receipt = build_decision_settlement_receipt(_candidate(), resulting_version_id="b" * 64)

    failed = publish_decision_settlement_receipt(
        receipt,
        plans_dir=tmp_path,
        slug=_SLUG,
        receipt_committer=lambda *_args: (1, "hook rejected"),
    )
    assert failed.outcome == "commit-failed"
    final_path = decision_settlement_receipt_path(root, receipt.final_name)
    assert final_path.exists()

    resumed = publish_decision_settlement_receipt(
        receipt, plans_dir=tmp_path, slug=_SLUG, receipt_committer=commit_receipt
    )

    assert resumed.outcome == "committed-existing"
    assert resumed.receipt_id == receipt.receipt_id


@pytest.mark.parametrize(
    "committer",
    [
        lambda *_args: (1, "rejected"),
        lambda *_args: (_ for _ in ()).throw(OSError("boom")),
        lambda *_args: (_ for _ in ()).throw(subprocess.CalledProcessError(1, ["git"])),
    ],
    ids=["nonzero-rc", "os-error", "called-process-error"],
)
def test_commit_failure_variants_report_commit_failed_and_keep_the_final(
    tmp_path: Path, committer: object
) -> None:
    root = _prepare_roadmap_dir(tmp_path)
    receipt = build_decision_settlement_receipt(_candidate(), resulting_version_id="b" * 64)

    result = publish_decision_settlement_receipt(
        receipt, plans_dir=tmp_path, slug=_SLUG, receipt_committer=committer
    )

    assert result.outcome == "commit-failed"
    assert result.receipt_id is None
    assert decision_settlement_receipt_path(root, receipt.final_name).exists()


def test_no_worktree_refuses_before_any_evidence_write_no_git_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare_roadmap_dir(tmp_path)
    monkeypatch.setattr(
        receipt_module, "receipt_worktree_for_plans_dir", lambda _plans_dir: None
    )
    receipt = build_decision_settlement_receipt(_candidate(), resulting_version_id="b" * 64)

    result = publish_decision_settlement_receipt(
        receipt, plans_dir=tmp_path, slug=_SLUG, receipt_committer=commit_receipt
    )

    assert result.outcome == "no-worktree"
    assert result.receipt_id is None
    assert not (roadmap_dir(tmp_path, _SLUG) / ".plan-tool" / "evidence").exists()


def test_no_worktree_refuses_before_any_evidence_write_outside_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _prepare_roadmap_dir(tmp_path)
    monkeypatch.setattr(
        receipt_module, "receipt_path_is_within_worktree", lambda *_a, **_k: False
    )
    receipt = build_decision_settlement_receipt(_candidate(), resulting_version_id="b" * 64)

    result = publish_decision_settlement_receipt(
        receipt, plans_dir=tmp_path, slug=_SLUG, receipt_committer=commit_receipt
    )

    assert result.outcome == "no-worktree"
    assert result.receipt_id is None
    assert not (roadmap_dir(tmp_path, _SLUG) / ".plan-tool" / "evidence").exists()


def test_existing_final_with_different_head_bytes_is_a_collision_and_is_never_overwritten(
    tmp_path: Path,
) -> None:
    root = _prepare_roadmap_dir(tmp_path)
    receipt = build_decision_settlement_receipt(_candidate(), resulting_version_id="b" * 64)
    final_path = decision_settlement_receipt_path(root, receipt.final_name)
    final_path.parent.mkdir(parents=True)
    final_path.write_bytes(b"unrelated committed bytes")
    subprocess.run(
        ["git", "add", "-f", str(final_path)], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "-m", "seed unrelated head bytes"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    final_path.write_bytes(render_decision_settlement_receipt(receipt))

    def refusing_committer(*_args: object) -> tuple[int, str]:
        pytest.fail("a collision must never be committed")

    result = publish_decision_settlement_receipt(
        receipt, plans_dir=tmp_path, slug=_SLUG, receipt_committer=refusing_committer
    )

    assert result.outcome == "collision"
    assert result.receipt_id is None
    assert final_path.read_bytes() == render_decision_settlement_receipt(receipt)


@pytest.mark.parametrize(
    "stored_bytes",
    [b"garbage, not json", _payload_bytes(_ANOTHER_RECEIPTS_PAYLOAD)],
    ids=["garbage", "another-receipts-bytes"],
)
def test_invalid_existing_final_is_refused_and_left_in_place(
    tmp_path: Path, stored_bytes: bytes
) -> None:
    root = _prepare_roadmap_dir(tmp_path)
    receipt = build_decision_settlement_receipt(_candidate(), resulting_version_id="b" * 64)
    final_path = decision_settlement_receipt_path(root, receipt.final_name)
    final_path.parent.mkdir(parents=True)
    final_path.write_bytes(stored_bytes)

    def refusing_committer(*_args: object) -> tuple[int, str]:
        pytest.fail("an invalid existing receipt must never be committed")

    result = publish_decision_settlement_receipt(
        receipt, plans_dir=tmp_path, slug=_SLUG, receipt_committer=refusing_committer
    )

    assert result.outcome == "invalid-existing-receipt"
    assert result.receipt_id is None
    assert final_path.read_bytes() == stored_bytes


def test_existing_final_with_different_semantic_fields_is_a_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _prepare_roadmap_dir(tmp_path)
    receipt = build_decision_settlement_receipt(_candidate(), resulting_version_id="b" * 64)
    final_path = decision_settlement_receipt_path(root, receipt.final_name)
    final_path.parent.mkdir(parents=True)
    final_path.write_bytes(render_decision_settlement_receipt(receipt))

    forced = iter(("forged", "candidate"))
    monkeypatch.setattr(
        receipt_module, "_receipt_content_preimage", lambda _receipt: next(forced)
    )

    result = publish_decision_settlement_receipt(
        receipt,
        plans_dir=tmp_path,
        slug=_SLUG,
        receipt_committer=lambda *_a: pytest.fail("a collision must never be committed"),
    )

    assert result.outcome == "collision"
    assert result.receipt_id is None


@pytest.mark.parametrize(
    "storage_outcome, expected",
    [(EVIDENCE_INVALID_INPUT, "storage-rejected"), (EVIDENCE_WRITE_FAILED, "write-failed")],
)
def test_storage_outcomes_map_to_named_refusals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    storage_outcome: str,
    expected: DecisionSettlementReceiptOutcome,
) -> None:
    _prepare_roadmap_dir(tmp_path)
    receipt = build_decision_settlement_receipt(_candidate(), resulting_version_id="b" * 64)
    monkeypatch.setattr(
        receipt_module,
        "publish_evidence",
        lambda *_a, **_k: EvidencePublishResult(storage_outcome),
    )

    result = publish_decision_settlement_receipt(
        receipt, plans_dir=tmp_path, slug=_SLUG, receipt_committer=commit_receipt
    )

    assert result.outcome == expected
    assert result.receipt_id is None


def test_success_outcomes_are_exactly_created_reused_and_committed_existing() -> None:
    assert DECISION_SETTLEMENT_RECEIPT_SUCCESS_OUTCOMES == {
        "created",
        "reused",
        "committed-existing",
    }
    assert set(get_args(DecisionSettlementReceiptOutcome)) == {
        "no-worktree",
        "storage-rejected",
        "write-failed",
        "commit-failed",
        "invalid-existing-receipt",
        "collision",
        "created",
        "reused",
        "committed-existing",
    }


def test_settlement_receipts_live_only_in_their_own_namespace(tmp_path: Path) -> None:
    root = _prepare_roadmap_dir(tmp_path)
    receipt = build_decision_settlement_receipt(_candidate(), resulting_version_id="b" * 64)

    publish_decision_settlement_receipt(
        receipt, plans_dir=tmp_path, slug=_SLUG, receipt_committer=commit_receipt
    )

    assert (root / ".plan-tool" / "evidence" / "decision-settlements" / receipt.final_name).exists()
    assert not (root / ".plan-tool" / "evidence" / "escalations").exists()


def test_head_state_reads_the_settlement_namespace_path(tmp_path: Path) -> None:
    root = _prepare_roadmap_dir(tmp_path)
    receipt = build_decision_settlement_receipt(_candidate(), resulting_version_id="b" * 64)
    publish_decision_settlement_receipt(
        receipt, plans_dir=tmp_path, slug=_SLUG, receipt_committer=commit_receipt
    )
    worktree = escalation_run.receipt_worktree_for_plans_dir(tmp_path)
    data = render_decision_settlement_receipt(receipt)

    assert (
        escalation_run.receipt_head_state(
            data,
            receipt_final_name=receipt.final_name,
            roadmap_root=root,
            receipt_worktree=worktree,
            namespace=EvidenceNamespace.DECISION_SETTLEMENTS,
        )
        == "matching"
    )
    assert (
        escalation_run.receipt_head_state(
            data,
            receipt_final_name=receipt.final_name,
            roadmap_root=root,
            receipt_worktree=worktree,
            namespace=EvidenceNamespace.ESCALATIONS,
        )
        == "missing"
    )


# --------------------------------------------------------------------------
# Read-back
# --------------------------------------------------------------------------


def test_receipt_with_unenrolled_lineage_still_parses() -> None:
    """Live legacy record: stored receipts may carry ``lineage: unenrolled`` and stay readable."""
    parsed = _legacy_unenrolled_receipt(_candidate())

    assert parsed.lineage == "unenrolled"
    assert parsed.predecessor_version_id is None
    assert parsed.resulting_version_id is None


@pytest.mark.parametrize(
    "stage_bytes",
    [b"settled content\n", b"still pending\n"],
    ids=["stage-holds-the-settled-bytes", "stage-holds-other-bytes"],
)
def test_unenrolled_receipt_never_proves_from_a_top_level_stage_file(
    tmp_path: Path, stage_bytes: bytes
) -> None:
    """Deliberate carve-out: with no accepted head, a stage file's bytes prove nothing."""
    _write_domain_stage(tmp_path, stage_bytes)
    candidate = _candidate(settled_digest=hashlib.sha256(b"settled content\n").hexdigest())
    receipt = _legacy_unenrolled_receipt(candidate)

    assert (
        decision_settlement_receipt_proves_completion(
            receipt, plans_dir=tmp_path, slug=_SLUG, stages=STAGES
        )
        is False
    )


@pytest.mark.parametrize(
    "edited_bytes",
    [b"another decision settled\n", b"rationale revised\n"],
    ids=["another-decision", "rationale-revised"],
)
def test_unenrolled_proof_ends_on_a_later_edit_to_the_same_accepted_artifact(
    tmp_path: Path, edited_bytes: bytes
) -> None:
    settled_bytes = b"settled content\n"
    candidate = _candidate(settled_digest=hashlib.sha256(settled_bytes).hexdigest())
    receipt = _legacy_unenrolled_receipt(candidate)
    root_record = _store_root_version(tmp_path, settled_bytes)
    _select_accepted_version(tmp_path, root_record.version_id)
    assert (
        decision_settlement_receipt_proves_completion(
            receipt, plans_dir=tmp_path, slug=_SLUG, stages=STAGES
        )
        is True
    )

    edited_record = _store_candidate_version(
        tmp_path, predecessor_version_id=root_record.version_id, domain_bytes=edited_bytes
    )
    _select_accepted_version(tmp_path, edited_record.version_id)

    assert (
        decision_settlement_receipt_proves_completion(
            receipt, plans_dir=tmp_path, slug=_SLUG, stages=STAGES
        )
        is False
    )


def test_missing_stage_file_does_not_prove(tmp_path: Path) -> None:
    _prepare_roadmap_dir(tmp_path)
    candidate = _candidate(settled_digest="a" * 64)
    receipt = _legacy_unenrolled_receipt(candidate)

    assert (
        decision_settlement_receipt_proves_completion(
            receipt, plans_dir=tmp_path, slug=_SLUG, stages=STAGES
        )
        is False
    )


def _pending_generation_journal() -> PendingGeneration:
    return PendingGeneration(
        kind="test",
        members=(GenerationMember("some/path.json", None, b"x"),),
    )


def test_any_pending_generation_means_not_proven_unenrolled(tmp_path: Path) -> None:
    settled_bytes = b"settled content\n"
    candidate = _candidate(settled_digest=hashlib.sha256(settled_bytes).hexdigest())
    receipt = _legacy_unenrolled_receipt(candidate)
    root_record = _store_root_version(tmp_path, settled_bytes)
    _select_accepted_version(tmp_path, root_record.version_id)
    root = roadmap_dir(tmp_path, _SLUG)
    pending_generation_path(root).write_bytes(render_pending_generation(_pending_generation_journal()))

    assert (
        decision_settlement_receipt_proves_completion(
            receipt, plans_dir=tmp_path, slug=_SLUG, stages=STAGES
        )
        is False
    )


def test_any_pending_generation_means_not_proven_enrolled(tmp_path: Path) -> None:
    root_record = _store_root_version(tmp_path, b"root domain\n")
    settled_bytes = b"settled domain\n"
    settled_record = _store_candidate_version(
        tmp_path, predecessor_version_id=root_record.version_id, domain_bytes=settled_bytes
    )
    _select_accepted_version(tmp_path, settled_record.version_id)
    candidate = _candidate(
        accepted_version_id=root_record.version_id,
        settled_digest=hashlib.sha256(settled_bytes).hexdigest(),
    )
    receipt = build_decision_settlement_receipt(
        candidate, resulting_version_id=settled_record.version_id
    )
    root = roadmap_dir(tmp_path, _SLUG)
    pending_generation_path(root).write_bytes(render_pending_generation(_pending_generation_journal()))

    assert (
        decision_settlement_receipt_proves_completion(
            receipt, plans_dir=tmp_path, slug=_SLUG, stages=STAGES
        )
        is False
    )


def test_enrolled_receipt_proves_while_its_version_is_the_head(tmp_path: Path) -> None:
    root_record = _store_root_version(tmp_path, b"root domain\n")
    settled_bytes = b"settled domain\n"
    settled_record = _store_candidate_version(
        tmp_path, predecessor_version_id=root_record.version_id, domain_bytes=settled_bytes
    )
    _select_accepted_version(tmp_path, settled_record.version_id)
    candidate = _candidate(
        accepted_version_id=root_record.version_id,
        settled_digest=hashlib.sha256(settled_bytes).hexdigest(),
    )
    receipt = build_decision_settlement_receipt(
        candidate, resulting_version_id=settled_record.version_id
    )

    assert (
        decision_settlement_receipt_proves_completion(
            receipt, plans_dir=tmp_path, slug=_SLUG, stages=STAGES
        )
        is True
    )


def test_enrolled_proof_survives_a_later_promotion(tmp_path: Path) -> None:
    root_record = _store_root_version(tmp_path, b"root domain\n")
    settled_bytes = b"settled domain\n"
    settled_record = _store_candidate_version(
        tmp_path, predecessor_version_id=root_record.version_id, domain_bytes=settled_bytes
    )
    _select_accepted_version(tmp_path, settled_record.version_id)
    candidate = _candidate(
        accepted_version_id=root_record.version_id,
        settled_digest=hashlib.sha256(settled_bytes).hexdigest(),
    )
    receipt = build_decision_settlement_receipt(
        candidate, resulting_version_id=settled_record.version_id
    )
    assert (
        decision_settlement_receipt_proves_completion(
            receipt, plans_dir=tmp_path, slug=_SLUG, stages=STAGES
        )
        is True
    )

    child_record = _store_candidate_version(
        tmp_path, predecessor_version_id=settled_record.version_id, domain_bytes=b"later domain\n"
    )
    _select_accepted_version(tmp_path, child_record.version_id)

    assert (
        decision_settlement_receipt_proves_completion(
            receipt, plans_dir=tmp_path, slug=_SLUG, stages=STAGES
        )
        is True
    )


def test_enrolled_receipt_whose_version_was_never_stored_does_not_prove(tmp_path: Path) -> None:
    root_record = _store_root_version(tmp_path, b"root domain\n")
    _select_accepted_version(tmp_path, root_record.version_id)
    candidate = _candidate(accepted_version_id=root_record.version_id, settled_digest="a" * 64)
    receipt = build_decision_settlement_receipt(candidate, resulting_version_id="b" * 64)

    assert (
        decision_settlement_receipt_proves_completion(
            receipt, plans_dir=tmp_path, slug=_SLUG, stages=STAGES
        )
        is False
    )


def test_enrolled_receipt_naming_a_version_off_the_head_chain_does_not_prove(tmp_path: Path) -> None:
    root_record = _store_root_version(tmp_path, b"root domain\n")
    sibling_bytes = b"sibling domain\n"
    sibling_record = _store_candidate_version(
        tmp_path, predecessor_version_id=root_record.version_id, domain_bytes=sibling_bytes
    )
    other_record = _store_candidate_version(
        tmp_path, predecessor_version_id=root_record.version_id, domain_bytes=b"other head domain\n"
    )
    _select_accepted_version(tmp_path, other_record.version_id)
    candidate = _candidate(
        accepted_version_id=root_record.version_id,
        settled_digest=hashlib.sha256(sibling_bytes).hexdigest(),
    )
    receipt = build_decision_settlement_receipt(
        candidate, resulting_version_id=sibling_record.version_id
    )

    assert (
        decision_settlement_receipt_proves_completion(
            receipt, plans_dir=tmp_path, slug=_SLUG, stages=STAGES
        )
        is False
    )


def test_enrolled_predecessor_chain_cycle_raises_instead_of_hanging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A corrupted store whose predecessor pointers cycle must raise a
    diagnosable RoadmapVersionError, not spin forever walking the chain —
    the read-back check's own docstring promises a corrupt store propagates
    as an error, never a silent answer."""
    root_record = _store_root_version(tmp_path, b"root domain\n")
    _select_accepted_version(tmp_path, root_record.version_id)
    candidate = _candidate(
        accepted_version_id=root_record.version_id,
        settled_digest=hashlib.sha256(b"unrelated\n").hexdigest(),
    )
    receipt = build_decision_settlement_receipt(candidate, resulting_version_id="9" * 64)

    cycle = {
        "head": SimpleNamespace(predecessor_version_id="a"),
        "a": SimpleNamespace(predecessor_version_id="head"),
    }
    monkeypatch.setattr(
        receipt_module,
        "load_accepted_head",
        lambda *, plans_dir, slug: SimpleNamespace(version_id="head"),
    )
    monkeypatch.setattr(
        receipt_module,
        "load_stored_version",
        lambda *, plans_dir, slug, version_id: cycle[version_id],
    )

    with pytest.raises(receipt_module.RoadmapVersionError, match="cycle"):
        decision_settlement_receipt_proves_completion(
            receipt, plans_dir=tmp_path, slug=_SLUG, stages=STAGES
        )


@pytest.mark.parametrize("mutate", ["member-digest", "predecessor"])
def test_enrolled_version_with_a_different_member_digest_or_predecessor_does_not_prove(
    tmp_path: Path, mutate: str
) -> None:
    root_record = _store_root_version(tmp_path, b"root domain\n")
    settled_bytes = b"settled domain\n"
    settled_record = _store_candidate_version(
        tmp_path, predecessor_version_id=root_record.version_id, domain_bytes=settled_bytes
    )
    _select_accepted_version(tmp_path, settled_record.version_id)

    if mutate == "member-digest":
        candidate = _candidate(accepted_version_id=root_record.version_id, settled_digest="c" * 64)
    else:
        candidate = _candidate(
            accepted_version_id="d" * 64,
            settled_digest=hashlib.sha256(settled_bytes).hexdigest(),
        )
    receipt = build_decision_settlement_receipt(
        candidate, resulting_version_id=settled_record.version_id
    )

    assert (
        decision_settlement_receipt_proves_completion(
            receipt, plans_dir=tmp_path, slug=_SLUG, stages=STAGES
        )
        is False
    )


def test_enrolled_receipt_on_an_unenrolled_roadmap_does_not_prove(tmp_path: Path) -> None:
    _prepare_roadmap_dir(tmp_path)
    candidate = _candidate(accepted_version_id="a" * 64, settled_digest="b" * 64)
    receipt = build_decision_settlement_receipt(candidate, resulting_version_id="c" * 64)

    assert (
        decision_settlement_receipt_proves_completion(
            receipt, plans_dir=tmp_path, slug=_SLUG, stages=STAGES
        )
        is False
    )


def test_unenrolled_receipt_after_enrollment_compares_the_accepted_member(tmp_path: Path) -> None:
    settled_bytes = b"settled domain\n"
    candidate = _candidate(settled_digest=hashlib.sha256(settled_bytes).hexdigest())
    receipt = _legacy_unenrolled_receipt(candidate)

    root_record = _store_root_version(tmp_path, settled_bytes)
    _select_accepted_version(tmp_path, root_record.version_id)

    assert (
        decision_settlement_receipt_proves_completion(
            receipt, plans_dir=tmp_path, slug=_SLUG, stages=STAGES
        )
        is True
    )

    promoted_record = _store_candidate_version(
        tmp_path, predecessor_version_id=root_record.version_id, domain_bytes=b"promoted domain\n"
    )
    _select_accepted_version(tmp_path, promoted_record.version_id)

    assert (
        decision_settlement_receipt_proves_completion(
            receipt, plans_dir=tmp_path, slug=_SLUG, stages=STAGES
        )
        is False
    )


def test_unenrolled_receipt_naming_an_unrecognized_artifact_key_does_not_prove(
    tmp_path: Path,
) -> None:
    """A receipt whose artifact_key isn't one of the accepted version's own
    keys must return False, matching this function's own "a pending
    publication always means not proven" contract — not raise ValueError
    from an unguarded tuple.index() lookup."""
    settled_bytes = b"settled domain\n"
    candidate = _candidate(
        artifact_key="not-a-real-artifact-key",
        settled_digest=hashlib.sha256(settled_bytes).hexdigest(),
    )
    receipt = _legacy_unenrolled_receipt(candidate)

    root_record = _store_root_version(tmp_path, settled_bytes)
    _select_accepted_version(tmp_path, root_record.version_id)

    assert (
        decision_settlement_receipt_proves_completion(
            receipt, plans_dir=tmp_path, slug=_SLUG, stages=STAGES
        )
        is False
    )


def test_enrolled_readback_never_reads_stage_files(tmp_path: Path) -> None:
    root_record = _store_root_version(tmp_path, b"root domain\n")
    settled_bytes = b"settled domain\n"
    settled_record = _store_candidate_version(
        tmp_path, predecessor_version_id=root_record.version_id, domain_bytes=settled_bytes
    )
    _select_accepted_version(tmp_path, settled_record.version_id)
    candidate = _candidate(
        accepted_version_id=root_record.version_id,
        settled_digest=hashlib.sha256(settled_bytes).hexdigest(),
    )
    receipt = build_decision_settlement_receipt(
        candidate, resulting_version_id=settled_record.version_id
    )

    class _ExplodingStage:
        artifact_key = "domain"

        def artifact_path(self, plans_dir: Path, slug: str) -> Path:
            raise AssertionError("enrolled read-back must never read a stage file")

    assert (
        decision_settlement_receipt_proves_completion(
            receipt, plans_dir=tmp_path, slug=_SLUG, stages=(_ExplodingStage(),)
        )
        is True
    )


def test_corrupt_version_store_raises_rather_than_reporting_false(tmp_path: Path) -> None:
    root_record = _store_root_version(tmp_path, b"root domain\n")
    settled_bytes = b"settled domain\n"
    settled_record = _store_candidate_version(
        tmp_path, predecessor_version_id=root_record.version_id, domain_bytes=settled_bytes
    )
    _select_accepted_version(tmp_path, settled_record.version_id)
    record_path = (
        version_directory_path(tmp_path, _SLUG, settled_record.version_id)
        / STORED_VERSION_RECORD_FILENAME
    )
    record_path.write_bytes(b"not json")
    candidate = _candidate(
        accepted_version_id=root_record.version_id,
        settled_digest=hashlib.sha256(settled_bytes).hexdigest(),
    )
    receipt = build_decision_settlement_receipt(
        candidate, resulting_version_id=settled_record.version_id
    )

    with pytest.raises(RoadmapVersionError):
        decision_settlement_receipt_proves_completion(
            receipt, plans_dir=tmp_path, slug=_SLUG, stages=STAGES
        )


# --------------------------------------------------------------------------
# Seam and discipline
# --------------------------------------------------------------------------


def test_receipt_built_from_a_real_preflight_candidate_names_its_settled_digest(
    tmp_path: Path,
) -> None:
    domain = DomainArtifact(
        entities=(),
        business_rules=(),
        workflows=(),
        decisions=(
            DecisionRow(
                id="decision-1",
                chosen_option="Keep it simple.",
                rejected_alternatives=(),
                rationale="Because it is simple.",
                anchor="decision-1",
                status=DecisionStatus.PENDING,
            ),
        ),
        body="# Domain\n",
        feedback=(
            FeedbackRow(
                id="feedback-1",
                target=FeedbackTarget(FeedbackTargetKind.ROW, "decision-1"),
                request="Ship it.",
                state=FeedbackState.OPEN,
            ),
        ),
    )
    domain_bytes = render_domain_artifact(domain).encode("utf-8")
    root_record = _store_root_version(tmp_path, domain_bytes)
    _select_accepted_version(tmp_path, root_record.version_id)

    selector = DecisionSettlementSelector(
        artifact_key="domain", decision_id="decision-1", feedback_id="feedback-1"
    )
    candidate = build_decision_settlement_candidate(
        selector, plans_dir=tmp_path, slug=_SLUG, stages=STAGES
    )
    assert isinstance(candidate, DecisionSettlementCandidate)

    receipt = build_decision_settlement_receipt(candidate, resulting_version_id="a" * 64)

    assert receipt.resulting_artifact_digest == hashlib.sha256(candidate.settled_bytes).hexdigest()
    assert receipt.predecessor_digest == candidate.source_digest
    assert receipt.evidence_digest == candidate.evidence_digest


def test_module_never_imports_the_cli_computes_a_version_or_deletes_files() -> None:
    source = Path(receipt_module.__file__).read_text(encoding="utf-8")

    for forbidden in (
        "plan_tool.cli",
        "create_candidate_version",
        "unlink",
        "rmtree",
        "os.remove",
    ):
        assert forbidden not in source
