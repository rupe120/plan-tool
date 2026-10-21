"""Intent proposal: draft a one-line ``intent`` for a plan and for the steps
that lack one, then take accept / edit / decline on each draft.

The create-time remedy for ``review.py``'s ``intent-presence`` finding: an
absent intent is offered a draft while the plan is still being authored, so the
blocking finding is not the operator's first encounter with the gap. On a plan
already on disk the remedy is a one-line frontmatter edit.

Entirely **in-memory** — :func:`render_intent_prompt`,
:func:`parse_intent_drafts`, :func:`propose_intents`,
:func:`review_intent_drafts`, and :func:`apply_intent_drafts`. The one caller
(``create``) holds a ``Plan`` with no file on disk yet, so nothing here reads
or writes a plan file; persisting is the caller's job.

Pure domain logic like :mod:`plan_tool.gates` — no CLI imports, and ``invoker``
is a required keyword with **no** real-backend default, so a caller that forgets
the seam fails loudly instead of shelling out.

**Presence is the only check.** ``review.is_usable_intent`` is the sole judge of
a draft, here as everywhere: nothing scores quality, caps length, or compares a
draft against the plan body, a step's ``## Why``, or its detail. Asking the model
for one line is not the same as rejecting a draft that is not one — the write
collapses whitespace (so a value cannot forge a ``##`` heading inside the scope
fence, see ``scope_fence._render_intent_section``) and truncates nothing.

Mints no finding of its own and adds no source token: the caller already holds
the ``intent-presence`` finding that fired this.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Callable, Optional

from plan_tool.review import is_usable_intent
from plan_tool.scope_fence import collapse_intent_to_one_line
from plan_tool.schema import Plan, Step
from plan_tool.run_log import hash_prompt
from plan_tool.response_contract import (
    JSON_ROOT_ARRAY,
    JsonResponseContract,
    coerce_response_id,
)

if TYPE_CHECKING:  # avoid a runtime import in this domain module
    from plan_tool.run_log import RunLogWriter

# A backend round-trip: prompt in, raw response text out. Callers pass the
# active backend (``plan_tool.create.shell_claude_invoker``); tests pass a
# canned-response fake. No default — see the module docstring.
IntentInvoker = Callable[[str], str]

# The response's ``target`` value for the plan-level field, as opposed to an
# integer step id.
PLAN_TARGET = "plan"

_INTENT_DRAFTS_RESPONSE_CONTRACT = JsonResponseContract(
    root=JSON_ROOT_ARRAY,
    # Cover the plan and integer step-id target arms.
    example=[
        {"target": "plan", "intent": "one line explaining why it exists"},
        {"target": 1, "intent": "one line explaining why step 1 exists"},
    ],
)


@dataclass(frozen=True)
class IntentDraft:
    """One drafted intent. ``step_id`` is ``None`` for the plan-level field."""

    step_id: Optional[int]
    text: str


# --------------------------------------------------------------------------
# Prompt.
# --------------------------------------------------------------------------


def _render_target_step_block(step_id: int, step: Optional[Step]) -> str:
    """Render one target step's grounding: title, footprint, classification."""
    if step is None:
        return f"- {step_id} — (no such step in the plan)"
    lines = [f"- {step.id} — {step.title}"]
    files = ", ".join(step.all_files)
    if files:
        lines.append(f"  files: {files}")
    facets: list[str] = []
    if step.change_type is not None:
        facets.append(f"change_type: {step.change_type.value}")
    if step.complexity is not None:
        facets.append(f"complexity: {step.complexity.value}")
    if step.depends_on:
        facets.append("depends_on: " + ", ".join(str(d) for d in step.depends_on))
    if facets:
        lines.append("  " + "; ".join(facets))
    return "\n".join(lines)


def render_intent_prompt(
    plan: Plan,
    *,
    plan_needs_intent: bool,
    step_ids: Sequence[int],
    source_text: str = "",
    project_context: str = "",
) -> str:
    """Build the one prompt that asks for every missing intent at once.

    Grounding is the plan title, each target step's title / files /
    ``change_type`` / ``complexity`` / ``depends_on``, plus whatever free-text
    ``source_text`` the caller supplies (``create`` passes the seed; the bridge
    passes the plan file). This module never decides where grounding comes from
    and opens no file to find it.

    This renderer echoes no stored intent: a target has none by construction,
    and quoting a non-target's value back invites the quality comparison this
    module must not make. ``source_text`` is the caller's own material and is
    passed through verbatim.
    """
    wanted = sorted({int(i) for i in step_ids})
    by_id = {s.id: s for s in plan.steps}
    targets = [f'- "{PLAN_TARGET}" — the plan itself'] if plan_needs_intent else []
    targets.extend(_render_target_step_block(sid, by_id.get(sid)) for sid in wanted)
    targets_block = "\n".join(targets)
    source_block = (
        f"Source material this plan was written from:\n{source_text.strip()}\n\n"
        if source_text.strip()
        else ""
    )
    project_context_block = (
        f"{project_context.strip()}\n\n" if project_context.strip() else ""
    )
    return (
        "Draft a one-line `intent` for each target below.\n\n"
        "An `intent` states **why** the thing exists — the positive half of its "
        "scope fence, carried into every authoring and execution prompt. It is "
        "not a summary of what changes (`title` and `files` already say that); "
        "it is the reason the work is worth doing, in one line.\n\n"
        "Ground every draft in the material below. Do not invent scope that is "
        "not there, and propose nothing for a target you cannot ground — a "
        "shorter array is better than a guess.\n\n"
        f"{project_context_block}"
        f"Plan: {plan.title}\n\n"
        f"{source_block}"
        "Targets (the ONLY valid `target` values):\n"
        f"{targets_block}\n\n"
        + _INTENT_DRAFTS_RESPONSE_CONTRACT.render_prompt_block()
        + "\n\n`target` is either the string "
        f'"{PLAN_TARGET}" for the plan-level field, or a **bare JSON integer** '
        "step id listed above (never a quoted string like \"1\"); "
        "`intent` is ONE line of prose."
    )


# --------------------------------------------------------------------------
# Response parse.
# --------------------------------------------------------------------------


def _first_json_array(text: str) -> Optional[list]:
    """Return the first balanced top-level ``[...]`` in ``text``, or ``None``.

    Scans for the matching bracket rather than ``rfind("]")``: the prompt
    explicitly tells the model trailing prose is tolerated, and a ``]`` inside
    that prose (a citation, a bracketed aside) would otherwise extend the slice
    past the array and make a perfectly good response unparseable. Brackets
    inside JSON strings are skipped so a draft mentioning one cannot end the
    scan early.
    """
    start = text.find("[")
    if start == -1:
        return None
    depth = 0
    in_str = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                parsed = _INTENT_DRAFTS_RESPONSE_CONTRACT.decode(
                    text[start : i + 1], allow_surrounding=False
                )
                return parsed if isinstance(parsed, list) else None
    return None


def _draft_target(
    raw_target: object, *, plan_needs_intent: bool, valid_step_ids: set[int]
) -> tuple[bool, Optional[int]]:
    """Resolve one entry's ``target`` to ``(recognized, step_id)``, where a
    ``step_id`` of ``None`` is the plan arm. The boolean is what keeps the plan
    arm distinguishable from a target the caller never asked about."""
    if isinstance(raw_target, str) and raw_target.strip().lower() == PLAN_TARGET:
        return (plan_needs_intent, None)
    coerced = coerce_response_id(raw_target)
    if coerced in valid_step_ids:
        return (True, coerced)
    return (False, None)


def parse_intent_drafts(
    raw: str, *, plan_needs_intent: bool, valid_step_ids: set[int]
) -> Optional[list[IntentDraft]]:
    """Parse the backend's JSON into :class:`IntentDraft`s.

    Lenient on entries, strict on the envelope (mirroring
    ``gates.parse_gate_suggestions``): no parseable ``[...]`` returns ``None``,
    so a caller can tell an unusable response from a valid empty array.

    An entry is dropped — never relocated — when its ``target`` is neither
    ``"plan"`` (and asked for) nor an id in ``valid_step_ids``, or when its text
    fails ``is_usable_intent``. Unlike a gate, a mis-targeted intent is not
    relocatable: an intent written onto the wrong step is a false statement
    about that step. A second draft for an already-drafted target is dropped
    too, so the operator is asked about each target exactly once.
    """
    text = raw.strip()
    items = _first_json_array(text)
    if items is None:
        return None
    if not isinstance(items, list):
        return None
    out: list[IntentDraft] = []
    seen: set[Optional[int]] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        recognized, step_id = _draft_target(
            item.get("target"),
            plan_needs_intent=plan_needs_intent,
            valid_step_ids=valid_step_ids,
        )
        if not recognized or step_id in seen:
            continue
        drafted = item.get("intent")
        if not isinstance(drafted, str) or not is_usable_intent(drafted):
            continue
        seen.add(step_id)
        out.append(IntentDraft(step_id=step_id, text=drafted))
    return out


def propose_intents(
    plan: Plan,
    *,
    invoker: IntentInvoker,
    plan_needs_intent: bool,
    step_ids: Sequence[int],
    source_text: str = "",
    project_context: str = "",
    run_logger: "Optional[RunLogWriter]" = None,
) -> Optional[list[IntentDraft]]:
    """One backend round-trip drafting every missing intent for ``plan``.

    Returns ``None`` when the response is unparseable; an empty list when the
    model drafted nothing usable, or when there was nothing to ask about (no
    targets — then no call is made at all). One call per plan, not per step.

    When ``run_logger`` is supplied the call is bracketed by the standard
    call-end sink (phase ``propose_intents``), so it shows up in
    ``plan-tool runs`` like every other backend interaction.
    """
    wanted = sorted({int(i) for i in step_ids})
    if not plan_needs_intent and not wanted:
        return []
    prompt = render_intent_prompt(
        plan,
        plan_needs_intent=plan_needs_intent,
        step_ids=wanted,
        source_text=source_text,
        project_context=project_context,
    )
    if run_logger is not None:
        run_logger.claude_call_start(
            phase="propose_intents", attempt=1,
            prompt_bytes=len(prompt.encode("utf-8")),
            prompt_sha256=hash_prompt(prompt),
        )
        run_logger.install_call_end_sink(phase="propose_intents", attempt=1)
    try:
        raw = invoker(prompt)
    finally:
        if run_logger is not None:
            run_logger.uninstall_call_end_sink()
    return parse_intent_drafts(
        raw, plan_needs_intent=plan_needs_intent, valid_step_ids=set(wanted)
    )


# --------------------------------------------------------------------------
# Operator walk: accept / edit / decline.
# --------------------------------------------------------------------------


def _draft_label(draft: IntentDraft) -> str:
    return "the plan" if draft.step_id is None else f"step {draft.step_id}"


def _ask_draft(
    input_fn: Callable[[str], str], *, draft: IntentDraft
) -> Optional[IntentDraft]:
    """Prompt for one draft; return the kept draft or ``None`` to decline.

    Enter defaults to accept. An edit that fails ``is_usable_intent`` (blank, a
    placeholder) is a decline rather than a write of nothing, and an
    unrecognized key re-prompts instead of guessing which way it was meant.
    """
    while True:
        print(f"  intent for {_draft_label(draft)}:")
        print(f"    {draft.text}")
        raw = input_fn("    (a)ccept / (e)dit / (d)ecline [accept]: ").strip().lower()
        if raw in ("", "a"):
            return draft
        if raw == "d":
            return None
        if raw == "e":
            edited = input_fn("    intent> ")
            return replace(draft, text=edited) if is_usable_intent(edited) else None
        print("    please choose a, e, d, or Enter")


def review_intent_drafts(
    drafts: Sequence[IntentDraft], *, input_fn: Callable[[str], str]
) -> list[IntentDraft]:
    """Walk the operator through each draft, returning only the kept ones.

    Every value is shown before it is kept, and nothing reaches
    :func:`apply_intent_drafts` without passing through here. An EOF or
    interrupt declines the remaining drafts rather than propagating out of a
    half-finished walk.
    """
    kept: list[IntentDraft] = []
    for draft in drafts:
        try:
            resolved = _ask_draft(input_fn, draft=draft)
        except EOFError:
            # Stdin closed (piped / non-interactive): nothing left to ask, so
            # decline the rest. ``KeyboardInterrupt`` deliberately does NOT land
            # here — Ctrl-C means "stop the run", not "accept what I have".
            print("\n  input closed — remaining drafts declined.", file=sys.stderr)
            break
        if resolved is not None:
            kept.append(resolved)
    return kept


def apply_intent_drafts(plan: Plan, drafts: Sequence[IntentDraft]) -> Plan:
    """Return a copy of ``plan`` carrying each draft's intent on its target.

    Pure model transform, no IO (mirrors ``gates.apply_gate_suggestions``). Each
    value is collapsed to a single line: a real newline could put a ``##`` at
    line start and forge a heading inside the authoritative scope-fence block
    ``scope_fence._render_intent_section`` renders. That is normalization, not
    validation — nothing is truncated or rejected for its shape. Targets with no
    draft come back untouched; the caller is responsible for persisting
    at the call site.
    """
    by_step: dict[int, str] = {}
    plan_intent: Optional[str] = None
    for draft in drafts:
        collapsed = collapse_intent_to_one_line(draft.text)
        if draft.step_id is None:
            plan_intent = collapsed
        else:
            by_step[draft.step_id] = collapsed
    new_steps = [
        step.model_copy(update={"intent": by_step[step.id]})
        if step.id in by_step
        else step
        for step in plan.steps
    ]
    update: dict[str, object] = {"steps": new_steps}
    if plan_intent is not None:
        update["intent"] = plan_intent
    return plan.model_copy(update=update)
