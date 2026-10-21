"""Tests for plan_tool.lessons.

Pure in-memory / tmp-path tests. No claude shell-out — extraction calls
live in callers (review.py, detail.py) and are exercised by their own
test suites with injected invokers.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from plan_tool import lessons, style
from plan_tool.lessons import (
    DEFAULT_EQUIVALENCE_CONFIDENCE,
    GENERAL_FILENAME,
    GENERAL_LESSONS_REL,
    LESSON_SURFACES,
    LESSONS_EQUIVALENCE_SLUG,
    PENDING_LESSONS_DIRNAME,
    PROJECT_FILENAME,
    PROJECT_LESSONS_REL,
    WARNINGS_FILENAME,
    WARNINGS_REL,
    AppendLessonsResult,
    EquivalenceFinding,
    EquivalenceFindings,
    EquivalenceKind,
    LessonEntry,
    LessonsBundle,
    LessonsFile,
    LessonsWarning,
    _append_citation_jsonl,
    _equivalence_input_hash,
    _render_equivalence_prompt,
    _rule_hash,
    append_lessons,
    append_pending_lessons,
    append_warning,
    discover_lessons_files,
    find_lesson_equivalences,
    general_citations_path,
    general_lessons_dir,
    general_path,
    load_lessons,
    load_warnings,
    parse_equivalence_response,
    parse_existing_entries,
    parse_lessons_extract_response,
    pending_lessons_path,
    project_citations_path,
    project_lessons_dir,
    project_path,
    recurrence_counts,
    recurrence_weight_from_counts,
    render_consolidated_file,
    render_lessons_block,
    shell_equivalence_invoker,
    warnings_log_path,
)
from plan_tool.checkpoint import (
    Checkpoint,
    checkpoint_path,
    save_checkpoint,
)


def test_review_lesson_prompt_includes_stored_confidence(tmp_path: Path) -> None:
    """Lesson synthesis sees legacy evidence support without reclassifying it."""
    from plan_tool.review import Recommendation, _render_extract_lessons_prompt

    prompt = _render_extract_lessons_prompt(
        plan_name="demo",
        plan_title="Demo",
        report_md="report",
        recommendations=[
            Recommendation(
                id="legacy", source="plan-completeness", severity="medium",
                step_id=None, title="Need an invariant", body="State it.",
                confidence=None,
            )
        ],
        repo_root=tmp_path,
    )

    assert "confidence: unknown" in prompt
    assert "never\n  weaken, reclassify, or suppress" in prompt


def test_review_lesson_prompt_keeps_a_multiline_body_inside_its_list_item(tmp_path: Path) -> None:
    """A fenced citation at column 0 would end the bullet and fuse the quoted
    plan text with the next finding the lessons model reads."""
    from plan_tool.review import Recommendation, _render_extract_lessons_prompt

    prompt = _render_extract_lessons_prompt(
        plan_name="demo",
        plan_title="Demo",
        report_md="report",
        recommendations=[
            Recommendation(
                id="fenced", source="plan-correctness", severity="high",
                step_id=None, title="Quoted plan text",
                body="It contradicts:\n```text\n## Stack\n```\nFix it.",
                confidence="supported",
            )
        ],
        repo_root=tmp_path,
    )

    lines = prompt.splitlines()
    start = next(i for i, ln in enumerate(lines) if "**Quoted plan text**" in ln)
    assert lines[start + 1] == "  ```text"
    assert lines[start + 2] == "  ## Stack"


# ---------- path helpers ----------

def test_general_lessons_live_in_user_home(tmp_path: Path) -> None:
    """``general_lessons_dir`` resolves under ``Path.home()`` so the
    portable plan-authoring rules accumulate across every repo this
    user runs plan-tool against. The autouse ``HOME``-redirection
    fixture in ``conftest.py`` pins ``Path.home()`` to a per-test temp
    dir, so the assertion is stable.
    """
    expected = Path.home().joinpath(*GENERAL_LESSONS_REL)
    assert general_lessons_dir(tmp_path) == expected
    assert general_path(tmp_path) == expected / GENERAL_FILENAME
    # Lives under ``~/.plan-tool/`` — sanity-check the constant matches
    # the docstring.
    assert GENERAL_LESSONS_REL[0] == ".plan-tool"


def test_project_lessons_live_under_repo_root(tmp_path: Path) -> None:
    """Project lessons stay per-repo: rooted at ``repo_root``, not home."""
    expected = tmp_path.joinpath(*PROJECT_LESSONS_REL)
    assert project_lessons_dir(tmp_path) == expected
    assert project_path(tmp_path) == expected / PROJECT_FILENAME
    assert PROJECT_LESSONS_REL[0] == ".plan-tool"


# ---------- load_lessons ----------

def test_load_lessons_returns_empty_bundle_when_files_absent(tmp_path: Path) -> None:
    bundle = load_lessons(tmp_path)
    assert bundle.general == ""
    assert bundle.project == ""
    assert bundle.is_empty


def test_load_lessons_reads_both_files_when_present(tmp_path: Path) -> None:
    gp = general_path(tmp_path)
    pp = project_path(tmp_path)
    gp.parent.mkdir(parents=True)
    pp.parent.mkdir(parents=True)
    gp.write_text("# General\n- rule one\n", encoding="utf-8")
    pp.write_text("# Project\n- fact one\n", encoding="utf-8")

    bundle = load_lessons(tmp_path)

    assert "rule one" in bundle.general
    assert "fact one" in bundle.project
    assert not bundle.is_empty


def test_load_lessons_truncates_oversize_body(tmp_path: Path) -> None:
    gp = general_path(tmp_path)
    gp.parent.mkdir(parents=True)
    big = "# General\n" + ("- x" * 5000)
    gp.write_text(big, encoding="utf-8")

    bundle = load_lessons(tmp_path, max_bytes=512)

    assert "older entries truncated" in bundle.general
    assert len(bundle.general) <= 512 + 200  # header + tail marker slop


def test_load_lessons_keeps_newest_bullets_on_truncation(tmp_path: Path) -> None:
    gp = general_path(tmp_path)
    gp.parent.mkdir(parents=True)
    # Oldest first — appends land at the tail, so truncation must keep 049.
    body = "# General\n\n" + "".join(
        f"- bullet number {i:03d} with padding text to take up space\n"
        for i in range(50)
    )
    gp.write_text(body, encoding="utf-8")

    bundle = load_lessons(tmp_path, max_bytes=300)

    assert "older entries truncated" in bundle.general
    assert "bullet number 049" in bundle.general  # newest kept
    assert "bullet number 000" not in bundle.general  # oldest dropped


def test_load_lessons_filters_by_surface(tmp_path: Path) -> None:
    gp = general_path(tmp_path)
    gp.parent.mkdir(parents=True)
    gp.write_text(
        "# General\n\n"
        "- `[detail-authoring]` keep me\n"
        "- `[create-heuristic]` drop me\n"
        "- untagged stays\n",
        encoding="utf-8",
    )

    bundle = load_lessons(tmp_path, surfaces=frozenset({"detail-authoring"}))

    assert "keep me" in bundle.general
    assert "untagged stays" in bundle.general  # untagged applies everywhere
    assert "drop me" not in bundle.general


# ---------- render_lessons_block ----------

def test_render_block_for_empty_bundle_returns_placeholder() -> None:
    block = render_lessons_block(LessonsBundle(general="", project=""))
    assert "no lessons captured yet" in block


def test_render_block_includes_both_sections() -> None:
    bundle = LessonsBundle(
        general="# General\n- rule G\n",
        project="# Project\n- fact P\n",
    )
    block = render_lessons_block(bundle)

    assert "rule G" in block
    assert "fact P" in block
    assert "authoritative context" in block


def test_render_block_skips_empty_section() -> None:
    bundle = LessonsBundle(general="# General\n- rule G\n", project="")
    block = render_lessons_block(bundle)

    assert "rule G" in block
    assert "# Project" not in block


# ---------- append_lessons ----------

def _fixed_now() -> datetime:
    return datetime(2026, 5, 12, 0, 0, 0, tzinfo=timezone.utc)


def test_append_creates_file_and_returns_count(tmp_path: Path) -> None:
    n_g, n_p = append_lessons(
        tmp_path,
        general=[LessonEntry(rule="Verify file paths before proposing", why="dedupe")],
        project=[LessonEntry(rule="AppSync subs only fire on resolver mutations")],
        source="review:test",
        now=_fixed_now(),
    )

    assert (n_g, n_p) == (1, 1)
    assert general_path(tmp_path).is_file()
    assert project_path(tmp_path).is_file()

    g_body = general_path(tmp_path).read_text()
    assert "Verify file paths" in g_body
    assert "General plan-authoring lessons" in g_body  # header inserted
    # Source / date are no longer rendered inline as <sub>; they land in
    # the citations JSONL sidecar so the bullet body stays dense.
    assert "<sub>" not in g_body
    assert "review:test" not in g_body

    g_citations = general_citations_path(tmp_path).read_text()
    assert "review:test" in g_citations  # source stamped in sidecar
    assert "2026-05-12" in g_citations  # added date stamped in sidecar
    record = json.loads(g_citations.strip().splitlines()[0])
    assert record["source"] == "review:test"
    assert record["added"] == "2026-05-12"
    assert record["rule_hash"] == _rule_hash("Verify file paths before proposing")
    assert record["rule_preview"].startswith("Verify file paths before proposing")


def test_append_dedupes_by_case_insensitive_substring(tmp_path: Path) -> None:
    append_lessons(
        tmp_path,
        general=[LessonEntry(rule="Verify file paths before proposing")],
        source="review:first",
        now=_fixed_now(),
    )
    # Same rule, different case, with extra prose — should be deduped.
    n_g, _ = append_lessons(
        tmp_path,
        general=[LessonEntry(rule="VERIFY FILE PATHS before proposing")],
        source="review:second",
        now=_fixed_now(),
    )

    assert n_g == 0
    body = general_path(tmp_path).read_text()
    assert body.count("Verify file paths") == 1


def test_append_skips_empty_rules(tmp_path: Path) -> None:
    n_g, n_p = append_lessons(
        tmp_path,
        general=[LessonEntry(rule="   "), LessonEntry(rule="")],
        project=[LessonEntry(rule="")],
        source="review:test",
        now=_fixed_now(),
    )
    assert (n_g, n_p) == (0, 0)
    assert not general_path(tmp_path).exists()
    assert not project_path(tmp_path).exists()


def test_append_preserves_existing_entries(tmp_path: Path) -> None:
    append_lessons(
        tmp_path,
        general=[LessonEntry(rule="First lesson")],
        source="review:one",
        now=_fixed_now(),
    )
    append_lessons(
        tmp_path,
        general=[LessonEntry(rule="Second lesson")],
        source="review:two",
        now=_fixed_now(),
    )

    body = general_path(tmp_path).read_text()
    assert "First lesson" in body
    assert "Second lesson" in body
    assert body.index("First lesson") < body.index("Second lesson")
    # Sidecar accumulates one record per appended bullet, in order.
    citations = general_citations_path(tmp_path).read_text().strip().splitlines()
    assert len(citations) == 2
    assert json.loads(citations[0])["source"] == "review:one"
    assert json.loads(citations[1])["source"] == "review:two"


def test_append_routes_repo_scoped_general_lesson_to_project_store(
    tmp_path: Path,
) -> None:
    """A model's broad bucket choice cannot leak a vendor fact globally."""
    entry = LessonEntry(
        rule=(
            "Use `VendorCredentialsSecret` for "
            "`/example/app/{i}/vendor/credentials`."
        )
    )

    result = append_lessons(
        tmp_path, general=[entry], source="review:vendor", now=_fixed_now()
    )

    assert result.n_general_added == 0
    assert result.n_project_added == 1
    assert result.n_general_routed_to_project == 1
    assert not general_path(tmp_path).exists()
    assert "VendorCredentialsSecret" in project_path(tmp_path).read_text(
        encoding="utf-8"
    )


def test_append_routes_a_resolving_project_path_to_project_store(
    tmp_path: Path,
) -> None:
    credential_path = tmp_path / "vendor" / "credentials"
    credential_path.parent.mkdir()
    credential_path.write_text("secret", encoding="utf-8")

    result = append_lessons(
        tmp_path,
        general=[LessonEntry(rule="Read `vendor/credentials` before deployment.")],
        source="review:vendor-path",
        now=_fixed_now(),
    )

    assert result.n_general_added == 0
    assert result.n_project_added == 1
    assert result.n_general_routed_to_project == 1
    assert not general_path(tmp_path).exists()
    assert "vendor/credentials" in project_path(tmp_path).read_text(
        encoding="utf-8"
    )


def test_append_keeps_plan_tool_package_citation_in_general_store(
    tmp_path: Path,
) -> None:
    """Only ``plan_tool/`` is carved out — a rule about driving this tool."""
    entry = LessonEntry(
        rule="Use `Plan` intent when grounding changes in `plan_tool/detail.py`."
    )

    result = append_lessons(
        tmp_path, general=[entry], source="review:generic", now=_fixed_now()
    )

    assert result.n_general_added == 1
    assert result.n_project_added == 0
    assert result.n_general_routed_to_project == 0
    assert "Plan" in general_path(tmp_path).read_text(encoding="utf-8")
    assert not project_path(tmp_path).exists()


@pytest.mark.parametrize("rel", ["tests/fixtures/vendor.json", "docs/runbook.md"])
def test_append_routes_consuming_repo_tests_and_docs_to_project(
    tmp_path: Path, rel: str
) -> None:
    """``tests/`` and ``docs/`` are every repo's directories, not plan-tool's.

    Exempting them by name waved a consuming project's own files into the
    cross-project store — the exact leak the gate exists to stop, in exactly
    the repos it was filed for.
    """
    target = tmp_path / rel
    target.parent.mkdir(parents=True)
    target.write_text("x", encoding="utf-8")

    result = append_lessons(
        tmp_path,
        general=[LessonEntry(rule=f"Seed the stub from `{rel}` first.")],
        source="review:consuming-repo",
        now=_fixed_now(),
    )

    assert result.n_general_added == 0
    assert result.n_project_added == 1
    assert rel in project_path(tmp_path).read_text(encoding="utf-8")


def test_append_does_not_route_on_a_bare_symbol(tmp_path: Path) -> None:
    """The accepted known limit, pinned so a re-added proxy fails loudly.

    A CamelCase-symbol pass shipped here and was removed 2026-08-06: nothing
    separates ``VendorCredentialsSecret`` from ``GitHub`` without measuring
    vocabulary, and the shipped version silently demoted ordinary portable
    prose. Routing keys on path *resolution* only. Do not "fix" this by
    re-adding a lexical symbol rule — see the note in ``lessons.py``.
    """
    result = append_lessons(
        tmp_path,
        general=[
            LessonEntry(rule="Prefer a GitHub PR over a long-lived branch."),
            LessonEntry(rule="Name the step's PlanStatus explicitly."),
        ],
        source="review:symbols",
        now=_fixed_now(),
    )

    assert result.n_general_added == 2
    assert result.n_general_routed_to_project == 0
    assert not project_path(tmp_path).exists()


# ---------- surface tag + trigger rendering ----------


def test_render_includes_surface_prefix_when_set() -> None:
    entry = LessonEntry(
        rule="Always cite the sibling template",
        why="forecloses style debates",
        surface="detail-authoring",
    )
    rendered = entry.render()
    assert rendered.startswith("- `[detail-authoring]` **Always cite the sibling template**")
    assert "<sub>" not in rendered
    assert "forecloses style debates" in rendered


def test_render_omits_surface_prefix_when_empty() -> None:
    entry = LessonEntry(rule="Verify paths", why="dedupe")
    rendered = entry.render()
    assert rendered.startswith("- **Verify paths** — dedupe")
    assert "[" not in rendered.split("**")[0]  # no prefix tag


def test_render_includes_trigger_clause_when_set() -> None:
    entry = LessonEntry(
        rule="files:[] is wrong for UI steps",
        why="creates miscategorization",
        trigger="when create proposes files:[] for a UI-feature step",
        example="step 9 here",
        surface="create-heuristic",
    )
    rendered = entry.render()
    assert "_(when: when create proposes files:[] for a UI-feature step)_" in rendered
    assert "_(e.g. step 9 here)_" in rendered
    # trigger comes before example
    assert rendered.index("when:") < rendered.index("e.g.")


def test_append_writes_surface_prefix_into_body(tmp_path: Path) -> None:
    append_lessons(
        tmp_path,
        general=[
            LessonEntry(
                rule="Steps with new model + new lambda + new util are L-min",
                surface="create-heuristic",
            )
        ],
        source="detail:foo#1",
        now=_fixed_now(),
    )
    body = general_path(tmp_path).read_text()
    assert "`[create-heuristic]`" in body


def test_parse_extracts_surface_and_trigger() -> None:
    raw = """{
      "general": [
        {
          "rule": "rule one",
          "why": "because",
          "example": "x",
          "surface": "create-heuristic",
          "trigger": "when X happens"
        }
      ],
      "project": []
    }"""
    parsed = parse_lessons_extract_response(raw)
    assert parsed is not None
    general, _ = parsed
    assert general[0].surface == "create-heuristic"
    assert general[0].trigger == "when X happens"


def test_parse_drops_unknown_surface_to_empty() -> None:
    raw = """{
      "general": [
        {"rule": "rule one", "surface": "make-up-tag"}
      ],
      "project": []
    }"""
    parsed = parse_lessons_extract_response(raw)
    assert parsed is not None
    general, _ = parsed
    assert general[0].rule == "rule one"
    assert general[0].surface == ""  # unknown tag silently dropped


def test_lesson_surfaces_constant_matches_documented_set() -> None:
    # If LESSON_SURFACES changes, the two extract-lessons prompts also
    # have to change. This test pins the tuple so a drift between code
    # and prompts is loud.
    assert LESSON_SURFACES == (
        "create-heuristic",
        "detail-authoring",
        "review-heuristic",
        "cross-step",
        "domain-shape",
    )


# ---------- parse_lessons_extract_response ----------

def test_parse_valid_response() -> None:
    raw = """Some preamble.
    {
      "general": [
        {"rule": "rule one", "why": "because", "example": "see file.ts"}
      ],
      "project": [
        {"rule": "fact one", "why": "", "example": ""}
      ]
    }
    trailing chatter
    """
    parsed = parse_lessons_extract_response(raw)
    assert parsed is not None
    general, project = parsed
    assert len(general) == 1
    assert general[0].rule == "rule one"
    assert general[0].why == "because"
    assert general[0].example == "see file.ts"
    assert len(project) == 1
    assert project[0].rule == "fact one"


def test_parse_handles_empty_arrays() -> None:
    parsed = parse_lessons_extract_response('{"general": [], "project": []}')
    assert parsed == ([], [])


def test_parse_returns_none_for_unparseable_json() -> None:
    assert parse_lessons_extract_response("not json at all") is None
    assert parse_lessons_extract_response("{not: valid}") is None


def test_parse_returns_none_when_top_level_not_object() -> None:
    assert parse_lessons_extract_response('["just", "an", "array"]') is None


def test_parse_returns_none_when_arrays_missing() -> None:
    # The fields default to empty list if absent — but if present as
    # non-list, the response is malformed.
    assert parse_lessons_extract_response('{"general": "wrong type"}') is None


def test_parse_drops_entries_without_rule() -> None:
    raw = """{
      "general": [
        {"rule": "good"},
        {"rule": "  "},
        {"rule": ""},
        {"why": "no rule field"}
      ],
      "project": []
    }"""
    parsed = parse_lessons_extract_response(raw)
    assert parsed is not None
    general, _ = parsed
    assert len(general) == 1
    assert general[0].rule == "good"


# ---------- equivalence primitive: fake invoker fixture ----------


class _FakeInvoker:
    """Callable invoker that records prompts and returns a canned response."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.response


# ---------- parse_equivalence_response ----------


class TestParseEquivalenceResponse:
    def test_parse_valid_response(self) -> None:
        raw = """{
          "duplicates": [
            {"left_index": 1, "right_index": 2, "confidence": 0.9, "rationale": "same"}
          ],
          "conflicts": [
            {"left_index": 3, "right_index": 4, "confidence": 0.8, "rationale": "opposite"}
          ]
        }"""
        parsed = parse_equivalence_response(raw)
        assert parsed is not None
        assert len(parsed.duplicates) == 1
        assert parsed.duplicates[0].kind is EquivalenceKind.DUPLICATE
        assert parsed.duplicates[0].left_index == 1
        assert parsed.duplicates[0].right_index == 2
        assert parsed.duplicates[0].confidence == 0.9
        assert parsed.duplicates[0].rationale == "same"
        assert len(parsed.conflicts) == 1
        assert parsed.conflicts[0].kind is EquivalenceKind.CONFLICT
        assert parsed.conflicts[0].rationale == "opposite"

    def test_parse_handles_chatter_around_json(self) -> None:
        raw = (
            "Here are my findings.\n\n"
            '{"duplicates": [{"left_index": 1, "right_index": 2, "confidence": 0.75}], '
            '"conflicts": []}\n'
            "Hope this helps!"
        )
        parsed = parse_equivalence_response(raw)
        assert parsed is not None
        assert len(parsed.duplicates) == 1
        assert parsed.duplicates[0].left_index == 1

    def test_parse_returns_none_for_unparseable_json(self) -> None:
        assert parse_equivalence_response("not json at all") is None
        assert parse_equivalence_response("{not: valid}") is None

    def test_parse_returns_none_when_top_level_not_object(self) -> None:
        assert parse_equivalence_response('["just", "an", "array"]') is None

    def test_parse_returns_none_when_arrays_wrong_type(self) -> None:
        assert (
            parse_equivalence_response('{"duplicates": "x", "conflicts": []}') is None
        )

    def test_parse_drops_items_missing_required_fields(self) -> None:
        raw = """{
          "duplicates": [
            {"left_index": 1, "right_index": 2, "confidence": 0.9, "rationale": "ok"},
            {"right_index": 2, "confidence": 0.9},
            {"left_index": 1, "confidence": 0.9},
            {"left_index": 1, "right_index": 2}
          ],
          "conflicts": []
        }"""
        parsed = parse_equivalence_response(raw)
        assert parsed is not None
        assert len(parsed.duplicates) == 1
        assert parsed.duplicates[0].rationale == "ok"

    def test_parse_drops_items_with_confidence_out_of_range(self) -> None:
        raw = """{
          "duplicates": [
            {"left_index": 1, "right_index": 2, "confidence": 1.7},
            {"left_index": 1, "right_index": 2, "confidence": -0.1},
            {"left_index": 1, "right_index": 2, "confidence": 0.0},
            {"left_index": 1, "right_index": 2, "confidence": 1.0}
          ],
          "conflicts": []
        }"""
        parsed = parse_equivalence_response(raw)
        assert parsed is not None
        assert len(parsed.duplicates) == 2
        confidences = sorted(f.confidence for f in parsed.duplicates)
        assert confidences == [0.0, 1.0]

    def test_parse_assigns_kind_per_array(self) -> None:
        raw = """{
          "duplicates": [
            {"left_index": 1, "right_index": 2, "confidence": 0.8}
          ],
          "conflicts": [
            {"left_index": 3, "right_index": 4, "confidence": 0.8}
          ]
        }"""
        parsed = parse_equivalence_response(raw)
        assert parsed is not None
        assert all(f.kind is EquivalenceKind.DUPLICATE for f in parsed.duplicates)
        assert all(f.kind is EquivalenceKind.CONFLICT for f in parsed.conflicts)

    def test_parse_defaults_missing_rationale_to_empty_string(self) -> None:
        raw = '{"duplicates": [{"left_index": 1, "right_index": 2, "confidence": 0.8}], "conflicts": []}'
        parsed = parse_equivalence_response(raw)
        assert parsed is not None
        assert parsed.duplicates[0].rationale == ""


# ---------- _render_equivalence_prompt ----------


class TestEquivalencePromptRender:
    def test_render_includes_numbered_existing(self) -> None:
        existing = [
            LessonEntry(rule="rule A", why="why A"),
            LessonEntry(rule="rule B"),
        ]
        prompt = _render_equivalence_prompt(existing, [])
        assert "1. **rule A**" in prompt
        assert "2. **rule B**" in prompt

    def test_render_collapses_empty_why_and_example(self) -> None:
        prompt = _render_equivalence_prompt([LessonEntry(rule="x")], [])
        # No trailing em-dash clause, no example clause.
        assert "1. **x**" in prompt
        assert "**x** —" not in prompt
        assert "_(e.g." not in prompt

    def test_render_empty_candidates_block_uses_intra_set_marker(self) -> None:
        existing = [LessonEntry(rule="rule A")]
        prompt = _render_equivalence_prompt(existing, [])
        assert "no candidates" in prompt
        assert "existing-vs-existing" in prompt

    def test_render_empty_existing_block_uses_no_existing_marker(self) -> None:
        candidates = [LessonEntry(rule="rule X")]
        prompt = _render_equivalence_prompt([], candidates)
        assert "_(no existing lessons)_" in prompt
        assert "1. **rule X**" in prompt

    def test_render_loads_template_from_prompts_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_template = tmp_path / "lessons-equivalence.md"
        fake_template.write_text(
            "TOP\n\nEXISTING:\n${existing_block}\n\nCANDIDATES:\n${candidates_block}\nEND",
            encoding="utf-8",
        )
        monkeypatch.setattr("plan_tool.lessons.prompts_dir", lambda: tmp_path)
        prompt = _render_equivalence_prompt(
            [LessonEntry(rule="rule A")], [LessonEntry(rule="rule X")]
        )
        assert prompt.startswith("TOP")
        assert prompt.endswith("END")
        assert "1. **rule A**" in prompt
        assert "1. **rule X**" in prompt


# ---------- find_lesson_equivalences ----------


_CANNED_FINDINGS_JSON = (
    '{"duplicates": [{"left_index": 1, "right_index": 2, '
    '"confidence": 0.9, "rationale": "same"}], '
    '"conflicts": []}'
)


def _two_existing() -> list[LessonEntry]:
    return [LessonEntry(rule="rule A"), LessonEntry(rule="rule B")]


class TestFindLessonEquivalences:
    def test_invokes_with_rendered_prompt(self) -> None:
        invoker = _FakeInvoker(_CANNED_FINDINGS_JSON)
        existing = _two_existing()
        find_lesson_equivalences(existing, invoker=invoker)
        assert len(invoker.calls) == 1
        expected_prompt = _render_equivalence_prompt(existing, [])
        assert invoker.calls[0] == expected_prompt

    def test_returns_parsed_findings_when_response_is_valid_json(self) -> None:
        invoker = _FakeInvoker(_CANNED_FINDINGS_JSON)
        findings = find_lesson_equivalences(_two_existing(), invoker=invoker)
        assert len(findings.duplicates) == 1
        assert findings.duplicates[0].rationale == "same"
        assert findings.conflicts == ()

    def test_returns_empty_findings_when_response_is_unparseable(self) -> None:
        invoker = _FakeInvoker("not json")
        findings = find_lesson_equivalences(_two_existing(), invoker=invoker)
        assert findings.is_empty

    def test_filters_below_min_confidence(self) -> None:
        canned = (
            '{"duplicates": ['
            '{"left_index": 1, "right_index": 2, "confidence": 0.4},'
            '{"left_index": 1, "right_index": 2, "confidence": 0.8}'
            '], "conflicts": []}'
        )
        invoker = _FakeInvoker(canned)
        findings = find_lesson_equivalences(_two_existing(), invoker=invoker)
        assert len(findings.duplicates) == 1
        assert findings.duplicates[0].confidence == 0.8

    def test_min_confidence_override_passes_through(self) -> None:
        canned = (
            '{"duplicates": ['
            '{"left_index": 1, "right_index": 2, "confidence": 0.8}'
            '], "conflicts": []}'
        )
        invoker = _FakeInvoker(canned)
        findings = find_lesson_equivalences(
            _two_existing(), invoker=invoker, min_confidence=0.9
        )
        assert findings.is_empty

    def test_no_repo_root_skips_checkpoint_path(self, tmp_path: Path) -> None:
        # repo_root=None → no checkpoint dir created.
        invoker = _FakeInvoker(_CANNED_FINDINGS_JSON)
        find_lesson_equivalences(_two_existing(), invoker=invoker, repo_root=None)
        assert len(invoker.calls) == 1
        # Sanity: ensure no .plan-tool dir was created in the cwd of the test —
        # but a more direct check is that tmp_path stays clean.
        assert not (tmp_path / ".plan-tool").exists()

    def test_checkpoint_hit_skips_invoker(self, tmp_path: Path) -> None:
        existing = _two_existing()
        input_hash = _equivalence_input_hash(existing, [])
        ckpt = checkpoint_path(tmp_path, LESSONS_EQUIVALENCE_SLUG, input_hash)
        save_checkpoint(
            ckpt,
            Checkpoint(
                input_hash=input_hash,
                payload=_CANNED_FINDINGS_JSON,
                created_at=datetime.now(timezone.utc)
                .replace(microsecond=0)
                .isoformat(),
            ),
        )

        def explode(prompt: str) -> str:
            raise AssertionError("invoker must not be called on cache hit")

        findings = find_lesson_equivalences(
            existing, invoker=explode, repo_root=tmp_path
        )
        assert len(findings.duplicates) == 1
        assert findings.duplicates[0].rationale == "same"

    def test_checkpoint_miss_invokes_and_saves(self, tmp_path: Path) -> None:
        existing = _two_existing()
        invoker = _FakeInvoker(_CANNED_FINDINGS_JSON)

        find_lesson_equivalences(existing, invoker=invoker, repo_root=tmp_path)

        input_hash = _equivalence_input_hash(existing, [])
        ckpt = checkpoint_path(tmp_path, LESSONS_EQUIVALENCE_SLUG, input_hash)
        assert ckpt.exists()
        import json as _json
        body = _json.loads(ckpt.read_text(encoding="utf-8"))
        assert body["payload"] == _CANNED_FINDINGS_JSON
        assert body["input_hash"] == input_hash

    def test_resume_false_skips_load_but_still_saves(self, tmp_path: Path) -> None:
        existing = _two_existing()
        input_hash = _equivalence_input_hash(existing, [])
        ckpt = checkpoint_path(tmp_path, LESSONS_EQUIVALENCE_SLUG, input_hash)
        stale_payload = '{"duplicates": [], "conflicts": []}'
        save_checkpoint(
            ckpt,
            Checkpoint(
                input_hash=input_hash,
                payload=stale_payload,
                created_at=datetime.now(timezone.utc)
                .replace(microsecond=0)
                .isoformat(),
            ),
        )
        invoker = _FakeInvoker(_CANNED_FINDINGS_JSON)
        findings = find_lesson_equivalences(
            existing, invoker=invoker, repo_root=tmp_path, resume=False
        )

        assert len(invoker.calls) == 1
        assert len(findings.duplicates) == 1
        import json as _json
        body = _json.loads(ckpt.read_text(encoding="utf-8"))
        assert body["payload"] == _CANNED_FINDINGS_JSON

    def test_input_hash_changes_when_rule_text_changes(self) -> None:
        a = [LessonEntry(rule="rule A")]
        b = [LessonEntry(rule="rule B")]
        assert _equivalence_input_hash(a, []) != _equivalence_input_hash(b, [])

    def test_input_hash_stable_across_runs_for_same_input(self) -> None:
        a = _two_existing()
        b = _two_existing()
        assert _equivalence_input_hash(a, []) == _equivalence_input_hash(b, [])

    def test_unparseable_response_not_cached(self, tmp_path: Path) -> None:
        existing = _two_existing()
        invoker = _FakeInvoker("garbage non-json")
        find_lesson_equivalences(existing, invoker=invoker, repo_root=tmp_path)

        input_hash = _equivalence_input_hash(existing, [])
        ckpt = checkpoint_path(tmp_path, LESSONS_EQUIVALENCE_SLUG, input_hash)
        assert not ckpt.exists()

    def test_intra_set_case_passes_empty_candidates_marker_to_prompt(self) -> None:
        invoker = _FakeInvoker(_CANNED_FINDINGS_JSON)
        find_lesson_equivalences(_two_existing(), candidates=(), invoker=invoker)
        assert len(invoker.calls) == 1
        assert "no candidates" in invoker.calls[0]

    def test_default_confidence_constant(self) -> None:
        assert DEFAULT_EQUIVALENCE_CONFIDENCE == 0.6

    def test_empty_inputs_short_circuit_without_invoker(self) -> None:
        def explode(prompt: str) -> str:
            raise AssertionError("invoker must not be called for empty inputs")

        findings = find_lesson_equivalences([], invoker=explode)
        assert findings.is_empty

    def test_equivalence_findings_dataclass_defaults(self) -> None:
        empty = EquivalenceFindings(duplicates=(), conflicts=())
        assert empty.is_empty
        non_empty = EquivalenceFindings(
            duplicates=(
                EquivalenceFinding(
                    kind=EquivalenceKind.DUPLICATE,
                    left_index=1,
                    right_index=2,
                    confidence=0.8,
                    rationale="x",
                ),
            ),
            conflicts=(),
        )
        assert not non_empty.is_empty

    def test_checkpoint_path_lives_under_lessons_equivalence_slug(
        self, tmp_path: Path
    ) -> None:
        path = checkpoint_path(tmp_path, LESSONS_EQUIVALENCE_SLUG, "abc123")
        assert path == tmp_path / ".plan-tool" / "checkpoints" / "lessons-equivalence" / "abc123.json"


# ---------- discover_lessons_files ----------


class _FakePlan:
    """Minimal stand-in for ``schema.Plan`` carrying only ``lessons``."""

    def __init__(self, lessons: str | None) -> None:
        self.lessons = lessons


class _FakePlanEntry:
    """Minimal stand-in for ``locator.PlanEntry`` for discovery tests."""

    def __init__(self, slug: str, lessons: str | None) -> None:
        self._slug = slug
        self.plan = _FakePlan(lessons) if lessons is not None else None

    @property
    def slug(self) -> str:
        return self._slug


class TestDiscoverLessonsFiles:
    def _seed(self, path: Path, text: str = "# seed\n") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_discovers_general_and_project_when_present(
        self, tmp_path: Path
    ) -> None:
        self._seed(general_path(tmp_path))
        self._seed(project_path(tmp_path))
        rows = discover_lessons_files(tmp_path, [])
        assert all(isinstance(r, LessonsFile) for r in rows)
        assert [(r.kind, r.plan_slug) for r in rows] == [
            ("general", None),
            ("project", None),
        ]

    def test_skips_missing_general_or_project_silently(
        self, tmp_path: Path
    ) -> None:
        self._seed(project_path(tmp_path))
        rows = discover_lessons_files(tmp_path, [])
        assert len(rows) == 1
        assert rows[0].kind == "project"

    def test_includes_per_plan_lessons_from_entries(
        self, tmp_path: Path
    ) -> None:
        per_plan = tmp_path / "plans" / "demo-lessons.md"
        self._seed(per_plan)
        entry = _FakePlanEntry("demo", "plans/demo-lessons.md")
        rows = discover_lessons_files(tmp_path, [entry])
        assert len(rows) == 1
        assert rows[0].kind == "per-plan"
        assert rows[0].plan_slug == "demo"
        assert rows[0].path == tmp_path / "plans/demo-lessons.md"

    def test_dedupes_when_per_plan_path_equals_general_or_project(
        self, tmp_path: Path
    ) -> None:
        self._seed(general_path(tmp_path))
        # A pathological plan whose ``lessons:`` aliases general.md.
        rel = general_path(tmp_path).resolve()
        try:
            rel_str = rel.relative_to(tmp_path.resolve()).as_posix()
        except ValueError:
            rel_str = str(rel)
        entry = _FakePlanEntry("aliased", rel_str)
        rows = discover_lessons_files(tmp_path, [entry])
        # general.md must appear exactly once (not re-listed as per-plan).
        assert len(rows) == 1
        assert rows[0].kind == "general"

    def test_order_is_general_then_project_then_per_plan_entries_order(
        self, tmp_path: Path
    ) -> None:
        self._seed(general_path(tmp_path))
        self._seed(project_path(tmp_path))
        p_a = tmp_path / "plans" / "a.md"
        p_b = tmp_path / "plans" / "b.md"
        self._seed(p_a)
        self._seed(p_b)
        entries = [
            _FakePlanEntry("a", "plans/a.md"),
            _FakePlanEntry("b", "plans/b.md"),
            _FakePlanEntry("no-lessons", None),
        ]
        rows = discover_lessons_files(tmp_path, entries)
        assert [r.kind for r in rows] == [
            "general",
            "project",
            "per-plan",
            "per-plan",
        ]
        assert [r.plan_slug for r in rows] == [None, None, "a", "b"]


# ---------- parse_existing_entries ----------


class TestParseExistingEntries:
    def test_parses_well_formed_machine_entry(self) -> None:
        entry = LessonEntry(
            rule="verify paths",
            why="the heuristic misses partials",
            example="grep the repo",
            surface="detail-authoring",
            trigger="detail time",
        )
        parsed = parse_existing_entries(entry.render())
        assert parsed == [entry]

    def test_parses_entry_with_empty_why_and_example(self) -> None:
        entry = LessonEntry(rule="just a rule")
        parsed = parse_existing_entries(entry.render())
        assert len(parsed) == 1
        assert parsed[0].rule == "just a rule"
        assert parsed[0].why == ""
        assert parsed[0].example == ""

    def test_skips_hand_written_bullets_without_bold_rule(self) -> None:
        body = "- some hand-written bullet without bold\n"
        assert parse_existing_entries(body) == []

    def test_skips_header_and_blank_lines(self) -> None:
        from plan_tool.lessons import _GENERAL_HEADER

        e1 = LessonEntry(rule="one")
        e2 = LessonEntry(rule="two")
        body = _GENERAL_HEADER + e1.render() + "\n\n" + e2.render() + "\n"
        parsed = parse_existing_entries(body)
        assert [p.rule for p in parsed] == ["one", "two"]

    def test_round_trips_with_lesson_entry_render(self) -> None:
        entry = LessonEntry(
            rule="dense rule",
            why="dense why",
            example="dense example",
            surface="cross-step",
            trigger="on handoff",
        )
        parsed = parse_existing_entries(entry.render())
        assert parsed == [entry]


# ---------- render_consolidated_file ----------


class TestRenderConsolidatedFile:
    def _body(self, *rules: str) -> str:
        from plan_tool.lessons import _GENERAL_HEADER

        return _GENERAL_HEADER + "\n".join(
            LessonEntry(rule=r).render() for r in rules
        ) + "\n"

    def test_drops_indicated_indices_only(self) -> None:
        body = self._body("zero", "one", "two", "three")
        out = render_consolidated_file(body, frozenset({1, 3}))
        assert [p.rule for p in parse_existing_entries(out)] == ["zero", "two"]

    def test_drop_empty_returns_body_unchanged_byte_for_byte(self) -> None:
        body = self._body("a", "b")
        assert render_consolidated_file(body, frozenset()) == body

    def test_preserves_header_and_hand_written_lines(self) -> None:
        from plan_tool.lessons import _GENERAL_HEADER

        m0 = LessonEntry(rule="machine zero")
        m1 = LessonEntry(rule="machine one")
        body = (
            _GENERAL_HEADER
            + "- a hand-written prose bullet\n\n"
            + m0.render()
            + "\n\n"
            + m1.render()
            + "\n"
        )
        out = render_consolidated_file(body, frozenset({0}))
        assert "- a hand-written prose bullet" in out
        assert _GENERAL_HEADER in out
        assert [p.rule for p in parse_existing_entries(out)] == ["machine one"]

    def test_preserves_trailing_newline_shape(self) -> None:
        single = self._body("a", "b")  # ends with one \n
        assert single.endswith("\n") and not single.endswith("\n\n")
        assert render_consolidated_file(single, frozenset({0})).endswith("\n")
        double = single + "\n"
        assert render_consolidated_file(double, frozenset({0})).endswith("\n\n")

    def test_index_referencing_nonexistent_entry_is_ignored(self) -> None:
        body = self._body("a", "b")
        assert render_consolidated_file(body, frozenset({99})) == body


# ---------- append_pending_lessons ----------


class TestAppendPendingLessons:
    """Step 6: pending file holds quarantined bullets when a plan's
    ``files:`` set includes the canonical lessons sink."""

    def test_pending_path_lives_under_user_general_dir(
        self, tmp_path: Path
    ) -> None:
        """Pending entries sit next to the canonical general sink, which
        now lives under ``~/.plan-tool/lessons/`` (not in-repo)."""
        expected = (
            Path.home().joinpath(*GENERAL_LESSONS_REL)
            / PENDING_LESSONS_DIRNAME
            / "foo.md"
        )
        assert pending_lessons_path(tmp_path, "foo") == expected
        # Sanity-check the dirname constant.
        assert PENDING_LESSONS_DIRNAME == "pending"

    def test_append_pending_creates_file_with_general_and_project_subsections(
        self, tmp_path: Path
    ) -> None:
        n_g, n_p = append_pending_lessons(
            tmp_path,
            plan_slug="foo",
            general=[LessonEntry(rule="Pending general rule", why="quarantined")],
            project=[LessonEntry(rule="Pending project fact")],
            source="detail:foo#3",
            now=_fixed_now(),
        )
        assert (n_g, n_p) == (1, 1)
        path = pending_lessons_path(tmp_path, "foo")
        assert path.is_file()
        body = path.read_text(encoding="utf-8")
        # Header mentions the plan slug + why-quarantined wording so a
        # later operator (or promoter command) has context.
        assert "Pending lessons for plan `foo`" in body
        assert "Not loaded by `load_lessons`" in body
        # Subsection headings present and ordered (General before Project).
        assert "## General" in body
        assert "## Project" in body
        assert body.index("## General") < body.index("## Project")
        # General bullet lands under the General heading; project under Project.
        general_section = body[body.index("## General"):body.index("## Project")]
        project_section = body[body.index("## Project"):]
        assert "Pending general rule" in general_section
        assert "Pending project fact" in project_section
        # Citations sidecar is intentionally NOT written for pending entries.
        sidecar = path.with_name(path.stem + "-citations.jsonl")
        assert not sidecar.exists()

    def test_append_pending_dedupes_within_pending_file_not_against_canonical(
        self, tmp_path: Path
    ) -> None:
        # Pre-seed the canonical general sink with a bullet whose rule
        # text the pending appender will see; the pending write must
        # still fire (cross-file dedupe would defeat the quarantine).
        append_lessons(
            tmp_path,
            general=[
                LessonEntry(rule="Verify file paths before proposing")
            ],
            source="review:earlier",
            now=_fixed_now(),
        )
        assert general_path(tmp_path).is_file()

        # First pending append with the same rule still lands.
        n_g, _ = append_pending_lessons(
            tmp_path,
            plan_slug="foo",
            general=[
                LessonEntry(rule="Verify file paths before proposing")
            ],
            source="detail:foo#1",
            now=_fixed_now(),
        )
        assert n_g == 1
        pending = pending_lessons_path(tmp_path, "foo")
        assert pending.is_file()
        assert "Verify file paths before proposing" in pending.read_text(
            encoding="utf-8"
        )

        # Second pending append with the same rule deduplicates within
        # the pending file.
        n_g2, _ = append_pending_lessons(
            tmp_path,
            plan_slug="foo",
            general=[
                LessonEntry(rule="Verify file paths before proposing")
            ],
            source="detail:foo#2",
            now=_fixed_now(),
        )
        assert n_g2 == 0
        body = pending.read_text(encoding="utf-8")
        # Exactly one bullet body for that rule.
        assert body.count("Verify file paths before proposing") == 1


# ---------- style routing ----------


class TestLessonsStyleOutput:
    """Pin the lessons diagnostics to ``style.tool()`` / ``style.warn()``:
    plain-mode bytes are unchanged, and forced color paints only the
    ``plan-tool:`` / ``warning:`` prefix — the body stays plain."""

    def test_citation_failure_plain(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        path = tmp_path / "general-citations.jsonl"

        def boom(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
            raise OSError("nope")

        monkeypatch.setattr(Path, "open", boom)
        _append_citation_jsonl(
            path,
            entries=[LessonEntry(rule="r")],
            added="2026-06-01",
            source="review:x",
        )
        err = capsys.readouterr().err
        assert err == (
            f"plan-tool: failed to append citation sidecar {path} (nope); "
            "the bullet is still written, only the audit-trail record was lost\n"
        )

    def test_equivalence_unparseable_warns_plain(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        find_lesson_equivalences(
            _two_existing(), invoker=_FakeInvoker("not json")
        )
        err = capsys.readouterr().err
        assert err == (
            "warning: equivalence response was unparseable; "
            "treating as no findings\n"
        )

    def test_equivalence_checkpoint_failure_plain(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def boom(*args, **kwargs):  # noqa: ANN002, ANN003
            raise OSError("no space")

        monkeypatch.setattr(lessons, "save_checkpoint", boom)
        existing = _two_existing()
        input_hash = _equivalence_input_hash(existing, [])
        ckpt = checkpoint_path(tmp_path, LESSONS_EQUIVALENCE_SLUG, input_hash)
        find_lesson_equivalences(
            existing,
            invoker=_FakeInvoker(_CANNED_FINDINGS_JSON),
            repo_root=tmp_path,
        )
        err = capsys.readouterr().err
        assert err == (
            f"plan-tool: failed to save equivalence checkpoint "
            f"{ckpt} (no space); resume on next run will not be "
            "available for this call\n"
        )



# ======================================================================
# Step 5 additions — strict/warn-check hooks on ``append_lessons``, the
# warning-log writer/reader, recurrence aggregation, and the
# substring-dedupe regression pin. The step-1 primitive classes
# (``TestParseEquivalenceResponse`` / ``TestEquivalencePromptRender`` /
# ``TestFindLessonEquivalences``) already live above and are unchanged.
# Every claude-shaped interaction below goes through an injected fake —
# no test reaches ``plan_tool.shell.claude_invoke``.
# ======================================================================


def _findings_json(
    *,
    duplicates: tuple[tuple[int, int, float, str], ...] = (),
    conflicts: tuple[tuple[int, int, float, str], ...] = (),
) -> str:
    """Serialize ``(left, right, confidence, rationale)`` tuples as the
    equivalence-primitive JSON the fake invoker hands back."""

    def _items(rows: tuple[tuple[int, int, float, str], ...]) -> list[dict]:
        return [
            {
                "left_index": left,
                "right_index": right,
                "confidence": confidence,
                "rationale": rationale,
            }
            for (left, right, confidence, rationale) in rows
        ]

    return json.dumps(
        {"duplicates": _items(duplicates), "conflicts": _items(conflicts)}
    )


def _explode_invoker(prompt: str) -> str:
    raise AssertionError("equivalence invoker must not be called")


def _seed_warning_log(repo_root: Path, records: list[LessonsWarning]) -> Path:
    """Write a fully-formed warning log without going through ``append_warning``."""
    path = warnings_log_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(r.to_json_line() for r in records), encoding="utf-8")
    return path


def _warning(
    *,
    candidate_rule: str,
    matched_rules: tuple[str, ...],
    kind: str = "duplicate",
    confidence: float = 0.9,
    timestamp: str = "2026-05-12T00:00:00+00:00",
    mode: str = "warn",
    source: str = "review:test",
    target_file: str = "general.md",
    rationale: str = "",
) -> LessonsWarning:
    return LessonsWarning(
        timestamp=timestamp,
        target_file=target_file,
        candidate_rule=candidate_rule,
        matched_rules=matched_rules,
        kind=kind,
        confidence=confidence,
        rationale=rationale,
        source=source,
        mode=mode,
    )


# ---------- substring-dedupe regression pin ----------


class TestSubstringDedupeRegression:
    """The load-bearing pin: steps 3-4 widened ``append_lessons`` with
    keyword-only knobs but must not have touched the case-insensitive
    substring dedupe that pre-dates them."""

    def test_default_call_signature_returns_iterable_two_tuple(
        self, tmp_path: Path
    ) -> None:
        result = append_lessons(
            tmp_path,
            general=[LessonEntry(rule="Verify file paths before proposing")],
            project=[LessonEntry(rule="AppSync subs fire on resolver mutations")],
            source="review:test",
            now=_fixed_now(),
        )
        assert isinstance(result, AppendLessonsResult)
        n_g, n_p = result
        assert (n_g, n_p) == (1, 1)
        assert result.general_dropped == ()
        assert result.project_dropped == ()
        assert result.general_warnings == ()
        assert result.project_warnings == ()

    def test_substring_dedupe_unchanged_with_checks_disabled(
        self, tmp_path: Path
    ) -> None:
        # Replays the legacy substring contract through the new
        # keyword-only knobs (both off, no invoker): a recased substring
        # of an existing rule is still dropped, body byte-identical to
        # the legacy path.
        append_lessons(
            tmp_path,
            general=[LessonEntry(rule="Verify file paths before proposing")],
            source="review:first",
            strict_check=False,
            warn_check=False,
            equivalence_invoker=None,
            now=_fixed_now(),
        )
        before = general_path(tmp_path).read_text(encoding="utf-8")
        result = append_lessons(
            tmp_path,
            general=[LessonEntry(rule="VERIFY FILE PATHS before proposing")],
            source="review:second",
            strict_check=False,
            warn_check=False,
            equivalence_invoker=None,
            now=_fixed_now(),
        )
        n_g, _ = result
        assert n_g == 0
        after = general_path(tmp_path).read_text(encoding="utf-8")
        assert after == before  # byte-for-byte: nothing appended

    def test_substring_dedupe_runs_before_strict_check_invoker(
        self, tmp_path: Path
    ) -> None:
        # Prime a substring-duplicate candidate, then pass an invoker that
        # raises on call. The substring filter drops the candidate first,
        # so the claude judge is never consulted.
        append_lessons(
            tmp_path,
            general=[LessonEntry(rule="Verify file paths before proposing")],
            source="review:first",
            now=_fixed_now(),
        )
        result = append_lessons(
            tmp_path,
            general=[LessonEntry(rule="verify file paths before proposing")],
            source="review:second",
            strict_check=True,
            equivalence_invoker=_explode_invoker,
            now=_fixed_now(),
        )
        assert result.n_general_added == 0
        assert result.general_dropped == ()


# ---------- append_lessons strict-check branch ----------


class TestAppendLessonsStrictCheck:
    def _seed_general(self, tmp_path: Path, rule: str) -> None:
        append_lessons(
            tmp_path,
            general=[LessonEntry(rule=rule)],
            source="review:seed",
            now=_fixed_now(),
        )

    def test_default_invoker_is_the_module_shell_invoker(self) -> None:
        # The fallback ``append_lessons`` reaches for when no
        # ``equivalence_invoker`` is injected and ``strict_check`` is on.
        assert callable(shell_equivalence_invoker)

    def test_strict_check_false_does_not_call_equivalence_invoker(
        self, tmp_path: Path
    ) -> None:
        result = append_lessons(
            tmp_path,
            general=[LessonEntry(rule="A brand new rule")],
            source="review:test",
            strict_check=False,
            equivalence_invoker=_explode_invoker,
            now=_fixed_now(),
        )
        assert result.n_general_added == 1
        assert result.general_dropped == ()

    def test_strict_check_true_falls_back_to_default_invoker(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._seed_general(tmp_path, "An existing seeded rule")
        fake = _FakeInvoker(_findings_json())  # empty findings
        monkeypatch.setattr(lessons, "shell_equivalence_invoker", fake)
        append_lessons(
            tmp_path,
            general=[LessonEntry(rule="A wholly different candidate")],
            source="review:test",
            strict_check=True,
            equivalence_invoker=None,
            now=_fixed_now(),
        )
        assert len(fake.calls) == 1

    def test_strict_check_drops_duplicate_above_threshold(
        self, tmp_path: Path
    ) -> None:
        self._seed_general(tmp_path, "Verify file paths before proposing")
        fake = _FakeInvoker(
            _findings_json(duplicates=((1, 1, 0.95, "same idea"),))
        )
        result = append_lessons(
            tmp_path,
            general=[LessonEntry(rule="Always confirm paths against the repo")],
            source="review:test",
            strict_check=True,
            equivalence_invoker=fake,
            now=_fixed_now(),
        )
        assert result.n_general_added == 0
        assert len(result.general_dropped) == 1
        assert result.general_dropped[0].kind is EquivalenceKind.DUPLICATE

    def test_strict_check_drops_conflict_above_threshold(
        self, tmp_path: Path
    ) -> None:
        self._seed_general(tmp_path, "Always prefer composition over inheritance")
        fake = _FakeInvoker(
            _findings_json(conflicts=((1, 1, 0.9, "contradicts prior"),))
        )
        result = append_lessons(
            tmp_path,
            general=[LessonEntry(rule="Always prefer inheritance over composition")],
            source="review:test",
            strict_check=True,
            equivalence_invoker=fake,
            now=_fixed_now(),
        )
        assert result.n_general_added == 0
        assert len(result.general_dropped) == 1
        assert result.general_dropped[0].kind is EquivalenceKind.CONFLICT

    def test_strict_check_keeps_finding_below_threshold(
        self, tmp_path: Path
    ) -> None:
        self._seed_general(tmp_path, "Verify file paths before proposing")
        # 0.5 < DEFAULT_EQUIVALENCE_CONFIDENCE (0.6) → primitive drops it.
        fake = _FakeInvoker(
            _findings_json(duplicates=((1, 1, 0.5, "weak match"),))
        )
        result = append_lessons(
            tmp_path,
            general=[LessonEntry(rule="A candidate the judge is unsure about")],
            source="review:test",
            strict_check=True,
            equivalence_invoker=fake,
            now=_fixed_now(),
        )
        assert result.n_general_added == 1
        assert result.general_dropped == ()

    def test_strict_check_with_no_prior_entries_writes_all(
        self, tmp_path: Path
    ) -> None:
        fake = _FakeInvoker(_findings_json())  # no findings
        result = append_lessons(
            tmp_path,
            general=[
                LessonEntry(rule="First rule"),
                LessonEntry(rule="Second rule"),
            ],
            source="review:test",
            strict_check=True,
            equivalence_invoker=fake,
            now=_fixed_now(),
        )
        assert result.n_general_added == 2
        assert result.general_dropped == ()

    def test_strict_check_drop_emits_stderr_and_warning_record(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._seed_general(tmp_path, "Verify file paths before proposing")
        fake = _FakeInvoker(
            _findings_json(duplicates=((1, 1, 0.95, "same idea"),))
        )
        append_lessons(
            tmp_path,
            general=[LessonEntry(rule="Always confirm paths against the repo")],
            source="review:test",
            strict_check=True,
            equivalence_invoker=fake,
            now=_fixed_now(),
        )
        err = capsys.readouterr().err
        assert "strict-check dropped" in err
        records = load_warnings(tmp_path)
        assert len(records) == 1
        assert records[0].mode == "drop"

    def test_strict_check_result_unpacks_and_carries_drops(
        self, tmp_path: Path
    ) -> None:
        self._seed_general(tmp_path, "Verify file paths before proposing")
        fake = _FakeInvoker(
            _findings_json(duplicates=((1, 1, 0.95, "same idea"),))
        )
        result = append_lessons(
            tmp_path,
            general=[LessonEntry(rule="Always confirm paths against the repo")],
            source="review:test",
            strict_check=True,
            equivalence_invoker=fake,
            now=_fixed_now(),
        )
        n_g, n_p = result  # the __iter__ regression still holds
        assert (n_g, n_p) == (0, 0)
        assert len(result.general_dropped) == 1


# ---------- append_lessons warn-check branch ----------


class TestAppendLessonsWarnCheck:
    def _seed_general(self, tmp_path: Path, rule: str) -> None:
        append_lessons(
            tmp_path,
            general=[LessonEntry(rule=rule)],
            source="review:seed",
            now=_fixed_now(),
        )

    def test_warn_check_writes_warning_but_keeps_candidate(
        self, tmp_path: Path
    ) -> None:
        self._seed_general(tmp_path, "Verify file paths before proposing")
        fake = _FakeInvoker(
            _findings_json(duplicates=((1, 1, 0.9, "overlaps"),))
        )
        result = append_lessons(
            tmp_path,
            general=[LessonEntry(rule="Always confirm paths against the repo")],
            source="review:test",
            warn_check=True,
            equivalence_invoker=fake,
            now=_fixed_now(),
        )
        assert result.n_general_added == 1  # kept despite the finding
        records = load_warnings(tmp_path)
        assert len(records) == 1
        assert records[0].mode == "warn"

    def test_warn_check_surfaces_warnings_on_result(
        self, tmp_path: Path
    ) -> None:
        self._seed_general(tmp_path, "Verify file paths before proposing")
        fake = _FakeInvoker(
            _findings_json(duplicates=((1, 1, 0.9, "overlaps"),))
        )
        result = append_lessons(
            tmp_path,
            general=[LessonEntry(rule="Always confirm paths against the repo")],
            source="review:test",
            warn_check=True,
            equivalence_invoker=fake,
            now=_fixed_now(),
        )
        assert len(result.general_warnings) == 1
        assert result.n_general_added == 1

    def test_warn_check_false_writes_no_log(self, tmp_path: Path) -> None:
        append_lessons(
            tmp_path,
            general=[LessonEntry(rule="A brand new rule")],
            source="review:test",
            now=_fixed_now(),
        )
        assert not warnings_log_path(tmp_path).exists()

    def test_strict_check_wins_when_both_flags_set(
        self, tmp_path: Path
    ) -> None:
        self._seed_general(tmp_path, "Verify file paths before proposing")
        fake = _FakeInvoker(
            _findings_json(duplicates=((1, 1, 0.95, "same idea"),))
        )
        result = append_lessons(
            tmp_path,
            general=[LessonEntry(rule="Always confirm paths against the repo")],
            source="review:test",
            strict_check=True,
            warn_check=True,
            equivalence_invoker=fake,
            now=_fixed_now(),
        )
        # Strict path ran: the finding is a drop, not a warn — exactly one
        # log record, in drop mode.
        assert result.n_general_added == 0
        assert result.general_warnings == ()
        records = load_warnings(tmp_path)
        assert len(records) == 1
        assert records[0].mode == "drop"


# ---------- LessonsWarning JSONL round-trip ----------


class TestLessonsWarning:
    def test_to_json_line_round_trips_through_from_json(self) -> None:
        w = _warning(
            candidate_rule="new rule",
            matched_rules=("prior one", "prior two"),
            kind="conflict",
            confidence=0.82,
            rationale="why",
            mode="drop",
        )
        restored = LessonsWarning.from_json(json.loads(w.to_json_line()))
        assert restored == w

    def test_from_json_tolerates_missing_optional_fields(self) -> None:
        restored = LessonsWarning.from_json(
            {"timestamp": "2026-05-12T00:00:00+00:00", "candidate_rule": "r"}
        )
        assert restored.matched_rules == ()
        assert restored.rationale == ""
        assert restored.source == ""
        assert restored.mode == ""
        assert restored.confidence == 0.0


# ---------- append_warning ----------


class TestAppendWarning:
    def test_creates_file_and_parent_dir_on_first_write(
        self, tmp_path: Path
    ) -> None:
        path = warnings_log_path(tmp_path)
        assert not path.exists()
        append_warning(
            tmp_path,
            _warning(candidate_rule="r", matched_rules=("p",)),
        )
        assert path.is_file()
        assert len(load_warnings(tmp_path)) == 1

    def test_appends_one_line_per_call(self, tmp_path: Path) -> None:
        append_warning(tmp_path, _warning(candidate_rule="r1", matched_rules=("p",)))
        append_warning(tmp_path, _warning(candidate_rule="r2", matched_rules=("p",)))
        text = warnings_log_path(tmp_path).read_text(encoding="utf-8")
        assert text.endswith("\n")
        assert len(load_warnings(tmp_path)) == 2

    def test_rolling_cap_trims_oldest_records(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        for i in range(5):
            append_warning(
                tmp_path,
                _warning(candidate_rule=f"rule {i}", matched_rules=("p",)),
                max_records=3,
                stderr=sys.stderr,
            )
        records = load_warnings(tmp_path)
        assert len(records) == 3
        # Oldest two trimmed; newest three survive in order.
        assert [r.candidate_rule for r in records] == ["rule 2", "rule 3", "rule 4"]
        # The cap is enforced per append, so the log never reaches 5
        # records: appends 4 and 5 each trim 4 -> 3.
        assert "trimmed to 3 records (was 4)" in capsys.readouterr().err

    def test_failed_append_does_not_raise(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        ro = tmp_path / "ro"
        ro.mkdir()
        ro.chmod(0o500)
        try:
            append_warning(
                ro,
                _warning(candidate_rule="r", matched_rules=("p",)),
                stderr=sys.stderr,
            )
            assert "append_warning failed" in capsys.readouterr().err
        finally:
            ro.chmod(0o700)  # restore so tmp_path cleanup succeeds


# ---------- load_warnings ----------


class TestLoadWarnings:
    def test_warnings_log_path_composed_from_module_constants(
        self, tmp_path: Path
    ) -> None:
        assert warnings_log_path(tmp_path) == tmp_path.joinpath(
            *WARNINGS_REL, WARNINGS_FILENAME
        )

    def test_returns_empty_list_when_file_absent(self, tmp_path: Path) -> None:
        assert load_warnings(tmp_path) == []

    def test_skips_malformed_lines_silently(self, tmp_path: Path) -> None:
        path = warnings_log_path(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        good = _warning(candidate_rule="r", matched_rules=("p",)).to_json_line()
        path.write_text(good + "not json\n" + good, encoding="utf-8")
        assert len(load_warnings(tmp_path)) == 2

    def test_returns_records_in_file_order_oldest_first(
        self, tmp_path: Path
    ) -> None:
        _seed_warning_log(
            tmp_path,
            [
                _warning(candidate_rule="first", matched_rules=("p",)),
                _warning(candidate_rule="second", matched_rules=("p",)),
                _warning(candidate_rule="third", matched_rules=("p",)),
            ],
        )
        assert [r.candidate_rule for r in load_warnings(tmp_path)] == [
            "first",
            "second",
            "third",
        ]


# ---------- recurrence_counts ----------


class TestRecurrenceCounts:
    def test_counts_pair_case_insensitive(self) -> None:
        records = [
            _warning(candidate_rule="Verify Paths", matched_rules=("Check Repo",)),
            _warning(candidate_rule="verify paths", matched_rules=("check repo",)),
        ]
        counts = recurrence_counts(records)
        assert counts == {("verify paths", "check repo"): 2}

    def test_one_to_many_matched_rules_counts_each_pair(self) -> None:
        records = [
            _warning(
                candidate_rule="cand",
                matched_rules=("a", "b", "c"),
            )
        ]
        counts = recurrence_counts(records)
        assert counts == {
            ("cand", "a"): 1,
            ("cand", "b"): 1,
            ("cand", "c"): 1,
        }

    def test_empty_candidate_or_matched_rule_skipped(self) -> None:
        records = [
            _warning(candidate_rule="   ", matched_rules=("a",)),
            _warning(candidate_rule="cand", matched_rules=("",)),
        ]
        assert recurrence_counts(records) == {}


# ---------- recurrence_weight_from_counts ----------


class TestRecurrenceWeightFromCounts:
    def _finding(self, left: int, right: int) -> EquivalenceFinding:
        return EquivalenceFinding(
            kind=EquivalenceKind.DUPLICATE,
            left_index=left,
            right_index=right,
            confidence=0.9,
            rationale="",
        )

    def test_returns_constant_one_when_entries_index_none(self) -> None:
        weight = recurrence_weight_from_counts({}, entries_by_index=None)
        assert weight(self._finding(1, 2)) == 1.0

    def test_weight_is_one_plus_count(self) -> None:
        entries = {1: LessonEntry(rule="a"), 2: LessonEntry(rule="b")}
        counts = {("b", "a"): 4}
        weight = recurrence_weight_from_counts(counts, entries_by_index=entries)
        assert weight(self._finding(1, 2)) == 5.0

    def test_weight_symmetric_in_left_right_order(self) -> None:
        entries = {1: LessonEntry(rule="a"), 2: LessonEntry(rule="b")}
        counts = {("a", "b"): 3}
        weight = recurrence_weight_from_counts(counts, entries_by_index=entries)
        assert weight(self._finding(1, 2)) == weight(self._finding(2, 1)) == 4.0


# ---------- strict-check threading through detail / review extraction ----------


class TestStrictCheckThreading:
    """``strict_check`` / ``equivalence_invoker`` reach ``append_lessons``
    when threaded through the detail and review lesson-extraction
    entry points — the invoker actually fires against a fresh repo."""

    _EXTRACT_JSON = json.dumps(
        {
            "general": [{"rule": "A distilled general lesson"}],
            "project": [],
        }
    )

    def test_threads_through_review_extraction(self, tmp_path: Path) -> None:
        from plan_tool.review import (
            Recommendation,
            extract_and_append_review_lessons,
        )

        fake_eq = _FakeInvoker(_findings_json())  # called, returns no findings
        extract_and_append_review_lessons(
            plan_name="demo-plan",
            plan_title="Demo Plan",
            report_md="# report",
            recommendations=[
                Recommendation(
                    id="r1",
                    source="claude",
                    severity="high",
                    step_id=1,
                    title="Do the thing",
                    body="because reasons",
                )
            ],
            invoker=lambda prompt: (0, self._EXTRACT_JSON),
            repo_root=tmp_path,
            strict_check=True,
            equivalence_invoker=fake_eq,
        )
        assert len(fake_eq.calls) == 1

    def test_threads_through_detail_extraction(self, tmp_path: Path) -> None:
        from plan_tool.detail import extract_and_append_detail_lessons
        from plan_tool.parser import parse_plan

        plan_path = tmp_path / "1-demo.md"
        plan_path.write_text(
            "---\n"
            "title: Demo Plan\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Do the thing\n"
            "    files: []\n"
            "---\n\n"
            "# Demo Plan\n",
            encoding="utf-8",
        )
        plan = parse_plan(plan_path)
        fake_eq = _FakeInvoker(_findings_json())
        extract_and_append_detail_lessons(
            plan=plan,
            plan_path=plan_path,
            step=plan.steps[0],
            detail_body="# Step 1\n\nsome body\n",
            repo_root=tmp_path,
            invoker=lambda prompt: (0, self._EXTRACT_JSON),
            strict_check=True,
            equivalence_invoker=fake_eq,
        )
        assert len(fake_eq.calls) == 1
