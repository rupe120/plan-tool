"""Shared ANSI styling helpers. Minimal and dependency-free.

Color is on only for real TTYs (so piped/captured output stays plain),
off when ``NO_COLOR`` is set; ``PLAN_TOOL_FORCE_COLOR`` forces it on for
demos. This mirrors the gate ``review_walk`` applies to its own output —
both honor the same three env/TTY signals so the tool behaves uniformly.

Callers pass the stream they actually write to (stderr for progress,
stdout for results) so the TTY check matches the real destination.
"""

from __future__ import annotations

import difflib
import os
import re
import sys
from typing import TYPE_CHECKING, Optional, TextIO

if TYPE_CHECKING:
    from plan_tool.schema import ChangeType

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BOLD_RED = "\033[1;31m"
BOLD_GREEN = "\033[1;32m"
BOLD_YELLOW = "\033[1;33m"
BOLD_CYAN = "\033[1;36m"
# Reverse-video on/off. Used to spotlight the changed *spans* inside a
# removed/added diff line while the rest of the line keeps its base
# red/green — toggled off (``\033[27m``) rather than full-RESET so the
# surrounding line color survives across a highlighted span.
REVERSE = "\033[7m"
REVERSE_OFF = "\033[27m"


def color_enabled(stream: Optional[TextIO] = None) -> bool:
    """True when ``stream`` (default stdout) should carry ANSI styling."""
    if os.environ.get("PLAN_TOOL_FORCE_COLOR"):
        return True
    if os.environ.get("NO_COLOR"):
        return False
    s = stream if stream is not None else sys.stdout
    try:
        return bool(s.isatty())
    except Exception:
        return False


def paint(text: str, style: str, *, enabled: bool) -> str:
    """Wrap ``text`` in ``style`` (and a reset) when ``enabled``, else return as-is."""
    return f"{style}{text}{RESET}" if enabled else text


# --- Diagnostic line helpers ------------------------------------------------
#
# One place owns the prefix wording + color + target stream for every
# diagnostic the tool emits, so ``warning:`` looks the same whether it comes
# from ``create``, ``run``, or the launcher. The prefix word is the only
# colored span; the body is left plain so paths/identifiers stay legible.
# In plain mode (non-TTY / ``NO_COLOR``) the output is byte-identical to the
# old hand-rolled ``print(f"warning: {x}")`` form, so existing greps/tests
# that match the bare prefix keep working.


def _emit_prefixed(prefix: str, prefix_style: str, body: str, stream: TextIO) -> None:
    head = paint(prefix, prefix_style, enabled=color_enabled(stream))
    print(f"{head} {body}" if body else head, file=stream)


def warn(body: str, *, stream: Optional[TextIO] = None) -> None:
    """``warning: <body>`` (yellow prefix); stderr by default."""
    _emit_prefixed("warning:", BOLD_YELLOW, body, stream or sys.stderr)


def error(body: str, *, stream: Optional[TextIO] = None) -> None:
    """``error: <body>`` (red prefix); stderr by default."""
    _emit_prefixed("error:", BOLD_RED, body, stream or sys.stderr)


def info(body: str, *, stream: Optional[TextIO] = None) -> None:
    """``info: <body>`` (cyan prefix); stderr by default."""
    _emit_prefixed("info:", BOLD_CYAN, body, stream or sys.stderr)


def note(body: str, *, stream: Optional[TextIO] = None) -> None:
    """``note: <body>`` (dim prefix, for low-key advisories); stderr by default."""
    _emit_prefixed("note:", DIM, body, stream or sys.stderr)


# Level word → style for the ``plan-tool:``-namespaced helper below.
_TOOL_LEVELS = {
    "warning": BOLD_YELLOW,
    "error": BOLD_RED,
    "note": DIM,
    "info": BOLD_CYAN,
}


def tool(body: str, *, level: Optional[str] = None, stream: Optional[TextIO] = None) -> None:
    """``plan-tool: [level:] <body>`` for library-level messages.

    The ``plan-tool:`` source tag is dimmed; an optional ``level``
    (``warning``/``error``/``note``/``info``) is colored like the bare
    helpers. Library functions (e.g. ``create``'s claude-call retries) use
    this so their lines are recognizable when they sit beside other output.
    """
    s = stream or sys.stderr
    color = color_enabled(s)
    head = paint("plan-tool:", DIM, enabled=color)
    if level is not None:
        head += " " + paint(f"{level}:", _TOOL_LEVELS.get(level, DIM), enabled=color)
    print(f"{head} {body}", file=s)


def success(body: str, *, mark: str = "✓", stream: Optional[TextIO] = None) -> None:
    """Green ``✓ <body>`` headline; stdout by default."""
    s = stream or sys.stdout
    color = color_enabled(s)
    print(
        f"{paint(mark, BOLD_GREEN, enabled=color)} "
        f"{paint(body, BOLD_GREEN, enabled=color)}",
        file=s,
    )


# A diff line is split into word/whitespace runs for intra-line diffing,
# keeping whitespace as its own token so the rebuilt line is byte-exact.
_DIFF_WORD_RE = re.compile(r"\s+|\S+")
# Below this token-similarity, a removed/added pair is treated as two
# unrelated lines (whole-line red/green) rather than an edit — otherwise a
# wholesale rewrite reverse-highlights the entire line, which is just noise.
_INTRALINE_MIN_RATIO = 0.3


def _intraline_pair(old_body: str, new_body: str) -> Optional[tuple[str, str]]:
    """Word-level highlight of one removed/added line pair.

    Returns ``(styled_old, styled_new)`` — each the full line (leading
    ``-``/``+`` included) in its base red/green, with only the changed
    word spans reverse-highlighted so the eye lands on what actually
    differs. Returns ``None`` when the two lines are too dissimilar to
    read as an edit; the caller then colors each whole-line, matching the
    pre-intraline behavior. Neither return value carries the line ending.
    """
    o_toks = _DIFF_WORD_RE.findall(old_body[1:])  # drop the -/+ marker
    n_toks = _DIFF_WORD_RE.findall(new_body[1:])
    sm = difflib.SequenceMatcher(a=o_toks, b=n_toks, autojunk=False)
    if sm.ratio() < _INTRALINE_MIN_RATIO:
        return None
    o_out = [RED + old_body[:1]]
    n_out = [GREEN + new_body[:1]]
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        o_seg = "".join(o_toks[i1:i2])
        n_seg = "".join(n_toks[j1:j2])
        if tag == "equal":
            o_out.append(o_seg)
            n_out.append(n_seg)
        else:
            # Reverse-highlight the changed span, then toggle reverse back
            # off so the rest of the line stays plain red/green.
            if o_seg:
                o_out.append(f"{REVERSE}{o_seg}{REVERSE_OFF}")
            if n_seg:
                n_out.append(f"{REVERSE}{n_seg}{REVERSE_OFF}")
    return "".join(o_out) + RESET, "".join(n_out) + RESET


def colorize_diff(diff_text: str, *, stream: Optional[TextIO] = None) -> str:
    """Apply git-style ANSI coloring to a unified diff.

    Bold file headers (``---``/``+++``), cyan hunk headers (``@@``), red
    removals, green additions; context lines stay plain. Within a
    contiguous removed-then-added block, paired lines are additionally
    word-diffed so the *changed spans* are reverse-highlighted over the
    base red/green — the whole-line color says "this line changed", the
    highlight says "this is the text that changed". Returns ``diff_text``
    unchanged when color is disabled for ``stream`` (default stdout), so
    piped/captured output is byte-identical to the raw diff.
    """
    if not color_enabled(stream):
        return diff_text

    def split(line: str) -> tuple[str, str]:
        body = line.rstrip("\r\n")
        return body, line[len(body):]

    def emit_change_block(
        out: list[str],
        rem: list[tuple[str, str]],
        add: list[tuple[str, str]],
    ) -> None:
        # Word-diff line k of the removals against line k of the additions
        # (git's positional pairing). Keep the -,-,+,+ block order: compute
        # the styled spans up front, then emit all removals then all adds.
        styled_rem: list[Optional[str]] = [None] * len(rem)
        styled_add: list[Optional[str]] = [None] * len(add)
        for k in range(min(len(rem), len(add))):
            res = _intraline_pair(rem[k][0], add[k][0])
            if res is not None:
                styled_rem[k], styled_add[k] = res
        for k, (body, ending) in enumerate(rem):
            painted = styled_rem[k] or f"{RED}{body}{RESET}"
            out.append(painted + ending)
        for k, (body, ending) in enumerate(add):
            painted = styled_add[k] or f"{GREEN}{body}{RESET}"
            out.append(painted + ending)

    lines = diff_text.splitlines(keepends=True)
    out: list[str] = []
    i, n = 0, len(lines)
    while i < n:
        body, ending = split(lines[i])
        # File headers before removals/additions: ``---``/``+++`` would
        # otherwise match the single-char ``-``/``+`` checks below.
        if body.startswith("---") or body.startswith("+++"):
            out.append(f"{BOLD}{body}{RESET}{ending}")
            i += 1
        elif body.startswith("@@"):
            out.append(f"{CYAN}{body}{RESET}{ending}")
            i += 1
        elif body.startswith("-"):
            # Gather a contiguous removal run, then the addition run that
            # follows it, and hand the pair to the word-diff emitter.
            rem: list[tuple[str, str]] = []
            while i < n:
                b, e = split(lines[i])
                if b.startswith("-") and not b.startswith("---"):
                    rem.append((b, e))
                    i += 1
                else:
                    break
            add: list[tuple[str, str]] = []
            while i < n:
                b, e = split(lines[i])
                if b.startswith("+") and not b.startswith("+++"):
                    add.append((b, e))
                    i += 1
                else:
                    break
            emit_change_block(out, rem, add)
        elif body.startswith("+"):
            # A pure insertion (no preceding removal to pair with).
            out.append(f"{GREEN}{body}{RESET}{ending}")
            i += 1
        else:
            out.append(lines[i])
            i += 1
    return "".join(out)


def detail(body: str, *, stream: Optional[TextIO] = None) -> None:
    """Dim, bulleted subordinate line under a headline; stdout by default."""
    s = stream or sys.stdout
    color = color_enabled(s)
    print(f"  {paint('·', DIM, enabled=color)} {paint(body, DIM, enabled=color)}", file=s)


def change_type_tag(change_type: "Optional[ChangeType]") -> str:
    """Inline ``[refactor]`` / ``[feature]`` / ``[non-code]`` tag for a step.

    Returns a leading-space, bracketed wire value (`` [refactor]``) for a
    classified step and ``""`` for an unclassified one, so call sites append
    it straight onto an existing label with no separator or conditional of
    their own — an unclassified step renders byte-identically. Rendered via
    ``.value`` so any future ``ChangeType`` member tracks automatically.
    """
    return f" [{change_type.value}]" if change_type is not None else ""


# --- Markdown → console rendering --------------------------------------------
#
# Reports are authored and persisted as markdown (the durable artifact), but
# dumping that markdown raw to the terminal obscures the content: italic
# markers turn `/path/to/report.md` into `_/path/to/report.md_` (breaking
# terminal click-to-open), backticks break command copy-paste, and `###`
# noise buries the headings. ``render_markdown_for_console`` converts the
# report for display: markers are ALWAYS stripped (that's the function's
# point, TTY or not); ANSI styling is layered on only when ``color_enabled``
# says the destination stream should carry it.

_MD_HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$")
_MD_RULE_RE = re.compile(r"^\s*-{3,}\s*$")
# Whole-line italic (`_…_` spanning the line) — the report's note/rationale
# convention (`_Completeness report saved to …_`). Anchored both ends so a
# snake_case word mid-line never matches.
_MD_LINE_ITALIC_RE = re.compile(r"^(\s*)_(.+)_\s*$")
# Inline italic restricted to the `_( … )_` parenthetical convention
# (`_(none)_`, `_(truncated)_`). A general `_…_` rule would eat the
# underscores of snake_case identifiers and file paths.
_MD_PAREN_ITALIC_RE = re.compile(r"_\((.*?)\)_")
_MD_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_MD_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")


def _strip_md_inline(text: str) -> str:
    """Drop inline markers (code backticks, bold, `_(…)_`) without styling."""
    text = _MD_INLINE_CODE_RE.sub(r"\1", text)
    text = _MD_BOLD_RE.sub(r"\1", text)
    text = _MD_PAREN_ITALIC_RE.sub(r"(\1)", text)
    return text


def _style_md_inline(text: str, *, color: bool) -> str:
    """Replace inline markers with their styled (or bare) content."""
    text = _MD_INLINE_CODE_RE.sub(
        lambda m: paint(m.group(1), CYAN, enabled=color), text
    )
    text = _MD_BOLD_RE.sub(
        lambda m: paint(m.group(1), BOLD, enabled=color), text
    )
    text = _MD_PAREN_ITALIC_RE.sub(
        lambda m: paint(f"({m.group(1)})", DIM, enabled=color), text
    )
    return text


def render_markdown_for_console(
    md: str, *, stream: Optional[TextIO] = None
) -> str:
    """Convert report markdown into console-friendly text.

    Line-oriented and dependency-free. Headings lose their ``#`` prefix
    (bold), whole-line and ``_(…)_`` italics lose their underscores
    (dim) — so file paths inside them stay terminal-clickable — inline
    code loses its backticks (cyan; commands copy-paste clean), bold
    loses its asterisks, and a ``---`` rule becomes a drawn line. Fenced
    code blocks pass through verbatim (minus the fence delimiters).
    Styling follows ``color_enabled(stream)`` (default stdout); marker
    stripping happens regardless, since a piped report is still meant
    for reading — the durable markdown artifact is the saved file, not
    the console dump.
    """
    color = color_enabled(stream)
    out: list[str] = []
    in_fence = False
    for line in md.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            out.append(line)
            continue
        if _MD_RULE_RE.match(line):
            out.append(paint("─" * 60, DIM, enabled=color))
            continue
        m = _MD_HEADING_RE.match(line)
        if m:
            # Strip (not style) inner markers first: a styled span's RESET
            # would cut the heading's bold short mid-line.
            out.append(
                paint(_strip_md_inline(m.group(1)), BOLD, enabled=color)
            )
            continue
        m = _MD_LINE_ITALIC_RE.match(line)
        if m:
            out.append(
                m.group(1)
                + paint(_strip_md_inline(m.group(2)), DIM, enabled=color)
            )
            continue
        out.append(_style_md_inline(line, color=color))
    return "\n".join(out)
