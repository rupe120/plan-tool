"""Tests for plan_tool.cli.gitcommit — the shared ``--commit`` git plumbing."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from plan_tool.cli.gitcommit import (
    branch_exists,
    checkout_existing_branch,
    clone_repo,
    commit_receipt,
    create_and_checkout_branch,
    current_branch,
    default_branch,
    ignored_recommended_paths,
    list_branches,
    path_is_gitignored,
    remote_collisions,
    unexpected_dirty_paths,
    warn_recommended_paths_ignored,
    worktree_add,
    worktree_list,
    worktree_prune,
    worktree_remove,
)


_GIT_TEMPLATE: Path | None = None


@pytest.fixture(scope="session", autouse=True)
def _empty_git_template(tmp_path_factory: pytest.TempPathFactory):
    """Provide isolated repos with local identity but no initial commit."""
    global _GIT_TEMPLATE
    root = tmp_path_factory.mktemp("git-template")
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
    if _GIT_TEMPLATE is not None:
        shutil.copytree(_GIT_TEMPLATE, root / ".git")
        return
    for cmd in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@example.com"],
        ["git", "config", "user.name", "Test"],
    ):
        subprocess.run(cmd, cwd=root, check=True, capture_output=True)


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True
    )


def _commit_initial(root: Path) -> str:
    """Seed one commit so HEAD points at a branch; return its sha."""
    (root / "f.txt").write_text("x\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return _git(root, "rev-parse", "HEAD").stdout.decode().strip()


class TestCommitReceipt:
    def _write_ignored_receipt(self, root: Path) -> Path:
        _init_git_repo(root)
        _commit_initial(root)
        (root / ".gitignore").write_text(
            "**/.plan-tool/evidence/\n", encoding="utf-8"
        )
        _git(root, "add", ".gitignore")
        _git(root, "commit", "-q", "-m", "ignore evidence")
        receipt = root / ".plan-tool" / "evidence" / "escalations" / "r.json"
        receipt.parent.mkdir(parents=True)
        receipt.write_text('{"receipt": true}\n', encoding="utf-8")
        return receipt

    def test_receipt_commit_forces_only_ignored_receipt_into_head(
        self, tmp_path: Path
    ) -> None:
        receipt = self._write_ignored_receipt(tmp_path)

        rc, tail = commit_receipt(tmp_path, receipt, "persist receipt")

        assert rc == 0, tail
        assert _git(
            tmp_path, "show", "--format=", "--name-only", "HEAD"
        ).stdout.decode().splitlines() == [
            ".plan-tool/evidence/escalations/r.json"
        ]
        assert _git(
            tmp_path, "status", "--porcelain", "--", str(receipt)
        ).stdout == b""

    def test_receipt_commit_rejects_attribute_transformed_bytes_before_staging(
        self, tmp_path: Path
    ) -> None:
        receipt = self._write_ignored_receipt(tmp_path)
        (tmp_path / ".gitattributes").write_text(
            ".plan-tool/evidence/escalations/r.json filter=uppercase\n",
            encoding="utf-8",
        )
        _git(tmp_path, "add", ".gitattributes")
        _git(tmp_path, "commit", "-q", "-m", "configure receipt filter")
        _git(tmp_path, "config", "filter.uppercase.clean", "tr a-z A-Z")
        before = _git(tmp_path, "rev-parse", "HEAD").stdout

        rc, tail = commit_receipt(tmp_path, receipt, "persist receipt")

        assert rc != 0
        assert tail == "Git attributes would transform receipt bytes"
        assert _git(tmp_path, "rev-parse", "HEAD").stdout == before
        assert receipt.read_text(encoding="utf-8") == '{"receipt": true}\n'
        assert _git(tmp_path, "ls-files", "--stage", "--", str(receipt)).stdout == b""

    def test_receipt_commit_treats_glob_characters_as_literal_pathspecs(
        self, tmp_path: Path
    ) -> None:
        _init_git_repo(tmp_path)
        _commit_initial(tmp_path)
        receipt = tmp_path / "feed*back" / "receipt.json"
        receipt.parent.mkdir()
        receipt.write_text('{"receipt": true}\n', encoding="utf-8")
        sibling = tmp_path / "feedBback" / "receipt.json"
        sibling.parent.mkdir()
        sibling.write_text('{"sibling": true}\n', encoding="utf-8")

        rc, tail = commit_receipt(tmp_path, receipt, "persist receipt")

        assert rc == 0, tail
        assert _git(
            tmp_path, "show", "--format=", "--name-only", "HEAD"
        ).stdout.decode().splitlines() == ["feed*back/receipt.json"]
        assert _git(
            tmp_path, "status", "--porcelain", "--", str(sibling)
        ).stdout == b"?? feedBback/receipt.json\n"

    def test_receipt_commit_preserves_unrelated_staged_change(
        self, tmp_path: Path
    ) -> None:
        receipt = self._write_ignored_receipt(tmp_path)
        unrelated = tmp_path / "f.txt"
        unrelated.write_text("staged\n", encoding="utf-8")
        _git(tmp_path, "add", "--", "f.txt")

        rc, tail = commit_receipt(tmp_path, receipt, "persist receipt")

        assert rc == 0, tail
        assert unrelated.read_text(encoding="utf-8") == "staged\n"
        assert _git(tmp_path, "status", "--porcelain", "--", "f.txt").stdout == (
            b"M  f.txt\n"
        )
        assert b"staged" in _git(
            tmp_path, "diff", "--cached", "--", "f.txt"
        ).stdout
        assert _git(
            tmp_path, "show", "--format=", "--name-only", "HEAD"
        ).stdout == b".plan-tool/evidence/escalations/r.json\n"

    def test_receipt_commit_preserves_unrelated_unstaged_change(
        self, tmp_path: Path
    ) -> None:
        receipt = self._write_ignored_receipt(tmp_path)
        unrelated = tmp_path / "f.txt"
        unrelated.write_text("unstaged\n", encoding="utf-8")

        rc, tail = commit_receipt(tmp_path, receipt, "persist receipt")

        assert rc == 0, tail
        assert unrelated.read_text(encoding="utf-8") == "unstaged\n"
        assert _git(tmp_path, "status", "--porcelain", "--", "f.txt").stdout == (
            b" M f.txt\n"
        )
        assert b"unstaged" in _git(
            tmp_path, "diff", "--", "f.txt"
        ).stdout

    def test_receipt_commit_failure_unstages_only_receipt_after_simple_hook_rejection(
        self, tmp_path: Path
    ) -> None:
        receipt = self._write_ignored_receipt(tmp_path)
        hook = tmp_path / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)

        rc, _tail = commit_receipt(tmp_path, receipt, "persist receipt")

        assert rc != 0
        assert receipt.read_text(encoding="utf-8") == '{"receipt": true}\n'
        assert _git(tmp_path, "ls-files", "--stage", "--", str(receipt)).stdout == b""

    def test_receipt_commit_process_launch_failure_before_staging_returns_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        receipt = self._write_ignored_receipt(tmp_path)
        unrelated = tmp_path / "f.txt"
        unrelated.write_text("staged\n", encoding="utf-8")
        _git(tmp_path, "add", "--", "f.txt")
        before = _git(tmp_path, "status", "--porcelain").stdout
        import plan_tool.cli.gitcommit as gc

        def _no_git(*_args, **_kwargs):
            raise OSError("git is unavailable")

        with monkeypatch.context() as context:
            context.setattr(gc.subprocess, "run", _no_git)

            rc, tail = commit_receipt(tmp_path, receipt, "persist receipt")

        assert rc != 0
        assert "git subprocess error: git is unavailable" == tail
        assert receipt.read_text(encoding="utf-8") == '{"receipt": true}\n'
        assert _git(tmp_path, "status", "--porcelain").stdout == before
        assert _git(tmp_path, "ls-files", "--stage", "--", str(receipt)).stdout == b""

    def test_receipt_commit_process_launch_failure_after_staging_unstages_only_receipt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        receipt = self._write_ignored_receipt(tmp_path)
        unrelated = tmp_path / "f.txt"
        unrelated.write_text("staged\n", encoding="utf-8")
        _git(tmp_path, "add", "--", "f.txt")
        import plan_tool.cli.gitcommit as gc

        real_run = gc.subprocess.run

        def _fail_commit(args, *args_rest, **kwargs):
            if args[:2] == ["git", "commit"]:
                raise OSError("git is unavailable")
            return real_run(args, *args_rest, **kwargs)

        with monkeypatch.context() as context:
            context.setattr(gc.subprocess, "run", _fail_commit)

            rc, tail = commit_receipt(tmp_path, receipt, "persist receipt")

        assert rc != 0
        assert "git subprocess error: git is unavailable" == tail
        assert receipt.read_text(encoding="utf-8") == '{"receipt": true}\n'
        assert _git(tmp_path, "ls-files", "--stage", "--", str(receipt)).stdout == b""
        assert _git(tmp_path, "status", "--porcelain", "--", "f.txt").stdout == (
            b"M  f.txt\n"
        )

    def test_receipt_commit_interruption_propagates_without_cleanup(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        receipt = self._write_ignored_receipt(tmp_path)
        unrelated = tmp_path / "f.txt"
        unrelated.write_text("staged\n", encoding="utf-8")
        _git(tmp_path, "add", "--", "f.txt")
        import plan_tool.cli.gitcommit as gc

        real_run = gc.subprocess.run

        def _interrupt_commit(args, *args_rest, **kwargs):
            if args[:2] == ["git", "commit"]:
                raise KeyboardInterrupt
            return real_run(args, *args_rest, **kwargs)

        with monkeypatch.context() as context:
            context.setattr(gc.subprocess, "run", _interrupt_commit)

            with pytest.raises(KeyboardInterrupt):
                commit_receipt(tmp_path, receipt, "persist receipt")

        assert receipt.read_text(encoding="utf-8") == '{"receipt": true}\n'
        assert _git(tmp_path, "ls-files", "--stage", "--", str(receipt)).stdout
        assert _git(tmp_path, "status", "--porcelain", "--", "f.txt").stdout == (
            b"M  f.txt\n"
        )


class TestPathIsGitignored:
    def test_ignored_path_is_true(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        (tmp_path / ".gitignore").write_text(".plan-tool/\n", encoding="utf-8")
        ignored = tmp_path / ".plan-tool" / "reviews" / "demo.json"
        ignored.parent.mkdir(parents=True)
        ignored.write_text("{}\n", encoding="utf-8")
        assert path_is_gitignored(tmp_path, ignored) is True

    def test_tracked_path_is_false(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        (tmp_path / ".gitignore").write_text(".plan-tool/\n", encoding="utf-8")
        tracked = tmp_path / "docs" / "reports" / "demo.json"
        tracked.parent.mkdir(parents=True)
        tracked.write_text("{}\n", encoding="utf-8")
        assert path_is_gitignored(tmp_path, tracked) is False

    def test_non_repo_returns_false(self, tmp_path: Path) -> None:
        # No git work tree: check-ignore exits 128, which must read as "not
        # proven ignored" (False) so the guard never false-warns.
        assert path_is_gitignored(tmp_path, tmp_path / "x.json") is False


class TestIgnoredRecommendedPaths:
    def _seed(self, root: Path) -> None:
        """Create both recommended-to-commit paths so existence checks pass."""
        (root / ".plan-tool").mkdir()
        (root / ".plan-tool" / "plans.json").write_text(
            '{"plans": []}\n', encoding="utf-8"
        )
        (root / ".plan-tool" / "lessons").mkdir()
        (root / ".plan-tool" / "lessons" / "project.md").write_text(
            "x\n", encoding="utf-8"
        )
        (root / ".plan-tool" / "project.json").write_text(
            '{"schema_version": 1}\n', encoding="utf-8"
        )

    def test_wholesale_ignore_flags_all_committed_paths(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        self._seed(tmp_path)
        (tmp_path / ".gitignore").write_text(".plan-tool/\n", encoding="utf-8")
        ignored = {p.as_posix() for p in ignored_recommended_paths(tmp_path)}
        assert ignored == {
            ".plan-tool/plans.json",
            ".plan-tool/lessons",
            ".plan-tool/project.json",
        }

    def test_committed_paths_not_flagged(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        self._seed(tmp_path)
        # Only the runtime subdirs are ignored — the recommended paths are not.
        (tmp_path / ".gitignore").write_text(
            ".plan-tool/runs\n.plan-tool/reviews\n", encoding="utf-8"
        )
        assert ignored_recommended_paths(tmp_path) == []

    def test_absent_paths_skipped(self, tmp_path: Path) -> None:
        # plans.json exists but lessons/ does not; only the existing one can
        # be flagged.
        _init_git_repo(tmp_path)
        (tmp_path / ".plan-tool").mkdir()
        (tmp_path / ".plan-tool" / "plans.json").write_text(
            '{"plans": []}\n', encoding="utf-8"
        )
        (tmp_path / ".gitignore").write_text(".plan-tool/\n", encoding="utf-8")
        ignored = {p.as_posix() for p in ignored_recommended_paths(tmp_path)}
        assert ignored == {".plan-tool/plans.json"}

    def test_non_repo_returns_empty(self, tmp_path: Path) -> None:
        self._seed(tmp_path)
        assert ignored_recommended_paths(tmp_path) == []

    def test_warn_emits_when_ignored(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        self._seed(tmp_path)
        (tmp_path / ".gitignore").write_text(".plan-tool/\n", encoding="utf-8")
        messages: list[str] = []
        warn_recommended_paths_ignored(tmp_path, messages.append)
        assert len(messages) == 1
        assert ".plan-tool/plans.json" in messages[0]
        assert ".plan-tool/project.json" in messages[0]
        assert ".gitignore" in messages[0]

    def test_warn_silent_when_committed(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        self._seed(tmp_path)
        messages: list[str] = []
        warn_recommended_paths_ignored(tmp_path, messages.append)
        assert messages == []


class TestCurrentBranch:
    def test_returns_branch_name_on_branch(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        _commit_initial(tmp_path)
        expected = (
            _git(tmp_path, "symbolic-ref", "--short", "HEAD")
            .stdout.decode()
            .strip()
        )
        assert current_branch(tmp_path) == expected

    def test_detached_head_returns_none(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        sha = _commit_initial(tmp_path)
        _git(tmp_path, "checkout", "-q", sha)
        assert current_branch(tmp_path) is None

    def test_non_repo_returns_none(self, tmp_path: Path) -> None:
        assert current_branch(tmp_path) is None


class TestDefaultBranch:
    def test_env_override_wins(self, tmp_path: Path, monkeypatch) -> None:
        _init_git_repo(tmp_path)
        _commit_initial(tmp_path)
        _git(
            tmp_path,
            "symbolic-ref",
            "refs/remotes/origin/HEAD",
            "refs/remotes/origin/main",
        )
        monkeypatch.setenv("PLAN_TOOL_DEFAULT_BRANCH", "release")
        assert default_branch(tmp_path) == "release"

    def test_empty_env_falls_through(self, tmp_path: Path, monkeypatch) -> None:
        _init_git_repo(tmp_path)
        _commit_initial(tmp_path)
        monkeypatch.setenv("PLAN_TOOL_DEFAULT_BRANCH", "   ")
        assert default_branch(tmp_path) is None

    def test_origin_head_resolves_and_strips_prefix(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.delenv("PLAN_TOOL_DEFAULT_BRANCH", raising=False)
        _init_git_repo(tmp_path)
        _commit_initial(tmp_path)
        _git(
            tmp_path,
            "symbolic-ref",
            "refs/remotes/origin/HEAD",
            "refs/remotes/origin/main",
        )
        assert default_branch(tmp_path) == "main"

    def test_no_origin_head_returns_none(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.delenv("PLAN_TOOL_DEFAULT_BRANCH", raising=False)
        _init_git_repo(tmp_path)
        _commit_initial(tmp_path)
        assert default_branch(tmp_path) is None


class TestBranchExists:
    def test_existing_local_branch_is_true(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        _commit_initial(tmp_path)
        _git(tmp_path, "branch", "feat")
        assert branch_exists(tmp_path, "feat") is True

    def test_absent_branch_is_false(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        _commit_initial(tmp_path)
        assert branch_exists(tmp_path, "nope") is False

    def test_non_repo_is_false(self, tmp_path: Path) -> None:
        assert branch_exists(tmp_path, "main") is False


class TestCreateAndCheckoutBranch:
    def test_creates_and_switches_rc_zero(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        _commit_initial(tmp_path)
        rc, tail = create_and_checkout_branch(tmp_path, "feature-x")
        assert rc == 0
        assert tail == ""
        assert current_branch(tmp_path) == "feature-x"

    def test_existing_branch_fails_nonzero(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        _commit_initial(tmp_path)
        _git(tmp_path, "branch", "dup")
        rc, tail = create_and_checkout_branch(tmp_path, "dup")
        assert rc != 0
        assert tail != ""


class TestCheckoutExistingBranch:
    def test_switches_to_existing_rc_zero(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        _commit_initial(tmp_path)
        _git(tmp_path, "branch", "target")
        rc, _tail = checkout_existing_branch(tmp_path, "target")
        assert rc == 0
        assert current_branch(tmp_path) == "target"

    def test_missing_branch_fails_nonzero(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        _commit_initial(tmp_path)
        rc, tail = checkout_existing_branch(tmp_path, "ghost")
        assert rc != 0
        assert tail != ""


class TestListBranches:
    def test_lists_local_branches(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        _commit_initial(tmp_path)
        _git(tmp_path, "branch", "one")
        _git(tmp_path, "branch", "two")
        branches = list_branches(tmp_path)
        assert "one" in branches
        assert "two" in branches

    def test_includes_remote_tracking_refs(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        _commit_initial(tmp_path)
        _git(tmp_path, "update-ref", "refs/remotes/origin/main", "HEAD")
        assert "origin/main" in list_branches(tmp_path)

    def test_non_repo_returns_empty(self, tmp_path: Path) -> None:
        assert list_branches(tmp_path) == []


class TestRemoteCollisions:
    def test_single_remote_collides(self) -> None:
        assert remote_collisions(
            ["origin/plan/x"], "plan/x", ["plan/"]
        ) == ["origin/plan/x"]

    def test_multi_remote_both_surfaced(self) -> None:
        assert remote_collisions(
            ["origin/plan/x", "fork/plan/x"], "plan/x", ["plan/"]
        ) == ["fork/plan/x", "origin/plan/x"]

    def test_remote_head_is_filtered(self) -> None:
        assert remote_collisions(["origin/HEAD"], "HEAD", ["plan/"]) == []

    def test_non_matching_remote_no_collision(self) -> None:
        assert remote_collisions(
            ["origin/feature/y"], "plan/x", ["plan/"]
        ) == []

    def test_slash_bearing_branch_name_normalizes(self) -> None:
        assert remote_collisions(
            ["origin/plan/my/slug"], "plan/my/slug", ["plan/"]
        ) == ["origin/plan/my/slug"]

    def test_local_convention_branch_not_remote_collision(self) -> None:
        assert remote_collisions(["plan/x"], "plan/x", ["plan/"]) == []

    def test_single_segment_ref_ignored(self) -> None:
        assert remote_collisions(["main"], "plan/x", ["plan/"]) == []

    def test_duplicate_raw_entries_deduped(self) -> None:
        assert remote_collisions(
            ["origin/plan/x", "origin/plan/x"], "plan/x", ["plan/"]
        ) == ["origin/plan/x"]

    def test_empty_ref_list_no_collision(self) -> None:
        assert remote_collisions([], "plan/x", ["plan/"]) == []


class TestWorktreeAdd:
    def test_create_new_branch_off_start_point(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        _commit_initial(repo)
        wt = tmp_path / "wt"
        rc, tail = worktree_add(
            repo, wt, "feat", create=True, start_point="HEAD"
        )
        assert rc == 0
        assert tail == ""
        assert current_branch(wt) == "feat"

    def test_add_existing_branch(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        _commit_initial(repo)
        _git(repo, "branch", "existing")
        wt = tmp_path / "wt"
        rc, _tail = worktree_add(
            repo, wt, "existing", create=False, start_point=""
        )
        assert rc == 0
        assert current_branch(wt) == "existing"

    def test_same_branch_twice_refused(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        _commit_initial(repo)
        current = current_branch(repo)
        assert current is not None
        # Adding a worktree on the branch already checked out in the main tree.
        wt = tmp_path / "wt"
        rc, tail = worktree_add(
            repo, wt, current, create=False, start_point=""
        )
        assert rc != 0
        assert tail != ""

    def test_non_repo_returns_nonzero(self, tmp_path: Path) -> None:
        rc, _tail = worktree_add(
            tmp_path, tmp_path / "wt", "feat", create=True, start_point="HEAD"
        )
        assert rc != 0


class TestWorktreeList:
    def test_lists_main_and_added_worktree(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        _commit_initial(repo)
        wt = tmp_path / "wt"
        worktree_add(repo, wt, "feat", create=True, start_point="HEAD")
        entries = worktree_list(repo)
        assert len(entries) == 2
        added = [e for e in entries if e.branch == "feat"]
        assert len(added) == 1
        assert Path(added[0].path).resolve() == wt.resolve()

    def test_detached_entry_has_none_branch(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        sha = _commit_initial(repo)
        wt = tmp_path / "wt"
        _git(repo, "worktree", "add", "--detach", str(wt), sha)
        entries = worktree_list(repo)
        detached = [e for e in entries if Path(e.path).resolve() == wt.resolve()]
        assert len(detached) == 1
        assert detached[0].branch is None
        assert detached[0].detached is True

    def test_non_repo_returns_empty(self, tmp_path: Path) -> None:
        assert worktree_list(tmp_path) == []


class TestWorktreeRemove:
    def _add_worktree(self, tmp_path: Path) -> tuple[Path, Path]:
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        _commit_initial(repo)
        wt = tmp_path / "wt"
        worktree_add(repo, wt, "feat", create=True, start_point="HEAD")
        return repo, wt

    def test_removes_clean_worktree(self, tmp_path: Path) -> None:
        repo, wt = self._add_worktree(tmp_path)
        rc, tail = worktree_remove(repo, wt, force=False)
        assert rc == 0
        assert tail == ""
        assert not wt.exists()

    def test_dirty_refused_without_force(self, tmp_path: Path) -> None:
        repo, wt = self._add_worktree(tmp_path)
        (wt / "f.txt").write_text("dirty\n", encoding="utf-8")
        rc, _tail = worktree_remove(repo, wt, force=False)
        assert rc != 0

    def test_dirty_removed_with_force(self, tmp_path: Path) -> None:
        repo, wt = self._add_worktree(tmp_path)
        (wt / "f.txt").write_text("dirty\n", encoding="utf-8")
        rc, _tail = worktree_remove(repo, wt, force=True)
        assert rc == 0
        assert not wt.exists()


class TestWorktreePrune:
    def test_prune_clears_deleted_worktree(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        _commit_initial(repo)
        wt = tmp_path / "wt"
        worktree_add(repo, wt, "feat", create=True, start_point="HEAD")
        shutil.rmtree(wt)
        rc, tail = worktree_prune(repo)
        assert rc == 0
        assert tail == ""
        assert all(
            Path(e.path).resolve() != wt.resolve() for e in worktree_list(repo)
        )


class TestCloneRepo:
    def test_clone_creates_new_branch(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        _commit_initial(repo)
        clone = tmp_path / "clone"
        rc, tail = clone_repo(
            repo, clone, branch="x", create=True, start_point="HEAD"
        )
        assert rc == 0
        assert tail == ""
        assert current_branch(clone) == "x"

    def test_clone_switches_existing_branch(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        _commit_initial(repo)
        _git(repo, "branch", "existing")
        clone = tmp_path / "clone"
        rc, _tail = clone_repo(
            repo, clone, branch="existing", create=False, start_point=""
        )
        assert rc == 0
        assert current_branch(clone) == "existing"

    def test_clone_new_branch_off_nondefault_start_point(
        self, tmp_path: Path
    ) -> None:
        # Source's current branch differs from the start point, so the start
        # point exists only as origin/<name> in the clone; a bare `switch -c`
        # would fail. clone_repo must resolve it to the remote-tracking ref.
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        _commit_initial(repo)
        _git(repo, "branch", "-M", "mainish")  # name the default branch
        _git(repo, "switch", "-c", "feat")  # source now on a different branch
        (repo / "feat.txt").write_text("f\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "on feat")  # feat diverges from mainish
        clone = tmp_path / "clone"
        rc, tail = clone_repo(
            repo, clone, branch="new", create=True, start_point="mainish"
        )
        assert rc == 0, tail
        assert current_branch(clone) == "new"
        # 'new' is off mainish (== origin/mainish), NOT the source's feat HEAD.
        heads = subprocess.run(
            ["git", "-C", str(clone), "rev-parse", "new", "origin/mainish",
             "origin/feat"],
            check=True, capture_output=True, text=True,
        ).stdout.split()
        assert heads[0] == heads[1]  # new == origin/mainish
        assert heads[0] != heads[2]  # and not origin/feat

    def test_clone_bad_source_returns_nonzero(self, tmp_path: Path) -> None:
        bad = tmp_path / "not-a-repo"
        bad.mkdir()
        clone = tmp_path / "clone"
        rc, _tail = clone_repo(
            bad, clone, branch="x", create=True, start_point="HEAD"
        )
        assert rc != 0
        # The switch phase must not have run — git leaves no usable clone
        # (either no dir at all, or one with no branch landed).
        assert not clone.exists() or current_branch(clone) is None


class TestUnexpectedDirtyPaths:
    """The relocated-root safety helper: which dirt isn't a create write?"""

    def test_clean_when_only_expected(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        _commit_initial(tmp_path)
        plan = tmp_path / "plan.md"
        plan.write_text("edited\n", encoding="utf-8")  # tracked, now modified
        manifest = tmp_path / "manifest.json"
        manifest.write_text("{}\n", encoding="utf-8")  # new, untracked
        assert unexpected_dirty_paths(tmp_path, [plan, manifest]) == []

    def test_reports_extra_file(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        _commit_initial(tmp_path)
        plan = tmp_path / "plan.md"
        plan.write_text("edited\n", encoding="utf-8")
        stranger = tmp_path / "stranger.txt"
        stranger.write_text("not mine\n", encoding="utf-8")
        assert unexpected_dirty_paths(tmp_path, [plan]) == ["stranger.txt"]

    def test_untracked_dir_not_collapsed(self, tmp_path: Path) -> None:
        # A wholly-new .plan-tool/ holding the expected plans.json and an
        # unrelated file: -uall lists both, so only the stranger is reported —
        # git's bare-porcelain collapse to '?? .plan-tool/' would have hidden it.
        _init_git_repo(tmp_path)
        _commit_initial(tmp_path)
        (tmp_path / ".plan-tool").mkdir()
        expected = tmp_path / ".plan-tool" / "plans.json"
        expected.write_text('{"plans": []}\n', encoding="utf-8")
        (tmp_path / ".plan-tool" / "extra.txt").write_text("x\n", encoding="utf-8")
        assert unexpected_dirty_paths(tmp_path, [expected]) == [
            ".plan-tool/extra.txt"
        ]

    def test_expected_dir_covers_its_contents(self, tmp_path: Path) -> None:
        # An expected directory covers the files -uall lists beneath it (the
        # collision-replace renamed detail dir is handed in as a directory).
        _init_git_repo(tmp_path)
        _commit_initial(tmp_path)
        detail = tmp_path / "plan-details" / "slug"
        detail.mkdir(parents=True)
        (detail / "01-a.md").write_text("a\n", encoding="utf-8")
        (detail / "02-b.md").write_text("b\n", encoding="utf-8")
        assert unexpected_dirty_paths(tmp_path, [detail]) == []

    def test_expected_outside_repo_root_skipped(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        _commit_initial(repo)
        stranger = repo / "stranger.txt"
        stranger.write_text("x\n", encoding="utf-8")
        outside = tmp_path / "elsewhere" / "manifest.json"
        # An out-of-repo expected path is ignored, not an error; the in-repo
        # stranger is still reported.
        assert unexpected_dirty_paths(repo, [outside]) == ["stranger.txt"]

    def test_non_repo_returns_none(self, tmp_path: Path) -> None:
        assert unexpected_dirty_paths(tmp_path, []) is None

    def test_git_binary_absent_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A missing git binary must yield the documented None (caller fails
        # closed), not an uncaught FileNotFoundError crashing the chain.
        import plan_tool.cli.gitcommit as gc

        def _no_git(*_a, **_k):
            raise FileNotFoundError("git: command not found")

        monkeypatch.setattr(gc.subprocess, "run", _no_git)
        assert unexpected_dirty_paths(tmp_path, []) is None

    def test_all_clean_returns_empty_list(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        _commit_initial(tmp_path)
        assert unexpected_dirty_paths(tmp_path, []) == []
