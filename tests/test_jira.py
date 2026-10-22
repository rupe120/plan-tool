"""Tests for plan_tool.jira — JIRA story export.

Never spawns a real ``claude`` subprocess. Each test that reaches
``export_jira`` injects a fake invoker.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Callable, Optional

import pytest

from plan_tool import style
from plan_tool.jira import (
    _DETAIL_STATE_MISSING,
    _DETAIL_STATE_PRESENT,
    _STORY_SOURCE_ABSENT,
    _ExistingExport,
    _FrozenTicket,
    _StoryRenderInput,
    JiraError,
    Story,
    CompanionCreatedTicketNotice,
    _EXPORT_STATE_CREATED,
    _EXPORT_STATE_DRAFT,
    _EXPORT_STATE_DROPPED,
    _LAYER_UNSPECIFIED,
    _VALID_LAYERS,
    _emit_story_warnings,
    _read_json_stories_for_lint,
    _read_markdown_stories_for_lint,
    _render_story_block,
    _render_story_json,
    _render_story_markdown,
    _resolve_export_state,
    _set_markdown_block_state,
    _story_to_json_dict,
    _normalize_story_references,
    build_story_id_re,
    capture_companion_export_input,
    is_frontend_impacting,
    layer_tag,
    compute_start_number,
    derive_default_handoff_output_path,
    derive_jira_output_path,
    export_jira,
    lint_acceptance_criteria,
    lint_layer_metadata,
    lint_story_size,
    parse_jira_response,
    partition_lint_findings,
    plan_tag_bracket,
    read_stories_for_lint,
    regenerate_companion_stories,
    render_companion_export_prompt,
    scan_existing_story_numbers,
    story_id_prefix,
)

from plan_tool.detail_artifacts import derive_detail_path, derive_jira_detail_path
from plan_tool.jira_config import Epic
from plan_tool.jira_handoff import (
    PROVENANCE_FORMAT_REVISION,
    CompanionProvenance,
    GeneratedSourcePairIdentity,
    read_markdown_provenance,
    write_markdown_provenance,
)
from plan_tool.parser import parse_plan
from plan_tool.schema import ChangeType, Step, StepScope
from plan_tool.progress import ProgressReporter, StepHandle


def _format_markdown(
    plan_title: str,
    stories: list[Story],
    *,
    epic: Epic,
    step_detail_map: Optional[dict[int, str]] = None,
    plan_tag: str = "",
) -> str:
    """Test-local stand-in for the retired public ``format_markdown``
    wrapper: exercises the same still-live ``_render_story_markdown`` /
    ``_StoryRenderInput`` boundary the companion pipeline also renders
    through, without a public library surface no production code calls."""
    return _render_story_markdown(
        _StoryRenderInput(
            plan_title=plan_title,
            epic=epic,
            new_stories=stories,
            detail_map=step_detail_map or {},
            plan_tag=plan_tag,
        )
    )


def _format_json(
    plan_title: str,
    stories: list[Story],
    *,
    epic: Epic,
    step_detail_map: Optional[dict[int, str]] = None,
    plan_tag: str = "",
) -> str:
    """Test-local stand-in for the retired public ``format_json`` wrapper
    — see :func:`_format_markdown`."""
    return _render_story_json(
        _StoryRenderInput(
            plan_title=plan_title,
            epic=epic,
            new_stories=stories,
            detail_map=step_detail_map or {},
            plan_tag=plan_tag,
        )
    )


_PLAN_TEMPLATE = """---
title: Demo Plan
status: in-progress
priority: medium
steps:
  - id: 1
    title: Build the parser
    files:
      - parser.py
    complexity: low
    status: current
  - id: 2
    title: Wire up the renderer
    files:
      - renderer.py
    depends_on: [1]
---

# Demo Plan
"""


# Every test runs against an explicit epic — the legacy bare ``S<N>``
# shape is no longer accepted, so fixtures default to ``AUTH`` unless a
# test overrides for a multi-epic scenario.
_DEFAULT_EPIC = Epic(key="AUTH", name="Auth")


def _write_plan(tmp_path: Path) -> Path:
    plan_path = tmp_path / "1-demo.md"
    plan_path.write_text(_PLAN_TEMPLATE, encoding="utf-8")
    (tmp_path / "parser.py").write_text(
        "class Parser:\n    pass\n", encoding="utf-8"
    )
    (tmp_path / "renderer.py").write_text(
        "def render(plan):\n    return None\n", encoding="utf-8"
    )
    return plan_path


def _consolidated_payload(prefix: str = "AUTH-") -> str:
    """One story covering both plan steps (consolidation)."""
    return json.dumps(
        [
            {
                "id": f"{prefix}S1",
                "title": "Wire parser through to renderer",
                "description": "Build parser and renderer together.",
                "acceptance_criteria": ["Parser importable", "Renderer returns text"],
                "files": ["parser.py", "renderer.py"],
                "steps": [1, 2],
                "depends_on": [],
                "estimate_hours": 4,
            }
        ]
    )


def _split_payload(prefix: str = "AUTH-") -> str:
    """Three stories: step 1 split into two, step 2 as one."""
    return json.dumps(
        [
            {
                "id": f"{prefix}S1",
                "title": "Stub the parser API",
                "description": "Add the function signature.",
                "acceptance_criteria": ["Importable"],
                "files": ["parser.py"],
                "steps": [1],
                "depends_on": [],
                "estimate_hours": 2,
            },
            {
                "id": f"{prefix}S2",
                "title": "Wire the parser impl",
                "description": "Fill in the body.",
                "acceptance_criteria": ["Returns 42"],
                "files": ["parser.py"],
                "steps": [1],
                "depends_on": [f"{prefix}S1"],
                "estimate_hours": 4,
            },
            {
                "id": f"{prefix}S3",
                "title": "Add the renderer",
                "description": "Hook up the renderer.",
                "acceptance_criteria": ["Renders correctly"],
                "files": ["renderer.py"],
                "steps": [2],
                "depends_on": [f"{prefix}S2"],
                "estimate_hours": 2,
            },
        ]
    )


def _one_story_per_step_payload(prefix: str = "AUTH-") -> str:
    """Two stories, one per step (no consolidation, no splitting)."""
    return json.dumps(
        [
            {
                "id": f"{prefix}S1",
                "title": "Build the parser",
                "description": "Implement parser.",
                "acceptance_criteria": ["Importable"],
                "files": ["parser.py"],
                "steps": [1],
                "depends_on": [],
                "estimate_hours": 3,
            },
            {
                "id": f"{prefix}S2",
                "title": "Wire the renderer",
                "description": "Implement renderer.",
                "acceptance_criteria": ["Renders"],
                "files": ["renderer.py"],
                "steps": [2],
                "depends_on": [f"{prefix}S1"],
                "estimate_hours": 3,
            },
        ]
    )


# --- parse_jira_response ---------------------------------------------------


class TestParseJiraResponse:
    def test_consolidated_story_accepted(self) -> None:
        stories = parse_jira_response(
            _consolidated_payload(), plan_step_ids=[1, 2], epic=_DEFAULT_EPIC
        )
        assert stories is not None
        assert len(stories) == 1
        s = stories[0]
        assert s.id == "AUTH-S1"
        assert s.steps == [1, 2]
        assert s.estimate_hours == 4

    def test_split_payload_accepted(self) -> None:
        stories = parse_jira_response(
            _split_payload(), plan_step_ids=[1, 2], epic=_DEFAULT_EPIC
        )
        assert stories is not None
        assert [s.id for s in stories] == ["AUTH-S1", "AUTH-S2", "AUTH-S3"]
        assert stories[0].steps == [1]
        assert stories[1].steps == [1]
        assert stories[2].steps == [2]

    def test_fenced_code_block_with_chatter(self) -> None:
        chatter = (
            "Sure, here's the JSON you asked for:\n\n"
            "```json\n" + _consolidated_payload() + "\n```\n\n"
            "Let me know if you'd like adjustments."
        )
        stories = parse_jira_response(
            chatter, plan_step_ids=[1, 2], epic=_DEFAULT_EPIC
        )
        assert stories is not None
        assert stories[0].id == "AUTH-S1"

    def test_empty_string_returns_none(self) -> None:
        assert (
            parse_jira_response("", plan_step_ids=[1], epic=_DEFAULT_EPIC)
            is None
        )
        assert (
            parse_jira_response(
                "   \n\n", plan_step_ids=[1], epic=_DEFAULT_EPIC
            )
            is None
        )

    def test_no_brackets_returns_none(self) -> None:
        assert (
            parse_jira_response(
                "Sorry, I can't help.",
                plan_step_ids=[1],
                epic=_DEFAULT_EPIC,
            )
            is None
        )

    def test_top_level_object_not_list_returns_none(self) -> None:
        assert (
            parse_jira_response(
                '{"id": "AUTH-S1"}', plan_step_ids=[1], epic=_DEFAULT_EPIC
            )
            is None
        )

    def test_empty_list_returns_none(self) -> None:
        assert (
            parse_jira_response("[]", plan_step_ids=[1], epic=_DEFAULT_EPIC)
            is None
        )

    def test_missing_id_field_returns_none(self) -> None:
        bad = json.dumps(
            [
                {
                    "title": "x",
                    "description": "y",
                    "steps": [1],
                    "estimate_hours": 1,
                }
            ]
        )
        assert (
            parse_jira_response(bad, plan_step_ids=[1], epic=_DEFAULT_EPIC)
            is None
        )

    def test_bad_id_shape_returns_none(self) -> None:
        bad = json.dumps(
            [
                {
                    "id": "story-1",  # not <EPIC>-S<N>
                    "title": "x",
                    "description": "y",
                    "steps": [1],
                    "estimate_hours": 1,
                }
            ]
        )
        assert (
            parse_jira_response(bad, plan_step_ids=[1], epic=_DEFAULT_EPIC)
            is None
        )

    def test_legacy_bare_id_rejected(self) -> None:
        """Bare ``S<N>`` (no epic prefix) is no longer valid — the tool
        always emits ``<EPIC>-S<N>`` so two plans can't collide."""
        bad = json.dumps(
            [
                {
                    "id": "S1",
                    "title": "x",
                    "description": "y",
                    "steps": [1, 2],
                    "estimate_hours": 1,
                }
            ]
        )
        assert (
            parse_jira_response(
                bad, plan_step_ids=[1, 2], epic=_DEFAULT_EPIC
            )
            is None
        )

    def test_duplicate_ids_returns_none(self) -> None:
        bad = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "x",
                    "description": "y",
                    "steps": [1],
                    "estimate_hours": 1,
                },
                {
                    "id": "AUTH-S1",
                    "title": "y",
                    "description": "z",
                    "steps": [2],
                    "estimate_hours": 1,
                },
            ]
        )
        assert (
            parse_jira_response(
                bad, plan_step_ids=[1, 2], epic=_DEFAULT_EPIC
            )
            is None
        )

    def test_duplicate_step_ids_within_one_story_return_none(self) -> None:
        bad = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "x",
                    "description": "y",
                    "steps": [1, 1],
                    "estimate_hours": 1,
                }
            ]
        )
        assert (
            parse_jira_response(bad, plan_step_ids=[1], epic=_DEFAULT_EPIC)
            is None
        )

    def test_bad_acceptance_criteria_type_returns_none(self) -> None:
        bad = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "x",
                    "description": "y",
                    "acceptance_criteria": "should be a list",
                    "files": [],
                    "steps": [1],
                    "depends_on": [],
                    "estimate_hours": 1,
                }
            ]
        )
        assert (
            parse_jira_response(bad, plan_step_ids=[1], epic=_DEFAULT_EPIC)
            is None
        )

    def test_float_estimate_hours_coerced_to_int(self) -> None:
        body = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "x",
                    "description": "y",
                    "acceptance_criteria": [],
                    "files": [],
                    "steps": [1],
                    "depends_on": [],
                    "estimate_hours": 3.0,
                }
            ]
        )
        stories = parse_jira_response(
            body, plan_step_ids=[1], epic=_DEFAULT_EPIC
        )
        assert stories is not None
        assert stories[0].estimate_hours == 3

    def test_bool_estimate_rejected(self) -> None:
        """``True`` is technically an int in Python — must be rejected explicitly."""
        body = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "x",
                    "description": "y",
                    "acceptance_criteria": [],
                    "files": [],
                    "steps": [1],
                    "depends_on": [],
                    "estimate_hours": True,
                }
            ]
        )
        assert (
            parse_jira_response(body, plan_step_ids=[1], epic=_DEFAULT_EPIC)
            is None
        )

    def test_omitted_optional_fields_default_to_empty(self) -> None:
        body = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "x",
                    "description": "y",
                    "steps": [1],
                    "estimate_hours": 1,
                }
            ]
        )
        stories = parse_jira_response(
            body, plan_step_ids=[1], epic=_DEFAULT_EPIC
        )
        assert stories is not None
        assert stories[0].acceptance_criteria == []
        assert stories[0].files == []
        assert stories[0].depends_on == []

    def test_missing_steps_field_rejected(self) -> None:
        bad = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "x",
                    "description": "y",
                    "estimate_hours": 1,
                }
            ]
        )
        assert (
            parse_jira_response(bad, plan_step_ids=[1], epic=_DEFAULT_EPIC)
            is None
        )

    def test_empty_steps_list_rejected(self) -> None:
        bad = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "x",
                    "description": "y",
                    "steps": [],
                    "estimate_hours": 1,
                }
            ]
        )
        assert (
            parse_jira_response(bad, plan_step_ids=[1], epic=_DEFAULT_EPIC)
            is None
        )

    def test_steps_referencing_unknown_id_rejected(self) -> None:
        bad = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "x",
                    "description": "y",
                    "steps": [1, 99],
                    "estimate_hours": 1,
                }
            ]
        )
        assert (
            parse_jira_response(
                bad, plan_step_ids=[1, 2], epic=_DEFAULT_EPIC
            )
            is None
        )

    def test_uncovered_step_rejected(self) -> None:
        """Plan has steps [1, 2] but the response only covers step 1."""
        body = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "x",
                    "description": "y",
                    "steps": [1],
                    "estimate_hours": 1,
                }
            ]
        )
        assert (
            parse_jira_response(
                body, plan_step_ids=[1, 2], epic=_DEFAULT_EPIC
            )
            is None
        )

    def test_min_number_enforced(self) -> None:
        """``min_number=10`` rejects responses that start at S1."""
        body = _consolidated_payload()
        assert (
            parse_jira_response(
                body,
                plan_step_ids=[1, 2],
                epic=_DEFAULT_EPIC,
                min_number=10,
            )
            is None
        )

    def test_min_number_accepts_at_or_above(self) -> None:
        body = json.dumps(
            [
                {
                    "id": "AUTH-S10",
                    "title": "x",
                    "description": "y",
                    "steps": [1, 2],
                    "estimate_hours": 2,
                }
            ]
        )
        stories = parse_jira_response(
            body,
            plan_step_ids=[1, 2],
            epic=_DEFAULT_EPIC,
            min_number=10,
        )
        assert stories is not None
        assert stories[0].id == "AUTH-S10"

    def test_parse_reads_new_fields(self) -> None:
        body = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "x",
                    "description": "y",
                    "steps": [1, 2],
                    "estimate_hours": 2,
                    "layer": "backend",
                    "ui_impact": "adds a spinner on save",
                    "frontend_test_recommendation": ["assert spinner renders"],
                }
            ]
        )
        stories = parse_jira_response(
            body, plan_step_ids=[1, 2], epic=_DEFAULT_EPIC
        )
        assert stories is not None
        s = stories[0]
        assert s.layer == "backend"
        assert s.ui_impact == "adds a spinner on save"
        assert s.frontend_test_recommendation == ["assert spinner renders"]

    def test_parse_defaults_missing_new_fields(self) -> None:
        body = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "x",
                    "description": "y",
                    "steps": [1, 2],
                    "estimate_hours": 2,
                }
            ]
        )
        stories = parse_jira_response(
            body, plan_step_ids=[1, 2], epic=_DEFAULT_EPIC
        )
        assert stories is not None
        s = stories[0]
        assert s.layer == _LAYER_UNSPECIFIED
        assert s.ui_impact == ""
        assert s.frontend_test_recommendation == []

    def test_parse_invalid_layer_defaults_not_rejected(self) -> None:
        body = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "x",
                    "description": "y",
                    "steps": [1, 2],
                    "estimate_hours": 2,
                    "layer": "middleware",
                }
            ]
        )
        stories = parse_jira_response(
            body, plan_step_ids=[1, 2], epic=_DEFAULT_EPIC
        )
        assert stories is not None
        assert stories[0].layer == _LAYER_UNSPECIFIED

    def test_parse_ui_impact_none_kept_distinct_from_empty(self) -> None:
        with_none = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "x",
                    "description": "y",
                    "steps": [1, 2],
                    "estimate_hours": 2,
                    "ui_impact": "none",
                }
            ]
        )
        stories = parse_jira_response(
            with_none, plan_step_ids=[1, 2], epic=_DEFAULT_EPIC
        )
        assert stories is not None
        assert stories[0].ui_impact == "none"
        without = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "x",
                    "description": "y",
                    "steps": [1, 2],
                    "estimate_hours": 2,
                }
            ]
        )
        stories = parse_jira_response(
            without, plan_step_ids=[1, 2], epic=_DEFAULT_EPIC
        )
        assert stories is not None
        assert stories[0].ui_impact == ""

    def test_parse_frontend_test_recommendation_list_filtered(self) -> None:
        body = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "x",
                    "description": "y",
                    "steps": [1, 2],
                    "estimate_hours": 2,
                    "frontend_test_recommendation": ["keep me", 7, None, "and me"],
                }
            ]
        )
        stories = parse_jira_response(
            body, plan_step_ids=[1, 2], epic=_DEFAULT_EPIC
        )
        assert stories is not None
        assert stories[0].frontend_test_recommendation == ["keep me", "and me"]
        bad_type = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "x",
                    "description": "y",
                    "steps": [1, 2],
                    "estimate_hours": 2,
                    "frontend_test_recommendation": "not a list",
                }
            ]
        )
        stories = parse_jira_response(
            bad_type, plan_step_ids=[1, 2], epic=_DEFAULT_EPIC
        )
        assert stories is not None
        assert stories[0].frontend_test_recommendation == []

    def test_parse_new_fields_survive_normalize(self) -> None:
        body = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "x",
                    "description": "y",
                    "steps": [1, 2],
                    "estimate_hours": 2,
                    "layer": "full_stack",
                    "ui_impact": "new page",
                    "frontend_test_recommendation": ["render check"],
                }
            ]
        )
        # parse_jira_response ends with a _normalize_story_references call.
        stories = parse_jira_response(
            body, plan_step_ids=[1, 2], epic=_DEFAULT_EPIC
        )
        assert stories is not None
        s = stories[0]
        assert s.layer == "full_stack"
        assert s.ui_impact == "new page"
        assert s.frontend_test_recommendation == ["render check"]

    def test_parse_legacy_payload_still_parses(self) -> None:
        stories = parse_jira_response(
            _consolidated_payload(), plan_step_ids=[1, 2], epic=_DEFAULT_EPIC
        )
        assert stories is not None
        assert len(stories) == 1
        assert stories[0].id == "AUTH-S1"
        assert stories[0].layer == _LAYER_UNSPECIFIED
        assert stories[0].ui_impact == ""
        assert stories[0].frontend_test_recommendation == []


# --- story markdown rendering ------------------------------------------------


class TestRenderStoryMarkdown:
    def test_consolidated_story_renders(self) -> None:
        stories = [
            Story(
                id="AUTH-S1",
                title="Wire parser through renderer",
                description="Class skeleton + tests.",
                acceptance_criteria=["Importable", "Tests pass"],
                files=["parser.py", "renderer.py"],
                steps=[1, 2],
                depends_on=[],
                estimate_hours=4,
            )
        ]
        out = _format_markdown(
            "Demo Plan",
            stories,
            epic=_DEFAULT_EPIC,
            step_detail_map={
                1: "plan-details/demo/01-parser.md",
                2: "plan-details/demo/02-renderer.md",
            },
        )
        assert "# JIRA stories — Demo Plan" in out
        assert "_Epic: **AUTH** (Auth)_" in out
        assert "1 story" in out
        assert "total estimate: 4h" in out
        assert "AUTH-S1 — Plan steps: 1, 2" in out
        assert "(estimate: 4h)" in out
        # Title carries the ``[<id>] `` prefix added by the renderer so
        # the rendered block matches the actual JIRA ticket title.
        assert "[AUTH-S1] Wire parser through renderer" in out
        assert "- Importable" in out
        assert "- Tests pass" in out
        assert "- `parser.py`" in out
        assert "- `renderer.py`" in out
        # Plan details section: one line per step with the detail path.
        assert "## Plan details" in out
        assert "- Step 1: `plan-details/demo/01-parser.md`" in out
        assert "- Step 2: `plan-details/demo/02-renderer.md`" in out

    def test_plan_tag_renders_between_id_and_layer_tag(self) -> None:
        stories = [
            Story(
                id="AUTH-S1",
                title="Wire parser through renderer",
                description="d",
                steps=[1],
                estimate_hours=4,
                layer="backend",
            )
        ]
        out = _format_markdown(
            "Demo Plan", stories, epic=_DEFAULT_EPIC, plan_tag="DCL"
        )
        assert (
            "[AUTH-S1] [DCL] [BE] Wire parser through renderer" in out
        )

    def test_blank_plan_tag_omits_bracket(self) -> None:
        stories = [
            Story(id="AUTH-S1", title="x", description="d", steps=[1])
        ]
        out = _format_markdown(
            "Demo Plan", stories, epic=_DEFAULT_EPIC, plan_tag=""
        )
        assert "[AUTH-S1] x" in out
        assert "[AUTH-S1] [" not in out

    def test_plan_details_falls_back_when_step_has_no_detail(self) -> None:
        stories = [
            Story(
                id="AUTH-S1",
                title="x",
                description="y",
                acceptance_criteria=[],
                files=[],
                steps=[1, 2],
                depends_on=[],
                estimate_hours=1,
            )
        ]
        out = _format_markdown(
            "p",
            stories,
            epic=_DEFAULT_EPIC,
            step_detail_map={1: "plan-details/p/01-foo.md"},
        )
        assert "- Step 1: `plan-details/p/01-foo.md`" in out
        assert "- Step 2 _(no detail file)_" in out

    def test_split_renders_all_substories(self) -> None:
        stories = [
            Story(
                id=f"AUTH-S{i}",
                title=f"sub {i}",
                description=f"body {i}",
                acceptance_criteria=[],
                files=[],
                steps=[1],
                depends_on=[],
                estimate_hours=2,
            )
            for i in range(1, 4)
        ]
        out = _format_markdown("Demo Plan", stories, epic=_DEFAULT_EPIC)
        assert "AUTH-S1 — Plan steps: 1" in out
        assert "AUTH-S2 — Plan steps: 1" in out
        assert "AUTH-S3 — Plan steps: 1" in out

    def test_empty_description_marker(self) -> None:
        stories = [
            Story(
                id="AUTH-S1",
                title="x",
                description="   ",
                acceptance_criteria=[],
                files=[],
                steps=[1],
                depends_on=[],
                estimate_hours=1,
            )
        ]
        out = _format_markdown("p", stories, epic=_DEFAULT_EPIC)
        assert "_(no description)_" in out

    def test_jira_epic_id_not_rendered(self) -> None:
        """The real JIRA epic id, when configured, must not bleed into
        the rendered output — only the local key + name are useful for
        readers."""
        stories = [
            Story(
                id="AUTH-S1",
                title="x",
                description="y",
                acceptance_criteria=[],
                files=[],
                steps=[1],
                depends_on=[],
                estimate_hours=1,
            )
        ]
        epic = Epic(key="AUTH", name="Auth", jira_epic_id="PROJ-9999")
        out = _format_markdown("p", stories, epic=epic)
        assert "PROJ-9999" not in out
        assert "→ JIRA" not in out
        assert "roll up" not in out

    @staticmethod
    def _render(story: Story) -> str:
        return _format_markdown("p", [story], epic=_DEFAULT_EPIC)

    def test_markdown_title_carries_layer_tag(self) -> None:
        assert "[AUTH-S1] [BE] t" in self._render(
            Story(id="AUTH-S1", title="t", description="d", layer="backend")
        )
        assert "[AUTH-S1] [FE+BE] t" in self._render(
            Story(id="AUTH-S1", title="t", description="d", layer="full_stack")
        )
        assert "[AUTH-S1] [FE] t" in self._render(
            Story(id="AUTH-S1", title="t", description="d", layer="frontend")
        )

    def test_markdown_unspecified_layer_renders_no_tag(self) -> None:
        out = self._render(
            Story(id="AUTH-S1", title="t", description="d")
        )
        # Single space, no bracket tag between prefix and title.
        assert "[AUTH-S1] t" in out
        assert "[AUTH-S1]  t" not in out
        assert "[unspecified]" not in out

    def test_markdown_renders_layer_section(self) -> None:
        out = self._render(
            Story(id="AUTH-S1", title="t", description="d", layer="backend")
        )
        assert "## Layer\nbackend" in out

    def test_markdown_ui_impact_section_placeholder_when_empty(self) -> None:
        out = self._render(
            Story(id="AUTH-S1", title="t", description="d", layer="backend")
        )
        assert "## UI impact\n_(none)_" in out

    def test_markdown_ui_impact_literal_none_distinct_from_empty(self) -> None:
        out = self._render(
            Story(
                id="AUTH-S1",
                title="t",
                description="d",
                layer="backend",
                ui_impact="none",
            )
        )
        assert "## UI impact\nnone" in out
        assert "## UI impact\n_(none)_" not in out

    def test_markdown_testing_recommendation_bullets_for_frontend_story(
        self,
    ) -> None:
        out = self._render(
            Story(
                id="AUTH-S1",
                title="t",
                description="d",
                layer="frontend",
                frontend_test_recommendation=["Click the button", "Check aria"],
            )
        )
        assert "## Testing recommendation" in out
        assert "- Click the button" in out
        assert "- Check aria" in out

    def test_markdown_testing_recommendation_absent_for_non_frontend_story(
        self,
    ) -> None:
        out = self._render(
            Story(id="AUTH-S1", title="t", description="d", layer="backend")
        )
        assert "## Testing recommendation" not in out

    def test_markdown_testing_recommendation_placeholder_when_empty(self) -> None:
        out = self._render(
            Story(id="AUTH-S1", title="t", description="d", layer="frontend")
        )
        assert "## Testing recommendation\n_(none specified)_" in out

    def test_markdown_round_trips_new_fields_through_reader(self) -> None:
        out = self._render(
            Story(
                id="AUTH-S1",
                title="t",
                description="d",
                layer="frontend",
                ui_impact="Adds a login form",
                frontend_test_recommendation=["Submit valid creds", "Submit blank"],
            )
        )
        recovered = _read_markdown_stories_for_lint(out)
        assert len(recovered) == 1
        assert recovered[0].layer == "frontend"
        assert recovered[0].ui_impact == "Adds a login form"
        assert recovered[0].frontend_test_recommendation == [
            "Submit valid creds",
            "Submit blank",
        ]

    def test_markdown_layer_tag_stripped_on_reparse_not_leaked_into_title(
        self,
    ) -> None:
        # The render-only ``[BE]`` tag must not leak into Story.title on
        # re-parse, else a second render doubles it (``[BE] [BE] …``).
        story = Story(
            id="AUTH-S1", title="Add cache", description="d", layer="backend"
        )
        out = self._render(story)
        recovered = _read_markdown_stories_for_lint(out)
        assert recovered[0].title == "Add cache"
        # Idempotent: re-rendering the recovered story yields a single tag.
        again = self._render(recovered[0])
        assert "[AUTH-S1] [BE] Add cache" in again
        assert "[BE] [BE]" not in again

    def test_markdown_empty_ui_impact_round_trips_empty_not_sentinel(
        self,
    ) -> None:
        # An empty ui_impact renders as ``_(none)_`` but must read back as
        # empty, so is_frontend_impacting stays False for a backend story.
        story = Story(
            id="AUTH-S1", title="t", description="d", layer="backend"
        )
        recovered = _read_markdown_stories_for_lint(self._render(story))
        assert recovered[0].ui_impact == ""
        assert is_frontend_impacting(recovered[0]) is False

    def test_markdown_preserves_test_rec_on_non_frontend_story(self) -> None:
        # A populated recommendation on a non-frontend-impacting story must
        # survive the markdown round-trip (not be gated out of the render).
        story = Story(
            id="AUTH-S1",
            title="t",
            description="d",
            layer="backend",
            ui_impact="none",
            frontend_test_recommendation=["Add a component test"],
        )
        assert is_frontend_impacting(story) is False
        recovered = _read_markdown_stories_for_lint(self._render(story))
        assert recovered[0].frontend_test_recommendation == [
            "Add a component test"
        ]

    def test_markdown_hand_edited_tag_prefix_preserved_when_layer_absent(
        self,
    ) -> None:
        # A hand-edited export whose title genuinely begins with `[BE] ` but
        # has no `## Layer` section: layer resolves to unspecified (render
        # would have emitted no tag), so the reader must NOT clip the authored
        # prefix — the canonical strip is symmetric with render.
        block = (
            f"{'=' * 64}\n"
            "AUTH-S1 — Plan steps: 1   (estimate: 1h)   [status: todo]\n"
            f"{'=' * 64}\n\n"
            "## Title\n[AUTH-S1] [BE] Add cache\n\n"
            "## Description\nd\n"
        )
        recovered = _read_markdown_stories_for_lint(block)
        assert recovered[0].layer == "unspecified"
        assert recovered[0].title == "[BE] Add cache"


# --- story json rendering ----------------------------------------------------


class TestRenderStoryJson:
    def test_round_trips_through_json_loads(self) -> None:
        stories = [
            Story(
                id="AUTH-S1",
                title="x",
                description="y",
                acceptance_criteria=["a"],
                files=["b.py"],
                steps=[1, 2],
                depends_on=[],
                estimate_hours=4,
            )
        ]
        out = _format_json("Demo Plan", stories, epic=_DEFAULT_EPIC)
        loaded = json.loads(out)
        assert isinstance(loaded, dict)
        assert loaded["plan_title"] == "Demo Plan"
        assert loaded["total_estimate_hours"] == 4
        assert loaded["stories"][0]["id"] == "AUTH-S1"
        # Title carries the ``[<id>] `` prefix so downstream tooling
        # gets the canonical shape used by the real JIRA tickets.
        assert loaded["stories"][0]["title"] == "[AUTH-S1] x"
        assert loaded["stories"][0]["steps"] == [1, 2]
        assert loaded["epic"]["key"] == "AUTH"

    def test_json_emits_new_field_keys(self) -> None:
        story = Story(
            id="AUTH-S1",
            title="x",
            description="y",
            layer="frontend",
            ui_impact="Adds a form",
            frontend_test_recommendation=["Submit valid"],
        )
        out = _format_json("p", [story], epic=_DEFAULT_EPIC)
        s = json.loads(out)["stories"][0]
        assert s["layer"] == "frontend"
        assert s["ui_impact"] == "Adds a form"
        assert s["frontend_test_recommendation"] == ["Submit valid"]

    def test_json_title_stays_clean_of_layer_tag(self) -> None:
        story = Story(
            id="AUTH-S1", title="x", description="y", layer="backend"
        )
        out = _format_json("p", [story], epic=_DEFAULT_EPIC)
        s = json.loads(out)["stories"][0]
        assert s["title"] == "[AUTH-S1] x"
        assert "[BE]" not in s["title"]

    def test_json_title_folds_in_plan_tag(self) -> None:
        story = Story(id="AUTH-S1", title="x", description="y")
        out = _format_json("p", [story], epic=_DEFAULT_EPIC, plan_tag="DCL")
        s = json.loads(out)["stories"][0]
        assert s["title"] == "[AUTH-S1] [DCL] x"

    def test_json_title_blank_plan_tag_omits_bracket(self) -> None:
        story = Story(id="AUTH-S1", title="x", description="y")
        out = _format_json("p", [story], epic=_DEFAULT_EPIC, plan_tag="")
        s = json.loads(out)["stories"][0]
        assert s["title"] == "[AUTH-S1] x"

    def test_json_frontend_test_recommendation_is_list_copy(self) -> None:
        recs = ["Submit valid"]
        story = Story(
            id="AUTH-S1",
            title="x",
            description="y",
            layer="frontend",
            frontend_test_recommendation=recs,
        )
        emitted = _story_to_json_dict(story, {})
        assert emitted["frontend_test_recommendation"] == recs
        assert emitted["frontend_test_recommendation"] is not recs


# --- title prefix + cross-story reference normalization -------------------


class TestStoryTitlePrefix:
    def test_markdown_prepends_id_to_title(self) -> None:
        stories = [
            Story(
                id="AUTH-S2",
                title="Wire X",
                description="d",
                acceptance_criteria=[],
                files=[],
                steps=[1],
                depends_on=[],
                estimate_hours=1,
            )
        ]
        out = _format_markdown("p", stories, epic=_DEFAULT_EPIC)
        assert "[AUTH-S2] Wire X" in out
        # The bare title must not appear on its own ``## Title`` line.
        assert "\nWire X\n" not in out

    def test_parse_strips_existing_prefix_in_title(self) -> None:
        """Claude shouldn't include the prefix (the prompt says so),
        but if it slips through we drop it so the renderer doesn't
        emit ``[AUTH-S1] [AUTH-S1] x``."""
        body = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "[AUTH-S1] Wire X",
                    "description": "d",
                    "acceptance_criteria": [],
                    "files": [],
                    "steps": [1, 2],
                    "depends_on": [],
                    "estimate_hours": 1,
                }
            ]
        )
        stories = parse_jira_response(
            body, [1, 2], epic=_DEFAULT_EPIC
        )
        assert stories is not None
        assert stories[0].title == "Wire X"
        rendered = _format_markdown("p", stories, epic=_DEFAULT_EPIC)
        assert "[AUTH-S1] Wire X" in rendered
        assert "[AUTH-S1] [AUTH-S1]" not in rendered


class TestStoryReferenceNormalization:
    def test_bare_sN_in_description_rewritten_to_full_id(self) -> None:
        body = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "scaffold",
                    "description": "Sets up the contract S2 consumes.",
                    "acceptance_criteria": ["foo"],
                    "files": [],
                    "steps": [1],
                    "depends_on": [],
                    "estimate_hours": 1,
                },
                {
                    "id": "AUTH-S2",
                    "title": "consumer",
                    "description": "Reads contract from S1; later S1 hook fires.",
                    "acceptance_criteria": [
                        "after S1 deploys, /foo returns 200",
                    ],
                    "files": [],
                    "steps": [2],
                    "depends_on": ["AUTH-S1"],
                    "estimate_hours": 1,
                },
            ]
        )
        stories = parse_jira_response(
            body, [1, 2], epic=_DEFAULT_EPIC
        )
        assert stories is not None
        assert stories[0].description == "Sets up the contract AUTH-S2 consumes."
        assert (
            stories[1].description
            == "Reads contract from AUTH-S1; later AUTH-S1 hook fires."
        )
        assert stories[1].acceptance_criteria == [
            "after AUTH-S1 deploys, /foo returns 200"
        ]

    def test_already_prefixed_ids_left_alone(self) -> None:
        body = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "x",
                    "description": "blocks AUTH-S2",
                    "acceptance_criteria": [],
                    "files": [],
                    "steps": [1, 2],
                    "depends_on": [],
                    "estimate_hours": 1,
                },
                {
                    "id": "AUTH-S2",
                    "title": "y",
                    "description": "z",
                    "acceptance_criteria": [],
                    "files": [],
                    "steps": [2],
                    "depends_on": ["AUTH-S1"],
                    "estimate_hours": 1,
                },
            ]
        )
        stories = parse_jira_response(
            body, [1, 2], epic=_DEFAULT_EPIC
        )
        assert stories is not None
        assert stories[0].description == "blocks AUTH-S2"

    def test_unrelated_sN_tokens_not_rewritten(self) -> None:
        """``S3`` (AWS) and ``S4`` (gear) must survive — only ``S<N>``
        for ``N`` that's actually a story id in this response should
        get prefixed."""
        body = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "x",
                    "description": "Uploads to S3 bucket; depends on S2.",
                    "acceptance_criteria": ["S3 object exists at key foo"],
                    "files": [],
                    "steps": [1, 2],
                    "depends_on": [],
                    "estimate_hours": 1,
                },
                {
                    "id": "AUTH-S2",
                    "title": "y",
                    "description": "z",
                    "acceptance_criteria": [],
                    "files": [],
                    "steps": [2],
                    "depends_on": [],
                    "estimate_hours": 1,
                },
            ]
        )
        stories = parse_jira_response(
            body, [1, 2], epic=_DEFAULT_EPIC
        )
        assert stories is not None
        # ``S2`` was a real story → rewritten. ``S3`` was not → kept.
        assert (
            stories[0].description
            == "Uploads to S3 bucket; depends on AUTH-S2."
        )
        assert stories[0].acceptance_criteria == [
            "S3 object exists at key foo"
        ]


# --- Story layer fields + helpers -----------------------------------------


class TestStoryLayerFields:
    def test_story_defaults_new_fields(self) -> None:
        s = Story(id="AUTH-S1", title="scaffold", description="d")
        assert s.layer == "unspecified"
        assert s.ui_impact == ""
        assert s.frontend_test_recommendation == []

    def test_story_accepts_new_fields(self) -> None:
        s = Story(
            id="AUTH-S1",
            title="scaffold",
            description="d",
            layer="backend",
            ui_impact="new banner appears on save",
            frontend_test_recommendation=["assert banner renders"],
        )
        assert s.layer == "backend"
        assert s.ui_impact == "new banner appears on save"
        assert s.frontend_test_recommendation == ["assert banner renders"]

    def test_layer_tag_for_each_layer(self) -> None:
        assert layer_tag("frontend") == "[FE]"
        assert layer_tag("backend") == "[BE]"
        assert layer_tag("full_stack") == "[FE+BE]"
        assert layer_tag("infra") == "[INFRA]"

    def test_layer_tag_unspecified_and_unknown_empty(self) -> None:
        assert layer_tag("unspecified") == ""
        assert layer_tag("bogus") == ""
        assert layer_tag("") == ""

    def test_frontend_impacting_frontend_and_full_stack(self) -> None:
        assert is_frontend_impacting(
            Story(id="A-S1", title="t", description="d", layer="frontend")
        )
        assert is_frontend_impacting(
            Story(id="A-S1", title="t", description="d", layer="full_stack")
        )
        # true regardless of ui_impact
        assert is_frontend_impacting(
            Story(
                id="A-S1", title="t", description="d",
                layer="frontend", ui_impact="none",
            )
        )

    def test_frontend_impacting_backend_with_ui_impact(self) -> None:
        assert is_frontend_impacting(
            Story(
                id="A-S1", title="t", description="d",
                layer="backend", ui_impact="adds a spinner",
            )
        )

    def test_frontend_impacting_backend_none_or_empty(self) -> None:
        for ui in ("", "none", "None"):
            assert not is_frontend_impacting(
                Story(
                    id="A-S1", title="t", description="d",
                    layer="backend", ui_impact=ui,
                )
            )

    def test_frontend_impacting_infra_and_unspecified(self) -> None:
        assert not is_frontend_impacting(
            Story(id="A-S1", title="t", description="d", layer="infra")
        )
        assert not is_frontend_impacting(
            Story(id="A-S1", title="t", description="d", layer="unspecified")
        )

    def test_valid_layers_membership(self) -> None:
        assert _VALID_LAYERS == ("frontend", "backend", "full_stack", "infra")
        assert "unspecified" not in _VALID_LAYERS

    def test_normalize_preserves_new_fields(self) -> None:
        recs = ["assert banner renders"]
        s = Story(
            id="AUTH-S1",
            title="scaffold",
            description="d",
            steps=[1],
            layer="backend",
            ui_impact="new banner on save",
            frontend_test_recommendation=recs,
        )
        out = _normalize_story_references([s], _DEFAULT_EPIC)
        assert out[0].layer == "backend"
        assert out[0].ui_impact == "new banner on save"
        assert out[0].frontend_test_recommendation == ["assert banner renders"]
        # the list is a copy, not an alias
        recs.append("mutated")
        assert out[0].frontend_test_recommendation == ["assert banner renders"]


class TestPlanTagBracket:
    def test_non_empty_tag_wraps_in_brackets(self) -> None:
        assert plan_tag_bracket("DCL") == "[DCL]"

    def test_empty_tag_is_empty(self) -> None:
        assert plan_tag_bracket("") == ""


# --- derive_jira_output_path ----------------------------------------------


class TestDeriveJiraOutputPath:
    def test_strips_leading_digit_prefix_and_writes_md(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_plan(tmp_path)
        plan = parse_plan(plan_path)
        out = derive_jira_output_path(plan_path, plan, format="markdown")
        assert out == tmp_path / "plan-details" / "demo" / "jira-stories.md"

    def test_json_format_produces_json_extension(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_plan(tmp_path)
        plan = parse_plan(plan_path)
        out = derive_jira_output_path(plan_path, plan, format="json")
        assert out == tmp_path / "plan-details" / "demo" / "jira-stories.json"

    def test_unknown_format_raises(self, tmp_path: Path) -> None:
        plan_path = _write_plan(tmp_path)
        plan = parse_plan(plan_path)
        with pytest.raises(JiraError):
            derive_jira_output_path(plan_path, plan, format="xml")  # type: ignore[arg-type]


# --- scan_existing_story_numbers / compute_start_number -------------------


class TestScanExistingStoryNumbers:
    def test_no_directory_returns_empty(self, tmp_path: Path) -> None:
        plan_path = _write_plan(tmp_path)
        assert (
            scan_existing_story_numbers(plan_path, _DEFAULT_EPIC) == set()
        )

    def test_picks_up_numbers_from_md_and_json(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_plan(tmp_path)
        # Sibling plan (different slug) already wrote stories.
        other = tmp_path / "plan-details" / "other"
        other.mkdir(parents=True)
        (other / "jira-stories.md").write_text(
            "AUTH-S1 — Plan steps: 1\nAUTH-S5 — Plan steps: 2\n",
            encoding="utf-8",
        )
        (other / "jira-stories.json").write_text(
            json.dumps(
                {
                    "stories": [
                        {"id": "AUTH-S7"},
                        {"id": "AUTH-S12"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        found = scan_existing_story_numbers(plan_path, _DEFAULT_EPIC)
        assert found == {1, 5, 7, 12}

    def test_ignores_other_epics(self, tmp_path: Path) -> None:
        plan_path = _write_plan(tmp_path)
        other = tmp_path / "plan-details" / "other"
        other.mkdir(parents=True)
        (other / "jira-stories.md").write_text(
            "PAY-S1\nPAY-S99\n", encoding="utf-8"
        )
        assert (
            scan_existing_story_numbers(plan_path, _DEFAULT_EPIC) == set()
        )

    def test_excludes_own_plan_output(self, tmp_path: Path) -> None:
        plan_path = _write_plan(tmp_path)
        # Own output already exists from a prior run.
        own = tmp_path / "plan-details" / "demo"
        own.mkdir(parents=True)
        (own / "jira-stories.md").write_text(
            "AUTH-S5 — Plan steps: 1\nAUTH-S6 — Plan steps: 2\n",
            encoding="utf-8",
        )
        # Sibling plan also wrote stories.
        other = tmp_path / "plan-details" / "other"
        other.mkdir(parents=True)
        (other / "jira-stories.md").write_text(
            "AUTH-S1 — Plan steps: 1\n", encoding="utf-8"
        )
        found = scan_existing_story_numbers(plan_path, _DEFAULT_EPIC)
        # Own numbers (5, 6) excluded; sibling number (1) included.
        assert found == {1}

    def test_includes_archived_plan_numbers(self, tmp_path: Path) -> None:
        plan_path = _write_plan(tmp_path)
        # An archived plan keeps its original ids; they must still count.
        archived = tmp_path / "archive" / "plan-details" / "old"
        archived.mkdir(parents=True)
        (archived / "jira-stories.md").write_text(
            "AUTH-S3 — Plan steps: 1\nAUTH-S9 — Plan steps: 2\n",
            encoding="utf-8",
        )
        # A live sibling also wrote stories.
        other = tmp_path / "plan-details" / "other"
        other.mkdir(parents=True)
        (other / "jira-stories.md").write_text(
            "AUTH-S1 — Plan steps: 1\n", encoding="utf-8"
        )
        found = scan_existing_story_numbers(plan_path, _DEFAULT_EPIC)
        assert found == {1, 3, 9}

    def test_archive_only_no_live_details(self, tmp_path: Path) -> None:
        # No live plan-details dir at all, only an archive: still scanned.
        plan_path = _write_plan(tmp_path)
        archived = tmp_path / "archive" / "plan-details" / "old"
        archived.mkdir(parents=True)
        (archived / "jira-stories.json").write_text(
            json.dumps({"stories": [{"id": "AUTH-S4"}]}),
            encoding="utf-8",
        )
        assert compute_start_number(plan_path, _DEFAULT_EPIC) == 5


class TestComputeStartNumber:
    def test_first_plan_starts_at_one(self, tmp_path: Path) -> None:
        plan_path = _write_plan(tmp_path)
        assert compute_start_number(plan_path, _DEFAULT_EPIC) == 1

    def test_picks_up_after_existing_max(self, tmp_path: Path) -> None:
        plan_path = _write_plan(tmp_path)
        other = tmp_path / "plan-details" / "other"
        other.mkdir(parents=True)
        (other / "jira-stories.md").write_text(
            "AUTH-S1 — x\nAUTH-S7 — x\nAUTH-S3 — x\n", encoding="utf-8"
        )
        assert compute_start_number(plan_path, _DEFAULT_EPIC) == 8


class TestParseJiraResponseHardened:
    def test_large_estimate_accepted_no_cap(self) -> None:
        """estimate_hours is advisory — a large-but-atomic story is kept.

        There is no upper cap: atomicity, not an hour ceiling, bounds a
        story, so a big estimate parses cleanly rather than being rejected.
        """
        body = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "x",
                    "description": "y",
                    "steps": [1],
                    "estimate_hours": 12,
                }
            ]
        )
        stories = parse_jira_response(
            body, plan_step_ids=[1], epic=_DEFAULT_EPIC
        )
        assert stories is not None
        assert stories[0].estimate_hours == 12

    def test_normal_estimate_accepted(self) -> None:
        body = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "x",
                    "description": "y",
                    "steps": [1],
                    "estimate_hours": 4,
                }
            ]
        )
        stories = parse_jira_response(
            body, plan_step_ids=[1], epic=_DEFAULT_EPIC
        )
        assert stories is not None
        assert stories[0].estimate_hours == 4

    def test_estimate_zero_rejected(self) -> None:
        body = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "x",
                    "description": "y",
                    "steps": [1],
                    "estimate_hours": 0,
                }
            ]
        )
        assert (
            parse_jira_response(
                body, plan_step_ids=[1], epic=_DEFAULT_EPIC
            )
            is None
        )

    def test_estimate_negative_rejected(self) -> None:
        body = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "x",
                    "description": "y",
                    "steps": [1],
                    "estimate_hours": -1,
                }
            ]
        )
        assert (
            parse_jira_response(
                body, plan_step_ids=[1], epic=_DEFAULT_EPIC
            )
            is None
        )

    def test_depends_on_freeform_string_rejected(self) -> None:
        body = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "x",
                    "description": "y",
                    "steps": [1],
                    "depends_on": ["previous story"],
                    "estimate_hours": 2,
                }
            ]
        )
        assert (
            parse_jira_response(
                body, plan_step_ids=[1], epic=_DEFAULT_EPIC
            )
            is None
        )

    def test_depends_on_unresolved_id_rejected(self) -> None:
        """``AUTH-S99`` has the right shape but isn't elsewhere in the response."""
        body = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "x",
                    "description": "y",
                    "steps": [1],
                    "depends_on": ["AUTH-S99"],
                    "estimate_hours": 2,
                }
            ]
        )
        assert (
            parse_jira_response(
                body, plan_step_ids=[1], epic=_DEFAULT_EPIC
            )
            is None
        )

    def test_depends_on_resolves_within_response(self) -> None:
        body = _split_payload()
        stories = parse_jira_response(
            body, plan_step_ids=[1, 2], epic=_DEFAULT_EPIC
        )
        assert stories is not None
        assert stories[1].depends_on == ["AUTH-S1"]
        assert stories[2].depends_on == ["AUTH-S2"]


# --- lint_acceptance_criteria ---------------------------------------------


def _story(
    *,
    id: str = "AUTH-S1",
    acceptance_criteria: Optional[list[str]] = None,
    steps: Optional[list[int]] = None,
) -> Story:
    """Build a minimal Story for lint tests.

    Only the fields the linter actually inspects are interesting; the
    rest get harmless defaults so the test reads at the level of the
    behavior being checked.
    """
    return Story(
        id=id,
        title="t",
        description="d",
        acceptance_criteria=list(acceptance_criteria or []),
        files=[],
        steps=list(steps or [1]),
        depends_on=[],
        estimate_hours=1,
    )


class TestLintAcceptanceCriteria:
    def test_no_warnings_for_observable_bullets(self) -> None:
        """Mechanical, behavior-stable bullets — the shape the prompt
        teaches — produce zero warnings."""
        stories = [
            _story(
                acceptance_criteria=[
                    "GET /foo returns 200 with a `cursor` field",
                    (
                        "the TODO cleanup marker is absent from the generated "
                        "settings page"
                    ),
                    "an unauthorized user receives 403 on POST /admin/app-mode",
                    "a test fails if the cache-key hash drops `step.title` from its inputs",
                ]
            )
        ]
        assert lint_acceptance_criteria(stories) == []

    def test_warns_when_acceptance_criteria_empty(self) -> None:
        warnings = lint_acceptance_criteria([_story(acceptance_criteria=[])])
        assert len(warnings) == 1
        assert "AUTH-S1" in warnings[0]
        assert "no acceptance criteria" in warnings[0]

    def test_flags_vague_phrasing(self) -> None:
        cases = [
            "Code is clean",
            "The handler is well-tested",
            "The handler is well tested",
            "Tests are comprehensive",
            "It looks correct after the refactor",
            "The endpoint works as expected",
            "All tests pass",
            "tests pass",
            "No regressions",
            "no errors",
        ]
        for bullet in cases:
            warnings = lint_acceptance_criteria(
                [_story(acceptance_criteria=[bullet])]
            )
            assert len(warnings) == 1, f"expected warning for {bullet!r}"
            assert "vague phrasing" in warnings[0]
            assert bullet in warnings[0]

    def test_does_not_flag_qualified_use_of_brittle_words(self) -> None:
        """A bullet that uses the brittle word inside a richer,
        observable claim is fine — the anchored bare-bullet patterns
        don't fire."""
        ok = [
            "Lambda emits no errors when invoked with the empty payload fixture",
            "All tests pass after the helper is renamed; nothing here that the lint should flag in isolation",
        ]
        # The first bullet is fine. The second contains "All tests pass"
        # but is not a bare bullet, so the anchored ``^…$`` pattern
        # shouldn't fire — confirming the linter doesn't drown the user
        # in noise on qualified uses.
        assert lint_acceptance_criteria([_story(acceptance_criteria=ok)]) == []

    def test_flags_test_function_handles(self) -> None:
        cases = [
            "test_cache_miss passes",
            "test_cache_miss()",
            "it('renders the row')",
            'it("renders the row")',
            "should_render_row holds",
        ]
        for bullet in cases:
            warnings = lint_acceptance_criteria(
                [_story(acceptance_criteria=[bullet])]
            )
            assert len(warnings) == 1, f"expected warning for {bullet!r}"
            assert "refactor-fragile" in warnings[0]

    def test_flags_file_line_handles(self) -> None:
        cases = [
            "handler.ts:42 returns the cached row",
            "amplify/lambda/foo/handler.py:117 no longer logs the secret",
            "line 42 returns the cached row",
        ]
        for bullet in cases:
            warnings = lint_acceptance_criteria(
                [_story(acceptance_criteria=[bullet])]
            )
            assert len(warnings) == 1, f"expected warning for {bullet!r}"
            assert "refactor-fragile" in warnings[0]

    def test_flags_grep_and_call_counts(self) -> None:
        cases = [
            "git grep 'old_helper' returns no matches",
            "grep TODO finds exactly 2 matches",
            "There are zero call-sites for old_helper",
            "old_helper occurs exactly 1 time",
        ]
        for bullet in cases:
            warnings = lint_acceptance_criteria(
                [_story(acceptance_criteria=[bullet])]
            )
            assert len(warnings) == 1, f"expected warning for {bullet!r}"
            assert "grep/call-count" in warnings[0]

    def test_flags_import_lists(self) -> None:
        warnings = lint_acceptance_criteria(
            [
                _story(
                    acceptance_criteria=[
                        "from plan_tool.jira import Story, JiraError, export_jira",
                    ]
                )
            ]
        )
        assert len(warnings) == 1
        assert "import list" in warnings[0]

    def test_flags_file_size_caps(self) -> None:
        cases = [
            "plan_tool/jira.py stays under 1200 lines",
            "helper file remains below 8 KB",
        ]
        for bullet in cases:
            warnings = lint_acceptance_criteria(
                [_story(acceptance_criteria=[bullet])]
            )
            assert len(warnings) == 1, f"expected warning for {bullet!r}"
            assert "file-size cap" in warnings[0]

    def test_flags_infra_literals_outside_infra_contract(self) -> None:
        warnings = lint_acceptance_criteria(
            [
                Story(
                    id="AUTH-S1",
                    title="Add login validation",
                    description="User-facing form behavior.",
                    acceptance_criteria=[
                        "Lambda function auth-prod-login keeps the same IAM role",
                    ],
                    files=["app/login.py"],
                    steps=[1],
                    depends_on=[],
                    estimate_hours=1,
                )
            ]
        )
        assert len(warnings) == 1
        assert "infra literal" in warnings[0]

    def test_allows_infra_literals_for_infra_contract(self) -> None:
        warnings = lint_acceptance_criteria(
            [
                Story(
                    id="AUTH-S1",
                    title="Update CDK stack",
                    description="Infrastructure deployment contract.",
                    acceptance_criteria=[
                        "Lambda function auth-prod-login keeps the same IAM role",
                    ],
                    files=["infra/auth-stack.ts"],
                    steps=[1],
                    depends_on=[],
                    estimate_hours=1,
                )
            ]
        )
        assert warnings == []

    def test_flags_verification_evidence_without_behavior(self) -> None:
        warnings = lint_acceptance_criteria(
            [
                _story(
                    acceptance_criteria=[
                        "Verification notes are recorded in the release report",
                    ]
                )
            ]
        )
        assert len(warnings) == 1
        assert "verification evidence" in warnings[0]

    def test_collapses_duplicate_warnings_per_story(self) -> None:
        """Multiple bullets sharing the same failure category produce
        at most one warning per category — the user gets pointed at the
        problem without the message repeating five times."""
        stories = [
            _story(
                acceptance_criteria=[
                    "Code is clean",
                    "Tests are comprehensive",
                    "All tests pass",
                ]
            )
        ]
        warnings = lint_acceptance_criteria(stories)
        assert len(warnings) == 1
        assert "vague phrasing" in warnings[0]

    def test_separate_categories_emit_separate_warnings(self) -> None:
        """Vague-phrasing and internal-handle failures are independent
        signals — both fire when both shapes appear."""
        stories = [
            _story(
                acceptance_criteria=[
                    "Code is clean",
                    "test_foo passes",
                ]
            )
        ]
        warnings = lint_acceptance_criteria(stories)
        categories = {
            "vague" if "vague phrasing" in w else "handle" for w in warnings
        }
        assert categories == {"vague", "handle"}

    def test_warnings_scoped_per_story(self) -> None:
        """Each story is linted independently — one bad story doesn't
        suppress another story's warnings."""
        stories = [
            _story(id="AUTH-S1", acceptance_criteria=["Code is clean"]),
            _story(id="AUTH-S2", acceptance_criteria=[]),
            _story(
                id="AUTH-S3",
                acceptance_criteria=[
                    "GET /foo returns 200 with a `cursor` field",
                ],
            ),
        ]
        warnings = lint_acceptance_criteria(stories)
        assert any("AUTH-S1" in w and "vague" in w for w in warnings)
        assert any("AUTH-S2" in w and "no acceptance criteria" in w for w in warnings)
        assert not any("AUTH-S3" in w for w in warnings)


# --- lint_layer_metadata --------------------------------------------------


def _layer_story(
    *,
    id: str = "AUTH-S1",
    layer: str = _LAYER_UNSPECIFIED,
    ui_impact: str = "",
    frontend_test_recommendation: Optional[list[str]] = None,
) -> Story:
    """Build a Story exercising only the layer-metadata fields."""
    return Story(
        id=id,
        title="t",
        description="d",
        acceptance_criteria=[],
        files=[],
        steps=[1],
        depends_on=[],
        estimate_hours=1,
        layer=layer,
        ui_impact=ui_impact,
        frontend_test_recommendation=list(frontend_test_recommendation or []),
    )


_SUBSTANTIVE_REC = [
    "Add a component test for the checkout total updating when a line is removed",
]


class TestLintLayerMetadata:
    def _ui_impact_findings(self, warnings: list[str]) -> list[str]:
        return [w for w in warnings if "UI-impact note" in w]

    def _test_rec_findings(self, warnings: list[str]) -> list[str]:
        return [w for w in warnings if "test recommendation" in w]

    def test_backend_missing_ui_impact_warns(self) -> None:
        story = _layer_story(layer="backend", ui_impact="")
        findings = self._ui_impact_findings(lint_layer_metadata([story]))
        assert len(findings) == 1
        assert "AUTH-S1" in findings[0]

    def test_full_stack_missing_ui_impact_warns(self) -> None:
        story = _layer_story(layer="full_stack", ui_impact="")
        findings = self._ui_impact_findings(lint_layer_metadata([story]))
        assert len(findings) == 1
        assert "AUTH-S1" in findings[0]

    def test_backend_ui_impact_none_no_warning(self) -> None:
        for value in ("none", "None"):
            story = _layer_story(layer="backend", ui_impact=value)
            assert self._ui_impact_findings(lint_layer_metadata([story])) == []

    def test_backend_ui_impact_present_no_warning(self) -> None:
        story = _layer_story(
            layer="backend",
            ui_impact="adds a new balance field to the account summary card",
        )
        assert self._ui_impact_findings(lint_layer_metadata([story])) == []

    def test_frontend_infra_unspecified_no_ui_impact_check(self) -> None:
        for layer in ("frontend", "infra", "unspecified"):
            story = _layer_story(layer=layer, ui_impact="")
            assert self._ui_impact_findings(lint_layer_metadata([story])) == []

    def test_frontend_impacting_empty_test_rec_warns(self) -> None:
        story = _layer_story(layer="frontend", frontend_test_recommendation=[])
        findings = self._test_rec_findings(lint_layer_metadata([story]))
        assert len(findings) == 1
        assert "AUTH-S1" in findings[0]

    def test_backend_with_ui_impact_empty_test_rec_warns(self) -> None:
        story = _layer_story(
            layer="backend",
            ui_impact="changes the error banner copy",
            frontend_test_recommendation=[],
        )
        assert is_frontend_impacting(story)
        findings = self._test_rec_findings(lint_layer_metadata([story]))
        assert len(findings) == 1

    def test_low_content_test_rec_warns(self) -> None:
        story = _layer_story(
            layer="frontend", frontend_test_recommendation=["test it"]
        )
        assert len(self._test_rec_findings(lint_layer_metadata([story]))) == 1

    def test_substantive_test_rec_no_warning(self) -> None:
        story = _layer_story(
            layer="frontend", frontend_test_recommendation=list(_SUBSTANTIVE_REC)
        )
        assert self._test_rec_findings(lint_layer_metadata([story])) == []

    def test_non_frontend_impacting_test_rec_not_checked(self) -> None:
        story = _layer_story(
            layer="backend", ui_impact="none", frontend_test_recommendation=[]
        )
        assert self._test_rec_findings(lint_layer_metadata([story])) == []

    def test_full_stack_empty_both_yields_two_findings(self) -> None:
        story = _layer_story(
            layer="full_stack", ui_impact="", frontend_test_recommendation=[]
        )
        warnings = lint_layer_metadata([story])
        assert len(warnings) == 2
        assert len(self._ui_impact_findings(warnings)) == 1
        assert len(self._test_rec_findings(warnings)) == 1

    def test_one_warning_per_check_per_story(self) -> None:
        """Many blank rec bullets still produce one test-rec finding."""
        story = _layer_story(
            layer="frontend",
            frontend_test_recommendation=["", "  ", "x", "y"],
        )
        assert len(self._test_rec_findings(lint_layer_metadata([story]))) == 1


# --- lint_story_size ------------------------------------------------------


def _size_story(*, id: str = "AUTH-S1", estimate_hours: int = 4) -> Story:
    """Build a Story exercising only the estimate-size field.

    Carries a valid observable AC so the blocking acceptance-criteria lint
    stays silent and the story-size finding is isolated.
    """
    return Story(
        id=id,
        title="t",
        description="d",
        acceptance_criteria=["GET /foo returns 200 with a `cursor` field"],
        files=[],
        steps=[1],
        depends_on=[],
        estimate_hours=estimate_hours,
    )


class TestLintStorySize:
    def test_below_floor_warns(self) -> None:
        for hours in (1, 2, 3):
            story = _size_story(estimate_hours=hours)
            findings = lint_story_size([story])
            assert len(findings) == 1
            assert "AUTH-S1" in findings[0]
            assert f"{hours}h" in findings[0]

    def test_at_or_above_floor_no_warning(self) -> None:
        for hours in (4, 5, 8, 20):
            assert lint_story_size([_size_story(estimate_hours=hours)]) == []

    def test_not_provided_sentinel_no_warning(self) -> None:
        """A non-positive estimate is the "not provided" sentinel
        (``read_stories_for_lint`` coerces missing/invalid to 0), not a
        real sub-floor ticket — flagging it would give "0h" advice."""
        for hours in (0, -3):
            assert lint_story_size([_size_story(estimate_hours=hours)]) == []

    def test_one_finding_per_undersized_story(self) -> None:
        stories = [
            _size_story(id="AUTH-S1", estimate_hours=1),
            _size_story(id="AUTH-S2", estimate_hours=6),
            _size_story(id="AUTH-S3", estimate_hours=2),
        ]
        findings = lint_story_size(stories)
        assert len(findings) == 2
        assert any("AUTH-S1" in f for f in findings)
        assert any("AUTH-S3" in f for f in findings)
        assert not any("AUTH-S2" in f for f in findings)

    def test_partition_puts_size_on_advisory_side(self) -> None:
        """A sub-floor story is advisory, never blocking."""
        story = _size_story(
            id="AUTH-S1",
            estimate_hours=1,
        )
        blocking, advisory = partition_lint_findings([story])
        assert blocking == []
        assert any("soft decomposition floor" in f for f in advisory)

    def test_partition_no_size_finding_when_above_floor(self) -> None:
        story = _size_story(estimate_hours=8)
        _, advisory = partition_lint_findings([story])
        assert not any("soft decomposition floor" in f for f in advisory)


class TestReadStoriesForLint:
    def test_rejects_non_utf8_input_as_jira_error(self, tmp_path: Path) -> None:
        path = tmp_path / "jira-stories.md"
        path.write_bytes(b"\xff")

        with pytest.raises(JiraError, match="failed to read jira lint input"):
            read_stories_for_lint(path)

    def test_reads_markdown_export_acceptance_criteria(self, tmp_path: Path) -> None:
        path = tmp_path / "jira-stories.md"
        path.write_text(
            _format_markdown(
                "Demo",
                [
                    Story(
                        id="AUTH-S1",
                        title="Add behavior",
                        description="Ship the behavior.",
                        acceptance_criteria=["Code is clean"],
                        files=["parser.py"],
                        steps=[1],
                        depends_on=[],
                        estimate_hours=1,
                    )
                ],
                epic=_DEFAULT_EPIC,
                step_detail_map={},
            )
            + "\n",
            encoding="utf-8",
        )
        stories = read_stories_for_lint(path)
        assert [s.id for s in stories] == ["AUTH-S1"]
        assert stories[0].acceptance_criteria == ["Code is clean"]
        assert lint_acceptance_criteria(stories)

    def test_markdown_companion_provenance_does_not_extend_last_ui_section(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "jira-stories.md"
        source = _format_markdown(
            "Demo",
            [
                Story(
                    id="AUTH-S1",
                    title="Add behavior",
                    description="Ship the behavior.",
                    acceptance_criteria=["Code is clean"],
                    files=["parser.py"],
                    steps=[1],
                    depends_on=[],
                    estimate_hours=1,
                    layer="backend",
                )
            ],
            epic=_DEFAULT_EPIC,
            step_detail_map={},
        )
        path.write_text(
            source
            + "\n\n<!-- plan-tool-companion-provenance\n"
            + "fingerprint: example\n-->\n",
            encoding="utf-8",
        )

        lint_story = read_stories_for_lint(path)[0]
        from plan_tool.jira import _read_existing_export_text

        existing = _read_existing_export_text(
            path.read_text(encoding="utf-8"), format="markdown", epic=_DEFAULT_EPIC
        )

        assert lint_story.ui_impact == ""
        assert existing is not None
        assert "plan-tool-companion-provenance" not in existing.tickets[0].raw_markdown

    def test_reads_json_export_acceptance_criteria(self, tmp_path: Path) -> None:
        path = tmp_path / "jira-stories.json"
        path.write_text(
            _format_json(
                "Demo",
                [
                    Story(
                        id="AUTH-S1",
                        title="Add behavior",
                        description="Ship the behavior.",
                        acceptance_criteria=["Code is clean"],
                        files=["parser.py"],
                        steps=[1],
                        depends_on=[],
                        estimate_hours=1,
                    )
                ],
                epic=_DEFAULT_EPIC,
                step_detail_map={},
            )
            + "\n",
            encoding="utf-8",
        )
        stories = read_stories_for_lint(path)
        assert stories[0].acceptance_criteria == ["Code is clean"]
        assert lint_acceptance_criteria(stories)

    def test_json_lint_reader_reads_new_fields(self) -> None:
        text = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "Add behavior",
                    "description": "Ship it.",
                    "acceptance_criteria": ["parse_plan returns a Plan"],
                    "files": ["parser.py"],
                    "steps": [1],
                    "depends_on": [],
                    "estimate_hours": 1,
                    "layer": "frontend",
                    "ui_impact": "renders a new panel",
                    "frontend_test_recommendation": ["assert panel visible"],
                }
            ]
        )
        stories = _read_json_stories_for_lint(text)
        assert len(stories) == 1
        s = stories[0]
        assert s.layer == "frontend"
        assert s.ui_impact == "renders a new panel"
        assert s.frontend_test_recommendation == ["assert panel visible"]

    def test_json_lint_reader_defaults_and_tolerates_bad_types(self) -> None:
        text = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "Add behavior",
                    "description": "Ship it.",
                    "steps": [1],
                    "estimate_hours": 1,
                },
                {
                    "id": "AUTH-S2",
                    "title": "Bad types",
                    "description": "Ship it.",
                    "steps": [1],
                    "estimate_hours": 1,
                    "layer": "middleware",
                    "ui_impact": 42,
                    "frontend_test_recommendation": "not a list",
                },
            ]
        )
        stories = _read_json_stories_for_lint(text)
        missing, bad = stories
        assert missing.layer == _LAYER_UNSPECIFIED
        assert missing.ui_impact == ""
        assert missing.frontend_test_recommendation == []
        assert bad.layer == _LAYER_UNSPECIFIED
        assert bad.ui_impact == ""
        assert bad.frontend_test_recommendation == []

    def test_markdown_lint_reader_reads_new_field_sections(self) -> None:
        rule = "=" * 64
        block = (
            f"{rule}\n"
            "AUTH-S1 — Plan steps: 1 (estimate: 1h) [status: todo]\n"
            f"{rule}\n\n"
            "## Title\n[AUTH-S1] Add behavior\n\n"
            "## Description\nShip it.\n\n"
            "## Layer\nbackend\n\n"
            "## UI impact\nnone\n\n"
            "## Acceptance criteria\n- parse_plan returns a Plan\n\n"
            "## Testing recommendation\n- assert spinner renders\n- assert toast\n\n"
            "## Files in scope\n- `parser.py`\n\n"
            "## Depends on\n- _(none)_\n"
        )
        stories = _read_markdown_stories_for_lint(block)
        assert len(stories) == 1
        s = stories[0]
        assert s.layer == "backend"
        assert s.ui_impact == "none"
        assert s.frontend_test_recommendation == [
            "assert spinner renders",
            "assert toast",
        ]

    def test_markdown_lint_reader_defaults_when_sections_absent(self) -> None:
        rule = "=" * 64
        block = (
            f"{rule}\n"
            "AUTH-S1 — Plan steps: 1 (estimate: 1h) [status: todo]\n"
            f"{rule}\n\n"
            "## Title\n[AUTH-S1] Add behavior\n\n"
            "## Description\nShip it.\n\n"
            "## Acceptance criteria\n- parse_plan returns a Plan\n\n"
            "## Files in scope\n- `parser.py`\n\n"
            "## Depends on\n- _(none)_\n"
        )
        stories = _read_markdown_stories_for_lint(block)
        assert len(stories) == 1
        s = stories[0]
        assert s.layer == _LAYER_UNSPECIFIED
        assert s.ui_impact == ""
        assert s.frontend_test_recommendation == []


class TestJiraStyleOutput:
    """Pin ``_emit_story_warnings`` to ``style.warn()``: plain-mode bytes
    are unchanged and color, when forced on, paints only the prefix."""

    @staticmethod
    def _story(
        *,
        id: str = "AUTH-S1",
        acceptance_criteria: Optional[list[str]] = None,
        files: Optional[list[str]] = None,
        estimate_hours: int = 4,
    ) -> Story:
        # Default at the 4h floor so these exact-stderr assertions aren't
        # perturbed by the advisory story-size warning (tested separately).
        return Story(
            id=id,
            title="t",
            description="d",
            acceptance_criteria=list(acceptance_criteria or []),
            files=list(files or []),
            steps=[1],
            depends_on=[],
            estimate_hours=estimate_hours,
        )

    def test_story_size_warning_plain(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        stories = [
            self._story(
                estimate_hours=1,
                acceptance_criteria=["GET /foo returns 200 with a `cursor` field"],
            )
        ]
        _emit_story_warnings(stories, tmp_path)
        err = capsys.readouterr().err
        assert err == f"warning: {lint_story_size(stories)[0]}\n"
        assert "soft decomposition floor" in err

    def test_missing_doc_file_warning_plain(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        f = "docs/missing.md"
        stories = [
            self._story(
                files=[f],
                acceptance_criteria=["GET /foo returns 200 with a `cursor` field"],
            )
        ]
        _emit_story_warnings(stories, tmp_path)
        err = capsys.readouterr().err
        assert err == (
            f"warning: story AUTH-S1 references file `{f}` that doesn't "
            f"exist under repo root `{tmp_path}`\n"
        )

    def test_acceptance_criteria_warnings_plain(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        stories = [self._story(acceptance_criteria=["Code is clean"])]
        _emit_story_warnings(stories, tmp_path)
        err = capsys.readouterr().err
        expected = "".join(
            f"warning: {b}\n" for b in lint_acceptance_criteria(stories)
        )
        assert err == expected

    def test_no_acceptance_criteria_warning_plain(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        stories = [self._story(acceptance_criteria=[])]
        _emit_story_warnings(stories, tmp_path)
        err = capsys.readouterr().err
        assert err == f"warning: {lint_acceptance_criteria(stories)[0]}\n"
        assert "no acceptance criteria" in err

    def test_multiple_warnings_each_prefixed_plain(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        stories = [
            self._story(
                files=["docs/missing.md"],
                acceptance_criteria=["Code is clean", "test_foo passes"],
            )
        ]
        _emit_story_warnings(stories, tmp_path)
        lines = [l for l in capsys.readouterr().err.splitlines() if l]
        assert all(l.startswith("warning: ") for l in lines)
        # The missing-file warning precedes the AC warnings.
        assert "doesn't exist" in lines[0]

    def test_warning_color_prefix_only(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_FORCE_COLOR", "1")
        stories = [self._story(acceptance_criteria=["Code is clean"])]
        _emit_story_warnings(stories, tmp_path)
        lines = [l for l in capsys.readouterr().err.splitlines() if l]
        prefix = style.BOLD_YELLOW + "warning:" + style.RESET + " "
        for line in lines:
            assert line.startswith(prefix)
            body = line[len(prefix) :]
            assert style.RESET not in body
            assert "\033[" not in body


# --- Epic-prefixed story ids ----------------------------------------------


class TestBuildStoryIdRe:
    def test_epic_prefix_required(self) -> None:
        r = build_story_id_re(Epic(key="AUTH", name="Auth"))
        assert r.match("AUTH-S1")
        assert r.match("AUTH-S42")
        assert not r.match("S1")  # missing prefix
        assert not r.match("PAY-S1")  # wrong prefix
        assert not r.match("AUTHS1")  # missing dash
        assert not r.match("AUTH-1")  # missing S


class TestStoryIdPrefix:
    def test_with_epic(self) -> None:
        assert story_id_prefix(Epic(key="AUTH", name="x")) == "AUTH-S"


class TestParseJiraResponseWithEpic:
    def test_accepts_epic_prefixed_ids(self) -> None:
        epic = Epic(key="AUTH", name="Auth")
        stories = parse_jira_response(
            _consolidated_payload("AUTH-"),
            [1, 2],
            epic=epic,
        )
        assert stories is not None
        assert stories[0].id == "AUTH-S1"

    def test_rejects_wrong_prefix(self) -> None:
        epic = Epic(key="AUTH", name="Auth")
        stories = parse_jira_response(
            _consolidated_payload("PAY-"),
            [1, 2],
            epic=epic,
        )
        assert stories is None


class TestCliJiraConfig:
    """End-to-end: ``plan-tool jira config --show`` reports the resolved
    config; ``plan-tool jira <name>`` routes through the epic lookup."""

    def test_show_when_no_config_file(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        rc = cli_module.main(["jira", "config", "--show"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "no jira config" in out

    def test_show_with_config(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.jira_config import (
            JiraConfig,
            default_config_path,
            write_jira_config,
        )

        (tmp_path / ".git").mkdir()
        config_path = default_config_path(tmp_path)
        write_jira_config(
            JiraConfig(
                epics=[Epic(key="AUTH", name="Authentication", jira_epic_id="PROJ-1")],
                plan_assignments={"docs/foo.md": "AUTH"},
            ),
            config_path,
        )
        monkeypatch.chdir(tmp_path)
        rc = cli_module.main(["jira", "config", "--show"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "AUTH" in out
        assert "Authentication" in out
        assert "PROJ-1" in out
        assert "docs/foo.md → AUTH" in out

    def test_show_on_config_already_violating_the_project_key_rule(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A pre-existing config where an epic's key already collides with
        its real JIRA project (valid before this rule existed) must still
        be showable -- and the wizard reachable to fix it -- rather than
        hard-failing every ``jira config`` invocation with no recovery
        path. See ``load_jira_config``'s ``enforce_key_distinct_from_
        jira_project`` and ``cmd_jira_config``."""
        from plan_tool.cli import app as cli_module
        from plan_tool.jira_config import (
            JiraConfig,
            default_config_path,
            write_jira_config,
        )

        (tmp_path / ".git").mkdir()
        config_path = default_config_path(tmp_path)
        write_jira_config(
            JiraConfig(
                epics=[Epic(key="AUTH", name="Auth", jira_epic_id="AUTH-1234")]
            ),
            config_path,
        )
        monkeypatch.chdir(tmp_path)
        rc = cli_module.main(["jira", "config", "--show"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "WARNING" in out
        assert "matches the real JIRA project key" in out
        assert "AUTH" in out

    def test_missing_plan_name_errors(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        rc = cli_module.main(["jira"])
        assert rc == 2
        err = capsys.readouterr().err
        assert "plan name" in err


class TestPlainSummaryPreamble:
    """The PM-facing ``## In plain English`` preamble (``plain_summary``)."""

    def test_markdown_renders_preamble_before_description(self) -> None:
        story = Story(
            id="AUTH-S1",
            title="Add signup",
            description="Technical: wires handleSubmit() to POST /signup.",
            plain_summary="Lets new users create an account.",
            steps=[1],
            estimate_hours=1,
        )
        out = _format_markdown("p", [story], epic=_DEFAULT_EPIC)
        assert "## In plain English\nLets new users create an account." in out
        # Preamble comes before the technical description section.
        assert out.index("## In plain English") < out.index("## Description")

    def test_markdown_empty_summary_renders_sentinel(self) -> None:
        story = Story(id="AUTH-S1", title="x", description="y", steps=[1])
        out = _format_markdown("p", [story], epic=_DEFAULT_EPIC)
        assert "## In plain English\n_(no summary)_" in out

    def test_markdown_round_trips_summary_through_reader(self) -> None:
        story = Story(
            id="AUTH-S1",
            title="x",
            description="y",
            plain_summary="Speeds up the dashboard for everyone.",
            steps=[1],
        )
        out = _format_markdown("p", [story], epic=_DEFAULT_EPIC)
        recovered = _read_markdown_stories_for_lint(out)
        assert recovered[0].plain_summary == "Speeds up the dashboard for everyone."

    def test_markdown_empty_summary_round_trips_empty_not_sentinel(self) -> None:
        story = Story(id="AUTH-S1", title="x", description="y", steps=[1])
        out = _format_markdown("p", [story], epic=_DEFAULT_EPIC)
        recovered = _read_markdown_stories_for_lint(out)
        assert recovered[0].plain_summary == ""

    def test_json_emits_plain_summary(self) -> None:
        story = Story(
            id="AUTH-S1",
            title="x",
            description="y",
            plain_summary="Adds a way to reset a forgotten password.",
            steps=[1],
        )
        out = _format_json("p", [story], epic=_DEFAULT_EPIC)
        s = json.loads(out)["stories"][0]
        assert s["plain_summary"] == "Adds a way to reset a forgotten password."

    def test_json_round_trips_summary_through_reader(self) -> None:
        story = Story(
            id="AUTH-S1",
            title="x",
            description="y",
            plain_summary="Notifies users when their order ships.",
            steps=[1],
        )
        out = _format_json("p", [story], epic=_DEFAULT_EPIC)
        recovered = _read_json_stories_for_lint(out)
        assert recovered[0].plain_summary == "Notifies users when their order ships."

    def test_parse_reads_plain_summary(self) -> None:
        body = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "x",
                    "description": "y",
                    "plain_summary": "  Makes checkout faster.  ",
                    "steps": [1],
                    "estimate_hours": 2,
                }
            ]
        )
        stories = parse_jira_response(body, plan_step_ids=[1], epic=_DEFAULT_EPIC)
        assert stories is not None
        # Stripped on read.
        assert stories[0].plain_summary == "Makes checkout faster."

    def test_parse_defaults_missing_plain_summary_to_empty(self) -> None:
        body = json.dumps(
            [
                {
                    "id": "AUTH-S1",
                    "title": "x",
                    "description": "y",
                    "steps": [1],
                    "estimate_hours": 2,
                }
            ]
        )
        stories = parse_jira_response(body, plan_step_ids=[1], epic=_DEFAULT_EPIC)
        assert stories is not None
        assert stories[0].plain_summary == ""


class TestExportStateVocabulary:
    """The draft/created/dropped handoff model (JIRA_FORMAT.md "Status")."""

    def test_legacy_todo_reads_as_draft(self) -> None:
        assert _resolve_export_state("todo", "") == _EXPORT_STATE_DRAFT

    def test_legacy_done_reads_as_created_not_dropped(self) -> None:
        # ``done`` meant shipped-and-accepted, so the ticket exists in JIRA.
        assert _resolve_export_state("done", "") == _EXPORT_STATE_CREATED

    def test_unknown_and_missing_state_default_to_draft(self) -> None:
        assert _resolve_export_state(None, "") == _EXPORT_STATE_DRAFT
        assert _resolve_export_state("nonsense", "") == _EXPORT_STATE_DRAFT
        assert _resolve_export_state(17, "") == _EXPORT_STATE_DRAFT

    def test_a_recorded_key_promotes_draft_to_created(self) -> None:
        # The operator writes only the key; the state is derived from it.
        assert _resolve_export_state("draft", "PROJ-4412") == _EXPORT_STATE_CREATED

    def test_a_key_never_resurrects_a_dropped_story(self) -> None:
        assert (
            _resolve_export_state("dropped", "PROJ-4412") == _EXPORT_STATE_DROPPED
        )


class TestStoryStateRendering:
    def test_markdown_header_puts_the_human_key_last(self) -> None:
        story = _mk_story(
            "AUTH-S1", [1], export_state="created", jira_issue_key="PROJ-4412"
        )
        text = _format_markdown("P", [story], epic=_DEFAULT_EPIC)
        assert (
            "AUTH-S1 — Plan steps: 1   (estimate: 2h)   "
            "[state: created]   [jira: PROJ-4412]" in text
        )

    def test_markdown_omits_the_key_tag_entirely_when_blank(self) -> None:
        text = _format_markdown("P", [_mk_story("AUTH-S1", [1])], epic=_DEFAULT_EPIC)
        assert "[state: draft]" in text
        assert "[jira:" not in text

    def test_json_emits_the_human_key_as_the_final_field(self) -> None:
        story = _mk_story(
            "AUTH-S1", [1], export_state="created", jira_issue_key="PROJ-4412"
        )
        payload = _story_to_json_dict(story, {})
        assert list(payload)[-1] == "jira_issue_key"
        assert payload["export_state"] == "created"
        assert "status" not in payload

    def test_state_and_key_round_trip_through_markdown(self) -> None:
        story = _mk_story(
            "AUTH-S1", [1], export_state="created", jira_issue_key="PROJ-4412"
        )
        text = _format_markdown("P", [story], epic=_DEFAULT_EPIC)
        recovered = _read_markdown_stories_for_lint(text)[0]
        assert recovered.export_state == _EXPORT_STATE_CREATED
        assert recovered.jira_issue_key == "PROJ-4412"

    def test_legacy_markdown_block_still_parses(self) -> None:
        rule = "=" * 64
        block = (
            f"{rule}\n"
            "AUTH-S1 — Plan steps: 1   (estimate: 1h)   [status: done]\n"
            f"{rule}\n\n"
            "## Title\n[AUTH-S1] Add cache\n\n"
            "## Description\nd\n"
        )
        recovered = _read_markdown_stories_for_lint(block)[0]
        assert recovered.export_state == _EXPORT_STATE_CREATED
        assert recovered.jira_issue_key == ""

    def test_legacy_json_status_key_still_parses(self) -> None:
        text = json.dumps(
            {
                "stories": [
                    {
                        "id": "AUTH-S1",
                        "title": "Add cache",
                        "description": "d",
                        "steps": [1],
                        "estimate_hours": 2,
                        "status": "done",
                    }
                ]
            }
        )
        recovered = _read_json_stories_for_lint(text)[0]
        assert recovered.export_state == _EXPORT_STATE_CREATED


class TestSetMarkdownBlockState:
    def test_replaces_a_legacy_status_tag_in_place(self) -> None:
        block = "AUTH-S1 — Plan steps: 1   (estimate: 2h)   [status: todo]\n## Title\n"
        out = _set_markdown_block_state(block, _EXPORT_STATE_DROPPED)
        assert "[state: dropped]" in out
        assert "[status:" not in out

    def test_never_disturbs_the_hand_written_key(self) -> None:
        block = (
            "AUTH-S1 — Plan steps: 1   (estimate: 2h)   "
            "[state: created]   [jira: PROJ-4412]\n## Title\n"
        )
        out = _set_markdown_block_state(block, _EXPORT_STATE_DROPPED)
        assert "[state: dropped]   [jira: PROJ-4412]" in out

    def test_inserts_the_tag_ahead_of_a_key_when_absent(self) -> None:
        block = (
            "AUTH-S1 — Plan steps: 1   (estimate: 2h)   [jira: PROJ-4412]\n"
            "## Title\n"
        )
        out = _set_markdown_block_state(block, _EXPORT_STATE_DROPPED)
        assert "(estimate: 2h)   [state: dropped]   [jira: PROJ-4412]" in out


class TestHeaderRobustness:
    """A hand-typed header must never cost an operator their tickets."""

    def _block(self, header_extra: str) -> str:
        rule = "=" * 64
        return (
            f"{rule}\n"
            f"AUTH-S1 — Plan steps: 1   (estimate: 2h){header_extra}\n"
            f"{rule}\n\n"
            "## Title\n[AUTH-S1] Add cache\n\n"
            "## Description\nd\n"
        )

    @pytest.mark.parametrize(
        "extra",
        [
            "   [state: created]   [jira: ]",
            "   [state: created]   [jira:]",
            "   [state: created]   [jira: PROJ-1] (mine)",
            "   [state: created] trailing note",
        ],
    )
    def test_malformed_trailing_text_still_parses_the_block(
        self, extra: str
    ) -> None:
        stories = _read_markdown_stories_for_lint(self._block(extra))
        assert [s.id for s in stories] == ["AUTH-S1"]

    def test_a_well_formed_key_is_still_captured(self) -> None:
        stories = _read_markdown_stories_for_lint(
            self._block("   [state: created]   [jira: PROJ-4412]")
        )
        assert stories[0].jira_issue_key == "PROJ-4412"


# A complete run-grade detail body for paired-export fixtures.
_RUN_GRADE_BODY = """# Build the parser

## Summary

Ships the parser.

## Table of Contents

- Summary

## Why

Nothing parses the plan yet.

## Files (creates vs edits)

- `parser.py` — add the class.

## Implementation

Parse the frontmatter, then the body.

## Tests

- Round-trips a two-step plan.

## Acceptance criteria

- The parser imports.
"""


def _seed_existing_md(
    plan_path: Path, stories: list[Story], epic: Epic = _DEFAULT_EPIC
) -> Path:
    target = derive_jira_output_path(plan_path, None, format="markdown")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        _format_markdown("Demo Plan", stories, epic=epic) + "\n",
        encoding="utf-8",
    )
    return target


def _seed_existing_json(
    plan_path: Path, stories: list[Story], epic: Epic = _DEFAULT_EPIC
) -> Path:
    target = derive_jira_output_path(plan_path, None, format="json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        _format_json("Demo Plan", stories, epic=epic) + "\n", encoding="utf-8"
    )
    return target


def _mk_story(sid: str, steps: list[int], **kw: object) -> Story:
    return Story(
        id=sid,
        title=kw.get("title", f"Concept {sid}"),  # type: ignore[arg-type]
        description=kw.get("description", "body"),  # type: ignore[arg-type]
        acceptance_criteria=list(kw.get("acceptance_criteria", ["a check"])),  # type: ignore[arg-type]
        files=list(kw.get("files", [])),  # type: ignore[arg-type]
        steps=steps,
        depends_on=list(kw.get("depends_on", [])),  # type: ignore[arg-type]
        estimate_hours=int(kw.get("estimate_hours", 2)),  # type: ignore[arg-type]
        export_state=str(kw.get("export_state", "draft")),
        jira_issue_key=str(kw.get("jira_issue_key", "")),
    )


# --- capture_companion_export_input ----------------------------------------


# A single committed, `done` step with no files or detail — the minimal
# fixture that satisfies companion capture without any detail-file
# infrastructure, for tests focused on something other than detail capture.
_COMPANION_MINIMAL_PLAN = """---
title: Companion Plan
status: in-progress
priority: medium
steps:
  - id: 1
    title: Ship the thing
    status: done
---

# Companion Plan

Original body prose.
"""

# Missing Table of Contents, Files, Implementation, Tests, and Acceptance
# criteria — a run-grade detail body that fails the structural check.
_COMPANION_MALFORMED_RUN_DETAIL = """# Step

## Summary

Ships the thing.

## Why

Nothing does this yet.
"""


def _write_companion_plan(tmp_path: Path, body: str = _COMPANION_MINIMAL_PLAN) -> Path:
    plan_path = tmp_path / "1-companion.md"
    plan_path.write_text(body, encoding="utf-8")
    return plan_path


def _companion_handoff_target(tmp_path: Path, name: str = "handoff.md") -> Path:
    return tmp_path / "jira-handoffs" / "companion" / name


_COMPANION_MULTI_STEP_PLAN = """---
title: Companion Plan
status: in-progress
priority: medium
steps:
  - id: 1
    title: Ship the thing
    status: done
  - id: 2
    title: Build the widget
    intent: Deliver the requested widget behavior.
    status: current
    detail: plan-details/companion/02-widget.md
  - id: 3
    title: Wire the renderer
    intent: Connect the widget to its rendered output.
    status: pending
    detail: plan-details/companion/03-renderer.md
  - id: 4
    title: Explore alt parser
    scope: deferred
    status_note: waiting on vendor API
  - id: 5
    title: Old approach
    scope: wont_do
    status_note: replaced by step 1
---

# Companion Plan
"""


def _write_companion_multi_step_plan(tmp_path: Path) -> Path:
    plan_path = tmp_path / "1-companion.md"
    plan_path.write_text(_COMPANION_MULTI_STEP_PLAN, encoding="utf-8")
    for name in ("02-widget.md", "03-renderer.md"):
        detail_path = tmp_path / "plan-details" / "companion" / name
        detail_path.parent.mkdir(parents=True, exist_ok=True)
        detail_path.write_text(_RUN_GRADE_BODY, encoding="utf-8")
    return plan_path


def _companion_response(entries: list[dict]) -> str:
    payload = [
        {
            "id": entry["id"],
            "title": entry.get("title", f"Story {entry['id']}"),
            "description": entry.get("description", "body"),
            "acceptance_criteria": entry.get("acceptance_criteria", ["a check"]),
            "files": entry.get("files", []),
            "steps": entry["steps"],
            "depends_on": entry.get("depends_on", []),
            "estimate_hours": entry.get("estimate_hours", 2),
        }
        for entry in entries
    ]
    return json.dumps(payload)


def _seed_companion_existing_md(
    plan_path: Path,
    stories: list[Story],
    *,
    source_plan_path: str,
    epic: Epic = _DEFAULT_EPIC,
) -> Path:
    target = derive_jira_output_path(plan_path, None, format="markdown")
    target.parent.mkdir(parents=True, exist_ok=True)
    text = _render_story_markdown(
        _StoryRenderInput(
            plan_title="Companion Plan",
            epic=epic,
            new_stories=stories,
            source_plan_path=source_plan_path,
        )
    )
    provenance = CompanionProvenance(
        provenance_format_revision=PROVENANCE_FORMAT_REVISION,
        generation_mode="jira-companion",
        selected_grade="run",
        source_plan_path=source_plan_path,
        selected_detail_source_paths=(),
        pair_identity=GeneratedSourcePairIdentity(
            story_path=target.relative_to(plan_path.parent).as_posix(),
            handoff_path="jira-handoffs/companion/handoff.md",
            format="markdown",
        ),
        story_prompt_contract_revision=1,
        handoff_format_contract_revision=1,
        fingerprint="test-fingerprint",
    )
    target.write_text(
        text + "\n\n" + write_markdown_provenance(provenance) + "\n",
        encoding="utf-8",
    )
    return target


class TestCaptureCompanionExportInput:
    def test_companion_capture_preserves_plan_body_details_and_excerpts_after_source_changes(
        self, tmp_path: Path
    ) -> None:
        plan_path = tmp_path / "1-companion.md"
        plan_path.write_text(
            "---\n"
            "title: Companion Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Build the widget\n"
            "    files:\n"
            "      - widget.py\n"
            "    detail: plan-details/companion/detail.md\n"
            "    status: current\n"
            "---\n\n"
            "# Companion Plan\n\n"
            "Original body prose.\n",
            encoding="utf-8",
        )
        (tmp_path / "widget.py").write_text(
            "ORIGINAL_SOURCE_MARKER\n", encoding="utf-8"
        )
        detail_path = tmp_path / "plan-details" / "companion" / "detail.md"
        detail_path.parent.mkdir(parents=True, exist_ok=True)
        detail_path.write_text(
            _RUN_GRADE_BODY.replace(
                "Nothing parses the plan yet.", "ORIGINAL_DETAIL_MARKER"
            ),
            encoding="utf-8",
        )

        capture = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=derive_jira_output_path(
                plan_path, None, format="markdown"
            ),
            handoff_output_path=_companion_handoff_target(tmp_path),
        )

        # Mutate every source this snapshot could have re-read.
        plan_path.write_text(
            plan_path.read_text(encoding="utf-8").replace(
                "Build the widget", "CHANGED TITLE"
            ),
            encoding="utf-8",
        )
        (tmp_path / "widget.py").write_text(
            "CHANGED_SOURCE_MARKER\n", encoding="utf-8"
        )
        detail_path.write_text(
            _RUN_GRADE_BODY.replace(
                "Nothing parses the plan yet.", "CHANGED_DETAIL_MARKER"
            ),
            encoding="utf-8",
        )

        assert "Build the widget" in capture.frontmatter_text
        assert capture.plan.step_by_id(1).title == "Build the widget"
        assert capture.committed_steps[0].detail.state == _DETAIL_STATE_PRESENT
        assert "ORIGINAL_DETAIL_MARKER" in capture.committed_steps[0].detail.text
        assert "CHANGED_DETAIL_MARKER" not in capture.committed_steps[0].detail.text
        excerpt = capture.committed_steps[0].file_excerpts[0].excerpt
        assert "ORIGINAL_SOURCE_MARKER" in excerpt.text
        assert "CHANGED_SOURCE_MARKER" not in excerpt.text

    def test_companion_capture_records_complete_generated_source_pair_identity(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_plan(tmp_path)
        story_target = derive_jira_output_path(plan_path, None, format="markdown")
        handoff_target = _companion_handoff_target(tmp_path)
        other_handoff_target = _companion_handoff_target(tmp_path, "other.md")

        capture_a = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=story_target,
            handoff_output_path=handoff_target,
        )
        capture_b = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=story_target,
            handoff_output_path=handoff_target,
        )
        capture_c = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=story_target,
            handoff_output_path=other_handoff_target,
        )

        assert capture_a.pair_identity == capture_b.pair_identity
        assert capture_a.pair_identity != capture_c.pair_identity
        assert capture_a.pair_identity.format == capture_a.settings.format == "markdown"

    def test_companion_capture_reports_every_broken_committed_detail(self, tmp_path: Path) -> None:
        plan_path = _write_companion_multi_step_plan(tmp_path)
        (tmp_path / "plan-details" / "companion" / "02-widget.md").unlink()
        (tmp_path / "plan-details" / "companion" / "03-renderer.md").unlink()

        with pytest.raises(JiraError) as excinfo:
            capture_companion_export_input(
                plan_path,
                repo_root=tmp_path,
                epic=_DEFAULT_EPIC,
                story_output_path=derive_jira_output_path(
                    plan_path, None, format="markdown"
                ),
                handoff_output_path=_companion_handoff_target(tmp_path),
            )

        message = str(excinfo.value)
        assert "could not ground 2 committed steps" in message
        assert "step 2 (Build the widget)" in message
        assert "step 3 (Wire the renderer)" in message

    def test_default_handoff_path_is_an_orchestrator_convention(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "1-demo.md"
        story_path = tmp_path / "out" / "release.v1.json"

        assert derive_default_handoff_output_path(story_path, plan_path) == (
            tmp_path / "jira-handoffs" / "demo" / "release.v1.developer-handoff.md"
        )

    def test_companion_capture_selects_only_committed_steps_and_records_parked_history(
        self, tmp_path: Path
    ) -> None:
        plan_path = tmp_path / "1-companion.md"
        plan_path.write_text(
            "---\n"
            "title: Companion Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Ship the thing\n"
            "    status: done\n"
            "  - id: 2\n"
            "    title: Explore alternate parser\n"
            "    scope: deferred\n"
            "    status_note: waiting on vendor API\n"
            "  - id: 3\n"
            "    title: Old approach\n"
            "    scope: wont_do\n"
            "    status_note: replaced by step 1\n"
            "---\n\n# Companion Plan\n",
            encoding="utf-8",
        )
        capture = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=derive_jira_output_path(
                plan_path, None, format="markdown"
            ),
            handoff_output_path=_companion_handoff_target(tmp_path),
        )

        assert [s.id for s in capture.committed_steps] == [1]
        by_id = {p.id: p for p in capture.parked_step_history}
        assert set(by_id) == {2, 3}
        assert by_id[2].scope == StepScope.DEFERRED
        assert by_id[2].status_note == "waiting on vendor API"
        assert by_id[3].scope == StepScope.WONT_DO
        assert by_id[3].status_note == "replaced by step 1"

    def test_companion_capture_requires_selected_detail_for_each_committed_non_done_step(
        self, tmp_path: Path
    ) -> None:
        plan_path = tmp_path / "1-companion.md"
        plan_path.write_text(
            "---\n"
            "title: Companion Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Ship the thing\n"
            "    status: current\n"
            "---\n\n# Companion Plan\n",
            encoding="utf-8",
        )
        with pytest.raises(JiraError):
            capture_companion_export_input(
                plan_path,
                repo_root=tmp_path,
                epic=_DEFAULT_EPIC,
                story_output_path=derive_jira_output_path(
                    plan_path, None, format="markdown"
                ),
                handoff_output_path=_companion_handoff_target(tmp_path),
            )

    def test_companion_capture_records_done_step_without_detail_for_historical_fallback(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_plan(tmp_path)
        capture = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=derive_jira_output_path(
                plan_path, None, format="markdown"
            ),
            handoff_output_path=_companion_handoff_target(tmp_path),
        )
        assert capture.committed_steps[0].detail.state == _DETAIL_STATE_MISSING
        assert capture.committed_steps[0].detail.text is None
        assert capture.committed_steps[0].detail.path is None

    def test_companion_capture_exempts_a_done_step_with_a_dangling_detail_pointer(
        self, tmp_path: Path
    ) -> None:
        # A run-grade step.detail pointer to a file that has since been
        # deleted or moved is functionally "no detail" from the caller's
        # done/non-done rule's perspective -- _capture_jira_grade_step_detail
        # already treats its own equivalent "not on disk" case as
        # _DETAIL_STATE_MISSING precisely so a done step is exempted; the
        # run-grade path must match instead of hard-rejecting the whole
        # export regardless of status.
        plan_path = tmp_path / "1-companion.md"
        plan_path.write_text(
            "---\n"
            "title: Companion Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Ship the thing\n"
            "    status: done\n"
            "    detail: plan-details/companion/01-thing.md\n"
            "---\n\n# Companion Plan\n",
            encoding="utf-8",
        )

        capture = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=derive_jira_output_path(
                plan_path, None, format="markdown"
            ),
            handoff_output_path=_companion_handoff_target(tmp_path),
        )
        assert capture.committed_steps[0].detail.state == _DETAIL_STATE_MISSING

    def test_companion_capture_still_rejects_a_non_done_step_with_a_dangling_detail_pointer(
        self, tmp_path: Path
    ) -> None:
        # The done-step exemption above must not broaden to a non-done
        # step: _capture_run_grade_step_detail now returns
        # _DETAIL_STATE_MISSING for a dangling pointer instead of raising
        # directly, but the caller's non-done/done rule must still reject
        # it -- just via that shared check instead of a capture-local one.
        plan_path = tmp_path / "1-companion.md"
        plan_path.write_text(
            "---\n"
            "title: Companion Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Ship the thing\n"
            "    status: current\n"
            "    detail: plan-details/companion/01-thing.md\n"
            "---\n\n# Companion Plan\n",
            encoding="utf-8",
        )

        with pytest.raises(JiraError):
            capture_companion_export_input(
                plan_path,
                repo_root=tmp_path,
                epic=_DEFAULT_EPIC,
                story_output_path=derive_jira_output_path(
                    plan_path, None, format="markdown"
                ),
                handoff_output_path=_companion_handoff_target(tmp_path),
            )

    def test_companion_capture_rejects_malformed_present_done_detail(
        self, tmp_path: Path
    ) -> None:
        plan_path = tmp_path / "1-companion.md"
        plan_path.write_text(
            "---\n"
            "title: Companion Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Ship the thing\n"
            "    status: done\n"
            "    detail: plan-details/companion/detail.md\n"
            "---\n\n# Companion Plan\n",
            encoding="utf-8",
        )
        detail_path = tmp_path / "plan-details" / "companion" / "detail.md"
        detail_path.parent.mkdir(parents=True, exist_ok=True)
        detail_path.write_text(_COMPANION_MALFORMED_RUN_DETAIL, encoding="utf-8")

        with pytest.raises(JiraError):
            capture_companion_export_input(
                plan_path,
                repo_root=tmp_path,
                epic=_DEFAULT_EPIC,
                story_output_path=derive_jira_output_path(
                    plan_path, None, format="markdown"
                ),
                handoff_output_path=_companion_handoff_target(tmp_path),
            )

    def test_companion_capture_reports_non_utf8_selected_detail_as_jira_error(
        self, tmp_path: Path
    ) -> None:
        plan_path = tmp_path / "1-companion.md"
        plan_path.write_text(
            "---\n"
            "title: Companion Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Ship the thing\n"
            "    status: done\n"
            "    detail: plan-details/companion/detail.md\n"
            "---\n\n# Companion Plan\n",
            encoding="utf-8",
        )
        detail_path = tmp_path / "plan-details" / "companion" / "detail.md"
        detail_path.parent.mkdir(parents=True, exist_ok=True)
        detail_path.write_bytes(b"\xff\xfe")

        with pytest.raises(JiraError, match="could not be read"):
            capture_companion_export_input(
                plan_path,
                repo_root=tmp_path,
                epic=_DEFAULT_EPIC,
                story_output_path=derive_jira_output_path(
                    plan_path, None, format="markdown"
                ),
                handoff_output_path=_companion_handoff_target(tmp_path),
            )

    def test_companion_capture_ignores_missing_or_malformed_parked_detail(
        self, tmp_path: Path
    ) -> None:
        plan_path = tmp_path / "1-companion.md"
        plan_path.write_text(
            "---\n"
            "title: Companion Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Ship the thing\n"
            "    status: done\n"
            "  - id: 2\n"
            "    title: Parked idea\n"
            "    scope: deferred\n"
            "    detail: plan-details/companion/bad.md\n"
            "---\n\n# Companion Plan\n",
            encoding="utf-8",
        )
        # No file at all is written to plan-details/companion/bad.md — a
        # committed step in this state would be rejected; a parked one must
        # not even be checked.

        capture = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=derive_jira_output_path(
                plan_path, None, format="markdown"
            ),
            handoff_output_path=_companion_handoff_target(tmp_path),
        )

        assert [s.id for s in capture.committed_steps] == [1]
        assert capture.parked_step_history[0].id == 2

    def test_companion_capture_keeps_jira_grade_selection_without_run_grade_fallback(
        self, tmp_path: Path
    ) -> None:
        plan_path = tmp_path / "1-companion.md"
        plan_path.write_text(
            "---\n"
            "title: Companion Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Ship the thing\n"
            "    status: done\n"
            "    detail: plan-details/companion/run.md\n"
            "---\n\n# Companion Plan\n",
            encoding="utf-8",
        )
        run_detail = tmp_path / "plan-details" / "companion" / "run.md"
        run_detail.parent.mkdir(parents=True, exist_ok=True)
        run_detail.write_text(_RUN_GRADE_BODY, encoding="utf-8")
        # Deliberately no jira-grade artifact at
        # plan-details/companion/jira/01-ship-the-thing.md.

        capture = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=derive_jira_output_path(
                plan_path, None, format="markdown"
            ),
            handoff_output_path=_companion_handoff_target(tmp_path),
            grade="jira",
        )

        assert capture.committed_steps[0].detail.state == _DETAIL_STATE_MISSING
        assert capture.committed_steps[0].detail.text is None

    def test_companion_capture_preserves_existing_ticket_state_and_key_ownership(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_plan(tmp_path)
        story = _mk_story("AUTH-S1", [1], export_state="draft", jira_issue_key="PROJ-1")
        target = _seed_existing_md(plan_path, [story])

        capture = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=target,
            handoff_output_path=_companion_handoff_target(tmp_path),
        )

        existing = capture.existing_story_source.existing
        assert existing is not None
        ticket = existing.tickets[0]
        assert ticket.id == "AUTH-S1"
        assert ticket.jira_issue_key == "PROJ-1"
        # A keyed draft is promoted to created purely from recording the
        # key — see _resolve_export_state.
        assert ticket.export_state == _EXPORT_STATE_CREATED
        assert existing.covered_current_steps({1}) == {1}

    def test_companion_capture_parses_the_existing_story_source_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = _write_companion_plan(tmp_path)
        target = _seed_existing_md(plan_path, [_mk_story("AUTH-S1", [1])])
        original_read_text = Path.read_text
        calls = 0

        def read_once(path: Path, *args: object, **kwargs: object) -> str:
            nonlocal calls
            if path == target:
                calls += 1
                if calls > 1:
                    raise OSError("changed after capture")
            return original_read_text(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", read_once)

        capture = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=target,
            handoff_output_path=_companion_handoff_target(tmp_path),
        )

        assert calls == 1
        assert capture.existing_story_source.existing is not None

    def test_companion_capture_preserves_complete_existing_record_representation(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_plan(tmp_path)
        stories = [
            _mk_story(
                "AUTH-S1",
                [1],
                export_state="created",
                jira_issue_key="PROJ-9",
                title="Ship it",
                description="Full description body",
                files=["widget.py"],
            ),
        ]
        target = _seed_existing_json(plan_path, stories)

        capture = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=target,
            handoff_output_path=_companion_handoff_target(tmp_path),
            format="json",
        )

        ticket = capture.existing_story_source.existing.tickets[0]
        assert ticket.raw_json is not None
        assert ticket.raw_json["description"] == "Full description body"
        assert ticket.raw_json["files"] == ["widget.py"]
        assert ticket.steps == [1]
        assert ticket.jira_issue_key == "PROJ-9"
        assert ticket.export_state == _EXPORT_STATE_CREATED

    def test_companion_capture_records_raw_target_content_state_proofs(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_plan(tmp_path)
        story_target = derive_jira_output_path(plan_path, None, format="markdown")
        story_target.parent.mkdir(parents=True, exist_ok=True)
        story_target.write_text("some existing bytes\n", encoding="utf-8")
        handoff_target = _companion_handoff_target(tmp_path)

        capture = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=story_target,
            handoff_output_path=handoff_target,
        )

        expected_digest = hashlib.sha256(b"some existing bytes\n").hexdigest()
        assert capture.target_preflight.story_target.exists is True
        assert capture.target_preflight.story_target.sha256 == expected_digest
        assert capture.target_preflight.handoff_target.exists is False
        assert capture.target_preflight.handoff_target.sha256 is None

    def test_companion_target_preflight_rejects_any_grade_detail_before_rendering(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        colliding_run_path = derive_detail_path(plan_path, plan, step)
        colliding_jira_path = derive_jira_detail_path(plan_path, plan, step)
        handoff_target = _companion_handoff_target(tmp_path)

        with pytest.raises(JiraError):
            capture_companion_export_input(
                plan_path,
                repo_root=tmp_path,
                epic=_DEFAULT_EPIC,
                story_output_path=colliding_run_path,
                handoff_output_path=handoff_target,
            )

        with pytest.raises(JiraError):
            capture_companion_export_input(
                plan_path,
                repo_root=tmp_path,
                epic=_DEFAULT_EPIC,
                story_output_path=derive_jira_output_path(
                    plan_path, None, format="markdown"
                ),
                # A jira-grade artifact path, even though this call uses the
                # (default) run grade — collision is checked across both
                # grades regardless of which one is selected.
                handoff_output_path=colliding_jira_path,
            )

    def test_target_preflight_is_not_a_handoff_render_input(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.jira import _build_handoff_render_input
        from plan_tool.jira_handoff import render_handoff_body

        plan_path = _write_companion_plan(tmp_path)
        story_target = derive_jira_output_path(plan_path, None, format="markdown")
        handoff_target = _companion_handoff_target(tmp_path)

        capture_before = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=story_target,
            handoff_output_path=handoff_target,
        )
        body_before = render_handoff_body(
            _build_handoff_render_input(capture_before, repo_root=tmp_path)
        )

        # Publishing a predecessor at the handoff target changes only the
        # final-write ownership proof, not the handoff's captured content.
        handoff_target.parent.mkdir(parents=True, exist_ok=True)
        handoff_target.write_text("a previously published handoff\n", encoding="utf-8")

        capture_after = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=story_target,
            handoff_output_path=handoff_target,
        )

        assert capture_before.target_preflight != capture_after.target_preflight
        assert body_before == render_handoff_body(
            _build_handoff_render_input(capture_after, repo_root=tmp_path)
        )


class TestCaptureStepDetailFormatVersion:
    """The run-grade capture's format-version check sits alongside its
    sibling ``OSError``/fence/missing-section ``JiraError`` raises; the
    jira-grade capture is a different artifact class and stays unaffected."""

    def test_run_grade_export_refuses_an_unsupported_detail_marker(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.detail_artifacts import render_detail_format_version_marker
        from plan_tool.jira import _capture_run_grade_step_detail

        detail_path = tmp_path / "detail.md"
        detail_path.write_text(
            _RUN_GRADE_BODY.replace(
                "# Build the parser",
                f"# Build the parser\n{render_detail_format_version_marker(999)}",
                1,
            ),
            encoding="utf-8",
        )
        step = Step(id=1, title="Build the parser", detail="detail.md")

        with pytest.raises(JiraError, match="999"):
            _capture_run_grade_step_detail(step, tmp_path)

    def test_jira_grade_export_ignores_the_run_grade_marker(
        self, tmp_path: Path
    ) -> None:
        """Negative control: ``_capture_jira_grade_step_detail`` is a
        different artifact class and is unaffected by this change."""
        from plan_tool.jira import _capture_jira_grade_step_detail

        plan_path = tmp_path / "1-demo.md"
        plan_path.write_text(
            "---\n"
            "title: Demo\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Build the parser\n"
            "    status: current\n"
            "---\n\n# Demo\n",
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        jira_path = derive_jira_detail_path(plan_path, plan, step)
        jira_path.parent.mkdir(parents=True, exist_ok=True)
        jira_path.write_text(
            "## Intent\n\nShip the parser.\n\n"
            "## Change\n\nAdd the parser class.\n\n"
            "## Constraints\n\nNo public API change.\n\n"
            "## Done when\n\nThe parser imports.\n\n"
            "## Out of scope\n\nThe renderer.\n",
            encoding="utf-8",
        )

        result = _capture_jira_grade_step_detail(plan_path, plan, step, tmp_path)
        assert result.state == _DETAIL_STATE_PRESENT


class TestRegenerateCompanionStories:
    def test_companion_regeneration_uses_the_captured_snapshot_after_live_inputs_change(
        self, tmp_path: Path
    ) -> None:
        plan_path = tmp_path / "1-companion.md"
        plan_path.write_text(
            "---\n"
            "title: Companion Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Build the widget\n"
            "    files:\n"
            "      - widget.py\n"
            "    detail: plan-details/companion/detail.md\n"
            "    status: current\n"
            "---\n\n"
            "# Companion Plan\n",
            encoding="utf-8",
        )
        (tmp_path / "widget.py").write_text(
            "ORIGINAL_SOURCE_MARKER\n", encoding="utf-8"
        )
        detail_path = tmp_path / "plan-details" / "companion" / "detail.md"
        detail_path.parent.mkdir(parents=True, exist_ok=True)
        detail_path.write_text(
            _RUN_GRADE_BODY.replace(
                "Nothing parses the plan yet.", "ORIGINAL_DETAIL_MARKER"
            ),
            encoding="utf-8",
        )

        capture = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=derive_jira_output_path(
                plan_path, None, format="markdown"
            ),
            handoff_output_path=_companion_handoff_target(tmp_path),
        )

        # Mutate every source this regeneration could re-read.
        plan_path.write_text(
            plan_path.read_text(encoding="utf-8").replace(
                "Build the widget", "CHANGED TITLE"
            ),
            encoding="utf-8",
        )
        (tmp_path / "widget.py").write_text(
            "CHANGED_SOURCE_MARKER\n", encoding="utf-8"
        )
        detail_path.write_text(
            _RUN_GRADE_BODY.replace(
                "Nothing parses the plan yet.", "CHANGED_DETAIL_MARKER"
            ),
            encoding="utf-8",
        )

        prompt = render_companion_export_prompt(capture)
        assert "ORIGINAL_DETAIL_MARKER" in prompt
        assert "CHANGED_DETAIL_MARKER" not in prompt
        assert "ORIGINAL_SOURCE_MARKER" in prompt
        assert "CHANGED_SOURCE_MARKER" not in prompt
        assert "Build the widget" in prompt
        assert "CHANGED TITLE" not in prompt

        export = regenerate_companion_stories(
            capture,
            _companion_response([{"id": "AUTH-S1", "steps": [1]}]),
            repo_root=tmp_path,
        )
        assert "Companion Plan" in export.output

    def test_prompt_truncates_detail_by_utf8_bytes_not_characters(
        self, tmp_path: Path
    ) -> None:
        # Multi-byte UTF-8 characters (e.g. em dashes) make a text's byte
        # length exceed its character length; truncating by character count
        # alone silently lets the rendered prompt exceed the caller's byte
        # budget for detail text containing them.
        plan_path = tmp_path / "1-companion.md"
        plan_path.write_text(
            "---\n"
            "title: Companion Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Build the widget\n"
            "    detail: plan-details/companion/detail.md\n"
            "    status: current\n"
            "---\n\n"
            "# Companion Plan\n",
            encoding="utf-8",
        )
        detail_path = tmp_path / "plan-details" / "companion" / "detail.md"
        detail_path.parent.mkdir(parents=True, exist_ok=True)
        detail_body = _RUN_GRADE_BODY + ("—" * 200)
        detail_path.write_text(detail_body, encoding="utf-8")
        char_len = len(detail_body)
        byte_len = len(detail_body.encode("utf-8"))
        assert char_len < byte_len, "fixture must contain multi-byte characters"
        budget = (char_len + byte_len) // 2

        capture = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=derive_jira_output_path(
                plan_path, None, format="markdown"
            ),
            handoff_output_path=_companion_handoff_target(tmp_path),
        )
        prompt = render_companion_export_prompt(capture, max_file_bytes=budget)

        marker = "_from `plan-details/companion/detail.md`:_\n\n"
        detail_section = prompt.split(marker, 1)[1]
        snippet = detail_section.split("\n\n**Current file contents:**", 1)[0]
        assert len(snippet.encode("utf-8")) <= budget

    def test_companion_regeneration_covers_only_committed_steps_and_marks_done_status(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_multi_step_plan(tmp_path)
        capture = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=derive_jira_output_path(
                plan_path, None, format="markdown"
            ),
            handoff_output_path=_companion_handoff_target(tmp_path),
        )
        prompt = render_companion_export_prompt(capture)
        assert "Explore alt parser" not in prompt
        assert "Old approach" not in prompt

        export = regenerate_companion_stories(
            capture,
            _companion_response(
                [
                    {"id": "AUTH-S1", "steps": [1]},
                    {"id": "AUTH-S2", "steps": [2, 3]},
                ]
            ),
            repo_root=tmp_path,
        )
        assert {s.id for s in export.stories} == {"AUTH-S1", "AUTH-S2"}
        assert all(4 not in s.steps and 5 not in s.steps for s in export.stories)
        assert "- Step 1 (done)" in export.output
        assert "- Step 2 (current)" in export.output
        assert "- Step 3 (pending)" in export.output
        assert (
            export.output.count(
                "_(historical — every covered step is already done)_"
            )
            == 1
        )

    def test_companion_regeneration_replaces_live_story_content_instead_of_appending_it(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_plan(tmp_path)
        _seed_existing_md(
            plan_path,
            [
                _mk_story(
                    "AUTH-S1",
                    [1],
                    title="Old title",
                    description="Old description",
                )
            ],
        )
        capture = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=derive_jira_output_path(
                plan_path, None, format="markdown"
            ),
            handoff_output_path=_companion_handoff_target(tmp_path),
        )

        export = regenerate_companion_stories(
            capture,
            _companion_response(
                [
                    {
                        "id": "AUTH-S2",
                        "steps": [1],
                        "title": "New title",
                        "description": "New description",
                    }
                ]
            ),
            repo_root=tmp_path,
        )
        assert "New title" in export.output
        assert "New description" in export.output
        assert "Old title" not in export.output
        assert "Old description" not in export.output

    def test_companion_regeneration_promotes_keyed_draft_before_matching(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_plan(tmp_path)
        _seed_companion_existing_md(
            plan_path,
            [_mk_story("AUTH-S1", [1], export_state="draft", jira_issue_key="PROJ-1")],
            source_plan_path="1-companion.md",
        )
        capture = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=derive_jira_output_path(
                plan_path, None, format="markdown"
            ),
            handoff_output_path=_companion_handoff_target(tmp_path),
        )

        export = regenerate_companion_stories(
            capture,
            _companion_response([{"id": "AUTH-S2", "steps": [1]}]),
            repo_root=tmp_path,
        )
        assert len(export.stories) == 1
        assert export.stories[0].export_state == "created"
        assert export.stories[0].jira_issue_key == "PROJ-1"

    def test_companion_regeneration_preserves_created_key_and_reports_changed_ticket(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_plan(tmp_path)
        _seed_companion_existing_md(
            plan_path,
            [
                _mk_story(
                    "AUTH-S1",
                    [1],
                    export_state="created",
                    jira_issue_key="PROJ-9",
                    title="Old title",
                )
            ],
            source_plan_path="1-companion.md",
        )
        capture = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=derive_jira_output_path(
                plan_path, None, format="markdown"
            ),
            handoff_output_path=_companion_handoff_target(tmp_path),
        )

        export = regenerate_companion_stories(
            capture,
            _companion_response(
                [{"id": "AUTH-S2", "steps": [1], "title": "New title"}]
            ),
            repo_root=tmp_path,
        )
        assert export.stories[0].jira_issue_key == "PROJ-9"
        assert export.stories[0].export_state == "created"
        assert export.changed_created_tickets == [
            CompanionCreatedTicketNotice(story_id="AUTH-S2", jira_issue_key="PROJ-9")
        ]

    def test_companion_regeneration_uses_embedded_provenance_not_story_header(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_plan(tmp_path)
        target = _seed_companion_existing_md(
            plan_path,
            [
                _mk_story(
                    "AUTH-S1", [1], export_state="created", jira_issue_key="PROJ-9"
                )
            ],
            source_plan_path="1-companion.md",
        )
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                "_Source plan: `1-companion.md`_",
                "_Source plan: `9-other-plan.md`_",
            ),
            encoding="utf-8",
        )
        capture = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=target,
            handoff_output_path=_companion_handoff_target(tmp_path),
        )

        export = regenerate_companion_stories(
            capture,
            _companion_response([{"id": "AUTH-S2", "steps": [1]}]),
            repo_root=tmp_path,
        )

        assert export.stories[0].jira_issue_key == "PROJ-9"

    def test_companion_regeneration_rejects_a_keyed_source_from_another_pair(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_plan(tmp_path)
        target = _seed_companion_existing_md(
            plan_path,
            [
                _mk_story(
                    "AUTH-S1", [1], export_state="created", jira_issue_key="PROJ-9"
                )
            ],
            source_plan_path="1-companion.md",
        )
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                "pair_identity_handoff_path: jira-handoffs/companion/handoff.md",
                "pair_identity_handoff_path: jira-handoffs/companion/other.md",
            ),
            encoding="utf-8",
        )
        capture = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=target,
            handoff_output_path=_companion_handoff_target(tmp_path),
        )

        with pytest.raises(JiraError, match="foreign source"):
            regenerate_companion_stories(
                capture,
                _companion_response([{"id": "AUTH-S2", "steps": [1]}]),
                repo_root=tmp_path,
            )

    def test_companion_regeneration_carries_the_key_forward_after_a_plan_renumber(
        self, tmp_path: Path
    ) -> None:
        # A real prior companion run stamps source_plan_path="1-companion.md".
        # The plan is then renumbered to 2-companion.md -- its priority
        # prefix changed, but its slug ("companion") and generated
        # destinations are unchanged. Same-plan ownership must still
        # recognize its own prior output and carry the key forward.
        plan_path = _write_companion_plan(tmp_path)
        story_target, handoff_target = derive_jira_output_path(
            plan_path, None, format="markdown"
        ), _companion_handoff_target(tmp_path)
        export_jira(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=story_target,
            handoff_output_path=handoff_target,
            invoker=lambda prompt: _companion_response(
                [{"id": "AUTH-S1", "steps": [1]}]
            ),
        )
        text = story_target.read_text(encoding="utf-8")
        story_target.write_text(
            text.replace("[state: draft]", "[state: created]   [jira: PROJ-9]"),
            encoding="utf-8",
        )

        renumbered_plan_path = plan_path.parent / "2-companion.md"
        plan_path.rename(renumbered_plan_path)
        capture = capture_companion_export_input(
            renumbered_plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=story_target,
            handoff_output_path=handoff_target,
        )

        export = regenerate_companion_stories(
            capture,
            _companion_response([{"id": "AUTH-S2", "steps": [1]}]),
            repo_root=tmp_path,
        )
        assert export.stories[0].jira_issue_key == "PROJ-9"

    def test_companion_regeneration_keeps_parked_or_dropped_record_as_story_history_only(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_multi_step_plan(tmp_path)
        _seed_existing_md(
            plan_path,
            [
                # Already dropped, and its only covered step is parked.
                _mk_story("AUTH-S1", [4], export_state="dropped"),
                # Not dropped, but every covered step is parked — no key,
                # so this normalizes to history with no lifecycle notice.
                _mk_story("AUTH-S2", [5], export_state="draft"),
            ],
        )
        capture = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=derive_jira_output_path(
                plan_path, None, format="markdown"
            ),
            handoff_output_path=_companion_handoff_target(tmp_path),
        )

        export = regenerate_companion_stories(
            capture,
            _companion_response(
                [
                    {"id": "AUTH-S3", "steps": [1]},
                    {"id": "AUTH-S4", "steps": [2, 3]},
                ]
            ),
            repo_root=tmp_path,
        )
        assert {t.id for t in export.dropped_history} == {"AUTH-S1", "AUTH-S2"}
        assert export.created_to_dropped == []
        assert all(4 not in s.steps and 5 not in s.steps for s in export.stories)
        assert "AUTH-S1" in export.output
        assert "AUTH-S2" in export.output

    def test_companion_regeneration_rejects_dropped_or_mixed_record_covering_a_committed_step(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_multi_step_plan(tmp_path)

        # A dropped record still naming a committed step.
        _seed_existing_md(plan_path, [_mk_story("AUTH-S1", [1], export_state="dropped")])
        capture_a = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=derive_jira_output_path(
                plan_path, None, format="markdown"
            ),
            handoff_output_path=_companion_handoff_target(tmp_path),
        )
        with pytest.raises(JiraError):
            regenerate_companion_stories(
                capture_a,
                _companion_response([{"id": "AUTH-S2", "steps": [1, 2, 3]}]),
                repo_root=tmp_path,
            )

        # A non-dropped record mixing committed (1) and parked (4) coverage.
        target = derive_jira_output_path(plan_path, None, format="markdown")
        target.write_text(
            _format_markdown(
                "Companion Plan",
                [_mk_story("AUTH-S3", [1, 4], export_state="draft")],
                epic=_DEFAULT_EPIC,
            )
            + "\n",
            encoding="utf-8",
        )
        capture_b = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=target,
            handoff_output_path=_companion_handoff_target(tmp_path),
        )
        with pytest.raises(JiraError):
            regenerate_companion_stories(
                capture_b,
                _companion_response([{"id": "AUTH-S4", "steps": [1, 2, 3]}]),
                repo_root=tmp_path,
            )

    def test_companion_regeneration_rejects_created_record_without_jira_key(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_plan(tmp_path)
        _seed_existing_md(plan_path, [_mk_story("AUTH-S1", [1], export_state="created")])
        capture = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=derive_jira_output_path(
                plan_path, None, format="markdown"
            ),
            handoff_output_path=_companion_handoff_target(tmp_path),
        )
        with pytest.raises(JiraError):
            regenerate_companion_stories(
                capture,
                _companion_response([{"id": "AUTH-S2", "steps": [1]}]),
                repo_root=tmp_path,
            )

    def test_companion_regeneration_matches_equivalent_step_orders_as_one_canonical_set(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_multi_step_plan(tmp_path)
        _seed_companion_existing_md(
            plan_path,
            [
                _mk_story(
                    "AUTH-S1", [2, 1], export_state="created", jira_issue_key="PROJ-5"
                )
            ],
            source_plan_path="1-companion.md",
        )
        capture = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=derive_jira_output_path(
                plan_path, None, format="markdown"
            ),
            handoff_output_path=_companion_handoff_target(tmp_path),
        )

        export = regenerate_companion_stories(
            capture,
            _companion_response(
                [
                    {"id": "AUTH-S2", "steps": [1, 2]},
                    {"id": "AUTH-S3", "steps": [3]},
                ]
            ),
            repo_root=tmp_path,
        )
        matched = next(s for s in export.stories if s.jira_issue_key)
        assert matched.id == "AUTH-S2"
        assert matched.jira_issue_key == "PROJ-5"

    def test_companion_regeneration_rejects_empty_repeated_or_unparseable_source_step_sets(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_plan(tmp_path)
        target = derive_jira_output_path(plan_path, None, format="json")
        target.parent.mkdir(parents=True, exist_ok=True)

        def _seed_json_steps(steps: list) -> None:
            target.write_text(
                json.dumps(
                    {
                        "plan_title": "Companion Plan",
                        "epic": _DEFAULT_EPIC.to_dict(),
                        "total_estimate_hours": 2,
                        "stories": [
                            {
                                "id": "AUTH-S1",
                                "title": "Widget",
                                "description": "body",
                                "acceptance_criteria": ["a check"],
                                "files": [],
                                "steps": steps,
                                "depends_on": [],
                                "estimate_hours": 2,
                                "export_state": "draft",
                                "layer": "unspecified",
                                "ui_impact": "",
                                "frontend_test_recommendation": [],
                                "jira_issue_key": "",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

        for bad_steps in ([], [1, 1]):
            _seed_json_steps(bad_steps)
            capture = capture_companion_export_input(
                plan_path,
                repo_root=tmp_path,
                epic=_DEFAULT_EPIC,
                story_output_path=target,
                handoff_output_path=_companion_handoff_target(tmp_path),
                format="json",
            )
            with pytest.raises(JiraError):
                regenerate_companion_stories(
                    capture,
                    _companion_response([{"id": "AUTH-S2", "steps": [1]}]),
                    repo_root=tmp_path,
                )

        # An unparseable (non-numeric) covered-step field never becomes a
        # ticket at all, so it trivially never reaches key matching either.
        md_target = derive_jira_output_path(plan_path, None, format="markdown")
        valid_block = _format_markdown(
            "Companion Plan",
            [_mk_story("AUTH-S9", [1], export_state="draft")],
            epic=_DEFAULT_EPIC,
        )
        malformed_block = valid_block.replace("Plan steps: 1", "Plan steps: abc")
        md_target.write_text(malformed_block + "\n", encoding="utf-8")
        capture3 = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=md_target,
            handoff_output_path=_companion_handoff_target(tmp_path),
        )
        export3 = regenerate_companion_stories(
            capture3,
            _companion_response([{"id": "AUTH-S2", "steps": [1]}]),
            repo_root=tmp_path,
        )
        assert export3.dropped_history == []
        assert "AUTH-S9" not in export3.output

    def test_companion_regeneration_rejects_foreign_or_legacy_unproven_keyed_source(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_plan(tmp_path)

        # Legacy: an ordinary (non-companion) export carries no provenance
        # marker at all.
        _seed_existing_md(
            plan_path,
            [_mk_story("AUTH-S1", [1], export_state="created", jira_issue_key="PROJ-1")],
        )
        capture_legacy = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=derive_jira_output_path(
                plan_path, None, format="markdown"
            ),
            handoff_output_path=_companion_handoff_target(tmp_path),
        )
        with pytest.raises(JiraError):
            regenerate_companion_stories(
                capture_legacy,
                _companion_response([{"id": "AUTH-S2", "steps": [1]}]),
                repo_root=tmp_path,
            )

        # Foreign: a provenance marker is present but names a different plan.
        _seed_companion_existing_md(
            plan_path,
            [
                _mk_story(
                    "AUTH-S3", [1], export_state="created", jira_issue_key="PROJ-2"
                )
            ],
            source_plan_path="9-other-plan.md",
        )
        capture_foreign = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=derive_jira_output_path(
                plan_path, None, format="markdown"
            ),
            handoff_output_path=_companion_handoff_target(tmp_path),
        )
        with pytest.raises(JiraError):
            regenerate_companion_stories(
                capture_foreign,
                _companion_response([{"id": "AUTH-S4", "steps": [1]}]),
                repo_root=tmp_path,
            )

        capture_foreign_adopt = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=derive_jira_output_path(
                plan_path, None, format="markdown"
            ),
            handoff_output_path=_companion_handoff_target(tmp_path),
            adopt_existing=True,
        )
        with pytest.raises(JiraError, match="foreign source"):
            regenerate_companion_stories(
                capture_foreign_adopt,
                _companion_response([{"id": "AUTH-S4", "steps": [1]}]),
                repo_root=tmp_path,
            )

    def test_companion_regeneration_rejects_repeated_jira_key_across_source_records(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_multi_step_plan(tmp_path)
        _seed_existing_md(
            plan_path,
            [
                _mk_story(
                    "AUTH-S1", [1], export_state="created", jira_issue_key="PROJ-1"
                ),
                _mk_story(
                    "AUTH-S2", [2, 3], export_state="created", jira_issue_key="PROJ-1"
                ),
            ],
        )
        capture = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=derive_jira_output_path(
                plan_path, None, format="markdown"
            ),
            handoff_output_path=_companion_handoff_target(tmp_path),
        )
        with pytest.raises(JiraError):
            regenerate_companion_stories(
                capture,
                _companion_response(
                    [
                        {"id": "AUTH-S3", "steps": [1]},
                        {"id": "AUTH-S4", "steps": [2, 3]},
                    ]
                ),
                repo_root=tmp_path,
            )

    def test_companion_regeneration_rejects_duplicate_source_or_regenerated_step_set(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_plan(tmp_path)

        # Two existing (matchable) records sharing one canonical set.
        _seed_existing_md(
            plan_path,
            [
                _mk_story("AUTH-S1", [1], export_state="draft"),
                _mk_story("AUTH-S2", [1], export_state="draft"),
            ],
        )
        capture_a = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=derive_jira_output_path(
                plan_path, None, format="markdown"
            ),
            handoff_output_path=_companion_handoff_target(tmp_path),
        )
        with pytest.raises(JiraError):
            regenerate_companion_stories(
                capture_a,
                _companion_response([{"id": "AUTH-S3", "steps": [1]}]),
                repo_root=tmp_path,
            )

        # Two regenerated stories sharing one canonical set (no existing
        # source at all, so only the regenerated side is in play).
        target = derive_jira_output_path(plan_path, None, format="markdown")
        target.unlink()
        capture_b = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=target,
            handoff_output_path=_companion_handoff_target(tmp_path),
        )
        with pytest.raises(JiraError):
            regenerate_companion_stories(
                capture_b,
                _companion_response(
                    [
                        {"id": "AUTH-S4", "steps": [1]},
                        {"id": "AUTH-S5", "steps": [1]},
                    ]
                ),
                repo_root=tmp_path,
            )

    def test_companion_regeneration_rejects_changed_keyed_step_set_without_dropping_the_key(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_multi_step_plan(tmp_path)
        _seed_companion_existing_md(
            plan_path,
            [
                _mk_story(
                    "AUTH-S1", [2, 3], export_state="created", jira_issue_key="PROJ-7"
                )
            ],
            source_plan_path="1-companion.md",
        )
        capture = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=derive_jira_output_path(
                plan_path, None, format="markdown"
            ),
            handoff_output_path=_companion_handoff_target(tmp_path),
        )
        # The old combined [2, 3] set is split into two stories, so no
        # regenerated story shares its exact canonical set.
        with pytest.raises(JiraError):
            regenerate_companion_stories(
                capture,
                _companion_response(
                    [
                        {"id": "AUTH-S2", "steps": [1, 2]},
                        {"id": "AUTH-S3", "steps": [3]},
                    ]
                ),
                repo_root=tmp_path,
            )

    def test_companion_regeneration_reserves_retained_dropped_story_ids(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_multi_step_plan(tmp_path)
        _seed_existing_md(plan_path, [_mk_story("AUTH-S1", [4], export_state="dropped")])
        capture = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=derive_jira_output_path(
                plan_path, None, format="markdown"
            ),
            handoff_output_path=_companion_handoff_target(tmp_path),
        )
        with pytest.raises(JiraError):
            regenerate_companion_stories(
                capture,
                _companion_response(
                    [
                        # Reuses the retained dropped id "AUTH-S1".
                        {"id": "AUTH-S1", "steps": [1]},
                        {"id": "AUTH-S9", "steps": [2, 3]},
                    ]
                ),
                repo_root=tmp_path,
            )

    def test_companion_regeneration_reports_keyed_created_to_dropped_transition(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_multi_step_plan(tmp_path)
        _seed_existing_md(
            plan_path,
            [
                _mk_story(
                    "AUTH-S1", [4], export_state="created", jira_issue_key="PROJ-3"
                )
            ],
        )
        capture = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=derive_jira_output_path(
                plan_path, None, format="markdown"
            ),
            handoff_output_path=_companion_handoff_target(tmp_path),
        )

        export = regenerate_companion_stories(
            capture,
            _companion_response(
                [
                    {"id": "AUTH-S2", "steps": [1]},
                    {"id": "AUTH-S3", "steps": [2, 3]},
                ]
            ),
            repo_root=tmp_path,
        )
        assert export.created_to_dropped == [
            CompanionCreatedTicketNotice(story_id="AUTH-S1", jira_issue_key="PROJ-3")
        ]
        assert export.changed_created_tickets == []

    def test_companion_regeneration_json_format_carries_status_and_provenance(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_multi_step_plan(tmp_path)
        capture = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=derive_jira_output_path(plan_path, None, format="json"),
            handoff_output_path=_companion_handoff_target(tmp_path),
            format="json",
        )

        export = regenerate_companion_stories(
            capture,
            _companion_response(
                [
                    {"id": "AUTH-S1", "steps": [1]},
                    {"id": "AUTH-S2", "steps": [2, 3]},
                ]
            ),
            repo_root=tmp_path,
        )
        payload = json.loads(export.output)
        assert payload["source_plan_path"] == "1-companion.md"
        by_id = {s["id"]: s for s in payload["stories"]}
        assert by_id["AUTH-S1"]["step_status"] == {"1": "done"}
        assert by_id["AUTH-S1"]["historical"] is True
        assert by_id["AUTH-S2"]["step_status"] == {"2": "current", "3": "pending"}
        assert by_id["AUTH-S2"]["historical"] is False

    def test_json_and_markdown_historical_verdicts_agree_on_a_duplicate_step_id(
        self,
    ) -> None:
        # parse_jira_response now rejects a duplicate step id before a
        # Story is ever built, but the two renderers' "historical"
        # computation must still agree for any Story that reaches them by
        # another path -- a dict keyed by str(step_id) silently collapses
        # a duplicate, while a list-based count does not.
        story = _mk_story("AUTH-S1", [1, 1])
        step_status_map = {1: "done"}

        markdown = _render_story_block(story, detail_map={}, step_status_map=step_status_map)
        json_dict = _story_to_json_dict(story, {}, step_status_map=step_status_map)

        assert (
            "_(historical — every covered step is already done)_" in markdown
        )
        assert json_dict["historical"] is True


def _companion_invoker_with_fresh_ids(
    counter: dict[str, int], *, title: Optional[str] = None
) -> Callable[[str], str]:
    def invoker(_prompt: str) -> str:
        counter["n"] += 1
        entry: dict = {"id": f"AUTH-S{counter['n']}", "steps": [1]}
        if title is not None:
            entry["title"] = title
        return _companion_response([entry])

    return invoker


class TestPairedJiraExport:
    """Publication (step 5): preflight, staged two-target replace, recovery."""

    def _targets(self, root: Path, plan_path: Path) -> tuple[Path, Path]:
        return (
            derive_jira_output_path(plan_path, None, format="markdown"),
            _companion_handoff_target(root),
        )

    def test_staging_cleanup_ignores_permission_errors(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.jira import _StagedCompanionOutput, _cleanup_staged_outputs

        staged_path = tmp_path / ".jira-stories.md.companion.tmp"
        staged_path.write_text("staged", encoding="utf-8")
        original_unlink = Path.unlink

        def deny_cleanup(path: Path, *args: object, **kwargs: object) -> None:
            if path == staged_path:
                raise PermissionError("cleanup denied")
            original_unlink(path, *args, **kwargs)

        monkeypatch.setattr(Path, "unlink", deny_cleanup)

        _cleanup_staged_outputs(
            [
                _StagedCompanionOutput(
                    label="story",
                    final_path=tmp_path / "jira-stories.md",
                    tmp_path=staged_path,
                )
            ]
        )

    def test_staging_translates_directory_creation_failures(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.jira import _stage_companion_output

        target = tmp_path / "blocked" / "jira-stories.md"
        real_mkdir = Path.mkdir

        def deny_target_parent(path: Path, *args: object, **kwargs: object) -> None:
            if path == target.parent:
                raise OSError("permission denied")
            real_mkdir(path, *args, **kwargs)

        monkeypatch.setattr(Path, "mkdir", deny_target_parent)

        with pytest.raises(JiraError, match="could not stage companion story"):
            _stage_companion_output("story", target, "body")

    def test_second_export_reuses_the_same_plan_own_story_number(
        self, tmp_path: Path
    ) -> None:
        # Companion mode always fully regenerates on every export (by
        # design -- JIRA_FORMAT.md: "every successful export captures
        # fresh and republishes"). compute_start_number deliberately
        # excludes the plan's own existing story numbers so start_number
        # doesn't drift upward on repeat exports, but that only works if
        # the model is actually *allowed* to reuse its own plan's id: a
        # faithful model re-proposing AUTH-S1 for an unchanged plan must
        # not be rejected as a collision with itself.
        plan_path = _write_companion_plan(tmp_path)
        story_target, handoff_target = self._targets(tmp_path, plan_path)
        invoker = lambda prompt: _companion_response(  # noqa: E731
            [{"id": "AUTH-S1", "steps": [1]}]
        )

        export_jira(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=story_target,
            handoff_output_path=handoff_target,
            invoker=invoker,
        )

        result = export_jira(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=story_target,
            handoff_output_path=handoff_target,
            invoker=invoker,
        )
        assert "AUTH-S1" in story_target.read_text(encoding="utf-8")
        assert result.story_path == story_target

    def test_target_preflight_recognizes_its_own_output_after_a_plan_renumber(
        self, tmp_path: Path
    ) -> None:
        # Same defect shape as regenerate_companion_stories's same-plan
        # ownership proof (see the sibling renumber test above): a
        # renumbered plan's generated destinations are unchanged (keyed
        # by slug), so target-ownership recognition must tolerate a
        # stamped source_plan_path whose priority prefix no longer
        # matches the plan's current filename.
        from plan_tool.jira import _companion_target_preflight

        plan_path = _write_companion_plan(tmp_path)
        story_target, handoff_target = self._targets(tmp_path, plan_path)
        export_jira(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=story_target,
            handoff_output_path=handoff_target,
            invoker=lambda prompt: _companion_response(
                [{"id": "AUTH-S1", "steps": [1]}]
            ),
        )

        renumbered_plan_path = plan_path.parent / "2-companion.md"
        plan_path.rename(renumbered_plan_path)
        capture = capture_companion_export_input(
            renumbered_plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=story_target,
            handoff_output_path=handoff_target,
        )

        _companion_target_preflight(
            capture,
            story_output_path=story_target,
            handoff_output_path=handoff_target,
            repo_root=tmp_path,
        )

    def test_target_preflight_rejects_a_case_variant_story_handoff_collision(
        self, tmp_path: Path
    ) -> None:
        # A case-insensitive filesystem (default macOS/Windows) treats two
        # paths differing only in case as the same on-disk file; an exact
        # string comparison alone would miss that and let one companion
        # target silently overwrite the other on publish.
        from plan_tool.jira import _companion_target_preflight

        plan_path = _write_companion_plan(tmp_path)
        story_target, _handoff_target = self._targets(tmp_path, plan_path)
        case_variant_handoff = story_target.with_name(story_target.name.upper())

        capture = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=story_target,
            handoff_output_path=case_variant_handoff,
        )

        with pytest.raises(JiraError, match="must be distinct"):
            _companion_target_preflight(
                capture,
                story_output_path=story_target,
                handoff_output_path=case_variant_handoff,
                repo_root=tmp_path,
            )

    def test_target_preflight_rejects_a_case_variant_jira_lane_target_without_crashing(
        self, tmp_path: Path
    ) -> None:
        # A target that lands inside the jira-grade authoring lane only via
        # a case-insensitive match on `plan-details` (default macOS/Windows)
        # must still be rejected cleanly with a JiraError, not crash: parts
        # extraction after the containment check must use the same
        # case-safe comparison the containment check itself used, not a
        # plain case-sensitive relative_to() that only matches one of the
        # two branches _is_within can take.
        from plan_tool.jira import _companion_target_preflight

        plan_path = _write_companion_plan(tmp_path)
        case_variant_story = (
            plan_path.parent / "PLAN-DETAILS" / "companion" / "jira" / "story.md"
        )
        handoff_target = _companion_handoff_target(tmp_path)

        capture = capture_companion_export_input(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=case_variant_story,
            handoff_output_path=handoff_target,
        )

        with pytest.raises(JiraError, match="jira-grade authoring lane"):
            _companion_target_preflight(
                capture,
                story_output_path=case_variant_story,
                handoff_output_path=handoff_target,
                repo_root=tmp_path,
            )

    def test_existing_legacy_story_source_requires_explicit_adoption(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_plan(tmp_path)
        story_target, handoff_target = self._targets(tmp_path, plan_path)
        _seed_existing_md(
            plan_path,
            [
                _mk_story(
                    "AUTH-S1", [1], export_state="created", jira_issue_key="PROJ-1"
                )
            ],
        )

        def must_not_invoke(_prompt: str) -> str:
            raise AssertionError("legacy ownership must fail before invocation")

        with pytest.raises(JiraError, match="not a recognized companion-generated"):
            export_jira(
                plan_path,
                repo_root=tmp_path,
                epic=_DEFAULT_EPIC,
                story_output_path=story_target,
                handoff_output_path=handoff_target,
                invoker=must_not_invoke,
            )

    def test_adopt_existing_requires_a_readable_legacy_story_source(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_plan(tmp_path)
        story_target, handoff_target = self._targets(tmp_path, plan_path)

        with pytest.raises(JiraError, match="requires the selected readable legacy"):
            export_jira(
                plan_path,
                repo_root=tmp_path,
                epic=_DEFAULT_EPIC,
                story_output_path=story_target,
                handoff_output_path=handoff_target,
                adopt_existing=True,
                invoker=lambda _prompt: (_ for _ in ()).throw(
                    AssertionError("adoption preflight must run before invocation")
                ),
            )

    def test_adopt_existing_preserves_a_valid_legacy_jira_key_and_state(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_plan(tmp_path)
        story_target, handoff_target = self._targets(tmp_path, plan_path)
        _seed_existing_md(
            plan_path,
            [
                _mk_story(
                    "AUTH-S1", [1], export_state="created", jira_issue_key="PROJ-1"
                )
            ],
        )

        result = export_jira(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=story_target,
            handoff_output_path=handoff_target,
            adopt_existing=True,
            invoker=lambda _prompt: _companion_response(
                [{"id": "AUTH-S2", "steps": [1]}]
            ),
        )

        assert result.stories[0].id == "AUTH-S2"
        assert result.stories[0].export_state == "created"
        assert result.stories[0].jira_issue_key == "PROJ-1"
        assert read_markdown_provenance(story_target.read_text(encoding="utf-8"))
        assert read_markdown_provenance(handoff_target.read_text(encoding="utf-8"))

    def test_adopt_existing_replaces_a_readable_invalid_json_story_source(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_plan(tmp_path)
        story_target = derive_jira_output_path(plan_path, None, format="json")
        handoff_target = _companion_handoff_target(tmp_path)
        story_target.parent.mkdir(parents=True)
        story_target.write_text('{"stories": [', encoding="utf-8")

        result = export_jira(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=story_target,
            handoff_output_path=handoff_target,
            format="json",
            adopt_existing=True,
            invoker=lambda _prompt: _companion_response(
                [{"id": "AUTH-S1", "steps": [1]}]
            ),
        )

        assert result.story_path == story_target
        assert json.loads(story_target.read_text(encoding="utf-8"))["stories"][0][
            "id"
        ] == "AUTH-S1"

    def test_invalid_json_story_source_without_adoption_fails_before_invocation(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_plan(tmp_path)
        story_target = derive_jira_output_path(plan_path, None, format="json")
        story_target.parent.mkdir(parents=True)
        story_target.write_text('{"stories": [', encoding="utf-8")

        with pytest.raises(JiraError, match="invalid JSON"):
            export_jira(
                plan_path,
                repo_root=tmp_path,
                epic=_DEFAULT_EPIC,
                story_output_path=story_target,
                handoff_output_path=_companion_handoff_target(tmp_path),
                format="json",
                invoker=lambda _prompt: (_ for _ in ()).throw(
                    AssertionError("invalid JSON must fail before invocation")
                ),
            )

    def test_adopt_existing_rejects_a_missing_regenerated_key_match(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_multi_step_plan(tmp_path)
        story_target, handoff_target = self._targets(tmp_path, plan_path)
        _seed_existing_md(
            plan_path,
            [
                _mk_story(
                    "AUTH-S1", [1], export_state="created", jira_issue_key="PROJ-1"
                )
            ],
        )

        with pytest.raises(JiraError, match="no regenerated story covers"):
            export_jira(
                plan_path,
                repo_root=tmp_path,
                epic=_DEFAULT_EPIC,
                story_output_path=story_target,
                handoff_output_path=handoff_target,
                adopt_existing=True,
                invoker=lambda _prompt: _companion_response(
                    [{"id": "AUTH-S2", "steps": [1, 2, 3]}]
                ),
            )
        assert not handoff_target.exists()

    def test_adopt_existing_never_adopts_a_human_handoff(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_plan(tmp_path)
        story_target, handoff_target = self._targets(tmp_path, plan_path)
        _seed_existing_md(plan_path, [_mk_story("AUTH-S1", [1])])
        handoff_target.parent.mkdir(parents=True, exist_ok=True)
        handoff_target.write_text("human handoff\n", encoding="utf-8")

        with pytest.raises(JiraError, match="handoff target.*not a recognized"):
            export_jira(
                plan_path,
                repo_root=tmp_path,
                epic=_DEFAULT_EPIC,
                story_output_path=story_target,
                handoff_output_path=handoff_target,
                adopt_existing=True,
                invoker=lambda _prompt: _companion_response(
                    [{"id": "AUTH-S2", "steps": [1]}]
                ),
            )

    def test_render_jira_export_scopes_spawn_cwd_to_repo_root(
        self, tmp_path: Path
    ) -> None:
        """@spawn_cwd_from_repo_root scopes the paired renderer's invocation."""
        from plan_tool.backend import get_active_spawn_cwd
        from plan_tool.jira import render_jira_export

        plan_path = _write_companion_plan(tmp_path)
        story_target, handoff_target = self._targets(tmp_path, plan_path)
        seen: list = []

        def capture(_prompt: str) -> str:
            seen.append(get_active_spawn_cwd())
            return _companion_response([{"id": "AUTH-S1", "steps": [1]}])

        render_jira_export(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=story_target,
            handoff_output_path=handoff_target,
            invoker=capture,
        )
        assert seen == [tmp_path]

    def test_no_write_preview_surfaces_the_same_story_warnings_a_real_write_would(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # render_jira_export's own docstring says the publication path and
        # `jira --no-write` "share this sequence so each validates the
        # same handoff contract" -- that must include advisory warnings,
        # not just hard validation, or a --no-write preview silently
        # under-reports problems a real write would flag.
        from plan_tool.jira import render_jira_export

        plan_path = _write_companion_plan(tmp_path)
        story_target, handoff_target = self._targets(tmp_path, plan_path)
        invoker = lambda prompt: _companion_response(  # noqa: E731
            [{"id": "AUTH-S1", "steps": [1], "files": ["docs/MISSING.md"]}]
        )

        render_jira_export(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=story_target,
            handoff_output_path=handoff_target,
            invoker=invoker,
        )
        assert "docs/MISSING.md" in capsys.readouterr().err

        export_jira(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=story_target,
            handoff_output_path=handoff_target,
            invoker=invoker,
        )
        assert "docs/MISSING.md" in capsys.readouterr().err

    def test_companion_publication_renders_the_handoff_body_exactly_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # render_jira_export computes the handoff body to validate it
        # before invoking the model; export_jira must reuse that
        # result rather than rendering the same (deterministic) body a
        # second time.
        import plan_tool.jira as jira_module
        import plan_tool.jira_handoff as jira_handoff_module

        plan_path = _write_companion_plan(tmp_path)
        story_target, handoff_target = self._targets(tmp_path, plan_path)
        calls: list = []
        real_render_handoff_body = jira_handoff_module.render_handoff_body

        def counting_render_handoff_body(render_input: object) -> str:
            calls.append(render_input)
            return real_render_handoff_body(render_input)

        # jira.py's render_jira_export and jira_handoff.py's render_handoff
        # each hold their own imported/module-local name binding for
        # render_handoff_body -- patch both so either call site is caught.
        monkeypatch.setattr(
            jira_module, "render_handoff_body", counting_render_handoff_body
        )
        monkeypatch.setattr(
            jira_handoff_module, "render_handoff_body", counting_render_handoff_body
        )

        export_jira(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=story_target,
            handoff_output_path=handoff_target,
            invoker=lambda prompt: _companion_response(
                [{"id": "AUTH-S1", "steps": [1]}]
            ),
        )

        assert len(calls) == 1

    def test_companion_export_surfaces_documented_advisory_warnings(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        plan_path = _write_companion_plan(tmp_path)
        story_target, handoff_target = self._targets(tmp_path, plan_path)

        export_jira(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=story_target,
            handoff_output_path=handoff_target,
            invoker=lambda _prompt: _companion_response(
                [{"id": "AUTH-S1", "steps": [1], "estimate_hours": 1}]
            ),
        )

        assert "soft decomposition floor" in capsys.readouterr().err

    def test_companion_publication_reports_handoff_render_errors_as_jira_errors(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.jira_handoff import HandoffRenderError

        plan_path = _write_companion_plan(tmp_path)
        story_target, handoff_target = self._targets(tmp_path, plan_path)

        def fail_render(render_input: object) -> str:
            raise HandoffRenderError("missing historical step intent")

        monkeypatch.setattr("plan_tool.jira.render_handoff_body", fail_render)
        invocations: list[str] = []

        with pytest.raises(JiraError, match="companion handoff cannot be rendered"):
            export_jira(
                plan_path,
                repo_root=tmp_path,
                epic=_DEFAULT_EPIC,
                story_output_path=story_target,
                handoff_output_path=handoff_target,
                invoker=lambda prompt: invocations.append(prompt) or "[]",
            )

        assert invocations == []
        assert not story_target.exists()
        assert not handoff_target.exists()

    def test_companion_publication_uses_one_captured_snapshot_and_complete_provenance_for_both_sources(
        self, tmp_path: Path
    ) -> None:
        plan_path = tmp_path / "1-companion.md"
        plan_path.write_text(
            "---\n"
            "title: Companion Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Build the widget\n"
            "    intent: Ship the widget end-to-end.\n"
            "    files:\n"
            "      - widget.py\n"
            "    detail: plan-details/companion/detail.md\n"
            "    status: current\n"
            "---\n\n"
            "# Companion Plan\n\n"
            "Original body prose.\n",
            encoding="utf-8",
        )
        (tmp_path / "widget.py").write_text(
            "ORIGINAL_SOURCE_MARKER\n", encoding="utf-8"
        )
        detail_path = tmp_path / "plan-details" / "companion" / "detail.md"
        detail_path.parent.mkdir(parents=True, exist_ok=True)
        detail_path.write_text(
            _RUN_GRADE_BODY.replace(
                "Nothing parses the plan yet.", "ORIGINAL_DETAIL_MARKER"
            ),
            encoding="utf-8",
        )
        story_target, handoff_target = self._targets(tmp_path, plan_path)

        def invoker(prompt: str) -> str:
            # Mutate every source captured before this call runs, proving
            # the published outputs reflect the frozen snapshot rather
            # than a live re-read.
            plan_path.write_text(
                plan_path.read_text(encoding="utf-8").replace(
                    "Build the widget", "CHANGED TITLE"
                ),
                encoding="utf-8",
            )
            (tmp_path / "widget.py").write_text(
                "CHANGED_SOURCE_MARKER\n", encoding="utf-8"
            )
            detail_path.write_text(
                _RUN_GRADE_BODY.replace(
                    "Nothing parses the plan yet.", "CHANGED_DETAIL_MARKER"
                ),
                encoding="utf-8",
            )
            return _companion_response([{"id": "AUTH-S1", "steps": [1]}])

        result = export_jira(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=story_target,
            handoff_output_path=handoff_target,
            invoker=invoker,
        )

        assert "ORIGINAL_DETAIL_MARKER" in result.handoff_output
        assert "CHANGED_DETAIL_MARKER" not in result.handoff_output
        assert "ORIGINAL_SOURCE_MARKER" in result.handoff_output
        assert "CHANGED_SOURCE_MARKER" not in result.handoff_output
        assert "Build the widget" in result.handoff_output
        assert "CHANGED TITLE" not in result.handoff_output

        story_provenance = read_markdown_provenance(result.story_output)
        handoff_provenance = read_markdown_provenance(result.handoff_output)
        assert story_provenance is not None
        assert handoff_provenance is not None
        assert story_provenance.fingerprint == handoff_provenance.fingerprint
        assert story_provenance.pair_identity == handoff_provenance.pair_identity
        assert story_target.read_text(encoding="utf-8") == result.story_output
        assert handoff_target.read_text(encoding="utf-8") == result.handoff_output

    def test_companion_replaces_current_story_source_instead_of_using_append_mode(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_plan(tmp_path)
        story_target, handoff_target = self._targets(tmp_path, plan_path)
        counter = {"n": 0}

        first = export_jira(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=story_target,
            handoff_output_path=handoff_target,
            invoker=_companion_invoker_with_fresh_ids(counter, title="Old title"),
        )
        assert "Old title" in first.story_output

        second = export_jira(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=story_target,
            handoff_output_path=handoff_target,
            invoker=_companion_invoker_with_fresh_ids(counter, title="New title"),
        )

        assert "New title" in second.story_output
        assert "Old title" not in second.story_output
        on_disk = story_target.read_text(encoding="utf-8")
        assert "New title" in on_disk
        assert "Old title" not in on_disk

    def test_companion_replaces_only_unchanged_same_plan_complete_pair_targets(
        self, tmp_path: Path
    ) -> None:
        def never_invoke(prompt: str) -> str:
            raise AssertionError(
                "companion model must not be invoked for an unsafe target"
            )

        # (a) A recognized, unchanged pair is replaced on a second run.
        recognized_dir = tmp_path / "recognized"
        recognized_dir.mkdir()
        plan_path = _write_companion_plan(recognized_dir)
        story_target, handoff_target = self._targets(recognized_dir, plan_path)
        counter = {"n": 0}
        invoker = _companion_invoker_with_fresh_ids(counter)

        export_jira(
            plan_path,
            repo_root=recognized_dir,
            epic=_DEFAULT_EPIC,
            story_output_path=story_target,
            handoff_output_path=handoff_target,
            invoker=invoker,
        )
        assert counter["n"] == 1
        result = export_jira(
            plan_path,
            repo_root=recognized_dir,
            epic=_DEFAULT_EPIC,
            story_output_path=story_target,
            handoff_output_path=handoff_target,
            invoker=invoker,
        )
        assert counter["n"] == 2
        assert result.story_path == story_target

        # (b) A human-owned (ordinary, unstamped) story target is refused
        # before the model is ever invoked.
        human_dir = tmp_path / "human"
        human_dir.mkdir()
        human_plan = _write_companion_plan(human_dir)
        human_story, human_handoff = self._targets(human_dir, human_plan)
        _seed_existing_md(human_plan, [_mk_story("AUTH-S1", [1])])
        with pytest.raises(JiraError):
            export_jira(
                human_plan,
                repo_root=human_dir,
                epic=_DEFAULT_EPIC,
                story_output_path=human_story,
                handoff_output_path=human_handoff,
                invoker=never_invoke,
            )

        # (c) A foreign-plan companion source is refused.
        foreign_dir = tmp_path / "foreign"
        foreign_dir.mkdir()
        plan_a = _write_companion_plan(foreign_dir)
        story_a, handoff_a = self._targets(foreign_dir, plan_a)
        export_jira(
            plan_a,
            repo_root=foreign_dir,
            epic=_DEFAULT_EPIC,
            story_output_path=story_a,
            handoff_output_path=handoff_a,
            invoker=lambda prompt: _companion_response(
                [{"id": "AUTH-S1", "steps": [1]}]
            ),
        )
        plan_b_path = foreign_dir / "2-other.md"
        plan_b_path.write_text(
            _COMPANION_MINIMAL_PLAN.replace("Companion Plan", "Other Plan"),
            encoding="utf-8",
        )
        with pytest.raises(JiraError):
            export_jira(
                plan_b_path,
                repo_root=foreign_dir,
                epic=_DEFAULT_EPIC,
                story_output_path=story_a,
                handoff_output_path=_companion_handoff_target(foreign_dir, "other.md"),
                invoker=never_invoke,
            )

        # (d) An alternate-destination pair is refused.
        alt_dest_dir = tmp_path / "alt_dest"
        alt_dest_dir.mkdir()
        plan_d = _write_companion_plan(alt_dest_dir)
        story_d, handoff_d = self._targets(alt_dest_dir, plan_d)
        export_jira(
            plan_d,
            repo_root=alt_dest_dir,
            epic=_DEFAULT_EPIC,
            story_output_path=story_d,
            handoff_output_path=handoff_d,
            invoker=lambda prompt: _companion_response(
                [{"id": "AUTH-S1", "steps": [1]}]
            ),
        )
        other_handoff_d = _companion_handoff_target(alt_dest_dir, "other.md")
        with pytest.raises(JiraError):
            export_jira(
                plan_d,
                repo_root=alt_dest_dir,
                epic=_DEFAULT_EPIC,
                story_output_path=story_d,
                handoff_output_path=other_handoff_d,
                invoker=never_invoke,
            )

        # (e) An alternate-format pair is refused.
        alt_fmt_dir = tmp_path / "alt_fmt"
        alt_fmt_dir.mkdir()
        plan_e = _write_companion_plan(alt_fmt_dir)
        story_e, handoff_e = self._targets(alt_fmt_dir, plan_e)
        export_jira(
            plan_e,
            repo_root=alt_fmt_dir,
            epic=_DEFAULT_EPIC,
            story_output_path=story_e,
            handoff_output_path=handoff_e,
            invoker=lambda prompt: _companion_response(
                [{"id": "AUTH-S1", "steps": [1]}]
            ),
        )
        with pytest.raises(JiraError):
            export_jira(
                plan_e,
                repo_root=alt_fmt_dir,
                epic=_DEFAULT_EPIC,
                story_output_path=story_e,
                handoff_output_path=handoff_e,
                format="json",
                invoker=never_invoke,
            )

    def test_companion_target_preflight_rejects_any_grade_detail_before_model_or_renderer(
        self, tmp_path: Path
    ) -> None:
        def never_invoke(prompt: str) -> str:
            raise AssertionError("must not invoke the model on an unsafe target")

        # (a) A destination colliding with an *unselected*-grade detail
        # artifact is rejected — capture_companion_export_input's own
        # preflight fires before invocation or either renderer runs.
        detail_dir = tmp_path / "detail_collision"
        detail_dir.mkdir()
        plan_path = _write_companion_plan(detail_dir)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        jira_grade_path = derive_jira_detail_path(plan_path, plan, step)
        with pytest.raises(JiraError):
            export_jira(
                plan_path,
                repo_root=detail_dir,
                epic=_DEFAULT_EPIC,
                story_output_path=jira_grade_path,
                handoff_output_path=_companion_handoff_target(detail_dir),
                grade="run",
                invoker=never_invoke,
            )

        # (b) A handoff destination inside *any* plan's detail bundle is
        # rejected, even without colliding with a specific artifact.
        bundle_dir = tmp_path / "bundle"
        bundle_dir.mkdir()
        plan_path_b = _write_companion_plan(bundle_dir)
        with pytest.raises(JiraError):
            export_jira(
                plan_path_b,
                repo_root=bundle_dir,
                epic=_DEFAULT_EPIC,
                story_output_path=derive_jira_output_path(
                    plan_path_b, None, format="markdown"
                ),
                handoff_output_path=(
                    bundle_dir / "plan-details" / "companion" / "handoff.md"
                ),
                invoker=never_invoke,
            )

        # (c) Either generated target inside the jira-grade authoring lane
        # is rejected.
        lane_dir = tmp_path / "lane"
        lane_dir.mkdir()
        plan_path_c = _write_companion_plan(lane_dir)
        with pytest.raises(JiraError):
            export_jira(
                plan_path_c,
                repo_root=lane_dir,
                epic=_DEFAULT_EPIC,
                story_output_path=(
                    lane_dir
                    / "plan-details"
                    / "companion"
                    / "jira"
                    / "jira-stories.md"
                ),
                handoff_output_path=_companion_handoff_target(lane_dir),
                invoker=never_invoke,
            )

    def test_companion_final_raw_content_change_aborts_unstarted_replacements(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_companion_plan(tmp_path)
        story_target, handoff_target = self._targets(tmp_path, plan_path)
        counter = {"n": 0}
        export_jira(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=story_target,
            handoff_output_path=handoff_target,
            invoker=_companion_invoker_with_fresh_ids(counter),
        )
        original_story_text = story_target.read_text(encoding="utf-8")
        original_handoff_text = handoff_target.read_text(encoding="utf-8")
        fresh_ids = _companion_invoker_with_fresh_ids(counter, title="New title")

        def mutating_invoker(prompt: str) -> str:
            # A concurrent edit landing after capture but before this run's
            # final replacement — outside any parsed record mapping.
            handoff_target.write_text(
                original_handoff_text + "\n<!-- concurrent edit -->\n",
                encoding="utf-8",
            )
            return fresh_ids(prompt)

        with pytest.raises(JiraError):
            export_jira(
                plan_path,
                repo_root=tmp_path,
                epic=_DEFAULT_EPIC,
                story_output_path=story_target,
                handoff_output_path=handoff_target,
                invoker=mutating_invoker,
            )

        # Neither replacement started: the story target is untouched, and
        # the handoff target still shows the injected edit rather than a
        # freshly rendered (or restored) file.
        assert story_target.read_text(encoding="utf-8") == original_story_text
        assert handoff_target.read_text(encoding="utf-8") == (
            original_handoff_text + "\n<!-- concurrent edit -->\n"
        )

    def test_companion_second_final_replace_failure_reports_target_and_cleans_staging(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = _write_companion_plan(tmp_path)
        story_target, handoff_target = self._targets(tmp_path, plan_path)
        counter = {"n": 0}
        export_jira(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=story_target,
            handoff_output_path=handoff_target,
            invoker=_companion_invoker_with_fresh_ids(counter),
        )
        original_story_text = story_target.read_text(encoding="utf-8")
        original_handoff_text = handoff_target.read_text(encoding="utf-8")

        real_replace = os.replace
        replace_calls = {"n": 0}

        def flaky_replace(src: object, dst: object) -> None:
            replace_calls["n"] += 1
            if replace_calls["n"] == 2:
                raise OSError("disk full")
            real_replace(src, dst)

        monkeypatch.setattr("plan_tool.jira.os.replace", flaky_replace)

        with pytest.raises(JiraError) as excinfo:
            export_jira(
                plan_path,
                repo_root=tmp_path,
                epic=_DEFAULT_EPIC,
                story_output_path=story_target,
                handoff_output_path=handoff_target,
                invoker=_companion_invoker_with_fresh_ids(counter, title="New title"),
            )
        assert str(handoff_target) in str(excinfo.value)
        assert "rerun companion export to regenerate both sources" in str(excinfo.value)

        # The story replacement (staged first) landed; the handoff
        # replacement (second) failed and was never written — and no
        # partial publication is reported as success.
        assert story_target.read_text(encoding="utf-8") != original_story_text
        assert handoff_target.read_text(encoding="utf-8") == original_handoff_text
        assert list(story_target.parent.glob(".*.companion.tmp")) == []
        assert list(handoff_target.parent.glob(".*.companion.tmp")) == []

    def test_companion_next_run_regenerates_both_sources_after_partial_publication(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = _write_companion_plan(tmp_path)
        story_target, handoff_target = self._targets(tmp_path, plan_path)
        counter = {"n": 0}
        export_jira(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=story_target,
            handoff_output_path=handoff_target,
            invoker=_companion_invoker_with_fresh_ids(counter),
        )

        real_replace = os.replace
        replace_calls = {"n": 0}

        def flaky_replace(src: object, dst: object) -> None:
            replace_calls["n"] += 1
            if replace_calls["n"] == 2:
                raise OSError("disk full")
            real_replace(src, dst)

        with monkeypatch.context() as m:
            m.setattr("plan_tool.jira.os.replace", flaky_replace)
            with pytest.raises(JiraError):
                export_jira(
                    plan_path,
                    repo_root=tmp_path,
                    epic=_DEFAULT_EPIC,
                    story_output_path=story_target,
                    handoff_output_path=handoff_target,
                    invoker=_companion_invoker_with_fresh_ids(
                        counter, title="Partial title"
                    ),
                )

        # os.replace is back to normal outside the monkeypatch context — a
        # later current-input run must fully recover, no special-cased
        # "resume" logic required.
        export_jira(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=story_target,
            handoff_output_path=handoff_target,
            invoker=_companion_invoker_with_fresh_ids(counter, title="Recovered title"),
        )

        story_text = story_target.read_text(encoding="utf-8")
        handoff_text = handoff_target.read_text(encoding="utf-8")
        assert "Recovered title" in story_text
        assert "Partial title" not in story_text
        story_provenance = read_markdown_provenance(story_text)
        handoff_provenance = read_markdown_provenance(handoff_text)
        assert story_provenance is not None
        assert handoff_provenance is not None
        assert story_provenance.fingerprint == handoff_provenance.fingerprint
        assert list(story_target.parent.glob(".*.companion.tmp")) == []
        assert list(handoff_target.parent.glob(".*.companion.tmp")) == []


def test_run_grade_paired_export_rejects_unmatched_fence_before_target_write(
    tmp_path: Path,
) -> None:
    plan_path = _write_companion_plan(tmp_path, body=_COMPANION_MINIMAL_PLAN)
    story_target = derive_jira_output_path(plan_path, None, format="markdown")
    handoff_target = _companion_handoff_target(tmp_path)
    export_jira(
        plan_path,
        repo_root=tmp_path,
        epic=_DEFAULT_EPIC,
        story_output_path=story_target,
        handoff_output_path=handoff_target,
        invoker=lambda _prompt: _companion_response(
            [{"id": "AUTH-S1", "steps": [1]}]
        ),
    )
    before_story = story_target.read_text(encoding="utf-8")
    before_handoff = handoff_target.read_text(encoding="utf-8")
    plan_path.write_text(
        plan_path.read_text(encoding="utf-8") + "\n```\n",
        encoding="utf-8",
    )

    with pytest.raises(JiraError, match="unmatched opening code fence"):
        export_jira(
            plan_path,
            repo_root=tmp_path,
            epic=_DEFAULT_EPIC,
            story_output_path=story_target,
            handoff_output_path=handoff_target,
            invoker=lambda _prompt: _companion_response(
                [{"id": "AUTH-S1", "steps": [1]}]
            ),
        )

    assert story_target.read_text(encoding="utf-8") == before_story
    assert handoff_target.read_text(encoding="utf-8") == before_handoff
    assert list(story_target.parent.glob(".*.companion.tmp")) == []
    assert list(handoff_target.parent.glob(".*.companion.tmp")) == []


def test_export_accepts_rewritten_description_plan_without_changing_story_title(tmp_path):
    from plan_tool.parser import parse_plan, write_plan

    path = _write_companion_plan(tmp_path)
    plan = parse_plan(path)
    text = plan.steps[0].title
    write_plan(path, plan)
    prompts = []
    def fake_invoker(prompt):
        prompts.append(prompt)
        return _companion_response([{"id": "AUTH-S1", "steps": [1], "title": "Story title"}])

    target = tmp_path / "stories.md"
    export_jira(
        path, repo_root=tmp_path, epic=_DEFAULT_EPIC,
        story_output_path=target,
        handoff_output_path=_companion_handoff_target(tmp_path),
        invoker=fake_invoker,
    )
    assert text in prompts[0]
    assert "Story title" in target.read_text()
