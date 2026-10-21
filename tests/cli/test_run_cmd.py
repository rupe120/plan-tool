"""Characterization tests for the ``run <name> --all`` sweep controller.

``_cmd_run_sweep`` is the loop behind ``plan-tool run <name> --all``: it
resolves the next-runnable step, runs it, and repeats until the plan
completes, a step exits non-zero, or ``--max-steps`` is hit. The plan's
``COVERAGE_BASELINE.md`` marks it ``indirectly covered`` — every existing
test reaches it only through ``main(["run", …, "--all"])`` — so per the
cli-package-split plan these are its first *direct* tests, importing the
symbol from ``plan_tool.cli`` and calling it with a hand-built
``PlanToolContext`` + ``argparse.Namespace``. That names the function
(converting the verdict to *directly covered*) while staying split-proof:
no ``plan_tool.cli`` module global is patched (see ``test_package_surface.py``).

Scope is the deterministic surface that returns *before* any claude call —
the flag-validation gates ("mode routing") and the no-runnable early exit.
The claude-driven loop body (happy-path advance, halt-on-failure exit-code
propagation, ``--max-steps`` cap, ``--all`` implies ``-y``) is pinned
end-to-end in ``tests/test_cli.py`` and the inventory pointer stands in for it
rather than a duplicate that would have to stub the claude subprocess:

  - sweep happy path / halt-on-failure / max-steps cap / implies-yes
        → ``tests/test_cli.py`` ``TestRunAllSweep``
  - the same ``--all`` gates driven through ``main()``
        → ``tests/test_cli.py`` ``TestCmdRunAll``
  - ``run --reconcile`` mutex with ``--mode`` / ``--iterate`` (``cmd_run``'s
    own routing, not the sweep's)
        → ``tests/test_cli.py`` ``TestRunReconcileDispatch``
"""

from __future__ import annotations

import argparse
import json as _json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from plan_tool import launcher
from plan_tool.backend import CODEX_BACKEND, set_active_backend
from plan_tool.claude_errors import get_rate_limit_resume_command
import plan_tool.cli.run_cmd as run_cmd
from plan_tool.cli import _cmd_run_sweep
from plan_tool.cli.run_cmd import (
    _archive_on_completion,
    _build_run_resume_command,
    _commit_green_step,
    _confirm_missing_step_details,
    _detail_grade,
    _green_commit_subject,
    _load_run_prefs,
    _open_plan_entries,
    _preflight_branch_guard,
    _preflight_jira_grade_details,
    _prompt_run_scope,
    _record_sweep_halt,
    _save_run_prefs,
    _select_open_plan,
    _warn_missing_step_detail,
    _working_tree_dirty,
)
from plan_tool.branch_ownership import BranchClassification, Tier
from plan_tool.locator import PlanToolContext
from plan_tool.parser import parse_plan
from plan_tool.plan_merge_guard import NO_REMOTE, MergeCheck


def _sweep_args(**overrides) -> argparse.Namespace:
    """A ``run --all`` namespace with every attribute the sweep reads.

    Defaults describe a vanilla ``plan-tool run demo --all`` (mode=run, no
    ``--step`` / ``--reconcile``, no iteration budget overrides); each test
    flips exactly the field whose gate it exercises.
    """
    base = dict(
        name="demo",
        step=None,
        mode="run",
        max_steps=None,
        reconcile=False,
        commit=False,
        archive=False,
        iterate=False,
        max_iterations=10,
        iteration_budget=900,
        max_stall_rounds=2,
        dry_run=False,
        no_save=False,
        no_walk=False,
        yes=False,
        allow_missing_parent=False,
        switch_branch=False,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def _ctx(repo_root: Path) -> PlanToolContext:
    return PlanToolContext(repo_root=repo_root, plans_dir=None, entries=[])


def _init_git_repo(repo: Path) -> None:
    """``git init`` + throwaway identity so commits succeed in a tmp repo.

    Mirrors ``plan_tool/bench.py:_git_init_scratch``."""
    subprocess.run(
        ["git", "init", "-q"],
        cwd=repo,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
    )
    for key, value in (
        ("user.email", "test@plan-tool.local"),
        ("user.name", "plan-tool test"),
    ):
        subprocess.run(
            ["git", "config", key, value],
            cwd=repo,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=True,
        )


def _all_done_plan(repo_root: Path) -> Path:
    """A registered-shape plan whose only step is already ``done`` — so
    ``resolve_step`` finds nothing runnable and the sweep is a no-op."""
    path = repo_root / "done.md"
    path.write_text(
        "---\n"
        "title: Done\n"
        "status: completed\n"
        "priority: low\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: only step\n"
        "    status: done\n"
        "---\n",
        encoding="utf-8",
    )
    return path


class TestGradeFlagSuffix:
    """Every printed `plan-tool run` line carries the active grade.

    A hint that drops it sends the operator to a run rendering from the
    other contract's body — the mismatch `_build_run_resume_command`
    already guards against.
    """

    @staticmethod
    def _args(grade: str) -> argparse.Namespace:
        return argparse.Namespace(name="p", grade=grade, detail_grade=grade)

    def test_default_grade_adds_nothing(self) -> None:
        assert run_cmd._grade_flag_suffix(self._args("run")) == ""

    def test_non_default_grade_is_carried(self) -> None:
        assert run_cmd._grade_flag_suffix(self._args("jira")) == (
            " --detail-grade jira"
        )

    def test_missing_attribute_falls_back_to_default(self) -> None:
        # Hand-built namespaces are a repo-wide test idiom; a missing
        # attribute must not raise inside a console print path.
        assert run_cmd._grade_flag_suffix(argparse.Namespace(name="p")) == ""


class TestSweepFlagGates:
    """Flag combinations the sweep rejects with rc=2 before opening a log."""

    def test_step_and_all_are_mutually_exclusive(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = _cmd_run_sweep(
            _sweep_args(step=1), ctx=_ctx(tmp_path), plan_path=tmp_path / "p.md"
        )
        assert rc == 2
        assert "--all and --step are mutually exclusive" in capsys.readouterr().err

    def test_review_mode_redirects_to_verify_all(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = _cmd_run_sweep(
            _sweep_args(mode="check"), ctx=_ctx(tmp_path), plan_path=tmp_path / "p.md"
        )
        assert rc == 2
        err = capsys.readouterr().err
        assert "verify-all" in err
        assert "--mode check" in err

    def test_reconcile_flag_rejected(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = _cmd_run_sweep(
            _sweep_args(reconcile=True), ctx=_ctx(tmp_path),
            plan_path=tmp_path / "p.md",
        )
        assert rc == 2
        assert "mutually exclusive with --reconcile" in capsys.readouterr().err

    def test_max_steps_below_one_rejected(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = _cmd_run_sweep(
            _sweep_args(max_steps=0), ctx=_ctx(tmp_path),
            plan_path=tmp_path / "p.md",
        )
        assert rc == 2
        assert "--max-steps must be >= 1" in capsys.readouterr().err

    def test_bad_iteration_budget_rejected(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # The budget is validated once up front (a bad value would fail every
        # per-iteration call identically), so it's surfaced before the loop.
        rc = _cmd_run_sweep(
            _sweep_args(max_iterations=0), ctx=_ctx(tmp_path),
            plan_path=tmp_path / "p.md",
        )
        assert rc == 2
        assert "--max-iterations must be >= 1" in capsys.readouterr().err

    def test_gate_rejection_opens_no_run_log(self, tmp_path: Path) -> None:
        # A rejected invocation must not leave a ghost run-log directory.
        _cmd_run_sweep(
            _sweep_args(step=1), ctx=_ctx(tmp_path), plan_path=tmp_path / "p.md"
        )
        assert not (tmp_path / ".plan-tool" / "runs").exists()

    def test_commit_requires_clean_tree(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # A dirty tree at sweep start trips the precheck (rc=2) before any
        # run-log dir is created.
        _init_git_repo(tmp_path)
        (tmp_path / "dirty.txt").write_text("uncommitted", encoding="utf-8")
        rc = _cmd_run_sweep(
            _sweep_args(commit=True),
            ctx=_ctx(tmp_path),
            plan_path=tmp_path / "p.md",
        )
        assert rc == 2
        assert "--commit requires a clean working tree" in capsys.readouterr().err
        assert not (tmp_path / ".plan-tool" / "runs").exists()

    def test_commit_clean_tree_precheck_passes(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # A clean tree does not false-trip the precheck: the sweep proceeds
        # to the no-runnable exit (rc=0). ``_all_done_plan`` writes done.md,
        # which must be committed so ``git status --porcelain`` is empty.
        _init_git_repo(tmp_path)
        plan_path = _all_done_plan(tmp_path)
        subprocess.run(
            ["git", "add", "-A"], cwd=tmp_path,
            stdin=subprocess.DEVNULL, capture_output=True, check=True,
        )
        subprocess.run(
            ["git", "commit", "-q", "-m", "baseline"], cwd=tmp_path,
            stdin=subprocess.DEVNULL, capture_output=True, check=True,
        )
        rc = _cmd_run_sweep(
            _sweep_args(commit=True), ctx=_ctx(tmp_path), plan_path=plan_path
        )
        assert rc == 0
        assert "nothing to sweep" in capsys.readouterr().err


def _completed_plan_and_manifest(repo_root: Path) -> tuple[Path, Path]:
    """A registered ``status: completed`` plan + a manifest listing it.

    Returns ``(plan_path, manifest_path)``. The plan's lone step is
    already ``done`` so :func:`classify_plan` reports it complete and
    ``_archive_on_completion`` archives it.
    """
    plan_path = _all_done_plan(repo_root)
    manifest_path = repo_root / "m.json"
    manifest_path.write_text(
        _json.dumps({"plans": [plan_path.name]}), encoding="utf-8"
    )
    return plan_path, manifest_path


def _running_plan_and_manifest(repo_root: Path) -> tuple[Path, Path]:
    """A registered plan with one pending step — NOT complete."""
    plan_path = repo_root / "running.md"
    plan_path.write_text(
        "---\n"
        "title: Running\n"
        "status: in-progress\n"
        "priority: low\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: first step\n"
        "    status: done\n"
        "  - id: 2\n"
        "    title: second step\n"
        "    status: pending\n"
        "---\n",
        encoding="utf-8",
    )
    manifest_path = repo_root / "m.json"
    manifest_path.write_text(
        _json.dumps({"plans": [plan_path.name]}), encoding="utf-8"
    )
    return plan_path, manifest_path


class TestArchiveOnCompletion:
    """Direct tests of ``_archive_on_completion`` — the deterministic
    before-claude surface ``--archive`` wires into both run-completion
    paths. No claude call; the plan is on disk already at N/N done."""

    def test_archives_completed_plan_moves_file_and_deregisters(
        self, tmp_path: Path
    ) -> None:
        plan_path, manifest_path = _completed_plan_and_manifest(tmp_path)
        outcome = _archive_on_completion(
            plan_path, ctx=_ctx(tmp_path), manifest_path=manifest_path
        )
        assert outcome is not None
        assert outcome.archived_to is not None
        assert outcome.archived_to.parent == tmp_path / "archive"
        assert not plan_path.exists()
        assert outcome.deregistered is True
        manifest = _json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["plans"] == []

    def test_archives_moves_plan_details(self, tmp_path: Path) -> None:
        plan_path, manifest_path = _completed_plan_and_manifest(tmp_path)
        details_src = tmp_path / "plan-details" / "done"
        details_src.mkdir(parents=True)
        (details_src / "step-01.md").write_text(
            "# step one detail\n", encoding="utf-8"
        )
        _archive_on_completion(
            plan_path, ctx=_ctx(tmp_path), manifest_path=manifest_path
        )
        archived_detail = (
            tmp_path / "archive" / "plan-details" / "done" / "step-01.md"
        )
        assert archived_detail.is_file()
        body = archived_detail.read_text(encoding="utf-8")
        assert "Auto-archived" in body
        assert "# step one detail" in body
        assert not details_src.exists()

    def test_prints_archived_path_and_register_undo_hint(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        plan_path, manifest_path = _completed_plan_and_manifest(tmp_path)
        _archive_on_completion(
            plan_path, ctx=_ctx(tmp_path), manifest_path=manifest_path
        )
        out = capsys.readouterr().out
        assert "archive/done.md" in out
        assert "plan-tool register" in out
        assert "archive/done.md" in out.split("plan-tool register", 1)[1]

    def test_noop_with_note_when_plan_not_completed(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        plan_path, manifest_path = _running_plan_and_manifest(tmp_path)
        before = plan_path.read_text(encoding="utf-8")
        outcome = _archive_on_completion(
            plan_path, ctx=_ctx(tmp_path), manifest_path=manifest_path
        )
        assert outcome is None
        out = capsys.readouterr().out
        assert "not complete" in out
        assert "1/2 done" in out
        # File and manifest untouched.
        assert plan_path.read_text(encoding="utf-8") == before
        manifest = _json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["plans"] == [plan_path.name]

    def test_handles_missing_manifest_entry_gracefully(
        self, tmp_path: Path
    ) -> None:
        plan_path = _all_done_plan(tmp_path)
        # A manifest that does not list the plan — deregister is a
        # best-effort no-op, the file move still happens.
        manifest_path = tmp_path / "m.json"
        manifest_path.write_text(
            _json.dumps({"plans": []}), encoding="utf-8"
        )
        outcome = _archive_on_completion(
            plan_path, ctx=_ctx(tmp_path), manifest_path=manifest_path
        )
        assert outcome is not None
        assert outcome.archived_to is not None
        assert not plan_path.exists()
        assert outcome.deregistered is False


def _pending_plan(repo_root: Path, *, detail: str | None) -> Path:
    """A plan whose step 1 is runnable, optionally declaring a ``detail`` path.

    The detail path (when given) is recorded verbatim; the test controls
    whether the referenced file actually exists on disk.
    """
    detail_line = f"    detail: {detail}\n" if detail is not None else ""
    path = repo_root / "feature.md"
    path.write_text(
        "---\n"
        "title: Feature\n"
        "status: planning\n"
        "priority: low\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: only step\n"
        "    status: pending\n"
        f"{detail_line}"
        "---\n",
        encoding="utf-8",
    )
    return path


class TestMissingDetailWarning:
    """``run`` recommends a detail file before invoking claude for a
    detail-less step — a recommendation, not a gate."""

    def test_warns_when_detail_field_unset(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        plan_path = _pending_plan(tmp_path, detail=None)
        warned = _warn_missing_step_detail(
            plan_path, repo_root=tmp_path, plan_name="feature", step_id=None
        )
        assert warned is True
        err = capsys.readouterr().err
        assert "step 1 has no detail file" in err
        assert "plan-tool detail feature --step 1" in err

    def test_warns_when_detail_file_missing_on_disk(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Field points at a path that was never written.
        plan_path = _pending_plan(
            tmp_path, detail="plan-details/feature/step-01.md"
        )
        warned = _warn_missing_step_detail(
            plan_path, repo_root=tmp_path, plan_name="feature", step_id=None
        )
        assert warned is True
        assert "plan-tool detail feature --step 1" in capsys.readouterr().err

    def test_silent_when_detail_file_exists(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        detail_rel = "plan-details/feature/step-01.md"
        detail_abs = tmp_path / detail_rel
        detail_abs.parent.mkdir(parents=True)
        detail_abs.write_text("# Step 1 detail\n", encoding="utf-8")
        plan_path = _pending_plan(tmp_path, detail=detail_rel)
        warned = _warn_missing_step_detail(
            plan_path, repo_root=tmp_path, plan_name="feature", step_id=None
        )
        assert warned is False
        assert capsys.readouterr().err == ""

    def test_silent_when_plan_unresolvable(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # A bad plan path resolves to nothing; run_step surfaces the real
        # error, so the recommendation stays quiet.
        warned = _warn_missing_step_detail(
            tmp_path / "missing.md",
            repo_root=tmp_path,
            plan_name="feature",
            step_id=None,
        )
        assert warned is False
        assert capsys.readouterr().err == ""


class TestMissingDetailGate:
    """``run`` warns and confirms before executing a step whose detail
    file is missing — a gate (unlike the non-blocking recommendation)."""

    def test_proceeds_under_yes_after_warning(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        plan_path = _pending_plan(tmp_path, detail=None)
        proceed = _confirm_missing_step_details(
            plan_path,
            repo_root=tmp_path,
            plan_name="feature",
            step_id=None,
            all_steps=False,
            yes=True,
        )
        assert proceed is True
        assert "detail file missing for step(s) 1" in capsys.readouterr().err

    def test_silent_and_proceeds_when_detail_exists(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        detail_rel = "plan-details/feature/step-01.md"
        detail_abs = tmp_path / detail_rel
        detail_abs.parent.mkdir(parents=True)
        detail_abs.write_text("# detail\n", encoding="utf-8")
        plan_path = _pending_plan(tmp_path, detail=detail_rel)
        proceed = _confirm_missing_step_details(
            plan_path,
            repo_root=tmp_path,
            plan_name="feature",
            step_id=None,
            all_steps=False,
            yes=False,
        )
        assert proceed is True
        assert capsys.readouterr().err == ""

    def test_non_tty_proceeds_with_warning(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(run_cmd, "_stdin_is_tty", lambda: False)
        plan_path = _pending_plan(tmp_path, detail=None)
        proceed = _confirm_missing_step_details(
            plan_path,
            repo_root=tmp_path,
            plan_name="feature",
            step_id=None,
            all_steps=False,
            yes=False,
        )
        assert proceed is True
        assert "not a TTY" in capsys.readouterr().err

    def test_tty_confirm_yes_proceeds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(run_cmd, "_stdin_is_tty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda _prompt="": "y")
        plan_path = _pending_plan(tmp_path, detail=None)
        assert (
            _confirm_missing_step_details(
                plan_path,
                repo_root=tmp_path,
                plan_name="feature",
                step_id=None,
                all_steps=False,
                yes=False,
            )
            is True
        )

    def test_tty_default_no_aborts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(run_cmd, "_stdin_is_tty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda _prompt="": "")
        plan_path = _pending_plan(tmp_path, detail=None)
        assert (
            _confirm_missing_step_details(
                plan_path,
                repo_root=tmp_path,
                plan_name="feature",
                step_id=None,
                all_steps=False,
                yes=False,
            )
            is False
        )

    def test_all_steps_flags_any_missing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Two steps; step 1 has a detail file, step 2 does not. The
        # whole-plan gate (the ``--all`` sweep) must flag step 2.
        detail_rel = "plan-details/feature/step-01.md"
        detail_abs = tmp_path / detail_rel
        detail_abs.parent.mkdir(parents=True)
        detail_abs.write_text("# detail\n", encoding="utf-8")
        plan_path = tmp_path / "feature.md"
        plan_path.write_text(
            "---\n"
            "title: Feature\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: first step\n"
            "    status: pending\n"
            f"    detail: {detail_rel}\n"
            "  - id: 2\n"
            "    title: second step\n"
            "    status: pending\n"
            "---\n",
            encoding="utf-8",
        )
        proceed = _confirm_missing_step_details(
            plan_path,
            repo_root=tmp_path,
            plan_name="feature",
            step_id=None,
            all_steps=True,
            yes=True,
        )
        assert proceed is True
        err = capsys.readouterr().err
        assert "detail file missing for step(s) 2" in err

    def test_all_steps_ignores_done_steps(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Step 1 is done with no detail (archived); step 2 is pending with
        # a detail file. A sweep only runs not-done steps, so the gate must
        # stay silent and proceed.
        detail_rel = "plan-details/feature/step-02.md"
        detail_abs = tmp_path / detail_rel
        detail_abs.parent.mkdir(parents=True)
        detail_abs.write_text("# detail\n", encoding="utf-8")
        plan_path = tmp_path / "feature.md"
        plan_path.write_text(
            "---\n"
            "title: Feature\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: first step\n"
            "    status: done\n"
            "  - id: 2\n"
            "    title: second step\n"
            "    status: pending\n"
            f"    detail: {detail_rel}\n"
            "---\n",
            encoding="utf-8",
        )
        proceed = _confirm_missing_step_details(
            plan_path,
            repo_root=tmp_path,
            plan_name="feature",
            step_id=None,
            all_steps=True,
            yes=False,
        )
        assert proceed is True
        assert capsys.readouterr().err == ""

    def test_unresolvable_plan_proceeds_silently(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        proceed = _confirm_missing_step_details(
            tmp_path / "missing.md",
            repo_root=tmp_path,
            plan_name="feature",
            step_id=None,
            all_steps=False,
            yes=False,
        )
        assert proceed is True
        assert capsys.readouterr().err == ""


class TestSweepNoRunnableStep:
    """An all-done plan reports nothing to sweep and exits cleanly."""

    def test_reports_and_exits_zero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        plan_path = _all_done_plan(tmp_path)
        rc = _cmd_run_sweep(
            _sweep_args(), ctx=_ctx(tmp_path), plan_path=plan_path
        )
        assert rc == 0
        assert "nothing to sweep" in capsys.readouterr().err

    def test_opens_no_run_log_when_nothing_runnable(
        self, tmp_path: Path
    ) -> None:
        plan_path = _all_done_plan(tmp_path)
        _cmd_run_sweep(_sweep_args(), ctx=_ctx(tmp_path), plan_path=plan_path)
        # The run logger is created only after ``resolve_step`` succeeds, so a
        # plan with no runnable step leaves no run-log dir behind.
        assert not (tmp_path / ".plan-tool" / "runs").exists()


def _git_log_subject(repo: Path) -> str:
    """Subject of the most recent commit."""
    proc = subprocess.run(
        ["git", "log", "-1", "--format=%s"],
        cwd=repo, stdin=subprocess.DEVNULL, capture_output=True,
        text=True, check=True,
    )
    return proc.stdout.strip()


def _git_log_body(repo: Path) -> str:
    """Body of the most recent commit."""
    proc = subprocess.run(
        ["git", "log", "-1", "--format=%b"],
        cwd=repo, stdin=subprocess.DEVNULL, capture_output=True,
        text=True, check=True,
    )
    return proc.stdout


def _commit_baseline(repo: Path) -> None:
    """Stage everything and make an initial commit so the tree is clean."""
    subprocess.run(
        ["git", "add", "-A"], cwd=repo,
        stdin=subprocess.DEVNULL, capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", "baseline"], cwd=repo,
        stdin=subprocess.DEVNULL, capture_output=True, check=True,
    )


class TestCommitGreenStep:
    """The per-step commit helpers ``--commit`` builds on."""

    def test_green_commit_subject_format(self) -> None:
        assert (
            _green_commit_subject("demo", 3, "My step")
            == "plan(demo): step 3 green — My step"
        )

    def test_green_commit_subject_truncates_long_title(self) -> None:
        long_title = "Add an opt-in --archive flag and wire it through " * 5
        subject = _green_commit_subject("demo", 1, long_title)
        # Title portion is capped with an ellipsis; subject stays sane width.
        assert subject.startswith("plan(demo): step 1 green — ")
        assert subject.endswith("…")
        assert len(subject) < 100  # was ~250 chars untruncated

    def test_commit_creates_one_commit_with_mirrored_subject(
        self, tmp_path: Path
    ) -> None:
        _init_git_repo(tmp_path)
        (tmp_path / "f.txt").write_text("v1", encoding="utf-8")
        _commit_baseline(tmp_path)
        (tmp_path / "f.txt").write_text("v2", encoding="utf-8")
        rc, _tail = _commit_green_step(
            tmp_path, slug="demo", step_id=3, step_title="My step"
        )
        assert rc == 0
        assert _git_log_subject(tmp_path) == "plan(demo): step 3 green — My step"
        # No AI-attribution trailer — the operator's own git identity is the
        # sole author of record.
        assert _git_log_body(tmp_path).strip() == ""

    def test_commit_stages_untracked_files(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        (tmp_path / "f.txt").write_text("v1", encoding="utf-8")
        _commit_baseline(tmp_path)
        # A brand-new untracked file present before the commit call.
        (tmp_path / "new.txt").write_text("fresh", encoding="utf-8")
        rc, _tail = _commit_green_step(
            tmp_path, slug="demo", step_id=1, step_title="t"
        )
        assert rc == 0
        listing = subprocess.run(
            ["git", "show", "--name-only", "--format=", "HEAD"],
            cwd=tmp_path, stdin=subprocess.DEVNULL, capture_output=True,
            text=True, check=True,
        )
        assert "new.txt" in listing.stdout

    def test_commit_returns_nonzero_when_nothing_to_commit(
        self, tmp_path: Path
    ) -> None:
        _init_git_repo(tmp_path)
        (tmp_path / "f.txt").write_text("v1", encoding="utf-8")
        _commit_baseline(tmp_path)
        # Tree is clean — git refuses to make an empty commit.
        rc, _tail = _commit_green_step(
            tmp_path, slug="demo", step_id=1, step_title="t"
        )
        assert rc != 0

    def test_working_tree_dirty_detects_modification(
        self, tmp_path: Path
    ) -> None:
        _init_git_repo(tmp_path)
        (tmp_path / "f.txt").write_text("v1", encoding="utf-8")
        _commit_baseline(tmp_path)
        (tmp_path / "f.txt").write_text("v2", encoding="utf-8")
        assert _working_tree_dirty(tmp_path) is True

    def test_working_tree_clean_after_commit(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        (tmp_path / "f.txt").write_text("v1", encoding="utf-8")
        _commit_baseline(tmp_path)
        assert _working_tree_dirty(tmp_path) is False


def _lessons_plan(repo_root: Path, *, lessons: str | None) -> "object":
    """Parse a one-step plan that optionally declares a ``lessons:`` path.

    Returns the parsed ``Plan`` (its ``.lessons`` field is what
    ``_record_sweep_halt`` reads). The path is recorded verbatim; the
    file itself is not created here so the helper's mkdir behavior stays
    under test.
    """
    lessons_line = f"lessons: {lessons}\n" if lessons is not None else ""
    path = repo_root / "halt.md"
    path.write_text(
        "---\n"
        "title: Halt\n"
        "status: in-progress\n"
        "priority: low\n"
        f"{lessons_line}"
        "steps:\n"
        "  - id: 1\n"
        "    title: only step\n"
        "    status: current\n"
        "---\n",
        encoding="utf-8",
    )
    return parse_plan(path)


_FIXED_TS = datetime(2026, 6, 8, 12, 0, 0, tzinfo=timezone.utc)


class TestRecordSweepHalt:
    """``_record_sweep_halt`` self-records sweep halts to the plan's
    ``lessons:`` file in the launcher's append-only format."""

    def test_records_halt_line_in_sweep_format(self, tmp_path: Path) -> None:
        plan = _lessons_plan(tmp_path, lessons="plan-details/halt/lessons.md")
        lessons_path = _record_sweep_halt(
            plan,
            repo_root=tmp_path,
            step_id=2,
            reason="run failed (exit code 42)",
            now=_FIXED_TS,
        )
        assert lessons_path is not None
        assert lessons_path.read_text(encoding="utf-8") == (
            "- 2026-06-08T12:00:00Z step 2 halt (sweep): "
            "run failed (exit code 42)\n"
        )

    def test_noop_when_lessons_unset(self, tmp_path: Path) -> None:
        plan = _lessons_plan(tmp_path, lessons=None)
        result = _record_sweep_halt(
            plan, repo_root=tmp_path, step_id=1, reason="boom"
        )
        assert result is None
        # Nothing was written anywhere under the repo root.
        assert not any(p.suffix == ".md" and p.name != "halt.md"
                       for p in tmp_path.rglob("*"))

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        plan = _lessons_plan(
            tmp_path, lessons="plan-details/halt/nested/lessons.md"
        )
        lessons_path = _record_sweep_halt(
            plan, repo_root=tmp_path, step_id=1, reason="boom", now=_FIXED_TS
        )
        assert lessons_path is not None
        assert lessons_path.is_file()
        assert lessons_path == tmp_path / "plan-details/halt/nested/lessons.md"

    def test_appends_not_overwrites(self, tmp_path: Path) -> None:
        plan = _lessons_plan(tmp_path, lessons="plan-details/halt/lessons.md")
        lessons_path = tmp_path / "plan-details/halt/lessons.md"
        lessons_path.parent.mkdir(parents=True)
        lessons_path.write_text(
            "- 2026-06-01T00:00:00Z step 1: First thing\n", encoding="utf-8"
        )
        _record_sweep_halt(
            plan, repo_root=tmp_path, step_id=2, reason="boom", now=_FIXED_TS
        )
        content = lessons_path.read_text(encoding="utf-8")
        assert content == (
            "- 2026-06-01T00:00:00Z step 1: First thing\n"
            "- 2026-06-08T12:00:00Z step 2 halt (sweep): boom\n"
        )

    def test_halt_line_not_counted_as_step_completion(
        self, tmp_path: Path
    ) -> None:
        # The ``halt (sweep)`` segment dodges ``_LESSONS_STEP_RE`` so a
        # halt never inflates the completion-entry counter (which would
        # otherwise trip ``append_lesson``'s idempotency guard).
        plan = _lessons_plan(tmp_path, lessons="plan-details/halt/lessons.md")
        lessons_path = _record_sweep_halt(
            plan, repo_root=tmp_path, step_id=2, reason="boom", now=_FIXED_TS
        )
        assert launcher.read_lessons_step_ids(lessons_path) == set()

    def test_preflight_reason_not_counted_as_step_completion(
        self, tmp_path: Path
    ) -> None:
        # A representative call-site-2 ``reason=str(exc)`` payload. It is
        # regex-safe because of its own text (no adjacent ``step N:``),
        # not the ``halt (sweep)`` prefix — pin that the preflight
        # messages reaching call site 2 at HEAD don't inflate counting.
        plan = _lessons_plan(tmp_path, lessons="plan-details/halt/lessons.md")
        lessons_path = _record_sweep_halt(
            plan,
            repo_root=tmp_path,
            step_id=3,
            reason="step 3 declared file paths don't resolve under repo root",
            now=_FIXED_TS,
        )
        assert launcher.read_lessons_step_ids(lessons_path) == set()
        # Companion: a reason that *does* embed ``step N:`` adjacent to a
        # colon WOULD be counted — pinning the safe-vs-unsafe boundary so
        # a regex-unsafe LauncherError reword can't be believed safe.
        lessons_path.write_text(
            "- 2026-06-08T12:00:00Z step 9 halt (sweep): step 3: blew up\n",
            encoding="utf-8",
        )
        assert launcher.read_lessons_step_ids(lessons_path) == {3}

    def test_returns_written_path(self, tmp_path: Path) -> None:
        plan = _lessons_plan(tmp_path, lessons="plan-details/halt/lessons.md")
        lessons_path = _record_sweep_halt(
            plan, repo_root=tmp_path, step_id=1, reason="boom"
        )
        assert lessons_path == tmp_path / "plan-details/halt/lessons.md"


def _open_plan_file(
    repo: Path, fname: str, statuses: list[str], *, status: str = "in-progress"
) -> Path:
    """Write a directory-mode plan whose steps carry ``statuses``.

    ``status="completed"`` + all-``done`` steps makes an all-done plan the
    picker must exclude; the default leaves at least one open step.
    """
    p = repo / fname
    steps = "\n".join(
        f"  - id: {i + 1}\n    title: step {i + 1}\n    status: {s}"
        for i, s in enumerate(statuses)
    )
    p.write_text(
        f"---\ntitle: t\nstatus: {status}\npriority: high\nsteps:\n{steps}\n---\n",
        encoding="utf-8",
    )
    return p


def _entry(path: Path) -> "object":
    from plan_tool.locator import PlanEntry
    from plan_tool.parser import parse_plan

    return PlanEntry(path=path, plan=parse_plan(path), error=None)


class TestRunPrefs:
    """The picker's last-plan + per-plan scope memory file."""

    def test_roundtrip_records_plan_and_scope(self, tmp_path: Path) -> None:
        _save_run_prefs(tmp_path, last_plan="alpha", scope="all")
        prefs = _load_run_prefs(tmp_path)
        assert prefs["last_plan"] == "alpha"
        assert prefs["scope_by_plan"]["alpha"] == "all"

    def test_none_scope_updates_plan_only(self, tmp_path: Path) -> None:
        _save_run_prefs(tmp_path, last_plan="alpha", scope="next")
        _save_run_prefs(tmp_path, last_plan="beta", scope=None)
        prefs = _load_run_prefs(tmp_path)
        assert prefs["last_plan"] == "beta"
        # beta has no remembered scope; alpha's survives.
        assert "beta" not in prefs["scope_by_plan"]
        assert prefs["scope_by_plan"]["alpha"] == "next"

    def test_missing_file_is_empty(self, tmp_path: Path) -> None:
        assert _load_run_prefs(tmp_path) == {}

    def test_corrupt_file_is_empty(self, tmp_path: Path) -> None:
        p = run_cmd._run_prefs_path(tmp_path)
        p.parent.mkdir(parents=True)
        p.write_text("{not json", encoding="utf-8")
        assert _load_run_prefs(tmp_path) == {}


class TestOpenPlanFilter:
    def test_excludes_all_done_and_unparseable(self, tmp_path: Path) -> None:
        from plan_tool.locator import PlanEntry, PlanToolContext

        open_e = _entry(_open_plan_file(tmp_path, "1-alpha.md", ["done", "pending"]))
        done_e = _entry(
            _open_plan_file(tmp_path, "1-beta.md", ["done"], status="completed")
        )
        bad_e = PlanEntry(path=tmp_path / "bad.md", plan=None, error="boom")
        ctx = PlanToolContext(
            repo_root=tmp_path, plans_dir=tmp_path, entries=[open_e, done_e, bad_e]
        )
        assert [e.slug for e in _open_plan_entries(ctx)] == ["alpha"]


class TestPickerPrompts:
    def _ctx_with(self, tmp_path: Path, *files):
        from plan_tool.locator import PlanToolContext

        entries = [_entry(f) for f in files]
        return PlanToolContext(
            repo_root=tmp_path, plans_dir=tmp_path, entries=entries
        )

    def test_enter_picks_last_plan_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        a = _open_plan_file(tmp_path, "1-alpha.md", ["pending"])
        b = _open_plan_file(tmp_path, "1-beta.md", ["pending"])
        ctx = self._ctx_with(tmp_path, a, b)
        monkeypatch.setattr("builtins.input", lambda *_: "")  # Enter
        sel = _select_open_plan(ctx, last_plan="beta")
        assert sel is not None and sel[1] == "beta"

    def test_quit_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        a = _open_plan_file(tmp_path, "1-alpha.md", ["pending"])
        ctx = self._ctx_with(tmp_path, a)
        monkeypatch.setattr("builtins.input", lambda *_: "q")
        assert _select_open_plan(ctx, last_plan=None) is None

    def test_no_candidates_returns_none(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from plan_tool.locator import PlanToolContext

        ctx = PlanToolContext(repo_root=tmp_path, plans_dir=tmp_path, entries=[])
        assert _select_open_plan(ctx, last_plan=None) is None
        assert "no plans with open steps" in capsys.readouterr().out

    def test_scope_default_taken_on_enter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("builtins.input", lambda *_: "")
        assert _prompt_run_scope("all") == "all"
        assert _prompt_run_scope("next") == "next"

    def test_scope_explicit_choice(self, monkeypatch: pytest.MonkeyPatch) -> None:
        answers = iter(["a", "n"])
        monkeypatch.setattr("builtins.input", lambda *_: next(answers))
        assert _prompt_run_scope("next") == "all"
        assert _prompt_run_scope("all") == "next"


class TestCmdRunPicker:
    """`cmd_run`'s early-return picker paths (none reach a claude call)."""

    def _args(self, repo: Path, **ov) -> argparse.Namespace:
        base = dict(
            plans_dir=repo,
            manifest=None,
            repo_root=repo,
            name=None,
            step=None,
            all=False,
            reconcile=False,
            mode="run",
            iterate=False,
            dry_run=False,
            switch_branch=False,
        )
        base.update(ov)
        return argparse.Namespace(**base)

    def test_no_name_non_tty_errors(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(run_cmd, "_stdin_is_tty", lambda: False)
        assert run_cmd.cmd_run(self._args(tmp_path)) == 2
        assert "not a TTY" in capsys.readouterr().err

    def test_no_name_tty_quit_returns_0(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _open_plan_file(tmp_path, "1-alpha.md", ["pending"])
        monkeypatch.setattr(run_cmd, "_stdin_is_tty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda *_: "q")
        assert run_cmd.cmd_run(self._args(tmp_path)) == 0

    def test_run_unmatched_fence_writes_no_preferences_or_run_log(
        self, tmp_path: Path
    ) -> None:
        plan_path = _open_plan_file(tmp_path, "1-alpha.md", ["pending"])
        plan_path.write_text(
            plan_path.read_text(encoding="utf-8") + "\n```\n",
            encoding="utf-8",
        )

        assert run_cmd.cmd_run(self._args(tmp_path, name="alpha")) == 2
        assert not (tmp_path / ".plan-tool").exists()

    def test_pick_all_dispatches_sweep_and_saves_prefs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _open_plan_file(tmp_path, "1-alpha.md", ["pending"])
        seen: dict = {}

        def fake_sweep(args, *, ctx, plan_path):
            seen["all"] = args.all
            seen["name"] = args.name
            return 0

        monkeypatch.setattr(run_cmd, "_cmd_run_sweep", fake_sweep)
        monkeypatch.setattr(run_cmd, "_stdin_is_tty", lambda: True)
        answers = iter(["", "a"])  # pick default plan, then scope=all
        monkeypatch.setattr("builtins.input", lambda *_: next(answers))
        assert run_cmd.cmd_run(self._args(tmp_path)) == 0
        assert seen == {"all": True, "name": "alpha"}
        prefs = _load_run_prefs(tmp_path)
        assert prefs["last_plan"] == "alpha"
        assert prefs["scope_by_plan"]["alpha"] == "all"

    def test_bad_name_non_tty_reraises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(run_cmd, "_stdin_is_tty", lambda: False)
        with pytest.raises(FileNotFoundError):
            run_cmd.cmd_run(self._args(tmp_path, name="nope"))

    def test_bad_name_tty_falls_back_to_picker(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _open_plan_file(tmp_path, "1-alpha.md", ["pending"])
        monkeypatch.setattr(
            run_cmd, "_cmd_run_sweep", lambda a, *, ctx, plan_path: 0
        )
        monkeypatch.setattr(run_cmd, "_stdin_is_tty", lambda: True)
        answers = iter(["", "a"])
        monkeypatch.setattr("builtins.input", lambda *_: next(answers))
        assert run_cmd.cmd_run(self._args(tmp_path, name="nope")) == 0
        # The unresolved name was surfaced before the picker took over.
        assert "nope" in capsys.readouterr().err

    def test_default_scope_from_remembered_choice(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _open_plan_file(tmp_path, "1-alpha.md", ["pending"])
        _save_run_prefs(tmp_path, last_plan="alpha", scope="all")
        monkeypatch.setattr(
            run_cmd, "_cmd_run_sweep", lambda a, *, ctx, plan_path: 0
        )
        monkeypatch.setattr(run_cmd, "_stdin_is_tty", lambda: True)
        # Enter at the plan menu (default = remembered "alpha"), Enter at
        # the scope prompt (default = remembered "all") -> sweep dispatch.
        answers = iter(["", ""])
        monkeypatch.setattr("builtins.input", lambda *_: next(answers))
        assert run_cmd.cmd_run(self._args(tmp_path)) == 0


# --------------------------------------------------------------------------
# --reuse / --no-reuse / --reuse-id parse contract (run / reconcile-code)
# --------------------------------------------------------------------------
#
# The reconcile-family reuse switch mirrors completeness-audit's
# --reuse-audit family flag-for-flag. ``--reuse`` is a tri-state
# BooleanOptionalAction(default=None): None=unset (prompt / auto-decide),
# True=reuse-when-fresh, False=never. ``--reuse-id STEM`` pins one save.
# These are pure parse-contract gates — no claude call.


class TestRunReuseFlags:
    def test_run_reuse_default_is_none(self) -> None:
        from plan_tool.cli import build_parser

        args = build_parser().parse_args(["run", "demo", "--reconcile"])
        assert args.reuse is None
        assert args.reuse_id is None

    def test_run_reuse_and_no_reuse_parse(self) -> None:
        from plan_tool.cli import build_parser

        parser = build_parser()
        assert parser.parse_args(["run", "demo", "--reconcile", "--reuse"]).reuse is True
        assert (
            parser.parse_args(["run", "demo", "--reconcile", "--no-reuse"]).reuse
            is False
        )

    def test_run_reuse_id_parses_stem(self) -> None:
        from plan_tool.cli import build_parser

        args = build_parser().parse_args(
            ["run", "demo", "--reconcile", "--reuse-id", "20260612-120000-run-reconcile"]
        )
        assert args.reuse_id == "20260612-120000-run-reconcile"

    def test_reconcile_code_reuse_flags_parse(self) -> None:
        from plan_tool.cli import build_parser

        parser = build_parser()
        default = parser.parse_args(["reconcile-code", "demo"])
        assert default.reuse is None
        assert default.reuse_id is None
        assert parser.parse_args(["reconcile-code", "demo", "--reuse"]).reuse is True
        assert (
            parser.parse_args(["reconcile-code", "demo", "--no-reuse"]).reuse is False
        )
        pinned = parser.parse_args(
            ["reconcile-code", "demo", "--reuse-id", "20260612-120000"]
        )
        assert pinned.reuse_id == "20260612-120000"


# --------------------------------------------------------------------------
# Branch-awareness preflight guard (``_preflight_branch_guard``)
# --------------------------------------------------------------------------
#
# Drives the guard directly with a hand-built ``PlanToolContext`` + a tiny
# ``Namespace``, monkeypatching the branch symbols imported into
# ``plan_tool.cli.run_cmd`` so no real git/config state is needed (the pure
# tier logic is pinned in ``tests/test_branch_ownership.py``). The guard is a
# no-op when branch awareness is off, so every pre-existing ``run`` test is
# unaffected.


def _guard_args(**ov) -> argparse.Namespace:
    """Minimal namespace the guard reads (only ``switch_branch``)."""
    base = dict(switch_branch=False)
    base.update(ov)
    return argparse.Namespace(**base)


def _patch_guard_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    enabled: bool = True,
    current: str | None = "feature-work",
    classification: BranchClassification | None = None,
    expected: str = "plan/feature",
    convention: str | None = None,
    dirty: bool = False,
    branch_present: bool = False,
    checkout: tuple[int, str] = (0, ""),
    create: tuple[int, str] = (0, ""),
) -> dict:
    """Neutralize the guard's branch reads; return a call-record dict.

    ``record["current_calls"]`` / ``["checkout"]`` / ``["create"]`` let a
    test assert that a branch was (not) read and which mutator (if any)
    ran. ``branch_owner`` returns ``None`` (its result is ignored because
    ``classify_branch`` is patched to return ``classification`` directly).
    """
    record: dict = {"current_calls": 0, "checkout": None, "create": None}

    def _current(_root):
        record["current_calls"] += 1
        return current

    def _checkout(_root, name):
        record["checkout"] = name
        return checkout

    def _create(_root, name):
        record["create"] = name
        return create

    monkeypatch.setattr(run_cmd, "branch_awareness_enabled", lambda _root: enabled)
    monkeypatch.setattr(run_cmd, "current_branch", _current)
    monkeypatch.setattr(run_cmd, "branch_prefixes", lambda _root: ["plan/"])
    monkeypatch.setattr(run_cmd, "branch_owner", lambda *a, **k: None)
    if classification is not None:
        monkeypatch.setattr(
            run_cmd, "classify_branch", lambda *a, **k: classification
        )
    monkeypatch.setattr(run_cmd, "expected_branch", lambda *a, **k: expected)
    monkeypatch.setattr(run_cmd, "convention_owner", lambda *a, **k: convention)
    monkeypatch.setattr(run_cmd, "_working_tree_dirty", lambda _root: dirty)
    monkeypatch.setattr(run_cmd, "branch_exists", lambda _root, _name: branch_present)
    monkeypatch.setattr(run_cmd, "checkout_existing_branch", _checkout)
    monkeypatch.setattr(run_cmd, "create_and_checkout_branch", _create)
    return record


class TestPreflightBranchGuardOffAndNonGit:
    """Off-state and undeterminable-branch no-ops."""

    def test_guard_noop_when_disabled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rec = _patch_guard_env(monkeypatch, enabled=False)
        rc = _preflight_branch_guard(
            _guard_args(), ctx=_ctx(tmp_path), plan_slug="feature"
        )
        assert rc is None
        # No branch is read before the flag check.
        assert rec["current_calls"] == 0

    def test_guard_noop_non_git_or_detached(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # ``classify_branch`` is intentionally NOT patched: reaching it on
        # the ``None`` path would raise, proving we never classify.
        _patch_guard_env(monkeypatch, current=None, classification=None)
        rc = _preflight_branch_guard(
            _guard_args(), ctx=_ctx(tmp_path), plan_slug="feature"
        )
        assert rc is None
        assert "undeterminable" in capsys.readouterr().err


class TestPreflightBranchGuardBlock:
    """Tier 1-2: block unless the branch is this plan's."""

    def test_guard_tier1_blocks_other_plan(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        cls = BranchClassification(
            tier=Tier.AD_HOC_OWNED, owner="other", is_owned_by_plan=False
        )
        _patch_guard_env(monkeypatch, classification=cls)
        rc = _preflight_branch_guard(
            _guard_args(), ctx=_ctx(tmp_path), plan_slug="feature"
        )
        assert rc == 2
        assert "other" in capsys.readouterr().err

    def test_guard_tier1_proceeds_own_plan(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cls = BranchClassification(
            tier=Tier.AD_HOC_OWNED, owner="feature", is_owned_by_plan=True
        )
        _patch_guard_env(monkeypatch, classification=cls)
        rc = _preflight_branch_guard(
            _guard_args(), ctx=_ctx(tmp_path), plan_slug="feature"
        )
        assert rc is None

    def test_guard_tier1_surfaces_shadowed_convention(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        cls = BranchClassification(
            tier=Tier.AD_HOC_OWNED, owner="bound", is_owned_by_plan=False
        )
        _patch_guard_env(monkeypatch, classification=cls, convention="named")
        rc = _preflight_branch_guard(
            _guard_args(), ctx=_ctx(tmp_path), plan_slug="feature"
        )
        assert rc == 2
        err = capsys.readouterr().err
        assert "bound" in err
        assert "named" in err

    def test_guard_tier2_blocks_other_plan(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        cls = BranchClassification(
            tier=Tier.CONVENTION_OWNED, owner="other", is_owned_by_plan=False
        )
        _patch_guard_env(monkeypatch, classification=cls)
        rc = _preflight_branch_guard(
            _guard_args(), ctx=_ctx(tmp_path), plan_slug="feature"
        )
        assert rc == 2
        assert "other" in capsys.readouterr().err

    def test_guard_tier2_proceeds_own_plan(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cls = BranchClassification(
            tier=Tier.CONVENTION_OWNED, owner="feature", is_owned_by_plan=True
        )
        _patch_guard_env(monkeypatch, classification=cls)
        rc = _preflight_branch_guard(
            _guard_args(), ctx=_ctx(tmp_path), plan_slug="feature"
        )
        assert rc is None


class TestPreflightBranchGuardOrphan:
    """Tier 3: warn and proceed."""

    def test_guard_tier3_warns_and_proceeds(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        cls = BranchClassification(
            tier=Tier.ORPHAN_PATTERN, owner=None, is_owned_by_plan=False
        )
        _patch_guard_env(monkeypatch, classification=cls, current="plan/elsewhere")
        rc = _preflight_branch_guard(
            _guard_args(), ctx=_ctx(tmp_path), plan_slug="feature"
        )
        assert rc is None
        err = capsys.readouterr().err
        assert "warning:" in err
        assert "plan/elsewhere" in err


class TestPreflightBranchGuardUnowned:
    """Tier 4: nudge, or clean-tree-gated switch."""

    def _unowned(self) -> BranchClassification:
        return BranchClassification(
            tier=Tier.UNOWNED, owner=None, is_owned_by_plan=False
        )

    def test_guard_tier4_no_action_when_on_expected(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _patch_guard_env(
            monkeypatch,
            classification=self._unowned(),
            current="plan/feature",
            expected="plan/feature",
        )
        rc = _preflight_branch_guard(
            _guard_args(), ctx=_ctx(tmp_path), plan_slug="feature"
        )
        assert rc is None
        assert capsys.readouterr().err == ""

    def test_guard_tier4_nudges_when_elsewhere(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _patch_guard_env(
            monkeypatch,
            classification=self._unowned(),
            current="random",
            expected="plan/feature",
        )
        rc = _preflight_branch_guard(
            _guard_args(switch_branch=False),
            ctx=_ctx(tmp_path),
            plan_slug="feature",
        )
        assert rc is None
        err = capsys.readouterr().err
        assert "plan/feature" in err
        assert "--switch-branch" in err

    def test_guard_tier4_switch_creates_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rec = _patch_guard_env(
            monkeypatch,
            classification=self._unowned(),
            current="random",
            expected="plan/feature",
            dirty=False,
            branch_present=False,
        )
        rc = _preflight_branch_guard(
            _guard_args(switch_branch=True),
            ctx=_ctx(tmp_path),
            plan_slug="feature",
        )
        assert rc is None
        assert rec["create"] == "plan/feature"
        assert rec["checkout"] is None

    def test_guard_tier4_switch_uses_existing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rec = _patch_guard_env(
            monkeypatch,
            classification=self._unowned(),
            current="random",
            expected="plan/feature",
            dirty=False,
            branch_present=True,
        )
        rc = _preflight_branch_guard(
            _guard_args(switch_branch=True),
            ctx=_ctx(tmp_path),
            plan_slug="feature",
        )
        assert rc is None
        assert rec["checkout"] == "plan/feature"
        assert rec["create"] is None

    def test_guard_tier4_switch_branch_already_in_worktree_clean_message(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # The expected branch is already checked out in a worktree (e.g. from
        # `worktree add`); git refuses. The guard must surface an actionable
        # message pointing at the worktree, not exit on the raw fatal alone.
        _patch_guard_env(
            monkeypatch,
            classification=self._unowned(),
            current="random",
            expected="plan/feature",
            dirty=False,
            branch_present=True,
            checkout=(
                128,
                "fatal: 'plan/feature' is already checked out at '/wt/feature'",
            ),
        )
        rc = _preflight_branch_guard(
            _guard_args(switch_branch=True),
            ctx=_ctx(tmp_path),
            plan_slug="feature",
        )
        assert rc == 2
        err = capsys.readouterr().err
        assert "already checked out in another worktree" in err
        assert "plan-tool worktree remove feature" in err

    def test_guard_tier4_switch_refuses_dirty(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        rec = _patch_guard_env(
            monkeypatch,
            classification=self._unowned(),
            current="random",
            expected="plan/feature",
            dirty=True,
        )
        rc = _preflight_branch_guard(
            _guard_args(switch_branch=True),
            ctx=_ctx(tmp_path),
            plan_slug="feature",
        )
        assert rc == 2
        assert "clean working tree" in capsys.readouterr().err
        assert rec["checkout"] is None and rec["create"] is None

    def test_guard_tier4_switch_mutator_failure(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _patch_guard_env(
            monkeypatch,
            classification=self._unowned(),
            current="random",
            expected="plan/feature",
            branch_present=False,
            create=(1, "fatal: cannot create"),
        )
        rc = _preflight_branch_guard(
            _guard_args(switch_branch=True),
            ctx=_ctx(tmp_path),
            plan_slug="feature",
        )
        assert rc == 2
        assert "fatal: cannot create" in capsys.readouterr().err


class _FakeRunResult:
    """Minimal ``run_step`` return stub for the call-site gating tests."""

    exit_code = 0
    step_id = 1
    stdout = ""
    advanced_to = None
    plan_completed = False
    done = True


class TestRunResumeCommand:
    """Rate-limit resume command registered by ``run`` backend call paths."""

    def _args(self, **ov) -> argparse.Namespace:
        base = dict(
            commit=False,
            all=False,
            step=None,
            archive=False,
            dry_run=False,
            allow_missing_parent=False,
            model=None,
        )
        base.update(ov)
        return argparse.Namespace(**base)

    def test_build_run_resume_command_names_backend_plan_and_run_flags(
        self,
    ) -> None:
        set_active_backend(CODEX_BACKEND)
        cmd = _build_run_resume_command(
            self._args(
                commit=True,
                all=True,
                archive=True,
                dry_run=True,
                allow_missing_parent=True,
            ),
            "feature plan",
        )
        assert (
            cmd
            == "plan-tool --backend codex run 'feature plan' --commit "
            "--all --archive --dry-run --allow-missing-parent"
        )

    def test_build_run_resume_command_includes_explicit_step(
        self,
    ) -> None:
        set_active_backend(CODEX_BACKEND)
        cmd = _build_run_resume_command(self._args(step=7), "feature")
        assert cmd == "plan-tool --backend codex run feature --step 7"

    def test_build_run_resume_command_includes_explicit_model(self) -> None:
        set_active_backend(CODEX_BACKEND)
        cmd = _build_run_resume_command(
            self._args(model="gpt-5.6-terra"), "feature"
        )
        assert cmd == "plan-tool --backend codex --model gpt-5.6-terra run feature"

    def test_build_run_resume_command_omits_model_after_backend_switch(self) -> None:
        set_active_backend(CODEX_BACKEND)
        cmd = _build_run_resume_command(
            self._args(model="claude-opus-4-6"),
            "feature",
            initial_backend_name="claude",
        )
        assert cmd == "plan-tool --backend codex run feature"

    def test_cmd_run_registers_resume_command_during_run_step(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _pending_plan(tmp_path, detail=None)
        seen: list[str | None] = []

        def fake_run_step(*_args, **_kwargs):
            seen.append(get_rate_limit_resume_command())
            return _FakeRunResult()

        set_active_backend(CODEX_BACKEND)
        monkeypatch.setattr(run_cmd, "run_step", fake_run_step)
        monkeypatch.setattr(run_cmd, "_working_tree_dirty", lambda *_args: False)
        monkeypatch.setattr(run_cmd, "_commit_green_step", lambda *a, **k: (0, ""))

        rc = run_cmd.cmd_run(
            TestPreflightBranchGuardCallSite()._args(
                tmp_path,
                step=3,
                commit=True,
                archive=True,
                allow_missing_parent=True,
            )
        )

        assert rc == 0
        assert seen == [
            "plan-tool --backend codex run feature --commit --step 3 "
            "--archive --allow-missing-parent"
        ]
        assert get_rate_limit_resume_command() is None


class TestPreflightBranchGuardCallSite:
    """The mutating-only call-site predicate (``mode == run`` ∧ not dry-run)."""

    def _args(self, repo: Path, **ov) -> argparse.Namespace:
        base = dict(
            plans_dir=repo,
            manifest=None,
            repo_root=repo,
            name="feature",
            step=None,
            all=False,
            reconcile=False,
            mode="run",
            iterate=False,
            dry_run=False,
            yes=True,
            no_save=False,
            no_walk=False,
            allow_missing_parent=False,
            archive=False,
            switch_branch=False,
            max_iterations=10,
            iteration_budget=900,
            max_stall_rounds=2,
        )
        base.update(ov)
        return argparse.Namespace(**base)

    def test_run_review_mode_skips_guard(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _pending_plan(tmp_path, detail=None)
        seen: list[int] = []
        monkeypatch.setattr(
            run_cmd, "_preflight_branch_guard", lambda *a, **k: seen.append(1)
        )
        # Stub run_step so a review mode never reaches the real claude backend.
        monkeypatch.setattr(
            run_cmd, "run_step", lambda *a, **k: _FakeRunResult()
        )
        rc = run_cmd.cmd_run(self._args(tmp_path, mode="check"))
        assert rc == 0
        assert seen == []

    def test_run_dry_run_skips_guard(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _pending_plan(tmp_path, detail=None)
        seen: list[int] = []
        monkeypatch.setattr(
            run_cmd, "_preflight_branch_guard", lambda *a, **k: seen.append(1)
        )
        monkeypatch.setattr(
            run_cmd, "run_step", lambda *a, **k: _FakeRunResult()
        )
        rc = run_cmd.cmd_run(self._args(tmp_path, dry_run=True))
        assert rc == 0
        assert seen == []


class TestPreflightMergedPlanGuard:
    """``_preflight_merged_plan_guard``: refuse on the default branch or before the plan is fully on it."""

    @staticmethod
    def _patch(monkeypatch: pytest.MonkeyPatch, *, check, current: str | None = "feature", required: bool = True) -> dict:
        calls = {"check": 0}

        def _check(_root, _plan, grade="run"):
            calls["check"] += 1
            calls["grade"] = grade
            return check

        monkeypatch.setattr(run_cmd, "require_merged_plan", lambda _root: required)
        monkeypatch.setattr(run_cmd, "check_plan_merged", _check)
        monkeypatch.setattr(run_cmd, "current_branch", lambda _root: current)
        return calls

    @staticmethod
    def _run(tmp_path: Path, **ov) -> int | None:
        args = argparse.Namespace(**{"skip_merge_check": False, **ov})
        return run_cmd._preflight_merged_plan_guard(args, ctx=_ctx(tmp_path), plan_path=tmp_path / "demo.md")

    def test_skip_flag_bypasses_the_check_and_says_so(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        calls = self._patch(monkeypatch, check=MergeCheck(default_ref="origin/main", missing=("plan.md",)))
        assert self._run(tmp_path, skip_merge_check=True) is None
        assert calls["check"] == 0
        assert "skipped" in capsys.readouterr().err

    def test_config_off_bypasses_the_check_silently(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        calls = self._patch(monkeypatch, check=MergeCheck(default_ref="origin/main", missing=("plan.md",)), required=False)
        assert self._run(tmp_path) is None
        assert calls["check"] == 0
        assert capsys.readouterr().err == ""

    def test_no_origin_remote_proceeds_without_a_word(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._patch(monkeypatch, check=MergeCheck(unverifiable=NO_REMOTE))
        assert self._run(tmp_path) is None
        assert capsys.readouterr().err == ""

    def test_any_other_unverifiable_reason_warns_and_proceeds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._patch(monkeypatch, check=MergeCheck(unverifiable="the plan is outside the repository"))
        assert self._run(tmp_path) is None
        assert "cannot verify" in capsys.readouterr().err

    def test_running_on_the_default_branch_is_refused(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._patch(monkeypatch, check=MergeCheck(default_ref="origin/main"), current="main")
        assert self._run(tmp_path) == 2
        err = capsys.readouterr().err
        assert "default branch 'main'" in err and "--skip-merge-check" in err

    def test_missing_files_are_refused_with_the_remedy_and_capped_in_the_list(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        missing = tuple(f"docs/d/{i:02}.md" for i in range(11))
        self._patch(monkeypatch, check=MergeCheck(default_ref="origin/main", missing=missing))
        assert self._run(tmp_path) == 2
        err = capsys.readouterr().err
        assert "origin/main" in err and "docs/d/00.md" in err and "and 3 more" in err
        assert "docs/d/10.md" not in err
        assert "git fetch" in err and "--skip-merge-check" in err

    def test_drift_warns_but_proceeds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._patch(monkeypatch, check=MergeCheck(default_ref="origin/main", drifted=("plan.md",)))
        assert self._run(tmp_path) is None
        assert "edited after the plan merged" in capsys.readouterr().err

    def test_the_check_is_told_which_detail_grade_the_run_will_read(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = self._patch(monkeypatch, check=MergeCheck(default_ref="origin/main"))
        assert self._run(tmp_path, detail_grade="jira") is None
        assert calls["grade"] == "jira"

    def test_a_merged_plan_off_the_default_branch_proceeds_silently(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._patch(monkeypatch, check=MergeCheck(default_ref="origin/main"))
        assert self._run(tmp_path) is None
        assert capsys.readouterr().err == ""


class TestPreflightMergedPlanGuardCallSite:
    """The guard runs on a mutating ``run`` only, after the branch guard, and a refusal stops the run."""

    def _args(self, repo: Path, **ov) -> argparse.Namespace:
        return TestPreflightBranchGuardCallSite()._args(repo, **ov)

    def test_a_refusal_stops_the_run_before_any_step_executes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _pending_plan(tmp_path, detail=None)
        ran: list[int] = []
        monkeypatch.setattr(run_cmd, "_preflight_merged_plan_guard", lambda *a, **k: 2)
        monkeypatch.setattr(run_cmd, "run_step", lambda *a, **k: ran.append(1) or _FakeRunResult())
        assert run_cmd.cmd_run(self._args(tmp_path)) == 2
        assert ran == []

    def test_review_mode_and_dry_run_skip_the_guard(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _pending_plan(tmp_path, detail=None)
        seen: list[int] = []
        monkeypatch.setattr(run_cmd, "_preflight_merged_plan_guard", lambda *a, **k: seen.append(1))
        monkeypatch.setattr(run_cmd, "run_step", lambda *a, **k: _FakeRunResult())
        assert run_cmd.cmd_run(self._args(tmp_path, mode="check")) == 0
        assert run_cmd.cmd_run(self._args(tmp_path, dry_run=True)) == 0
        assert seen == []

    def test_the_reconcile_audit_skips_the_guard(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Carve-out: ``--reconcile`` is a code audit that executes no step, like the unguarded ``reconcile-code``.
        _pending_plan(tmp_path, detail=None)
        seen: list[int] = []
        monkeypatch.setattr(run_cmd, "_preflight_merged_plan_guard", lambda *a, **k: seen.append(1))
        monkeypatch.setattr(run_cmd, "_cmd_run_reconcile", lambda *a, **k: 0)
        assert run_cmd.cmd_run(self._args(tmp_path, reconcile=True)) == 0
        assert seen == []

    def test_the_branch_guard_runs_first_and_its_block_skips_the_merge_guard(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _pending_plan(tmp_path, detail=None)
        seen: list[int] = []
        monkeypatch.setattr(run_cmd, "_preflight_branch_guard", lambda *a, **k: 2)
        monkeypatch.setattr(run_cmd, "_preflight_merged_plan_guard", lambda *a, **k: seen.append(1))
        assert run_cmd.cmd_run(self._args(tmp_path)) == 2
        assert seen == []


class TestRunHelpSurface:
    """The step's gate: ``run --help`` advertises ``--switch-branch``."""

    def test_run_help_advertises_switch_branch(self) -> None:
        from plan_tool.cli import build_parser

        parser = build_parser()
        run_help = ""
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                run_help = action.choices["run"].format_help()
                break
        assert "--switch-branch" in run_help

    def test_run_help_advertises_skip_merge_check(self) -> None:
        from plan_tool.cli import build_parser

        parser = build_parser()
        run_help = ""
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                run_help = action.choices["run"].format_help()
                break
        assert "--skip-merge-check" in run_help


class TestKeyboardInterruptExitCode:
    """batch-authoring-observability step 8: an operator's Ctrl-C during
    either lane's claude call must reach a real process exit 130 instead of
    Python's default ``KeyboardInterrupt`` handler (a raw traceback and exit
    1) — ``app.py``'s dispatcher catches only ``Exception``, so the fix is a
    ``SystemExit`` conversion at each call site, not a change to ``app.py``.
    """

    def test_cmd_run_keyboard_interrupt_exits_130(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _pending_plan(tmp_path, detail=None)

        def raising_run_step(*_a, **_kw):
            raise KeyboardInterrupt()

        monkeypatch.setattr(run_cmd, "run_step", raising_run_step)

        with pytest.raises(SystemExit) as exc_info:
            run_cmd.cmd_run(
                TestPreflightBranchGuardCallSite()._args(tmp_path, step=1)
            )
        assert exc_info.value.code == 130

    def test_sweep_keyboard_interrupt_exits_130(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path, _manifest_path = _running_plan_and_manifest(tmp_path)

        def raising_run_step(*_a, **_kw):
            raise KeyboardInterrupt()

        monkeypatch.setattr(run_cmd, "run_step", raising_run_step)

        with pytest.raises(SystemExit) as exc_info:
            _cmd_run_sweep(_sweep_args(), ctx=_ctx(tmp_path), plan_path=plan_path)
        assert exc_info.value.code == 130

    def test_interrupt_run_end_row_still_records_rc_130(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Proves the SystemExit conversion still runs the finally: record —
        # not just that the process exits cleanly.
        _pending_plan(tmp_path, detail=None)

        def raising_run_step(*_a, **_kw):
            raise KeyboardInterrupt()

        monkeypatch.setattr(run_cmd, "run_step", raising_run_step)

        with pytest.raises(SystemExit):
            run_cmd.cmd_run(
                TestPreflightBranchGuardCallSite()._args(tmp_path, step=1)
            )

        logs = sorted(
            (tmp_path / ".plan-tool" / "runs" / "feature").glob("*.jsonl")
        )
        assert logs, "no run log was written"
        events = [
            _json.loads(line)
            for line in logs[0].read_text(encoding="utf-8").splitlines()
        ]
        run_end = next(e for e in events if e.get("event") == "run_end")
        assert run_end["rc"] == 130
        assert run_end["error"] == "interrupted"


# --------------------------------------------------------------------------
# ``--detail-grade``: the opt-in jira-grade execution lane
# --------------------------------------------------------------------------

_JIRA_ARTIFACT = """## Intent

Ground a run on the compact artifact.

## Change

Read this body instead of the run-grade detail file.

## Constraints

Never substitute the run-grade body.

## Done when

The step executes from this artifact.

## Out of scope

The reconcile lane.
"""


def _graded_plan(repo_root: Path) -> Path:
    """A three-step plan: step 1 done, steps 2–3 still to run."""
    path = repo_root / "feature.md"
    path.write_text(
        "---\n"
        "title: Feature\n"
        "status: planning\n"
        "priority: low\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: first step\n"
        "    status: done\n"
        "  - id: 2\n"
        "    title: second step\n"
        "    status: current\n"
        "  - id: 3\n"
        "    title: third step\n"
        "    depends_on: [2]\n"
        "---\n",
        encoding="utf-8",
    )
    return path


def _write_jira_artifact(
    plan_path: Path, step_id: int, slug: str, body: str = _JIRA_ARTIFACT
) -> Path:
    path = (
        plan_path.parent
        / "plan-details"
        / plan_path.stem
        / "jira"
        / f"{step_id:02d}-{slug}.md"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _read_run_start_flags(repo_root: Path, slug: str) -> dict:
    """The ``flags`` payload of the single run log written under ``slug``."""
    logs = sorted((repo_root / ".plan-tool" / "runs" / slug).glob("*.jsonl"))
    assert logs, "no run log was written"
    for line in logs[0].read_text(encoding="utf-8").splitlines():
        event = _json.loads(line)
        if event.get("event") == "run_start":
            return event.get("flags") or {}
    raise AssertionError("no run_start event in the run log")


class TestDetailGradeFlagSurface:
    """Registration and the argument-validation rejections."""

    def _args(self, repo: Path, **ov) -> argparse.Namespace:
        base = dict(
            plans_dir=repo,
            manifest=None,
            repo_root=repo,
            name="feature",
            step=None,
            all=False,
            reconcile=False,
            mode="run",
            iterate=False,
            dry_run=False,
            yes=True,
            no_save=False,
            no_walk=False,
            allow_missing_parent=False,
            archive=False,
            commit=False,
            switch_branch=False,
            detail_grade="jira",
            max_iterations=10,
            iteration_budget=900,
            max_stall_rounds=2,
        )
        base.update(ov)
        return argparse.Namespace(**base)

    def test_detail_grade_flag_registered(self) -> None:
        from plan_tool.cli import build_parser

        parser = build_parser()
        run_parser = None
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                run_parser = action.choices["run"]
                break
        assert run_parser is not None
        flag = next(
            a for a in run_parser._actions if a.dest == "detail_grade"
        )
        assert flag.option_strings == ["--detail-grade"]
        assert tuple(flag.choices) == ("run", "jira")
        assert flag.default == "run"

    def test_detail_grade_jira_review_mode_rejected_rc2(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _graded_plan(tmp_path)
        rc = run_cmd.cmd_run(self._args(tmp_path, mode="check"))
        assert rc == 2
        assert "execution only" in capsys.readouterr().err
        assert not (tmp_path / ".plan-tool" / "runs").exists()

    def test_detail_grade_jira_reconcile_rejected_rc2(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _graded_plan(tmp_path)
        rc = run_cmd.cmd_run(self._args(tmp_path, reconcile=True))
        assert rc == 2
        assert "--reconcile" in capsys.readouterr().err
        assert not (tmp_path / ".plan-tool" / "runs").exists()

    def test_default_grade_leaves_review_mode_alone(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _graded_plan(tmp_path)
        monkeypatch.setattr(run_cmd, "run_step", lambda *a, **k: _FakeRunResult())
        rc = run_cmd.cmd_run(
            self._args(tmp_path, mode="check", detail_grade="run")
        )
        assert rc == 0


class TestJiraGradePreflight:
    """The aggregated artifact check that runs before any backend call."""

    def test_jira_preflight_aggregates_all_broken_steps(
        self, tmp_path: Path
    ) -> None:
        plan_path = _graded_plan(tmp_path)
        problem = _preflight_jira_grade_details(
            plan_path, repo_root=tmp_path, step_id=None, all_steps=True
        )
        assert problem is not None
        assert "02-second-step.md" in problem
        assert "03-third-step.md" in problem
        assert "2 steps" in problem

    def test_jira_preflight_silent_when_every_step_covered(
        self, tmp_path: Path
    ) -> None:
        plan_path = _graded_plan(tmp_path)
        _write_jira_artifact(plan_path, 2, "second-step")
        _write_jira_artifact(plan_path, 3, "third-step")
        assert (
            _preflight_jira_grade_details(
                plan_path, repo_root=tmp_path, step_id=None, all_steps=True
            )
            is None
        )

    def test_jira_preflight_explicit_done_step_without_artifact(
        self, tmp_path: Path
    ) -> None:
        # Bundle coverage exempts ``done`` steps, so a bundle covering only
        # steps 2–3 is complete — but ``--step 1`` still cannot execute.
        plan_path = _graded_plan(tmp_path)
        _write_jira_artifact(plan_path, 2, "second-step")
        _write_jira_artifact(plan_path, 3, "third-step")

        problem = _preflight_jira_grade_details(
            plan_path, repo_root=tmp_path, step_id=1, all_steps=False
        )
        assert problem is not None
        assert "01-first-step.md" in problem
        assert "bundle is not at fault" in problem
        assert "incomplete" not in problem

        # The sweep's own scope is unaffected...
        assert (
            _preflight_jira_grade_details(
                plan_path, repo_root=tmp_path, step_id=None, all_steps=True
            )
            is None
        )
        # ...and the export accepts the very same bundle, so the two
        # consumers stay in agreement about it: capture_companion_export_input's
        # real per-step capture exempts the done step (its caller only
        # rejects _DETAIL_STATE_MISSING for a non-done step) and validates
        # steps 2-3's artifacts cleanly.
        from plan_tool.jira import (
            _capture_jira_grade_step_detail,
            _DETAIL_STATE_MISSING,
            _DETAIL_STATE_PRESENT,
        )

        plan = parse_plan(plan_path)
        step_1, step_2, step_3 = plan.steps
        assert (
            _capture_jira_grade_step_detail(plan_path, plan, step_1, tmp_path).state
            == _DETAIL_STATE_MISSING
        )
        for step in (step_2, step_3):
            assert (
                _capture_jira_grade_step_detail(plan_path, plan, step, tmp_path).state
                == _DETAIL_STATE_PRESENT
            )

    def test_jira_preflight_rejects_wrong_schema_body(
        self, tmp_path: Path
    ) -> None:
        plan_path = _graded_plan(tmp_path)
        _write_jira_artifact(plan_path, 2, "second-step")
        _write_jira_artifact(
            plan_path,
            3,
            "third-step",
            body="## Summary\n\nx\n\n## Why\n\ny\n\n## Tests\n\nz\n",
        )
        problem = _preflight_jira_grade_details(
            plan_path, repo_root=tmp_path, step_id=None, all_steps=True
        )
        assert problem is not None
        assert "run-grade body at a jira-grade path" in problem

    def test_cmd_run_jira_preflight_returns_rc2_without_invoking(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _graded_plan(tmp_path)

        def boom(*_a, **_k):
            raise AssertionError("run_step must not be reached")

        monkeypatch.setattr(run_cmd, "run_step", boom)
        rc = run_cmd.cmd_run(
            TestDetailGradeFlagSurface()._args(tmp_path, step=2)
        )
        assert rc == 2
        assert "02-second-step.md" in capsys.readouterr().err
        assert not (tmp_path / ".plan-tool" / "runs").exists()

    def test_cmd_run_jira_preflight_fires_under_dry_run(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _graded_plan(tmp_path)

        def boom(*_a, **_k):
            raise AssertionError("run_step must not be reached")

        monkeypatch.setattr(run_cmd, "run_step", boom)
        rc = run_cmd.cmd_run(
            TestDetailGradeFlagSurface()._args(tmp_path, step=2, dry_run=True)
        )
        assert rc == 2


class TestDetailGradeDurability:
    """Resume command + run-log flags carry the grade."""

    def _resume_args(self, **ov) -> argparse.Namespace:
        base = dict(
            commit=False,
            all=False,
            step=None,
            archive=False,
            dry_run=False,
            allow_missing_parent=False,
        )
        base.update(ov)
        return argparse.Namespace(**base)

    def test_resume_command_includes_detail_grade(self) -> None:
        set_active_backend(CODEX_BACKEND)
        cmd = _build_run_resume_command(
            self._resume_args(detail_grade="jira"), "feature"
        )
        assert cmd == (
            "plan-tool --backend codex run feature --detail-grade jira"
        )

    def test_resume_command_omits_default_grade(self) -> None:
        set_active_backend(CODEX_BACKEND)
        cmd = _build_run_resume_command(
            self._resume_args(detail_grade="run"), "feature"
        )
        assert "--detail-grade" not in cmd

    def test_hand_built_namespace_defaults_to_run_grade(self) -> None:
        # The ``_sweep_args`` idiom (and ``direct-run``'s copied namespace)
        # carries no ``detail_grade`` attribute — that must read as run grade,
        # never raise.
        args = _sweep_args()
        assert not hasattr(args, "detail_grade")
        assert _detail_grade(args) == "run"
        set_active_backend(CODEX_BACKEND)
        assert "--detail-grade" not in _build_run_resume_command(args, "demo")

    def test_run_log_flags_include_detail_grade(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = _graded_plan(tmp_path)
        _write_jira_artifact(plan_path, 2, "second-step")
        monkeypatch.setattr(run_cmd, "run_step", lambda *a, **k: _FakeRunResult())
        rc = run_cmd.cmd_run(
            TestDetailGradeFlagSurface()._args(tmp_path, step=2)
        )
        assert rc == 0
        flags = _read_run_start_flags(tmp_path, "feature")
        assert flags["detail_grade"] == "jira"
        assert flags["mode"] == "run"

    def test_sweep_run_log_flags_include_detail_grade(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = _graded_plan(tmp_path)
        _write_jira_artifact(plan_path, 2, "second-step")
        _write_jira_artifact(plan_path, 3, "third-step")
        monkeypatch.setattr(run_cmd, "run_step", lambda *a, **k: _FakeRunResult())
        rc = _cmd_run_sweep(
            _sweep_args(detail_grade="jira", max_steps=1),
            ctx=_ctx(tmp_path),
            plan_path=plan_path,
        )
        assert rc == 0
        flags = _read_run_start_flags(tmp_path, "demo")
        assert flags["detail_grade"] == "jira"
        assert flags["all"] is True

    def test_sweep_threads_detail_grade_to_run_step(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = _graded_plan(tmp_path)
        _write_jira_artifact(plan_path, 2, "second-step")
        _write_jira_artifact(plan_path, 3, "third-step")
        seen: list[str] = []

        def fake_run_step(*_a, **kwargs):
            seen.append(kwargs["detail_grade"])
            return _FakeRunResult()

        monkeypatch.setattr(run_cmd, "run_step", fake_run_step)
        rc = _cmd_run_sweep(
            _sweep_args(detail_grade="jira", max_steps=1),
            ctx=_ctx(tmp_path),
            plan_path=plan_path,
        )
        assert rc == 0
        assert seen == ["jira"]

    def test_sweep_rejects_broken_bundle_before_any_run_log(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plan_path = _graded_plan(tmp_path)

        def boom(*_a, **_k):
            raise AssertionError("run_step must not be reached")

        monkeypatch.setattr(run_cmd, "run_step", boom)
        rc = _cmd_run_sweep(
            _sweep_args(detail_grade="jira"),
            ctx=_ctx(tmp_path),
            plan_path=plan_path,
        )
        assert rc == 2
        assert "02-second-step.md" in capsys.readouterr().err
        assert not (tmp_path / ".plan-tool" / "runs").exists()

    def test_jira_grade_sweep_skips_run_grade_detail_warning(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # The run-grade warn/confirm helpers read ``Step.detail`` and
        # recommend authoring it — the wrong artifact at this grade.
        plan_path = _graded_plan(tmp_path)
        _write_jira_artifact(plan_path, 2, "second-step")
        _write_jira_artifact(plan_path, 3, "third-step")
        monkeypatch.setattr(run_cmd, "run_step", lambda *a, **k: _FakeRunResult())
        rc = _cmd_run_sweep(
            _sweep_args(detail_grade="jira", max_steps=1),
            ctx=_ctx(tmp_path),
            plan_path=plan_path,
        )
        assert rc == 0
        assert "has no detail file" not in capsys.readouterr().err


# --- ``run --accept``: certify a hand-fixed step with no backend call -------


def _accept_plan(
    repo: Path,
    *,
    test_command: str | None = "true",
    gate: list[str] | None = None,
    steps: int = 2,
    step1_status: str = "current",
    step1_scope: str | None = None,
    note: str | None = None,
) -> Path:
    """A committed plan whose step 1 failed its gate and was then hand-fixed."""
    lines = ["---", "title: Accept", "status: in-progress", "priority: low"]
    if test_command is not None:
        lines.append(f'test_command: "{test_command}"')
    lines += ["steps:", "  - id: 1", "    title: First", "    files:", "      - a.py"]
    if gate:
        lines.append("    gate:")
        lines += [f'      - "{c}"' for c in gate]
    if step1_scope:
        lines.append(f"    scope: {step1_scope}")
    lines.append(f"    status: {step1_status}")
    if note:
        lines.append(f"    status_note: {note}")
    if steps == 2:
        lines += [
            "  - id: 2", "    title: Second", "    files:", "      - b.py",
            "    depends_on:", "      - 1",
        ]
    lines += ["---", "", "# Accept", ""]
    path = repo / "accept.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    _commit_everything(repo)
    return path


def _commit_everything(repo: Path) -> None:
    for cmd in (["git", "add", "-A"], ["git", "commit", "-q", "-m", "fixture"]):
        subprocess.run(
            cmd, cwd=repo, stdin=subprocess.DEVNULL,
            capture_output=True, check=True,
        )


def _accept_args(**overrides) -> argparse.Namespace:
    return _sweep_args(**{"accept": True, "step": 1, **overrides})


class TestRunAccept:
    """``--accept`` certifies with the gates a backend run would have run and
    writes nothing unless all pass; it is never a second route past a red gate."""

    def test_green_gates_mark_done_clear_note_and_promote_next(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _init_git_repo(tmp_path)
        plan_path = _accept_plan(tmp_path, note="'test gate failed (rc=1)'")
        rc = run_cmd._cmd_run_accept(
            _accept_args(), ctx=_ctx(tmp_path), plan_path=plan_path
        )
        assert rc == 0
        plan = parse_plan(plan_path)
        assert plan.step_by_id(1).status.value == "done"
        assert plan.step_by_id(1).status_note is None
        assert plan.step_by_id(2).status.value == "current"
        assert "accepted — advanced to step 2" in capsys.readouterr().out

    def test_accepting_the_last_step_completes_the_plan(
        self, tmp_path: Path
    ) -> None:
        _init_git_repo(tmp_path)
        plan_path = _accept_plan(tmp_path, steps=1)
        assert run_cmd._cmd_run_accept(
            _accept_args(), ctx=_ctx(tmp_path), plan_path=plan_path
        ) == 0
        assert parse_plan(plan_path).status.value == "completed"

    @pytest.mark.parametrize(
        ("kwargs", "expected_rc"),
        [
            ({"test_command": "exit 3"}, 3),
            ({"test_command": "true", "gate": ["exit 4"]}, 4),
        ],
        ids=["red-suite", "red-step-gate"],
    )
    def test_a_red_gate_leaves_the_plan_byte_identical(
        self, tmp_path: Path, kwargs, expected_rc
    ) -> None:
        _init_git_repo(tmp_path)
        plan_path = _accept_plan(tmp_path, **kwargs)
        before = plan_path.read_bytes()
        rc = run_cmd._cmd_run_accept(
            _accept_args(), ctx=_ctx(tmp_path), plan_path=plan_path
        )
        # The gate's own rc, not a parse or refusal rc: the gate really ran.
        assert rc == expected_rc
        assert plan_path.read_bytes() == before

    def test_nothing_to_certify_with_is_refused(self, tmp_path: Path) -> None:
        """Deliberate: with no test_command and no step gate, --accept would
        flip a step on no evidence at all, so it refuses."""
        _init_git_repo(tmp_path)
        plan_path = _accept_plan(tmp_path, test_command=None)
        before = plan_path.read_bytes()
        rc = run_cmd._cmd_run_accept(
            _accept_args(), ctx=_ctx(tmp_path), plan_path=plan_path
        )
        assert rc == 2
        assert plan_path.read_bytes() == before

    def test_dirty_tree_is_refused_before_any_gate_runs(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _init_git_repo(tmp_path)
        marker = tmp_path / "gate-ran"
        plan_path = _accept_plan(tmp_path, test_command=f"touch {marker}")
        (tmp_path / "uncommitted.txt").write_text("x", encoding="utf-8")
        before = plan_path.read_bytes()
        rc = run_cmd._cmd_run_accept(
            _accept_args(), ctx=_ctx(tmp_path), plan_path=plan_path
        )
        assert rc == 2
        assert not marker.exists()
        assert plan_path.read_bytes() == before
        assert "requires a clean working tree" in capsys.readouterr().err

    @pytest.mark.parametrize(
        "kwargs", [{"step1_status": "done"}, {"step1_scope": "deferred"}],
        ids=["already-done", "not-committed"],
    )
    def test_a_done_or_non_committed_step_is_refused(
        self, tmp_path: Path, kwargs
    ) -> None:
        _init_git_repo(tmp_path)
        plan_path = _accept_plan(tmp_path, **kwargs)
        before = plan_path.read_bytes()
        assert run_cmd._cmd_run_accept(
            _accept_args(), ctx=_ctx(tmp_path), plan_path=plan_path
        ) == 2
        assert plan_path.read_bytes() == before

    @pytest.mark.parametrize(
        "overrides",
        [
            {"all": True}, {"reconcile": True}, {"dry_run": True},
            {"archive": True}, {"mode": "check"}, {"step": None},
            {"detail_grade": "jira"},
        ],
        ids=[
            "all", "reconcile", "dry-run", "archive", "review-mode", "no-step",
            "detail-grade",
        ],
    )
    def test_flag_combinations_that_imply_a_backend_call_are_refused(
        self, overrides
    ) -> None:
        """Validated by ``_accept_flag_error``, which ``cmd_run`` calls before
        the picker, so a bad combination never reaches a prompt or a run log."""
        args = _accept_args()
        for key, value in overrides.items():
            setattr(args, key, value)
        assert run_cmd._accept_flag_error(args) == 2

    def test_iterate_and_max_steps_are_tolerated_as_on_every_run(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Deliberate: scripts append ``--iterate`` uniformly and ``--max-steps``
        is documented as ignored without ``--all``; neither implies a backend
        call, so they are tolerated (``--iterate`` with a warning)."""
        assert run_cmd._accept_flag_error(_accept_args(max_steps=3)) is None
        assert run_cmd._accept_flag_error(_accept_args(iterate=True)) is None
        assert "--iterate has no effect with --accept" in capsys.readouterr().err

    def test_a_pending_step_with_a_failed_gate_note_is_accepted(
        self, tmp_path: Path
    ) -> None:
        """Deliberate: a step run out of order and failed on a gate stays
        ``pending`` with a ``status_note``; refusing it would leave a dead end,
        since a re-run hits the same gate. The note, not the status, separates
        it from a mistyped id."""
        _init_git_repo(tmp_path)
        plan_path = _accept_plan(
            tmp_path, step1_status="pending", note="'test gate failed (rc=1)'"
        )
        assert run_cmd._cmd_run_accept(
            _accept_args(), ctx=_ctx(tmp_path), plan_path=plan_path
        ) == 0
        assert parse_plan(plan_path).step_by_id(1).status.value == "done"

    def test_a_step_changed_while_the_gates_ran_is_refused_on_the_fresh_copy(
        self, tmp_path: Path
    ) -> None:
        """Deliberate: the preconditions are re-checked after the gates, so a
        step flipped to done mid-run is not certified on a stale snapshot."""
        _init_git_repo(tmp_path)
        (tmp_path / "flip.py").write_text(
            "from pathlib import Path\n"
            "p = Path('accept.md')\n"
            "t = p.read_text().replace('status: current', 'status: done', 1)\n"
            "p.write_text(t)\n",
            encoding="utf-8",
        )
        plan_path = _accept_plan(tmp_path, test_command="python3 flip.py")
        assert run_cmd._cmd_run_accept(
            _accept_args(), ctx=_ctx(tmp_path), plan_path=plan_path
        ) == 2

    def test_a_gitignored_lessons_file_does_not_fail_the_commit(
        self, tmp_path: Path
    ) -> None:
        """Deliberate: scoping ``git add`` to explicit paths must not turn an
        ignored lessons file into a hard failure."""
        _init_git_repo(tmp_path)
        (tmp_path / ".gitignore").write_text("docs/lessons.md\n", encoding="utf-8")
        plan_path = _accept_plan(tmp_path)
        text = plan_path.read_text(encoding="utf-8").replace(
            "priority: low\n", "priority: low\nlessons: docs/lessons.md\n", 1
        )
        plan_path.write_text(text, encoding="utf-8")
        _commit_everything(tmp_path)
        assert run_cmd._cmd_run_accept(
            _accept_args(commit=True), ctx=_ctx(tmp_path), plan_path=plan_path
        ) == 0
        assert not _working_tree_dirty(tmp_path)

    def test_commit_includes_a_tracked_lessons_file(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        plan_path = _accept_plan(tmp_path)
        text = plan_path.read_text(encoding="utf-8").replace(
            "priority: low\n", "priority: low\nlessons: docs/lessons.md\n", 1
        )
        plan_path.write_text(text, encoding="utf-8")
        _commit_everything(tmp_path)
        assert run_cmd._cmd_run_accept(
            _accept_args(commit=True), ctx=_ctx(tmp_path), plan_path=plan_path
        ) == 0
        tracked = subprocess.run(
            ["git", "ls-files"], cwd=tmp_path, capture_output=True,
            text=True, check=True,
        ).stdout.split()
        assert "docs/lessons.md" in tracked
        assert not _working_tree_dirty(tmp_path)

    def test_a_dirty_lessons_file_is_tolerated_by_the_precheck(
        self, tmp_path: Path
    ) -> None:
        """A sweep halt appends to the lessons log, so it is expected dirty."""
        _init_git_repo(tmp_path)
        plan_path = _accept_plan(tmp_path)
        text = plan_path.read_text(encoding="utf-8").replace(
            "priority: low\n", "priority: low\nlessons: docs/lessons.md\n", 1
        )
        plan_path.write_text(text, encoding="utf-8")
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "lessons.md").write_text("- seed\n", encoding="utf-8")
        _commit_everything(tmp_path)
        (tmp_path / "docs" / "lessons.md").write_text(
            "- seed\n- halt (sweep): step 1\n", encoding="utf-8"
        )
        assert run_cmd._cmd_run_accept(
            _accept_args(), ctx=_ctx(tmp_path), plan_path=plan_path
        ) == 0

    def test_a_persistence_failure_names_accept_not_a_backend_rerun(
        self, tmp_path: Path, monkeypatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Deliberate: the shared completion write's recovery hint must not
        send an operator to ``run --step N``, which spends a backend call and
        then trips the test-authoring gate."""
        _init_git_repo(tmp_path)
        plan_path = _accept_plan(tmp_path)

        def boom(*_a, **_k):
            raise OSError("disk full")

        monkeypatch.setattr(launcher, "write_plan", boom)
        rc = run_cmd._cmd_run_accept(
            _accept_args(), ctx=_ctx(tmp_path), plan_path=plan_path
        )
        err = capsys.readouterr().err
        assert rc == 1
        assert "--step 1 --accept" in err

    def test_a_valid_accept_passes_flag_validation(self) -> None:
        assert run_cmd._accept_flag_error(_accept_args()) is None
        assert run_cmd._accept_flag_error(_sweep_args()) is None  # no --accept

    def test_cmd_run_rejects_accept_without_step_before_any_prompt(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Deliberate: through the real entry point, ``--accept`` with no
        ``--step`` is refused before the plan picker and the all-or-next
        question, so the user is never asked for a scope they cannot give."""
        rc = run_cmd.cmd_run(_sweep_args(name=None, accept=True, step=None))
        assert rc == 2
        assert "--accept needs --step N" in capsys.readouterr().err

    def test_a_pending_step_is_refused_not_certified_by_an_unrelated_suite(
        self, tmp_path: Path
    ) -> None:
        """Deliberate: a mistyped step id must not go ``done`` on the strength
        of a green plan-wide suite; only the step a failed gate left current
        is certified."""
        _init_git_repo(tmp_path)
        plan_path = _accept_plan(tmp_path)
        before = plan_path.read_bytes()
        rc = run_cmd._cmd_run_accept(
            _accept_args(step=2), ctx=_ctx(tmp_path), plan_path=plan_path
        )
        assert rc == 2
        assert plan_path.read_bytes() == before

    def test_the_plan_file_dirtied_by_a_failed_gate_is_expected(
        self, tmp_path: Path
    ) -> None:
        """The tool itself writes ``status_note`` into the plan when a gate
        fails, so a plan-file-only change must not read as an unclean tree."""
        _init_git_repo(tmp_path)
        plan_path = _accept_plan(tmp_path)
        plan_path.write_text(
            plan_path.read_text(encoding="utf-8").replace(
                "    status: current\n",
                "    status: current\n    status_note: 'test gate failed (rc=1)'\n",
            ),
            encoding="utf-8",
        )
        assert run_cmd._cmd_run_accept(
            _accept_args(), ctx=_ctx(tmp_path), plan_path=plan_path
        ) == 0
        assert parse_plan(plan_path).step_by_id(1).status_note is None

    def test_an_unrelated_uncommitted_file_is_still_refused(
        self, tmp_path: Path
    ) -> None:
        _init_git_repo(tmp_path)
        plan_path = _accept_plan(tmp_path)
        (tmp_path / "hand-fix.py").write_text("x", encoding="utf-8")
        assert run_cmd._cmd_run_accept(
            _accept_args(), ctx=_ctx(tmp_path), plan_path=plan_path
        ) == 2

    def test_accept_appends_the_lessons_entry_a_run_would_have(
        self, tmp_path: Path
    ) -> None:
        """Deliberate: an accepted step is not left without a lessons-log
        entry, which the lessons-coverage check would report as missing."""
        _init_git_repo(tmp_path)
        plan_path = _accept_plan(tmp_path)
        text = plan_path.read_text(encoding="utf-8").replace(
            "priority: low\n", "priority: low\nlessons: docs/lessons.md\n", 1
        )
        plan_path.write_text(text, encoding="utf-8")
        _commit_everything(tmp_path)
        assert run_cmd._cmd_run_accept(
            _accept_args(), ctx=_ctx(tmp_path), plan_path=plan_path
        ) == 0
        lessons = (tmp_path / "docs" / "lessons.md").read_text(encoding="utf-8")
        assert "step 1: First" in lessons

    def test_an_edit_made_to_the_plan_during_the_gates_survives(
        self, tmp_path: Path
    ) -> None:
        """Deliberate: the gates run for minutes; the write-back re-reads the
        plan so a concurrent edit is not reverted by the pre-gate snapshot."""
        _init_git_repo(tmp_path)
        (tmp_path / "edit.py").write_text(
            "from pathlib import Path\n"
            "p = Path('accept.md')\n"
            "p.write_text(p.read_text().replace('priority: low', 'priority: high'))\n",
            encoding="utf-8",
        )
        plan_path = _accept_plan(tmp_path, test_command="python3 edit.py")
        assert run_cmd._cmd_run_accept(
            _accept_args(), ctx=_ctx(tmp_path), plan_path=plan_path
        ) == 0
        plan = parse_plan(plan_path)
        assert plan.priority.value == "high"  # the in-gate edit, not reverted
        assert plan.step_by_id(1).status.value == "done"

    def test_commit_flag_commits_only_the_plan_not_build_output(
        self, tmp_path: Path
    ) -> None:
        """Deliberate: the accept commit is the plan flip; an artifact the
        certifying suite wrote stays out of it."""
        _init_git_repo(tmp_path)
        plan_path = _accept_plan(tmp_path, test_command="touch coverage.out")
        assert run_cmd._cmd_run_accept(
            _accept_args(commit=True), ctx=_ctx(tmp_path), plan_path=plan_path
        ) == 0
        tracked = subprocess.run(
            ["git", "ls-files"], cwd=tmp_path, capture_output=True,
            text=True, check=True,
        ).stdout.split()
        assert "coverage.out" not in tracked
        assert (tmp_path / "coverage.out").exists()

    def test_commit_flag_commits_the_plan_edit_as_a_green_step(
        self, tmp_path: Path
    ) -> None:
        _init_git_repo(tmp_path)
        plan_path = _accept_plan(tmp_path)
        assert run_cmd._cmd_run_accept(
            _accept_args(commit=True), ctx=_ctx(tmp_path), plan_path=plan_path
        ) == 0
        subject = subprocess.run(
            ["git", "log", "-1", "--format=%s"], cwd=tmp_path,
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        assert "step 1 green" in subject
        assert not _working_tree_dirty(tmp_path)
