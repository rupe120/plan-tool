from __future__ import annotations

from argparse import Namespace
from json import dumps
from pathlib import Path

import pytest

from plan_tool.cli import authoring, roadmap_cmd, run_cmd
from plan_tool.cli.app import _requires_repo_mutation_lock, main
from plan_tool.repo_lock import mutation_lock_path, repo_mutation_lock


def test_reconcile_mutating_aliases_require_repo_lock() -> None:
    for command in (
        "reconcile-plan",
        "reconcile",
        "review",
        "reconcile-plan-walk",
        "reconcile-walk",
        "review-walk",
    ):
        assert _requires_repo_mutation_lock(Namespace(command=command))


def test_read_only_aliases_do_not_require_repo_lock() -> None:
    for command in ("verify-all", "reconcile-all", "review-all", "verify"):
        assert not _requires_repo_mutation_lock(Namespace(command=command))


def test_scope_review_requires_repo_lock() -> None:
    assert _requires_repo_mutation_lock(Namespace(command="scope-review"))


@pytest.fixture
def checkouts(tmp_path, monkeypatch):
    checkout, target = (tmp_path.resolve() / name for name in ("cwd", "target"))
    for root in (checkout, target):
        (root / ".git").mkdir(parents=True)
    monkeypatch.chdir(checkout)
    for key in ("PLAN_TOOL_REPO_ROOT", "PLAN_TOOL_PLANS_DIR", "PLAN_TOOL_BACKEND"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(run_cmd, "_stdin_is_tty", lambda: False)
    return checkout, target


@pytest.mark.parametrize("selector", ["flag", "env", "pinned", "manifest", "cwd"])
def test_run_holds_locks_for_the_checkouts_it_resolves(
    checkouts, monkeypatch, capsys, selector,
):
    checkout, target = checkouts
    plans_dir = target / "docs" / "implementation-plans"
    plans_dir.mkdir(parents=True)
    options = ["--plans-dir", str(plans_dir)]
    expected_roots = {target}
    handler_root = target
    if selector == "env":
        monkeypatch.setenv("PLAN_TOOL_PLANS_DIR", str(plans_dir))
        options = []
    elif selector == "pinned":
        options += ["--repo-root", str(checkout)]
        expected_roots.add(checkout)
        handler_root = checkout
    elif selector == "manifest":
        # Run from a nested checkout with no plans. Its parent's manifest
        # wins because it resolves an entry.
        nested = target / "nested"
        (nested / ".git").mkdir(parents=True)
        monkeypatch.chdir(nested)
        checkout = nested
        plan = plans_dir / "existing.md"
        plan.write_text("A manifest candidate", encoding="utf-8")
        manifest = target / ".plan-tool" / "plans.json"
        manifest.parent.mkdir()
        manifest.write_text(
            dumps({"plans": [str(plan.relative_to(target))]}), encoding="utf-8",
        )
        options = []
    elif selector == "cwd":
        options = []
        expected_roots = {checkout}
        handler_root = checkout

    observed = []

    def load_prefs(root: Path) -> dict:
        observed.append(root)
        assert {
            candidate
            for candidate in (checkout, target)
            if mutation_lock_path(candidate).exists()
        } == expected_roots
        return {}

    monkeypatch.setattr(run_cmd, "_load_run_prefs", load_prefs)
    assert main([*options, "run", "missing"]) == 2
    assert "no plan matching" in capsys.readouterr().err
    assert observed == [handler_root]
    assert all(not mutation_lock_path(root).exists() for root in expected_roots)


def test_run_rejects_busy_destination_before_reaching_the_plan(
    checkouts, monkeypatch, capsys,
):
    checkout, target = checkouts
    plans_dir = target / "plans"
    plans_dir.mkdir()

    def unexpected_prefs(root: Path) -> dict:
        pytest.fail(f"run reached plan lookup while {root} was locked")

    monkeypatch.setattr(run_cmd, "_load_run_prefs", unexpected_prefs)
    argv = ["--repo-root", str(checkout), "--plans-dir", str(plans_dir), "run", "missing"]
    with repo_mutation_lock(target, command="detail"):
        assert main(argv) == 2
        assert "another mutating plan-tool command is active" in capsys.readouterr().err
        assert mutation_lock_path(target).is_file()
        assert not mutation_lock_path(checkout).exists()


def test_fresh_create_locks_the_seed_selected_checkout(
    checkouts, monkeypatch, capsys,
):
    checkout, target = checkouts
    monkeypatch.setattr(authoring, "find_umbrella_root", lambda *a, **kw: target)

    def unexpected_collision_gate(*args, **kwargs):
        pytest.fail("create reached the branch-changing gate while the target was locked")

    monkeypatch.setattr(authoring, "_create_branch_collision_gate", unexpected_collision_gate)
    with repo_mutation_lock(target, command="detail"):
        assert main(["create", "demo", "--from", "Update `src/feature.py`.", "-y"]) == 2
        assert "another mutating plan-tool command is active" in capsys.readouterr().err
        assert not mutation_lock_path(checkout).exists()


def test_roadmap_locks_its_external_plans_checkout(
    checkouts, monkeypatch, capsys,
):
    checkout, target = checkouts
    plans_dir = target / "plans"
    plans_dir.mkdir()

    def unexpected_roadmap_apply(*args, **kwargs):
        pytest.fail("roadmap reached apply while the target was locked")

    monkeypatch.setattr(roadmap_cmd, "_cmd_roadmap_apply", unexpected_roadmap_apply)
    with repo_mutation_lock(target, command="detail"):
        assert main(["--plans-dir", str(plans_dir), "roadmap", "demo", "--apply"]) == 2
        assert "another mutating plan-tool command is active" in capsys.readouterr().err
        assert not mutation_lock_path(checkout).exists()
