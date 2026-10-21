"""Tests for inline decision outcome resolution."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from plan_tool.telemetry import (
    TELEMETRY_SCHEMA_VERSION,
    DecisionEvent,
    code_fingerprint_digest,
    read_decisions,
    record_decision,
    telemetry_path,
)
from plan_tool.convergence_diagnosis import ReportHistory, RunFinding, RunSnapshot
from plan_tool import telemetry_analysis
from plan_tool.run_log import RunOutcome
from plan_tool.review import Recommendation
from plan_tool.review_persistence import compute_plan_fingerprint, save_review
from plan_tool.telemetry_analysis import (
    OUTCOME_ACTED_ON,
    OUTCOME_NO_OP,
    OUTCOME_REVERTED,
    OUTCOME_STILL_OPEN,
    RESOLUTION_ASYNC,
    RESOLUTION_INLINE,
    RESOLUTION_UNRESOLVED,
    HIGH_NO_OP_RATE,
    LOW_COVERAGE_RATE,
    MIN_SAMPLE_FOR_RECOMMENDATION,
    REVERTED_RATE_FLAG,
    DecisionAggregate,
    FindingClass,
    FindingClassDriftSignal,
    FindingDriftAnalysis,
    LowImpactDemotionLookup,
    ResolvedDecision,
    TelemetryAnalysis,
    TuningRecommendation,
    aggregate_decisions,
    analyze_decisions,
    analyze_finding_drift,
    build_low_impact_demotion_lookup,
    classify_calibration_recommendation,
    recommend_tuning,
    render_analysis,
    resolve_decision_async,
    resolve_decision_inline,
    resolve_decisions,
)


def event(kind: str, decision: str = "recorded", **context: str) -> DecisionEvent:
    return DecisionEvent(2, "t", kind, decision, "demo", context, "decision-1")


def finding(
    step_id: int,
    *,
    source: str = "granularity-split",
    severity: str = "info",
) -> RunFinding:
    return RunFinding("finding", source, severity, step_id, None, "Split step")


def snapshot(fingerprint: str, *findings: RunFinding) -> RunSnapshot:
    return RunSnapshot(
        "completeness", None, "2026-01-01T00:00:00Z", fingerprint, {}, False,
        1, list(findings), {},
    )


def split_event(*, fingerprint: str = "P") -> DecisionEvent:
    item = event("granularity", "code-reveals-split")
    item.context = {"step_ids": ["5"]}
    item.plan_fingerprint = fingerprint
    return item


def history(*runs: RunSnapshot) -> ReportHistory:
    return ReportHistory("demo", "/plans/2-demo.md", list(runs))


def calibration_snapshot(
    kind: str, created_at: str, step_id: int | None, *findings: RunFinding,
    outcome_evidence_valid: bool | None = None,
) -> RunSnapshot:
    return RunSnapshot(
        kind, step_id, created_at, "P", {}, False, 1, list(findings), {},
        outcome_evidence_valid,
    )


def calibration_finding(
    *, title: str = "Validate boundary contract", anchor: str | None = "boundary-contract",
    step_id: int | None = 5, source: str = "plan-correctness",
    redirect_present: bool = False,
) -> RunFinding:
    return RunFinding(
        "finding", source, "high", step_id, anchor, title,
        redirect_present=redirect_present,
    )


def _analyze_calibration_history(
    monkeypatch: pytest.MonkeyPatch, item: ReportHistory
):
    plan_path = Path("/plans/2-demo.md")
    monkeypatch.setattr(
        telemetry_analysis.locator, "list_plans_from_manifest",
        lambda _root: [SimpleNamespace(path=plan_path)],
    )
    monkeypatch.setattr(
        telemetry_analysis.convergence_diagnosis, "load_report_history",
        lambda _path: item,
    )
    return analyze_finding_drift(Path("/repo"))


@pytest.mark.parametrize(
    ("verdict", "expected"),
    [
        ("APPLIED", OUTCOME_ACTED_ON),
        ("NOT-APPLICABLE", OUTCOME_NO_OP),
        ("BLOCKED", OUTCOME_STILL_OPEN),
        ("BLOCKED-STRUCTURAL", OUTCOME_STILL_OPEN),
        ("UNKNOWN", OUTCOME_STILL_OPEN),
        ("INVOCATION-FAILED", OUTCOME_STILL_OPEN),
    ],
)
def test_apply_verdict_mapping(verdict: str, expected: str) -> None:
    assert resolve_decision_inline(event("apply-verdict", verdict=verdict)) == expected


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        ("applied", OUTCOME_ACTED_ON),
        ("recommended", OUTCOME_STILL_OPEN),
        ("unsafe", OUTCOME_NO_OP),
        ("proposal-unusable", OUTCOME_NO_OP),
        ("step-missing", OUTCOME_NO_OP),
    ],
)
def test_escalate_split_mapping(outcome: str, expected: str) -> None:
    assert resolve_decision_inline(event("escalate-split", "resolved", outcome=outcome)) == expected


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        ("split-applied", OUTCOME_ACTED_ON),
        ("accept", OUTCOME_NO_OP),
        ("override", OUTCOME_NO_OP),
        ("unclassified-accepted", OUTCOME_NO_OP),
        ("unclassified-classified", OUTCOME_NO_OP),
        ("split-requested", OUTCOME_STILL_OPEN),
        ("split-error", OUTCOME_STILL_OPEN),
        ("split-unusable", OUTCOME_STILL_OPEN),
        ("split-invalid", OUTCOME_STILL_OPEN),
    ],
)
def test_create_step_outcome_mapping(action: str, expected: str) -> None:
    assert resolve_decision_inline(
        event("granularity", "create-step-outcome", action=action)
    ) == expected


def test_associated_create_outcome_keeps_inline_mapping() -> None:
    assert resolve_decision_inline(
        event(
            "granularity",
            "create-step-outcome",
            assessment_id="assessment-1",
            action="split-applied",
        )
    ) == OUTCOME_ACTED_ON


def test_legacy_create_outcome_keeps_inline_mapping() -> None:
    legacy = event("granularity", "create-step-outcome", action="accept")
    assert "assessment_id" not in legacy.context
    assert resolve_decision_inline(legacy) == OUTCOME_NO_OP


def test_unknown_result_value_is_still_open() -> None:
    assert resolve_decision_inline(event("apply-verdict", verdict="FUTURE")) == OUTCOME_STILL_OPEN


@pytest.mark.parametrize("decision", ["assessed", "code-reveals-split", "create-review"])
def test_other_granularity_decisions_are_not_inline(decision: str) -> None:
    assert resolve_decision_inline(event("granularity", decision)) is None


def test_non_self_recording_family_returns_none() -> None:
    assert resolve_decision_inline(event("drift-gate", "gated")) is None


def test_inline_mapper_never_emits_reverted() -> None:
    inline_events = [
        event("apply-verdict", verdict="APPLIED"),
        event("escalate-split", "resolved", outcome="applied"),
        event("granularity", "create-step-outcome", action="split-applied"),
    ]
    assert OUTCOME_REVERTED not in {resolve_decision_inline(item) for item in inline_events}


def test_async_completed_run_carries_run_evidence() -> None:
    item = event("drift-gate")
    item.run_id = "run-1"
    result = resolve_decision_async(
        item,
        run_outcome=RunOutcome("run-1", True, outcome="completed", rc=0),
        history=None,
    )
    assert result == (OUTCOME_STILL_OPEN, "run-log: outcome=completed rc=0")


def test_async_incomplete_run_is_still_open() -> None:
    result = resolve_decision_async(
        event("drift-gate"),
        run_outcome=RunOutcome("run-1", False),
        history=None,
    )
    assert result == (OUTCOME_STILL_OPEN, "run-log: incomplete")


def test_async_resolver_returns_none_without_evidence() -> None:
    assert resolve_decision_async(event("drift-gate"), run_outcome=None, history=None) is None


def test_code_reveals_split_transition_is_acted_on() -> None:
    result = resolve_decision_async(
        split_event(),
        run_outcome=None,
        history=history(snapshot("P", finding(5)), snapshot("P-prime")),
    )
    assert result is not None
    assert result[0] == OUTCOME_ACTED_ON


def test_code_reveals_split_without_transition_is_still_open() -> None:
    result = resolve_decision_async(
        split_event(),
        run_outcome=None,
        history=history(snapshot("P", finding(5)), snapshot("P", finding(5))),
    )
    assert result is not None
    assert result[0] == OUTCOME_STILL_OPEN


def test_code_reveals_split_ignores_nonstructural_post_transition_finding() -> None:
    result = resolve_decision_async(
        split_event(),
        run_outcome=None,
        history=history(
            snapshot("P", finding(5)),
            snapshot("P-prime", finding(5, source="plan-correctness", severity="high")),
        ),
    )
    assert result is not None
    assert result[0] == OUTCOME_ACTED_ON


def test_async_region_resolved_then_reappears_is_reverted() -> None:
    result = resolve_decision_async(
        split_event(),
        run_outcome=None,
        history=history(
            snapshot("P", finding(5)),
            snapshot("P-prime"),
            snapshot("P-double-prime", finding(5)),
        ),
    )
    assert result is not None
    assert result[0] == OUTCOME_REVERTED


def test_async_region_resolved_then_original_fingerprint_returns_is_reverted() -> None:
    result = resolve_decision_async(
        split_event(),
        run_outcome=None,
        history=history(
            snapshot("P", finding(5)),
            snapshot("P-prime"),
            snapshot("P", finding(5)),
        ),
    )
    assert result is not None
    assert result[0] == OUTCOME_REVERTED


def test_async_no_matching_region_is_no_op() -> None:
    result = resolve_decision_async(
        split_event(),
        run_outcome=None,
        history=history(snapshot("P", finding(6)), snapshot("P-prime", finding(6))),
    )
    assert result is not None
    assert result[0] == OUTCOME_NO_OP


def test_async_anchor_reuses_step_token_matcher() -> None:
    item = event("drift-gate")
    item.anchor = "step5-over-packed"
    item.plan_fingerprint = "P"
    result = resolve_decision_async(
        item,
        run_outcome=None,
        history=history(snapshot("P", finding(5)), snapshot("P-prime")),
    )
    assert result is not None
    assert result[0] == OUTCOME_ACTED_ON


def test_resolve_decisions_marks_non_inline_unresolved(tmp_path: Path) -> None:
    record_decision(tmp_path, kind="apply-verdict", decision="recorded", plan_slug="demo", context={"verdict": "APPLIED"})
    record_decision(tmp_path, kind="drift-gate", decision="gated", plan_slug="demo")

    inline, unresolved = resolve_decisions(tmp_path)
    assert (inline.resolution, inline.outcome, inline.evidence) == (RESOLUTION_INLINE, OUTCOME_ACTED_ON, "APPLIED")
    assert (unresolved.resolution, unresolved.outcome, unresolved.evidence) == (RESOLUTION_UNRESOLVED, OUTCOME_STILL_OPEN, "")


def test_resolve_decisions_empty_log_returns_empty(tmp_path: Path) -> None:
    assert resolve_decisions(tmp_path) == []


def test_resolve_decisions_tolerates_missing_context_keys(tmp_path: Path) -> None:
    record_decision(tmp_path, kind="apply-verdict", decision="recorded", plan_slug="demo")
    (result,) = resolve_decisions(tmp_path)
    assert (result.outcome, result.resolution, result.evidence) == (OUTCOME_STILL_OPEN, RESOLUTION_INLINE, "")


def test_telemetry_analysis_does_not_import_cli() -> None:
    source = (Path(__file__).parents[1] / "plan_tool" / "telemetry_analysis.py").read_text()
    assert "plan_tool.cli" not in source


def test_resolved_decision_is_frozen() -> None:
    result = ResolvedDecision("id", "kind", "decision", "slug", OUTCOME_NO_OP, RESOLUTION_INLINE, "raw")
    with pytest.raises(FrozenInstanceError):
        result.outcome = OUTCOME_ACTED_ON  # type: ignore[misc]


def resolved(
    kind: str = "signal",
    decision: str = "fired",
    *,
    slug: str = "demo",
    outcome: str = OUTCOME_ACTED_ON,
    resolution: str = RESOLUTION_INLINE,
) -> ResolvedDecision:
    return ResolvedDecision("id", kind, decision, slug, outcome, resolution, "evidence")


def aggregate(**overrides: int) -> DecisionAggregate:
    values = dict(
        total=10, plan_count=1, acted_on=10, no_op=0, reverted=0,
        still_open=0, resolved=10, unresolved=0,
    )
    values.update(overrides)
    return DecisionAggregate("signal", "fired", **values)


def test_aggregate_groups_by_kind_and_decision_in_stable_order() -> None:
    result = aggregate_decisions([
        resolved("granularity", "create-review"),
        resolved("granularity", "assessed"),
        resolved("granularity", "assessed"),
    ])
    assert [(item.kind, item.decision, item.total) for item in result] == [
        ("granularity", "assessed", 2),
        ("granularity", "create-review", 1),
    ]


def test_create_association_does_not_change_aggregate_buckets() -> None:
    result = aggregate_decisions(
        [
            resolved("granularity", "create-review"),
            resolved("granularity", "create-step-outcome"),
            resolved("granularity", "create-step-outcome"),
        ]
    )
    assert [(item.decision, item.total) for item in result] == [
        ("create-review", 1),
        ("create-step-outcome", 2),
    ]


def test_aggregate_counts_outcomes_and_resolution_split() -> None:
    result = aggregate_decisions([
        resolved(outcome=OUTCOME_ACTED_ON),
        resolved(outcome=OUTCOME_NO_OP, resolution=RESOLUTION_ASYNC),
        resolved(outcome=OUTCOME_REVERTED, resolution=RESOLUTION_ASYNC),
        resolved(outcome=OUTCOME_STILL_OPEN, resolution=RESOLUTION_UNRESOLVED),
    ])[0]
    assert (result.acted_on, result.no_op, result.reverted, result.still_open) == (1, 1, 1, 1)
    assert (result.resolved, result.unresolved) == (3, 1)


def test_aggregate_counts_distinct_nonempty_plan_slugs() -> None:
    result = aggregate_decisions([
        resolved(slug="one"), resolved(slug="one"), resolved(slug="two"), resolved(slug=""),
    ])[0]
    assert (result.total, result.plan_count) == (4, 2)


def test_aggregate_empty_and_unknown_values_are_total() -> None:
    assert aggregate_decisions([]) == []
    result = aggregate_decisions([resolved(outcome="future", resolution="future")])[0]
    assert result.total == 1
    assert sum((result.acted_on, result.no_op, result.reverted, result.still_open)) == 0
    assert result.resolved == result.unresolved == 0


def test_recommend_high_no_op_and_reverted_rates() -> None:
    item = aggregate(acted_on=1, no_op=6, reverted=3)
    result = recommend_tuning([item])
    assert [note.category for note in result] == ["over-sensitive", "reverting"]
    assert "6/10 resolved outcomes were no-op" in result[0].message
    assert "3/10 resolved outcomes reverted" in result[1].message
    assert item == aggregate(acted_on=1, no_op=6, reverted=3)
    assert HIGH_NO_OP_RATE == 0.6 and REVERTED_RATE_FLAG == 0.2


def test_recommend_low_join_coverage() -> None:
    item = aggregate(total=10, acted_on=2, still_open=8, resolved=2, unresolved=8)
    recommendations = recommend_tuning([item])
    assert [note.category for note in recommendations] == ["low-coverage"]
    assert "8/10 outcomes are uncorrelated" in recommendations[0].message
    assert LOW_COVERAGE_RATE == 0.7


def test_recommend_thin_and_well_calibrated_groups_are_silent() -> None:
    thin = aggregate(total=9, acted_on=0, no_op=9, resolved=9)
    assert recommend_tuning([thin, aggregate()]) == []
    assert MIN_SAMPLE_FOR_RECOMMENDATION == 10


def test_analyze_decisions_end_to_end_and_empty(tmp_path: Path) -> None:
    assert analyze_decisions(tmp_path) == TelemetryAnalysis(0, (), ())
    record_decision(tmp_path, kind="apply-verdict", decision="recorded", plan_slug="demo", context={"verdict": "APPLIED"})
    record_decision(tmp_path, kind="apply-verdict", decision="recorded", plan_slug="demo", context={"verdict": "NOT-APPLICABLE"})
    analysis = analyze_decisions(tmp_path)
    assert analysis.total_events == 2
    assert len(analysis.aggregates) == 1
    assert (analysis.aggregates[0].acted_on, analysis.aggregates[0].no_op) == (1, 1)


def test_legacy_and_current_rows_resolve_identically(tmp_path: Path) -> None:
    path = telemetry_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fingerprint = {"src/a.py": "abc"}
    base = {
        "ts": "t",
        "kind": "apply-verdict",
        "decision": "recorded",
        "plan_slug": "demo",
        "context": {"verdict": "APPLIED"},
    }
    rows = [
        {**base, "schema_version": 2, "code_fingerprint": fingerprint},
        {
            **base,
            "schema_version": TELEMETRY_SCHEMA_VERSION,
            "code_fingerprint": code_fingerprint_digest(fingerprint),
        },
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    events = read_decisions(tmp_path)
    assert events[0].code_fingerprint == events[1].code_fingerprint
    resolved = resolve_decisions(tmp_path)
    assert [(item.resolution, item.outcome) for item in resolved] == [
        (RESOLUTION_INLINE, OUTCOME_ACTED_ON),
        (RESOLUTION_INLINE, OUTCOME_ACTED_ON),
    ]


def test_analysis_accepts_ownerless_legacy_digest_rows(tmp_path: Path) -> None:
    path = telemetry_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "ts": "t",
                "kind": "drift-gate",
                "decision": "gated",
                "plan_slug": "",
                "context": {"verdict": "drifted"},
                "code_fingerprint": "f" * 64,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (result,) = resolve_decisions(tmp_path)
    assert result.outcome == OUTCOME_STILL_OPEN
    assert result.resolution == RESOLUTION_UNRESOLVED
    assert analyze_decisions(tmp_path).total_events == 1


@pytest.mark.integration
def test_smoke_code_reveals_split_sidecar_transition_is_acted_on(
    tmp_path: Path,
) -> None:
    plan_rel = "docs/implementation-plans/2-demo.md"
    plan_path = tmp_path / plan_rel
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text(
        "---\n"
        "title: Demo\n"
        "status: planning\n"
        "priority: low\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: First step\n"
        "---\n"
        "# Demo\n",
        encoding="utf-8",
    )
    manifest = tmp_path / ".plan-tool" / "plans.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"plans": [plan_rel]}), encoding="utf-8")

    before = compute_plan_fingerprint(plan_path)
    recommendation = Recommendation(
        id="split-5",
        source="granularity-split",
        severity="info",
        step_id=5,
        title="Split step 5",
        body="The step mixes two concerns.",
    )
    save_review(
        plan_slug="demo",
        plan_path=plan_rel,
        repo_root=tmp_path,
        report_md="before\n",
        recommendations=[recommendation],
        now=datetime(2026, 1, 1, tzinfo=timezone.utc),
        kind="completeness",
        plan_fingerprint=before,
    )
    record_decision(
        tmp_path,
        kind="granularity",
        decision="code-reveals-split",
        plan_slug="demo",
        context={"step_ids": ["5"]},
        plan_fingerprint=before,
    )

    plan_path.write_text(
        "---\n"
        "title: Demo\n"
        "status: planning\n"
        "priority: low\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: First half\n"
        "  - id: 2\n"
        "    title: Second half\n"
        "---\n"
        "# Demo\n",
        encoding="utf-8",
    )
    after = compute_plan_fingerprint(plan_path)
    save_review(
        plan_slug="demo",
        plan_path=plan_rel,
        repo_root=tmp_path,
        report_md="after\n",
        recommendations=[],
        now=datetime(2026, 1, 2, tzinfo=timezone.utc),
        kind="completeness",
        plan_fingerprint=after,
    )

    (result,) = resolve_decisions(tmp_path)
    assert (result.resolution, result.outcome) == (RESOLUTION_ASYNC, OUTCOME_ACTED_ON)


def test_render_analysis_contains_totals_and_recommendations() -> None:
    note = TuningRecommendation("signal", "fired", "over-sensitive", "Review threshold.")
    output = render_analysis(TelemetryAnalysis(10, (aggregate(),), (note,)))
    assert "Telemetry analysis: 10 events" in output
    assert "signal/fired: total=10" in output
    assert "Review threshold." in output
    assert render_analysis(TelemetryAnalysis(0, (), ())) == "No telemetry recorded yet."


def test_analysis_projection_and_render_include_calibration_without_decisions() -> None:
    finding_class = telemetry_analysis.FindingClass(
        "granularity-split", "step", "cross-boundary", "fresh"
    )
    signal = telemetry_analysis.FindingClassDriftSignal(
        finding_class, total=3, confirmed=2, cleared=1, unresolved=0,
        confirmed_rate=2 / 3,
        evidence_state=telemetry_analysis.FINDING_DRIFT_EVIDENCE_SUFFICIENT,
    )
    analysis = TelemetryAnalysis(
        0, (), (), telemetry_analysis.FindingDriftAnalysis(3, (signal,))
    )

    projected = telemetry_analysis.analysis_to_dict(analysis)
    assert projected["calibration"] == {
        "total_findings": 3,
        "signals": [{
            "source": "granularity-split", "anchor_category": "step",
            "scope_shape": "cross-boundary", "purity_verdict_provenance": "fresh",
            "total": 3, "confirmed": 2, "cleared": 1, "unresolved": 0,
            "confirmed_rate": 2 / 3, "evidence_state": "evidence-sufficient",
        }],
    }
    output = render_analysis(analysis)
    assert "Telemetry analysis: 0 events" in output
    assert "Calibration:" in output
    assert "provenance=fresh" in output
    assert "confirmed=2, cleared=1, unresolved=0" in output


def test_finding_class_confirmed_by_later_run_reconcile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin = calibration_finding()
    result = _analyze_calibration_history(monkeypatch, history(
        calibration_snapshot("detail-reconcile", "2026-01-01T00:00:00Z", 5, origin),
        calibration_snapshot("run-reconcile", "2026-01-01T00:00:01Z", 5, origin,
                             outcome_evidence_valid=True),
    ))

    (signal,) = result.signals
    assert (signal.confirmed, signal.cleared, signal.unresolved) == (1, 0, 0)
    assert signal.confirmed_rate == 1.0


def test_finding_class_clears_only_with_valid_outcome_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin = calibration_finding()
    valid = _analyze_calibration_history(monkeypatch, history(
        calibration_snapshot("detail-reconcile", "2026-01-01T00:00:00Z", 5, origin),
        calibration_snapshot("run-reconcile", "2026-01-01T00:00:01Z", 5,
                             outcome_evidence_valid=True),
    ))
    invalid = _analyze_calibration_history(monkeypatch, history(
        calibration_snapshot("detail-reconcile", "2026-01-01T00:00:00Z", 5, origin),
        calibration_snapshot("run-reconcile", "2026-01-01T00:00:01Z", 5,
                             outcome_evidence_valid=None),
    ))

    assert (valid.signals[0].cleared, valid.signals[0].unresolved) == (1, 0)
    assert (invalid.signals[0].cleared, invalid.signals[0].unresolved) == (0, 1)


def test_finding_drift_uses_strict_identity_and_deduplicates_origins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin = calibration_finding()
    later_origin = calibration_finding()
    unrelated = calibration_finding(title="Update unrelated command", anchor="other-anchor")
    result = _analyze_calibration_history(monkeypatch, history(
        calibration_snapshot("completeness", "2026-01-01T00:00:00Z", None, origin),
        calibration_snapshot("completeness", "2026-01-01T00:00:01Z", None, later_origin),
        calibration_snapshot("run-reconcile", "2026-01-01T00:00:02Z", 5, unrelated,
                             outcome_evidence_valid=True),
    ))

    (signal,) = result.signals
    assert (signal.total, signal.confirmed, signal.cleared, signal.unresolved) == (1, 0, 1, 0)


def test_completeness_step_anchor_and_redirect_outcome_boundaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin = calibration_finding(step_id=None, anchor="step5-boundary-contract")
    redirected = calibration_finding(redirect_present=True)
    result = _analyze_calibration_history(monkeypatch, history(
        calibration_snapshot("completeness", "2026-01-01T00:00:00Z", None, origin),
        calibration_snapshot("run-reconcile", "2026-01-01T00:00:01Z", 5, redirected,
                             outcome_evidence_valid=True),
    ))

    (signal,) = result.signals
    assert (signal.confirmed, signal.cleared, signal.unresolved) == (0, 1, 0)


def test_live_recommendation_and_persisted_finding_share_calibration_class() -> None:
    rec = Recommendation(
        id="x", source="granularity-split", severity="medium", step_id=5,
        anchor="step5-contract", title="Split contract boundary", body="x",
        purity_verdict_provenance="fresh",
    )
    persisted = RunFinding(
        "finding", "granularity-split", "medium", 5, "step5-contract",
        "Split contract boundary", purity_verdict_provenance="fresh",
    )

    assert classify_calibration_recommendation(rec) == telemetry_analysis._classify_history_finding(persisted)


def calibration_recommendation(**overrides: object) -> Recommendation:
    values: dict[str, object] = {
        "id": "calibration-rec",
        "source": "plan-correctness",
        "severity": "medium",
        "step_id": 5,
        "anchor": "boundary-contract",
        "title": "Validate boundary contract",
        "body": "x",
        "impact": "low",
    }
    values.update(overrides)
    return Recommendation(**values)


def calibration_signal(
    finding_class: FindingClass, *, confirmed: int = 1, cleared: int = 9,
    unresolved: int = 0, confirmed_rate: float | None = 0.10,
) -> FindingClassDriftSignal:
    return FindingClassDriftSignal(
        finding_class=finding_class,
        total=confirmed + cleared + unresolved,
        confirmed=confirmed,
        cleared=cleared,
        unresolved=unresolved,
        confirmed_rate=confirmed_rate,
        evidence_state=telemetry_analysis.FINDING_DRIFT_EVIDENCE_SUFFICIENT,
    )


def lookup_for_signal(
    monkeypatch: pytest.MonkeyPatch, signal: FindingClassDriftSignal,
) -> LowImpactDemotionLookup:
    monkeypatch.setattr(
        telemetry_analysis,
        "analyze_finding_drift",
        lambda _root: FindingDriftAnalysis(signal.total, (signal,)),
    )
    return build_low_impact_demotion_lookup(Path("/repo"))


def test_low_impact_medium_recommendation_demotes_at_resolved_threshold_and_rate_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recommendation = calibration_recommendation()
    lookup = lookup_for_signal(
        monkeypatch,
        calibration_signal(classify_calibration_recommendation(recommendation)),
    )

    assert lookup(recommendation) is True


def test_low_impact_medium_recommendation_remains_blocking_below_resolved_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recommendation = calibration_recommendation()
    lookup = lookup_for_signal(
        monkeypatch,
        calibration_signal(
            classify_calibration_recommendation(recommendation),
            confirmed=0,
            cleared=9,
            unresolved=100,
            confirmed_rate=0.0,
        ),
    )

    assert lookup(recommendation) is False


def test_low_impact_medium_recommendation_remains_blocking_above_confirmed_rate_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recommendation = calibration_recommendation()
    lookup = lookup_for_signal(
        monkeypatch,
        calibration_signal(
            classify_calibration_recommendation(recommendation),
            confirmed=2,
            cleared=8,
            confirmed_rate=0.11,
        ),
    )

    assert lookup(recommendation) is False


def test_demotion_lookup_rejects_missing_unknown_and_unresolved_only_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recommendation = calibration_recommendation(source="granularity-split")
    unknown_class = classify_calibration_recommendation(recommendation)
    lookup = lookup_for_signal(
        monkeypatch,
        calibration_signal(unknown_class, confirmed=0, cleared=10, confirmed_rate=0.0),
    )
    assert lookup(recommendation) is False

    legacy_lookup = lookup_for_signal(
        monkeypatch,
        calibration_signal(
            FindingClass("granularity-split", "step", "step-detail", "legacy"),
            confirmed=0,
            cleared=10,
            confirmed_rate=0.0,
        ),
    )
    assert legacy_lookup(calibration_recommendation(
        source="granularity-split", anchor="step5", purity_verdict_provenance="legacy",
    )) is False

    unresolved_lookup = lookup_for_signal(
        monkeypatch,
        calibration_signal(
            FindingClass("plan-correctness", "step", "step-detail"),
            confirmed=0,
            cleared=0,
            unresolved=10,
            confirmed_rate=None,
        ),
    )
    assert unresolved_lookup(calibration_recommendation()) is False
    assert LowImpactDemotionLookup(frozenset())(calibration_recommendation()) is False


def test_demotion_lookup_matches_live_recommendation_calibration_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    matching = calibration_recommendation(
        source="granularity-split", anchor="step5-contract",
        purity_verdict_provenance="fresh",
    )
    different_provenance = calibration_recommendation(
        source="granularity-split", anchor="step5-contract",
        purity_verdict_provenance="exact-cache",
    )
    different_source = calibration_recommendation(
        source="plan-correctness", anchor="step5-contract",
    )
    different_anchor_shape = calibration_recommendation(
        source="granularity-split", anchor="ordinary-anchor",
        purity_verdict_provenance="fresh",
    )
    lookup = lookup_for_signal(
        monkeypatch,
        calibration_signal(classify_calibration_recommendation(matching)),
    )

    assert lookup(matching) is True
    assert lookup(different_provenance) is False
    assert lookup(different_source) is False
    assert lookup(different_anchor_shape) is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"severity": "high"}, {"severity": "critical"},
        {"severity": "nit"}, {"severity": "info"},
        {"impact": "medium"}, {"impact": None},
    ],
)
def test_demotion_lookup_rejects_non_low_medium_candidates(
    monkeypatch: pytest.MonkeyPatch, overrides: dict[str, object],
) -> None:
    qualifying = calibration_recommendation()
    lookup = lookup_for_signal(
        monkeypatch,
        calibration_signal(classify_calibration_recommendation(qualifying)),
    )

    assert lookup(calibration_recommendation(**overrides)) is False


def test_demotion_lookup_reads_calibration_once_and_evaluation_reads_no_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recommendation = calibration_recommendation()
    analysis = FindingDriftAnalysis(
        10, (calibration_signal(classify_calibration_recommendation(recommendation)),)
    )
    calls = 0

    def analyze_once(_root: Path) -> FindingDriftAnalysis:
        nonlocal calls
        calls += 1
        return analysis

    monkeypatch.setattr(telemetry_analysis, "analyze_finding_drift", analyze_once)
    lookup = build_low_impact_demotion_lookup(Path("/repo"))
    assert [lookup(recommendation) for _ in range(3)] == [True, True, True]
    assert calls == 1


def test_demotion_lookup_is_immutable(monkeypatch: pytest.MonkeyPatch) -> None:
    recommendation = calibration_recommendation()
    lookup = lookup_for_signal(
        monkeypatch,
        calibration_signal(classify_calibration_recommendation(recommendation)),
    )

    with pytest.raises(FrozenInstanceError):
        lookup.qualifying_finding_classes = frozenset()
    with pytest.raises(AttributeError):
        lookup.qualifying_finding_classes.add(classify_calibration_recommendation(recommendation))


@pytest.mark.parametrize(
    "value,field",
    [(aggregate(), "total"),
     (TuningRecommendation("k", "d", "category", "message"), "message"),
     (TelemetryAnalysis(0, (), ()), "total_events")],
)
def test_analysis_records_are_frozen(value: object, field: str) -> None:
    with pytest.raises(FrozenInstanceError):
        setattr(value, field, None)
