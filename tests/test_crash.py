"""Tests for plan_tool.crash.save_crash_traceback."""

from __future__ import annotations

from pathlib import Path

import pytest

from plan_tool.crash import CRASHES_REL, crashes_root, save_crash_traceback


def test_writes_traceback_under_crashes_label_dir(tmp_path: Path) -> None:
    path = save_crash_traceback(tmp_path, "my-plan", tb_text="boom\nframe\n")
    assert path is not None
    # Lives under <repo>/.plan-tool/crashes/<label>/
    assert path.parent == crashes_root(tmp_path) / "my-plan"
    assert path.parent.parent == tmp_path.joinpath(*CRASHES_REL)
    assert path.suffix == ".txt"
    assert path.read_text(encoding="utf-8") == "boom\nframe\n"


def test_label_is_sanitized(tmp_path: Path) -> None:
    # Slashes / spaces must not escape the crashes dir or nest surprise
    # subdirectories — they collapse to single dashes.
    path = save_crash_traceback(
        tmp_path, "feature/foo bar", tb_text="x"
    )
    assert path is not None
    assert path.parent == crashes_root(tmp_path) / "feature-foo-bar"


def test_empty_label_falls_back_to_unknown(tmp_path: Path) -> None:
    path = save_crash_traceback(tmp_path, "///", tb_text="x")
    assert path is not None
    assert path.parent == crashes_root(tmp_path) / "unknown"


@pytest.mark.parametrize("label", [".", "..", " . ", " .. "])
def test_dot_labels_cannot_escape_crashes_dir(
    tmp_path: Path, label: str
) -> None:
    # Dots survive the char allowlist, so a label that sanitizes to "."
    # or ".." must be rejected explicitly -- otherwise the file lands in
    # the crashes dir itself or its parent (.plan-tool/). (A label like
    # "../.." collapses its slashes to "..-..", which is already safe.)
    path = save_crash_traceback(tmp_path, label, tb_text="x")
    assert path is not None
    assert path.parent == crashes_root(tmp_path) / "unknown"
    # Stays strictly under the crashes root.
    assert crashes_root(tmp_path) in path.parents


def test_best_effort_returns_none_on_unwritable_root(tmp_path: Path) -> None:
    # A regular file where the .plan-tool dir should go makes mkdir raise
    # OSError; the helper must swallow it and return None.
    (tmp_path / ".plan-tool").write_text("not a dir", encoding="utf-8")
    assert save_crash_traceback(tmp_path, "p", tb_text="x") is None
