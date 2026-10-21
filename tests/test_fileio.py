from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from plan_tool import fileio
from plan_tool.fileio import (
    atomic_write_bytes,
    atomic_write_text,
    durable_create_text,
    durable_write_bytes,
    durable_write_text,
)


def test_atomic_write_text_replaces_content(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "config.json"
    atomic_write_text(target, "new\n")
    assert target.read_text(encoding="utf-8") == "new\n"


def test_atomic_write_text_preserves_old_content_when_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "config.json"
    target.write_text("old\n", encoding="utf-8")

    def boom(src, dst):  # noqa: ANN001
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError, match="replace failed"):
        atomic_write_text(target, "new\n")

    assert target.read_text(encoding="utf-8") == "old\n"
    assert not list(tmp_path.glob(".*.tmp"))


def test_atomic_write_bytes_preserves_lf_payload_on_every_platform(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The structural publisher must never turn approved LF bytes into CRLF."""
    target = tmp_path / "artifact.md"
    payload = b"first line\nsecond line\n"
    monkeypatch.setattr(fileio.os, "linesep", "\r\n")

    atomic_write_bytes(target, payload)

    assert target.read_bytes() == payload


def test_atomic_write_bytes_preserves_old_content_when_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "artifact.md"
    target.write_bytes(b"old\n")

    def boom(src, dst):  # noqa: ANN001
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError, match="replace failed"):
        atomic_write_bytes(target, b"new\n")

    assert target.read_bytes() == b"old\n"
    assert not list(tmp_path.glob(".*.tmp"))


def test_durable_write_text_replaces_content(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    target.write_text("old\n", encoding="utf-8")
    durable_write_text(target, "new\n")
    assert target.read_text(encoding="utf-8") == "new\n"
    assert not list(tmp_path.glob(".*.tmp"))


def test_durable_write_bytes_syncs_before_and_after_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order: list[str] = []
    real_fsync, real_replace = os.fsync, os.replace

    def spy_fsync(fd: int) -> None:
        order.append("fsync")
        real_fsync(fd)

    def spy_replace(src, dst):  # noqa: ANN001
        order.append("replace")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "fsync", spy_fsync)
    monkeypatch.setattr(os, "replace", spy_replace)

    durable_write_bytes(tmp_path / "nested" / "artifact.md", b"bytes\n")

    assert order == ["fsync", "replace", "fsync"]
    assert (tmp_path / "nested" / "artifact.md").read_bytes() == b"bytes\n"


def test_durable_write_text_syncs_before_and_after_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Text and byte durable writes preserve the same publication boundary."""
    order: list[str] = []
    real_fsync, real_replace = os.fsync, os.replace

    def spy_fsync(fd):  # noqa: ANN001
        order.append("fsync")
        return real_fsync(fd)

    def spy_replace(src, dst):  # noqa: ANN001
        order.append("replace")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "fsync", spy_fsync)
    monkeypatch.setattr(os, "replace", spy_replace)
    durable_write_text(tmp_path / "durable.json", "{}\n")
    assert order == ["fsync", "replace", "fsync"]


def test_durable_write_text_does_not_create_missing_parents(tmp_path: Path) -> None:
    """Deliberate divergence from ``atomic_write_text``, which does mkdir.

    Callers of the durable writer own their directory; conjuring the tree
    would hide a mis-computed path instead of failing on it.
    """
    target = tmp_path / "absent" / "config.json"
    with pytest.raises((FileNotFoundError, NotADirectoryError)):
        durable_write_text(target, "{}\n")
    assert not target.parent.exists()


def test_durable_write_text_cleans_up_tmp_when_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "config.json"
    target.write_text("old\n", encoding="utf-8")

    def boom(src, dst):  # noqa: ANN001
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError, match="replace failed"):
        durable_write_text(target, "new\n")

    assert target.read_text(encoding="utf-8") == "old\n"
    assert not list(tmp_path.glob(".*.tmp"))


def test_durable_create_text_publishes_a_private_new_file(tmp_path: Path) -> None:
    target = tmp_path / "config.json"

    durable_create_text(target, "new\n")

    assert target.read_text(encoding="utf-8") == "new\n"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".*.tmp"))


def test_durable_create_text_never_replaces_an_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    target.write_text("old\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        durable_create_text(target, "new\n")

    assert target.read_text(encoding="utf-8") == "old\n"
    assert not list(tmp_path.glob(".*.tmp"))


def test_durable_create_text_syncs_before_and_after_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order: list[str] = []
    real_fsync, real_link = os.fsync, os.link

    def spy_fsync(fd: int) -> None:
        order.append("fsync")
        real_fsync(fd)

    def spy_link(src, dst):  # noqa: ANN001
        order.append("link")
        real_link(src, dst)

    monkeypatch.setattr(os, "fsync", spy_fsync)
    monkeypatch.setattr(os, "link", spy_link)

    durable_create_text(tmp_path / "config.json", "new\n")

    assert order == ["fsync", "link", "fsync"]


def test_durable_create_text_cleans_up_tmp_when_publication_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "config.json"

    def boom(src, dst):  # noqa: ANN001
        raise OSError("link failed")

    monkeypatch.setattr(os, "link", boom)
    with pytest.raises(OSError, match="link failed"):
        durable_create_text(target, "new\n")

    assert not target.exists()
    assert not list(tmp_path.glob(".*.tmp"))
