"""Immutable opaque evidence storage for roadmap-local consumers."""

from __future__ import annotations

import errno
import os
import re
import secrets
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal

from plan_tool.fileio import sync_directory as _sync_directory

try:  # ``fcntl`` is present on macOS, where the stronger flush is required.
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - exercised on platforms without fcntl.
    _fcntl = None


EVIDENCE_CREATED = "created"
EVIDENCE_EXISTING = "existing"
EVIDENCE_INVALID_INPUT = "invalid-input"
EVIDENCE_WRITE_FAILED = "write-failed"

PublishOutcome = Literal[
    "created",
    "existing",
    "invalid-input",
    "write-failed",
]
ScanFailure = Literal["invalid-input", "write-failed"]
ExactReadFailure = Literal["invalid-input", "missing", "write-failed"]


class EvidenceNamespace(StrEnum):
    """Namespaces whose paths and final-name grammars this leaf owns."""

    ESCALATIONS = "escalations"
    IMPACT_ANALYSES = "impact-analyses"
    DECISION_SETTLEMENTS = "decision-settlements"


_NAMESPACE_COMPONENTS = {
    EvidenceNamespace.ESCALATIONS: (".plan-tool", "evidence", "escalations"),
    EvidenceNamespace.IMPACT_ANALYSES: (".plan-tool", "evidence", "impact-analyses"),
    EvidenceNamespace.DECISION_SETTLEMENTS: (".plan-tool", "evidence", "decision-settlements"),
}
_FINAL_NAME_RE = re.compile(r"[0-9a-f]{64}", re.ASCII)
_TEMP_ATTEMPTS = 32


def namespace_relative_components(namespace: EvidenceNamespace) -> tuple[str, ...]:
    """Return one namespace's fixed path components, for a caller that needs
    to describe a location without deriving it from a hand-copied path."""
    return _NAMESPACE_COMPONENTS[namespace]


@dataclass(frozen=True)
class EvidencePublishResult:
    """The result of one immutable final-name publication attempt."""

    outcome: PublishOutcome
    data: bytes | None = None


@dataclass(frozen=True)
class EvidenceRecord:
    """One opaque, grammar-matching final record."""

    name: str
    data: bytes


@dataclass(frozen=True)
class EvidenceScanResult:
    """A deterministic record listing or its ordinary storage failure."""

    records: tuple[EvidenceRecord, ...] = ()
    failure: ScanFailure | None = None


@dataclass(frozen=True)
class EvidenceExactReadResult:
    """The bytes for one named final or a narrow read failure."""

    data: bytes | None = None
    failure: ExactReadFailure | None = None


class _NoExactFinal(Exception):
    """A lookup collision did not name an evidence final exactly."""


def _valid_namespace(namespace: object) -> bool:
    return isinstance(namespace, EvidenceNamespace) and namespace in _NAMESPACE_COMPONENTS


def _valid_final_name(final_name: object) -> bool:
    return isinstance(final_name, str) and _FINAL_NAME_RE.fullmatch(final_name) is not None


def _sync_file(fd: int) -> None:
    """Flush data, using macOS's stronger file boundary where available."""
    os.fsync(fd)
    if sys.platform != "darwin":
        return
    if _fcntl is None or not hasattr(_fcntl, "F_FULLFSYNC"):
        raise OSError("F_FULLFSYNC is unavailable on this macOS runtime")
    _fcntl.fcntl(fd, _fcntl.F_FULLFSYNC)


def _ensure_namespace(roadmap_dir: Path, namespace: EvidenceNamespace) -> Path:
    """Create and synchronize the fixed namespace ancestry on every call."""
    if not roadmap_dir.is_dir():
        raise FileNotFoundError(f"roadmap directory does not exist: {roadmap_dir}")

    current = roadmap_dir
    _sync_directory(current)
    for component in _NAMESPACE_COMPONENTS[namespace]:
        child = current / component
        try:
            child.mkdir(mode=0o700)
        except FileExistsError:
            if not child.is_dir():
                raise NotADirectoryError(f"evidence namespace component is not a directory: {child}")
        _sync_directory(child)
        _sync_directory(current)
        current = child
    return current


def _existing_namespace(roadmap_dir: Path, namespace: EvidenceNamespace) -> Path | None:
    """Return the fixed namespace without creating a path for a reader."""
    if not roadmap_dir.is_dir():
        raise FileNotFoundError(f"roadmap directory does not exist: {roadmap_dir}")

    current = roadmap_dir
    for component in _NAMESPACE_COMPONENTS[namespace]:
        child = current / component
        if not child.exists():
            return None
        if not child.is_dir():
            raise NotADirectoryError(f"evidence namespace component is not a directory: {child}")
        current = child
    return current


def _temporary_nonce() -> str:
    return secrets.token_hex(16)


def _open_temporary(directory: Path, final_name: str) -> tuple[Path, int]:
    """Open a private temporary without touching another caller's file."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    for _attempt in range(_TEMP_ATTEMPTS):
        path = directory / f".{final_name}.{_temporary_nonce()}.tmp"
        try:
            return path, os.open(path, flags, 0o600)
        except FileExistsError:
            continue
    raise FileExistsError("could not allocate a private evidence temporary")


def _write_all(fd: int, data: bytes) -> None:
    """Write all caller bytes before the final-link attempt."""
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError(errno.EIO, "could not write evidence temporary")
        view = view[written:]


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _read_exact_existing(directory: Path, final_name: str) -> bytes:
    with os.scandir(directory) as entries:
        exact_name_present = any(entry.name == final_name for entry in entries)
    if not exact_name_present:
        raise _NoExactFinal
    _sync_directory(directory)
    return _read_bytes(directory / final_name)


def _read_final_direct(directory: Path, final_name: str) -> bytes:
    """Read the one named final without disclosing namespace siblings."""
    try:
        return _read_bytes(directory / final_name)
    except FileNotFoundError:
        raise _NoExactFinal


def publish_evidence(
    roadmap_dir: Path,
    namespace: EvidenceNamespace,
    final_name: str,
    data: bytes,
) -> EvidencePublishResult:
    """Publish sealed opaque bytes once, or return the exact existing bytes."""
    if (
        not _valid_namespace(namespace)
        or not _valid_final_name(final_name)
        or not isinstance(data, bytes)
    ):
        return EvidencePublishResult(EVIDENCE_INVALID_INPUT)

    temporary: Path | None = None
    fd: int | None = None
    try:
        directory = _ensure_namespace(Path(roadmap_dir), namespace)
        temporary, fd = _open_temporary(directory, final_name)
        try:
            _write_all(fd, data)
            _sync_file(fd)
        finally:
            try:
                os.close(fd)
            finally:
                fd = None

        try:
            os.link(temporary, directory / final_name)
        except FileExistsError:
            try:
                existing = _read_exact_existing(directory, final_name)
            except (_NoExactFinal, OSError):
                return EvidencePublishResult(EVIDENCE_WRITE_FAILED)
            return EvidencePublishResult(EVIDENCE_EXISTING, existing)

        _sync_directory(directory)
        return EvidencePublishResult(EVIDENCE_CREATED, data)
    except OSError:
        return EvidencePublishResult(EVIDENCE_WRITE_FAILED)
    finally:
        if fd is not None:
            os.close(fd)
        if temporary is not None:
            try:
                temporary.unlink()
            except OSError:
                pass


def read_evidence_final(
    roadmap_dir: Path,
    namespace: EvidenceNamespace,
    final_name: object,
) -> EvidenceExactReadResult:
    """Read one existing immutable final without listing sibling records."""
    if not _valid_namespace(namespace) or not _valid_final_name(final_name):
        return EvidenceExactReadResult(failure=EVIDENCE_INVALID_INPUT)
    assert isinstance(final_name, str)

    try:
        directory = _existing_namespace(Path(roadmap_dir), namespace)
        if directory is None:
            return EvidenceExactReadResult(failure="missing")
        return EvidenceExactReadResult(data=_read_final_direct(directory, final_name))
    except _NoExactFinal:
        return EvidenceExactReadResult(failure="missing")
    except OSError:
        return EvidenceExactReadResult(failure=EVIDENCE_WRITE_FAILED)


def scan_evidence(
    roadmap_dir: Path,
    namespace: EvidenceNamespace,
) -> EvidenceScanResult:
    """List grammar-matching opaque final records in raw-name order."""
    if not _valid_namespace(namespace):
        return EvidenceScanResult(failure=EVIDENCE_INVALID_INPUT)

    try:
        directory = _existing_namespace(Path(roadmap_dir), namespace)
        if directory is None:
            return EvidenceScanResult()
        with os.scandir(directory) as entries:
            names = [
                entry.name
                for entry in entries
                if _FINAL_NAME_RE.fullmatch(entry.name) is not None
            ]
        names.sort(key=lambda name: name.encode("ascii"))
        _sync_directory(directory)
        records = tuple(EvidenceRecord(name, _read_bytes(directory / name)) for name in names)
        return EvidenceScanResult(records=records)
    except OSError:
        return EvidenceScanResult(failure=EVIDENCE_WRITE_FAILED)
