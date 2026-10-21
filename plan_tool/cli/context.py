"""Workspace + budget resolution helpers shared across CLI commands.

A leaf module: depends only on the standard library and the domain
modules ``plan_tool.convergence`` / ``plan_tool.create`` /
``plan_tool.locator`` (none of which import the ``plan_tool.cli``
package), so per-intent command modules can resolve context and budgets
without an import cycle through ``app.py``.
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from plan_tool.convergence import (
    DEFAULT_ITERATION_BUDGET_SECONDS,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_MAX_STALL_ROUNDS,
    IterativeBudget,
)
from plan_tool.create import CreateError
from plan_tool.locator import (
    PlanToolContext,
    build_plan_tool_context,
    find_repo_root_from_cwd,
    resolve_repo_root,
)


def _load_context(args: argparse.Namespace) -> PlanToolContext:
    return build_plan_tool_context(
        args.plans_dir,
        manifest_path=args.manifest,
        repo_root_override=args.repo_root,
    )


def _resolve_cmd_repo_root(args: argparse.Namespace) -> Path:
    """Resolve repo root for subcommands that take no plan name.

    Precedence matches ``--help``: ``--repo-root`` flag (highest) →
    ``PLAN_TOOL_REPO_ROOT`` env var → walk upward from cwd via
    :func:`find_repo_root_from_cwd` (which stops at a ``.git`` *or*
    ``.plan-tool`` ancestor). Delegates the first two to
    :func:`resolve_repo_root` so the env-var branch can't drift from
    :func:`_load_context` / :func:`build_plan_tool_context`.

    When the walk finds no marker (reaching the filesystem root), default to
    the current directory rather than erroring — so ``plan-tool`` stays
    usable in a fresh directory, and ``create`` can lay down a new
    ``.plan-tool/`` there.
    """
    override = getattr(args, "repo_root", None)
    explicit = resolve_repo_root(
        Path(override) if override is not None else None
    )
    if explicit is not None:
        return explicit
    try:
        return find_repo_root_from_cwd()
    except FileNotFoundError:
        return Path.cwd().resolve()


def _resolve_iterative_budget(args: argparse.Namespace) -> IterativeBudget:
    """Translate ``--iterate``/``--max-iterations``/``--iteration-budget`` into a budget.

    Centralizes validation so ``cmd_create`` / ``cmd_detail`` / ``cmd_run`` all get
    the same negative-value and zero-rejection rules. Raises ``CreateError``
    with a friendly message instead of letting argparse surface a
    ``SystemExit(2)`` — the handlers catch ``CreateError`` and exit 1
    (``cmd_create``) or 2 (``cmd_detail`` / ``cmd_run``).
    """
    enabled = bool(getattr(args, "iterate", False))
    max_iterations = int(
        getattr(args, "max_iterations", DEFAULT_MAX_ITERATIONS)
    )
    budget_seconds = int(
        getattr(args, "iteration_budget", DEFAULT_ITERATION_BUDGET_SECONDS)
    )
    max_stall_rounds = int(
        getattr(args, "max_stall_rounds", DEFAULT_MAX_STALL_ROUNDS)
    )
    hard_budget_seconds = _resolve_time_budget_seconds(args)
    if max_iterations < 1:
        raise CreateError(
            f"--max-iterations must be >= 1 (got {max_iterations})"
        )
    if budget_seconds < 1:
        raise CreateError(
            f"--iteration-budget must be >= 1 second (got {budget_seconds})"
        )
    if max_stall_rounds < 0:
        raise CreateError(
            f"--max-stall-rounds must be >= 0 (got {max_stall_rounds})"
        )
    # Stamp the op-level wall-clock anchor ONCE, here at command entry (before
    # the round-0 authoring claude pass), so the hard cap measures total op
    # elapsed — including that first pass and every step — not just a loop's
    # own elapsed. Only when the cap is active, so the off path reads no clock.
    op_started_at = time.monotonic() if hard_budget_seconds > 0 else None
    return IterativeBudget(
        enabled=enabled,
        max_iterations=max_iterations,
        budget_seconds=budget_seconds,
        max_stall_rounds=max_stall_rounds,
        hard_budget_seconds=hard_budget_seconds,
        op_started_at=op_started_at,
    )


def _resolve_time_budget_seconds(args: argparse.Namespace) -> int:
    """Resolve the cooperative wall-clock cap (#123): ``--time-budget`` flag
    → ``PLAN_TOOL_TIME_BUDGET`` env → ``0`` (off).

    ``0`` disables the cap; the loop then consults no hard-deadline clock.
    An unparseable/negative flag or env value raises ``CreateError`` so a
    typo surfaces instead of silently disabling the backstop.
    """
    flag = getattr(args, "time_budget", None)
    if flag is not None:
        seconds = int(flag)
        if seconds < 0:
            raise CreateError(
                f"--time-budget must be >= 0 seconds (got {seconds})"
            )
        return seconds
    raw = os.environ.get("PLAN_TOOL_TIME_BUDGET")
    if raw is None or raw.strip() == "":
        return 0
    try:
        seconds = int(raw.strip())
    except ValueError:
        raise CreateError(
            f"PLAN_TOOL_TIME_BUDGET must be an integer number of seconds "
            f"(got {raw!r})"
        )
    if seconds < 0:
        raise CreateError(
            f"PLAN_TOOL_TIME_BUDGET must be >= 0 seconds (got {seconds})"
        )
    return seconds


def _build_run_budget(args: argparse.Namespace) -> IterativeBudget:
    """Return the ``IterativeBudget`` ``cmd_run`` should hand to the
    post-reconcile iteration loop.

    Reads ``--iterate`` / ``--max-iterations`` / ``--iteration-budget``
    from ``args`` via :func:`_resolve_iterative_budget`, the shared
    helper used by ``cmd_create`` and ``cmd_detail``. Validation
    errors (``--max-iterations 0`` etc.) are caught at the top of
    ``cmd_run`` before this is called, so a ``CreateError`` raised
    here would be a programmer error rather than user input — it
    surfaces as an uncaught exception. Tests reach the iteration
    loop by patching this function.
    """
    return _resolve_iterative_budget(args)
