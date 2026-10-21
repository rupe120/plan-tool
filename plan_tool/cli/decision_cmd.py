"""Explicit decomposition-decision recorder command."""

from __future__ import annotations

import argparse

from plan_tool.cli.context import _load_context
from plan_tool.cli.parser import Handler
from plan_tool.locator import resolve_plan_for_context, slug_from_filename
from plan_tool.parser import parse_plan
from plan_tool.review_persistence import compute_plan_fingerprint
from plan_tool.style import error
from plan_tool.telemetry import (
    DECOMPOSITION_OUTCOMES,
    decomposition_anchor_step_id,
    record_decomposition_decision,
)


def cmd_decide(args: argparse.Namespace) -> int:
    """Persist one explicit plan or step decomposition decision."""
    rationale = args.rationale.strip()
    if not rationale:
        error("--rationale must be non-empty")
        return 2

    ctx = _load_context(args)
    path = resolve_plan_for_context(ctx, args.name)
    plan = parse_plan(path)
    anchor = args.anchor
    step_id = decomposition_anchor_step_id(anchor)
    if anchor != "plan" and step_id is None:
        error("--anchor must be 'plan' or 'step:<existing step id>'")
        return 2
    if step_id is not None and int(step_id) not in {step.id for step in plan.steps}:
        error(f"--anchor {anchor!r} does not name a step in plan {plan.title!r}")
        return 2

    plan_slug = slug_from_filename(path)
    assert plan_slug is not None
    if not record_decomposition_decision(
        ctx.repo_root,
        plan_slug=plan_slug,
        outcome=args.outcome,
        anchor=anchor,
        rationale=rationale,
        plan_fingerprint=compute_plan_fingerprint(path),
    ):
        error("could not persist decomposition decision; no decision was recorded")
        return 1

    print(f"Recorded {args.outcome} decision for {plan_slug} at {anchor}.")
    return 0


def register(subparsers) -> dict[str, Handler]:
    """Add the ``decide`` subparser and return its handler map."""
    parser = subparsers.add_parser(
        "decide",
        help="record an explicit plan decomposition decision",
    )
    parser.add_argument(
        "name",
        help="plan name — slug, filename stem, or filename.md",
    )
    parser.add_argument(
        "--outcome",
        required=True,
        choices=DECOMPOSITION_OUTCOMES,
        help="the explicit decomposition outcome to record",
    )
    parser.add_argument(
        "--anchor",
        required=True,
        help="decision target: plan or step:<existing step id>",
    )
    parser.add_argument(
        "--rationale",
        required=True,
        help="non-empty reason for the explicit decision",
    )
    return {"decide": cmd_decide}
