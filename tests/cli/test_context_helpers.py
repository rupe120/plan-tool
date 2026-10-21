"""Characterization tests for the workspace-resolution helpers.

These pin how ``plan_tool.cli`` turns parsed global flags + environment
into a resolved workspace, across the three resolution modes:

* ``--plans-dir`` (directory mode),
* a manifest with a pinned ``--repo-root``,
* a manifest with the repo root coming from ``PLAN_TOOL_REPO_ROOT`` or a
  walk-up from cwd.

and how ``--iterate`` / ``--max-iterations`` / ``--iteration-budget`` /
``--max-stall-rounds`` fold into an :class:`IterativeBudget`. They are
written against the monolith so the package split can move the helpers
without changing resolution precedence.

Scope is set by ``tests/cli/COVERAGE_BASELINE.md``: direct tests are added
only for helpers it marks as lacking direct coverage. ``_build_run_budget``
is already directly covered (``test_cli.py`` passes a pass-through spy and
asserts its real ``IterativeBudget``), so it keeps that baseline pointer
instead of a duplicate here — and since it merely delegates to
``_resolve_iterative_budget``, the validation tests below cover its logic.

Split-proof conventions (see ``test_package_surface.py``): the helpers are
imported from ``plan_tool.cli`` and driven through real namespaces built by
the public ``build_parser()`` (or a plain ``argparse.Namespace`` for the
getattr-defaulted budget helper); no ``plan_tool.cli`` module global is
``monkeypatch.setattr``\\ed. Environment branches are driven via real env
vars (``monkeypatch.setenv``), which the helpers read through the domain
``plan_tool.locator`` resolvers — not through any cli-module global. The
``tmp_repo`` / ``registered_plan`` fixtures come from ``conftest.py``.
"""

from __future__ import annotations

import argparse

import pytest

from plan_tool.cli import (
    _load_context,
    _resolve_cmd_repo_root,
    _resolve_iterative_budget,
    build_parser,
)
from plan_tool.convergence import (
    DEFAULT_ITERATION_BUDGET_SECONDS,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_MAX_STALL_ROUNDS,
)
from plan_tool.create import CreateError


def _parse(*argv: str) -> argparse.Namespace:
    """Parse global flags + a subcommand into a real namespace."""
    return build_parser().parse_args(list(argv))


class TestLoadContext:
    def test_manifest_mode_with_pinned_repo_root(self, registered_plan) -> None:
        repo = registered_plan
        ctx = _load_context(_parse(*repo.argv("list")))
        assert ctx.plans_dir is None  # manifest mode never sets a plans dir
        assert ctx.repo_root == repo.root.resolve()
        assert [p.path.name for p in ctx.entries] == ["1-demo.md"]

    def test_plans_dir_mode_scans_the_directory(self, registered_plan) -> None:
        repo = registered_plan
        ctx = _load_context(_parse("--plans-dir", str(repo.plans_dir), "list"))
        assert ctx.plans_dir == repo.plans_dir.resolve()
        assert [p.path.name for p in ctx.entries] == ["1-demo.md"]

    def test_repo_root_from_env_var(
        self, registered_plan, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo = registered_plan
        monkeypatch.setenv("PLAN_TOOL_REPO_ROOT", str(repo.root))
        # No --repo-root flag: the env var is the only repo-root source.
        ctx = _load_context(_parse("--manifest", str(repo.manifest_path), "list"))
        assert ctx.plans_dir is None
        assert ctx.repo_root == repo.root.resolve()
        assert [p.path.name for p in ctx.entries] == ["1-demo.md"]


class TestResolveCmdRepoRoot:
    def test_flag_takes_precedence(self, tmp_repo) -> None:
        args = _parse(*tmp_repo.argv("list"))
        assert _resolve_cmd_repo_root(args) == tmp_repo.root.resolve()

    def test_env_var_when_no_flag(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_REPO_ROOT", str(tmp_repo.root))
        args = _parse("--manifest", str(tmp_repo.manifest_path), "list")
        assert _resolve_cmd_repo_root(args) == tmp_repo.root.resolve()

    def test_walks_up_from_cwd_when_unset(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No flag, no env var: fall back to the nearest .git above cwd.
        monkeypatch.chdir(tmp_repo.root)
        assert _resolve_cmd_repo_root(_parse("list")) == tmp_repo.root.resolve()


class TestResolveIterativeBudget:
    def test_defaults_when_iterate_absent(self) -> None:
        budget = _resolve_iterative_budget(argparse.Namespace())
        assert budget.enabled is False
        assert budget.max_iterations == DEFAULT_MAX_ITERATIONS
        assert budget.budget_seconds == DEFAULT_ITERATION_BUDGET_SECONDS
        assert budget.max_stall_rounds == DEFAULT_MAX_STALL_ROUNDS

    def test_explicit_values_are_carried_through(self) -> None:
        args = argparse.Namespace(
            iterate=True,
            max_iterations=5,
            iteration_budget=120,
            max_stall_rounds=0,
        )
        budget = _resolve_iterative_budget(args)
        assert budget.enabled is True
        assert budget.max_iterations == 5
        assert budget.budget_seconds == 120
        assert budget.max_stall_rounds == 0

    def test_zero_max_iterations_rejected(self) -> None:
        with pytest.raises(CreateError, match="--max-iterations must be >= 1"):
            _resolve_iterative_budget(argparse.Namespace(max_iterations=0))

    def test_zero_iteration_budget_rejected(self) -> None:
        with pytest.raises(
            CreateError, match="--iteration-budget must be >= 1 second"
        ):
            _resolve_iterative_budget(argparse.Namespace(iteration_budget=0))

    def test_negative_max_stall_rounds_rejected(self) -> None:
        with pytest.raises(CreateError, match="--max-stall-rounds must be >= 0"):
            _resolve_iterative_budget(argparse.Namespace(max_stall_rounds=-1))

    # ---- cooperative time-budget (#123): flag > env > off ----

    def test_time_budget_defaults_off(self, monkeypatch) -> None:
        monkeypatch.delenv("PLAN_TOOL_TIME_BUDGET", raising=False)
        budget = _resolve_iterative_budget(argparse.Namespace())
        assert budget.hard_budget_seconds == 0
        # No cap -> no op anchor stamped (the off path reads no clock).
        assert budget.op_started_at is None

    def test_time_budget_flag_carried_through(self, monkeypatch) -> None:
        monkeypatch.delenv("PLAN_TOOL_TIME_BUDGET", raising=False)
        budget = _resolve_iterative_budget(
            argparse.Namespace(time_budget=300)
        )
        assert budget.hard_budget_seconds == 300
        # Cap active -> the op-level wall-clock anchor is stamped now.
        assert budget.op_started_at is not None

    def test_time_budget_env_when_no_flag(self, monkeypatch) -> None:
        monkeypatch.setenv("PLAN_TOOL_TIME_BUDGET", "240")
        budget = _resolve_iterative_budget(argparse.Namespace())
        assert budget.hard_budget_seconds == 240

    def test_time_budget_flag_overrides_env(self, monkeypatch) -> None:
        monkeypatch.setenv("PLAN_TOOL_TIME_BUDGET", "240")
        budget = _resolve_iterative_budget(
            argparse.Namespace(time_budget=300)
        )
        assert budget.hard_budget_seconds == 300

    def test_time_budget_empty_env_is_off(self, monkeypatch) -> None:
        monkeypatch.setenv("PLAN_TOOL_TIME_BUDGET", "  ")
        budget = _resolve_iterative_budget(argparse.Namespace())
        assert budget.hard_budget_seconds == 0

    def test_time_budget_zero_is_allowed(self, monkeypatch) -> None:
        monkeypatch.delenv("PLAN_TOOL_TIME_BUDGET", raising=False)
        budget = _resolve_iterative_budget(
            argparse.Namespace(time_budget=0)
        )
        assert budget.hard_budget_seconds == 0

    def test_negative_time_budget_flag_rejected(self, monkeypatch) -> None:
        monkeypatch.delenv("PLAN_TOOL_TIME_BUDGET", raising=False)
        with pytest.raises(CreateError, match="--time-budget must be >= 0"):
            _resolve_iterative_budget(argparse.Namespace(time_budget=-1))

    def test_invalid_env_time_budget_rejected(self, monkeypatch) -> None:
        monkeypatch.setenv("PLAN_TOOL_TIME_BUDGET", "soon")
        with pytest.raises(CreateError, match="PLAN_TOOL_TIME_BUDGET must be"):
            _resolve_iterative_budget(argparse.Namespace())

    def test_negative_env_time_budget_rejected(self, monkeypatch) -> None:
        monkeypatch.setenv("PLAN_TOOL_TIME_BUDGET", "-5")
        with pytest.raises(CreateError, match="PLAN_TOOL_TIME_BUDGET must be >= 0"):
            _resolve_iterative_budget(argparse.Namespace())
