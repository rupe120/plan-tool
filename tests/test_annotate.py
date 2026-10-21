"""Tests for plan_tool.annotate — the classification core (step 1).

Every case passes a stub ``invoker=`` (lambda or recording closure) so
the autouse ``tests/conftest.py`` gate never fires; no real claude.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plan_tool.annotate import (
    AnnotateError,
    AnnotationStatus,
    PlanAnnotation,
    _load_step_specs,
    classify_plan_implementation,
    render_annotate_prompt,
)
from plan_tool.create import CreateError
from plan_tool.parser import write_plan
from plan_tool.schema import Plan, PlanStatus, Priority, Step


# --- fixtures / helpers -----------------------------------------------------


def _canned(sections: list[dict]) -> str:
    """Wrap a section list as a stubbed invoker's JSON-array response."""
    return json.dumps(sections)


def _stub(response: str):
    """An invoker that ignores its prompt and returns ``response``."""
    return lambda _prompt: response


def _write_notes(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def _write_grounding_files(tmp_path: Path, *names: str) -> None:
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {name}\n", encoding="utf-8")


def _write_plan_file(
    tmp_path: Path,
    *,
    steps: list[Step],
    name: str = "plan.md",
) -> Path:
    path = tmp_path / name
    # Seed a stub so write_plan (which round-trips an existing file,
    # preserving the body) has a frontmatter fence + body to read.
    path.write_text(
        "---\n---\n## Steps\n\nSee the `steps:` block in the frontmatter.\n",
        encoding="utf-8",
    )
    plan = Plan(
        title="Demo Plan",
        status=PlanStatus.PLANNING,
        priority=Priority.MEDIUM,
        steps=steps,
    )
    write_plan(path, plan, expect_unchanged=False)
    return path


# --- core return shape ------------------------------------------------------


def test_classify_returns_sections_from_stubbed_invoker(tmp_path: Path) -> None:
    _write_grounding_files(tmp_path, "src/a.py", "src/b.py", "src/c.py")
    (tmp_path / "src" / "a.py").write_text(
        "def implemented():\n    return None\n", encoding="utf-8"
    )
    src = _write_notes(
        tmp_path,
        "notes.md",
        "# Overview\n\nDo a thing in `src/a.py`, `src/b.py`, and `src/c.py`.\n",
    )
    response = _canned(
        [
            {"heading": "Overview", "status": "IMPLEMENTED",
             "evidence": "done", "code_refs": ["src/a.py:implemented"]},
            {"heading": "Risks", "status": "NOT-IMPLEMENTED",
             "evidence": "absent", "code_refs": []},
        ]
    )
    result = classify_plan_implementation(
        src, repo_root=tmp_path, invoker=_stub(response)
    )
    assert isinstance(result, PlanAnnotation)
    assert [s.heading for s in result.sections] == ["Overview", "Risks"]
    assert [s.status for s in result.sections] == [
        AnnotationStatus.IMPLEMENTED,
        AnnotationStatus.NOT_IMPLEMENTED,
    ]


def test_classify_scopes_spawn_cwd_to_repo_root(tmp_path: Path) -> None:
    """@spawn_cwd_from_repo_root scopes backend spawns (and the shell-backstop
    telemetry) to repo_root during the invoke."""
    from plan_tool.backend import get_active_spawn_cwd

    src = _write_notes(tmp_path, "notes.md", "# Overview\n\nDo a thing.\n")
    response = _canned(
        [{"heading": "Overview", "status": "IMPLEMENTED",
          "evidence": "done", "code_refs": []}]
    )
    seen: list = []

    def capture(_prompt: str) -> str:
        seen.append(get_active_spawn_cwd())
        return response

    classify_plan_implementation(src, repo_root=tmp_path, invoker=capture)
    assert seen == [tmp_path]


def test_status_strings_map_to_enum(tmp_path: Path) -> None:
    _write_grounding_files(tmp_path, "src/a.py", "src/b.py", "src/c.py")
    (tmp_path / "src" / "a.py").write_text(
        "def x():\n    return None\n", encoding="utf-8"
    )
    (tmp_path / "src" / "b.py").write_text(
        "def y():\n    return None\n", encoding="utf-8"
    )
    src = _write_notes(
        tmp_path,
        "notes.md",
        "References `src/a.py`, `src/b.py`, and `src/c.py`.\n",
    )
    response = _canned(
        [
            {
                "heading": "A",
                "status": "IMPLEMENTED",
                "code_refs": ["src/a.py:x"],
            },
            {
                "heading": "B",
                "status": "PARTIAL",
                "code_refs": ["src/b.py:y"],
            },
            {"heading": "C", "status": "NOT-IMPLEMENTED", "code_refs": []},
        ]
    )
    result = classify_plan_implementation(
        src, repo_root=tmp_path, invoker=_stub(response)
    )
    assert [s.status for s in result.sections] == [
        AnnotationStatus.IMPLEMENTED,
        AnnotationStatus.PARTIAL,
        AnnotationStatus.NOT_IMPLEMENTED,
    ]


def test_source_text_is_verbatim(tmp_path: Path) -> None:
    body = "# Title\n\nLine with a literal $dollar and trailing space.  \n"
    src = _write_notes(tmp_path, "notes.md", body)
    response = _canned(
        [{"heading": "Title", "status": "NOT-IMPLEMENTED", "code_refs": []}]
    )
    result = classify_plan_implementation(
        src, repo_root=tmp_path, invoker=_stub(response)
    )
    assert result.source_text == body


# --- parser error / demotion semantics --------------------------------------


def test_not_implemented_with_code_refs_becomes_needs_review(tmp_path: Path) -> None:
    src = _write_notes(tmp_path, "notes.md", "notes")
    response = _canned(
        [{"heading": "A", "status": "NOT-IMPLEMENTED",
          "evidence": "claimed absent", "code_refs": ["a.py:x"]}]
    )
    result = classify_plan_implementation(
        src, repo_root=tmp_path, invoker=_stub(response)
    )
    section = result.sections[0]
    assert section.status is AnnotationStatus.NEEDS_REVIEW
    assert section.code_refs == ("a.py:x",)
    assert section.low_confidence is True
    assert section.contradiction_review is True
    assert "NOT-IMPLEMENTED while also citing code_refs" in section.evidence
    assert "claimed absent" in section.evidence


@pytest.mark.parametrize("status", ["IMPLEMENTED", "PARTIAL"])
def test_implemented_without_code_refs_demoted_to_low_confidence(
    tmp_path: Path, status: str
) -> None:
    src = _write_notes(tmp_path, "notes.md", "notes")
    response = _canned(
        [{"heading": "A", "status": status, "evidence": "e", "code_refs": []}]
    )
    result = classify_plan_implementation(
        src, repo_root=tmp_path, invoker=_stub(response)
    )
    assert result.sections[0].low_confidence is True


@pytest.mark.parametrize("status", ["IMPLEMENTED", "PARTIAL"])
def test_unresolved_code_refs_demote_verdict_and_name_bad_refs(
    tmp_path: Path, status: str
) -> None:
    code_path = tmp_path / "src" / "code.py"
    code_path.parent.mkdir()
    code_path.write_text("def present():\n    return None\n", encoding="utf-8")
    src = _write_notes(tmp_path, "notes.md", "References `src/code.py`.\n")
    response = _canned(
        [{
            "heading": "A",
            "status": status,
            "evidence": "claimed done",
            "code_refs": [
                "src/missing.py:present",
                "src/code.py:missing",
                "src/code.py:99",
            ],
        }]
    )
    result = classify_plan_implementation(
        src, repo_root=tmp_path, invoker=_stub(response)
    )
    section = result.sections[0]
    assert section.low_confidence is True
    assert "LOW-CONFIDENCE: unresolved code_refs at HEAD" in section.evidence
    assert "`src/missing.py:present`" in section.evidence
    assert "`src/code.py:missing`" in section.evidence
    assert "`src/code.py:99`" in section.evidence


def test_resolved_code_ref_keeps_confident_verdict(tmp_path: Path) -> None:
    code_path = tmp_path / "src" / "code.py"
    code_path.parent.mkdir()
    code_path.write_text("def present():\n    return None\n", encoding="utf-8")
    src = _write_notes(tmp_path, "notes.md", "References `src/code.py`.\n")
    response = _canned(
        [{
            "heading": "A",
            "status": "IMPLEMENTED",
            "evidence": "claimed done",
            "code_refs": ["src/code.py:present", "src/code.py:1"],
        }]
    )
    result = classify_plan_implementation(
        src, repo_root=tmp_path, invoker=_stub(response)
    )
    assert result.sections[0].low_confidence is False


def test_resolved_non_python_code_ref_keeps_confident_verdict(tmp_path: Path) -> None:
    code_path = tmp_path / "src" / "code.ts"
    code_path.parent.mkdir()
    code_path.write_text("export function present() {}\n", encoding="utf-8")
    src = _write_notes(tmp_path, "notes.md", "References `src/code.ts`.\n")
    response = _canned(
        [{
            "heading": "A",
            "status": "IMPLEMENTED",
            "evidence": "claimed done",
            "code_refs": ["src/code.ts:present"],
        }]
    )
    result = classify_plan_implementation(
        src, repo_root=tmp_path, invoker=_stub(response)
    )
    assert result.sections[0].low_confidence is False


def test_unparseable_response_raises(tmp_path: Path) -> None:
    src = _write_notes(tmp_path, "notes.md", "notes")
    with pytest.raises(AnnotateError):
        classify_plan_implementation(src, repo_root=tmp_path, invoker=_stub(""))
    with pytest.raises(AnnotateError):
        classify_plan_implementation(
            src, repo_root=tmp_path, invoker=_stub("no json here at all")
        )


def test_unsupported_plan_format_version_is_reported_not_treated_as_rough_notes(
    tmp_path: Path,
) -> None:
    """A structured plan declaring an unsupported format_version is a real
    source failure, not the rough-notes fallback: it must reach the
    operator as an AnnotateError, and — because _try_parse_plan raises
    before classify_plan_implementation ever builds a prompt — the Claude
    seam must never be invoked for it, unlike genuine rough notes (which
    reach the invoker after falling back to section-by-heading judgement).
    """
    src = _write_notes(
        tmp_path,
        "plan.md",
        "---\n"
        "title: Newer plan\n"
        "status: planning\n"
        "priority: low\n"
        "format_version: 999\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: One\n"
        "---\n"
        "# Body\n",
    )
    calls: list[str] = []

    def recording(prompt: str) -> str:
        calls.append(prompt)
        return _canned([{"heading": "A", "status": "NOT-IMPLEMENTED", "code_refs": []}])

    with pytest.raises(AnnotateError, match="999") as exc_info:
        classify_plan_implementation(src, repo_root=tmp_path, invoker=recording)

    assert "999" in str(exc_info.value)
    assert calls == []


def test_unsupported_detail_format_version_is_reported_as_annotate_error(
    tmp_path: Path,
) -> None:
    """A cited detail file declaring an unsupported version is a real
    source failure, reported as ``AnnotateError`` before the Claude seam
    is ever invoked — mirrors the plan-format-version equivalent above."""
    from plan_tool.detail_artifacts import render_detail_format_version_marker

    (tmp_path / "detail.md").write_text(
        f"# Step\n{render_detail_format_version_marker(999)}\n\nfine.\n",
        encoding="utf-8",
    )
    src = _write_notes(
        tmp_path,
        "plan.md",
        "---\n"
        "title: Plan\n"
        "status: planning\n"
        "priority: low\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: One\n"
        "    detail: detail.md\n"
        "---\n"
        "# Body\n",
    )
    calls: list[str] = []

    def recording(prompt: str) -> str:
        calls.append(prompt)
        return _canned([{"heading": "A", "status": "NOT-IMPLEMENTED", "code_refs": []}])

    with pytest.raises(AnnotateError, match="999") as exc_info:
        classify_plan_implementation(src, repo_root=tmp_path, invoker=recording)

    assert "999" in str(exc_info.value)
    assert calls == []


def test_malformed_status_raises(tmp_path: Path) -> None:
    src = _write_notes(tmp_path, "notes.md", "notes")
    response = _canned([{"heading": "A", "status": "DONE", "code_refs": []}])
    with pytest.raises(AnnotateError) as exc:
        classify_plan_implementation(
            src, repo_root=tmp_path, invoker=_stub(response)
        )
    assert "DONE" in str(exc.value)


@pytest.mark.parametrize(
    "raw_status", ["NEEDS-REVIEW", "needs-review", " needs-review "]
)
def test_model_cannot_directly_emit_needs_review_status(
    tmp_path: Path, raw_status: str
) -> None:
    src = _write_notes(tmp_path, "notes.md", "notes")
    response = _canned([{"heading": "A", "status": raw_status, "code_refs": []}])
    with pytest.raises(AnnotateError, match="unknown status"):
        classify_plan_implementation(
            src, repo_root=tmp_path, invoker=_stub(response)
        )


@pytest.mark.parametrize(
    ("raw_status", "expected", "code_refs"),
    [
        (" implemented ", AnnotationStatus.IMPLEMENTED, ["src/a.py:foo"]),
        ("partial", AnnotationStatus.PARTIAL, ["src/a.py:foo"]),
        (" not-implemented ", AnnotationStatus.NOT_IMPLEMENTED, []),
    ],
)
def test_status_normalization_preserves_the_closed_vocabulary(
    tmp_path: Path,
    raw_status: str,
    expected: AnnotationStatus,
    code_refs: list[str],
) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("def foo(): pass\n", encoding="utf-8")
    src = _write_notes(tmp_path, "notes.md", "References `src/a.py`.")
    response = _canned(
        [{"heading": "A", "status": raw_status, "code_refs": code_refs}]
    )
    result = classify_plan_implementation(
        src, repo_root=tmp_path, invoker=_stub(response)
    )
    assert result.sections[0].status is expected


def test_missing_source_file_raises_create_error(tmp_path: Path) -> None:
    missing = tmp_path / "nope.md"
    with pytest.raises(CreateError):
        classify_plan_implementation(
            missing, repo_root=tmp_path, invoker=_stub("[]")
        )


# --- grounding --------------------------------------------------------------


def test_grounding_resolves_to_find_umbrella_root(tmp_path: Path) -> None:
    # Two sibling repos under a common (non-git) parent; a source citing a
    # file in each must resolve repo_root to the common ancestor.
    outer = tmp_path / "outer"
    for repo in ("repo_a", "repo_b"):
        (outer / repo / ".git").mkdir(parents=True)
        (outer / repo / "mod.py").write_text("x = 1\n", encoding="utf-8")
    src = _write_notes(
        outer,
        "notes.md",
        "Touches `repo_a/mod.py` and `repo_b/mod.py`.\n",
    )
    response = _canned(
        [{"heading": "notes.md", "status": "PARTIAL", "code_refs": ["x"]}]
    )
    result = classify_plan_implementation(
        src, repo_root=outer, invoker=_stub(response)
    )
    assert result.repo_root == outer


def test_unresolved_candidate_files_are_skipped(tmp_path: Path) -> None:
    src = _write_notes(
        tmp_path, "notes.md", "References `does/not/exist.py`.\n"
    )
    response = _canned(
        [{"heading": "notes.md", "status": "NOT-IMPLEMENTED", "code_refs": []}]
    )
    result = classify_plan_implementation(
        src, repo_root=tmp_path, invoker=_stub(response)
    )
    assert all("exist.py" not in str(p) for p in result.grounded_files)


def test_grounding_records_candidate_and_skipped_counts(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "code.py").write_text("x = 1\n", encoding="utf-8")
    src = _write_notes(
        tmp_path,
        "notes.md",
        "References `src/code.py` and `src/missing.py`.\n",
    )
    response = _canned(
        [{"heading": "notes.md", "status": "PARTIAL", "code_refs": ["x"]}]
    )
    result = classify_plan_implementation(
        src, repo_root=tmp_path, invoker=_stub(response)
    )
    assert result.grounding_candidate_count == 2
    assert result.grounding_skipped_count == 1
    assert result.grounding_skip_reasons == (
        "src/missing.py: grounding skipped unresolved file",
    )


def test_binary_candidate_files_are_skipped_and_reported(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    binary_path = tmp_path / "assets" / "image.png"
    binary_path.write_bytes(b"\x89PNG\r\n\x1a\n\x00binary")
    src = _write_notes(
        tmp_path, "notes.md", "References `assets/image.png`.\n"
    )
    captured: dict[str, str] = {}

    def recording(prompt: str) -> str:
        captured["prompt"] = prompt
        return _canned(
            [{"heading": "notes.md", "status": "NOT-IMPLEMENTED",
              "code_refs": []}]
        )

    result = classify_plan_implementation(
        src, repo_root=tmp_path, invoker=recording
    )
    assert result.grounded_files == ()
    assert result.grounding_candidate_count == 1
    assert result.grounding_skipped_count == 1
    assert result.grounding_skip_reasons == (
        "assets/image.png: grounding skipped binary file",
    )
    assert "\x00binary" not in captured["prompt"]


def test_invalid_utf8_candidate_reports_binary_skip(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "blob.bin").write_bytes(b"\xff\xfe\xfd")
    src = _write_notes(
        tmp_path, "notes.md", "References `data/blob.bin`.\n"
    )
    response = _canned(
        [{"heading": "notes.md", "status": "NOT-IMPLEMENTED", "code_refs": []}]
    )
    result = classify_plan_implementation(
        src, repo_root=tmp_path, invoker=_stub(response)
    )
    assert result.grounding_skip_reasons == (
        "data/blob.bin: grounding skipped binary file",
    )


def test_zero_grounding_demotes_implemented_to_needs_review(tmp_path: Path) -> None:
    src = _write_notes(tmp_path, "notes.md", "No file paths here.\n")
    response = _canned(
        [{"heading": "notes.md", "status": "IMPLEMENTED",
          "evidence": "claimed done", "code_refs": ["a.py:done"]}]
    )
    result = classify_plan_implementation(
        src, repo_root=tmp_path, invoker=_stub(response)
    )
    section = result.sections[0]
    assert section.status is AnnotationStatus.NEEDS_REVIEW
    assert section.low_confidence is True
    assert section.low_grounding is True
    assert section.contradiction_review is False
    assert "Low grounding" in section.evidence
    assert "claimed done" in section.evidence


def test_low_grounding_partial_stays_partial_and_marks_review_required(
    tmp_path: Path,
) -> None:
    _write_grounding_files(tmp_path, "src/code.py")
    src = _write_notes(
        tmp_path,
        "notes.md",
        "References `src/code.py` and `src/missing.py`.\n",
    )
    response = _canned(
        [{"heading": "notes.md", "status": "PARTIAL",
          "evidence": "some done", "code_refs": ["src/code.py:done"],
          "remaining": "finish the rest"}]
    )
    result = classify_plan_implementation(
        src, repo_root=tmp_path, invoker=_stub(response)
    )
    section = result.sections[0]
    assert section.status is AnnotationStatus.PARTIAL
    assert section.low_confidence is True
    assert section.low_grounding is True
    assert section.remaining_work == "finish the rest"


def test_fully_grounded_small_plan_keeps_confident_implemented(
    tmp_path: Path,
) -> None:
    _write_grounding_files(tmp_path, "src/one.py", "src/two.py")
    (tmp_path / "src" / "one.py").write_text(
        "def done():\n    return None\n", encoding="utf-8"
    )
    src = _write_notes(
        tmp_path, "notes.md", "References `src/one.py` and `src/two.py`.\n"
    )
    response = _canned(
        [{"heading": "notes.md", "status": "IMPLEMENTED",
          "evidence": "done", "code_refs": ["src/one.py:done"]}]
    )
    result = classify_plan_implementation(
        src, repo_root=tmp_path, invoker=_stub(response)
    )
    section = result.sections[0]
    assert section.status is AnnotationStatus.IMPLEMENTED
    assert section.low_confidence is False
    assert section.low_grounding is False


def test_grounding_prompt_uses_symbol_excerpt_for_plan_step_title(
    tmp_path: Path,
) -> None:
    code_path = tmp_path / "src" / "feature.py"
    code_path.parent.mkdir()
    code_path.write_text(
        "\n".join(f"# header {i}" for i in range(80))
        + "\n\n\ndef target_symbol():\n    return 1\n",
        encoding="utf-8",
    )
    plan = _write_plan_file(
        tmp_path,
        steps=[Step(id=1, title="Implement target_symbol")],
    )
    plan.write_text(
        plan.read_text(encoding="utf-8") + "\nSee `src/feature.py`.\n",
        encoding="utf-8",
    )
    captured: dict[str, str] = {}

    def recording(prompt: str) -> str:
        captured["prompt"] = prompt
        return _canned(
            [{"heading": "Implement target_symbol", "status": "NOT-IMPLEMENTED",
              "code_refs": [], "is_step": True}]
        )

    classify_plan_implementation(
        plan, repo_root=tmp_path, invoker=recording, max_file_bytes=120
    )
    assert "def target_symbol()" in captured["prompt"]
    assert "# header 0" not in captured["prompt"]


def test_grounding_prompt_uses_symbol_excerpt_for_rough_notes_heading(
    tmp_path: Path,
) -> None:
    code_path = tmp_path / "src" / "notes_target.py"
    code_path.parent.mkdir()
    code_path.write_text(
        "\n".join(f"# preface {i}" for i in range(80))
        + "\n\n\nclass HeadingSymbol:\n    pass\n",
        encoding="utf-8",
    )
    src = _write_notes(
        tmp_path,
        "notes.md",
        "# Verify HeadingSymbol\n\nReview `src/notes_target.py`.\n",
    )
    captured: dict[str, str] = {}

    def recording(prompt: str) -> str:
        captured["prompt"] = prompt
        return _canned(
            [{"heading": "Verify HeadingSymbol", "status": "NOT-IMPLEMENTED",
              "code_refs": []}]
        )

    classify_plan_implementation(
        src, repo_root=tmp_path, invoker=recording, max_file_bytes=120
    )
    assert "class HeadingSymbol" in captured["prompt"]
    assert "# preface 0" not in captured["prompt"]


def test_grounding_excerpt_preserves_skip_counts_and_resolved_paths(
    tmp_path: Path,
) -> None:
    detail_rel = "details/step1.md"
    detail_path = tmp_path / detail_rel
    detail_path.parent.mkdir(parents=True)
    detail_path.write_text("spec body\n", encoding="utf-8")
    code_path = tmp_path / "src" / "code.py"
    code_path.parent.mkdir()
    code_path.write_text(
        "\n".join(f"# header {i}" for i in range(80))
        + "\n\n\ndef counted_symbol():\n    return 1\n",
        encoding="utf-8",
    )
    plan = _write_plan_file(
        tmp_path,
        steps=[Step(id=1, title="Implement counted_symbol", detail=detail_rel)],
    )
    plan.write_text(
        plan.read_text(encoding="utf-8")
        + (
            "\nSee `src/code.py`, `src/./code.py`, "
            "`src/missing.py`, and `details/step1.md`.\n"
        ),
        encoding="utf-8",
    )
    captured: dict[str, str] = {}

    def recording(prompt: str) -> str:
        captured["prompt"] = prompt
        return _canned(
            [{"heading": "Implement counted_symbol", "status": "NOT-IMPLEMENTED",
              "code_refs": [], "is_step": True}]
        )

    result = classify_plan_implementation(
        plan, repo_root=tmp_path, invoker=recording, max_file_bytes=120
    )
    assert result.grounded_files == (code_path.resolve(),)
    assert result.grounding_candidate_count == 4
    assert result.grounding_skipped_count == 3
    assert result.grounding_skip_reasons == (
        "details/step1.md: grounding skipped plan detail file",
        "src/code.py: grounding skipped duplicate file",
        "src/missing.py: grounding skipped unresolved file",
    )
    assert "def counted_symbol()" in captured["prompt"]


def test_ground_source_excerpt_contract_survives_cleanup(
    tmp_path: Path,
) -> None:
    code_path = tmp_path / "src" / "cleanup.py"
    code_path.parent.mkdir()
    code_path.write_text(
        "\n".join(f"# preface {i}" for i in range(80))
        + "\n\n\ndef cleanup_symbol():\n    return 1\n",
        encoding="utf-8",
    )
    src = _write_notes(
        tmp_path,
        "notes.md",
        "# Verify cleanup_symbol\n\n"
        "Review `src/cleanup.py`, `src/./cleanup.py`, and `src/missing.py`.\n",
    )
    captured: dict[str, str] = {}

    def recording(prompt: str) -> str:
        captured["prompt"] = prompt
        return _canned(
            [{"heading": "Verify cleanup_symbol", "status": "NOT-IMPLEMENTED",
              "code_refs": []}]
        )

    result = classify_plan_implementation(
        src, repo_root=tmp_path, invoker=recording, max_file_bytes=120
    )

    assert result.grounded_files == (code_path.resolve(),)
    assert result.grounding_candidate_count == 3
    assert result.grounding_skipped_count == 2
    assert result.grounding_skip_reasons == (
        "src/cleanup.py: grounding skipped duplicate file",
        "src/missing.py: grounding skipped unresolved file",
    )
    assert "def cleanup_symbol()" in captured["prompt"]
    assert "# preface 0" not in captured["prompt"]


def test_grounding_excerpt_fallback_keeps_truncation_signal(
    tmp_path: Path,
) -> None:
    code_path = tmp_path / "src" / "fallback.py"
    code_path.parent.mkdir()
    code_path.write_text(
        "def actual_symbol():\n    return 1\n\n" + ("x" * 500),
        encoding="utf-8",
    )
    src = _write_notes(
        tmp_path,
        "notes.md",
        "# MissingSymbol\n\nReview `src/fallback.py`.\n",
    )
    captured: dict[str, str] = {}

    def recording(prompt: str) -> str:
        captured["prompt"] = prompt
        return _canned(
            [{"heading": "MissingSymbol", "status": "NOT-IMPLEMENTED",
              "code_refs": []}]
        )

    classify_plan_implementation(
        src, repo_root=tmp_path, invoker=recording, max_file_bytes=120
    )
    assert "excerpt_kind=fallback" in captured["prompt"]
    assert "fallback_reason=no-symbol-match" in captured["prompt"]
    assert "truncated=true" in captured["prompt"]
    assert "fallback preview: no-symbol-match" in captured["prompt"]
    assert "_(truncated)_" in captured["prompt"]
    assert "x" * 200 not in captured["prompt"]


# --- prompt rendering -------------------------------------------------------


def test_prompt_includes_source_and_grounded_block(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "code.py").write_text(
        "def grounded_marker():\n    return 1\n", encoding="utf-8"
    )
    src = _write_notes(
        tmp_path, "notes.md", "SOURCE_MARKER cites `src/code.py`.\n"
    )
    captured: dict[str, str] = {}

    def recording(prompt: str) -> str:
        captured["prompt"] = prompt
        return _canned(
            [{"heading": "notes.md", "status": "PARTIAL", "code_refs": ["x"]}]
        )

    classify_plan_implementation(src, repo_root=tmp_path, invoker=recording)
    assert "SOURCE_MARKER" in captured["prompt"]
    assert "grounded_marker" in captured["prompt"]


def test_prompt_includes_step_detail_spec(tmp_path: Path) -> None:
    detail_rel = "details/step1.md"
    detail_path = tmp_path / detail_rel
    detail_path.parent.mkdir(parents=True)
    detail_path.write_text("STEP_SPEC_MARKER body\n", encoding="utf-8")
    plan = _write_plan_file(
        tmp_path,
        steps=[Step(id=1, title="Do the work", detail=detail_rel)],
    )
    captured: dict[str, str] = {}

    def recording(prompt: str) -> str:
        captured["prompt"] = prompt
        return _canned(
            [{"heading": "Do the work", "status": "NOT-IMPLEMENTED",
              "code_refs": [], "is_step": True}]
        )

    classify_plan_implementation(plan, repo_root=tmp_path, invoker=recording)
    assert "STEP_SPEC_MARKER" in captured["prompt"]


def test_step_detail_files_excluded_from_grounding(tmp_path: Path) -> None:
    # The plan body cites its own detail file; it must be loaded as spec,
    # not injected into the grounded-code block.
    detail_rel = "details/step1.md"
    detail_path = tmp_path / detail_rel
    detail_path.parent.mkdir(parents=True)
    detail_path.write_text("spec body\n", encoding="utf-8")
    plan = _write_plan_file(
        tmp_path,
        steps=[Step(id=1, title="Do the work", detail=detail_rel)],
    )
    # Append a body reference to the detail file so it shows up as a candidate.
    plan.write_text(
        plan.read_text(encoding="utf-8") + f"\nSee `{detail_rel}`.\n",
        encoding="utf-8",
    )
    response = _canned(
        [{"heading": "Do the work", "status": "NOT-IMPLEMENTED",
          "code_refs": [], "is_step": True}]
    )
    result = classify_plan_implementation(
        plan, repo_root=tmp_path, invoker=_stub(response)
    )
    assert all(
        detail_path.resolve() != p for p in result.grounded_files
    )


def test_load_step_specs_still_bounds_specs_after_cleanup(
    tmp_path: Path,
) -> None:
    detail_rel = "details/step1.md"
    detail_path = tmp_path / detail_rel
    detail_path.parent.mkdir(parents=True)
    detail_path.write_text("SPEC-" + ("x" * 200), encoding="utf-8")
    plan = _write_plan_file(
        tmp_path,
        steps=[Step(id=1, title="Do the work", detail=detail_rel)],
    )

    specs = _load_step_specs(
        plan.read_text(encoding="utf-8"),
        repo_root=tmp_path,
        max_file_bytes=20,
    )

    assert specs == (
        (
            "Do the work",
            "[truncated to first 20 bytes — symbols past the cut may exist]\n"
            "SPEC-xxxxxxxxxxxxxxx",
        ),
    )


def test_render_annotate_prompt_substitutes_placeholders() -> None:
    rendered = render_annotate_prompt("BODY_X", "SPECS_X", "GROUND_X")
    assert "BODY_X" in rendered
    assert "SPECS_X" in rendered
    assert "GROUND_X" in rendered
    assert "${" not in rendered


def test_response_contract_examples_cover_all_model_statuses() -> None:
    rendered = render_annotate_prompt("BODY_X", "SPECS_X", "GROUND_X")
    for status in ("IMPLEMENTED", "PARTIAL", "NOT-IMPLEMENTED"):
        assert f'"status": "{status}"' in rendered


# --- optional-key parsing ---------------------------------------------------


def test_low_confidence_flag_parsed(tmp_path: Path) -> None:
    _write_grounding_files(tmp_path, "src/a.py", "src/b.py", "src/c.py")
    (tmp_path / "src" / "b.py").write_text(
        "def y():\n    return None\n", encoding="utf-8"
    )
    src = _write_notes(
        tmp_path,
        "notes.md",
        "References `src/a.py`, `src/b.py`, and `src/c.py`.\n",
    )
    response = _canned(
        [
            {"heading": "A", "status": "IMPLEMENTED",
             "code_refs": ["a.py:x"], "confidence_low": True},
            {"heading": "B", "status": "IMPLEMENTED",
             "code_refs": ["src/b.py:y"]},
        ]
    )
    result = classify_plan_implementation(
        src, repo_root=tmp_path, invoker=_stub(response)
    )
    assert result.sections[0].low_confidence is True
    assert result.sections[1].low_confidence is False


def test_partial_remaining_work_parsed(tmp_path: Path) -> None:
    _write_grounding_files(tmp_path, "src/a.py", "src/b.py", "src/c.py")
    src = _write_notes(
        tmp_path,
        "notes.md",
        "References `src/a.py`, `src/b.py`, and `src/c.py`.\n",
    )
    response = _canned(
        [
            {"heading": "A", "status": "PARTIAL", "code_refs": ["a.py:x"],
             "remaining": "resolver in step 6 still missing"},
            {"heading": "B", "status": "IMPLEMENTED", "code_refs": ["b.py:y"]},
        ]
    )
    result = classify_plan_implementation(
        src, repo_root=tmp_path, invoker=_stub(response)
    )
    assert result.sections[0].remaining_work == "resolver in step 6 still missing"
    assert result.sections[1].remaining_work == ""


def test_is_step_flag_parsed(tmp_path: Path) -> None:
    src = _write_notes(tmp_path, "notes.md", "notes")
    response = _canned(
        [
            {"heading": "Step 1", "status": "NOT-IMPLEMENTED",
             "code_refs": [], "is_step": True},
            {"heading": "Overview", "status": "NOT-IMPLEMENTED",
             "code_refs": []},
        ]
    )
    result = classify_plan_implementation(
        src, repo_root=tmp_path, invoker=_stub(response)
    )
    assert result.sections[0].is_step is True
    assert result.sections[1].is_step is False


def test_heading_less_source_classified_as_one_section(tmp_path: Path) -> None:
    src = _write_notes(
        tmp_path, "rough.md", "just some freeform thoughts, no headings\n"
    )
    response = _canned(
        [{"heading": "rough.md", "status": "NOT-IMPLEMENTED", "code_refs": []}]
    )
    result = classify_plan_implementation(
        src, repo_root=tmp_path, invoker=_stub(response)
    )
    assert len(result.sections) == 1
