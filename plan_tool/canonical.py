"""Deterministic read helpers for canonical-shape plan sources.

A *canonical source* is a plan/notes file whose ``## Steps`` section
uses the strict ``### N. Title`` heading form with ``Files:`` /
``Creates:`` bullet blocks and ``Depends on: N, M`` lines. ``Files:``
lists existing files the step modifies; ``Creates:`` lists new files it
adds. ``create --from-existing`` can lift the step graph out of such a
source without a Claude call.

This module contains only the deterministic read path:

- :func:`has_canonical_steps_marker` — cheap "looks canonical" probe.
- :func:`extract_canonical_steps` — strict reader; returns ``None`` on
  any drift from the canonical shape.
- :func:`read_canonical_provenance` — reads the optional
  ``source`` / ``plan_details`` provenance YAML some legacy canonical
  files carry in their frontmatter.

Strictness in :func:`extract_canonical_steps` is enforced via a
re-render round-trip rather than ad-hoc shape checks: parsed steps are
passed back through :func:`_render_steps_section` and the result must
match the source slice byte-for-byte. This way the reader and any
hypothetical writer are forced to agree on the shape exactly — a guard
preserved here even after ``plan-tool reformat`` (the prior writer)
was removed (BACKLOG #40).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

import yaml

from plan_tool.parser import ParseError, _split_frontmatter


@dataclass
class CanonicalStep:
    """One step extracted from a canonical source."""

    title: str
    files: list[str] = field(default_factory=list)
    creates: list[str] = field(default_factory=list)
    depends_on: list[int] = field(default_factory=list)
    # Optional refactor/feature/non-code classification, lifted from a
    # single ``Type:`` line under the step heading. Kept a plain ``str``
    # (validated by ``_STRICT_TYPE_RE``, never imported as the schema
    # enum) so ``canonical.py`` stays free of ``plan_tool.schema``; the
    # create wrapper coerces it to ``ChangeType`` when it builds ``Step``s.
    change_type: Optional[str] = None


@dataclass(frozen=True)
class CanonicalProvenance:
    """Filesystem-level pointers carried in a canonical file's frontmatter.

    ``source`` is the original seed file's name (or path) relative to the
    canonical's parent directory. ``plan_details`` is the parent-relative
    path to the existing ``plan-details/<slug>/`` directory associated
    with the seed, or ``None`` when no such directory exists. Both values
    are stored relative to the canonical so the link survives if the
    pair gets moved as a unit.

    No writer remains in plan-tool (the ``reformat`` subcommand that
    produced these frontmatters was removed — see BACKLOG #40). The
    type is retained for graceful reading of legacy canonical files
    still on disk.
    """

    source: str
    plan_details: Optional[str] = None


# Strict regexes. ``extract_canonical_steps`` round-trips parsed steps
# through ``_render_steps_section`` and requires byte-exact equality, so
# any drift the regexes admit but the renderer doesn't emit (or vice
# versa) shows up as a returned ``None``.
_STRICT_STEPS_H2_RE = re.compile(r"(?:\A|\n)## Steps\n")
_STRICT_STEP_HEAD_RE = re.compile(r"^### (\d+)\. (.+)$", re.MULTILINE)
_STRICT_PATH_BULLET_RE = re.compile(r"^- `([^`]+)`$")
_STRICT_DEPENDS_RE = re.compile(r"^Depends on: ([0-9, ]+)$", re.MULTILINE)
_STRICT_TYPE_RE = re.compile(r"^Type: (refactor|feature|non-code)$", re.MULTILINE)


def _body_after_frontmatter(text: str) -> str:
    """Strip a YAML frontmatter block when present, else return ``text``.

    Reuses :func:`plan_tool.parser._split_frontmatter` so the fence rules
    match the rest of plan-tool exactly. The frontmatter's YAML contents
    are not validated here — only the ``---`` fences are consumed.
    """
    try:
        return _split_frontmatter(text).body
    except ParseError:
        return text


def has_canonical_steps_marker(text: str) -> bool:
    """Does ``text`` look like it tried to be canonical? (``## Steps`` H2 line.)

    Used by ``create_plan`` to distinguish "user fed in a structured plan
    that drifted from strict shape" (warn loudly) from "user fed in free
    prose that was never canonical to begin with" (silent fallback to
    Claude). The match is intentionally looser than
    :data:`_STRICT_STEPS_H2_RE` — trailing whitespace on the H2 line still
    counts as "trying to be canonical" even though it fails strict
    extraction.
    """
    body = _body_after_frontmatter(text)
    return bool(re.search(r"^##\s+Steps\s*$", body, re.MULTILINE))


def extract_canonical_steps(text: str) -> Optional[list[CanonicalStep]]:
    """Strict reader for the canonical ``## Steps`` section.

    Returns the ordered list of :class:`CanonicalStep` s when the
    source's Steps section matches the byte-exact canonical shape (same
    headings, same blank-line discipline, same trailing newline).
    Returns ``None`` on anything else (no Steps H2, drifted shape,
    mid-section prose, …) so the caller can fall back to the Claude
    path.

    Strictness is enforced via a re-render round-trip rather than
    ad-hoc "does this line look right" checks: parsed steps are passed
    back through :func:`_render_steps_section` and the result must
    equal the source slice byte-for-byte (modulo the single trailing
    newline at the section boundary). Any drift — extra blank line,
    non-canonical heading form, malformed ``Files:`` bullet, stray
    prose — fails the equality check and the function returns ``None``.
    """
    body = _body_after_frontmatter(text)

    h2 = _STRICT_STEPS_H2_RE.search(body)
    if h2 is None:
        return None
    section_start = h2.end()

    next_h2 = re.search(r"\n## \S", body[section_start:])
    if next_h2 is not None:
        section_text = body[section_start : section_start + next_h2.start()]
    else:
        section_text = body[section_start:]

    heads = list(_STRICT_STEP_HEAD_RE.finditer(section_text))
    if not heads:
        return None

    steps: list[CanonicalStep] = []
    for i, head in enumerate(heads):
        ordinal = int(head.group(1))
        if ordinal != i + 1:
            return None
        title = head.group(2)
        body_start = head.end()
        body_end = (
            heads[i + 1].start() if i + 1 < len(heads) else len(section_text)
        )
        step_body = section_text[body_start:body_end]

        change_type = _parse_strict_type_line(step_body)
        files = _parse_strict_labeled_block(step_body, "Files")
        creates = _parse_strict_labeled_block(step_body, "Creates")
        depends_on = _parse_strict_depends_line(step_body)
        steps.append(
            CanonicalStep(
                title=title,
                files=files,
                creates=creates,
                depends_on=depends_on,
                change_type=change_type,
            )
        )

    re_rendered = _render_steps_section(steps)
    if re_rendered + "\n" != "## Steps\n" + section_text:
        return None

    return steps


def read_canonical_provenance(text: str) -> Optional[CanonicalProvenance]:
    """Lift a :class:`CanonicalProvenance` out of a canonical file's text.

    Returns ``None`` when there's no frontmatter, when the frontmatter
    YAML doesn't parse, or when no ``source`` key is present. Tolerates
    extra unknown keys (forward-compat for future provenance fields).

    The producer of these frontmatters (``plan-tool reformat``) was
    removed in BACKLOG #40. This reader is preserved so legacy canonical
    files on disk still carry their provenance forward into
    ``create --from-existing``.
    """
    try:
        split = _split_frontmatter(text)
    except ParseError:
        return None
    try:
        raw = yaml.safe_load(split.frontmatter_yaml)
    except yaml.YAMLError:
        return None
    if not isinstance(raw, dict):
        return None
    source = raw.get("source")
    if not isinstance(source, str) or not source.strip():
        return None
    plan_details = raw.get("plan_details")
    if plan_details is not None and not isinstance(plan_details, str):
        plan_details = None
    return CanonicalProvenance(
        source=source.strip(),
        plan_details=plan_details.strip() if isinstance(plan_details, str) else None,
    )


def _parse_strict_labeled_block(step_body: str, label: str) -> list[str]:
    """Collect ``- `path``` bullets directly under a ``<label>:`` line.

    Shared by the ``Files:`` (existing files modified) and ``Creates:``
    (new files added) blocks — both carry an identical path-bullet shape.
    Stops at the first line that doesn't match the strict bullet shape;
    any drift is caught downstream by
    :func:`extract_canonical_steps`'s round-trip check, so this helper
    only needs to gather the bullets it can definitively recognize.
    """
    m = re.search(rf"^{re.escape(label)}:$", step_body, re.MULTILINE)
    if not m:
        return []
    after = step_body[m.end():]
    if not after.startswith("\n"):
        return []
    paths: list[str] = []
    for line in after[1:].splitlines():
        bullet = _STRICT_PATH_BULLET_RE.match(line)
        if not bullet:
            break
        paths.append(bullet.group(1))
    return paths


def _parse_strict_type_line(step_body: str) -> Optional[str]:
    """Parse a ``Type: refactor|feature|non-code`` line; absent or
    out-of-range → ``None``.

    The closed alternation in :data:`_STRICT_TYPE_RE` is the canonical-
    side validity gate: an out-of-range value (``Type: chore``) matches
    nothing, leaves ``change_type`` ``None``, the renderer omits the
    line, and the byte-exact round-trip in :func:`extract_canonical_steps`
    mismatches — so a mistyped type falls the whole source back to the
    Claude path rather than producing a step with a silently-dropped type.
    """
    m = _STRICT_TYPE_RE.search(step_body)
    if not m:
        return None
    return m.group(1)


def _parse_strict_depends_line(step_body: str) -> list[int]:
    """Parse a ``Depends on: 1, 2`` line; absent or malformed → ``[]``."""
    m = _STRICT_DEPENDS_RE.search(step_body)
    if not m:
        return []
    try:
        return [int(x.strip()) for x in m.group(1).split(",")]
    except ValueError:
        return []


def _render_steps_section(steps: list[CanonicalStep]) -> str:
    """Build the ``## Steps`` H2 block followed by one ``### N.`` per step.

    Used by :func:`extract_canonical_steps` for round-trip equality
    enforcement. Not part of any public write path — the writer that
    historically used this (``plan-tool reformat``) was removed in
    BACKLOG #40.
    """
    parts: list[str] = ["## Steps"]
    for i, step in enumerate(steps, start=1):
        parts.append(_render_step(i, step))
    return "\n\n".join(parts)


def _render_step(ordinal: int, step: CanonicalStep) -> str:
    """Emit one ``### N. Title`` block with an optional Type line and
    optional Files / Creates / Depends on blocks.

    Inner blocks are joined with the same ``\\n\\n`` separator the
    section-level join uses, so a blank line surrounds each block on both
    sides. The fixed block order is ``Type:`` (refactor/feature/non-code
    classification), then ``Files:`` (existing files modified),
    ``Creates:`` (new files added), then ``Depends on:`` — ``Type:`` sits
    first because it classifies the step as a whole, not a file footprint.
    A source that orders these differently fails
    :func:`extract_canonical_steps`'s byte-exact round-trip and falls
    back to the Claude path.
    """
    blocks: list[str] = [f"### {ordinal}. {step.title}"]
    if step.change_type:
        blocks.append(f"Type: {step.change_type}")
    if step.files:
        files_lines = "\n".join(f"- `{f}`" for f in step.files)
        blocks.append(f"Files:\n{files_lines}")
    if step.creates:
        creates_lines = "\n".join(f"- `{f}`" for f in step.creates)
        blocks.append(f"Creates:\n{creates_lines}")
    if step.depends_on:
        deps = ", ".join(str(d) for d in step.depends_on)
        blocks.append(f"Depends on: {deps}")
    return "\n\n".join(blocks)
