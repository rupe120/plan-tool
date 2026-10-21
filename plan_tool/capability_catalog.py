"""App-level capability catalog: parse ``CAPABILITIES.md``, extract MISSION
principle ids, and enumerate the CLI surface.

A **capability** is a durable feature of the implemented app, mapped to the
MISSION.md grounding principle(s) it serves — distinct from the per-plan
``features:`` registry (transient, inward-pointing). See ``CAPABILITIES.md``
and CLAUDE.md.

This module is a **leaf**: it imports only stdlib at module load. The CLI
enumerator pulls ``build_parser`` via a *deferred* import so a consumer in the
``plan_tool.cli`` package (``cli/inspect.py``) can import this without a cycle.
The deterministic, no-Claude honesty check is layered on top (see
:func:`check_capabilities`).
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Principle:
    """One MISSION.md grounding principle: its stable kebab-slug ``id`` and
    the heading ``title`` it was assigned to (position prefix stripped)."""

    id: str
    title: str


@dataclass(frozen=True)
class Capability:
    """One ``CAPABILITIES.md`` entry. ``surfaces`` are CLI subcommand names
    and/or repo-relative module paths; ``principles`` are MISSION principle
    ids the capability serves."""

    id: str
    title: str
    surfaces: tuple[str, ...]
    principles: tuple[str, ...]


# A principle id is a kebab slug carried in an HTML comment under its heading:
#   ### 3. Keep the plan true to live code
#   <!-- principle-id: keep-the-plan-true-to-code -->
# The ``[a-z0-9-]+`` class deliberately excludes the scheme-note's ``…``
# placeholder, so that documentation line never parses as a real id.
_PRINCIPLE_ID_RE = re.compile(r"<!--\s*principle-id:\s*([a-z0-9][a-z0-9-]*)\s*-->")
_HEADING_RE = re.compile(r"^#{1,6}\s+(.*\S)\s*$")
_POSITION_PREFIX_RE = re.compile(r"^\d+\.\s*")


def extract_principle_ids(mission_text: str) -> list[Principle]:
    """Parse MISSION.md text into the ordered list of declared principles.

    Each ``<!-- principle-id: slug -->`` comment is paired with the nearest
    preceding heading for its title (the volatile ``N. `` position prefix is
    stripped, since the slug — not the number — is the stable handle).
    """
    principles: list[Principle] = []
    last_heading: Optional[str] = None
    for line in mission_text.splitlines():
        heading = _HEADING_RE.match(line)
        if heading:
            last_heading = heading.group(1).strip()
            continue
        m = _PRINCIPLE_ID_RE.search(line)
        if m:
            title = _POSITION_PREFIX_RE.sub("", last_heading or "")
            principles.append(Principle(id=m.group(1), title=title))
    return principles


def read_principle_ids(repo_root: Path) -> list[Principle]:
    """Read ``MISSION.md`` at the repo root and extract its principles.

    Returns ``[]`` when MISSION.md is absent or unreadable — the honesty check
    treats "no principles found" as its own finding rather than crashing."""
    mission = repo_root / "MISSION.md"
    try:
        text = mission.read_text(encoding="utf-8")
    except OSError:
        return []
    return extract_principle_ids(text)


def enumerate_subcommands() -> list[str]:
    """The plan-tool subcommand primary names, aliases collapsed.

    Mirrors ``cli_reference``'s enumeration: argparse stores one pseudo-action
    per *primary* in ``_choices_actions`` (aliases share the parser object but
    not the pseudo-action), so ``ca.dest`` yields each command once. The
    ``build_parser`` import is deferred so this leaf module stays importable
    from inside the ``plan_tool.cli`` package without a cycle."""
    from plan_tool.cli import build_parser

    parser = build_parser()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return [ca.dest for ca in action._choices_actions]
    return []


# ``## `` heading starts a capability block iff a ``- id:`` line follows; the
# fields are ``key: `a`, `b``` (backtick-wrapped, comma-separated) bullet lines.
_CAP_HEADING_RE = re.compile(r"^##\s+(.*\S)\s*$")
# Tolerates plain (``- id:``) and bold (``- **id:**``) field styles.
_CAP_FIELD_RE = re.compile(r"^-\s+\*{0,2}(id|surfaces|principles):\*{0,2}\s*(.*)$")
_BACKTICK_RE = re.compile(r"`([^`]+)`")


@dataclass(frozen=True)
class _RawBlock:
    title: str
    fields: dict[str, str]


def _split_capability_blocks(doc_text: str) -> list[_RawBlock]:
    """Group the doc into ``## `` blocks carrying recognized field lines."""
    blocks: list[_RawBlock] = []
    title: Optional[str] = None
    fields: dict[str, str] = {}
    for line in doc_text.splitlines():
        heading = _CAP_HEADING_RE.match(line)
        if heading:
            if title is not None:
                blocks.append(_RawBlock(title, fields))
            title = heading.group(1).strip()
            fields = {}
            continue
        if title is None:
            continue
        field = _CAP_FIELD_RE.match(line)
        if field:
            fields[field.group(1)] = field.group(2).strip()
    if title is not None:
        blocks.append(_RawBlock(title, fields))
    return blocks


def _parse_values(raw: str) -> tuple[str, ...]:
    """Backtick-wrapped, comma-separated values → a tuple. Falls back to a
    bare comma split when no backticks are present (lenient on author style)."""
    ticked = _BACKTICK_RE.findall(raw)
    if ticked:
        return tuple(v.strip() for v in ticked if v.strip())
    return tuple(v.strip() for v in raw.split(",") if v.strip())


def parse_capabilities(doc_text: str) -> tuple[list[Capability], list[str]]:
    """Parse ``CAPABILITIES.md`` text into ``(capabilities, problems)``.

    A ``## `` block is a capability iff it carries an ``- id:`` line; prose
    sections (no ``id``) are skipped. ``problems`` collects malformed-doc
    findings the honesty check surfaces rather than crashing on: a capability
    block missing ``surfaces``/``principles``, an unparseable ``id``, or a
    duplicate ``id``. The capability ``id`` is a diff-stable handle only —
    nothing tags against it — so it is validated for shape, never as a referent.
    """
    capabilities: list[Capability] = []
    problems: list[str] = []
    seen_ids: set[str] = set()
    for block in _split_capability_blocks(doc_text):
        if "id" not in block.fields:
            continue  # prose section, not a capability
        cid = block.fields["id"].strip().strip("`").strip()
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", cid or ""):
            problems.append(
                f"capability '{block.title}' has a missing or malformed id "
                f"(expected a kebab slug, got '{cid}')"
            )
            continue
        if cid in seen_ids:
            problems.append(f"duplicate capability id '{cid}'")
            continue
        seen_ids.add(cid)
        missing = [k for k in ("surfaces", "principles") if k not in block.fields]
        if missing:
            problems.append(
                f"capability '{cid}' is missing {' and '.join(missing)}"
            )
            continue
        capabilities.append(
            Capability(
                id=cid,
                title=block.title,
                surfaces=_parse_values(block.fields["surfaces"]),
                principles=_parse_values(block.fields["principles"]),
            )
        )
    return capabilities, problems


def read_capabilities(
    repo_root: Path,
) -> Optional[tuple[list[Capability], list[str]]]:
    """Read + parse ``CAPABILITIES.md`` at the repo root.

    Returns ``None`` when the doc is absent (the honesty check is inert then),
    distinct from a present-but-empty/malformed doc (returns parsed results +
    problems)."""
    doc = repo_root / "CAPABILITIES.md"
    try:
        text = doc.read_text(encoding="utf-8")
    except OSError:
        return None
    return parse_capabilities(text)


@dataclass(frozen=True)
class CapabilityFinding:
    """One advisory honesty-check finding. ``code`` is one of ``malformed-doc``
    / ``absent-surface`` / ``no-valid-principle`` / ``orphan-subcommand`` /
    ``unserved-principle``."""

    code: str
    message: str


# Subcommands intentionally left without an owning capability — they won't be
# flagged as orphans. Empty today; add a primary name here to deliberately omit
# one so the check doesn't nag forever.
CAPABILITY_ALLOWLIST: frozenset[str] = frozenset()


def _surface_exists(surface: str, repo_root: Path, subcommands: set[str]) -> bool:
    """A surface resolves if it's a real subcommand primary name or a module
    path present at HEAD. A path-shaped surface (ends ``.py`` or contains ``/``)
    is checked on disk; everything else is matched against the subcommand set."""
    if surface.endswith(".py") or "/" in surface:
        return (repo_root / surface).is_file()
    return surface in subcommands


def check_capabilities(repo_root: Path) -> list[CapabilityFinding]:
    """Repo-wide, no-Claude honesty check for ``CAPABILITIES.md``.

    Returns advisory findings — it never raises and never gates an exit code.
    **Inert** (returns ``[]``) when ``CAPABILITIES.md`` is absent. Flags: a
    capability citing a surface absent at HEAD; a capability citing an invalid
    (typo'd or retired) principle id, or none; a subcommand (primary name,
    aliases collapsed, allowlist-aware) with no owning capability; a principle
    no capability serves; and a present-but-malformed doc (``parse_capabilities``
    problems). See CAPABILITIES.md for the taxonomy.
    """
    result = read_capabilities(repo_root)
    if result is None:
        return []
    capabilities, problems = result
    findings = [CapabilityFinding("malformed-doc", m) for m in problems]

    principle_ids = {p.id for p in read_principle_ids(repo_root)}
    subcommands = set(enumerate_subcommands())
    owned: set[str] = set()
    served: set[str] = set()

    for cap in capabilities:
        for s in cap.surfaces:
            if not _surface_exists(s, repo_root, subcommands):
                findings.append(
                    CapabilityFinding(
                        "absent-surface",
                        f"capability '{cap.id}' cites surface '{s}', absent at HEAD",
                    )
                )
        if not cap.principles:
            findings.append(
                CapabilityFinding(
                    "no-valid-principle",
                    f"capability '{cap.id}' references no principle",
                )
            )
        for p in cap.principles:
            if p not in principle_ids:
                findings.append(
                    CapabilityFinding(
                        "no-valid-principle",
                        f"capability '{cap.id}' cites principle id '{p}', "
                        f"not a valid MISSION principle at HEAD",
                    )
                )
        owned.update(s for s in cap.surfaces if s in subcommands)
        served.update(p for p in cap.principles if p in principle_ids)

    for sub in sorted(subcommands - owned - CAPABILITY_ALLOWLIST):
        findings.append(
            CapabilityFinding(
                "orphan-subcommand", f"subcommand '{sub}' has no owning capability"
            )
        )
    for pid in sorted(principle_ids - served):
        findings.append(
            CapabilityFinding(
                "unserved-principle", f"principle '{pid}' is served by no capability"
            )
        )
    return findings
