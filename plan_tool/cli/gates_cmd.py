"""Gate-suggestion command module — the ``suggest-gates`` verb.

``plan-tool suggest-gates <slug>`` reads a plan's already-built (``done``)
steps and their details, asks the active backend to propose ``gate:`` shell
commands that protect those invariants, and — after the operator confirms each
one — writes them onto the remaining not-done steps' frontmatter. Grounded in
real, already-built artifacts (``create`` does not propose gates); the engine
lives in :mod:`plan_tool.gates`.

``--all-steps`` relaxes the done-steps precondition: on a plan with no built
steps yet it proposes *speculative* gates from every not-done step's detail
instead.

Like every per-intent command module this imports only the cycle-free leaves
(:mod:`plan_tool.cli.context`, :mod:`plan_tool.cli.parser`) and domain
packages — never :mod:`plan_tool.cli.app`. ``cmd_suggest_gates`` exposes
``invoker`` / ``input_fn`` keyword seams (defaulted) so tests never shell out
or block on stdin; dispatch calls it with the ``Namespace`` alone.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from typing import Optional

from plan_tool.cli.context import _load_context
from plan_tool.cli.parser import Handler
from plan_tool.create import shell_claude_invoker
from plan_tool.gates import (
    GateInvoker,
    GateSuggestion,
    apply_gate_suggestions,
    built_steps,
    remaining_steps,
    suggest_gates,
)
from plan_tool.locator import resolve_plan_for_context, slug_from_filename
from plan_tool.parser import parse_plan, write_plan
from plan_tool.run_log import RunLogWriter
from plan_tool.style import tool


def _ask_suggestion(
    input_fn,
    *,
    suggestion: GateSuggestion,
    valid_targets: dict[int, str],
) -> Optional[GateSuggestion]:
    """Prompt the operator to keep / edit / move / drop one suggested gate.

    Returns the resolved :class:`GateSuggestion` (``(k)eep`` / Enter, the typed
    replacement on ``(e)dit``, or a re-targeted copy after ``(m)ove``) or
    ``None`` to drop it. Enter defaults to *keep*: the model already judged the
    gate fit, but a command is never written without passing through this
    confirm. ``valid_targets`` maps every remaining step id to its title — the
    only ids ``(m)ove`` will accept.
    """
    current = suggestion
    while True:
        protects = current.protects_id
        head = f"  protect step {protects} → " if protects is not None else "  "
        title = valid_targets.get(current.target_id, "?")
        print(f"{head}gate on step {current.target_id} ({title}):")
        print(f"    {current.command}")
        if current.rationale:
            print(f"    rationale: {current.rationale}")
        raw = input_fn("    (k)eep / (e)dit / (m)ove / (d)rop [keep]: ").strip().lower()
        if raw in ("", "k"):
            return current
        if raw == "d":
            return None
        if raw == "e":
            edited = input_fn("    command> ")
            # A blank replacement is a drop (an empty gate would fail the
            # schema's non-empty validator anyway).
            return replace(current, command=edited) if edited.strip() else None
        if raw == "m":
            ans = input_fn("    move to step id: ").strip()
            try:
                new_target = int(ans)
            except ValueError:
                print("    not a number; choose a remaining step id")
                continue
            if new_target not in valid_targets:
                ids = ", ".join(str(i) for i in valid_targets)
                print(f"    step {new_target} is not a remaining step ({ids})")
                continue
            current = replace(current, target_id=new_target)
            continue  # re-display with the new target, then keep/edit/drop
        print("    please choose k, e, m, d, or Enter")


def cmd_suggest_gates(
    args: argparse.Namespace,
    *,
    invoker: Optional[GateInvoker] = None,
    input_fn=input,
) -> int:
    """Propose and (after confirmation) write gates for a plan's remaining steps.

    Interactive: each suggestion is shown and kept / edited / dropped, then the
    confirmed gates are written onto their target steps. Non-interactive
    (``--yes`` or non-TTY): the suggestions are printed as a report and
    **nothing is written** — a gate is an executable shell command, so with no
    operator present the safe default is to surface rather than apply (the same
    don't-write-unvetted-commands principle the create wizard's ``--yes`` path
    follows, here landing on a useful preview instead of a silent drop).
    """
    ctx = _load_context(args)
    path = resolve_plan_for_context(ctx, args.slug)
    plan = parse_plan(path)

    all_steps = getattr(args, "all_steps", False)
    if not remaining_steps(plan):
        tool(
            "every step is done — no remaining steps for a gate to attach to",
            level="note",
        )
        return 0
    if not all_steps and not built_steps(plan):
        tool(
            "no built (done) steps yet — nothing to ground gates on; run some "
            "steps first, then re-run suggest-gates (or pass --all-steps to "
            "propose speculative gates from the step details now)",
            level="note",
        )
        return 0

    inv = invoker if invoker is not None else shell_claude_invoker
    title_by_id = {s.id: s.title for s in plan.steps}
    # Remaining-step ids are the only valid attach targets — the set ``(m)ove``
    # validates against.
    valid_targets = {s.id: s.title for s in remaining_steps(plan)}

    # The backend round-trip happens below, so the run starts being logged here
    # (the two no-op guards above made no call and need no log).
    run_logger = RunLogWriter.start(
        repo_root=ctx.repo_root,
        slug=slug_from_filename(path.name) or args.slug,
        command="suggest-gates",
        argv=list(sys.argv[1:]),
        plan_path=path,
        flags={"yes": getattr(args, "yes", False), "all_steps": all_steps},
    )
    rc = 1
    err_msg: Optional[str] = None
    try:
        suggestions = suggest_gates(
            plan,
            repo_root=ctx.repo_root,
            invoker=inv,
            run_logger=run_logger,
            all_steps=all_steps,
        )
        if suggestions is None:
            err_msg = "backend response could not be parsed into gate suggestions"
            tool(f"the {err_msg}", level="warning")
            rc = 1
            return rc
        if not suggestions:
            tool("no gates suggested for the remaining steps", level="note")
            rc = 0
            return rc

        # Non-interactive: report, don't write unvetted shell commands.
        if getattr(args, "yes", False) or not sys.stdin.isatty():
            tool(
                f"{len(suggestions)} gate(s) suggested but not written "
                "(re-run interactively to apply, or add `gate:` directly):",
                level="note",
            )
            for s in suggestions:
                print(f"  step {s.target_id} ({title_by_id.get(s.target_id, '?')}): {s.command}")
                if s.rationale:
                    print(f"    — {s.rationale}")
            rc = 0
            return rc

        kept: list[GateSuggestion] = []
        for s in suggestions:
            resolved = _ask_suggestion(
                input_fn, suggestion=s, valid_targets=valid_targets
            )
            if resolved is not None:
                kept.append(resolved)

        if not kept:
            tool("no gates kept — plan unchanged", level="note")
            rc = 0
            return rc

        updated = apply_gate_suggestions(plan, kept)
        write_plan(path, updated)
        n_steps = len({s.target_id for s in kept})
        tool(
            f"wrote {len(kept)} gate(s) across {n_steps} step(s) to {path.name}",
            level="note",
        )
        rc = 0
        return rc
    finally:
        run_logger.run_end(
            outcome="ok" if rc == 0 else "error", rc=rc, error=err_msg
        )


def register(subparsers) -> dict[str, Handler]:
    """Add the ``suggest-gates`` subparser and return its handler map."""
    # Deliberately NOT parser.make_yes_parent(): here -y does not mean
    # auto-accept. It selects report-instead-of-prompt, so the shared help
    # text would be a false claim about the flag.
    yes_parent = argparse.ArgumentParser(add_help=False)
    yes_parent.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help=(
            "non-interactive: print the suggested gates as a report instead "
            "of prompting; nothing is written (executable commands are never "
            "applied unvetted)."
        ),
    )
    p = subparsers.add_parser(
        "suggest-gates",
        help=(
            "propose gate: commands for a plan's remaining steps, grounded in "
            "its already-built (done) steps"
        ),
        parents=[yes_parent],
    )
    p.add_argument("slug", help="plan slug or name")
    p.add_argument(
        "--all-steps",
        action="store_true",
        help=(
            "propose speculative gates from the step details even when no step "
            "is built yet (e.g. on a freshly-created plan); every not-done "
            "step becomes a valid target. Default grounds gates only on "
            "already-built (done) steps."
        ),
    )
    return {"suggest-gates": cmd_suggest_gates}
