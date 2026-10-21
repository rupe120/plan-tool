from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from plan_tool import model_response_sidecar
from plan_tool.model_response_sidecar import (
    ModelResponseSidecarOutcome,
    store_model_response_sidecar,
)


def test_written_response_is_stored_under_the_producer_slug(tmp_path: Path) -> None:
    response = "rejected response: ☃"

    result = store_model_response_sidecar(
        repo_root=tmp_path,
        producer_slug="roadmap",
        receipt_identity="stage-01-attempt-01",
        raw_response=response,
    )

    assert result.outcome is ModelResponseSidecarOutcome.WRITTEN
    assert result.path == (
        tmp_path
        / ".plan-tool"
        / "parse-failures"
        / "roadmap"
        / "stage-01-attempt-01.txt"
    )
    assert result.path.read_bytes() == response.encode("utf-8")
    assert result.digest == hashlib.sha256(response.encode("utf-8")).hexdigest()


def test_existing_target_is_replaced_as_one_complete_response(tmp_path: Path) -> None:
    first = store_model_response_sidecar(
        repo_root=tmp_path,
        producer_slug="roadmap",
        receipt_identity="stage-01-attempt-01",
        raw_response="old response",
    )
    second = store_model_response_sidecar(
        repo_root=tmp_path,
        producer_slug="roadmap",
        receipt_identity="stage-01-attempt-01",
        raw_response="new complete response",
    )

    assert first.path == second.path
    assert second.path is not None
    assert second.path.read_bytes() == b"new complete response"


def test_distinct_receipt_identities_never_overwrite_each_other(tmp_path: Path) -> None:
    results = [
        store_model_response_sidecar(
            repo_root=tmp_path,
            producer_slug="roadmap",
            receipt_identity=f"stage-01-attempt-0{attempt}",
            raw_response=response,
        )
        for attempt, response in enumerate(("first", "second"), start=1)
    ]

    assert results[0].path != results[1].path
    for result in results:
        assert result.path is not None
        assert result.digest == hashlib.sha256(result.path.read_bytes()).hexdigest()


def test_write_failure_reports_write_failed_and_preserves_existing_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = (
        tmp_path / ".plan-tool" / "parse-failures" / "roadmap" / "receipt.txt"
    )
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old response")

    def fail_write(path: Path, data: bytes) -> None:
        raise OSError("disk unavailable")

    monkeypatch.setattr(model_response_sidecar, "atomic_write_bytes", fail_write)
    result = store_model_response_sidecar(
        repo_root=tmp_path,
        producer_slug="roadmap",
        receipt_identity="receipt",
        raw_response="new response",
    )

    assert result.outcome is ModelResponseSidecarOutcome.WRITE_FAILED
    assert result.path is None
    assert target.read_bytes() == b"old response"


def test_digest_and_response_bytes_survive_a_non_written_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A caller's receipt needs a response identity whether or not the
    sidecar file was actually written — WRITE_FAILED and NOT_RETAINED must
    carry the same digest/byte count a WRITTEN outcome would, not just the
    written path."""
    response = "rejected response"
    expected_digest = hashlib.sha256(response.encode("utf-8")).hexdigest()
    expected_bytes = len(response.encode("utf-8"))

    not_retained = store_model_response_sidecar(
        repo_root=tmp_path,
        producer_slug="roadmap",
        receipt_identity="not-retained",
        raw_response=response,
        retain_response=False,
    )
    assert not_retained.digest == expected_digest
    assert not_retained.response_bytes == expected_bytes

    def fail_write(path: Path, data: bytes) -> None:
        raise OSError("disk unavailable")

    monkeypatch.setattr(model_response_sidecar, "atomic_write_bytes", fail_write)
    write_failed = store_model_response_sidecar(
        repo_root=tmp_path,
        producer_slug="roadmap",
        receipt_identity="write-failed",
        raw_response=response,
    )
    assert write_failed.digest == expected_digest
    assert write_failed.response_bytes == expected_bytes


def test_no_response_and_not_retained_are_distinct_non_write_results(
    tmp_path: Path,
) -> None:
    no_response = store_model_response_sidecar(
        repo_root=tmp_path,
        producer_slug="roadmap",
        receipt_identity="no-response",
        raw_response=None,
    )
    not_retained = store_model_response_sidecar(
        repo_root=tmp_path,
        producer_slug="roadmap",
        receipt_identity="not-retained",
        raw_response="response",
        retain_response=False,
    )

    assert no_response.outcome is ModelResponseSidecarOutcome.NO_RESPONSE
    assert not_retained.outcome is ModelResponseSidecarOutcome.NOT_RETAINED
    assert not (tmp_path / ".plan-tool" / "parse-failures").exists()


def test_leaf_does_not_import_producer_orchestrators() -> None:
    source = Path(model_response_sidecar.__file__).read_text(encoding="utf-8")

    for module in ("detail", "roadmap", "run_log", "create"):
        assert f"plan_tool.{module}" not in source
