"""Shared foundational-logic sweep.

A single focused claude call that names a plan's (or a step's) **foundational
logic** and greps the repo for other locations sharing it — duplicated blocks,
parallel call sites, sibling implementations. Lifted out of the `create`
step-proposal and `detail` authoring prompts so the *divergent* repo-wide search
no longer competes with those prompts' *convergent* emission.

Two consumers:
- ``create`` runs the sweep over the proposed step list, then
  :func:`merge_sweep_into_steps` folds finds back into the existing
  ``files``/``creates`` shapes or appends a consolidation step.
- ``detail`` runs the sweep over the single step in scope, then
  :func:`format_foundational_logic_block` injects the result into the authoring
  prompt so the model *places* the finds (no searching of its own).

The call is stdlib-only below the invoker seam: callers pass an
``invoker`` (the same ``shell_*_invoker`` they already hold), so tests stub it
without spawning a backend.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from pathlib import Path
from string import Template
from typing import Any, Callable, Optional

from plan_tool.run_log import hash_prompt
from plan_tool.renderer import prompts_dir
from plan_tool.response_contract import (
    JSON_ROOT_OBJECT,
    JsonResponseContract,
    coerce_response_id,
)
from plan_tool.review import is_usable_intent
from plan_tool.schema import ChangeType, Step
from plan_tool.scope_fence import collapse_intent_to_one_line

# Invoker shape shared with ``create`` (stdout only). The sweep ignores any
# exit code — a non-empty body is parsed, an empty/garbage one yields ``None``.
SweepInvoker = Callable[[str], str]

# Threshold for the multi-file foundational footprint (shared by create/detail
# scenario categorization).
_FOUNDATIONAL_MULTI_FILE = 2


def step_has_foundational_footprint(step: Step) -> bool:
    """Arm-independent structural signal that a step touches *shared logic*.

    Two patterns, derived from the step STRUCTURE (identical in both arms, which
    both fold foundational finds into ``files`` / ``creates``):
    - **spans ≥2 existing files** — edits logic that lives in multiple
      locations; or
    - **extract-to-new-source** — creates ≥1 new file *while* editing ≥1
      existing (factoring shared logic out + updating its callers).

    Broadened beyond a refactor-only proxy so a *non-refactor* consolidation
    (e.g. a feature that extracts a shared module) is still caught — recall over
    precision, since a thin foundational cohort hurts the A/B more than a few
    marginal members.
    """
    return len(step.files) >= _FOUNDATIONAL_MULTI_FILE or (
        len(step.creates) >= 1 and len(step.files) >= 1
    )

_RELATIONS = frozenset(
    {"duplicate", "parallel-call-site", "sibling-implementation"}
)
_RECOMMENDATIONS = frozenset({"update-in-place", "consolidate", "defer"})

_SWEEP_RESPONSE_CONTRACT = JsonResponseContract(
    root=JSON_ROOT_OBJECT,
    # Cover every vocabulary member and both nullable-id states.
    example={
        "logic": "one phrase naming the foundational logic",
        "shared_locations": [{
            "path": "repo/relative/path.py",
            "anchor": "symbol_or_section",
            "relation": "duplicate",
            "recommendation": "update-in-place",
            "note": "what is shared and why it matters",
            "step_id": None,
        }, {
            "path": "repo/relative/other_path.py",
            "anchor": "other_symbol",
            "relation": "sibling-implementation",
            "recommendation": "consolidate",
            "note": "what is shared and why it matters",
            "step_id": 2,
        }, {
            "path": "repo/relative/caller.py",
            "anchor": "call_site",
            "relation": "parallel-call-site",
            "recommendation": "defer",
            "note": "why this location remains out of scope",
            "step_id": None,
        }],
        "consolidation": {
            "title": "dedicated consolidation step title",
            "files": ["existing/path.py"],
            "creates": ["new/path.py"],
            "rationale": "why one source beats in-place patches",
            "intent": "why this step exists",
            "after_step_id": None,
        },
    },
    alternate_examples=({
        "logic": "one phrase naming the foundational logic",
        "shared_locations": [],
        "consolidation": {
            "title": "dedicated consolidation step title",
            "files": ["existing/path.py"],
            "creates": ["new/path.py"],
            "rationale": "why one source beats in-place patches",
            "intent": "why this step exists",
            "after_step_id": 2,
        },
    },),
)


@dataclass(frozen=True)
class SharedLocation:
    """One repo location that exercises the same foundational logic."""

    path: str
    anchor: str = ""
    relation: str = ""
    recommendation: str = ""
    note: str = ""
    step_id: Optional[int] = None


@dataclass(frozen=True)
class ConsolidationSuggestion:
    """A proposed dedicated step that collapses duplicated logic to one source."""

    title: str
    files: list[str] = field(default_factory=list)
    creates: list[str] = field(default_factory=list)
    rationale: str = ""
    intent: str = ""
    after_step_id: Optional[int] = None


@dataclass(frozen=True)
class SweepResult:
    """Parsed foundational-logic sweep response."""

    logic: str
    shared_locations: list[SharedLocation] = field(default_factory=list)
    consolidation: Optional[ConsolidationSuggestion] = None

    def is_empty(self) -> bool:
        """True when the sweep surfaced nothing to act on or display."""
        return (
            not self.shared_locations
            and self.consolidation is None
            and not self.logic.strip()
        )


def render_foundational_logic_prompt(sweep_context: str) -> str:
    """Render ``prompts/foundational-logic-sweep.md`` with caller-supplied scope.

    ``sweep_context`` is the in-scope description the caller assembles —
    the proposed step list (create) or the single step's context (detail).
    """
    template_path = prompts_dir() / "foundational-logic-sweep.md"
    template = Template(template_path.read_text(encoding="utf-8"))
    return template.safe_substitute(
        sweep_context=sweep_context.strip(),
        response_format_block=_SWEEP_RESPONSE_CONTRACT.render_prompt_block(),
    )


def parse_sweep_response(raw: str) -> Optional[SweepResult]:
    """Parse the sweep JSON. Returns ``None`` when nothing usable is present.

    Lenient like ``_parse_steps_json``: slices the first ``{`` … last ``}``,
    tolerates trailing prose, and coerces soft fields rather than rejecting the
    whole response. A missing/blank ``logic`` with no locations yields ``None``
    (treated as "no sweep result" by callers).
    """
    obj = _SWEEP_RESPONSE_CONTRACT.decode(raw)
    if not isinstance(obj, dict):
        return None

    logic = obj.get("logic")
    logic = logic.strip() if isinstance(logic, str) else ""

    locations: list[SharedLocation] = []
    raw_locs = obj.get("shared_locations")
    if isinstance(raw_locs, list):
        for item in raw_locs:
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            if not isinstance(path, str) or not path.strip():
                continue
            relation = item.get("relation")
            recommendation = item.get("recommendation")
            step_id = item.get("step_id")
            locations.append(
                SharedLocation(
                    path=path.strip(),
                    anchor=_soft_str(item.get("anchor")),
                    relation=(
                        relation if relation in _RELATIONS else ""
                    ),
                    recommendation=(
                        recommendation
                        if recommendation in _RECOMMENDATIONS
                        else ""
                    ),
                    note=_soft_str(item.get("note")),
                    step_id=coerce_response_id(step_id),
                )
            )

    consolidation = _parse_consolidation(obj.get("consolidation"))

    result = SweepResult(
        logic=logic,
        shared_locations=locations,
        consolidation=consolidation,
    )
    return None if result.is_empty() else result


def _parse_consolidation(raw: object) -> Optional[ConsolidationSuggestion]:
    if not isinstance(raw, dict):
        return None
    title = raw.get("title")
    if not isinstance(title, str) or not title.strip():
        return None
    after = raw.get("after_step_id")
    return ConsolidationSuggestion(
        title=title.strip(),
        files=_soft_str_list(raw.get("files")),
        creates=_soft_str_list(raw.get("creates")),
        rationale=_soft_str(raw.get("rationale")),
        intent=_soft_str(raw.get("intent")),
        after_step_id=coerce_response_id(after),
    )


def _soft_str(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _soft_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [v.strip() for v in value if isinstance(v, str) and v.strip()]


def logged_invoke(
    invoker: SweepInvoker,
    prompt: str,
    *,
    run_logger: Optional[Any],
    phase: str,
    attempt: int,
    step_id: Optional[int] = None,
) -> str:
    """Invoke ``invoker(prompt)``, emitting run-log telemetry when a
    ``run_logger`` is present so a split sub-call is visible in the same
    ``.plan-tool/runs/`` log the scorer reads.

    Emits a ``claude_call_start`` per attempt (the attempt count is the
    first-pass-compliance signal — an attempt-2 event means attempt 1 failed to
    parse) and binds the shell call-end sink so the call's tokens/cost are
    attributed to ``phase``. Duck-typed: ``run_logger`` is any object exposing
    ``claude_call_start`` / ``bind_shell_sink``.
    """
    if run_logger is None:
        return invoker(prompt)
    extra = {"step_id": step_id} if step_id is not None else {}
    run_logger.claude_call_start(
        phase=phase,
        attempt=attempt,
        prompt_bytes=len(prompt.encode("utf-8")),
        prompt_sha256=hash_prompt(prompt),
        **extra,
    )
    with run_logger.bind_shell_sink(phase=phase, attempt=attempt):
        return invoker(prompt)


def run_foundational_logic_sweep(
    sweep_context: str,
    invoker: SweepInvoker,
    *,
    run_logger: Optional[Any] = None,
    phase: str = "foundational_sweep",
    step_id: Optional[int] = None,
) -> Optional[SweepResult]:
    """Run the sweep call once, with a single repair retry on parse failure.

    Mirrors the one-retry contract used by ``propose_steps_from_claude`` and
    ``generate_detail``: a parse miss is usually model variance, so re-prompt
    once with the contract restated before giving up. Returns ``None`` when both
    attempts fail to yield a usable result — callers treat that as "no sweep"
    and proceed unchanged. A ``run_logger`` (when wired by the split arm) makes
    each attempt visible in the run-log telemetry.
    """
    prompt = render_foundational_logic_prompt(sweep_context)
    raw = logged_invoke(
        invoker, prompt, run_logger=run_logger, phase=phase, attempt=1,
        step_id=step_id,
    )
    result = parse_sweep_response(raw)
    if result is not None:
        return result
    repair_prompt = (
        prompt
        + "\n\n## Repair\n\nYour previous response did not parse as the "
        "required JSON object. Return ONLY the JSON object described in the "
        "Output contract — no fences, no preamble."
    )
    raw = logged_invoke(
        invoker, repair_prompt, run_logger=run_logger, phase=phase, attempt=2,
        step_id=step_id,
    )
    return parse_sweep_response(raw)


def merge_sweep_into_steps(
    steps: list[Step],
    result: Optional[SweepResult],
    *,
    repo_root: Optional[Path] = None,
) -> list[Step]:
    """Fold sweep finds into the existing ``Step`` shapes (create consumer).

    Per item 9's contract, an ``update-in-place`` location appends its path
    to the named step's ``files``/``creates``; a ``consolidation`` appends a
    new ``refactor`` step instead, with ``intent`` taken from the
    suggestion's own ``intent`` (falling back to ``rationale``, then
    ``None``). A deferred path suppresses only a consolidation that names it.

    Returns a new list; the input is not mutated. A ``None`` result returns the
    steps unchanged.
    """
    if result is None:
        return steps

    by_id = {s.id: s for s in steps}
    # Accumulate per-step path additions, then rebuild each Step once.
    add_files: dict[int, list[str]] = {}
    add_creates: dict[int, list[str]] = {}
    for loc in result.shared_locations:
        if loc.recommendation != "update-in-place":
            continue
        if loc.step_id is None or loc.step_id not in by_id:
            continue
        exists = (
            repo_root is not None and (repo_root / loc.path).exists()
        )
        bucket = add_files if exists else add_creates
        bucket.setdefault(loc.step_id, []).append(loc.path)

    merged: list[Step] = []
    for step in steps:
        extra_files = _dedup_new(step.files, add_files.get(step.id, []))
        extra_creates = _dedup_new(
            step.creates, add_creates.get(step.id, [])
        )
        if not extra_files and not extra_creates:
            merged.append(step)
            continue
        merged.append(
            step.model_copy(
                update={
                    "files": [*step.files, *extra_files],
                    "creates": [*step.creates, *extra_creates],
                }
            )
        )

    consolidation = result.consolidation
    deferred_paths = {
        loc.path
        for loc in result.shared_locations
        if loc.recommendation == "defer"
    }
    if consolidation is not None and deferred_paths.intersection(
        [*consolidation.files, *consolidation.creates]
    ):
        consolidation = None
    if consolidation is not None:
        next_id = max((s.id for s in merged), default=0) + 1
        depends_on = (
            [consolidation.after_step_id]
            if consolidation.after_step_id in by_id
            else []
        )
        # Prefers intent; falls back to rationale (item-6-style
        # classification-defense, not "why this step exists") only when
        # intent isn't usable. is_usable_intent — not a hand-rolled blank
        # check — so a placeholder like "TBD" doesn't out-rank a real
        # rationale the way bare truthiness or .strip() alone would.
        consolidation_intent = (
            consolidation.intent
            if is_usable_intent(consolidation.intent)
            else consolidation.rationale
            if is_usable_intent(consolidation.rationale)
            else None
        )
        merged.append(
            Step(
                id=next_id,
                title=consolidation.title,
                change_type=ChangeType.REFACTOR,
                files=consolidation.files,
                creates=consolidation.creates,
                depends_on=depends_on,
                intent=(
                    collapse_intent_to_one_line(consolidation_intent)
                    if consolidation_intent
                    else None
                ),
            )
        )
    return merged


def _dedup_new(existing: list[str], additions: list[str]) -> list[str]:
    """Return additions not already in ``existing`` (order-preserving, unique)."""
    seen = set(existing)
    out: list[str] = []
    for path in additions:
        if path in seen:
            continue
        seen.add(path)
        out.append(path)
    return out


def format_foundational_logic_block(result: Optional[SweepResult]) -> str:
    """Render the sweep result for injection into the detail authoring prompt.

    Returns a placeholder string when the sweep found nothing (or was skipped),
    so the template substitution always has a value.
    """
    if result is None or result.is_empty():
        return "_no shared foundational logic surfaced for this step_"

    lines: list[str] = []
    if result.logic:
        lines.append(f"**Foundational logic:** {result.logic}")
        lines.append("")
    if result.shared_locations:
        lines.append("Shared locations (place each in the right section):")
        for loc in result.shared_locations:
            anchor = f" — `{loc.anchor}`" if loc.anchor else ""
            tags = ", ".join(t for t in (loc.relation, loc.recommendation) if t)
            tag_str = f" ({tags})" if tags else ""
            note = f" — {loc.note}" if loc.note else ""
            lines.append(f"- `{loc.path}`{anchor}{tag_str}{note}")
        lines.append("")
    if result.consolidation is not None:
        c = result.consolidation
        # Deliberately c.rationale, not c.intent: this candidate is routed to
        # `## Deferred`, never materialized into a Step here, so there is no
        # step yet for `intent` to answer "why does it exist" about.
        lines.append(
            f"Consolidation candidate (route to `## Deferred` for reconcile): "
            f"{c.title}"
            + (f" — {c.rationale}" if c.rationale else "")
        )
    return "\n".join(lines).strip()
