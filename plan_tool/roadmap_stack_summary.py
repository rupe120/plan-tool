"""The one producer of the stack summary shown at first publish and in ``INDEX.md``.

Pure text over parsed values: no I/O, no backend call, no judgment of any
choice. A leaf over ``roadmap_artifacts`` only; the first-run completion output
and the generated index both call it so their wording cannot drift.
"""

from __future__ import annotations

from collections.abc import Iterable

from plan_tool.roadmap_artifacts import (
    ConstraintsArtifact,
    DecisionRow,
    DecisionStatus,
    StackRow,
    StoreRow,
)

STACK_NOT_RECORDED_LINE = "Stack: not recorded for this version."
STACK_EMPTY_LINE = "Stack: recorded, with no rows."
OPEN_CONCERNS_HEADING = "Open concerns:"
PENDING_CONCERNS_HEADING = "Pending concerns:"
_NONE_LINE = "- none"
NO_PRODUCT_MARKER = "no product recorded"


def pending_anchor_ids(*decision_groups: Iterable[DecisionRow]) -> frozenset[str]:
    """Ids that a ``pending`` decision in any given group anchors to."""
    return frozenset(
        decision.anchor
        for decisions in decision_groups
        for decision in decisions
        if decision.status is DecisionStatus.PENDING
    )


def _one_line(value: object) -> str:
    """Model-authored text on one physical line, so it cannot start a heading or a list item."""
    return " ".join(str(value).split())


def _stack_row_line(row: StackRow) -> str:
    shown = "open" if row.open else (row.choice if row.choice is not None else "no choice")
    return f"- `{_one_line(row.id)}` {_one_line(row.concern)}: {_one_line(shown)}"


def _stack_concern_line(row: StackRow) -> str:
    return f"- `{_one_line(row.id)}` {_one_line(row.concern)}"


def stack_summary_lines(
    constraints: ConstraintsArtifact, pending_ids: frozenset[str]
) -> list[str]:
    """Plain-text summary lines: every stack row, then open and pending groups."""
    rows = constraints.stack
    if rows is None:
        return [STACK_NOT_RECORDED_LINE]
    if not rows:
        return [STACK_EMPTY_LINE]
    lines = [f"Stack ({len(rows)} row(s)):"]
    lines += [_stack_row_line(row) for row in rows]
    lines += ["", OPEN_CONCERNS_HEADING]
    lines += [_stack_concern_line(row) for row in rows if row.open] or [_NONE_LINE]
    lines += ["", PENDING_CONCERNS_HEADING]
    lines += [_stack_concern_line(row) for row in rows if row.id in pending_ids] or [
        _NONE_LINE
    ]
    return lines


def candidate_stack_summary_lines(
    candidate: ConstraintsArtifact,
    predecessor: ConstraintsArtifact,
    candidate_stores: Iterable[StoreRow],
) -> list[str]:
    """Candidate-review lines: the stack, its delta by row id, and listed hosting/store products.

    Display only: a choice is never compared to a product, and nothing here judges either.
    """
    rows = candidate.stack
    if rows is None:
        lines = [STACK_NOT_RECORDED_LINE]
    else:
        before = {row.id: row for row in predecessor.stack or ()}
        added = [row for row in rows if row.id not in before]
        changed = [row for row in rows if row.id in before and row != before[row.id]]
        opened = [row for row in rows if row.open and not (row.id in before and before[row.id].open)]
        lines = [f"Stack ({len(rows)} row(s)):"] if rows else [STACK_EMPTY_LINE]
        lines += [_stack_row_line(row) for row in rows]
        for heading, group in (
            ("Stack rows added:", added),
            ("Stack rows changed:", changed),
            ("Stack rows opened:", opened),
        ):
            lines += ["", heading]
            lines += [_stack_row_line(row) for row in group] or [_NONE_LINE]
    lines += ["", "Hosting and store products:"]
    products = [
        f"- hosting `{_one_line(row.id)}` {_one_line(row.facet)}: {_one_line(row.product or NO_PRODUCT_MARKER)}"
        for row in candidate.hosting
    ] + [
        f"- store `{_one_line(row.id)}` {_one_line(row.category)}: {_one_line(row.product or NO_PRODUCT_MARKER)}"
        for row in candidate_stores
    ]
    return lines + (products or [_NONE_LINE])
