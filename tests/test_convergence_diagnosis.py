"""Tests for plan_tool.convergence_diagnosis — the saved-report-history reader."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from plan_tool.convergence_diagnosis import (
    HISTORY_KINDS,
    TITLE_SIMILARITY_CUTOFF,
    VERDICT_CONVERGING,
    VERDICT_INSUFFICIENT_HISTORY,
    VERDICT_NO_HISTORY,
    WINDOW_SIZE,
    AuditEvidenceMetadata,
    CompatiblePass,
    ConvergenceDiagnosis,
    EditDriftAdvisory,
    FindingChurn,
    ImpactRecurrenceAdvisory,
    AuditEvidenceLedger,
    AuditEvidenceRow,
    ReportHistory,
    RunFinding,
    RunSnapshot,
    SeriesDiagnosis,
    build_collapsed_completeness_passes,
    classify_bare_mechanism_advisory,
    classify_edit_drift,
    classify_impact_recurrence,
    compose_mechanism_edit_drift_advisory_lines,
    diagnose_convergence,
    is_structural_source,
    load_audit_evidence_ledger,
    load_report_history,
    load_saved_reviews,
    partition_series,
    render_audit_evidence_ledger,
    render_diagnosis,
    _code_drifted_since_prior,
    _capped_finding_confidence_labels,
    _capped_finding_titles,
    _edit_drift_lines,
    _finding_churn,
    _impact_recurrence_lines,
    _latest_blocking_findings,
    _matches,
    _normalized_focus,
    _open_medium_plus,
    _redecomposition_step_counts,
    _step_token,
    _structural_recurs_in_streak,
)
from plan_tool.convergence import STAGE_BARE, STAGE_DETAIL
from plan_tool.review import Recommendation
from plan_tool.review_persistence import (
    Annotation,
    load_review,
    plan_reports_dir,
    save_review,
    save_sampler_checkpoint,
    sampler_checkpoint_path,
)


# A plan file whose slug ("spinner") drives both the reports dir and the
# ``plan_slug`` save_review records.
_PLAN_REL = "docs/implementation-plans/1-spinner.md"
_FIXTURE = (
    Path(__file__).parent / "fixtures" / "convergence" / "sample-report-history.json"
)
_LEDGER_FIXTURE = (
    Path(__file__).parent / "fixtures" / "convergence" / "audit-history-ledger.json"
)


def _plan_abs(repo_root: Path) -> Path:
    return repo_root / _PLAN_REL


def _completeness_rec(
    rec_id: str,
    anchor: str = "step5-over-pack",
    *,
    title: str = "Step 5 packs too much",
    impact: str | None = None,
) -> Recommendation:
    """A completeness finding: step_id None, anchor carries the step slug."""
    return Recommendation(
        id=rec_id,
        source="plan-completeness",
        severity="medium",
        step_id=None,
        title=title,
        body="…",
        anchor=anchor,
        impact=impact,
    )


def _reconcile_rec(rec_id: str, step_id: int) -> Recommendation:
    return Recommendation(
        id=rec_id,
        source="detail-reconcile",
        severity="high",
        step_id=step_id,
        title=f"Step {step_id} drifted",
        body="…",
    )


def _structural_rec(rec_id: str) -> Recommendation:
    """A structural medium finding."""
    return Recommendation(
        id=rec_id,
        source="granularity-split",
        severity="medium",
        step_id=None,
        title="Step 5 packs too much",
        body="…",
        anchor="step5-over-pack",
    )


def _save(
    repo_root: Path,
    *,
    recs: list[Recommendation],
    kind: str = "completeness",
    when: datetime,
    step_id: int | None = None,
    report_md: str = "report body\n",
    annotations: dict[str, Annotation] | None = None,
    is_pre_apply_checkpoint: bool = False,
    audit_stage: str | None = "bare",
) -> Path:
    kwargs: dict = {}
    if kind == "completeness" and audit_stage is not None:
        kwargs["audit_stage"] = audit_stage
    return save_review(
        plan_slug="spinner",
        plan_path=_PLAN_REL,
        repo_root=repo_root,
        report_md=report_md,
        recommendations=recs,
        annotations=annotations,
        now=when,
        kind=kind,
        step_id=step_id,
        is_pre_apply_checkpoint=is_pre_apply_checkpoint,
        **kwargs,
    )


def _rewrite_role_payload(path: Path, **overrides: object) -> Path:
    """Write a saved sidecar back with ``overrides`` applied to its payload.

    ``save_review`` emits only the role a producer can legitimately write, so
    legacy and untrusted role metadata is authored here."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update(overrides)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _dt(day: int, *, second: int = 0) -> datetime:
    return datetime(2026, 6, day, 9, 0, second, tzinfo=timezone.utc)


def _write_completeness_markdown(repo_root: Path, stem: str) -> Path:
    reports_dir = plan_reports_dir(_plan_abs(repo_root))
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"{stem}-completeness.md"
    path.write_text("saved completeness report\n", encoding="utf-8")
    return path


def test_load_report_history_empty_when_no_reports_dir(tmp_path: Path) -> None:
    history = load_report_history(_plan_abs(tmp_path))
    assert isinstance(history, ReportHistory)
    assert history.runs == []
    assert history.plan_slug == "spinner"


def test_load_audit_evidence_ledger_empty(tmp_path: Path) -> None:
    ledger = load_audit_evidence_ledger(_plan_abs(tmp_path))

    assert ledger == AuditEvidenceLedger("spinner", str(_plan_abs(tmp_path)), ())


def test_load_audit_evidence_ledger_discovers_stable_in_progress_checkpoint(
    tmp_path: Path,
) -> None:
    _save(tmp_path, recs=[], when=_dt(1))
    _write_completeness_markdown(tmp_path, "20260601-090000")
    checkpoint = save_sampler_checkpoint(
        plan_slug="spinner",
        plan_path=_PLAN_REL,
        repo_root=tmp_path,
        report_md="sampler checkpoint",
        recommendations=[],
        sampler_state={"lifecycle": "in-progress", "next_pass": 2},
    )

    saved_reviews = load_saved_reviews(
        _plan_abs(tmp_path), completeness_only=True
    )
    ledger = load_audit_evidence_ledger(
        _plan_abs(tmp_path), saved_reviews=saved_reviews
    )

    assert checkpoint in saved_reviews
    assert [row.state for row in ledger.rows] == [
        "saved-final",
        "in-progress-checkpoint",
    ]
    row = ledger.rows[-1]
    assert row.report_path is None
    assert row.sidecar_path == checkpoint
    assert row.filename_time == "unknown"
    rendered = render_audit_evidence_ledger(ledger)
    assert "in-progress-checkpoint: filename time unknown" in rendered
    assert f"sidecar path: {checkpoint}" in rendered


def test_load_audit_evidence_ledger_orders_checkpoint_by_saved_time_not_always_last(
    tmp_path: Path,
) -> None:
    """The checkpoint's fixed filename carries no timestamp for ordering
    purposes, but it must still sort by its real saved time rather than
    unconditionally ranking after every dated report."""
    checkpoint = save_sampler_checkpoint(
        plan_slug="spinner",
        plan_path=_PLAN_REL,
        repo_root=tmp_path,
        report_md="sampler checkpoint",
        recommendations=[],
        sampler_state={"lifecycle": "in-progress", "next_pass": 2},
        now=_dt(1),
    )
    _save(tmp_path, recs=[], when=_dt(9))
    _write_completeness_markdown(tmp_path, "20260609-090000")

    ledger = load_audit_evidence_ledger(_plan_abs(tmp_path))

    assert [row.sidecar_path for row in ledger.rows] == [
        checkpoint,
        sampler_checkpoint_path(_plan_abs(tmp_path)).parent
        / "20260609-090000-completeness.json",
    ]
    assert [row.state for row in ledger.rows] == [
        "in-progress-checkpoint",
        "saved-final",
    ]


@pytest.mark.parametrize(
    ("artifact_kind", "expected_state"),
    [
        ("unreadable", "malformed-sidecar"),
        ("wrong-kind", "malformed-sidecar"),
        ("invalid-role", "unknown-role"),
    ],
)
def test_load_audit_evidence_ledger_does_not_promote_invalid_stable_checkpoint(
    tmp_path: Path,
    artifact_kind: str,
    expected_state: str,
) -> None:
    checkpoint = sampler_checkpoint_path(_plan_abs(tmp_path))
    if artifact_kind == "unreadable":
        checkpoint.parent.mkdir(parents=True)
        checkpoint.write_text("not JSON", encoding="utf-8")
    elif artifact_kind == "wrong-kind":
        wrong_kind = _save(tmp_path, recs=[], kind="review", when=_dt(1))
        wrong_kind.replace(checkpoint)
    else:
        checkpoint = save_sampler_checkpoint(
            plan_slug="spinner",
            plan_path=_PLAN_REL,
            repo_root=tmp_path,
            report_md="invalid sampler checkpoint",
            recommendations=[],
            sampler_state={"lifecycle": "in-progress"},
        )
        _rewrite_role_payload(checkpoint, is_pre_apply_checkpoint=False)

    ledger = load_audit_evidence_ledger(_plan_abs(tmp_path))

    assert len(ledger.rows) == 1
    assert ledger.rows[0].state == expected_state
    assert ledger.rows[0].state not in {
        "in-progress-checkpoint",
        "terminal-sampler-residue",
    }
    assert load_report_history(_plan_abs(tmp_path)).runs == []


def test_load_audit_evidence_ledger_names_terminal_sampler_residue(
    tmp_path: Path,
) -> None:
    checkpoint = save_sampler_checkpoint(
        plan_slug="spinner",
        plan_path=_PLAN_REL,
        repo_root=tmp_path,
        report_md="terminal sampler residue",
        recommendations=[],
        sampler_state={"lifecycle": "terminal-residue", "next_pass": 3},
    )

    ledger = load_audit_evidence_ledger(_plan_abs(tmp_path))

    assert len(ledger.rows) == 1
    row = ledger.rows[0]
    assert row.state == "terminal-sampler-residue"
    assert row.report_path is None
    assert row.sidecar_path == checkpoint
    assert "terminal-sampler-residue: filename time unknown" in (
        render_audit_evidence_ledger(ledger)
    )


def test_load_report_history_excludes_in_progress_checkpoint(tmp_path: Path) -> None:
    _save(tmp_path, recs=[], when=_dt(1))
    save_sampler_checkpoint(
        plan_slug="spinner",
        plan_path=_PLAN_REL,
        repo_root=tmp_path,
        report_md="sampler checkpoint",
        recommendations=[],
        sampler_state={"lifecycle": "in-progress"},
    )

    history = load_report_history(_plan_abs(tmp_path))

    assert len(history.runs) == 1
    assert history.runs[0].created_at == "2026-06-01T09:00:00Z"


def _ledger_row(
    state: str,
    *,
    filename_time: str = "2026-06-01T09:00:00Z",
    headline: str = "awaiting-human-action",
    next_action: str = "Inspect the saved report and its saved result.",
) -> AuditEvidenceRow:
    """Build an immutable display row without involving saved-artifact parsing."""
    return AuditEvidenceRow(
        report_path=Path(f"/saved/{state}.md"),
        sidecar_path=Path(f"/saved/{state}.json"),
        filename_time=filename_time,
        state=state,
        saved_metadata=AuditEvidenceMetadata(
            is_pre_apply_checkpoint=False,
            created_at="2026-06-01T09:00:00Z",
            audit_stage="bare",
            audit_revision_grade="run",
            audit_coverage={"evidence_status": "confirmed"},
            qualified_result={
                "headline": headline,
                "stage": "bare",
                "coverage": "confirmed",
                "revision_status": "current",
            },
        ),
        next_action=next_action,
    )


def test_render_audit_evidence_ledger_empty() -> None:
    out = render_audit_evidence_ledger(
        AuditEvidenceLedger("spinner", _PLAN_REL, ())
    )

    assert "saved audit evidence ledger: spinner" in out
    assert "no-saved-audits" in out
    assert "Run a completeness audit to save structured evidence." in out


def test_render_audit_evidence_ledger_renders_rows_in_reader_order() -> None:
    first = _ledger_row("checkpoint", filename_time="2026-06-03T09:00:00Z")
    second = _ledger_row("report-only", filename_time="2026-06-01T09:00:00Z")

    out = render_audit_evidence_ledger(
        AuditEvidenceLedger("spinner", _PLAN_REL, (first, second))
    )

    assert out.index("checkpoint: filename time 2026-06-03T09:00:00Z") < out.index(
        "report-only: filename time 2026-06-01T09:00:00Z"
    )


def test_render_audit_evidence_ledger_state_actions_are_specific() -> None:
    rows = tuple(
        _ledger_row(
            state,
            next_action=f"Action for {state}.",
        )
        for state in (
            "report-only",
            "orphan-sidecar",
            "malformed-sidecar",
            "checkpoint",
            "unknown-role",
            "saved-final",
        )
    )

    out = render_audit_evidence_ledger(AuditEvidenceLedger("spinner", _PLAN_REL, rows))

    assert out.count("next action:") == len(rows)
    for row in rows:
        assert f"  {row.state}:" in out
        assert str(row.report_path) in out
        assert "pre-apply checkpoint=False" in out
        assert f"next action: {row.next_action}" in out


def test_render_audit_evidence_ledger_saved_final_unknown_result_does_not_claim_a_result() -> None:
    row = _ledger_row(
        "saved-final",
        headline="unknown",
        next_action=(
            "Inspect the saved artifact; run a fresh audit when a qualified result "
            "is needed."
        ),
    )

    out = render_audit_evidence_ledger(AuditEvidenceLedger("spinner", _PLAN_REL, (row,)))

    assert "headline=unknown" in out
    assert row.next_action in out
    assert "saved result." not in out


def test_render_audit_evidence_ledger_no_qualified_current_evidence_requests_fresh_audit() -> None:
    row = _ledger_row(
        "saved-final",
        headline="no-qualified-current-evidence",
        next_action="Run a fresh completeness audit.",
    )

    out = render_audit_evidence_ledger(AuditEvidenceLedger("spinner", _PLAN_REL, (row,)))

    assert "headline=no-qualified-current-evidence" in out
    assert "next action: Run a fresh completeness audit." in out


def test_load_audit_evidence_ledger_orders_paired_and_orphaned_artifacts(
    tmp_path: Path,
) -> None:
    matrix = json.loads(_LEDGER_FIXTURE.read_text(encoding="utf-8"))
    for artifact in matrix["artifacts"]:
        timestamp = artifact["timestamp"]
        if artifact["report"]:
            _write_completeness_markdown(tmp_path, timestamp)
        if artifact["sidecar"]:
            when = datetime.strptime(timestamp, "%Y%m%d-%H%M%S").replace(
                tzinfo=timezone.utc
            )
            _save(
                tmp_path,
                recs=[],
                when=when,
                is_pre_apply_checkpoint=artifact["sidecar"] == "checkpoint",
            )

    ledger = load_audit_evidence_ledger(_plan_abs(tmp_path))

    assert [row.state for row in ledger.rows] == matrix["expected_order"]
    assert [row.filename_time for row in ledger.rows] == [
        expected["filename_time"] for expected in matrix["expected_rows"]
    ]
    for row, expected in zip(ledger.rows, matrix["expected_rows"], strict=True):
        assert row.state == expected["state"]
        assert row.saved_metadata.created_at == expected["created_at"]
        assert row.saved_metadata.audit_stage == expected["audit_stage"]
        assert (
            row.saved_metadata.audit_coverage["evidence_status"]
            == expected["audit_coverage_status"]
        )
        assert (
            row.saved_metadata.qualified_result["headline"]
            == expected["qualified_headline"]
        )
    assert ledger.rows[0].saved_metadata.is_pre_apply_checkpoint is True
    assert ledger.rows[1].saved_metadata.is_pre_apply_checkpoint is False
    assert ledger.rows[2].report_path is not None
    assert ledger.rows[2].sidecar_path is not None


def test_load_audit_evidence_ledger_orders_filename_times_then_paths(
    tmp_path: Path,
) -> None:
    second = _write_completeness_markdown(tmp_path, "b-20260604-090000")
    first = _write_completeness_markdown(tmp_path, "a-20260604-090000")

    ledger = load_audit_evidence_ledger(_plan_abs(tmp_path))

    assert [row.report_path for row in ledger.rows] == [first, second]
    assert [row.filename_time for row in ledger.rows] == [
        "2026-06-04T09:00:00Z",
        "2026-06-04T09:00:00Z",
    ]


def test_load_audit_evidence_ledger_keeps_bad_pairs_visible_without_history(
    tmp_path: Path,
) -> None:
    malformed = _save(tmp_path, recs=[], when=_dt(1))
    _write_completeness_markdown(tmp_path, "20260601-090000")
    malformed.write_bytes(b"\xff")
    non_completeness = _save(tmp_path, recs=[], kind="review", when=_dt(2))
    paired_non_completeness = non_completeness.with_name(
        "20260602-090000-completeness.json"
    )
    non_completeness.rename(paired_non_completeness)
    _write_completeness_markdown(tmp_path, "20260602-090000")

    ledger = load_audit_evidence_ledger(_plan_abs(tmp_path))

    assert [row.state for row in ledger.rows] == [
        "malformed-sidecar",
        "malformed-sidecar",
    ]
    assert all("fresh completeness audit" in row.next_action for row in ledger.rows)
    assert load_report_history(_plan_abs(tmp_path)).runs == []


def test_load_audit_evidence_ledger_keeps_malformed_orphan_sidecars_visible(
    tmp_path: Path,
) -> None:
    corrupt = _save(tmp_path, recs=[], when=_dt(1))
    corrupt.write_bytes(b"\xff")
    wrong_kind = _save(tmp_path, recs=[], kind="review", when=_dt(2))
    wrong_kind.rename(wrong_kind.with_name("20260602-090000-completeness.json"))

    ledger = load_audit_evidence_ledger(_plan_abs(tmp_path))

    assert [row.state for row in ledger.rows] == [
        "malformed-sidecar",
        "malformed-sidecar",
    ]
    assert all(row.report_path is None for row in ledger.rows)


def test_saved_report_readers_reject_foreign_snapshots(tmp_path: Path) -> None:
    foreign = (
        plan_reports_dir(tmp_path / "docs/implementation-plans/2-other.md")
        / "20260601-090000-completeness.json"
    )
    foreign.parent.mkdir(parents=True)
    foreign.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="saved-artifact snapshot"):
        load_saved_reviews(_plan_abs(tmp_path), artifact_paths=(foreign,))
    with pytest.raises(ValueError, match="saved-artifact snapshot"):
        load_audit_evidence_ledger(_plan_abs(tmp_path), artifact_paths=(foreign,))
    with pytest.raises(ValueError, match="saved-review cache"):
        load_report_history(_plan_abs(tmp_path), saved_reviews={foreign: None})


def test_load_audit_evidence_ledger_rejects_incomplete_supplied_cache(
    tmp_path: Path,
) -> None:
    sidecar = _save(tmp_path, recs=[], when=_dt(1))

    with pytest.raises(ValueError, match="does not cover"):
        load_audit_evidence_ledger(
            _plan_abs(tmp_path),
            artifact_paths=(sidecar,),
            saved_reviews={},
        )


def test_load_audit_evidence_ledger_unknown_role_is_not_checkpoint(
    tmp_path: Path,
) -> None:
    sidecar = _save(tmp_path, recs=[], when=_dt(1))
    _rewrite_role_payload(sidecar, version=3, is_pre_apply_checkpoint="unknown")
    _write_completeness_markdown(tmp_path, "20260601-090000")

    row = load_audit_evidence_ledger(_plan_abs(tmp_path)).rows[0]

    assert row.state == "unknown-role"
    assert row.saved_metadata.is_pre_apply_checkpoint is None
    assert "unknown-role: filename time" in render_audit_evidence_ledger(
        AuditEvidenceLedger("spinner", _PLAN_REL, (row,))
    )


def test_load_audit_evidence_ledger_uses_one_snapshot_and_loads_only_completeness(
    tmp_path: Path, monkeypatch
) -> None:
    import plan_tool.convergence_diagnosis as convergence_diagnosis

    completeness_sidecar = _save(tmp_path, recs=[], when=_dt(1))
    _save(tmp_path, recs=[], kind="run-reconcile", when=_dt(2))
    _write_completeness_markdown(tmp_path, "20260601-090000")
    original_list_artifacts = convergence_diagnosis.list_report_artifacts
    original_load_review = convergence_diagnosis.load_review
    snapshot_calls = 0
    loaded_paths: list[Path] = []

    def counting_list_artifacts(path: Path):
        nonlocal snapshot_calls
        snapshot_calls += 1
        return original_list_artifacts(path)

    def counting_load_review(path: Path):
        loaded_paths.append(path)
        return original_load_review(path)

    monkeypatch.setattr(
        convergence_diagnosis, "list_report_artifacts", counting_list_artifacts
    )
    monkeypatch.setattr(convergence_diagnosis, "load_review", counting_load_review)

    ledger = load_audit_evidence_ledger(_plan_abs(tmp_path))

    assert len(ledger.rows) == 1
    assert snapshot_calls == 1
    assert loaded_paths == [completeness_sidecar]


def test_load_audit_evidence_ledger_uses_saved_metadata_only(tmp_path: Path) -> None:
    sidecar = _save(tmp_path, recs=[], when=_dt(1))
    _write_completeness_markdown(tmp_path, "20260601-090000")
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    payload["created_at"] = "not-a-time"
    payload["qualified_result"] = ["not", "a", "result"]
    payload["audit_coverage"] = ["not", "coverage"]
    sidecar.write_text(json.dumps(payload), encoding="utf-8")

    row = load_audit_evidence_ledger(_plan_abs(tmp_path)).rows[0]

    assert row.state == "saved-final"
    assert row.saved_metadata.created_at == "invalid"
    assert row.saved_metadata.audit_coverage["evidence_status"] == "unknown-legacy"
    assert row.saved_metadata.qualified_result["headline"] == "unknown"
    assert "qualified result" in row.next_action
    rendered = render_audit_evidence_ledger(
        AuditEvidenceLedger("spinner", _PLAN_REL, (row,))
    )
    assert '"evidence_status": "unknown-legacy"' in rendered
    assert "headline=unknown" in rendered


def test_history_normalizes_purity_provenance_and_redirect_state() -> None:
    from plan_tool.convergence_diagnosis import _finding_from_recommendation
    from plan_tool.review import Redirect

    legacy_purity = Recommendation(
        id="purity", source="granularity-split", severity="medium", step_id=1,
        title="Mixed", body="Split it.",
    )
    ordinary = Recommendation(
        id="ordinary", source="claude", severity="high", step_id=1,
        title="Drift", body="Fix it.", redirect=Redirect(reason="plan"),
    )

    assert _finding_from_recommendation(legacy_purity).purity_verdict_provenance == "unknown"
    normalized = _finding_from_recommendation(ordinary)
    assert normalized.purity_verdict_provenance is None
    assert normalized.redirect_present is True


def test_finding_from_recommendation_carries_impact() -> None:
    from plan_tool.convergence_diagnosis import _finding_from_recommendation

    for impact in ("high", "medium", "low"):
        rec = Recommendation(
            id=f"impact-{impact}",
            source="plan-completeness",
            severity="medium",
            step_id=None,
            title="Tagged finding",
            body="…",
            impact=impact,
        )
        assert _finding_from_recommendation(rec).impact == impact


def test_finding_from_recommendation_impact_none_when_absent() -> None:
    from plan_tool.convergence_diagnosis import _finding_from_recommendation

    rec = Recommendation(
        id="no-impact",
        source="plan-completeness",
        severity="medium",
        step_id=None,
        title="Untagged finding",
        body="…",
    )
    assert _finding_from_recommendation(rec).impact is None


def test_load_report_history_preserves_impact(tmp_path: Path) -> None:
    rec = _completeness_rec("impact-high")
    rec = Recommendation(
        id=rec.id,
        source=rec.source,
        severity=rec.severity,
        step_id=rec.step_id,
        title=rec.title,
        body=rec.body,
        anchor=rec.anchor,
        impact="high",
    )
    _save(tmp_path, recs=[rec], when=_dt(1))
    history = load_report_history(_plan_abs(tmp_path))
    assert history.runs[0].findings[0].impact == "high"


def test_finding_from_recommendation_carries_likely_bare_mechanism_signal() -> None:
    from plan_tool.convergence_diagnosis import _finding_from_recommendation

    rec = Recommendation(
        id="mechanism",
        source="plan-correctness",
        severity="medium",
        step_id=None,
        title="Select a serializer choice",
        body="Use a serializer choice for the internal payload.",
    )
    assert _finding_from_recommendation(rec).likely_bare_mechanism is True


def test_loaded_history_recomputes_likely_bare_mechanism_from_saved_recommendation_text(
    tmp_path: Path,
) -> None:
    rec = Recommendation(
        id="mechanism",
        source="plan-correctness",
        severity="medium",
        step_id=None,
        title="Select a serializer choice",
        body="Use a serializer choice for the internal payload.",
    )
    path = _save(tmp_path, recs=[rec], when=_dt(1))
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert "likely_bare_mechanism" not in payload["recommendations"][0]
    loaded = load_review(path)
    assert loaded.recommendations[0] == rec
    assert load_report_history(_plan_abs(tmp_path)).runs[0].findings[0].likely_bare_mechanism


def test_loaded_history_classifies_only_newest_completed_completeness_pass(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import plan_tool.convergence_diagnosis as convergence_diagnosis

    older = Recommendation(
        id="older",
        source="plan-correctness",
        severity="medium",
        step_id=None,
        title="Select an older serializer choice",
        body="Use a serializer choice for the internal payload.",
    )
    newest = Recommendation(
        id="newest",
        source="plan-correctness",
        severity="medium",
        step_id=None,
        title="Select a newer serializer choice",
        body="Use a serializer choice for the internal payload.",
    )
    _save(tmp_path, recs=[older], when=_dt(1))
    _save(tmp_path, recs=[newest], when=_dt(2))

    calls: list[str] = []
    original = convergence_diagnosis.classify_likely_bare_mechanism

    def _tracking_classify(rec: Recommendation) -> bool:
        calls.append(rec.id)
        return original(rec)

    monkeypatch.setattr(
        convergence_diagnosis, "classify_likely_bare_mechanism", _tracking_classify
    )

    history = load_report_history(_plan_abs(tmp_path))

    assert calls == ["newest"]
    assert not history.runs[0].findings[0].likely_bare_mechanism
    assert history.runs[1].findings[0].likely_bare_mechanism


def test_finding_from_recommendation_skips_domain_classify_for_non_conceptual(
    monkeypatch,
) -> None:
    """``classify_finding_domain`` is only ever consulted by
    ``is_blocking_finding`` for ``plan-correctness``/``plan-completeness``
    findings -- a non-conceptual source's ``.domain`` is unread by every
    caller, so it must not be classified (or even called) at flatten time."""
    import plan_tool.convergence_diagnosis as convergence_diagnosis
    from plan_tool.convergence_diagnosis import _finding_from_recommendation

    calls: list[str] = []

    def _tracking_classify(rec: Recommendation) -> str:
        calls.append(rec.id)
        return "code-logic"

    monkeypatch.setattr(
        convergence_diagnosis, "classify_finding_domain", _tracking_classify
    )

    non_conceptual = Recommendation(
        id="nc-1", source="claude", severity="high", step_id=1,
        title="Drift", body="src/module.py needs a fix.",
    )
    conceptual = Recommendation(
        id="c-1", source="plan-correctness", severity="medium", step_id=None,
        title="Gap", body="src/module.py contradicts the plan.",
    )

    non_conceptual_finding = _finding_from_recommendation(non_conceptual)
    assert non_conceptual_finding.domain is None
    assert calls == []

    conceptual_finding = _finding_from_recommendation(conceptual)
    assert conceptual_finding.domain == "code-logic"
    assert calls == ["c-1"]


def test_load_report_history_reads_saved_sidecars(tmp_path: Path) -> None:
    _save(tmp_path, recs=[_completeness_rec("a-1")], when=_dt(1))
    _save(tmp_path, recs=[_completeness_rec("b-1"), _completeness_rec("b-2")], when=_dt(2))
    history = load_report_history(_plan_abs(tmp_path))
    assert len(history.runs) == 2
    assert [len(r.findings) for r in history.runs] == [1, 2]
    assert history.runs[0].findings[0].id == "a-1"


def test_runs_sorted_oldest_to_newest(tmp_path: Path) -> None:
    _save(tmp_path, recs=[_completeness_rec("late")], when=_dt(3))
    _save(tmp_path, recs=[_completeness_rec("early")], when=_dt(1))
    _save(tmp_path, recs=[_completeness_rec("mid")], when=_dt(2))
    history = load_report_history(_plan_abs(tmp_path))
    assert [r.created_at for r in history.runs] == [
        "2026-06-01T09:00:00Z",
        "2026-06-02T09:00:00Z",
        "2026-06-03T09:00:00Z",
    ]


def test_runs_with_malformed_created_at_sort_last(tmp_path: Path) -> None:
    malformed = _save(tmp_path, recs=[_completeness_rec("malformed")], when=_dt(1))
    payload = json.loads(malformed.read_text(encoding="utf-8"))
    payload["created_at"] = "not-a-timestamp"
    malformed.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _save(tmp_path, recs=[_completeness_rec("valid")], when=_dt(2))

    history = load_report_history(_plan_abs(tmp_path))

    assert [run.findings[0].id for run in history.runs] == ["valid", "malformed"]


def test_history_skips_sidecar_missing_required_field(tmp_path: Path) -> None:
    malformed = _save(tmp_path, recs=[_completeness_rec("malformed")], when=_dt(1))
    payload = json.loads(malformed.read_text(encoding="utf-8"))
    payload.pop("plan_slug")
    malformed.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _save(tmp_path, recs=[_completeness_rec("valid")], when=_dt(2))

    history = load_report_history(_plan_abs(tmp_path))

    assert [run.findings[0].id for run in history.runs] == ["valid"]


def test_kind_filter_excludes_bare_review(tmp_path: Path) -> None:
    _save(tmp_path, recs=[_completeness_rec("keep")], kind="completeness", when=_dt(1))
    _save(tmp_path, recs=[_completeness_rec("drop")], kind="review", when=_dt(2))
    history = load_report_history(_plan_abs(tmp_path))
    assert [r.kind for r in history.runs] == ["completeness"]
    assert history.runs[0].findings[0].id == "keep"


def test_kind_filter_keeps_reconcile_kinds(tmp_path: Path) -> None:
    _save(
        tmp_path,
        recs=[_reconcile_rec("d-1", 3)],
        kind="detail-reconcile",
        step_id=3,
        when=_dt(1),
    )
    _save(
        tmp_path,
        recs=[_reconcile_rec("r-1", 4)],
        kind="run-reconcile",
        step_id=4,
        when=_dt(2),
    )
    history = load_report_history(_plan_abs(tmp_path))
    assert {r.kind for r in history.runs} == {"detail-reconcile", "run-reconcile"}
    assert {r.step_id for r in history.runs} == {3, 4}


def test_completeness_finding_step_id_is_none(tmp_path: Path) -> None:
    _save(tmp_path, recs=[_completeness_rec("c-1", anchor="step5-over-pack")], when=_dt(1))
    history = load_report_history(_plan_abs(tmp_path))
    finding = history.runs[0].findings[0]
    assert finding.step_id is None
    assert finding.anchor == "step5-over-pack"


def test_annotations_carried_through_verbatim(tmp_path: Path) -> None:
    annotations = {"c-1": Annotation(status="skip", halt_reason="")}
    _save(
        tmp_path,
        recs=[_completeness_rec("c-1")],
        when=_dt(1),
        annotations=annotations,
    )
    history = load_report_history(_plan_abs(tmp_path))
    ann = history.runs[0].annotations["c-1"]
    assert ann.status == "skip"
    assert ann.halt_reason == ""


def test_run_finding_omits_resolved(tmp_path: Path) -> None:
    _save(tmp_path, recs=[_completeness_rec("c-1")], when=_dt(1))
    finding = load_report_history(_plan_abs(tmp_path)).runs[0].findings[0]
    assert not hasattr(finding, "resolved")


def test_run_finding_omits_verdict(tmp_path: Path) -> None:
    _save(tmp_path, recs=[_completeness_rec("c-1")], when=_dt(1))
    finding = load_report_history(_plan_abs(tmp_path)).runs[0].findings[0]
    assert not hasattr(finding, "verdict")


def test_report_bytes_is_len_report_md(tmp_path: Path) -> None:
    body = "## Completeness\n\nsome finding\n"
    _save(tmp_path, recs=[_completeness_rec("c-1")], when=_dt(1), report_md=body)
    snapshot = load_report_history(_plan_abs(tmp_path)).runs[0]
    assert snapshot.report_bytes == len(body)


def test_corrupt_sidecar_is_skipped(tmp_path: Path) -> None:
    valid = _save(tmp_path, recs=[_completeness_rec("good")], when=_dt(1))
    corrupt = valid.parent / "20260602-090000-completeness.json"
    corrupt.write_text("{not valid json", encoding="utf-8")
    history = load_report_history(_plan_abs(tmp_path))
    assert [r.findings[0].id for r in history.runs] == ["good"]


def test_load_report_history_excludes_marked_pre_apply_checkpoint(
    tmp_path: Path,
) -> None:
    """A confirmed checkpoint holds mid-apply findings, so it is no run — and
    it stays on disk as recovery evidence while the finals keep their order."""
    _save(tmp_path, recs=[_completeness_rec("first-final")], when=_dt(1))
    checkpoint = _save(
        tmp_path,
        recs=[_completeness_rec("mid-apply")],
        when=_dt(2),
        is_pre_apply_checkpoint=True,
    )
    _save(tmp_path, recs=[_completeness_rec("second-final")], when=_dt(3))

    history = load_report_history(_plan_abs(tmp_path))

    assert load_review(checkpoint).is_pre_apply_checkpoint is True
    assert [r.findings[0].id for r in history.runs] == ["first-final", "second-final"]
    assert [r.created_at for r in history.runs] == [
        "2026-06-01T09:00:00Z",
        "2026-06-03T09:00:00Z",
    ]


def test_load_report_history_keeps_ordinary_final_roles(tmp_path: Path) -> None:
    """Both ordinary-final shapes stay eligible: a raw version-3 explicit
    ``false`` and the unmarked version-1/2 legacy sidecars, unmigrated."""
    explicit_final = _save(
        tmp_path, recs=[_completeness_rec("explicit-final")], when=_dt(1)
    )
    _rewrite_role_payload(explicit_final, version=3, is_pre_apply_checkpoint=False)
    legacy_v1 = _save(tmp_path, recs=[_completeness_rec("legacy-v1")], when=_dt(2))
    legacy_v2 = _save(tmp_path, recs=[_completeness_rec("legacy-v2")], when=_dt(3))
    _rewrite_role_payload(legacy_v2, version=2)

    for legacy, version in ((legacy_v1, 1), (legacy_v2, 2)):
        payload = json.loads(legacy.read_text(encoding="utf-8"))
        assert payload["version"] == version
        assert "is_pre_apply_checkpoint" not in payload
        assert load_review(legacy).is_pre_apply_checkpoint is False
    assert load_review(explicit_final).is_pre_apply_checkpoint is False

    history = load_report_history(_plan_abs(tmp_path))

    assert [r.findings[0].id for r in history.runs] == [
        "explicit-final",
        "legacy-v1",
        "legacy-v2",
    ]


def test_load_report_history_excludes_unknown_checkpoint_roles(
    tmp_path: Path,
) -> None:
    """Untrusted role metadata fails closed for every history kind — including
    a marked reconcile sidecar — while staying readable through load_review."""
    _save(tmp_path, recs=[_completeness_rec("final")], when=_dt(1))
    malformed = _save(
        tmp_path, recs=[_completeness_rec("malformed-marker")], when=_dt(2)
    )
    _rewrite_role_payload(malformed, version=3, is_pre_apply_checkpoint="yes")
    marked_reconcile = _save(
        tmp_path,
        recs=[_reconcile_rec("marked-reconcile", 4)],
        kind="run-reconcile",
        step_id=4,
        when=_dt(3),
    )
    _rewrite_role_payload(marked_reconcile, version=3, is_pre_apply_checkpoint=True)

    for path in (malformed, marked_reconcile):
        loaded = load_review(path)
        assert loaded.is_pre_apply_checkpoint is None, path.name
        assert len(loaded.recommendations) == 1, path.name

    history = load_report_history(_plan_abs(tmp_path))

    assert [r.findings[0].id for r in history.runs] == ["final"]


def test_load_report_history_final_snapshot_count_drives_diagnosis(
    tmp_path: Path,
) -> None:
    """The verdict reads only the finals. Counting the checkpoint would turn a
    two-run insufficient-history call into a full-window converging one."""
    from plan_tool.convergence_diagnosis import _snapshot_from_saved_review

    _save(tmp_path, recs=[_structural_rec("pack-1")], when=_dt(1))
    checkpoint = _save(
        tmp_path,
        recs=[_structural_rec("pack-checkpoint")],
        when=_dt(2),
        is_pre_apply_checkpoint=True,
    )
    _save(tmp_path, recs=[_structural_rec("pack-2")], when=_dt(3))

    history = load_report_history(_plan_abs(tmp_path))
    diagnosis = diagnose_convergence(history)

    assert len(history.runs) == 2
    assert [s.run_count for s in diagnosis.series] == [2]
    assert diagnosis.verdict == VERDICT_INSUFFICIENT_HISTORY

    counterfactual = ReportHistory(
        plan_slug=history.plan_slug,
        plan_path=history.plan_path,
        runs=[
            history.runs[0],
            _snapshot_from_saved_review(load_review(checkpoint)),
            history.runs[1],
        ],
    )
    assert diagnose_convergence(counterfactual).verdict == VERDICT_CONVERGING


def test_fixture_loads_into_model(tmp_path: Path) -> None:
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    history = ReportHistory(
        plan_slug=data["plan_slug"],
        plan_path=data["plan_path"],
        runs=[
            RunSnapshot(
                kind=run["kind"],
                step_id=run["step_id"],
                created_at=run["created_at"],
                plan_fingerprint=run["plan_fingerprint"],
                code_fingerprint=run["code_fingerprint"],
                code_fingerprint_present=run["code_fingerprint_present"],
                report_bytes=run["report_bytes"],
                findings=[
                    RunFinding(
                        id=f["id"],
                        source=f["source"],
                        severity=f["severity"],
                        step_id=f["step_id"],
                        anchor=f["anchor"],
                        title=f["title"],
                    )
                    for f in run["findings"]
                ],
                annotations={
                    rec_id: Annotation(**ann)
                    for rec_id, ann in run["annotations"].items()
                },
            )
            for run in data["runs"]
        ],
    )
    assert len(history.runs) == 3
    assert diagnose_convergence(history).verdict == VERDICT_CONVERGING


def test_history_kinds_excludes_bare_review() -> None:
    assert "review" not in HISTORY_KINDS
    assert HISTORY_KINDS == frozenset(
        {"completeness", "detail-reconcile", "run-reconcile"}
    )


# --------------------------------------------------------------------------- #
# Finding-matching helpers
# --------------------------------------------------------------------------- #


def _finding(
    rec_id: str,
    *,
    source: str = "granularity-split",
    severity: str = "medium",
    impact: str | None = None,
    step_id: int | None = None,
    anchor: str | None = None,
    title: str = "A finding",
    domain: str | None = None,
    likely_bare_mechanism: bool = False,
) -> RunFinding:
    """An in-memory ``RunFinding`` with structural/medium+ defaults."""
    return RunFinding(
        id=rec_id,
        source=source,
        severity=severity,
        impact=impact,
        step_id=step_id,
        anchor=anchor,
        title=title,
        domain=domain,
        likely_bare_mechanism=likely_bare_mechanism,
    )


def _snapshot(
    findings: list[RunFinding],
    *,
    kind: str = "completeness",
    step_id: int | None = None,
    created_at: str = "2026-06-01T09:00:00Z",
    annotations: dict[str, Annotation] | None = None,
    code_fingerprint: dict[str, str] | None = None,
    code_fingerprint_present: bool = True,
    plan_fingerprint: str = "fp",
    audit_stage: str | None = "bare",
    audit_revision_grade: str | None = None,
    step_ids: tuple[int, ...] = (),
) -> RunSnapshot:
    return RunSnapshot(
        kind=kind,
        step_id=step_id,
        created_at=created_at,
        plan_fingerprint=plan_fingerprint,
        code_fingerprint={} if code_fingerprint is None else code_fingerprint,
        code_fingerprint_present=code_fingerprint_present,
        report_bytes=100,
        findings=findings,
        annotations=annotations or {},
        audit_stage=audit_stage,
        audit_revision_grade=audit_revision_grade,
        step_ids=step_ids,
    )


def _history(runs: list[RunSnapshot]) -> ReportHistory:
    return ReportHistory(plan_slug="p", plan_path="x.md", runs=runs)


def test_diagnosis_mechanism_signal_leaves_verdict_and_blocking_unchanged() -> None:
    def _diagnosis_with_signal(likely_bare_mechanism: bool) -> ConvergenceDiagnosis:
        finding = RunFinding(
            id="mechanism",
            source="plan-correctness",
            severity="high",
            step_id=None,
            anchor=None,
            title="Select a serializer choice",
            domain="code-logic",
            likely_bare_mechanism=likely_bare_mechanism,
        )
        return diagnose_convergence(_history([_snapshot([finding])]), audit_stage=STAGE_BARE)

    unlabelled = _diagnosis_with_signal(False)
    labelled = _diagnosis_with_signal(True)

    assert labelled.verdict == unlabelled.verdict == VERDICT_INSUFFICIENT_HISTORY
    assert [f.id for f in labelled.latest_blocking] == [f.id for f in unlabelled.latest_blocking]


def _bare_mechanism_history(
    findings: list[RunFinding],
    *,
    annotations: dict[str, Annotation] | None = None,
    audit_stage: str = STAGE_BARE,
    audit_revision_grade: str | None = 'run',
) -> ReportHistory:
    return _history(
        [
            _snapshot(
                findings,
                annotations=annotations,
                audit_stage=audit_stage,
                audit_revision_grade=audit_revision_grade,
            )
        ]
    )


def test_bare_mechanism_advisory_appears_after_one_completed_pass() -> None:
    finding = _finding(
        "mechanism",
        source="plan-correctness",
        title="Select a serializer choice",
        likely_bare_mechanism=True,
    )

    diagnosis = diagnose_convergence(_bare_mechanism_history([finding]))

    assert diagnosis.verdict == VERDICT_INSUFFICIENT_HISTORY
    assert diagnosis.bare_mechanism_findings == (finding,)
    assert "Bare-plan mechanism advisory" in render_diagnosis(diagnosis)


def test_bare_mechanism_advisory_requires_open_bare_plan_correctness_finding() -> None:
    mechanism = _finding(
        "mechanism",
        source="plan-correctness",
        title="Select a serializer choice",
        likely_bare_mechanism=True,
    )
    cases = (
        _bare_mechanism_history([mechanism], audit_stage=STAGE_DETAIL),
        _bare_mechanism_history(
            [_finding("other", source="plan-completeness", likely_bare_mechanism=True)]
        ),
        _bare_mechanism_history(
            [mechanism], annotations={"mechanism": Annotation(status="applied")}
        ),
        _bare_mechanism_history(
            [_finding("unclassified", source="plan-correctness")]
        ),
    )

    assert all(not classify_bare_mechanism_advisory(history) for history in cases)


def test_bare_mechanism_advisory_requires_completed_run_grade_evidence() -> None:
    finding = _finding(
        "mechanism",
        source="plan-correctness",
        title="Select a serializer choice",
        likely_bare_mechanism=True,
    )
    run_history = _bare_mechanism_history([finding])
    jira_history = _bare_mechanism_history(
        [finding], audit_revision_grade='jira'
    )
    legacy_history = _bare_mechanism_history([finding], audit_revision_grade=None)
    malformed_history = _bare_mechanism_history([finding], audit_revision_grade="unknown")
    collapsed_jira_replay = _history(
        [
            _snapshot(
                [finding],
                created_at="2026-06-01T09:00:00Z",
                audit_revision_grade='run',
            ),
            _snapshot(
                [finding],
                created_at="2026-06-02T09:00:00Z",
                audit_revision_grade='jira',
            ),
        ]
    )

    baseline = diagnose_convergence(run_history)
    assert baseline.bare_mechanism_findings == (finding,)
    assert not diagnose_convergence(jira_history).bare_mechanism_findings
    assert not diagnose_convergence(legacy_history).bare_mechanism_findings
    assert not diagnose_convergence(malformed_history).bare_mechanism_findings
    assert not diagnose_convergence(collapsed_jira_replay).bare_mechanism_findings
    assert diagnose_convergence(jira_history).verdict == baseline.verdict


def test_diagnose_convergence_builds_collapsed_passes_once(monkeypatch) -> None:
    import plan_tool.convergence_diagnosis as convergence_diagnosis

    history = _bare_mechanism_history([])
    original = convergence_diagnosis.build_collapsed_completeness_passes
    calls = 0

    def _tracking_build(history: ReportHistory) -> tuple[CompatiblePass, ...]:
        nonlocal calls
        calls += 1
        return original(history)

    monkeypatch.setattr(
        convergence_diagnosis,
        "build_collapsed_completeness_passes",
        _tracking_build,
    )

    diagnose_convergence(history)

    assert calls == 1


def test_diagnose_mechanism_advisory_does_not_change_existing_diagnosis_fields() -> None:
    labelled = _finding(
        "mechanism",
        source="plan-correctness",
        title="Select a serializer choice",
        likely_bare_mechanism=True,
    )
    unlabelled = _finding(
        "mechanism",
        source="plan-correctness",
        title="Select a serializer choice",
    )
    with_advisory = diagnose_convergence(_bare_mechanism_history([labelled]))
    without_advisory = diagnose_convergence(_bare_mechanism_history([unlabelled]))

    assert with_advisory.verdict == without_advisory.verdict
    assert with_advisory.latest_blocking == without_advisory.latest_blocking
    assert with_advisory.finding_churn == without_advisory.finding_churn
    assert with_advisory.edit_drift == without_advisory.edit_drift
    assert with_advisory.bare_mechanism_findings == (labelled,)
    assert not without_advisory.bare_mechanism_findings


def test_is_structural_source_includes_legacy_detail_purity() -> None:
    assert is_structural_source("detail-purity")
    assert is_structural_source("granularity-split")
    assert not is_structural_source("plan-completeness")


# --- keying ---------------------------------------------------------------- #


def test_normalized_focus_prefers_finding_step_id() -> None:
    f = _finding("x", step_id=5, anchor="step7-elsewhere")
    assert _normalized_focus(f) == "step5"


def test_normalized_focus_parses_step_token_from_anchor() -> None:
    f = _finding("x", step_id=None, anchor="step7-over-pack")
    assert _normalized_focus(f) == "step7"


def test_normalized_focus_falls_back_to_anchor_then_title() -> None:
    by_anchor = _finding("x", step_id=None, anchor="concept-slug-thing")
    assert _normalized_focus(by_anchor) == "concept-slug-thing"
    by_title = _finding("y", step_id=None, anchor=None, title="A Vague Title Here")
    assert _normalized_focus(by_title) == "a-vague-title-here"


def test_step_token_matches_hyphen_and_plain() -> None:
    assert _step_token("step5-x") == 5
    assert _step_token("step-5-x") == 5
    assert _step_token("over-packed-step") is None
    assert _step_token(None) is None


# --- matching tiers ---------------------------------------------------------- #


def test_match_tier1_step_focus_authoritative() -> None:
    a = _finding("a", step_id=5, title="totally unrelated wording")
    b = _finding("b", step_id=5, title="nothing alike at all here")
    assert _matches(a, b)
    c = _finding("c", step_id=7, title="totally unrelated wording")
    assert not _matches(c, b)


def test_match_tier2_anchor_equality() -> None:
    same_a = _finding("a", anchor="cross-cutting-concept", title="alpha")
    same_b = _finding("b", anchor="cross-cutting-concept", title="omega")
    assert _matches(same_a, same_b)
    differ_a = _finding("a", anchor="concept-one", title="alpha")
    differ_b = _finding("b", anchor="concept-two", title="omega")
    assert not _matches(differ_a, differ_b)


def test_match_tier3_title_similarity_cutoff() -> None:
    base = "Step five packs schema migration and api into one step here"
    near = base.replace("here", "now")  # tiny edit -> well above cutoff
    a = _finding("a", anchor=None, title=base)
    b = _finding("b", anchor=None, title=near)
    assert _matches(a, b)
    from plan_tool.convergence_diagnosis import _title_ratio, _title_slug

    assert _title_ratio(_title_slug(base), _title_slug(near)) >= TITLE_SIMILARITY_CUTOFF
    far_a = _finding("a", anchor=None, title="alpha beta gamma delta")
    far_b = _finding("b", anchor=None, title="zulu yankee xray whiskey")
    assert not _matches(far_a, far_b)


# --- partitioning ------------------------------------------------------------ #


def test_partition_series_completeness_by_kind() -> None:
    history = ReportHistory(
        plan_slug="p",
        plan_path="x.md",
        runs=[
            _snapshot([_finding("a")], created_at="2026-06-01T09:00:00Z"),
            _snapshot([_finding("b")], created_at="2026-06-02T09:00:00Z"),
        ],
    )
    series = partition_series(history)
    assert list(series.keys()) == [("completeness",)]
    assert len(series[("completeness",)]) == 2


def test_partition_reconcile_by_kind_and_step_id() -> None:
    history = ReportHistory(
        plan_slug="p",
        plan_path="x.md",
        runs=[
            _snapshot([_finding("a", source="detail-reconcile", step_id=3)],
                      kind="detail-reconcile", step_id=3),
            _snapshot([_finding("b", source="detail-reconcile", step_id=4)],
                      kind="detail-reconcile", step_id=4),
        ],
    )
    series = partition_series(history)
    assert set(series.keys()) == {("detail-reconcile", 3), ("detail-reconcile", 4)}


# --------------------------------------------------------------------------- #
# Verdict: three states + fingerprint streak
# --------------------------------------------------------------------------- #


def _fp_snapshot(
    rec_id: str,
    *,
    step_id: int,
    plan_fingerprint: str,
    code_fingerprint: dict[str, str] | None = None,
    created_at: str,
) -> RunSnapshot:
    """A completeness snapshot with explicit fingerprints for the path-(b) tests."""
    return RunSnapshot(
        kind="completeness",
        step_id=None,
        created_at=created_at,
        plan_fingerprint=plan_fingerprint,
        code_fingerprint=code_fingerprint or {},
        code_fingerprint_present=bool(code_fingerprint),
        report_bytes=100,
        findings=[_finding(rec_id, step_id=step_id)],
        annotations={},
    )


def test_series_converging_path_a_full_window_no_trip() -> None:
    snaps = [
        _snapshot([_finding("a", step_id=5)], created_at="2026-06-01T09:00:00Z"),
        _snapshot([_finding("b", step_id=6)], created_at="2026-06-02T09:00:00Z"),
        _snapshot([_finding("c", step_id=7)], created_at="2026-06-03T09:00:00Z"),
    ]
    assert diagnose_convergence(_history(snaps)).verdict == VERDICT_CONVERGING


def test_series_converges_when_matching_finding_is_missing_from_latest_run() -> None:
    snaps = [
        _snapshot([_finding("a", step_id=5)], created_at="2026-06-01T09:00:00Z"),
        _snapshot([_finding("b", step_id=5)], created_at="2026-06-02T09:00:00Z"),
        _snapshot([], created_at="2026-06-03T09:00:00Z"),
    ]
    series = diagnose_convergence(_history(snaps)).series[0]
    assert series.verdict == VERDICT_CONVERGING


def test_series_converging_path_b_fingerprint_stable_substhreshold() -> None:
    snaps = [
        _fp_snapshot("a", step_id=5, plan_fingerprint="fp", created_at="2026-06-01T09:00:00Z"),
        _fp_snapshot("b", step_id=6, plan_fingerprint="fp", created_at="2026-06-02T09:00:00Z"),
    ]
    assert diagnose_convergence(_history(snaps)).verdict == VERDICT_CONVERGING


def test_path_b_ignores_unset_plan_fingerprint() -> None:
    snaps = [
        _fp_snapshot("a", step_id=5, plan_fingerprint="", created_at="2026-06-01T09:00:00Z"),
        _fp_snapshot("b", step_id=6, plan_fingerprint="", created_at="2026-06-02T09:00:00Z"),
    ]
    assert diagnose_convergence(_history(snaps)).verdict == VERDICT_INSUFFICIENT_HISTORY


def test_path_b_code_fingerprint_optional() -> None:
    # Empty code_fingerprint certifies on plan fingerprint alone.
    optional = [
        _fp_snapshot("a", step_id=5, plan_fingerprint="fp", code_fingerprint={},
                     created_at="2026-06-01T09:00:00Z"),
        _fp_snapshot("b", step_id=6, plan_fingerprint="fp", code_fingerprint={},
                     created_at="2026-06-02T09:00:00Z"),
    ]
    assert diagnose_convergence(_history(optional)).verdict == VERDICT_CONVERGING
    # Differing non-empty code_fingerprint blocks the streak.
    blocked = [
        _fp_snapshot("a", step_id=5, plan_fingerprint="fp", code_fingerprint={"f": "h1"},
                     created_at="2026-06-01T09:00:00Z"),
        _fp_snapshot("b", step_id=6, plan_fingerprint="fp", code_fingerprint={"f": "h2"},
                     created_at="2026-06-02T09:00:00Z"),
    ]
    assert diagnose_convergence(_history(blocked)).verdict == VERDICT_INSUFFICIENT_HISTORY


def test_path_b_blocked_by_recurring_structural_finding() -> None:
    # Same step focus (5) + structural source (the ``_finding`` default,
    # "granularity-split") on both runs -> recurs across the streak, so the
    # sub-threshold fingerprint-stable streak must not certify converging.
    snaps = [
        _fp_snapshot("a", step_id=5, plan_fingerprint="fp", created_at="2026-06-01T09:00:00Z"),
        _fp_snapshot("a2", step_id=5, plan_fingerprint="fp", created_at="2026-06-02T09:00:00Z"),
    ]
    assert diagnose_convergence(_history(snaps)).verdict == VERDICT_INSUFFICIENT_HISTORY


def test_path_b_ignores_recurring_nonstructural_finding() -> None:
    # Same step focus (5) but a nonstructural source (e.g. plan-completeness)
    # never blocks the streak — matches the pre-#251 scope, where
    # ``recurring_regions`` only ever admitted structural+blocking findings.
    def _snapshot_with(rec_id: str, created_at: str) -> RunSnapshot:
        return RunSnapshot(
            kind="completeness",
            step_id=None,
            created_at=created_at,
            plan_fingerprint="fp",
            code_fingerprint={},
            code_fingerprint_present=False,
            report_bytes=100,
            findings=[_finding(rec_id, source="plan-completeness", step_id=5)],
            annotations={},
        )

    snaps = [
        _snapshot_with("a", "2026-06-01T09:00:00Z"),
        _snapshot_with("b", "2026-06-02T09:00:00Z"),
    ]
    assert diagnose_convergence(_history(snaps)).verdict == VERDICT_CONVERGING


def test_structural_recurs_in_streak_requires_two_distinct_runs() -> None:
    same_run = [_finding("a", step_id=5), _finding("b", step_id=5)]
    snaps = [_snapshot(same_run, created_at="2026-06-01T09:00:00Z")]
    # Both findings land in run 0 only -> one distinct run, not a recurrence.
    assert not _structural_recurs_in_streak(snaps, [0])

    across_runs = [
        _snapshot([_finding("a", step_id=5)], created_at="2026-06-01T09:00:00Z"),
        _snapshot([_finding("b", step_id=5)], created_at="2026-06-02T09:00:00Z"),
    ]
    assert _structural_recurs_in_streak(across_runs, [0, 1])


def test_series_insufficient_history_substhreshold_churning() -> None:
    snaps = [
        _fp_snapshot("a", step_id=5, plan_fingerprint="fp1", created_at="2026-06-01T09:00:00Z"),
        _fp_snapshot("b", step_id=6, plan_fingerprint="fp2", created_at="2026-06-02T09:00:00Z"),
    ]
    assert diagnose_convergence(_history(snaps)).verdict == VERDICT_INSUFFICIENT_HISTORY


def test_diagnose_no_history_empty_reports() -> None:
    diagnosis = diagnose_convergence(_history([]))
    assert isinstance(diagnosis, ConvergenceDiagnosis)
    assert diagnosis.verdict == VERDICT_NO_HISTORY
    assert diagnosis.series == ()


# --- worst-of headline ----------------------------------------------------- #


def _reconcile_snapshot(rec_id: str, *, step_id: int, created_at: str) -> RunSnapshot:
    # Unset plan fingerprint: a short streak of these must never accidentally
    # certify via the fingerprint-stability path (test_headline_converging_
    # outranks_insufficient wants a genuine run-count insufficient-history).
    return _snapshot(
        [_finding(rec_id, source="granularity-split", step_id=step_id)],
        kind="detail-reconcile",
        step_id=step_id,
        created_at=created_at,
        plan_fingerprint="",
    )


def test_series_uses_own_run_count_not_global_history() -> None:
    reconcile = [
        _reconcile_snapshot("r0", step_id=5, created_at="2026-06-01T09:00:00Z"),
        _reconcile_snapshot("r1", step_id=5, created_at="2026-06-02T09:00:00Z"),
        _reconcile_snapshot("r2", step_id=5, created_at="2026-06-03T09:00:00Z"),
    ]
    newer_completeness = [
        _snapshot([], created_at="2026-06-04T09:00:00Z"),
    ]
    diagnosis = diagnose_convergence(_history(reconcile + newer_completeness))
    by_kind = {series.kind: series.verdict for series in diagnosis.series}
    assert by_kind["detail-reconcile"] == VERDICT_CONVERGING
    assert by_kind["completeness"] == VERDICT_INSUFFICIENT_HISTORY
    assert diagnosis.verdict == VERDICT_CONVERGING
    # Same finder scoped to the same step (5) across all 3 full-window runs:
    # a real recurring structural finding, surfaced as the advisory without
    # downgrading the verdict.
    assert len(diagnosis.structural_recurrence) == 1
    assert diagnosis.structural_recurrence[0].kind == "detail-reconcile"


def test_series_converging_path_a_full_window_no_recurrence() -> None:
    # Companion to test_series_converging_path_a_full_window_no_trip: distinct
    # step ids each run -> no recurrence -> no structural_recurrence advisory.
    snaps = [
        _snapshot([_finding("a", step_id=5)], created_at="2026-06-01T09:00:00Z"),
        _snapshot([_finding("b", step_id=6)], created_at="2026-06-02T09:00:00Z"),
        _snapshot([_finding("c", step_id=7)], created_at="2026-06-03T09:00:00Z"),
    ]
    diagnosis = diagnose_convergence(_history(snaps))
    assert diagnosis.verdict == VERDICT_CONVERGING
    assert diagnosis.structural_recurrence == ()


def test_headline_converging_outranks_insufficient() -> None:
    completeness = [
        _snapshot([_finding("c0", anchor="step6-x")], created_at="2026-06-01T09:00:00Z"),
        _snapshot([_finding("c1", anchor="step7-x")], created_at="2026-06-02T09:00:00Z"),
        _snapshot([_finding("c2", anchor="step8-x")], created_at="2026-06-03T09:00:00Z"),
    ]
    # Distinct (unset) plan fingerprints so a short 2-run streak doesn't
    # accidentally certify via the fingerprint-stability path.
    reconcile = [
        _reconcile_snapshot("r0", step_id=5, created_at="2026-06-01T09:00:00Z"),
        _reconcile_snapshot("r1", step_id=5, created_at="2026-06-02T09:00:00Z"),
    ]
    diagnosis = diagnose_convergence(_history(completeness + reconcile))
    assert diagnosis.verdict == VERDICT_CONVERGING
    by_kind = {s.kind: s.verdict for s in diagnosis.series}
    assert by_kind["completeness"] == VERDICT_CONVERGING
    assert by_kind["detail-reconcile"] == VERDICT_INSUFFICIENT_HISTORY


def test_window_keyword_shrinks_threshold() -> None:
    # The ``window`` keyword lets a 2-run series read converging without 3 runs.
    snaps = [
        _snapshot([_finding("a", step_id=5)], created_at="2026-06-01T09:00:00Z"),
        _snapshot([_finding("b", step_id=5)], created_at="2026-06-02T09:00:00Z"),
    ]
    assert diagnose_convergence(_history(snaps), window=2).verdict == VERDICT_CONVERGING
    assert diagnose_convergence(_history(snaps)).window == WINDOW_SIZE


def test_window_one_with_staged_completeness_history_has_no_cross_pass_advisories(
    tmp_path: Path,
) -> None:
    """A one-pass diagnosis is valid but lacks cross-pass evidence."""
    only = Recommendation(
        id="only",
        source="plan-completeness",
        severity="medium",
        step_id=None,
        title="Only high-impact observation",
        body="…",
        impact="high",
    )
    _save(tmp_path, recs=[only], when=_dt(1), audit_stage="bare")

    diagnosis = diagnose_convergence(
        load_report_history(_plan_abs(tmp_path)), window=1
    )

    assert diagnosis.verdict == VERDICT_CONVERGING
    assert diagnosis.impact_recurrence is None
    assert diagnosis.edit_drift is None


def test_series_diagnosis_shape() -> None:
    snaps = [
        _snapshot([_finding("a", step_id=5)], created_at="2026-06-01T09:00:00Z"),
        _snapshot([_finding("b", step_id=5)], created_at="2026-06-02T09:00:00Z"),
        _snapshot([_finding("c", step_id=5)], created_at="2026-06-03T09:00:00Z"),
    ]
    series = diagnose_convergence(_history(snaps)).series[0]
    assert isinstance(series, SeriesDiagnosis)
    assert series.key == ("completeness",)
    assert series.run_count == 3
    assert series.verdict == VERDICT_CONVERGING


# --- render_diagnosis ------------------------------------------------------ #


def _series(
    verdict: str,
    *,
    kind: str = "completeness",
    step_id: int | None = None,
    run_count: int = 3,
) -> SeriesDiagnosis:
    return SeriesDiagnosis(
        key=(kind,) if step_id is None else (kind, step_id),
        kind=kind,
        step_id=step_id,
        verdict=verdict,
        run_count=run_count,
    )


def _diag(
    series: tuple[SeriesDiagnosis, ...],
    *,
    verdict: str,
    plan_slug: str = "spinner",
    window: int = WINDOW_SIZE,
    impact_recurrence: ImpactRecurrenceAdvisory | None = None,
    edit_drift: EditDriftAdvisory | None = None,
) -> ConvergenceDiagnosis:
    return ConvergenceDiagnosis(
        plan_slug=plan_slug,
        verdict=verdict,
        window=window,
        series=series,
        impact_recurrence=impact_recurrence,
        edit_drift=edit_drift,
    )


def test_render_no_history_names_eligible_final_history_only() -> None:
    out = render_diagnosis(_diag((), verdict=VERDICT_NO_HISTORY))
    assert VERDICT_NO_HISTORY in out
    assert "eligible ordinary-final completeness or reconcile history sidecars" in out


def test_render_insufficient_history() -> None:
    series = _series(VERDICT_INSUFFICIENT_HISTORY, run_count=2)
    out = render_diagnosis(_diag((series,), verdict=VERDICT_INSUFFICIENT_HISTORY))
    assert "2 of 3" in out


def test_render_converging() -> None:
    out = render_diagnosis(_diag((_series(VERDICT_CONVERGING),), verdict=VERDICT_CONVERGING))
    assert "converging" in out


def test_render_includes_per_series_breakdown() -> None:
    completeness = _series(VERDICT_CONVERGING)
    reconcile = _series(
        VERDICT_INSUFFICIENT_HISTORY,
        kind="detail-reconcile",
        step_id=5,
        run_count=1,
    )
    out = render_diagnosis(_diag((completeness, reconcile), verdict=VERDICT_CONVERGING))
    lines = out.splitlines()
    assert lines[0].startswith("convergence: converging")
    assert lines[1] == f"  completeness: {VERDICT_CONVERGING} (3 audits)"
    assert lines[2] == f"  detail-reconcile/step 5: {VERDICT_INSUFFICIENT_HISTORY} (1 audit)"


def test_render_reads_plan_slug_from_diagnosis() -> None:
    out = render_diagnosis(_diag((_series(VERDICT_CONVERGING),), verdict=VERDICT_CONVERGING, plan_slug="my-plan"))
    assert "my-plan" in out


# --- newest-run advisory: blocking findings + code-drift recommendation ----- #
#
# The verdict is a run-count/fingerprint signal; by design it reads
# ``converging`` even when the newest audit just surfaced a fresh,
# unresolved critical. These cover the leaves that let the render flag that
# and recommend a fix WITHOUT altering the verdict.


def _hist(runs: list[RunSnapshot]) -> ReportHistory:
    return ReportHistory(plan_slug="spinner", plan_path=_PLAN_REL, runs=runs)


# --- _latest_blocking_findings --------------------------------------------- #


def test_latest_blocking_empty_history() -> None:
    assert _latest_blocking_findings(_hist([])) == ()


def test_latest_blocking_keeps_only_newest_run_critical_high() -> None:
    older = _snapshot([_finding("old", severity="critical")], created_at="2026-06-01T09:00:00Z")
    newest = _snapshot(
        [
            _finding("c", severity="critical"),
            _finding("h", severity="high"),
            _finding("m", severity="medium"),
            _finding("n", severity="nit"),
        ],
        created_at="2026-06-02T09:00:00Z",
    )
    blocking = _latest_blocking_findings(_hist([older, newest]))
    # newest-run only; medium/nit dropped; the older critical excluded.
    assert {f.id for f in blocking} == {"c", "h"}


def test_latest_blocking_severity_match_is_case_insensitive() -> None:
    newest = _snapshot([_finding("c", severity="CRITICAL"), _finding("h", severity="High")])
    assert {f.id for f in _latest_blocking_findings(_hist([newest]))} == {"c", "h"}


def test_latest_blocking_keeps_nonstructural_source() -> None:
    # plan-completeness is nonstructural but IS what completeness-apply's gap
    # walk resolves — a structural source gate would wrongly drop it (review F1).
    newest = _snapshot([_finding("g", severity="critical", source="plan-completeness")])
    assert {f.id for f in _latest_blocking_findings(_hist([newest]))} == {"g"}


def test_latest_blocking_excludes_resolved_annotations() -> None:
    # Review finding (independent): completeness-apply rewrites the SAME report
    # in place, keeping recommendations verbatim and only adding annotations. A
    # finding marked applied or declined (decline-close) is no longer open and
    # must not drive the advisory; a drift-halt skip and open/unreached stay live.
    newest = _snapshot(
        [
            _finding("applied", severity="critical"),
            _finding("declined", severity="critical"),
            _finding("drifthalt", severity="critical"),
            _finding("open", severity="critical"),
        ],
        annotations={
            "applied": Annotation(status="applied"),
            "declined": Annotation(status="skip", halt_reason=""),
            "drifthalt": Annotation(status="skip", halt_reason="drift"),
            "open": Annotation(status="open"),
        },
    )
    assert {f.id for f in _latest_blocking_findings(_hist([newest]))} == {"drifthalt", "open"}


def test_render_no_advisory_when_all_blocking_resolved() -> None:
    # The F1 false positive: an applied critical with no drift must not fire.
    newest = _snapshot(
        [_finding("c", severity="critical")],
        annotations={"c": Annotation(status="applied")},
    )
    diagnosis = diagnose_convergence(_hist([newest]))
    assert diagnosis.latest_blocking == ()
    assert "⚠" not in render_diagnosis(diagnosis)


# --- _code_drifted_since_prior --------------------------------------------- #


def test_code_drift_false_with_single_run() -> None:
    one = _snapshot([], code_fingerprint={"a.py": "1"})
    assert _code_drifted_since_prior(_hist([one])) is False


def test_code_drift_true_when_newest_differs_from_prior() -> None:
    prior = _snapshot([], code_fingerprint={"a.py": "1"}, created_at="2026-06-01T09:00:00Z")
    newest = _snapshot([], code_fingerprint={"a.py": "2"}, created_at="2026-06-02T09:00:00Z")
    assert _code_drifted_since_prior(_hist([prior, newest])) is True


def test_code_drift_false_when_fingerprints_equal() -> None:
    fp = {"a.py": "1"}
    prior = _snapshot([], code_fingerprint=fp, created_at="2026-06-01T09:00:00Z")
    newest = _snapshot([], code_fingerprint=dict(fp), created_at="2026-06-02T09:00:00Z")
    assert _code_drifted_since_prior(_hist([prior, newest])) is False


def test_code_drift_true_for_computed_empty_to_populated() -> None:
    # F2: a computed-but-empty prior (docs-only plan) gaining files IS drift —
    # gate on code_fingerprint_present, not dict truthiness.
    prior = _snapshot([], code_fingerprint={}, created_at="2026-06-01T09:00:00Z")
    newest = _snapshot([], code_fingerprint={"a.py": "1"}, created_at="2026-06-02T09:00:00Z")
    assert _code_drifted_since_prior(_hist([prior, newest])) is True


def test_code_drift_false_when_a_fingerprint_uncomputed() -> None:
    # F2: an uncomputed (present=False) fingerprint is not evidence either way.
    prior = _snapshot(
        [], code_fingerprint={}, code_fingerprint_present=False, created_at="2026-06-01T09:00:00Z"
    )
    newest = _snapshot([], code_fingerprint={"a.py": "1"}, created_at="2026-06-02T09:00:00Z")
    assert _code_drifted_since_prior(_hist([prior, newest])) is False


def test_code_drift_compares_same_kind_only() -> None:
    # F3: the prior must be the prior run of the SAME kind — a reconcile sidecar
    # between two completeness runs must not become the drift baseline.
    older_c = _snapshot([], kind="completeness", code_fingerprint={"a.py": "1"}, created_at="2026-06-01T09:00:00Z")
    mid_r = _snapshot([], kind="detail-reconcile", code_fingerprint={"z.py": "9"}, created_at="2026-06-02T09:00:00Z")
    newest_c = _snapshot([], kind="completeness", code_fingerprint={"a.py": "1"}, created_at="2026-06-03T09:00:00Z")
    # newest completeness == prior completeness fingerprint → no drift, despite
    # the interleaved reconcile run carrying a different fingerprint.
    assert _code_drifted_since_prior(_hist([older_c, mid_r, newest_c])) is False


def test_code_drift_false_when_no_same_kind_prior() -> None:
    prior_r = _snapshot([], kind="detail-reconcile", code_fingerprint={"z.py": "9"}, created_at="2026-06-01T09:00:00Z")
    newest_c = _snapshot([], kind="completeness", code_fingerprint={"a.py": "1"}, created_at="2026-06-02T09:00:00Z")
    assert _code_drifted_since_prior(_hist([prior_r, newest_c])) is False


def test_diagnose_populates_blocking_and_drift() -> None:
    prior = _snapshot(
        [_finding("c0", severity="critical", source="plan-correctness")],
        code_fingerprint={"a.py": "1"},
        created_at="2026-06-01T09:00:00Z",
    )
    newest = _snapshot(
        [_finding("c1", severity="critical", source="plan-correctness")],
        code_fingerprint={"a.py": "2"},
        created_at="2026-06-02T09:00:00Z",
    )
    diagnosis = diagnose_convergence(_hist([prior, newest]))
    assert diagnosis.code_drift is True
    assert {f.id for f in diagnosis.latest_blocking} == {"c1"}


# --- finding trajectory ---------------------------------------------------- #


def test_finding_churn_flags_rising_relocated_findings_without_changing_verdict() -> None:
    """A growing, more-severe non-recurring series remains converging.

    The new signal is informational only: it tells the operator not to
    mistake a rising open-finding count for a settling audit loop.
    """
    runs = [
        _snapshot(
            [_finding("old", step_id=1, severity="medium")],
            created_at="2026-06-01T09:00:00Z",
        ),
        _snapshot(
            [
                _finding("mid-1", step_id=2, severity="medium"),
                _finding("mid-2", step_id=3, severity="medium"),
            ],
            created_at="2026-06-02T09:00:00Z",
        ),
        _snapshot(
            [
                _finding("new-1", step_id=4, severity="high"),
                _finding("new-2", step_id=5, severity="medium"),
                _finding("new-3", step_id=6, severity="medium"),
            ],
            created_at="2026-06-03T09:00:00Z",
        ),
    ]
    diagnosis = diagnose_convergence(_hist(runs))

    assert diagnosis.verdict == VERDICT_CONVERGING
    assert diagnosis.finding_churn == FindingChurn(
        kind="completeness",
        prior_open_count=2,
        latest_open_count=3,
        prior_ceiling="medium",
        latest_ceiling="high",
    )
    rendered = render_diagnosis(diagnosis)
    assert "from 2 to 3" in rendered
    assert "measure the source before adding another iteration" in rendered
    assert "not a re-decomposition signal" in rendered


def test_structural_recurrence_flags_full_window_recurrence_without_changing_verdict() -> None:
    """A full-window series whose same structural finding never resolves stays
    converging, but renders the re-decomposition advisory (BACKLOG #251's
    retired ``spinning`` verdict does not come back)."""
    runs = [
        _snapshot([_finding("a", step_id=5)], created_at="2026-06-01T09:00:00Z"),
        _snapshot([_finding("b", step_id=5)], created_at="2026-06-02T09:00:00Z"),
        _snapshot([_finding("c", step_id=5)], created_at="2026-06-03T09:00:00Z"),
    ]
    diagnosis = diagnose_convergence(_hist(runs))

    assert diagnosis.verdict == VERDICT_CONVERGING
    assert len(diagnosis.structural_recurrence) == 1
    assert diagnosis.structural_recurrence[0].verdict == VERDICT_CONVERGING
    rendered = render_diagnosis(diagnosis)
    assert "converging" in rendered
    assert "recurred across the trailing window" in rendered
    assert "re-splitting the step or `plan-tool scope-out`" in rendered


# --- BACKLOG #166: redecomposition step-count span --------------------- #


def test_redecomposition_step_counts_fires_on_varying_known_counts() -> None:
    snapshots = [
        _snapshot([], step_ids=tuple(range(18))),
        _snapshot([], step_ids=tuple(range(10))),
        _snapshot([], step_ids=tuple(range(6))),
    ]
    assert _redecomposition_step_counts(snapshots, [0, 1, 2]) == (18, 10, 6)


def test_redecomposition_step_counts_empty_when_ids_agree() -> None:
    snapshots = [_snapshot([], step_ids=(1, 2, 3)) for _ in range(3)]
    assert _redecomposition_step_counts(snapshots, [0, 1, 2]) == ()


def test_redecomposition_step_counts_fires_when_ids_change_at_same_count() -> None:
    snapshots = [
        _snapshot([], step_ids=(1, 2, 3)),
        _snapshot([], step_ids=(7, 8, 9)),
        _snapshot([], step_ids=(10, 11, 12)),
    ]
    assert _redecomposition_step_counts(snapshots, [0, 1, 2]) == (3, 3, 3)


def test_redecomposition_step_counts_skips_unknown_sentinel() -> None:
    """A ``()`` snapshot (legacy history, or a save-time parse failure) is
    skipped rather than treated as a mismatch — it must not falsely flag
    every full-window series computed before BACKLOG #166 shipped."""
    snapshots = [
        _snapshot([], step_ids=()),
        _snapshot([], step_ids=(1, 2, 3)),
        _snapshot([], step_ids=()),
    ]
    assert _redecomposition_step_counts(snapshots, [0, 1, 2]) == ()


def test_redecomposition_step_counts_requires_two_known_values() -> None:
    snapshots = [_snapshot([], step_ids=()), _snapshot([], step_ids=(1, 2))]
    assert _redecomposition_step_counts(snapshots, [0, 1]) == ()


def test_redecomposition_span_labels_full_window_without_changing_verdict_or_run_count() -> None:
    """The concrete historical evidence BACKLOG #166 was written against: an
    18-step, a 10-step, and a 6-step version of one plan, one audit each.
    The full-window path certifies ``converging`` unconditionally on run
    count alone — this only labels that certification, it never excludes a
    run or denies it (contrast the sub-threshold fingerprint-streak path,
    which is already immune by construction)."""
    runs = [
        _snapshot([], created_at="2026-06-01T09:00:00Z", step_ids=tuple(range(18))),
        _snapshot([], created_at="2026-06-02T09:00:00Z", step_ids=tuple(range(10))),
        _snapshot([], created_at="2026-06-03T09:00:00Z", step_ids=tuple(range(6))),
    ]
    diagnosis = diagnose_convergence(_hist(runs))

    assert diagnosis.verdict == VERDICT_CONVERGING
    assert diagnosis.series[0].run_count == 3
    assert len(diagnosis.redecomposition_span) == 1
    assert diagnosis.redecomposition_span[0].redecomposition_step_counts == (18, 10, 6)
    rendered = render_diagnosis(diagnosis)
    assert "converging" in rendered
    assert "step IDs varied across runs (step counts: 18 → 10 → 6)" in rendered
    assert "may span a re-decomposition" in rendered


def test_redecomposition_span_labels_same_count_identity_changes() -> None:
    runs = [
        _snapshot([], created_at="2026-06-01T09:00:00Z", step_ids=(1, 2, 3)),
        _snapshot([], created_at="2026-06-02T09:00:00Z", step_ids=(7, 8, 9)),
        _snapshot([], created_at="2026-06-03T09:00:00Z", step_ids=(10, 11, 12)),
    ]

    diagnosis = diagnose_convergence(_hist(runs))

    assert diagnosis.redecomposition_span[0].redecomposition_step_counts == (3, 3, 3)
    assert "step IDs varied across runs (step counts: 3 → 3 → 3)" in render_diagnosis(
        diagnosis
    )


def test_redecomposition_span_silent_when_step_ids_agree() -> None:
    runs = [
        _snapshot([], created_at="2026-06-01T09:00:00Z", step_ids=(1, 2, 3)),
        _snapshot([], created_at="2026-06-02T09:00:00Z", step_ids=(1, 2, 3)),
        _snapshot([], created_at="2026-06-03T09:00:00Z", step_ids=(1, 2, 3)),
    ]
    diagnosis = diagnose_convergence(_hist(runs))

    assert diagnosis.verdict == VERDICT_CONVERGING
    assert diagnosis.redecomposition_span == ()
    assert "step IDs varied" not in render_diagnosis(diagnosis)


def test_redecomposition_span_silent_on_legacy_history_without_step_ids() -> None:
    """Pre-#166 history (every snapshot's ``step_ids`` is the unset
    sentinel) must not retroactively flag every full-window series."""
    runs = [
        _snapshot([], created_at="2026-06-01T09:00:00Z"),
        _snapshot([], created_at="2026-06-02T09:00:00Z"),
        _snapshot([], created_at="2026-06-03T09:00:00Z"),
    ]
    diagnosis = diagnose_convergence(_hist(runs))

    assert diagnosis.verdict == VERDICT_CONVERGING
    assert diagnosis.redecomposition_span == ()


def test_redecomposition_span_fires_but_does_not_exclude_a_one_step_change() -> None:
    """A plan that gains one step between runs keeps its full trajectory —
    this labels the run, it never shrinks ``run_count`` or the verdict
    (BACKLOG #166's stated risk: over-aggressive invalidation must not
    destroy a legitimate one-step-growth history)."""
    runs = [
        _snapshot([], created_at="2026-06-01T09:00:00Z", step_ids=tuple(range(10))),
        _snapshot([], created_at="2026-06-02T09:00:00Z", step_ids=tuple(range(11))),
        _snapshot([], created_at="2026-06-03T09:00:00Z", step_ids=tuple(range(11))),
    ]
    diagnosis = diagnose_convergence(_hist(runs))

    assert diagnosis.verdict == VERDICT_CONVERGING
    assert diagnosis.series[0].run_count == 3
    assert diagnosis.redecomposition_span[0].redecomposition_step_counts == (10, 11, 11)


def test_redecomposition_span_scoped_to_full_window_not_fingerprint_streak() -> None:
    """The sub-threshold certification path requires an identical whole-plan
    fingerprint across its streak, which already makes a step-count
    difference impossible — so this signal is only computed on the
    full-window path, matching ``structural_recurrence``'s scoping."""
    runs = [
        _snapshot(
            [],
            created_at="2026-06-01T09:00:00Z",
            plan_fingerprint="stable",
            step_ids=(1, 2, 3),
        ),
        _snapshot(
            [],
            created_at="2026-06-02T09:00:00Z",
            plan_fingerprint="stable",
            step_ids=(1, 2, 3),
        ),
    ]
    diagnosis = diagnose_convergence(_hist(runs), window=3)

    assert diagnosis.verdict == VERDICT_CONVERGING  # fingerprint-stable streak
    assert diagnosis.series[0].run_count == 2  # sub-threshold: below window
    assert diagnosis.redecomposition_span == ()


def test_finding_churn_uses_same_kind_open_findings_only() -> None:
    prior = _snapshot(
        [_finding("closed", severity="medium")],
        created_at="2026-06-01T09:00:00Z",
        annotations={"closed": Annotation(status="applied")},
    )
    intervening = _snapshot(
        [_finding("other", severity="critical")],
        kind="detail-reconcile",
        step_id=1,
        created_at="2026-06-02T09:00:00Z",
    )
    newest = _snapshot(
        [_finding("new", severity="critical")],
        created_at="2026-06-03T09:00:00Z",
    )
    assert (
        _finding_churn(_hist([prior, intervening, newest]), audit_stage=STAGE_DETAIL)
        is None
    )


def test_finding_churn_ranks_nit_above_info_for_the_medium_floor() -> None:
    """Sub-medium severities are excluded, not merely ranked below medium.

    Pins the carve that the shared ``is_blocking`` floor owns: a run whose
    findings are all ``nit``/``info`` contributes no open evidence, so no
    trajectory can be computed off it however the counts move.
    """
    runs = [
        _snapshot(
            [_finding("n1", severity="nit"), _finding("i1", severity="info")],
            created_at="2026-06-01T09:00:00Z",
        ),
        _snapshot(
            [
                _finding("n2", severity="nit"),
                _finding("i2", severity="info"),
                _finding("i3", severity="info"),
            ],
            created_at="2026-06-02T09:00:00Z",
        ),
    ]
    assert _finding_churn(_hist(runs), audit_stage=STAGE_DETAIL) is None


def test_open_medium_plus_demotes_docs_domain_at_detail_stage() -> None:
    """``_open_medium_plus`` agrees with ``completeness-audit``'s stage bar.

    Regression for the disagreement where ``completeness-audit`` correctly
    demotes a medium docs-domain conceptual finding (not blocking, not open
    backlog) while ``plan-tool convergence`` still counted the identical
    finding as an open medium+ blocker via the old blanket ``is_blocking``
    floor. A real ``classify_domain`` callback must actually change the
    result, or this pins nothing.
    """
    snapshot = _snapshot(
        [
            _finding(
                "docs-1",
                severity="medium",
                source="plan-completeness",
                domain="docs",
            )
        ]
    )
    classify_domain = lambda f: f.domain or "unknown"  # noqa: E731
    assert (
        _open_medium_plus(
            snapshot, audit_stage=STAGE_DETAIL, classify_domain=classify_domain
        )
        == ()
    )
    # Without a real classifier (the pre-fix default), the same finding reads
    # as unknown-domain and blocks -- confirming the assertion above actually
    # exercises the demotion rather than being a vacuous no-op.
    assert len(_open_medium_plus(snapshot, audit_stage=STAGE_DETAIL)) == 1


def test_diagnose_convergence_default_domain_fn_shared_with_finding_churn(
    monkeypatch,
) -> None:
    """Default domain callback reaches finding_churn, not only edit-drift."""
    seen: list[object] = []
    real = _finding_churn

    def _spy(history, *, audit_stage, classify_domain=None):
        seen.append(classify_domain)
        return real(
            history, audit_stage=audit_stage, classify_domain=classify_domain
        )

    monkeypatch.setattr(
        "plan_tool.convergence_diagnosis._finding_churn", _spy
    )
    diagnose_convergence(
        _hist(
            [
                _snapshot(
                    [_finding("x", severity="medium")],
                    created_at="2026-06-01T09:00:00Z",
                    audit_stage=STAGE_DETAIL,
                )
            ]
        ),
        audit_stage=STAGE_DETAIL,
    )
    assert len(seen) == 1
    domain_fn = seen[0]
    assert callable(domain_fn)
    assert domain_fn(_finding("docs", domain="docs")) == "docs"
    assert domain_fn(_finding("blank", domain=None)) == "unknown"


# --- render advisory ------------------------------------------------------- #


def _adv_diag(
    *,
    latest_blocking: tuple[RunFinding, ...],
    code_drift: bool,
    finding_churn: FindingChurn | None = None,
    impact_recurrence: ImpactRecurrenceAdvisory | None = None,
    edit_drift: EditDriftAdvisory | None = None,
    verdict: str = VERDICT_CONVERGING,
) -> ConvergenceDiagnosis:
    return ConvergenceDiagnosis(
        plan_slug="spinner",
        verdict=verdict,
        window=WINDOW_SIZE,
        series=(_series(verdict),),
        latest_blocking=latest_blocking,
        code_drift=code_drift,
        finding_churn=finding_churn,
        impact_recurrence=impact_recurrence,
        edit_drift=edit_drift,
    )


def test_render_no_advisory_without_blocking_or_drift() -> None:
    out = render_diagnosis(_adv_diag(latest_blocking=(), code_drift=False))
    assert "⚠" not in out
    assert "reconcile-plan" not in out


def test_render_advisory_recommends_reconcile_on_drift() -> None:
    blocking = (_finding("c", severity="critical"), _finding("h", severity="high"))
    out = render_diagnosis(_adv_diag(latest_blocking=blocking, code_drift=True))
    # verdict line is unchanged…
    assert out.splitlines()[0].startswith(f"convergence: {VERDICT_CONVERGING}")
    assert "The audit/apply loop is converging; no re-decomposition needed." in out
    # …and the advisory makes the rebase recommendation, tying the findings to
    # the drift (coherent head+body — review finding F2).
    assert "⚠" in out
    assert "1 critical, 1 high" in out
    assert "stale-baseline artifacts" in out
    assert "Rebase against current code" in out
    assert "plan-tool reconcile-plan spinner" in out
    assert "completeness-apply" not in out


def test_render_advisory_points_at_report_without_drift() -> None:
    # F1: no over-claimed command — the resolving verb is source-dependent.
    out = render_diagnosis(_adv_diag(latest_blocking=(_finding("h", severity="high"),), code_drift=False))
    assert "⚠" in out
    assert "1 high" in out
    assert "see the saved report" in out
    assert "reconcile-plan" not in out
    assert "completeness-apply" not in out
    assert "stale against current code" not in out


def test_render_drift_only_advisory_without_blocking() -> None:
    # F7: code drifted but no current blocking finding still hints a rebase.
    out = render_diagnosis(_adv_diag(latest_blocking=(), code_drift=True))
    assert "⚠ Code moved under the plan" in out
    assert "()" not in out  # F8: no empty breakdown parenthetical
    assert "plan-tool reconcile-plan spinner" in out


def test_render_advisory_always_shown_regardless_of_verdict() -> None:
    # Advisories are newest-run signals independent of the verdict: they are
    # shown on every verdict, including insufficient-history.
    out = render_diagnosis(
        _adv_diag(
            latest_blocking=(_finding("c", severity="critical"),),
            code_drift=True,
            verdict=VERDICT_INSUFFICIENT_HISTORY,
        )
    )
    assert out.splitlines()[0].startswith(f"convergence: {VERDICT_INSUFFICIENT_HISTORY}")
    assert "⚠" in out
    assert "reconcile-plan" in out


def test_render_advisory_wording_verdict_agnostic_under_insufficient_history() -> None:
    # F6: the advisory must not claim "loop dynamics" under insufficient-history.
    out = render_diagnosis(
        _adv_diag(
            latest_blocking=(_finding("c", severity="critical"),),
            code_drift=False,
            verdict=VERDICT_INSUFFICIENT_HISTORY,
        )
    )
    assert "loop dynamics" not in out
    assert "not a run-readiness gate" in out


def test_snapshot_carries_audit_stage_from_saved_review(tmp_path: Path) -> None:
    _save(tmp_path, recs=[_completeness_rec("a")], when=_dt(1), audit_stage="detail")
    history = load_report_history(_plan_abs(tmp_path))
    assert history.runs[-1].audit_stage == "detail"


def test_collapsed_passes_exclude_reconcile_kinds(tmp_path: Path) -> None:
    _save(tmp_path, recs=[_completeness_rec("c1")], when=_dt(1), audit_stage="bare")
    _save(
        tmp_path,
        recs=[_reconcile_rec("r1", 5)],
        kind="detail-reconcile",
        when=_dt(2),
        step_id=5,
        audit_stage=None,
    )
    passes = build_collapsed_completeness_passes(load_report_history(_plan_abs(tmp_path)))
    assert len(passes) == 1
    assert passes[0].audit_stage == "bare"


def test_collapsed_passes_exclude_missing_audit_stage(tmp_path: Path) -> None:
    path = _save(tmp_path, recs=[_completeness_rec("legacy")], when=_dt(1))
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("audit_stage", None)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    assert load_review(path).audit_stage is None
    assert build_collapsed_completeness_passes(load_report_history(_plan_abs(tmp_path))) == ()


def test_stage_change_breaks_compatible_sequence(tmp_path: Path) -> None:
    _save(tmp_path, recs=[_completeness_rec("b1")], when=_dt(1), audit_stage="bare")
    _save(tmp_path, recs=[_completeness_rec("b2")], when=_dt(2), audit_stage="bare")
    _save(tmp_path, recs=[_completeness_rec("d1")], when=_dt(3), audit_stage="detail")
    passes = build_collapsed_completeness_passes(load_report_history(_plan_abs(tmp_path)))
    assert len(passes) == 3
    assert [p.audit_stage for p in passes] == ["bare", "bare", "detail"]


def test_adjacent_identical_id_sets_collapse(tmp_path: Path) -> None:
    rec = _completeness_rec("same-id")
    _save(tmp_path, recs=[rec], when=_dt(1), audit_stage="bare")
    _save(tmp_path, recs=[rec], when=_dt(2), audit_stage="bare")
    passes = build_collapsed_completeness_passes(load_report_history(_plan_abs(tmp_path)))
    assert len(passes) == 1
    assert passes[0].collapsed_count == 2

    _save(tmp_path, recs=[_completeness_rec("other")], when=_dt(3), audit_stage="bare")
    passes = build_collapsed_completeness_passes(load_report_history(_plan_abs(tmp_path)))
    assert len(passes) == 2


def test_adjacent_collapse_merges_annotations_from_older_final(tmp_path: Path) -> None:
    rec = _completeness_rec("reuse-id")
    _save(
        tmp_path,
        recs=[rec],
        when=_dt(1),
        audit_stage="bare",
        annotations={"reuse-id": Annotation(status="applied")},
    )
    _save(tmp_path, recs=[rec], when=_dt(2), audit_stage="bare")
    passes = build_collapsed_completeness_passes(load_report_history(_plan_abs(tmp_path)))
    assert passes[0].annotations["reuse-id"].status == "applied"


def test_adjacent_collapse_terminal_beats_newer_non_terminal(tmp_path: Path) -> None:
    rec = _completeness_rec("terminal-id")
    _save(
        tmp_path,
        recs=[rec],
        when=_dt(1),
        audit_stage="bare",
        annotations={"terminal-id": Annotation(status="skip", halt_reason="")},
    )
    _save(
        tmp_path,
        recs=[rec],
        when=_dt(2),
        audit_stage="bare",
        annotations={"terminal-id": Annotation(status="open")},
    )
    passes = build_collapsed_completeness_passes(load_report_history(_plan_abs(tmp_path)))
    assert passes[0].annotations["terminal-id"].status == "skip"
    assert passes[0].annotations["terminal-id"].halt_reason == ""


def test_checkpoint_final_pair_not_double_counted(tmp_path: Path) -> None:
    checkpoint = _save(
        tmp_path,
        recs=[_completeness_rec("chk")],
        when=_dt(1),
        audit_stage="bare",
        is_pre_apply_checkpoint=True,
    )
    _save(tmp_path, recs=[_completeness_rec("chk")], when=_dt(2), audit_stage="bare")
    history = load_report_history(_plan_abs(tmp_path))
    assert len(history.runs) == 1
    passes = build_collapsed_completeness_passes(history)
    assert len(passes) == 1
    assert load_review(checkpoint).is_pre_apply_checkpoint is True


# --------------------------------------------------------------------------- #
# Impact-recurrence classifier
# --------------------------------------------------------------------------- #


def _high_impact_rec(
    rec_id: str,
    *,
    anchor: str = "step5-over-pack",
    title: str = "Step 5 packs too much",
) -> Recommendation:
    return _completeness_rec(rec_id, anchor, title=title, impact="high")


def _impact_history(tmp_path: Path, *pass_specs: list[Recommendation]) -> ReportHistory:
    for day, recs in enumerate(pass_specs, start=1):
        _save(tmp_path, recs=recs, when=_dt(day), audit_stage="bare")
    return load_report_history(_plan_abs(tmp_path))


class TestImpactRecurrenceClassifier:
    def test_impact_recurrence_fires_on_three_pass_stable_seam(
        self, tmp_path: Path
    ) -> None:
        seam = _high_impact_rec("p1")
        history = _impact_history(
            tmp_path,
            [seam],
            [_high_impact_rec("p2", anchor=seam.anchor)],
            [_high_impact_rec("p3", anchor=seam.anchor)],
        )
        advisory = classify_impact_recurrence(history)
        assert isinstance(advisory, ImpactRecurrenceAdvisory)
        assert advisory.passes_present == 3
        assert advisory.newest_matched_count >= 1
        assert advisory.window_audit_stage == "bare"
        assert advisory.seam_anchor == seam.anchor

    def test_impact_recurrence_tie_break_most_passes_then_count_then_key(
        self, tmp_path: Path
    ) -> None:
        seam_a = _high_impact_rec("a1", anchor="concept-alpha", title="Alpha gap")
        seam_b = _high_impact_rec(
            "b1", anchor="concept-beta", title="Beta gap needs more detail"
        )
        history = _impact_history(
            tmp_path,
            [seam_a, seam_b],
            [_high_impact_rec("a2", anchor=seam_a.anchor), _high_impact_rec("b2", anchor=seam_b.anchor)],
            [
                _high_impact_rec("a3", anchor=seam_a.anchor),
                _high_impact_rec("a3b", anchor=seam_a.anchor, title="Alpha gap restated"),
                _high_impact_rec("b3", anchor=seam_b.anchor),
            ],
        )
        advisory = classify_impact_recurrence(history)
        assert advisory is not None
        assert advisory.seam_anchor == seam_a.anchor
        assert advisory.newest_matched_count == 2

        history_key = _impact_history(
            tmp_path,
            [_high_impact_rec("z1", anchor="aaa-first", title="Same count tie")],
            [_high_impact_rec("z2", anchor="aaa-first", title="Same count tie")],
            [
                _high_impact_rec("z3a", anchor="aaa-first", title="Same count tie"),
                _high_impact_rec(
                    "z3b",
                    anchor="zzz-second",
                    title="Same count tie on other seam",
                ),
            ],
        )
        key_advisory = classify_impact_recurrence(history_key)
        assert key_advisory is not None
        assert key_advisory.seam_anchor == "aaa-first"

        history_passes = _impact_history(
            tmp_path,
            [_high_impact_rec("w1", anchor="win-a")],
            [_high_impact_rec("w2", anchor="win-a")],
            [_high_impact_rec("w3", anchor="win-a")],
            [_high_impact_rec("w4a", anchor="win-a"), _high_impact_rec("w4b", anchor="win-b")],
        )
        passes_advisory = classify_impact_recurrence(history_passes, window=4)
        assert passes_advisory is not None
        assert passes_advisory.seam_anchor == "win-a"
        assert passes_advisory.passes_present == 4

    def test_impact_recurrence_no_fire_when_impact_not_high(
        self, tmp_path: Path
    ) -> None:
        seam = _completeness_rec("p1", impact=None)
        history_none = _impact_history(
            tmp_path,
            [seam],
            [_completeness_rec("p2", impact=None)],
            [_completeness_rec("p3", impact=None)],
        )
        assert classify_impact_recurrence(history_none) is None

        for impact in ("medium", "low"):
            history = _impact_history(
                tmp_path,
                [_completeness_rec("m1", impact=impact)],
                [_completeness_rec("m2", impact=impact)],
                [_completeness_rec("m3", impact=impact)],
            )
            assert classify_impact_recurrence(history) is None

    def test_impact_recurrence_no_fire_on_shrinkage(self, tmp_path: Path) -> None:
        seam = _high_impact_rec("s1")
        history = _impact_history(
            tmp_path,
            [seam, _high_impact_rec("s1b", anchor=seam.anchor, title=seam.title)],
            [seam],
            [_high_impact_rec("s3", anchor=seam.anchor)],
        )
        assert classify_impact_recurrence(history) is None

    def test_impact_recurrence_partial_close_still_present_does_not_shrink(
        self, tmp_path: Path
    ) -> None:
        open_rec = _high_impact_rec("open")
        closed_rec = _high_impact_rec("closed", title="Step 5 packs too much detail")
        annotations = {"closed": Annotation(status="applied")}
        _save(tmp_path, recs=[open_rec, closed_rec], when=_dt(1), audit_stage="bare")
        _save(
            tmp_path,
            recs=[_high_impact_rec("p2"), _high_impact_rec("p2b", title=closed_rec.title)],
            when=_dt(2),
            audit_stage="bare",
            annotations=annotations,
        )
        _save(
            tmp_path,
            recs=[_high_impact_rec("p3"), _high_impact_rec("p3b", title=closed_rec.title)],
            when=_dt(3),
            audit_stage="bare",
            annotations=annotations,
        )
        advisory = classify_impact_recurrence(load_report_history(_plan_abs(tmp_path)))
        assert advisory is not None
        assert advisory.passes_present == 3
        assert advisory.newest_matched_count == 2

    def test_impact_recurrence_no_fire_when_resolved_in_newest(
        self, tmp_path: Path
    ) -> None:
        seam = _high_impact_rec("r1")
        annotations = {"r3": Annotation(status="applied")}
        _save(tmp_path, recs=[seam], when=_dt(1), audit_stage="bare")
        _save(
            tmp_path,
            recs=[_high_impact_rec("r2", anchor=seam.anchor)],
            when=_dt(2),
            audit_stage="bare",
        )
        _save(
            tmp_path,
            recs=[_high_impact_rec("r3", anchor=seam.anchor)],
            when=_dt(3),
            audit_stage="bare",
            annotations=annotations,
        )
        assert classify_impact_recurrence(load_report_history(_plan_abs(tmp_path))) is None

        decline_annotations = {"d3": Annotation(status="skip", halt_reason="")}
        _save(tmp_path, recs=[seam], when=_dt(4), audit_stage="bare")
        _save(
            tmp_path,
            recs=[_high_impact_rec("d2", anchor=seam.anchor)],
            when=_dt(5),
            audit_stage="bare",
        )
        _save(
            tmp_path,
            recs=[_high_impact_rec("d3", anchor=seam.anchor)],
            when=_dt(6),
            audit_stage="bare",
            annotations=decline_annotations,
        )
        assert classify_impact_recurrence(load_report_history(_plan_abs(tmp_path))) is None

    def test_impact_recurrence_no_fire_when_fewer_than_three_compatible_passes(
        self, tmp_path: Path
    ) -> None:
        seam = _high_impact_rec("few1")
        history = _impact_history(
            tmp_path,
            [seam],
            [_high_impact_rec("few2", anchor=seam.anchor)],
        )
        assert classify_impact_recurrence(history) is None

    def test_impact_recurrence_no_fire_on_stage_boundary(
        self, tmp_path: Path
    ) -> None:
        seam = _high_impact_rec("stage1")
        _save(tmp_path, recs=[seam], when=_dt(1), audit_stage="bare")
        _save(
            tmp_path,
            recs=[_high_impact_rec("stage2", anchor=seam.anchor)],
            when=_dt(2),
            audit_stage="bare",
        )
        _save(
            tmp_path,
            recs=[_high_impact_rec("stage3", anchor=seam.anchor)],
            when=_dt(3),
            audit_stage="detail",
        )
        assert classify_impact_recurrence(load_report_history(_plan_abs(tmp_path))) is None

    def test_impact_recurrence_reuse_collapse_not_triple_confirm(
        self, tmp_path: Path
    ) -> None:
        rec = _high_impact_rec("reuse")
        _save(tmp_path, recs=[rec], when=_dt(1), audit_stage="bare")
        _save(tmp_path, recs=[rec], when=_dt(2), audit_stage="bare")
        _save(tmp_path, recs=[_high_impact_rec("other")], when=_dt(3), audit_stage="bare")
        assert classify_impact_recurrence(load_report_history(_plan_abs(tmp_path))) is None

    def test_impact_recurrence_uses_matches_not_raw_id(self, tmp_path: Path) -> None:
        base_title = "Step five packs schema migration and api into one step here"
        near_title = base_title.replace("here", "now")
        _save(
            tmp_path,
            recs=[_high_impact_rec("old", anchor=None, title=base_title)],
            when=_dt(1),
            audit_stage="bare",
        )
        _save(
            tmp_path,
            recs=[_high_impact_rec("mid", anchor=None, title=base_title)],
            when=_dt(2),
            audit_stage="bare",
        )
        _save(
            tmp_path,
            recs=[_high_impact_rec("brand-new-id", anchor=None, title=near_title)],
            when=_dt(3),
            audit_stage="bare",
        )
        from plan_tool.convergence_diagnosis import _title_ratio, _title_slug

        assert (
            _title_ratio(_title_slug(base_title), _title_slug(near_title))
            >= TITLE_SIMILARITY_CUTOFF
        )
        advisory = classify_impact_recurrence(load_report_history(_plan_abs(tmp_path)))
        assert advisory is not None
        assert advisory.passes_present == 3
        assert advisory.seam_title_slug == _title_slug(base_title)

    def test_impact_recurrence_classifier_imports_no_retired_fork_apis(self) -> None:
        import inspect

        import plan_tool.convergence_diagnosis as mod

        names = (
            "classify_impact_recurrence",
            "_impact_recurrence_trailing_window",
            "_matched_high_impact_count",
            "_has_open_high_impact_match",
            "_build_impact_seam_representatives",
            "_impact_recurrence_shrinkage_ok",
            "_seam_sort_key",
        )
        source = "".join(inspect.getsource(getattr(mod, name)) for name in names)
        forbidden = (
            "RegionTrend",
            "classify_fork",
            "recurring_regions",
            "FORK_",
            "spinning",
        )
        for token in forbidden:
            assert token not in source


# --------------------------------------------------------------------------- #
# Edit-drift classifier
# --------------------------------------------------------------------------- #


def _correctness_rec(
    rec_id: str,
    *,
    anchor: str = "step5-gap",
    title: str = "Plan contradicts code",
    severity: str = "medium",
) -> Recommendation:
    return Recommendation(
        id=rec_id,
        source="plan-correctness",
        severity=severity,
        step_id=None,
        title=title,
        body="…",
        anchor=anchor,
    )


def _edit_drift_history(tmp_path: Path, *pass_specs: list[Recommendation], **kwargs) -> ReportHistory:
    annotations_list: list[dict[str, Annotation] | None] = kwargs.pop(
        "annotations_list", [None] * len(pass_specs)
    )
    audit_stage = kwargs.pop("audit_stage", "bare")
    for day, (recs, day_annotations) in enumerate(
        zip(pass_specs, annotations_list, strict=True), start=1
    ):
        _save(
            tmp_path,
            recs=recs,
            when=_dt(day),
            audit_stage=audit_stage,
            annotations=day_annotations,
            **kwargs,
        )
    return load_report_history(_plan_abs(tmp_path))


class TestEditDriftClassifier:
    def test_edit_drift_fires_on_strict_majority_match(self, tmp_path: Path) -> None:
        gone = _correctness_rec("gone", anchor="vanished-gap", title="Vanished gap")
        applied = _correctness_rec("applied", anchor="applied-gap", title="Applied gap")
        history = _edit_drift_history(
            tmp_path,
            [gone, applied],
            [_correctness_rec("carry1")],
            [
                _correctness_rec("new1", anchor="vanished-gap", title="Vanished gap restated"),
                _correctness_rec("new2", anchor="applied-gap", title="Applied gap restated"),
                _correctness_rec("new3", anchor="fresh-gap", title="Fresh unrelated gap"),
            ],
            annotations_list=[
                {"applied": Annotation(status="applied")},
                None,
                None,
            ],
        )
        advisory = classify_edit_drift(history)
        assert isinstance(advisory, EditDriftAdvisory)
        assert advisory.matched_count == 2
        assert advisory.new_eligible_count == 3
        assert advisory.window_audit_stage == "bare"
        assert {f.id for f in advisory.matched_findings} == {"new1", "new2"}

    def test_edit_drift_decline_close_joins_prior_apply(self, tmp_path: Path) -> None:
        declined = _correctness_rec("declined", anchor="declined-gap", title="Declined gap")
        history = _edit_drift_history(
            tmp_path,
            [declined],
            [_correctness_rec("carry1")],
            [
                _correctness_rec("n1", anchor="declined-gap", title="Declined gap restated"),
                _correctness_rec("n2", anchor="declined-gap", title="Declined gap again"),
                _correctness_rec("n3", anchor="other-gap", title="Unrelated gap here"),
            ],
            annotations_list=[
                {"declined": Annotation(status="skip", halt_reason="")},
                None,
                None,
            ],
        )
        advisory = classify_edit_drift(history)
        assert advisory is not None
        assert advisory.matched_count == 2
        assert advisory.new_eligible_count == 3

    def test_edit_drift_no_fire_on_minority_match(self, tmp_path: Path) -> None:
        applied = _correctness_rec("applied", anchor="applied-gap")
        history = _edit_drift_history(
            tmp_path,
            [applied],
            [_correctness_rec("carry1")],
            [
                _correctness_rec("n1", anchor="applied-gap", title="Applied gap restated"),
                _correctness_rec("n2", anchor="fresh-a", title="Fresh gap alpha"),
                _correctness_rec("n3", anchor="fresh-b", title="Fresh gap beta"),
            ],
            annotations_list=[
                {"applied": Annotation(status="applied")},
                None,
                None,
            ],
        )
        assert classify_edit_drift(history) is None

    def test_edit_drift_no_fire_when_zero_new_eligible(self, tmp_path: Path) -> None:
        stable = _correctness_rec("stable")
        history_same = _edit_drift_history(
            tmp_path,
            [stable],
            [stable],
            [stable],
        )
        assert classify_edit_drift(history_same) is None

        history_ineligible = _edit_drift_history(
            tmp_path,
            [_completeness_rec("p0")],
            [_completeness_rec("p1")],
            [
                _completeness_rec("new1"),
                _completeness_rec("new2"),
            ],
        )
        assert classify_edit_drift(history_ineligible) is None

    def test_edit_drift_rested_finding_not_new(self, tmp_path: Path) -> None:
        restated = _correctness_rec("old-id", anchor="same-gap", title="Same conceptual gap")
        history = _edit_drift_history(
            tmp_path,
            [_correctness_rec("p0")],
            [restated],
            [
                _correctness_rec("brand-new-id", anchor="same-gap", title="Same conceptual gap"),
            ],
        )
        assert classify_edit_drift(history) is None

    def test_edit_drift_no_fire_when_fewer_than_three_compatible_passes(
        self, tmp_path: Path
    ) -> None:
        seam = _correctness_rec("few1")
        history = _edit_drift_history(
            tmp_path,
            [seam],
            [_correctness_rec("few2", anchor=seam.anchor)],
        )
        assert classify_edit_drift(history) is None

    def test_edit_drift_no_fire_on_stage_boundary(self, tmp_path: Path) -> None:
        seam = _correctness_rec("stage1")
        _save(tmp_path, recs=[seam], when=_dt(1), audit_stage="bare")
        _save(
            tmp_path,
            recs=[_correctness_rec("stage2", anchor=seam.anchor)],
            when=_dt(2),
            audit_stage="bare",
        )
        _save(
            tmp_path,
            recs=[
                _correctness_rec("stage3a", anchor=seam.anchor),
                _correctness_rec("stage3b", anchor="other"),
                _correctness_rec("stage3c", anchor="another"),
            ],
            when=_dt(3),
            audit_stage="detail",
        )
        assert classify_edit_drift(load_report_history(_plan_abs(tmp_path))) is None

    def test_edit_drift_bare_stage_medium_completeness_excluded(
        self, tmp_path: Path
    ) -> None:
        applied = _completeness_rec("applied")
        history = _edit_drift_history(
            tmp_path,
            [applied],
            [_completeness_rec("carry1")],
            [
                _completeness_rec("n1", anchor=applied.anchor),
                _completeness_rec("n2", anchor="other-a"),
                _completeness_rec("n3", anchor="other-b"),
            ],
            annotations_list=[
                {"applied": Annotation(status="applied")},
                None,
                None,
            ],
        )
        assert classify_edit_drift(history) is None

    def test_edit_drift_bare_stage_medium_data_contract_still_eligible(
        self, tmp_path: Path
    ) -> None:
        applied = Recommendation(
            id="dc-applied",
            source="data-contract",
            severity="medium",
            step_id=None,
            title="Applied contract drift",
            body="…",
            anchor="contract-gap",
        )
        history = _edit_drift_history(
            tmp_path,
            [
                Recommendation(
                    id="dc0",
                    source="data-contract",
                    severity="medium",
                    step_id=None,
                    title="Vanished contract drift",
                    body="…",
                    anchor="vanished-contract",
                ),
                applied,
            ],
            [Recommendation(
                id="dc-carry",
                source="data-contract",
                severity="medium",
                step_id=None,
                title="Carry contract drift",
                body="…",
                anchor="carry-contract",
            )],
            [
                Recommendation(
                    id="dc-new1",
                    source="data-contract",
                    severity="medium",
                    step_id=None,
                    title="Vanished contract drift restated",
                    body="…",
                    anchor="vanished-contract",
                ),
                Recommendation(
                    id="dc-new2",
                    source="data-contract",
                    severity="medium",
                    step_id=None,
                    title="Applied contract drift restated",
                    body="…",
                    anchor="contract-gap",
                ),
                Recommendation(
                    id="dc-new3",
                    source="data-contract",
                    severity="medium",
                    step_id=None,
                    title="Fresh contract drift",
                    body="…",
                    anchor="fresh-contract",
                ),
            ],
            annotations_list=[
                {"dc-applied": Annotation(status="applied")},
                None,
                None,
            ],
        )
        advisory = classify_edit_drift(history)
        assert advisory is not None
        assert advisory.matched_count == 2
        assert advisory.new_eligible_count == 3

    def test_edit_drift_detail_stage_docs_domain_demoted(self, tmp_path: Path) -> None:
        docs = Recommendation(
            id="docs1",
            source="plan-completeness",
            severity="medium",
            step_id=None,
            title="Docs gap",
            body="…",
            anchor="docs-gap",
        )
        _save(tmp_path, recs=[docs], when=_dt(1), audit_stage="detail")
        _save(tmp_path, recs=[docs], when=_dt(2), audit_stage="detail")
        _save(
            tmp_path,
            recs=[
                Recommendation(
                    id="docs2",
                    source="plan-completeness",
                    severity="medium",
                    step_id=None,
                    title="Docs gap restated",
                    body="…",
                    anchor="docs-gap",
                ),
                Recommendation(
                    id="docs3",
                    source="plan-completeness",
                    severity="medium",
                    step_id=None,
                    title="Other docs gap",
                    body="…",
                    anchor="docs-other",
                ),
                Recommendation(
                    id="docs4",
                    source="plan-completeness",
                    severity="medium",
                    step_id=None,
                    title="Third docs gap",
                    body="…",
                    anchor="docs-third",
                ),
            ],
            when=_dt(3),
            audit_stage="detail",
        )
        history = load_report_history(_plan_abs(tmp_path))
        classify_domain = lambda f: f.domain or "unknown"  # noqa: E731
        for run in history.runs:
            for finding in run.findings:
                if finding.source in {"plan-completeness", "plan-correctness"}:
                    object.__setattr__(finding, "domain", "docs")
        assert classify_edit_drift(history, classify_domain=classify_domain) is None

    def test_edit_drift_deterministic_only_churn_no_fire(self, tmp_path: Path) -> None:
        history = _edit_drift_history(
            tmp_path,
            [_correctness_rec("p0")],
            [_correctness_rec("p1")],
            [
                Recommendation(
                    id="nit1", source="plan-correctness", severity="nit",
                    step_id=None, title="Nit", body="…", anchor="nit-a",
                ),
                Recommendation(
                    id="info1", source="plan-correctness", severity="info",
                    step_id=None, title="Info", body="…", anchor="info-a",
                ),
            ],
        )
        assert classify_edit_drift(history) is None

    def test_edit_drift_prior_apply_outside_window_ignored(self, tmp_path: Path) -> None:
        old_applied = _correctness_rec("old-applied", anchor="legacy-gap")
        _save(
            tmp_path,
            recs=[old_applied],
            when=_dt(1),
            audit_stage="bare",
            annotations={"old-applied": Annotation(status="applied")},
        )
        _save(tmp_path, recs=[_correctness_rec("p1")], when=_dt(2), audit_stage="bare")
        _save(tmp_path, recs=[_correctness_rec("p2")], when=_dt(3), audit_stage="bare")
        _save(tmp_path, recs=[_correctness_rec("p3")], when=_dt(4), audit_stage="bare")
        _save(
            tmp_path,
            recs=[
                _correctness_rec("n1", anchor="legacy-gap", title="Legacy gap restated"),
                _correctness_rec("n2", anchor="legacy-gap", title="Legacy gap again"),
                _correctness_rec("n3", anchor="other", title="Other gap here"),
            ],
            when=_dt(5),
            audit_stage="bare",
        )
        assert classify_edit_drift(load_report_history(_plan_abs(tmp_path))) is None

    def test_edit_drift_reuse_collapse_not_triple_confirm(self, tmp_path: Path) -> None:
        rec = _correctness_rec("reuse")
        _save(tmp_path, recs=[rec], when=_dt(1), audit_stage="bare")
        _save(tmp_path, recs=[rec], when=_dt(2), audit_stage="bare")
        _save(tmp_path, recs=[_correctness_rec("other")], when=_dt(3), audit_stage="bare")
        assert classify_edit_drift(load_report_history(_plan_abs(tmp_path))) is None

    def test_edit_drift_uses_matches_not_raw_id(self, tmp_path: Path) -> None:
        base_title = "Step five packs schema migration and api into one step here"
        near_title = base_title.replace("here", "now")
        vanished = Recommendation(
            id="prior",
            source="plan-correctness",
            severity="medium",
            step_id=None,
            title=base_title,
            body="…",
            anchor=None,
        )
        _save(tmp_path, recs=[vanished], when=_dt(1), audit_stage="bare")
        _save(tmp_path, recs=[_correctness_rec("carry1")], when=_dt(2), audit_stage="bare")
        _save(
            tmp_path,
            recs=[
                Recommendation(
                    id="brand-new-id",
                    source="plan-correctness",
                    severity="medium",
                    step_id=None,
                    title=near_title,
                    body="…",
                    anchor=None,
                ),
                Recommendation(
                    id="brand-new-id-2",
                    source="plan-correctness",
                    severity="medium",
                    step_id=None,
                    title=base_title.replace("here", "today"),
                    body="…",
                    anchor=None,
                ),
                _correctness_rec("n3", anchor="fresh-b", title="Fresh gap beta"),
            ],
            when=_dt(3),
            audit_stage="bare",
        )
        from plan_tool.convergence_diagnosis import _title_ratio, _title_slug

        assert (
            _title_ratio(_title_slug(base_title), _title_slug(near_title))
            >= TITLE_SIMILARITY_CUTOFF
        )
        advisory = classify_edit_drift(load_report_history(_plan_abs(tmp_path)))
        assert advisory is not None
        assert advisory.matched_count == 2
        assert advisory.new_eligible_count == 3
        assert advisory.matched_findings[0].id == "brand-new-id"

    def test_edit_drift_classifier_imports_no_retired_fork_apis(self) -> None:
        import inspect

        import plan_tool.convergence_diagnosis as mod

        names = (
            "classify_edit_drift",
            "_build_prior_apply_set",
            "_new_findings_vs_prior",
            "_edit_drift_eligible",
        )
        source = "".join(inspect.getsource(getattr(mod, name)) for name in names)
        forbidden = (
            "RegionTrend",
            "classify_fork",
            "recurring_regions",
            "FORK_",
            "spinning",
        )
        for token in forbidden:
            assert token not in source


# --------------------------------------------------------------------------- #
# Impact-recurrence and edit-drift diagnosis wiring
# --------------------------------------------------------------------------- #


def _sample_impact_recurrence() -> ImpactRecurrenceAdvisory:
    return ImpactRecurrenceAdvisory(
        window_audit_stage="bare",
        seam_source="plan-completeness",
        seam_anchor="step5-over-pack",
        seam_step_id=None,
        seam_title_slug="step-5-packs-too-much",
        passes_present=3,
        newest_matched_count=1,
    )


def _sample_edit_drift() -> EditDriftAdvisory:
    return EditDriftAdvisory(
        window_audit_stage="bare",
        matched_findings=(
            RunFinding(
                id="new1",
                source="plan-correctness",
                severity="medium",
                step_id=None,
                anchor="vanished-gap",
                title="Vanished gap restated",
                confidence="supported",
            ),
            RunFinding(
                id="new2",
                source="plan-correctness",
                severity="medium",
                step_id=None,
                anchor="applied-gap",
                title="Applied gap restated",
                confidence=None,
            ),
        ),
        new_eligible_count=3,
        matched_count=2,
    )


def test_diagnose_populates_impact_recurrence_when_classifier_fires(
    tmp_path: Path,
) -> None:
    seam = _high_impact_rec("p1")
    history = _impact_history(
        tmp_path,
        [seam],
        [_high_impact_rec("p2", anchor=seam.anchor)],
        [_high_impact_rec("p3", anchor=seam.anchor)],
    )
    diagnosis = diagnose_convergence(history)
    assert diagnosis.verdict == VERDICT_CONVERGING
    assert diagnosis.impact_recurrence is not None
    assert diagnosis.impact_recurrence.passes_present == 3
    assert diagnosis.impact_recurrence.seam_anchor == seam.anchor
    assert diagnosis.edit_drift is None


def test_diagnose_populates_edit_drift_when_classifier_fires(tmp_path: Path) -> None:
    gone = _correctness_rec("gone", anchor="vanished-gap", title="Vanished gap")
    applied = _correctness_rec("applied", anchor="applied-gap", title="Applied gap")
    history = _edit_drift_history(
        tmp_path,
        [gone, applied],
        [_correctness_rec("carry1")],
        [
            _correctness_rec("new1", anchor="vanished-gap", title="Vanished gap restated"),
            _correctness_rec("new2", anchor="applied-gap", title="Applied gap restated"),
            _correctness_rec("new3", anchor="fresh-gap", title="Fresh unrelated gap"),
        ],
        annotations_list=[
            {"applied": Annotation(status="applied")},
            None,
            None,
        ],
    )
    diagnosis = diagnose_convergence(history)
    assert diagnosis.verdict == VERDICT_CONVERGING
    assert diagnosis.edit_drift is not None
    assert diagnosis.edit_drift.matched_count == 2
    assert diagnosis.edit_drift.new_eligible_count == 3
    assert diagnosis.impact_recurrence is None


def test_diagnose_leaves_advisories_none_when_classifiers_silent(
    tmp_path: Path,
) -> None:
    seam = _high_impact_rec("few1")
    history = _impact_history(
        tmp_path,
        [seam],
        [_high_impact_rec("few2", anchor=seam.anchor)],
    )
    diagnosis = diagnose_convergence(history)
    assert diagnosis.impact_recurrence is None
    assert diagnosis.edit_drift is None


def test_render_impact_recurrence_advisory_names_seam_and_is_recommend_only() -> None:
    advisory = _sample_impact_recurrence()
    out = render_diagnosis(
        _diag(
            (_series(VERDICT_CONVERGING),),
            verdict=VERDICT_CONVERGING,
            impact_recurrence=advisory,
        )
    )
    assert out.splitlines()[0].startswith(f"convergence: {VERDICT_CONVERGING}")
    assert "⚠" in out
    assert "plan-completeness" in out
    assert "step5-over-pack" in out
    assert "session-directed edit" in out
    assert "recommend-only" in out
    assert "run-readiness gate" in out


def test_render_edit_drift_advisory_names_majority_and_matched_findings() -> None:
    advisory = _sample_edit_drift()
    out = render_diagnosis(
        _diag(
            (_series(VERDICT_CONVERGING),),
            verdict=VERDICT_CONVERGING,
            edit_drift=advisory,
        )
    )
    assert "⚠" in out
    assert "2 of 3" in out
    assert "Vanished gap restated" in out
    assert "Evidence support: Vanished gap restated: confidence: supported" in out
    assert "Applied gap restated: confidence: unknown" in out
    assert "auditing your edits" in out
    assert "recommend-only" in out
    assert "run-readiness gate" in out


def test_edit_drift_lines_honor_an_explicit_empty_finding_override() -> None:
    advisory = _sample_edit_drift()

    rendered = "\n".join(_edit_drift_lines(advisory, named_findings=()))

    assert 'Matched findings: .' in rendered
    assert advisory.matched_findings[0].title not in rendered
    assert _capped_finding_titles(()) == ""


def test_capped_confidence_labels_signal_omitted_findings() -> None:
    findings = tuple(
        RunFinding(
            id=f"finding-{i}",
            source="plan-correctness",
            severity="medium",
            step_id=None,
            anchor=None,
            title=f"finding {i}",
            confidence="supported",
        )
        for i in range(5)
    )

    assert _capped_finding_confidence_labels(findings) == (
        "finding 0: confidence: supported; "
        "finding 1: confidence: supported; "
        "finding 2: confidence: supported; and 2 more"
    )


def test_bare_mechanism_advisory_combines_only_same_current_edit_drift_match() -> None:
    exact = _finding(
        "exact",
        source="plan-correctness",
        anchor="step5-serializer",
        title="Select exact serializer",
        likely_bare_mechanism=True,
    )
    similar = _finding(
        "similar",
        source="plan-correctness",
        anchor="step5-serializer",
        title="Select similar serializer",
        likely_bare_mechanism=True,
    )
    advisory = EditDriftAdvisory(
        window_audit_stage=STAGE_BARE,
        matched_findings=(exact,),
        new_eligible_count=1,
        matched_count=1,
    )

    assert _matches(similar, exact)

    lines = compose_mechanism_edit_drift_advisory_lines((exact, similar), advisory)
    rendered = "\n".join(lines)

    assert "Bare-plan mechanism and edit-drift advisory" in rendered
    assert "Select exact serializer" in rendered
    assert "Bare-plan mechanism advisory" in rendered
    assert "Select similar serializer" in rendered


def test_bare_mechanism_advisory_keeps_unrelated_standalone_and_edit_drift_advice() -> None:
    combined = _finding(
        "combined",
        source="plan-correctness",
        title="Select serializer",
        likely_bare_mechanism=True,
    )
    standalone = _finding(
        "standalone",
        source="plan-correctness",
        title="Select carrier",
        likely_bare_mechanism=True,
    )
    drift_only = _finding("drift-only", title="Restated unrelated gap")
    advisory = EditDriftAdvisory(
        window_audit_stage=STAGE_BARE,
        matched_findings=(combined, drift_only),
        new_eligible_count=3,
        matched_count=2,
    )

    rendered = "\n".join(
        compose_mechanism_edit_drift_advisory_lines(
            (combined, standalone), advisory
        )
    )

    assert "Bare-plan mechanism and edit-drift advisory" in rendered
    assert "Bare-plan mechanism advisory" in rendered
    assert "Select carrier" in rendered
    assert "Edit drift" in rendered
    assert "2 of 3" in rendered
    assert 'Matched findings: "Restated unrelated gap".' in rendered


def test_render_combined_mechanism_edit_drift_advisory_is_recommend_only() -> None:
    finding = _finding(
        "mechanism",
        source="plan-correctness",
        title="Select a serializer choice",
        likely_bare_mechanism=True,
    )
    advisory = EditDriftAdvisory(
        window_audit_stage=STAGE_BARE,
        matched_findings=(finding,),
        new_eligible_count=1,
        matched_count=1,
    )
    diagnosis = ConvergenceDiagnosis(
        plan_slug="spinner",
        verdict=VERDICT_INSUFFICIENT_HISTORY,
        window=WINDOW_SIZE,
        series=(_series(VERDICT_INSUFFICIENT_HISTORY, run_count=1),),
        edit_drift=advisory,
        bare_mechanism_findings=(finding,),
    )
    out = render_diagnosis(diagnosis)

    assert "Select a serializer choice" in out
    assert "observable property" in out
    assert "leave the delivery choice to detail" in out
    assert "not causal proof" in out
    assert "recommend-only" in out
    assert out.splitlines()[0].startswith("convergence: insufficient-history")


def test_render_both_advisories_together() -> None:
    out = render_diagnosis(
        _diag(
            (_series(VERDICT_CONVERGING),),
            verdict=VERDICT_CONVERGING,
            impact_recurrence=_sample_impact_recurrence(),
            edit_drift=_sample_edit_drift(),
        )
    )
    assert "High-impact seam recurrence" in out
    assert "Edit drift" in out


def test_render_impact_recurrence_shown_on_insufficient_history_verdict() -> None:
    out = render_diagnosis(
        _diag(
            (_series(VERDICT_INSUFFICIENT_HISTORY, run_count=2),),
            verdict=VERDICT_INSUFFICIENT_HISTORY,
            impact_recurrence=_sample_impact_recurrence(),
        )
    )
    assert out.splitlines()[0].startswith(
        f"convergence: {VERDICT_INSUFFICIENT_HISTORY}"
    )
    assert "High-impact seam recurrence" in out


def test_render_advisory_mutation_deleting_helpers_goes_red(monkeypatch) -> None:
    diagnosis = _diag(
        (_series(VERDICT_CONVERGING),),
        verdict=VERDICT_CONVERGING,
        impact_recurrence=_sample_impact_recurrence(),
        edit_drift=_sample_edit_drift(),
    )
    full = render_diagnosis(diagnosis)
    assert "High-impact seam recurrence" in full
    assert "Edit drift" in full

    import plan_tool.convergence_diagnosis as mod

    monkeypatch.setattr(mod, "_impact_recurrence_lines", lambda *a, **k: [])
    assert "High-impact seam recurrence" not in render_diagnosis(diagnosis)
    monkeypatch.setattr(mod, "_edit_drift_lines", lambda *a, **k: [])
    assert "Edit drift" not in render_diagnosis(diagnosis)


def test_end_to_end_impact_recurrence_through_load_and_render(tmp_path: Path) -> None:
    seam = _high_impact_rec("p1")
    _impact_history(
        tmp_path,
        [seam],
        [_high_impact_rec("p2", anchor=seam.anchor)],
        [_high_impact_rec("p3", anchor=seam.anchor)],
    )
    history = load_report_history(_plan_abs(tmp_path))
    rendered = render_diagnosis(diagnose_convergence(history))
    assert "High-impact seam recurrence" in rendered
    assert "step5-over-pack" in rendered


def test_end_to_end_edit_drift_through_load_and_render(tmp_path: Path) -> None:
    gone = _correctness_rec("gone", anchor="vanished-gap", title="Vanished gap")
    applied = _correctness_rec("applied", anchor="applied-gap", title="Applied gap")
    _edit_drift_history(
        tmp_path,
        [gone, applied],
        [_correctness_rec("carry1")],
        [
            _correctness_rec("new1", anchor="vanished-gap", title="Vanished gap restated"),
            _correctness_rec("new2", anchor="applied-gap", title="Applied gap restated"),
            _correctness_rec("new3", anchor="fresh-gap", title="Fresh unrelated gap"),
        ],
        annotations_list=[
            {"applied": Annotation(status="applied")},
            None,
            None,
        ],
    )
    history = load_report_history(_plan_abs(tmp_path))
    rendered = render_diagnosis(diagnose_convergence(history))
    assert "Edit drift" in rendered
    assert "2 of 3" in rendered
