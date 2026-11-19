"""The installed routers name, per phase, the DIRECTIVES.md sections a driving session must read.

A session that reads DIRECTIVES.md by search hit skips whole sections (measured
2026-10-28, BACKLOG #518), so each router carries one phase table. The table is
the same in all three routers, every section it names must still exist, and the
checklist rules the incident broke stay in it.
"""

from __future__ import annotations

import pytest

from tests.skill_router_phase import (
    DIRECTIVES,
    LINK_RE,
    ROOT,
    anchors,
    phase_section,
    slug,
)

BACKENDS = ("claude", "codex", "cursor")
# phase -> (every section its row links, checklist sentences its row carries)
PHASES = {
    "Authoring": (
        (
            "authoring-hygiene",
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
            "Three audit snapshots are the minimum window; stop only at one of the three exits.",
            "Surface a scope move to the user before making it.",
            "Record an owner's answer to a product question as one dated decision line in the plan.",
            "Present in-scope plan-level findings as the plan-gap map.",
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
            "with `--commit` unless the user withholds commits (then one step at a time)",
            "never mark a step `done` by hand-editing.",
            "run `reconcile-code <name> --all`, then a code-review pass to convergence;",
            "the reconcile tail has its own stop rule.",
        ),
    ),
    "Roadmap": (
        ("roadmap",),
        ("including its resume and refusal semantics.",),
    ),
}
MODEL_SELECTION = "which-model-to-run-a-subcommand-with"


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
    sections = {b: phase_section(_router(b), b) for b in BACKENDS}
    assert sections["claude"] == sections["codex"] == sections["cursor"]


@pytest.mark.parametrize("backend", BACKENDS)
def test_every_section_a_router_names_exists_in_directives(backend: str) -> None:
    known = anchors(DIRECTIVES.read_text(encoding="utf-8"))
    linked = LINK_RE.findall(phase_section(_router(backend), backend))
    assert linked, f"{backend} router names no DIRECTIVES.md section"
    missing = [a for a in linked if a not in known]
    assert not missing, f"{backend} router links headings DIRECTIVES.md no longer has: {missing}"


@pytest.mark.parametrize("backend", BACKENDS)
def test_each_phase_row_links_every_section_and_carries_its_checklist(backend: str) -> None:
    """The four broken rules live in the checklist text, so a deleted link or sentence fails."""
    rows = _rows(phase_section(_router(backend), backend))
    for phase, (expected_links, sentences) in PHASES.items():
        matches = [r for name, r in rows.items() if name.startswith(phase)]
        assert len(matches) == 1, f"{backend} router has {len(matches)} {phase} rows"
        row = matches[0]
        linked = LINK_RE.findall(row)
        assert linked == list(expected_links), f"{backend} {phase} row links {linked}"
        for sentence in sentences:
            assert sentence in row, f"{backend} {phase} row lost: {sentence}"


@pytest.mark.parametrize("backend", BACKENDS)
def test_router_names_the_model_selection_section_for_every_phase(backend: str) -> None:
    """From #425: the pointer sits above the table, once, so no phase can skip it."""
    section = phase_section(_router(backend), backend)
    assert section.count(f"DIRECTIVES.md#{MODEL_SELECTION})") == 1
    assert section.index(MODEL_SELECTION) < section.index("| Phase |")
    # The section's own rule omits --backend/--model when backends.json exists, so the
    # router must defer to the rule and never tell a session to pass them.
    assert "apply its selection rule for backend and model" in section
    assert "pass them explicitly" not in section


def test_slug_and_anchor_rules_match_what_the_routers_already_rely_on() -> None:
    assert slug("Which model to run a subcommand with") == MODEL_SELECTION
    assert slug("Explicit overengineering checkpoints") == "explicit-overengineering-checkpoints"
    text = "# A\n\n```bash\n# not a heading\n```\n\n## B\n\n## B\n"
    assert anchors(text) == {"a", "b", "b-1"}
