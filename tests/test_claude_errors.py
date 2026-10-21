"""Tests for plan_tool.claude_errors.

Three areas under test:

1. ``classify()`` — the bucket assignment for each failure family.
   Patterns are lifted from ``run-validation-dataset.sh``; tests pin
   the *exact* user-facing copy each pattern is meant to catch, so a
   future regex tweak that loses a real-world string would surface
   here.
2. ``parse_reset_epoch()`` — the three time-format variants
   (with-date, ``resets HH:MM``, bare ``try again at``), each with a
   pinned ``now`` so the rollover-to-tomorrow branch is exercised
   deterministically.
3. ``wait_until_epoch()`` — the countdown loop. Tests use an injected
   clock / sleep so the suite stays sub-second.
"""

from __future__ import annotations

import io
import signal
from datetime import date, datetime

import pytest

from plan_tool import claude_errors, style
from plan_tool.backend import CURSOR_BACKEND, set_active_backend
from plan_tool.claude_errors import (
    ClaudeFailureKind,
    OnRateLimitAction,
    OnRateLimitAskResult,
    OnRateLimitPolicy,
    WaitUntilAction,
    WaitUntilResult,
    ask_on_rate_limit_action,
    build_classification_from_outcome,
    build_streaming_classification_from_outcome,
    classify,
    format_user_hint,
    get_rate_limit_resume_command,
    get_default_on_rate_limit_policy,
    get_default_wait_on_rate_limit,
    parse_reset_epoch,
    parse_plan_quota_reset_date,
    reset_rate_limit_resume_command_provider,
    resolve_on_rate_limit_policy,
    set_rate_limit_resume_command_provider,
    set_default_on_rate_limit_policy,
    set_default_wait_on_rate_limit,
    wait_until_epoch,
)
from plan_tool.rate_limit_loop import AttemptCategory


# ---------- classify ----------


def test_classify_success_when_rc_zero() -> None:
    """rc=0 is SUCCESS even if the body contains rate-limit copy.

    A step that *talks about* rate limits in its output should not be
    misclassified as a failure.
    """
    f = classify(0, "all good; rate limit text in the body", "")
    assert f.kind is ClaudeFailureKind.SUCCESS


@pytest.mark.parametrize("stdout", ["", " \n\t "])
def test_classify_empty_success_payload_as_transient(stdout: str) -> None:
    """An rc=0 transport success is not an application success without text."""
    f = classify(0, stdout, "")
    assert f.kind is ClaudeFailureKind.TRANSIENT
    assert "empty response" in f.hint


def test_classify_empty_streaming_success_payload_as_success() -> None:
    """Streaming implementation calls can complete entirely through edits."""
    f = classify(0, "", "", empty_response_is_failure=False)
    assert f.kind is ClaudeFailureKind.SUCCESS


@pytest.mark.parametrize(
    "stdout, stderr",
    [
        ("You've hit your limit. Try again at 5pm.", ""),
        ("", "rate limit reached"),
        ("usage limit exceeded", ""),
        ("HTTP 429 Too Many Requests", ""),
        ("try again at January 5, 2026 9pm", ""),
        # Claude Code's session-limit banner (the misclassified wording).
        ("You've hit your session limit · resets 4:20pm (America/New_York)", ""),
        ("You've hit your weekly limit", ""),
        ("", "You’ve hit your usage limit"),  # curly apostrophe variant
    ],
)
def test_classify_rate_limit_variants(stdout: str, stderr: str) -> None:
    f = classify(1, stdout, stderr)
    assert f.kind is ClaudeFailureKind.RATE_LIMIT, (
        f"expected RATE_LIMIT for stdout={stdout!r} stderr={stderr!r}, got {f.kind}"
    )


def test_classify_session_limit_banner_parses_reset_epoch() -> None:
    """Banner classifies as RATE_LIMIT *and* yields a reset epoch, so shell.py
    waits until the stated time. Regression for the never-wait incident."""
    banner = "You've hit your session limit · resets 4:20pm (America/New_York)"
    f = classify(1, banner, "")
    assert f.kind is ClaudeFailureKind.RATE_LIMIT
    assert f.reset_epoch is not None and f.reset_epoch > 0


def test_classify_rate_limit_captures_reset_epoch_when_parseable() -> None:
    """When the message carries a parseable time, classify() stashes it.

    The retry loop in shell.py uses this to decide how long to wait
    rather than falling back to the 1-hour default.
    """
    text = "rate limit. resets 3:30pm"
    f = classify(1, text, "")
    assert f.kind is ClaudeFailureKind.RATE_LIMIT
    assert f.reset_epoch is not None
    assert f.reset_epoch > 0


def test_classify_rate_limit_no_reset_epoch_when_unparseable() -> None:
    """Rate-limit without a time: kind set, epoch None."""
    f = classify(1, "rate limit reached", "")
    assert f.kind is ClaudeFailureKind.RATE_LIMIT
    assert f.reset_epoch is None


_CURSOR_MONTHLY_PLAN_QUOTA = (
    "ActionRequiredError: You've hit your usage limit for Opus. "
    "Switch to a different model or set a Spend Limit. "
    "Your usage limits will reset when your monthly cycle ends on 8/24/2026."
)


def test_classify_cursor_monthly_plan_quota_returns_plan_quota() -> None:
    set_active_backend(CURSOR_BACKEND)
    failure = classify(1, _CURSOR_MONTHLY_PLAN_QUOTA, "")
    assert failure.kind is ClaudeFailureKind.PLAN_QUOTA
    assert failure.plan_quota_reset_date == date(2026, 8, 24)


def test_classify_cursor_plan_quota_does_not_invent_reset_epoch() -> None:
    set_active_backend(CURSOR_BACKEND)
    failure = classify(1, _CURSOR_MONTHLY_PLAN_QUOTA, "")
    assert failure.reset_epoch is None


def test_classify_cursor_plan_quota_without_generic_limit_vocabulary() -> None:
    set_active_backend(CURSOR_BACKEND)
    failure = classify(
        1,
        "ActionRequiredError. Switch to a different model or set a Spend "
        "Limit. Details: monthly cycle ends on 8/24/2026.",
        "",
    )

    assert failure.kind is ClaudeFailureKind.PLAN_QUOTA
    assert failure.plan_quota_reset_date == date(2026, 8, 24)


def test_plan_quota_maps_to_terminal_recovery_category() -> None:
    set_active_backend(CURSOR_BACKEND)
    outcome = (1, _CURSOR_MONTHLY_PLAN_QUOTA, "")

    for builder in (
        build_classification_from_outcome,
        build_streaming_classification_from_outcome,
    ):
        classified = builder(outcome)
        assert classified.category is AttemptCategory.TERMINAL
        assert classified.failure.kind is ClaudeFailureKind.PLAN_QUOTA


def test_plan_quota_hint_preserves_date_only_context() -> None:
    set_active_backend(CURSOR_BACKEND)
    failure = classify(1, _CURSOR_MONTHLY_PLAN_QUOTA, "")

    assert format_user_hint(failure) == (
        "cursor monthly plan quota reached; monthly cycle resets on 2026-08-24"
    )
    assert failure.reset_epoch is None


def test_classify_generic_usage_limit_is_not_plan_quota() -> None:
    set_active_backend(CURSOR_BACKEND)
    failure = classify(1, "usage limit reached", "")
    assert failure.kind is ClaudeFailureKind.RATE_LIMIT
    assert failure.plan_quota_reset_date is None
    assert (
        build_classification_from_outcome((1, "usage limit reached", "")).category
        is AttemptCategory.RATE_LIMIT
    )


def test_classify_cursor_plan_quota_near_miss_preserves_redacted_evidence() -> None:
    set_active_backend(CURSOR_BACKEND)
    failure = classify(
        1,
        "ActionRequiredError — usage limit reached. Switch models or set a "
        "Spend Limit. The monthly cycle ends on 8/24/2026. token sk-secret123",
        "",
    )

    assert failure.kind is ClaudeFailureKind.RATE_LIMIT
    assert failure.plan_quota_pattern_miss is not None
    assert failure.plan_quota_pattern_miss.backend == "cursor"
    assert set(failure.plan_quota_pattern_miss.markers) == {
        "action-required-error",
        "usage-limit",
        "switch-model",
        "spend-limit",
        "monthly-cycle",
    }
    assert "sk-secret123" not in failure.plan_quota_pattern_miss.excerpt
    assert "[REDACTED]" in failure.plan_quota_pattern_miss.excerpt


def test_classify_cursor_plan_quota_near_miss_redacts_before_excerpt_slice() -> None:
    set_active_backend(CURSOR_BACKEND)
    secret = "sk-" + "a" * 40
    failure = classify(
        1,
        "x" * 200
        + secret
        + "x" * 127
        + "ActionRequiredError — usage limit reached. Switch models or set a "
        "Spend Limit before the monthly cycle ends.",
        "",
    )

    assert failure.plan_quota_pattern_miss is not None
    excerpt = failure.plan_quota_pattern_miss.excerpt
    assert secret not in excerpt
    assert "a" * 30 not in excerpt
    assert "[REDACTED]" in excerpt


def test_classify_cursor_plan_quota_near_miss_uses_earliest_marker_for_excerpt() -> None:
    set_active_backend(CURSOR_BACKEND)
    failure = classify(
        1,
        "The monthly cycle ends later. "
        + "x" * 400
        + "ActionRequiredError — usage limit reached. Switch models or set a "
        "Spend Limit.",
        "",
    )

    assert failure.plan_quota_pattern_miss is not None
    assert failure.plan_quota_pattern_miss.excerpt.startswith(
        "The monthly cycle ends later."
    )


def test_classify_generic_cursor_rate_limit_has_no_quota_near_miss() -> None:
    set_active_backend(CURSOR_BACKEND)
    failure = classify(1, "usage limit reached", "")

    assert failure.kind is ClaudeFailureKind.RATE_LIMIT
    assert failure.plan_quota_pattern_miss is None


def test_classify_cursor_non_candidate_skips_near_miss_redaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_active_backend(CURSOR_BACKEND)
    redacted: list[str] = []
    monkeypatch.setattr(
        claude_errors,
        "redact_sensitive_text",
        lambda text: redacted.append(text) or text,
    )

    failure = classify(1, "usage limit reached", "")

    assert failure.kind is ClaudeFailureKind.RATE_LIMIT
    assert redacted == []


def test_classify_cursor_unknown_plan_quota_near_miss_keeps_evidence() -> None:
    set_active_backend(CURSOR_BACKEND)
    failure = classify(
        1,
        "ActionRequiredError — set a Spend Limit before the monthly cycle ends.",
        "",
    )

    assert failure.kind is ClaudeFailureKind.UNKNOWN_NONZERO
    assert failure.plan_quota_pattern_miss is not None
    assert failure.plan_quota_pattern_miss.markers == (
        "action-required-error",
        "spend-limit",
        "monthly-cycle",
    )


@pytest.mark.parametrize(
    ("competing_failure", "kind"),
    [
        ("unauthorized", ClaudeFailureKind.AUTH),
        ("input too long", ClaudeFailureKind.CONTEXT_OVERFLOW),
        ("network error", ClaudeFailureKind.TRANSIENT),
    ],
)
def test_classify_cursor_near_miss_survives_competing_failure_branch(
    competing_failure: str, kind: ClaudeFailureKind
) -> None:
    set_active_backend(CURSOR_BACKEND)
    failure = classify(
        1,
        "ActionRequiredError — set a Spend Limit before the monthly cycle "
        f"ends; {competing_failure}.",
        "",
    )

    assert failure.kind is kind
    assert failure.plan_quota_pattern_miss is not None


@pytest.mark.parametrize(
    "stdout",
    [
        "prompt is too long",
        "input too long",
        "too many tokens in request",
        "maximum context exceeded",
        "context length exceeded the limit",
        "exceeded the maximum context",
        "please reduce tokens in the prompt",
    ],
)
def test_classify_context_overflow_variants(stdout: str) -> None:
    f = classify(1, stdout, "")
    assert f.kind is ClaudeFailureKind.CONTEXT_OVERFLOW
    assert "split a large seed" in f.hint


@pytest.mark.parametrize(
    "stdout",
    [
        "request timed out after 30s",
        "ECONNRESET while reading response",
        "EAI_AGAIN dns lookup",
        "network error: connection reset",
        "temporarily unavailable, please retry",
        "HTTP 429",  # bare 429 with no quota copy = transient
        # Node-fetch's dropped-connection wordings.
        "API Error: The socket connection was closed unexpectedly. "
        "For more information, pass `verbose: true`",
        "FetchError: socket hang up",
        # Anthropic server-side overload / 5xx — retryable, no 429.
        "Overloaded",
        "API Error: 529",  # bare overload status, no word copy
        "500 Internal Server Error",
        "502 Bad Gateway",
        "503 Service Unavailable",
        # Mid-stream turn abort — only the truncation tail is emitted.
        "The response above may be incomplete.",
    ],
)
def test_classify_transient_variants(stdout: str) -> None:
    f = classify(1, stdout, "")
    assert f.kind is ClaudeFailureKind.TRANSIENT


def test_classify_generic_api_error_is_not_transient() -> None:
    """A bare "API error" (e.g. a permanent 400) must stay UNKNOWN_NONZERO —
    the transient net is deliberately keyword-specific so deterministic 4xx
    failures fail fast instead of burning the backoff budget."""
    f = classify(1, "API error: 400 invalid request", "")
    assert f.kind is ClaudeFailureKind.UNKNOWN_NONZERO


def test_classify_overload_does_not_lose_to_rate_limit_precedence() -> None:
    """An overload that also carries quota/429 copy still classifies as
    RATE_LIMIT — the additive overload alternations must not steal
    precedence from the rate-limit check.
    """
    f = classify(
        1, "HTTP 429 rate limit reached; service unavailable. Try at 5pm.", ""
    )
    assert f.kind is ClaudeFailureKind.RATE_LIMIT


def test_classify_unknown_when_rc_nonzero_and_no_pattern_matches() -> None:
    f = classify(2, "something else broke", "stacktrace")
    assert f.kind is ClaudeFailureKind.UNKNOWN_NONZERO
    assert "code 2" in f.hint


def test_classify_rate_limit_wins_over_transient_on_overlap() -> None:
    """When both rate-limit copy and transient copy are present, rate-limit wins.

    Real Claude errors often include both ("HTTP 429: rate limit
    reached. Try again at 5pm") — waiting for the explicit reset is
    more accurate than a few-second backoff.
    """
    f = classify(
        1, "HTTP 429 rate limit reached. timed out. Try again at 5pm.", ""
    )
    assert f.kind is ClaudeFailureKind.RATE_LIMIT


def test_classify_reads_both_stdout_and_stderr() -> None:
    """Patterns must match across stream boundaries.

    Some failures land on stdout (in-band SDK message), others on
    stderr (transport-layer error). The classifier sees a combined view.
    """
    f = classify(1, "", "rate limit on stderr only")
    assert f.kind is ClaudeFailureKind.RATE_LIMIT


# ---------- parse_reset_epoch ----------


def test_parse_reset_epoch_resets_hhmm() -> None:
    now = datetime(2026, 5, 14, 10, 0)  # 10:00 → 3:30pm later today
    epoch = parse_reset_epoch("rate limit. resets 3:30pm", now=now)
    assert epoch is not None
    expected = datetime(2026, 5, 14, 15, 30)
    # +120s buffer per the implementation
    assert epoch == int(expected.timestamp()) + 120


def test_parse_reset_epoch_rolls_forward_when_time_is_past() -> None:
    """A bare HH:MM in the past must roll to tomorrow.

    Otherwise a 3am reset parsed at 10am would tell the caller to
    wait until -7h, blow past the buffer, and immediately retry into
    the same rate limit.
    """
    now = datetime(2026, 5, 14, 10, 0)
    epoch = parse_reset_epoch("resets 3am", now=now)
    assert epoch is not None
    expected = datetime(2026, 5, 15, 3, 0)
    assert epoch == int(expected.timestamp()) + 120


def test_parse_reset_epoch_try_again_at_with_date() -> None:
    now = datetime(2026, 5, 14, 10, 0)
    epoch = parse_reset_epoch(
        "try again at January 5, 2027 9:30pm", now=now
    )
    assert epoch is not None
    expected = datetime(2027, 1, 5, 21, 30)
    assert epoch == int(expected.timestamp()) + 120


def test_parse_reset_epoch_try_again_at_no_date() -> None:
    now = datetime(2026, 5, 14, 10, 0)
    epoch = parse_reset_epoch("try again at 9pm", now=now)
    assert epoch is not None
    expected = datetime(2026, 5, 14, 21, 0)
    assert epoch == int(expected.timestamp()) + 120


def test_parse_reset_epoch_handles_noon_and_midnight() -> None:
    now = datetime(2026, 5, 14, 1, 0)
    epoch_noon = parse_reset_epoch("resets 12pm", now=now)
    assert epoch_noon is not None
    expected_noon = datetime(2026, 5, 14, 12, 0)
    assert epoch_noon == int(expected_noon.timestamp()) + 120

    now = datetime(2026, 5, 14, 14, 0)
    epoch_mid = parse_reset_epoch("resets 12am", now=now)
    assert epoch_mid is not None
    expected_mid = datetime(2026, 5, 15, 0, 0)
    assert epoch_mid == int(expected_mid.timestamp()) + 120


def test_parse_reset_epoch_returns_none_when_no_match() -> None:
    assert parse_reset_epoch("totally unrelated text") is None


def test_parse_reset_epoch_invalid_date_returns_none() -> None:
    """Feb 30 isn't a valid date — return None rather than raise.

    The classifier should still bucket as RATE_LIMIT in this case
    (the surrounding text says "rate limit") and the caller falls
    back to the default wait.
    """
    epoch = parse_reset_epoch("try again at February 30, 2027 9pm")
    assert epoch is None


def test_plan_quota_reset_date_rejects_invalid_calendar_date() -> None:
    assert (
        parse_plan_quota_reset_date("monthly cycle ends on 2/30/2026") is None
    )


# ---------- wait_until_epoch ----------


class _ManualClock:
    """Fake clock that advances only when ``sleep`` is called.

    Lets a test simulate a 10-minute wait in milliseconds while still
    exercising the loop's exit condition.
    """

    def __init__(self, start: float) -> None:
        self.t = start

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds


def test_wait_until_epoch_returns_true_immediately_when_past() -> None:
    clock = _ManualClock(1000.0)
    stream = io.StringIO()
    sleep_calls: list[float] = []
    result = wait_until_epoch(
        500,  # already past
        sleep=lambda s: sleep_calls.append(s),
        clock=clock.now,
        stream=stream,
    )
    assert result == WaitUntilResult(action=WaitUntilAction.RETRY)
    assert sleep_calls == []
    assert stream.getvalue() == ""


def test_wait_until_epoch_counts_down_then_returns_true() -> None:
    clock = _ManualClock(1000.0)
    stream = io.StringIO()
    target = int(clock.t) + 3  # 3 seconds in the future
    result = wait_until_epoch(
        target, sleep=clock.sleep, clock=clock.now, stream=stream
    )
    assert result.action is WaitUntilAction.RETRY
    out = stream.getvalue()
    assert "waiting until" in out
    assert "wait complete" in out


def test_wait_until_epoch_returns_false_on_cancel_check() -> None:
    """A cancel_check returning True breaks the loop early.

    The launcher uses this to honor a Ctrl+C without having to install
    its own signal handler in the middle of a streaming claude call.
    """
    clock = _ManualClock(1000.0)
    target = int(clock.t) + 60
    cancel_after = {"calls": 0}

    def cancel() -> bool:
        cancel_after["calls"] += 1
        return cancel_after["calls"] >= 2

    result = wait_until_epoch(
        target,
        sleep=clock.sleep,
        clock=clock.now,
        stream=io.StringIO(),
        cancel_check=cancel,
    )
    assert result.action is WaitUntilAction.STOP


def test_wait_until_epoch_returns_stop_on_key_check_stop() -> None:
    clock = _ManualClock(1000.0)
    target = int(clock.t) + 60
    key_calls = {"n": 0}

    def key_check() -> str | None:
        key_calls["n"] += 1
        return "q" if key_calls["n"] >= 2 else None

    result = wait_until_epoch(
        target,
        sleep=clock.sleep,
        clock=clock.now,
        stream=io.StringIO(),
        key_check=key_check,
    )
    assert result.action is WaitUntilAction.STOP


def test_wait_until_epoch_ignores_unmapped_key_check_key() -> None:
    clock = _ManualClock(1000.0)
    target = int(clock.t) + 2
    keys = iter(["x", None])

    result = wait_until_epoch(
        target,
        sleep=clock.sleep,
        clock=clock.now,
        stream=io.StringIO(),
        key_check=lambda: next(keys, None),
    )
    assert result.action is WaitUntilAction.RETRY


# ---------- wait_until_epoch: on_interrupt ----------


def test_wait_until_epoch_interrupted_default_stays_swallowed() -> None:
    """``test_wait_interrupted_plain``'s exact fixture, with no
    ``on_interrupt`` — every existing caller's shape. Byte-identical to
    before this parameter existed: swallowed, converted to STOP, no raise.
    """
    clock = _ManualClock(1000.0)
    stream = io.StringIO()

    def interrupt(_seconds: float) -> None:
        raise KeyboardInterrupt

    prev = signal.getsignal(signal.SIGINT)
    try:
        result = wait_until_epoch(
            int(clock.t) + 60,
            sleep=interrupt,
            clock=clock.now,
            stream=stream,
        )
    finally:
        signal.signal(signal.SIGINT, prev)
    assert result.action is WaitUntilAction.STOP
    assert stream.getvalue().endswith("\nplan-tool: wait interrupted.\n")


def test_wait_until_epoch_interrupted_calls_hook_and_reraises() -> None:
    """With ``on_interrupt`` supplied, the hook fires exactly once and the
    original ``KeyboardInterrupt`` propagates instead of a
    ``WaitUntilResult`` being returned."""
    clock = _ManualClock(1000.0)
    stream = io.StringIO()
    calls: list[None] = []

    def interrupt(_seconds: float) -> None:
        raise KeyboardInterrupt

    prev = signal.getsignal(signal.SIGINT)
    try:
        with pytest.raises(KeyboardInterrupt):
            wait_until_epoch(
                int(clock.t) + 60,
                sleep=interrupt,
                clock=clock.now,
                stream=stream,
                on_interrupt=lambda: calls.append(None),
            )
    finally:
        signal.signal(signal.SIGINT, prev)
    assert len(calls) == 1


def test_wait_until_epoch_reraise_still_reinstalls_sigint_handler() -> None:
    """The default SIGINT handler is still reinstalled before the
    exception propagates — the existing second-Ctrl+C-should-kill
    behavior is unweakened by taking the ``on_interrupt`` branch."""
    clock = _ManualClock(1000.0)
    stream = io.StringIO()

    def interrupt(_seconds: float) -> None:
        raise KeyboardInterrupt

    prev = signal.getsignal(signal.SIGINT)
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        with pytest.raises(KeyboardInterrupt):
            wait_until_epoch(
                int(clock.t) + 60,
                sleep=interrupt,
                clock=clock.now,
                stream=stream,
                on_interrupt=lambda: None,
            )
        assert signal.getsignal(signal.SIGINT) is signal.default_int_handler
    finally:
        signal.signal(signal.SIGINT, prev)


# ---------- module-level rate-limit policy ----------


def test_on_rate_limit_action_values_are_stable() -> None:
    assert [action.value for action in OnRateLimitAction] == [
        "wait",
        "switch",
        "stop",
        "ask",
    ]


def test_wait_until_action_values_are_stable() -> None:
    assert [action.value for action in WaitUntilAction] == ["retry", "stop"]


def test_default_on_rate_limit_policy_round_trips() -> None:
    original = get_default_on_rate_limit_policy()
    try:
        policy = OnRateLimitPolicy(action=OnRateLimitAction.STOP)
        set_default_on_rate_limit_policy(policy)
        assert get_default_on_rate_limit_policy() == policy

        wait_policy = OnRateLimitPolicy(
            action=OnRateLimitAction.WAIT,
            fallback_backend="codex",
        )
        set_default_on_rate_limit_policy(wait_policy)
        assert get_default_on_rate_limit_policy() == wait_policy
    finally:
        set_default_on_rate_limit_policy(original)


def test_on_rate_limit_ask_result_accepts_switch_backend() -> None:
    result = OnRateLimitAskResult(
        action=OnRateLimitAction.SWITCH,
        switch_backend_name="codex",
    )
    assert result.action is OnRateLimitAction.SWITCH
    assert result.switch_backend_name == "codex"


def test_on_rate_limit_ask_result_requires_switch_backend() -> None:
    with pytest.raises(ValueError, match="required for switch"):
        OnRateLimitAskResult(action=OnRateLimitAction.SWITCH)


def test_on_rate_limit_ask_result_rejects_backend_for_wait_or_stop() -> None:
    with pytest.raises(ValueError, match="only valid for switch"):
        OnRateLimitAskResult(
            action=OnRateLimitAction.WAIT,
            switch_backend_name="codex",
        )


def test_default_wait_flag_round_trips() -> None:
    original = get_default_on_rate_limit_policy()
    try:
        set_default_wait_on_rate_limit(False)
        assert get_default_wait_on_rate_limit() is False
        assert (
            get_default_on_rate_limit_policy().action
            is OnRateLimitAction.STOP
        )
        set_default_wait_on_rate_limit(True)
        assert get_default_wait_on_rate_limit() is True
        assert (
            get_default_on_rate_limit_policy().action
            is OnRateLimitAction.WAIT
        )
    finally:
        set_default_on_rate_limit_policy(original)


def test_resolve_on_rate_limit_policy_none_reads_process_default() -> None:
    """``None`` yields the full process-wide policy — action *and* fallback —
    so SWITCH/ASK reach the invokers instead of collapsing to a boolean."""
    original = get_default_on_rate_limit_policy()
    try:
        policy = OnRateLimitPolicy(
            action=OnRateLimitAction.SWITCH, fallback_backend="codex"
        )
        set_default_on_rate_limit_policy(policy)
        assert resolve_on_rate_limit_policy(None) == policy
    finally:
        set_default_on_rate_limit_policy(original)


def test_resolve_on_rate_limit_policy_boolean_maps_to_wait_or_stop() -> None:
    """The legacy per-call boolean maps exactly like the compat setter:
    True → WAIT, False → STOP, independent of the process default."""
    original = get_default_on_rate_limit_policy()
    try:
        set_default_on_rate_limit_policy(
            OnRateLimitPolicy(action=OnRateLimitAction.ASK)
        )
        assert resolve_on_rate_limit_policy(True) == OnRateLimitPolicy(
            action=OnRateLimitAction.WAIT
        )
        assert resolve_on_rate_limit_policy(False) == OnRateLimitPolicy(
            action=OnRateLimitAction.STOP
        )
    finally:
        set_default_on_rate_limit_policy(original)


def test_rate_limit_resume_command_provider_is_context_scoped() -> None:
    assert get_rate_limit_resume_command() is None

    token = set_rate_limit_resume_command_provider(
        lambda: "plan-tool run example --backend claude"
    )
    try:
        assert (
            get_rate_limit_resume_command()
            == "plan-tool run example --backend claude"
        )
    finally:
        reset_rate_limit_resume_command_provider(token)

    assert get_rate_limit_resume_command() is None


def test_ask_on_rate_limit_action_waits_on_empty_choice() -> None:
    stream = io.StringIO()
    prompts: list[str] = []
    token = set_rate_limit_resume_command_provider(
        lambda: "plan-tool run p --step 4 --backend claude"
    )

    def input_fn(prompt: str) -> str:
        prompts.append(prompt)
        return ""

    try:
        result = ask_on_rate_limit_action(
            current_backend_name="claude",
            input_fn=input_fn,
            stream=stream,
        )
    finally:
        reset_rate_limit_resume_command_provider(token)

    assert result == OnRateLimitAskResult(action=OnRateLimitAction.WAIT)
    assert prompts == ["rate limit [w/b/s]: "]
    assert "Choose (w)ait, switch (b)ackend, or (s)top." in stream.getvalue()
    assert "plan-tool run p --step 4 --backend claude" in stream.getvalue()


def test_ask_on_rate_limit_action_stops_on_save_choice() -> None:
    result = ask_on_rate_limit_action(
        current_backend_name="claude",
        input_fn=lambda _prompt: "s",
        stream=io.StringIO(),
    )
    assert result == OnRateLimitAskResult(action=OnRateLimitAction.STOP)


def test_ask_on_rate_limit_action_stops_on_eof() -> None:
    def input_fn(_prompt: str) -> str:
        raise EOFError

    result = ask_on_rate_limit_action(
        current_backend_name="claude",
        input_fn=input_fn,
        stream=io.StringIO(),
    )
    assert result == OnRateLimitAskResult(action=OnRateLimitAction.STOP)


def test_ask_on_rate_limit_action_reprompts_for_invalid_menu_choice() -> None:
    answers = iter(["x", "w"])
    stream = io.StringIO()

    result = ask_on_rate_limit_action(
        current_backend_name="claude",
        input_fn=lambda _prompt: next(answers),
        stream=stream,
    )

    assert result == OnRateLimitAskResult(action=OnRateLimitAction.WAIT)
    assert "please choose w, b, or s." in stream.getvalue()


def test_ask_on_rate_limit_action_switches_to_registered_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from plan_tool import backend

    monkeypatch.setattr(backend, "registered_names", lambda: {"claude", "codex"})
    answers = iter(["b", "codex"])

    result = ask_on_rate_limit_action(
        current_backend_name="claude",
        input_fn=lambda _prompt: next(answers),
        stream=io.StringIO(),
    )

    assert result == OnRateLimitAskResult(
        action=OnRateLimitAction.SWITCH,
        switch_backend_name="codex",
    )


def test_ask_on_rate_limit_action_rejects_unregistered_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from plan_tool import backend

    monkeypatch.setattr(backend, "registered_names", lambda: {"claude", "codex"})
    answers = iter(["b", "nope", "", "codex"])
    stream = io.StringIO()

    result = ask_on_rate_limit_action(
        current_backend_name="claude",
        input_fn=lambda _prompt: next(answers),
        stream=stream,
    )

    assert result.switch_backend_name == "codex"
    assert "unknown backend 'nope'; registered: claude, codex" in stream.getvalue()
    assert "please enter a backend name (claude, codex)." in stream.getvalue()


# ---------- format_user_hint ----------


def test_format_user_hint_empty_response_is_retryable() -> None:
    f = classify(0, "", "")
    assert "empty response" in format_user_hint(f)


def test_format_user_hint_uses_hint_when_present() -> None:
    f = classify(1, "prompt is too long", "")
    msg = format_user_hint(f)
    assert "split a large seed" in msg


# ---------- style routing ----------


class TestClaudeErrorsStyleOutput:
    """Pin ``wait_until_epoch``'s diagnostic heads to ``style.tool()``:
    plain-mode bytes are unchanged, the ``\\r`` countdown ticker stays raw,
    and forced color paints only the ``plan-tool:`` prefix."""

    def test_waiting_notice_plain(self) -> None:
        clock = _ManualClock(1000.0)
        stream = io.StringIO()
        wait_until_epoch(
            int(clock.t) + 3, sleep=clock.sleep, clock=clock.now, stream=stream
        )
        assert stream.getvalue().startswith("\nplan-tool: waiting until ")

    def test_wait_complete_plain(self) -> None:
        clock = _ManualClock(1000.0)
        stream = io.StringIO()
        result = wait_until_epoch(
            int(clock.t) + 3, sleep=clock.sleep, clock=clock.now, stream=stream
        )
        assert result.action is WaitUntilAction.RETRY
        assert stream.getvalue().endswith("plan-tool: wait complete, retrying.\n")

    def test_wait_cancelled_plain(self) -> None:
        clock = _ManualClock(1000.0)
        stream = io.StringIO()
        result = wait_until_epoch(
            int(clock.t) + 60,
            sleep=clock.sleep,
            clock=clock.now,
            stream=stream,
            cancel_check=lambda: True,
        )
        assert result.action is WaitUntilAction.STOP
        assert stream.getvalue().endswith("\nplan-tool: wait cancelled.\n")

    def test_wait_interrupted_plain(self) -> None:
        clock = _ManualClock(1000.0)
        stream = io.StringIO()

        def interrupt(_seconds: float) -> None:
            raise KeyboardInterrupt

        prev = signal.getsignal(signal.SIGINT)
        try:
            result = wait_until_epoch(
                int(clock.t) + 60,
                sleep=interrupt,
                clock=clock.now,
                stream=stream,
            )
        finally:
            signal.signal(signal.SIGINT, prev)
        assert result.action is WaitUntilAction.STOP
        assert stream.getvalue().endswith("\nplan-tool: wait interrupted.\n")

    def test_countdown_ticker_stays_raw(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_FORCE_COLOR", "1")
        clock = _ManualClock(1000.0)
        stream = io.StringIO()
        wait_until_epoch(
            int(clock.t) + 3, sleep=clock.sleep, clock=clock.now, stream=stream
        )
        # The per-tick line is written raw, so its ``plan-tool:`` tag is
        # un-dimmed even with color forced on — proves it was not routed
        # through ``tool()`` (which would emit ``\r\033[2mplan-tool:``).
        assert "\rplan-tool: " in stream.getvalue()

    def test_wait_complete_color_prefix_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_FORCE_COLOR", "1")
        clock = _ManualClock(1000.0)
        stream = io.StringIO()
        wait_until_epoch(
            int(clock.t) + 3, sleep=clock.sleep, clock=clock.now, stream=stream
        )
        assert (
            style.DIM + "plan-tool:" + style.RESET + " wait complete, retrying.\n"
            in stream.getvalue()
        )


def test_backend_timeout_sentinel_classifies_timeout_terminal() -> None:
    """A synthetic timeout outcome (BACKEND_TIMEOUT_SENTINEL on stderr)
    classifies TIMEOUT so the recovery loop does not retry under the same
    budget."""
    from plan_tool.claude_errors import (
        BACKEND_TIMEOUT_SENTINEL,
        ClaudeFailureKind,
        AttemptCategory,
        build_classification,
        classify,
    )

    stderr = f"{BACKEND_TIMEOUT_SENTINEL}: no response within 300.0s"
    failure = classify(124, "", stderr)
    assert failure.kind is ClaudeFailureKind.TIMEOUT
    assert failure.kind.value == "backend_timeout"
    classified = build_classification(124, "", stderr)
    assert classified.category is AttemptCategory.TERMINAL


def test_backend_runner_sentinel_matches_claude_errors_sentinel() -> None:
    """Drift guard for the mirror-not-import design: ``backend_runner``
    can't import this module (its leaf constraint), so it mirrors
    ``BACKEND_TIMEOUT_SENTINEL``'s literal value instead. This pins the two
    equal so a future edit to either can't silently break the bridge."""
    from plan_tool import backend_runner
    from plan_tool.claude_errors import BACKEND_TIMEOUT_SENTINEL

    assert backend_runner._BACKEND_TIMEOUT_SENTINEL == BACKEND_TIMEOUT_SENTINEL


def test_classify_recognizes_a_runner_produced_timeout_stderr() -> None:
    """A monitor-thread kill (``backend_runner.run_streaming_once``) never
    raises ``subprocess.TimeoutExpired`` — it terminates the child directly
    and appends a sentinel-bearing line to the returned stderr. Feeding
    ``classify()`` stderr shaped like the runner's own kill-path formatting
    proves the bridge holds with zero changes to ``classify()`` itself."""
    from plan_tool.claude_errors import BACKEND_TIMEOUT_SENTINEL

    stderr = (
        f"{BACKEND_TIMEOUT_SENTINEL}: configured timeout exceeded after "
        "60s (threshold 60s)\n"
    )
    failure = classify(1, "", stderr)
    assert failure.kind is ClaudeFailureKind.TIMEOUT

    stderr_silence = (
        f"{BACKEND_TIMEOUT_SENTINEL}: no activity for 900s "
        "(threshold 900s)\n"
    )
    failure_silence = classify(-15, "", stderr_silence)
    assert failure_silence.kind is ClaudeFailureKind.TIMEOUT
