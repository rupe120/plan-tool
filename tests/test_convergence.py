"""Tests for plan_tool.convergence.

Pure in-memory tests. No I/O, no claude shell-out -- the module is a
pure-logic primitive. Callers in steps 2/3/4 (create.py, detail.py,
cli.cmd_run) own their own integration tests with injected invokers.
"""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path

import pytest

from plan_tool.convergence import (
    DEFAULT_ITERATION_BUDGET_SECONDS,
    DEFAULT_MAX_ITERATIONS,
    MARGINAL_OVERLAP_THRESHOLD,
    ConvergenceState,
    IterativeBudget,
    STAGE_BARE,
    STAGE_DETAIL,
    finding_set_delta,
    is_blocking,
    is_blocking_finding,
    is_blocking_impact,
    is_marginal,
    larger_iteration_budget_seconds,
    record_iteration,
    should_continue,
    touch,
)
from plan_tool.review import Recommendation, classify_finding_domain
from tests.test_review import (
    docs_detail_body_fixture,
    merge_bridge_reauthor_context_fixture,
)


def _recommendation(severity: str, impact: str | None = None) -> Recommendation:
    return Recommendation(
        id="finding-1",
        source="claude",
        severity=severity,
        step_id=None,
        title="Test finding",
        body="Test recommendation body.",
        impact=impact,
    )


def _conceptual_recommendation(
    *,
    source: str,
    severity: str,
    rec_id: str = "conceptual-1",
) -> Recommendation:
    return Recommendation(
        id=rec_id,
        source=source,
        severity=severity,
        step_id=None,
        title="Conceptual finding",
        body="Conceptual finding body.",
    )


def _state(
    *,
    iteration: int = 0,
    previous: tuple[str, ...] = (),
    current: tuple[str, ...] = (),
    budget: IterativeBudget | None = None,
    started_at: float = 0.0,
    last_activity_at: float | None = None,
) -> ConvergenceState:
    s = ConvergenceState(budget=budget or IterativeBudget())
    s.iteration = iteration
    s.previous_finding_ids = frozenset(previous)
    s.current_finding_ids = frozenset(current)
    s.started_at = started_at
    # Default last_activity_at mirrors started_at so existing tests
    # that only set started_at keep working under the debounced
    # deadline semantics.
    s.last_activity_at = (
        started_at if last_activity_at is None else last_activity_at
    )
    return s


# ---------- IterativeBudget construction ----------

def test_default_budget_uses_module_constants() -> None:
    b = IterativeBudget()
    assert b.max_iterations == DEFAULT_MAX_ITERATIONS
    assert b.budget_seconds == DEFAULT_ITERATION_BUDGET_SECONDS
    assert b.enabled is True


def test_every_stop_reason_should_continue_returns_is_documented() -> None:
    """``docs/ITERATION.md`` § "How the loop terminates" is the operator's only
    key to the reason code on the final stderr line, so a stop added to
    ``should_continue`` without a bullet there leaves an unexplained code."""
    import inspect

    from plan_tool import convergence

    returned = set(
        re.findall(
            r'return (?:True|False), "(\w+)"',
            inspect.getsource(convergence.should_continue),
        )
    ) - {"continue"}
    doc = (Path(__file__).resolve().parent.parent / "docs" / "ITERATION.md").read_text(
        encoding="utf-8"
    )
    section = doc.split("## How the loop terminates", 1)[1].split("\n## ", 1)[0]
    assert returned, "reason-code extraction found nothing; update this test"
    assert sorted(code for code in returned if f"`{code}`" not in section) == []


@pytest.mark.parametrize("effective", [0, 1, 600, 900, 1800, 5000])
def test_resume_hint_budget_always_exceeds_the_deadline_that_expired(
    effective: int,
) -> None:
    """A hint that repeats the expired value, or the default, would change
    nothing on resume: the printed value must be strictly larger."""
    assert larger_iteration_budget_seconds(effective) > effective


def test_resume_hint_budget_floors_at_the_default_and_otherwise_doubles() -> None:
    assert larger_iteration_budget_seconds(0) == DEFAULT_ITERATION_BUDGET_SECONDS
    assert larger_iteration_budget_seconds(1800) == 3600


def test_budget_rejects_negative_max_iterations() -> None:
    with pytest.raises(ValueError):
        IterativeBudget(max_iterations=-1)


def test_budget_rejects_negative_budget_seconds() -> None:
    with pytest.raises(ValueError):
        IterativeBudget(budget_seconds=-1)


def test_budget_rejects_negative_hard_budget_seconds() -> None:
    with pytest.raises(ValueError):
        IterativeBudget(hard_budget_seconds=-1)


def test_budget_hard_budget_defaults_off() -> None:
    assert IterativeBudget().hard_budget_seconds == 0


def test_budget_accepts_zero_max_iterations() -> None:
    b = IterativeBudget(max_iterations=0)
    assert b.max_iterations == 0


def test_budget_is_frozen() -> None:
    b = IterativeBudget()
    with pytest.raises(dataclasses.FrozenInstanceError):
        b.max_iterations = 5  # type: ignore[misc]


# ---------- finding_set_delta ----------


def test_nit_and_info_are_non_blocking_under_current_rule() -> None:
    """The severity-only continuation rule leaves advisory findings open."""
    assert is_blocking("nit") is False
    assert is_blocking("info") is False


def test_high_impact_nit_blocks() -> None:
    assert is_blocking_impact(_recommendation("nit", "high")) is True


def test_high_impact_info_blocks() -> None:
    assert is_blocking_impact(_recommendation("info", "high")) is True


@pytest.mark.parametrize("severity", ["nit", "info", "medium", "high", "critical"])
def test_is_blocking_impact_preserves_current_augment(severity: str) -> None:
    """High impact augments, but never replaces, severity blocking."""
    assert is_blocking_impact(_recommendation(severity, "high")) is True
    assert is_blocking_impact(_recommendation(severity, "low")) is is_blocking(
        severity
    )


@pytest.mark.parametrize(
    ("severity", "impact"),
    [
        ("medium", None),  # Parser-normalized LOW control case.
        ("medium", "low"),
        ("medium", "medium"),
        ("high", None),
        ("high", "low"),
        ("high", "medium"),
        ("critical", None),
        ("critical", "low"),
        ("critical", "medium"),
    ],
)
def test_medium_or_higher_severity_remains_blocking(
    severity: str, impact: str | None
) -> None:
    assert is_blocking_impact(_recommendation(severity, impact)) is True


@pytest.mark.parametrize("severity", ["nit", "info", "medium", "high", "critical"])
def test_missing_impact_falls_back_to_severity_rule(severity: str) -> None:
    rec = _recommendation(severity)
    assert is_blocking_impact(rec) is is_blocking(rec.severity)


@pytest.mark.parametrize("severity", ["nit", "info"])
@pytest.mark.parametrize("impact", [None, "low", "medium"])
def test_low_and_medium_impact_do_not_promote_advisories(
    severity: str, impact: str | None
) -> None:
    assert is_blocking_impact(_recommendation(severity, impact)) is False


def test_demotion_callback_can_demote_low_impact_medium_block() -> None:
    rec = _recommendation("medium", "low")
    callback_calls: list[Recommendation] = []

    def demote_low_impact_medium(candidate: Recommendation) -> bool:
        callback_calls.append(candidate)
        return True

    assert (
        is_blocking_impact(
            rec, demote_low_impact_medium=demote_low_impact_medium
        )
        is False
    )
    assert callback_calls == [rec]


@pytest.mark.parametrize(
    ("severity", "impact"),
    [
        ("medium", None),
        ("medium", "medium"),
        ("medium", "high"),
        ("high", "low"),
        ("critical", "low"),
        ("nit", "low"),
        ("info", "low"),
    ],
)
def test_demotion_callback_cannot_override_fixed_outcomes(
    severity: str, impact: str | None
) -> None:
    callback_calls: list[Recommendation] = []

    def always_demote(candidate: Recommendation) -> bool:
        callback_calls.append(candidate)
        return True

    rec = _recommendation(severity, impact)
    assert is_blocking_impact(rec, demote_low_impact_medium=always_demote) is (
        rec.impact == "high" or is_blocking(rec.severity)
    )
    assert callback_calls == []


# ---------- is_blocking_impact classify_domain (docs exemption) ----------


def test_impact_docs_domain_medium_conceptual_non_blocking() -> None:
    rec = _conceptual_recommendation(source="plan-completeness", severity="medium")
    assert (
        is_blocking_impact(rec, classify_domain=lambda _: "docs") is False
    )


def test_impact_unknown_domain_medium_conceptual_stays_material() -> None:
    rec = _conceptual_recommendation(source="plan-correctness", severity="medium")
    assert is_blocking_impact(rec, classify_domain=lambda _: "unknown") is True


def test_impact_non_conceptual_never_invokes_classify_domain() -> None:
    rec = _recommendation("medium")

    def _raise(_: Recommendation) -> str:
        raise AssertionError("classify_domain must not run for non-conceptual")

    assert is_blocking_impact(rec, classify_domain=_raise) is True


def test_impact_high_severity_docs_domain_still_blocks() -> None:
    rec = _conceptual_recommendation(source="plan-correctness", severity="high")
    assert is_blocking_impact(rec, classify_domain=lambda _: "docs") is True


def test_impact_high_impact_docs_domain_still_blocks() -> None:
    rec = _conceptual_recommendation(source="plan-completeness", severity="medium")
    rec = dataclasses.replace(rec, impact="high")
    assert is_blocking_impact(rec, classify_domain=lambda _: "docs") is True


def test_impact_missing_classify_domain_skips_docs_exemption() -> None:
    rec = _conceptual_recommendation(source="plan-completeness", severity="medium")
    assert is_blocking_impact(rec) is True


def test_delta_returns_three_sets() -> None:
    introduced, resolved, persisted = finding_set_delta({"a"}, {"b"})
    assert introduced == frozenset({"b"})
    assert resolved == frozenset({"a"})
    assert persisted == frozenset()


def test_delta_handles_empty_previous() -> None:
    introduced, resolved, persisted = finding_set_delta((), ("a", "b"))
    assert introduced == frozenset({"a", "b"})
    assert resolved == frozenset()
    assert persisted == frozenset()


def test_delta_handles_empty_current() -> None:
    introduced, resolved, persisted = finding_set_delta(("a", "b"), ())
    assert introduced == frozenset()
    assert resolved == frozenset({"a", "b"})
    assert persisted == frozenset()


def test_delta_persisted_is_intersection() -> None:
    _, _, persisted = finding_set_delta(("a", "b", "c"), ("b", "c", "d"))
    assert persisted == frozenset({"b", "c"})


def test_delta_inputs_can_be_any_iterable() -> None:
    from_gen = finding_set_delta((x for x in ["a", "b"]), (x for x in ["b", "c"]))
    from_list = finding_set_delta(["a", "b"], ["b", "c"])
    from_tuple = finding_set_delta(("a", "b"), ("b", "c"))
    assert from_gen == from_list == from_tuple


# ---------- is_marginal ----------

def test_marginal_false_when_current_empty() -> None:
    state = _state(previous=("a", "b"), current=())
    assert is_marginal(state) is False


def test_marginal_false_when_previous_empty() -> None:
    state = _state(previous=(), current=("a", "b"))
    assert is_marginal(state) is False


def test_marginal_true_when_full_overlap() -> None:
    state = _state(previous=("a", "b"), current=("a", "b"))
    assert is_marginal(state) is True


def test_marginal_false_below_threshold() -> None:
    state = _state(previous=("a", "b", "c", "d"), current=("a", "e", "f", "g"))
    assert is_marginal(state) is False


def test_marginal_true_at_threshold() -> None:
    state = _state(previous=("a", "b"), current=("a", "x"))
    assert is_marginal(state) is True


def test_marginal_honors_threshold_override() -> None:
    state = _state(previous=("a", "b"), current=("a", "x"))
    assert is_marginal(state, threshold=0.9) is False


def test_marginal_threshold_constant_is_half() -> None:
    assert MARGINAL_OVERLAP_THRESHOLD == 0.5


# ---------- should_continue ----------

def test_disabled_budget_returns_disabled_reason() -> None:
    state = _state(budget=IterativeBudget(enabled=False))
    cont, reason = should_continue(state)
    assert cont is False
    assert reason == "disabled"


def test_max_iterations_reached_stops() -> None:
    # Use the constant so future retuning doesn't false-fail this
    # test (originally hardcoded `iteration=3` against the legacy
    # default; bumped to use the live constant after #20 retune).
    state = _state(iteration=DEFAULT_MAX_ITERATIONS, current=("still-open",))
    cont, reason = should_continue(state)
    assert cont is False
    assert reason == "max_iterations"


def test_deadline_exceeded_stops() -> None:
    state = _state(iteration=1, current=("a",), started_at=0.0)
    cont, reason = should_continue(
        state, now_fn=lambda: DEFAULT_ITERATION_BUDGET_SECONDS + 1.0
    )
    assert cont is False
    assert reason == "deadline_exceeded"


# ---------- cooperative hard wall-clock cap (#123) ----------

def test_time_budget_exceeded_stops_a_progressing_loop() -> None:
    # A loop still making progress (disjoint prev/current -> not marginal)
    # is stopped once the hard cap elapses.
    state = _state(
        iteration=1,
        previous=("a",),
        current=("b", "c"),
        budget=IterativeBudget(hard_budget_seconds=60),
        started_at=0.0,
    )
    cont, reason = should_continue(state, now_fn=lambda: 120.0)
    assert cont is False
    assert reason == "time_budget_exceeded"


def test_time_budget_zero_disables_cap() -> None:
    # Default hard_budget_seconds=0: no clock consulted for the hard cap,
    # so a progressing loop keeps going even at a huge wall-clock.
    state = _state(
        iteration=1,
        previous=("a",),
        current=("b", "c"),
        started_at=0.0,
        last_activity_at=99_999.0,  # keep the debounced deadline from firing
    )
    cont, reason = should_continue(state, now_fn=lambda: 99_999.0)
    assert cont is True
    assert reason == "continue"


def test_time_budget_not_exceeded_continues() -> None:
    state = _state(
        iteration=1,
        previous=("a",),
        current=("b", "c"),
        budget=IterativeBudget(hard_budget_seconds=300),
        started_at=0.0,
    )
    cont, reason = should_continue(state, now_fn=lambda: 120.0)
    assert cont is True
    assert reason == "continue"


def test_time_budget_anchored_on_started_at_not_debounced() -> None:
    # The hard cap must NOT reset on activity: a freshly-touched
    # last_activity_at still trips the cap because it is anchored on
    # started_at (the key difference from the debounced deadline).
    state = _state(
        iteration=1,
        previous=("a",),
        current=("b", "c"),
        budget=IterativeBudget(hard_budget_seconds=60),
        started_at=0.0,
        last_activity_at=119.0,  # just touched
    )
    cont, reason = should_continue(state, now_fn=lambda: 120.0)
    assert cont is False
    assert reason == "time_budget_exceeded"


def test_time_budget_uses_op_anchor_over_per_loop_started_at() -> None:
    # op_started_at (the op-level anchor) trips the cap even though this
    # per-loop state's own started_at is recent — proving a multi-step op
    # measures TOTAL elapsed, not just this loop's. (detail rebuilds a
    # ConvergenceState per step; the cap must not reset with it.)
    state = _state(
        iteration=1,
        previous=("a",),
        current=("b", "c"),
        budget=IterativeBudget(hard_budget_seconds=60, op_started_at=0.0),
        started_at=115.0,          # per-loop anchor: only 5s elapsed
        last_activity_at=115.0,
    )
    cont, reason = should_continue(state, now_fn=lambda: 120.0)
    assert cont is False
    assert reason == "time_budget_exceeded"


def test_time_budget_op_anchor_absent_falls_back_to_started_at() -> None:
    # op_started_at None -> anchor on the per-loop started_at; a recent
    # started_at means the cap has NOT elapsed for this loop.
    state = _state(
        iteration=1,
        previous=("a",),
        current=("b", "c"),
        budget=IterativeBudget(hard_budget_seconds=60, op_started_at=None),
        started_at=115.0,
        last_activity_at=115.0,
    )
    cont, reason = should_continue(state, now_fn=lambda: 120.0)
    assert cont is True
    assert reason == "continue"


def test_natural_converged_outranks_time_budget() -> None:
    # A clean final scan reports "converged", not the hard cap, even when
    # the wall-clock is past budget.
    state = _state(
        iteration=1,
        previous=("a",),
        current=(),
        budget=IterativeBudget(hard_budget_seconds=60),
        started_at=0.0,
    )
    cont, reason = should_continue(state, now_fn=lambda: 120.0)
    assert cont is False
    assert reason == "converged"


def test_max_iterations_outranks_time_budget() -> None:
    state = _state(
        iteration=DEFAULT_MAX_ITERATIONS,
        current=("still-open",),
        budget=IterativeBudget(hard_budget_seconds=60),
        started_at=0.0,
    )
    cont, reason = should_continue(state, now_fn=lambda: 120.0)
    assert cont is False
    assert reason == "max_iterations"


def test_converged_when_current_empty_after_first_iteration() -> None:
    state = _state(iteration=1, previous=("a", "b"), current=())
    cont, reason = should_continue(state, now_fn=lambda: 0.0)
    assert cont is False
    assert reason == "converged"


def test_converged_outranks_max_iterations_when_final_scan_clean() -> None:
    state = _state(
        iteration=1,
        previous=("a",),
        current=(),
        budget=IterativeBudget(max_iterations=1),
    )
    cont, reason = should_continue(state, now_fn=lambda: 0.0)
    assert cont is False
    assert reason == "converged"


def test_marginal_stop_after_first_iteration() -> None:
    state = _state(iteration=1, previous=("a", "b"), current=("a", "b"))
    cont, reason = should_continue(state, now_fn=lambda: 0.0)
    assert cont is False
    assert reason == "marginal"


def test_should_continue_returns_continue_otherwise() -> None:
    state = _state(iteration=1, previous=("a",), current=("b", "c", "d"))
    cont, reason = should_continue(state, now_fn=lambda: 0.0)
    assert cont is True
    assert reason == "continue"


# ---------- no_progress (net-progress stall) ----------

def test_no_progress_stop_after_stall_threshold() -> None:
    """When the open-finding count fails to shrink for
    ``max_stall_rounds`` consecutive rounds, the loop stops with
    ``no_progress`` even though the IDs churn (so marginal/converged
    never fire). Models the body-hash treadmill: each round resolves N
    and introduces N fresh ids, count steady."""
    budget = IterativeBudget(max_iterations=10, max_stall_rounds=2)
    state = ConvergenceState(budget=budget)
    # Round 1 (seed): empty -> {a,b}. Seed roll never charges stall.
    record_iteration(state, ("a", "b"))
    assert state.stall_rounds == 0
    cont, _ = should_continue(state, now_fn=lambda: 0.0)
    assert cont is True
    # Round 2: {a,b} -> {c,d} (count steady, fully churned ids). Stall=1.
    record_iteration(state, ("c", "d"))
    assert state.stall_rounds == 1
    cont, _ = should_continue(state, now_fn=lambda: 0.0)
    assert cont is True
    # Round 3: {c,d} -> {e,f} (still no net progress). Stall=2 -> stop.
    record_iteration(state, ("e", "f"))
    assert state.stall_rounds == 2
    cont, reason = should_continue(state, now_fn=lambda: 0.0)
    assert cont is False
    assert reason == "no_progress"


def test_net_progress_resets_stall_streak() -> None:
    """A round that strictly shrinks the open set resets the stall
    counter, so genuine forward progress keeps the loop alive."""
    budget = IterativeBudget(max_iterations=10, max_stall_rounds=2)
    state = ConvergenceState(budget=budget)
    record_iteration(state, ("a", "b", "c"))  # seed
    record_iteration(state, ("d", "e", "f"))  # steady count -> stall=1
    assert state.stall_rounds == 1
    # Shrink 3->2 with fresh ids: resets stall AND avoids marginal
    # (no overlap with the prior set), so the loop genuinely continues.
    record_iteration(state, ("g", "h"))
    assert state.stall_rounds == 0
    cont, reason = should_continue(state, now_fn=lambda: 0.0)
    assert cont is True
    assert reason == "continue"


def test_max_stall_rounds_zero_disables_no_progress_stop() -> None:
    """``max_stall_rounds=0`` is the legacy kill-switch: the
    ``no_progress`` stop never fires no matter how long the count
    stalls."""
    budget = IterativeBudget(max_iterations=10, max_stall_rounds=0)
    state = ConvergenceState(budget=budget)
    record_iteration(state, ("a", "b"))
    for ids in (("c", "d"), ("e", "f"), ("g", "h"), ("i", "j")):
        record_iteration(state, ids)
        cont, reason = should_continue(state, now_fn=lambda: 0.0)
        assert cont is True
        assert reason == "continue"


def test_budget_rejects_negative_max_stall_rounds() -> None:
    with pytest.raises(ValueError):
        IterativeBudget(max_stall_rounds=-1)


def test_seed_roll_does_not_charge_stall() -> None:
    """The first record_iteration (previous set still empty) must not
    count as a stall, or every loop would start pre-charged."""
    state = ConvergenceState(budget=IterativeBudget(max_stall_rounds=2))
    record_iteration(state, ("a", "b", "c"))
    assert state.stall_rounds == 0


def test_converged_round_resets_stall() -> None:
    """Reaching an empty current set resets the stall streak (and
    ``should_continue`` reports ``converged``, which outranks
    ``no_progress``)."""
    budget = IterativeBudget(max_iterations=10, max_stall_rounds=2)
    state = ConvergenceState(budget=budget)
    record_iteration(state, ("a", "b"))  # seed
    record_iteration(state, ("c", "d"))  # stall=1
    assert state.stall_rounds == 1
    record_iteration(state, ())  # converged -> reset
    assert state.stall_rounds == 0
    cont, reason = should_continue(state, now_fn=lambda: 0.0)
    assert cont is False
    assert reason == "converged"


def test_first_iteration_with_open_findings_continues() -> None:
    state = _state(iteration=0, current=("a", "b"))
    cont, reason = should_continue(state, now_fn=lambda: 0.0)
    assert cont is True
    assert reason == "continue"


def test_deadline_debounced_by_record_iteration() -> None:
    """A long iteration that ends with record_iteration shouldn't trip
    the deadline at the top of the next round, because record_iteration
    refreshes last_activity_at."""
    # iteration=0, previous=current=()  → first iteration with brand-new
    # findings, neither converged nor marginal nor at max_iterations.
    state = _state(
        iteration=0, current=(), started_at=0.0, last_activity_at=0.0
    )
    record_iteration(state, ("a", "b", "c"))  # bumps last_activity_at
    # last_activity_at is now ~time.monotonic(), not 0.
    assert state.last_activity_at > 0.0
    # 1 s later: well within the default 300s budget.
    cont, reason = should_continue(
        state, now_fn=lambda: state.last_activity_at + 1.0
    )
    assert cont is True
    assert reason == "continue"


def test_touch_refreshes_last_activity_at() -> None:
    """``touch`` resets the debounce timer so the deadline doesn't fire
    when callers actively report progress between iterations."""
    state = _state(
        iteration=1, current=("a",), started_at=0.0, last_activity_at=0.0
    )
    # 1000s elapsed since last_activity_at → would normally fire.
    # Caller touches state to report progress.
    touch(state, now_fn=lambda: 1000.0)
    assert state.last_activity_at == 1000.0
    # Next should_continue check 50s later → still within budget.
    cont, reason = should_continue(state, now_fn=lambda: 1050.0)
    assert cont is True
    assert reason == "continue"


def test_no_blocking_findings_stops_after_first_iteration() -> None:
    """When current_finding_ids is non-empty but every finding is
    nit/info, the loop should stop with reason="no_blocking_findings"
    rather than churning on advisory findings."""
    state = _state(iteration=1, current=("nit-1", "info-2"))
    state.has_blocking_findings = False
    cont, reason = should_continue(state, now_fn=lambda: 0.0)
    assert cont is False
    assert reason == "no_blocking_findings"


def test_blocking_findings_keep_loop_running() -> None:
    """When has_blocking_findings is True, the loop continues
    regardless of severity content (the flag is the only gate the
    convergence module knows about — severity classification is the
    caller's responsibility)."""
    state = _state(
        iteration=1, previous=("a",), current=("b",)
    )
    state.has_blocking_findings = True
    cont, reason = should_continue(state, now_fn=lambda: 0.0)
    assert cont is True
    assert reason == "continue"


def test_no_blocking_findings_skipped_on_first_iteration() -> None:
    """On iteration 0, has_blocking_findings=False does NOT exit
    early — a round-0 plan with only advisory findings still gets
    one apply pass."""
    state = _state(iteration=0, current=("nit-1",))
    state.has_blocking_findings = False
    cont, reason = should_continue(state, now_fn=lambda: 0.0)
    assert cont is True
    assert reason == "continue"


def test_deadline_still_fires_when_idle_since_last_activity() -> None:
    """If no record_iteration / touch happens for budget_seconds, the
    deadline still fires. The debounce only resets on explicit
    activity signals."""
    state = _state(
        iteration=1, current=("a",), started_at=0.0, last_activity_at=100.0
    )
    # 1s past the default no-progress budget, measured from
    # last_activity_at (not started_at) -> fires.
    cont, reason = should_continue(
        state, now_fn=lambda: 100.0 + DEFAULT_ITERATION_BUDGET_SECONDS + 1.0
    )
    assert cont is False
    assert reason == "deadline_exceeded"


# ---------- record_iteration ----------

def test_record_advances_iteration_counter() -> None:
    state = _state(iteration=0)
    record_iteration(state, ("a",))
    assert state.iteration == 1


def test_record_rolls_current_into_previous() -> None:
    state = _state(current=("a", "b"))
    record_iteration(state, ("c",))
    assert state.previous_finding_ids == frozenset({"a", "b"})
    assert state.current_finding_ids == frozenset({"c"})


# ---------- is_blocking_finding ----------


class TestIsBlockingFindingBare:
    def test_bare_medium_plan_correctness_blocks(self) -> None:
        rec = _conceptual_recommendation(
            source="plan-correctness", severity="medium"
        )
        assert is_blocking_finding(rec, stage=STAGE_BARE) is True

    def test_bare_medium_plan_completeness_non_blocking(self) -> None:
        rec = _conceptual_recommendation(
            source="plan-completeness", severity="medium"
        )
        assert is_blocking_finding(rec, stage=STAGE_BARE) is False

    @pytest.mark.parametrize("severity", ["high", "critical"])
    def test_bare_high_or_critical_completeness_blocks(self, severity: str) -> None:
        rec = _conceptual_recommendation(
            source="plan-completeness", severity=severity
        )
        assert is_blocking_finding(rec, stage=STAGE_BARE) is True

    def test_bare_low_correctness_non_blocking(self) -> None:
        # Parser folds LOW to medium in production; "low" is the lowest
        # non-blocking severity the schema still allows for this pin.
        rec = _conceptual_recommendation(
            source="plan-correctness", severity="low"
        )
        assert is_blocking_finding(rec, stage=STAGE_BARE) is False

    @pytest.mark.parametrize(
        ("source", "severity"),
        [
            ("plan-correctness", "nit"),
            ("plan-correctness", "info"),
            ("plan-completeness", "nit"),
            ("plan-completeness", "info"),
        ],
    )
    def test_bare_nit_info_conceptual_never_block(
        self, source: str, severity: str
    ) -> None:
        rec = _conceptual_recommendation(source=source, severity=severity)
        assert is_blocking_finding(rec, stage=STAGE_BARE) is False

    def test_bare_non_conceptual_uses_severity_only(self) -> None:
        rec = Recommendation(
            id="data-contract-1",
            source="data-contract",
            severity="medium",
            step_id=None,
            title="Contract drift",
            body="Missing anchor.",
        )
        assert is_blocking_finding(rec, stage=STAGE_BARE) is True

    def test_bare_plan_completeness_never_invokes_classify_domain(self) -> None:
        rec = _conceptual_recommendation(
            source="plan-completeness", severity="medium"
        )

        def _raise(_: Recommendation) -> str:
            raise AssertionError(
                "classify_domain must not run for bare-stage plan-completeness"
            )

        assert (
            is_blocking_finding(
                rec,
                stage=STAGE_BARE,
                classify_domain=_raise,
            )
            is False
        )

    def test_bare_medium_docs_domain_non_blocking(self) -> None:
        rec = _conceptual_recommendation(
            source="plan-correctness", severity="medium"
        )
        assert (
            is_blocking_finding(
                rec, stage=STAGE_BARE, classify_domain=lambda _: "docs"
            )
            is False
        )

    @pytest.mark.parametrize("domain", ["code-logic", "unit-test", "unknown"])
    def test_bare_medium_non_docs_domain_blocks(self, domain: str) -> None:
        rec = _conceptual_recommendation(
            source="plan-correctness", severity="medium"
        )
        assert (
            is_blocking_finding(
                rec, stage=STAGE_BARE, classify_domain=lambda _: domain
            )
            is True
        )


def test_is_blocking_finding_rejects_invalid_stage() -> None:
    rec = _conceptual_recommendation(source="plan-correctness", severity="medium")
    with pytest.raises(ValueError, match="invalid stage"):
        is_blocking_finding(rec, stage="bogus")


class TestIsBlockingFindingDetail:
    @pytest.mark.parametrize(
        ("source", "severity"),
        [
            ("plan-correctness", "high"),
            ("plan-correctness", "critical"),
            ("plan-completeness", "high"),
            ("plan-completeness", "critical"),
        ],
    )
    def test_detail_high_critical_conceptual_always_blocks(
        self, source: str, severity: str
    ) -> None:
        rec = _conceptual_recommendation(source=source, severity=severity)
        assert is_blocking_finding(rec, stage=STAGE_DETAIL) is True

    @pytest.mark.parametrize(
        ("source", "severity"),
        [
            ("plan-correctness", "nit"),
            ("plan-correctness", "info"),
            ("plan-completeness", "nit"),
            ("plan-completeness", "info"),
        ],
    )
    def test_detail_nit_info_conceptual_never_blocks(
        self, source: str, severity: str
    ) -> None:
        rec = _conceptual_recommendation(source=source, severity=severity)
        assert is_blocking_finding(rec, stage=STAGE_DETAIL) is False

    def test_detail_low_never_blocks_even_when_domain_would(self) -> None:
        # "low" is below the general medium+ floor and must not fall through
        # to the domain check the way "medium" does.
        rec = _conceptual_recommendation(
            source="plan-correctness", severity="low"
        )
        assert (
            is_blocking_finding(
                rec,
                stage=STAGE_DETAIL,
                classify_domain=lambda _: "code-logic",
            )
            is False
        )

    def test_detail_medium_code_logic_blocks(self) -> None:
        rec = _conceptual_recommendation(
            source="plan-correctness", severity="medium"
        )
        assert (
            is_blocking_finding(
                rec,
                stage=STAGE_DETAIL,
                classify_domain=lambda _: "code-logic",
            )
            is True
        )

    def test_detail_medium_docs_advisory(self) -> None:
        rec = _conceptual_recommendation(
            source="plan-completeness", severity="medium"
        )
        assert (
            is_blocking_finding(
                rec,
                stage=STAGE_DETAIL,
                classify_domain=lambda _: "docs",
            )
            is False
        )

    def test_detail_medium_unit_test_blocks(self) -> None:
        # unit-test is application logic, not supporting information --
        # only "docs" demotes.
        rec = _conceptual_recommendation(
            source="plan-completeness", severity="medium"
        )
        assert (
            is_blocking_finding(
                rec,
                stage=STAGE_DETAIL,
                classify_domain=lambda _: "unit-test",
            )
            is True
        )

    def test_detail_medium_unknown_blocks(self) -> None:
        rec = _conceptual_recommendation(
            source="plan-correctness", severity="medium"
        )
        assert (
            is_blocking_finding(
                rec,
                stage=STAGE_DETAIL,
                classify_domain=lambda _: "unknown",
            )
            is True
        )

    def test_detail_missing_callback_treats_medium_as_unknown(self) -> None:
        rec = _conceptual_recommendation(
            source="plan-completeness", severity="medium"
        )
        assert is_blocking_finding(rec, stage=STAGE_DETAIL) is True

    def test_detail_non_conceptual_skips_domain(self) -> None:
        rec = Recommendation(
            id="data-contract-1",
            source="data-contract",
            severity="medium",
            step_id=None,
            title="Contract drift",
            body="Missing anchor.",
        )

        def _raise(_: Recommendation) -> str:
            raise AssertionError("classify_domain must not run for non-conceptual")

        assert (
            is_blocking_finding(
                rec,
                stage=STAGE_DETAIL,
                classify_domain=_raise,
            )
            is True
        )

    def test_detail_docs_fixture_demoted_with_classify_finding_domain(self) -> None:
        rec = docs_detail_body_fixture()
        assert (
            is_blocking_finding(
                rec,
                stage=STAGE_DETAIL,
                classify_domain=classify_finding_domain,
            )
            is False
        )

    def test_detail_code_logic_fixture_blocks_with_classify_finding_domain(
        self,
    ) -> None:
        rec = merge_bridge_reauthor_context_fixture()
        assert (
            is_blocking_finding(
                rec,
                stage=STAGE_DETAIL,
                classify_domain=classify_finding_domain,
            )
            is True
        )


_BARE_BAR_FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "convergence"
    / "bare-bar-four-round-sample.json"
)


def _expand_bare_bar_round(round_data: dict) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for source, severity_counts in round_data["counts"].items():
        for severity, count in severity_counts.items():
            for index in range(count):
                recs.append(
                    _conceptual_recommendation(
                        source=source,
                        severity=severity,
                        rec_id=f"r{round_data['round']}-{source}-{severity}-{index}",
                    )
                )
    return recs


class TestBareBarFourRoundSample:
    @pytest.fixture(scope="class")
    def fixture_data(self) -> dict:
        return json.loads(_BARE_BAR_FIXTURE.read_text(encoding="utf-8"))

    def test_bare_bar_four_round_sample_is_blocking_tallies(
        self, fixture_data: dict
    ) -> None:
        for round_data in fixture_data["rounds"]:
            recs = _expand_bare_bar_round(round_data)
            assert len(recs) == round_data["totals"]["findings"]
            legacy_blocking = sum(1 for rec in recs if is_blocking(rec.severity))
            assert legacy_blocking == round_data["legacy_is_blocking_count"]

    def test_bare_bar_four_round_sample_stays_blocking_all_rounds(
        self, fixture_data: dict
    ) -> None:
        for round_data in fixture_data["rounds"]:
            recs = _expand_bare_bar_round(round_data)
            assert any(
                is_blocking_finding(rec, stage=STAGE_BARE) for rec in recs
            ), f"round {round_data['round']} would allow no_blocking_findings"


def test_convergence_has_no_runtime_review_import() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "plan_tool" / "convergence.py"
    ).read_text(encoding="utf-8")
    assert re.search(r"(?m)^(from|import) plan_tool", source) is None
    assert "from plan_tool.review import Recommendation" in source
    assert "if TYPE_CHECKING:" in source


# ---------- compute_conceptual_bar_blocking_ids / qualifying sample ----------


class TestComputeConceptualBarBlockingIds:
    def test_compute_conceptual_bar_blocking_ids_bare_medium_correctness_blocks(
        self,
    ) -> None:
        from plan_tool.cli.completeness_cmd import compute_conceptual_bar_blocking_ids

        rec = _conceptual_recommendation(
            source="plan-correctness", severity="medium", rec_id="corr-medium"
        )
        assert compute_conceptual_bar_blocking_ids(
            [rec], audit_stage=STAGE_BARE
        ) == ("corr-medium",)

    def test_compute_conceptual_bar_blocking_ids_bare_medium_completeness_advisory(
        self,
    ) -> None:
        from plan_tool.cli.completeness_cmd import compute_conceptual_bar_blocking_ids

        rec = _conceptual_recommendation(
            source="plan-completeness", severity="medium", rec_id="comp-medium"
        )
        assert compute_conceptual_bar_blocking_ids(
            [rec], audit_stage=STAGE_BARE
        ) == ()

    def test_compute_conceptual_bar_blocking_ids_detail_docs_medium_demoted(
        self,
    ) -> None:
        from plan_tool.cli.completeness_cmd import compute_conceptual_bar_blocking_ids

        rec = docs_detail_body_fixture()
        assert compute_conceptual_bar_blocking_ids(
            [rec],
            audit_stage=STAGE_DETAIL,
            classify_domain=classify_finding_domain,
        ) == ()

    def test_compute_conceptual_bar_blocking_ids_detail_unknown_medium_blocks(
        self,
    ) -> None:
        from plan_tool.cli.completeness_cmd import compute_conceptual_bar_blocking_ids

        rec = _conceptual_recommendation(
            source="plan-correctness",
            severity="medium",
            rec_id="unknown-medium",
        )
        assert compute_conceptual_bar_blocking_ids(
            [rec],
            audit_stage=STAGE_DETAIL,
            classify_domain=classify_finding_domain,
        ) == ("unknown-medium",)


@pytest.mark.parametrize(
    ("conforming", "failed", "expected"),
    [
        (1, 0, True),
        (2, 0, True),
        (0, 0, False),
        (1, 1, False),
        (0, 1, False),
    ],
)
def test_audit_coverage_qualifies_sample_requires_conforming_and_no_failures(
    conforming: int, failed: int, expected: bool
) -> None:
    from plan_tool.review_persistence import audit_coverage_qualifies_sample

    total = max(1, conforming + failed)
    if total == 1:
        confirmation_kind = "confirmed-dry" if conforming and not failed else None
        budget_limited = False
    else:
        confirmation_kind = "confirmed-dry" if conforming and not failed else None
        budget_limited = confirmation_kind is None
    coverage = {
        "budget_limited": budget_limited,
        "passes_used": total,
        "cap": total,
        "recommendation_kind": None,
        "recommended_passes": None,
        "recommendation_advice": None,
        "confirmation_kind": confirmation_kind,
        "conforming_pass_count": conforming,
        "failed_or_malformed_pass_count": failed,
    }
    assert audit_coverage_qualifies_sample(coverage) is expected
    assert audit_coverage_qualifies_sample(None) is False


def test_audit_coverage_qualifies_sample_rejects_plan_quota_stop() -> None:
    from plan_tool.review_persistence import audit_coverage_qualifies_sample

    coverage = {
        "budget_limited": False,
        "passes_used": 2,
        "cap": 3,
        "recommendation_kind": None,
        "recommended_passes": None,
        "recommendation_advice": None,
        "confirmation_kind": None,
        "conforming_pass_count": 1,
        "failed_or_malformed_pass_count": 1,
        "early_stop_reason": "plan-quota",
    }

    assert audit_coverage_qualifies_sample(coverage) is False
