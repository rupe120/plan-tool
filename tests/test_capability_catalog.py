"""Unit tests for the capability catalog parser / extractor / enumerator."""

from __future__ import annotations

from pathlib import Path

from plan_tool.capability_catalog import (
    Capability,
    Principle,
    enumerate_subcommands,
    extract_principle_ids,
    parse_capabilities,
    read_capabilities,
    read_principle_ids,
)


# ---------- extract_principle_ids ----------

_MISSION = (
    "# Mission & grounding principles\n\n"
    "## Grounding principles\n\n"
    "Each principle carries a slug in `<!-- principle-id: … -->` (this is the\n"
    "scheme note, not a real id).\n\n"
    "### 1. Converge on the more-correct plan; mutate only when allowed\n"
    "<!-- principle-id: converge-on-correct-plan -->\n\n"
    "*tagline*\n\n"
    "### 2. Keep the plan true to live code\n"
    "<!-- principle-id: keep-the-plan-true-to-code -->\n\n"
    "body\n"
)


def test_extract_pairs_id_with_preceding_heading() -> None:
    got = extract_principle_ids(_MISSION)
    assert got == [
        Principle(
            id="converge-on-correct-plan",
            title="Converge on the more-correct plan; mutate only when allowed",
        ),
        Principle(
            id="keep-the-plan-true-to-code",
            title="Keep the plan true to live code",
        ),
    ]


def test_extract_strips_position_prefix_keeps_slug_stable() -> None:
    # The volatile "N. " number is dropped from the title; the slug is the id.
    [p] = extract_principle_ids(
        "### 7. Survive interruption\n<!-- principle-id: survive-interruption -->\n"
    )
    assert p.id == "survive-interruption"
    assert p.title == "Survive interruption"


def test_extract_ignores_ellipsis_placeholder_in_scheme_note() -> None:
    # The scheme-note line carries a literal "…", which is not a kebab slug, so
    # it must not parse as a principle.
    assert extract_principle_ids(
        "Each principle carries `<!-- principle-id: … -->`.\n"
    ) == []


# ---------- enumerate_subcommands ----------


def test_enumerate_returns_primary_names_collapsing_aliases() -> None:
    subs = enumerate_subcommands()
    # A representative primary is present...
    assert "reconcile-plan" in subs
    assert "completeness-audit" in subs
    # ...and its aliases are collapsed out (one entry per command).
    assert "reconcile" not in subs
    assert "review" not in subs
    assert len(subs) == len(set(subs))


# ---------- parse_capabilities ----------

_CLEAN_DOC = (
    "# title\n\nintro prose\n\n"
    "## Plan authoring\n"
    "- **id:** `plan-authoring`\n"
    "- **surfaces:** `create`, `detail`, `plan_tool/create.py`\n"
    "- **principles:** `converge-on-correct-plan`\n\n"
    "## How this is maintained\n\n"
    "This is a prose section with no id — it must be skipped.\n\n"
    "## Step execution\n"
    "- id: `step-execution`\n"
    "- surfaces: `run`\n"
    "- principles: `converge-on-correct-plan`, `deterministic-non-determinism`\n"
)


def test_parse_clean_doc_yields_capabilities_no_problems() -> None:
    caps, problems = parse_capabilities(_CLEAN_DOC)
    assert problems == []
    assert caps == [
        Capability(
            id="plan-authoring",
            title="Plan authoring",
            surfaces=("create", "detail", "plan_tool/create.py"),
            principles=("converge-on-correct-plan",),
        ),
        Capability(
            id="step-execution",
            title="Step execution",
            surfaces=("run",),
            principles=("converge-on-correct-plan", "deterministic-non-determinism"),
        ),
    ]


def test_parse_skips_prose_sections_without_id() -> None:
    caps, _ = parse_capabilities(_CLEAN_DOC)
    assert "How this is maintained" not in {c.title for c in caps}


def test_parse_flags_missing_fields() -> None:
    _, problems = parse_capabilities(
        "## Broken\n- **id:** `broken`\n- **surfaces:** `run`\n"
    )
    assert any("broken" in p and "principles" in p for p in problems)


def test_parse_flags_duplicate_id() -> None:
    doc = (
        "## A\n- id: `dup`\n- surfaces: `run`\n- principles: `p`\n\n"
        "## B\n- id: `dup`\n- surfaces: `jira`\n- principles: `p`\n"
    )
    caps, problems = parse_capabilities(doc)
    assert len(caps) == 1
    assert any("duplicate" in p and "dup" in p for p in problems)


def test_parse_flags_malformed_id() -> None:
    _, problems = parse_capabilities(
        "## Bad\n- id: `Not A Slug`\n- surfaces: `run`\n- principles: `p`\n"
    )
    assert any("malformed id" in p for p in problems)


# ---------- read_* (absent files) ----------


def test_read_principle_ids_absent_mission_returns_empty(tmp_path: Path) -> None:
    assert read_principle_ids(tmp_path) == []


def test_read_capabilities_absent_doc_returns_none(tmp_path: Path) -> None:
    # None (absent) is distinct from ([], []) (present but empty) — the check
    # is inert only when the doc is absent.
    assert read_capabilities(tmp_path) is None


def test_repo_capabilities_doc_is_self_consistent() -> None:
    # The shipped CAPABILITIES.md parses with zero problems (the deterministic
    # honesty check has its own coverage below; this guards parseability).
    result = read_capabilities(Path(__file__).resolve().parents[1])
    assert result is not None
    _caps, problems = result
    assert problems == []


# ---------- check_capabilities (honesty check) ----------

import pytest  # noqa: E402

from plan_tool.capability_catalog import check_capabilities  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_repo(tmp_path: Path, principle_ids, capabilities_md: str) -> None:
    mission = "## Grounding principles\n\n"
    for i, pid in enumerate(principle_ids, 1):
        mission += f"### {i}. Principle {i}\n<!-- principle-id: {pid} -->\n\n"
    (tmp_path / "MISSION.md").write_text(mission, encoding="utf-8")
    (tmp_path / "CAPABILITIES.md").write_text(capabilities_md, encoding="utf-8")


def _cap(title: str, cid: str, surfaces, principles) -> str:
    surf = ", ".join(f"`{s}`" for s in surfaces)
    prin = ", ".join(f"`{p}`" for p in principles)
    return f"## {title}\n- id: `{cid}`\n- surfaces: {surf}\n- principles: {prin}\n\n"


@pytest.fixture
def _two_subcommands(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "plan_tool.capability_catalog.enumerate_subcommands",
        lambda: ["create", "run"],
    )


def test_check_inert_when_doc_absent(tmp_path: Path) -> None:
    (tmp_path / "MISSION.md").write_text(
        "### 1. P\n<!-- principle-id: p1 -->\n", encoding="utf-8"
    )
    assert check_capabilities(tmp_path) == []  # no CAPABILITIES.md → inert


def test_check_clean_repo_no_findings(tmp_path: Path, _two_subcommands) -> None:
    _write_repo(
        tmp_path,
        ["p1"],
        _cap("A", "a", ["create"], ["p1"]) + _cap("B", "b", ["run"], ["p1"]),
    )
    assert check_capabilities(tmp_path) == []


def test_check_flags_orphan_subcommand(tmp_path: Path, _two_subcommands) -> None:
    _write_repo(tmp_path, ["p1"], _cap("A", "a", ["create"], ["p1"]))
    fs = check_capabilities(tmp_path)
    assert any(f.code == "orphan-subcommand" and "run" in f.message for f in fs)


def test_check_flags_absent_surface(tmp_path: Path, _two_subcommands) -> None:
    _write_repo(
        tmp_path,
        ["p1"],
        _cap("A", "a", ["create", "run", "nope-cmd", "plan_tool/ghost.py"], ["p1"]),
    )
    fs = check_capabilities(tmp_path)
    assert any(f.code == "absent-surface" and "nope-cmd" in f.message for f in fs)
    assert any(f.code == "absent-surface" and "ghost.py" in f.message for f in fs)
    # The real surfaces are not flagged.
    assert not any(f.code == "absent-surface" and "'create'" in f.message for f in fs)


def test_check_flags_invalid_principle_id(tmp_path: Path, _two_subcommands) -> None:
    # A retired/typo'd principle slug trips no-valid-principle even alongside a
    # valid one (Part D's retirement rule).
    _write_repo(
        tmp_path,
        ["p1"],
        _cap("A", "a", ["create"], ["p1", "retired-slug"])
        + _cap("B", "b", ["run"], ["p1"]),
    )
    fs = check_capabilities(tmp_path)
    assert any(
        f.code == "no-valid-principle" and "retired-slug" in f.message for f in fs
    )


def test_check_flags_unserved_principle(tmp_path: Path, _two_subcommands) -> None:
    _write_repo(
        tmp_path,
        ["p1", "p2"],
        _cap("A", "a", ["create"], ["p1"]) + _cap("B", "b", ["run"], ["p1"]),
    )
    fs = check_capabilities(tmp_path)
    assert any(f.code == "unserved-principle" and "p2" in f.message for f in fs)
    assert not any(f.code == "unserved-principle" and "'p1'" in f.message for f in fs)


def test_check_flags_malformed_doc(tmp_path: Path, _two_subcommands) -> None:
    _write_repo(tmp_path, ["p1"], _cap("A", "a", ["create"], ["p1"]))
    # Append a capability missing its principles field.
    with (tmp_path / "CAPABILITIES.md").open("a", encoding="utf-8") as fh:
        fh.write("## Broken\n- id: `broken`\n- surfaces: `run`\n")
    fs = check_capabilities(tmp_path)
    assert any(f.code == "malformed-doc" and "broken" in f.message for f in fs)


def test_check_real_repo_catalog_is_honest() -> None:
    # Regression guard: the shipped CAPABILITIES.md stays honest against the
    # live CLI surface + MISSION principles. Trips if a subcommand is added
    # without cataloging it, or a cited surface/principle is renamed away.
    assert check_capabilities(_REPO_ROOT) == []
