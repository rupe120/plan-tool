"""Unit tests for the decision-telemetry recorder (BACKLOG #72)."""

from __future__ import annotations

from pathlib import Path

import plan_tool.telemetry as telemetry
from plan_tool.telemetry import (
    APPLY_VERDICT_DECISION,
    APPLY_VERDICT_INVOCATION_FAILED,
    APPLY_VERDICT_KIND,
    BACKEND_PATTERN_MISS_DECISION,
    BACKEND_PATTERN_MISS_KIND,
    CREATE_ACTION_ACCEPT,
    CREATE_ACTION_OVERRIDE,
    CREATE_ACTION_SPLIT_APPLIED,
    CREATE_ACTION_SPLIT_ERROR,
    CREATE_ACTION_SPLIT_INVALID,
    CREATE_ACTION_SPLIT_REQUESTED,
    CREATE_ACTION_SPLIT_UNUSABLE,
    CREATE_ACTION_UNCLASSIFIED_ACCEPTED,
    CREATE_ACTION_UNCLASSIFIED_CLASSIFIED,
    CREATE_DECISION_REVIEW,
    CREATE_DECISION_STEP_OUTCOME,
    CREATE_MODE_CHECKPOINT,
    CREATE_MODE_INTERACTIVE,
    CREATE_MODE_NON_TTY,
    CREATE_MODE_YES,
    CODE_REVEALS_SPLIT_DECISION,
    DRIFT_GATE_DECISION,
    DRIFT_GATE_KIND,
    DRIFT_VERDICT_DRIFTED,
    DECOMPOSITION_DECISION_KIND,
    DECOMPOSITION_DECISION_RECORDED,
    ESCALATE_SPLIT_DECISION,
    ESCALATE_SPLIT_KIND,
    PLAN_CRITERIA_BREAKDOWN_KIND,
    PLAN_CRITERIA_DECISION,
    PROMPT_BUDGET_DECISION,
    PROMPT_BUDGET_KIND,
    TELEMETRY_SCHEMA_VERSION,
    _MAX_LINE_BYTES,
    _append_json_line,
    _compute_decision_id,
    DecisionEvent,
    code_fingerprint_digest,
    read_decisions,
    record_apply_verdict,
    record_backend_pattern_miss,
    record_code_reveals_split,
    record_create_granularity_assessment,
    record_create_step_outcome,
    record_decision,
    record_drift_gate,
    record_decomposition_decision,
    record_escalate_split,
    record_granularity,
    record_plan_criteria_breakdown,
    record_prompt_budget,
    record_audit_coverage,
    record_step_provenance,
    read_step_provenance_titles,
    scoped_run_id,
    telemetry_path,
    STEP_PROVENANCE_DECISION,
    STEP_PROVENANCE_KIND,
)

import json
import re


def test_record_then_read_roundtrips(tmp_path: Path) -> None:
    record_decision(
        tmp_path,
        kind="granularity",
        decision="assessed",
        plan_slug="demo",
        context={"steps": 5, "split": 2},
        clock=lambda: "2026-06-22T00:00:00+00:00",
    )
    (event,) = read_decisions(tmp_path)
    assert event.schema_version == TELEMETRY_SCHEMA_VERSION
    assert event.ts == "2026-06-22T00:00:00+00:00"
    assert event.kind == "granularity"
    assert event.decision == "assessed"
    assert event.plan_slug == "demo"
    assert event.context == {"steps": 5, "split": 2}
    # The recorded event now carries a stable 16-hex-char decision_id and the
    # empty-by-default join keys.
    assert re.fullmatch(r"[0-9a-f]{16}", event.decision_id)
    assert event.run_id == ""
    assert event.plan_fingerprint == ""
    assert event.code_fingerprint == ""
    assert event.anchor == ""


def test_record_audit_coverage_preserves_terminal_stop_reason(tmp_path: Path) -> None:
    record_audit_coverage(
        tmp_path,
        plan_slug="quota",
        passes=1,
        budget_limited=False,
        findings=0,
        steps=1,
        early_stop_reason="plan-quota",
    )
    record_audit_coverage(
        tmp_path,
        plan_slug="ordinary",
        passes=1,
        budget_limited=False,
        findings=0,
        steps=1,
    )

    quota, ordinary = read_decisions(tmp_path)
    assert quota.context["early_stop_reason"] == "plan-quota"
    assert ordinary.context["early_stop_reason"] is None


def test_record_backend_pattern_miss_preserves_redacted_evidence(tmp_path: Path) -> None:
    record_backend_pattern_miss(
        tmp_path,
        plan_slug="",
        backend="cursor",
        classified_as="rate_limit",
        markers=("spend-limit", "monthly-cycle"),
        excerpt="Spend Limit. Monthly cycle ends on 8/24/2026.",
        phase="detail",
    )

    (event,) = read_decisions(tmp_path)
    assert event.kind == BACKEND_PATTERN_MISS_KIND
    assert event.decision == BACKEND_PATTERN_MISS_DECISION
    assert event.context == {
        "backend": "cursor",
        "classified_as": "rate_limit",
        "markers": ["spend-limit", "monthly-cycle"],
        "excerpt": "Spend Limit. Monthly cycle ends on 8/24/2026.",
        "phase": "detail",
    }


def test_decision_id_is_stable(tmp_path: Path) -> None:
    def rec() -> str:
        record_decision(
            tmp_path,
            kind="granularity",
            decision="assessed",
            plan_slug="demo",
            plan_fingerprint="pf",
            step_id="2",
            clock=lambda: "2026-06-22T00:00:00+00:00",
        )
        return read_decisions(tmp_path)[-1].decision_id

    first, second = rec(), rec()
    assert first == second
    assert re.fullmatch(r"[0-9a-f]{16}", first)


def test_decision_id_changes_with_content(tmp_path: Path) -> None:
    base = dict(
        kind="granularity",
        decision="assessed",
        plan_slug="demo",
        plan_fingerprint="pf",
        step_id="2",
        clock=lambda: "2026-06-22T00:00:00+00:00",
    )

    def id_for(**overrides) -> str:
        record_decision(tmp_path, **{**base, **overrides})
        return read_decisions(tmp_path)[-1].decision_id

    baseline = id_for()
    assert id_for(kind="audit-coverage") != baseline
    assert id_for(decision="other") != baseline
    assert id_for(plan_slug="other") != baseline
    assert id_for(plan_fingerprint="pf2") != baseline
    assert id_for(step_id="3") != baseline
    assert id_for(clock=lambda: "2026-06-22T00:00:01+00:00") != baseline


def test_run_id_read_from_contextvar(tmp_path: Path) -> None:
    with scoped_run_id("run-123"):
        record_decision(tmp_path, kind="k", decision="d", plan_slug="p")
    assert record_decision(tmp_path, kind="k", decision="d", plan_slug="p") is True
    events = read_decisions(tmp_path)
    assert events[0].run_id == "run-123"
    assert events[1].run_id == ""


def test_run_id_scope_clears_on_exit(tmp_path: Path) -> None:
    with scoped_run_id("run-abc"):
        pass
    record_decision(tmp_path, kind="k", decision="d", plan_slug="p")
    assert read_decisions(tmp_path)[-1].run_id == ""


def test_plan_and_code_fingerprint_recorded(tmp_path: Path) -> None:
    record_decision(
        tmp_path,
        kind="k",
        decision="d",
        plan_slug="p",
        plan_fingerprint="pf42",
        code_fingerprint={"plan_tool/foo.py": "deadbeef"},
    )
    event = read_decisions(tmp_path)[-1]
    assert event.plan_fingerprint == "pf42"
    assert event.code_fingerprint == code_fingerprint_digest(
        {"plan_tool/foo.py": "deadbeef"}
    )


def test_anchor_recorded_and_defaults_empty(tmp_path: Path) -> None:
    record_decision(
        tmp_path, kind="k", decision="d", plan_slug="p", anchor="x",
        clock=lambda: "t",
    )
    record_decision(
        tmp_path, kind="k", decision="d", plan_slug="p", clock=lambda: "t"
    )
    events = read_decisions(tmp_path)
    assert events[0].anchor == "x"
    assert events[1].anchor == ""
    # anchor is out of the decision_id hash — same identity tuple + ts collide.
    assert events[0].decision_id == events[1].decision_id


def test_reads_old_v1_line_without_new_fields(tmp_path: Path) -> None:
    path = telemetry_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{"schema_version":1,"ts":"t","kind":"k","decision":"d",'
        '"plan_slug":"p","context":{"a":1}}\n',
        encoding="utf-8",
    )
    (event,) = read_decisions(tmp_path)
    assert event.kind == "k"
    assert event.context == {"a": 1}
    assert event.decision_id == ""
    assert event.run_id == ""
    assert event.plan_fingerprint == ""
    assert event.code_fingerprint == ""
    assert event.anchor == ""


def test_schema_version_matches_digest_contract() -> None:
    assert TELEMETRY_SCHEMA_VERSION == 3


def test_code_fingerprint_digest_is_order_independent() -> None:
    first = {"src/b.py": "b" * 64, "src/a.py": "a" * 64}
    second = {"src/a.py": "a" * 64, "src/b.py": "b" * 64}
    digest = code_fingerprint_digest(first)
    assert digest == code_fingerprint_digest(second)
    assert re.fullmatch(r"[0-9a-f]{64}", digest)


def test_code_fingerprint_digest_changes_with_path_or_hash() -> None:
    baseline = code_fingerprint_digest({"src/a.py": "a"})
    assert code_fingerprint_digest({"src/b.py": "a"}) != baseline
    assert code_fingerprint_digest({"src/a.py": "b"}) != baseline
    assert code_fingerprint_digest({"src/a.py": "a", "src/b.py": "b"}) != baseline
    assert code_fingerprint_digest({}) != baseline


def test_computed_empty_code_fingerprint_has_stable_nonempty_digest() -> None:
    digest = code_fingerprint_digest({})
    assert digest
    assert digest == code_fingerprint_digest({})
    assert digest != ""


def test_record_code_reveals_split_captures_fire(tmp_path: Path) -> None:
    record_code_reveals_split(
        tmp_path, plan_slug="demo", steps=6, step_ids=["3", "5"]
    )
    (event,) = read_decisions(tmp_path)
    assert event.kind == "granularity"
    assert event.decision == CODE_REVEALS_SPLIT_DECISION
    assert event.plan_slug == "demo"
    assert event.context == {
        "stage": "reconcile",
        "steps": 6,
        "fired": 2,
        "step_ids": ["3", "5"],
    }


def test_appends_one_line_per_event(tmp_path: Path) -> None:
    for i in range(3):
        record_decision(
            tmp_path, kind="audit-coverage", decision="passes",
            plan_slug="p", context={"i": i}, clock=lambda: "t",
        )
    path = telemetry_path(tmp_path)
    assert len(path.read_text(encoding="utf-8").splitlines()) == 3
    assert [e.context["i"] for e in read_decisions(tmp_path)] == [0, 1, 2]


def test_record_decision_retries_short_write_to_complete_json_line(
    tmp_path: Path, monkeypatch,
) -> None:
    real_write = telemetry.os.write
    writes = 0

    def short_first_write(fd: int, data: bytes) -> int:
        nonlocal writes
        writes += 1
        if writes == 1:
            return real_write(fd, data[:7])
        return real_write(fd, data)

    monkeypatch.setattr(telemetry.os, "write", short_first_write)
    record_decision(tmp_path, kind="k", decision="d", plan_slug="p")
    assert writes >= 2
    assert len(read_decisions(tmp_path)) == 1
    assert telemetry_path(tmp_path).read_bytes().endswith(b"\n")


def test_record_decision_rolls_back_partial_write_on_append_failure(
    tmp_path: Path, monkeypatch,
) -> None:
    record_decision(tmp_path, kind="existing", decision="d", plan_slug="p")
    path = telemetry_path(tmp_path)
    before = path.read_bytes()
    real_write = telemetry.os.write
    writes = 0

    def short_then_stall(fd: int, data: bytes) -> int:
        nonlocal writes
        writes += 1
        if writes == 1:
            return real_write(fd, data[:5])
        return 0

    monkeypatch.setattr(telemetry.os, "write", short_then_stall)
    assert _append_json_line(path, b'{"new":true}\n') is False
    assert path.read_bytes() == before
    assert [event.kind for event in read_decisions(tmp_path)] == ["existing"]


def test_append_uses_windows_byte_range_lock_when_fcntl_is_unavailable(
    tmp_path: Path, monkeypatch,
) -> None:
    calls: list[tuple[int, int]] = []

    class FakeMsvcrt:
        LK_LOCK = 1
        LK_UNLCK = 2

        @staticmethod
        def locking(_fd: int, mode: int, byte_count: int) -> None:
            calls.append((mode, byte_count))

    monkeypatch.setattr(telemetry, "_fcntl", None)
    monkeypatch.setattr(telemetry, "_msvcrt", FakeMsvcrt)
    path = tmp_path / "decisions.jsonl"

    assert _append_json_line(path, b'{"new":true}\n') is True
    assert path.read_bytes() == b'{"new":true}\n'
    assert calls == [(FakeMsvcrt.LK_LOCK, 1), (FakeMsvcrt.LK_UNLCK, 1)]
    assert Path(f"{path}.lock").stat().st_size == 1


def test_record_decision_acknowledges_partial_append_failure(
    tmp_path: Path, monkeypatch,
) -> None:
    real_write = telemetry.os.write
    writes = 0

    def short_then_stall(fd: int, data: bytes) -> int:
        nonlocal writes
        writes += 1
        if writes == 1:
            return real_write(fd, data[:5])
        return 0

    monkeypatch.setattr(telemetry.os, "write", short_then_stall)
    assert record_decision(tmp_path, kind="k", decision="d", plan_slug="p") is False
    assert read_decisions(tmp_path) == []


def test_unrelated_oversized_context_is_dropped_not_truncated(tmp_path: Path) -> None:
    record_decision(tmp_path, kind="existing", decision="d", plan_slug="p")
    before = telemetry_path(tmp_path).read_bytes()
    record_decision(
        tmp_path,
        kind="large",
        decision="d",
        plan_slug="p",
        context={"payload": "x" * _MAX_LINE_BYTES},
    )
    assert telemetry_path(tmp_path).read_bytes() == before
    assert [event.kind for event in read_decisions(tmp_path)] == ["existing"]


def test_record_is_best_effort_never_raises(tmp_path: Path) -> None:
    # A repo_root that can't hold the file (a regular file, not a dir) must not
    # raise — telemetry is observational and must never break the caller.
    notadir = tmp_path / "afile"
    notadir.write_text("x", encoding="utf-8")
    record_decision(
        notadir, kind="convergence", decision="verdict", plan_slug="p"
    )  # must not raise
    assert read_decisions(notadir) == []


def test_non_serializable_context_is_dropped_not_raised(tmp_path: Path) -> None:
    record_decision(
        tmp_path, kind="granularity", decision="assessed", plan_slug="p",
        context={"bad": object()},  # not JSON-serializable
        clock=lambda: "t",
    )
    # Dropped silently; nothing written, no raise.
    assert read_decisions(tmp_path) == []


def test_read_skips_malformed_lines(tmp_path: Path) -> None:
    path = telemetry_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{"schema_version":1,"ts":"t","kind":"k","decision":"d","plan_slug":"p","context":{}}\n'
        "not json\n"
        "\n"
        '{"schema_version":1,"ts":"u","kind":"k2","decision":"d2","plan_slug":"q","context":{"a":1}}\n',
        encoding="utf-8",
    )
    events = read_decisions(tmp_path)
    assert [e.kind for e in events] == ["k", "k2"]


def test_read_absent_log_returns_empty(tmp_path: Path) -> None:
    assert read_decisions(tmp_path) == []


def test_reads_v2_empty_and_nonempty_code_fingerprint_maps(tmp_path: Path) -> None:
    path = telemetry_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    base = {
        "schema_version": 2,
        "ts": "t",
        "kind": "k",
        "decision": "d",
        "plan_slug": "p",
        "context": {},
    }
    rows = [
        {**base, "code_fingerprint": {}},
        {**base, "code_fingerprint": {"src/a.py": "abc"}},
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    events = read_decisions(tmp_path)
    assert events[0].code_fingerprint == ""
    assert events[1].code_fingerprint == code_fingerprint_digest(
        {"src/a.py": "abc"}
    )


def test_reads_current_row_with_stored_digest(tmp_path: Path) -> None:
    stored_digest = "a" * 64
    path = telemetry_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": TELEMETRY_SCHEMA_VERSION,
                "ts": "t",
                "kind": "k",
                "decision": "d",
                "plan_slug": "p",
                "context": {},
                "code_fingerprint": stored_digest,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert read_decisions(tmp_path)[0].code_fingerprint == stored_digest


def test_record_create_assessment_roundtrips_assessment_id(tmp_path: Path) -> None:
    record_create_granularity_assessment(
        tmp_path,
        plan_slug="demo",
        assessment_id="assessment-1",
        steps=3,
        candidate_fingerprint="abc123",
        file_footprint=4,
        split=2,
        split_steps=1,
        merge=1,
        split_step_ids=["2"],
        predicate_counts={"mixed-verbs": 2},
        can_split=True,
        mode=CREATE_MODE_INTERACTIVE,
    )
    event = read_decisions(tmp_path)[0]
    assert event.kind == "granularity"
    assert event.decision == CREATE_DECISION_REVIEW
    assert event.plan_slug == "demo"
    assert event.context == {
        "stage": "create",
        "assessment_id": "assessment-1",
        "steps": 3,
        "candidate_fingerprint": "abc123",
        "file_footprint": 4,
        "split": 2,
        "split_steps": 1,
        "merge": 1,
        "split_step_ids": ["2"],
        "predicate_counts": {"mixed-verbs": 2},
        "can_split": True,
        "mode": "interactive",
    }


def test_create_recorders_keep_assessment_and_candidate_identities_distinct(
    tmp_path: Path,
) -> None:
    record_create_granularity_assessment(
        tmp_path,
        plan_slug="demo",
        assessment_id="observed-pass-7",
        steps=1,
        candidate_fingerprint="equivalent-candidates",
        file_footprint=0,
        split=0,
        split_steps=0,
        merge=0,
        split_step_ids=[],
        predicate_counts={},
        can_split=False,
        mode=CREATE_MODE_YES,
    )
    context = read_decisions(tmp_path)[0].context
    assert context["assessment_id"] == "observed-pass-7"
    assert context["candidate_fingerprint"] == "equivalent-candidates"


def test_assessment_predicate_counts_passthrough(tmp_path: Path) -> None:
    record_create_granularity_assessment(
        tmp_path,
        plan_slug="demo",
        assessment_id="assessment-2",
        steps=1,
        candidate_fingerprint="fp",
        file_footprint=0,
        split=3,
        split_steps=2,
        merge=0,
        split_step_ids=["1", "2"],
        predicate_counts={"any-key": 7},
        can_split=False,
        mode=CREATE_MODE_NON_TTY,
    )
    assert read_decisions(tmp_path)[0].context["predicate_counts"] == {"any-key": 7}


def test_record_step_outcome_carries_assessment_id_without_code_fingerprint(
    tmp_path: Path,
) -> None:
    record_create_step_outcome(
        tmp_path,
        plan_slug="demo",
        assessment_id="assessment-1",
        step_id="1",
        had_split_hint=True,
        action=CREATE_ACTION_ACCEPT,
        proposed_change_type="feature",
        resolved_change_type="feature",
    )
    event = read_decisions(tmp_path)[0]
    assert event.decision == CREATE_DECISION_STEP_OUTCOME
    assert event.plan_slug == "demo"
    assert event.context == {
        "assessment_id": "assessment-1",
        "step_id": "1",
        "had_split_hint": True,
        "action": "accept",
        "proposed_change_type": "feature",
        "resolved_change_type": "feature",
    }
    assert "before_steps" not in event.context
    assert "after_steps" not in event.context
    assert "error_class" not in event.context
    assert event.code_fingerprint == ""


def test_legacy_create_outcome_without_assessment_id_is_readable(
    tmp_path: Path,
) -> None:
    path = telemetry_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "ts": "t",
                "kind": "granularity",
                "decision": CREATE_DECISION_STEP_OUTCOME,
                "plan_slug": "demo",
                "context": {"step_id": "1", "action": CREATE_ACTION_ACCEPT},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    event = read_decisions(tmp_path)[0]
    assert event.context["action"] == CREATE_ACTION_ACCEPT
    assert "assessment_id" not in event.context


def test_record_step_outcome_split_applied_carries_counts(tmp_path: Path) -> None:
    record_create_step_outcome(
        tmp_path,
        plan_slug="demo",
        assessment_id="assessment-1",
        step_id="1",
        had_split_hint=True,
        action=CREATE_ACTION_SPLIT_APPLIED,
        proposed_change_type="feature",
        resolved_change_type=None,
        before_steps=2,
        after_steps=3,
    )
    context = read_decisions(tmp_path)[0].context
    assert context["before_steps"] == 2
    assert context["after_steps"] == 3
    assert "error_class" not in context


def test_record_step_outcome_split_invalid_carries_error_class(tmp_path: Path) -> None:
    record_create_step_outcome(
        tmp_path,
        plan_slug="demo",
        assessment_id="assessment-1",
        step_id="1",
        had_split_hint=True,
        action=CREATE_ACTION_SPLIT_INVALID,
        proposed_change_type="feature",
        resolved_change_type=None,
        error_class="CreateError",
    )
    context = read_decisions(tmp_path)[0].context
    assert context["error_class"] == "CreateError"
    assert "message" not in context


def test_create_action_and_mode_constants_have_expected_values() -> None:
    assert [
        CREATE_ACTION_ACCEPT,
        CREATE_ACTION_OVERRIDE,
        CREATE_ACTION_SPLIT_REQUESTED,
        CREATE_ACTION_SPLIT_APPLIED,
        CREATE_ACTION_SPLIT_UNUSABLE,
        CREATE_ACTION_SPLIT_INVALID,
        CREATE_ACTION_SPLIT_ERROR,
        CREATE_ACTION_UNCLASSIFIED_ACCEPTED,
        CREATE_ACTION_UNCLASSIFIED_CLASSIFIED,
    ] == [
        "accept",
        "override",
        "split-requested",
        "split-applied",
        "split-unusable",
        "split-invalid",
        "split-error",
        "unclassified-accepted",
        "unclassified-classified",
    ]
    assert [
        CREATE_MODE_INTERACTIVE,
        CREATE_MODE_YES,
        CREATE_MODE_NON_TTY,
        CREATE_MODE_CHECKPOINT,
    ] == ["interactive", "yes", "non_tty", "checkpoint"]


def test_create_recorders_are_best_effort(tmp_path: Path) -> None:
    notadir = tmp_path / "afile"
    notadir.write_text("x", encoding="utf-8")
    record_create_granularity_assessment(
        notadir,
        plan_slug="demo",
        assessment_id="assessment-1",
        steps=1,
        candidate_fingerprint="fp",
        file_footprint=0,
        split=0,
        split_steps=0,
        merge=0,
        split_step_ids=[],
        predicate_counts={},
        can_split=False,
        mode=CREATE_MODE_YES,
    )
    record_create_step_outcome(
        notadir,
        plan_slug="demo",
        assessment_id="assessment-1",
        step_id="1",
        had_split_hint=False,
        action=CREATE_ACTION_UNCLASSIFIED_ACCEPTED,
        proposed_change_type=None,
        resolved_change_type=None,
    )
    assert read_decisions(notadir) == []


def _sample_criteria() -> list[dict]:
    return [
        {"id": "mixed-verbs", "fired": True, "severity": "high", "step_ids": ["2"]},
        {"id": "multi-area", "fired": False, "severity": None, "step_ids": []},
    ]


def test_record_plan_criteria_breakdown_roundtrips(tmp_path: Path) -> None:
    record_plan_criteria_breakdown(
        tmp_path,
        plan_slug="demo",
        plan_fingerprint="pf123",
        criteria=_sample_criteria(),
    )
    event = read_decisions(tmp_path)[0]
    assert event.kind == PLAN_CRITERIA_BREAKDOWN_KIND == "plan-criteria-breakdown"
    assert event.decision == PLAN_CRITERIA_DECISION
    assert event.plan_slug == "demo"
    # Dual-home: the fingerprint lands on the base field *and* stays in context.
    assert event.plan_fingerprint == "pf123"
    assert event.context["plan_fingerprint"] == "pf123"
    assert event.context["criteria"] == _sample_criteria()
    assert event.context["criteria_count"] == 2
    assert event.context["fired_count"] == 1


def test_plan_criteria_code_fingerprint_base_homed(tmp_path: Path) -> None:
    # code_fingerprint is base-homed only (never copied into context) — it is the
    # largest field and nothing reads it from context, so dual-homing it would
    # double the payload against _MAX_LINE_BYTES. plan_fingerprint stays dual-homed.
    # Without a computed map: base field serializes as the unavailable sentinel.
    record_plan_criteria_breakdown(
        tmp_path,
        plan_slug="demo",
        plan_fingerprint="pf",
        criteria=_sample_criteria(),
    )
    absent = read_decisions(tmp_path)[0]
    assert absent.code_fingerprint == ""
    assert "code_fingerprint" not in absent.context

    # With a map: its digest lands on the base field only, never in context.
    record_plan_criteria_breakdown(
        tmp_path,
        plan_slug="demo",
        plan_fingerprint="pf",
        criteria=_sample_criteria(),
        code_fingerprint={"plan_tool/foo.py": "deadbeef"},
    )
    present = read_decisions(tmp_path)[1]
    assert present.code_fingerprint == code_fingerprint_digest(
        {"plan_tool/foo.py": "deadbeef"}
    )
    assert "code_fingerprint" not in present.context
    # plan_fingerprint stays dual-homed (base + context) for split_criteria.py.
    assert present.plan_fingerprint == "pf"
    assert present.context["plan_fingerprint"] == "pf"


def test_plan_criteria_criteria_rows_passthrough(tmp_path: Path) -> None:
    rows = [
        {"id": "c1", "fired": True, "severity": "critical", "step_ids": ["1", "3"]},
        {"id": "c2", "fired": True, "severity": "low", "step_ids": ["2"]},
    ]
    record_plan_criteria_breakdown(
        tmp_path, plan_slug="demo", plan_fingerprint="pf", criteria=rows
    )
    assert read_decisions(tmp_path)[0].context["criteria"] == rows


def test_plan_criteria_counts_derived(tmp_path: Path) -> None:
    rows = [
        {"id": "a", "fired": True, "severity": None, "step_ids": []},
        {"id": "b", "fired": False, "severity": None, "step_ids": []},
        {"id": "c", "fired": True, "severity": None, "step_ids": []},
    ]
    record_plan_criteria_breakdown(
        tmp_path, plan_slug="demo", plan_fingerprint="pf", criteria=rows
    )
    context = read_decisions(tmp_path)[0].context
    assert context["criteria_count"] == len(rows) == 3
    assert context["fired_count"] == 2


def test_plan_criteria_recorder_is_best_effort(tmp_path: Path) -> None:
    notadir = tmp_path / "afile"
    notadir.write_text("x", encoding="utf-8")
    record_plan_criteria_breakdown(
        notadir, plan_slug="demo", plan_fingerprint="pf", criteria=_sample_criteria()
    )  # must not raise
    assert read_decisions(notadir) == []


def test_plan_criteria_kind_constant_value() -> None:
    assert PLAN_CRITERIA_BREAKDOWN_KIND == "plan-criteria-breakdown"


def test_create_step_outcome_forwards_step_id_to_hash(tmp_path: Path) -> None:
    # The wrapper folds its step_id into the decision_id hash: recomputing the id
    # with the event's own ts and step_id="1" matches, while step_id="2" differs —
    # so two step outcomes sharing plan_slug/ts but not step_id can't collide.
    record_create_step_outcome(
        tmp_path,
        plan_slug="demo",
        assessment_id="assessment-1",
        step_id="1",
        had_split_hint=False,
        action=CREATE_ACTION_ACCEPT,
        proposed_change_type="feature",
        resolved_change_type="feature",
    )
    event = read_decisions(tmp_path)[-1]

    def id_with(step_id: str) -> str:
        return _compute_decision_id(
            schema_version=event.schema_version,
            kind=event.kind,
            decision=event.decision,
            plan_slug=event.plan_slug,
            plan_fingerprint=event.plan_fingerprint,
            step_id=step_id,
            ts=event.ts,
        )

    assert id_with("1") == event.decision_id
    assert id_with("2") != event.decision_id


def test_wrappers_forward_plan_fingerprint(tmp_path: Path) -> None:
    # A non-plan-criteria wrapper forwards the fingerprint to the base field only
    # (it does not dual-home into context — that is the plan-criteria wrapper).
    record_granularity(
        tmp_path,
        plan_slug="demo",
        stage="create",
        steps=3,
        split=1,
        merge=0,
        plan_fingerprint="pf",
    )
    event = read_decisions(tmp_path)[0]
    assert event.plan_fingerprint == "pf"
    assert "plan_fingerprint" not in event.context


def test_large_code_fingerprint_stays_below_line_cap(tmp_path: Path) -> None:
    code_fp = {f"plan_tool/module_{i:04d}.py": f"{i:064x}" for i in range(1000)}
    old_size = len(json.dumps({"code_fingerprint": code_fp}).encode("utf-8"))
    assert old_size > _MAX_LINE_BYTES
    record_plan_criteria_breakdown(
        tmp_path,
        plan_slug="demo",
        plan_fingerprint="pf",
        criteria=_sample_criteria(),
        code_fingerprint=code_fp,
    )
    events = read_decisions(tmp_path)
    assert len(events) == 1  # recorded, not dropped
    line = telemetry_path(tmp_path).read_text(encoding="utf-8").splitlines()[0]
    assert len(line.encode("utf-8")) < _MAX_LINE_BYTES
    assert events[0].code_fingerprint == code_fingerprint_digest(code_fp)
    assert "code_fingerprint" not in events[0].context  # base-homed only


def test_record_prompt_budget_roundtrips(tmp_path: Path) -> None:
    record_prompt_budget(
        tmp_path,
        plan_slug="demo",
        phase="detail",
        total_bytes=48000,
        advisory="warn",
        estimated_tokens=12000,
        context_window=200000,
        headroom_ratio=0.06,
        blocks=(("detail", 1200), ("lessons", 300)),
    )
    event = read_decisions(tmp_path)[0]
    assert event.kind == PROMPT_BUDGET_KIND == "prompt-budget"
    assert event.decision == PROMPT_BUDGET_DECISION
    assert event.plan_slug == "demo"
    context = event.context
    assert context["phase"] == "detail"
    assert context["total_bytes"] == 48000
    assert context["advisory"] == "warn"
    assert context["estimated_tokens"] == 12000
    assert context["context_window"] == 200000
    assert context["headroom_ratio"] == 0.06
    assert context["blocks"] == [["detail", 1200], ["lessons", 300]]


def test_record_prompt_budget_omits_optional_keys(tmp_path: Path) -> None:
    record_prompt_budget(
        tmp_path,
        plan_slug="demo",
        phase="run-step",
        total_bytes=1000,
        advisory="ok",
    )
    context = read_decisions(tmp_path)[0].context
    assert set(context) == {"phase", "total_bytes", "advisory"}
    for key in ("estimated_tokens", "context_window", "headroom_ratio", "blocks"):
        assert key not in context


def test_record_prompt_budget_blocks_serialize_as_pairs(tmp_path: Path) -> None:
    record_prompt_budget(
        tmp_path,
        plan_slug="demo",
        phase="detail",
        total_bytes=2000,
        advisory="high",
        blocks=(("detail", 1200), ("lessons", 300)),
    )
    assert read_decisions(tmp_path)[0].context["blocks"] == [
        ["detail", 1200],
        ["lessons", 300],
    ]


def test_record_prompt_budget_empty_slug_ok(tmp_path: Path) -> None:
    record_prompt_budget(
        tmp_path,
        plan_slug="",
        phase="shell-backstop",
        total_bytes=500,
        advisory="ok",
    )
    event = read_decisions(tmp_path)[0]
    assert event.plan_slug == ""
    assert event.context["phase"] == "shell-backstop"


def test_record_prompt_budget_is_best_effort(tmp_path: Path) -> None:
    notadir = tmp_path / "afile"
    notadir.write_text("x", encoding="utf-8")
    record_prompt_budget(
        notadir, plan_slug="demo", phase="detail", total_bytes=1, advisory="ok"
    )  # must not raise
    assert read_decisions(notadir) == []


def test_record_drift_gate_roundtrips(tmp_path: Path) -> None:
    record_drift_gate(
        tmp_path,
        plan_slug="demo",
        verdict=DRIFT_VERDICT_DRIFTED,
        drifted_files=2,
        findings=3,
        plan_fingerprint="planfp",
        code_fingerprint={"src/foo.py": "abc"},
    )
    event = read_decisions(tmp_path)[0]
    assert event.kind == DRIFT_GATE_KIND == "drift-gate"
    assert event.decision == DRIFT_GATE_DECISION == "gated"
    assert event.plan_slug == "demo"
    assert event.context == {
        "verdict": "drifted",
        "drifted_files": 2,
        "findings": 3,
    }
    assert event.plan_fingerprint == "planfp"
    assert event.code_fingerprint == code_fingerprint_digest({"src/foo.py": "abc"})


def test_drift_gate_leaves_step_and_anchor_unset(tmp_path: Path) -> None:
    record_drift_gate(
        tmp_path,
        plan_slug="demo",
        verdict=DRIFT_VERDICT_DRIFTED,
        drifted_files=1,
        findings=0,
    )
    event = read_decisions(tmp_path)[0]
    assert event.anchor == ""
    assert re.fullmatch(r"[0-9a-f]{16}", event.decision_id)
    assert "step_id" not in event.context


def test_prompt_budget_constants_have_expected_values() -> None:
    assert PROMPT_BUDGET_KIND == "prompt-budget"
    assert PROMPT_BUDGET_DECISION == "estimated"


def test_apply_verdict_constants_have_expected_values() -> None:
    assert APPLY_VERDICT_KIND == "apply-verdict"
    assert APPLY_VERDICT_DECISION == "recorded"
    assert APPLY_VERDICT_INVOCATION_FAILED == "INVOCATION-FAILED"


def test_record_apply_verdict_roundtrips(tmp_path: Path) -> None:
    record_apply_verdict(
        tmp_path, plan_slug="demo", verdict="APPLIED", step_id="3",
    )
    event = read_decisions(tmp_path)[0]
    assert event.kind == APPLY_VERDICT_KIND == "apply-verdict"
    assert event.decision == APPLY_VERDICT_DECISION == "recorded"
    assert event.plan_slug == "demo"
    assert event.context["verdict"] == "APPLIED"
    assert event.context["step_id"] == "3"


def test_record_invocation_failed_apply_verdict_roundtrips(tmp_path: Path) -> None:
    with scoped_run_id("run-17"):
        record_apply_verdict(
            tmp_path,
            plan_slug="demo",
            verdict=APPLY_VERDICT_INVOCATION_FAILED,
            step_id="3",
            anchor="finding-anchor",
            plan_fingerprint="plan-fingerprint",
        )
    event = read_decisions(tmp_path)[0]
    assert event.context == {
        "verdict": "INVOCATION-FAILED",
        "step_id": "3",
    }
    assert event.run_id == "run-17"
    assert event.anchor == "finding-anchor"
    assert event.plan_fingerprint == "plan-fingerprint"


def test_apply_verdict_step_id_folds_into_decision_id(tmp_path: Path) -> None:
    record_apply_verdict(tmp_path, plan_slug="p", verdict="APPLIED", step_id="1")
    record_apply_verdict(tmp_path, plan_slug="p", verdict="APPLIED", step_id="2")
    events = read_decisions(tmp_path)
    assert events[0].decision_id != events[1].decision_id


def test_apply_verdict_omits_step_id_when_none(tmp_path: Path) -> None:
    record_apply_verdict(tmp_path, plan_slug="p", verdict="BLOCKED", step_id=None)
    event = read_decisions(tmp_path)[0]
    assert "step_id" not in event.context


def test_apply_verdict_carries_plan_fingerprint_and_anchor(tmp_path: Path) -> None:
    record_apply_verdict(
        tmp_path,
        plan_slug="p",
        verdict="APPLIED",
        step_id="4",
        anchor="some-slug",
        plan_fingerprint="pf123",
    )
    event = read_decisions(tmp_path)[0]
    assert event.plan_fingerprint == "pf123"
    assert event.anchor == "some-slug"
    assert event.code_fingerprint == ""


def test_apply_verdict_anchor_none_coerced_to_empty(tmp_path: Path) -> None:
    # An anchorless finding (Recommendation.anchor is None) must land as "",
    # never the literal string "None".
    record_apply_verdict(tmp_path, plan_slug="p", verdict="APPLIED", anchor=None)
    event = read_decisions(tmp_path)[0]
    assert event.anchor == ""


def test_apply_verdict_best_effort(tmp_path: Path) -> None:
    notadir = tmp_path / "afile"
    notadir.write_text("x", encoding="utf-8")
    record_apply_verdict(
        notadir, plan_slug="p", verdict="APPLIED", step_id="1"
    )  # must not raise
    assert read_decisions(notadir) == []


def test_escalate_split_constants_have_expected_values() -> None:
    assert ESCALATE_SPLIT_KIND == "escalate-split"
    assert ESCALATE_SPLIT_DECISION == "resolved"


def test_record_escalate_split_roundtrips(tmp_path: Path) -> None:
    record_escalate_split(
        tmp_path,
        plan_slug="demo",
        outcome="applied",
        allow_split=True,
        step_id=3,
    )
    (event,) = read_decisions(tmp_path)
    assert event.kind == ESCALATE_SPLIT_KIND == "escalate-split"
    assert event.decision == ESCALATE_SPLIT_DECISION == "resolved"
    assert event.plan_slug == "demo"
    assert event.context["outcome"] == "applied"
    assert event.context["allow_split"] is True
    assert event.context["step_id"] == "3"


def test_escalate_split_blocking_omitted_when_empty(tmp_path: Path) -> None:
    record_escalate_split(
        tmp_path, plan_slug="p", outcome="recommended",
        allow_split=False, step_id=1,
    )
    event = read_decisions(tmp_path)[0]
    assert "blocking" not in event.context


def test_escalate_split_blocking_present_on_unsafe(tmp_path: Path) -> None:
    record_escalate_split(
        tmp_path, plan_slug="p", outcome="unsafe",
        allow_split=True, step_id=1, blocking=[2],
    )
    event = read_decisions(tmp_path)[0]
    assert event.context["blocking"] == ["2"]


def test_escalate_split_step_id_folds_into_decision_id(tmp_path: Path) -> None:
    record_escalate_split(
        tmp_path, plan_slug="p", outcome="applied", allow_split=True, step_id=1,
    )
    record_escalate_split(
        tmp_path, plan_slug="p", outcome="applied", allow_split=True, step_id=2,
    )
    events = read_decisions(tmp_path)
    assert events[0].decision_id != events[1].decision_id


def test_escalate_split_carries_plan_fingerprint_only(tmp_path: Path) -> None:
    record_escalate_split(
        tmp_path,
        plan_slug="p",
        outcome="applied",
        allow_split=True,
        step_id=1,
        plan_fingerprint="pf123",
    )
    event = read_decisions(tmp_path)[0]
    assert event.plan_fingerprint == "pf123"
    assert event.code_fingerprint == ""


def test_escalate_split_best_effort(tmp_path: Path) -> None:
    notadir = tmp_path / "afile"
    notadir.write_text("x", encoding="utf-8")
    record_escalate_split(
        notadir, plan_slug="p", outcome="applied", allow_split=True, step_id=1,
    )  # must not raise
    assert read_decisions(notadir) == []


def test_record_decomposition_decision_roundtrips(tmp_path: Path) -> None:
    assert record_decomposition_decision(
        tmp_path,
        plan_slug="demo",
        outcome="withdraw",
        anchor="step:2",
        rationale="The premise is disproved.",
        plan_fingerprint="pf123",
    )

    (event,) = read_decisions(tmp_path)
    assert event.kind == DECOMPOSITION_DECISION_KIND == "decomposition-decision"
    assert event.decision == DECOMPOSITION_DECISION_RECORDED == "recorded"
    assert event.plan_slug == "demo"
    assert event.anchor == "step:2"
    assert event.plan_fingerprint == "pf123"
    assert event.context == {
        "outcome": "withdraw",
        "rationale": "The premise is disproved.",
    }


def test_record_decomposition_decision_rejects_invalid_shape(tmp_path: Path) -> None:
    assert not record_decomposition_decision(
        tmp_path,
        plan_slug="demo",
        outcome="unknown",
        anchor="step:2",
        rationale="reason",
    )
    assert not record_decomposition_decision(
        tmp_path,
        plan_slug="demo",
        outcome="single",
        anchor="step:02",
        rationale="reason",
    )
    assert not record_decomposition_decision(
        tmp_path,
        plan_slug="demo",
        outcome="single",
        anchor="plan",
        rationale="  ",
    )
    assert read_decisions(tmp_path) == []


# ---------- step-provenance (#238) ----------

def test_step_provenance_constants_have_expected_values() -> None:
    assert STEP_PROVENANCE_KIND == "step-provenance"
    assert STEP_PROVENANCE_DECISION == "created"


def test_record_step_provenance_roundtrips(tmp_path: Path) -> None:
    record_step_provenance(
        tmp_path,
        plan_slug="demo",
        new_step_titles=["Refactor half", "Feature half"],
        mechanism="split",
        plan_fingerprint="pf1",
    )
    (event,) = read_decisions(tmp_path)
    assert event.kind == STEP_PROVENANCE_KIND == "step-provenance"
    assert event.decision == STEP_PROVENANCE_DECISION == "created"
    assert event.plan_slug == "demo"
    assert event.context["new_step_titles"] == ["Refactor half", "Feature half"]
    assert event.context["mechanism"] == "split"
    assert event.plan_fingerprint == "pf1"


def test_record_step_provenance_noop_on_empty_titles(tmp_path: Path) -> None:
    record_step_provenance(
        tmp_path, plan_slug="demo", new_step_titles=[], mechanism="split",
    )
    assert read_decisions(tmp_path) == []


def test_record_step_provenance_drops_empty_strings(tmp_path: Path) -> None:
    record_step_provenance(
        tmp_path,
        plan_slug="demo",
        new_step_titles=["", "Real title", ""],
        mechanism="escalate-split",
    )
    (event,) = read_decisions(tmp_path)
    assert event.context["new_step_titles"] == ["Real title"]


def test_read_step_provenance_titles_unions_across_mechanisms(tmp_path: Path) -> None:
    record_step_provenance(
        tmp_path, plan_slug="demo", new_step_titles=["A"], mechanism="split",
    )
    record_step_provenance(
        tmp_path, plan_slug="demo", new_step_titles=["B"], mechanism="escalate-split",
    )
    assert read_step_provenance_titles(tmp_path, "demo") == {"A", "B"}


def test_read_step_provenance_titles_filters_by_plan_slug(tmp_path: Path) -> None:
    record_step_provenance(
        tmp_path, plan_slug="demo", new_step_titles=["A"], mechanism="split",
    )
    record_step_provenance(
        tmp_path, plan_slug="other", new_step_titles=["B"], mechanism="split",
    )
    assert read_step_provenance_titles(tmp_path, "demo") == {"A"}


def test_read_step_provenance_titles_empty_when_no_events(tmp_path: Path) -> None:
    assert read_step_provenance_titles(tmp_path, "demo") == set()


def test_read_step_provenance_titles_ignores_other_kinds(tmp_path: Path) -> None:
    record_escalate_split(
        tmp_path, plan_slug="demo", outcome="applied", allow_split=True, step_id=1,
    )
    assert read_step_provenance_titles(tmp_path, "demo") == set()


def test_step_provenance_best_effort(tmp_path: Path) -> None:
    notadir = tmp_path / "afile"
    notadir.write_text("x", encoding="utf-8")
    record_step_provenance(
        notadir, plan_slug="p", new_step_titles=["A"], mechanism="split",
    )  # must not raise
    assert read_decisions(notadir) == []
