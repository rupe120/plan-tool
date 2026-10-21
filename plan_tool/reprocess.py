"""Fill ``_(TODO)_`` placeholders in an existing plan from its archive.

`reprocess` is the cheap, token-free counterpart to `create --iterate`:
when a previous run left H2 sections as ``_(TODO)_`` placeholders (e.g.
because the source carried no provenance frontmatter), and an archived
predecessor of the plan still exists under ``<plan-dir>/archive/``,
this module lifts the archive's section bodies into the live plan
without calling Claude.

Only sections whose body is the ``_(TODO)_`` marker are substituted —
already-populated sections are left untouched. The ``## Steps``
section is also skipped: it carries a frontmatter pointer, not prose
content, and lifting an archive's steps prose would re-introduce drift
between the frontmatter and the body.

Frontmatter is preserved byte-for-byte via :func:`parser.write_plan`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from plan_tool.create import _H2_HEADING_RE, extract_h2_sections
from plan_tool.parser import ParseError, _split_frontmatter, parse_plan
from plan_tool.scope_fence import _fenced_code_spans, _strip_frontmatter


TODO_MARKER = "_(TODO)_"

# Section bodies the substitution must never overwrite — the Steps
# section is a one-line pointer at the frontmatter, not prose content.
_NEVER_SUBSTITUTE = frozenset({"steps"})


class ReprocessError(Exception):
    """Raised when reprocess can't proceed (missing plan / archive)."""


def _reject_unmatched_fence(source_text: str, source: Path) -> None:
    if _fenced_code_spans(_strip_frontmatter(source_text)).unmatched_opening is not None:
        raise ReprocessError(
            f"{source}: unmatched opening code fence; add a matching closing fence "
            "before reprocessing."
        )


def _reject_unmatched_plan_fence(plan_text: str, plan_path: Path) -> None:
    """Same check as :func:`_reject_unmatched_fence`, but for ``plan_text``
    specifically: isolate the body via ``parser._split_frontmatter`` rather
    than the lenient ``scope_fence`` splitter.

    ``plan_text`` gets strictly re-parsed moments later (``parse_plan`` and
    :func:`_split_frontmatter_for_rewrite`, both matching-on-``rstrip``, not
    ``strip``), so this guard must fail exactly when that reparse would —
    otherwise a closing ``---`` line with trailing whitespace can pass this
    check (lenient frontmatter isolation finds no unmatched code fence) and
    then fail the reparse moments later with an unrelated-sounding error.
    """
    try:
        body = _split_frontmatter(plan_text).body
    except ParseError as exc:
        raise ReprocessError(str(exc)) from exc
    if _fenced_code_spans(body).unmatched_opening is not None:
        raise ReprocessError(
            f"{plan_path}: unmatched opening code fence; add a matching closing fence "
            "before reprocessing."
        )


@dataclass
class ReprocessResult:
    plan_path: Path
    archive_path: Path
    # H2 titles whose ``_(TODO)_`` body was replaced from the archive.
    filled: list[str] = field(default_factory=list)
    # H2 titles that are still ``_(TODO)_`` because the archive has no
    # matching section (or the archive's section was itself empty).
    unfilled: list[str] = field(default_factory=list)
    # H2 titles left untouched because they already had non-TODO content.
    skipped: list[str] = field(default_factory=list)


def find_archive_for_slug(plan_path: Path, slug: str) -> Optional[Path]:
    """Locate the most-recent ``<slug>.replaced.md`` archive for ``plan_path``.

    Archives live under ``<plan-dir>/archive/`` and are named after the
    original source filename (e.g. ``foo.replaced.md`` or
    ``2-foo.replaced.md``). Multiple replacements over time leave
    multiple archives; the most-recently modified one is returned so
    the freshest predecessor content wins.

    Returns ``None`` when the archive dir is missing or no archive
    matches the slug.
    """
    archive_dir = plan_path.parent / "archive"
    if not archive_dir.is_dir():
        return None
    pattern = re.compile(rf"^(\d+-)?{re.escape(slug)}\.replaced\.md$")
    matches = [
        p for p in archive_dir.iterdir()
        if p.is_file() and pattern.match(p.name)
    ]
    if not matches:
        return None
    matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0]


def reprocess_plan(
    plan_path: Path, archive_path: Path
) -> ReprocessResult:
    """Substitute ``_(TODO)_`` section bodies in ``plan_path`` from ``archive_path``.

    Walks the live plan's body H2 sections in order. For each section
    whose body is the bare ``_(TODO)_`` marker (after stripping
    whitespace), looks up the same-titled section in the archive (case-
    insensitive). When the archive has a non-empty body, the marker is
    replaced with that body. Sections without an archive match stay as
    ``_(TODO)_`` and land in ``ReprocessResult.unfilled``.

    Re-parses the plan after the write to confirm the result still
    satisfies the schema — a corrupted reprocess never lands on disk.

    Raises :class:`ReprocessError` when:

    - the plan or archive isn't a readable file;
    - the plan has no ``_(TODO)_`` sections (nothing to do — likely a
      caller bug worth surfacing, not a silent no-op).
    """
    if not plan_path.is_file():
        raise ReprocessError(f"plan file not found: {plan_path}")
    if not archive_path.is_file():
        raise ReprocessError(f"archive file not found: {archive_path}")

    plan_text = plan_path.read_text(encoding="utf-8")
    archive_text = archive_path.read_text(encoding="utf-8")
    _reject_unmatched_plan_fence(plan_text, plan_path)
    _reject_unmatched_fence(archive_text, archive_path)

    # Validate the plan parses before we touch it — refusing to mutate
    # an already-broken plan is cheaper than untangling a half-written
    # result.
    parse_plan(plan_path)

    archive_sections = extract_h2_sections(
        archive_text, ignore_fenced_code=True
    )

    frontmatter, body = _split_frontmatter_for_rewrite(plan_text)
    new_body, result_meta = _substitute_todo_sections(
        body, archive_sections
    )
    if not result_meta["had_todos"]:
        raise ReprocessError(
            f"no `_(TODO)_` sections found in {plan_path}; nothing to "
            "reprocess. Run `plan-tool completeness` to verify, or "
            "edit the plan body to mark sections that need filling."
        )

    plan_path.write_text(frontmatter + new_body, encoding="utf-8")
    # Re-parse from disk: if the substitution somehow corrupted the
    # plan we want to know before the user does.
    parse_plan(plan_path)

    return ReprocessResult(
        plan_path=plan_path,
        archive_path=archive_path,
        filled=result_meta["filled"],
        unfilled=result_meta["unfilled"],
        skipped=result_meta["skipped"],
    )


def _split_frontmatter_for_rewrite(text: str) -> tuple[str, str]:
    """Return (frontmatter_block_including_fences, body).

    ``parser._split_frontmatter`` strips the fences and returns just
    the YAML inside; we need the fences too so the rewrite can
    concatenate cleanly and stay byte-identical to the original
    frontmatter. The body half is the rest of the file after the
    closing fence's newline.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        raise ReprocessError(
            "plan file does not begin with a '---' frontmatter fence"
        )
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r\n") == "---":
            fm = "".join(lines[: i + 1])
            body = "".join(lines[i + 1:])
            return fm, body
    raise ReprocessError(
        "plan file opens with '---' but has no closing fence"
    )


def _substitute_todo_sections(
    body: str, archive_sections: dict[str, str]
) -> tuple[str, dict]:
    """Rebuild ``body`` with TODO H2 bodies substituted from ``archive_sections``.

    Returns ``(new_body, meta)`` where meta carries ``filled``,
    ``unfilled``, ``skipped`` lists plus a ``had_todos`` flag the
    caller uses to decide whether the no-op error fires.
    """
    fenced_spans = _fenced_code_spans(body).spans
    matches = [
        match
        for match in _H2_HEADING_RE.finditer(body)
        if not any(start <= match.start() < end for start, end in fenced_spans)
    ]
    # Filter to only H2 (## ) matches — extract_h2_sections does the
    # same; mirroring it keeps detection symmetric.
    h2_matches = [m for m in matches if m.group(1) == "##"]
    filled: list[str] = []
    unfilled: list[str] = []
    skipped: list[str] = []
    had_todos = False

    if not h2_matches:
        return body, {
            "filled": filled,
            "unfilled": unfilled,
            "skipped": skipped,
            "had_todos": False,
        }

    parts: list[str] = [body[: h2_matches[0].start()]]
    for i, m in enumerate(h2_matches):
        title = m.group(2).strip()
        section_start = m.start()
        body_start = m.end()
        body_end = (
            h2_matches[i + 1].start()
            if i + 1 < len(h2_matches)
            else len(body)
        )
        section_body_raw = body[body_start:body_end]
        section_body_stripped = section_body_raw.strip()
        key = title.lower()

        if key in _NEVER_SUBSTITUTE:
            parts.append(body[section_start:body_end])
            skipped.append(title)
            continue

        if section_body_stripped != TODO_MARKER:
            parts.append(body[section_start:body_end])
            skipped.append(title)
            continue

        had_todos = True
        archive_body = archive_sections.get(key)
        if not archive_body:
            parts.append(body[section_start:body_end])
            unfilled.append(title)
            continue

        # Reuse the original section's whitespace shell: heading line,
        # the blank line(s) before the body, and the trailing blank
        # line(s) before the next heading. Only the body content
        # between them is swapped.
        heading_line = body[section_start:body_start]
        # Find the leading whitespace in section_body_raw (typically
        # "\n\n") so the inserted body keeps the same separation.
        leading_ws = ""
        for ch in section_body_raw:
            if ch in (" ", "\t", "\n", "\r"):
                leading_ws += ch
            else:
                break
        trailing_ws = ""
        for ch in reversed(section_body_raw):
            if ch in (" ", "\t", "\n", "\r"):
                trailing_ws = ch + trailing_ws
            else:
                break
        parts.append(
            heading_line + leading_ws + archive_body + trailing_ws
        )
        filled.append(title)

    return "".join(parts), {
        "filled": filled,
        "unfilled": unfilled,
        "skipped": skipped,
        "had_todos": had_todos,
    }
