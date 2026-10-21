"""Pins the conftest scrub of git's repo-local environment (see TESTING.md)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from plan_tool.cli.gitcommit import worktree_add


def _conftest_module(config: pytest.Config):
    conftest = Path(__file__).with_name("conftest.py").resolve()
    for plugin in config.pluginmanager.get_plugins():
        module_file = getattr(plugin, "__file__", None)
        if module_file and Path(module_file).resolve() == conftest:
            return plugin
    raise AssertionError(f"pytest did not load {conftest} as a plugin")


def test_scrub_stops_an_inherited_git_dir_from_registering_a_worktree_in_that_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pytestconfig: pytest.Config
) -> None:
    real = tmp_path / "real"
    subprocess.run(["git", "init", "-q", str(real)], check=True)
    subprocess.run(
        ["git", "-C", str(real), "-c", "user.name=t", "-c", "user.email=t@e",
         "commit", "-q", "--allow-empty", "-m", "init"],
        check=True,
    )
    not_a_repo = tmp_path / "not-a-repo"
    not_a_repo.mkdir()
    monkeypatch.setenv("GIT_DIR", str(real / ".git"))
    # Stop discovery above tmp_path, so a --basetemp inside a clone cannot reach it.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))

    _conftest_module(pytestconfig)._drop_repo_local_git_env()
    rc, _tail = worktree_add(
        not_a_repo, not_a_repo / "wt", "feat", create=True, start_point="HEAD"
    )

    assert rc != 0
    listed = subprocess.run(
        ["git", "-C", str(real), "worktree", "list", "--porcelain"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert listed.count("worktree ") == 1


def test_no_repo_local_git_variable_reaches_a_test_so_git_calls_cannot_target_the_real_repo() -> None:
    # Pins that conftest runs the scrub at import, not only that the scrub works.
    names = subprocess.run(
        ["git", "rev-parse", "--local-env-vars"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert sorted(name for name in names if name in os.environ) == []


def test_scrub_is_a_no_op_without_a_git_binary_so_git_free_tests_still_run(
    monkeypatch: pytest.MonkeyPatch, pytestconfig: pytest.Config
) -> None:
    monkeypatch.setenv("GIT_DIR", "/nonexistent")

    def no_git(*_args, **_kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", no_git)

    _conftest_module(pytestconfig)._drop_repo_local_git_env()

    assert os.environ["GIT_DIR"] == "/nonexistent"

