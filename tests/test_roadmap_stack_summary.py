"""Tests for the single producer of the stack summary."""

from __future__ import annotations

import re
from pathlib import Path

from plan_tool import roadmap_stack_summary
from plan_tool.roadmap_artifacts import (
    ConstraintsArtifact,
    DecisionRow,
    DecisionStatus,
    HostingRow,
    StackRow,
    StoreRow,
)
from plan_tool.roadmap_stack_summary import (
    NO_PRODUCT_MARKER,
    OPEN_CONCERNS_HEADING,
    PENDING_CONCERNS_HEADING,
    STACK_EMPTY_LINE,
    STACK_NOT_RECORDED_LINE,
    candidate_stack_summary_lines,
    pending_anchor_ids,
    stack_summary_lines,
)


def _constraints(stack) -> ConstraintsArtifact:
    return ConstraintsArtifact(
        dispositions=(), constraints=(), decisions=(), body="", stack=stack
    )


def _decision(anchor: str, status: DecisionStatus = DecisionStatus.PENDING) -> DecisionRow:
    return DecisionRow(
        id=f"decision-{anchor}",
        chosen_option="x",
        rejected_alternatives=(),
        rationale="r",
        anchor=anchor,
        status=status,
    )


CHOSEN = StackRow(id="stack-1", concern="platform", choice="AWS Lambda")
OPEN = StackRow(id="stack-2", concern="store-engine", open=True)


def _group(lines: list[str], heading: str) -> list[str]:
    group = []
    for line in lines[lines.index(heading) + 1 :]:
        if not line.startswith("- "):
            break
        group.append(line)
    return group


def test_not_recorded_stack_prints_not_recorded_not_empty():
    lines = stack_summary_lines(_constraints(None), frozenset())
    assert lines == [STACK_NOT_RECORDED_LINE]
    assert STACK_NOT_RECORDED_LINE != STACK_EMPTY_LINE


def test_empty_stack_prints_present_but_empty():
    assert stack_summary_lines(_constraints(()), frozenset()) == [STACK_EMPTY_LINE]


def test_every_row_is_listed_in_source_order():
    lines = stack_summary_lines(_constraints((CHOSEN, OPEN)), frozenset())
    assert lines[1] == "- `stack-1` platform: AWS Lambda"
    assert lines[2] == "- `stack-2` store-engine: open"


def test_open_and_pending_concerns_are_listed_separately():
    lines = stack_summary_lines(_constraints((CHOSEN, OPEN)), frozenset({"stack-1"}))
    assert _group(lines, "Open concerns:") == ["- `stack-2` store-engine"]
    assert _group(lines, "Pending concerns:") == ["- `stack-1` platform"]


def test_row_both_open_and_pending_appears_in_both_groups():
    lines = stack_summary_lines(_constraints((OPEN,)), frozenset({"stack-2"}))
    assert _group(lines, "Open concerns:") == ["- `stack-2` store-engine"]
    assert _group(lines, "Pending concerns:") == ["- `stack-2` store-engine"]


def test_empty_groups_keep_their_heading_and_say_none():
    lines = stack_summary_lines(_constraints((CHOSEN,)), frozenset())
    assert _group(lines, "Open concerns:") == ["- none"]
    assert _group(lines, "Pending concerns:") == ["- none"]


def test_unknown_concern_and_duplicate_id_print_as_stored():
    rows = (
        StackRow(id="stack-1", concern="not-a-known-concern", choice="a"),
        StackRow(id="stack-1", concern="platform", choice="b"),
    )
    lines = stack_summary_lines(_constraints(rows), frozenset())
    assert "- `stack-1` not-a-known-concern: a" in lines
    assert "- `stack-1` platform: b" in lines


def test_settled_decision_is_not_pending_and_groups_union_both_artifacts():
    pending = pending_anchor_ids(
        [_decision("stack-1", DecisionStatus.SETTLED)], [_decision("stack-2")]
    )
    assert pending == frozenset({"stack-2"})


def test_producer_imports_only_the_artifacts_leaf():
    source = Path(roadmap_stack_summary.__file__).read_text()
    imported = re.findall(r"^\s*(?:from|import)\s+(plan_tool[\w.]*)", source, re.MULTILINE)
    assert imported == ["plan_tool.roadmap_artifacts"]
    assert "roadmap_candidate_narrative" not in source


def _constraints_with(stack, hosting=()) -> ConstraintsArtifact:
    return ConstraintsArtifact(
        dispositions=(), constraints=(), decisions=(), body="", stack=stack, hosting=tuple(hosting)
    )


def test_candidate_lines_list_added_changed_and_opened_stack_rows():
    predecessor = _constraints_with(
        (
            StackRow(id="stack-1", concern="platform", choice="AWS Lambda"),
            StackRow(id="stack-2", concern="store-engine", open=True),
            StackRow(id="stack-3", concern="runtime", choice="python"),
        )
    )
    candidate = _constraints_with(
        (
            StackRow(id="stack-1", concern="platform", choice="ECS"),
            StackRow(id="stack-2", concern="store-engine", choice="postgres"),
            StackRow(id="stack-3", concern="runtime", open=True),
            StackRow(id="stack-4", concern="queue", choice="sqs"),
        )
    )
    lines = candidate_stack_summary_lines(candidate, predecessor, ())
    added = _group(lines, "Stack rows added:")
    changed = _group(lines, "Stack rows changed:")
    opened = _group(lines, "Stack rows opened:")
    assert len(added) == 1 and "stack-4" in added[0]
    assert len(changed) == 3  # an open row that became chosen counts as changed
    assert len(opened) == 1 and "stack-3" in opened[0]


def test_candidate_without_stack_collection_prints_stack_not_recorded():
    lines = candidate_stack_summary_lines(_constraints_with(None), _constraints_with(None), ())
    assert lines[0] == STACK_NOT_RECORDED_LINE
    assert STACK_EMPTY_LINE not in lines


def test_predecessor_without_stack_makes_every_candidate_row_an_add():
    lines = candidate_stack_summary_lines(
        _constraints_with((CHOSEN, OPEN)), _constraints_with(None), ()
    )
    assert len(_group(lines, "Stack rows added:")) == 2
    assert _group(lines, "Stack rows changed:") == ["- none"]


def test_hosting_and_store_products_are_listed_verbatim_with_explicit_none_marker():
    hosting = (
        HostingRow(id="hosting-1", facet="model", value="serverless"),
        HostingRow(id="hosting-2", facet="topology", value="multi-region", product="AWS Lambda"),
    )
    stores = (StoreRow(id="store-1", category="relational", sharing="shared", product="Postgres"),)
    lines = candidate_stack_summary_lines(
        _constraints_with((), hosting), _constraints_with(()), stores
    )
    products = _group(lines, "Hosting and store products:")
    assert any("hosting-1" in line and NO_PRODUCT_MARKER in line for line in products)
    assert any("hosting-2" in line and line.endswith("AWS Lambda") for line in products)
    assert any("store-1" in line and line.endswith("Postgres") for line in products)


def test_summary_displays_and_never_compares_a_choice_to_a_product():
    """A choice differing from a store product yields the same line shapes as one that matches."""

    def render(choice: str) -> list[str]:
        stack = (StackRow(id="stack-1", concern="store-engine", choice=choice),)
        stores = (StoreRow(id="store-1", category="relational", sharing="shared", product="Postgres"),)
        return candidate_stack_summary_lines(
            _constraints_with(stack), _constraints_with(stack), stores
        )

    def masked(lines: list[str]) -> list[str]:
        return [line.replace("Postgres", "X").replace("MySQL", "X") for line in lines]

    matching, differing = render("Postgres"), render("MySQL")
    assert masked(matching) == masked(differing)
    assert not any(w in " ".join(differing).lower() for w in ("mismatch", "conflict", "recommend"))


def test_a_multi_line_choice_stays_on_one_line_and_cannot_start_a_heading() -> None:
    """``choice`` is free model text; the summary lands in INDEX.md and the terminal,
    so an embedded newline must not forge a heading or list item there."""
    row = StackRow("stack-engine", "store-engine", choice="Postgres\n## Versions\n| fake | row |")
    constraints = ConstraintsArtifact(
        dispositions=(), constraints=(), decisions=(), body="b", stack=(row,)
    )

    lines = stack_summary_lines(constraints, frozenset())

    assert all("\n" not in line for line in lines)
    assert not any(line.startswith("## ") or line.startswith("| ") for line in lines)
    assert "- `stack-engine` store-engine: Postgres ## Versions | fake | row |" in lines


def test_ids_and_concerns_on_every_summary_line_are_collapsed_to_one_line() -> None:
    """Pass 3: the id and concern are model text too; the open and pending groups
    printed them raw, so a newline in either could forge a heading in INDEX.md."""
    row = StackRow("stack-x\n## Versions", "plat\n## form", open=True)
    constraints = ConstraintsArtifact(
        dispositions=(), constraints=(), decisions=(), body="b", stack=(row,)
    )

    lines = stack_summary_lines(constraints, frozenset({row.id}))

    assert all("\n" not in line for line in lines)
    assert not any(line.startswith("## ") for line in lines)
    assert lines.count("- `stack-x ## Versions` plat ## form") == 2


def test_each_group_heading_follows_a_blank_line_so_a_markdown_viewer_keeps_the_groups_apart() -> None:
    """INDEX.md embeds these lines; a heading directly after a bullet is a lazy
    continuation of that bullet in CommonMark and merges the groups into one list."""
    constraints = ConstraintsArtifact(
        dispositions=(),
        constraints=(),
        decisions=(),
        body="b",
        stack=(StackRow("stack-1", "platform", open=True),),
    )

    lines = stack_summary_lines(constraints, frozenset())

    for heading in (OPEN_CONCERNS_HEADING, PENDING_CONCERNS_HEADING):
        assert lines[lines.index(heading) - 1] == ""
