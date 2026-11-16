"""The installed routers name, per phase, the DIRECTIVES.md sections a driving session must read.

A session that reads DIRECTIVES.md by search hit skips whole sections (measured
2026-10-28, BACKLOG #518), so each router carries one phase table. The table is
the same in all three routers, and every section it names must still exist.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BACKENDS = ("claude", "codex", "cursor")
DIRECTIVES = ROOT / "integrations/shared/DIRECTIVES.md"
SECTION_HEADING = "## Read these `DIRECTIVES.md` sections before acting in a phase"
PHASES = {
    "Authoring": ("explicit-overengineering-checkpoints",),
    "Auditing": (
        "gate-1--the-bare-plan-audit-before-detail",
        "trajectory-stopping-and-the-three-exits",
        "before-applying-anything-audit-the-why-not-the-what",
    ),
    "Running": ("--commit", "after-run-finishes-a-plan"),
    "Roadmap": ("roadmap",),
}
MODEL_SELECTION = "which-model-to-run-a-subcommand-with"
LINK_RE = re.compile(r"\]\(DIRECTIVES\.md#([^)]+)\)")


def _slug(heading: str) -> str:
    """GitHub's anchor rule: lowercase, drop punctuation but keep hyphens, spaces to hyphens."""
    text = heading.replace("`", "").lower()
    return re.sub(r"[^a-z0-9 _-]", "", text).replace(" ", "-")


def _directive_anchors() -> set[str]:
    return {
        _slug(m.group(1))
        for m in re.finditer(r"^#{1,6} (.+)$", DIRECTIVES.read_text(encoding="utf-8"), re.M)
    }


def _phase_section(backend: str) -> str:
    text = (ROOT / f"integrations/{backend}/SKILL.md").read_text(encoding="utf-8")
    assert text.count(SECTION_HEADING) == 1, f"{backend} router lost its phase table"
    start = text.index(SECTION_HEADING)
    end = text.index("\n## ", start + len(SECTION_HEADING))
    return text[start:end]


def test_phase_table_is_identical_across_the_three_routers() -> None:
    """Parity: one phase table, not three drifting copies (#386 asks for the relationship)."""
    sections = {b: _phase_section(b) for b in BACKENDS}
    assert sections["claude"] == sections["codex"] == sections["cursor"]


@pytest.mark.parametrize("backend", BACKENDS)
def test_every_section_a_router_names_exists_in_directives(backend: str) -> None:
    anchors = _directive_anchors()
    linked = LINK_RE.findall(_phase_section(backend))
    assert linked, f"{backend} router names no DIRECTIVES.md section"
    missing = [a for a in linked if a not in anchors]
    assert not missing, f"{backend} router links headings DIRECTIVES.md no longer has: {missing}"


@pytest.mark.parametrize("backend", BACKENDS)
def test_router_names_each_phase_and_its_load_bearing_sections(backend: str) -> None:
    section = _phase_section(backend)
    rows = {
        line.split("|")[1].strip(): line
        for line in section.splitlines()
        if line.startswith("| ") and not line.startswith("| ---")
    }
    for phase, anchors in PHASES.items():
        row = next((r for name, r in rows.items() if name.startswith(phase)), None)
        assert row is not None, f"{backend} router has no {phase} row"
        for anchor in anchors:
            assert f"DIRECTIVES.md#{anchor})" in row, f"{backend} {phase} row omits #{anchor}"


@pytest.mark.parametrize("backend", BACKENDS)
def test_router_names_the_model_selection_section_for_every_phase(backend: str) -> None:
    """From #425: the pointer sits above the table, once, so no phase can skip it."""
    section = _phase_section(backend)
    assert section.count(f"DIRECTIVES.md#{MODEL_SELECTION})") == 1
    assert section.index(MODEL_SELECTION) < section.index("| Phase |")


def test_slug_matches_the_anchors_the_routers_already_rely_on() -> None:
    """Pins the anchor rule against two links that predate the table."""
    assert _slug("Which model to run a subcommand with") == MODEL_SELECTION
    assert _slug("Explicit overengineering checkpoints") == "explicit-overengineering-checkpoints"
