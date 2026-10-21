"""Split-criteria command module — the read-only ``split-criteria`` verb.

``plan-tool split-criteria [<plan>]`` visualizes the structural-split axis the
tool already applies. With **no plan** it prints the plan-independent legend
(:func:`plan_tool.split_criteria.render_split_criteria`); with a **plan name**
it resolves that plan and prints the per-plan breakdown of which split criteria
fire and why (:func:`plan_tool.split_criteria.evaluate_split_criteria` plus its
renderer). It spends no Claude, mutates nothing, writes no run-log entry, and
**criterion outcomes exit 0** — a pure "tell me the state" diagnostic, like
the sibling :mod:`plan_tool.cli.convergence_cmd`. Input-resolution, parsing,
and unsupported-detail-format errors remain command failures.

One deliberate divergence from ``cmd_convergence``: the handler records **no**
telemetry itself. ``evaluate_split_criteria`` already writes the
``plan-criteria-breakdown`` event as part of evaluating (a read → diff → record
cycle), so a second write here would double-count; legend mode has no per-plan
run to log at all. Like every per-intent command module it imports only the
cycle-free leaves (:mod:`plan_tool.cli.context`, :mod:`plan_tool.cli.parser`)
and domain modules — never :mod:`plan_tool.cli.app`.
"""

from __future__ import annotations

import argparse
import sys

from plan_tool import style
from plan_tool.cli.context import _load_context
from plan_tool.cli.parser import Handler
from plan_tool.locator import resolve_plan_for_context
from plan_tool.parser import parse_plan
from plan_tool.split_criteria import (
    evaluate_split_criteria,
    render_plan_breakdown,
    render_split_criteria,
)


def cmd_split_criteria(args: argparse.Namespace) -> int:
    """Print the split-criteria legend, or one plan's per-criterion breakdown.

    With no ``name`` the legend is plan-independent, so no plan/context is
    resolved. With a ``name`` the plan path is resolved, parsed, and evaluated
    against every deterministically-evaluable split criterion. Read-only: no
    Claude call, no mutation, no run-log entry, and it records no telemetry —
    ``evaluate_split_criteria`` owns the ``plan-criteria-breakdown`` write.
    Returns 0 for both modes, including when criteria fire. An unresolvable
    ``name`` still surfaces a non-zero error from name resolution upstream.
    """
    color = style.color_enabled(sys.stdout)
    if args.name is None:
        # Legend mode: plan-independent, so never touch plan resolution.
        print(render_split_criteria(color=color))
        return 0
    ctx = _load_context(args)
    path = resolve_plan_for_context(ctx, args.name)
    plan = parse_plan(path)
    breakdown = evaluate_split_criteria(plan, plan_path=path, repo_root=ctx.repo_root)
    print(render_plan_breakdown(breakdown, color=color))
    return 0


def register(subparsers) -> dict[str, Handler]:
    """Add the ``split-criteria`` subparser and return its handler map.

    The single ``name`` positional is optional (``nargs="?"``): present →
    per-plan breakdown, absent → the plan-independent legend. No ``-y`` parent —
    a read-only diagnostic has no confirm prompt to auto-accept.
    """
    p = subparsers.add_parser(
        "split-criteria",
        help=(
            "show the split-criteria legend, or (with a plan) why that plan is "
            "shaped the way it is (read-only; no claude; criteria exit 0)"
        ),
    )
    p.add_argument(
        "name",
        nargs="?",
        default=None,
        help=(
            "plan name — slug, filename stem (e.g. 1-my-feature), or "
            "filename.md; omit for the plan-independent legend"
        ),
    )
    return {"split-criteria": cmd_split_criteria}
