"""Estimate a prompt's token cost against a context-window budget and warn
*before* the call is sent — a pre-flight safeguard, not post-mortem accounting.

Today the tool only learns a prompt was too big after a call fails
(``plan_tool/claude_errors.py`` classifies ``CONTEXT_OVERFLOW`` on a failed
invoke). ``prompt_bytes`` is measured all over the codebase but nothing
compares it to a budget beforehand. This leaf is the shared measuring stick:
turn a byte count into a conservative token estimate, classify the headroom
into ``ok`` / ``warn`` / ``high``, and — only at ``warn``/``high`` — emit a
color-gated advisory. The advisory never blocks the invoke and never changes
an exit code (same surface-and-return discipline as the ``convergence``
diagnostic); wiring steps feed their byte totals in and the caller resolves
and passes ``context_window``.

Cycle-free leaf: the only first-party import is ``plan_tool.style`` (itself a
leaf) for color-gated diagnostic formatting — no orchestrator, no
``model_specs``. See ``docs/how-to/pipeline/audit.md`` for where the wiring steps call it.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from typing import Mapping, Optional, Sequence, TextIO, Union

from plan_tool.style import warn as _style_warn

# Conservative bytes-per-token divisor — kept a named constant so BACKLOG #72
# telemetry can retune it later without hunting magic numbers.
BYTES_PER_TOKEN = 3.5
# ~200K-class fallback window when the caller passes no ``context_window`` —
# an illustrative Anthropic-class size. Callers pass the selected model's window
# from ``plan_tool.context_window`` where it is known; this is the unknown case.
DEFAULT_CONTEXT_WINDOW = 200_000
# Headroom fractions below which the advisory fires (checked high before warn).
WARN_HEADROOM_RATIO = 0.40
HIGH_HEADROOM_RATIO = 0.15

LEVEL_OK = "ok"
LEVEL_WARN = "warn"
LEVEL_HIGH = "high"

# Cap the per-block breakdown so a warning stays scannable.
_MAX_BLOCKS_SHOWN = 5

# A block breakdown is either a name→bytes mapping or a sequence of pairs.
Blocks = Union[Mapping[str, int], Sequence[tuple[str, int]]]


@dataclass(frozen=True)
class PromptBudget:
    """The verdict for one prompt assembly. In-memory only — a return value

    this leaf never writes to disk, so it carries no ``DATA_CONTRACT.md``
    obligation (step 2 records a primitive projection into telemetry, not this
    dataclass). ``blocks`` is the per-block breakdown (name→bytes) sorted
    largest-first, empty when the caller passed none.
    """

    total_bytes: int
    estimated_tokens: int
    context_window: int
    headroom_ratio: float
    level: str
    # True when no usable window was passed and DEFAULT_CONTEXT_WINDOW stood in. Required, so a
    # hand-built budget must say whether its window was known.
    window_defaulted: bool
    blocks: tuple[tuple[str, int], ...] = ()


def _normalize_blocks(blocks: Optional[Blocks]) -> tuple[tuple[str, int], ...]:
    """Coerce a mapping or pair-sequence into pairs sorted by bytes descending."""
    if not blocks:
        return ()
    pairs = list(blocks.items()) if isinstance(blocks, Mapping) else list(blocks)
    return tuple(sorted(
        ((str(name), int(size)) for name, size in pairs),
        key=lambda nb: nb[1],
        reverse=True,
    ))


def estimate_prompt_budget(
    total_bytes: int,
    *,
    context_window: Optional[int] = None,
    blocks: Optional[Blocks] = None,
) -> PromptBudget:
    """Estimate tokens for ``total_bytes`` and classify headroom vs the window.

    Pure. Rounds the token estimate **up** (never under-reports), guards a
    non-positive ``context_window`` by falling back to the default, and
    classifies ``high`` before ``warn`` (a tight prompt satisfies both ``<``
    thresholds — the tighter one must win).
    """
    estimated_tokens = math.ceil(total_bytes / BYTES_PER_TOKEN)
    window_defaulted = context_window is None or context_window <= 0
    window = DEFAULT_CONTEXT_WINDOW if window_defaulted else context_window
    # Goes negative when the estimate exceeds the window — that lands in high.
    headroom_ratio = (window - estimated_tokens) / window
    if headroom_ratio < HIGH_HEADROOM_RATIO:
        level = LEVEL_HIGH
    elif headroom_ratio < WARN_HEADROOM_RATIO:
        level = LEVEL_WARN
    else:
        level = LEVEL_OK
    return PromptBudget(
        total_bytes=total_bytes,
        estimated_tokens=estimated_tokens,
        context_window=window,
        headroom_ratio=headroom_ratio,
        level=level,
        blocks=_normalize_blocks(blocks),
        window_defaulted=window_defaulted,
    )


def render_budget_summary(
    budget: PromptBudget,
    *,
    surface: str = "",
    blocks_label: str = "top blocks",
    max_blocks: Optional[int] = _MAX_BLOCKS_SHOWN,
    remedies: Sequence[str] = (),
) -> str:
    """Format the one-line budget summary shared by the advisory and the
    dry-run breakdown printers, so the wording and number format live here
    once (not copy-pasted across the leaf + the detail/run printers).

    ``max_blocks=None`` shows every block (the dry-run printers, which are
    inspection surfaces); a positive cap truncates with an ellipsis (the
    advisory, to stay scannable).
    """
    head = f"prompt budget {budget.level}"
    if surface:
        head += f" for {surface}"
    parts = [
        f"{head}: ~{budget.estimated_tokens:,} tokens vs "
        f"{budget.context_window:,} window"
        f"{' (default)' if budget.window_defaulted else ''} "
        f"({budget.headroom_ratio:.0%} headroom)"
    ]
    if budget.blocks:
        shown = budget.blocks if max_blocks is None else budget.blocks[:max_blocks]
        breakdown = ", ".join(f"{name} {size:,}B" for name, size in shown)
        if max_blocks is not None and len(budget.blocks) > max_blocks:
            breakdown += ", …"
        parts.append(f"{blocks_label}: {breakdown}")
    if remedies:
        parts.append("remedies: " + "; ".join(remedies))
    return " — ".join(parts)


def maybe_warn_prompt_budget(
    total_bytes: int,
    *,
    context_window: Optional[int] = None,
    blocks: Optional[Blocks] = None,
    surface: str = "",
    remedies: Sequence[str] = (),
    stream: Optional[TextIO] = None,
) -> PromptBudget:
    """Estimate the budget and, at ``warn``/``high`` only, emit an advisory.

    Silent at ``ok`` (the whole point of avoiding advisory fatigue). Always
    returns the :class:`PromptBudget` so a later step can record telemetry;
    never raises and never returns a value a caller could read as a block/rc
    change. Emits through ``style.warn`` so color/TTY gating matches every
    other diagnostic; ``stream`` (default stderr) is injectable for tests.
    """
    budget = estimate_prompt_budget(
        total_bytes, context_window=context_window, blocks=blocks
    )
    if budget.level == LEVEL_OK:
        return budget

    stream = stream if stream is not None else sys.stderr
    _style_warn(
        render_budget_summary(budget, surface=surface, remedies=remedies),
        stream=stream,
    )
    return budget
