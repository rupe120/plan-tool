"""Tests for the ``worktree`` command group (``add`` + ``list``).

Drives real ``git`` against a ``tmp_path`` repo (no ``claude``), reusing the
repo-init helper style from ``test_gitcommit.py``. Verbs are exercised through
``cmd_worktree`` with a built ``argparse.Namespace``; the wiring class drives
``main([...])`` end to end. The worktree base is pinned via
``.plan-tool/config.json`` to a dir *outside* the repo (the inside-repo guard
forbids a base under the repo), so provisioned workspaces land under
``tmp_path`` and stay hermetic.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

import pytest

import plan_tool.cli as cli
from plan_tool.cli.worktree_cmd import (
    _resolve_branch,
    _resolve_start_point,
    cmd_worktree,
)
from plan_tool.cli.gitcommit import current_branch
from plan_tool.project_config import branch_prefixes
from plan_tool.worktree import derive_worktree_path

_PLAN_TEXT = (
    "---\n"
    "title: Demo\n"
    "status: planning\n"
    "priority: low\n"
    "steps:\n"
    "  - id: 1\n"
    "    title: Only step\n"
    "---\n"
    "# Body\n"
)
_REPO_TEMPLATE: Path | None = None


@pytest.fixture(scope="session", autouse=True)
def _repo_template(tmp_path_factory: pytest.TempPathFactory):
    """Create the committed worktree source once per pytest worker."""
    global _REPO_TEMPLATE
    root = tmp_path_factory.mktemp("worktree-repo-template")
    _init_git_repo(root)
    _commit_initial(root)
    _REPO_TEMPLATE = root
    yield
    _REPO_TEMPLATE = None


def _init_git_repo(root: Path) -> None:
    for cmd in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@example.com"],
        ["git", "config", "user.name", "Test"],
    ):
        subprocess.run(cmd, cwd=root, check=True, capture_output=True)


def _commit_initial(root: Path) -> None:
    (root / "f.txt").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"],
        cwd=root,
        check=True,
        capture_output=True,
    )


def _make_repo(
    tmp_path: Path, *, stem: str = "1-demo", awareness: bool = False
) -> tuple[Path, Path, Path]:
    """Build a real git repo with one registered plan + a pinned worktree base.

    Returns ``(repo_root, manifest_path, worktree_base)``.
    """
    root = tmp_path / "repo"
    assert _REPO_TEMPLATE is not None
    shutil.copytree(_REPO_TEMPLATE, root)
    plans_dir = root / "plans"
    plans_dir.mkdir()
    plan_path = plans_dir / f"{stem}.md"
    plan_path.write_text(_PLAN_TEXT, encoding="utf-8")
    manifest = root / "structured_plans.json"
    manifest.write_text(
        json.dumps({"plans": [str(plan_path.relative_to(root))]}),
        encoding="utf-8",
    )
    base = tmp_path / "wt"  # outside the repo — the inside-repo guard forbids under-repo
    cfg: dict = {"worktree_base": str(base)}
    if awareness:
        cfg["branch_awareness"] = {"enabled": True}
    cfg_dir = root / ".plan-tool"
    cfg_dir.mkdir(exist_ok=True)
    (cfg_dir / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    return root, manifest, base


def _ns(root: Path, manifest: Path, **kw) -> argparse.Namespace:
    return argparse.Namespace(
        plans_dir=None, manifest=manifest, repo_root=root, **kw
    )


@pytest.fixture(autouse=True)
def _clear_branch_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the ambient env from perturbing branch / start-point resolution."""
    monkeypatch.delenv("PLAN_TOOL_BRANCH_AWARENESS", raising=False)
    monkeypatch.delenv("PLAN_TOOL_DEFAULT_BRANCH", raising=False)


class TestBranchAndStartPointResolution:
    def test_resolve_branch_precedence(self, tmp_path: Path) -> None:
        off_root, _, _ = _make_repo(tmp_path / "off")
        # explicit --branch wins regardless of awareness / config.
        assert _resolve_branch(off_root, "demo", "feat-x") == "feat-x"
        # awareness OFF (project default) → the slug-derived fallback.
        assert _resolve_branch(off_root, "demo", None) == "demo"
        # awareness ON → the canonical derive_branch name.
        on_root, _, _ = _make_repo(tmp_path / "on", awareness=True)
        expected = branch_prefixes(on_root)[0] + "demo"
        assert _resolve_branch(on_root, "demo", None) == expected

    def test_resolve_start_point_falls_back_to_head(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root, _, _ = _make_repo(tmp_path)
        # No origin/HEAD and no env override → the "HEAD" fallback.
        assert _resolve_start_point(root) == "HEAD"
        # A resolvable default branch is returned as-is.
        monkeypatch.setenv("PLAN_TOOL_DEFAULT_BRANCH", "mainish")
        assert _resolve_start_point(root) == "mainish"


class TestWorktreeAdd:
    def test_add_provisions_worktree_on_slug_branch(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root, manifest, _ = _make_repo(tmp_path)
        rc = cmd_worktree(
            _ns(root, manifest, action="add", name="demo", branch=None, clone=False)
        )
        assert rc == 0
        target = derive_worktree_path(root, "demo")
        assert target.is_dir()
        assert current_branch(target) == "demo"
        assert str(target) in capsys.readouterr().out

    def test_add_local_only_repo_uses_head_start_point(
        self, tmp_path: Path
    ) -> None:
        # No remote / origin/HEAD: the start point resolves to "HEAD" and the
        # add still succeeds with no cryptic git error.
        root, manifest, _ = _make_repo(tmp_path)
        assert _resolve_start_point(root) == "HEAD"
        rc = cmd_worktree(
            _ns(root, manifest, action="add", name="demo", branch=None, clone=False)
        )
        assert rc == 0
        assert derive_worktree_path(root, "demo").is_dir()

    def test_add_explicit_branch_wins(self, tmp_path: Path) -> None:
        root, manifest, _ = _make_repo(tmp_path)
        rc = cmd_worktree(
            _ns(root, manifest, action="add", name="demo", branch="feat-x", clone=False)
        )
        assert rc == 0
        assert current_branch(derive_worktree_path(root, "demo")) == "feat-x"

    def test_add_branch_awareness_on_uses_derive_branch(
        self, tmp_path: Path
    ) -> None:
        root, manifest, _ = _make_repo(tmp_path, awareness=True)
        rc = cmd_worktree(
            _ns(root, manifest, action="add", name="demo", branch=None, clone=False)
        )
        assert rc == 0
        expected = branch_prefixes(root)[0] + "demo"
        assert current_branch(derive_worktree_path(root, "demo")) == expected

    def test_add_idempotent_reuse_healthy_worktree(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root, manifest, _ = _make_repo(tmp_path)
        assert (
            cmd_worktree(
                _ns(root, manifest, action="add", name="demo", branch=None, clone=False)
            )
            == 0
        )
        capsys.readouterr()  # drop the first-add output
        # A second add reuses the existing worktree (rc 0, reuse message) rather
        # than hitting git's same-branch-twice refusal.
        rc = cmd_worktree(
            _ns(root, manifest, action="add", name="demo", branch=None, clone=False)
        )
        assert rc == 0
        assert "reusing" in capsys.readouterr().out.lower()

    def test_add_foreign_nonempty_target_fails(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root, manifest, _ = _make_repo(tmp_path)
        target = derive_worktree_path(root, "demo")
        target.mkdir(parents=True)
        (target / "foo.txt").write_text("unrelated\n", encoding="utf-8")
        rc = cmd_worktree(
            _ns(root, manifest, action="add", name="demo", branch=None, clone=False)
        )
        assert rc != 0
        # No overwrite: the foreign file survives.
        assert (target / "foo.txt").read_text(encoding="utf-8") == "unrelated\n"
        assert "error:" in capsys.readouterr().err

    def test_add_clone_provisions_clone(self, tmp_path: Path) -> None:
        root, manifest, _ = _make_repo(tmp_path)
        rc = cmd_worktree(
            _ns(root, manifest, action="add", name="demo", branch=None, clone=True)
        )
        assert rc == 0
        target = derive_worktree_path(root, "demo")
        assert (target / ".git").is_dir()
        assert current_branch(target) == "demo"


class TestWorktreeList:
    def _add(self, root: Path, manifest: Path, *, clone: bool = False) -> Path:
        assert (
            cmd_worktree(
                _ns(root, manifest, action="add", name="demo", branch=None, clone=clone)
            )
            == 0
        )
        return derive_worktree_path(root, "demo")

    def test_list_reports_worktree_kind_branch_dirty(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root, manifest, _ = _make_repo(tmp_path)
        self._add(root, manifest)
        capsys.readouterr()
        rc = cmd_worktree(_ns(root, manifest, action="list"))
        assert rc == 0
        out = capsys.readouterr().out
        assert "demo" in out
        assert "worktree" in out
        assert "clean" in out

    def test_list_reports_clone_kind(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root, manifest, _ = _make_repo(tmp_path)
        self._add(root, manifest, clone=True)
        capsys.readouterr()
        rc = cmd_worktree(_ns(root, manifest, action="list"))
        assert rc == 0
        assert "clone" in capsys.readouterr().out

    def test_list_reports_dirty(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root, manifest, _ = _make_repo(tmp_path)
        target = self._add(root, manifest)
        (target / "scratch.txt").write_text("dirty\n", encoding="utf-8")
        capsys.readouterr()
        rc = cmd_worktree(_ns(root, manifest, action="list"))
        assert rc == 0
        assert "dirty" in capsys.readouterr().out

    def test_list_empty_when_no_workspaces(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root, manifest, _ = _make_repo(tmp_path)
        rc = cmd_worktree(_ns(root, manifest, action="list"))
        assert rc == 0
        assert "no workspaces" in capsys.readouterr().out.lower()


def _add(root: Path, manifest: Path, *, clone: bool = False) -> Path:
    """Provision ``demo``'s workspace and return its derived path."""
    assert (
        cmd_worktree(
            _ns(root, manifest, action="add", name="demo", branch=None, clone=clone)
        )
        == 0
    )
    return derive_worktree_path(root, "demo")


def _deregister(manifest: Path) -> None:
    """Drop every plan from the manifest (simulate deregistration)."""
    manifest.write_text(json.dumps({"plans": []}), encoding="utf-8")


class TestWorktreeRemove:
    def test_remove_clean_worktree_succeeds(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root, manifest, _ = _make_repo(tmp_path)
        target = _add(root, manifest)
        rc = cmd_worktree(
            _ns(root, manifest, action="remove", name="demo", force=False, yes=True)
        )
        assert rc == 0
        assert not target.exists()
        assert "removed" in capsys.readouterr().out.lower()

    def test_remove_dirty_refused_without_force(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root, manifest, _ = _make_repo(tmp_path)
        target = _add(root, manifest)
        (target / "scratch.txt").write_text("dirty\n", encoding="utf-8")
        rc = cmd_worktree(
            _ns(root, manifest, action="remove", name="demo", force=False, yes=True)
        )
        assert rc != 0
        assert target.is_dir()
        assert "uncommitted changes" in capsys.readouterr().err

    def test_remove_dirty_succeeds_with_force(self, tmp_path: Path) -> None:
        root, manifest, _ = _make_repo(tmp_path)
        target = _add(root, manifest)
        (target / "scratch.txt").write_text("dirty\n", encoding="utf-8")
        rc = cmd_worktree(
            _ns(root, manifest, action="remove", name="demo", force=True, yes=True)
        )
        assert rc == 0
        assert not target.exists()

    def test_remove_clone_surfaces_manual_cleanup_not_deleted(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root, manifest, _ = _make_repo(tmp_path)
        target = _add(root, manifest, clone=True)
        # Clean clone, no --force: surfaced, not deleted.
        rc = cmd_worktree(
            _ns(root, manifest, action="remove", name="demo", force=False, yes=True)
        )
        assert rc == 0
        assert (target / ".git").is_dir()
        assert "won't delete" in capsys.readouterr().err
        # Dirty clone + --force: still never deleted.
        (target / "scratch.txt").write_text("dirty\n", encoding="utf-8")
        rc = cmd_worktree(
            _ns(root, manifest, action="remove", name="demo", force=True, yes=True)
        )
        assert rc == 0
        assert (target / ".git").is_dir()

    def test_remove_missing_workspace_is_noop(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root, manifest, _ = _make_repo(tmp_path)
        rc = cmd_worktree(
            _ns(root, manifest, action="remove", name="demo", force=False, yes=True)
        )
        assert rc == 0
        assert "no workspace" in capsys.readouterr().err.lower()

    def test_remove_from_inside_target_clean_message(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root, manifest, _ = _make_repo(tmp_path)
        target = _add(root, manifest)
        monkeypatch.chdir(target)
        rc = cmd_worktree(
            _ns(root, manifest, action="remove", name="demo", force=False, yes=True)
        )
        assert rc != 0
        err = capsys.readouterr().err
        assert "you are inside" in err
        assert "fatal:" not in err
        assert target.is_dir()

    def test_remove_leaves_branch(self, tmp_path: Path) -> None:
        root, manifest, _ = _make_repo(tmp_path)
        _add(root, manifest)
        rc = cmd_worktree(
            _ns(root, manifest, action="remove", name="demo", force=False, yes=True)
        )
        assert rc == 0
        branches = subprocess.run(
            ["git", "branch", "--format", "%(refname:short)"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.split()
        assert "demo" in branches


class TestWorktreePrune:
    def test_prune_removes_deregistered_worktree(self, tmp_path: Path) -> None:
        root, manifest, _ = _make_repo(tmp_path)
        target = _add(root, manifest)
        _deregister(manifest)
        rc = cmd_worktree(_ns(root, manifest, action="prune", yes=True))
        assert rc == 0
        assert not target.exists()

    def test_prune_keeps_registered_worktree(self, tmp_path: Path) -> None:
        root, manifest, _ = _make_repo(tmp_path)
        target = _add(root, manifest)
        rc = cmd_worktree(_ns(root, manifest, action="prune", yes=True))
        assert rc == 0
        assert target.is_dir()

    def test_prune_never_touches_clone(self, tmp_path: Path) -> None:
        root, manifest, _ = _make_repo(tmp_path)
        target = _add(root, manifest, clone=True)
        _deregister(manifest)
        rc = cmd_worktree(_ns(root, manifest, action="prune", yes=True))
        assert rc == 0
        # A clone is not in git's worktree registry, so prune never sees it.
        assert (target / ".git").is_dir()

    def test_prune_discovers_via_worktree_registry_not_path_scan(
        self, tmp_path: Path
    ) -> None:
        root, manifest, base = _make_repo(tmp_path)
        # A plain dir parked under the base is never a prune candidate.
        stray = base / "unrelated"
        stray.mkdir(parents=True)
        (stray / "keep.txt").write_text("keep\n", encoding="utf-8")
        rc = cmd_worktree(_ns(root, manifest, action="prune", yes=True))
        assert rc == 0
        assert (stray / "keep.txt").is_file()

    def test_prune_surfaces_dirty_not_deletes_even_with_yes(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root, manifest, _ = _make_repo(tmp_path)
        target = _add(root, manifest)
        (target / "scratch.txt").write_text("dirty\n", encoding="utf-8")
        _deregister(manifest)
        rc = cmd_worktree(_ns(root, manifest, action="prune", yes=True))
        assert rc == 0
        assert target.is_dir()
        assert "dead-but-dirty" in capsys.readouterr().err

    def test_prune_path_gone_clears_admin(self, tmp_path: Path) -> None:
        root, manifest, _ = _make_repo(tmp_path)
        target = _add(root, manifest)
        _deregister(manifest)
        # Delete the dir by hand; the registry entry lingers until prune.
        subprocess.run(["rm", "-rf", str(target)], check=True)
        listed = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        assert str(target) in listed
        rc = cmd_worktree(_ns(root, manifest, action="prune", yes=True))
        assert rc == 0
        listed = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        assert str(target) not in listed

    def test_prune_empty_when_nothing_dead(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root, manifest, _ = _make_repo(tmp_path)
        rc = cmd_worktree(_ns(root, manifest, action="prune", yes=True))
        assert rc == 0
        assert "no dead workspaces" in capsys.readouterr().out.lower()


class TestRemovePruneConfirmGate:
    def test_remove_declined_at_tty_keeps_workspace(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root, manifest, _ = _make_repo(tmp_path)
        target = _add(root, manifest)
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda _prompt: "n")
        rc = cmd_worktree(
            _ns(root, manifest, action="remove", name="demo", force=False, yes=False)
        )
        assert rc == 0
        assert target.is_dir()

    def test_prune_non_tty_without_yes_declines(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root, manifest, _ = _make_repo(tmp_path)
        target = _add(root, manifest)
        _deregister(manifest)
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        rc = cmd_worktree(_ns(root, manifest, action="prune", yes=False))
        assert rc == 0
        assert target.is_dir()

    def test_yes_bypasses_prompt(self, tmp_path: Path) -> None:
        root, manifest, _ = _make_repo(tmp_path)
        target = _add(root, manifest)

        def _boom(_prompt: str) -> str:
            raise AssertionError("input() must not be called under -y")

        # No monkeypatch of isatty; -y must short-circuit before any prompt.
        import builtins

        original = builtins.input
        builtins.input = _boom
        try:
            rc = cmd_worktree(
                _ns(root, manifest, action="remove", name="demo", force=False, yes=True)
            )
        finally:
            builtins.input = original
        assert rc == 0
        assert not target.exists()


class TestWorktreeWiring:
    def test_worktree_in_help_and_dispatch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("COLUMNS", "80")
        assert "worktree" in cli.build_parser().format_help()
        root, manifest, _ = _make_repo(tmp_path)
        base_argv = ["--repo-root", str(root), "--manifest", str(manifest)]
        assert cli.main([*base_argv, "worktree", "add", "demo"]) == 0
        assert derive_worktree_path(root, "demo").is_dir()
        assert cli.main([*base_argv, "worktree", "list"]) == 0

    def test_remove_and_prune_dispatch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root, manifest, _ = _make_repo(tmp_path)
        base_argv = ["--repo-root", str(root), "--manifest", str(manifest)]
        assert cli.main([*base_argv, "worktree", "add", "demo"]) == 0
        target = derive_worktree_path(root, "demo")
        # prune reaches its handler (registered plan → nothing dead → kept).
        assert cli.main([*base_argv, "worktree", "prune", "-y"]) == 0
        assert target.is_dir()
        # remove reaches its handler and deletes the worktree.
        assert cli.main([*base_argv, "worktree", "remove", "demo", "-y"]) == 0
        assert not target.exists()

    def test_cmd_worktree_on_package_surface(self) -> None:
        assert callable(getattr(cli, "cmd_worktree", None))


class TestWorktreeReviewFixes:
    """Regression tests for the code-review correctness findings."""

    def test_clone_reuse_refuses_foreign_repo(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # An UNRELATED clone sits at the derived path on a same-named branch.
        # Reuse must refuse it (identity check), not silently adopt it.
        root, manifest, _ = _make_repo(tmp_path)
        target = derive_worktree_path(root, "demo")
        target.parent.mkdir(parents=True, exist_ok=True)
        other = tmp_path / "other-src"
        other.mkdir()
        _init_git_repo(other)
        _commit_initial(other)
        subprocess.run(
            ["git", "clone", "--quiet", str(other), str(target)],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(target), "switch", "-c", "demo"],
            check=True, capture_output=True,
        )
        rc = cmd_worktree(
            _ns(root, manifest, action="add", name="demo", branch=None, clone=True)
        )
        assert rc != 0
        assert "refusing" in capsys.readouterr().err

    def test_prune_skips_workspace_operator_is_inside(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root, manifest, _ = _make_repo(tmp_path)
        target = _add(root, manifest)
        _deregister(manifest)  # now dead
        monkeypatch.chdir(target)  # stand inside it
        rc = cmd_worktree(_ns(root, manifest, action="prune", yes=True))
        assert rc == 0
        assert target.is_dir()  # NOT deleted out from under the operator
        assert "standing in" in capsys.readouterr().err

    def test_prune_returns_nonzero_on_removal_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root, manifest, _ = _make_repo(tmp_path)
        _add(root, manifest)
        _deregister(manifest)
        import plan_tool.cli.worktree_cmd as wc

        monkeypatch.setattr(wc, "worktree_remove", lambda *a, **k: (1, "boom"))
        rc = cmd_worktree(_ns(root, manifest, action="prune", yes=True))
        assert rc != 0  # partial/total failure is not a false success

    def test_prune_skips_non_slug_worktree_dir_name(self, tmp_path: Path) -> None:
        # A git worktree under the base whose dir name can't be a plan slug (a
        # backslash, which _validate_slug rejects) must be skipped, not crash.
        root, manifest, base = _make_repo(tmp_path)
        base.mkdir(parents=True, exist_ok=True)
        weird = base / "weird\\name"
        subprocess.run(
            ["git", "worktree", "add", "-b", "wb", str(weird), "HEAD"],
            cwd=root, check=True, capture_output=True,
        )
        rc = cmd_worktree(_ns(root, manifest, action="prune", yes=True))
        assert rc == 0  # no unhandled ValueError
        assert weird.is_dir()  # untouched (not a plan-tool candidate)
