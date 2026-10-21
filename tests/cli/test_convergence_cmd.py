"""Behavior tests for the read-only ``plan-tool convergence`` handler.

Every case drives the real parse → dispatch → command path through
``main(argv)`` against the ``registered_plan`` conftest fixture, seeding real
report sidecars with :func:`plan_tool.review_persistence.save_review` (not the
pre-normalized JSON fixture, which feeds the engine unit tests). The command is
purely informational: it spends no Claude, mutates nothing, and **always exits
0**.
"""

from __future__ import annotations

from datetime import datetime, timezone

from plan_tool.cli.app import main
from plan_tool.review import Recommendation
from plan_tool.review_persistence import (
    Annotation,
    compute_plan_fingerprint,
    plan_reports_dir,
    save_review,
)


def _dt(day: int) -> datetime:
    return datetime(2026, 6, day, 9, 0, 0, tzinfo=timezone.utc)


def _structural_rec(rec_id: str, anchor: str = "step5-over-pack") -> Recommendation:
    """A structural medium completeness finding anchored to one step."""
    return Recommendation(
        id=rec_id,
        source="granularity-split",
        severity="medium",
        step_id=None,
        title="Step 5 packs too much",
        body="…",
        anchor=anchor,
    )


def _high_impact_rec(
    rec_id: str,
    *,
    anchor: str = "step5-over-pack",
    title: str = "Step 5 packs too much",
) -> Recommendation:
    return Recommendation(
        id=rec_id,
        source="plan-completeness",
        severity="medium",
        step_id=None,
        title=title,
        body="…",
        anchor=anchor,
        impact="high",
    )


def _correctness_rec(
    rec_id: str,
    *,
    anchor: str = "step5-gap",
    title: str = "Plan contradicts code",
) -> Recommendation:
    return Recommendation(
        id=rec_id,
        source="plan-correctness",
        severity="medium",
        step_id=None,
        title=title,
        body="…",
        anchor=anchor,
    )


def _mechanism_rec(
    rec_id: str,
    *,
    anchor: str = "serializer-choice",
    title: str = "Select a serializer choice",
) -> Recommendation:
    """A classified internal delivery-choice correctness finding."""
    return Recommendation(
        id=rec_id,
        source="plan-correctness",
        severity="medium",
        step_id=None,
        title=title,
        body="Use a serializer choice for the internal payload.",
        anchor=anchor,
        suggested_action="Specify the serializer choice in detail.",
    )


def _save(
    repo,
    *,
    recs,
    when,
    kind="completeness",
    step_id=None,
    plan_fingerprint="",
    audit_stage: str | None = "bare",
    annotations: dict[str, Annotation] | None = None,
    audit_grade: str | None = None,
):
    kwargs: dict = {}
    if kind == "completeness" and audit_stage is not None:
        kwargs["audit_stage"] = audit_stage
    if audit_grade is not None:
        from plan_tool.review_persistence import AuditInputSnapshot

        snapshot = AuditInputSnapshot.capture(
            repo.plans_dir / "1-demo.md", repo.root, detail_grade=audit_grade
        )
        kwargs["qualified_result"] = {
            "headline": "awaiting-human-action",
            "stage": audit_stage,
            "coverage": "confirmed",
            "revision_status": "current",
            "audit_revision": snapshot.revision,
        }
    return save_review(
        plan_slug="demo",
        plan_path="plans/1-demo.md",
        repo_root=repo.root,
        report_md="report body\n",
        recommendations=recs,
        annotations=annotations,
        now=when,
        kind=kind,
        step_id=step_id,
        plan_fingerprint=plan_fingerprint,
        **kwargs,
    )


def _seed_three_runs(repo) -> None:
    """Three completeness runs — enough to reach a converging verdict."""
    for i in range(1, 4):
        _save(repo, recs=[_structural_rec(f"c-{i}")], when=_dt(i))


def _write_report_only(repo, timestamp: str = "20260604-090000") -> None:
    """Save a visible non-final artifact without creating history evidence."""
    reports_dir = plan_reports_dir(repo.plans_dir / "1-demo.md")
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / f"{timestamp}-completeness.md").write_text(
        "saved report only\n", encoding="utf-8"
    )


def test_no_history_exits_zero(registered_plan, capsys) -> None:
    rc = main(registered_plan.argv("convergence", "1-demo"))
    out = capsys.readouterr().out
    assert rc == 0
    assert "no-history" in out


def test_convergence_renders_ledger_after_existing_diagnosis(registered_plan, capsys) -> None:
    rc = main(registered_plan.argv("convergence", "1-demo"))
    out = capsys.readouterr().out

    assert rc == 0
    assert out.index("convergence: no-history") < out.index(
        "saved audit evidence ledger: demo"
    )
    assert "no-saved-audits" in out


def test_convergence_visible_nonfinal_ledger_does_not_change_no_history_verdict(
    registered_plan, capsys
) -> None:
    _write_report_only(registered_plan)

    rc = main(registered_plan.argv("convergence", "1-demo"))
    out = capsys.readouterr().out

    assert rc == 0
    assert "convergence: no-history" in out
    assert "report-only: filename time 2026-06-04T09:00:00Z" in out


def test_convergence_malformed_sidecar_is_visible_not_an_error(registered_plan, capsys) -> None:
    sidecar = _save(registered_plan, recs=[], kind="review", when=_dt(4))
    reports_dir = plan_reports_dir(registered_plan.plans_dir / "1-demo.md")
    sidecar.rename(reports_dir / "20260604-090000-completeness.json")
    _write_report_only(registered_plan)

    rc = main(registered_plan.argv("convergence", "1-demo"))
    out = capsys.readouterr().out

    assert rc == 0
    assert "convergence: no-history" in out
    assert "malformed-sidecar: filename time 2026-06-04T09:00:00Z" in out


def test_convergence_loads_each_saved_sidecar_once(
    registered_plan, capsys, monkeypatch
) -> None:
    import plan_tool.cli.convergence_cmd as convergence_cmd
    import plan_tool.convergence_diagnosis as convergence_diagnosis

    sidecars = [
        _save(registered_plan, recs=[], when=_dt(day)) for day in (4, 5, 6)
    ]
    _write_report_only(registered_plan)
    original_load_review = convergence_diagnosis.load_review
    original_list_artifacts = convergence_cmd.list_report_artifacts
    loaded_paths = []
    snapshot_calls = 0

    def counting_load_review(path):
        loaded_paths.append(path)
        return original_load_review(path)

    def counting_list_artifacts(path):
        nonlocal snapshot_calls
        snapshot_calls += 1
        return original_list_artifacts(path)

    monkeypatch.setattr(convergence_diagnosis, "load_review", counting_load_review)
    monkeypatch.setattr(
        convergence_cmd, "list_report_artifacts", counting_list_artifacts
    )

    assert main(registered_plan.argv("convergence", "1-demo")) == 0
    capsys.readouterr()
    assert sorted(loaded_paths) == sorted(sidecars)
    assert len(loaded_paths) == len(sidecars)
    assert snapshot_calls == 1


def test_converging_exits_zero(registered_plan, capsys) -> None:
    _seed_three_runs(registered_plan)
    rc = main(registered_plan.argv("convergence", "1-demo"))
    out = capsys.readouterr().out
    assert rc == 0
    assert "converging" in out


def test_insufficient_history_exits_zero(registered_plan, capsys) -> None:
    _save(registered_plan, recs=[_structural_rec("c-1")], when=_dt(1))
    rc = main(registered_plan.argv("convergence", "1-demo"))
    out = capsys.readouterr().out
    assert rc == 0
    assert "insufficient-history" in out


def test_prints_slug_from_diagnosis(registered_plan, capsys) -> None:
    _seed_three_runs(registered_plan)
    rc = main(registered_plan.argv("convergence", "1-demo"))
    out = capsys.readouterr().out
    assert rc == 0
    # render_diagnosis emits the slug straight off the diagnosis; the handler
    # does not recompute it.
    assert "demo" in out


def test_reads_real_saved_sidecars(registered_plan, capsys) -> None:
    _seed_three_runs(registered_plan)
    reports_dir = (
        registered_plan.plans_dir / "plan-details" / "demo" / "reports"
    )
    assert list(reports_dir.glob("*.json")), "sidecars were not written to disk"
    rc = main(registered_plan.argv("convergence", "1-demo"))
    out = capsys.readouterr().out
    assert rc == 0
    assert "completeness" in out


def test_unknown_plan_errors(registered_plan, capsys) -> None:
    rc = main(registered_plan.argv("convergence", "does-not-exist"))
    assert rc != 0


def test_no_real_backend_spawned(registered_plan, capsys) -> None:
    # Relies on the autouse tests/conftest.py gate that raises if any backend
    # binary is spawned; this test carries no @allow_real_claude marker, so a
    # green run proves the command shells out to no Claude/backend process.
    _seed_three_runs(registered_plan)
    rc = main(registered_plan.argv("convergence", "1-demo"))
    out = capsys.readouterr().out
    assert rc == 0
    assert "saved audit evidence ledger: demo" in out


def test_emits_decision_telemetry(registered_plan, capsys) -> None:
    # Wiring smoke (#72): the convergence verdict is recorded as a decision
    # event for later threshold tuning. Best-effort, so it never affects rc.
    from plan_tool.telemetry import read_decisions

    _seed_three_runs(registered_plan)
    rc = main(registered_plan.argv("convergence", "1-demo"))
    assert rc == 0
    conv = [e for e in read_decisions(registered_plan.root) if e.kind == "convergence"]
    assert len(conv) == 1
    assert conv[0].decision == "diagnosed"
    assert conv[0].plan_slug == "demo"
    assert isinstance(conv[0].context.get("verdict"), str) and conv[0].context["verdict"]
    assert conv[0].context["runs"] == 3


def test_convergence_event_carries_plan_fingerprint(registered_plan) -> None:
    # Phase-2 backfill: the convergence event stamps the plan digest so a later
    # resolver can join on the renumber-proof anchor.
    from plan_tool.telemetry import read_decisions

    _seed_three_runs(registered_plan)
    rc = main(registered_plan.argv("convergence", "1-demo"))
    assert rc == 0
    conv = [e for e in read_decisions(registered_plan.root) if e.kind == "convergence"]
    assert len(conv) == 1
    plan_path = registered_plan.plans_dir / "1-demo.md"
    assert conv[0].plan_fingerprint == compute_plan_fingerprint(plan_path)


def test_convergence_event_has_empty_code_fingerprint(registered_plan) -> None:
    # Convergence carries no code map — the verdict is about report recurrence.
    from plan_tool.telemetry import read_decisions

    _seed_three_runs(registered_plan)
    rc = main(registered_plan.argv("convergence", "1-demo"))
    assert rc == 0
    conv = [e for e in read_decisions(registered_plan.root) if e.kind == "convergence"]
    assert conv[0].code_fingerprint == ""


def test_current_audit_stage_bare_with_no_detail_files(registered_plan) -> None:
    from plan_tool.cli.convergence_cmd import _current_audit_stage
    from plan_tool.cli.context import _load_context
    from plan_tool.convergence import STAGE_BARE
    from plan_tool.jira_grade import GRADE_RUN
    from plan_tool.locator import resolve_plan_for_context

    ctx = _load_context(_ns_for(registered_plan))
    path = resolve_plan_for_context(ctx, "1-demo")
    assert _current_audit_stage(ctx, path, detail_grade=GRADE_RUN) == STAGE_BARE


def test_current_audit_stage_detail_when_step_has_detail_file(registered_plan) -> None:
    from plan_tool.cli.convergence_cmd import _current_audit_stage
    from plan_tool.cli.context import _load_context
    from plan_tool.convergence import STAGE_DETAIL
    from plan_tool.jira_grade import GRADE_RUN
    from plan_tool.locator import resolve_plan_for_context

    plan_path = registered_plan.plans_dir / "1-demo.md"
    detail = plan_path.parent / "plan-details" / "demo" / "01-only-step.md"
    detail.parent.mkdir(parents=True, exist_ok=True)
    detail.write_text("## Summary\n\nDone.\n", encoding="utf-8")

    ctx = _load_context(_ns_for(registered_plan))
    path = resolve_plan_for_context(ctx, "1-demo")
    assert _current_audit_stage(ctx, path, detail_grade=GRADE_RUN) == STAGE_DETAIL


def test_current_audit_stage_detail_at_jira_grade_when_run_grade_is_bare(
    registered_plan,
) -> None:
    """A plan authored/audited only at jira grade must resolve STAGE_DETAIL
    when asked at jira grade, even though it has no run-grade detail file
    (the disagreement `--grade` exists to prevent)."""
    from plan_tool.cli.convergence_cmd import _current_audit_stage
    from plan_tool.cli.context import _load_context
    from plan_tool.convergence import STAGE_BARE, STAGE_DETAIL
    from plan_tool.detail_artifacts import derive_jira_detail_path
    from plan_tool.jira_grade import GRADE_JIRA, GRADE_RUN
    from plan_tool.locator import resolve_plan_for_context
    from plan_tool.parser import parse_plan

    plan_path = registered_plan.plans_dir / "1-demo.md"
    plan = parse_plan(plan_path)
    jira = derive_jira_detail_path(plan_path, plan, plan.steps[0])
    jira.parent.mkdir(parents=True, exist_ok=True)
    jira.write_text(
        "## Intent\n\nShip it.\n\n## Change\n\nAdd the handler.\n\n"
        "## Constraints\n\nNo API change.\n\n"
        "## Done when\n\nThe handler returns 200.\n\n"
        "## Out of scope\n\nThe beta path.\n",
        encoding="utf-8",
    )

    ctx = _load_context(_ns_for(registered_plan))
    path = resolve_plan_for_context(ctx, "1-demo")
    assert _current_audit_stage(ctx, path, detail_grade=GRADE_RUN) == STAGE_BARE
    assert _current_audit_stage(ctx, path, detail_grade=GRADE_JIRA) == STAGE_DETAIL


def test_current_audit_stage_falls_back_to_none_on_unparseable_plan(
    registered_plan,
) -> None:
    from plan_tool.cli.convergence_cmd import _current_audit_stage
    from plan_tool.cli.context import _load_context
    from plan_tool.jira_grade import GRADE_RUN
    from plan_tool.locator import resolve_plan_for_context

    ctx = _load_context(_ns_for(registered_plan))
    path = resolve_plan_for_context(ctx, "1-demo")
    (registered_plan.plans_dir / "1-demo.md").write_text(
        "not a valid plan file", encoding="utf-8"
    )
    assert _current_audit_stage(ctx, path, detail_grade=GRADE_RUN) is None


def test_convergence_agrees_with_completeness_audit_detail_stage_demotion(
    registered_plan, capsys
) -> None:
    """The disagreement this fixes: a medium docs-domain finding that
    ``completeness-audit`` demotes at the detail stage must not read as open
    backlog to ``plan-tool convergence`` either, so a later, genuinely new
    high-severity finding doesn't misreport as "rising churn" relative to a
    docs finding that was never really an open blocker.

    Under the old blanket ``is_blocking`` floor this pair (docs-only ->
    docs+high) reads as open findings rising 1 -> 2 with the ceiling rising
    medium -> high: a churn advisory. With the docs finding correctly
    demoted at the detail stage, the "prior" run has zero open findings, so
    the churn gate's own emptiness check suppresses the advisory instead.
    """
    plan_path = registered_plan.plans_dir / "1-demo.md"
    detail = plan_path.parent / "plan-details" / "demo" / "01-only-step.md"
    detail.parent.mkdir(parents=True, exist_ok=True)
    detail.write_text("## Summary\n\nDone.\n", encoding="utf-8")

    docs_finding = Recommendation(
        id="docs-1",
        source="plan-completeness",
        severity="medium",
        step_id=None,
        title="Doc drift",
        body="Update `docs/RUNBOOK.md` with the new flag.",
    )
    code_finding = Recommendation(
        id="code-1",
        source="plan-correctness",
        severity="high",
        step_id=None,
        title="Real bug",
        body="Fix `plan_tool/foo.py`.",
    )
    _save(registered_plan, recs=[docs_finding], when=_dt(1))
    _save(registered_plan, recs=[docs_finding], when=_dt(2))
    _save(registered_plan, recs=[docs_finding, code_finding], when=_dt(3))

    rc = main(registered_plan.argv("convergence", "1-demo"))
    out = capsys.readouterr().out
    assert rc == 0
    assert "converging" in out
    assert "rose" not in out.lower()
    assert "churning" not in out.lower()


def _ns_for(repo):
    import argparse

    return argparse.Namespace(
        repo_root=repo.root, manifest=repo.manifest_path, plans_dir=None
    )


def test_convergence_fingerprint_failure_keeps_exit_zero(
    registered_plan, capsys, monkeypatch
) -> None:
    # A raising fingerprint compute leaves the always-exits-0 read-only contract
    # and stdout intact; the event still records with an empty fingerprint.
    import plan_tool.cli.convergence_cmd as convergence_cmd
    from plan_tool.telemetry import read_decisions

    def _boom(*a, **k):
        raise RuntimeError("fingerprint blew up")

    _seed_three_runs(registered_plan)
    monkeypatch.setattr(convergence_cmd, "compute_plan_fingerprint", _boom)
    rc = main(registered_plan.argv("convergence", "1-demo"))
    out = capsys.readouterr().out
    assert rc == 0
    assert "converging" in out
    conv = [e for e in read_decisions(registered_plan.root) if e.kind == "convergence"]
    assert len(conv) == 1
    assert conv[0].plan_fingerprint == ""


def _seed_impact_recurrence_runs(repo) -> None:
    seam = _high_impact_rec("p1")
    for day in range(1, 4):
        _save(
            repo,
            recs=[_high_impact_rec(f"p{day}", anchor=seam.anchor)],
            when=_dt(day),
            audit_stage="bare",
        )


def _seed_edit_drift_runs(repo) -> None:
    gone = _correctness_rec("gone", anchor="vanished-gap", title="Vanished gap")
    applied = _correctness_rec("applied", anchor="applied-gap", title="Applied gap")
    _save(
        repo,
        recs=[gone, applied],
        when=_dt(1),
        audit_stage="bare",
        annotations={"applied": Annotation(status="applied")},
    )
    _save(repo, recs=[_correctness_rec("carry1")], when=_dt(2), audit_stage="bare")
    _save(
        repo,
        recs=[
            _correctness_rec("new1", anchor="vanished-gap", title="Vanished gap restated"),
            _correctness_rec("new2", anchor="applied-gap", title="Applied gap restated"),
            _correctness_rec("new3", anchor="fresh-gap", title="Fresh unrelated gap"),
        ],
        when=_dt(3),
        audit_stage="bare",
    )


def test_convergence_prints_impact_recurrence_advisory(registered_plan, capsys) -> None:
    _seed_impact_recurrence_runs(registered_plan)
    rc = main(registered_plan.argv("convergence", "1-demo"))
    out = capsys.readouterr().out
    assert rc == 0
    assert "converging" in out
    assert "High-impact seam recurrence" in out


def test_convergence_ledger_preserves_diagnosis_advisories_and_eligible_run_count(
    registered_plan, capsys
) -> None:
    from plan_tool.telemetry import read_decisions

    _seed_impact_recurrence_runs(registered_plan)
    _write_report_only(registered_plan)

    rc = main(registered_plan.argv("convergence", "1-demo"))
    out = capsys.readouterr().out
    events = [
        event
        for event in read_decisions(registered_plan.root)
        if event.kind == "convergence"
    ]

    assert rc == 0
    assert "convergence: converging" in out
    assert "High-impact seam recurrence" in out
    assert "report-only: filename time 2026-06-04T09:00:00Z" in out
    assert len(events) == 1
    assert events[0].context["runs"] == 3


def test_convergence_prints_edit_drift_advisory(registered_plan, capsys) -> None:
    _seed_edit_drift_runs(registered_plan)
    rc = main(registered_plan.argv("convergence", "1-demo"))
    out = capsys.readouterr().out
    assert rc == 0
    assert "Edit drift" in out


def test_convergence_prints_standalone_mechanism_advisory_after_one_bare_pass(
    registered_plan, capsys
) -> None:
    from plan_tool.jira_grade import GRADE_RUN

    _save(
        registered_plan,
        recs=[_mechanism_rec("mechanism")],
        when=_dt(1),
        audit_grade=GRADE_RUN,
    )

    rc = main(registered_plan.argv("convergence", "1-demo"))
    out = capsys.readouterr().out

    assert rc == 0
    assert "insufficient-history" in out
    assert "Bare-plan mechanism advisory" in out


def test_convergence_prints_combined_mechanism_edit_drift_advisory(
    registered_plan, capsys
) -> None:
    from plan_tool.jira_grade import GRADE_RUN

    _save(
        registered_plan,
        recs=[
            _mechanism_rec("gone", anchor="serializer-choice"),
            _correctness_rec("applied", anchor="applied-gap", title="Applied gap"),
        ],
        when=_dt(1),
        annotations={"applied": Annotation(status="applied")},
        audit_grade=GRADE_RUN,
    )
    _save(
        registered_plan,
        recs=[_correctness_rec("carry", anchor="carry-gap")],
        when=_dt(2),
        audit_grade=GRADE_RUN,
    )
    _save(
        registered_plan,
        recs=[
            _mechanism_rec("new-mechanism", anchor="serializer-choice"),
            _correctness_rec("new-drift", anchor="applied-gap", title="Applied gap restated"),
            _correctness_rec("fresh", anchor="fresh-gap", title="Fresh unrelated gap"),
        ],
        when=_dt(3),
        audit_grade=GRADE_RUN,
    )

    rc = main(registered_plan.argv("convergence", "1-demo"))
    out = capsys.readouterr().out

    assert rc == 0
    assert "Bare-plan mechanism and edit-drift advisory" in out
    assert "Select a serializer choice" in out
    assert "\n⚠ Bare-plan mechanism advisory:" not in out
    assert 'Matched findings: "Applied gap restated".' in out


def test_convergence_jira_grade_suppresses_mechanism_advisory(
    registered_plan, capsys
) -> None:
    from plan_tool.jira_grade import GRADE_RUN

    _save(
        registered_plan,
        recs=[_mechanism_rec("mechanism")],
        when=_dt(1),
        audit_grade=GRADE_RUN,
    )
    reports_dir = registered_plan.plans_dir / "plan-details" / "demo" / "reports"
    saved_before = {path.name: path.read_bytes() for path in reports_dir.glob("*.json")}

    rc = main(registered_plan.argv("convergence", "1-demo", "--grade", "jira"))
    out = capsys.readouterr().out

    saved_after = {path.name: path.read_bytes() for path in reports_dir.glob("*.json")}
    assert rc == 0
    assert "insufficient-history" in out
    assert "Bare-plan mechanism" not in out
    assert saved_after == saved_before


def test_convergence_parse_failure_still_passes_classify_domain(
    registered_plan, capsys, monkeypatch
) -> None:
    import plan_tool.cli.convergence_cmd as convergence_cmd

    plan_path = registered_plan.plans_dir / "1-demo.md"
    detail = plan_path.parent / "plan-details" / "demo" / "01-only-step.md"
    detail.parent.mkdir(parents=True, exist_ok=True)
    detail.write_text("## Summary\n\nDone.\n", encoding="utf-8")

    docs_finding = Recommendation(
        id="docs1",
        source="plan-completeness",
        severity="medium",
        step_id=None,
        title="Docs gap",
        body="Update `docs/RUNBOOK.md`.",
        anchor="docs-gap",
    )
    _save(registered_plan, recs=[docs_finding], when=_dt(1), audit_stage="detail")
    _save(registered_plan, recs=[_correctness_rec("carry1")], when=_dt(2), audit_stage="detail")
    _save(
        registered_plan,
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

    monkeypatch.setattr(convergence_cmd, "_current_audit_stage", lambda *a, **k: None)
    rc = main(registered_plan.argv("convergence", "1-demo"))
    out = capsys.readouterr().out
    assert rc == 0
    assert "Edit drift" not in out
