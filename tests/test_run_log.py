"""Tests for plan_tool.run_log.

Pure ``tmp_path`` tests — no claude shell-out, no concurrency
simulation. The module is a pure-I/O primitive; callers in later
steps (shell.py meta tee, create.py / detail.py / run.py wiring,
the ``plan-tool runs`` subcommand) own their own integration tests.
"""

from __future__ import annotations

import dataclasses
import json
import threading
from pathlib import Path
from typing import get_args

import pytest

from plan_tool.create import _propose_risk_profile_from_seed as _real_risk_classifier

from plan_tool.run_log import (
    IN_FLIGHT_FILENAME,
    IN_FLIGHT_STATUS_AWAITING_RETRY,
    IN_FLIGHT_STATUS_RUNNING,
    IN_FLIGHT_STATUS_TERMINATED,
    RUN_LOG_SCHEMA_VERSION,
    RUNS_REL,
    AttemptFailed,
    BackendRecoveryWait,
    BackendSpawn,
    BackendTermination,
    RunInterrupted,
    RunLogWriter,
    CheckpointDiscard,
    CheckpointHit,
    CheckpointSave,
    ClaudeCallEnd,
    ClaudeCallProgress,
    ClaudeCallStallSuspected,
    ClaudeCallStart,
    ClaudeStreamEvent,
    GateViolations,
    ModelFailureReceipt,
    IterationEnd,
    IterationStart,
    ParseFailure,
    PhaseEnd,
    PhaseStart,
    RoadmapPreflightFailed,
    RoadmapEscalationPreflight,
    RoadmapEscalationResult,
    RoadmapImpactPreflight,
    RoadmapImpactResult,
    RoadmapStructuralRevisionAttempt,
    RoadmapStructuralRevisionPreflight,
    RoadmapSeedApplyResult,
    RoadmapStageWritten,
    RunEnd,
    RunLogLineTooLarge,
    RunOutcome,
    RunStart,
    append_event,
    in_flight_path,
    new_run_id,
    read_in_flight,
    read_run_events,
    read_run_outcome,
    run_dir,
    run_log_path,
    runs_root,
    utc_now_iso,
    write_in_flight,
)
from plan_tool.model_response_sidecar import (
    ModelResponseSidecarOutcome,
    ModelResponseSidecarResult,
)


def _make_run_start(run_id: str = "r1") -> RunStart:
    return RunStart(
        ts="2026-05-14T12:34:56+00:00",
        run_id=run_id,
        schema_version=RUN_LOG_SCHEMA_VERSION,
        command="create",
        plan_slug="my-plan",
        argv=["plan-tool", "create"],
        pid=42,
        cwd="/repo",
    )


def _make_claude_end(run_id: str = "r1") -> ClaudeCallEnd:
    return ClaudeCallEnd(
        ts="2026-05-14T12:34:57+00:00",
        run_id=run_id,
        phase="propose_steps",
        attempt=1,
        rc=0,
        duration_ms=1234,
        stdout_bytes=4096,
    )


def _make_phase_end(run_id: str = "r1") -> PhaseEnd:
    return PhaseEnd(
        ts="2026-05-14T12:34:58+00:00",
        run_id=run_id,
        phase="propose_steps",
        duration_ms=2000,
        outcome="ok",
    )


# ---------- constants and path helpers ----------


def test_schema_version_is_two() -> None:
    # Bumped from 1 to 2 in step 1 of the Claude Call Observability
    # plan when ``ClaudeStreamEvent`` / ``ClaudeCallProgress`` /
    # ``ClaudeCallStallSuspected`` were added. ``read_in_flight``
    # rejects mismatched versions, so old in-flight snapshots are
    # treated as "no in-flight run" — the documented fail-safe.
    assert RUN_LOG_SCHEMA_VERSION == 2


def test_runs_root_under_dot_plan_tool(tmp_path: Path) -> None:
    assert runs_root(tmp_path) == tmp_path / ".plan-tool" / "runs"
    assert RUNS_REL[0] == ".plan-tool"


def test_run_dir_namespaces_by_slug(tmp_path: Path) -> None:
    assert run_dir(tmp_path, "foo-plan") == tmp_path / ".plan-tool" / "runs" / "foo-plan"


def test_run_log_path_appends_jsonl_suffix(tmp_path: Path) -> None:
    p = run_log_path(tmp_path, "foo", "r1")
    assert p.name == "r1.jsonl"
    assert p.parent == run_dir(tmp_path, "foo")


def test_in_flight_path_uses_in_flight_json(tmp_path: Path) -> None:
    p = in_flight_path(tmp_path, "foo")
    assert p.name == IN_FLIGHT_FILENAME == "in-flight.json"
    assert p.parent == run_dir(tmp_path, "foo")


# ---------- new_run_id ----------


def test_new_run_id_is_filename_safe() -> None:
    rid = new_run_id()
    assert "/" not in rid
    assert "\\" not in rid
    assert ".." not in rid
    assert not rid.startswith(".")


def test_new_run_id_is_unique_per_call() -> None:
    ids = {new_run_id() for _ in range(100)}
    assert len(ids) == 100


# ---------- utc_now_iso ----------


def test_utc_now_iso_is_seconds_precision_utc() -> None:
    ts = utc_now_iso()
    assert ts.endswith("+00:00")
    # No fractional seconds.
    assert "." not in ts


# ---------- event dataclass construction ----------


def test_run_start_serializes_with_event_discriminator() -> None:
    obj = dataclasses.asdict(_make_run_start())
    assert obj["event"] == "run_start"
    assert obj["schema_version"] == RUN_LOG_SCHEMA_VERSION
    assert obj["command"] == "create"
    assert obj["argv"] == ["plan-tool", "create"]
    # Round-trips through JSON.
    assert json.loads(json.dumps(obj)) == obj


def test_claude_call_end_token_fields_default_to_none() -> None:
    e = ClaudeCallEnd(
        ts="2026-05-14T00:00:00+00:00",
        run_id="r",
        phase="x",
        attempt=1,
        rc=0,
        duration_ms=10,
        stdout_bytes=0,
    )
    assert e.tokens_input is None
    assert e.tokens_output is None
    assert e.cache_creation_tokens is None
    assert e.cache_read_tokens is None
    assert e.request_id is None
    assert e.cost_usd is None
    assert e.event == "claude_call_end"


def test_parse_failure_references_failure_path_relative() -> None:
    e = ParseFailure(
        ts="2026-05-14T00:00:00+00:00",
        run_id="r",
        phase="per_step_body",
        attempt=2,
        failure_path=".plan-tool/parse-failures/foo/step-3.txt",
    )
    assert e.failure_path == ".plan-tool/parse-failures/foo/step-3.txt"
    assert e.event == "parse_failure"


def test_event_dataclasses_are_frozen() -> None:
    e = _make_run_start()
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.command = "detail"  # type: ignore[misc]


def test_every_event_kind_has_expected_discriminator() -> None:
    # One assertion per concrete kind — proves the discriminator
    # defaults are wired up correctly.
    base = {"ts": "2026-05-14T00:00:00+00:00", "run_id": "r"}
    assert PhaseStart(phase="x", **base).event == "phase_start"
    assert PhaseEnd(phase="x", duration_ms=1, outcome="ok", **base).event == "phase_end"
    assert (
        ClaudeCallStart(phase="x", attempt=1, prompt_bytes=0, **base).event == "claude_call_start"
    )
    assert _make_claude_end().event == "claude_call_end"
    assert (
        ClaudeStreamEvent(phase="x", attempt=1, kind="tool_use", **base).event
        == "claude_stream_event"
    )
    assert (
        ClaudeCallProgress(phase="x", attempt=1, elapsed_ms=0, silent_ms=0, **base).event
        == "claude_call_progress"
    )
    assert (
        ClaudeCallStallSuspected(
            phase="x",
            attempt=1,
            silent_ms=0,
            threshold_ms=0,
            **base,
        ).event
        == "claude_call_stall_suspected"
    )
    assert (
        AttemptFailed(phase="x", attempt=1, failure_kind="parse", **base).event == "attempt_failed"
    )
    assert ModelFailureReceipt(phase="x", attempt=1, reason="parse", **base).event == "model_failure_receipt"
    assert GateViolations(phase="x", attempt=1, **base).event == "gate_violations"
    assert BackendSpawn(phase="x", attempt=1, backend="claude", **base).event == "backend_spawn"
    assert (
        BackendTermination(
            phase="x",
            attempt=1,
            backend="claude",
            reason="completed",
            duration_ms=1,
            **base,
        ).event
        == "backend_termination"
    )
    assert (
        RunInterrupted(phase="x", attempt=1, source="recovery_wait", **base).event
        == "run_interrupted"
    )
    assert (
        BackendRecoveryWait(
            phase="x",
            attempt=1,
            reason="rate_limit",
            delay_ms=0,
            next_attempt=2,
            backend="claude",
            **base,
        ).event
        == "backend_recovery_wait"
    )
    assert RoadmapPreflightFailed(check="brief_source", **base).event == (
        "roadmap_preflight_failed"
    )
    assert RoadmapStageWritten(phase="x", stage=1, **base).event == ("roadmap_stage_written")
    assert RoadmapSeedApplyResult(outcome="applied", **base).event == ("roadmap_seed_apply_result")
    assert RoadmapEscalationPreflight(verdict="accepted", **base).event == (
        "roadmap_escalation_preflight"
    )
    assert RoadmapEscalationResult(outcome="created", **base).event == ("roadmap_escalation_result")
    assert RoadmapImpactPreflight(verdict="accepted", **base).event == ("roadmap_impact_preflight")
    assert RoadmapImpactResult(outcome="completed", **base).event == ("roadmap_impact_result")
    assert (
        CheckpointHit(name="n", input_hash="h", payload_bytes=0, **base).event == "checkpoint_hit"
    )
    assert (
        CheckpointSave(name="n", input_hash="h", payload_bytes=0, **base).event == "checkpoint_save"
    )
    assert CheckpointDiscard(name="n", reason="success", **base).event == "checkpoint_discard"
    assert IterationStart(step_id=1, step_title="t", **base).event == "iteration_start"
    assert IterationEnd(step_id=1, duration_ms=1, outcome="ok", **base).event == "iteration_end"
    assert RunEnd(duration_ms=1, outcome="ok", rc=0, **base).event == "run_end"


def _structural_preflight_fields(**updates: object) -> dict[str, object]:
    fields: dict[str, object] = {
        "receipt_final": None,
        "analysis_final": None,
        "artifact_key": None,
        "feedback_id": None,
        "target_row_id": None,
        "binding_digest": None,
        "render_canonical": None,
        "verdict": "interrupted",
    }
    fields.update(updates)
    return fields


def _accepted_structural_preflight_fields() -> dict[str, object]:
    return _structural_preflight_fields(
        receipt_final="a" * 64,
        analysis_final="b" * 64,
        artifact_key="domain",
        feedback_id="feedback-1",
        target_row_id="domain-row-1",
        binding_digest="c" * 64,
        render_canonical=True,
        verdict="accepted",
    )


def _structural_attempt_fields(**updates: object) -> dict[str, object]:
    fields: dict[str, object] = {
        "attempt": 1,
        "binding_digest": "d" * 64,
        "invalidated_seed_count": None,
        "operation_verdict": "not-reached",
        "merge_verdict": "not-reached",
        "proof_verdict": "not-reached",
        "final_snapshot_verdict": "not-reached",
        "publication_outcome": "not-reached",
        "outcome": "invoke-failed",
    }
    fields.update(updates)
    return fields


def test_structural_revision_events_have_closed_fields_and_nullability(
    tmp_path: Path,
) -> None:
    base_fields = {"ts", "run_id", "event"}
    assert {
        field.name for field in dataclasses.fields(RoadmapStructuralRevisionPreflight)
    } == base_fields | {
        "receipt_final",
        "analysis_final",
        "artifact_key",
        "feedback_id",
        "target_row_id",
        "binding_digest",
        "render_canonical",
        "verdict",
    }
    assert {
        field.name for field in dataclasses.fields(RoadmapStructuralRevisionAttempt)
    } == base_fields | {
        "attempt",
        "binding_digest",
        "invalidated_seed_count",
        "operation_verdict",
        "merge_verdict",
        "proof_verdict",
        "final_snapshot_verdict",
        "publication_outcome",
        "outcome",
    }

    writer = _make_writer(tmp_path)
    writer.roadmap_structural_revision_preflight(
        **_structural_preflight_fields(verdict="mode-rejected")
    )
    writer.roadmap_structural_revision_attempt(
        **_structural_attempt_fields(
            outcome="invoke-failed",
        )
    )
    events = _read_events(writer.log_path)
    assert events[-2]["receipt_final"] is None
    assert events[-2]["render_canonical"] is None
    assert events[-1]["binding_digest"] == "d" * 64
    assert events[-1]["invalidated_seed_count"] is None


def test_structural_revision_preflight_requires_the_closed_fact_matrix(
    tmp_path: Path,
) -> None:
    writer = _make_writer(tmp_path)
    for verdict in (
        "mode-rejected",
        "evaluator-rejected",
        "enrolled-roadmap-rejected",
        "interrupted",
    ):
        writer.roadmap_structural_revision_preflight(
            **_structural_preflight_fields(verdict=verdict)
        )
    writer.roadmap_structural_revision_preflight(
        **_structural_preflight_fields(
            receipt_final="a" * 64,
            analysis_final="b" * 64,
            verdict="evidence-rejected",
        )
    )
    for verdict in ("changed-brief", "legacy-brief"):
        writer.roadmap_structural_revision_preflight(
            **_structural_preflight_fields(
                receipt_final="a" * 64,
                analysis_final="b" * 64,
                verdict=verdict,
            )
        )
    writer.roadmap_structural_revision_preflight(
        **_structural_preflight_fields(
            receipt_final="a" * 64,
            analysis_final="b" * 64,
            artifact_key="domain",
            feedback_id="feedback-1",
            verdict="feedback-rejected",
        )
    )
    writer.roadmap_structural_revision_preflight(
        **_structural_preflight_fields(
            receipt_final="a" * 64,
            analysis_final="b" * 64,
            artifact_key="domain",
            feedback_id="feedback-1",
            target_row_id="domain-row-1",
            render_canonical=False,
            verdict="render-canonical-rejected",
        )
    )
    writer.roadmap_structural_revision_preflight(**_accepted_structural_preflight_fields())

    invalid_rows = (
        _structural_preflight_fields(receipt_final="a" * 64, verdict="evidence-rejected"),
        _structural_preflight_fields(
            receipt_final="a" * 64,
            analysis_final="b" * 64,
            artifact_key="unsafe/id",
            feedback_id="feedback-1",
            verdict="feedback-rejected",
        ),
        _structural_preflight_fields(
            receipt_final="a" * 64,
            analysis_final="b" * 64,
            binding_digest="c" * 64,
            render_canonical=True,
            verdict="accepted",
        ),
        _structural_preflight_fields(
            receipt_final="a" * 64,
            analysis_final="b" * 64,
            artifact_key="domain",
            feedback_id="feedback-1",
            verdict="evidence-rejected",
        ),
        _structural_preflight_fields(
            receipt_final="a" * 64,
            analysis_final="b" * 64,
            artifact_key="domain",
            feedback_id="feedback-1",
            target_row_id="domain-row-1",
            render_canonical=0,
            verdict="render-canonical-rejected",
        ),
    )
    for fields in invalid_rows:
        with pytest.raises(ValueError):
            writer.roadmap_structural_revision_preflight(**fields)


def test_structural_revision_preflight_rejections_keep_raw_inputs_out_of_events(
    tmp_path: Path,
) -> None:
    writer = _make_writer(tmp_path)
    writer.roadmap_structural_revision_preflight(
        **_structural_preflight_fields(verdict="mode-rejected")
    )
    writer.roadmap_structural_revision_preflight(
        **_structural_preflight_fields(verdict="evaluator-rejected")
    )

    events = _read_events(writer.log_path)
    preflights = [
        event for event in events if event["event"] == "roadmap_structural_revision_preflight"
    ]
    assert len(preflights) == 2
    assert all(
        all(
            event[field] is None
            for field in (
                "receipt_final",
                "analysis_final",
                "artifact_key",
                "feedback_id",
                "target_row_id",
                "binding_digest",
                "render_canonical",
            )
        )
        for event in preflights
    )
    assert not any(event["event"] == "roadmap_structural_revision_attempt" for event in events)


def test_structural_revision_attempt_requires_exact_outcome_phase_tuples(
    tmp_path: Path,
) -> None:
    writer = _make_writer(tmp_path)
    rows = (
        _structural_attempt_fields(outcome="invoke-failed"),
        _structural_attempt_fields(outcome="empty-reply"),
        _structural_attempt_fields(operation_verdict="rejected", outcome="envelope-rejected"),
        _structural_attempt_fields(
            operation_verdict="accepted",
            merge_verdict="rejected",
            outcome="merge-rejected",
        ),
        _structural_attempt_fields(
            operation_verdict="accepted",
            merge_verdict="accepted",
            proof_verdict="structural-rejected",
            outcome="proof-rejected",
        ),
        _structural_attempt_fields(
            operation_verdict="accepted",
            merge_verdict="accepted",
            proof_verdict="gate-rejected",
            outcome="proof-rejected",
        ),
        _structural_attempt_fields(
            operation_verdict="accepted",
            merge_verdict="accepted",
            proof_verdict="accepted",
            final_snapshot_verdict="stale",
            outcome="final-snapshot-stale",
        ),
        *(
            _structural_attempt_fields(
                operation_verdict="accepted",
                merge_verdict="accepted",
                proof_verdict="accepted",
                final_snapshot_verdict="stale",
                outcome=outcome,
            )
            for outcome in ("changed-brief", "legacy-brief")
        ),
        _structural_attempt_fields(
            operation_verdict="accepted",
            merge_verdict="accepted",
            proof_verdict="accepted",
            final_snapshot_verdict="current",
            publication_outcome="failed",
            outcome="publication-failed",
        ),
        _structural_attempt_fields(
            operation_verdict="accepted",
            merge_verdict="accepted",
            proof_verdict="accepted",
            final_snapshot_verdict="current",
            publication_outcome="published",
            invalidated_seed_count=0,
            outcome="published",
        ),
        _structural_attempt_fields(invalidated_seed_count=None, outcome="interrupted"),
        _structural_attempt_fields(operation_verdict="accepted", outcome="interrupted"),
        _structural_attempt_fields(
            operation_verdict="accepted",
            merge_verdict="accepted",
            proof_verdict="accepted",
            final_snapshot_verdict="current",
            publication_outcome="unknown-after-interrupt",
            outcome="interrupted",
        ),
    )
    for fields in rows:
        writer.roadmap_structural_revision_attempt(**fields)

    with pytest.raises(ValueError):
        writer.roadmap_structural_revision_attempt(
            **_structural_attempt_fields(
                operation_verdict="accepted",
                merge_verdict="accepted",
                proof_verdict="accepted",
                final_snapshot_verdict="stale",
                publication_outcome="published",
                outcome="published",
            )
        )
    with pytest.raises(ValueError):
        writer.roadmap_structural_revision_attempt(
            **_structural_attempt_fields(
                operation_verdict="accepted",
                merge_verdict="accepted",
                proof_verdict="accepted",
                final_snapshot_verdict="not-reached",
                publication_outcome="unknown-after-interrupt",
                outcome="interrupted",
            )
        )


def test_structural_revision_attempt_reports_seed_count_only_after_publication(
    tmp_path: Path,
) -> None:
    writer = _make_writer(tmp_path)
    with pytest.raises(ValueError):
        writer.roadmap_structural_revision_attempt(
            **_structural_attempt_fields(invalidated_seed_count=0, outcome="invoke-failed")
        )
    with pytest.raises(ValueError):
        writer.roadmap_structural_revision_attempt(
            **_structural_attempt_fields(
                operation_verdict="accepted",
                merge_verdict="accepted",
                proof_verdict="accepted",
                final_snapshot_verdict="current",
                publication_outcome="published",
                invalidated_seed_count=None,
                outcome="published",
            )
        )
    with pytest.raises(ValueError):
        writer.roadmap_structural_revision_attempt(
            **_structural_attempt_fields(
                invalidated_seed_count=0,
                operation_verdict="accepted",
                outcome="interrupted",
            )
        )


def test_structural_revision_writer_methods_reject_unlisted_vocabulary_and_content(
    tmp_path: Path,
) -> None:
    writer = _make_writer(tmp_path)
    with pytest.raises(ValueError):
        writer.roadmap_structural_revision_preflight(
            **_structural_preflight_fields(verdict="reviewer-rejected")
        )
    with pytest.raises(ValueError):
        writer.roadmap_structural_revision_attempt(
            **_structural_attempt_fields(operation_verdict="skipped")
        )
    with pytest.raises(ValueError):
        writer.roadmap_structural_revision_attempt(**_structural_attempt_fields(attempt=True))
    with pytest.raises(TypeError):
        writer.roadmap_structural_revision_preflight(  # type: ignore[call-arg]
            **_structural_preflight_fields(verdict="mode-rejected"),
            feedback="reviewer text",
        )
    with pytest.raises(TypeError):
        writer.roadmap_structural_revision_attempt(  # type: ignore[call-arg]
            **_structural_attempt_fields(), reply="backend reply"
        )
    assert "reviewer text" not in writer.log_path.read_text(encoding="utf-8")
    assert "backend reply" not in writer.log_path.read_text(encoding="utf-8")


def test_structural_revision_events_are_event_union_members(tmp_path: Path) -> None:
    target = tmp_path / "events.jsonl"
    base = {"ts": "2026-05-14T00:00:00+00:00", "run_id": "r"}
    append_event(
        target,
        RoadmapStructuralRevisionPreflight(
            receipt_final="a" * 64,
            analysis_final="b" * 64,
            artifact_key="domain",
            feedback_id="feedback-1",
            target_row_id="domain-row-1",
            binding_digest="c" * 64,
            render_canonical=True,
            verdict="accepted",
            **base,
        ),
    )
    append_event(
        target,
        RoadmapStructuralRevisionAttempt(
            binding_digest="c" * 64,
            invalidated_seed_count=0,
            operation_verdict="accepted",
            merge_verdict="accepted",
            proof_verdict="accepted",
            final_snapshot_verdict="current",
            publication_outcome="published",
            outcome="published",
            **base,
        ),
    )
    assert [event["event"] for event in _read_events(target)] == [
        "roadmap_structural_revision_preflight",
        "roadmap_structural_revision_attempt",
    ]


def test_structural_revision_events_append_without_refreshing_active_snapshot(
    tmp_path: Path,
) -> None:
    writer = _make_writer(tmp_path)
    before = read_in_flight(writer.in_flight_path)
    writer.roadmap_structural_revision_preflight(**_accepted_structural_preflight_fields())
    writer.roadmap_structural_revision_attempt(
        **_structural_attempt_fields(
            operation_verdict="accepted",
            merge_verdict="accepted",
            proof_verdict="accepted",
            final_snapshot_verdict="current",
            publication_outcome="published",
            invalidated_seed_count=0,
            outcome="published",
        )
    )
    assert read_in_flight(writer.in_flight_path) == before


def test_escalation_events_have_closed_fields_and_monotonic_nullability(
    tmp_path: Path,
) -> None:
    base_fields = {"ts", "run_id", "event"}
    assert {field.name for field in dataclasses.fields(RoadmapEscalationPreflight)} == (
        base_fields
        | {
            "artifact_key",
            "feedback_id",
            "reason",
            "target_kind",
            "target_id",
            "artifact_digest",
            "verdict",
        }
    )
    assert {field.name for field in dataclasses.fields(RoadmapEscalationResult)} == (
        base_fields | {"outcome", "receipt_id", "handoff"}
    )

    writer = _make_writer(tmp_path)
    writer.roadmap_escalation_preflight(
        artifact_key=None,
        feedback_id=None,
        reason=None,
        target_kind=None,
        target_id=None,
        artifact_digest=None,
        verdict="interrupted",
    )
    writer.roadmap_escalation_result(outcome="interrupted", receipt_id=None, handoff=None)

    events = _read_events(writer.log_path)
    assert events[-2]["artifact_key"] is None
    assert events[-2]["reason"] is None
    assert events[-2]["target_id"] is None
    assert events[-1]["receipt_id"] is None
    assert events[-1]["handoff"] is None


@pytest.mark.parametrize(
    "kwargs",
    (
        {"reason": "row-structure"},
        {"reason": "row-structure", "artifact_digest": "a" * 64},
        {
            "artifact_key": "domain",
            "feedback_id": "feedback",
            "target_kind": "row",
            "target_id": "target",
        },
    ),
)
def test_escalation_preflight_rejects_nonmonotonic_facts(
    tmp_path: Path, kwargs: dict[str, str]
) -> None:
    writer = _make_writer(tmp_path)
    fields = {
        "artifact_key": None,
        "feedback_id": None,
        "reason": None,
        "target_kind": None,
        "target_id": None,
        "artifact_digest": None,
        "verdict": "interrupted",
    }
    fields.update(kwargs)

    with pytest.raises(ValueError):
        writer.roadmap_escalation_preflight(**fields)


def test_escalation_writer_methods_reject_unknown_vocabulary_and_reviewer_content(
    tmp_path: Path,
) -> None:
    writer = _make_writer(tmp_path)
    with pytest.raises(ValueError):
        writer.roadmap_escalation_preflight(
            artifact_key=None,
            feedback_id=None,
            reason=None,
            target_kind=None,
            target_id=None,
            artifact_digest=None,
            verdict="reviewer-request",
        )
    with pytest.raises(ValueError):
        writer.roadmap_escalation_result(
            outcome="created", receipt_id="a" * 64, handoff="reviewer-request"
        )
    with pytest.raises(TypeError):
        writer.roadmap_escalation_result(  # type: ignore[call-arg]
            outcome="created",
            receipt_id="a" * 64,
            handoff="requires-scope-review",
            reviewer_content="must not persist",
        )


def test_escalation_result_accepts_shared_outcomes_and_redacts_unshared_failures(
    tmp_path: Path,
) -> None:
    writer = _make_writer(tmp_path)
    for outcome in ("created", "committed-existing", "reused"):
        writer.roadmap_escalation_result(
            outcome=outcome,
            receipt_id="a" * 64,
            handoff="requires-scope-review",
        )
    for outcome in ("commit-failed", "interrupted"):
        writer.roadmap_escalation_result(
            outcome=outcome,
            receipt_id=None,
            handoff=None,
        )
        with pytest.raises(ValueError):
            writer.roadmap_escalation_result(
                outcome=outcome,
                receipt_id="a" * 64,
                handoff="requires-scope-review",
            )


def test_escalation_events_are_event_union_members(tmp_path: Path) -> None:
    target = tmp_path / "events.jsonl"
    base = {"ts": "2026-05-14T00:00:00+00:00", "run_id": "r"}
    append_event(target, RoadmapEscalationPreflight(verdict="accepted", **base))
    append_event(target, RoadmapEscalationResult(outcome="created", **base))

    assert [event["event"] for event in _read_events(target)] == [
        "roadmap_escalation_preflight",
        "roadmap_escalation_result",
    ]


def _impact_preflight_fields(**updates: object) -> dict[str, object]:
    fields: dict[str, object] = {
        "receipt_final": None,
        "artifact_key": None,
        "feedback_id": None,
        "reason": None,
        "target_kind": None,
        "target_id": None,
        "receipt_source_digest": None,
        "source_record_digest": None,
        "brief_digest": None,
        "snapshot_artifact_count": None,
        "closure_node_count": None,
        "closure_relation_count": None,
        "closure_mapping_failures": None,
        "verdict": "interrupted",
    }
    fields.update(updates)
    return fields


def _resolved_impact_preflight_fields() -> dict[str, object]:
    return _impact_preflight_fields(
        receipt_final="a" * 64,
        artifact_key="domain",
        feedback_id="feedback-1",
        reason="cross-artifact-impact",
        target_kind="row",
        target_id="domain-row-1",
        receipt_source_digest="b" * 64,
    )


def test_impact_preflight_verdict_matrix_has_closed_fields_and_monotonic_nullability(
    tmp_path: Path,
) -> None:
    base_fields = {"ts", "run_id", "event"}
    assert {field.name for field in dataclasses.fields(RoadmapImpactPreflight)} == (
        base_fields
        | {
            "receipt_final",
            "artifact_key",
            "feedback_id",
            "reason",
            "target_kind",
            "target_id",
            "receipt_source_digest",
            "source_record_digest",
            "brief_digest",
            "snapshot_artifact_count",
            "closure_node_count",
            "closure_relation_count",
            "closure_mapping_failures",
            "verdict",
        }
    )
    assert {field.name for field in dataclasses.fields(RoadmapImpactResult)} == (
        base_fields
        | {
            "outcome",
            "analysis_id",
            "route_class",
            "publication_outcome",
            "next_workflow",
        }
    )

    writer = _make_writer(tmp_path)
    writer.roadmap_impact_preflight(**_impact_preflight_fields(verdict="mode-rejected"))
    for verdict in ("final-rejected", "receipt-missing", "receipt-unreadable", "receipt-invalid"):
        writer.roadmap_impact_preflight(
            **_impact_preflight_fields(receipt_final="a" * 64, verdict=verdict)
        )
    receipt_fields = _resolved_impact_preflight_fields()
    writer.roadmap_impact_preflight(**{**receipt_fields, "verdict": "receipt-rejected"})
    snapshot_fields = {
        **receipt_fields,
        "source_record_digest": "c" * 64,
        "brief_digest": "d" * 64,
        "snapshot_artifact_count": 4,
    }
    writer.roadmap_impact_preflight(**{**snapshot_fields, "verdict": "snapshot-rejected"})
    closure_fields = {
        **snapshot_fields,
        "closure_node_count": 3,
        "closure_relation_count": 2,
        "closure_mapping_failures": (),
    }
    writer.roadmap_impact_preflight(**{**closure_fields, "verdict": "closure-rejected"})
    writer.roadmap_impact_preflight(**{**closure_fields, "verdict": "accepted"})
    writer.roadmap_impact_preflight(**_impact_preflight_fields(verdict="interrupted"))

    events = [
        event
        for event in _read_events(writer.log_path)
        if event["event"] == "roadmap_impact_preflight"
    ]
    assert events[0]["receipt_final"] is None
    for event in events[1:5]:
        assert event["receipt_final"] == "a" * 64
        assert event["receipt_source_digest"] is None
    assert events[5]["receipt_source_digest"] == "b" * 64
    assert events[5]["source_record_digest"] is None
    assert events[6]["snapshot_artifact_count"] == 4
    assert events[6]["closure_node_count"] is None
    assert events[7]["closure_node_count"] == 3
    assert events[7]["closure_relation_count"] == 2
    assert events[7]["closure_mapping_failures"] == []
    assert events[8]["closure_relation_count"] == 2
    assert events[9]["receipt_final"] is None


def test_impact_preflight_rejects_unsafe_or_out_of_order_facts(
    tmp_path: Path,
) -> None:
    writer = _make_writer(tmp_path)
    with pytest.raises(ValueError):
        writer.roadmap_impact_preflight(
            **{
                **_resolved_impact_preflight_fields(),
                "artifact_key": "unsafe selector",
                "verdict": "receipt-rejected",
            }
        )
    with pytest.raises(ValueError):
        writer.roadmap_impact_preflight(
            **{
                **_resolved_impact_preflight_fields(),
                "source_record_digest": "c" * 64,
                "brief_digest": "d" * 64,
                "snapshot_artifact_count": 4,
                "closure_node_count": 0,
                "closure_relation_count": 0,
                "closure_mapping_failures": ((0, -1, 1),),
                "verdict": "closure-rejected",
            }
        )
    with pytest.raises(ValueError):
        writer.roadmap_impact_preflight(
            **_impact_preflight_fields(receipt_final="not-a-digest", verdict="receipt-missing")
        )
    with pytest.raises(ValueError):
        writer.roadmap_impact_preflight(
            **{
                **_resolved_impact_preflight_fields(),
                "source_record_digest": "c" * 64,
                "brief_digest": "d" * 64,
                "snapshot_artifact_count": -1,
                "verdict": "snapshot-rejected",
            }
        )
    with pytest.raises(ValueError):
        writer.roadmap_impact_preflight(
            **_impact_preflight_fields(
                source_record_digest="c" * 64,
                brief_digest="d" * 64,
                snapshot_artifact_count=4,
                verdict="snapshot-rejected",
            )
        )
    with pytest.raises(ValueError):
        writer.roadmap_impact_preflight(**_impact_preflight_fields(verdict="unlisted-verdict"))


@pytest.mark.parametrize("verdict", ("changed-brief", "legacy-brief"))
def test_impact_preflight_brief_refusals_stop_after_safe_receipt_facts(
    tmp_path: Path, verdict: str
) -> None:
    writer = _make_writer(tmp_path)
    receipt_fields = _resolved_impact_preflight_fields()

    writer.roadmap_impact_preflight(**{**receipt_fields, "verdict": verdict})

    event = _read_events(writer.log_path)[-1]
    assert event["verdict"] == verdict
    assert event["receipt_final"] == "a" * 64
    assert event["receipt_source_digest"] == "b" * 64
    assert all(
        event[name] is None
        for name in (
            "source_record_digest",
            "brief_digest",
            "snapshot_artifact_count",
            "closure_node_count",
            "closure_relation_count",
            "closure_mapping_failures",
        )
    )
    with pytest.raises(ValueError):
        writer.roadmap_impact_preflight(
            **{
                **receipt_fields,
                "source_record_digest": "c" * 64,
                "brief_digest": "d" * 64,
                "snapshot_artifact_count": 4,
                "verdict": verdict,
            }
        )


def test_impact_result_separates_completed_route_publication_identity_and_workflow(
    tmp_path: Path,
) -> None:
    writer = _make_writer(tmp_path)
    for route_class, next_workflow in (
        ("same-artifact", "roadmap-same-artifact-structural-revision"),
        ("cross-artifact", "roadmap-cross-artifact-revision-transaction"),
        ("requires-scope-review", None),
    ):
        writer.roadmap_impact_result(
            outcome="completed",
            analysis_id="e" * 64,
            route_class=route_class,
            publication_outcome="created",
            next_workflow=next_workflow,
        )

    writer.roadmap_impact_result(
        outcome="storage-rejected",
        analysis_id=None,
        route_class=None,
        publication_outcome=None,
        next_workflow=None,
    )

    results = [
        event
        for event in _read_events(writer.log_path)
        if event["event"] == "roadmap_impact_result"
    ]
    assert all(event["analysis_id"] == "e" * 64 for event in results[:3])
    assert results[2]["route_class"] == "requires-scope-review"
    assert results[2]["publication_outcome"] == "created"
    assert results[2]["next_workflow"] is None
    assert all(
        value is None
        for key, value in results[3].items()
        if key in {"analysis_id", "route_class", "publication_outcome", "next_workflow"}
    )
    with pytest.raises(ValueError):
        writer.roadmap_impact_result(
            outcome="completed",
            analysis_id="e" * 64,
            route_class="requires-scope-review",
            publication_outcome="reused",
            next_workflow="roadmap-cross-artifact-revision-transaction",
        )


@pytest.mark.parametrize("outcome", ("changed-brief", "legacy-brief"))
def test_impact_result_brief_refusals_expose_no_analysis_facts(
    tmp_path: Path, outcome: str
) -> None:
    writer = _make_writer(tmp_path)

    writer.roadmap_impact_result(
        outcome=outcome,
        analysis_id=None,
        route_class=None,
        publication_outcome=None,
        next_workflow=None,
    )

    event = _read_events(writer.log_path)[-1]
    assert event["outcome"] == outcome
    assert all(
        event[name] is None
        for name in ("analysis_id", "route_class", "publication_outcome", "next_workflow")
    )
    with pytest.raises(ValueError):
        writer.roadmap_impact_result(
            outcome=outcome,
            analysis_id="e" * 64,
            route_class="same-artifact",
            publication_outcome="created",
            next_workflow="roadmap-same-artifact-structural-revision",
        )


def test_impact_result_excludes_return_only_telemetry_unavailable(tmp_path: Path) -> None:
    writer = _make_writer(tmp_path)
    with pytest.raises(ValueError):
        writer.roadmap_impact_result(
            outcome="telemetry-unavailable",
            analysis_id=None,
            route_class=None,
            publication_outcome=None,
            next_workflow=None,
        )


def test_impact_writer_methods_reject_unknown_vocabulary_and_prose(
    tmp_path: Path,
) -> None:
    writer = _make_writer(tmp_path)
    with pytest.raises(ValueError):
        writer.roadmap_impact_preflight(
            **_impact_preflight_fields(reason="reviewer-prose", verdict="receipt-rejected")
        )
    with pytest.raises(ValueError):
        writer.roadmap_impact_preflight(
            **_impact_preflight_fields(verdict="unknown-brief-refusal")
        )
    with pytest.raises(ValueError):
        writer.roadmap_impact_result(
            outcome="completed",
            analysis_id="e" * 64,
            route_class="same-artifact",
            publication_outcome="created",
            next_workflow="reviewer-request",
        )
    with pytest.raises(ValueError):
        writer.roadmap_impact_result(
            outcome="unknown-brief-refusal",
            analysis_id=None,
            route_class=None,
            publication_outcome=None,
            next_workflow=None,
        )
    with pytest.raises(TypeError):
        writer.roadmap_impact_result(  # type: ignore[call-arg]
            outcome="invalid",
            analysis_id=None,
            route_class=None,
            publication_outcome=None,
            next_workflow=None,
            reviewer_content="must not persist",
            artifact_path="must-not-persist.md",
        )
    assert "must not persist" not in writer.log_path.read_text(encoding="utf-8")
    assert "must-not-persist.md" not in writer.log_path.read_text(encoding="utf-8")


def test_impact_event_fields_are_reserved_from_writer_context(tmp_path: Path) -> None:
    writer = _make_writer(
        tmp_path,
        context={
            "receipt_final": "0" * 64,
            "analysis_id": "1" * 64,
            "route_class": "cross-artifact",
            "publication_outcome": "reused",
            "next_workflow": "roadmap-cross-artifact-revision-transaction",
            "outcome": "collision",
            "roadmap_action": "impact-analysis",
        },
    )
    preflight = {
        **_resolved_impact_preflight_fields(),
        "source_record_digest": "c" * 64,
        "brief_digest": "d" * 64,
        "snapshot_artifact_count": 4,
        "closure_node_count": 3,
        "closure_relation_count": 2,
        "closure_mapping_failures": (),
    }
    writer.roadmap_impact_preflight(**{**preflight, "verdict": "accepted"})
    writer.roadmap_impact_result(
        outcome="completed",
        analysis_id="e" * 64,
        route_class="same-artifact",
        publication_outcome="created",
        next_workflow="roadmap-same-artifact-structural-revision",
    )

    events = _read_events(writer.log_path)
    assert events[-2]["receipt_final"] == "a" * 64
    assert events[-2]["roadmap_action"] == "impact-analysis"
    assert events[-1]["analysis_id"] == "e" * 64
    assert events[-1]["route_class"] == "same-artifact"
    assert events[-1]["publication_outcome"] == "created"
    assert events[-1]["next_workflow"] == "roadmap-same-artifact-structural-revision"
    assert events[-1]["outcome"] == "completed"


def test_impact_events_are_event_union_members(tmp_path: Path) -> None:
    target = tmp_path / "events.jsonl"
    base = {"ts": "2026-05-14T00:00:00+00:00", "run_id": "r"}
    append_event(target, RoadmapImpactPreflight(verdict="accepted", **base))
    append_event(target, RoadmapImpactResult(outcome="completed", **base))

    assert [event["event"] for event in _read_events(target)] == [
        "roadmap_impact_preflight",
        "roadmap_impact_result",
    ]


def test_impact_events_append_without_refreshing_active_snapshot(tmp_path: Path) -> None:
    writer = _make_writer(tmp_path)
    before = read_in_flight(writer.in_flight_path)
    assert before is not None
    accepted = {
        **_resolved_impact_preflight_fields(),
        "source_record_digest": "c" * 64,
        "brief_digest": "d" * 64,
        "snapshot_artifact_count": 4,
        "closure_node_count": 3,
        "closure_relation_count": 2,
        "closure_mapping_failures": (),
        "verdict": "accepted",
    }
    writer.roadmap_impact_preflight(**accepted)
    writer.roadmap_impact_result(
        outcome="completed",
        analysis_id="e" * 64,
        route_class="same-artifact",
        publication_outcome="created",
        next_workflow="roadmap-same-artifact-structural-revision",
    )

    assert read_in_flight(writer.in_flight_path) == before


def test_impact_events_preserve_newer_snapshot_during_guarded_run_end_cleanup(
    tmp_path: Path,
) -> None:
    writer_a = _make_writer(tmp_path, slug="shared")
    writer_a.roadmap_impact_preflight(
        **{**_resolved_impact_preflight_fields(), "verdict": "changed-brief"}
    )
    writer_a.roadmap_impact_result(
        outcome="changed-brief",
        analysis_id=None,
        route_class=None,
        publication_outcome=None,
        next_workflow=None,
    )
    writer_b = _make_writer(tmp_path, slug="shared")

    writer_a.run_end(outcome="changed-brief", rc=1)
    snapshot = read_in_flight(writer_a.in_flight_path)
    assert snapshot is not None
    assert snapshot["run_id"] == writer_b.run_id

    writer_b.run_end(outcome="ok", rc=0)


# ---------- append_event ----------


def test_append_creates_parent_dir_and_writes_one_line(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "log.jsonl"
    append_event(target, _make_run_start())
    assert target.is_file()
    raw = target.read_text(encoding="utf-8")
    assert raw.endswith("\n")
    # Strip the trailing newline; what's left is a single JSON object.
    body = raw.rstrip("\n")
    obj = json.loads(body)
    assert obj["event"] == "run_start"


def test_append_two_events_produces_two_lines(tmp_path: Path) -> None:
    target = tmp_path / "log.jsonl"
    append_event(target, _make_run_start())
    append_event(target, _make_phase_end())
    lines = target.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["event"] == "run_start"
    assert json.loads(lines[1])["event"] == "phase_end"


def test_append_uses_canonical_json_no_extra_whitespace(tmp_path: Path) -> None:
    target = tmp_path / "log.jsonl"
    append_event(target, _make_run_start())
    raw = target.read_text(encoding="utf-8")
    # Exactly one newline, at the end.
    assert raw.count("\n") == 1
    # No `": "` (default separators); ``separators=(",", ":")`` is honored.
    assert '": ' not in raw
    # No `", "` either.
    assert ", " not in raw


def test_append_preserves_unicode_via_ensure_ascii_false(tmp_path: Path) -> None:
    target = tmp_path / "log.jsonl"
    event = IterationStart(
        ts="2026-05-14T00:00:00+00:00",
        run_id="r",
        step_id=1,
        step_title="café — résumé",
    )
    append_event(target, event)
    raw_bytes = target.read_bytes()
    # UTF-8 encoding of "café" — not the escaped é form.
    assert "café".encode("utf-8") in raw_bytes
    assert b"\\u00e9" not in raw_bytes


def test_append_truncates_a_single_long_string_to_fit_under_cap(
    tmp_path: Path,
) -> None:
    """A single oversized field (typical case: long --from description
    in argv) is truncated with an elision marker so the line fits under
    ``_MAX_LINE_BYTES`` and the event is written successfully."""
    target = tmp_path / "log.jsonl"
    huge = "x" * 5000
    event = RunStart(
        ts="2026-05-14T00:00:00+00:00",
        run_id="r",
        schema_version=RUN_LOG_SCHEMA_VERSION,
        command="create",
        plan_slug="p",
        argv=[huge],
        pid=1,
        cwd="/",
    )
    # No exception — the long string is truncated rather than refused.
    append_event(target, event)
    assert target.exists()
    line = target.read_text(encoding="utf-8").splitlines()[0]
    parsed = json.loads(line)
    truncated_arg = parsed["argv"][0]
    # The 5000-char original is now bounded at ~1024 chars + elision tail.
    assert len(truncated_arg) < 1100, len(truncated_arg)
    assert "elided" in truncated_arg, truncated_arg
    # Whole line is under the cap.
    assert len((line + "\n").encode("utf-8")) <= 4096


def test_append_raises_when_many_medium_strings_exceed_cap(
    tmp_path: Path,
) -> None:
    """Pathological payload: many strings each under the per-string cap
    but cumulatively exceeding ``_MAX_LINE_BYTES``. Truncation can't
    help; ``RunLogLineTooLarge`` still fires and the file is not
    modified."""
    target = tmp_path / "log.jsonl"
    medium = "y" * 900  # under the 1024-char per-string cap
    event = RunStart(
        ts="2026-05-14T00:00:00+00:00",
        run_id="r",
        schema_version=RUN_LOG_SCHEMA_VERSION,
        command="create",
        plan_slug="p",
        argv=[medium] * 6,  # ~5400 bytes of strings alone, line exceeds 4096
        pid=1,
        cwd="/",
    )
    with pytest.raises(RunLogLineTooLarge):
        append_event(target, event)
    assert not target.exists()


def test_append_event_is_idempotent_under_repeated_calls(tmp_path: Path) -> None:
    target = tmp_path / "log.jsonl"
    event = _make_run_start()
    for _ in range(5):
        append_event(target, event)
    lines = target.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 5
    parsed = [json.loads(line) for line in lines]
    assert all(p == parsed[0] for p in parsed)


# ---------- write_in_flight / read_in_flight ----------


def test_write_in_flight_creates_parent_and_writes_pretty_json(
    tmp_path: Path,
) -> None:
    target = tmp_path / "nested" / IN_FLIGHT_FILENAME
    snapshot = {
        "schema_version": RUN_LOG_SCHEMA_VERSION,
        "run_id": "r1",
        "current_phase": "propose_steps",
    }
    write_in_flight(target, snapshot)
    assert read_in_flight(target) == snapshot
    # Human-readable — at least one internal newline from indent=2.
    assert target.read_text(encoding="utf-8").count("\n") > 1


def test_write_in_flight_overwrites_existing_snapshot(tmp_path: Path) -> None:
    target = tmp_path / IN_FLIGHT_FILENAME
    write_in_flight(target, {"schema_version": RUN_LOG_SCHEMA_VERSION, "phase": "first"})
    write_in_flight(target, {"schema_version": RUN_LOG_SCHEMA_VERSION, "phase": "second"})
    assert read_in_flight(target) == {
        "schema_version": RUN_LOG_SCHEMA_VERSION,
        "phase": "second",
    }


def test_write_in_flight_leaves_no_tempfile_on_success(tmp_path: Path) -> None:
    target = tmp_path / IN_FLIGHT_FILENAME
    write_in_flight(target, {"schema_version": RUN_LOG_SCHEMA_VERSION})
    leftovers = list(target.parent.glob("*.tmp"))
    assert leftovers == []


def test_write_in_flight_preserves_previous_snapshot_and_removes_tempfile_when_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import plan_tool.run_log as run_log_module

    target = tmp_path / IN_FLIGHT_FILENAME
    previous = {"schema_version": RUN_LOG_SCHEMA_VERSION, "phase": "previous"}
    write_in_flight(target, previous)

    def _raise_replace(*_args: object, **_kwargs: object) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(run_log_module.os, "replace", _raise_replace)
    with pytest.raises(OSError, match="replace failed"):
        write_in_flight(target, {"schema_version": RUN_LOG_SCHEMA_VERSION, "phase": "next"})

    assert read_in_flight(target) == previous
    assert list(target.parent.glob(f".{target.name}.*.tmp")) == []


def test_read_in_flight_returns_none_when_missing(tmp_path: Path) -> None:
    assert read_in_flight(tmp_path / "absent.json") is None


def test_read_in_flight_returns_none_on_malformed_json(tmp_path: Path) -> None:
    target = tmp_path / IN_FLIGHT_FILENAME
    target.write_text("not json{", encoding="utf-8")
    assert read_in_flight(target) is None


def test_read_in_flight_returns_none_on_schema_version_mismatch(
    tmp_path: Path,
) -> None:
    target = tmp_path / IN_FLIGHT_FILENAME
    target.write_text(json.dumps({"schema_version": 99}), encoding="utf-8")
    assert read_in_flight(target) is None


def test_read_in_flight_returns_none_when_top_level_not_dict(
    tmp_path: Path,
) -> None:
    target = tmp_path / IN_FLIGHT_FILENAME
    target.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    assert read_in_flight(target) is None


# ---------- completed-run readers ----------


def test_read_run_events_returns_empty_when_missing(tmp_path: Path) -> None:
    assert read_run_events(tmp_path / "absent.jsonl") == []


def test_read_run_events_returns_empty_on_oserror(tmp_path: Path) -> None:
    assert read_run_events(tmp_path) == []


def test_read_run_events_parses_each_line_in_order(tmp_path: Path) -> None:
    target = tmp_path / "run.jsonl"
    append_event(target, _make_run_start())
    append_event(target, _make_phase_end())
    append_event(
        target,
        RunEnd(ts="2026-05-14T12:35:00+00:00", run_id="r1", outcome="ok"),
    )
    assert [event["event"] for event in read_run_events(target)] == [
        "run_start",
        "phase_end",
        "run_end",
    ]


def test_read_run_events_skips_blank_and_damaged_lines(tmp_path: Path) -> None:
    target = tmp_path / "run.jsonl"
    target.write_text(
        '\n{"event":"run_start","run_id":"r1"}\n[1,2]\n42\n{"event":',
        encoding="utf-8",
    )
    assert read_run_events(target) == [{"event": "run_start", "run_id": "r1"}]


def test_read_run_events_keeps_mismatched_schema_version(tmp_path: Path) -> None:
    target = tmp_path / "run.jsonl"
    target.write_text(
        '{"event":"run_start","run_id":"r1","schema_version":99}\n',
        encoding="utf-8",
    )
    assert read_run_events(target)[0]["schema_version"] == 99


def test_read_run_outcome_returns_none_without_events(tmp_path: Path) -> None:
    assert read_run_outcome(tmp_path / "absent.jsonl") is None
    empty = tmp_path / "empty.jsonl"
    empty.write_text("\n \n", encoding="utf-8")
    assert read_run_outcome(empty) is None


def test_read_run_outcome_extracts_run_end_and_optional_error(
    tmp_path: Path,
) -> None:
    target = tmp_path / "run.jsonl"
    target.write_text(
        '{"event":"run_end","run_id":"r1","outcome":"failed",'
        '"rc":2,"duration_ms":45,"error":"boom"}\n',
        encoding="utf-8",
    )
    outcome = read_run_outcome(target)
    assert outcome == RunOutcome(
        run_id="r1",
        completed=True,
        outcome="failed",
        rc=2,
        duration_ms=45,
        error="boom",
    )


def test_read_run_outcome_error_defaults_to_none(tmp_path: Path) -> None:
    target = tmp_path / "run.jsonl"
    target.write_text(
        '{"event":"run_end","run_id":"r1","outcome":"ok","rc":0,"duration_ms":1}\n',
        encoding="utf-8",
    )
    outcome = read_run_outcome(target)
    assert outcome is not None
    assert outcome.error is None


def test_read_run_outcome_incomplete_when_no_run_end(tmp_path: Path) -> None:
    target = tmp_path / "run.jsonl"
    append_event(target, _make_run_start("unfinished"))
    assert read_run_outcome(target) == RunOutcome(run_id="unfinished", completed=False)


def test_read_run_outcome_takes_last_run_end(tmp_path: Path) -> None:
    target = tmp_path / "run.jsonl"
    target.write_text(
        '{"event":"run_end","run_id":"first","outcome":"failed","rc":1}\n'
        '{"event":"run_end","run_id":"last","outcome":"ok","rc":0,'
        '"duration_ms":7}\n',
        encoding="utf-8",
    )
    outcome = read_run_outcome(target)
    assert outcome is not None
    assert (outcome.run_id, outcome.outcome, outcome.duration_ms) == (
        "last",
        "ok",
        7,
    )


def test_read_run_outcome_collects_iteration_outcomes(tmp_path: Path) -> None:
    target = tmp_path / "run.jsonl"
    for step_id, step_outcome in ((1, "ok"), (2, "failed")):
        append_event(
            target,
            IterationEnd(
                ts="2026-05-14T12:34:59+00:00",
                run_id="r1",
                step_id=step_id,
                outcome=step_outcome,
            ),
        )
    outcome = read_run_outcome(target)
    assert outcome is not None
    assert outcome.iteration_outcomes == {1: "ok", 2: "failed"}


def test_read_run_outcome_from_real_writer(tmp_path: Path) -> None:
    writer = _make_writer(tmp_path)
    writer.run_end(outcome="ok", rc=0)
    outcome = read_run_outcome(writer.log_path)
    assert outcome is not None
    assert outcome.run_id == writer.run_id
    assert outcome.completed is True
    assert outcome.outcome == "ok"
    assert outcome.rc == 0


def test_run_outcome_is_frozen() -> None:
    outcome = RunOutcome(run_id="r1", completed=True)
    with pytest.raises(dataclasses.FrozenInstanceError):
        outcome.completed = False  # type: ignore[misc]


# ---------- RunLogWriter: sink + parse_failure coverage ----------


def _make_writer(
    tmp_path: Path,
    slug: str = "demo",
    context: dict[str, object] | None = None,
) -> "RunLogWriter":
    """Construct a real writer rooted at ``tmp_path``. Wraps ``start()``
    so each test gets an isolated log + in-flight snapshot."""
    from plan_tool.run_log import RunLogWriter

    return RunLogWriter.start(
        repo_root=tmp_path,
        slug=slug,
        command="run",
        argv=["plan-tool", "run", slug],
        context=context,
    )


def _read_events(log_path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _roadmap_context(*, active_plan_id: str | None = None) -> dict[str, object]:
    return {
        "roadmap_action": "materialize",
        "roadmap_slug": "demo",
        "requested_plan_id": None,
        "active_plan_id": active_plan_id,
    }


def test_context_enabled_writer_flattens_context_into_run_start_and_snapshot(
    tmp_path: Path,
) -> None:
    writer = RunLogWriter.start(
        repo_root=tmp_path,
        slug="demo",
        command="roadmap",
        argv=["plan-tool", "roadmap", "demo", "--materialize"],
        context=_roadmap_context(),
    )

    start = _read_events(writer.log_path)[0]
    snapshot = read_in_flight(writer.in_flight_path)
    assert snapshot is not None
    for payload in (start, snapshot):
        assert payload["command"] == "roadmap"
        assert payload["roadmap_action"] == "materialize"
        assert payload["roadmap_slug"] == "demo"
        assert payload["requested_plan_id"] is None
        assert payload["active_plan_id"] is None


def test_context_reaches_regular_shell_sink_terminal_and_snapshot_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import plan_tool.run_log as run_log_module
    from plan_tool import shell

    snapshots: list[dict[str, object]] = []
    real_write_in_flight = run_log_module.write_in_flight

    def _capture_snapshot(path: Path, snapshot: dict[str, object]) -> None:
        snapshots.append(dict(snapshot))
        real_write_in_flight(path, snapshot)

    monkeypatch.setattr(run_log_module, "write_in_flight", _capture_snapshot)
    writer = RunLogWriter.start(
        repo_root=tmp_path,
        slug="demo",
        command="roadmap",
        argv=["plan-tool", "roadmap", "demo", "--materialize"],
        context=_roadmap_context(active_plan_id="plan-auth"),
    )
    writer.phase_start("materialize")
    with writer.bind_shell_sink(phase="materialize", attempt=1):
        sink = shell.get_active_sink()
        assert sink is not None
        sink(
            ClaudeCallEnd(
                ts="2026-05-14T12:00:00+00:00",
                run_id="",
                phase="claude_invoke",
                attempt=1,
                rc=0,
                duration_ms=5,
                stdout_bytes=3,
            )
        )
    writer.backend_spawn(phase="materialize", attempt=1, backend="claude")
    writer.run_end(outcome="ok", rc=0)

    events = _read_events(writer.log_path)
    assert {event["event"] for event in events} >= {
        "phase_start",
        "claude_call_end",
        "backend_spawn",
        "run_end",
    }
    for payload in [*events, *snapshots]:
        assert payload["command"] == "roadmap"
        assert payload["roadmap_action"] == "materialize"
        assert payload["roadmap_slug"] == "demo"
        assert payload["active_plan_id"] == "plan-auth"


def test_context_update_preserves_phase_end_attribution_then_clears_snapshot(
    tmp_path: Path,
) -> None:
    writer = RunLogWriter.start(
        repo_root=tmp_path,
        slug="demo",
        command="roadmap",
        argv=[],
        context=_roadmap_context(),
    )
    writer.update_context(active_plan_id="plan-auth", seed_attempt=1, backend_attempt=2)
    writer.phase_end("materialize", 10, "ok")
    writer.update_context(seed_attempt=None, backend_attempt=None)
    writer.update_context(active_plan_id=None)

    phase_end = next(
        event for event in _read_events(writer.log_path) if event["event"] == "phase_end"
    )
    snapshot = read_in_flight(writer.in_flight_path)
    assert snapshot is not None
    assert phase_end["active_plan_id"] == "plan-auth"
    assert phase_end["seed_attempt"] == 1
    assert phase_end["backend_attempt"] == 2
    assert snapshot["active_plan_id"] is None
    assert snapshot["seed_attempt"] is None
    assert snapshot["backend_attempt"] is None

    writer.run_end(outcome="ok", rc=0)
    assert _read_events(writer.log_path)[-1]["active_plan_id"] is None


def test_context_update_preserves_snapshot_lifecycle_fields(tmp_path: Path) -> None:
    writer = RunLogWriter.start(
        repo_root=tmp_path,
        slug="demo",
        command="roadmap",
        argv=[],
        context=_roadmap_context(),
    )
    writer.phase_start("materialize")
    writer.update_context(active_plan_id="plan-auth")

    snapshot = read_in_flight(writer.in_flight_path)
    assert snapshot is not None
    assert snapshot["schema_version"] == RUN_LOG_SCHEMA_VERSION
    assert snapshot["run_id"] == writer.run_id
    assert snapshot["command"] == "roadmap"
    assert snapshot["plan_slug"] == "demo"
    assert snapshot["current_phase"] == "materialize"
    assert snapshot["status"] == IN_FLIGHT_STATUS_RUNNING
    assert "started_at" in snapshot
    assert "last_event_ts" in snapshot


def test_context_is_copied_and_cannot_override_event_identity(
    tmp_path: Path,
) -> None:
    context = _roadmap_context()
    context.update({"command": "other", "run_id": "not-a-run", "event": "other"})
    writer = RunLogWriter.start(
        repo_root=tmp_path,
        slug="demo",
        command="roadmap",
        argv=[],
        context=context,
    )
    context["roadmap_action"] = "mutated-after-start"
    writer.update_context(command="changed-after-start", active_plan_id="plan-auth")
    writer.phase_start("materialize", command="event-command", roadmap_action="event-action")

    phase_start = next(
        event for event in _read_events(writer.log_path) if event["event"] == "phase_start"
    )
    snapshot = read_in_flight(writer.in_flight_path)
    assert snapshot is not None
    assert phase_start["run_id"] == writer.run_id
    assert phase_start["event"] == "phase_start"
    assert phase_start["command"] == "roadmap"
    assert phase_start["roadmap_action"] == "materialize"
    assert phase_start["active_plan_id"] == "plan-auth"
    assert snapshot["run_id"] == writer.run_id
    assert snapshot["command"] == "roadmap"


def test_writer_without_context_keeps_existing_event_and_snapshot_shape(
    tmp_path: Path,
) -> None:
    writer = _make_writer(tmp_path)
    start = _read_events(writer.log_path)[0]
    snapshot = read_in_flight(writer.in_flight_path)
    assert snapshot is not None
    assert set(start) == {
        "ts",
        "run_id",
        "event",
        "schema_version",
        "command",
        "plan_slug",
        "argv",
        "pid",
        "cwd",
    }
    assert set(snapshot) == {
        "schema_version",
        "run_id",
        "command",
        "plan_slug",
        "started_at",
        "log_path",
        "status",
    }
    assert start["schema_version"] == RUN_LOG_SCHEMA_VERSION == 2


def test_install_call_end_sink_substitutes_run_id_phase_attempt(
    tmp_path: Path,
) -> None:
    """The stateful sink overrides the event's empty ``run_id`` and
    replaces ``phase`` / ``attempt`` with the install-time values.
    This is the contract ``create.py``'s ``shell_claude_invoker``
    relies on — the wrapper passes no kwargs through, so the
    shell-side event arrives with the defaults."""
    from plan_tool import shell
    from plan_tool.run_log import ClaudeCallEnd

    writer = _make_writer(tmp_path)
    writer.install_call_end_sink("propose_steps", 1)
    try:
        sink = shell.get_active_sink()
        assert sink is not None
        # Emit a shell-side event with the DEFAULTS shell.claude_invoke
        # would supply when no kwargs are threaded through the wrapper.
        sink(
            ClaudeCallEnd(
                ts="2026-05-14T12:00:00+00:00",
                run_id="",
                phase="claude_invoke",
                attempt=1,
                rc=0,
                duration_ms=42,
                stdout_bytes=10,
            )
        )
    finally:
        writer.uninstall_call_end_sink()

    events = _read_events(writer.log_path)
    end = next(e for e in events if e["event"] == "claude_call_end")
    assert end["run_id"] == writer.run_id
    assert end["phase"] == "propose_steps"
    assert end["attempt"] == 1
    assert end["duration_ms"] == 42


def test_uninstall_call_end_sink_restores_previous(
    tmp_path: Path,
) -> None:
    """Uninstall pops the prev-sink stack so a sink installed before
    ours (e.g. by an outer writer) survives our scope intact."""
    from plan_tool import shell
    from plan_tool.run_log import ClaudeCallEnd

    # Pre-install an outer sentinel sink we expect to see again.
    outer_calls: list = []
    outer_sink = lambda e: outer_calls.append(e)
    shell.set_active_sink(outer_sink)
    try:
        writer = _make_writer(tmp_path, slug="outer")
        writer.install_call_end_sink("inner_phase", 1)
        assert shell.get_active_sink() is not outer_sink
        writer.uninstall_call_end_sink()
        assert shell.get_active_sink() is outer_sink
    finally:
        shell.set_active_sink(None)


def test_install_call_end_sink_nested_pairs_unwind_correctly(
    tmp_path: Path,
) -> None:
    """Two install/uninstall cycles on the same writer must use a stack
    — the second install can't clobber the first's prev-sink slot."""
    from plan_tool import shell

    outer_sink = lambda e: None
    shell.set_active_sink(outer_sink)
    try:
        writer = _make_writer(tmp_path)
        writer.install_call_end_sink("phase_a", 1)
        first_installed = shell.get_active_sink()
        writer.install_call_end_sink("phase_b", 1)
        # The second install captured first_installed (our sink) as its
        # prev. Uninstalling pops back to first_installed.
        writer.uninstall_call_end_sink()
        assert shell.get_active_sink() is first_installed
        writer.uninstall_call_end_sink()
        # Final uninstall pops back to the original outer_sink — the
        # bug this test pins: without a stack, the second install would
        # have clobbered prev_shell_sink to first_installed, and the
        # final restore would set the sink to first_installed instead
        # of outer_sink.
        assert shell.get_active_sink() is outer_sink
    finally:
        shell.set_active_sink(None)


def test_uninstall_call_end_sink_safe_without_install(
    tmp_path: Path,
) -> None:
    """Uninstall on a fresh writer must no-op (empty stack)."""
    from plan_tool import shell

    writer = _make_writer(tmp_path)
    # Should not raise.
    writer.uninstall_call_end_sink()
    # Shell sink is whatever it was before — must not have been clobbered.
    assert shell.get_active_sink() is None


def test_bind_shell_sink_overrides_phase_and_attempt(
    tmp_path: Path,
) -> None:
    """``bind_shell_sink`` substitutes the bind-time ``phase`` /
    ``attempt`` over the event's own labels — load-bearing for
    ``launcher.run_step`` / ``apply_finding`` callers that don't
    thread kwargs through the shell wrapper."""
    from plan_tool import shell
    from plan_tool.run_log import ClaudeCallEnd

    writer = _make_writer(tmp_path)
    with writer.bind_shell_sink(phase="apply_finding_dispatch", attempt=2):
        sink = shell.get_active_sink()
        assert sink is not None
        sink(
            ClaudeCallEnd(
                ts="2026-05-14T12:00:00+00:00",
                run_id="",
                phase="claude_invoke",
                attempt=1,
                rc=0,
                duration_ms=5,
                stdout_bytes=3,
            )
        )

    events = _read_events(writer.log_path)
    end = next(e for e in events if e["event"] == "claude_call_end")
    assert end["run_id"] == writer.run_id
    assert end["phase"] == "apply_finding_dispatch"
    assert end["attempt"] == 2


def test_bind_shell_sink_restores_prev_on_exception(
    tmp_path: Path,
) -> None:
    """A raise inside ``with bind_shell_sink`` must restore the
    previous sink — otherwise a missing-claude failure in
    ``invoker(prompt)`` would leak a stale sink onto the next call."""
    from plan_tool import shell

    outer_sink = lambda e: None
    shell.set_active_sink(outer_sink)
    try:
        writer = _make_writer(tmp_path)
        with pytest.raises(RuntimeError):
            with writer.bind_shell_sink(phase="x", attempt=1):
                raise RuntimeError("simulated invoker failure")
        # Outer sink restored despite the raise.
        assert shell.get_active_sink() is outer_sink
    finally:
        shell.set_active_sink(None)


def test_parse_failure_emits_pointer_not_payload(
    tmp_path: Path,
) -> None:
    """The ``parse_failure`` event records the failure-path string;
    it never embeds the raw response payload (which would blow past
    the 4096-byte per-line cap on a non-trivial response)."""
    writer = _make_writer(tmp_path)
    writer.parse_failure(
        phase="per_step_body",
        attempt=1,
        failure_path=".plan-tool/parse-failures/demo/01-attempt1-2026.txt",
        step_id=1,
        raw_bytes=2048,
    )
    events = _read_events(writer.log_path)
    pf = next(e for e in events if e["event"] == "parse_failure")
    assert pf["phase"] == "per_step_body"
    assert pf["attempt"] == 1
    assert pf["failure_path"].endswith(".txt")
    # ``**extra`` kwargs flow through to the payload.
    assert pf["step_id"] == 1
    assert pf["raw_bytes"] == 2048
    # The raw response payload is NOT in the event.
    assert "raw" not in pf
    assert "response" not in pf


# ---------- attempt_failed ----------


def test_attempt_failed_records_the_kind_and_passes_extra_through(
    tmp_path: Path,
) -> None:
    writer = _make_writer(tmp_path)
    writer.attempt_failed(
        phase="stage-1-domain",
        attempt=2,
        failure_kind="authored-review-rows",
        stage=1,
    )

    ev = next(e for e in _read_events(writer.log_path) if e["event"] == "attempt_failed")
    assert ev["run_id"] == writer.run_id
    assert ev["phase"] == "stage-1-domain"
    assert ev["attempt"] == 2
    assert ev["failure_kind"] == "authored-review-rows"
    # ``**extra`` kwargs flow through to the payload.
    assert ev["stage"] == 1
    # The reply bytes are deliberately absent — ``claude_call_end`` already
    # carries rc/duration/stdout_bytes for the same (phase, attempt).
    assert "raw" not in ev
    assert "rc" not in ev


# ---------- gate_violations ----------


def test_model_failure_receipt_records_safe_identity_and_sidecar_pointer(
    tmp_path: Path,
) -> None:
    writer = _make_writer(tmp_path)
    sidecar_path = tmp_path / ".plan-tool/parse-failures/demo/stage-1-attempt-2.txt"
    writer.model_failure_receipt(
        phase="stage-1-domain",
        attempt=2,
        reason="parse",
        response_bytes=17,
        response_sha256="a" * 64,
        sidecar_result=ModelResponseSidecarResult(
            ModelResponseSidecarOutcome.WRITTEN, path=sidecar_path
        ),
    )

    receipt = next(e for e in _read_events(writer.log_path) if e["event"] == "model_failure_receipt")
    assert receipt["phase"] == "stage-1-domain"
    assert receipt["attempt"] == 2
    assert receipt["reason"] == "parse"
    assert receipt["response_bytes"] == 17
    assert receipt["response_sha256"] == "a" * 64
    assert receipt["sidecar_disposition"] == "written"
    assert receipt["sidecar_path"] == ".plan-tool/parse-failures/demo/stage-1-attempt-2.txt"


@pytest.mark.parametrize(
    ("response_bytes", "response_sha256", "outcome"),
    [
        (None, None, ModelResponseSidecarOutcome.NO_RESPONSE),
        (8, "b" * 64, ModelResponseSidecarOutcome.NOT_RETAINED),
    ],
)
def test_model_failure_receipt_omits_path_when_no_response_or_sidecar_is_not_retained(
    tmp_path: Path,
    response_bytes: int | None,
    response_sha256: str | None,
    outcome: ModelResponseSidecarOutcome,
) -> None:
    writer = _make_writer(tmp_path)
    writer.model_failure_receipt(
        phase="stage-1-domain",
        attempt=1,
        reason="parse",
        response_bytes=response_bytes,
        response_sha256=response_sha256,
        sidecar_result=ModelResponseSidecarResult(outcome),
    )

    receipt = next(e for e in _read_events(writer.log_path) if e["event"] == "model_failure_receipt")
    assert receipt["sidecar_disposition"] == outcome.value
    assert "sidecar_path" not in receipt
    if response_bytes is None:
        assert receipt["response_sha256"] is None


def test_model_failure_receipt_never_serializes_raw_response_or_diagnostic_prose(
    tmp_path: Path,
) -> None:
    writer = _make_writer(tmp_path)
    writer.model_failure_receipt(
        phase="stage-1-domain",
        attempt=1,
        reason="parse",
        response_bytes=9,
        response_sha256="c" * 64,
        sidecar_result=ModelResponseSidecarResult(ModelResponseSidecarOutcome.NOT_RETAINED),
    )

    serialized = writer.log_path.read_text(encoding="utf-8")
    for forbidden in ("raw reply", "prompt body", "validation message", "provider transcript", "tool input"):
        assert forbidden not in serialized
    with pytest.raises(TypeError):
        writer.model_failure_receipt(  # type: ignore[call-arg]
            phase="stage-1-domain",
            attempt=2,
            reason="parse",
            response_bytes=9,
            response_sha256="c" * 64,
            sidecar_result=ModelResponseSidecarResult(ModelResponseSidecarOutcome.NOT_RETAINED),
            raw_response="raw reply",
        )


def test_model_failure_receipt_keeps_write_failed_response_identity_without_path(
    tmp_path: Path,
) -> None:
    writer = _make_writer(tmp_path)
    writer.model_failure_receipt(
        phase="stage-1-domain",
        attempt=1,
        reason="parse",
        response_bytes=21,
        response_sha256="d" * 64,
        sidecar_result=ModelResponseSidecarResult(ModelResponseSidecarOutcome.WRITE_FAILED),
    )

    receipt = next(e for e in _read_events(writer.log_path) if e["event"] == "model_failure_receipt")
    assert receipt["response_bytes"] == 21
    assert receipt["response_sha256"] == "d" * 64
    assert receipt["sidecar_disposition"] == "write-failed"
    assert "sidecar_path" not in receipt


def test_model_failure_receipt_does_not_refresh_or_replace_in_flight_snapshot(
    tmp_path: Path,
) -> None:
    writer = _make_writer(tmp_path)
    before = read_in_flight(writer.in_flight_path)
    writer.model_failure_receipt(
        phase="stage-1-domain",
        attempt=1,
        reason="parse",
        response_bytes=5,
        response_sha256="e" * 64,
        sidecar_result=ModelResponseSidecarResult(ModelResponseSidecarOutcome.NOT_RETAINED),
    )
    assert read_in_flight(writer.in_flight_path) == before


def test_gate_violations_records_every_message_when_they_fit(
    tmp_path: Path,
) -> None:
    writer = _make_writer(tmp_path)
    writer.gate_violations(
        phase="stage-2-constraints",
        attempt=2,
        messages=["row 'perf' has no disposition", "constraint c3 anchors nothing"],
        stage=2,
    )

    ev = next(e for e in _read_events(writer.log_path) if e["event"] == "gate_violations")
    assert ev["run_id"] == writer.run_id
    assert ev["attempt"] == 2
    assert ev["violations"] == [
        "row 'perf' has no disposition",
        "constraint c3 anchors nothing",
    ]
    assert ev["violation_count"] == 2
    assert ev["violations_omitted"] == 0
    # ``**extra`` kwargs flow through to the payload.
    assert ev["stage"] == 2


def test_gate_violations_drops_whole_messages_past_the_budget(
    tmp_path: Path,
) -> None:
    """A message is never cut mid-sentence — a half message reads as a
    different complaint than the one the gate made. The count stays exact."""
    writer = _make_writer(tmp_path)
    messages = [f"{i:02d} " + "x" * 300 for i in range(20)]

    writer.gate_violations(phase="p", attempt=1, messages=messages)

    ev = next(e for e in _read_events(writer.log_path) if e["event"] == "gate_violations")
    assert ev["violation_count"] == 20
    assert 0 < len(ev["violations"]) < 20
    assert ev["violations_omitted"] == 20 - len(ev["violations"])
    # Every retained message is whole, and they are the first ones.
    assert ev["violations"] == messages[: len(ev["violations"])]
    assert all("…<elided" not in m for m in ev["violations"])


def test_gate_violations_keeps_one_oversized_message_rather_than_none(
    tmp_path: Path,
) -> None:
    """An event reporting violations while showing none is worse than one
    showing a visibly elided message."""
    writer = _make_writer(tmp_path)

    writer.gate_violations(phase="p", attempt=1, messages=["y" * 9000])

    ev = next(e for e in _read_events(writer.log_path) if e["event"] == "gate_violations")
    assert ev["violation_count"] == 1
    assert ev["violations_omitted"] == 0
    assert len(ev["violations"]) == 1
    assert "…<elided" in ev["violations"][0]


@pytest.mark.parametrize(
    "make_message",
    [
        pytest.param(
            lambda i: f"id '{i}' is inventoried but never named in the body",
            id="prose",
        ),
        # Escaping is what lands on the line: each of these costs about twice
        # its character count once serialized. Sized so a budget counted in
        # *raw* bytes keeps 15 of them and blows the cap at 4132.
        pytest.param(lambda i: f"{i:02d}" + '"\\' * 64, id="escape-heavy"),
    ],
)
def test_gate_violations_line_stays_under_the_cap(tmp_path: Path, make_message) -> None:
    """The budget exists to keep the line writable — an observability event
    must never break the run it observes with ``RunLogLineTooLarge``."""
    writer = _make_writer(tmp_path)

    writer.gate_violations(
        phase="stage-2-constraints",
        attempt=1,
        messages=[make_message(i) for i in range(80)],
        stage=2,
    )

    line = next(
        raw
        for raw in writer.log_path.read_text(encoding="utf-8").splitlines()
        if '"gate_violations"' in raw
    )
    assert len(line.encode("utf-8")) + 1 <= 4096


# ---------- roadmap lifecycle events ----------


def test_roadmap_lifecycle_events_capture_effects_without_source_text(
    tmp_path: Path,
) -> None:
    writer = _make_writer(tmp_path)

    writer.roadmap_preflight_failed(check="upstream_artifacts")
    writer.roadmap_stage_written(
        phase="stage-4-plans",
        stage=4,
        artifact_path="docs/implementation-plans/roadmaps/widget/04-roadmap.md",
        artifact_digest="b" * 64,
        replaced=True,
        draft_seed_count=2,
    )
    writer.roadmap_seed_apply_result(
        outcome="applied",
        target_count=2,
        promotion_count=2,
        collision_count=0,
        missing_draft_count=0,
        malformed_draft_count=0,
        stale_draft_count=0,
        path_escaping_draft_count=0,
        duplicate_draft_count=0,
        digest_mismatched_draft_count=0,
    )

    events = _read_events(writer.log_path)
    written = next(e for e in events if e["event"] == "roadmap_stage_written")
    assert written["replaced"] is True
    assert written["draft_seed_count"] == 2
    applied = next(e for e in events if e["event"] == "roadmap_seed_apply_result")
    assert applied["promotion_count"] == 2


# ---------- Claude Call Observability: new event surface ----------


def test_claude_stream_event_optional_fields_default_to_none() -> None:
    """``tool_name`` and ``tool_input_summary`` are nullable — a
    ``system`` or ``result`` line carries no tool metadata, but the
    dataclass must still be constructible."""
    e = ClaudeStreamEvent(
        ts="2026-05-14T00:00:00+00:00",
        run_id="r",
        phase="propose_steps",
        attempt=1,
        kind="system",
    )
    assert e.tool_name is None
    assert e.tool_input_summary is None
    assert e.bytes_in_delta == 0
    assert e.event == "claude_stream_event"


def test_claude_call_progress_carries_elapsed_and_silent_ms() -> None:
    e = ClaudeCallProgress(
        ts="2026-05-14T00:00:00+00:00",
        run_id="r",
        phase="propose_steps",
        attempt=1,
        elapsed_ms=20_000,
        silent_ms=18_500,
        last_tool="Bash",
        last_activity_kind="tool_use",
    )
    assert e.elapsed_ms == 20_000
    assert e.silent_ms == 18_500
    assert e.last_tool == "Bash"
    assert e.last_activity_kind == "tool_use"
    assert e.event == "claude_call_progress"


def test_claude_call_stall_suspected_carries_threshold() -> None:
    e = ClaudeCallStallSuspected(
        ts="2026-05-14T00:00:00+00:00",
        run_id="r",
        phase="propose_steps",
        attempt=1,
        silent_ms=305_000,
        threshold_ms=300_000,
        last_tool="Bash",
    )
    assert e.silent_ms == 305_000
    assert e.threshold_ms == 300_000
    assert e.last_tool == "Bash"
    assert e.event == "claude_call_stall_suspected"


def test_new_observability_events_are_frozen() -> None:
    """Same immutability contract as the rest of the event surface —
    no in-place mutation between emission and serialization."""
    e = ClaudeStreamEvent(
        ts="2026-05-14T00:00:00+00:00",
        run_id="r",
        phase="x",
        attempt=1,
        kind="tool_use",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.kind = "result"  # type: ignore[misc]


def test_writer_claude_stream_event_emits_with_run_id(
    tmp_path: Path,
) -> None:
    """``RunLogWriter.claude_stream_event`` stamps the writer's
    ``run_id`` onto the payload (callers don't pass it), substitutes
    the discriminator, and lets ``**extra`` kwargs through — same
    contract as the other emit helpers."""
    writer = _make_writer(tmp_path)
    writer.claude_stream_event(
        phase="propose_steps",
        attempt=1,
        kind="tool_use",
        tool_name="Edit",
        tool_input_summary="apps/web/src/App.tsx",
        bytes_in_delta=384,
        step_id=3,
    )
    events = _read_events(writer.log_path)
    ev = next(e for e in events if e["event"] == "claude_stream_event")
    assert ev["run_id"] == writer.run_id
    assert ev["phase"] == "propose_steps"
    assert ev["attempt"] == 1
    assert ev["kind"] == "tool_use"
    assert ev["tool_name"] == "Edit"
    assert ev["tool_input_summary"] == "apps/web/src/App.tsx"
    assert ev["bytes_in_delta"] == 384
    # ``**extra`` flows through.
    assert ev["step_id"] == 3


def test_writer_claude_call_progress_emits_heartbeat(
    tmp_path: Path,
) -> None:
    writer = _make_writer(tmp_path)
    writer.claude_call_progress(
        phase="propose_steps",
        attempt=2,
        elapsed_ms=40_000,
        silent_ms=22_000,
        last_tool="Bash",
        last_activity_kind="tool_use",
        step_id=5,
    )
    events = _read_events(writer.log_path)
    ev = next(e for e in events if e["event"] == "claude_call_progress")
    assert ev["run_id"] == writer.run_id
    assert ev["phase"] == "propose_steps"
    assert ev["attempt"] == 2
    assert ev["elapsed_ms"] == 40_000
    assert ev["silent_ms"] == 22_000
    assert ev["last_tool"] == "Bash"
    assert ev["last_activity_kind"] == "tool_use"
    assert ev["step_id"] == 5


def test_writer_claude_call_stall_suspected_emits_one_marker(
    tmp_path: Path,
) -> None:
    writer = _make_writer(tmp_path)
    writer.claude_call_stall_suspected(
        phase="propose_steps",
        attempt=1,
        silent_ms=305_000,
        threshold_ms=300_000,
        last_tool="Bash",
        step_id=4,
    )
    events = _read_events(writer.log_path)
    ev = next(e for e in events if e["event"] == "claude_call_stall_suspected")
    assert ev["run_id"] == writer.run_id
    assert ev["phase"] == "propose_steps"
    assert ev["attempt"] == 1
    assert ev["silent_ms"] == 305_000
    assert ev["threshold_ms"] == 300_000
    assert ev["last_tool"] == "Bash"
    assert ev["step_id"] == 4


def test_writer_new_observability_payloads_use_canonical_separators(
    tmp_path: Path,
) -> None:
    """One more proof the new emitters route through ``_append_jsonl_line``
    — no ``": "`` or ``", "`` whitespace, one line per event, all under
    the per-line cap. Guards against a future regression where someone
    adds an emit helper that bypasses the shared serializer."""
    writer = _make_writer(tmp_path)
    writer.claude_stream_event(phase="p", attempt=1, kind="assistant_text")
    writer.claude_call_progress(phase="p", attempt=1, elapsed_ms=1, silent_ms=1)
    writer.claude_call_stall_suspected(phase="p", attempt=1, silent_ms=1, threshold_ms=1)
    raw = writer.log_path.read_text(encoding="utf-8")
    new_lines = [
        line
        for line in raw.splitlines()
        if any(
            kind in line
            for kind in (
                "claude_stream_event",
                "claude_call_progress",
                "claude_call_stall_suspected",
            )
        )
    ]
    assert len(new_lines) == 3
    for line in new_lines:
        assert '": ' not in line
        assert ", " not in line
        assert len((line + "\n").encode("utf-8")) <= 4096


# ---------- step 7 cross-cutting regression ----------
#
# These tests pin the fail-safe contract from the *combination* of
# read_in_flight + append_event + the RUN_LOG_SCHEMA_VERSION constant.
# They overlap deliberately with one assertion from earlier in this
# file (``test_read_in_flight_returns_none_on_schema_version_mismatch``)
# — the overlap is the point: step 1's test pins ``read_in_flight``
# alone, step 7's test pins the asymmetric ``append vs. read`` contract
# that lets a writer keep working while a reader degrades gracefully.


@pytest.mark.parametrize(
    "shape,payload",
    [
        ("empty_file", b""),
        ("malformed_json_truncated", b"not json{"),
        ("malformed_json_trailing_garbage", b'{"x":1}trail'),
        ("json_array_top_level", b"[1, 2, 3]"),
        ("schema_mismatch_dict", b'{"schema_version": 99, "run_id": "r"}'),
    ],
)
def test_read_in_flight_fails_safe_on_garbage(tmp_path: Path, shape: str, payload: bytes) -> None:
    """``read_in_flight`` returns ``None`` rather than raising on every
    documented garbage shape. Acts as a regression guard if someone
    later changes the fail-safe contract to throw — callers treat
    ``None`` as "no in-flight run" and any raise would break resume."""
    target = tmp_path / IN_FLIGHT_FILENAME
    target.write_bytes(payload)
    assert read_in_flight(target) is None


def test_run_log_schema_version_constant_is_canonical_source(
    tmp_path: Path,
) -> None:
    """The schema version is gated by one named constant. ``RunStart``
    defaults to it, and ``read_in_flight`` rejects on inequality —
    a future bump must be a single-site change, not a piecemeal one.
    Pins the "single source of truth" invariant."""
    obj = RunStart(
        ts="2026-05-14T00:00:00+00:00",
        run_id="r",
        command="x",
    )
    assert obj.schema_version == RUN_LOG_SCHEMA_VERSION

    target = tmp_path / IN_FLIGHT_FILENAME
    # A +1 snapshot is rejected by the reader.
    target.write_text(
        json.dumps({"schema_version": RUN_LOG_SCHEMA_VERSION + 1}),
        encoding="utf-8",
    )
    assert read_in_flight(target) is None

    # A matching version round-trips.
    target.write_text(
        json.dumps({"schema_version": RUN_LOG_SCHEMA_VERSION, "run_id": "r"}),
        encoding="utf-8",
    )
    assert read_in_flight(target) == {
        "schema_version": RUN_LOG_SCHEMA_VERSION,
        "run_id": "r",
    }


def test_append_event_does_not_reject_mismatched_schema_version(
    tmp_path: Path,
) -> None:
    """Schema enforcement lives at the reader, not the appender —
    an out-of-range ``RunStart`` is still written to disk. Regression
    guard: a future "validate-on-append" refactor would break the
    asymmetric contract where appenders never silently drop events
    while readers degrade gracefully on stale logs."""
    target = tmp_path / "log.jsonl"
    event = RunStart(
        ts="2026-05-14T00:00:00+00:00",
        run_id="r",
        schema_version=99,
        command="create",
        plan_slug="p",
        argv=[],
        pid=1,
        cwd="/",
    )
    append_event(target, event)
    lines = target.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    obj = json.loads(lines[0])
    assert obj["schema_version"] == 99
    assert obj["event"] == "run_start"


# ---- telemetry run_id scope (step 3) ----


def test_telemetry_run_id_scope_binds_writer_run_id(tmp_path: Path) -> None:
    """Inside the scope, the telemetry active run_id equals the writer's."""
    from plan_tool import telemetry

    writer = _make_writer(tmp_path)
    assert telemetry._active_run_id.get() == ""
    with writer.telemetry_run_id_scope():
        assert telemetry._active_run_id.get() == writer.run_id


def test_telemetry_run_id_scope_resets_on_exit(tmp_path: Path) -> None:
    """After the scope exits, the active run_id is back to its default."""
    from plan_tool import telemetry

    writer = _make_writer(tmp_path)
    with writer.telemetry_run_id_scope():
        pass
    assert telemetry._active_run_id.get() == ""


def test_telemetry_run_id_scope_resets_prior_value(tmp_path: Path) -> None:
    """An outer binding is restored on exit — the scope resets the prior
    value via a token, it does not hard-set ``""``."""
    from plan_tool import telemetry

    writer = _make_writer(tmp_path)
    token = telemetry.set_active_run_id("outer-run")
    try:
        with writer.telemetry_run_id_scope():
            assert telemetry._active_run_id.get() == writer.run_id
        assert telemetry._active_run_id.get() == "outer-run"
    finally:
        telemetry._active_run_id.reset(token)


def test_telemetry_run_id_scope_resets_on_exception(tmp_path: Path) -> None:
    """A body that raises still resets the ContextVar — the clear is a
    ``finally``/``__exit__``, not tied to the success path."""
    from plan_tool import telemetry

    writer = _make_writer(tmp_path)
    with pytest.raises(RuntimeError):
        with writer.telemetry_run_id_scope():
            raise RuntimeError("boom")
    assert telemetry._active_run_id.get() == ""


def test_run_id_reset_survives_run_end_failure(tmp_path: Path) -> None:
    """Mirrors ``run_cmd``'s finally structure: ``run_end`` is nested in its own
    ``try`` so its failure (OSError / RunLogLineTooLarge) cannot skip the scope's
    ``__exit__``. Without the nesting the reset was skipped and a stale run_id
    leaked into the next run."""
    from plan_tool import telemetry

    writer = _make_writer(tmp_path)
    scope = writer.telemetry_run_id_scope()
    scope.__enter__()
    assert telemetry._active_run_id.get() == writer.run_id
    with pytest.raises(OSError):
        try:
            # ... run body ...
            pass
        finally:
            try:
                raise OSError("run_end failed: disk full")  # stand-in for run_end
            finally:
                scope.__exit__(None, None, None)
    assert telemetry._active_run_id.get() == ""  # reset despite run_end raising


def test_recorded_decision_inside_scope_carries_run_id(tmp_path: Path) -> None:
    """A decision recorded inside the scope carries the writer's run_id; one
    recorded outside any scope carries ``""``."""
    from plan_tool import telemetry

    writer = _make_writer(tmp_path)
    telemetry.record_decision(tmp_path, kind="convergence", decision="diagnosed", plan_slug="demo")
    with writer.telemetry_run_id_scope():
        telemetry.record_decision(
            tmp_path, kind="convergence", decision="diagnosed", plan_slug="demo"
        )

    events = telemetry.read_decisions(tmp_path)
    assert len(events) == 2
    outside, inside = events
    assert outside.run_id == ""
    assert inside.run_id == writer.run_id


def test_two_writers_do_not_leak_run_id(tmp_path: Path) -> None:
    """Two writers with distinct run_ids (the sweep shape): each scope binds
    its own id and clearing one restores ``""`` before the next binds."""
    from plan_tool import telemetry

    first = _make_writer(tmp_path, slug="a")
    second = _make_writer(tmp_path, slug="b")
    assert first.run_id != second.run_id

    with first.telemetry_run_id_scope():
        assert telemetry._active_run_id.get() == first.run_id
    assert telemetry._active_run_id.get() == ""
    with second.telemetry_run_id_scope():
        assert telemetry._active_run_id.get() == second.run_id
    assert telemetry._active_run_id.get() == ""


# ---------- backend lifecycle events: backend_spawn / backend_termination /
# run_interrupted / backend_recovery_wait ----------


def test_backend_spawn_serializes_with_discriminator_and_fields() -> None:
    e = BackendSpawn(
        ts="2026-05-14T00:00:00+00:00",
        run_id="r",
        phase="claude_invoke",
        attempt=1,
        backend="claude",
        transport="argv",
        child_pid=1234,
        effective_timeout_ms=60_000,
        prompt_bytes=512,
    )
    obj = dataclasses.asdict(e)
    assert obj["event"] == "backend_spawn"
    assert obj["phase"] == "claude_invoke"
    assert obj["attempt"] == 1
    assert obj["backend"] == "claude"
    assert obj["transport"] == "argv"
    assert obj["child_pid"] == 1234
    assert obj["effective_timeout_ms"] == 60_000
    assert obj["prompt_bytes"] == 512
    assert json.loads(json.dumps(obj)) == obj


def test_backend_spawn_optional_fields_default_to_none() -> None:
    e = BackendSpawn(
        ts="2026-05-14T00:00:00+00:00",
        run_id="r",
        phase="claude_invoke",
        attempt=1,
        backend="claude",
    )
    assert e.transport is None
    assert e.child_pid is None
    assert e.effective_timeout_ms is None
    assert e.prompt_bytes is None


def test_backend_termination_serializes_with_discriminator_and_fields() -> None:
    e = BackendTermination(
        ts="2026-05-14T00:00:00+00:00",
        run_id="r",
        phase="claude_invoke",
        attempt=1,
        backend="claude",
        reason="backend_nonzero",
        duration_ms=4200,
        signal_or_timeout="SIGKILL",
        silent_ms=9000,
    )
    obj = dataclasses.asdict(e)
    assert obj["event"] == "backend_termination"
    assert obj["reason"] == "backend_nonzero"
    assert obj["duration_ms"] == 4200
    assert obj["signal_or_timeout"] == "SIGKILL"
    assert obj["silent_ms"] == 9000
    assert json.loads(json.dumps(obj)) == obj


def test_run_interrupted_serializes_with_discriminator_and_fields() -> None:
    e = RunInterrupted(
        ts="2026-05-14T00:00:00+00:00",
        run_id="r",
        phase="claude_invoke",
        attempt=1,
        source="recovery_wait",
    )
    obj = dataclasses.asdict(e)
    assert obj["event"] == "run_interrupted"
    assert obj["source"] == "recovery_wait"
    assert obj["signal"] == "SIGINT"
    assert json.loads(json.dumps(obj)) == obj


def test_run_interrupted_accepts_source_proc_wait() -> None:
    """``"proc_wait"`` — reserved by step 5 for the streaming-lane spawn/
    termination work — round-trips like any other ``source`` value. Step 7
    is the first producer of this value (a ``KeyboardInterrupt`` caught
    during ``backend_runner.run_streaming_once``'s own ``proc.wait()``)."""
    e = RunInterrupted(
        ts="2026-05-14T00:00:00+00:00",
        run_id="r",
        phase="claude_call",
        attempt=1,
        source="proc_wait",
    )
    obj = dataclasses.asdict(e)
    assert obj["source"] == "proc_wait"
    assert json.loads(json.dumps(obj)) == obj


def test_run_log_writer_satisfies_the_runner_observer_contract(
    tmp_path: Path,
) -> None:
    """A real :class:`RunLogWriter` provides every capability
    :class:`RunnerObserver` needs with zero adaptation — catches a future
    rename of a ``RunLogWriter`` method here rather than as a silent
    ``AttributeError`` deep in ``backend_runner.py``."""
    from plan_tool.run_log import RunnerObserver

    writer = _make_writer(tmp_path)
    assert isinstance(writer, RunnerObserver)


def test_backend_recovery_wait_serializes_with_discriminator_and_fields() -> None:
    e = BackendRecoveryWait(
        ts="2026-05-14T00:00:00+00:00",
        run_id="r",
        phase="claude_invoke",
        attempt=1,
        reason="rate_limit",
        delay_ms=3600_000,
        next_attempt=2,
        backend="claude",
    )
    obj = dataclasses.asdict(e)
    assert obj["event"] == "backend_recovery_wait"
    assert obj["next_attempt"] == 2
    assert obj["delay_ms"] == 3600_000
    assert json.loads(json.dumps(obj)) == obj


def test_new_termination_events_are_frozen() -> None:
    base = dict(ts="2026-05-14T00:00:00+00:00", run_id="r")
    with pytest.raises(dataclasses.FrozenInstanceError):
        BackendSpawn(phase="x", attempt=1, backend="claude", **base).phase = "y"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        BackendTermination(
            phase="x",
            attempt=1,
            backend="claude",
            reason="completed",
            duration_ms=1,
            **base,
        ).reason = "y"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        RunInterrupted(phase="x", attempt=1, source="recovery_wait", **base).source = "y"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        BackendRecoveryWait(
            phase="x",
            attempt=1,
            reason="rate_limit",
            delay_ms=0,
            next_attempt=2,
            backend="claude",
            **base,
        ).reason = "y"  # type: ignore[misc]


def test_writer_backend_spawn_and_termination_round_trip(
    tmp_path: Path,
) -> None:
    writer = _make_writer(tmp_path)
    writer.backend_spawn(phase="claude_invoke", attempt=1, backend="claude")
    writer.backend_termination(
        phase="claude_invoke",
        attempt=1,
        backend="claude",
        reason="completed",
        duration_ms=500,
    )
    events = _read_events(writer.log_path)
    spawn = next(e for e in events if e["event"] == "backend_spawn")
    term = next(e for e in events if e["event"] == "backend_termination")
    assert spawn["run_id"] == writer.run_id
    assert spawn["phase"] == "claude_invoke"
    assert term["run_id"] == writer.run_id
    assert term["reason"] == "completed"
    assert term["duration_ms"] == 500


def test_writer_run_end_defaults_termination_reason_from_backend_termination(
    tmp_path: Path,
) -> None:
    writer = _make_writer(tmp_path)
    writer.backend_termination(
        phase="claude_invoke",
        attempt=1,
        backend="claude",
        reason="backend_nonzero",
        duration_ms=10,
    )
    writer.run_end(outcome="error", rc=1)
    events = _read_events(writer.log_path)
    end = next(e for e in events if e["event"] == "run_end")
    assert end["termination_reason"] == "backend_nonzero"


def test_writer_run_end_reflects_terminal_of_multiple_backend_terminations(
    tmp_path: Path,
) -> None:
    """The multi-spawn bracket proof: the writer tracks the *terminal*
    reason, not the first one."""
    writer = _make_writer(tmp_path)
    writer.backend_termination(
        phase="claude_invoke",
        attempt=1,
        backend="claude",
        reason="backend_nonzero",
        duration_ms=10,
    )
    writer.backend_termination(
        phase="claude_invoke",
        attempt=2,
        backend="claude",
        reason="completed",
        duration_ms=20,
    )
    writer.run_end(outcome="ok", rc=0)
    events = _read_events(writer.log_path)
    end = next(e for e in events if e["event"] == "run_end")
    assert end["termination_reason"] == "completed"


def test_writer_run_interrupted_overrides_tracked_termination_reason(
    tmp_path: Path,
) -> None:
    writer = _make_writer(tmp_path)
    writer.backend_termination(
        phase="claude_invoke",
        attempt=1,
        backend="claude",
        reason="backend_nonzero",
        duration_ms=10,
    )
    writer.run_interrupted(
        phase="claude_invoke",
        attempt=1,
        source="recovery_wait",
    )
    writer.run_end(outcome="error", rc=1)
    events = _read_events(writer.log_path)
    end = next(e for e in events if e["event"] == "run_end")
    assert end["termination_reason"] == "operator_interrupt"


def test_writer_run_end_omits_termination_reason_when_never_set(
    tmp_path: Path,
) -> None:
    writer = _make_writer(tmp_path)
    writer.run_end(outcome="ok", rc=0)
    events = _read_events(writer.log_path)
    end = next(e for e in events if e["event"] == "run_end")
    assert "termination_reason" not in end


def test_writer_run_end_explicit_termination_reason_overrides_tracked_value(
    tmp_path: Path,
) -> None:
    writer = _make_writer(tmp_path)
    writer.backend_termination(
        phase="claude_invoke",
        attempt=1,
        backend="claude",
        reason="backend_nonzero",
        duration_ms=10,
    )
    writer.run_end(outcome="ok", rc=0, termination_reason="configured_timeout")
    events = _read_events(writer.log_path)
    end = next(e for e in events if e["event"] == "run_end")
    assert end["termination_reason"] == "configured_timeout"


def test_install_call_end_sink_also_binds_run_logger(tmp_path: Path) -> None:
    from plan_tool import shell

    writer = _make_writer(tmp_path)
    writer.install_call_end_sink("propose_steps", 1)
    try:
        assert shell.get_active_run_logger() is writer
    finally:
        writer.uninstall_call_end_sink()


def test_uninstall_call_end_sink_restores_previous_run_logger(
    tmp_path: Path,
) -> None:
    from plan_tool import shell

    outer = _make_writer(tmp_path, slug="outer")
    shell.set_active_run_logger(outer)
    try:
        writer = _make_writer(tmp_path, slug="inner")
        writer.install_call_end_sink("inner_phase", 1)
        assert shell.get_active_run_logger() is writer
        writer.uninstall_call_end_sink()
        assert shell.get_active_run_logger() is outer
    finally:
        shell.set_active_run_logger(None)


def test_bind_shell_sink_also_binds_and_restores_run_logger(
    tmp_path: Path,
) -> None:
    from plan_tool import shell

    writer = _make_writer(tmp_path)
    with writer.bind_shell_sink(phase="apply_finding_dispatch", attempt=2):
        assert shell.get_active_run_logger() is writer
    assert shell.get_active_run_logger() is None


def test_bind_shell_sink_restores_prev_run_logger_on_exception(
    tmp_path: Path,
) -> None:
    from plan_tool import shell

    outer = _make_writer(tmp_path, slug="outer")
    shell.set_active_run_logger(outer)
    try:
        writer = _make_writer(tmp_path, slug="inner")
        with pytest.raises(RuntimeError):
            with writer.bind_shell_sink(phase="x", attempt=1):
                raise RuntimeError("simulated invoker failure")
        assert shell.get_active_run_logger() is outer
    finally:
        shell.set_active_run_logger(None)


# ---------- in-flight snapshot refresh (step 9) ----------


def test_start_snapshot_reports_running_status(tmp_path: Path) -> None:
    writer = _make_writer(tmp_path)
    snapshot = read_in_flight(writer.in_flight_path)
    assert snapshot is not None
    assert snapshot["status"] == IN_FLIGHT_STATUS_RUNNING


def test_phase_start_refreshes_current_phase(tmp_path: Path) -> None:
    writer = _make_writer(tmp_path)
    writer.phase_start("propose_steps")
    snapshot = read_in_flight(writer.in_flight_path)
    assert snapshot is not None
    assert snapshot["current_phase"] == "propose_steps"
    assert "last_event_ts" in snapshot


def test_refresh_keeps_snapshot_readable(tmp_path: Path) -> None:
    """After several refreshes the snapshot still round-trips through
    ``read_in_flight`` — the merge-not-rebuild contract keeps every
    ``start()`` field alive across every later write."""
    writer = _make_writer(tmp_path)
    writer.phase_start("propose_steps")
    writer.backend_spawn(phase="propose_steps", attempt=1, backend="claude")
    writer.claude_call_progress(
        phase="propose_steps",
        attempt=1,
        elapsed_ms=500,
        silent_ms=100,
    )
    snapshot = read_in_flight(writer.in_flight_path)
    assert snapshot is not None
    assert snapshot["schema_version"] == RUN_LOG_SCHEMA_VERSION
    assert snapshot["run_id"] == writer.run_id
    assert snapshot["command"] == "run"
    assert snapshot["plan_slug"] == "demo"
    assert "started_at" in snapshot
    assert "log_path" in snapshot


def test_backend_spawn_refreshes_snapshot(tmp_path: Path) -> None:
    writer = _make_writer(tmp_path)
    writer.backend_spawn(
        phase="claude_invoke",
        attempt=1,
        backend="claude",
        transport="streaming",
        child_pid=4242,
        effective_timeout_ms=60000,
        prompt_bytes=128,
    )
    snapshot = read_in_flight(writer.in_flight_path)
    assert snapshot is not None
    assert snapshot["status"] == IN_FLIGHT_STATUS_RUNNING
    assert snapshot["child_pid"] == 4242
    assert snapshot["effective_timeout_ms"] == 60000
    assert snapshot["transport"] == "streaming"
    assert snapshot["prompt_bytes"] == 128


def test_heartbeat_refreshes_elapsed_and_silent_ms(tmp_path: Path) -> None:
    writer = _make_writer(tmp_path)
    writer.claude_call_progress(
        phase="claude_invoke",
        attempt=1,
        elapsed_ms=1500,
        silent_ms=250,
        last_tool="Bash",
        last_activity_kind="tool_use",
    )
    snapshot = read_in_flight(writer.in_flight_path)
    assert snapshot is not None
    assert snapshot["elapsed_ms"] == 1500
    assert snapshot["silent_ms"] == 250
    assert snapshot["last_tool"] == "Bash"
    assert snapshot["last_activity_kind"] == "tool_use"


def test_heartbeat_never_writes_status(tmp_path: Path) -> None:
    """A heartbeat after ``backend_recovery_wait`` leaves the
    awaiting-retry status in place while updating the timing fields —
    the rule that makes a late heartbeat harmless."""
    writer = _make_writer(tmp_path)
    writer.backend_recovery_wait(
        phase="claude_invoke",
        attempt=1,
        reason="rate_limit",
        delay_ms=5000,
        next_attempt=2,
        backend="claude",
    )
    writer.claude_call_progress(
        phase="claude_invoke",
        attempt=2,
        elapsed_ms=100,
        silent_ms=50,
    )
    snapshot = read_in_flight(writer.in_flight_path)
    assert snapshot is not None
    assert snapshot["status"] == IN_FLIGHT_STATUS_AWAITING_RETRY
    assert snapshot["elapsed_ms"] == 100


def test_backend_termination_writes_status_and_reason(tmp_path: Path) -> None:
    writer = _make_writer(tmp_path)
    writer.backend_termination(
        phase="claude_invoke",
        attempt=1,
        backend="claude",
        reason="backend_nonzero",
        duration_ms=10,
    )
    snapshot = read_in_flight(writer.in_flight_path)
    assert snapshot is not None
    assert snapshot["status"] == IN_FLIGHT_STATUS_TERMINATED
    assert snapshot["termination_reason"] == "backend_nonzero"


def test_recovery_wait_status_distinct_from_termination(tmp_path: Path) -> None:
    writer = _make_writer(tmp_path)
    writer.backend_recovery_wait(
        phase="claude_invoke",
        attempt=1,
        reason="rate_limit",
        delay_ms=3000,
        next_attempt=2,
        backend="claude",
    )
    snapshot = read_in_flight(writer.in_flight_path)
    assert snapshot is not None
    assert snapshot["status"] == IN_FLIGHT_STATUS_AWAITING_RETRY
    assert snapshot["status"] != IN_FLIGHT_STATUS_TERMINATED


def test_late_heartbeat_after_termination_keeps_terminated_status(
    tmp_path: Path,
) -> None:
    """Pins the merge rule: emit termination, then a heartbeat; the
    snapshot's status still reads terminated."""
    writer = _make_writer(tmp_path)
    writer.backend_termination(
        phase="claude_invoke",
        attempt=1,
        backend="claude",
        reason="completed",
        duration_ms=500,
    )
    writer.claude_call_progress(
        phase="claude_invoke",
        attempt=1,
        elapsed_ms=600,
        silent_ms=0,
    )
    snapshot = read_in_flight(writer.in_flight_path)
    assert snapshot is not None
    assert snapshot["status"] == IN_FLIGHT_STATUS_TERMINATED
    assert snapshot["elapsed_ms"] == 600


def test_next_phase_start_returns_status_to_running(tmp_path: Path) -> None:
    writer = _make_writer(tmp_path)
    writer.backend_termination(
        phase="phase_a",
        attempt=1,
        backend="claude",
        reason="completed",
        duration_ms=500,
    )
    writer.phase_start("phase_b")
    snapshot = read_in_flight(writer.in_flight_path)
    assert snapshot is not None
    assert snapshot["status"] == IN_FLIGHT_STATUS_RUNNING
    assert snapshot["current_phase"] == "phase_b"


def test_refresh_swallows_snapshot_write_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With ``write_in_flight`` monkeypatched to raise ``OSError``,
    ``phase_start`` neither raises nor skips its JSONL append."""
    import plan_tool.run_log as run_log_module

    writer = _make_writer(tmp_path)

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(run_log_module, "write_in_flight", _raise)
    writer.phase_start("propose_steps")  # must not raise

    events = _read_events(writer.log_path)
    assert any(e["event"] == "phase_start" for e in events)


def test_distinct_slugs_keep_independent_snapshots(tmp_path: Path) -> None:
    writer_a = _make_writer(tmp_path, slug="alpha")
    writer_b = _make_writer(tmp_path, slug="beta")
    writer_a.phase_start("phase_a")
    writer_b.phase_start("phase_b")
    snapshot_a = read_in_flight(writer_a.in_flight_path)
    snapshot_b = read_in_flight(writer_b.in_flight_path)
    assert snapshot_a is not None
    assert snapshot_b is not None
    assert snapshot_a["current_phase"] == "phase_a"
    assert snapshot_b["current_phase"] == "phase_b"
    assert snapshot_a["run_id"] != snapshot_b["run_id"]


def test_run_end_skips_unlink_when_a_newer_run_owns_the_snapshot(
    tmp_path: Path,
) -> None:
    """Writer A starts, then writer B on the same slug starts (its
    ``start()`` overwrites the snapshot with B's ``run_id``); A's
    ``run_end()`` leaves the file in place, still carrying B's
    ``run_id``; B's own ``run_end()`` then removes it."""
    writer_a = _make_writer(tmp_path, slug="shared")
    writer_b = _make_writer(tmp_path, slug="shared")
    assert writer_a.in_flight_path == writer_b.in_flight_path
    assert writer_a.run_id != writer_b.run_id

    writer_a.run_end(outcome="ok", rc=0)
    snapshot = read_in_flight(writer_a.in_flight_path)
    assert snapshot is not None
    assert snapshot["run_id"] == writer_b.run_id

    writer_b.run_end(outcome="ok", rc=0)
    assert read_in_flight(writer_b.in_flight_path) is None


def test_refresh_does_not_reclaim_a_newer_same_slug_snapshot(tmp_path: Path) -> None:
    """A superseded writer leaves the newer run's liveness record intact."""
    writer_a = _make_writer(tmp_path, slug="shared")
    writer_b = _make_writer(tmp_path, slug="shared")

    writer_a.phase_start("stale-phase")

    snapshot = read_in_flight(writer_a.in_flight_path)
    assert snapshot is not None
    assert snapshot["run_id"] == writer_b.run_id
    writer_a.run_end(outcome="ok", rc=0)
    writer_b.run_end(outcome="ok", rc=0)


def test_run_end_serializes_new_snapshot_replacement_after_owner_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A start racing cleanup waits until the old owner has unlinked."""
    import plan_tool.run_log as run_log_module

    writer_a = _make_writer(tmp_path, slug="shared")
    original_unlink = Path.unlink
    original_write = run_log_module.write_in_flight
    unlink_entered = threading.Event()
    release_unlink = threading.Event()
    newer_write_entered = threading.Event()
    errors: list[BaseException] = []
    writers_b: list[RunLogWriter] = []

    def _paused_unlink(path: Path, *args: object, **kwargs: object) -> None:
        if path == writer_a.in_flight_path:
            unlink_entered.set()
            assert release_unlink.wait(timeout=2)
        original_unlink(path, *args, **kwargs)

    def _observed_write(path: Path, snapshot: dict[str, object]) -> None:
        if snapshot.get("run_id") != writer_a.run_id:
            newer_write_entered.set()
        original_write(path, snapshot)

    monkeypatch.setattr(Path, "unlink", _paused_unlink)
    monkeypatch.setattr(run_log_module, "write_in_flight", _observed_write)

    def _end_a() -> None:
        try:
            writer_a.run_end(outcome="ok", rc=0)
        except BaseException as exc:  # pragma: no cover - assertion aid.
            errors.append(exc)

    def _start_b() -> None:
        try:
            writers_b.append(_make_writer(tmp_path, slug="shared"))
        except BaseException as exc:  # pragma: no cover - assertion aid.
            errors.append(exc)

    end_thread = threading.Thread(target=_end_a)
    end_thread.start()
    assert unlink_entered.wait(timeout=2)

    start_thread = threading.Thread(target=_start_b)
    start_thread.start()
    assert not newer_write_entered.wait(timeout=0.1)
    release_unlink.set()
    end_thread.join(timeout=2)
    start_thread.join(timeout=2)

    assert not end_thread.is_alive()
    assert not start_thread.is_alive()
    assert not errors
    assert len(writers_b) == 1
    snapshot = read_in_flight(writer_a.in_flight_path)
    assert snapshot is not None
    assert snapshot["run_id"] == writers_b[0].run_id
    writers_b[0].run_end(outcome="ok", rc=0)


def test_run_end_still_unlinks_own_snapshot(tmp_path: Path) -> None:
    """The ordinary single-run case: ``run_end`` with the writer's own
    ``run_id`` on disk removes the file — the guard changes nothing
    for the common path."""
    writer = _make_writer(tmp_path)
    assert read_in_flight(writer.in_flight_path) is not None
    writer.run_end(outcome="ok", rc=0)
    assert read_in_flight(writer.in_flight_path) is None


class TestPruneStreamLogs:
    def _make(self, slug_dir, name, mtime):
        import os

        d = slug_dir / f"{name}.streams"
        d.mkdir(parents=True)
        f = d / "claude-stream.0001.p.a1.ndjson"
        f.write_text("{}\n")
        os.utime(f, (mtime, mtime))
        os.utime(d, (mtime, mtime))
        return d

    def test_removes_only_streams_dirs_older_than_the_cutoff(self, tmp_path):
        from plan_tool.run_log import prune_stream_logs

        old = self._make(tmp_path, "old", 1_000)
        new = self._make(tmp_path, "new", 9_000)
        run_log = tmp_path / "old.jsonl"
        run_log.write_text("{}\n")
        removed = prune_stream_logs(
            tmp_path, older_than_seconds=5_000, now=10_000
        )
        assert removed == [old]
        assert not old.exists()
        assert new.is_dir()
        # Deliberately not the run log: pruning touches stream dirs only.
        assert run_log.is_file()

    def test_none_cutoff_removes_every_streams_dir(self, tmp_path):
        from plan_tool.run_log import prune_stream_logs

        self._make(tmp_path, "a", 9_999)
        assert len(prune_stream_logs(tmp_path, older_than_seconds=None)) == 1

    def test_symlinked_streams_dir_is_not_followed(self, tmp_path):
        from plan_tool.run_log import prune_stream_logs

        target = tmp_path / "elsewhere"
        target.mkdir()
        (target / "keep").write_text("x")
        (tmp_path / "slug").mkdir()
        (tmp_path / "slug" / "r.streams").symlink_to(target)
        assert prune_stream_logs(
            tmp_path / "slug", older_than_seconds=None
        ) == []
        assert (target / "keep").is_file()


@pytest.mark.integration
class TestExistingCallLogging:
    @pytest.mark.parametrize("site", ["apply", "followup", "assessment", "risk", "intents", "gates"])
    def test_existing_logged_calls_retain_exact_prompt_identity_and_one_end(
        self, tmp_path: Path, site: str,
    ) -> None:
        from plan_tool import create, launcher, shell
        from plan_tool.progress import NullReporter
        from plan_tool.run_log import hash_prompt

        writer = _make_writer(tmp_path)
        prompts: list[str] = []
        previous_sink = shell.get_active_sink()
        if site in {"apply", "followup"}:
            plan_path = tmp_path / "plan.md"
            plan_path.write_text(
                "---\ntitle: Logging\nstatus: in-progress\npriority: low\n"
                "steps:\n  - id: 1\n    title: Build\n    files: [foo.py]\n"
                "    status: done\n---\n\n## Overview\nReal description.\n",
                encoding="utf-8",
            )
            (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")

            def streaming_invoker(prompt: str) -> tuple[int, str]:
                prompts.append(prompt)
                text = plan_path.read_text(encoding="utf-8")
                if site == "followup":
                    text = text.replace(
                        "## Overview\nReal description.\n", "## Overview\n_(TODO)_\n"
                    ) if len(prompts) == 1 else text.replace(
                        "## Overview\n_(TODO)_\n", "## Overview\nRestored description.\n"
                    )
                else:
                    text = text.replace("priority: low", "priority: medium")
                plan_path.write_text(text, encoding="utf-8")
                return 0, "## Summary\n- edited\n\n## Verdict\nAPPLIED\n"

            launcher.apply_finding(
                plan_path, repo_root=tmp_path, finding_body="Apply change", step_id=1,
                invoker=streaming_invoker, run_logger=writer, reporter=NullReporter(),
            )
        else:
            def batch_invoker(prompt: str) -> str:
                prompts.append(prompt)
                sink = shell.get_active_sink()
                if sink is not None:
                    sink(ClaudeCallEnd(ts="now", run_id="", tokens_input=17))
                return '{"outcome":"single"}' if site == "assessment" else "invalid"

            if site == "assessment":
                create.assess_direct_source_split_from_claude(
                    "One bounded effort.", batch_invoker, run_logger=writer,
                )
            elif site == "risk":
                _real_risk_classifier(
                    "One bounded effort.", batch_invoker, slug="demo",
                    predicted_plan_path=tmp_path / "plan.md", repo_root=tmp_path,
                    resume=False, allow_resume=False, run_logger=writer,
                )
            else:
                from plan_tool.gates import suggest_gates
                from plan_tool.intent_proposal import propose_intents
                from plan_tool.schema import Plan, Step

                plan = Plan(
                    title="Logging", status="in-progress", priority="low",
                    steps=[Step(id=1, title="Pending")],
                )
                if site == "intents":
                    propose_intents(
                        plan, invoker=batch_invoker, plan_needs_intent=True,
                        step_ids=[1], run_logger=writer,
                    )
                else:
                    suggest_gates(
                        plan, repo_root=tmp_path, invoker=batch_invoker,
                        all_steps=True, done_details={}, run_logger=writer,
                    )
        events = _read_events(writer.log_path)
        starts = [e for e in events if e["event"] == "claude_call_start"]
        ends = [e for e in events if e["event"] == "claude_call_end"]
        assert len(prompts) == (2 if site == "followup" else 1)
        assert len(starts) == len(ends) == len(prompts)
        assert [e["prompt_sha256"] for e in starts] == [hash_prompt(p) for p in prompts]
        assert [(e["phase"], e["attempt"]) for e in starts] == [
            (e["phase"], e["attempt"]) for e in ends
        ]
        assert shell.get_active_sink() is previous_sink
        assert all("prompt" not in e for e in starts)


    @pytest.mark.parametrize("site", ["intents", "gates"])
    def test_no_target_skips_do_not_record_phantom_calls(self, tmp_path: Path, site: str) -> None:
        from plan_tool.gates import suggest_gates
        from plan_tool.intent_proposal import propose_intents
        from plan_tool.schema import Plan, Step

        writer = _make_writer(tmp_path)
        plan = Plan(
            title="No targets", status="in-progress", priority="low",
            steps=[Step(id=1, title="Done", status="done")],
        )

        def forbidden_invoker(prompt: str) -> str:
            pytest.fail("No-target path must not invoke a backend")

        if site == "intents":
            result = propose_intents(
                plan, invoker=forbidden_invoker, plan_needs_intent=False,
                step_ids=[], run_logger=writer,
            )
        else:
            result = suggest_gates(
                plan, repo_root=tmp_path, invoker=forbidden_invoker, run_logger=writer,
            )
        assert result == []
        assert not any(e["event"].startswith("claude_call_") for e in _read_events(writer.log_path))


def test_prompt_hash_uses_exact_utf8_bytes_and_unknown_prompts_remain_null(
    tmp_path: Path,
) -> None:
    import hashlib
    from plan_tool.run_log import hash_prompt

    writer = _make_writer(tmp_path)
    prompt = "private café\n"
    digest = hash_prompt(prompt)
    assert digest == hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    assert digest != hash_prompt(prompt.rstrip())
    writer.claude_call_start("known", 1, len(prompt.encode("utf-8")), prompt_sha256=digest)
    writer.claude_call_start("unknown", 1, 0)
    events = _read_events(writer.log_path)
    starts = [e for e in events if e["event"] == "claude_call_start"]
    assert [e["prompt_sha256"] for e in starts] == [digest, None]
    assert prompt not in writer.log_path.read_text(encoding="utf-8")


def test_every_prompt_bearing_start_site_supplies_its_prompt_hash() -> None:
    """New prompt-bearing start sites must preserve exact-input observability."""
    import ast

    missing = []
    source_root = Path(__file__).resolve().parents[1] / "plan_tool"
    for path in source_root.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in {"claude_call_start", "start_step", "begin_seed_attempt"}:
                continue
            keywords = {kw.arg for kw in node.keywords}
            has_prompt_size = "prompt_bytes" in keywords or (
                node.func.attr == "claude_call_start" and len(node.args) >= 3
            )
            # A ``start_step`` without ``phase`` never reaches the run log
            # (the reporter writes the start only for a phased call), so a
            # hash there would be dead; review.py's audit loop hashes instead.
            reaches_log = node.func.attr != "start_step" or "phase" in keywords
            if has_prompt_size and reaches_log and "prompt_sha256" not in keywords:
                missing.append(f"{path.name}:{node.lineno}")
    assert missing == []


def test_sink_bearing_direct_invocations_cannot_omit_their_start_event() -> None:
    import ast

    missing = []
    source_root = Path(__file__).resolve().parents[1] / "plan_tool"
    for path in source_root.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            calls = [n for n in ast.walk(node) if isinstance(n, ast.Call)]
            methods = {n.func.attr for n in calls if isinstance(n.func, ast.Attribute)}
            invokes = any(
                isinstance(n.func, ast.Name) and n.func.id == "invoker" for n in calls
            )
            if invokes and methods & {"install_call_end_sink", "bind_shell_sink"}:
                if not methods & {"claude_call_start", "start_step", "begin_seed_attempt"}:
                    missing.append(f"{path.name}:{node.name}")
    assert missing == []


def _run_end_event(writer):
    return [e for e in _read_events(writer.log_path) if e["event"] == "run_end"]


def test_run_end_that_would_exceed_the_line_cap_still_lands_without_its_result(tmp_path: Path) -> None:
    """`run_end` is emitted from `finally`; an oversize event must shrink, never raise.

    Raising there would replace the command's own return code or exception. The
    full terminal fields survive, and the dropped `result` is flagged, not silent.
    """
    writer = _make_writer(tmp_path)
    # Multibyte error (3 bytes/char) plus a full-size result: > 4096 serialized bytes.
    big_result = {"detail_files_written": ["docs/" + "x" * 90 + f"{i}.md" for i in range(20)]}

    writer.run_end(outcome="error", rc=2, error="あ" * 1000, result=big_result)

    (end,) = _run_end_event(writer)
    assert end["outcome"] == "error" and end["rc"] == 2
    assert end["result_dropped"] is True and "result" not in end
    assert not writer.in_flight_path.exists()  # snapshot cleanup still ran


def test_run_end_within_the_cap_keeps_its_result_untouched(tmp_path: Path) -> None:
    """The carve-out: shrinking applies only to an oversize event."""
    writer = _make_writer(tmp_path)

    writer.run_end(outcome="ok", rc=0, result={"plan_path": "plans/1-demo.md"})

    (end,) = _run_end_event(writer)
    assert end["result"] == {"plan_path": "plans/1-demo.md"}
    assert "result_dropped" not in end

def _call_end(**usage):
    from plan_tool.run_log import ClaudeCallEnd

    return ClaudeCallEnd(
        ts="2026-05-14T12:00:00+00:00", run_id="", phase="p", attempt=1, rc=0,
        duration_ms=5, stdout_bytes=3, **usage,
    )


def _run_end_usage(writer) -> dict | None:
    writer.run_end(outcome="ok", rc=0)
    end = next(e for e in _read_events(writer.log_path) if e["event"] == "run_end")
    return end.get("usage")


def test_run_end_usage_equals_the_sum_of_claude_call_end_events(tmp_path: Path) -> None:
    from plan_tool import shell

    writer = _make_writer(tmp_path)
    with writer.bind_shell_sink(phase="p", attempt=1):
        sink = shell.get_active_sink()
        sink(_call_end(tokens_input=10, tokens_output=2, cache_creation_tokens=3,
                       cache_read_tokens=4, cost_usd=0.25))
        sink(_call_end(tokens_input=5, tokens_output=1, cache_creation_tokens=0,
                       cache_read_tokens=6, cost_usd=0.5))

    events = _read_events(writer.log_path)
    ends = [e for e in events if e["event"] == "claude_call_end"]
    usage = _run_end_usage(writer)

    assert usage["calls"] == len(ends) == 2
    for name in ("tokens_input", "tokens_output", "cache_creation_tokens", "cache_read_tokens", "cost_usd"):
        assert usage[name] == pytest.approx(sum(e[name] for e in ends)), name
    assert "estimate" in usage["cost_usd_basis"]


def test_run_end_usage_names_a_partial_field_instead_of_showing_it_complete(tmp_path: Path) -> None:
    """A field only some calls reported is a lower bound named in `partial_fields`.

    A field every call reported is complete (not listed); a field no call
    reported is null. A retried or failed call (no usage) must not erase the rest.
    """
    from plan_tool import shell

    writer = _make_writer(tmp_path)
    with writer.bind_shell_sink(phase="p", attempt=1):
        sink = shell.get_active_sink()
        sink(_call_end(tokens_input=10, tokens_output=2, cost_usd=0.25))
        sink(_call_end(tokens_input=5, tokens_output=1, cost_usd=None))

    usage = _run_end_usage(writer)

    assert usage["tokens_input"] == 15 and "tokens_input" not in usage["partial_fields"]
    assert usage["cost_usd"] == 0.25 and usage["partial_fields"] == ["cost_usd"]
    assert usage["cache_read_tokens"] is None  # no call reported it


def test_run_end_usage_counts_call_ends_emitted_straight_through_the_writer(tmp_path: Path) -> None:
    """Roadmap materialization writes `claude_call_end` via `_emit`, not the shell sink."""
    writer = _make_writer(tmp_path)
    writer._emit(_call_end(tokens_input=7, cost_usd=0.5))

    usage = _run_end_usage(writer)

    assert usage["calls"] == 1 and usage["tokens_input"] == 7 and usage["cost_usd"] == 0.5


def test_run_end_usage_counts_a_call_whose_log_write_failed(tmp_path: Path, monkeypatch) -> None:
    from plan_tool import run_log, shell

    writer = _make_writer(tmp_path)
    real = run_log._append_jsonl_line

    def failing(path, payload):
        if payload.get("event") == "claude_call_end":
            raise OSError("disk full")
        return real(path, payload)

    monkeypatch.setattr(run_log, "_append_jsonl_line", failing)
    with writer.bind_shell_sink(phase="p", attempt=1):
        with pytest.raises(OSError):
            shell.get_active_sink()(_call_end(tokens_input=3))

    assert _run_end_usage(writer)["tokens_input"] == 3


def test_run_end_omits_usage_when_the_run_made_no_backend_call(tmp_path: Path) -> None:
    """Runs with no backend call (`jira`, `annotate`, ...) keep today's exact run_end shape."""
    assert _run_end_usage(_make_writer(tmp_path)) is None


def test_run_end_usage_counts_calls_from_concurrent_workers(tmp_path: Path) -> None:
    import threading

    from plan_tool import shell

    writer = _make_writer(tmp_path)
    with writer.bind_shell_sink(phase="p", attempt=1):
        sink = shell.get_active_sink()
        threads = [
            threading.Thread(target=lambda: [sink(_call_end(tokens_input=1)) for _ in range(50)])
            for _ in range(8)
        ]
        [t.start() for t in threads]
        [t.join() for t in threads]

    usage = _run_end_usage(writer)
    assert usage["calls"] == 400
    assert usage["tokens_input"] == 400
