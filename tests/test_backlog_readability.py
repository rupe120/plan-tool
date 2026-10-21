"""Whether the id guard can read ``BACKLOG.md`` completely.

``tests/test_backlog_ids.py`` asserts that no id opens two entries. That result
is only as good as what the guard can see, so this module checks the
precondition, separately on purpose. It is not a ``BACKLOG.md`` format
validator: a red result here says "the id guard is blind somewhere", not "an id
collided".

It refuses a file in three states, each of which lets a duplicate pass while the
id test stays green:

* a line that looks like an entry opener but is not ``**#N — title**`` (a
  hyphen, an en dash, a colon, ``**#7** — B``, ``**#7 —B**``): its id is
  invisible to the guard;
* a code fence left unclosed to the end of the text: every entry below it is
  skipped;
* no entries found at all: the opener shape changed, and the id test would pass
  on nothing.

Deliberately not checked, each because it is a different and larger check:

* Required fields, scope-contract completeness, ordering, section placement,
  status vocabulary, or any other entry structure.
* Wrapped prose that merely starts with a bolded id (``**#97** build …``): it
  is not an opener, so it is not flagged.
* ``**Closed …**`` records: an id held only there is not guarded (see the id
  module).
* A fence that a later stray closer happens to pair with: CommonMark reads it
  the same way, so the entries between the two are skipped.
* ``BUG_BACKLOG.md`` -- its entries are titled headings with no id.
"""

from __future__ import annotations

import re

import pytest

from plan_tool.scope_fence import _fenced_code_spans
from tests.test_backlog_ids import _BACKLOG, _OPENER_TAIL, _id_lines

# What follows the id on a line that is trying to be an opener but is not one
# (`**#7 - B**`, `**#7: B**`, `**#7** — B`, `**#7 —B**`). A wrapped prose line
# such as `**#97** build (T3), …` starts the same way but is not one.
_DRIFT_RE = re.compile(r"(?:\*\*)?\s*[-–—:]")


def blind_spots(text: str) -> list[str]:
    """Reasons the id guard cannot see every entry id in ``text``; empty when it can."""
    scan = _fenced_code_spans(text)
    lines = _id_lines(text, scan.spans)
    problems: list[str] = []
    if scan.unmatched_opening is not None:
        line = text.count("\n", 0, scan.unmatched_opening) + 1
        problems.append(
            f"line {line}: a code fence never closes, so every line below it is skipped"
        )
    problems.extend(
        f"line {line}: `**#{entry_id}{tail.rstrip()[:30]}` looks like an opener but is "
        "not `**#N — title**`, so its id is not guarded (a wrapped prose line? rewrap it)"
        for line, entry_id, tail in lines
        if not tail.startswith(_OPENER_TAIL) and _DRIFT_RE.match(tail)
    )
    if not any(tail.startswith(_OPENER_TAIL) for _, _, tail in lines):
        problems.append("no `**#N — title**` entry found; the opener shape changed")
    return problems


def test_backlog_is_fully_readable_by_the_id_guard() -> None:
    problems = blind_spots(_BACKLOG.read_text(encoding="utf-8"))
    assert not problems, (
        "the id guard cannot read BACKLOG.md completely, so a duplicate could pass:\n  "
        + "\n  ".join(problems)
    )


class TestBlindSpots:
    """What makes the guard refuse a file instead of passing it silently."""

    def test_a_well_formed_file_has_none(self) -> None:
        assert blind_spots("**#7 — A**\n\n**#8 — B** → promoted to IPPT-1 (x)\n") == []

    @pytest.mark.parametrize(
        "opener",
        ["**#7 - B**", "**#7 – B**", "**#7: B**", "**#7** — B", "**#7 —B**"],
    )
    def test_an_id_line_outside_the_opener_shape_is_flagged(self, opener: str) -> None:
        # Each of these would open an entry the strict shape cannot see, so a
        # duplicate of its id would pass.
        spots = blind_spots(f"**#8 — A**\n\n{opener}\n")
        assert len(spots) == 1 and spots[0].startswith("line 3:"), spots

    def test_only_column_zero_lines_count(self) -> None:
        assert blind_spots("**#8 — A**\n\n- see **#7 - x**\n  **#7: y**\n") == []

    @pytest.mark.parametrize("fence", ["```", "~~~"])
    def test_a_fence_that_never_closes_is_flagged_with_its_line(self, fence: str) -> None:
        # Everything below an unterminated fence is skipped, so a duplicate
        # there would pass.
        spots = blind_spots(f"**#7 — A**\n\n{fence}\n**#7 — B**\n")
        assert spots == ["line 3: a code fence never closes, so every line below it is skipped"]

    def test_a_malformed_line_inside_a_closed_fence_is_not_flagged(self) -> None:
        assert blind_spots("**#7 — A**\n\n```\n**#7 - quoted**\n```\n") == []

    def test_a_malformed_line_after_a_closed_fence_is_still_flagged(self) -> None:
        # The fence exclusion covers the fence only, not everything below it.
        spots = blind_spots("**#8 — A**\n\n```\nx\n```\n**#7 - B**\n")
        assert len(spots) == 1 and spots[0].startswith("line 6:"), spots

    def test_wrapped_prose_starting_with_a_bold_id_is_not_flagged(self) -> None:
        # Hard-wrapped paragraphs in BACKLOG.md's history began a line with
        # `**#97** build …` and `**#210** remains …`; neither is an opener.
        text = (
            "**#8 — A**\n\n"
            "**#97** build (T3), once the authored inventory is drained.\n"
            "**#210** remains passive observation only: the rest.\n"
        )
        assert blind_spots(text) == []

    def test_a_fence_that_never_closes_at_the_very_start_is_flagged_on_line_one(self) -> None:
        # Offset 0 is falsy; the check has to test for None, not truthiness.
        spots = blind_spots("```\nx\n")
        assert spots[0] == "line 1: a code fence never closes, so every line below it is skipped"

    def test_a_file_with_no_entries_is_flagged_so_the_guard_cannot_pass_vacuously(self) -> None:
        assert blind_spots("# Backlog\n\nno entries\n") == [
            "no `**#N — title**` entry found; the opener shape changed"
        ]

    def test_an_inline_code_line_is_not_read_as_an_unclosed_fence(self) -> None:
        # The info-string rule the shared scanner applies: this line is an
        # inline code span, so it neither opens a fence nor hides what follows.
        assert blind_spots("```inline``` wrapped text\n\n**#7 — A**\n") == []
