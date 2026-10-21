from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from plan_tool import roadmap_evidence_store as evidence_store
from plan_tool.roadmap_evidence_store import (
    EVIDENCE_CREATED,
    EVIDENCE_EXISTING,
    EVIDENCE_INVALID_INPUT,
    EVIDENCE_WRITE_FAILED,
    EvidenceNamespace,
    namespace_relative_components,
    publish_evidence,
    read_evidence_final,
    scan_evidence,
)


def _name(character: str = "a") -> str:
    return character * 64


def _namespace_dir(roadmap_dir: Path, namespace: EvidenceNamespace = EvidenceNamespace.ESCALATIONS) -> Path:
    return roadmap_dir.joinpath(*namespace_relative_components(namespace))


def test_impact_analysis_namespace_has_fixed_components() -> None:
    assert namespace_relative_components(EvidenceNamespace.IMPACT_ANALYSES) == (
        ".plan-tool",
        "evidence",
        "impact-analyses",
    )


def test_decision_settlement_namespace_has_fixed_components() -> None:
    assert namespace_relative_components(EvidenceNamespace.DECISION_SETTLEMENTS) == (
        ".plan-tool",
        "evidence",
        "decision-settlements",
    )


@pytest.mark.parametrize("namespace", list(EvidenceNamespace))
def test_publish_creates_durable_final_and_removes_its_temporary(
    tmp_path: Path,
    namespace: EvidenceNamespace,
) -> None:
    result = publish_evidence(tmp_path, namespace, _name(), b"first")

    assert result.outcome == EVIDENCE_CREATED
    assert result.data == b"first"
    directory = _namespace_dir(tmp_path, namespace)
    assert (directory / _name()).read_bytes() == b"first"
    assert not list(directory.glob(".*.tmp"))


@pytest.mark.parametrize("namespace", list(EvidenceNamespace))
def test_publish_reuses_exact_final_without_overwriting(
    tmp_path: Path,
    namespace: EvidenceNamespace,
) -> None:
    assert publish_evidence(tmp_path, namespace, _name(), b"first").outcome == EVIDENCE_CREATED

    result = publish_evidence(tmp_path, namespace, _name(), b"second")

    assert result.outcome == EVIDENCE_EXISTING
    assert result.data == b"first"
    assert (_namespace_dir(tmp_path, namespace) / _name()).read_bytes() == b"first"


def test_namespaces_isolate_identical_final_names(tmp_path: Path) -> None:
    final_name = _name()
    assert publish_evidence(
        tmp_path,
        EvidenceNamespace.ESCALATIONS,
        final_name,
        b"receipt",
    ).outcome == EVIDENCE_CREATED
    assert publish_evidence(
        tmp_path,
        EvidenceNamespace.IMPACT_ANALYSES,
        final_name,
        b"analysis",
    ).outcome == EVIDENCE_CREATED
    assert publish_evidence(
        tmp_path,
        EvidenceNamespace.DECISION_SETTLEMENTS,
        final_name,
        b"settlement",
    ).outcome == EVIDENCE_CREATED

    receipts = scan_evidence(tmp_path, EvidenceNamespace.ESCALATIONS)
    analyses = scan_evidence(tmp_path, EvidenceNamespace.IMPACT_ANALYSES)
    settlements = scan_evidence(tmp_path, EvidenceNamespace.DECISION_SETTLEMENTS)

    assert [(record.name, record.data) for record in receipts.records] == [(final_name, b"receipt")]
    assert [(record.name, record.data) for record in analyses.records] == [(final_name, b"analysis")]
    assert [(record.name, record.data) for record in settlements.records] == [
        (final_name, b"settlement")
    ]


def test_each_publisher_synchronizes_the_full_fixed_namespace_ancestry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    synchronized: list[Path] = []

    def record_sync(path: Path) -> None:
        synchronized.append(path)

    monkeypatch.setattr(evidence_store, "_sync_directory", record_sync)

    assert (
        publish_evidence(
            tmp_path,
            EvidenceNamespace.IMPACT_ANALYSES,
            _name("a"),
            b"first",
        ).outcome
        == EVIDENCE_CREATED
    )
    assert (
        publish_evidence(
            tmp_path,
            EvidenceNamespace.IMPACT_ANALYSES,
            _name("b"),
            b"second",
        ).outcome
        == EVIDENCE_CREATED
    )

    root = tmp_path
    dot_plan = root / ".plan-tool"
    evidence = dot_plan / "evidence"
    namespace = evidence / "impact-analyses"
    expected_call = [root, dot_plan, root, evidence, dot_plan, namespace, evidence, namespace]
    assert synchronized == expected_call * 2


def test_competing_initializers_publish_one_final_and_sync_the_fixed_ancestry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_sync_file = evidence_store._sync_file
    barrier = threading.Barrier(2)

    def synchronized_file(fd: int) -> None:
        barrier.wait(timeout=5)
        real_sync_file(fd)

    monkeypatch.setattr(evidence_store, "_sync_file", synchronized_file)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                publish_evidence,
                tmp_path,
                EvidenceNamespace.ESCALATIONS,
                _name(),
                payload,
            )
            for payload in (b"first", b"second")
        ]
    results = [future.result() for future in futures]

    assert sorted(result.outcome for result in results) == [EVIDENCE_CREATED, EVIDENCE_EXISTING]
    stored = (_namespace_dir(tmp_path) / _name()).read_bytes()
    assert {result.data for result in results} == {stored}
    assert _namespace_dir(tmp_path).is_dir()


@pytest.mark.parametrize(
    ("namespace", "final_name", "data"),
    [
        ("escalations", _name(), b"payload"),
        (EvidenceNamespace.ESCALATIONS, "not-a-sealed-name", b"payload"),
        (EvidenceNamespace.ESCALATIONS, _name(), bytearray(b"payload")),
    ],
)
def test_publish_rejects_unsealed_inputs_before_storage_access(
    tmp_path: Path,
    namespace: object,
    final_name: str,
    data: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def storage_must_not_open(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("invalid input opened evidence storage")

    monkeypatch.setattr(evidence_store, "_ensure_namespace", storage_must_not_open)

    result = publish_evidence(tmp_path, namespace, final_name, data)  # type: ignore[arg-type]

    assert result.outcome == EVIDENCE_INVALID_INPUT


def test_publish_retries_a_private_temporary_name_without_touching_the_collision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = _namespace_dir(tmp_path)
    directory.mkdir(parents=True)
    collision = directory / f".{_name()}.first.tmp"
    collision.write_bytes(b"another call")
    nonces = iter(("first", "second"))
    monkeypatch.setattr(evidence_store, "_temporary_nonce", lambda: next(nonces))

    result = publish_evidence(tmp_path, EvidenceNamespace.ESCALATIONS, _name(), b"payload")

    assert result.outcome == EVIDENCE_CREATED
    assert collision.read_bytes() == b"another call"
    assert not (directory / f".{_name()}.second.tmp").exists()


def test_publish_rejects_case_folded_nonmatching_collision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = _namespace_dir(tmp_path)
    directory.mkdir(parents=True)
    upper_name = _name("a").upper()
    (directory / upper_name).write_bytes(b"not evidence")
    real_link = evidence_store.os.link

    def case_folded_link(source, destination, *args, **kwargs):  # noqa: ANN001
        if Path(destination).name == _name():
            raise FileExistsError
        return real_link(source, destination, *args, **kwargs)

    monkeypatch.setattr(evidence_store.os, "link", case_folded_link)

    result = publish_evidence(tmp_path, EvidenceNamespace.ESCALATIONS, _name(), b"payload")

    assert result.outcome == EVIDENCE_WRITE_FAILED
    assert (directory / upper_name).read_bytes() == b"not evidence"


def test_publish_uses_full_fsync_for_macos_file_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    class FakeFcntl:
        F_FULLFSYNC = 51

        @staticmethod
        def fcntl(fd: int, command: int) -> None:
            calls.append((fd, command))

    monkeypatch.setattr(evidence_store.sys, "platform", "darwin")
    monkeypatch.setattr(evidence_store, "_fcntl", FakeFcntl)

    result = publish_evidence(tmp_path, EvidenceNamespace.ESCALATIONS, _name(), b"payload")

    assert result.outcome == EVIDENCE_CREATED
    assert [command for _fd, command in calls] == [FakeFcntl.F_FULLFSYNC]


def test_publish_converts_storage_failure_to_write_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken_directory_sync(_path: Path) -> None:
        raise OSError("sync failed")

    monkeypatch.setattr(evidence_store, "_sync_directory", broken_directory_sync)

    result = publish_evidence(tmp_path, EvidenceNamespace.ESCALATIONS, _name(), b"payload")

    assert result.outcome == EVIDENCE_WRITE_FAILED


def test_scan_returns_only_matching_records_in_raw_name_order(tmp_path: Path) -> None:
    directory = _namespace_dir(tmp_path, EvidenceNamespace.IMPACT_ANALYSES)
    directory.mkdir(parents=True)
    late, early = _name("f"), _name("0")
    (directory / late).write_bytes(b"late")
    (directory / early).write_bytes(b"early")
    (directory / f".{_name()}.crash-left.tmp").write_bytes(b"ignored")
    (directory / _name().upper()).write_bytes(b"ignored")
    (directory / "notes.txt").write_bytes(b"ignored")

    result = scan_evidence(tmp_path, EvidenceNamespace.IMPACT_ANALYSES)

    assert result.failure is None
    assert [(record.name, record.data) for record in result.records] == [
        (early, b"early"),
        (late, b"late"),
    ]


def test_scan_empty_namespace_is_read_only(tmp_path: Path) -> None:
    result = scan_evidence(tmp_path, EvidenceNamespace.IMPACT_ANALYSES)

    assert result.records == ()
    assert result.failure is None
    assert not (tmp_path / ".plan-tool").exists()


def test_scan_rejects_unknown_namespace_before_storage_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def storage_must_not_open(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("invalid namespace opened evidence storage")

    monkeypatch.setattr(evidence_store, "_existing_namespace", storage_must_not_open)

    result = scan_evidence(tmp_path, "escalations")  # type: ignore[arg-type]

    assert result.failure == EVIDENCE_INVALID_INPUT


def test_scan_converts_matching_record_read_failure_to_write_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = _namespace_dir(tmp_path)
    directory.mkdir(parents=True)
    (directory / _name()).write_bytes(b"payload")

    def broken_read(_path: Path) -> bytes:
        raise OSError("read failed")

    monkeypatch.setattr(evidence_store, "_read_bytes", broken_read)

    result = scan_evidence(tmp_path, EvidenceNamespace.ESCALATIONS)

    assert result.failure == EVIDENCE_WRITE_FAILED


def test_exact_read_opens_only_its_named_final(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    directory = _namespace_dir(tmp_path)
    directory.mkdir(parents=True)
    requested = _name("a")
    sibling = _name("b")
    (directory / requested).write_bytes(b"requested")
    (directory / sibling).write_bytes(b"unreadable sibling")
    opened: list[Path] = []
    real_read = evidence_store._read_bytes

    def read_requested_only(path: Path) -> bytes:
        opened.append(path)
        if path.name == sibling:
            raise AssertionError("exact read opened a sibling final")
        return real_read(path)

    monkeypatch.setattr(evidence_store, "_read_bytes", read_requested_only)
    monkeypatch.setattr(
        evidence_store.os,
        "scandir",
        lambda _directory: (_ for _ in ()).throw(
            AssertionError("exact read enumerated sibling finals")
        ),
    )

    result = read_evidence_final(tmp_path, EvidenceNamespace.ESCALATIONS, requested)

    assert result.data == b"requested"
    assert result.failure is None
    assert opened == [directory / requested]


def test_exact_read_distinguishes_missing_invalid_and_storage_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = read_evidence_final(tmp_path, EvidenceNamespace.ESCALATIONS, _name())
    invalid = read_evidence_final(tmp_path, EvidenceNamespace.ESCALATIONS, "not-a-final")

    directory = _namespace_dir(tmp_path)
    directory.mkdir(parents=True)
    (directory / _name()).write_bytes(b"payload")

    def broken_read(_path: Path) -> bytes:
        raise OSError("read failed")

    monkeypatch.setattr(evidence_store, "_read_bytes", broken_read)
    unavailable = read_evidence_final(tmp_path, EvidenceNamespace.ESCALATIONS, _name())

    assert missing.failure == "missing"
    assert invalid.failure == EVIDENCE_INVALID_INPUT
    assert unavailable.failure == EVIDENCE_WRITE_FAILED
