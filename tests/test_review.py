"""Tests for plan_tool.review — plan-vs-codebase reality check.

The real `claude` CLI is never invoked; every test that reaches
`review_plan` supplies an injected fake ``Invoker`` or ``invoker=None``.
"""

from __future__ import annotations

import dataclasses
import io
import json
import sys
from pathlib import Path
from typing import Optional

import pytest

from plan_tool import parse_plan, style
from plan_tool.parser import ParseError
from plan_tool.parser import ValidationError as ParserValidationError
from plan_tool.progress import NullReporter, ProgressReporter, StepHandle
from plan_tool.review import (
    fenced_spans,
    APPLY_ELIGIBLE_SOURCES,
    CARRIED_RESOLUTION_APPLIED,
    CARRIED_RESOLUTION_OPEN,
    CARRIED_RESOLUTION_SKIPPED,
    CarriedFinding,
    DETAIL_ALTITUDE_SOURCE,
    DepIssue,
    FINDING_DOMAIN_CODE_LOGIC,
    FINDING_DOMAIN_DOCS,
    FINDING_DOMAIN_UNIT_TEST,
    FINDING_DOMAIN_UNKNOWN,
    FINDING_DOMAINS,
    FileCheck,
    FileExistence,
    HeuristicHit,
    MERGE_ACTION_MERGE,
    MERGE_ACTION_REGROUND,
    MergeAction,
    PathStyleHint,
    Recommendation,
    Redirect,
    ReviewError,
    STRUCTURAL_SOURCES,
    StepFileCheck,
    _BARE_MECHANISM_PROTECTED_PHRASES,
    _CARRIED_BLOCK_MAX_FINDINGS,
    _CARRIED_BODY_EXCERPT_CHARS,
    _GRANULARITY_MERGE_SOURCE,
    _code_reveals_split_recommendations,
    _derive_symbols,
    _describe_file_check,
    _extract_seed_scope_contract,
    _format_carried_findings_block,
    _format_intent_block,
    _format_scope_contract_block,
    _promote_missing_parents,
    _reground_already_built_recommendation,
    _render_severity_banner,
    assemble_carried_findings,
    assemble_report,
    check_criteria_fulfillment,
    check_file_existence,
    check_input_contract_references,
    check_plan_audit,
    check_test_strategy_alignment,
    classify_finding_domain,
    classify_likely_bare_mechanism,
    collect_deterministic_findings,
    confidence_label,
    detect_path_style_mismatch,
    extract_recommendations,
    emit_triage_summary,
    format_recommendation_for_apply,
    extract_and_append_review_lessons,
    heuristic_already_done,
    is_apply_eligible,
    is_pairwise_merge_finding,
    is_structural,
    parse_merge_action,
    render_merge_action,
    restated_property_or_none,
    render_review_prompt,
    recommendation_from_persisted_mapping,
    review_plan,
    review_plan_full,
    triage_reason,
    validate_deps,
)
from plan_tool.granularity import (
    GRANULARITY_MERGE_SOURCE,
    GranularityEvidence,
    assess_granularity,
)
from plan_tool.schema import Plan, PlanStatus, Priority, Step, StepStatus


# A plan fixture that deliberately embeds:
#   - step 1 (done): real file on disk → OK control
#   - step 2 (current): real file, no symbol collision → OK control
#   - step 3 (pending): file whose parent dir is missing → MISSING_PARENT WARN
#   - step 4 (pending): real file that already defines the title's symbol →
#     heuristic WARN
_REVIEW_PLAN = """---
title: Review Test Plan
status: in-progress
priority: medium
steps:
  - id: 1
    title: Build the parser
    files:
      - parser.py
    status: done
  - id: 2
    title: Wire up the renderer
    files:
      - renderer.py
    depends_on: [1]
    status: current
  - id: 3
    title: Add foo endpoint
    files:
      - missing_dir/foo_endpoint.py
    depends_on: [2]
  - id: 4
    title: Add bar utility
    files:
      - utils.py
    depends_on: [2]
---

# Review Test Plan
"""


_REVIEW_PLAN_WITH_DETAIL_TEMPLATE = """---
title: Review Test Plan With Detail
status: in-progress
priority: medium
steps:
  - id: 1
    title: Build the parser
    files:
      - parser.py
    status: done
  - id: 2
    title: Wire up the renderer
    files:
      - renderer.py
    detail: details/step-2-detail.md
    depends_on: [1]
    status: current
  - id: 3
    title: Add foo endpoint
    files:
      - missing_dir/foo_endpoint.py
    depends_on: [2]
  - id: 4
    title: Add bar utility
    files:
      - utils.py
    depends_on: [2]
---

# Review Test Plan With Detail
"""


def _write_review_fixture_with_detail(
    tmp_path: Path,
    *,
    detail_body: str = "## Acceptance criteria\n\nAcceptance criteria here.\n",
    missing_detail: bool = False,
) -> Path:
    """Write a plan whose step 2 has a `detail:` pointer, plus the source files."""
    plan_path = tmp_path / "1-review-test-detail.md"
    plan_path.write_text(_REVIEW_PLAN_WITH_DETAIL_TEMPLATE, encoding="utf-8")
    (tmp_path / "parser.py").write_text(
        "class Parser:\n    pass\n", encoding="utf-8"
    )
    (tmp_path / "renderer.py").write_text(
        "def render(plan):\n    return None\n", encoding="utf-8"
    )
    (tmp_path / "utils.py").write_text(
        "def bar():\n    return 1\n", encoding="utf-8"
    )
    if not missing_detail:
        details_dir = tmp_path / "details"
        details_dir.mkdir()
        (details_dir / "step-2-detail.md").write_text(
            detail_body, encoding="utf-8"
        )
    return plan_path


def _write_review_fixture(tmp_path: Path) -> Path:
    """Write plan + supporting repo files; return the plan path."""
    plan_path = tmp_path / "1-review-test.md"
    plan_path.write_text(_REVIEW_PLAN, encoding="utf-8")
    # Step 1: file exists, content mentions Parser — but step is done, so the
    # heuristic must skip it. Keeps the control clean.
    (tmp_path / "parser.py").write_text(
        "class Parser:\n    pass\n", encoding="utf-8"
    )
    # Step 2: file exists. Content uses a SHORTER token that does NOT match
    # any ``_PATTERN_TEMPLATES`` substring for the derived symbol "renderer".
    # ``def render(plan)`` has no substring "def renderer" in it.
    (tmp_path / "renderer.py").write_text(
        "def render(plan):\n    return None\n", encoding="utf-8"
    )
    # Step 3: deliberately no ``missing_dir/`` — MISSING_PARENT trigger.
    # Step 4: file exists, contains ``def bar`` which matches the "bar" token.
    (tmp_path / "utils.py").write_text(
        "def bar():\n    return 1\n", encoding="utf-8"
    )
    return plan_path


# --- _derive_symbols -------------------------------------------------------


class TestDeriveSymbols:
    def test_strips_stopwords(self) -> None:
        assert _derive_symbols("Add the foo endpoint") == ["foo", "endpoint"]

    def test_drops_short_tokens(self) -> None:
        assert _derive_symbols("Do X now") == []

    def test_deduplicates_case_insensitively(self) -> None:
        got = _derive_symbols("Refactor Foo into foo")
        assert [s.lower() for s in got] == ["foo"]

    def test_preserves_casing_of_first_occurrence(self) -> None:
        got = _derive_symbols("Wire up the RendererBase component")
        assert got == ["RendererBase", "component"]


# --- check_file_existence --------------------------------------------------


def test_recommendation_defaults_to_limited() -> None:
    rec = Recommendation(
        id="rec-1",
        source="claude",
        severity="medium",
        step_id=None,
        title="title",
        body="body",
    )

    assert rec.confidence == "limited"


def test_confidence_label_renders_stored_values_without_reclassification() -> None:
    assert confidence_label("supported") == "confidence: supported"
    assert confidence_label("limited") == "confidence: limited"
    assert confidence_label(None) == "confidence: unknown"

    rec = Recommendation(
        id="legacy", source="heuristic", severity="info", step_id=None,
        title="Legacy value", body="Keep the stored value.", confidence=None,
    )
    assert "confidence: unknown" in format_recommendation_for_apply(rec)


def test_format_recommendation_for_apply_carries_the_restatement() -> None:
    """The apply-driving Claude call is the one place a misread citation
    actually gets acted on, so it must see ``restated_property`` -- not
    just the persisted report, which the apply flow never consults."""
    rec = Recommendation(
        id="bare-gap", source="plan-correctness", severity="high",
        step_id=None, title="title", body="body",
        restated_property="the safety net has no route for this case",
    )
    rendered = format_recommendation_for_apply(rec)
    assert "the safety net has no route for this case" in rendered
    assert "restatement" in rendered.lower()


def test_format_recommendation_for_apply_omits_restatement_block_when_absent() -> None:
    rec = Recommendation(
        id="no-restated", source="plan-correctness", severity="high",
        step_id=None, title="title", body="body",
    )
    assert "restat" not in format_recommendation_for_apply(rec).lower()


def test_format_recommendation_for_apply_strips_bodys_own_trailing_whitespace() -> None:
    """``body`` moved from the last concatenated element to an interior one
    once a restatement can follow it -- the overall ``.strip()`` no longer
    cleans body's own trailing whitespace, so body must be stripped itself.
    Regression test for a corrupted apply-prompt separator (five newlines
    instead of one blank line) between body and the restatement block."""
    rec = Recommendation(
        id="trailing-ws", source="plan-correctness", severity="high",
        step_id=None, title="title", body="text\n\n\n",
        restated_property="evidence text",
    )
    rendered = format_recommendation_for_apply(rec)
    assert "\n\n\n\n" not in rendered
    assert "text\n\nPlan-altitude restatement" in rendered


def test_format_recommendation_for_apply_handles_empty_body_with_restatement() -> None:
    """The trailing-whitespace fix above covers only a non-empty body; an
    outright empty body is a sibling case the block-filtering rewrite
    closes for the whole class rather than one input at a time."""
    rec = Recommendation(
        id="empty-body", source="plan-correctness", severity="high",
        step_id=None, title="title", body="",
        restated_property="evidence text",
    )
    rendered = format_recommendation_for_apply(rec)
    assert "\n\n\n" not in rendered
    assert "confidence: limited\n\nPlan-altitude restatement" in rendered


@pytest.mark.parametrize(
    "restated_property,expected",
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("  evidence  ", "evidence"),
    ],
)
def test_restated_property_or_none(restated_property, expected) -> None:
    """The single source every render site now shares -- a whitespace-only
    value must read as absent, the same as a genuinely absent one."""
    rec = Recommendation(
        id="x", source="plan-correctness", severity="high", step_id=None,
        title="t", body="b", restated_property=restated_property,
    )
    assert restated_property_or_none(rec) == expected


def test_persisted_recommendation_restores_a_typed_redirect() -> None:
    rec = Recommendation(
        id="redirect", source="run-reconcile", severity="medium", step_id=1,
        title="Redirect", body="Follow up in the plan.",
        redirect=Redirect(reason="plan-owned", suggested_next="plan-tool detail demo"),
    )

    loaded = recommendation_from_persisted_mapping(dataclasses.asdict(rec))

    assert loaded.redirect == rec.redirect


@pytest.mark.parametrize(
    "field_name", ["purity_verdict_provenance", "file_path", "target_signature"]
)
def test_persisted_mapping_rejects_non_string_optional_text_fields(
    field_name,
) -> None:
    """Round-5 regression: round 4 centralized this type check for only 3
    of 6 free-text Optional[str] fields on Recommendation, leaving these
    three with the same crash-far-from-load-site shape round 4 fixed for
    restated_property (file_path's non-string form crashes later in
    _collect_finding_path_mentions's paths.add(...), a TypeError on an
    unhashable list, confirmed by direct execution)."""
    raw = {
        "id": "x", "source": "reconcile", "severity": "medium",
        "step_id": 1, "title": "t", "body": "b", field_name: ["not", "a", "string"],
    }
    with pytest.raises(ValueError, match=f"{field_name} must be a string or null"):
        recommendation_from_persisted_mapping(raw)


def test_carried_finding_rendering_preserves_stored_confidence() -> None:
    rec = Recommendation(
        id="supported", source="deps", severity="high", step_id=1,
        title="Dependency gap", body="Resolve the dependency.",
        anchor="dependency-gap", confidence="supported",
    )
    carried = assemble_carried_findings([rec])
    assert carried[0].confidence == "supported"
    assert "confidence: supported" in _format_carried_findings_block(carried)


class TestCheckFileExistence:
    def test_classifies_each_step(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        results = check_file_existence(plan, tmp_path)

        by_id = {r.step_id: r for r in results}
        assert by_id[1].files[0].status == FileExistence.OK
        assert by_id[2].files[0].status == FileExistence.OK
        # Parent dir `missing_dir/` doesn't exist → MISSING_PARENT, not NEW.
        assert by_id[3].files[0].status == FileExistence.MISSING_PARENT
        assert by_id[4].files[0].status == FileExistence.OK

    def test_new_when_parent_exists(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: New\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Create foo\n"
            "    files:\n"
            "      - new_file.py\n"
            "---\n",
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)
        results = check_file_existence(plan, tmp_path)
        # Parent `tmp_path` exists; file doesn't → NEW, not MISSING_PARENT.
        assert results[0].files[0].status == FileExistence.NEW

    def test_empty_files_list(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: Empty\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: noop\n"
            "---\n",
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)
        results = check_file_existence(plan, tmp_path)
        assert results[0].files == []


class TestInputContractPlannedPaths:
    """A detail's ``## Input`` anchor naming a module an earlier step
    ``creates:`` is a forward dependency contract, not drift. See BUG_BACKLOG."""

    def _plan(self, tmp_path: Path, *, creates: str) -> Path:
        (tmp_path / "details").mkdir(exist_ok=True)
        (tmp_path / "details" / "02.md").write_text(
            "# Step 2\n\n## Input\n\n"
            "Consumes `pkg/new_module.py:Thing`.\n\n"
            "## Implementation\n\nDo it.\n",
            encoding="utf-8",
        )
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: Planned paths\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: build the module\n"
            f"    creates: [{creates}]\n"
            "    status: current\n"
            "  - id: 2\n"
            "    title: consume the module\n"
            "    detail: details/02.md\n"
            "    status: pending\n"
            "---\n",
            encoding="utf-8",
        )
        return plan_path

    def test_anchor_on_a_sibling_steps_creates_is_not_flagged(
        self, tmp_path: Path
    ) -> None:
        plan_path = self._plan(tmp_path, creates="pkg/new_module.py")
        plan = parse_plan(plan_path)
        issues = check_input_contract_references(plan, plan_path, tmp_path)
        assert issues == []

    def test_anchor_no_step_creates_is_still_flagged(self, tmp_path: Path) -> None:
        plan_path = self._plan(tmp_path, creates="pkg/other_module.py")
        plan = parse_plan(plan_path)
        issues = check_input_contract_references(plan, plan_path, tmp_path)
        assert len(issues) == 1
        assert "does not exist" in issues[0].reason


class TestCreatesFootprint:
    """A step's ``creates:`` list — files it brings into existence — is
    classified but exempt from the missing/doesn't-resolve findings."""

    def _plan(self, tmp_path: Path, *, status: str = "current") -> Path:
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: Creates\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: build a brand new module tree\n"
            "    creates:\n"
            "      - brand/new/tree/module.py\n"
            f"    status: {status}\n"
            "---\n",
            encoding="utf-8",
        )
        return plan_path

    def test_created_file_marked_and_classified(self, tmp_path: Path) -> None:
        plan = parse_plan(self._plan(tmp_path))
        fc = check_file_existence(plan, tmp_path)[0].files[0]
        # Parent tree doesn't exist → MISSING_PARENT, but flagged created.
        assert fc.status == FileExistence.MISSING_PARENT
        assert fc.created is True

    def test_created_missing_parent_emits_no_recommendation(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import _file_check_recommendation

        plan = parse_plan(self._plan(tmp_path))
        step = plan.steps[0]
        fc = check_file_existence(plan, tmp_path)[0].files[0]
        rec = _file_check_recommendation(fc, step, plan_name="p")
        assert rec is None

    def test_created_missing_on_done_step_flagged(self, tmp_path: Path) -> None:
        from plan_tool.review import _file_check_recommendation

        plan = parse_plan(self._plan(tmp_path, status="done"))
        step = plan.steps[0]
        fc = check_file_existence(plan, tmp_path)[0].files[0]
        rec = _file_check_recommendation(fc, step, plan_name="p")
        assert rec is not None
        assert rec.source == "file-check"
        assert rec.confidence == "supported"
        assert "creates" in rec.body
        assert "done" in rec.body

    def test_created_files_excluded_from_path_style(self, tmp_path: Path) -> None:
        # All-created plan with missing parents: detect_path_style_mismatch
        # must NOT fire — created files are expected to be absent.
        plan = parse_plan(self._plan(tmp_path))
        checks = check_file_existence(plan, tmp_path)
        assert detect_path_style_mismatch(checks, tmp_path) is None

    def test_all_files_merges_modified_and_created(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: Merge\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: x\n"
            "    files: [a.py, shared.py]\n"
            "    creates: [b.py, shared.py]\n"
            "---\n",
            encoding="utf-8",
        )
        step = parse_plan(plan_path).steps[0]
        # Order preserved, files first, duplicate `shared.py` collapsed once.
        assert step.all_files == ["a.py", "shared.py", "b.py"]


class TestCrossStepMissingParent:
    """``check_file_existence`` projects each step's ``creates:`` directories
    forward in plan-list order, so a later step's ``files:`` entry under that
    tree classifies NEW instead of MISSING_PARENT. ``TestCheckFileExistence``
    and ``TestCreatesFootprint`` are the unchanged-behavior controls."""

    def _parse(self, tmp_path: Path, body: str) -> Plan:
        plan_path = tmp_path / "p.md"
        plan_path.write_text(body, encoding="utf-8")
        return parse_plan(plan_path)

    def test_earlier_creates_downgrades_later_files(
        self, tmp_path: Path
    ) -> None:
        plan = self._parse(
            tmp_path,
            "---\n"
            "title: Cross\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: scaffold package\n"
            "    creates:\n"
            "      - pkg/__init__.py\n"
            "  - id: 2\n"
            "    title: add foo module\n"
            "    files:\n"
            "      - pkg/foo.py\n"
            "    depends_on: [1]\n"
            "---\n",
        )
        by_id = {r.step_id: r for r in check_file_existence(plan, tmp_path)}
        # `pkg/` is absent on disk, but step 1 creates it → NEW, not suspect.
        assert by_id[2].files[0].status == FileExistence.NEW

    def test_ancestor_directory_credited(self, tmp_path: Path) -> None:
        plan = self._parse(
            tmp_path,
            "---\n"
            "title: Ancestor\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: deep create\n"
            "    creates:\n"
            "      - a/b/c.py\n"
            "  - id: 2\n"
            "    title: sibling under a\n"
            "    files:\n"
            "      - a/d.py\n"
            "    depends_on: [1]\n"
            "---\n",
        )
        by_id = {r.step_id: r for r in check_file_existence(plan, tmp_path)}
        # `a/` is an ancestor of the created `a/b/c.py` → credited.
        assert by_id[2].files[0].status == FileExistence.NEW

    def test_own_creates_does_not_downgrade_own_files(
        self, tmp_path: Path
    ) -> None:
        plan = self._parse(
            tmp_path,
            "---\n"
            "title: Own\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: same step\n"
            "    files:\n"
            "      - pkg/y.py\n"
            "    creates:\n"
            "      - pkg/x.py\n"
            "---\n",
        )
        files = check_file_existence(plan, tmp_path)[0].files
        # Only earlier steps credit; the step's own `creates:` must not
        # downgrade its own `files:` entry.
        y = next(fc for fc in files if fc.path == "pkg/y.py")
        assert y.status == FileExistence.MISSING_PARENT

    def test_later_creates_does_not_credit_earlier_step(
        self, tmp_path: Path
    ) -> None:
        plan = self._parse(
            tmp_path,
            "---\n"
            "title: Order\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: edit foo\n"
            "    files:\n"
            "      - pkg/foo.py\n"
            "  - id: 2\n"
            "    title: scaffold package\n"
            "    creates:\n"
            "      - pkg/__init__.py\n"
            "---\n",
        )
        by_id = {r.step_id: r for r in check_file_existence(plan, tmp_path)}
        # List order, not reverse: step 2's create can't credit step 1.
        assert by_id[1].files[0].status == FileExistence.MISSING_PARENT

    def test_no_creates_unchanged(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        by_id = {r.step_id: r for r in check_file_existence(plan, tmp_path)}
        # No step creates `missing_dir/` → step 3 stays MISSING_PARENT.
        assert by_id[3].files[0].status == FileExistence.MISSING_PARENT

    def test_cross_step_excluded_from_path_style(self, tmp_path: Path) -> None:
        plan = self._parse(
            tmp_path,
            "---\n"
            "title: NewTree\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: scaffold tree\n"
            "    creates:\n"
            "      - newtree/__init__.py\n"
            "  - id: 2\n"
            "    title: fill the tree\n"
            "    files:\n"
            "      - newtree/a.py\n"
            "      - newtree/b.py\n"
            "    depends_on: [1]\n"
            "---\n",
        )
        checks = check_file_existence(plan, tmp_path)
        # Every `files:` parent is covered by step 1's create → no MISSING_PARENT
        # remains, so the systemic-mismatch hint must not fire.
        assert detect_path_style_mismatch(checks, tmp_path) is None

    def test_genuine_path_style_still_fires(self, tmp_path: Path) -> None:
        plan = self._parse(
            tmp_path,
            "---\n"
            "title: Wrong Root\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: touch foo\n"
            "    files:\n"
            "      - nonexistent_dir/a.py\n"
            "      - nonexistent_dir/b.py\n"
            "  - id: 2\n"
            "    title: touch bar\n"
            "    files:\n"
            "      - nonexistent_dir/c.py\n"
            "      - nonexistent_dir/d.py\n"
            "    depends_on: [1]\n"
            "---\n",
        )
        checks = check_file_existence(plan, tmp_path)
        # No `creates:` covers the missing tree → counts unchanged, hint fires.
        hint = detect_path_style_mismatch(checks, tmp_path)
        assert hint is not None
        assert hint.missing_count == 4
        assert hint.total == 4

    def test_allow_missing_parent_still_promotes(self, tmp_path: Path) -> None:
        plan = self._parse(
            tmp_path,
            "---\n"
            "title: Uncovered\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: edit foo\n"
            "    files:\n"
            "      - dir/x.py\n"
            "---\n",
        )
        checks = check_file_existence(plan, tmp_path)
        # Uncovered by any create → survives the cross-step pass as
        # MISSING_PARENT, then the escape hatch promotes it to NEW.
        assert checks[0].files[0].status == FileExistence.MISSING_PARENT
        promoted = _promote_missing_parents(checks)
        assert promoted[0].files[0].status == FileExistence.NEW


# --- heuristic_already_done -------------------------------------------------


class TestHeuristicAlreadyDone:
    def test_flags_existing_symbol(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        hits = heuristic_already_done(plan, tmp_path)

        # Exactly one hit, on step 4 ("Add bar utility" → `def bar` in utils.py).
        assert len(hits) == 1
        hit = hits[0]
        assert hit.step_id == 4
        assert hit.file == "utils.py"
        assert hit.symbol.lower() == "bar"
        assert "def bar" in hit.pattern

    def test_skips_done_steps(self, tmp_path: Path) -> None:
        """Step 1 is ``done`` and its file contains ``class Parser`` — the
        heuristic must still not flag it, because done steps are expected to
        have their symbols on disk."""
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        hits = heuristic_already_done(plan, tmp_path)
        assert all(h.step_id != 1 for h in hits)

    def test_skips_nonexistent_files(self, tmp_path: Path) -> None:
        """Step 3's file doesn't exist — the heuristic can't read it, so it
        must silently skip rather than error."""
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        hits = heuristic_already_done(plan, tmp_path)
        assert all(h.step_id != 3 for h in hits)

    def test_no_symbols_means_no_hits(self, tmp_path: Path) -> None:
        """A title made entirely of stopwords yields no symbols to search."""
        (tmp_path / "x.py").write_text("def anything(): pass\n", encoding="utf-8")
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: Only Stopwords\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Add the\n"  # every token is a stopword
            "    files:\n"
            "      - x.py\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)
        hits = heuristic_already_done(plan, tmp_path)
        assert hits == []

    def test_prose_with_code_content_does_not_match_header_patterns(
        self, tmp_path: Path
    ) -> None:
        """Prose files use line-anchored header patterns; code-shaped strings
        that happen to live in a `.md` body don't trigger a heuristic hit.
        """
        (tmp_path / "notes.md").write_text(
            "def bar(): here's some code in a markdown file\n", encoding="utf-8"
        )
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Add bar utility\n"
            "    files:\n"
            "      - notes.md\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)
        hits = heuristic_already_done(plan, tmp_path)
        assert hits == []


_HEURISTIC_PROSE_PLAN = """---
title: P
status: in-progress
priority: low
steps:
  - id: 1
    title: Wire up Foo widget
    files:
      - notes.md
    status: current
---
"""


def _write_prose_plan(tmp_path: Path) -> Path:
    plan_path = tmp_path / "prose.md"
    plan_path.write_text(_HEURISTIC_PROSE_PLAN, encoding="utf-8")
    return plan_path


class TestHeuristicProseExtension:
    def test_flags_md_with_two_matching_headers(self, tmp_path: Path) -> None:
        """Two `# Foo` headers exceed the prose threshold and emit a hit."""
        (tmp_path / "notes.md").write_text(
            "# Foo\n\nIntro paragraph.\n\n## Foo\n\nMore detail here.\n",
            encoding="utf-8",
        )
        plan = parse_plan(_write_prose_plan(tmp_path))
        hits = heuristic_already_done(plan, tmp_path)

        assert len(hits) == 1
        assert hits[0].file == "notes.md"
        assert hits[0].symbol.lower() == "foo"
        assert hits[0].pattern in ("# Foo", "## Foo")

    def test_does_not_flag_md_with_only_one_header(self, tmp_path: Path) -> None:
        (tmp_path / "notes.md").write_text(
            "# Foo\n\nOnly one matching header.\n", encoding="utf-8"
        )
        plan = parse_plan(_write_prose_plan(tmp_path))
        hits = heuristic_already_done(plan, tmp_path)
        assert hits == []

    def test_does_not_flag_inline_mentions(self, tmp_path: Path) -> None:
        """Even five mentions of the token in body text shouldn't flag —
        only line-anchored headers count."""
        (tmp_path / "notes.md").write_text(
            "We discuss Foo, Foo, Foo, Foo, Foo here, but no headers.\n",
            encoding="utf-8",
        )
        plan = parse_plan(_write_prose_plan(tmp_path))
        hits = heuristic_already_done(plan, tmp_path)
        assert hits == []

    def test_does_not_flag_hash_inside_line(self, tmp_path: Path) -> None:
        """`# Foo` must start the line; mid-line occurrences don't count."""
        (tmp_path / "notes.md").write_text(
            "Some prefix # Foo and again some prefix # Foo end\n",
            encoding="utf-8",
        )
        plan = parse_plan(_write_prose_plan(tmp_path))
        hits = heuristic_already_done(plan, tmp_path)
        assert hits == []

    def test_custom_min_hits_threshold(self, tmp_path: Path) -> None:
        """Lowering ``prose_min_hits`` to 1 flags on a single header."""
        (tmp_path / "notes.md").write_text(
            "# Foo\n\nOne header is enough now.\n", encoding="utf-8"
        )
        plan = parse_plan(_write_prose_plan(tmp_path))
        hits = heuristic_already_done(plan, tmp_path, prose_min_hits=1)
        assert len(hits) == 1
        assert hits[0].symbol.lower() == "foo"


_HEURISTIC_CONFIG_PLAN = """---
title: P
status: in-progress
priority: low
steps:
  - id: 1
    title: Add foo settings
    files:
      - {filename}
    status: current
---
"""


def _write_config_plan(tmp_path: Path, filename: str) -> Path:
    plan_path = tmp_path / "config.md"
    plan_path.write_text(
        _HEURISTIC_CONFIG_PLAN.format(filename=filename), encoding="utf-8"
    )
    return plan_path


class TestHeuristicConfigExtension:
    def test_flags_toml_section(self, tmp_path: Path) -> None:
        (tmp_path / "config.toml").write_text(
            "[other]\nx = 1\n\n[foo]\ny = 2\n", encoding="utf-8"
        )
        plan = parse_plan(_write_config_plan(tmp_path, "config.toml"))
        hits = heuristic_already_done(plan, tmp_path)
        assert len(hits) == 1
        assert hits[0].file == "config.toml"
        assert hits[0].pattern == "[foo]"

    def test_flags_toml_key(self, tmp_path: Path) -> None:
        (tmp_path / "config.toml").write_text(
            "title = 'something'\nfoo = true\n", encoding="utf-8"
        )
        plan = parse_plan(_write_config_plan(tmp_path, "config.toml"))
        hits = heuristic_already_done(plan, tmp_path)
        assert len(hits) == 1
        assert hits[0].pattern == "foo ="

    def test_flags_json_top_level_key(self, tmp_path: Path) -> None:
        (tmp_path / "config.json").write_text(
            '{\n  "foo": "value",\n  "other": 1\n}\n', encoding="utf-8"
        )
        plan = parse_plan(_write_config_plan(tmp_path, "config.json"))
        hits = heuristic_already_done(plan, tmp_path)
        assert len(hits) == 1
        assert hits[0].file == "config.json"
        assert hits[0].pattern == '"foo"'

    def test_unrelated_toml_does_not_flag(self, tmp_path: Path) -> None:
        (tmp_path / "config.toml").write_text(
            "[unrelated]\nx = 1\n", encoding="utf-8"
        )
        plan = parse_plan(_write_config_plan(tmp_path, "config.toml"))
        hits = heuristic_already_done(plan, tmp_path)
        assert hits == []


class TestHeuristicSkipsUnknownExtensions:
    def test_yaml_skipped(self, tmp_path: Path) -> None:
        """`.yaml` is not in any extension category — heuristic must skip
        even when the content would otherwise look like a header or key."""
        (tmp_path / "config.yaml").write_text(
            "foo:\n  - 1\n  - 2\n", encoding="utf-8"
        )
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Add foo config\n"
            "    files:\n"
            "      - config.yaml\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)
        hits = heuristic_already_done(plan, tmp_path)
        assert hits == []


# --- validate_deps ---------------------------------------------------------


class TestValidateDeps:
    def test_ok_on_normal_plan(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        assert validate_deps(plan) == []

    def test_committed_dep_on_parked_step_rejected_at_parse(
        self, tmp_path: Path
    ) -> None:
        # The old "depends on a blocked step" soft warning is now a hard
        # parse-time error: a committed step that depends on a parked
        # (deferred/wont_do) step can never become runnable, so the schema
        # rejects it before validate_deps ever sees the plan.
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: Deadlock Plan\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: One\n"
            "    scope: deferred\n"
            "  - id: 2\n"
            "    title: Two\n"
            "    depends_on: [1]\n"
            "---\n",
            encoding="utf-8",
        )
        with pytest.raises(ParserValidationError, match="depends_on parked"):
            parse_plan(plan_path)


# --- render_review_prompt --------------------------------------------------


class TestRenderReviewPrompt:
    def test_source_excerpt_contract_survives_cleanup(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: Source Excerpt Contract\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Prepare first owner\n"
            "    files:\n"
            "      - pkg/shared.py\n"
            "      - pkg/unreadable.py\n"
            "  - id: 2\n"
            "    title: Implement second_symbol\n"
            "    creates:\n"
            "      - pkg/shared.py\n"
            "      - pkg/missing.py\n"
            "---\n",
            encoding="utf-8",
        )
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        shared = pkg / "shared.py"
        unreadable = pkg / "unreadable.py"
        shared.write_text(
            "\n".join(f"# filler {i}" for i in range(80))
            + "\n\n\ndef second_symbol():\n    return 2\n",
            encoding="utf-8",
        )
        unreadable.write_text("def hidden():\n    pass\n", encoding="utf-8")
        original_read_text = Path.read_text

        def fake_read_text(path: Path, *args, **kwargs) -> str:
            if path == unreadable:
                raise OSError("permission denied")
            return original_read_text(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", fake_read_text)

        prompt = render_review_prompt(
            parse_plan(plan_path), tmp_path, max_file_bytes=160
        )

        assert "`pkg/shared.py` (new)" in prompt
        assert prompt.count("### `pkg/shared.py`") == 1
        assert "def second_symbol()" in prompt
        assert "# filler 0" not in prompt
        assert "### `pkg/missing.py` _(not on disk)_" in prompt
        assert "### `pkg/unreadable.py` _(unreadable: permission denied)_" in prompt

    def test_includes_plan_title_and_steps(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        prompt = render_review_prompt(plan, tmp_path)

        assert "Review Test Plan" in prompt
        assert "Build the parser" in prompt
        assert "Wire up the renderer" in prompt
        assert "Add foo endpoint" in prompt
        assert "Add bar utility" in prompt

    def test_demands_machine_parsed_findings_block(
        self, tmp_path: Path
    ) -> None:
        """The prompt carries the ``## Findings`` block contract.

        ``_claude_recommendations`` → ``parse_finding_bullets`` only
        reads bullets inside a ``## Findings`` heading; without the
        contract in the prompt, claude's semantic findings render as
        report prose but never become walkable recommendations (found
        live by the backend bench: a review that named every seeded
        defect scored zero because nothing was extracted).
        """
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        prompt = render_review_prompt(plan, tmp_path)

        assert "## Findings" in prompt
        assert "machine-parsed" in prompt
        assert "_(none)_" in prompt

    def test_renders_canonical_body_when_pointer_unset(
        self, tmp_path: Path
    ) -> None:
        """A canonical-only step's body reaches the prompt when ``plan_path`` is
        given — so the reviewer sees the same bundle the deterministic battery
        emits findings against (step 2's stated parity)."""
        plan_path = tmp_path / "2-p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: build it\n"
            "    files: [foo.py]\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
        bundle = tmp_path / "plan-details" / "p"
        bundle.mkdir(parents=True)
        (bundle / "01-build.md").write_text(
            "# Step 1\n\n## Summary\n\nCANONICAL-BODY-MARKER\n", encoding="utf-8"
        )
        plan = parse_plan(plan_path)

        # Without plan_path there is no canonical fallback: previous behavior.
        assert "CANONICAL-BODY-MARKER" not in render_review_prompt(plan, tmp_path)

        prompt = render_review_prompt(plan, tmp_path, plan_path=plan_path)
        assert "CANONICAL-BODY-MARKER" in prompt
        assert "plan-details/p/01-build.md" in prompt
        assert "_no step detail files declared_" not in prompt

    def test_review_prompt_refuses_an_unsupported_detail_marker(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.detail_artifacts import (
            DetailFormatError,
            render_detail_format_version_marker,
        )

        plan_path = tmp_path / "2-p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: build it\n"
            "    files: [foo.py]\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
        bundle = tmp_path / "plan-details" / "p"
        bundle.mkdir(parents=True)
        (bundle / "01-build.md").write_text(
            f"# Step 1\n{render_detail_format_version_marker(999)}\n\n"
            "## Summary\n\nCANONICAL-BODY-MARKER\n",
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)

        with pytest.raises(DetailFormatError):
            render_review_prompt(plan, tmp_path, plan_path=plan_path)

    def test_empty_pointer_is_treated_as_unset_like_the_resolver(
        self, tmp_path: Path
    ) -> None:
        """``detail: ''`` parses (no non-empty validator on ``Step.detail``),
        and ``resolve_detail_artifact`` classifies it with ``bool()``. The
        prompt's own guard must agree, or the same plan takes different
        branches in the two halves of one function."""
        plan_path = tmp_path / "2-p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: build it\n"
            "    files: [foo.py]\n"
            "    detail: ''\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
        bundle = tmp_path / "plan-details" / "p"
        bundle.mkdir(parents=True)
        (bundle / "01-build.md").write_text(
            "# Step 1\n\nEMPTY-POINTER-MARKER\n", encoding="utf-8"
        )
        plan = parse_plan(plan_path)
        assert plan.step_by_id(1).detail == ""

        prompt = render_review_prompt(plan, tmp_path, plan_path=plan_path)
        # Resolved canonically, exactly as a None pointer would be.
        assert "EMPTY-POINTER-MARKER" in prompt
        assert "plan-details/p/01-build.md" in prompt

        # And without a plan_path it is skipped, exactly as a None pointer is.
        # This is the arm the guard's truthiness actually decides: with a
        # plan_path supplied both spellings agree, so only this one pins it.
        bare = render_review_prompt(plan, tmp_path)
        assert "_no step detail files declared_" in bare
        assert "declared but not on disk" not in bare

    def test_canonical_fallback_skips_a_step_with_no_file_on_disk(
        self, tmp_path: Path
    ) -> None:
        """An unset pointer with no canonical file on disk stays skipped —
        the fallback adds visibility, it never invents a block."""
        plan_path = tmp_path / "2-p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: build it\n"
            "    files: [foo.py]\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
        plan = parse_plan(plan_path)

        prompt = render_review_prompt(plan, tmp_path, plan_path=plan_path)
        assert "_no step detail files declared_" in prompt

    def test_includes_file_contents(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        prompt = render_review_prompt(plan, tmp_path)

        assert "class Parser" in prompt
        assert "def render(plan)" in prompt
        assert "def bar()" in prompt
        # Missing file is noted, not crashed on.
        assert "missing_dir/foo_endpoint.py" in prompt
        assert "not on disk" in prompt

    def test_prompt_requires_read_grep_grounding(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        prompt = render_review_prompt(plan, tmp_path)

        assert "truncated preview for orientation" in prompt
        assert "Read and Grep the repository at HEAD" in prompt
        assert "Read/Grep only; do not edit any file" in prompt
        assert "do not consult LLM-specific guidance files" in prompt

    def test_step_filter_narrows_to_one_step(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        prompt = render_review_prompt(plan, tmp_path, step_filter=4)

        assert "Add bar utility" in prompt
        # Other steps and their files are excluded.
        assert "Build the parser" not in prompt
        assert "class Parser" not in prompt

    def test_no_detail_files_renders_placeholder(self, tmp_path: Path) -> None:
        """Regression guard: plans with no `step.detail` produce the
        placeholder string and no orphan detail blocks.
        """
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        prompt = render_review_prompt(plan, tmp_path)

        assert "Step details (acceptance criteria)" in prompt
        assert "no step detail files declared" in prompt

    def test_detail_file_body_appears_in_prompt(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture_with_detail(tmp_path)
        plan = parse_plan(plan_path)
        prompt = render_review_prompt(plan, tmp_path)

        assert "Acceptance criteria here" in prompt
        assert "from `details/step-2-detail.md`" in prompt
        # Header for the step bearing the detail.
        assert "Step 2: Wire up the renderer" in prompt

    def test_missing_detail_file_marked_inline(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture_with_detail(
            tmp_path, missing_detail=True
        )
        plan = parse_plan(plan_path)
        prompt = render_review_prompt(plan, tmp_path)

        assert "details/step-2-detail.md" in prompt
        assert "declared but not on disk" in prompt

    def test_oversized_detail_truncated(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture_with_detail(
            tmp_path, detail_body="x" * 9000
        )
        plan = parse_plan(plan_path)
        prompt = render_review_prompt(plan, tmp_path, max_file_bytes=100)

        assert "_(truncated)_" in prompt
        # Truncation actually happened — full body is not present.
        assert "x" * 9000 not in prompt

    def test_step_filter_excludes_other_step_details(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_review_fixture_with_detail(tmp_path)
        plan = parse_plan(plan_path)
        prompt = render_review_prompt(plan, tmp_path, step_filter=4)

        # Step 4 in the fixture has no detail; step 2's detail must not leak.
        assert "Acceptance criteria here" not in prompt
        assert "no step detail files declared" in prompt

    def test_creates_files_rendered_as_declared(self, tmp_path: Path) -> None:
        """``creates:`` paths are declared files too — render them (marked
        ``(new)``) in the steps block and surface an already-on-disk created
        file in the contents section, so the audit can't false-flag a
        creates-only step as "declares no files" or its modules as "omitted"
        (BUG_BACKLOG RISK)."""
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: Creates Grounding\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Build the new module\n"
            "    creates:\n"
            "      - pkg/new_module.py\n"
            "  - id: 2\n"
            "    title: Extend and add\n"
            "    files:\n"
            "      - pkg/existing.py\n"
            "    creates:\n"
            "      - pkg/added.py\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "pkg").mkdir()
        # The creates-only step's file already exists — reconcile should see
        # it (the "already implemented" signal), not omit it.
        (tmp_path / "pkg" / "new_module.py").write_text("X = 1\n", encoding="utf-8")
        (tmp_path / "pkg" / "existing.py").write_text("Y = 2\n", encoding="utf-8")

        plan = parse_plan(plan_path)
        prompt = render_review_prompt(plan, tmp_path)

        # Steps block: creates paths listed and marked (new); the creates-only
        # step is not rendered fileless.
        assert "`pkg/new_module.py` (new)" in prompt
        assert "`pkg/added.py` (new)" in prompt
        assert "`pkg/existing.py`" in prompt
        # Contents block surfaces the already-on-disk created file.
        assert "X = 1" in prompt

    def test_uses_symbol_excerpt_for_declared_file(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: Symbol Excerpt\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Add target_symbol helper\n"
            "    files:\n"
            "      - pkg/helpers.py\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "pkg").mkdir()
        (tmp_path / "pkg" / "helpers.py").write_text(
            "\n".join(f"# header {i}" for i in range(200))
            + "\n\n\ndef target_symbol():\n    return 1\n",
            encoding="utf-8",
        )

        plan = parse_plan(plan_path)
        prompt = render_review_prompt(plan, tmp_path, max_file_bytes=200)

        assert "## Current file contents" in prompt
        assert "def target_symbol()" in prompt
        assert "# header 0" not in prompt

    def test_keeps_missing_and_unreadable_file_branches(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: File Errors\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Add helpers\n"
            "    files:\n"
            "      - missing.py\n"
            "      - unreadable.py\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "unreadable.py").write_text(
            "def helpers():\n    pass\n", encoding="utf-8"
        )
        original_read_text = Path.read_text

        def fail_unreadable(
            path: Path, *args: object, **kwargs: object
        ) -> str:
            if path.name == "unreadable.py":
                raise OSError("denied")
            return original_read_text(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", fail_unreadable)

        plan = parse_plan(plan_path)
        prompt = render_review_prompt(plan, tmp_path)

        assert "### `missing.py` _(not on disk)_" in prompt
        assert "### `unreadable.py` _(unreadable: denied)_" in prompt


# --- assemble_report -------------------------------------------------------


class TestAssembleReport:
    def test_ok_and_warn_lines(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        report = assemble_report(
            plan,
            "review-test",
            repo_root=tmp_path,
            file_checks=check_file_existence(plan, tmp_path),
            heuristic_hits=heuristic_already_done(plan, tmp_path),
            dep_issues=validate_deps(plan),
            claude_review=None,
        )
        # Metadata header
        assert "Plan Review: Review Test Plan" in report
        assert "status=in-progress" in report
        # Per-step verdicts: steps 1/2 OK, steps 3/4 WARN.
        assert "- Step 1 (done)  OK" in report
        assert "- Step 2 (current)  OK" in report
        assert "- Step 3 (pending)  WARN" in report
        assert "missing_dir/foo_endpoint.py" in report
        assert "- Step 4 (pending)  WARN" in report
        assert "symbol `bar`" in report
        # Claude section present with a skipped note (claude_review=None).
        assert "Claude's semantic review" in report
        assert "not available" in report
        # Suggested actions mentions reconcile for step 4.
        assert "Suggested actions" in report
        assert "plan-tool detail review-test --reconcile --step 4" in report

    def test_claude_section_inlined_when_provided(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        report = assemble_report(
            plan,
            "review-test",
            repo_root=tmp_path,
            file_checks=[],
            heuristic_hits=[],
            dep_issues=[],
            claude_review="### Findings\n\nNothing surprising.",
        )
        assert "### Findings" in report
        assert "Nothing surprising." in report

    def test_step_filter_shows_only_that_step(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        report = assemble_report(
            plan,
            "review-test",
            repo_root=tmp_path,
            file_checks=check_file_existence(plan, tmp_path),
            heuristic_hits=heuristic_already_done(plan, tmp_path),
            dep_issues=[],
            claude_review=None,
            step_filter=4,
        )
        assert "- Step 4 (pending)  WARN" in report
        assert "- Step 1 (done)" not in report
        assert "- Step 2 (current)" not in report
        assert "- Step 3 (pending)" not in report

    def test_missing_parent_diagnostic_uses_relative_paths(
        self, tmp_path: Path
    ) -> None:
        """The repo-relative path appears in BOTH the per-step WARN line and
        the suggestions block so a user can act from either. The absolute
        repo root is named once in the header, never repeated per finding.
        """
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        report = assemble_report(
            plan,
            "review-test",
            repo_root=tmp_path,
            file_checks=check_file_existence(plan, tmp_path),
            heuristic_hits=[],
            dep_issues=[],
            claude_review=None,
        )
        abs_path = tmp_path / "missing_dir/foo_endpoint.py"
        warn_section = report.split("### Suggested actions")[0]
        suggestions_section = report.split("### Suggested actions")[1]

        # Repo root named once, in the header — not on every finding line.
        assert f"Repo root: `{tmp_path}`" in report
        assert str(abs_path) not in warn_section
        assert str(abs_path) not in suggestions_section

        # Both sections carry the repo-relative path + missing parent dir.
        assert "missing_dir/foo_endpoint.py" in warn_section
        assert "missing_dir/" in warn_section
        assert "missing_dir/foo_endpoint.py" in suggestions_section
        assert "missing_dir/" in suggestions_section

    def test_existing_happy_path_strings_unchanged(self, tmp_path: Path) -> None:
        """Regression guard: OK / NEW-on-pending lines keep their old shape."""
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        report = assemble_report(
            plan,
            "review-test",
            repo_root=tmp_path,
            file_checks=check_file_existence(plan, tmp_path),
            heuristic_hits=[],
            dep_issues=[],
            claude_review=None,
        )
        # Step 1 has parser.py on disk → "1 file(s) declared, all exist".
        assert "1 file(s) declared, all exist" in report
        # No false-positive on the abs-path text for OK steps.
        assert "Step 1 (done)  OK" in report


def _banner_line(report: str) -> str | None:
    """Return the report's ``Findings:`` line, or ``None`` if absent."""
    for line in report.splitlines():
        if line.startswith("Findings:"):
            return line
    return None


def _rec(severity: str) -> "Recommendation":
    """Build a minimal ``Recommendation`` carrying just a severity."""
    return Recommendation(
        id=f"id-{severity}",
        source="test",
        severity=severity,
        step_id=None,
        title="t",
        body="b",
    )


def _carried_rec(
    rec_id: str,
    *,
    severity: str = "medium",
    anchor: Optional[str] = "anchor",
    title: str = "title",
    body: str = "body",
) -> Recommendation:
    return Recommendation(
        id=rec_id,
        source="test",
        severity=severity,
        step_id=None,
        title=title,
        body=body,
        anchor=anchor,
    )


class TestAssembleCarriedFindings:
    def test_carried_finding_is_frozen(self) -> None:
        carried = CarriedFinding(
            anchor="a",
            title="t",
            severity="medium",
            body_excerpt="b",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            carried.title = "changed"  # type: ignore[misc]

    def test_assemble_carried_findings_basic(self) -> None:
        rec = _carried_rec(
            "r1",
            severity="high",
            anchor="cache-invalidation",
            title="cache never invalidates",
            body="cache gap body",
        )

        assert assemble_carried_findings([rec]) == [
            CarriedFinding(
                anchor="cache-invalidation",
                title="cache never invalidates",
                severity="high",
                body_excerpt="cache gap body",
                confidence="limited",
            )
        ]

    def test_carried_body_excerpt_capped(self) -> None:
        long_body = "x" * (_CARRIED_BODY_EXCERPT_CHARS + 20)
        short_body = "short body"
        carried = assemble_carried_findings(
            [
                _carried_rec("long", title="long", body=long_body),
                _carried_rec("short", title="short", body=short_body),
            ]
        )
        by_title = {c.title: c for c in carried}

        assert len(by_title["long"].body_excerpt) == _CARRIED_BODY_EXCERPT_CHARS
        assert by_title["long"].body_excerpt.endswith("…")
        assert by_title["short"].body_excerpt == short_body
        assert not by_title["short"].body_excerpt.endswith("…")

    def test_carried_findings_sorted_by_severity_then_anchor(self) -> None:
        recs = [
            _carried_rec("info", severity="info", anchor="b", title="info"),
            _carried_rec("high", severity="high", anchor="b", title="high"),
            _carried_rec("nit", severity="nit", anchor="a", title="nit"),
            _carried_rec(
                "medium-b",
                severity="medium",
                anchor="b",
                title="medium b",
            ),
            _carried_rec(
                "critical",
                severity="critical",
                anchor="z",
                title="critical",
            ),
            _carried_rec(
                "medium-a2",
                severity="medium",
                anchor="a",
                title="medium a2",
            ),
            _carried_rec(
                "medium-a1",
                severity="medium",
                anchor="a",
                title="medium a1",
            ),
        ]

        assert [
            (c.severity, c.anchor, c.title)
            for c in assemble_carried_findings(recs)
        ] == [
            ("critical", "z", "critical"),
            ("high", "b", "high"),
            ("medium", "a", "medium a1"),
            ("medium", "a", "medium a2"),
            ("medium", "b", "medium b"),
            ("nit", "a", "nit"),
            ("info", "b", "info"),
        ]

    def test_assemble_carried_findings_is_deterministic(self) -> None:
        recs = [
            _carried_rec("b", severity="medium", anchor="b", title="b"),
            _carried_rec("a", severity="high", anchor="a", title="a"),
        ]

        first = assemble_carried_findings(recs)
        second = assemble_carried_findings(recs)

        assert second == first

    def test_carried_resolution_defaults_open(self) -> None:
        carried = assemble_carried_findings([_carried_rec("r1")])

        assert carried[0].resolution == CARRIED_RESOLUTION_OPEN
        assert carried[0].resolution_reason == ""

    def test_carried_resolution_from_map(self) -> None:
        recs = [
            _carried_rec("applied", title="applied"),
            _carried_rec("skipped", title="skipped"),
            _carried_rec("absent", title="absent"),
        ]

        carried = assemble_carried_findings(
            recs,
            resolution_by_id={
                "applied": (CARRIED_RESOLUTION_APPLIED, "landed"),
                "skipped": (CARRIED_RESOLUTION_SKIPPED, "declined"),
            },
        )
        by_title = {c.title: c for c in carried}

        assert by_title["applied"].resolution == CARRIED_RESOLUTION_APPLIED
        assert by_title["applied"].resolution_reason == "landed"
        assert by_title["skipped"].resolution == CARRIED_RESOLUTION_SKIPPED
        assert by_title["skipped"].resolution_reason == "declined"
        assert by_title["absent"].resolution == CARRIED_RESOLUTION_OPEN
        assert by_title["absent"].resolution_reason == ""

    def test_carried_anchor_none_for_sluggless(self) -> None:
        carried = assemble_carried_findings(
            [_carried_rec("r1", anchor=None)]
        )

        assert carried[0].anchor is None

    def test_unknown_severity_sorts_last(self) -> None:
        carried = assemble_carried_findings(
            [
                _carried_rec("unknown", severity="urgent", title="unknown"),
                _carried_rec("info", severity="info", title="info"),
            ]
        )

        assert [c.severity for c in carried] == ["info", "urgent"]


class TestFormatCarriedFindingsBlock:
    def test_carried_block_renders_severity_and_title(self) -> None:
        block = _format_carried_findings_block(
            [
                CarriedFinding(
                    anchor="cache-invalidation",
                    title="cache never invalidates",
                    severity="high",
                    body_excerpt="body",
                )
            ]
        )

        assert "- `[cache-invalidation]` (HIGH) — cache never invalidates" in block

    def test_carried_block_renders_excerpt_line(self) -> None:
        block = _format_carried_findings_block(
            [
                CarriedFinding(
                    anchor="with-excerpt",
                    title="has excerpt",
                    severity="medium",
                    body_excerpt="short carried body",
                ),
                CarriedFinding(
                    anchor="without-excerpt",
                    title="no excerpt",
                    severity="medium",
                    body_excerpt="",
                ),
            ]
        )

        assert "  excerpt: short carried body" in block
        assert "excerpt: \n" not in block

    def test_carried_block_renders_resolution_only_when_not_open(self) -> None:
        block = _format_carried_findings_block(
            [
                CarriedFinding(
                    anchor="open-gap",
                    title="still active",
                    severity="medium",
                    body_excerpt="",
                    resolution=CARRIED_RESOLUTION_OPEN,
                ),
                CarriedFinding(
                    anchor="applied-gap",
                    title="already applied",
                    severity="medium",
                    body_excerpt="",
                    resolution=CARRIED_RESOLUTION_APPLIED,
                ),
                CarriedFinding(
                    anchor="skipped-gap",
                    title="intentionally skipped",
                    severity="medium",
                    body_excerpt="",
                    resolution=CARRIED_RESOLUTION_SKIPPED,
                    resolution_reason="not worth scope",
                ),
            ]
        )

        assert "- `[open-gap]` (MEDIUM) — still active" in block
        assert "(MEDIUM, open)" not in block
        assert "- `[applied-gap]` (MEDIUM, applied) — already applied" in block
        assert (
            "- `[skipped-gap]` (MEDIUM, skipped: not worth scope) — "
            "intentionally skipped"
        ) in block

    def test_carried_block_preserves_slug_reuse_instruction(self) -> None:
        block = _format_carried_findings_block(
            [
                CarriedFinding(
                    anchor="cache-invalidation",
                    title="cache never invalidates",
                    severity="medium",
                    body_excerpt="",
                )
            ]
        )

        normalized = " ".join(block.split())
        assert (
            "re-use its exact `[anchor-slug]` verbatim — your wording may "
            "differ; the slug is the identity. Mint a new slug only for a "
            "genuinely new concept."
        ) in normalized

    def test_carried_block_frames_convergence_guidance(self) -> None:
        """The carried block steers the pass toward convergence — not just
        slug dedupe: it names converging as the goal, points at the areas
        prior passes have NOT covered, and guards both against inventing
        marginal gaps and against suppressing a real late gap."""
        block = _format_carried_findings_block(
            [
                CarriedFinding(
                    anchor="cache-invalidation",
                    title="cache never invalidates",
                    severity="high",
                    body_excerpt="",
                )
            ]
        )

        normalized = " ".join(block.split())
        assert "converge" in normalized.lower()
        assert "NOT covered" in block
        assert "never suppress a real new gap" in normalized

    def test_carried_block_omits_sluggless_findings(self) -> None:
        block = _format_carried_findings_block(
            [
                CarriedFinding(
                    anchor=None,
                    title="sluggless",
                    severity="high",
                    body_excerpt="body",
                ),
                CarriedFinding(
                    anchor="anchored",
                    title="anchored title",
                    severity="medium",
                    body_excerpt="body",
                ),
            ]
        )

        assert "sluggless" not in block
        assert "- `[anchored]` (MEDIUM) — anchored title" in block

    def test_carried_block_empty_for_no_anchored(self) -> None:
        assert _format_carried_findings_block([]) == ""
        assert (
            _format_carried_findings_block(
                [
                    CarriedFinding(
                        anchor=None,
                        title="sluggless",
                        severity="high",
                        body_excerpt="body",
                    )
                ]
            )
            == ""
        )

    def test_carried_block_caps_findings(self) -> None:
        carried = [
            CarriedFinding(
                anchor=f"info-{i:02d}",
                title=f"info {i:02d}",
                severity="info",
                body_excerpt="",
            )
            for i in range(_CARRIED_BLOCK_MAX_FINDINGS + 3)
        ] + [
            CarriedFinding(
                anchor="critical-gap",
                title="critical gap",
                severity="critical",
                body_excerpt="",
            ),
            CarriedFinding(
                anchor="high-gap",
                title="high gap",
                severity="high",
                body_excerpt="",
            ),
        ]

        block = _format_carried_findings_block(carried)
        finding_lines = [
            line for line in block.splitlines() if line.startswith("- `[")
        ]

        assert len(finding_lines) == _CARRIED_BLOCK_MAX_FINDINGS
        assert finding_lines[0].startswith("- `[critical-gap]`")
        assert finding_lines[1].startswith("- `[high-gap]`")
        assert (
            f"… 5 more lower-priority finding(s) not shown "
            f"(cap {_CARRIED_BLOCK_MAX_FINDINGS})."
        ) in block

    def test_carried_block_cap_is_deterministic(self) -> None:
        carried = [
            CarriedFinding(
                anchor=f"gap-{i:02d}",
                title=f"gap {i:02d}",
                severity="medium",
                body_excerpt="body",
            )
            for i in reversed(range(_CARRIED_BLOCK_MAX_FINDINGS + 2))
        ]

        assert _format_carried_findings_block(
            carried
        ) == _format_carried_findings_block(carried)

    def test_carried_block_prefers_unresolved_within_severity(self) -> None:
        block = _format_carried_findings_block(
            [
                CarriedFinding(
                    anchor="a-resolved",
                    title="resolved",
                    severity="medium",
                    body_excerpt="",
                    resolution=CARRIED_RESOLUTION_APPLIED,
                ),
                CarriedFinding(
                    anchor="z-open",
                    title="unresolved",
                    severity="medium",
                    body_excerpt="",
                    resolution=CARRIED_RESOLUTION_OPEN,
                ),
            ],
            max_findings=1,
        )

        assert "- `[z-open]` (MEDIUM) — unresolved" in block
        assert "a-resolved" not in block


class TestAssembleReportSeverityBanner:
    def test_severity_banner_absent_without_recommendations(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        report = assemble_report(
            plan,
            "review-test",
            repo_root=tmp_path,
            file_checks=check_file_existence(plan, tmp_path),
            heuristic_hits=heuristic_already_done(plan, tmp_path),
            dep_issues=validate_deps(plan),
            claude_review=None,
        )
        assert _banner_line(report) is None

    def test_severity_banner_tallies_real_findings(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        recs = extract_recommendations(
            plan,
            "review-test",
            repo_root=tmp_path,
            file_checks=check_file_existence(plan, tmp_path),
            heuristic_hits=heuristic_already_done(plan, tmp_path),
            dep_issues=validate_deps(plan),
            path_style_hint=None,
        )
        report = assemble_report(
            plan,
            "review-test",
            repo_root=tmp_path,
            file_checks=check_file_existence(plan, tmp_path),
            heuristic_hits=heuristic_already_done(plan, tmp_path),
            dep_issues=validate_deps(plan),
            claude_review=None,
            recommendations=recs,
        )
        # Fixture: step-3 MISSING_PARENT (medium) + step-4 heuristic (info).
        line = _banner_line(report)
        assert line == "Findings: 1 medium · 1 info"
        # Zero-count levels are omitted.
        assert "critical" not in line
        assert "high" not in line

    def test_severity_banner_orders_high_before_info(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        recs = [
            _rec("info"),
            _rec("nit"),
            _rec("medium"),
            _rec("high"),
            _rec("critical"),
        ]
        report = assemble_report(
            plan,
            "review-test",
            repo_root=tmp_path,
            file_checks=[],
            heuristic_hits=[],
            dep_issues=[],
            claude_review=None,
            recommendations=recs,
        )
        line = _banner_line(report)
        assert line == (
            "Findings: 1 critical · 1 high · 1 medium · 1 nit · 1 info"
        )

    def test_severity_banner_none_when_empty(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        report = assemble_report(
            plan,
            "review-test",
            repo_root=tmp_path,
            file_checks=[],
            heuristic_hits=[],
            dep_issues=[],
            claude_review=None,
            recommendations=[],
        )
        assert _banner_line(report) == "Findings: none"

    def test_severity_banner_position_under_repo_root(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        report = assemble_report(
            plan,
            "review-test",
            repo_root=tmp_path,
            file_checks=[],
            heuristic_hits=[],
            dep_issues=[],
            claude_review=None,
            recommendations=[_rec("high")],
        )
        repo_root_pos = report.index("Repo root:")
        banner_pos = report.index("Findings:")
        review_pos = report.index("### Claude's semantic review")
        assert repo_root_pos < banner_pos < review_pos

    def test_severity_banner_respects_step_filter(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        result = review_plan_full(
            plan_path,
            repo_root=tmp_path,
            plan_name="review-test",
            step_id=4,
            invoker=None,
        )
        # Step 4's only finding is the heuristic info hit.
        assert _banner_line(result.report) == "Findings: 1 info"
        from collections import Counter

        by_sev = Counter(r.severity for r in result.recommendations)
        assert by_sev == Counter({"info": 1})

    def test_render_severity_banner_unit(self) -> None:
        recs = [_rec("critical"), _rec("info"), _rec("info")]
        assert (
            _render_severity_banner(recs) == "Findings: 1 critical · 2 info"
        )
        assert _render_severity_banner([]) == "Findings: none"


class TestAssembleReportWalkMode:
    """``walk_will_run=True`` de-duplicates the report against the walk."""

    def test_walk_mode_omits_recommendation_lines_but_default_renders_them(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        rec = Recommendation(
            id="report-rec", source="deps", severity="high", step_id=2,
            title="Resolve dependency", body="Step 2 waits for step 1.",
            confidence="supported",
        )
        common = dict(
            repo_root=tmp_path,
            file_checks=[],
            heuristic_hits=[],
            dep_issues=[],
            claude_review=None,
            recommendations=[rec],
        )

        walk_report = assemble_report(
            plan, "review-test", walk_will_run=True, **common
        )
        default_report = assemble_report(plan, "review-test", **common)

        assert "Findings: 1 high" in walk_report
        assert "Finding:" not in walk_report
        assert (
            "Finding: deps/high · step 2 [confidence: supported] — "
            "Resolve dependency"
        ) in default_report

    def test_walk_mode_omits_block_and_slims_warn(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        report = assemble_report(
            plan,
            "review-test",
            repo_root=tmp_path,
            file_checks=check_file_existence(plan, tmp_path),
            heuristic_hits=heuristic_already_done(plan, tmp_path),
            dep_issues=validate_deps(plan),
            claude_review=None,
            walk_will_run=True,
        )
        # Suggested actions block omitted — the walk presents them.
        assert "### Suggested actions" not in report
        # Step 3's WARN line is a finding count, not the issue detail.
        assert "- Step 3 (pending)  WARN — 1 finding" in report
        # The missing-parent path detail lives only in the walk now.
        assert "missing_dir/foo_endpoint.py" not in report
        # At-a-glance map + semantic review still render.
        assert "### Per-step status" in report
        assert "### Claude's semantic review" in report

    def test_default_keeps_block_and_warn_detail(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        report = assemble_report(
            plan,
            "review-test",
            repo_root=tmp_path,
            file_checks=check_file_existence(plan, tmp_path),
            heuristic_hits=heuristic_already_done(plan, tmp_path),
            dep_issues=validate_deps(plan),
            claude_review=None,
        )
        # Default (no walk) keeps the full block and full WARN detail.
        assert "### Suggested actions" in report
        assert "plan-tool detail review-test --reconcile --step 4" in report
        assert "missing_dir/foo_endpoint.py" in report

    def test_warn_count_singular_plural(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        one_hit = [
            HeuristicHit(step_id=4, file="utils.py", symbol="bar", pattern="def bar")
        ]
        two_hits = one_hit + [
            HeuristicHit(
                step_id=4, file="utils.py", symbol="baz", pattern="def baz"
            )
        ]
        singular = assemble_report(
            plan,
            "review-test",
            repo_root=tmp_path,
            file_checks=[],
            heuristic_hits=one_hit,
            dep_issues=[],
            claude_review=None,
            walk_will_run=True,
        )
        plural = assemble_report(
            plan,
            "review-test",
            repo_root=tmp_path,
            file_checks=[],
            heuristic_hits=two_hits,
            dep_issues=[],
            claude_review=None,
            walk_will_run=True,
        )
        assert "- Step 4 (pending)  WARN — 1 finding" in singular
        assert "- Step 4 (pending)  WARN — 2 findings" in plural

    def test_hint_legend_dropped_in_walk_mode(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        hits = heuristic_already_done(plan, tmp_path)
        assert hits, "fixture must trip the heuristic for this test"

        walk = assemble_report(
            plan,
            "review-test",
            repo_root=tmp_path,
            file_checks=check_file_existence(plan, tmp_path),
            heuristic_hits=hits,
            dep_issues=[],
            claude_review=None,
            walk_will_run=True,
        )
        # Both the inline `hint:` detail and the `> hint:` legend are gone.
        assert "hint: symbol" not in walk
        assert "low-confidence" not in walk

        default = assemble_report(
            plan,
            "review-test",
            repo_root=tmp_path,
            file_checks=check_file_existence(plan, tmp_path),
            heuristic_hits=hits,
            dep_issues=[],
            claude_review=None,
        )
        assert "hint: symbol" in default
        assert "low-confidence" in default


# --- _describe_file_check --------------------------------------------------


class TestDescribeFileCheck:
    def test_missing_parent_names_rel_path_and_parent(
        self, tmp_path: Path
    ) -> None:
        fc = FileCheck(
            path="missing_dir/foo.py", status=FileExistence.MISSING_PARENT
        )
        issue, suggestion = _describe_file_check(
            fc, step_status=StepStatus.PENDING
        )
        # Issue text names the repo-relative path and the missing parent
        # dir — the absolute repo root is printed once in the report
        # header, not repeated on every finding.
        assert "missing_dir/foo.py" in issue
        assert "missing_dir/" in issue
        assert str(tmp_path) not in issue
        # Suggestion mirrors the same data so the user can act from either
        # the WARN line or the suggestions block.
        assert suggestion is not None
        assert "missing_dir/foo.py" in suggestion
        assert str(tmp_path) not in suggestion

    def test_new_on_done_step_returns_issue_only(self, tmp_path: Path) -> None:
        fc = FileCheck(path="created.py", status=FileExistence.NEW)
        issue, suggestion = _describe_file_check(
            fc, step_status=StepStatus.DONE
        )
        assert "created.py" in issue
        assert str(tmp_path) not in issue
        assert "step marked done" in issue
        # NEW-on-DONE suggestion is None — caller has plan_name/step_id and
        # emits the reconcile guidance.
        assert suggestion is None

    def test_ok_returns_empty(self, tmp_path: Path) -> None:
        fc = FileCheck(path="x.py", status=FileExistence.OK)
        issue, suggestion = _describe_file_check(
            fc, step_status=StepStatus.PENDING
        )
        assert issue == ""
        assert suggestion is None

    def test_new_on_pending_step_returns_empty(self, tmp_path: Path) -> None:
        """The expected case for steps that create files — must not warn."""
        fc = FileCheck(path="will_be_created.py", status=FileExistence.NEW)
        issue, suggestion = _describe_file_check(
            fc, step_status=StepStatus.PENDING
        )
        assert issue == ""
        assert suggestion is None

    def test_new_on_current_step_returns_empty(self, tmp_path: Path) -> None:
        """Same logic as pending: in-flight steps may not have written files yet."""
        fc = FileCheck(path="in_progress.py", status=FileExistence.NEW)
        issue, suggestion = _describe_file_check(
            fc, step_status=StepStatus.CURRENT
        )
        assert issue == ""
        assert suggestion is None


# --- detect_path_style_mismatch --------------------------------------------


def _file_check(path: str, status: FileExistence) -> FileCheck:
    return FileCheck(path=path, status=status)


def _step_files(step_id: int, *checks: FileCheck) -> StepFileCheck:
    return StepFileCheck(step_id=step_id, files=list(checks))


class TestDetectPathStyleMismatch:
    def test_returns_none_when_no_files_declared(self, tmp_path: Path) -> None:
        # Two steps, neither declares any files.
        checks = [_step_files(1), _step_files(2)]
        assert detect_path_style_mismatch(checks, tmp_path) is None

    def test_returns_none_below_threshold(self, tmp_path: Path) -> None:
        # 2 of 4 missing → 50% < 80%.
        checks = [
            _step_files(
                1,
                _file_check("a.py", FileExistence.OK),
                _file_check("b.py", FileExistence.MISSING_PARENT),
            ),
            _step_files(
                2,
                _file_check("c.py", FileExistence.NEW),
                _file_check("d.py", FileExistence.MISSING_PARENT),
            ),
        ]
        assert detect_path_style_mismatch(checks, tmp_path) is None

    def test_returns_hint_at_or_above_threshold(self, tmp_path: Path) -> None:
        # 4 of 5 missing → 80% exactly.
        checks = [
            _step_files(
                1,
                _file_check("a.py", FileExistence.MISSING_PARENT),
                _file_check("b.py", FileExistence.MISSING_PARENT),
                _file_check("c.py", FileExistence.MISSING_PARENT),
            ),
            _step_files(
                2,
                _file_check("d.py", FileExistence.MISSING_PARENT),
                _file_check("e.py", FileExistence.OK),
            ),
        ]
        hint = detect_path_style_mismatch(checks, tmp_path)
        assert hint is not None
        assert hint.missing_count == 4
        assert hint.total == 5
        assert hint.ratio == pytest.approx(0.8)
        assert hint.repo_root == tmp_path

    def test_hint_examples_capped_at_three(self, tmp_path: Path) -> None:
        # 5 missing in declared order — examples should be the first 3.
        checks = [
            _step_files(
                1,
                _file_check("a.py", FileExistence.MISSING_PARENT),
                _file_check("b.py", FileExistence.MISSING_PARENT),
                _file_check("c.py", FileExistence.MISSING_PARENT),
                _file_check("d.py", FileExistence.MISSING_PARENT),
                _file_check("e.py", FileExistence.MISSING_PARENT),
            ),
        ]
        hint = detect_path_style_mismatch(checks, tmp_path)
        assert hint is not None
        assert hint.examples == ["a.py", "b.py", "c.py"]

    def test_custom_threshold(self, tmp_path: Path) -> None:
        # 1 of 2 missing → 50%; with threshold=0.5 the hint should fire.
        checks = [
            _step_files(
                1,
                _file_check("a.py", FileExistence.MISSING_PARENT),
                _file_check("b.py", FileExistence.OK),
            ),
        ]
        hint = detect_path_style_mismatch(checks, tmp_path, threshold=0.5)
        assert hint is not None
        assert hint.ratio == pytest.approx(0.5)


# --- assemble_report integration with PathStyleHint ------------------------


class TestAssembleReportPathStyle:
    def test_top_level_section_when_hint_supplied(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        hint = PathStyleHint(
            missing_count=8,
            total=10,
            ratio=0.8,
            examples=["a.py", "b.py", "c.py"],
            repo_root=tmp_path,
        )
        report = assemble_report(
            plan,
            "review-test",
            repo_root=tmp_path,
            file_checks=check_file_existence(plan, tmp_path),
            heuristic_hits=[],
            dep_issues=[],
            claude_review=None,
            path_style_hint=hint,
        )
        # New top-level section present, with examples and the suggestion.
        assert "### Plan-wide path issue" in report
        assert "8 of 10" in report
        assert "80% mismatch" in report
        assert "- `a.py`" in report
        assert "--repo-root" in report

    def test_no_top_level_section_when_hint_absent(self, tmp_path: Path) -> None:
        """All-OK plan: no top-level diagnostic appears."""
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        report = assemble_report(
            plan,
            "review-test",
            repo_root=tmp_path,
            file_checks=check_file_existence(plan, tmp_path),
            heuristic_hits=[],
            dep_issues=[],
            claude_review=None,
            path_style_hint=None,
        )
        assert "Plan-wide path issue" not in report

    def test_per_step_warnings_still_render_alongside_hint(
        self, tmp_path: Path
    ) -> None:
        """The hint is additive — per-step WARN lines must still appear."""
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        hint = PathStyleHint(
            missing_count=1,
            total=1,
            ratio=1.0,
            examples=["x.py"],
            repo_root=tmp_path,
        )
        report = assemble_report(
            plan,
            "review-test",
            repo_root=tmp_path,
            file_checks=check_file_existence(plan, tmp_path),
            heuristic_hits=heuristic_already_done(plan, tmp_path),
            dep_issues=validate_deps(plan),
            claude_review=None,
            path_style_hint=hint,
        )
        # Both blocks present.
        assert "### Plan-wide path issue" in report
        assert "- Step 3 (pending)  WARN" in report
        assert "missing_dir/foo_endpoint.py" in report

    def test_hint_renders_above_per_step_status(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        hint = PathStyleHint(
            missing_count=2,
            total=2,
            ratio=1.0,
            examples=["a", "b"],
            repo_root=tmp_path,
        )
        report = assemble_report(
            plan,
            "review-test",
            repo_root=tmp_path,
            file_checks=check_file_existence(plan, tmp_path),
            heuristic_hits=[],
            dep_issues=[],
            claude_review=None,
            path_style_hint=hint,
        )
        assert report.index("### Plan-wide path issue") < report.index(
            "### Per-step status"
        )


# --- review_plan (end-to-end) ----------------------------------------------


class TestReviewPlanAcceptance:
    def test_report_flags_both_issues_and_does_not_false_positive(
        self, tmp_path: Path
    ) -> None:
        """The acceptance criterion from 04-plan-review.md."""
        plan_path = _write_review_fixture(tmp_path)

        calls: list[str] = []

        def fake_invoker(prompt: str) -> tuple[int, str]:
            calls.append(prompt)
            return (0, "Semantic review: looks fine from my side.\n")

        report = review_plan(
            plan_path,
            repo_root=tmp_path,
            plan_name="review-test",
            invoker=fake_invoker,
            extract_lessons=False,
        )

        # File-existence issue on step 3 surfaces with relative path + missing parent.
        assert "- Step 3 (pending)  WARN" in report
        assert "missing_dir/foo_endpoint.py" in report
        assert "parent dir `missing_dir/` doesn't exist" in report
        # Already-done heuristic on step 4 surfaces.
        assert "- Step 4 (pending)  WARN" in report
        assert "symbol `bar`" in report
        # Steps 1 and 2 stay OK — no false positives on the control steps.
        assert "- Step 1 (done)  OK" in report
        assert "- Step 2 (current)  OK" in report
        # Claude's text is folded in.
        assert "Semantic review: looks fine from my side." in report
        # Exactly one claude invocation when lesson extraction is off.
        assert len(calls) == 1
        assert "Review Test Plan" in calls[0]

    def test_dry_run_returns_prompt(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        called: list[str] = []

        def should_not_call(prompt: str) -> tuple[int, str]:
            called.append(prompt)
            return (0, "")

        out = review_plan(
            plan_path,
            repo_root=tmp_path,
            plan_name="review-test",
            invoker=should_not_call,
            dry_run=True,
        )
        assert called == []
        # Dry run returns the raw prompt text (mirrors `run --dry-run`).
        assert "Plan review: Review Test Plan" in out
        assert "## Plan Review:" not in out  # not the report header

    def test_invoker_none_produces_report_with_note(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        report = review_plan(
            plan_path,
            repo_root=tmp_path,
            plan_name="review-test",
            invoker=None,
        )
        # Deterministic checks still run.
        assert "- Step 3 (pending)  WARN" in report
        assert "- Step 4 (pending)  WARN" in report
        # Claude section present with a skip note.
        assert "no invoker supplied" in report

    def test_claude_missing_note(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)

        def missing_claude(prompt: str) -> tuple[int, str]:
            return (127, "")

        report = review_plan(
            plan_path,
            repo_root=tmp_path,
            plan_name="review-test",
            invoker=missing_claude,
        )
        assert "executable not found" in report

    def test_unknown_step_id_raises(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        with pytest.raises(ReviewError):
            review_plan(
                plan_path,
                repo_root=tmp_path,
                plan_name="review-test",
                step_id=99,
                invoker=None,
            )

    def test_step_filter_runs_end_to_end(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)

        def fake_invoker(prompt: str) -> tuple[int, str]:
            return (0, "filtered review.")

        report = review_plan(
            plan_path,
            repo_root=tmp_path,
            plan_name="review-test",
            step_id=4,
            invoker=fake_invoker,
        )
        assert "- Step 4 (pending)  WARN" in report
        assert "- Step 1 (done)" not in report

    def test_plan_file_unchanged(self, tmp_path: Path) -> None:
        """review is read-only — it must never touch the plan file."""
        plan_path = _write_review_fixture(tmp_path)
        original = plan_path.read_text(encoding="utf-8")
        review_plan(
            plan_path,
            repo_root=tmp_path,
            plan_name="review-test",
            invoker=lambda _: (0, "fine."),
        )
        assert plan_path.read_text(encoding="utf-8") == original

    def test_plan_object_state_preserved(self, tmp_path: Path) -> None:
        """Double-check the parsed plan's step statuses end unchanged after review."""
        plan_path = _write_review_fixture(tmp_path)
        review_plan(
            plan_path,
            repo_root=tmp_path,
            plan_name="review-test",
            invoker=lambda _: (0, ""),
        )
        reloaded = parse_plan(plan_path)
        assert reloaded.step_by_id(1).status == StepStatus.DONE
        assert reloaded.step_by_id(2).status == StepStatus.CURRENT
        assert reloaded.step_by_id(3).status == StepStatus.PENDING
        assert reloaded.step_by_id(4).status == StepStatus.PENDING


class TestReviewPlanHeuristicSuppressor:
    def test_no_false_positive_on_clean_plan(self, tmp_path: Path) -> None:
        """Plan where every step is clean — no WARNs, no suggested actions."""
        (tmp_path / "a.py").write_text("# nothing\n", encoding="utf-8")
        plan_path = tmp_path / "clean.md"
        plan_path.write_text(
            "---\n"
            "title: Clean Plan\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Add fooWidget thing\n"
            "    files:\n"
            "      - a.py\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        report = review_plan(
            plan_path,
            repo_root=tmp_path,
            plan_name="clean",
            invoker=None,
        )
        assert "- Step 1 (current)  OK" in report
        assert "WARN" not in report
        assert "Suggested actions" not in report

    def test_review_plan_emits_path_style_hint_end_to_end(
        self, tmp_path: Path
    ) -> None:
        """When ≥80% of declared paths MISSING_PARENT, the report contains
        the top-level diagnostic without any caller plumbing the hint manually.
        """
        plan_path = tmp_path / "broken.md"
        # Every file lives under nonexistent_dir/ so all four resolve to
        # MISSING_PARENT (parent dir doesn't exist).
        plan_path.write_text(
            "---\n"
            "title: Broken Paths Plan\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Touch foo\n"
            "    files:\n"
            "      - nonexistent_dir/a.py\n"
            "      - nonexistent_dir/b.py\n"
            "  - id: 2\n"
            "    title: Touch bar\n"
            "    files:\n"
            "      - nonexistent_dir/c.py\n"
            "      - nonexistent_dir/d.py\n"
            "    depends_on: [1]\n"
            "---\n",
            encoding="utf-8",
        )
        report = review_plan(
            plan_path,
            repo_root=tmp_path,
            plan_name="broken",
            invoker=None,
        )
        assert "### Plan-wide path issue" in report
        assert "4 of 4" in report
        assert "100% mismatch" in report
        # Per-step lines still rendered.
        assert "- Step 1 (pending)  WARN" in report
        assert "- Step 2 (pending)  WARN" in report


class TestPromoteMissingParents:
    def test_promotes_missing_parent_to_new(self) -> None:
        before = [
            StepFileCheck(
                step_id=1,
                files=[
                    FileCheck(path="ok.py", status=FileExistence.OK),
                    FileCheck(
                        path="dir/new.py", status=FileExistence.MISSING_PARENT
                    ),
                ],
            ),
        ]
        after = _promote_missing_parents(before)
        assert after[0].files[0].status == FileExistence.OK
        assert after[0].files[1].status == FileExistence.NEW
        # Path is preserved.
        assert after[0].files[1].path == "dir/new.py"

    def test_leaves_other_statuses_untouched(self) -> None:
        before = [
            StepFileCheck(
                step_id=2,
                files=[
                    FileCheck(path="a.py", status=FileExistence.OK),
                    FileCheck(path="b.py", status=FileExistence.NEW),
                ],
            ),
        ]
        after = _promote_missing_parents(before)
        assert after[0].files[0].status == FileExistence.OK
        assert after[0].files[1].status == FileExistence.NEW

    def test_does_not_mutate_input(self) -> None:
        before = [
            StepFileCheck(
                step_id=1,
                files=[
                    FileCheck(
                        path="dir/x.py", status=FileExistence.MISSING_PARENT
                    ),
                ],
            ),
        ]
        _promote_missing_parents(before)
        assert before[0].files[0].status == FileExistence.MISSING_PARENT


class TestReviewPlanAllowMissingParent:
    def test_silences_per_step_warn(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        report = review_plan(
            plan_path,
            repo_root=tmp_path,
            plan_name="review-test",
            invoker=None,
            allow_missing_parent=True,
        )
        # Step 3's MISSING_PARENT has been promoted to NEW; the per-step
        # line now reads as a creator, not a WARN.
        assert "- Step 3 (pending)  OK" in report
        assert "missing under repo root" not in report
        # Step 4's heuristic WARN still fires — flag is scoped to file checks.
        assert "- Step 4 (pending)  WARN" in report

    def test_suppresses_path_style_hint(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "broken.md"
        plan_path.write_text(
            "---\n"
            "title: Broken Paths Plan\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Touch foo\n"
            "    files:\n"
            "      - nonexistent_dir/a.py\n"
            "      - nonexistent_dir/b.py\n"
            "  - id: 2\n"
            "    title: Touch bar\n"
            "    files:\n"
            "      - nonexistent_dir/c.py\n"
            "      - nonexistent_dir/d.py\n"
            "    depends_on: [1]\n"
            "---\n",
            encoding="utf-8",
        )
        report = review_plan(
            plan_path,
            repo_root=tmp_path,
            plan_name="broken",
            invoker=None,
            allow_missing_parent=True,
        )
        # Plan-wide hint keys off MISSING_PARENT counts; promoting to NEW
        # zeros that count, so the section must not render.
        assert "### Plan-wide path issue" not in report
        # Per-step lines render as creators rather than WARNs.
        assert "- Step 1 (pending)  OK" in report
        assert "- Step 2 (pending)  OK" in report

    def test_recommendations_list_drops_missing_parent(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_review_fixture(tmp_path)
        result = review_plan_full(
            plan_path,
            repo_root=tmp_path,
            plan_name="review-test",
            invoker=None,
            allow_missing_parent=True,
        )
        sources_for_step_3 = [
            r.source for r in result.recommendations if r.step_id == 3
        ]
        assert "file-check" not in sources_for_step_3

    def test_new_on_done_still_fires(self, tmp_path: Path) -> None:
        """If a DONE step's file is under a missing parent, promoting to NEW
        must still surface the NEW-on-DONE warning — the user marked the step
        complete but the file isn't on disk."""
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: Done But Missing\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Add the thing\n"
            "    files:\n"
            "      - nonexistent_dir/done.py\n"
            "    status: done\n"
            "---\n",
            encoding="utf-8",
        )
        report = review_plan(
            plan_path,
            repo_root=tmp_path,
            plan_name="dbm",
            invoker=None,
            allow_missing_parent=True,
        )
        assert "- Step 1 (done)  WARN" in report
        assert "step marked done" in report

    def test_default_behavior_unchanged(self, tmp_path: Path) -> None:
        """Smoke test: with the flag off, the legacy MISSING_PARENT WARN still
        renders so we know the promotion is gated on the flag."""
        plan_path = _write_review_fixture(tmp_path)
        report = review_plan(
            plan_path,
            repo_root=tmp_path,
            plan_name="review-test",
            invoker=None,
        )
        assert "- Step 3 (pending)  WARN" in report
        assert "parent dir `missing_dir/` doesn't exist" in report


# --- progress reporting ----------------------------------------------------


class _RecordingHandle(StepHandle):
    def __init__(self) -> None:
        self.completed: tuple[float, int] | None = None
        self.failed: tuple[float, str] | None = None

    def complete(self, elapsed_s: float, response_bytes: int) -> None:
        self.completed = (elapsed_s, response_bytes)

    def fail(self, elapsed_s: float, reason: str) -> None:
        self.failed = (elapsed_s, reason)


class _RecordingReporter(ProgressReporter):
    def __init__(self) -> None:
        self.starts: list[tuple[int, int, str]] = []
        self.handles: list[_RecordingHandle] = []

    def start_step(self, idx: int, total: int, label: str) -> StepHandle:
        self.starts.append((idx, total, label))
        h = _RecordingHandle()
        self.handles.append(h)
        return h


class TestReviewPlanProgress:
    def test_complete_on_successful_claude(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        reporter = _RecordingReporter()
        review_plan(
            plan_path,
            repo_root=tmp_path,
            plan_name="rev",
            invoker=lambda p: (0, "review body."),
            reporter=reporter,
            extract_lessons=False,
        )
        assert reporter.starts == [(1, 1, "Claude semantic review")]
        h = reporter.handles[0]
        assert h.completed is not None
        assert h.failed is None
        _, nbytes = h.completed
        assert nbytes == len("review body.".encode("utf-8"))

    def test_fail_when_claude_exec_missing(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        reporter = _RecordingReporter()
        review_plan(
            plan_path,
            repo_root=tmp_path,
            plan_name="rev",
            invoker=lambda p: (127, ""),
            reporter=reporter,
        )
        h = reporter.handles[0]
        assert h.completed is None
        assert h.failed is not None
        _, reason = h.failed
        assert "executable" in reason

    def test_fail_when_claude_exits_nonzero(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        reporter = _RecordingReporter()
        review_plan(
            plan_path,
            repo_root=tmp_path,
            plan_name="rev",
            invoker=lambda p: (3, "partial..."),
            reporter=reporter,
        )
        h = reporter.handles[0]
        assert h.completed is None
        assert h.failed is not None
        _, reason = h.failed
        assert "code 3" in reason

    def test_fail_when_claude_returns_empty_stdout(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        reporter = _RecordingReporter()
        review_plan(
            plan_path,
            repo_root=tmp_path,
            plan_name="rev",
            invoker=lambda p: (0, "   \n"),
            reporter=reporter,
        )
        h = reporter.handles[0]
        assert h.completed is None
        assert h.failed is not None
        _, reason = h.failed
        assert "empty" in reason

    def test_dry_run_emits_no_progress(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        reporter = _RecordingReporter()
        review_plan(
            plan_path,
            repo_root=tmp_path,
            plan_name="rev",
            invoker=lambda p: (0, "irrelevant"),
            dry_run=True,
            reporter=reporter,
        )
        assert reporter.starts == []

    def test_invoker_none_emits_no_progress(self, tmp_path: Path) -> None:
        """No claude call → nothing to report on."""
        plan_path = _write_review_fixture(tmp_path)
        reporter = _RecordingReporter()
        review_plan(
            plan_path,
            repo_root=tmp_path,
            plan_name="rev",
            invoker=None,
            reporter=reporter,
        )
        assert reporter.starts == []


class TestCmdReviewEndToEndStderr:
    """End-to-end: ``StderrReporter`` (the production default) emits lines
    on stderr when ``plan-tool reconcile-plan`` runs.
    """

    def test_emits_progress_on_stderr(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        _write_review_fixture(tmp_path)
        manifest = tmp_path / "m.json"
        manifest.write_text(
            '{"plans": ["1-review-test.md"]}\n', encoding="utf-8"
        )
        (tmp_path / ".git").mkdir()

        original = cli_module.review_plan_full

        def patched(path, **kwargs):
            kwargs["invoker"] = lambda p: (0, "looks fine.")
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.review_cmd.review_plan_full", patched)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            [
                "--manifest",
                str(manifest),
                "reconcile",
                "review-test",
            ]
        )
        assert rc == 0
        err = capsys.readouterr().err
        # Singleton call (n=1) → the ``[1/1]`` counter is suppressed.
        assert "Claude semantic review" in err
        assert "[1/1]" not in err
        assert "done in" in err


# --- Step 1: whole-token regex (substring-bleed regression tests) ----------


class TestHeuristicWholeTokenRegex:
    """Regression tests for the substring-bleed false-positive class.

    Before whole-token matching, ``def parser_setup`` matched the pattern
    ``def parser`` because the check was ``"def parser" in text``.
    After: word-boundary regex rejects the bleed.
    """

    def _plan_with_one_step(
        self, tmp_path: Path, title: str, filename: str
    ) -> Path:
        plan_path = tmp_path / "plan.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            f"    title: {title}\n"
            "    files:\n"
            f"      - {filename}\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        return plan_path

    def test_def_parser_does_not_hit_def_parser_setup(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "x.py").write_text(
            "def parser_setup():\n    pass\n", encoding="utf-8"
        )
        plan = parse_plan(
            self._plan_with_one_step(tmp_path, "Build the parser", "x.py")
        )
        hits = heuristic_already_done(plan, tmp_path)
        assert hits == []

    def test_def_parser_still_hits_def_parser(self, tmp_path: Path) -> None:
        """True positives still fire — the regex doesn't kill the signal."""
        (tmp_path / "x.py").write_text(
            "def parser():\n    pass\n", encoding="utf-8"
        )
        plan = parse_plan(
            self._plan_with_one_step(tmp_path, "Build the parser", "x.py")
        )
        hits = heuristic_already_done(plan, tmp_path)
        assert len(hits) == 1
        assert hits[0].symbol.lower() == "parser"

    def test_class_parser_does_not_hit_class_parserhelper(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "x.py").write_text(
            "class ParserHelper:\n    pass\n", encoding="utf-8"
        )
        plan = parse_plan(
            self._plan_with_one_step(tmp_path, "Build the parser", "x.py")
        )
        hits = heuristic_already_done(plan, tmp_path)
        assert hits == []

    def test_const_foo_does_not_hit_const_foobar(self, tmp_path: Path) -> None:
        (tmp_path / "x.ts").write_text(
            "const foobar = 1;\n", encoding="utf-8"
        )
        plan = parse_plan(
            self._plan_with_one_step(tmp_path, "Wire up the foo", "x.ts")
        )
        hits = heuristic_already_done(plan, tmp_path)
        assert hits == []

    def test_toml_key_does_not_hit_longer_key(self, tmp_path: Path) -> None:
        """`foo =` shouldn't match `foobar =`."""
        (tmp_path / "config.toml").write_text(
            "foobar = true\n", encoding="utf-8"
        )
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Add foo settings\n"
            "    files:\n"
            "      - config.toml\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)
        hits = heuristic_already_done(plan, tmp_path)
        assert hits == []

    def test_quoted_config_pattern_still_works(self, tmp_path: Path) -> None:
        """`"foo"` in JSON should still fire — the existing config tests
        depend on this. Quotes are non-word chars so we don't add `\\b`."""
        (tmp_path / "config.json").write_text(
            '{"foo": 1}\n', encoding="utf-8"
        )
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Add foo settings\n"
            "    files:\n"
            "      - config.json\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)
        hits = heuristic_already_done(plan, tmp_path)
        assert len(hits) == 1
        assert hits[0].pattern == '"foo"'

    def test_prose_header_does_not_hit_compound_header(
        self, tmp_path: Path
    ) -> None:
        """`## Foo` shouldn't match `## FooHelper` (substring bleed at end)."""
        (tmp_path / "notes.md").write_text(
            "## FooHelper\n\nIntro.\n\n## FooHelper\n\nMore.\n",
            encoding="utf-8",
        )
        plan = parse_plan(_write_prose_plan(tmp_path))
        hits = heuristic_already_done(plan, tmp_path)
        assert hits == []


# --- Step 2: detail cross-check -------------------------------------------


class TestHeuristicDetailCrossCheck:
    """When step.detail is set and exists, only flag symbols the detail mentions."""

    def _plan_with_detail(
        self,
        tmp_path: Path,
        title: str,
        filename: str,
        detail_path: str,
    ) -> Path:
        plan_path = tmp_path / "plan.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            f"    title: {title}\n"
            "    files:\n"
            f"      - {filename}\n"
            f"    detail: {detail_path}\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        return plan_path

    def test_symbol_absent_from_detail_suppresses_hit(
        self, tmp_path: Path
    ) -> None:
        """Detail body doesn't name `parser` → no hit even though file has `def parser()`."""
        (tmp_path / "x.py").write_text(
            "def parser():\n    pass\n", encoding="utf-8"
        )
        (tmp_path / "detail.md").write_text(
            "# Step 1\n\n## Why\n\nUnrelated rationale.\n", encoding="utf-8"
        )
        plan = parse_plan(
            self._plan_with_detail(
                tmp_path, "Build the parser", "x.py", "detail.md"
            )
        )
        hits = heuristic_already_done(plan, tmp_path)
        assert hits == []

    def test_symbol_present_in_detail_still_hits(
        self, tmp_path: Path
    ) -> None:
        """Detail body names `parser` → hit fires as before."""
        (tmp_path / "x.py").write_text(
            "def parser():\n    pass\n", encoding="utf-8"
        )
        (tmp_path / "detail.md").write_text(
            "# Step 1\n\n## Why\n\nReplace the existing parser.\n",
            encoding="utf-8",
        )
        plan = parse_plan(
            self._plan_with_detail(
                tmp_path, "Build the parser", "x.py", "detail.md"
            )
        )
        hits = heuristic_already_done(plan, tmp_path)
        assert len(hits) == 1
        assert hits[0].symbol.lower() == "parser"

    def test_missing_detail_file_falls_through(self, tmp_path: Path) -> None:
        """Detail declared but not on disk → don't suppress the hit."""
        (tmp_path / "x.py").write_text(
            "def parser():\n    pass\n", encoding="utf-8"
        )
        # No detail.md file written.
        plan = parse_plan(
            self._plan_with_detail(
                tmp_path, "Build the parser", "x.py", "detail.md"
            )
        )
        hits = heuristic_already_done(plan, tmp_path)
        assert len(hits) == 1

    def test_no_detail_pointer_falls_through(self, tmp_path: Path) -> None:
        """Step without `detail:` field — heuristic behaves as before (no filter)."""
        (tmp_path / "x.py").write_text(
            "def parser():\n    pass\n", encoding="utf-8"
        )
        plan_path = tmp_path / "plan.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Build the parser\n"
            "    files:\n"
            "      - x.py\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)
        hits = heuristic_already_done(plan, tmp_path)
        assert len(hits) == 1

    def test_case_insensitive_match_in_detail(self, tmp_path: Path) -> None:
        """`Parser` in detail matches symbol token `parser`."""
        (tmp_path / "x.py").write_text(
            "class Parser:\n    pass\n", encoding="utf-8"
        )
        (tmp_path / "detail.md").write_text(
            "# Step 1\n\nWe rebuild the Parser class.\n", encoding="utf-8"
        )
        plan = parse_plan(
            self._plan_with_detail(
                tmp_path, "Build the parser", "x.py", "detail.md"
            )
        )
        hits = heuristic_already_done(plan, tmp_path)
        assert len(hits) == 1

    def test_symbol_filter_refuses_rather_than_falls_through_on_an_unsupported_marker(
        self, tmp_path: Path
    ) -> None:
        """Unlike the missing-file/unreadable cases above, a *present,
        readable* detail body that declares an unsupported format version
        must refuse rather than silently returning the symbols unfiltered
        — this function interprets the body's prose, so it's a semantic
        reader and must fail closed."""
        from plan_tool.detail_artifacts import (
            DetailFormatError,
            render_detail_format_version_marker,
        )

        (tmp_path / "x.py").write_text(
            "def parser():\n    pass\n", encoding="utf-8"
        )
        (tmp_path / "detail.md").write_text(
            f"# Step 1\n{render_detail_format_version_marker(999)}\n\n"
            "## Why\n\nReplace the existing parser.\n",
            encoding="utf-8",
        )
        plan = parse_plan(
            self._plan_with_detail(
                tmp_path, "Build the parser", "x.py", "detail.md"
            )
        )
        with pytest.raises(DetailFormatError):
            heuristic_already_done(plan, tmp_path)


# --- Step 3: --no-heuristic flag ------------------------------------------


class TestReviewPlanNoHeuristic:
    """When no_heuristic=True, the heuristic scan is skipped entirely."""

    def _setup_heuristic_tripping_plan(self, tmp_path: Path) -> Path:
        """Plan with one non-done step whose file already has a matching symbol."""
        (tmp_path / "x.py").write_text(
            "def parser():\n    pass\n", encoding="utf-8"
        )
        plan_path = tmp_path / "plan.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Build the parser\n"
            "    files:\n"
            "      - x.py\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        return plan_path

    def test_default_includes_heuristic_warning(self, tmp_path: Path) -> None:
        plan_path = self._setup_heuristic_tripping_plan(tmp_path)
        report = review_plan(
            plan_path,
            repo_root=tmp_path,
            plan_name="p",
            invoker=None,
        )
        # Per-step hint names the symbol/file; the low-confidence disclaimer
        # is hoisted to a single legend line rather than repeated per hit.
        assert "hint: symbol `parser` already in `x.py`" in report
        assert "low-confidence" in report

    def test_no_heuristic_suppresses_warning(self, tmp_path: Path) -> None:
        plan_path = self._setup_heuristic_tripping_plan(tmp_path)
        report = review_plan(
            plan_path,
            repo_root=tmp_path,
            plan_name="p",
            invoker=None,
            no_heuristic=True,
        )
        assert "hint:" not in report

    def test_no_heuristic_keeps_other_checks(self, tmp_path: Path) -> None:
        """File-existence and dep checks still run."""
        plan_path = self._setup_heuristic_tripping_plan(tmp_path)
        report = review_plan(
            plan_path,
            repo_root=tmp_path,
            plan_name="p",
            invoker=None,
            no_heuristic=True,
        )
        # Per-step status block still rendered.
        assert "Per-step status" in report
        assert "Step 1" in report

    def test_cli_no_heuristic_flag(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        self._setup_heuristic_tripping_plan(tmp_path)
        manifest = tmp_path / "m.json"
        manifest.write_text('{"plans": ["plan.md"]}\n', encoding="utf-8")
        (tmp_path / ".git").mkdir()

        # Patch shell_review_invoker to skip the real claude call.
        original_review = cli_module.review_plan_full

        def patched(path, **kwargs):
            kwargs["invoker"] = None
            return original_review(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.review_cmd.review_plan_full", patched)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            ["--manifest", str(manifest), "reconcile", "plan", "--no-heuristic"]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "low-confidence hint" not in out


# --- Code-review fixes ----------------------------------------------------


from plan_tool.review import _compile_pattern


class TestCompilePatternEmptyGuard:
    """Guard against future callers passing an empty needle.

    Today no call site can produce one (templates always include a literal
    keyword), but `re.compile("")` would match every position and inflate
    counts catastrophically. The guard returns a never-match pattern.
    """

    def test_empty_needle_never_matches(self) -> None:
        regex = _compile_pattern("", line_anchored=False)
        assert regex.findall("anything at all here") == []

    def test_empty_needle_never_matches_line_anchored(self) -> None:
        regex = _compile_pattern("", line_anchored=True)
        assert regex.findall("# Header\n\nbody\n") == []

    def test_normal_needle_still_works(self) -> None:
        regex = _compile_pattern("def parser", line_anchored=False)
        assert regex.findall("def parser():\n") == ["def parser"]
        assert regex.findall("def parser_setup():\n") == []


# --- Step 1: extract_recommendations --------------------------------------


from plan_tool.review import (
    _make_rec_id,
)


_REC_PLAN = """---
title: Recs Plan
status: in-progress
priority: medium
steps:
  - id: 1
    title: First
    files:
      - a.py
    status: done
  - id: 2
    title: Second
    files:
      - b.py
    depends_on: [1]
    status: current
---

# Recs Plan
"""


def _write_recs_plan(tmp_path: Path) -> Path:
    p = tmp_path / "plan.md"
    p.write_text(_REC_PLAN, encoding="utf-8")
    return p


class TestMakeRecId:
    def test_stable_across_calls(self) -> None:
        a = _make_rec_id(2, "deps", "depends on step 1 which is blocked")
        b = _make_rec_id(2, "deps", "depends on step 1 which is blocked")
        assert a == b

    def test_changes_with_content(self) -> None:
        a = _make_rec_id(2, "deps", "alpha")
        b = _make_rec_id(2, "deps", "beta")
        assert a != b

    def test_step_id_in_prefix(self) -> None:
        rec_id = _make_rec_id(3, "file-check", "x")
        assert rec_id.startswith("step3-file-check-")

    def test_plan_prefix_when_step_id_none(self) -> None:
        rec_id = _make_rec_id(None, "path-style", "x")
        assert rec_id.startswith("plan-path-style-")


class TestExtractRecommendationsFileChecks:
    def test_missing_parent_emits_medium_severity(self, tmp_path: Path) -> None:
        plan_path = _write_recs_plan(tmp_path)
        plan = parse_plan(plan_path)
        file_checks = [
            StepFileCheck(
                step_id=2,
                files=[FileCheck(path="b.py", status=FileExistence.MISSING_PARENT)],
            ),
        ]
        recs = extract_recommendations(
            plan, "p",
            repo_root=tmp_path,
            file_checks=file_checks,
            heuristic_hits=[],
            dep_issues=[],
            path_style_hint=None,
        )
        assert len(recs) == 1
        assert recs[0].source == "file-check"
        assert recs[0].confidence == "supported"
        # Demoted from high: a single declared path that doesn't resolve
        # is a pre-execution structural hint on an unstarted step, and
        # apply now offers a durable fix (move it to creates:).
        assert recs[0].severity == "medium"
        assert recs[0].step_id == 2
        assert "doesn't resolve" in recs[0].title
        # The path is carried so apply can move it files: -> creates:.
        assert recs[0].file_path == "b.py"

    def test_new_on_done_emits_medium_severity(self, tmp_path: Path) -> None:
        plan_path = _write_recs_plan(tmp_path)
        plan = parse_plan(plan_path)
        file_checks = [
            StepFileCheck(
                step_id=1,
                files=[FileCheck(path="a.py", status=FileExistence.NEW)],
            ),
        ]
        recs = extract_recommendations(
            plan, "p",
            repo_root=tmp_path,
            file_checks=file_checks,
            heuristic_hits=[],
            dep_issues=[],
            path_style_hint=None,
        )
        assert len(recs) == 1
        assert recs[0].source == "file-check"
        assert recs[0].confidence == "supported"
        assert recs[0].severity == "medium"
        # suggested action references reconcile mode for this plan + step
        assert "reconcile" in (recs[0].suggested_action or "")
        assert "step 1" in (recs[0].suggested_action or "")

    def test_ok_files_skipped(self, tmp_path: Path) -> None:
        plan_path = _write_recs_plan(tmp_path)
        plan = parse_plan(plan_path)
        file_checks = [
            StepFileCheck(
                step_id=1,
                files=[FileCheck(path="a.py", status=FileExistence.OK)],
            ),
        ]
        recs = extract_recommendations(
            plan, "p",
            repo_root=tmp_path,
            file_checks=file_checks,
            heuristic_hits=[],
            dep_issues=[],
            path_style_hint=None,
        )
        assert recs == []

    def test_new_on_pending_skipped(self, tmp_path: Path) -> None:
        """NEW on a non-DONE step is the expected creator case → no rec."""
        plan_path = _write_recs_plan(tmp_path)
        plan = parse_plan(plan_path)
        file_checks = [
            StepFileCheck(
                step_id=2,  # status: current
                files=[FileCheck(path="b.py", status=FileExistence.NEW)],
            ),
        ]
        recs = extract_recommendations(
            plan, "p",
            repo_root=tmp_path,
            file_checks=file_checks,
            heuristic_hits=[],
            dep_issues=[],
            path_style_hint=None,
        )
        assert recs == []


class TestExtractRecommendationsHeuristic:
    def test_emits_info_severity(self, tmp_path: Path) -> None:
        plan_path = _write_recs_plan(tmp_path)
        plan = parse_plan(plan_path)
        recs = extract_recommendations(
            plan, "p",
            repo_root=tmp_path,
            file_checks=[],
            heuristic_hits=[
                HeuristicHit(
                    step_id=2, file="b.py", symbol="Foo", pattern="class Foo"
                )
            ],
            dep_issues=[],
            path_style_hint=None,
        )
        assert len(recs) == 1
        assert recs[0].source == "heuristic"
        assert recs[0].severity == "info"
        assert recs[0].step_id == 2
        assert recs[0].confidence == "limited"
        assert "low-confidence hint" in recs[0].title


class TestExtractRecommendationsDeps:
    def test_blocked_dep_high(self, tmp_path: Path) -> None:
        plan_path = _write_recs_plan(tmp_path)
        plan = parse_plan(plan_path)
        recs = extract_recommendations(
            plan, "p",
            repo_root=tmp_path,
            file_checks=[],
            heuristic_hits=[],
            dep_issues=[DepIssue(step_id=2, depends_on=1, reason="blocked")],
            path_style_hint=None,
        )
        assert len(recs) == 1
        assert recs[0].source == "deps"
        assert recs[0].severity == "high"
        assert recs[0].confidence == "supported"

    def test_unknown_dep_critical(self, tmp_path: Path) -> None:
        plan_path = _write_recs_plan(tmp_path)
        plan = parse_plan(plan_path)
        recs = extract_recommendations(
            plan, "p",
            repo_root=tmp_path,
            file_checks=[],
            heuristic_hits=[],
            dep_issues=[DepIssue(step_id=2, depends_on=99, reason="unknown")],
            path_style_hint=None,
        )
        assert len(recs) == 1
        assert recs[0].severity == "critical"
        assert recs[0].confidence == "supported"


class TestFilesCoherenceRecommendationFix:
    """Both files-coherence kinds now carry a ``suggested_action`` (the
    deterministic-finding sweep) so the walk renders a "suggested" fix."""

    def test_not_mentioned_nit_has_suggested_fix(self) -> None:
        from plan_tool.review import (
            _files_coherence_recommendation,
        )

        rec = _files_coherence_recommendation(
            FilesCoherenceIssue(
                step_id=2, kind="files_only",
                path="plan_tool/auto_reconcile.py", near_match=None,
            )
        )
        assert rec.source == "files-coherence"
        assert rec.suggested_action is not None
        assert "plan_tool/auto_reconcile.py" in rec.suggested_action
        assert "files:" in rec.suggested_action

    def test_detail_only_keeps_its_suggested_fix(self) -> None:
        from plan_tool.review import (
            _files_coherence_recommendation,
        )

        rec = _files_coherence_recommendation(
            FilesCoherenceIssue(
                step_id=3, kind="detail_only", path="apps/typo.ts",
                near_match="apps/foo.ts",
            )
        )
        assert rec.suggested_action is not None


class TestExtractRecommendationsPathStyle:
    def test_path_style_hint_emits_first_critical(self, tmp_path: Path) -> None:
        plan_path = _write_recs_plan(tmp_path)
        plan = parse_plan(plan_path)
        hint = PathStyleHint(
            missing_count=4,
            total=5,
            ratio=0.8,
            examples=["src/a.py", "src/b.py"],
            repo_root=tmp_path,
        )
        recs = extract_recommendations(
            plan, "p",
            repo_root=tmp_path,
            file_checks=[],
            heuristic_hits=[],
            dep_issues=[],
            path_style_hint=hint,
        )
        # Plan-wide rec comes first.
        assert recs[0].source == "path-style"
        assert recs[0].severity == "critical"
        assert recs[0].step_id is None
        assert "80%" in recs[0].title


class TestExtractRecommendationsClaude:
    def test_parses_findings_block(self, tmp_path: Path) -> None:
        plan_path = _write_recs_plan(tmp_path)
        plan = parse_plan(plan_path)
        claude_stdout = (
            "Some review prose...\n\n"
            "## Findings\n\n"
            "- CRITICAL: serious bug at foo.py:10\n"
            "- HIGH: missing validation\n"
            "- NIT: trailing whitespace\n"
        )
        recs = extract_recommendations(
            plan, "p",
            repo_root=tmp_path,
            file_checks=[],
            heuristic_hits=[],
            dep_issues=[],
            path_style_hint=None,
            claude_stdout=claude_stdout,
        )
        assert len(recs) == 3
        assert [r.source for r in recs] == ["claude", "claude", "claude"]
        sevs = [r.severity for r in recs]
        assert sevs == ["critical", "high", "nit"]

    def test_no_findings_block_yields_nothing(self, tmp_path: Path) -> None:
        plan_path = _write_recs_plan(tmp_path)
        plan = parse_plan(plan_path)
        recs = extract_recommendations(
            plan, "p",
            repo_root=tmp_path,
            file_checks=[],
            heuristic_hits=[],
            dep_issues=[],
            path_style_hint=None,
            claude_stdout="just prose, no findings block here",
        )
        assert recs == []

    def test_none_marker_yields_nothing(self, tmp_path: Path) -> None:
        plan_path = _write_recs_plan(tmp_path)
        plan = parse_plan(plan_path)
        recs = extract_recommendations(
            plan, "p",
            repo_root=tmp_path,
            file_checks=[],
            heuristic_hits=[],
            dep_issues=[],
            path_style_hint=None,
            claude_stdout="## Findings\n\n_(none)_\n",
        )
        assert recs == []


class TestExtractRecommendationsStableIds:
    def test_same_inputs_yield_same_ids(self, tmp_path: Path) -> None:
        plan_path = _write_recs_plan(tmp_path)
        plan = parse_plan(plan_path)
        kwargs = dict(
            plan=plan, plan_name="p",
            repo_root=tmp_path,
            file_checks=[],
            heuristic_hits=[
                HeuristicHit(step_id=2, file="b.py", symbol="Foo", pattern="class Foo")
            ],
            dep_issues=[DepIssue(step_id=2, depends_on=1, reason="blocked")],
            path_style_hint=None,
        )
        a = extract_recommendations(**kwargs)
        b = extract_recommendations(**kwargs)
        assert [r.id for r in a] == [r.id for r in b]

    def test_confidence_is_metadata_only_for_finding_identity_and_order(
        self, tmp_path: Path
    ) -> None:
        plan = parse_plan(_write_recs_plan(tmp_path))
        recs = extract_recommendations(
            plan,
            "p",
            repo_root=tmp_path,
            file_checks=[],
            heuristic_hits=[
                HeuristicHit(step_id=2, file="b.py", symbol="Foo", pattern="class Foo")
            ],
            dep_issues=[DepIssue(step_id=2, depends_on=1, reason="blocked")],
            path_style_hint=None,
        )
        changed_confidence = [
            dataclasses.replace(rec, confidence="supported") for rec in recs
        ]

        assert [rec.id for rec in changed_confidence] == [rec.id for rec in recs]
        assert [rec.severity for rec in changed_confidence] == [
            rec.severity for rec in recs
        ]
        assert [rec.source for rec in changed_confidence] == [rec.source for rec in recs]


class TestExtractRecommendationsOrdering:
    def test_order_is_plan_wide_then_per_step_then_claude(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_recs_plan(tmp_path)
        plan = parse_plan(plan_path)
        hint = PathStyleHint(
            missing_count=4, total=5, ratio=0.8,
            examples=["x"], repo_root=tmp_path,
        )
        recs = extract_recommendations(
            plan, "p",
            repo_root=tmp_path,
            file_checks=[
                StepFileCheck(
                    step_id=2,
                    files=[FileCheck(
                        path="b.py", status=FileExistence.MISSING_PARENT
                    )],
                ),
            ],
            heuristic_hits=[],
            dep_issues=[],
            path_style_hint=hint,
            claude_stdout="## Findings\n\n- HIGH: an issue\n",
        )
        sources = [r.source for r in recs]
        # path-style first (plan-wide), then file-check (per-step), then claude.
        assert sources == ["path-style", "file-check", "claude"]
        assert recs[-1].confidence == "limited"


# --- launcher.parse_finding_bullets (reused by review extraction) -----------


from plan_tool.launcher import parse_finding_bullets, FindingBullet


class TestParseFindingBullets:
    def test_returns_bullets_with_severity(self) -> None:
        out = (
            "## Findings\n\n"
            "- CRITICAL: bug at foo.py:10\n"
            "- HIGH: missing validation\n"
            "- NIT: small thing\n"
        )
        bullets = parse_finding_bullets(out)
        assert len(bullets) == 3
        assert bullets[0].severity == "CRITICAL"
        assert bullets[0].body == "bug at foo.py:10"
        assert bullets[2].severity == "NIT"

    def test_no_findings_returns_empty(self) -> None:
        assert parse_finding_bullets("just prose") == []

    def test_none_marker_returns_empty(self) -> None:
        assert parse_finding_bullets("## Findings\n\n_(none)_\n") == []

    def test_unspecified_bullet_marked(self) -> None:
        # Freestanding bullets *before* the first severity bullet are
        # bucketed as unspecified. Bullets that fall after a severity
        # bullet are absorbed into that finding's body so a trailing
        # ``## Decision`` sub-block stays attached.
        out = (
            "## Findings\n\n"
            "- not-a-token: weird format\n"
            "- HIGH: known one\n"
        )
        bullets = parse_finding_bullets(out)
        assert len(bullets) == 2
        sevs = [b.severity for b in bullets]
        assert "HIGH" in sevs
        assert "UNSPECIFIED" in sevs
        unspec = next(b for b in bullets if b.severity == "UNSPECIFIED")
        assert unspec.body == "not-a-token: weird format"

    def test_anchors_to_last_findings(self) -> None:
        out = (
            "## Findings\n\n- CRITICAL: from prompt echo\n\n"
            "Some prose...\n\n"
            "## Findings\n\n- NIT: real one\n"
        )
        bullets = parse_finding_bullets(out)
        assert len(bullets) == 1
        assert bullets[0].severity == "NIT"


# --- parse_redirect_block (Reconcile Subcommand Split, step 4) -----------


class TestParseRedirectBlock:
    """``parse_redirect_block`` mirrors ``parse_decision_block``'s shape
    to extract the ``## Redirect`` sub-block emitted by the
    ``run-reconcile`` prompt under findings whose root cause is in the
    plan."""

    _WELL_FORMED = (
        "Some bullet preamble.\n\n"
        "## Redirect\n\n"
        "- **Reason**: step.files declares a stale path; the code is correct\n"
        "- **Suggested next**: detail --reconcile\n"
    )

    def test_returns_none_when_heading_absent(self) -> None:
        from plan_tool.review import parse_redirect_block

        assert parse_redirect_block("plain bullet with no heading") is None

    def test_returns_none_for_empty_string(self) -> None:
        from plan_tool.review import parse_redirect_block

        assert parse_redirect_block("") is None

    def test_extracts_reason_and_suggested_next(self) -> None:
        from plan_tool.review import parse_redirect_block

        r = parse_redirect_block(self._WELL_FORMED)
        assert r is not None
        assert r.reason == (
            "step.files declares a stale path; the code is correct"
        )
        assert r.suggested_next == "detail --reconcile"

    @pytest.mark.parametrize(
        "reason_line",
        [
            "**Reason**: stale",
            "Reason: stale",
            "- Reason: stale",
            "- **Reason**: stale",
            "* **Reason**: stale",
            "-   **Reason**   :   stale",
            "- Reason - stale",
        ],
    )
    def test_tolerates_bullet_and_bold_field_variants(
        self, reason_line: str
    ) -> None:
        """Same tolerance asserted today against ``parse_decision_block``:
        leading bullet (``-``/``*``), optional bold, ``:`` or ``-``
        separator, permissive whitespace."""
        from plan_tool.review import parse_redirect_block

        text = f"## Redirect\n\n{reason_line}\n"
        r = parse_redirect_block(text)
        assert r is not None
        assert r.reason == "stale"

    def test_returns_redirect_with_empty_fields_when_labels_missing(
        self,
    ) -> None:
        """A heading without labelled lines is a contract miss — the
        parser still returns a ``Redirect`` so the CLI can surface the
        signal with an ``(unspecified)`` filler rather than dropping
        it."""
        from plan_tool.review import parse_redirect_block

        text = "## Redirect\n\n(no fields here)\n"
        r = parse_redirect_block(text)
        assert r is not None
        assert r.reason == ""
        assert r.suggested_next == ""

    def test_first_redirect_block_wins(self) -> None:
        """Mirrors ``parse_decision_block``'s posture: if claude emits
        two blocks under one finding (against the prompt contract), the
        first wins."""
        from plan_tool.review import parse_redirect_block

        text = (
            "## Redirect\n\n"
            "- **Reason**: first reason\n"
            "- **Suggested next**: detail --reconcile\n\n"
            "## Redirect\n\n"
            "- **Reason**: second reason\n"
        )
        r = parse_redirect_block(text)
        assert r is not None
        assert r.reason == "first reason"

    def test_a_heading_shaped_line_with_no_blank_line_before_it_is_not_a_redirect(
        self,
    ) -> None:
        """The prompt contract requires the heading to start its own
        paragraph (a blank line, or start-of-text, before it). A
        ``## Redirect``-shaped line that instead continues the same
        paragraph as the preceding prose is not a real sub-block."""
        from plan_tool.review import parse_redirect_block

        text = (
            "Some prose that wraps onto a continuation line\n"
            "## Redirect happens to start this next line\n"
        )
        assert parse_redirect_block(text) is None

    def test_blank_line_immediately_before_the_heading_still_matches(
        self,
    ) -> None:
        from plan_tool.review import parse_redirect_block

        text = "prose\n\n## Redirect\n\n- **Reason**: stale\n"
        r = parse_redirect_block(text)
        assert r is not None
        assert r.reason == "stale"

    def test_crlf_blank_line_before_the_heading_still_matches(self) -> None:
        """A CRLF-separated blank line is still a paragraph break -- cached
        or replayed payloads aren't guaranteed universal-newline-normalized
        the way a live subprocess capture is."""
        from plan_tool.review import parse_redirect_block

        text = "prose\r\n\r\n## Redirect\r\n\r\n- **Reason**: stale\r\n"
        r = parse_redirect_block(text)
        assert r is not None
        assert r.reason == "stale"

    def test_a_heading_shaped_line_inside_a_fenced_citation_is_not_a_redirect(
        self,
    ) -> None:
        """A finding legitimately quoting this repo's own ``## Redirect``
        convention inside a fenced code block must not fake a real
        sub-block -- mirrors the fence exclusion ``_split_audit_fix`` and
        ``_split_audit_restated_and_fix`` already apply for the same
        reason (CLAUDE.md's heading-anchored sub-block convention)."""
        from plan_tool.review import parse_redirect_block

        text = (
            "consider this citation:\n\n"
            "```\n"
            "prose\n\n## Redirect\n\nfake fields here\n"
            "```\n"
        )
        assert parse_redirect_block(text) is None


class TestExtractRunReconcileRedirects:
    """``extract_run_reconcile_recommendations`` tags recs with
    ``source="run-reconcile"`` and populates ``rec.redirect`` per
    bullet from the inline ``## Redirect`` sub-block when present."""

    def test_attaches_redirect_when_present(self) -> None:
        from plan_tool.review import extract_run_reconcile_recommendations

        stdout = (
            "## Findings\n\n"
            "- MEDIUM: apps/old-foo.ts declared but missing\n"
            "\n"
            "## Redirect\n\n"
            "- **Reason**: step.files declares a stale path\n"
            "- **Suggested next**: detail --reconcile\n"
        )
        recs = extract_run_reconcile_recommendations(stdout, step_id=4)
        assert len(recs) == 1
        assert recs[0].redirect is not None
        assert recs[0].redirect.reason == (
            "step.files declares a stale path"
        )
        assert recs[0].redirect.suggested_next == "detail --reconcile"

    def test_leaves_redirect_none_when_absent(self) -> None:
        from plan_tool.review import extract_run_reconcile_recommendations

        stdout = (
            "## Findings\n\n"
            "- HIGH: handleSubmit() dispatches before the validation step\n"
        )
        recs = extract_run_reconcile_recommendations(stdout, step_id=4)
        assert len(recs) == 1
        assert recs[0].redirect is None

    def test_redirect_wins_over_a_malformed_trailing_fix_marker(self) -> None:
        """A malformed finding carrying both contract alternatives keeps
        its redirect instead of absorbing the redirect block as a fix."""
        from plan_tool.review import extract_run_reconcile_recommendations

        def extract(fix: str):
            stdout = (
                "## Findings\n\n"
                f"- MEDIUM: stale path declared -> fix: {fix}\n\n"
                "## Redirect\n\n"
                "- **Reason**: step.files declares a stale path\n"
                "- **Suggested next**: detail --reconcile\n"
            )
            return extract_run_reconcile_recommendations(stdout, step_id=4)[0]

        rec = extract("replace the path")
        reworded = extract("replace the path entirely with a new one")

        assert rec.redirect is not None
        assert rec.redirect.reason == "step.files declares a stale path"
        assert rec.redirect.suggested_next == "detail --reconcile"
        assert rec.suggested_action is None
        assert (rec.id, rec.title, rec.body) == (
            reworded.id,
            reworded.title,
            reworded.body,
        )
        # The discarded fix marker/text must not silently take the
        # ``## Redirect`` section's raw text down with it: body/title stay
        # in the same shape a well-formed (no colliding marker) redirect
        # finding would produce, so a reader of ``rec.body`` still sees
        # what claude actually wrote rather than a marker-truncated stub.
        from plan_tool.review import extract_run_reconcile_recommendations

        well_formed = extract_run_reconcile_recommendations(
            "## Findings\n\n"
            "- MEDIUM: stale path declared\n\n"
            "## Redirect\n\n"
            "- **Reason**: step.files declares a stale path\n"
            "- **Suggested next**: detail --reconcile\n",
            step_id=4,
        )[0]
        assert rec.body == well_formed.body
        assert "## Redirect" in rec.body

    def test_fix_remediation_wrapping_onto_a_redirect_shaped_line_is_not_a_real_redirect(
        self,
    ) -> None:
        """A contract-violating multi-line ``-> fix:`` remediation that
        happens to wrap onto a line starting with the same words as the
        redirect heading must not be mistaken for a genuine ``##
        Redirect`` sub-block -- the prompt contract requires the real
        heading to start its own paragraph (a blank line before it), and
        this finding's continuation line has none."""
        from plan_tool.review import extract_run_reconcile_recommendations

        stdout = (
            "## Findings\n\n"
            "- MEDIUM: something wrong -> fix: also check the\n"
            "## Redirect heading regex does not match inside quoted text\n"
        )
        rec = extract_run_reconcile_recommendations(stdout, step_id=4)[0]
        assert rec.redirect is None
        assert rec.suggested_action == (
            "also check the ## Redirect heading regex does not match "
            "inside quoted text"
        )

    def test_a_coincidental_field_empty_heading_does_not_swallow_a_real_trailing_fix(
        self,
    ) -> None:
        """A finding that merely discusses the ``## Redirect`` convention
        (a blank-line-preceded heading with no populated Reason/Suggested
        next fields -- indistinguishable, by parse_redirect_block's own
        deliberate contract-miss leniency, from a genuine near-miss
        redirect) must not let a real trailing ``-> fix:`` marker further
        down the same body get silently discarded."""
        from plan_tool.review import extract_run_reconcile_recommendations

        stdout = (
            "## Findings\n\n"
            "- MEDIUM: the parser documents its own convention.\n\n"
            "When writing sub-blocks, remember the format:\n\n"
            "## Redirect\n\n"
            "is how the heading looks in this repo -> fix: rename the "
            "section heading\n"
        )
        rec = extract_run_reconcile_recommendations(stdout, step_id=4)[0]
        assert rec.suggested_action == "rename the section heading"
        assert "-> fix:" not in rec.body

    def test_a_well_formed_redirect_with_no_colliding_marker_leaves_body_whitespace_untouched(
        self,
    ) -> None:
        """When there is no fix marker to strip, the collision-handling
        path must not run at all -- it must not canonicalize whitespace
        (e.g. an incidental double blank line before the heading) that a
        marker-free redirect finding never asked to have rewritten."""
        from plan_tool.review import extract_run_reconcile_recommendations

        stdout = (
            "## Findings\n\n"
            "- MEDIUM: stale path declared\n\n\n"
            "## Redirect\n\n"
            "- **Reason**: step.files declares a stale path\n"
            "- **Suggested next**: detail --reconcile\n"
        )
        rec = extract_run_reconcile_recommendations(stdout, step_id=4)[0]
        assert rec.body == (
            "stale path declared\n\n\n## Redirect\n\n"
            "- **Reason**: step.files declares a stale path\n"
            "- **Suggested next**: detail --reconcile"
        )

    def test_tags_source_as_run_reconcile(self) -> None:
        from plan_tool.review import extract_run_reconcile_recommendations

        stdout = (
            "## Findings\n\n"
            "- HIGH: missing implementation\n"
            "- MEDIUM: stale path\n"
            "\n"
            "## Redirect\n\n"
            "- **Reason**: plan needs the rename\n"
            "- **Suggested next**: detail --reconcile\n"
        )
        recs = extract_run_reconcile_recommendations(stdout, step_id=4)
        assert len(recs) == 2
        assert all(r.source == "run-reconcile" for r in recs)
        # ``_make_rec_id`` namespaces ids by source so a parallel
        # ``reconcile`` save for the same step wouldn't collide.
        assert all(r.id.startswith("step4-run-reconcile-") for r in recs)


class TestExtractRunReconcileFix:
    """``extract_run_reconcile_recommendations`` splits the ``→ fix:``
    one-line code remediation onto ``suggested_action`` (parse_fix=True)
    so the walk can display the proposed fix, while leaving the rec
    non-dispatchable (run-reconcile edits land inline during the audit)."""

    def test_fix_lands_on_suggested_action_and_strips_from_body(
        self,
    ) -> None:
        from plan_tool.review import extract_run_reconcile_recommendations

        stdout = (
            "## Findings\n\n"
            "- HIGH: `handleSubmit()` in `apps/foo.ts` (step 4 \"wire "
            "validation\") dispatches before the detail's validation step "
            "→ fix: call validateForm() ahead of the dispatch "
            "(impact: high, complexity: low)\n"
        )
        recs = extract_run_reconcile_recommendations(stdout, step_id=4)
        assert len(recs) == 1
        rec = recs[0]
        assert rec.suggested_action == (
            "call validateForm() ahead of the dispatch"
        )
        # Fix + triage stripped from the prose body and title.
        assert "→ fix:" not in rec.body
        assert "impact:" not in rec.body
        assert rec.body.startswith("`handleSubmit()` in `apps/foo.ts`")
        assert (rec.impact, rec.complexity) == ("high", "low")

    def test_fix_absent_leaves_suggested_action_none(self) -> None:
        from plan_tool.review import extract_run_reconcile_recommendations

        stdout = (
            "## Findings\n\n"
            "- MEDIUM: `apps/foo.ts` over-delivers an unused export "
            "(impact: low, complexity: low)\n"
        )
        recs = extract_run_reconcile_recommendations(stdout, step_id=4)
        assert recs[0].suggested_action is None

    def test_marker_shaped_text_earlier_in_body_does_not_win_over_trailing_fix(
        self,
    ) -> None:
        """The marker is TRAILING by contract; an earlier fix-shaped
        occurrence (e.g. the finding discussing review.py's own marker
        syntax, plausible in this self-hosting repo) must not be picked
        over the real trailing one -- a plain leftmost-vs-last bug, found
        independent of the fencing question."""
        from plan_tool.review import extract_run_reconcile_recommendations

        stdout = (
            "## Findings\n\n"
            "- HIGH: `review.py` documents its own marker syntax as "
            "\"→ fix: <text>\", but the reconcile prompt never enforces it "
            "→ fix: add a validator for the marker contract "
            "(impact: high, complexity: low)\n"
        )
        rec = extract_run_reconcile_recommendations(stdout, step_id=4)[0]
        assert rec.suggested_action == (
            "add a validator for the marker contract"
        )
        assert '"→ fix: <text>"' in rec.body

    def test_fenced_later_occurrence_does_not_beat_the_real_trailing_fix(
        self,
    ) -> None:
        """Round-5 regression: unlike the leftmost-vs-last case above, this
        specifically exercises the fence-exclusion guard itself -- the fake
        occurrence sits AFTER the real one, so without fence exclusion
        "last occurrence wins" would pick the fake one. (Confirmed by
        mutation: this test fails if `_split_audit_fix`'s
        `_outside_fences` filter is removed.) The fenced text itself is
        excised from the captured fix; legitimate unfenced trailing prose
        is not."""
        from plan_tool.review import extract_run_reconcile_recommendations

        stdout = (
            "## Findings\n\n"
            "- HIGH: gap in `apps/foo.ts` -> fix: add the missing call. "
            "The finding also cites review.py's own docs:\n\n"
            "  ```\n  documents its own marker as -> fix: <text>\n  ```\n"
            "(impact: high, complexity: low)\n"
        )
        rec = extract_run_reconcile_recommendations(stdout, step_id=4)[0]
        assert rec.suggested_action == (
            "add the missing call. The finding also cites review.py's own "
            "docs:"
        )
        assert "```" not in rec.suggested_action
        assert "<text>" not in rec.suggested_action

    def test_run_reconcile_fix_is_not_will_apply_label(self) -> None:
        """A run-reconcile fix renders under the neutral "suggested"
        label — it is NOT in AUDIT_FIX_SOURCES, so the walk doesn't claim
        apply will make it (the edit already landed inline)."""
        from plan_tool.review import (
            AUDIT_FIX_SOURCES,
            audit_targeted_fix,
            extract_run_reconcile_recommendations,
        )

        stdout = (
            "## Findings\n\n"
            "- HIGH: gap in `apps/foo.ts` → fix: add the call "
            "(impact: high, complexity: low)\n"
        )
        rec = extract_run_reconcile_recommendations(stdout, step_id=4)[0]
        assert "run-reconcile" not in AUDIT_FIX_SOURCES
        # Never fed to apply_finding as the verbatim edit.
        assert audit_targeted_fix(rec) is None

    def test_plain_reconcile_does_not_parse_fix(self) -> None:
        """``parse_fix`` is source-derived: plain ``reconcile`` predates the
        ``→ fix:`` convention, so the marker stays inline in the body and
        suggested_action is None."""
        from plan_tool.review import extract_reconcile_recommendations

        stdout = (
            "## Findings\n\n"
            "- HIGH: step body drifts → fix: tweak the wording "
            "(impact: high, complexity: low)\n"
        )
        recs = extract_reconcile_recommendations(
            stdout, step_id=2, source="reconcile"
        )
        assert recs[0].suggested_action is None
        assert "→ fix:" in recs[0].body

    def test_misshaped_header_recovers_severity(self) -> None:
        """``HIGH `[anchor]`: prose`` recovers severity like plan-audit."""
        from plan_tool.review import extract_reconcile_recommendations

        stdout = (
            "## Findings\n\n"
            "- HIGH `[files-drift]`: step.files lists a path that is gone "
            "(impact: high, complexity: low)\n"
        )
        recs = extract_reconcile_recommendations(
            stdout, step_id=2, source="reconcile"
        )
        assert len(recs) == 1
        assert recs[0].severity == "high"
        assert not recs[0].title.startswith("HIGH")


class TestExtractDetailReconcileFix:
    """``detail-reconcile`` findings adopt the plan-audit ``→ fix:``
    convention AND are applied via ``apply_finding`` — so the fix renders
    under "will apply" and feeds the apply as the targeted edit."""

    def test_fix_lands_on_suggested_action(self) -> None:
        from plan_tool.review import extract_reconcile_recommendations

        stdout = (
            "## Findings\n\n"
            "- HIGH: step 2's `step.files` lists `apps/old-foo.ts` which no "
            "longer exists → fix: replace it with `apps/foo.ts` in step 2's "
            "`step.files` (impact: medium, complexity: low)\n"
        )
        recs = extract_reconcile_recommendations(
            stdout, step_id=2, source="detail-reconcile"
        )
        assert recs[0].suggested_action == (
            "replace it with `apps/foo.ts` in step 2's `step.files`"
        )
        assert "→ fix:" not in recs[0].body

    def test_detail_reconcile_fix_is_will_apply(self) -> None:
        """detail-reconcile IS in AUDIT_FIX_SOURCES — its fix is rendered
        as "will apply" and injected into apply_finding."""
        from plan_tool.review import (
            AUDIT_FIX_SOURCES,
            audit_targeted_fix,
            extract_reconcile_recommendations,
        )

        stdout = (
            "## Findings\n\n"
            "- HIGH: step 2 path is stale → fix: replace `a.ts` with `b.ts` "
            "(impact: medium, complexity: low)\n"
        )
        rec = extract_reconcile_recommendations(
            stdout, step_id=2, source="detail-reconcile"
        )[0]
        assert "detail-reconcile" in AUDIT_FIX_SOURCES
        assert audit_targeted_fix(rec) == "replace `a.ts` with `b.ts`"


class TestClaudeReconcilePlanFix:
    """reconcile-plan's semantic pass (``_claude_recommendations``, source
    ``claude``) now splits a ``→ fix:`` onto suggested_action and — since
    these findings are applied via ``apply_finding`` — renders "will
    apply" and feeds the apply via :func:`audit_targeted_fix`."""

    def test_fix_lands_on_suggested_action_and_strips_body(self) -> None:
        from plan_tool.review import _claude_recommendations

        stdout = (
            "Prose review.\n\n"
            "## Findings\n\n"
            "- HIGH: step 2's `step.files` lists `apps/old-foo.ts` which no "
            "longer exists → fix: replace it with `apps/foo.ts` in step 2's "
            "`step.files`\n"
        )
        recs = _claude_recommendations(stdout)
        assert len(recs) == 1
        rec = recs[0]
        assert rec.source == "claude"
        assert rec.suggested_action == (
            "replace it with `apps/foo.ts` in step 2's `step.files`"
        )
        assert "→ fix:" not in rec.body
        assert rec.body.startswith("step 2's `step.files`")

    def test_fix_absent_leaves_suggested_action_none(self) -> None:
        from plan_tool.review import _claude_recommendations

        stdout = (
            "## Findings\n\n"
            "- NIT: `bar()` in `lib/util.ts` lacks a docstring\n"
        )
        assert _claude_recommendations(stdout)[0].suggested_action is None

    def test_claude_fix_is_will_apply(self) -> None:
        from plan_tool.review import (
            AUDIT_FIX_SOURCES,
            _claude_recommendations,
            audit_targeted_fix,
        )

        stdout = (
            "## Findings\n\n"
            "- HIGH: step 1 path stale → fix: replace `a.ts` with `b.ts`\n"
        )
        rec = _claude_recommendations(stdout)[0]
        assert "claude" in AUDIT_FIX_SOURCES
        assert audit_targeted_fix(rec) == "replace `a.ts` with `b.ts`"


class TestExtractReconcileTriageTags:
    """``extract_reconcile_recommendations`` parses the inline
    ``(impact: …, complexity: …)`` pair the reconcile prompts emit into
    ``rec.impact`` / ``rec.complexity`` and strips it from the body."""

    def test_parses_inline_impact_complexity(self) -> None:
        from plan_tool.review import extract_reconcile_recommendations

        stdout = (
            "## Findings\n\n"
            "- HIGH: add retry to the fetch call "
            "(impact: high, complexity: low)\n"
            "- LOW: rename the helper (impact: low, complexity: high)\n"
        )
        recs = extract_reconcile_recommendations(stdout, step_id=2)
        assert (recs[0].impact, recs[0].complexity) == ("high", "low")
        assert (recs[1].impact, recs[1].complexity) == ("low", "high")
        # Pair stripped from body + title (machine metadata, not prose).
        assert "impact:" not in recs[0].body
        assert "complexity:" not in recs[0].title
        assert recs[0].body == "add retry to the fetch call"

    def test_reconcile_high_impact_nit_keeps_explicit_severity(
        self,
    ) -> None:
        """Impact is independent metadata; an explicit NIT stays a NIT."""
        from plan_tool.review import extract_reconcile_recommendations

        stdout = (
            "## Findings\n\n"
            "- NIT: clarify the helper name (impact: high, complexity: low)\n"
        )
        recs = extract_reconcile_recommendations(stdout, step_id=2)

        assert len(recs) == 1
        assert recs[0].severity == "nit"
        assert recs[0].impact == "high"

    def test_reconcile_high_impact_unspecified_is_coerced_to_high(
        self,
    ) -> None:
        """An unlabelled high-impact finding gets a useful fallback level."""
        from plan_tool.review import extract_reconcile_recommendations

        stdout = (
            "## Findings\n\n"
            "- clarify the helper name (impact: high, complexity: low)\n"
        )
        recs = extract_reconcile_recommendations(stdout, step_id=2)

        assert len(recs) == 1
        assert recs[0].severity == "high"
        assert recs[0].impact == "high"

    def test_low_label_remains_medium_and_blocking(self) -> None:
        from plan_tool.review import extract_reconcile_recommendations

        stdout = (
            "## Findings\n\n"
            "- LOW: clarify the helper name (impact: high, complexity: low)\n"
        )
        recs = extract_reconcile_recommendations(stdout, step_id=2)

        assert len(recs) == 1
        assert recs[0].severity == "medium"
        assert recs[0].impact == "high"

    def test_triage_tags_drive_deferral(self) -> None:
        from plan_tool.review import (
            extract_reconcile_recommendations,
            partition_findings_for_triage,
        )

        stdout = (
            "## Findings\n\n"
            "- HIGH: load-bearing fix (impact: high, complexity: low)\n"
            "- LOW: nice-to-have (impact: low, complexity: high)\n"
        )
        recs = extract_reconcile_recommendations(stdout, step_id=2)
        open_apply, open_deferred = partition_findings_for_triage(recs)
        assert [r.title for r in open_apply] == ["load-bearing fix"]
        assert [r.title for r in open_deferred] == ["nice-to-have"]

    def test_untagged_bullet_falls_open(self) -> None:
        from plan_tool.review import extract_reconcile_recommendations

        stdout = "## Findings\n\n- HIGH: no triage tag here\n"
        recs = extract_reconcile_recommendations(stdout, step_id=2)
        assert recs[0].impact is None and recs[0].complexity is None
        assert recs[0].body == "no triage tag here"

    def test_triage_pair_coexists_with_redirect_block(self) -> None:
        """A finding carrying both the inline pair and a ``## Redirect``
        sub-block keeps both pieces of structured metadata."""
        from plan_tool.review import extract_run_reconcile_recommendations

        stdout = (
            "## Findings\n\n"
            "- MEDIUM: stale path declared (impact: medium, complexity: low)\n"
            "\n"
            "## Redirect\n\n"
            "- **Reason**: step.files declares a stale path\n"
            "- **Suggested next**: detail --reconcile\n"
        )
        recs = extract_run_reconcile_recommendations(stdout, step_id=4)
        assert (recs[0].impact, recs[0].complexity) == ("medium", "low")
        assert "impact:" not in recs[0].body
        assert recs[0].redirect is not None
        assert recs[0].redirect.reason == "step.files declares a stale path"


# --- Step 3: save-by-default in cmd_review --------------------------------


class TestCmdReviewSaveByDefault:
    def _setup(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> Path:
        _write_review_fixture(tmp_path)
        manifest = tmp_path / "m.json"
        manifest.write_text(
            '{"plans": ["1-review-test.md"]}\n', encoding="utf-8"
        )
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        return manifest

    def _patch_review_plan_full(
        self,
        cli_module,
        monkeypatch: pytest.MonkeyPatch,
        claude_stdout: str = "",
    ) -> None:
        original = cli_module.review_plan_full

        def patched(path, **kwargs):
            if claude_stdout:
                kwargs["invoker"] = lambda p: (0, claude_stdout)
            else:
                kwargs["invoker"] = None
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.review_cmd.review_plan_full", patched)

    def _run_log_events(self, tmp_path: Path) -> list[dict]:
        import json

        events: list[dict] = []
        for log in sorted((tmp_path / ".plan-tool" / "runs").rglob("*.jsonl")):
            for line in log.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    events.append(json.loads(line))
        return events

    def test_opens_a_run_log_with_the_canonical_command_name(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The audit verbs used to spend claude with no run log at all — no
        cost record, no in-flight snapshot. See BUG_BACKLOG."""
        from plan_tool.cli import app as cli_module

        manifest = self._setup(tmp_path, monkeypatch)
        self._patch_review_plan_full(cli_module, monkeypatch)
        # Invoked under the ``reconcile`` alias; the log names the canonical
        # verb so one grep finds every run regardless of alias.
        rc = cli_module.main(
            ["--manifest", str(manifest), "reconcile", "review-test"]
        )
        assert rc == 0
        events = self._run_log_events(tmp_path)
        starts = [e for e in events if e.get("event") == "run_start"]
        ends = [e for e in events if e.get("event") == "run_end"]
        assert [e["command"] for e in starts] == ["reconcile-plan"]
        assert len(ends) == 1
        assert ends[0]["rc"] == 0
        assert ends[0]["outcome"] == "success"
        # run_end fired, so the in-flight snapshot is torn down.
        assert not list((tmp_path / ".plan-tool" / "runs").rglob("in-flight.json"))

    def test_claude_calls_land_in_the_run_log(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The open writer alone records nothing — ``shell._emit_call_end``
        no-ops unless a sink is installed. Drives the emit the real
        ``claude_invoke`` performs per call and asserts it lands, tagged with
        the bind-time phase."""
        from plan_tool import shell
        from plan_tool.cli import app as cli_module

        manifest = self._setup(tmp_path, monkeypatch)
        original = cli_module.review_plan_full

        def patched(path, **kwargs):
            kwargs["invoker"] = None
            shell._emit_call_end(
                phase="claude_invoke",  # the shell-side default the sink overrides
                attempt=1,
                rc=0,
                duration_ms=1234,
                stdout_bytes=42,
                prompt_bytes=7,
            )
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.review_cmd.review_plan_full", patched)
        rc = cli_module.main(
            ["--manifest", str(manifest), "reconcile", "review-test"]
        )
        assert rc == 0
        ends = [
            e for e in self._run_log_events(tmp_path)
            if e.get("event") == "claude_call_end"
        ]
        assert len(ends) == 1
        assert ends[0]["phase"] == "reconcile_plan"
        assert ends[0]["duration_ms"] == 1234

    def test_dry_run_opens_no_run_log(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--dry-run renders the prompt and spends nothing, so it writes no
        log — the log exists iff the verb may spend claude."""
        from plan_tool.cli import app as cli_module

        manifest = self._setup(tmp_path, monkeypatch)
        self._patch_review_plan_full(cli_module, monkeypatch)
        rc = cli_module.main(
            ["--manifest", str(manifest), "reconcile", "review-test", "--dry-run"]
        )
        assert rc == 0
        assert not (tmp_path / ".plan-tool").exists()

    def test_default_saves_to_disk(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = self._setup(tmp_path, monkeypatch)
        self._patch_review_plan_full(cli_module, monkeypatch)
        rc = cli_module.main(
            ["--manifest", str(manifest), "reconcile", "review-test"]
        )
        assert rc == 0
        # Saved file under plan-details/<slug>/reports/
        reviews = list(
            (tmp_path / "plan-details" / "review-test" / "reports").glob("*.json")
        )
        assert len(reviews) == 1
        # Closing line on stdout names the path.
        out = capsys.readouterr().out
        assert "Saved to" in out
        assert str(reviews[0]) in out

    def test_no_save_skips_persistence(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = self._setup(tmp_path, monkeypatch)
        self._patch_review_plan_full(cli_module, monkeypatch)
        rc = cli_module.main(
            ["--manifest", str(manifest), "reconcile", "review-test", "--no-save"]
        )
        assert rc == 0
        # --no-save skips the walkable *review sidecar* (its documented
        # scope), not every artifact: the call still spends claude, so the
        # run log is still written.
        assert not list(
            (tmp_path / "plan-details" / "review-test" / "reports").glob("*.json")
        )
        assert list((tmp_path / ".plan-tool" / "runs").rglob("*.jsonl"))
        out = capsys.readouterr().out
        assert "Saved to" not in out

    def test_dry_run_skips_save(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = self._setup(tmp_path, monkeypatch)
        self._patch_review_plan_full(cli_module, monkeypatch)
        rc = cli_module.main(
            ["--manifest", str(manifest), "reconcile", "review-test", "--dry-run"]
        )
        assert rc == 0
        assert not (tmp_path / ".plan-tool").exists()
        out = capsys.readouterr().out
        assert "Saved to" not in out

    def test_saved_file_round_trips(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.review_persistence import load_review

        manifest = self._setup(tmp_path, monkeypatch)
        self._patch_review_plan_full(cli_module, monkeypatch)
        cli_module.main(
            ["--manifest", str(manifest), "reconcile", "review-test"]
        )
        reviews = list(
            (tmp_path / "plan-details" / "review-test" / "reports").glob("*.json")
        )
        assert len(reviews) == 1
        loaded = load_review(reviews[0])
        assert loaded.plan_slug == "review-test"
        assert "## Plan Review" in loaded.report_md

    def test_saved_review_carries_fingerprints(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.review_persistence import load_review

        manifest = self._setup(tmp_path, monkeypatch)
        self._patch_review_plan_full(cli_module, monkeypatch)
        cli_module.main(
            ["--manifest", str(manifest), "reconcile", "review-test"]
        )
        reviews = list(
            (tmp_path / "plan-details" / "review-test" / "reports").glob("*.json")
        )
        assert len(reviews) == 1
        loaded = load_review(reviews[0])
        # Both staleness axes captured: a non-empty plan digest and a
        # present, code-keyed fingerprint (the plan markdown is excluded).
        assert loaded.plan_fingerprint != ""
        assert loaded.code_fingerprint_present is True
        assert "parser.py" in loaded.code_fingerprint
        assert "renderer.py" in loaded.code_fingerprint
        assert "1-review-test.md" not in loaded.code_fingerprint

    def test_review_plan_str_wrapper_still_works(self, tmp_path: Path) -> None:
        """Backwards-compat: review_plan returns str."""
        plan_path = _write_review_fixture(tmp_path)
        out = review_plan(
            plan_path,
            repo_root=tmp_path,
            plan_name="x",
            invoker=None,
        )
        assert isinstance(out, str)
        assert "## Plan Review" in out

    def test_cmd_review_allows_missing_parent_by_default(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Review defaults to --allow-missing-parent: Step 3 isn't flagged."""
        from plan_tool.cli import app as cli_module

        manifest = self._setup(tmp_path, monkeypatch)
        self._patch_review_plan_full(cli_module, monkeypatch)
        monkeypatch.setattr(
            "plan_tool.cli.review_cmd.walk_recommendations", lambda *a, **k: None
        )
        rc = cli_module.main(
            ["--manifest", str(manifest), "reconcile", "review-test", "--no-walk"]
        )
        assert rc == 0
        out = capsys.readouterr().out
        # MISSING_PARENT promoted to NEW → no Step 3 finding, no path hint.
        assert "missing_dir/foo_endpoint.py" not in out
        assert "MISSING_PARENT" not in out

    def test_cmd_review_no_walk_keeps_full_report(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = self._setup(tmp_path, monkeypatch)
        self._patch_review_plan_full(cli_module, monkeypatch)
        calls: list[object] = []
        monkeypatch.setattr(
            "plan_tool.cli.review_cmd.walk_recommendations",
            lambda *a, **k: calls.append((a, k)),
        )
        # --no-allow-missing-parent keeps the Step 3 MISSING_PARENT finding,
        # which review now suppresses by default; this test needs a finding.
        rc = cli_module.main(
            [
                "--manifest",
                str(manifest),
                "reconcile",
                "review-test",
                "--no-walk",
                "--no-allow-missing-parent",
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        # --no-walk → the report is the only surface, so keep full detail.
        assert "Suggested actions" in out
        assert "missing_dir/foo_endpoint.py" in out
        # The walk did not run.
        assert calls == []

    def test_cmd_review_walk_run_slims_report(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = self._setup(tmp_path, monkeypatch)
        self._patch_review_plan_full(cli_module, monkeypatch)
        calls: list[object] = []
        # Stub the walk at the name cmd_review calls
        # (plan_tool.cli.review_cmd.walk_recommendations).
        monkeypatch.setattr(
            "plan_tool.cli.review_cmd.walk_recommendations",
            lambda *a, **k: calls.append((a, k)),
        )
        # The walk is per-finding and TTY-gated; simulate a terminal so it
        # runs. --no-allow-missing-parent keeps the Step 3 MISSING_PARENT
        # finding, which review now suppresses by default; this test needs a
        # finding.
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        rc = cli_module.main(
            [
                "--manifest",
                str(manifest),
                "reconcile",
                "review-test",
                "-y",
                "--no-allow-missing-parent",
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        # Walk ran → report omits the block and slims the WARN line.
        assert calls, "expected the interactive walk to run"
        assert "Suggested actions" not in out
        assert "- Step 3 (pending)  WARN — 1 finding" in out
        assert "Per-step status" in out

    def test_review_walk_environment_allows_explicit_remote_non_tty_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import argparse

        from plan_tool.cli import _review_walk_environment_allows

        def ns(**overrides: object) -> argparse.Namespace:
            base = dict(no_walk=False, no_save=False, dry_run=False, yes=False)
            base.update(overrides)
            return argparse.Namespace(**base)

        # Ordinary non-TTY input cannot walk; --yes does not widen it.
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
        monkeypatch.delenv("PLAN_TOOL_HUMAN_IO", raising=False)
        assert _review_walk_environment_allows(ns()) is False
        assert _review_walk_environment_allows(ns(yes=True)) is False
        # Explicit remote mode is the sole headless exception.
        monkeypatch.setenv("PLAN_TOOL_HUMAN_IO", "remote")
        assert _review_walk_environment_allows(ns()) is True
        assert _review_walk_environment_allows(ns(yes=True)) is True
        # Each opt-out disqualifies the walk on its own.
        assert _review_walk_environment_allows(ns(no_walk=True)) is False
        assert _review_walk_environment_allows(ns(no_save=True)) is False
        assert _review_walk_environment_allows(ns(dry_run=True)) is False
        # A TTY (with no opt-out) is eligible.
        monkeypatch.delenv("PLAN_TOOL_HUMAN_IO", raising=False)
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        assert _review_walk_environment_allows(ns()) is True


class TestReviewPlanFull:
    def test_reconcile_rejects_unmatched_plan_before_review_invocation_or_saved_report(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import ReviewError, review_plan_full

        plan_path = _write_review_fixture(tmp_path)
        original = plan_path.read_text(encoding="utf-8") + "\n```\n"
        plan_path.write_text(original, encoding="utf-8")

        with pytest.raises(ReviewError, match="unmatched opening code fence"):
            review_plan_full(
                plan_path,
                repo_root=tmp_path,
                plan_name="review-test",
                invoker=lambda _prompt: pytest.fail("review must not run"),
            )

        assert plan_path.read_text(encoding="utf-8") == original

    def test_returns_review_result(self, tmp_path: Path) -> None:
        from plan_tool.review import review_plan_full, ReviewResult

        plan_path = _write_review_fixture(tmp_path)
        result = review_plan_full(
            plan_path,
            repo_root=tmp_path,
            plan_name="x",
            invoker=None,
        )
        assert isinstance(result, ReviewResult)
        assert isinstance(result.report, str)
        assert isinstance(result.recommendations, list)
        assert result.dry_run is False

    def test_dry_run_returns_prompt(self, tmp_path: Path) -> None:
        from plan_tool.review import review_plan_full

        plan_path = _write_review_fixture(tmp_path)
        result = review_plan_full(
            plan_path,
            repo_root=tmp_path,
            plan_name="x",
            invoker=None,
            dry_run=True,
        )
        assert result.dry_run is True
        assert result.recommendations == []
        # report carries the rendered claude prompt
        assert "plan-vs-codebase reality check" in result.report

    def test_recommendations_extracted(self, tmp_path: Path) -> None:
        """Plan with a missing-parent path produces a file-check rec."""
        from plan_tool.review import review_plan_full

        plan_text = (
            "---\n"
            "title: Bad Paths\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: t\n"
            "    files:\n"
            "      - some/missing/dir/x.py\n"
            "    status: current\n"
            "---\n"
        )
        plan_path = tmp_path / "plan.md"
        plan_path.write_text(plan_text, encoding="utf-8")
        result = review_plan_full(
            plan_path,
            repo_root=tmp_path,
            plan_name="x",
            invoker=None,
        )
        # at least one rec from the missing-parent file check + the
        # plan-wide path-style hint (since 100% of paths miss).
        sources = {r.source for r in result.recommendations}
        assert "path-style" in sources

    def test_threads_walk_will_run(self, tmp_path: Path) -> None:
        """``walk_will_run=True`` slims the report while keeping recs intact."""
        from plan_tool.review import review_plan_full

        plan_path = _write_review_fixture(tmp_path)
        result = review_plan_full(
            plan_path,
            repo_root=tmp_path,
            plan_name="review-test",
            invoker=None,
            walk_will_run=True,
        )
        assert "### Suggested actions" not in result.report
        # WARN line is the count form; the per-step map still renders.
        assert "- Step 3 (pending)  WARN — 1 finding" in result.report
        assert "### Per-step status" in result.report
        # Slimming the report doesn't drop the structured recommendations.
        assert result.recommendations


# --- completeness checks (Steps 1-5) ---------------------------------------


_FULL_BODY_SECTIONS = (
    "## Overview\n\nReal overview prose.\n\n"
    "## Problem statement\n\nReal problem description.\n\n"
    "## Architecture\n\nReal architecture detail.\n\n"
    "## References\n\n- [Docs](https://example.com) — primary reference.\n\n"
    "## Steps\n\nSee frontmatter.\n\n"
    "## Out of scope\n\nReal out-of-scope.\n\n"
    "## Risks\n\nReal risk discussion.\n\n"
    "## Testing\n\nReal testing strategy.\n\n"
    "## Acceptance criteria\n\nReal acceptance bullets.\n\n"
    "## Deferred\n\nReal deferred items.\n"
)


def _write_completeness_plan(
    tmp_path: Path,
    *,
    body: str = "",
    lessons_path: Optional[str] = None,
    extra_step_yaml: str = "",
) -> Path:
    """Write a minimal valid plan with the supplied body."""
    plan_path = tmp_path / "completeness-plan.md"
    lessons_yaml = f"lessons: {lessons_path}\n" if lessons_path else ""
    plan_path.write_text(
        "---\n"
        "title: Completeness Plan\n"
        "status: in-progress\n"
        "priority: medium\n"
        f"{lessons_yaml}"
        "steps:\n"
        "  - id: 1\n"
        "    title: do thing\n"
        "    files:\n"
        "      - foo.py\n"
        "    status: current\n"
        f"{extra_step_yaml}"
        "---\n"
        "\n"
        f"{body}",
        encoding="utf-8",
    )
    (tmp_path / "foo.py").write_text("x = 1\n", encoding="utf-8")
    return plan_path


# Re-import for clarity at the test-class boundary.
from plan_tool.review import (  # noqa: E402
    BodyCompletenessIssue,
    DetailBodyIssue,
    DetailCoverageIssue,
    FilesCoherenceIssue,
    LessonsCoverageIssue,
    check_body_completeness,
    check_detail_body_completeness,
    check_detail_coverage,
    check_files_coherence,
    check_lessons_coverage,
)


class TestCheckBodyCompleteness:
    def test_all_required_sections_present_no_issues(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_completeness_plan(tmp_path, body=_FULL_BODY_SECTIONS)
        assert check_body_completeness(plan_path) == []

    def test_missing_three_sections(self, tmp_path: Path) -> None:
        body = (
            "## Overview\n\nx\n\n"
            "## Problem statement\n\nx\n\n"
            "## Architecture\n\nx\n\n"
            "## Steps\n\nx\n\n"
            "## Out of scope\n\nx\n\n"
            "## Acceptance criteria\n\nx\n"
        )
        plan_path = _write_completeness_plan(tmp_path, body=body)
        issues = check_body_completeness(plan_path)
        kinds = {(i.kind, i.section) for i in issues}
        assert ("missing", "Risks") in kinds
        assert ("missing", "Testing") in kinds
        assert ("missing", "Deferred") in kinds

    def test_todo_placeholder_flagged(self, tmp_path: Path) -> None:
        body = _FULL_BODY_SECTIONS.replace(
            "## Architecture\n\nReal architecture detail.\n\n",
            "## Architecture\n\n_(TODO)_\n\n",
        )
        plan_path = _write_completeness_plan(tmp_path, body=body)
        issues = check_body_completeness(plan_path)
        assert any(
            i.kind == "placeholder" and i.section == "Architecture"
            for i in issues
        )

    def test_tbd_placeholder_flagged(self, tmp_path: Path) -> None:
        # A whole-body `TBD` is as vacuous as `TODO` — flag it.
        for marker in ("TBD", "(TBD)", "_(TBD)_"):
            body = _FULL_BODY_SECTIONS.replace(
                "## Architecture\n\nReal architecture detail.\n\n",
                f"## Architecture\n\n{marker}\n\n",
            )
            plan_path = _write_completeness_plan(tmp_path, body=body)
            issues = check_body_completeness(plan_path)
            assert any(
                i.kind == "placeholder" and i.section == "Architecture"
                for i in issues
            ), f"{marker!r} should be flagged as a placeholder"

    def test_none_answer_is_not_a_placeholder(self, tmp_path: Path) -> None:
        # A legitimate "nothing here" answer in a section is real content, not a
        # placeholder — `None` / `N/A` must NOT be flagged (a Deferred section
        # with nothing deferred is a complete answer).
        for answer in ("None", "N/A", "_None — nothing deferred._"):
            body = _FULL_BODY_SECTIONS.replace(
                "## Deferred\n\nReal deferred items.\n",
                f"## Deferred\n\n{answer}\n",
            )
            plan_path = _write_completeness_plan(tmp_path, body=body)
            issues = check_body_completeness(plan_path)
            assert not any(
                i.section == "Deferred" for i in issues
            ), f"{answer!r} is a real answer, not a placeholder"

    def test_placeholder_recommendation_embeds_content_shape(
        self, tmp_path: Path
    ) -> None:
        """When ``_body_completeness_recommendation`` lifts a
        placeholder finding into a Recommendation, the rec body must
        include the recommended content shape from
        ``PLAN_BODY_SECTION_SHAPES``. Without the shape, apply_finding
        refuses placeholder findings as 'too vague to act on without
        guessing content' (observed during bug #24 verification).
        """
        from plan_tool.review import (
            _body_completeness_recommendation,
            check_body_completeness,
        )

        body = _FULL_BODY_SECTIONS.replace(
            "## Risks\n\nReal risk discussion.\n\n",
            "## Risks\n\n_(TODO)_\n\n",
        )
        plan_path = _write_completeness_plan(tmp_path, body=body)
        issues = check_body_completeness(plan_path)
        risks_issue = next(
            i for i in issues
            if i.kind == "placeholder" and i.section == "Risks"
        )

        rec = _body_completeness_recommendation(risks_issue)

        # The rec body must include both the original placeholder
        # detail AND the recommended shape -- apply_finding needs
        # both: the "what's wrong" and the "what should fill it."
        assert "Risks" in rec.body
        assert "placeholder" in rec.body
        assert "Recommended content shape:" in rec.body
        # Sanity: the shape text mentions risk-shape vocabulary
        # (failure modes / severity / mitigation) per the dict.
        assert any(
            tok in rec.body
            for tok in ("failure modes", "severity", "mitigation")
        ), rec.body

    def test_placeholder_recommendation_omits_shape_for_unknown_section(
        self, tmp_path: Path
    ) -> None:
        """Sections absent from ``PLAN_BODY_SECTION_SHAPES`` (e.g. a
        custom required-section list passed to
        ``check_body_completeness``) fall back to issue.details alone,
        preserving the legacy behavior for callers with custom
        section lists."""
        from plan_tool.review import (
            _body_completeness_recommendation,
        )

        custom_issue = BodyCompletenessIssue(
            kind="placeholder",
            section="MyCustomSection",  # not in PLAN_BODY_SECTION_SHAPES
            details="`## MyCustomSection` body is a `_(TODO)_` placeholder",
        )
        rec = _body_completeness_recommendation(custom_issue)
        assert "MyCustomSection" in rec.body
        # No shape recommendation appended -- legacy behavior preserved.
        assert "Recommended content shape:" not in rec.body

    def test_skip_marker_suppresses_finding(self, tmp_path: Path) -> None:
        body = _FULL_BODY_SECTIONS.replace(
            "## Architecture\n\nReal architecture detail.\n\n",
            "## Architecture\n\n_(TODO)_\n\n"
            "<!-- completeness:skip Architecture -->\n\n",
        )
        plan_path = _write_completeness_plan(tmp_path, body=body)
        issues = check_body_completeness(plan_path)
        assert not any(i.section == "Architecture" for i in issues)

    def test_empty_body_flags_every_required_section(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.create import PLAN_BODY_SECTIONS

        plan_path = _write_completeness_plan(tmp_path, body="")
        issues = check_body_completeness(plan_path)
        # Every PLAN_BODY_SECTIONS entry produces a "missing" finding.
        assert len(issues) == len(PLAN_BODY_SECTIONS)
        assert all(i.kind == "missing" for i in issues)


class TestCheckDetailCoverage:
    def test_no_detail_declared_not_flagged(self, tmp_path: Path) -> None:
        # A step with files but no `detail:` declaration is NOT a coverage
        # defect — authoring detail files is normal operations, not
        # something to reconcile against the plan's declarations.
        plan_path = _write_completeness_plan(tmp_path, body=_FULL_BODY_SECTIONS)
        plan = parse_plan(plan_path)
        assert check_detail_coverage(plan, plan_path, tmp_path) == []

    def test_undeclared_detail_no_files_not_flagged(
        self, tmp_path: Path
    ) -> None:
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: pure analysis\n"
            "    complexity: low\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)
        assert check_detail_coverage(plan, plan_path, tmp_path) == []

    def test_declared_but_missing_on_disk_flagged_medium(
        self, tmp_path: Path
    ) -> None:
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: x\n"
            "    files: [foo.py]\n"
            "    detail: details/missing-step-1.md\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
        plan = parse_plan(plan_path)
        issues = check_detail_coverage(plan, plan_path, tmp_path)
        assert len(issues) == 1
        assert issues[0].kind == "missing_on_disk"
        assert issues[0].detail_path == "details/missing-step-1.md"

    def test_done_step_skipped(self, tmp_path: Path) -> None:
        # A non-done step with files and a declared-but-missing detail is
        # flagged (test_declared_but_missing_on_disk_flagged_medium). The
        # same shape on a done step produces nothing — the detail's
        # briefing job is finished once the step is implemented.
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: x\n"
            "    files: [foo.py]\n"
            "    detail: details/missing.md\n"
            "    status: done\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
        plan = parse_plan(plan_path)
        assert check_detail_coverage(plan, plan_path, tmp_path) == []

    def _plan_with_unset_pointer(self, tmp_path: Path) -> Path:
        # Plan `2-p.md` → bundle `plan-details/p/`; step 1 has no `detail:`.
        plan_path = tmp_path / "2-p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: build it\n"
            "    files: [foo.py]\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
        return plan_path

    def test_on_disk_but_unreferenced_flagged(self, tmp_path: Path) -> None:
        # A detail file exists for step 1's id but the frontmatter never
        # points at it — the orphaned-after-split state.
        plan_path = self._plan_with_unset_pointer(tmp_path)
        bundle = tmp_path / "plan-details" / "p"
        bundle.mkdir(parents=True)
        (bundle / "01-build-it.md").write_text("# Build\n", encoding="utf-8")
        plan = parse_plan(plan_path)
        issues = check_detail_coverage(plan, plan_path, tmp_path)
        assert len(issues) == 1
        assert issues[0].kind == "unreferenced_on_disk"
        assert issues[0].detail_path == "plan-details/p/01-build-it.md"

    def test_unreferenced_on_disk_uses_the_canonical_posix_labeler(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The persisted recommendation id must use the shared POSIX label."""
        from plan_tool import review as review_module

        plan_path = self._plan_with_unset_pointer(tmp_path)
        bundle = tmp_path / "plan-details" / "p"
        bundle.mkdir(parents=True)
        (bundle / "01-build-it.md").write_text("# Build\n", encoding="utf-8")
        monkeypatch.setattr(
            review_module,
            "_repo_relative_posix",
            lambda _path, _root: "canonical/detail-path.md",
        )

        issues = check_detail_coverage(parse_plan(plan_path), plan_path, tmp_path)

        assert issues[0].detail_path == "canonical/detail-path.md"
        rec = review_module._detail_coverage_recommendation(
            issues[0], plan_name="p"
        )
        assert rec.id == review_module._make_rec_id(
            1, "detail-coverage", "unreferenced_on_diskcanonical/detail-path.md"
        )

    def test_unreferenced_on_disk_still_fires_for_audited_step(
        self, tmp_path: Path
    ) -> None:
        # Visibility and the reattach-the-pointer diagnostic are
        # complementary: the same canonical-only step whose body now yields
        # quality findings still gets its ``unreferenced_on_disk`` finding.
        plan_path = self._plan_with_unset_pointer(tmp_path)
        bundle = tmp_path / "plan-details" / "p"
        bundle.mkdir(parents=True)
        (bundle / "01-build.md").write_text(
            "# Build\n\n## Summary\n\nonly a summary\n", encoding="utf-8"
        )
        plan = parse_plan(plan_path)
        coverage = check_detail_coverage(plan, plan_path, tmp_path)
        assert [i.kind for i in coverage] == ["unreferenced_on_disk"]
        assert coverage[0].detail_path == "plan-details/p/01-build.md"
        body_issues = check_detail_body_completeness(
            plan, tmp_path, plan_path=plan_path
        )
        assert {i.step_id for i in body_issues} == {1}

    def test_no_file_on_disk_pointer_unset_not_flagged(
        self, tmp_path: Path
    ) -> None:
        # Pointer unset AND no file → normal un-authored step, no finding.
        plan_path = self._plan_with_unset_pointer(tmp_path)
        plan = parse_plan(plan_path)
        assert check_detail_coverage(plan, plan_path, tmp_path) == []

    def test_unreferenced_file_claimed_by_other_step_not_flagged(
        self, tmp_path: Path
    ) -> None:
        # The only `01-*.md` file is already pointed at by another step, so
        # it isn't a free orphan for step 1.
        plan_path = tmp_path / "2-p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: build it\n"
            "    files: [foo.py]\n"
            "    status: current\n"
            "  - id: 2\n"
            "    title: other\n"
            "    files: [bar.py]\n"
            "    detail: plan-details/p/01-claimed.md\n"
            "    status: pending\n"
            "---\n",
            encoding="utf-8",
        )
        for fn in ("foo.py", "bar.py"):
            (tmp_path / fn).write_text("x\n", encoding="utf-8")
        bundle = tmp_path / "plan-details" / "p"
        bundle.mkdir(parents=True)
        (bundle / "01-claimed.md").write_text("# c\n", encoding="utf-8")
        plan = parse_plan(plan_path)
        issues = check_detail_coverage(plan, plan_path, tmp_path)
        # Step 2's pointer resolves (file exists); step 1 has no free
        # orphan → no findings.
        assert issues == []


class TestCheckDetailBodyCompleteness:
    def _plan_with_detail(
        self, tmp_path: Path, detail_body: str
    ) -> tuple[Path, "Plan"]:
        from plan_tool.schema import Plan as _Plan  # type: ignore

        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: x\n"
            "    files: [foo.py]\n"
            "    detail: details/01.md\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
        details_dir = tmp_path / "details"
        details_dir.mkdir()
        (details_dir / "01.md").write_text(detail_body, encoding="utf-8")
        return plan_path, parse_plan(plan_path)

    def test_all_seven_sections_populated_no_issues(
        self, tmp_path: Path
    ) -> None:
        body = (
            "# Step 1\n\n"
            "## Summary\n\noverview\n\n"
            "## Table of Contents\n\n- [Why](#why) — motivation\n\n"
            "## Why\n\nsome reason\n\n"
            "## Files\n\nfoo.py\n\n"
            "## Implementation\n\ndo thing\n\n"
            "## Tests\n\ntest thing\n\n"
            "## Acceptance criteria\n\nbullet\n"
        )
        _, plan = self._plan_with_detail(tmp_path, body)
        assert check_detail_body_completeness(plan, tmp_path) == []

    def test_missing_two_sections(self, tmp_path: Path) -> None:
        body = (
            "# Step 1\n\n"
            "## Summary\n\noverview\n\n"
            "## Table of Contents\n\n- [Why](#why) — motivation\n\n"
            "## Why\n\nx\n\n"
            "## Files\n\nfoo.py\n\n"
            "## Implementation\n\nx\n"
        )
        _, plan = self._plan_with_detail(tmp_path, body)
        issues = check_detail_body_completeness(plan, tmp_path)
        sections = {(i.kind, i.section) for i in issues}
        assert ("missing", "Tests") in sections
        assert ("missing", "Acceptance criteria") in sections

    def test_missing_reviewer_scaffolding_sections(
        self, tmp_path: Path
    ) -> None:
        """Summary and Table of Contents are required reviewer-facing
        scaffolding. A body that omits them must surface both as
        missing-section issues."""
        body = (
            "# Step 1\n\n"
            "## Why\n\nx\n\n"
            "## Files\n\nfoo.py\n\n"
            "## Implementation\n\nx\n\n"
            "## Tests\n\nx\n\n"
            "## Acceptance criteria\n\nx\n"
        )
        _, plan = self._plan_with_detail(tmp_path, body)
        issues = check_detail_body_completeness(plan, tmp_path)
        sections = {(i.kind, i.section) for i in issues}
        assert ("missing", "Summary") in sections
        assert ("missing", "Table of Contents") in sections

    def test_todo_placeholder_in_section(self, tmp_path: Path) -> None:
        body = (
            "# Step 1\n\n"
            "## Summary\n\noverview\n\n"
            "## Table of Contents\n\n- [Why](#why) — motivation\n\n"
            "## Why\n\nx\n\n"
            "## Files\n\nfoo.py\n\n"
            "## Implementation\n\nx\n\n"
            "## Tests\n\n_(TODO)_\n\n"
            "## Acceptance criteria\n\nx\n"
        )
        _, plan = self._plan_with_detail(tmp_path, body)
        issues = check_detail_body_completeness(plan, tmp_path)
        assert any(
            i.kind == "placeholder" and i.section == "Tests" for i in issues
        )

    def test_done_step_skipped(self, tmp_path: Path) -> None:
        # A thin detail body on a non-done step yields missing-section
        # issues (test_missing_two_sections). Once the step is done the
        # body check no longer fires — the briefing already did its job.
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: x\n"
            "    files: [foo.py]\n"
            "    detail: details/01.md\n"
            "    status: done\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
        details_dir = tmp_path / "details"
        details_dir.mkdir()
        (details_dir / "01.md").write_text(
            "# Step 1\n\n## Summary\n\nonly a summary\n", encoding="utf-8"
        )
        plan = parse_plan(plan_path)
        assert check_detail_body_completeness(plan, tmp_path) == []

    # --- canonical-only detail files (pointer unset, file on disk) --------

    # Plan ``2-p.md`` → bundle ``plan-details/p/``; step 1 "build it" →
    # canonical file ``01-build.md`` (``derive_detail_path``).
    CANONICAL_REL = "plan-details/p/01-build.md"

    def _plan_with_canonical_detail(
        self,
        tmp_path: Path,
        detail_body: str,
        *,
        status: str = "current",
        pointer: Optional[str] = None,
    ) -> tuple[Path, "Plan"]:
        """A plan whose step 1 carries the canonical detail file on disk.

        ``pointer`` sets an explicit ``detail:`` (used to pin that a set
        pointer never falls back to the canonical file); omitted, the
        pointer is unset — the state this visibility rule addresses.
        """
        pointer_line = f"    detail: {pointer}\n" if pointer else ""
        plan_path = tmp_path / "2-p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: build it\n"
            "    files: [foo.py]\n"
            f"{pointer_line}"
            f"    status: {status}\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
        bundle = tmp_path / "plan-details" / "p"
        bundle.mkdir(parents=True)
        (bundle / "01-build.md").write_text(detail_body, encoding="utf-8")
        return plan_path, parse_plan(plan_path)

    def test_detail_body_completeness_reads_canonical_when_pointer_unset(
        self, tmp_path: Path
    ) -> None:
        # Pointer never persisted, canonical file on disk: the body is judged
        # and the finding names the canonical path (never ``None``).
        body = (
            "# Step 1\n\n"
            "## Summary\n\noverview\n\n"
            "## Table of Contents\n\n- [Why](#why) — motivation\n\n"
            "## Why\n\nx\n\n"
            "## Files\n\nfoo.py\n\n"
            "## Implementation\n\nx\n\n"
            "## Acceptance criteria\n\nx\n"
        )
        plan_path, plan = self._plan_with_canonical_detail(tmp_path, body)
        issues = check_detail_body_completeness(
            plan, tmp_path, plan_path=plan_path
        )
        missing = [i for i in issues if i.section == "Tests"]
        assert len(missing) == 1
        assert missing[0].kind == "missing"
        assert missing[0].detail_path == self.CANONICAL_REL

    def test_detail_body_completeness_set_pointer_never_falls_back(
        self, tmp_path: Path
    ) -> None:
        # A set-but-missing pointer is authoritative: the defective canonical
        # file beside it is NOT read, so ``missing_on_disk`` keeps its meaning.
        body = "# Step 1\n\n## Summary\n\nonly a summary\n"
        plan_path, plan = self._plan_with_canonical_detail(
            tmp_path, body, pointer="details/gone.md"
        )
        assert (
            check_detail_body_completeness(plan, tmp_path, plan_path=plan_path)
            == []
        )
        coverage = check_detail_coverage(plan, plan_path, tmp_path)
        assert [i.kind for i in coverage] == ["missing_on_disk"]
        assert coverage[0].detail_path == "details/gone.md"

    def test_detail_body_completeness_plan_path_none_keeps_pointer_only(
        self, tmp_path: Path
    ) -> None:
        # No ``plan_path`` → no canonical path to derive, so the canonical-only
        # step stays skipped (the compatibility default `bench.py`-style
        # callers rely on).
        body = "# Step 1\n\n## Summary\n\nonly a summary\n"
        _, plan = self._plan_with_canonical_detail(tmp_path, body)
        assert check_detail_body_completeness(plan, tmp_path) == []

    def test_done_step_canonical_detail_still_skipped(
        self, tmp_path: Path
    ) -> None:
        # The three checks that already filter ``done`` keep doing so: their
        # findings are pre-execution authoring signals. The other two changed
        # checks never filtered ``done`` — see
        # ``test_done_step_canonical_body_still_scanned_for_suppression``.
        body = (
            "# Step 1\n\n"
            "## Summary\n\nonly a summary\n\n"
            "## Input\n\nConsumes `pkg/absent.py:Thing`.\n\n"
            "## Implementation\n\nEdit `apps/foo.py`.\n"
        )
        plan_path, plan = self._plan_with_canonical_detail(
            tmp_path, body, status="done"
        )
        assert (
            check_detail_body_completeness(plan, tmp_path, plan_path=plan_path)
            == []
        )
        assert check_files_coherence(plan, tmp_path, plan_path=plan_path) == []
        assert check_input_contract_references(plan, plan_path, tmp_path) == []

    def test_done_step_canonical_body_still_scanned_for_suppression(
        self, tmp_path: Path
    ) -> None:
        # ``detect_suppression_shape`` has never filtered ``done`` — it scans
        # every step, pointed body included — so canonical visibility applies
        # there uniformly rather than inventing a ``done`` carve-out the check
        # doesn't otherwise make. Pins both sides of that widening.
        body = (
            "# Step 1\n\n"
            "## Summary\n\nSuppress the files-coherence check for these paths.\n\n"
            "## Why\n\nIt is noisy.\n\n"
            "## Implementation\n\nEdit `foo.py`.\n"
        )
        plan_path, plan = self._plan_with_canonical_detail(
            tmp_path, body, status="done"
        )
        assert detect_suppression_shape(plan, tmp_path, plan_name="p") == []
        recs = detect_suppression_shape(
            plan, tmp_path, plan_name="p", plan_path=plan_path
        )
        assert len(recs) == 1

    def test_input_contract_references_labels_canonical_path(
        self, tmp_path: Path
    ) -> None:
        # An ``## Input`` anchor in a canonical-only body is validated, and the
        # issue is located by the canonical path rather than a ``None`` label.
        body = (
            "# Step 1\n\n"
            "## Input\n\nConsumes `pkg/absent_module.py:Thing`.\n\n"
            "## Implementation\n\nDo it.\n"
        )
        plan_path, plan = self._plan_with_canonical_detail(tmp_path, body)
        issues = check_input_contract_references(plan, plan_path, tmp_path)
        assert len(issues) == 1
        assert issues[0].step_id == 1
        assert issues[0].location == f"{self.CANONICAL_REL}:## Input"
        assert issues[0].path == self.CANONICAL_REL

    def test_quality_visibility_matches_bundle_status(
        self, tmp_path: Path
    ) -> None:
        # The steps the quality checks read must equal the set
        # ``audit_detail_bundle_status`` calls detailed — canonical fallback
        # included, bare steps excluded from both.
        from plan_tool.review import audit_detail_bundle_status

        body = "# Step 1\n\n## Summary\n\nonly a summary\n"
        plan_path = tmp_path / "2-p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: build it\n"
            "    files: [foo.py]\n"
            "    status: current\n"
            "  - id: 2\n"
            "    title: ship it\n"
            "    files: [bar.py]\n"
            "    status: pending\n"
            "---\n",
            encoding="utf-8",
        )
        for fn in ("foo.py", "bar.py"):
            (tmp_path / fn).write_text("x\n", encoding="utf-8")
        bundle = tmp_path / "plan-details" / "p"
        bundle.mkdir(parents=True)
        (bundle / "01-build.md").write_text(body, encoding="utf-8")
        plan = parse_plan(plan_path)

        status = audit_detail_bundle_status(plan, plan_path, tmp_path)
        assert status.detailed_step_ids == (1,)
        assert status.bare_step_ids == (2,)
        issues = check_detail_body_completeness(
            plan, tmp_path, plan_path=plan_path
        )
        assert {i.step_id for i in issues} == {1}


class TestNearestDeclaredMatch:
    """Unit coverage for the near-miss predicate behind files-coherence."""

    def test_same_basename_different_dir_matches(self) -> None:
        from plan_tool.review import _nearest_declared_match

        assert (
            _nearest_declared_match(
                "apps/web/src/Foo.tsx", ["packages/web/Foo.tsx"]
            )
            == "packages/web/Foo.tsx"
        )

    def test_basename_typo_matches_via_ratio(self) -> None:
        from plan_tool.review import _nearest_declared_match

        # `Fooo.tsx` vs `Foo.tsx` — different basename, but the full path
        # is nearly identical, so the similarity ratio catches it.
        assert (
            _nearest_declared_match(
                "apps/web/Fooo.tsx", ["apps/web/Foo.tsx"]
            )
            == "apps/web/Foo.tsx"
        )

    def test_short_basename_single_char_typo_still_matches(self) -> None:
        from plan_tool.review import _nearest_declared_match

        # A one-character typo on a short basename has a *low ratio*
        # (0.75) purely from string length, even though it's a clearer
        # typo than the long, merely-similar-vocabulary pairs the basename
        # gap check must reject. The absolute character-gap check (not a
        # ratio) must still catch it. See BUG_BACKLOG.
        assert (
            _nearest_declared_match("handlers/b.py", ["handlers/a.py"])
            == "handlers/a.py"
        )

    def test_renamed_file_with_suffix_added_still_matches(self) -> None:
        from plan_tool.review import _nearest_declared_match

        # A realistic rename (a suffix added, gap 4) must still be caught —
        # this is the case a too-tight gap threshold (3) regressed.
        assert (
            _nearest_declared_match(
                "plan_tool/review_persistence.py",
                ["plan_tool/review_persistence_old.py"],
            )
            == "plan_tool/review_persistence_old.py"
        )

    def test_distinct_sibling_does_not_match(self) -> None:
        from plan_tool.review import _nearest_declared_match

        assert _nearest_declared_match("apps/bar.py", ["apps/foo.py"]) is None

    def test_unrelated_context_path_does_not_match(self) -> None:
        from plan_tool.review import _nearest_declared_match

        assert (
            _nearest_declared_match(
                "amplify/backend.ts", ["docs/secrets-and-parameters.md"]
            )
            is None
        )

    def test_generic_basename_does_not_match(self) -> None:
        from plan_tool.review import _nearest_declared_match

        assert (
            _nearest_declared_match(
                "apps/bar/index.ts", ["apps/foo/index.ts"]
            )
            is None
        )

    def test_distinct_sibling_with_deep_shared_directory_does_not_match(
        self,
    ) -> None:
        from plan_tool.review import _nearest_declared_match

        # A long shared directory prefix alone pushed the full-path ratio
        # to 0.9 between these two permanently-distinct, real files even
        # though their basenames ("sync" vs "client") share almost nothing
        # (basename ratio 0.5) — a false near-miss. See BUG_BACKLOG.
        assert (
            _nearest_declared_match(
                "backend-py/app/integrations/qbo/sync.py",
                ["backend-py/app/integrations/qbo/client.py"],
            )
            is None
        )

    def test_distinct_test_files_with_overlapping_words_do_not_match(
        self,
    ) -> None:
        from plan_tool.review import _nearest_declared_match

        # Full-path ratio 0.886 (shared "backend-py/tests/" directory plus
        # overlapping "test_"/"signup"/"sso" words) used to clear
        # threshold; basename ratio alone is 0.8 — below it. See
        # BUG_BACKLOG.
        assert (
            _nearest_declared_match(
                "backend-py/tests/test_sso_signup_flow.py",
                ["backend-py/tests/test_qbo_signup_sso.py"],
            )
            is None
        )

    def test_prefers_strongest_candidate(self) -> None:
        from plan_tool.review import _nearest_declared_match

        # A same-basename candidate must win over a merely-similar one.
        match = _nearest_declared_match(
            "apps/web/src/Foo.tsx",
            ["apps/web/src/Foob.tsx", "packages/web/Foo.tsx"],
        )
        assert match == "packages/web/Foo.tsx"


class TestFilesCoherenceRootLevelFilenames:
    """A repo-root file can only be cited bare, which the path-shaped mention
    regex can't see — it used to land in ``unmentioned`` however often the body
    named it, so every docs/status step drew false NITs. See BUG_BACKLOG."""

    def _fixture(self, tmp_path: Path, body: str, *, files: str) -> Path:
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: x\n"
            f"    files: [{files}]\n"
            "    detail: details/01.md\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "apps").mkdir(exist_ok=True)
        (tmp_path / "apps" / "foo.py").write_text("x\n", encoding="utf-8")
        (tmp_path / "BACKLOG.md").write_text("x\n", encoding="utf-8")
        (tmp_path / "DETAIL_FORMAT.md").write_text("x\n", encoding="utf-8")
        details_dir = tmp_path / "details"
        details_dir.mkdir(exist_ok=True)
        (details_dir / "01.md").write_text(body, encoding="utf-8")
        return plan_path

    def test_bare_root_filename_counts_as_mentioned(self, tmp_path: Path) -> None:
        # The mixed-state trigger: one path-shaped file plus one root-level
        # file, both cited. Previously emitted a NIT for `BACKLOG.md`.
        body = (
            "# Step 1\n\n## Implementation\n\n"
            "Edit `apps/foo.py`, then remove the entry from `BACKLOG.md`.\n"
        )
        plan_path = self._fixture(tmp_path, body, files="apps/foo.py, BACKLOG.md")
        issues = check_files_coherence(parse_plan(plan_path), tmp_path)
        assert issues == []

    def test_undiscussed_root_filename_still_nits(self, tmp_path: Path) -> None:
        body = "# Step 1\n\n## Implementation\n\nEdit `apps/foo.py` only.\n"
        plan_path = self._fixture(tmp_path, body, files="apps/foo.py, BACKLOG.md")
        issues = check_files_coherence(parse_plan(plan_path), tmp_path)
        assert [(i.kind, i.path) for i in issues] == [("files_only", "BACKLOG.md")]

    def test_relative_example_path_is_not_stale_drift(self, tmp_path: Path) -> None:
        # `../DETAIL_FORMAT.md` illustrates link depth; it names the declared
        # file, not a stale sibling copy of it.
        body = (
            "# Step 1\n\n## Implementation\n\n"
            "Edit `apps/foo.py`. From a subdirectory the link reads "
            "`../DETAIL_FORMAT.md`, which is `DETAIL_FORMAT.md`.\n"
        )
        plan_path = self._fixture(
            tmp_path, body, files="apps/foo.py, DETAIL_FORMAT.md"
        )
        issues = check_files_coherence(parse_plan(plan_path), tmp_path)
        assert issues == []

    def test_bare_mention_does_not_invent_near_miss_drift(
        self, tmp_path: Path
    ) -> None:
        # Bare tokens feed the declared-mention direction only. A body citing
        # `foo.py` while the step declares `apps/foo.py` must not produce a
        # same-basename "did you mean apps/foo.py" finding.
        body = (
            "# Step 1\n\n## Implementation\n\n"
            "Edit `apps/foo.py`; the module is just `foo.py` in prose.\n"
        )
        plan_path = self._fixture(tmp_path, body, files="apps/foo.py")
        issues = check_files_coherence(parse_plan(plan_path), tmp_path)
        assert issues == []


class TestCheckFilesCoherence:
    def test_files_coherence_reads_canonical_when_pointer_unset(
        self, tmp_path: Path
    ) -> None:
        # Pointer never persisted, canonical file on disk: the near-miss path
        # cited only in that body still surfaces as drift.
        body = (
            "# Step 1\n\n"
            "## Implementation\n\nEdit `packages/web/Foo.tsx`.\n"
        )
        plan_path = tmp_path / "2-p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: build it\n"
            "    files: [apps/web/src/Foo.tsx]\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "apps" / "web" / "src").mkdir(parents=True)
        (tmp_path / "apps" / "web" / "src" / "Foo.tsx").write_text(
            "x\n", encoding="utf-8"
        )
        bundle = tmp_path / "plan-details" / "p"
        bundle.mkdir(parents=True)
        (bundle / "01-build.md").write_text(body, encoding="utf-8")
        plan = parse_plan(plan_path)

        # Without a plan path there is no canonical path to derive → skipped.
        assert check_files_coherence(plan, tmp_path) == []

        issues = check_files_coherence(plan, tmp_path, plan_path=plan_path)
        drift = [i for i in issues if i.kind == "detail_only"]
        assert len(drift) == 1
        assert drift[0].path == "packages/web/Foo.tsx"
        assert drift[0].near_match == "apps/web/src/Foo.tsx"

    def test_files_coherence_refuses_an_unsupported_detail_marker(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.detail_artifacts import (
            DetailFormatError,
            render_detail_format_version_marker,
        )

        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: build it\n"
            "    files: [apps/foo.py]\n"
            "    detail: detail.md\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "detail.md").write_text(
            f"# Step 1\n{render_detail_format_version_marker(999)}\n\n"
            "## Implementation\n\nEdit `apps/foo.py`.\n",
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)
        with pytest.raises(DetailFormatError):
            check_files_coherence(plan, tmp_path)

    def test_full_match_no_issues(self, tmp_path: Path) -> None:
        body = (
            "# Step 1\n\n"
            "## Implementation\n\nEdit `apps/foo.py` to add bar.\n"
        )
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: x\n"
            "    files: [apps/foo.py]\n"
            "    detail: details/01.md\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "apps").mkdir()
        (tmp_path / "apps" / "foo.py").write_text("x\n", encoding="utf-8")
        details_dir = tmp_path / "details"
        details_dir.mkdir()
        (details_dir / "01.md").write_text(body, encoding="utf-8")
        plan = parse_plan(plan_path)
        assert check_files_coherence(plan, tmp_path) == []

    def test_detail_only_near_miss_flagged(self, tmp_path: Path) -> None:
        # Same basename in a different directory — likely a moved/typo'd
        # path the author forgot to re-sync. This IS drift; flag it.
        body = (
            "# Step 1\n\n"
            "## Implementation\n\nEdit `packages/web/Foo.tsx`.\n"
        )
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: x\n"
            "    files: [apps/web/src/Foo.tsx]\n"
            "    detail: details/01.md\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "apps" / "web" / "src").mkdir(parents=True)
        (tmp_path / "apps" / "web" / "src" / "Foo.tsx").write_text(
            "x\n", encoding="utf-8"
        )
        details_dir = tmp_path / "details"
        details_dir.mkdir()
        (details_dir / "01.md").write_text(body, encoding="utf-8")
        plan = parse_plan(plan_path)
        issues = check_files_coherence(plan, tmp_path)
        drift = [i for i in issues if i.kind == "detail_only"]
        assert len(drift) == 1
        assert drift[0].path == "packages/web/Foo.tsx"
        assert drift[0].near_match == "apps/web/src/Foo.tsx"

    def test_context_reference_not_flagged(self, tmp_path: Path) -> None:
        # A cited path bearing no resemblance to the declared file is a
        # context reference (a file the step reads, not edits). It must
        # NOT produce a finding — this is the noise the check used to emit.
        body = (
            "# Step 1\n\n"
            "## Implementation\n\nEdit `docs/secrets-and-parameters.md`. "
            "For context, this consumes `amplify/backend.ts` and the "
            "values produced by `infra/parameters.ts`.\n"
        )
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: x\n"
            "    files: [docs/secrets-and-parameters.md]\n"
            "    detail: details/01.md\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "secrets-and-parameters.md").write_text(
            "x\n", encoding="utf-8"
        )
        details_dir = tmp_path / "details"
        details_dir.mkdir()
        (details_dir / "01.md").write_text(body, encoding="utf-8")
        plan = parse_plan(plan_path)
        issues = check_files_coherence(plan, tmp_path)
        assert not any(i.kind == "detail_only" for i in issues)

    def test_generic_basename_not_flagged(self, tmp_path: Path) -> None:
        # Two unrelated `index.ts` files share a ubiquitous basename, so
        # the shared name carries no drift signal — don't flag it.
        body = (
            "# Step 1\n\n"
            "## Implementation\n\nEdit `apps/foo/index.ts`. It re-exports "
            "from `apps/bar/index.ts`.\n"
        )
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: x\n"
            "    files: [apps/foo/index.ts]\n"
            "    detail: details/01.md\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "apps" / "foo").mkdir(parents=True)
        (tmp_path / "apps" / "foo" / "index.ts").write_text(
            "x\n", encoding="utf-8"
        )
        details_dir = tmp_path / "details"
        details_dir.mkdir()
        (details_dir / "01.md").write_text(body, encoding="utf-8")
        plan = parse_plan(plan_path)
        issues = check_files_coherence(plan, tmp_path)
        assert not any(i.kind == "detail_only" for i in issues)

    def test_distinct_sibling_not_flagged(self, tmp_path: Path) -> None:
        # `apps/bar.py` shares only the directory and extension with the
        # declared `apps/foo.py` — a genuinely distinct sibling, not a
        # mistyped path. Below the similarity threshold, so not flagged.
        body = (
            "# Step 1\n\n"
            "## Implementation\n\nEdit `apps/foo.py`; reads `apps/bar.py`.\n"
        )
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: x\n"
            "    files: [apps/foo.py]\n"
            "    detail: details/01.md\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "apps").mkdir()
        (tmp_path / "apps" / "foo.py").write_text("x\n", encoding="utf-8")
        details_dir = tmp_path / "details"
        details_dir.mkdir()
        (details_dir / "01.md").write_text(body, encoding="utf-8")
        plan = parse_plan(plan_path)
        issues = check_files_coherence(plan, tmp_path)
        assert not any(i.kind == "detail_only" for i in issues)

    def test_no_declared_paths_cited_emits_single_nit(
        self, tmp_path: Path
    ) -> None:
        body = "# Step 1\n\n## Implementation\n\nNo paths cited at all.\n"
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: x\n"
            "    files: [apps/foo.py]\n"
            "    detail: details/01.md\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "apps").mkdir()
        (tmp_path / "apps" / "foo.py").write_text("x\n", encoding="utf-8")
        details_dir = tmp_path / "details"
        details_dir.mkdir()
        (details_dir / "01.md").write_text(body, encoding="utf-8")
        plan = parse_plan(plan_path)
        issues = check_files_coherence(plan, tmp_path)
        # Single nit covering all unmentioned files together.
        assert len(issues) == 1
        assert issues[0].kind == "files_only"

    def test_allowed_mentions_endorses_cited_path(
        self, tmp_path: Path
    ) -> None:
        # `apps/sub/foo.py` would otherwise be flagged as a near-miss of
        # the declared `apps/foo.py`; allowed_mentions must silence it.
        body = (
            "# Step 1\n\n"
            "## Implementation\n\nEdit `apps/foo.py` and `apps/sub/foo.py`.\n"
        )
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: x\n"
            "    files: [apps/foo.py]\n"
            "    allowed_mentions: [apps/sub/foo.py]\n"
            "    detail: details/01.md\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "apps").mkdir()
        (tmp_path / "apps" / "foo.py").write_text("x\n", encoding="utf-8")
        details_dir = tmp_path / "details"
        details_dir.mkdir()
        (details_dir / "01.md").write_text(body, encoding="utf-8")
        plan = parse_plan(plan_path)
        issues = check_files_coherence(plan, tmp_path)
        # The endorsed mention must not produce a detail_only finding…
        assert not any(
            i.kind == "detail_only" and i.path == "apps/sub/foo.py"
            for i in issues
        )
        # …and the allowed-mentions union must not leak into the files_only
        # branch (which still reads from `declared`, not `recognized`).
        assert not any(i.kind == "files_only" for i in issues)

    def test_done_step_skipped(self, tmp_path: Path) -> None:
        # The near-miss drift flagged by test_detail_only_near_miss_flagged
        # is suppressed once the step is done — coherence is a
        # pre-execution authoring signal, moot after implementation.
        body = (
            "# Step 1\n\n"
            "## Implementation\n\nEdit `packages/web/Foo.tsx`.\n"
        )
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: x\n"
            "    files: [apps/web/src/Foo.tsx]\n"
            "    detail: details/01.md\n"
            "    status: done\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "apps" / "web" / "src").mkdir(parents=True)
        (tmp_path / "apps" / "web" / "src" / "Foo.tsx").write_text(
            "x\n", encoding="utf-8"
        )
        details_dir = tmp_path / "details"
        details_dir.mkdir()
        (details_dir / "01.md").write_text(body, encoding="utf-8")
        plan = parse_plan(plan_path)
        assert check_files_coherence(plan, tmp_path) == []


class TestCheckLessonsCoverage:
    def test_no_lessons_no_issues(self, tmp_path: Path) -> None:
        plan_path = _write_completeness_plan(tmp_path)
        plan = parse_plan(plan_path)
        assert check_lessons_coverage(plan, tmp_path) == []

    def test_done_step_with_matching_entry(self, tmp_path: Path) -> None:
        lessons_dir = tmp_path / "lessons"
        lessons_dir.mkdir()
        lessons_path = lessons_dir / "log.md"
        lessons_path.write_text(
            "- 2026-05-05T00:00:00Z step 1: done thing — landed\n",
            encoding="utf-8",
        )
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: medium\n"
            "lessons: lessons/log.md\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: x\n"
            "    files: [foo.py]\n"
            "    status: done\n"
            "  - id: 2\n"
            "    title: y\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
        plan = parse_plan(plan_path)
        assert check_lessons_coverage(plan, tmp_path) == []

    def test_done_step_without_entry_flagged(self, tmp_path: Path) -> None:
        lessons_dir = tmp_path / "lessons"
        lessons_dir.mkdir()
        lessons_path = lessons_dir / "log.md"
        lessons_path.write_text(
            "- 2026-05-05T00:00:00Z step 1: only step 1 logged\n",
            encoding="utf-8",
        )
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: medium\n"
            "lessons: lessons/log.md\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: x\n"
            "    files: [foo.py]\n"
            "    status: done\n"
            "  - id: 2\n"
            "    title: y\n"
            "    files: [bar.py]\n"
            "    status: done\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
        (tmp_path / "bar.py").write_text("x\n", encoding="utf-8")
        plan = parse_plan(plan_path)
        issues = check_lessons_coverage(plan, tmp_path)
        assert len(issues) == 1
        assert issues[0].kind == "missing_entry"
        assert issues[0].step_id == 2

    def test_missing_lessons_file_with_done_steps(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: medium\n"
            "lessons: lessons/log.md\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: x\n"
            "    files: [foo.py]\n"
            "    status: done\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
        plan = parse_plan(plan_path)
        issues = check_lessons_coverage(plan, tmp_path)
        assert len(issues) == 1
        assert issues[0].kind == "missing_file"


class TestCorrectnessBeforeCompletenessOrdering:
    """Verify recommendations list correctness items before completeness items."""

    def test_path_style_precedes_body_completeness(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import review_plan_full

        # Plan with: a wrong-repo-root path (path-style finding) AND no
        # body sections (body-completeness findings). Path-style is
        # critical-severity correctness; body-completeness is medium.
        plan_path = tmp_path / "plan.md"
        plan_path.write_text(
            "---\n"
            "title: Mixed Plan\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: t\n"
            "    files:\n"
            "      - some/missing/dir/x.py\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        result = review_plan_full(
            plan_path,
            repo_root=tmp_path,
            plan_name="x",
            invoker=None,
        )
        sources = [r.source for r in result.recommendations]
        # path-style is correctness; body-completeness is completeness.
        assert "path-style" in sources
        assert "body-completeness" in sources
        # Order: every path-style index must precede every body-
        # completeness index.
        path_idx = sources.index("path-style")
        body_idx = sources.index("body-completeness")
        assert path_idx < body_idx


# --- completeness CLI subcommand (Step 7) ---------------------------------


class TestCmdCompleteness:
    @pytest.fixture(autouse=True)
    def _stub_plan_audit_invoker(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Keep these deterministic-focused tests hermetic. The
        conceptual audit shells out to claude on every ``completeness``
        run now, so default the invoker to an empty result; tests that
        exercise the audit override it in-body. The deterministic phase
        also runs a per-step MIXED-STEP purity pass that shells out to
        claude for any detailed code step, so stub that seam too (return
        no findings); tests exercising it override in-body."""
        from plan_tool import detail as detail_module
        from plan_tool import review as review_module

        monkeypatch.setattr(
            review_module,
            "shell_review_invoker",
            lambda _p: (
                0,
                "## Correctness findings\n\n_(none)_\n\n"
                "## Completeness findings\n\n_(none)_\n",
            ),
        )
        monkeypatch.setattr(
            detail_module,
            "collect_detail_quality_findings",
            lambda *a, **k: [],
        )

    def _setup_repo(self, tmp_path: Path, plan_text: str) -> Path:
        plan_path = tmp_path / "plan.md"
        plan_path.write_text(plan_text, encoding="utf-8")
        manifest = tmp_path / "m.json"
        manifest.write_text('{"plans": ["plan.md"]}\n', encoding="utf-8")
        (tmp_path / ".git").mkdir()
        return manifest

    def test_clean_plan_exits_zero(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        # Intents included: without them the plan is clean against every gate
        # but still carries the two ``intent-presence`` advisories, and this
        # case is about the nothing-found rendering.
        plan_text = (
            "---\n"
            "title: Clean Plan\n"
            "intent: prove a clean plan reports nothing\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: do\n"
            "    intent: do the one thing this plan needs\n"
            "    complexity: low\n"
            "    status: current\n"
            "---\n"
            "\n" + _FULL_BODY_SECTIONS
        )
        manifest = self._setup_repo(tmp_path, plan_text)
        monkeypatch.chdir(tmp_path)
        rc = cli_module.main(
            ["--manifest", str(manifest), "completeness-audit", "plan"]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "no completeness issues" in out

    def test_correctness_renders_before_completeness(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        plan_text = (
            "---\n"
            "title: Mixed\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: t\n"
            "    files:\n"
            "      - some/missing/dir/x.py\n"
            "    status: current\n"
            "---\n"
        )
        manifest = self._setup_repo(tmp_path, plan_text)
        monkeypatch.chdir(tmp_path)
        rc = cli_module.main(
            ["--manifest", str(manifest), "completeness-audit", "plan"]
        )
        # path-style critical AND body-completeness mediums, but a
        # completed audit always exits 0 — findings live in the report.
        assert rc == 0
        out = capsys.readouterr().out
        # The Correctness header must appear before the Plan sections
        # header — the user's "correctness first" directive.
        corr_idx = out.find("Correctness")
        body_idx = out.find("Plan sections")
        assert corr_idx >= 0
        assert body_idx >= 0
        assert corr_idx < body_idx

    def test_fail_on_findings_exits_one_when_blocking(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--fail-on-findings restores the medium+ gate as a non-zero rc
        so a CI step can stop on it; the report is unchanged."""
        from plan_tool.cli import app as cli_module

        plan_text = (
            "---\n"
            "title: Mixed\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: t\n"
            "    files:\n"
            "      - some/missing/dir/x.py\n"
            "    status: current\n"
            "---\n"
        )
        manifest = self._setup_repo(tmp_path, plan_text)
        monkeypatch.chdir(tmp_path)
        rc = cli_module.main(
            [
                "--manifest", str(manifest), "completeness-audit", "plan",
                "--fail-on-findings",
            ]
        )
        assert rc == 1
        out = capsys.readouterr().out
        assert "Correctness" in out

    def test_fail_on_findings_clean_plan_exits_zero(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--fail-on-findings only flips the rc on *blocking* findings. A
        genuinely clean plan declares an `intent:` at both altitudes, so
        nothing reaches the blocking bucket and it exits 0."""
        from plan_tool.cli import app as cli_module

        plan_text = (
            "---\n"
            "title: Clean Plan\n"
            "intent: keep the clean-plan control genuinely clean\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: do\n"
            "    intent: why the only step exists\n"
            "    complexity: low\n"
            "    status: current\n"
            "---\n"
            "\n" + _FULL_BODY_SECTIONS
        )
        manifest = self._setup_repo(tmp_path, plan_text)
        monkeypatch.chdir(tmp_path)
        rc = cli_module.main(
            [
                "--manifest", str(manifest), "completeness-audit", "plan",
                "--fail-on-findings",
            ]
        )
        assert rc == 0

    def test_missing_intent_exits_zero_but_gates_fail_on_findings(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The promotion's end-to-end shape: a plan declaring no `intent` is
        blocking, yet a *completed* audit still exits 0 — only
        --fail-on-findings turns that into a non-zero rc."""
        from plan_tool.cli import app as cli_module

        plan_text = (
            "---\n"
            "title: No Intent Plan\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: do\n"
            "    complexity: low\n"
            "    status: current\n"
            "---\n"
            "\n" + _FULL_BODY_SECTIONS
        )
        manifest = self._setup_repo(tmp_path, plan_text)
        monkeypatch.chdir(tmp_path)
        assert cli_module.main(
            ["--manifest", str(manifest), "completeness-audit", "plan"]
        ) == 0
        capsys.readouterr()
        assert cli_module.main(
            [
                "--manifest", str(manifest), "completeness-audit", "plan",
                "--fail-on-findings",
            ]
        ) == 1

    def test_plan_sections_framing_disambiguates_from_jira(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Body-section findings must be framed as *plan document
        sections*, not Jira story acceptance criteria. Pins the
        disambiguation wording so the terminology collision can't
        silently regress: the group header, the explanatory intro, and
        the per-line ``plan section`` prefix."""
        from plan_tool.cli import app as cli_module

        # A placeholder ``## Acceptance criteria`` section trips the
        # body-completeness check, so the finding renders under the
        # plan-sections group — exactly the line a user could otherwise
        # mistake for a Jira acceptance-criteria message.
        plan_text = (
            "---\n"
            "title: Framing\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: t\n"
            "    complexity: low\n"
            "    status: current\n"
            "---\n"
            "\n"
            "## Acceptance criteria\n\n_(TODO)_\n"
        )
        manifest = self._setup_repo(tmp_path, plan_text)
        monkeypatch.chdir(tmp_path)
        rc = cli_module.main(
            ["--manifest", str(manifest), "completeness-audit", "plan"]
        )
        # Completed audit exits 0 even with placeholder-section findings.
        assert rc == 0
        out = capsys.readouterr().out
        # New header + the old ambiguous one is gone.
        assert "Plan sections" in out
        assert "Body sections" not in out
        # The intro explicitly distinguishes from Jira.
        assert "not a Jira story's acceptance criteria" in out
        # Each finding line names the source as a plan section.
        # Console rendering strips the inline-code backticks.
        assert "plan section ## Acceptance criteria" in out

    def test_json_output_shape(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module
        import json as _json

        plan_text = (
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: t\n"
            "    files: [foo.py]\n"
            "    status: current\n"
            "---\n"
        )
        manifest = self._setup_repo(tmp_path, plan_text)
        (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        rc = cli_module.main(
            ["--manifest", str(manifest), "completeness-audit", "plan", "--json"]
        )
        out = capsys.readouterr().out
        payload = _json.loads(out)
        assert payload["plan"] == "plan"
        assert "checks" in payload
        # The process exits 0 on a completed audit; the JSON carries the
        # blocking-findings signal instead.
        assert rc == 0
        assert "has_blocking_findings" in payload
        assert isinstance(payload["has_blocking_findings"], bool)
        assert payload["coverage"] == {
            "evidence_status": "observed",
            "budget_limited": False,
            "passes_used": 1,
            "cap": 3,
            "recommendation_kind": None,
            "recommended_passes": None,
            "recommendation_advice": None,
            "confirmation_kind": "confirmed-dry",
            "conforming_pass_count": 0,
            "failed_or_malformed_pass_count": 0,
        }
        assert "body_sections" in payload["checks"]
        assert "detail_coverage" in payload["checks"]
        assert "correctness" in payload["checks"]

    def test_json_output_keeps_budget_advice_compatibility_fields_null(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool import review as review_module
        from plan_tool.cli import app as cli_module
        import json as _json

        def fake_audit(
            plan,
            plan_path,
            *,
            repo_root,
            invoker,
            max_passes,
            dry_rounds,
            reporter=None,
            budget_report=None,
            **_kw,
        ):
            assert max_passes == 3
            assert dry_rounds == 2
            if budget_report is not None:
                budget_report.update(
                    {
                        "budget_limited": True,
                        "passes_used": 3,
                        "cap": 3,
                        # A stale producer value must not reopen the retired
                        # count-guidance channel in public JSON.
                        "recommendation_kind": "ignored",
                        "recommended_passes": 5,
                        "recommendation_advice": "ignored",
                    }
                )
            return [
                Recommendation(
                    id="plan-plan-completeness-gap",
                    source="plan-completeness",
                    severity="medium",
                    step_id=None,
                    title="gap",
                    body="gap",
                    anchor="gap",
                )
            ]

        monkeypatch.setattr(review_module, "audit_plan_until_stable", fake_audit)
        plan_text = (
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: t\n"
            "    files: [foo.py]\n"
            "    status: current\n"
            "---\n"
            "\n" + _FULL_BODY_SECTIONS
        )
        manifest = self._setup_repo(tmp_path, plan_text)
        (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            [
                "--manifest",
                str(manifest),
                "completeness-audit",
                "plan",
                "--json",
                "--audit-passes",
                "3",
                "--audit-dry-rounds",
                "2",
            ]
        )

        payload = _json.loads(capsys.readouterr().out)
        assert rc == 0
        assert payload["coverage"] == {
            "evidence_status": "observed",
            "budget_limited": True,
            "passes_used": 3,
            "cap": 3,
            "recommendation_kind": None,
            "recommended_passes": None,
            "recommendation_advice": None,
            "confirmation_kind": None,
        }

    # A detail body that satisfies check_detail_body_completeness (all seven
    # required sections present and non-empty) so the only files_coherence
    # signal in the JSON/grouped output is the one the test is targeting.
    # Cites `apps/sub/foo.py` — a near-miss of the declared `apps/foo.py`
    # (same basename, different directory), the genuine drift signal.
    _DETAIL_BODY_DRIFT = (
        "# Step 1\n\n"
        "## Summary\n\noverview\n\n"
        "## Table of Contents\n\n- [Why](#why) — motivation\n\n"
        "## Why\n\nreason\n\n"
        "## Files\n\napps/foo.py\n\n"
        "## Implementation\n\nEdit `apps/foo.py` and `apps/sub/foo.py`.\n\n"
        "## Tests\n\nrun pytest\n\n"
        "## Acceptance criteria\n\n- done\n"
    )
    _DETAIL_BODY_NO_PATHS = (
        "# Step 1\n\n"
        "## Summary\n\noverview\n\n"
        "## Table of Contents\n\n- [Why](#why) — motivation\n\n"
        "## Why\n\nreason\n\n"
        "## Files\n\napps/foo.py\n\n"
        "## Implementation\n\nNo paths cited at all.\n\n"
        "## Tests\n\nrun pytest\n\n"
        "## Acceptance criteria\n\n- done\n"
    )

    def _setup_files_coherence_repo(
        self,
        tmp_path: Path,
        detail_body: str,
    ) -> Path:
        plan_text = (
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: t\n"
            "    files: [apps/foo.py]\n"
            "    detail: details/01.md\n"
            "    status: current\n"
            "---\n"
            "\n" + _FULL_BODY_SECTIONS
        )
        manifest = self._setup_repo(tmp_path, plan_text)
        (tmp_path / "apps").mkdir()
        (tmp_path / "apps" / "foo.py").write_text("x\n", encoding="utf-8")
        details_dir = tmp_path / "details"
        details_dir.mkdir()
        (details_dir / "01.md").write_text(detail_body, encoding="utf-8")
        return manifest

    def test_detail_only_severity_is_info_in_json(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module
        import json as _json

        manifest = self._setup_files_coherence_repo(
            tmp_path, self._DETAIL_BODY_DRIFT
        )
        monkeypatch.chdir(tmp_path)
        cli_module.main(
            ["--manifest", str(manifest), "completeness-audit", "plan", "--json"]
        )
        out = capsys.readouterr().out
        payload = _json.loads(out)
        entries = payload["checks"]["files_coherence"]
        assert len(entries) == 1
        entry = entries[0]
        assert entry["kind"] == "detail_only"
        assert entry["path"] == "apps/sub/foo.py"
        assert entry["near_match"] == "apps/foo.py"
        assert entry["severity"] == "info"

    def test_files_only_severity_unchanged_nit_in_json(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module
        import json as _json

        manifest = self._setup_files_coherence_repo(
            tmp_path, self._DETAIL_BODY_NO_PATHS
        )
        monkeypatch.chdir(tmp_path)
        cli_module.main(
            ["--manifest", str(manifest), "completeness-audit", "plan", "--json"]
        )
        out = capsys.readouterr().out
        payload = _json.loads(out)
        entries = payload["checks"]["files_coherence"]
        assert len(entries) == 1
        entry = entries[0]
        assert entry["kind"] == "files_only"
        assert entry["severity"] == "nit"

    def test_info_only_files_coherence_exits_zero(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = self._setup_files_coherence_repo(
            tmp_path, self._DETAIL_BODY_DRIFT
        )
        monkeypatch.chdir(tmp_path)
        rc = cli_module.main(
            ["--manifest", str(manifest), "completeness-audit", "plan"]
        )
        assert rc == 0
        out = capsys.readouterr().out
        # Belt-and-suspenders: the finding actually rendered — exit 0 isn't
        # the result of suppressing the issue entirely.
        assert "Files coherence" in out

    def test_detail_only_grouped_report_uses_info_prefix(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = self._setup_files_coherence_repo(
            tmp_path, self._DETAIL_BODY_DRIFT
        )
        monkeypatch.chdir(tmp_path)
        cli_module.main(
            ["--manifest", str(manifest), "completeness-audit", "plan"]
        )
        out = capsys.readouterr().out
        assert "Files coherence" in out
        assert "- INFO: step 1 detail cites" in out
        # The near-miss target is named so the finding is actionable.
        assert "resembling declared apps/foo.py" in out
        # detail_only is advisory (INFO), never a blocking WARN.
        assert "- WARN: step 1 detail cites" not in out


class TestStepSchemaAllowedMentions:
    def test_singular_allowed_mention_field_rejected(self) -> None:
        from plan_tool.parser import ValidationError, parse_plan_text

        text = (
            "---\n"
            "title: Typo\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: t\n"
            "    files: [foo.py]\n"
            "    allowed_mention: [bar.py]\n"
            "    status: current\n"
            "---\n"
        )
        with pytest.raises(ValidationError) as exc_info:
            parse_plan_text(text)
        assert "allowed_mention" in str(exc_info.value)

    def test_allowed_mentions_plural_list_accepted(self) -> None:
        from plan_tool.parser import parse_plan_text

        text = (
            "---\n"
            "title: OK\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: t\n"
            "    files: [foo.py]\n"
            "    allowed_mentions: [bar.py, baz/qux.py]\n"
            "    status: current\n"
            "---\n"
        )
        plan = parse_plan_text(text)
        assert plan.steps[0].allowed_mentions == ["bar.py", "baz/qux.py"]


# --- Criteria fulfillment (Fulfillment axis, claude-driven) --------------

class TestCheckCriteriaFulfillment:
    """Layered semantic check: does the DONE-step code fulfill the
    plan's ``## Acceptance criteria``? No-ops when there's nothing to
    check; otherwise renders a prompt and invokes claude."""

    _FINDINGS_OK = "\n## Findings\n\n_(none)_\n"
    _FINDINGS_ONE_HIGH = (
        "Some prose.\n\n## Findings\n\n"
        "- HIGH: acceptance #2 requires X, missing in `foo.py:bar()`\n"
    )

    def test_done_step_source_excerpt_contract_survives_cleanup(
        self, tmp_path: Path
    ) -> None:
        plan_path = tmp_path / "criteria-plan.md"
        plan_path.write_text(
            "---\n"
            "title: Criteria Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Prepare first owner\n"
            "    files:\n"
            "      - shared.py\n"
            "    status: done\n"
            "  - id: 2\n"
            "    title: Implement second_symbol\n"
            "    files:\n"
            "      - shared.py\n"
            "    status: done\n"
            "---\n"
            "\n"
            "## Acceptance criteria\n\n"
            "- second_symbol works.\n",
            encoding="utf-8",
        )
        (tmp_path / "shared.py").write_text(
            "\n".join(f"# filler {i}" for i in range(80))
            + "\n\n\ndef second_symbol():\n    return 2\n",
            encoding="utf-8",
        )
        captured: dict[str, str] = {}

        def fake_invoker(prompt: str):
            captured["prompt"] = prompt
            return (0, self._FINDINGS_OK)

        recs = check_criteria_fulfillment(
            parse_plan(plan_path),
            plan_path,
            repo_root=tmp_path,
            invoker=fake_invoker,
            max_file_bytes=160,
        )

        assert recs == []
        assert captured["prompt"].count("### `shared.py` (from step 1)") == 1
        assert "from step 2" not in captured["prompt"]
        assert "def second_symbol()" in captured["prompt"]
        assert "# filler 0" not in captured["prompt"]

    def _write_plan_with_done_step(
        self,
        tmp_path: Path,
        *,
        body: str,
        step_status: str = "done",
    ) -> Path:
        plan_path = tmp_path / "concept-plan.md"
        plan_path.write_text(
            "---\n"
            "title: Concept Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: build the thing\n"
            "    files:\n"
            "      - foo.py\n"
            f"    status: {step_status}\n"
            "---\n"
            "\n"
            f"{body}",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text(
            "def bar():\n    return 41\n", encoding="utf-8"
        )
        return plan_path

    def test_returns_empty_when_invoker_is_none(
        self, tmp_path: Path
    ) -> None:
        """Offline mode: no invoker → no claude call → empty findings."""
        from plan_tool.review import check_criteria_fulfillment
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan_with_done_step(
            tmp_path, body=_FULL_BODY_SECTIONS,
        )
        plan = parse_plan(plan_path)
        assert (
            check_criteria_fulfillment(
                plan, plan_path, repo_root=tmp_path, invoker=None,
            )
            == []
        )

    def test_returns_empty_when_no_acceptance_criteria(
        self, tmp_path: Path
    ) -> None:
        """No ``## Acceptance criteria`` section → check skips even
        when invoker is present. The plan author hasn't declared an
        intent to audit against."""
        from plan_tool.review import check_criteria_fulfillment
        from plan_tool.parser import parse_plan

        body = (
            "## Overview\n\nx\n\n"
            "## Problem statement\n\nx\n\n"
            "## Architecture\n\nx\n\n"
            "## Steps\n\nx\n"
            # No `## Acceptance criteria` section.
        )
        plan_path = self._write_plan_with_done_step(tmp_path, body=body)
        plan = parse_plan(plan_path)
        called = {"n": 0}

        def fake_invoker(prompt: str):
            called["n"] += 1
            return (0, self._FINDINGS_OK)

        recs = check_criteria_fulfillment(
            plan, plan_path, repo_root=tmp_path, invoker=fake_invoker,
        )
        assert recs == []
        assert called["n"] == 0

    def test_returns_empty_when_acceptance_is_placeholder(
        self, tmp_path: Path
    ) -> None:
        """``## Acceptance criteria`` body is just ``_(TODO)_`` → skip.
        Nothing actionable to audit against."""
        from plan_tool.review import check_criteria_fulfillment
        from plan_tool.parser import parse_plan

        body = (
            "## Overview\n\nx\n\n"
            "## Acceptance criteria\n\n_(TODO)_\n\n"
            "## Steps\n\nx\n"
        )
        plan_path = self._write_plan_with_done_step(tmp_path, body=body)
        plan = parse_plan(plan_path)
        called = {"n": 0}

        def fake_invoker(prompt: str):
            called["n"] += 1
            return (0, self._FINDINGS_OK)

        assert (
            check_criteria_fulfillment(
                plan, plan_path, repo_root=tmp_path,
                invoker=fake_invoker,
            )
            == []
        )
        assert called["n"] == 0

    def test_returns_empty_when_no_done_steps(
        self, tmp_path: Path
    ) -> None:
        """Plan has acceptance criteria but no DONE step declares files
        → nothing built to evaluate against → skip."""
        from plan_tool.review import check_criteria_fulfillment
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan_with_done_step(
            tmp_path, body=_FULL_BODY_SECTIONS,
            step_status="pending",
        )
        plan = parse_plan(plan_path)
        called = {"n": 0}

        def fake_invoker(prompt: str):
            called["n"] += 1
            return (0, self._FINDINGS_OK)

        assert (
            check_criteria_fulfillment(
                plan, plan_path, repo_root=tmp_path,
                invoker=fake_invoker,
            )
            == []
        )
        assert called["n"] == 0

    def test_returns_empty_when_invoker_returns_nonzero(
        self, tmp_path: Path
    ) -> None:
        """Claude exited non-zero (e.g. not on PATH) → swallow and
        return empty so callers don't crash on missing claude."""
        from plan_tool.review import check_criteria_fulfillment
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan_with_done_step(
            tmp_path, body=_FULL_BODY_SECTIONS,
        )
        plan = parse_plan(plan_path)
        assert (
            check_criteria_fulfillment(
                plan, plan_path, repo_root=tmp_path,
                invoker=lambda _p: (127, ""),
            )
            == []
        )

    def test_returns_empty_when_invoker_raises(
        self, tmp_path: Path
    ) -> None:
        """An invoker raising for any reason should not propagate; the
        check is best-effort and yields zero findings instead."""
        from plan_tool.review import check_criteria_fulfillment
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan_with_done_step(
            tmp_path, body=_FULL_BODY_SECTIONS,
        )
        plan = parse_plan(plan_path)

        def boom(_p):
            raise RuntimeError("claude crashed")

        assert (
            check_criteria_fulfillment(
                plan, plan_path, repo_root=tmp_path, invoker=boom,
            )
            == []
        )

    def test_parses_findings_with_concept_source(
        self, tmp_path: Path
    ) -> None:
        """Happy path: acceptance criteria present, DONE step with
        files, invoker returns a `## Findings` block → claude bullets
        come back as Recommendation objects with
        ``source="criteria-fulfillment"``."""
        from plan_tool.review import check_criteria_fulfillment
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan_with_done_step(
            tmp_path, body=_FULL_BODY_SECTIONS,
        )
        plan = parse_plan(plan_path)

        captured: dict[str, str] = {}

        def fake_invoker(prompt: str):
            captured["prompt"] = prompt
            return (0, self._FINDINGS_ONE_HIGH)

        recs = check_criteria_fulfillment(
            plan, plan_path, repo_root=tmp_path,
            invoker=fake_invoker,
        )
        assert len(recs) == 1
        assert recs[0].source == "criteria-fulfillment"
        assert recs[0].severity == "high"
        # The prompt should include the plan title, acceptance
        # criteria body, and the DONE-step file's contents so claude
        # has the inputs it needs.
        assert "Concept Plan" in captured["prompt"]
        assert "Real acceptance bullets." in captured["prompt"]
        assert "def bar()" in captured["prompt"]

    def test_criteria_fulfillment_done_files_use_symbol_excerpt(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import check_criteria_fulfillment
        from plan_tool.parser import parse_plan

        plan_path = tmp_path / "symbol-plan.md"
        plan_path.write_text(
            "---\n"
            "title: Symbol Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Add target_symbol helper\n"
            "    files:\n"
            "      - foo.py\n"
            "    status: done\n"
            "---\n"
            "\n"
            f"{_FULL_BODY_SECTIONS}",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text(
            "\n".join(f"# header {i}" for i in range(200))
            + "\n\n\ndef target_symbol():\n    return 1\n",
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)
        captured: dict[str, str] = {}

        def fake_invoker(prompt: str):
            captured["prompt"] = prompt
            return (0, self._FINDINGS_OK)

        check_criteria_fulfillment(
            plan,
            plan_path,
            repo_root=tmp_path,
            invoker=fake_invoker,
            max_file_bytes=200,
        )

        assert "def target_symbol()" in captured["prompt"]
        assert "# header 0" not in captured["prompt"]

    def test_criteria_fulfillment_keeps_done_file_headers_and_truncation_marker(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import check_criteria_fulfillment
        from plan_tool.parser import parse_plan

        plan_path = tmp_path / "symbol-plan.md"
        plan_path.write_text(
            "---\n"
            "title: Symbol Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Add target_symbol helper\n"
            "    files:\n"
            "      - foo.py\n"
            "    status: done\n"
            "---\n"
            "\n"
            f"{_FULL_BODY_SECTIONS}",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text(
            "\n".join(f"# header {i}" for i in range(200))
            + "\n\n\ndef target_symbol():\n    return 1\n"
            + "\n".join(f"# tail {i}" for i in range(200)),
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)
        captured: dict[str, str] = {}

        def fake_invoker(prompt: str):
            captured["prompt"] = prompt
            return (0, self._FINDINGS_OK)

        check_criteria_fulfillment(
            plan,
            plan_path,
            repo_root=tmp_path,
            invoker=fake_invoker,
            max_file_bytes=200,
        )

        assert "### `foo.py` (from step 1)" in captured["prompt"]
        assert "_(truncated)_" in captured["prompt"]

    def test_render_prompt_helper_returns_none_when_no_acceptance(
        self, tmp_path: Path
    ) -> None:
        """The prompt-render helper exposes the skip path directly for
        callers that want to short-circuit before constructing the
        invoker."""
        from plan_tool.review import render_criteria_fulfillment_prompt
        from plan_tool.parser import parse_plan

        body = "## Overview\n\nx\n\n## Steps\n\nx\n"
        plan_path = self._write_plan_with_done_step(tmp_path, body=body)
        plan = parse_plan(plan_path)
        assert (
            render_criteria_fulfillment_prompt(plan, plan_path, tmp_path)
            is None
        )

    def test_attribution_resolves_step_id_from_backticked_path(
        self, tmp_path: Path
    ) -> None:
        """A finding body citing `foo.py` in backticks is attributed to
        the DONE step whose step.files lists `foo.py` -- not left at
        step_id=None where apply_finding would fall back to a
        scope-mismatched step."""
        from plan_tool.review import check_criteria_fulfillment
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan_with_done_step(
            tmp_path, body=_FULL_BODY_SECTIONS,
        )
        plan = parse_plan(plan_path)

        # Finding bullet cites foo.py — should attribute to step 1.
        stdout = (
            "Some prose.\n\n## Findings\n\n"
            "- HIGH: acceptance #2 requires X but `foo.py:bar()` returns 41\n"
        )
        recs = check_criteria_fulfillment(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (0, stdout),
        )
        assert len(recs) == 1
        assert recs[0].step_id == 1

    def test_attribution_leaves_step_id_none_when_no_file_match(
        self, tmp_path: Path
    ) -> None:
        """No file path mentioned in the body → step_id remains None;
        apply_finding's default routing handles the fallback."""
        from plan_tool.review import check_criteria_fulfillment
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan_with_done_step(
            tmp_path, body=_FULL_BODY_SECTIONS,
        )
        plan = parse_plan(plan_path)

        stdout = (
            "Some prose.\n\n## Findings\n\n"
            "- MEDIUM: acceptance is vague and unfalsifiable\n"
        )
        recs = check_criteria_fulfillment(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (0, stdout),
        )
        assert len(recs) == 1
        assert recs[0].step_id is None

    def test_logs_skip_when_invoker_is_none(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Each skip path emits a one-line structured stderr note so
        CI operators can tell whether the check actually ran."""
        from plan_tool.review import check_criteria_fulfillment
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan_with_done_step(
            tmp_path, body=_FULL_BODY_SECTIONS,
        )
        plan = parse_plan(plan_path)
        check_criteria_fulfillment(
            plan, plan_path, repo_root=tmp_path, invoker=None,
        )
        err = capsys.readouterr().err
        assert "criteria-fulfillment: skipped" in err
        assert "no invoker configured" in err

    def test_logs_skip_when_no_acceptance_criteria(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.review import check_criteria_fulfillment
        from plan_tool.parser import parse_plan

        body = "## Overview\n\nx\n\n## Steps\n\nx\n"
        plan_path = self._write_plan_with_done_step(tmp_path, body=body)
        plan = parse_plan(plan_path)
        check_criteria_fulfillment(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (0, self._FINDINGS_OK),
        )
        err = capsys.readouterr().err
        assert "criteria-fulfillment: skipped" in err
        assert "Acceptance criteria" in err

    def test_logs_skip_when_no_done_steps(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.review import check_criteria_fulfillment
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan_with_done_step(
            tmp_path, body=_FULL_BODY_SECTIONS, step_status="pending",
        )
        plan = parse_plan(plan_path)
        check_criteria_fulfillment(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (0, self._FINDINGS_OK),
        )
        err = capsys.readouterr().err
        assert "criteria-fulfillment: skipped" in err
        assert "no DONE step declares files" in err

    def test_logs_skip_when_invoker_exits_nonzero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``exit_code != 0`` typically means claude isn't on PATH --
        the most important skip case for CI visibility."""
        from plan_tool.review import check_criteria_fulfillment
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan_with_done_step(
            tmp_path, body=_FULL_BODY_SECTIONS,
        )
        plan = parse_plan(plan_path)
        check_criteria_fulfillment(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (127, ""),
        )
        err = capsys.readouterr().err
        assert "criteria-fulfillment: skipped" in err
        assert "code 127" in err
        assert "PATH" in err

    def test_logs_skip_when_invoker_raises(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.review import check_criteria_fulfillment
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan_with_done_step(
            tmp_path, body=_FULL_BODY_SECTIONS,
        )
        plan = parse_plan(plan_path)

        def boom(_p):
            raise RuntimeError("claude crashed mid-call")

        check_criteria_fulfillment(
            plan, plan_path, repo_root=tmp_path, invoker=boom,
        )
        err = capsys.readouterr().err
        assert "criteria-fulfillment: skipped" in err
        assert "invoker raised" in err
        assert "claude crashed" in err

    def test_logs_findings_count_on_success(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A successful run emits a count line so operators can see
        the check ran AND distinguish clean vs noisy outcomes."""
        from plan_tool.review import check_criteria_fulfillment
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan_with_done_step(
            tmp_path, body=_FULL_BODY_SECTIONS,
        )
        plan = parse_plan(plan_path)
        check_criteria_fulfillment(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (0, self._FINDINGS_ONE_HIGH),
        )
        err = capsys.readouterr().err
        assert "criteria-fulfillment: 1 finding(s) raised" in err

    def test_logs_clean_when_no_findings(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.review import check_criteria_fulfillment
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan_with_done_step(
            tmp_path, body=_FULL_BODY_SECTIONS,
        )
        plan = parse_plan(plan_path)
        check_criteria_fulfillment(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (0, self._FINDINGS_OK),
        )
        err = capsys.readouterr().err
        assert "criteria-fulfillment: 0 findings" in err
        assert "appear met" in err

    def test_log_file_kwarg_overrides_stderr(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``log_file`` redirects the structured summary to an
        arbitrary writable sink so noise-sensitive callers (json
        output, scripted pipelines) can suppress the stderr line."""
        import io
        from plan_tool.review import check_criteria_fulfillment
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan_with_done_step(
            tmp_path, body=_FULL_BODY_SECTIONS,
        )
        plan = parse_plan(plan_path)
        sink = io.StringIO()
        check_criteria_fulfillment(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (0, self._FINDINGS_OK),
            log_file=sink,
        )
        assert "criteria-fulfillment" in sink.getvalue()
        assert capsys.readouterr().err == ""

    def test_attribution_leaves_step_id_none_on_ambiguous_match(
        self, tmp_path: Path
    ) -> None:
        """When the body mentions files owned by two different DONE
        steps, attribution is ambiguous — we leave step_id=None
        instead of guessing wrong (apply_finding's default routing is
        the conservative fallback)."""
        from plan_tool.review import check_criteria_fulfillment
        from plan_tool.parser import parse_plan

        plan_path = tmp_path / "ambiguous-plan.md"
        plan_path.write_text(
            "---\n"
            "title: Ambiguous Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: alpha\n"
            "    files:\n"
            "      - alpha.py\n"
            "    status: done\n"
            "  - id: 2\n"
            "    title: beta\n"
            "    files:\n"
            "      - beta.py\n"
            "    status: done\n"
            "---\n"
            "\n"
            f"{_FULL_BODY_SECTIONS}",
            encoding="utf-8",
        )
        (tmp_path / "alpha.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_path / "beta.py").write_text("y = 2\n", encoding="utf-8")
        plan = parse_plan(plan_path)

        stdout = (
            "## Findings\n\n"
            "- HIGH: criterion spans `alpha.py` and `beta.py`\n"
        )
        recs = check_criteria_fulfillment(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (0, stdout),
        )
        assert len(recs) == 1
        # Both steps matched → ambiguous → step_id stays None.
        assert recs[0].step_id is None


# --- Conceptual audit (Conceptual axis: bundle-grounded, claude-driven) ---

class TestSplitAuditKey:
    """The leading ``[anchor-slug]`` split. The slug is what makes a
    re-worded finding hash to a stable id across runs, so a wrapper the
    regex fails to tolerate costs the anchor *and* the stable id."""

    @pytest.mark.parametrize(
        "opened",
        [
            "[cache-invalidation]",
            "**[cache-invalidation]**",
            "`[cache-invalidation]`",
            "**`[cache-invalidation]`**",
            "`**[cache-invalidation]**`",
        ],
        ids=["bare", "bold", "code", "bold-code", "code-bold"],
    )
    def test_wrappers_are_stripped_from_both_sides(self, opened: str) -> None:
        """Every wrapper form yields the same slug and the same remaining
        body — no wrapper residue leaks into the rendered title."""
        from plan_tool.review import _split_audit_key

        slug, body = _split_audit_key(f"{opened} Risks names a hazard")
        assert slug == "cache-invalidation"
        assert body == "Risks names a hazard"

    def test_sluggless_body_is_returned_unchanged(self) -> None:
        from plan_tool.review import _split_audit_key

        assert _split_audit_key("Risks names a hazard") == (
            None, "Risks names a hazard"
        )

    def test_prose_bracket_is_not_mistaken_for_a_slug(self) -> None:
        """A bracketed phrase with spaces is prose, not a kebab slug."""
        from plan_tool.review import _split_audit_key

        assert _split_audit_key("[see step 2] a gap") == (
            None, "[see step 2] a gap"
        )

    def test_markdown_link_is_not_mistaken_for_a_slug(self) -> None:
        """``[text](url)`` is a link, not an anchor. Capturing it would
        mint a bogus anchor *and* collapse two unrelated findings that
        happen to link the same doc onto one recurrence region."""
        from plan_tool.review import _split_audit_key

        body = "[detail-format](docs/DETAIL_FORMAT.md) is stale"
        assert _split_audit_key(body) == (None, body)

    @pytest.mark.parametrize(
        "body, expected_rest",
        [
            ("[step-3]`Step.concept_ids` drifts", "`Step.concept_ids` drifts"),
            ("[step-3]**important** gap", "**important** gap"),
        ],
        ids=["code", "bold"],
    )
    def test_unopened_trailing_marker_belongs_to_the_prose(
        self, body: str, expected_rest: str
    ) -> None:
        """The regression a naive both-sides strip introduces: with no
        leading wrapper there is nothing to close, so a marker that opens
        the finding text must survive. Eating it leaves an unbalanced
        span that renders as broken markdown in the report."""
        from plan_tool.review import _split_audit_key

        assert _split_audit_key(body) == ("step-3", expected_rest)

    def test_trailing_wrapper_is_stripped_only_when_it_mirrors(self) -> None:
        """An unbalanced *leading* wrapper still yields the anchor, and
        consumes nothing it did not open."""
        from plan_tool.review import _split_audit_key

        assert _split_audit_key("**[step-3] unbalanced") == (
            "step-3", "unbalanced"
        )

    @pytest.mark.parametrize(
        "opened",
        ["**[cache-invalidation]**", "`[cache-invalidation]`"],
        ids=["bold", "code"],
    )
    def test_wrapped_slug_hashes_to_the_same_id_as_the_bare_form(
        self, opened: str
    ) -> None:
        """The regression that motivated this: a backtick-wrapped slug
        must not mint a fresh content-hashed id, or the same recurring
        finding reads as a new one every audit and cross-run
        recurrence-counting (e.g. convergence's structural-recurrence
        check) under-counts it."""
        from plan_tool.review import _parse_plan_audit_findings

        def _section(open_form: str) -> str:
            return (
                "## Completeness findings\n\n"
                f"- MEDIUM: {open_form} Risks names a hazard no step "
                "mitigates (impact=high, complexity=medium)\n"
            )

        bare = _parse_plan_audit_findings(_section("[cache-invalidation]"))[0][0]
        wrapped = _parse_plan_audit_findings(_section(opened))[0][0]
        assert wrapped.anchor == bare.anchor == "cache-invalidation"
        assert wrapped.id == bare.id
        assert wrapped.title == bare.title
        # The wrapper must not survive into the rendered title.
        assert "`" not in wrapped.title and "*" not in wrapped.title

    def test_wrapped_slug_is_not_counted_sluggless(self) -> None:
        """``sluggless`` drives the conformance warning — a tolerated
        wrapper must not inflate it."""
        from plan_tool.review import _parse_plan_audit_findings

        _recs, _present, sluggless, _coerced = _parse_plan_audit_findings(
            "## Completeness findings\n\n"
            "- MEDIUM: `[cache-invalidation]` Risks names a hazard\n"
        )
        assert sluggless == 0

    def test_out_of_scope_findings_keep_distinct_topic_anchors(self) -> None:
        """The deferred classification marker must never become the id key."""
        from plan_tool.review import _parse_plan_audit_findings

        recs, _present, sluggless, _coerced = _parse_plan_audit_findings(
            "## Completeness findings\n\n"
            "- LOW: [cache-retention] Cache retention is outside this plan "
            "[out-of-scope-deferred]\n"
            "- LOW: [release-notes] Release-note cleanup is outside this plan "
            "[out-of-scope-deferred]\n"
        )

        assert sluggless == 0
        assert [rec.anchor for rec in recs] == ["cache-retention", "release-notes"]
        assert len({rec.id for rec in recs}) == 2

    def test_misshaped_header_recovers_severity_and_anchor_from_body(
        self,
    ) -> None:
        """``- HIGH `[anchor]`: prose`` (no colon after HIGH) used to
        persist as severity=info, anchor=None while impact=high still
        extracted — a partial parse that broke #125 stopping and
        recurrence matching."""
        from plan_tool.review import _parse_plan_audit_findings

        recs, _present, sluggless, _coerced = _parse_plan_audit_findings(
            "## Correctness findings\n\n"
            "- HIGH `[decision-gate-domain-input]`: Step 2 renders the "
            "constraints prompt with no upstream domain "
            "(impact=high, complexity=medium)\n"
            "- HIGH `[constraint-attribute-field]`: a field no gate checks "
            "(impact=high, complexity=low)\n"
        )
        assert sluggless == 0
        assert len(recs) == 2
        assert [r.severity for r in recs] == ["high", "high"]
        assert [r.impact for r in recs] == ["high", "high"]
        assert [r.anchor for r in recs] == [
            "decision-gate-domain-input",
            "constraint-attribute-field",
        ]
        assert not any(t.startswith("HIGH") for t in (r.title for r in recs))
        assert not any(t.startswith(":") for t in (r.title for r in recs))

    def test_misshape_after_well_formed_is_minted_with_anchor(
        self,
    ) -> None:
        """Mixed well-formed + misshape must mint both findings (not absorb)."""
        from plan_tool.review import _parse_plan_audit_findings

        recs, _present, sluggless, _coerced = _parse_plan_audit_findings(
            "## Correctness findings\n\n"
            "- HIGH: `[first]` well-formed gap "
            "(impact=high, complexity=low)\n"
            "- HIGH `[second]`: misshaped gap "
            "(impact=high, complexity=medium)\n"
        )
        assert sluggless == 0
        assert len(recs) == 2
        assert [r.severity for r in recs] == ["high", "high"]
        assert [r.anchor for r in recs] == ["first", "second"]
        assert "misshaped" not in recs[0].body
        assert "well-formed" not in recs[1].body

    def test_english_high_priority_prose_is_not_severity_recovery(
        self,
    ) -> None:
        """``HIGH priority…`` must not lift to severity via body recovery —
        only a header cue (``:``, dash+whitespace, or ``[anchor]``)
        authorizes that path. When the triage tag still says
        ``impact=high``, the incoherent-pair refuse promotes severity
        afterward (not a prose lift — title keeps ``HIGH priority…``)."""
        from plan_tool.review import (
            _parse_plan_audit_findings,
            _recover_severity_from_body,
        )

        sev, body = _recover_severity_from_body(
            "UNSPECIFIED",
            "HIGH priority items must be listed first "
            "(impact=high, complexity=low)",
        )
        assert sev == "UNSPECIFIED"
        assert body.startswith("HIGH priority")

        recs, _present, _sluggless, coerced = _parse_plan_audit_findings(
            "## Completeness findings\n\n"
            "- HIGH priority items must be listed first "
            "(impact=high, complexity=low)\n"
        )
        assert len(recs) == 1
        assert coerced == 1
        assert recs[0].severity == "high"  # coerced from info, not prose-lifted
        assert recs[0].impact == "high"
        assert recs[0].title.startswith("HIGH priority")

    def test_high_impact_only_backfills_an_unlabelled_severity(
        self,
    ) -> None:
        """A triage tag cannot override an explicit advisory prefix."""
        from plan_tool.review import (
            _parse_plan_audit_findings,
        )

        recs, _present, _sluggless, coerced = _parse_plan_audit_findings(
            "## Correctness findings\n\n"
            "- NIT: `[slug-a]` urgent gap "
            "(impact=high, complexity=low)\n"
            "## Completeness findings\n\n"
            "- unlabelled gap with high impact "
            "(impact=high, complexity=low)\n"
            "- MEDIUM: `[slug-c]` coherent high-impact medium "
            "(impact=high, complexity=low)\n"
        )
        assert coerced == 1
        by_anchor = {r.anchor: r for r in recs}
        assert by_anchor["slug-a"].severity == "nit"
        assert by_anchor["slug-c"].severity == "medium"
        assert by_anchor[None].severity == "high"  # unlabelled → coerced
        assert all(r.impact == "high" for r in recs)

    def test_high_impact_with_medium_severity_is_not_coerced(self) -> None:
        """MEDIUM + impact=high is a coherent judgment — leave it."""
        from plan_tool.review import _parse_plan_audit_findings

        recs, _present, _sluggless, coerced = _parse_plan_audit_findings(
            "## Completeness findings\n\n"
            "- MEDIUM: `[slug]` gap "
            "(impact=high, complexity=low)\n"
        )
        assert coerced == 0
        assert recs[0].severity == "medium"
        assert recs[0].impact == "high"

    def test_recover_severity_requires_header_cue(self) -> None:
        """Direct recovery: colon form and ``[anchor]`` form lift; prose does not."""
        from plan_tool.review import _recover_severity_from_body, _split_audit_key

        sev, rest = _recover_severity_from_body(
            "UNSPECIFIED", "HIGH: `[slug]` prose here"
        )
        assert sev == "HIGH"
        key, prose = _split_audit_key(rest)
        assert key == "slug"
        assert prose.startswith("prose")

        sev2, rest2 = _recover_severity_from_body(
            "UNSPECIFIED", "MEDIUM `[other-slug]`: gap text"
        )
        assert sev2 == "MEDIUM"
        key2, prose2 = _split_audit_key(rest2)
        assert key2 == "other-slug"
        if prose2.startswith((":", "-")):
            prose2 = prose2[1:].lstrip()
        assert prose2.startswith("gap")

        sev3, body3 = _recover_severity_from_body(
            "UNSPECIFIED", "LOW hanging fruit is out of scope"
        )
        assert sev3 == "UNSPECIFIED"
        assert body3.startswith("LOW hanging")

    def test_hyphenated_english_is_not_severity_recovery(self) -> None:
        """``high-level`` / ``low-hanging`` must not treat ``-`` as a header cue."""
        from plan_tool.review import (
            _parse_plan_audit_findings,
            _recover_severity_from_body,
        )

        for prose in (
            "high-level acceptance criteria are missing",
            "low-hanging fruit is out of scope",
        ):
            sev, body = _recover_severity_from_body("UNSPECIFIED", prose)
            assert sev == "UNSPECIFIED", prose
            assert body == prose

        recs, _present, _sluggless, _coerced = _parse_plan_audit_findings(
            "## Completeness findings\n\n"
            "- high-level acceptance criteria are missing "
            "(impact=medium, complexity=low)\n"
            "- low-hanging fruit is out of scope "
            "(impact=low, complexity=low)\n"
        )
        assert [r.severity for r in recs] == ["info", "info"]
        assert recs[0].title.startswith("high-level")
        assert recs[1].title.startswith("low-hanging")

    def test_dash_separator_still_recovers_severity(self) -> None:
        """``MEDIUM - prose`` (dash + whitespace) remains a valid header cue."""
        from plan_tool.review import _recover_severity_from_body

        sev, rest = _recover_severity_from_body(
            "UNSPECIFIED", "MEDIUM - gap text here"
        )
        assert sev == "MEDIUM"
        assert rest.startswith("gap")


class TestCheckPlanAudit:
    """Bundle-grounded semantic pass: reads the plan body + per-step
    detail files (and may Read/Grep the repo), checks correctness,
    completeness, and material ambiguity, and emits the latter under the
    two stable correctness/completeness source headings."""

    def _write_plan(
        self, tmp_path: Path, *, body: str = _FULL_BODY_SECTIONS,
        step_status: str = "pending",
    ) -> Path:
        plan_path = tmp_path / "audit-plan.md"
        plan_path.write_text(
            "---\n"
            "title: Audit Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: build the thing\n"
            f"    status: {step_status}\n"
            "---\n"
            "\n"
            f"{body}",
            encoding="utf-8",
        )
        return plan_path

    def _write_phrase_consistency_plan(self, tmp_path: Path) -> Path:
        detail_rel = "details/01-audit-sample-reuse.md"
        detail_path = tmp_path / detail_rel
        detail_path.parent.mkdir(parents=True)
        detail_path.write_text(
            "# Audit sample reuse guard\n\n"
            "## Design\n\n"
            "Keep the audit sample reuse guard phrase stable across plan "
            "and detail prose. Mechanical specifics stay illustrative, "
            "e.g. callers may branch on explicit flags, but the invariant "
            "is preserving default suppression semantics.\n",
            encoding="utf-8",
        )
        plan_path = tmp_path / "phrase-consistency-plan.md"
        plan_path.write_text(
            "---\n"
            "title: Phrase Consistency Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "features:\n"
            "  - id: audit-sample-reuse\n"
            "    title: Audit sample reuse guard\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Preserve audit sample reuse guard\n"
            "    features:\n"
            "      - audit-sample-reuse\n"
            f"    detail: {detail_rel}\n"
            "---\n\n"
            "## Overview\n\n"
            "The audit sample reuse guard keeps saved audit decisions "
            "traceable while details demote brittle mechanics to examples.\n\n"
            "## Risks\n\n"
            "- Audit sample reuse guard drift would make later fixes hard "
            "to connect to the feature id.\n\n"
            "## Acceptance criteria\n\n"
            "- The audit sample reuse guard remains named consistently "
            "across the plan and detail bundle.\n",
            encoding="utf-8",
        )
        return plan_path

    _TWO_SECTION = (
        "Prose audit.\n\n"
        "## Correctness findings\n\n"
        "- HIGH: step 1 writes a cache no step establishes\n"
        "- MEDIUM: step 5 assumes step 2 ran but is sequenced first\n\n"
        "## Completeness findings\n\n"
        "- MEDIUM: Risks names a rollback hazard no step mitigates\n"
    )

    def test_returns_empty_when_invoker_is_none(self, tmp_path: Path) -> None:
        from plan_tool.review import check_plan_audit
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        assert (
            check_plan_audit(
                plan, plan_path, repo_root=tmp_path, invoker=None,
            )
            == []
        )

    def test_runs_without_done_steps_and_routes_two_sources(
        self, tmp_path: Path
    ) -> None:
        """Unlike fulfillment, the audit fires with no DONE steps, and
        splits findings into plan-correctness / plan-completeness."""
        from plan_tool.review import check_plan_audit
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path, step_status="pending")
        plan = parse_plan(plan_path)
        captured: dict[str, str] = {}

        def fake_invoker(prompt: str):
            captured["prompt"] = prompt
            return (0, self._TWO_SECTION)

        recs = check_plan_audit(
            plan, plan_path, repo_root=tmp_path, invoker=fake_invoker,
        )
        by_source = {r.source for r in recs}
        assert by_source == {"plan-correctness", "plan-completeness"}
        corr = [r for r in recs if r.source == "plan-correctness"]
        comp = [r for r in recs if r.source == "plan-completeness"]
        assert len(corr) == 2
        assert len(comp) == 1
        assert corr[0].severity == "high"
        # Plan-only: the prompt carries the title + plan body.
        assert "Audit Plan" in captured["prompt"]
        assert "Real acceptance bullets." in captured["prompt"]
        # Ambiguity is a first-class conceptual check, but keeps the
        # established two-source wire format by routing with correctness.
        assert "### Ambiguity" in captured["prompt"]
        assert "materially different" in captured["prompt"]
        assert "Report ambiguity findings under **Correctness findings**" in (
            captured["prompt"]
        )

    def test_audit_findings_have_no_step_attribution(
        self, tmp_path: Path
    ) -> None:
        """Plan-level findings route with step_id=None — apply_finding
        picks the runnable step downstream."""
        from plan_tool.review import check_plan_audit
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        recs = check_plan_audit(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (0, self._TWO_SECTION),
        )
        assert all(r.step_id is None for r in recs)

    def test_plan_audit_accepts_only_the_literal_audit_step_tag_slot(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import _parse_plan_audit_findings_with_evidence

        response = (
            "## Correctness findings\n\n"
            "- HIGH: [valid] [audit-step:1] valid attribution\n"
            "- HIGH: [adjacent][audit-step:1] no separator\n"
            "- HIGH: [late] prose first [audit-step:1]\n"
            "- HIGH: [repeated] [audit-step:1] [audit-step:1] repeated\n"
            "- HIGH: [bad] [audit-step:01] malformed\n\n"
            "## Completeness findings\n\n_(none)_\n"
        )

        recs, _present, _sluggless, observations, _coerced = (
            _parse_plan_audit_findings_with_evidence(
                response, valid_audit_target_ids=frozenset({1})
            )
        )
        assert [observation.target_step_id for observation in observations] == [
            1,
            None,
            None,
            None,
            None,
        ]
        assert all(rec.step_id is None for rec in recs)
        assert all("audit-step" not in rec.body for rec in recs)

    def test_audit_tag_consensus_keeps_recommendations_unattributed(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.parser import parse_plan
        from plan_tool.review import audit_plan_until_stable

        plan_path = tmp_path / "five-step-audit.md"
        steps = "\n".join(
            f"  - id: {step_id}\n    title: step {step_id}"
            for step_id in range(1, 6)
        )
        plan_path.write_text(
            "---\n"
            "title: Five-step Audit\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            f"{steps}\n"
            "---\n\n"
            "## Overview\n\nAudit a five-step plan.\n",
            encoding="utf-8",
        )
        response = (
            "## Correctness findings\n\n"
            "- HIGH: [one] [audit-step:1] first material finding\n"
            "- HIGH: [two] [audit-step:2] second material finding\n"
            "- HIGH: [three] [audit-step:3] third material finding\n\n"
            "## Completeness findings\n\n_(none)_\n"
        )
        responses = iter((response, response))
        advisory_out: list = []
        recs = audit_plan_until_stable(
            parse_plan(plan_path),
            plan_path,
            repo_root=tmp_path,
            invoker=lambda _prompt: (0, next(responses)),
            max_passes=2,
            dry_rounds=1,
            advisory_out=advisory_out,
        )

        assert all(rec.step_id is None for rec in recs)
        assert advisory_out[0] is not None
        assert advisory_out[0].arm_step_ids == (1, 2, 3)

    def test_review_or_audit_high_impact_keeps_explicit_advisory_severity(
        self, tmp_path: Path
    ) -> None:
        """The explicit severity prefix remains independent of impact."""
        from plan_tool.review import check_plan_audit
        from plan_tool.parser import parse_plan

        stdout = (
            "## Correctness findings\n\n"
            "- NIT: [helper-name] clarify the helper name "
            "(impact=high, complexity=low)\n\n"
            "## Completeness findings\n\n"
            "- [missing-rationale] explain why the retry is necessary "
            "(impact=high, complexity=low)\n"
        )
        plan_path = self._write_plan(tmp_path, step_status="pending")
        plan = parse_plan(plan_path)
        recs = check_plan_audit(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (0, stdout),
        )

        assert [(rec.severity, rec.impact) for rec in recs] == [
            ("nit", "high"),
            ("high", "high"),
        ]
        assert [rec.anchor for rec in recs] == [
            "helper-name", "missing-rationale",
        ]

    def test_targeted_fix_parses_onto_suggested_action(
        self, tmp_path: Path
    ) -> None:
        """The ``### Fix`` sub-block lands on ``suggested_action`` while the
        body keeps only the gap prose and the triage tag still parses."""
        from plan_tool.review import check_plan_audit
        from plan_tool.parser import parse_plan

        stdout = (
            "## Correctness findings\n\n_(none)_\n\n"
            "## Completeness findings\n\n"
            "- MEDIUM: [audit-samples] Architecture commits to suppressing "
            "auto-accept but no step operationalizes it "
            "(impact=high, complexity=medium)\n\n"
            "### Fix\n\n"
            "add an --audit-samples explicit-vs-default branch to "
            "_resolve_audit_reuse in step 5\n"
        )
        plan_path = self._write_plan(tmp_path, step_status="pending")
        plan = parse_plan(plan_path)
        recs = check_plan_audit(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (0, stdout),
        )
        comp = [r for r in recs if r.source == "plan-completeness"]
        assert len(comp) == 1
        rec = comp[0]
        assert rec.suggested_action == (
            "add an --audit-samples explicit-vs-default branch to "
            "_resolve_audit_reuse in step 5"
        )
        # Gap prose retained; fix sub-block and triage tag stripped from body.
        assert "### Fix" not in rec.body
        assert "operationalizes it" in rec.body
        assert "impact=" not in rec.body
        assert rec.anchor == "audit-samples"
        assert rec.impact == "high" and rec.complexity == "medium"

    def test_finding_without_fix_marker_degrades(
        self, tmp_path: Path
    ) -> None:
        """A finding that omits the marker leaves ``suggested_action`` None
        (graceful degradation) — the body is unaffected."""
        from plan_tool.review import check_plan_audit
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path, step_status="pending")
        plan = parse_plan(plan_path)
        recs = check_plan_audit(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (0, self._TWO_SECTION),
        )
        assert all(r.suggested_action is None for r in recs)

    def test_targeted_fix_does_not_shift_finding_id(
        self, tmp_path: Path
    ) -> None:
        """Adding a ``### Fix`` sub-block to a slugged finding must not
        change its id — the anchor slug owns the fingerprint, not the fix
        wording."""
        from plan_tool.review import _parse_plan_audit_findings

        without = (
            "## Completeness findings\n\n"
            "- MEDIUM: [cache-invalidation] Risks names a hazard no step "
            "mitigates (impact=high, complexity=medium)\n"
        )
        with_fix = (
            "## Completeness findings\n\n"
            "- MEDIUM: [cache-invalidation] Risks names a hazard no step "
            "mitigates (impact=high, complexity=medium)\n\n"
            "### Fix\n\n"
            "add a mitigation criterion to step 3\n"
        )
        id_without = _parse_plan_audit_findings(without)[0][0].id
        id_with = _parse_plan_audit_findings(with_fix)[0][0].id
        assert id_without == id_with

    def test_restated_marker_parses_onto_restated_property(
        self, tmp_path: Path
    ) -> None:
        """The ``### Restated`` sub-block (bare-step Correctness only) lands
        on ``restated_property``, is stripped from the body, and a sibling
        ``### Fix`` sub-block plus the triage tag still parse."""
        from plan_tool.review import check_plan_audit
        from plan_tool.parser import parse_plan

        stdout = (
            "## Correctness findings\n\n"
            "- CRITICAL: [amount-header-distinctness] Step 2's resolution "
            "never checks the two amount-header fields name distinct CSV "
            "columns (impact=high, complexity=medium)\n\n"
            "### Restated\n\n"
            "the resolution-confidence-reconciliation chain has no "
            "guarantee against a confidently-resolved-but-degenerate "
            "mapping\n\n"
            "### Fix\n\n"
            "require distinct columns and route a collision through "
            "needs_review\n\n"
            "## Completeness findings\n\n_(none)_\n"
        )
        plan_path = self._write_plan(tmp_path, step_status="pending")
        plan = parse_plan(plan_path)
        recs = check_plan_audit(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (0, stdout),
        )
        corr = [r for r in recs if r.source == "plan-correctness"]
        assert len(corr) == 1
        rec = corr[0]
        assert rec.restated_property == (
            "the resolution-confidence-reconciliation chain has no "
            "guarantee against a confidently-resolved-but-degenerate "
            "mapping"
        )
        assert rec.suggested_action == (
            "require distinct columns and route a collision through "
            "needs_review"
        )
        # Both sub-blocks and the triage tag stripped from the body; gap
        # prose retained.
        assert "### Restated" not in rec.body
        assert "### Fix" not in rec.body
        assert "impact=" not in rec.body
        assert "distinct CSV" in rec.body
        assert rec.anchor == "amount-header-distinctness"

    def test_finding_without_restated_marker_degrades(
        self, tmp_path: Path
    ) -> None:
        """A Correctness finding that omits ``### Restated`` leaves
        ``restated_property`` ``None`` (graceful degradation) — the same
        shape as an omitted ``### Fix``."""
        from plan_tool.review import check_plan_audit
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path, step_status="pending")
        plan = parse_plan(plan_path)
        recs = check_plan_audit(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (0, self._TWO_SECTION),
        )
        assert all(r.restated_property is None for r in recs)

    def test_restated_marker_does_not_shift_finding_id(
        self, tmp_path: Path
    ) -> None:
        """Adding a ``### Restated`` sub-block to a slugged finding must not
        change its id — the anchor slug owns the fingerprint, not the
        restatement."""
        from plan_tool.review import _parse_plan_audit_findings

        without = (
            "## Correctness findings\n\n"
            "- HIGH: [cache-invalidation] A cache is introduced but no "
            "step invalidates it (impact=high, complexity=medium)\n\n"
            "## Completeness findings\n\n_(none)_\n"
        )
        with_restated = (
            "## Correctness findings\n\n"
            "- HIGH: [cache-invalidation] A cache is introduced but no "
            "step invalidates it (impact=high, complexity=medium)\n\n"
            "### Restated\n\n"
            "the plan has no invalidation route for the introduced cache\n\n"
            "## Completeness findings\n\n_(none)_\n"
        )
        id_without = _parse_plan_audit_findings(without)[0][0].id
        id_with = _parse_plan_audit_findings(with_restated)[0][0].id
        assert id_without == id_with

    def test_reversed_subblock_order_still_parses_both(
        self, tmp_path: Path
    ) -> None:
        """A finding emitting ``### Fix`` before ``### Restated`` (reversing
        the order plan-audit.md's example shows) must still recover both
        values -- the sub-block split is order-independent by design,
        unlike the withdrawn inline-marker mechanism it replaced."""
        from plan_tool.review import check_plan_audit
        from plan_tool.parser import parse_plan

        stdout = (
            "## Correctness findings\n\n"
            "- HIGH: [reversed-order] Step 2's resolution never checks "
            "distinctness (impact=high, complexity=medium)\n\n"
            "### Fix\n\n"
            "require distinct columns\n\n"
            "### Restated\n\n"
            "the resolution chain has no guarantee against a degenerate "
            "mapping\n\n"
            "## Completeness findings\n\n_(none)_\n"
        )
        plan_path = self._write_plan(tmp_path, step_status="pending")
        plan = parse_plan(plan_path)
        recs = check_plan_audit(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (0, stdout),
        )
        rec = [r for r in recs if r.source == "plan-correctness"][0]
        assert rec.suggested_action == "require distinct columns"
        assert rec.restated_property == (
            "the resolution chain has no guarantee against a degenerate "
            "mapping"
        )
        assert "### Fix" not in rec.body
        assert "### Restated" not in rec.body

    def test_marker_shaped_text_in_quoted_citation_does_not_corrupt_split(
        self, tmp_path: Path
    ) -> None:
        """A verbatim-quoted plan citation (mandatory per the property-
        coverage rule) can itself legitimately discuss marker syntax --
        plausible in this self-hosting repo, where plan-audit.md's own text
        about "### Fix"/"### Restated" is a citable plan sentence. Unlike
        the withdrawn inline ``→ fix:``/``→ restated:`` design, a heading
        that must start its own line cannot be produced by inline quoted
        prose, so the citation cannot be confused with the real sub-block
        boundary -- regression test for the bug class two code-review
        rounds found in that withdrawn mechanism."""
        from plan_tool.review import check_plan_audit
        from plan_tool.parser import parse_plan

        stdout = (
            "## Correctness findings\n\n"
            "- HIGH: [quoted-marker-text] Step 3 cites the plan text "
            '"append the fix in the form -> fix: <remediation>, placed '
            'before the -> restated: <one-line restatement>" as the '
            "property it relies on, but nothing enforces it "
            "(impact=high, complexity=medium)\n\n"
            "### Restated\n\n"
            "the plan has no enforcement route for its own documented "
            "marker contract\n\n"
            "### Fix\n\n"
            "add a validator step\n\n"
            "## Completeness findings\n\n_(none)_\n"
        )
        plan_path = self._write_plan(tmp_path, step_status="pending")
        plan = parse_plan(plan_path)
        recs = check_plan_audit(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (0, stdout),
        )
        rec = [r for r in recs if r.source == "plan-correctness"][0]
        assert rec.restated_property == (
            "the plan has no enforcement route for its own documented "
            "marker contract"
        )
        assert rec.suggested_action == "add a validator step"
        # The false marker-shaped text inside the quoted citation survives
        # in the gap prose rather than truncating it.
        assert (
            '"append the fix in the form -> fix: <remediation>, placed '
            'before the -> restated: <one-line restatement>"' in rec.body
        )
        assert "as the property it relies on" in rec.body

    def test_completeness_finding_never_carries_a_restatement(
        self, tmp_path: Path
    ) -> None:
        """``restated_property`` is Correctness-axis only by contract; a
        stray ``### Restated`` sub-block on a Completeness bullet must not
        populate it, even though nothing in the parser forbids the model
        from emitting one there."""
        from plan_tool.review import check_plan_audit
        from plan_tool.parser import parse_plan

        stdout = (
            "## Correctness findings\n\n_(none)_\n\n"
            "## Completeness findings\n\n"
            "- MEDIUM: [stray-marker] A concept the plan names is never "
            "operationalized (impact=medium, complexity=low)\n\n"
            "### Restated\n\n"
            "the plan has no route for this concept\n"
        )
        plan_path = self._write_plan(tmp_path, step_status="pending")
        plan = parse_plan(plan_path)
        recs = check_plan_audit(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (0, stdout),
        )
        comp = [r for r in recs if r.source == "plan-completeness"][0]
        assert comp.restated_property is None
        # The sub-block is still stripped from the body even though its
        # value is discarded, so the stray syntax doesn't leak into the
        # rendered finding text.
        assert "### Restated" not in comp.body

    def test_duplicate_subblock_heading_keeps_first_occurrence(
        self, tmp_path: Path
    ) -> None:
        """A repeated ``### Fix`` heading keeps its first occurrence --
        matching :func:`parse_redirect_block`'s own documented convention
        for the sibling ``## Redirect`` sub-block."""
        from plan_tool.review import check_plan_audit
        from plan_tool.parser import parse_plan

        stdout = (
            "## Correctness findings\n\n_(none)_\n\n"
            "## Completeness findings\n\n"
            "- MEDIUM: [dup-fix] A concept the plan names is never "
            "operationalized (impact=medium, complexity=low)\n\n"
            "### Fix\n\nfirst remediation\n\n"
            "### Fix\n\nsecond remediation\n"
        )
        plan_path = self._write_plan(tmp_path, step_status="pending")
        plan = parse_plan(plan_path)
        recs = check_plan_audit(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (0, stdout),
        )
        comp = [r for r in recs if r.source == "plan-completeness"][0]
        assert comp.suggested_action == "first remediation"

    def test_duplicate_subblock_heading_skips_empty_first_occurrence(
        self, tmp_path: Path
    ) -> None:
        """An empty ``### Fix`` heading must not shadow a real, non-empty
        one that follows -- the "first occurrence" contract means first
        NON-EMPTY occurrence, not literally the first heading match."""
        from plan_tool.review import check_plan_audit
        from plan_tool.parser import parse_plan

        stdout = (
            "## Correctness findings\n\n_(none)_\n\n"
            "## Completeness findings\n\n"
            "- MEDIUM: [empty-then-real-fix] A concept the plan names is "
            "never operationalized (impact=medium, complexity=low)\n\n"
            "### Fix\n\n"
            "### Restated\n\nnot on this axis\n\n"
            "### Fix\n\nthe real remediation\n"
        )
        plan_path = self._write_plan(tmp_path, step_status="pending")
        plan = parse_plan(plan_path)
        recs = check_plan_audit(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (0, stdout),
        )
        comp = [r for r in recs if r.source == "plan-completeness"][0]
        assert comp.suggested_action == "the real remediation"

    def test_subblock_heading_with_colon_suffix_still_parses(
        self, tmp_path: Path
    ) -> None:
        """A model slip emitting ``### Fix:``/``### Restated:`` (the
        withdrawn predecessor design used colons) must not leave a stray
        leading ``: `` in the captured value."""
        from plan_tool.review import check_plan_audit
        from plan_tool.parser import parse_plan

        stdout = (
            "## Correctness findings\n\n"
            "- HIGH: [colon-heading] Step 2 names a property with no route "
            "(impact=high, complexity=medium)\n\n"
            "### Restated:\n\nthe generalized property claim\n\n"
            "### Fix:\n\nthe proposed fix\n\n"
            "## Completeness findings\n\n_(none)_\n"
        )
        plan_path = self._write_plan(tmp_path, step_status="pending")
        plan = parse_plan(plan_path)
        recs = check_plan_audit(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (0, stdout),
        )
        rec = [r for r in recs if r.source == "plan-correctness"][0]
        assert rec.restated_property == "the generalized property claim"
        assert rec.suggested_action == "the proposed fix"

    def test_fenced_citation_containing_a_real_heading_line_does_not_corrupt_split(
        self, tmp_path: Path
    ) -> None:
        """Round 4 regression: a multi-line verbatim citation can contain a
        genuine line-starting ``### Restated``/``### Fix`` heading (this
        repo's own worked example does), which a bare heading-position
        heuristic cannot distinguish from the real boundary -- the class
        the sub-block redesign was built to close, reopened one level up.
        plan-audit.md now requires such a citation to be fenced; the parser
        excludes any match inside a fenced span from the boundary search."""
        from plan_tool.review import check_plan_audit
        from plan_tool.parser import parse_plan

        stdout = (
            "## Correctness findings\n\n"
            "- HIGH: [fenced-citation] Step 2 names a property with no "
            "route; the plan cites this repo's own contract:\n\n"
            "```\n"
            "### Restated\n\n"
            "fake restated from the citation\n\n"
            "### Fix\n\n"
            "fake fix from the citation\n"
            "```\n\n"
            "(impact=high, complexity=medium)\n\n"
            "### Restated\n\n"
            "the real restated claim\n\n"
            "### Fix\n\n"
            "the real fix\n\n"
            "## Completeness findings\n\n_(none)_\n"
        )
        plan_path = self._write_plan(tmp_path, step_status="pending")
        plan = parse_plan(plan_path)
        recs = check_plan_audit(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (0, stdout),
        )
        rec = [r for r in recs if r.source == "plan-correctness"][0]
        assert rec.restated_property == "the real restated claim"
        assert rec.suggested_action == "the real fix"
        assert "fake restated from the citation" in rec.body
        assert "fake fix from the citation" in rec.body

    def test_unfenced_citation_containing_a_real_heading_line_is_a_known_residual_risk(
        self,
    ) -> None:
        """Deliberate carve-out, not a bug to fix here: an UNFENCED
        citation that happens to contain a bare ``### Restated``/``### Fix``
        line is NOT protected -- fencing is a prompt-compliance requirement
        (plan-audit.md), not a guarantee the parser can enforce on its own.
        Pinned so a future round doesn't rediscover this as a fresh finding
        without knowing it's an accepted, documented tradeoff."""
        from plan_tool.review import _split_audit_restated_and_fix

        body = (
            "The plan cites this repo's own contract verbatim, unfenced:\n\n"
            "### Restated\n\nfake restated from the citation\n\n"
            "### Fix\n\nfake fix from the citation\n\n"
            "the real gap prose continues here.\n"
        )
        restated, fix, gap = _split_audit_restated_and_fix(body)
        # The unfenced embedded heading wins -- known, accepted limitation.
        assert restated == "fake restated from the citation"

    def test_unclosed_citation_fence_degrades_to_none_not_corruption(
        self,
    ) -> None:
        """Round-5 regression: the round-4 regex-based fence matcher paired
        an unclosed citation fence with an unrelated LATER fence elsewhere
        in the same finding (a code sample in the real ### Fix text),
        merging everything between into one bogus span and silently
        replacing restated_property/suggested_action with garbled
        citation fragments -- even though the model wrote its own
        sub-blocks correctly and unfenced. Failing safe to None is the
        correct outcome here: the model's own mistake (not closing its
        fence) makes its trailing content unrecoverable, but the parser
        must not fabricate wrong content in its place."""
        from plan_tool.review import _split_audit_restated_and_fix

        body = (
            "cites plan text in an unclosed fence:\n\n"
            "```\n"
            "the citation never closes its own fence\n\n"
            "### Restated\n\n"
            "the real restated claim\n\n"
            "### Fix\n\n"
            "do X, for example:\n\n"
            "```python\n"
            "foo()\n"
            "```\n"
        )
        restated, fix, gap = _split_audit_restated_and_fix(body)
        assert restated is None
        assert fix is None

    def test_fenced_span_between_two_real_headings_is_excised_not_leaked(
        self,
    ) -> None:
        """Round-5 regression: excluding a fake heading match from the
        boundary search isn't enough -- the fenced span's own text (fake
        heading, backticks, and all) must also be excised from an adjacent
        REAL heading's captured value, not swallowed into it verbatim."""
        from plan_tool.review import _split_audit_restated_and_fix

        body = (
            "### Fix\n\n"
            "F1 short real answer.\n\n"
            "Some citation text follows:\n\n"
            "```\n### Restated\n\nfake restated inside citation\n```\n\n"
            "### Fix\n\n"
            "F2 second real fix."
        )
        _restated, fix, _gap = _split_audit_restated_and_fix(body)
        assert fix == "F1 short real answer. Some citation text follows:"
        assert "```" not in fix
        assert "fake restated" not in fix

    def test_tilde_fenced_citation_protects_the_boundary(self) -> None:
        """CommonMark's other fence delimiter, ~~~, must get the same
        protection as ```` ``` ````."""
        from plan_tool.review import _split_audit_restated_and_fix

        body = (
            "cites text with a tilde fence:\n\n"
            "~~~\n### Restated\n\nfake\n~~~\n\n"
            "### Restated\n\nreal restated\n\n### Fix\n\nreal fix\n"
        )
        restated, fix, _gap = _split_audit_restated_and_fix(body)
        assert restated == "real restated"
        assert fix == "real fix"

    def test_indented_citation_fence_protects_the_boundary(self) -> None:
        """A fence indented past CommonMark's 3-space limit (a plausible
        rendering choice nested under a bulleted list continuation) must
        still be recognized -- a missed fence is the unsafe direction for
        this internal protocol, unlike literal markdown rendering."""
        from plan_tool.review import _split_audit_restated_and_fix

        body = (
            "cites text, indented fence:\n\n"
            "    ```\n    ### Restated\n\n    fake\n    ```\n\n"
            "### Restated\n\nreal restated\n\n### Fix\n\nreal fix\n"
        )
        restated, fix, _gap = _split_audit_restated_and_fix(body)
        assert restated == "real restated"
        assert fix == "real fix"

    def test_crlf_citation_fence_protects_the_boundary(self) -> None:
        """A citation using CRLF line endings must not silently lose fence
        protection."""
        from plan_tool.review import _split_audit_restated_and_fix

        body = (
            "cites text:\r\n\r\n```\r\n### Restated\r\n\r\nfake\r\n```\r\n\r\n"
            "### Restated\r\n\r\nreal restated\r\n\r\n"
            "### Fix\r\n\r\nreal fix\r\n"
        )
        restated, fix, _gap = _split_audit_restated_and_fix(body)
        assert restated == "real restated"
        assert fix == "real fix"

    def test_nested_triple_backtick_citation_with_longer_outer_fence(
        self,
    ) -> None:
        """A compliant model widens its outer fence past the citation's own
        nested triple-backtick run (plan-audit.md now instructs this); the
        parser must not close the outer fence on the shorter nested run."""
        from plan_tool.review import _split_audit_restated_and_fix

        body = (
            "cites text with its own fenced example:\n\n"
            "````\n### Restated\n\nfake outer\n\n"
            "```\nfake nested\n```\n````\n\n"
            "### Restated\n\nreal restated\n\n### Fix\n\nreal fix\n"
        )
        restated, fix, _gap = _split_audit_restated_and_fix(body)
        assert restated == "real restated"
        assert fix == "real fix"

    def test_subblock_heading_colon_variants_all_strip_cleanly(self) -> None:
        """Round-5 regression: the round-4 colon-suffix fix only consumed a
        colon immediately after the heading word -- ``### Restated :``
        (space before colon) and ``### Restated::`` (doubled colon) still
        left a stray leading punctuation prefix."""
        from plan_tool.review import _split_audit_restated_and_fix

        space_then_colon = (
            "### Restated :\n\nreal value\n\n### Fix\n\nreal fix\n"
        )
        double_colon = (
            "### Restated::\n\nreal value\n\n### Fix\n\nreal fix\n"
        )
        assert _split_audit_restated_and_fix(space_then_colon)[0] == (
            "real value"
        )
        assert _split_audit_restated_and_fix(double_colon)[0] == "real value"

    def test_returns_empty_on_nonzero_exit(self, tmp_path: Path) -> None:
        from plan_tool.review import check_plan_audit
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        assert (
            check_plan_audit(
                plan, plan_path, repo_root=tmp_path,
                invoker=lambda _p: (127, ""),
            )
            == []
        )

    def test_returns_empty_when_invoker_raises(self, tmp_path: Path) -> None:
        from plan_tool.review import check_plan_audit
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)

        def boom(_p):
            raise RuntimeError("claude crashed")

        assert (
            check_plan_audit(
                plan, plan_path, repo_root=tmp_path, invoker=boom,
            )
            == []
        )

    def test_empty_sections_yield_no_findings(self, tmp_path: Path) -> None:
        from plan_tool.review import check_plan_audit
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        recs = check_plan_audit(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (
                0,
                "## Correctness findings\n\n_(none)_\n\n"
                "## Completeness findings\n\n_(none)_\n",
            ),
        )
        assert recs == []

    def test_render_prompt_returns_none_for_bodyless_plan(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import render_plan_audit_prompt
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path, body="")
        plan = parse_plan(plan_path)
        assert (
            render_plan_audit_prompt(plan, plan_path, repo_root=tmp_path)
            is None
        )

    def test_plan_audit_prompt_mentions_concept_phrase_consistency(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import render_plan_audit_prompt
        from plan_tool.parser import parse_plan

        plan_path = self._write_phrase_consistency_plan(tmp_path)
        plan = parse_plan(plan_path)
        prompt = render_plan_audit_prompt(plan, plan_path, repo_root=tmp_path)

        assert prompt is not None
        assert "Concept phrase consistency" in prompt
        assert "Flag concept phrase" in prompt
        assert "drift when the same concept is renamed" in prompt
        assert "same concept is renamed in a way that breaks" in prompt
        assert "**not** flag harmless wording variation" in prompt
        assert "generic synonyms" in prompt
        assert "real code, file, or symbol" in prompt
        assert "names that differ for valid reasons" in prompt
        assert "Phrase drift alone is advisory" in prompt
        # Shared regression fixture: the prompt carries the recurring phrase
        # and keeps brittle mechanics demoted to an example in the detail.
        assert "audit sample reuse guard" in prompt
        assert "Mechanical specifics stay illustrative" in prompt
        assert "e.g. callers may branch on explicit flags" in prompt

    def test_plan_audit_phrase_guidance_stays_in_stable_prefix(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import render_plan_audit_prompt
        from plan_tool.parser import parse_plan

        plan_path = self._write_phrase_consistency_plan(tmp_path)
        plan = parse_plan(plan_path)
        prompt = render_plan_audit_prompt(plan, plan_path, repo_root=tmp_path)

        assert prompt is not None
        phrase_guidance = prompt.index("Concept phrase consistency")
        assert phrase_guidance < prompt.index("## Plan body")
        assert phrase_guidance < prompt.index(
            "## Detail files (implementation bundle)"
        )

    def test_plan_audit_parses_phrase_drift_finding_as_completeness(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import check_plan_audit
        from plan_tool.parser import parse_plan

        stdout = (
            "## Correctness findings\n\n_(none)_\n\n"
            "## Completeness findings\n\n"
            "- NIT: [audit-sample-reuse] Risks call the recurring concept "
            "`audit sample reuse guard`, but step 1 (`Preserve audit "
            "sample reuse guard`) and its detail switch to `saved audit "
            "reuse policy` with no bridge, so readers cannot tell the "
            "risk and implementation describe the same thread "
            "(impact=low, complexity=low)\n\n"
            "### Fix\n\n"
            "choose one distinctive phrase for the concept and "
            "bridge the alternate wording in the plan/detail prose\n"
        )
        plan_path = self._write_phrase_consistency_plan(tmp_path)
        plan = parse_plan(plan_path)
        recs = check_plan_audit(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (0, stdout),
        )

        assert len(recs) == 1
        rec = recs[0]
        assert rec.source == "plan-completeness"
        assert rec.severity == "nit"
        assert rec.anchor == "audit-sample-reuse"
        assert rec.suggested_action == (
            "choose one distinctive phrase for the concept and bridge the "
            "alternate wording in the plan/detail prose"
        )
        assert "cannot tell the risk and implementation" in rec.body
        assert rec.impact == "low"
        assert rec.complexity == "low"

    def test_plan_audit_phrase_drift_finding_id_uses_concept_anchor(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import check_plan_audit
        from plan_tool.parser import parse_plan

        plan_path = self._write_phrase_consistency_plan(tmp_path)
        plan = parse_plan(plan_path)

        def audit(phrasing: str):
            return check_plan_audit(
                plan, plan_path, repo_root=tmp_path,
                invoker=lambda _p: (
                    0,
                    "## Correctness findings\n\n_(none)_\n\n"
                    "## Completeness findings\n\n"
                    f"- NIT: [audit-sample-reuse] {phrasing} "
                    "(impact=low, complexity=low)\n\n"
                    "### Fix\n\nbridge the alternate wording\n",
                ),
            )

        id_a = audit(
            "the risk says reuse guard while the detail says policy"
        )[0].id
        id_b = audit("the detail renames the same reader-facing thread")[0].id
        assert id_a == id_b

    def test_fixless_findings_surface_in_log(self, tmp_path: Path) -> None:
        """Findings omitting the `### Fix` sub-block are counted and logged —
        contract-conformance parity with the missing-slug visibility."""
        import io
        from plan_tool.review import check_plan_audit
        from plan_tool.parser import parse_plan

        # One finding carries a fix, one omits it.
        stdout = (
            "## Correctness findings\n\n"
            "- HIGH: [a] step 1 contradicts step 2 "
            "(impact=high, complexity=low)\n\n"
            "### Fix\n\nreorder step 1 after step 2\n\n"
            "## Completeness findings\n\n"
            "- MEDIUM: [b] Risks names a hazard no step mitigates "
            "(impact=medium, complexity=low)\n"
        )
        plan_path = self._write_plan(tmp_path, step_status="pending")
        plan = parse_plan(plan_path)
        sink = io.StringIO()
        check_plan_audit(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (0, stdout), log_file=sink,
        )
        assert "1 missing ### Fix" in sink.getvalue()

    _KEYED_SECTIONS = (
        "## Correctness findings\n\n"
        "- HIGH: [cache-coherence] step 1 writes a cache no step "
        "establishes\n\n"
        "## Completeness findings\n\n"
        "- MEDIUM: [rollback-hazard] Risks names a rollback hazard "
        "no step mitigates\n"
    )

    def test_anchor_slug_strips_from_body_and_title(
        self, tmp_path: Path
    ) -> None:
        """The ``[slug]`` is a machine key, not prose — it must not leak
        into the rendered body or title shown to the user."""
        from plan_tool.review import check_plan_audit
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        recs = check_plan_audit(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (0, self._KEYED_SECTIONS),
        )
        corr = next(r for r in recs if r.source == "plan-correctness")
        assert corr.body.startswith("step 1 writes a cache")
        assert "[cache-coherence]" not in corr.body
        assert "[cache-coherence]" not in corr.title

    def test_anchor_slug_retained_on_recommendation(
        self, tmp_path: Path
    ) -> None:
        """The slug is kept on ``rec.anchor`` (not just hashed into the
        id) so the multi-sample loop can feed it back into later
        samples' prompts and reports can cite it as a readable key. Sluggless findings stay ``None``."""
        from plan_tool.review import check_plan_audit
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        recs = check_plan_audit(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (0, self._KEYED_SECTIONS),
        )
        assert {r.anchor for r in recs} == {
            "cache-coherence", "rollback-hazard",
        }
        sluggless = check_plan_audit(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (
                0,
                "## Correctness findings\n\n"
                "- HIGH: no slug on this one\n\n"
                "## Completeness findings\n\n_(none)_\n",
            ),
        )
        assert sluggless[0].anchor is None

    def test_anchor_slug_gives_rephrasing_stable_id(
        self, tmp_path: Path
    ) -> None:
        """Two audits that name the same concept with the same slug but
        different prose must produce the SAME rec id — that's what lets
        the convergence loop recognize a re-surfaced finding instead of
        treating it as brand new (the body-hash treadmill fix)."""
        from plan_tool.review import check_plan_audit
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)

        def audit(phrasing: str):
            return check_plan_audit(
                plan, plan_path, repo_root=tmp_path,
                invoker=lambda _p: (
                    0,
                    "## Correctness findings\n\n"
                    f"- HIGH: [cache-coherence] {phrasing}\n\n"
                    "## Completeness findings\n\n_(none)_\n",
                ),
            )

        id_a = audit("step 1 writes a cache no step establishes")[0].id
        id_b = audit("the cache from step 1 is never set up anywhere")[0].id
        assert id_a == id_b

    def test_missing_slug_falls_back_to_body_hash(
        self, tmp_path: Path
    ) -> None:
        """Slug-less bullets keep the legacy content-addressed id, so an
        older prompt (or a claude response that omits the slug) still
        produces stable, non-crashing ids."""
        from plan_tool.review import check_plan_audit
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        recs = check_plan_audit(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (0, self._TWO_SECTION),
        )
        # IDs are still minted (and namespaced ``plan-...``), body intact.
        corr = [r for r in recs if r.source == "plan-correctness"]
        assert all(r.id.startswith("plan-plan-correctness-") for r in corr)
        assert corr[0].body.startswith("step 1 writes a cache")

    _TRIAGE_SECTIONS = (
        "## Correctness findings\n\n"
        "- HIGH: [cache-coherence] step 1 writes a cache no step "
        "establishes (impact=high, complexity=low)\n\n"
        "## Completeness findings\n\n"
        "- LOW: [naming-nit] rename the widget concept "
        "(impact=low, complexity=high)\n"
    )

    def test_parses_impact_complexity_triage_tags(
        self, tmp_path: Path
    ) -> None:
        """The trailing ``(impact=…, complexity=…)`` tag populates
        ``rec.impact`` / ``rec.complexity`` and is stripped from the
        body/title (it's machine metadata, not prose)."""
        from plan_tool.review import check_plan_audit
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        recs = check_plan_audit(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (0, self._TRIAGE_SECTIONS),
        )
        corr = next(r for r in recs if r.source == "plan-correctness")
        comp = next(r for r in recs if r.source == "plan-completeness")
        assert (corr.impact, corr.complexity) == ("high", "low")
        assert (comp.impact, comp.complexity) == ("low", "high")
        assert "impact=" not in corr.body and "complexity=" not in corr.body
        assert "impact=" not in corr.title
        assert corr.body.startswith("step 1 writes a cache")

    def test_triage_tags_drive_apply_deferral(self, tmp_path: Path) -> None:
        """End-to-end with the apply gate: the high-impact/low-complexity
        finding applies; the low-impact/high-complexity one defers. This
        is the behavior that was a no-op before plan-audit emitted tags."""
        from plan_tool.review import (
            check_plan_audit,
            partition_findings_for_triage,
        )
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        recs = check_plan_audit(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (0, self._TRIAGE_SECTIONS),
        )
        open_apply, open_deferred = partition_findings_for_triage(
            recs, include_info=True,  # isolate the complexity gate
        )
        assert [r.title for r in open_apply] == [
            "step 1 writes a cache no step establishes"
        ]
        assert [r.title for r in open_deferred] == [
            "rename the widget concept"
        ]

    def test_missing_triage_tag_falls_open_to_apply(
        self, tmp_path: Path
    ) -> None:
        """A finding with no triage tag keeps ``impact=complexity=None``
        and falls open to apply (legacy behavior for untagged findings)."""
        from plan_tool.review import (
            check_plan_audit,
            partition_findings_for_triage,
        )
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        recs = check_plan_audit(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _p: (0, self._KEYED_SECTIONS),  # no triage tag
        )
        corr = next(r for r in recs if r.source == "plan-correctness")
        assert corr.impact is None and corr.complexity is None
        open_apply, _ = partition_findings_for_triage(recs, include_info=True)
        assert corr in open_apply

    # --- Detail-bundle grounding (report defect #1) -----------------------

    def test_plan_audit_detail_bundle_uses_markdown_section_excerpt_for_step_detail(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import render_plan_audit_prompt
        from plan_tool.parser import parse_plan

        detail_rel = "details/01-prompt-excerpts.md"
        detail_abs = tmp_path / detail_rel
        detail_abs.parent.mkdir(parents=True)
        detail_abs.write_text(
            "## Setup prose\n\n"
            + ("SETUP-ONLY-LINE\n" * 360)
            + "\n## Prompt excerpts in plan audit bundles\n\n"
            "TARGET-LATE-SECTION explains the audit bundle excerpt.\n\n"
            "## Unrelated later section\n\n"
            "Later material should not be needed.\n",
            encoding="utf-8",
        )
        plan_path = tmp_path / "audit-plan.md"
        plan_path.write_text(
            "---\n"
            "title: Audit Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Use prompt excerpts in plan audit bundles\n"
            "    status: pending\n"
            f"    detail: {detail_rel}\n"
            "---\n"
            "\n"
            f"{_FULL_BODY_SECTIONS}",
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)
        prompt = render_plan_audit_prompt(plan, plan_path, repo_root=tmp_path)

        assert prompt is not None
        assert "### Step 01 — Use prompt excerpts in plan audit bundles" in prompt
        assert "TARGET-LATE-SECTION" in prompt
        assert "SETUP-ONLY-LINE" not in prompt
        assert "_(truncated)_" in prompt

    def test_prompt_embeds_detail_file_via_step_pointer(
        self, tmp_path: Path
    ) -> None:
        """The audit prompt carries each step's on-disk detail body
        (resolved from ``step.detail``) so the conceptual pass stops
        re-flagging gaps a detail file already specifies."""
        from plan_tool.review import render_plan_audit_prompt
        from plan_tool.parser import parse_plan

        detail_rel = "details/01-build-thing.md"
        detail_abs = tmp_path / detail_rel
        detail_abs.parent.mkdir(parents=True)
        detail_abs.write_text(
            "# Build the thing\n\nCache invalidation is handled in "
            "`invalidate_cache()` after every write.\n",
            encoding="utf-8",
        )
        plan_path = tmp_path / "audit-plan.md"
        plan_path.write_text(
            "---\n"
            "title: Audit Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: build the thing\n"
            "    status: pending\n"
            f"    detail: {detail_rel}\n"
            "---\n"
            "\n"
            f"{_FULL_BODY_SECTIONS}",
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)
        prompt = render_plan_audit_prompt(plan, plan_path, repo_root=tmp_path)
        assert prompt is not None
        assert "### Step 01 — build the thing" in prompt
        assert "Cache invalidation is handled" in prompt

    def test_plan_audit_detail_bundle_preserves_missing_and_unreadable_notes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import review
        from plan_tool.parser import parse_plan

        unreadable_rel = "details/02-unreadable.md"
        unreadable_abs = tmp_path / unreadable_rel
        unreadable_abs.parent.mkdir(parents=True)
        unreadable_abs.write_text("## Unreadable\n\nbody\n", encoding="utf-8")
        plan_path = tmp_path / "audit-plan.md"
        plan_path.write_text(
            "---\n"
            "title: Audit Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: missing detail\n"
            "    detail: details/01-missing.md\n"
            "  - id: 2\n"
            "    title: unreadable detail\n"
            f"    detail: {unreadable_rel}\n"
            "---\n"
            "\n"
            f"{_FULL_BODY_SECTIONS}",
            encoding="utf-8",
        )
        original_read_text = Path.read_text
        excerpt_calls: list[str] = []

        def fake_read_text(path: Path, *args, **kwargs):
            if path == unreadable_abs:
                raise OSError("permission denied")
            return original_read_text(path, *args, **kwargs)

        def fake_build_prompt_excerpt(*args, **kwargs):
            excerpt_calls.append(args[0])
            raise AssertionError("missing/unreadable branches should not excerpt")

        monkeypatch.setattr(Path, "read_text", fake_read_text)
        monkeypatch.setattr(review, "build_prompt_excerpt", fake_build_prompt_excerpt)

        plan = parse_plan(plan_path)
        prompt = review.render_plan_audit_prompt(
            plan, plan_path, repo_root=tmp_path
        )

        assert prompt is not None
        assert "### Step 01 — missing detail" in prompt
        assert "_(no detail file on disk)_" in prompt
        assert "### Step 02 — unreadable detail" in prompt
        assert "_(unreadable: permission denied)_" in prompt
        assert excerpt_calls == []

    def _render_audit_prompt(self, tmp_path: Path, body: str) -> str:
        from plan_tool.review import render_plan_audit_prompt
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path, body=body)
        prompt = render_plan_audit_prompt(
            parse_plan(plan_path), plan_path, repo_root=tmp_path
        )
        assert prompt is not None
        return prompt

    def test_audit_prompt_names_stack_as_authoritative_preserved_section(
        self, tmp_path: Path
    ) -> None:
        prompt = self._render_audit_prompt(tmp_path, _FULL_BODY_SECTIONS)
        start = prompt.index("`## Scope guardrails`")
        sentence = prompt[start:start + 400]
        for heading in (
            "`## Audit guardrails`", "`## Expected placement`", "`## Stack`",
        ):
            assert heading in sentence

    def test_audit_prompt_treats_a_stack_contradiction_as_in_scope(
        self, tmp_path: Path
    ) -> None:
        """The stack must not be read as out of scope: contradicting it is a
        correctness finding, not an [out-of-scope-deferred] item."""
        prompt = self._render_audit_prompt(tmp_path, _FULL_BODY_SECTIONS)
        start = prompt.index("contradicts a `## Stack` choice")
        clause = prompt[start:start + 300]
        assert "correctness finding" in clause
        assert "[out-of-scope-deferred]" in clause

    def test_audit_prompt_lists_settled_store_or_hosting_product_as_a_commitment_kind(
        self, tmp_path: Path
    ) -> None:
        prompt = self._render_audit_prompt(tmp_path, _FULL_BODY_SECTIONS)
        method = prompt.index("## Method — audit commitments, not sites")
        lenses = prompt.index("## Lenses — what breaks a commitment")
        entry = prompt.index("a settled store or hosting product")
        assert method < entry < lenses

    def test_audit_prompt_with_no_stack_section_renders_without_a_stack_requirement(
        self, tmp_path: Path
    ) -> None:
        """The Stack edits are conditional on the section being present: a
        plan body without one renders cleanly and demands no stack."""
        assert "## Stack" not in _FULL_BODY_SECTIONS
        prompt = self._render_audit_prompt(tmp_path, _FULL_BODY_SECTIONS)
        assert "$" + "{" not in prompt
        assert "must carry a `## Stack`" not in prompt

    def test_volatile_inputs_are_last_for_prefix_caching(
        self, tmp_path: Path
    ) -> None:
        """The per-pass-volatile inputs (plan body, detail bundle, carried
        findings) must trail every stable instruction section so the large
        static prefix stays cache-reusable across the audit loop's re-scans
        (#74 lever A1). A regression here silently re-breaks prefix caching."""
        from plan_tool.review import render_plan_audit_prompt
        from plan_tool.parser import parse_plan

        body = _FULL_BODY_SECTIONS + "\n\nUNIQUE-PLAN-BODY-MARKER\n"
        plan_path = self._write_plan(tmp_path, body=body)
        plan = parse_plan(plan_path)
        prompt = render_plan_audit_prompt(
            plan, plan_path, repo_root=tmp_path,
            carried_findings=[
                CarriedFinding(
                    anchor="zzz-carried-marker",
                    title="carried marker finding",
                    severity="high",
                    body_excerpt="carried excerpt",
                ),
            ],
        )
        assert prompt is not None
        # Every stable instruction section forms the cached prefix.
        stable_end = max(
            prompt.index("## Method — audit commitments, not sites"),
            prompt.index("## Lenses — what breaks a commitment"),
            prompt.index("## Rules"),
            prompt.index("## Findings format"),
            prompt.index("## Writing style"),
        )
        # All volatile content (and its section headings) trails the prefix.
        assert prompt.index("UNIQUE-PLAN-BODY-MARKER") > stable_end
        assert prompt.index("[zzz-carried-marker]") > stable_end
        assert prompt.index("## Plan body") > stable_end
        assert prompt.index("## Detail files (implementation bundle)") > stable_end

    def test_plan_audit_detail_bundle_preserves_derived_path_fallback(
        self, tmp_path: Path
    ) -> None:
        """A detail file on disk at the conventional path still lands in
        the bundle even before the plan's ``detail:`` pointer is written."""
        from plan_tool.review import render_plan_audit_prompt
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)  # step has no detail pointer
        derived = tmp_path / "plan-details" / "audit-plan" / "01-build-thing.md"
        derived.parent.mkdir(parents=True)
        derived.write_text(
            "## Setup prose\n\n"
            + ("DERIVED-SETUP-ONLY\n" * 360)
            + "\n## Build thing implementation\n\n"
            "Derived-path detail body.\n",
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)
        prompt = render_plan_audit_prompt(plan, plan_path, repo_root=tmp_path)
        assert prompt is not None
        assert "### Step 01 — build the thing" in prompt
        assert "Derived-path detail body." in prompt
        assert "DERIVED-SETUP-ONLY" not in prompt

    def test_prompt_notes_missing_detail_file(self, tmp_path: Path) -> None:
        """A step with no detail file on disk renders an explicit note so
        the audit can tell 'not authored yet' from 'says nothing'."""
        from plan_tool.review import render_plan_audit_prompt
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        prompt = render_plan_audit_prompt(plan, plan_path, repo_root=tmp_path)
        assert prompt is not None
        assert "### Step 01 — build the thing" in prompt
        assert "_(no detail file on disk)_" in prompt

    # --- Cross-sample slug re-use block ------------------------------------

    def test_prompt_omits_slug_reuse_block_without_known_anchors(
        self, tmp_path: Path
    ) -> None:
        """First sample (nothing accumulated yet): no slug-reuse block,
        and no unexpanded template variable left behind."""
        from plan_tool.review import render_plan_audit_prompt
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        prompt = render_plan_audit_prompt(plan, plan_path, repo_root=tmp_path)
        assert prompt is not None
        assert "earlier audit passes" not in prompt
        assert "carried_findings_block" not in prompt

    def test_prompt_lists_known_anchors_for_slug_reuse(
        self, tmp_path: Path
    ) -> None:
        """Accumulated carried findings render as the slug-reuse block
        so a later sample maps a re-found concept onto the established
        slug instead of minting a semantic duplicate."""
        from plan_tool.review import render_plan_audit_prompt
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        prompt = render_plan_audit_prompt(
            plan, plan_path, repo_root=tmp_path,
            carried_findings=[
                CarriedFinding(
                    anchor="cache-invalidation",
                    title="cache never invalidated",
                    severity="high",
                    body_excerpt="cache gap body",
                ),
                CarriedFinding(
                    anchor="rollback-hazard",
                    title="no rollback step",
                    severity="medium",
                    body_excerpt="rollback gap body",
                ),
            ],
        )
        assert prompt is not None
        assert "re-use its exact" in prompt
        assert "- `[cache-invalidation]` (HIGH) — cache never invalidated" in prompt
        assert "- `[rollback-hazard]` (MEDIUM) — no rollback step" in prompt
        assert "  excerpt: cache gap body" in prompt
        assert "Treat confidence as display-only evidence context" in prompt
        assert "never\n  permits a carried finding to be skipped" in prompt

    # --- Layer-presence retry (report defect #3) --------------------------

    def test_retries_once_when_layer_heading_absent(
        self, tmp_path: Path
    ) -> None:
        """A response that drops a whole findings section re-prompts once
        with the conformance reminder; the retry's parse wins."""
        from plan_tool.review import check_plan_audit
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        prompts: list[str] = []

        def flaky_invoker(prompt: str):
            prompts.append(prompt)
            if len(prompts) == 1:
                # Correctness layer dropped entirely (not `_(none)_`).
                return (
                    0,
                    "## Completeness findings\n\n"
                    "- MEDIUM: [rollback-hazard] uncovered rollback\n",
                )
            return (0, self._KEYED_SECTIONS)

        recs = check_plan_audit(
            plan, plan_path, repo_root=tmp_path, invoker=flaky_invoker,
        )
        assert len(prompts) == 2
        assert "omitted a required findings section" in prompts[1]
        assert {r.source for r in recs} == {
            "plan-correctness", "plan-completeness",
        }

    def test_valid_none_layer_does_not_retry(self, tmp_path: Path) -> None:
        """Both headings present with ``_(none)_`` is a valid empty audit
        — exactly one claude call, no conformance retry."""
        from plan_tool.review import check_plan_audit
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        calls: list[str] = []

        def invoker(prompt: str):
            calls.append(prompt)
            return (
                0,
                "## Correctness findings\n\n_(none)_\n\n"
                "## Completeness findings\n\n_(none)_\n",
            )

        recs = check_plan_audit(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
        )
        assert recs == []
        assert len(calls) == 1

    def test_both_layers_absent_on_retry_returns_partial(
        self, tmp_path: Path
    ) -> None:
        """When the retry is still malformed, the second response's parse
        is accepted as-is (no infinite loop, no crash)."""
        from plan_tool.review import check_plan_audit
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        calls: list[str] = []

        def stubborn_invoker(prompt: str):
            calls.append(prompt)
            return (0, "no findings sections at all")

        recs = check_plan_audit(
            plan, plan_path, repo_root=tmp_path, invoker=stubborn_invoker,
        )
        assert recs == []
        assert len(calls) == 2

    # --- Normalized sluggless fallback id (report defect #4) --------------

    def test_sluggless_id_survives_punctuation_and_case_rewording(
        self, tmp_path: Path
    ) -> None:
        """Without a slug, the id hashes a normalized skeleton — so
        casing/punctuation/whitespace rewording maps to the same id
        instead of minting a fresh one every audit."""
        from plan_tool.review import check_plan_audit
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)

        def audit(phrasing: str):
            return check_plan_audit(
                plan, plan_path, repo_root=tmp_path,
                invoker=lambda _p: (
                    0,
                    "## Correctness findings\n\n"
                    f"- HIGH: {phrasing}\n\n"
                    "## Completeness findings\n\n_(none)_\n",
                ),
            )

        id_a = audit("step 1 writes a cache no step establishes")[0].id
        id_b = audit("Step 1 writes a cache — no step establishes!")[0].id
        assert id_a == id_b


class TestAuditTargetedFix:
    """``audit_targeted_fix`` only surfaces the fix for audit findings so a
    deterministic finding's command-shaped ``suggested_action`` is never fed
    to ``apply_finding`` as 'apply exactly this'."""

    def _rec(self, source: str, suggested: Optional[str]):
        from plan_tool.review import Recommendation

        return Recommendation(
            id="x", source=source, severity="medium", step_id=None,
            title="t", body="b", suggested_action=suggested,
        )

    def test_audit_sources_return_fix(self) -> None:
        from plan_tool.review import audit_targeted_fix

        for src in ("plan-completeness", "plan-correctness"):
            rec = self._rec(src, "add a mitigation criterion to step 3")
            assert audit_targeted_fix(rec) == (
                "add a mitigation criterion to step 3"
            )

    def test_command_bearing_sources_return_none(self) -> None:
        from plan_tool.review import audit_targeted_fix

        # detail-body / body-completeness carry a shell command or a
        # "fill in this section" hint — never a targeted plan/detail edit.
        det = self._rec("detail-body", "plan-tool detail my-plan --step 3 --force")
        body = self._rec(
            "body-completeness", "fill in the `## Risks` section, or add …"
        )
        assert audit_targeted_fix(det) is None
        assert audit_targeted_fix(body) is None


class TestPlanAuditPassConformance:
    """Outer-pass conformance aggregates on check_plan_audit / audit_plan_until_stable."""

    _write_plan = TestCheckPlanAudit._write_plan
    _TWO_SECTION = TestCheckPlanAudit._TWO_SECTION

    def _evidence(self, invoker, plan, plan_path, tmp_path):
        from plan_tool.review import check_plan_audit

        evidence: list = []
        check_plan_audit(
            plan,
            plan_path,
            repo_root=tmp_path,
            invoker=invoker,
            _sample_evidence_out=evidence,
        )
        assert len(evidence) == 1
        return evidence[0]

    def test_check_plan_audit_conforming_pass_both_headings(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import PASS_OUTCOME_CONFORMING
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        sample = self._evidence(
            lambda _p: (0, self._TWO_SECTION), plan, plan_path, tmp_path
        )
        assert sample.pass_outcome == PASS_OUTCOME_CONFORMING

    def test_check_plan_audit_inner_retry_still_one_conforming_outer_pass(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import PASS_OUTCOME_CONFORMING, check_plan_audit
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        calls = {"n": 0}

        def invoker(_prompt: str):
            calls["n"] += 1
            if calls["n"] == 1:
                return (0, "## Correctness findings\n\n_(none)_\n")
            return (0, self._TWO_SECTION)

        evidence: list = []
        check_plan_audit(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            _sample_evidence_out=evidence,
        )
        assert len(evidence) == 1
        assert evidence[0].pass_outcome == PASS_OUTCOME_CONFORMING
        assert calls["n"] == 2

    def test_check_plan_audit_failed_invoker_increments_failed_not_conforming(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import PASS_OUTCOME_FAILED_OR_MALFORMED
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        sample = self._evidence(lambda _p: (1, ""), plan, plan_path, tmp_path)
        assert sample.pass_outcome == PASS_OUTCOME_FAILED_OR_MALFORMED

    def test_check_plan_audit_missing_headings_after_retry_is_failed(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import PASS_OUTCOME_FAILED_OR_MALFORMED
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        missing = "## Correctness findings\n\n_(none)_\n"
        sample = self._evidence(lambda _p: (0, missing), plan, plan_path, tmp_path)
        assert sample.pass_outcome == PASS_OUTCOME_FAILED_OR_MALFORMED

    def test_check_plan_audit_skipped_without_invoker_counts_neither(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import PASS_OUTCOME_SKIPPED, check_plan_audit
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        evidence: list = []
        check_plan_audit(
            plan, plan_path, repo_root=tmp_path, invoker=None,
            _sample_evidence_out=evidence,
        )
        assert evidence[0].pass_outcome == PASS_OUTCOME_SKIPPED

    def test_audit_plan_until_stable_writes_conformance_counts_to_budget_report(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        sections = TestAuditPlanUntilStable._sections

        def invoker(prompt: str):
            if "Your previous response omitted" in prompt:
                return (0, sections("retry-gap"))
            return (0, sections("gap-one"))

        budget: dict = {}
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=2, dry_rounds=1, budget_report=budget,
        )
        assert budget["conforming_pass_count"] >= 1
        assert budget["failed_or_malformed_pass_count"] == 0

    def test_audit_plan_until_stable_pass_errored_counts_as_failed(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        sections = TestAuditPlanUntilStable._sections
        calls = {"n": 0}

        def invoker(_prompt: str):
            calls["n"] += 1
            if calls["n"] == 1:
                return (1, "")
            return (0, sections("gap-one"))

        budget: dict = {}
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=2, dry_rounds=1, budget_report=budget,
        )
        assert budget["failed_or_malformed_pass_count"] >= 1


class TestAuditPlanUntilStable:
    """Multi-sample wrapper: unions the non-deterministic conceptual
    audit's findings by stable id until samples run dry (report defect
    #2 — one sample captures only a subset of the stable set)."""

    _write_plan = TestCheckPlanAudit._write_plan

    @staticmethod
    def _sections(*slugs: str) -> str:
        bullets = "\n".join(
            f"- MEDIUM: [{slug}] gap about {slug}" for slug in slugs
        )
        return (
            "## Correctness findings\n\n_(none)_\n\n"
            "## Completeness findings\n\n"
            + (bullets + "\n" if bullets else "_(none)_\n")
        )

    @staticmethod
    def _sev_sections(
        completeness: tuple[tuple[str, str], ...] = (),
        *,
        correctness: tuple[tuple[str, str], ...] = (),
    ) -> str:
        """Like ``_sections`` but with an explicit ``(severity, slug)`` per
        bullet (e.g. ``_sev_sections((("NIT", "a"), ("MEDIUM", "b")))``), and
        an optional separate ``correctness`` tuple to place bullets under the
        ``## Correctness findings`` heading instead."""

        def _fmt(pairs: tuple[tuple[str, str], ...]) -> str:
            if not pairs:
                return "_(none)_\n"
            return (
                "\n".join(
                    f"- {sev}: [{slug}] gap about {slug}" for sev, slug in pairs
                )
                + "\n"
            )

        return (
            "## Correctness findings\n\n" + _fmt(correctness) + "\n"
            "## Completeness findings\n\n" + _fmt(completeness)
        )

    def _sampling_invoker(self, responses: list[str]):
        """One queued response per claude call; raises if over-called."""
        calls: list[str] = []

        def invoker(prompt: str):
            calls.append(prompt)
            return (0, responses[len(calls) - 1])

        return invoker, calls

    def test_unions_across_samples_and_stops_on_dry_round(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, calls = self._sampling_invoker([
            self._sections("cache-invalidation"),
            self._sections("rollback-hazard"),   # new id → keep sampling
            self._sections("cache-invalidation"),  # nothing new → dry
            self._sections("never-reached"),
        ])
        recs = audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=4, dry_rounds=1,
        )
        slugged = sorted(r.body for r in recs)
        assert slugged == [
            "gap about cache-invalidation",
            "gap about rollback-hazard",
        ]
        assert len(calls) == 3  # stopped on the dry round, not the cap

    def test_max_samples_caps_even_without_dry_round(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, calls = self._sampling_invoker([
            self._sections("gap-one"),
            self._sections("gap-two"),
            self._sections("gap-three"),
        ])
        recs = audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=2, dry_rounds=1,
        )
        assert len(calls) == 2
        assert len(recs) == 2

    def test_budget_report_flags_budget_limited_on_cap(
        self, tmp_path: Path
    ) -> None:
        """Hitting the cap while still discovering → budget_report records
        budget_limited=True (BACKLOG #60c trust signal)."""
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, _ = self._sampling_invoker([
            self._sections("gap-one"),
            self._sections("gap-two"),  # still new at the cap → not converged
        ])
        budget: dict = {}
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=2, dry_rounds=1, budget_report=budget,
        )
        assert budget["budget_limited"] is True
        assert budget["passes_used"] == 2
        assert budget["cap"] == 2

    def test_budget_report_clean_on_dry_stop(self, tmp_path: Path) -> None:
        """A clean dry-round stop → budget_limited=False."""
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, _ = self._sampling_invoker([
            self._sections("cache-invalidation"),
            self._sections("rollback-hazard"),
            self._sections("cache-invalidation"),  # dry → clean stop
            self._sections("never-reached"),
        ])
        budget: dict = {}
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=4, dry_rounds=1, budget_report=budget,
        )
        assert budget["budget_limited"] is False

    def test_single_sample_reproduces_legacy_behavior(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, calls = self._sampling_invoker([
            self._sections("only-gap"),
        ])
        recs = audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=1, dry_rounds=1,
        )
        assert len(calls) == 1
        assert [r.body for r in recs] == ["gap about only-gap"]

    def test_first_occurrence_wins_on_duplicate_id(
        self, tmp_path: Path
    ) -> None:
        """Same slug re-sampled with different prose keeps the earliest
        sample's wording (stable report text across runs)."""
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, _calls = self._sampling_invoker([
            "## Correctness findings\n\n_(none)_\n\n"
            "## Completeness findings\n\n"
            "- MEDIUM: [same-gap] first wording\n",
            "## Correctness findings\n\n_(none)_\n\n"
            "## Completeness findings\n\n"
            "- MEDIUM: [same-gap] reworded second time\n",
        ])
        recs = audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=2, dry_rounds=1,
        )
        assert [r.body for r in recs] == ["first wording"]

    def test_later_samples_see_accumulated_slugs(
        self, tmp_path: Path
    ) -> None:
        """Each sample after the first carries the slugs + titles already
        collected (the prompt's slug-reuse block), so a sample that
        re-finds a concept re-uses the established slug instead of
        minting a semantic duplicate the union can't collapse."""
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, calls = self._sampling_invoker([
            self._sections("cache-invalidation"),
            self._sections("rollback-hazard"),
            self._sections("rollback-hazard"),  # nothing new → dry
        ])
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=3, dry_rounds=1,
        )
        assert len(calls) == 3
        # First sample: nothing accumulated, no slug-reuse block.
        assert "earlier audit passes" not in calls[0]
        # Second sample sees the first's slug + title.
        assert (
            "- `[cache-invalidation]` (MEDIUM) — gap about cache-invalidation"
            in calls[1]
        )
        # Third sample sees the union of both prior samples.
        assert "- `[cache-invalidation]`" in calls[2]
        assert (
            "- `[rollback-hazard]` (MEDIUM) — gap about rollback-hazard"
            in calls[2]
        )

    def test_audit_loop_carries_widened_block(self, tmp_path: Path) -> None:
        """The second pass prompt carries the full prior finding context,
        not just the slug/title subset."""
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, calls = self._sampling_invoker([
            "## Correctness findings\n\n"
            "- HIGH: [cache-invalidation] cache never invalidates\n\n"
            "## Completeness findings\n\n_(none)_\n",
            "## Correctness findings\n\n"
            "- HIGH: [cache-invalidation] stale cache survives deploy\n\n"
            "## Completeness findings\n\n_(none)_\n",
        ])

        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=2, dry_rounds=1,
        )

        assert len(calls) == 2
        assert "- `[cache-invalidation]` (HIGH) — cache never invalidates" in calls[1]
        assert "  excerpt: cache never invalidates" in calls[1]

    def test_audit_loop_slug_reuse_set_unchanged(
        self, tmp_path: Path
    ) -> None:
        """The second pass prompt still receives the first pass's slug so
        reworded duplicates can collapse by anchor-derived id."""
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, calls = self._sampling_invoker([
            "## Correctness findings\n\n_(none)_\n\n"
            "## Completeness findings\n\n"
            "- MEDIUM: [cache-invalidation] cache never invalidates\n",
            "## Correctness findings\n\n_(none)_\n\n"
            "## Completeness findings\n\n"
            "- MEDIUM: [cache-invalidation] stale cache survives deploy\n",
        ])

        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=2, dry_rounds=1,
        )

        assert len(calls) == 2
        assert (
            "- `[cache-invalidation]` (MEDIUM) — cache never invalidates"
            in calls[1]
        )

    def _erroring_invoker(self):
        """Invoker that always exits non-zero; counts calls."""
        calls: list[str] = []

        def invoker(prompt: str):
            calls.append(prompt)
            return (1, "boom")

        return invoker, calls

    def test_two_dry_rounds_required_to_stop(self, tmp_path: Path) -> None:
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, calls = self._sampling_invoker([
            self._sections("a"),
            self._sections("b"),
            self._sections("a"),  # one dry sample — must NOT stop alone
            self._sections("b"),  # second consecutive dry → stop here
        ])
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=8, dry_rounds=2,
        )
        assert len(calls) == 4  # a single no-new sample is no longer a stop

    def test_stops_after_two_consecutive_dry_rounds(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, calls = self._sampling_invoker([
            self._sections("g1"),
            self._sections("g2"),
            self._sections("g1"),  # nothing new → dry 1
            self._sections("g2"),  # nothing new → dry 2 → stop
        ])
        recs = audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=8, dry_rounds=2,
        )
        assert len(calls) == 4
        assert sorted(r.body for r in recs) == [
            "gap about g1",
            "gap about g2",
        ]

    def test_keeps_sampling_while_productive_past_three(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, calls = self._sampling_invoker([
            self._sections("s1"),
            self._sections("s2"),
            self._sections("s3"),
            self._sections("s4"),
            self._sections("s5"),
        ])
        recs = audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=5, dry_rounds=2,
        )
        assert len(calls) > 3  # the old 3-sample cap no longer truncates
        assert len(recs) == 5

    def test_hard_cap_stops_and_logs_budget_limited(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, calls = self._sampling_invoker([
            self._sections("c1"),
            self._sections("c2"),
            self._sections("c3"),
        ])
        log = io.StringIO()
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=3, dry_rounds=2, log_file=log,
        )
        assert len(calls) == 3  # cap hit
        assert "budget-limited" in log.getvalue()

    def test_dry_stop_emits_no_truncation_log(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, calls = self._sampling_invoker([
            self._sections("only"),
            self._sections("only"),  # dry 1
            self._sections("only"),  # dry 2 → clean dry-stop
        ])
        log = io.StringIO()
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=8, dry_rounds=2, log_file=log,
        )
        assert len(calls) == 3
        assert "budget-limited" not in log.getvalue()

    def test_no_regression_two_sample_dry_costs_two_calls(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, calls = self._sampling_invoker([
            self._sections("gap"),
            self._sections("gap"),  # dry → stop with legacy dry_rounds=1
        ])
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=8, dry_rounds=1,
        )
        assert len(calls) == 2  # explicit-arg callers keep their behavior

    def test_new_threshold_treats_low_yield_as_dry(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, calls = self._sampling_invoker([
            self._sections("a", "b"),   # +2 new → productive
            self._sections("a", "c"),   # +1 new → below threshold 2 → dry
            self._sections("a", "d"),   # never reached
        ])
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=8, dry_rounds=1, new_threshold=2,
        )
        # The 1-new sample is non-productive at threshold 2, so dry_rounds=1
        # stops on it — at default threshold 1 it would keep sampling.
        assert len(calls) == 2

    def test_low_yield_stop_emits_budget_limited_log(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, calls = self._sampling_invoker([
            self._sections("a", "b"),        # +2 → productive
            self._sections("a", "b", "c"),   # +1 → below threshold, growing
            self._sections("a", "b", "c", "d"),  # +1 → below threshold, dry 2
        ])
        log = io.StringIO()
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=8, dry_rounds=2, new_threshold=2, log_file=log,
        )
        assert len(calls) == 3
        # The set was still growing at the stop point → not silent convergence.
        assert "budget-limited" in log.getvalue()

    def test_single_sample_cap_emits_no_truncation_log(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, calls = self._sampling_invoker([self._sections("only")])
        log = io.StringIO()
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=1, dry_rounds=2, log_file=log,
        )
        assert len(calls) == 1
        assert "budget-limited" not in log.getvalue()

    def test_errored_samples_do_not_count_as_dry(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, calls = self._erroring_invoker()
        log = io.StringIO()
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=8, dry_rounds=2, log_file=log,
        )
        # Errored samples are neutral — they never trigger the dry-stop, so
        # the loop runs the full cap instead of "converging" at dry_rounds=2.
        assert len(calls) == 8
        out = log.getvalue()
        assert "errored" in out
        assert "budget-limited" in out  # surfaced, not "all clear, converged"

    def test_audit_default_constants(self) -> None:
        from plan_tool import review

        assert review.AUDIT_DEFAULT_DRY_ROUNDS == 1
        assert review.AUDIT_DEFAULT_MAX_PASSES == 3
        assert review.AUDIT_DEFAULT_NEW_THRESHOLD == 1

    def test_budget_limited_audit_keeps_legacy_coverage_advice_fields_null(
        self, tmp_path: Path
    ) -> None:
        """A capped audit retains facts without a count-series operator route."""
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        # +3, +1, +1 unique each pass: cap hit before the two-pass dry tail.
        invoker, _ = self._sampling_invoker([
            self._sections("a", "b", "c"),
            self._sections("a", "b", "c", "d"),
            self._sections("a", "b", "c", "d", "e"),
        ])
        budget: dict = {}
        log = io.StringIO()
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=3, dry_rounds=2, budget_report=budget, log_file=log,
        )
        assert budget["budget_limited"] is True
        assert budget["passes_used"] == 3
        assert budget["cap"] == 3
        assert budget["recommendation_kind"] is None
        assert budget["recommended_passes"] is None
        assert budget["recommendation_advice"] is None
        out = log.getvalue()
        assert "budget-limited" in out
        assert "--audit-passes" not in out
        assert "plan-tool convergence" not in out

    # ---- BACKLOG #125: severity-aware diminishing-return convergence ----

    def test_singleton_low_severity_streak_converges_clean(
        self, tmp_path: Path
    ) -> None:
        """`1(nit)→1(nit)` — two singleton advisory findings in a row is a
        clean low-yield convergence, not a budget-limited cap-out."""
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, calls = self._sampling_invoker([
            self._sev_sections((("NIT", "a"),)),
            self._sev_sections((("NIT", "b"),)),  # different singleton nit
            self._sev_sections((("NIT", "c"),)),  # never reached
        ])
        budget: dict = {}
        recs = audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=5, dry_rounds=2, budget_report=budget,
        )
        assert len(calls) == 2  # stopped on the low-yield streak, not the cap
        assert sorted(r.body for r in recs) == [
            "gap about a", "gap about b",
        ]
        assert budget["budget_limited"] is False
        assert budget["confirmation_kind"] == "confirmed-low-yield"

    def test_all_low_severity_multi_finding_pass_is_non_productive(
        self, tmp_path: Path
    ) -> None:
        """A pass with several new findings is still non-productive when
        every one of them is advisory (nit) — count alone doesn't make a
        low-severity-only pass "productive". (``NIT`` is the only advisory
        token the parser recognizes as a severity-bullet prefix; ``info``
        severity only arises from an unlabeled bullet, which is exercised
        separately and isn't needed to cover this behavior.) The second,
        literally-dry pass is required by the two-pass low-yield floor (see
        ``test_low_yield_stop_requires_two_passes_even_at_default_dry_rounds``)
        even though ``dry_rounds`` here defaults to 1."""
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, calls = self._sampling_invoker([
            self._sev_sections((
                ("NIT", "a"), ("NIT", "b"), ("NIT", "c"),
            )),
            self._sev_sections(()),  # dry 2/2 (floored) → stop
            self._sev_sections((("NIT", "d"),)),  # never reached
        ])
        budget: dict = {}
        recs = audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=5, dry_rounds=1, budget_report=budget,
        )
        assert len(calls) == 2  # 3 new low-severity findings never resets the streak
        assert len(recs) == 3
        assert budget["budget_limited"] is False
        assert budget["confirmation_kind"] == "confirmed-low-yield"

    def test_low_yield_stop_requires_two_passes_even_at_default_dry_rounds(
        self, tmp_path: Path
    ) -> None:
        """A *single* advisory-only pass never converges on its own, even at
        the default ``dry_rounds=1`` — BACKLOG #125's explicit "two repeated
        low-yield passes" floor. Without it, this would wrongly stop after
        just 1 of the 3 default passes on the very first plan that happens to
        turn up a nit on pass 1."""
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, calls = self._sampling_invoker([
            self._sev_sections((("NIT", "a"),)),
            self._sev_sections((("NIT", "b"),)),  # 2nd low-yield pass → stop
            self._sev_sections((("NIT", "c"),)),  # never reached
        ])
        budget: dict = {}
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=3, dry_rounds=1, budget_report=budget,
        )
        assert len(calls) == 2  # NOT 1 — a single low-yield pass isn't confirmed
        assert budget["confirmation_kind"] == "confirmed-low-yield"

    def test_low_yield_floor_does_not_affect_new_threshold_dry_mechanism(
        self, tmp_path: Path
    ) -> None:
        """The pre-existing below-``new_threshold`` dry mechanism (unrelated
        to severity) still honors ``dry_rounds`` exactly as configured, with
        no two-pass floor — regression guard alongside the pre-existing
        ``test_new_threshold_treats_low_yield_as_dry``."""
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, calls = self._sampling_invoker([
            self._sev_sections(correctness=(("MEDIUM", "a"), ("MEDIUM", "b"))),
            # +1 new MEDIUM (material), but below new_threshold=2 → non-productive
            # for the pre-#125 reason, not the low-yield carve-out.
            self._sev_sections(correctness=(("MEDIUM", "a"), ("MEDIUM", "b"), ("MEDIUM", "c"))),
            self._sev_sections(  # never reached
                correctness=(("MEDIUM", "a"), ("MEDIUM", "b"), ("MEDIUM", "c"), ("MEDIUM", "d"))
            ),
        ])
        budget: dict = {}
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=5, dry_rounds=1, new_threshold=2, budget_report=budget,
        )
        assert len(calls) == 2  # dry_rounds=1 honored, no floor to 2
        assert budget["budget_limited"] is True  # material growth, not low-yield

    def test_below_threshold_advisory_only_pass_stays_budget_limited(
        self, tmp_path: Path
    ) -> None:
        """A below-``new_threshold`` pass whose sole new finding is
        advisory-only (nit/info) must stay budget-limited, same as the
        material variant above — severity must not let it slip through as a
        1-pass "confirmed-low-yield" just because it also happens to be
        below the count threshold. This is the gap the low-yield carve-out
        (``low_yield_reason``) deliberately excludes: it only fires when
        the count threshold is actually cleared."""
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, calls = self._sampling_invoker([
            self._sev_sections(correctness=(("MEDIUM", "a"), ("MEDIUM", "b"))),
            # +1 new NIT, below new_threshold=2 — advisory-only AND below
            # threshold at once.
            self._sev_sections((("NIT", "c"),), correctness=(("MEDIUM", "a"), ("MEDIUM", "b"))),
        ])
        budget: dict = {}
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=5, dry_rounds=1, new_threshold=2, budget_report=budget,
        )
        assert len(calls) == 2  # stops on dry_rounds=1, but must stay unconfirmed
        assert budget["budget_limited"] is True
        assert budget["confirmation_kind"] is None

    def test_low_yield_cap_keeps_coverage_facts_without_operator_route(
        self, tmp_path: Path
    ) -> None:
        """A near-confirmed low-yield tail stays factual when capped."""
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, calls = self._sampling_invoker([
            self._sev_sections(correctness=(("MEDIUM", "a"),)),
            # +1 new NIT — low-yield-eligible (threshold cleared, all
            # advisory), but the cap (2) is hit one pass short of the
            # two-pass floor.
            self._sev_sections((("NIT", "b"),), correctness=(("MEDIUM", "a"),)),
        ])
        budget: dict = {}
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=2, dry_rounds=1, budget_report=budget,
        )
        assert len(calls) == 2
        assert budget["budget_limited"] is True
        assert budget["recommendation_kind"] is None
        assert budget["recommended_passes"] is None
        assert budget["recommendation_advice"] is None

    def test_material_finding_resets_the_low_yield_streak(
        self, tmp_path: Path
    ) -> None:
        """`1(nit)→1(medium correctness)` resets the streak: the medium
        correctness finding is productive regardless of the preceding
        low-yield pass, so sampling continues past it."""
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, calls = self._sampling_invoker([
            self._sev_sections((("NIT", "a"),)),               # non-productive
            self._sev_sections(  # productive → resets the streak
                (("NIT", "a"),), correctness=(("MEDIUM", "b"),),
            ),
            self._sev_sections(  # dry 1/2 since the reset
                (("NIT", "a"),), correctness=(("MEDIUM", "b"),),
            ),
            self._sev_sections(  # dry 2/2 → stop
                (("NIT", "a"),), correctness=(("MEDIUM", "b"),),
            ),
        ])
        budget: dict = {}
        recs = audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=4, dry_rounds=2, budget_report=budget,
        )
        # If the medium correctness finding had NOT reset the streak, pass 2
        # would already have completed a 2-dry streak and stopped after only
        # 2 calls. Reaching all 4 calls proves the reset happened.
        assert len(calls) == 4
        assert sorted(r.body for r in recs) == ["gap about a", "gap about b"]
        assert budget["budget_limited"] is False
        assert budget["confirmation_kind"] == "confirmed-dry"

    def test_alternating_dry_low_and_material_passes(
        self, tmp_path: Path
    ) -> None:
        """A mixed sequence (material → low → material → low → low) still
        resets correctly on each material pass and converges low-yield on
        the trailing low-severity streak."""
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, calls = self._sampling_invoker([
            self._sev_sections(correctness=(("MEDIUM", "a"),)),  # productive
            self._sev_sections(  # non-productive (nit only) → dry 1/2
                (("NIT", "b"),), correctness=(("MEDIUM", "a"),),
            ),
            self._sev_sections(  # productive (new medium) → resets
                (("NIT", "b"),), correctness=(("MEDIUM", "a"), ("MEDIUM", "c")),
            ),
            self._sev_sections(  # non-productive (nit only) → dry 1/2
                (("NIT", "b"), ("NIT", "d")),
                correctness=(("MEDIUM", "a"), ("MEDIUM", "c")),
            ),
            self._sev_sections(  # non-productive (nit only) → dry 2/2 → stop
                (("NIT", "b"), ("NIT", "d"), ("NIT", "e")),
                correctness=(("MEDIUM", "a"), ("MEDIUM", "c")),
            ),
        ])
        budget: dict = {}
        recs = audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=6, dry_rounds=2, budget_report=budget,
        )
        assert len(calls) == 5
        assert sorted(r.body for r in recs) == [
            "gap about a", "gap about b", "gap about c",
            "gap about d", "gap about e",
        ]
        assert budget["budget_limited"] is False
        assert budget["confirmation_kind"] == "confirmed-low-yield"

    def test_low_yield_pass_dedupes_before_severity_check(
        self, tmp_path: Path
    ) -> None:
        """A re-emitted known nit id doesn't count as "new" — dedup runs
        before the severity classification, same as for any other finding."""
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, calls = self._sampling_invoker([
            self._sev_sections((("NIT", "a"),)),
            # "a" re-emitted (not new) + "b" genuinely new — still exactly
            # 1 new finding this pass, not 2.
            self._sev_sections((("NIT", "a"), ("NIT", "b"))),
        ])
        budget: dict = {}
        recs = audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=5, dry_rounds=2, budget_report=budget,
        )
        assert len(calls) == 2
        assert sorted(r.body for r in recs) == ["gap about a", "gap about b"]
        assert budget["confirmation_kind"] == "confirmed-low-yield"

    def test_singleton_high_at_cap_stays_coverage_unconfirmed(
        self, tmp_path: Path
    ) -> None:
        """A recurring singleton HIGH finding never triggers low-yield
        convergence, even though the per-pass count (1) is as small as any
        low-yield example — severity, not count, is what's checked."""
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, calls = self._sampling_invoker([
            self._sev_sections(correctness=(("HIGH", "a"),)),
            self._sev_sections(correctness=(("HIGH", "a"), ("HIGH", "b"))),
        ])
        budget: dict = {}
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=2, dry_rounds=2, budget_report=budget,
        )
        assert len(calls) == 2  # exhausted the cap while still productive
        assert budget["budget_limited"] is True
        assert budget["confirmation_kind"] is None

    # ---- cap==1 (single-pass legacy mode): confirmation_kind must not
    # ---- mislabel a productive one-shot pass as "confirmed-dry" ----

    def test_single_pass_cap_one_productive_has_no_confirmation_kind(
        self, tmp_path: Path
    ) -> None:
        """``budget_limited`` is unconditionally False at ``cap == 1`` (the
        documented single-call legacy mode), but a pass that found genuine
        new material findings never went dry — ``confirmation_kind`` must
        stay ``None``, not "confirmed-dry"."""
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, calls = self._sampling_invoker([
            self._sev_sections(correctness=(("MEDIUM", "a"),)),
        ])
        budget: dict = {}
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=1, dry_rounds=1, budget_report=budget,
        )
        assert len(calls) == 1
        assert budget["budget_limited"] is False
        assert budget["confirmation_kind"] is None

    def test_single_pass_cap_one_zero_findings_confirms_dry(
        self, tmp_path: Path
    ) -> None:
        """A single pass that genuinely finds nothing IS a confirmed-dry
        stop, even at ``cap == 1``."""
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, calls = self._sampling_invoker([self._sev_sections(())])
        budget: dict = {}
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=1, dry_rounds=1, budget_report=budget,
        )
        assert len(calls) == 1
        assert budget["budget_limited"] is False
        assert budget["confirmation_kind"] == "confirmed-dry"

    def test_single_pass_cap_one_low_yield_pass_has_no_confirmation_kind(
        self, tmp_path: Path
    ) -> None:
        """A single advisory-only pass at ``cap == 1`` can never satisfy the
        two-pass low-yield floor, so it stays unconfirmed (``None``), not
        "confirmed-low-yield" — the two-pass rule holds even when the cap
        makes a second pass impossible."""
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, calls = self._sampling_invoker([
            self._sev_sections((("NIT", "a"),)),
        ])
        budget: dict = {}
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=1, dry_rounds=1, budget_report=budget,
        )
        assert len(calls) == 1
        assert budget["budget_limited"] is False
        assert budget["confirmation_kind"] is None

    def test_high_impact_advisory_pass_is_productive(
        self, tmp_path: Path
    ) -> None:
        """A high-impact finding resets the dry streak and prompts another pass.

        The model may emit NIT + impact=high. The triage materiality signal
        remains productive while the explicit advisory severity is preserved.
        """
        from plan_tool.parser import parse_plan
        from plan_tool.review import audit_plan_until_stable

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        high_impact_response = (
            "## Correctness findings\n\n_(none)_\n\n"
            "## Completeness findings\n\n"
            "- NIT: [clarify-helper] clarify the helper name "
            "(impact: high, complexity: low)\n"
        )
        untagged_response = (
            "## Correctness findings\n\n_(none)_\n\n"
            "## Completeness findings\n\n"
            "- NIT: [style-note] clarify the surrounding prose\n"
        )
        second_untagged_response = (
            "## Correctness findings\n\n_(none)_\n\n"
            "## Completeness findings\n\n"
            "- NIT: [format-note] clarify the formatting guidance\n"
        )
        invoker, calls = self._sampling_invoker([
            untagged_response,
            high_impact_response,
            second_untagged_response,
            second_untagged_response,
        ])
        budget: dict = {}
        recs = audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=4, dry_rounds=1, budget_report=budget,
        )

        assert len(calls) == 4
        assert [(rec.severity, rec.impact, rec.complexity) for rec in recs] == [
            ("nit", None, None), ("nit", "high", "low"),
            ("nit", None, None),
        ]
        assert budget["confirmation_kind"] == "confirmed-low-yield"

    def test_audit_materiality_builds_calibration_lookup_once_per_invocation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool import review as review_module
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        lookup_builds: list[Path] = []
        evaluated_recommendations: list[str] = []

        def build_lookup(repo_root: Path):
            lookup_builds.append(repo_root)

            def demote(rec):
                evaluated_recommendations.append(rec.id)
                return True

            return demote

        monkeypatch.setattr(
            review_module, "build_low_impact_demotion_lookup", build_lookup,
        )
        invoker, calls = self._sampling_invoker([
            "## Correctness findings\n\n_(none)_\n\n"
            "## Completeness findings\n\n"
            "- MEDIUM: [first] first calibrated finding (impact: low)\n",
            "## Correctness findings\n\n_(none)_\n\n"
            "## Completeness findings\n\n"
            "- MEDIUM: [second] second calibrated finding (impact: low)\n",
        ])

        review_module.audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=3, dry_rounds=1,
        )

        assert len(calls) == 2
        assert lookup_builds == [tmp_path]
        assert len(evaluated_recommendations) == 2
        assert len(set(evaluated_recommendations)) == 2

    def test_qualifying_low_impact_medium_audit_finding_is_low_yield(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool import review as review_module
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        monkeypatch.setattr(
            review_module,
            "build_low_impact_demotion_lookup",
            lambda repo_root: lambda rec: True,
        )
        invoker, calls = self._sampling_invoker([
            "## Correctness findings\n\n_(none)_\n\n"
            "## Completeness findings\n\n"
            "- MEDIUM: [first] first calibrated finding (impact: low)\n",
            "## Correctness findings\n\n_(none)_\n\n"
            "## Completeness findings\n\n"
            "- MEDIUM: [second] second calibrated finding (impact: low)\n",
        ])
        budget: dict = {}

        review_module.audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=3, dry_rounds=1, budget_report=budget,
        )

        assert len(calls) == 2
        assert budget["confirmation_kind"] == "confirmed-low-yield"

    def test_calibration_does_not_demote_high_impact_audit_finding(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool import review as review_module
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        demotion_checks: list[str] = []

        def demote(rec):
            demotion_checks.append(rec.id)
            return True

        monkeypatch.setattr(
            review_module,
            "build_low_impact_demotion_lookup",
            lambda repo_root: demote,
        )
        invoker, calls = self._sampling_invoker([
            "## Correctness findings\n\n_(none)_\n\n"
            "## Completeness findings\n\n"
            "- NIT: [high-impact] urgent issue (impact: high)\n",
            self._sev_sections(()),
        ])

        review_module.audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=2, dry_rounds=1,
        )

        assert len(calls) == 2
        assert demotion_checks == []

    def test_calibration_does_not_demote_high_severity_audit_finding(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool import review as review_module
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        demotion_checks: list[str] = []

        def demote(rec):
            demotion_checks.append(rec.id)
            return True

        monkeypatch.setattr(
            review_module,
            "build_low_impact_demotion_lookup",
            lambda repo_root: demote,
        )
        invoker, calls = self._sampling_invoker([
            "## Correctness findings\n\n"
            "- HIGH: [high-severity] urgent issue (impact: low)\n\n"
            "## Completeness findings\n\n_(none)_\n",
            self._sev_sections(()),
        ])

        review_module.audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=2, dry_rounds=1,
        )

        assert len(calls) == 2
        assert demotion_checks == []


class TestAuditSamplerCheckpoints:
    """Completed sampler passes persist only while another pass can run."""

    _write_plan = TestCheckPlanAudit._write_plan
    _sections = staticmethod(TestAuditPlanUntilStable._sections)

    def test_resume_keeps_pre_crash_calibration_instead_of_rebuilding(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Calibration is carried on the checkpoint, not part of the resume
        identity gate (see ``_SAMPLER_IDENTITY_FIELDS``): a resumed run
        reproduces the pre-crash result even when live calibration history
        changes in between, instead of rebuilding from today's disk state."""
        from plan_tool import review as review_module
        from plan_tool.parser import parse_plan
        from plan_tool.telemetry_analysis import FindingClass, LowImpactDemotionLookup

        plan_path = self._write_plan(tmp_path)
        calls = 0
        build_calls: list[str] = []

        monkeypatch.setattr(
            review_module,
            "build_low_impact_demotion_lookup",
            lambda repo_root: build_calls.append("pre-crash")
            or LowImpactDemotionLookup(frozenset()),
        )

        def interrupted_invoker(_prompt: str):
            nonlocal calls
            calls += 1
            if calls == 1:
                return (0, self._sections("first-gap"))
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            review_module.audit_plan_until_stable(
                parse_plan(plan_path), plan_path, repo_root=tmp_path,
                invoker=interrupted_invoker, max_passes=3, dry_rounds=1,
            )

        # Live calibration changes between the crash and the resume. If the
        # resumed run rebuilt it instead of carrying the frozen snapshot,
        # this monkeypatch would fire and build_calls would grow.
        monkeypatch.setattr(
            review_module,
            "build_low_impact_demotion_lookup",
            lambda repo_root: build_calls.append("post-crash")
            or LowImpactDemotionLookup(
                frozenset({FindingClass("review", "code", "single-file", None)})
            ),
        )

        review_module.audit_plan_until_stable(
            parse_plan(plan_path), plan_path, repo_root=tmp_path,
            invoker=lambda _prompt: (0, self._sections("second-gap")),
            max_passes=3, dry_rounds=1,
        )

        assert build_calls == ["pre-crash"]

    def test_resumed_run_with_skipped_pass_reports_budget_limited_not_converged(
        self, tmp_path: Path,
    ) -> None:
        """A skipped pass (no invoker) continuing a genuine resumed
        checkpoint must not read as dry-streak convergence — that would
        silently finalize real carried progress as "confirmed" even though
        no real sampling happened this run."""
        from plan_tool import review as review_module
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        calls = 0

        def interrupted_invoker(_prompt: str):
            nonlocal calls
            calls += 1
            if calls == 1:
                return (0, self._sections("durable-gap"))
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            review_module.audit_plan_until_stable(
                parse_plan(plan_path), plan_path, repo_root=tmp_path,
                invoker=interrupted_invoker, max_passes=3, dry_rounds=1,
            )

        budget: dict = {}
        resumed: list[bool] = []
        result = review_module.audit_plan_until_stable(
            parse_plan(plan_path), plan_path, repo_root=tmp_path,
            invoker=None, max_passes=3, dry_rounds=1,
            budget_report=budget, resumed_out=resumed,
        )

        assert resumed == [True]
        # The real carried finding from the genuinely-completed pass is
        # still returned...
        assert [rec.body for rec in result] == ["gap about durable-gap"]
        # ...but the outcome is honestly reported as unconfirmed, not as a
        # false "confirmed-dry" convergence.
        assert budget["budget_limited"] is True
        assert budget["confirmation_kind"] != "confirmed-dry"

    def test_continuing_pass_checkpoint_contains_completed_sampler_state(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.parser import parse_plan
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.review_persistence import load_sampler_checkpoint

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        calls = 0

        def invoker(prompt: str):
            nonlocal calls
            calls += 1
            if calls == 2:
                checkpoint = load_sampler_checkpoint(plan_path)
                assert checkpoint.status == "valid"
                assert checkpoint.review is not None
                assert [rec.body for rec in checkpoint.review.recommendations] == [
                    "gap about first-gap"
                ]
                state = checkpoint.review.sampler_state
                assert state is not None
                assert state["lifecycle"] == "in-progress"
                assert state["passes"] == 1
                assert state["next_pass"] == 2
                assert state["conforming_pass_count"] == 1
                assert state["failed_or_malformed_pass_count"] == 0
                assert state["consecutive_dry"] == 0
                assert state["materiality_by_id"]
                assert state["observations_by_id"]
                assert state["low_impact_demotion_classes"] == []
                assert "[first-gap]" in prompt
            return (0, self._sections("first-gap"))

        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=3, dry_rounds=1,
        )

        assert calls == 2

    def test_continuing_pass_replaces_the_prior_sampler_checkpoint(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.parser import parse_plan
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.review_persistence import load_sampler_checkpoint

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        calls = 0

        def invoker(_prompt: str):
            nonlocal calls
            calls += 1
            if calls == 3:
                checkpoint = load_sampler_checkpoint(plan_path)
                assert checkpoint.status == "valid"
                assert checkpoint.review is not None
                state = checkpoint.review.sampler_state
                assert state is not None
                assert state["lifecycle"] == "in-progress"
                assert state["passes"] == 2
                assert state["next_pass"] == 3
                assert [rec.body for rec in checkpoint.review.recommendations] == [
                    "gap about first-gap", "gap about second-gap"
                ]
            return (0, self._sections(
                "first-gap" if calls != 2 else "second-gap"
            ))

        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=4, dry_rounds=1,
        )

        assert calls == 3

    def test_nonterminal_errored_pass_persists_its_consumed_sampler_slot(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.parser import parse_plan
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.review_persistence import load_sampler_checkpoint

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        calls = 0

        def invoker(_prompt: str):
            nonlocal calls
            calls += 1
            if calls == 2:
                checkpoint = load_sampler_checkpoint(plan_path)
                assert checkpoint.review is not None
                state = checkpoint.review.sampler_state
                assert state is not None
                assert state["passes"] == 1
                assert state["next_pass"] == 2
                assert state["failed_or_malformed_pass_count"] == 1
                assert state["conforming_pass_count"] == 0
                return (0, self._sections("gap"))
            if calls == 1:
                return (1, "ordinary failure")
            return (0, self._sections("gap"))

        budget: dict = {}
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=3, dry_rounds=1, budget_report=budget,
        )

        assert calls == 3
        assert budget["failed_or_malformed_pass_count"] == 1

    def test_keyboard_interrupt_does_not_checkpoint_the_inflight_pass(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.parser import parse_plan
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.review_persistence import load_sampler_checkpoint

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        calls = 0

        def invoker(_prompt: str):
            nonlocal calls
            calls += 1
            if calls == 1:
                return (0, self._sections("durable-gap"))
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            audit_plan_until_stable(
                plan, plan_path, repo_root=tmp_path, invoker=invoker,
                max_passes=3, dry_rounds=1,
            )

        checkpoint = load_sampler_checkpoint(plan_path)
        assert checkpoint.status == "valid"
        assert checkpoint.review is not None
        assert checkpoint.review.sampler_state is not None
        assert checkpoint.review.sampler_state["passes"] == 1
        assert [rec.body for rec in checkpoint.review.recommendations] == [
            "gap about durable-gap"
        ]

    def test_resume_after_interruption_starts_at_next_unrun_pass(
        self, tmp_path: Path
    ) -> None:
        """Resume carries completed findings and spends only the open pass."""
        from plan_tool.parser import parse_plan
        from plan_tool.review import audit_plan_until_stable

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        initial_calls = 0

        def interrupted_invoker(_prompt: str):
            nonlocal initial_calls
            initial_calls += 1
            if initial_calls == 1:
                return (0, self._sections("first-gap"))
            if initial_calls == 2:
                return (0, self._sections("second-gap"))
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            audit_plan_until_stable(
                plan,
                plan_path,
                repo_root=tmp_path,
                invoker=interrupted_invoker,
                max_passes=3,
                dry_rounds=1,
            )

        resumed_prompts: list[str] = []
        resumed: list[bool] = []
        recs = audit_plan_until_stable(
            parse_plan(plan_path),
            plan_path,
            repo_root=tmp_path,
            invoker=lambda prompt: (
                resumed_prompts.append(prompt) or (0, self._sections("first-gap"))
            ),
            max_passes=3,
            dry_rounds=1,
            resumed_out=resumed,
        )

        assert initial_calls == 3
        assert len(resumed_prompts) == 1
        assert "[first-gap]" in resumed_prompts[0]
        assert "[second-gap]" in resumed_prompts[0]
        assert [rec.body for rec in recs] == [
            "gap about first-gap",
            "gap about second-gap",
        ]
        assert resumed == [True]

    def test_interrupted_inflight_pass_is_retried_not_counted(
        self, tmp_path: Path
    ) -> None:
        """Retry an interrupted call from the published boundary without its output."""
        from plan_tool.parser import parse_plan
        from plan_tool.review import audit_plan_until_stable

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        calls = 0

        def interrupted_invoker(_prompt: str):
            nonlocal calls
            calls += 1
            if calls == 1:
                return (0, self._sections("durable-gap"))
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            audit_plan_until_stable(
                plan,
                plan_path,
                repo_root=tmp_path,
                invoker=interrupted_invoker,
                max_passes=3,
                dry_rounds=1,
            )

        resumed_prompts: list[str] = []
        audit_plan_until_stable(
            parse_plan(plan_path),
            plan_path,
            repo_root=tmp_path,
            invoker=lambda prompt: (
                resumed_prompts.append(prompt) or (0, self._sections("retried-gap"))
            ),
            max_passes=3,
            dry_rounds=1,
        )

        assert len(resumed_prompts) == 2
        assert "[durable-gap]" in resumed_prompts[0]
        assert "[retried-gap]" not in resumed_prompts[0]
        assert "[retried-gap]" in resumed_prompts[1]

    def test_resume_restores_union_counters_observations_and_calibration(
        self, tmp_path: Path
    ) -> None:
        """A resumed durable prefix has the same observable result as one run."""
        from plan_tool.parser import parse_plan
        from plan_tool.review import audit_plan_until_stable

        uninterrupted_root = tmp_path / "uninterrupted"
        resumed_root = tmp_path / "resumed"
        uninterrupted_root.mkdir()
        resumed_root.mkdir()
        uninterrupted_path = self._write_plan(uninterrupted_root)
        resumed_path = self._write_plan(resumed_root)

        replies = ["first-gap", "second-gap", "first-gap"]

        def run_sequence(plan_path: Path, replies: list[str], **kwargs):
            return audit_plan_until_stable(
                parse_plan(plan_path), plan_path, repo_root=plan_path.parent,
                invoker=lambda _prompt: (0, self._sections(replies.pop(0))),
                max_passes=3, dry_rounds=2, **kwargs,
            )

        whole_budget: dict = {}
        whole_advisory: list = []
        whole = run_sequence(
            uninterrupted_path, replies.copy(), budget_report=whole_budget,
            advisory_out=whole_advisory,
        )

        prefix = replies.copy()

        def interrupted_invoker(_prompt: str):
            if len(prefix) == 1:
                raise KeyboardInterrupt
            return (0, self._sections(prefix.pop(0)))

        with pytest.raises(KeyboardInterrupt):
            audit_plan_until_stable(
                parse_plan(resumed_path), resumed_path, repo_root=resumed_root,
                invoker=interrupted_invoker, max_passes=3, dry_rounds=2,
            )

        resumed_budget: dict = {}
        resumed_advisory: list = []
        resumed = run_sequence(
            resumed_path, prefix, budget_report=resumed_budget,
            advisory_out=resumed_advisory,
        )

        assert resumed == whole
        assert resumed_budget == whole_budget
        assert resumed_advisory == whole_advisory

    def test_sampler_checkpoint_identity_mismatch_starts_fresh(
        self, tmp_path: Path
    ) -> None:
        """Reject changed sampler inputs instead of carrying old findings."""
        from plan_tool.parser import parse_plan
        from plan_tool.review import audit_plan_until_stable

        plan_path = self._write_plan(tmp_path)
        calls = 0

        def interrupted_invoker(_prompt: str):
            nonlocal calls
            calls += 1
            if calls == 1:
                return (0, self._sections("old-gap"))
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            audit_plan_until_stable(
                parse_plan(plan_path),
                plan_path,
                repo_root=tmp_path,
                invoker=interrupted_invoker,
                max_passes=3,
                dry_rounds=1,
            )

        fresh_prompts: list[str] = []
        log = io.StringIO()
        audit_plan_until_stable(
            parse_plan(plan_path),
            plan_path,
            repo_root=tmp_path,
            invoker=lambda prompt: (
                fresh_prompts.append(prompt) or (0, self._sections("fresh-gap"))
            ),
            max_passes=3,
            dry_rounds=2,
            log_file=log,
        )

        assert len(fresh_prompts) == 3
        assert "[old-gap]" not in fresh_prompts[0]
        assert "identity mismatch" in log.getvalue()

    @pytest.mark.parametrize(
        "field",
        [
            "audit_input_fingerprint",
            "max_passes",
            "dry_rounds",
            "new_threshold",
            "backend_name",
            "resolved_model",
            "code_fingerprint",
        ],
    )
    def test_each_sampler_identity_component_declines_a_checkpoint(
        self, tmp_path: Path, field: str
    ) -> None:
        """Every persisted identity component participates in the resume gate."""
        from plan_tool.parser import parse_plan
        from plan_tool import review as review_module
        from plan_tool.review_persistence import load_sampler_checkpoint

        plan_path = self._write_plan(tmp_path)
        calls = 0

        def interrupted_invoker(_prompt: str):
            nonlocal calls
            calls += 1
            if calls == 1:
                return (0, self._sections("durable-gap"))
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            review_module.audit_plan_until_stable(
                parse_plan(plan_path), plan_path, repo_root=tmp_path,
                invoker=interrupted_invoker, max_passes=3,
            )

        checkpoint = load_sampler_checkpoint(plan_path)
        assert checkpoint.review is not None
        assert checkpoint.review.sampler_state is not None
        identity = dict(checkpoint.review.sampler_state["identity"])
        code_fingerprint = dict(checkpoint.review.code_fingerprint or {})
        if field == "code_fingerprint":
            code_fingerprint["plan_tool/review.py"] = "different"
        elif isinstance(identity[field], int):
            identity[field] += 1
        else:
            identity[field] = "different"

        restored, outcome = review_module._restore_sampler_checkpoint_state(
            checkpoint.review,
            expected_identity=identity,
            expected_code_fingerprint=code_fingerprint,
        )

        assert restored is None
        assert outcome == "identity-mismatch"

    @pytest.mark.parametrize("missing_key", ["early_stop_reason", "terminal_reason"])
    def test_checkpoint_missing_stop_reason_key_declines_without_raising(
        self, tmp_path: Path, missing_key: str
    ) -> None:
        """A well-formed-but-truncated checkpoint fails closed, never KeyErrors."""
        import dataclasses

        from plan_tool.parser import parse_plan
        from plan_tool import review as review_module
        from plan_tool.review_persistence import load_sampler_checkpoint

        plan_path = self._write_plan(tmp_path)
        calls = 0

        def interrupted_invoker(_prompt: str):
            nonlocal calls
            calls += 1
            if calls == 1:
                return (0, self._sections("durable-gap"))
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            review_module.audit_plan_until_stable(
                parse_plan(plan_path), plan_path, repo_root=tmp_path,
                invoker=interrupted_invoker, max_passes=3,
            )

        checkpoint = load_sampler_checkpoint(plan_path)
        assert checkpoint.review is not None
        assert checkpoint.review.sampler_state is not None
        truncated_state = dict(checkpoint.review.sampler_state)
        del truncated_state[missing_key]
        truncated_review = dataclasses.replace(
            checkpoint.review, sampler_state=truncated_state
        )

        restored, outcome = review_module._restore_sampler_checkpoint_state(
            truncated_review,
            expected_identity=truncated_state["identity"],
            expected_code_fingerprint=dict(checkpoint.review.code_fingerprint or {}),
        )

        assert restored is None
        assert outcome == "malformed"

    def test_checkpoint_with_boolean_next_pass_declines_as_malformed(
        self, tmp_path: Path
    ) -> None:
        """``next_pass`` is int-typed like every sibling counter — a JSON
        ``true`` (== 1 under Python equality) must not slip past this
        specific check where every other counter field rejects bools."""
        import dataclasses

        from plan_tool.parser import parse_plan
        from plan_tool import review as review_module
        from plan_tool.review_persistence import load_sampler_checkpoint

        plan_path = self._write_plan(tmp_path)
        calls = 0

        def interrupted_invoker(_prompt: str):
            nonlocal calls
            calls += 1
            if calls == 1:
                return (0, self._sections("durable-gap"))
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            review_module.audit_plan_until_stable(
                parse_plan(plan_path), plan_path, repo_root=tmp_path,
                invoker=interrupted_invoker, max_passes=3,
            )

        checkpoint = load_sampler_checkpoint(plan_path)
        assert checkpoint.review is not None
        assert checkpoint.review.sampler_state is not None
        tampered_state = dict(checkpoint.review.sampler_state)
        # Reset the pass-count fields consistently so "next_pass == passes + 1"
        # is the *only* thing at stake: True == 1 == 0 + 1 under Python
        # equality, so a checkpoint with passes=0 is exactly where a bool
        # would slip through the buggy comparison.
        tampered_state["passes"] = 0
        tampered_state["conforming_pass_count"] = 0
        tampered_state["failed_or_malformed_pass_count"] = 0
        tampered_state["observations_by_id"] = {}
        tampered_state["next_pass"] = True  # equals 1, must not pass as an int
        tampered_review = dataclasses.replace(
            checkpoint.review, sampler_state=tampered_state
        )

        restored, outcome = review_module._restore_sampler_checkpoint_state(
            tampered_review,
            expected_identity=tampered_state["identity"],
            expected_code_fingerprint=dict(checkpoint.review.code_fingerprint or {}),
        )

        assert restored is None
        assert outcome == "malformed"

    def test_malformed_sampler_checkpoint_starts_fresh_without_raising(
        self, tmp_path: Path
    ) -> None:
        """Fail closed when the stable sampler artifact cannot be decoded."""
        from plan_tool.parser import parse_plan
        from plan_tool.review import audit_plan_until_stable
        from plan_tool.review_persistence import sampler_checkpoint_path

        plan_path = self._write_plan(tmp_path)
        checkpoint_path = sampler_checkpoint_path(plan_path)
        checkpoint_path.parent.mkdir(parents=True)
        checkpoint_path.write_text("{truncated", encoding="utf-8")
        prompts: list[str] = []
        log = io.StringIO()

        audit_plan_until_stable(
            parse_plan(plan_path),
            plan_path,
            repo_root=tmp_path,
            invoker=lambda prompt: (
                prompts.append(prompt) or (0, self._sections("fresh-gap"))
            ),
            max_passes=1,
            log_file=log,
        )

        assert len(prompts) == 1
        assert "malformed" in log.getvalue()

    def test_terminal_sampler_residue_starts_a_fresh_sampler(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A retained terminal artifact is diagnostic, never a resume boundary."""
        from plan_tool import review as review_module
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        monkeypatch.setattr(
            review_module,
            "_remove_sampler_checkpoint",
            lambda _path: (_ for _ in ()).throw(OSError("retain residue")),
        )
        review_module.audit_plan_until_stable(
            parse_plan(plan_path), plan_path, repo_root=tmp_path,
            invoker=lambda _prompt: (0, self._sections("old-gap")),
            max_passes=3, dry_rounds=1,
        )

        prompts: list[str] = []
        resumed: list[bool] = []
        log = io.StringIO()
        review_module.audit_plan_until_stable(
            parse_plan(plan_path), plan_path, repo_root=tmp_path,
            invoker=lambda prompt: (
                prompts.append(prompt) or (0, self._sections("fresh-gap"))
            ),
            max_passes=1, log_file=log, resumed_out=resumed,
        )

        assert len(prompts) == 1
        assert "[old-gap]" not in prompts[0]
        assert resumed == [False]
        assert "not resumable" in log.getvalue()

    def test_matching_resume_emits_checkpoint_hit_when_run_logger_is_present(
        self, tmp_path: Path
    ) -> None:
        """Record exactly one existing checkpoint hit before resumed sampling."""
        from plan_tool import review as review_module
        from plan_tool.parser import parse_plan

        class RunLogger:
            def __init__(self) -> None:
                self.hits: list[tuple[object, ...]] = []

            def audit_pass_end(self, **_kwargs) -> None:
                pass

            def bind_shell_sink(self, **_kwargs):
                return review_module.contextlib.nullcontext()

            def checkpoint_hit(self, *args) -> None:
                self.hits.append(args)

            def checkpoint_save(self, *_args) -> None:
                pass

            def checkpoint_discard(self, *_args) -> None:
                pass

        plan_path = self._write_plan(tmp_path)
        log = io.StringIO()
        calls = 0

        def interrupted_invoker(_prompt: str):
            nonlocal calls
            calls += 1
            if calls == 1:
                return (0, self._sections("durable-gap"))
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            review_module.audit_plan_until_stable(
                parse_plan(plan_path),
                plan_path,
                repo_root=tmp_path,
                invoker=interrupted_invoker,
                max_passes=3,
            )

        logger = RunLogger()
        review_module.audit_plan_until_stable(
            parse_plan(plan_path),
            plan_path,
            repo_root=tmp_path,
            invoker=lambda _prompt: (0, self._sections("durable-gap")),
            max_passes=3,
            run_logger=logger,
            log_file=log,
        )

        assert len(logger.hits) == 1
        assert logger.hits[0][0] == review_module._SAMPLER_CHECKPOINT_NAME
        assert "resuming sampler at pass 2/3 with 1 carried finding(s)" in log.getvalue()

    def test_declined_sampler_checkpoint_emits_no_hit_and_names_the_decline(
        self, tmp_path: Path
    ) -> None:
        """Only an accepted checkpoint produces run-log resume provenance."""
        from plan_tool import review as review_module
        from plan_tool.parser import parse_plan

        class RunLogger:
            def __init__(self) -> None:
                self.hits: list[tuple[object, ...]] = []

            def audit_pass_end(self, **_kwargs) -> None:
                pass

            def bind_shell_sink(self, **_kwargs):
                return review_module.contextlib.nullcontext()

            def checkpoint_hit(self, *args) -> None:
                self.hits.append(args)

            def checkpoint_save(self, *_args) -> None:
                pass

            def checkpoint_discard(self, *_args) -> None:
                pass

        plan_path = self._write_plan(tmp_path)
        calls = 0

        def interrupted_invoker(_prompt: str):
            nonlocal calls
            calls += 1
            if calls == 1:
                return (0, self._sections("durable-gap"))
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            review_module.audit_plan_until_stable(
                parse_plan(plan_path), plan_path, repo_root=tmp_path,
                invoker=interrupted_invoker, max_passes=3,
            )

        logger = RunLogger()
        log = io.StringIO()
        review_module.audit_plan_until_stable(
            parse_plan(plan_path), plan_path, repo_root=tmp_path,
            invoker=lambda _prompt: (0, self._sections("fresh-gap")),
            max_passes=3, dry_rounds=2, run_logger=logger, log_file=log,
        )

        assert logger.hits == []
        assert "identity mismatch — starting fresh at pass 1" in log.getvalue()

    @pytest.mark.parametrize("terminal_path", ["dry", "cap", "plan-quota"])
    def test_terminal_paths_skip_resumable_checkpoint_replacement(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, terminal_path: str,
    ) -> None:
        from plan_tool import review as review_module
        from plan_tool.claude_errors import ClaudeFailureKind
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        published_states: list[dict[str, object]] = []
        real_save = review_module._save_sampler_checkpoint

        def record_save(**kwargs):
            published_states.append(dict(kwargs["sampler_state"]))
            return real_save(**kwargs)

        monkeypatch.setattr(review_module, "_save_sampler_checkpoint", record_save)
        calls = 0

        def invoker(_prompt: str):
            nonlocal calls
            calls += 1
            if calls == 1:
                return (0, self._sections("first-gap"))
            if terminal_path == "plan-quota":
                return review_module._PlanAuditInvocation(
                    1, "quota", ClaudeFailureKind.PLAN_QUOTA
                )
            if terminal_path == "dry":
                return (0, self._sections("first-gap"))
            return (0, self._sections("second-gap"))

        review_module.audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=2, dry_rounds=1,
        )

        assert [state["lifecycle"] for state in published_states] == [
            "in-progress", "terminal-residue"
        ]
        assert published_states[0]["passes"] == 1
        assert published_states[1]["passes"] == 2

    def test_continuing_save_value_error_is_nonfatal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """save_review's own internal-consistency checks raise ValueError,
        not OSError — that must degrade the same best-effort way a write
        failure does, never crashing the audit and losing an
        already-completed pass's real findings."""
        from plan_tool import review as review_module
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)

        def fail_save(**_kwargs):
            raise ValueError("forced validation failure")

        monkeypatch.setattr(review_module, "_save_sampler_checkpoint", fail_save)
        log = io.StringIO()

        result = review_module.audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _prompt: (0, self._sections("gap")),
            max_passes=3, dry_rounds=1, log_file=log,
        )

        assert len(result) == 1
        assert "failed to save sampler checkpoint" in log.getvalue()

    def test_terminal_transition_value_error_is_nonfatal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The terminal-transition write is subject to the same ValueError
        exposure as the continuing save — must degrade the same way."""
        from plan_tool import review as review_module
        from plan_tool.parser import parse_plan

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        real_save = review_module._save_sampler_checkpoint

        def fail_terminal_transition(**kwargs):
            if kwargs["sampler_state"]["lifecycle"] == "terminal-residue":
                raise ValueError("forced validation failure")
            return real_save(**kwargs)

        monkeypatch.setattr(
            review_module, "_save_sampler_checkpoint", fail_terminal_transition
        )
        log = io.StringIO()

        result = review_module.audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _prompt: (0, self._sections("gap")),
            max_passes=3, dry_rounds=1, log_file=log,
        )

        assert len(result) == 1
        assert "terminal sampler checkpoint" in log.getvalue()

    def test_terminal_transition_before_publication_preserves_prior_boundary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool import review as review_module
        from plan_tool.parser import parse_plan
        from plan_tool.review_persistence import load_sampler_checkpoint

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        real_save = review_module._save_sampler_checkpoint

        def fail_terminal_transition(**kwargs):
            if kwargs["sampler_state"]["lifecycle"] == "terminal-residue":
                raise OSError("not published")
            return real_save(**kwargs)

        monkeypatch.setattr(
            review_module, "_save_sampler_checkpoint", fail_terminal_transition
        )
        review_module.audit_plan_until_stable(
            plan,
            plan_path,
            repo_root=tmp_path,
            invoker=lambda _prompt: (0, self._sections("gap")),
            max_passes=3,
            dry_rounds=1,
        )

        checkpoint = load_sampler_checkpoint(plan_path)
        assert checkpoint.status == "valid"
        assert checkpoint.review is not None
        assert checkpoint.review.is_in_progress_sampler_checkpoint
        assert checkpoint.review.sampler_state is not None
        assert checkpoint.review.sampler_state["passes"] == 1

    def test_code_fingerprint_failure_is_logged_not_silent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A code-fingerprint failure (e.g. a step's declared file escaping
        repo_root) must not be indistinguishable from ordinary code drift —
        it gets its own diagnostic, not just a later generic
        "identity mismatch" on the next resume attempt."""
        import plan_tool.fingerprint as fingerprint_module
        from plan_tool import review as review_module
        from plan_tool.parser import parse_plan
        from plan_tool.review_persistence import AuditInputSnapshot

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)

        def fail_fingerprint(*_args, **_kwargs):
            raise ValueError("'../escape.py' is not in the subpath of repo_root")

        monkeypatch.setattr(
            fingerprint_module, "compute_code_fingerprint", fail_fingerprint
        )
        log = io.StringIO()
        snapshot = AuditInputSnapshot.capture(plan_path, tmp_path)

        review_module.audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _prompt: (0, self._sections("gap")),
            max_passes=1, dry_rounds=1, log_file=log,
            audit_input_snapshot=snapshot,
        )

        assert "failed to compute the declared code fingerprint" in log.getvalue()

    def test_terminal_transition_attempted_when_existence_check_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A failed existence check must not read as "no checkpoint": an
        unattempted transition would leave a real in-progress checkpoint on
        disk for a later, unrelated invocation to wrongly resume. Logged and
        non-fatal, like every sibling filesystem call in this block, but the
        transition is attempted regardless rather than skipped."""
        from plan_tool import review as review_module
        from plan_tool.parser import parse_plan
        from plan_tool.review_persistence import (
            load_sampler_checkpoint,
            sampler_checkpoint_path,
        )

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        calls = 0

        def interrupted_invoker(_prompt: str):
            nonlocal calls
            calls += 1
            if calls == 1:
                return (0, self._sections("gap"))
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            review_module.audit_plan_until_stable(
                parse_plan(plan_path), plan_path, repo_root=tmp_path,
                invoker=interrupted_invoker, max_passes=3, dry_rounds=1,
            )
        checkpoint = load_sampler_checkpoint(plan_path)
        assert checkpoint.review is not None
        assert checkpoint.review.is_in_progress_sampler_checkpoint

        checkpoint_path = sampler_checkpoint_path(plan_path)
        real_exists = Path.exists

        def flaky_exists(self: Path) -> bool:
            if self == checkpoint_path:
                raise OSError("permission denied")
            return real_exists(self)

        monkeypatch.setattr(Path, "exists", flaky_exists)
        log = io.StringIO()

        result = review_module.audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path,
            invoker=lambda _prompt: (0, self._sections("gap")),
            max_passes=3, dry_rounds=1, log_file=log,
        )
        monkeypatch.setattr(Path, "exists", real_exists)

        assert len(result) == 1
        assert "failed to check for a sampler checkpoint" in log.getvalue()
        assert "attempting the terminal transition anyway" in log.getvalue()
        # The real leftover checkpoint from the first run must still be
        # transitioned away, not left resumable by a later invocation.
        after = load_sampler_checkpoint(plan_path)
        assert after.review is None or not after.review.is_in_progress_sampler_checkpoint

    def test_terminal_transition_after_publication_leaves_no_resumable_prefix(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool import review as review_module
        from plan_tool.parser import parse_plan
        from plan_tool.review_persistence import load_sampler_checkpoint

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        real_save = review_module._save_sampler_checkpoint

        def publish_then_report_error(**kwargs):
            path = real_save(**kwargs)
            if kwargs["sampler_state"]["lifecycle"] == "terminal-residue":
                raise OSError("published before fsync failed")
            return path

        monkeypatch.setattr(
            review_module, "_save_sampler_checkpoint", publish_then_report_error
        )
        monkeypatch.setattr(
            review_module,
            "_remove_sampler_checkpoint",
            lambda _path: (_ for _ in ()).throw(OSError("cleanup failed")),
        )
        review_module.audit_plan_until_stable(
            plan,
            plan_path,
            repo_root=tmp_path,
            invoker=lambda _prompt: (0, self._sections("gap")),
            max_passes=3,
            dry_rounds=1,
        )

        checkpoint = load_sampler_checkpoint(plan_path)
        assert checkpoint.status == "valid"
        assert checkpoint.review is not None
        assert checkpoint.review.sampler_state is not None
        assert checkpoint.review.sampler_state["lifecycle"] == "terminal-residue"
        assert not checkpoint.review.is_in_progress_sampler_checkpoint

    def test_terminal_cleanup_error_is_nonfatal_after_nonresumable_transition(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool import review as review_module
        from plan_tool.parser import parse_plan
        from plan_tool.review_persistence import load_sampler_checkpoint

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        monkeypatch.setattr(
            review_module,
            "_remove_sampler_checkpoint",
            lambda _path: (_ for _ in ()).throw(OSError("cleanup failed")),
        )
        log = io.StringIO()
        recs = review_module.audit_plan_until_stable(
            plan,
            plan_path,
            repo_root=tmp_path,
            invoker=lambda _prompt: (0, self._sections("gap")),
            max_passes=3,
            dry_rounds=1,
            log_file=log,
        )

        checkpoint = load_sampler_checkpoint(plan_path)
        assert [rec.body for rec in recs] == ["gap about gap"]
        assert checkpoint.review is not None
        assert checkpoint.review.sampler_state is not None
        assert checkpoint.review.sampler_state["lifecycle"] == "terminal-residue"
        assert "failed to discard terminal sampler checkpoint" in log.getvalue()

    def test_sampler_checkpoint_events_use_existing_run_logger_methods(
        self, tmp_path: Path
    ) -> None:
        from plan_tool import review as review_module
        from plan_tool.parser import parse_plan

        class RunLogger:
            def __init__(self) -> None:
                self.saves: list[tuple[object, ...]] = []
                self.discards: list[tuple[object, ...]] = []
                self.starts: list[dict[str, object]] = []
                self.pass_ends: list[dict[str, object]] = []

            def claude_call_start(self, **kwargs) -> None:
                self.starts.append(kwargs)

            def audit_pass_end(self, **kwargs) -> None:
                self.pass_ends.append(kwargs)

            def bind_shell_sink(self, **_kwargs):
                return review_module.contextlib.nullcontext()

            def checkpoint_save(self, *args) -> None:
                self.saves.append(args)

            def checkpoint_discard(self, *args) -> None:
                self.discards.append(args)

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        logger = RunLogger()
        calls = 0

        def invoker(_prompt: str):
            nonlocal calls
            calls += 1
            return (0, self._sections("gap"))

        review_module.audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=3, dry_rounds=1, run_logger=logger,
        )

        assert calls == 2
        # Production reporters carry no run log, so each plan_audit call writes
        # its own start: attempt = pass number (matches the bound sink), hash only.
        assert [(e["phase"], e["attempt"]) for e in logger.starts] == [
            ("plan_audit", 1),
            ("plan_audit", 2),
        ]
        assert all(len(e["prompt_sha256"]) == 64 for e in logger.starts)
        # Per-pass yield (the saved report keeps only the final union): pass 1
        # adds the finding, pass 2 adds none, and carried ids are not re-counted.
        assert [
            (e["pass_number"], e["outcome"], len(e["new_ids"]), e["unique_so_far"])
            for e in logger.pass_ends
        ] == [(1, "conforming", 1, 1), (2, "conforming", 0, 1)]
        assert logger.saves
        assert logger.discards == [
            (review_module._SAMPLER_CHECKPOINT_NAME, "terminal")
        ]


class TestPlanQuotaConceptualAudit:
    """A typed plan quota stops only the current conceptual audit."""

    _write_plan = TestCheckPlanAudit._write_plan
    _sections = staticmethod(TestAuditPlanUntilStable._sections)

    def test_plan_quota_stops_conceptual_sampling_after_terminal_pass(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.claude_errors import ClaudeFailureKind
        from plan_tool.parser import parse_plan
        from plan_tool.review import _PlanAuditInvocation, audit_plan_until_stable

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        calls: list[str] = []

        def invoker(prompt: str):
            calls.append(prompt)
            return _PlanAuditInvocation(
                1, "monthly plan quota", ClaudeFailureKind.PLAN_QUOTA
            )

        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=3, dry_rounds=1,
        )

        assert len(calls) == 1

    def test_plan_audit_adapter_preserves_terminal_signal_through_wrappers(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import review as review_module
        from plan_tool.claude_errors import ClaudeFailure, ClaudeFailureKind
        from plan_tool.parser import parse_plan
        from plan_tool.progress import NullReporter
        from plan_tool.shell import ClaudeInvokeOutcome

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        monkeypatch.setattr(
            review_module,
            "claude_invoke_outcome",
            lambda _prompt: ClaudeInvokeOutcome(
                1,
                "quota",
                ClaudeFailure(ClaudeFailureKind.PLAN_QUOTA),
            ),
        )
        budget: dict = {}
        import functools

        @functools.wraps(review_module.shell_review_invoker)
        def wrapped_invoker(prompt: str):
            return review_module.shell_review_invoker(prompt)

        review_module.audit_plan_until_stable(
            plan,
            plan_path,
            repo_root=tmp_path,
            invoker=review_module.plan_audit_invoker_from_review_invoker(
                wrapped_invoker
            ),
            reporter=NullReporter(),
            max_passes=3,
            budget_report=budget,
        )

        assert budget["early_stop_reason"] == "plan-quota"
        assert budget["passes_used"] == 1

    def test_plan_audit_adapter_ignores_mock_without_typed_capability(self) -> None:
        from unittest.mock import Mock

        from plan_tool.review import plan_audit_invoker_from_review_invoker

        invoker = Mock()
        assert plan_audit_invoker_from_review_invoker(invoker) is invoker

    def test_standard_review_invoker_remains_tuple_based(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import review as review_module

        monkeypatch.setattr(
            review_module, "claude_invoke", lambda _prompt: (0, "review text")
        )
        assert review_module.shell_review_invoker("prompt") == (0, "review text")

    def test_plan_quota_coverage_uses_actual_pass_count(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.claude_errors import ClaudeFailureKind
        from plan_tool.parser import parse_plan
        from plan_tool.review import _PlanAuditInvocation, audit_plan_until_stable

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        calls = 0

        def invoker(_prompt: str):
            nonlocal calls
            calls += 1
            if calls == 1:
                return (0, self._sections("first-gap"))
            return _PlanAuditInvocation(1, "quota", ClaudeFailureKind.PLAN_QUOTA)

        budget: dict = {}
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=5, dry_rounds=1, budget_report=budget,
        )

        assert budget == {
            "budget_limited": False,
            "passes_used": 2,
            "cap": 5,
            "recommendation_kind": None,
            "recommended_passes": None,
            "recommendation_advice": None,
            "confirmation_kind": None,
            "conforming_pass_count": 1,
            "failed_or_malformed_pass_count": 1,
            "early_stop_reason": "plan-quota",
        }

    def test_nonquota_failed_pass_remains_neutral(self, tmp_path: Path) -> None:
        from plan_tool.parser import parse_plan
        from plan_tool.review import audit_plan_until_stable

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        responses = [
            (1, "ordinary failure"),
            (0, self._sections("gap")),
            (0, self._sections("gap")),
        ]
        calls = 0

        def invoker(_prompt: str):
            nonlocal calls
            response = responses[calls]
            calls += 1
            return response

        budget: dict = {}
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=3, dry_rounds=1, budget_report=budget,
        )

        assert calls == 3
        assert budget["early_stop_reason"] is None
        assert budget["failed_or_malformed_pass_count"] == 1

    def test_plan_quota_state_does_not_cross_audit_invocations(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.claude_errors import ClaudeFailureKind
        from plan_tool.parser import parse_plan
        from plan_tool.review import _PlanAuditInvocation, audit_plan_until_stable

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        audit_plan_until_stable(
            plan,
            plan_path,
            repo_root=tmp_path,
            invoker=lambda _prompt: _PlanAuditInvocation(
                1, "quota", ClaudeFailureKind.PLAN_QUOTA
            ),
            max_passes=3,
        )
        calls: list[str] = []

        def next_invoker(prompt: str):
            calls.append(prompt)
            return (0, self._sections("fresh-call"))

        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=next_invoker,
            max_passes=1,
        )

        assert len(calls) == 1


class TestAuditPromptIntentBlock:
    """``_format_intent_block`` + ``${intent_block}`` in the audit prompt.

    Every new word lives in the dynamic block: an intent-free plan keeps the
    same prompt it had before this step; placeholders omit the same way.
    """

    def _plan(
        self,
        *,
        plan_intent: Optional[str] = None,
        steps: Optional[list[tuple[int, str, Optional[str]]]] = None,
    ) -> Plan:
        if steps is None:
            steps = [(1, "build the thing", None)]
        return Plan(
            title="Audit Plan",
            status=PlanStatus.IN_PROGRESS,
            priority=Priority.MEDIUM,
            intent=plan_intent,
            steps=[
                Step(id=sid, title=title, intent=intent)
                for sid, title, intent in steps
            ],
        )

    def _write_plan(
        self,
        tmp_path: Path,
        *,
        body: str = _FULL_BODY_SECTIONS,
        plan_intent: Optional[str] = None,
        step_intent: Optional[str] = None,
        extra_steps: Optional[list[tuple[int, str, Optional[str]]]] = None,
    ) -> Path:
        plan_path = tmp_path / "audit-intent-plan.md"

        def _yaml_str(value: str) -> str:
            if any(ch in value for ch in (":", "#", '"', "'", "\n", "$", "{", "}")):
                escaped = value.replace("'", "''")
                return f"'{escaped}'"
            return value

        step_lines = [
            "  - id: 1\n"
            "    title: build the thing\n"
            "    status: pending\n"
        ]
        if step_intent is not None:
            step_lines.append(f"    intent: {_yaml_str(step_intent)}\n")
        for sid, title, intent in extra_steps or ():
            step_lines.append(
                f"  - id: {sid}\n"
                f"    title: {title}\n"
                f"    status: pending\n"
            )
            if intent is not None:
                step_lines.append(f"    intent: {_yaml_str(intent)}\n")
        plan_intent_yaml = ""
        if plan_intent is not None:
            plan_intent_yaml = f"intent: {_yaml_str(plan_intent)}\n"
        plan_path.write_text(
            "---\n"
            "title: Audit Plan\n"
            f"{plan_intent_yaml}"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            + "".join(step_lines)
            + "---\n"
            "\n"
            f"{body}",
            encoding="utf-8",
        )
        return plan_path

    def test_intent_block_is_empty_when_no_intent_is_set(self) -> None:
        assert _format_intent_block(self._plan()) == ""

    @pytest.mark.parametrize("value", ["", "   ", "\t\n"])
    def test_intent_block_is_empty_for_blank_and_whitespace_values(
        self, value: str
    ) -> None:
        assert (
            _format_intent_block(
                self._plan(
                    plan_intent=value,
                    steps=[(1, "build the thing", value)],
                )
            )
            == ""
        )

    @pytest.mark.parametrize("value", ["TODO", "_(TODO)_", "(TODO)"])
    def test_intent_block_is_empty_for_placeholder_values(
        self, value: str
    ) -> None:
        assert (
            _format_intent_block(
                self._plan(
                    plan_intent=value,
                    steps=[(1, "build the thing", value)],
                )
            )
            == ""
        )

    def test_intent_block_omits_a_tbd_intent(self) -> None:
        # ``check_intent_presence`` reports a ``TBD`` intent missing; the audit
        # block must not then hand the auditor "TBD" as the stated why. The two
        # predicates share ``is_placeholder_intent`` so they cannot disagree.
        block = _format_intent_block(
            self._plan(
                plan_intent="TBD",
                steps=[(1, "build the thing", "TBD")],
            )
        )
        assert "TBD" not in block

    def test_intent_block_renders_the_plan_intent(self) -> None:
        block = _format_intent_block(
            self._plan(plan_intent="Ship the audit intent delivery")
        )
        assert "Plan intent: Ship the audit intent delivery" in block

    def test_intent_block_renders_each_step_intent_with_id_and_title(
        self,
    ) -> None:
        block = _format_intent_block(
            self._plan(
                steps=[
                    (1, "First step", "do the first thing"),
                    (2, "Second step", "do the second thing"),
                    (3, "Third step", "do the third thing"),
                ]
            )
        )
        first = block.index("step 1 (First step): do the first thing")
        second = block.index("step 2 (Second step): do the second thing")
        third = block.index("step 3 (Third step): do the third thing")
        assert first < second < third

    def test_intent_block_skips_steps_with_no_intent(self) -> None:
        block = _format_intent_block(
            self._plan(
                steps=[
                    (1, "No intent", None),
                    (2, "Has intent", "only this one"),
                    (3, "Placeholder", "TODO"),
                ]
            )
        )
        assert "step 2 (Has intent): only this one" in block
        assert "step 1" not in block
        assert "step 3" not in block

    def test_intent_block_renders_with_only_a_plan_intent(self) -> None:
        block = _format_intent_block(
            self._plan(plan_intent="Plan purpose only")
        )
        assert block
        assert "Plan intent: Plan purpose only" in block
        assert "step 1" not in block

    def test_intent_block_renders_with_only_step_intents(self) -> None:
        block = _format_intent_block(
            self._plan(
                steps=[(1, "Only step", "step purpose only")],
            )
        )
        assert block
        assert "Plan intent:" not in block
        assert "step 1 (Only step): step purpose only" in block

    def test_intent_block_collapses_a_multi_line_intent_to_one_line(
        self,
    ) -> None:
        block = _format_intent_block(
            self._plan(
                plan_intent="first line\n## forged heading\nthird",
            )
        )
        assert "\n" not in block.split("Plan intent: ", 1)[1].split("\n", 1)[0]
        assert "## forged heading" not in block.splitlines()
        assert "first line ## forged heading third" in block

    def test_prompt_carries_the_plan_and_step_intent(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.parser import parse_plan
        from plan_tool.review import render_plan_audit_prompt

        plan_path = self._write_plan(
            tmp_path,
            plan_intent="Deliver intents to the audit",
            step_intent="Format the intent block",
        )
        plan = parse_plan(plan_path)
        prompt = render_plan_audit_prompt(plan, plan_path, repo_root=tmp_path)
        assert prompt is not None
        assert "Deliver intents to the audit" in prompt
        assert "Format the intent block" in prompt

    def test_prompt_places_the_intent_block_before_the_plan_body(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.parser import parse_plan
        from plan_tool.review import render_plan_audit_prompt

        plan_path = self._write_plan(
            tmp_path, plan_intent="Purpose before body"
        )
        plan = parse_plan(plan_path)
        prompt = render_plan_audit_prompt(plan, plan_path, repo_root=tmp_path)
        assert prompt is not None
        assert prompt.index("Purpose before body") < prompt.index(
            "## Plan body"
        )

    def test_prompt_embeds_confirmed_project_context(self, tmp_path: Path) -> None:
        from plan_tool.project_profile import initialize_project_profile
        from plan_tool.review import render_plan_audit_prompt

        initialize_project_profile(
            tmp_path,
            intent="Keep the audit focused on user value.",
            non_goals=("Do not add a service.",),
            decisions=("Prefer reversible changes.",),
        )
        plan_path = self._write_plan(tmp_path)
        prompt = render_plan_audit_prompt(
            parse_plan(plan_path), plan_path, repo_root=tmp_path
        )

        assert prompt is not None
        assert "Keep the audit focused on user value." in prompt
        assert "Do not add a service." in prompt
        assert "Prefer reversible changes." in prompt
        assert prompt.index("Confirmed project context") < prompt.index("## Plan body")

    def test_project_context_follows_a_carried_plan_body_marker(
        self, tmp_path: Path
    ) -> None:
        """A carried excerpt cannot become the insertion target."""
        from plan_tool.project_profile import initialize_project_profile
        from plan_tool.review import render_plan_audit_prompt

        initialize_project_profile(tmp_path, intent="Keep the audit narrow.")
        plan_path = self._write_plan(tmp_path)
        prompt = render_plan_audit_prompt(
            parse_plan(plan_path),
            plan_path,
            repo_root=tmp_path,
            carried_findings=[
                CarriedFinding(
                    anchor="quoted-heading",
                    title="quoted ## Plan body marker",
                    severity="medium",
                    body_excerpt="The finding carries a literal heading marker.",
                )
            ],
        )

        assert prompt is not None
        carried_marker = prompt.index("quoted ## Plan body marker")
        context_marker = prompt.index("## Confirmed project context")
        plan_body_marker = prompt.rindex("## Plan body")
        assert carried_marker < context_marker < plan_body_marker

    def test_project_context_invalidates_the_audit_snapshot(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.project_profile import initialize_project_profile
        from plan_tool.review_persistence import AuditInputSnapshot

        plan_path = self._write_plan(tmp_path)
        before = AuditInputSnapshot.capture(plan_path, tmp_path)
        initialize_project_profile(tmp_path, intent="Keep the audit focused.")
        after = AuditInputSnapshot.capture(plan_path, tmp_path)

        assert before.fingerprint != after.fingerprint
        assert before.revision != after.revision
        assert after.revision["version"] == 3
        assert after.revision["project_context_digest"] is not None
        assert "Keep the audit focused." in after.project_context

    def test_snapshot_freezes_project_context_against_a_later_disk_edit(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.project_profile import (
            initialize_project_profile,
            project_profile_path,
        )
        from plan_tool.review import render_plan_audit_prompt
        from plan_tool.review_persistence import AuditInputSnapshot

        initialize_project_profile(tmp_path, intent="Keep the audit narrow.")
        plan_path = self._write_plan(tmp_path)
        snapshot = AuditInputSnapshot.capture(plan_path, tmp_path)
        project_profile_path(tmp_path).write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "intent": "EXPANDED AFTER CAPTURE.",
                    "non_goals": [],
                    "decisions": [],
                }
            )
            + "\n",
            encoding="utf-8",
        )

        prompt = render_plan_audit_prompt(
            snapshot.plan,
            plan_path,
            repo_root=tmp_path,
            audit_input_snapshot=snapshot,
        )

        assert prompt is not None
        assert "Keep the audit narrow." in prompt
        assert "EXPANDED AFTER CAPTURE." not in prompt

    def test_prompt_has_no_unresolved_template_placeholder(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.parser import parse_plan
        from plan_tool.review import render_plan_audit_prompt

        plan_path = self._write_plan(
            tmp_path, plan_intent="Resolve every placeholder"
        )
        plan = parse_plan(plan_path)
        prompt = render_plan_audit_prompt(plan, plan_path, repo_root=tmp_path)
        assert prompt is not None
        assert "${" not in prompt

    def test_no_intent_prompt_inserts_nothing_before_the_plan_body(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.parser import parse_plan
        from plan_tool.review import render_plan_audit_prompt

        free_dir = tmp_path / "free"
        free_dir.mkdir()
        free_path = self._write_plan(free_dir)
        free_plan = parse_plan(free_path)
        free_prompt = render_plan_audit_prompt(
            free_plan, free_path, repo_root=free_dir
        )
        assert free_prompt is not None
        before, _, _ = free_prompt.partition("## Plan body")
        # Intent-free: only whitespace between prior content and the body.
        assert before[len(before.rstrip()):].strip() == ""
        assert "Authoritative scope input" not in before

        placeholder_dir = tmp_path / "placeholder"
        placeholder_dir.mkdir()
        placeholder_path = self._write_plan(
            placeholder_dir,
            plan_intent="TODO",
            step_intent="_(TODO)_",
        )
        placeholder_plan = parse_plan(placeholder_path)
        placeholder_prompt = render_plan_audit_prompt(
            placeholder_plan, placeholder_path, repo_root=placeholder_dir
        )
        assert placeholder_prompt == free_prompt

    def test_bodyless_plan_returns_none_even_with_an_intent_set(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.parser import parse_plan
        from plan_tool.review import render_plan_audit_prompt

        plan_path = self._write_plan(
            tmp_path, body="", plan_intent="Still bodyless"
        )
        plan = parse_plan(plan_path)
        assert (
            render_plan_audit_prompt(plan, plan_path, repo_root=tmp_path)
            is None
        )


    def test_dollar_sign_in_an_intent_reaches_the_prompt_literally(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.parser import parse_plan
        from plan_tool.review import render_plan_audit_prompt

        plan_path = self._write_plan(
            tmp_path, plan_intent="Keep ${x} literal"
        )
        plan = parse_plan(plan_path)
        prompt = render_plan_audit_prompt(plan, plan_path, repo_root=tmp_path)
        assert prompt is not None
        assert "Keep ${x} literal" in prompt

    def test_prompt_never_asks_for_an_intent_agreement_check(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.parser import parse_plan
        from plan_tool.review import render_plan_audit_prompt

        plan_path = self._write_plan(
            tmp_path, plan_intent="Framing must refuse agreement checks"
        )
        plan = parse_plan(plan_path)
        prompt = render_plan_audit_prompt(plan, plan_path, repo_root=tmp_path)
        assert prompt is not None
        block = _format_intent_block(plan)
        assert "[out-of-scope-deferred]" in block
        assert "Do **not** audit the intent itself" in block
        assert "do not compare" in block
        assert block in prompt
        # Static template gains the slot only — no agreement-check prose.
        template = (
            Path(__file__).resolve().parents[1]
            / "plan_tool"
            / "prompts"
            / "plan-audit.md"
        ).read_text(encoding="utf-8")
        assert template.count("${intent_block}") == 1
        assert "Do **not** audit the intent itself" not in template
        assert "do not compare it against Overview" not in template


class TestAuditPromptScopeContractBlock:
    """``_format_scope_contract_block`` + ``${scope_contract_block}`` in the
    audit prompt (BACKLOG #162).

    Same posture as ``TestAuditPromptIntentBlock``: a plan with no resolvable
    ``source_seed``, or a seed carrying none of the canonical fields, keeps
    the exact prompt it had before this feature existed.
    """

    _SEED_WITH_FIELDS = (
        "# Plan seed: demo\n\n"
        "## Outcome\n\nShip the demo feature end to end.\n\n"
        "## In scope\n\nThe demo module only.\n\n"
        "## Out of scope / Non-goals\n\nAny other module.\n\n"
        "## Verification\n\nRun the demo suite.\n"
    )

    def _plan(self, *, source_seed: Optional[str] = None) -> Plan:
        return Plan(
            title="Audit Plan",
            status=PlanStatus.IN_PROGRESS,
            priority=Priority.MEDIUM,
            source_seed=source_seed,
            steps=[Step(id=1, title="build the thing")],
        )

    def _write_plan(
        self,
        tmp_path: Path,
        *,
        body: str = _FULL_BODY_SECTIONS,
        source_seed: Optional[str] = None,
    ) -> Path:
        plan_path = tmp_path / "audit-scope-contract-plan.md"
        source_seed_yaml = (
            f"source_seed: {source_seed}\n" if source_seed is not None else ""
        )
        plan_path.write_text(
            "---\n"
            "title: Audit Plan\n"
            f"{source_seed_yaml}"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: build the thing\n"
            "    status: pending\n"
            "---\n"
            "\n"
            f"{body}",
            encoding="utf-8",
        )
        return plan_path

    # -- _format_scope_contract_block (unit) --

    def test_empty_when_no_source_seed(self, tmp_path: Path) -> None:
        assert _format_scope_contract_block(self._plan(), tmp_path) == ""

    def test_empty_when_seed_file_missing(self, tmp_path: Path) -> None:
        plan = self._plan(source_seed="plan-seeds/gone.md")
        assert _format_scope_contract_block(plan, tmp_path) == ""

    def test_falls_back_to_the_archived_seed_after_create_moves_it(
        self, tmp_path: Path
    ) -> None:
        """``create --from-existing`` unconditionally archives its seed right
        after publishing the new plan (``create.py``'s ``archive_existing_
        source``, called from ``cli/authoring.py`` on every ``--from-
        existing`` run) — this is the common case, not an edge case, so a
        plan's very first ``completeness-audit`` already finds the seed gone
        from its recorded path and must resolve the archived copy instead."""
        seeds_dir = tmp_path / "plan-seeds"
        seeds_dir.mkdir()
        archive_dir = seeds_dir / "archive"
        archive_dir.mkdir()
        # Mirrors create.py's archive_existing_source: moved + a prepended
        # blockquote replacement notice, never a byte-identical copy.
        (archive_dir / "notes.replaced.md").write_text(
            "> **Replaced**: this file has been superseded by `plans/demo.md`.\n"
            "> Preserved here for history; do not edit.\n\n"
            + self._SEED_WITH_FIELDS,
            encoding="utf-8",
        )
        plan = self._plan(source_seed="plan-seeds/notes.md")

        block = _format_scope_contract_block(plan, tmp_path)

        assert "Ship the demo feature end to end." in block

    def test_empty_when_seed_resolves_outside_repo_root(
        self, tmp_path: Path
    ) -> None:
        outside = tmp_path.parent / "outside-scope-contract-seed.md"
        outside.write_text(self._SEED_WITH_FIELDS, encoding="utf-8")
        try:
            plan = self._plan(source_seed="../outside-scope-contract-seed.md")
            assert _format_scope_contract_block(plan, tmp_path) == ""
        finally:
            outside.unlink(missing_ok=True)

    def test_empty_when_seed_has_no_canonical_fields(
        self, tmp_path: Path
    ) -> None:
        seed = tmp_path / "notes.md"
        seed.write_text(
            "# Plan seed: demo\n\n## Why\n\nJust some prose.\n",
            encoding="utf-8",
        )
        plan = self._plan(source_seed="notes.md")
        assert _format_scope_contract_block(plan, tmp_path) == ""

    def test_renders_only_the_present_canonical_fields(
        self, tmp_path: Path
    ) -> None:
        seed = tmp_path / "notes.md"
        seed.write_text(self._SEED_WITH_FIELDS, encoding="utf-8")
        contract = _extract_seed_scope_contract(seed.read_text(encoding="utf-8"))
        assert contract is not None
        assert "**Outcome:**" in contract
        assert "Ship the demo feature end to end." in contract
        assert "**In scope:**" in contract
        assert "**Out of scope / Non-goals:**" in contract
        assert "**Verification:**" in contract
        # Fields the seed never declared are absent, not padded empty.
        assert "**Allowed behavior changes:**" not in contract
        assert "**Allowed reorganization:**" not in contract
        assert "**Stop / defer:**" not in contract

    def test_renders_canonical_out_of_scope_as_non_goals(self) -> None:
        contract = _extract_seed_scope_contract(
            "# Plan seed: demo\n\n"
            "## Out of scope\n\n"
            "Do not change the sibling workflow.\n"
        )

        assert contract == (
            "**Out of scope / Non-goals:**\n\n"
            "Do not change the sibling workflow."
        )

    def test_prefers_explicit_non_goals_heading_when_both_are_present(self) -> None:
        contract = _extract_seed_scope_contract(
            "# Plan seed: demo\n\n"
            "## Out of scope / Non-goals\n\n"
            "Keep the explicit scope-contract wording.\n\n"
            "## Out of scope\n\n"
            "Keep the canonical body wording.\n"
        )

        assert contract == (
            "**Out of scope / Non-goals:**\n\n"
            "Keep the explicit scope-contract wording."
        )

    def test_block_names_the_seed_path_and_conflict_rule(
        self, tmp_path: Path
    ) -> None:
        seed = tmp_path / "notes.md"
        seed.write_text(self._SEED_WITH_FIELDS, encoding="utf-8")
        plan = self._plan(source_seed="notes.md")
        block = _format_scope_contract_block(plan, tmp_path)
        assert "notes.md" in block
        assert "the plan body wins on conflict" in block
        assert "Ship the demo feature end to end." in block

    def test_truncates_an_oversized_contract_with_an_explicit_marker(
        self, tmp_path: Path
    ) -> None:
        seed = tmp_path / "notes.md"
        seed.write_text(
            "# Plan seed: demo\n\n## Outcome\n\n" + ("x" * 500) + "\n",
            encoding="utf-8",
        )
        plan = self._plan(source_seed="notes.md")
        block = _format_scope_contract_block(plan, tmp_path, max_bytes=64)
        assert "truncated" in block
        assert len(block.encode("utf-8")) < 500

    # -- render_plan_audit_prompt (integration) --

    def test_prompt_places_the_scope_contract_block_before_the_plan_body(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.parser import parse_plan
        from plan_tool.review import render_plan_audit_prompt

        seed = tmp_path / "notes.md"
        seed.write_text(self._SEED_WITH_FIELDS, encoding="utf-8")
        plan_path = self._write_plan(tmp_path, source_seed="notes.md")
        plan = parse_plan(plan_path)
        prompt = render_plan_audit_prompt(plan, plan_path, repo_root=tmp_path)
        assert prompt is not None
        assert prompt.index(
            "Ship the demo feature end to end."
        ) < prompt.index("## Plan body")

    def test_intent_and_scope_contract_render_as_separate_paragraphs(
        self, tmp_path: Path
    ) -> None:
        """Both dynamic blocks share one template line with no separator
        between them (so either alone stays byte-identical to before the
        other existed) — when both render, a missing blank line would merge
        the scope contract's bold header into the intent block's last
        sentence as one markdown paragraph (caught in code review)."""
        from plan_tool.parser import parse_plan
        from plan_tool.review import render_plan_audit_prompt

        seed = tmp_path / "notes.md"
        seed.write_text(self._SEED_WITH_FIELDS, encoding="utf-8")
        plan_path = tmp_path / "audit-scope-contract-with-intent-plan.md"
        plan_path.write_text(
            "---\n"
            "title: Audit Plan\n"
            "intent: Carry the plan's purpose\n"
            "source_seed: notes.md\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: build the thing\n"
            "    status: pending\n"
            "---\n"
            "\n"
            f"{_FULL_BODY_SECTIONS}",
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)

        prompt = render_plan_audit_prompt(plan, plan_path, repo_root=tmp_path)

        assert prompt is not None
        intent_end = prompt.index("stated intent.") + len("stated intent.")
        scope_start = prompt.index("**Originating scope contract")
        # A markdown paragraph break needs a blank line (\n\n), not one \n.
        assert prompt[intent_end:scope_start] == "\n\n"

    def test_no_source_seed_prompt_is_byte_identical_to_before_the_feature(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.parser import parse_plan
        from plan_tool.review import render_plan_audit_prompt

        no_seed_dir = tmp_path / "no-seed"
        no_seed_dir.mkdir()
        no_seed_path = self._write_plan(no_seed_dir)
        no_seed_plan = parse_plan(no_seed_path)
        no_seed_prompt = render_plan_audit_prompt(
            no_seed_plan, no_seed_path, repo_root=no_seed_dir
        )
        assert no_seed_prompt is not None

        no_fields_dir = tmp_path / "no-fields"
        no_fields_dir.mkdir()
        (no_fields_dir / "notes.md").write_text(
            "# Plan seed: demo\n\n## Why\n\nJust some prose.\n",
            encoding="utf-8",
        )
        no_fields_path = self._write_plan(
            no_fields_dir, source_seed="notes.md"
        )
        no_fields_plan = parse_plan(no_fields_path)
        no_fields_prompt = render_plan_audit_prompt(
            no_fields_plan, no_fields_path, repo_root=no_fields_dir
        )
        assert no_fields_prompt is not None

        # Both plans render byte-identical bodies apart from the plan
        # filename baked into ``## Plan body`` headers — normalize that
        # away by comparing everything up to the plan body marker instead.
        before_no_seed, _, _ = no_seed_prompt.partition("## Plan body")
        before_no_fields, _, _ = no_fields_prompt.partition("## Plan body")
        assert before_no_seed == before_no_fields
        assert "Originating scope contract" not in before_no_seed
        # Pin the literal separator too, not just cross-plan equality: an
        # empty ``${scope_contract_block}`` on its own template line would
        # pass the equality check above while still adding a stray blank
        # line versus the pre-feature template (caught in code review —
        # both blocks empty must leave the same one-blank-line gap
        # ``${intent_block}`` alone left before ``## Plan body``).
        assert before_no_seed.endswith("\n\n\n\n")
        assert not before_no_seed.endswith("\n\n\n\n\n")

    def test_prompt_has_no_unresolved_template_placeholder(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.parser import parse_plan
        from plan_tool.review import render_plan_audit_prompt

        seed = tmp_path / "notes.md"
        seed.write_text(self._SEED_WITH_FIELDS, encoding="utf-8")
        plan_path = self._write_plan(tmp_path, source_seed="notes.md")
        plan = parse_plan(plan_path)
        prompt = render_plan_audit_prompt(plan, plan_path, repo_root=tmp_path)
        assert prompt is not None
        assert "${" not in prompt

    def test_static_template_gains_only_the_slot(self) -> None:
        template = (
            Path(__file__).resolve().parents[1]
            / "plan_tool"
            / "prompts"
            / "plan-audit.md"
        ).read_text(encoding="utf-8")
        assert template.count("${scope_contract_block}") == 1
        assert "Ship the demo feature" not in template

    # -- audit_input_snapshot freezes the seed content (BACKLOG #162 review) --

    def test_snapshot_freezes_seed_content_against_a_later_disk_edit(
        self, tmp_path: Path
    ) -> None:
        """A multi-pass ``--iterate`` audit takes one ``AuditInputSnapshot``
        before sampling; every pass must see the same seed bytes that
        snapshot captured, exactly like it already does for the plan and
        detail bundle — a seed edited mid-run must not leak into a later
        pass's prompt."""
        from plan_tool.review_persistence import AuditInputSnapshot

        seed = tmp_path / "notes.md"
        seed.write_text(self._SEED_WITH_FIELDS, encoding="utf-8")
        plan_path = self._write_plan(tmp_path, source_seed="notes.md")

        snapshot = AuditInputSnapshot.capture(plan_path, tmp_path)
        assert snapshot.source_seed_bytes == self._SEED_WITH_FIELDS.encode("utf-8")

        # Edit the seed on disk after the snapshot was taken.
        seed.write_text(
            "# Plan seed: demo\n\n## Outcome\n\nEDITED AFTER CAPTURE.\n",
            encoding="utf-8",
        )

        frozen_block = _format_scope_contract_block(
            snapshot.plan, tmp_path, audit_input_snapshot=snapshot
        )
        assert "Ship the demo feature end to end." in frozen_block
        assert "EDITED AFTER CAPTURE" not in frozen_block

        # Without a snapshot, the same call reads live and sees the edit —
        # confirming the frozen result above isn't just a stale plan object.
        live_block = _format_scope_contract_block(snapshot.plan, tmp_path)
        assert "EDITED AFTER CAPTURE" in live_block

    def test_snapshot_source_seed_bytes_is_none_when_unresolvable(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review_persistence import AuditInputSnapshot

        plan_path = self._write_plan(
            tmp_path, source_seed="plan-seeds/gone.md"
        )
        snapshot = AuditInputSnapshot.capture(plan_path, tmp_path)
        assert snapshot.source_seed_bytes is None

    def test_seed_edit_changes_the_captured_fingerprint(
        self, tmp_path: Path
    ) -> None:
        """A seed edit must count as audit-input drift like a plan/detail
        edit does — otherwise a multi-pass run's freshness/staleness checks
        (``matches_disk``) would miss a changed scope contract."""
        from plan_tool.review_persistence import AuditInputSnapshot

        seed = tmp_path / "notes.md"
        seed.write_text(self._SEED_WITH_FIELDS, encoding="utf-8")
        plan_path = self._write_plan(tmp_path, source_seed="notes.md")

        before = AuditInputSnapshot.capture(plan_path, tmp_path)
        seed.write_text(
            "# Plan seed: demo\n\n## Outcome\n\nSomething else entirely.\n",
            encoding="utf-8",
        )
        after = AuditInputSnapshot.capture(plan_path, tmp_path)

        assert before.fingerprint != after.fingerprint
        assert not before.matches_disk(plan_path, tmp_path)


class TestAuditPromptBudgetAdvisory:
    """Step 5: ``audit_plan_until_stable`` warns + records the prompt budget
    once per run (before the pass loop), advisory-only, gated on a real send.
    Spies replace the module-level names on ``plan_tool.review``."""

    _write_plan = TestCheckPlanAudit._write_plan
    _sections = staticmethod(TestAuditPlanUntilStable._sections)

    class _WarnSpy:
        """Records each call and returns a budget forced to ``level``."""

        def __init__(self, level: str = "warn") -> None:
            self.level = level
            self.calls: list[dict] = []

        def __call__(
            self, total_bytes, *, context_window=None, blocks=None,
            surface="", remedies=(), stream=None,
        ):
            from plan_tool.prompt_budget import estimate_prompt_budget

            self.calls.append(
                {
                    "total_bytes": total_bytes,
                    "blocks": list(blocks) if blocks else [],
                    "surface": surface,
                }
            )
            budget = estimate_prompt_budget(
                total_bytes, context_window=context_window, blocks=blocks
            )
            return dataclasses.replace(budget, level=self.level)

    class _RecordSpy:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def __call__(self, repo_root, **kwargs):
            self.calls.append({"repo_root": repo_root, **kwargs})

    def _install(
        self, monkeypatch: pytest.MonkeyPatch, *, level: str = "warn"
    ) -> tuple["TestAuditPromptBudgetAdvisory._WarnSpy",
               "TestAuditPromptBudgetAdvisory._RecordSpy"]:
        from plan_tool import review as review_module

        warn_spy = self._WarnSpy(level=level)
        record_spy = self._RecordSpy()
        monkeypatch.setattr(
            review_module, "maybe_warn_prompt_budget", warn_spy
        )
        monkeypatch.setattr(
            review_module, "record_prompt_budget", record_spy
        )
        return warn_spy, record_spy

    def _install_fake_shell(
        self,
        monkeypatch: pytest.MonkeyPatch,
        responses: list[str],
        records: list[dict] | None = None,
    ) -> list[dict]:
        from types import SimpleNamespace

        from plan_tool import backend_runner, shell as shell_module
        from plan_tool.backend import PromptTransport
        from subprocess_doubles import _FakeProc

        remaining = list(responses)
        shell_records = records if records is not None else []
        fake_backend = SimpleNamespace(
            name="claude",
            binary="claude",
            batch_transport=lambda p: PromptTransport(["claude", "-p", p]),
            batch_output="stdout",
            parse_stream_line=lambda line, *, bytes_in: None,
        )
        monkeypatch.setattr(
            shell_module, "get_active_backend", lambda: fake_backend
        )
        monkeypatch.setattr(
            backend_runner, "get_active_backend", lambda: fake_backend
        )
        monkeypatch.setattr(
            shell_module.shutil, "which", lambda _name: "/usr/bin/claude"
        )

        real_popen = backend_runner.subprocess.Popen

        def fake_popen(argv, **kwargs):
            if argv and argv[0] == "git":
                return real_popen(argv, **kwargs)
            if not remaining:
                raise AssertionError("unexpected shell invoke")
            return _FakeProc(remaining.pop(0).splitlines(keepends=True), [], 0)

        monkeypatch.setattr(backend_runner.subprocess, "Popen", fake_popen)
        monkeypatch.setattr(
            shell_module,
            "record_prompt_budget",
            lambda *a, **k: shell_records.append({"source": "shell", **dict(k)}),
        )
        return shell_records

    def test_audit_budget_warns_once_before_passes(
        self, tmp_path: Path, capsys
    ) -> None:
        """A large plan body drives the real leaf to a warn/high advisory —
        emitted on stderr exactly once, not once per pass."""
        from plan_tool.review import audit_plan_until_stable

        # ~600KB body → over the high-headroom threshold under the default
        # 200K window, so the real (unspied) leaf emits.
        big_body = "## Overview\n\n" + ("lorem ipsum dolor sit amet. " * 24_000)
        plan_path = self._write_plan(tmp_path, body=big_body)
        plan = parse_plan(plan_path)
        invoker, calls = TestAuditPlanUntilStable()._sampling_invoker([
            self._sections("gap-one"),
            self._sections("gap-one"),  # dry → clean stop
        ])
        capsys.readouterr()  # drop anything buffered before the run
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=3, dry_rounds=1,
        )
        err = capsys.readouterr().err
        assert err.count("prompt budget") == 1

    def test_audit_budget_records_one_prompt_budget_event(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.locator import slug_from_filename
        from plan_tool.review import audit_plan_until_stable

        _, record_spy = self._install(monkeypatch)
        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        invoker, _ = TestAuditPlanUntilStable()._sampling_invoker([
            self._sections("gap-one"),
            self._sections("gap-one"),
        ])
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=3, dry_rounds=1,
        )
        assert len(record_spy.calls) == 1
        rec = record_spy.calls[0]
        assert rec["phase"] == "plan-audit"
        assert rec["total_bytes"] > 0
        assert rec["advisory"] in {"ok", "warn", "high"}
        assert rec["plan_slug"] == slug_from_filename(plan_path)

    def test_shell_review_invoker_records_named_budget_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.backend import spawn_cwd
        from plan_tool import review as review_module
        from plan_tool.review import audit_plan_until_stable, shell_review_invoker

        self._install(monkeypatch)
        records: list[dict] = []
        monkeypatch.setattr(
            review_module,
            "record_prompt_budget",
            lambda *a, **k: records.append({"source": "review", **dict(k)}),
        )
        self._install_fake_shell(monkeypatch, [self._sections("gap-one")], records)
        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)

        with spawn_cwd(tmp_path):
            audit_plan_until_stable(
                plan,
                plan_path,
                repo_root=tmp_path,
                invoker=shell_review_invoker,
                max_passes=1,
                dry_rounds=1,
            )

        assert [rec["phase"] for rec in records] == ["plan-audit"]
        assert [rec["source"] for rec in records] == ["review"]

    def test_plan_audit_suppresses_shell_backstop_across_passes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.backend import spawn_cwd
        from plan_tool import review as review_module
        from plan_tool.review import audit_plan_until_stable, shell_review_invoker

        self._install(monkeypatch)
        records: list[dict] = []
        monkeypatch.setattr(
            review_module,
            "record_prompt_budget",
            lambda *a, **k: records.append({"source": "review", **dict(k)}),
        )
        self._install_fake_shell(
            monkeypatch,
            [self._sections("gap-one"), self._sections("gap-two")],
            records,
        )
        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)

        with spawn_cwd(tmp_path):
            recs = audit_plan_until_stable(
                plan,
                plan_path,
                repo_root=tmp_path,
                invoker=shell_review_invoker,
                max_passes=2,
                dry_rounds=3,
            )

        assert len(recs) >= 2
        assert [rec["phase"] for rec in records] == ["plan-audit"]
        assert [rec["source"] for rec in records] == ["review"]

    def test_plan_audit_backstop_is_fallback_when_advisory_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the once-per-run audit advisory raises (and is swallowed), the
        shell backstop is NOT suppressed, so it stays a fallback net across
        passes rather than leaving each send with zero budget coverage."""
        from plan_tool.backend import spawn_cwd
        from plan_tool import review as review_module
        from plan_tool.review import audit_plan_until_stable, shell_review_invoker

        self._install(monkeypatch)  # warn returns a budget
        monkeypatch.setattr(
            review_module,
            "record_prompt_budget",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        records: list[dict] = []
        self._install_fake_shell(
            monkeypatch,
            [self._sections("gap-one"), self._sections("gap-two")],
            records,
        )
        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)

        with spawn_cwd(tmp_path):
            audit_plan_until_stable(
                plan,
                plan_path,
                repo_root=tmp_path,
                invoker=shell_review_invoker,
                max_passes=2,
                dry_rounds=3,
            )

        # The scoped advisory raised → the generic backstop covered each send.
        assert records
        assert all(rec["phase"] == "shell-backstop" for rec in records)
        assert all(rec["source"] == "shell" for rec in records)

    def test_plan_audit_high_carried_growth_rearms_backstop(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When a later pass's carried-findings block grows the prompt from a
        safe base into the 'high' band, the per-pass suppression is dropped so
        the generic backstop warns — the once-per-run base advisory (which
        measured only the empty-carried base) cannot catch it on its own.

        Non-tautological on the byte accounting: the estimate is driven to
        'high' *only* once the sized prompt exceeds the base (i.e. only after
        ``carried_bytes`` is actually added), so an accounting regression that
        dropped ``carried_bytes`` would leave every pass at the base size and
        fail to re-arm."""
        import plan_tool.prompt_budget as pb
        from plan_tool.backend import spawn_cwd
        from plan_tool import review as review_module
        from plan_tool.review import audit_plan_until_stable, shell_review_invoker

        # Base advisory returns 'warn' (covered, not high) so the per-pass
        # danger-band check runs.
        self._install(monkeypatch, level="warn")
        records: list[dict] = []
        monkeypatch.setattr(
            review_module,
            "record_prompt_budget",
            lambda *a, **k: records.append({"source": "review", **dict(k)}),
        )
        # Sizes the danger-band estimate was actually asked about. 'high' only
        # once the prompt exceeds the first (empty-carried, pass-1) size — so it
        # trips solely because the growing carried block was summed in.
        sized: list[int] = []

        def fake_estimate(total_bytes, **kwargs):
            base = sized[0] if sized else total_bytes
            sized.append(total_bytes)
            level = "high" if total_bytes > base else "ok"
            return dataclasses.replace(
                pb.estimate_prompt_budget(total_bytes), level=level
            )

        monkeypatch.setattr(
            review_module, "estimate_prompt_budget", fake_estimate
        )
        self._install_fake_shell(
            monkeypatch,
            [self._sections("gap-one"), self._sections("gap-two")],
            records,
        )
        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)

        with spawn_cwd(tmp_path):
            audit_plan_until_stable(
                plan,
                plan_path,
                repo_root=tmp_path,
                invoker=shell_review_invoker,
                max_passes=2,
                dry_rounds=3,
            )

        # Some sizing exceeds the base — proving carried_bytes was summed into
        # pass_bytes (not just the base). The base is re-measured each pass, so
        # the growing size is not at a fixed index.
        assert len(sized) >= 2
        assert max(sized) > sized[0]
        phases = [rec["phase"] for rec in records]
        assert "plan-audit" in phases  # once-per-run base advisory
        # The re-arm fires exactly once (guarded), not once per crossing pass.
        assert phases.count("shell-backstop") == 1

    def test_a_base_that_read_high_against_the_default_window_still_rearms_once_the_window_is_known(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The base advisory runs before any call, so on Claude it measures against the 200K default
        and can read `high` for a prompt that fits the real 1M window. That stale verdict must not
        switch the growth re-arm off for the rest of the run: the base is re-measured every pass."""
        import plan_tool.prompt_budget as pb
        from plan_tool.backend import spawn_cwd
        from plan_tool import review as review_module
        from plan_tool.review import audit_plan_until_stable, shell_review_invoker

        self._install(monkeypatch, level="high")  # base advisory: high against the default
        records: list[dict] = []
        monkeypatch.setattr(
            review_module,
            "record_prompt_budget",
            lambda *a, **k: records.append({"source": "review", **dict(k)}),
        )
        monkeypatch.setattr(review_module, "active_context_window", lambda **_: 1_000_000)
        base_bytes: list[int] = []

        def fake_estimate(total_bytes, **kwargs):
            """Against the known window only a prompt larger than the base is `high`."""
            assert kwargs.get("context_window") == 1_000_000, "the re-arm must use the window known now"
            base = base_bytes[0] if base_bytes else total_bytes
            base_bytes.append(base) if not base_bytes else None
            level = "high" if total_bytes > base else "ok"
            return dataclasses.replace(pb.estimate_prompt_budget(total_bytes), level=level)

        monkeypatch.setattr(review_module, "estimate_prompt_budget", fake_estimate)
        self._install_fake_shell(
            monkeypatch, [self._sections("gap-one"), self._sections("gap-two")], records
        )
        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)

        with spawn_cwd(tmp_path):
            audit_plan_until_stable(
                plan, plan_path, repo_root=tmp_path, invoker=shell_review_invoker,
                max_passes=2, dry_rounds=3,
            )

        phases = [rec["phase"] for rec in records]
        assert phases.count("shell-backstop") == 1

    def test_a_base_that_never_warned_but_reads_high_against_a_smaller_learned_window_rearms_at_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The base advisory ran against the 200K default and said `ok`, so nothing was printed and the
        backstop is suppressed. If a call then teaches a window smaller than the default, the base
        reads `high` for the first time: skipping the re-arm because it "reads high" would leave the
        run with no warning at all, so the suppression is dropped once."""
        import plan_tool.prompt_budget as pb
        from plan_tool.backend import spawn_cwd
        from plan_tool import review as review_module
        from plan_tool.review import audit_plan_until_stable, shell_review_invoker

        self._install(monkeypatch, level="ok")  # base advisory against the default: ok, nothing printed
        records: list[dict] = []
        monkeypatch.setattr(
            review_module,
            "record_prompt_budget",
            lambda *a, **k: records.append({"source": "review", **dict(k)}),
        )
        monkeypatch.setattr(review_module, "active_context_window", lambda **_: 100_000)

        def fake_estimate(total_bytes, **kwargs):
            level = "high" if kwargs.get("context_window") == 100_000 else "ok"
            return dataclasses.replace(pb.estimate_prompt_budget(total_bytes), level=level)

        monkeypatch.setattr(review_module, "estimate_prompt_budget", fake_estimate)
        self._install_fake_shell(
            monkeypatch, [self._sections("gap-one"), self._sections("gap-two")], records
        )
        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)

        with spawn_cwd(tmp_path):
            audit_plan_until_stable(
                plan, plan_path, repo_root=tmp_path, invoker=shell_review_invoker,
                max_passes=2, dry_rounds=3,
            )

        phases = [rec["phase"] for rec in records]
        assert phases.count("shell-backstop") == 1

    def test_audit_budget_fires_once_per_run_not_per_pass(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.review import audit_plan_until_stable

        warn_spy, record_spy = self._install(monkeypatch)
        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        # Every pass finds a new id → the loop runs all three passes.
        invoker, calls = TestAuditPlanUntilStable()._sampling_invoker([
            self._sections("gap-one"),
            self._sections("gap-two"),
            self._sections("gap-three"),
        ])
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=3, dry_rounds=3,
        )
        assert len(calls) == 3  # all passes ran
        assert len(warn_spy.calls) == 1
        assert len(record_spy.calls) == 1

    def test_audit_budget_skipped_when_no_invoker(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.review import audit_plan_until_stable

        warn_spy, record_spy = self._install(monkeypatch)
        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=None, max_passes=3,
        )
        assert warn_spy.calls == []
        assert record_spy.calls == []

    def test_audit_budget_skipped_when_no_body(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.review import audit_plan_until_stable

        warn_spy, record_spy = self._install(monkeypatch)
        plan_path = self._write_plan(tmp_path, body="")  # render → None
        plan = parse_plan(plan_path)
        invoker, _ = TestAuditPlanUntilStable()._sampling_invoker([
            self._sections("gap-one"),
        ])
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker, max_passes=3,
        )
        assert warn_spy.calls == []
        assert record_spy.calls == []

    def test_audit_budget_does_not_change_return(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.review import audit_plan_until_stable

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        responses = [self._sections("gap-one"), self._sections("gap-one")]

        # With the advisory firing (spied warn/record):
        self._install(monkeypatch, level="high")
        inv_a, _ = TestAuditPlanUntilStable()._sampling_invoker(list(responses))
        with_advisory = audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=inv_a,
            max_passes=3, dry_rounds=1,
        )
        # With both hooks stubbed to silent no-ops:
        from plan_tool import review as review_module
        from plan_tool.prompt_budget import estimate_prompt_budget

        monkeypatch.setattr(
            review_module, "maybe_warn_prompt_budget",
            lambda tb, **k: estimate_prompt_budget(tb),
        )
        monkeypatch.setattr(
            review_module, "record_prompt_budget", lambda *a, **k: None
        )
        inv_b, _ = TestAuditPlanUntilStable()._sampling_invoker(list(responses))
        without_advisory = audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=inv_b,
            max_passes=3, dry_rounds=1,
        )
        assert [r.body for r in with_advisory] == [
            r.body for r in without_advisory
        ]

    def test_audit_budget_silent_at_ok_level(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A small prompt stays silent on stderr (leaf silent at ``ok``) while
        telemetry still records the event."""
        from plan_tool.review import audit_plan_until_stable

        _, record_spy = self._install(monkeypatch, level="ok")
        plan_path = self._write_plan(tmp_path)  # small default body
        plan = parse_plan(plan_path)
        invoker, _ = TestAuditPlanUntilStable()._sampling_invoker([
            self._sections("gap-one"),
            self._sections("gap-one"),
        ])
        audit_plan_until_stable(
            plan, plan_path, repo_root=tmp_path, invoker=invoker,
            max_passes=3, dry_rounds=1,
        )
        assert len(record_spy.calls) == 1
        assert record_spy.calls[0]["advisory"] == "ok"

    def test_plan_audit_collect_blocks_names_major_blocks(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import render_plan_audit_prompt

        plan_path = self._write_plan(tmp_path)
        plan = parse_plan(plan_path)
        # Blocks are collected during the render itself (no second formatter
        # pass) via the collect_blocks out-param.
        blocks: list[tuple[str, int]] = []
        prompt = render_plan_audit_prompt(
            plan, plan_path, repo_root=tmp_path, collect_blocks=blocks
        )
        names = [name for name, _ in blocks]
        assert names == [
            "plan body",
            "detail bundle",
            "detail-bundle status",
            "scope contract",
        ]
        assert prompt is not None
        # Breakdown is display-only — the sum may be under the full prompt's
        # byte count (template scaffolding + carried block omitted).
        assert sum(n for _, n in blocks) <= len(prompt.encode("utf-8"))


# ---------------------------------------------------------------------------
# Impact-weighted apply triage (session 4 follow-up)
# ---------------------------------------------------------------------------


class TestApplyTriage:
    """Triage rule: skip applies whose complexity strictly exceeds
    their impact. Pins the matrix, the missing-tag fall-open, the
    partition helper, and the stderr summary shape."""

    def _rec(
        self,
        *,
        rec_id: str = "r",
        impact: Optional[str] = None,
        complexity: Optional[str] = None,
        title: str = "t",
    ):
        from plan_tool.review import Recommendation

        return Recommendation(
            id=rec_id,
            source="reconcile",
            severity="high",
            step_id=1,
            title=title,
            body="body",
            impact=impact,
            complexity=complexity,
        )

    @pytest.mark.parametrize(
        "impact, complexity, expected_apply",
        [
            # Apply when impact >= complexity.
            ("high", "high", True),
            ("high", "medium", True),
            ("high", "low", True),
            ("medium", "medium", True),
            ("medium", "low", True),
            ("low", "low", True),
            # Skip when complexity > impact.
            ("low", "medium", False),
            ("low", "high", False),
            ("medium", "high", False),
        ],
    )
    def test_should_apply_by_triage_matrix(
        self, impact: str, complexity: str, expected_apply: bool,
    ) -> None:
        """Full 3x3 matrix of (impact, complexity) levels.
        ``complexity <= impact`` is the rule; the converse skips."""
        from plan_tool.review import should_apply_by_triage

        rec = self._rec(impact=impact, complexity=complexity)
        assert should_apply_by_triage(rec) is expected_apply

    def test_should_apply_by_triage_missing_tags_falls_open(
        self,
    ) -> None:
        """Findings without triage tags (None/empty/unrecognized)
        default to apply -- legacy reconcile output, deterministic
        completeness checks, and concept findings don't carry these
        fields and must continue to flow through the apply path."""
        from plan_tool.review import should_apply_by_triage

        assert should_apply_by_triage(
            self._rec(impact=None, complexity=None)
        ) is True
        assert should_apply_by_triage(
            self._rec(impact="", complexity="")
        ) is True
        # Only impact populated → no signal → apply.
        assert should_apply_by_triage(
            self._rec(impact="high", complexity=None)
        ) is True
        # Unrecognized token → treated as no signal → apply.
        assert should_apply_by_triage(
            self._rec(impact="critical", complexity="trivial")
        ) is True

    def test_should_apply_by_triage_case_insensitive(self) -> None:
        """Triage tags are normalized to lowercase so claude's
        case-variations (``Low``, ``HIGH``) don't break the
        comparison."""
        from plan_tool.review import should_apply_by_triage

        # Uppercase tags should classify the same as lowercase.
        assert should_apply_by_triage(
            self._rec(impact="LOW", complexity="HIGH")
        ) is False
        assert should_apply_by_triage(
            self._rec(impact="High", complexity="Medium")
        ) is True

    def test_triage_reason_renders_levels(self) -> None:
        """``triage_reason`` produces a human-readable string with
        both levels for use in stderr summaries and the rollup."""
        from plan_tool.review import triage_reason

        rec = self._rec(impact="low", complexity="high")
        reason = triage_reason(rec)
        assert "impact=low" in reason
        assert "complexity=high" in reason
        assert "deferred by triage" in reason

    def test_triage_reason_handles_missing_tags(self) -> None:
        """When only one tag is set (rare; partial parse), the
        reason still renders without crashing -- ``?`` placeholder
        for the missing side."""
        from plan_tool.review import triage_reason

        rec = self._rec(impact=None, complexity="high")
        reason = triage_reason(rec)
        assert "impact=?" in reason
        assert "complexity=high" in reason

    def test_partition_findings_for_triage_splits_by_rule(
        self,
    ) -> None:
        """The partition helper bisects ``findings`` into the apply
        and deferred buckets. Input order is preserved within each
        bucket so caller's downstream loop ordering is stable."""
        from plan_tool.review import partition_findings_for_triage

        recs = [
            self._rec(rec_id="a-apply", impact="high", complexity="low"),
            self._rec(rec_id="b-defer", impact="low", complexity="high"),
            self._rec(rec_id="c-apply", impact="medium", complexity="medium"),
            self._rec(rec_id="d-defer", impact="medium", complexity="high"),
            self._rec(rec_id="e-noteag", impact=None, complexity=None),
        ]
        open_apply, open_deferred = partition_findings_for_triage(recs)

        assert [r.id for r in open_apply] == [
            "a-apply", "c-apply", "e-noteag",
        ]
        assert [r.id for r in open_deferred] == ["b-defer", "d-defer"]

    def test_partition_findings_disabled_returns_all_in_apply(
        self,
    ) -> None:
        """``triage_enabled=False`` (CLI ``--no-triage``) returns
        the full input as apply, deferred is empty -- legacy
        behavior preserved."""
        from plan_tool.review import partition_findings_for_triage

        recs = [
            self._rec(rec_id="r1", impact="low", complexity="high"),
            self._rec(rec_id="r2", impact="high", complexity="high"),
        ]
        open_apply, open_deferred = partition_findings_for_triage(
            recs, triage_enabled=False,
        )
        assert len(open_apply) == 2
        assert open_deferred == []

    def _rec_sev(self, *, rec_id: str, severity: str):
        from plan_tool.review import Recommendation

        # Use an apply-eligible source so the info-severity gate is
        # exercised in isolation from the apply-eligibility gate.
        return Recommendation(
            id=rec_id, source="body-completeness", severity=severity,
            step_id=None, title="t", body="b",
        )

    def test_info_findings_excluded_by_default(self) -> None:
        """Info-severity findings are deferred by default -- advisory,
        not worth an apply pass. Non-info findings still apply."""
        from plan_tool.review import partition_findings_for_triage

        recs = [
            self._rec_sev(rec_id="info-1", severity="info"),
            self._rec_sev(rec_id="med-1", severity="medium"),
        ]
        open_apply, open_deferred = partition_findings_for_triage(recs)
        assert [r.id for r in open_apply] == ["med-1"]
        assert [r.id for r in open_deferred] == ["info-1"]

    def test_include_info_opts_info_back_into_apply(self) -> None:
        """``include_info=True`` (CLI ``--include-info``) routes info
        findings into the apply bucket."""
        from plan_tool.review import partition_findings_for_triage

        recs = [self._rec_sev(rec_id="info-1", severity="info")]
        open_apply, open_deferred = partition_findings_for_triage(
            recs, include_info=True,
        )
        assert [r.id for r in open_apply] == ["info-1"]
        assert open_deferred == []

    def test_info_exclusion_independent_of_triage_disable(self) -> None:
        """Info exclusion is its own gate: ``--no-triage`` still defers
        info findings (combine with ``--include-info`` to apply them)."""
        from plan_tool.review import partition_findings_for_triage

        recs = [
            self._rec_sev(rec_id="info-1", severity="info"),
            self._rec_sev(rec_id="high-1", severity="high"),
        ]
        open_apply, open_deferred = partition_findings_for_triage(
            recs, triage_enabled=False,
        )
        assert [r.id for r in open_apply] == ["high-1"]
        assert [r.id for r in open_deferred] == ["info-1"]
        # Both gates off -> everything applies.
        open_apply2, open_deferred2 = partition_findings_for_triage(
            recs, triage_enabled=False, include_info=True,
        )
        assert len(open_apply2) == 2
        assert open_deferred2 == []

    def test_triage_reason_distinguishes_info_exclusion(self) -> None:
        """``triage_reason`` reports the info-exclusion cause distinctly
        from the complexity-vs-impact cause."""
        from plan_tool.review import triage_reason

        info_rec = self._rec_sev(rec_id="i", severity="info")
        assert "info severity" in triage_reason(info_rec)
        assert "--include-info" in triage_reason(info_rec)

    def _rec_src(self, *, rec_id: str, source: str, severity: str = "high"):
        from plan_tool.review import Recommendation

        return Recommendation(
            id=rec_id, source=source, severity=severity,
            step_id=None, title="t", body="b",
        )

    def test_is_apply_eligible_by_source(self) -> None:
        """Prose-editable sources are eligible; structural diagnostics
        are not (dispatching them only yields NOT-APPLICABLE)."""
        from plan_tool.review import is_apply_eligible

        for src in (
            "body-completeness", "detail-body", "plan-correctness",
            "reconcile", "detail-reconcile", "run-reconcile", "claude",
        ):
            assert is_apply_eligible(self._rec_src(rec_id="x", source=src))
        for src in (
            "file-check", "path-style", "deps", "detail-coverage",
            "files-coherence", "lessons-coverage", "plan-completeness",
            "heuristic",
        ):
            assert not is_apply_eligible(
                self._rec_src(rec_id="x", source=src)
            )

    def test_detail_altitude_source_not_apply_eligible(self) -> None:
        from plan_tool.review import is_apply_eligible

        rec = self._rec_src(rec_id="alt", source=DETAIL_ALTITUDE_SOURCE)
        assert not is_apply_eligible(rec)
        assert DETAIL_ALTITUDE_SOURCE not in APPLY_ELIGIBLE_SOURCES
        assert DETAIL_ALTITUDE_SOURCE not in STRUCTURAL_SOURCES

    def test_detail_altitude_deferred_even_with_include_info(self) -> None:
        from plan_tool.review import partition_findings_for_triage

        rec = self._rec_src(
            rec_id="alt", source=DETAIL_ALTITUDE_SOURCE, severity="info"
        )
        open_apply, open_deferred = partition_findings_for_triage(
            [rec], include_info=True,
        )
        assert open_apply == []
        assert open_deferred == [rec]

    def test_detail_altitude_triage_reason_names_advisory_altitude(
        self,
    ) -> None:
        rec = self._rec_src(rec_id="alt", source=DETAIL_ALTITUDE_SOURCE)
        reason = triage_reason(rec)
        assert "advisory detail-quality altitude issue" in reason
        assert "structural diagnostic" not in reason
        assert "plan-tool detail" not in reason

    def test_structural_diagnostics_deferred_even_at_high_severity(
        self,
    ) -> None:
        """A high-severity ``file-check`` finding is deferred, not
        dispatched -- this is the NOT-APPLICABLE waste fix."""
        from plan_tool.review import partition_findings_for_triage

        recs = [
            self._rec_src(rec_id="fc", source="file-check", severity="high"),
            self._rec_src(
                rec_id="bc", source="body-completeness", severity="high",
            ),
        ]
        open_apply, open_deferred = partition_findings_for_triage(recs)
        assert [r.id for r in open_apply] == ["bc"]
        assert [r.id for r in open_deferred] == ["fc"]

    def test_no_triage_still_defers_structural_diagnostics(self) -> None:
        """``--no-triage`` force-applies eligible findings but still
        won't dispatch a diagnostic with no apply remedy."""
        from plan_tool.review import partition_findings_for_triage

        recs = [
            self._rec_src(rec_id="fc", source="file-check"),
            self._rec_src(rec_id="bc", source="body-completeness"),
        ]
        open_apply, open_deferred = partition_findings_for_triage(
            recs, triage_enabled=False,
        )
        assert [r.id for r in open_apply] == ["bc"]
        assert [r.id for r in open_deferred] == ["fc"]

    def test_apply_eligible_only_false_lets_diagnostics_through(
        self,
    ) -> None:
        """The eligibility gate can be disabled for callers that want
        the legacy 'dispatch everything' behavior."""
        from plan_tool.review import partition_findings_for_triage

        recs = [self._rec_src(rec_id="fc", source="file-check")]
        open_apply, _ = partition_findings_for_triage(
            recs, apply_eligible_only=False,
        )
        assert [r.id for r in open_apply] == ["fc"]

    def test_triage_reason_for_structural_diagnostic(self) -> None:
        from plan_tool.review import triage_reason

        rec = self._rec_src(rec_id="fc", source="file-check")
        assert "structural diagnostic" in triage_reason(rec)

    def test_triage_reason_for_granularity_split_now_points_at_split(
        self,
    ) -> None:
        """A ``granularity-split`` rec now routes through ``is_structural``
        (ordered ahead of the generic ``not is_apply_eligible`` fallback),
        so its reason points at ``plan-tool split`` and no longer carries
        the generic ``structural diagnostic`` / ``plan-tool detail`` text."""
        from plan_tool.review import triage_reason

        rec = self._rec_src(rec_id="gs", source="granularity-split")
        reason = triage_reason(rec)
        assert "plan-tool split" in reason
        assert "plan-tool detail" not in reason
        assert "structural diagnostic" not in reason

    def test_structural_split_is_structural(self) -> None:
        """``is_structural`` is True for the bridge-emitted
        ``structural-split`` source (now in STRUCTURAL_SOURCES)."""
        from plan_tool.review import is_structural

        assert is_structural(
            self._rec_src(rec_id="ss", source="structural-split")
        )

    def test_structural_split_not_apply_eligible(self) -> None:
        """``structural-split`` stays out of APPLY_ELIGIBLE_SOURCES, so
        ``is_apply_eligible`` is False and it never reaches apply."""
        from plan_tool.review import is_apply_eligible

        assert not is_apply_eligible(
            self._rec_src(rec_id="ss", source="structural-split")
        )

    def test_triage_reason_for_structural_split_points_at_split(
        self,
    ) -> None:
        """A ``structural-split`` rec's reason points the operator at
        ``plan-tool split`` and not at ``plan-tool detail``."""
        from plan_tool.review import triage_reason

        rec = self._rec_src(rec_id="ss", source="structural-split")
        reason = triage_reason(rec)
        assert "plan-tool split" in reason
        assert "plan-tool detail" not in reason

    def test_is_structural_by_source(self) -> None:
        """``is_structural`` is True only for the split-bridge sources;
        apply-eligible sources and the generic diagnostics are not
        structural-split."""
        from plan_tool.review import APPLY_ELIGIBLE_SOURCES, is_structural

        assert is_structural(
            self._rec_src(rec_id="gs", source="granularity-split")
        )
        for src in APPLY_ELIGIBLE_SOURCES:
            assert not is_structural(self._rec_src(rec_id="x", source=src))
        for src in (
            "file-check", "path-style", "granularity-merge",
            "files-coherence", "plan-completeness", "heuristic",
        ):
            assert not is_structural(self._rec_src(rec_id="x", source=src))

    def test_structural_sources_value_matches_granularity_constant(
        self,
    ) -> None:
        """The deliberately-duplicated literal stays in sync with the
        producer's constant (caught if granularity renames the source)."""
        from plan_tool.granularity import GRANULARITY_SPLIT_SOURCE
        from plan_tool.review import STRUCTURAL_SOURCES

        assert GRANULARITY_SPLIT_SOURCE in STRUCTURAL_SOURCES

    def test_structural_sources_disjoint_from_apply_eligible(self) -> None:
        """A finding is never both apply-eligible and structural-split;
        the sets evolve independently (step 2 widens STRUCTURAL_SOURCES)."""
        from plan_tool.review import (
            fenced_spans,
    APPLY_ELIGIBLE_SOURCES,
            STRUCTURAL_SOURCES,
        )

        assert STRUCTURAL_SOURCES & APPLY_ELIGIBLE_SOURCES == frozenset()

    def test_apply_authority_invariants_across_policy_modules(self) -> None:
        """Pin the cross-module safety contract without coupling its owners."""
        from plan_tool.granularity import (
            GRANULARITY_MERGE_SOURCE,
            GRANULARITY_SPLIT_SOURCE,
        )
        from plan_tool.review_walk import split_escalation_target

        granularity_sources = frozenset(
            {GRANULARITY_SPLIT_SOURCE, GRANULARITY_MERGE_SOURCE}
        )
        assert not granularity_sources & APPLY_ELIGIBLE_SOURCES
        assert not STRUCTURAL_SOURCES & APPLY_ELIGIBLE_SOURCES

        cases = (
            (GRANULARITY_SPLIT_SOURCE, "medium", frozenset(), False),
            (
                GRANULARITY_SPLIT_SOURCE,
                "info",
                frozenset({GRANULARITY_SPLIT_SOURCE}),
                False,
            ),
            (
                GRANULARITY_SPLIT_SOURCE,
                "medium",
                frozenset({GRANULARITY_SPLIT_SOURCE}),
                True,
            ),
            (
                GRANULARITY_SPLIT_SOURCE,
                "high",
                frozenset({GRANULARITY_SPLIT_SOURCE}),
                False,
            ),
            (
                GRANULARITY_MERGE_SOURCE,
                "medium",
                frozenset({GRANULARITY_SPLIT_SOURCE}),
                False,
            ),
        )
        for source, severity, extra_sources, expected in cases:
            rec = self._rec_src(rec_id=source, source=source, severity=severity)
            assert is_apply_eligible(rec) is False
            assert (
                split_escalation_target(rec, extra_apply_sources=extra_sources)
                is expected
            )

    def test_emit_triage_summary_no_op_on_empty(self) -> None:
        """Empty deferred list = no-op. Callers can pass the
        partition result unconditionally."""
        import io
        from plan_tool.review import emit_triage_summary

        buf = io.StringIO()
        emit_triage_summary([], iteration_label="x", file=buf)
        assert buf.getvalue() == ""

    def test_emit_triage_summary_lists_each_deferred_rec(self) -> None:
        """Each deferred rec gets a bullet with its id, title, and
        triage reason. The header carries the iteration label so
        operators can correlate across iterations."""
        import io
        from plan_tool.review import emit_triage_summary

        deferred = [
            self._rec(
                rec_id="r1", title="trivial-typo-on-huge-file",
                impact="low", complexity="high",
            ),
            self._rec(
                rec_id="r2", title="medium-rename-spanning-files",
                impact="medium", complexity="high",
            ),
        ]
        buf = io.StringIO()
        emit_triage_summary(
            deferred, iteration_label="reconcile iter 2", file=buf,
        )
        out = buf.getvalue()
        assert "deferring 2 finding(s)" in out
        assert "reconcile iter 2" in out
        assert "r1: trivial-typo-on-huge-file" in out
        assert "complexity=high > impact=low" in out
        assert "r2: medium-rename-spanning-files" in out

    def _structural_rec(
        self, *, rec_id: str, source: str, body: str,
        suggested_action: Optional[str],
    ):
        from plan_tool.review import Recommendation

        return Recommendation(
            id=rec_id, source=source, severity="high", step_id=3,
            title="over-packed step", body=body,
            suggested_action=suggested_action,
        )

    def test_emit_triage_summary_renders_body_and_action_for_structural_split(
        self,
    ) -> None:
        """A deferred ``structural-split`` rec prints its body and its
        ``plan-tool split`` suggested-action on indented sub-lines under
        the bullet."""
        import io
        from plan_tool.review import emit_triage_summary

        rec = self._structural_rec(
            rec_id="ss", source="structural-split",
            body="step 3 mixes refactor + feature; split it",
            suggested_action="plan-tool split my-plan 3",
        )
        buf = io.StringIO()
        emit_triage_summary([rec], iteration_label="iter 1", file=buf)
        out = buf.getvalue()
        assert "ss: over-packed step" in out
        assert "      step 3 mixes refactor + feature; split it" in out
        assert "      plan-tool split my-plan 3" in out

    def test_emit_triage_summary_renders_body_for_granularity_split(
        self,
    ) -> None:
        """A live-shape ``granularity-split`` deferred rec (body + the
        ``granularity.py`` producer's non-None action) prints both
        sub-lines, pinning that this reaches the real detail path."""
        import io
        from plan_tool.review import emit_triage_summary

        rec = self._structural_rec(
            rec_id="gs", source="granularity-split",
            body="step 3 is over-packed",
            suggested_action="Consider splitting step 3 into type-pure steps",
        )
        buf = io.StringIO()
        emit_triage_summary([rec], iteration_label="detail iter 2", file=buf)
        out = buf.getvalue()
        assert "      step 3 is over-packed" in out
        assert (
            "      Consider splitting step 3 into type-pure steps" in out
        )

    def test_emit_triage_summary_omits_action_line_when_none(self) -> None:
        """A structural rec with ``suggested_action=None`` prints the body
        sub-line but no action sub-line."""
        import io
        from plan_tool.review import emit_triage_summary

        rec = self._structural_rec(
            rec_id="ss", source="structural-split",
            body="split rationale only", suggested_action=None,
        )
        buf = io.StringIO()
        emit_triage_summary([rec], iteration_label="iter 1", file=buf)
        out = buf.getvalue()
        assert "      split rationale only" in out
        # Exactly two lines after the header: the bullet + the body.
        body_lines = [ln for ln in out.splitlines() if ln.startswith("      ")]
        assert body_lines == ["      split rationale only"]

    def test_emit_triage_summary_non_structural_unchanged(self) -> None:
        """A ``reconcile`` rec still emits exactly the single bullet line —
        no body/action sub-lines — guarding the ``is_structural`` gate."""
        import io
        from plan_tool.review import emit_triage_summary

        rec = self._rec(
            rec_id="rc", title="non-structural finding",
            impact="low", complexity="high",
        )
        buf = io.StringIO()
        emit_triage_summary([rec], iteration_label="iter 1", file=buf)
        out = buf.getvalue()
        assert "rc: non-structural finding" in out
        assert not [ln for ln in out.splitlines() if ln.startswith("      ")]


class TestCompletenessReportDispositionLanguage:
    def _rec(self, rec_id: str, source: str) -> Recommendation:
        return Recommendation(
            id=rec_id,
            source=source,
            severity="medium",
            step_id=None,
            title="gap",
            body="gap",
            anchor=rec_id,
        )

    def test_auto_apply_deferred_stop_keeps_conceptual_gaps_distinct(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.completeness_report import (
            blocking_verdict_from_gate,
            build_report_md,
            console_summary,
        )

        report_path = tmp_path / "report.md"
        deferred = [self._rec("drift", "files-coherence")]
        correctness = [self._rec("bad-design", "plan-correctness")]
        conceptual = [self._rec("missing-edge", "plan-completeness")]

        summary = console_summary(
            plan_name="p",
            iterate_enabled=True,
            stop_reason="all_auto_apply_findings_deferred",
            iterations=0,
            applied=[],
            deferred=deferred,
            advisory_conceptual=conceptual,
            open_findings=[],
            report_path=report_path,
            correctness=correctness,
            verdict=blocking_verdict_from_gate(["bad-design"]),
        )
        report = build_report_md(
            plan_title="P",
            plan_name="p",
            iterate_enabled=True,
            stop_reason="all_auto_apply_findings_deferred",
            iterations=0,
            applied=[],
            deferred=deferred,
            advisory_conceptual=conceptual,
            open_findings=[],
            grouped_report_md="## Grouped\n",
            correctness=correctness,
        )

        assert "loop stopped: all_auto_apply_findings_deferred" in summary
        assert "correctness 1 conceptual gap(s)" in summary
        assert "advisory  1 conceptual gap(s)" in summary
        assert "Deferred:** 1" in report
        assert "Conceptual correctness:** 1" in report
        assert "Conceptual completeness" in report
        assert "all_findings_deferred" not in summary
        assert "all_findings_deferred" not in report


# ``TestDecisionImpactComplexity`` removed: ``parse_decision_block`` is
# gone (step 6 of Reconcile Subcommand Split). Step 8 owns the broader
# test-deletion pass.


class TestReviewStyleOutput:
    """review.py's library-level ``plan-tool:`` diagnostics route through
    ``style.tool()``. Plain mode stays byte-identical to the legacy
    ``print(f"plan-tool: ...")`` strings (the form CI operators grep); under
    ``PLAN_TOOL_FORCE_COLOR`` only the ``plan-tool:`` tag carries ANSI, so the
    body stays plain.
    """

    def _deferred(self) -> list[Recommendation]:
        return [
            Recommendation(
                id="rec-1",
                source="reconcile",
                severity="low",
                step_id=1,
                title="trivial typo on huge file",
                body="body",
                impact="low",
                complexity="high",
            )
        ]

    def test_triage_summary_plain_byte_identical(self) -> None:
        deferred = self._deferred()
        buf = io.StringIO()
        emit_triage_summary(deferred, iteration_label="iteration 2", file=buf)
        rec = deferred[0]
        assert buf.getvalue() == (
            "plan-tool: deferring 1 finding(s) by triage "
            "(iteration 2). Apply manually if the complexity is "
            "worth the impact -- the iteration loop will short-circuit "
            "if these are the only findings remaining:\n"
            f"  - {rec.id}: {rec.title} [{triage_reason(rec)}] "
            "[confidence: limited]\n"
        )

    def test_criteria_fulfillment_skip_plain(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        buf = io.StringIO()
        check_criteria_fulfillment(
            plan, plan_path, repo_root=tmp_path, invoker=None, log_file=buf,
        )
        assert buf.getvalue() == (
            "plan-tool: criteria-fulfillment: skipped (no invoker configured)\n"
        )

    def test_plan_audit_skip_plain(self, tmp_path: Path) -> None:
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        buf = io.StringIO()
        check_plan_audit(
            plan, plan_path, repo_root=tmp_path, invoker=None, log_file=buf,
        )
        assert buf.getvalue() == (
            "plan-tool: plan-audit: skipped (no invoker configured)\n"
        )

    def test_triage_summary_color_prefix_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # PLAN_TOOL_FORCE_COLOR is checked first in color_enabled, so it
        # forces color even on a plain StringIO (no real TTY needed).
        monkeypatch.setenv("PLAN_TOOL_FORCE_COLOR", "1")
        buf = io.StringIO()
        emit_triage_summary(
            self._deferred(), iteration_label="iteration 2", file=buf,
        )
        out = buf.getvalue()
        assert out.startswith(style.DIM + "plan-tool:" + style.RESET + " ")
        # The body substring carries no surrounding escapes.
        assert "deferring 1 finding(s) by triage (iteration 2)" in out

    def test_plan_audit_skip_color_prefix_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_FORCE_COLOR", "1")
        plan_path = _write_review_fixture(tmp_path)
        plan = parse_plan(plan_path)
        buf = io.StringIO()
        check_plan_audit(
            plan, plan_path, repo_root=tmp_path, invoker=None, log_file=buf,
        )
        out = buf.getvalue()
        assert out.startswith(style.DIM + "plan-tool:" + style.RESET + " ")
        assert "plan-audit: skipped (no invoker configured)" in out

    def test_lesson_extraction_error_plain(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Unlike the other three sites, this line hardcodes ``sys.stderr``
        # rather than accepting a stream kwarg, so it is driven through
        # ``review_plan_full`` and captured via capsys. The ``except``
        # branch is reachable only when extract_lessons=True, invoker is
        # non-None and returns (0, non-empty) (so claude_stdout_for_recs is
        # set), and the plan yields non-empty recommendations — the
        # missing-parent fixture supplies deterministic findings.
        # NullReporter suppresses the StderrReporter progress lines that
        # would otherwise pollute the captured stream.
        plan_path = _write_review_fixture(tmp_path)

        def _boom(*args, **kwargs):
            raise RuntimeError("kaboom")

        monkeypatch.setattr(
            "plan_tool.review.extract_and_append_review_lessons", _boom,
        )
        review_plan_full(
            plan_path,
            repo_root=tmp_path,
            plan_name="review-test",
            invoker=lambda prompt: (0, "## Findings\n\n_(none)_\n"),
            reporter=NullReporter(),
            extract_lessons=True,
        )
        err = capsys.readouterr().err
        assert err == (
            "plan-tool: lesson extraction failed (kaboom); "
            "review report is unaffected\n"
        )


# --- check_test_strategy_alignment -----------------------------------------


def _write_ts_plan(tmp_path: Path, steps_block: str, *, name: str = "1-ts.md") -> Path:
    """Write a minimal plan whose ``steps:`` block is supplied verbatim."""
    text = (
        "---\n"
        "title: TS Plan\n"
        "status: in-progress\n"
        "priority: medium\n"
        "steps:\n"
        f"{steps_block}"
        "---\n\n# TS Plan\n"
    )
    plan_path = tmp_path / name
    plan_path.write_text(text, encoding="utf-8")
    return plan_path


# A refactor step's ## Tests section that describes after-the-change testing
# (contradicts the step-5 directive) and carries no characterization signal.
_REFACTOR_TESTS_AFTER_DETAIL = (
    "## Summary\n\nrestructure the parser.\n\n"
    "## Tests\n\n"
    "Run the unit tests after the change to confirm behavior is unchanged.\n"
)


class TestCheckTestStrategyAlignment:
    def test_alignment_no_classified_steps_returns_empty(
        self, tmp_path: Path
    ) -> None:
        plan = parse_plan(
            _write_ts_plan(
                tmp_path,
                "  - id: 1\n    title: Do a thing\n    files:\n      - a.py\n"
                "  - id: 2\n    title: Do another\n    files:\n      - b.py\n",
            )
        )
        assert check_test_strategy_alignment(plan) == []

    def test_alignment_consistency_nudge_when_mixed(self, tmp_path: Path) -> None:
        plan = parse_plan(
            _write_ts_plan(
                tmp_path,
                "  - id: 1\n    title: Restructure\n    files:\n      - a.py\n"
                "    change_type: refactor\n"
                "  - id: 2\n    title: Add a feature\n    files:\n      - b.py\n",
            )
        )
        recs = check_test_strategy_alignment(plan)
        nudges = [r for r in recs if r.step_id is None]
        assert len(nudges) == 1
        nudge = nudges[0]
        assert nudge.severity == "info"
        assert nudge.source == "test-strategy"
        assert "2" in nudge.body
        # Carries a concrete suggested fix (deterministic-finding sweep).
        assert nudge.suggested_action is not None
        assert "change_type" in nudge.suggested_action

    def test_alignment_no_nudge_when_all_classified(self, tmp_path: Path) -> None:
        plan = parse_plan(
            _write_ts_plan(
                tmp_path,
                "  - id: 1\n    title: Restructure\n    files:\n      - a.py\n"
                "    change_type: refactor\n"
                "  - id: 2\n    title: Add a feature\n    files:\n      - b.py\n"
                "    change_type: feature\n",
            )
        )
        recs = check_test_strategy_alignment(plan)
        assert [r for r in recs if r.step_id is None] == []

    def test_alignment_no_nudge_when_none_classified(self, tmp_path: Path) -> None:
        plan = parse_plan(
            _write_ts_plan(
                tmp_path,
                "  - id: 1\n    title: Do a thing\n    files:\n      - a.py\n"
                "  - id: 2\n    title: Do another\n    files:\n      - b.py\n",
            )
        )
        # Opt-in: no classified step at all → no findings, hence no nudge.
        assert check_test_strategy_alignment(plan) == []


    def test_alignment_detail_contradiction_skipped_when_no_detail_file(
        self, tmp_path: Path
    ) -> None:
        # change_type set, but detail points nowhere (missing file) — no crash,
        # no contradiction finding.
        plan = parse_plan(
            _write_ts_plan(
                tmp_path,
                "  - id: 1\n    title: Restructure\n    files:\n      - a.py\n"
                "    detail: details/gone.md\n"
                "    change_type: refactor\n",
            )
        )
        recs = check_test_strategy_alignment(plan)
        assert recs == []

    def test_alignment_noncode_footprint_flags_code_path(
        self, tmp_path: Path
    ) -> None:
        plan = parse_plan(
            _write_ts_plan(
                tmp_path,
                "  - id: 1\n    title: Document the deploy\n"
                "    files:\n      - docs/deploy.md\n      - plan_tool/foo.py\n"
                "    change_type: non-code\n",
            )
        )
        recs = check_test_strategy_alignment(plan)
        footprint = [r for r in recs if r.step_id == 1]
        assert len(footprint) == 1
        rec = footprint[0]
        assert rec.source == "test-strategy"
        assert rec.severity == "medium"
        assert "plan_tool/foo.py" in rec.body
        assert "docs/deploy.md" not in rec.body
        # Carries a concrete suggested fix (deterministic-finding sweep).
        assert rec.suggested_action is not None
        assert "re-classify step 1" in rec.suggested_action

    def test_alignment_noncode_footprint_clean_for_doc_paths(
        self, tmp_path: Path
    ) -> None:
        plan = parse_plan(
            _write_ts_plan(
                tmp_path,
                "  - id: 1\n    title: Wire CI\n"
                "    files:\n      - README.md\n      - .github/ci.yaml\n"
                "    change_type: non-code\n",
            )
        )
        assert check_test_strategy_alignment(plan) == []

    def test_alignment_noncode_footprint_exempts_test_code(
        self, tmp_path: Path
    ) -> None:
        """Test code is not production code: a tests-only footprint is
        exactly what `non-code` (test-authoring) describes. Surfaced by
        the cli-package-split audit, where steps 1-7 (characterization
        test authoring, footprints entirely under tests/) were falsely
        flagged as misclassified.
        """
        plan = parse_plan(
            _write_ts_plan(
                tmp_path,
                "  - id: 1\n    title: Author characterization tests\n"
                "    files:\n"
                "      - tests/cli/test_inspect_cmds.py\n"
                "      - tests/cli/conftest.py\n"
                "      - test_toplevel.py\n"
                "    change_type: non-code\n"
                "  - id: 2\n    title: Docs plus stray source\n"
                "    files:\n"
                "      - tests/cli/test_run_cmd.py\n"
                "      - plan_tool/foo.py\n"
                "    change_type: non-code\n",
            )
        )
        recs = check_test_strategy_alignment(plan)
        # Step 1 (tests-only) is clean; step 2 flags ONLY the non-test path.
        assert [r.step_id for r in recs] == [2]
        assert "plan_tool/foo.py" in recs[0].body
        assert "tests/cli/test_run_cmd.py" not in recs[0].body

    def test_alignment_feature_step_no_footprint_check(
        self, tmp_path: Path
    ) -> None:
        # A feature/refactor step listing .py paths is not footprint-checked.
        plan = parse_plan(
            _write_ts_plan(
                tmp_path,
                "  - id: 1\n    title: Add a feature\n"
                "    files:\n      - plan_tool/foo.py\n"
                "    change_type: feature\n"
                "  - id: 2\n    title: Restructure\n"
                "    files:\n      - plan_tool/bar.py\n"
                "    change_type: refactor\n",
            )
        )
        recs = check_test_strategy_alignment(plan)
        assert recs == []

    def test_collect_deterministic_findings_includes_test_strategy(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_ts_plan(
            tmp_path,
            "  - id: 1\n    title: Document the deploy\n"
            "    files:\n      - plan_tool/foo.py\n"
            "    change_type: non-code\n"
            "  - id: 2\n    title: Add a feature\n    files:\n      - b.py\n",
        )
        plan = parse_plan(plan_path)
        recs = collect_deterministic_findings(
            plan, plan_path, repo_root=tmp_path, plan_name="p"
        )
        ts = [r for r in recs if r.source == "test-strategy"]
        # Both the consistency nudge (step 2 unclassified) and the non-code
        # footprint contradiction (step 1's .py path) surface.
        assert any(r.step_id is None for r in ts)
        assert any(r.step_id == 1 for r in ts)

    def test_collect_deterministic_findings_test_strategy_absent_from_review(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_ts_plan(
            tmp_path,
            "  - id: 1\n    title: Document the deploy\n"
            "    files:\n      - plan_tool/foo.py\n"
            "    change_type: non-code\n"
            "  - id: 2\n    title: Add a feature\n    files:\n      - b.py\n",
        )
        plan = parse_plan(plan_path)
        recs = extract_recommendations(
            plan,
            "p",
            repo_root=tmp_path,
            file_checks=check_file_existence(plan, tmp_path),
            heuristic_hits=[],
            dep_issues=[],
            path_style_hint=None,
        )
        assert [r for r in recs if r.source == "test-strategy"] == []


class TestIsTestCodePath:
    """The shared test-code predicate behind ``check_test_strategy_alignment``'s
    non-code footprint check *and* the launcher test-authoring gate.
    """

    @pytest.mark.parametrize(
        "path",
        [
            # Directory-shaped, any depth above the basename. Each of the
            # three directory names is pinned by a basename the *other*
            # rules do not match, so dropping one goes red on its own.
            "tests/fixtures/helpers.ts",
            "src/test/helpers.py",
            "packages/shared/src/__tests__/helpers.ts",
            "packages/shared/src/__tests__/bar.test.ts",
            "tests/test_foo.py",
            # Python basenames.
            "test_toplevel.py",
            "conftest.py",
            # Colocated Vitest/Jest basenames.
            "apps/mobile/services/app-restart.test.ts",
            "apps/web/src/Foo.test.tsx",
            "apps/web/src/Foo.spec.tsx",
            "packages/api/index.spec.js",
            "packages/api/index.test.mjs",
            "packages/api/legacy.spec.cjs",
            # Case-insensitive on the basename suffix.
            "apps/web/src/Foo.Test.TS",
        ],
    )
    def test_recognizes_test_code(self, path: str) -> None:
        from plan_tool.review import _is_test_code_path

        assert _is_test_code_path(path)

    @pytest.mark.parametrize(
        "path",
        [
            # Production siblings of the colocated shapes above.
            "apps/mobile/services/app-restart.ts",
            "apps/web/src/Foo.tsx",
            "packages/api/index.js",
            "plan_tool/review.py",
            # `test`/`tests` as the *basename*, not a parent directory.
            "src/test.ts",
            "src/tests.py",
            # A substring match must not be enough: `latest.ts` ends in
            # "test" + ".ts" but is not `.test.ts`.
            "apps/web/src/latest.ts",
            "apps/web/src/protest.js",
        ],
    )
    def test_rejects_production_code(self, path: str) -> None:
        from plan_tool.review import _is_test_code_path

        assert not _is_test_code_path(path)


def _write_input_contract_plan(
    tmp_path: Path,
    *,
    first_ref: str,
    second_ref: str,
    plan_ref: str | None = None,
) -> Path:
    plan_tool_dir = tmp_path / "plan_tool"
    plan_tool_dir.mkdir()
    (plan_tool_dir / "review_persistence.py").write_text(
        "class SavedReview:\n    pass\n", encoding="utf-8"
    )
    details = tmp_path / "details"
    details.mkdir()
    (details / "01.md").write_text(
        "# Step 1\n\n"
        "## Summary\n\nsummary\n\n"
        "## Table of Contents\n\n- [Input](#input) - input\n\n"
        "## Input\n\n"
        f"Reads `{first_ref}` from `plan_tool/review_persistence.py:SavedReview`.\n\n"
        "## Why\n\nwhy\n\n"
        "## Files\n\nplan_tool/review_persistence.py\n\n"
        "## Implementation\n\nimplementation\n\n"
        "## Tests\n\ntests\n\n"
        "## Acceptance criteria\n\nacceptance\n",
        encoding="utf-8",
    )
    (details / "02.md").write_text(
        "# Step 2\n\n"
        "## Summary\n\nsummary\n\n"
        "## Table of Contents\n\n- [Input](#input) - input\n\n"
        "## Input\n\n"
        f"Reads `{second_ref}` from `plan_tool/review_persistence.py:SavedReview`.\n\n"
        "## Why\n\nwhy\n\n"
        "## Files\n\nplan_tool/review_persistence.py\n\n"
        "## Implementation\n\nimplementation\n\n"
        "## Tests\n\ntests\n\n"
        "## Acceptance criteria\n\nacceptance\n",
        encoding="utf-8",
    )
    plan_path = tmp_path / "p.md"
    input_section = ""
    if plan_ref is not None:
        input_section = (
            "## Input\n\n"
            f"Reads `{plan_ref}` from "
            "`plan_tool/review_persistence.py:SavedReview`.\n\n"
        )
    plan_path.write_text(
        "---\n"
        "title: P\n"
        "status: in-progress\n"
        "priority: medium\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: One\n"
        "    files: [plan_tool/review_persistence.py]\n"
        "    detail: details/01.md\n"
        "  - id: 2\n"
        "    title: Two\n"
        "    files: [plan_tool/review_persistence.py]\n"
        "    detail: details/02.md\n"
        "---\n"
        "# P\n\n"
        f"{input_section}"
        "## Overview\n\nx\n\n"
        "## Problem statement\n\nx\n\n"
        "## Architecture\n\nx\n\n"
        "## References\n\nx\n\n"
        "## Steps\n\nx\n\n"
        "## Out of scope\n\nx\n\n"
        "## Risks\n\nx\n\n"
        "## Testing\n\nx\n\n"
        "## Acceptance criteria\n\nx\n\n"
        "## Deferred\n\nx\n",
        encoding="utf-8",
    )
    return plan_path


def test_collect_deterministic_findings_reports_stale_input_contract_reference(
    tmp_path: Path,
) -> None:
    plan_path = _write_input_contract_plan(
        tmp_path,
        first_ref="SavedReview.not_a_field",
        second_ref="SavedReview.recommendations",
    )
    plan = parse_plan(plan_path)
    recs = collect_deterministic_findings(
        plan, plan_path, repo_root=tmp_path, plan_name="p"
    )
    data_recs = [r for r in recs if r.source == "data-contract"]
    assert len(data_recs) == 1
    assert data_recs[0].id.startswith("step1-data-contract-")
    assert data_recs[0].confidence == "limited"
    assert "SavedReview.not_a_field" in data_recs[0].body


def test_collect_deterministic_findings_reports_plan_input_contract_drift(
    tmp_path: Path,
) -> None:
    plan_path = _write_input_contract_plan(
        tmp_path,
        plan_ref="SavedReview.plan_missing",
        first_ref="SavedReview.recommendations",
        second_ref="SavedReview.recommendations",
    )
    plan = parse_plan(plan_path)
    recs = collect_deterministic_findings(
        plan, plan_path, repo_root=tmp_path, plan_name="p"
    )
    data_recs = [r for r in recs if r.source == "data-contract"]
    assert len(data_recs) == 1
    assert data_recs[0].id.startswith("plan-data-contract-")
    assert data_recs[0].step_id is None
    assert "p.md:## Input" in data_recs[0].body
    assert "SavedReview.plan_missing" in data_recs[0].body


def test_collect_deterministic_findings_reports_detail_input_contract_drift(
    tmp_path: Path,
) -> None:
    plan_path = _write_input_contract_plan(
        tmp_path,
        first_ref="SavedReview.not_a_field",
        second_ref="SavedReview.recommendations",
    )
    plan = parse_plan(plan_path)
    rec = next(
        r
        for r in collect_deterministic_findings(
            plan, plan_path, repo_root=tmp_path, plan_name="p"
        )
        if r.source == "data-contract"
    )
    assert rec.step_id == 1
    assert rec.id.startswith("step1-data-contract-")
    assert rec.anchor == "data-contract-input-savedreview-not-a-field"
    assert "details/01.md:## Input" in rec.body


def test_collect_deterministic_findings_ignores_valid_input_contract_references(
    tmp_path: Path,
) -> None:
    plan_path = _write_input_contract_plan(
        tmp_path,
        plan_ref="SavedReview.recommendations",
        first_ref="SavedReview.version",
        second_ref="SavedReview.recommendations",
    )
    plan = parse_plan(plan_path)
    recs = collect_deterministic_findings(
        plan, plan_path, repo_root=tmp_path, plan_name="p"
    )
    assert [r for r in recs if r.source == "data-contract"] == []


def test_input_contract_recommendation_has_plan_detail_target(tmp_path: Path) -> None:
    plan_path = _write_input_contract_plan(
        tmp_path,
        first_ref="SavedReview.not_a_field",
        second_ref="SavedReview.recommendations",
    )
    plan = parse_plan(plan_path)
    rec = next(
        r
        for r in collect_deterministic_findings(
            plan, plan_path, repo_root=tmp_path, plan_name="p"
        )
        if r.source == "data-contract"
    )
    assert "## Input" in rec.body
    assert rec.suggested_action is not None
    assert "DATA_CONTRACT.md" not in rec.suggested_action


def test_collect_deterministic_findings_respects_step_filter_for_input_contract_references(
    tmp_path: Path,
) -> None:
    plan_path = _write_input_contract_plan(
        tmp_path,
        first_ref="SavedReview.first_missing",
        second_ref="SavedReview.second_missing",
    )
    plan = parse_plan(plan_path)
    recs = collect_deterministic_findings(
        plan, plan_path, repo_root=tmp_path, plan_name="p", step_filter=2
    )
    data_recs = [r for r in recs if r.source == "data-contract"]
    assert len(data_recs) == 1
    assert data_recs[0].step_id == 2
    assert "second_missing" in data_recs[0].body
    assert "first_missing" not in data_recs[0].body


# --- Advisory smell layer --------------------------------------------------

from plan_tool.parser import parse_plan_text
from plan_tool.review import (
    AUDIT_FIX_SOURCES,
    CONCEPT_BUCKET_MISSING_SOURCE,
    CONCEPT_LEGACY_STALE_SOURCE,
    INTENT_PRESENCE_SOURCE,
    PlanFootprint,
    SELF_CONSISTENCY_SOURCES,
    _self_consistency_from_smells,
    build_plan_footprint,
    check_intent_presence,
    collect_self_consistency_findings,
    collect_smell_findings,
    detect_claim_vs_delivery,
    detect_orphaned_deliverable,
    detect_self_referential_features,
    detect_suppression_shape,
    is_usable_intent,
    validate_feature_refs,
)


def _smell_plan_text(
    *,
    features: str = "",
    steps: str,
    title: str = "Smell Test Plan",
    intent: str = "",
) -> str:
    """Assemble a minimal plan-text fixture with optional `features:` block.

    ``intent`` is a whole frontmatter line (e.g. ``'intent: why\\n'``) so a
    caller can omit the key entirely, not just leave it blank."""
    return (
        f"---\ntitle: {title}\n{intent}status: in-progress\npriority: medium\n"
        f"{features}steps:\n{steps}---\n\n# {title}\n"
    )


class TestValidateFeatureRefs:
    def test_clean_registry_no_findings(self) -> None:
        plan = parse_plan_text(
            _smell_plan_text(
                features=(
                    "features:\n"
                    "  - id: feature-one\n    title: Feature One\n"
                    "  - id: feature-two\n    title: Feature Two\n"
                ),
                steps=(
                    "  - id: 1\n    title: Do the thing\n"
                    "    files:\n      - a.py\n"
                    "    features:\n      - feature-one\n"
                ),
            )
        )
        assert validate_feature_refs(plan) == []

    def test_no_features_block_no_findings(self) -> None:
        plan = parse_plan_text(
            _smell_plan_text(
                steps="  - id: 1\n    title: Do the thing\n    files:\n      - a.py\n"
            )
        )
        assert plan.features == []
        assert validate_feature_refs(plan) == []

    def test_duplicate_registry_id_flagged(self) -> None:
        plan = parse_plan_text(
            _smell_plan_text(
                features=(
                    "features:\n"
                    "  - id: feature-one\n    title: Feature One\n"
                    "  - id: feature-one\n    title: Feature One Again\n"
                ),
                steps="  - id: 1\n    title: Do the thing\n    files:\n      - a.py\n",
            )
        )
        recs = validate_feature_refs(plan)
        assert len(recs) == 1
        assert recs[0].source == "feature-ref"
        assert recs[0].severity == "info"
        assert recs[0].step_id is None

    def test_non_kebab_id_flagged(self) -> None:
        for bad in ("Feature_One", "featureOne"):
            plan = parse_plan_text(
                _smell_plan_text(
                    features=f"features:\n  - id: {bad}\n    title: T\n",
                    steps="  - id: 1\n    title: Do it\n    files:\n      - a.py\n",
                )
            )
            recs = validate_feature_refs(plan)
            assert len(recs) == 1, bad
            assert recs[0].source == "feature-ref"
            assert recs[0].step_id is None

    def test_dangling_tag_flagged(self) -> None:
        plan = parse_plan_text(
            _smell_plan_text(
                features="features:\n  - id: feature-one\n    title: Feature One\n",
                steps=(
                    "  - id: 1\n    title: Do it\n    files:\n      - a.py\n"
                    "    features:\n      - ghost\n"
                ),
            )
        )
        recs = validate_feature_refs(plan)
        assert len(recs) == 1
        assert recs[0].source == "feature-ref"
        assert recs[0].step_id == 1
        assert "ghost" in recs[0].body

    def test_tag_without_registry_dangles(self) -> None:
        # A plan that tags steps but declares no registry must not early-return.
        plan = parse_plan_text(
            _smell_plan_text(
                steps=(
                    "  - id: 1\n    title: Do it\n    files:\n      - a.py\n"
                    "    features:\n      - ghost\n"
                ),
            )
        )
        recs = validate_feature_refs(plan)
        assert [r.source for r in recs] == ["feature-ref"]
        assert recs[0].step_id == 1

    def test_never_raises_on_malformed(self) -> None:
        plan = parse_plan_text(
            _smell_plan_text(
                features=(
                    "features:\n"
                    "  - id: Feature_One\n    title: Dup Bad\n"
                    "  - id: Feature_One\n    title: Dup Bad Again\n"
                ),
                steps=(
                    "  - id: 1\n    title: Do it\n    files:\n      - a.py\n"
                    "    features:\n      - ghost\n"
                ),
            )
        )
        recs = validate_feature_refs(plan)
        # duplicate + non-kebab (x1, deduped flag) + dangling — all surface.
        assert all(r.source == "feature-ref" for r in recs)
        assert len(recs) >= 3


def _intent_plan(*, plan_intent: Optional[str], step_intents: list[Optional[str]]):
    """Parse a plan whose intents are exactly as given.

    ``None`` omits the key; any string is emitted verbatim as a YAML double-
    quoted scalar, so ``""`` and ``"   "`` survive the round trip.
    """
    def _line(value: Optional[str], indent: str) -> str:
        if value is None:
            return ""
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        escaped = escaped.replace("\n", "\\n")
        return f'{indent}intent: "{escaped}"\n'

    steps = "".join(
        f"  - id: {i}\n    title: Step {i}\n{_line(value, '    ')}"
        for i, value in enumerate(step_intents, start=1)
    )
    return parse_plan_text(
        _smell_plan_text(steps=steps, intent=_line(plan_intent, ""))
    )


_PLACEHOLDER_INTENTS = ("TODO", "TBD", "_(TODO)_", "(TODO)", "todo")


class TestIsUsableIntent:
    """The shared predicate itself — plain string in, bool out, so a caller
    can judge a candidate line before any ``Plan``/``Step`` exists."""

    def test_real_prose_is_usable(self) -> None:
        assert is_usable_intent("ship the field end to end") is True

    def test_none_is_not_usable(self) -> None:
        assert is_usable_intent(None) is False

    def test_empty_string_is_not_usable(self) -> None:
        # Pins emptiness-before-placeholder: the placeholder helper calls ""
        # a non-placeholder, so the ordering is what makes this False.
        assert is_usable_intent("") is False

    def test_whitespace_only_is_not_usable(self) -> None:
        assert is_usable_intent("   \t ") is False

    @pytest.mark.parametrize("marker", _PLACEHOLDER_INTENTS)
    def test_placeholder_markers_are_not_usable(self, marker: str) -> None:
        assert is_usable_intent(marker) is False, marker

    def test_marker_word_inside_real_prose_is_usable(self) -> None:
        assert is_usable_intent("ship the TODO list view") is True

    def test_long_or_vague_values_are_usable(self) -> None:
        # No quality or length judgment lives here.
        assert is_usable_intent("x" * 500) is True
        assert is_usable_intent("stuff") is True

    def test_private_name_is_gone(self) -> None:
        # Guards against an alias or leftover wrapper reintroducing a second
        # name for the one predicate.
        import plan_tool.review as review_module

        assert not hasattr(review_module, "_is_usable_intent")


class TestCheckIntentPresence:
    """Presence, and nothing else: no case here asserts anything about an
    intent's content, shape, or length."""

    def test_plan_and_step_intents_present_yield_nothing(self) -> None:
        plan = _intent_plan(
            plan_intent="Fence every prompt with the plan's why",
            step_intents=["Make the field parseable", "Nudge when it is absent"],
        )
        assert check_intent_presence(plan) == []

    def test_missing_plan_intent_yields_one_finding(self) -> None:
        plan = _intent_plan(plan_intent=None, step_intents=["why this step"])
        recs = check_intent_presence(plan)
        assert len(recs) == 1
        assert recs[0].step_id is None
        assert "Plan" in recs[0].title

    def test_missing_step_intent_yields_one_rollup(self) -> None:
        plan = _intent_plan(plan_intent="why", step_intents=[None, None, None])
        recs = check_intent_presence(plan)
        assert len(recs) == 1
        assert recs[0].step_id is None

    def test_rollup_names_every_missing_step_id(self) -> None:
        plan = _intent_plan(plan_intent="why", step_intents=[None, None, None])
        body = check_intent_presence(plan)[0].body
        assert "1, 2, 3" in body

    def test_rollup_omits_steps_that_have_an_intent(self) -> None:
        plan = _intent_plan(
            plan_intent="why", step_intents=[None, "a real why", None]
        )
        recs = check_intent_presence(plan)
        assert len(recs) == 1
        assert "1, 3" in recs[0].body
        assert "2" not in recs[0].suggested_action

    def test_both_altitudes_report_independently(self) -> None:
        plan = _intent_plan(plan_intent=None, step_intents=[None, None])
        assert len(check_intent_presence(plan)) == 2

    def test_cap_holds_as_step_count_grows(self) -> None:
        # The whole design decision: volume is per plan, never per step.
        for count in (1, 11):
            plan = _intent_plan(plan_intent=None, step_intents=[None] * count)
            assert len(check_intent_presence(plan)) == 2, count

    def test_empty_string_intent_counts_as_missing(self) -> None:
        plan = _intent_plan(plan_intent="", step_intents=[""])
        assert len(check_intent_presence(plan)) == 2

    def test_whitespace_only_intent_counts_as_missing(self) -> None:
        plan = _intent_plan(plan_intent="   ", step_intents=["  \t "])
        assert len(check_intent_presence(plan)) == 2

    @pytest.mark.parametrize("marker", _PLACEHOLDER_INTENTS)
    def test_placeholder_intents_count_as_missing(self, marker: str) -> None:
        plan = _intent_plan(plan_intent=marker, step_intents=[marker])
        assert len(check_intent_presence(plan)) == 2, marker

    def test_todo_inside_real_prose_is_not_a_placeholder(self) -> None:
        plan = _intent_plan(
            plan_intent="ship the TODO list view",
            step_intents=["ship the TODO list view"],
        )
        assert check_intent_presence(plan) == []

    def test_findings_are_medium_severity(self) -> None:
        # ``medium`` is what makes the missing intent block: it is the
        # threshold ``_completeness_has_blocking_findings`` reads.
        plan = _intent_plan(plan_intent=None, step_intents=[None])
        assert [r.severity for r in check_intent_presence(plan)] == [
            "medium",
            "medium",
        ]

    def test_findings_carry_the_intent_presence_source(self) -> None:
        plan = _intent_plan(plan_intent=None, step_intents=[None])
        assert {r.source for r in check_intent_presence(plan)} == {
            INTENT_PRESENCE_SOURCE
        }

    def test_finding_text_is_identical_whatever_the_non_value_was(self) -> None:
        # The anti-echo property stated positively: the finding cannot depend
        # on the value it read, because it never reads it into the text.
        renderings = {
            tuple(
                (r.id, r.title, r.body, r.suggested_action)
                for r in check_intent_presence(
                    _intent_plan(plan_intent=value, step_intents=[value])
                )
            )
            for value in (None, "", "   ", *_PLACEHOLDER_INTENTS)
        }
        assert len(renderings) == 1

    def test_finding_never_carries_a_forged_heading(self) -> None:
        # A newline-bearing intent could otherwise open a line with ``##`` and
        # forge a heading in the rendered markdown report.
        plan = _intent_plan(
            plan_intent="why\n## Injected heading", step_intents=[None]
        )
        recs = check_intent_presence(plan)
        assert recs
        for rec in recs:
            for field in (rec.title, rec.body, rec.suggested_action or ""):
                assert "Injected heading" not in field
                assert "#" not in field

    def test_source_routes_to_self_consistency_and_nowhere_else(self) -> None:
        # The blocking bucket is the *only* set it joins: an apply pass is a
        # prose editor and would corrupt its own pre/post delta on a
        # frontmatter field.
        assert INTENT_PRESENCE_SOURCE in SELF_CONSISTENCY_SOURCES
        assert INTENT_PRESENCE_SOURCE not in APPLY_ELIGIBLE_SOURCES
        assert INTENT_PRESENCE_SOURCE not in STRUCTURAL_SOURCES
        assert INTENT_PRESENCE_SOURCE not in AUDIT_FIX_SOURCES

    def test_is_apply_eligible_and_is_structural_are_false(self) -> None:
        plan = _intent_plan(plan_intent=None, step_intents=[None])
        for rec in check_intent_presence(plan):
            assert is_apply_eligible(rec) is False
            assert is_structural(rec) is False

    def test_triage_reason_is_intent_specific(self) -> None:
        plan = _intent_plan(plan_intent=None, step_intents=[None])
        for rec in check_intent_presence(plan):
            reason = triage_reason(rec)
            assert "intent" in reason
            assert "author lessons" not in reason
            # No longer advisory, and the reason must say so rather than
            # describing a finding that now halts the loop as skippable.
            assert "advisory" not in reason
            assert "add a one-line `intent:`" in reason

    def test_rec_ids_are_stable_across_two_runs(self) -> None:
        plan = _intent_plan(plan_intent=None, step_intents=[None, "why", None])
        first = [r.id for r in check_intent_presence(plan)]
        assert first == [r.id for r in check_intent_presence(plan)]

    def test_intent_finding_ids_are_unchanged_by_the_promotion(self) -> None:
        # ``_make_rec_id`` hashes the fingerprint, never the severity, so a
        # saved sidecar does not re-report the promoted finding as a new one.
        # These are the exact strings the fan-out characterization map pins.
        plan = _intent_plan(plan_intent=None, step_intents=[None])
        assert [r.id for r in check_intent_presence(plan)] == [
            "plan-intent-presence-59e905f4",
            "plan-intent-presence-2e2ad0b9",
        ]

    def test_long_or_vague_intent_yields_nothing(self) -> None:
        for value in ("x" * 500, "stuff"):
            plan = _intent_plan(plan_intent=value, step_intents=[value])
            assert check_intent_presence(plan) == [], value


def _write_suppression_plan(
    tmp_path: Path,
    *,
    title: str,
    detail_body: Optional[str] = None,
) -> Plan:
    """Write a one-step plan (optionally with a detail file) and parse it."""
    steps = f"  - id: 1\n    title: {title}\n    files:\n      - a.py\n"
    if detail_body is not None:
        (tmp_path / "details").mkdir(exist_ok=True)
        (tmp_path / "details" / "step-1.md").write_text(
            detail_body, encoding="utf-8"
        )
        steps += "    detail: details/step-1.md\n"
    plan_path = tmp_path / "1-suppression.md"
    plan_path.write_text(_smell_plan_text(steps=steps), encoding="utf-8")
    return parse_plan(plan_path)


class TestSuppressionShape:
    def test_title_states_suppression_trips(self, tmp_path: Path) -> None:
        plan = _write_suppression_plan(tmp_path, title="Bypass the purity gate")
        recs = detect_suppression_shape(plan, tmp_path, plan_name="p")
        assert len(recs) == 1
        assert recs[0].source == "suppression-shape"
        assert recs[0].severity == "medium"
        assert recs[0].step_id == 1

    def test_suppression_severity_is_medium(self, tmp_path: Path) -> None:
        # Elevated from info so the completeness gate can block on it once it's
        # routed onto the self_consistency bucket.
        plan = _write_suppression_plan(tmp_path, title="Suppress the audit gate")
        recs = detect_suppression_shape(plan, tmp_path, plan_name="p")
        assert len(recs) == 1
        assert recs[0].source == "suppression-shape"
        assert recs[0].severity == "medium"

    def test_body_states_suppression_trips(self, tmp_path: Path) -> None:
        body = (
            "## Summary\n\nRefine the renderer.\n\n"
            "## Why\n\nWe need to downgrade the mixed-step finding so it "
            "stops complaining.\n"
        )
        plan = _write_suppression_plan(
            tmp_path, title="Refine the renderer", detail_body=body
        )
        recs = detect_suppression_shape(plan, tmp_path, plan_name="p")
        assert len(recs) == 1
        assert recs[0].source == "suppression-shape"

    def test_self_describing_detector_does_not_trip(
        self, tmp_path: Path
    ) -> None:
        body = (
            "## Summary\n\nAdNo-Claude smell detector "
            "detect_suppression_shape (a step/feature whose own deliverable "
            "suppresses an existing audit gate).\n\n"
            "## Why\n\nSurface brittle shapes at author time.\n"
        )
        plan = _write_suppression_plan(
            tmp_path, title="Add the suppression detector", detail_body=body
        )
        assert detect_suppression_shape(plan, tmp_path, plan_name="p") == []

    def test_class_of_units_reasoning_does_not_trip(
        self, tmp_path: Path
    ) -> None:
        body = (
            "## Summary\n\nDescribe the audit.\n\n"
            "## Why\n\nWe flag any step that suppresses an audit gate.\n"
        )
        plan = _write_suppression_plan(
            tmp_path, title="Describe the audit", detail_body=body
        )
        assert detect_suppression_shape(plan, tmp_path, plan_name="p") == []

    def test_deliberate_design_statement_does_not_trip(
        self, tmp_path: Path
    ) -> None:
        # A documented, intentional no-sidecar policy must not become a
        # blocking false positive that forces the author to rewrite true prose.
        body = (
            "## Summary\n\nRecord the output contract.\n\n"
            "## Why\n\nThis design deliberately suppresses the JSON "
            "findings sidecar because the command writes no sidecar.\n"
        )
        plan = _write_suppression_plan(
            tmp_path, title="Document the output contract", detail_body=body
        )
        assert detect_suppression_shape(plan, tmp_path, plan_name="p") == []

    def test_bare_step_no_features_block_still_checked(
        self, tmp_path: Path
    ) -> None:
        # No features: block, no detail file — title-only scan still trips.
        plan = _write_suppression_plan(
            tmp_path, title="Silence the mixed-step finding"
        )
        assert plan.features == []
        recs = detect_suppression_shape(plan, tmp_path, plan_name="p")
        assert len(recs) == 1
        assert recs[0].source == "suppression-shape"

    def test_undetailed_plan_does_not_crash(self, tmp_path: Path) -> None:
        # step.detail is None — must short-circuit before repo_root / None.
        plan = _write_suppression_plan(tmp_path, title="Add a feature")
        assert detect_suppression_shape(plan, tmp_path, plan_name="p") == []

    def test_suppression_shape_scans_canonical_summary_why(
        self, tmp_path: Path
    ) -> None:
        # Plan ``1-suppression.md`` → bundle ``plan-details/suppression/``;
        # step 1 "Refine the renderer" → canonical ``01-refine-renderer.md``.
        body = (
            "## Summary\n\nRefine the renderer.\n\n"
            "## Why\n\nWe need to downgrade the mixed-step finding so it "
            "stops complaining.\n"
        )
        plan = _write_suppression_plan(tmp_path, title="Refine the renderer")
        plan_path = tmp_path / "1-suppression.md"
        bundle = tmp_path / "plan-details" / "suppression"
        bundle.mkdir(parents=True)
        (bundle / "01-refine-renderer.md").write_text(body, encoding="utf-8")

        # Title alone is innocuous, and without a plan path the canonical body
        # is invisible.
        assert detect_suppression_shape(plan, tmp_path, plan_name="p") == []

        recs = detect_suppression_shape(
            plan, tmp_path, plan_name="p", plan_path=plan_path
        )
        assert len(recs) == 1
        assert recs[0].source == "suppression-shape"
        assert recs[0].step_id == 1

    def test_real_detail_bundle_self_flags_nothing(self) -> None:
        from plan_tool.locator import load_manifest_plan_paths

        repo_root = Path(__file__).resolve().parents[1]
        target = None
        for path in load_manifest_plan_paths(repo_root):
            if not path.is_file():
                continue
            try:
                candidate = parse_plan(path)
            except Exception:
                continue
            if candidate.title == "Feature Health Declaration And Smell Checks":
                target = candidate
                break
        if target is None:
            pytest.skip(
                "plan 'Feature Health Declaration And Smell Checks' not "
                "resolvable by title"
            )
        recs = collect_smell_findings(
            target, repo_root, plan_name=target.title
        )
        supp = [r for r in recs if r.source == "suppression-shape"]
        assert supp == [], (
            "shipped detector self-flagged its own live prose: "
            f"{[r.title for r in supp]}"
        )


def _write_orphan_plan(
    tmp_path: Path,
    step_specs: list[dict],
    *,
    title: str = "Orphan Test Plan",
    plan_body: str = "",
    intent: Optional[str] = None,
) -> tuple[Plan, Path]:
    """Write a plan whose steps carry optional ``creates:``/``files:`` and a
    detail file, then parse it. Each spec: ``{id, title, creates?, files?,
    status?, detail_body?, intent?}``. ``plan_body`` is markdown appended below
    the plan's ``# Title`` heading (e.g. a ``## Overview`` / ``## Deferred``).
    ``intent`` (plan-level) and a spec's ``intent`` (step-level) default to
    absent, which the blocking ``intent-presence`` check flags — pass both to
    build a fixture that is clean against every detector."""
    details_dir = tmp_path / "details"
    steps_yaml = ""
    for spec in step_specs:
        sid = spec["id"]
        steps_yaml += f"  - id: {sid}\n    title: {spec['title']}\n"
        if spec.get("intent"):
            steps_yaml += f"    intent: {spec['intent']}\n"
        for key in ("creates", "files"):
            if spec.get(key):
                steps_yaml += f"    {key}:\n"
                for p in spec[key]:
                    steps_yaml += f"      - {p}\n"
        if spec.get("status"):
            steps_yaml += f"    status: {spec['status']}\n"
        if spec.get("detail_body") is not None:
            details_dir.mkdir(exist_ok=True)
            rel = f"details/step-{sid}.md"
            (tmp_path / rel).write_text(spec["detail_body"], encoding="utf-8")
            steps_yaml += f"    detail: {rel}\n"
    text = (
        _smell_plan_text(
            steps=steps_yaml,
            title=title,
            intent=f"intent: {intent}\n" if intent else "",
        )
        + plan_body
    )
    plan_path = tmp_path / "1-orphan.md"
    plan_path.write_text(text, encoding="utf-8")
    return parse_plan(plan_path), plan_path


class TestBuildPlanFootprint:
    def test_build_plan_footprint_collects_declared_paths_and_symbols(
        self, tmp_path: Path
    ) -> None:
        plan, _ = _write_orphan_plan(
            tmp_path,
            [
                {
                    "id": 1,
                    "title": "Ship",
                    "creates": ["pkg/orphan_widget.py"],
                    "files": ["lib/helper_core.py"],
                }
            ],
        )
        fp = build_plan_footprint(plan, tmp_path)
        assert isinstance(fp, PlanFootprint)
        assert "pkg/orphan_widget.py" in fp.declared_paths
        assert "lib/helper_core.py" in fp.declared_paths
        assert "orphan_widget" in fp.declared_symbols
        assert "helper_core" in fp.declared_symbols
        assert fp.declared_paths_by_step[1] == frozenset(
            {"pkg/orphan_widget.py", "lib/helper_core.py"}
        )

    def test_build_plan_footprint_collects_references_from_detail_and_claims(
        self, tmp_path: Path
    ) -> None:
        detail = (
            "## Summary\n\nWork.\n\n"
            "## Implementation\n\nEdits `pkg/orphan_widget.py`.\n\n"
            "## Acceptance criteria\n\nThe `pkg/consumer_module.py` calls it.\n"
        )
        plan, plan_path = _write_orphan_plan(
            tmp_path,
            [{"id": 1, "title": "Ship", "detail_body": detail}],
            plan_body="\n## Overview\n\nDelivers `pkg/overview_ref.py` end to end.\n",
        )
        fp = build_plan_footprint(plan, tmp_path, plan_path=plan_path)
        # (a) path mention in the detail body.
        assert "pkg/orphan_widget.py" in fp.referenced_paths_by_step[1]
        # (c) claim prose from the detail acceptance + the plan overview.
        assert "pkg/consumer_module.py" in fp.claim_paths
        assert "pkg/overview_ref.py" in fp.claim_paths

    def test_plan_footprint_referenced_side_includes_canonical_body(
        self, tmp_path: Path
    ) -> None:
        # Plan ``1-orphan.md`` → bundle ``plan-details/orphan/``; step 1
        # "Ship" → canonical ``01-ship.md``. With ``plan_path`` its path
        # mentions land on the referenced side even though no pointer is set.
        plan, plan_path = _write_orphan_plan(
            tmp_path, [{"id": 1, "title": "Ship"}]
        )
        bundle = tmp_path / "plan-details" / "orphan"
        bundle.mkdir(parents=True)
        (bundle / "01-ship.md").write_text(
            "## Summary\n\nWork.\n\n"
            "## Implementation\n\nEdits `pkg/orphan_widget.py`.\n",
            encoding="utf-8",
        )
        assert build_plan_footprint(plan, tmp_path).referenced_paths_by_step[
            1
        ] == frozenset()
        fp = build_plan_footprint(plan, tmp_path, plan_path=plan_path)
        assert "pkg/orphan_widget.py" in fp.referenced_paths_by_step[1]

    def test_build_plan_footprint_opens_no_source_files(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        import pathlib

        (tmp_path / "pkg").mkdir()
        (tmp_path / "pkg" / "orphan_widget.py").write_text(
            "SECRET = 1\n", encoding="utf-8"
        )
        plan, plan_path = _write_orphan_plan(
            tmp_path,
            [
                {
                    "id": 1,
                    "title": "Ship",
                    "creates": ["pkg/orphan_widget.py"],
                    "detail_body": "## Summary\n\nShip it.\n",
                }
            ],
        )
        read_paths: list[str] = []
        orig = pathlib.Path.read_text

        def spy(self, *a, **k):
            read_paths.append(str(self))
            return orig(self, *a, **k)

        monkeypatch.setattr(pathlib.Path, "read_text", spy)
        build_plan_footprint(plan, tmp_path, plan_path=plan_path)
        assert read_paths, "expected to read plan/detail markdown"
        assert not any(p.endswith(".py") for p in read_paths)


# A detail body that ships a deliverable and defers its wiring — the orphan shape.
def _orphan_detail(path: str) -> str:
    return (
        "## Summary\n\nShip the primitive.\n\n"
        f"## Deferred\n\nWiring `{path}` into its caller is deferred to a "
        "later plan.\n"
    )


class TestOrphanedDeliverable:
    def test_orphaned_deliverable_trips_on_deferred_unconsumed_creates(
        self, tmp_path: Path
    ) -> None:
        plan, plan_path = _write_orphan_plan(
            tmp_path,
            [
                {
                    "id": 1,
                    "title": "Ship the widget",
                    "creates": ["pkg/orphan_widget.py"],
                    "detail_body": _orphan_detail("pkg/orphan_widget.py"),
                }
            ],
        )
        recs = detect_orphaned_deliverable(
            plan, tmp_path, plan_name="p", plan_path=plan_path
        )
        assert len(recs) == 1
        assert recs[0].source == "orphaned-deliverable"
        assert recs[0].severity == "medium"
        assert recs[0].step_id == 1
        assert "pkg/orphan_widget.py" in recs[0].title

    def test_orphaned_deliverable_no_trip_when_consumer_step_exists(
        self, tmp_path: Path
    ) -> None:
        consumer = (
            "## Summary\n\nConsume the widget.\n\n"
            "## Implementation\n\nCalls into `pkg/orphan_widget.py`.\n"
        )
        plan, plan_path = _write_orphan_plan(
            tmp_path,
            [
                {
                    "id": 1,
                    "title": "Ship the widget",
                    "creates": ["pkg/orphan_widget.py"],
                    "detail_body": _orphan_detail("pkg/orphan_widget.py"),
                },
                {"id": 2, "title": "Use the widget", "detail_body": consumer},
            ],
        )
        assert (
            detect_orphaned_deliverable(
                plan, tmp_path, plan_name="p", plan_path=plan_path
            )
            == []
        )

    def test_orphaned_deliverable_no_trip_when_consumer_is_fenced_example(
        self, tmp_path: Path
    ) -> None:
        consumer = (
            "## Implementation\n\n"
            "```python\n"
            "# The sample wires `pkg/orphan_widget.py` into the caller.\n"
            "```\n"
        )
        plan, plan_path = _write_orphan_plan(
            tmp_path,
            [
                {
                    "id": 1,
                    "title": "Ship the widget",
                    "creates": ["pkg/orphan_widget.py"],
                    "detail_body": _orphan_detail("pkg/orphan_widget.py"),
                },
                {
                    "id": 2,
                    "title": "Use the widget",
                    "detail_body": consumer,
                },
            ],
        )

        assert (
            detect_orphaned_deliverable(
                plan, tmp_path, plan_name="p", plan_path=plan_path
            )
            == []
        )

    def test_orphaned_deliverable_no_trip_when_claim_references_it(
        self, tmp_path: Path
    ) -> None:
        detail = (
            "## Summary\n\nShip it.\n\n"
            "## Deferred\n\nWiring `pkg/orphan_widget.py` is deferred.\n\n"
            "## Acceptance criteria\n\n`pkg/orphan_widget.py` is exercised by "
            "the new suite.\n"
        )
        plan, plan_path = _write_orphan_plan(
            tmp_path,
            [
                {
                    "id": 1,
                    "title": "Ship the widget",
                    "creates": ["pkg/orphan_widget.py"],
                    "detail_body": detail,
                }
            ],
        )
        assert (
            detect_orphaned_deliverable(
                plan, tmp_path, plan_name="p", plan_path=plan_path
            )
            == []
        )

    def test_orphaned_deliverable_no_trip_when_wiring_not_deferred(
        self, tmp_path: Path
    ) -> None:
        plan, plan_path = _write_orphan_plan(
            tmp_path,
            [
                {
                    "id": 1,
                    "title": "Ship the widget",
                    "creates": ["pkg/orphan_widget.py"],
                    "detail_body": "## Summary\n\nShip the widget.\n",
                }
            ],
        )
        assert (
            detect_orphaned_deliverable(
                plan, tmp_path, plan_name="p", plan_path=plan_path
            )
            == []
        )

    def test_orphaned_deliverable_skips_done_steps(self, tmp_path: Path) -> None:
        plan, plan_path = _write_orphan_plan(
            tmp_path,
            [
                {
                    "id": 1,
                    "title": "Ship the widget",
                    "creates": ["pkg/orphan_widget.py"],
                    "status": "done",
                    "detail_body": _orphan_detail("pkg/orphan_widget.py"),
                },
                {"id": 2, "title": "Later unrelated step"},
            ],
        )
        assert (
            detect_orphaned_deliverable(
                plan, tmp_path, plan_name="p", plan_path=plan_path
            )
            == []
        )

    def test_orphaned_deliverable_reproduces_prompt_budget_shape(
        self, tmp_path: Path
    ) -> None:
        # #95-shaped: a primitive shipped, its only consumer deferred to a
        # future plan — nothing in-scope wires it.
        path = "plan_tool/prompt_budget_advisory.py"
        detail = (
            "## Summary\n\nAdd the prompt-budget advisory primitive.\n\n"
            f"## Deferred\n\nCalling `{path}` from the run loop is deferred to "
            "a follow-up plan; this plan only ships the primitive.\n"
        )
        plan, plan_path = _write_orphan_plan(
            tmp_path,
            [{"id": 1, "title": "Add advisory", "creates": [path],
              "detail_body": detail}],
        )
        recs = detect_orphaned_deliverable(
            plan, tmp_path, plan_name="p", plan_path=plan_path
        )
        assert len(recs) == 1
        assert recs[0].source == "orphaned-deliverable"
        assert path in recs[0].title

    def test_orphaned_deliverable_no_trip_on_coincidental_plan_out_of_scope_symbol(
        self, tmp_path: Path
    ) -> None:
        # Plan-wide ``## Out of scope`` names the deliverable's own path-derived
        # symbol (``cache``) as bare prose, not its path. Pre-fix this tripped
        # condition 4 via a plan-level symbol match (a false positive); the fix
        # matches plan-level deferral on the explicit path only, so it must NOT
        # trip. (The word is `cache` verbatim, not "caching" — there is no
        # stemming, so a non-matching word would guard nothing.)
        plan, plan_path = _write_orphan_plan(
            tmp_path,
            [{"id": 1, "title": "Ship cache", "creates": ["pkg/cache.py"]}],
            plan_body="\n## Out of scope\n\nThe cache mechanism is out of scope.\n",
        )
        assert (
            detect_orphaned_deliverable(
                plan, tmp_path, plan_name="p", plan_path=plan_path
            )
            == []
        )

    def test_orphaned_deliverable_trips_despite_shared_directory_sibling(
        self, tmp_path: Path
    ) -> None:
        # Two steps declare files in the same non-stopword directory, and the
        # sibling's prose even names that directory word. The shared directory
        # token must NOT cross-suppress: step 1's deliverable is genuinely
        # orphaned (deferred, unconsumed) and its finding must still fire.
        # Guards that identity symbols are filename-derived (no `billing`).
        plan, plan_path = _write_orphan_plan(
            tmp_path,
            [
                {
                    "id": 1,
                    "title": "Ship the report",
                    "creates": ["billing/report.py"],
                    "detail_body": _orphan_detail("billing/report.py"),
                },
                {
                    "id": 2,
                    "title": "Unrelated invoice work",
                    "creates": ["billing/invoice.py"],
                    "detail_body": "## Summary\n\nInvoice work for the "
                    "billing system.\n",
                },
            ],
        )
        recs = detect_orphaned_deliverable(
            plan, tmp_path, plan_name="p", plan_path=plan_path
        )
        assert len(recs) == 1
        assert recs[0].step_id == 1
        assert "billing/report.py" in recs[0].title

    def test_orphaned_deliverable_no_trip_when_claim_names_package_token(
        self, tmp_path: Path
    ) -> None:
        # Condition 3 matches the deliverable against its *own* claim prose,
        # where the directory/package token is a legitimate reference. A claim
        # naming the package word (`payments`) must still suppress — so the
        # full path-derived identity (not the filename-only condition-2 set)
        # feeds condition 3. The step also defers by path so the finding would
        # fire were condition 3 not suppressing it.
        plan, plan_path = _write_orphan_plan(
            tmp_path,
            [
                {
                    "id": 1,
                    "title": "Ship the handler",
                    "creates": ["payments/handler.py"],
                    "detail_body": _orphan_detail("payments/handler.py"),
                }
            ],
            plan_body="\n## Acceptance criteria\n\nThe `payments` subsystem is "
            "delivered end to end.\n",
        )
        assert (
            detect_orphaned_deliverable(
                plan, tmp_path, plan_name="p", plan_path=plan_path
            )
            == []
        )

    def test_orphaned_deliverable_trips_when_own_deferred_names_package_token(
        self, tmp_path: Path
    ) -> None:
        # Condition 4 matches the deliverable against its *own* ## Deferred
        # prose. A step that defers its deliverable by the package word
        # (`billing`, not the path or `report`) must still satisfy condition 4
        # and fire — so the full path-derived identity feeds condition 4.
        detail = (
            "## Summary\n\nShip the report.\n\n"
            "## Deferred\n\nWiring the `billing` layer is deferred to a "
            "follow-up plan.\n"
        )
        plan, plan_path = _write_orphan_plan(
            tmp_path,
            [
                {
                    "id": 1,
                    "title": "Ship the report",
                    "creates": ["billing/report.py"],
                    "detail_body": detail,
                }
            ],
        )
        recs = detect_orphaned_deliverable(
            plan, tmp_path, plan_name="p", plan_path=plan_path
        )
        assert len(recs) == 1
        assert "billing/report.py" in recs[0].title

    def test_orphaned_deliverable_trips_on_plan_level_deferred_path(
        self, tmp_path: Path
    ) -> None:
        # Plan-level deferral still trips when it names the deliverable's
        # explicit *path* (the specific, intended plan-scope signal).
        path = "pkg/orphan_widget.py"
        plan, plan_path = _write_orphan_plan(
            tmp_path,
            [{"id": 1, "title": "Ship the widget", "creates": [path]}],
            plan_body=f"\n## Deferred\n\nWiring `{path}` is deferred to a "
            "follow-up plan.\n",
        )
        recs = detect_orphaned_deliverable(
            plan, tmp_path, plan_name="p", plan_path=plan_path
        )
        assert len(recs) == 1
        assert recs[0].source == "orphaned-deliverable"
        assert path in recs[0].title


class TestCollectSelfConsistencyFindings:
    """The blocking-capable self-consistency battery the ``--iterate`` loop's
    blocking signal shares with the finalize gate. Membership must match
    ``_run_deterministic_checks``'s ``self_consistency_recs`` (single-sourced
    via ``_self_consistency_from_smells``) so the loop can't falsely converge
    while the gate flips rc — the BUG_BACKLOG defect this closes."""


    def test_includes_orphaned_deliverable(self, tmp_path: Path) -> None:
        # The fixture declares no intent, so the two intent recs ride the same
        # bucket — smell-derived first, ``orphaned-deliverable`` last.
        plan, plan_path = _write_orphan_plan(
            tmp_path,
            [
                {
                    "id": 1,
                    "title": "Ship the widget",
                    "creates": ["pkg/orphan_widget.py"],
                    "detail_body": _orphan_detail("pkg/orphan_widget.py"),
                }
            ],
        )
        recs = collect_self_consistency_findings(
            plan, tmp_path, plan_name="p", plan_path=plan_path
        )
        assert [r.source for r in recs] == [
            "intent-presence",
            "intent-presence",
            "orphaned-deliverable",
        ]
        assert all(r.source in SELF_CONSISTENCY_SOURCES for r in recs)

    def test_parity_with_deterministic_checks_battery(
        self, tmp_path: Path
    ) -> None:
        # The loop's collector must equal what ``_run_deterministic_checks``
        # partitions into ``self_consistency_recs`` (suppression-shape off the
        # smells + orphaned-deliverable), so the loop's blocking signal and the
        # gate can never disagree.
        plan, plan_path = _write_orphan_plan(
            tmp_path,
            [
                {
                    "id": 1,
                    "title": "Ship the widget",
                    "creates": ["pkg/orphan_widget.py"],
                    "detail_body": _orphan_detail("pkg/orphan_widget.py"),
                }
            ],
        )
        loop_recs = collect_self_consistency_findings(
            plan, tmp_path, plan_name="p", plan_path=plan_path
        )
        smells = collect_smell_findings(
            plan, tmp_path, plan_name="p", plan_path=plan_path
        )
        gate_recs = [
            r for r in smells if r.source in SELF_CONSISTENCY_SOURCES
        ] + detect_orphaned_deliverable(
            plan, tmp_path, plan_name="p", plan_path=plan_path
        )
        assert [r.id for r in loop_recs] == [r.id for r in gate_recs]

    def test_clean_plan_yields_no_self_consistency_findings(
        self, tmp_path: Path
    ) -> None:
        # Genuinely clean means intent-bearing too, now that a missing intent
        # blocks: a fixture without one is no longer a clean-plan control.
        plan, plan_path = _write_orphan_plan(
            tmp_path,
            [
                {
                    "id": 1,
                    "title": "A clean step",
                    "files": ["pkg/mod.py"],
                    "intent": "why the clean step exists",
                }
            ],
            intent="why the clean plan exists",
        )
        assert (
            collect_self_consistency_findings(
                plan, tmp_path, plan_name="p", plan_path=plan_path
            )
            == []
        )

    def test_plan_with_intent_yields_no_self_consistency_findings(
        self, tmp_path: Path
    ) -> None:
        # The positive control for the promotion: supplying both altitudes'
        # intents is what empties the bucket, so the check reads presence and
        # nothing about the value.
        plan, plan_path = _write_orphan_plan(
            tmp_path,
            [
                {"id": 1, "title": "First", "intent": "why the first step"},
                {"id": 2, "title": "Second", "intent": "why the second step"},
            ],
            intent="why this plan exists",
        )
        assert plan.intent == "why this plan exists"
        assert (
            collect_self_consistency_findings(
                plan, tmp_path, plan_name="p", plan_path=plan_path
            )
            == []
        )

    def test_intent_presence_reaches_the_blocking_bucket_from_both_paths(
        self, tmp_path: Path
    ) -> None:
        # The ``--iterate`` collector and the finalize partition must agree on
        # the promoted finding — same recs, same order, or the loop converges
        # while the gate blocks.
        plan, plan_path = _write_orphan_plan(
            tmp_path, [{"id": 1, "title": "A step", "files": ["pkg/mod.py"]}]
        )
        loop_recs = collect_self_consistency_findings(
            plan, tmp_path, plan_name="p", plan_path=plan_path
        )
        smells = collect_smell_findings(
            plan, tmp_path, plan_name="p", plan_path=plan_path
        )
        gate_recs = _self_consistency_from_smells(
            smells, plan, tmp_path, plan_name="p", plan_path=plan_path
        )
        assert [r.id for r in loop_recs] == [r.id for r in gate_recs]
        assert [r.source for r in loop_recs] == [
            "intent-presence",
            "intent-presence",
        ]
        assert all(r.severity == "medium" for r in loop_recs)


def _fanout_corpus(tmp_path: Path) -> list[tuple[str, "Plan", Path, Path]]:
    """Fixtures that between them trip every detector inside the two
    deterministic fan-outs — ``collect_smell_findings``' five and
    ``_self_consistency_from_smells``' one.

    Returns ``(name, plan, plan_path, repo_root)``; each fixture gets its own
    root so the footprint detectors resolve paths independently."""
    corpus: list[tuple[str, "Plan", Path, Path]] = []

    clean_root = tmp_path / "clean"
    clean_root.mkdir()
    plan, plan_path = _write_orphan_plan(
        clean_root, [{"id": 1, "title": "A clean step", "files": ["pkg/mod.py"]}]
    )
    corpus.append(("clean", plan, plan_path, clean_root))

    # feature-ref (ghost id) + suppression-shape (bypass verb on a validation
    # machinery path) + self-referential (the same path is the audit's own).
    smell_root = tmp_path / "smells"
    smell_root.mkdir()
    _write_machinery_config(smell_root, ["plan_tool/review.py"])
    smell_path = smell_root / "1-smells.md"
    smell_path.write_text(
        _smell_plan_text(
            features=(
                "features:\n"
                "  - id: feature-one\n    title: Feature One\n"
                "  - id: Feature_Two\n    title: Feature Two\n"
            ),
            steps=(
                "  - id: 1\n    title: Bypass the purity gate\n"
                "    files:\n      - plan_tool/review.py\n"
                "    features:\n      - feature-one\n      - ghost\n"
            ),
        ),
        encoding="utf-8",
    )
    corpus.append(("smells", parse_plan(smell_path), smell_path, smell_root))

    # orphaned-deliverable (deferred, unconsumed ``creates:``) alongside
    # claim-vs-delivery (an acceptance criterion no step delivers).
    orphan_root = tmp_path / "orphan"
    orphan_root.mkdir()
    plan, plan_path = _write_orphan_plan(
        orphan_root,
        [
            {
                "id": 1,
                "title": "Ship the widget",
                "creates": ["pkg/orphan_widget.py"],
                "detail_body": _orphan_detail("pkg/orphan_widget.py"),
            }
        ],
        plan_body="\n## Acceptance criteria\n\n- `pkg/never_built.py` exists.\n",
    )
    corpus.append(("orphan", plan, plan_path, orphan_root))

    concept_root = tmp_path / "concepts"
    concept_root.mkdir()
    plan, plan_path, _ = _write_concept_coverage_fixture(concept_root)
    corpus.append(("concepts", plan, plan_path, concept_root))

    return corpus


def _characterize_recs(recs) -> list[list]:
    """One fan-out's output rendered by identity, order preserved."""
    return [[r.source, r.severity, r.step_id, r.id, r.title] for r in recs]


class TestDeterministicFanoutCharacterization:
    """The two deterministic fan-outs, pinned finding by finding.

    Written before the detector registry landed and unchanged by it: routing
    each detector through a registry entry changes how it is reached, never
    what it finds or where the finding lands."""

    _CONCEPT_ID = (
        "2381241d984524b0470787688af80c6b555f95c2d636927b1f911d0945533d69"
    )
    _SUPPRESSION_REC = [
        "suppression-shape",
        "medium",
        1,
        "step1-suppression-shape-ad245435",
        "Step 1: deliverable suppresses an existing gate",
    ]
    _CONCEPT_REC = [
        "concept-coverage",
        "medium",
        None,
        "plan-concept-coverage-d05bcae4",
        f"Concept `{_CONCEPT_ID}` has no explicit accounting link",
    ]
    # Every fixture is a one-step plan declaring no ``intent``, so each closes
    # with the same two blocking findings — the table's last entry, so nothing
    # above it moved. The ids are the promotion's proof: ``_make_rec_id``
    # hashes the fingerprint, not the severity, so they survive it unchanged.
    _INTENT_RECS = [
        [
            "intent-presence",
            "medium",
            None,
            "plan-intent-presence-59e905f4",
            "Plan declares no `intent`",
        ],
        [
            "intent-presence",
            "medium",
            None,
            "plan-intent-presence-2e2ad0b9",
            "1 step(s) declare no `intent`",
        ],
    ]
    _SMELLS = {
        "clean": [*_INTENT_RECS],
        "smells": [
            [
                "feature-ref",
                "info",
                None,
                "plan-feature-ref-4e21e6a0",
                "Non-kebab feature id `Feature_Two`",
            ],
            [
                "feature-ref",
                "info",
                1,
                "step1-feature-ref-26231239",
                "Step 1 tags unknown feature `ghost`",
            ],
            _SUPPRESSION_REC,
            [
                "self-referential",
                "info",
                None,
                "plan-self-referential-4097c2ec",
                "Feature `feature-one` modifies the audit machinery",
            ],
            *_INTENT_RECS,
        ],
        "orphan": [
            [
                "claim-vs-delivery",
                "info",
                None,
                "plan-claim-vs-delivery-50fee5a1",
                "Plan claims `pkg/never_built.py` but no step delivers it",
            ],
            *_INTENT_RECS,
        ],
        "concepts": [
            [
                "feature-ref",
                "info",
                1,
                "step1-feature-ref-aef53cbc",
                "Step 1 tags unknown feature `explicit-cache-ownership`",
            ],
            _CONCEPT_REC,
            *_INTENT_RECS,
        ],
    }
    # Smell-derived members keep the smell fan-out's relative order and the
    # never-a-smell ``orphaned-deliverable`` is appended last.
    _SELF_CONSISTENCY = {
        "clean": [*_INTENT_RECS],
        "smells": [_SUPPRESSION_REC, *_INTENT_RECS],
        "orphan": [
            *_INTENT_RECS,
            [
                "orphaned-deliverable",
                "medium",
                1,
                "step1-orphaned-deliverable-3db4e3cf",
                "Step 1: deliverable `pkg/orphan_widget.py` has no "
                "in-scope consumer",
            ],
        ],
        "concepts": [_CONCEPT_REC, *_INTENT_RECS],
    }

    def test_collect_smell_findings_characterization(
        self, tmp_path: Path
    ) -> None:
        actual = {
            name: _characterize_recs(
                collect_smell_findings(
                    plan, root, plan_name="p", plan_path=plan_path
                )
            )
            for name, plan, plan_path, root in _fanout_corpus(tmp_path)
        }
        assert actual == self._SMELLS

    def test_self_consistency_from_smells_characterization(
        self, tmp_path: Path
    ) -> None:
        actual = {}
        for name, plan, plan_path, root in _fanout_corpus(tmp_path):
            smells = collect_smell_findings(
                plan, root, plan_name="p", plan_path=plan_path
            )
            recs = _self_consistency_from_smells(
                smells, plan, root, plan_name="p", plan_path=plan_path
            )
            assert all(r.source in SELF_CONSISTENCY_SOURCES for r in recs)
            actual[name] = _characterize_recs(recs)
        assert actual == self._SELF_CONSISTENCY

    def test_collect_self_consistency_findings_parity_preserved(
        self, tmp_path: Path
    ) -> None:
        # The ``--iterate`` loop's independent collector and the finalize
        # gate's partition must stay the same battery over the whole corpus,
        # not just the single-orphan case ``TestCollectSelfConsistencyFindings``
        # pins.
        for name, plan, plan_path, root in _fanout_corpus(tmp_path):
            loop_recs = collect_self_consistency_findings(
                plan, root, plan_name="p", plan_path=plan_path
            )
            smells = collect_smell_findings(
                plan, root, plan_name="p", plan_path=plan_path
            )
            gate_recs = _self_consistency_from_smells(
                smells, plan, root, plan_name="p", plan_path=plan_path
            )
            assert _characterize_recs(loop_recs) == _characterize_recs(
                gate_recs
            ), name


class TestDetectorRegistry:
    """The registry mechanism: one policy — run every entry, once, in order."""

    def _ctx(self, tmp_path: Path):
        from plan_tool.review import DetectorContext

        plan, plan_path = _write_orphan_plan(
            tmp_path, [{"id": 1, "title": "A step", "files": ["pkg/mod.py"]}]
        )
        return DetectorContext(
            plan=plan, repo_root=tmp_path, plan_name="p", plan_path=plan_path
        )

    def test_registry_default_policy_runs_every_detector(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import (
            DetectorEntry,
            DetectorRegistry,
        )

        ran: list[str] = []

        def _spy(key):
            def call(ctx, results):
                ran.append(key)
                return [key]

            return DetectorEntry(key, call)

        registry = DetectorRegistry(tuple(_spy(k) for k in ("a", "b", "c")))
        results = registry.run_all(self._ctx(tmp_path))
        assert ran == ["a", "b", "c"]
        assert list(results) == ["a", "b", "c"]
        assert results == {"a": ["a"], "b": ["b"], "c": ["c"]}

    def test_consumer_receives_its_producer_result(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import DetectorEntry, DetectorRegistry

        registry = DetectorRegistry(
            (
                DetectorEntry("producer", lambda ctx, results: ["hit"]),
                DetectorEntry(
                    "consumer",
                    lambda ctx, results: list(results["producer"]) + ["read"],
                    consumes=("producer",),
                ),
            )
        )
        results = registry.run_all(self._ctx(tmp_path))
        assert results["consumer"] == ["hit", "read"]

    def test_consumer_declared_before_its_producer_is_rejected(self) -> None:
        # A policy that skipped the producer would feed the consumer an empty
        # result set and silently weaken it; the ordering rule makes the
        # dependency impossible to leave implicit.
        from plan_tool.review import DetectorEntry, DetectorRegistry

        with pytest.raises(ValueError, match="no earlier entry"):
            DetectorRegistry(
                (
                    DetectorEntry(
                        "consumer",
                        lambda ctx, results: [],
                        consumes=("producer",),
                    ),
                    DetectorEntry("producer", lambda ctx, results: []),
                )
            )

    def test_duplicate_keys_are_rejected(self) -> None:
        from plan_tool.review import DetectorEntry, DetectorRegistry

        with pytest.raises(ValueError, match="duplicate detector key"):
            DetectorRegistry(
                (
                    DetectorEntry("dup", lambda ctx, results: []),
                    DetectorEntry("dup", lambda ctx, results: []),
                )
            )

    def test_self_consistency_smell_subset_is_derived_from_sources(
        self,
    ) -> None:
        # Derived, not hand-listed: the loop's collector runs exactly the smell
        # entries that can mint a blocking self-consistency source.
        from plan_tool.review import (
            SELF_CONSISTENCY_SMELL_DETECTORS,
            SMELL_DETECTORS,
        )

        assert SELF_CONSISTENCY_SMELL_DETECTORS.keys == (
            "suppression-shape",
            "concept-coverage",
            "intent-presence",
        )
        for entry in SMELL_DETECTORS:
            expected = not SELF_CONSISTENCY_SOURCES.isdisjoint(
                entry.finding_sources
            )
            assert (
                entry.key in SELF_CONSISTENCY_SMELL_DETECTORS.keys
            ) is expected

    def test_input_contract_arms_recompose_into_the_single_call(
        self, tmp_path: Path
    ) -> None:
        # The two entries together must equal the undivided call the
        # reconcile/review lane still makes.
        from plan_tool.review import (
            check_input_contract_references,
            check_plan_input_contract_references,
            check_step_input_contract_references,
        )

        plan, plan_path = _write_orphan_plan(
            tmp_path,
            [
                {
                    "id": 1,
                    "title": "Ship the widget",
                    "creates": ["pkg/orphan_widget.py"],
                    "detail_body": _orphan_detail("pkg/orphan_widget.py"),
                }
            ],
        )
        assert check_input_contract_references(
            plan, plan_path, tmp_path
        ) == check_plan_input_contract_references(
            plan, plan_path, tmp_path
        ) + check_step_input_contract_references(plan, plan_path, tmp_path)


def _write_concept_coverage_fixture(
    tmp_path: Path,
    *,
    review_state: str = "approved",
    decision: str = "include",
    owner_scopes: tuple[str, ...] = (),
    deferral_step_ids: tuple[int, ...] = (),
    matching_prose: bool = False,
) -> tuple[Plan, Path, str]:
    from plan_tool.concept_tree import ConceptNode, ConceptTree, concept_id, save_concepts
    from plan_tool.review_persistence import compute_plan_fingerprint

    stable_id = concept_id("Explicit cache ownership", [])
    steps = []
    for index, scope in enumerate(owner_scopes, 1):
        steps.append(
            "  - id: %d\n    title: %s\n    scope: %s\n"
            "    concept_ids: [%s]\n"
            % (
                index,
                "Explicit cache ownership" if matching_prose else f"Step {index}",
                scope,
                stable_id,
            )
        )
    if not steps:
        steps = [
            "  - id: 1\n    title: Explicit cache ownership\n"
            "    features: [explicit-cache-ownership]\n"
        ]
    plan_path = tmp_path / "1-concepts.md"
    plan_path.write_text(
        "---\ntitle: Concepts\nstatus: planning\npriority: medium\nsteps:\n"
        + "".join(steps)
        + "---\n# Concepts\n\nExplicit cache ownership.\n",
        encoding="utf-8",
    )
    node = ConceptNode(
        id=stable_id,
        title="Explicit cache ownership",
        review_state=review_state,
        decision=decision,
    )
    if deferral_step_ids:
        node.source_metadata["detail_deferral_step_ids"] = json.dumps(
            list(deferral_step_ids), separators=(",", ":")
        )
    save_concepts(
        plan_path,
        ConceptTree(
            plan_slug="concepts",
            plan_fingerprint=compute_plan_fingerprint(plan_path),
            concepts=[node],
        ),
    )
    return parse_plan(plan_path), plan_path, stable_id


def _write_flat_decision_fixture(
    tmp_path: Path,
    *,
    title: str = "Deferred cache concept",
    bucket: str = "caching",
    decision: str = "defer",
    review_state: str = "unreviewed",
    body_sections: tuple[str, ...] = ("Caching",),
) -> tuple[Plan, Path, str]:
    """Write a plan plus a flat ``decision-record`` concepts sidecar."""
    from plan_tool.concept_tree import (
        RECORD_KIND_DECISION,
        ConceptNode,
        ConceptTree,
        concept_id,
        save_concepts,
    )
    from plan_tool.review_persistence import compute_plan_fingerprint

    stable_id = concept_id(title, [])
    body = "# Flat\n\nIntro prose.\n" + "".join(
        f"\n## {name}\n\nSection prose.\n" for name in body_sections
    )
    plan_path = tmp_path / "1-flat.md"
    plan_path.write_text(
        "---\ntitle: Flat\nstatus: planning\npriority: medium\nsteps:\n"
        "  - id: 1\n    title: Only step\n---\n" + body,
        encoding="utf-8",
    )
    node = ConceptNode(
        id=stable_id,
        title=title,
        review_state=review_state,
        decision=decision,
        bucket=bucket,
    )
    save_concepts(
        plan_path,
        ConceptTree(
            plan_slug="flat",
            plan_fingerprint=compute_plan_fingerprint(plan_path),
            concepts=[node],
            record_kind=RECORD_KIND_DECISION,
        ),
    )
    return parse_plan(plan_path), plan_path, stable_id


class TestConceptCoverage:
    def test_accepts_exact_committed_owner(self, tmp_path: Path) -> None:
        from plan_tool.review import check_concept_coverage

        plan, path, _ = _write_concept_coverage_fixture(
            tmp_path, owner_scopes=("committed",)
        )
        assert check_concept_coverage(plan, path, plan_name="p") == []

    def test_accepts_valid_structured_deferral(self, tmp_path: Path) -> None:
        from plan_tool.review import check_concept_coverage

        plan, path, _ = _write_concept_coverage_fixture(
            tmp_path, decision="defer", deferral_step_ids=(1,)
        )
        assert check_concept_coverage(plan, path, plan_name="p") == []

    def test_rejects_invalid_structured_deferral(self, tmp_path: Path) -> None:
        from plan_tool.review import check_concept_coverage

        plan, path, _ = _write_concept_coverage_fixture(
            tmp_path, decision="defer", deferral_step_ids=(99,)
        )
        assert [r.source for r in check_concept_coverage(plan, path, plan_name="p")] == [
            "concept-coverage"
        ]

    def test_reports_missing_owner_and_deferral(self, tmp_path: Path) -> None:
        from plan_tool.review import check_concept_coverage

        plan, path, stable_id = _write_concept_coverage_fixture(tmp_path)
        recs = check_concept_coverage(plan, path, plan_name="p")
        assert len(recs) == 1
        assert (recs[0].source, recs[0].severity) == ("concept-coverage", "medium")
        assert stable_id in recs[0].body
        assert "committed step" in recs[0].body
        assert "structured deferral" in recs[0].body

    def test_does_not_infer_from_title_features_or_prose(self, tmp_path: Path) -> None:
        from plan_tool.review import check_concept_coverage

        plan, path, _ = _write_concept_coverage_fixture(
            tmp_path, matching_prose=True
        )
        assert [r.source for r in check_concept_coverage(plan, path, plan_name="p")] == [
            "concept-coverage"
        ]

    def test_ignores_non_committed_owner(self, tmp_path: Path) -> None:
        from plan_tool.review import check_concept_coverage

        plan, path, _ = _write_concept_coverage_fixture(
            tmp_path, owner_scopes=("deferred",)
        )
        assert [r.source for r in check_concept_coverage(plan, path, plan_name="p")] == [
            "concept-coverage"
        ]

    def test_any_surviving_committed_owner_is_sufficient(self, tmp_path: Path) -> None:
        from plan_tool.review import check_concept_coverage

        plan, path, _ = _write_concept_coverage_fixture(
            tmp_path, owner_scopes=("deferred", "committed")
        )
        assert check_concept_coverage(plan, path, plan_name="p") == []

    def test_unsigned_concept_is_advisory_only(self, tmp_path: Path) -> None:
        from plan_tool.review import check_concept_coverage

        plan, path, _ = _write_concept_coverage_fixture(
            tmp_path, review_state="unreviewed", decision="defer"
        )
        recs = check_concept_coverage(plan, path, plan_name="p")
        assert [(r.source, r.severity) for r in recs] == [
            ("concept-unsigned-deferral", "info")
        ]
        assert "concept-unsigned-deferral" not in SELF_CONSISTENCY_SOURCES

    @pytest.mark.parametrize("exc", [ParseError("bad fence"), ValueError("bad utf-8")])
    def test_decision_record_coverage_never_raises_on_unreadable_plan(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exc: Exception
    ) -> None:
        # Totality (step 3, "Never raises"): if the plan body can't be read
        # (malformed frontmatter → ParseError, non-utf-8 → ValueError) bucket
        # existence is undeterminable, so the check falls back to the unsigned
        # reminder for each node rather than propagating the exception.
        from plan_tool import review as review_module
        from plan_tool.concept_tree import (
            ConceptNode,
            ConceptTree,
            RECORD_KIND_DECISION,
            concept_id,
        )

        node = ConceptNode(
            id=concept_id("Caching", []),
            title="Caching",
            decision="defer",
            review_state="unreviewed",
            bucket="Caching",
        )
        tree = ConceptTree("flat", "fp", [node], record_kind=RECORD_KIND_DECISION)
        plan_path = tmp_path / "1-flat.md"
        plan_path.write_text("body", encoding="utf-8")

        def boom(_text: str):
            raise exc

        monkeypatch.setattr(review_module, "_split_frontmatter", boom)
        sentinel = object()
        recs = review_module._check_decision_record_coverage(
            tree, plan_path, lambda _n: sentinel
        )
        # No exception; sections=None → unsigned reminder, never a bogus
        # concept-bucket-missing finding.
        assert recs == [sentinel]

    def test_finding_id_survives_step_prose_edit(self, tmp_path: Path) -> None:
        from plan_tool.concept_tree import ConceptTree, load_concepts, save_concepts
        from plan_tool.review import check_concept_coverage
        from plan_tool.review_persistence import compute_plan_fingerprint

        plan, path, _ = _write_concept_coverage_fixture(tmp_path)
        first_id = check_concept_coverage(plan, path, plan_name="p")[0].id
        tree = load_concepts(path, compute_plan_fingerprint(path))
        assert tree is not None
        text = path.read_text(encoding="utf-8").replace(
            "title: Explicit cache ownership", "title: Renamed prose"
        )
        path.write_text(text, encoding="utf-8")
        save_concepts(
            path,
            ConceptTree(
                plan_slug=tree.plan_slug,
                plan_fingerprint=compute_plan_fingerprint(path),
                concepts=tree.concepts,
            ),
        )
        second_id = check_concept_coverage(
            parse_plan(path), path, plan_name="p"
        )[0].id
        assert second_id == first_id

    def test_missing_record_is_inert(self, tmp_path: Path) -> None:
        from plan_tool.review import check_concept_coverage

        path = tmp_path / "1-none.md"
        path.write_text(
            _smell_plan_text(
                steps="  - id: 1\n    title: Only step\n"
            ),
            encoding="utf-8",
        )
        assert check_concept_coverage(parse_plan(path), path, plan_name="p") == []

    def test_source_membership_and_collectors(self, tmp_path: Path) -> None:
        from plan_tool.review import check_concept_coverage

        plan, path, _ = _write_concept_coverage_fixture(tmp_path)
        direct = check_concept_coverage(plan, path, plan_name="p")
        collected = collect_self_consistency_findings(
            plan, tmp_path, plan_name="p", plan_path=path
        )
        assert "concept-coverage" in SELF_CONSISTENCY_SOURCES
        assert "concept-coverage" not in APPLY_ELIGIBLE_SOURCES
        assert [r.id for r in collected if r.source == "concept-coverage"] == [
            direct[0].id
        ]
        assert all(
            r.source != "concept-coverage"
            for r in collect_deterministic_findings(
                plan, path, repo_root=tmp_path, plan_name="p"
            )
        )

    def test_stale_legacy_record_surfaces_resync_advisory(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.concept_tree import (
            ConceptNode,
            ConceptTree,
            concept_id,
            save_concepts,
        )
        from plan_tool.review import check_concept_coverage

        stable_id = concept_id("Explicit cache ownership", [])
        path = tmp_path / "1-concepts.md"
        path.write_text(
            "---\ntitle: Concepts\nstatus: planning\npriority: medium\nsteps:\n"
            "  - id: 1\n    title: Only step\n---\n# Concepts\n\nBody.\n",
            encoding="utf-8",
        )
        save_concepts(
            path,
            ConceptTree(
                plan_slug="concepts",
                plan_fingerprint="stale-does-not-match-current-plan",
                concepts=[
                    ConceptNode(
                        id=stable_id,
                        title="Explicit cache ownership",
                        review_state="approved",
                        decision="include",
                    )
                ],
            ),
        )
        recs = check_concept_coverage(parse_plan(path), path, plan_name="p")
        assert [r.source for r in recs] == [CONCEPT_LEGACY_STALE_SOURCE]
        assert recs[0].severity == "info"
        assert CONCEPT_LEGACY_STALE_SOURCE not in SELF_CONSISTENCY_SOURCES

    def test_malformed_record_returns_empty(self, tmp_path: Path) -> None:
        from plan_tool.concept_tree import concepts_path
        from plan_tool.review import check_concept_coverage

        plan, path, _ = _write_concept_coverage_fixture(tmp_path)
        concepts_path(path).write_text("{ not valid json", encoding="utf-8")
        assert check_concept_coverage(plan, path, plan_name="p") == []

    def test_decision_record_missing_bucket_surfaces_rereview(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import check_concept_coverage

        plan, path, stable_id = _write_flat_decision_fixture(
            tmp_path, bucket="gone-section", body_sections=("Caching",)
        )
        recs = check_concept_coverage(plan, path, plan_name="p")
        assert [(r.source, r.step_id) for r in recs] == [
            (CONCEPT_BUCKET_MISSING_SOURCE, None)
        ]
        assert recs[0].anchor == f"concept-{stable_id}"
        assert "gone-section" in recs[0].body

    def test_signed_off_missing_bucket_is_cleared(self, tmp_path: Path) -> None:
        from plan_tool.review import check_concept_coverage

        plan, path, _ = _write_flat_decision_fixture(
            tmp_path,
            bucket="gone-section",
            decision="wont_do",
            review_state="approved",
        )
        assert check_concept_coverage(plan, path, plan_name="p") == []

    def test_bucket_missing_finding_is_non_blocking(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import check_concept_coverage

        plan, path, _ = _write_flat_decision_fixture(
            tmp_path, bucket="gone-section"
        )
        recs = check_concept_coverage(plan, path, plan_name="p")
        assert CONCEPT_BUCKET_MISSING_SOURCE not in SELF_CONSISTENCY_SOURCES
        assert recs[0].severity == "info"

    def test_approved_flat_defer_present_bucket_no_finding(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import check_concept_coverage

        plan, path, _ = _write_flat_decision_fixture(
            tmp_path, decision="defer", review_state="approved"
        )
        assert check_concept_coverage(plan, path, plan_name="p") == []

    def test_unreviewed_flat_defer_present_bucket_still_unsigned(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import check_concept_coverage

        plan, path, _ = _write_flat_decision_fixture(
            tmp_path, decision="defer", review_state="unreviewed"
        )
        recs = check_concept_coverage(plan, path, plan_name="p")
        assert [(r.source, r.severity) for r in recs] == [
            ("concept-unsigned-deferral", "info")
        ]

    def test_missing_bucket_takes_priority_over_unsigned(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import check_concept_coverage

        plan, path, _ = _write_flat_decision_fixture(
            tmp_path, bucket="gone-section", decision="defer"
        )
        recs = check_concept_coverage(plan, path, plan_name="p")
        assert [r.source for r in recs] == [CONCEPT_BUCKET_MISSING_SOURCE]

    def test_legacy_full_tree_coverage_unchanged(self, tmp_path: Path) -> None:
        from plan_tool.review import check_concept_coverage

        plan, path, stable_id = _write_concept_coverage_fixture(tmp_path)
        recs = check_concept_coverage(plan, path, plan_name="p")
        assert [(r.source, r.severity) for r in recs] == [
            ("concept-coverage", "medium")
        ]
        assert recs[0].anchor == f"concept-{stable_id}"


def _acceptance_body(text: str) -> str:
    """A plan-body ``## Acceptance criteria`` section for the claim tests."""
    return f"\n## Acceptance criteria\n\n{text}\n"


class TestClaimVsDelivery:
    def test_claim_vs_delivery_trips_on_claimed_undelivered_symbol(
        self, tmp_path: Path
    ) -> None:
        plan, plan_path = _write_orphan_plan(
            tmp_path,
            [{"id": 1, "title": "Ship", "creates": ["pkg/widget.py"]}],
            plan_body=_acceptance_body(
                "The `nonexistent_mechanism` gates the run end to end."
            ),
        )
        recs = detect_claim_vs_delivery(
            plan, tmp_path, plan_name="p", plan_path=plan_path
        )
        assert len(recs) == 1
        assert recs[0].source == "claim-vs-delivery"
        assert recs[0].severity == "info"
        assert recs[0].step_id is None
        assert "nonexistent_mechanism" in recs[0].title

    def test_claim_vs_delivery_no_trip_when_step_declares_it(
        self, tmp_path: Path
    ) -> None:
        plan, plan_path = _write_orphan_plan(
            tmp_path,
            [{"id": 1, "title": "Ship", "creates": ["pkg/widget.py"]}],
            plan_body=_acceptance_body(
                "The plan ships `pkg/widget.py` and delivers `widget`."
            ),
        )
        assert (
            detect_claim_vs_delivery(
                plan, tmp_path, plan_name="p", plan_path=plan_path
            )
            == []
        )

    def test_claim_vs_delivery_fuzzy_match_tolerates_minor_variance(
        self, tmp_path: Path
    ) -> None:
        # Claim names ``foo_widgets``; the declared symbol is ``foo_widget``
        # (from ``pkg/foo_widget.py``). Small edit distance -> delivered.
        plan, plan_path = _write_orphan_plan(
            tmp_path,
            [{"id": 1, "title": "Ship", "creates": ["pkg/foo_widget.py"]}],
            plan_body=_acceptance_body("The `foo_widgets` primitive is built."),
        )
        assert (
            detect_claim_vs_delivery(
                plan, tmp_path, plan_name="p", plan_path=plan_path
            )
            == []
        )

    def test_claim_vs_delivery_ignores_bare_prose_nouns(
        self, tmp_path: Path
    ) -> None:
        plan, plan_path = _write_orphan_plan(
            tmp_path,
            [{"id": 1, "title": "Ship", "creates": ["pkg/widget.py"]}],
            plan_body=_acceptance_body("The workflow runs end to end."),
        )
        assert (
            detect_claim_vs_delivery(
                plan, tmp_path, plan_name="p", plan_path=plan_path
            )
            == []
        )

    def test_claim_vs_delivery_overview_alone_does_not_trip(
        self, tmp_path: Path
    ) -> None:
        # ``orphan_widget`` appears only in ``## Overview`` (corroboration
        # only); the acceptance prose names no code token, so nothing trips.
        body = (
            "\n## Overview\n\nBuilds on `orphan_widget` from an earlier plan.\n"
            + _acceptance_body("The feature works end to end.")
        )
        plan, plan_path = _write_orphan_plan(
            tmp_path,
            [{"id": 1, "title": "Ship", "creates": ["pkg/widget.py"]}],
            plan_body=body,
        )
        assert (
            detect_claim_vs_delivery(
                plan, tmp_path, plan_name="p", plan_path=plan_path
            )
            == []
        )

    def test_claim_vs_delivery_opens_no_source_files(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        import pathlib

        (tmp_path / "pkg").mkdir()
        (tmp_path / "pkg" / "widget.py").write_text(
            "SECRET = 1\n", encoding="utf-8"
        )
        plan, plan_path = _write_orphan_plan(
            tmp_path,
            [{"id": 1, "title": "Ship", "creates": ["pkg/widget.py"]}],
            plan_body=_acceptance_body("The `nonexistent_mechanism` gates it."),
        )
        read_paths: list[str] = []
        orig = pathlib.Path.read_text

        def spy(self, *a, **k):
            read_paths.append(str(self))
            return orig(self, *a, **k)

        monkeypatch.setattr(pathlib.Path, "read_text", spy)
        recs = detect_claim_vs_delivery(
            plan, tmp_path, plan_name="p", plan_path=plan_path
        )
        assert len(recs) == 1  # ran the full match, still read no source
        assert not any(p.endswith(".py") for p in read_paths)

    def test_claim_vs_delivery_is_info_severity(self, tmp_path: Path) -> None:
        plan, plan_path = _write_orphan_plan(
            tmp_path,
            [{"id": 1, "title": "Ship", "creates": ["pkg/widget.py"]}],
            plan_body=_acceptance_body("The `undelivered_symbol` is exercised."),
        )
        recs = detect_claim_vs_delivery(
            plan, tmp_path, plan_name="p", plan_path=plan_path
        )
        assert [r.severity for r in recs] == ["info"]

    def test_claim_vs_delivery_reproduces_prompt_budget_shape(
        self, tmp_path: Path
    ) -> None:
        # #95-shaped: the acceptance prose claims a mechanism no step delivers.
        plan, plan_path = _write_orphan_plan(
            tmp_path,
            [{"id": 1, "title": "Add an unrelated primitive",
              "creates": ["pkg/other.py"]}],
            plan_body=_acceptance_body(
                "The `prompt_budget_advisory` mechanism caps the run's spend."
            ),
        )
        recs = detect_claim_vs_delivery(
            plan, tmp_path, plan_name="p", plan_path=plan_path
        )
        assert len(recs) == 1
        assert recs[0].source == "claim-vs-delivery"
        assert "prompt_budget_advisory" in recs[0].title


def _write_machinery_config(tmp_path: Path, paths: list[str]) -> None:
    from plan_tool import project_config as pc

    cfg = pc.project_config_path(tmp_path)
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        json.dumps(
            {pc.SMELL_CONFIG_BLOCK: {pc.VALIDATION_MACHINERY_PATHS_KEY: paths}}
        ),
        encoding="utf-8",
    )


def _feature_plan(file_path: str) -> Plan:
    return parse_plan_text(
        _smell_plan_text(
            features="features:\n  - id: feature-one\n    title: Feature One\n",
            steps=(
                f"  - id: 1\n    title: Do it\n    files:\n      - {file_path}\n"
                "    features:\n      - feature-one\n"
            ),
        )
    )


class TestSelfReferentialFeatures:
    def test_inert_when_unconfigured(self, tmp_path: Path) -> None:
        plan = _feature_plan("plan_tool/review.py")
        assert detect_self_referential_features(plan, tmp_path, plan_name="p") == []

    def test_overlap_flagged(self, tmp_path: Path) -> None:
        _write_machinery_config(tmp_path, ["plan_tool/review.py"])
        plan = _feature_plan("plan_tool/review.py")
        recs = detect_self_referential_features(plan, tmp_path, plan_name="p")
        assert len(recs) == 1
        assert recs[0].source == "self-referential"
        assert recs[0].severity == "info"
        assert recs[0].step_id is None
        assert "plan_tool/review.py" in recs[0].body

    def test_no_overlap_no_findings(self, tmp_path: Path) -> None:
        _write_machinery_config(tmp_path, ["plan_tool/review.py"])
        plan = _feature_plan("app/unrelated.py")
        assert detect_self_referential_features(plan, tmp_path, plan_name="p") == []


class TestCollectSmellFindings:
    def test_aggregates_all_three(self, tmp_path: Path) -> None:
        _write_machinery_config(tmp_path, ["plan_tool/review.py"])
        steps = (
            "  - id: 1\n    title: Bypass the purity gate\n"
            "    files:\n      - plan_tool/review.py\n"
            "    features:\n      - feature-one\n      - ghost\n"
        )
        features = (
            "features:\n"
            "  - id: feature-one\n    title: Feature One\n"
            "  - id: Feature_Two\n    title: Feature Two\n"
        )
        plan_path = tmp_path / "1-agg.md"
        plan_path.write_text(
            _smell_plan_text(features=features, steps=steps), encoding="utf-8"
        )
        plan = parse_plan(plan_path)
        recs = collect_smell_findings(plan, tmp_path, plan_name="p")
        sources = {r.source for r in recs}
        assert "feature-ref" in sources
        assert "suppression-shape" in sources
        assert "self-referential" in sources

    def test_sources_not_apply_eligible(self, tmp_path: Path) -> None:
        _write_machinery_config(tmp_path, ["plan_tool/review.py"])
        steps = (
            "  - id: 1\n    title: Silence the audit gate\n"
            "    files:\n      - plan_tool/review.py\n"
            "    features:\n      - feature-one\n      - ghost\n"
        )
        features = "features:\n  - id: feature-one\n    title: Feature One\n"
        plan_path = tmp_path / "1-elig.md"
        plan_path.write_text(
            _smell_plan_text(features=features, steps=steps), encoding="utf-8"
        )
        plan = parse_plan(plan_path)
        recs = collect_smell_findings(plan, tmp_path, plan_name="p")
        assert recs  # non-trivial: actually exercises the guard
        for rec in recs:
            assert rec.source not in APPLY_ELIGIBLE_SOURCES

    def test_intent_presence_reaches_the_smell_battery(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "1-intent.md"
        plan_path.write_text(
            _smell_plan_text(steps="  - id: 1\n    title: Do it\n"),
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)
        recs = collect_smell_findings(plan, tmp_path, plan_name="p")
        assert [r.source for r in recs if r.source == INTENT_PRESENCE_SOURCE] == [
            INTENT_PRESENCE_SOURCE,
            INTENT_PRESENCE_SOURCE,
        ]


class TestDetailBundleStatus:
    """Bare-plan detection + audit-prompt grounding conditioning (BACKLOG #61)."""

    @staticmethod
    def _render_bare_altitude_prompt(
        tmp_path: Path, *, detail_authored: bool = False
    ) -> str:
        from plan_tool.parser import parse_plan
        from plan_tool.review import render_plan_audit_prompt

        tmp_path.mkdir(parents=True, exist_ok=True)
        detail_rel = "details/01-do-thing.md"
        plan_path = _write_completeness_plan(
            tmp_path,
            body=_FULL_BODY_SECTIONS,
            extra_step_yaml=(
                f"    detail: {detail_rel}\n" if detail_authored else ""
            ),
        )
        if detail_authored:
            detail_path = tmp_path / detail_rel
            detail_path.parent.mkdir()
            detail_path.write_text(
                "## Delivery\n\nUse the selected typed attachment.\n",
                encoding="utf-8",
            )
        prompt = render_plan_audit_prompt(
            parse_plan(plan_path), plan_path, repo_root=tmp_path
        )
        assert prompt is not None
        return prompt

    def test_status_partial_bare(self, tmp_path: Path) -> None:
        from plan_tool.parser import parse_plan
        from plan_tool.review import audit_detail_bundle_status

        # fixture: 4-step plan; only step 2 has an on-disk detail file.
        plan_path = _write_review_fixture_with_detail(tmp_path)
        plan = parse_plan(plan_path)
        status = audit_detail_bundle_status(plan, plan_path, tmp_path)
        assert status.total == 4
        assert status.detailed_step_ids == (2,)
        assert status.bare_step_ids == (1, 3, 4)
        assert status.detailed_count == 1
        assert status.is_bare is True
        assert status.is_fully_bare is False

    def test_status_fully_bare(self, tmp_path: Path) -> None:
        from plan_tool.parser import parse_plan
        from plan_tool.review import audit_detail_bundle_status

        plan_path = _write_review_fixture_with_detail(
            tmp_path, missing_detail=True
        )
        plan = parse_plan(plan_path)
        status = audit_detail_bundle_status(plan, plan_path, tmp_path)
        assert status.bare_step_ids == (1, 2, 3, 4)
        assert status.detailed_count == 0
        assert status.is_bare is True
        assert status.is_fully_bare is True

    def test_status_block_empty_when_all_detailed(self) -> None:
        from plan_tool.review import (
            DetailBundleStatus,
            _format_detail_bundle_status_block,
        )

        status = DetailBundleStatus(
            total=2, detailed_step_ids=(1, 2), bare_step_ids=()
        )
        assert _format_detail_bundle_status_block(status) == ""

    def test_status_block_names_bare_steps_and_forbids_detail_findings(
        self,
    ) -> None:
        from plan_tool.review import (
            DetailBundleStatus,
            _format_detail_bundle_status_block,
        )

        status = DetailBundleStatus(
            total=4, detailed_step_ids=(2,), bare_step_ids=(1, 3, 4)
        )
        block = _format_detail_bundle_status_block(status)
        assert "1 of 4" in block
        assert "partially-detailed" in block
        assert "step 1" in block and "step 3" in block and "step 4" in block
        assert "no detail file yet" in block
        assert "do **not** raise" in block

    def test_status_block_labels_fully_bare(self) -> None:
        from plan_tool.review import (
            DetailBundleStatus,
            _format_detail_bundle_status_block,
        )

        status = DetailBundleStatus(
            total=3, detailed_step_ids=(), bare_step_ids=(1, 2, 3)
        )
        block = _format_detail_bundle_status_block(status)
        assert "0 of 3" in block
        assert "bare plan" in block

    def test_bare_prompt_requires_a_named_property_to_have_a_route(
        self, tmp_path: Path
    ) -> None:
        prompt = self._render_bare_altitude_prompt(tmp_path)

        assert "A named observable property, acceptance result, ownership" in prompt
        assert "provides no route that delivers it" in prompt
        assert (
            "raise a **Correctness** finding that names the missing property"
            in prompt
        )

    def test_bare_prompt_omits_unselected_delivery_mechanisms_from_both_axes(
        self, tmp_path: Path
    ) -> None:
        prompt = self._render_bare_altitude_prompt(tmp_path)

        assert (
            "Do **not** raise a Correctness or Completeness finding solely"
            in prompt
        )
        assert "typed attachment or carrier, serializer" in prompt
        assert "internal dependency ordering" in prompt
        assert "even when the proposed choice is described as severe" in prompt
        assert "omit it from both axes" in prompt
        assert "until detail authoring selects the" in prompt

    def test_audit_prompt_defers_merely_useful_scope_expansion(
        self, tmp_path: Path
    ) -> None:
        prompt = self._render_bare_altitude_prompt(tmp_path)
        normalized_prompt = " ".join(prompt.split())

        assert "Keep findings proportional to that intent." in prompt
        assert "challenge necessity before elaborating machinery" in prompt
        assert "internally consistent design can still overbuild" in normalized_prompt
        assert "not necessary merely because the generated plan" in normalized_prompt
        assert "preserve settled choices" in normalized_prompt
        assert "adds no deterministic minimality score" in normalized_prompt
        assert (
            "more general abstraction, adjacent workflow, or future capability"
            in normalized_prompt
        )
        assert "would be useful" in normalized_prompt

    def test_bare_prompt_keeps_explicit_observable_mechanisms_in_correctness(
        self, tmp_path: Path
    ) -> None:
        prompt = self._render_bare_altitude_prompt(tmp_path)

        assert "mechanism remains a bare **Correctness** obligation only" in prompt
        assert "compatibility, safety, ordering, ownership, or bypass" in prompt
        assert (
            "do not infer that exception from a plausible implementation choice"
            in prompt
        )

    def test_detail_grounded_prompt_can_require_a_selected_delivery_mechanism(
        self, tmp_path: Path
    ) -> None:
        prompt = self._render_bare_altitude_prompt(tmp_path, detail_authored=True)

        assert "Once a detail file selects a delivery mechanism" in prompt
        assert "may require that selected mechanism and the evidence" in prompt
        assert "Keep named observable-property coverage at this bare stage" not in prompt

    def test_prompt_carries_the_bare_step_restatement_instruction(
        self, tmp_path: Path
    ) -> None:
        """The ``### Restated`` sub-block instruction is part of the one
        shared template -- present the same way whether or not any step has
        a detail file yet, since the rule is conditioned on the *step* the
        model is judging, not on a separate template variant."""
        bare_prompt = self._render_bare_altitude_prompt(tmp_path)
        detailed_prompt = self._render_bare_altitude_prompt(
            tmp_path / "detailed", detail_authored=True
        )

        for prompt in (bare_prompt, detailed_prompt):
            normalized = " ".join(prompt.split())
            assert "also restate the finding at plan altitude" in normalized
            assert "using the `### Restated` sub-block" in normalized
            assert (
                "the `### Restated` sub-block carries the restatement that "
                "rule requires" in normalized
            )
            assert (
                "Assign this finding's severity, and its triage `impact=` "
                "tag below, from that same bare-plan-altitude framing"
                in normalized
            )
            assert (
                "Omit the sub-block entirely for a step that already has a "
                "detail file" in normalized
            )
            # The heading-anchored format is spelled out as a worked
            # example, not just described in prose.
            assert "### Restated" in prompt and "### Fix" in prompt
            # The verbatim-citation fencing requirement (round 4: a
            # multi-line citation can contain a genuine heading line, so
            # only a fence -- not heading position -- protects the split).
            assert "Wrap the verbatim citation in a fenced code block" in (
                normalized
            )
            assert (
                "the parser excludes any match inside a fenced span from "
                "the sub-block boundary search" in normalized
            )

    def test_bare_altitude_status_block_reaches_rendered_prompt(
        self, tmp_path: Path
    ) -> None:
        bare_prompt = self._render_bare_altitude_prompt(tmp_path)
        detailed_prompt = self._render_bare_altitude_prompt(
            tmp_path / "detailed", detail_authored=True
        )

        status_rule = (
            "Keep named observable-property coverage at this bare stage"
        )
        assert status_rule in bare_prompt
        assert status_rule not in detailed_prompt

    def test_render_prompt_injects_bare_status_block(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.parser import parse_plan
        from plan_tool.review import render_plan_audit_prompt

        detail_rel = "details/01-a.md"
        (tmp_path / "details").mkdir()
        (tmp_path / detail_rel).write_text("## A\n\nbody\n", encoding="utf-8")
        plan_path = tmp_path / "audit-plan.md"
        plan_path.write_text(
            "---\n"
            "title: Audit Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: do a\n"
            "    status: pending\n"
            f"    detail: {detail_rel}\n"
            "  - id: 2\n"
            "    title: do b\n"
            "    status: pending\n"
            "    depends_on: [1]\n"
            "---\n\n"
            f"{_FULL_BODY_SECTIONS}",
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)
        prompt = render_plan_audit_prompt(plan, plan_path, repo_root=tmp_path)
        assert prompt is not None
        assert "step(s) have a detail file authored" in prompt
        assert "do **not** raise" in prompt
        # step 2 is the bare one
        assert "step 2" in prompt

    def test_render_prompt_no_status_block_when_all_detailed(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.parser import parse_plan
        from plan_tool.review import render_plan_audit_prompt

        detail_rel = "details/01-x.md"
        (tmp_path / "details").mkdir()
        (tmp_path / detail_rel).write_text("## X\n\nbody\n", encoding="utf-8")
        plan_path = tmp_path / "audit-plan.md"
        plan_path.write_text(
            "---\n"
            "title: Audit Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: do x\n"
            "    status: pending\n"
            f"    detail: {detail_rel}\n"
            "---\n\n"
            f"{_FULL_BODY_SECTIONS}",
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)
        prompt = render_plan_audit_prompt(plan, plan_path, repo_root=tmp_path)
        assert prompt is not None
        assert "detail file authored" not in prompt
        assert "do **not** raise" not in prompt

    def test_status_block_admits_edge_case_gaps_whose_fix_is_a_step_or_criterion(
        self,
    ) -> None:
        from plan_tool.review import (
            DetailBundleStatus,
            _format_detail_bundle_status_block,
        )

        status = DetailBundleStatus(
            total=2, detailed_step_ids=(1,), bare_step_ids=(2,)
        )
        block = _format_detail_bundle_status_block(status)
        assert "**Missing edge-case concept**" in block
        assert "new step" in block
        assert "acceptance criterion" in block

    def test_status_block_refuses_edge_case_gaps_whose_fix_is_detail_prose(
        self,
    ) -> None:
        from plan_tool.review import (
            DetailBundleStatus,
            _format_detail_bundle_status_block,
        )

        status = DetailBundleStatus(
            total=2, detailed_step_ids=(1,), bare_step_ids=(2,)
        )
        block = _format_detail_bundle_status_block(status)
        assert "specify it in the detail file" in block
        assert "Skip it when the fix" in block

    def test_status_block_reuses_the_audit_prompts_edge_case_phrase(self) -> None:
        from plan_tool.renderer import prompts_dir
        from plan_tool.review import (
            DetailBundleStatus,
            _format_detail_bundle_status_block,
        )

        gap_kind = "**Missing edge-case concept**"
        audit_template = (prompts_dir() / "plan-audit.md").read_text(
            encoding="utf-8"
        )
        assert gap_kind.strip("*") in audit_template
        status = DetailBundleStatus(
            total=1, detailed_step_ids=(), bare_step_ids=(1,)
        )
        block = _format_detail_bundle_status_block(status)
        assert gap_kind in block

    def test_status_block_has_no_edge_case_rule_when_all_detailed(self) -> None:
        from plan_tool.review import (
            DetailBundleStatus,
            _format_detail_bundle_status_block,
        )

        status = DetailBundleStatus(
            total=2, detailed_step_ids=(1, 2), bare_step_ids=()
        )
        block = _format_detail_bundle_status_block(status)
        assert block == ""
        assert "Missing edge-case concept" not in block

    def test_render_prompt_carries_edge_case_narrowing_on_a_bare_plan(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.parser import parse_plan
        from plan_tool.review import render_plan_audit_prompt

        detail_rel = "details/01-a.md"
        (tmp_path / "details").mkdir()
        (tmp_path / detail_rel).write_text("## A\n\nbody\n", encoding="utf-8")
        plan_path = tmp_path / "audit-plan.md"
        plan_path.write_text(
            "---\n"
            "title: Audit Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: do a\n"
            "    status: pending\n"
            f"    detail: {detail_rel}\n"
            "  - id: 2\n"
            "    title: do b\n"
            "    status: pending\n"
            "    depends_on: [1]\n"
            "---\n\n"
            f"{_FULL_BODY_SECTIONS}",
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)
        prompt = render_plan_audit_prompt(plan, plan_path, repo_root=tmp_path)
        assert prompt is not None
        assert "**Missing edge-case concept**" in prompt
        assert "specify it in the detail file" in prompt

    def test_render_prompt_omits_edge_case_narrowing_when_all_detailed(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.parser import parse_plan
        from plan_tool.review import render_plan_audit_prompt

        detail_rel = "details/01-x.md"
        (tmp_path / "details").mkdir()
        (tmp_path / detail_rel).write_text("## X\n\nbody\n", encoding="utf-8")
        plan_path = tmp_path / "audit-plan.md"
        plan_path.write_text(
            "---\n"
            "title: Audit Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: do x\n"
            "    status: pending\n"
            f"    detail: {detail_rel}\n"
            "---\n\n"
            f"{_FULL_BODY_SECTIONS}",
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)
        prompt = render_plan_audit_prompt(plan, plan_path, repo_root=tmp_path)
        assert prompt is not None
        assert "specify it in the detail file" not in prompt
        assert "decomposition gap this audit should catch" not in prompt


_BARE_ALTITUDE_TWO_STAGE_REPLAY_FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "convergence"
    / "bare-altitude-two-stage-replay.json"
)


class TestBareAltitudeTwoStageReplay:
    """Policy replay for the combined and split proposal routes."""

    @pytest.fixture(scope="class")
    def replay(self) -> dict:
        return json.loads(
            _BARE_ALTITUDE_TWO_STAGE_REPLAY_FIXTURE.read_text(encoding="utf-8")
        )

    def test_bare_altitude_two_stage_replay_covers_combined_and_split_routes(
        self, replay: dict
    ) -> None:
        from plan_tool.create import (
            _PROPOSAL_FOUNDATIONAL_ITEM,
            _render_from_prompt,
            _render_sweep_context,
        )

        routes = replay["proposal_routes"]
        assert [route["name"] for route in routes] == ["combined", "split"]
        case_sets = []
        for route in routes:
            prompt = _render_from_prompt(
                "Refactor the proposal route.",
                omit_foundational_item=route["omit_foundational_item"],
            )
            sweep_context = _render_sweep_context(
                [Step(id=1, title="Refactor the proposal route")]
            )
            assert route["refactor_boundary_property"] in prompt
            assert route["refactor_boundary_property"] in sweep_context
            assert (
                _PROPOSAL_FOUNDATIONAL_ITEM in prompt
            ) is route["expects_inline_foundational_item"]
            case_sets.append(route["bare_cases"])

        assert case_sets[0] == case_sets[1]

    def test_bare_altitude_replay_separates_missing_property_from_delivery_choice(
        self, replay: dict
    ) -> None:
        for route in replay["proposal_routes"]:
            cases = {case["kind"]: case for case in route["bare_cases"]}
            assert cases["missing-route"]["expected_axes"] == ["correctness"]
            assert cases["unselected-delivery-choice"]["expected_axes"] == []
            assert cases["unselected-delivery-choice"]["described_as_severe"] is True
            assert cases["explicit-observable-contract"]["expected_axes"] == [
                "correctness"
            ]
            assert route["detail_stage"]["selected_delivery_mechanism"] is True
            assert route["detail_stage"]["may_check_selected_mechanism"] is True


class TestAuditDetailBundleFormatVersion:
    """The plan-audit prompt's run-grade grounding refuses an unsupported
    or malformed detail-format-version marker before it reaches the
    prompt, from either of the bundle's two text sources."""

    def _write_plan_with_detail(
        self, tmp_path: Path, *, declared_version: int = 999
    ) -> tuple[Path, Path]:
        from plan_tool.detail_artifacts import render_detail_format_version_marker

        plan_path = tmp_path / "audit-plan.md"
        plan_path.write_text(
            "---\n"
            "title: Audit Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: build the thing\n"
            "    detail: detail.md\n"
            "    status: pending\n"
            "---\n\n"
            "## Overview\n\nDo the thing.\n",
            encoding="utf-8",
        )
        detail_path = tmp_path / "detail.md"
        detail_path.write_text(
            f"# Step 1\n{render_detail_format_version_marker(declared_version)}\n\n"
            "## Summary\n\nBody.\n",
            encoding="utf-8",
        )
        return plan_path, detail_path

    def test_audit_bundle_refuses_an_unsupported_detail_marker_from_a_fresh_read(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.detail_artifacts import DetailFormatError
        from plan_tool.parser import parse_plan
        from plan_tool.review import render_plan_audit_prompt

        plan_path, _ = self._write_plan_with_detail(tmp_path)
        plan = parse_plan(plan_path)

        with pytest.raises(DetailFormatError):
            render_plan_audit_prompt(plan, plan_path, repo_root=tmp_path)

    def test_audit_bundle_refuses_an_unsupported_detail_marker_from_a_captured_snapshot(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.detail_artifacts import DetailFormatError
        from plan_tool.parser import parse_plan
        from plan_tool.review import render_plan_audit_prompt
        from plan_tool.review_persistence import AuditInputSnapshot

        plan_path, _ = self._write_plan_with_detail(tmp_path)
        # Captured before the plan is (re-)parsed, mirroring how a
        # multi-pass audit takes one snapshot up front and reuses it.
        snapshot = AuditInputSnapshot.capture(plan_path, tmp_path)
        plan = parse_plan(plan_path)

        with pytest.raises(DetailFormatError):
            render_plan_audit_prompt(
                plan, plan_path, repo_root=tmp_path, audit_input_snapshot=snapshot
            )

    def test_audit_budget_estimator_reraises_detail_format_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The pre-pass budget estimate in ``audit_plan_until_stable`` must
        not swallow a format refusal into a silently missing advisory —
        forcing the *first* call (the estimator's) to raise and checking
        it's never retried proves the refusal escapes that specific
        ``try/except``, not merely the audit as a whole."""
        import plan_tool.review as review_module
        from plan_tool.detail_artifacts import DetailFormatError
        from plan_tool.parser import parse_plan
        from plan_tool.review import audit_plan_until_stable

        plan_path = tmp_path / "audit-plan.md"
        plan_path.write_text(
            "---\n"
            "title: Audit Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: build the thing\n"
            "    status: pending\n"
            "---\n\n"
            "## Overview\n\nDo the thing.\n",
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)

        calls = {"n": 0}

        def flaky_render(*args, **kwargs):
            calls["n"] += 1
            raise DetailFormatError("boom")

        monkeypatch.setattr(review_module, "render_plan_audit_prompt", flaky_render)

        with pytest.raises(DetailFormatError):
            audit_plan_until_stable(
                plan,
                plan_path,
                repo_root=tmp_path,
                invoker=lambda _prompt: (
                    0, "## Correctness findings\n\n_(none)_\n\n"
                    "## Completeness findings\n\n_(none)_\n",
                ),
                max_passes=2,
                dry_rounds=1,
            )
        # Exactly one call: the estimator's own, immediately re-raised —
        # not swallowed and retried by the main pass loop.
        assert calls["n"] == 1


# --- granularity-merge re-ground finding (reconcile lane) ------------------


_REGROUND_PLAN = """---
title: Re-ground Test Plan
status: in-progress
priority: medium
steps:
  - id: 1
    title: Build the parser
    files:
      - parser.py
    status: done
  - id: 2
    title: Wire up the renderer
    files:
      - renderer.py
    depends_on: [1]
    status: current
  - id: 3
    title: Add foo endpoint
    files:
      - foo_endpoint.py
    depends_on: [2]
  - id: 4
    title: Add bar utility
    files:
      - utils.py
    depends_on: [2]
---

# Re-ground Test Plan
"""


def _write_reground_fixture(tmp_path: Path) -> Path:
    """Plan whose pending steps 3 and 4 both already define their title
    symbols on disk, so ``heuristic_already_done`` flags two distinct
    steps."""
    plan_path = tmp_path / "1-reground-test.md"
    plan_path.write_text(_REGROUND_PLAN, encoding="utf-8")
    (tmp_path / "parser.py").write_text(
        "class Parser:\n    pass\n", encoding="utf-8"
    )
    (tmp_path / "renderer.py").write_text(
        "def render(plan):\n    return None\n", encoding="utf-8"
    )
    (tmp_path / "foo_endpoint.py").write_text(
        "def foo():\n    return 1\n", encoding="utf-8"
    )
    (tmp_path / "utils.py").write_text(
        "def bar():\n    return 1\n", encoding="utf-8"
    )
    return plan_path


def _hit(step_id: int, file: str, symbol: str) -> HeuristicHit:
    return HeuristicHit(
        step_id=step_id, file=file, symbol=symbol, pattern=f"def {symbol}"
    )


class TestRegroundBuilder:
    def test_reground_builder_returns_none_for_no_hits(self) -> None:
        assert _reground_already_built_recommendation([], plan_name="p") is None

    def test_reground_builder_returns_none_for_single_step(self) -> None:
        hits = [
            _hit(3, "a.py", "foo"),
            _hit(3, "b.py", "bar"),
        ]
        assert _reground_already_built_recommendation(hits, plan_name="p") is None

    def test_reground_builder_emits_for_two_distinct_steps(self) -> None:
        hits = [_hit(3, "a.py", "foo"), _hit(4, "b.py", "bar")]
        rec = _reground_already_built_recommendation(hits, plan_name="p")
        assert rec is not None
        assert rec.source == "granularity-merge"
        assert rec.severity == "info"
        assert rec.step_id is None
        assert "3" in rec.body and "4" in rec.body
        assert "re-baseline" in rec.suggested_action.lower()
        assert "merge" in rec.suggested_action.lower()

    def test_reground_builder_counts_distinct_not_raw(self) -> None:
        hits = [
            _hit(3, "a.py", "foo"),
            _hit(3, "b.py", "qux"),
            _hit(4, "c.py", "bar"),
            _hit(4, "d.py", "baz"),
        ]
        rec = _reground_already_built_recommendation(hits, plan_name="p")
        assert rec is not None
        assert "3" in rec.title and "4" in rec.title

    def test_reground_id_stable_for_same_set(self) -> None:
        hits = [_hit(3, "a.py", "foo"), _hit(4, "b.py", "bar")]
        a = _reground_already_built_recommendation(hits, plan_name="p")
        b = _reground_already_built_recommendation(
            list(reversed(hits)), plan_name="p"
        )
        assert a is not None and b is not None
        assert a.id == b.id

    def test_reground_id_changes_when_set_changes(self) -> None:
        two = [_hit(3, "a.py", "foo"), _hit(4, "b.py", "bar")]
        three = two + [_hit(5, "c.py", "baz")]
        a = _reground_already_built_recommendation(two, plan_name="p")
        b = _reground_already_built_recommendation(three, plan_name="p")
        assert a is not None and b is not None
        assert a.id != b.id


class TestMergeActionGrammar:
    def _reground(self) -> Recommendation:
        hits = [_hit(3, "a.py", "foo"), _hit(4, "b.py", "bar"), _hit(5, "c.py", "baz")]
        rec = _reground_already_built_recommendation(hits, plan_name="p")
        assert rec is not None
        return rec

    def test_merge_action_constants_pin_values(self) -> None:
        assert MERGE_ACTION_MERGE == "merge"
        assert MERGE_ACTION_REGROUND == "reground"

    def test_reground_suggested_action_carries_reground_directive(self) -> None:
        action = parse_merge_action(self._reground())
        assert action is not None
        assert action.kind == MERGE_ACTION_REGROUND

    def test_reground_directive_carries_full_id_set(self) -> None:
        action = parse_merge_action(self._reground())
        assert action is not None
        assert action.step_ids == (3, 4, 5)

    def test_reground_directive_kind_is_reground_despite_merge_prose(self) -> None:
        rec = self._reground()
        # Prose deliberately mentions merge / plan-tool merge...
        assert "merge" in rec.suggested_action.lower()
        # ...but the marker kind wins.
        action = parse_merge_action(rec)
        assert action is not None
        assert action.kind == MERGE_ACTION_REGROUND
        assert action.kind != MERGE_ACTION_MERGE

    def test_parse_merge_action_returns_none_for_non_merge_source(self) -> None:
        rec = Recommendation(
            id="x",
            source="deps",
            severity="high",
            step_id=4,
            title="t",
            body="b",
            suggested_action="→ reground steps: 3, 4",
        )
        assert parse_merge_action(rec) is None

    def test_parse_merge_action_returns_none_without_marker(self) -> None:
        rec = Recommendation(
            id="x",
            source=_GRANULARITY_MERGE_SOURCE,
            severity="info",
            step_id=None,
            title="t",
            body="b",
            suggested_action="merge these steps somehow",
        )
        assert parse_merge_action(rec) is None

    def test_is_pairwise_merge_finding_covers_contiguous_and_gapped(self) -> None:
        # A pairwise granularity-merge finding (step_id set) is a merge whether
        # it carries a dispatchable marker (contiguous) or not (gapped) — the
        # walk's skip_info carve keeps both visible.
        contiguous = Recommendation(
            id="m1", source=_GRANULARITY_MERGE_SOURCE, severity="info", step_id=2,
            title="t", body="b",
            suggested_action="Consider merging steps 2 and 3. "
            + render_merge_action(MERGE_ACTION_MERGE, (2, 3)),
        )
        gapped = Recommendation(
            id="m2", source=_GRANULARITY_MERGE_SOURCE, severity="info", step_id=2,
            title="t", body="b",
            suggested_action="Consider merging steps 2 and 5 (gapped).",  # no marker
        )
        assert is_pairwise_merge_finding(contiguous) is True
        assert is_pairwise_merge_finding(gapped) is True

    def test_is_pairwise_merge_finding_excludes_reground_and_other_sources(
        self,
    ) -> None:
        # The plan-wide re-ground finding (step_id None) is NOT a pairwise merge,
        # and a non-granularity-merge source never is.
        assert is_pairwise_merge_finding(self._reground()) is False
        assert is_pairwise_merge_finding(
            Recommendation(
                id="d", source="deps", severity="high", step_id=2,
                title="t", body="b", suggested_action="x",
            )
        ) is False

    def test_reground_directive_does_not_change_rec_id(self) -> None:
        # The marker lives on suggested_action, not the fingerprint, so the id
        # is unchanged from the pre-directive fingerprint scheme.
        rec = self._reground()
        expected = _make_rec_id(
            None, _GRANULARITY_MERGE_SOURCE, "reground-already-built:3,4,5"
        )
        assert rec.id == expected

    def test_render_parse_round_trip_for_reground(self) -> None:
        prose = "re-baseline. " + render_merge_action(MERGE_ACTION_REGROUND, (3, 4, 5))
        rec = Recommendation(
            id="x",
            source=_GRANULARITY_MERGE_SOURCE,
            severity="info",
            step_id=None,
            title="t",
            body="b",
            suggested_action=prose,
        )
        action = parse_merge_action(rec)
        assert action == MergeAction(kind=MERGE_ACTION_REGROUND, step_ids=(3, 4, 5))

    def test_render_parse_round_trip_for_merge(self) -> None:
        prose = "Consider merging. " + render_merge_action(MERGE_ACTION_MERGE, (1, 2))
        rec = Recommendation(
            id="x",
            source=_GRANULARITY_MERGE_SOURCE,
            severity="info",
            step_id=1,
            title="t",
            body="b",
            suggested_action=prose,
        )
        action = parse_merge_action(rec)
        assert action == MergeAction(kind=MERGE_ACTION_MERGE, step_ids=(1, 2))


class TestGranularityMergeRouting:
    def _rec(self) -> Recommendation:
        hits = [_hit(3, "a.py", "foo"), _hit(4, "b.py", "bar")]
        rec = _reground_already_built_recommendation(hits, plan_name="p")
        assert rec is not None
        return rec

    def test_granularity_merge_not_apply_eligible(self) -> None:
        assert is_apply_eligible(self._rec()) is False
        assert _GRANULARITY_MERGE_SOURCE not in APPLY_ELIGIBLE_SOURCES

    def test_granularity_merge_not_structural(self) -> None:
        assert is_structural(self._rec()) is False
        assert _GRANULARITY_MERGE_SOURCE not in STRUCTURAL_SOURCES

    def test_granularity_merge_triage_reason_names_merge_or_reground(self) -> None:
        reason = triage_reason(self._rec())
        assert "merge" in reason.lower()
        assert "re-ground" in reason.lower() or "re-baseline" in reason.lower()
        assert "plan-tool split" not in reason
        assert "author lessons" not in reason

    def test_granularity_merge_literal_matches_granularity_module(self) -> None:
        assert _GRANULARITY_MERGE_SOURCE == GRANULARITY_MERGE_SOURCE


class TestExtractRegroundGating:
    def _hits(self) -> list[HeuristicHit]:
        return [_hit(3, "a.py", "foo"), _hit(4, "b.py", "bar")]

    def _extract(self, tmp_path: Path, **kw: object) -> list[Recommendation]:
        plan_path = _write_reground_fixture(tmp_path)
        plan = parse_plan(plan_path)
        return extract_recommendations(
            plan,
            "reground-test",
            repo_root=tmp_path,
            file_checks=[],
            heuristic_hits=kw.pop("heuristic_hits", self._hits()),
            dep_issues=[],
            path_style_hint=None,
            **kw,
        )

    def test_extract_emits_reground_in_reconcile_lane(self, tmp_path: Path) -> None:
        recs = self._extract(tmp_path, reconcile_lane=True, step_filter=None)
        merge = [r for r in recs if r.source == "granularity-merge"]
        assert len(merge) == 1

    def test_extract_omits_reground_by_default(self, tmp_path: Path) -> None:
        recs = self._extract(tmp_path)
        assert not [r for r in recs if r.source == "granularity-merge"]

    def test_extract_omits_reground_under_step_filter(self, tmp_path: Path) -> None:
        recs = self._extract(tmp_path, reconcile_lane=True, step_filter=3)
        assert not [r for r in recs if r.source == "granularity-merge"]

    def test_extract_omits_reground_for_single_already_built_step(
        self, tmp_path: Path
    ) -> None:
        recs = self._extract(
            tmp_path,
            reconcile_lane=True,
            step_filter=None,
            heuristic_hits=[_hit(4, "utils.py", "bar")],
        )
        assert not [r for r in recs if r.source == "granularity-merge"]


@pytest.mark.integration
class TestRegroundReconcileLaneIntegration:
    def test_review_plan_full_surfaces_reground_finding(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_reground_fixture(tmp_path)
        plan = parse_plan(plan_path)
        hits = heuristic_already_done(plan, tmp_path)
        assert len({h.step_id for h in hits}) >= 2, "fixture must flag ≥2 steps"
        result = review_plan_full(
            plan_path,
            repo_root=tmp_path,
            plan_name="reground-test",
            invoker=None,
        )
        merge = [
            r for r in result.recommendations if r.source == "granularity-merge"
        ]
        assert len(merge) == 1
        assert "info" in result.report.lower()

    def test_collect_deterministic_findings_omits_reground(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_reground_fixture(tmp_path)
        plan = parse_plan(plan_path)
        recs = collect_deterministic_findings(
            plan,
            plan_path,
            repo_root=tmp_path,
            plan_name="reground-test",
        )
        assert not [r for r in recs if r.source == "granularity-merge"]


# --- Step 2: pairwise granularity-merge in saved reconcile recommendations ---


_PAIRWISE_MERGE_PLAN = """---
title: Pairwise Merge Plan
status: in-progress
priority: medium
steps:
  - id: 1
    title: Add alpha widget
    files:
      - widgets.py
  - id: 2
    title: Add beta widget
    files:
      - widgets.py
    depends_on: [1]
---

# Pairwise Merge Plan
"""


_PAIRWISE_MERGE_AND_REGROUND_PLAN = """---
title: Merge And Reground Plan
status: in-progress
priority: medium
steps:
  - id: 1
    title: Add alpha helper
    files:
      - combined.py
  - id: 2
    title: Add beta helper
    files:
      - combined.py
    depends_on: [1]
---

# Merge And Reground Plan
"""


def _write_pairwise_merge_fixture(tmp_path: Path) -> Path:
    """Two dependency-adjacent steps sharing an identical, non-empty file set,
    so the granularity advisor emits one pairwise ``granularity-merge``
    finding. File content names no title symbol, so the re-ground heuristic
    stays silent."""
    plan_path = tmp_path / "1-pairwise-merge.md"
    plan_path.write_text(_PAIRWISE_MERGE_PLAN, encoding="utf-8")
    (tmp_path / "widgets.py").write_text("DATA = 1\n", encoding="utf-8")
    return plan_path


def _write_pairwise_merge_and_reground_fixture(tmp_path: Path) -> Path:
    """Two dependency-adjacent steps sharing a file that already defines both
    title symbols, so the fixture trips *both* the pairwise merge signal
    (identical file sets) and the plan-wide re-ground signal (≥2 steps flagged
    by ``heuristic_already_done``)."""
    plan_path = tmp_path / "1-merge-and-reground.md"
    plan_path.write_text(_PAIRWISE_MERGE_AND_REGROUND_PLAN, encoding="utf-8")
    (tmp_path / "combined.py").write_text(
        "def alpha():\n    return 1\n\n\ndef beta():\n    return 2\n",
        encoding="utf-8",
    )
    return plan_path


def _pairwise_merge_recs(tmp_path: Path) -> list[Recommendation]:
    """The granularity advisor's pairwise ``granularity-merge`` findings for the
    identical-file-set fixture (``step_id`` set; excludes plan-wide re-ground)."""
    plan = parse_plan(_write_pairwise_merge_fixture(tmp_path))
    recs = assess_granularity(
        plan, stage="completeness", evidence=GranularityEvidence()
    )
    merge = [
        r
        for r in recs
        if r.source == GRANULARITY_MERGE_SOURCE and r.step_id is not None
    ]
    assert merge, "fixture must produce ≥1 pairwise merge finding"
    return merge


class TestExtractPairwiseMergeGating:
    def _extract(
        self,
        tmp_path: Path,
        merge_recs: list[Recommendation],
        **kw: object,
    ) -> list[Recommendation]:
        plan = parse_plan(_write_pairwise_merge_fixture(tmp_path))
        return extract_recommendations(
            plan,
            "pairwise-merge",
            repo_root=tmp_path,
            file_checks=[],
            heuristic_hits=[],
            dep_issues=[],
            path_style_hint=None,
            granularity_recommendations=merge_recs,
            **kw,
        )

    def test_extract_emits_pairwise_merge_in_reconcile_lane(
        self, tmp_path: Path
    ) -> None:
        merge = _pairwise_merge_recs(tmp_path)
        recs = self._extract(
            tmp_path, merge, reconcile_lane=True, step_filter=None
        )
        pairwise = [
            r
            for r in recs
            if r.source == GRANULARITY_MERGE_SOURCE and r.step_id is not None
        ]
        assert {r.id for r in pairwise} == {r.id for r in merge}

    def test_extract_omits_pairwise_merge_by_default(
        self, tmp_path: Path
    ) -> None:
        merge = _pairwise_merge_recs(tmp_path)
        recs = self._extract(tmp_path, merge)
        assert not [r for r in recs if r.source == GRANULARITY_MERGE_SOURCE]

    def test_extract_omits_pairwise_merge_under_step_filter(
        self, tmp_path: Path
    ) -> None:
        merge = _pairwise_merge_recs(tmp_path)
        recs = self._extract(
            tmp_path, merge, reconcile_lane=True, step_filter=1
        )
        assert not [r for r in recs if r.source == GRANULARITY_MERGE_SOURCE]

    def test_pairwise_merge_recommendation_is_passed_through_unchanged(
        self, tmp_path: Path
    ) -> None:
        merge = _pairwise_merge_recs(tmp_path)
        recs = self._extract(
            tmp_path, merge, reconcile_lane=True, step_filter=None
        )
        surfaced = {
            r.id: r
            for r in recs
            if r.source == GRANULARITY_MERGE_SOURCE and r.step_id is not None
        }
        for original in merge:
            passed = surfaced[original.id]
            # Object identity: the producer rec is threaded through, not rebuilt.
            assert passed is original
            assert passed.suggested_action == original.suggested_action
            assert passed.severity == original.severity
            assert passed.step_id == original.step_id
            assert passed.body == original.body


@pytest.mark.integration
class TestPairwiseMergeReconcileLaneIntegration:
    def test_review_plan_full_surfaces_pairwise_merge_finding(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_pairwise_merge_fixture(tmp_path)
        result = review_plan_full(
            plan_path,
            repo_root=tmp_path,
            plan_name="pairwise-merge",
            invoker=None,
        )
        merge = [
            r
            for r in result.recommendations
            if r.source == GRANULARITY_MERGE_SOURCE
        ]
        assert len(merge) == 1
        # Pairwise, not plan-wide re-ground: the finding carries a step id.
        assert merge[0].step_id is not None

    def test_review_plan_full_can_surface_pairwise_merge_and_reground(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_pairwise_merge_and_reground_fixture(tmp_path)
        plan = parse_plan(plan_path)
        hits = heuristic_already_done(plan, tmp_path)
        assert len({h.step_id for h in hits}) >= 2, "fixture must flag ≥2 steps"
        result = review_plan_full(
            plan_path,
            repo_root=tmp_path,
            plan_name="merge-and-reground",
            invoker=None,
        )
        merge = [
            r
            for r in result.recommendations
            if r.source == GRANULARITY_MERGE_SOURCE
        ]
        pairwise = [r for r in merge if r.step_id is not None]
        reground = [r for r in merge if r.step_id is None]
        assert pairwise, "pairwise merge finding must survive"
        assert len(reground) == 1, "re-ground finding must survive alongside it"


# --- Step 1: code-grounded split producer (the inverse of re-ground) ---------


def _split_plan(*steps: Step) -> Plan:
    return Plan(
        title="Code Split Plan",
        status="in-progress",
        priority="medium",
        steps=list(steps),
    )


def _split_step(
    step_id: int,
    files: list[str],
    *,
    status: StepStatus = StepStatus.PENDING,
    title: Optional[str] = None,
) -> Step:
    return Step(
        id=step_id,
        title=title or f"Add step {step_id} widget",
        files=list(files),
        status=status,
    )


def _by_step(hits: list[HeuristicHit]) -> dict[int, list[HeuristicHit]]:
    """Group hits by step_id — mirrors the map extract_recommendations passes
    the split producer (which now takes the prebuilt map, not a raw list)."""
    grouped: dict[int, list[HeuristicHit]] = {}
    for h in hits:
        grouped.setdefault(h.step_id, []).append(h)
    return grouped


def test_extract_recommendations_records_code_reveals_split_telemetry(
    tmp_path: Path,
) -> None:
    """Wiring: when the detector fires in the reconcile lane, extract_recommendations
    records one best-effort telemetry event carrying the flagged step ids (#117)."""
    from plan_tool.telemetry import read_decisions

    plan = _split_plan(_split_step(1, ["a.py", "b.py", "c.py"]))
    # a.py + b.py built (hit), c.py declared but un-built + scannable non-test.
    hits = [_hit(1, "a.py", "foo"), _hit(1, "b.py", "bar")]
    extract_recommendations(
        plan, "myplan",
        repo_root=tmp_path,
        file_checks=[],
        heuristic_hits=hits,
        dep_issues=[],
        path_style_hint=None,
        reconcile_lane=True,
    )
    fires = [e for e in read_decisions(tmp_path) if e.decision == "code-reveals-split"]
    assert len(fires) == 1
    assert fires[0].plan_slug == "myplan"
    assert fires[0].context["fired"] == 1
    assert fires[0].context["step_ids"] == ["1"]


def test_extract_recommendations_no_telemetry_when_detector_silent(
    tmp_path: Path,
) -> None:
    """No fire → no telemetry noise (all declared files built, nothing un-built)."""
    from plan_tool.telemetry import read_decisions

    plan = _split_plan(_split_step(1, ["a.py", "b.py"]))
    hits = [_hit(1, "a.py", "foo"), _hit(1, "b.py", "bar")]
    extract_recommendations(
        plan, "myplan",
        repo_root=tmp_path,
        file_checks=[],
        heuristic_hits=hits,
        dep_issues=[],
        path_style_hint=None,
        reconcile_lane=True,
    )
    assert [e for e in read_decisions(tmp_path) if e.decision == "code-reveals-split"] == []


def test_code_reveals_split_event_carries_code_fingerprint_digest(tmp_path: Path) -> None:
    """A reconcile-lane split fire with a real plan_path stamps both join keys:
    plan_fingerprint and the canonical code-state digest."""
    from plan_tool.fingerprint import compute_code_fingerprint
    from plan_tool.review_persistence import compute_plan_fingerprint
    from plan_tool.telemetry import code_fingerprint_digest, read_decisions

    # a.py + b.py built (hits) on disk, c.py declared but un-built → split fires.
    (tmp_path / "a.py").write_text("def foo():\n    pass\n")
    (tmp_path / "b.py").write_text("def bar():\n    pass\n")
    plan_path = tmp_path / "myplan.md"
    plan_path.write_text("# plan\n")
    plan = _split_plan(_split_step(1, ["a.py", "b.py", "c.py"]))
    hits = [_hit(1, "a.py", "foo"), _hit(1, "b.py", "bar")]
    extract_recommendations(
        plan, "myplan",
        repo_root=tmp_path,
        file_checks=[],
        heuristic_hits=hits,
        dep_issues=[],
        path_style_hint=None,
        reconcile_lane=True,
        plan_path=plan_path,
    )
    fires = [e for e in read_decisions(tmp_path) if e.decision == "code-reveals-split"]
    assert len(fires) == 1
    assert fires[0].plan_fingerprint == compute_plan_fingerprint(plan_path)
    assert fires[0].code_fingerprint == code_fingerprint_digest(
        compute_code_fingerprint(plan, plan_path, tmp_path)
    )


@pytest.mark.parametrize("helper_name", ["plan", "code"])
def test_code_reveals_split_fingerprint_failure_is_best_effort(
    tmp_path: Path, monkeypatch, helper_name: str,
) -> None:
    import plan_tool.fingerprint as fingerprint_module
    import plan_tool.review_persistence as persistence
    from plan_tool.telemetry import read_decisions

    plan_path = tmp_path / "myplan.md"
    plan_path.write_text("# plan\n")
    plan = _split_plan(_split_step(1, ["a.py", "b.py", "c.py"]))
    hits = [_hit(1, "a.py", "foo"), _hit(1, "b.py", "bar")]

    expected = _code_reveals_split_recommendations(
        _by_step(hits), plan, plan_name="myplan"
    )

    def fail_fingerprint(*_args, **_kwargs):
        raise OSError("fingerprint unavailable")

    if helper_name == "plan":
        monkeypatch.setattr(
            persistence, "compute_plan_fingerprint", fail_fingerprint
        )
    else:
        monkeypatch.setattr(
            fingerprint_module, "compute_code_fingerprint", fail_fingerprint
        )
    recommendations = extract_recommendations(
        plan,
        "myplan",
        repo_root=tmp_path,
        file_checks=[],
        heuristic_hits=hits,
        dep_issues=[],
        path_style_hint=None,
        reconcile_lane=True,
        plan_path=plan_path,
    )
    split_recommendations = [
        rec for rec in recommendations if rec.source == "granularity-split"
    ]
    assert split_recommendations == expected
    (event,) = [
        event
        for event in read_decisions(tmp_path)
        if event.decision == "code-reveals-split"
    ]
    assert event.plan_fingerprint == ""
    assert event.code_fingerprint == ""


def test_code_reveals_split_recorder_failure_is_best_effort(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import plan_tool.review as review_module

    plan_path = tmp_path / "myplan.md"
    plan_path.write_text("# plan\n")
    plan = _split_plan(_split_step(1, ["a.py", "b.py", "c.py"]))
    hits = [_hit(1, "a.py", "foo"), _hit(1, "b.py", "bar")]
    expected = _code_reveals_split_recommendations(
        _by_step(hits), plan, plan_name="myplan"
    )

    def fail_recorder(*_args, **_kwargs):
        raise OSError("telemetry unavailable")

    monkeypatch.setattr(
        review_module, "record_code_reveals_split", fail_recorder
    )
    recommendations = extract_recommendations(
        plan,
        "myplan",
        repo_root=tmp_path,
        file_checks=[],
        heuristic_hits=hits,
        dep_issues=[],
        path_style_hint=None,
        reconcile_lane=True,
        plan_path=plan_path,
    )

    assert [
        rec for rec in recommendations if rec.source == "granularity-split"
    ] == expected


def test_extract_recommendations_without_plan_path_still_records_split(
    tmp_path: Path,
) -> None:
    """plan_path defaulting to None: the split event still records (fingerprints
    empty) and nothing raises — the optional param is safe."""
    from plan_tool.telemetry import read_decisions

    plan = _split_plan(_split_step(1, ["a.py", "b.py", "c.py"]))
    hits = [_hit(1, "a.py", "foo"), _hit(1, "b.py", "bar")]
    extract_recommendations(
        plan, "myplan",
        repo_root=tmp_path,
        file_checks=[],
        heuristic_hits=hits,
        dep_issues=[],
        path_style_hint=None,
        reconcile_lane=True,
    )
    fires = [e for e in read_decisions(tmp_path) if e.decision == "code-reveals-split"]
    assert len(fires) == 1
    assert fires[0].plan_fingerprint == ""
    assert fires[0].code_fingerprint == ""


def test_collect_deterministic_findings_records_no_split(tmp_path: Path) -> None:
    """The non-reconcile caller (empty hits, reconcile_lane False) emits no split
    event, so leaving its extract_recommendations call at the default plan_path=None
    is correct."""
    from plan_tool.review import collect_deterministic_findings
    from plan_tool.telemetry import read_decisions

    plan = _split_plan(_split_step(1, ["a.py", "b.py", "c.py"]))
    plan_path = tmp_path / "myplan.md"
    # Real callers always pass a plan_path that already parsed into `plan`
    # (apply_finding / _compute_findings_delta both call parse_plan(plan_path)
    # first), so the file needs real frontmatter here too — collect_deterministic_findings
    # now rejects an unmatched fence up front, which requires the body to be
    # splittable in the first place.
    plan_path.write_text(
        "---\ntitle: Code Split Plan\nstatus: in-progress\npriority: medium\n"
        "steps: []\n---\n\n# plan\n"
    )
    collect_deterministic_findings(
        plan, plan_path, repo_root=tmp_path, plan_name="myplan"
    )
    assert [
        e for e in read_decisions(tmp_path) if e.decision == "code-reveals-split"
    ] == []


class TestCodeRevealsSplitBuilder:
    def test_split_builder_returns_empty_for_no_hits(self) -> None:
        plan = _split_plan(_split_step(1, ["a.py", "b.py", "c.py"]))
        assert _code_reveals_split_recommendations({}, plan, plan_name="p") == []

    def test_split_builder_no_finding_for_single_file(self) -> None:
        plan = _split_plan(_split_step(1, ["a.py", "b.py"]))
        hits = [_hit(1, "a.py", "foo"), _hit(1, "a.py", "bar")]
        assert _code_reveals_split_recommendations(_by_step(hits), plan, plan_name="p") == []

    def test_split_builder_no_finding_when_all_declared_files_hit(self) -> None:
        plan = _split_plan(_split_step(1, ["a.py", "b.py"]))
        hits = [_hit(1, "a.py", "foo"), _hit(1, "b.py", "bar")]
        assert _code_reveals_split_recommendations(_by_step(hits), plan, plan_name="p") == []

    def test_split_builder_no_finding_when_only_unbuilt_file_is_a_test(
        self,
    ) -> None:
        # Impl landed, tests pending → one half-done concern, not a split.
        plan = _split_plan(_split_step(1, ["a.py", "b.py", "tests/test_c.py"]))
        hits = [_hit(1, "a.py", "foo"), _hit(1, "b.py", "bar")]
        assert _code_reveals_split_recommendations(_by_step(hits), plan, plan_name="p") == []

    def test_split_builder_ignores_test_hits_on_built_side(self) -> None:
        # Hits on pre-written test files must not count toward the >=2 "built
        # part": a step whose only hits land on test files (title symbol matching
        # test_foo) with production code un-built is NOT a built/un-built split.
        plan = _split_plan(
            _split_step(1, ["tests/test_a.py", "tests/test_b.py", "a.py"])
        )
        hits = [_hit(1, "tests/test_a.py", "foo"), _hit(1, "tests/test_b.py", "bar")]
        assert (
            _code_reveals_split_recommendations(_by_step(hits), plan, plan_name="p")
            == []
        )

    def test_split_builder_no_finding_when_only_unbuilt_file_is_unscannable(
        self,
    ) -> None:
        # config.yaml is never opened by heuristic_already_done, so its lack of a
        # hit is "not scanned", not "un-built" — a fully-built step whose only
        # un-hit declared file is unscannable must not be flagged as a split.
        plan = _split_plan(_split_step(1, ["a.py", "b.py", "config.yaml"]))
        hits = [_hit(1, "a.py", "foo"), _hit(1, "b.py", "bar")]
        assert (
            _code_reveals_split_recommendations(_by_step(hits), plan, plan_name="p")
            == []
        )

    def test_split_builder_emits_when_unbuilt_test_and_nontest_remain(
        self,
    ) -> None:
        # An un-hit test file plus an un-hit non-test file → a real second
        # concern remains, so it fires.
        plan = _split_plan(
            _split_step(1, ["a.py", "b.py", "tests/test_c.py", "d.py"])
        )
        hits = [_hit(1, "a.py", "foo"), _hit(1, "b.py", "bar")]
        recs = _code_reveals_split_recommendations(_by_step(hits), plan, plan_name="p")
        assert len(recs) == 1
        assert "`d.py`" in recs[0].body

    def test_split_builder_emits_for_built_and_unbuilt_mix(self) -> None:
        plan = _split_plan(_split_step(1, ["a.py", "b.py", "c.py"]))
        hits = [_hit(1, "a.py", "foo"), _hit(1, "b.py", "bar")]
        recs = _code_reveals_split_recommendations(_by_step(hits), plan, plan_name="demo")
        assert len(recs) == 1
        rec = recs[0]
        assert rec.source == "granularity-split"
        assert rec.severity == "info"
        assert rec.step_id == 1
        # Runnable scaffold: plan name + --step render, not a bare verb.
        assert "plan-tool split demo --step 1" in rec.suggested_action
        # The two load-bearing caveats.
        assert "separable concerns" in rec.body
        assert "mark the built half `done`" in rec.body

    def test_split_builder_skips_done_step(self) -> None:
        # A DONE step fed a synthetic qualifying hit list — the only input that
        # reaches a done step, since heuristic_already_done never emits hits for
        # done steps — yields nothing (the structural status exclusion).
        plan = _split_plan(
            _split_step(1, ["a.py", "b.py", "c.py"], status=StepStatus.DONE)
        )
        hits = [_hit(1, "a.py", "foo"), _hit(1, "b.py", "bar")]
        assert _code_reveals_split_recommendations(_by_step(hits), plan, plan_name="p") == []

    def test_split_builder_counts_distinct_files_not_raw_hits(self) -> None:
        plan = _split_plan(_split_step(1, ["a.py", "b.py"]))
        hits = [
            _hit(1, "a.py", "foo"),
            _hit(1, "a.py", "bar"),
            _hit(1, "a.py", "baz"),
        ]
        assert _code_reveals_split_recommendations(_by_step(hits), plan, plan_name="p") == []

    def test_split_builder_id_stable_across_file_set_changes(self) -> None:
        plan = _split_plan(_split_step(1, ["a.py", "b.py", "c.py"]))
        # Pass 1: a.py + b.py built, c.py un-built.
        recs1 = _code_reveals_split_recommendations(
            _by_step([_hit(1, "a.py", "foo"), _hit(1, "b.py", "bar")]), plan, plan_name="p"
        )
        # Pass 2: a.py + c.py built, b.py un-built (different hit-file set).
        recs2 = _code_reveals_split_recommendations(
            _by_step([_hit(1, "a.py", "foo"), _hit(1, "c.py", "baz")]), plan, plan_name="p"
        )
        assert recs1[0].id == recs2[0].id  # step-keyed, survives a prior skip

    def test_split_builder_distinct_steps_yield_distinct_ids(self) -> None:
        plan = _split_plan(
            _split_step(1, ["a.py", "b.py", "c.py"]),
            _split_step(2, ["d.py", "e.py", "f.py"]),
        )
        hits = [
            _hit(1, "a.py", "foo"),
            _hit(1, "b.py", "bar"),
            _hit(2, "d.py", "baz"),
            _hit(2, "e.py", "qux"),
        ]
        recs = _code_reveals_split_recommendations(_by_step(hits), plan, plan_name="p")
        assert {r.id for r in recs} == {recs[0].id, recs[1].id}
        assert recs[0].id != recs[1].id

    def test_two_qualifying_steps_yield_two_findings(self) -> None:
        plan = _split_plan(
            _split_step(1, ["a.py", "b.py", "c.py"]),
            _split_step(2, ["d.py", "e.py", "f.py"]),
        )
        hits = [
            _hit(1, "a.py", "foo"),
            _hit(1, "b.py", "bar"),
            _hit(2, "d.py", "baz"),
            _hit(2, "e.py", "qux"),
        ]
        recs = _code_reveals_split_recommendations(_by_step(hits), plan, plan_name="demo")
        assert len(recs) == 2
        assert {r.step_id for r in recs} == {1, 2}
        assert "plan-tool split demo --step 1" in recs[0].suggested_action
        assert "plan-tool split demo --step 2" in recs[1].suggested_action


class TestExtractCodeSplitGating:
    def _plan(self) -> Plan:
        return _split_plan(_split_step(1, ["a.py", "b.py", "c.py"]))

    def _hits(self) -> list[HeuristicHit]:
        return [_hit(1, "a.py", "foo"), _hit(1, "b.py", "bar")]

    def _extract(
        self, tmp_path: Path, plan: Optional[Plan] = None, **kw: object
    ) -> list[Recommendation]:
        return extract_recommendations(
            plan or self._plan(),
            "code-split",
            repo_root=tmp_path,
            file_checks=[],
            heuristic_hits=kw.pop("heuristic_hits", self._hits()),
            dep_issues=[],
            path_style_hint=None,
            **kw,
        )

    def _split(self, recs: list[Recommendation]) -> list[Recommendation]:
        return [r for r in recs if r.source == "granularity-split"]

    def test_extract_emits_split_in_reconcile_lane(self, tmp_path: Path) -> None:
        recs = self._extract(tmp_path, reconcile_lane=True, step_filter=None)
        split = self._split(recs)
        assert len(split) == 1
        assert split[0].step_id == 1

    def test_extract_omits_split_by_default(self, tmp_path: Path) -> None:
        assert not self._split(self._extract(tmp_path))

    def test_extract_omits_split_under_step_filter(self, tmp_path: Path) -> None:
        recs = self._extract(tmp_path, reconcile_lane=True, step_filter=1)
        assert not self._split(recs)

    def test_split_does_not_suppress_reground(self, tmp_path: Path) -> None:
        # The split detector is purely additive: it never filters re-ground's
        # input. Step 1 is split-qualifying AND already-built alongside steps 2
        # and 3, so re-ground fires over the FULL set {1, 2, 3} (a low-confidence
        # split must not suppress the higher-confidence re-baseline signal), and
        # step 1 additionally carries the split advisory. Both co-fire.
        plan = _split_plan(
            _split_step(1, ["a.py", "b.py", "c.py"]),
            _split_step(2, ["d.py"]),
            _split_step(3, ["e.py"]),
        )
        hits = [
            _hit(1, "a.py", "foo"),
            _hit(1, "b.py", "bar"),
            _hit(2, "d.py", "baz"),
            _hit(3, "e.py", "qux"),
        ]
        recs = self._extract(
            tmp_path, plan, heuristic_hits=hits, reconcile_lane=True
        )
        assert [r.step_id for r in self._split(recs)] == [1]
        reground = [
            r
            for r in recs
            if r.source == "granularity-merge" and r.step_id is None
        ]
        assert len(reground) == 1
        action = parse_merge_action(reground[0])
        assert action is not None and set(action.step_ids) == {1, 2, 3}

    def test_reground_survives_when_split_qualifying_step_present(
        self, tmp_path: Path
    ) -> None:
        # Regression guard: a split-qualifying step must NOT drop re-ground below
        # its 2-step threshold. Steps 1 and 2 are both already-built (so re-ground
        # fires over {1, 2}); step 1 also qualifies for split. Pre-fix, filtering
        # step 1 out of re-ground's input left only {2} and suppressed re-ground.
        plan = _split_plan(
            _split_step(1, ["a.py", "b.py", "c.py"]),
            _split_step(2, ["d.py"]),
        )
        hits = [
            _hit(1, "a.py", "foo"),
            _hit(1, "b.py", "bar"),
            _hit(2, "d.py", "baz"),
        ]
        recs = self._extract(
            tmp_path, plan, heuristic_hits=hits, reconcile_lane=True
        )
        assert [r.step_id for r in self._split(recs)] == [1]
        reground = [
            r for r in recs
            if r.source == "granularity-merge" and r.step_id is None
        ]
        assert len(reground) == 1  # NOT suppressed by the split false-positive
        action = parse_merge_action(reground[0])
        assert action is not None and set(action.step_ids) == {1, 2}

    def test_pairwise_merge_not_excluded_for_split_step(
        self, tmp_path: Path
    ) -> None:
        # Static pairwise-merge findings are a DIFFERENT lens (structural, from
        # the granularity advisor) than the code-grounded split, so they are NOT
        # filtered against split-qualifying steps: both a merge over (1, 2) — a
        # pair including the split-qualifying step 1 — and the split-step-1 rec
        # survive. (Dropping the visible merge would hide the default-view signal
        # and, for a gapped pair, only ever catch its lo_id; only the re-ground
        # exclusion, same code-grounded signal family, is filtered.)
        plan = _split_plan(
            _split_step(1, ["a.py", "b.py", "c.py"]),
            _split_step(2, ["d.py"]),
        )
        merge_1_2 = Recommendation(
            id="m12", source=_GRANULARITY_MERGE_SOURCE, severity="info",
            step_id=1, title="Steps 1 and 2", body="b",
            suggested_action="Consider merging steps 1 and 2. "
            + render_merge_action(MERGE_ACTION_MERGE, (1, 2)),
        )
        recs = self._extract(
            tmp_path,
            plan,
            heuristic_hits=self._hits(),
            reconcile_lane=True,
            granularity_recommendations=[merge_1_2],
        )
        assert [r.step_id for r in self._split(recs)] == [1]
        merge_ids = {r.id for r in recs if r.source == "granularity-merge"}
        assert "m12" in merge_ids  # kept: split and static merge co-exist


_CODE_SPLIT_PLAN = """---
title: Code Split Test Plan
status: in-progress
priority: medium
steps:
  - id: 1
    title: Add alpha and beta handlers
    files:
      - alpha.py
      - beta.py
      - gamma.py
    status: current
---

# Code Split Test Plan
"""


def _write_code_split_fixture(tmp_path: Path) -> Path:
    """One non-done step whose declared alpha/beta files already define their
    title symbols on disk (built) while gamma.py names none (un-built), so
    ``heuristic_already_done`` flags ≥2 distinct files and leaves a non-test
    file un-hit — the code-grounded split signal."""
    plan_path = tmp_path / "1-code-split.md"
    plan_path.write_text(_CODE_SPLIT_PLAN, encoding="utf-8")
    (tmp_path / "alpha.py").write_text(
        "def alpha():\n    return 1\n", encoding="utf-8"
    )
    (tmp_path / "beta.py").write_text(
        "def beta():\n    return 2\n", encoding="utf-8"
    )
    (tmp_path / "gamma.py").write_text("VALUE = 3\n", encoding="utf-8")
    return plan_path


class TestCollectDeterministicOmitsCodeSplit:
    def test_collect_deterministic_findings_omits_code_split(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_code_split_fixture(tmp_path)
        plan = parse_plan(plan_path)
        recs = collect_deterministic_findings(
            plan,
            plan_path,
            repo_root=tmp_path,
            plan_name="code-split",
        )
        assert not [r for r in recs if r.source == "granularity-split"]


@pytest.mark.integration
class TestCodeSplitReconcileLaneIntegration:
    def test_review_plan_full_surfaces_code_split_finding(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_code_split_fixture(tmp_path)
        plan = parse_plan(plan_path)
        hits = heuristic_already_done(plan, tmp_path)
        built = {h.file for h in hits if h.step_id == 1}
        assert built == {"alpha.py", "beta.py"}, "fixture must build ≥2 files"
        result = review_plan_full(
            plan_path,
            repo_root=tmp_path,
            plan_name="code-split",
            invoker=None,
        )
        split = [
            r for r in result.recommendations if r.source == "granularity-split"
        ]
        assert len(split) == 1
        assert split[0].severity == "info"
        assert split[0].step_id == 1
        # Surfaces in the markdown report's severity tally (info-level)...
        assert "info" in result.report.lower()
        # ...and round-trips through the saved JSON sidecar.
        from plan_tool.review_persistence import save_review

        saved = save_review(
            plan_slug="code-split",
            plan_path=str(plan_path),
            repo_root=tmp_path,
            report_md=result.report,
            recommendations=result.recommendations,
        )
        assert "granularity-split" in saved.read_text(encoding="utf-8")


def merge_bridge_reauthor_context_fixture() -> Recommendation:
    """BACKLOG #91 code-logic pin: plan-level behavioral medium, no target file."""
    return Recommendation(
        id="merge-bridge-reauthor-context",
        source="plan-completeness",
        severity="medium",
        step_id=None,
        title="merge_bridge re-author path omits repo_root passthrough",
        body=(
            "Step 3's merge_bridge path shells out to Claude for re-authoring "
            "without passing repo_root through to the invoker, so runtime "
            "behavior diverges from the plan's passthrough contract and adds "
            "avoidable Claude cost at each call site."
        ),
        file_path=None,
        anchor="merge-bridge-reauthor-context",
    )


def docs_detail_body_fixture() -> Recommendation:
    """BACKLOG #91 docs pin: conceptual medium about detail-body file citations."""
    return Recommendation(
        id="detail-body-files-footprint",
        source="plan-completeness",
        severity="medium",
        step_id=2,
        title="Detail body omits declared step files",
        body=(
            "The detail body never cites the step's declared files: footprint — "
            "(no declared files cited in detail body). Each declared path from "
            "files: should appear in the detail-body prose."
        ),
        file_path=None,
    )


class TestClassifyFindingDomain:
    def test_classify_finding_domain_code_logic_fixture(self) -> None:
        assert (
            classify_finding_domain(merge_bridge_reauthor_context_fixture())
            == FINDING_DOMAIN_CODE_LOGIC
        )

    def test_classify_finding_domain_docs_fixture(self) -> None:
        assert (
            classify_finding_domain(docs_detail_body_fixture())
            == FINDING_DOMAIN_DOCS
        )

    def test_classify_finding_domain_test_path_in_body(self) -> None:
        rec = Recommendation(
            id="test-path",
            source="plan-completeness",
            severity="medium",
            step_id=1,
            title="Missing coverage",
            body="Add assertions in `tests/test_foo.py`.",
        )
        assert classify_finding_domain(rec) == FINDING_DOMAIN_UNIT_TEST

    def test_classify_finding_domain_docs_md_path(self) -> None:
        rec = Recommendation(
            id="docs-path",
            source="plan-completeness",
            severity="medium",
            step_id=1,
            title="Doc drift",
            body="Update the gate sequence in `docs/how-to/pipeline/audit.md`.",
        )
        assert classify_finding_domain(rec) == FINDING_DOMAIN_DOCS

    def test_classify_finding_domain_docs_absolute_non_prose_path(self) -> None:
        # Leading "/" must not defeat the docs-tree parts[:1] == ("docs",)
        # signal for a non-.md file (the _PROSE_EXTS check can't save this
        # one, since .json isn't in _PROSE_EXTS).
        rec = Recommendation(
            id="docs-abs-path",
            source="plan-completeness",
            severity="medium",
            step_id=1,
            title="Report drift",
            body=(
                "See `/docs/plan-reports/"
                "20260810-160558-run-reconcile.json`."
            ),
        )
        assert classify_finding_domain(rec) == FINDING_DOMAIN_DOCS

    def test_classify_finding_domain_generic_word_does_not_imply_docs(self) -> None:
        # "wording" is a common English word, not a reliable docs signal --
        # a real code-behavior finding must not be demoted just because its
        # prose happens to use it.
        rec = Recommendation(
            id="code-wording",
            source="plan-correctness",
            severity="medium",
            step_id=None,
            title="Fix the exception wording",
            body=(
                "The retry handler swallows the error before logging; fix "
                "the wording of the exception message so operators can "
                "tell which branch failed."
            ),
        )
        assert classify_finding_domain(rec) != FINDING_DOMAIN_DOCS

    def test_classify_finding_domain_generic_words_do_not_imply_code_logic(
        self,
    ) -> None:
        # "runtime"/"parameter"/"implementation"/"subprocess" are common
        # technical words, not reliable code-logic signals -- a doc-only
        # finding must not be forced blocking just because its prose
        # happens to use one.
        rec = Recommendation(
            id="docs-subprocess",
            source="plan-completeness",
            severity="medium",
            step_id=1,
            title="Document the audit's process model",
            body=(
                "`RUNBOOK.md` should document that the completeness-audit "
                "runs as a subprocess with its own runtime timeout and "
                "one required parameter; the implementation itself is "
                "unaffected."
            ),
        )
        assert classify_finding_domain(rec) == FINDING_DOMAIN_DOCS

    def test_classify_finding_domain_docs_implementation_plans_path(self) -> None:
        # BUG_BACKLOG regression: "implementation" used to substring-match
        # inside this repo's own docs/implementation-plans/ directory name,
        # misclassifying a pure docs-report finding as code-logic.
        rec = Recommendation(
            id="docs-impl-plans-path",
            source="plan-completeness",
            severity="medium",
            step_id=1,
            title="Report drift",
            body=(
                "See `docs/implementation-plans/plan-details/"
                "stage-differentiated-blocking/reports/"
                "20260810-160558-run-reconcile.json`."
            ),
        )
        assert classify_finding_domain(rec) == FINDING_DOMAIN_DOCS

    def test_classify_finding_domain_step_detail_file_path_not_docs(self) -> None:
        # A citation to the plan/detail bundle under audit is about that
        # bundle's content, not supporting docs -- must not classify "docs"
        # on the path alone. Falls to "unknown" (blocks), not "code-logic".
        rec = Recommendation(
            id="step-detail-path",
            source="plan-correctness",
            severity="medium",
            step_id=3,
            title="Detail omits rollback",
            body=(
                "`docs/implementation-plans/plan-details/foo/"
                "03-migrate-schema.md` doesn't cover the rollback path the "
                "plan body promises."
            ),
        )
        assert classify_finding_domain(rec) == FINDING_DOMAIN_UNKNOWN

    def test_classify_finding_domain_step_detail_reports_path_stays_docs(self) -> None:
        # Adjacent to the above: a *reports/* artifact under the same
        # plan-details/ segment is genuinely reporting output, not the
        # audited step content -- must keep classifying "docs".
        rec = Recommendation(
            id="step-detail-reports-path",
            source="plan-completeness",
            severity="medium",
            step_id=3,
            title="Report drift",
            body=(
                "See `docs/implementation-plans/plan-details/foo/reports/"
                "20260810-completeness.md`."
            ),
        )
        assert classify_finding_domain(rec) == FINDING_DOMAIN_DOCS

    def test_classify_finding_domain_code_py_path(self) -> None:
        rec = Recommendation(
            id="code-path",
            source="plan-completeness",
            severity="medium",
            step_id=1,
            title="Predicate gap",
            body="Wire stage into `plan_tool/convergence.py`.",
        )
        assert classify_finding_domain(rec) == FINDING_DOMAIN_CODE_LOGIC

    @pytest.mark.parametrize(
        "body",
        [
            "Fix `plan_tool/review.py` and document in `docs/how-to/pipeline/audit.md`.",
            "Touch `docs/PLAN_FORMAT.md` then `plan_tool/schema.py`.",
        ],
    )
    def test_classify_finding_domain_precedence_code_over_docs(
        self, body: str
    ) -> None:
        rec = Recommendation(
            id="prec-code-docs",
            source="plan-completeness",
            severity="medium",
            step_id=1,
            title="Mixed paths",
            body=body,
        )
        assert classify_finding_domain(rec) == FINDING_DOMAIN_CODE_LOGIC

    def test_classify_finding_domain_precedence_code_over_unit_test(self) -> None:
        rec = Recommendation(
            id="prec-code-test",
            source="plan-completeness",
            severity="medium",
            step_id=1,
            title="Mixed paths",
            body=(
                "Update `plan_tool/review.py` and add coverage in "
                "`tests/test_review.py`."
            ),
        )
        assert classify_finding_domain(rec) == FINDING_DOMAIN_CODE_LOGIC

    def test_classify_finding_domain_precedence_unit_test_over_docs(self) -> None:
        rec = Recommendation(
            id="prec-test-docs",
            source="plan-completeness",
            severity="medium",
            step_id=1,
            title="Mixed paths",
            body=(
                "Mirror the contract in `docs/how-to/pipeline/audit.md` inside "
                "`tests/test_audit_flow.py`."
            ),
        )
        assert classify_finding_domain(rec) == FINDING_DOMAIN_UNIT_TEST

    def test_classify_finding_domain_unknown_generic_prose(self) -> None:
        rec = Recommendation(
            id="generic",
            source="plan-completeness",
            severity="medium",
            step_id=None,
            title="Clarify plan goals",
            body="The plan should state its success criteria more clearly.",
        )
        assert classify_finding_domain(rec) == FINDING_DOMAIN_UNKNOWN

    def test_classify_finding_domain_test_strategy_source(self) -> None:
        rec = Recommendation(
            id="test-strategy",
            source="test-strategy",
            severity="medium",
            step_id=2,
            title="Classification mismatch",
            body="Step 2 should declare a change_type.",
        )
        assert classify_finding_domain(rec) == FINDING_DOMAIN_UNIT_TEST

    @pytest.mark.parametrize(
        "rec",
        [
            merge_bridge_reauthor_context_fixture(),
            docs_detail_body_fixture(),
            Recommendation(
                id="test-path",
                source="plan-completeness",
                severity="medium",
                step_id=1,
                title="t",
                body="See `tests/test_foo.py`.",
            ),
            Recommendation(
                id="docs-path",
                source="plan-completeness",
                severity="medium",
                step_id=1,
                title="t",
                body="See `docs/how-to/pipeline/audit.md`.",
            ),
            Recommendation(
                id="code-path",
                source="plan-completeness",
                severity="medium",
                step_id=1,
                title="t",
                body="See `plan_tool/convergence.py`.",
            ),
            Recommendation(
                id="unknown",
                source="plan-completeness",
                severity="medium",
                step_id=None,
                title="Clarify goals",
                body="State success criteria more clearly.",
            ),
            Recommendation(
                id="test-strategy",
                source="test-strategy",
                severity="medium",
                step_id=2,
                title="t",
                body="Declare change_type.",
            ),
        ],
    )
    def test_classify_finding_domain_returns_only_closed_vocab(
        self, rec: Recommendation
    ) -> None:
        assert classify_finding_domain(rec) in FINDING_DOMAINS


def _bare_mechanism_recommendation(**overrides: object) -> Recommendation:
    fields: dict[str, object] = {
        "id": "mechanism",
        "source": "plan-correctness",
        "severity": "medium",
        "step_id": None,
        "title": "Select a serializer choice",
        "body": "Use a serializer choice for the internal payload.",
        "suggested_action": "Specify the serializer choice in detail.",
    }
    fields.update(overrides)
    return Recommendation(**fields)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("title", "body", "suggested_action"),
    (
        ("Use a carrier", "Keep the internal payload local.", None),
        ("Carrier selection", "Use a carrier for the internal payload.", None),
        ("Carrier selection", "Keep the internal payload local.", "Use a carrier."),
    ),
)
def test_classify_likely_bare_mechanism_labels_internal_delivery_choice(
    title: str,
    body: str,
    suggested_action: str | None,
) -> None:
    assert classify_likely_bare_mechanism(
        _bare_mechanism_recommendation(
            title=title,
            body=body,
            suggested_action=suggested_action,
        )
    )


@pytest.mark.parametrize(
    "rec",
    [
        _bare_mechanism_recommendation(
            body="The named property must hold; choose a serializer choice later."
        ),
        _bare_mechanism_recommendation(
            body="The split route lacks coverage; choose a serializer choice later."
        ),
    ],
)
def test_classify_likely_bare_mechanism_rejects_named_property_or_route_coverage(
    rec: Recommendation,
) -> None:
    assert not classify_likely_bare_mechanism(rec)


@pytest.mark.parametrize("protected_phrase", _BARE_MECHANISM_PROTECTED_PHRASES)
def test_classify_likely_bare_mechanism_rejects_every_protected_phrase(
    protected_phrase: str,
) -> None:
    rec = _bare_mechanism_recommendation(
        body=(
            "Use a serializer choice for the internal payload while preserving the "
            f"plan's {protected_phrase}."
        )
    )

    assert not classify_likely_bare_mechanism(rec)


def test_classify_likely_bare_mechanism_does_not_treat_router_as_route() -> None:
    rec = _bare_mechanism_recommendation(
        body="Use a serializer for the internal payload; wire it into the router module."
    )

    assert classify_likely_bare_mechanism(rec)


@pytest.mark.parametrize(
    "contract",
    ("compatibility", "safety", "ordering", "ownership", "bypass"),
)
def test_classify_likely_bare_mechanism_rejects_explicit_observable_contract(
    contract: str,
) -> None:
    rec = _bare_mechanism_recommendation(
        body=(
            "Select a serializer choice to satisfy the observable "
            f"{contract} contract."
        )
    )
    assert not classify_likely_bare_mechanism(rec)


def test_classify_likely_bare_mechanism_rejects_observable_contract_boundary() -> None:
    rec = _bare_mechanism_recommendation(
        body="Use a serializer choice to preserve the observable compatibility boundary."
    )

    assert not classify_likely_bare_mechanism(rec)


@pytest.mark.parametrize(
    "body",
    (
        "Could a serializer be appropriate here?",
        "The plan may need different wiring.",
    ),
)
def test_classify_likely_bare_mechanism_leaves_ambiguous_text_unlabelled(
    body: str,
) -> None:
    assert not classify_likely_bare_mechanism(
        _bare_mechanism_recommendation(
            title="Unclear detail", body=body, suggested_action=None
        )
    )


def test_classify_likely_bare_mechanism_is_repeatable_for_identical_persisted_text() -> None:
    rec = _bare_mechanism_recommendation()
    assert [classify_likely_bare_mechanism(rec) for _ in range(3)] == [True] * 3


def test_classify_likely_bare_mechanism_ignores_nontext_recommendation_metadata() -> None:
    baseline = _bare_mechanism_recommendation()
    metadata_variant = dataclasses.replace(
        baseline,
        id="other-id",
        source="claude",
        severity="critical",
        step_id=9,
        anchor="other-anchor",
        file_path="docs/other.md",
    )
    assert classify_likely_bare_mechanism(metadata_variant) is True
    assert classify_likely_bare_mechanism(metadata_variant) == classify_likely_bare_mechanism(
        baseline
    )


def test_audit_plan_uses_the_supplied_grade_aware_capture(tmp_path: Path) -> None:
    """Later plan/detail edits cannot change prompts built from one capture."""
    from plan_tool.parser import parse_plan
    from plan_tool.review import audit_plan_until_stable
    from plan_tool.review_persistence import AuditInputSnapshot

    plan_path = tmp_path / "plans" / "1-demo.md"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text(
        "---\n"
        "title: Demo\nstatus: planning\npriority: medium\nsteps:\n"
        "  - id: 1\n    title: First\n    detail: details/01-first.md\n"
        "---\n\n# Plan\n\nCaptured plan body.\n",
        encoding="utf-8",
    )
    detail = tmp_path / "details" / "01-first.md"
    detail.parent.mkdir()
    detail.write_text("# First\n\nCaptured detail.\n", encoding="utf-8")
    snapshot = AuditInputSnapshot.capture(plan_path, tmp_path)
    plan_path.write_text(
        plan_path.read_text(encoding="utf-8").replace(
            "Captured plan body.", "Changed plan body."
        ),
        encoding="utf-8",
    )
    detail.write_text("# First\n\nChanged detail.\n", encoding="utf-8")
    prompts: list[str] = []

    def invoker(prompt: str) -> tuple[int, str]:
        prompts.append(prompt)
        return 0, "## Correctness findings\n\n_(none)_\n\n## Completeness findings\n\n_(none)_\n"

    audit_plan_until_stable(
        parse_plan(plan_path),
        plan_path,
        repo_root=tmp_path,
        invoker=invoker,
        max_passes=1,
        audit_input_snapshot=snapshot,
    )

    assert len(prompts) == 1
    assert "Captured plan body." in prompts[0]
    assert "Captured detail." in prompts[0]
    assert "Changed plan body." not in prompts[0]
    assert "Changed detail." not in prompts[0]


def test_body_completeness_uses_real_heading_after_fenced_pseudo_heading(
    tmp_path: Path,
) -> None:
    body = _FULL_BODY_SECTIONS.replace(
        "## Risks\n\nReal risk discussion.\n\n",
        "```markdown\n## Risks\n\nExample-only risk discussion.\n```\n\n",
    )
    plan_path = _write_completeness_plan(tmp_path, body=body)

    issues = check_body_completeness(plan_path)

    assert ("missing", "Risks") in {(issue.kind, issue.section) for issue in issues}


def test_review_claim_matching_ignores_fenced_claims_and_suppression_text(
    tmp_path: Path,
) -> None:
    detail = (
        "## Summary\n\nDescribe the renderer.\n\n"
        "## Why\n\n```markdown\n"
        "Suppress the audit gate with `fenced_symbol`.\n"
        "Edits `pkg/fenced_example.py`.\n```\n"
        "\n```markdown\n## Acceptance criteria\n\n"
        "The `pkg/fenced_detail_claim.py` uses `fenced_detail_claim`.\n```\n"
    )
    plan, plan_path = _write_orphan_plan(
        tmp_path,
        [{"id": 1, "title": "Describe renderer", "detail_body": detail}],
        plan_body=(
            "\n## Acceptance criteria\n\n```markdown\n"
            "The `pkg/fenced_claim.py` uses `fenced_claim`.\n```\n"
        ),
    )

    footprint = build_plan_footprint(plan, tmp_path, plan_path=plan_path)

    assert "pkg/fenced_detail_claim.py" not in footprint.claim_paths
    assert "fenced_detail_claim" not in footprint.claim_symbols
    assert "pkg/fenced_claim.py" not in footprint.claim_paths
    assert "fenced_claim" not in footprint.claim_symbols
    assert detect_claim_vs_delivery(
        plan, tmp_path, plan_name="p", plan_path=plan_path
    ) == []
    assert detect_suppression_shape(
        plan, tmp_path, plan_name="p", plan_path=plan_path
    ) == []


def test_review_prompt_section_reads_preserve_fenced_examples(tmp_path: Path) -> None:
    from plan_tool.review import _extract_acceptance_criteria

    plan_path = _write_completeness_plan(
        tmp_path,
        body=(
            "## Acceptance criteria\n\n"
            "```markdown\n## Example heading\n- Preserve this example.\n```\n\n"
            "The real criterion remains.\n"
        ),
    )
    seed = (
        "## Outcome\n\n"
        "```markdown\n## In scope\nExample-only scope.\n```\n\n"
        "Ship the real change.\n\n## In scope\n\nKeep the source example.\n"
    )

    acceptance = _extract_acceptance_criteria(plan_path)
    contract = _extract_seed_scope_contract(seed)

    assert acceptance is not None
    assert "## Example heading" in acceptance
    assert "The real criterion remains." in acceptance
    assert contract is not None
    assert "Example-only scope." in contract
    assert "Keep the source example." in contract


def test_fence_safe_read_hides_later_pseudo_heading_after_unmatched_opener(
    tmp_path: Path,
) -> None:
    plan_path = _write_completeness_plan(
        tmp_path,
        body=(
            "## Overview\n\nReal overview.\n\n```markdown\n"
            "## Acceptance criteria\n\nThis is code through EOF.\n"
        ),
    )

    issues = check_body_completeness(plan_path)

    assert ("missing", "Acceptance criteria") in {
        (issue.kind, issue.section) for issue in issues
    }


def test_decision_record_bucket_lookup_ignores_fenced_pseudo_heading(
    tmp_path: Path,
) -> None:
    from plan_tool.review import check_concept_coverage

    plan, path, _ = _write_flat_decision_fixture(
        tmp_path, bucket="fenced bucket", body_sections=("Overview",)
    )
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "## Overview\n\nSection prose.\n",
            "## Overview\n\n```markdown\n## Fenced bucket\n````\n",
        ),
        encoding="utf-8",
    )

    recs = check_concept_coverage(plan, path, plan_name="p")

    assert [rec.source for rec in recs] == [CONCEPT_BUCKET_MISSING_SOURCE]


class TestEligibleSiblingCreates:
    def plan(self, root, name, *, source=None, creates="new.py", files="edit.py"):
        path = root / f"{name}.md"
        path.write_text(
            "---\ntitle: Example\nstatus: planning\npriority: medium\n"
            + (f"source_seed: {source}\n" if source else "")
            + "steps:\n  - id: 1\n    title: Build\n    status: pending\n"
            + f"    creates: [{creates}]\n    files: [{files}]\n---\n"
        )
        return path, parse_plan(path)

    def manifest(self, root, paths):
        (root / ".plan-tool").mkdir(exist_ok=True)
        (root / ".plan-tool/plans.json").write_text(json.dumps({"plans": paths}))

    def test_eligible_creates_preserve_own_plan_without_manifest(self, tmp_path):
        from plan_tool.review import _eligible_planned_paths
        path, plan = self.plan(tmp_path, "own")
        assert _eligible_planned_paths(plan, path, tmp_path) == frozenset({"new.py"})

    def test_only_registered_explicit_contained_creates_contribute(self, tmp_path):
        from plan_tool.review import _eligible_planned_paths
        path, plan = self.plan(tmp_path, "own")
        self.plan(tmp_path, "sibling", creates="sibling.py, ../escape.py")
        self.plan(tmp_path, "unregistered", creates="unregistered.py")
        (tmp_path / "bad.md").write_text("malformed")
        self.manifest(tmp_path, ["own.md", "sibling.md", "sibling.md", "bad.md", "missing.md"])
        assert _eligible_planned_paths(plan, path, tmp_path) == frozenset({"new.py", "sibling.py"})

    @pytest.mark.parametrize("manifest", ['{', '{"plans": 1}'])
    def test_invalid_manifest_preserves_own_creates_without_broadening(self, tmp_path, manifest):
        from plan_tool.review import _eligible_planned_paths
        path, plan = self.plan(tmp_path, "own")
        self.manifest(tmp_path, [])
        (tmp_path / ".plan-tool/plans.json").write_text(manifest)
        assert _eligible_planned_paths(plan, path, tmp_path) == frozenset({"new.py"})

    @pytest.mark.parametrize("seed", [None, "---\nroadmap: demo\n---\n", "---\nroadmap: demo\nplan_id: p1\n---\n"])
    def test_unknown_roadmap_identity_does_not_enable_repository_wide_selection(self, tmp_path, seed):
        from plan_tool.review import _eligible_planned_paths
        path, plan = self.plan(tmp_path, "own", source="seed.md")
        if seed is not None:
            (tmp_path / "seed.md").write_text(seed)
        self.plan(tmp_path, "sibling", creates="sibling.py")
        self.manifest(tmp_path, ["sibling.md"])
        assert _eligible_planned_paths(plan, path, tmp_path) == frozenset({"new.py"})

    def test_archived_plain_metadata_requires_accepted_membership_and_same_owner(self, tmp_path):
        from plan_tool.review import _eligible_planned_paths
        self.accepted_roadmap(tmp_path, "demo", ["p1", "p2"])
        (tmp_path / "archive").mkdir()
        for name, row in [("own", "p1"), ("sibling", "p2"), ("absent", "p3")]:
            (tmp_path / "archive" / f"{name}.replaced.md").write_text(
                "> **Replaced**: superseded\n> Preserved here for history; do not edit.\n\n"
                f"---\nroadmap: demo\nplan_id: {row}\n---\n"
            )
        path, plan = self.plan(tmp_path, "own", source="own-seed.md")
        (tmp_path / "archive/own.replaced.md").rename(tmp_path / "archive/own-seed.replaced.md")
        self.plan(tmp_path, "sibling", source="sibling.seed", creates="sibling.py")
        (tmp_path / "archive/sibling.replaced.md").rename(tmp_path / "archive/sibling.replaced.seed")
        self.plan(tmp_path, "absent", source="absent.seed", creates="absent.py")
        (tmp_path / "archive/absent.replaced.md").rename(tmp_path / "archive/absent.replaced.seed")
        self.plan(tmp_path, "ordinary", creates="ordinary.py")
        self.manifest(tmp_path, ["sibling.md", "absent.md", "ordinary.md"])
        before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
        assert _eligible_planned_paths(plan, path, tmp_path) == frozenset({"new.py", "sibling.py"})
        assert before == {p: p.read_bytes() for p in before}

    @pytest.mark.parametrize("escape", ["plan", "seed", "creates", "state"])
    def test_sibling_selection_rejects_repository_escapes(self, tmp_path, escape):
        from plan_tool.review import _eligible_planned_paths
        root = tmp_path / "repo"
        root.mkdir()
        outside, _ = self.plan(tmp_path, "outside", creates="outside.py")
        path, plan = self.plan(root, "own")
        if escape == "plan":
            (root / "linked.md").symlink_to(outside)
            registrations = ["../outside.md", "linked.md"]
        elif escape == "creates":
            (root / "linked").symlink_to(tmp_path, target_is_directory=True)
            self.plan(root, "sibling", creates="linked/escape.py, ../escape.py")
            registrations = ["sibling.md"]
        else:
            plan.source_seed = "seed.md"
            if escape == "seed":
                (root / "seed.md").symlink_to(outside)
            else:
                (root / "seed.md").write_text(
                    '<!-- plan-tool-roadmap-seed-state: {"plan_id":"p1",'
                    '"roadmap_slug":"demo","state":"../seed-state.json"} -->'
                )
            self.plan(root, "sibling", creates="sibling.py")
            registrations = ["sibling.md"]
        self.manifest(root, registrations)
        assert _eligible_planned_paths(plan, path, root) == frozenset({"new.py"})

    @pytest.mark.parametrize("metadata", [
        "---\nroadmap: [\n---\n",
        '<!-- plan-tool-roadmap-seed-state: {"plan_id":"p1","roadmap_slug":"demo","state":"missing.json"} -->',
        "---\nplan_id: p1\n---\n",
    ])
    def test_malformed_or_unavailable_identity_never_becomes_ordinary(self, tmp_path, metadata):
        from plan_tool.review import _eligible_planned_paths
        path, plan = self.plan(tmp_path, "own", source="seed.md")
        (tmp_path / "seed.md").write_text(metadata)
        self.plan(tmp_path, "sibling", creates="sibling.py")
        self.manifest(tmp_path, ["sibling.md"])
        assert _eligible_planned_paths(plan, path, tmp_path) == frozenset({"new.py"})

    @pytest.mark.parametrize("tracked", [False, True])
    @pytest.mark.parametrize("target", ["own", "sibling"])
    @pytest.mark.parametrize("invalid", [
        "---\nroadmap: null\nplan_id: null\n---\n",
        "---\nroadmap: null\n---\n",
        "---\nplan_id: null\n---\n",
        "---\nroadmap: demo\nplan_id: p1\n---\n"
        '<!-- plan-tool-roadmap-seed-state: broken -->',
    ])
    def test_present_invalid_identity_never_grants_sibling_exemptions(self, tmp_path, target, invalid, tracked):
        from plan_tool.review import _eligible_planned_paths
        self.accepted_roadmap(tmp_path, "demo", ["p1", "p2"])
        source_dir = tmp_path / "roadmaps/demo/seeds" if tracked else tmp_path
        source_dir.mkdir(exist_ok=True)
        if tracked:
            (tmp_path / "roadmaps/demo/seed-state.json").write_text(json.dumps({"version": 1, "seeds": {
                row: {"draft_seed_path": f"seeds/{name}-seed.md", "status": "current"}
                for name, row in [("own", "p1"), ("sibling", "p2")]
            }}))
        for name, row in [("own", "p1"), ("sibling", "p2")]:
            (source_dir / f"{name}-seed.md").write_text(
                invalid if name == target else f"---\nroadmap: demo\nplan_id: {row}\n---\n"
            )
        prefix = "roadmaps/demo/seeds/" if tracked else ""
        path, plan = self.plan(tmp_path, "own", source=f"{prefix}own-seed.md")
        self.plan(tmp_path, "sibling", source=f"{prefix}sibling-seed.md", creates="sibling.py")
        self.manifest(tmp_path, ["sibling.md"])
        assert _eligible_planned_paths(plan, path, tmp_path) == frozenset({"new.py"})

    @pytest.mark.parametrize("archived", [False, True])
    @pytest.mark.parametrize("state_present", [False, True])
    def test_structural_source_owner_wins_over_output_plan_directory(self, tmp_path, archived, state_present):
        from plan_tool.review import _eligible_planned_paths
        for folder in ("a", "b"):
            (tmp_path / folder).mkdir()
            self.accepted_roadmap(tmp_path / folder, "demo", ["p1", "p2"])
        owner = tmp_path / "a/roadmaps/demo"
        seeds = owner / "seeds"
        seeds.mkdir()
        if state_present:
            (owner / "seed-state.json").write_text(json.dumps({"version": 1, "seeds": {
                row: {"draft_seed_path": f"seeds/{row}.md", "status": "current"}
                for row in ("p1", "p2")
            }}))
        source_dir = seeds / "archive" if archived else seeds
        source_dir.mkdir(exist_ok=True)
        for row in ("p1", "p2"):
            name = f"{row}.replaced.md" if archived else f"{row}.md"
            (source_dir / name).write_text(f"---\nroadmap: demo\nplan_id: {row}\n---\n")
        suffix = "archive/p1.replaced.md" if archived else "p1.md"
        path, plan = self.plan(tmp_path / "b", "own", source=f"a/roadmaps/demo/seeds/{suffix}")
        suffix = "archive/p2.replaced.md" if archived else "p2.md"
        self.plan(tmp_path / "a", "same", source=f"a/roadmaps/demo/seeds/{suffix}", creates="same.py")
        (tmp_path / "other-seed.md").write_text("---\nroadmap: demo\nplan_id: p2\n---\n")
        self.plan(tmp_path / "b", "other", source="other-seed.md", creates="other.py")
        self.manifest(tmp_path, ["a/same.md", "b/other.md"])
        assert _eligible_planned_paths(plan, path, tmp_path) == frozenset({"new.py", "same.py"})

    def accepted_roadmap(self, plans_dir, slug, rows):
        import hashlib
        from plan_tool import roadmap_versions as versions
        artifact = ("---\nplans:\n" + "".join(
            f"- id: {row}\n  title: Build\n  disposition: keep\n"
            f"  draft_seed_path: seeds/{row}.md\n  sizing_rationale: Small\n"
            for row in rows
        ) + "---\n").encode()
        content = versions.RoadmapVersionContent(
            brief_bytes=b"Brief", artifact_bytes=(b"domain", b"constraints", b"components", artifact)
        )
        record = versions.create_root_version(
            roadmap_slug=slug,
            brief_digest=hashlib.sha256(content.brief_bytes).hexdigest(),
            artifact_digests=tuple(hashlib.sha256(data).hexdigest() for data in content.artifact_bytes),
        )
        prepared = versions.PreparedRoadmapVersion(record=record, content=content)
        directory = versions.version_directory_path(plans_dir, slug, record.version_id)
        directory.mkdir(parents=True)
        for member in versions.stored_version_members(prepared):
            (directory / member.member_name).write_bytes(member.data)
        versions.accepted_head_path(plans_dir, slug).write_bytes(versions.render_accepted_head(
            versions.AcceptedRoadmapHead(schema_version=versions.ROADMAP_VERSION_SCHEMA_VERSION,
                                         roadmap_slug=slug, version_id=record.version_id)
        ))

    def test_same_slug_separate_owners_and_unselected_rows_do_not_supply_promises(self, tmp_path):
        from plan_tool.review import _eligible_planned_paths
        for folder in ("plans", "other"):
            directory = tmp_path / folder
            directory.mkdir()
            self.accepted_roadmap(directory, "demo", ["p1", "p2"])
        paths = []
        for folder, name, row in [("plans", "own", "p1"), ("plans", "sibling", "p2"),
                                  ("plans", "absent", "p3"), ("other", "different", "p2")]:
            source = f"{name}-seed.md"
            (tmp_path / source).write_text(f"---\nroadmap: demo\nplan_id: {row}\n---\n")
            path, plan = self.plan(tmp_path / folder, name, source=source, creates=f"{name}.py")
            paths.append(path.relative_to(tmp_path).as_posix())
            if name == "own":
                own_path, own_plan = path, plan
        (tmp_path / "plans/roadmaps/demo/04-roadmap.md").write_text("unselected p3")
        self.manifest(tmp_path, paths)
        assert _eligible_planned_paths(own_plan, own_path, tmp_path) == frozenset({"own.py", "sibling.py"})

    @pytest.mark.parametrize("conflict", [False, True])
    def test_archived_lifecycle_identity_requires_consistent_frontmatter(self, tmp_path, conflict):
        from plan_tool.review import _eligible_planned_paths
        from plan_tool.roadmap_seed_state import render_seed_state_marker
        self.accepted_roadmap(tmp_path, "demo", ["p1", "p2"])
        state = tmp_path / "roadmaps/demo/seed-state.json"
        state.write_text(json.dumps({"version": 1, "seeds": {
            row: {"draft_seed_path": f"seeds/{row}.md", "status": "current"}
            for row in ("p1", "p2")
        }}))
        (tmp_path / "archive").mkdir()
        for name, row in [("own", "p1"), ("sibling", "p2")]:
            marker = render_seed_state_marker(plan_id=row, roadmap_slug="demo", state_path=state, repo_root=tmp_path)
            (tmp_path / "archive" / f"{name}-seed.replaced.md").write_text(
                f"---\nroadmap: demo\nplan_id: {'wrong' if conflict and name == 'sibling' else row}\n---\n{marker}\n"
            )
        path, plan = self.plan(tmp_path, "own", source="own-seed.md")
        self.plan(tmp_path, "sibling", source="sibling-seed.md", creates="sibling.py")
        self.manifest(tmp_path, ["sibling.md"])
        expected = {"new.py"} if conflict else {"new.py", "sibling.py"}
        assert _eligible_planned_paths(plan, path, tmp_path) == frozenset(expected)

    def test_unreadable_sibling_does_not_discard_valid_promises_or_use_own_disk_copy(self, tmp_path, monkeypatch):
        from plan_tool import review
        path, plan = self.plan(tmp_path, "own", creates="supplied.py")
        self.plan(tmp_path, "own", creates="disk.py")
        self.plan(tmp_path, "valid", creates="valid.py")
        self.plan(tmp_path, "unreadable", creates="unreadable.py")
        self.manifest(tmp_path, ["own.md", "unreadable.md", "valid.md"])
        original_parse = review.parse_plan

        def read_candidate(candidate):
            if candidate.name == "unreadable.md":
                raise PermissionError("unreadable sibling")
            return original_parse(candidate)

        monkeypatch.setattr(review, "parse_plan", read_candidate)
        assert review._eligible_planned_paths(plan, path, tmp_path) == frozenset({"supplied.py", "valid.py"})


def _sibling_input_fixture(tmp_path, anchor="pkg/future.py:Thing", *, own=False, eligible=True, edit_only=False):
    body = f"## Input\n\nUses `{anchor}`.\n"
    plan, path = _write_orphan_plan(
        tmp_path,
        [{"id": 1, "title": "Consume", "creates": ["pkg/future.py"] if own else [],
          "detail_body": body}],
        plan_body=body,
    )
    fixtures = TestEligibleSiblingCreates()
    fixtures.plan(tmp_path, "sibling", creates="" if edit_only else "pkg/future.py", files="pkg/future.py")
    if eligible:
        fixtures.manifest(tmp_path, ["sibling.md"])
    return plan, path


def _input_check(arm, plan, path, root):
    from plan_tool import review
    return getattr(review, f"check_{arm}_input_contract_references")(plan, path, root)


@pytest.mark.parametrize("arm", ["plan", "step"])
@pytest.mark.parametrize("declared", ["pkg/future.py", "./pkg/future.py"])
def test_both_input_checks_accept_eligible_sibling_creates(tmp_path, arm, declared):
    plan, path = _sibling_input_fixture(tmp_path)
    sibling = tmp_path / "sibling.md"
    sibling.write_text(sibling.read_text().replace("creates: [pkg/future.py]", f"creates: [{declared}]"))
    assert _input_check(arm, plan, path, tmp_path) == []


@pytest.mark.parametrize("arm", ["plan", "step"])
def test_both_input_checks_preserve_own_creates_without_siblings(tmp_path, arm):
    plan, path = _sibling_input_fixture(tmp_path, own=True, eligible=False)
    assert _input_check(arm, plan, path, tmp_path) == []


@pytest.mark.parametrize("arm", ["plan", "step"])
@pytest.mark.parametrize("case", ["typo", "edit-only", "ineligible"])
def test_both_input_checks_reject_paths_without_an_eligible_create(tmp_path, arm, case):
    anchor = "pkg/typo.py:Thing" if case == "typo" else "pkg/future.py:Thing"
    plan, path = _sibling_input_fixture(
        tmp_path, anchor, eligible=case != "ineligible", edit_only=case == "edit-only"
    )
    issues = _input_check(arm, plan, path, tmp_path)
    assert len(issues) == 1
    assert issues[0].code_anchor == anchor
    assert "does not exist" in issues[0].reason


@pytest.mark.parametrize("arm", ["plan", "step"])
def test_both_input_checks_validate_existing_symbols_despite_sibling_creates(tmp_path, arm):
    plan, path = _sibling_input_fixture(tmp_path)
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg/future.py").write_text("class Present:\n    pass\n")
    issues = _input_check(arm, plan, path, tmp_path)
    assert len(issues) == 1
    assert issues[0].code_anchor == "pkg/future.py:Thing"
    assert "does not resolve in HEAD" in issues[0].reason


def test_step_filter_limits_checked_bodies_not_creation_promises(tmp_path):
    from plan_tool.review import check_input_contract_references
    plan, path = _sibling_input_fixture(tmp_path)
    (tmp_path / "details/step-1.md").write_text("## Input\n\nUses `pkg/local.py:Local` and `pkg/future.py:Thing`.\n")
    path.write_text(path.read_text().replace("pkg/future.py:Thing", "pkg/typo.py:Missing"))
    plan.steps.append(plan.steps[0].model_copy(update={"id": 2, "creates": ["pkg/local.py"], "detail": "details/step-2.md"}))
    plan.steps[0].creates = []
    (tmp_path / "details/step-2.md").write_text("## Input\n\nUses `pkg/typo.py:Missing`.\n")
    assert check_input_contract_references(plan, path, tmp_path, step_filter=1) == []
    assert check_input_contract_references(plan, path, tmp_path)


def test_sibling_create_wiring_preserves_detail_resolution_and_done_exclusion(tmp_path):
    from plan_tool.review import check_step_input_contract_references
    from plan_tool.detail_artifacts import derive_detail_path
    plan, path = _sibling_input_fixture(tmp_path)
    canonical = derive_detail_path(path, plan, plan.steps[0])
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_text((tmp_path / "details/step-1.md").read_text())
    plan.steps[0].detail = None
    assert check_step_input_contract_references(plan, path, tmp_path) == []
    canonical.write_text("## Input\n\nUses `pkg/typo.py:Missing`.\n")
    assert len(check_step_input_contract_references(plan, path, tmp_path)) == 1
    plan.steps[0].status = StepStatus.DONE
    assert check_step_input_contract_references(plan, path, tmp_path) == []


def test_input_contract_dispatch_routes_share_sibling_eligibility(tmp_path):
    from plan_tool.review import DetectorContext, INPUT_CONTRACT_DETECTORS, check_input_contract_references
    plan, path = _sibling_input_fixture(tmp_path, "pkg/future.py:Thing` and `pkg/typo.py:Missing")
    results = INPUT_CONTRACT_DETECTORS.run_all(DetectorContext(plan, tmp_path, "p", path))
    dispatched = [issue for issues in results.values() for issue in issues]
    assert dispatched == check_input_contract_references(plan, path, tmp_path)
    assert [(i.path, i.step_id, i.location) for i in dispatched] == [
        (path.name, None, f"{path.name}:## Input"),
        ("details/step-1.md", 1, "details/step-1.md:## Input"),
    ]
    assert all(i.code_anchor == "pkg/typo.py:Missing" for i in dispatched)


def test_review_prompt_keeps_step_text_after_description_round_trip(tmp_path):
    from plan_tool.parser import parse_plan_text, render_plan_text
    from plan_tool.review import render_review_prompt

    plan = parse_plan_text("---\ntitle: Plan\nstatus: planning\npriority: medium\nsteps:\n- id: 1\n  title: Exact step text\n---\n")
    rewritten = parse_plan_text(render_plan_text(plan, ""))
    assert "Exact step text" in render_review_prompt(rewritten, tmp_path)


class TestFencedSpans:
    """Citation fences preserve review annotation boundaries."""

    def test_fenced_spans_returns_original_text_offsets_for_closed_fence(self) -> None:
        text = "before\n```\ncode\n```\nafter\n"
        spans = fenced_spans(text)
        assert spans == [(7, 20)]
        assert text[spans[0][0] : spans[0][1]] == "```\ncode\n```\n"

    def test_fenced_spans_unclosed_fence_spans_to_end_of_text(self) -> None:
        """An unclosed fence must span to EOF, not pair with an unrelated
        later fence elsewhere in the same text (the round-5 regression the
        old regex-based mechanism had: it paired an unclosed citation fence
        with a later, unrelated fence in the ### Fix suggestion)."""
        text = "before\n```\nnever closes\n"
        spans = fenced_spans(text)
        assert spans == [(7, len(text))]

    def test_tilde_fence_recognized(self) -> None:
        text = "before\n~~~\ncode\n~~~\nafter\n"
        assert fenced_spans(text) == [(7, 20)]

    def test_fenced_spans_requires_matching_delimiter_character_and_length(self) -> None:
        text = "before\n```\ncode\n~~~\nstill inside\n```\nafter\n"
        spans = fenced_spans(text)
        assert len(spans) == 1
        assert spans[0] == (7, len(text) - len("after\n"))

    def test_nested_shorter_run_does_not_close_a_longer_fence_early(self) -> None:
        """CommonMark's closing-length rule: a citation nesting a same-
        character run no longer than the opener's fence can't close it."""
        text = "before\n````\nouter\n```\ninner-fake-close\n````\nafter\n"
        spans = fenced_spans(text)
        assert len(spans) == 1
        assert text[spans[0][0] : spans[0][1]] == (
            "````\nouter\n```\ninner-fake-close\n````\n"
        )

    def test_fenced_spans_preserves_crlf_offsets(self) -> None:
        text = "before\r\n```\r\ncode\r\n```\r\nafter\r\n"
        spans = fenced_spans(text)
        assert len(spans) == 1
        assert text[spans[0][0] : spans[0][1]] == "```\r\ncode\r\n```\r\n"

    def test_fenced_spans_recognizes_fence_indented_beyond_three_spaces(self) -> None:
        """Deliberately more lenient than CommonMark's 3-space limit: this
        parses a model's own citation protocol, not rendered markdown, so a
        missed fence (false negative) is the unsafe direction."""
        text = "before\n      ```\n      code\n      ```\nafter\n"
        spans = fenced_spans(text)
        assert len(spans) == 1

    def test_no_fence_returns_empty(self) -> None:
        assert fenced_spans("just plain prose, no backticks at all\n") == []


class TestCitationInlineFenceContract:
    def test_fenced_spans_preserves_current_leading_inline_backtick_span_treatment(self) -> None:
        # Citation safety treats a leading triple-backtick inline span as an opener.
        text = "before\n```inline``` prose\n### Fix\nprotected\n"
        assert fenced_spans(text) == [(7, len(text))]


@pytest.fixture
def run_grade_audit_bundle(tmp_path):
    from plan_tool.detail_artifacts import derive_detail_path

    path = tmp_path / "1-demo.md"
    path.write_text(
        "---\ntitle: Demo\nstatus: planning\npriority: medium\nsteps:\n"
        "  - id: 1\n    title: First\n    detail: declared.md\n"
        "  - id: 2\n    title: Second\n---\n# Demo\n"
    )
    plan = parse_plan(path)
    pointer = tmp_path / "declared.md"
    canonical = derive_detail_path(path, plan, plan.steps[1])
    canonical.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text("## Summary\n\nDeclared detail evidence.\n")
    canonical.write_text("## Summary\n\nCanonical detail evidence.\n")
    return plan, path, pointer, canonical


def test_audit_detail_bundle_reads_declared_run_grade_detail(run_grade_audit_bundle):
    from plan_tool.review import _format_audit_detail_bundle

    plan, path, _pointer, _canonical = run_grade_audit_bundle
    bundle = _format_audit_detail_bundle(plan, path, path.parent, max_file_bytes=4096)
    assert "Declared detail evidence." in bundle
    assert "Canonical detail evidence." in bundle


def test_audit_detail_bundle_status_matches_run_grade_bundle_resolution(run_grade_audit_bundle):
    from plan_tool.review import _format_audit_detail_bundle, audit_detail_bundle_status
    from plan_tool.review_persistence import AuditInputSnapshot

    plan, path, pointer, canonical = run_grade_audit_bundle
    snapshot = AuditInputSnapshot.capture(path, path.parent)
    pointer.unlink()
    canonical.unlink()
    captured = audit_detail_bundle_status(plan, path, path.parent, audit_input_snapshot=snapshot)
    current = audit_detail_bundle_status(plan, path, path.parent)
    assert captured.detailed_step_ids == (1, 2)
    assert current.bare_step_ids == (1, 2)
    bundle = _format_audit_detail_bundle(
        plan, path, path.parent, max_file_bytes=4096, audit_input_snapshot=snapshot
    )
    assert "Declared detail evidence." in bundle and "Canonical detail evidence." in bundle


def test_plan_audit_prompt_uses_run_grade_bundle_framing(run_grade_audit_bundle):
    from plan_tool.review import render_plan_audit_prompt, _RUN_GRADE_BUNDLE_FRAMING

    plan, path, _pointer, _canonical = run_grade_audit_bundle
    prompt = render_plan_audit_prompt(plan, path, repo_root=path.parent)
    assert _RUN_GRADE_BUNDLE_FRAMING in prompt
    assert "jira-grade" not in prompt
    assert "Declared detail evidence." in prompt
