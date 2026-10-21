"""Render a step-1 :class:`PlanAnnotation` into the two operator artifacts.

Two pure functions consume one classification result:

- :func:`render_annotated_report` — the **lossless audit**: the original
  file verbatim, with one status block inserted after each matched
  heading, a top-of-file coverage summary, and a provenance header. Every
  line of ``annotation.source_text`` survives unchanged and in order — the
  strictly-additive guarantee step 2's tests lock down.
- :func:`render_create_seed` — the **compact carryover brief** for
  ``create --from-existing``: the NOT-IMPLEMENTED / actionable
  NEEDS-REVIEW sections plus each PARTIAL's ``remaining_work`` as scope,
  and the IMPLEMENTED sections plus each PARTIAL's already-implemented
  half as done-context.

Both are deterministic string builders — no file IO, no git, no Claude,
no ``invoker=`` seam. They import only step 1's frozen contract plus
stdlib; path derivation, disk writes, and archiving stay in step 3's CLI.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from plan_tool.annotate import AnnotateError, AnnotationStatus, PlanAnnotation, SectionAnnotation
from plan_tool.scope_fence import (
    _fenced_code_spans,
    _is_placeholder_section,
    _strip_frontmatter,
    extract_h2_sections,
)


_UNMATCHED_HEADING = "## Annotate — unmatched sections"
_REPORT_HEADER_RE = re.compile(
    r"^<!-- plan-tool annotate report\n(?P<body>.*?)\n-->", re.S
)
_COVERAGE_RE = re.compile(r"> \*\*Coverage:\*\* (?P<body>.*)")
_COUNT_RE = re.compile(
    r"(?P<count>\d+) (?P<label>IMPLEMENTED|PARTIAL|NOT-IMPLEMENTED|NEEDS-REVIEW)"
)


def reject_unmatched_annotation_fence(source_text: str, source: Path | str) -> None:
    """Reject an annotation source that would hide later H2 sections."""
    if _fenced_code_spans(_strip_frontmatter(source_text)).unmatched_opening is not None:
        raise AnnotateError(
            f"{source}: unmatched opening code fence; add a matching closing fence "
            "before annotating."
        )


@dataclass(frozen=True)
class CachedAnnotatedReport:
    """Summary fields read from a cached ``*.annotated.md`` report."""

    path: Path
    source_path: Path | None
    annotated_at: str
    grounded_files: int
    implemented: int
    partial: int
    not_implemented: int
    needs_review: int

    @property
    def counts_key(self) -> tuple[int, int, int, int, int]:
        """Return the comparable count payload for duplicate-report checks."""
        return (
            self.implemented,
            self.partial,
            self.not_implemented,
            self.needs_review,
            self.grounded_files,
        )


def parse_cached_annotated_report(path: Path) -> CachedAnnotatedReport | None:
    """Read rollup metadata from a cached ``*.annotated.md`` report.

    Returns ``None`` when ``path`` is unreadable or is not an annotate report.
    The parser intentionally reads only the stable header and coverage line
    emitted by :func:`render_annotated_report`; it never reparses original
    plan prose or calls the classifier.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    header_match = _REPORT_HEADER_RE.search(text)
    if header_match is None:
        return None
    header = _parse_report_header(header_match.group("body"))
    coverage = _parse_report_coverage(text)
    if coverage is None:
        return None
    source = header.get("source", "").strip()
    return CachedAnnotatedReport(
        path=path,
        source_path=Path(source) if source else None,
        annotated_at=header.get("annotated_at", "").strip(),
        grounded_files=_parse_int(header.get("grounded_files", "0")),
        implemented=coverage.get("IMPLEMENTED", 0),
        partial=coverage.get("PARTIAL", 0),
        not_implemented=coverage.get("NOT-IMPLEMENTED", 0),
        needs_review=coverage.get("NEEDS-REVIEW", 0),
    )


def render_annotated_report(annotation: PlanAnnotation) -> str:
    """Render the strictly-additive annotated report.

    Prepends a provenance header and a coverage summary, then reproduces
    ``annotation.source_text`` verbatim with one status block inserted
    after each matched heading. The report is the lossless audit, so a
    PARTIAL renders its whole verdict (status + evidence + all refs) — the
    implemented/remaining split is a seed-scoping concern only.
    """
    reject_unmatched_annotation_fence(annotation.source_text, annotation.source_path)
    header = (
        "<!-- plan-tool annotate report\n"
        f"source: {annotation.source_path}\n"
        f"repo_root: {annotation.repo_root}\n"
        f"annotated_at: {annotation.annotated_at}\n"
        f"grounded_files: {len(annotation.grounded_files)}\n"
        f"candidate_text_files: {annotation.grounding_candidate_count}\n"
        f"skipped_or_unreadable_files: {annotation.grounding_skipped_count}\n"
        "-->"
    )
    banner = _low_grounding_banner(annotation)
    summary = _coverage_summary(annotation.sections)
    body = _insert_status_blocks(annotation.source_text, annotation.sections)
    prefix = f"{header}\n"
    if banner:
        prefix += f"{banner}\n"
    return f"{prefix}{summary}\n\n{body}"


def render_create_seed(annotation: PlanAnnotation, *, report_path: Path) -> str:
    """Render the compact carryover create-seed scoped to the remaining work.

    Partitions the sections, splitting each PARTIAL across both blocks:
    carryover scope gets every NOT-IMPLEMENTED section whole plus only the
    ``remaining_work`` of every PARTIAL; done-context gets every
    IMPLEMENTED section whole plus the already-implemented half (``code_refs``
    / ``evidence``) of every PARTIAL. ``report_path`` is injected (not
    derived) so the renderer stays filesystem-agnostic.
    """
    reject_unmatched_annotation_fence(annotation.source_text, annotation.source_path)
    source_name = annotation.source_path.name

    header = (
        "<!-- plan-tool annotate create-seed\n"
        f"source: {annotation.source_path}\n"
        f"report: {report_path}\n"
        "-->"
    )

    lines: list[str] = [
        header,
        "",
        f"# Plan seed: carryover from {source_name}",
        "",
        (
            "This is a `plan-tool create` input. It scopes **only the "
            "remaining work** — the IMPLEMENTED items and the "
            "already-done half of the PARTIAL items in "
            "**Already implemented** below are done-context, not to be "
            f"re-planned. See the full annotated report at `{report_path}`."
        ),
        "",
        "## Carryover scope (remaining work)",
        "",
    ]

    carryover = [
        s
        for s in annotation.sections
        if s.status
        in (
            AnnotationStatus.NOT_IMPLEMENTED,
            AnnotationStatus.PARTIAL,
            AnnotationStatus.NEEDS_REVIEW,
        )
        and not s.contradiction_review
    ]
    if not carryover:
        if all(s.status is AnnotationStatus.IMPLEMENTED for s in annotation.sections):
            lines.append("No remaining work — every section is implemented.")
        else:
            lines.append(
                "No carryover scope selected — review NEEDS-REVIEW items in "
                "the annotated report before planning."
            )
        lines.append("")
    else:
        for section in carryover:
            lines.extend(_carryover_entry(section))

    lines.append("## Already implemented (done-context — do not re-plan)")
    lines.append("")
    done = [
        s
        for s in annotation.sections
        if s.status in (AnnotationStatus.IMPLEMENTED, AnnotationStatus.PARTIAL)
        or (s.status is AnnotationStatus.NEEDS_REVIEW and s.contradiction_review)
    ]
    if not done:
        lines.append("_None — nothing classified as implemented._")
    else:
        for section in done:
            lines.append(_done_context_bullet(section))
    lines.append("")

    source_references = extract_h2_sections(
        _strip_frontmatter(annotation.source_text), ignore_fenced_code=True
    ).get("references")
    references = (source_references or "").strip()
    lines.append("## References")
    lines.append("")
    if references and not _is_placeholder_section(references):
        lines.append(references)
    else:
        lines.append(f"- Source document: `{annotation.source_path}`")
        lines.append(f"- Annotated report: `{report_path}`")
    lines.append("")

    lines.append("## Provenance")
    lines.append("")
    lines.append(f"- Original: {annotation.source_path}")
    lines.append(f"- Report: {report_path}")
    lines.append("")

    return "\n".join(lines)


def _carryover_entry(section: SectionAnnotation) -> list[str]:
    """Render one carryover subsection for an unfinished or review-needed section."""
    low_conf = " (low confidence — verify before planning)" if section.low_confidence else ""
    out: list[str] = [f"### {section.heading}", ""]
    if section.status is AnnotationStatus.NOT_IMPLEMENTED:
        out.append(f"[NOT-IMPLEMENTED]{low_conf}")
        if section.evidence:
            out.append("")
            out.append(section.evidence)
    elif section.status is AnnotationStatus.NEEDS_REVIEW:
        out.append(f"[NEEDS-REVIEW]{low_conf}")
        if section.evidence:
            out.append("")
            out.append(section.evidence)
    else:  # PARTIAL — carry only the remaining_work, never the implemented refs.
        partial_label = (
            "[PARTIAL — review-required remaining]"
            if section.low_grounding
            else "[PARTIAL — remaining]"
        )
        if section.remaining_work:
            out.append(f"{partial_label}{low_conf}")
            out.append("")
            out.append(section.remaining_work)
        else:
            # The model omitted the remainder — carry forward via evidence
            # rather than silently drop the PARTIAL.
            out.append(
                f"{partial_label} (remainder not pinned — "
                f"verify scope before planning){low_conf}"
            )
            if section.evidence:
                out.append("")
                out.append(section.evidence)
        if section.low_grounding:
            out.append("")
            out.append("Review required: grounding was too thin to trust this split.")
        out.append("")
        out.append("(already-implemented portion below in Already implemented)")
    out.append("")
    return out


def _done_context_bullet(section: SectionAnnotation) -> str:
    """Render one done-context bullet for an IMPLEMENTED or PARTIAL section."""
    refs = _format_code_refs(section.code_refs)
    low_conf = " (low confidence)" if section.low_confidence else ""
    if section.status is AnnotationStatus.PARTIAL:
        suffix = f" — {refs}" if refs else ""
        return f"- {section.heading} (partial — done half){suffix}{low_conf}"
    suffix = f" — {refs}" if refs else ""
    return f"- {section.heading}{suffix}{low_conf}"


def _insert_status_blocks(
    source_text: str, sections: tuple[SectionAnnotation, ...]
) -> str:
    """Reproduce ``source_text`` verbatim with status blocks added additively.

    Prose sections (``is_step`` False) are heading-matched: their block is
    emitted right after the first matching heading line. Plan-step sections
    (``is_step`` True) carry a frontmatter ``title:`` that never appears as
    a markdown heading, so they are anchored to the ``## Steps`` region in
    frontmatter order. The only writes are pass-through of each original
    line plus inserted ``>``-prefixed block lines — no original line is
    modified, reordered, or dropped.
    """
    prose_sections = [s for s in sections if not s.is_step]
    step_sections = [s for s in sections if s.is_step]

    by_norm: dict[str, SectionAnnotation] = {}
    for section in prose_sections:
        key = _normalize_heading(section.heading)
        by_norm.setdefault(key, section)
    consumed: set[str] = set()

    out: list[str] = []
    steps_region_seen = False
    for line in source_text.splitlines():
        out.append(line)
        norm = _normalize_heading(line)
        if norm in by_norm and norm not in consumed:
            consumed.add(norm)
            out.extend(_status_block(by_norm[norm]).splitlines())
        if step_sections and not steps_region_seen and norm == "Steps":
            steps_region_seen = True
            for step in step_sections:
                out.append(f"> **{step.heading}**")
                out.extend(_status_block(step).splitlines())

    # Anything never matched is appended (append-only, so the guarantee holds):
    # prose headings absent from the body, and step sections when the source
    # has no ## Steps heading to anchor them under.
    unmatched: list[SectionAnnotation] = [
        s for s in prose_sections if _normalize_heading(s.heading) not in consumed
    ]
    if not steps_region_seen:
        unmatched.extend(step_sections)
    if unmatched:
        out.append("")
        out.append(_UNMATCHED_HEADING)
        out.append("")
        for section in unmatched:
            out.append(f"> **{section.heading}**")
            out.extend(_status_block(section).splitlines())

    return "\n".join(out)


def _normalize_heading(line: str) -> str:
    """Strip leading ``#`` markers and surrounding whitespace for matching.

    Step 1's prompt-emitted heading is "verbatim" but marker inclusion is
    not guaranteed, so matching on the marker-stripped text is robust
    whether or not the captured heading kept its ``#``/``##``/``###``.
    """
    return line.lstrip("#").strip()


def _status_block(section: SectionAnnotation) -> str:
    """Render one section's verdict as a single blockquote line."""
    label = _status_label(section.status)
    refs = _format_code_refs(section.code_refs)
    refs_suffix = f" ({refs})" if refs else ""
    low_conf_suffix = " _(low confidence)_" if section.low_confidence else ""
    return f"> **{label}** — {section.evidence}{refs_suffix}{low_conf_suffix}"


def _status_label(status: AnnotationStatus) -> str:
    """Human-facing status label (``NOT IMPLEMENTED`` with a space, not the wire form)."""
    if status is AnnotationStatus.NOT_IMPLEMENTED:
        return "NOT IMPLEMENTED"
    return status.value


def _format_code_refs(refs: tuple[str, ...]) -> str:
    """Backtick-wrap each ref and join with ``, ``; ``""`` for an empty tuple."""
    return ", ".join(f"`{ref}`" for ref in refs)


def _coverage_summary(sections: tuple[SectionAnnotation, ...]) -> str:
    """Render the top-of-file per-status coverage line as a blockquote."""
    counts = Counter(s.status for s in sections)
    implemented = counts[AnnotationStatus.IMPLEMENTED]
    partial = counts[AnnotationStatus.PARTIAL]
    not_implemented = counts[AnnotationStatus.NOT_IMPLEMENTED]
    needs_review = counts[AnnotationStatus.NEEDS_REVIEW]
    low_conf = sum(1 for s in sections if s.low_confidence)

    parts = [
        f"{implemented} IMPLEMENTED",
        f"{partial} PARTIAL",
        f"{not_implemented} NOT-IMPLEMENTED",
        f"{needs_review} NEEDS-REVIEW",
    ]
    if low_conf > 0:
        parts.append(f"{low_conf} low-confidence")
    line = "> **Coverage:** " + " · ".join(parts)
    if sections and implemented == len(sections):
        line += " · 100% implemented"
    return line


def _low_grounding_banner(annotation: PlanAnnotation) -> str:
    """Render the report-level warning when any verdict hit the grounding floor."""
    if not annotation.low_grounding:
        return ""
    grounded = len(annotation.grounded_files)
    candidates = annotation.grounding_candidate_count
    skipped = annotation.grounding_skipped_count
    return (
        f"> **Low grounding ({grounded} files)** — verdicts are speculative; "
        f"verify before trusting. Candidates: {candidates}; skipped/unreadable: "
        f"{skipped}."
    )


def _parse_report_header(body: str) -> dict[str, str]:
    """Parse the simple ``key: value`` lines from the annotate report header."""
    values: dict[str, str] = {}
    for line in body.splitlines():
        key, sep, value = line.partition(":")
        if sep:
            values[key.strip()] = value.strip()
    return values


def _parse_report_coverage(text: str) -> dict[str, int] | None:
    """Parse the rendered coverage line into per-status counts."""
    match = _COVERAGE_RE.search(text)
    if match is None:
        return None
    counts = {
        "IMPLEMENTED": 0,
        "PARTIAL": 0,
        "NOT-IMPLEMENTED": 0,
        "NEEDS-REVIEW": 0,
    }
    for item in _COUNT_RE.finditer(match.group("body")):
        counts[item.group("label")] = int(item.group("count"))
    return counts


def _parse_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0
