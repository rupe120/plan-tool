"""Tests for scripts/split_pr.py: the plan-artifact / code branch splitter."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "split_pr.py"
PLAN_PREFIXES = ("docs/implementation-plans/", "plan-seeds/")


def _env(tmp_path: Path) -> dict[str, str]:
    return {
        **os.environ,
        "HOME": str(tmp_path),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }


class Repo:
    def __init__(self, path: Path, env: dict[str, str]) -> None:
        self.path, self.env = path, env

    def git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=self.path, env=self.env, capture_output=True, text=True, check=check
        )

    def write(self, rel: str, content: str | bytes) -> None:
        target = self.path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content if isinstance(content, bytes) else content.encode())

    def commit(self, message: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def split(self, *extra: str, key: str = "IPPT-1") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), key, "--base", "main", *extra],
            cwd=self.path, env=self.env, capture_output=True, text=True,
        )

    def branches(self) -> set[str]:
        return set(self.git("branch", "--format=%(refname:short)").stdout.split())

    def changed(self, branch: str) -> list[str]:
        return self.git("diff", "--name-only", "--no-renames", "main", branch).stdout.split()


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    root = tmp_path / "repo"
    root.mkdir()
    r = Repo(root, _env(tmp_path))
    r.git("init", "-q", "-b", "main")
    r.write("plan_tool/a.py", "a = 1\n")
    r.write("notes.md", "notes\n")
    r.write("docs/implementation-plans/p.md", "status: planning\n")
    r.write("plan-seeds/s.md", "seed\n")
    r.write("plan-seeds/gone.md", "delete me\n")
    r.commit("base")
    r.git("checkout", "-q", "-b", "work")
    return r


def _mixed_work(r: Repo) -> None:
    r.write("docs/implementation-plans/p.md", "status: completed\n")
    r.write("docs/implementation-plans/plan-details/p/01.md", "detail\n")
    (r.path / "plan-seeds/gone.md").unlink()
    r.write("plan_tool/a.py", "a = 2\n")
    r.write("tests/test_a.py", "def test_a(): pass\n")
    r.write("blob.bin", b"\x00\x01\xff\xfe binary \x00")
    r.git("mv", "notes.md", "plan-seeds/notes.md")
    r.commit("work")


def test_split_makes_one_branch_per_nonempty_path_set_and_leaves_the_work_branch_untouched(repo: Repo) -> None:
    _mixed_work(repo)
    tip = repo.git("rev-parse", "work").stdout
    result = repo.split()
    assert result.returncode == 0, result.stderr
    assert repo.branches() == {"main", "work", "IPPT-1-plan", "IPPT-1-code"}
    assert repo.git("rev-parse", "work").stdout == tip
    assert repo.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "work"
    assert repo.git("status", "--porcelain").stdout == ""
    assert len(repo.git("worktree", "list").stdout.strip().splitlines()) == 1


def test_each_branch_holds_only_its_own_paths(repo: Repo) -> None:
    _mixed_work(repo)
    assert repo.split().returncode == 0
    plan_files, code_files = repo.changed("IPPT-1-plan"), repo.changed("IPPT-1-code")
    assert plan_files and all(f.startswith(PLAN_PREFIXES) for f in plan_files)
    assert code_files and not any(f.startswith(PLAN_PREFIXES) for f in code_files)


def test_the_two_branches_together_reproduce_the_work_tree(repo: Repo) -> None:
    # Covers a delete, a binary file, and a rename that crosses the two path sets.
    _mixed_work(repo)
    assert repo.split().returncode == 0
    repo.git("checkout", "-q", "--detach", "main")
    repo.git("merge", "-q", "--no-edit", "IPPT-1-plan", "IPPT-1-code")
    assert repo.git("diff", "--quiet", "work", "HEAD", check=False).returncode == 0


def test_trailing_whitespace_is_copied_verbatim_even_when_apply_whitespace_is_error(repo: Repo) -> None:
    repo.git("config", "apply.whitespace", "error")
    repo.write("docs/implementation-plans/report.md", "- finding  \n")
    repo.write("plan_tool/a.py", "a = 4  \n")
    repo.commit("trailing whitespace")
    result = repo.split()
    assert result.returncode == 0, result.stderr
    repo.git("checkout", "-q", "--detach", "main")
    repo.git("merge", "-q", "--no-edit", "IPPT-1-plan", "IPPT-1-code")
    assert repo.git("diff", "--quiet", "work", "HEAD", check=False).returncode == 0


def test_a_dirty_working_tree_is_refused_and_creates_nothing(repo: Repo) -> None:
    _mixed_work(repo)
    repo.write("scratch.txt", "untracked\n")
    result = repo.split()
    assert result.returncode == 2
    assert "uncommitted changes" in result.stderr
    assert repo.branches() == {"main", "work"}


def test_an_existing_target_branch_is_refused_and_no_sibling_is_created(repo: Repo) -> None:
    _mixed_work(repo)
    repo.git("branch", "IPPT-1-code")
    result = repo.split()
    assert result.returncode == 2
    assert "IPPT-1-code" in result.stderr
    assert repo.branches() == {"main", "work", "IPPT-1-code"}


def test_dry_run_lists_both_sets_and_creates_no_branch(repo: Repo) -> None:
    _mixed_work(repo)
    result = repo.split("--dry-run")
    assert result.returncode == 0
    assert "IPPT-1-plan" in result.stdout and "IPPT-1-code" in result.stdout
    assert repo.branches() == {"main", "work"}


def test_a_code_only_branch_makes_only_a_code_branch_and_says_so(repo: Repo) -> None:
    repo.write("plan_tool/a.py", "a = 3\n")
    repo.commit("code only")
    result = repo.split()
    assert result.returncode == 0
    assert "no plan artifacts changed" in result.stdout
    assert repo.branches() == {"main", "work", "IPPT-1-code"}


def test_a_branch_with_no_changes_says_there_is_nothing_to_split(repo: Repo) -> None:
    result = repo.split()
    assert result.returncode == 0
    assert "nothing to split" in result.stdout
    assert repo.branches() == {"main", "work"}


def test_a_malformed_ticket_key_is_rejected(repo: Repo) -> None:
    _mixed_work(repo)
    result = repo.split(key="not-a-key")
    assert result.returncode == 2
    assert "ticket key" in result.stderr
    assert repo.branches() == {"main", "work"}


def test_a_failing_commit_hook_blocks_the_split_and_leaves_no_branch_or_worktree(repo: Repo) -> None:
    # The snapshot commits run the repository's hooks; none is bypassed.
    _mixed_work(repo)
    hooks = repo.path.parent / "hooks"
    hooks.mkdir()
    hook = hooks / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    repo.git("config", "core.hooksPath", str(hooks))
    result = repo.split()
    assert result.returncode == 2
    assert repo.branches() == {"main", "work"}
    assert len(repo.git("worktree", "list").stdout.strip().splitlines()) == 1
