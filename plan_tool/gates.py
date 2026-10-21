"""Gate suggestion: propose ``gate:`` commands for a plan's steps.

Two grounding modes share one engine, prompt contract, and review walk:

- **Post-build (default)** — grounded in the plan's already-built (``done``)
  steps, targeting the remaining not-done steps. The model can cite real test
  files, real symbols, and the actual diff, and the gates land where they pay
  off: locking in what a completed step established so a later step can't
  silently regress it (exactly the pattern the retired ``run-plan-gated.sh``
  harness hand-wrote per plan).
- **Pre-build (``all_steps``)** — for a plan with no built steps yet (e.g. a
  freshly-created plan). With no diff to inspect, the model proposes
  *speculative* gates from each step's stated intent and detail. Every
  not-done step is a valid target.

This module is pure domain logic — no CLI imports, an injectable ``invoker``
so tests never shell out. The :mod:`plan_tool.cli.gates_cmd` command wires it
to the active backend, the operator wizard, and the plan write-back.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

from plan_tool.detail_artifacts import require_supported_detail_format_version
from plan_tool.schema import Plan, Step, StepStatus
from plan_tool.run_log import hash_prompt
from plan_tool.response_contract import (
    JSON_ROOT_ARRAY,
    JsonResponseContract,
    coerce_response_id,
)

if TYPE_CHECKING:  # avoid a runtime import in this leaf domain module
    from plan_tool.run_log import RunLogWriter

# A claude round-trip: prompt in, raw response text out. The CLI passes
# :func:`plan_tool.create.shell_claude_invoker` (the active backend); tests
# pass a canned-response fake.
GateInvoker = Callable[[str], str]

# Cap on per-step detail text folded into the prompt. Detail files can be
# long; the head carries the step's intent/acceptance, which is what grounds
# a gate, so a generous head is enough without blowing up the prompt.
_DETAIL_HEAD_CHARS = 4000

_GATE_SUGGESTIONS_RESPONSE_CONTRACT = JsonResponseContract(
    root=JSON_ROOT_ARRAY,
    # Show both valid protects states so neither becomes the default.
    example=[{
        "command": "uv run pytest tests/test_example.py -q",
        "target": 1,
        "protects": None,
        "rationale": "protects the completed invariant",
    }, {
        "command": "uv run pytest tests/test_other_example.py -q",
        "target": 2,
        "protects": 1,
        "rationale": "protects the invariant step 1 established",
    }],
)


@dataclass(frozen=True)
class GateSuggestion:
    """One proposed gate: a shell ``command`` to attach to the remaining step
    ``target_id``, protecting the invariant established by the built step
    ``protects_id`` (``None`` when the model didn't name one). ``rationale``
    is the model's one-line defense, shown in the review wizard."""

    command: str
    target_id: int
    rationale: str = ""
    protects_id: Optional[int] = None


def built_steps(plan: Plan) -> list[Step]:
    """The plan's already-built steps (status ``done``) — the invariants a
    gate would protect."""
    return [s for s in plan.steps if s.status == StepStatus.DONE]


def remaining_steps(plan: Plan) -> list[Step]:
    """The not-done steps (pending / current / blocked) — the valid targets a
    suggested gate can attach to."""
    return [s for s in plan.steps if s.status != StepStatus.DONE]


def default_target_step(plan: Plan) -> Optional[Step]:
    """The step a suggestion lands on when the model names no valid target.

    Prefers the ``current`` step (the next thing to run), else the first
    runnable pending step, else the first remaining step in list order.
    ``None`` only when nothing remains.
    """
    cur = plan.current_step()
    if cur is not None:
        return cur
    nxt = plan.next_runnable_step()
    if nxt is not None:
        return nxt
    rem = remaining_steps(plan)
    return rem[0] if rem else None


def load_step_details(
    plan: Plan,
    steps: list[Step],
    repo_root: Path,
    *,
    head_chars: int = _DETAIL_HEAD_CHARS,
) -> dict[int, str]:
    """Read the detail markdown of each given step, keyed by step id.

    Best-effort: a step with no ``detail`` path, or whose file is missing or
    unreadable, is simply absent from the result (the prompt still carries the
    step's title / files / change_type). A present unsupported-format body is
    a hard refusal, not an omission. Each body is truncated to ``head_chars``.
    """
    out: dict[int, str] = {}
    for step in steps:
        if not step.detail:
            continue
        path = repo_root / step.detail
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        require_supported_detail_format_version(text, path=path)
        out[step.id] = text[:head_chars]
    return out


def load_done_details(
    plan: Plan, repo_root: Path, *, head_chars: int = _DETAIL_HEAD_CHARS
) -> dict[int, str]:
    """Read the detail markdown of each built step (see :func:`load_step_details`)."""
    return load_step_details(plan, built_steps(plan), repo_root, head_chars=head_chars)


def _render_done_step_block(step: Step, detail: Optional[str]) -> str:
    ct = step.change_type.value if step.change_type else "unclassified"
    files = ", ".join(step.all_files) or "(none)"
    lines = [f"- step {step.id} [{ct}]: {step.title}", f"  files: {files}"]
    if detail:
        lines.append(f"  detail (head):\n{detail.strip()}")
    return "\n".join(lines)


def _render_remaining_step_line(step: Step) -> str:
    line = f"- step {step.id}: {step.title}"
    if step.gate:
        existing = "; ".join(f"`{g}`" for g in step.gate)
        line += f"  (already gated: {existing})"
    return line


def render_suggest_gates_prompt(
    plan: Plan,
    *,
    done: list[Step],
    remaining: list[Step],
    done_details: dict[int, str],
    default_target_id: int,
) -> str:
    """Build the prompt that asks the backend to propose grounded gates.

    Frames the task around *protecting built work*: the model is given the
    completed steps (with detail heads) as the invariants to guard and the
    remaining steps as the only valid attach targets, and is told to ground
    every command in artifacts that actually exist now (real test files,
    symbols, the diff) — the whole point of running after the build. The
    strict JSON-only contract mirrors :func:`plan_tool.create._render_from_prompt`.
    """
    done_block = "\n".join(
        _render_done_step_block(s, done_details.get(s.id)) for s in done
    )
    remaining_block = "\n".join(_render_remaining_step_line(s) for s in remaining)
    return (
        "Propose `gate:` commands that protect the work already built in this "
        "plan from being regressed by its remaining steps.\n\n"
        "A `gate` is a shell command `plan-tool run` executes after a step's "
        "work, before advancing — a non-zero exit blocks the step. Gates are "
        "for *ephemeral / structural / cross-artifact / per-milestone* checks "
        "that would rot or be wrong as a permanent unit test: a `--help` "
        "golden diff, a `grep` proving a removed identifier is gone repo-wide, "
        "a per-milestone module/line cap, a `pytest` of the suite a built step "
        "established, a smoke command.\n\n"
        "**Ground every command in what exists now.** These steps are already "
        "built — Glob/Read/Grep the repo and the diff to cite REAL test files, "
        "symbols, and paths. Do NOT invent a path. Do NOT propose a gate for a "
        "durable behavioral invariant (that is a real unit test) nor for the "
        "whole suite run (that is `test_command`). Do NOT re-propose a command "
        "already shown as `already gated` on a remaining step below. If nothing "
        "is worth gating, return an empty array.\n\n"
        "Already-built steps (the invariants to protect):\n"
        f"{done_block}\n\n"
        "Remaining steps (the ONLY valid `target` ids — attach each gate to "
        "the earliest remaining step by which the invariant must already "
        f"hold; default to step {default_target_id} when unsure):\n"
        f"{remaining_block}\n\n"
        + _GATE_SUGGESTIONS_RESPONSE_CONTRACT.render_prompt_block()
        + "\n\n`command` is one runnable shell command; `target` "
        "is a remaining step id; `protects` is the built step id whose work it "
        "guards; `rationale` is one line."
    )


def _render_planned_step_block(step: Step, detail: Optional[str]) -> str:
    """Render a not-yet-built step for the pre-build prompt: like a done block
    but also surfacing any existing gate (so the model won't re-propose it)."""
    ct = step.change_type.value if step.change_type else "unclassified"
    files = ", ".join(step.all_files) or "(none)"
    lines = [f"- step {step.id} [{ct}]: {step.title}", f"  files: {files}"]
    if step.gate:
        existing = "; ".join(f"`{g}`" for g in step.gate)
        lines.append(f"  already gated: {existing}")
    if detail:
        lines.append(f"  detail (head):\n{detail.strip()}")
    return "\n".join(lines)


def render_pre_build_gates_prompt(
    plan: Plan,
    *,
    steps: list[Step],
    step_details: dict[int, str],
    default_target_id: int,
) -> str:
    """Build the prompt for speculative gates on a not-yet-built plan.

    The ``all_steps`` companion to :func:`render_suggest_gates_prompt`: with no
    built step there is no diff to ground in, so the model proposes gates
    speculatively from each step's stated intent and detail instead. Shares
    the strict JSON-only contract so :func:`parse_gate_suggestions` is reused.
    """
    step_block = "\n".join(
        _render_planned_step_block(s, step_details.get(s.id)) for s in steps
    )
    return (
        "Propose `gate:` commands that protect the invariants this plan's steps "
        "will establish, so a later step can't silently regress an earlier "
        "one.\n\n"
        "A `gate` is a shell command `plan-tool run` executes after a step's "
        "work, before advancing — a non-zero exit blocks the step. Gates are "
        "for *ephemeral / structural / cross-artifact / per-milestone* checks "
        "that would rot or be wrong as a permanent unit test: a `--help` "
        "golden diff, a `grep` proving a removed identifier is gone repo-wide, "
        "a per-milestone module/line cap, a `pytest` of the suite a step "
        "establishes, a smoke command.\n\n"
        "**These steps are NOT built yet — there is no diff to inspect.** "
        "Propose each command speculatively from the step's stated intent and "
        "detail below, citing the test paths / symbols the step says it will "
        "create or touch. A gate may reference a path that does not exist yet "
        "(it must hold by the time the step it guards runs). Do NOT propose a "
        "gate for a durable behavioral invariant (that is a real unit test) nor "
        "for the whole suite run (that is `test_command`). Do NOT re-propose a "
        "command already shown as `already gated` on a step below. If nothing "
        "is worth gating, return an empty array.\n\n"
        "Plan steps (each id is a valid `target`; attach each gate to the "
        "earliest step by which the invariant must already hold; default to "
        f"step {default_target_id} when unsure):\n"
        f"{step_block}\n\n"
        + _GATE_SUGGESTIONS_RESPONSE_CONTRACT.render_prompt_block()
        + "\n\n`command` is one runnable shell command; `target` "
        "is a step id; `protects` is the step id whose work it guards (or null); "
        "`rationale` is one line."
    )


def parse_gate_suggestions(
    raw: str, *, valid_targets: set[int], default_target_id: int
) -> Optional[list[GateSuggestion]]:
    """Parse the backend's JSON into :class:`GateSuggestion`s.

    Lenient on individual entries (a malformed one is dropped, never sinking
    the batch), strict on the envelope (no parseable ``[...]`` → ``None`` so
    the caller can distinguish "unparseable response" from "nothing
    suggested", which is a valid empty array). A ``target`` that is missing or
    not a remaining-step id is retargeted to ``default_target_id`` rather than
    dropped — the suggestion is still useful, the operator confirms placement.
    Commands are preserved verbatim (a gate may carry quoted whitespace).
    """
    items = _GATE_SUGGESTIONS_RESPONSE_CONTRACT.decode(raw)
    if not isinstance(items, list):
        return None
    out: list[GateSuggestion] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        command = item.get("command")
        if not isinstance(command, str) or not command.strip():
            continue
        raw_target = coerce_response_id(item.get("target"))
        target = (
            raw_target
            if raw_target in valid_targets
            else default_target_id
        )
        protects = coerce_response_id(item.get("protects"))
        rationale = item.get("rationale")
        rationale = rationale.strip() if isinstance(rationale, str) else ""
        out.append(
            GateSuggestion(
                command=command,
                target_id=target,
                rationale=rationale,
                protects_id=protects,
            )
        )
    return out


def suggest_gates(
    plan: Plan,
    *,
    repo_root: Path,
    invoker: GateInvoker,
    done_details: Optional[dict[int, str]] = None,
    run_logger: "Optional[RunLogWriter]" = None,
    all_steps: bool = False,
) -> Optional[list[GateSuggestion]]:
    """Suggest gates for ``plan``'s remaining steps.

    Default (post-build): grounds the suggestions in the plan's built (``done``)
    steps — returns an empty list when there are no built steps. With
    ``all_steps=True`` (pre-build): grounds them speculatively in every not-done
    step's detail instead, so a plan with no built steps still gets suggestions.

    Returns ``None`` when the backend response is unparseable; an empty list
    when there is nothing to do (no valid steps, or the model suggested none);
    otherwise the parsed suggestions. ``done_details`` overrides the on-disk
    detail read (used by tests).

    When ``run_logger`` is supplied the single backend round-trip is bracketed
    by the standard call-end sink (phase ``suggest_gates``), so the call shows
    up in ``plan-tool runs list`` like every other backend interaction.
    """
    remaining = remaining_steps(plan)
    if not remaining:
        return []
    target = default_target_step(plan)
    if target is None:
        return []
    if all_steps:
        details = (
            done_details
            if done_details is not None
            else load_step_details(plan, remaining, repo_root)
        )
        prompt = render_pre_build_gates_prompt(
            plan,
            steps=remaining,
            step_details=details,
            default_target_id=target.id,
        )
    else:
        done = built_steps(plan)
        if not done:
            return []
        details = (
            done_details
            if done_details is not None
            else load_done_details(plan, repo_root)
        )
        prompt = render_suggest_gates_prompt(
            plan,
            done=done,
            remaining=remaining,
            done_details=details,
            default_target_id=target.id,
        )
    if run_logger is not None:
        run_logger.claude_call_start(
            phase="suggest_gates", attempt=1,
            prompt_bytes=len(prompt.encode("utf-8")),
            prompt_sha256=hash_prompt(prompt),
        )
        run_logger.install_call_end_sink(phase="suggest_gates", attempt=1)
    try:
        raw = invoker(prompt)
    finally:
        if run_logger is not None:
            run_logger.uninstall_call_end_sink()
    return parse_gate_suggestions(
        raw,
        valid_targets={s.id for s in remaining},
        default_target_id=target.id,
    )


def apply_gate_suggestions(
    plan: Plan, suggestions: list[GateSuggestion]
) -> Plan:
    """Return a copy of ``plan`` with each suggestion's ``command`` appended to
    its ``target_id`` step's ``gate`` list.

    Pure list→model transform (no I/O). De-dupes: a command already present on
    the target step is not appended twice. Steps with no suggestion are
    returned unchanged. The result is re-validated by ``write_plan`` at the
    call site.
    """
    by_target: dict[int, list[str]] = {}
    for s in suggestions:
        by_target.setdefault(s.target_id, []).append(s.command)
    new_steps: list[Step] = []
    for step in plan.steps:
        adds = by_target.get(step.id)
        if not adds:
            new_steps.append(step)
            continue
        merged = list(step.gate)
        for cmd in adds:
            if cmd not in merged:
                merged.append(cmd)
        new_steps.append(step.model_copy(update={"gate": merged}))
    return plan.model_copy(update={"steps": new_steps})
