"""Tests for plan_tool.renderer."""

from __future__ import annotations

from pathlib import Path

import pytest

from plan_tool import parse_plan_text
from plan_tool.detail_artifacts import (
    derive_jira_detail_path,
    render_detail_format_version_marker,
)
from plan_tool.renderer import (
    DetailGradeError,
    load_jira_grade_step_detail,
    prompts_dir,
    render_prompt,
)


_PLAN_YAML = """---
title: Render Test
status: in-progress
priority: medium
lessons: plan-details/render-test/lessons.md
steps:
  - id: 1
    title: Step one
    status: done
  - id: 2
    title: Step two
    files: [a.py, b.py]
    complexity: medium
    depends_on: [1]
    detail: plan-details/render-test/02-step-two.md
    status: current
---

# Render Test
"""


def _plan():
    return parse_plan_text(_PLAN_YAML)


class TestCanonicalDetailFallback:
    """`_load_detail` resolves pointer first, canonical second."""

    _YAML = """---
title: Canon
status: in-progress
priority: medium
steps:
  - id: 1
    title: build it
    files: [foo.py]
    status: current
---

# Canon
"""

    def test_run_render_rejects_unmatched_plan_body_fence(self, tmp_path: Path) -> None:
        plan = _plan()
        plan_path = _plan_file(tmp_path)
        plan_path.write_text(
            plan_path.read_text(encoding="utf-8") + "\n```\n",
            encoding="utf-8",
        )

        with pytest.raises(DetailGradeError, match="unmatched opening code fence"):
            render_prompt(
                plan,
                plan.step_by_id(2),
                repo_root=tmp_path,
                mode="run",
                plan_path=plan_path,
            )

    @staticmethod
    def _setup(tmp_path: Path):
        plan_path = tmp_path / "2-canon.md"
        plan_path.write_text(TestCanonicalDetailFallback._YAML, encoding="utf-8")
        (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
        bundle = tmp_path / "plan-details" / "canon"
        bundle.mkdir(parents=True)
        (bundle / "01-build.md").write_text(
            "# Step 1\n\nCANONICAL-RUN-BODY\n", encoding="utf-8"
        )
        return plan_path, parse_plan_text(TestCanonicalDetailFallback._YAML)

    def test_executor_reads_canonical_body_when_pointer_unset(
        self, tmp_path: Path
    ) -> None:
        plan_path, plan = self._setup(tmp_path)
        step = plan.step_by_id(1)

        # Without plan_path there is no canonical resolution: prior behavior.
        bare = render_prompt(plan, step, repo_root=tmp_path, mode="run")
        assert "CANONICAL-RUN-BODY" not in bare
        assert "No detail file for this step" in bare

        prompt = render_prompt(
            plan, step, repo_root=tmp_path, mode="run", plan_path=plan_path
        )
        assert "CANONICAL-RUN-BODY" in prompt
        assert "No detail file for this step" not in prompt

    def test_absent_canonical_file_still_reports_no_detail(
        self, tmp_path: Path
    ) -> None:
        plan_path = tmp_path / "2-canon.md"
        plan_path.write_text(self._YAML, encoding="utf-8")
        (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
        plan = parse_plan_text(self._YAML)

        prompt = render_prompt(
            plan, plan.step_by_id(1), repo_root=tmp_path, mode="run",
            plan_path=plan_path,
        )
        assert "No detail file for this step" in prompt

    def test_set_pointer_never_falls_back_to_canonical(
        self, tmp_path: Path
    ) -> None:
        """A set-but-missing pointer keeps its own diagnostic; the canonical
        file beside it must not be substituted (that would erase
        ``check_detail_coverage``'s missing_on_disk signal)."""
        yaml = self._YAML.replace(
            "    status: current",
            "    detail: plan-details/canon/nope.md\n    status: current",
        )
        plan_path = tmp_path / "2-canon.md"
        plan_path.write_text(yaml, encoding="utf-8")
        (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
        bundle = tmp_path / "plan-details" / "canon"
        bundle.mkdir(parents=True)
        (bundle / "01-build.md").write_text("CANONICAL-RUN-BODY\n", encoding="utf-8")
        plan = parse_plan_text(yaml)

        prompt = render_prompt(
            plan, plan.step_by_id(1), repo_root=tmp_path, mode="run",
            plan_path=plan_path,
        )
        assert "CANONICAL-RUN-BODY" not in prompt
        assert "but not found on disk" in prompt

    def test_run_render_refuses_an_unsupported_detail_marker(
        self, tmp_path: Path
    ) -> None:
        plan_path, plan = self._setup(tmp_path)
        detail_path = tmp_path / "plan-details" / "canon" / "01-build.md"
        detail_path.write_text(
            f"# Step 1\n{render_detail_format_version_marker(999)}\n\n"
            "CANONICAL-RUN-BODY\n",
            encoding="utf-8",
        )

        with pytest.raises(DetailGradeError, match=r"step 1.*999"):
            render_prompt(
                plan, plan.step_by_id(1), repo_root=tmp_path, mode="run",
                plan_path=plan_path,
            )

    def test_run_render_with_no_marker_reads_the_body_unchanged(
        self, tmp_path: Path
    ) -> None:
        plan_path, plan = self._setup(tmp_path)
        prompt = render_prompt(
            plan, plan.step_by_id(1), repo_root=tmp_path, mode="run",
            plan_path=plan_path,
        )
        assert "CANONICAL-RUN-BODY" in prompt


class TestRenderRunPrompt:
    def test_substitutes_plan_and_step_fields(self, tmp_path: Path) -> None:
        plan = _plan()
        step = plan.step_by_id(2)
        prompt = render_prompt(plan, step, repo_root=tmp_path, mode="run")

        assert "Render Test" in prompt
        assert "Step two" in prompt
        assert "step 2 of 2" in prompt
        assert "1 previously done" in prompt
        assert "medium" in prompt  # priority or complexity

    def test_renders_files_as_bullets(self, tmp_path: Path) -> None:
        plan = _plan()
        step = plan.step_by_id(2)
        prompt = render_prompt(plan, step, repo_root=tmp_path, mode="run")
        assert "- `a.py`" in prompt
        assert "- `b.py`" in prompt

    def test_no_files_fallback(self, tmp_path: Path) -> None:
        plan = _plan()
        step = plan.step_by_id(1)  # has no files declared
        prompt = render_prompt(plan, step, repo_root=tmp_path, mode="run")
        assert "no files declared" in prompt

    def test_loads_detail_file_when_present(self, tmp_path: Path) -> None:
        plan = _plan()
        step = plan.step_by_id(2)

        detail_path = tmp_path / "plan-details" / "render-test" / "02-step-two.md"
        detail_path.parent.mkdir(parents=True)
        detail_path.write_text("UNIQUE_DETAIL_MARKER_XYZ", encoding="utf-8")

        prompt = render_prompt(plan, step, repo_root=tmp_path, mode="run")
        assert "UNIQUE_DETAIL_MARKER_XYZ" in prompt

    def test_missing_detail_file_shows_note(self, tmp_path: Path) -> None:
        plan = _plan()
        step = plan.step_by_id(2)  # detail declared but not on disk
        prompt = render_prompt(plan, step, repo_root=tmp_path, mode="run")
        assert "not found on disk" in prompt

    def test_no_detail_declared_shows_note(self, tmp_path: Path) -> None:
        plan = _plan()
        step = plan.step_by_id(1)  # no detail field at all
        prompt = render_prompt(plan, step, repo_root=tmp_path, mode="run")
        assert "No detail file" in prompt

    def test_lessons_section_included_when_present(self, tmp_path: Path) -> None:
        plan = _plan()
        step = plan.step_by_id(2)

        lessons_path = tmp_path / "plan-details" / "render-test" / "lessons.md"
        lessons_path.parent.mkdir(parents=True)
        lessons_path.write_text("Lesson: always test things.", encoding="utf-8")

        prompt = render_prompt(plan, step, repo_root=tmp_path, mode="run")
        assert "Lesson: always test things" in prompt
        assert "Lessons from earlier steps" in prompt

    def test_lessons_section_omitted_when_no_file(self, tmp_path: Path) -> None:
        plan = _plan()
        step = plan.step_by_id(2)
        prompt = render_prompt(plan, step, repo_root=tmp_path, mode="run")
        assert "Lessons from earlier steps" not in prompt

    def test_unknown_mode_raises(self, tmp_path: Path) -> None:
        plan = _plan()
        step = plan.step_by_id(2)
        with pytest.raises(FileNotFoundError):
            render_prompt(plan, step, repo_root=tmp_path, mode="does-not-exist")


# A conforming jira-grade artifact: the five required H2s, nothing else.
_JIRA_BODY = """## Intent

Prove the renderer reads the compact artifact. UNIQUE_JIRA_MARKER_ABC

## Change

Add the grade parameter and the strict loader.

## Constraints

Never substitute the run-grade body.

## Done when

The rendered prompt carries this body.

## Out of scope

The reconcile lane.
"""

# A run-grade body parked at the jira-grade path — the mislabeling case.
_RUN_GRADE_BODY = """## Summary

Seven sections, not five.

## Why

Because this is the run-grade schema.

## Files (creates vs edits)

- `a.py`

## Implementation

Do the thing.

## Tests

Test the thing.

## Acceptance criteria

- It works.
"""


def _plan_file(tmp_path: Path) -> Path:
    """Write the test plan to disk so jira-grade paths can be derived."""
    plan_path = tmp_path / "docs" / "implementation-plans" / "1-render-test.md"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(_PLAN_YAML, encoding="utf-8")
    return plan_path


def _jira_artifact_path(plan_path: Path) -> Path:
    """Where step 2's jira-grade artifact is derived to."""
    return (
        plan_path.parent
        / "plan-details"
        / "render-test"
        / "jira"
        / "02-step-two.md"
    )


def _write_run_grade_detail(tmp_path: Path, body: str) -> None:
    """Write the run-grade file ``Step.detail`` points at."""
    detail_path = tmp_path / "plan-details" / "render-test" / "02-step-two.md"
    detail_path.parent.mkdir(parents=True, exist_ok=True)
    detail_path.write_text(body, encoding="utf-8")


class TestRenderJiraGradePrompt:
    def test_jira_grade_renders_jira_body(self, tmp_path: Path) -> None:
        plan = _plan()
        step = plan.step_by_id(2)
        plan_path = _plan_file(tmp_path)
        _write_run_grade_detail(tmp_path, "RUN_GRADE_MARKER_ZZZ")
        artifact = _jira_artifact_path(plan_path)
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(_JIRA_BODY, encoding="utf-8")

        prompt = render_prompt(
            plan, step, repo_root=tmp_path, mode="run",
            plan_path=plan_path, detail_grade="jira",
        )
        assert "UNIQUE_JIRA_MARKER_ABC" in prompt
        assert "RUN_GRADE_MARKER_ZZZ" not in prompt

    def test_jira_grade_uses_run_jira_template(self, tmp_path: Path) -> None:
        plan = _plan()
        step = plan.step_by_id(2)
        plan_path = _plan_file(tmp_path)
        artifact = _jira_artifact_path(plan_path)
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(_JIRA_BODY, encoding="utf-8")

        prompt = render_prompt(
            plan, step, repo_root=tmp_path, mode="run",
            plan_path=plan_path, detail_grade="jira",
        )
        # Framing unique to the jira-grade template.
        assert "compact contract with five sections" in prompt
        # Framing unique to prompts/run.md.
        assert "Choose intuitive, self-descriptive names" not in prompt
        assert "${" not in prompt

    def test_jira_grade_missing_artifact_raises(self, tmp_path: Path) -> None:
        plan = _plan()
        step = plan.step_by_id(2)
        plan_path = _plan_file(tmp_path)
        _write_run_grade_detail(tmp_path, "RUN_GRADE_MARKER_ZZZ")

        with pytest.raises(DetailGradeError) as excinfo:
            render_prompt(
                plan, step, repo_root=tmp_path, mode="run",
                plan_path=plan_path, detail_grade="jira",
            )
        message = str(excinfo.value)
        assert "02-step-two.md" in message  # names the derived path
        assert "## Intent" in message  # states the durable contract
        assert "RUN_GRADE_MARKER_ZZZ" not in message

    def test_jira_grade_wrong_schema_raises(self, tmp_path: Path) -> None:
        plan = _plan()
        step = plan.step_by_id(2)
        plan_path = _plan_file(tmp_path)
        artifact = _jira_artifact_path(plan_path)
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(_RUN_GRADE_BODY, encoding="utf-8")

        with pytest.raises(DetailGradeError) as excinfo:
            render_prompt(
                plan, step, repo_root=tmp_path, mode="run",
                plan_path=plan_path, detail_grade="jira",
            )
        assert "run-grade body at a jira-grade path" in str(excinfo.value)

    def test_jira_grade_collect_blocks_measures_jira_body(
        self, tmp_path: Path
    ) -> None:
        plan = _plan()
        step = plan.step_by_id(2)
        plan_path = _plan_file(tmp_path)
        _write_run_grade_detail(tmp_path, "a much longer run-grade body " * 20)
        artifact = _jira_artifact_path(plan_path)
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(_JIRA_BODY, encoding="utf-8")

        blocks: list[tuple[str, int]] = []
        render_prompt(
            plan, step, repo_root=tmp_path, mode="run",
            plan_path=plan_path, detail_grade="jira", collect_blocks=blocks,
        )
        assert ("step detail", len(_JIRA_BODY.encode("utf-8"))) in blocks

    def test_jira_grade_needs_plan_path(self, tmp_path: Path) -> None:
        plan = _plan()
        step = plan.step_by_id(2)
        with pytest.raises(DetailGradeError):
            render_prompt(
                plan, step, repo_root=tmp_path, mode="run", detail_grade="jira"
            )

    def test_unknown_grade_raises(self, tmp_path: Path) -> None:
        plan = _plan()
        step = plan.step_by_id(2)
        with pytest.raises(DetailGradeError):
            render_prompt(
                plan, step, repo_root=tmp_path, mode="run",
                plan_path=_plan_file(tmp_path), detail_grade="nonesuch",
            )

    def test_default_grade_render_unchanged(self, tmp_path: Path) -> None:
        plan = _plan()
        step = plan.step_by_id(2)
        plan_path = _plan_file(tmp_path)
        _write_run_grade_detail(tmp_path, "RUN_GRADE_MARKER_ZZZ")
        artifact = _jira_artifact_path(plan_path)
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(_JIRA_BODY, encoding="utf-8")

        implicit = render_prompt(plan, step, repo_root=tmp_path, mode="run")
        explicit = render_prompt(
            plan, step, repo_root=tmp_path, mode="run",
            plan_path=plan_path, detail_grade="run",
        )
        assert implicit == explicit
        assert "RUN_GRADE_MARKER_ZZZ" in implicit
        assert "UNIQUE_JIRA_MARKER_ABC" not in implicit

    def test_jira_grade_only_swaps_the_execution_template(
        self, tmp_path: Path
    ) -> None:
        # Grade selects the detail source at every mode; only ``run`` has a
        # grade-specific template, so a review mode keeps prompts/<mode>.md.
        plan = _plan()
        step = plan.step_by_id(2)
        plan_path = _plan_file(tmp_path)
        artifact = _jira_artifact_path(plan_path)
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(_JIRA_BODY, encoding="utf-8")

        prompt = render_prompt(
            plan, step, repo_root=tmp_path, mode="check",
            plan_path=plan_path, detail_grade="jira",
        )
        assert "compact contract with five sections" not in prompt

    def test_loader_reports_repo_relative_path(self, tmp_path: Path) -> None:
        plan = _plan()
        step = plan.step_by_id(2)
        plan_path = _plan_file(tmp_path)
        with pytest.raises(DetailGradeError) as excinfo:
            load_jira_grade_step_detail(
                plan, step, plan_path=plan_path, repo_root=tmp_path
            )
        assert (
            "docs/implementation-plans/plan-details/render-test/jira/"
            "02-step-two.md" in str(excinfo.value)
        )


_FENCED_PLAN_YAML = """---
title: Fenced Plan
intent: PLAN_INTENT_MARKER — ship the fence to the run lane
status: in-progress
priority: medium
steps:
  - id: 1
    title: Step one
    intent: STEP_ONE_INTENT_MARKER — wire the renderer variable
    files: [a.py]
    status: current
  - id: 2
    title: Step two
    intent: STEP_TWO_INTENT_MARKER — add the template slots
    files: [b.py]
    depends_on: [1]
---

# Fenced Plan

## Scope guardrails

GUARDRAIL_MARKER — no gate flips.

## Out of scope

OUT_OF_SCOPE_MARKER — the review and reconcile prompts.
"""

# Same shape, no intents and no fence sections: the unchanged-render control.
_FENCELESS_PLAN_YAML = """---
title: Fenceless Plan
status: in-progress
priority: medium
steps:
  - id: 1
    title: Step one
    files: [a.py]
    status: current
---

# Fenceless Plan

## Overview

Nothing here is fence content.
"""


def _write_plan(tmp_path: Path, yaml: str, name: str = "1-fenced.md") -> Path:
    path = tmp_path / "docs" / "implementation-plans" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml, encoding="utf-8")
    return path


class TestScopeFenceInRunPrompt:
    """Both fence halves reach ``run`` and ``run-jira`` through one variable."""

    @staticmethod
    def _fenced(tmp_path: Path):
        plan_path = _write_plan(tmp_path, _FENCED_PLAN_YAML)
        return plan_path, parse_plan_text(_FENCED_PLAN_YAML)

    @staticmethod
    def _write_jira_artifact(plan_path: Path, plan, step) -> None:
        path = derive_jira_detail_path(plan_path, plan, step)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_JIRA_BODY, encoding="utf-8")

    def test_fence_reaches_the_run_prompt(self, tmp_path: Path) -> None:
        plan_path, plan = self._fenced(tmp_path)
        prompt = render_prompt(
            plan, plan.step_by_id(1), repo_root=tmp_path, mode="run",
            plan_path=plan_path,
        )
        assert "PLAN_INTENT_MARKER" in prompt
        assert "STEP_ONE_INTENT_MARKER" in prompt
        assert "GUARDRAIL_MARKER" in prompt
        assert "OUT_OF_SCOPE_MARKER" in prompt

    def test_fence_reaches_the_run_jira_prompt(self, tmp_path: Path) -> None:
        plan_path, plan = self._fenced(tmp_path)
        step = plan.step_by_id(1)
        self._write_jira_artifact(plan_path, plan, step)

        prompt = render_prompt(
            plan, step, repo_root=tmp_path, mode="run",
            plan_path=plan_path, detail_grade="jira",
        )
        assert "compact contract with five sections" in prompt  # the jira template
        assert "PLAN_INTENT_MARKER" in prompt
        assert "STEP_ONE_INTENT_MARKER" in prompt
        assert "OUT_OF_SCOPE_MARKER" in prompt

    def test_run_and_run_jira_carry_the_same_fence(self, tmp_path: Path) -> None:
        """One variable, built above the template choice — the two grades
        cannot drift into rendering different fences."""
        plan_path, plan = self._fenced(tmp_path)
        step = plan.step_by_id(1)
        self._write_jira_artifact(plan_path, plan, step)

        run_prompt = render_prompt(
            plan, step, repo_root=tmp_path, mode="run", plan_path=plan_path,
        )
        jira_prompt = render_prompt(
            plan, step, repo_root=tmp_path, mode="run",
            plan_path=plan_path, detail_grade="jira",
        )

        def fence_of(prompt: str) -> str:
            start = prompt.index("**Scope fence")
            return prompt[start:prompt.index("## What to do", start)]

        assert fence_of(run_prompt) == fence_of(jira_prompt)

    def test_plan_intent_reaches_the_run_prompt(self, tmp_path: Path) -> None:
        yaml = _FENCED_PLAN_YAML.replace(
            "    intent: STEP_ONE_INTENT_MARKER — wire the renderer variable\n", ""
        )
        plan_path = _write_plan(tmp_path, yaml)
        plan = parse_plan_text(yaml)
        prompt = render_prompt(
            plan, plan.step_by_id(1), repo_root=tmp_path, mode="run",
            plan_path=plan_path,
        )
        assert "PLAN_INTENT_MARKER" in prompt
        assert "STEP_ONE_INTENT_MARKER" not in prompt

    def test_step_intent_reaches_the_run_prompt(self, tmp_path: Path) -> None:
        yaml = _FENCED_PLAN_YAML.replace(
            "intent: PLAN_INTENT_MARKER — ship the fence to the run lane\n", ""
        )
        plan_path = _write_plan(tmp_path, yaml)
        plan = parse_plan_text(yaml)
        prompt = render_prompt(
            plan, plan.step_by_id(1), repo_root=tmp_path, mode="run",
            plan_path=plan_path,
        )
        assert "STEP_ONE_INTENT_MARKER" in prompt
        assert "PLAN_INTENT_MARKER" not in prompt

    def test_each_step_gets_its_own_intent(self, tmp_path: Path) -> None:
        plan_path, plan = self._fenced(tmp_path)
        first = render_prompt(
            plan, plan.step_by_id(1), repo_root=tmp_path, mode="run",
            plan_path=plan_path,
        )
        second = render_prompt(
            plan, plan.step_by_id(2), repo_root=tmp_path, mode="run",
            plan_path=plan_path,
        )
        assert "STEP_ONE_INTENT_MARKER" in first
        assert "STEP_TWO_INTENT_MARKER" not in first
        assert "STEP_TWO_INTENT_MARKER" in second
        assert "STEP_ONE_INTENT_MARKER" not in second

    def test_fenceless_plan_renders_no_fence_block(self, tmp_path: Path) -> None:
        plan_path = _write_plan(
            tmp_path, _FENCELESS_PLAN_YAML, name="1-fenceless.md"
        )
        plan = parse_plan_text(_FENCELESS_PLAN_YAML)
        prompt = render_prompt(
            plan, plan.step_by_id(1), repo_root=tmp_path, mode="run",
            plan_path=plan_path,
        )
        assert "**Scope fence" not in prompt
        assert "Plan intent" not in prompt
        assert "Step intent" not in prompt
        assert "## Scope guardrails" not in prompt

    def test_fenceless_prompt_keeps_one_blank_line_before_what_to_do(
        self, tmp_path: Path
    ) -> None:
        """The slot replaces an existing blank line, so a fence-free plan
        renders the run prompt byte for byte as it does without the slot."""
        plan_path = _write_plan(
            tmp_path, _FENCELESS_PLAN_YAML, name="1-fenceless.md"
        )
        plan = parse_plan_text(_FENCELESS_PLAN_YAML)
        prompt = render_prompt(
            plan, plan.step_by_id(1), repo_root=tmp_path, mode="run",
            plan_path=plan_path,
        )
        assert "- `a.py`\n\n## What to do" in prompt

    def test_no_plan_path_renders_an_empty_fence(self, tmp_path: Path) -> None:
        _, plan = self._fenced(tmp_path)
        prompt = render_prompt(
            plan, plan.step_by_id(1), repo_root=tmp_path, mode="run",
        )
        assert "**Scope fence" not in prompt
        assert "PLAN_INTENT_MARKER" not in prompt
        assert "${" not in prompt
        assert "- `a.py`\n\n## What to do" in prompt

    def test_fence_sits_between_the_files_list_and_the_instructions(
        self, tmp_path: Path
    ) -> None:
        plan_path, plan = self._fenced(tmp_path)
        prompt = render_prompt(
            plan, plan.step_by_id(1), repo_root=tmp_path, mode="run",
            plan_path=plan_path,
        )
        assert (
            prompt.index("## Files in scope")
            < prompt.index("**Scope fence")
            < prompt.index("## What to do")
        )

    def test_lead_in_names_the_plan_as_the_source(self, tmp_path: Path) -> None:
        """The only prose this lane mints for the fence, on the one surface
        that writes code — pinned so a reword is a visible diff."""
        plan_path, plan = self._fenced(tmp_path)
        prompt = render_prompt(
            plan, plan.step_by_id(1), repo_root=tmp_path, mode="run",
            plan_path=plan_path,
        )
        assert (
            "**Scope fence (authoritative, from the plan).** These sections "
            "state what the whole plan is for, what this step is for, and "
            "what the plan will not build. They bind this step. Do not widen "
            "past them."
        ) in prompt

    def test_fence_block_is_measured_in_collect_blocks(
        self, tmp_path: Path
    ) -> None:
        plan_path, plan = self._fenced(tmp_path)
        blocks: list[tuple[str, int]] = []
        prompt = render_prompt(
            plan, plan.step_by_id(1), repo_root=tmp_path, mode="run",
            plan_path=plan_path, collect_blocks=blocks,
        )
        entries = [b for b in blocks if b[0] == "scope fence"]
        assert len(entries) == 1
        start = prompt.index("\n**Scope fence")
        block = prompt[start:prompt.index("## What to do", start) - 1]
        assert entries[0][1] == len(block.encode("utf-8"))

    def test_empty_fence_still_reports_a_zero_byte_block(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_plan(
            tmp_path, _FENCELESS_PLAN_YAML, name="1-fenceless.md"
        )
        plan = parse_plan_text(_FENCELESS_PLAN_YAML)
        blocks: list[tuple[str, int]] = []
        render_prompt(
            plan, plan.step_by_id(1), repo_root=tmp_path, mode="run",
            plan_path=plan_path, collect_blocks=blocks,
        )
        assert ("scope fence", 0) in blocks

    def test_dollar_brace_in_the_fence_survives_verbatim(
        self, tmp_path: Path
    ) -> None:
        """``safe_substitute`` passes over the template once, so a ``${…}``
        inside the substituted fence is never treated as a placeholder."""
        yaml = _FENCED_PLAN_YAML.replace(
            "OUT_OF_SCOPE_MARKER — the review and reconcile prompts.",
            "Anything naming ${example} stays out.",
        )
        plan_path = _write_plan(tmp_path, yaml)
        plan = parse_plan_text(yaml)
        prompt = render_prompt(
            plan, plan.step_by_id(1), repo_root=tmp_path, mode="run",
            plan_path=plan_path,
        )
        assert "Anything naming ${example} stays out." in prompt

    def test_other_modes_render_no_fence_block(self, tmp_path: Path) -> None:
        """Only the two run templates carry the slot; the review-style
        templates are unchanged."""
        plan_path, plan = self._fenced(tmp_path)
        prompt = render_prompt(
            plan, plan.step_by_id(1), repo_root=tmp_path, mode="check",
            plan_path=plan_path,
        )
        assert "**Scope fence" not in prompt
        assert "## Scope guardrails" not in prompt
        assert "PLAN_INTENT_MARKER" not in prompt


class TestApplyFindingPromptOrdering:
    def test_volatile_inputs_are_last_for_prefix_caching(
        self, tmp_path: Path
    ) -> None:
        """apply-finding: the per-iteration-volatile inputs (plan content,
        step detail, finding bodies) must trail the stable instruction
        sections so the static prefix stays cache-reusable across the
        convergence loop's re-applies (#74 lever A1)."""
        plan = _plan()
        step = plan.step_by_id(2)
        prompt = render_prompt(
            plan, step, repo_root=tmp_path, mode="apply-finding",
            extra_vars={
                "plan_path": "p.md",
                "plan_content": "UNIQUE-PLAN-CONTENT-MARKER",
                "detail_path": "d.md",
                "step_detail": "UNIQUE-STEP-DETAIL-MARKER",
                "finding_body": "UNIQUE-FINDING-MARKER",
                "finding_fix_block": "",
                "operator_feedback_block": "",
                "carried_findings_block": "",
                "structural_verdict_option": "",
            },
        )
        stable_end = max(
            prompt.index("## What to do"),
            prompt.index("## Output contract"),
            prompt.index("## Writing style"),
        )
        assert prompt.index("UNIQUE-PLAN-CONTENT-MARKER") > stable_end
        assert prompt.index("UNIQUE-STEP-DETAIL-MARKER") > stable_end
        assert prompt.index("UNIQUE-FINDING-MARKER") > stable_end


class TestPromptsDirLocation:
    def test_run_template_exists(self) -> None:
        assert (prompts_dir() / "run.md").is_file()


_ALL_MODES = ("run", "check", "optimize", "document", "test", "security", "lint")


class TestAllModesShip:
    """Every mode declared in cli.AVAILABLE_MODES must have a template file that
    renders without raising."""

    @pytest.mark.parametrize("mode", _ALL_MODES)
    def test_template_exists(self, mode: str) -> None:
        assert (prompts_dir() / f"{mode}.md").is_file(), (
            f"missing prompt template for mode '{mode}'"
        )

    @pytest.mark.parametrize("mode", _ALL_MODES)
    def test_template_renders(self, mode: str, tmp_path: Path) -> None:
        plan = _plan()
        step = plan.step_by_id(2)
        prompt = render_prompt(plan, step, repo_root=tmp_path, mode=mode)
        # Core variables must have been substituted — no leftover ${placeholders}.
        assert "${" not in prompt, f"unsubstituted placeholder in mode '{mode}'"
        # Every rendered prompt should reference the plan and step.
        assert "Render Test" in prompt
        assert "Step two" in prompt


def test_run_prompt_keeps_step_text_after_description_round_trip(tmp_path):
    from plan_tool.parser import render_plan_text

    plan = parse_plan_text(render_plan_text(_plan(), ""))
    assert "Step two" in render_prompt(plan, plan.steps[1], repo_root=tmp_path)
