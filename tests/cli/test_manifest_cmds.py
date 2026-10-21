"""Characterization tests for the manifest-mutating command helpers.

Pins the resolution + reporting helpers behind ``register`` / ``deregister``
/ ``sweep`` so the "split cli.py into an intent-grouped package" refactor
can move them into a manifest submodule without changing what they resolve
or print. The ``cmd_*`` handlers themselves are directly covered by the
legacy suite (``test_cli.py`` / ``test_sweep.py``); per
``tests/cli/COVERAGE_BASELINE.md`` the gaps filled here are the
``indirectly covered`` helpers:

* ``_resolve_register_target`` / ``_resolve_deregister_target`` — path vs
  slug resolution, including the deregister-only known-missing slug match.
* ``_archive_duplicate_plans`` — the dry-run / move / best-effort-skip paths.
* ``_prompt_remove_missing`` — the ``--dry-run`` / ``-y`` / TTY / non-TTY
  decision contract, driven with scripted stdin.
* ``_print_sweep_report`` — the headline + per-section rendering, fed a
  report built from real classifications.

Split-proof conventions (see ``test_package_surface.py``): helpers are
imported from ``plan_tool.cli``; a :class:`PlanToolContext` is built via the
public ``build_parser()`` + ``_load_context`` seam over the ``tmp_repo`` /
``registered_plan`` fixtures; stdin/TTY is driven by patching the stdlib
``sys.stdin`` / ``builtins.input`` (never a cli-module global).
"""

from __future__ import annotations

import json
import sys

import pytest

from plan_tool.cli import (
    _archive_duplicate_plans,
    _load_context,
    _print_sweep_report,
    _prompt_remove_missing,
    _resolve_deregister_target,
    _resolve_register_target,
    build_parser,
)
from plan_tool.sweep import SweepReport, classify_plan


def _ctx(repo):
    """Build a :class:`PlanToolContext` for ``repo`` via the public seam."""
    args = build_parser().parse_args(repo.argv("register", "placeholder"))
    return _load_context(args)


class _FakeStdin:
    """Minimal stand-in for ``sys.stdin`` with a fixed ``isatty`` verdict."""

    def __init__(self, *, tty: bool) -> None:
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


class TestResolveRegisterTarget:
    def test_repo_relative_path_resolves(self, registered_plan) -> None:
        ctx = _ctx(registered_plan)
        got = _resolve_register_target(ctx, "plans/1-demo.md")
        assert got == (registered_plan.plans_dir / "1-demo.md").resolve()

    def test_absolute_path_resolves(self, registered_plan) -> None:
        ctx = _ctx(registered_plan)
        abs_path = (registered_plan.plans_dir / "1-demo.md").resolve()
        assert _resolve_register_target(ctx, str(abs_path)) == abs_path

    def test_bare_slug_matches_priority_prefixed_file(
        self, registered_plan
    ) -> None:
        ctx = _ctx(registered_plan)
        # "demo" must find "1-demo.md" via the 1-/2-/3- prefix probe.
        got = _resolve_register_target(ctx, "demo")
        assert got == (registered_plan.plans_dir / "1-demo.md").resolve()

    def test_unknown_slug_returns_none(self, registered_plan) -> None:
        assert _resolve_register_target(_ctx(registered_plan), "nope") is None

    def test_pathlike_miss_does_not_fall_through_to_slug(
        self, registered_plan
    ) -> None:
        # Contains a slash but doesn't resolve → None, never a slug guess.
        assert _resolve_register_target(_ctx(registered_plan), "sub/demo") is None


class TestResolveDeregisterTarget:
    def test_literal_path_returned_without_existence_check(
        self, registered_plan
    ) -> None:
        ctx = _ctx(registered_plan)
        # A ".md" path resolves even though the file was never written.
        got = _resolve_deregister_target(ctx, "plans/9-ghost.md")
        assert got == (registered_plan.plans_dir / "9-ghost.md").resolve()

    def test_bare_slug_matches_registered_entry(self, registered_plan) -> None:
        ctx = _ctx(registered_plan)
        got = _resolve_deregister_target(ctx, "demo")
        assert got == (registered_plan.plans_dir / "1-demo.md").resolve()

    def test_bare_slug_matches_known_missing_entry(self, tmp_repo) -> None:
        tmp_repo.add_plan("1-demo", title="Demo")
        ghost = tmp_repo.plans_dir / "9-ghost.md"  # registered but never written
        tmp_repo.plans.append(ghost)
        tmp_repo.write_manifest()

        ctx = _ctx(tmp_repo)
        assert ghost.resolve() in [p.resolve() for p in ctx.missing_paths]
        # Pruning a stale entry by slug is a core deregister use case.
        assert _resolve_deregister_target(ctx, "ghost") == ghost.resolve()

    def test_empty_and_unknown_return_none(self, registered_plan) -> None:
        ctx = _ctx(registered_plan)
        assert _resolve_deregister_target(ctx, "   ") is None
        assert _resolve_deregister_target(ctx, "missing-slug") is None


class TestArchiveDuplicatePlans:
    def test_dry_run_returns_planned_dest_without_moving(self, tmp_path) -> None:
        src = tmp_path / "1-dup.md"
        src.write_text("body", encoding="utf-8")
        results = _archive_duplicate_plans([src], dry_run=True)
        assert results == [(src, src.parent / "archive" / src.name)]
        assert src.is_file()  # untouched
        assert not (src.parent / "archive").exists()

    def test_move_relocates_into_archive_subdir(self, tmp_path) -> None:
        src = tmp_path / "1-dup.md"
        src.write_text("body", encoding="utf-8")
        results = _archive_duplicate_plans([src], dry_run=False)
        dest = src.parent / "archive" / src.name
        assert results == [(src, dest)]
        assert not src.exists()
        assert dest.read_text(encoding="utf-8") == "body"

    def test_unmovable_source_is_skipped(self, tmp_path) -> None:
        missing = tmp_path / "1-gone.md"  # never created → rename raises OSError
        assert _archive_duplicate_plans([missing], dry_run=False) == []


class TestPromptRemoveMissing:
    @staticmethod
    def _manifest_plans(repo) -> list[str]:
        data = json.loads(repo.manifest_path.read_text(encoding="utf-8"))
        return data["plans"]

    @staticmethod
    def _repo_with_missing(tmp_repo):
        tmp_repo.add_plan("1-demo", title="Demo")
        ghost = tmp_repo.plans_dir / "9-ghost.md"
        tmp_repo.plans.append(ghost)
        tmp_repo.write_manifest()
        return ghost

    def test_empty_missing_is_a_noop(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _prompt_remove_missing(
            [],
            manifest_path=tmp_repo.manifest_path,
            repo_root=tmp_repo.root,
            dry_run=False,
            yes=True,
        )
        assert capsys.readouterr().out == ""

    def test_dry_run_reports_but_keeps_manifest(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        ghost = self._repo_with_missing(tmp_repo)
        _prompt_remove_missing(
            [ghost],
            manifest_path=tmp_repo.manifest_path,
            repo_root=tmp_repo.root,
            dry_run=True,
            yes=False,
        )
        assert "would remove 1 missing entry" in capsys.readouterr().out
        assert "plans/9-ghost.md" in self._manifest_plans(tmp_repo)

    def test_non_tty_without_yes_leaves_entry_and_hints(
        self,
        tmp_repo,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        ghost = self._repo_with_missing(tmp_repo)
        monkeypatch.setattr(sys, "stdin", _FakeStdin(tty=False))
        _prompt_remove_missing(
            [ghost],
            manifest_path=tmp_repo.manifest_path,
            repo_root=tmp_repo.root,
            dry_run=False,
            yes=False,
        )
        err = capsys.readouterr().err
        assert "left in the manifest" in err
        assert "plans/9-ghost.md" in self._manifest_plans(tmp_repo)

    def test_yes_removes_entry_from_manifest(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        ghost = self._repo_with_missing(tmp_repo)
        _prompt_remove_missing(
            [ghost],
            manifest_path=tmp_repo.manifest_path,
            repo_root=tmp_repo.root,
            dry_run=False,
            yes=True,
        )
        out = capsys.readouterr().out
        assert "removed 1 missing entry" in out
        assert "plans/9-ghost.md" not in self._manifest_plans(tmp_repo)

    def test_tty_yes_answer_removes_entry(
        self,
        tmp_repo,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        ghost = self._repo_with_missing(tmp_repo)
        monkeypatch.setattr(sys, "stdin", _FakeStdin(tty=True))
        monkeypatch.setattr("builtins.input", lambda *a, **k: "y")
        _prompt_remove_missing(
            [ghost],
            manifest_path=tmp_repo.manifest_path,
            repo_root=tmp_repo.root,
            dry_run=False,
            yes=False,
        )
        assert "plans/9-ghost.md" not in self._manifest_plans(tmp_repo)

    def test_tty_no_answer_keeps_entry(
        self,
        tmp_repo,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        ghost = self._repo_with_missing(tmp_repo)
        monkeypatch.setattr(sys, "stdin", _FakeStdin(tty=True))
        monkeypatch.setattr("builtins.input", lambda *a, **k: "n")
        _prompt_remove_missing(
            [ghost],
            manifest_path=tmp_repo.manifest_path,
            repo_root=tmp_repo.root,
            dry_run=False,
            yes=False,
        )
        assert "plans/9-ghost.md" in self._manifest_plans(tmp_repo)


class TestPrintSweepReport:
    def test_headline_and_sections_render(
        self, tmp_repo, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # A partial (planning) plan plus a registered-but-missing entry.
        tmp_repo.add_plan("1-demo", title="Demo Plan")
        ghost = tmp_repo.plans_dir / "9-ghost.md"
        tmp_repo.plans.append(ghost)
        tmp_repo.write_manifest()

        ctx = _ctx(tmp_repo)
        report = SweepReport(
            classifications=[classify_plan(e) for e in ctx.entries]
        )
        _print_sweep_report(
            report,
            ctx=ctx,
            manifest_path=tmp_repo.manifest_path,
            report_only=True,
        )
        out = capsys.readouterr().out
        # report-only headline: nothing archived, one partial, one missing.
        assert "sweep (report-only): 0 completed (not archived), 1 partial" in out
        assert "1 missing" in out
        assert f"manifest: {tmp_repo.manifest_path}" in out
        assert "partial (1):" in out
        assert "demo" in out
        assert "missing (1):" in out
        assert "plans/9-ghost.md" in out


# ---------------------------------------------------------------------------
# `sweep --commit`
# ---------------------------------------------------------------------------


def _init_git_repo(root) -> None:
    import subprocess

    for cmd in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@example.com"],
        ["git", "config", "user.name", "Test"],
    ):
        subprocess.run(cmd, cwd=root, check=True, capture_output=True)


def _git_commit_all(root, message: str) -> None:
    import subprocess

    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", message],
        cwd=root, check=True, capture_output=True,
    )


def _git_log_subjects(root) -> list[str]:
    import subprocess

    proc = subprocess.run(
        ["git", "log", "--format=%s"],
        cwd=root, check=True, capture_output=True, text=True,
    )
    return proc.stdout.strip().splitlines()


def _git_tree_clean(root) -> bool:
    import subprocess

    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root, check=True, capture_output=True, text=True,
    )
    return not proc.stdout.strip()


_COMPLETED_PLAN_TEXT = (
    "---\n"
    "title: Done Plan\n"
    "status: completed\n"
    "priority: low\n"
    "steps:\n"
    "  - id: 1\n"
    "    title: Only step\n"
    "    status: done\n"
    "---\n"
    "# Body\n"
)


def _add_completed_plan(repo, stem: str = "1-done"):
    """Register a sweep-completable plan (status: completed + all steps done)."""
    path = repo.plans_dir / f"{stem}.md"
    path.write_text(_COMPLETED_PLAN_TEXT, encoding="utf-8")
    repo.plans.append(path)
    return path


def _real_git_repo(repo):
    """Swap the fixture's stub ``.git`` for a real initialized repo."""
    import shutil

    shutil.rmtree(repo.root / ".git")
    _init_git_repo(repo.root)


class TestSweepCommitSubjects:
    def test_subject_singular_plural_and_hygiene(self) -> None:
        from plan_tool.cli.manifest import _sweep_commit_subject

        assert _sweep_commit_subject(1) == "sweep: archive 1 completed plan"
        assert _sweep_commit_subject(2) == "sweep: archive 2 completed plans"
        assert _sweep_commit_subject(0) == "sweep: manifest hygiene"


# ---------------------------------------------------------------------------
# `attach-branch` / `detach-branch`
# ---------------------------------------------------------------------------


import plan_tool.cli.manifest as manifest_mod  # noqa: E402
from plan_tool.branch_ownership import (  # noqa: E402
    OWNER_AD_HOC,
    OWNER_CONVENTION,
    BranchOwner,
)


def _enable_branch_awareness(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force ``branch_awareness_enabled`` (as imported into manifest) on."""
    monkeypatch.setattr(
        manifest_mod, "branch_awareness_enabled", lambda repo_root: True
    )


class _Recorder:
    """Captures positional args of every call for later assertion."""

    def __init__(self, result=None) -> None:
        self.calls: list[tuple] = []
        self._result = result

    def __call__(self, *args):
        self.calls.append(args)
        return self._result

    @property
    def called(self) -> bool:
        return bool(self.calls)


class TestAttachBranch:
    def _args(self, repo, *extra: str):
        return build_parser().parse_args(repo.argv("attach-branch", *extra))

    def test_attach_refuses_when_disabled(
        self, registered_plan, monkeypatch, capsys
    ) -> None:
        monkeypatch.delenv("PLAN_TOOL_BRANCH_AWARENESS", raising=False)
        set_b = _Recorder()
        monkeypatch.setattr(manifest_mod, "set_binding", set_b)
        rc = manifest_mod.cmd_attach_branch(
            self._args(registered_plan, "demo", "feat/x")
        )
        assert rc == 2
        assert "disabled" in capsys.readouterr().err
        assert not set_b.called

    def test_attach_refuses_directory_mode(
        self, registered_plan, monkeypatch, capsys
    ) -> None:
        _enable_branch_awareness(monkeypatch)
        args = build_parser().parse_args(
            [
                "--plans-dir",
                str(registered_plan.plans_dir),
                "attach-branch",
                "demo",
                "feat/x",
            ]
        )
        rc = manifest_mod.cmd_attach_branch(args)
        assert rc == 2
        assert "manifest-mode" in capsys.readouterr().err

    def test_attach_unresolvable_plan_returns_2(
        self, registered_plan, monkeypatch
    ) -> None:
        _enable_branch_awareness(monkeypatch)
        rc = manifest_mod.cmd_attach_branch(
            self._args(registered_plan, "nope", "feat/x")
        )
        assert rc == 2

    def test_attach_empty_branch_returns_2(
        self, registered_plan, monkeypatch
    ) -> None:
        _enable_branch_awareness(monkeypatch)
        set_b = _Recorder()
        monkeypatch.setattr(manifest_mod, "set_binding", set_b)
        rc = manifest_mod.cmd_attach_branch(
            self._args(registered_plan, "demo", "   ")
        )
        assert rc == 2
        assert not set_b.called

    def test_attach_binds_when_no_owner(
        self, registered_plan, monkeypatch
    ) -> None:
        _enable_branch_awareness(monkeypatch)
        monkeypatch.setattr(
            manifest_mod, "branch_owner", lambda *a, **k: None
        )
        set_b = _Recorder()
        monkeypatch.setattr(manifest_mod, "set_binding", set_b)
        dirty = _Recorder(result=True)
        monkeypatch.setattr(manifest_mod, "working_tree_dirty", dirty)
        rc = manifest_mod.cmd_attach_branch(
            self._args(registered_plan, "demo", "feat/x")
        )
        assert rc == 0
        assert set_b.calls == [(registered_plan.root, "demo", "feat/x")]
        assert not dirty.called  # no clean-tree gate on a plain bind

    def test_attach_binds_when_self_owned(
        self, registered_plan, monkeypatch
    ) -> None:
        _enable_branch_awareness(monkeypatch)
        monkeypatch.setattr(
            manifest_mod,
            "branch_owner",
            lambda *a, **k: BranchOwner(slug="demo", kind=OWNER_CONVENTION),
        )
        set_b = _Recorder()
        monkeypatch.setattr(manifest_mod, "set_binding", set_b)
        rc = manifest_mod.cmd_attach_branch(
            self._args(registered_plan, "demo", "plan/demo")
        )
        assert rc == 0
        assert set_b.calls == [(registered_plan.root, "demo", "plan/demo")]

    def test_attach_surfaces_set_binding_error(
        self, registered_plan, monkeypatch, capsys
    ) -> None:
        _enable_branch_awareness(monkeypatch)
        monkeypatch.setattr(
            manifest_mod, "branch_owner", lambda *a, **k: None
        )

        def _raise(*a, **k):
            raise manifest_mod.BranchBindingError("boom")

        monkeypatch.setattr(manifest_mod, "set_binding", _raise)
        rc = manifest_mod.cmd_attach_branch(
            self._args(registered_plan, "demo", "feat/x")
        )
        assert rc == 1
        assert "boom" in capsys.readouterr().err

    def test_attach_does_not_validate_override_ref(
        self, registered_plan, monkeypatch
    ) -> None:
        _enable_branch_awareness(monkeypatch)
        monkeypatch.setattr(
            manifest_mod, "branch_owner", lambda *a, **k: None
        )
        set_b = _Recorder()
        monkeypatch.setattr(manifest_mod, "set_binding", set_b)
        rc = manifest_mod.cmd_attach_branch(
            self._args(registered_plan, "demo", "JIRA-1")
        )
        assert rc == 0
        assert set_b.calls == [(registered_plan.root, "demo", "JIRA-1")]

    def test_attach_refuses_adhoc_bound_elsewhere(
        self, registered_plan, monkeypatch, capsys
    ) -> None:
        _enable_branch_awareness(monkeypatch)
        monkeypatch.setattr(
            manifest_mod,
            "branch_owner",
            lambda *a, **k: BranchOwner(slug="other", kind=OWNER_AD_HOC),
        )
        set_b = _Recorder()
        monkeypatch.setattr(manifest_mod, "set_binding", set_b)
        rc = manifest_mod.cmd_attach_branch(
            self._args(registered_plan, "demo", "feat/x")
        )
        assert rc == 2
        err = capsys.readouterr().err
        assert "other" in err
        assert "detach-branch" in err
        assert not set_b.called

    def test_attach_rehome_requires_consent_noninteractive(
        self, registered_plan, monkeypatch
    ) -> None:
        _enable_branch_awareness(monkeypatch)
        monkeypatch.setattr(
            manifest_mod,
            "branch_owner",
            lambda *a, **k: BranchOwner(slug="other", kind=OWNER_CONVENTION),
        )
        monkeypatch.setattr(sys, "stdin", _FakeStdin(tty=False))
        co = _Recorder(result=(0, ""))
        create = _Recorder(result=(0, ""))
        set_b = _Recorder()
        monkeypatch.setattr(manifest_mod, "checkout_existing_branch", co)
        monkeypatch.setattr(manifest_mod, "create_and_checkout_branch", create)
        monkeypatch.setattr(manifest_mod, "set_binding", set_b)
        rc = manifest_mod.cmd_attach_branch(
            self._args(registered_plan, "demo", "plan/other")
        )
        assert rc == 2
        assert not co.called and not create.called and not set_b.called

    def test_attach_rehome_refuses_dirty_tree(
        self, registered_plan, monkeypatch, capsys
    ) -> None:
        _enable_branch_awareness(monkeypatch)
        monkeypatch.setattr(
            manifest_mod,
            "branch_owner",
            lambda *a, **k: BranchOwner(slug="other", kind=OWNER_CONVENTION),
        )
        monkeypatch.setattr(manifest_mod, "working_tree_dirty", lambda r: True)
        create = _Recorder(result=(0, ""))
        set_b = _Recorder()
        monkeypatch.setattr(manifest_mod, "create_and_checkout_branch", create)
        monkeypatch.setattr(manifest_mod, "set_binding", set_b)
        rc = manifest_mod.cmd_attach_branch(
            self._args(registered_plan, "demo", "plan/other", "-y")
        )
        assert rc == 2
        assert "clean working tree" in capsys.readouterr().err
        assert not create.called and not set_b.called

    def test_attach_rehome_creates_from_existing(
        self, registered_plan, monkeypatch
    ) -> None:
        _enable_branch_awareness(monkeypatch)
        monkeypatch.setattr(
            manifest_mod,
            "branch_owner",
            lambda *a, **k: BranchOwner(slug="other", kind=OWNER_CONVENTION),
        )
        monkeypatch.setattr(manifest_mod, "working_tree_dirty", lambda r: False)
        monkeypatch.setattr(manifest_mod, "current_branch", lambda r: "main")
        # rehome (plan/demo) absent, colliding (plan/other) present.
        monkeypatch.setattr(
            manifest_mod,
            "branch_exists",
            lambda r, name: name == "plan/other",
        )
        co = _Recorder(result=(0, ""))
        create = _Recorder(result=(0, ""))
        set_b = _Recorder()
        monkeypatch.setattr(manifest_mod, "checkout_existing_branch", co)
        monkeypatch.setattr(manifest_mod, "create_and_checkout_branch", create)
        monkeypatch.setattr(manifest_mod, "set_binding", set_b)
        rc = manifest_mod.cmd_attach_branch(
            self._args(registered_plan, "demo", "plan/other", "-y")
        )
        assert rc == 0
        assert co.calls == [(registered_plan.root, "plan/other")]
        assert create.calls == [(registered_plan.root, "plan/demo")]
        assert set_b.calls == [(registered_plan.root, "demo", "plan/demo")]

    def test_attach_rehome_reuses_existing_rehome_branch(
        self, registered_plan, monkeypatch
    ) -> None:
        _enable_branch_awareness(monkeypatch)
        monkeypatch.setattr(
            manifest_mod,
            "branch_owner",
            lambda *a, **k: BranchOwner(slug="other", kind=OWNER_CONVENTION),
        )
        monkeypatch.setattr(manifest_mod, "working_tree_dirty", lambda r: False)
        monkeypatch.setattr(manifest_mod, "current_branch", lambda r: "main")
        monkeypatch.setattr(
            manifest_mod, "branch_exists", lambda r, name: name == "plan/demo"
        )
        co = _Recorder(result=(0, ""))
        create = _Recorder(result=(0, ""))
        set_b = _Recorder()
        monkeypatch.setattr(manifest_mod, "checkout_existing_branch", co)
        monkeypatch.setattr(manifest_mod, "create_and_checkout_branch", create)
        monkeypatch.setattr(manifest_mod, "set_binding", set_b)
        rc = manifest_mod.cmd_attach_branch(
            self._args(registered_plan, "demo", "plan/other", "-y")
        )
        assert rc == 0
        assert co.calls == [(registered_plan.root, "plan/demo")]
        assert not create.called
        assert set_b.calls == [(registered_plan.root, "demo", "plan/demo")]

    def test_attach_rehome_mutator_failure_no_bind(
        self, registered_plan, monkeypatch, capsys
    ) -> None:
        _enable_branch_awareness(monkeypatch)
        monkeypatch.setattr(
            manifest_mod,
            "branch_owner",
            lambda *a, **k: BranchOwner(slug="other", kind=OWNER_CONVENTION),
        )
        monkeypatch.setattr(manifest_mod, "working_tree_dirty", lambda r: False)
        monkeypatch.setattr(manifest_mod, "current_branch", lambda r: "main")
        monkeypatch.setattr(
            manifest_mod, "branch_exists", lambda r, name: name == "plan/other"
        )
        # checkout the colliding branch succeeds, then create fails.
        co = _Recorder(result=(0, ""))
        monkeypatch.setattr(manifest_mod, "checkout_existing_branch", co)
        monkeypatch.setattr(
            manifest_mod,
            "create_and_checkout_branch",
            lambda r, name: (1, "create failed"),
        )
        set_b = _Recorder()
        monkeypatch.setattr(manifest_mod, "set_binding", set_b)
        rc = manifest_mod.cmd_attach_branch(
            self._args(registered_plan, "demo", "plan/other", "-y")
        )
        assert rc == 2
        assert not set_b.called
        assert "create failed" in capsys.readouterr().err

    def test_attach_remote_only_collision_warns_and_binds(
        self, registered_plan, monkeypatch, capsys
    ) -> None:
        _enable_branch_awareness(monkeypatch)
        monkeypatch.setattr(manifest_mod, "branch_owner", lambda *a, **k: None)
        monkeypatch.setattr(
            manifest_mod, "list_branches", lambda r: ["origin/feat/x"]
        )
        set_b = _Recorder()
        monkeypatch.setattr(manifest_mod, "set_binding", set_b)
        rc = manifest_mod.cmd_attach_branch(
            self._args(registered_plan, "demo", "feat/x")
        )
        assert rc == 0
        assert set_b.calls == [(registered_plan.root, "demo", "feat/x")]
        err = capsys.readouterr().err
        assert "origin/feat/x" in err
        assert "no network" in err

    def test_attach_flag_off_reads_no_branches(
        self, registered_plan, monkeypatch
    ) -> None:
        monkeypatch.delenv("PLAN_TOOL_BRANCH_AWARENESS", raising=False)

        def _boom(r):
            raise AssertionError("list_branches must not be read when flag off")

        monkeypatch.setattr(manifest_mod, "list_branches", _boom)
        rc = manifest_mod.cmd_attach_branch(
            self._args(registered_plan, "demo", "feat/x")
        )
        assert rc == 2

    def test_attach_local_orphan_plus_remote_warns_and_binds(
        self, registered_plan, monkeypatch, capsys
    ) -> None:
        _enable_branch_awareness(monkeypatch)
        monkeypatch.setattr(manifest_mod, "branch_owner", lambda *a, **k: None)
        monkeypatch.setattr(
            manifest_mod, "list_branches", lambda r: ["feat/x", "origin/feat/x"]
        )
        set_b = _Recorder()
        monkeypatch.setattr(manifest_mod, "set_binding", set_b)
        rc = manifest_mod.cmd_attach_branch(
            self._args(registered_plan, "demo", "feat/x")
        )
        assert rc == 0
        assert set_b.calls == [(registered_plan.root, "demo", "feat/x")]
        assert "origin/feat/x" in capsys.readouterr().err

    def test_attach_remote_no_collision_silent(
        self, registered_plan, monkeypatch, capsys
    ) -> None:
        _enable_branch_awareness(monkeypatch)
        monkeypatch.setattr(manifest_mod, "branch_owner", lambda *a, **k: None)
        monkeypatch.setattr(manifest_mod, "list_branches", lambda r: [])
        set_b = _Recorder()
        monkeypatch.setattr(manifest_mod, "set_binding", set_b)
        rc = manifest_mod.cmd_attach_branch(
            self._args(registered_plan, "demo", "feat/x")
        )
        assert rc == 0
        assert set_b.calls == [(registered_plan.root, "demo", "feat/x")]
        assert "no network" not in capsys.readouterr().err

    def test_attach_self_owned_skips_remote_read(
        self, registered_plan, monkeypatch
    ) -> None:
        _enable_branch_awareness(monkeypatch)
        monkeypatch.setattr(
            manifest_mod,
            "branch_owner",
            lambda *a, **k: BranchOwner(slug="demo", kind=OWNER_CONVENTION),
        )

        def _boom(r):
            raise AssertionError("self-owned re-attach must not read remote")

        monkeypatch.setattr(manifest_mod, "list_branches", _boom)
        set_b = _Recorder()
        monkeypatch.setattr(manifest_mod, "set_binding", set_b)
        rc = manifest_mod.cmd_attach_branch(
            self._args(registered_plan, "demo", "plan/demo")
        )
        assert rc == 0
        assert set_b.calls == [(registered_plan.root, "demo", "plan/demo")]

    def test_attach_adhoc_refuse_does_not_read_remote(
        self, registered_plan, monkeypatch, capsys
    ) -> None:
        _enable_branch_awareness(monkeypatch)
        monkeypatch.setattr(
            manifest_mod,
            "branch_owner",
            lambda *a, **k: BranchOwner(slug="other", kind=OWNER_AD_HOC),
        )

        def _boom(r):
            raise AssertionError("ad-hoc refuse must not read remote")

        monkeypatch.setattr(manifest_mod, "list_branches", _boom)
        set_b = _Recorder()
        monkeypatch.setattr(manifest_mod, "set_binding", set_b)
        rc = manifest_mod.cmd_attach_branch(
            self._args(registered_plan, "demo", "feat/x")
        )
        assert rc == 2
        assert "already attached" in capsys.readouterr().err
        assert not set_b.called

    def test_attach_rehome_does_not_read_remote(
        self, registered_plan, monkeypatch
    ) -> None:
        _enable_branch_awareness(monkeypatch)
        monkeypatch.setattr(
            manifest_mod,
            "branch_owner",
            lambda *a, **k: BranchOwner(slug="other", kind=OWNER_CONVENTION),
        )
        monkeypatch.setattr(manifest_mod, "working_tree_dirty", lambda r: False)
        monkeypatch.setattr(manifest_mod, "current_branch", lambda r: "main")
        monkeypatch.setattr(
            manifest_mod, "branch_exists", lambda r, name: name == "plan/other"
        )

        def _boom(r):
            raise AssertionError("re-home path must not read remote")

        monkeypatch.setattr(manifest_mod, "list_branches", _boom)
        monkeypatch.setattr(
            manifest_mod, "checkout_existing_branch", _Recorder(result=(0, ""))
        )
        monkeypatch.setattr(
            manifest_mod, "create_and_checkout_branch", _Recorder(result=(0, ""))
        )
        monkeypatch.setattr(manifest_mod, "set_binding", _Recorder())
        rc = manifest_mod.cmd_attach_branch(
            self._args(registered_plan, "demo", "plan/other", "-y")
        )
        assert rc == 0


class TestDetachBranch:
    def _args(self, repo, *extra: str):
        return build_parser().parse_args(repo.argv("detach-branch", *extra))

    def test_detach_refuses_when_disabled(
        self, registered_plan, monkeypatch, capsys
    ) -> None:
        monkeypatch.delenv("PLAN_TOOL_BRANCH_AWARENESS", raising=False)
        clear = _Recorder(result=True)
        monkeypatch.setattr(manifest_mod, "clear_binding", clear)
        rc = manifest_mod.cmd_detach_branch(self._args(registered_plan, "demo"))
        assert rc == 2
        assert "disabled" in capsys.readouterr().err
        assert not clear.called

    def test_detach_clears_existing(
        self, registered_plan, monkeypatch, capsys
    ) -> None:
        _enable_branch_awareness(monkeypatch)
        monkeypatch.setattr(manifest_mod, "clear_binding", lambda r, slug: True)
        rc = manifest_mod.cmd_detach_branch(self._args(registered_plan, "demo"))
        assert rc == 0
        assert "cleared branch override for demo" in capsys.readouterr().out

    def test_detach_quiet_when_absent(
        self, registered_plan, monkeypatch, capsys
    ) -> None:
        _enable_branch_awareness(monkeypatch)
        monkeypatch.setattr(manifest_mod, "clear_binding", lambda r, slug: False)
        rc = manifest_mod.cmd_detach_branch(self._args(registered_plan, "demo"))
        assert rc == 0
        assert "no branch override to clear for demo" in capsys.readouterr().err

    def test_detach_unresolvable_plan_returns_2(
        self, registered_plan, monkeypatch
    ) -> None:
        _enable_branch_awareness(monkeypatch)
        rc = manifest_mod.cmd_detach_branch(
            self._args(registered_plan, "missing-slug")
        )
        assert rc == 2


class TestAttachDetachParserSurface:
    def test_attach_detach_registered(self) -> None:
        import argparse

        from plan_tool.cli.parser import assemble

        parser, dispatch = assemble(
            manifest_mod.__doc__ or "", [manifest_mod]
        )
        assert dispatch["attach-branch"] is manifest_mod.cmd_attach_branch
        assert dispatch["detach-branch"] is manifest_mod.cmd_detach_branch
        # Each subparser renders non-empty help (mirrors the step's gate).
        sub_action = next(
            a
            for a in parser._actions
            if isinstance(a, argparse._SubParsersAction)
        )
        assert sub_action.choices["attach-branch"].format_help()
        assert sub_action.choices["detach-branch"].format_help()


class TestSweepCommit:
    def test_commit_archives_completed_plan_and_commits(self, tmp_repo) -> None:
        from plan_tool.cli import main

        _real_git_repo(tmp_repo)
        plan = _add_completed_plan(tmp_repo)
        tmp_repo.write_manifest()
        _git_commit_all(tmp_repo.root, "init")

        rc = main(tmp_repo.argv("sweep", "--commit", "-y"))

        assert rc == 0
        assert not plan.exists()
        assert (tmp_repo.plans_dir / "archive" / "1-done.md").is_file()
        assert (
            _git_log_subjects(tmp_repo.root)[0]
            == "sweep: archive 1 completed plan"
        )
        assert _git_tree_clean(tmp_repo.root)

    def test_commit_nothing_to_sweep_makes_no_commit(
        self, tmp_repo, capsys
    ) -> None:
        from plan_tool.cli import main

        _real_git_repo(tmp_repo)
        tmp_repo.add_plan("1-demo", title="Demo")  # planning — not completed
        tmp_repo.write_manifest()
        _git_commit_all(tmp_repo.root, "init")

        rc = main(tmp_repo.argv("sweep", "--commit", "-y"))

        assert rc == 0
        assert _git_log_subjects(tmp_repo.root) == ["init"]
        assert "nothing to commit" in capsys.readouterr().err

    def test_commit_rejects_dirty_tree(self, tmp_repo, capsys) -> None:
        from plan_tool.cli import main

        _real_git_repo(tmp_repo)
        _add_completed_plan(tmp_repo)
        tmp_repo.write_manifest()
        _git_commit_all(tmp_repo.root, "init")
        (tmp_repo.root / "stray.txt").write_text("x\n", encoding="utf-8")

        rc = main(tmp_repo.argv("sweep", "--commit", "-y"))

        assert rc == 2
        assert "clean working tree" in capsys.readouterr().err

    def test_commit_rejects_dry_run(self, tmp_repo, capsys) -> None:
        from plan_tool.cli import main

        _real_git_repo(tmp_repo)
        _add_completed_plan(tmp_repo)
        tmp_repo.write_manifest()
        _git_commit_all(tmp_repo.root, "init")

        rc = main(tmp_repo.argv("sweep", "--commit", "--dry-run", "-y"))

        assert rc == 2
        assert "nothing to commit" in capsys.readouterr().err

    def test_commit_rejects_report_only(self, tmp_repo, capsys) -> None:
        from plan_tool.cli import main

        _real_git_repo(tmp_repo)
        _add_completed_plan(tmp_repo)
        tmp_repo.write_manifest()
        _git_commit_all(tmp_repo.root, "init")

        rc = main(tmp_repo.argv("sweep", "--commit", "--report-only", "-y"))

        assert rc == 2
        assert "nothing to commit" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Stale-manifest-path fallback: `--manifest` omitted resolves under
# `--repo-root`, never cwd (regression for the bare `default_manifest_path()`
# call in `cmd_register` / `cmd_deregister` / `cmd_sweep`).
# ---------------------------------------------------------------------------


_PLANNING_PLAN_TEXT = (
    "---\n"
    "title: Demo Plan\n"
    "status: planning\n"
    "priority: low\n"
    "steps:\n"
    "  - id: 1\n"
    "    title: Only step\n"
    "---\n"
    "# Body\n"
)


def _two_git_roots(tmp_path):
    """Two `.git`-rooted dirs: one used as ``--repo-root``, one as cwd.

    Both carry a ``.git`` marker so the buggy cwd-walk would *succeed*
    (and write the manifest under cwd) — the test proves the fix routes
    the write to ``--repo-root`` instead of merely avoiding a crash.
    """
    repo_root = tmp_path / "repo"
    (repo_root / ".git").mkdir(parents=True)
    (repo_root / "plans").mkdir()
    cwd = tmp_path / "elsewhere"
    (cwd / ".git").mkdir(parents=True)
    return repo_root, cwd


def _repo_manifest(repo_root):
    return repo_root / ".plan-tool" / "plans.json"


class TestManifestFallbackHonorsRepoRoot:
    def _chdir_elsewhere(self, monkeypatch, cwd) -> None:
        monkeypatch.delenv("PLAN_TOOL_PLANS_DIR", raising=False)
        monkeypatch.delenv("PLAN_TOOL_REPO_ROOT", raising=False)
        monkeypatch.chdir(cwd)

    def test_manifest_lands_under_repo_root_not_cwd(
        self, tmp_path, monkeypatch
    ) -> None:
        from plan_tool.cli import main

        repo_root, cwd = _two_git_roots(tmp_path)
        plan_path = repo_root / "plans" / "1-demo.md"
        plan_path.write_text(_PLANNING_PLAN_TEXT, encoding="utf-8")
        self._chdir_elsewhere(monkeypatch, cwd)

        rc = main(["--repo-root", str(repo_root), "register", str(plan_path)])

        assert rc == 0
        manifest = _repo_manifest(repo_root)
        assert manifest.is_file()
        assert "plans/1-demo.md" in json.loads(
            manifest.read_text(encoding="utf-8")
        )["plans"]
        # No manifest was created under the ambient cwd.
        assert not _repo_manifest(cwd).exists()

    def test_deregister_reads_repo_root_manifest_not_cwd(
        self, tmp_path, monkeypatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from plan_tool.cli import main

        repo_root, cwd = _two_git_roots(tmp_path)
        plan_path = repo_root / "plans" / "1-demo.md"
        plan_path.write_text(_PLANNING_PLAN_TEXT, encoding="utf-8")
        manifest = _repo_manifest(repo_root)
        manifest.parent.mkdir(parents=True)
        manifest.write_text(
            json.dumps({"plans": ["plans/1-demo.md"]}), encoding="utf-8"
        )
        self._chdir_elsewhere(monkeypatch, cwd)

        rc = main(["--repo-root", str(repo_root), "deregister", "plans/1-demo.md"])

        out = capsys.readouterr().out
        assert rc == 0
        assert "deregistered plans/1-demo.md" in out
        assert "not registered" not in out
        assert json.loads(manifest.read_text(encoding="utf-8"))["plans"] == []

    def test_sweep_archives_and_deregisters_under_repo_root_not_cwd(
        self, tmp_path, monkeypatch
    ) -> None:
        from plan_tool.cli import main

        repo_root, cwd = _two_git_roots(tmp_path)
        plan_path = repo_root / "plans" / "1-done.md"
        plan_path.write_text(_COMPLETED_PLAN_TEXT, encoding="utf-8")
        manifest = _repo_manifest(repo_root)
        manifest.parent.mkdir(parents=True)
        manifest.write_text(
            json.dumps({"plans": ["plans/1-done.md"]}), encoding="utf-8"
        )
        self._chdir_elsewhere(monkeypatch, cwd)

        rc = main(["--repo-root", str(repo_root), "sweep", "-y"])

        assert rc == 0
        assert not plan_path.exists()
        assert (repo_root / "plans" / "archive" / "1-done.md").is_file()
        # Deregistered from the repo-root manifest, not left dangling there.
        assert json.loads(manifest.read_text(encoding="utf-8"))["plans"] == []
