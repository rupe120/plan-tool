from __future__ import annotations

import json
from pathlib import Path

import pytest

from plan_tool.repo_lock import (
    RepoMutationLockError,
    acquire_repo_mutation_lock,
    mutation_lock_path,
    release_repo_mutation_lock,
    repo_mutation_lock,
)


def test_repo_mutation_lock_creates_and_releases(tmp_path: Path) -> None:
    with repo_mutation_lock(tmp_path, command="create") as lock:
        assert lock is not None
        assert lock.path.exists()
    assert not (tmp_path / ".plan-tool" / "mutation.lock").exists()


def test_repo_mutation_lock_refuses_active_lock(tmp_path: Path) -> None:
    first = acquire_repo_mutation_lock(tmp_path, command="create")
    try:
        with pytest.raises(RepoMutationLockError, match="another mutating"):
            acquire_repo_mutation_lock(tmp_path, command="jira")
    finally:
        release_repo_mutation_lock(first)


def test_repo_mutation_lock_reclaims_dead_pid(tmp_path: Path) -> None:
    lock_path = tmp_path / ".plan-tool" / "mutation.lock"
    lock_path.parent.mkdir()
    lock_path.write_text(
        json.dumps({"pid": 999999999, "command": "create"}) + "\n",
        encoding="utf-8",
    )

    lock = acquire_repo_mutation_lock(tmp_path, command="jira")
    try:
        assert lock.path == lock_path
    finally:
        release_repo_mutation_lock(lock)


def test_repo_mutation_lock_uses_git_dir_when_present(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    assert (
        mutation_lock_path(tmp_path)
        == tmp_path / ".git" / "plan-tool-mutation.lock"
    )

    with repo_mutation_lock(tmp_path, command="run") as lock:
        assert lock is not None
        assert lock.path == tmp_path / ".git" / "plan-tool-mutation.lock"
        assert not (tmp_path / ".plan-tool" / "mutation.lock").exists()


def test_repo_mutation_lock_uses_linked_worktree_gitdir(tmp_path: Path) -> None:
    actual_git = tmp_path / ".git-worktrees" / "demo"
    actual_git.mkdir(parents=True)
    (tmp_path / ".git").write_text(
        f"gitdir: {actual_git.relative_to(tmp_path)}\n",
        encoding="utf-8",
    )

    assert mutation_lock_path(tmp_path) == actual_git / "plan-tool-mutation.lock"
    with repo_mutation_lock(tmp_path, command="run") as lock:
        assert lock is not None
        assert lock.path == actual_git / "plan-tool-mutation.lock"
        assert not (tmp_path / ".plan-tool" / "mutation.lock").exists()
