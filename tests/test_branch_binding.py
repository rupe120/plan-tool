"""Tests for plan_tool.branch_binding — the ad-hoc plan→branch override store."""

from __future__ import annotations

import subprocess
import shutil
from pathlib import Path

import pytest

from plan_tool.branch_binding import (
    BranchBindingError,
    all_bindings,
    clear_binding,
    get_binding,
    reverse_binding,
    set_binding,
)

_GIT_TEMPLATE: Path | None = None


@pytest.fixture(scope="session", autouse=True)
def _empty_git_template(tmp_path_factory: pytest.TempPathFactory):
    """Provide isolated binding stores with local Git identity."""
    global _GIT_TEMPLATE
    root = tmp_path_factory.mktemp("branch-binding-git-template")
    for cmd in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@example.com"],
        ["git", "config", "user.name", "Test"],
    ):
        subprocess.run(cmd, cwd=root, check=True, capture_output=True)
    _GIT_TEMPLATE = root / ".git"
    yield
    _GIT_TEMPLATE = None


def _init_git_repo(root: Path) -> None:
    assert _GIT_TEMPLATE is not None
    shutil.copytree(_GIT_TEMPLATE, root / ".git")


def test_get_binding_unset_returns_none(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    assert get_binding(tmp_path, "my-plan") is None


def test_set_then_get_round_trips(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    set_binding(tmp_path, "my-plan", "feat/x")
    assert get_binding(tmp_path, "my-plan") == "feat/x"


def test_set_overwrites_existing(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    set_binding(tmp_path, "my-plan", "feat/x")
    set_binding(tmp_path, "my-plan", "other")
    assert get_binding(tmp_path, "my-plan") == "other"


def test_set_empty_branch_raises(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    with pytest.raises(BranchBindingError):
        set_binding(tmp_path, "my-plan", "")
    with pytest.raises(BranchBindingError):
        set_binding(tmp_path, "my-plan", "   ")
    assert get_binding(tmp_path, "my-plan") is None


def test_set_empty_slug_raises(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    with pytest.raises(BranchBindingError):
        set_binding(tmp_path, "", "feat/x")


def test_set_outside_repo_raises(tmp_path: Path) -> None:
    with pytest.raises(BranchBindingError):
        set_binding(tmp_path, "my-plan", "feat/x")


def test_clear_existing_returns_true(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    set_binding(tmp_path, "my-plan", "feat/x")
    assert clear_binding(tmp_path, "my-plan") is True
    assert get_binding(tmp_path, "my-plan") is None


def test_clear_absent_returns_false(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    assert clear_binding(tmp_path, "my-plan") is False


def test_clear_is_idempotent(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    set_binding(tmp_path, "my-plan", "feat/x")
    assert clear_binding(tmp_path, "my-plan") is True
    assert clear_binding(tmp_path, "my-plan") is False


def test_all_bindings_empty(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    assert all_bindings(tmp_path) == {}


def test_all_bindings_returns_all_pairs(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    set_binding(tmp_path, "plan-a", "feat/a")
    set_binding(tmp_path, "plan-b", "feat/b")
    assert all_bindings(tmp_path) == {"plan-a": "feat/a", "plan-b": "feat/b"}


def test_reverse_binding_found(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    set_binding(tmp_path, "plan-a", "feat/a")
    assert reverse_binding(tmp_path, "feat/a") == "plan-a"


def test_reverse_binding_not_found(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    set_binding(tmp_path, "plan-a", "feat/a")
    assert reverse_binding(tmp_path, "feat/unbound") is None


def test_reverse_binding_deterministic_on_collision(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    set_binding(tmp_path, "plan-z", "feat/shared")
    set_binding(tmp_path, "plan-a", "feat/shared")
    assert reverse_binding(tmp_path, "feat/shared") == "plan-a"
