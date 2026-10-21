"""Characterization tests for the cross-command console / path helpers.

These pin the *current* behavior of the small formatting and filesystem
helpers in ``plan_tool.cli`` so the upcoming "split cli.py into an
intent-grouped package" refactor can relocate them between submodules
without silently changing what they emit. They are deliberately written
against the monolith.

Scope is set by ``tests/cli/COVERAGE_BASELINE.md``: this file adds direct
tests only for helpers the inventory marks as lacking direct coverage
(``indirectly covered`` / ``uncovered``). Helpers already covered directly
elsewhere keep their baseline pointer instead of a duplicate here.

Split-proof conventions (see ``test_package_surface.py``): every symbol
under test is imported from ``plan_tool.cli`` (the package entry point),
and no ``plan_tool.cli`` module global is ever ``monkeypatch.setattr``\\ed
— these are pure helpers, so they are imported and called directly, and
their output is asserted. ``stream=`` overrides (a real argument, not a
patched global) carry the capture.
"""

from __future__ import annotations

import io
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from plan_tool.cli import (
    _atomic_write,
    _common_dir_prefix,
    _fmt_ms,
    _fmt_ms_or_n,
    _format_relative_age,
    _is_within,
    _print_detail_summary,
    _print_next_steps,
    _repo_rel,
    _short_path,
)
from plan_tool.cli.console import render_roadmap_view


class _TTY(io.StringIO):
    def isatty(self) -> bool:
        return True


class TestFmtMs:
    """``_fmt_ms`` picks a unit (ms / s / m) by magnitude; ``None`` → ``-``."""

    def test_none_renders_dash(self) -> None:
        assert _fmt_ms(None) == "-"

    @pytest.mark.parametrize(
        "value, expected",
        [
            (0, "0ms"),
            (1, "1ms"),
            (1.6, "2ms"),  # rounds to nearest ms
            (999, "999ms"),
            (1000, "1.0s"),  # exactly 1s flips to the seconds unit
            (1500, "1.5s"),
            (30000, "30.0s"),
            (60000, "1.0m"),  # exactly 60s flips to the minutes unit
            (90000, "1.5m"),
        ],
    )
    def test_magnitude_units(self, value: float, expected: str) -> None:
        assert _fmt_ms(value) == expected


class TestFmtMsOrN:
    """``_fmt_ms_or_n`` shows ``n=N`` only when the value is suppressed."""

    def test_suppressed_value_with_samples_shows_count(self) -> None:
        assert _fmt_ms_or_n(None, 3) == "n=3"

    def test_suppressed_value_with_no_samples_falls_back_to_dash(self) -> None:
        assert _fmt_ms_or_n(None, 0) == "-"

    def test_present_value_renders_normally_regardless_of_count(self) -> None:
        assert _fmt_ms_or_n(500, 0) == "500ms"
        assert _fmt_ms_or_n(500, 9) == "500ms"


class TestIsWithin:
    def test_descendant_is_within(self, tmp_path: Path) -> None:
        assert _is_within(tmp_path / "a" / "b.md", tmp_path) is True

    def test_self_is_within(self, tmp_path: Path) -> None:
        assert _is_within(tmp_path, tmp_path) is True

    def test_sibling_is_not_within(self, tmp_path: Path) -> None:
        (tmp_path / "root").mkdir()
        (tmp_path / "other").mkdir()
        assert _is_within(tmp_path / "other" / "x", tmp_path / "root") is False


class TestShortPath:
    def test_none_repo_root_returns_str(self, tmp_path: Path) -> None:
        p = tmp_path / "a" / "b.md"
        assert _short_path(p, None) == str(p)

    def test_path_under_root_is_repo_relative(self, tmp_path: Path) -> None:
        p = tmp_path / "plans" / "1-demo.md"
        assert _short_path(p, tmp_path) == str(Path("plans") / "1-demo.md")

    def test_path_outside_root_returns_original_str(self, tmp_path: Path) -> None:
        root = tmp_path / "repo"
        root.mkdir()
        outside = tmp_path / "elsewhere" / "x.md"
        assert _short_path(outside, root) == str(outside)


class TestCommonDirPrefix:
    def test_empty_list_returns_none(self) -> None:
        assert _common_dir_prefix([]) is None

    def test_single_path_returns_its_parent(self, tmp_path: Path) -> None:
        p = tmp_path / "detail" / "1.md"
        assert _common_dir_prefix([p]) == tmp_path / "detail"

    def test_shared_parent_is_returned(self, tmp_path: Path) -> None:
        d = tmp_path / "detail"
        assert _common_dir_prefix([d / "1.md", d / "2.md"]) == d

    def test_divergent_parents_return_none(self, tmp_path: Path) -> None:
        paths = [tmp_path / "a" / "1.md", tmp_path / "b" / "2.md"]
        assert _common_dir_prefix(paths) is None


class TestFormatRelativeAge:
    """Bucketed age string for an ISO-8601 UTC timestamp.

    ``now()`` is real (the helper imports ``datetime`` locally, so it
    isn't a patchable cli global). Buckets are exercised with values far
    enough from each boundary that sub-second test latency can't tip them.
    """

    @staticmethod
    def _z(delta: timedelta) -> str:
        ts = datetime.now(timezone.utc) - delta
        return ts.strftime("%Y-%m-%dT%H:%M:%SZ")

    def test_seconds_bucket(self) -> None:
        result = _format_relative_age(self._z(timedelta(seconds=30)))
        assert re.fullmatch(r"\d+s ago", result)
        # The Z-format floors the timestamp to the whole second, so the
        # measured delta can land a touch above 30; allow a small margin.
        assert 29 <= int(result[: -len("s ago")]) <= 31

    def test_minutes_bucket(self) -> None:
        assert _format_relative_age(self._z(timedelta(minutes=5))) == "5m ago"

    def test_hours_bucket(self) -> None:
        assert _format_relative_age(self._z(timedelta(hours=3))) == "3h ago"

    def test_days_bucket(self) -> None:
        # >= 48h crosses into the days bucket.
        assert _format_relative_age(self._z(timedelta(days=5))) == "5d ago"

    def test_naive_isoformat_without_z_is_accepted(self) -> None:
        ts = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
        assert _format_relative_age(ts) == "2m ago"

    def test_malformed_timestamp_returns_input(self) -> None:
        assert _format_relative_age("not-a-timestamp") == "not-a-timestamp"

    def test_future_timestamp_returns_input(self) -> None:
        future = (datetime.now(timezone.utc) + timedelta(minutes=1)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        assert _format_relative_age(future) == future


class TestAtomicWrite:
    def test_writes_body(self, tmp_path: Path) -> None:
        target = tmp_path / "out.txt"
        _atomic_write(target, "hello\nworld\n")
        assert target.read_text(encoding="utf-8") == "hello\nworld\n"

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        target = tmp_path / "out.txt"
        target.write_text("old", encoding="utf-8")
        _atomic_write(target, "new")
        assert target.read_text(encoding="utf-8") == "new"

    def test_leaves_no_temp_sibling_behind(self, tmp_path: Path) -> None:
        target = tmp_path / "out.txt"
        _atomic_write(target, "body")
        leftovers = [p.name for p in tmp_path.iterdir() if p.name != "out.txt"]
        assert leftovers == []


class TestRepoRel:
    """``_repo_rel`` — POSIX repo-relative form, absolute ``str`` fallback.

    Genuinely uncovered before this test: ``COVERAGE_BASELINE.md`` had
    conflated it with ``plan_tool.detail._repo_relative`` (a distinct
    function). The baseline row is corrected alongside this file.
    """

    def test_path_under_root_is_posix_relative(self, tmp_path: Path) -> None:
        p = tmp_path / "plans" / "1-demo.md"
        assert _repo_rel(p, tmp_path) == "plans/1-demo.md"

    def test_path_outside_root_returns_original_str(self, tmp_path: Path) -> None:
        root = tmp_path / "repo"
        root.mkdir()
        outside = tmp_path / "elsewhere" / "x.md"
        assert _repo_rel(outside, root) == str(outside)


class TestPrintNextSteps:
    def test_empty_steps_emits_nothing(self) -> None:
        out = io.StringIO()
        _print_next_steps("Next steps:", [], stream=out)
        assert out.getvalue() == ""

    def test_renders_title_and_aligned_commands(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PLAN_TOOL_FORCE_COLOR", raising=False)
        out = io.StringIO()
        _print_next_steps(
            "Next steps:",
            [
                ("plan-tool detail my-plan", "author per-step detail files"),
                ("plan-tool run my-plan", "execute step 1"),
            ],
            stream=out,
        )
        text = out.getvalue()
        assert "Next steps:" in text
        assert "# author per-step detail files" in text
        assert "# execute step 1" in text
        # The longest command sets the column; every '#' aligns under it.
        hash_columns = {line.index("#") for line in text.splitlines() if "#" in line}
        assert len(hash_columns) == 1


class TestRenderRoadmapView:
    def test_summary_uses_its_own_banner_title(self) -> None:
        text = render_roadmap_view("summary", "roadmap: demo", stream=io.StringIO())

        assert text.startswith("Roadmap view · Roadmap summary\n")

    def test_plain_output_has_a_named_banner_and_no_ansi(self) -> None:
        body = "roadmap: demo (mode: current)\nsettled:\n  (none)"
        text = render_roadmap_view("ledger", body, stream=io.StringIO())

        assert text.startswith("Roadmap view · Decision ledger\n")
        assert "─" * 60 in text
        assert text.endswith(body)
        assert "\033[" not in text

    def test_tty_output_styles_semantic_roadmap_concepts(self) -> None:
        body = "\n".join(
            [
                "roadmap: demo (mode: review)",
                "artifact status: absent: 04-roadmap.md",
                "settled:",
                "pending:",
                "  - Resolve the open question.",
                "⚠ undefined: entity-missing",
            ]
        )
        text = render_roadmap_view("ledger", body, stream=_TTY())

        assert "\033[1;36mRoadmap view · Decision ledger\033[0m" in text
        assert "\033[1;32msettled:\033[0m" in text
        assert "\033[1;33mpending:\033[0m" in text
        assert "\033[1;33m⚠ undefined: entity-missing\033[0m" in text


class TestPrintDetailSummary:
    def test_multiple_files_factor_a_common_prefix(self, tmp_path: Path) -> None:
        detail_dir = tmp_path / "plans" / "detail"
        wrote = [(1, detail_dir / "1.md"), (2, detail_dir / "2.md")]
        out = io.StringIO()
        _print_detail_summary(
            slug="my-plan",
            wrote=wrote,
            skipped=[],
            rc=0,
            repo_root=tmp_path,
            stream=out,
        )
        text = out.getvalue()
        assert "plan-tool detail · my-plan" in text
        assert "wrote 2 detail file(s) in plans/detail/" in text
        assert "1. 1.md" in text
        assert "2. 2.md" in text
        assert "─" * 60 in text

    def test_single_file_lists_the_short_path(self, tmp_path: Path) -> None:
        p = tmp_path / "plans" / "detail" / "1.md"
        out = io.StringIO()
        _print_detail_summary(
            slug="solo",
            wrote=[(1, p)],
            skipped=[],
            rc=0,
            repo_root=tmp_path,
            stream=out,
        )
        text = out.getvalue()
        assert "wrote 1 detail file(s):" in text
        assert "plans/detail/1.md" in text

    def test_nonzero_rc_marks_errors(self, tmp_path: Path) -> None:
        out = io.StringIO()
        _print_detail_summary(
            slug="oops",
            wrote=[(1, tmp_path / "1.md")],
            skipped=[],
            rc=1,
            repo_root=tmp_path,
            stream=out,
        )
        assert "wrote (with errors)" in out.getvalue()

    def test_skipped_steps_render_as_subblock(self, tmp_path: Path) -> None:
        out = io.StringIO()
        _print_detail_summary(
            slug="part",
            wrote=[],
            skipped=[(3, "no changes detected")],
            rc=0,
            repo_root=tmp_path,
            stream=out,
        )
        text = out.getvalue()
        assert "skipped 1 step(s):" in text
        assert "step 3: no changes detected" in text

    def test_skipped_steps_group_identical_reasons(self, tmp_path: Path) -> None:
        out = io.StringIO()
        reason = "already exists (user declined replace; pass --force …)"
        _print_detail_summary(
            slug="part",
            wrote=[],
            skipped=[(1, reason), (2, reason), (4, reason)],
            rc=0,
            repo_root=tmp_path,
            stream=out,
        )
        text = out.getvalue()
        assert "skipped 3 step(s):" in text
        # One grouped line lists all three ids, not three repeated reasons.
        assert f"steps 1, 2, 4: {reason}" in text
        assert text.count(reason) == 1
