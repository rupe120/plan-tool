"""Tests for plan_tool.detail — step 1 (pure helpers).

No I/O outside ``tmp_path`` fixtures; no claude invocation. The
orchestrator and CLI tests live alongside in later steps.
"""

from __future__ import annotations

import contextlib
import inspect
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pytest

from plan_tool.checkpoint import (
    CHECKPOINT_SCHEMA_VERSION,
    Checkpoint,
    checkpoint_path,
    save_checkpoint,
)


def _fresh_now() -> str:
    """Current UTC timestamp in the iso8601 form ``Checkpoint.created_at``
    expects. Used by resume-test fixtures so seeded checkpoints aren't
    rejected by ``load_if_valid``'s default ``DEFAULT_MAX_AGE_SECONDS``
    (30 days) — a hardcoded historical timestamp would silently turn
    every cache-hit test into a cache-miss test once the wall clock
    moved past the TTL.
    """
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
from plan_tool import style
from plan_tool.detail import (
    DetailDeferral,
    DetailError,
    DetailResult,
    _DETAIL_CHECKPOINT_NAME,
    _REPROMPT_SUFFIX,
    _STUB_SECTION_BODY,
    _StepAuthoringOutcome,
    _archive_orphan_details,
    _author_step_detail,
    _discover_siblings,
    _strip_bare_fence_lines,
    _detail_step_input_hash,
    _format_tests_directive,
    _plan_slug,
    _repo_relative,
    _scaled_detail_budget_for_step,
    derive_detail_path,
    derive_step_slug,
    emit_detail_findings_summary,
    extract_filename_mentions,
    extract_plan_guardrails,
    extract_plan_references,
    extract_path_mentions,
    find_unreferenced_detail_for_step,
    generate_detail,
    parse_detail_response,
    parse_structured_detail_response,
    render_declared_risk_context,
    render_detail_prompt,
    stamp_detail_format_version_marker,
    update_step_detail_field,
)
from plan_tool.detail_artifacts import (
    DetailFormatError,
    locate_detail_format_carrier,
    render_detail_format_version_marker,
    require_supported_detail_format_version,
)
from plan_tool.review import Recommendation
from plan_tool.scope_fence import (
    PLAN_INTENT_HEADING,
    STEP_INTENT_HEADING,
    render_scope_fence,
)
from plan_tool.concept_tree import (
    ConceptNode,
    ConceptTree,
    RECORD_KIND_DECISION,
    RECORD_KIND_FULL_TREE,
    concept_id,
    load_concepts,
    save_concepts,
)
from plan_tool.review_persistence import compute_plan_fingerprint
from plan_tool.parser import parse_plan, write_plan
from plan_tool.schema import (
    ChangeType,
    Complexity,
    Plan,
    PlanStatus,
    Priority,
    RiskProfile,
    Step,
    StepScope,
    StepStatus,
)
from plan_tool.progress import NullReporter, ProgressReporter, StepHandle
from plan_tool.project_profile import initialize_project_profile


def test_generate_detail_signature_is_exact() -> None:
    """Keep generate_detail's callable boundary stable for direct callers."""
    from plan_tool import detail as detail_module

    signature = inspect.signature(generate_detail)
    parameter_records = [
        (parameter.name, parameter.kind, parameter.default, parameter.annotation)
        for parameter in signature.parameters.values()
    ]

    assert parameter_records == [
        ("plan_path", inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.empty, "Path"),
        ("repo_root", inspect.Parameter.KEYWORD_ONLY, inspect.Parameter.empty, "Path"),
        ("step_id", inspect.Parameter.KEYWORD_ONLY, None, "Optional[int]"),
        ("force", inspect.Parameter.KEYWORD_ONLY, False, "bool"),
        ("dry_run", inspect.Parameter.KEYWORD_ONLY, False, "bool"),
        (
            "invoker",
            inspect.Parameter.KEYWORD_ONLY,
            detail_module.shell_detail_invoker,
            "DetailInvoker",
        ),
        ("reporter", inspect.Parameter.KEYWORD_ONLY, None, "Optional[ProgressReporter]"),
        ("extract_lessons", inspect.Parameter.KEYWORD_ONLY, False, "bool"),
        ("lessons_invoker", inspect.Parameter.KEYWORD_ONLY, None, "Optional[LessonsInvoker]"),
        (
            "foundational_invoker",
            inspect.Parameter.KEYWORD_ONLY,
            None,
            "Optional[SweepInvoker]",
        ),
        ("capture_scenarios", inspect.Parameter.KEYWORD_ONLY, False, "bool"),
        ("arm", inspect.Parameter.KEYWORD_ONLY, None, "Optional[str]"),
        ("strict_check", inspect.Parameter.KEYWORD_ONLY, False, "bool"),
        (
            "equivalence_invoker",
            inspect.Parameter.KEYWORD_ONLY,
            None,
            "Optional[EquivalenceInvoker]",
        ),
        ("resume", inspect.Parameter.KEYWORD_ONLY, True, "bool"),
        (
            "prompt_fn",
            inspect.Parameter.KEYWORD_ONLY,
            None,
            "Optional[Callable[[str], str]]",
        ),
        ("yes", inspect.Parameter.KEYWORD_ONLY, False, "bool"),
        ("run_logger", inspect.Parameter.KEYWORD_ONLY, None, "Optional[RunLogWriter]"),
        (
            "budget",
            inspect.Parameter.KEYWORD_ONLY,
            detail_module.IterativeBudget(enabled=False),
            "IterativeBudget",
        ),
        ("allow_drift", inspect.Parameter.KEYWORD_ONLY, False, "bool"),
        ("auto_reconcile_on_drift", inspect.Parameter.KEYWORD_ONLY, True, "bool"),
        ("collision_sidecar", inspect.Parameter.KEYWORD_ONLY, True, "bool"),
        ("triage", inspect.Parameter.KEYWORD_ONLY, True, "bool"),
        ("include_info", inspect.Parameter.KEYWORD_ONLY, False, "bool"),
        ("allow_split", inspect.Parameter.KEYWORD_ONLY, False, "bool"),
        ("jobs", inspect.Parameter.KEYWORD_ONLY, 1, "int"),
        (
            "commit_step",
            inspect.Parameter.KEYWORD_ONLY,
            None,
            "Optional[Callable[[int, str], None]]",
        ),
        ("prior_body", inspect.Parameter.KEYWORD_ONLY, "", "str"),
        ("recovery_only", inspect.Parameter.KEYWORD_ONLY, False, "bool"),
    ]
    assert signature.return_annotation == "list[DetailResult]"


def test_parse_dispatch_wraps_plan_parse_failure_as_detail_error(
    tmp_path: Path,
) -> None:
    plan_path = tmp_path / "broken.md"
    plan_path.write_text(
        "---\n"
        "title: Broken\n"
        "  invalid: : :\n"
        "---\n"
        "# body\n",
        encoding="utf-8",
    )

    with pytest.raises(DetailError, match="failed to parse"):
        generate_detail(plan_path, repo_root=tmp_path)


def test_parse_dispatch_signature_returns_run_grade_outcome() -> None:
    from plan_tool import detail as detail_module

    signature = inspect.signature(detail_module._parse_detail_plan_and_dispatch)
    assert signature.return_annotation == "_RunGradeDetailDispatch"


def test_path_extractors_recognize_text_golden_artifacts() -> None:
    body = (
        "Refresh `tests/cli/package_surface_help.golden.txt` and "
        "compare `package_surface_help.golden.txt`."
    )

    assert extract_path_mentions(body) == {
        "tests/cli/package_surface_help.golden.txt"
    }
    assert extract_filename_mentions(body) == {"package_surface_help.golden.txt"}


def test_path_extractors_recognize_the_extensionless_dockerfile_only() -> None:
    """``Dockerfile`` is the one supported extensionless filename: an exact
    ``/Dockerfile`` path and a bare backticked ``Dockerfile`` match, while
    look-alikes, a different case, an unlisted suffix and un-backticked prose
    do not."""
    body = (
        "Edit `engine_worker/Dockerfile` and `Dockerfile`. Not these: "
        "`engine_worker/Dockerfiles`, `engine_worker/MyDockerfile`, "
        "`engine_worker/dockerfile`, `Dockerfile.dev`, `Makefile`, or the "
        "Dockerfile in prose."
    )

    assert extract_path_mentions(body) == {"engine_worker/Dockerfile"}
    assert extract_filename_mentions(body) == {"Dockerfile"}


@pytest.fixture(autouse=True)
def _stub_lessons_extraction(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default the lesson-extraction inside ``generate_detail`` to a
    no-op. The real path falls back to ``shell.claude_invoke`` when no
    ``lessons_invoker`` is passed (detail.py:1605), which shells out to
    real claude — slow and non-deterministic. The convention in this
    file is to pass ``extract_lessons=False`` per call; this fixture is
    defense-in-depth so a forgotten kwarg doesn't reintroduce a real
    claude call. Tests that need to assert on lesson extraction can
    override by re-monkeypatching the same attribute.
    """
    from plan_tool import detail as detail_module
    monkeypatch.setattr(
        detail_module,
        "extract_and_append_detail_lessons",
        lambda **kwargs: (0, 0),
    )


_DETAIL_PLAN = """---
title: Detail Test Plan
status: in-progress
priority: medium
steps:
  - id: 1
    title: Wire up the renderer
    files:
      - renderer.py
    complexity: low
    status: current
  - id: 3
    title: Build it
    files:
      - foo.py
      - bar.py
    depends_on: [1]
---

# Detail Test Plan
"""


def _write_detail_plan(tmp_path: Path) -> Path:
    plan_path = tmp_path / "2-foo.md"
    plan_path.write_text(_DETAIL_PLAN, encoding="utf-8")
    (tmp_path / "renderer.py").write_text(
        "def render(plan):\n    return None\n", encoding="utf-8"
    )
    (tmp_path / "foo.py").write_text(
        "FOO = 1\n", encoding="utf-8"
    )
    (tmp_path / "bar.py").write_text(
        "# bar module\n", encoding="utf-8"
    )
    return plan_path


# Same steps as ``_DETAIL_PLAN`` but with real H2 body sections, so the plan
# has body-section buckets a detail step can propose deferring.
_DETAIL_PLAN_WITH_SECTIONS = """---
title: Detail Test Plan
status: in-progress
priority: medium
steps:
  - id: 1
    title: Wire up the renderer
    files:
      - renderer.py
    complexity: low
    status: current
  - id: 3
    title: Build it
    files:
      - foo.py
      - bar.py
    depends_on: [1]
---

# Detail Test Plan

## Overview

Some overview prose.

## Risks

Risky bits that might be deferred.

## Follow-up

Later work.
"""


def _write_detail_plan_with_sections(tmp_path: Path) -> Path:
    plan_path = _write_detail_plan(tmp_path)
    plan_path.write_text(_DETAIL_PLAN_WITH_SECTIONS, encoding="utf-8")
    return plan_path


# --- derive_step_slug ------------------------------------------------------


class TestDeriveStepSlug:
    def test_simple_title_kebab_cased(self) -> None:
        assert derive_step_slug("Wire up renderer") == "wire-up-renderer"

    def test_drops_stopwords(self) -> None:
        assert derive_step_slug("Add the foo endpoint") == "foo-endpoint"

    def test_lowercases_camel_case(self) -> None:
        # Token-level lowercasing: AddFooEndpoint is one regex token, not three.
        assert derive_step_slug("AddFooEndpoint") == "addfooendpoint"

    def test_drops_short_tokens(self) -> None:
        # `X` is a 1-char token (dropped); `Do` and `now` are stopwords.
        assert derive_step_slug("Do X now") == "step"

    def test_empty_title_falls_back(self) -> None:
        assert derive_step_slug("") == "step"

    def test_keeps_digits(self) -> None:
        assert (
            derive_step_slug("Migrate to v2 schema")
            == "migrate-v2-schema"
        )

    def test_punctuation_drops_cleanly(self) -> None:
        """Backticks / dots / commas don't leave artifacts in the slug."""
        assert (
            derive_step_slug("Implement `foo.bar`, then build")
            == "implement-foo-bar-then-build"
        )

    def test_long_title_truncated_at_word_boundary(self) -> None:
        """A restated-paragraph title is capped to a filesystem-safe length."""
        title = (
            "Correct existing docs to match real paths and scopes "
            "Advice Service apikey not api key LaborDataService instanceName "
            "not env new content not currently covered any scope doc "
            "sandbox app vpc id vs pipeline example app infra vpc id "
            "env plus store scope owner ownership matrix per value"
        )
        slug = derive_step_slug(title)
        assert len(slug) <= 40
        # Truncates at a ``-`` so we never end mid-word.
        assert not slug.endswith("-")
        # The truncated tail should still be a real token from the title,
        # not a partially cut provider name.
        assert slug.split("-")[-1].isalnum()

    def test_long_single_token_hard_truncated(self) -> None:
        """One pathological token longer than the budget gets a hard slice."""
        title = "x" * 200
        slug = derive_step_slug(title)
        assert len(slug) <= 40
        assert slug == "x" * 40


# --- derive_detail_path ----------------------------------------------------


class TestDeriveDetailPath:
    def test_default_layout(self, tmp_path: Path) -> None:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(3)
        assert (
            derive_detail_path(plan_path, plan, step)
            == tmp_path / "plan-details" / "foo" / "03-build.md"
        )

    def test_zero_pads_step_id(self, tmp_path: Path) -> None:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)  # id=1 → "01-..."
        path = derive_detail_path(plan_path, plan, step)
        assert path.name == "01-wire-up-renderer.md"

    def test_strips_priority_prefix_from_plan_slug(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "1-foo-bar.md"
        plan_path.write_text(_DETAIL_PLAN, encoding="utf-8")
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        path = derive_detail_path(plan_path, plan, step)
        # Plan slug is "foo-bar" (digit prefix stripped).
        assert path.parent == tmp_path / "plan-details" / "foo-bar"

    def test_keeps_stem_when_no_priority_prefix(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "manual.md"
        plan_path.write_text(_DETAIL_PLAN, encoding="utf-8")
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        path = derive_detail_path(plan_path, plan, step)
        assert path.parent == tmp_path / "plan-details" / "manual"


class TestFindUnreferencedDetailForStep:
    """`find_unreferenced_detail_for_step` returns the step's canonical
    detail file when it's on disk, so the adoption pre-pass can reattach
    the pointer instead of clobbering it via a fresh author. Restricted to
    the canonical name — a slug-drift sibling is a superseded orphan the
    authoring path re-authors and archives, not an adoption candidate."""

    def _bundle(self, tmp_path: Path) -> Path:
        # _write_detail_plan → plan `2-foo.md`, slug `foo`.
        d = tmp_path / "plan-details" / "foo"
        d.mkdir(parents=True)
        return d

    def test_returns_canonical_when_present(self, tmp_path: Path) -> None:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(3)  # canonical name 03-build.md
        canonical = self._bundle(tmp_path) / "03-build.md"
        canonical.write_text("# Build\n", encoding="utf-8")
        assert (
            find_unreferenced_detail_for_step(plan_path, plan, step)
            == canonical
        )

    def test_none_when_no_file_on_disk(self, tmp_path: Path) -> None:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(3)
        assert find_unreferenced_detail_for_step(plan_path, plan, step) is None

    def test_ignores_slug_drift_sibling(self, tmp_path: Path) -> None:
        # Canonical name (03-build.md) absent; a stale-slug `03-` sibling
        # is NOT adopted — it's a superseded orphan for the archive sweep.
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(3)
        sibling = self._bundle(tmp_path) / "03-old-title-slug.md"
        sibling.write_text("# Old\n", encoding="utf-8")
        assert find_unreferenced_detail_for_step(plan_path, plan, step) is None

    def test_none_when_bundle_dir_absent(self, tmp_path: Path) -> None:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(3)
        # No plan-details/foo/ directory created at all.
        assert find_unreferenced_detail_for_step(plan_path, plan, step) is None


class TestPlanSlugHelper:
    def test_strips_leading_digit_prefix(self, tmp_path: Path) -> None:
        assert _plan_slug(tmp_path / "1-foo-bar.md") == "foo-bar"

    def test_keeps_stem_when_first_part_isnt_digit(
        self, tmp_path: Path
    ) -> None:
        assert _plan_slug(tmp_path / "manual.md") == "manual"

    def test_only_strips_when_dash_separator_present(
        self, tmp_path: Path
    ) -> None:
        # No `-`, so the stem is treated as the slug verbatim.
        assert _plan_slug(tmp_path / "1foo.md") == "1foo"


# --- render_detail_prompt --------------------------------------------------


class TestRenderDeclaredRiskContext:
    @pytest.mark.parametrize(
        ("risk_profile", "rationale"),
        [
            (RiskProfile.LOW, "The change stays within one well-tested helper."),
            (RiskProfile.STANDARD, "The change crosses normal application paths."),
            (RiskProfile.HIGH, "The change affects an externally visible boundary."),
        ],
    )
    def test_render_declared_risk_context_for_explicit_profiles(
        self, risk_profile: RiskProfile, rationale: str
    ) -> None:
        plan = Plan(
            title="Risk context plan",
            status=PlanStatus.IN_PROGRESS,
            priority=Priority.MEDIUM,
            risk_profile=risk_profile,
            risk_profile_rationale=rationale,
            steps=[Step(id=1, title="Render context")],
        )

        context = render_declared_risk_context(plan)

        assert f"`{risk_profile.value}`" in context
        assert rationale in context
        assert "advisory" in context.lower()
        assert "procedure proportionate" in context
        assert "grounding requirements" in context
        assert "test duties" in context
        assert "safety review" in context
        assert "explain the mismatch" in context

    def test_render_declared_risk_context_omits_legacy_plan(self) -> None:
        plan = Plan(
            title="Legacy risk context plan",
            status=PlanStatus.IN_PROGRESS,
            priority=Priority.MEDIUM,
            steps=[Step(id=1, title="Render context")],
        )

        assert plan.effective_risk_profile is RiskProfile.STANDARD
        assert render_declared_risk_context(plan) == ""


class TestRenderDetailPrompt:
    def test_detail_prompt_renders_supplied_risk_context_block(
        self, tmp_path: Path
    ) -> None:
        plan = parse_plan(_write_detail_plan(tmp_path))
        risk_context_block = "## Test risk context\n\nSUPPLIED-RISK-CONTEXT\n\n"
        blocks: list[tuple[str, int]] = []

        prompt = render_detail_prompt(
            plan,
            plan.step_by_id(1),
            repo_root=tmp_path,
            risk_context_block=risk_context_block,
            collect_blocks=blocks,
        )

        assert prompt.index("SUPPLIED-RISK-CONTEXT") < prompt.index("## Step")
        assert dict(blocks)["risk-context"] == len(risk_context_block.encode("utf-8"))

    def test_detail_prompt_reserves_the_marker_slot_without_declaring_a_version(
        self, tmp_path: Path
    ) -> None:
        """The rendered prompt tells the model the line after the H1 is
        plan-tool's, names the marker prefix, but never shows a versioned
        marker — the model can never propose the value the writer picks."""
        plan = parse_plan(_write_detail_plan(tmp_path))

        prompt = render_detail_prompt(
            plan, plan.step_by_id(1), repo_root=tmp_path,
        )

        assert "plan-tool:detail-format-version" in prompt
        assert not re.search(
            r"plan-tool:detail-format-version:\s*\d", prompt
        )
        assert "${" not in prompt


    def test_source_excerpt_contract_survives_cleanup(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        readable = tmp_path / "handlers.py"
        unreadable = tmp_path / "unreadable.py"
        readable.write_text(
            "\n".join(f"LEADING_FILLER_{i} = {i}" for i in range(80))
            + "\n\nclass TargetHandler:\n    pass\n",
            encoding="utf-8",
        )
        unreadable.write_text("def hidden():\n    pass\n", encoding="utf-8")
        plan = Plan(
            title="Detail Test Plan",
            status=PlanStatus.IN_PROGRESS,
            priority=Priority.MEDIUM,
            steps=[
                Step(
                    id=1,
                    title="Implement TargetHandler",
                    files=["handlers.py", "missing.py", "unreadable.py"],
                )
            ],
        )
        original_read_text = Path.read_text

        def fake_read_text(path: Path, *args, **kwargs) -> str:
            if path == unreadable:
                raise OSError("permission denied")
            return original_read_text(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", fake_read_text)

        prompt = render_detail_prompt(
            plan, plan.step_by_id(1), repo_root=tmp_path, max_file_bytes=180
        )

        assert "### `handlers.py`" in prompt
        assert "class TargetHandler" in prompt
        assert "LEADING_FILLER_0" not in prompt
        assert "excerpt_kind: symbol" in prompt
        assert "```\n" in prompt
        assert "### `missing.py` _(not on disk)_" in prompt
        assert "### `unreadable.py` _(unreadable: permission denied)_" in prompt

    def test_uses_symbol_excerpt_for_declared_python_file(
        self, tmp_path: Path
    ) -> None:
        source_path = tmp_path / "handlers.py"
        source_path.write_text(
            "\n".join(f"LEADING_FILLER_{i} = {i}" for i in range(80))
            + "\n\nclass TargetHandler:\n    def run(self):\n        return 42\n",
            encoding="utf-8",
        )
        plan = Plan(
            title="Detail Test Plan",
            status=PlanStatus.IN_PROGRESS,
            priority=Priority.MEDIUM,
            steps=[
                Step(
                    id=1,
                    title="Implement TargetHandler",
                    files=["handlers.py"],
                )
            ],
        )
        prompt = render_detail_prompt(
            plan, plan.step_by_id(1), repo_root=tmp_path, max_file_bytes=180
        )

        assert "class TargetHandler" in prompt
        assert "LEADING_FILLER_0" not in prompt
        assert "excerpt_kind: symbol" in prompt

    def test_preserves_missing_unreadable_and_no_files_contracts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        readable = tmp_path / "readable.py"
        unreadable = tmp_path / "unreadable.py"
        readable.write_text("def readable():\n    return True\n", encoding="utf-8")
        unreadable.write_text("def unreadable():\n    return False\n", encoding="utf-8")
        plan = Plan(
            title="Detail Test Plan",
            status=PlanStatus.IN_PROGRESS,
            priority=Priority.MEDIUM,
            steps=[
                Step(
                    id=1,
                    title="Read readable",
                    files=["readable.py", "missing.py", "unreadable.py"],
                ),
                Step(id=2, title="No files"),
            ],
        )
        original_read_text = Path.read_text

        def fake_read_text(path: Path, *args, **kwargs) -> str:
            if path == unreadable:
                raise OSError("permission denied")
            return original_read_text(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", fake_read_text)

        prompt = render_detail_prompt(plan, plan.step_by_id(1), repo_root=tmp_path)
        no_files_prompt = render_detail_prompt(
            plan, plan.step_by_id(2), repo_root=tmp_path
        )

        assert "`missing.py` _(not on disk)_" in prompt
        assert "`unreadable.py` _(unreadable: permission denied)_" in prompt
        assert "def readable" in prompt
        assert "_no files declared_" in no_files_prompt

    def test_renders_no_match_bounded_fallback_preview(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "misc.py").write_text(
            "def alpha():\n    return 'alpha'\n" + ("x = 1\n" * 200),
            encoding="utf-8",
        )
        plan = Plan(
            title="Detail Test Plan",
            status=PlanStatus.IN_PROGRESS,
            priority=Priority.MEDIUM,
            steps=[
                Step(id=1, title="Implement zzzzzz", files=["misc.py"])
            ],
        )
        prompt = render_detail_prompt(
            plan, plan.step_by_id(1), repo_root=tmp_path, max_file_bytes=120
        )

        assert "excerpt_kind: fallback" in prompt
        assert "fallback_reason: no-symbol-match" in prompt
        assert "truncated: true" in prompt
        assert "fallback preview: no-symbol-match" in prompt
        assert "x = 1\n" * 200 not in prompt

    def test_preserves_truncation_marker_for_excerpted_large_file(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "handlers.py").write_text(
            "\n".join(f"LEADING_FILLER_{i} = {i}" for i in range(80))
            + "\n\nclass TargetHandler:\n    pass\n"
            + "\n".join(f"TRAILING_FILLER_{i} = {i}" for i in range(80)),
            encoding="utf-8",
        )
        plan = Plan(
            title="Detail Test Plan",
            status=PlanStatus.IN_PROGRESS,
            priority=Priority.MEDIUM,
            steps=[
                Step(
                    id=1,
                    title="Implement TargetHandler",
                    files=["handlers.py"],
                )
            ],
        )
        prompt = render_detail_prompt(
            plan, plan.step_by_id(1), repo_root=tmp_path, max_file_bytes=220
        )

        assert "class TargetHandler" in prompt
        assert "_(truncated)_" in prompt
        assert "truncated: true" in prompt

    def test_uses_step_title_and_path_symbols_for_each_file(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "title_match.py").write_text(
            "def first_symbol():\n    return 1\n"
            + ("PADDING = 1\n" * 80)
            + "\ndef TitleSymbol():\n    return 2\n",
            encoding="utf-8",
        )
        (tmp_path / "path_symbol.py").write_text(
            "def first_symbol():\n    return 1\n"
            + ("PADDING = 1\n" * 80)
            + "\ndef path_symbol():\n    return 2\n",
            encoding="utf-8",
        )
        plan = Plan(
            title="Detail Test Plan",
            status=PlanStatus.IN_PROGRESS,
            priority=Priority.MEDIUM,
            steps=[
                Step(
                    id=1,
                    title="Implement TitleSymbol",
                    files=["title_match.py", "path_symbol.py"],
                )
            ],
        )
        prompt = render_detail_prompt(
            plan, plan.step_by_id(1), repo_root=tmp_path, max_file_bytes=180
        )

        assert "def TitleSymbol" in prompt
        assert "def path_symbol" in prompt
        assert "def first_symbol" not in prompt

    def test_embeds_plan_and_step_metadata(self, tmp_path: Path) -> None:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(3)
        prompt = render_detail_prompt(plan, step, repo_root=tmp_path)

        assert "Detail Test Plan" in prompt
        assert "Build it" in prompt
        assert "complexity: unknown" in prompt  # step.complexity unset on id=3
        assert "depends_on: 1" in prompt

    def test_embeds_confirmed_project_context(self, tmp_path: Path) -> None:
        initialize_project_profile(
            tmp_path,
            intent="Keep the implementation narrow.",
            non_goals=("Do not add a service.",),
            decisions=("Prefer reversible changes.",),
        )
        plan = parse_plan(_write_detail_plan(tmp_path))

        for prompt in (
            render_detail_prompt(plan, plan.step_by_id(1), repo_root=tmp_path),
        ):
            assert "Keep the implementation narrow." in prompt
            assert "Do not add a service." in prompt
            assert "Prefer reversible changes." in prompt

    def test_project_context_invalidates_detail_checkpoint_hash(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_detail_plan(tmp_path)
        step = parse_plan(plan_path).step_by_id(1)
        empty = _detail_step_input_hash(plan_path, step)
        assert empty == _detail_step_input_hash(plan_path, step, project_context="")
        assert empty != _detail_step_input_hash(
            plan_path, step, project_context="intent: changed"
        )

    def test_detail_runs_snapshot_project_context_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import detail as detail_module

        plan_path = _write_detail_plan(tmp_path)
        calls: list[Path] = []

        def snapshot(repo_root: Path) -> str:
            calls.append(repo_root)
            return "## Confirmed project context\n\nRun snapshot marker"

        monkeypatch.setattr(detail_module, "project_profile_context", snapshot)
        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            dry_run=True,
            reporter=NullReporter(),
        )

        assert calls == [tmp_path]
        assert all("Run snapshot marker" in (result.prompt or "") for result in results)


    def test_output_path_pins_canonical_and_forbids_self_write(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        out = tmp_path / "docs" / "plan-details" / "x" / "01-foo.md"
        prompt = render_detail_prompt(
            plan, step, repo_root=tmp_path, output_path=out
        )
        assert "Do not create, write, or edit any file." in prompt
        # repo-relative canonical path is named so the model has no reason
        # to invent its own (uncapped-slug) path.
        assert "`docs/plan-details/x/01-foo.md`" in prompt

    def test_output_path_omitted_drops_path_clause_keeps_guard(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        prompt = render_detail_prompt(plan, step, repo_root=tmp_path)
        # Guard still present without a path; no leftover placeholder.
        assert "Do not create, write, or edit any file." in prompt
        assert "canonical path `" not in prompt
        assert "${output_path_block}" not in prompt

    def test_unset_complexity_renders_unknown(self, tmp_path: Path) -> None:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(3)
        prompt = render_detail_prompt(plan, step, repo_root=tmp_path)
        assert "complexity: unknown" in prompt

    def test_set_complexity_rendered(self, tmp_path: Path) -> None:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)  # complexity=low
        prompt = render_detail_prompt(plan, step, repo_root=tmp_path)
        assert "complexity: low" in prompt

    def test_no_depends_on_renders_none(self, tmp_path: Path) -> None:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)  # no depends_on
        prompt = render_detail_prompt(plan, step, repo_root=tmp_path)
        assert "depends_on: (none)" in prompt

    def test_embeds_file_contents(self, tmp_path: Path) -> None:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        prompt = render_detail_prompt(plan, step, repo_root=tmp_path)
        assert "def render(plan)" in prompt  # body of renderer.py
        assert "`renderer.py`" in prompt

    def test_truncates_oversized_files(self, tmp_path: Path) -> None:
        plan_path = _write_detail_plan(tmp_path)
        # Bloat foo.py past the 100-byte cap so truncation triggers.
        (tmp_path / "foo.py").write_text("x" * 9000, encoding="utf-8")
        plan = parse_plan(plan_path)
        step = plan.step_by_id(3)
        prompt = render_detail_prompt(
            plan, step, repo_root=tmp_path, max_file_bytes=100
        )
        assert "_(truncated)_" in prompt
        # Not the whole 9000-byte body.
        assert "x" * 9000 not in prompt

    def test_missing_file_marked_inline(self, tmp_path: Path) -> None:
        plan_path = _write_detail_plan(tmp_path)
        # Drop bar.py before rendering so the prompt has to handle missing.
        (tmp_path / "bar.py").unlink()
        plan = parse_plan(plan_path)
        step = plan.step_by_id(3)
        prompt = render_detail_prompt(plan, step, repo_root=tmp_path)
        assert "`bar.py`" in prompt
        assert "(not on disk)" in prompt

    def test_no_siblings_renders_placeholder(self, tmp_path: Path) -> None:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        prompt = render_detail_prompt(plan, step, repo_root=tmp_path)
        assert "no sibling detail files yet" in prompt

    def test_embeds_siblings_when_present(self, tmp_path: Path) -> None:
        plan_path = _write_detail_plan(tmp_path)
        details_dir = tmp_path / "plan-details" / "foo"
        details_dir.mkdir(parents=True)
        sibling = details_dir / "01-prior.md"
        sibling.write_text(
            "# Step 1 — Wire up renderer\n\nReference body.\n",
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)
        step = plan.step_by_id(3)
        prompt = render_detail_prompt(
            plan, step, repo_root=tmp_path, sibling_details=[sibling]
        )
        assert "Reference body." in prompt
        assert "01-prior.md" in prompt

    def test_skips_siblings_that_disappeared(self, tmp_path: Path) -> None:
        """A sibling listed by the orchestrator could vanish before render
        (rare, but defensive). The block should still render the placeholder
        rather than blowing up."""
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        prompt = render_detail_prompt(
            plan,
            step,
            repo_root=tmp_path,
            sibling_details=[tmp_path / "ghost.md"],
        )
        assert "no sibling detail files yet" in prompt

    def test_prompt_carries_references_instructions(
        self, tmp_path: Path
    ) -> None:
        """The detail prompt instructs claude to web-search for dev/API
        docs (starting from any plan-level references) and emit them in
        an optional ``## References`` section."""
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        prompt = render_detail_prompt(plan, step, repo_root=tmp_path)
        assert "## References" in prompt
        assert "web-search" in prompt.lower()
        assert "Plan-level references" in prompt
        assert "_no plan-level references available_" in prompt

    def test_prompt_describes_conditional_input_without_requiring_it(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        prompt = render_detail_prompt(plan, step, repo_root=tmp_path)
        assert "emit `## Input` only when" in prompt
        assert "owning step id and outcome" in prompt

        produced = prompt.split("## What to produce", 1)[1]
        produced = produced.split("## Constraints", 1)[0]
        advertised = {
            line.strip()
            for line in produced.splitlines()
            if line.strip().startswith("## ")
        }
        assert "## Input" not in advertised


class TestRenderDetailPromptABMode:
    """The detail authoring prompt is A/B-conditional. COMBINED (default, no
    ``split_mode``) is the legacy prompt: the model greps for shared logic
    itself and runs the purity self-check, with no finds section. SPLIT receives
    a prior sweep's finds, places them, and drops the self-check (detail-quality
    owns purity)."""

    # The seven required produced-file H2 headings, advertised in the
    # `## What to produce` block; References/Deferred are optional.
    REQUIRED_HEADINGS = (
        "## Summary",
        "## Table of Contents",
        "## Why",
        "## Files (creates vs edits)",
        "## Implementation",
        "## Tests",
        "## Acceptance criteria",
    )

    def test_combined_default_inlines_grep_directive(self, tmp_path: Path) -> None:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        prompt = render_detail_prompt(plan, step, repo_root=tmp_path)
        assert "other locations that exercise the same logic" in prompt
        # No finds section in combined mode.
        assert "shared locations surfaced by a prior sweep" not in prompt

    def test_combined_default_has_self_check(self, tmp_path: Path) -> None:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        prompt = render_detail_prompt(plan, step, repo_root=tmp_path)
        assert "Step purity self-check" in prompt
        assert "MIXED-STEP" in prompt

    def test_combined_guidance_names_reuse_local_and_separate_routes(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        prompt = render_detail_prompt(plan, step, repo_root=tmp_path)

        assert "other locations that exercise the same logic" in prompt
        assert "**Reuse unchanged:**" in prompt
        assert "**Bounded local work:**" in prompt
        assert "**Separate shared work:**" in prompt
        assert "existing consumer behavior and current schema" in prompt
        assert "shared authority, lifecycle, identity, precedence" in prompt

    def test_split_drops_grep_and_self_check(self, tmp_path: Path) -> None:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        prompt = render_detail_prompt(
            plan, step, repo_root=tmp_path, split_mode=True
        )
        # The model no longer greps for shared logic itself...
        assert "other locations that exercise the same logic" not in prompt
        # ...and the always-on self-check is gone (detail-quality owns it).
        assert "Step purity self-check" not in prompt
        # The fold-the-finds directive + finds section are present instead.
        assert "Fold the **Foundational-logic finds**" in prompt
        assert "shared locations surfaced by a prior sweep" in prompt

    def test_split_injects_finds_block(self, tmp_path: Path) -> None:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        prompt = render_detail_prompt(
            plan,
            step,
            repo_root=tmp_path,
            split_mode=True,
            foundational_logic_block="**Foundational logic:** path resolver",
        )
        assert "**Foundational logic:** path resolver" in prompt

    def test_split_guidance_names_reuse_local_and_separate_routes(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        prompt = render_detail_prompt(
            plan,
            step,
            repo_root=tmp_path,
            split_mode=True,
            foundational_logic_block="**Foundational logic:** path resolver",
        )

        assert "Foundational-logic finds" in prompt
        assert "**Reuse unchanged:**" in prompt
        assert "**Bounded local work:**" in prompt
        assert "**Separate shared work:**" in prompt

    def test_split_guidance_does_not_repeat_the_foundational_search(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        prompt = render_detail_prompt(
            plan, step, repo_root=tmp_path, split_mode=True
        )

        assert "Fold the **Foundational-logic finds**" in prompt
        assert "other locations that exercise the same logic" not in prompt
        assert "Step purity self-check" not in prompt

    def test_shared_location_alone_does_not_require_shared_work(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        prompt = render_detail_prompt(plan, step, repo_root=tmp_path)
        normalized_prompt = " ".join(prompt.split())

        assert "A shared file, helper, caller count, or" in normalized_prompt
        assert "Foundational-logic relation is evidence to inspect" in normalized_prompt
        assert "never by itself a reason to widen this focused detail" in normalized_prompt
        assert "a common path, helper, or sweep" in normalized_prompt
        assert "finding cannot override this step's scope fence" in normalized_prompt

    def test_existing_prompt_structure_remains_unchanged(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        for split in (False, True):
            prompt = render_detail_prompt(
                plan, step, repo_root=tmp_path, split_mode=split
            )
            assert "${" not in prompt
            assert "## Shared logic" not in prompt
            produced = prompt.split("## What to produce", 1)[1]
            produced = produced.split("## Constraints", 1)[0]
            advertised = {
                line.strip()
                for line in produced.splitlines()
                if line.strip().startswith("## ")
            }
            assert advertised == set(self.REQUIRED_HEADINGS) | {
                "## References",
                "## Applicable guardrails",
                "## Deferred",
            }

    def test_existing_audit_bullets_unchanged(self, tmp_path: Path) -> None:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        prompt = render_detail_prompt(plan, step, repo_root=tmp_path)
        assert "Use Grep to find the public symbols" in prompt
        assert "Use Read on sibling files" in prompt
        assert "the already-implemented signal above flagged any hits" in prompt
        assert "Use Glob to locate the matching test file(s)" in prompt
        assert "Do not narrate the audit in the response" in prompt

    def test_no_new_required_heading_advertised(self, tmp_path: Path) -> None:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        prompt = render_detail_prompt(plan, step, repo_root=tmp_path)
        # The audit must not invent a produced-file heading for shared logic.
        assert "## Shared logic" not in prompt
        # The produced-file required structure lives in the `## What to
        # produce` section, before the template's own `## Constraints`.
        produced = prompt.split("## What to produce", 1)[1]
        produced = produced.split("## Constraints", 1)[0]
        advertised = {
            line.strip()
            for line in produced.splitlines()
            if line.strip().startswith("## ")
        }
        known = set(self.REQUIRED_HEADINGS) | {
            "## References",
            "## Applicable guardrails",
            "## Deferred",
        }
        assert advertised == known


# --- parse_detail_response -------------------------------------------------


_FIVE_SECTIONS = (
    "# Step 3 — Foo\n\n"
    "## Summary\n\nReviewer-facing overview of the step.\n\n"
    "## Table of Contents\n\n"
    "- [Why](#why) — motivation\n"
    "- [Files](#files) — paths touched\n"
    "- [Implementation](#implementation) — walkthrough\n"
    "- [Tests](#tests) — coverage\n"
    "- [Acceptance criteria](#acceptance-criteria) — verifiable bullets\n\n"
    "## Why\n\nReason.\n\n"
    "## Files\n\n- foo.py\n\n"
    "## Implementation\n\nWalkthrough.\n\n"
    "## Tests\n\n- one test\n\n"
    "## Acceptance criteria\n\n- returns 42\n"
)


class TestParseDetailResponse:
    def test_accepts_clean_markdown(self) -> None:
        assert parse_detail_response(_FIVE_SECTIONS) == _FIVE_SECTIONS.strip()

    def test_accepts_clean_markdown_without_input(self) -> None:
        out = parse_detail_response(_FIVE_SECTIONS)
        assert out is not None
        assert "## Input" not in out

    def test_accepts_and_preserves_optional_input(self) -> None:
        body = _FIVE_SECTIONS.replace(
            "## Files\n\n",
            (
                "## Input\n\n"
                "- Reads step 1's drift audit JSON outcome.\n\n"
                "## Files\n\n"
            ),
        )
        out = parse_detail_response(body)
        assert out == body.strip()
        assert "## Input" in out
        assert "drift audit JSON" in out

    def test_missing_input_alone_is_not_stubbed_or_rejected(self) -> None:
        out = parse_detail_response(_FIVE_SECTIONS)
        assert out is not None
        assert "stub:" not in out
        assert "## Input" not in out

    def test_strips_markdown_fence(self) -> None:
        wrapped = f"```markdown\n{_FIVE_SECTIONS}```"
        out = parse_detail_response(wrapped)
        assert out is not None
        assert out.startswith("# Step 3 — Foo")
        assert "```" not in out

    def test_strips_unfenced_code_block(self) -> None:
        wrapped = f"```\n{_FIVE_SECTIONS}```"
        out = parse_detail_response(wrapped)
        assert out is not None
        assert out.startswith("# Step 3 — Foo")
        assert "```" not in out

    def test_rejects_empty(self) -> None:
        assert parse_detail_response("") is None
        assert parse_detail_response("   \n  ") is None

    def test_rejects_response_without_heading(self) -> None:
        assert parse_detail_response("Sorry, I can't help.") is None

    def test_tolerates_leading_blank_lines(self) -> None:
        # `text.strip()` removes them before the heading check.
        body = f"\n\n{_FIVE_SECTIONS}"
        out = parse_detail_response(body)
        assert out is not None
        assert out.startswith("# Step 3 — Foo")

    def test_tolerates_unmatched_leading_fence(self) -> None:
        """Opening fence with no closing fence: drop the fence, accept rest."""
        out = parse_detail_response(f"```markdown\n{_FIVE_SECTIONS}")
        assert out is not None
        assert out.startswith("# Step 3 — Foo")
        assert "```" not in out

    def test_tolerates_unmatched_trailing_fence(self) -> None:
        """Closing fence with no opening fence: drop the fence, accept rest."""
        out = parse_detail_response(f"{_FIVE_SECTIONS}\n```")
        assert out is not None
        assert out.startswith("# Step 3 — Foo")
        assert "```" not in out

    def test_strips_leading_preamble_before_heading(self) -> None:
        """One-line courtesy preamble is dropped, body parses normally."""
        body = f"Here is the detail file:\n\n{_FIVE_SECTIONS}"
        out = parse_detail_response(body)
        assert out is not None
        assert out.startswith("# Step 3 — Foo")
        assert "Here is the detail" not in out

    def test_strips_preamble_and_fence_together_via_the_wrapper_sentinel(self) -> None:
        """A fence-wrapped response with no sentinel is unparseable by
        design (see ``test_fence_wrapped_response_without_sentinel_is_unparseable``)
        — the wrapper sentinel is the supported way to combine a preamble
        with a fenced or commented response."""
        raw = (
            "Sure, here you go:\n\n"
            "<!-- plan-tool:detail-response-start -->\n"
            f"```markdown\n{_FIVE_SECTIONS}```"
            "\n<!-- plan-tool:detail-response-end -->\n"
        )
        out = parse_detail_response(raw)
        assert out is not None
        assert out.startswith("# Step 3 — Foo")
        assert "```" not in out
        assert "Sure, here" not in out

    def test_fence_wrapped_response_without_sentinel_is_unparseable(self) -> None:
        """A response entirely wrapped in a fence, with no sentinel and no
        plain unwrapped title, is unparseable — this is the fail-closed
        default a prior positional-heuristic design replaced: guessing
        which fenced block was the real answer was defeated by a new
        adversarial input across several rounds (2026-09-08
        authored-artifact-format-version handoff, review passes 5-9)."""
        raw = f"Sure, here you go:\n\n```markdown\n{_FIVE_SECTIONS}```"
        assert parse_detail_response(raw) is None

    def test_skips_heading_like_preamble_before_the_detail_title(self) -> None:
        body = (
            "# Note: this depends on a prior migration\n\n"
            "```markdown\n"
            "# Example heading, not the detail title\n"
            "```\n\n"
            + _FIVE_SECTIONS
        )

        out = parse_detail_response(body)

        assert out is not None
        assert out.startswith("# Step 3 — Foo")
        assert "# Note:" not in out
        assert stamp_detail_format_version_marker(out).startswith(
            "# Step 3 — Foo\n\n"
            "<!-- plan-tool:detail-format-version: 1 -->"
        )

    def test_preserves_title_when_a_later_unfenced_h1_interrupts_sections(self) -> None:
        body = _FIVE_SECTIONS.replace(
            "## Table of Contents\n\n",
            "# Accidental heading, unfenced\n\n## Table of Contents\n\n",
        )

        assert parse_detail_response(body) == body.strip()

    def test_sentinel_wrapped_response_ignores_an_earlier_fenced_prose_example(self) -> None:
        """A courtesy fenced example in the preamble, before the sentinel
        pair, is excluded unconditionally — the sentinel is a substring
        boundary, not an inference about which fence is real."""
        raw = (
            "Do not format it like this:\n\n"
            "```\n# Bad title\n```\n\n"
            "<!-- plan-tool:detail-response-start -->\n"
            f"```markdown\n{_FIVE_SECTIONS}```"
            "\n<!-- plan-tool:detail-response-end -->\n"
        )

        out = parse_detail_response(raw)

        assert out is not None
        assert out.startswith("# Step 3 — Foo")
        assert "# Bad title" not in out

    def test_rejects_bare_skeleton_missing_sections(self) -> None:
        """An H1 with no H2s is missing >1 section: hard reject."""
        assert parse_detail_response("# Step 3 — Foo\n\nIntro.\n") is None

    def test_synthesizes_stub_when_one_section_missing(self) -> None:
        """Missing exactly one section: synthesize a stub so the file is well-formed."""
        body = (
            "# Title\n\n"
            "## Summary\n\nx\n\n"
            "## Table of Contents\n\n- x\n\n"
            "## Why\n\nx\n\n"
            "## Files\n\nx\n\n"
            "## Implementation\n\nx\n\n"
            "## Tests\n\nx\n"
            # no Acceptance criteria
        )
        out = parse_detail_response(body)
        assert out is not None
        assert "## Acceptance criteria" in out
        assert "stub:" in out

    def test_synthesizes_stub_when_summary_missing(self) -> None:
        """Missing Summary alone: synthesize the stub heading."""
        body = (
            "# Title\n\n"
            "## Table of Contents\n\n- x\n\n"
            "## Why\n\nx\n\n"
            "## Files\n\nx\n\n"
            "## Implementation\n\nx\n\n"
            "## Tests\n\nx\n\n"
            "## Acceptance criteria\n\nx\n"
        )
        out = parse_detail_response(body)
        assert out is not None
        assert "## Summary" in out
        assert "stub:" in out

    def test_synthesizes_stub_when_table_of_contents_missing(self) -> None:
        """Missing Table of Contents alone: synthesize the stub heading."""
        body = (
            "# Title\n\n"
            "## Summary\n\nx\n\n"
            "## Why\n\nx\n\n"
            "## Files\n\nx\n\n"
            "## Implementation\n\nx\n\n"
            "## Tests\n\nx\n\n"
            "## Acceptance criteria\n\nx\n"
        )
        out = parse_detail_response(body)
        assert out is not None
        assert "## Table of Contents" in out
        assert "stub:" in out

    def test_rejects_when_two_or_more_sections_missing(self) -> None:
        body = (
            "# Title\n\n"
            "## Summary\n\nx\n\n"
            "## Table of Contents\n\n- x\n\n"
            "## Why\n\nx\n\n"
            "## Files\n\nx\n\n"
            "## Implementation\n\nx\n"
            # no Tests, no Acceptance criteria
        )
        assert parse_detail_response(body) is None

    def test_accepts_trailing_modifier_on_heading(self) -> None:
        """`## Why we did this` still satisfies `## Why`."""
        body = (
            "# Title\n\n"
            "## Summary of the step\n\nx\n\n"
            "## Table of Contents\n\n- x\n\n"
            "## Why we did this\n\nx\n\n"
            "## Files modified\n\nx\n\n"
            "## Implementation walkthrough\n\nx\n\n"
            "## Tests added\n\nx\n\n"
            "## Acceptance criteria\n\nx\n"
        )
        assert parse_detail_response(body) is not None

    def test_response_whose_first_heading_is_an_h2_has_no_h1_and_is_rejected(
        self,
    ) -> None:
        """A response starting at ``## Summary`` has no carrier H1 — the
        writer would have nowhere to stamp a format-version marker — so it
        is rejected even though all seven required H2s are present."""
        body = _FIVE_SECTIONS.replace("# Step 3 — Foo\n\n", "", 1)
        assert body.startswith("## Summary")
        assert parse_detail_response(body) is None

    def test_response_with_an_indented_h1_is_rejected_before_checkpoint(
        self,
    ) -> None:
        """An indented ``#`` is not a real H1 (``locate_detail_format_carrier``
        requires column 0), so no accepted response can later miss the
        writer's marker slot. A leading preamble line keeps the outer
        ``.strip()`` from unindenting the H1 candidate itself."""
        body = "Sure, here you go:\n\n" + "  " + _FIVE_SECTIONS
        assert parse_detail_response(body) is None

    def test_preamble_before_a_real_h1_is_still_stripped(self) -> None:
        """The tightened H1 rule preserves the existing preamble-skip
        leniency for prose preceding a real, unindented H1."""
        body = f"Sure, here's the detail file:\n\n{_FIVE_SECTIONS}"
        out = parse_detail_response(body)
        assert out is not None
        assert out.startswith("# Step 3 — Foo")
        assert "Sure, here" not in out

    def test_sentinel_wrapped_body_with_same_length_inner_fence_now_fails_closed(
        self,
    ) -> None:
        """Superseded 2026-09-11 (round-13 review, user-selected fix): a
        same-length nested example fence inside a sentinel-wrapped body
        made the scanner report the wrap's own true closing fence as a
        separate, later, unmatched-to-EOF span. Earlier rounds (9-12)
        trusted content in that trailing span as real, unfenced text so
        this exact case would parse — but that same trust let an
        illustrative, genuinely-never-closed fence elsewhere in a response
        (containing a coincidental end-marker-shaped line) silently
        truncate real content instead of being rejected (round-13 finding
        1). Marker search no longer opts into that leniency at all: it
        always excludes every fenced span, trailing unmatched one
        included, so this legitimate-but-rare same-length-nesting shape
        now fails closed (rejects, triggers a retry) rather than risking
        the corruption class finding 1 found. See DETAIL_FORMAT.md rule
        3.1 and the 2026-09-08 authored-artifact-format-version handoff's
        review pass 13 triage."""
        body = _FIVE_SECTIONS.replace(
            "## Implementation\n\nWalkthrough.",
            "## Implementation\n\n```python\ndef foo():\n    return 1\n```\n\nWalkthrough.",
        )
        raw = (
            "Sure, here's the detail file:\n\n"
            "<!-- plan-tool:detail-response-start -->\n"
            f"```markdown\n{body}```"
            "\n<!-- plan-tool:detail-response-end -->\n\n"
            "Let me know if you need anything else!"
        )

        assert parse_detail_response(raw) is None

    def test_sentinel_wrapped_body_with_two_same_length_inner_fences_now_fails_closed(
        self,
    ) -> None:
        """Same supersession as
        ``test_sentinel_wrapped_body_with_same_length_inner_fence_now_fails_closed``,
        for the two-nested-fence shape."""
        body = _FIVE_SECTIONS.replace(
            "## Implementation\n\nWalkthrough.",
            "## Implementation\n\n```python\ndef foo():\n    return 1\n```\n\nWalkthrough.",
        ).replace(
            "## Tests\n\n- one test",
            "## Tests\n\n```python\ndef test_foo():\n    assert foo() == 1\n```",
        )
        raw = (
            "Sure, here's the detail file:\n\n"
            "<!-- plan-tool:detail-response-start -->\n"
            f"```markdown\n{body}```"
            "\n<!-- plan-tool:detail-response-end -->\n\n"
            "Let me know if you need anything else!"
        )

        assert parse_detail_response(raw) is None

    def test_ambiguous_multi_wrapper_document_without_sentinel_is_unparseable(
        self,
    ) -> None:
        """Without a sentinel, a document containing more than one
        fence-wrapped candidate (regardless of whether a later one has a
        required, non-required, or no heading at all) is uniformly
        unparseable — there is no candidate selection to defeat, since
        none is attempted. This closes the whole class of "which fence is
        the real one" findings from review passes 7 and 8, rather than
        distinguishing decoy shapes."""
        raw = (
            "Sure, here's the detail file:\n\n"
            f"```markdown\n{_FIVE_SECTIONS}```\n\n"
            "```markdown\n# Note\n\n## Notes\n\nUnrelated trailing note.\n```\n"
        )

        assert parse_detail_response(raw) is None

    def test_later_invalid_wrapper_does_not_fall_back_to_an_earlier_example(self) -> None:
        """Without a sentinel, neither fence-wrapped candidate is a plain
        unwrapped title, so the response is unparseable regardless of which
        one is complete — not because of a "last wrapper wins" policy
        (there is no wrapper-selection mechanism at all)."""
        raw = (
            f"Preamble example:\n\n```markdown\n{_FIVE_SECTIONS}```\n\n"
            "Actual response:\n\n```markdown\n# Actual\n\n## Summary\n\nx\n```\n"
        )

        assert parse_detail_response(raw) is None

    def test_sentinel_wrapped_response_excludes_a_trailing_illustrative_snippet(
        self,
    ) -> None:
        """Content after the end marker — including a trailing fenced
        example whose first line looks like a heading — is excluded
        unconditionally, since extraction is a substring slice bounded by
        the two markers, not an inference about document shape. Without a
        sentinel, this same input is unparseable
        (``test_ambiguous_multi_wrapper_document_without_sentinel_is_unparseable``
        covers the analogous no-sentinel shape) — a prior positional design
        discarded or corrupted the real answer here instead (review pass 7)."""
        raw = (
            "Sure, here's the detail file:\n\n"
            "<!-- plan-tool:detail-response-start -->\n"
            f"```markdown\n{_FIVE_SECTIONS}```"
            "\n<!-- plan-tool:detail-response-end -->\n\n"
            "Note:\n\n```python\n# Example usage\nfoo()\n```\n"
        )

        out = parse_detail_response(raw)
        assert out == _FIVE_SECTIONS.strip()
        assert "Example usage" not in out

    def test_near_complete_trailing_wrapper_no_longer_silently_wins_without_a_sentinel(
        self,
    ) -> None:
        """Closes a residual accepted in review pass 8: without a
        sentinel, a document with a complete wrapper followed by a
        near-complete trailing decoy is unparseable, full stop — it does
        not silently return the decoy's content. The old "last wrapper
        wins" candidate-selection mechanism (and the residual it
        carried) no longer exists; there is nothing left to distinguish a
        "genuine-but-broken final attempt" from a decoy, because neither
        is guessed at anymore."""
        near_complete_decoy = _FIVE_SECTIONS.replace(
            "# Step 3 — Foo", "# Decoy"
        ).replace("## Acceptance criteria\n\n- returns 42\n", "")
        raw = (
            "Sure, here's the detail file:\n\n"
            f"```markdown\n{_FIVE_SECTIONS}```\n\n"
            f"```markdown\n{near_complete_decoy}```\n"
        )

        assert parse_detail_response(raw) is None

    def test_sentinel_markers_must_each_be_alone_on_their_own_line(self) -> None:
        """A sentinel-shaped phrase appearing inline (not alone on its own
        line) must not be mistaken for a real boundary — the structural
        guarantee the sentinel exists to provide would otherwise be
        defeated by ordinary prose or a fenced example quoting the
        marker syntax itself."""
        raw = (
            "Note: don't write `<!-- plan-tool:detail-response-start -->` "
            "inline like this.\n\n"
            f"```markdown\n{_FIVE_SECTIONS}```"
        )

        assert parse_detail_response(raw) is None

    def test_sentinel_wraps_an_unfenced_body_without_leaking_the_end_marker(
        self,
    ) -> None:
        """The sentinel's primary, non-adversarial use case: bracketing a
        response with no inner fence at all. Before this fix, the plain
        unwrapped path ran first (since the wrapped title is already
        unfenced), silently ignoring the end marker and everything after
        it — the literal end-marker line and trailing commentary leaked
        into the persisted body."""
        raw = (
            "Sure, here you go:\n\n"
            "<!-- plan-tool:detail-response-start -->\n"
            f"{_FIVE_SECTIONS}"
            "<!-- plan-tool:detail-response-end -->\n\n"
            "Let me know if you need anything else!"
        )

        out = parse_detail_response(raw)
        assert out == _FIVE_SECTIONS.strip()
        assert "detail-response-end" not in out
        assert "Let me know" not in out

    def test_sentinel_interacts_correctly_with_the_deferrals_envelope(self) -> None:
        """The deferrals envelope always follows the sentinel's end marker
        (never sits inside it) and parse_structured_detail_response's
        prefix-slice before the envelope still resolves to the correctly
        bounded sentinel body."""
        raw = (
            "<!-- plan-tool:detail-response-start -->\n"
            f"{_FIVE_SECTIONS}"
            "<!-- plan-tool:detail-response-end -->\n"
            '<!-- plan-tool-detail-deferrals\n{"deferrals": []}\n-->'
        )

        parsed = parse_structured_detail_response(raw)
        assert parsed is not None
        assert parsed.body == _FIVE_SECTIONS.strip()
        assert parsed.deferrals == ()

    def test_two_sentinel_pairs_are_ambiguous_and_unparseable(self) -> None:
        """More than one occurrence of either marker is ambiguous — the
        earlier (illustrative or decoy) pair must not win over the real
        one via an unanchored leftmost match, reintroducing the same class
        of positional guessing the sentinel replaced."""
        raw = (
            "Don't format it like this:\n\n"
            "<!-- plan-tool:detail-response-start -->\n"
            "# Bad\n"
            "<!-- plan-tool:detail-response-end -->\n\n"
            "<!-- plan-tool:detail-response-start -->\n"
            f"{_FIVE_SECTIONS}"
            "<!-- plan-tool:detail-response-end -->\n"
        )

        assert parse_detail_response(raw) is None

    def test_sentinel_tolerates_crlf_line_endings(self) -> None:
        """A fully compliant, sentinel-wrapped response using CRLF line
        endings throughout must not be unconditionally rejected."""
        raw = (
            "Sure, here you go:\r\n\r\n"
            "<!-- plan-tool:detail-response-start -->\r\n"
            + _FIVE_SECTIONS.replace("\n", "\r\n")
            + "<!-- plan-tool:detail-response-end -->\r\n"
        )

        out = parse_detail_response(raw)
        assert out is not None
        assert out.replace("\r\n", "\n") == _FIVE_SECTIONS.strip()

    def test_four_backtick_fence_without_sentinel_parses_cleanly(self) -> None:
        """A longer backtick run (4+) is a valid fence per CommonMark; the
        leading/trailing strip must recognize its closer the same way it
        recognizes a 3-backtick one, not leave a stray fence line behind."""
        raw = f"````markdown\n{_FIVE_SECTIONS}````"

        out = parse_detail_response(raw)
        assert out == _FIVE_SECTIONS.strip()
        assert "`" not in out

    def test_fenced_example_illustrating_the_sentinel_syntax_does_not_hijack_a_plain_response(
        self,
    ) -> None:
        """A plain, unwrapped, complete response whose body happens to
        fence an illustrative example of the sentinel syntax (e.g.
        documenting the mechanism) must still parse via the plain path —
        the fenced example is not a real sentinel, and matching it as one
        would reintroduce the exact 'fenced example misread as a real
        boundary' class this design exists to close."""
        body = _FIVE_SECTIONS.replace(
            "## Implementation\n\nWalkthrough.",
            "## Implementation\n\nExample of the sentinel syntax:\n"
            "```\n<!-- plan-tool:detail-response-start -->\n"
            "<!-- plan-tool:detail-response-end -->\n```",
        )

        assert parse_detail_response(body) == body.strip()

    def test_deferrals_offset_is_consistent_when_the_raw_response_has_leading_whitespace(
        self,
    ) -> None:
        """``parse_structured_detail_response`` must slice the same string
        it computed the deferrals-envelope match against — computing the
        match against a stripped copy while slicing the original silently
        truncates the persisted body by exactly the amount of leading
        whitespace stripped."""
        raw = (
            "\n\n"
            f"{_FIVE_SECTIONS}"
            '<!-- plan-tool-detail-deferrals\n{"deferrals": []}\n-->'
        )

        parsed = parse_structured_detail_response(raw)
        assert parsed is not None
        assert parsed.body == _FIVE_SECTIONS.strip()

    def test_deferrals_envelope_ignores_a_fenced_illustrative_example(self) -> None:
        """The deferrals search must not lock onto an earlier fenced
        example illustrating the envelope syntax — its greedy,
        end-anchored payload would otherwise swallow everything through to
        the real trailing envelope as one invalid JSON blob."""
        body = _FIVE_SECTIONS.replace(
            "## Why\n\nReason.",
            "## Why\n\nExample:\n```\n<!-- plan-tool-detail-deferrals\n{}\n-->\n```",
        )
        raw = body + '<!-- plan-tool-detail-deferrals\n{"deferrals": []}\n-->'

        parsed = parse_structured_detail_response(raw)
        assert parsed is not None
        assert parsed.body == body.strip()
        assert parsed.deferrals == ()

    def test_legitimate_trailing_fence_with_no_leading_wrap_is_preserved(self) -> None:
        """A response with no leading fence (a plain, unwrapped title)
        that legitimately ends with a fenced example (e.g. ``## Tests``
        showing command output, reordered last) must keep that fence
        intact — it is real content, not a whole-response wrapper's
        closer."""
        body = (
            _FIVE_SECTIONS.split("## Tests")[0]
            + "## Acceptance criteria\n\n- returns 42\n\n"
            + "## Tests\n\n~~~\npytest output here\n~~~"
        )

        out = parse_detail_response(body)
        assert out == body.strip()
        assert out.endswith("~~~")

    def test_no_leading_wrap_protects_real_content_trapped_in_a_dangling_fence(
        self,
    ) -> None:
        """Round-14 review: a trailing fence-close-shaped line must only be
        stripped when the scanner finds it to be a genuinely partner-less
        opener (nothing fenced before it). When an earlier, real opener
        exists (the model opened a fence and never validly closed it —
        e.g. a 4-backtick opener with only a 3-backtick line after it,
        which can never close it per CommonMark run-length rules), the
        whole dangling region is real, load-bearing content and must be
        preserved, not silently truncated by stripping its last line —
        the exact hazard class rule 3.1 already closed for marker search."""
        body = _FIVE_SECTIONS.replace(
            "## Acceptance criteria\n\n- returns 42\n",
            "## Acceptance criteria\n\n````\nREAL LOAD-BEARING LINE THAT SHOULD SURVIVE\n```",
        )

        out = parse_detail_response(body)
        assert out is not None
        assert "REAL LOAD-BEARING LINE THAT SHOULD SURVIVE" in out
        assert out.endswith("```")

    def test_leading_wrap_closed_early_protects_an_unrelated_later_example(
        self,
    ) -> None:
        """Round-15 review: the third instance of the same hazard class.
        When the document opens with a fence that validly closes early
        (a real, complete span ending well before EOF), the trailing
        strip must not assume a whole-document-wrap just because the
        document's last line happens to share the leading opener's
        character and run length — an unrelated, later, separately-fenced
        example can coincidentally match. Only strip the trailing line
        when the scanner's own pairing shows the leading fence's span
        actually reaching EOF, or the leading fence never validly closes
        at all (the genuine whole-wrap and scanner-artifact cases)."""
        body = (
            _FIVE_SECTIONS.rstrip("\n")
            + "\n```\n\n## Verification\n\nRun it:\n\n```\npytest -k foo\n```"
        )
        raw = "```markdown\n" + body

        out = parse_detail_response(raw)
        assert out is not None
        assert out.endswith("```\npytest -k foo\n```")

    def test_plain_wrap_with_a_same_length_inner_fence_still_strips_the_true_closer(
        self,
    ) -> None:
        """A scanner artifact must not preserve a whole-wrap closer."""
        body = _FIVE_SECTIONS.replace(
            "## Implementation\n\nWalkthrough.",
            "## Implementation\n\n```python\ndef foo():\n    return 1\n```\n\nWalkthrough.",
        )
        raw = "```markdown\n" + body + "```"

        out = parse_detail_response(raw)
        assert out is not None
        assert out == body.strip()
        assert "```markdown" not in out

    def test_bare_wrap_preserves_a_final_content_fence(self) -> None:
        body = _FIVE_SECTIONS.rstrip() + (
            "\n\n```\nclosing fence remains content\n```"
        )
        assert parse_detail_response(f"```\n{body}\n```\n") == body

    def test_early_leading_wrap_preserves_a_later_unclosed_fence_closer(self) -> None:
        """An unrelated later opener cannot authorize trailing stripping."""
        body = (
            _FIVE_SECTIONS.rstrip("\n")
            + "\n```\n\n## Verification\n\n````\nREAL CONTENT\n```"
        )

        out = parse_detail_response("```markdown\n" + body)

        assert out is not None
        assert out.endswith("````\nREAL CONTENT\n```")

    def test_strip_bare_fence_lines_does_not_crash_on_a_blank_first_line(
        self,
    ) -> None:
        """Round-15 review: the opens-with-a-fence gate must not trust
        _fenced_code_spans's position-0 verdict without also confirming
        lines[0] itself is genuinely fence-shaped — a blank lines[0]
        (a violated, documented-but-previously-unenforced precondition)
        made position 0 of the *joined* text look fenced while lines[0]
        itself matched no fence-open pattern, crashing with
        AttributeError instead of the pre-existing graceful pass-through."""
        out = _strip_bare_fence_lines(["", "```\n", "fenced content\n", "```\n"])
        assert out == ["", "```\n", "fenced content\n", "```\n"]

    def test_leading_inline_code_span_with_a_backtick_is_not_a_fake_wrap(
        self,
    ) -> None:
        """Round-14 review: a first line that is an ordinary inline code
        span containing a backtick (e.g. an illustrative shell command)
        must not be mistaken for a real leading fence — CommonMark forbids
        a backtick in a backtick fence's info string, and
        ``_fenced_code_spans`` already excludes this case. Treating it as
        a real wrap silently stripped an unrelated, real trailing
        example's own closing fence as if it belonged to the fake wrap.

        Round-15 review: the first version of this test put a plain
        section (``## Acceptance criteria``) after the fenced ``## Tests``
        example, so the example was never the document's true trailing
        content and the stripping logic under test never ran on it — the
        test passed identically on the pre-fix code (mutation-verified).
        The fenced example must be the document's actual last content."""
        raw = (
            "```rm -rf /``` deletes files.\n"
            + _FIVE_SECTIONS.split("## Tests")[0]
            + "## Acceptance criteria\n\n- returns 42\n\n"
            + "## Tests\n\nExample output:\n```\npytest ok\n```"
        )

        out = parse_detail_response(raw)
        assert out is not None
        assert out.endswith("```\npytest ok\n```")
        assert "rm -rf" not in out

    def test_sentinel_tolerates_commentary_before_the_title_inside_the_brackets(
        self,
    ) -> None:
        """The sentinel exists specifically so the model can add
        commentary it can't avoid — including *inside* the brackets,
        before the title. Rejecting that defeats the sentinel's own
        stated purpose."""
        raw = (
            "<!-- plan-tool:detail-response-start -->\n"
            "Sure, here you go:\n\n"
            f"{_FIVE_SECTIONS}"
            "<!-- plan-tool:detail-response-end -->\n"
        )

        out = parse_detail_response(raw)
        assert out == _FIVE_SECTIONS.strip()

    def test_never_closed_leading_fence_preserves_a_different_character_trailing_fence(
        self,
    ) -> None:
        """A closer can only close a matching-character opener. When the
        leading fence is itself never closed (a documented common failure
        mode) and the response legitimately ends in a *different*-character
        fenced example (e.g. leading ``` `` ` never closed, trailing
        ``~~~``), that trailing fence must survive — it cannot be the
        leading fence's own closer."""
        body = (
            _FIVE_SECTIONS.split("## Tests")[0]
            + "## Acceptance criteria\n\n- returns 42\n\n"
            + "## Tests\n\n~~~\npytest output here\n~~~"
        )
        raw = "```markdown\n" + body

        out = parse_detail_response(raw)
        assert out == body.strip()
        assert out.endswith("~~~")

    def test_never_closed_leading_fence_preserves_a_shorter_run_trailing_fence(
        self,
    ) -> None:
        """A closer must be at least as long as its opener, not merely the
        same character (CommonMark; mirrors ``_fenced_code_spans``'s own
        ``len(match.group(1)) >= opener[1]`` rule). A 4-backtick leading
        fence the model never closed must not treat an unrelated, shorter
        3-backtick trailing example's own real closer as its own — a
        3-backtick line can never close a 4-backtick opener."""
        body = (
            _FIVE_SECTIONS.split("## Tests")[0]
            + "## Acceptance criteria\n\n- returns 42\n\n"
            + "## Tests\n\n```\npytest output here\n```"
        )
        raw = "````\n" + body

        out = parse_detail_response(raw)
        assert out == body.strip()
        assert out.endswith("```")

    def test_marker_inside_a_genuinely_unterminated_fence_is_never_found(
        self,
    ) -> None:
        """Superseded 2026-09-11 (round-13 review, user-selected fix): the
        prior round accepted this as an ambiguous residual that happened
        to fail closed only via a count-mismatch side effect of the
        now-removed leniency. Marker search excludes every fenced span
        unconditionally now, so a marker-shaped line genuinely inside an
        unclosed fence is never found as a marker at all — not ambiguous,
        not a residual, just correctly excluded. With a real sentinel wrap
        present (the corruption shape round 13 actually found — finding
        1), the missing end marker now makes the whole response reject
        cleanly instead of silently truncating real content."""
        raw = (
            "<!-- plan-tool:detail-response-start -->\n"
            "# Title\n\n## Summary\nb\n\n## Table of Contents\nb\n\n## Why\nb\n\n"
            "## Files\nb\n\n## Implementation\nb\n\n"
            "## Tests\n\nExample:\n```\n<!-- plan-tool:detail-response-end -->\n"
            "## Acceptance criteria\nb\n"
        )

        assert parse_detail_response(raw) is None

    def test_stamped_body_reparses_through_parse_detail_response_and_the_envelope_parser(
        self,
    ) -> None:
        """Neither parser treats the marker as a heading or as the deferrals
        envelope — a stamped body, with and without a trailing envelope,
        parses back to the same body."""
        stamped = stamp_detail_format_version_marker(_FIVE_SECTIONS)
        assert parse_detail_response(stamped) == stamped.strip()

        enveloped = _structured_detail(body=stamped)
        parsed = parse_structured_detail_response(enveloped)
        assert parsed is not None
        assert parsed.body == stamped.strip()

    def test_parse_then_stamp_preserves_interior_line_terminators(self) -> None:
        """The authoring pipeline keeps response bytes outside the marker slot."""
        prose = "line one\r\nline two\vvertical\fform\u2028line\u2029paragraph"
        raw = _FIVE_SECTIONS.replace("Walkthrough.", prose)

        parsed = parse_detail_response(raw)

        assert parsed is not None
        assert prose in parsed
        assert prose in stamp_detail_format_version_marker(parsed)

    def test_reprompt_suffix_reserves_the_marker_slot_without_declaring_a_version(
        self,
    ) -> None:
        assert "plan-tool:detail-format-version" in _REPROMPT_SUFFIX
        assert not re.search(
            r"plan-tool:detail-format-version:\s*\d", _REPROMPT_SUFFIX
        )


def _structured_detail(
    *deferrals: tuple, body: str = _FIVE_SECTIONS
) -> str:
    """Build a detail response with a deferral envelope.

    Each deferral is ``(concept_id, step_id)`` or ``(concept_id, step_id,
    rationale)``; a supplied rationale is carried into both the ``## Deferred``
    bullet and the transport envelope.
    """
    norm = [
        (item[0], item[1], item[2] if len(item) > 2 else None)
        for item in deferrals
    ]
    if norm and "## Deferred" not in body:
        body = (
            f"{body.rstrip()}\n\n## Deferred\n\n"
            + "\n".join(
                f"- `{concept_id_value}` — {rationale or 'follow up later'}"
                for concept_id_value, _step_id, rationale in norm
            )
            + "\n"
        )
    payload = {
        "deferrals": [
            {
                "concept_id": concept_id_value,
                "step_id": step_id,
                **({"rationale": rationale} if rationale is not None else {}),
            }
            for concept_id_value, step_id, rationale in norm
        ]
    }
    return (
        f"{body.rstrip()}\n\n<!-- plan-tool-detail-deferrals\n"
        f"{json.dumps(payload, separators=(',', ':'))}\n-->"
    )


class TestParseStructuredDetailResponse:
    def test_returns_body_and_ordered_deferrals(self) -> None:
        first = "a" * 64
        second = "b" * 64
        parsed = parse_structured_detail_response(
            _structured_detail((first, 3), (second, 3))
        )

        assert parsed is not None
        assert parsed.body.startswith(_FIVE_SECTIONS.strip())
        assert first in parsed.body and second in parsed.body
        assert parsed.deferrals == (
            DetailDeferral(first, 3),
            DetailDeferral(second, 3),
        )

    def test_accepts_explicit_empty_deferrals(self) -> None:
        parsed = parse_structured_detail_response(_structured_detail())
        assert parsed is not None
        assert parsed.deferrals == ()

    def test_rejects_missing_payload_and_duplicate_link(self) -> None:
        duplicate = "a" * 64
        assert parse_structured_detail_response(_FIVE_SECTIONS) is None
        assert parse_structured_detail_response(
            _structured_detail((duplicate, 3), (duplicate, 3))
        ) is None

    def test_section_order_doesnt_matter(self) -> None:
        body = (
            "# Title\n\n"
            "## Acceptance criteria\n\nx\n\n"
            "## Tests\n\nx\n\n"
            "## Implementation\n\nx\n\n"
            "## Files\n\nx\n\n"
            "## Why\n\nx\n\n"
            "## Table of Contents\n\n- x\n\n"
            "## Summary\n\nx\n"
        )
        assert parse_detail_response(body) is not None

    def test_section_match_case_insensitive(self) -> None:
        body = (
            "# Title\n\n"
            "## summary\n\nx\n\n"
            "## TABLE of contents\n\n- x\n\n"
            "## why\n\nx\n\n"
            "## FILES\n\nx\n\n"
            "## Implementation\n\nx\n\n"
            "## Tests\n\nx\n\n"
            "## Acceptance criteria\n\nx\n"
        )
        assert parse_detail_response(body) is not None


# --- DetailError -----------------------------------------------------------


class TestDetailError:
    def test_is_an_exception(self) -> None:
        with pytest.raises(DetailError):
            raise DetailError("boom")


# --- update_step_detail_field ----------------------------------------------


_FRONTMATTER_PLAN = """---
title: Frontmatter Test Plan
status: in-progress
priority: medium
steps:
  - id: 1
    title: Step one
    files:
      - a.py
    detail: docs/plan-details/foo/01-prior.md
    status: done
  - id: 2
    title: Step two
    files:
      - b.py
    depends_on: [1]
  - id: 3
    title: Step three
    files:
      - c.py
    detail: docs/plan-details/foo/03-prior.md
    depends_on: [2]
---

# Frontmatter Test Plan

Some prose body.

- bullet one
- bullet two

## A subsection

More content here that we expect to survive a frontmatter mutation
byte-for-byte.
"""


def _write_frontmatter_plan(tmp_path: Path) -> Path:
    plan_path = tmp_path / "1-frontmatter.md"
    plan_path.write_text(_FRONTMATTER_PLAN, encoding="utf-8")
    return plan_path


class TestUpdateStepDetailField:
    def test_sets_detail_on_step_with_no_detail(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_frontmatter_plan(tmp_path)
        # Step 2 starts with detail=None.
        update_step_detail_field(plan_path, 2, "docs/plan-details/foo/02-new.md")
        plan = parse_plan(plan_path)
        assert plan.step_by_id(2).detail == "docs/plan-details/foo/02-new.md"

    def test_overwrites_existing_detail(self, tmp_path: Path) -> None:
        plan_path = _write_frontmatter_plan(tmp_path)
        # Step 1 already has detail=docs/plan-details/foo/01-prior.md.
        update_step_detail_field(
            plan_path, 1, "docs/plan-details/foo/01-replacement.md"
        )
        plan = parse_plan(plan_path)
        assert (
            plan.step_by_id(1).detail
            == "docs/plan-details/foo/01-replacement.md"
        )

    def test_preserves_body_byte_for_byte(self, tmp_path: Path) -> None:
        """Everything after the closing `---` fence must round-trip
        unchanged. Frontmatter reformat is allowed; body reformat is not.
        """
        plan_path = _write_frontmatter_plan(tmp_path)
        before = plan_path.read_text(encoding="utf-8")
        before_body = before[before.index("---\n", 4) + len("---\n") :]

        update_step_detail_field(plan_path, 2, "docs/plan-details/foo/02-new.md")

        after = plan_path.read_text(encoding="utf-8")
        after_body = after[after.index("---\n", 4) + len("---\n") :]
        assert after_body == before_body

    def test_preserves_other_steps_detail_fields(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_frontmatter_plan(tmp_path)
        update_step_detail_field(plan_path, 2, "docs/plan-details/foo/02-new.md")

        plan = parse_plan(plan_path)
        # Steps 1 and 3 keep their pre-existing detail values.
        assert plan.step_by_id(1).detail == "docs/plan-details/foo/01-prior.md"
        assert plan.step_by_id(3).detail == "docs/plan-details/foo/03-prior.md"

    def test_preserves_other_step_metadata(self, tmp_path: Path) -> None:
        """Title, files, status, depends_on on other steps stay intact."""
        plan_path = _write_frontmatter_plan(tmp_path)
        update_step_detail_field(plan_path, 2, "docs/plan-details/foo/02-new.md")

        plan = parse_plan(plan_path)
        s1 = plan.step_by_id(1)
        s3 = plan.step_by_id(3)
        assert s1.title == "Step one"
        assert s1.files == ["a.py"]
        assert s1.status.value == "done"
        assert s3.title == "Step three"
        assert s3.depends_on == [2]

    def test_unknown_step_id_raises_DetailError(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_frontmatter_plan(tmp_path)
        before = plan_path.read_bytes()
        with pytest.raises(DetailError, match="99"):
            update_step_detail_field(
                plan_path, 99, "docs/plan-details/foo/99-nope.md"
            )
        # File untouched on error.
        assert plan_path.read_bytes() == before

    def test_parse_failure_raises_DetailError(
        self, tmp_path: Path
    ) -> None:
        plan_path = tmp_path / "broken.md"
        # Malformed YAML inside the frontmatter fences.
        plan_path.write_text(
            "---\n"
            "title: Broken\n"
            "  invalid: : :\n"
            "---\n"
            "# body\n",
            encoding="utf-8",
        )
        before = plan_path.read_bytes()
        with pytest.raises(DetailError, match="parse"):
            update_step_detail_field(plan_path, 1, "anywhere.md")
        assert plan_path.read_bytes() == before

    def test_missing_plan_file_raises_DetailError(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises((DetailError, FileNotFoundError)):
            update_step_detail_field(
                tmp_path / "nope.md", 1, "anywhere.md"
            )


# --- generate_detail (orchestrator) ----------------------------------------


_ORCHESTRATOR_PLAN = """---
title: Orchestrator Plan
status: in-progress
priority: medium
steps:
  - id: 1
    title: Wire up the renderer
    files:
      - renderer.py
    complexity: low
    status: current
  - id: 2
    title: Build it
    files:
      - foo.py
    depends_on: [1]
---

# Orchestrator Plan
"""


_GOOD_BODY = (
    "# Step 1 — Wire up the renderer\n"
    "\n"
    "## Summary\n"
    "\n"
    "Reviewer-facing overview of the wire-up step.\n"
    "\n"
    "## Table of Contents\n"
    "\n"
    "- [Why](#why) — motivation\n"
    "- [Files (creates vs edits)](#files-creates-vs-edits) — paths touched\n"
    "- [Implementation](#implementation) — walkthrough\n"
    "- [Tests](#tests) — coverage\n"
    "- [Acceptance criteria](#acceptance-criteria) — verifiable bullets\n"
    "- [Deferred](#deferred) — out of scope\n"
    "\n"
    "## Why\n"
    "\n"
    "Reason in the codebase's terms.\n"
    "\n"
    "## Files (creates vs edits)\n"
    "\n"
    "- **New files:** none\n"
    "- **Existing files (edits only):** `renderer.py`\n"
    "\n"
    "## Implementation\n"
    "\n"
    "Walkthrough.\n"
    "\n"
    "## Tests\n"
    "\n"
    "- `test_x` — asserts y\n"
    "\n"
    "## Acceptance criteria\n"
    "\n"
    "- function returns 42\n"
    "\n"
    "## Deferred\n"
    "\n"
    "- nothing\n"
)


# ``_GOOD_BODY`` with the declared ``renderer.py`` cited from a directory that
# doesn't exist — a same-basename near-miss, the canonical files-coherence
# drift signal. Used by the tests that need a *real* deterministic finding
# while the LLM reports ``_(none)_``. (``_GOOD_BODY`` itself is coherent: it
# cites its declared root-level file bare.)
_DRIFTED_BODY = _GOOD_BODY.replace("`renderer.py`", "`src/renderer.py`")

# ``_GOOD_BODY`` as ``_author_step_detail`` actually writes it: the current
# format-version marker stamped into the fixed post-H1 slot. Written files
# no longer contain ``_GOOD_BODY`` byte-for-byte (the stamp inserts a line),
# so tests asserting on written content compare through this stamped form
# rather than weakening to a loose substring check.
_GOOD_BODY_STAMPED = stamp_detail_format_version_marker(_GOOD_BODY)


def _write_orchestrator_plan(tmp_path: Path) -> Path:
    plan_path = tmp_path / "2-orch.md"
    plan_path.write_text(_ORCHESTRATOR_PLAN, encoding="utf-8")
    (tmp_path / "renderer.py").write_text(
        "def render(plan):\n    return None\n", encoding="utf-8"
    )
    (tmp_path / "foo.py").write_text("FOO = 1\n", encoding="utf-8")
    return plan_path


def _set_declared_risk_profile(
    plan_path: Path, profile: RiskProfile, rationale: str
) -> None:
    """Replace the plan's explicit declaration without touching its body."""
    lines = plan_path.read_text(encoding="utf-8").splitlines(keepends=True)
    profile_lines = {"risk_profile:", "risk_profile_rationale:"}
    updated: list[str] = []
    for line in lines:
        if any(line.startswith(prefix) for prefix in profile_lines):
            continue
        updated.append(line)
        if line.startswith("priority:"):
            updated.extend(
                [
                    f"risk_profile: {profile.value}\n",
                    f"risk_profile_rationale: {rationale}\n",
                ]
            )
    plan_path.write_text("".join(updated), encoding="utf-8")


def _detail_path_for(tmp_path: Path, step_id: int, slug: str) -> Path:
    return tmp_path / "plan-details" / "orch" / f"{step_id:02d}-{slug}.md"


# A three-step plan for the ``recovery_only`` tests: step 1 is the recovery
# target, steps 2 and 3 are siblings whose detail files carry a refused
# (or, in one test, malformed-adjacent) format-version marker.
_RECOVERY_PLAN = """---
title: Recovery Plan
status: in-progress
priority: medium
steps:
  - id: 1
    title: Wire up the renderer
    files:
      - renderer.py
    complexity: low
    status: current
  - id: 2
    title: Build the widget
    files:
      - widget.py
  - id: 3
    title: Ship the gadget
    files:
      - gadget.py
---

# Recovery Plan
"""


def _write_recovery_plan(tmp_path: Path) -> Path:
    plan_path = tmp_path / "2-recovery.md"
    plan_path.write_text(_RECOVERY_PLAN, encoding="utf-8")
    (tmp_path / "renderer.py").write_text(
        "def render(plan):\n    return None\n", encoding="utf-8"
    )
    (tmp_path / "widget.py").write_text("WIDGET = 1\n", encoding="utf-8")
    (tmp_path / "gadget.py").write_text("GADGET = 1\n", encoding="utf-8")
    return plan_path


def _recovery_detail_path(tmp_path: Path, step_id: int, slug: str) -> Path:
    return tmp_path / "plan-details" / "recovery" / f"{step_id:02d}-{slug}.md"


def _seed_refused_sibling(tmp_path: Path, plan_path: Path, step_id: int, slug: str) -> Path:
    """Write a detail file declaring an unsupported marker and point
    ``step_id``'s frontmatter pointer at it."""
    path = _recovery_detail_path(tmp_path, step_id, slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# Step {step_id}\n"
        f"{render_detail_format_version_marker(999)}\n\n"
        "## Body\n\nfine.\n",
        encoding="utf-8",
    )
    update_step_detail_field(
        plan_path, step_id, _repo_relative(path, tmp_path)
    )
    return path


class TestAuthorStepWorker:
    """``_author_step_detail`` — the concurrency-safe per-step worker.

    Drives the worker directly with a fake invoker (no ``generate_detail``
    loop) to pin the extraction seam: it writes the detail file and returns a
    deferred ``(step_id, detail_rel)`` record, but never mutates the plan
    ``.md`` (that stays in the serial caller).
    """

    def _run_worker(
        self, tmp_path: Path, invoker
    ) -> tuple[Path, Path, _StepAuthoringOutcome]:
        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        output_path = derive_detail_path(plan_path, plan, step)
        plan_slug = _plan_slug(plan_path)
        ckpt_name = _DETAIL_CHECKPOINT_NAME.format(step_id=step.id)
        ckpt_path = checkpoint_path(tmp_path, plan_slug, ckpt_name)
        outcome = _author_step_detail(
            step,
            prompt="author step 1",
            output_path=output_path,
            cached=None,
            input_hash=_detail_step_input_hash(plan_path, step),
            ckpt_path=ckpt_path,
            ckpt_name=ckpt_name,
            plan_slug=plan_slug,
            phase_name="detail-step-01",
            invoke_idx=0,
            invoke_total=1,
            reporter=NullReporter(),
            run_logger=None,
            invoker=invoker,
            repo_root=tmp_path,
            plan_path=plan_path,
            capture_scenarios=False,
            arm=None,
            foundational_invoker=None,
        )
        return plan_path, output_path, outcome

    def test_author_step_worker_writes_and_returns_update_record(
        self, tmp_path: Path
    ) -> None:
        plan_path, output_path, outcome = self._run_worker(
            tmp_path, invoker=lambda _p: _GOOD_BODY
        )
        assert isinstance(outcome, _StepAuthoringOutcome)
        assert outcome.succeeded is True
        # Detail file on disk carrying the parsed body.
        assert output_path.is_file()
        assert "Wire up the renderer" in output_path.read_text(encoding="utf-8")
        # Deferred plan-update record returned instead of a plan-file write.
        assert outcome.update == (1, _repo_relative(output_path, tmp_path))
        assert outcome.body is not None
        # The worker never touches the plan .md — the pointer is still unset.
        assert parse_plan(plan_path).step_by_id(1).detail is None

    def test_author_step_worker_parse_failure_returns_no_update(
        self, tmp_path: Path
    ) -> None:
        plan_path, output_path, outcome = self._run_worker(
            tmp_path, invoker=lambda _p: "no thanks"
        )
        assert outcome.succeeded is False
        assert outcome.update is None
        assert outcome.result is not None
        assert outcome.result.written is False
        assert "unparseable" in (outcome.result.skipped_reason or "")
        # No file written and no plan change on a parse failure.
        assert not output_path.exists()
        assert parse_plan(plan_path).step_by_id(1).detail is None


@pytest.mark.integration
class TestGenerateDetailHappyPath:
    def test_generate_detail_rejects_unmatched_plan_before_detail_write_or_pointer_update(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        original = plan_path.read_text(encoding="utf-8") + "\n```\n"
        plan_path.write_text(original, encoding="utf-8")

        with pytest.raises(DetailError, match="unmatched opening code fence"):
            generate_detail(
                plan_path,
                repo_root=tmp_path,
                step_id=1,
                invoker=lambda _prompt: pytest.fail("detail model must not run"),
            )

        assert plan_path.read_text(encoding="utf-8") == original
        assert not _detail_path_for(tmp_path, 1, "wire-up-renderer").exists()

    def test_single_step_writes_file_and_updates_plan(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda prompt: _GOOD_BODY,
        )
        assert len(results) == 1
        r = results[0]
        assert r.step_id == 1
        assert r.written is True
        assert r.skipped_reason is None

        # File on disk with the body.
        expected = _detail_path_for(tmp_path, 1, "wire-up-renderer")
        assert r.output_path == expected
        assert expected.is_file()
        assert "Wire up the renderer" in expected.read_text(encoding="utf-8")

        # Plan frontmatter updated to repo-relative path.
        plan = parse_plan(plan_path)
        assert plan.step_by_id(1).detail == "plan-details/orch/01-wire-up-renderer.md"

    def test_commit_step_callback_fires_once_per_written_step(
        self, tmp_path: Path
    ) -> None:
        """#122 wiring: generate_detail calls ``commit_step(step_id, title)``
        at each converged step's success point, so the CLI can commit per
        step. Fires only on a clean written success (not a skip/split)."""
        plan_path = _write_orchestrator_plan(tmp_path)
        committed: list[tuple[int, str]] = []
        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda prompt: _GOOD_BODY,
            commit_step=lambda sid, title: committed.append((sid, title)),
        )
        assert [r.step_id for r in results if r.written] == [1]
        assert committed == [(1, "Wire up the renderer")]

    def test_commit_step_callback_not_called_on_skip(
        self, tmp_path: Path
    ) -> None:
        """A step already authored (skipped, not written) must not fire the
        per-step commit callback."""
        plan_path = _write_orchestrator_plan(tmp_path)
        # First run authors + would-commit step 1.
        generate_detail(
            plan_path, repo_root=tmp_path, step_id=1,
            invoker=lambda prompt: _GOOD_BODY,
        )
        # Second run: step 1 already has a detail file → skipped, no commit.
        committed: list[tuple[int, str]] = []
        results = generate_detail(
            plan_path, repo_root=tmp_path, step_id=1,
            invoker=lambda prompt: _GOOD_BODY,
            commit_step=lambda sid, title: committed.append((sid, title)),
        )
        assert all(not r.written for r in results)
        assert committed == []

    def test_commit_step_stops_after_a_prior_step_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Once a step's frontmatter update fails (orphaning its written file),
        later steps must NOT per-step commit — their `git add -A` would sweep
        the orphan the tool told the operator to delete (#122 review)."""
        from plan_tool import detail as detail_mod

        plan_path = _write_concurrent_plan(tmp_path)  # 4-step serial plan
        committed: list[int] = []
        real_update = detail_mod.update_step_detail_field

        def failing_update(pp, step_id, rel):
            if step_id == 1:
                raise DetailError("simulated frontmatter update failure")
            return real_update(pp, step_id, rel)

        monkeypatch.setattr(
            detail_mod, "update_step_detail_field", failing_update
        )
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            invoker=lambda _p: _GOOD_BODY,
            commit_step=lambda sid, title: committed.append(sid),
        )
        # Step 1 failed (orphaned file, no pointer); no later step may per-step
        # commit, or its `git add -A` would sweep the orphan into a wrong commit.
        assert committed == []

    def test_foundational_invoker_injects_finds_into_authoring_prompt(
        self, tmp_path: Path
    ) -> None:
        """When a ``foundational_invoker`` is supplied, the sweep runs first and
        its result is injected into the authoring prompt as a finds block."""
        plan_path = _write_orchestrator_plan(tmp_path)
        sweep = json.dumps(
            {
                "logic": "renderer dispatch",
                "shared_locations": [
                    {
                        "path": "foo.py",
                        "anchor": "FOO",
                        "relation": "duplicate",
                        "recommendation": "update-in-place",
                        "step_id": 1,
                    }
                ],
                "consolidation": None,
            }
        )
        seen = {"prompt": ""}

        def authoring(prompt: str) -> str:
            seen["prompt"] = prompt
            return _GOOD_BODY

        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=authoring,
            foundational_invoker=lambda _p: sweep,
        )
        assert "renderer dispatch" in seen["prompt"]
        assert "foo.py" in seen["prompt"]

    def test_foundational_invoker_receives_per_step_scope_fence(
        self, tmp_path: Path
    ) -> None:
        """The serial split sweep receives the current step's rendered fence."""
        plan_path = _write_intent_plan(tmp_path)
        seen: list[str] = []
        sweep = json.dumps(
            {"logic": "renderer dispatch", "shared_locations": [], "consolidation": None}
        )

        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _prompt: _GOOD_BODY,
            foundational_invoker=lambda prompt: seen.append(prompt) or sweep,
        )

        assert len(seen) == 1
        assert "Make the step's stated purpose reach the model doing the work." in seen[0]
        assert "Give the renderer the fence." in seen[0]
        assert "Give the builder the fence." not in seen[0]

    def test_no_foundational_invoker_renders_combined(
        self, tmp_path: Path
    ) -> None:
        """Without a ``foundational_invoker`` (the default) authoring renders the
        legacy COMBINED prompt: inline grep directive + self-check, no sweep
        call, no finds section."""
        plan_path = _write_orchestrator_plan(tmp_path)
        seen = {"prompt": ""}

        def authoring(prompt: str) -> str:
            seen["prompt"] = prompt
            return _GOOD_BODY

        generate_detail(
            plan_path, repo_root=tmp_path, step_id=1, invoker=authoring
        )
        assert "other locations that exercise the same logic" in seen["prompt"]
        assert "Step purity self-check" in seen["prompt"]
        assert "shared locations surfaced by a prior sweep" not in seen["prompt"]

    def test_purity_block_stripped_from_file_and_surfaced(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """An authoring response that appends a ## Structural findings block
        must (a) NOT write that block into the detail file and (b) surface a
        mixed-step warning — the always-on, --iterate-independent path."""
        plan_path = _write_orchestrator_plan(tmp_path)
        mixed_response = (
            _GOOD_BODY
            + "\n## Structural findings\n\n"
            "- MIXED-STEP: the renderer extract preserves behavior but the "
            "new caching changes it; split them\n"
        )
        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: mixed_response,
        )
        assert results[0].written is True
        written = _detail_path_for(tmp_path, 1, "wire-up-renderer").read_text(
            encoding="utf-8"
        )
        # The structural block must not pollute the detail file.
        assert "Structural findings" not in written
        assert "MIXED-STEP" not in written
        # ...but the body itself is intact.
        assert "Wire up the renderer" in written
        # ...and the mixed-step heads-up reached stderr.
        assert "mixed-step detected" in capsys.readouterr().err

    def test_pure_step_writes_no_warning(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
        )
        assert "mixed-step detected" not in capsys.readouterr().err

    def test_all_steps_mode_invokes_per_step(self, tmp_path: Path) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        calls: list[int] = []

        def fake(prompt: str) -> str:
            calls.append(len(calls) + 1)
            return _GOOD_BODY

        results = generate_detail(
            plan_path, repo_root=tmp_path, invoker=fake
        )
        assert len(results) == 2
        assert len(calls) == 2
        assert all(r.written for r in results)

    def test_all_steps_mode_skips_steps_with_existing_detail(
        self, tmp_path: Path
    ) -> None:
        """Mixed state: step 1 pre-populated, step 2 lacking → skip + write."""
        plan_path = _write_orchestrator_plan(tmp_path)
        # Pre-populate step 1 (file + pointer).
        detail_path = _detail_path_for(tmp_path, 1, "wire-up-renderer")
        detail_path.parent.mkdir(parents=True)
        detail_path.write_text("# Existing\n", encoding="utf-8")
        update_step_detail_field(
            plan_path, 1, "plan-details/orch/01-wire-up-renderer.md"
        )

        calls: list[str] = []

        def fake(prompt: str) -> str:
            calls.append(prompt)
            return _GOOD_BODY

        results = generate_detail(
            plan_path, repo_root=tmp_path, invoker=fake
        )
        assert len(results) == 2

        # Step 1 → skipped (already exists). Step 2 → written.
        by_id = {r.step_id: r for r in results}
        assert by_id[1].written is False
        assert "already exists" in (by_id[1].skipped_reason or "")
        assert by_id[2].written is True
        # Invoker called only for step 2.
        assert len(calls) == 1
        # Step 1's existing file untouched.
        assert detail_path.read_text(encoding="utf-8") == "# Existing\n"


_CONCURRENT_PLAN = """---
title: Concurrent Plan
status: in-progress
priority: medium
steps:
  - id: 1
    title: Alpha work
    files:
      - a.py
    complexity: low
    status: current
  - id: 2
    title: Beta work
    files:
      - b.py
    depends_on: [1]
  - id: 3
    title: Gamma work
    files:
      - c.py
    depends_on: [1]
  - id: 4
    title: Delta work
    files:
      - d.py
    depends_on: [1]
---

# Concurrent Plan
"""


def _write_concurrent_plan(root: Path) -> Path:
    """Write the four-step concurrent-dispatch plan + its declared files."""
    root.mkdir(parents=True, exist_ok=True)
    plan_path = root / "2-concurrent.md"
    plan_path.write_text(_CONCURRENT_PLAN, encoding="utf-8")
    for name in ("a.py", "b.py", "c.py", "d.py"):
        (root / name).write_text(f"# {name}\nX = 1\n", encoding="utf-8")
    return plan_path


@pytest.mark.integration
class TestGenerateDetailConcurrent:
    """``generate_detail(jobs>1)`` — overlap the per-step authoring calls
    while keeping every plan mutation and result serial and step-ordered.

    All authoring goes through a fake ``invoker`` (never real claude) and
    ``extract_lessons=False`` per the file convention.
    """

    def _detail_pointers(self, plan_path: Path) -> dict[int, Optional[str]]:
        return {s.id: s.detail for s in parse_plan(plan_path).steps}

    def test_jobs_one_matches_serial(self, tmp_path: Path) -> None:
        """``jobs=1`` writes the same files and returns the same result
        sequence as the default (unspecified-jobs) serial call."""
        serial_plan = _write_concurrent_plan(tmp_path / "serial")
        explicit_plan = _write_concurrent_plan(tmp_path / "explicit")

        serial = generate_detail(
            serial_plan,
            repo_root=tmp_path / "serial",
            invoker=lambda _p: _GOOD_BODY,
            reporter=NullReporter(),
            extract_lessons=False,
        )
        explicit = generate_detail(
            explicit_plan,
            repo_root=tmp_path / "explicit",
            invoker=lambda _p: _GOOD_BODY,
            reporter=NullReporter(),
            extract_lessons=False,
            jobs=1,
        )
        assert [(r.step_id, r.written) for r in serial] == [
            (r.step_id, r.written) for r in explicit
        ]
        assert self._detail_pointers(serial_plan) == self._detail_pointers(
            explicit_plan
        )

    def test_concurrent_worker_path_stamps_the_same_way(
        self, tmp_path: Path
    ) -> None:
        """The stamp runs inside the shared ``_author_step_detail`` worker,
        so ``jobs>1`` dispatch writes a stamped file too — one case checks
        the seam, not a second full roster."""
        plan_path = _write_concurrent_plan(tmp_path)

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            invoker=lambda _p: _GOOD_BODY,
            reporter=NullReporter(),
            extract_lessons=False,
            jobs=2,
        )
        written = [r for r in results if r.written]
        assert len(written) == 4
        for result in written:
            text = result.output_path.read_text(encoding="utf-8")
            require_supported_detail_format_version(text)
            assert render_detail_format_version_marker() in text.splitlines()

    def test_run_grade_lifecycle_selects_concurrent_or_serial_authoring(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The lifecycle chooses one existing authoring path and keeps order."""
        from plan_tool import detail as detail_module

        concurrent_calls: list[int] = []
        original_concurrent = detail_module._generate_detail_concurrent

        def spy_concurrent(*args, **kwargs):  # noqa: ANN002, ANN003
            concurrent_calls.append(kwargs["jobs"])
            return original_concurrent(*args, **kwargs)

        monkeypatch.setattr(
            detail_module, "_generate_detail_concurrent", spy_concurrent
        )

        def run_lifecycle(root: Path, jobs: int):  # noqa: ANN202
            plan_path = _write_concurrent_plan(root)
            prepared = detail_module._prepare_run_grade_detail(
                plan_path,
                parse_plan(plan_path),
                repo_root=root,
                step_id=None,
                force=False,
                dry_run=False,
                reporter=NullReporter(),
                resume=True,
                prompt_fn=lambda _p: "",
                run_logger=None,
            )
            return detail_module._run_grade_detail_lifecycle(
                prepared=prepared,
                plan_path=plan_path,
                repo_root=root,
                force=False,
                dry_run=False,
                invoker=lambda _p: _GOOD_BODY,
                extract_lessons=False,
                lessons_invoker=None,
                foundational_invoker=None,
                capture_scenarios=False,
                arm=None,
                strict_check=False,
                equivalence_invoker=None,
                budget=_IterativeBudget(enabled=False),
                allow_drift=False,
                auto_reconcile_on_drift=True,
                collision_sidecar=True,
                triage=True,
                include_info=False,
                allow_split=False,
                jobs=jobs,
                commit_step=None,
                prior_body="",
            )

        concurrent = run_lifecycle(tmp_path / "concurrent", jobs=2)
        serial = run_lifecycle(tmp_path / "serial", jobs=1)

        assert concurrent_calls == [2]
        assert [result.step_id for result in concurrent.results] == [1, 2, 3, 4]
        assert [result.step_id for result in serial.results] == [1, 2, 3, 4]
        assert all(result.written for result in concurrent.results + serial.results)

    def test_run_grade_lifecycle_preserves_serial_resume_and_durable_follow_up(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A resumed serial step updates its pointer and clears its checkpoint."""
        from plan_tool import detail as detail_module

        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        ckpt_path = checkpoint_path(
            tmp_path, "orch", _DETAIL_CHECKPOINT_NAME.format(step_id=step.id)
        )
        save_checkpoint(
            ckpt_path,
            Checkpoint(
                input_hash=_detail_step_input_hash(plan_path, step),
                payload=_GOOD_BODY,
                created_at=_fresh_now(),
            ),
        )
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        prepared = detail_module._prepare_run_grade_detail(
            plan_path,
            plan,
            repo_root=tmp_path,
            step_id=1,
            force=False,
            dry_run=False,
            reporter=NullReporter(),
            resume=True,
            prompt_fn=lambda _p: "",
            run_logger=None,
        )

        outcome = detail_module._run_grade_detail_lifecycle(
            prepared=prepared,
            plan_path=plan_path,
            repo_root=tmp_path,
            force=False,
            dry_run=False,
            invoker=lambda _p: (_ for _ in ()).throw(
                AssertionError("serial resume must not invoke")
            ),
            extract_lessons=False,
            lessons_invoker=None,
            foundational_invoker=None,
            capture_scenarios=False,
            arm=None,
            strict_check=False,
            equivalence_invoker=None,
            budget=_IterativeBudget(enabled=False),
            allow_drift=False,
            auto_reconcile_on_drift=True,
            collision_sidecar=True,
            triage=True,
            include_info=False,
            allow_split=False,
            jobs=1,
            commit_step=None,
            prior_body="",
        )

        assert [result.written for result in outcome.results] == [True]
        assert parse_plan(plan_path).step_by_id(1).detail is not None
        assert not ckpt_path.exists()

    def test_jobs_above_one_runs_workers_concurrently(
        self, tmp_path: Path
    ) -> None:
        """A fake invoker that rendezvouses two threads on a barrier proves
        more than one authoring call is in flight at once."""
        import threading

        gate = threading.Barrier(2, timeout=5)
        lock = threading.Lock()
        state = {"active": 0, "peak": 0}

        def probe(_prompt: str) -> str:
            # Block until a second worker also arrives — hard proof of overlap.
            with contextlib.suppress(threading.BrokenBarrierError):
                gate.wait()
            with lock:
                state["active"] += 1
                state["peak"] = max(state["peak"], state["active"])
            time.sleep(0.02)
            with lock:
                state["active"] -= 1
            return _GOOD_BODY

        plan_path = _write_concurrent_plan(tmp_path / "c")
        generate_detail(
            plan_path,
            repo_root=tmp_path / "c",
            invoker=probe,
            reporter=NullReporter(),
            extract_lessons=False,
            jobs=2,
        )
        assert state["peak"] >= 2

    def test_foundational_invoker_receives_per_step_scope_fence(
        self, tmp_path: Path
    ) -> None:
        """Each concurrent pre-dispatch sweep receives its own step fence."""
        root = tmp_path / "c"
        plan_path = _write_intent_plan(root)
        seen: list[str] = []
        sweep = json.dumps(
            {"logic": "renderer dispatch", "shared_locations": [], "consolidation": None}
        )

        generate_detail(
            plan_path,
            repo_root=root,
            invoker=lambda _prompt: _GOOD_BODY,
            foundational_invoker=lambda prompt: seen.append(prompt) or sweep,
            reporter=NullReporter(),
            extract_lessons=False,
            jobs=2,
        )

        step_one, step_two = seen
        assert "Step 1: Wire up the renderer" in step_one
        assert "Give the renderer the fence." in step_one
        assert "Give the builder the fence." not in step_one
        assert "Step 2: Build it" in step_two
        assert "Give the builder the fence." in step_two
        assert "Give the renderer the fence." not in step_two

    def test_results_in_step_order_regardless_of_completion(
        self, tmp_path: Path
    ) -> None:
        """Scrambled completion order still yields results ordered by step id,
        with every plan ``detail:`` pointer set."""
        import threading

        counter = {"n": 0}
        clock_lock = threading.Lock()

        def scrambling(_prompt: str) -> str:
            with clock_lock:
                i = counter["n"]
                counter["n"] += 1
            # Earlier-submitted (lower step id) sleeps longest → finishes last.
            time.sleep(0.02 * (5 - i))
            return _GOOD_BODY

        plan_path = _write_concurrent_plan(tmp_path / "c")
        results = generate_detail(
            plan_path,
            repo_root=tmp_path / "c",
            invoker=scrambling,
            reporter=NullReporter(),
            extract_lessons=False,
            jobs=4,
        )
        assert [r.step_id for r in results] == [1, 2, 3, 4]
        pointers = self._detail_pointers(plan_path)
        assert all(pointers[i] is not None for i in (1, 2, 3, 4))

    def test_jobs_with_iterate_raises(self, tmp_path: Path) -> None:
        """``jobs>1`` with ``budget.enabled`` raises and writes nothing."""
        from plan_tool.convergence import IterativeBudget

        plan_path = _write_concurrent_plan(tmp_path / "c")
        with pytest.raises(DetailError, match="iterate"):
            generate_detail(
                plan_path,
                repo_root=tmp_path / "c",
                invoker=lambda _p: _GOOD_BODY,
                reporter=NullReporter(),
                extract_lessons=False,
                jobs=2,
                budget=IterativeBudget(enabled=True),
            )
        assert not (tmp_path / "c" / "plan-details").exists()
        assert self._detail_pointers(plan_path) == {1: None, 2: None, 3: None, 4: None}

    def test_jobs_with_split_raises(self, tmp_path: Path) -> None:
        """``jobs>1`` with ``allow_split`` (iterate off) raises and writes
        nothing — the defense-in-depth backstop for direct callers."""
        plan_path = _write_concurrent_plan(tmp_path / "c")
        with pytest.raises(DetailError, match="split"):
            generate_detail(
                plan_path,
                repo_root=tmp_path / "c",
                invoker=lambda _p: _GOOD_BODY,
                reporter=NullReporter(),
                extract_lessons=False,
                jobs=2,
                allow_split=True,
            )
        assert not (tmp_path / "c" / "plan-details").exists()

    def test_jobs_with_lessons_raises(self, tmp_path: Path) -> None:
        """``jobs>1`` with ``extract_lessons`` raises and writes nothing."""
        plan_path = _write_concurrent_plan(tmp_path / "c")
        with pytest.raises(DetailError, match="lessons"):
            generate_detail(
                plan_path,
                repo_root=tmp_path / "c",
                invoker=lambda _p: _GOOD_BODY,
                reporter=NullReporter(),
                extract_lessons=True,
                jobs=2,
            )
        assert not (tmp_path / "c" / "plan-details").exists()

    def test_concurrent_run_log_lines_intact(self, tmp_path: Path) -> None:
        """Under overlapping workers, every run-log JSONL line parses as whole
        JSON — the ``_append_jsonl_line`` lock holds."""
        import json
        import threading
        from plan_tool.run_log import RunLogWriter

        lock = threading.Lock()
        state = {"n": 0}

        def busy(_prompt: str) -> str:
            with lock:
                state["n"] += 1
            time.sleep(0.01)
            return _GOOD_BODY

        root = tmp_path / "c"
        plan_path = _write_concurrent_plan(root)
        writer = RunLogWriter.start(
            repo_root=root,
            slug="concurrent",
            command="detail",
            argv=["plan-tool", "detail", "concurrent"],
        )
        generate_detail(
            plan_path,
            repo_root=root,
            invoker=busy,
            reporter=NullReporter(),
            extract_lessons=False,
            jobs=4,
            run_logger=writer,
        )
        lines = [
            ln for ln in writer.log_path.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
        events = [json.loads(ln) for ln in lines]  # raises on a torn line
        assert any(e.get("event") == "claude_call_start" for e in events)

    def test_concurrent_per_step_failure_isolated(
        self, tmp_path: Path
    ) -> None:
        """One step's unparseable response is isolated: its result is
        not-written with a ``skipped_reason``; the others still write."""
        def selective(prompt: str) -> str:
            return "no thanks" if "Beta work" in prompt else _GOOD_BODY

        root = tmp_path / "c"
        plan_path = _write_concurrent_plan(root)
        results = generate_detail(
            plan_path,
            repo_root=root,
            invoker=selective,
            reporter=NullReporter(),
            extract_lessons=False,
            jobs=4,
        )
        by_id = {r.step_id: r for r in results}
        assert by_id[2].written is False
        assert "unparseable" in (by_id[2].skipped_reason or "")
        for other in (1, 3, 4):
            assert by_id[other].written is True
            assert by_id[other].output_path.is_file()
        # Step 2's pointer stays unset; the others resolve to their files.
        pointers = self._detail_pointers(plan_path)
        assert pointers[2] is None
        assert all(pointers[i] is not None for i in (1, 3, 4))

    def test_worker_count_bounded_by_work(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With ``jobs`` above the invoke-target count, the pool is sized to
        the target count — never more threads than work."""
        from plan_tool import detail as detail_module

        real_pool = detail_module.ThreadPoolExecutor
        captured: dict[str, int] = {}

        def spy(*, max_workers: int, **kw):
            captured["max_workers"] = max_workers
            return real_pool(max_workers=max_workers, **kw)

        monkeypatch.setattr(detail_module, "ThreadPoolExecutor", spy)
        root = tmp_path / "c"
        plan_path = _write_concurrent_plan(root)
        generate_detail(
            plan_path,
            repo_root=root,
            invoker=lambda _p: _GOOD_BODY,
            reporter=NullReporter(),
            extract_lessons=False,
            jobs=10,
        )
        assert captured["max_workers"] == 4

    def test_jobs_below_one_floored_to_serial(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``jobs=0`` runs the serial path (no pool) to completion — the CLI
        is the validation point, so a stray value floors to serial."""
        from plan_tool import detail as detail_module

        def boom(*a, **k):  # pragma: no cover - must never be called
            raise AssertionError("ThreadPoolExecutor used on the serial path")

        monkeypatch.setattr(detail_module, "ThreadPoolExecutor", boom)
        root = tmp_path / "c"
        plan_path = _write_concurrent_plan(root)
        results = generate_detail(
            plan_path,
            repo_root=root,
            invoker=lambda _p: _GOOD_BODY,
            reporter=NullReporter(),
            extract_lessons=False,
            jobs=0,
        )
        assert [r.written for r in results] == [True, True, True, True]

    def test_single_step_id_ignores_jobs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A single explicit ``step_id`` is one invoke → serial path, no pool,
        regardless of ``jobs``."""
        from plan_tool import detail as detail_module

        def boom(*a, **k):  # pragma: no cover - must never be called
            raise AssertionError("pool used for a single-step run")

        monkeypatch.setattr(detail_module, "ThreadPoolExecutor", boom)
        root = tmp_path / "c"
        plan_path = _write_concurrent_plan(root)
        results = generate_detail(
            plan_path,
            repo_root=root,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            reporter=NullReporter(),
            extract_lessons=False,
            jobs=4,
        )
        assert len(results) == 1
        assert results[0].step_id == 1 and results[0].written is True

    def test_concurrent_plan_pointers_all_set(self, tmp_path: Path) -> None:
        """After a ``jobs>1`` run every authored step's ``detail:`` pointer
        resolves to its on-disk file (the serial tail ran for each)."""
        root = tmp_path / "c"
        plan_path = _write_concurrent_plan(root)
        generate_detail(
            plan_path,
            repo_root=root,
            invoker=lambda _p: _GOOD_BODY,
            reporter=NullReporter(),
            extract_lessons=False,
            jobs=3,
        )
        for step in parse_plan(plan_path).steps:
            assert step.detail is not None
            assert (root / step.detail).is_file()

    def test_concurrent_write_oserror_isolated(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A write ``OSError`` on one step is isolated (matching the serial
        taxonomy's second aggregated case): that step's result is not-written
        with a ``write failed`` reason and its pointer stays unset, while every
        sibling still writes. Results remain step-ordered through the failure."""
        real_write_text = Path.write_text

        def failing_write_text(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            # Only step 2's detail file (``NN-beta-work.md``) fails to write.
            # Checkpoints use tempfile+os.replace (not write_text), and the
            # plan file is ``2-concurrent.md`` — neither matches, so exactly
            # the step-2 detail write raises.
            if self.suffix == ".md" and "beta" in self.name.lower():
                raise OSError("simulated disk full")
            return real_write_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", failing_write_text)
        root = tmp_path / "c"
        plan_path = _write_concurrent_plan(root)
        results = generate_detail(
            plan_path,
            repo_root=root,
            invoker=lambda _p: _GOOD_BODY,
            reporter=NullReporter(),
            extract_lessons=False,
            jobs=4,
        )
        by_id = {r.step_id: r for r in results}
        assert by_id[2].written is False
        assert "write failed" in (by_id[2].skipped_reason or "")
        for other in (1, 3, 4):
            assert by_id[other].written is True
            assert by_id[other].output_path.is_file()
        pointers = self._detail_pointers(plan_path)
        assert pointers[2] is None
        assert all(pointers[i] is not None for i in (1, 3, 4))
        # The isolated failure does not scramble the durable result order.
        assert [r.step_id for r in results] == [1, 2, 3, 4]

    def test_concurrent_non_oserror_is_plan_level_abort(
        self, tmp_path: Path
    ) -> None:
        """A non-OSError raised inside a worker is a plan-level abort, NOT a
        per-step skip: it propagates out of ``generate_detail``. When more than
        one worker fails, the abort is deterministic — the lowest step id's
        error is re-raised in step order after the pool joins."""

        class Boom(RuntimeError):
            pass

        def exploding(prompt: str) -> str:
            if "Beta work" in prompt:  # step 2 — lowest failing id
                raise Boom("beta blew up")
            if "Gamma work" in prompt:  # step 3 — also fails
                raise Boom("gamma blew up")
            return _GOOD_BODY

        root = tmp_path / "c"
        plan_path = _write_concurrent_plan(root)
        # Step order wins: step 2's Boom, never step 3's, and never a swallowed
        # per-step skip that would let generate_detail return normally.
        with pytest.raises(Boom, match="beta blew up"):
            generate_detail(
                plan_path,
                repo_root=root,
                invoker=exploding,
                reporter=NullReporter(),
                extract_lessons=False,
                jobs=4,
            )


_SPLIT_PLAN_PENDING = """---
title: Split Test
status: in-progress
priority: medium
steps:
  - id: 1
    title: Mixed step
    files:
      - renderer.py
    complexity: low
  - id: 2
    title: Downstream
    files:
      - foo.py
    depends_on: [1]
---

# Split Test
"""

# Two-step decomposition _propose_step_split parses from the split prompt.
_SPLIT_JSON = (
    '[{"title": "Refactor extract", "change_type": "refactor", '
    '"files": ["renderer.py"], "creates": []}, '
    '{"title": "Add caching", "change_type": "feature", '
    '"files": ["renderer.py"], "creates": []}]'
)
_MIXED_AUTHORING = (
    _GOOD_BODY
    + "\n## Structural findings\n\n"
    "- MIXED-STEP: the extract is behavior-preserving but the caching "
    "changes behavior; split them\n"
)


@pytest.mark.integration
class TestInteractiveSplit:
    """Phase B: --split offers a refactor→feature split for flagged steps."""

    def _pending_plan(self, tmp_path: Path) -> Path:
        plan_path = tmp_path / "3-split.md"
        plan_path.write_text(_SPLIT_PLAN_PENDING, encoding="utf-8")
        (tmp_path / "renderer.py").write_text("X = 1\n", encoding="utf-8")
        (tmp_path / "foo.py").write_text("Y = 1\n", encoding="utf-8")
        return plan_path

    def _invoker(self):
        """Mixed body for the target step's authoring; split JSON for the
        decomposition prompt; clean body for downstream + re-authored halves."""

        def fake(prompt: str) -> str:
            if "decomposing ONE implementation step" in prompt:
                return _SPLIT_JSON
            if "Mixed step" in prompt:
                return _MIXED_AUTHORING
            return _GOOD_BODY

        return fake

    @staticmethod
    def _answer(msg: str) -> str:
        # Confirm the split; decline any "replace existing file" prompt so
        # the re-author pass doesn't overwrite the migrated downstream file.
        return "y" if "Apply this split" in msg else "n"

    @staticmethod
    def _mixed_recommendation(step_id: int) -> Recommendation:
        return Recommendation(
            id=f"mixed-step-{step_id}",
            source="purity",
            severity="medium",
            step_id=step_id,
            title="Mixed step",
            body="Split the refactor from the feature work.",
        )

    @staticmethod
    def _phase_b_context(
        detail_module,
        plan_path: Path,
        repo_root: Path,
        invoker,
        prompt_fn=None,
    ):
        return detail_module._PhaseBSplitContext(
            plan_path=plan_path,
            repo_root=repo_root,
            invoker=invoker,
            reporter=NullReporter(),
            extract_lessons=False,
            lessons_invoker=None,
            foundational_invoker=None,
            strict_check=False,
            equivalence_invoker=None,
            prompt_fn=prompt_fn or (lambda _message: "n"),
            run_logger=None,
            budget=_IterativeBudget(enabled=False),
            allow_drift=False,
            auto_reconcile_on_drift=True,
            collision_sidecar=True,
            triage=True,
            include_info=False,
            allow_split=True,
            plan_slug=_plan_slug(plan_path),
        )

    def test_happy_path_splits_and_reauthors(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        plan_path = self._pending_plan(tmp_path)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            invoker=self._invoker(),
            prompt_fn=self._answer,
            extract_lessons=False,
            allow_split=True,
        )
        plan = parse_plan(plan_path)
        # Step 1 became the refactor+feature pair; downstream pushed to id 3.
        assert [s.title for s in plan.steps] == [
            "Refactor extract",
            "Add caching",
            "Downstream",
        ]
        assert plan.step_by_id(1).change_type == ChangeType.REFACTOR
        assert plan.step_by_id(2).change_type == ChangeType.FEATURE
        # depends_on rewired: downstream repoints to the feature half.
        assert plan.step_by_id(3).depends_on == [2]
        # Every step resolves to a detail file on disk.
        for s in plan.steps:
            assert s.detail is not None
            assert (tmp_path / s.detail).is_file()
        # The original mixed file was archived, not left active.
        active = {(tmp_path / s.detail).name for s in plan.steps}
        assert "01-mixed-step.md" not in active

    def test_split_does_not_prompt_to_replace_existing_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Regression: re-authoring the halves must target only the new
        # detail-less steps, never re-visit (and prompt to replace) the
        # already-detailed upstream/downstream files.
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        plan_path = self._pending_plan(tmp_path)
        prompts: list[str] = []

        def record(msg: str) -> str:
            prompts.append(msg)
            return "y" if "Apply this split" in msg else "n"

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            invoker=self._invoker(),
            prompt_fn=record,
            extract_lessons=False,
            allow_split=True,
        )
        # No replace prompt fired during the half re-authoring.
        assert not any("Replace" in m for m in prompts)
        # Results are coherent: unique ids, and every written path exists.
        ids = [r.step_id for r in results]
        assert len(ids) == len(set(ids)), ids
        for r in results:
            if r.written:
                assert Path(r.output_path).is_file()

    def test_declined_split_leaves_plan_unchanged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        plan_path = self._pending_plan(tmp_path)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            invoker=self._invoker(),
            prompt_fn=lambda _m: "n",  # decline the split
            extract_lessons=False,
            allow_split=True,
        )
        plan = parse_plan(plan_path)
        assert [s.title for s in plan.steps] == ["Mixed step", "Downstream"]

    def test_without_flag_only_warns(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        plan_path = self._pending_plan(tmp_path)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            invoker=self._invoker(),
            prompt_fn=lambda _m: "y",
            extract_lessons=False,
            allow_split=False,  # detection only
        )
        plan = parse_plan(plan_path)
        assert [s.title for s in plan.steps] == ["Mixed step", "Downstream"]

    def test_multiple_splits_renumber_and_rewire(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Two mixed steps (Alpha, Beta) ahead of a downstream Gamma. Both
        # split; processed high→low so the Beta split doesn't disturb the
        # not-yet-processed Alpha target. End state:
        #   [Alpha-R(1), Alpha-F(2), Beta-R(3), Beta-F(4), Gamma(5)]
        # and Gamma's depends_on [2] (Beta) remaps to [4] (the Beta feature).
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        plan_path = tmp_path / "4-multi.md"
        plan_path.write_text(
            "---\n"
            "title: Multi Split\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n    title: Alpha\n    files:\n      - renderer.py\n"
            "  - id: 2\n    title: Beta\n    files:\n      - foo.py\n"
            "    depends_on: [1]\n"
            "  - id: 3\n    title: Gamma\n    files:\n      - bar.py\n"
            "    depends_on: [2]\n"
            "---\n\n# Multi Split\n",
            encoding="utf-8",
        )
        for fn in ("renderer.py", "foo.py", "bar.py"):
            (tmp_path / fn).write_text("X = 1\n", encoding="utf-8")

        alpha_json = (
            '[{"title": "Alpha refactor", "change_type": "refactor", '
            '"files": ["renderer.py"], "creates": []}, '
            '{"title": "Alpha feature", "change_type": "feature", '
            '"files": ["renderer.py"], "creates": []}]'
        )
        beta_json = (
            '[{"title": "Beta refactor", "change_type": "refactor", '
            '"files": ["foo.py"], "creates": []}, '
            '{"title": "Beta feature", "change_type": "feature", '
            '"files": ["foo.py"], "creates": []}]'
        )
        # First two authored steps (Alpha, Beta) are mixed; Gamma and every
        # re-authored half are clean. A counter pins the flag to the first two
        # without relying on prompt content (siblings would contaminate that).
        authored = {"n": 0}

        def fake(prompt: str) -> str:
            if "decomposing ONE implementation step" in prompt:
                return alpha_json if "Alpha" in prompt else beta_json
            authored["n"] += 1
            return _MIXED_AUTHORING if authored["n"] <= 2 else _GOOD_BODY

        generate_detail(
            plan_path,
            repo_root=tmp_path,
            invoker=fake,
            prompt_fn=lambda m: "y" if "Apply this split" in m else "n",
            extract_lessons=False,
            allow_split=True,
        )
        plan = parse_plan(plan_path)
        assert [s.title for s in plan.steps] == [
            "Alpha refactor",
            "Alpha feature",
            "Beta refactor",
            "Beta feature",
            "Gamma",
        ]
        assert [
            plan.step_by_id(i).change_type for i in (1, 2, 3, 4)
        ] == [
            ChangeType.REFACTOR,
            ChangeType.FEATURE,
            ChangeType.REFACTOR,
            ChangeType.FEATURE,
        ]
        # Gamma's dependency followed the Beta split to the feature half.
        assert plan.step_by_id(5).depends_on == [4]
        # Every step resolves to a detail file on disk, none stale.
        for s in plan.steps:
            assert s.detail is not None
            assert (tmp_path / s.detail).is_file()

    def test_carried_downstream_reported_as_skip_not_write(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # `--step 1` run: only step 1 is authored this run; downstream was
        # detailed by a PRIOR run. Splitting step 1 renumbers them. The
        # rebuild must report the renumbered downstream as carried-through
        # skips (present on disk, not freshly written), not fresh writes.
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        plan_path = tmp_path / "5-carry.md"
        plan_path.write_text(
            "---\ntitle: Carry\nstatus: in-progress\npriority: medium\n"
            "steps:\n"
            "  - id: 1\n    title: Mixed step\n    files:\n      - renderer.py\n"
            "  - id: 2\n    title: Down one\n    files:\n      - foo.py\n"
            "    depends_on: [1]\n"
            "  - id: 3\n    title: Down two\n    files:\n      - bar.py\n"
            "    depends_on: [2]\n"
            "---\n\n# Carry\n",
            encoding="utf-8",
        )
        for fn in ("renderer.py", "foo.py", "bar.py"):
            (tmp_path / fn).write_text("X = 1\n", encoding="utf-8")
        # Simulate a prior run: downstream detail files + pointers already set.
        ddir = tmp_path / "plan-details" / "carry"
        ddir.mkdir(parents=True)
        (ddir / "02-down-one.md").write_text("# Down one\n", encoding="utf-8")
        (ddir / "03-down-two.md").write_text("# Down two\n", encoding="utf-8")
        update_step_detail_field(plan_path, 2, "plan-details/carry/02-down-one.md")
        update_step_detail_field(plan_path, 3, "plan-details/carry/03-down-two.md")

        def fake(prompt: str) -> str:
            if "decomposing ONE implementation step" in prompt:
                return _SPLIT_JSON
            if "Mixed step" in prompt:
                return _MIXED_AUTHORING
            return _GOOD_BODY

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=fake,
            prompt_fn=lambda m: "y" if "Apply this split" in m else "n",
            extract_lessons=False,
            allow_split=True,
        )
        by_id = {r.step_id: r for r in results}
        # The two halves were authored this run.
        assert by_id[1].written is True
        assert by_id[2].written is True
        # The renumbered downstream were carried, not re-written.
        assert by_id[3].written is False
        assert "carried through split" in (by_id[3].skipped_reason or "")
        assert by_id[4].written is False
        # All four still resolve to a file on disk.
        plan = parse_plan(plan_path)
        for s in plan.steps:
            assert (tmp_path / s.detail).is_file()

    def test_unrun_current_mixed_step_is_split(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # The fix: step 1 is an unrun `status: current` step. Phase B now
        # reaches the split bridge for it (it was pre-declined as "already
        # run/started" before), proposes + applies the refactor+feature
        # split, and the first half keeps `current` (exactly one current).
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        plan_path = _write_orchestrator_plan(tmp_path)

        # First authoring call flags step 1 as MIXED (triggers the split);
        # every later call (the two new halves, step 2) is a clean body. The
        # split-proposal prompt returns the two-step decomposition.
        authored = {"n": 0}

        def fake(prompt: str) -> str:
            if "decomposing ONE implementation step" in prompt:
                return _SPLIT_JSON
            authored["n"] += 1
            return _MIXED_AUTHORING if authored["n"] == 1 else _GOOD_BODY

        generate_detail(
            plan_path,
            repo_root=tmp_path,
            invoker=fake,
            prompt_fn=lambda _m: "y",
            extract_lessons=False,
            allow_split=True,
        )
        plan = parse_plan(plan_path)
        # Step 1 was split into the two named halves; downstream pushed to 3.
        assert [s.title for s in plan.steps] == [
            "Refactor extract",
            "Add caching",
            "Build it",
        ]
        # Status inheritance through escalate: exactly one current step (the
        # first half), never zero — the finding-2 invariant.
        assert [
            s.id for s in plan.steps if s.status == StepStatus.CURRENT
        ] == [1]

    def test_phase_b_delegates_to_escalate_to_split(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Phase B reaches the split engine only through the bridge: it calls
        # ``escalate_to_split`` once per flagged mixed target, forwarding the
        # target id, the opt-in flag, and the proposer/confirm seams.
        from plan_tool.launcher import EscalateResult

        from plan_tool import detail as detail_module
        plan_path = self._pending_plan(tmp_path)
        invoker = self._invoker()
        calls: list[dict] = []

        def spy(plan_path_arg, **kwargs):
            calls.append(kwargs)
            return EscalateResult(
                outcome="recommended", target_id=kwargs["step_id"]
            )

        monkeypatch.setattr("plan_tool.detail.escalate_to_split", spy)
        detail_module._handle_phase_b_splits(
            [],
            mixed_steps=[(1, self._mixed_recommendation(1))],
            applied_in_loop_split_ids=set(),
            context=self._phase_b_context(
                detail_module, plan_path, tmp_path, invoker, self._answer
            ),
        )
        # Only the single flagged mixed step (id 1) reaches the bridge.
        assert len(calls) == 1
        kw = calls[0]
        assert kw["step_id"] == 1
        assert kw["allow_split"] is True
        assert kw["prompt_fn"] is self._answer
        assert kw["invoker"] is invoker

    def test_phase_b_excludes_applied_in_loop_split_target(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import detail as detail_module

        plan_path = self._pending_plan(tmp_path)

        def boom(*_args, **_kwargs):
            raise AssertionError("in-loop split target must not re-enter Phase B")

        monkeypatch.setattr(detail_module, "escalate_to_split", boom)
        results: list[DetailResult] = []
        returned = detail_module._handle_phase_b_splits(
            results,
            mixed_steps=[(1, self._mixed_recommendation(1))],
            applied_in_loop_split_ids={1},
            context=self._phase_b_context(
                detail_module, plan_path, tmp_path, self._invoker()
            ),
        )

        assert returned is results

    def test_phase_b_reentry_targets_all_and_only_current_detail_less_steps(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import detail as detail_module
        from plan_tool.launcher import EscalateResult

        plan_path = tmp_path / "4-phase-b-targets.md"
        plan_path.write_text(
            "---\n"
            "title: Phase B Targets\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n    title: Mixed target\n    files:\n      - mixed.py\n"
            "  - id: 2\n    title: Existing detail\n    files:\n      - existing.py\n"
            "    detail: plan-details/phase-b-targets/02-existing-detail.md\n"
            "  - id: 3\n    title: Later unset\n    files:\n      - later.py\n"
            "---\n\n# Phase B Targets\n",
            encoding="utf-8",
        )
        for filename in ("mixed.py", "existing.py", "later.py"):
            (tmp_path / filename).write_text("X = 1\n", encoding="utf-8")
        existing_detail = (
            tmp_path / "plan-details/phase-b-targets/02-existing-detail.md"
        )
        existing_detail.parent.mkdir(parents=True)
        existing_detail.write_text("# Existing\n", encoding="utf-8")

        monkeypatch.setattr(
            detail_module,
            "escalate_to_split",
            lambda _path, **kwargs: EscalateResult(
                outcome="applied", target_id=kwargs["step_id"]
            ),
        )
        reauthored_ids: list[int] = []

        def failed_child(_path, **kwargs):
            step_id = kwargs["step_id"]
            reauthored_ids.append(step_id)
            return [
                DetailResult(
                    step_id=step_id,
                    output_path=tmp_path / f"failed-{step_id}.md",
                    written=False,
                    skipped_reason="child authoring failed",
                )
            ]

        monkeypatch.setattr(detail_module, "generate_detail", failed_child)
        results = detail_module._handle_phase_b_splits(
            [],
            mixed_steps=[(1, self._mixed_recommendation(1))],
            applied_in_loop_split_ids=set(),
            context=self._phase_b_context(
                detail_module, plan_path, tmp_path, self._invoker()
            ),
        )

        assert reauthored_ids == [1, 3]
        assert existing_detail.read_text(encoding="utf-8") == "# Existing\n"
        carried = next(result for result in results if result.step_id == 2)
        assert carried.written is False
        assert "carried through split" in (carried.skipped_reason or "")

    def test_phase_b_reentry_preserves_nested_persistence_result(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import detail as detail_module
        from plan_tool.launcher import EscalateResult

        plan_path = tmp_path / "3-nested-persistence.md"
        plan_path.write_text(
            "---\n"
            "title: Nested Persistence\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n    title: Mixed target\n    files:\n      - mixed.py\n"
            "---\n\n# Nested Persistence\n",
            encoding="utf-8",
        )
        (tmp_path / "mixed.py").write_text("X = 1\n", encoding="utf-8")
        nested_persistence_failure = DetailResult(
            step_id=1,
            output_path=tmp_path / "plan-details/nested-persistence/01-mixed.md",
            written=False,
            skipped_reason="concept deferral persistence failed: disk full",
        )
        monkeypatch.setattr(
            detail_module,
            "escalate_to_split",
            lambda _path, **kwargs: EscalateResult(
                outcome="applied", target_id=kwargs["step_id"]
            ),
        )
        monkeypatch.setattr(
            detail_module,
            "generate_detail",
            lambda _path, **_kwargs: [nested_persistence_failure],
        )

        results = detail_module._handle_phase_b_splits(
            [],
            mixed_steps=[(1, self._mixed_recommendation(1))],
            applied_in_loop_split_ids=set(),
            context=self._phase_b_context(
                detail_module, plan_path, tmp_path, self._invoker()
            ),
        )

        assert results == [nested_persistence_failure]

    def test_phase_b_no_inline_engine_calls(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # With the bridge stubbed, the inline split primitives must never fire
        # — proving Phase B no longer calls them directly.
        from plan_tool.launcher import EscalateResult

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        plan_path = self._pending_plan(tmp_path)

        def boom(*_a, **_k):
            raise AssertionError("inline split primitive must not be called")

        monkeypatch.setattr("plan_tool.create._apply_step_split", boom)
        monkeypatch.setattr("plan_tool.create._propose_step_split", boom)
        called = {"n": 0}

        def spy(plan_path_arg, **kwargs):
            called["n"] += 1
            return EscalateResult(outcome="recommended", target_id=kwargs["step_id"])

        monkeypatch.setattr("plan_tool.detail.escalate_to_split", spy)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            invoker=self._invoker(),
            prompt_fn=self._answer,
            extract_lessons=False,
            allow_split=True,
        )
        assert called["n"] == 1

    def test_phase_b_split_halves_do_not_inherit_the_target_intent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        plan_path = self._pending_plan(tmp_path)
        plan = parse_plan(plan_path)
        target_intent = "make the mixed step work"
        plan.steps[0].intent = target_intent
        write_plan(plan_path, plan)

        generate_detail(
            plan_path,
            repo_root=tmp_path,
            invoker=self._invoker(),
            prompt_fn=self._answer,
            extract_lessons=False,
            allow_split=True,
        )
        plan = parse_plan(plan_path)
        assert plan.step_by_id(1).intent is None
        assert plan.step_by_id(2).intent is None
        assert plan.step_by_id(1).intent != target_intent
        assert plan.step_by_id(2).intent != target_intent


class TestUnattendedSplitRecommendation:
    """Phase B's dropped opt-in/TTY guard: every flagged mixed step enters
    ``escalate_to_split``, and ``recommended`` outcomes surface a
    ``structural-split`` recommendation via ``_emit_split_recommendations``
    on the default (no ``--split``) / non-TTY path — no plan mutation."""

    def _plan(self, tmp_path: Path) -> Path:
        plan_path = tmp_path / "3-split.md"
        plan_path.write_text(_SPLIT_PLAN_PENDING, encoding="utf-8")
        (tmp_path / "renderer.py").write_text("X = 1\n", encoding="utf-8")
        (tmp_path / "foo.py").write_text("Y = 1\n", encoding="utf-8")
        return plan_path

    @staticmethod
    def _mixed_invoker():
        """Flag the target step as mixed; everything else clean."""

        def fake(prompt: str) -> str:
            if "Mixed step" in prompt:
                return _MIXED_AUTHORING
            return _GOOD_BODY

        return fake

    @staticmethod
    def _clean_invoker():
        def fake(_prompt: str) -> str:
            return _GOOD_BODY

        return fake

    @staticmethod
    def _structural_rec(step_id: int = 1, *, suggested: bool = True):
        from plan_tool.review import Recommendation, _make_rec_id

        return Recommendation(
            id=_make_rec_id(step_id, "structural-split", f"structural-split:{step_id}"),
            source="structural-split",
            severity="medium",
            step_id=step_id,
            title=f"Step {step_id} mixes refactor + feature — split it",
            body="The only correct fix is to split it into two type-pure steps.",
            suggested_action=(
                f'plan-tool split <plan> --step {step_id} --into "R" --into "F"'
                if suggested
                else None
            ),
        )

    def test_guard_enters_bridge_without_opt_in_or_tty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # allow_split=False AND non-TTY: the old guard skipped Phase B
        # entirely; the new ``if mixed_steps:`` guard still enters the bridge.
        from plan_tool.launcher import EscalateResult

        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        plan_path = self._plan(tmp_path)
        calls: list[dict] = []

        def spy(_plan_path, **kwargs):
            calls.append(kwargs)
            return EscalateResult(
                outcome="recommended",
                target_id=kwargs["step_id"],
                recommendation=self._structural_rec(kwargs["step_id"]),
            )

        monkeypatch.setattr("plan_tool.detail.escalate_to_split", spy)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            invoker=self._mixed_invoker(),
            extract_lessons=False,
            allow_split=False,
        )
        assert len(calls) == 1
        assert calls[0]["step_id"] == 1
        # The real flag is threaded, not a forced True.
        assert calls[0]["allow_split"] is False

    def test_no_mixed_steps_skips_bridge_and_emission(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        plan_path = self._plan(tmp_path)

        def boom(*_a, **_k):
            raise AssertionError("bridge must not be entered with no mixed step")

        monkeypatch.setattr("plan_tool.detail.escalate_to_split", boom)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            invoker=self._clean_invoker(),
            extract_lessons=False,
            allow_split=False,
        )
        assert "structural splits for" not in capsys.readouterr().err

    def test_default_run_recommends_for_mixed_step(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.launcher import EscalateResult

        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        plan_path = self._plan(tmp_path)

        def stub(_plan_path, **kwargs):
            return EscalateResult(
                outcome="recommended",
                target_id=kwargs["step_id"],
                recommendation=self._structural_rec(kwargs["step_id"]),
            )

        monkeypatch.setattr("plan_tool.detail.escalate_to_split", stub)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            invoker=self._mixed_invoker(),
            extract_lessons=False,
            allow_split=False,
        )
        err = capsys.readouterr().err
        assert "plan-tool split" in err
        # Recommend-only: the plan structure is untouched (no split applied;
        # a normal detail run still writes detail pointers, so assert on the
        # step titles, not byte-equality).
        assert [s.title for s in parse_plan(plan_path).steps] == [
            "Mixed step",
            "Downstream",
        ]

    def test_split_flag_non_tty_recommends(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.launcher import EscalateResult

        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        plan_path = self._plan(tmp_path)

        def stub(_plan_path, **kwargs):
            return EscalateResult(
                outcome="recommended",
                target_id=kwargs["step_id"],
                recommendation=self._structural_rec(kwargs["step_id"]),
            )

        monkeypatch.setattr("plan_tool.detail.escalate_to_split", stub)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            invoker=self._mixed_invoker(),
            extract_lessons=False,
            allow_split=True,  # --split, but non-TTY → bridge recommends
        )
        assert "plan-tool split" in capsys.readouterr().err
        assert [s.title for s in parse_plan(plan_path).steps] == [
            "Mixed step",
            "Downstream",
        ]

    def test_applied_outcome_emits_no_recommendation(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.launcher import EscalateResult

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        plan_path = self._plan(tmp_path)

        def stub(_plan_path, **kwargs):
            return EscalateResult(outcome="applied", target_id=kwargs["step_id"])

        monkeypatch.setattr("plan_tool.detail.escalate_to_split", stub)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            invoker=self._mixed_invoker(),
            prompt_fn=lambda _m: "n",
            extract_lessons=False,
            allow_split=True,
        )
        assert "structural splits for" not in capsys.readouterr().err

    def test_unsafe_outcome_warns_without_recommendation(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.launcher import EscalateResult

        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        plan_path = self._plan(tmp_path)

        def stub(_plan_path, **kwargs):
            return EscalateResult(
                outcome="unsafe", target_id=kwargs["step_id"], blocking=[2]
            )

        monkeypatch.setattr("plan_tool.detail.escalate_to_split", stub)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            invoker=self._mixed_invoker(),
            extract_lessons=False,
            allow_split=False,
        )
        err = capsys.readouterr().err
        assert "cannot recommend split" in err
        assert "[2]" in err
        assert "skipping auto-split" not in err
        assert "structural splits for" not in err

    def test_step_missing_outcome_is_silent(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.launcher import EscalateResult

        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        plan_path = self._plan(tmp_path)

        def stub(_plan_path, **kwargs):
            return EscalateResult(outcome="step-missing", target_id=kwargs["step_id"])

        monkeypatch.setattr("plan_tool.detail.escalate_to_split", stub)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            invoker=self._mixed_invoker(),
            extract_lessons=False,
            allow_split=False,
        )
        err = capsys.readouterr().err
        assert "cannot recommend split" not in err
        assert "structural splits for" not in err

    def test_recommendation_keeps_rc_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.launcher import EscalateResult

        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        plan_path = self._plan(tmp_path)

        def stub(_plan_path, **kwargs):
            return EscalateResult(
                outcome="recommended",
                target_id=kwargs["step_id"],
                recommendation=self._structural_rec(kwargs["step_id"]),
            )

        monkeypatch.setattr("plan_tool.detail.escalate_to_split", stub)
        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            invoker=self._mixed_invoker(),
            extract_lessons=False,
            allow_split=False,
        )
        # A recommend-only run carries no failure DetailResult — nothing
        # flips the run's exit code.
        assert all(r.skipped_reason is None or r.written for r in results)

    def test_emit_split_recommendations_empty_is_noop(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from plan_tool.detail import _emit_split_recommendations

        _emit_split_recommendations([], plan_slug="x")
        out = capsys.readouterr()
        assert out.err == ""
        assert out.out == ""

    def test_emit_split_recommendations_renders_action(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from plan_tool.detail import _emit_split_recommendations
        from plan_tool.review import triage_reason

        rec = self._structural_rec(1, suggested=True)
        _emit_split_recommendations([rec], plan_slug="myplan")
        err = capsys.readouterr().err
        assert "myplan" in err
        assert rec.title in err
        assert triage_reason(rec) in err
        assert rec.body in err
        assert rec.suggested_action in err

        # A rec with no suggested_action omits the action sub-line.
        bare = self._structural_rec(1, suggested=False)
        _emit_split_recommendations([bare], plan_slug="myplan")
        err2 = capsys.readouterr().err
        assert bare.title in err2
        assert "plan-tool split <plan>" not in err2


@pytest.mark.integration
class TestSplitStepOnDemand:
    """``split_step``: deterministic, operator-named split of one step."""

    def _pending_plan(self, tmp_path: Path) -> Path:
        plan_path = tmp_path / "3-split.md"
        plan_path.write_text(_SPLIT_PLAN_PENDING, encoding="utf-8")
        (tmp_path / "renderer.py").write_text("X = 1\n", encoding="utf-8")
        (tmp_path / "foo.py").write_text("Y = 1\n", encoding="utf-8")
        return plan_path

    def _owned_pending_plan(self, tmp_path: Path) -> tuple[Path, list[str]]:
        concept_ids = ["a" * 64, "b" * 64]
        plan_path = self._pending_plan(tmp_path)
        plan = parse_plan(plan_path)
        plan.steps[0].concept_ids = concept_ids
        write_plan(plan_path, plan)
        return plan_path, concept_ids

    def test_split_step_copies_concept_ids_to_each_named_half(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.detail import split_step

        plan_path, concept_ids = self._owned_pending_plan(tmp_path)
        split_step(
            plan_path,
            target_id=1,
            new_titles=["First half", "Second half"],
            repo_root=tmp_path,
            author_details=False,
        )
        plan = parse_plan(plan_path)
        assert [plan.step_by_id(i).concept_ids for i in (1, 2)] == [
            concept_ids,
            concept_ids,
        ]

    def test_split_step_dry_run_preserves_concept_ids_without_writing(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.detail import split_step

        plan_path, _concept_ids = self._owned_pending_plan(tmp_path)
        before = plan_path.read_bytes()
        result = split_step(
            plan_path,
            target_id=1,
            new_titles=["First half", "Second half"],
            repo_root=tmp_path,
            dry_run=True,
        )
        assert result.dry_run is True
        assert plan_path.read_bytes() == before

    def test_split_step_records_step_provenance(self, tmp_path: Path) -> None:
        """#238: a real (non-dry-run) split records the new halves' titles
        as step-provenance telemetry, so plan-mass audit-induced-growth can
        find them later."""
        from plan_tool.detail import split_step
        from plan_tool.telemetry import read_step_provenance_titles

        plan_path = self._pending_plan(tmp_path)
        split_step(
            plan_path,
            target_id=1,
            new_titles=["First half", "Second half"],
            repo_root=tmp_path,
            author_details=False,
        )
        titles = read_step_provenance_titles(tmp_path, "split")
        assert titles == {"First half", "Second half"}

    def test_split_step_dry_run_records_no_provenance(self, tmp_path: Path) -> None:
        from plan_tool.detail import split_step
        from plan_tool.telemetry import read_step_provenance_titles

        plan_path = self._pending_plan(tmp_path)
        split_step(
            plan_path,
            target_id=1,
            new_titles=["First half", "Second half"],
            repo_root=tmp_path,
            dry_run=True,
        )
        assert read_step_provenance_titles(tmp_path, "split") == set()

    def test_split_step_authors_halves_without_losing_concept_ids(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.detail import split_step

        plan_path, concept_ids = self._owned_pending_plan(tmp_path)
        split_step(
            plan_path,
            target_id=1,
            new_titles=["First half", "Second half"],
            repo_root=tmp_path,
            invoker=lambda _prompt: _GOOD_BODY,
            prompt_fn=lambda _message: "n",
        )
        plan = parse_plan(plan_path)
        assert [plan.step_by_id(i).concept_ids for i in (1, 2)] == [
            concept_ids,
            concept_ids,
        ]
        assert all(plan.step_by_id(i).detail for i in (1, 2))

    def test_splits_renumbers_and_authors_halves(self, tmp_path: Path) -> None:
        from plan_tool.detail import split_step

        plan_path = self._pending_plan(tmp_path)
        result = split_step(
            plan_path,
            target_id=1,
            new_titles=["Extract the validator", "Wire it into the handler"],
            repo_root=tmp_path,
            invoker=lambda _p: _GOOD_BODY,
            prompt_fn=lambda _m: "n",
        )
        assert result.new_ids == [1, 2]
        assert result.original_title == "Mixed step"

        plan = parse_plan(plan_path)
        # Target replaced in place by the two named halves; downstream pushed.
        assert [s.title for s in plan.steps] == [
            "Extract the validator",
            "Wire it into the handler",
            "Downstream",
        ]
        # Halves chain (first inherits target's deps; second on first);
        # downstream repoints to the terminal half.
        assert plan.step_by_id(2).depends_on == [1]
        assert plan.step_by_id(3).depends_on == [2]
        # Halves inherit the parent's complexity and each gets a detail file.
        for sid in (1, 2):
            assert plan.step_by_id(sid).detail is not None
            assert (tmp_path / plan.step_by_id(sid).detail).is_file()
        # Both halves were authored this run.
        assert sorted(r.step_id for r in result.detail_results if r.written) == [
            1, 2,
        ]

    def test_splits_current_step_inherits_status_on_first_half(
        self, tmp_path: Path
    ) -> None:
        # Splitting the `current` step keeps exactly one current step: the
        # first half inherits `current`, later halves are pending (the
        # authored-but-unrun-plan case the split-safety fix unblocks).
        from plan_tool.detail import split_step

        plan_path = tmp_path / "3-split.md"
        plan_path.write_text(
            _SPLIT_PLAN_PENDING.replace(
                "    title: Mixed step\n",
                "    title: Mixed step\n    status: current\n",
            ),
            encoding="utf-8",
        )
        (tmp_path / "renderer.py").write_text("X = 1\n", encoding="utf-8")
        (tmp_path / "foo.py").write_text("Y = 1\n", encoding="utf-8")

        split_step(
            plan_path,
            target_id=1,
            new_titles=["Extract the validator", "Wire it into the handler"],
            repo_root=tmp_path,
            invoker=lambda _p: _GOOD_BODY,
            prompt_fn=lambda _m: "n",
        )

        plan = parse_plan(plan_path)
        assert plan.step_by_id(1).status == StepStatus.CURRENT
        assert plan.step_by_id(2).status == StepStatus.PENDING
        assert plan.step_by_id(3).status == StepStatus.PENDING
        # Schema invariant: exactly one current step survives the split.
        assert [
            s.id for s in plan.steps if s.status == StepStatus.CURRENT
        ] == [1]

    def test_requires_at_least_two_titles(self, tmp_path: Path) -> None:
        from plan_tool.detail import split_step

        plan_path = self._pending_plan(tmp_path)
        with pytest.raises(DetailError, match="at least two"):
            split_step(
                plan_path,
                target_id=1,
                new_titles=["only one"],
                repo_root=tmp_path,
                invoker=lambda _p: _GOOD_BODY,
            )

    def test_unknown_step_raises(self, tmp_path: Path) -> None:
        from plan_tool.detail import split_step

        plan_path = self._pending_plan(tmp_path)
        with pytest.raises(DetailError, match="step 99 not found"):
            split_step(
                plan_path,
                target_id=99,
                new_titles=["a", "b"],
                repo_root=tmp_path,
                invoker=lambda _p: _GOOD_BODY,
            )

    def test_duplicate_titles_rejected(self, tmp_path: Path) -> None:
        # Two sub-steps with the same title (case-insensitive) is always a
        # mistake — reject before any mutation.
        from plan_tool.detail import split_step

        plan_path = self._pending_plan(tmp_path)
        with pytest.raises(DetailError, match="distinct"):
            split_step(
                plan_path,
                target_id=1,
                new_titles=["Extract it", "extract it"],
                repo_root=tmp_path,
                invoker=lambda _p: _GOOD_BODY,
            )
        # Plan untouched.
        assert [s.title for s in parse_plan(plan_path).steps] == [
            "Mixed step",
            "Downstream",
        ]

    def test_non_canonical_ids_refused(self, tmp_path: Path) -> None:
        # The renumber/migration primitives equate id with position; a plan
        # with a gap (hand-edited) must be refused, not silently corrupted.
        from plan_tool.detail import split_step

        plan_path = tmp_path / "3-split.md"
        plan_path.write_text(
            "---\ntitle: Split\nstatus: in-progress\npriority: medium\n"
            "steps:\n"
            "  - id: 1\n    title: First\n    files:\n      - renderer.py\n"
            "  - id: 3\n    title: Third\n    files:\n      - foo.py\n"
            "    depends_on: [1]\n"
            "---\n\n# Split\n",
            encoding="utf-8",
        )
        (tmp_path / "renderer.py").write_text("X = 1\n", encoding="utf-8")
        (tmp_path / "foo.py").write_text("Y = 1\n", encoding="utf-8")
        with pytest.raises(DetailError, match="not canonical"):
            split_step(
                plan_path,
                target_id=1,
                new_titles=["a", "b"],
                repo_root=tmp_path,
                invoker=lambda _p: _GOOD_BODY,
            )

    def test_dry_run_previews_without_mutation(self, tmp_path: Path) -> None:
        from plan_tool.detail import split_step

        plan_path = self._pending_plan(tmp_path)
        before = plan_path.read_text(encoding="utf-8")

        def _boom(_p: str) -> str:
            raise AssertionError("dry-run must not author")

        result = split_step(
            plan_path,
            target_id=1,
            new_titles=["First half", "Second half"],
            repo_root=tmp_path,
            dry_run=True,
            invoker=_boom,
        )
        assert result.dry_run is True
        assert result.detail_results == []
        # Renumber: target 1 folds into terminal id 2; old step 2 shifts to 3.
        assert result.renumber == [(1, 2), (2, 3)]
        assert result.new_plan == [
            (1, "First half", []),
            (2, "Second half", [1]),
            (3, "Downstream", [2]),
        ]
        # Nothing on disk changed.
        assert plan_path.read_text(encoding="utf-8") == before
        assert not (tmp_path / "plan-details").exists()

    def test_unsafe_downstream_refused(self, tmp_path: Path) -> None:
        # A downstream step that has already run carries id-keyed state a
        # renumber would orphan, so the split is refused before any edit.
        from plan_tool.detail import split_step

        plan_path = tmp_path / "3-split.md"
        plan_path.write_text(
            "---\ntitle: Split\nstatus: in-progress\npriority: medium\n"
            "steps:\n"
            "  - id: 1\n    title: Mixed step\n    files:\n      - renderer.py\n"
            "  - id: 2\n    title: Downstream\n    files:\n      - foo.py\n"
            "    depends_on: [1]\n    status: done\n"
            "---\n\n# Split\n",
            encoding="utf-8",
        )
        (tmp_path / "renderer.py").write_text("X = 1\n", encoding="utf-8")
        (tmp_path / "foo.py").write_text("Y = 1\n", encoding="utf-8")
        with pytest.raises(DetailError, match=r"step\(s\) \[2\] are done"):
            split_step(
                plan_path,
                target_id=1,
                new_titles=["a", "b"],
                repo_root=tmp_path,
                invoker=lambda _p: _GOOD_BODY,
            )
        # Plan untouched.
        assert [s.title for s in parse_plan(plan_path).steps] == [
            "Mixed step",
            "Downstream",
        ]

    def test_no_detail_splits_without_authoring(self, tmp_path: Path) -> None:
        from plan_tool.detail import split_step

        plan_path = self._pending_plan(tmp_path)

        def _boom(_p: str) -> str:  # must never be invoked
            raise AssertionError("author_details=False must not invoke claude")

        result = split_step(
            plan_path,
            target_id=1,
            new_titles=["First half", "Second half"],
            repo_root=tmp_path,
            author_details=False,
            invoker=_boom,
        )
        assert result.detail_results == []
        plan = parse_plan(plan_path)
        assert [s.title for s in plan.steps][:2] == ["First half", "Second half"]
        # Halves carry no detail pointer yet.
        assert plan.step_by_id(1).detail is None
        assert plan.step_by_id(2).detail is None

    def test_split_target_with_own_detail_file_archives_orphan(
        self, tmp_path: Path
    ) -> None:
        # The real BLOCKED-finding case: the step being split is already
        # detailed. Its old file becomes a same-id-prefix orphan once the
        # first half is authored — `_archive_orphan_details` must sweep it
        # into archive/ so it isn't left referencing nothing.
        from plan_tool.detail import split_step

        plan_path = self._pending_plan(tmp_path)
        ddir = tmp_path / "plan-details" / "split"
        ddir.mkdir(parents=True)
        (ddir / "01-mixed-step.md").write_text("# Mixed step\n", encoding="utf-8")
        update_step_detail_field(
            plan_path, 1, "plan-details/split/01-mixed-step.md"
        )

        split_step(
            plan_path,
            target_id=1,
            new_titles=["First half", "Second half"],
            repo_root=tmp_path,
            invoker=lambda _p: _GOOD_BODY,
            prompt_fn=lambda _m: "n",
        )
        plan = parse_plan(plan_path)
        # Both halves authored to canonical files on disk.
        for sid in (1, 2):
            assert (tmp_path / plan.step_by_id(sid).detail).is_file()
        # The orphaned old target file is gone from the active dir and
        # archived (not left stranded next to the new id-1 file).
        assert not (ddir / "01-mixed-step.md").exists()
        assert (ddir / "archive" / "01-mixed-step.md").exists()

    def test_downstream_detail_file_migrated(self, tmp_path: Path) -> None:
        # A downstream step with an existing detail file gets its NN- prefix
        # renamed to the post-split id and its pointer repointed.
        from plan_tool.detail import split_step

        plan_path = self._pending_plan(tmp_path)
        ddir = tmp_path / "plan-details" / "split"
        ddir.mkdir(parents=True)
        (ddir / "02-downstream.md").write_text("# Downstream\n", encoding="utf-8")
        update_step_detail_field(
            plan_path, 2, "plan-details/split/02-downstream.md"
        )

        split_step(
            plan_path,
            target_id=1,
            new_titles=["First half", "Second half"],
            repo_root=tmp_path,
            invoker=lambda _p: _GOOD_BODY,
            prompt_fn=lambda _m: "n",
        )
        plan = parse_plan(plan_path)
        downstream = plan.step_by_id(3)
        assert downstream.title == "Downstream"
        assert downstream.detail == "plan-details/split/03-downstream.md"
        assert (tmp_path / downstream.detail).is_file()
        assert not (ddir / "02-downstream.md").exists()

    def test_split_halves_do_not_inherit_the_target_intent(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.detail import split_step

        plan_path = self._pending_plan(tmp_path)
        plan = parse_plan(plan_path)
        plan.steps[0].intent = "make the mixed step work"
        write_plan(plan_path, plan)

        split_step(
            plan_path,
            target_id=1,
            new_titles=["First half", "Second half"],
            repo_root=tmp_path,
            author_details=False,
        )
        plan = parse_plan(plan_path)
        assert plan.step_by_id(1).intent is None
        assert plan.step_by_id(2).intent is None

    def test_split_leaves_the_plan_intent_untouched(self, tmp_path: Path) -> None:
        from plan_tool.detail import split_step

        plan_path = self._pending_plan(tmp_path)
        plan = parse_plan(plan_path)
        plan.intent = "prove the whole plan purpose"
        plan.steps[0].intent = "make the mixed step work"
        write_plan(plan_path, plan)

        split_step(
            plan_path,
            target_id=1,
            new_titles=["First half", "Second half"],
            repo_root=tmp_path,
            author_details=False,
        )
        assert parse_plan(plan_path).intent == "prove the whole plan purpose"

    def test_split_writes_no_intent_key_when_nothing_carries_one(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.detail import split_step

        plan_path = self._pending_plan(tmp_path)
        assert "intent:" not in plan_path.read_text(encoding="utf-8")

        split_step(
            plan_path,
            target_id=1,
            new_titles=["First half", "Second half"],
            repo_root=tmp_path,
            author_details=False,
        )
        assert "intent:" not in plan_path.read_text(encoding="utf-8")


    def test_split_step_threads_depends_on_notes(self, tmp_path: Path) -> None:
        from plan_tool.detail import split_step
        from plan_tool.parser import parse_plan, write_plan

        plan_path = self._pending_plan(tmp_path)
        plan = parse_plan(plan_path)
        plan.steps[1] = plan.steps[1].model_copy(
            update={
                "depends_on_notes": {1: "consumes mixed step"},
            }
        )
        write_plan(plan_path, plan)

        split_step(
            plan_path,
            target_id=1,
            new_titles=["Refactor half", "Feature half"],
            repo_root=tmp_path,
            author_details=False,
        )
        plan = parse_plan(plan_path)
        downstream = plan.step_by_id(3)
        assert downstream.depends_on == [2]
        assert downstream.depends_on_notes == {}


@pytest.mark.integration
class TestGenerateDetailIdempotency:
    def test_skips_step_with_existing_detail_and_file(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)

        # Pre-populate: write the detail file and set step.detail.
        detail_path = _detail_path_for(tmp_path, 1, "wire-up-renderer")
        detail_path.parent.mkdir(parents=True)
        detail_path.write_text("# Already here\n", encoding="utf-8")
        update_step_detail_field(
            plan_path, 1, "plan-details/orch/01-wire-up-renderer.md"
        )

        def fake(prompt: str) -> str:
            raise AssertionError("invoker should not be called for skipped step")

        results = generate_detail(
            plan_path, repo_root=tmp_path, step_id=1, invoker=fake
        )
        assert len(results) == 1
        assert results[0].written is False
        assert "already exists" in (results[0].skipped_reason or "")
        # File contents unchanged.
        assert detail_path.read_text(encoding="utf-8") == "# Already here\n"

    def test_force_overwrites_existing_detail(self, tmp_path: Path) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        detail_path = _detail_path_for(tmp_path, 1, "wire-up-renderer")
        detail_path.parent.mkdir(parents=True)
        detail_path.write_text("# Stale\n", encoding="utf-8")
        update_step_detail_field(
            plan_path, 1, "plan-details/orch/01-wire-up-renderer.md"
        )

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            force=True,
            invoker=lambda prompt: _GOOD_BODY,
        )
        assert results[0].written is True
        assert "Wire up the renderer" in detail_path.read_text(encoding="utf-8")
        assert "# Stale" not in detail_path.read_text(encoding="utf-8")

    def test_set_detail_with_missing_file_is_treated_as_lacking(
        self, tmp_path: Path
    ) -> None:
        """Pointer without the file = stale — regenerate, not skip."""
        plan_path = _write_orchestrator_plan(tmp_path)
        # Set the pointer but never write the file.
        update_step_detail_field(
            plan_path, 1, "plan-details/orch/01-wire-up-renderer.md"
        )

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda prompt: _GOOD_BODY,
        )
        assert results[0].written is True
        assert results[0].output_path.is_file()

    def test_authored_file_carries_the_current_marker_after_the_h1(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda prompt: _GOOD_BODY,
        )
        assert results[0].written is True

        text = results[0].output_path.read_text(encoding="utf-8")
        lines = text.splitlines()
        first_nonblank_after_h1 = next(
            line for line in lines[1:] if line.strip()
        )
        assert first_nonblank_after_h1 == render_detail_format_version_marker()
        require_supported_detail_format_version(text)  # raises on failure

    def test_model_proposed_marker_never_reaches_disk(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        proposed = (
            "# Step 1 — Wire up the renderer\n"
            "<!-- plan-tool:detail-format-version: 999 -->\n"
            + _GOOD_BODY.split("\n", 1)[1]
        )

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda prompt: proposed,
        )
        assert results[0].written is True

        text = results[0].output_path.read_text(encoding="utf-8")
        assert "999" not in text
        assert text.count("plan-tool:detail-format-version") == 1
        assert render_detail_format_version_marker() in text

    def test_direct_recovery_archives_a_refused_file_without_reading_any_bundle_detail(
        self, tmp_path: Path
    ) -> None:
        """``generate_detail(..., step_id=1, force=True, recovery_only=True)``
        — the ``detail --recover-refused`` signal — replaces exactly the
        named target, even though two siblings' own detail files declare an
        unsupported marker (which would otherwise raise ``DetailFormatError``
        via the already-implemented heuristic scan)."""
        plan_path = _write_recovery_plan(tmp_path)

        target_path = _recovery_detail_path(tmp_path, 1, "wire-up-renderer")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_original = (
            f"# Step 1\n{render_detail_format_version_marker(999)}\n\n"
            "## Body\n\nrefused target.\n"
        )
        target_path.write_text(target_original, encoding="utf-8")
        update_step_detail_field(
            plan_path, 1, _repo_relative(target_path, tmp_path)
        )
        sibling_2 = _seed_refused_sibling(tmp_path, plan_path, 2, "build-the-widget")
        sibling_3 = _seed_refused_sibling(tmp_path, plan_path, 3, "ship-the-gadget")
        sibling_2_bytes = sibling_2.read_bytes()
        sibling_3_bytes = sibling_3.read_bytes()

        captured_prompts: list[str] = []

        def fake(prompt: str) -> str:
            captured_prompts.append(prompt)
            return _GOOD_BODY

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            force=True,
            recovery_only=True,
            invoker=fake,
            extract_lessons=False,
        )

        assert results[0].written is True
        assert len(captured_prompts) == 1
        prompt = captured_prompts[0]
        # No sibling body, already-implemented excerpt, or the siblings'
        # refused ``999`` value reached the prompt.
        assert "no bundle detail file was read" in prompt
        assert "999" not in prompt
        assert "refused target" not in prompt

        # Sibling bytes are untouched.
        assert sibling_2.read_bytes() == sibling_2_bytes
        assert sibling_3.read_bytes() == sibling_3_bytes

        # Target archived byte-for-byte, replaced with a stamped body.
        archive_dir = target_path.parent / "archive"
        archived = [
            p for p in archive_dir.iterdir()
            if p.name.startswith(target_path.stem + ".")
        ]
        assert len(archived) == 1
        assert archived[0].read_text(encoding="utf-8") == target_original

        written_text = target_path.read_text(encoding="utf-8")
        require_supported_detail_format_version(written_text)
        assert render_detail_format_version_marker() in written_text.splitlines()

    def test_direct_recovery_reauthors_a_carrierless_detail_without_reading_it(
        self, tmp_path: Path
    ) -> None:
        """A target with no valid carrier H1 (the legacy pre-marker shape)
        follows the same ``--force --recover-refused`` route: archived
        byte-for-byte, replaced with a stamped current body."""
        plan_path = _write_recovery_plan(tmp_path)

        target_path = _recovery_detail_path(tmp_path, 1, "wire-up-renderer")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_original = "## Body only — no H1 at all\n\nlegacy shape.\n"
        target_path.write_text(target_original, encoding="utf-8")
        update_step_detail_field(
            plan_path, 1, _repo_relative(target_path, tmp_path)
        )

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            force=True,
            recovery_only=True,
            invoker=lambda prompt: _GOOD_BODY,
            extract_lessons=False,
        )

        assert results[0].written is True
        archive_dir = target_path.parent / "archive"
        archived = [
            p for p in archive_dir.iterdir()
            if p.name.startswith(target_path.stem + ".")
        ]
        assert len(archived) == 1
        assert archived[0].read_text(encoding="utf-8") == target_original

        written_text = target_path.read_text(encoding="utf-8")
        require_supported_detail_format_version(written_text)
        assert render_detail_format_version_marker() in written_text.splitlines()


@pytest.mark.integration
class TestGenerateDetailAdoptsOrphan:
    """A detail file present on disk whose `detail:` pointer was never
    persisted (e.g. a split that renumbered an unpointed step) is adopted —
    the pointer is reattached and the file is NOT re-authored/clobbered."""

    def test_adopts_canonical_orphan_without_invoking(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        detail_path = _detail_path_for(tmp_path, 1, "wire-up-renderer")
        detail_path.parent.mkdir(parents=True)
        detail_path.write_text("# Already here\n", encoding="utf-8")
        # NOTE: deliberately do NOT call update_step_detail_field — the
        # pointer is unset, mirroring the orphaned-after-split state.

        def fake(prompt: str) -> str:
            raise AssertionError("invoker must not run for an adopted orphan")

        results = generate_detail(
            plan_path, repo_root=tmp_path, step_id=1, invoker=fake
        )
        # File untouched.
        assert detail_path.read_text(encoding="utf-8") == "# Already here\n"
        # Pointer reattached and persisted.
        plan = parse_plan(plan_path)
        assert (
            plan.step_by_id(1).detail
            == "plan-details/orch/01-wire-up-renderer.md"
        )
        # Step is skipped (idempotent), not freshly written.
        assert results[0].written is False

    def test_slug_drift_orphan_is_reauthored_not_adopted(
        self, tmp_path: Path
    ) -> None:
        # A `01-` sibling under a *different* slug (pointer unset) is NOT
        # adopted — it's superseded; the authoring path re-authors the
        # canonical file and archives the stale one (existing policy).
        plan_path = _write_orchestrator_plan(tmp_path)
        bundle = tmp_path / "plan-details" / "orch"
        bundle.mkdir(parents=True)
        stale = bundle / "01-old-renderer-slug.md"
        stale.write_text("# Original body\n", encoding="utf-8")

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda prompt: _GOOD_BODY,
            extract_lessons=False,
        )
        assert results[0].written is True
        canonical = _detail_path_for(tmp_path, 1, "wire-up-renderer")
        assert "Wire up the renderer" in canonical.read_text(encoding="utf-8")
        # Stale orphan swept into archive/, not adopted in place.
        assert not stale.exists()
        assert (bundle / "archive" / "01-old-renderer-slug.md").is_file()

    def test_force_does_not_adopt_and_reauthors(self, tmp_path: Path) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        detail_path = _detail_path_for(tmp_path, 1, "wire-up-renderer")
        detail_path.parent.mkdir(parents=True)
        detail_path.write_text("# Stale orphan\n", encoding="utf-8")

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            force=True,
            invoker=lambda prompt: _GOOD_BODY,
        )
        assert results[0].written is True
        assert "Wire up the renderer" in detail_path.read_text(encoding="utf-8")
        assert "# Stale orphan" not in detail_path.read_text(encoding="utf-8")


@pytest.mark.integration
class TestGenerateDetailReplacePrompt:
    """Replace-or-skip prompt fires when an existing detail file is hit
    without ``--force``. TTY only — non-TTY callers auto-decline so the
    historical "skip if exists" behavior is preserved for CI / piped use.
    """

    def _seed_existing_detail(self, tmp_path: Path) -> Path:
        plan_path = _write_orchestrator_plan(tmp_path)
        detail_path = _detail_path_for(tmp_path, 1, "wire-up-renderer")
        detail_path.parent.mkdir(parents=True)
        detail_path.write_text("# Old body\n", encoding="utf-8")
        update_step_detail_field(
            plan_path, 1, "plan-details/orch/01-wire-up-renderer.md"
        )
        return plan_path

    def test_decline_skips_and_leaves_file_untouched(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = self._seed_existing_detail(tmp_path)
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        def boom_invoker(prompt: str) -> str:
            raise AssertionError("invoker should not run when user skips")

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=boom_invoker,
            extract_lessons=False,
            prompt_fn=lambda _q: "n",
        )
        assert results[0].written is False
        assert "already exists" in (results[0].skipped_reason or "")
        detail_path = _detail_path_for(tmp_path, 1, "wire-up-renderer")
        assert detail_path.read_text(encoding="utf-8") == "# Old body\n"
        # Nothing should have been archived — the prior file stayed put.
        assert not (detail_path.parent / "archive").exists()

    def test_accept_archives_prior_and_writes_new(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = self._seed_existing_detail(tmp_path)
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda prompt: _GOOD_BODY,
            extract_lessons=False,
            prompt_fn=lambda _q: "y",
        )
        assert results[0].written is True

        canonical = _detail_path_for(tmp_path, 1, "wire-up-renderer")
        # Canonical name preserved, new body landed.
        assert "Wire up the renderer" in canonical.read_text(encoding="utf-8")
        # Old body lives under archive/ with a timestamp-renamed stem.
        archive_dir = canonical.parent / "archive"
        archived = [
            p for p in archive_dir.iterdir()
            if p.name.startswith(canonical.stem + ".")
            and p.suffix == ".md"
        ]
        assert len(archived) == 1
        assert archived[0].read_text(encoding="utf-8") == "# Old body\n"

    def test_non_tty_auto_declines(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CI / piped contexts must keep the historical idempotent skip."""
        plan_path = self._seed_existing_detail(tmp_path)
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)

        def explode_prompt(_q: str) -> str:
            raise AssertionError("prompt_fn must not be called on non-TTY")

        def boom_invoker(prompt: str) -> str:
            raise AssertionError("invoker must not run on non-TTY skip")

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=boom_invoker,
            extract_lessons=False,
            prompt_fn=explode_prompt,
        )
        assert results[0].written is False
        assert "already exists" in (results[0].skipped_reason or "")
        detail_path = _detail_path_for(tmp_path, 1, "wire-up-renderer")
        assert detail_path.read_text(encoding="utf-8") == "# Old body\n"


def _ckpt_path_for(tmp_path: Path, step_id: int) -> Path:
    return (
        tmp_path
        / ".plan-tool"
        / "checkpoints"
        / "orch"
        / f"detail-step-{step_id:02d}.json"
    )


@pytest.mark.integration
class TestGenerateDetailResume:
    """Per-step checkpoint memoization across runs.

    The checkpoint lives between a successful claude parse and a durable
    on-disk detail file. On success it's cleaned up; on a mid-run failure
    (plan-update raise, write OSError) it persists so the next run can
    skip the claude call.
    """

    def test_first_run_writes_checkpoint_then_discards_it(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda prompt: _GOOD_BODY,
            extract_lessons=False,
        )
        assert results[0].written is True
        # Detail file on disk, checkpoint discarded post-commit.
        assert _detail_path_for(tmp_path, 1, "wire-up-renderer").is_file()
        assert not _ckpt_path_for(tmp_path, 1).exists()

    def test_checkpoint_written_when_plan_update_fails_then_recoverable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        from plan_tool import detail as detail_module

        def boom(*args, **kwargs):
            raise DetailError("frontmatter exploded")

        monkeypatch.setattr(detail_module, "update_step_detail_field", boom)

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda prompt: _GOOD_BODY,
            extract_lessons=False,
        )
        # Plan update failed → result is unwritten, but the checkpoint
        # was saved before the failing update.
        assert results[0].written is False
        ckpt_path = _ckpt_path_for(tmp_path, 1)
        assert ckpt_path.is_file()
        import json

        data = json.loads(ckpt_path.read_text(encoding="utf-8"))
        # ``parse_detail_response`` strips trailing whitespace, so the
        # cached payload is the parsed body (not the raw invoker return).
        assert data["payload"] == parse_detail_response(_GOOD_BODY)
        plan = parse_plan(plan_path)
        assert data["input_hash"] == _detail_step_input_hash(
            plan_path, plan.step_by_id(1)
        )

        # Restore the real update_step_detail_field; re-run with an invoker
        # that explodes if called. The detail FILE is already on disk from
        # phase 1's author — only the pointer failed to persist. The
        # adoption pre-pass recovers this exact partial-write state by
        # reattaching the pointer (no claude re-call → boom_invoker proves
        # it), so the step idempotently skips rather than re-committing.
        monkeypatch.undo()

        def boom_invoker(prompt: str) -> str:
            raise AssertionError("invoker should not be called when cache hits")

        results2 = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=boom_invoker,
            extract_lessons=False,
        )
        assert results2[0].written is False
        assert "already exists" in (results2[0].skipped_reason or "")
        # Pointer now persisted and the file carries the authored body.
        plan2 = parse_plan(plan_path)
        assert (
            plan2.step_by_id(1).detail
            == "plan-details/orch/01-wire-up-renderer.md"
        )
        assert "Wire up the renderer" in _detail_path_for(
            tmp_path, 1, "wire-up-renderer"
        ).read_text(encoding="utf-8")
        # The now-vestigial checkpoint is left for the next run's
        # hash-match self-discard (the adoption skip doesn't touch it).
        assert ckpt_path.exists()

    def test_resume_uses_cached_body_when_input_hash_matches(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)

        # Seed a valid checkpoint by hand, mimicking a prior interrupted run.
        ckpt_path = checkpoint_path(
            tmp_path,
            "orch",
            _DETAIL_CHECKPOINT_NAME.format(step_id=step.id),
        )
        save_checkpoint(
            ckpt_path,
            Checkpoint(
                input_hash=_detail_step_input_hash(plan_path, step),
                payload=_GOOD_BODY,
                created_at=_fresh_now(),
            ),
        )

        def boom_invoker(prompt: str) -> str:
            raise AssertionError("invoker should not be called on cache hit")

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=boom_invoker,
            extract_lessons=False,
        )
        assert results[0].written is True
        detail_path = _detail_path_for(tmp_path, 1, "wire-up-renderer")
        assert _GOOD_BODY_STAMPED in detail_path.read_text(encoding="utf-8")
        # Checkpoint discarded post-commit.
        assert not ckpt_path.exists()

    def test_resume_fails_cleanly_when_a_cached_body_no_longer_parses(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        ckpt_path = checkpoint_path(
            tmp_path,
            "orch",
            _DETAIL_CHECKPOINT_NAME.format(step_id=step.id),
        )
        save_checkpoint(
            ckpt_path,
            Checkpoint(
                input_hash=_detail_step_input_hash(plan_path, step),
                payload="preamble\n\n  " + _GOOD_BODY,
                created_at=_fresh_now(),
            ),
        )
        calls: list[str] = []

        def no_invoke(prompt: str) -> str:
            calls.append(prompt)
            return _GOOD_BODY

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=no_invoke,
            extract_lessons=False,
        )

        assert results[0].written is False
        assert "no longer satisfies" in (results[0].skipped_reason or "")
        assert calls == []
        assert not ckpt_path.exists()

    def test_resumed_checkpoint_body_is_stamped_at_write(
        self, tmp_path: Path
    ) -> None:
        """A resumed checkpoint payload is stamped at write time, same as a
        freshly-invoked body — the checkpoint itself stays unstamped
        (pinned by ``test_checkpoint_written_when_plan_update_fails_then_
        recoverable``'s payload-equality assertion above)."""
        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)

        marker_free_payload = parse_detail_response(_GOOD_BODY)
        assert marker_free_payload is not None
        assert "plan-tool:detail-format-version" not in marker_free_payload

        ckpt_path = checkpoint_path(
            tmp_path,
            "orch",
            _DETAIL_CHECKPOINT_NAME.format(step_id=step.id),
        )
        save_checkpoint(
            ckpt_path,
            Checkpoint(
                input_hash=_detail_step_input_hash(plan_path, step),
                payload=marker_free_payload,
                created_at=_fresh_now(),
            ),
        )

        def boom_invoker(prompt: str) -> str:
            raise AssertionError("invoker should not be called on cache hit")

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=boom_invoker,
            extract_lessons=False,
        )
        assert results[0].written is True
        text = _detail_path_for(tmp_path, 1, "wire-up-renderer").read_text(
            encoding="utf-8"
        )
        require_supported_detail_format_version(text)
        assert render_detail_format_version_marker() in text.splitlines()

    def test_resume_cache_miss_on_title_change_re_invokes(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)

        # Seed checkpoint against the ORIGINAL title.
        ckpt_path = checkpoint_path(
            tmp_path,
            "orch",
            _DETAIL_CHECKPOINT_NAME.format(step_id=step.id),
        )
        save_checkpoint(
            ckpt_path,
            Checkpoint(
                input_hash=_detail_step_input_hash(plan_path, step),
                payload=_GOOD_BODY,
                created_at=_fresh_now(),
            ),
        )

        # Mutate the title via parse_plan / write_plan round-trip.
        step.title = "Wire up the renderer differently"
        write_plan(plan_path, plan)

        calls: list[str] = []

        def fake(prompt: str) -> str:
            calls.append(prompt)
            return _GOOD_BODY.replace(
                "# Step 1 — Wire up the renderer",
                "# Step 1 — Wire up the renderer differently",
            )

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=fake,
            extract_lessons=False,
        )
        assert results[0].written is True
        assert len(calls) == 1
        body = results[0].output_path.read_text(encoding="utf-8")
        assert "differently" in body

    def test_resume_cache_miss_on_files_reorder_re_invokes(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(2)

        # Seed checkpoint against the original ordering ([foo.py]).
        ckpt_path = checkpoint_path(
            tmp_path,
            "orch",
            _DETAIL_CHECKPOINT_NAME.format(step_id=step.id),
        )
        save_checkpoint(
            ckpt_path,
            Checkpoint(
                input_hash=_detail_step_input_hash(plan_path, step),
                payload=_GOOD_BODY,
                created_at=_fresh_now(),
            ),
        )

        # Add a second file then reorder — hash sensitive to order.
        (tmp_path / "renderer.py").write_text(
            "def render(plan):\n    return None\n", encoding="utf-8"
        )
        step.files = ["renderer.py", "foo.py"]
        write_plan(plan_path, plan)

        calls: list[str] = []

        def fake(prompt: str) -> str:
            calls.append(prompt)
            return _GOOD_BODY

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=2,
            invoker=fake,
            extract_lessons=False,
        )
        assert results[0].written is True
        assert len(calls) == 1

    def test_resume_false_bypasses_cache_but_still_writes_then_discards(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)

        ckpt_path = checkpoint_path(
            tmp_path,
            "orch",
            _DETAIL_CHECKPOINT_NAME.format(step_id=step.id),
        )
        save_checkpoint(
            ckpt_path,
            Checkpoint(
                input_hash=_detail_step_input_hash(plan_path, step),
                payload="# should not be used\n\n## Why\n\nx\n",
                created_at=_fresh_now(),
            ),
        )

        calls: list[str] = []

        def fake(prompt: str) -> str:
            calls.append(prompt)
            return _GOOD_BODY

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=fake,
            resume=False,
            extract_lessons=False,
        )
        assert results[0].written is True
        # Invoker called exactly once — cache load bypassed.
        assert len(calls) == 1
        # Checkpoint still discarded after the successful commit.
        assert not ckpt_path.exists()
        # The on-disk body comes from the invoker, not the seeded payload.
        body = results[0].output_path.read_text(encoding="utf-8")
        assert "should not be used" not in body
        assert "Wire up the renderer" in body

    def test_resume_ignored_when_force_and_file_exists(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        detail_path = _detail_path_for(tmp_path, 1, "wire-up-renderer")
        detail_path.parent.mkdir(parents=True)
        detail_path.write_text("# Stale on-disk body\n", encoding="utf-8")
        update_step_detail_field(
            plan_path, 1, "plan-details/orch/01-wire-up-renderer.md"
        )

        # Seed a STALE checkpoint (hash deliberately mismatched).
        ckpt_path = checkpoint_path(
            tmp_path,
            "orch",
            _DETAIL_CHECKPOINT_NAME.format(step_id=1),
        )
        save_checkpoint(
            ckpt_path,
            Checkpoint(
                input_hash="0" * 64,
                payload="# stale payload\n\n## Why\n\nx\n",
                created_at=_fresh_now(),
            ),
        )

        calls: list[str] = []

        def fake(prompt: str) -> str:
            calls.append(prompt)
            return _GOOD_BODY

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            force=True,
            invoker=fake,
            extract_lessons=False,
        )
        assert results[0].written is True
        # force=True overrides the skip-if-exists, and the stale
        # checkpoint can't satisfy the resume check → claude is called.
        assert len(calls) == 1
        body = detail_path.read_text(encoding="utf-8")
        assert "Stale on-disk body" not in body
        assert "Wire up the renderer" in body
        # Stale checkpoint replaced (during save) and then discarded.
        assert not ckpt_path.exists()

    def test_force_bypasses_matching_hash_checkpoint(
        self, tmp_path: Path
    ) -> None:
        """``--force`` is "burn it all down" — a *valid* (matching-hash)
        checkpoint must NOT be honored. Before the fix, force only
        bypassed the file-exists skip, so a fresh-hash cache would
        silently re-emit the cached body the user explicitly asked
        to regenerate.
        """
        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)

        # Seed a checkpoint whose input_hash matches the *current*
        # step shape — under default `force=False` this would be a
        # cache hit and skip the invoker entirely.
        ckpt_path = checkpoint_path(
            tmp_path, "orch", _DETAIL_CHECKPOINT_NAME.format(step_id=1),
        )
        cached_body = "# Cached body\n\n## Why\n\nx\n\n## Files\n\nx\n\n## Implementation\n\nx\n\n## Tests\n\nx\n\n## Acceptance criteria\n\nx\n"
        save_checkpoint(
            ckpt_path,
            Checkpoint(
                input_hash=_detail_step_input_hash(plan_path, step),
                payload=cached_body,
                created_at=_fresh_now(),
            ),
        )

        calls: list[str] = []

        def fake(prompt: str) -> str:
            calls.append(prompt)
            return _GOOD_BODY

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            force=True,
            invoker=fake,
            extract_lessons=False,
        )
        assert results[0].written is True
        # Force MUST have invoked claude despite the matching-hash hit.
        assert len(calls) == 1
        # Detail file holds the FRESH body, not the cached one.
        body = _detail_path_for(tmp_path, 1, "wire-up-renderer").read_text(
            encoding="utf-8"
        )
        assert "Cached body" not in body
        assert "Wire up the renderer" in body

    def test_dry_run_does_not_consume_seeded_checkpoint(
        self, tmp_path: Path
    ) -> None:
        """``--dry-run`` short-circuits before the resume check — a
        valid checkpoint must still exist on disk after the run, and
        the run must report a prompt (not the cached body)."""
        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)

        ckpt_path = checkpoint_path(
            tmp_path, "orch", _DETAIL_CHECKPOINT_NAME.format(step_id=1),
        )
        save_checkpoint(
            ckpt_path,
            Checkpoint(
                input_hash=_detail_step_input_hash(plan_path, step),
                payload=_GOOD_BODY,
                created_at=_fresh_now(),
            ),
        )

        def fake(prompt: str) -> str:
            raise AssertionError("invoker must not be called under dry_run")

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            dry_run=True,
            invoker=fake,
            extract_lessons=False,
        )
        # Dry-run carries the rendered prompt, not the cached body.
        assert results[0].written is False
        assert results[0].prompt is not None
        assert results[0].prompt != _GOOD_BODY
        # Checkpoint untouched — dry-run is read-only.
        assert ckpt_path.is_file()

    def test_save_checkpoint_oserror_is_swallowed_with_warning(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A permissions/disk error on checkpoint save must not abort
        the run — the file write + plan-update should still happen,
        and a warning must reach stderr."""
        plan_path = _write_orchestrator_plan(tmp_path)

        from plan_tool import detail as detail_module

        def boom(*args: object, **kwargs: object) -> None:
            raise OSError("disk full")

        monkeypatch.setattr(detail_module, "save_checkpoint", boom)

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda prompt: _GOOD_BODY,
            extract_lessons=False,
        )
        # Despite the failed save, the step completes successfully.
        assert results[0].written is True
        # Detail file is on disk, plan frontmatter updated.
        canonical = _detail_path_for(tmp_path, 1, "wire-up-renderer")
        assert canonical.is_file()
        # Warning surfaced on stderr.
        err = capsys.readouterr().err
        assert "failed to save checkpoint" in err
        assert "step 1" in err

    def test_resume_cache_miss_on_depends_on_change_re_invokes(
        self, tmp_path: Path
    ) -> None:
        """Mutating ``step.depends_on`` invalidates the cached body."""
        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(2)

        ckpt_path = checkpoint_path(
            tmp_path,
            "orch",
            _DETAIL_CHECKPOINT_NAME.format(step_id=step.id),
        )
        save_checkpoint(
            ckpt_path,
            Checkpoint(
                input_hash=_detail_step_input_hash(plan_path, step),
                payload=_GOOD_BODY,
                created_at=_fresh_now(),
            ),
        )

        # Drop the dependency on step 1 — the keying decision must catch
        # this so the cached body doesn't get reused under a different
        # prompt context.
        step.depends_on = []
        write_plan(plan_path, plan)

        calls: list[str] = []

        def fake(prompt: str) -> str:
            calls.append(prompt)
            return _GOOD_BODY

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=2,
            invoker=fake,
            extract_lessons=False,
        )
        assert results[0].written is True
        assert len(calls) == 1

    def test_plan_title_change_still_cache_hits(self, tmp_path: Path) -> None:
        """Plan-level field changes (title) must NOT invalidate the per-step cache.

        The detail-step input hash is keyed on slug + step shape, not on
        plan-level metadata. A future refactor that adds plan-level fields
        to the hash would invalidate every cached body on a title edit —
        this negative test pins the keying decision.
        """
        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)

        ckpt_path = checkpoint_path(
            tmp_path,
            "orch",
            _DETAIL_CHECKPOINT_NAME.format(step_id=step.id),
        )
        save_checkpoint(
            ckpt_path,
            Checkpoint(
                input_hash=_detail_step_input_hash(plan_path, step),
                payload=_GOOD_BODY,
                created_at=_fresh_now(),
            ),
        )

        # Change the PLAN's title (not the step's). The per-step
        # checkpoint should still hash-match.
        plan.title = "A Completely Different Plan Title"
        write_plan(plan_path, plan)

        def boom_invoker(prompt: str) -> str:
            raise AssertionError(
                "invoker must not be called: plan-level title change "
                "should not invalidate the per-step checkpoint"
            )

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=boom_invoker,
            extract_lessons=False,
        )
        assert results[0].written is True
        detail_path = _detail_path_for(tmp_path, 1, "wire-up-renderer")
        assert _GOOD_BODY_STAMPED in detail_path.read_text(encoding="utf-8")

    def test_partial_resume_invokes_only_fresh_step(
        self, tmp_path: Path
    ) -> None:
        """Cached step 1 reuses the payload; uncached step 2 invokes claude."""
        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step1 = plan.step_by_id(1)

        # Seed only step 1's checkpoint.
        cached_marker_body = _GOOD_BODY.replace(
            "Wire up the renderer",
            "Wire up the renderer FROM-CACHE-MARKER",
        )
        ckpt_path = checkpoint_path(
            tmp_path,
            "orch",
            _DETAIL_CHECKPOINT_NAME.format(step_id=step1.id),
        )
        save_checkpoint(
            ckpt_path,
            Checkpoint(
                input_hash=_detail_step_input_hash(plan_path, step1),
                payload=cached_marker_body,
                created_at=_fresh_now(),
            ),
        )

        calls: list[str] = []

        def fake(prompt: str) -> str:
            calls.append(prompt)
            return _GOOD_BODY

        # All steps mode (no step_id) — should hit cache for step 1 and
        # invoke claude exactly once for step 2.
        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            invoker=fake,
            extract_lessons=False,
        )
        assert len(results) == 2
        assert all(r.written for r in results)
        assert len(calls) == 1

        # Step 1's body came from the cache (carries the marker).
        body1 = _detail_path_for(tmp_path, 1, "wire-up-renderer").read_text(
            encoding="utf-8"
        )
        assert "FROM-CACHE-MARKER" in body1
        # Step 2's body came from the invoker (plain _GOOD_BODY).
        body2 = _detail_path_for(tmp_path, 2, "build").read_text(
            encoding="utf-8"
        )
        assert "FROM-CACHE-MARKER" not in body2

    def test_schema_version_mismatch_invokes_fresh(
        self, tmp_path: Path
    ) -> None:
        """A checkpoint with an unrecognized schema_version is treated as absent."""
        import json as _json

        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)

        # Hand-write a JSON checkpoint with a future schema_version that
        # the loader must reject. Using save_checkpoint would clamp to
        # the current version, defeating the test.
        ckpt_path = checkpoint_path(
            tmp_path,
            "orch",
            _DETAIL_CHECKPOINT_NAME.format(step_id=step.id),
        )
        ckpt_path.parent.mkdir(parents=True, exist_ok=True)
        ckpt_path.write_text(
            _json.dumps(
                {
                    "input_hash": _detail_step_input_hash(plan_path, step),
                    "payload": "# should not be used\n\n## Why\n\nx\n",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "schema_version": CHECKPOINT_SCHEMA_VERSION + 998,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        calls: list[str] = []

        def fake(prompt: str) -> str:
            calls.append(prompt)
            return _GOOD_BODY

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=fake,
            extract_lessons=False,
        )
        assert results[0].written is True
        # Cache rejected on schema mismatch → claude invoked.
        assert len(calls) == 1
        body = results[0].output_path.read_text(encoding="utf-8")
        assert "should not be used" not in body
        assert "Wire up the renderer" in body

    def test_resumed_step_counter_excludes_resumed_from_denominator(
        self, tmp_path: Path
    ) -> None:
        """The ``[N/M]`` denominator counts invocations, not resumed steps.

        Step 2 will be the only invoked step; its progress entry must read
        ``(1, 1, ...)`` — not ``(1, 2, ...)``. A regression that lets the
        resumed step bleed into ``invoke_total`` would show ``(?, 2, ...)``.
        """
        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step1 = plan.step_by_id(1)

        ckpt_path = checkpoint_path(
            tmp_path,
            "orch",
            _DETAIL_CHECKPOINT_NAME.format(step_id=step1.id),
        )
        save_checkpoint(
            ckpt_path,
            Checkpoint(
                input_hash=_detail_step_input_hash(plan_path, step1),
                payload=_GOOD_BODY,
                created_at=_fresh_now(),
            ),
        )

        reporter = _RecordingReporter()

        def fake(prompt: str) -> str:
            return _GOOD_BODY

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            invoker=fake,
            reporter=reporter,
            extract_lessons=False,
        )
        assert len(results) == 2

        # Filter out the resumed-step entry; the lone fresh invocation
        # should be reported as [1/1]. The resumed entry's label carries
        # the "(resumed from checkpoint)" marker so it's identifiable
        # even though the orchestrator does emit it for the heartbeat.
        non_resumed = [
            s for s in reporter.starts if "(resumed" not in s[2]
        ]
        assert non_resumed == [(1, 1, "step 2: Build it")]


class TestPrepareRunGradeDetail:
    """Run-grade setup prepares the lifecycle handoff before authoring."""

    def test_prepare_run_grade_detail_preserves_preparation_order(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import detail as detail_module

        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        events: list[str] = []
        real_step_by_id = detail_module.Plan.step_by_id

        def load_concepts_in_order(_path: Path, _fingerprint: str):
            events.append("concepts")
            return None

        def derive_buckets_in_order(_plan: Plan, _text: str) -> dict[str, str]:
            events.append("buckets")
            return {}

        def select_target_in_order(self: Plan, step_id: int) -> Step:
            events.append("targets")
            return real_step_by_id(self, step_id)

        def adopt_in_order(_path: Path, _plan: Plan, _step: Step):
            events.append("adopt")
            return None

        def scan_checkpoint_in_order(_path: Path, *, expected_input_hash: str):
            events.append("checkpoints")
            return None

        monkeypatch.setattr(detail_module, "load_concepts", load_concepts_in_order)
        monkeypatch.setattr(
            detail_module, "derive_candidate_buckets", derive_buckets_in_order
        )
        monkeypatch.setattr(
            detail_module.Plan, "step_by_id", select_target_in_order
        )
        monkeypatch.setattr(
            detail_module,
            "find_unreferenced_detail_for_step",
            adopt_in_order,
        )
        monkeypatch.setattr(detail_module, "load_if_valid", scan_checkpoint_in_order)

        prepared = detail_module._prepare_run_grade_detail(
            plan_path,
            plan,
            repo_root=tmp_path,
            step_id=1,
            force=False,
            dry_run=False,
            reporter=None,
            resume=True,
            prompt_fn=None,
            run_logger=None,
        )

        assert events == ["concepts", "buckets", "targets", "adopt", "checkpoints"]
        assert [step.id for step in prepared.target_steps] == [1]
        assert prepared.plan is plan
        assert isinstance(prepared.reporter, detail_module.StderrReporter)
        assert callable(prepared.prompt_fn)
        assert prepared.invoke_idx == 0

    def test_prepare_run_grade_detail_preserves_regeneration_and_checkpoint_accounting(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import detail as detail_module

        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        regenerated = plan.step_by_id(1)
        cached = plan.step_by_id(2)
        regenerated_path = derive_detail_path(plan_path, plan, regenerated)
        regenerated_path.parent.mkdir(parents=True)
        regenerated_path.write_text(_GOOD_BODY, encoding="utf-8")
        update_step_detail_field(
            plan_path, regenerated.id, _repo_relative(regenerated_path, tmp_path)
        )
        plan = parse_plan(plan_path)
        cached = plan.step_by_id(2)
        checkpoint = Checkpoint(
            input_hash=_detail_step_input_hash(plan_path, cached),
            payload=_GOOD_BODY,
            created_at=_fresh_now(),
        )
        scanned_ids: list[int] = []

        def regeneration_targets(_tree: object, _plan: Plan) -> set[int]:
            return {1}

        def cached_second_step(
            _path: Path, *, expected_input_hash: str
        ) -> Optional[Checkpoint]:
            scanned_ids.append(2)
            return checkpoint

        monkeypatch.setattr(
            detail_module, "_included_deferral_step_ids", regeneration_targets
        )
        monkeypatch.setattr(detail_module, "load_if_valid", cached_second_step)

        prepared = detail_module._prepare_run_grade_detail(
            plan_path,
            plan,
            repo_root=tmp_path,
            step_id=2,
            force=False,
            dry_run=False,
            reporter=NullReporter(),
            resume=True,
            prompt_fn=lambda _prompt: "",
            run_logger=None,
        )
        dry_run_prepared = detail_module._prepare_run_grade_detail(
            plan_path,
            plan,
            repo_root=tmp_path,
            step_id=2,
            force=False,
            dry_run=True,
            reporter=NullReporter(),
            resume=True,
            prompt_fn=lambda _prompt: "",
            run_logger=None,
        )

        assert [step.id for step in prepared.target_steps] == [1, 2]
        assert prepared.cached_by_id[1] is None
        assert prepared.cached_by_id[2] is checkpoint
        assert scanned_ids == [2, 2]
        assert prepared.invoke_total == 1
        assert dry_run_prepared.invoke_total == 0


@pytest.mark.integration
class TestGenerateDetailDryRun:
    def test_dry_run_returns_prompts_without_writes(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        before_bytes = plan_path.read_bytes()

        def fake(prompt: str) -> str:
            raise AssertionError("invoker should not be called in dry-run")

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            dry_run=True,
            invoker=fake,
        )
        assert len(results) == 1
        r = results[0]
        assert r.written is False
        assert r.skipped_reason is None
        assert r.prompt is not None
        assert "Implementation detail for step 1" in r.prompt
        # No file written, plan untouched.
        assert not r.output_path.exists()
        assert plan_path.read_bytes() == before_bytes


def _save_detail_concept(
    plan_path: Path,
    *,
    decision: str = "defer",
    owner_step_id: Optional[int] = None,
    deferred_step_ids: tuple[int, ...] = (),
) -> ConceptNode:
    node = ConceptNode(
        id=concept_id("Tracked concept", []),
        title="Tracked concept",
        decision=decision,
        review_state="approved",
    )
    if deferred_step_ids:
        node.source_metadata["detail_deferral_step_ids"] = json.dumps(
            list(deferred_step_ids), separators=(",", ":")
        )
    plan = parse_plan(plan_path)
    if owner_step_id is not None:
        plan.step_by_id(owner_step_id).concept_ids = [node.id]
        write_plan(plan_path, plan)
    save_concepts(
        plan_path,
        ConceptTree(
            plan_slug=_plan_slug(plan_path),
            plan_fingerprint=compute_plan_fingerprint(plan_path),
            concepts=[node],
        ),
    )
    return node


def _sign_off_and_read_deferred(
    monkeypatch: pytest.MonkeyPatch,
    plan_path: Path,
    concept_id_value: str,
    decision: str,
) -> None:
    """Run ``scope-review`` to sign off one flat pending decision."""
    import argparse

    from plan_tool.cli import scope_review_cmd

    monkeypatch.setattr(
        scope_review_cmd, "_load_context", lambda args: object()
    )
    monkeypatch.setattr(
        scope_review_cmd,
        "resolve_plan_for_context",
        lambda context, name: plan_path,
    )
    args = argparse.Namespace(
        name=plan_path.stem,
        concept=[concept_id_value],
        decision=[(concept_id_value, decision)],
    )
    rc = scope_review_cmd.cmd_scope_review(args)
    assert rc == 0, rc


def _plan_deferred_section(plan_path: Path) -> str:
    from plan_tool.parser import split_body_sections, split_plan_document

    body = split_plan_document(plan_path.read_text(encoding="utf-8")).body
    return split_body_sections(body).get("deferred", "")


class TestStructuredDetailDeferrals:
    @pytest.mark.parametrize(
        "first_reply",
        [
            _FIVE_SECTIONS,
            _FIVE_SECTIONS
            + "\n<!-- plan-tool-detail-deferrals\n{invalid json}\n-->",
        ],
    )
    def test_envelope_only_retry_keeps_body_and_checkpoint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, first_reply: str
    ) -> None:
        from plan_tool import detail as detail_module

        plan_path = _write_detail_plan_with_sections(tmp_path)
        prompts: list[str] = []
        payloads: list[str] = []
        budgets: list[dict] = []
        original_save = detail_module.save_checkpoint

        def save(path: Path, checkpoint: Checkpoint) -> None:
            payloads.append(checkpoint.payload)
            original_save(path, checkpoint)

        def invoke(prompt: str) -> str:
            prompts.append(prompt)
            return first_reply if len(prompts) == 1 else (
                '<!-- plan-tool-detail-deferrals\n{"deferrals":[]}\n-->'
            )

        monkeypatch.setattr(detail_module, "save_checkpoint", save)
        monkeypatch.setattr(
            detail_module, "record_prompt_budget",
            lambda _root, **kwargs: budgets.append(kwargs),
        )
        results = generate_detail(
            plan_path, repo_root=tmp_path, step_id=1,
            invoker=invoke, reporter=NullReporter(), extract_lessons=False,
        )

        assert results[0].written
        assert len(prompts) == 2
        assert "## Repair" in prompts[1]
        assert first_reply in prompts[1]
        assert "Return ONLY the trailing" in prompts[1]
        assert [record["total_bytes"] for record in budgets] == [
            len(prompt.encode("utf-8")) for prompt in prompts
        ]
        assert len(payloads) == 1
        plan = parse_plan(plan_path)
        parsed = parse_structured_detail_response(
            payloads[0], step=plan.step_by_id(1), plan=plan,
            candidate_buckets=detail_module.derive_candidate_buckets(
                plan, plan_path.read_text(encoding="utf-8")
            ),
        )
        assert parsed is not None
        assert parsed.body == _FIVE_SECTIONS.strip()
        assert "{invalid json}" not in payloads[0]
        assert "plan-tool-detail-deferrals" not in results[0].output_path.read_text()

    @pytest.mark.parametrize(
        "repair_reply",
        [
            "not an envelope",
            'Here it is:\n<!-- plan-tool-detail-deferrals\n{"deferrals":[]}\n-->',
        ],
    )
    def test_invalid_envelope_repair_exhausts_existing_retry(
        self, tmp_path: Path, repair_reply: str
    ) -> None:
        plan_path = _write_detail_plan_with_sections(tmp_path)
        prompts: list[str] = []

        def invoke(prompt: str) -> str:
            prompts.append(prompt)
            return _FIVE_SECTIONS if len(prompts) == 1 else repair_reply

        results = generate_detail(
            plan_path, repo_root=tmp_path, step_id=1,
            invoker=invoke, reporter=NullReporter(), extract_lessons=False,
        )

        assert len(prompts) == 2
        assert "## Repair" in prompts[1]
        assert not results[0].written
        assert "after 2 attempt(s)" in (results[0].skipped_reason or "")
        assert not results[0].output_path.exists()

    def test_summary_reply_uses_full_regeneration(self, tmp_path: Path) -> None:
        plan_path = _write_detail_plan_with_sections(tmp_path)
        prompts: list[str] = []

        def invoke(prompt: str) -> str:
            prompts.append(prompt)
            return "I wrote the detail file." if len(prompts) == 1 else _structured_detail()

        results = generate_detail(
            plan_path, repo_root=tmp_path, step_id=1,
            invoker=invoke, reporter=NullReporter(), extract_lessons=False,
        )

        assert results[0].written
        assert len(prompts) == 2
        assert "could not be parsed" in prompts[1]
        assert "## Repair" not in prompts[1]

    def test_valid_json_with_invalid_deferral_uses_full_regeneration(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_detail_plan_with_sections(tmp_path)
        prompts: list[str] = []

        def invoke(prompt: str) -> str:
            prompts.append(prompt)
            return (
                _structured_detail(("f" * 64, 1))
                if len(prompts) == 1 else _structured_detail()
            )

        results = generate_detail(
            plan_path, repo_root=tmp_path, step_id=1,
            invoker=invoke, reporter=NullReporter(), extract_lessons=False,
        )

        assert results[0].written
        assert len(prompts) == 2
        assert "could not be parsed" in prompts[1]
        assert "## Repair" not in prompts[1]

    def test_repair_reply_can_state_deferrals_named_in_the_body(
        self, tmp_path: Path
    ) -> None:
        # The repair prompt carries the rejected reply, so a body whose
        # `## Deferred` section names a bucket id is repairable: the model
        # restates that id in the envelope. Repair is not limited to an
        # empty envelope.
        plan_path = _write_detail_plan_with_sections(tmp_path)
        bucket_id = concept_id("risks", [])
        full = _structured_detail((bucket_id, 1))
        body, marker, envelope = full.partition("\n<!-- plan-tool-detail-deferrals")
        prompts: list[str] = []

        def invoke(prompt: str) -> str:
            prompts.append(prompt)
            return body if len(prompts) == 1 else marker.lstrip() + envelope

        results = generate_detail(
            plan_path, repo_root=tmp_path, step_id=1,
            invoker=invoke, reporter=NullReporter(), extract_lessons=False,
        )

        assert results[0].written
        assert len(prompts) == 2
        assert "## Repair" in prompts[1]
        assert bucket_id in prompts[1]
        saved = load_concepts(plan_path, compute_plan_fingerprint(plan_path))
        assert saved is not None
        assert [node.id for node in saved.concepts] == [bucket_id]

    def test_marker_quoted_in_body_uses_full_regeneration_not_truncation(
        self, tmp_path: Path
    ) -> None:
        # Truncating at an unfenced marker-like line inside the body would
        # drop `## Acceptance criteria`, which the parser then auto-stubs and
        # accepts, silently losing the section. Only a marker that opens one
        # comment running to end-of-text is an envelope worth repairing.
        plan_path = _write_detail_plan_with_sections(tmp_path)
        quoted = _FIVE_SECTIONS.replace(
            "## Acceptance criteria",
            "<!-- plan-tool-detail-deferrals\n"
            "{\"deferrals\":[]}\n"
            "-->\n\n## Acceptance criteria",
        )
        prompts: list[str] = []

        def invoke(prompt: str) -> str:
            prompts.append(prompt)
            return quoted if len(prompts) == 1 else _structured_detail()

        results = generate_detail(
            plan_path, repo_root=tmp_path, step_id=1,
            invoker=invoke, reporter=NullReporter(), extract_lessons=False,
        )

        assert results[0].written
        assert len(prompts) == 2
        assert "could not be parsed" in prompts[1]
        assert "## Repair" not in prompts[1]
        assert "returns 42" in results[0].output_path.read_text(encoding="utf-8")

    def test_cut_off_envelope_uses_full_regeneration(self, tmp_path: Path) -> None:
        plan_path = _write_detail_plan_with_sections(tmp_path)
        prompts: list[str] = []

        def invoke(prompt: str) -> str:
            prompts.append(prompt)
            return (
                _FIVE_SECTIONS
                + '\n<!-- plan-tool-detail-deferrals\n{"deferrals":[{"concept_id":"ab'
                if len(prompts) == 1 else _structured_detail()
            )

        results = generate_detail(
            plan_path, repo_root=tmp_path, step_id=1,
            invoker=invoke, reporter=NullReporter(), extract_lessons=False,
        )

        assert results[0].written
        assert len(prompts) == 2
        assert "could not be parsed" in prompts[1]
        assert "## Repair" not in prompts[1]

    def test_repair_keeps_the_one_missing_section_stub_an_enveloped_reply_gets(
        self, tmp_path: Path
    ) -> None:
        # Auto-stubbing exactly one missing section is the documented rule
        # (DETAIL_FORMAT.md rule 4) for a reply with or without a repaired
        # envelope; repair must not be stricter than the ordinary parse.
        plan_path = _write_detail_plan_with_sections(tmp_path)
        body = _FIVE_SECTIONS.split("\n## Acceptance criteria")[0]
        prompts: list[str] = []

        def invoke(prompt: str) -> str:
            prompts.append(prompt)
            return body if len(prompts) == 1 else (
                '<!-- plan-tool-detail-deferrals\n{"deferrals":[]}\n-->'
            )

        results = generate_detail(
            plan_path, repo_root=tmp_path, step_id=1,
            invoker=invoke, reporter=NullReporter(), extract_lessons=False,
        )

        assert results[0].written
        assert len(prompts) == 2
        assert "## Repair" in prompts[1]
        assert "stub: model omitted" in results[0].output_path.read_text(
            encoding="utf-8"
        )

    def test_empty_envelope_is_not_written_without_concept_record(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_detail_plan(tmp_path)
        results = generate_detail(
            plan_path, repo_root=tmp_path, step_id=1,
            invoker=lambda prompt: _structured_detail(),
            reporter=NullReporter(), extract_lessons=False,
        )

        assert results[0].written
        assert "plan-tool-detail-deferrals" not in (
            results[0].output_path.read_text(encoding="utf-8")
        )

    def test_valid_deferral_persists_after_detail_write(self, tmp_path: Path) -> None:
        plan_path = _write_detail_plan_with_sections(tmp_path)
        bucket_id = concept_id("risks", [])

        results = generate_detail(
            plan_path, repo_root=tmp_path, step_id=1,
            invoker=lambda prompt: _structured_detail((bucket_id, 1)),
            reporter=NullReporter(), extract_lessons=False,
        )

        assert results[0].written
        assert "plan-tool-detail-deferrals" not in results[0].output_path.read_text()
        saved = load_concepts(plan_path, compute_plan_fingerprint(plan_path))
        assert saved is not None
        assert saved.record_kind == RECORD_KIND_DECISION
        assert [node.id for node in saved.concepts] == [bucket_id]
        assert saved.concepts[0].decision == "defer"

    def test_detail_records_flat_defer_on_record_absent_plan(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_detail_plan_with_sections(tmp_path)
        assert not (plan_path.parent / "plan-details").exists()
        bucket_id = concept_id("risks", [])

        results = generate_detail(
            plan_path, repo_root=tmp_path, step_id=1,
            invoker=lambda prompt: _structured_detail((bucket_id, 1)),
            reporter=NullReporter(), extract_lessons=False,
        )

        assert results[0].written
        saved = load_concepts(plan_path, compute_plan_fingerprint(plan_path))
        assert saved is not None
        assert saved.record_kind == RECORD_KIND_DECISION
        assert len(saved.concepts) == 1
        node = saved.concepts[0]
        assert node.decision == "defer"
        assert node.review_state == "unreviewed"
        assert node.bucket == "risks"

    def test_yes_does_not_sign_off_new_deferral(self, tmp_path: Path) -> None:
        plan_path = _write_detail_plan_with_sections(tmp_path)
        bucket_id = concept_id("risks", [])

        results = generate_detail(
            plan_path, repo_root=tmp_path, step_id=1, yes=True,
            prompt_fn=lambda prompt: (_ for _ in ()).throw(AssertionError(prompt)),
            invoker=lambda prompt: _structured_detail((bucket_id, 1)),
            reporter=NullReporter(), extract_lessons=False,
        )

        assert results[0].written
        saved = load_concepts(plan_path, compute_plan_fingerprint(plan_path))
        assert saved is not None
        assert saved.concepts[0].review_state == "unreviewed"

    def test_deferral_for_unknown_bucket_does_not_publish_detail(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_detail_plan_with_sections(tmp_path)

        results = generate_detail(
            plan_path, repo_root=tmp_path, step_id=1,
            invoker=lambda prompt: _structured_detail(("f" * 64, 1)),
            reporter=NullReporter(), extract_lessons=False,
        )

        assert not results[0].written
        assert not results[0].output_path.exists()
        assert not (plan_path.parent / "plan-details").exists()

    def test_proposable_buckets_appear_in_prompt(self, tmp_path: Path) -> None:
        plan_path = _write_detail_plan_with_sections(tmp_path)

        results = generate_detail(
            plan_path, repo_root=tmp_path, step_id=1, dry_run=True,
            invoker=lambda prompt: (_ for _ in ()).throw(AssertionError(prompt)),
            reporter=NullReporter(), extract_lessons=False,
        )

        prompt = results[0].prompt
        assert prompt is not None
        for section in ("overview", "risks", "follow-up"):
            assert f"`{concept_id(section, [])}`" in prompt
            assert section in prompt

    def test_deferred_section_must_mention_the_bucket_id(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_detail_plan_with_sections(tmp_path)
        bucket_id = concept_id("risks", [])
        # Envelope names the bucket but the ``## Deferred`` prose omits its id.
        body_without_id = (
            f"{_FIVE_SECTIONS.rstrip()}\n\n## Deferred\n\n- something else\n"
        )

        results = generate_detail(
            plan_path, repo_root=tmp_path, step_id=1,
            invoker=lambda prompt: _structured_detail(
                (bucket_id, 1), body=body_without_id
            ),
            reporter=NullReporter(), extract_lessons=False,
        )

        assert not results[0].written
        assert not results[0].output_path.exists()

    def test_deferral_rationale_persisted_and_rendered(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = _write_detail_plan_with_sections(tmp_path)
        bucket_id = concept_id("risks", [])

        results = generate_detail(
            plan_path, repo_root=tmp_path, step_id=1,
            invoker=lambda prompt: _structured_detail(
                (bucket_id, 1, "concurrency edge cases are out of scope")
            ),
            reporter=NullReporter(), extract_lessons=False,
        )

        assert results[0].written
        saved = load_concepts(plan_path, compute_plan_fingerprint(plan_path))
        assert saved is not None
        assert saved.concepts[0].rationale == "concurrency edge cases are out of scope"

        # After scope-review signs it off, the plan's ``## Deferred`` renders
        # ``- {title} — {rationale}``, not a bare section bullet.
        _sign_off_and_read_deferred(monkeypatch, plan_path, bucket_id, "defer")
        deferred = _plan_deferred_section(plan_path)
        assert "risks — concurrency edge cases are out of scope" in deferred

    def test_deferral_without_rationale_records_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = _write_detail_plan_with_sections(tmp_path)
        bucket_id = concept_id("risks", [])

        results = generate_detail(
            plan_path, repo_root=tmp_path, step_id=1,
            invoker=lambda prompt: _structured_detail((bucket_id, 1)),
            reporter=NullReporter(), extract_lessons=False,
        )

        assert results[0].written
        saved = load_concepts(plan_path, compute_plan_fingerprint(plan_path))
        assert saved is not None
        assert saved.concepts[0].rationale == ""
        _sign_off_and_read_deferred(monkeypatch, plan_path, bucket_id, "defer")
        deferred = _plan_deferred_section(plan_path)
        assert "- risks" in deferred
        assert "risks —" not in deferred

    def test_existing_decision_record_gains_the_new_bucket(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_detail_plan_with_sections(tmp_path)
        prior_id = concept_id("overview", [])
        save_concepts(
            plan_path,
            ConceptTree(
                plan_slug=_plan_slug(plan_path),
                plan_fingerprint=compute_plan_fingerprint(plan_path),
                concepts=[
                    ConceptNode(
                        id=prior_id, title="overview", bucket="overview",
                        decision="defer", review_state="unreviewed",
                    )
                ],
                record_kind=RECORD_KIND_DECISION,
            ),
        )
        new_id = concept_id("risks", [])

        results = generate_detail(
            plan_path, repo_root=tmp_path, step_id=1,
            invoker=lambda prompt: _structured_detail((new_id, 1)),
            reporter=NullReporter(), extract_lessons=False,
        )

        assert results[0].written
        saved = load_concepts(plan_path, compute_plan_fingerprint(plan_path))
        assert saved is not None
        by_id = {node.id: node for node in saved.concepts}
        assert set(by_id) == {prior_id, new_id}
        assert by_id[prior_id].review_state == "unreviewed"
        assert by_id[new_id].decision == "defer"

    def test_redeferral_of_pending_bucket_is_noop(self, tmp_path: Path) -> None:
        plan_path = _write_detail_plan_with_sections(tmp_path)
        bucket_id = concept_id("risks", [])
        save_concepts(
            plan_path,
            ConceptTree(
                plan_slug=_plan_slug(plan_path),
                plan_fingerprint=compute_plan_fingerprint(plan_path),
                concepts=[
                    ConceptNode(
                        id=bucket_id, title="risks", bucket="risks",
                        rationale="already pending", decision="defer",
                        review_state="unreviewed",
                    )
                ],
                record_kind=RECORD_KIND_DECISION,
            ),
        )

        results = generate_detail(
            plan_path, repo_root=tmp_path, step_id=1,
            invoker=lambda prompt: _structured_detail(
                (bucket_id, 1, "a different reason")
            ),
            reporter=NullReporter(), extract_lessons=False,
        )

        assert results[0].written
        saved = load_concepts(plan_path, compute_plan_fingerprint(plan_path))
        assert saved is not None
        assert [node.id for node in saved.concepts] == [bucket_id]
        # The pending proposal already stands; it is neither duplicated nor
        # overwritten with the new rationale.
        assert saved.concepts[0].rationale == "already pending"

    def test_redeferral_of_approved_bucket_preserves_decision(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_detail_plan_with_sections(tmp_path)
        bucket_id = concept_id("risks", [])
        save_concepts(
            plan_path,
            ConceptTree(
                plan_slug=_plan_slug(plan_path),
                plan_fingerprint=compute_plan_fingerprint(plan_path),
                concepts=[
                    ConceptNode(
                        id=bucket_id, title="risks", bucket="risks",
                        decision="wont_do", review_state="approved",
                    )
                ],
                record_kind=RECORD_KIND_DECISION,
            ),
        )

        results = generate_detail(
            plan_path, repo_root=tmp_path, step_id=1,
            invoker=lambda prompt: _structured_detail((bucket_id, 1)),
            reporter=NullReporter(), extract_lessons=False,
        )

        assert results[0].written
        saved = load_concepts(plan_path, compute_plan_fingerprint(plan_path))
        assert saved is not None
        assert [node.id for node in saved.concepts] == [bucket_id]
        # The operator's signed-off decision is authoritative — never re-opened.
        assert saved.concepts[0].review_state == "approved"
        assert saved.concepts[0].decision == "wont_do"

    def test_legacy_record_deferral_warns_not_dropped(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        plan_path = _write_detail_plan_with_sections(tmp_path)
        # A valid, non-stale legacy full-tree record over the current plan.
        tracked_id = concept_id("Tracked concept", [])
        full_tree = ConceptTree(
            plan_slug=_plan_slug(plan_path),
            plan_fingerprint=compute_plan_fingerprint(plan_path),
            concepts=[
                ConceptNode(
                    id=tracked_id,
                    title="Tracked concept",
                    decision="include",
                    review_state="approved",
                    source_metadata={"detail_deferral_step_ids": "[1]"},
                )
            ],
            record_kind=RECORD_KIND_FULL_TREE,
        )
        save_concepts(plan_path, full_tree)
        bucket_id = concept_id("risks", [])

        results = generate_detail(
            plan_path, repo_root=tmp_path, step_id=1,
            invoker=lambda prompt: _structured_detail((bucket_id, 1)),
            reporter=NullReporter(), extract_lessons=False,
        )

        assert results[0].written
        saved = load_concepts(plan_path, compute_plan_fingerprint(plan_path))
        assert saved is not None
        # The full-tree record is not turned into a decision record.
        assert saved.record_kind == RECORD_KIND_FULL_TREE
        assert [node.id for node in saved.concepts] == [tracked_id]
        assert "detail_deferral_step_ids" not in saved.concepts[0].source_metadata
        captured = capsys.readouterr()
        message = captured.out + captured.err
        assert bucket_id in message
        assert "131" in message

    def test_include_transition_regenerates_and_clears_link(self, tmp_path: Path) -> None:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        output_path = derive_detail_path(plan_path, plan, step)
        output_path.parent.mkdir(parents=True)
        output_path.write_text("old deferred body\n", encoding="utf-8")
        step.detail = _repo_relative(output_path, tmp_path)
        write_plan(plan_path, plan)
        _save_detail_concept(
            plan_path, decision="include", owner_step_id=1,
            deferred_step_ids=(1,),
        )
        calls: list[str] = []

        results = generate_detail(
            plan_path, repo_root=tmp_path, step_id=1,
            invoker=lambda prompt: calls.append(prompt) or _structured_detail(),
            reporter=NullReporter(), extract_lessons=False,
        )

        assert len(calls) == 1
        assert results[0].written
        saved = load_concepts(plan_path, compute_plan_fingerprint(plan_path))
        assert saved is not None
        assert "detail_deferral_step_ids" not in saved.concepts[0].source_metadata

    def test_failed_regeneration_retains_link_and_old_body(self, tmp_path: Path) -> None:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        output_path = derive_detail_path(plan_path, plan, step)
        output_path.parent.mkdir(parents=True)
        output_path.write_text("old deferred body\n", encoding="utf-8")
        step.detail = _repo_relative(output_path, tmp_path)
        write_plan(plan_path, plan)
        _save_detail_concept(
            plan_path, decision="include", owner_step_id=1,
            deferred_step_ids=(1,),
        )

        results = generate_detail(
            plan_path, repo_root=tmp_path, step_id=1,
            invoker=lambda prompt: _FIVE_SECTIONS,
            reporter=NullReporter(), extract_lessons=False,
        )

        assert not results[0].written
        assert output_path.read_text(encoding="utf-8") == "old deferred body\n"
        saved = load_concepts(plan_path, compute_plan_fingerprint(plan_path))
        assert saved is not None
        assert saved.concepts[0].source_metadata["detail_deferral_step_ids"] == "[1]"

    def test_concurrent_deferrals_save_once_in_step_order(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = _write_detail_plan_with_sections(tmp_path)
        overview_id = concept_id("overview", [])
        risks_id = concept_id("risks", [])
        from plan_tool import detail as detail_module
        real_save = detail_module.save_concepts
        saved_buckets: list[list[str]] = []

        def recording_save(path: Path, tree: ConceptTree) -> Path:
            saved_buckets.append([node.bucket for node in tree.concepts])
            return real_save(path, tree)

        monkeypatch.setattr(detail_module, "save_concepts", recording_save)

        def invoke(prompt: str) -> str:
            if "Wire up the renderer" in prompt:
                return _structured_detail((overview_id, 1))
            return _structured_detail((risks_id, 3))

        results = generate_detail(
            plan_path, repo_root=tmp_path, jobs=2, invoker=invoke,
            reporter=NullReporter(), extract_lessons=False,
        )

        assert [result.step_id for result in results] == [1, 3]
        assert all(result.written for result in results)
        # One decision-record write holding both flat nodes in step order.
        assert saved_buckets == [["overview", "risks"]]

    def test_dry_run_reports_include_regeneration_without_writes(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        output_path = derive_detail_path(plan_path, plan, step)
        output_path.parent.mkdir(parents=True)
        output_path.write_text("old deferred body\n", encoding="utf-8")
        step.detail = _repo_relative(output_path, tmp_path)
        write_plan(plan_path, plan)
        _save_detail_concept(
            plan_path, decision="include", owner_step_id=1,
            deferred_step_ids=(1,),
        )
        concept_path = output_path.parent / "concepts.json"
        before = concept_path.read_bytes()

        results = generate_detail(
            plan_path, repo_root=tmp_path, step_id=1, dry_run=True,
            invoker=lambda prompt: (_ for _ in ()).throw(AssertionError(prompt)),
            reporter=NullReporter(), extract_lessons=False,
        )

        assert results[0].prompt is not None
        assert "decision=include" in results[0].prompt
        assert output_path.read_text(encoding="utf-8") == "old deferred body\n"
        assert concept_path.read_bytes() == before

    def test_concept_persistence_failure_marks_written_results_for_recovery(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Keep the detail file while marking an unpublishable deferral incomplete."""
        from plan_tool import detail as detail_module

        plan_path = _write_detail_plan_with_sections(tmp_path)
        bucket_id = concept_id("risks", [])

        def fail_save(_path: Path, _tree: ConceptTree) -> Path:
            raise OSError("simulated concept storage failure")

        monkeypatch.setattr(detail_module, "save_concepts", fail_save)

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _prompt: _structured_detail((bucket_id, 1)),
            reporter=NullReporter(),
            extract_lessons=False,
        )

        assert results[0].output_path.is_file()
        assert results[0].written is False
        assert "concept deferral persistence failed" in (
            results[0].skipped_reason or ""
        )

    def test_yes_does_not_sign_off_unreviewed_concept(self, tmp_path: Path) -> None:
        plan_path = _write_detail_plan(tmp_path)
        node = ConceptNode(
            id=concept_id("Unsigned", []), title="Unsigned", decision="include"
        )
        save_concepts(
            plan_path,
            ConceptTree(
                _plan_slug(plan_path), compute_plan_fingerprint(plan_path), [node]
            ),
        )

        results = generate_detail(
            plan_path, repo_root=tmp_path, step_id=1, yes=True,
            prompt_fn=lambda prompt: (_ for _ in ()).throw(AssertionError(prompt)),
            invoker=lambda prompt: _structured_detail(),
            reporter=NullReporter(), extract_lessons=False,
        )

        assert results[0].written
        saved = load_concepts(plan_path, compute_plan_fingerprint(plan_path))
        assert saved is not None
        assert saved.concepts[0].review_state == "unreviewed"


@pytest.mark.integration
class TestGenerateDetailFailures:
    def test_claude_returns_garbage_records_skip_continues(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        # Step 1 succeeds on first call; step 2 fails twice (first attempt +
        # the parse-failure retry added by ``_MAX_INVOKE_ATTEMPTS``).
        responses = [
            _GOOD_BODY,
            "no thanks, can't help",
            "still no thanks",
        ]

        def fake(prompt: str) -> str:
            return responses.pop(0)

        results = generate_detail(
            plan_path, repo_root=tmp_path, invoker=fake
        )
        assert len(results) == 2
        assert results[0].written is True
        assert results[1].written is False
        assert "claude" in (results[1].skipped_reason or "")
        # Both retry slots were consumed.
        assert responses == []

    def test_retry_recovers_when_second_attempt_parses(
        self, tmp_path: Path
    ) -> None:
        """Single transient parse failure should not burn the step."""
        plan_path = _write_orchestrator_plan(tmp_path)
        # First call returns un-parseable text; second call returns a
        # well-formed body. Expected: step writes successfully.
        responses = ["sure, here you go: no markdown though", _GOOD_BODY]
        prompts_seen: list[str] = []

        def fake(prompt: str) -> str:
            prompts_seen.append(prompt)
            return responses.pop(0)

        results = generate_detail(
            plan_path, repo_root=tmp_path, step_id=1, invoker=fake
        )
        assert len(results) == 1
        assert results[0].written is True
        assert results[0].skipped_reason is None
        # Both prompts fired; the retry prompt is strictly longer and
        # contains the template-conformance reminder.
        assert len(prompts_seen) == 2
        assert prompts_seen[1] != prompts_seen[0]
        assert prompts_seen[1].startswith(prompts_seen[0])
        assert "could not be parsed" in prompts_seen[1]

    def test_retry_exhausted_records_attempt_count_in_reason(
        self, tmp_path: Path
    ) -> None:
        """When every attempt fails the skip reason names the attempt cap."""
        plan_path = _write_orchestrator_plan(tmp_path)
        calls: list[str] = []

        def fake(prompt: str) -> str:
            calls.append(prompt)
            return "no thanks"

        results = generate_detail(
            plan_path, repo_root=tmp_path, step_id=1, invoker=fake
        )
        assert len(results) == 1
        assert results[0].written is False
        reason = results[0].skipped_reason or ""
        assert "claude" in reason
        # Two calls — first attempt plus one retry.
        assert len(calls) == 2
        assert "attempt" in reason

    def test_unknown_explicit_step_id_raises_DetailError(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        with pytest.raises(DetailError):
            generate_detail(
                plan_path,
                repo_root=tmp_path,
                step_id=99,
                invoker=lambda prompt: _GOOD_BODY,
            )

    def test_path_outside_repo_root_falls_back_to_absolute(
        self, tmp_path: Path
    ) -> None:
        """Defensive: when --repo-root pins outside the plan's tree,
        the stored detail path falls back to absolute (with a warning).
        """
        plan_path = _write_orchestrator_plan(tmp_path)
        # Repo root is a sibling directory that doesn't contain plan_path.
        unrelated = tmp_path.parent / f"{tmp_path.name}-unrelated"
        unrelated.mkdir(exist_ok=True)
        try:
            results = generate_detail(
                plan_path,
                repo_root=unrelated,
                step_id=1,
                invoker=lambda prompt: _GOOD_BODY,
            )
        finally:
            # Cleanup the sibling dir so other tests don't trip on it.
            import shutil
            shutil.rmtree(unrelated, ignore_errors=True)

        assert results[0].written is True
        plan = parse_plan(plan_path)
        # Stored path is absolute (no relative-to-unrelated possible).
        assert Path(plan.step_by_id(1).detail).is_absolute()


def test_generated_handoff_is_not_a_detail_sibling_or_orphan(tmp_path: Path) -> None:
    """A companion developer-handoff under the default ``jira-handoffs/<slug>/``
    root sits outside the ``plan-details/<slug>/`` bundle both
    ``_discover_siblings`` and ``_archive_orphan_details`` scan, so it is
    never discovered, adopted, or archived as a detail artifact.
    """
    plan_details = tmp_path / "plan-details" / "orch"
    plan_details.mkdir(parents=True)
    canonical = plan_details / "01-wire-up-renderer.md"
    canonical.write_text("# Canonical\n", encoding="utf-8")

    handoff_dir = tmp_path / "jira-handoffs" / "orch"
    handoff_dir.mkdir(parents=True)
    handoff = handoff_dir / "jira-stories.developer-handoff.md"
    handoff.write_text("# Developer handoff\n", encoding="utf-8")

    siblings = _discover_siblings(canonical)
    assert handoff not in siblings

    archived = _archive_orphan_details(canonical, 1)
    assert archived == []
    assert handoff.is_file()
    assert handoff.read_text(encoding="utf-8") == "# Developer handoff\n"


def test_orphan_sweep_archives_only_stale_same_step_files(tmp_path: Path) -> None:
    canonical = tmp_path / "01-current.md"
    other_step = tmp_path / "02-other.md"
    stale = [tmp_path / "01-old.md", tmp_path / "01-older.md"]
    for path in [canonical, other_step, *stale]:
        path.write_text(path.name, encoding="utf-8")

    moved = _archive_orphan_details(canonical, 1)

    assert set(moved) == {tmp_path / "archive" / path.name for path in stale}
    for path in stale:
        assert not path.exists()
        assert (tmp_path / "archive" / path.name).read_text(encoding="utf-8") == path.name
    for path in [canonical, other_step]:
        assert path.read_text(encoding="utf-8") == path.name


@pytest.mark.integration
class TestGenerateDetailOrphanSweep:
    """``_archive_orphan_details`` moves stale ``NN-*.md`` siblings.

    Triggers when a step's title is edited between runs and the new
    detail filename ends up next to the old one. The canonical (just-
    written) file stays put; everything else with the same ``NN-``
    prefix in the directory lands under ``archive/``.
    """

    def test_orphan_with_different_slug_is_archived(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        # Pre-seed an orphan from a prior run: same step id (01) but
        # different slug. Lives in the conventional plan-details dir.
        plan_details = tmp_path / "plan-details" / "orch"
        plan_details.mkdir(parents=True)
        orphan = plan_details / "01-old-slug-from-prior-run.md"
        orphan.write_text("# Stale\n", encoding="utf-8")

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda prompt: _GOOD_BODY,
            extract_lessons=False,
        )
        assert results[0].written is True

        # Canonical file is on disk under its new slug.
        canonical = _detail_path_for(tmp_path, 1, "wire-up-renderer")
        assert canonical.is_file()
        # Orphan is gone from the active directory.
        assert not orphan.exists()
        # And was moved to ``archive/`` preserving its filename.
        archived = plan_details / "archive" / orphan.name
        assert archived.is_file()
        assert archived.read_text(encoding="utf-8") == "# Stale\n"

    def test_canonical_overwrite_archives_prior_content(
        self, tmp_path: Path
    ) -> None:
        """A regen with the same slug archives the prior file with a
        timestamp-renamed copy before writing the new body at the
        canonical path. The active filename is preserved for downstream
        readers; the archived copy is the renamed one.
        """
        plan_path = _write_orchestrator_plan(tmp_path)
        canonical = _detail_path_for(tmp_path, 1, "wire-up-renderer")
        canonical.parent.mkdir(parents=True)
        canonical.write_text("# Old version\n", encoding="utf-8")
        # Force overwrite so the orchestrator actually writes again.
        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            force=True,
            invoker=lambda prompt: _GOOD_BODY,
            extract_lessons=False,
        )
        assert results[0].written is True
        # Canonical name is preserved and now carries the new body.
        assert canonical.is_file()
        assert "Wire up the renderer" in canonical.read_text(encoding="utf-8")
        # The prior content survives under archive/ with a timestamp-
        # renamed stem (``01-wire-up-renderer.<ts>.md``).
        archive_dir = canonical.parent / "archive"
        assert archive_dir.is_dir()
        archived = [
            p for p in archive_dir.iterdir()
            if p.name.startswith(canonical.stem + ".")
            and p.suffix == ".md"
        ]
        assert len(archived) == 1
        assert archived[0].read_text(encoding="utf-8") == "# Old version\n"

    def test_multiple_orphans_all_archived(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        plan_details = tmp_path / "plan-details" / "orch"
        plan_details.mkdir(parents=True)
        orphans = [
            plan_details / "01-first-old-slug.md",
            plan_details / "01-second-old-slug.md",
        ]
        for o in orphans:
            o.write_text(f"# {o.stem}\n", encoding="utf-8")

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda prompt: _GOOD_BODY,
            extract_lessons=False,
        )
        assert results[0].written is True
        archive_dir = plan_details / "archive"
        for o in orphans:
            assert not o.exists()
            assert (archive_dir / o.name).is_file()

    def test_other_step_files_are_left_alone(
        self, tmp_path: Path
    ) -> None:
        """A different step's file (``02-*.md``) must NOT be swept."""
        plan_path = _write_orchestrator_plan(tmp_path)
        plan_details = tmp_path / "plan-details" / "orch"
        plan_details.mkdir(parents=True)
        other_step = plan_details / "02-someone-elses-detail.md"
        other_step.write_text("# Step 2 detail\n", encoding="utf-8")

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda prompt: _GOOD_BODY,
            extract_lessons=False,
        )
        assert results[0].written is True
        # Step-2 file untouched.
        assert other_step.is_file()
        assert not (plan_details / "archive").exists()


@pytest.mark.integration
class TestGenerateDetailParseFailureLogging:
    """First-attempt parse failures dump the raw response to disk.

    Lets a later debugging pass see *why* the parser rejected it —
    preamble, missing section, fenced wrapper — without having to
    re-run the model.
    """

    def test_first_attempt_failure_logs_raw_response(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        # First call returns garbage (parse fails); second call returns
        # the well-formed body (parse succeeds). The logger fires on
        # the first attempt.
        responses = ["sure: but no markdown here", _GOOD_BODY]

        def fake(prompt: str) -> str:
            return responses.pop(0)

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=fake,
            extract_lessons=False,
        )
        assert results[0].written is True

        # A parse-failure file exists at the conventional path.
        failures_dir = tmp_path / ".plan-tool" / "parse-failures" / "orch"
        assert failures_dir.is_dir()
        dumps = list(failures_dir.glob("01-attempt1-*.txt"))
        assert len(dumps) == 1
        assert dumps[0].read_text(encoding="utf-8") == (
            "sure: but no markdown here"
        )

    def test_clean_first_attempt_writes_no_failure_log(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda prompt: _GOOD_BODY,
            extract_lessons=False,
        )
        assert results[0].written is True
        # No parse-failures dir created when nothing failed.
        assert not (tmp_path / ".plan-tool" / "parse-failures").exists()

    def test_both_attempts_fail_logs_both(self, tmp_path: Path) -> None:
        """Each rejected attempt gets its own dump."""
        plan_path = _write_orchestrator_plan(tmp_path)
        responses = ["first garbage", "second garbage"]

        def fake(prompt: str) -> str:
            return responses.pop(0)

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=fake,
            extract_lessons=False,
        )
        # Step skipped: both attempts failed parse.
        assert results[0].written is False
        failures_dir = tmp_path / ".plan-tool" / "parse-failures" / "orch"
        dumps = sorted(failures_dir.glob("01-attempt*.txt"))
        assert [p.name.split("-")[1] for p in dumps] == [
            "attempt1",
            "attempt2",
        ]
        assert dumps[0].read_text(encoding="utf-8") == "first garbage"
        assert dumps[1].read_text(encoding="utf-8") == "second garbage"


# --- CLI integration -------------------------------------------------------


class TestCmdDetail:
    def _setup(self, tmp_path: Path) -> tuple[Path, Path]:
        plan_path = _write_orchestrator_plan(tmp_path)
        manifest = tmp_path / "m.json"
        # Manifest entry: plan path relative to repo root (tmp_path).
        manifest.write_text(
            '{"plans": ["2-orch.md"]}\n', encoding="utf-8"
        )
        (tmp_path / ".git").mkdir()
        return plan_path, manifest

    def test_cli_writes_files_and_zero_exit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module

        plan_path, manifest = self._setup(tmp_path)
        original = cli_module.generate_detail

        def patched(path, **kwargs):
            kwargs["invoker"] = lambda prompt: _GOOD_BODY
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.authoring.generate_detail", patched)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            [
                "--manifest",
                str(manifest),
                "detail",
                "orch",
                "--step",
                "1",
            ]
        )
        assert rc == 0
        expected = _detail_path_for(tmp_path, 1, "wire-up-renderer")
        assert expected.is_file()

    def test_cli_dry_run_returns_zero_no_writes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module

        plan_path, manifest = self._setup(tmp_path)
        before_bytes = plan_path.read_bytes()
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            [
                "--manifest",
                str(manifest),
                "detail",
                "orch",
                "--step",
                "1",
                "--dry-run",
            ]
        )
        assert rc == 0
        # No file, plan untouched.
        assert not _detail_path_for(tmp_path, 1, "wire-up-renderer").exists()
        assert plan_path.read_bytes() == before_bytes

    def test_detail_unmatched_fence_opens_no_run_log(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module

        plan_path, manifest = self._setup(tmp_path)
        plan_path.write_text(
            plan_path.read_text(encoding="utf-8") + "\n```\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(["--manifest", str(manifest), "detail", "orch"])

        assert rc == 2
        assert not (tmp_path / ".plan-tool" / "runs").exists()

    def test_cli_force_overwrites(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module

        plan_path, manifest = self._setup(tmp_path)
        # Pre-populate.
        detail_path = _detail_path_for(tmp_path, 1, "wire-up-renderer")
        detail_path.parent.mkdir(parents=True)
        detail_path.write_text("# Stale\n", encoding="utf-8")
        update_step_detail_field(
            plan_path, 1, "plan-details/orch/01-wire-up-renderer.md"
        )

        original = cli_module.generate_detail

        def patched(path, **kwargs):
            kwargs["invoker"] = lambda prompt: _GOOD_BODY
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.authoring.generate_detail", patched)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            [
                "--manifest",
                str(manifest),
                "detail",
                "orch",
                "--step",
                "1",
                "--force",
            ]
        )
        assert rc == 0
        body = detail_path.read_text(encoding="utf-8")
        assert "Wire up the renderer" in body
        assert "# Stale" not in body

    def test_cli_unknown_step_returns_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module

        _plan_path, manifest = self._setup(tmp_path)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            [
                "--manifest",
                str(manifest),
                "detail",
                "orch",
                "--step",
                "99",
            ]
        )
        assert rc == 2

    def test_cli_claude_failure_returns_one(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module

        _plan_path, manifest = self._setup(tmp_path)
        original = cli_module.generate_detail

        def patched(path, **kwargs):
            kwargs["invoker"] = lambda prompt: "no thanks"
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.authoring.generate_detail", patched)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            [
                "--manifest",
                str(manifest),
                "detail",
                "orch",
                "--step",
                "1",
            ]
        )
        assert rc == 1

    def test_cli_idempotent_skip_returns_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module

        plan_path, manifest = self._setup(tmp_path)
        # Pre-populate: file exists + pointer set → skip on re-run.
        detail_path = _detail_path_for(tmp_path, 1, "wire-up-renderer")
        detail_path.parent.mkdir(parents=True)
        detail_path.write_text("# Existing\n", encoding="utf-8")
        update_step_detail_field(
            plan_path, 1, "plan-details/orch/01-wire-up-renderer.md"
        )
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            [
                "--manifest",
                str(manifest),
                "detail",
                "orch",
                "--step",
                "1",
            ]
        )
        # Idempotent skip → exit 0 (not a failure).
        assert rc == 0


class TestLessonsCaptureDefaultOff:
    """Lesson capture is opt-in: ``generate_detail`` skips it unless asked."""

    def test_default_skips_lesson_extraction(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No ``extract_lessons`` kwarg → the extractor is never called.

        Re-monkeypatches the autouse ``_stub_lessons_extraction`` no-op with
        a counting spy so the assertion is "zero calls", not "no real claude".
        """
        from plan_tool import detail as detail_module

        calls: list[dict] = []
        monkeypatch.setattr(
            detail_module,
            "extract_and_append_detail_lessons",
            lambda **kwargs: (calls.append(kwargs), (0, 0))[1],
        )
        plan_path = _write_detail_plan(tmp_path)

        generate_detail(
            plan_path,
            repo_root=tmp_path,
            invoker=lambda _p: _GOOD_BODY,
            reporter=NullReporter(),
        )

        assert calls == []

    def test_extract_lessons_true_still_captures(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The opt-in kwarg reaches the extractor after a clean quality pass."""
        from plan_tool import detail as detail_module
        from plan_tool.convergence import IterativeBudget

        calls: list[dict] = []
        monkeypatch.setattr(
            detail_module,
            "extract_and_append_detail_lessons",
            lambda **kwargs: (calls.append(kwargs), (0, 0))[1],
        )
        monkeypatch.setattr(
            detail_module,
            "collect_detail_quality_findings",
            lambda *a, **kw: [],
        )
        plan_path = _write_detail_plan(tmp_path)

        generate_detail(
            plan_path,
            repo_root=tmp_path,
            invoker=lambda _p: _GOOD_BODY,
            reporter=NullReporter(),
            extract_lessons=True,
            lessons_invoker=lambda _p: "{}",
            budget=IterativeBudget(enabled=True, max_iterations=3),
        )

        # One call per authored step — derived, not hardcoded, so adding a
        # step to the shared ``_DETAIL_PLAN`` fixture doesn't fail here.
        assert len(calls) == len(parse_plan(plan_path).steps)
        assert [c["step"].id for c in calls] == [
            s.id for s in parse_plan(plan_path).steps
        ]


@pytest.mark.integration
class TestLessonsFlag:
    """``detail --lessons`` / ``--no-lessons`` plumb into ``generate_detail``."""

    def _setup(self, tmp_path: Path) -> Path:
        _write_orchestrator_plan(tmp_path)
        manifest = tmp_path / "m.json"
        manifest.write_text('{"plans": ["2-orch.md"]}\n', encoding="utf-8")
        (tmp_path / ".git").mkdir()
        return manifest

    def _captured_kwargs(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        extra_argv: list[str],
    ) -> dict[str, object]:
        from plan_tool.cli import app as cli_module

        manifest = self._setup(tmp_path)
        captured: dict[str, object] = {}

        def fake_generate_detail(path, **kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(
            "plan_tool.cli.authoring.generate_detail", fake_generate_detail
        )
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            ["--manifest", str(manifest), "detail", "orch", "--step", "1"]
            + extra_argv
        )
        assert rc == 0
        return captured

    def test_default_is_extract_lessons_false(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured = self._captured_kwargs(tmp_path, monkeypatch, [])
        assert captured.get("extract_lessons") is False

    def test_lessons_flag_opts_in(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured = self._captured_kwargs(tmp_path, monkeypatch, ["--lessons"])
        assert captured.get("extract_lessons") is True

    def test_no_lessons_flag_still_accepted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Scripts habitually passing ``--no-lessons`` keep working."""
        captured = self._captured_kwargs(tmp_path, monkeypatch, ["--no-lessons"])
        assert captured.get("extract_lessons") is False


@pytest.mark.integration
class TestResumePromptAndFlag:
    """`--no-resume` CLI flag plus interactive resume prompt on TTY."""

    def _setup(self, tmp_path: Path) -> tuple[Path, Path]:
        plan_path = _write_orchestrator_plan(tmp_path)
        manifest = tmp_path / "m.json"
        manifest.write_text(
            '{"plans": ["2-orch.md"]}\n', encoding="utf-8"
        )
        (tmp_path / ".git").mkdir()
        return plan_path, manifest

    def test_no_resume_flag_passes_resume_false_to_generate_detail(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module

        _plan_path, manifest = self._setup(tmp_path)
        captured: dict[str, object] = {}

        def fake_generate_detail(path, **kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr("plan_tool.cli.authoring.generate_detail", fake_generate_detail)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            [
                "--manifest",
                str(manifest),
                "detail",
                "orch",
                "--step",
                "1",
                "--no-resume",
            ]
        )
        assert rc == 0
        assert captured.get("resume") is False

    def test_no_resume_flag_default_is_resume_true(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module

        _plan_path, manifest = self._setup(tmp_path)
        captured: dict[str, object] = {}

        def fake_generate_detail(path, **kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr("plan_tool.cli.authoring.generate_detail", fake_generate_detail)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            [
                "--manifest",
                str(manifest),
                "detail",
                "orch",
                "--step",
                "1",
            ]
        )
        assert rc == 0
        assert captured.get("resume") is True

    def test_resume_prompt_yes_returns_cached_body(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)

        ckpt_path = checkpoint_path(
            tmp_path,
            "orch",
            _DETAIL_CHECKPOINT_NAME.format(step_id=step.id),
        )
        save_checkpoint(
            ckpt_path,
            Checkpoint(
                input_hash=_detail_step_input_hash(plan_path, step),
                payload=_GOOD_BODY,
                created_at=_fresh_now(),
            ),
        )

        # Pretend stdin is a TTY so the prompt fires.
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        def boom_invoker(prompt: str) -> str:
            raise AssertionError("invoker should not be called on cache hit")

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=boom_invoker,
            extract_lessons=False,
            prompt_fn=lambda _q: "",  # empty → default yes
        )
        assert results[0].written is True
        detail_path = _detail_path_for(tmp_path, 1, "wire-up-renderer")
        assert _GOOD_BODY_STAMPED in detail_path.read_text(encoding="utf-8")

    def test_resume_prompt_no_discards_checkpoint_and_reinvokes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)

        ckpt_path = checkpoint_path(
            tmp_path,
            "orch",
            _DETAIL_CHECKPOINT_NAME.format(step_id=step.id),
        )
        save_checkpoint(
            ckpt_path,
            Checkpoint(
                input_hash=_detail_step_input_hash(plan_path, step),
                payload="# should not be used\n\n## Why\n\nx\n",
                created_at=_fresh_now(),
            ),
        )

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        calls: list[str] = []

        def fake(prompt: str) -> str:
            calls.append(prompt)
            return _GOOD_BODY

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=fake,
            extract_lessons=False,
            prompt_fn=lambda _q: "n",
        )
        assert results[0].written is True
        # Re-invoked because user declined the cache.
        assert len(calls) == 1
        # Checkpoint is gone — discarded on decline, then again post-commit.
        assert not ckpt_path.exists()
        body = results[0].output_path.read_text(encoding="utf-8")
        assert "should not be used" not in body

    def test_resume_prompt_skipped_when_not_tty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)

        ckpt_path = checkpoint_path(
            tmp_path,
            "orch",
            _DETAIL_CHECKPOINT_NAME.format(step_id=step.id),
        )
        save_checkpoint(
            ckpt_path,
            Checkpoint(
                input_hash=_detail_step_input_hash(plan_path, step),
                payload=_GOOD_BODY,
                created_at=_fresh_now(),
            ),
        )

        # Non-TTY: prompt MUST NOT be consulted.
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)

        def explode_prompt(_q: str) -> str:
            raise AssertionError("prompt_fn must not be called on non-TTY")

        def boom_invoker(prompt: str) -> str:
            raise AssertionError("invoker should not be called on cache hit")

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=boom_invoker,
            extract_lessons=False,
            prompt_fn=explode_prompt,
        )
        assert results[0].written is True
        detail_path = _detail_path_for(tmp_path, 1, "wire-up-renderer")
        assert _GOOD_BODY_STAMPED in detail_path.read_text(encoding="utf-8")


# --- progress reporting ----------------------------------------------------


class _RecordingHandle(StepHandle):
    """Captures complete/fail calls on one step for assertion."""

    def __init__(self) -> None:
        self.completed: tuple[float, int] | None = None
        self.failed: tuple[float, str] | None = None

    def complete(self, elapsed_s: float, response_bytes: int) -> None:
        self.completed = (elapsed_s, response_bytes)

    def fail(self, elapsed_s: float, reason: str) -> None:
        self.failed = (elapsed_s, reason)


class _RecordingReporter(ProgressReporter):
    """Captures (idx, total, label) per start_step call and the resulting handle.

    ``prefix`` (the convergence loop's structured progress descriptor) is
    captured separately so prefix-shape tests can assert it without the
    positional-tuple comparisons elsewhere having to grow a field.
    """

    def __init__(self) -> None:
        self.starts: list[tuple[int, int, str]] = []
        self.prefixes: list[Optional[str]] = []
        self.handles: list[_RecordingHandle] = []

    def start_step(
        self,
        idx: int,
        total: int,
        label: str,
        *,
        prefix: Optional[str] = None,
        phase: Optional[str] = None,
        attempt: int = 1,
        prompt_bytes: int = 0,
    ) -> StepHandle:
        self.starts.append((idx, total, label))
        self.prefixes.append(prefix)
        h = _RecordingHandle()
        self.handles.append(h)
        return h


@pytest.mark.integration
class TestGenerateDetailProgress:
    def test_start_complete_per_invoked_step(self, tmp_path: Path) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        reporter = _RecordingReporter()
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            invoker=lambda prompt: _GOOD_BODY,
            reporter=reporter,
            extract_lessons=False,
        )
        # Two steps in fixture, both invoked.
        assert reporter.starts == [
            (1, 2, "step 1: Wire up the renderer"),
            (2, 2, "step 2: Build it"),
        ]
        # Both succeed, response_bytes equals encoded body length.
        for h in reporter.handles:
            assert h.completed is not None
            assert h.failed is None
            elapsed, nbytes = h.completed
            assert elapsed >= 0.0
            assert nbytes == len(_GOOD_BODY.encode("utf-8"))

    def test_fail_on_unparseable_response(self, tmp_path: Path) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        reporter = _RecordingReporter()
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda prompt: "no thanks",
            reporter=reporter,
        )
        assert reporter.starts == [(1, 1, "step 1: Wire up the renderer")]
        h = reporter.handles[0]
        assert h.completed is None
        assert h.failed is not None
        _, reason = h.failed
        assert "unparseable" in reason

    def test_fail_on_write_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        reporter = _RecordingReporter()

        # Force the write step to raise.
        original_write = Path.write_text

        def explode(self: Path, *args, **kwargs):
            if "plan-details" in str(self):
                raise OSError("disk full")
            return original_write(self, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", explode)

        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda prompt: _GOOD_BODY,
            reporter=reporter,
        )
        h = reporter.handles[0]
        assert h.completed is None
        assert h.failed is not None
        _, reason = h.failed
        assert "write failed" in reason
        assert "disk full" in reason

    def test_fail_on_frontmatter_update_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        reporter = _RecordingReporter()

        from plan_tool import detail as detail_module

        def boom(*args, **kwargs):
            raise DetailError("frontmatter exploded")

        monkeypatch.setattr(detail_module, "update_step_detail_field", boom)

        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda prompt: _GOOD_BODY,
            reporter=reporter,
        )
        h = reporter.handles[0]
        assert h.completed is None
        assert h.failed is not None
        _, reason = h.failed
        assert "frontmatter" in reason

    def test_dry_run_emits_no_progress(self, tmp_path: Path) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        reporter = _RecordingReporter()
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            dry_run=True,
            invoker=lambda prompt: _GOOD_BODY,
            reporter=reporter,
        )
        # Dry-run skips claude entirely → no reporter activity.
        assert reporter.starts == []

    def test_idempotent_skip_emits_no_progress(self, tmp_path: Path) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        # Pre-populate step 1 → next call should skip.
        detail_path = _detail_path_for(tmp_path, 1, "wire-up-renderer")
        detail_path.parent.mkdir(parents=True)
        detail_path.write_text("# Existing\n", encoding="utf-8")
        update_step_detail_field(
            plan_path, 1, "plan-details/orch/01-wire-up-renderer.md"
        )

        reporter = _RecordingReporter()

        def fake(prompt: str) -> str:
            return _GOOD_BODY

        generate_detail(
            plan_path,
            repo_root=tmp_path,
            invoker=fake,
            reporter=reporter,
            extract_lessons=False,
        )
        # Step 1 skipped, step 2 invoked → exactly one start_step call,
        # numbered (1/1) — counter reflects invocations, not raw targets.
        assert reporter.starts == [(1, 1, "step 2: Build it")]


class TestCmdDetailEndToEndStderr:
    """End-to-end CLI test that ``StderrReporter`` (the production default)
    actually emits progress lines to ``sys.stderr`` when the user runs
    ``plan-tool detail``. Guards against a future refactor that drops the
    reporter wiring or swaps ``StderrReporter`` for ``NullReporter``.
    """

    def test_emits_start_and_done_lines_on_stderr(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        _write_orchestrator_plan(tmp_path)
        manifest = tmp_path / "m.json"
        manifest.write_text('{"plans": ["2-orch.md"]}\n', encoding="utf-8")
        (tmp_path / ".git").mkdir()

        original = cli_module.generate_detail

        def patched(path, **kwargs):
            kwargs["invoker"] = lambda prompt: _GOOD_BODY
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.authoring.generate_detail", patched)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            [
                "--manifest",
                str(manifest),
                "detail",
                "orch",
                "--step",
                "1",
            ]
        )
        assert rc == 0
        err = capsys.readouterr().err
        # Start line and a closing ``done in Xs`` line landed on stderr.
        # Singleton call (n=1) → the ``[1/1]`` counter is suppressed.
        assert "step 1: Wire up the renderer" in err
        assert "[1/1]" not in err
        assert "done in" in err
        assert "KB response" in err


# --- Step 5: missing-files-mentioned warning -------------------------------


@pytest.mark.integration
class TestGenerateDetailMissingFilesWarning:
    def test_warns_when_few_files_mentioned(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        # Body with all required sections but no mention of foo.py / renderer.py.
        body = (
            "# Title\n\n"
            "## Summary\n\nOverview.\n\n"
            "## Table of Contents\n\n- [Why](#why) — motivation\n\n"
            "## Why\n\nReason.\n\n"
            "## Files\n\n- something\n\n"
            "## Implementation\n\nstuff\n\n"
            "## Tests\n\n- test\n\n"
            "## Acceptance criteria\n\n- works\n"
        )
        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=2,  # uses files: ["foo.py"]
            invoker=lambda prompt: body,
        )
        assert results[0].written is True
        err = capsys.readouterr().err
        assert "foo.py" in err
        assert "0 of 1 declared files" in err

    def test_no_warning_when_files_mentioned(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        # Body that does mention renderer.py.
        body = (
            "# Title\n\n"
            "## Summary\n\nOverview.\n\n"
            "## Table of Contents\n\n- [Why](#why) — motivation\n\n"
            "## Why\n\nReason.\n\n"
            "## Files\n\n- renderer.py\n\n"
            "## Implementation\n\nrenderer.py is updated\n\n"
            "## Tests\n\n- test\n\n"
            "## Acceptance criteria\n\n- works\n"
        )
        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,  # uses files: ["renderer.py"]
            invoker=lambda prompt: body,
        )
        assert results[0].written is True
        err = capsys.readouterr().err
        assert "declared files" not in err


# --- plan-level references seeding ----------------------------------------


_PLAN_WITH_REFS_TEMPLATE = """---
title: Detail Test Plan
status: in-progress
priority: medium
steps:
  - id: 1
    title: Wire up the renderer
    files:
      - renderer.py
    complexity: low
    status: current
---

# Detail Test Plan

## Overview

Some overview.

## References

{body}

## Steps

See the `steps:` block in the frontmatter.
"""


def _write_plan_with_references(tmp_path: Path, refs_body: str) -> Path:
    plan_path = tmp_path / "2-foo.md"
    plan_path.write_text(
        _PLAN_WITH_REFS_TEMPLATE.format(body=refs_body), encoding="utf-8"
    )
    (tmp_path / "renderer.py").write_text(
        "def render(plan):\n    return None\n", encoding="utf-8"
    )
    return plan_path


class TestExtractPlanReferences:
    def test_returns_bulleted_refs_body(self, tmp_path: Path) -> None:
        body = (
            "- [Vendor Docs](https://example.com) — primary API reference.\n"
            "- [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110) — HTTP semantics."
        )
        plan_path = _write_plan_with_references(tmp_path, body)
        out = extract_plan_references(plan_path)
        assert "Vendor Docs" in out
        assert "RFC 9110" in out
        assert "https://example.com" in out

    def test_empty_when_no_references_section(self, tmp_path: Path) -> None:
        # Use the base _DETAIL_PLAN which has no body sections at all.
        plan_path = _write_detail_plan(tmp_path)
        assert extract_plan_references(plan_path) == ""

    def test_empty_when_todo_placeholder(self, tmp_path: Path) -> None:
        plan_path = _write_plan_with_references(tmp_path, "_(TODO)_")
        assert extract_plan_references(plan_path) == ""

    def test_empty_when_bare_todo(self, tmp_path: Path) -> None:
        plan_path = _write_plan_with_references(tmp_path, "TODO")
        assert extract_plan_references(plan_path) == ""

    def test_case_insensitive_heading(self, tmp_path: Path) -> None:
        # Override the template's heading casing.
        plan_path = tmp_path / "p.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: t\n"
            "---\n"
            "\n"
            "## REFERENCES\n\n"
            "- [Docs](https://example.com) — read this.\n",
            encoding="utf-8",
        )
        out = extract_plan_references(plan_path)
        assert "[Docs](https://example.com)" in out

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert extract_plan_references(tmp_path / "nope.md") == ""

    def test_stops_at_next_h2(self, tmp_path: Path) -> None:
        plan_path = _write_plan_with_references(
            tmp_path, "- [A](https://a.com) — first."
        )
        out = extract_plan_references(plan_path)
        # ``## Steps`` follows References in the template — must not leak in.
        assert "Steps" not in out
        assert "steps:` block" not in out


class TestExtractPlanGuardrails:
    """Wiring only — the extractor's own cases live in
    ``tests/test_scope_fence.py`` beside the implementation."""

    def test_out_of_scope_reaches_the_detail_prompt(self, tmp_path: Path) -> None:
        # End-to-end: the gap this closes was a populated fence that the
        # prompt never saw.
        plan_path = _write_plan_with_references(tmp_path, "- [A](https://a.com)")
        plan_path.write_text(
            plan_path.read_text(encoding="utf-8")
            + "\n## Out of scope\n\nDo not add an export gate.\n",
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)

        prompt = render_detail_prompt(
            plan,
            plan.step_by_id(1),
            repo_root=tmp_path,
            scope_fence_block=extract_plan_guardrails(plan_path),
        )

        assert "Do not add an export gate." in prompt
        assert "_no plan-level guardrails or scope fence_" not in prompt
        assert "Keep the detail proportional to the plan." in prompt
        assert "**Smallest proof first.**" in prompt
        assert "current requirement that fails" in prompt
        assert "not permission to build both possible designs" in prompt
        assert "do not silently weaken it" in prompt


# A plan carrying intent at both altitudes, with per-step intents that differ
# so a hoisted fence render shows up as the wrong step's intent.
_INTENT_PLAN = """---
title: Intent Plan
intent: Make the step's stated purpose reach the model doing the work.
status: in-progress
priority: medium
steps:
  - id: 1
    title: Wire up the renderer
    intent: Give the renderer the fence.
    files:
      - renderer.py
    complexity: low
    status: current
  - id: 2
    title: Build it
    intent: Give the builder the fence.
    files:
      - foo.py
    depends_on: [1]
---

# Intent Plan
"""


def _write_intent_plan(root: Path) -> Path:
    """Write the two-step intent plan + its declared files."""
    root.mkdir(parents=True, exist_ok=True)
    plan_path = root / "2-intent.md"
    plan_path.write_text(_INTENT_PLAN, encoding="utf-8")
    (root / "renderer.py").write_text(
        "def render(plan):\n    return None\n", encoding="utf-8"
    )
    (root / "foo.py").write_text("FOO = 1\n", encoding="utf-8")
    return plan_path


def _prompt_for_step(prompts: list[str], step_id: int) -> str:
    """The one captured authoring prompt whose H1 names ``step_id``."""
    matches = [
        p
        for p in prompts
        if p.startswith(f"# Implementation detail for step {step_id}:")
    ]
    assert len(matches) == 1, f"step {step_id}: {len(matches)} prompts"
    return matches[0]


class TestScopeFenceReachesDetailPrompt:
    """Wiring only — ``render_scope_fence``'s own cases live in
    ``tests/test_scope_fence.py`` beside the implementation."""

    def test_plan_and_step_intent_reach_the_detail_prompt(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_intent_plan(tmp_path / "i")
        plan = parse_plan(plan_path)

        prompt = render_detail_prompt(
            plan,
            plan.step_by_id(1),
            repo_root=tmp_path / "i",
            scope_fence_block=render_scope_fence(
                plan_path,
                plan_intent=plan.intent or "",
                step_intent=plan.step_by_id(1).intent or "",
            ),
        )

        assert "Plan-level guardrails and scope fence (authoritative)" in prompt
        assert PLAN_INTENT_HEADING in prompt
        assert STEP_INTENT_HEADING in prompt
        assert "Make the step's stated purpose reach" in prompt
        assert "Give the renderer the fence." in prompt

    def test_prompt_carries_no_intent_heading_when_no_intent_is_set(
        self, tmp_path: Path
    ) -> None:
        # The no-migration property, end to end: a plan with no ``intent:``
        # renders the guardrail half alone.
        plan_path = _write_plan_with_references(tmp_path, "- [A](https://a.com)")
        plan_path.write_text(
            plan_path.read_text(encoding="utf-8")
            + "\n## Out of scope\n\nDo not add an export gate.\n",
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)

        block = render_scope_fence(
            plan_path,
            plan_intent=plan.intent or "",
            step_intent=step.intent or "",
        )
        prompt = render_detail_prompt(
            plan, step, repo_root=tmp_path, scope_fence_block=block
        )

        assert block == extract_plan_guardrails(plan_path)
        assert PLAN_INTENT_HEADING not in prompt
        assert STEP_INTENT_HEADING not in prompt

    def test_no_unresolved_template_placeholder_in_the_detail_prompt(
        self, tmp_path: Path
    ) -> None:
        # ``safe_substitute`` leaves an unmatched ``${name}`` in place and
        # raises nothing, so a half-landed template rename is silent.
        plan = parse_plan(_write_detail_plan(tmp_path))

        prompt = render_detail_prompt(
            plan,
            plan.step_by_id(1),
            repo_root=tmp_path,
            scope_fence_block="## Scope guardrails\n\nKeep this narrow.",
        )

        assert "${" not in prompt

    def test_budget_breakdown_labels_the_fence_block(
        self, tmp_path: Path
    ) -> None:
        plan = parse_plan(_write_detail_plan(tmp_path))
        blocks: list[tuple[str, int]] = []

        render_detail_prompt(
            plan,
            plan.step_by_id(1),
            repo_root=tmp_path,
            scope_fence_block="## Scope guardrails\n\nKeep this narrow.",
            collect_blocks=blocks,
        )

        labels = [name for name, _ in blocks]
        assert "scope-fence" in labels
        assert "plan-guardrails" not in labels


@pytest.mark.integration
class TestGenerateDetailThreadsIntent:
    """The fence render sits inside each authoring loop, so every step gets
    its *own* intent — hoisting it would give every step step 1's."""

    def _author(self, plan_path: Path, root: Path, **kwargs) -> list[str]:
        prompts: list[str] = []

        def capturing(prompt: str) -> str:
            prompts.append(prompt)
            return _GOOD_BODY

        results = generate_detail(
            plan_path,
            repo_root=root,
            invoker=capturing,
            reporter=NullReporter(),
            extract_lessons=False,
            **kwargs,
        )
        assert all(r.written for r in results)
        return prompts

    def test_generate_detail_passes_each_steps_own_intent(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "serial"
        prompts = self._author(_write_intent_plan(root), root)

        first = _prompt_for_step(prompts, 1)
        second = _prompt_for_step(prompts, 2)
        assert "Give the renderer the fence." in first
        assert "Give the builder the fence." not in first
        assert "Give the builder the fence." in second
        assert "Give the renderer the fence." not in second
        # The plan-level intent is shared, so both carry it.
        assert all(
            "Make the step's stated purpose reach" in p
            for p in (first, second)
        )

    def test_concurrent_detail_passes_each_steps_own_intent(
        self, tmp_path: Path
    ) -> None:
        # The concurrent pre-dispatch loop is a second copy of the same wiring.
        root = tmp_path / "concurrent"
        prompts = self._author(_write_intent_plan(root), root, jobs=2)

        assert "Give the renderer the fence." in _prompt_for_step(prompts, 1)
        assert "Give the builder the fence." in _prompt_for_step(prompts, 2)


class TestRenderDetailPromptIncludesPlanRefs:
    def test_plan_refs_passed_through_when_provided(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        prompt = render_detail_prompt(
            plan,
            step,
            repo_root=tmp_path,
            plan_references_block="- [Vendor Docs](https://example.com) — read me.",
        )
        assert "Plan-level references" in prompt
        assert "[Vendor Docs](https://example.com)" in prompt
        # The "no plan-level references" placeholder appears once in the
        # prompt's instruction prose explaining how claude should
        # behave when the data block is empty. When refs ARE supplied,
        # it should NOT also appear in the data slot — so total
        # occurrences stay at one.
        assert prompt.count("_no plan-level references available_") == 1

    def test_placeholder_when_no_plan_refs(self, tmp_path: Path) -> None:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        prompt = render_detail_prompt(plan, step, repo_root=tmp_path)
        # Once in the data slot, once in the instruction prose.
        assert prompt.count("_no plan-level references available_") == 2

    def test_plan_guardrails_are_authoritative_context(self, tmp_path: Path) -> None:
        plan = parse_plan(_write_detail_plan(tmp_path))
        prompt = render_detail_prompt(
            plan,
            plan.step_by_id(1),
            repo_root=tmp_path,
            scope_fence_block="## Scope guardrails\n\nKeep this narrow.",
        )

        assert "Plan-level guardrails and scope fence (authoritative)" in prompt
        assert "Keep this narrow." in prompt
        assert "Do not relax, contradict, replace, or silently omit it" in prompt
        assert "## Applicable guardrails" in prompt
        # The section references the plan's fence rather than reproducing its
        # wording: a quoted clause goes stale on the next plan edit, in a file
        # unrelated to that edit (BACKLOG #211).
        assert "Reference the constraint; do not reproduce its text." in prompt
        assert "name it and state the boundary" in prompt


@pytest.mark.integration
class TestGenerateDetailThreadsPlanReferences:
    def test_orchestrator_extracts_and_passes_refs(
        self, tmp_path: Path
    ) -> None:
        """End-to-end: ``generate_detail`` reads the plan's References
        section and the rendered prompt for each step carries it."""
        body = "- [Vendor Docs](https://example.com) — primary API reference."
        plan_path = _write_plan_with_references(tmp_path, body)
        plan_path.write_text(
            plan_path.read_text(encoding="utf-8")
            + "\n## Scope guardrails\n\nKeep the renderer change narrow.\n",
            encoding="utf-8",
        )

        captured: dict[str, str] = {}

        def fake_invoker(prompt: str) -> str:
            captured["prompt"] = prompt
            # Return a valid detail body (with the now-mandatory empty deferral
            # envelope, since this plan has body-section buckets) so
            # generate_detail succeeds.
            return _structured_detail(
                body=(
                    "# Step 1 — Wire up renderer\n\n"
                    "## Summary\n\nOverview.\n\n"
                    "## Table of Contents\n\n- [Why](#why) — motivation\n\n"
                    "## Why\n\nx\n\n"
                    "## Files\n\n- renderer.py\n\n"
                    "## Implementation\n\nUpdate renderer.py.\n\n"
                    "## Tests\n\n- test\n\n"
                    "## Acceptance criteria\n\n- works\n"
                )
            )

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=fake_invoker,
            reporter=NullReporter(),
        )
        assert results[0].written is True
        assert "Plan-level references" in captured["prompt"]
        assert "[Vendor Docs](https://example.com)" in captured["prompt"]
        assert "Keep the renderer change narrow." in captured["prompt"]

    def test_orchestrator_falls_back_when_plan_has_no_refs(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_detail_plan(tmp_path)  # no References section

        captured: dict[str, str] = {}

        def fake_invoker(prompt: str) -> str:
            captured["prompt"] = prompt
            return _structured_detail(
                body=(
                    "# Step 1 — Wire up renderer\n\n"
                    "## Summary\n\nOverview.\n\n"
                    "## Table of Contents\n\n- [Why](#why) — motivation\n\n"
                    "## Why\n\nx\n\n"
                    "## Files\n\n- renderer.py\n\n"
                    "## Implementation\n\nUpdate renderer.py.\n\n"
                    "## Tests\n\n- test\n\n"
                    "## Acceptance criteria\n\n- works\n"
                )
            )

        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=fake_invoker,
            reporter=NullReporter(),
        )
        assert "_no plan-level references available_" in captured["prompt"]


# --- Step 4: run_log structured events ------------------------------------


from plan_tool.run_log import RunLogWriter  # noqa: E402


def _read_run_log_for_slug(
    repo_root: Path, plan_slug: str
) -> tuple[Path, list[dict]]:
    """Locate and parse the single JSONL run log under ``runs/<plan_slug>/``.

    Asserts exactly one JSONL exists so callers don't have to disambiguate
    a leftover from a prior test (pytest's ``tmp_path`` fixture creates a
    fresh dir per test, so this should always be ``1`` unless the run
    actually opened two writers — which is a bug).
    """
    runs_dir = repo_root / ".plan-tool" / "runs" / plan_slug
    files = sorted(runs_dir.glob("*.jsonl"))
    assert len(files) == 1, (
        f"Expected exactly one JSONL under {runs_dir}; got: {files}"
    )
    lines = files[0].read_text(encoding="utf-8").splitlines()
    return files[0], [json.loads(ln) for ln in lines]


def _make_run_logger(tmp_path: Path, slug: str = "orch") -> RunLogWriter:
    return RunLogWriter.start(
        repo_root=tmp_path,
        slug=slug,
        command="detail",
        argv=["detail", slug, "--step", "1"],
        plan_path=None,
        step_filter=1,
        flags={"force": False, "dry_run": False, "lessons": False, "no_resume": False},
    )


class TestCmdDetailRunLog:
    """CLI-level integration: ``cmd_detail`` opens / closes a run log."""

    def _setup(self, tmp_path: Path) -> tuple[Path, Path]:
        plan_path = _write_orchestrator_plan(tmp_path)
        manifest = tmp_path / "m.json"
        manifest.write_text(
            '{"plans": ["2-orch.md"]}\n', encoding="utf-8"
        )
        (tmp_path / ".git").mkdir()
        return plan_path, manifest

    def test_run_start_and_run_end_emitted_exactly_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module

        plan_path, manifest = self._setup(tmp_path)
        original = cli_module.generate_detail

        def patched(path, **kwargs):
            kwargs["invoker"] = lambda prompt: _GOOD_BODY
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.authoring.generate_detail", patched)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            [
                "--manifest",
                str(manifest),
                "detail",
                "orch",
                "--step",
                "1",
                "--no-lessons",
            ]
        )
        assert rc == 0
        _, events = _read_run_log_for_slug(tmp_path, "orch")
        kinds = [e["event"] for e in events]
        assert kinds.count("run_start") == 1
        assert kinds.count("run_end") == 1
        assert kinds[0] == "run_start"
        assert kinds[-1] == "run_end"

    def test_run_end_outcome_success_on_zero_rc(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module

        plan_path, manifest = self._setup(tmp_path)
        original = cli_module.generate_detail

        def patched(path, **kwargs):
            kwargs["invoker"] = lambda prompt: _GOOD_BODY
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.authoring.generate_detail", patched)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            [
                "--manifest",
                str(manifest),
                "detail",
                "orch",
                "--step",
                "1",
                "--no-lessons",
            ]
        )
        assert rc == 0
        _, events = _read_run_log_for_slug(tmp_path, "orch")
        run_end = next(e for e in events if e["event"] == "run_end")
        assert run_end["outcome"] == "success"
        assert run_end["rc"] == 0

    def test_run_end_outcome_error_on_detail_error_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unknown ``--step`` raises ``DetailError`` → rc=2, outcome=error."""
        from plan_tool.cli import app as cli_module

        _plan_path, manifest = self._setup(tmp_path)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            [
                "--manifest",
                str(manifest),
                "detail",
                "orch",
                "--step",
                "99",
            ]
        )
        assert rc == 2
        _, events = _read_run_log_for_slug(tmp_path, "orch")
        run_end = next(e for e in events if e["event"] == "run_end")
        assert run_end["outcome"] == "error"
        assert run_end["rc"] == 2
        # ``error`` extra is set on the DetailError path.
        assert "error" in run_end and run_end["error"]

    def test_keyboard_interrupt_exits_130_after_recording_run_end(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module
        import plan_tool.cli.authoring as authoring

        _plan_path, manifest = self._setup(tmp_path)
        monkeypatch.setattr(
            authoring,
            "generate_detail",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
        )
        monkeypatch.chdir(tmp_path)

        with pytest.raises(SystemExit) as exc:
            cli_module.main([
                "--manifest", str(manifest), "detail", "orch", "--step", "1"
            ])
        assert exc.value.code == 130

        _, events = _read_run_log_for_slug(tmp_path, "orch")
        assert events[-1]["event"] == "run_end"
        assert events[-1]["rc"] == 130
        assert events[-1]["error"] == "interrupted"

    def test_run_end_outcome_error_on_skipped_failure_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Parse-exhaustion → DetailResult skipped, rc=1, outcome=error."""
        from plan_tool.cli import app as cli_module

        _plan_path, manifest = self._setup(tmp_path)
        original = cli_module.generate_detail

        def patched(path, **kwargs):
            kwargs["invoker"] = lambda prompt: "garbage"
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.authoring.generate_detail", patched)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            [
                "--manifest",
                str(manifest),
                "detail",
                "orch",
                "--step",
                "1",
                "--no-lessons",
            ]
        )
        assert rc == 1
        _, events = _read_run_log_for_slug(tmp_path, "orch")
        run_end = next(e for e in events if e["event"] == "run_end")
        assert run_end["outcome"] == "error"
        assert run_end["rc"] == 1

    def test_run_log_written_under_runs_slug_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.detail import _plan_slug as _detail_plan_slug

        plan_path, manifest = self._setup(tmp_path)
        original = cli_module.generate_detail

        def patched(path, **kwargs):
            kwargs["invoker"] = lambda prompt: _GOOD_BODY
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.authoring.generate_detail", patched)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            [
                "--manifest",
                str(manifest),
                "detail",
                "orch",
                "--step",
                "1",
                "--no-lessons",
            ]
        )
        assert rc == 0
        slug = _detail_plan_slug(plan_path)
        assert slug == "orch"
        log_path, _ = _read_run_log_for_slug(tmp_path, slug)
        assert log_path.parent == tmp_path / ".plan-tool" / "runs" / "orch"


@pytest.mark.integration
class TestGenerateDetailRunLogPhases:
    """Phase events open/close around steps that actually do work."""

    def test_one_phase_per_invoked_step(self, tmp_path: Path) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        run_logger = _make_run_logger(tmp_path)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            invoker=lambda prompt: _GOOD_BODY,
            extract_lessons=False,
            run_logger=run_logger,
        )
        run_logger.run_end(outcome="success", rc=0)
        _, events = _read_run_log_for_slug(tmp_path, "orch")
        phase_starts = [e for e in events if e["event"] == "phase_start"]
        phase_ends = [e for e in events if e["event"] == "phase_end"]
        assert len(phase_starts) == 2  # two steps, both invoked
        assert len(phase_ends) == 2
        assert phase_starts[0]["phase"] == "detail-step-01"
        assert phase_starts[1]["phase"] == "detail-step-02"

    def test_no_phase_event_for_already_exists_skip(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        # Pre-populate step 1.
        detail_path = _detail_path_for(tmp_path, 1, "wire-up-renderer")
        detail_path.parent.mkdir(parents=True)
        detail_path.write_text("# Existing\n", encoding="utf-8")
        update_step_detail_field(
            plan_path, 1, "plan-details/orch/01-wire-up-renderer.md"
        )

        run_logger = _make_run_logger(tmp_path)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda prompt: _GOOD_BODY,
            extract_lessons=False,
            run_logger=run_logger,
        )
        run_logger.run_end(outcome="success", rc=0)
        _, events = _read_run_log_for_slug(tmp_path, "orch")
        # Step 1 already exists → no phase events fired.
        assert not any(e["event"] == "phase_start" for e in events)
        assert not any(e["event"] == "phase_end" for e in events)

    def test_no_phase_event_for_dry_run(self, tmp_path: Path) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        run_logger = _make_run_logger(tmp_path)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            dry_run=True,
            invoker=lambda prompt: _GOOD_BODY,
            extract_lessons=False,
            run_logger=run_logger,
        )
        run_logger.run_end(outcome="success", rc=0)
        _, events = _read_run_log_for_slug(tmp_path, "orch")
        assert not any(e["event"] == "phase_start" for e in events)
        assert not any(e["event"] == "phase_end" for e in events)

    def test_phase_end_cached_true_on_resume_branch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A seeded checkpoint that hits → phase_end{cached: true}, no claude_call_start."""
        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        ckpt_path = checkpoint_path(
            tmp_path,
            "orch",
            _DETAIL_CHECKPOINT_NAME.format(step_id=step.id),
        )
        save_checkpoint(
            ckpt_path,
            Checkpoint(
                input_hash=_detail_step_input_hash(plan_path, step),
                payload=_GOOD_BODY,
                created_at=_fresh_now(),
            ),
        )
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)

        run_logger = _make_run_logger(tmp_path)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda p: (_ for _ in ()).throw(
                AssertionError("invoker must not run on cache hit")
            ),
            extract_lessons=False,
            run_logger=run_logger,
        )
        run_logger.run_end(outcome="success", rc=0)
        _, events = _read_run_log_for_slug(tmp_path, "orch")
        phase_ends = [e for e in events if e["event"] == "phase_end"]
        assert len(phase_ends) == 1
        assert phase_ends[0].get("cached") is True
        # No claude_call_start fired for the cached step.
        assert not any(e["event"] == "claude_call_start" for e in events)

    def test_phase_end_error_on_parse_exhaustion(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        run_logger = _make_run_logger(tmp_path)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda prompt: "no markdown here",
            extract_lessons=False,
            run_logger=run_logger,
        )
        run_logger.run_end(outcome="error", rc=1)
        _, events = _read_run_log_for_slug(tmp_path, "orch")
        phase_ends = [e for e in events if e["event"] == "phase_end"]
        assert len(phase_ends) == 1
        assert phase_ends[0]["outcome"] == "error"
        assert "unparseable" in phase_ends[0].get("reason", "")

    def test_phase_end_error_on_write_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        original_write = Path.write_text

        def explode(self: Path, *args, **kwargs):
            if "plan-details" in str(self):
                raise OSError("disk full")
            return original_write(self, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", explode)

        run_logger = _make_run_logger(tmp_path)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda prompt: _GOOD_BODY,
            extract_lessons=False,
            run_logger=run_logger,
        )
        run_logger.run_end(outcome="error", rc=1)
        _, events = _read_run_log_for_slug(tmp_path, "orch")
        phase_ends = [e for e in events if e["event"] == "phase_end"]
        assert len(phase_ends) == 1
        assert phase_ends[0]["outcome"] == "error"
        assert "write failed" in phase_ends[0].get("reason", "")

    def test_phase_end_error_on_frontmatter_update_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        from plan_tool import detail as detail_module

        def boom(*args, **kwargs):
            raise DetailError("frontmatter exploded")

        monkeypatch.setattr(detail_module, "update_step_detail_field", boom)

        run_logger = _make_run_logger(tmp_path)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda prompt: _GOOD_BODY,
            extract_lessons=False,
            run_logger=run_logger,
        )
        run_logger.run_end(outcome="error", rc=1)
        _, events = _read_run_log_for_slug(tmp_path, "orch")
        phase_ends = [e for e in events if e["event"] == "phase_end"]
        assert len(phase_ends) == 1
        assert phase_ends[0]["outcome"] == "error"
        assert "frontmatter" in phase_ends[0].get("reason", "")


@pytest.mark.integration
class TestGenerateDetailRunLogClaudeCalls:
    """ClaudeCallStart events fire per attempt of the retry loop."""

    def test_one_claude_call_start_per_attempt_happy_path(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        run_logger = _make_run_logger(tmp_path)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            invoker=lambda prompt: _GOOD_BODY,
            extract_lessons=False,
            run_logger=run_logger,
        )
        run_logger.run_end(outcome="success", rc=0)
        _, events = _read_run_log_for_slug(tmp_path, "orch")
        starts = [e for e in events if e["event"] == "claude_call_start"]
        # Two steps, one attempt each.
        assert len(starts) == 2
        assert all(e["attempt"] == 1 for e in starts)

    def test_two_claude_call_starts_on_retry_success(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        responses = ["garbage", _GOOD_BODY]

        def fake(prompt: str) -> str:
            return responses.pop(0)

        run_logger = _make_run_logger(tmp_path)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=fake,
            extract_lessons=False,
            run_logger=run_logger,
        )
        run_logger.run_end(outcome="success", rc=0)
        _, events = _read_run_log_for_slug(tmp_path, "orch")
        # Event order inside the single phase: start1, parse_fail1, start2.
        per_step = [
            e for e in events
            if e["event"] in {
                "claude_call_start", "parse_failure", "phase_end",
            }
        ]
        assert [e["event"] for e in per_step] == [
            "claude_call_start",
            "parse_failure",
            "claude_call_start",
            "phase_end",
        ]
        starts = [e for e in events if e["event"] == "claude_call_start"]
        assert [e["attempt"] for e in starts] == [1, 2]

    def test_prompt_bytes_includes_reprompt_suffix_on_attempt_two(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        responses = ["garbage", _GOOD_BODY]

        def fake(prompt: str) -> str:
            return responses.pop(0)

        run_logger = _make_run_logger(tmp_path)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=fake,
            extract_lessons=False,
            run_logger=run_logger,
        )
        run_logger.run_end(outcome="success", rc=0)
        _, events = _read_run_log_for_slug(tmp_path, "orch")
        starts = [e for e in events if e["event"] == "claude_call_start"]
        # Attempt 2's prompt has the reprompt suffix appended → strictly more bytes.
        assert starts[1]["prompt_bytes"] > starts[0]["prompt_bytes"]

    def test_no_claude_call_start_on_resumed_step(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        ckpt_path = checkpoint_path(
            tmp_path,
            "orch",
            _DETAIL_CHECKPOINT_NAME.format(step_id=step.id),
        )
        save_checkpoint(
            ckpt_path,
            Checkpoint(
                input_hash=_detail_step_input_hash(plan_path, step),
                payload=_GOOD_BODY,
                created_at=_fresh_now(),
            ),
        )
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)

        run_logger = _make_run_logger(tmp_path)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda p: (_ for _ in ()).throw(
                AssertionError("invoker must not run on cache hit")
            ),
            extract_lessons=False,
            run_logger=run_logger,
        )
        run_logger.run_end(outcome="success", rc=0)
        _, events = _read_run_log_for_slug(tmp_path, "orch")
        assert not any(e["event"] == "claude_call_start" for e in events)


@pytest.mark.integration
class TestGenerateDetailRunLogParseFailure:
    """Parse-failure events reference the on-disk dump rather than the payload."""

    def test_parse_failure_event_path_points_at_log_file_on_disk(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        responses = ["sure: but no markdown here", _GOOD_BODY]

        def fake(prompt: str) -> str:
            return responses.pop(0)

        run_logger = _make_run_logger(tmp_path)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=fake,
            extract_lessons=False,
            run_logger=run_logger,
        )
        run_logger.run_end(outcome="success", rc=0)
        _, events = _read_run_log_for_slug(tmp_path, "orch")
        pf = next(e for e in events if e["event"] == "parse_failure")
        # Path is relative; join with repo_root and verify the dump exists.
        rel = pf["failure_path"]
        assert rel
        assert (tmp_path / rel).is_file()
        # The dump on disk equals the rejected raw response.
        assert (tmp_path / rel).read_text(encoding="utf-8") == (
            "sure: but no markdown here"
        )

    def test_parse_failure_event_path_is_repo_relative(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        run_logger = _make_run_logger(tmp_path)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda prompt: "garbage",
            extract_lessons=False,
            run_logger=run_logger,
        )
        run_logger.run_end(outcome="error", rc=1)
        _, events = _read_run_log_for_slug(tmp_path, "orch")
        pfs = [e for e in events if e["event"] == "parse_failure"]
        assert pfs
        for pf in pfs:
            path = pf["failure_path"]
            assert path
            assert not path.startswith("/")
            assert "\\" not in path  # posix separators

    def test_parse_failure_event_path_empty_when_logging_failed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        from plan_tool import detail as detail_module

        def fail_log(**kwargs):
            return None  # simulate OSError inside _log_parse_failure

        monkeypatch.setattr(detail_module, "_log_parse_failure", fail_log)
        run_logger = _make_run_logger(tmp_path)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda prompt: "garbage-here",
            extract_lessons=False,
            run_logger=run_logger,
        )
        run_logger.run_end(outcome="error", rc=1)
        _, events = _read_run_log_for_slug(tmp_path, "orch")
        pf = next(e for e in events if e["event"] == "parse_failure")
        # Empty string when log path is None — the event still fires and
        # raw_bytes records the response size.
        assert pf["failure_path"] == ""
        assert pf.get("raw_bytes") == len("garbage-here".encode("utf-8"))

    def test_parse_failure_event_does_not_duplicate_payload(
        self, tmp_path: Path
    ) -> None:
        """Spec: parse_failure references the dump file, never the bytes."""
        plan_path = _write_orchestrator_plan(tmp_path)
        marker = "UNIQUE_SENTINEL_THAT_SHOULD_NOT_LEAK_TO_RUN_LOG"

        run_logger = _make_run_logger(tmp_path)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda prompt: marker,
            extract_lessons=False,
            run_logger=run_logger,
        )
        run_logger.run_end(outcome="error", rc=1)
        log_path, _ = _read_run_log_for_slug(tmp_path, "orch")
        raw_log = log_path.read_text(encoding="utf-8")
        assert marker not in raw_log


@pytest.mark.integration
class TestGenerateDetailRunLogCheckpoints:
    """Checkpoint hit/save/discard events fire at the four call sites."""

    def test_checkpoint_hit_emitted_for_valid_seeded_checkpoint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        ckpt_path = checkpoint_path(
            tmp_path,
            "orch",
            _DETAIL_CHECKPOINT_NAME.format(step_id=step.id),
        )
        save_checkpoint(
            ckpt_path,
            Checkpoint(
                input_hash=_detail_step_input_hash(plan_path, step),
                payload=_GOOD_BODY,
                created_at=_fresh_now(),
            ),
        )
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)

        run_logger = _make_run_logger(tmp_path)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda p: _GOOD_BODY,  # not called on cache hit
            extract_lessons=False,
            run_logger=run_logger,
        )
        run_logger.run_end(outcome="success", rc=0)
        _, events = _read_run_log_for_slug(tmp_path, "orch")
        hits = [e for e in events if e["event"] == "checkpoint_hit"]
        assert len(hits) == 1
        assert hits[0]["name"] == "detail-step-01"
        assert hits[0].get("step_id") == 1
        assert hits[0].get("created_at")
        assert hits[0]["payload_bytes"] == len(_GOOD_BODY.encode("utf-8"))

    def test_no_checkpoint_hit_for_invalid_or_missing(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        run_logger = _make_run_logger(tmp_path)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda prompt: _GOOD_BODY,
            extract_lessons=False,
            run_logger=run_logger,
        )
        run_logger.run_end(outcome="success", rc=0)
        _, events = _read_run_log_for_slug(tmp_path, "orch")
        assert not any(e["event"] == "checkpoint_hit" for e in events)

    def test_checkpoint_discard_user_declined_when_resume_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        ckpt_path = checkpoint_path(
            tmp_path,
            "orch",
            _DETAIL_CHECKPOINT_NAME.format(step_id=step.id),
        )
        save_checkpoint(
            ckpt_path,
            Checkpoint(
                input_hash=_detail_step_input_hash(plan_path, step),
                payload="# stale\n\n## Why\n\nx\n",
                created_at=_fresh_now(),
            ),
        )
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        run_logger = _make_run_logger(tmp_path)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda prompt: _GOOD_BODY,
            extract_lessons=False,
            run_logger=run_logger,
            prompt_fn=lambda _q: "n",
        )
        run_logger.run_end(outcome="success", rc=0)
        _, events = _read_run_log_for_slug(tmp_path, "orch")
        discards = [
            e for e in events
            if e["event"] == "checkpoint_discard"
            and e.get("reason") == "user_declined_resume"
        ]
        assert len(discards) == 1
        assert discards[0].get("step_id") == 1

    def test_checkpoint_save_after_successful_parse(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        run_logger = _make_run_logger(tmp_path)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda prompt: _GOOD_BODY,
            extract_lessons=False,
            run_logger=run_logger,
        )
        run_logger.run_end(outcome="success", rc=0)
        _, events = _read_run_log_for_slug(tmp_path, "orch")
        saves = [e for e in events if e["event"] == "checkpoint_save"]
        assert len(saves) == 1
        assert saves[0]["name"] == "detail-step-01"
        assert saves[0].get("step_id") == 1
        assert saves[0]["input_hash"]
        assert saves[0]["payload_bytes"] > 0

    def test_checkpoint_discard_durable_write_after_plan_update(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        run_logger = _make_run_logger(tmp_path)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda prompt: _GOOD_BODY,
            extract_lessons=False,
            run_logger=run_logger,
        )
        run_logger.run_end(outcome="success", rc=0)
        _, events = _read_run_log_for_slug(tmp_path, "orch")
        # Save then discard, in that order, per step.
        ckpt_events = [
            e for e in events
            if e["event"] in {"checkpoint_save", "checkpoint_discard"}
        ]
        kinds = [e["event"] for e in ckpt_events]
        assert kinds == ["checkpoint_save", "checkpoint_discard"]
        assert ckpt_events[1].get("reason") == "durable_write"

    def test_no_checkpoint_save_when_save_oserror(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        from plan_tool import detail as detail_module

        def boom(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(detail_module, "save_checkpoint", boom)
        run_logger = _make_run_logger(tmp_path)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda prompt: _GOOD_BODY,
            extract_lessons=False,
            run_logger=run_logger,
        )
        run_logger.run_end(outcome="success", rc=0)
        _, events = _read_run_log_for_slug(tmp_path, "orch")
        # The on-success-only contract: save event never fires when
        # ``save_checkpoint`` raises.
        assert not any(e["event"] == "checkpoint_save" for e in events)


@pytest.mark.integration
class TestGenerateDetailRunLogBackCompat:
    """``run_logger=None`` (the default) is a pure no-op."""

    def test_run_logger_none_is_a_no_op(self, tmp_path: Path) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda prompt: _GOOD_BODY,
            extract_lessons=False,
        )
        assert results[0].written is True
        # No .plan-tool/runs/ artifacts.
        assert not (tmp_path / ".plan-tool" / "runs").exists()


# --- Step 3: detail-quality iteration loop -------------------------------

from plan_tool.convergence import IterativeBudget as _IterativeBudget  # noqa: E402
from plan_tool.detail import (  # noqa: E402
    _DETAIL_GROUNDING_SOURCES,
    DeferralReport,
    _cached_purity_findings,
    _iteration_prefix,
    collect_detail_quality_findings,
    render_detail_quality_prompt,
    summarize_deferral_delta,
)
from plan_tool.launcher import ApplyFindingResult as _ApplyFindingResult  # noqa: E402


_FINDINGS_BLOCK_TWO_OPEN = (
    "Review of the detail body.\n\n"
    "Both issues are worth flagging before the developer picks this up.\n\n"
    "## Findings\n\n"
    "- MEDIUM: implementation paragraph in step 1 omits file:line citations\n"
    "- NIT: tests bullet uses vague 'a lot' wording\n"
)

_FINDINGS_BLOCK_NONE = (
    "Review of the detail body.\n\n"
    "Looks good — no actionable issues.\n\n"
    "## Findings\n\n"
    "_(none)_\n"
)


class TestDetailIterationBudgetScaling:
    def test_default_cap_scales_by_complexity(self) -> None:
        base = _IterativeBudget(enabled=True, max_iterations=3)

        assert _scaled_detail_budget_for_step(
            Step(id=1, title="low", complexity=Complexity.LOW), base
        ).max_iterations == 1
        assert _scaled_detail_budget_for_step(
            Step(id=1, title="medium", complexity=Complexity.MEDIUM), base
        ).max_iterations == 2
        assert _scaled_detail_budget_for_step(
            Step(id=1, title="high", complexity=Complexity.HIGH), base
        ).max_iterations == 3
        assert _scaled_detail_budget_for_step(
            Step(id=1, title="unknown"), base
        ).max_iterations == 3

    def test_non_default_cap_is_not_scaled(self) -> None:
        explicit = _IterativeBudget(enabled=True, max_iterations=5)

        scaled = _scaled_detail_budget_for_step(
            Step(id=1, title="low", complexity=Complexity.LOW), explicit
        )

        assert scaled is explicit
        assert scaled.max_iterations == 5

    def test_disabled_budget_is_not_scaled(self) -> None:
        disabled = _IterativeBudget(enabled=False, max_iterations=3)

        assert (
            _scaled_detail_budget_for_step(
                Step(id=1, title="low", complexity=Complexity.LOW), disabled
            )
            is disabled
        )

    def test_scaling_preserves_time_budget_fields(self) -> None:
        # Regression (#123): the per-step cap-scaling rebuild must carry the
        # cooperative wall-clock cap forward, not reset it — else --time-budget
        # would silently no-op on every LOW/MEDIUM detail step.
        base = _IterativeBudget(
            enabled=True,
            max_iterations=3,
            hard_budget_seconds=300,
            op_started_at=42.0,
        )
        scaled = _scaled_detail_budget_for_step(
            Step(id=1, title="low", complexity=Complexity.LOW), base
        )
        assert scaled.max_iterations == 1  # scaled
        assert scaled.hard_budget_seconds == 300  # preserved
        assert scaled.op_started_at == 42.0  # preserved


_ALTITUDE_REGRESSION_DETAIL_BODY = (
    "# Step 1 - Tune prompt cache budget\n\n"
    "## Summary\n\n"
    "Keep the prompt cache budget concept stable while making the executor "
    "details less brittle.\n\n"
    "## Table of Contents\n\n"
    "- [Summary](#summary) - overview\n"
    "- [Implementation](#implementation) - work\n"
    "- [Tests](#tests) - checks\n"
    "- [Acceptance criteria](#acceptance-criteria) - done\n\n"
    "## Why\n\n"
    "The prompt cache budget should be easy to preserve across steps.\n\n"
    "## Files\n\n"
    "- edits: `renderer.py`\n\n"
    "## Implementation\n\n"
    "In `renderer.py:render`, add `build_prompt_cache_budget(max_tokens=4096, "
    "retry_ms=250, helper_name=\"forcePromptCacheBudget\")` exactly as written, "
    "then pass `{\"cache_control\": {\"type\": \"ephemeral\"}}` to every call. "
    "Demote these mechanics to e.g. examples when they are not required.\n\n"
    "## Tests\n\n"
    "- `test_prompt_cache_budget_unit_a`\n"
    "- `test_prompt_cache_budget_unit_b`\n"
    "- `test_prompt_cache_budget_unit_c`\n\n"
    "## Acceptance criteria\n\n"
    "- The prompt cache budget phrase stays stable in related steps.\n"
)


def _stub_apply_result_detail() -> _ApplyFindingResult:
    """Inert ``ApplyFindingResult`` for fake ``apply_finding`` doubles."""
    return _ApplyFindingResult(
        step_id=None,
        exit_code=0,
        verdict="APPLIED",
        summary="",
        diff_text="",
        pre_snapshot={},
        stdout="",
    )


def _seed_step1_detail_file(tmp_path: Path) -> Path:
    """Pre-populate ``plan-details/orch/01-wire-up-renderer.md`` so the
    detail-file-on-disk preconditions for iteration are met without
    routing through the full ``generate_detail`` initial write.
    """
    detail_path = _detail_path_for(tmp_path, 1, "wire-up-renderer")
    detail_path.parent.mkdir(parents=True, exist_ok=True)
    detail_path.write_text(_GOOD_BODY, encoding="utf-8")
    return detail_path


class TestRenderDetailQualityPrompt:
    """``render_detail_quality_prompt`` substitutes plan/step/body context."""

    def test_detail_quality_prompt_renders_supplied_risk_context_block(
        self, tmp_path: Path
    ) -> None:
        plan = parse_plan(_write_orchestrator_plan(tmp_path))
        risk_context_block = "## Test risk context\n\nSUPPLIED-RISK-CONTEXT\n\n"

        prompt = render_detail_quality_prompt(
            plan,
            plan.step_by_id(1),
            repo_root=tmp_path,
            detail_body=_GOOD_BODY,
            risk_context_block=risk_context_block,
        )

        assert prompt.index("SUPPLIED-RISK-CONTEXT") < prompt.index(
            "## Step files"
        )

    def test_empty_risk_context_keeps_detail_prompts_renderable(
        self, tmp_path: Path
    ) -> None:
        plan = parse_plan(_write_orchestrator_plan(tmp_path))
        step = plan.step_by_id(1)

        authoring_default = render_detail_prompt(plan, step, repo_root=tmp_path)
        authoring_empty = render_detail_prompt(
            plan, step, repo_root=tmp_path, risk_context_block=""
        )
        quality_default = render_detail_quality_prompt(
            plan, step, repo_root=tmp_path, detail_body=_GOOD_BODY
        )
        quality_empty = render_detail_quality_prompt(
            plan,
            step,
            repo_root=tmp_path,
            detail_body=_GOOD_BODY,
            risk_context_block="",
        )

        assert authoring_default == authoring_empty
        assert quality_default == quality_empty
        assert "${risk_context_block}" not in authoring_default
        assert "${risk_context_block}" not in quality_default

    def test_embeds_confirmed_project_context(self, tmp_path: Path) -> None:
        initialize_project_profile(
            tmp_path,
            intent="Keep the implementation narrow.",
            non_goals=("Do not add a service.",),
            decisions=("Prefer reversible changes.",),
        )
        plan = parse_plan(_write_orchestrator_plan(tmp_path))

        prompt = render_detail_quality_prompt(
            plan,
            plan.step_by_id(1),
            repo_root=tmp_path,
            detail_body=_GOOD_BODY,
        )

        assert "Keep the implementation narrow." in prompt
        assert "Do not add a service." in prompt
        assert "Prefer reversible changes." in prompt
        assert prompt.index("Confirmed project context") < prompt.index(
            "## Step files"
        )

    def test_includes_authoritative_plan_guardrails(self, tmp_path: Path) -> None:
        plan = parse_plan(_write_orchestrator_plan(tmp_path))
        prompt = render_detail_quality_prompt(
            plan,
            plan.step_by_id(1),
            repo_root=tmp_path,
            detail_body=_GOOD_BODY,
            plan_guardrails_block="## Audit guardrails\n\nKeep warnings advisory.",
        )

        assert "Plan-level guardrails and scope fence (authoritative)" in prompt
        assert "Keep warnings advisory." in prompt
        assert "Plan-guardrail drift" in prompt
        assert "## Applicable guardrails" in prompt

    def test_never_receives_the_intent(self, tmp_path: Path) -> None:
        # The review prompt gets the guardrail half only. Handing it the
        # intent *and* the authored prose it explains would set up an
        # intent-vs-prose agreement check the plan's fence refuses.
        plan_path = _write_intent_plan(tmp_path / "i")
        plan_path.write_text(
            plan_path.read_text(encoding="utf-8")
            + "\n## Audit guardrails\n\nKeep warnings advisory.\n",
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)

        prompt = render_detail_quality_prompt(
            plan,
            step,
            repo_root=tmp_path / "i",
            detail_body=_GOOD_BODY,
            plan_guardrails_block=extract_plan_guardrails(plan_path),
        )

        assert "Keep warnings advisory." in prompt
        assert PLAN_INTENT_HEADING not in prompt
        assert STEP_INTENT_HEADING not in prompt
        assert "Give the renderer the fence." not in prompt

    def test_source_excerpt_contract_survives_cleanup(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        readable = tmp_path / "renderer.py"
        unreadable = tmp_path / "unreadable.py"
        readable.write_text(
            "\n".join(f"LEADING_FILLER_{i} = {i}" for i in range(80))
            + "\n\ndef renderer():\n    return 'target'\n",
            encoding="utf-8",
        )
        unreadable.write_text("def hidden():\n    pass\n", encoding="utf-8")
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        step.files.extend(["missing.py", "unreadable.py"])
        original_read_text = Path.read_text

        def fake_read_text(path: Path, *args, **kwargs) -> str:
            if path == unreadable:
                raise OSError("permission denied")
            return original_read_text(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", fake_read_text)

        prompt = render_detail_quality_prompt(
            plan,
            step,
            repo_root=tmp_path,
            detail_body=_GOOD_BODY,
            max_file_bytes=180,
        )

        assert "### `renderer.py`" in prompt
        assert "def renderer" in prompt
        assert "LEADING_FILLER_0" not in prompt
        assert "excerpt_kind: symbol" in prompt
        assert "### `missing.py` _(not on disk)_" in prompt
        assert "### `unreadable.py` _(unreadable: permission denied)_" in prompt

    def test_uses_same_symbol_excerpt_for_declared_python_file(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        source_path = tmp_path / "renderer.py"
        source_path.write_text(
            "\n".join(f"LEADING_FILLER_{i} = {i}" for i in range(80))
            + "\n\ndef renderer():\n    return 'target'\n",
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        prompt = render_detail_quality_prompt(
            plan,
            step,
            repo_root=tmp_path,
            detail_body=_GOOD_BODY,
            max_file_bytes=180,
        )

        source_at = prompt.index("def renderer")
        body_at = prompt.index("# Step 1")
        assert source_at < body_at
        assert "LEADING_FILLER_0" not in prompt
        assert "excerpt_kind: symbol" in prompt

    def test_substitutes_plan_and_step_metadata(self, tmp_path: Path) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        prompt = render_detail_quality_prompt(
            plan,
            step,
            repo_root=tmp_path,
            detail_body=_GOOD_BODY,
        )
        assert plan.title in prompt
        # ``${step_id}`` becomes "1" via ``str(step.id)``.
        assert "step 1" in prompt
        assert step.title in prompt
        # Step 1 has no depends_on → renders ``(none)`` literal.
        assert "depends on (none)" in prompt

    def test_includes_truncated_file_contents(self, tmp_path: Path) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        # Oversize file forces the truncation marker.
        big = "X" * 8192
        (tmp_path / "renderer.py").write_text(big, encoding="utf-8")
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        prompt = render_detail_quality_prompt(
            plan,
            step,
            repo_root=tmp_path,
            detail_body=_GOOD_BODY,
        )
        # Declared file path appears in the contents block header.
        assert "`renderer.py`" in prompt
        assert "_(truncated)_" in prompt

    def test_includes_detail_body_under_block_heading(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        body = "# Step 1 — verbatim\n\n## Why\n\nbecause\n"
        prompt = render_detail_quality_prompt(
            plan,
            step,
            repo_root=tmp_path,
            detail_body=body,
        )
        # Body substitutes verbatim under the block heading; no
        # fence-wrapping or escaping at render time.
        assert "# Step 1 — verbatim" in prompt
        assert "## Why" in prompt
        assert "because" in prompt

    def test_volatile_body_is_last_for_prefix_caching(
        self, tmp_path: Path
    ) -> None:
        """The per-iteration-volatile detail body must come AFTER the stable
        context (file contents, instructions, lessons) so the large static
        prefix stays cache-reusable across the loop's re-scans (#74 lever A1).
        A regression here silently re-breaks prefix caching."""
        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        body = "# UNIQUE-BODY-MARKER\n\n## Why\n\nbecause\n"
        prompt = render_detail_quality_prompt(
            plan, step, repo_root=tmp_path, detail_body=body,
        )
        body_at = prompt.index("UNIQUE-BODY-MARKER")
        # Body trails every stable section → those stay in the cached prefix.
        assert body_at > prompt.index("## Current contents of declared files")
        assert body_at > prompt.index("## What to do")
        assert body_at > prompt.index("## Findings")
        assert body_at > prompt.index("## Recurring failure modes")

    def test_lessons_block_renders_no_lessons_marker_when_empty(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        prompt = render_detail_quality_prompt(
            plan,
            step,
            repo_root=tmp_path,
            detail_body=_GOOD_BODY,
        )
        # With no lessons file under ``repo_root``, the lessons block
        # falls back to the "no lessons" marker — same shape the other
        # detail prompts surface.
        assert "no lessons" in prompt.lower()

    def test_quality_prompt_includes_advisory_altitude_contract(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        prompt = render_detail_quality_prompt(
            plan,
            step,
            repo_root=tmp_path,
            detail_body=_ALTITUDE_REGRESSION_DETAIL_BODY,
        )

        assert "## Advisory altitude findings" in prompt
        assert "conceptual-altitude" in prompt
        assert "demoting the material to `e.g.`" in prompt
        assert "Do **not** flag exact specificity" in prompt
        assert "Do not include these" in prompt
        assert "advisory bullets in the final `## Findings`" in prompt
        assert (
            "The final `## Findings` section below remains mandatory"
            in prompt
        )
        assert "prompt cache budget" in prompt


def test_run_grade_detail_authoring_routes_receive_declared_risk_context(
    tmp_path: Path,
) -> None:
    """Keep serial and concurrent run-grade authoring on one declaration."""
    serial_root = tmp_path / "serial"
    concurrent_root = tmp_path / "concurrent"
    serial_root.mkdir()
    concurrent_root.mkdir()
    serial_plan_path = _write_orchestrator_plan(serial_root)
    concurrent_plan_path = _write_orchestrator_plan(concurrent_root)
    rationale = "The renderer change crosses an external boundary."
    _set_declared_risk_profile(serial_plan_path, RiskProfile.HIGH, rationale)
    _set_declared_risk_profile(concurrent_plan_path, RiskProfile.HIGH, rationale)

    serial_prompts: list[str] = []
    concurrent_prompts: list[str] = []
    generate_detail(
        serial_plan_path,
        repo_root=serial_root,
        invoker=lambda prompt: serial_prompts.append(prompt) or _GOOD_BODY,
        extract_lessons=False,
        reporter=NullReporter(),
    )
    generate_detail(
        concurrent_plan_path,
        repo_root=concurrent_root,
        invoker=lambda prompt: concurrent_prompts.append(prompt) or _GOOD_BODY,
        extract_lessons=False,
        reporter=NullReporter(),
        jobs=2,
    )

    expected = render_declared_risk_context(parse_plan(serial_plan_path))
    assert expected
    assert len(serial_prompts) == len(concurrent_prompts) == 2
    assert all(expected in prompt for prompt in serial_prompts)
    assert all(expected in prompt for prompt in concurrent_prompts)


def test_detail_quality_review_receives_current_declared_risk_context(
    tmp_path: Path,
) -> None:
    """Render explicit declarations for review and leave legacy review inert.

    ``collect_detail_quality_findings`` takes ``risk_context_block`` as an
    explicit parameter (mirroring ``render_detail_prompt`` /
    ``render_detail_quality_prompt``) rather than computing it from ``plan``
    internally — it is also the producer behind the completeness-audit's
    read-through purity check, which must stay inert (see
    ``TestCachedPurityFindings.test_read_through_never_renders_declared_risk_context``).
    This test exercises the caller shape the detail-authoring loop uses:
    render the block from the current plan and pass it in.
    """
    explicit_root = tmp_path / "explicit"
    legacy_root = tmp_path / "legacy"
    explicit_root.mkdir()
    legacy_root.mkdir()
    explicit_plan_path = _write_orchestrator_plan(explicit_root)
    legacy_plan_path = _write_orchestrator_plan(legacy_root)
    rationale = "The review changes a shared integration contract."
    _set_declared_risk_profile(explicit_plan_path, RiskProfile.HIGH, rationale)

    for root, plan_path in (
        (explicit_root, explicit_plan_path),
        (legacy_root, legacy_plan_path),
    ):
        detail_path = _detail_path_for(root, 1, "wire-up-renderer")
        detail_path.parent.mkdir(parents=True)
        detail_path.write_text(_GOOD_BODY, encoding="utf-8")
        update_step_detail_field(
            plan_path, 1, detail_path.relative_to(root).as_posix()
        )

    explicit_plan = parse_plan(explicit_plan_path)
    explicit_prompts: list[str] = []
    collect_detail_quality_findings(
        explicit_plan_path,
        explicit_plan.step_by_id(1),
        repo_root=explicit_root,
        plan_name="orch",
        invoker=lambda prompt: explicit_prompts.append(prompt) or _FINDINGS_BLOCK_NONE,
        risk_context_block=render_declared_risk_context(explicit_plan),
    )
    legacy_prompts: list[str] = []
    collect_detail_quality_findings(
        legacy_plan_path,
        parse_plan(legacy_plan_path).step_by_id(1),
        repo_root=legacy_root,
        plan_name="orch",
        invoker=lambda prompt: legacy_prompts.append(prompt) or _FINDINGS_BLOCK_NONE,
    )

    expected = render_declared_risk_context(explicit_plan)
    assert expected in explicit_prompts[0]
    assert "Declared risk profile (advisory)" not in legacy_prompts[0]


def test_serial_detail_lifecycle_refreshes_context_after_accepted_declaration_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refresh later serial prompts only after an accepted detail-loop apply."""
    from plan_tool import detail as detail_module
    from plan_tool import launcher as launcher_module

    plan_path = _write_orchestrator_plan(tmp_path)
    original_rationale = "The change stays within one well-tested helper."
    updated_rationale = "The accepted edit crosses an external boundary."
    _set_declared_risk_profile(plan_path, RiskProfile.LOW, original_rationale)
    original_context = render_declared_risk_context(parse_plan(plan_path))

    apply_prompts: list[str] = []

    def apply_invoker(prompt: str) -> tuple[int, str]:
        apply_prompts.append(prompt)
        current = plan_path.read_text(encoding="utf-8")
        if len(apply_prompts) == 1:
            _set_declared_risk_profile(
                plan_path, RiskProfile.HIGH, updated_rationale
            )
            plan_path.write_text(
                plan_path.read_text(encoding="utf-8").replace(
                    "detail: plan-details/orch/01-wire-up-renderer.md",
                    "detail: plan-details/orch/missing.md",
                ),
                encoding="utf-8",
            )
            return 0, "## Summary\n- update declaration\n\n## Verdict\nAPPLIED\n"
        plan_path.write_text(
            current.replace(
                "detail: plan-details/orch/missing.md",
                "detail: plan-details/orch/01-wire-up-renderer.md",
            ),
            encoding="utf-8",
        )
        return 0, "## Summary\n- restore detail path\n\n## Verdict\nAPPLIED\n"

    real_apply = launcher_module.apply_finding

    def apply_with_captured_prompts(*args, **kwargs):  # noqa: ANN002, ANN003
        kwargs["invoker"] = apply_invoker
        return real_apply(*args, **kwargs)

    monkeypatch.setattr(detail_module, "apply_finding", apply_with_captured_prompts)

    review_counts = {1: 0, 2: 0}
    authoring_prompts: list[str] = []
    quality_prompts: list[str] = []

    def detail_invoker(prompt: str) -> str:
        if prompt.startswith("# Detail-quality review"):
            quality_prompts.append(prompt)
            step_id = 1 if "review for step 1:" in prompt else 2
            review_counts[step_id] += 1
            if step_id == 1 and review_counts[step_id] == 1:
                return "## Findings\n\n- MEDIUM: Refresh the detail.\n"
            return _FINDINGS_BLOCK_NONE
        authoring_prompts.append(prompt)
        return _GOOD_BODY

    results = generate_detail(
        plan_path,
        repo_root=tmp_path,
        invoker=detail_invoker,
        extract_lessons=False,
        reporter=NullReporter(),
        budget=_IterativeBudget(enabled=True, max_iterations=5),
    )

    updated_context = render_declared_risk_context(parse_plan(plan_path))
    assert all(result.written for result in results), (
        results,
        authoring_prompts,
        quality_prompts,
    )
    assert len(apply_prompts) == 2, (authoring_prompts, quality_prompts)
    assert updated_context != original_context
    assert all(
        original_context in prompt.split("## What to do", 1)[0]
        for prompt in apply_prompts
    )
    assert updated_context in authoring_prompts[1]
    assert updated_context in [
        prompt for prompt in quality_prompts if "review for step 2:" in prompt
    ][0]


def test_serial_detail_lifecycle_reauthors_later_step_from_accepted_frontmatter_edit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A step-1 accepted apply that edits step 2's own frontmatter (the class
    sweep apply-finding.md's own instructions explicitly invite) must reach
    step 2's authoring prompt — not a title/intent snapshot captured before
    the loop began. Refreshing ``plan`` mid-loop without also refreshing the
    stale ``step`` object it hands to ``render_detail_prompt`` would leave
    step 2 authored against its pre-edit title."""
    from plan_tool import detail as detail_module
    from plan_tool import launcher as launcher_module

    plan_path = _write_orchestrator_plan(tmp_path)
    original_title = "Build it"
    updated_title = "Build the renderer's downstream consumer"

    apply_prompts: list[str] = []

    def apply_invoker(prompt: str) -> tuple[int, str]:
        apply_prompts.append(prompt)
        # By the time this runs, step 1's own ``detail:`` update has already
        # re-serialized the plan; edit through its retained internal API.
        from plan_tool.parser import parse_plan, write_plan

        updated = parse_plan(plan_path)
        assert updated.step_by_id(2).title == original_title
        updated.step_by_id(2).title = updated_title
        write_plan(plan_path, updated)
        return 0, "## Summary\n- retitle step 2\n\n## Verdict\nAPPLIED\n"

    real_apply = launcher_module.apply_finding

    def apply_with_captured_prompts(*args, **kwargs):  # noqa: ANN002, ANN003
        kwargs["invoker"] = apply_invoker
        return real_apply(*args, **kwargs)

    monkeypatch.setattr(detail_module, "apply_finding", apply_with_captured_prompts)

    review_counts = {1: 0, 2: 0}
    authoring_prompts: list[str] = []

    def detail_invoker(prompt: str) -> str:
        if prompt.startswith("# Detail-quality review"):
            step_id = 1 if "review for step 1:" in prompt else 2
            review_counts[step_id] += 1
            if step_id == 1 and review_counts[step_id] == 1:
                return "## Findings\n\n- MEDIUM: Retitle step 2 for clarity.\n"
            return _FINDINGS_BLOCK_NONE
        authoring_prompts.append(prompt)
        return _GOOD_BODY

    results = generate_detail(
        plan_path,
        repo_root=tmp_path,
        invoker=detail_invoker,
        extract_lessons=False,
        reporter=NullReporter(),
        budget=_IterativeBudget(enabled=True, max_iterations=5),
    )

    assert all(result.written for result in results), (results, authoring_prompts)
    assert len(apply_prompts) == 1
    assert len(authoring_prompts) == 2
    step2_authoring_prompt = authoring_prompts[1]
    assert f"step 2: {updated_title}" in step2_authoring_prompt
    assert f"step 2: {original_title}" not in step2_authoring_prompt


def test_detail_quality_loop_recaptures_context_for_each_accepted_apply(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Capture each apply attempt from its own accepted plan snapshot."""
    from plan_tool import detail as detail_module

    plan_path = _write_orchestrator_plan(tmp_path)
    initial_rationale = "The first edit stays within a well-tested helper."
    updated_rationale = "The second edit crosses an external boundary."
    _set_declared_risk_profile(plan_path, RiskProfile.LOW, initial_rationale)
    initial_context = render_declared_risk_context(parse_plan(plan_path))
    detail_path = _seed_step1_detail_file(tmp_path)
    update_step_detail_field(
        plan_path, 1, detail_path.relative_to(tmp_path).as_posix()
    )

    findings = [
        Recommendation(
            id="risk-context-first",
            source="claude",
            severity="medium",
            step_id=1,
            title="First detail finding",
            body="Fix the first detail finding.",
        ),
        Recommendation(
            id="risk-context-second",
            source="claude",
            severity="medium",
            step_id=1,
            title="Second detail finding",
            body="Fix the second detail finding.",
        ),
    ]
    scans = {"count": 0}

    def fake_collect(*args, **kwargs):  # noqa: ANN002, ANN003
        scans["count"] += 1
        if scans["count"] <= len(findings):
            return [findings[scans["count"] - 1]]
        return []

    monkeypatch.setattr(detail_module, "collect_detail_quality_findings", fake_collect)
    captured_contexts: list[str] = []

    def fake_apply(*args, **kwargs):  # noqa: ANN002, ANN003
        captured_contexts.append(kwargs["risk_context_block"])
        if len(captured_contexts) == 1:
            _set_declared_risk_profile(
                plan_path, RiskProfile.HIGH, updated_rationale
            )
        return _stub_apply_result_detail()

    monkeypatch.setattr(detail_module, "apply_finding", fake_apply)
    plan = parse_plan(plan_path)
    detail_module._converge_run_grade_step_detail(
        step=plan.step_by_id(1),
        plan=plan,
        plan_path=plan_path,
        repo_root=tmp_path,
        plan_fingerprint=compute_plan_fingerprint(plan_path),
        plan_slug="orch",
        invoker=lambda _prompt: _GOOD_BODY,
        reporter=NullReporter(),
        run_logger=None,
        budget=_IterativeBudget(enabled=True, max_iterations=5),
        allow_drift=False,
        auto_reconcile_on_drift=True,
        collision_sidecar=True,
        triage=True,
        include_info=False,
        allow_split=False,
        prompt_fn=lambda _prompt: "",
        structural_seen=set(),
    )

    assert captured_contexts == [
        initial_context,
        render_declared_risk_context(parse_plan(plan_path)),
    ]


def test_undeclared_profile_keeps_detail_authoring_and_review_prompts_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Route an empty block without changing either legacy prompt renderer."""
    from plan_tool import detail as detail_module

    plan_path = _write_orchestrator_plan(tmp_path)
    captured_authoring_contexts: list[str] = []
    captured_quality_contexts: list[str] = []
    real_authoring_render = detail_module.render_detail_prompt
    real_quality_render = detail_module.render_detail_quality_prompt

    def capture_authoring(*args, **kwargs):  # noqa: ANN002, ANN003
        captured_authoring_contexts.append(kwargs["risk_context_block"])
        return real_authoring_render(*args, **kwargs)

    def capture_quality(*args, **kwargs):  # noqa: ANN002, ANN003
        captured_quality_contexts.append(kwargs["risk_context_block"])
        return real_quality_render(*args, **kwargs)

    monkeypatch.setattr(detail_module, "render_detail_prompt", capture_authoring)
    monkeypatch.setattr(
        detail_module, "render_detail_quality_prompt", capture_quality
    )

    generate_detail(
        plan_path,
        repo_root=tmp_path,
        step_id=1,
        invoker=lambda prompt: _FINDINGS_BLOCK_NONE
        if prompt.startswith("# Detail-quality review")
        else _GOOD_BODY,
        extract_lessons=False,
        reporter=NullReporter(),
        budget=_IterativeBudget(enabled=True, max_iterations=5),
    )

    plan = parse_plan(plan_path)
    step = plan.step_by_id(1)
    assert captured_authoring_contexts == [""]
    assert captured_quality_contexts == [""]
    assert real_authoring_render(plan, step, repo_root=tmp_path) == (
        real_authoring_render(
            plan, step, repo_root=tmp_path, risk_context_block=""
        )
    )
    assert real_quality_render(
        plan, step, repo_root=tmp_path, detail_body=_GOOD_BODY
    ) == real_quality_render(
        plan,
        step,
        repo_root=tmp_path,
        detail_body=_GOOD_BODY,
        risk_context_block="",
    )


class TestIterationPrefix:
    """``_iteration_prefix`` builds the convergence loop's structured prefix."""

    def test_full_position_with_budget(self) -> None:
        assert (
            _iteration_prefix(8, 2, 3, "scan") == "step 8 / iter 2-of-3 / scan"
        )

    def test_phase_may_carry_its_own_budget(self) -> None:
        assert (
            _iteration_prefix(8, 2, 3, "apply 1-of-3")
            == "step 8 / iter 2-of-3 / apply 1-of-3"
        )

    def test_drops_iter_segment_for_one_shot_probe(self) -> None:
        # iteration=0 → no iteration position, just step + phase.
        assert _iteration_prefix(8, 0, 3, "scan") == "step 8 / scan"

    def test_drops_iter_segment_when_budget_unknown(self) -> None:
        # max_iterations<=0 → can't form an ``-of-N`` denominator.
        assert _iteration_prefix(8, 2, 0, "scan") == "step 8 / scan"

    def test_terminal_pass_past_cap_is_named_convergence_check(self) -> None:
        # The loop's trailing re-scan passes ``state.iteration + 2``, which
        # reaches ``max_iterations + 1`` after the final apply round. That
        # pass opens no new round, so it must not read ``iter 4-of-3`` —
        # nor ``iter 3-of-3`` (that collides with round 3's opening scan).
        # It's named for its job: confirming convergence post-apply.
        assert _iteration_prefix(2, 4, 3, "scan") == "step 2 / convergence check"

    def test_last_budgeted_scan_at_cap_is_not_marked_final(self) -> None:
        # ``iteration == max_iterations`` is the opening scan of the final
        # budgeted round (applies still follow it), so it stays a plain
        # ``iter N-of-N`` — only ``> max_iterations`` is terminal.
        assert (
            _iteration_prefix(2, 3, 3, "scan") == "step 2 / iter 3-of-3 / scan"
        )


class TestSummarizeDeferralDelta:
    """``summarize_deferral_delta`` collapses a repeated deferred set to a
    one-line delta and keeps a changed set on the full-block path."""

    @staticmethod
    def _rec(rec_id: str) -> object:
        from plan_tool.review import Recommendation as _Rec

        return _Rec(
            id=rec_id, source="files-coherence", severity="nit",
            step_id=1, title=f"diagnostic {rec_id}", body="b",
            suggested_action=None,
        )

    def test_unchanged_set_collapses_to_delta_line(self) -> None:
        deferred = [self._rec("det-a"), self._rec("det-b")]
        report = summarize_deferral_delta(
            deferred,
            previous_ids=frozenset({"det-a", "det-b"}),
            previous_iteration=2,
        )
        assert isinstance(report, DeferralReport)
        assert report.collapsed is True
        assert report.line == (
            "deferred findings unchanged from iter 2 (2: det-a, det-b)"
        )

    def test_changed_set_prints_full_with_delta_note(self) -> None:
        # det-a survived, det-b resolved, det-c is new → full block, and the
        # note records both the addition and the resolution.
        deferred = [self._rec("det-a"), self._rec("det-c")]
        report = summarize_deferral_delta(
            deferred,
            previous_ids=frozenset({"det-a", "det-b"}),
            previous_iteration=2,
        )
        assert report.collapsed is False
        assert report.line == (
            "deferred set changed from iter 2 (+det-c; -det-b)"
        )

    def test_first_iteration_prints_full_with_no_delta_note(self) -> None:
        deferred = [self._rec("det-a")]
        report = summarize_deferral_delta(
            deferred, previous_ids=None, previous_iteration=0,
        )
        assert report.collapsed is False
        assert report.line == ""


class TestCollectDetailQualityFindingsProgressPrefix:
    """The scan call surfaces its iteration position as a structured prefix
    shared by the reporter's start/tick/done lines, not buried in label prose."""

    def test_scan_passes_structured_prefix(self, tmp_path: Path) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        _seed_step1_detail_file(tmp_path)
        update_step_detail_field(
            plan_path, 1, "plan-details/orch/01-wire-up-renderer.md"
        )
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)

        reporter = _RecordingReporter()
        collect_detail_quality_findings(
            plan_path,
            step,
            repo_root=tmp_path,
            plan_name="orch",
            invoker=lambda _p: _FINDINGS_BLOCK_NONE,
            iteration=2,
            max_iterations=3,
            reporter=reporter,
        )
        assert reporter.prefixes == ["step 1 / iter 2-of-3 / scan"]

    def test_one_shot_probe_prefix_has_no_iter_segment(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        _seed_step1_detail_file(tmp_path)
        update_step_detail_field(
            plan_path, 1, "plan-details/orch/01-wire-up-renderer.md"
        )
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)

        reporter = _RecordingReporter()
        collect_detail_quality_findings(
            plan_path,
            step,
            repo_root=tmp_path,
            plan_name="orch",
            invoker=lambda _p: _FINDINGS_BLOCK_NONE,
            reporter=reporter,
        )
        assert reporter.prefixes == ["step 1 / scan"]


class TestDistillLessonsRunLogging:
    """The lessons-distill call was spent unrecorded — no sink was installed,
    so ``shell._emit_call_end`` no-opped. See BACKLOG #176-#178."""

    class _FakeRunLogger:
        run_id = "run-1"

        def __init__(self) -> None:
            self.starts: list[tuple] = []
            self.binds: list[tuple] = []

        def claude_call_start(
            self, *, phase, attempt, prompt_bytes, prompt_sha256, **extra
        ):
            assert len(prompt_sha256) == 64  # hash of the prompt, never its text
            self.starts.append((phase, attempt, extra))

        def bind_shell_sink(self, *, phase, attempt):
            import contextlib

            self.binds.append((phase, attempt))
            return contextlib.nullcontext()

    def _run(self, tmp_path: Path, run_logger):
        # The autouse ``_stub_lessons_extraction`` fixture replaces the module
        # attribute, so call the import-time reference captured below (the same
        # bypass ``TestExtractDetailLessonsRoutesAroundPlanTargets`` uses); the
        # module-level import runs before any fixture, and the global resolves
        # at call time.
        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        return _real_extract_and_append_detail_lessons(
            plan=plan,
            plan_path=plan_path,
            step=plan.step_by_id(1),
            detail_body=_GOOD_BODY,
            repo_root=tmp_path,
            # Non-zero exit short-circuits after the invoke; the
            # instrumentation fires before it, which is what's under test.
            invoker=lambda _p: (1, ""),
            reporter=_RecordingReporter(),
            run_logger=run_logger,
        )

    def test_call_is_instrumented(self, tmp_path: Path) -> None:
        rl = self._FakeRunLogger()
        self._run(tmp_path, rl)
        assert rl.starts == [("distill_lessons", 1, {"step_id": 1})]
        assert rl.binds == [("distill_lessons", 1)]

    def test_without_run_logger_still_works(self, tmp_path: Path) -> None:
        result = self._run(tmp_path, None)
        assert (result.n_general_added, result.n_project_added) == (0, 0)


class TestCollectDetailQualityFindingsProgressClose:
    """The scan closes ``fail``, not ``complete``, when the reply carried no
    verdict — a timed-out call otherwise renders ``done … (0.0 KB response)``
    (and, after a transient retry notice, "recovered after 1 retry"), claiming
    coverage the scan never delivered. See BUG_BACKLOG."""

    def _scan(self, tmp_path: Path, raw: str) -> _RecordingHandle:
        plan_path = _write_orchestrator_plan(tmp_path)
        _seed_step1_detail_file(tmp_path)
        update_step_detail_field(
            plan_path, 1, "plan-details/orch/01-wire-up-renderer.md"
        )
        plan = parse_plan(plan_path)
        reporter = _RecordingReporter()
        collect_detail_quality_findings(
            plan_path,
            plan.step_by_id(1),
            repo_root=tmp_path,
            plan_name="orch",
            invoker=lambda _p: raw,
            reporter=reporter,
        )
        assert len(reporter.handles) == 1
        return reporter.handles[0]

    def test_well_formed_reply_completes(self, tmp_path: Path) -> None:
        handle = self._scan(tmp_path, _FINDINGS_BLOCK_NONE)
        assert handle.failed is None
        assert handle.completed is not None
        assert handle.completed[1] == len(_FINDINGS_BLOCK_NONE.encode("utf-8"))

    def test_empty_reply_fails(self, tmp_path: Path) -> None:
        handle = self._scan(tmp_path, "")
        assert handle.completed is None
        assert handle.failed is not None
        assert handle.failed[1] == "empty response (0 bytes)"

    def test_whitespace_only_reply_fails(self, tmp_path: Path) -> None:
        raw = "  \n\t\n"
        handle = self._scan(tmp_path, raw)
        assert handle.completed is None
        assert handle.failed is not None
        # Byte count is the real length, not a hardcoded 0 — whitespace is
        # empty in substance, not in bytes.
        assert handle.failed[1] == (
            f"empty response ({len(raw.encode('utf-8'))} bytes)"
        )

    def test_truncated_reply_fails_with_byte_count(self, tmp_path: Path) -> None:
        raw = "Review of the detail body.\n\n## Structural findings\n"
        handle = self._scan(tmp_path, raw)
        assert handle.completed is None
        assert handle.failed is not None
        assert handle.failed[1] == (
            "truncated response: no `## Findings` section "
            f"({len(raw.encode('utf-8'))} bytes)"
        )


class TestCollectDetailQualityFindings:
    """``collect_detail_quality_findings`` lifts the LLM Findings block
    and merges in the deterministic per-step grounding findings."""

    def test_returns_recommendation_per_bullet(self, tmp_path: Path) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        _seed_step1_detail_file(tmp_path)
        update_step_detail_field(
            plan_path, 1, "plan-details/orch/01-wire-up-renderer.md"
        )
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)

        calls: list[str] = []

        def fake(prompt: str) -> str:
            calls.append(prompt)
            return _FINDINGS_BLOCK_TWO_OPEN

        recs = collect_detail_quality_findings(
            plan_path,
            step,
            repo_root=tmp_path,
            plan_name="orch",
            invoker=fake,
        )
        # The two LLM bullets come through as ``claude``-sourced; the
        # deterministic supplement may add structural findings alongside.
        claude_recs = [r for r in recs if r.source == "claude"]
        assert len(claude_recs) == 2
        assert all(r.id for r in recs)
        # Stable, content-addressed IDs: re-running with the same body +
        # on-disk state produces the same IDs (LLM and deterministic).
        recs2 = collect_detail_quality_findings(
            plan_path,
            step,
            repo_root=tmp_path,
            plan_name="orch",
            invoker=fake,
        )
        assert [r.id for r in recs2] == [r.id for r in recs]

    def test_no_claude_findings_for_none_marker(self, tmp_path: Path) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        _seed_step1_detail_file(tmp_path)
        update_step_detail_field(
            plan_path, 1, "plan-details/orch/01-wire-up-renderer.md"
        )
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)

        recs = collect_detail_quality_findings(
            plan_path,
            step,
            repo_root=tmp_path,
            plan_name="orch",
            invoker=lambda _p: _FINDINGS_BLOCK_NONE,
        )
        # ``_(none)_`` → no LLM findings; only deterministic ones (if any).
        assert [r for r in recs if r.source == "claude"] == []

    def test_quality_check_refuses_an_unsupported_detail_marker(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.detail_artifacts import (
            DetailFormatError,
            render_detail_format_version_marker,
        )

        plan_path = _write_orchestrator_plan(tmp_path)
        detail_path = _seed_step1_detail_file(tmp_path)
        detail_path.write_text(
            f"# Step\n{render_detail_format_version_marker(999)}\n\n"
            + _GOOD_BODY,
            encoding="utf-8",
        )
        update_step_detail_field(
            plan_path, 1, "plan-details/orch/01-wire-up-renderer.md"
        )
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)

        with pytest.raises(DetailFormatError):
            collect_detail_quality_findings(
                plan_path,
                step,
                repo_root=tmp_path,
                plan_name="orch",
                invoker=lambda _p: _FINDINGS_BLOCK_NONE,
            )

    def test_advisory_altitude_block_returns_detail_altitude_rec(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review import DETAIL_ALTITUDE_SOURCE

        plan_path = _write_orchestrator_plan(tmp_path)
        detail_path = _seed_step1_detail_file(tmp_path)
        detail_path.write_text(
            _ALTITUDE_REGRESSION_DETAIL_BODY, encoding="utf-8",
        )
        update_step_detail_field(
            plan_path, 1, "plan-details/orch/01-wire-up-renderer.md"
        )
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        response = (
            "## Advisory altitude findings\n\n"
            "- ALTITUDE: `build_prompt_cache_budget(max_tokens=4096, "
            "retry_ms=250)` reads as mandatory mechanics; demote it to an "
            "e.g. executor note while preserving the prompt cache budget "
            "constraint.\n\n"
            "## Findings\n\n"
            "_(none)_\n"
        )

        recs = collect_detail_quality_findings(
            plan_path,
            step,
            repo_root=tmp_path,
            plan_name="orch",
            invoker=lambda _p: response,
        )

        altitude = [r for r in recs if r.source == DETAIL_ALTITUDE_SOURCE]
        assert len(altitude) == 1
        assert altitude[0].severity == "info"
        assert altitude[0].step_id == step.id
        assert altitude[0].suggested_action is None
        assert "prompt cache budget" in altitude[0].body
        assert altitude[0].id.startswith(f"step{step.id}-detail-altitude-")

    def test_advisory_altitude_block_not_lifted_as_claude_finding(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        detail_path = _seed_step1_detail_file(tmp_path)
        detail_path.write_text(
            _ALTITUDE_REGRESSION_DETAIL_BODY, encoding="utf-8",
        )
        update_step_detail_field(
            plan_path, 1, "plan-details/orch/01-wire-up-renderer.md"
        )
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        response = (
            "## Advisory altitude findings\n\n"
            "- ALTITUDE: exhaustive prompt cache budget test roster reads "
            "mandatory; demote the list to examples.\n\n"
            "## Findings\n\n"
            "_(none)_\n"
        )

        recs = collect_detail_quality_findings(
            plan_path,
            step,
            repo_root=tmp_path,
            plan_name="orch",
            invoker=lambda _p: response,
        )

        assert [r for r in recs if r.source == "claude"] == []

    @pytest.mark.parametrize(
        "response",
        [
            (
                "## Advisory altitude findings\n\n"
                "- ALTITUDE: speculative helper name should become an e.g. "
                "note for the prompt cache budget.\n\n"
                "## Findings\n\n"
                "- MEDIUM: acceptance criterion is not CI-checkable\n"
            ),
            (
                "## Findings\n\n"
                "- MEDIUM: acceptance criterion is not CI-checkable\n\n"
                "## Advisory altitude findings\n\n"
                "- ALTITUDE: speculative helper name should become an e.g. "
                "note for the prompt cache budget.\n"
            ),
        ],
        ids=["advisory-before-findings", "advisory-after-findings"],
    )
    def test_misordered_advisory_block_never_leaks_into_findings(
        self, tmp_path: Path, response: str
    ) -> None:
        from plan_tool.review import DETAIL_ALTITUDE_SOURCE

        plan_path = _write_orchestrator_plan(tmp_path)
        detail_path = _seed_step1_detail_file(tmp_path)
        detail_path.write_text(
            _ALTITUDE_REGRESSION_DETAIL_BODY, encoding="utf-8",
        )
        update_step_detail_field(
            plan_path, 1, "plan-details/orch/01-wire-up-renderer.md"
        )
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)

        recs = collect_detail_quality_findings(
            plan_path,
            step,
            repo_root=tmp_path,
            plan_name="orch",
            invoker=lambda _p: response,
        )

        claude = [r for r in recs if r.source == "claude"]
        altitude = [r for r in recs if r.source == DETAIL_ALTITUDE_SOURCE]
        assert len(claude) == 1
        assert len(altitude) == 1
        assert "Advisory altitude findings" not in claude[0].body
        assert "ALTITUDE" not in claude[0].body
        assert "prompt cache budget" in altitude[0].body

    def test_merges_deterministic_grounding_findings(
        self, tmp_path: Path
    ) -> None:
        """A files-coherence near-miss in the detail body surfaces as a
        deterministic finding even when the LLM reports ``_(none)_`` —
        the supplement that makes the loop useful when the body reads
        cleanly but cites a path that only resembles a declared one."""
        plan_path = _write_orchestrator_plan(tmp_path)
        detail_path = _seed_step1_detail_file(tmp_path)
        detail_path.write_text(_DRIFTED_BODY, encoding="utf-8")
        update_step_detail_field(
            plan_path, 1, "plan-details/orch/01-wire-up-renderer.md"
        )
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)

        recs = collect_detail_quality_findings(
            plan_path,
            step,
            repo_root=tmp_path,
            plan_name="orch",
            invoker=lambda _p: _FINDINGS_BLOCK_NONE,
        )
        assert any(r.source == "files-coherence" for r in recs)
        # Deterministic grounding findings are scoped to this step.
        assert all(
            r.step_id == step.id
            for r in recs
            if r.source in _DETAIL_GROUNDING_SOURCES
        )

    def test_returns_empty_list_when_detail_body_missing(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        # ``step.detail`` is ``None`` (no pre-population, no
        # ``update_step_detail_field``) → collector short-circuits
        # before invoking claude.
        call_count = {"n": 0}

        def fake(_prompt: str) -> str:
            call_count["n"] += 1
            return _FINDINGS_BLOCK_TWO_OPEN

        recs = collect_detail_quality_findings(
            plan_path,
            step,
            repo_root=tmp_path,
            plan_name="orch",
            invoker=fake,
        )
        assert recs == []
        assert call_count["n"] == 0


# --- Step 5: change_type steers the Tests directive ----------------------


def _body_with_tests_section(tests_body: str) -> str:
    """A minimal detail body carrying a ``## Tests`` section with the
    given prose, plus the surrounding required headings so the parser
    sees a well-formed file."""
    return (
        "# Step 1 — Refactor the renderer\n\n"
        "## Summary\n\noverview\n\n"
        "## Table of Contents\n\n- [Tests](#tests)\n\n"
        "## Why\n\nreason\n\n"
        "## Files (creates vs edits)\n\n- `renderer.py`\n\n"
        "## Implementation\n\nwalkthrough\n\n"
        f"## Tests\n\n{tests_body}\n\n"
        "## Acceptance criteria\n\n- returns 42\n\n"
        "## Deferred\n\n- nothing\n"
    )


class TestFormatTestsDirective:
    """``_format_tests_directive`` is the single wording source."""

    def test_code_types_share_one_block(self) -> None:
        """Both code types get the *same* directive. The per-type ordering
        contract was withdrawn (BACKLOG #204) — a regression that reinstates
        a refactor-specific block fails here."""
        refactor = _format_tests_directive(ChangeType.REFACTOR)
        feature = _format_tests_directive(ChangeType.FEATURE)
        assert refactor and refactor == feature
        assert "green before" in refactor.lower()
        # Opens a sub-section within ## Tests, never a new output H2.
        assert "### " in refactor
        assert "\n## " not in refactor

    def test_no_ordering_contract_in_any_block(self) -> None:
        """The withdrawn contract's vocabulary must not reappear in any
        block — the check that survives the wording, not just the branch."""
        for ct in (ChangeType.REFACTOR, ChangeType.FEATURE, ChangeType.NON_CODE):
            lowered = _format_tests_directive(ct).lower()
            for banned in (
                "characterization",
                "before touching",
                "pass-unchanged",
                "test-creation order",
                "first",
            ):
                assert banned not in lowered, (
                    f"{ct} directive reintroduced withdrawn ordering term "
                    f"{banned!r} — see BACKLOG #204"
                )

    def test_non_code_block_is_verification_only(self) -> None:
        block = _format_tests_directive(ChangeType.NON_CODE)
        assert block
        assert "verification" in block.lower()
        assert block != _format_tests_directive(ChangeType.FEATURE)

    def test_none_returns_empty(self) -> None:
        assert _format_tests_directive(None) == ""


class TestRenderDetailPromptChangeTypeDirective:
    """``change_type`` steers the rendered ``## Tests`` directive."""

    def _step(self, tmp_path: Path, change_type) -> tuple:
        plan_path = _write_detail_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        step.change_type = change_type
        return plan, step

    def test_code_types_inject_the_same_directive(self, tmp_path: Path) -> None:
        plan, step = self._step(tmp_path, ChangeType.REFACTOR)
        refactor = render_detail_prompt(plan, step, repo_root=tmp_path)
        plan, step = self._step(tmp_path, ChangeType.FEATURE)
        feature = render_detail_prompt(plan, step, repo_root=tmp_path)
        for prompt in (refactor, feature):
            assert "### Tests for this step" in prompt
            assert "green before" in prompt.lower()
            # The withdrawn ordering contract must not reappear (BACKLOG #204).
            assert "### Test-creation order" not in prompt

    def test_non_code_injects_verification(self, tmp_path: Path) -> None:
        plan, step = self._step(tmp_path, ChangeType.NON_CODE)
        prompt = render_detail_prompt(plan, step, repo_root=tmp_path)
        assert "### Verification (non-code step)" in prompt
        assert "### Tests for this step" not in prompt

    def test_unclassified_zero_delta(self, tmp_path: Path) -> None:
        plan, step = self._step(tmp_path, None)
        a = render_detail_prompt(plan, step, repo_root=tmp_path)
        b = render_detail_prompt(plan, step, repo_root=tmp_path)
        assert a == b
        assert "### Tests for this step" not in a
        assert "### Verification (non-code step)" not in a

    def test_quality_prompt_carries_the_same_directive(
        self, tmp_path: Path
    ) -> None:
        plan, step = self._step(tmp_path, ChangeType.REFACTOR)
        prompt = render_detail_quality_prompt(
            plan, step, repo_root=tmp_path, detail_body=_GOOD_BODY
        )
        # Reviewer and author render from the one source.
        assert "### Tests for this step" in prompt
        assert "### Test-creation order" not in prompt

    def test_quality_prompt_unclassified_zero_delta(
        self, tmp_path: Path
    ) -> None:
        plan, step = self._step(tmp_path, None)
        prompt = render_detail_quality_prompt(
            plan, step, repo_root=tmp_path, detail_body=_GOOD_BODY
        )
        assert "### Tests for this step" not in prompt


_STRUCTURAL_BLOCK_MIXED = (
    "Review of the detail body.\n\n"
    "## Findings\n\n"
    "_(none)_\n\n"
    "## Structural findings\n\n"
    "- MIXED-STEP: the `Promise.all` parallelization preserves behavior "
    "but the auth removal changes the failure mode from throw to "
    "fail-soft; these must be two steps\n"
)


def test_detail_strip_and_kernel_share_one_regex() -> None:
    # The defensive strip in detail and the parse kernel in granularity must
    # read the SAME regex object — identity, not equality — so they can never
    # drift to two copies.
    import plan_tool.detail as detail_mod
    import plan_tool.granularity as granularity_mod

    assert detail_mod._STRUCTURAL_BLOCK_RE is granularity_mod._STRUCTURAL_BLOCK_RE


from plan_tool.detail import (  # noqa: E402
    _confirm_split,
    _migrate_downstream_details_after_split,
)
from plan_tool.split_safety import split_is_safe  # noqa: E402


def _plan_with_statuses(*statuses: StepStatus) -> Plan:
    return Plan(
        title="t",
        status=PlanStatus.PLANNING,
        priority=Priority.LOW,
        steps=[
            Step(id=i + 1, title=f"step {i + 1}", status=st)
            for i, st in enumerate(statuses)
        ],
    )


class TestSplitIsSafe:
    """The run-state gate: a split is unsafe iff a DONE step is at or after
    the target (its ``step N green`` commit + completion status is the durable
    id-keyed state a renumber orphans). A CURRENT step ("next runnable" after
    authoring, never green) renumbers cleanly, as does a parked
    (still-PENDING) step."""

    def test_all_pending_is_safe(self) -> None:
        plan = _plan_with_statuses(
            StepStatus.PENDING, StepStatus.PENDING, StepStatus.PENDING
        )
        assert split_is_safe(plan, 2) == (True, [])

    def test_downstream_done_blocks(self) -> None:
        plan = _plan_with_statuses(
            StepStatus.PENDING, StepStatus.PENDING, StepStatus.DONE
        )
        assert split_is_safe(plan, 2) == (False, [3])

    def test_target_done_blocks(self) -> None:
        plan = _plan_with_statuses(
            StepStatus.PENDING, StepStatus.DONE, StepStatus.PENDING
        )
        assert split_is_safe(plan, 2) == (False, [2])

    def test_unrun_current_target_is_safe(self) -> None:
        # The reported bug: a freshly-authored plan's `current` step must be
        # splittable — CURRENT is "next runnable", not "mid-execution".
        plan = _plan_with_statuses(
            StepStatus.DONE, StepStatus.CURRENT, StepStatus.PENDING
        )
        assert split_is_safe(plan, 2) == (True, [])

    def test_downstream_current_is_safe(self) -> None:
        # A downstream CURRENT step renumbers cleanly (never green → no state).
        plan = _plan_with_statuses(
            StepStatus.PENDING, StepStatus.PENDING, StepStatus.CURRENT
        )
        assert split_is_safe(plan, 2) == (True, [])

    def test_downstream_deferred_is_safe(self) -> None:
        # A parked (deferred) step is still PENDING — no run state, so it
        # renumbers cleanly and does not block a split.
        plan = _plan_with_statuses(
            StepStatus.PENDING, StepStatus.PENDING, StepStatus.PENDING
        )
        plan.steps[2].scope = StepScope.DEFERRED
        assert split_is_safe(plan, 2) == (True, [])

    def test_upstream_non_pending_is_safe(self) -> None:
        # A DONE/CURRENT step BEFORE the target keeps its id; doesn't block.
        plan = _plan_with_statuses(
            StepStatus.DONE, StepStatus.PENDING, StepStatus.PENDING
        )
        assert split_is_safe(plan, 2) == (True, [])


class TestMigrateDownstreamDetailsAfterSplit:
    """Renumber downstream detail files + repoint pointers after a split."""

    def _touch(self, repo_root: Path, rel: str) -> Path:
        p = repo_root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("body\n", encoding="utf-8")
        return p

    def test_renames_and_repoints_high_to_low_no_collision(
        self, tmp_path: Path
    ) -> None:
        # Pre-split: steps 3 and 4 detailed. Split target = 2 (shift=1) →
        # old 3→4, old 4→5. Done naively low→high, renaming 3→4 would clobber
        # 4's file; the helper must go high→low.
        self._touch(tmp_path, "plan-details/p/03-three.md")
        self._touch(tmp_path, "plan-details/p/04-four.md")
        # Post-split list as _apply_step_split would produce it: the renumbered
        # downstream steps still carry their OLD detail pointer.
        new_steps = [
            Step(id=1, title="one"),
            Step(id=2, title="refactor half"),  # replacement
            Step(id=3, title="feature half"),  # replacement
            Step(id=4, title="three", detail="plan-details/p/03-three.md"),
            Step(id=5, title="four", detail="plan-details/p/04-four.md"),
        ]
        _migrate_downstream_details_after_split(
            new_steps, repo_root=tmp_path, target_id=2, shift=1
        )
        assert (tmp_path / "plan-details/p/04-three.md").is_file()
        assert (tmp_path / "plan-details/p/05-four.md").is_file()
        assert not (tmp_path / "plan-details/p/03-three.md").exists()
        assert new_steps[3].detail == "plan-details/p/04-three.md"
        assert new_steps[4].detail == "plan-details/p/05-four.md"

    def test_rollback_restores_files_and_pointers(self, tmp_path: Path) -> None:
        # The journal the migration returns must put every rename back and
        # restore the pointer it repointed — the all-or-nothing guarantee
        # _migrate_and_write_split relies on when the plan write refuses.
        from plan_tool.detail import _rollback_detail_migration

        self._touch(tmp_path, "plan-details/p/03-three.md")
        self._touch(tmp_path, "plan-details/p/04-four.md")
        new_steps = [
            Step(id=1, title="one"),
            Step(id=2, title="refactor half"),
            Step(id=3, title="feature half"),
            Step(id=4, title="three", detail="plan-details/p/03-three.md"),
            Step(id=5, title="four", detail="plan-details/p/04-four.md"),
        ]
        journal = _migrate_downstream_details_after_split(
            new_steps, repo_root=tmp_path, target_id=2, shift=1
        )
        assert len(journal) == 2

        _rollback_detail_migration(journal)

        assert (tmp_path / "plan-details/p/03-three.md").is_file()
        assert (tmp_path / "plan-details/p/04-four.md").is_file()
        assert not (tmp_path / "plan-details/p/05-four.md").exists()
        assert new_steps[3].detail == "plan-details/p/03-three.md"
        assert new_steps[4].detail == "plan-details/p/04-four.md"

    def test_rollback_leaves_the_pointer_when_the_file_cannot_return(
        self, tmp_path: Path
    ) -> None:
        # The pointer follows the file: if the migrated file is gone, restoring
        # the pre-split pointer would just aim at a different missing path.
        from plan_tool.detail import _rollback_detail_migration

        self._touch(tmp_path, "plan-details/p/03-three.md")
        new_steps = [
            Step(id=1, title="one"),
            Step(id=2, title="refactor"),
            Step(id=3, title="feature"),
            Step(id=4, title="three", detail="plan-details/p/03-three.md"),
        ]
        journal = _migrate_downstream_details_after_split(
            new_steps, repo_root=tmp_path, target_id=2, shift=1
        )
        (tmp_path / "plan-details/p/04-three.md").unlink()

        _rollback_detail_migration(journal)

        assert new_steps[3].detail == "plan-details/p/04-three.md"

    def test_rollback_restores_a_pointer_only_migration(
        self, tmp_path: Path
    ) -> None:
        # No file on disk: the migration repoints without a move, and the
        # rollback must still undo the pointer.
        from plan_tool.detail import _rollback_detail_migration

        new_steps = [
            Step(id=1, title="one"),
            Step(id=2, title="refactor"),
            Step(id=3, title="feature"),
            Step(id=4, title="gone", detail="plan-details/p/03-gone.md"),
        ]
        journal = _migrate_downstream_details_after_split(
            new_steps, repo_root=tmp_path, target_id=2, shift=1
        )
        assert new_steps[3].detail == "plan-details/p/04-gone.md"

        _rollback_detail_migration(journal)

        assert new_steps[3].detail == "plan-details/p/03-gone.md"

    def test_slug_drift_swaps_prefix_only(self, tmp_path: Path) -> None:
        # File slug doesn't match the current title's slug (title was edited).
        # The prefix must still swap; the slug is preserved verbatim.
        self._touch(tmp_path, "plan-details/p/03-old-slug.md")
        new_steps = [
            Step(id=1, title="one"),
            Step(id=2, title="refactor"),
            Step(id=3, title="feature"),
            Step(id=4, title="renamed title", detail="plan-details/p/03-old-slug.md"),
        ]
        _migrate_downstream_details_after_split(
            new_steps, repo_root=tmp_path, target_id=2, shift=1
        )
        assert (tmp_path / "plan-details/p/04-old-slug.md").is_file()
        assert new_steps[3].detail == "plan-details/p/04-old-slug.md"

    def test_missing_file_repoints_without_crash(self, tmp_path: Path) -> None:
        new_steps = [
            Step(id=1, title="one"),
            Step(id=2, title="refactor"),
            Step(id=3, title="feature"),
            Step(id=4, title="gone", detail="plan-details/p/03-gone.md"),
        ]
        _migrate_downstream_details_after_split(
            new_steps, repo_root=tmp_path, target_id=2, shift=1
        )
        # No file existed to move, but the pointer still tracks the new id.
        assert new_steps[3].detail == "plan-details/p/04-gone.md"

    def test_stray_at_target_path_is_archived_not_clobbered(
        self, tmp_path: Path
    ) -> None:
        # Downstream step 3 (→4), but a stray file already occupies the exact
        # target path 04-three.md. The rename must not clobber it.
        self._touch(tmp_path, "plan-details/p/03-three.md")
        stray = tmp_path / "plan-details/p/04-three.md"
        stray.write_text("PRECIOUS\n", encoding="utf-8")
        new_steps = [
            Step(id=1, title="one"),
            Step(id=2, title="refactor"),
            Step(id=3, title="feature"),
            Step(id=4, title="three", detail="plan-details/p/03-three.md"),
        ]
        _migrate_downstream_details_after_split(
            new_steps, repo_root=tmp_path, target_id=2, shift=1
        )
        # The downstream file took the slot...
        assert (tmp_path / "plan-details/p/04-three.md").read_text(
            encoding="utf-8"
        ) == "body\n"
        # ...and the stray was preserved in archive/, not overwritten.
        archived = list(
            (tmp_path / "plan-details/p/archive").glob("04-three.*.md")
        )
        assert len(archived) == 1
        assert archived[0].read_text(encoding="utf-8") == "PRECIOUS\n"

    def test_upstream_and_replacements_untouched(self, tmp_path: Path) -> None:
        self._touch(tmp_path, "plan-details/p/01-one.md")
        new_steps = [
            Step(id=1, title="one", detail="plan-details/p/01-one.md"),
            Step(id=2, title="refactor"),
            Step(id=3, title="feature"),
        ]
        _migrate_downstream_details_after_split(
            new_steps, repo_root=tmp_path, target_id=2, shift=1
        )
        # Upstream step 1 keeps its id, file, and pointer.
        assert new_steps[0].detail == "plan-details/p/01-one.md"
        assert (tmp_path / "plan-details/p/01-one.md").is_file()


class TestConfirmSplit:
    def test_non_tty_auto_declines(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        step = Step(id=2, title="mixed")
        reps = [Step(id=2, title="r"), Step(id=3, title="f")]
        # prompt_fn must not even be consulted when non-interactive.
        assert _confirm_split(
            lambda _p: pytest.fail("should not prompt"),
            step=step,
            replacements=reps,
        ) is False

    @pytest.mark.parametrize(
        "answer,expected",
        [("y", True), ("yes", True), ("", False), ("n", False)],
    )
    def test_tty_honors_answer(
        self, monkeypatch: pytest.MonkeyPatch, answer: str, expected: bool
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        step = Step(id=2, title="mixed")
        reps = [
            Step(id=2, title="r", change_type=ChangeType.REFACTOR),
            Step(id=3, title="f", change_type=ChangeType.FEATURE),
        ]
        assert _confirm_split(
            lambda _p: answer, step=step, replacements=reps
        ) is expected


class TestQualityFindingsIncludePurity:
    """The purity group rides the live ``collect_detail_quality_findings``
    merge and is not lifted into an apply-eligible ``claude`` rec."""

    def test_mixed_step_surfaces_and_defers_in_merged_findings(
        self, tmp_path: Path
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        detail_path = _detail_path_for(tmp_path, 1, "wire-up-renderer")
        detail_path.parent.mkdir(parents=True, exist_ok=True)
        detail_path.write_text(
            _body_with_tests_section("- `test_x` — characterization first"),
            encoding="utf-8",
        )
        update_step_detail_field(
            plan_path, 1, "plan-details/orch/01-wire-up-renderer.md"
        )
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        step.change_type = ChangeType.REFACTOR

        recs = collect_detail_quality_findings(
            plan_path,
            step,
            repo_root=tmp_path,
            plan_name="orch",
            invoker=lambda _p: _STRUCTURAL_BLOCK_MIXED,
        )
        purity = [r for r in recs if r.source == "granularity-split"]
        assert len(purity) == 1
        # It must NOT also appear as an apply-eligible ``claude`` rec.
        assert all(r.source != "claude" for r in recs)

    @pytest.mark.parametrize(
        "response",
        [
            # Structural block BEFORE findings (prompt's prescribed order).
            (
                "## Structural findings\n\n"
                "- MIXED-STEP: parallelization preserves behavior but the "
                "auth removal changes the failure mode\n\n"
                "## Findings\n\n"
                "- MEDIUM: implementation omits file:line citations\n"
            ),
            # Structural block AFTER findings (the dangerous order: the
            # ## Findings parser slices to end-of-string, so without the
            # strip the MIXED-STEP text leaks into the MEDIUM finding body).
            (
                "## Findings\n\n"
                "- MEDIUM: implementation omits file:line citations\n\n"
                "## Structural findings\n\n"
                "- MIXED-STEP: parallelization preserves behavior but the "
                "auth removal changes the failure mode\n"
            ),
        ],
        ids=["structural-before-findings", "structural-after-findings"],
    )
    def test_structural_block_never_leaks_into_findings(
        self, tmp_path: Path, response: str
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        detail_path = _detail_path_for(tmp_path, 1, "wire-up-renderer")
        detail_path.parent.mkdir(parents=True, exist_ok=True)
        detail_path.write_text(
            _body_with_tests_section("- `test_x` — characterization first"),
            encoding="utf-8",
        )
        update_step_detail_field(
            plan_path, 1, "plan-details/orch/01-wire-up-renderer.md"
        )
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        step.change_type = ChangeType.REFACTOR

        recs = collect_detail_quality_findings(
            plan_path,
            step,
            repo_root=tmp_path,
            plan_name="orch",
            invoker=lambda _p: response,
        )
        claude = [r for r in recs if r.source == "claude"]
        purity = [r for r in recs if r.source == "granularity-split"]
        # Exactly one real finding and one purity finding, cleanly separated.
        assert len(claude) == 1
        assert len(purity) == 1
        # The real finding's body must not have absorbed the structural block.
        assert "MIXED-STEP" not in claude[0].body
        assert "Structural findings" not in claude[0].body


_PURE_RESPONSE = "## Findings\n\n_(none)_\n"


class TestCachedPurityFindings:
    """``_cached_purity_findings`` — the shared purity cache boundary that the
    audit path reads through (skips Claude on a hit) and the detail loop writes
    through (always calls Claude, refreshes the cache)."""

    def _setup(self, tmp_path: Path, *, change_type=ChangeType.REFACTOR):
        plan_path = _write_orchestrator_plan(tmp_path)
        detail_path = _detail_path_for(tmp_path, 1, "wire-up-renderer")
        detail_path.parent.mkdir(parents=True, exist_ok=True)
        detail_path.write_text(
            _body_with_tests_section("- `test_x` — characterization first"),
            encoding="utf-8",
        )
        update_step_detail_field(
            plan_path, 1, "plan-details/orch/01-wire-up-renderer.md"
        )
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        step.change_type = change_type
        return plan_path, plan, step

    def _seed(self, tmp_path, plan_path, plan, step, findings):
        from plan_tool.fingerprint import compute_purity_cache_key
        from plan_tool.purity_cache import (
            PurityCache,
            PurityCacheEntry,
            purity_cache_path,
            save_purity_cache,
        )

        key, comps = compute_purity_cache_key(plan, plan_path, step, tmp_path)
        entry = PurityCacheEntry(
            step_id=step.id,
            cache_key=key,
            detail_hash=comps.detail_hash,
            all_files_fingerprint=comps.all_files_fingerprint,
            change_type=comps.change_type,
            depends_on=list(comps.depends_on),
            purity_verdict_logic_version=comps.logic_version,
            detail_relpath=step.detail,
            findings=findings,
            impl_tests_text="seed",
            checked_at="2026-07-18T00:00:00Z",
        )
        save_purity_cache(
            purity_cache_path(tmp_path, _plan_slug(plan_path)),
            PurityCache(
                plan_slug=_plan_slug(plan_path), entries={step.id: entry}
            ),
        )
        return key

    @staticmethod
    def _mixed_rec(step_id: int = 1):
        from plan_tool.review import Recommendation

        return Recommendation(
            id=f"granularity-split-{step_id}",
            source="granularity-split",
            severity="medium",
            step_id=step_id,
            title="mixed refactor + feature",
            body="mixes a behavior-preserving refactor with new behavior",
        )

    @staticmethod
    def _counting(response: str):
        calls: list[str] = []

        def inv(prompt: str) -> str:
            calls.append(prompt)
            return response

        return inv, calls

    def _load_entry(self, tmp_path, plan_path, step_id: int = 1):
        from plan_tool.purity_cache import load_purity_cache, purity_cache_path

        cache = load_purity_cache(
            purity_cache_path(tmp_path, _plan_slug(plan_path))
        )
        return cache.entries.get(step_id)

    def test_purity_cache_read_through_hit_skips_claude(
        self, tmp_path: Path
    ) -> None:
        plan_path, plan, step = self._setup(tmp_path)
        cached = self._mixed_rec()
        self._seed(tmp_path, plan_path, plan, step, [cached])
        inv, calls = self._counting(_PURE_RESPONSE)
        recs = _cached_purity_findings(
            plan_path, step, repo_root=tmp_path, plan_name="orch",
            invoker=inv, read_through=True,
        )
        assert calls == []  # served from cache — no Claude call
        purity = [r for r in recs if r.source == "granularity-split"]
        assert len(purity) == 1
        assert purity[0].purity_verdict_provenance == "exact-cache"
        assert self._load_entry(tmp_path, plan_path).findings == [cached]

    def test_live_purity_verdict_is_fresh_without_mutating_cache_baseline(
        self, tmp_path: Path
    ) -> None:
        plan_path, plan, step = self._setup(tmp_path)
        inv, _ = self._counting(_STRUCTURAL_BLOCK_MIXED)

        recs = _cached_purity_findings(
            plan_path, step, repo_root=tmp_path, plan_name="orch",
            invoker=inv, read_through=True,
        )

        purity = [r for r in recs if r.source == "granularity-split"]
        assert len(purity) == 1
        assert purity[0].purity_verdict_provenance == "fresh"
        baseline = self._load_entry(tmp_path, plan_path).findings
        assert len(baseline) == 1
        assert baseline[0].purity_verdict_provenance is None

    def test_purity_cache_write_through_always_calls_claude(
        self, tmp_path: Path
    ) -> None:
        plan_path, plan, step = self._setup(tmp_path)
        self._seed(tmp_path, plan_path, plan, step, [self._mixed_rec()])
        inv, calls = self._counting(_PURE_RESPONSE)
        _cached_purity_findings(
            plan_path, step, repo_root=tmp_path, plan_name="orch",
            invoker=inv, read_through=False,
        )
        assert len(calls) == 1  # write-through never skips, even on a hit
        # The cache was refreshed to the fresh (pure) verdict.
        assert self._load_entry(tmp_path, plan_path).findings == []

    def test_impl_tests_section_text_handles_heading_aliases(self) -> None:
        """Non-canonical tests headings on disk (## Testing, ## Test coverage)
        are still extracted, so a Tests-only rewrite under them is measured, not
        graded as 0% and reused (the code-review stale-hit finding). With no
        Implementation/Tests headings the result is empty — the grader's
        unmeasurable → genuine-miss fail-safe."""
        from plan_tool.detail import _impl_tests_section_text

        aliased = (
            "## Implementation\nimpl body\n"
            "## Testing\ntest body under a variant heading\n"
            "## Acceptance criteria\nx\n"
        )
        text = _impl_tests_section_text(aliased)
        assert "impl body" in text
        assert "test body under a variant heading" in text
        assert "tc body" in _impl_tests_section_text(
            "## Implementation\ni\n## Test coverage\ntc body\n"
        )
        assert _impl_tests_section_text("## Summary\nonly summary\n").strip() == ""

    def test_purity_cache_write_prunes_orphaned_entries(
        self, tmp_path: Path
    ) -> None:
        """The cache helper parses the plan, so it must pass its step ids to
        load_purity_cache — a write then prunes entries for steps the plan no
        longer has (guards the reconcile MEDIUM: pruning was dead because the
        caller never passed valid_step_ids)."""
        from plan_tool.purity_cache import (
            PurityCache,
            PurityCacheEntry,
            load_purity_cache,
            purity_cache_path,
            save_purity_cache,
        )

        plan_path, plan, step = self._setup(tmp_path)
        cache_file = purity_cache_path(tmp_path, _plan_slug(plan_path))
        # Seed an ORPHAN entry (step 99 is not in the plan) alongside no step-1 entry.
        orphan = PurityCacheEntry(
            step_id=99, cache_key="stale", detail_hash=None,
            all_files_fingerprint="x", change_type="feature", depends_on=[],
            purity_verdict_logic_version=1, detail_relpath="gone.md",
            findings=[], impl_tests_text="", checked_at="2026-07-18T00:00:00Z",
        )
        save_purity_cache(
            cache_file,
            PurityCache(plan_slug=_plan_slug(plan_path), entries={99: orphan}),
        )
        inv, _ = self._counting(_PURE_RESPONSE)
        _cached_purity_findings(
            plan_path, step, repo_root=tmp_path, plan_name="orch",
            invoker=inv, read_through=False,
        )
        after = load_purity_cache(cache_file).entries
        assert 99 not in after  # orphan pruned on the write's load
        assert 1 in after  # the real step's fresh entry landed

    def test_purity_cache_miss_calls_claude_and_writes_back(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.fingerprint import compute_purity_cache_key

        plan_path, plan, step = self._setup(tmp_path)
        inv, calls = self._counting(_STRUCTURAL_BLOCK_MIXED)
        _cached_purity_findings(
            plan_path, step, repo_root=tmp_path, plan_name="orch",
            invoker=inv, read_through=True,
        )
        assert len(calls) == 1
        key, _ = compute_purity_cache_key(plan, plan_path, step, tmp_path)
        entry = self._load_entry(tmp_path, plan_path)
        assert entry.cache_key == key
        assert [r.source for r in entry.findings] == ["granularity-split"]
        assert entry.change_type == step.change_type.value
        assert entry.depends_on == list(step.depends_on)
        assert "walkthrough" in entry.impl_tests_text  # Implementation text
        assert "characterization" in entry.impl_tests_text  # Tests text

    def test_read_through_never_renders_declared_risk_context(
        self, tmp_path: Path
    ) -> None:
        """The completeness-audit's purity check (read_through=True) must stay
        unaffected by a declared risk profile on an empty-cache miss (a real
        Claude call) — the risk-profile plan's explicit non-goal. The
        detail-authoring loop's write-through call is the only one that
        renders the advisory block. See
        ``test_read_through_never_reuses_a_risk_influenced_cache_entry``
        for the cache-*hit* half of this invariant — a write-through call
        populating the cache under a declared risk profile, then a later
        read-through call against that now-warm entry."""
        plan_path, plan, step = self._setup(tmp_path)
        _set_declared_risk_profile(
            plan_path, RiskProfile.HIGH, "Crosses an external boundary."
        )

        miss_inv, miss_calls = self._counting(_PURE_RESPONSE)
        _cached_purity_findings(
            plan_path, step, repo_root=tmp_path, plan_name="orch",
            invoker=miss_inv, read_through=True,
        )
        assert len(miss_calls) == 1
        assert "Declared risk profile" not in miss_calls[0]

        write_inv, write_calls = self._counting(_PURE_RESPONSE)
        _cached_purity_findings(
            plan_path, step, repo_root=tmp_path, plan_name="orch",
            invoker=write_inv, read_through=False,
        )
        assert len(write_calls) == 1
        assert "Declared risk profile" in write_calls[0]

    def test_read_through_never_reuses_a_risk_influenced_cache_entry(
        self, tmp_path: Path
    ) -> None:
        """A write-through call under a declared risk profile populates the
        SAME cache slot a later read-through call consults. Even though the
        cache key still matches (files/detail/change-type/depends-on are all
        unchanged), the entry must be unusable to read-through on both reuse
        paths — the strict hit check and the below-floor graded-reuse hook —
        because it was produced by a prompt read-through never renders.
        Regression for a gap the strict-hit-only fix left open: the key
        alone can't tell the two callers' prompts apart, since whether risk
        context reaches the prompt depends on the caller, not the plan."""
        plan_path, plan, step = self._setup(tmp_path)
        _set_declared_risk_profile(
            plan_path, RiskProfile.HIGH, "Crosses an external boundary."
        )

        write_inv, write_calls = self._counting(_STRUCTURAL_BLOCK_MIXED)
        _cached_purity_findings(
            plan_path, step, repo_root=tmp_path, plan_name="orch",
            invoker=write_inv, read_through=False,
        )
        assert len(write_calls) == 1
        assert "Declared risk profile" in write_calls[0]
        written = self._load_entry(tmp_path, plan_path)
        assert written.risk_context_rendered is True
        assert [r.source for r in written.findings] == ["granularity-split"]

        # A read-through call against this now-warm, risk-influenced entry
        # must NOT be served it — it must miss and call Claude itself, with
        # no risk context in that call's own prompt.
        read_inv, read_calls = self._counting(_PURE_RESPONSE)
        recs = _cached_purity_findings(
            plan_path, step, repo_root=tmp_path, plan_name="orch",
            invoker=read_inv, read_through=True,
        )
        assert len(read_calls) == 1  # not silently served the cached hit
        assert "Declared risk profile" not in read_calls[0]
        assert [r for r in recs if r.source == "granularity-split"] == []
        refreshed = self._load_entry(tmp_path, plan_path)
        assert refreshed.risk_context_rendered is False

        # The refreshed (context-free) entry now caches normally: a later
        # read-through call hits without calling Claude again.
        hit_inv, hit_calls = self._counting(_PURE_RESPONSE)
        _cached_purity_findings(
            plan_path, step, repo_root=tmp_path, plan_name="orch",
            invoker=hit_inv, read_through=True,
        )
        assert hit_calls == []

    def test_purity_cache_key_change_on_declared_file_forces_recheck(
        self, tmp_path: Path
    ) -> None:
        plan_path, plan, step = self._setup(tmp_path)
        self._seed(tmp_path, plan_path, plan, step, [self._mixed_rec()])
        # Change a declared ``files:`` file under an unchanged detail body.
        (tmp_path / "renderer.py").write_text(
            "def render(plan):\n    return 42\n", encoding="utf-8"
        )
        inv, calls = self._counting(_PURE_RESPONSE)
        _cached_purity_findings(
            plan_path, step, repo_root=tmp_path, plan_name="orch",
            invoker=inv, read_through=True,
        )
        assert len(calls) == 1  # key differs → miss → Claude

    def test_purity_cache_key_change_on_change_type_forces_recheck(
        self, tmp_path: Path
    ) -> None:
        plan_path, plan, step = self._setup(
            tmp_path, change_type=ChangeType.REFACTOR
        )
        self._seed(tmp_path, plan_path, plan, step, [self._mixed_rec()])
        step.change_type = ChangeType.FEATURE  # flip under unchanged detail+files
        inv, calls = self._counting(_PURE_RESPONSE)
        _cached_purity_findings(
            plan_path, step, repo_root=tmp_path, plan_name="orch",
            invoker=inv, read_through=True,
        )
        assert len(calls) == 1  # frontmatter is in the key → miss → Claude

    def test_purity_cache_empty_verdict_is_a_read_through_hit(
        self, tmp_path: Path
    ) -> None:
        plan_path, plan, step = self._setup(tmp_path)
        self._seed(tmp_path, plan_path, plan, step, [])  # confirmed pure
        inv, calls = self._counting(_PURE_RESPONSE)
        recs = _cached_purity_findings(
            plan_path, step, repo_root=tmp_path, plan_name="orch",
            invoker=inv, read_through=True,
        )
        assert calls == []  # empty verdict + matching key is a hit
        assert [r for r in recs if r.source == "granularity-split"] == []

    def test_purity_cache_key_change_on_creates_file_forces_recheck(
        self, tmp_path: Path
    ) -> None:
        plan_path, plan, step = self._setup(tmp_path)
        (tmp_path / "created.py").write_text("X = 1\n", encoding="utf-8")
        step.creates = ["created.py"]
        self._seed(tmp_path, plan_path, plan, step, [self._mixed_rec()])
        (tmp_path / "created.py").write_text("X = 2\n", encoding="utf-8")
        inv, calls = self._counting(_PURE_RESPONSE)
        _cached_purity_findings(
            plan_path, step, repo_root=tmp_path, plan_name="orch",
            invoker=inv, read_through=True,
        )
        assert len(calls) == 1  # key grounds on all_files, not only files:

    def test_purity_cache_failed_call_not_cached(self, tmp_path: Path) -> None:
        plan_path, plan, step = self._setup(tmp_path)
        inv, calls = self._counting("")  # failed invoke → empty reply
        recs = _cached_purity_findings(
            plan_path, step, repo_root=tmp_path, plan_name="orch",
            invoker=inv, read_through=True,
        )
        assert len(calls) == 1
        assert [r for r in recs if r.source == "granularity-split"] == []
        assert self._load_entry(tmp_path, plan_path) is None  # not cached
        # A subsequent read-through call misses and calls Claude again.
        inv2, calls2 = self._counting("")
        _cached_purity_findings(
            plan_path, step, repo_root=tmp_path, plan_name="orch",
            invoker=inv2, read_through=True,
        )
        assert len(calls2) == 1

    def test_purity_cache_return_status_propagates_succeeded(
        self, tmp_path: Path
    ) -> None:
        """``return_status=True`` surfaces the producer signal the audit needs
        to distinguish a failed scan from a clean empty verdict."""
        plan_path, plan, step = self._setup(tmp_path)
        inv, _ = self._counting("")  # empty → succeeded=False
        recs, succeeded = _cached_purity_findings(
            plan_path, step, repo_root=tmp_path, plan_name="orch",
            invoker=inv, read_through=True, return_status=True,
        )
        assert succeeded is False
        assert recs == [] or all(r.source != "granularity-split" for r in recs)
        # Hit path reports succeeded=True without calling Claude.
        inv_ok, _ = self._counting(_PURE_RESPONSE)
        _cached_purity_findings(
            plan_path, step, repo_root=tmp_path, plan_name="orch",
            invoker=inv_ok, read_through=False,
        )
        inv2, calls2 = self._counting(_PURE_RESPONSE)
        recs2, ok = _cached_purity_findings(
            plan_path, step, repo_root=tmp_path, plan_name="orch",
            invoker=inv2, read_through=True, return_status=True,
        )
        assert ok is True
        assert calls2 == []  # cache hit
        assert isinstance(recs2, list)

    def test_purity_cache_pure_success_is_cached(self, tmp_path: Path) -> None:
        plan_path, plan, step = self._setup(tmp_path)
        inv, calls = self._counting(_PURE_RESPONSE)  # genuinely pure success
        _cached_purity_findings(
            plan_path, step, repo_root=tmp_path, plan_name="orch",
            invoker=inv, read_through=True,
        )
        assert len(calls) == 1
        assert self._load_entry(tmp_path, plan_path).findings == []
        # A subsequent read-through call is a hit with no Claude call.
        inv2, calls2 = self._counting(_PURE_RESPONSE)
        recs = _cached_purity_findings(
            plan_path, step, repo_root=tmp_path, plan_name="orch",
            invoker=inv2, read_through=True,
        )
        assert calls2 == []
        assert [r for r in recs if r.source == "granularity-split"] == []

    def test_purity_cache_quiet_probe_not_cached(self, tmp_path: Path) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)  # no detail pointer → quiet probe
        inv, calls = self._counting(_PURE_RESPONSE)
        recs = _cached_purity_findings(
            plan_path, step, repo_root=tmp_path, plan_name="orch",
            invoker=inv, read_through=True,
        )
        assert calls == []  # short-circuits before the invoker
        assert recs == []
        assert self._load_entry(tmp_path, plan_path) is None

    def test_purity_cache_truncated_response_not_cached(
        self, tmp_path: Path
    ) -> None:
        plan_path, plan, step = self._setup(tmp_path)
        # Non-empty reply lacking the mandatory final ``## Findings`` heading.
        truncated = (
            "## Structural findings\n\n"
            "- MIXED-STEP: refactors the parser, then adds new caching\n"
        )
        inv, calls = self._counting(truncated)
        _cached_purity_findings(
            plan_path, step, repo_root=tmp_path, plan_name="orch",
            invoker=inv, read_through=True,
        )
        assert len(calls) == 1
        assert self._load_entry(tmp_path, plan_path) is None  # not cached
        # A subsequent read-through call re-checks.
        inv2, calls2 = self._counting(truncated)
        _cached_purity_findings(
            plan_path, step, repo_root=tmp_path, plan_name="orch",
            invoker=inv2, read_through=True,
        )
        assert len(calls2) == 1

    def test_purity_cache_pure_reply_is_cached(self, tmp_path: Path) -> None:
        # A well-formed reply that reached ``## Findings`` but emitted no
        # ``## Structural findings`` block caches an empty purity verdict.
        plan_path, plan, step = self._setup(tmp_path)
        pure = "## Findings\n\n- MEDIUM: acceptance criterion is not CI-checkable\n"
        inv, calls = self._counting(pure)
        _cached_purity_findings(
            plan_path, step, repo_root=tmp_path, plan_name="orch",
            invoker=inv, read_through=True,
        )
        assert len(calls) == 1
        assert self._load_entry(tmp_path, plan_path).findings == []
        inv2, calls2 = self._counting(pure)
        _cached_purity_findings(
            plan_path, step, repo_root=tmp_path, plan_name="orch",
            invoker=inv2, read_through=True,
        )
        assert calls2 == []  # hit — stops re-checking every audit

    def test_purity_cache_write_persists_detail_relpath(
        self, tmp_path: Path
    ) -> None:
        plan_path, plan, step = self._setup(tmp_path)
        inv, _calls = self._counting(_PURE_RESPONSE)
        _cached_purity_findings(
            plan_path, step, repo_root=tmp_path, plan_name="orch",
            invoker=inv, read_through=False,
        )
        assert self._load_entry(tmp_path, plan_path).detail_relpath == step.detail


# --- Step 6: detail lessons distillation redirect ------------------------

# Capture the real ``extract_and_append_detail_lessons`` reference at
# import time, BEFORE the autouse ``_stub_lessons_extraction`` fixture
# has a chance to monkeypatch the module attribute. Tests in
# ``TestExtractDetailLessonsRoutesAroundPlanTargets`` call this binding
# directly so the redirect logic actually runs end-to-end.
from plan_tool.detail import (  # noqa: E402
    extract_and_append_detail_lessons as _real_extract_and_append_detail_lessons,
)


class TestExtractDetailLessonsRoutesAroundPlanTargets:
    """Step 6: ``extract_and_append_detail_lessons`` quarantines bullets
    whose canonical sink is in the active plan's ``files:`` set.

    The auto-use ``_stub_lessons_extraction`` fixture short-circuits the
    module-attribute lookup of the extractor; these tests bypass the
    stub by calling the function reference captured at import time
    (``_real_extract_and_append_detail_lessons``), so the redirect
    logic runs against a deterministic JSON-returning fake invoker.
    """

    _LESSONS_JSON = (
        '{"general": [{"rule": "Routed general rule", "why": "g-why"}], '
        '"project": [{"rule": "Routed project fact", "why": "p-why"}]}'
    )

    def _call_extractor(
        self,
        tmp_path: Path,
        *,
        files: list[str],
    ) -> tuple[int, int]:
        """Invoke the real extractor against a plan with the given
        ``step.files`` declaration and a stub JSON invoker."""
        from plan_tool.parser import parse_plan

        plan_yaml = (
            "---\n"
            "title: Step 6 routing plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Touch lessons files\n"
            "    files:\n"
        )
        for f in files:
            plan_yaml += f"      - {f}\n"
        plan_yaml += (
            "    complexity: low\n"
            "    status: current\n"
            "---\n\n"
            "# Step 6 routing plan\n"
        )
        plan_path = tmp_path / "2-bug-backlog-drain.md"
        plan_path.write_text(plan_yaml, encoding="utf-8")
        # Deliberately do NOT seed declared files — the redirect test
        # cases assert that the canonical lessons sinks are absent
        # after the call when they didn't exist beforehand. The prompt
        # renderer handles missing files with a ``_(not on disk)_``
        # marker so the extractor still runs cleanly.

        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)

        def fake_invoker(_prompt: str) -> tuple[int, str]:
            return 0, self._LESSONS_JSON

        return _real_extract_and_append_detail_lessons(
            plan=plan,
            plan_path=plan_path,
            step=step,
            detail_body="# step body\n\nstub\n",
            repo_root=tmp_path,
            invoker=fake_invoker,
            reporter=NullReporter(),
        )

    def test_project_in_files_redirects_project_to_pending(
        self, tmp_path: Path
    ) -> None:
        from plan_tool import lessons as lessons_module

        n_general, n_project = self._call_extractor(
            tmp_path,
            files=[".plan-tool/lessons/project.md"],
        )
        assert (n_general, n_project) == (1, 1)
        # Canonical project sink was NOT touched.
        assert not lessons_module.project_path(tmp_path).exists()
        # Canonical general sink received the general bullet.
        general_body = lessons_module.general_path(tmp_path).read_text(
            encoding="utf-8"
        )
        assert "Routed general rule" in general_body
        pending = lessons_module.pending_lessons_path(
            tmp_path, "bug-backlog-drain"
        )
        assert pending.is_file()
        pending_body = pending.read_text(encoding="utf-8")
        project_section = pending_body[pending_body.index("## Project"):]
        assert "Routed project fact" in project_section

    def test_neither_in_files_writes_canonical_only(
        self, tmp_path: Path
    ) -> None:
        from plan_tool import lessons as lessons_module

        n_general, n_project = self._call_extractor(
            tmp_path,
            files=["foo.py"],
        )
        assert (n_general, n_project) == (1, 1)
        # Both canonical sinks exist and carry the bullets.
        assert "Routed general rule" in lessons_module.general_path(
            tmp_path
        ).read_text(encoding="utf-8")
        assert "Routed project fact" in lessons_module.project_path(
            tmp_path
        ).read_text(encoding="utf-8")
        # Pending directory was not created.
        pending_dir = lessons_module.pending_lessons_path(
            tmp_path, "bug-backlog-drain"
        ).parent
        assert not pending_dir.exists()

    def test_pending_path_uses_plan_slug_from_filename(
        self, tmp_path: Path
    ) -> None:
        from plan_tool import lessons as lessons_module

        # The helper's plan filename is ``2-bug-backlog-drain.md`` — the
        # digit prefix must be stripped to ``bug-backlog-drain`` per
        # ``_plan_slug``. The plan references the in-repo ``project.md``
        # sink, so the scope-guard routes the project bullet to pending;
        # the pending file lives under ``~/.plan-tool/lessons/pending/``.
        self._call_extractor(
            tmp_path,
            files=[".plan-tool/lessons/project.md"],
        )
        expected = (
            Path.home()
            / ".plan-tool"
            / "lessons"
            / "pending"
            / "bug-backlog-drain.md"
        )
        assert expected == lessons_module.pending_lessons_path(
            tmp_path, "bug-backlog-drain"
        )
        assert expected.is_file()


@pytest.mark.integration
class TestGenerateDetailIterationLoop:
    """End-to-end loop wiring with fake invoker + fake ``apply_finding``."""

    def test_disabled_budget_skips_iteration_loop(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Default ``IterativeBudget(enabled=False)`` is a hard no-op.

        The extracted helper must return without scanning or applying.
        """
        from plan_tool import detail as detail_module

        plan_path = _write_orchestrator_plan(tmp_path)

        def boom(*a, **kw):  # noqa: ARG001
            raise AssertionError(
                "apply_finding called with budget disabled"
            )

        monkeypatch.setattr(detail_module, "apply_finding", boom, raising=False)
        monkeypatch.setattr(
            detail_module, "_cached_purity_findings", boom, raising=False
        )

        plan = parse_plan(plan_path)
        outcome = detail_module._converge_run_grade_step_detail(
            step=plan.step_by_id(1),
            plan=plan,
            plan_path=plan_path,
            repo_root=tmp_path,
            plan_fingerprint=compute_plan_fingerprint(plan_path),
            plan_slug="orch",
            invoker=lambda _p: _GOOD_BODY,
            reporter=NullReporter(),
            run_logger=None,
            budget=_IterativeBudget(enabled=False),
            allow_drift=False,
            auto_reconcile_on_drift=True,
            collision_sidecar=True,
            triage=True,
            include_info=False,
            allow_split=False,
            prompt_fn=lambda _p: "",
            structural_seen=set(),
        )
        assert outcome.detail_quality_clean is False
        assert outcome.did_structural_split is False

    def test_iterates_until_converged(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Round 0 surfaces one finding, round 1 returns ``[]``: exits ``converged``."""
        from plan_tool import detail as detail_module

        plan_path = _write_orchestrator_plan(tmp_path)

        apply_calls = {"n": 0}

        def fake_apply(*a, **kw):  # noqa: ARG001
            apply_calls["n"] += 1
            return _stub_apply_result_detail()

        monkeypatch.setattr(detail_module, "apply_finding", fake_apply)

        collect_calls = {"n": 0}

        def fake_collect(*a, **kw):  # noqa: ARG001
            collect_calls["n"] += 1
            if collect_calls["n"] == 1:
                # Use _claude_recommendations to build a real one from a
                # findings block so the IDs / shape match production.
                from plan_tool.review import _claude_recommendations
                return _claude_recommendations(_FINDINGS_BLOCK_TWO_OPEN)[:1]
            return []

        monkeypatch.setattr(
            detail_module, "collect_detail_quality_findings", fake_collect
        )

        plan = parse_plan(plan_path)
        outcome = detail_module._converge_run_grade_step_detail(
            step=plan.step_by_id(1),
            plan=plan,
            plan_path=plan_path,
            repo_root=tmp_path,
            plan_fingerprint=compute_plan_fingerprint(plan_path),
            plan_slug="orch",
            invoker=lambda _p: _GOOD_BODY,
            reporter=NullReporter(),
            run_logger=None,
            budget=_IterativeBudget(enabled=True, max_iterations=3),
            allow_drift=False,
            auto_reconcile_on_drift=True,
            collision_sidecar=True,
            triage=True,
            include_info=False,
            allow_split=False,
            prompt_fn=lambda _p: "",
            structural_seen=set(),
        )
        assert outcome.detail_quality_clean is True
        # Exactly one apply pass for the single round-0 finding.
        assert apply_calls["n"] == 1
        # Round 0 (initial) + round 1 (post-apply).
        assert collect_calls["n"] == 2
        err = capsys.readouterr().err
        assert "detail iteration loop stopped" in err
        assert "converged" in err

    def test_lessons_capture_after_apply_then_converge(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Apply-then-empty must set clean via ``converged`` stop, not skip."""
        from plan_tool import detail as detail_module

        plan_path = _write_orchestrator_plan(tmp_path)
        lesson_calls: list[dict] = []

        def track_lessons(**kwargs: object) -> tuple[int, int]:
            lesson_calls.append(kwargs)
            return (0, 0)

        monkeypatch.setattr(
            detail_module, "extract_and_append_detail_lessons", track_lessons
        )
        monkeypatch.setattr(
            detail_module,
            "apply_finding",
            lambda *a, **kw: _stub_apply_result_detail(),
        )
        collect_calls = {"n": 0}

        def fake_collect(*a, **kw):  # noqa: ARG001
            collect_calls["n"] += 1
            if collect_calls["n"] == 1:
                from plan_tool.review import _claude_recommendations
                return _claude_recommendations(_FINDINGS_BLOCK_TWO_OPEN)[:1]
            return []

        monkeypatch.setattr(
            detail_module, "collect_detail_quality_findings", fake_collect
        )

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=True,
            lessons_invoker=lambda _p: (0, ""),
            budget=_IterativeBudget(enabled=True, max_iterations=3),
        )
        assert results[0].written is True
        assert collect_calls["n"] == 2
        assert len(lesson_calls) == 1

    def test_detail_apply_loop_hoists_and_forwards_telemetry_keys(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import detail as detail_module
        from plan_tool.review import Recommendation
        import plan_tool.review_persistence as persistence

        plan_path = _write_orchestrator_plan(tmp_path)
        findings = [
            Recommendation(
                id="quality-a", source="claude", severity="medium",
                step_id=1, title="quality A", body="fix A", anchor="tests",
            ),
            Recommendation(
                id="quality-b", source="claude", severity="medium",
                step_id=1, title="quality B", body="fix B", anchor=None,
            ),
        ]
        monkeypatch.setattr(
            detail_module,
            "collect_detail_quality_findings",
            lambda *a, **kw: findings,
        )
        fingerprint_calls: list[Path] = []
        monkeypatch.setattr(
            persistence,
            "compute_plan_fingerprint",
            lambda path: fingerprint_calls.append(path) or "shared-detail-fp",
        )
        apply_calls: list[dict] = []
        monkeypatch.setattr(
            detail_module,
            "apply_finding",
            lambda *a, **kw: apply_calls.append(kw) or _stub_apply_result_detail(),
        )

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            budget=_IterativeBudget(enabled=True, max_iterations=3),
        )

        assert results[0].written is True
        assert [call["anchor"] for call in apply_calls] == ["tests", ""]
        assert {call["plan_fingerprint"] for call in apply_calls} == {
            "shared-detail-fp"
        }
        assert all("record_verdict" not in call for call in apply_calls)
        assert fingerprint_calls == [plan_path]

    def test_detail_apply_loop_fingerprint_failure_is_best_effort(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import detail as detail_module
        from plan_tool.review import Recommendation
        import plan_tool.review_persistence as persistence

        plan_path = _write_orchestrator_plan(tmp_path)
        finding = Recommendation(
            id="quality-a", source="claude", severity="medium",
            step_id=1, title="quality A", body="fix A", anchor="tests",
        )
        monkeypatch.setattr(
            detail_module,
            "collect_detail_quality_findings",
            lambda *a, **kw: [finding],
        )

        def fail_fingerprint(_path):
            raise OSError("fingerprint unavailable")

        monkeypatch.setattr(
            persistence, "compute_plan_fingerprint", fail_fingerprint
        )
        apply_calls: list[dict] = []
        monkeypatch.setattr(
            detail_module,
            "apply_finding",
            lambda *a, **kw: apply_calls.append(kw) or _stub_apply_result_detail(),
        )
        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            budget=_IterativeBudget(enabled=True, max_iterations=3),
        )

        assert results[0].written is True
        assert [(call["anchor"], call["plan_fingerprint"]) for call in apply_calls] == [
            ("tests", "")
        ]

    def test_default_low_complexity_step_uses_one_iteration_cap(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool import detail as detail_module

        plan_path = _write_orchestrator_plan(tmp_path)
        seen_caps: list[int] = []

        def fake_collect(*a, **kw):  # noqa: ARG001
            seen_caps.append(kw["max_iterations"])
            return []

        monkeypatch.setattr(
            detail_module, "collect_detail_quality_findings", fake_collect
        )

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            budget=_IterativeBudget(enabled=True, max_iterations=3),
        )

        assert results[0].written is True
        assert seen_caps == [1]

    def test_stops_on_marginal_overlap(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Same finding-set across rounds → 100% overlap → ``marginal``."""
        from plan_tool import detail as detail_module

        plan_path = _write_orchestrator_plan(tmp_path)

        monkeypatch.setattr(
            detail_module,
            "apply_finding",
            lambda *a, **kw: _stub_apply_result_detail(),
        )

        from plan_tool.review import _claude_recommendations
        same_recs = _claude_recommendations(_FINDINGS_BLOCK_TWO_OPEN)

        monkeypatch.setattr(
            detail_module,
            "collect_detail_quality_findings",
            lambda *a, **kw: list(same_recs),
        )

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            budget=_IterativeBudget(enabled=True, max_iterations=5),
        )
        assert results[0].written is True
        err = capsys.readouterr().err
        assert "marginal" in err

    def test_stops_on_max_iterations(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """New finding IDs each round → exits after ``max_iterations``."""
        from plan_tool import detail as detail_module
        from plan_tool.review import Recommendation as _Rec

        plan_path = _write_orchestrator_plan(tmp_path)

        apply_calls = {"n": 0}

        def fake_apply(*a, **kw):  # noqa: ARG001
            apply_calls["n"] += 1
            return _stub_apply_result_detail()

        monkeypatch.setattr(detail_module, "apply_finding", fake_apply)

        # Round 0 = 1 finding; round 1 = 2 fresh findings; round 2 = 3
        # fresh findings. Disjoint ID sets keep ``is_marginal`` False so
        # the loop runs to ``max_iterations``.
        rounds = iter([
            [_Rec(id="round0-a", source="claude", severity="medium",
                  step_id=None, title="t", body="b0a",
                  suggested_action=None)],
            [_Rec(id="round1-a", source="claude", severity="medium",
                  step_id=None, title="t", body="b1a",
                  suggested_action=None),
             _Rec(id="round1-b", source="claude", severity="medium",
                  step_id=None, title="t", body="b1b",
                  suggested_action=None)],
            [_Rec(id="round2-a", source="claude", severity="medium",
                  step_id=None, title="t", body="b2a",
                  suggested_action=None),
             _Rec(id="round2-b", source="claude", severity="medium",
                  step_id=None, title="t", body="b2b",
                  suggested_action=None),
             _Rec(id="round2-c", source="claude", severity="medium",
                  step_id=None, title="t", body="b2c",
                  suggested_action=None)],
        ])

        def fake_collect(*a, **kw):  # noqa: ARG001
            return next(rounds)

        monkeypatch.setattr(
            detail_module, "collect_detail_quality_findings", fake_collect
        )

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            budget=_IterativeBudget(enabled=True, max_iterations=2),
        )
        assert results[0].written is True
        # Apply pass per finding across rounds 1 and 2:
        # round 1 applies round-0 findings (1), round 2 applies round-1
        # findings (2) → 3 total apply_finding calls.
        assert apply_calls["n"] == 1 + 2
        err = capsys.readouterr().err
        assert "max_iterations" in err

    def test_dedup_dispatches_each_finding_once(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A finding that re-surfaces across scans (apply didn't resolve it) is
        dispatched to ``apply_finding`` exactly ONCE, not re-applied every round
        (#74 dedup lever). The set grows each round so the loop keeps iterating
        (not stalled) — yet the persistent finding is never re-dispatched."""
        from plan_tool import detail as detail_module
        from plan_tool.review import Recommendation as _Rec

        plan_path = _write_orchestrator_plan(tmp_path)

        # Count apply dispatches per finding body.
        applied_bodies: list[str] = []

        def fake_apply(*a, **kw):  # noqa: ARG001
            applied_bodies.append(kw.get("finding_body", ""))
            return _stub_apply_result_detail()

        monkeypatch.setattr(detail_module, "apply_finding", fake_apply)

        def _rec(rid: str, body: str) -> "_Rec":
            return _Rec(id=rid, source="claude", severity="medium",
                        step_id=None, title="t", body=body,
                        suggested_action=None)

        # "persistent-a" appears in every scan (its apply never resolves it),
        # but each rescan also churns in enough *fresh* findings that the
        # persistent one stays under the 0.5 marginal-overlap threshold — so the
        # loop keeps iterating across multiple apply rounds instead of
        # stall-halting after the first. Each round applies the fresh findings;
        # persistent-a must be dispatched only on the first round it appears.
        rounds = [
            [_rec("persistent-a", "bA")],
            [_rec("persistent-a", "bA"), _rec("r1-b", "bB"),
             _rec("r1-c", "bC"), _rec("r1-d", "bD")],
            [_rec("persistent-a", "bA"), _rec("r2-e", "bE"),
             _rec("r2-f", "bF"), _rec("r2-g", "bG")],
            [_rec("persistent-a", "bA"), _rec("r3-h", "bH"),
             _rec("r3-i", "bI"), _rec("r3-j", "bJ")],
        ]
        scan_n = {"i": 0}

        def fake_collect(*a, **kw):  # noqa: ARG001
            i = min(scan_n["i"], len(rounds) - 1)
            scan_n["i"] += 1
            return rounds[i]

        monkeypatch.setattr(
            detail_module, "collect_detail_quality_findings", fake_collect
        )

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            budget=_IterativeBudget(enabled=True, max_iterations=5),
        )
        assert results[0].written is True
        # persistent-a re-surfaces in every scan but is dispatched exactly ONCE;
        # without dedup it would be re-applied on each round it appears in.
        assert sum(body.endswith("bA") for body in applied_bodies) == 1
        assert all("confidence: limited" in body for body in applied_bodies)
        # The loop genuinely ran multiple apply rounds (so dedup mattered):
        # at least one later-round fresh finding was also dispatched.
        assert len(applied_bodies) >= 4

    def test_stops_on_deadline_exceeded(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``budget_seconds=0`` halts before iter-1 apply runs."""
        from plan_tool import detail as detail_module
        from plan_tool.review import _claude_recommendations

        plan_path = _write_orchestrator_plan(tmp_path)

        apply_calls = {"n": 0}

        def fake_apply(*a, **kw):  # noqa: ARG001
            apply_calls["n"] += 1
            return _stub_apply_result_detail()

        monkeypatch.setattr(detail_module, "apply_finding", fake_apply)
        monkeypatch.setattr(
            detail_module,
            "collect_detail_quality_findings",
            lambda *a, **kw: _claude_recommendations(_FINDINGS_BLOCK_TWO_OPEN),
        )

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            budget=_IterativeBudget(
                enabled=True, max_iterations=3, budget_seconds=0
            ),
        )
        assert results[0].written is True
        # ``should_continue`` evaluates ``now - started >= 0`` on the
        # first check post-initial-collect, so no apply pass fires.
        assert apply_calls["n"] == 0
        err = capsys.readouterr().err
        assert "deadline_exceeded" in err

    def test_iteration_loop_lessons_redirect_when_project_in_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Step 6 redirect survives the iteration-loop wrapper.

        A plan whose step declares the canonical project lessons sink
        in ``files:`` must NOT write distilled bullets into that sink
        — even when running through the full ``generate_detail``
        path with ``extract_lessons=True``. Pins the iteration-surface
        contract for the per-bucket routing in
        ``extract_and_append_detail_lessons``.
        """
        from plan_tool import detail as detail_module
        from plan_tool import lessons as lessons_module

        # Override the autouse ``_stub_lessons_extraction`` fixture so
        # the real extractor runs against the fake invoker below.
        monkeypatch.setattr(
            detail_module,
            "extract_and_append_detail_lessons",
            _real_extract_and_append_detail_lessons,
        )

        # Plan declares the canonical project lessons sink as the
        # step's only file. The fake invoker returns ``_GOOD_BODY`` for
        # the detail call; the fake lessons_invoker returns a JSON
        # payload the parser can lift into one general + one project
        # bullet.
        plan_yaml = (
            "---\n"
            "title: Step 6 iteration-loop redirect\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Touch the project lessons file\n"
            "    files:\n"
            "      - .plan-tool/lessons/project.md\n"
            "    complexity: low\n"
            "    status: current\n"
            "---\n\n"
            "# Step 6 iteration-loop redirect\n"
        )
        plan_path = tmp_path / "9-iter-redirect.md"
        plan_path.write_text(plan_yaml, encoding="utf-8")

        lessons_json = (
            '{"general": [{"rule": "Iteration-loop redirect rule"}], '
            '"project": [{"rule": "Iteration-loop project rule"}]}'
        )

        def fake_lessons_invoker(_prompt: str) -> tuple[int, str]:
            return 0, lessons_json

        monkeypatch.setattr(
            detail_module,
            "collect_detail_quality_findings",
            lambda *a, **kw: [],
        )

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=True,
            lessons_invoker=fake_lessons_invoker,
            budget=_IterativeBudget(enabled=True, max_iterations=3),
        )
        assert len(results) == 1
        assert results[0].written is True

        # Canonical project sink is untouched (it didn't exist before
        # the call and still doesn't after).
        assert not lessons_module.project_path(tmp_path).exists()
        # Canonical general sink received the general bullet
        # (general lives outside the repo and is never in files:).
        assert "Iteration-loop redirect rule" in lessons_module.general_path(
            tmp_path
        ).read_text(encoding="utf-8")
        # Pending file carries the redirected project bullet.
        pending = lessons_module.pending_lessons_path(
            tmp_path, "iter-redirect"
        )
        assert pending.is_file()
        assert "Iteration-loop project rule" in pending.read_text(
            encoding="utf-8"
        )

    def test_generate_detail_loop_writes_through_and_still_calls_claude(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A pre-seeded matching entry must not let the write-through loop skip
        the purity Claude call — it always calls the producer and refreshes."""
        from plan_tool import detail as detail_module
        from plan_tool.purity_cache import (
            PurityCache,
            PurityCacheEntry,
            load_purity_cache,
            purity_cache_path,
            save_purity_cache,
        )

        plan_path = _write_orchestrator_plan(tmp_path)
        seeded = PurityCacheEntry(
            step_id=1,
            cache_key="stale-key",
            detail_hash=None,
            all_files_fingerprint="x",
            change_type="refactor",
            depends_on=[],
            purity_verdict_logic_version=1,
            detail_relpath="plan-details/orch/01-wire-up-renderer.md",
            findings=[],
            impl_tests_text="",
            checked_at="2026-07-18T00:00:00Z",
        )
        save_purity_cache(
            purity_cache_path(tmp_path, "orch"),
            PurityCache(plan_slug="orch", entries={1: seeded}),
        )

        collect_calls = {"n": 0}

        def fake_collect(*a, **kw):  # noqa: ARG001
            collect_calls["n"] += 1
            return []  # converge immediately

        monkeypatch.setattr(
            detail_module, "collect_detail_quality_findings", fake_collect
        )

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            budget=_IterativeBudget(enabled=True, max_iterations=3),
        )
        assert results[0].written is True
        assert collect_calls["n"] >= 1  # write-through called the producer
        # The cache was refreshed off the stale seed to a fresh entry.
        refreshed = load_purity_cache(
            purity_cache_path(tmp_path, "orch")
        ).entries[1]
        assert refreshed.cache_key != "stale-key"


# --- Step 7: in-loop BLOCKED-STRUCTURAL (trigger 2) escalation ----------


def _blocked_structural_apply_result(pre_snapshot=None) -> _ApplyFindingResult:
    """``ApplyFindingResult`` carrying the trigger-2 verdict."""
    return _ApplyFindingResult(
        step_id=1,
        exit_code=0,
        verdict="BLOCKED-STRUCTURAL",
        summary="",
        diff_text="",
        pre_snapshot=pre_snapshot if pre_snapshot is not None else {},
        stdout="",
    )


def _apply_result_with_verdict(verdict: str) -> _ApplyFindingResult:
    return _ApplyFindingResult(
        step_id=1,
        exit_code=0,
        verdict=verdict,
        summary="",
        diff_text="",
        pre_snapshot={},
        stdout="",
    )


def _structural_split_rec(step_id: int = 1):
    """A ``structural-split`` recommendation the bridge surfaces."""
    from plan_tool.review import Recommendation, _make_rec_id

    return Recommendation(
        id=_make_rec_id(
            step_id, "structural-split", f"structural-split:{step_id}"
        ),
        source="structural-split",
        severity="medium",
        step_id=step_id,
        title=f"Step {step_id} mixes refactor + feature — split it",
        body="The only correct fix is to split it into two type-pure steps.",
        suggested_action=(
            f'plan-tool split <plan> --step {step_id} --into "R" --into "F"'
        ),
    )


def _finding_once_collect(monkeypatch, detail_module):
    """Patch ``collect_detail_quality_findings`` to surface one apply-eligible
    finding on the first call and none after, so the convergence loop applies
    exactly once before converging. Returns the call counter dict."""
    from plan_tool.review import _claude_recommendations

    calls = {"n": 0}

    def fake_collect(*a, **kw):  # noqa: ARG001
        calls["n"] += 1
        if calls["n"] == 1:
            return _claude_recommendations(_FINDINGS_BLOCK_TWO_OPEN)[:1]
        return []

    monkeypatch.setattr(
        detail_module, "collect_detail_quality_findings", fake_collect
    )
    return calls


def _trigger_2_context(detail_module, plan_path: Path, repo_root: Path):
    """Build the private Trigger 2 handoff used by recovery tests."""
    return detail_module._Trigger2SplitContext(
        plan_path=plan_path,
        repo_root=repo_root,
        invoker=lambda _prompt: _GOOD_BODY,
        reporter=NullReporter(),
        extract_lessons=False,
        lessons_invoker=None,
        foundational_invoker=None,
        strict_check=False,
        equivalence_invoker=None,
        prompt_fn=lambda _message: "n",
        run_logger=None,
        budget=_IterativeBudget(enabled=True, max_iterations=3),
        allow_drift=False,
        auto_reconcile_on_drift=True,
        collision_sidecar=True,
        triage=True,
        include_info=False,
        plan_slug=_plan_slug(plan_path),
    )


@pytest.mark.integration
class TestInLoopStructuralEscalation:
    """``generate_detail``'s convergence loop routes a ``BLOCKED-STRUCTURAL``
    apply verdict (trigger 2) to ``escalate_to_split``: revert → dedup →
    escalate, breaking all three loops on an applied split and recommending
    (no mutation) otherwise."""

    def test_final_persistence_runs_after_phase_b_and_trigger_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Persist the final results only after both post-loop handlers."""
        from plan_tool import detail as detail_module

        plan_path = _write_concurrent_plan(tmp_path)
        lifecycle = detail_module._RunGradeDetailLifecycleResult(
            results=[],
            mixed_steps=[
                (2, _structural_split_rec(2)),
                (3, _structural_split_rec(3)),
            ],
            structural_split_ids={1},
            inloop_structural_recs=[],
        )
        monkeypatch.setattr(
            detail_module,
            "_run_grade_detail_lifecycle",
            lambda **_kwargs: lifecycle,
        )
        events: list[str] = []

        def phase_b_handler(results, **kwargs):
            assert results == []
            assert kwargs["mixed_steps"] == lifecycle.mixed_steps
            assert kwargs["applied_in_loop_split_ids"] == {1}
            events.extend(["phase-b recovery", "phase-b report"])
            return [
                DetailResult(
                    step_id=2,
                    output_path=tmp_path / "phase-b.md",
                    written=False,
                )
            ]

        def trigger_2_handler(results, **kwargs):
            assert events == ["phase-b recovery", "phase-b report"]
            assert [result.step_id for result in results] == [2]
            assert kwargs["structural_split_ids"] == {1}
            assert kwargs["inloop_structural_recs"] == []
            events.append("trigger-2")
            return results

        def persist_final(results, **kwargs):
            assert events == ["phase-b recovery", "phase-b report", "trigger-2"]
            assert [result.step_id for result in results] == [2]
            assert kwargs["plan_path"] == plan_path
            assert kwargs["dry_run"] is False
            events.append("persistence")
            return results

        monkeypatch.setattr(
            detail_module,
            "_handle_phase_b_splits",
            phase_b_handler,
        )
        monkeypatch.setattr(
            detail_module,
            "_handle_trigger_2_splits",
            trigger_2_handler,
        )
        monkeypatch.setattr(
            detail_module,
            "_persist_final_detail_concepts",
            persist_final,
        )

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            invoker=lambda _prompt: _GOOD_BODY,
            extract_lessons=False,
        )

        assert events == [
            "phase-b recovery",
            "phase-b report",
            "trigger-2",
            "persistence",
        ]
        assert [result.step_id for result in results] == [2]

    @pytest.mark.parametrize("reentry_phase", ["phase_b", "trigger_2"])
    def test_recursive_phase_b_and_trigger_2_reentry_keep_per_invocation_persistence(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        reentry_phase: str,
    ) -> None:
        """Nested authoring persists before its enclosing handler resumes."""
        from plan_tool import detail as detail_module

        plan_path = _write_orchestrator_plan(tmp_path)
        events: list[str] = []
        persisted_result_ids: list[tuple[int, ...]] = []

        def lifecycle(**kwargs):
            step = kwargs["prepared"].target_steps[0]
            return detail_module._RunGradeDetailLifecycleResult(
                results=[
                    DetailResult(
                        step_id=step.id,
                        output_path=tmp_path / f"{step.id}.md",
                        written=True,
                    )
                ],
                mixed_steps=[],
                structural_split_ids=set(),
                inloop_structural_recs=[],
            )

        def phase_b_handler(results, **_kwargs):
            nested = results[0].step_id == 2
            events.append(f"phase-b {'nested' if nested else 'outer'}")
            if reentry_phase == "phase_b" and not nested:
                child_results = generate_detail(
                    plan_path,
                    repo_root=tmp_path,
                    step_id=2,
                    invoker=lambda _prompt: _GOOD_BODY,
                    extract_lessons=False,
                )
                events.append("phase-b outer resumed")
                return [*results, *child_results]
            return results

        def trigger_2_handler(results, **_kwargs):
            nested = results[0].step_id == 2
            events.append(f"trigger-2 {'nested' if nested else 'outer'}")
            if reentry_phase == "trigger_2" and not nested:
                child_results = generate_detail(
                    plan_path,
                    repo_root=tmp_path,
                    step_id=2,
                    invoker=lambda _prompt: _GOOD_BODY,
                    extract_lessons=False,
                )
                events.append("trigger-2 outer resumed")
                return [*results, *child_results]
            return results

        def persist_final(results, **kwargs):
            assert kwargs["plan_path"] == plan_path
            persisted_result_ids.append(tuple(result.step_id for result in results))
            events.append(
                "persistence nested"
                if results[0].step_id == 2
                else "persistence outer"
            )
            return results

        monkeypatch.setattr(detail_module, "_run_grade_detail_lifecycle", lifecycle)
        monkeypatch.setattr(detail_module, "_handle_phase_b_splits", phase_b_handler)
        monkeypatch.setattr(
            detail_module, "_handle_trigger_2_splits", trigger_2_handler
        )
        monkeypatch.setattr(
            detail_module, "_persist_final_detail_concepts", persist_final
        )

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            invoker=lambda _prompt: _GOOD_BODY,
            extract_lessons=False,
        )

        assert persisted_result_ids == [(2,), (1, 2)]
        if reentry_phase == "phase_b":
            assert events == [
                "phase-b outer",
                "phase-b nested",
                "trigger-2 nested",
                "persistence nested",
                "phase-b outer resumed",
                "trigger-2 outer",
                "persistence outer",
            ]
        else:
            assert events == [
                "phase-b outer",
                "trigger-2 outer",
                "phase-b nested",
                "trigger-2 nested",
                "persistence nested",
                "trigger-2 outer resumed",
                "persistence outer",
            ]
        assert [result.step_id for result in results] == [1, 2]

    def test_blocked_structural_escalates_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import detail as detail_module
        from plan_tool.launcher import EscalateResult

        plan_path = _write_orchestrator_plan(tmp_path)
        monkeypatch.setattr(
            detail_module,
            "apply_finding",
            lambda *a, **kw: _blocked_structural_apply_result(),
        )
        _finding_once_collect(monkeypatch, detail_module)

        esc_calls: list[dict] = []

        def spy(_plan_path, **kwargs):
            esc_calls.append(kwargs)
            return EscalateResult(
                outcome="recommended",
                target_id=kwargs["step_id"],
                recommendation=_structural_split_rec(kwargs["step_id"]),
            )

        monkeypatch.setattr(detail_module, "escalate_to_split", spy)

        def my_prompt_fn(_msg):  # noqa: ANN001
            return "n"

        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            allow_split=True,
            prompt_fn=my_prompt_fn,
            budget=_IterativeBudget(enabled=True, max_iterations=3),
        )
        assert len(esc_calls) == 1
        assert esc_calls[0]["step_id"] == 1
        # The real flags are forwarded straight through, not forced.
        assert esc_calls[0]["allow_split"] is True
        assert esc_calls[0]["prompt_fn"] is my_prompt_fn

    def test_structural_seen_is_lifecycle_wide_across_two_steps(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """One structural id escalates once while both steps still converge."""
        from plan_tool import detail as detail_module
        from plan_tool.launcher import EscalateResult

        plan_path = _write_orchestrator_plan(tmp_path)
        finding = Recommendation(
            id="shared-structural-id",
            source="claude",
            severity="medium",
            step_id=None,
            title="split",
            body="split this step",
            suggested_action=None,
        )
        apply_calls = {"n": 0}
        escalate_calls = {"n": 0}

        def fake_apply(*_args, **_kwargs):
            apply_calls["n"] += 1
            return _blocked_structural_apply_result()

        def fake_escalate(_plan_path, **kwargs):
            escalate_calls["n"] += 1
            return EscalateResult(
                outcome="recommended",
                target_id=kwargs["step_id"],
                recommendation=_structural_split_rec(kwargs["step_id"]),
            )

        monkeypatch.setattr(detail_module, "apply_finding", fake_apply)
        monkeypatch.setattr(
            detail_module,
            "collect_detail_quality_findings",
            lambda *_args, **_kwargs: [finding],
        )
        monkeypatch.setattr(detail_module, "escalate_to_split", fake_escalate)

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            budget=_IterativeBudget(enabled=True, max_iterations=3),
        )

        assert apply_calls["n"] == 2
        assert escalate_calls["n"] == 1
        assert [result.written for result in results] == [True, True]

    def test_reverts_before_escalate(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import detail as detail_module
        from plan_tool.launcher import EscalateResult

        plan_path = _write_orchestrator_plan(tmp_path)

        def fake_apply(*a, **kw):  # noqa: ARG001
            # Capture the on-disk content, then leave a partial edit behind
            # and report the pre-edit snapshot — exactly what a real
            # BLOCKED-STRUCTURAL run leaves (apply_finding only reverts on a
            # non-zero exit).
            current = plan_path.read_text(encoding="utf-8")
            plan_path.write_text(
                current + "\nSENTINEL PARTIAL EDIT\n", encoding="utf-8"
            )
            return _blocked_structural_apply_result(
                pre_snapshot={plan_path: current}
            )

        monkeypatch.setattr(detail_module, "apply_finding", fake_apply)
        _finding_once_collect(monkeypatch, detail_module)

        seen: dict = {}

        def spy(_plan_path, **kwargs):
            seen["content"] = Path(_plan_path).read_text(encoding="utf-8")
            return EscalateResult(
                outcome="recommended",
                target_id=kwargs["step_id"],
                recommendation=_structural_split_rec(kwargs["step_id"]),
            )

        monkeypatch.setattr(detail_module, "escalate_to_split", spy)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            allow_split=True,
            budget=_IterativeBudget(enabled=True, max_iterations=3),
        )
        # The revert ran strictly before the escalate, so the bridge saw the
        # pre-edit (reverted) plan, not the half-applied one.
        assert "content" in seen
        assert "SENTINEL PARTIAL EDIT" not in seen["content"]

    def test_applied_split_breaks_all_loops(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import detail as detail_module
        from plan_tool.review import Recommendation as _Rec
        from plan_tool.launcher import EscalateResult

        plan_path = _write_orchestrator_plan(tmp_path)  # 2 steps
        run_logger = _make_run_logger(tmp_path)

        apply_calls = {"n": 0}

        def fake_apply(*a, **kw):  # noqa: ARG001
            apply_calls["n"] += 1
            return _blocked_structural_apply_result()

        monkeypatch.setattr(detail_module, "apply_finding", fake_apply)

        collect_calls = {"n": 0}

        def fake_collect(*a, **kw):  # noqa: ARG001
            collect_calls["n"] += 1
            if collect_calls["n"] == 1:
                # Two apply-eligible findings: the second must NOT reach
                # apply_finding once the first applies a split and breaks.
                return [
                    _Rec(id="bs-a", source="claude", severity="medium",
                         step_id=None, title="t", body="ba",
                         suggested_action=None),
                    _Rec(id="bs-b", source="claude", severity="medium",
                         step_id=None, title="t", body="bb",
                         suggested_action=None),
                ]
            return []

        monkeypatch.setattr(
            detail_module, "collect_detail_quality_findings", fake_collect
        )

        esc_calls = {"n": 0}

        def spy(_plan_path, **kwargs):
            esc_calls["n"] += 1
            return EscalateResult(outcome="applied", target_id=kwargs["step_id"])

        monkeypatch.setattr(detail_module, "escalate_to_split", spy)

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=None,  # both steps in scope — step 2 must not be reached
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            allow_split=True,
            run_logger=run_logger,
            budget=_IterativeBudget(enabled=True, max_iterations=3),
        )
        run_logger.run_end(outcome="success", rc=0)

        # One apply (the BLOCKED-STRUCTURAL one); the second open_apply rec and
        # step 2's main-loop pass never fire another apply.
        assert apply_calls["n"] == 1
        assert esc_calls["n"] == 1
        # The split step's phase ended structural-split, with no written result.
        _, events = _read_run_log_for_slug(tmp_path, "orch")
        struct = [
            e for e in events
            if e["event"] == "phase_end" and e.get("outcome") == "structural-split"
        ]
        assert len(struct) == 1
        assert struct[0]["step_id"] == 1
        assert all(not r.written for r in results if r.step_id == 1)

    def test_applied_split_reauthors_detail_less_halves(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import detail as detail_module
        from plan_tool.launcher import EscalateResult

        plan_path = tmp_path / "5-onestep.md"
        plan_path.write_text(
            "---\n"
            "title: One Step Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Mixed refactor and feature\n"
            "    files:\n"
            "      - renderer.py\n"
            "    complexity: low\n"
            "    status: current\n"
            "---\n\n"
            "# One Step Plan\n",
            encoding="utf-8",
        )
        (tmp_path / "renderer.py").write_text("X = 1\n", encoding="utf-8")

        monkeypatch.setattr(
            detail_module,
            "apply_finding",
            lambda *a, **kw: _blocked_structural_apply_result(),
        )
        _finding_once_collect(monkeypatch, detail_module)

        def split_stub(_plan_path, **kwargs):
            # Realize the renumber the real bridge would do: replace the
            # mixed step with two detail-less halves and drop the orphan
            # detail file authored for the original step.
            p = Path(_plan_path)
            orig = parse_plan(p).step_by_id(kwargs["step_id"])
            if orig.detail:
                (tmp_path / orig.detail).unlink(missing_ok=True)
            p.write_text(
                "---\n"
                "title: One Step Plan\n"
                "status: in-progress\n"
                "priority: medium\n"
                "steps:\n"
                "  - id: 1\n"
                "    title: Refactor the renderer\n"
                "    files:\n"
                "      - renderer.py\n"
                "    complexity: low\n"
                "    status: current\n"
                "  - id: 2\n"
                "    title: Add new rendering behavior\n"
                "    files:\n"
                "      - renderer.py\n"
                "    depends_on: [1]\n"
                "    complexity: low\n"
                "    status: pending\n"
                "---\n\n"
                "# One Step Plan\n",
                encoding="utf-8",
            )
            return EscalateResult(outcome="applied", target_id=kwargs["step_id"])

        monkeypatch.setattr(detail_module, "escalate_to_split", split_stub)

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            allow_split=True,
            budget=_IterativeBudget(enabled=True, max_iterations=3),
        )
        # Both renumbered halves were re-authored in this same run.
        written = {r.step_id for r in results if r.written}
        assert written == {1, 2}
        # The rebuilt region is slug-attributed to the new half titles.
        by_id = {r.step_id: Path(r.output_path).name for r in results}
        assert by_id[1].startswith("01-") and "refactor" in by_id[1]
        assert by_id[2].startswith("02-") and "rendering" in by_id[2]

    def test_trigger_2_reentry_targets_all_and_only_detail_less_steps(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Re-enter every unset post-split step without replacing details."""
        from plan_tool import detail as detail_module

        plan_path = tmp_path / "5-trigger-2-targets.md"
        plan_path.write_text(
            "---\n"
            "title: Trigger 2 Targets\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n    title: First new half\n    files:\n      - one.py\n"
            "  - id: 2\n    title: Existing detail\n    files:\n      - two.py\n"
            "    detail: plan-details/trigger-2-targets/02-existing.md\n"
            "  - id: 3\n    title: Later unset\n    files:\n      - three.py\n"
            "---\n\n# Trigger 2 Targets\n",
            encoding="utf-8",
        )
        for filename in ("one.py", "two.py", "three.py"):
            (tmp_path / filename).write_text("X = 1\n", encoding="utf-8")
        existing_detail = (
            tmp_path / "plan-details/trigger-2-targets/02-existing.md"
        )
        existing_detail.parent.mkdir(parents=True)
        existing_detail.write_text("# Existing\n", encoding="utf-8")

        reentered_ids: list[int] = []

        def failed_child(_path, **kwargs):
            step_id = kwargs["step_id"]
            reentered_ids.append(step_id)
            return [
                DetailResult(
                    step_id=step_id,
                    output_path=tmp_path / f"failed-{step_id}.md",
                    written=False,
                    skipped_reason="child authoring failed",
                )
            ]

        monkeypatch.setattr(detail_module, "generate_detail", failed_child)
        results = detail_module._handle_trigger_2_splits(
            [],
            structural_split_ids={1},
            inloop_structural_recs=[],
            context=_trigger_2_context(detail_module, plan_path, tmp_path),
        )

        assert reentered_ids == [1, 3]
        assert existing_detail.read_text(encoding="utf-8") == "# Existing\n"
        carried = next(result for result in results if result.step_id == 2)
        assert carried.written is False
        assert "carried through split" in (carried.skipped_reason or "")

    def test_trigger_2_reentry_preserves_budget_without_nested_split_or_half_commit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Keep parent convergence settings while suppressing child splitting."""
        from plan_tool import detail as detail_module

        plan_path = tmp_path / "5-trigger-2-budget.md"
        plan_path.write_text(
            "---\n"
            "title: Trigger 2 Budget\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n    title: New half\n    files:\n      - half.py\n"
            "---\n\n# Trigger 2 Budget\n",
            encoding="utf-8",
        )
        (tmp_path / "half.py").write_text("X = 1\n", encoding="utf-8")
        context = _trigger_2_context(detail_module, plan_path, tmp_path)
        calls: list[dict] = []

        def child(_path, **kwargs):
            calls.append(kwargs)
            return []

        monkeypatch.setattr(detail_module, "generate_detail", child)
        detail_module._handle_trigger_2_splits(
            [],
            structural_split_ids={1},
            inloop_structural_recs=[],
            context=context,
        )

        assert len(calls) == 1
        assert calls[0]["budget"] is context.budget
        assert calls[0]["resume"] is False
        assert calls[0]["allow_split"] is False
        assert "commit_step" not in calls[0]

    def test_trigger_2_rebuilds_renumbered_results_by_slug_key(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Attribute only matching slug keys to this recovery invocation."""
        from plan_tool import detail as detail_module

        plan_path = tmp_path / "5-trigger-2-rebuild.md"
        plan_path.write_text(
            "---\n"
            "title: Trigger 2 Rebuild\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n    title: Preserved step\n    files:\n      - one.py\n"
            "    detail: plan-details/trigger-2-rebuild/01-preserved.md\n"
            "  - id: 2\n    title: Written half\n    files:\n      - two.py\n"
            "  - id: 3\n    title: Carried step\n    files:\n      - three.py\n"
            "    detail: plan-details/trigger-2-rebuild/03-carried.md\n"
            "  - id: 4\n    title: Failed half\n    files:\n      - four.py\n"
            "---\n\n# Trigger 2 Rebuild\n",
            encoding="utf-8",
        )
        for filename in ("one.py", "two.py", "three.py", "four.py"):
            (tmp_path / filename).write_text("X = 1\n", encoding="utf-8")
        detail_dir = tmp_path / "plan-details/trigger-2-rebuild"
        detail_dir.mkdir(parents=True)
        preserved_path = detail_dir / "01-preserved.md"
        carried_path = detail_dir / "03-carried.md"
        written_path = detail_dir / "02-written-half.md"
        preserved_path.write_text("# Preserved\n", encoding="utf-8")
        carried_path.write_text("# Carried\n", encoding="utf-8")

        def child(path, **kwargs):
            if kwargs["step_id"] == 2:
                written_path.write_text("# Written\n", encoding="utf-8")
                update_step_detail_field(
                    path,
                    2,
                    "plan-details/trigger-2-rebuild/02-written-half.md",
                )
                return [
                    DetailResult(
                        step_id=2,
                        output_path=detail_dir / "07-written-half.md",
                        written=True,
                    )
                ]
            return [
                DetailResult(
                    step_id=4,
                    output_path=detail_dir / "04-failed-half.md",
                    written=False,
                    skipped_reason="concept deferral persistence failed: disk full",
                )
            ]

        monkeypatch.setattr(detail_module, "generate_detail", child)
        results = detail_module._handle_trigger_2_splits(
            [DetailResult(step_id=1, output_path=preserved_path, written=True)],
            structural_split_ids={2},
            inloop_structural_recs=[],
            context=_trigger_2_context(detail_module, plan_path, tmp_path),
        )

        by_id = {result.step_id: result for result in results}
        assert by_id[1].written is True
        assert by_id[2].written is True
        assert by_id[2].output_path == written_path
        assert by_id[3].written is False
        assert "carried through split" in (by_id[3].skipped_reason or "")
        assert by_id[4].skipped_reason == "concept deferral persistence failed: disk full"

    def test_seen_set_suppresses_reproposal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import detail as detail_module
        from plan_tool.review import Recommendation as _Rec
        from plan_tool.launcher import EscalateResult

        plan_path = _write_orchestrator_plan(tmp_path)
        monkeypatch.setattr(
            detail_module,
            "apply_finding",
            lambda *a, **kw: _blocked_structural_apply_result(),
        )

        # The SAME finding re-collects every round; the seen-set must keep
        # escalate_to_split from firing more than once across iterations.
        persistent = [
            _Rec(id="persistent-bs", source="claude", severity="medium",
                 step_id=None, title="t", body="b", suggested_action=None)
        ]
        monkeypatch.setattr(
            detail_module,
            "collect_detail_quality_findings",
            lambda *a, **kw: list(persistent),
        )

        esc_calls = {"n": 0}

        def spy(_plan_path, **kwargs):
            esc_calls["n"] += 1
            return EscalateResult(
                outcome="recommended",
                target_id=kwargs["step_id"],
                recommendation=_structural_split_rec(kwargs["step_id"]),
            )

        monkeypatch.setattr(detail_module, "escalate_to_split", spy)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            allow_split=True,
            budget=_IterativeBudget(enabled=True, max_iterations=3),
        )
        assert esc_calls["n"] == 1

    def test_recommend_only_collects_and_surfaces_rec(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool import detail as detail_module

        plan_path = _write_orchestrator_plan(tmp_path)
        before = plan_path.read_bytes()

        results = detail_module._handle_trigger_2_splits(
            [],
            structural_split_ids=set(),
            inloop_structural_recs=[_structural_split_rec(1)],
            context=_trigger_2_context(detail_module, plan_path, tmp_path),
        )

        assert results == []
        assert plan_path.read_bytes() == before
        err = capsys.readouterr().err
        assert "plan-tool split" in err
        assert err.count("structural splits for") == 1

    def test_unattended_recommends_no_mutation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import create as create_module
        from plan_tool import detail as detail_module
        from plan_tool.launcher import EscalateResult

        monkeypatch.setattr("sys.stdin.isatty", lambda: False)

        def boom_split(*_a, **_k):
            raise AssertionError("_apply_step_split must not run on recommend-only")

        monkeypatch.setattr(create_module, "_apply_step_split", boom_split)

        plan_path = _write_orchestrator_plan(tmp_path)
        before = [s.id for s in parse_plan(plan_path).steps]

        monkeypatch.setattr(
            detail_module,
            "apply_finding",
            lambda *a, **kw: _blocked_structural_apply_result(),
        )
        _finding_once_collect(monkeypatch, detail_module)
        monkeypatch.setattr(
            detail_module,
            "escalate_to_split",
            lambda _p, **kw: EscalateResult(
                outcome="recommended",
                target_id=kw["step_id"],
                recommendation=_structural_split_rec(kw["step_id"]),
            ),
        )

        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            allow_split=True,
            prompt_fn=None,
            budget=_IterativeBudget(enabled=True, max_iterations=3),
        )
        assert [s.id for s in parse_plan(plan_path).steps] == before

    @pytest.mark.parametrize("verdict", ["APPLIED", "BLOCKED"])
    def test_normal_verdict_never_escalates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, verdict: str
    ) -> None:
        from plan_tool import detail as detail_module

        plan_path = _write_orchestrator_plan(tmp_path)
        monkeypatch.setattr(
            detail_module,
            "apply_finding",
            lambda *a, **kw: _apply_result_with_verdict(verdict),
        )
        _finding_once_collect(monkeypatch, detail_module)

        def boom(*_a, **_k):
            raise AssertionError(
                f"escalate_to_split must not fire for verdict {verdict}"
            )

        monkeypatch.setattr(detail_module, "escalate_to_split", boom)
        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            allow_split=True,
            budget=_IterativeBudget(enabled=True, max_iterations=3),
        )
        assert results[0].written is True

    def test_real_apply_path_emits_blocked_structural(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import detail as detail_module
        from plan_tool import launcher as launcher_module
        from plan_tool.launcher import EscalateResult, _STRUCTURAL_VERDICT_OPTION

        plan_path = _write_orchestrator_plan(tmp_path)
        real_apply = launcher_module.apply_finding
        captured: dict = {"prompt": None}

        def fake_claude(prompt: str):
            captured["prompt"] = prompt
            # Emit the structural verdict ONLY when the prompt actually offered
            # it — so the test fails if allow_structural_verdict isn't set.
            if "BLOCKED-STRUCTURAL" in prompt:
                return 0, "## Verdict: BLOCKED-STRUCTURAL\n\n## Summary\n\nsplit it\n"
            return 0, "## Verdict: APPLIED\n\n## Summary\n\nok\n"

        def apply_wrapper(*args, **kwargs):
            kwargs["invoker"] = fake_claude
            return real_apply(*args, **kwargs)

        monkeypatch.setattr(detail_module, "apply_finding", apply_wrapper)
        _finding_once_collect(monkeypatch, detail_module)

        esc_calls: list[dict] = []

        def spy(_plan_path, **kwargs):
            esc_calls.append(kwargs)
            return EscalateResult(
                outcome="recommended",
                target_id=kwargs["step_id"],
                recommendation=_structural_split_rec(kwargs["step_id"]),
            )

        monkeypatch.setattr(detail_module, "escalate_to_split", spy)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            allow_split=True,
            budget=_IterativeBudget(enabled=True, max_iterations=3),
        )
        # The detail call set allow_structural_verdict=True, so the rendered
        # prompt offered the verdict; real parse_apply_verdict produced it; the
        # loop routed it to escalate_to_split.
        assert captured["prompt"] is not None
        assert _STRUCTURAL_VERDICT_OPTION in captured["prompt"]
        assert len(esc_calls) == 1
        assert esc_calls[0]["step_id"] == 1


# --- Step 6: cross-cutting iteration-surface invariants for cmd_detail ---


@pytest.mark.integration
class TestCrossCuttingIterationDetail:
    """Cross-cutting invariants over the detail-quality iteration loop.

    The internals (loop body, marginal-stop predicate, budget) are
    covered by ``TestGenerateDetailIterationLoop`` above (step 3).
    These tests pin the *contract* the user sees across subcommands:
    the marginal-stop predicate halts before the next round fires
    (so invoker call counts are bounded); exhaustion is a clean exit
    (``written=True`` is preserved on the ``DetailResult``); the
    disabled-budget default is byte-equivalent to omitting the
    kwarg; and the checkpoint discard contract from
    ``TestGenerateDetailResume`` still holds after a marginal stop.

    Step 3's hash (``_detail_step_input_hash``) is intentionally NOT
    iteration-keyed (the apply path edits the file in place; round
    N+1's review re-reads round N's output from disk), so the
    iteration-N cache-hit test from the create surface has no
    analogue here.
    """

    def test_detail_quality_findings_marginal_stop(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Identical findings on round 0 and round 1 → marginal halt.

        Cross-cutting bit: with ``max_iterations=5`` the loop would
        happily run all five rounds, but the marginal predicate must
        halt after iter-1 — so the apply pass fires exactly once (for
        the round-0 findings) and the second collect call (round 1) is
        the last one. Round 2's collect must not fire.
        """
        from plan_tool import detail as detail_module
        from plan_tool.review import _claude_recommendations

        plan_path = _write_orchestrator_plan(tmp_path)

        apply_calls = {"n": 0}

        def fake_apply(*a, **kw):  # noqa: ARG001
            apply_calls["n"] += 1
            return _stub_apply_result_detail()

        monkeypatch.setattr(detail_module, "apply_finding", fake_apply)

        same_recs = _claude_recommendations(_FINDINGS_BLOCK_TWO_OPEN)
        collect_calls = {"n": 0}

        def fake_collect(*a, **kw):  # noqa: ARG001
            collect_calls["n"] += 1
            return list(same_recs)

        monkeypatch.setattr(
            detail_module, "collect_detail_quality_findings", fake_collect
        )

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            budget=_IterativeBudget(enabled=True, max_iterations=5),
        )
        assert results[0].written is True
        # Round 0 collect + round 1 collect = 2. Round 2 collect must
        # not fire (marginal halt before iter-2's body).
        assert collect_calls["n"] == 2
        # Apply pass for the round-0 findings (2 recs).
        assert apply_calls["n"] == len(same_recs)
        err = capsys.readouterr().err
        assert "marginal" in err

    def test_deterministic_finding_surfaces_as_deferred(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A clean LLM review plus a real deterministic grounding finding
        makes the loop surface a deferred finding — not "converged (0
        findings)" — and never spends an apply call on the structural
        diagnostic. Exercises the real ``collect_step_grounding_findings``
        merge through the loop (the other loop tests mock the collector)."""
        from plan_tool import detail as detail_module

        plan_path = _write_orchestrator_plan(tmp_path)

        apply_calls = {"n": 0}

        def fake_apply(*a, **kw):  # noqa: ARG001
            apply_calls["n"] += 1
            return _stub_apply_result_detail()

        monkeypatch.setattr(detail_module, "apply_finding", fake_apply)

        def invoker(prompt: str) -> str:
            # Detail-quality critique → clean; detail authoring → the body.
            # ``_DRIFTED_BODY`` cites `src/renderer.py` against a declared
            # `renderer.py`, tripping a real files-coherence near-miss.
            if "Detail-quality review" in prompt:
                return _FINDINGS_BLOCK_NONE
            return _DRIFTED_BODY

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=invoker,
            extract_lessons=False,
            budget=_IterativeBudget(enabled=True, max_iterations=5),
        )

        assert results[0].written is True
        err = capsys.readouterr().err
        assert "triaged-deferred" in err
        assert "converged (0 findings" not in err
        # Structural diagnostics never cost an apply call.
        assert apply_calls["n"] == 0

    def test_advisory_altitude_findings_are_not_dispatched_to_apply_finding(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool import detail as detail_module
        from plan_tool.review import DETAIL_ALTITUDE_SOURCE, Recommendation

        plan_path = _write_orchestrator_plan(tmp_path)
        altitude = Recommendation(
            id="step1-detail-altitude-advisory",
            source=DETAIL_ALTITUDE_SOURCE,
            severity="info",
            step_id=1,
            title="demote helper mechanics",
            body=(
                "Speculative helper names for the prompt cache budget should "
                "be examples, not mandatory instructions."
            ),
        )

        apply_calls = {"n": 0}

        def fake_apply(*a, **kw):  # noqa: ARG001
            apply_calls["n"] += 1
            return _stub_apply_result_detail()

        monkeypatch.setattr(detail_module, "apply_finding", fake_apply)
        monkeypatch.setattr(
            detail_module,
            "collect_detail_quality_findings",
            lambda *a, **kw: [altitude],
        )

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _ALTITUDE_REGRESSION_DETAIL_BODY,
            extract_lessons=False,
            budget=_IterativeBudget(enabled=True, max_iterations=3),
            include_info=True,
        )

        assert results[0].written is True
        assert apply_calls["n"] == 0
        err = capsys.readouterr().err
        assert "triaged-deferred" in err
        assert "advisory detail-quality altitude issue" in err

    def test_persistent_deferred_finding_does_not_trigger_marginal(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A deferred (non-apply-eligible) finding that persists every
        round must not inflate ``is_marginal``. With a fresh apply-eligible
        finding each round, the loop keeps applying to ``max_iterations``
        instead of stopping early on the deferred finding's overlap.

        Pre-fix the deferred finding lived in the convergence id-set, so
        round 1's 50%-overlap fired ``marginal`` after a single apply."""
        from plan_tool import detail as detail_module
        from plan_tool.review import Recommendation as _Rec

        plan_path = _write_orchestrator_plan(tmp_path)

        apply_calls = {"n": 0}

        def fake_apply(*a, **kw):  # noqa: ARG001
            apply_calls["n"] += 1
            return _stub_apply_result_detail()

        monkeypatch.setattr(detail_module, "apply_finding", fake_apply)

        det = _Rec(
            id="det-1", source="files-coherence", severity="nit",
            step_id=1, title="path drift", body="path drift",
            suggested_action=None,
        )
        calls = {"n": 0}

        def fake_collect(*a, **kw):  # noqa: ARG001
            n = calls["n"]
            calls["n"] += 1
            # Fresh apply-eligible finding + the same persistent deferred one.
            llm = _Rec(
                id=f"llm-{n}", source="claude", severity="medium",
                step_id=None, title=f"fix {n}", body=f"fix {n}",
                suggested_action=None,
            )
            return [llm, det]

        monkeypatch.setattr(
            detail_module, "collect_detail_quality_findings", fake_collect
        )

        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            budget=_IterativeBudget(
                enabled=True, max_iterations=4, max_stall_rounds=0
            ),
        )

        err = capsys.readouterr().err
        assert "marginal" not in err
        assert apply_calls["n"] >= 3  # one fresh fix applied each round

    def test_repeated_deferred_block_collapses_to_delta_line(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The same deferred set across rounds prints in full once, then
        collapses to a single ``deferred findings unchanged`` line per
        repeat instead of re-emitting the whole per-finding block."""
        from plan_tool import detail as detail_module
        from plan_tool.review import Recommendation as _Rec

        plan_path = _write_orchestrator_plan(tmp_path)

        monkeypatch.setattr(
            detail_module,
            "apply_finding",
            lambda *a, **kw: _stub_apply_result_detail(),
        )

        det = _Rec(
            id="det-1", source="files-coherence", severity="nit",
            step_id=1, title="path drift", body="path drift",
            suggested_action=None,
        )
        calls = {"n": 0}

        def fake_collect(*a, **kw):  # noqa: ARG001
            n = calls["n"]
            calls["n"] += 1
            llm = _Rec(
                id=f"llm-{n}", source="claude", severity="medium",
                step_id=None, title=f"fix {n}", body=f"fix {n}",
                suggested_action=None,
            )
            return [llm, det]

        monkeypatch.setattr(
            detail_module, "collect_detail_quality_findings", fake_collect
        )

        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            budget=_IterativeBudget(
                enabled=True, max_iterations=4, max_stall_rounds=0
            ),
        )

        err = capsys.readouterr().err
        # Iter 1 prints the full block; the unchanged set on iters 2 and 3
        # each collapse to one delta line naming the prior iteration.
        assert "deferring 1 finding(s) by triage" in err
        assert "deferred findings unchanged from iter 1 (1: det-1)" in err
        assert "deferred findings unchanged from iter 2 (1: det-1)" in err
        # The full per-finding bullet appears once (iter 1), not per repeat.
        assert err.count("- det-1: path drift") == 1

    def test_detail_budget_exhaustion_keeps_written_true(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Exhausting the budget doesn't roll back the file write.

        Cross-cutting bit: the iteration loop runs *after* the durable
        write and plan-update are committed, so a budget-exhaustion
        exit leaves ``written=True`` on the result rather than
        retroactively flipping the step into the "skipped" branch.
        The on-disk detail file is still the durable artifact.
        """
        from plan_tool import detail as detail_module
        from plan_tool.review import Recommendation as _Rec

        plan_path = _write_orchestrator_plan(tmp_path)

        monkeypatch.setattr(
            detail_module,
            "apply_finding",
            lambda *a, **kw: _stub_apply_result_detail(),
        )

        # Always-fresh finding IDs → loop never converges or hits the
        # marginal predicate. With max_iterations=1 the second
        # should_continue check fires the "max_iterations" exit.
        rounds = iter([
            [_Rec(id="exh-0", source="claude", severity="medium",
                  step_id=None, title="t", body="b0",
                  suggested_action=None)],
            [_Rec(id="exh-1", source="claude", severity="medium",
                  step_id=None, title="t", body="b1",
                  suggested_action=None)],
        ])

        def fake_collect(*a, **kw):  # noqa: ARG001
            return next(rounds)

        monkeypatch.setattr(
            detail_module, "collect_detail_quality_findings", fake_collect
        )

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            budget=_IterativeBudget(enabled=True, max_iterations=1),
        )
        assert results[0].written is True
        # ``skipped_reason`` is the failure-marker field, untouched on
        # the success-with-exhaustion path.
        assert results[0].skipped_reason is None
        detail_path = _detail_path_for(tmp_path, 1, "wire-up-renderer")
        assert detail_path.is_file()
        err = capsys.readouterr().err
        assert "max_iterations" in err

    def test_disabled_budget_byte_equivalent_to_default(
        self, tmp_path: Path
    ) -> None:
        """``IterativeBudget(enabled=False)`` and the default kwarg
        produce byte-identical detail files.

        Cross-cutting bit: a regression that swaps the production
        default from ``IterativeBudget(enabled=False)`` to ``enabled=True``
        would inflate invoker counts even on the "default off" path —
        this test pins that the disabled-budget short-circuit is the
        only code path the default flag exercises.
        """
        # Two independent runs under different subdirectories so the
        # plan files don't collide.
        run_dirs: list[Path] = []
        for label in ("with_disabled", "default_kwarg"):
            run_dir = tmp_path / label
            run_dir.mkdir()
            plan_path = _write_orchestrator_plan(run_dir)
            kwargs = {
                "repo_root": run_dir,
                "step_id": 1,
                "invoker": lambda _p: _GOOD_BODY,
                "extract_lessons": False,
            }
            if label == "with_disabled":
                kwargs["budget"] = _IterativeBudget(enabled=False)
            results = generate_detail(plan_path, **kwargs)
            assert results[0].written is True
            run_dirs.append(run_dir)

        a = _detail_path_for(run_dirs[0], 1, "wire-up-renderer").read_bytes()
        b = _detail_path_for(run_dirs[1], 1, "wire-up-renderer").read_bytes()
        assert a == b

    def test_marginal_stop_does_not_leak_checkpoint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Marginal-stop is a success exit → checkpoint stays discarded.

        Mirrors ``TestGenerateDetailResume.test_first_run_writes_checkpoint_then_discards_it``
        but under the iteration loop. Without this pin, a future
        refactor that conflates "marginal" with "exhausted" (or worse,
        re-saves the checkpoint inside the loop body) would leak a
        ``detail-step-NN.json`` shard the next run would have to
        evict.
        """
        from plan_tool import detail as detail_module
        from plan_tool.review import _claude_recommendations

        plan_path = _write_orchestrator_plan(tmp_path)

        monkeypatch.setattr(
            detail_module,
            "apply_finding",
            lambda *a, **kw: _stub_apply_result_detail(),
        )
        same_recs = _claude_recommendations(_FINDINGS_BLOCK_TWO_OPEN)
        monkeypatch.setattr(
            detail_module,
            "collect_detail_quality_findings",
            lambda *a, **kw: list(same_recs),
        )

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            budget=_IterativeBudget(enabled=True, max_iterations=5),
        )
        assert results[0].written is True
        # Step 1's checkpoint must be gone post-success regardless of
        # whether the loop exited "converged" or "marginal".
        assert not _ckpt_path_for(tmp_path, 1).exists()


# --- Mid-iteration drift halt (task #33) ----------------------------------

@pytest.mark.integration
class TestGenerateDetailDriftHalt:
    """Pre/post-apply drift check in the per-step convergence helper.
    iteration loop. Mirrors the cmd_completeness pattern (task #30)."""

    def test_iterate_loop_reverts_parse_broken_apply(self) -> None:
        """Call-site contract: parse-breaking apply edits are reverted.

        The helper itself is covered in launcher/completeness tests; this
        guards the extracted detail loop against regressing back to leaving an
        unparseable plan on disk.
        """
        import inspect

        from plan_tool import detail as detail_module

        src = inspect.getsource(detail_module._converge_run_grade_step_detail)
        revert = "apply_reverted = revert_apply_if_parse_broken(apply_result)"
        assert revert in src
        assert src.index(revert) < src.index("run_logger.phase_end(", src.index(revert))
        assert '"reverted" if apply_reverted' in src
        assert "detail_parse_halted = True" in src
        assert "if detail_parse_halted:" in src

    def test_post_apply_drift_halts_loop_and_keeps_edits(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The apply mock advances the watched (step.files) file's
        mtime. Post-apply check fires; loop halts after exactly one
        apply call with ``DURING apply`` wording."""
        import os
        from plan_tool import detail as detail_module

        plan_path = _write_orchestrator_plan(tmp_path)
        watched = tmp_path / "renderer.py"

        apply_calls = {"n": 0}

        def fake_apply(*a, **kw):  # noqa: ARG001
            apply_calls["n"] += 1
            # Mutate watched content -- mtime advance alone no
            # longer triggers drift.
            watched.write_bytes(watched.read_bytes() + b"_drift")
            return _stub_apply_result_detail()

        monkeypatch.setattr(detail_module, "apply_finding", fake_apply)

        from plan_tool.review import _claude_recommendations
        monkeypatch.setattr(
            detail_module,
            "collect_detail_quality_findings",
            lambda *a, **kw: _claude_recommendations(
                _FINDINGS_BLOCK_TWO_OPEN
            )[:2],
        )

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            budget=_IterativeBudget(enabled=True, max_iterations=3),
            # Auto-reconcile would fire run_step → real claude
            # shell-out in tests that don't mock it. Opt out to keep
            # this test focused on the drift-halt path itself.
            auto_reconcile_on_drift=False,
        )
        assert results[0].written is True
        # First apply triggered drift; second apply was halted.
        assert apply_calls["n"] == 1
        err = capsys.readouterr().err
        assert "drift detected" in err
        assert "DURING apply" in err
        # drifted file is named alongside its owning
        # step. Proves generate_detail's drift-halt call site passes
        # `file_to_step` through. Step 1's title is "Wire up the
        # renderer" per ``_ORCHESTRATOR_PLAN``.
        assert "(step 1: Wire up the renderer)" in err

    def test_allow_drift_disables_halt(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``allow_drift=True`` skips the halt: both findings' applies
        run even though the apply mock advances the watched mtime.
        The legacy lock-release drift warning still fires at end."""
        import os
        from plan_tool import detail as detail_module

        plan_path = _write_orchestrator_plan(tmp_path)
        watched = tmp_path / "renderer.py"

        apply_calls = {"n": 0}

        def fake_apply(*a, **kw):  # noqa: ARG001
            apply_calls["n"] += 1
            # Mutate watched content -- mtime advance alone no
            # longer triggers drift.
            watched.write_bytes(watched.read_bytes() + b"_drift")
            return _stub_apply_result_detail()

        monkeypatch.setattr(detail_module, "apply_finding", fake_apply)

        from plan_tool.review import _claude_recommendations
        collect_calls = {"n": 0}

        def fake_collect(*a, **kw):  # noqa: ARG001
            collect_calls["n"] += 1
            if collect_calls["n"] == 1:
                return _claude_recommendations(_FINDINGS_BLOCK_TWO_OPEN)[:2]
            return []

        monkeypatch.setattr(
            detail_module,
            "collect_detail_quality_findings",
            fake_collect,
        )

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            budget=_IterativeBudget(enabled=True, max_iterations=3),
            allow_drift=True,
        )
        assert results[0].written is True
        # Both findings' applies ran -- no halt.
        assert apply_calls["n"] == 2
        err = capsys.readouterr().err
        assert "drift detected" not in err
        assert "DURING apply" not in err
        # Legacy lock-release drift warning still fires.
        assert "changed during" in err


# --- Step 2: style-helper routing for detail diagnostics -----------------


_TOOL_COLOR_PREFIX = style.DIM + "plan-tool:" + style.RESET + " "
_WARN_COLOR_PREFIX = style.BOLD_YELLOW + "warning:" + style.RESET + " "


def _line_containing(err: str, needle: str) -> str:
    """Return the single stderr line containing ``needle`` (sans newline)."""
    for line in err.splitlines():
        if needle in line:
            return line
    raise AssertionError(f"no line containing {needle!r} in:\n{err}")


def _ckpt_path_for(tmp_path: Path, step_id: int) -> Path:
    return checkpoint_path(
        tmp_path, "orch", _DETAIL_CHECKPOINT_NAME.format(step_id=step_id)
    )


@pytest.mark.integration
class TestDetailStyleOutput:
    """``detail.py``'s ``plan-tool:``/``warning:`` diagnostics route through
    ``style.tool()``/``style.warn()``: plain mode is byte-identical to the
    legacy strings, color mode tints only the prefix tag."""

    def test_save_checkpoint_failure_plain(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        from plan_tool import detail as detail_module

        def boom(*a: object, **kw: object) -> None:
            raise OSError("disk full")

        monkeypatch.setattr(detail_module, "save_checkpoint", boom)

        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            reporter=NullReporter(),
        )
        err = capsys.readouterr().err
        ckpt = _ckpt_path_for(tmp_path, 1)
        assert (
            f"plan-tool: failed to save checkpoint {ckpt} (disk full); "
            f"resume on next run will not be available for step 1"
        ) in err

    def test_save_checkpoint_failure_color_prefix_only(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_FORCE_COLOR", "1")
        plan_path = _write_orchestrator_plan(tmp_path)
        from plan_tool import detail as detail_module

        def boom(*a: object, **kw: object) -> None:
            raise OSError("disk full")

        monkeypatch.setattr(detail_module, "save_checkpoint", boom)

        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            reporter=NullReporter(),
        )
        line = _line_containing(capsys.readouterr().err, "failed to save")
        assert line.startswith(_TOOL_COLOR_PREFIX)
        assert "\033" not in line[len(_TOOL_COLOR_PREFIX):]

    def test_declined_resume_discard_failure_plain(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        ckpt = _ckpt_path_for(tmp_path, 1)
        save_checkpoint(
            ckpt,
            Checkpoint(
                input_hash=_detail_step_input_hash(plan_path, step),
                payload=_GOOD_BODY,
                created_at=_fresh_now(),
            ),
        )
        # TTY so the resume prompt fires; "n" declines → discard path.
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        from plan_tool import detail as detail_module

        def boom(*a: object, **kw: object) -> None:
            raise OSError("perm")

        monkeypatch.setattr(detail_module, "discard_checkpoint", boom)

        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            prompt_fn=lambda _q: "n",
            reporter=NullReporter(),
        )
        err = capsys.readouterr().err
        assert (
            f"plan-tool: failed to discard declined checkpoint {ckpt} "
            f"(perm); next run may re-prompt against the same stale body"
        ) in err

    def test_durable_write_discard_failure_plain(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        from plan_tool import detail as detail_module

        def boom(*a: object, **kw: object) -> None:
            raise OSError("gone")

        monkeypatch.setattr(detail_module, "discard_checkpoint", boom)

        # No seeded/declined checkpoint, so only the post-write discard fires.
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            reporter=NullReporter(),
        )
        err = capsys.readouterr().err
        ckpt = _ckpt_path_for(tmp_path, 1)
        assert (
            f"plan-tool: failed to discard checkpoint {ckpt} (gone); "
            f"next run may waste a hash-match read"
        ) in err

    def test_archived_previous_detail_plain(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        canonical = _detail_path_for(tmp_path, 1, "wire-up-renderer")
        canonical.parent.mkdir(parents=True)
        canonical.write_text("# prior body\n", encoding="utf-8")

        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            force=True,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            reporter=NullReporter(),
        )
        err = capsys.readouterr().err
        archived = list((canonical.parent / "archive").glob("*.md"))
        assert len(archived) == 1
        assert f"plan-tool: archived previous detail to {archived[0]}" in err

    def test_archived_orphan_detail_plain(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        canonical = _detail_path_for(tmp_path, 1, "wire-up-renderer")
        canonical.parent.mkdir(parents=True)
        # Sibling for the same step id under a stale slug → orphan sweep.
        orphan = canonical.parent / "01-old-slug.md"
        orphan.write_text("# stale orphan\n", encoding="utf-8")

        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            reporter=NullReporter(),
        )
        err = capsys.readouterr().err
        dest = canonical.parent / "archive" / "01-old-slug.md"
        assert f"plan-tool: archived orphan detail to {dest}" in err

    def _write_two_file_plan(self, tmp_path: Path) -> Path:
        """Plan whose step 1 declares two files the body never mentions."""
        plan_path = tmp_path / "2-orch.md"
        plan_path.write_text(
            "---\n"
            "title: Orchestrator Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Wire up the renderer\n"
            "    files:\n"
            "      - alpha.py\n"
            "      - beta.py\n"
            "    complexity: low\n"
            "    status: current\n"
            "---\n\n# Orchestrator Plan\n",
            encoding="utf-8",
        )
        return plan_path

    # Body with all required H2s but no mention of alpha.py / beta.py.
    _BODY_NO_FILES = (
        "# Title\n\n"
        "## Summary\n\nOverview.\n\n"
        "## Table of Contents\n\n- [Why](#why) — motivation\n\n"
        "## Why\n\nReason.\n\n"
        "## Files\n\n- something\n\n"
        "## Implementation\n\nstuff\n\n"
        "## Tests\n\n- test\n\n"
        "## Acceptance criteria\n\n- works\n"
    )

    def test_detail_body_mentions_warning_plain(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        plan_path = self._write_two_file_plan(tmp_path)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: self._BODY_NO_FILES,
            extract_lessons=False,
            reporter=NullReporter(),
        )
        err = capsys.readouterr().err
        assert (
            "warning: step 1 detail body mentions 0 of 2 declared files; "
            "missing: alpha.py, beta.py"
        ) in err

    def test_detail_body_mentions_warning_color_prefix_only(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_FORCE_COLOR", "1")
        plan_path = self._write_two_file_plan(tmp_path)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: self._BODY_NO_FILES,
            extract_lessons=False,
            reporter=NullReporter(),
        )
        line = _line_containing(capsys.readouterr().err, "detail body mentions")
        assert line.startswith(_WARN_COLOR_PREFIX)
        assert "\033" not in line[len(_WARN_COLOR_PREFIX):]

    def test_lesson_extraction_error_plain(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        from plan_tool import detail as detail_module

        def boom(**kwargs: object) -> tuple[int, int]:
            raise RuntimeError("boom")

        # Override the autouse no-op stub so the error path fires.
        monkeypatch.setattr(
            detail_module, "extract_and_append_detail_lessons", boom
        )
        # Capture only runs after a clean detail-quality converge.
        monkeypatch.setattr(
            detail_module,
            "collect_detail_quality_findings",
            lambda *a, **kw: [],
        )
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=True,
            lessons_invoker=lambda _p: (0, ""),
            reporter=NullReporter(),
            budget=_IterativeBudget(enabled=True, max_iterations=3),
        )
        err = capsys.readouterr().err
        assert (
            "plan-tool: lesson extraction failed for step 1 (boom); "
            "detail file is unaffected"
        ) in err

    def test_lesson_extraction_error_no_error_level(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        from plan_tool import detail as detail_module

        def boom(**kwargs: object) -> tuple[int, int]:
            raise RuntimeError("boom")

        monkeypatch.setattr(
            detail_module, "extract_and_append_detail_lessons", boom
        )
        monkeypatch.setattr(
            detail_module,
            "collect_detail_quality_findings",
            lambda *a, **kw: [],
        )
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=True,
            lessons_invoker=lambda _p: (0, ""),
            reporter=NullReporter(),
            budget=_IterativeBudget(enabled=True, max_iterations=3),
        )
        line = _line_containing(
            capsys.readouterr().err, "lesson extraction failed"
        )
        # ``tool()`` with no ``level=`` → no ``error:`` tag (byte-identity).
        assert "error:" not in line

    def test_lesson_extraction_skipped_without_iterate(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``--lessons`` without a clean quality converge must not capture."""
        plan_path = _write_orchestrator_plan(tmp_path)
        from plan_tool import detail as detail_module

        calls = {"n": 0}

        def track(**kwargs: object) -> tuple[int, int]:
            calls["n"] += 1
            return (0, 0)

        monkeypatch.setattr(
            detail_module, "extract_and_append_detail_lessons", track
        )
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=True,
            lessons_invoker=lambda _p: (0, ""),
            reporter=NullReporter(),
        )
        assert calls["n"] == 0
        err = capsys.readouterr().err
        assert "lesson extraction skipped for step 1" in err
        assert "clean detail-quality pass" in err

    def test_iteration_halt_plain(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        from plan_tool import detail as detail_module
        from plan_tool import review as review_module
        from plan_tool.review import _claude_recommendations

        recs = _claude_recommendations(_FINDINGS_BLOCK_TWO_OPEN)
        # Module-level: patch ``detail.collect_detail_quality_findings``.
        monkeypatch.setattr(
            detail_module,
            "collect_detail_quality_findings",
            lambda *a, **kw: list(recs),
        )
        # Lazily imported inside the loop from ``plan_tool.review``, so the
        # patch must land on the review module, not detail. Forcing
        # ``open_apply`` empty + ``open_deferred`` non-empty fires the halt.
        monkeypatch.setattr(
            review_module,
            "partition_findings_for_triage",
            lambda findings, **kw: ([], list(findings)),
        )

        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            budget=_IterativeBudget(enabled=True, max_iterations=3),
            reporter=NullReporter(),
        )
        err = capsys.readouterr().err
        assert (
            f"plan-tool: detail iteration halting -- all {len(recs)} "
            f"remaining finding(s) for step 1 are triaged-deferred. "
            f"Apply manually or pass --no-triage to force-apply."
        ) in err

    def test_repo_relative_out_of_tree_warning_plain(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        out_of_tree = Path("/elsewhere/x.md")
        result = _repo_relative(out_of_tree, tmp_path)
        assert result == str(out_of_tree.resolve())
        err = capsys.readouterr().err
        # ``repo_root`` is interpolated un-resolved, so it's ``tmp_path`` as passed.
        assert err == (
            f"warning: detail path {out_of_tree} is not under repo root "
            f"{tmp_path}; storing absolute path in step.detail\n"
        )

    def test_repo_relative_out_of_tree_warning_color_prefix_only(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_FORCE_COLOR", "1")
        _repo_relative(Path("/elsewhere/x.md"), tmp_path)
        err = capsys.readouterr().err
        assert err.startswith(_WARN_COLOR_PREFIX)
        assert "\033" not in err[len(_WARN_COLOR_PREFIX):]


def _quality_rec(
    rec_id: str,
    severity: str,
    body: str,
    *,
    anchor: Optional[str] = None,
    title: str = "title",
) -> "Recommendation":
    from plan_tool.review import Recommendation

    return Recommendation(
        id=rec_id,
        source="detail-quality",
        step_id=1,
        severity=severity,
        title=title,
        body=body,
        anchor=anchor,
    )


class TestEmitDetailFindingsSummary:
    """The detail convergence loop surfaces gaps with severity, mirroring
    the completeness-audit display (severity banner + per-finding lines)."""

    def test_renders_banner_and_per_finding_lines_most_urgent_first(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        recs = [
            _quality_rec("r1", "medium", "Decorative vocabulary flagged.", anchor="dv"),
            _quality_rec("r2", "critical", "Missing edge case."),
        ]
        emit_detail_findings_summary(recs, step_id=3, iteration=2)
        err = capsys.readouterr().err
        # Audit-style severity histogram banner.
        assert "detail-quality: step 3 / iter 2 — Findings: 1 critical · 1 medium" in err
        # Most-urgent-first ordering: critical precedes medium.
        crit_line = "          - CRITICAL: Missing edge case."
        med_line = "          - MEDIUM [dv]: Decorative vocabulary flagged."
        assert crit_line in err and med_line in err
        assert err.index(crit_line) < err.index(med_line)

    def test_anchor_tag_only_when_present(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        emit_detail_findings_summary(
            [_quality_rec("r1", "nit", "No anchor here.")], step_id=1, iteration=1
        )
        err = capsys.readouterr().err
        assert "- NIT: No anchor here." in err
        assert "[confidence: limited]" in err.split("- NIT:")[1]

    def test_multiline_body_collapses_to_one_line(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        emit_detail_findings_summary(
            [_quality_rec("r1", "high", "Line one.\n\nLine two.")],
            step_id=1,
            iteration=1,
        )
        err = capsys.readouterr().err
        assert "- HIGH: Line one. Line two." in err

    def test_empty_body_falls_back_to_title(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        emit_detail_findings_summary(
            [_quality_rec("r1", "nit", "", title="Trailing whitespace")],
            step_id=1,
            iteration=1,
        )
        assert "- NIT: Trailing whitespace" in capsys.readouterr().err

    def test_empty_scan_prints_nothing(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        emit_detail_findings_summary([], step_id=1, iteration=1)
        assert capsys.readouterr().err == ""


# --- Step 2: merge cluster (inverse of the split cluster) ------------------

from plan_tool.detail import (  # noqa: E402
    MergeBridgeResult,
    MergeResult,
    _confirm_merge,
    _merge_is_safe,
    _migrate_downstream_details_after_merge,
    merge_bridge,
    merge_steps,
)

_PLAN_STUB = (
    "---\ntitle: stub\nstatus: planning\npriority: low\n"
    "steps:\n  - id: 1\n    title: stub\n---\n\n# stub\n"
)


def _seed_and_write_plan(plan_path: Path, plan: Plan) -> None:
    """Seed a stub file then serialize ``plan`` through ``write_plan`` (which
    reads the existing file for its prose body)."""
    plan_path.write_text(_PLAN_STUB, encoding="utf-8")
    write_plan(plan_path, plan, expect_unchanged=False)


def _build_merge_plan(
    tmp_path: Path,
    *,
    statuses: "Optional[dict[int, StepStatus]]" = None,
    concept_ids: "Optional[dict[int, list[str]]]" = None,
    intents: "Optional[dict[int, Optional[str]]]" = None,
) -> Path:
    """Canonical 4-step all-PENDING plan with rich per-step fields.

    step2 (refactor, low, feat-core, gate, enforce) and step3 (feature, high,
    feat-extra, creates) are the merge members; step4 is the downstream the
    fold renumbers down. ``statuses`` overrides individual step statuses.
    ``intents`` sets per-step ``intent`` (omit a key to leave the default None).
    """
    statuses = statuses or {}
    concept_ids = concept_ids or {}
    intents = intents or {}
    steps = [
        Step(
            id=1,
            title="Setup",
            files=["a.py"],
            status=statuses.get(1, StepStatus.PENDING),
            intent=intents.get(1),
        ),
        Step(
            id=2,
            title="Build core",
            files=["b.py"],
            complexity=Complexity.LOW,
            change_type=ChangeType.REFACTOR,
            features=["feat-core"],
            gate=["pytest -q"],
            enforce_test_authoring=True,
            concept_ids=concept_ids.get(2, []),
            depends_on=[1],
            status=statuses.get(2, StepStatus.PENDING),
            intent=intents.get(2),
        ),
        Step(
            id=3,
            title="Add feature",
            files=["c.py"],
            creates=["new.py"],
            complexity=Complexity.HIGH,
            change_type=ChangeType.FEATURE,
            features=["feat-extra"],
            concept_ids=concept_ids.get(3, []),
            depends_on=[2],
            status=statuses.get(3, StepStatus.PENDING),
            intent=intents.get(3),
        ),
        Step(
            id=4,
            title="Wire CLI",
            files=["d.py"],
            depends_on=[3],
            status=statuses.get(4, StepStatus.PENDING),
            intent=intents.get(4),
        ),
    ]
    plan = Plan(
        title="Merge Test",
        status=PlanStatus.IN_PROGRESS,
        priority=Priority.MEDIUM,
        steps=steps,
    )
    plan_path = tmp_path / "2-merge.md"
    _seed_and_write_plan(plan_path, plan)
    for f in ("a.py", "b.py", "c.py", "d.py"):
        (tmp_path / f).write_text(f"# {f}\nX = 1\n", encoding="utf-8")
    return plan_path


def _plan_with_n_statuses(*statuses: StepStatus) -> Plan:
    """All-id plan whose steps chain 1<-2<-3<-... so a merge set is
    dependency-connected."""
    return Plan(
        title="t",
        status=PlanStatus.PLANNING,
        priority=Priority.LOW,
        steps=[
            Step(
                id=i + 1,
                title=f"step {i + 1}",
                status=st,
                depends_on=[i] if i > 0 else [],
            )
            for i, st in enumerate(statuses)
        ],
    )


class TestDetailFormatVersionStamp:
    """``stamp_detail_format_version_marker`` — the writer's sole authority
    over the current run-grade detail marker. Unit-level: pure string
    operations on an already-parsed body, no invoker, no filesystem."""

    def test_stamp_makes_current_marker_the_first_nonblank_line_after_h1(
        self,
    ) -> None:
        body = "# Title\n\n## Summary\n\nx\n"
        stamped = stamp_detail_format_version_marker(body)

        lines = stamped.splitlines()
        assert lines[0] == "# Title"
        first_nonblank_after_h1 = next(
            line for line in lines[1:] if line.strip()
        )
        assert first_nonblank_after_h1 == render_detail_format_version_marker()
        assert "## Summary" in stamped

    @pytest.mark.parametrize("proposed_payload", ["1", "999", "banana", ""])
    def test_stamp_replaces_a_model_proposed_marker_rather_than_adding_beside_it(
        self, proposed_payload: str
    ) -> None:
        """A model cannot cause a self-refusing file: whatever it proposes
        in the slot — well-formed, unsupported, or malformed — is dropped
        and replaced with exactly the current marker."""
        body = (
            f"# Title\n"
            f"<!-- plan-tool:detail-format-version: {proposed_payload} -->\n"
            f"\n## Summary\n\nx\n"
        )
        stamped = stamp_detail_format_version_marker(body)

        assert stamped.count("plan-tool:detail-format-version") == 1
        assert render_detail_format_version_marker() in stamped
        if proposed_payload not in {"1", ""}:
            assert proposed_payload not in stamped

    def test_stamp_collapses_stacked_proposed_markers_to_one(self) -> None:
        body = (
            "# Title\n"
            "<!-- plan-tool:detail-format-version: 1 -->\n"
            "<!-- plan-tool:detail-format-version: 2 -->\n"
            "\n## Summary\n\nx\n"
        )
        stamped = stamp_detail_format_version_marker(body)

        assert stamped.count("plan-tool:detail-format-version") == 1

    def test_stamp_preserves_blank_separated_marker_beyond_the_slot(self) -> None:
        marker_in_prose = "<!-- plan-tool:detail-format-version: 999 -->"
        body = (
            "# Title\n"
            "<!-- plan-tool:detail-format-version: 1 -->\n\n"
            f"{marker_in_prose}\n\n"
            "## Summary\n\nx\n"
        )

        stamped = stamp_detail_format_version_marker(body)

        assert marker_in_prose in stamped

    def test_stamp_leaves_marker_shaped_prose_outside_the_slot_untouched(
        self,
    ) -> None:
        marker_in_prose = "<!-- plan-tool:detail-format-version: 999 -->"
        body = (
            "# Title\n\n"
            "## Summary\n\nx\n\n"
            "## Implementation\n\n"
            f"Do not write {marker_in_prose} yourself.\n\n"
            "```\n"
            f"{marker_in_prose}\n"
            "```\n"
        )
        stamped = stamp_detail_format_version_marker(body)

        # The slot carries exactly one current marker...
        lines = stamped.splitlines()
        first_nonblank_after_h1 = next(
            line for line in lines[1:] if line.strip()
        )
        assert first_nonblank_after_h1 == render_detail_format_version_marker()
        # ...and both out-of-slot occurrences of the proposed marker survive
        # byte-for-byte, untouched.
        assert stamped.count(marker_in_prose) == 2

    def test_stamp_preserves_non_newline_line_separators_outside_the_slot(
        self,
    ) -> None:
        separators = "vertical\vform\fline\u2028paragraph\u2029end"
        body = f"# Title\n\n## Summary\n\n{separators}\n"

        stamped = stamp_detail_format_version_marker(body)

        assert separators in stamped

    def test_stamp_is_idempotent(self) -> None:
        body = "# Title\n\n## Summary\n\nx\n"
        once = stamp_detail_format_version_marker(body)
        twice = stamp_detail_format_version_marker(once)

        assert twice == once

    def test_stamp_writes_exactly_the_string_the_reader_renders(self) -> None:
        body = "# Title\n\n## Summary\n\nx\n"
        stamped = stamp_detail_format_version_marker(body)

        assert render_detail_format_version_marker() in stamped.splitlines()

    def test_stamped_body_passes_the_shared_reader_gate(self) -> None:
        body = "# Title\n\n## Summary\n\nx\n"
        stamped = stamp_detail_format_version_marker(body)

        require_supported_detail_format_version(stamped)  # raises on failure

    def test_stamped_body_still_parses_into_all_seven_sections(self) -> None:
        stamped = stamp_detail_format_version_marker(_GOOD_BODY)

        from plan_tool.detail import parse_detail_file_sections

        sections = parse_detail_file_sections(stamped)
        for token in (
            "summary", "table", "why", "files",
            "implementation", "tests", "acceptance",
        ):
            assert token in sections
        assert (
            sections["summary"].strip()
            == "Reviewer-facing overview of the wire-up step."
        )

    def test_stamp_requires_a_valid_carrier_h1(self) -> None:
        with pytest.raises(DetailError):
            stamp_detail_format_version_marker("## Summary\n\nx\n")


class TestDetailFormatVersionAuthoringBoundaries:
    """The authoring-prompt readers (sibling reference, already-implemented
    heuristic scoping, deterministic per-step grounding) each refuse an
    unsupported detail marker rather than silently degrading into their
    ordinary best-effort fallback — that fallback stays reserved for a
    genuinely missing/unreadable/crashing case."""

    def test_sibling_reference_block_refuses_an_unsupported_detail_marker(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.detail import _format_sibling_details_block
        from plan_tool.detail_artifacts import (
            DetailFormatError,
            render_detail_format_version_marker,
        )

        good = tmp_path / "01-first.md"
        good.write_text("# Step 1\n\nfine.\n", encoding="utf-8")
        bad = tmp_path / "02-second.md"
        bad.write_text(
            f"# Step 2\n{render_detail_format_version_marker(999)}\n\nfine.\n",
            encoding="utf-8",
        )

        with pytest.raises(DetailFormatError):
            _format_sibling_details_block([good, bad], max_file_bytes=4096)

    def test_authoring_prompt_boundaries_reraise_detail_format_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``_format_already_implemented_block`` and
        ``collect_step_grounding_findings`` keep their existing best-effort
        fallback for an unrelated crash, but a real ``DetailFormatError``
        from the review primitives they call must escape instead."""
        from plan_tool import detail as detail_module
        from plan_tool import review as review_module
        from plan_tool.detail import (
            _format_already_implemented_block,
            collect_step_grounding_findings,
        )
        from plan_tool.detail_artifacts import DetailFormatError

        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)

        # Unrelated crash: existing fallback is preserved. ``detail.py``
        # imports ``heuristic_already_done`` by name, so the patch target
        # is the name bound in *its* namespace, not ``review``'s.
        monkeypatch.setattr(
            detail_module,
            "heuristic_already_done",
            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        assert _format_already_implemented_block(plan, step, tmp_path) == (
            "_(heuristic skipped — could not scan plan files)_"
        )
        monkeypatch.setattr(
            review_module,
            "collect_deterministic_findings",
            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        assert collect_step_grounding_findings(
            plan, plan_path, step, repo_root=tmp_path, plan_name="orch",
        ) == []

        # A real format refusal escapes both instead of being swallowed.
        monkeypatch.setattr(
            detail_module,
            "heuristic_already_done",
            lambda *a, **kw: (_ for _ in ()).throw(
                DetailFormatError("detail declares an unsupported version")
            ),
        )
        with pytest.raises(DetailFormatError):
            _format_already_implemented_block(plan, step, tmp_path)

        monkeypatch.setattr(
            review_module,
            "collect_deterministic_findings",
            lambda *a, **kw: (_ for _ in ()).throw(
                DetailFormatError("detail declares an unsupported version")
            ),
        )
        with pytest.raises(DetailFormatError):
            collect_step_grounding_findings(
                plan, plan_path, step, repo_root=tmp_path, plan_name="orch",
            )

    def test_files_contents_block_ignores_detail_format_version_entirely(
        self, tmp_path: Path
    ) -> None:
        """A negative control: the declared-*source-files* renderer is a
        different artifact class and must be unaffected by a marker-shaped
        line inside one of those files."""
        from plan_tool.detail import _format_files_contents_block
        from plan_tool.detail_artifacts import render_detail_format_version_marker

        (tmp_path / "foo.py").write_text(
            f"# {render_detail_format_version_marker(999)}\n"
            "def foo():\n    return 1\n",
            encoding="utf-8",
        )
        step = Step(id=1, title="Build foo", files=["foo.py"])
        rendered = _format_files_contents_block(
            step, tmp_path, max_file_bytes=4096
        )
        assert "def foo" in rendered


class TestMergeIsSafe:
    """A merge is unsafe iff any member OR any step after the merged region is
    DONE. A CURRENT (next-runnable, unrun) member or downstream step, a DONE
    step before the region, and a parked-but-PENDING member, do not block."""

    def test_all_pending_set_is_safe(self) -> None:
        plan = _plan_with_n_statuses(
            StepStatus.PENDING, StepStatus.PENDING,
            StepStatus.PENDING, StepStatus.PENDING,
        )
        assert _merge_is_safe(plan, [2, 3]) == (True, [])

    def test_done_member_blocks(self) -> None:
        plan = _plan_with_n_statuses(
            StepStatus.PENDING, StepStatus.DONE,
            StepStatus.PENDING, StepStatus.PENDING,
        )
        assert _merge_is_safe(plan, [2, 3]) == (False, [2])

    def test_current_member_is_safe(self) -> None:
        # An authored-but-unrun ``current`` member no longer blocks: ``current``
        # is "next runnable", not mid-execution (only DONE is renumber-orphanable).
        plan = _plan_with_n_statuses(
            StepStatus.PENDING, StepStatus.PENDING,
            StepStatus.CURRENT, StepStatus.PENDING,
        )
        assert _merge_is_safe(plan, [2, 3]) == (True, [])

    def test_parked_member_is_safe(self) -> None:
        plan = _plan_with_n_statuses(
            StepStatus.PENDING, StepStatus.PENDING,
            StepStatus.PENDING, StepStatus.PENDING,
        )
        plan.steps[1].scope = StepScope.DEFERRED
        assert _merge_is_safe(plan, [2, 3]) == (True, [])

    def test_downstream_done_blocks(self) -> None:
        plan = _plan_with_n_statuses(
            StepStatus.PENDING, StepStatus.PENDING,
            StepStatus.PENDING, StepStatus.DONE,
        )
        assert _merge_is_safe(plan, [2, 3]) == (False, [4])

    def test_downstream_current_does_not_block(self) -> None:
        # A downstream CURRENT step renumbers cleanly (no green commit to orphan).
        plan = _plan_with_n_statuses(
            StepStatus.PENDING, StepStatus.PENDING,
            StepStatus.PENDING, StepStatus.CURRENT,
        )
        assert _merge_is_safe(plan, [2, 3]) == (True, [])

    def test_upstream_done_does_not_block(self) -> None:
        plan = _plan_with_n_statuses(
            StepStatus.DONE, StepStatus.PENDING,
            StepStatus.PENDING, StepStatus.PENDING,
        )
        assert _merge_is_safe(plan, [2, 3]) == (True, [])


class TestMigrateDownstreamDetailsAfterMerge:
    """Rename downstream detail files DOWN and repoint after a merge."""

    def _touch(self, repo_root: Path, rel: str, body: str = "body\n") -> Path:
        p = repo_root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
        return p

    def test_renames_downstream_down_and_repoints(self, tmp_path: Path) -> None:
        self._touch(tmp_path, "plan-details/p/04-four.md")
        new_steps = [
            Step(id=1, title="one"),
            Step(id=2, title="merged"),
            Step(id=3, title="four", detail="plan-details/p/04-four.md"),
        ]
        _migrate_downstream_details_after_merge(
            new_steps, repo_root=tmp_path, merged_new_id=2
        )
        assert (tmp_path / "plan-details/p/03-four.md").is_file()
        assert not (tmp_path / "plan-details/p/04-four.md").exists()
        assert new_steps[2].detail == "plan-details/p/03-four.md"

    def test_processes_low_to_high_without_clobber(self, tmp_path: Path) -> None:
        # source 04 -> target 03, source 05 -> target 04. Ascending renames
        # 04->03 first so 05->04 lands on a freed slot; high->low would clobber.
        self._touch(tmp_path, "plan-details/p/04-shared.md", body="three\n")
        self._touch(tmp_path, "plan-details/p/05-shared.md", body="four\n")
        new_steps = [
            Step(id=1, title="one"),
            Step(id=2, title="merged"),
            Step(id=3, title="three", detail="plan-details/p/04-shared.md"),
            Step(id=4, title="four", detail="plan-details/p/05-shared.md"),
        ]
        _migrate_downstream_details_after_merge(
            new_steps, repo_root=tmp_path, merged_new_id=2
        )
        assert (tmp_path / "plan-details/p/03-shared.md").read_text() == "three\n"
        assert (tmp_path / "plan-details/p/04-shared.md").read_text() == "four\n"
        assert not (tmp_path / "plan-details/p/05-shared.md").exists()

    def test_missing_source_file_repoints_only(self, tmp_path: Path) -> None:
        (tmp_path / "plan-details/p").mkdir(parents=True)
        new_steps = [
            Step(id=1, title="one"),
            Step(id=2, title="merged"),
            Step(id=3, title="gone", detail="plan-details/p/04-gone.md"),
            Step(id=4, title="odd", detail="plan-details/p/weird.md"),
        ]
        _migrate_downstream_details_after_merge(
            new_steps, repo_root=tmp_path, merged_new_id=2
        )
        assert new_steps[2].detail == "plan-details/p/03-gone.md"
        assert new_steps[3].detail == "plan-details/p/weird.md"

    def test_pre_region_steps_untouched(self, tmp_path: Path) -> None:
        self._touch(tmp_path, "plan-details/p/01-one.md")
        new_steps = [
            Step(id=1, title="one", detail="plan-details/p/01-one.md"),
            Step(id=2, title="merged"),
        ]
        _migrate_downstream_details_after_merge(
            new_steps, repo_root=tmp_path, merged_new_id=2
        )
        assert (tmp_path / "plan-details/p/01-one.md").is_file()
        assert new_steps[0].detail == "plan-details/p/01-one.md"


class TestConfirmMerge:
    """The TTY yes/no gate (defined here, invoked by step 3's cmd_merge)."""

    def test_non_tty_auto_declines(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)

        def _boom(_m: str) -> str:
            raise AssertionError("non-TTY must not prompt")

        assert (
            _confirm_merge(
                _boom,
                steps_to_merge=[Step(id=2, title="a"), Step(id=3, title="b")],
                merged_title="a",
            )
            is False
        )

    @pytest.mark.parametrize("answer", ["y", "yes", "  YES "])
    def test_yes_confirms(
        self, monkeypatch: pytest.MonkeyPatch, answer: str
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        assert (
            _confirm_merge(
                lambda _m: answer,
                steps_to_merge=[Step(id=2, title="a"), Step(id=3, title="b")],
                merged_title="a",
            )
            is True
        )

    @pytest.mark.parametrize("answer", ["", "n", "no", "maybe"])
    def test_default_declines(
        self, monkeypatch: pytest.MonkeyPatch, answer: str
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        assert (
            _confirm_merge(
                lambda _m: answer,
                steps_to_merge=[Step(id=2, title="a"), Step(id=3, title="b")],
                merged_title="a",
            )
            is False
        )


class TestMergeSteps:
    """``merge_steps``: deterministic fold of a contiguous all-PENDING set."""

    _CONCEPT_A = "a" * 64
    _CONCEPT_B = "b" * 64
    _CONCEPT_C = "c" * 64

    def test_dry_run_computes_renumber_and_newplan_no_writes(
        self, tmp_path: Path
    ) -> None:
        plan_path = _build_merge_plan(tmp_path)
        before = plan_path.read_text(encoding="utf-8")

        def _boom(_p: str) -> str:
            raise AssertionError("dry-run must not author")

        res = merge_steps(
            plan_path,
            merge_ids=[2, 3],
            repo_root=tmp_path,
            dry_run=True,
            invoker=_boom,
        )
        assert res.dry_run is True
        assert res.detail_results == []
        assert res.renumber == [(1, 1), (2, 2), (3, 2), (4, 3)]
        assert res.new_plan == [
            (1, "Setup", []),
            (2, "Build core", [1]),
            (3, "Wire CLI", [2]),
        ]
        assert plan_path.read_text(encoding="utf-8") == before
        assert not (tmp_path / "plan-details").exists()

    def test_dry_run_unions_concept_ownership_without_writes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = _build_merge_plan(
            tmp_path,
            concept_ids={
                2: [self._CONCEPT_B, self._CONCEPT_A],
                3: [self._CONCEPT_A, self._CONCEPT_C],
            },
        )
        before = plan_path.read_text(encoding="utf-8")
        from plan_tool import create as create_module

        real_apply_step_merge = create_module._apply_step_merge
        preview_concept_ids: list[str] = []

        def _capture_preview(steps, merge_ids, merged):
            new_steps = real_apply_step_merge(steps, merge_ids, merged)
            preview_concept_ids.extend(new_steps[min(merge_ids) - 1].concept_ids)
            return new_steps

        monkeypatch.setattr(create_module, "_apply_step_merge", _capture_preview)

        merge_steps(
            plan_path,
            merge_ids=[2, 3],
            repo_root=tmp_path,
            dry_run=True,
        )

        assert preview_concept_ids == [
            self._CONCEPT_B,
            self._CONCEPT_A,
            self._CONCEPT_C,
        ]
        assert plan_path.read_text(encoding="utf-8") == before

    def test_persisted_merge_preserves_all_member_concept_ids(
        self, tmp_path: Path
    ) -> None:
        plan_path = _build_merge_plan(
            tmp_path,
            concept_ids={2: [self._CONCEPT_A], 3: [self._CONCEPT_B]},
        )

        merge_steps(
            plan_path, merge_ids=[2, 3], repo_root=tmp_path, author_details=False
        )

        assert parse_plan(plan_path).step_by_id(2).concept_ids == [
            self._CONCEPT_A,
            self._CONCEPT_B,
        ]

    def test_persisted_merge_deduplicates_shared_concept_ownership(
        self, tmp_path: Path
    ) -> None:
        plan_path = _build_merge_plan(
            tmp_path,
            concept_ids={
                2: [self._CONCEPT_A, self._CONCEPT_B],
                3: [self._CONCEPT_B],
            },
        )

        merge_steps(
            plan_path, merge_ids=[2, 3], repo_root=tmp_path, author_details=False
        )

        assert parse_plan(plan_path).step_by_id(2).concept_ids == [
            self._CONCEPT_A,
            self._CONCEPT_B,
        ]

    def test_rejects_fewer_than_two_ids(self, tmp_path: Path) -> None:
        plan_path = _build_merge_plan(tmp_path)
        with pytest.raises(DetailError, match="at least two"):
            merge_steps(
                plan_path, merge_ids=[2], repo_root=tmp_path, author_details=False
            )

    def test_rejects_non_canonical_numbering(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "2-gap.md"
        plan_path.write_text(
            "---\ntitle: Gap\nstatus: in-progress\npriority: medium\n"
            "steps:\n"
            "  - id: 1\n    title: First\n    files:\n      - a.py\n"
            "  - id: 3\n    title: Third\n    files:\n      - b.py\n"
            "    depends_on: [1]\n"
            "---\n\n# Gap\n",
            encoding="utf-8",
        )
        with pytest.raises(DetailError, match="not canonical"):
            merge_steps(
                plan_path, merge_ids=[1, 3], repo_root=tmp_path, author_details=False
            )

    def test_rejects_unknown_id(self, tmp_path: Path) -> None:
        plan_path = _build_merge_plan(tmp_path)
        with pytest.raises(DetailError, match="not found"):
            merge_steps(
                plan_path, merge_ids=[2, 99], repo_root=tmp_path, author_details=False
            )

    def test_unsafe_set_raises_before_mutation(self, tmp_path: Path) -> None:
        plan_path = _build_merge_plan(tmp_path, statuses={2: StepStatus.DONE})
        before = plan_path.read_text(encoding="utf-8")
        with pytest.raises(DetailError, match="are done"):
            merge_steps(
                plan_path, merge_ids=[2, 3], repo_root=tmp_path, author_details=False
            )
        assert plan_path.read_text(encoding="utf-8") == before
        assert not (tmp_path / "plan-details").exists()

    def test_invalid_graph_raises(self, tmp_path: Path) -> None:
        plan_path = _build_merge_plan(tmp_path)
        before = plan_path.read_text(encoding="utf-8")
        with pytest.raises(DetailError, match="merge failed"):
            merge_steps(
                plan_path, merge_ids=[2, 4], repo_root=tmp_path, author_details=False
            )
        assert plan_path.read_text(encoding="utf-8") == before

    def test_mixed_scope_set_raises_before_mutation(self, tmp_path: Path) -> None:
        mixed_dir = tmp_path / "mixed"
        mixed_dir.mkdir()
        mixed = Plan(
            title="Mixed",
            status=PlanStatus.IN_PROGRESS,
            priority=Priority.MEDIUM,
            steps=[
                Step(id=1, title="Setup"),
                Step(id=2, title="Core", scope=StepScope.DEFERRED, depends_on=[1]),
                Step(id=3, title="Feature", depends_on=[1]),
            ],
        )
        mixed_path = mixed_dir / "2-mixed.md"
        _seed_and_write_plan(mixed_path, mixed)
        before = mixed_path.read_text(encoding="utf-8")
        with pytest.raises(DetailError, match="mixed-scope"):
            merge_steps(
                mixed_path, merge_ids=[2, 3], repo_root=mixed_dir, author_details=False
            )
        assert mixed_path.read_text(encoding="utf-8") == before

        uni_dir = tmp_path / "uni"
        uni_dir.mkdir()
        uni = Plan(
            title="Uniform",
            status=PlanStatus.IN_PROGRESS,
            priority=Priority.MEDIUM,
            steps=[
                Step(id=1, title="Setup"),
                Step(id=2, title="Core", scope=StepScope.DEFERRED, depends_on=[1]),
                Step(id=3, title="Feature", scope=StepScope.DEFERRED, depends_on=[2]),
            ],
        )
        uni_path = uni_dir / "2-uni.md"
        _seed_and_write_plan(uni_path, uni)
        merge_steps(
            uni_path, merge_ids=[2, 3], repo_root=uni_dir, author_details=False
        )
        assert parse_plan(uni_path).step_by_id(2).scope == StepScope.DEFERRED

    def test_folds_set_and_renumbers(self, tmp_path: Path) -> None:
        plan_path = _build_merge_plan(tmp_path)
        merge_steps(
            plan_path, merge_ids=[2, 3], repo_root=tmp_path, author_details=False
        )
        plan = parse_plan(plan_path)
        assert [s.id for s in plan.steps] == [1, 2, 3]
        assert plan.step_by_id(2).title == "Build core"
        assert plan.step_by_id(2).depends_on == [1]
        assert plan.step_by_id(3).title == "Wire CLI"
        assert plan.step_by_id(3).depends_on == [2]

    def test_merged_step_inherits_assembled_fields(self, tmp_path: Path) -> None:
        plan_path = _build_merge_plan(tmp_path)
        merge_steps(
            plan_path, merge_ids=[2, 3], repo_root=tmp_path, author_details=False
        )
        m = parse_plan(plan_path).step_by_id(2)
        assert m.title == "Build core"
        assert m.files == ["b.py", "c.py"]
        assert m.creates == ["new.py"]
        assert m.complexity == Complexity.HIGH
        assert m.change_type == ChangeType.FEATURE
        assert "type_impure" not in Step.model_fields

    def test_merged_step_carries_features_gate_and_enforce_test_authoring(
        self, tmp_path: Path
    ) -> None:
        plan_path = _build_merge_plan(tmp_path)
        merge_steps(
            plan_path, merge_ids=[2, 3], repo_root=tmp_path, author_details=False
        )
        m = parse_plan(plan_path).step_by_id(2)
        assert m.features == ["feat-core", "feat-extra"]
        assert m.gate == ["pytest -q"]
        assert m.enforce_test_authoring is True

    def test_returns_populated_mergeresult(self, tmp_path: Path) -> None:
        plan_path = _build_merge_plan(tmp_path)
        res = merge_steps(
            plan_path, merge_ids=[2, 3], repo_root=tmp_path, author_details=False
        )
        assert isinstance(res, MergeResult)
        assert res.folded_ids == [2, 3]
        assert res.folded_titles == ["Build core", "Add feature"]
        assert res.merged_id == 2
        assert res.merged_title == "Build core"
        assert res.detail_results == []
        assert res.dry_run is False

    def _detail_member_files(self, tmp_path: Path, plan_path: Path) -> Path:
        ddir = tmp_path / "plan-details" / "merge"
        ddir.mkdir(parents=True)
        (ddir / "02-build-core.md").write_text(_GOOD_BODY, encoding="utf-8")
        (ddir / "03-add-feature.md").write_text(_GOOD_BODY, encoding="utf-8")
        update_step_detail_field(plan_path, 2, "plan-details/merge/02-build-core.md")
        update_step_detail_field(plan_path, 3, "plan-details/merge/03-add-feature.md")
        return ddir

    def test_folded_files_archived_after_merge(self, tmp_path: Path) -> None:
        plan_path = _build_merge_plan(tmp_path)
        ddir = self._detail_member_files(tmp_path, plan_path)
        merge_steps(
            plan_path,
            merge_ids=[2, 3],
            repo_root=tmp_path,
            invoker=lambda _p: _GOOD_BODY,
        )
        assert (ddir / "02-build-core.md").is_file()
        assert not (ddir / "03-add-feature.md").exists()
        assert (ddir / "archive").is_dir()
        assert parse_plan(plan_path).step_by_id(2).detail == (
            "plan-details/merge/02-build-core.md"
        )

    def test_reauthor_receives_full_member_bodies_via_prior_body(
        self, tmp_path: Path
    ) -> None:
        plan_path = _build_merge_plan(tmp_path)
        ddir = tmp_path / "plan-details" / "merge"
        ddir.mkdir(parents=True)
        big = (
            "# Step 2 — Build core\n"
            "<!-- plan-tool:detail-format-version: 1 -->\n\n"
            + ("filler line padding here\n" * 400)
            + "LOWEST_MEMBER_MARKER_PAST_CUTOFF\n"
        )
        assert len(big.encode("utf-8")) > 4096
        (ddir / "02-build-core.md").write_text(big, encoding="utf-8")
        (ddir / "03-add-feature.md").write_text(
            "# Step 3 — Add feature\n\nMEMBER3_UNIQUE_MARKER\n", encoding="utf-8"
        )
        update_step_detail_field(plan_path, 2, "plan-details/merge/02-build-core.md")
        update_step_detail_field(plan_path, 3, "plan-details/merge/03-add-feature.md")

        captured: list[str] = []

        def _capture(prompt: str) -> str:
            captured.append(prompt)
            return _GOOD_BODY

        merge_steps(
            plan_path, merge_ids=[2, 3], repo_root=tmp_path, invoker=_capture
        )
        joined = "\n".join(captured)
        assert "LOWEST_MEMBER_MARKER_PAST_CUTOFF" in joined
        assert "MEMBER3_UNIQUE_MARKER" in joined
        assert "<!-- plan-tool:detail-format-version: 1 -->" not in joined

    @pytest.mark.parametrize("bad_member", [2, 3])
    def test_merge_refuses_an_unsupported_detail_marker_on_either_side(
        self, tmp_path: Path, bad_member: int
    ) -> None:
        from plan_tool.detail_artifacts import (
            DetailFormatError,
            render_detail_format_version_marker,
        )

        plan_path = _build_merge_plan(tmp_path)
        ddir = tmp_path / "plan-details" / "merge"
        ddir.mkdir(parents=True)
        bodies = {
            2: "# Step 2 — Build core\n\nfine.\n",
            3: "# Step 3 — Add feature\n\nfine.\n",
        }
        bodies[bad_member] = (
            f"# Step {bad_member}\n{render_detail_format_version_marker(999)}\n\n"
            "fine.\n"
        )
        (ddir / "02-build-core.md").write_text(bodies[2], encoding="utf-8")
        (ddir / "03-add-feature.md").write_text(bodies[3], encoding="utf-8")
        update_step_detail_field(plan_path, 2, "plan-details/merge/02-build-core.md")
        update_step_detail_field(plan_path, 3, "plan-details/merge/03-add-feature.md")

        def _boom(_p: str) -> str:
            raise AssertionError("must not re-author before the marker refusal")

        with pytest.raises(DetailFormatError):
            merge_steps(
                plan_path, merge_ids=[2, 3], repo_root=tmp_path, invoker=_boom
            )

    def test_reauthor_failure_leaves_renumbered_plan_and_orphans(
        self, tmp_path: Path
    ) -> None:
        plan_path = _build_merge_plan(tmp_path)
        ddir = self._detail_member_files(tmp_path, plan_path)
        (ddir / "04-wire-cli.md").write_text(_GOOD_BODY, encoding="utf-8")
        update_step_detail_field(plan_path, 4, "plan-details/merge/04-wire-cli.md")

        def _boom(_p: str) -> str:
            raise RuntimeError("re-author exploded")

        with pytest.raises(RuntimeError, match="exploded"):
            merge_steps(
                plan_path, merge_ids=[2, 3], repo_root=tmp_path, invoker=_boom
            )
        plan = parse_plan(plan_path)
        assert [s.id for s in plan.steps] == [1, 2, 3]
        assert plan.step_by_id(2).title == "Build core"
        assert plan.step_by_id(2).detail is None
        assert plan.step_by_id(3).title == "Wire CLI"
        assert plan.step_by_id(3).detail == "plan-details/merge/03-wire-cli.md"
        assert (ddir / "03-add-feature.md").exists()
        assert (ddir / "03-wire-cli.md").exists()
        assert not (ddir / "archive").exists()

    def test_merged_step_keeps_a_unanimous_member_intent(
        self, tmp_path: Path
    ) -> None:
        shared = "keep the fold simple"
        plan_path = _build_merge_plan(tmp_path, intents={2: shared, 3: shared})
        merge_steps(
            plan_path,
            merge_ids=[2, 3],
            repo_root=tmp_path,
            author_details=False,
        )
        assert parse_plan(plan_path).step_by_id(2).intent == shared

    def test_merged_step_keeps_the_first_members_text_verbatim(
        self, tmp_path: Path
    ) -> None:
        first = "keep the\nfold simple"
        second = "keep  the   fold simple"
        plan_path = _build_merge_plan(tmp_path, intents={2: first, 3: second})
        merge_steps(
            plan_path,
            merge_ids=[2, 3],
            repo_root=tmp_path,
            author_details=False,
        )
        assert parse_plan(plan_path).step_by_id(2).intent == first

    def test_merged_step_clears_on_differing_member_intents(
        self, tmp_path: Path
    ) -> None:
        plan_path = _build_merge_plan(
            tmp_path,
            intents={2: "make the core solid", 3: "add the feature path"},
        )
        merge_steps(
            plan_path,
            merge_ids=[2, 3],
            repo_root=tmp_path,
            author_details=False,
        )
        assert parse_plan(plan_path).step_by_id(2).intent is None

    def test_merged_step_clears_when_a_member_has_no_intent(
        self, tmp_path: Path
    ) -> None:
        plan_path = _build_merge_plan(
            tmp_path, intents={2: "make the core solid", 3: None}
        )
        merge_steps(
            plan_path,
            merge_ids=[2, 3],
            repo_root=tmp_path,
            author_details=False,
        )
        assert parse_plan(plan_path).step_by_id(2).intent is None

    def test_merged_step_clears_when_a_member_intent_is_blank(
        self, tmp_path: Path
    ) -> None:
        plan_path = _build_merge_plan(
            tmp_path, intents={2: "make the core solid", 3: "   "}
        )
        merge_steps(
            plan_path,
            merge_ids=[2, 3],
            repo_root=tmp_path,
            author_details=False,
        )
        assert parse_plan(plan_path).step_by_id(2).intent is None

    def test_merged_step_clears_when_members_are_unanimous_placeholders(
        self, tmp_path: Path
    ) -> None:
        plan_path = _build_merge_plan(
            tmp_path, intents={2: "TODO", 3: "_(TODO)_"}
        )
        merge_steps(
            plan_path,
            merge_ids=[2, 3],
            repo_root=tmp_path,
            author_details=False,
        )
        assert parse_plan(plan_path).step_by_id(2).intent is None

    def test_merged_step_drops_a_unanimous_tbd(self, tmp_path: Path) -> None:
        # ``TBD`` states no why, so a merge that inherited it would carry a
        # placeholder forward as the merged step's purpose. Absent beats a
        # half-true why — same six spellings ``is_placeholder_intent`` owns.
        plan_path = _build_merge_plan(tmp_path, intents={2: "TBD", 3: "TBD"})
        merge_steps(
            plan_path,
            merge_ids=[2, 3],
            repo_root=tmp_path,
            author_details=False,
        )
        assert parse_plan(plan_path).step_by_id(2).intent is None

    def test_merged_step_has_no_intent_when_no_member_carries_one(
        self, tmp_path: Path
    ) -> None:
        plan_path = _build_merge_plan(tmp_path)
        merge_steps(
            plan_path,
            merge_ids=[2, 3],
            repo_root=tmp_path,
            author_details=False,
        )
        assert parse_plan(plan_path).step_by_id(2).intent is None

    def test_merge_leaves_the_plan_intent_untouched(self, tmp_path: Path) -> None:
        plan_path = _build_merge_plan(
            tmp_path, intents={2: "shared why", 3: "shared why"}
        )
        plan = parse_plan(plan_path)
        plan.intent = "prove the whole plan purpose"
        write_plan(plan_path, plan)

        merge_steps(
            plan_path,
            merge_ids=[2, 3],
            repo_root=tmp_path,
            author_details=False,
        )
        assert parse_plan(plan_path).intent == "prove the whole plan purpose"

    def test_merge_writes_no_intent_key_when_nothing_carries_one(
        self, tmp_path: Path
    ) -> None:
        plan_path = _build_merge_plan(tmp_path)
        assert "intent:" not in plan_path.read_text(encoding="utf-8")

        merge_steps(
            plan_path,
            merge_ids=[2, 3],
            repo_root=tmp_path,
            author_details=False,
        )
        assert "intent:" not in plan_path.read_text(encoding="utf-8")

    def test_merge_steps_threads_depends_on_notes(self, tmp_path: Path) -> None:
        from plan_tool.create import _apply_step_merge
        from plan_tool.parser import parse_plan, write_plan

        plan_path = _build_merge_plan(tmp_path)
        plan = parse_plan(plan_path)
        plan.steps[1] = plan.steps[1].model_copy(
            update={"depends_on_notes": {1: "shared outbound note"}}
        )
        plan.steps[2] = plan.steps[2].model_copy(
            update={
                "depends_on": [1, 2],
                "depends_on_notes": {1: "shared outbound note"},
            }
        )
        write_plan(plan_path, plan)

        new_steps = _apply_step_merge(
            plan.steps, [2, 3], Step(id=99, title="Build core")
        )
        survivor = next(s for s in new_steps if s.id == 2)
        assert survivor.depends_on_notes == {1: "shared outbound note"}

        res = merge_steps(
            plan_path,
            merge_ids=[2, 3],
            repo_root=tmp_path,
            dry_run=True,
        )
        assert res.dry_run is True


def test_reground_seed_ignores_depends_on_notes(tmp_path: Path) -> None:
    from plan_tool.reground import render_rebaseline_seed

    note = "must not appear in rebaseline seed"
    plan = Plan(
        title="Reground notes",
        status=PlanStatus.IN_PROGRESS,
        priority=Priority.MEDIUM,
        steps=[
            Step(id=1, title="Done step", status=StepStatus.DONE),
            Step(
                id=2,
                title="Flagged",
                status=StepStatus.CURRENT,
                depends_on=[1],
                depends_on_notes={1: note},
            ),
            Step(id=3, title="Remaining"),
        ],
    )
    seed = render_rebaseline_seed(
        plan=plan, flagged_ids=[1, 2], source_path=tmp_path / "plan.md"
    )
    assert note not in seed


class TestMergeBridge:
    """``merge_bridge``: gated apply-or-recommend wrapper around ``merge_steps``.

    Structured outcome for every path (applied / recommended / unsafe /
    invalid); no raised ``DetailError`` reaches the caller."""

    def test_merge_bridge_recommends_without_opt_in(self, tmp_path: Path) -> None:
        plan_path = _build_merge_plan(tmp_path)
        before = plan_path.read_text(encoding="utf-8")

        def _boom(_p: str) -> str:
            raise AssertionError("recommend path must not author")

        res = merge_bridge(
            plan_path,
            merge_ids=[2, 3],
            allow_merge=False,
            repo_root=tmp_path,
            invoker=_boom,
        )
        assert isinstance(res, MergeBridgeResult)
        assert res.outcome == "recommended"
        assert res.requested_ids == [2, 3]
        assert res.merge_result is not None
        assert res.merge_result.dry_run is True
        assert res.merge_result.renumber == [(1, 1), (2, 2), (3, 2), (4, 3)]
        assert plan_path.read_text(encoding="utf-8") == before
        assert not (tmp_path / "plan-details").exists()

    def test_merge_bridge_applies_when_allowed_and_confirmed(
        self, tmp_path: Path
    ) -> None:
        plan_path = _build_merge_plan(tmp_path)

        def _boom(_m: str) -> str:
            raise AssertionError("yes must bypass the prompt")

        res = merge_bridge(
            plan_path,
            merge_ids=[2, 3],
            allow_merge=True,
            yes=True,
            repo_root=tmp_path,
            invoker=lambda _p: _GOOD_BODY,
            prompt_fn=_boom,
        )
        assert res.outcome == "applied"
        assert res.merge_result is not None
        assert isinstance(res.merge_result, MergeResult)
        assert res.merge_result.dry_run is False
        assert res.merge_result.merged_id == 2
        assert res.apply_error is None  # clean apply carries no error
        plan = parse_plan(plan_path)
        assert [s.id for s in plan.steps] == [1, 2, 3]

    def test_merge_bridge_applied_fold_uses_the_same_intent_rule(
        self, tmp_path: Path
    ) -> None:
        shared = "keep the fold simple"
        plan_path = _build_merge_plan(tmp_path, intents={2: shared, 3: shared})

        def _boom(_m: str) -> str:
            raise AssertionError("yes must bypass the prompt")

        res = merge_bridge(
            plan_path,
            merge_ids=[2, 3],
            allow_merge=True,
            yes=True,
            repo_root=tmp_path,
            invoker=lambda _p: _GOOD_BODY,
            prompt_fn=_boom,
        )
        assert res.outcome == "applied"
        assert parse_plan(plan_path).step_by_id(2).intent == shared

    def test_merge_bridge_authoring_failure_stays_applied_with_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # ``merge_steps`` writes the folded/renumbered plan to disk BEFORE
        # re-authoring the merged step. If authoring then raises ``DetailError``,
        # the bridge must NOT leak it (contract: never a raised DetailError):
        # the fold persisted, so it reports ``applied`` with ``apply_error`` and
        # a ``None`` merge_result — a folded-but-unauthored plan the operator
        # finishes with ``plan-tool detail``.
        import plan_tool.detail as detail_mod

        plan_path = _build_merge_plan(tmp_path)

        # The real apply calls generate_detail AFTER write_plan folds the plan;
        # force it to raise the way a post-write backend/gate failure would. The
        # dry-run preview passes author_details=False so it never reaches here.
        def _raise_author(*_a, **_k):
            raise detail_mod.DetailError("authoring blew up")

        monkeypatch.setattr(detail_mod, "generate_detail", _raise_author)

        res = merge_bridge(
            plan_path,
            merge_ids=[2, 3],
            allow_merge=True,
            yes=True,
            repo_root=tmp_path,
        )
        assert res.outcome == "applied"
        assert res.merge_result is None
        assert res.apply_error is not None
        assert "authoring blew up" in res.apply_error
        # The structural fold DID persist — the plan on disk is renumbered.
        plan = parse_plan(plan_path)
        assert [s.id for s in plan.steps] == [1, 2, 3]

    def test_merge_bridge_failure_before_fold_maps_invalid(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # If the real apply raises BEFORE the fold persists (nothing written),
        # the bridge reports ``invalid`` — not a false ``applied`` — and the
        # plan on disk is unchanged.
        import plan_tool.detail as detail_mod

        plan_path = _build_merge_plan(tmp_path)
        before = plan_path.read_text(encoding="utf-8")

        # Fail the real fold at its first step (dry-run preview is a separate
        # call and stays green, so validity/opt-in/confirm all pass first).
        real_merge_steps = detail_mod.merge_steps

        def _fail_real_merge(*args, **kwargs):
            if kwargs.get("dry_run"):
                return real_merge_steps(*args, **kwargs)
            raise detail_mod.DetailError("fold blew up before any write")

        monkeypatch.setattr(detail_mod, "merge_steps", _fail_real_merge)

        res = merge_bridge(
            plan_path,
            merge_ids=[2, 3],
            allow_merge=True,
            yes=True,
            repo_root=tmp_path,
        )
        assert res.outcome == "invalid"
        assert res.merge_result is None
        assert res.apply_error is None
        assert plan_path.read_text(encoding="utf-8") == before

    def test_merge_bridge_os_error_after_fold_stays_applied(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # An OSError (filesystem infra — the migrate/archive steps) raised while
        # re-authoring, after the fold persisted, must NOT escape merge_bridge:
        # the fold landed, so report applied + apply_error, never leak it.
        import plan_tool.detail as detail_mod

        plan_path = _build_merge_plan(tmp_path)

        def _raise_infra(*_a, **_k):
            raise OSError("disk full during archive")

        monkeypatch.setattr(detail_mod, "generate_detail", _raise_infra)

        res = merge_bridge(
            plan_path,
            merge_ids=[2, 3],
            allow_merge=True,
            yes=True,
            repo_root=tmp_path,
        )
        assert res.outcome == "applied"
        assert res.merge_result is None
        assert "disk full during archive" in res.apply_error
        assert [s.id for s in parse_plan(plan_path).steps] == [1, 2, 3]

    def test_merge_bridge_unexpected_bug_propagates_not_swallowed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A genuine programming bug (e.g. TypeError) raised while re-authoring —
        # even AFTER the fold persisted — is NOT a merge outcome and must NOT be
        # masked as a benign apply_error: it propagates so the defect surfaces
        # (CI/tracebacks) rather than looping the operator on `plan-tool detail`.
        import plan_tool.detail as detail_mod

        plan_path = _build_merge_plan(tmp_path)

        def _bug(*_a, **_k):
            raise TypeError("None has no attribute 'id'")

        monkeypatch.setattr(detail_mod, "generate_detail", _bug)

        with pytest.raises(TypeError, match="None has no attribute"):
            merge_bridge(
                plan_path,
                merge_ids=[2, 3],
                allow_merge=True,
                yes=True,
                repo_root=tmp_path,
            )

    def test_merge_bridge_os_error_before_fold_reraises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # An OSError raised BEFORE any mutation (no partial fold) is a genuine
        # infra failure — re-raise it rather than mask it as a false
        # `invalid`/`applied` outcome; the plan on disk is untouched.
        import plan_tool.detail as detail_mod

        plan_path = _build_merge_plan(tmp_path)
        before = plan_path.read_text(encoding="utf-8")
        real_merge_steps = detail_mod.merge_steps

        def _fail_real_merge(*args, **kwargs):
            if kwargs.get("dry_run"):
                return real_merge_steps(*args, **kwargs)
            raise OSError("exploded before the write")

        monkeypatch.setattr(detail_mod, "merge_steps", _fail_real_merge)

        with pytest.raises(OSError, match="exploded before the write"):
            merge_bridge(
                plan_path,
                merge_ids=[2, 3],
                allow_merge=True,
                yes=True,
                repo_root=tmp_path,
            )
        assert plan_path.read_text(encoding="utf-8") == before

    def test_merge_bridge_declined_confirm_recommends(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        plan_path = _build_merge_plan(tmp_path)
        before = plan_path.read_text(encoding="utf-8")

        res = merge_bridge(
            plan_path,
            merge_ids=[2, 3],
            allow_merge=True,
            repo_root=tmp_path,
            invoker=lambda _p: _GOOD_BODY,
            prompt_fn=lambda _m: "n",
        )
        assert res.outcome == "recommended"
        assert res.merge_result is not None
        assert res.merge_result.dry_run is True
        assert plan_path.read_text(encoding="utf-8") == before

    def test_merge_bridge_unsafe_reports_blocking_ids(self, tmp_path: Path) -> None:
        plan_path = _build_merge_plan(tmp_path, statuses={4: StepStatus.DONE})
        before = plan_path.read_text(encoding="utf-8")

        res = merge_bridge(
            plan_path,
            merge_ids=[2, 3],
            allow_merge=True,
            yes=True,
            repo_root=tmp_path,
            invoker=lambda _p: _GOOD_BODY,
        )
        assert res.outcome == "unsafe"
        assert res.blocking_ids == [4]
        assert res.merge_result is None
        assert plan_path.read_text(encoding="utf-8") == before

    def test_merge_bridge_invalid_maps_detail_error(self, tmp_path: Path) -> None:
        plan_path = _build_merge_plan(tmp_path)
        before = plan_path.read_text(encoding="utf-8")

        res = merge_bridge(
            plan_path,
            merge_ids=[2],
            allow_merge=True,
            yes=True,
            repo_root=tmp_path,
        )
        assert res.outcome == "invalid"
        assert res.merge_result is None
        assert res.blocking_ids == []
        assert plan_path.read_text(encoding="utf-8") == before

    def test_merge_bridge_mints_no_recommendation(self, tmp_path: Path) -> None:
        from plan_tool.review import Recommendation

        plan_path = _build_merge_plan(tmp_path)
        res = merge_bridge(
            plan_path,
            merge_ids=[2, 3],
            allow_merge=False,
            repo_root=tmp_path,
        )
        assert not any(
            isinstance(getattr(res, f), Recommendation)
            for f in ("outcome", "requested_ids", "merge_result", "blocking_ids")
        )


@pytest.mark.integration
class TestGenerateDetailPromptBudget:
    """The pre-send prompt-budget advisory wired into the detail path.

    The advisory fires once per invoked step (skipping resumes), records one
    telemetry event, prints a breakdown on ``--dry-run``, and never changes the
    result or blocks the invoke. Spies delegate to the real leaf so the returned
    ``PromptBudget`` stays valid for the telemetry projection.
    """

    def _spy_warn(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> list[tuple[int, dict]]:
        """Install a delegating spy on ``detail.maybe_warn_prompt_budget``."""
        import threading

        from plan_tool import detail as detail_module
        import plan_tool.prompt_budget as pb

        calls: list[tuple[int, dict]] = []
        lock = threading.Lock()
        real = pb.maybe_warn_prompt_budget

        def spy(total_bytes: int, **kwargs: object):  # type: ignore[no-untyped-def]
            with lock:
                calls.append((total_bytes, dict(kwargs)))
            return real(total_bytes, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(detail_module, "maybe_warn_prompt_budget", spy)
        return calls

    def _spy_record(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> list[dict]:
        """Install a capturing spy on ``detail.record_prompt_budget``."""
        from plan_tool import detail as detail_module

        records: list[dict] = []

        def spy(repo_root, **kwargs):  # type: ignore[no-untyped-def]
            records.append(dict(kwargs))

        monkeypatch.setattr(detail_module, "record_prompt_budget", spy)
        return records

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

    def test_generate_detail_warns_before_invoke(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        calls = self._spy_warn(monkeypatch)
        seen: dict[str, Optional[str]] = {"prompt": None}

        def invoker(prompt: str) -> str:
            seen["prompt"] = prompt
            return _GOOD_BODY

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=invoker,
            extract_lessons=False,
        )
        assert len(calls) == 1
        total_bytes, kwargs = calls[0]
        assert total_bytes == len(seen["prompt"].encode("utf-8"))  # type: ignore[union-attr]
        assert kwargs["blocks"]  # non-empty per-block breakdown
        assert results[0].written is True

    def test_generate_detail_records_prompt_budget(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import plan_tool.prompt_budget as pb

        plan_path = _write_orchestrator_plan(tmp_path)
        records = self._spy_record(monkeypatch)
        seen: dict[str, Optional[str]] = {"prompt": None}

        def invoker(prompt: str) -> str:
            seen["prompt"] = prompt
            return _GOOD_BODY

        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=invoker,
            extract_lessons=False,
        )
        assert len(records) == 1
        rec = records[0]
        total_bytes = len(seen["prompt"].encode("utf-8"))  # type: ignore[arg-type]
        assert rec["phase"] == "detail"
        assert rec["plan_slug"] == "orch"
        assert rec["total_bytes"] == total_bytes
        assert rec["advisory"] == pb.estimate_prompt_budget(total_bytes).level

    def test_shell_detail_invoker_records_named_budget_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.backend import spawn_cwd
        from plan_tool import detail as detail_module
        from plan_tool.detail import shell_detail_invoker

        plan_path = _write_orchestrator_plan(tmp_path)
        self._spy_record(monkeypatch)
        records: list[dict] = []
        monkeypatch.setattr(
            detail_module,
            "record_prompt_budget",
            lambda *a, **k: records.append({"source": "detail", **dict(k)}),
        )
        self._install_fake_shell(monkeypatch, [_GOOD_BODY], records)

        with spawn_cwd(tmp_path):
            results = generate_detail(
                plan_path,
                repo_root=tmp_path,
                step_id=1,
                invoker=shell_detail_invoker,
                extract_lessons=False,
            )

        assert results[0].written is True
        assert [rec["phase"] for rec in records] == ["detail"]
        assert [rec["source"] for rec in records] == ["detail"]

    def test_detail_parse_retry_stays_suppressed_for_shell_backstop(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.backend import spawn_cwd
        from plan_tool.detail import shell_detail_invoker

        plan_path = _write_orchestrator_plan(tmp_path)
        records = self._spy_record(monkeypatch)
        shell_records = self._install_fake_shell(
            monkeypatch, ["not parseable", _GOOD_BODY]
        )

        with spawn_cwd(tmp_path):
            results = generate_detail(
                plan_path,
                repo_root=tmp_path,
                step_id=1,
                invoker=shell_detail_invoker,
                extract_lessons=False,
            )

        assert results[0].written is True
        assert [rec["phase"] for rec in records] == ["detail"]
        assert shell_records == []

    def test_detail_backstop_is_fallback_when_advisory_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the scoped detail advisory raises (and is swallowed), the send
        is NOT suppressed, so the generic shell backstop stays a fallback net
        instead of leaving the prompt with zero budget coverage."""
        from plan_tool.backend import spawn_cwd
        from plan_tool import detail as detail_module
        from plan_tool.detail import shell_detail_invoker

        plan_path = _write_orchestrator_plan(tmp_path)
        # Scoped detail record raises → the advisory returns not-covered.
        monkeypatch.setattr(
            detail_module,
            "record_prompt_budget",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        shell_records = self._install_fake_shell(monkeypatch, [_GOOD_BODY])

        with spawn_cwd(tmp_path):
            results = generate_detail(
                plan_path,
                repo_root=tmp_path,
                step_id=1,
                invoker=shell_detail_invoker,
                extract_lessons=False,
            )

        assert results[0].written is True
        # The scoped record raised → the shell backstop fired instead.
        assert [rec["source"] for rec in shell_records] == ["shell"]
        assert shell_records[0]["phase"] == "shell-backstop"

    def test_advisory_does_not_change_result(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import detail as detail_module
        from plan_tool.prompt_budget import PromptBudget

        plan_path = _write_orchestrator_plan(tmp_path)
        invoked: list[str] = []

        def forced_high(total_bytes: int, **kwargs: object) -> PromptBudget:
            return PromptBudget(
                total_bytes=total_bytes,
                estimated_tokens=total_bytes,
                context_window=200_000,
                headroom_ratio=0.0,
                level="high",
                window_defaulted=True,
                blocks=(),
            )

        monkeypatch.setattr(
            detail_module, "maybe_warn_prompt_budget", forced_high
        )

        def invoker(prompt: str) -> str:
            invoked.append(prompt)
            return _GOOD_BODY

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=invoker,
            extract_lessons=False,
        )
        assert results[0].written is True
        assert len(invoked) == 1

    def test_dry_run_prints_breakdown_and_does_not_invoke(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)

        def boom(prompt: str) -> str:
            raise AssertionError("dry-run must not invoke")

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=boom,
            extract_lessons=False,
            dry_run=True,
        )
        err = capsys.readouterr().err
        assert "prompt budget" in err
        assert "blocks:" in err
        assert results[0].prompt is not None

    def test_dry_run_does_not_record_telemetry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        records = self._spy_record(monkeypatch)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
            dry_run=True,
        )
        assert records == []

    def test_resumed_step_does_not_warn_or_record(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        plan = parse_plan(plan_path)
        step = plan.step_by_id(1)
        ckpt_path = checkpoint_path(
            tmp_path, "orch", _DETAIL_CHECKPOINT_NAME.format(step_id=step.id)
        )
        save_checkpoint(
            ckpt_path,
            Checkpoint(
                input_hash=_detail_step_input_hash(plan_path, step),
                payload=_GOOD_BODY,
                created_at=_fresh_now(),
            ),
        )
        warn_calls = self._spy_warn(monkeypatch)
        records = self._spy_record(monkeypatch)

        def boom(prompt: str) -> str:
            raise AssertionError("resume must not invoke")

        results = generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=boom,
            extract_lessons=False,
        )
        assert results[0].written is True
        assert warn_calls == []
        assert records == []

    def test_budget_blocks_include_file_contents(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = _write_orchestrator_plan(tmp_path)
        calls = self._spy_warn(monkeypatch)
        generate_detail(
            plan_path,
            repo_root=tmp_path,
            step_id=1,
            invoker=lambda _p: _GOOD_BODY,
            extract_lessons=False,
        )
        assert len(calls) == 1
        blocks = dict(calls[0][1]["blocks"])
        assert blocks.get("file-contents", 0) > 0

    def test_concurrent_path_warns_before_invoke(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plan_path = _write_concurrent_plan(tmp_path / "c")
        calls = self._spy_warn(monkeypatch)
        generate_detail(
            plan_path,
            repo_root=tmp_path / "c",
            invoker=lambda _p: _GOOD_BODY,
            reporter=NullReporter(),
            extract_lessons=False,
            jobs=2,
        )
        # Four fresh steps → one advisory per invoked step, from the worker.
        assert len(calls) == 4


def test_extract_plan_references_ignores_fenced_pseudo_heading_and_preserves_body(
    tmp_path: Path,
) -> None:
    plan_path = _write_plan_with_references(
        tmp_path,
        "```markdown\n## Example reference heading\n- Example-only text.\n```\n\n"
        "- [Real Docs](https://example.test/docs)\n",
    )

    references = extract_plan_references(plan_path)

    assert "## Example reference heading" in references
    assert "Example-only text." in references
    assert "Real Docs" in references
    assert "steps:` block" not in references


def test_candidate_body_buckets_ignore_fenced_pseudo_heading(tmp_path: Path) -> None:
    from plan_tool.detail import derive_candidate_buckets

    plan_path = _write_detail_plan_with_sections(tmp_path)
    plan_text = plan_path.read_text(encoding="utf-8").replace(
        "Some overview prose.\n\n",
        "Some overview prose.\n\n```markdown\n## Example bucket\n```\n\n",
    )

    buckets = derive_candidate_buckets(parse_plan(plan_path), plan_text)

    names = {bucket.lower() for bucket in buckets.values()}
    assert "overview" in names
    assert "risks" in names
    assert "example bucket" not in names


@pytest.mark.parametrize("empty_heading", ["## :", "## ."], ids=["colon", "period"])
def test_candidate_buckets_refuse_a_heading_with_no_name_naming_it(
    tmp_path: Path, empty_heading: str
) -> None:
    """A hand-edited plan can hold a heading whose name is empty after
    normalization; ``concept_id`` would raise a bare ``ValueError`` naming
    nothing. ``detail`` refuses with the same text ``create`` uses."""
    from plan_tool.detail import derive_candidate_buckets

    plan_path = _write_detail_plan_with_sections(tmp_path)
    plan_text = plan_path.read_text(encoding="utf-8") + f"\n{empty_heading}\n\nbody.\n"

    with pytest.raises(DetailError) as excinfo:
        derive_candidate_buckets(parse_plan(plan_path), plan_text)

    message = str(excinfo.value)
    assert "no name after normalization" in message
    assert f"'{empty_heading}'" in message


def test_candidate_buckets_keep_a_zero_width_only_heading(tmp_path: Path) -> None:
    """Carve-out: a zero-width space is not whitespace to ``str.split``, so the
    heading has a non-empty (invisible) name and is neither refused nor a crash."""
    from plan_tool.detail import derive_candidate_buckets

    plan_path = _write_detail_plan_with_sections(tmp_path)
    plan_text = plan_path.read_text(encoding="utf-8") + "\n## \u200b\n\nbody.\n"

    assert derive_candidate_buckets(parse_plan(plan_path), plan_text)


def test_detail_render_and_pointer_update_keep_description_step_text(tmp_path):
    import yaml
    from plan_tool.parser import parse_plan, parse_plan_text, render_plan_text, split_plan_document
    from plan_tool.detail import render_detail_prompt, update_step_detail_field

    plan = parse_plan_text("---\ntitle: Plan\nstatus: planning\npriority: medium\nsteps:\n- id: 1\n  description: Exact step text\n---\n")
    path = tmp_path / "plan.md"
    path.write_text(render_plan_text(plan, "# Body\n"))
    assert "Exact step text" in render_detail_prompt(plan, plan.steps[0], repo_root=tmp_path)
    update_step_detail_field(path, 1, "details/one.md")
    step = yaml.safe_load(split_plan_document(path.read_text()).frontmatter_yaml)["steps"][0]
    assert step["description"] == "Exact step text"
    assert "title" not in step
    assert parse_plan(path).steps[0].detail == "details/one.md"
    assert parse_plan(path).steps[0].title == "Exact step text"


def test_jira_grade_authoring_symbols_are_not_exposed() -> None:
    from plan_tool import detail

    for name in ("render_jira_detail_prompt", "_generate_jira_detail", "derive_jira_detail_path"):
        assert not hasattr(detail, name)
    for writer in (detail.generate_detail, detail._author_step_detail, detail._parse_detail_plan_and_dispatch):
        assert "grade" not in inspect.signature(writer).parameters


def test_run_grade_worker_preserves_replacement_checkpoint_and_saved_output(tmp_path: Path) -> None:
    from plan_tool import detail

    plan_path = _write_orchestrator_plan(tmp_path)
    plan = parse_plan(plan_path)
    step = plan.step_by_id(1)
    canonical = detail.derive_detail_path(plan_path, plan, step)
    canonical.parent.mkdir(parents=True)
    canonical.write_text("prior detail\n", encoding="utf-8")
    checkpoint = tmp_path / "checkpoint.json"
    outcome = detail._author_step_detail(
        step, prompt="author detail", output_path=canonical, cached=None,
        input_hash="test-hash", ckpt_path=checkpoint, ckpt_name="detail-step-01",
        plan_slug="orch", phase_name="detail-step-01", invoke_idx=0,
        invoke_total=1, reporter=NullReporter(), run_logger=None,
        invoker=lambda _prompt: _GOOD_BODY, repo_root=tmp_path,
        plan_path=plan_path, capture_scenarios=False, arm=None,
        foundational_invoker=None,
    )
    assert outcome.succeeded
    assert outcome.update == (1, canonical.relative_to(tmp_path).as_posix())
    assert "Wire up the renderer" in canonical.read_text(encoding="utf-8")
    assert checkpoint.is_file()  # The caller retains recovery until it saves the pointer.
    archives = list((canonical.parent / "archive").glob("*.md"))
    assert len(archives) == 1
    assert archives[0].read_text(encoding="utf-8") == "prior detail\n"


def test_retired_jira_detail_parser_is_not_exposed() -> None:
    import plan_tool.detail as detail_module

    assert not {"JiraDetailParse", "parse_jira_detail_response"} & vars(detail_module).keys()
