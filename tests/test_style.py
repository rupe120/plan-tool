"""Tests for plan_tool.style.

Color is gated on a real TTY plus ``NO_COLOR`` / ``PLAN_TOOL_FORCE_COLOR``.
Tests write to ``io.StringIO`` (non-TTY) so the default path is plain text —
this is the contract the rest of the suite relies on when it greps for bare
``warning:`` / ``error:`` prefixes in captured output.
"""

from __future__ import annotations

import io

import pytest

from plan_tool import style
from plan_tool.schema import ChangeType


class _TTY(io.StringIO):
    def isatty(self) -> bool:
        return True


class TestColorEnabled:
    def test_off_for_non_tty(self) -> None:
        assert style.color_enabled(io.StringIO()) is False

    def test_on_for_tty(self) -> None:
        assert style.color_enabled(_TTY()) is True

    def test_no_color_wins_over_tty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.delenv("PLAN_TOOL_FORCE_COLOR", raising=False)
        assert style.color_enabled(_TTY()) is False

    def test_force_color_wins_over_non_tty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_FORCE_COLOR", "1")
        assert style.color_enabled(io.StringIO()) is True


class TestPaint:
    def test_wraps_when_enabled(self) -> None:
        assert style.paint("x", style.RED, enabled=True) == f"{style.RED}x{style.RESET}"

    def test_passthrough_when_disabled(self) -> None:
        assert style.paint("x", style.RED, enabled=False) == "x"


class TestDiagnosticHelpers:
    """Plain-mode wording must stay byte-identical to the old hand-rolled prints."""

    def test_warn_plain(self) -> None:
        buf = io.StringIO()
        style.warn("disk is full", stream=buf)
        assert buf.getvalue() == "warning: disk is full\n"

    def test_error_plain(self) -> None:
        buf = io.StringIO()
        style.error("boom", stream=buf)
        assert buf.getvalue() == "error: boom\n"

    def test_info_plain(self) -> None:
        buf = io.StringIO()
        style.info("heads up", stream=buf)
        assert buf.getvalue() == "info: heads up\n"

    def test_note_plain(self) -> None:
        buf = io.StringIO()
        style.note("by the way", stream=buf)
        assert buf.getvalue() == "note: by the way\n"

    def test_tool_plain_no_level(self) -> None:
        buf = io.StringIO()
        style.tool("retrying once", stream=buf)
        assert buf.getvalue() == "plan-tool: retrying once\n"

    def test_tool_plain_with_level(self) -> None:
        buf = io.StringIO()
        style.tool("dropped a step", level="warning", stream=buf)
        assert buf.getvalue() == "plan-tool: warning: dropped a step\n"

    def test_success_plain(self) -> None:
        buf = io.StringIO()
        style.success("created plans/x.md", stream=buf)
        assert buf.getvalue() == "✓ created plans/x.md\n"

    def test_detail_plain(self) -> None:
        buf = io.StringIO()
        style.detail("added to manifest", stream=buf)
        assert buf.getvalue() == "  · added to manifest\n"

    def test_change_type_tag_refactor(self) -> None:
        assert style.change_type_tag(ChangeType.REFACTOR) == " [refactor]"

    def test_change_type_tag_feature(self) -> None:
        assert style.change_type_tag(ChangeType.FEATURE) == " [feature]"

    def test_change_type_tag_non_code(self) -> None:
        assert style.change_type_tag(ChangeType.NON_CODE) == " [non-code]"

    def test_change_type_tag_none_empty(self) -> None:
        assert style.change_type_tag(None) == ""

    def test_warn_colored_prefix_only(self) -> None:
        """When styled, only the prefix word carries ANSI; the body stays plain."""
        buf = _TTY()
        style.warn("keep me legible", stream=buf)
        out = buf.getvalue()
        assert out.startswith(style.BOLD_YELLOW + "warning:" + style.RESET)
        assert "keep me legible\n" in out
        # The body must not be wrapped in escapes.
        assert style.RESET + " keep me legible\n" == out[len(style.BOLD_YELLOW + "warning:") :]

    def test_tool_colored_tag_and_level(self) -> None:
        buf = _TTY()
        style.tool("x", level="error", stream=buf)
        out = buf.getvalue()
        # Source tag dimmed, level colored red.
        assert style.DIM + "plan-tool:" + style.RESET in out
        assert style.BOLD_RED + "error:" + style.RESET in out


_DIFF = (
    "--- a/plan.md\n"
    "+++ b/plan.md\n"
    "@@ -8,3 +8,3 @@\n"
    " context before\n"
    "-    status: done\n"
    "+    status: current\n"
    " context after\n"
)


class TestColorizeDiff:
    def test_passthrough_when_color_disabled(self) -> None:
        assert style.colorize_diff(_DIFF, stream=io.StringIO()) == _DIFF

    def test_git_style_coloring(self) -> None:
        out = style.colorize_diff(_DIFF, stream=_TTY())
        assert f"{style.BOLD}--- a/plan.md{style.RESET}\n" in out
        assert f"{style.BOLD}+++ b/plan.md{style.RESET}\n" in out
        assert f"{style.CYAN}@@ -8,3 +8,3 @@{style.RESET}\n" in out
        # The removed/added pair shares a "    status: " prefix, so only the
        # differing word is reverse-highlighted; the line keeps its base hue.
        assert (
            f"{style.RED}-    status: "
            f"{style.REVERSE}done{style.REVERSE_OFF}{style.RESET}\n"
        ) in out
        assert (
            f"{style.GREEN}+    status: "
            f"{style.REVERSE}current{style.REVERSE_OFF}{style.RESET}\n"
        ) in out
        # Context lines stay plain.
        assert "\n context before\n" in out
        assert "\n context after\n" in out

    def test_file_headers_not_painted_as_changes(self) -> None:
        """``---``/``+++`` must take the header style, not red/green."""
        out = style.colorize_diff(_DIFF, stream=_TTY())
        assert style.RED + "---" not in out
        assert style.GREEN + "+++" not in out

    def test_dissimilar_pair_falls_back_to_whole_line(self) -> None:
        """A wholesale rewrite (no shared words) shouldn't reverse-highlight
        the entire line — it stays plain whole-line red/green."""
        out = style.colorize_diff("-old\n+new", stream=_TTY())
        assert out == f"{style.RED}-old{style.RESET}\n{style.GREEN}+new{style.RESET}"
        assert style.REVERSE not in out

    def test_intraline_highlights_only_changed_span(self) -> None:
        """Shared words stay in base color; only the edited word is reversed."""
        out = style.colorize_diff(
            "-the quick brown fox\n+the quick red fox", stream=_TTY()
        )
        assert (
            f"{style.RED}-the quick {style.REVERSE}brown"
            f"{style.REVERSE_OFF} fox{style.RESET}\n"
        ) in out
        assert (
            f"{style.GREEN}+the quick {style.REVERSE}red"
            f"{style.REVERSE_OFF} fox{style.RESET}"
        ) in out

    def test_unpaired_lines_keep_whole_line_color(self) -> None:
        """Two removals + one addition: the extra removal has no partner, so
        it stays whole-line red rather than dropping out of the output."""
        out = style.colorize_diff("-aaa\n-bbb\n+aaa!\n", stream=_TTY())
        # First removal pairs with the addition (shared "aaa" stem).
        assert f"{style.RED}-aaa" in out
        assert f"{style.GREEN}+aaa" in out
        # Second removal is unpaired → plain whole-line red, still present.
        assert f"{style.RED}-bbb{style.RESET}\n" in out

    def test_block_order_preserved(self) -> None:
        """All removals are emitted before all additions, even when paired."""
        out = style.colorize_diff(
            "-line one\n-line two\n+line one!\n+line two!\n", stream=_TTY()
        )
        first_plus = out.index("+")
        last_minus = out.rindex(f"{style.RED}-")
        assert last_minus < first_plus

    def test_missing_trailing_newline_preserved(self) -> None:
        out = style.colorize_diff(
            "-status: done\n+status: current", stream=_TTY()
        )
        # No trailing newline on the final added line.
        assert not out.endswith("\n")
        assert out.endswith(style.RESET)


class TestRenderMarkdownForConsole:
    """Reports are persisted as markdown but displayed console-friendly:
    markers are ALWAYS stripped (an italic-wrapped path breaks terminal
    click-to-open); ANSI styling rides on top only for color streams."""

    def test_heading_hashes_stripped_plain(self) -> None:
        out = style.render_markdown_for_console(
            "## Plan completeness: T\n\n### Conceptual completeness\n",
            stream=io.StringIO(),
        )
        assert "Plan completeness: T" in out
        assert "Conceptual completeness" in out
        assert "#" not in out

    def test_whole_line_italic_keeps_path_clickable(self) -> None:
        md = "_Completeness report saved to /tmp/reports/20260604-completeness.md_"
        out = style.render_markdown_for_console(md, stream=io.StringIO())
        assert out == "Completeness report saved to /tmp/reports/20260604-completeness.md"

    def test_paren_italic_stripped_inline(self) -> None:
        out = style.render_markdown_for_console(
            "- _(none — paths resolve, deps coherent)_",
            stream=io.StringIO(),
        )
        assert out == "- (none — paths resolve, deps coherent)"

    def test_inline_code_and_bold_markers_stripped(self) -> None:
        out = style.render_markdown_for_console(
            "Run `plan-tool detail my-plan` — **not** optional.",
            stream=io.StringIO(),
        )
        assert out == "Run plan-tool detail my-plan — not optional."

    def test_snake_case_and_paths_with_underscores_untouched(self) -> None:
        md = "- WARN: step 1 declared plan_tool/review_walk.py uses step_id"
        out = style.render_markdown_for_console(md, stream=io.StringIO())
        assert out == md

    def test_rule_becomes_drawn_line(self) -> None:
        out = style.render_markdown_for_console("---", stream=io.StringIO())
        assert out == "─" * 60

    def test_fence_content_passes_through_verbatim(self) -> None:
        md = "```\n- HIGH: [slug] _literal_ `markers` stay\n```"
        out = style.render_markdown_for_console(md, stream=io.StringIO())
        assert out == "- HIGH: [slug] _literal_ `markers` stay"

    def test_styling_applied_on_color_stream(self) -> None:
        out = style.render_markdown_for_console(
            "## Heading\n_saved note_\nrun `cmd` now",
            stream=_TTY(),
        )
        assert f"{style.BOLD}Heading{style.RESET}" in out
        assert f"{style.DIM}saved note{style.RESET}" in out
        assert f"{style.CYAN}cmd{style.RESET}" in out
