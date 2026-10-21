"""Unit tests for the split-criteria catalog and legend renderer.

No Claude — the autouse conftest gate must never fire. Each drift-guard test
asserts a rendered token equals the value imported from its owning module, so a
re-typed literal in the renderer fails the suite.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from plan_tool import distill_thresholds, granularity, split_criteria, split_safety, telemetry
from plan_tool.review_persistence import compute_plan_fingerprint, save_review
from plan_tool.schema import ChangeType, Plan, Step, StepStatus
from plan_tool.scope_out import compute_narrow
from plan_tool.cli.app import build_parser, main
from plan_tool.cli.split_criteria_cmd import cmd_split_criteria, register
from plan_tool.split_criteria import (
    SPLIT_CRITERIA,
    CriteriaDrift,
    CriterionResult,
    PlanCriteriaBreakdown,
    SplitCriterion,
    SplitSafetyGate,
    compute_criteria_drift,
    evaluate_split_criteria,
    render_plan_breakdown,
    render_split_criteria,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]

_ANSI_RE = re.compile(r"\033\[")

_CATALOG_IDS = {c.id for c in SPLIT_CRITERIA}


# --- per-plan evaluator fixtures -------------------------------------------

_PLAN_REL = "docs/implementation-plans/1-demo.md"


def _plan(*steps: Step) -> Plan:
    return Plan(title="Demo", status="planning", priority="medium", steps=list(steps))


def _plan_path(tmp_path: Path) -> Path:
    """An absolute plan path under ``tmp_path`` whose slug is ``demo``.

    The file need not exist — ``load_report_history`` reads only the derived
    reports dir, and the detail-bundle glob tolerates an absent directory.
    """
    return tmp_path / _PLAN_REL


def _result(breakdown: PlanCriteriaBreakdown, criterion_id: str) -> CriterionResult:
    return next(r for r in breakdown.results if r.criterion_id == criterion_id)


def _dt(day: int) -> datetime:
    return datetime(2026, 6, day, 9, 0, 0, tzinfo=timezone.utc)


def test_render_split_criteria_returns_string():
    text = render_split_criteria()
    assert isinstance(text, str)
    assert text.strip()


def test_legend_covers_all_three_altitudes():
    text = render_split_criteria().lower()
    assert "altitude 1" in text
    assert "altitude 2" in text
    assert "altitude 3" in text


def test_catalog_ids_unique():
    ids = [c.id for c in SPLIT_CRITERIA]
    assert len(ids) == len(set(ids))


def test_catalog_entries_are_frozen_descriptors():
    assert SPLIT_CRITERIA
    assert all(isinstance(c, SplitCriterion) for c in SPLIT_CRITERIA)


def test_catalog_reuses_granularity_predicate_slugs():
    altitude_2_split_ids = {
        c.id
        for c in SPLIT_CRITERIA
        if c.altitude == 2 and c.source == granularity.GRANULARITY_SPLIT_SOURCE
    }
    assert granularity.SPLIT_PREDICATE_MIXED_VERBS in altitude_2_split_ids
    assert granularity.SPLIT_PREDICATE_CONJOINED_CLAUSES in altitude_2_split_ids
    assert granularity.SPLIT_PREDICATE_UNRELATED_AREAS in altitude_2_split_ids


def test_legend_renders_distill_thresholds_from_source():
    text = render_split_criteria()
    assert str(distill_thresholds.DISTILL_SKIP_BELOW_BYTES) in text
    assert str(distill_thresholds.DISTILL_ADVISE_ABOVE_BYTES) in text


def test_altitude_one_guidance_distinguishes_inline_thresholds_from_direct_assessment():
    text = render_split_criteria()
    result = split_criteria._altitude1_result(_distill_criterion())

    assert "inline only" in text
    assert "file-backed direct sources assess raw text at every size" in text
    assert "raw source at every size" in result.reason


def test_legend_renders_verb_lexicons_from_source():
    text = render_split_criteria()
    for verb in granularity._REFACTOR_VERBS | granularity._FEATURE_VERBS:
        assert verb in text, verb


def test_legend_renders_trivial_refactor_max_files_from_source():
    text = render_split_criteria()
    assert str(granularity._TRIVIAL_REFACTOR_MAX_FILES) in text


def test_legend_renders_test_top_dirs_from_source():
    text = render_split_criteria()
    for top_dir in granularity._TEST_TOP_DIRS:
        assert top_dir in text, top_dir


def test_legend_renders_remedy_vocabulary():
    text = render_split_criteria()
    for remedy in ("re-split", "scope-out", "merge", "re-seed"):
        assert remedy in text, remedy


def test_control_flow_criteria_present_but_unpinned():
    # The multi-area / mixed-step / split-safe / scope-out-blocked criteria
    # render as prose: assert their descriptions appear; do not assert a number.
    text = render_split_criteria()
    for criterion_id in (
        granularity.SPLIT_PREDICATE_UNRELATED_AREAS,
        granularity.SPLIT_PREDICATE_MIXED_STEP,
        "split-safe",
        "scope-out-blocked",
    ):
        criterion = next(c for c in SPLIT_CRITERIA if c.id == criterion_id)
        assert criterion.description in text


def test_legend_plain_when_color_off_colored_when_on():
    plain = render_split_criteria(color=False)
    colored = render_split_criteria(color=True)
    assert not _ANSI_RE.search(plain)
    assert _ANSI_RE.search(colored)


def test_catalog_has_split_safe_and_scope_out_blocked_ids():
    merge = next(
        (c for c in SPLIT_CRITERIA if c.source == granularity.GRANULARITY_MERGE_SOURCE),
        None,
    )
    assert merge is not None
    assert merge.remedy == "merge"

    for gate_id in ("split-safe", "scope-out-blocked"):
        gate = next((c for c in SPLIT_CRITERIA if c.id == gate_id), None)
        assert gate is not None, gate_id
        assert gate.altitude == 3
        assert gate.deterministic is True

    # The single placeholder id is fully replaced by the two run-state signals.
    assert all(c.id != "split-safety" for c in SPLIT_CRITERIA)


def test_legend_names_both_split_safety_signals():
    text = render_split_criteria()
    assert "split-safe" in text
    assert "scope-out-blocked" in text


def test_mixed_step_criterion_marked_deterministic():
    mixed_step = next(
        (c for c in SPLIT_CRITERIA if c.id == granularity.SPLIT_PREDICATE_MIXED_STEP),
        None,
    )
    assert mixed_step is not None
    assert mixed_step.deterministic is True


def test_altitude_1_distill_marked_non_deterministic():
    distill = next((c for c in SPLIT_CRITERIA if c.altitude == 1), None)
    assert distill is not None
    assert distill.deterministic is False


# --- altitude 1 plan-mass citation (#238) -----------------------------------


def _distill_criterion() -> SplitCriterion:
    return next(c for c in SPLIT_CRITERIA if c.altitude == 1)


def test_altitude1_result_omits_plan_mass_citation_by_default():
    result = split_criteria._altitude1_result(_distill_criterion())
    assert result.evaluated is False
    assert "current plan:" not in result.reason


def test_altitude1_result_cites_plan_mass_numbers_when_provided():
    from plan_tool.completeness_report import PlanMass

    mass = PlanMass(
        step_count=7,
        detail_bundle_bytes=1234,
        keystone_fan_out=0.5,
        satellite_ratio=0.25,
        inert_step_ratio=0.0,
        audit_induced_growth=0.0,
        soft_edges=(),
    )
    result = split_criteria._altitude1_result(_distill_criterion(), mass)
    # Citing the current numbers must not turn this into a live evaluation —
    # it is still Claude-judged on the seed, not a threshold comparison.
    assert result.evaluated is False
    assert result.fired is False
    assert "7 committed step" in result.reason
    assert "1234 detail-bundle byte" in result.reason
    assert "informational only" in result.reason


def test_evaluate_split_criteria_altitude1_cites_current_plan_mass(
    tmp_path: Path,
):
    plan = _plan(
        Step(id=1, title="First step", files=["a.py"]),
        Step(id=2, title="Second step", files=["b.py"], depends_on=[1]),
    )
    breakdown = evaluate_split_criteria(plan, plan_path=_plan_path(tmp_path))
    distill = _result(breakdown, "distill-oversize")
    assert distill.evaluated is False
    assert "2 committed step" in distill.reason


# --- per-plan evaluator: altitude 2 (granularity) --------------------------


def test_evaluate_maps_mixed_verbs_split_to_catalog_id(tmp_path: Path):
    plan = _plan(
        Step(id=1, title="Refactor parser to add validation", files=["plan_tool/parser.py"])
    )
    breakdown = evaluate_split_criteria(plan, plan_path=_plan_path(tmp_path))
    result = _result(breakdown, granularity.SPLIT_PREDICATE_MIXED_VERBS)
    assert result.fired
    assert result.step_ids == (1,)
    assert result.altitude == 2


def test_evaluate_maps_conjoined_clauses_and_multi_area(tmp_path: Path):
    plan = _plan(
        Step(id=1, title="Add login and wire the handler", files=["plan_tool/auth.py"]),
        Step(id=2, title="Add adapters", files=["plan_tool/a.py", "svc/b.py"]),
    )
    breakdown = evaluate_split_criteria(plan, plan_path=_plan_path(tmp_path))
    two_clauses = _result(breakdown, granularity.SPLIT_PREDICATE_CONJOINED_CLAUSES)
    multi_area = _result(breakdown, granularity.SPLIT_PREDICATE_UNRELATED_AREAS)
    assert two_clauses.fired and two_clauses.step_ids == (1,)
    assert multi_area.fired and multi_area.step_ids == (2,)


def test_evaluate_maps_merge_source_to_merge_criterion(tmp_path: Path):
    plan = _plan(
        Step(id=1, title="Add part one", files=["plan_tool/auth.py"]),
        Step(id=2, title="Add part two", files=["plan_tool/auth.py"], depends_on=[1]),
    )
    breakdown = evaluate_split_criteria(plan, plan_path=_plan_path(tmp_path))
    merge = _result(breakdown, "merge")
    assert merge.fired
    assert merge.step_ids == (1,)


def test_evaluate_surfaces_mixed_step_from_detail_bodies(tmp_path: Path):
    plan = _plan(
        Step(
            id=1,
            title="Add the widget",
            files=["plan_tool/widget.py"],
            change_type=ChangeType.FEATURE,
        )
    )
    plan_path = _plan_path(tmp_path)
    bundle = plan_path.parent / "plan-details" / "demo"
    bundle.mkdir(parents=True)
    (bundle / "01-add-the-widget.md").write_text(
        "## Summary\n\nBody.\n\n"
        "## Structural findings\n"
        "- MIXED-STEP: bundles a behavior-preserving refactor with new behavior.\n",
        encoding="utf-8",
    )
    breakdown = evaluate_split_criteria(plan, plan_path=plan_path)
    mixed_step = _result(breakdown, granularity.SPLIT_PREDICATE_MIXED_STEP)
    # The invoker is never called: the evaluator hardwires ``invoker=None`` and
    # ``assess_granularity`` regex-lifts the block, so the autouse real-backend
    # conftest gate stays silent.
    assert mixed_step.fired
    assert mixed_step.step_ids == (1,)


def test_evaluate_no_detail_bodies_mixed_step_not_fired(tmp_path: Path):
    plan = _plan(Step(id=1, title="Add login", files=["plan_tool/auth.py"]))
    breakdown = evaluate_split_criteria(plan, plan_path=_plan_path(tmp_path))
    mixed_step = _result(breakdown, granularity.SPLIT_PREDICATE_MIXED_STEP)
    assert mixed_step.evaluated
    assert not mixed_step.fired


# --- per-plan evaluator: altitude 1 + invariants ---------------------------


def test_evaluate_altitude1_marked_not_evaluated(tmp_path: Path):
    plan = _plan(Step(id=1, title="Add login", files=["plan_tool/auth.py"]))
    breakdown = evaluate_split_criteria(plan, plan_path=_plan_path(tmp_path))
    distill = next(r for r in breakdown.results if r.altitude == 1)
    assert distill.evaluated is False
    assert distill.fired is False
    assert str(distill_thresholds.DISTILL_SKIP_BELOW_BYTES) in distill.reason
    assert str(distill_thresholds.DISTILL_ADVISE_ABOVE_BYTES) in distill.reason


def test_evaluate_every_result_id_is_a_catalog_id(tmp_path: Path):
    plan = _plan(
        Step(id=1, title="Refactor parser to add validation", files=["plan_tool/parser.py"]),
        Step(id=2, title="Add adapters", files=["plan_tool/a.py", "svc/b.py"]),
    )
    breakdown = evaluate_split_criteria(plan, plan_path=_plan_path(tmp_path))
    assert breakdown.results
    for result in breakdown.results:
        assert result.criterion_id in _CATALOG_IDS


# --- per-plan evaluator: telemetry write + drift diff (step 5) --------------


def _breakdown_events(repo_root: Path) -> list[telemetry.DecisionEvent]:
    return [
        e
        for e in telemetry.read_decisions(repo_root)
        if e.kind == telemetry.PLAN_CRITERIA_BREAKDOWN_KIND
    ]


def test_evaluator_records_plan_criteria_breakdown(tmp_path: Path):
    plan = _plan(
        Step(id=1, title="Refactor parser to add validation", files=["plan_tool/parser.py"])
    )
    breakdown = evaluate_split_criteria(plan, plan_path=_plan_path(tmp_path), repo_root=tmp_path)
    events = _breakdown_events(tmp_path)
    assert len(events) == 1
    ctx = events[0].context
    ids = {row["id"] for row in ctx["criteria"]}
    assert granularity.SPLIT_PREDICATE_MIXED_VERBS in ids  # the fires? results
    assert ctx["criteria_count"] == len(ctx["criteria"])
    assert ctx["fired_count"] == sum(1 for r in breakdown.results if r.fired)


def test_recorded_event_carries_plan_fingerprint(tmp_path: Path):
    plan = _plan(Step(id=1, title="Add login", files=["plan_tool/auth.py"]))
    plan_path = _plan_path(tmp_path)
    evaluate_split_criteria(plan, plan_path=plan_path, repo_root=tmp_path)
    event = _breakdown_events(tmp_path)[0]
    assert event.context["plan_fingerprint"] == compute_plan_fingerprint(plan_path)


def test_recorded_results_are_primitives(tmp_path: Path):
    plan = _plan(
        Step(id=1, title="Refactor parser to add validation", files=["plan_tool/parser.py"])
    )
    evaluate_split_criteria(plan, plan_path=_plan_path(tmp_path), repo_root=tmp_path)
    rows = _breakdown_events(tmp_path)[0].context["criteria"]
    assert rows
    for row in rows:
        assert isinstance(row, dict)
        assert isinstance(row["id"], str)
        assert isinstance(row["fired"], bool)
        assert row["severity"] is None or isinstance(row["severity"], str)
        assert isinstance(row["step_ids"], list)
        assert all(isinstance(s, str) for s in row["step_ids"])


def test_split_criteria_refuses_an_unsupported_detail_marker(tmp_path: Path):
    from plan_tool.detail_artifacts import (
        DetailFormatError,
        render_detail_format_version_marker,
    )

    plan = _plan(
        Step(id=1, title="Refactor parser to add validation", files=["plan_tool/parser.py"])
    )
    plan_path = _plan_path(tmp_path)
    bundle_dir = plan_path.parent / "plan-details" / "demo"
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "01-refactor.md").write_text(
        f"# Step 1\n{render_detail_format_version_marker(999)}\n\nfine.\n",
        encoding="utf-8",
    )
    with pytest.raises(DetailFormatError):
        evaluate_split_criteria(plan, plan_path=plan_path, repo_root=tmp_path)


def test_code_fingerprint_recorded_when_present(tmp_path: Path):
    code_fingerprint = {"plan_tool/x.py": "deadbeef"}
    save_review(
        plan_slug="demo",
        plan_path=_PLAN_REL,
        repo_root=tmp_path,
        report_md="report\n",
        recommendations=[],
        annotations=None,
        now=_dt(1),
        kind="detail-reconcile",
        step_id=1,
        code_fingerprint=code_fingerprint,
    )
    plan = _plan(Step(id=1, title="Add login", files=["plan_tool/auth.py"]))
    evaluate_split_criteria(plan, plan_path=_plan_path(tmp_path), repo_root=tmp_path)
    event = _breakdown_events(tmp_path)[0]
    # code_fingerprint is base-homed only (never copied into context).
    assert event.code_fingerprint == telemetry.code_fingerprint_digest(
        code_fingerprint
    )
    assert "code_fingerprint" not in event.context


def test_code_fingerprint_omitted_when_not_computed(tmp_path: Path):
    # A saved report that never computed a code fingerprint (present == False).
    save_review(
        plan_slug="demo",
        plan_path=_PLAN_REL,
        repo_root=tmp_path,
        report_md="report\n",
        recommendations=[],
        annotations=None,
        now=_dt(1),
        kind="detail-reconcile",
        step_id=1,
        code_fingerprint=None,
    )
    plan = _plan(Step(id=1, title="Add login", files=["plan_tool/auth.py"]))
    evaluate_split_criteria(plan, plan_path=_plan_path(tmp_path), repo_root=tmp_path)
    event = _breakdown_events(tmp_path)[0]
    assert "code_fingerprint" not in event.context


def test_code_fingerprint_omitted_when_no_report(tmp_path: Path):
    plan = _plan(Step(id=1, title="Add login", files=["plan_tool/auth.py"]))
    evaluate_split_criteria(plan, plan_path=_plan_path(tmp_path), repo_root=tmp_path)
    event = _breakdown_events(tmp_path)[0]
    assert "code_fingerprint" not in event.context


def test_evaluator_reads_before_recording(tmp_path: Path):
    plan_path = _plan_path(tmp_path)
    # A prior evaluation of a differently-shaped plan (distinct fingerprint).
    telemetry.record_plan_criteria_breakdown(
        tmp_path,
        plan_slug="demo",
        plan_fingerprint="OLD-FINGERPRINT",
        criteria=[
            {
                "id": granularity.SPLIT_PREDICATE_MIXED_VERBS,
                "fired": True,
                "severity": "medium",
                "step_ids": [1],
            }
        ],
    )
    plan = _plan(Step(id=1, title="Add login", files=["plan_tool/auth.py"]))
    breakdown = evaluate_split_criteria(plan, plan_path=plan_path, repo_root=tmp_path)
    # Exactly one new event; the diff picked the seeded prior, never this run's
    # own just-written event (whose fingerprint is the current one).
    assert len(_breakdown_events(tmp_path)) == 2
    assert breakdown.drift.has_prior
    assert breakdown.drift.prior_fingerprint == "OLD-FINGERPRINT"
    assert breakdown.drift.prior_fingerprint != compute_plan_fingerprint(plan_path)


def test_drift_note_when_fingerprint_and_results_change(tmp_path: Path):
    telemetry.record_plan_criteria_breakdown(
        tmp_path,
        plan_slug="demo",
        plan_fingerprint="OLD-FINGERPRINT",
        criteria=[
            {"id": "merge", "fired": True, "severity": "medium", "step_ids": [1]},
            {
                "id": granularity.SPLIT_PREDICATE_MIXED_VERBS,
                "fired": False,
                "severity": None,
                "step_ids": [],
            },
        ],
    )
    plan = _plan(
        Step(id=1, title="Refactor parser to add validation", files=["plan_tool/parser.py"])
    )
    breakdown = evaluate_split_criteria(plan, plan_path=_plan_path(tmp_path), repo_root=tmp_path)
    drift = breakdown.drift
    assert drift.changed
    assert granularity.SPLIT_PREDICATE_MIXED_VERBS in drift.newly_firing
    assert "merge" in drift.stopped_firing


def test_no_drift_when_no_prior_different_fingerprint(tmp_path: Path):
    plan_path = _plan_path(tmp_path)
    fingerprint = compute_plan_fingerprint(plan_path)
    # Only same-fingerprint history — nothing structurally different to diff.
    telemetry.record_plan_criteria_breakdown(
        tmp_path,
        plan_slug="demo",
        plan_fingerprint=fingerprint,
        criteria=[{"id": "merge", "fired": True, "severity": "medium", "step_ids": [1]}],
    )
    plan = _plan(Step(id=1, title="Add login", files=["plan_tool/auth.py"]))
    breakdown = evaluate_split_criteria(plan, plan_path=plan_path, repo_root=tmp_path)
    assert breakdown.drift.has_prior is False
    assert "Decomposition drift" not in render_plan_breakdown(breakdown)


def test_no_drift_when_results_unchanged(tmp_path: Path):
    plan_path = _plan_path(tmp_path)
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan = _plan(
        Step(id=1, title="Refactor parser to add validation", files=["plan_tool/parser.py"])
    )
    # Two runs whose plan bytes differ (distinct fingerprint) but whose steps —
    # and thus fires? results — are identical.
    plan_path.write_text("# plan v1\n", encoding="utf-8")
    evaluate_split_criteria(plan, plan_path=plan_path, repo_root=tmp_path)
    plan_path.write_text("# plan v2 — reshaped bytes, same steps\n", encoding="utf-8")
    breakdown = evaluate_split_criteria(plan, plan_path=plan_path, repo_root=tmp_path)
    assert breakdown.drift.has_prior  # the fingerprint moved
    assert breakdown.drift.changed is False
    assert "Decomposition drift" not in render_plan_breakdown(breakdown)


def test_drift_excludes_split_safety_gate(tmp_path: Path):
    plan_path = _plan_path(tmp_path)
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    pending = _plan(
        Step(id=1, title="Add one", files=["plan_tool/a.py"]),
        Step(id=2, title="Add two", files=["plan_tool/b.py"], depends_on=[1]),
    )
    plan_path.write_text("# plan v1\n", encoding="utf-8")
    before = evaluate_split_criteria(pending, plan_path=plan_path, repo_root=tmp_path)
    # Flip only run state: a downstream DONE step makes step 1 un-split-safe.
    started = _plan(
        Step(id=1, title="Add one", files=["plan_tool/a.py"]),
        Step(id=2, title="Add two", files=["plan_tool/b.py"], depends_on=[1], status=StepStatus.DONE),
    )
    plan_path.write_text("# plan v2\n", encoding="utf-8")
    after = evaluate_split_criteria(started, plan_path=plan_path, repo_root=tmp_path)
    assert _gate(before, 1).split_safe != _gate(after, 1).split_safe  # gate flipped
    # ...but the drift diff saw none of it: fires? results are unchanged and no
    # run-state gate id leaks into the diff.
    assert after.drift.changed is False
    moved = (
        set(after.drift.newly_firing)
        | set(after.drift.stopped_firing)
        | set(after.drift.severity_changed)
    )
    assert not (moved & {"split-safe", "scope-out-blocked"})


def test_telemetry_failure_never_breaks_evaluate(tmp_path: Path):
    # A regular file cannot hold the telemetry dir: the record + read both fail
    # and are swallowed — the evaluator still returns its breakdown.
    bad_root = tmp_path / "not-a-dir"
    bad_root.write_text("i am a file\n", encoding="utf-8")
    plan = _plan(Step(id=1, title="Add login", files=["plan_tool/auth.py"]))
    breakdown = evaluate_split_criteria(plan, plan_path=_plan_path(tmp_path), repo_root=bad_root)
    assert breakdown.results


def test_compute_criteria_drift_no_matching_history():
    drift = compute_criteria_drift(
        [], current_results=[], current_fingerprint="F", plan_slug="demo"
    )
    assert isinstance(drift, CriteriaDrift)
    assert drift.has_prior is False
    assert drift.changed is False


def test_render_plan_breakdown_shows_drift_plain(tmp_path: Path):
    telemetry.record_plan_criteria_breakdown(
        tmp_path,
        plan_slug="demo",
        plan_fingerprint="OLD-FINGERPRINT",
        criteria=[{"id": "merge", "fired": True, "severity": "medium", "step_ids": [1]}],
    )
    plan = _plan(
        Step(id=1, title="Refactor parser to add validation", files=["plan_tool/parser.py"])
    )
    breakdown = evaluate_split_criteria(plan, plan_path=_plan_path(tmp_path), repo_root=tmp_path)
    text = render_plan_breakdown(breakdown, color=False)
    assert not _ANSI_RE.search(text)
    note = text[text.index("Decomposition drift"):]
    assert "newly firing" in note
    assert granularity.SPLIT_PREDICATE_MIXED_VERBS in note
    assert "stopped firing" in note


def test_evaluate_now_covers_split_safety(tmp_path: Path):
    plan = _plan(
        Step(id=1, title="Add login", files=["plan_tool/auth.py"]),
        Step(id=2, title="Add logout", files=["plan_tool/auth.py"]),
    )
    breakdown = evaluate_split_criteria(plan, plan_path=_plan_path(tmp_path))
    # The gates are a separate structure; split-safety is no longer a fires? row.
    assert all(
        r.criterion_id not in ("split-safe", "scope-out-blocked")
        for r in breakdown.results
    )
    assert tuple(g.step_id for g in breakdown.gates) == (1, 2)
    assert all(isinstance(g, SplitSafetyGate) for g in breakdown.gates)


# --- run-state split-safety gates (step 4) ---------------------------------


def _gate(breakdown: PlanCriteriaBreakdown, step_id: int) -> SplitSafetyGate:
    return next(g for g in breakdown.gates if g.step_id == step_id)


def test_split_safe_true_when_all_steps_pending(tmp_path: Path):
    plan = _plan(
        Step(id=1, title="Add one", files=["plan_tool/a.py"]),
        Step(id=2, title="Add two", files=["plan_tool/b.py"]),
    )
    breakdown = evaluate_split_criteria(plan, plan_path=_plan_path(tmp_path))
    for step_id in (1, 2):
        gate = _gate(breakdown, step_id)
        assert gate.split_safe
        assert gate.split_blocking == ()


def test_split_safe_false_when_downstream_started(tmp_path: Path):
    plan = _plan(
        Step(id=1, title="Add one", files=["plan_tool/a.py"]),
        Step(id=2, title="Add two", files=["plan_tool/b.py"], status=StepStatus.DONE),
    )
    breakdown = evaluate_split_criteria(plan, plan_path=_plan_path(tmp_path))
    gate = _gate(breakdown, 1)
    assert not gate.split_safe
    assert gate.split_blocking == (2,)


def test_scope_out_blocked_on_inbound_dependent(tmp_path: Path):
    plan = _plan(
        Step(id=1, title="Add one", files=["plan_tool/a.py"]),
        Step(id=2, title="Add two", files=["plan_tool/b.py"], depends_on=[1]),
    )
    breakdown = evaluate_split_criteria(plan, plan_path=_plan_path(tmp_path))
    gate = _gate(breakdown, 1)
    assert gate.scope_out_blocked
    assert "inbound-dependent" in gate.scope_out_blocker_kinds


def test_scope_out_blocked_on_downstream_orphan(tmp_path: Path):
    plan = _plan(
        Step(id=1, title="Add one", files=["plan_tool/a.py"]),
        Step(id=2, title="Add two", files=["plan_tool/b.py"], status=StepStatus.DONE),
    )
    breakdown = evaluate_split_criteria(plan, plan_path=_plan_path(tmp_path))
    gate = _gate(breakdown, 1)
    assert gate.scope_out_blocked
    assert "downstream-orphan" in gate.scope_out_blocker_kinds


def test_split_safe_and_scope_out_are_independent(tmp_path: Path):
    # Step 1 has an inbound dependent (scope-out blocked) but no started
    # downstream work (split-safe) — the two signals disagree.
    plan = _plan(
        Step(id=1, title="Add one", files=["plan_tool/a.py"]),
        Step(id=2, title="Add two", files=["plan_tool/b.py"], depends_on=[1]),
    )
    breakdown = evaluate_split_criteria(plan, plan_path=_plan_path(tmp_path))
    gate = _gate(breakdown, 1)
    assert gate.split_safe
    assert gate.scope_out_blocked


def test_gates_match_the_real_deciders(tmp_path: Path):
    plan = _plan(
        Step(id=1, title="Add one", files=["plan_tool/a.py"]),
        Step(id=2, title="Add two", files=["plan_tool/b.py"], depends_on=[1]),
        Step(id=3, title="Add three", files=["plan_tool/c.py"], status=StepStatus.DONE),
    )
    plan_path = _plan_path(tmp_path)
    breakdown = evaluate_split_criteria(plan, plan_path=plan_path, repo_root=tmp_path)
    for step in plan.steps:
        gate = _gate(breakdown, step.id)
        safe, blocking = split_safety.split_is_safe(plan, step.id)
        assert gate.split_safe == safe
        assert gate.split_blocking == tuple(blocking)
        preview = compute_narrow(
            plan,
            carved_id=step.id,
            plan_path=plan_path,
            repo_root=tmp_path,
            source_frontmatter_hash="",
        )
        assert gate.scope_out_blocked == bool(preview.blockers)
        assert gate.scope_out_blocker_kinds == tuple(b.kind for b in preview.blockers)


def test_evaluate_split_safety_calls_no_claude(tmp_path: Path):
    # The gate deciders take no invoker; running the evaluator must not trip the
    # autouse real-backend conftest gate. A sentinel invoker is never wired in.
    calls: list[object] = []
    plan = _plan(
        Step(id=1, title="Add one", files=["plan_tool/a.py"]),
        Step(id=2, title="Add two", files=["plan_tool/b.py"], depends_on=[1]),
    )
    breakdown = evaluate_split_criteria(plan, plan_path=_plan_path(tmp_path))
    assert breakdown.gates
    assert calls == []


# --- per-plan renderer ------------------------------------------------------


def test_render_plan_breakdown_lists_each_criterion(tmp_path: Path):
    plan = _plan(
        Step(id=1, title="Refactor parser to add validation", files=["plan_tool/parser.py"])
    )
    breakdown = evaluate_split_criteria(plan, plan_path=_plan_path(tmp_path))
    text = render_plan_breakdown(breakdown)
    for result in breakdown.results:
        assert result.criterion_id in text
        assert result.reason in text


def test_render_plan_breakdown_plain_when_color_off(tmp_path: Path):
    plan = _plan(Step(id=1, title="Add login", files=["plan_tool/auth.py"]))
    breakdown = evaluate_split_criteria(plan, plan_path=_plan_path(tmp_path))
    plain = render_plan_breakdown(breakdown, color=False)
    colored = render_plan_breakdown(breakdown, color=True)
    assert plain.strip()
    assert not _ANSI_RE.search(plain)
    assert _ANSI_RE.search(colored)


def _gate_section(text: str) -> str:
    """The run-state gate section (everything from its header on)."""
    marker = "Run-state gates (splittable now?)"
    assert marker in text, text
    return text[text.index(marker):]


def test_render_breakdown_uses_splittable_wording(tmp_path: Path):
    plan = _plan(
        Step(id=1, title="Add one", files=["plan_tool/a.py"]),
        Step(id=2, title="Add two", files=["plan_tool/b.py"], depends_on=[1]),
    )
    breakdown = evaluate_split_criteria(plan, plan_path=_plan_path(tmp_path))
    section = _gate_section(render_plan_breakdown(breakdown))
    assert "splittable now?" in section
    assert "scope-out blocked" in section
    # The gate section never borrows the fires? "shape defect present" polarity.
    assert "fires" not in section


def test_render_breakdown_gates_separate_from_fires(tmp_path: Path):
    plan = _plan(
        Step(id=1, title="Refactor parser to add validation", files=["plan_tool/parser.py"])
    )
    breakdown = evaluate_split_criteria(plan, plan_path=_plan_path(tmp_path))
    text = render_plan_breakdown(breakdown)
    # Gates render in their own section below the altitude/fires? rows.
    marker = "Run-state gates (splittable now?)"
    assert marker in text
    last_result_line = max(
        text.index(f"• {r.criterion_id}:") for r in breakdown.results
    )
    assert text.index(marker) > last_result_line
    section = _gate_section(text)
    for gate in breakdown.gates:
        assert f"step {gate.step_id}:" in section


# --- CLI command wiring (step 6) --------------------------------------------


def _write_cli_plan(tmp_path: Path, *, step_title: str = "Only step") -> Path:
    """Write a minimal registered plan ``1-demo`` (slug ``demo``); return the manifest.

    The leanest frontmatter ``parse_plan`` accepts (title/status/priority + one
    step). ``step_title`` lets a test choose whether an altitude-2 predicate fires.
    """
    (tmp_path / ".git").mkdir(exist_ok=True)
    plans_dir = tmp_path / "plans"
    plans_dir.mkdir(exist_ok=True)
    (plans_dir / "1-demo.md").write_text(
        "---\n"
        "title: Demo\n"
        "status: planning\n"
        "priority: medium\n"
        "steps:\n"
        "  - id: 1\n"
        f"    title: {step_title}\n"
        "---\n"
        "# Body\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "structured_plans.json"
    manifest.write_text(json.dumps({"plans": ["plans/1-demo.md"]}), encoding="utf-8")
    return manifest


def _cli_argv(tmp_path: Path, manifest: Path, *args: str) -> list[str]:
    """Pin repo-root + manifest so ``main`` stays off ambient cwd discovery."""
    return ["--repo-root", str(tmp_path), "--manifest", str(manifest), *args]


def test_register_returns_handler_map():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    handlers = register(subparsers)
    assert handlers == {"split-criteria": cmd_split_criteria}
    assert "split-criteria" in subparsers.choices


def test_split_criteria_sorts_after_scope_out_in_help():
    help_text = build_parser().format_help()
    assert "split-criteria" in help_text
    # Canonical order pins the new verb right after scope-out.
    assert help_text.index("scope-out") < help_text.index("split-criteria")


def test_validate_reports_no_orphan_subcommand():
    from plan_tool.capability_catalog import check_capabilities

    findings = check_capabilities(_REPO_ROOT)
    orphans = [
        f
        for f in findings
        if f.code == "orphan-subcommand" and "split-criteria" in f.message
    ]
    assert not orphans, orphans


def test_split_criteria_cmd_imports_no_app_symbol():
    # The thin command module must not import from plan_tool.cli.app (cycle guard).
    import ast

    import plan_tool.cli.split_criteria_cmd as mod

    tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module != "plan_tool.cli.app"
        elif isinstance(node, ast.Import):
            assert all(a.name != "plan_tool.cli.app" for a in node.names)


@pytest.mark.integration
class TestSplitCriteriaCommand:
    """Drive ``main([...])`` end to end through parse → dispatch → handler."""

    def test_no_arg_renders_legend(self, capsys):
        # Legend mode short-circuits before any plan/context resolution.
        rc = main(["split-criteria"])
        out = capsys.readouterr().out
        assert rc == 0
        assert render_split_criteria() in out

    def test_with_plan_renders_breakdown(self, tmp_path, capsys):
        manifest = _write_cli_plan(tmp_path)
        rc = main(_cli_argv(tmp_path, manifest, "split-criteria", "1-demo"))
        out = capsys.readouterr().out
        assert rc == 0
        assert "Split criteria — demo" in out
        assert "Run-state gates (splittable now?)" in out

    def test_exits_zero_when_criteria_fire(self, tmp_path, capsys):
        manifest = _write_cli_plan(
            tmp_path, step_title="Refactor parser to add validation"
        )
        rc = main(_cli_argv(tmp_path, manifest, "split-criteria", "1-demo"))
        out = capsys.readouterr().out
        assert rc == 0  # no --fail-on-findings rc-flip
        assert granularity.SPLIT_PREDICATE_MIXED_VERBS in out
        assert "fires" in out

    def test_spends_no_claude(self, tmp_path):
        # No @allow_real_claude marker: the autouse conftest gate raises if any
        # backend binary is spawned, so a green run proves no invoker is wired.
        manifest = _write_cli_plan(
            tmp_path, step_title="Refactor parser to add validation"
        )
        rc = main(_cli_argv(tmp_path, manifest, "split-criteria", "1-demo"))
        assert rc == 0

    def test_handler_does_not_double_record(self, tmp_path):
        manifest = _write_cli_plan(tmp_path)
        rc = main(_cli_argv(tmp_path, manifest, "split-criteria", "1-demo"))
        assert rc == 0
        # evaluate_split_criteria writes exactly one event; the handler adds none.
        assert len(_breakdown_events(tmp_path)) == 1

    def test_legend_mode_records_nothing(self, tmp_path):
        manifest = _write_cli_plan(tmp_path)
        rc = main(_cli_argv(tmp_path, manifest, "split-criteria"))
        assert rc == 0
        assert _breakdown_events(tmp_path) == []
