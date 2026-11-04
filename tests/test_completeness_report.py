"""Tests for plan_tool.completeness_report — disposition classification,
report assembly, the 'why it wasn't addressed' rationale, and persistence.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import dataclasses
from types import SimpleNamespace
from typing import Optional

import plan_tool.completeness_report as completeness_report_module
from plan_tool.review import indent_bullet_body
import pytest

from plan_tool.completeness_report import (
    AuditShapeAdvisoryDisplay,
    AppliedOutcome,
    ReusableAudit,
    WHY,
    next_step_gaps,
    build_report_md,
    compute_code_fingerprint,
    console_summary,
    deferred_kind,
    next_stage_command,
    prepare_audit_shape_advisory_display,
    resolve_reusable_audit,
    suggested_next_step_commands,
    suggested_next_steps,
    write_completeness_report,
)
from plan_tool.parser import parse_plan
from plan_tool.review import Recommendation
from plan_tool.review_persistence import (
    compute_plan_fingerprint,
    load_review,
    save_review,
)
from plan_tool.schema import Plan, Step
from plan_tool.cli.completeness_phases import (
    _DeterministicReport,
    _render_completeness_json,
    _render_coverage_confidence_markdown,
    _render_grouped_report,
)


def _rec(rec_id: str, source: str, severity: str = "medium", **kw):
    kw.setdefault("step_id", None)
    return Recommendation(
        id=rec_id, source=source, severity=severity,
        title=f"title {rec_id}", body=f"body {rec_id}", **kw,
    )


def _write_minimal_plan(plan_path: Path) -> None:
    """Bare single-step plan so derive-at-write can resolve audit_stage."""
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(
        "---\n"
        "title: Test plan\n"
        "status: planning\n"
        "priority: medium\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: First step\n"
        "    files: [one.py]\n"
        "---\n"
        "# Test\n",
        encoding="utf-8",
    )


def _fresh_advisory_display(tmp_path: Path) -> AuditShapeAdvisoryDisplay:
    from plan_tool.audit_shapes import AuditShapeAdvisory, AuditShapeFindingEvidence
    from plan_tool.review_persistence import AuditInputSnapshot

    plan_path = tmp_path / "1-advisory.md"
    plan_path.write_text(
        "---\n"
        "title: Advisory plan\n"
        "status: planning\n"
        "priority: medium\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: Foundation\n"
        "    files: [one.py]\n"
        "  - id: 2\n"
        "    title: Concentrated first\n"
        "    files: [two.py]\n"
        "  - id: 3\n"
        "    title: Concentrated second\n"
        "    files: [three.py]\n"
        "  - id: 4\n"
        "    title: Follow-up\n"
        "    files: [four.py]\n"
        "  - id: 5\n"
        "    title: Later work\n"
        "    files: [five.py]\n"
        "---\n\n"
        "# Plan\n",
        encoding="utf-8",
    )
    plan = parse_plan(plan_path)
    snapshot = AuditInputSnapshot.capture(plan_path, tmp_path)
    advisory = AuditShapeAdvisory(
        shape_id="arm-clustering",
        source_plan_fingerprint=snapshot.fingerprint,
        arm_step_ids=(2, 3, 4),
        material_finding_ids=("opaque-a", "opaque-b", "opaque-c", "opaque-d"),
        arm_finding_ids=("opaque-a", "opaque-b", "opaque-c"),
        material_finding_evidence=(
            AuditShapeFindingEvidence("opaque-a", "design-gap", "plan-correctness"),
            AuditShapeFindingEvidence("opaque-b", "risk-gap", "plan-completeness"),
            AuditShapeFindingEvidence("opaque-c", "edge-gap", "plan-completeness"),
            AuditShapeFindingEvidence("opaque-d", "outside-gap", "plan-correctness"),
        ),
        material_finding_count=4,
        arm_finding_count=3,
        committed_step_count=5,
    )
    display = prepare_audit_shape_advisory_display(
        advisory,
        plan=plan,
        plan_path=plan_path,
        repo_root=tmp_path,
    )
    assert display is not None
    return display


# ---------- deferred_kind ----------

def test_deferred_kind_advisory_conceptual() -> None:
    assert deferred_kind(_rec("c", "plan-completeness")) == "advisory-conceptual"


def test_deferred_kind_structural_diagnostic() -> None:
    for src in ("file-check", "path-style", "deps", "files-coherence"):
        assert deferred_kind(_rec("x", src, "high")) == "diagnostic"


def test_deferred_kind_diagnostic_for_test_strategy() -> None:
    # "test-strategy" isn't in APPLY_ELIGIBLE_SOURCES, so the eligibility
    # gate trips first and routes it to a structural diagnostic.
    assert deferred_kind(_rec("x", "test-strategy", "medium")) == "diagnostic"


def test_deferred_kind_diagnostic_for_test_strategy_info() -> None:
    # The eligibility gate precedes the info gate, so an info-severity
    # test-strategy finding is still a diagnostic, not an info deferral.
    assert deferred_kind(_rec("x", "test-strategy", "info")) == "diagnostic"


def test_deferred_kind_info_for_eligible_source() -> None:
    # An eligible source at info severity is an info deferral, not a
    # diagnostic (eligibility gate passes first).
    assert deferred_kind(_rec("i", "claude", "info")) == "info"


def test_deferred_kind_triage_for_complexity_over_impact() -> None:
    rec = _rec("t", "reconcile", "high", impact="low", complexity="high")
    assert deferred_kind(rec) == "triage"


def test_deferred_kind_open_when_eligible_and_no_gate_trips() -> None:
    rec = _rec("o", "body-completeness", "high")
    assert deferred_kind(rec) == "open"


def test_finding_lines_render_stored_legacy_confidence() -> None:
    rec = _rec("legacy", "plan-completeness", confidence=None)

    assert "confidence: unknown" in completeness_report_module._fmt_finding_line(rec)
    assert "confidence: unknown" in completeness_report_module._fmt_pending_line(rec)


# A finding body quotes plan text in fenced blocks, so it spans lines and keeps
# the model's own indentation. Under a bullet every continuation line must sit
# indented, or a column-0 fence ends the list item (BUG_BACKLOG: multi-line bullets).
_FENCED_BODY = (
    "The cited step contradicts the stack.\n"
    "```text\n"
    "## Stack\n"
    "  nested: kept relative\n"
    "\n"
    "## Architecture\n"
    "```\n"
    "Resolve it."
)


def _nonblank_continuation(text: str) -> list[str]:
    return [ln for ln in text.splitlines()[1:] if ln.strip()]


def test_indent_bullet_body_sets_every_continuation_line_under_the_bullet() -> None:
    out = indent_bullet_body(_FENCED_BODY)

    assert out.splitlines()[0] == "The cited step contradicts the stack."
    assert all(ln.startswith("  ") for ln in _nonblank_continuation(out))
    # Relative indentation inside the fence survives; the text is not rewritten.
    assert "    nested: kept relative" in out.splitlines()
    assert "  ## Stack" in out.splitlines()
    assert "" in out.splitlines()[1:]  # the blank line inside the fence stays empty


def test_indent_bullet_body_normalizes_a_model_indented_fence_to_the_same_margin() -> None:
    col0 = "Lead.\n```text\nq\n```"
    indented = "Lead.\n  ```text\n  q\n  ```"

    assert (
        indent_bullet_body(col0)
        == indent_bullet_body(indented)
    )


@pytest.mark.parametrize(
    "body",
    (
        "Lead.\n    ```text\nq\n    ```\nEnd",
        "Lead.\n```text\n    q\n```\n    End",
        "Lead.\n~~~text\nq\n~~~\nEnd",
    ),
)
def test_indent_bullet_body_puts_every_fence_delimiter_at_the_bullet_margin(body: str) -> None:
    # A fence the model indented four or more spaces beside a column-0 line
    # would read as an indented code block (the original defect).
    out = indent_bullet_body(body).splitlines()

    delimiters = [ln for ln in out if ln.lstrip().startswith(("```", "~~~"))]
    assert delimiters
    assert all(ln.startswith("  ") and not ln.startswith("   ") for ln in delimiters)


def test_indent_bullet_body_does_not_strip_the_last_line_of_an_unclosed_fence() -> None:
    # An unclosed fence spans to end-of-text; its last line is content, so
    # relative indentation inside it is kept, not treated as a delimiter.
    out = indent_bullet_body("Lead.\n```text\nq\n    keep four spaces").splitlines()

    assert out[-1] == "      keep four spaces"


def test_indent_bullet_body_leaves_a_one_line_body_unchanged() -> None:
    assert indent_bullet_body("One sentence.") == "One sentence."


@pytest.mark.parametrize(
    "fmt", ("_fmt_finding_line", "_fmt_pending_line"), ids=("finding", "pending")
)
def test_finding_bullet_keeps_a_multiline_body_inside_the_list_item(fmt: str) -> None:
    rec = dataclasses.replace(_rec("fenced", "plan-correctness"), body=_FENCED_BODY)

    line = getattr(completeness_report_module, fmt)(rec)

    assert line.startswith("- ")
    assert all(ln.startswith("  ") for ln in _nonblank_continuation(line))


def test_applied_bullet_does_not_append_text_to_a_closing_fence() -> None:
    # Text after a closing fence turns it into an info string and un-closes the
    # block, so the note and confidence sit on their own continuation line.
    rec = dataclasses.replace(
        _rec("applied", "plan-correctness"), body="Quote:\n```text\nx\n```"
    )
    applied = [AppliedOutcome(rec=rec, verdict="APPLIED", summary="done")]

    md = build_report_md(
        plan_title="T", plan_name="p", iterate_enabled=True,
        stop_reason="converged", iterations=1, applied=applied, deferred=[],
        advisory_conceptual=[], open_findings=[], grouped_report_md="G",
    )

    lines = md.splitlines()
    close = max(i for i, ln in enumerate(lines) if ln.strip() == "```")
    assert lines[close] == "  ```"
    assert lines[close + 1].startswith("  — done [confidence:")


def test_grouped_report_indents_a_multiline_correctness_body() -> None:
    det = _DeterministicReport(None, [], [], [], [], [], [])
    rec = dataclasses.replace(
        _rec("g", "plan-correctness", anchor="g-anchor"), body=_FENCED_BODY
    )

    out = _render_grouped_report(
        SimpleNamespace(title="Demo"), SimpleNamespace(name="demo"), det,
        correctness_recs=[rec], conceptual_recs=[], audit_recs=[],
        iterate_enabled=False,
    )

    lines = out.splitlines()
    head = next(i for i, ln in enumerate(lines) if ln.startswith("- MEDIUM `[g-anchor]`"))
    fence = next(i for i in range(head, len(lines)) if lines[i].strip() == "```text")
    assert lines[fence] == "  ```text"


@pytest.mark.parametrize(
    "bucket",
    ("data_contract_recs", "smell_recs", "self_consistency_recs", "purity_coverage_recs"),
)
def test_grouped_report_indents_a_multiline_body_in_every_deterministic_bucket(
    bucket: str,
) -> None:
    rec = dataclasses.replace(_rec("d", "file-check", anchor="d-anchor"), body=_FENCED_BODY)
    det = dataclasses.replace(_DeterministicReport(None, [], [], [], [], [], []), **{bucket: [rec]})

    out = _render_grouped_report(
        SimpleNamespace(title="Demo"), SimpleNamespace(name="demo"), det,
        correctness_recs=[], conceptual_recs=[], audit_recs=[],
        iterate_enabled=False,
    )

    lines = out.splitlines()
    fence = next(i for i, ln in enumerate(lines) if ln.strip() == "```text")
    assert lines[fence] == "  ```text"


def test_grouped_report_indents_a_multiline_conceptual_body() -> None:
    det = _DeterministicReport(None, [], [], [], [], [], [])
    rec = dataclasses.replace(
        _rec("c", "plan-completeness", anchor="c-anchor"), body=_FENCED_BODY
    )

    out = _render_grouped_report(
        SimpleNamespace(title="Demo"), SimpleNamespace(name="demo"), det,
        correctness_recs=[], conceptual_recs=[rec], audit_recs=[],
        iterate_enabled=False,
    )

    lines = out.splitlines()
    fence = next(i for i, ln in enumerate(lines) if ln.strip() == "```text")
    assert lines[fence] == "  ```text"


# ---------- build_report_md ----------

def test_report_renders_qualified_result_and_routes_unqualified_to_audit() -> None:
    result = {
        "headline": "no-qualified-current-evidence",
        "stage": "not-sampled",
        "coverage": "not-sampled",
        "revision_status": "not-sampled",
        "audit_revision": None,
    }
    report = build_report_md(
        plan_title="Demo",
        plan_name="demo",
        iterate_enabled=False,
        stop_reason=None,
        iterations=0,
        applied=[],
        deferred=[],
        advisory_conceptual=[_rec("gap", "plan-completeness")],
        open_findings=[],
        grouped_report_md="",
        qualified_result=result,
    )

    assert "## Audit result" in report
    assert "`no-qualified-current-evidence`" in report
    next_steps = report.split("## Suggested next steps", 1)[1]
    assert "plan-tool completeness-audit demo" in next_steps
    assert "plan-tool completeness-apply demo" not in next_steps


def test_checkpoint_report_routes_to_a_fresh_audit_not_apply() -> None:
    report = build_report_md(
        plan_title="Demo",
        plan_name="demo",
        iterate_enabled=True,
        stop_reason="pre-apply checkpoint",
        iterations=0,
        applied=[],
        deferred=[],
        advisory_conceptual=[_rec("gap", "plan-completeness")],
        open_findings=[],
        grouped_report_md="",
        qualified_result=None,
        is_pre_apply_checkpoint=True,
    )

    assert "## Recovery evidence" in report
    next_steps = report.split("## Suggested next steps", 1)[1]
    assert "plan-tool completeness-audit demo" in next_steps
    assert "plan-tool completeness-apply demo" not in next_steps


def test_fresh_audit_shape_advisory_renders_evidence_and_override(
    tmp_path: Path,
) -> None:
    display = _fresh_advisory_display(tmp_path)
    report = build_report_md(
        plan_title="Advisory plan",
        plan_name="advisory",
        iterate_enabled=True,
        stop_reason="complete",
        iterations=1,
        applied=[],
        deferred=[],
        advisory_conceptual=[],
        open_findings=[],
        grouped_report_md="",
        audit_shape_advisory_display=display,
    )
    concise = console_summary(
        plan_name="advisory",
        iterate_enabled=True,
        stop_reason="complete",
        iterations=1,
        applied=[],
        deferred=[],
        advisory_conceptual=[],
        open_findings=[],
        report_path=tmp_path / "report.md",
        audit_shape_advisory_display=display,
    )

    assert "arm-clustering" in report
    assert (
        "2 — Concentrated first; 3 — Concentrated second; 4 — Follow-up"
        in report
    )
    assert "3 of 4 material finding(s)" in report
    assert "[design-gap]" in report
    assert "[risk-gap]" in report
    assert "Continuing with the current arm overrides this signal" in report
    assert "arm-clustering" in concise
    assert "continuing with the current arm overrides" in concise


def test_stale_audit_shape_advisory_is_not_rendered(tmp_path: Path) -> None:
    from plan_tool.audit_shapes import AuditShapeAdvisory

    plan_path = tmp_path / "1-stale.md"
    plan_path.write_text(
        "---\ntitle: Stale\nstatus: planning\npriority: low\nsteps:\n"
        "  - id: 1\n    title: Step\n    files: [step.py]\n---\n",
        encoding="utf-8",
    )
    display = prepare_audit_shape_advisory_display(
        AuditShapeAdvisory(
            shape_id="arm-clustering",
            source_plan_fingerprint="does-not-match",
            arm_step_ids=(1,),
            material_finding_ids=("one",),
            arm_finding_ids=("one",),
            material_finding_evidence=(),
            material_finding_count=1,
            arm_finding_count=1,
            committed_step_count=1,
        ),
        plan=parse_plan(plan_path),
        plan_path=plan_path,
        repo_root=tmp_path,
    )
    report = build_report_md(
        plan_title="Stale",
        plan_name="stale",
        iterate_enabled=False,
        stop_reason=None,
        iterations=0,
        applied=[],
        deferred=[],
        advisory_conceptual=[],
        open_findings=[],
        grouped_report_md="",
        audit_shape_advisory_display=display,
    )
    assert display is None
    assert "arm-clustering" not in report


def test_structurally_invalid_advisory_is_not_rendered(tmp_path: Path) -> None:
    from plan_tool.audit_shapes import AuditShapeAdvisory, AuditShapeFindingEvidence
    from plan_tool.review_persistence import AuditInputSnapshot

    plan_path = tmp_path / "1-invalid-advisory.md"
    plan_path.write_text(
        "---\n"
        "title: Invalid Advisory\nstatus: planning\npriority: low\nsteps:\n"
        "  - id: 1\n    title: First\n"
        "  - id: 2\n    title: Second\n"
        "  - id: 3\n    title: Third\n"
        "  - id: 4\n    title: Fourth\n"
        "---\n",
        encoding="utf-8",
    )
    advisory = AuditShapeAdvisory(
        shape_id="arm-clustering",
        source_plan_fingerprint=AuditInputSnapshot.capture(
            plan_path, tmp_path
        ).fingerprint,
        arm_step_ids=(1, 3),
        material_finding_ids=("one", "two", "three", "four"),
        arm_finding_ids=("one", "two", "three"),
        material_finding_evidence=(
            AuditShapeFindingEvidence("one", None, "plan-correctness"),
            AuditShapeFindingEvidence("two", None, "plan-completeness"),
            AuditShapeFindingEvidence("three", None, "plan-completeness"),
            AuditShapeFindingEvidence("four", None, "plan-correctness"),
        ),
        material_finding_count=4,
        arm_finding_count=3,
        committed_step_count=4,
    )

    assert prepare_audit_shape_advisory_display(
        advisory,
        plan=parse_plan(plan_path),
        plan_path=plan_path,
        repo_root=tmp_path,
    ) is None


def test_audit_shape_advisory_display_uses_registry_emitter_eligibility(
    tmp_path: Path, monkeypatch
) -> None:
    from plan_tool.audit_shapes import AuditShapeAdvisory, AuditShapeFindingEvidence
    from plan_tool.review_persistence import AuditInputSnapshot

    plan_path = tmp_path / "1-advisory.md"
    plan_path.write_text(
        "---\n"
        "title: Advisory plan\n"
        "status: planning\n"
        "priority: medium\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: Foundation\n"
        "    files: [one.py]\n"
        "---\n\n"
        "# Plan\n",
        encoding="utf-8",
    )
    plan = parse_plan(plan_path)
    advisory = AuditShapeAdvisory(
        shape_id="arm-clustering",
        source_plan_fingerprint=AuditInputSnapshot.capture(
            plan_path, tmp_path
        ).fingerprint,
        arm_step_ids=(1,),
        material_finding_ids=("opaque-a",),
        arm_finding_ids=("opaque-a",),
        material_finding_evidence=(
            AuditShapeFindingEvidence(
                "opaque-a", "design-gap", "plan-correctness"
            ),
        ),
        material_finding_count=1,
        arm_finding_count=1,
        committed_step_count=1,
    )
    monkeypatch.setattr(
        completeness_report_module,
        "is_advisory_emitter_eligible",
        lambda _shape_id: False,
    )

    assert prepare_audit_shape_advisory_display(
        advisory,
        plan=plan,
        plan_path=plan_path,
        repo_root=tmp_path,
    ) is None


def test_audit_shape_advisory_renders_typed_evidence_without_finding_prose(
    tmp_path: Path,
) -> None:
    display = _fresh_advisory_display(tmp_path)
    report = build_report_md(
        plan_title="Advisory plan",
        plan_name="advisory",
        iterate_enabled=False,
        stop_reason=None,
        iterations=0,
        applied=[],
        deferred=[],
        advisory_conceptual=[],
        open_findings=[],
        grouped_report_md="",
        audit_shape_advisory_display=display,
    )
    assert "Correctness anchors" in report
    assert "Completeness anchors" in report
    assert "opaque-a" not in report
    assert "opaque-b" not in report
    assert "body opaque" not in report

def test_report_explains_why_conceptual_not_addressed() -> None:
    """The headline requirement: the report states why conceptual-
    completeness gaps weren't auto-applied."""
    advisory = [_rec("cc", "plan-completeness", "medium")]
    md = build_report_md(
        plan_title="T", plan_name="p", iterate_enabled=True,
        stop_reason="marginal", iterations=1, applied=[], deferred=[],
        advisory_conceptual=advisory, open_findings=[],
        grouped_report_md="GROUPED",
    )
    assert "Conceptual completeness — reported, not auto-applied" in md
    assert WHY["advisory-conceptual"] in md
    assert "body cc" in md   # the finding's full body is listed (not the clipped title)
    assert "GROUPED" in md   # grouped report embedded


@pytest.mark.parametrize("iterate_enabled", [False, True])
def test_embedded_correctness_appears_once_and_standalone_keeps_findings(
    iterate_enabled,
) -> None:
    rec = _rec("unique-correctness", "plan-correctness", "high")
    det = _DeterministicReport(None, [], [], [], [], [], [])
    options = dict(
        correctness_recs=[rec], conceptual_recs=[], audit_recs=[rec],
        iterate_enabled=iterate_enabled,
    )
    plan = SimpleNamespace(title="Demo")
    args = SimpleNamespace(name="demo")
    standalone = _render_grouped_report(plan, args, det, **options)
    embedded = _render_grouped_report(plan, args, det, **options, embedded=True)
    md = build_report_md(
        plan_title="Demo", plan_name="demo", iterate_enabled=iterate_enabled,
        stop_reason="converged", iterations=0, applied=[], deferred=[],
        advisory_conceptual=[], open_findings=[], correctness=[rec],
        grouped_report_md=embedded,
    )
    assert standalone.count(rec.body) == 1
    assert rec.body not in embedded
    assert md.count(rec.body) == 1
    assert "see the dedicated section above" in embedded


def test_report_correctness_not_double_counted_as_open() -> None:
    """#85: correctness gaps are surfaced via the ``correctness`` bucket only.
    The caller passes open_findings=[] for them, so the disposition summary
    must NOT also list them as 'Open (not reached)' — that double-counted the
    same set and implied fruitless re-audit work."""
    correctness = [_rec("pc1", "plan-correctness", "high"),
                   _rec("pc2", "plan-correctness", "critical")]
    md = build_report_md(
        plan_title="T", plan_name="p", iterate_enabled=True,
        stop_reason="converged", iterations=0, applied=[], deferred=[],
        advisory_conceptual=[], open_findings=[],
        grouped_report_md="G", correctness=correctness,
    )
    # Correctness counted once, in its own bucket.
    assert "**Conceptual correctness:** 2" in md
    # NOT also as open/not-reached.
    assert "Open (not reached)" not in md
    # And the next-steps point at a session-directed edit, not a re-audit.
    assert "session-directed edit" in md


def test_report_renders_smells_section_when_present() -> None:
    smells = [_rec("sm", "feature-ref", "info")]
    md = build_report_md(
        plan_title="T", plan_name="p", iterate_enabled=True,
        stop_reason="marginal", iterations=1, applied=[], deferred=[],
        advisory_conceptual=[], open_findings=[],
        grouped_report_md="G", smells=smells,
    )
    assert "## Smells (advisory)" in md
    assert "body sm" in md  # the rec's full body is rendered


def test_report_omits_smells_section_when_none() -> None:
    md = build_report_md(
        plan_title="T", plan_name="p", iterate_enabled=True,
        stop_reason="marginal", iterations=1, applied=[], deferred=[],
        advisory_conceptual=[], open_findings=[],
        grouped_report_md="G",
    )
    assert "## Smells (advisory)" not in md


def test_report_renders_granularity_merge_in_smells_section() -> None:
    # A cross-step granularity-merge rec rides the existing ``smells`` param
    # into the ## Smells (advisory) section — no new build_report_md param.
    smells = [_rec("gm", "granularity-merge", "info")]
    md = build_report_md(
        plan_title="T", plan_name="p", iterate_enabled=True,
        stop_reason="marginal", iterations=1, applied=[], deferred=[],
        advisory_conceptual=[], open_findings=[],
        grouped_report_md="G", smells=smells,
    )
    assert "## Smells (advisory)" in md
    assert "body gm" in md  # the merge rec's full body renders


def test_report_renders_granularity_split_in_smells_section() -> None:
    smells = [_rec("gs", "granularity-split", "info")]
    md = build_report_md(
        plan_title="T", plan_name="p", iterate_enabled=True,
        stop_reason="marginal", iterations=1, applied=[], deferred=[],
        advisory_conceptual=[], open_findings=[],
        grouped_report_md="G", smells=smells,
    )
    assert "## Smells (advisory)" in md
    assert "body gs" in md


def test_report_smells_blurb_names_granularity() -> None:
    # The broadened descriptive sentence names step-granularity advice; the
    # heading text itself is unchanged (other tests key on it).
    smells = [_rec("gm", "granularity-merge", "info")]
    md = build_report_md(
        plan_title="T", plan_name="p", iterate_enabled=True,
        stop_reason="marginal", iterations=1, applied=[], deferred=[],
        advisory_conceptual=[], open_findings=[],
        grouped_report_md="G", smells=smells,
    )
    assert "## Smells (advisory)" in md
    assert "granularity" in md


def test_report_code_drift_with_critical_adds_reconcile_to_next_steps() -> None:
    """build_report_md threads code_drifted into the Suggested next steps
    section: drift + a critical finding → a reconcile-plan bullet."""
    md = build_report_md(
        plan_title="T", plan_name="p", iterate_enabled=True,
        stop_reason="marginal", iterations=1, applied=[], deferred=[],
        advisory_conceptual=[], open_findings=[_rec("o", "plan-correctness", "critical")],
        grouped_report_md="G", correctness=[_rec("o", "plan-correctness", "critical")],
        code_drifted=True,
    )
    assert "plan-tool reconcile-plan p" in md


def test_report_code_drift_only_medium_omits_reconcile() -> None:
    md = build_report_md(
        plan_title="T", plan_name="p", iterate_enabled=True,
        stop_reason="marginal", iterations=1, applied=[], deferred=[],
        advisory_conceptual=[_rec("cc", "plan-completeness", "medium")], open_findings=[],
        grouped_report_md="G", code_drifted=True,
    )
    assert "reconcile-plan" not in md


def test_report_groups_deferred_by_reason_with_rationale() -> None:
    deferred = [
        _rec("fc", "file-check", "high"),
        _rec("tr", "reconcile", "high", impact="low", complexity="high"),
    ]
    md = build_report_md(
        plan_title="T", plan_name="p", iterate_enabled=True,
        stop_reason="marginal", iterations=2, applied=[], deferred=deferred,
        advisory_conceptual=[], open_findings=[],
        grouped_report_md="G",
    )
    assert "structural diagnostics" in md
    assert WHY["diagnostic"] in md
    assert WHY["triage"] in md
    assert "body fc" in md and "body tr" in md


def test_report_renders_test_strategy_under_diagnostics() -> None:
    # A test-strategy deferred finding renders under the structural-
    # diagnostics group with WHY["diagnostic"] — no completeness_report edit.
    deferred = [_rec("ts", "test-strategy", "medium")]
    md = build_report_md(
        plan_title="T", plan_name="p", iterate_enabled=True,
        stop_reason="marginal", iterations=1, applied=[], deferred=deferred,
        advisory_conceptual=[], open_findings=[],
        grouped_report_md="G",
    )
    assert "structural diagnostics" in md
    assert WHY["diagnostic"] in md
    assert "body ts" in md


def test_report_lists_applied_with_verdicts() -> None:
    applied = [
        AppliedOutcome(
            rec=_rec("a", "plan-correctness", "high", confidence=None),
            verdict="APPLIED", summary="did the thing",
        ),
        AppliedOutcome(
            rec=_rec("b", "body-completeness", "medium"),
            verdict="NOT-APPLICABLE", summary="",
        ),
    ]
    md = build_report_md(
        plan_title="T", plan_name="p", iterate_enabled=True,
        stop_reason="converged", iterations=1, applied=applied, deferred=[],
        advisory_conceptual=[], open_findings=[], grouped_report_md="G",
    )
    assert "[APPLIED] body a — did the thing [confidence: unknown]" in md
    assert "[NOT-APPLICABLE] body b" in md
    assert "1 APPLIED, 1 other verdict" in md


def test_report_header_audit_only_mode() -> None:
    md = build_report_md(
        plan_title="T", plan_name="p", iterate_enabled=False,
        stop_reason=None, iterations=0, applied=[], deferred=[],
        advisory_conceptual=[], open_findings=[], grouped_report_md="G",
    )
    assert "mode: audit-only" in md
    assert "loop stopped" not in md


def test_concept_coverage_uses_specific_disposition_and_remedy() -> None:
    rec = _rec("concept-id", "concept-coverage")
    assert deferred_kind(rec) == "concept-link"
    md = build_report_md(
        plan_title="T", plan_name="p", iterate_enabled=False,
        stop_reason=None, iterations=0, applied=[], deferred=[rec],
        advisory_conceptual=[], open_findings=[], grouped_report_md="G",
    )
    assert "**Deferred:** 1 (1 missing-concept-link, 0 structural-diagnostic" in md
    assert "## Missing explicit concept links — assign or defer" in md
    assert "Assign each listed concept ID to a committed step" in md
    assert "record a reviewed structured deferral" in md
    assert "body concept-id" in md


def test_report_correctness_count_renders_even_at_zero() -> None:
    """The conceptual-correctness layer's count is always visible when
    tracked — including 0 — so a reader can't mistake 'layer wasn't
    sampled' for 'no correctness issues' (report defect #3)."""
    md = build_report_md(
        plan_title="T", plan_name="p", iterate_enabled=False,
        stop_reason=None, iterations=0, applied=[], deferred=[],
        advisory_conceptual=[], open_findings=[], grouped_report_md="G",
        correctness=[],
    )
    assert "**Conceptual correctness:** 0" in md


def test_report_correctness_count_omitted_when_untracked() -> None:
    """Callers that don't track the correctness set (correctness=None,
    the default) keep the legacy summary shape."""
    md = build_report_md(
        plan_title="T", plan_name="p", iterate_enabled=False,
        stop_reason=None, iterations=0, applied=[], deferred=[],
        advisory_conceptual=[], open_findings=[], grouped_report_md="G",
    )
    assert "Conceptual correctness" not in md


def test_report_correctness_count_nonzero() -> None:
    md = build_report_md(
        plan_title="T", plan_name="p", iterate_enabled=False,
        stop_reason=None, iterations=0, applied=[], deferred=[],
        advisory_conceptual=[], open_findings=[], grouped_report_md="G",
        correctness=[_rec("pc", "plan-correctness", "high")],
    )
    assert "**Conceptual correctness:** 1" in md


def test_report_renders_dedicated_correctness_section() -> None:
    """Conceptual-correctness gaps get a first-class section, placed ahead
    of the completeness section, with the auto-apply remediation commands."""
    correctness = [
        _rec("pc", "plan-correctness", "critical", anchor="bad-concept")
    ]
    md = build_report_md(
        plan_title="T", plan_name="p", iterate_enabled=True,
        stop_reason="halted", iterations=0, applied=[], deferred=[],
        advisory_conceptual=[_rec("cc", "plan-completeness", "medium")],
        open_findings=correctness, grouped_report_md="G",
        correctness=correctness,
    )
    assert "## Conceptual correctness — fix these first" in md
    assert "body pc" in md
    assert "plan-tool completeness-audit p --iterate" in md
    # Correctness reads ahead of the completeness section.
    assert md.index("## Conceptual correctness") < md.index(
        "Conceptual completeness — reported"
    )


def test_correctness_intro_advertises_no_apply_verb() -> None:
    """CORRECTNESS_INTRO must not advertise a walk that refuses plan-correctness.

    #367 makes this stronger than it was: the intro now names *no* apply verb
    at all, routing correctness gaps to a session-directed edit. The
    ``reconcile-plan-walk`` assertion below is kept as the original regression
    guard (BUG closed 2026-08-03) — that walk still refuses plan-correctness,
    so it must never reappear here.

    ``reconcile-plan-walk`` has no ``extra_apply_sources``, so
    ``should_apply_as_finding`` returns False for ``plan-correctness`` —
    naming it as an apply route is the defect (BUG closed 2026-08-03).
    """
    from plan_tool.completeness_report import CORRECTNESS_INTRO
    from plan_tool.review import Recommendation
    from plan_tool.review_walk import should_apply_as_finding

    intro = CORRECTNESS_INTRO.format(plan_name="demo")
    assert "session-directed edit" in intro
    assert "completeness-apply" not in intro
    assert "reconcile-plan-walk" not in intro
    # Pin the walk contract this prose must stay aligned with.
    refuse = Recommendation(
        id="x",
        source="plan-correctness",
        severity="high",
        step_id=None,
        title="t",
        body="b",
    )
    assert not should_apply_as_finding(refuse)


def test_report_omits_correctness_section_when_empty() -> None:
    md = build_report_md(
        plan_title="T", plan_name="p", iterate_enabled=True,
        stop_reason="converged", iterations=1, applied=[], deferred=[],
        advisory_conceptual=[], open_findings=[], grouped_report_md="G",
        correctness=[],
    )
    assert "## Conceptual correctness — fix these first" not in md


def test_report_deferred_correctness_not_double_listed() -> None:
    """A triaged (low-payoff) correctness finding renders only in the
    dedicated correctness section, not also under a deferred bucket."""
    rec = _rec(
        "pc", "plan-correctness", "high",
        impact="low", complexity="high", anchor="slow",
    )
    assert deferred_kind(rec) == "triage"
    md = build_report_md(
        plan_title="T", plan_name="p", iterate_enabled=True,
        stop_reason="halted", iterations=0, applied=[], deferred=[rec],
        advisory_conceptual=[], open_findings=[], grouped_report_md="G",
        correctness=[rec],
    )
    assert md.count("body pc") == 1
    assert "## Conceptual correctness — fix these first" in md
    assert WHY["triage"] not in md  # not also under the low-payoff bucket


# ---------- console_summary ----------

def test_grouped_report_renders_resumed_audit_provenance_only_for_positive_resume() -> None:
    """A positive sampler result is human-only provenance, not evidence."""
    det = _DeterministicReport(None, [], [], [], [], [], [])
    common = dict(
        correctness_recs=[],
        conceptual_recs=[],
        audit_recs=[],
        iterate_enabled=False,
    )
    resumed = _render_grouped_report(
        SimpleNamespace(title="Demo"), SimpleNamespace(name="demo"), det,
        resumed_from_sampler_checkpoint=True,
        **common,
    )
    fresh = _render_grouped_report(
        SimpleNamespace(title="Demo"), SimpleNamespace(name="demo"), det,
        resumed_from_sampler_checkpoint=False,
        **common,
    )

    assert "### Audit provenance" in resumed
    assert "resumed from a durable sampler pass boundary" in resumed
    assert "Audit provenance" not in fresh


def test_console_summary_concise_and_flags_advisory() -> None:
    advisory = [_rec("cc", "plan-completeness")]
    deferred = [_rec("fc", "file-check", "high")]
    out = console_summary(
        plan_name="p", iterate_enabled=True, stop_reason="marginal",
        iterations=1, applied=[], deferred=deferred,
        advisory_conceptual=advisory, open_findings=[],
        report_path=Path("/tmp/r.md"),
        verdict=blocking_verdict_from_gate(["cc"]),
    )
    assert "loop stopped: marginal" in out
    # #85/#367: completeness gaps are closed by a session-directed edit —
    # not by the audit, and not by any tool command.
    assert "session-directed edit" in out
    assert "human judgment" in out
    assert "structural-diagnostic" in out
    assert "/tmp/r.md" in out
    # Concise: no per-item finding ids dumped.
    assert "title fc" not in out


def test_console_summary_renders_resumed_audit_provenance() -> None:
    """Keep sampler recovery visible without changing the result line."""
    common = dict(
        plan_name="p",
        iterate_enabled=True,
        stop_reason="marginal",
        iterations=1,
        applied=[],
        deferred=[],
        advisory_conceptual=[],
        open_findings=[],
        report_path=Path("/tmp/r.md"),
    )
    resumed = console_summary(
        resumed_from_sampler_checkpoint=True,
        **common,
    )
    fresh = console_summary(**common)

    assert "provenance resumed from a durable sampler pass boundary" in resumed
    assert "provenance resumed from a durable sampler pass boundary" not in fresh


def test_console_summary_flags_correctness_first() -> None:
    correctness = [_rec("pc", "plan-correctness", "critical")]
    out = console_summary(
        plan_name="p", iterate_enabled=True, stop_reason="halted",
        iterations=0, applied=[], deferred=[], advisory_conceptual=[],
        open_findings=correctness, report_path=Path("/tmp/r.md"),
        correctness=correctness, verdict=blocking_verdict_from_gate(["pc"]),
    )
    assert "correctness" in out
    assert "fix these first" in out
    # The standalone "open" line is suppressed when correctness covers it.
    assert "(not reached)" not in out


def test_console_summary_bare_plan_completeness_line_omits_the_apply_verb() -> None:
    advisory = [_rec("cc", "plan-completeness")]
    out = console_summary(
        plan_name="p", iterate_enabled=True, stop_reason="marginal",
        iterations=1, applied=[], deferred=[],
        advisory_conceptual=advisory, open_findings=[],
        report_path=Path("/tmp/r.md"),
        bundle_status=SimpleNamespace(is_bare=True),
    )
    assert "informational until a complete detail bundle exists" in out
    assert "completeness-apply" not in out


def test_console_summary_bare_plan_flags_correctness_for_a_session_edit() -> None:
    """#367: a bare plan still surfaces correctness as the thing to fix first,
    but routes it to a session-directed edit rather than naming an apply verb."""
    correctness = [_rec("pc", "plan-correctness", "critical")]
    out = console_summary(
        plan_name="p", iterate_enabled=True, stop_reason="halted",
        iterations=0, applied=[], deferred=[], advisory_conceptual=[],
        open_findings=[], report_path=Path("/tmp/r.md"),
        correctness=correctness,
        bundle_status=SimpleNamespace(is_bare=True),
        verdict=blocking_verdict_from_gate(["pc"]),
    )
    assert "session-directed edit" in out
    assert "fix these first" in out


def test_console_summary_without_bundle_status_is_unchanged() -> None:
    """bundle_status=None keeps legacy output for every combination."""
    correctness = [_rec("pc", "plan-correctness", "high")]
    advisory = [_rec("cc", "plan-completeness")]
    for correctness_kw, advisory_kw in (
        (correctness, []),
        ([], advisory),
        (correctness, advisory),
    ):
        out = console_summary(
            plan_name="p", iterate_enabled=True, stop_reason="marginal",
            iterations=1, applied=[], deferred=[],
            advisory_conceptual=advisory_kw, open_findings=[],
            report_path=Path("/tmp/r.md"),
            correctness=correctness_kw,
            verdict=blocking_verdict_from_gate(["pc", "cc"]),
        )
        if advisory_kw:
            assert "close through a session-directed edit" in out
        if correctness_kw:
            assert "session-directed edit" in out


# ---------- suggested_next_steps ----------

def _verdict_blocking_every_listed_gap(kw):
    """A set verdict whose ids are exactly the listed conceptual gaps (an empty
    set when none are listed); pass ``verdict=`` to pin advisory behavior."""
    listed = [*kw.get("correctness", ()), *kw.get("advisory_conceptual", ())]
    return blocking_verdict_from_gate([r.id for r in listed])


def _steps(**kw):
    base = dict(
        plan_name="p", iterate_enabled=True, applied=[], deferred=[],
        advisory_conceptual=[], open_findings=[],
    )
    base.update(kw)
    base.setdefault("verdict", _verdict_blocking_every_listed_gap(base))
    return suggested_next_steps(**base)


def test_next_steps_blocked_points_at_new_step_workflow() -> None:
    """A BLOCKED apply verdict is the 'needs a new step' case: the bullet
    must point at the on-demand `split` command (which authors + re-audits
    for you) and, for a wholly new step, the add → detail fallback."""
    applied = [
        AppliedOutcome(
            rec=_rec("a", "plan-correctness", "medium"),
            verdict="BLOCKED", summary="requires a new detail file",
        ),
    ]
    steps = _steps(applied=applied)
    assert any("BLOCKED" in s for s in steps)
    head = steps[0]  # headline case sorts first
    assert "plan-tool split p --step" in head
    assert "new step" in head
    assert "plan-tool detail p" in head


def test_next_steps_blocked_names_specific_step_when_plan_given() -> None:
    """With a plan in hand, the split suggestion is prescriptive: it
    targets the exact step (number + title) the blocked finding sits on,
    not a placeholder `--step N`."""
    plan = Plan(
        title="T",
        status="planning",
        priority="medium",
        steps=[
            Step(id=1, title="Set up scaffolding"),
            Step(id=4, title="Wire the audit gate into run pre-flight"),
        ],
    )
    applied = [
        AppliedOutcome(
            rec=_rec("a", "plan-correctness", "medium", step_id=4),
            verdict="BLOCKED", summary="needs a new step",
        ),
    ]
    head = _steps(applied=applied, plan=plan)[0]
    assert "plan-tool split p --step 4" in head
    assert '(step 4: "Wire the audit gate into run pre-flight")' in head
    # No placeholder left to fill for the step itself.
    assert "--step N" not in head


def test_next_steps_blocked_falls_back_to_placeholder_without_step() -> None:
    """A plan-level BLOCKED finding (no step_id) keeps the generic
    `--step N` form — there's no specific step to name."""
    applied = [
        AppliedOutcome(
            rec=_rec("a", "plan-correctness", "medium"),
            verdict="BLOCKED", summary="plan-level gap",
        ),
    ]
    head = _steps(applied=applied)[0]
    assert "plan-tool split p --step N" in head


def test_next_steps_blocked_leads_with_detail_on_bare_plan() -> None:
    applied = [
        AppliedOutcome(
            rec=_rec("a", "plan-correctness", "medium"),
            verdict="BLOCKED", summary="requires a new detail file",
        ),
    ]
    head = _steps(
        applied=applied,
        bundle_status=SimpleNamespace(is_bare=True),
    )[0]
    detail_idx = head.index("plan-tool detail p")
    split_idx = head.index("plan-tool split p")
    assert detail_idx < split_idx


def test_next_steps_blocked_headline_names_the_missing_detail_file_on_bare_plan() -> None:
    applied = [
        AppliedOutcome(
            rec=_rec("a", "plan-correctness", "medium"),
            verdict="BLOCKED", summary="requires a new detail file",
        ),
    ]
    head = _steps(
        applied=applied,
        bundle_status=SimpleNamespace(is_bare=True),
    )[0]
    assert "can't create files" in head
    assert "detail file doesn't exist yet" in head
    assert "can't add or restructure steps" not in head


def test_next_steps_blocked_keeps_split_as_secondary_on_bare_plan() -> None:
    applied = [
        AppliedOutcome(
            rec=_rec("a", "plan-correctness", "medium"),
            verdict="BLOCKED", summary="requires a new detail file",
        ),
    ]
    head = _steps(
        applied=applied,
        bundle_status=SimpleNamespace(is_bare=True),
    )[0]
    assert "over-packed" in head
    assert "plan-tool split p --step" in head


def test_next_steps_blocked_bare_plan_still_names_the_specific_step_for_split() -> None:
    plan = Plan(
        title="T",
        status="planning",
        priority="medium",
        steps=[
            Step(id=1, title="Set up scaffolding"),
            Step(id=4, title="Wire the audit gate into run pre-flight"),
        ],
    )
    applied = [
        AppliedOutcome(
            rec=_rec("a", "plan-correctness", "medium", step_id=4),
            verdict="BLOCKED", summary="needs a new step",
        ),
    ]
    head = _steps(
        applied=applied,
        plan=plan,
        bundle_status=SimpleNamespace(is_bare=True),
    )[0]
    assert "plan-tool split p --step 4" in head
    assert '(step 4: "Wire the audit gate into run pre-flight")' in head


def test_next_steps_blocked_unchanged_on_detailed_plan() -> None:
    applied = [
        AppliedOutcome(
            rec=_rec("a", "plan-correctness", "medium"),
            verdict="BLOCKED", summary="requires a new detail file",
        ),
    ]
    none_block = _steps(applied=applied)[0]
    detailed_block = _steps(
        applied=applied,
        bundle_status=SimpleNamespace(is_bare=False),
    )[0]
    assert detailed_block == none_block
    assert detailed_block.index("plan-tool split p") < detailed_block.index(
        "plan-tool detail p"
    )


def test_next_steps_blocked_from_a_deterministic_apply_leads_with_detail_on_bare_plan() -> None:
    applied = [
        AppliedOutcome(
            rec=_rec("a", "files-coherence", "info"),
            verdict="BLOCKED", summary="requires a new detail file",
        ),
    ]
    head = _steps(
        applied=applied,
        bundle_status=SimpleNamespace(is_bare=True),
    )[0]
    detail_idx = head.index("plan-tool detail p")
    split_idx = head.index("plan-tool split p")
    assert detail_idx < split_idx


def test_next_steps_conditional_on_each_disposition() -> None:
    steps = _steps(
        advisory_conceptual=[_rec("cc", "plan-completeness")],
        deferred=[_rec("fc", "file-check", "high")],
        open_findings=[_rec("o", "plan-correctness", "high")],
    )
    joined = "\n".join(steps)
    assert "session-directed edit" in joined         # advisory-conceptual
    assert "structural diagnostic" in joined         # diagnostic deferral
    assert "--max-iterations" in joined              # open / not reached


def test_next_steps_correctness_points_at_a_session_edit_not_reaudit() -> None:
    """#85/#367: correctness gaps are unapplied and are closed by a
    session-directed edit. The prose next-steps must route them there and must
    NOT tell the operator to re-run --iterate (which never applies
    correctness). Under #85 the caller passes open_findings=[] for the
    correctness set."""
    steps = _steps(
        correctness=[_rec("pc", "plan-correctness", "high")],
        open_findings=[],
    )
    joined = "\n".join(steps)
    assert "session-directed edit" in joined
    assert "conceptual-correctness gap(s)" in joined
    # No misleading "re-run --iterate to reach them" line.
    assert "--max-iterations" not in joined
    assert "weren't reached" not in joined


def test_next_steps_correctness_and_completeness_emit_one_conceptual_line() -> None:
    """When both conceptual sources are present, a single session-directed-edit
    line (naming correctness first) covers both — not two bullets."""
    steps = _steps(
        correctness=[_rec("pc", "plan-correctness", "high")],
        advisory_conceptual=[_rec("cc", "plan-completeness")],
        open_findings=[],
    )
    edit_lines = [s for s in steps if s.startswith("Close ")]
    assert len(edit_lines) == 1
    assert "conceptual-correctness gap(s)" in edit_lines[0]


def test_next_steps_files_coherence_only_omits_detail() -> None:
    """When the only open diagnostics are files-coherence drift (every
    step's detail file already on disk), the remedy points at a `files:`
    edit and must NOT suggest `plan-tool detail` — running it would
    no-op, which was the original confusion."""
    steps = _steps(
        deferred=[
            _rec("fc1", "files-coherence", "info",
                 suggested_action="add path to files:"),
            _rec("fc2", "files-coherence", "nit",
                 suggested_action="drop from files:"),
        ],
    )
    joined = "\n".join(steps)
    assert "files-coherence drift" in joined
    assert "plan-tool detail" not in joined


def test_next_steps_detail_coverage_suggests_detail() -> None:
    """A missing/unreferenced detail file (source detail-coverage) names
    `plan-tool detail` — but the default (scoped) run, which reattaches /
    authors only the affected steps, NOT a blanket `--force` that re-authors
    every step. `--force` appears solely as the deliberate-overwrite escape
    hatch, never as the recommended command."""
    steps = _steps(
        deferred=[
            _rec("dc", "detail-coverage", "high",
                 suggested_action="plan-tool detail p --step 2 --force"),
        ],
    )
    joined = "\n".join(steps)
    assert "plan-tool detail p" in joined
    # The footgun: the old aggregate recommended a bare `--force`, which
    # re-authors every step's detail from scratch. It must not return.
    assert "plan-tool detail p --force" not in joined


def test_next_steps_bare_plan_suppresses_detail_authoring_actions() -> None:
    """Bare/partial-detail completeness is structural-only: detail-level
    diagnostics can still be listed in the report, but only the clean
    stage-transition fallback may propose authoring detail."""
    steps = _steps(
        deferred=[
            _rec("dc", "detail-coverage", "high"),
            _rec("fc", "files-coherence", "info", suggested_action="add path"),
        ],
        bundle_status=SimpleNamespace(is_bare=True),
    )
    joined = "\n".join(steps)
    assert "plan-tool detail p" in joined
    assert "plan-tool run p" not in joined
    assert "files-coherence" not in joined
    assert "No structural gaps left to close" in joined
    assert "Detail-level/conceptual findings above are informational" in joined


def test_next_steps_bare_plan_suppresses_conceptual_apply_action() -> None:
    steps = _steps(
        advisory_conceptual=[_rec("cc", "plan-completeness")],
        bundle_status=SimpleNamespace(is_bare=True),
        verdict=blocking_verdict_from_gate([]),
    )
    joined = "\n".join(steps)
    assert "completeness-apply" not in joined
    assert "plan-tool detail p" in joined
    assert "plan-tool run p" not in joined
    assert "informational until a complete detail bundle exists" in joined


def test_next_steps_bare_plan_keeps_the_correctness_route() -> None:
    """A bare-plan audit still routes correctness gaps somewhere actionable —
    a session-directed edit — rather than reporting nothing to do."""
    steps = _steps(
        correctness=[_rec("pc", "plan-correctness", "high")],
        bundle_status=SimpleNamespace(is_bare=True),
    )
    joined = "\n".join(steps)
    assert "session-directed edit" in joined
    assert "No gaps left to close" not in joined


def test_next_steps_bare_plan_correctness_bullet_omits_completeness_promise() -> None:
    steps = _steps(
        correctness=[_rec("pc", "plan-correctness", "high")],
        advisory_conceptual=[_rec("cc", "plan-completeness")],
        bundle_status=SimpleNamespace(is_bare=True),
        verdict=blocking_verdict_from_gate(["pc"]),
    )
    edit_line = next(s for s in steps if s.startswith("Close "))
    assert "then the completeness gaps" not in edit_line
    assert "informational until a complete detail bundle exists" in edit_line


def test_next_steps_bare_plan_calls_no_completeness_gap_informational_when_none_is_advisory() -> None:
    """With no non-blocking completeness gap listed, the correctness bullet
    must not claim any stays informational (amendment 8)."""
    steps = _steps(
        correctness=[_rec("pc", "plan-correctness", "high")],
        bundle_status=SimpleNamespace(is_bare=True),
    )
    edit_line = next(s for s in steps if s.startswith("Close "))
    assert "informational" not in edit_line


def test_next_steps_bare_plan_both_axes_names_only_correctness() -> None:
    steps = _steps(
        correctness=[_rec("pc", "plan-correctness", "high")],
        advisory_conceptual=[_rec("cc", "plan-completeness")],
        bundle_status=SimpleNamespace(is_bare=True),
    )
    edit_lines = [s for s in steps if s.startswith("Close ")]
    assert len(edit_lines) == 1
    assert "conceptual-correctness gap(s)" in edit_lines[0]
    assert "then the completeness gaps" not in edit_lines[0]


def test_next_steps_mixed_diagnostics_render_subbullets() -> None:
    """Distinct diagnostic sources produce one remedy line each, rendered
    as indented sub-bullets under a single headline."""
    from plan_tool.completeness_report import diagnostic_remedies

    diags = [
        _rec("fc", "files-coherence", "info", suggested_action="x"),
        _rec("dc", "detail-coverage", "high", suggested_action="y"),
        _rec("ls", "lessons-coverage", "high", suggested_action="z"),
    ]
    remedies = diagnostic_remedies(diags, "p")
    assert len(remedies) == 3
    steps = _steps(deferred=diags)
    headline = next(s for s in steps if "structural diagnostic" in s)
    assert headline.count("•") == 3


def test_next_steps_falls_back_to_run_when_clean() -> None:
    steps = _steps()
    assert len(steps) == 1
    assert "plan-tool run p" in steps[0]


def test_next_steps_falls_back_to_detail_when_bundle_is_bare() -> None:
    steps = _steps(bundle_status=SimpleNamespace(is_bare=True))
    assert len(steps) == 1
    assert "plan-tool detail p" in steps[0]
    assert "plan-tool run p" not in steps[0]


def test_report_renders_next_steps_last_in_summary() -> None:
    """The disposition next-steps section lands as the last part of the
    curated summary — above the embedded grouped report, so it isn't lost
    in the detail."""
    applied = [
        AppliedOutcome(
            rec=_rec("a", "plan-correctness", "medium"),
            verdict="BLOCKED", summary="needs new file",
        ),
    ]
    md = build_report_md(
        plan_title="T", plan_name="p", iterate_enabled=True,
        stop_reason="converged", iterations=1, applied=applied, deferred=[],
        advisory_conceptual=[], open_findings=[],
        grouped_report_md="GROUPED",
    )
    assert "## Suggested next steps" in md
    # Ordering: next-steps section precedes the embedded grouped dump.
    assert md.index("## Suggested next steps") < md.index("## Full grouped report")
    assert "new step" in md


def test_console_summary_ends_at_report_path_no_next_steps() -> None:
    """The summary is counts + report pointer only — next steps are rendered
    separately (``suggested_next_step_commands`` → ``_print_next_steps``) so
    the disposition actions and the pipeline suggestions land in one clean
    block instead of two competing ones."""
    applied = [
        AppliedOutcome(
            rec=_rec("a", "plan-correctness", "medium"),
            verdict="BLOCKED", summary="needs new file",
        ),
    ]
    out = console_summary(
        plan_name="p", iterate_enabled=True, stop_reason="converged",
        iterations=1, applied=applied, deferred=[],
        advisory_conceptual=[], open_findings=[],
        report_path=Path("/tmp/r.md"),
    )
    assert "blocked   1" in out
    # The report pointer is the closing line; no next-steps block follows.
    assert "next steps:" not in out
    assert out.rstrip().splitlines()[-1].strip().startswith("report  →")
    # Console output is rendered raw, so markdown markers are stripped.
    assert "**" not in out
    assert "`" not in out


# ---------- code-drift reconcile-plan suggestion (BACKLOG #65) ----------

def test_next_steps_code_drift_with_critical_emits_reconcile_first() -> None:
    """code_drifted + a critical/high finding → a reconcile-plan rebase
    bullet leads the prose list (most urgent)."""
    steps = _steps(
        code_drifted=True,
        open_findings=[_rec("o", "plan-correctness", "critical")],
    )
    assert "plan-tool reconcile-plan p" in steps[0]
    assert "stale against current code" in steps[0]


def test_next_steps_code_drift_with_high_in_applied_emits_reconcile() -> None:
    """The critical/high gate scans applied outcomes' recs too."""
    applied = [
        AppliedOutcome(
            rec=_rec("a", "plan-correctness", "high"),
            verdict="APPLIED",
        ),
    ]
    steps = _steps(code_drifted=True, applied=applied)
    assert "plan-tool reconcile-plan p" in steps[0]


def test_next_steps_code_drift_only_medium_omits_reconcile() -> None:
    """code_drifted but no critical/high (medium/nit only) → no
    reconcile-plan bullet (avoid docs-only-staleness noise)."""
    steps = _steps(
        code_drifted=True,
        open_findings=[_rec("o", "plan-correctness", "medium")],
        advisory_conceptual=[_rec("cc", "plan-completeness", "nit")],
    )
    assert not any("reconcile-plan" in s for s in steps)


def test_next_steps_no_drift_with_critical_omits_reconcile() -> None:
    """A critical finding but code did NOT drift → no reconcile-plan bullet."""
    steps = _steps(
        code_drifted=False,
        open_findings=[_rec("o", "plan-correctness", "critical")],
    )
    assert not any("reconcile-plan" in s for s in steps)


def test_next_steps_code_drift_severity_case_insensitive() -> None:
    """The critical/high gate is case-insensitive."""
    steps = _steps(
        code_drifted=True,
        open_findings=[_rec("o", "plan-correctness", "CRITICAL")],
    )
    assert "plan-tool reconcile-plan p" in steps[0]


# ---------- suggested_next_step_commands (console (command, desc) tuples) ----

def _cmds(**kw):
    base = dict(
        plan_name="p", applied=[], deferred=[],
        advisory_conceptual=[], open_findings=[],
    )
    base.update(kw)
    base.setdefault("verdict", _verdict_blocking_every_listed_gap(base))
    return suggested_next_step_commands(**base)


def test_next_step_gaps_close_only_ids_in_a_set_verdict_and_list_the_rest_as_advisory() -> None:
    corr = _rec("pc", "plan-correctness", "high")
    comp = _rec("cc", "plan-completeness", "high")
    adv = _rec("ac", "plan-completeness", "medium")
    det = _rec("d", "intent", "medium")
    gaps = next_step_gaps(
        blocking_verdict_from_gate(["pc", "cc", "gone"], [det]),
        correctness=[corr],
        advisory_conceptual=[comp, adv],
    )
    assert gaps.close_correctness == (corr,)
    assert gaps.close_completeness == (comp,)
    assert gaps.advisory_completeness == (adv,)
    assert gaps.close_deterministic == (det,)
    assert gaps.unlisted_blocking == 1


@pytest.mark.parametrize("state", ["set", "incomplete"])
def test_next_step_gaps_incomplete_keeps_the_ids_the_audit_established(state) -> None:
    """Amendment 1: an incomplete verdict closes the same ids a set does; only
    the stage differs. A HIGH correctness gap from a cut-short run is a gap to
    close, never advisory."""
    corr = _rec("pc", "plan-correctness", "high")
    det = _rec("d", "intent", "medium")
    gaps = next_step_gaps(
        BlockingVerdict(
            state,
            blocking_ids=("pc",),
            blocking_deterministic=(det,),
            untrusted_cause="transient" if state == "incomplete" else "",
        ),
        correctness=[corr],
    )
    assert gaps.close_correctness == (corr,)
    assert gaps.advisory_correctness == ()
    assert gaps.close_deterministic == (det,)


def test_next_step_gaps_absent_verdict_closes_nothing_by_id_but_keeps_deterministic() -> None:
    corr = _rec("pc", "plan-correctness", "high")
    det = _rec("d", "intent", "medium")
    gaps = next_step_gaps(
        BlockingVerdict("absent", blocking_ids=("pc",), blocking_deterministic=(det,)),
        correctness=[corr],
    )
    assert gaps.close_conceptual_count == 0
    assert gaps.advisory_correctness == (corr,)
    assert gaps.close_deterministic == (det,)


def test_no_renderer_names_an_apply_command_for_conceptual_gaps() -> None:
    """#367: conceptual gaps are closed by a session-directed edit, so the
    command block names no apply verb for them at any grade or stage, and the
    prose always leaves the reader an instruction instead.

    Replaces the old 'both renderers share one apply fence' contract, which
    became *vacuously* true the moment neither renderer could name the verb —
    it kept passing while asserting nothing. The positive
    ``session-directed edit`` assertion below is what stops this one from
    rotting the same way.
    """
    base = dict(
        correctness=[_rec("pc", "plan-correctness", "high")],
        advisory_conceptual=[_rec("cc", "plan-completeness")],
    )
    cases = [
        dict(bundle_status=SimpleNamespace(is_bare=True)),
        dict(),
        dict(bundle_status=SimpleNamespace(is_bare=False)),
        dict(bundle_status=None),
    ]
    for case in cases:
        kw = {**base, **case}
        assert not any(
            "completeness-apply" in c for c, _ in _cmds(**kw)
        ), case
        steps = _steps(**kw)
        assert any("session-directed edit" in s for s in steps), case
        assert not any("completeness-apply" in s for s in steps), case


def test_next_step_commands_are_command_description_tuples() -> None:
    """Manual remedies leave only executable command/description tuples."""
    assert [c for c, _ in _cmds(
        advisory_conceptual=[_rec("cc", "plan-completeness")]
    )] == ["plan-tool completeness-audit p --iterate"]
    cmds = _cmds(
        deferred=[_rec("fc", "files-coherence", "info",
                       suggested_action="add path")],
    )
    assert cmds == [("plan-tool run p", "no gaps left — execute the next runnable step")]



def test_next_step_commands_emit_no_conceptual_command() -> None:
    """#85/#367: correctness and completeness gaps are both unapplied and
    neither names a command — the console block stays empty, and the prose
    renderer carries the session-directed-edit instruction instead."""
    cmds = _cmds(
        correctness=[_rec("pc", "plan-correctness", "high")],
        advisory_conceptual=[_rec("cc", "plan-completeness")],
    )
    assert [c for c, _ in cmds] == ["plan-tool completeness-audit p --iterate"]


def test_next_step_commands_bare_plan_emits_no_correctness_command() -> None:
    """A bare-plan audit routes correctness gaps to a session-directed edit, so
    the console command block names nothing for them."""
    cmds = _cmds(
        correctness=[_rec("pc", "plan-correctness", "high")],
        bundle_status=SimpleNamespace(is_bare=True),
    )
    assert [c for c, _ in cmds] == ["plan-tool completeness-audit p --iterate"]


def test_next_step_commands_order_urgent_first() -> None:
    """BLOCKED (needs a manual split) leads, then advisory-conceptual, then
    deterministic drift clears, then the re-audit pointer."""
    applied = [
        AppliedOutcome(
            rec=_rec("a", "plan-correctness", "medium"),
            verdict="BLOCKED", summary="needs a new step",
        ),
    ]
    cmds = _cmds(
        applied=applied,
        advisory_conceptual=[_rec("cc", "plan-completeness")],
        deferred=[_rec("fc", "files-coherence", "info",
                       suggested_action="add path")],
        open_findings=[_rec("o", "plan-correctness", "high")],
    )
    verbs = [c for c, _ in cmds]
    assert verbs[0].startswith("plan-tool split p")
    assert not any("completeness-apply" in c for c in verbs)
    assert any("completeness-audit p --iterate" in c for c in verbs)
    # Commands stay short (no inline `--into "<a>"` syntax) so the aligned
    # column doesn't blow out; the full split form lives in the report.
    assert '--into' not in verbs[0]


def test_next_step_commands_bare_plan_suppresses_detail_authoring_actions() -> None:
    cmds = _cmds(
        deferred=[
            _rec("fc", "files-coherence", "info", suggested_action="add path"),
            _rec("dc", "detail-coverage", "info"),
        ],
        bundle_status=SimpleNamespace(is_bare=True),
    )
    # Detail-level diagnostics are withheld; only the shared stage remains.
    assert [c for c, _ in cmds] == ["plan-tool detail p"]


def test_next_step_commands_bare_plan_suppresses_conceptual_apply_action() -> None:
    cmds = _cmds(
        advisory_conceptual=[_rec("cc", "plan-completeness")],
        bundle_status=SimpleNamespace(is_bare=True),
    )
    assert [c for c, _ in cmds] == ["plan-tool completeness-audit p --iterate"]


def test_next_step_commands_bare_plan_correctness_still_omits_detail_authoring() -> None:
    cmds = _cmds(
        correctness=[_rec("pc", "plan-correctness", "high")],
        deferred=[_rec("dc", "detail-coverage", "high")],
        bundle_status=SimpleNamespace(is_bare=True),
    )
    verbs = [c for c, _ in cmds]
    assert "plan-tool completeness-apply p" not in verbs
    assert "plan-tool detail p" not in verbs


def test_next_step_commands_detailed_plan_keeps_detail_level_actions() -> None:
    cmds = _cmds(
        deferred=[
            _rec("fc", "files-coherence", "info", suggested_action="add path"),
            _rec("dc", "detail-coverage", "info"),
        ],
        bundle_status=SimpleNamespace(is_bare=False),
    )
    verbs = [cmd for cmd, _desc in cmds]
    assert "plan-tool completeness-apply p" not in verbs
    assert "plan-tool detail p" in verbs


def test_next_step_commands_parse_against_live_parser() -> None:
    """Every console next-step command the report emits must parse against the
    real CLI parser — a guard against stale suggestion strings (e.g. the
    removed `completeness-apply --apply`). Exercises all branches at once;
    the BLOCKED finding carries a concrete `step_id` so `split` emits a real
    `--step <id>` rather than the `--step N` template."""
    from plan_tool.cli import build_parser

    applied = [
        AppliedOutcome(
            rec=_rec("a", "plan-correctness", "high", step_id=2),
            verdict="BLOCKED", summary="needs a new step",
        ),
    ]
    cmds = _cmds(
        applied=applied,
        advisory_conceptual=[_rec("cc", "plan-completeness")],
        deferred=[
            _rec("fc", "files-coherence", "info", suggested_action="add path"),
            _rec("dc", "detail-coverage", "info"),
        ],
        open_findings=[_rec("o", "plan-correctness", "high")],
        code_drifted=True,
    )
    assert cmds  # the branches above must actually produce commands

    parser = build_parser()
    for cmd, _desc in cmds:
        argv = cmd.split()
        assert argv[0] == "plan-tool", cmd
        # parse_args raises SystemExit on an unknown subcommand/flag.
        parser.parse_args(argv[1:])


def test_next_step_commands_empty_when_nothing_outstanding() -> None:
    """No findings and a completed empty set → only the shared stage row;
    ``include_stage=False`` (a parent that appends its own) leaves none."""
    assert [c for c, _ in _cmds()] == ["plan-tool run p"]
    assert _cmds(include_stage=False) == []


def test_next_step_commands_code_drift_with_critical_emits_reconcile_first() -> None:
    """code_drifted + a critical finding → reconcile-plan command tuple
    leads the console list."""
    cmds = _cmds(
        code_drifted=True,
        open_findings=[_rec("o", "plan-correctness", "critical")],
    )
    assert cmds[0] == (
        "plan-tool reconcile-plan p",
        "# code drifted under the plan — rebase before running",
    )


def test_next_step_commands_code_drift_only_medium_omits_reconcile() -> None:
    cmds = _cmds(
        code_drifted=True,
        advisory_conceptual=[_rec("cc", "plan-completeness", "medium")],
    )
    assert not any("reconcile-plan" in c for c, _ in cmds)


def test_next_step_commands_no_drift_with_critical_omits_reconcile() -> None:
    cmds = _cmds(
        code_drifted=False,
        open_findings=[_rec("o", "plan-correctness", "critical")],
    )
    assert not any("reconcile-plan" in c for c, _ in cmds)


def test_next_step_commands_code_drift_reconcile_precedes_blocked() -> None:
    """reconcile-plan (drift) is the single most urgent step — ahead of even
    a BLOCKED split."""
    applied = [
        AppliedOutcome(
            rec=_rec("a", "plan-correctness", "high"),
            verdict="BLOCKED", summary="needs a new step",
        ),
    ]
    cmds = _cmds(code_drifted=True, applied=applied)
    verbs = [c for c, _ in cmds]
    assert verbs[0] == "plan-tool reconcile-plan p"
    assert any(v.startswith("plan-tool split p") for v in verbs)


def test_next_step_commands_blocked_bare_plan_emits_detail_first() -> None:
    applied = [
        AppliedOutcome(
            rec=_rec("a", "plan-correctness", "medium"),
            verdict="BLOCKED", summary="requires a new detail file",
        ),
    ]
    cmds = _cmds(
        applied=applied,
        bundle_status=SimpleNamespace(is_bare=True),
    )
    verbs = [c for c, _ in cmds]
    assert verbs[0] == "plan-tool detail p"


def test_next_step_commands_blocked_bare_plan_keeps_split_after_detail() -> None:
    applied = [
        AppliedOutcome(
            rec=_rec("a", "plan-correctness", "medium", step_id=2),
            verdict="BLOCKED", summary="requires a new detail file",
        ),
    ]
    cmds = _cmds(
        applied=applied,
        bundle_status=SimpleNamespace(is_bare=True),
    )
    verbs = [c for c, _ in cmds]
    assert verbs[0] == "plan-tool detail p"
    assert verbs[1] == "plan-tool split p --step 2"
    split_desc = next(d for c, d in cmds if c == "plan-tool split p --step 2")
    assert "if over-packed" in split_desc
    assert "BLOCKED — split into sub-steps (apply can't" not in split_desc


def test_next_step_commands_blocked_bare_plan_emits_detail_once() -> None:
    applied = [
        AppliedOutcome(
            rec=_rec("a", "plan-correctness", "medium", step_id=1),
            verdict="BLOCKED", summary="requires a new detail file",
        ),
        AppliedOutcome(
            rec=_rec("b", "plan-correctness", "medium", step_id=2),
            verdict="BLOCKED", summary="requires another detail file",
        ),
    ]
    cmds = _cmds(
        applied=applied,
        bundle_status=SimpleNamespace(is_bare=True),
    )
    detail_cmds = [c for c, _ in cmds if c == "plan-tool detail p"]
    assert len(detail_cmds) == 1


def test_next_step_commands_blocked_detailed_plan_unchanged() -> None:
    applied = [
        AppliedOutcome(
            rec=_rec("a", "plan-correctness", "medium", step_id=2),
            verdict="BLOCKED", summary="needs a new step",
        ),
    ]
    none_cmds = _cmds(applied=applied)
    detailed_cmds = _cmds(
        applied=applied,
        bundle_status=SimpleNamespace(is_bare=False),
    )
    assert detailed_cmds == none_cmds
    assert none_cmds[0][0].startswith("plan-tool split p")
    assert not any(c == "plan-tool detail p" for c, _ in none_cmds)


def test_next_step_commands_code_drift_precedes_bare_blocked_detail() -> None:
    applied = [
        AppliedOutcome(
            rec=_rec("a", "plan-correctness", "high"),
            verdict="BLOCKED", summary="requires a new detail file",
        ),
    ]
    cmds = _cmds(
        code_drifted=True,
        applied=applied,
        bundle_status=SimpleNamespace(is_bare=True),
    )
    verbs = [c for c, _ in cmds]
    assert verbs[0] == "plan-tool reconcile-plan p"
    assert verbs[1] == "plan-tool detail p"


def test_next_step_commands_bare_blocked_parse_against_live_parser() -> None:
    from plan_tool.cli import build_parser

    applied = [
        AppliedOutcome(
            rec=_rec("a", "plan-correctness", "high", step_id=2),
            verdict="BLOCKED", summary="requires a new detail file",
        ),
    ]
    cmds = _cmds(
        applied=applied,
        bundle_status=SimpleNamespace(is_bare=True),
        code_drifted=True,
    )
    assert cmds

    parser = build_parser()
    for cmd, _desc in cmds:
        argv = cmd.split()
        assert argv[0] == "plan-tool", cmd
        parser.parse_args(argv[1:])


# ---------- write_completeness_report ----------

def test_write_report_lands_under_reports_dir(tmp_path: Path) -> None:
    plan_path = tmp_path / "plans" / "1-my-plan.md"
    path = write_completeness_report(
        plan_path, "# report\n",
        repo_root=tmp_path,
        now=datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc),
    )
    assert path == (
        tmp_path / "plans" / "plan-details" / "my-plan" / "reports"
        / "20260526-120000-completeness.md"
    )
    assert path.read_text(encoding="utf-8") == "# report\n"


def test_write_report_accumulates_not_clobbers(tmp_path: Path) -> None:
    plan_path = tmp_path / "1-p.md"
    p1 = write_completeness_report(
        plan_path, "a", repo_root=tmp_path,
        now=datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc),
    )
    p2 = write_completeness_report(
        plan_path, "b", repo_root=tmp_path,
        now=datetime(2026, 5, 26, 12, 0, 1, tzinfo=timezone.utc),
    )
    assert p1 != p2
    assert p1.exists() and p2.exists()


def test_unknown_audit_coverage_projection_has_no_clean_verdict(
    capsys,
) -> None:
    det = _DeterministicReport(None, [], [], [], [], [], [])
    args = SimpleNamespace(name="demo", fail_on_findings=False)

    assert _render_completeness_json(
        args, det, [], has_blocking=False, budget={}
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["coverage"] == {
        "evidence_status": "unknown-legacy",
        "budget_limited": None,
        "passes_used": None,
        "cap": None,
        "recommendation_kind": None,
        "recommended_passes": None,
        "recommendation_advice": None,
        "confirmation_kind": None,
        "conforming_pass_count": None,
        "failed_or_malformed_pass_count": None,
        "early_stop_reason": None,
    }
    markdown = _render_coverage_confidence_markdown({})
    assert markdown is not None
    assert "Coverage confidence unknown" in markdown
    assert "lacks saved conceptual-audit evidence" in markdown


def test_completeness_json_keeps_qualified_result_additive(capsys) -> None:
    det = _DeterministicReport(None, [], [], [], [], [], [])
    result = {
        "headline": "no-qualified-current-evidence",
        "stage": "not-sampled",
        "coverage": "not-sampled",
        "revision_status": "not-sampled",
        "audit_revision": None,
    }
    args = SimpleNamespace(name="demo", fail_on_findings=False)

    assert _render_completeness_json(
        args, det, [], has_blocking=False, qualified_result=result
    ) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["plan"] == "demo"
    assert payload["qualified_result"] == result


# ---------- JSON sidecar for saved findings ----------

def test_write_report_emits_json_sidecar_when_recommendations_given(
    tmp_path: Path,
) -> None:
    """Saved readers load structured findings without rerunning the audit."""
    from plan_tool.review_persistence import load_review

    recs = [_rec("cache-invalidation", "plan-completeness", "medium")]
    plan_path = tmp_path / "plans" / "1-my-plan.md"
    _write_minimal_plan(plan_path)
    md_path = write_completeness_report(
        plan_path, "# report\n",
        repo_root=tmp_path,
        now=datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc),
        recommendations=recs,
        plan_rel_path="plans/1-my-plan.md",
    )
    json_path = md_path.parent / "20260526-120000-completeness.json"
    assert json_path.exists()
    # Sidecar lands in the same reports dir as the markdown report.
    assert json_path.parent == (
        tmp_path / "plans" / "plan-details" / "my-plan" / "reports"
    )
    saved = load_review(json_path)
    assert saved.kind == "completeness"
    assert [r.id for r in saved.recommendations] == ["cache-invalidation"]
    assert saved.plan_path == "plans/1-my-plan.md"
    # An ordinary final save omits the role key rather than serializing
    # ``false``, keeping historical unmarked sidecars on the legacy-final path.
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert "is_pre_apply_checkpoint" not in payload
    assert payload["version"] != 3
    assert saved.is_pre_apply_checkpoint is False


def test_write_completeness_report_derives_audit_stage_when_omitted(
    tmp_path: Path,
) -> None:
    from plan_tool.convergence import STAGE_BARE, STAGE_DETAIL

    recs = [_rec("derived-stage", "plan-completeness", "medium")]
    plan_path = tmp_path / "plans" / "1-my-plan.md"
    _write_minimal_plan(plan_path)
    md_path = write_completeness_report(
        plan_path, "# report\n",
        repo_root=tmp_path,
        now=datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc),
        recommendations=recs,
        plan_rel_path="plans/1-my-plan.md",
    )
    saved = load_review(md_path.with_suffix(".json"))
    assert saved.audit_stage in {STAGE_BARE, STAGE_DETAIL}
    payload = json.loads(md_path.with_suffix(".json").read_text(encoding="utf-8"))
    assert payload["audit_stage"] in {STAGE_BARE, STAGE_DETAIL}
    # Bare plan with no detail files derives bare.
    assert saved.audit_stage == STAGE_BARE


def test_write_completeness_report_soft_fails_audit_stage_on_unparseable_plan(
    tmp_path: Path,
) -> None:
    """Unparseable plan after ``.md`` write must still land the sidecar.

    Derive-at-write used to re-raise ``ParseError``/``ValidationError`` after
    the markdown was durable, orphaning the report without a JSON sibling.
    Soft-fail omits ``audit_stage`` instead (same contract as stamp).
    """
    from plan_tool.review_persistence import load_review

    plan_path = tmp_path / "plans" / "1-broken.md"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text("this is not a plan\n", encoding="utf-8")
    md_path = write_completeness_report(
        plan_path, "# report\n",
        repo_root=tmp_path,
        now=datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc),
        recommendations=[_rec("soft-fail", "plan-completeness", "medium")],
        plan_rel_path="plans/1-broken.md",
    )
    assert md_path.is_file()
    json_path = md_path.with_suffix(".json")
    assert json_path.is_file()
    saved = load_review(json_path)
    assert saved.audit_stage is None
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert "audit_stage" not in payload


def test_write_completeness_report_soft_fails_audit_stage_on_invalid_utf8_plan(
    tmp_path: Path,
) -> None:
    plan_path = tmp_path / "plans" / "1-broken.md"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_bytes(b"\xff")

    md_path = write_completeness_report(
        plan_path,
        "# report\n",
        repo_root=tmp_path,
        now=datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc),
        recommendations=[_rec("invalid-utf8", "plan-completeness", "medium")],
        plan_rel_path="plans/1-broken.md",
    )

    saved = load_review(md_path.with_suffix(".json"))
    assert saved.audit_stage is None
    assert saved.step_ids_present is False


def test_write_completeness_report_retries_audit_stage_after_transient_parse_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from plan_tool.convergence import STAGE_BARE

    plan_path = tmp_path / "plans" / "1-my-plan.md"
    _write_minimal_plan(plan_path)
    parsed_plan = parse_plan(plan_path)
    calls = 0

    def transient_parse(_path: Path):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("temporary read failure")
        return parsed_plan

    monkeypatch.setattr(completeness_report_module, "parse_plan", transient_parse)

    md_path = write_completeness_report(
        plan_path,
        "# report\n",
        repo_root=tmp_path,
        now=datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc),
        recommendations=[_rec("transient", "plan-completeness", "medium")],
        plan_rel_path="plans/1-my-plan.md",
    )

    saved = load_review(md_path.with_suffix(".json"))
    assert calls == 2
    assert saved.audit_stage == STAGE_BARE
    assert saved.step_ids_present is True


def test_write_report_marks_checkpoint_sidecar_when_requested(
    tmp_path: Path,
) -> None:
    """An explicit checkpoint request writes the version-3 role marker without
    disturbing the report and sidecar names."""
    from plan_tool.review_persistence import load_review

    plan_path = tmp_path / "plans" / "1-my-plan.md"
    _write_minimal_plan(plan_path)
    md_path = write_completeness_report(
        plan_path, "# report\n",
        repo_root=tmp_path,
        now=datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc),
        recommendations=[_rec("checkpointed", "plan-correctness")],
        plan_rel_path="plans/1-my-plan.md",
        is_pre_apply_checkpoint=True,
    )
    assert md_path.name == "20260526-120000-completeness.md"
    json_path = md_path.with_suffix(".json")
    assert json_path.name == "20260526-120000-completeness.json"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["version"] == 3
    assert payload["is_pre_apply_checkpoint"] is True
    assert load_review(json_path).is_pre_apply_checkpoint is True


def test_same_second_checkpoint_and_final_allocate_distinct_report_pairs(
    tmp_path: Path,
) -> None:
    """A checkpoint and the final report it precedes can share a wall-clock
    second; each keeps its own whole-second stem and every artifact survives."""
    plan_path = tmp_path / "plans" / "1-my-plan.md"
    _write_minimal_plan(plan_path)
    same_second = datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc)
    checkpoint_md = write_completeness_report(
        plan_path, "# checkpoint\n",
        repo_root=tmp_path,
        now=same_second,
        recommendations=[_rec("chk", "plan-correctness")],
        plan_rel_path="plans/1-my-plan.md",
        is_pre_apply_checkpoint=True,
    )
    final_md = write_completeness_report(
        plan_path, "# final\n",
        repo_root=tmp_path,
        now=same_second,
        recommendations=[_rec("fin", "plan-correctness")],
        plan_rel_path="plans/1-my-plan.md",
    )

    assert checkpoint_md.name == "20260526-120000-completeness.md"
    assert final_md.name == "20260526-120001-completeness.md"
    assert checkpoint_md.read_text(encoding="utf-8") == "# checkpoint\n"
    assert final_md.read_text(encoding="utf-8") == "# final\n"

    checkpoint = _load_sidecar(checkpoint_md)
    final = _load_sidecar(final_md)
    assert [r.id for r in checkpoint.recommendations] == ["chk"]
    assert [r.id for r in final.recommendations] == ["fin"]
    # Filename and persisted timestamp agree, so the allocated stem is what a
    # history reader sorts on.
    assert checkpoint.created_at == "2026-05-26T12:00:00Z"
    assert final.created_at == "2026-05-26T12:00:01Z"
    assert checkpoint.is_pre_apply_checkpoint is True
    assert final.is_pre_apply_checkpoint is False


def test_same_second_allocation_preserves_data_contract_payload(
    tmp_path: Path,
) -> None:
    """The data-contract payload is a reserved member of the artifact set, so
    an occupied stem advances the whole next write instead of clobbering it."""
    plan_path = tmp_path / "plans" / "1-my-plan.md"
    _write_minimal_plan(plan_path)
    reports_dir = tmp_path / "plans" / "plan-details" / "my-plan" / "reports"
    reports_dir.mkdir(parents=True)
    occupied = reports_dir / "20260526-120000-completeness-data-contract.json"
    occupied.write_text('{"kind": "data-contract", "payloads": {}}\n', encoding="utf-8")

    md_path = write_completeness_report(
        plan_path, "# report\n",
        repo_root=tmp_path,
        now=datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc),
        recommendations=[_rec("dc", "data-contract")],
        plan_rel_path="plans/1-my-plan.md",
        data_contract_payloads={"dc": {"operation": "add"}},
    )

    assert md_path.name == "20260526-120001-completeness.md"
    assert md_path.with_suffix(".json").is_file()
    written_payload = reports_dir / "20260526-120001-completeness-data-contract.json"
    assert json.loads(written_payload.read_text(encoding="utf-8"))["payloads"] == {
        "dc": {"operation": "add"}
    }
    # The pre-existing member of the occupied set is untouched.
    assert json.loads(occupied.read_text(encoding="utf-8"))["payloads"] == {}


def test_write_completeness_report_persists_normalized_audit_coverage(
    tmp_path: Path,
) -> None:
    coverage = {
        "budget_limited": False,
        "passes_used": 2,
        "cap": 3,
        "recommendation_kind": None,
        "recommended_passes": None,
        "recommendation_advice": None,
        "confirmation_kind": "confirmed-dry",
        "conforming_pass_count": 2,
        "failed_or_malformed_pass_count": 0,
    }
    plan_path = tmp_path / "plans" / "1-my-plan.md"
    _write_minimal_plan(plan_path)
    md_path = write_completeness_report(
        plan_path,
        "# report\n",
        repo_root=tmp_path,
        now=datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc),
        recommendations=[_rec("coverage", "plan-completeness")],
        plan_rel_path="plans/1-my-plan.md",
        audit_coverage=coverage,
    )

    sidecar = _load_sidecar(md_path)
    assert sidecar.audit_coverage == coverage
    payload = json.loads(md_path.with_suffix(".json").read_text(encoding="utf-8"))
    assert payload["audit_coverage"] == coverage


def test_write_report_requires_plan_rel_path_for_sidecar(
    tmp_path: Path,
) -> None:
    import pytest

    recs = [_rec("c", "plan-completeness")]
    plan_path = tmp_path / "1-p.md"
    with pytest.raises(ValueError, match="plan_rel_path"):
        write_completeness_report(
            plan_path, "x", repo_root=tmp_path,
            recommendations=recs,  # missing plan_rel_path
        )


def test_write_report_no_sidecar_when_no_recommendations(
    tmp_path: Path,
) -> None:
    """Back-compat: callers that don't pass recommendations get the
    legacy markdown-only behavior. No JSON file is created."""
    plan_path = tmp_path / "1-p.md"
    md_path = write_completeness_report(
        plan_path, "x", repo_root=tmp_path,
        now=datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc),
    )
    siblings = list(md_path.parent.glob("*.json"))
    assert siblings == []


# ---------- Fingerprint persistence on the sidecar ----------

def _load_sidecar(md_path: Path):
    from plan_tool.review_persistence import load_review

    json_path = md_path.with_suffix(".json")
    return load_review(json_path)


def test_write_report_persists_plan_fingerprint(tmp_path: Path) -> None:
    recs = [_rec("c", "plan-completeness")]
    plan_path = tmp_path / "plans" / "1-my-plan.md"
    _write_minimal_plan(plan_path)
    md_path = write_completeness_report(
        plan_path, "# r\n", repo_root=tmp_path,
        now=datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc),
        recommendations=recs,
        plan_fingerprint="abc123",
        plan_rel_path="plans/1-my-plan.md",
    )
    assert _load_sidecar(md_path).plan_fingerprint == "abc123"


def test_write_report_persists_code_fingerprint(tmp_path: Path) -> None:
    recs = [_rec("c", "plan-completeness")]
    plan_path = tmp_path / "plans" / "1-my-plan.md"
    _write_minimal_plan(plan_path)
    md_path = write_completeness_report(
        plan_path, "# r\n", repo_root=tmp_path,
        now=datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc),
        recommendations=recs,
        code_fingerprint={"plan_tool/x.py": "deadbeef"},
        plan_rel_path="plans/1-my-plan.md",
    )
    assert _load_sidecar(md_path).code_fingerprint == {
        "plan_tool/x.py": "deadbeef"
    }


def test_write_report_fingerprints_default_empty(tmp_path: Path) -> None:
    recs = [_rec("c", "plan-completeness")]
    plan_path = tmp_path / "plans" / "1-my-plan.md"
    _write_minimal_plan(plan_path)
    md_path = write_completeness_report(
        plan_path, "# r\n", repo_root=tmp_path,
        now=datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc),
        recommendations=recs,
        plan_rel_path="plans/1-my-plan.md",
    )
    saved = _load_sidecar(md_path)
    assert saved.plan_fingerprint == ""
    assert saved.code_fingerprint == {}


def test_write_report_none_code_fingerprint_stored_as_empty_dict(
    tmp_path: Path,
) -> None:
    recs = [_rec("c", "plan-completeness")]
    plan_path = tmp_path / "plans" / "1-my-plan.md"
    _write_minimal_plan(plan_path)
    md_path = write_completeness_report(
        plan_path, "# r\n", repo_root=tmp_path,
        now=datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc),
        recommendations=recs,
        code_fingerprint=None,
        plan_rel_path="plans/1-my-plan.md",
    )
    assert _load_sidecar(md_path).code_fingerprint == {}


def test_write_report_persists_both_axes(tmp_path: Path) -> None:
    recs = [
        _rec("a", "plan-correctness"),
        _rec("b", "plan-completeness"),
    ]
    plan_path = tmp_path / "plans" / "1-my-plan.md"
    _write_minimal_plan(plan_path)
    md_path = write_completeness_report(
        plan_path, "# r\n", repo_root=tmp_path,
        now=datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc),
        recommendations=recs,
        plan_rel_path="plans/1-my-plan.md",
    )
    saved = _load_sidecar(md_path)
    assert [r.id for r in saved.recommendations] == ["a", "b"]
    assert [r.source for r in saved.recommendations] == [
        "plan-correctness",
        "plan-completeness",
    ]


def test_write_report_persists_data_contract_recommendations_without_schema_change(
    tmp_path: Path,
) -> None:
    from plan_tool.review_persistence import SCHEMA_VERSION

    recs = [_rec("dc", "data-contract", "medium")]
    payloads = {
        "dc": {
            "target_section": "SavedReview",
            "operation": "add",
            "candidate_fields": {"field": "new_field"},
            "freshness": {
                "registry_fingerprint": "registry",
                "contract_fingerprint": "contract",
            },
        }
    }
    plan_path = tmp_path / "plans" / "1-my-plan.md"
    _write_minimal_plan(plan_path)
    md_path = write_completeness_report(
        plan_path,
        "# r\n",
        repo_root=tmp_path,
        now=datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc),
        recommendations=recs,
        data_contract_payloads=payloads,
        plan_rel_path="plans/1-my-plan.md",
    )
    saved = _load_sidecar(md_path)
    assert saved.schema_version == SCHEMA_VERSION
    assert [(r.id, r.source) for r in saved.recommendations] == [
        ("dc", "data-contract")
    ]
    payload_path = md_path.parent / "20260526-120000-completeness-data-contract.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["review_id"] == "20260526-120000-completeness"
    assert payload["payloads"] == payloads


# ---------- Per-finding "Address:" guidance in the report ----------

def test_report_advertises_no_apply_command_per_conceptual_finding() -> None:
    """#367: no per-finding apply command is advertised. The finding's
    ``[anchor-slug]`` tag is the handle a reader cites, and the section
    intro carries the session-directed-edit instruction instead — so the
    report never names a command that no longer closes conceptual gaps."""
    rec = _rec("cache-invalidation", "plan-completeness", "medium")
    md = build_report_md(
        plan_title="T", plan_name="1-my-plan", iterate_enabled=False,
        stop_reason=None, iterations=0, applied=[], deferred=[],
        advisory_conceptual=[rec], open_findings=[],
        grouped_report_md="G",
    )
    assert "Address: `plan-tool completeness-apply" not in md
    assert "`[cache-invalidation]`" in md
    assert "session-directed edit" in md


def test_report_bare_plan_omits_conceptual_apply_address() -> None:
    rec = _rec("cache-invalidation", "plan-completeness", "medium")
    md = build_report_md(
        plan_title="T", plan_name="1-my-plan", iterate_enabled=False,
        stop_reason=None, iterations=0, applied=[], deferred=[],
        advisory_conceptual=[rec], open_findings=[],
        grouped_report_md="G",
        bundle_status=SimpleNamespace(is_bare=True),
    )
    assert "Address: `plan-tool completeness-apply" not in md
    assert "Review plan-level completeness gaps now" in md
    assert "leave detail-only remedies for detail authoring" in md


def test_report_bare_plan_guidance_keeps_plan_contract_edits_actionable() -> None:
    rec = _rec("cache-invalidation", "plan-completeness", "medium")
    md = build_report_md(
        plan_title="T", plan_name="1-my-plan", iterate_enabled=False,
        stop_reason=None, iterations=0, applied=[], deferred=[],
        advisory_conceptual=[rec], open_findings=[],
        grouped_report_md="G",
        bundle_status=SimpleNamespace(is_bare=True),
    )
    assert "Correct plan contracts through a session-directed edit before authoring details" in md
    assert "Apply actions are withheld until a complete detail bundle exists" not in md


def test_report_bare_plan_correctness_intro_omits_completeness_walk_promise() -> None:
    correctness = [_rec("pc", "plan-correctness", "high")]
    md = build_report_md(
        plan_title="T", plan_name="1-my-plan", iterate_enabled=False,
        stop_reason=None, iterations=0, applied=[], deferred=[],
        advisory_conceptual=[], open_findings=[],
        grouped_report_md="G",
        correctness=correctness,
        bundle_status=SimpleNamespace(is_bare=True),
    )
    section = md.split("## Conceptual correctness")[1].split("##")[0]
    assert "session-directed edit" in section
    assert "then the completeness gaps" not in section
    assert "before the completeness gaps" not in section


def test_report_detailed_plan_correctness_intro_promises_completeness_order() -> None:
    """A detailed plan's correctness intro still promises correctness is
    addressed *before* the completeness gaps — the ordering contract that
    distinguishes it from the bare-plan intro, which makes no such promise.
    (#367 removed the apply-verb code block that used to carry the trailing
    "then the completeness gaps" half of this wording.)"""
    correctness = [_rec("pc", "plan-correctness", "high")]
    md = build_report_md(
        plan_title="T", plan_name="1-my-plan", iterate_enabled=False,
        stop_reason=None, iterations=0, applied=[], deferred=[],
        advisory_conceptual=[], open_findings=[],
        grouped_report_md="G",
        correctness=correctness,
        bundle_status=SimpleNamespace(is_bare=False),
    )
    section = md.split("## Conceptual correctness")[1].split("##")[0]
    assert "before the completeness gaps" in section
    assert "session-directed edit" in section


def test_report_prefers_readable_anchor_over_hashed_id() -> None:
    """When the audit captured the finding's ``[anchor-slug]``, the report's
    finding tag uses it instead of the hashed rec id — ``[cache-invalidation]``
    beats ``[plan-plan-completeness-0de2b7ba]`` for a human. The tag is the
    only place the anchor surfaces now (#367 removed the per-finding apply
    command), so this is what keeps the readable form load-bearing."""
    rec = _rec(
        "plan-plan-completeness-0de2b7ba", "plan-completeness",
        anchor="cache-invalidation",
    )
    md = build_report_md(
        plan_title="T", plan_name="1-my-plan", iterate_enabled=False,
        stop_reason=None, iterations=0, applied=[], deferred=[],
        advisory_conceptual=[rec], open_findings=[],
        grouped_report_md="G",
    )
    assert "`[cache-invalidation]`" in md
    assert "`[plan-plan-completeness-0de2b7ba]`" not in md


def test_advisory_conceptual_why_points_at_a_session_directed_edit() -> None:
    """#367: the 'why not auto-applied' rationale names the session-directed
    edit — no tool command applies a conceptual gap — and still points at the
    per-finding anchor slug so a reader can cite one precisely."""
    why = WHY["advisory-conceptual"]
    assert "session-directed edit" in why
    assert "anchor-slug" in why
    assert "completeness-apply" not in why


# ---------- compute_code_fingerprint ----------


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
    import hashlib

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


# ---------- resolve_reusable_audit ----------

_T0 = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
_T1 = datetime(2026, 6, 1, 12, 0, 5, tzinfo=timezone.utc)
_T2 = datetime(2026, 6, 1, 12, 0, 9, tzinfo=timezone.utc)


def _write_reusable_plan(
    tmp_path: Path, *, docs_only: bool = False, new_entry: bool = False
) -> Path:
    """Lay down ``plans/1-demo.md`` (slug ``demo``) with a detail bundle and,
    unless ``docs_only``, two on-disk ``step.files`` code files. ``new_entry``
    declares a ``src/baz.py (new)`` entry left *uncreated* so a test can land
    it later. Returns the absolute plan path."""
    plan_path = tmp_path / "plans" / "1-demo.md"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    if docs_only:
        files_block = ""
    else:
        files_block = "    files:\n      - src/foo.py\n      - src/bar.py\n"
        if new_entry:
            files_block += "      - src/baz.py (new)\n"
    plan_path.write_text(
        "---\n"
        "title: Demo\n"
        "status: planning\n"
        "priority: medium\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: Stub\n"
        f"{files_block}"
        "    detail: plans/plan-details/demo/01-stub.md\n"
        "---\n"
        "# Demo\n",
        encoding="utf-8",
    )
    detail = tmp_path / "plans" / "plan-details" / "demo" / "01-stub.md"
    detail.parent.mkdir(parents=True, exist_ok=True)
    detail.write_text("# detail\n", encoding="utf-8")
    if not docs_only:
        src = tmp_path / "src"
        src.mkdir(parents=True, exist_ok=True)
        (src / "foo.py").write_text("foo = 1\n", encoding="utf-8")
        (src / "bar.py").write_text("bar = 2\n", encoding="utf-8")
    return plan_path


def _save_completeness_sidecar(
    tmp_path: Path,
    plan_path: Path,
    *,
    recs: list[Recommendation],
    now: datetime,
    present: bool = True,
    kind: str = "completeness",
    audit_coverage: Optional[dict[str, object]] = None,
    is_pre_apply_checkpoint: bool = False,
) -> Path:
    """Save a sidecar with fingerprints computed from current disk. When
    ``present`` is False, persists a legacy/never-computed capture
    (``plan_fingerprint=""``, ``code_fingerprint=None``). Re-saving at the
    same ``now`` rewrites the same timestamped file from scratch."""
    plan = parse_plan(plan_path)
    if present:
        from plan_tool.fingerprint import audit_input_detail_fingerprint
        from plan_tool.review_persistence import AuditInputSnapshot

        snapshot = AuditInputSnapshot.capture(plan_path, tmp_path)
        plan_fp = snapshot.revision["plan_digest"]
        code_fp: Optional[dict[str, str]] = compute_code_fingerprint(
            plan, plan_path, tmp_path
        )
    else:
        plan_fp = ""
        code_fp = None
        snapshot = None
    save_kwargs = dict(
        plan_slug="demo",
        plan_path="plans/1-demo.md",
        repo_root=tmp_path,
        report_md="# r\n",
        recommendations=recs,
        plan_fingerprint=plan_fp,
        code_fingerprint=code_fp,
        kind=kind,
        now=now,
        audit_coverage=audit_coverage,
        is_pre_apply_checkpoint=is_pre_apply_checkpoint,
        detail_bundle_fingerprint=(
            audit_input_detail_fingerprint(snapshot)
            if snapshot is not None and kind == "completeness"
            else None
        ),
    )
    if is_pre_apply_checkpoint:
        save_kwargs["qualified_result"] = None
        save_kwargs["checkpoint_audit_revision"] = (
            snapshot.revision
            if snapshot is not None and kind == "completeness"
            else None
        )
    else:
        save_kwargs["audit_revision"] = (
            snapshot.revision
            if snapshot is not None and kind == "completeness"
            else None
        )
    return save_review(**save_kwargs)


def _rewrite_sidecar_payload(path: Path, **overrides: object) -> Path:
    """Write a saved sidecar back with ``overrides`` applied to its payload.

    ``save_review`` emits only the role a producer can legitimately write, so
    legacy and untrusted role metadata is authored here."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update(overrides)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _pin_forms(sidecar: Path) -> tuple[str, str]:
    """The bare ``<ts>`` and full ``<ts>-completeness`` ``review_id`` forms."""
    full_stem = sidecar.stem
    return full_stem[: -len("-completeness")], full_stem


def test_resolve_reusable_audit_fresh(tmp_path: Path) -> None:
    """A final sidecar with a sampled revision is current on matching input."""
    plan_path = _write_reusable_plan(tmp_path)
    sidecar = _save_completeness_sidecar(
        tmp_path, plan_path, recs=[_rec("a", "plan-correctness")], now=_T0
    )
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["version"] == 4
    assert payload["is_pre_apply_checkpoint"] is False
    audit = resolve_reusable_audit("demo", tmp_path, plan_path=plan_path)
    assert isinstance(audit, ReusableAudit)
    assert audit.plan_match is True
    assert audit.code_match is True
    assert audit.fresh is True
    assert audit.drifted_code == []


def test_resolve_reusable_audit_v3_explicit_false_is_eligible(
    tmp_path: Path,
) -> None:
    """A raw version-3 sidecar carrying literal ``false`` is an ordinary final
    report — read for compatibility even though no producer emits it."""
    plan_path = _write_reusable_plan(tmp_path)
    sidecar = _save_completeness_sidecar(
        tmp_path, plan_path, recs=[_rec("explicit-final", "plan-correctness")],
        now=_T0,
    )
    _rewrite_sidecar_payload(sidecar, version=3, is_pre_apply_checkpoint=False)
    assert load_review(sidecar).is_pre_apply_checkpoint is False

    audit = resolve_reusable_audit("demo", tmp_path, plan_path=plan_path)

    assert audit is not None
    assert [r.id for r in audit.saved.recommendations] == ["explicit-final"]
    assert audit.fresh is False


def test_resolve_reusable_audit_skips_newer_marked_checkpoint(
    tmp_path: Path,
) -> None:
    """A pre-apply checkpoint captures findings mid-apply, so it never
    displaces the last completed audit — even with matching fingerprints."""
    plan_path = _write_reusable_plan(tmp_path)
    _save_completeness_sidecar(
        tmp_path, plan_path, recs=[_rec("final", "plan-correctness")], now=_T0
    )
    checkpoint = _save_completeness_sidecar(
        tmp_path, plan_path, recs=[_rec("partial", "plan-correctness")],
        now=_T1, is_pre_apply_checkpoint=True,
    )
    saved_checkpoint = load_review(checkpoint)
    assert saved_checkpoint.is_pre_apply_checkpoint is True
    # The checkpoint is fresh by fingerprint: only its role excludes it.
    assert saved_checkpoint.plan_fingerprint == saved_checkpoint.audit_revision["plan_digest"]

    audit = resolve_reusable_audit("demo", tmp_path, plan_path=plan_path)

    assert audit is not None
    assert [r.id for r in audit.saved.recommendations] == ["final"]
    assert audit.fresh is True


def test_resolve_reusable_audit_skips_newer_unloadable_sidecar(
    tmp_path: Path,
) -> None:
    """A corrupt candidate cannot block the preceding final audit."""
    plan_path = _write_reusable_plan(tmp_path)
    _save_completeness_sidecar(
        tmp_path, plan_path, recs=[_rec("final", "plan-correctness")], now=_T0
    )
    corrupt = _save_completeness_sidecar(
        tmp_path, plan_path, recs=[_rec("corrupt", "plan-correctness")], now=_T1
    )
    corrupt.write_text("not valid JSON\n", encoding="utf-8")

    audit = resolve_reusable_audit("demo", tmp_path, plan_path=plan_path)

    assert audit is not None
    assert [r.id for r in audit.saved.recommendations] == ["final"]
    assert audit.fresh is True


def test_resolve_reusable_audit_skips_unknown_checkpoint_role(
    tmp_path: Path,
) -> None:
    """Role metadata a reader cannot trust as final fails closed in every
    shape, leaving the older final report selectable."""
    unknown_role_payloads = (
        ("malformed marker", {"version": 3, "is_pre_apply_checkpoint": "yes"}),
        (
            "misplaced marker",
            {"version": 3, "kind": "review", "is_pre_apply_checkpoint": True},
        ),
        ("role/version mismatch", {"version": 1, "is_pre_apply_checkpoint": True}),
    )
    plan_path = _write_reusable_plan(tmp_path)
    _save_completeness_sidecar(
        tmp_path, plan_path, recs=[_rec("final", "plan-correctness")], now=_T0
    )

    for label, overrides in unknown_role_payloads:
        # Re-save first so each shape starts from a clean ordinary-final payload.
        newer = _save_completeness_sidecar(
            tmp_path, plan_path, recs=[_rec("untrusted", "plan-correctness")],
            now=_T1,
        )
        _rewrite_sidecar_payload(newer, **overrides)
        assert load_review(newer).is_pre_apply_checkpoint is None, label

        audit = resolve_reusable_audit("demo", tmp_path, plan_path=plan_path)

        assert audit is not None, label
        assert [r.id for r in audit.saved.recommendations] == ["final"], label
        assert audit.fresh is True, label


def test_resolve_reusable_audit_skips_filename_kind_mismatch(
    tmp_path: Path,
) -> None:
    """The ``-completeness.json`` name locates candidates; the loaded ``kind``
    decides, so a non-completeness payload is neither reused nor pinnable."""
    plan_path = _write_reusable_plan(tmp_path)
    _save_completeness_sidecar(
        tmp_path, plan_path, recs=[_rec("final", "plan-correctness")], now=_T0
    )
    mismatched = _save_completeness_sidecar(
        tmp_path, plan_path, recs=[_rec("not-completeness", "plan-correctness")],
        now=_T1,
    )
    _rewrite_sidecar_payload(mismatched, kind="review")
    saved_mismatch = load_review(mismatched)
    assert saved_mismatch.kind == "review"
    assert saved_mismatch.is_pre_apply_checkpoint is None

    audit = resolve_reusable_audit("demo", tmp_path, plan_path=plan_path)

    assert audit is not None
    assert [r.id for r in audit.saved.recommendations] == ["final"]
    for review_id in _pin_forms(mismatched):
        assert (
            resolve_reusable_audit(
                "demo", tmp_path, plan_path=plan_path, review_id=review_id
            )
            is None
        ), review_id


def test_resolve_reusable_audit_pinned_unsafe_sidecar_returns_none(
    tmp_path: Path,
) -> None:
    """An explicit id names one sidecar: an unsafe role declines outright
    rather than substituting the fresh final report that exists beside it."""
    plan_path = _write_reusable_plan(tmp_path)
    final = _save_completeness_sidecar(
        tmp_path, plan_path, recs=[_rec("final", "plan-correctness")], now=_T0
    )
    checkpoint = _save_completeness_sidecar(
        tmp_path, plan_path, recs=[_rec("partial", "plan-correctness")],
        now=_T1, is_pre_apply_checkpoint=True,
    )
    unknown_role = _save_completeness_sidecar(
        tmp_path, plan_path, recs=[_rec("untrusted", "plan-correctness")],
        now=_T2,
    )
    _rewrite_sidecar_payload(
        unknown_role, version=4, is_pre_apply_checkpoint="unknown"
    )
    assert load_review(checkpoint).is_pre_apply_checkpoint is True
    assert load_review(unknown_role).is_pre_apply_checkpoint is None

    for unsafe in (checkpoint, unknown_role):
        for review_id in _pin_forms(unsafe):
            assert (
                resolve_reusable_audit(
                    "demo", tmp_path, plan_path=plan_path, review_id=review_id
                )
                is None
            ), (unsafe.name, review_id)

    # The final report beside them stays pinnable, so the declines are about
    # the role rather than the pin itself.
    pinned_final = resolve_reusable_audit(
        "demo", tmp_path, plan_path=plan_path, review_id=_pin_forms(final)[0]
    )
    assert pinned_final is not None
    assert [r.id for r in pinned_final.saved.recommendations] == ["final"]


def test_resolve_reusable_audit_exposes_saved_audit_coverage(
    tmp_path: Path,
) -> None:
    plan_path = _write_reusable_plan(tmp_path)
    coverage = {
        "budget_limited": True,
        "passes_used": 3,
        "cap": 3,
        "recommendation_kind": None,
        "recommended_passes": None,
        "recommendation_advice": None,
        "confirmation_kind": None,
        "conforming_pass_count": 1,
        "failed_or_malformed_pass_count": 0,
    }
    _save_completeness_sidecar(
        tmp_path,
        plan_path,
        recs=[_rec("a", "plan-correctness")],
        now=_T0,
        audit_coverage=coverage,
    )

    audit = resolve_reusable_audit("demo", tmp_path, plan_path=plan_path)

    assert audit is not None
    assert audit.fresh is True
    assert audit.audit_coverage == {"evidence_status": "observed", **coverage}


def test_resolve_reusable_audit_coverage_less_sidecar_is_fresh_and_unknown(
    tmp_path: Path,
) -> None:
    plan_path = _write_reusable_plan(tmp_path)
    _save_completeness_sidecar(
        tmp_path,
        plan_path,
        recs=[_rec("a", "plan-correctness")],
        now=_T0,
    )

    audit = resolve_reusable_audit("demo", tmp_path, plan_path=plan_path)

    assert audit is not None
    assert audit.fresh is True
    assert audit.audit_coverage == {
        "evidence_status": "unknown-legacy",
        "budget_limited": None,
        "passes_used": None,
        "cap": None,
        "recommendation_kind": None,
        "recommended_passes": None,
        "recommendation_advice": None,
        "confirmation_kind": None,
        "conforming_pass_count": None,
        "failed_or_malformed_pass_count": None,
        "early_stop_reason": None,
    }


def test_resolve_reusable_audit_stale_by_plan(tmp_path: Path) -> None:
    plan_path = _write_reusable_plan(tmp_path)
    _save_completeness_sidecar(
        tmp_path, plan_path, recs=[_rec("a", "plan-correctness")], now=_T0
    )
    # Edit a per-step detail file — flips the plan fingerprint, not the code.
    (tmp_path / "plans" / "plan-details" / "demo" / "01-stub.md").write_text(
        "# detail edited\n", encoding="utf-8"
    )

    audit = resolve_reusable_audit("demo", tmp_path, plan_path=plan_path)

    assert audit is not None
    assert audit.plan_match is False
    assert audit.fresh is False
    assert audit.drifted_code == []


def test_resolve_reusable_audit_stale_by_seed(tmp_path: Path) -> None:
    """A saved report becomes stale when the plan's seed changes, exactly
    like it already does for a plan or code edit (BACKLOG #162 — a seed
    edited after the report was saved must not silently reuse a prompt the
    seed no longer matches)."""
    plan_path = _write_reusable_plan(tmp_path)
    seed_path = tmp_path / "plan-seeds" / "demo.md"
    seed_path.parent.mkdir(parents=True, exist_ok=True)
    seed_path.write_text(
        "# Plan seed: demo\n\n## Outcome\n\nOriginal outcome.\n",
        encoding="utf-8",
    )
    plan_path.write_text(
        plan_path.read_text(encoding="utf-8").replace(
            "status: planning\n",
            "status: planning\nsource_seed: plan-seeds/demo.md\n",
        ),
        encoding="utf-8",
    )
    _save_completeness_sidecar(
        tmp_path, plan_path, recs=[_rec("a", "plan-correctness")], now=_T0
    )

    seed_path.write_text(
        "# Plan seed: demo\n\n## Outcome\n\nChanged outcome.\n",
        encoding="utf-8",
    )

    audit = resolve_reusable_audit("demo", tmp_path, plan_path=plan_path)

    assert audit is not None
    assert audit.plan_match is False
    assert audit.fresh is False


def test_report_writer_keeps_the_audit_time_revision(tmp_path: Path) -> None:
    """A final sidecar keeps sampled bytes even when the plan later changes."""
    from plan_tool.review_persistence import AuditInputSnapshot

    plan_path = _write_reusable_plan(tmp_path)
    snapshot = AuditInputSnapshot.capture(plan_path, tmp_path)
    plan_path.write_text(
        plan_path.read_text(encoding="utf-8").replace("title: Demo", "title: Changed"),
        encoding="utf-8",
    )
    md_path = write_completeness_report(
        plan_path,
        "# report\n",
        repo_root=tmp_path,
        recommendations=[],
        plan_rel_path="plans/1-demo.md",
        qualified_result={
            "headline": "clean",
            "stage": "detail",
            "coverage": "confirmed",
            "revision_status": "current",
            "audit_revision": snapshot.revision,
        },
        audit_stage="detail",
        audit_stage_is_sampled=True,
    )

    saved = load_review(md_path.with_suffix(".json"))
    assert saved.audit_revision == snapshot.revision
    payload = json.loads(md_path.with_suffix(".json").read_text(encoding="utf-8"))
    assert "audit_revision" not in payload


def test_resolve_reusable_audit_stale_by_code(tmp_path: Path) -> None:
    plan_path = _write_reusable_plan(tmp_path)
    _save_completeness_sidecar(
        tmp_path, plan_path, recs=[_rec("a", "plan-correctness")], now=_T0
    )
    (tmp_path / "src" / "foo.py").write_text("foo = 999\n", encoding="utf-8")

    audit = resolve_reusable_audit("demo", tmp_path, plan_path=plan_path)

    assert audit is not None
    assert audit.code_match is False
    assert audit.fresh is True
    assert audit.drifted_code == [(tmp_path / "src" / "foo.py").resolve()]


def test_resolve_reusable_audit_deleted_in_scope_file(tmp_path: Path) -> None:
    plan_path = _write_reusable_plan(tmp_path)
    _save_completeness_sidecar(
        tmp_path, plan_path, recs=[_rec("a", "plan-correctness")], now=_T0
    )
    # Vanished file leaves the fingerprint map → footprint membership, not
    # content drift (and not a reconcile-plan trigger).
    (tmp_path / "src" / "bar.py").unlink()

    audit = resolve_reusable_audit("demo", tmp_path, plan_path=plan_path)

    assert audit is not None
    assert audit.code_match is False
    assert audit.fresh is True
    assert audit.drifted_code == []
    assert audit.footprint_removed == [(tmp_path / "src" / "bar.py").resolve()]


def test_resolve_reusable_audit_new_file_landed(tmp_path: Path) -> None:
    plan_path = _write_reusable_plan(tmp_path, new_entry=True)
    # baz.py absent at capture → skipped from the saved map.
    _save_completeness_sidecar(
        tmp_path, plan_path, recs=[_rec("a", "plan-correctness")], now=_T0
    )
    (tmp_path / "src" / "baz.py").write_text("baz = 3\n", encoding="utf-8")

    audit = resolve_reusable_audit("demo", tmp_path, plan_path=plan_path)

    assert audit is not None
    assert audit.code_match is False
    assert audit.fresh is True
    assert audit.drifted_code == []
    assert audit.footprint_added == [(tmp_path / "src" / "baz.py").resolve()]


def test_resolve_reusable_audit_missing_returns_none(tmp_path: Path) -> None:
    plan_path = _write_reusable_plan(tmp_path)
    assert resolve_reusable_audit("demo", tmp_path, plan_path=plan_path) is None


def test_resolve_reusable_audit_picks_newest_completeness(tmp_path: Path) -> None:
    plan_path = _write_reusable_plan(tmp_path)
    _save_completeness_sidecar(
        tmp_path, plan_path, recs=[_rec("old", "plan-correctness")], now=_T0
    )
    _save_completeness_sidecar(
        tmp_path, plan_path, recs=[_rec("new", "plan-correctness")], now=_T1
    )
    # A newer non-completeness review sidecar must be ignored.
    _save_completeness_sidecar(
        tmp_path, plan_path, recs=[_rec("rev", "plan-correctness")],
        now=_T2, kind="review",
    )

    audit = resolve_reusable_audit("demo", tmp_path, plan_path=plan_path)

    assert audit is not None
    assert [r.id for r in audit.saved.recommendations] == ["new"]


def test_resolve_reusable_audit_pinned_by_id(tmp_path: Path) -> None:
    plan_path = _write_reusable_plan(tmp_path)
    old = _save_completeness_sidecar(
        tmp_path, plan_path, recs=[_rec("old", "plan-correctness")], now=_T0
    )
    _save_completeness_sidecar(
        tmp_path, plan_path, recs=[_rec("new", "plan-correctness")], now=_T1
    )
    full_stem = old.stem  # "<ts>-completeness"
    bare_stem = full_stem[: -len("-completeness")]

    for review_id in (bare_stem, full_stem):
        audit = resolve_reusable_audit(
            "demo", tmp_path, plan_path=plan_path, review_id=review_id
        )
        assert audit is not None
        assert [r.id for r in audit.saved.recommendations] == ["old"]


def test_resolve_reusable_audit_pinned_id_missing_returns_none(
    tmp_path: Path,
) -> None:
    plan_path = _write_reusable_plan(tmp_path)
    _save_completeness_sidecar(
        tmp_path, plan_path, recs=[_rec("a", "plan-correctness")], now=_T0
    )
    assert (
        resolve_reusable_audit(
            "demo", tmp_path, plan_path=plan_path, review_id="20990101-000000"
        )
        is None
    )


def test_resolve_reusable_audit_legacy_sidecar_is_stale(tmp_path: Path) -> None:
    plan_path = _write_reusable_plan(tmp_path)
    _save_completeness_sidecar(
        tmp_path, plan_path, recs=[_rec("a", "plan-correctness")],
        now=_T0, present=False,
    )

    audit = resolve_reusable_audit("demo", tmp_path, plan_path=plan_path)

    assert audit is not None
    assert audit.plan_match is False
    assert audit.code_match is False
    assert audit.fresh is False
    assert audit.drifted_code == []


def test_resolve_reusable_audit_computed_empty_code_fingerprint_reusable(
    tmp_path: Path,
) -> None:
    # Docs-only plan: computed-but-empty code fingerprint (present, empty map).
    plan_path = _write_reusable_plan(tmp_path, docs_only=True)
    _save_completeness_sidecar(
        tmp_path, plan_path, recs=[_rec("a", "plan-completeness")], now=_T0
    )

    audit = resolve_reusable_audit("demo", tmp_path, plan_path=plan_path)

    assert audit is not None
    assert audit.code_match is True
    assert audit.fresh is True
    assert audit.drifted_code == []


def test_resolve_reusable_audit_axis_split(tmp_path: Path) -> None:
    plan_path = _write_reusable_plan(tmp_path)
    recs = [
        _rec("corr", "plan-correctness"),
        _rec("conc", "plan-completeness"),
        _rec("diag", "file-check"),
    ]
    _save_completeness_sidecar(tmp_path, plan_path, recs=recs, now=_T0)

    audit = resolve_reusable_audit("demo", tmp_path, plan_path=plan_path)

    assert audit is not None
    assert [r.id for r in audit.correctness_recs] == ["corr"]
    assert [r.id for r in audit.conceptual_recs] == ["conc"]


# ---------- pending concept decisions ----------

from plan_tool.completeness_report import (  # noqa: E402
    PENDING_DECISION_SOURCES,
    group_pending_decisions,
    pending_concept_id,
)
from plan_tool.review import (  # noqa: E402
    CONCEPT_BUCKET_MISSING_SOURCE,
    CONCEPT_LEGACY_STALE_SOURCE,
    CONCEPT_UNSIGNED_DEFERRAL_SOURCE,
)


def _pending(rec_id: str, source: str, node_id: str):
    return _rec(rec_id, source, "info", anchor=f"concept-{node_id}")


def test_group_pending_decisions_filters_by_source() -> None:
    recs = [
        _pending("u", CONCEPT_UNSIGNED_DEFERRAL_SOURCE, "aaa"),
        _pending("m", CONCEPT_BUCKET_MISSING_SOURCE, "bbb"),
        _rec("s", "feature-ref", "info"),  # a genuine smell, dropped
        _rec("c", "plan-completeness"),  # conceptual, dropped
    ]
    groups = group_pending_decisions(recs)
    kept = {rec.source for g in groups for rec in g.recs}
    assert kept == {
        CONCEPT_UNSIGNED_DEFERRAL_SOURCE,
        CONCEPT_BUCKET_MISSING_SOURCE,
    }
    # Ordered: unsigned deferrals first, then missing-bucket re-reviews.
    assert [g.source for g in groups] == [
        CONCEPT_UNSIGNED_DEFERRAL_SOURCE,
        CONCEPT_BUCKET_MISSING_SOURCE,
    ]


def test_report_splits_pending_decisions_into_own_section() -> None:
    smells = [_pending("u", CONCEPT_UNSIGNED_DEFERRAL_SOURCE, "aaa")]
    md = build_report_md(
        plan_title="T", plan_name="p", iterate_enabled=True,
        stop_reason="marginal", iterations=1, applied=[], deferred=[],
        advisory_conceptual=[], open_findings=[],
        grouped_report_md="G", smells=smells,
    )
    assert "## Pending concept decisions" in md
    # Tagged with the bare concept id (the scope-review --concept token).
    assert "`[aaa]`" in md
    assert "body u" in md


def test_pending_decisions_not_double_rendered_under_smells() -> None:
    smells = [
        _pending("u", CONCEPT_UNSIGNED_DEFERRAL_SOURCE, "aaa"),
        _rec("real", "feature-ref", "info"),
    ]
    md = build_report_md(
        plan_title="T", plan_name="p", iterate_enabled=True,
        stop_reason="marginal", iterations=1, applied=[], deferred=[],
        advisory_conceptual=[], open_findings=[],
        grouped_report_md="G", smells=smells,
    )
    pending_at = md.index("## Pending concept decisions")
    smells_at = md.index("## Smells (advisory)")
    # The genuine smell still renders under ## Smells; the pending rec does not.
    assert "body real" in md[smells_at:]
    assert "body u" in md[pending_at:smells_at]
    assert "body u" not in md[smells_at:]


def test_pending_decisions_grouped_by_bucket() -> None:
    smells = [
        _pending("u", CONCEPT_UNSIGNED_DEFERRAL_SOURCE, "aaa"),
        _pending("m", CONCEPT_BUCKET_MISSING_SOURCE, "bbb"),
    ]
    md = build_report_md(
        plan_title="T", plan_name="p", iterate_enabled=True,
        stop_reason="marginal", iterations=1, applied=[], deferred=[],
        advisory_conceptual=[], open_findings=[],
        grouped_report_md="G", smells=smells,
    )
    assert "Unsigned deferrals" in md
    assert "Missing-bucket re-reviews" in md


def test_disposition_summary_counts_pending_decisions() -> None:
    smells = [
        _pending("u", CONCEPT_UNSIGNED_DEFERRAL_SOURCE, "aaa"),
        _pending("m", CONCEPT_BUCKET_MISSING_SOURCE, "bbb"),
    ]
    md = build_report_md(
        plan_title="T", plan_name="p", iterate_enabled=True,
        stop_reason="marginal", iterations=1, applied=[], deferred=[],
        advisory_conceptual=[], open_findings=[],
        grouped_report_md="G", smells=smells,
    )
    assert "**Pending concept decisions (advisory, not blocking):** 2" in md


def test_report_surfaces_legacy_stale_in_pending_section() -> None:
    # The stale-legacy re-sync advisory must reach the operator in the
    # dedicated pending section, not be buried under ## Smells (advisory).
    smells = [_rec("ls", CONCEPT_LEGACY_STALE_SOURCE, "info",
                   anchor="concept-legacy-stale")]
    md = build_report_md(
        plan_title="T", plan_name="p", iterate_enabled=True,
        stop_reason="marginal", iterations=1, applied=[], deferred=[],
        advisory_conceptual=[], open_findings=[],
        grouped_report_md="G", smells=smells,
    )
    pending_at = md.index("## Pending concept decisions")
    assert "Legacy record" in md[pending_at:]
    assert "body ls" in md[pending_at:]
    assert "## Smells (advisory)" not in md
    # The record-wide advisory has no per-node concept id, so it must NOT be
    # tagged with a bogus `[legacy-stale]` token (stripped from its anchor) that
    # `scope-review --concept legacy-stale` could never resolve.
    assert "[legacy-stale]" not in md


def test_pending_concept_id_strips_anchor_prefix() -> None:
    assert pending_concept_id(_pending("u", CONCEPT_UNSIGNED_DEFERRAL_SOURCE, "xyz")) == "xyz"


def test_pending_concept_id_empty_for_record_wide_legacy_stale() -> None:
    # The legacy-stale advisory is record-wide (anchor literal
    # `concept-legacy-stale`); it carries no `--concept` token, so the helper
    # returns "" rather than the bogus `legacy-stale` a blind prefix-strip yields.
    rec = _rec("ls", CONCEPT_LEGACY_STALE_SOURCE, "info", anchor="concept-legacy-stale")
    assert pending_concept_id(rec) == ""


def test_pending_decision_sources_membership() -> None:
    assert PENDING_DECISION_SOURCES == {
        CONCEPT_UNSIGNED_DEFERRAL_SOURCE,
        CONCEPT_BUCKET_MISSING_SOURCE,
        CONCEPT_LEGACY_STALE_SOURCE,
    }


from plan_tool.completeness_report import (  # noqa: E402
    diagnostic_remedies,
)


def _guidance_args(**overrides):
    base = dict(
        plan_name="demo",
        applied=[],
        deferred=[],
        advisory_conceptual=[],
        open_findings=[],
        verdict=blocking_verdict_from_gate([]),
    )
    base.update(overrides)
    return base


def test_report_default_grade_prose_unchanged() -> None:
    kwargs = dict(
        plan_title="T", plan_name="demo", iterate_enabled=False,
        stop_reason=None, iterations=0, applied=[], deferred=[],
        advisory_conceptual=[_rec("c", "plan-completeness")],
        open_findings=[], grouped_report_md="G",
        correctness=[_rec("k", "plan-correctness")],
    )
    # An explicit run grade and an omitted one render byte-for-byte alike.
    assert build_report_md(**kwargs) == build_report_md(
        **kwargs
    )
    md = build_report_md(**kwargs)
    assert "session-directed edit" in md
    assert "completeness-apply" not in md
    assert WHY["advisory-conceptual"] in md


class TestSuggestedActionRendersInReport:
    """The persisted report must carry each conceptual finding's remediation
    scope. The interactive walk shows ``suggested_action`` labelled "will
    apply"; the hand-applied path the #85 split mandates for a session reads
    this markdown instead, and used to see only the finding body — so fixes
    landed on the cited spot and missed what the action named."""

    def _rec(self, source, action):
        from plan_tool.review import Recommendation

        return Recommendation(
            id=f"x-{source}",
            source=source,
            severity="high",
            step_id=None,
            title="t",
            body="a body",
            suggested_action=action,
            anchor="an-anchor",
        )

    def _md(self, rec, *, correctness):
        from plan_tool.completeness_report import build_report_md

        return build_report_md(
            plan_title="T", plan_name="p", iterate_enabled=True,
            stop_reason="converged", iterations=0, applied=[], deferred=[],
            advisory_conceptual=[] if correctness else [rec],
            open_findings=[], grouped_report_md="G",
            correctness=[rec] if correctness else [],
        )

    def test_correctness_finding_renders_its_suggested_action(self):
        rec = self._rec("plan-correctness", "also add a test proving it")
        assert "also add a test proving it" in self._md(rec, correctness=True)

    def test_completeness_finding_renders_its_suggested_action(self):
        rec = self._rec("plan-completeness", "state the not-load-bearing case")
        assert "state the not-load-bearing case" in self._md(rec, correctness=False)

    def test_finding_without_an_action_renders_no_fix_bullet(self):
        rec = self._rec("plan-correctness", None)
        assert "- Fix:" not in self._md(rec, correctness=True)


class TestRestatedPropertyRendersInReport:
    """A bare-step Correctness finding's ``restated_property`` (the
    ``→ restated:`` marker's plan-altitude restatement) must render beside
    its own quoted citation as delivered evidence, not a verdict -- same
    shape as :class:`TestSuggestedActionRendersInReport`, one axis over."""

    def _rec(self, restated):
        from plan_tool.review import Recommendation

        return Recommendation(
            id="x-plan-correctness",
            source="plan-correctness",
            severity="high",
            step_id=None,
            title="t",
            body="a body",
            anchor="an-anchor",
            restated_property=restated,
        )

    def _md(self, rec):
        from plan_tool.completeness_report import build_report_md

        return build_report_md(
            plan_title="T", plan_name="p", iterate_enabled=True,
            stop_reason="converged", iterations=0, applied=[], deferred=[],
            advisory_conceptual=[], open_findings=[], grouped_report_md="G",
            correctness=[rec],
        )

    def test_correctness_finding_renders_its_restatement(self):
        rec = self._rec("the safety net has no route for a degenerate pick")
        md = self._md(rec)
        assert "the safety net has no route for a degenerate pick" in md
        assert "delivered evidence" in md
        assert "not a verdict" in md

    def test_finding_without_a_restatement_renders_no_restated_bullet(self):
        rec = self._rec(None)
        assert "- Restated" not in self._md(rec)


# ---------- Plan mass (#238) ----------

from plan_tool.completeness_report import (
    PlanMass,
    SoftEdge,
    compute_plan_mass,
    compute_plan_mass_best_effort,
    first_saved_plan_mass,
    plan_mass_to_json,
    render_plan_mass_section,
)
from plan_tool.schema import ChangeType, Priority, PlanStatus, StepStatus


def _mass_plan(steps: list[Step], *, plan_path: Path) -> Plan:
    plan = Plan(
        title="Mass test plan",
        status=PlanStatus.PLANNING,
        priority=Priority.MEDIUM,
        steps=steps,
    )
    return plan


def _write_detail(plan_path: Path, plan: Plan, step: Step, body: str) -> None:
    from plan_tool.detail_artifacts import derive_detail_path

    path = derive_detail_path(plan_path, plan, step)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_compute_plan_mass_single_step_has_no_ratios(tmp_path: Path) -> None:
    plan_path = tmp_path / "1-demo.md"
    plan = _mass_plan([Step(id=1, title="Only step")], plan_path=plan_path)
    mass = compute_plan_mass(plan, plan_path, tmp_path)
    assert mass.step_count == 1
    assert mass.keystone_fan_out is None
    assert mass.satellite_ratio is None
    assert mass.inert_step_ratio is None
    assert mass.audit_induced_growth is None
    assert mass.soft_edges == ()


def test_compute_plan_mass_excludes_parked_steps(tmp_path: Path) -> None:
    from plan_tool.schema import StepScope

    plan_path = tmp_path / "1-demo.md"
    plan = _mass_plan(
        [
            Step(id=1, title="Committed one"),
            Step(id=2, title="Committed two"),
            Step(id=3, title="Parked", scope=StepScope.DEFERRED),
        ],
        plan_path=plan_path,
    )
    mass = compute_plan_mass(plan, plan_path, tmp_path)
    assert mass.step_count == 2


def test_compute_plan_mass_keystone_and_satellite_ratio(tmp_path: Path) -> None:
    plan_path = tmp_path / "1-demo.md"
    plan = _mass_plan(
        [
            Step(id=1, title="Foundation A", change_type=ChangeType.FEATURE),
            Step(id=2, title="Foundation B", change_type=ChangeType.FEATURE),
            Step(
                id=3,
                title="Keystone",
                change_type=ChangeType.FEATURE,
                depends_on=[1, 2],
            ),
        ],
        plan_path=plan_path,
    )
    mass = compute_plan_mass(plan, plan_path, tmp_path)
    # keystone = step 3, fan-out 2 / (3-1) = 1.0
    assert mass.keystone_fan_out == 1.0
    # steps 1 and 2's only dependent is step 3 → both satellites: 2/3
    assert mass.satellite_ratio == 2 / 3


def test_compute_plan_mass_keystone_fan_out_never_exceeds_one(
    tmp_path: Path,
) -> None:
    """A duplicate ``depends_on`` entry (the schema places no uniqueness
    constraint on the list itself) must not inflate fan-out past 1.0 —
    counted as distinct dependencies, not raw list length."""
    plan_path = tmp_path / "1-demo.md"
    s1 = Step(id=1, title="Base", change_type=ChangeType.FEATURE)
    s2 = Step(
        id=2,
        title="Duplicated deps",
        change_type=ChangeType.FEATURE,
        depends_on=[1, 1, 1],
    )
    plan = _mass_plan([s1, s2], plan_path=plan_path)
    mass = compute_plan_mass(plan, plan_path, tmp_path)
    assert mass.keystone_fan_out == 1.0


def test_compute_plan_mass_non_code_step_excluded_as_keystone_candidate(
    tmp_path: Path,
) -> None:
    plan_path = tmp_path / "1-demo.md"
    plan = _mass_plan(
        [
            Step(id=1, title="Real work", change_type=ChangeType.FEATURE),
            Step(id=2, title="Real work two", change_type=ChangeType.FEATURE),
            Step(
                id=3,
                title="Docs wrap-up",
                change_type=ChangeType.NON_CODE,
                depends_on=[1, 2],
            ),
        ],
        plan_path=plan_path,
    )
    mass = compute_plan_mass(plan, plan_path, tmp_path)
    # The non-code step has the highest fan-out but is excluded from keystone
    # candidacy, so neither code step (fan-out 0) can be the keystone either.
    assert mass.keystone_fan_out == 0.0


def test_compute_plan_mass_detail_bundle_bytes_sums_existing_files(
    tmp_path: Path,
) -> None:
    plan_path = tmp_path / "1-demo.md"
    s1 = Step(id=1, title="One")
    s2 = Step(id=2, title="Two")
    plan = _mass_plan([s1, s2], plan_path=plan_path)
    _write_detail(plan_path, plan, s1, "hello")
    # step 2 has no detail file on disk
    mass = compute_plan_mass(plan, plan_path, tmp_path)
    assert mass.detail_bundle_bytes == len("hello".encode("utf-8"))


def test_compute_plan_mass_inert_step_ratio_matches_phrase(tmp_path: Path) -> None:
    plan_path = tmp_path / "1-demo.md"
    s1 = Step(id=1, title="Wiring only")
    s2 = Step(id=2, title="Real change")
    plan = _mass_plan([s1, s2], plan_path=plan_path)
    _write_detail(plan_path, plan, s1, "Nothing renders differently after this.")
    _write_detail(plan_path, plan, s2, "The button now shows a spinner.")
    mass = compute_plan_mass(plan, plan_path, tmp_path)
    assert mass.inert_step_ratio == 0.5


def test_compute_plan_mass_inert_ratio_excludes_non_code_boilerplate(
    tmp_path: Path,
) -> None:
    """A non-code step's auto-inserted Verification boilerplate
    ("...it changes no production code.") must not count as inert padding —
    every non-code step legitimately touches no production code by
    definition, and the phrase list deliberately excludes this exact
    boilerplate (detail.py:_format_tests_directive)."""
    plan_path = tmp_path / "1-demo.md"
    s1 = Step(id=1, title="Real code work", change_type=ChangeType.FEATURE)
    s2 = Step(id=2, title="Docs update", change_type=ChangeType.NON_CODE)
    plan = _mass_plan([s1, s2], plan_path=plan_path)
    _write_detail(plan_path, plan, s1, "The button now shows a spinner.")
    _write_detail(
        plan_path,
        plan,
        s2,
        "\n\n### Verification (non-code step)\n\n"
        "This is a **non-code** step — it changes no production code. "
        "Read the doc for accuracy.",
    )
    mass = compute_plan_mass(plan, plan_path, tmp_path)
    # 0 of 1 *code* step is inert — the non-code step is excluded from both
    # the count and the denominator, not counted as an inert 1-of-2.
    assert mass.inert_step_ratio == 0.0


def test_compute_plan_mass_inert_ratio_none_when_no_code_steps(
    tmp_path: Path,
) -> None:
    plan_path = tmp_path / "1-demo.md"
    plan = _mass_plan(
        [
            Step(id=1, title="Docs one", change_type=ChangeType.NON_CODE),
            Step(id=2, title="Docs two", change_type=ChangeType.NON_CODE),
        ],
        plan_path=plan_path,
    )
    mass = compute_plan_mass(plan, plan_path, tmp_path)
    assert mass.inert_step_ratio is None
    assert mass.keystone_fan_out is None
    assert mass.satellite_ratio is None


def test_compute_plan_mass_unclassified_step_counts_as_code_by_default(
    tmp_path: Path,
) -> None:
    """An unset ``change_type`` (``None``) is treated as a code step by
    explicit default — most unclassified steps in real plans are ordinary
    code steps, not non-code ones (see ``_is_code_step``)."""
    plan_path = tmp_path / "1-demo.md"
    plan = _mass_plan(
        [
            Step(id=1, title="Unclassified base"),
            Step(id=2, title="Unclassified dependent", depends_on=[1]),
        ],
        plan_path=plan_path,
    )
    mass = compute_plan_mass(plan, plan_path, tmp_path)
    # Neither step is explicitly non-code, so both are keystone candidates;
    # step 2 (fan-out 1) wins, matching the explicit code-by-default rule.
    assert mass.keystone_fan_out == 1.0
    assert mass.satellite_ratio == 0.5


def test_compute_plan_mass_soft_edge_detected_from_prose(tmp_path: Path) -> None:
    plan_path = tmp_path / "1-demo.md"
    s1 = Step(id=1, title="Base")
    s2 = Step(id=2, title="Dependent", depends_on=[1])
    plan = _mass_plan([s1, s2], plan_path=plan_path)
    _write_detail(
        plan_path,
        plan,
        s2,
        "This depends on step 1 for ordering-only reasons; no file collision.",
    )
    mass = compute_plan_mass(plan, plan_path, tmp_path)
    assert len(mass.soft_edges) == 1
    edge = mass.soft_edges[0]
    assert edge.step_id == 2
    assert edge.depends_on_id == 1
    assert "ordering-only" in edge.note


def test_compute_plan_mass_soft_edge_requires_dependency_mention(
    tmp_path: Path,
) -> None:
    """A marker phrase with no reference to the depended-on step id/title
    must not be misattributed as a soft edge."""
    plan_path = tmp_path / "1-demo.md"
    s1 = Step(id=1, title="Base")
    s2 = Step(id=2, title="Dependent", depends_on=[1])
    plan = _mass_plan([s1, s2], plan_path=plan_path)
    _write_detail(plan_path, plan, s2, "This is test-only work, unrelated prose.")
    mass = compute_plan_mass(plan, plan_path, tmp_path)
    assert mass.soft_edges == ()


def test_compute_plan_mass_soft_edge_does_not_match_multidigit_step_prefix(
    tmp_path: Path,
) -> None:
    """"step 1" must not match inside "step 12" on a plan with 10+ steps —
    a plain substring check would misattribute the edge (word-boundary
    regression)."""
    steps = [Step(id=i, title=f"Step {i}") for i in range(1, 13)]
    steps[11] = Step(  # step 12: depends on 1, prose mentions "step 12"
        id=12, title="Step twelve", depends_on=[1]
    )
    plan_path = tmp_path / "1-demo.md"
    plan = _mass_plan(steps, plan_path=plan_path)
    _write_detail(
        plan_path,
        plan,
        steps[11],
        "This is ordering-only w.r.t. step 12's own predecessor chain.",
    )
    mass = compute_plan_mass(plan, plan_path, tmp_path)
    assert mass.soft_edges == ()


def test_compute_plan_mass_soft_edge_matches_step_id_at_word_boundary(
    tmp_path: Path,
) -> None:
    steps = [Step(id=i, title=f"Step {i}") for i in range(1, 13)]
    steps[11] = Step(id=12, title="Step twelve", depends_on=[1])
    plan_path = tmp_path / "1-demo.md"
    plan = _mass_plan(steps, plan_path=plan_path)
    _write_detail(
        plan_path,
        plan,
        steps[11],
        "This is ordering-only w.r.t. step 1, no file collision.",
    )
    mass = compute_plan_mass(plan, plan_path, tmp_path)
    assert len(mass.soft_edges) == 1
    assert mass.soft_edges[0].depends_on_id == 1


def test_compute_plan_mass_soft_edge_marker_requires_full_qualifier(
    tmp_path: Path,
) -> None:
    """A genuine hard/content dependency phrased as "...depends on it for
    the behavior of X" must not match the soft-edge marker — only the full
    BACKLOG #238 example phrase ("...the suite observes") does. The bare
    fragment would otherwise flag real dependencies as removable."""
    plan_path = tmp_path / "1-demo.md"
    s1 = Step(id=1, title="Base")
    s2 = Step(id=2, title="Dependent", depends_on=[1])
    plan = _mass_plan([s1, s2], plan_path=plan_path)
    _write_detail(
        plan_path,
        plan,
        s2,
        "Step 2 depends on it for the behavior of the retry loop under load.",
    )
    mass = compute_plan_mass(plan, plan_path, tmp_path)
    assert mass.soft_edges == ()


def test_compute_plan_mass_soft_edge_matches_full_suite_observes_phrase(
    tmp_path: Path,
) -> None:
    plan_path = tmp_path / "1-demo.md"
    s1 = Step(id=1, title="Base")
    s2 = Step(id=2, title="Dependent", depends_on=[1])
    plan = _mass_plan([s1, s2], plan_path=plan_path)
    _write_detail(
        plan_path,
        plan,
        s2,
        "The edge to step 1 depends on it for the behavior the suite observes.",
    )
    mass = compute_plan_mass(plan, plan_path, tmp_path)
    assert len(mass.soft_edges) == 1


def test_compute_plan_mass_tolerates_non_utf8_detail_file(tmp_path: Path) -> None:
    """A non-UTF-8 detail file must degrade that step's body (replacement
    characters), not raise and blank the whole snapshot."""
    plan_path = tmp_path / "1-demo.md"
    s1 = Step(id=1, title="One")
    s2 = Step(id=2, title="Two")
    plan = _mass_plan([s1, s2], plan_path=plan_path)
    from plan_tool.detail_artifacts import derive_detail_path

    path1 = derive_detail_path(plan_path, plan, s1)
    path1.parent.mkdir(parents=True, exist_ok=True)
    path1.write_bytes(b"\xff\xfe not valid utf-8")
    _write_detail(plan_path, plan, s2, "The button now shows a spinner.")
    mass = compute_plan_mass(plan, plan_path, tmp_path)
    assert mass.step_count == 2


def test_compute_plan_mass_audit_induced_growth_reads_provenance(
    tmp_path: Path,
) -> None:
    from plan_tool.telemetry import record_step_provenance

    plan_path = tmp_path / "1-demo.md"
    s1 = Step(id=1, title="Author-written")
    s2 = Step(id=2, title="Split-created half")
    plan = _mass_plan([s1, s2], plan_path=plan_path)
    record_step_provenance(
        tmp_path,
        plan_slug="demo",
        new_step_titles=["Split-created half"],
        mechanism="split",
    )
    mass = compute_plan_mass(plan, plan_path, tmp_path)
    assert mass.audit_induced_growth == 0.5


def test_compute_plan_mass_audit_induced_growth_zero_with_no_provenance(
    tmp_path: Path,
) -> None:
    plan_path = tmp_path / "1-demo.md"
    plan = _mass_plan(
        [Step(id=1, title="One"), Step(id=2, title="Two")], plan_path=plan_path
    )
    mass = compute_plan_mass(plan, plan_path, tmp_path)
    assert mass.audit_induced_growth == 0.0


def test_plan_mass_to_json_serializes_none_ratios_as_none() -> None:
    mass = PlanMass(
        step_count=1,
        detail_bundle_bytes=0,
        keystone_fan_out=None,
        satellite_ratio=None,
        inert_step_ratio=None,
        audit_induced_growth=None,
        soft_edges=(),
    )
    payload = plan_mass_to_json(mass)
    assert payload["keystone_fan_out"] is None
    # asdict() rebuilds ``soft_edges`` as the same container type (a tuple);
    # json.dumps renders either a tuple or a list as a JSON array, so this
    # is a real round-trip through the actual persistence path.
    assert json.loads(json.dumps(payload))["soft_edges"] == []


def test_plan_mass_to_json_serializes_soft_edges_as_dicts() -> None:
    mass = PlanMass(
        step_count=2,
        detail_bundle_bytes=10,
        keystone_fan_out=1.0,
        satellite_ratio=1.0,
        inert_step_ratio=0.0,
        audit_induced_growth=0.0,
        soft_edges=(SoftEdge(step_id=2, depends_on_id=1, note="ordering-only"),),
    )
    payload = plan_mass_to_json(mass)
    assert json.loads(json.dumps(payload))["soft_edges"] == [
        {"step_id": 2, "depends_on_id": 1, "note": "ordering-only"}
    ]


def test_render_plan_mass_section_first_audit_has_no_delta() -> None:
    mass = PlanMass(
        step_count=3,
        detail_bundle_bytes=100,
        keystone_fan_out=0.5,
        satellite_ratio=0.25,
        inert_step_ratio=0.0,
        audit_induced_growth=0.0,
        soft_edges=(),
    )
    section = render_plan_mass_section(
        mass, first_step_count=None, first_detail_bytes=None
    )
    assert "## Plan mass" in section
    assert "(first audit)" in section
    assert "3" in section


def test_render_plan_mass_section_renders_delta_against_first_audit() -> None:
    mass = PlanMass(
        step_count=5,
        detail_bundle_bytes=300,
        keystone_fan_out=None,
        satellite_ratio=None,
        inert_step_ratio=None,
        audit_induced_growth=None,
        soft_edges=(),
    )
    section = render_plan_mass_section(
        mass, first_step_count=3, first_detail_bytes=100
    )
    assert "(+2 vs. first audit)" in section
    assert "(+200 vs. first audit)" in section
    assert "n/a (not computable for this plan)" in section


def test_render_plan_mass_section_lists_soft_edges() -> None:
    mass = PlanMass(
        step_count=2,
        detail_bundle_bytes=10,
        keystone_fan_out=1.0,
        satellite_ratio=1.0,
        inert_step_ratio=0.0,
        audit_induced_growth=0.0,
        soft_edges=(SoftEdge(step_id=2, depends_on_id=1, note="test-only"),),
    )
    section = render_plan_mass_section(
        mass, first_step_count=None, first_detail_bytes=None
    )
    assert "step 2 → step 1" in section
    assert "test-only" in section


def test_build_report_md_includes_plan_mass_section_when_provided() -> None:
    mass = PlanMass(
        step_count=2, detail_bundle_bytes=10, keystone_fan_out=1.0,
        satellite_ratio=1.0, inert_step_ratio=0.0, audit_induced_growth=0.0,
        soft_edges=(),
    )
    md = build_report_md(
        plan_title="T", plan_name="p", iterate_enabled=True,
        stop_reason="converged", iterations=0, applied=[], deferred=[],
        advisory_conceptual=[], open_findings=[], grouped_report_md="G",
        plan_mass=mass,
    )
    assert "## Plan mass" in md


def test_build_report_md_omits_plan_mass_section_when_none() -> None:
    md = build_report_md(
        plan_title="T", plan_name="p", iterate_enabled=True,
        stop_reason="converged", iterations=0, applied=[], deferred=[],
        advisory_conceptual=[], open_findings=[], grouped_report_md="G",
    )
    assert "## Plan mass" not in md


def test_first_saved_plan_mass_returns_earliest_snapshot(tmp_path: Path) -> None:
    plan_path = tmp_path / "1-demo.md"
    plan_path.write_text(
        "---\ntitle: Demo\nstatus: planning\npriority: medium\n"
        "steps:\n  - id: 1\n    title: Step one\n---\n\n# Plan\n",
        encoding="utf-8",
    )
    save_review(
        plan_slug="demo", plan_path="1-demo.md", repo_root=tmp_path,
        report_md="r1", recommendations=[], kind="completeness",
        now=datetime(2026, 1, 1, tzinfo=timezone.utc),
        plan_mass={"step_count": 1, "detail_bundle_bytes": 10},
    )
    save_review(
        plan_slug="demo", plan_path="1-demo.md", repo_root=tmp_path,
        report_md="r2", recommendations=[], kind="completeness",
        now=datetime(2026, 1, 2, tzinfo=timezone.utc),
        plan_mass={"step_count": 3, "detail_bundle_bytes": 40},
    )
    first = first_saved_plan_mass("demo", tmp_path, plan_path)
    assert first == {"step_count": 1, "detail_bundle_bytes": 10}


def test_first_saved_plan_mass_none_when_no_sidecar_carries_it(
    tmp_path: Path,
) -> None:
    plan_path = tmp_path / "1-demo.md"
    plan_path.write_text(
        "---\ntitle: Demo\nstatus: planning\npriority: medium\n"
        "steps:\n  - id: 1\n    title: Step one\n---\n\n# Plan\n",
        encoding="utf-8",
    )
    save_review(
        plan_slug="demo", plan_path="1-demo.md", repo_root=tmp_path,
        report_md="r1", recommendations=[], kind="completeness",
        now=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert first_saved_plan_mass("demo", tmp_path, plan_path) is None


def test_first_saved_plan_mass_skips_pre_apply_checkpoint(tmp_path: Path) -> None:
    plan_path = tmp_path / "1-demo.md"
    plan_path.write_text(
        "---\ntitle: Demo\nstatus: planning\npriority: medium\n"
        "steps:\n  - id: 1\n    title: Step one\n---\n\n# Plan\n",
        encoding="utf-8",
    )
    save_review(
        plan_slug="demo", plan_path="1-demo.md", repo_root=tmp_path,
        report_md="checkpoint", recommendations=[], kind="completeness",
        now=datetime(2026, 1, 1, tzinfo=timezone.utc),
        plan_mass={"step_count": 1, "detail_bundle_bytes": 5},
        is_pre_apply_checkpoint=True,
    )
    save_review(
        plan_slug="demo", plan_path="1-demo.md", repo_root=tmp_path,
        report_md="final", recommendations=[], kind="completeness",
        now=datetime(2026, 1, 2, tzinfo=timezone.utc),
        plan_mass={"step_count": 2, "detail_bundle_bytes": 20},
    )
    first = first_saved_plan_mass("demo", tmp_path, plan_path)
    assert first == {"step_count": 2, "detail_bundle_bytes": 20}


def test_compute_plan_mass_best_effort_returns_snapshot_on_success(
    tmp_path: Path,
) -> None:
    plan_path = tmp_path / "1-demo.md"
    plan = _mass_plan(
        [Step(id=1, title="One"), Step(id=2, title="Two")], plan_path=plan_path
    )
    mass = compute_plan_mass_best_effort(plan, plan_path, tmp_path)
    assert mass is not None
    assert mass.step_count == 2


def test_compute_plan_mass_best_effort_swallows_ordinary_internal_failure(
    tmp_path: Path,
) -> None:
    """The single shared failure policy every #238 CLI call site relies
    on: a raising ``plan`` (or any other internal failure) returns ``None``
    rather than propagating."""
    broken_plan = SimpleNamespace(steps=None)  # iterating .steps raises
    plan_path = tmp_path / "1-demo.md"
    assert compute_plan_mass_best_effort(broken_plan, plan_path, tmp_path) is None


def test_mass_detail_read_refuses_an_unsupported_detail_marker(
    tmp_path: Path,
) -> None:
    from plan_tool.detail_artifacts import (
        DetailFormatError,
        render_detail_format_version_marker,
    )

    plan_path = tmp_path / "1-demo.md"
    plan = _mass_plan(
        [Step(id=1, title="One"), Step(id=2, title="Two")], plan_path=plan_path
    )
    _write_detail(
        plan_path, plan, plan.steps[0],
        f"# Step 1\n{render_detail_format_version_marker(999)}\n\nfine.\n",
    )
    with pytest.raises(DetailFormatError):
        compute_plan_mass(plan, plan_path, tmp_path)


def test_plan_mass_wrapper_propagates_detail_format_error(
    tmp_path: Path,
) -> None:
    """``compute_plan_mass_best_effort`` re-raises a format refusal while
    still returning ``None`` for a missing/unreadable detail file (the
    ordinary best-effort case above)."""
    from plan_tool.detail_artifacts import (
        DetailFormatError,
        render_detail_format_version_marker,
    )

    plan_path = tmp_path / "1-demo.md"
    plan = _mass_plan(
        [Step(id=1, title="One"), Step(id=2, title="Two")], plan_path=plan_path
    )
    _write_detail(
        plan_path, plan, plan.steps[0],
        f"# Step 1\n{render_detail_format_version_marker(999)}\n\nfine.\n",
    )
    with pytest.raises(DetailFormatError):
        compute_plan_mass_best_effort(plan, plan_path, tmp_path)


# ---------- blocking verdict (next-step readers) ----------

from plan_tool.completeness_report import (  # noqa: E402
    BLOCKING_STATE_ABSENT,
    BLOCKING_STATE_INCOMPLETE,
    BLOCKING_STATE_SET,
    UNTRUSTED_PERSISTENT,
    UNTRUSTED_STALE_REVISION,
    UNTRUSTED_TRANSIENT,
    BlockingVerdict,
    blocking_verdict_from_gate,
)

_STAGE_MARKERS = (
    "no plan-level gaps remain",
    "No gaps left",
    "No structural gaps left",
    "plan-tool run ",
    "plan-tool jira ",
    "plan-tool detail ",
)


def _all_reader_output(
    verdict, *, is_bare=False, advisory=(), correctness=(),
    deferred=(),
):
    bundle = SimpleNamespace(is_bare=is_bare)
    advisory = list(advisory)
    correctness = list(correctness)
    steps = suggested_next_steps(
        plan_name="p", iterate_enabled=False, applied=[], deferred=list(deferred),
        advisory_conceptual=advisory, open_findings=[], bundle_status=bundle,
         verdict=verdict, correctness=correctness,
    )
    cmds = suggested_next_step_commands(
        plan_name="p", applied=[], deferred=list(deferred),
        advisory_conceptual=advisory,
        open_findings=[], bundle_status=bundle,
        verdict=verdict, correctness=correctness,
    )
    stage = next_stage_command("p", bundle, verdict=verdict)
    summary = console_summary(
        plan_name="p", iterate_enabled=False, stop_reason=None, iterations=0,
        applied=[], deferred=[], advisory_conceptual=advisory,
        open_findings=[], report_path=Path("r.md"), bundle_status=bundle,
        verdict=verdict, correctness=correctness,
    )
    return {"steps": steps, "cmds": cmds, "stage": stage, "summary": summary}


def _offers_stage(out: dict) -> bool:
    text = "\n".join(
        [*out["steps"], *(c for c, _ in out["cmds"]), out["stage"][0],
         out["summary"]]
    )
    return any(m in text for m in _STAGE_MARKERS)


_EMPTY_SET = blocking_verdict_from_gate([])


def test_empty_set_verdict_offers_stage_transition_at_run_grade() -> None:
    out = _all_reader_output(_EMPTY_SET)
    assert out["stage"][0] == "plan-tool run p"
    assert any("No gaps left" in s for s in out["steps"])


def test_empty_set_verdict_on_bare_plan_offers_detail_authoring() -> None:
    out = _all_reader_output(_EMPTY_SET, is_bare=True)
    assert out["stage"][0] == "plan-tool detail p"


@pytest.mark.parametrize("is_bare", [True, False])
def test_nonempty_set_verdict_never_says_no_gaps_remain( is_bare) -> None:
    out = _all_reader_output(
        blocking_verdict_from_gate(["a", "b"]), is_bare=is_bare
    )
    assert not _offers_stage(out)
    assert out["stage"][0].startswith("plan-tool completeness-audit p")


def test_nonempty_set_verdict_ends_command_list_with_reaudit() -> None:
    out = _all_reader_output(blocking_verdict_from_gate(["a"]))
    assert out["cmds"][-1][0].startswith("plan-tool completeness-audit p")
    assert out["steps"][-1].startswith("`plan-tool completeness-audit p")


def test_blocking_deterministic_finding_is_named_by_source_without_a_conceptual_id() -> None:
    verdict = blocking_verdict_from_gate([], [_rec("i", "intent", "medium")])
    out = _all_reader_output(verdict)
    assert any("`intent`" in s for s in out["steps"])
    assert not _offers_stage(out)
    assert "blocking  1 gap(s)" in out["summary"]


def test_absent_verdict_is_not_read_as_empty_set() -> None:
    """A missing verdict must never read as 'nothing blocks'."""
    out = _all_reader_output(BlockingVerdict(BLOCKING_STATE_ABSENT))
    assert not _offers_stage(out)
    assert "verdict unavailable" in out["summary"]


def test_omitted_verdict_reads_as_absent_and_offers_no_stage() -> None:
    """An omitted verdict must never read as 'nothing blocks' — it is absent."""
    bundle = SimpleNamespace(is_bare=False)
    assert next_stage_command("p", bundle)[0] == (
        "plan-tool completeness-audit p --iterate"
    )
    steps = suggested_next_steps(
        plan_name="p", iterate_enabled=False, applied=[], deferred=[],
        advisory_conceptual=[], open_findings=[], bundle_status=bundle,
    )
    assert not any("No gaps left" in s for s in steps)
    assert "verdict unavailable" in console_summary(
        plan_name="p", iterate_enabled=False, stop_reason=None, iterations=0,
        applied=[], deferred=[], advisory_conceptual=[], open_findings=[],
        report_path=Path("r.md"),
    )


def test_incomplete_verdict_is_not_read_as_empty_set() -> None:
    out = _all_reader_output(BlockingVerdict(BLOCKING_STATE_INCOMPLETE))
    assert not _offers_stage(out)
    # An incomplete verdict is named as such, never as "0 gap(s)" (a clear set)
    # and never as an unavailable one.
    assert "blocking  verdict incomplete" in out["summary"]
    assert "0 gap(s)" not in out["summary"]
    assert "verdict unavailable" not in out["summary"]


def test_advisory_gaps_are_listed_but_hold_back_no_stage() -> None:
    out = _all_reader_output(_EMPTY_SET, advisory=[_rec("adv", "plan-completeness")])
    assert out["stage"][0] == "plan-tool run p"
    _assert_advisory_rows_offer_only_the_stage(out)


def _assert_advisory_rows_offer_only_the_stage(out: dict) -> None:
    """Advisory gaps are listed, never phrased as 'close … then re-audit', and
    the one next command is the stage in every reader."""
    stage = out["stage"][0]
    assert not stage.startswith("plan-tool completeness-audit")
    assert any("1 conceptual gap(s)" in s for s in out["steps"])
    assert not any(s.startswith("Close ") for s in out["steps"])
    assert not any("completeness-audit" in s for s in out["steps"])
    assert out["cmds"][-1][0] == stage
    assert f"`{stage}`" in out["steps"][-1]
    assert not [c for c, _ in out["cmds"] if "completeness-audit" in c]


@pytest.mark.parametrize("is_bare", [True, False])
@pytest.mark.parametrize(
    "verdict,expect_stage",
    [
        (_EMPTY_SET, True),
        (blocking_verdict_from_gate(["x"]), False),
        (blocking_verdict_from_gate([], [_rec("d", "intent")]), False),
        (BlockingVerdict(BLOCKING_STATE_INCOMPLETE), False),
        (BlockingVerdict(BLOCKING_STATE_ABSENT), False),
        (None, False),
    ],
)
def test_four_readers_agree_on_blocking_state(
    verdict, expect_stage, is_bare
) -> None:
    out = _all_reader_output(verdict, is_bare=is_bare)
    assert _offers_stage(out) is expect_stage
    stage_cmd = out["stage"][0]
    assert stage_cmd.startswith("plan-tool completeness-audit") is not expect_stage


def test_verdict_wraps_gate_ids_without_refiltering() -> None:
    verdict = blocking_verdict_from_gate(["z", "a", "a"])
    assert verdict.state == BLOCKING_STATE_SET
    assert verdict.blocking_ids == ("z", "a", "a")


# One shared predicate per row: a stage transition or "no gaps" phrase
# (``_offers_stage``) plus the blocking count the console summary names. The
# table asserts agreement on those, not on each reader's wording.
_CORRECTNESS_GAP = _rec("plan-correctness-high", "plan-correctness", "high")
_COMPLETENESS_GAP = _rec("plan-completeness-high", "plan-completeness", "high")
_ADVISORY_GAP = _rec("adv", "plan-completeness", "medium")
_DETERMINISTIC_GAP = _rec("det", "intent", "medium")

# kind -> (verdict, correctness, advisory, blocking count or None, offers stage)
_AGREEMENT_KINDS = {
    "blocking-correctness": (
        blocking_verdict_from_gate(["plan-correctness-high"]),
        [_CORRECTNESS_GAP], [], 1, False,
    ),
    "blocking-completeness": (
        blocking_verdict_from_gate(["plan-completeness-high"]),
        [], [_COMPLETENESS_GAP], 1, False,
    ),
    "blocking-deterministic-no-conceptual-id": (
        blocking_verdict_from_gate([], [_DETERMINISTIC_GAP]),
        [], [], 1, False,
    ),
    "advisory-only-empty-set": (
        blocking_verdict_from_gate([]), [], [_ADVISORY_GAP], 0, True,
    ),
    "empty-set": (blocking_verdict_from_gate([]), [], [], 0, True),
    "incomplete": (
        BlockingVerdict(BLOCKING_STATE_INCOMPLETE), [], [], None, False,
    ),
    # An incomplete verdict keeps the ids the audit computed (amendment 1).
    "incomplete-transient-keeps-correctness-id": (
        blocking_verdict_from_gate(
            ["plan-correctness-high"], untrusted_cause=UNTRUSTED_TRANSIENT
        ),
        [_CORRECTNESS_GAP], [], 1, False,
    ),
    "incomplete-persistent-keeps-correctness-id": (
        blocking_verdict_from_gate(
            ["plan-correctness-high"], untrusted_cause=UNTRUSTED_PERSISTENT
        ),
        [_CORRECTNESS_GAP], [], 1, False,
    ),
    "incomplete-persistent-nothing-listed": (
        blocking_verdict_from_gate([], untrusted_cause=UNTRUSTED_PERSISTENT),
        [], [], None, False,
    ),
    "absent": (BlockingVerdict(BLOCKING_STATE_ABSENT), [], [], None, False),
}

# Readers take only ``bundle_status.is_bare``; step-less and partially detailed
# plans are where a reader deriving its own stage once disagreed with
# ``derive_audit_stage``, so both ``is_bare`` readings are tried for partial.
_AGREEMENT_STAGES = {
    "step-less": True,
    "bare": True,
    "partially-detailed-reads-bare": True,
    "partially-detailed-reads-detailed": False,
    "detailed": False,
}


@pytest.mark.parametrize("stage,is_bare", list(_AGREEMENT_STAGES.items()))
@pytest.mark.parametrize("kind", list(_AGREEMENT_KINDS))
def test_four_readers_agree_across_stage_grade_finding_kind_and_verdict(
    kind, stage, is_bare
) -> None:
    verdict, correctness, advisory, blocking_count, offers = _AGREEMENT_KINDS[kind]
    out = _all_reader_output(
        verdict, is_bare=is_bare,
        correctness=correctness, advisory=advisory,
    )
    assert _offers_stage(out) is offers
    assert out["stage"][0].startswith("plan-tool completeness-audit") is not offers
    next_cmd = out["stage"][0]
    # One next command, the same in every reader, and at most one re-audit row.
    assert out["cmds"][-1][0] == next_cmd
    assert f"`{next_cmd}`" in out["steps"][-1]
    assert len([c for c, _ in out["cmds"] if c.startswith("plan-tool completeness-audit p")]) == (0 if offers else 1)
    if not offers:
        # Every non-clear state ends both command lists with the re-audit; the
        # run lane always iterates, the jira lane never does.
        assert next_cmd == (
            "plan-tool completeness-audit p --iterate"
        )
    else:
        assert not [c for c, _ in out["cmds"] if "completeness-audit" in c]
    if blocking_count is None and kind == "absent":
        assert "verdict unavailable" in out["summary"]
    elif blocking_count is None:
        # An incomplete verdict is named as incomplete, not as unavailable and
        # not as a countable (clear-looking) set.
        assert "blocking  verdict incomplete" in out["summary"]
        assert "verdict unavailable" not in out["summary"]
    else:
        assert f"blocking  {blocking_count} gap(s)" in out["summary"]


def test_integration_bare_plan_blocking_correctness_gap_does_not_offer_detail() -> None:
    """The Integration shape: a bare plan whose blocking correctness gap used to print
    "no plan-level gaps remain — author the detail bundle"."""
    out = _all_reader_output(
        blocking_verdict_from_gate(["plan-correctness-high"]),
        is_bare=True,
        correctness=[_CORRECTNESS_GAP],
    )
    assert not _offers_stage(out)
    assert not any("plan-tool detail" in c for c, _ in out["cmds"])
    assert any(s.startswith("Close 1 conceptual-correctness") for s in out["steps"])
    assert out["cmds"][-1][0] == "plan-tool completeness-audit p --iterate"
    assert "blocking  1 gap(s)" in out["summary"]


def test_blocking_completeness_gap_on_bare_plan_is_counted_though_its_action_is_demoted() -> None:
    """Completeness gaps are informational on a bare plan, but the blocking
    fact is not: the verdict still names it and withholds the stage."""
    out = _all_reader_output(
        blocking_verdict_from_gate(["plan-completeness-high"]),
        is_bare=True,
        advisory=[_COMPLETENESS_GAP],
    )
    assert not _offers_stage(out)
    assert any(s.startswith("Close 1 conceptual-completeness") for s in out["steps"])
    assert "blocking  1 gap(s)" in out["summary"]


def test_advisory_only_findings_are_listed_without_any_blocking_line() -> None:
    out = _all_reader_output(
        blocking_verdict_from_gate([]), advisory=[_ADVISORY_GAP]
    )
    assert out["stage"][0] == "plan-tool run p"
    _assert_advisory_rows_offer_only_the_stage(out)
    assert "blocking  0 gap(s)" in out["summary"]
    assert "advisory  1 conceptual gap(s)" in out["summary"]


def test_advisory_only_gaps_are_listed_and_the_stage_is_still_offered() -> None:
    """A completed empty set with an advisory correctness gap lists the gap and
    still offers the next stage: advisory gaps hold back no stage."""
    steps = _steps(
        correctness=[_rec("pc", "plan-correctness", "low")],
        bundle_status=SimpleNamespace(is_bare=True),
        verdict=_EMPTY_SET,
    )
    assert any("plan-tool detail p" in step for step in steps)
    # The gap is listed, so no step may also claim there are none.
    assert not any("No gaps left" in step for step in steps)


def test_unqualified_result_reaudit_carries_the_grade_and_names_deterministic_blockers(
) -> None:
    from plan_tool.completeness_report import BlockingVerdict

    verdict = BlockingVerdict(
        state="incomplete",
        blocking_deterministic=(_rec("sc", "intent", "medium"),),
    )
    unqualified = {"headline": "no-qualified-current-evidence", "coverage": "unconfirmed"}
    steps = _steps(verdict=verdict, qualified_result=unqualified)
    cmds = _cmds(verdict=verdict, qualified_result=unqualified)
    expected = (
        "plan-tool completeness-audit p --iterate"
    )
    assert any("blocking `intent` finding" in step for step in steps)
    assert any(f"`{expected}`" in step for step in steps)
    assert [c for c, _ in cmds] == [expected]


def test_console_summary_counts_only_blocking_correctness_as_fix_first(tmp_path) -> None:
    from plan_tool.completeness_report import BlockingVerdict

    summary = console_summary(
        plan_name="p", iterate_enabled=True, stop_reason="converged", iterations=1,
        applied=[], deferred=[], advisory_conceptual=[], open_findings=[],
        report_path=tmp_path / "r.md",
        correctness=[_rec("a", "plan-correctness", "high"), _rec("b", "plan-correctness", "low")],
        verdict=BlockingVerdict(state="set", blocking_ids=("a",)),
    )
    assert "correctness 1 conceptual gap(s) — fix these first" in summary
    assert "advisory  1 conceptual gap(s)" in summary


_FILES_COHERENCE = _rec("fc", "files-coherence", "info", suggested_action="add path")


def test_files_coherence_hand_edit_preserves_the_existing_stage_suggestion() -> None:
    """Manual diagnostic remedies preserve the completed empty verdict's stage."""
    out = _all_reader_output(_EMPTY_SET, deferred=[_FILES_COHERENCE])
    assert [c for c, _ in out["cmds"]] == [
        "plan-tool run p",
    ]
    assert "`plan-tool run p`" in out["steps"][-1]


@pytest.mark.parametrize("state", ["incomplete", "absent"])
def test_untrusted_verdict_with_nothing_listed_says_no_verdict_and_never_close(
    state
) -> None:
    """Nothing is listed to close, so no step may tell the operator to close
    anything; the only offer is the one re-audit, in the audit's grade."""
    out = _all_reader_output(BlockingVerdict(state))
    assert not any(s.startswith("Close ") for s in out["steps"])
    reaudit = out["stage"][0]
    assert [c for c, _ in out["cmds"]] == [reaudit]
    assert reaudit == (
        "plan-tool completeness-audit p --iterate"
    )
    assert len([s for s in out["steps"] if "completeness-audit" in s]) == 1


def test_console_list_keeps_exactly_one_reaudit_row_in_the_stronger_form() -> None:
    """A concept-link row, an unreached-findings row, and the verdict re-audit
    collapse to one row: ``--iterate`` at run grade, ``--grade jira`` at jira."""
    cmds = _cmds(
        deferred=[_rec("cv", "concept-coverage", "medium")],
        open_findings=[_rec("o", "plan-correctness", "high")],
        verdict=blocking_verdict_from_gate(["x"]),
    )
    rows = [c for c, _ in cmds if c.startswith("plan-tool completeness-audit p")]
    assert rows == [
        "plan-tool completeness-audit p --iterate"
    ]


def test_deterministic_blocker_is_named_when_the_verdict_is_untrusted() -> None:
    verdict = BlockingVerdict(
        "incomplete", blocking_deterministic=(_rec("sc", "intent", "medium"),)
    )
    out = _all_reader_output(verdict)
    assert any("`intent`" in s for s in out["steps"])
    assert [c for c, _ in out["cmds"]] == ["plan-tool completeness-audit p --iterate"]


@pytest.mark.parametrize("is_bare", [True, False])
@pytest.mark.parametrize("cause", [UNTRUSTED_TRANSIENT, UNTRUSTED_PERSISTENT])
def test_incomplete_verdict_still_reads_fix_these_first_and_never_advisory(
    cause, is_bare
) -> None:
    """Amendment 1: a HIGH correctness gap from a cut-short run is a gap to
    close in every reader, not an advisory listing."""
    out = _all_reader_output(
        blocking_verdict_from_gate(["plan-correctness-high"], untrusted_cause=cause),
        is_bare=is_bare, correctness=[_CORRECTNESS_GAP],
    )
    assert any(s.startswith("Close 1 conceptual") for s in out["steps"])
    assert not any("advisory (outside the blocking set)" in s for s in out["steps"])
    assert "advisory  " not in out["summary"]
    assert "correctness 1 conceptual gap(s)" in out["summary"]


def test_persistent_cause_prescribes_triage_where_transient_prescribes_the_plain_reaudit(
) -> None:
    """Amendment 3: the cause is carried on the verdict and read only by the
    shared next-command function. A persistent cause's one next step is hand
    triage then the re-audit; a transient cause keeps the plain re-audit. The
    command is identical, so there is still exactly one next command."""
    outs = {
        cause: _all_reader_output(
            blocking_verdict_from_gate(["x"], untrusted_cause=cause)
        )
        for cause in (UNTRUSTED_TRANSIENT, UNTRUSTED_PERSISTENT)
    }
    transient, persistent = (outs[UNTRUSTED_TRANSIENT], outs[UNTRUSTED_PERSISTENT])
    assert transient["stage"][0] == persistent["stage"][0]
    assert transient["stage"][1] != persistent["stage"][1]
    for out in outs.values():
        # Every reader's closing row reuses the shared description verbatim.
        assert out["cmds"][-1] == out["stage"]
        assert out["stage"][1] in out["steps"][-1]
        assert out["steps"][-1].count("completeness-audit p") == 1


def test_merged_reaudit_row_is_built_at_the_source_and_keeps_every_reason() -> None:
    """Amendment 9: concept-link, unreached-findings, and the verdict reasons
    merge into the one ``_reaudit_command`` row, blocking count included."""
    from plan_tool.completeness_report import _reaudit_command

    verdict = blocking_verdict_from_gate(["x"])
    reasons = [
        "assign or structurally defer 1 concept(s)",
        "1 finding(s) not reached by the loop",
    ]
    cmds = _cmds(
        deferred=[_rec("cv", "concept-coverage", "medium")],
        open_findings=[_rec("o", "plan-correctness", "high")],
        verdict=verdict,
    )
    rows = [row for row in cmds if row[0].startswith("plan-tool completeness-audit p")]
    expected = _reaudit_command("p", verdict, also=reasons)
    pass
    assert rows == [expected]
    description = rows[0][1]
    assert "1 blocking gap(s)" in description
    assert reasons[0] in description
    assert reasons[1] in description


@pytest.mark.parametrize(
    "required",
    ["blocked", "concept-link", "diagnostic", "open-findings"],
)
def test_advisory_wording_never_follows_a_required_step(required) -> None:
    """Amendment 4: 'advisory, hold back no stage' follows only advisory rows.
    After a BLOCKED split, a concept-link assignment, or a diagnostic remedy
    the closing row is the bare stage row."""
    kw = {
        "blocked": dict(applied=[AppliedOutcome(
            rec=_rec("a", "plan-correctness", "medium", step_id=1),
            verdict="BLOCKED", summary="needs a new step",
        )]),
        "concept-link": dict(deferred=[_rec("cv", "concept-coverage", "medium")]),
        "diagnostic": dict(deferred=[_rec(
            "ls", "lessons-coverage", "high", suggested_action="z"
        )]),
        "open-findings": dict(open_findings=[_rec("o", "plan-correctness", "high")]),
    }[required]
    bundle = SimpleNamespace(is_bare=False)
    steps = _steps(
        verdict=_EMPTY_SET, advisory_conceptual=[_ADVISORY_GAP],
        bundle_status=bundle, **kw,
    )
    command, description = next_stage_command("p", bundle, verdict=_EMPTY_SET)
    assert steps[-1] == f"`{command}` — {description}."
    advisory_only = _steps(
        verdict=_EMPTY_SET, advisory_conceptual=[_ADVISORY_GAP], bundle_status=bundle
    )
    assert advisory_only[-1] != f"`{command}` — {description}."
    assert advisory_only[-1].endswith(f"`{command}` — {description}.")


def test_deterministic_blocker_covered_by_a_diagnostic_remedy_is_listed_once() -> None:
    """Amendment 5: a blocker whose source a diagnostic remedy already covers
    gets no second 'close directly' step; an uncovered one still does."""
    covered = _rec("dc", "detail-coverage", "high", suggested_action="y")
    uncovered = _rec("sc", "intent", "medium")
    verdict = blocking_verdict_from_gate([], [covered, uncovered])
    steps = _steps(verdict=verdict, deferred=[covered])
    direct = [s for s in steps if s.startswith("Close the blocking")]
    assert len(direct) == 1
    assert "`intent`" in direct[0]
    assert not any("`detail-coverage`" in s for s in direct)


def test_deterministic_steps_skip_only_the_covered_sources() -> None:
    from plan_tool.completeness_report import _blocking_deterministic_steps

    a, b = _rec("a", "deps", "medium"), _rec("b", "intent", "medium")
    verdict = blocking_verdict_from_gate([], [a, b])
    assert len(_blocking_deterministic_steps(verdict)) == 2
    only = _blocking_deterministic_steps(verdict, covered_sources={"deps"})
    assert len(only) == 1 and "`intent`" in only[0]


def test_reaudit_command_stale_revision_names_fresh_audit_not_triage() -> None:
    """Changed text gets a fresh-audit answer; "reproduces"/"triage" would be
    false for it. The command per grade is unchanged."""
    from plan_tool.completeness_report import _reaudit_command

    verdict = blocking_verdict_from_gate(
        ["plan-correctness-high"], untrusted_cause=UNTRUSTED_STALE_REVISION
    )
    command, reason = _reaudit_command("p", verdict)
    assert command == "plan-tool completeness-audit p --iterate"
    assert "fresh audit" in reason
    assert "reproduces" not in reason and "triage" not in reason


def test_reaudit_command_transient_and_persistent_texts_unchanged() -> None:
    from plan_tool.completeness_report import _reaudit_command

    _, transient = _reaudit_command(
        "p", blocking_verdict_from_gate([], untrusted_cause=UNTRUSTED_TRANSIENT)
    )
    _, persistent = _reaudit_command(
        "p", blocking_verdict_from_gate([], untrusted_cause=UNTRUSTED_PERSISTENT)
    )
    assert transient == "the audit stopped early — re-audit to continue"
    assert "re-auditing unchanged text reproduces this result" in persistent
    assert "triage the saved report's findings" in persistent


def test_next_step_gaps_stale_revision_lists_no_close_conceptual_gaps_but_keeps_deterministic() -> None:
    """Changed text: conceptual ids are advisory; deterministic blockers close."""
    from plan_tool.completeness_report import next_step_gaps

    det = _rec("det", "deps", "medium")
    verdict = blocking_verdict_from_gate(
        ["plan-correctness-high"], [det], untrusted_cause=UNTRUSTED_STALE_REVISION
    )
    listed = _rec("plan-correctness-high", "plan-correctness", "high")
    gaps = next_step_gaps(verdict, correctness=[listed])
    assert gaps.close_conceptual_count == 0
    assert gaps.unlisted_blocking == 0
    assert [r.id for r in gaps.advisory_correctness] == ["plan-correctness-high"]
    assert [r.id for r in gaps.close_deterministic] == ["det"]


@pytest.mark.parametrize(
    "cause", [UNTRUSTED_TRANSIENT, UNTRUSTED_PERSISTENT, UNTRUSTED_STALE_REVISION]
)
def test_every_reader_agrees_on_gap_count_and_command_for_incomplete_verdict(
    cause,
) -> None:
    """Report prose, console block, and summary all draw the count and the one
    re-audit command from the verdict, whatever the untrusted cause."""
    verdict = blocking_verdict_from_gate(["a", "b"], untrusted_cause=cause)
    out = _all_reader_output(verdict)
    command, _why = out["stage"]
    assert command == "plan-tool completeness-audit p --iterate"
    assert not _offers_stage(out)
    assert out["cmds"][-1][0] == command
    assert f"`{command}`" in out["steps"][-1]
    if cause == UNTRUSTED_STALE_REVISION:
        # Ids describing changed text are advisory: they are not counted.
        assert "blocking  2 gap(s)" not in out["summary"]
        assert "blocking  verdict incomplete: no current audit evidence" in out["summary"]
    else:
        assert "blocking  2 gap(s)" in out["summary"]
        assert "verdict incomplete: " in out["summary"]
        assert cause not in out["summary"]  # internal enum names stay internal


def test_stale_revision_verdict_does_not_list_saved_gaps_as_text_to_close() -> None:
    """Stale-revision ids describe changed text: the prose and the console
    count them as advisory, never as gaps to close."""
    rec = _rec("a", "plan-correctness", "high")
    out = _all_reader_output(
        blocking_verdict_from_gate(["a"], untrusted_cause=UNTRUSTED_STALE_REVISION),
        correctness=[rec],
    )
    assert "  correctness " not in out["summary"]
    assert "  advisory  1 conceptual gap(s)" in out["summary"]
    assert not any("Close the" in step for step in out["steps"])


def test_synthetic_arm_findings_are_named_as_failing_checks_not_counted_gaps() -> None:
    """Deliberate: an issue-object arm contributes one synthetic finding that
    names a failing check; counting it as "1 gap" would misstate five issues,
    so it is reported separately and a lone arm never reads as a cleared set."""
    from plan_tool.completeness_report import DeterministicArmFinding

    arm = DeterministicArmFinding(
        id="deterministic-deps", source="deps", severity="medium",
        step_id=None, title="5 blocking deps finding(s)", body="",
    )
    # Marked by type, not by id: a real finding whose id merely looks like an
    # arm's is still a counted gap.
    lookalike = _rec("deterministic-deps", "intent", "medium")
    real = _rec("det", "intent", "medium")
    assert blocking_verdict_from_gate([], [lookalike]).blocking_arm_count == 0
    verdict = blocking_verdict_from_gate(["plan-correctness-high"], [arm, real])
    assert verdict.blocking_arm_count == 1
    assert verdict.blocking_count == 2  # the id plus the one real finding
    out = _all_reader_output(verdict)
    assert "blocking  2 gap(s) + 1 deterministic check(s) failing" in out["summary"]
    lone = _all_reader_output(blocking_verdict_from_gate([], [arm]))
    assert "blocking  1 deterministic check(s) failing" in lone["summary"]
    assert "0 gap(s)" not in lone["summary"]


def test_stale_demoted_gaps_read_as_unverified_not_as_non_blocking() -> None:
    """Deliberate: ids a stale-revision verdict demotes were blocking and are
    unverified against current text, so the advisory line never calls them
    "outside the blocking set" -- with or without retained ids."""
    for ids in (["plan-correctness-high"], []):
        verdict = blocking_verdict_from_gate(ids, untrusted_cause=UNTRUSTED_STALE_REVISION)
        out = _all_reader_output(
            verdict,
            correctness=[_CORRECTNESS_GAP],
        )
        assert "not verified against the current text" in out["summary"]
        assert not any("outside the blocking set" in s for s in out["steps"])
    ordinary = _all_reader_output(
        blocking_verdict_from_gate([]), advisory=[_ADVISORY_GAP]
    )
    assert "outside the blocking set" in ordinary["summary"]


@pytest.mark.parametrize("damage", ["jira", "malformed"])
def test_resolve_reusable_audit_rejects_retired_or_malformed_revision_without_fallback(tmp_path, damage):
    plan_path = _write_reusable_plan(tmp_path)
    _save_completeness_sidecar(
        tmp_path, plan_path, recs=[], now=_T0.replace(year=_T0.year - 1)
    )
    sidecar = _save_completeness_sidecar(tmp_path, plan_path, recs=[], now=_T0)
    payload = json.loads(sidecar.read_text())
    revision = dict(payload["audit_revision"])
    if damage == "jira":
        revision["detail_grade"] = "jira"
    else:
        revision.pop("details")
    payload["audit_revision"] = revision
    sidecar.write_text(json.dumps(payload))
    archived_bytes = sidecar.read_bytes()
    audit = resolve_reusable_audit("demo", tmp_path, plan_path=plan_path)
    assert audit is None or not audit.fresh
    assert sidecar.read_bytes() == archived_bytes


@pytest.mark.parametrize("boundary", ["plan", "detail", "seed", "project-context", "code"])
def test_reusable_audit_preserves_each_input_freshness_boundary(tmp_path, monkeypatch, boundary):
    from plan_tool import project_profile

    plan_path = _write_reusable_plan(tmp_path)
    seed = tmp_path / "seed.md"
    seed.write_text("# Seed\n")
    plan_path.write_text(plan_path.read_text().replace("status: planning", "source_seed: seed.md\nstatus: planning"))
    monkeypatch.setattr(project_profile, "project_profile_context", lambda root: "context")
    _save_completeness_sidecar(tmp_path, plan_path, recs=[], now=_T0)
    if boundary == "project-context":
        monkeypatch.setattr(project_profile, "project_profile_context", lambda root: "changed context")
    else:
        path = {
            "plan": plan_path,
            "detail": tmp_path / "plans/plan-details/demo/01-stub.md",
            "seed": seed,
            "code": tmp_path / "src/foo.py",
        }[boundary]
        path.write_text(path.read_text() + "\n# changed\n")
    audit = resolve_reusable_audit("demo", tmp_path, plan_path=plan_path)
    assert audit is not None
    # Code remains live explanation context, separate from prompt-input identity.
    assert audit.fresh is (boundary == "code")
    assert audit.code_match is (boundary != "code")


def test_reaudit_command_keeps_iterate_for_the_only_supported_bundle():
    from plan_tool.completeness_report import _reaudit_command, ABSENT_BLOCKING_VERDICT

    assert _reaudit_command("p", ABSENT_BLOCKING_VERDICT)[0] == "plan-tool completeness-audit p --iterate"


@pytest.mark.parametrize("bare", [True, False])
def test_report_next_steps_never_emit_retired_grade_commands(bare):
    bundle = SimpleNamespace(is_bare=bare)
    commands = _cmds(bundle_status=bundle, verdict=_EMPTY_SET)
    prose = _steps(bundle_status=bundle, verdict=_EMPTY_SET)
    expected = "plan-tool detail p" if bare else "plan-tool run p"
    assert commands[-1][0] == expected
    assert expected in prose[-1]
    assert all("--grade" not in c for c, _ in commands)
    assert all("jira-grade" not in line and "--grade" not in line for line in prose)


def test_write_report_preserves_markdown_and_qualified_sidecar_replacement_guards(tmp_path, monkeypatch):
    import os
    from plan_tool.review_persistence import AuditInputSnapshot, load_review

    plan_path = tmp_path / "1-demo.md"
    _write_minimal_plan(plan_path)
    revision = AuditInputSnapshot.capture(plan_path, tmp_path).revision
    replaced = []
    real_replace = os.replace

    def replace(source, destination):
        replaced.append(Path(destination))
        return real_replace(source, destination)

    monkeypatch.setattr(os, "replace", replace)
    report = write_completeness_report(
        plan_path, "# Qualified report\n", repo_root=tmp_path, recommendations=[],
        plan_rel_path=plan_path.name, qualified_result={
            "headline": "clean", "stage": "bare", "coverage": "confirmed",
            "revision_status": "current", "audit_revision": revision,
        },
    )
    assert report in replaced and report.with_suffix(".json") in replaced
    assert load_review(report.with_suffix(".json")).qualified_result["headline"] == "clean"
    with pytest.raises(ValueError, match="qualified_result is not a valid completeness result"):
        write_completeness_report(
            plan_path, "# Unqualified report\n", repo_root=tmp_path, recommendations=[],
            plan_rel_path=plan_path.name, qualified_result={"headline": "clean"},
        )
    assert load_review(report.with_suffix(".json")).qualified_result["headline"] == "clean"
    assert len(list(report.parent.glob("*.json"))) == 1


def test_files_coherence_remedy_requires_reviewing_the_citation_and_scope() -> None:
    from plan_tool.completeness_report import diagnostic_remedies

    remedy = " ".join(diagnostic_remedies([
        _rec("real", "files-coherence", "info", suggested_action="add real.py"),
        _rec("typo", "files-coherence", "info", suggested_action="fix typo.py"),
    ], "p"))
    assert "Inspect each cited path" in remedy
    assert "hand-edit the detail citation" in remedy
    assert "`files:`/`allowed_mentions:`" in remedy
    assert "does not establish step scope or justify an exemption" in remedy
    assert "correct typo citations" in remedy
    assert "completeness-apply" not in remedy


def test_files_coherence_hand_edit_never_becomes_a_command_tuple() -> None:
    assert _cmds(deferred=[_FILES_COHERENCE]) == _cmds()


def test_empty_embedded_correctness_has_no_dangling_section_reference() -> None:
    out = _render_grouped_report(
        SimpleNamespace(title="Demo"), SimpleNamespace(name="demo"),
        _DeterministicReport(None, [], [], [], [], [], []),
        correctness_recs=[], conceptual_recs=[], audit_recs=[],
        iterate_enabled=False, embedded=True,
    )
    assert "see the dedicated section above" not in out
    assert "none — paths resolve, deps coherent, concepts sound" in out
