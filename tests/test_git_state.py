"""Tests for plan_tool.git_state — the working-tree read and the shared
partial-mutation retry guard both backend callers hand the recovery loop.

The guard's whole reason to exist is a past regression (see CLAUDE.md's
git_state.py entry): the batch path once retried unconditionally on the false
premise that batch proposal turns never edit the tree. These tests pin the
fail-closed / stop-on-new-changes behavior directly, not just the plumbing.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from plan_tool.git_state import (
    changed_paths,
    changed_paths_or_none,
    committed_changed_paths,
    head_revision,
    make_partial_mutation_retry_guard,
)
from plan_tool.rate_limit_loop import ALWAYS_RETRY, RetryPolicy


def _run_git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _init_git_repo(root: Path) -> None:
    _run_git(["init", "-q"], root)
    _run_git(["config", "user.email", "t@example.com"], root)
    _run_git(["config", "user.name", "Test"], root)


# --- changed_paths_or_none ---------------------------------------------


class TestChangedPathsOrNone:
    def test_clean_tree_returns_empty_set(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        (tmp_path / "a.txt").write_text("one\n", encoding="utf-8")
        _run_git(["add", "a.txt"], tmp_path)
        _run_git(["commit", "-q", "-m", "init"], tmp_path)

        assert changed_paths_or_none(tmp_path) == set()

    def test_modified_tracked_file_is_reported(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        (tmp_path / "a.txt").write_text("one\n", encoding="utf-8")
        _run_git(["add", "a.txt"], tmp_path)
        _run_git(["commit", "-q", "-m", "init"], tmp_path)

        (tmp_path / "a.txt").write_text("two\n", encoding="utf-8")

        assert changed_paths_or_none(tmp_path) == {"a.txt"}

    def test_untracked_file_reported_individually_not_collapsed(
        self, tmp_path: Path
    ) -> None:
        """``--untracked-files=all`` must list the file itself, not collapse a
        wholly-new directory to its bare name — otherwise a new ``tests/``
        dir would hide the individual test file the authoring gate checks
        for."""
        _init_git_repo(tmp_path)
        (tmp_path / "README.md").write_text("x\n", encoding="utf-8")
        _run_git(["add", "README.md"], tmp_path)
        _run_git(["commit", "-q", "-m", "init"], tmp_path)

        new_dir = tmp_path / "tests"
        new_dir.mkdir()
        (new_dir / "test_x.py").write_text("x = 1\n", encoding="utf-8")

        result = changed_paths_or_none(tmp_path)
        assert result == {"tests/test_x.py"}
        assert "tests" not in result
        assert "tests/" not in result

    def test_rename_record_skips_origin_path_field(self, tmp_path: Path) -> None:
        """``-z`` output follows a rename/copy status with an extra NUL field
        (the origin path); the parser must consume and discard it rather than
        treating it as its own changed-path entry."""
        _init_git_repo(tmp_path)
        (tmp_path / "a.txt").write_text("line one\nline two\nline three\n", encoding="utf-8")
        _run_git(["add", "a.txt"], tmp_path)
        _run_git(["commit", "-q", "-m", "init"], tmp_path)

        _run_git(["mv", "a.txt", "b.txt"], tmp_path)

        result = changed_paths_or_none(tmp_path)
        assert result == {"b.txt"}
        assert "a.txt" not in result

    def test_non_git_directory_returns_none(self, tmp_path: Path) -> None:
        assert changed_paths_or_none(tmp_path) is None

    def test_subprocess_spawn_failure_returns_none(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        def _raise(*args, **kwargs):
            raise FileNotFoundError("git not found")

        monkeypatch.setattr(subprocess, "run", _raise)

        assert changed_paths_or_none(tmp_path) is None


# --- changed_paths -------------------------------------------------------


class TestChangedPaths:
    def test_collapses_none_to_empty_set(self, tmp_path: Path) -> None:
        assert changed_paths(tmp_path) == set()

    def test_passes_through_real_changes(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        (tmp_path / "a.txt").write_text("x\n", encoding="utf-8")

        assert changed_paths(tmp_path) == {"a.txt"}


class TestCommittedChangedPaths:
    def test_reads_only_added_modified_destinations_across_all_commits(self, tmp_path):
        _init_git_repo(tmp_path)
        (tmp_path / "old.py").write_text("old\n")
        _run_git(["add", "."], tmp_path)
        _run_git(["commit", "-qm", "baseline"], tmp_path)
        baseline = head_revision(tmp_path)
        assert baseline
        assert committed_changed_paths(tmp_path, baseline) == set()
        (tmp_path / "new name.py").write_text("new\n")
        _run_git(["add", "."], tmp_path)
        _run_git(["commit", "-qm", "add"], tmp_path)
        (tmp_path / "old.py").unlink()
        _run_git(["add", "-A"], tmp_path)
        _run_git(["commit", "-qm", "delete"], tmp_path)
        assert committed_changed_paths(tmp_path, baseline) == {"new name.py"}

    def test_relative_diff_config_cannot_bypass_dirty_exclusion_from_subdirectory(self, tmp_path):
        _init_git_repo(tmp_path)
        _run_git(["config", "diff.relative", "true"], tmp_path)
        project = tmp_path / "app"
        test = project / "tests" / "test_x.py"
        test.parent.mkdir(parents=True)
        test.write_text("before\n")
        _run_git(["add", "."], tmp_path)
        _run_git(["commit", "-qm", "baseline"], tmp_path)
        baseline = head_revision(project)
        test.write_text("dirty before call\n")
        dirty = changed_paths_or_none(project)
        test.write_text("backend edit\n")
        _run_git(["add", "."], tmp_path)
        _run_git(["commit", "-qm", "backend"], tmp_path)
        committed = committed_changed_paths(project, baseline)
        assert committed == dirty == {"app/tests/test_x.py"}
        assert committed - dirty == set()

    def test_git_path_output_preserves_non_utf8_bytes_without_decoding_failure(self, tmp_path, monkeypatch):
        import os
        import sys

        real_run = subprocess.run

        def git_output(args, **kwargs):
            if args[1] == "merge-base":
                return subprocess.CompletedProcess(args, 0, "", "")
            data = b"?? test_\xff.py\0" if args[1] == "status" else b"test_\xff.py\0"
            return real_run(
                [sys.executable, "-c", f"import sys; sys.stdout.buffer.write({data!r})"],
                **kwargs,
            )

        monkeypatch.setattr(subprocess, "run", git_output)
        name = os.fsdecode(b"test_\xff.py")
        assert changed_paths_or_none(tmp_path) == {name}
        assert committed_changed_paths(tmp_path, "revision") == {name}

    def test_unavailable_baseline_or_git_returns_no_committed_evidence(self, tmp_path, monkeypatch):
        assert head_revision(tmp_path) is None
        assert committed_changed_paths(tmp_path, None) == set()
        assert committed_changed_paths(tmp_path, "invalid") == set()
        _init_git_repo(tmp_path)
        assert head_revision(tmp_path) is None

        def fail(*args, **kwargs):
            raise OSError("unreadable git")

        monkeypatch.setattr(subprocess, "run", fail)
        assert head_revision(tmp_path) is None
        assert committed_changed_paths(tmp_path, "revision") == set()


# --- make_partial_mutation_retry_guard ------------------------------------


class TestMakePartialMutationRetryGuard:
    def test_returns_none_when_spawn_cwd_is_none(self) -> None:
        assert make_partial_mutation_retry_guard(None) is None

    def test_returns_none_when_baseline_is_unreadable(self, tmp_path: Path) -> None:
        guard = make_partial_mutation_retry_guard(
            tmp_path, read_changed=lambda _root: None
        )
        assert guard is None

    def test_no_new_changes_since_baseline_retries(self, tmp_path: Path) -> None:
        calls = iter([{"a.txt"}, {"a.txt"}])
        guard = make_partial_mutation_retry_guard(
            tmp_path, read_changed=lambda _root: next(calls)
        )
        assert guard is not None
        assert guard(object()) == ALWAYS_RETRY

    def test_baseline_is_snapshotted_before_first_attempt(self, tmp_path: Path) -> None:
        """The baseline read must happen once, at construction time (before
        attempt 1), not on each guard invocation — otherwise attempt 1's own
        edits would be folded into the baseline and never trip the guard."""
        reads: list[int] = []

        def _read(_root: Path):
            reads.append(1)
            return {"a.txt"} if len(reads) == 1 else {"a.txt", "b.txt"}

        guard = make_partial_mutation_retry_guard(tmp_path, read_changed=_read)
        assert len(reads) == 1  # baseline read at construction, not deferred

        decision = guard(object())
        assert decision.policy is RetryPolicy.STOP
        assert len(reads) == 2

    def test_aborted_turn_leaving_new_changes_stops_retry_to_avoid_double_apply(
        self, tmp_path: Path
    ) -> None:
        """The regression this guard exists to prevent: an aborted turn that
        left a new changed path must STOP the retry rather than re-drive over
        the partial edit (CLAUDE.md's git_state.py entry — the batch path
        once retried unconditionally here)."""
        calls = iter([{"a.txt"}, {"a.txt", "b.txt"}])
        guard = make_partial_mutation_retry_guard(
            tmp_path, read_changed=lambda _root: next(calls)
        )
        assert guard is not None

        decision = guard(object())

        assert decision.policy is RetryPolicy.STOP
        assert "b.txt" in decision.hint
        assert "a.txt" not in decision.hint
        assert "double-apply" in decision.hint

    def test_unreadable_current_state_fails_closed_and_stops_retry(
        self, tmp_path: Path
    ) -> None:
        """When git becomes unreadable mid-run (e.g. an index.lock), the guard
        must fail CLOSED — refuse the retry — rather than treat the unreadable
        state as "no new changes" and retry anyway."""
        calls = iter([{"a.txt"}, None])
        guard = make_partial_mutation_retry_guard(
            tmp_path, read_changed=lambda _root: next(calls)
        )
        assert guard is not None

        decision = guard(object())

        assert decision.policy is RetryPolicy.STOP
        assert "could not read git state" in decision.hint

    def test_default_read_changed_uses_real_git_state(self, tmp_path: Path) -> None:
        """Without an injected ``read_changed``, the guard must wire up to the
        real ``changed_paths_or_none`` — the seam is for tests, production
        relies on the default."""
        _init_git_repo(tmp_path)
        (tmp_path / "a.txt").write_text("x\n", encoding="utf-8")
        _run_git(["add", "a.txt"], tmp_path)
        _run_git(["commit", "-q", "-m", "init"], tmp_path)

        guard = make_partial_mutation_retry_guard(tmp_path)
        assert guard is not None

        assert guard(object()) == ALWAYS_RETRY

        (tmp_path / "b.txt").write_text("new\n", encoding="utf-8")

        decision = guard(object())
        assert decision.policy is RetryPolicy.STOP
        assert "b.txt" in decision.hint
