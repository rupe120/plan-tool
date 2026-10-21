"""Characterization tests for the shared rate-limit recovery loop.

These pin the same recovery behaviors ``tests/test_shell.py`` and
``tests/test_launcher.py`` already prove for the two duplicate copies
(``shell.claude_invoke`` / ``launcher.shell_invoker``). They drive
``run_with_rate_limit_recovery`` with a fake ``run_once`` and recording
seams so nothing blocks and every branch is exercised directly.
"""

from __future__ import annotations

import contextlib
import re
import subprocess
import sys
from pathlib import Path

from plan_tool.rate_limit_loop import (
    AttemptCategory,
    AttemptClassification,
    RecoveryAction,
    RetryDecision,
    RetryPolicy,
    run_with_rate_limit_recovery,
)


# --- classification builders (the opaque outcome the fake run_once yields) ---


def _cls(category, *, rc=1, payload="out", reset_epoch=None, hint="", failure=None):
    return AttemptClassification(
        category=category,
        rc=rc,
        payload=payload,
        reset_epoch=reset_epoch,
        hint=hint,
        failure=failure,
    )


def success(payload="done"):
    return _cls(AttemptCategory.SUCCESS, rc=0, payload=payload)


def rate_limit(*, reset_epoch=1000, hint="rate limit reached", **kw):
    return _cls(AttemptCategory.RATE_LIMIT, reset_epoch=reset_epoch, hint=hint, **kw)


def transient(*, hint="transient failure", **kw):
    return _cls(AttemptCategory.TRANSIENT, hint=hint, **kw)


def terminal(*, hint="context window exceeded", **kw):
    return _cls(AttemptCategory.TERMINAL, hint=hint, **kw)


# --- driver harness ---------------------------------------------------------


class _Seq:
    """Return a scalar every call, or pop successive values from a list."""

    def __init__(self, spec):
        self.spec = spec

    def next(self):
        if isinstance(self.spec, list):
            return self.spec.pop(0)
        return self.spec


class Recorder:
    def __init__(self):
        self.notify_calls: list[tuple[str, str]] = []
        self.run_once_attempts: list[int] = []
        self.wait_targets: list[int] = []
        self.sleeps: list[float] = []
        self.select_calls: list[str] = []
        self.ask_calls = 0


def drive(
    outcomes,
    *,
    recover_rate_limit=True,
    action=RecoveryAction.WAIT,
    fallback_backend=None,
    select_results=True,
    wait_results=True,
    can_prompt=False,
    ask_results=RecoveryAction.WAIT,
    current_backend="claude",
    on_nonsuccess=None,
    prompt_lock=None,
    fallback_seconds=3600,
    max_wait_seconds=86400,
    max_transient_retries=2,
    transient_base_delay=2.0,
    clock_value=500.0,
    attempt=1,
    retry_guard=None,
):
    rec = Recorder()
    outcome_iter = iter(outcomes)
    select_seq = _Seq(select_results)
    wait_seq = _Seq(wait_results)
    ask_seq = _Seq(ask_results)

    def run_once(a):
        rec.run_once_attempts.append(a)
        return next(outcome_iter)

    def notify(message, *, kind):
        rec.notify_calls.append((message, kind))

    def select_backend(name):
        rec.select_calls.append(name)
        return select_seq.next()

    def ask_action():
        rec.ask_calls += 1
        return ask_seq.next()

    def wait(target):
        rec.wait_targets.append(target)
        return wait_seq.next()

    def sleep(delay):
        rec.sleeps.append(delay)

    lock = prompt_lock if prompt_lock is not None else contextlib.nullcontext()

    result = run_with_rate_limit_recovery(
        run_once=run_once,
        classify=lambda o: o,
        notify=notify,
        select_backend=select_backend,
        ask_action=ask_action,
        can_prompt=lambda: can_prompt,
        wait=wait,
        prompt_lock=lock,
        current_backend_name=lambda: current_backend,
        recover_rate_limit=recover_rate_limit,
        action=action,
        fallback_backend=fallback_backend,
        fallback_seconds=fallback_seconds,
        max_wait_seconds=max_wait_seconds,
        max_transient_retries=max_transient_retries,
        transient_base_delay=transient_base_delay,
        attempt=attempt,
        sleep=sleep,
        clock=lambda: clock_value,
        on_nonsuccess=on_nonsuccess,
        retry_guard=retry_guard,
    )
    return result, rec


def _messages(rec):
    return [m for m, _ in rec.notify_calls]


# --- tests ------------------------------------------------------------------


def test_success_first_attempt_returns_immediately():
    result, rec = drive([success(payload="ok")])
    assert result == (0, "ok")
    assert rec.wait_targets == []
    assert rec.notify_calls == []
    assert rec.run_once_attempts == [1]


def test_rate_limit_waits_then_retries_once():
    result, rec = drive([rate_limit(reset_epoch=1000), success(payload="ok")])
    assert result == (0, "ok")
    assert rec.wait_targets == [1000]
    assert rec.run_once_attempts == [1, 2]


def test_rate_limit_second_hit_surfaces_already_retried_and_returns():
    result, rec = drive(
        [
            rate_limit(reset_epoch=1000, rc=1, payload="rl1"),
            rate_limit(reset_epoch=1000, rc=1, payload="rl2"),
        ]
    )
    assert result == (1, "rl2")
    assert rec.wait_targets == [1000]  # one-shot guard: waited only once
    assert any("already retried once" in m for m in _messages(rec))


def test_rate_limit_recovery_disabled_returns_without_waiting():
    result, rec = drive(
        [rate_limit(reset_epoch=1000, rc=2, payload="rl")],
        recover_rate_limit=False,
    )
    assert result == (2, "rl")
    assert rec.wait_targets == []


def test_switch_policy_swaps_backend_and_retries():
    result, rec = drive(
        [rate_limit(reset_epoch=1000), success(payload="ok")],
        action=RecoveryAction.SWITCH,
        fallback_backend="codex",
        select_results=True,
    )
    assert result == (0, "ok")
    assert rec.select_calls == ["codex"]
    assert rec.wait_targets == []  # switched, never waited
    assert rec.run_once_attempts == [1, 2]


def test_switch_policy_degrades_to_wait_when_select_fails():
    result, rec = drive(
        [rate_limit(reset_epoch=1000), success(payload="ok")],
        action=RecoveryAction.SWITCH,
        fallback_backend="codex",
        select_results=False,
    )
    assert result == (0, "ok")
    assert rec.select_calls == ["codex"]
    assert rec.wait_targets == [1000]  # failed swap → wait
    assert any("could not switch to fallback backend" in m for m in _messages(rec))


def test_switch_to_already_active_backend_degrades_to_wait():
    result, rec = drive(
        [rate_limit(reset_epoch=1000), success(payload="ok")],
        action=RecoveryAction.SWITCH,
        fallback_backend="claude",
        current_backend="claude",
    )
    assert result == (0, "ok")
    assert rec.select_calls == []  # never even attempts the swap
    assert rec.wait_targets == [1000]
    assert any("already" in m and "active" in m for m in _messages(rec))


def test_switch_to_case_mismatched_active_backend_degrades_to_wait():
    """A case-mismatched fallback naming the active backend must be caught
    by the same already-active guard as an exact match. Left as a raw
    string compare, a fallback that resolves via model-family inference
    (``Claude`` -> ``claude``) would swap "successfully" onto the same
    still-rate-limited backend every attempt, resetting the one-shot guard
    forever with no backoff."""
    result, rec = drive(
        [rate_limit(reset_epoch=1000), success(payload="ok")],
        action=RecoveryAction.SWITCH,
        fallback_backend="Claude",
        current_backend="claude",
    )
    assert result == (0, "ok")
    assert rec.select_calls == []  # never even attempts the swap
    assert rec.wait_targets == [1000]
    assert any("already" in m and "active" in m for m in _messages(rec))


def test_far_future_reset_epoch_is_capped():
    """A parsed reset time is provider text. Uncapped, an absolute far-future
    date is an unbounded sleep an unattended run cannot escape."""
    result, rec = drive(
        [rate_limit(reset_epoch=10**9), success(payload="ok")],
        clock_value=500.0,
        max_wait_seconds=86400,
    )
    assert rec.wait_targets == [500 + 86400]
    assert any("beyond the 86400s cap" in m for m in _messages(rec))
    assert result == (0, "ok")


def test_reset_epoch_inside_the_cap_is_untouched():
    _result, rec = drive(
        [rate_limit(reset_epoch=1000), success(payload="ok")],
        clock_value=500.0,
        max_wait_seconds=86400,
    )
    assert rec.wait_targets == [1000]
    assert not any("cap" in m for m in _messages(rec))


def test_missing_reset_epoch_still_uses_the_shorter_fallback():
    """The cap must not widen the no-reset-time path, which was already
    bounded — it only narrows an over-long parse."""
    _result, rec = drive(
        [rate_limit(reset_epoch=None), success(payload="ok")],
        clock_value=500.0,
        fallback_seconds=3600,
        max_wait_seconds=86400,
    )
    assert rec.wait_targets == [500 + 3600]


def test_wait_policy_never_prompts_even_on_a_tty():
    """`wait` is the unattended policy: sleep until reset and retry. A TTY
    must not turn it into the interactive menu — that made `wait` block on
    input and left `ask` with nothing to select."""
    result, rec = drive(
        [rate_limit(reset_epoch=1000), success(payload="ok")],
        action=RecoveryAction.WAIT,
        can_prompt=True,
    )
    assert rec.ask_calls == 0
    assert rec.wait_targets == [1000]
    assert result == (0, "ok")


def test_ask_policy_without_a_tty_falls_back_to_waiting():
    result, rec = drive(
        [rate_limit(reset_epoch=1000), success(payload="ok")],
        action=RecoveryAction.ASK,
        can_prompt=False,
    )
    assert rec.ask_calls == 0
    assert rec.wait_targets == [1000]
    assert result == (0, "ok")


def test_ask_menu_stop_returns_without_retry():
    result, rec = drive(
        [rate_limit(reset_epoch=1000, rc=1, payload="rl")],
        action=RecoveryAction.ASK,
        can_prompt=True,
        ask_results=RecoveryAction.STOP,
    )
    assert result == (1, "rl")
    assert rec.wait_targets == []
    assert rec.ask_calls == 1


def test_ask_menu_switch_retries():
    result, rec = drive(
        [rate_limit(reset_epoch=1000), success(payload="ok")],
        action=RecoveryAction.ASK,
        can_prompt=True,
        ask_results=RecoveryAction.SWITCH,
    )
    assert result == (0, "ok")
    assert rec.wait_targets == []
    # ASK-switch swaps internally; the loop must NOT re-select the backend.
    assert rec.select_calls == []
    assert rec.run_once_attempts == [1, 2]


def test_wait_stop_result_returns():
    result, rec = drive(
        [rate_limit(reset_epoch=1000, rc=1, payload="rl")],
        wait_results=False,
    )
    assert result == (1, "rl")
    assert rec.wait_targets == [1000]
    assert rec.run_once_attempts == [1]


def test_no_reset_epoch_uses_fallback_seconds():
    result, rec = drive(
        [rate_limit(reset_epoch=None), success(payload="ok")],
        fallback_seconds=3600,
        clock_value=500.0,
    )
    assert result == (0, "ok")
    assert rec.wait_targets == [500 + 3600]
    assert any("as fallback" in m for m in _messages(rec))


def test_transient_retries_with_exponential_backoff():
    result, rec = drive(
        [transient(), transient(), success(payload="ok")],
        max_transient_retries=3,
        transient_base_delay=2.0,
    )
    assert result == (0, "ok")
    assert rec.sleeps == [2.0, 4.0]


def test_transient_gives_up_after_max_attempts():
    result, rec = drive(
        [transient(rc=1, payload="t1"), transient(rc=1, payload="t2")],
        max_transient_retries=2,
        transient_base_delay=2.0,
    )
    assert result == (1, "t2")
    assert rec.sleeps == [2.0]


def test_terminal_failure_surfaces_hint_and_returns():
    result, rec = drive(
        [terminal(rc=1, payload="ctx", hint="context window exceeded")]
    )
    assert result == (1, "ctx")
    assert rec.wait_targets == []
    assert rec.sleeps == []
    assert any("context window exceeded" in m for m in _messages(rec))


def test_terminal_plan_quota_bypasses_wait_prompt_switch_retry_and_guard():
    """A terminal quota must never enter any rate-limit recovery seam."""
    guard = _GuardSpy(_stop())
    result, rec = drive(
        [terminal(rc=1, payload="monthly quota", hint="monthly plan quota")],
        action=RecoveryAction.SWITCH,
        fallback_backend="codex",
        can_prompt=True,
        retry_guard=guard,
    )

    assert result == (1, "monthly quota")
    assert rec.run_once_attempts == [1]
    assert rec.wait_targets == []
    assert rec.sleeps == []
    assert rec.select_calls == []
    assert rec.ask_calls == 0
    assert guard.seen == []


def test_prompt_lock_held_across_switch_and_wait():
    events: list[str] = []

    class Lock:
        def __enter__(self):
            events.append("lock-enter")
            return self

        def __exit__(self, *exc):
            events.append("lock-exit")
            return False

    outcomes = iter([rate_limit(reset_epoch=1000), success(payload="ok")])

    result = run_with_rate_limit_recovery(
        run_once=lambda a: next(outcomes),
        classify=lambda o: o,
        notify=lambda message, *, kind: None,
        select_backend=lambda name: events.append("select") or False,
        ask_action=lambda: RecoveryAction.WAIT,
        can_prompt=lambda: False,
        wait=lambda target: events.append("wait") or True,
        prompt_lock=Lock(),
        current_backend_name=lambda: "claude",
        recover_rate_limit=True,
        action=RecoveryAction.SWITCH,
        fallback_backend="codex",
        fallback_seconds=3600,
        max_wait_seconds=86400,
        max_transient_retries=2,
        transient_base_delay=2.0,
        attempt=1,
        sleep=lambda d: None,
        clock=lambda: 500.0,
        on_nonsuccess=None,
    )
    assert result == (0, "ok")
    # Both the (failed) swap and the ensuing wait run inside the lock.
    assert events == ["lock-enter", "select", "wait", "lock-exit"]


def test_on_nonsuccess_hook_fires_when_provided():
    calls: list[tuple] = []
    sentinel = object()

    def hook(outcome, failure, will_retry, recovery_reinvoke_predicted):
        calls.append((outcome, failure, will_retry, recovery_reinvoke_predicted))

    result, rec = drive(
        [rate_limit(reset_epoch=1000, failure=sentinel), success(payload="ok")],
        on_nonsuccess=hook,
    )
    assert result == (0, "ok")
    assert len(calls) == 1
    outcome, failure, will_retry, recovery_reinvoke_predicted = calls[0]
    assert failure is sentinel  # opaque failure threaded through untouched
    assert will_retry is True  # fresh recoverable rate-limit, guard unspent
    assert recovery_reinvoke_predicted is True

    # A terminal failure has neither a retry nor a recovery candidate.
    term_calls: list[tuple] = []
    drive(
        [terminal(rc=1, payload="ctx")],
        on_nonsuccess=lambda o, f, w, p: term_calls.append((w, p)),
    )
    assert term_calls == [(False, False)]


def test_on_nonsuccess_absent_is_noop():
    # With no hook, a terminal failure just returns; the loop itself emits no
    # caller-owned diagnostics — only the hint.
    result, rec = drive([terminal(rc=1, payload="x", hint="boom")])
    assert result == (1, "x")
    assert _messages(rec) == ["boom"]


def test_run_once_receives_incrementing_attempt():
    result, rec = drive(
        [rate_limit(reset_epoch=1000), transient(), success(payload="ok")],
        max_transient_retries=3,
    )
    assert rec.run_once_attempts == [1, 2, 3]

    # Honors a custom starting attempt.
    _, rec2 = drive([success(payload="ok")], attempt=5)
    assert rec2.run_once_attempts == [5]


# --- retry_guard seam -------------------------------------------------------


class _GuardSpy:
    """Records each ``outcome`` the guard receives; returns a fixed decision."""

    def __init__(self, decision):
        self.decision = decision
        self.seen: list = []

    def __call__(self, outcome):
        self.seen.append(outcome)
        return self.decision


def _stop(hint="discard the partial edits and re-run"):
    return RetryDecision(RetryPolicy.STOP, hint=hint)


def _retry():
    return RetryDecision(RetryPolicy.RETRY)


def test_transient_guard_stop_refuses_retry():
    guard = _GuardSpy(_stop(hint="partial edits left in tree"))
    result, rec = drive(
        [transient(rc=1, payload="t1")],
        max_transient_retries=3,
        retry_guard=guard,
    )
    assert result == (1, "t1")  # the just-failed attempt returned as terminal
    assert rec.run_once_attempts == [1]  # no re-invoke
    assert rec.sleeps == []  # no backoff paid
    assert len(guard.seen) == 1  # consulted once on the predicted retry
    assert any("partial edits left in tree" in m for m in _messages(rec))


def test_on_nonsuccess_reports_terminal_when_guard_stops_retry():
    calls: list[tuple[bool, bool]] = []
    result, _rec = drive(
        [transient(rc=1, payload="t1")],
        max_transient_retries=3,
        retry_guard=_GuardSpy(_stop()),
        on_nonsuccess=lambda _outcome, _failure, will_retry, predicted: calls.append(
            (will_retry, predicted)
        ),
    )

    assert result == (1, "t1")
    assert calls == [(False, True)]


def test_on_nonsuccess_reports_terminal_when_rate_limit_wait_stops():
    calls: list[tuple[bool, bool]] = []
    result, _rec = drive(
        [rate_limit(reset_epoch=1000, payload="rl")],
        wait_results=False,
        on_nonsuccess=lambda _outcome, _failure, will_retry, predicted: calls.append(
            (will_retry, predicted)
        ),
    )

    assert result == (1, "rl")
    assert calls == [(False, True)]


def test_transient_guard_retry_behaves_as_today():
    guard = _GuardSpy(_retry())
    result, rec = drive(
        [transient(), transient(), success(payload="ok")],
        max_transient_retries=3,
        transient_base_delay=2.0,
        retry_guard=guard,
    )
    assert result == (0, "ok")
    assert rec.sleeps == [2.0, 4.0]  # same backoff the plain transient test proves
    assert len(guard.seen) == 2  # consulted on each predicted retry, not on success


def test_rate_limit_guard_stop_refuses_reinvoke():
    guard = _GuardSpy(_stop(hint="rate-limit re-drive would double-apply"))
    result, rec = drive(
        [rate_limit(reset_epoch=1000, rc=1, payload="rl")],
        retry_guard=guard,
    )
    assert result == (1, "rl")
    assert rec.run_once_attempts == [1]  # no re-invoke
    assert rec.wait_targets == []  # wait not paid
    assert rec.sleeps == []
    assert len(guard.seen) == 1
    assert any("rate-limit re-drive would double-apply" in m for m in _messages(rec))


def test_rate_limit_guard_retry_waits_then_reinvokes():
    guard = _GuardSpy(_retry())
    result, rec = drive(
        [rate_limit(reset_epoch=1000), success(payload="ok")],
        retry_guard=guard,
    )
    assert result == (0, "ok")
    assert rec.wait_targets == [1000]  # waits exactly as today
    assert rec.run_once_attempts == [1, 2]
    assert len(guard.seen) == 1


def test_guard_not_consulted_on_success():
    guard = _GuardSpy(_stop())
    result, rec = drive([success(payload="ok")], retry_guard=guard)
    assert result == (0, "ok")
    assert guard.seen == []  # returns before the predicted-retry gate


def test_guard_not_consulted_when_transient_budget_exhausted():
    guard = _GuardSpy(_stop())
    result, rec = drive(
        [transient(rc=1, payload="t2")],
        max_transient_retries=1,  # will_retry_transient is False on this attempt
        retry_guard=guard,
    )
    assert result == (1, "t2")
    assert guard.seen == []  # terminal-without-re-invoke: guard untouched


def test_guard_not_consulted_on_terminal():
    guard = _GuardSpy(_stop())
    result, rec = drive(
        [terminal(rc=1, payload="ctx", hint="context window exceeded")],
        retry_guard=guard,
    )
    assert result == (1, "ctx")
    assert guard.seen == []  # both predictions False → guard untouched


def test_default_no_guard_preserves_retry():
    # Transient retry unchanged with no guard.
    result, rec = drive(
        [transient(), transient(), success(payload="ok")],
        max_transient_retries=3,
    )
    assert result == (0, "ok")
    assert rec.sleeps == [2.0, 4.0]

    # Rate-limit retry unchanged with no guard.
    result2, rec2 = drive([rate_limit(reset_epoch=1000), success(payload="ok")])
    assert result2 == (0, "ok")
    assert rec2.wait_targets == [1000]


def test_guard_stop_skips_backoff_and_wait():
    # STOP returns before any sleep on the transient arm...
    guard_t = _GuardSpy(_stop())
    _, rec_t = drive(
        [transient(rc=1, payload="t")], max_transient_retries=3, retry_guard=guard_t
    )
    assert rec_t.sleeps == []
    # ...and before any wait on the rate-limit arm.
    guard_r = _GuardSpy(_stop())
    _, rec_r = drive(
        [rate_limit(reset_epoch=1000, rc=1, payload="rl")], retry_guard=guard_r
    )
    assert rec_r.wait_targets == []


def test_leaf_has_no_first_party_runtime_import():
    src = Path(__file__).resolve().parents[1] / "plan_tool" / "rate_limit_loop.py"
    text = src.read_text()
    # The plan's acceptance grep: no column-0 first-party import.
    assert re.search(r"(?m)^(from|import) plan_tool", text) is None

    # Loading the file in isolation (bypassing the package __init__, which
    # eagerly imports shell/launcher) pulls in no ``plan_tool`` module at all.
    code = (
        "import importlib.util, sys\n"
        f"spec = importlib.util.spec_from_file_location('rll_isolated', {str(src)!r})\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        # Register before exec_module — a @dataclass under `from __future__
        # import annotations` resolves KW_ONLY via sys.modules[__module__]
        # during class creation, so an unregistered module crashes there.
        "sys.modules['rll_isolated'] = mod\n"
        "spec.loader.exec_module(mod)\n"
        "leaked = [m for m in sys.modules "
        "if m == 'plan_tool' or m.startswith('plan_tool.')]\n"
        "assert not leaked, leaked\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stderr
