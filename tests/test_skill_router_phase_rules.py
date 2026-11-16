"""The installed routers name, per phase, the DIRECTIVES.md sections a driving session must read.

A session that reads DIRECTIVES.md by search hit skips whole sections (measured
2026-10-28, BACKLOG #518), so each router carries one phase table. The table is
the same in all three routers, every section it names must still exist, and the
checklist rules the incident broke stay in it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from plan_tool.review import fenced_spans

ROOT = Path(__file__).resolve().parent.parent
BACKENDS = ("claude", "codex", "cursor")
DIRECTIVES = ROOT / "integrations/shared/DIRECTIVES.md"
SECTION_HEADING = "## Read these `DIRECTIVES.md` sections before acting in a phase"
# phase -> (every section its row links, checklist sentences its row carries)
PHASES = {
    "Authoring": (
        (
            "explicit-overengineering-checkpoints",
            "pause-on-a-product-question--ask-dont-infer",
        ),
        ("Ask the user on a product question instead of inferring the answer.",),
    ),
    "Auditing": (
        (
            "gate-1--the-bare-plan-audit-before-detail",
            "gate-2--the-detail-grounded-audit-after-detail",
            "stage-differentiated-conceptual-bar-completeness-audit",
            "close-conceptual-gaps-through-judged-hand-edits",
            "before-applying-anything-audit-the-why-not-the-what",
            "trajectory-stopping-and-the-three-exits",
        ),
        (
            "Three audit snapshots are the minimum window, not a stopping point.",
            "Surface a scope move to the user before making it.",
            "Record each owner answer as one dated decision line in the plan.",
            "Present findings as the plan-gap map.",
        ),
    ),
    "Running": (
        (
            "--commit",
            "when-a-run-steps-own-tests-fail",
            "after-run-finishes-a-plan",
            "post-run-reconcile-tail-stop-rule",
            "the-two-reconcile-verbs-are-not-interchangeable",
        ),
        (
            "never mark a step `done` by hand.",
            "run `reconcile-code <name> --all`, then `/code-review` to convergence.",
        ),
    ),
    "Roadmap": (
        ("roadmap",),
        ("including its resume and refusal semantics.",),
    ),
}
MODEL_SELECTION = "which-model-to-run-a-subcommand-with"
LINK_RE = re.compile(r"\]\(DIRECTIVES\.md#([^)]+)\)")


def _slug(heading: str) -> str:
    """GitHub's anchor rule: lowercase, drop punctuation but keep hyphens, spaces to hyphens."""
    text = heading.replace("`", "").lower()
    return re.sub(r"[^a-z0-9 _-]", "", text).replace(" ", "-")


def _anchors(text: str) -> set[str]:
    """Anchors of the real headings: a ``#`` line inside a fence is not one, and a
    repeated heading gets GitHub's ``-1``, ``-2`` suffix."""
    fenced = fenced_spans(text)
    seen: dict[str, int] = {}
    anchors: set[str] = set()
    for m in re.finditer(r"^#{1,6} (.+)$", text, re.M):
        if any(start <= m.start() < end for start, end in fenced):
            continue
        base = _slug(m.group(1))
        count = seen.get(base, 0)
        anchors.add(base if count == 0 else f"{base}-{count}")
        seen[base] = count + 1
    return anchors


def _phase_section(router_text: str, label: str) -> str:
    assert router_text.count(SECTION_HEADING) == 1, f"{label} lost its phase table"
    start = router_text.index(SECTION_HEADING)
    end = router_text.find("\n## ", start + len(SECTION_HEADING))
    assert end != -1, f"{label}: no `##` section follows the phase table"
    return router_text[start:end]


def _router(backend: str) -> str:
    return (ROOT / f"integrations/{backend}/SKILL.md").read_text(encoding="utf-8")


def _rows(section: str) -> dict[str, str]:
    return {
        line.split("|")[1].strip(): line
        for line in section.splitlines()
        if line.startswith("| ") and not line.startswith("| ---")
    }


def test_phase_table_is_identical_across_the_three_routers() -> None:
    """Parity: one phase table, not three drifting copies (#386 asks for the relationship)."""
    sections = {b: _phase_section(_router(b), b) for b in BACKENDS}
    assert sections["claude"] == sections["codex"] == sections["cursor"]


@pytest.mark.parametrize("backend", BACKENDS)
def test_every_section_a_router_names_exists_in_directives(backend: str) -> None:
    anchors = _anchors(DIRECTIVES.read_text(encoding="utf-8"))
    linked = LINK_RE.findall(_phase_section(_router(backend), backend))
    assert linked, f"{backend} router names no DIRECTIVES.md section"
    missing = [a for a in linked if a not in anchors]
    assert not missing, f"{backend} router links headings DIRECTIVES.md no longer has: {missing}"


@pytest.mark.parametrize("backend", BACKENDS)
def test_each_phase_row_links_every_section_and_carries_its_checklist(backend: str) -> None:
    """The four broken rules live in the checklist text, so a deleted link or sentence fails."""
    rows = _rows(_phase_section(_router(backend), backend))
    for phase, (anchors, sentences) in PHASES.items():
        row = next((r for name, r in rows.items() if name.startswith(phase)), None)
        assert row is not None, f"{backend} router has no {phase} row"
        linked = LINK_RE.findall(row)
        assert linked == list(anchors), f"{backend} {phase} row links {linked}"
        for sentence in sentences:
            assert sentence in row, f"{backend} {phase} row lost: {sentence}"


@pytest.mark.parametrize("backend", BACKENDS)
def test_router_names_the_model_selection_section_for_every_phase(backend: str) -> None:
    """From #425: the pointer sits above the table, once, so no phase can skip it."""
    section = _phase_section(_router(backend), backend)
    assert section.count(f"DIRECTIVES.md#{MODEL_SELECTION})") == 1
    assert section.index(MODEL_SELECTION) < section.index("| Phase |")


def test_slug_and_anchor_rules_match_what_the_routers_already_rely_on() -> None:
    assert _slug("Which model to run a subcommand with") == MODEL_SELECTION
    assert _slug("Explicit overengineering checkpoints") == "explicit-overengineering-checkpoints"
    text = "# A\n\n```bash\n# not a heading\n```\n\n## B\n\n## B\n"
    assert _anchors(text) == {"a", "b", "b-1"}
