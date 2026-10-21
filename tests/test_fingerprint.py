"""Tests for plan_tool.fingerprint — the shared code-side digest producer
both the completeness and reconcile families compute against.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from plan_tool.fingerprint import compute_code_fingerprint, diff_code_fingerprint
from plan_tool.schema import Plan, Step


def _fingerprint_plan(detail: str = "docs/details/step-1.md") -> Plan:
    """Plan with two declared code files plus a per-step detail file —
    the detail and plan markdown must never appear in the fingerprint."""
    return Plan(
        title="Demo",
        status="planning",
        priority="medium",
        steps=[
            Step(
                id=1,
                title="Stub",
                files=["src/foo.py", "src/bar.py"],
                detail=detail,
            ),
        ],
    )


def _seed_code_files(tmp_path: Path) -> Path:
    """Write the plan markdown, the detail file, and the two declared code
    files under ``tmp_path``; return the plan path."""
    plan_path = tmp_path / "docs" / "plans" / "demo.md"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text("# plan", encoding="utf-8")
    detail = tmp_path / "docs" / "details" / "step-1.md"
    detail.parent.mkdir(parents=True, exist_ok=True)
    detail.write_text("# detail", encoding="utf-8")
    src = tmp_path / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "foo.py").write_text("foo = 1\n", encoding="utf-8")
    (src / "bar.py").write_text("bar = 2\n", encoding="utf-8")
    return plan_path


def test_code_fingerprint_covers_declared_code_files(tmp_path: Path) -> None:
    """Every on-disk declared code path is a key mapped to its SHA-256."""
    plan = _fingerprint_plan()
    plan_path = _seed_code_files(tmp_path)

    fp = compute_code_fingerprint(plan, plan_path, tmp_path)

    assert set(fp) == {"src/foo.py", "src/bar.py"}
    assert fp["src/foo.py"] == hashlib.sha256(b"foo = 1\n").hexdigest()
    assert fp["src/bar.py"] == hashlib.sha256(b"bar = 2\n").hexdigest()


def test_code_fingerprint_excludes_plan_and_detail(tmp_path: Path) -> None:
    """Neither the plan markdown nor any detail file appears as a key —
    the complement of compute_plan_fingerprint's surface."""
    plan = _fingerprint_plan()
    plan_path = _seed_code_files(tmp_path)

    fp = compute_code_fingerprint(plan, plan_path, tmp_path)

    assert "docs/plans/demo.md" not in fp
    assert "docs/details/step-1.md" not in fp


def test_code_fingerprint_skips_missing_declared_file(tmp_path: Path) -> None:
    """A declared file not on disk yields no key and does not raise."""
    plan = _fingerprint_plan()
    plan_path = _seed_code_files(tmp_path)
    (tmp_path / "src" / "bar.py").unlink()

    fp = compute_code_fingerprint(plan, plan_path, tmp_path)

    assert "src/bar.py" not in fp
    assert "src/foo.py" in fp


def test_code_fingerprint_keys_are_relative_posix(tmp_path: Path) -> None:
    """Every key is a repo-relative posix string — no absolute path or
    backslash, so the map compares across clones."""
    plan = _fingerprint_plan()
    plan_path = _seed_code_files(tmp_path)

    fp = compute_code_fingerprint(plan, plan_path, tmp_path)

    for key in fp:
        assert not Path(key).is_absolute()
        assert "\\" not in key


def test_code_fingerprint_is_deterministic(tmp_path: Path) -> None:
    """Two calls on identical disk state return equal maps with identical
    key order."""
    plan = _fingerprint_plan()
    plan_path = _seed_code_files(tmp_path)

    first = compute_code_fingerprint(plan, plan_path, tmp_path)
    second = compute_code_fingerprint(plan, plan_path, tmp_path)

    assert first == second
    assert list(first) == list(second)
    assert list(first) == sorted(first)


def test_code_fingerprint_changes_on_byte_edit(tmp_path: Path) -> None:
    """Mutating one watched file's bytes changes only that file's digest."""
    plan = _fingerprint_plan()
    plan_path = _seed_code_files(tmp_path)

    before = compute_code_fingerprint(plan, plan_path, tmp_path)
    (tmp_path / "src" / "foo.py").write_text("foo = 999\n", encoding="utf-8")
    after = compute_code_fingerprint(plan, plan_path, tmp_path)

    assert after["src/foo.py"] != before["src/foo.py"]
    assert after["src/bar.py"] == before["src/bar.py"]


def test_code_fingerprint_empty_when_no_code_files(tmp_path: Path) -> None:
    """A plan whose steps declare no code files returns ``{}``."""
    plan = Plan(
        title="Demo",
        status="planning",
        priority="medium",
        steps=[Step(id=1, title="Docs only", detail="docs/details/step-1.md")],
    )
    plan_path = tmp_path / "docs" / "plans" / "demo.md"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text("# plan", encoding="utf-8")

    assert compute_code_fingerprint(plan, plan_path, tmp_path) == {}


def test_code_fingerprint_reexported_from_completeness_report() -> None:
    """The completeness family still reaches the producer at its old import
    site — the same object, now sourced from this leaf."""
    from plan_tool import completeness_report

    assert completeness_report.compute_code_fingerprint is compute_code_fingerprint


def test_diff_code_fingerprint_identical_maps_match(tmp_path: Path) -> None:
    """Equal maps drift nowhere — ``match`` with empty lists."""
    fp = {"src/foo.py": "h", "src/bar.py": "g"}

    diff = diff_code_fingerprint(fp, dict(fp), tmp_path)
    assert diff.match is True
    assert diff.content_drifted == []
    assert diff.footprint_added == []
    assert diff.footprint_removed == []


def test_diff_code_fingerprint_changed_digest(tmp_path: Path) -> None:
    """Same key, differing digest → content drift on that file."""
    diff = diff_code_fingerprint(
        {"src/foo.py": "h1"}, {"src/foo.py": "h2"}, tmp_path
    )

    assert diff.match is False
    assert diff.content_drifted == [(tmp_path / "src" / "foo.py").resolve()]
    assert diff.footprint_added == []
    assert diff.footprint_removed == []


def test_diff_code_fingerprint_deleted_key_is_membership_not_content(
    tmp_path: Path,
) -> None:
    """A key only in saved is footprint removal — not content drift."""
    diff = diff_code_fingerprint({"src/foo.py": "h"}, {}, tmp_path)

    assert diff.match is False
    assert diff.content_drifted == []
    assert diff.footprint_removed == [(tmp_path / "src" / "foo.py").resolve()]
    assert diff.footprint_added == []


def test_diff_code_fingerprint_new_key_is_membership_not_content(
    tmp_path: Path,
) -> None:
    """A key only in current is footprint addition — not content drift."""
    diff = diff_code_fingerprint({}, {"src/foo.py": "h"}, tmp_path)

    assert diff.match is False
    assert diff.content_drifted == []
    assert diff.footprint_added == [(tmp_path / "src" / "foo.py").resolve()]
    assert diff.footprint_removed == []


def test_diff_code_fingerprint_combined(tmp_path: Path) -> None:
    """Content change stays in content_drifted; membership stays separate."""
    saved = {"src/changed.py": "h1", "src/deleted.py": "g"}
    current = {"src/changed.py": "h2", "src/new.py": "n"}

    diff = diff_code_fingerprint(saved, current, tmp_path)

    assert diff.match is False
    root = tmp_path.resolve()
    assert diff.content_drifted == [(root / "src/changed.py").resolve()]
    assert diff.footprint_removed == [(root / "src/deleted.py").resolve()]
    assert diff.footprint_added == [(root / "src/new.py").resolve()]
    assert diff.any_path_change == sorted(
        (root / rel).resolve()
        for rel in ("src/changed.py", "src/deleted.py", "src/new.py")
    )


def test_diff_code_fingerprint_drifted_code_is_absolute_resolved_sorted(
    tmp_path: Path,
) -> None:
    """Every returned path is absolute, under ``repo_root.resolve()``, and
    the list is sorted."""
    saved = {"z/last.py": "h", "a/first.py": "g"}

    diff = diff_code_fingerprint(saved, {}, tmp_path)

    root = tmp_path.resolve()
    assert diff.footprint_removed == sorted(diff.footprint_removed)
    for path in diff.footprint_removed:
        assert path.is_absolute()
        assert path.is_relative_to(root)


def test_diff_code_fingerprint_empty_maps_match(tmp_path: Path) -> None:
    """Two empty maps drift nowhere."""
    diff = diff_code_fingerprint({}, {}, tmp_path)
    assert diff.match is True
    assert diff.any_path_change == []


def test_detail_bundle_fingerprint_hashes_present_detail(tmp_path: Path) -> None:
    """Each step's on-disk detail file is a key → its SHA-256 (BACKLOG #61)."""
    from plan_tool.fingerprint import compute_detail_bundle_fingerprint

    plan = _fingerprint_plan()  # step 1, detail=docs/details/step-1.md
    plan_path = _seed_code_files(tmp_path)  # writes that detail file
    fp = compute_detail_bundle_fingerprint(plan, plan_path, tmp_path)
    assert fp == {
        "docs/details/step-1.md": hashlib.sha256(b"# detail").hexdigest()
    }


def test_detail_bundle_fingerprint_omits_bare_step(tmp_path: Path) -> None:
    """A step whose detail file is not on disk contributes no key — its
    absence is the bare-state signal, not a placeholder."""
    from plan_tool.fingerprint import compute_detail_bundle_fingerprint

    plan = Plan(
        title="Demo",
        status="planning",
        priority="medium",
        steps=[
            Step(id=1, title="A", files=["src/foo.py"],
                 detail="docs/details/step-1.md"),
            Step(id=2, title="B", files=["src/bar.py"],
                 detail="docs/details/step-2.md"),  # bare: no file written
        ],
    )
    plan_path = _seed_code_files(tmp_path)  # writes step-1.md only
    fp = compute_detail_bundle_fingerprint(plan, plan_path, tmp_path)
    assert "docs/details/step-1.md" in fp
    assert "docs/details/step-2.md" not in fp


def _write_jira_artifact(plan_path: Path, plan: Plan, step: Step, body: str) -> Path:
    """Write ``body`` at ``step``'s canonical jira-grade path; return it."""
    from plan_tool.detail_artifacts import derive_jira_detail_path

    path = derive_jira_detail_path(plan_path, plan, step)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_detail_bundle_fingerprint_grade_jira_keys(tmp_path: Path) -> None:
    """At jira grade the keys are the on-disk ``jira/`` artifacts; a step with
    no artifact contributes none."""
    from plan_tool.fingerprint import compute_detail_bundle_fingerprint

    plan = Plan(
        title="Demo",
        status="planning",
        priority="medium",
        steps=[
            Step(id=1, title="Alpha", detail="docs/details/step-1.md"),
            Step(id=2, title="Beta"),  # no jira artifact written
        ],
    )
    plan_path = _seed_code_files(tmp_path)
    written = _write_jira_artifact(plan_path, plan, plan.steps[0], "## Intent\n")
    fp = compute_detail_bundle_fingerprint(
        plan, plan_path, tmp_path, detail_grade="jira"
    )
    rel = written.relative_to(tmp_path).as_posix()
    assert fp == {rel: hashlib.sha256(b"## Intent\n").hexdigest()}
    assert "docs/plans/plan-details/demo/jira/02-beta.md" not in fp


def test_detail_bundle_fingerprint_grade_jira_ignores_pointer(
    tmp_path: Path,
) -> None:
    """``step.detail`` plays no part at jira grade — the run-grade file it
    points at is hashed neither instead of nor alongside the artifact."""
    from plan_tool.fingerprint import compute_detail_bundle_fingerprint

    plan = _fingerprint_plan()  # step 1, detail=docs/details/step-1.md
    plan_path = _seed_code_files(tmp_path)  # writes that run-grade detail file
    fp = compute_detail_bundle_fingerprint(
        plan, plan_path, tmp_path, detail_grade="jira"
    )
    # The pointer target exists on disk yet contributes nothing, and no
    # jira artifact was written, so the map is empty.
    assert fp == {}


def test_detail_bundle_fingerprint_default_unchanged(tmp_path: Path) -> None:
    """The default call still returns the run-grade pointer map, even when a
    jira artifact sits beside it."""
    from plan_tool.fingerprint import compute_detail_bundle_fingerprint

    plan = _fingerprint_plan()
    plan_path = _seed_code_files(tmp_path)
    _write_jira_artifact(plan_path, plan, plan.steps[0], "## Intent\n")
    expected = {"docs/details/step-1.md": hashlib.sha256(b"# detail").hexdigest()}
    assert compute_detail_bundle_fingerprint(plan, plan_path, tmp_path) == expected
    assert (
        compute_detail_bundle_fingerprint(
            plan, plan_path, tmp_path, detail_grade="run"
        )
        == expected
    )


# --- compute_purity_cache_key -------------------------------------------

from plan_tool.fingerprint import (  # noqa: E402
    PURITY_VERDICT_LOGIC_VERSION,
    PurityKeyComponents,
    compute_purity_cache_key,
)
from plan_tool.schema import ChangeType  # noqa: E402


def _purity_plan(
    *,
    change_type: ChangeType | None = ChangeType.REFACTOR,
    depends_on: list[int] | None = None,
    depends_on_notes: dict[int, str] | None = None,
    creates: list[str] | None = None,
    files: list[str] | None = None,
    title: str = "Stub",
    complexity=None,
) -> Plan:
    """Plan whose step 1 (the one under test) declares src/foo.py + src/bar.py
    (seeded by ``_seed_code_files``) with a detail file and a change_type. A
    trivial step 2 exists so ``depends_on=[2]`` validates."""
    return Plan(
        title="Demo",
        status="planning",
        priority="medium",
        steps=[
            Step(
                id=1,
                title=title,
                files=files or ["src/foo.py", "src/bar.py"],
                creates=creates or [],
                change_type=change_type,
                depends_on=depends_on or [],
                depends_on_notes=depends_on_notes or {},
                complexity=complexity,
                detail="docs/details/step-1.md",
            ),
            Step(id=2, title="Downstream"),
        ],
    )


def test_purity_cache_key_is_deterministic(tmp_path: Path) -> None:
    """Two calls on identical disk state return the same combined hex."""
    plan = _purity_plan()
    plan_path = _seed_code_files(tmp_path)

    first, _ = compute_purity_cache_key(plan, plan_path, plan.steps[0], tmp_path)
    second, _ = compute_purity_cache_key(plan, plan_path, plan.steps[0], tmp_path)

    assert first == second


def test_purity_cache_key_changes_on_detail_edit(tmp_path: Path) -> None:
    """Editing the step's detail-file bytes changes the key."""
    plan = _purity_plan()
    plan_path = _seed_code_files(tmp_path)

    before, _ = compute_purity_cache_key(plan, plan_path, plan.steps[0], tmp_path)
    (tmp_path / "docs" / "details" / "step-1.md").write_text(
        "# detail changed", encoding="utf-8"
    )
    after, _ = compute_purity_cache_key(plan, plan_path, plan.steps[0], tmp_path)

    assert after != before


def test_purity_cache_key_changes_on_declared_file_edit(tmp_path: Path) -> None:
    """Editing a declared ``files:`` file (detail unchanged) changes the key —
    the core soundness case proving the key isn't detail-only."""
    plan = _purity_plan()
    plan_path = _seed_code_files(tmp_path)

    before, _ = compute_purity_cache_key(plan, plan_path, plan.steps[0], tmp_path)
    (tmp_path / "src" / "foo.py").write_text("foo = 999\n", encoding="utf-8")
    after, _ = compute_purity_cache_key(plan, plan_path, plan.steps[0], tmp_path)

    assert after != before


def test_purity_cache_key_covers_creates_entries(tmp_path: Path) -> None:
    """Editing a ``creates:`` file's bytes changes the key — proves it grounds
    on ``all_files``, not just ``files``."""
    plan = _purity_plan(creates=["src/new.py"])
    plan_path = _seed_code_files(tmp_path)
    (tmp_path / "src" / "new.py").write_text("new = 1\n", encoding="utf-8")

    before, _ = compute_purity_cache_key(plan, plan_path, plan.steps[0], tmp_path)
    (tmp_path / "src" / "new.py").write_text("new = 2\n", encoding="utf-8")
    after, _ = compute_purity_cache_key(plan, plan_path, plan.steps[0], tmp_path)

    assert after != before


def test_purity_cache_key_changes_on_absent_declared_path(tmp_path: Path) -> None:
    """Adding a declared ``files:`` path that does NOT resolve on disk still
    changes the key — the prompt renders the declared list, so a content-only
    fingerprint would serve a stale hit. Guards the declared-path-set residual."""
    plan_path = _seed_code_files(tmp_path)
    before_plan = _purity_plan()
    after_plan = _purity_plan(files=["src/foo.py", "src/bar.py", "src/absent.py"])
    # src/absent.py is never written to disk.

    before, before_comps = compute_purity_cache_key(
        before_plan, plan_path, before_plan.steps[0], tmp_path
    )
    after, after_comps = compute_purity_cache_key(
        after_plan, plan_path, after_plan.steps[0], tmp_path
    )

    assert after != before
    # The isolated all_files_fingerprint must move too (step 4 grades on it).
    assert after_comps.all_files_fingerprint != before_comps.all_files_fingerprint


def test_purity_cache_key_changes_on_change_type_flip(tmp_path: Path) -> None:
    """Flipping ``change_type`` (refactor→feature) with detail and all files
    unchanged changes the key — the HIGH-finding soundness case."""
    plan_path = _seed_code_files(tmp_path)
    refactor = _purity_plan(change_type=ChangeType.REFACTOR)
    feature = _purity_plan(change_type=ChangeType.FEATURE)

    before, _ = compute_purity_cache_key(
        refactor, plan_path, refactor.steps[0], tmp_path
    )
    after, _ = compute_purity_cache_key(
        feature, plan_path, feature.steps[0], tmp_path
    )

    assert after != before


def test_purity_cache_key_changes_on_depends_on_edit(tmp_path: Path) -> None:
    """Changing ``depends_on`` (detail/files unchanged) changes the key."""
    plan_path = _seed_code_files(tmp_path)
    plan_a = _purity_plan(depends_on=[])
    plan_b = _purity_plan(depends_on=[2])

    before, _ = compute_purity_cache_key(plan_a, plan_path, plan_a.steps[0], tmp_path)
    after, _ = compute_purity_cache_key(plan_b, plan_path, plan_b.steps[0], tmp_path)

    assert after != before


def test_purity_cache_key_stable_when_title_or_complexity_changes(
    tmp_path: Path,
) -> None:
    """Changing only ``title``/``complexity`` leaves the key unchanged
    (decision 5 — those are excluded)."""
    from plan_tool.schema import Complexity

    plan_path = _seed_code_files(tmp_path)
    base = _purity_plan(title="Stub", complexity=None)
    changed = _purity_plan(title="Different", complexity=Complexity.HIGH)

    before, _ = compute_purity_cache_key(base, plan_path, base.steps[0], tmp_path)
    after, _ = compute_purity_cache_key(
        changed, plan_path, changed.steps[0], tmp_path
    )

    assert after == before


def test_purity_cache_key_stable_when_depends_on_notes_changes(
    tmp_path: Path,
) -> None:
    """Changing only ``depends_on_notes`` leaves the key unchanged."""
    plan_path = _seed_code_files(tmp_path)
    base = _purity_plan(depends_on=[2])
    changed = _purity_plan(
        depends_on=[2],
        depends_on_notes={2: "consumes downstream stub"},
    )

    before, _ = compute_purity_cache_key(base, plan_path, base.steps[0], tmp_path)
    after, _ = compute_purity_cache_key(
        changed, plan_path, changed.steps[0], tmp_path
    )

    assert after == before


def test_depends_on_notes_references_confined_to_allowlist() -> None:
    """``depends_on_notes`` must not leak into grading/gating until explicitly
    allowlisted. Step 2 adds transform carriers in ``create`` and ``scope_out``;
    step 3 adds create authoring (proposal parse, manual wizard, iterate preserve);
    step 4 adds read-only review display in ``create``. ``bench`` clears notes
    when isolating a step for files-coherence scoring (not note grading)."""
    allowlist = {
        "plan_tool/schema.py",
        "plan_tool/create.py",
        "plan_tool/scope_out.py",
        "plan_tool/bench.py",
    }
    root = Path(__file__).resolve().parents[1] / "plan_tool"
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        if "depends_on_notes" not in path.read_text(encoding="utf-8"):
            continue
        rel = path.relative_to(root.parent).as_posix()
        if rel not in allowlist:
            offenders.append(rel)
    assert offenders == []


def test_purity_cache_key_changes_on_logic_version_bump(
    tmp_path: Path, monkeypatch
) -> None:
    """Bumping ``PURITY_VERDICT_LOGIC_VERSION`` with every input unchanged
    changes the combined key (prompt-version-invalidation guard)."""
    import plan_tool.fingerprint as fp_mod

    plan = _purity_plan()
    plan_path = _seed_code_files(tmp_path)

    before, _ = compute_purity_cache_key(plan, plan_path, plan.steps[0], tmp_path)
    monkeypatch.setattr(
        fp_mod, "PURITY_VERDICT_LOGIC_VERSION", PURITY_VERDICT_LOGIC_VERSION + 1
    )
    after, _ = compute_purity_cache_key(plan, plan_path, plan.steps[0], tmp_path)

    assert after != before


# The purity-verdict region of the co-tenanted detail-quality.md prompt: from
# the MIXED-STEP criteria header through the structural-findings output format,
# stopping before the altitude/findings guidance that is tuned independently and
# does not steer the MIXED-STEP verdict. Scoping the drift-guard to this region
# (rather than the whole file) keeps unrelated prompt edits from cold-invalidating
# the entire purity cache. See the "drift-guard invalidation scope" residual.
_PURITY_SECTION_START = "## Step purity (refactor vs feature)"
_PURITY_SECTION_END = "## Conceptual altitude advisories"


def _purity_prompt_verdict_text(prompt: str) -> str:
    """Slice detail-quality.md to just its MIXED-STEP verdict region. Falls back
    to the whole prompt if either boundary header is missing (fail-safe: over-
    invalidate rather than silently under-cover a moved section)."""
    start = prompt.find(_PURITY_SECTION_START)
    if start == -1:
        return prompt
    end = prompt.find(_PURITY_SECTION_END, start)
    return prompt[start:] if end == -1 else prompt[start:end]


def test_purity_verdict_logic_version_bumped_on_logic_change() -> None:
    """Drift-guard: the MIXED-STEP verdict logic — the *purity region* of
    ``detail-quality.md`` (not the whole co-tenanted file), ``parse_mixed_step_findings``,
    and ``_format_tests_directive`` (the change_type-framing channel) — is
    hashed and pinned to the current ``PURITY_VERDICT_LOGIC_VERSION``. Editing that
    logic changes the hash and fails this test: bump ``PURITY_VERDICT_LOGIC_VERSION``
    in fingerprint.py and update the pinned ``(version, hash)`` below. Editing
    *unrelated* regions of detail-quality.md does not trip it (that is the point —
    it avoids cold-invalidating the whole cache on a grounding/altitude tweak).
    """
    import inspect

    from plan_tool.detail import _format_tests_directive
    from plan_tool.granularity import parse_mixed_step_findings
    from plan_tool.renderer import prompts_dir

    # (version, hash) pin — bump both together when the logic changes.
    PINNED_VERSION = 2
    PINNED_HASH = (
        "4ab60839d1c94fb4ae5feff54d11526a2d9cc0d0d74c531dee369f36173ac3fa"
    )

    prompt = (prompts_dir() / "detail-quality.md").read_text(encoding="utf-8")
    h = hashlib.sha256()
    h.update(_purity_prompt_verdict_text(prompt).encode("utf-8"))
    h.update(inspect.getsource(parse_mixed_step_findings).encode("utf-8"))
    h.update(inspect.getsource(_format_tests_directive).encode("utf-8"))

    assert PURITY_VERDICT_LOGIC_VERSION == PINNED_VERSION, (
        "PURITY_VERDICT_LOGIC_VERSION changed but the drift-guard pin was not "
        "updated — update PINNED_VERSION/PINNED_HASH to match."
    )
    assert h.hexdigest() == PINNED_HASH, (
        "MIXED-STEP verdict logic (detail-quality.md, parse_mixed_step_findings, "
        "or _format_tests_directive) changed. Bump "
        "PURITY_VERDICT_LOGIC_VERSION in plan_tool/fingerprint.py and update "
        "PINNED_VERSION/PINNED_HASH here."
    )


def test_purity_prompt_verdict_text_scopes_to_the_region() -> None:
    """The drift-guard slice covers the purity-verdict region and excludes the
    independently-tuned sections — so an unrelated prompt edit does not trip it."""
    prompt = (
        "## What to do\nintro\n"
        "## Step purity (refactor vs feature)\nPURITY CRITERIA\n"
        "## Structural findings\nOUTPUT FORMAT\n"
        "## Conceptual altitude advisories\nALTITUDE GUIDANCE\n"
        "## Findings\nfinal\n"
    )
    region = _purity_prompt_verdict_text(prompt)
    assert "PURITY CRITERIA" in region and "OUTPUT FORMAT" in region
    assert "ALTITUDE GUIDANCE" not in region and "intro" not in region
    # Editing an excluded section leaves the slice byte-identical (no false bump).
    edited = prompt.replace("ALTITUDE GUIDANCE", "ALTITUDE GUIDANCE, reworded")
    assert _purity_prompt_verdict_text(edited) == region
    # Editing the purity region does change the slice (a real bump).
    changed = prompt.replace("PURITY CRITERIA", "PURITY CRITERIA v2")
    assert _purity_prompt_verdict_text(changed) != region


def test_purity_prompt_verdict_text_falls_back_to_whole_prompt() -> None:
    """If the boundary header is missing (renamed/removed), fall back to the whole
    prompt — fail-safe over-invalidation, never silent under-coverage."""
    no_start = "## Something else\nbody\n## Findings\nx\n"
    assert _purity_prompt_verdict_text(no_start) == no_start
    no_end = "## Step purity (refactor vs feature)\ncriteria\n## Findings\nx\n"
    assert _purity_prompt_verdict_text(no_end).startswith("## Step purity")
    assert "criteria" in _purity_prompt_verdict_text(no_end)


def test_purity_cache_key_exposes_components(tmp_path: Path) -> None:
    """The returned components carry each field, and ``all_files_fingerprint``
    moves on an all_files edit while ``detail_hash`` moves on a detail edit —
    proving they are individually comparable (what step 4 needs)."""
    plan = _purity_plan(depends_on=[2], change_type=ChangeType.REFACTOR)
    plan_path = _seed_code_files(tmp_path)

    _, comps = compute_purity_cache_key(plan, plan_path, plan.steps[0], tmp_path)
    assert comps.detail_hash == hashlib.sha256(b"# detail").hexdigest()
    assert comps.change_type == "refactor"
    assert comps.depends_on == (2,)
    assert comps.logic_version == PURITY_VERDICT_LOGIC_VERSION
    assert isinstance(comps.all_files_fingerprint, str)

    # An all_files edit moves all_files_fingerprint but not detail_hash.
    (tmp_path / "src" / "foo.py").write_text("foo = 42\n", encoding="utf-8")
    _, comps2 = compute_purity_cache_key(plan, plan_path, plan.steps[0], tmp_path)
    assert comps2.all_files_fingerprint != comps.all_files_fingerprint
    assert comps2.detail_hash == comps.detail_hash

    # A detail edit moves detail_hash but not all_files_fingerprint.
    (tmp_path / "docs" / "details" / "step-1.md").write_text(
        "# other", encoding="utf-8"
    )
    _, comps3 = compute_purity_cache_key(plan, plan_path, plan.steps[0], tmp_path)
    assert comps3.detail_hash != comps2.detail_hash
    assert comps3.all_files_fingerprint == comps2.all_files_fingerprint


def test_purity_cache_key_stable_when_unrelated_file_changes(
    tmp_path: Path,
) -> None:
    """Editing a file outside this step's detail + all_files leaves the key
    unchanged."""
    plan = _purity_plan()
    plan_path = _seed_code_files(tmp_path)
    (tmp_path / "src" / "unrelated.py").write_text("x = 1\n", encoding="utf-8")

    before, _ = compute_purity_cache_key(plan, plan_path, plan.steps[0], tmp_path)
    (tmp_path / "src" / "unrelated.py").write_text("x = 2\n", encoding="utf-8")
    after, _ = compute_purity_cache_key(plan, plan_path, plan.steps[0], tmp_path)

    assert after == before


def test_purity_cache_key_missing_detail_does_not_raise(tmp_path: Path) -> None:
    """A step whose detail file isn't on disk returns a key without raising;
    its ``detail_hash`` is ``None``."""
    plan = _purity_plan()
    plan_path = _seed_code_files(tmp_path)
    (tmp_path / "docs" / "details" / "step-1.md").unlink()

    key, comps = compute_purity_cache_key(plan, plan_path, plan.steps[0], tmp_path)
    assert isinstance(key, str)
    assert comps.detail_hash is None


def test_purity_cache_key_missing_declared_file_does_not_raise(
    tmp_path: Path,
) -> None:
    """A declared file absent from disk is omitted and does not raise."""
    plan = _purity_plan()
    plan_path = _seed_code_files(tmp_path)
    (tmp_path / "src" / "bar.py").unlink()

    key, _ = compute_purity_cache_key(plan, plan_path, plan.steps[0], tmp_path)
    assert isinstance(key, str)


def test_purity_cache_key_returns_digest_and_components(tmp_path: Path) -> None:
    """The return is a (str, PurityKeyComponents) tuple whose first element is
    a 64-char lowercase hex string."""
    plan = _purity_plan()
    plan_path = _seed_code_files(tmp_path)

    key, comps = compute_purity_cache_key(plan, plan_path, plan.steps[0], tmp_path)
    assert isinstance(key, str)
    assert len(key) == 64
    assert key == key.lower()
    assert all(c in "0123456789abcdef" for c in key)
    assert isinstance(comps, PurityKeyComponents)
