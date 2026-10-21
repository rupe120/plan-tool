"""Scope-out command module — the ``scope-out`` carve verb.

``plan-tool scope-out <name> --step N [--apply] [-y]`` actuates the scope-out
structural remedy by calling the deterministic
:func:`plan_tool.scope_out.scope_out_step`: it carves one over-packed step out
of a plan into a ``create --from-existing`` forward-seed and narrows the plan.
It spends **no Claude** (both halves are deterministic) and mutates the plan
only under ``--apply`` plus an interactive confirm or the second opt-in
``-y/--yes``; the default no-``--apply`` path recommends only. Modeled on the
sibling :mod:`plan_tool.cli.convergence_cmd`; like every per-intent command
module it imports only the cycle-free leaves (:mod:`plan_tool.cli.context`,
:mod:`plan_tool.cli.parser`) and domain modules — never :mod:`plan_tool.cli.app`.
"""

from __future__ import annotations

import argparse
import sys

from plan_tool.cli.context import _load_context
from plan_tool.cli.parser import Handler
from plan_tool.locator import resolve_plan_for_context, slug_from_filename
from plan_tool.scope_out import (
    ScopeOutResult,
    _carve_target_label,
    scope_out_step,
)
from plan_tool.style import info, success, warn


def cmd_scope_out(args: argparse.Namespace) -> int:
    """Carve an over-packed step (or a contiguous ``--step N --through M`` region)
    out of a plan into a ``create --from-existing`` seed.

    Resolves the plan, expands ``N..M`` into the carved id set (``--step`` alone
    is the single-step path), calls the deterministic
    :func:`plan_tool.scope_out.scope_out_step` with the apply/confirm gate, and
    renders one branch per ``ScopeOutResult.outcome``. Returns 0 for every
    outcome — per the exit-code convention a completed carve or a deliberate
    refusal/recommendation is not a failure-to-complete. An out-of-order range
    is a **usage** error (rc 2, argparse's convention); an unresolvable ``name``
    still surfaces a non-zero error from name resolution upstream.
    """
    ctx = _load_context(args)
    path = resolve_plan_for_context(ctx, args.name)
    plan_slug = slug_from_filename(path) or args.name

    is_range = args.through is not None and args.through > args.step
    if args.through is None:
        carved_ids = [args.step]
    elif args.through < args.step:
        # Out-of-order range never reaches scope_out_step: it is a usage error,
        # not a ScopeOutResult outcome. Mutates nothing.
        print(
            f"error: --through {args.through} is before --step {args.step}; a "
            "range must be ordered (N..M with M >= N).",
            file=sys.stderr,
        )
        return 2
    else:
        carved_ids = list(range(args.step, args.through + 1))

    result = scope_out_step(
        path,
        carved_ids=carved_ids,
        repo_root=ctx.repo_root,
        allow_scope_out=args.apply,
        yes=args.yes,
    )

    hint_target = (
        f"--step {args.step} --through {args.through}"
        if is_range
        else f"--step {result.carved_id}"
    )
    render_scope_out_result(
        result,
        plan_slug=plan_slug,
        name=args.name,
        recommend_hint=(
            "To actuate it interactively:\n"
            f"  plan-tool scope-out {args.name} {hint_target} --apply\n"
            "Add -y for the deliberate non-interactive apply path "
            "(--apply -y mutates without a TTY confirm)."
        ),
    )
    return 0


def render_scope_out_result(
    result: ScopeOutResult,
    *,
    plan_slug: str,
    name: str,
    recommend_hint: str,
) -> None:
    """Render one line per :attr:`ScopeOutResult.outcome`.

    ``recommend_hint`` is the "to actuate" guidance for the recommend-only
    outcome. A multi-id carve renders a ``steps N..M`` label; a single id
    keeps the ``step N`` message.
    """
    label = _carve_target_label(result.carved_ids or [result.carved_id])
    if result.outcome == "applied":
        renumber = ", ".join(
            f"{old}->{new}" for old, new in result.narrow.renumber
        ) or "no survivors renumbered"
        cursor = (
            f"new CURRENT step {result.narrow.new_current_id}"
            if result.narrow.new_current_id is not None
            else "no CURRENT step promoted"
        )
        success(
            f"carved {label} out of {plan_slug}: wrote seed "
            f"{result.seed_path} and narrowed the plan ({renumber}; {cursor})."
        )
        if result.body_sweep_hits:
            warn(
                f"plan body still references carved or renumbered work "
                f"({len(result.body_sweep_hits)} hit(s)) — sweep the prose "
                f"(identifiers, then vocabulary); auto-rewrite is out of scope:"
            )
            for hit in result.body_sweep_hits:
                warn(f"  L{hit.line_no} [{hit.kind}] {hit.detail}: {hit.line}")
    elif result.outcome == "recommended":
        info(
            f"{label} of {plan_slug} is safe to carve, but "
            f"nothing was written (recommend-only). {recommend_hint}"
        )
    elif result.outcome == "unsafe":
        warn(
            f"refusing to carve {label} out of {plan_slug} — "
            "the plan graph blocks it:"
        )
        for blocker in result.blockers:
            warn(f"  [{blocker.kind}] {blocker.message}")
        warn(
            "To restructure anyway, re-seed and re-decompose the whole plan "
            "(annotate can forward-seed it):\n"
            f"  plan-tool create {plan_slug} --from-existing <seed.md> --iterate"
        )
    elif result.outcome == "empty-plan":
        warn(
            f"refusing to carve {label} out of {plan_slug} — "
            "it is the last committed step, so the narrowed plan would be "
            "permanently dead. Re-seed and re-decompose the whole plan instead "
            "(annotate can forward-seed it):\n"
            f"  plan-tool create {plan_slug} --from-existing <seed.md> --iterate"
        )
    else:  # step-missing
        warn(
            f"refusing to carve {label} out of {plan_slug} — "
            "no step with that id is in the plan. Check `plan-tool status "
            f"{name}` for the valid step ids."
        )


def register(subparsers) -> dict[str, Handler]:
    """Add the ``scope-out`` subparser and return its handler map."""
    # Deliberately NOT parser.make_yes_parent(): with --apply this is a
    # second opt-in that bypasses the TTY confirm in scope_out_step and may
    # mutate unattended, and the help text has to say so.
    yes_parent = argparse.ArgumentParser(add_help=False)
    yes_parent.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help=(
            "skip the interactive carve confirmation (relevant only with "
            "--apply): the deliberate second opt-in that may mutate a plan "
            "without a TTY. Useful for scripted/unattended runs."
        ),
    )
    p = subparsers.add_parser(
        "scope-out",
        help=(
            "carve an over-packed step out of a plan into a create --from-existing "
            "seed (recommend-only; --apply to mutate)"
        ),
        parents=[yes_parent],
    )
    p.add_argument(
        "name",
        help="plan name — slug, filename stem (e.g. 1-my-feature), or filename.md",
    )
    p.add_argument(
        "--step",
        type=int,
        required=True,
        help="step id to carve out of the plan (N; the region start with --through)",
    )
    p.add_argument(
        "--through",
        type=int,
        default=None,
        metavar="M",
        help=(
            "carve the inclusive N..M region (from --step N) in one carve, "
            "writing one forward-seed for the whole region; omit for a "
            "single-step carve. M must be >= N."
        ),
    )
    p.add_argument(
        "--apply",
        action="store_true",
        help=(
            "opt in to mutating the plan: write the forward-seed and narrow "
            "the plan (default: recommend only). Requires an interactive "
            "confirm unless paired with -y/--yes."
        ),
    )
    return {"scope-out": cmd_scope_out}
