"""Uniqueness guard for ``BACKLOG.md`` entry ids.

An id is the citation key across seeds, plans, code comments, and commit
messages, so a collision silently changes what a citation refers to instead of
erroring. Ids have collided before (#229, #365/#366, and #404 among them), and
nothing flagged any of them.

The one fact asserted is that no id opens two entries. Whether this guard can
see the whole file is a different question, checked on purpose in its own module,
``tests/test_backlog_readability.py``. Deliberately not checked here, each
because it is a different and larger check:

* ``BUG_BACKLOG.md`` -- its entries are titled headings with no id.
* ``**Closed …**`` records that carry an id, in either shape they have today
  (``**Closed #328 — …**``, ``**Closed (2026-09-16) — #367: …**``); an id held
  only there is not guarded, because guarding it needs a second opener grammar.
* Whether a cited id resolves to a live entry -- closed ids stay cited from
  ``docs/history/backlog-decisions.md``.
* Reuse of an id whose entry was removed -- the file no longer holds it.
* Required fields, scope-contract completeness, ordering, section placement.

Fenced blocks are skipped with the scanner the plan parsers share, so a quoted
example entry is not read as a real one.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from plan_tool.scope_fence import _fenced_code_spans

_BACKLOG = Path(__file__).resolve().parents[1] / "BACKLOG.md"
# Every column-0 `**#N` line. The opener is `**#N — title**`, and a promotion
# stub keeps that opening, so a stub and a live entry sharing an id collide.
_ID_LINE_RE = re.compile(r"^\*\*#(\d+)(.*)$", re.MULTILINE)
_OPENER_TAIL = " — "


def _id_lines(text: str, spans: tuple[tuple[int, int], ...]) -> list[tuple[int, int, str]]:
    """(line, id, tail) for each column-0 ``**#N`` line outside a code fence."""
    return [
        (text.count("\n", 0, match.start()) + 1, int(match.group(1)), match.group(2))
        for match in _ID_LINE_RE.finditer(text)
        if not any(start <= match.start() < end for start, end in spans)
    ]


def duplicate_entry_ids(text: str) -> dict[int, list[tuple[int, str]]]:
    """Ids that open more than one entry, each with (line number, title)."""
    seen: dict[int, list[tuple[int, str]]] = {}
    for line, entry_id, tail in _id_lines(text, _fenced_code_spans(text).spans):
        if tail.startswith(_OPENER_TAIL):
            title = tail[len(_OPENER_TAIL):].split("**", 1)[0].strip()
            seen.setdefault(entry_id, []).append((line, title))
    return {entry_id: rows for entry_id, rows in seen.items() if len(rows) > 1}


def _explain(duplicates: dict[int, list[tuple[int, str]]]) -> str:
    rows = "\n".join(
        f"  #{entry_id}: " + "; ".join(f"line {line} ({title})" for line, title in found)
        for entry_id, found in sorted(duplicates.items())
    )
    return (
        f"BACKLOG.md ids open more than one entry:\n{rows}\n"
        "The entry cited elsewhere keeps its id; with equal citations the one "
        "filed later moves to the next number above the highest ever used "
        '(docs/TRACKING.md § "Adding a new entry"). If a line is wrapped prose '
        "that happens to start `**#N — `, rewrap it instead."
    )


def test_backlog_entry_ids_are_unique() -> None:
    duplicates = duplicate_entry_ids(_BACKLOG.read_text(encoding="utf-8"))
    assert not duplicates, _explain(duplicates)


class TestDuplicateEntryIds:
    """The duplicate finder, on synthetic text."""

    def test_two_entries_sharing_an_id_are_reported_with_their_lines(self) -> None:
        text = "**#7 — First**\n\nbody\n\n**#7 — Second**\n"
        assert duplicate_entry_ids(text) == {7: [(1, "First"), (5, "Second")]}

    def test_distinct_ids_report_nothing(self) -> None:
        assert duplicate_entry_ids("**#7 — A**\n\n**#8 — B**\n") == {}

    def test_a_promotion_stub_still_claims_its_id(self) -> None:
        # The stub keeps the id so citations resolve; a live entry that reuses
        # it would make those citations ambiguous, so the pair must collide.
        text = "**#7 — A** → promoted to IPPT-1 (2026-09-23)\n\n**#7 — B**\n"
        assert set(duplicate_entry_ids(text)) == {7}

    def test_a_mid_line_or_indented_mention_is_not_an_entry(self) -> None:
        # Entry bodies cite other entries; only a line-start opener is an entry.
        text = "**#7 — A**\n\n- see **#7 — A** above\n  **#7 — quoted**\n"
        assert duplicate_entry_ids(text) == {}

    def test_a_fenced_example_entry_is_not_an_entry(self) -> None:
        # The carve-out: fenced text is quoted, not filed. Removing the fence
        # exclusion turns this red.
        for fence in ("```", "~~~"):
            text = f"**#7 — A**\n\n{fence}markdown\n**#7 — example**\n{fence}\n"
            assert duplicate_entry_ids(text) == {}, fence

    def test_text_after_a_closed_fence_is_still_checked(self) -> None:
        # The exclusion covers the fence only, not everything below it.
        text = "```\nx\n```\n**#7 — A**\n\n**#7 — B**\n"
        assert set(duplicate_entry_ids(text)) == {7}

    def test_an_inline_code_line_is_not_a_fence_and_hides_nothing(self) -> None:
        # CommonMark: a backtick fence's info string cannot contain a backtick,
        # so this line is an inline code span. Reading it as an opener would
        # flip fence parity and hide every entry below it.
        text = "```inline``` wrapped text\n\n**#7 — A**\n\n**#7 — B**\n"
        assert set(duplicate_entry_ids(text)) == {7}

    @pytest.mark.parametrize(
        "record",
        ["**Closed #328 — B**", "**Closed (2026-09-16) — #328: B**"],
    )
    def test_a_closed_record_line_is_not_an_opener_a_known_residual(self, record: str) -> None:
        # Deliberately unguarded: `**Closed …**` records carry an id in
        # irregular shapes, and guarding them needs a second opener grammar.
        assert duplicate_entry_ids(f"**#328 — A**\n\n{record}\n") == {}

    def test_a_malformed_opener_is_not_read_as_an_entry(self) -> None:
        # This finder reads only well-formed openers. A malformed one is the
        # readability module's concern (tests/test_backlog_readability.py), not
        # a duplicate.
        assert duplicate_entry_ids("**#7 — A**\n\n**#7 - B**\n") == {}

    def test_wrapped_prose_starting_with_a_bold_id_is_not_an_entry(self) -> None:
        # Hard-wrapped paragraphs in BACKLOG.md's history began a line with
        # `**#97** build …` and `**#210** remains …`; neither is an opener.
        text = (
            "**#8 — A**\n\n"
            "**#97** build (T3), once the authored inventory is drained.\n"
            "**#210** remains passive observation only: the rest.\n"
        )
        assert duplicate_entry_ids(text) == {}

    def test_a_stub_title_stops_at_the_bold_close(self) -> None:
        text = "**#7 — A** → promoted to IPPT-1 (2026-09-23)\n\n**#7 — B**\n"
        assert duplicate_entry_ids(text) == {7: [(1, "A"), (3, "B")]}


class TestFailureMessage:
    """The text an operator reads when the guard fails."""

    def test_it_names_each_id_line_and_title_and_says_who_keeps_the_id(self) -> None:
        text = "**#7 — A** → promoted to IPPT-1 (2026-09-23)\n\n**#7 — B**\n"
        message = _explain(duplicate_entry_ids(text))
        assert "#7: line 1 (A); line 3 (B)" in message
        assert "promoted" not in message  # a stub's pointer is not part of its title
        assert "cited elsewhere keeps its id" in message
        assert "rewrap" in message  # the way out when the second line is wrapped prose
