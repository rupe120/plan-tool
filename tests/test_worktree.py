"""Unit coverage for the pure worktree path/base resolution leaf.

Every level resolves against a ``tmp_path`` repo root and the
conftest-pinned temp ``$HOME`` (``_isolate_known_roots_cache``) — no real
git, no ``claude``. The inside-repo warning is asserted via ``capsys``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plan_tool import worktree as wt


def _write_project(repo_root: Path, payload: dict) -> None:
    from plan_tool.project_config import project_config_path

    path = project_config_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_user(payload: dict) -> None:
    from plan_tool.project_config import user_config_path

    path = user_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "myrepo"
    repo.mkdir()
    return repo


# --- default_worktree_base ----------------------------------------------


class TestDefaultWorktreeBase:
    def test_default_is_repo_sibling(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        # Compare against the resolved parent — the function resolves
        # ``repo_root`` first, so a symlinked tmp path (macOS /var) matches.
        assert (
            wt.default_worktree_base(repo)
            == repo.resolve().parent / "myrepo.worktrees"
        )


# --- worktree_base -------------------------------------------------------


class TestWorktreeBaseResolution:
    def test_unconfigured_returns_default(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        assert wt.worktree_base(repo) == wt.default_worktree_base(repo)

    def test_project_base_overrides_default(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        target = tmp_path / "custom-wt"
        _write_project(repo, {wt.WORKTREE_BASE_KEY: str(target)})
        assert wt.worktree_base(repo) == target.resolve()

    def test_project_overrides_user(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        proj = tmp_path / "proj-wt"
        user = tmp_path / "user-wt"
        _write_project(repo, {wt.WORKTREE_BASE_KEY: str(proj)})
        _write_user({wt.WORKTREE_BASE_KEY: str(user)})
        assert wt.worktree_base(repo) == proj.resolve()

    def test_user_used_when_project_absent(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        user = tmp_path / "user-wt"
        _write_user({wt.WORKTREE_BASE_KEY: str(user)})
        assert wt.worktree_base(repo) == user.resolve()

    def test_tilde_expanded(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        _write_project(repo, {wt.WORKTREE_BASE_KEY: "~/wt"})
        assert wt.worktree_base(repo) == (Path.home() / "wt").resolve()

    def test_relative_base_resolved_against_repo_parent(
        self, tmp_path: Path
    ) -> None:
        repo = _repo(tmp_path)
        _write_project(repo, {wt.WORKTREE_BASE_KEY: "sib-wt"})
        assert wt.worktree_base(repo) == (repo.parent / "sib-wt").resolve()

    @pytest.mark.parametrize(
        "payload",
        [
            "{ not json",  # bad JSON
            json.dumps([1, 2, 3]),  # top-level not a dict
            json.dumps({wt.WORKTREE_BASE_KEY: 42}),  # value not a str
            json.dumps({wt.WORKTREE_BASE_KEY: ""}),  # empty str
            json.dumps({"other": "x"}),  # key missing
        ],
    )
    def test_malformed_config_falls_back_to_default(
        self, tmp_path: Path, payload: str
    ) -> None:
        from plan_tool.project_config import project_config_path

        repo = _repo(tmp_path)
        path = project_config_path(repo)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
        assert wt.worktree_base(repo) == wt.default_worktree_base(repo)

    def test_malformed_project_falls_through_to_user(self, tmp_path: Path) -> None:
        from plan_tool.project_config import project_config_path

        repo = _repo(tmp_path)
        path = project_config_path(repo)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{ not json", encoding="utf-8")
        user = tmp_path / "user-wt"
        _write_user({wt.WORKTREE_BASE_KEY: str(user)})
        assert wt.worktree_base(repo) == user.resolve()

    def test_base_inside_repo_warns_and_falls_back(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = _repo(tmp_path)
        inside = repo / "nested" / "wt"
        _write_project(repo, {wt.WORKTREE_BASE_KEY: str(inside)})
        assert wt.worktree_base(repo) == wt.default_worktree_base(repo)
        err = capsys.readouterr().err
        assert wt.WORKTREE_BASE_KEY in err

    def test_inside_repo_base_does_not_fall_through_to_user(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo = _repo(tmp_path)
        inside = repo / "wt"
        user = tmp_path / "user-wt"
        _write_project(repo, {wt.WORKTREE_BASE_KEY: str(inside)})
        _write_user({wt.WORKTREE_BASE_KEY: str(user)})
        # A valid-but-inside-repo project base returns the default even
        # though a valid user base exists.
        assert wt.worktree_base(repo) == wt.default_worktree_base(repo)


# --- derive_worktree_path ------------------------------------------------


class TestDeriveWorktreePath:
    def test_path_is_base_slash_slug(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        base = tmp_path / "B"
        _write_project(repo, {wt.WORKTREE_BASE_KEY: str(base)})
        assert wt.derive_worktree_path(repo, "my-plan") == base.resolve() / "my-plan"

    def test_explicit_base_overrides_config(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        _write_project(repo, {wt.WORKTREE_BASE_KEY: str(tmp_path / "cfg")})
        explicit = tmp_path / "explicit"
        assert (
            wt.derive_worktree_path(repo, "my-plan", base=explicit)
            == explicit / "my-plan"
        )

    def test_deterministic_same_slug_same_path(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        first = wt.derive_worktree_path(repo, "my-plan")
        second = wt.derive_worktree_path(repo, "my-plan")
        assert first == second

    @pytest.mark.parametrize("slug", ["a/b", "..", "../escape", "", "   ", "x\\y"])
    def test_rejects_traversal_slug(self, tmp_path: Path, slug: str) -> None:
        repo = _repo(tmp_path)
        with pytest.raises(ValueError):
            wt.derive_worktree_path(repo, slug)


# --- classify_target -----------------------------------------------------


class TestClassifyTarget:
    def test_absent_path(self, tmp_path: Path) -> None:
        assert wt.classify_target(tmp_path / "nope") == wt.TargetState.ABSENT

    def test_empty_dir(self, tmp_path: Path) -> None:
        d = tmp_path / "empty"
        d.mkdir()
        assert wt.classify_target(d) == wt.TargetState.EMPTY

    def test_non_empty_dir(self, tmp_path: Path) -> None:
        d = tmp_path / "full"
        d.mkdir()
        (d / "f").write_text("x", encoding="utf-8")
        assert wt.classify_target(d) == wt.TargetState.NON_EMPTY

    def test_file_at_path_is_not_a_dir(self, tmp_path: Path) -> None:
        f = tmp_path / "afile"
        f.write_text("x", encoding="utf-8")
        assert wt.classify_target(f) == wt.TargetState.NOT_A_DIR
