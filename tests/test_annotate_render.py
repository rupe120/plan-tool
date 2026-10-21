"""Unit tests for the two pure renderers in :mod:`plan_tool.annotate_render`.

All tests run over hand-built :class:`PlanAnnotation` fixtures — the
renderers never call Claude, so there is no invoker stub and no
``main([...])`` here (that is step 3's integration concern).
"""

from __future__ import annotations

import difflib
from pathlib import Path

import pytest

from plan_tool.annotate import AnnotationStatus, PlanAnnotation, SectionAnnotation
from plan_tool.annotate_render import (
    parse_cached_annotated_report,
    render_annotated_report,
    render_create_seed,
)
from plan_tool.create import validate_from_existing_seed


def _annotation(
    *,
    source_text: str = "",
    sections: tuple[SectionAnnotation, ...] = (),
    source_path: Path = Path("docs/plan.md"),
    repo_root: Path = Path("/repo"),
    grounded_files: tuple[Path, ...] = (),
    low_grounding: bool = False,
    grounding_candidate_count: int = 0,
    grounding_skipped_count: int = 0,
    annotated_at: str = "",
) -> PlanAnnotation:
    return PlanAnnotation(
        source_path=source_path,
        source_text=source_text,
        repo_root=repo_root,
        grounded_files=grounded_files,
        sections=sections,
        low_grounding=low_grounding,
        annotated_at=annotated_at,
        grounding_candidate_count=grounding_candidate_count,
        grounding_skipped_count=grounding_skipped_count,
    )


def _is_subsequence(needles: list[str], haystack: list[str]) -> bool:
    """True when ``needles`` appears in order (not necessarily contiguous) in ``haystack``."""
    matcher = difflib.SequenceMatcher(a=needles, b=haystack, autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    return matched == len(needles)


# --- report: additive guarantee ---------------------------------------------


def test_report_preserves_every_original_line():
    source = "# Title\n\nSome prose.\n\n## Goal\n\nDo the thing.\n"
    ann = _annotation(
        source_text=source,
        sections=(
            SectionAnnotation(
                heading="Goal",
                status=AnnotationStatus.IMPLEMENTED,
                evidence="done",
                code_refs=("a.py:foo",),
            ),
        ),
    )
    report_lines = render_annotated_report(ann).splitlines()
    assert _is_subsequence(source.splitlines(), report_lines)


def test_report_inserts_status_block_under_each_heading():
    source = "## One\n\nbody\n\n## Two\n\nbody\n\n## Three\n\nbody\n"
    ann = _annotation(
        source_text=source,
        sections=(
            SectionAnnotation(heading="One", status=AnnotationStatus.IMPLEMENTED, evidence="e1", code_refs=("a.py:1",)),
            SectionAnnotation(heading="Two", status=AnnotationStatus.PARTIAL, evidence="e2", code_refs=("b.py:2",), remaining_work="rest"),
            SectionAnnotation(heading="Three", status=AnnotationStatus.NOT_IMPLEMENTED, evidence="e3"),
        ),
    )
    lines = render_annotated_report(ann).splitlines()
    for heading, label in (("## One", "IMPLEMENTED"), ("## Two", "PARTIAL"), ("## Three", "NOT IMPLEMENTED")):
        idx = lines.index(heading)
        # the next non-blank line after the heading is the status block
        following = [ln for ln in lines[idx + 1 :] if ln.strip()][0]
        assert following.startswith("> **" + label + "**")


def test_report_status_block_renders_evidence_and_refs():
    source = "## Goal\n\nbody\n"
    ann = _annotation(
        source_text=source,
        sections=(
            SectionAnnotation(
                heading="Goal",
                status=AnnotationStatus.IMPLEMENTED,
                evidence="the goal is met",
                code_refs=("schema.py:Table", "create.py:run"),
            ),
        ),
    )
    report = render_annotated_report(ann)
    assert "the goal is met" in report
    assert "`schema.py:Table`" in report
    assert "`create.py:run`" in report


def test_report_not_implemented_label_has_space():
    ann = _annotation(
        source_text="## Goal\n\nbody\n",
        sections=(
            SectionAnnotation(heading="Goal", status=AnnotationStatus.NOT_IMPLEMENTED, evidence="nope"),
        ),
    )
    report = render_annotated_report(ann)
    # the human-facing status block uses the spaced form, not the wire form
    block = [ln for ln in report.splitlines() if ln.startswith("> **NOT")][0]
    assert "> **NOT IMPLEMENTED**" in block


def test_report_coverage_summary_counts():
    ann = _annotation(
        source_text="## A\n## B\n## C\n",
        sections=(
            SectionAnnotation(heading="A", status=AnnotationStatus.IMPLEMENTED, evidence="", code_refs=("x:1",)),
            SectionAnnotation(heading="B", status=AnnotationStatus.PARTIAL, evidence="", code_refs=("y:1",), remaining_work="r"),
            SectionAnnotation(heading="C", status=AnnotationStatus.NOT_IMPLEMENTED, evidence=""),
        ),
    )
    summary = [ln for ln in render_annotated_report(ann).splitlines() if ln.startswith("> **Coverage:**")][0]
    assert "1 IMPLEMENTED" in summary
    assert "1 PARTIAL" in summary
    assert "1 NOT-IMPLEMENTED" in summary


def test_report_low_confidence_marked():
    ann = _annotation(
        source_text="## Goal\n\nbody\n",
        sections=(
            SectionAnnotation(
                heading="Goal",
                status=AnnotationStatus.IMPLEMENTED,
                evidence="maybe",
                code_refs=("a.py:1",),
                low_confidence=True,
            ),
        ),
    )
    report = render_annotated_report(ann)
    block = [ln for ln in report.splitlines() if ln.startswith("> **IMPLEMENTED**")][0]
    assert "_(low confidence)_" in block
    summary = [ln for ln in report.splitlines() if ln.startswith("> **Coverage:**")][0]
    assert "1 low-confidence" in summary


def test_report_needs_review_marked():
    ann = _annotation(
        source_text="## Goal\n\nbody\n",
        sections=(
            SectionAnnotation(
                heading="Goal",
                status=AnnotationStatus.NEEDS_REVIEW,
                evidence="contradictory verdict",
                code_refs=("a.py:1",),
                low_confidence=True,
                contradiction_review=True,
            ),
        ),
    )
    report = render_annotated_report(ann)
    block = [ln for ln in report.splitlines() if ln.startswith("> **NEEDS-REVIEW**")][0]
    summary = [ln for ln in report.splitlines() if ln.startswith("> **Coverage:**")][0]
    assert "contradictory verdict" in block
    assert "`a.py:1`" in block
    assert "1 NEEDS-REVIEW" in summary


def test_report_unmatched_section_appended():
    source = "## Present\n\nbody\n"
    ann = _annotation(
        source_text=source,
        sections=(
            SectionAnnotation(heading="Present", status=AnnotationStatus.IMPLEMENTED, evidence="ok", code_refs=("a:1",)),
            SectionAnnotation(heading="Ghost", status=AnnotationStatus.NOT_IMPLEMENTED, evidence="absent from body"),
        ),
    )
    report = render_annotated_report(ann)
    assert "Annotate — unmatched sections" in report
    assert "Ghost" in report
    assert _is_subsequence(source.splitlines(), report.splitlines())


def test_direct_annotate_renderers_reject_unmatched_source_fence() -> None:
    from plan_tool.annotate import AnnotateError

    annotation = _annotation(source_text="## Scope\n\n```\n")

    with pytest.raises(AnnotateError, match="unmatched opening code fence"):
        render_annotated_report(annotation)
    with pytest.raises(AnnotateError, match="unmatched opening code fence"):
        render_create_seed(annotation, report_path=Path("report.md"))


def test_report_plan_step_verdicts_anchored_in_steps_region():
    source = (
        "# Plan\n\n## Overview\n\nprose\n\n## Steps\n\n1. first\n2. second\n\n## Done\n"
    )
    ann = _annotation(
        source_text=source,
        sections=(
            SectionAnnotation(heading="Overview", status=AnnotationStatus.IMPLEMENTED, evidence="o", code_refs=("a:1",)),
            SectionAnnotation(heading="Add the resolver", status=AnnotationStatus.PARTIAL, evidence="s1", code_refs=("b:1",), remaining_work="rest", is_step=True),
            SectionAnnotation(heading="Wire the CLI", status=AnnotationStatus.NOT_IMPLEMENTED, evidence="s2", is_step=True),
        ),
    )
    lines = render_annotated_report(ann).splitlines()
    steps_idx = lines.index("## Steps")
    done_idx = lines.index("## Done")
    region = "\n".join(lines[steps_idx:done_idx])
    assert "> **Add the resolver**" in region
    assert "> **Wire the CLI**" in region
    # not pushed to the addendum
    assert "Annotate — unmatched sections" not in render_annotated_report(ann)


def test_report_header_records_source_and_repo_root():
    ann = _annotation(
        source_text="## A\n",
        source_path=Path("docs/myplan.md"),
        repo_root=Path("/some/repo/root"),
        sections=(SectionAnnotation(heading="A", status=AnnotationStatus.NOT_IMPLEMENTED, evidence=""),),
    )
    report = render_annotated_report(ann)
    assert "source: docs/myplan.md" in report
    assert "repo_root: /some/repo/root" in report


def test_report_header_records_grounding_counts():
    ann = _annotation(
        source_text="## A\n",
        grounded_files=(Path("/repo/a.py"),),
        grounding_candidate_count=3,
        grounding_skipped_count=2,
        sections=(SectionAnnotation(heading="A", status=AnnotationStatus.NOT_IMPLEMENTED, evidence=""),),
    )
    report = render_annotated_report(ann)
    assert "grounded_files: 1" in report
    assert "candidate_text_files: 3" in report
    assert "skipped_or_unreadable_files: 2" in report


def test_cached_report_parser_reads_rollup_metadata(tmp_path: Path) -> None:
    report_path = tmp_path / "plan.annotated.md"
    report_path.write_text(
        render_annotated_report(
            _annotation(
                source_text="## A\n## B\n## C\n## D\n",
                source_path=Path("plans/1-demo.md"),
                grounded_files=(Path("/repo/a.py"), Path("/repo/b.py")),
                annotated_at="2026-07-05T12:34:56Z",
                sections=(
                    SectionAnnotation(
                        heading="A",
                        status=AnnotationStatus.IMPLEMENTED,
                        evidence="",
                        code_refs=("a:1",),
                    ),
                    SectionAnnotation(
                        heading="B",
                        status=AnnotationStatus.PARTIAL,
                        evidence="",
                        code_refs=("b:1",),
                        remaining_work="rest",
                    ),
                    SectionAnnotation(
                        heading="C",
                        status=AnnotationStatus.NOT_IMPLEMENTED,
                        evidence="",
                    ),
                    SectionAnnotation(
                        heading="D",
                        status=AnnotationStatus.NEEDS_REVIEW,
                        evidence="review",
                    ),
                ),
            )
        ),
        encoding="utf-8",
    )

    cached = parse_cached_annotated_report(report_path)

    assert cached is not None
    assert cached.source_path == Path("plans/1-demo.md")
    assert cached.annotated_at == "2026-07-05T12:34:56Z"
    assert cached.grounded_files == 2
    assert cached.implemented == 1
    assert cached.partial == 1
    assert cached.not_implemented == 1
    assert cached.needs_review == 1


def test_report_low_grounding_banner_renders():
    ann = _annotation(
        source_text="## A\n",
        low_grounding=True,
        grounding_candidate_count=3,
        grounding_skipped_count=3,
        sections=(
            SectionAnnotation(
                heading="A",
                status=AnnotationStatus.NEEDS_REVIEW,
                evidence="verify",
                code_refs=("a.py:x",),
                low_confidence=True,
                low_grounding=True,
            ),
        ),
    )
    report = render_annotated_report(ann)
    assert "**Low grounding (0 files)**" in report
    assert "Candidates: 3" in report
    assert "skipped/unreadable: 3" in report


def test_report_all_implemented_coverage_100():
    ann = _annotation(
        source_text="## A\n## B\n",
        sections=(
            SectionAnnotation(heading="A", status=AnnotationStatus.IMPLEMENTED, evidence="", code_refs=("a:1",)),
            SectionAnnotation(heading="B", status=AnnotationStatus.IMPLEMENTED, evidence="", code_refs=("b:1",)),
        ),
    )
    summary = [ln for ln in render_annotated_report(ann).splitlines() if ln.startswith("> **Coverage:**")][0]
    assert "100% implemented" in summary


# --- seed: carryover scoping -------------------------------------------------


def _seed(ann: PlanAnnotation, report_path: Path = Path("docs/plan.annotated.md")) -> str:
    return render_create_seed(ann, report_path=report_path)


def test_seed_carryover_scope_is_remaining_work_and_not_implemented():
    ann = _annotation(
        sections=(
            SectionAnnotation(heading="Done bit", status=AnnotationStatus.IMPLEMENTED, evidence="", code_refs=("a:1",)),
            SectionAnnotation(heading="Half bit", status=AnnotationStatus.PARTIAL, evidence="", code_refs=("b:1",), remaining_work="finish it"),
            SectionAnnotation(heading="Missing bit", status=AnnotationStatus.NOT_IMPLEMENTED, evidence="not started"),
        ),
    )
    seed = _seed(ann)
    carryover = seed.split("## Already implemented")[0]
    assert "Half bit" in carryover
    assert "Missing bit" in carryover
    assert "Done bit" not in carryover


def test_seed_partial_scopes_remaining_work_not_implemented_refs():
    ann = _annotation(
        sections=(
            SectionAnnotation(
                heading="Resolver",
                status=AnnotationStatus.PARTIAL,
                evidence="some done",
                code_refs=("schema.py:Table",),
                remaining_work="resolver in step 6 still missing",
            ),
        ),
    )
    seed = _seed(ann)
    carryover = seed.split("## Already implemented")[0]
    done = seed.split("## Already implemented")[1].split("## Provenance")[0]
    assert "resolver in step 6 still missing" in carryover
    assert "schema.py:Table" not in carryover
    assert "schema.py:Table" in done


def test_seed_partial_implemented_half_in_done_context():
    ann = _annotation(
        sections=(
            SectionAnnotation(
                heading="Resolver",
                status=AnnotationStatus.PARTIAL,
                evidence="",
                code_refs=("schema.py:Table", "resolver.py:run"),
                remaining_work="rest",
            ),
        ),
    )
    done = _seed(ann).split("## Already implemented")[1]
    assert "partial — done half" in done
    assert "`schema.py:Table`" in done
    assert "`resolver.py:run`" in done


def test_seed_partial_empty_remaining_work_falls_back_to_evidence():
    ann = _annotation(
        sections=(
            SectionAnnotation(
                heading="Resolver",
                status=AnnotationStatus.PARTIAL,
                evidence="evidence about the partial work",
                code_refs=("a:1",),
                remaining_work="",
            ),
        ),
    )
    seed = _seed(ann)
    carryover = seed.split("## Already implemented")[0]
    assert "Resolver" in carryover
    assert "evidence about the partial work" in carryover
    assert "remainder not pinned" in carryover


def test_seed_done_context_lists_implemented():
    ann = _annotation(
        sections=(
            SectionAnnotation(heading="Done bit", status=AnnotationStatus.IMPLEMENTED, evidence="", code_refs=("a.py:1",)),
        ),
    )
    seed = _seed(ann)
    carryover = seed.split("## Already implemented")[0]
    done = seed.split("## Already implemented")[1]
    assert "Done bit" not in carryover
    assert "Done bit" in done
    assert "`a.py:1`" in done


def test_seed_records_report_and_source_provenance():
    ann = _annotation(source_path=Path("docs/orig.md"), sections=(
        SectionAnnotation(heading="A", status=AnnotationStatus.NOT_IMPLEMENTED, evidence=""),
    ))
    seed = _seed(ann, report_path=Path("docs/orig.annotated.md"))
    assert "docs/orig.md" in seed
    assert "docs/orig.annotated.md" in seed
    prov = seed.split("## Provenance")[1]
    assert "Original: docs/orig.md" in prov
    assert "Report: docs/orig.annotated.md" in prov


def test_seed_preserves_source_references_or_uses_source_fallback():
    sourced = _seed(
        _annotation(
            source_path=Path("docs/orig.md"),
            source_text="## References\n\n- [API](https://example.test/api)\n",
            sections=(
                SectionAnnotation(
                    heading="A", status=AnnotationStatus.NOT_IMPLEMENTED, evidence=""
                ),
            ),
        )
    )
    sourced_references = sourced.split("## References", 1)[1].split(
        "## Provenance", 1
    )[0]
    assert "[API](https://example.test/api)" in sourced_references

    fallback = _seed(
        _annotation(
            source_path=Path("docs/orig.md"),
            sections=(
                SectionAnnotation(
                    heading="A", status=AnnotationStatus.NOT_IMPLEMENTED, evidence=""
                ),
            ),
        ),
        report_path=Path("docs/orig.annotated.md"),
    )
    assert "- Source document: `docs/orig.md`" in fallback
    assert "- Annotated report: `docs/orig.annotated.md`" in fallback


def test_seed_frontmatter_only_references_uses_source_fallback():
    seed = _seed(
        _annotation(
            source_path=Path("docs/orig.md"),
            source_text="---\n## References\n---\n# Source\n\n## Overview\n\nBody.\n",
            sections=(
                SectionAnnotation(
                    heading="A", status=AnnotationStatus.NOT_IMPLEMENTED, evidence=""
                ),
            ),
        ),
        report_path=Path("docs/orig.annotated.md"),
    )
    references = seed.split("## References", 1)[1].split("## Provenance", 1)[0]
    assert "- Source document: `docs/orig.md`" in references
    assert "- Annotated report: `docs/orig.annotated.md`" in references
    assert "## References" not in references
    validate_from_existing_seed(seed)


def test_seed_fenced_only_references_uses_source_fallback():
    seed = _seed(
        _annotation(
            source_path=Path("docs/orig.md"),
            source_text=(
                "```markdown\n## References\n- https://example.test/api\n```\n"
            ),
            sections=(
                SectionAnnotation(
                    heading="A", status=AnnotationStatus.NOT_IMPLEMENTED, evidence=""
                ),
            ),
        ),
        report_path=Path("docs/orig.annotated.md"),
    )

    references = seed.split("## References", 1)[1].split("## Provenance", 1)[0]
    assert "- Source document: `docs/orig.md`" in references
    assert "https://example.test/api" not in references
    validate_from_existing_seed(seed)


def test_seed_preserves_body_references_after_frontmatter():
    seed = _seed(
        _annotation(
            source_text=(
                "---\n## References\n---\n# Source\n\n## References\n\n"
                "- `plan_tool/annotate_render.py`\n"
            ),
            sections=(
                SectionAnnotation(
                    heading="A", status=AnnotationStatus.NOT_IMPLEMENTED, evidence=""
                ),
            ),
        )
    )
    references = seed.split("## References", 1)[1].split("## Provenance", 1)[0]
    assert "`plan_tool/annotate_render.py`" in references
    assert "Source document:" not in references
    validate_from_existing_seed(seed)


@pytest.mark.parametrize("placeholder", ["TODO", "(TODO)", "_(TODO)_"])
def test_seed_replaces_placeholder_source_references_with_fallback(placeholder):
    seed = _seed(
        _annotation(
            source_path=Path("docs/orig.md"),
            source_text=f"## References\n\n{placeholder}\n",
            sections=(
                SectionAnnotation(
                    heading="A", status=AnnotationStatus.NOT_IMPLEMENTED, evidence=""
                ),
            ),
        ),
        report_path=Path("docs/orig.annotated.md"),
    )
    references = seed.split("## References", 1)[1].split("## Provenance", 1)[0]
    assert "- Source document: `docs/orig.md`" in references
    assert placeholder not in references


def test_seed_low_confidence_implemented_flagged_not_replanned():
    ann = _annotation(
        sections=(
            SectionAnnotation(heading="Maybe done", status=AnnotationStatus.IMPLEMENTED, evidence="", code_refs=("a:1",), low_confidence=True),
        ),
    )
    seed = _seed(ann)
    carryover = seed.split("## Already implemented")[0]
    done = seed.split("## Already implemented")[1]
    assert "Maybe done" not in carryover
    assert "Maybe done" in done
    assert "(low confidence)" in done


def test_seed_low_confidence_partial_flagged_in_both_halves():
    ann = _annotation(
        sections=(
            SectionAnnotation(
                heading="Half done",
                status=AnnotationStatus.PARTIAL,
                evidence="",
                code_refs=("a:1",),
                remaining_work="finish",
                low_confidence=True,
            ),
        ),
    )
    seed = _seed(ann)
    carryover = seed.split("## Already implemented")[0]
    done = seed.split("## Already implemented")[1].split("## Provenance")[0]
    assert "low confidence" in carryover
    assert "low confidence" in done


def test_seed_low_grounding_implemented_needs_review_carries_verification_work():
    ann = _annotation(
        sections=(
            SectionAnnotation(
                heading="Maybe done",
                status=AnnotationStatus.NEEDS_REVIEW,
                evidence="Low grounding makes this speculative.",
                code_refs=("a.py:x",),
                low_confidence=True,
                low_grounding=True,
            ),
        ),
    )
    carryover = _seed(ann).split("## Already implemented")[0]
    assert "Maybe done" in carryover
    assert "[NEEDS-REVIEW]" in carryover
    assert "Low grounding makes this speculative." in carryover


def test_seed_low_grounding_partial_marks_review_required_carryover():
    ann = _annotation(
        sections=(
            SectionAnnotation(
                heading="Half done",
                status=AnnotationStatus.PARTIAL,
                evidence="",
                code_refs=("a.py:x",),
                remaining_work="finish the rest",
                low_confidence=True,
                low_grounding=True,
            ),
        ),
    )
    carryover = _seed(ann).split("## Already implemented")[0]
    assert "[PARTIAL — review-required remaining]" in carryover
    assert "finish the rest" in carryover
    assert "Review required: grounding was too thin" in carryover


def test_seed_single_synthesized_section_partial_splits():
    ann = _annotation(
        source_path=Path("rough-notes.md"),
        sections=(
            SectionAnnotation(
                heading="rough-notes.md",
                status=AnnotationStatus.PARTIAL,
                evidence="",
                code_refs=("impl.py:done",),
                remaining_work="the rest is undone",
            ),
        ),
    )
    seed = _seed(ann)
    carryover = seed.split("## Already implemented")[0]
    done = seed.split("## Already implemented")[1]
    assert "the rest is undone" in carryover
    assert "`impl.py:done`" in done


def test_seed_all_implemented_renders_empty_carryover_marker():
    ann = _annotation(
        sections=(
            SectionAnnotation(heading="A", status=AnnotationStatus.IMPLEMENTED, evidence="", code_refs=("a:1",)),
            SectionAnnotation(heading="B", status=AnnotationStatus.IMPLEMENTED, evidence="", code_refs=("b:1",)),
        ),
    )
    seed = _seed(ann)
    assert "## Carryover scope (remaining work)" in seed
    carryover = seed.split("## Already implemented")[0]
    assert "No remaining work — every section is implemented." in carryover


def test_seed_excludes_contradiction_derived_needs_review_from_carryover():
    ann = _annotation(
        sections=(
            SectionAnnotation(
                heading="Contradictory",
                status=AnnotationStatus.NEEDS_REVIEW,
                evidence="model contradicted itself",
                code_refs=("a.py:1",),
                low_confidence=True,
                contradiction_review=True,
            ),
            SectionAnnotation(
                heading="Manual review",
                status=AnnotationStatus.NEEDS_REVIEW,
                evidence="operator requested review",
                low_confidence=True,
            ),
        ),
    )
    seed = _seed(ann)
    carryover = seed.split("## Already implemented")[0]
    assert "Contradictory" not in carryover
    assert "model contradicted itself" not in carryover
    assert "Manual review" in carryover
    assert "[NEEDS-REVIEW]" in carryover


def test_seed_contradiction_only_carryover_uses_review_empty_state():
    ann = _annotation(
        sections=(
            SectionAnnotation(
                heading="Contradictory",
                status=AnnotationStatus.NEEDS_REVIEW,
                evidence="model contradicted itself",
                code_refs=("a.py:1",),
                low_confidence=True,
                contradiction_review=True,
            ),
        ),
    )
    carryover = _seed(ann).split("## Already implemented")[0]
    assert "Contradictory" not in carryover
    assert "No carryover scope selected" in carryover
    assert "every section is implemented" not in carryover


def test_seed_contradiction_review_stays_done_context():
    ann = _annotation(
        sections=(
            SectionAnnotation(
                heading="Contradictory done claim",
                status=AnnotationStatus.NEEDS_REVIEW,
                evidence="model contradicted itself",
                code_refs=("a.py:1",),
                low_confidence=True,
                contradiction_review=True,
            ),
        ),
    )
    seed = _seed(ann)
    carryover, _, done = seed.partition(
        "## Already implemented (done-context — do not re-plan)"
    )
    assert "Contradictory done claim" not in carryover
    assert "Contradictory done claim" in done
    assert "`a.py:1`" in done


# --- purity ------------------------------------------------------------------


def test_renderers_are_pure_no_side_effects():
    ann = _annotation(
        source_text="## A\n\nbody\n",
        sections=(
            SectionAnnotation(heading="A", status=AnnotationStatus.PARTIAL, evidence="e", code_refs=("a:1",), remaining_work="r"),
        ),
    )
    assert render_annotated_report(ann) == render_annotated_report(ann)
    rp = Path("docs/x.annotated.md")
    assert render_create_seed(ann, report_path=rp) == render_create_seed(ann, report_path=rp)
