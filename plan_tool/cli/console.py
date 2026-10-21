"""Presentation + path-formatting helpers shared across CLI commands.

A leaf module: depends only on the standard library and the stdlib-only
``plan_tool.style`` / ``plan_tool.fileio`` / ``plan_tool.pathutil`` leaves
(none of which import anything first-party), so every per-intent command
module can import these without re-introducing an import cycle through
``app.py``.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any, Optional

from plan_tool.fileio import durable_write_text
from plan_tool.pathutil import display_path, is_within
from plan_tool.style import (
    BOLD,
    BOLD_CYAN,
    BOLD_GREEN,
    BOLD_YELLOW,
    CYAN,
    DIM,
    color_enabled,
    detail,
    paint,
    warn,
)

# These three are kept as names here because ``app`` re-exports them and the
# package-surface test pins them; the implementations are shared leaves.
_atomic_write = durable_write_text
_is_within = is_within
_short_path = display_path


def _report_archive_result(archive: Any, *, repo_root: Path) -> None:
    """Present one flat create-time archive result consistently."""
    for original, target in archive.archived:
        detail(
            f"archived {_short_path(original, repo_root)} "
            f"-> {_short_path(target, repo_root)}"
        )
    for reason in archive.skipped:
        warn(reason)


# --------------------------------------------------------------------------
# Roadmap views
# --------------------------------------------------------------------------


_ROADMAP_VIEW_TITLES = {
    "summary": "Roadmap summary",
    "walk": "Traceability walk",
    "ledger": "Decision ledger",
    "index": "Reverse citation index",
    "seeds": "Draft seed states",
    # ``html`` deliberately has no entry: that view prints a document, not a
    # report, and ``cmd_roadmap`` returns before this framing pass rather
    # than wrapping HTML in a banner.
}
_ROADMAP_SECTION_RE = re.compile(
    r"^(?P<indent>\s*)(?P<label>"
    r"roadmap|artifact status|intent|delivery shape|non-goals|depends_on|assumption_targets|assumptions|"
    r"components|entities|patterns|constraints|governs|fields|"
    r"roadmap_components|draft seed|settled|pending|anchor|rationale|"
    r"rejected_alternatives|target|artifacts|design|decisions|feedback|seeds|"
    r"indexed references|plan review context|needs attention|drill down"
    r"):"
)


def _style_roadmap_view_line(line: str, *, view: str, color: bool) -> str:
    """Add semantic emphasis to one already-rendered roadmap-view line.

    The view renderers intentionally return plain, deterministic text so
    callers can inspect or pipe their data without terminal escapes.  This
    console-only pass knows no roadmap data structures; it recognizes the
    stable presentation labels those renderers emit and gives the terminal
    reader a few fast visual anchors instead.
    """
    stripped = line.lstrip()
    indent = line[: len(line) - len(stripped)]

    if stripped.startswith("⚠"):
        return indent + paint(stripped, BOLD_YELLOW, enabled=color)

    match = _ROADMAP_SECTION_RE.match(line)
    if match is not None:
        label = match.group("label")
        label_style = BOLD
        if label == "settled":
            label_style = BOLD_GREEN
        elif label == "pending":
            label_style = BOLD_YELLOW
        elif label == "artifact status":
            label_style = BOLD_YELLOW
        prefix = match.group(0)
        return paint(prefix, label_style, enabled=color) + line[len(prefix) :]

    if view == "walk" and not indent and stripped:
        # The walk's unindented non-header lines are plan titles.  Making
        # them stand apart keeps a long nested plan/component/entity tree
        # scannable without changing its machine-friendly text shape.
        return paint(line, BOLD_CYAN, enabled=color)

    if view == "index" and not indent and ":" in line:
        row_id, remainder = line.split(":", 1)
        return paint(row_id + ":", CYAN, enabled=color) + remainder

    if stripped.startswith("- "):
        return indent + paint("-", DIM, enabled=color) + stripped[1:]

    return line


def render_roadmap_view(
    view: str, text: str, *, stream: Any = None
) -> str:
    """Frame and style a read-only roadmap view for terminal presentation.

    The heading identifies which projection the user is reading; the
    per-line pass then distinguishes structural labels, decision state,
    row ids, warnings, and the top-level plans in a traceability walk. ANSI
    styling follows the shared TTY/``NO_COLOR`` contract. The banner and
    divider remain useful in plain output, while the supplied ``text`` keeps
    its original wording and nesting for copy/paste and tests.
    """
    out = stream if stream is not None else sys.stdout
    color = color_enabled(out)
    title = _ROADMAP_VIEW_TITLES.get(view, "Roadmap")
    lines = [
        paint(f"Roadmap view · {title}", BOLD_CYAN, enabled=color),
        paint("─" * 60, DIM, enabled=color),
    ]
    lines.extend(
        _style_roadmap_view_line(line, view=view, color=color)
        for line in text.splitlines()
    )
    return "\n".join(lines)


def _common_dir_prefix(paths: list[Path]) -> Optional[Path]:
    """Return the deepest directory all ``paths`` share, or ``None``.

    Used to factor a repeated parent out of a list of files so the final
    summary shows the prefix once and just the basenames below. Returns
    ``None`` when paths span multiple directories (no factoring win) or
    when the list is empty.
    """
    if not paths:
        return None
    parents = [p.parent for p in paths]
    first = parents[0]
    if all(p == first for p in parents[1:]):
        return first
    return None


def _print_detail_summary(
    *,
    slug: str,
    wrote: list[tuple[int, Path]],
    skipped: list[tuple[int, str]],
    rc: int,
    repo_root: Path,
    stream: Any = None,
) -> None:
    """Render the final block of a ``plan-tool detail`` run.

    Visual goals (driven by operator feedback that the trailing block was
    the hardest part of the output to read):

    - Wrap the deliverable in a horizontal-rule banner so it stands out
      against the surrounding progress / status lines.
    - Factor a common parent directory out of the written-file list so
      the screen shows the path *once* with basenames beneath, rather
      than 5+ long repo-relative paths.
    - Show skipped-step lines as a separate sub-block (when present) so
      successful writes and skipped steps don't visually blend.

    The header line states the command + plan slug so an operator
    glancing at the bottom of the terminal can tell which run finished.
    """
    out = stream if stream is not None else sys.stdout
    bar = "─" * 60
    out.write(f"\n{bar}\n")
    verb = "wrote" if rc == 0 else "wrote (with errors)"
    out.write(f"  plan-tool detail · {slug}\n")
    if wrote:
        paths = [p for _, p in wrote]
        common = _common_dir_prefix(paths)
        if common is not None and len(paths) > 1:
            common_rel = _short_path(common, repo_root)
            out.write(f"  {verb} {len(paths)} detail file(s) in {common_rel}/\n")
            for step_id, p in wrote:
                out.write(f"    {step_id:>2}. {p.name}\n")
        else:
            out.write(f"  {verb} {len(paths)} detail file(s):\n")
            for step_id, p in wrote:
                out.write(f"    {step_id:>2}. {_short_path(p, repo_root)}\n")
    if skipped:
        if wrote:
            out.write("\n")
        out.write(f"  skipped {len(skipped)} step(s):\n")
        # Group identical reasons so a run that skipped every step for the
        # same cause (e.g. "already exists, declined replace") collapses to
        # one line listing the step ids, instead of repeating the long
        # reason once per step.
        by_reason: dict[str, list[int]] = {}
        for step_id, reason in skipped:
            by_reason.setdefault(reason, []).append(step_id)
        for reason, ids in by_reason.items():
            ids_txt = ", ".join(str(i) for i in sorted(ids))
            label = "step" if len(ids) == 1 else "steps"
            out.write(f"    {label} {ids_txt}: {reason}\n")
    out.write(f"{bar}\n")
    out.flush()


def _print_next_steps(
    title: str, steps: list[tuple[str, str]], *, stream: Any = None
) -> None:
    """Emit a uniformly-formatted "Next steps" / "Try" block.

    ``steps`` is a list of ``(command, description)`` tuples. The command
    is shown left-aligned with the description after a `#`. Renders like:

        Next steps:
          plan-tool detail my-plan     # author per-step detail files
          plan-tool run my-plan        # execute step 1

    Suggestions are advisory output and go to stderr by default so they
    don't pollute pipelines that capture stdout (e.g. `plan-tool list`
    consumed by another tool). ``stream`` is overridable for tests.
    """
    if not steps:
        return
    out = stream if stream is not None else sys.stderr
    color = color_enabled(out)
    out.write(f"\n{paint(title, BOLD, enabled=color)}\n")
    # Align all `#` columns to the longest command for readability. Padding
    # is computed on the raw command (no ANSI) so columns stay aligned even
    # once the command is colored.
    col = max(len(cmd) for cmd, _ in steps)
    for cmd, desc in steps:
        pad = " " * (col - len(cmd))
        cmd_txt = paint(cmd, CYAN, enabled=color)
        desc_txt = paint(f"# {desc}", DIM, enabled=color)
        out.write(f"  {cmd_txt}{pad}   {desc_txt}\n")
    out.flush()


def _fmt_ms(value: Optional[float]) -> str:
    """Render a millisecond value with a unit that fits the magnitude.

    < 1s → ``"NNNms"``; < 60s → ``"NN.Ns"``; ≥ 60s → ``"NN.Nm"``.
    ``None`` renders as ``"-"`` so an absent percentile (e.g. p95 with
    one sample) doesn't print as ``0``.
    """
    if value is None:
        return "-"
    ms = float(value)
    if ms < 1000:
        return f"{int(round(ms))}ms"
    seconds = ms / 1000.0
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = seconds / 60.0
    return f"{minutes:.1f}m"


def _fmt_ms_or_n(value: Optional[float], n_complete: int) -> str:
    """Render a millisecond value, or the ``n=N`` suppression sentinel.

    Used by ``runs profile`` for the p50 / p95 cells: when a bucket
    has fewer than ``_SMALL_BUCKET_THRESHOLD`` completed samples both
    quantiles are suppressed to ``None``; the cell instead shows
    ``n=<count - incomplete>`` so the operator sees both the
    suppression and the underlying sample count in one glance. With
    no completed samples at all (``n_complete == 0``) fall back to
    the regular ``-`` rendering — the ``count`` / ``incomplete``
    columns already surface that fact.
    """
    if value is None and n_complete > 0:
        return f"n={n_complete}"
    return _fmt_ms(value)


def _repo_rel(path: Path, repo_root: Path) -> str:
    """Repo-relative POSIX form of ``path``; absolute fallback when outside."""
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _format_relative_age(iso_ts: str) -> str:
    """Return a short human-readable age for an ISO-8601 UTC timestamp.

    Falls back to the raw ``iso_ts`` if parsing fails so the prompt
    never blocks on a malformed save. Examples: ``"45s ago"``,
    ``"3m ago"``, ``"2h ago"``, ``"4d ago"``.
    """
    from datetime import datetime, timezone

    try:
        if iso_ts.endswith("Z"):
            ts = datetime.strptime(iso_ts, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
        else:
            ts = datetime.fromisoformat(iso_ts)
    except (ValueError, TypeError):
        return iso_ts

    delta = datetime.now(timezone.utc) - ts
    secs = int(delta.total_seconds())
    if secs < 0:
        return iso_ts  # future timestamp — bail out
    if secs < 60:
        return f"{secs}s ago"
    mins = secs // 60
    if mins < 60:
        return f"{mins}m ago"
    hours = mins // 60
    if hours < 48:
        return f"{hours}h ago"
    return f"{hours // 24}d ago"
