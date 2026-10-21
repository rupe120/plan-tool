"""Small filesystem write helpers shared by leaf modules.

Two atomic text writers, and the difference is load-bearing — pick deliberately:
:func:`atomic_write_text` is atomic but **not durable** (no ``fsync``), and
creates missing parents; :func:`durable_write_text` syncs its file and
directory and requires the parent to exist. :func:`atomic_write_bytes`
provides the
same atomic, parent-creating semantics for byte-exact payloads.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Write ``text`` via a sibling tempfile and atomic rename.

    The tempfile lives in the target directory so ``os.replace`` is a
    same-filesystem operation. A failed write leaves the previous target
    content in place.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp_path.write_text(text, encoding=encoding)
        os.replace(tmp_path, path)
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write ``data`` unchanged via a binary sibling tempfile and rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp_path.write_bytes(data)
        os.replace(tmp_path, path)
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass


def durable_write_bytes(path: Path, data: bytes) -> None:
    """Atomically replace a byte sidecar after syncing its file and directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(
        mode="wb",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    tmp_path = Path(tmp.name)
    try:
        try:
            tmp.write(data)
            tmp.flush()
            os.fsync(tmp.fileno())
        finally:
            tmp.close()
        os.replace(tmp_path, path)
        sync_directory(path.parent)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp_path.unlink()
        raise


def is_write_temp_name(name: str) -> bool:
    """True for the ``.<target>.<random>.tmp`` leftover of an interrupted durable write."""
    return name.startswith(".") and name.endswith(".tmp") and name.count(".") >= 3


def durable_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Write ``text`` to ``path`` atomically **and durably**.

    Flushes and ``fsync``s the sibling tempfile before ``os.replace``, then
    syncs the parent directory, so a power loss or kernel panic cannot leave
    the rename visible while the
    bytes are still only in the page cache. Use this for state a later run
    reads back and trusts (grounding baselines, saved review sidecars,
    purity caches, the manifest).

    Differs from :func:`atomic_write_text` in two ways, both deliberate: it
    syncs the file and directory, and it does **not** create missing parents.
    A write into a directory that does not exist raises rather than conjuring
    the tree.
    """
    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        encoding=encoding,
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    tmp_path = Path(tmp.name)
    try:
        try:
            tmp.write(text)
            tmp.flush()
            os.fsync(tmp.fileno())
        finally:
            tmp.close()
        os.replace(tmp_path, path)
        sync_directory(path.parent)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp_path.unlink()
        raise


def durable_create_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Create ``path`` once without exposing a partial final file.

    See ``DATA_CONTRACT.md``.
    """
    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        encoding=encoding,
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    tmp_path = Path(tmp.name)
    try:
        try:
            tmp.write(text)
            tmp.flush()
            os.fsync(tmp.fileno())
        finally:
            tmp.close()
        os.link(tmp_path, path)
        sync_directory(path.parent)
    finally:
        with contextlib.suppress(OSError):
            tmp_path.unlink()


def sync_directory(path: Path) -> None:
    """Persist a just-published directory entry."""
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    fd = os.open(path, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
