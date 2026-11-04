"""Classification + recovery for claude subprocess failures.

This module gives the rest of plan-tool a typed view of *why* a
``claude -p`` call failed so the launcher and shell wrappers can react
appropriately instead of treating every non-zero exit identically.
``BACKEND_TIMEOUT_SENTINEL``-bearing stderr reaches ``classify`` from
``backend_runner.run_streaming_once``'s monitor-thread kill ladder — the
sole current producer, shared by both the streaming (``launcher``) and
batch (``shell.claude_invoke``) lanes since both now spawn through it —
which mirrors this module's constant rather than importing it, feeding this
module's classification unchanged.

Seven failure kinds are recognized. ``classify`` checks
:data:`ClaudeFailureKind.TIMEOUT` first when stderr carries
``BACKEND_TIMEOUT_SENTINEL`` (terminal under the same budget — value
``"backend_timeout"``, distinct from ``bench`` harness
``failure_kind="timeout"``), then recognizes a provider-confirmed plan quota
before the remaining classifications:

- :data:`ClaudeFailureKind.RATE_LIMIT` — Claude's quota-exhausted output
  (``"You've hit your limit"``, ``"try again at..."``, ``"resets HH:MM"``,
  HTTP 429 / ``"usage limit"``). Recoverable: the caller waits until the
  parsed reset epoch and retries.
- :data:`ClaudeFailureKind.PLAN_QUOTA` — provider-confirmed monthly plan
  exhaustion. Terminal: the caller surfaces the stated reset date without
  converting it into a local reset time or retrying.
- :data:`ClaudeFailureKind.AUTH` — the backend reports an unauthenticated
  state (e.g. codex's missing/invalid ``~/.codex/auth.json``). Only
  emitted when the active backend supplies an ``auth_pattern``. NOT
  recoverable by waiting or retrying; the caller surfaces a
  fix-credentials hint and bails. Ranks just below RATE_LIMIT so an
  auth-expired message that also 429s still waits.
- :data:`ClaudeFailureKind.CONTEXT_OVERFLOW` — prompt or response exceeded
  the model's context window (``"prompt is too long"``, ``"maximum
  context exceeded"``, ``"reduce ... tokens"``). NOT recoverable by
  waiting; the caller surfaces a hint to narrow scope (a smaller
  ``--step``, or splitting a large seed into multiple plans).
- :data:`ClaudeFailureKind.TRANSIENT` — network blips or generic 429s
  without a parseable reset time (``"timeout"``, ``"ECONNRESET"``,
  ``"EAI_AGAIN"``, ``"network error"``, ``"connection reset"``,
  bare ``"429"``). Recoverable with exponential backoff.
- :data:`ClaudeFailureKind.UNKNOWN_NONZERO` — non-zero exit with no
  recognizable pattern. Surface stderr tail and bail.

Plus :data:`ClaudeFailureKind.SUCCESS` for ``rc == 0``.

The pattern set is lifted from ``run-validation-dataset.sh`` which has
the most battle-tested copy detection in the org. Patterns deliberately
match the Codex flavor of the same messages too (``"usage limit"``,
``"try again at <Mon DD>"``) because some shared infrastructure layers
forward those strings unchanged.
"""

from __future__ import annotations

import re
import signal
import sys
import threading
import time
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional, TextIO, Union

try:  # POSIX-only modules; unavailable platforms simply skip TTY polling.
    import select
    import termios
    import tty
except ImportError:  # pragma: no cover - exercised only on non-POSIX hosts
    select = None  # type: ignore[assignment]
    termios = None  # type: ignore[assignment]
    tty = None  # type: ignore[assignment]

from plan_tool.backend import get_active_backend, redact_sensitive_text
from plan_tool.backend_runner import InterruptSource
from plan_tool.rate_limit_loop import (
    AttemptCategory,
    AttemptClassification,
    RecoveryAction,
)
from plan_tool.style import tool
from plan_tool.telemetry import record_backend_pattern_miss

if TYPE_CHECKING:
    # Type hints only — a runtime import would be safe (run_log.py doesn't
    # import this module) but TYPE_CHECKING keeps the wrapping factories
    # below consistent with the rest of plan-tool's seam-wrapping modules.
    from plan_tool.run_log import RunLogWriter


# Distinctive marker written to a killed call's stderr by
# `backend_runner.run_streaming_once`'s monitor-thread kill ladder — a
# configured-timeout kill on either lane (`shell.claude_invoke` opts in via
# `enforce_configured_timeout=True`; `launcher` stays exempt) or a
# silence-timeout kill on either. Classify routes it to TIMEOUT (terminal) —
# retrying under the same budget nearly always double-pays wall-clock for
# another empty kill. Unlikely in real backend output; kept here (the
# classifier's home) so the producer mirrors rather than imports it —
# `backend_runner` can't import this module without breaking its own leaf
# import constraint.
BACKEND_TIMEOUT_SENTINEL = "__plan_tool_backend_timeout__"


class ClaudeFailureKind(str, Enum):
    """Closed set of failure classifications.

    Strings (not auto-ints) so they grep cleanly in run-log JSONL
    and survive a serialization round-trip without an enum-aware decoder.
    """

    SUCCESS = "success"
    RATE_LIMIT = "rate_limit"
    PLAN_QUOTA = "plan_quota"
    AUTH = "auth"
    CONTEXT_OVERFLOW = "context_overflow"
    TRANSIENT = "transient"
    TIMEOUT = "backend_timeout"
    UNKNOWN_NONZERO = "unknown_nonzero"


class OnRateLimitAction(str, Enum):
    """Closed set of operator choices when a backend hits a quota limit."""

    WAIT = "wait"
    SWITCH = "switch"
    STOP = "stop"
    ASK = "ask"


class WaitUntilAction(str, Enum):
    """What the caller should do after a quota-reset wait returns."""

    RETRY = "retry"
    STOP = "stop"


# Maps the first-party enums onto the shared recovery loop's neutral
# vocabulary. Defined once here — the enums' owning module — so
# shell.claude_invoke and launcher.shell_invoker can't drift, which is the
# whole point of the rate_limit_loop extraction (BACKLOG #101). The leaf
# stays stdlib-only and off these types. PLAN_QUOTA and any
# ClaudeFailureKind not listed — AUTH, CONTEXT_OVERFLOW, TIMEOUT,
# UNKNOWN_NONZERO — are TERMINAL. ASK maps to its own RecoveryAction:
# collapsing it onto WAIT is what made every `wait` run prompt on a TTY and
# left `ask` selecting nothing.
KIND_TO_CATEGORY = {
    ClaudeFailureKind.SUCCESS: AttemptCategory.SUCCESS,
    ClaudeFailureKind.RATE_LIMIT: AttemptCategory.RATE_LIMIT,
    ClaudeFailureKind.TRANSIENT: AttemptCategory.TRANSIENT,
    ClaudeFailureKind.PLAN_QUOTA: AttemptCategory.TERMINAL,
}
ACTION_TO_RECOVERY = {
    OnRateLimitAction.WAIT: RecoveryAction.WAIT,
    OnRateLimitAction.ASK: RecoveryAction.ASK,
    OnRateLimitAction.SWITCH: RecoveryAction.SWITCH,
    OnRateLimitAction.STOP: RecoveryAction.STOP,
}


def build_classification(
    rc: int,
    payload,
    stderr: str,
    *,
    empty_response_is_failure: bool = True,
) -> AttemptClassification:
    """Classify one attempt's ``(rc, payload, stderr)`` into the loop's neutral
    :class:`AttemptClassification`. Shared by both rate_limit_loop callers so the
    mapping can't drift (BACKLOG #101); the callers only unpack their own outcome
    tuple onto it. ``empty_response_is_failure`` is true for request/response
    callers, but false for streaming implementation calls whose useful result
    can be entirely in workspace edits."""
    failure = classify(
        rc,
        payload,
        stderr,
        empty_response_is_failure=empty_response_is_failure,
    )
    return AttemptClassification(
        category=KIND_TO_CATEGORY.get(failure.kind, AttemptCategory.TERMINAL),
        rc=rc,
        payload=payload,
        reset_epoch=failure.reset_epoch,
        hint=format_user_hint(failure),
        failure=failure,
    )


def build_classification_from_outcome(outcome) -> AttemptClassification:
    """Classify a text-expecting ``(rc, payload, stderr)`` attempt outcome."""
    return build_classification(*outcome)


def build_streaming_classification_from_outcome(outcome) -> AttemptClassification:
    """Classify a streaming attempt whose successful work may have no text.

    ``plan-tool run`` accepts an empty final message when the backend completed
    the requested workspace edits. Request/response callers use
    :func:`build_classification_from_outcome` instead and retry that suspicious
    empty result.
    """
    return build_classification(*outcome, empty_response_is_failure=False)


def make_wait_seam(sleep, clock):
    """Build the loop's ``wait`` seam for a caller, binding its ``sleep`` /
    ``clock`` test seams. The returned ``wait(target)`` waits until the reset
    epoch and reports whether to retry (vs stop). A factory so the seam body
    lives once, not as a verbatim per-caller closure (BACKLOG #101)."""

    def wait_seam(target: int) -> bool:
        return wait_until_epoch(target, sleep=sleep, clock=clock).action is (
            WaitUntilAction.RETRY
        )

    return wait_seam


def make_backend_recovery_wait_seam(
    sleep: Callable[[float], None],
    clock: Callable[[], float],
    *,
    writer: "Callable[[], Optional[RunLogWriter]]",
    next_attempt: Callable[[], int],
    backend_name: Callable[[], str],
    phase: str,
) -> Callable[[int], bool]:
    """Build the loop's ``wait`` seam with ``backend_recovery_wait`` /
    ``run_interrupted`` observability layered on top of
    :func:`wait_until_epoch`.

    Same translation of ``WaitUntilResult`` to the loop's ``bool``
    contract as :func:`make_wait_seam`, plus two emissions whenever
    ``writer()`` resolves non-``None``: one ``backend_recovery_wait`` row
    before the wait blocks, and one ``run_interrupted`` row if the wait is
    cut short by a ``KeyboardInterrupt`` (via ``wait_until_epoch``'s
    ``on_interrupt`` hook — the interrupt is caught three frames down
    inside that function, so it can't be observed by wrapping this
    seam's own call in a ``try``/``except``).

    Calls ``wait_until_epoch`` directly rather than delegating to
    :func:`make_wait_seam`, which has no way to pass ``on_interrupt``.
    ``writer``, ``next_attempt``, and ``backend_name`` are all
    zero-argument accessors read fresh on every call — not resolved once
    at seam-construction time — so a caller whose attempt counter
    advances on a switch/ask-switch path (which never calls this seam)
    still reports the correct upcoming attempt on its next wait.
    """

    def wait_seam(target: int) -> bool:
        log = writer()
        on_interrupt: Optional[Callable[[], None]] = None
        if log is not None:
            upcoming = next_attempt()
            delay_ms = max(0, int((target - clock()) * 1000))
            log.backend_recovery_wait(
                phase=phase,
                attempt=upcoming - 1,
                reason="rate_limit",
                delay_ms=delay_ms,
                next_attempt=upcoming,
                backend=backend_name(),
            )

            def _on_interrupt() -> None:
                log.run_interrupted(
                    phase=phase,
                    attempt=upcoming - 1,
                    source=InterruptSource.RECOVERY_WAIT.value,
                )

            on_interrupt = _on_interrupt

        result = wait_until_epoch(
            target, sleep=sleep, clock=clock, on_interrupt=on_interrupt
        )
        return result.action is WaitUntilAction.RETRY

    return wait_seam


def make_backend_recovery_sleep_seam(
    sleep: Callable[[float], None],
    *,
    writer: "Callable[[], Optional[RunLogWriter]]",
    next_attempt: Callable[[], int],
    backend_name: Callable[[], str],
    phase: str,
) -> Callable[[float], None]:
    """Build the loop's transient ``sleep`` seam with
    ``backend_recovery_wait`` / ``run_interrupted`` observability.

    Unlike the rate-limit wait, the transient path calls the injected
    ``sleep`` callable directly with no intervening wait loop — a
    ``KeyboardInterrupt`` raised out of it is caught right here, not
    three frames down, so this wrapper needs its own ``try``/``except``
    (the rate-limit seam above instead threads an ``on_interrupt`` hook
    through ``wait_until_epoch``, since that function already catches
    and would otherwise swallow the exception itself).
    """

    def sleep_seam(delay: float) -> None:
        log = writer()
        upcoming = next_attempt() if log is not None else None
        if log is not None:
            log.backend_recovery_wait(
                phase=phase,
                attempt=upcoming - 1,
                reason="transient",
                delay_ms=int(delay * 1000),
                next_attempt=upcoming,
                backend=backend_name(),
            )
        try:
            sleep(delay)
        except KeyboardInterrupt:
            if log is not None:
                log.run_interrupted(
                    phase=phase,
                    attempt=upcoming - 1,
                    source=InterruptSource.RECOVERY_WAIT.value,
                )
            raise

    return sleep_seam


@dataclass(frozen=True)
class ClaudeFailure:
    """Classifier output: kind plus any context the caller needs to recover."""

    kind: ClaudeFailureKind
    # Unix epoch when a recoverable rate limit is expected to reset. None for
    # terminal outcomes, including plan quotas, and messages without a
    # parseable short-limit time.
    # The caller is expected to fall back to a sensible default wait
    # (typically ~3600s) when this is None on a RATE_LIMIT.
    reset_epoch: Optional[int] = None
    # Short, human-readable reason. Already truncated for terminal display.
    hint: str = ""
    # Provider-confirmed monthly plan-quota reset date. The date is context
    # only and never becomes a local reset instant.
    plan_quota_reset_date: Optional[date] = None
    # A near miss for a provider's plan-quota pattern. Observational only: it
    # never changes the current classification.
    plan_quota_pattern_miss: Optional["PlanQuotaPatternMiss"] = None


@dataclass(frozen=True)
class PlanQuotaPatternMiss:
    """Redacted evidence for a likely provider banner wording change."""

    backend: str
    markers: tuple[str, ...]
    excerpt: str


@dataclass(frozen=True)
class OnRateLimitPolicy:
    """Process-wide default for handling backend rate limits."""

    action: OnRateLimitAction = OnRateLimitAction.WAIT
    fallback_backend: Optional[str] = None


@dataclass(frozen=True)
class OnRateLimitAskResult:
    """Interactive rate-limit choice, including the chosen switch target."""

    action: OnRateLimitAction
    switch_backend_name: Optional[str] = None

    def __post_init__(self) -> None:
        if (
            self.action is OnRateLimitAction.SWITCH
            and not self.switch_backend_name
        ):
            raise ValueError("switch_backend_name is required for switch")
        if (
            self.action is not OnRateLimitAction.SWITCH
            and self.switch_backend_name is not None
        ):
            raise ValueError("switch_backend_name is only valid for switch")


@dataclass(frozen=True)
class WaitUntilResult:
    """Result of waiting for a reset epoch, naming the caller's next action."""

    action: WaitUntilAction

    def __bool__(self) -> bool:
        """Compatibility for older callers that treated the result as a bool."""
        return self.action is WaitUntilAction.RETRY


WaitUntilKeyCheck = Callable[
    [], Optional[Union[WaitUntilAction, WaitUntilResult, str]]
]
ResumeCommandProvider = Callable[[], Optional[str]]
RateLimitInput = Callable[[str], str]


_resume_command_provider: ContextVar[Optional[ResumeCommandProvider]] = (
    ContextVar("plan_tool_rate_limit_resume_command_provider", default=None)
)


# The rate-limit / context-overflow / transient regexes now live on the
# active :class:`~plan_tool.backend.CliBackend` (see ``CLAUDE_BACKEND``).
# ``classify`` reads them off ``get_active_backend()`` so a second backend
# supplies its own copy detection without editing this module's control
# flow. Everything else here — reset-time parsing, the hint strings — is
# generic and stays put.

_PLAN_QUOTA_MISS_MARKERS = (
    ("action-required-error", re.compile(r"\bActionRequiredError\b", re.I)),
    ("usage-limit", re.compile(r"\busage limits?\b", re.I)),
    (
        "switch-model",
        re.compile(
            r"\bswitch(?:ing)? (?:to )?(?:(?:a )?different )?models?\b", re.I
        ),
    ),
    ("spend-limit", re.compile(r"\bspend limit\b", re.I)),
    ("monthly-cycle", re.compile(r"\bmonthly cycle\b", re.I)),
)
# ``shell._MISSED_LIMIT_CANARY`` remains the generic UNKNOWN_NONZERO
# tripwire; its caller suppresses it when this Cursor-specific detector fires.


def _plan_quota_pattern_miss(backend, combined: str) -> Optional[PlanQuotaPatternMiss]:
    """Return a redacted near-miss record for an observed quota banner."""
    if backend.plan_quota_pattern is None:
        return None
    matches = [
        (name, pattern.search(combined))
        for name, pattern in _PLAN_QUOTA_MISS_MARKERS
    ]
    markers = tuple(name for name, match in matches if match is not None)
    if len(markers) < 2 or not {"spend-limit", "monthly-cycle"}.intersection(
        markers
    ):
        return None

    # Only candidate banners pay the full redaction cost. Re-scan after it so
    # the excerpt is still always sliced from redacted text.
    redacted_combined = redact_sensitive_text(combined)
    matches = [
        (name, pattern.search(redacted_combined))
        for name, pattern in _PLAN_QUOTA_MISS_MARKERS
    ]
    markers = tuple(name for name, match in matches if match is not None)
    if len(markers) < 2 or not {"spend-limit", "monthly-cycle"}.intersection(
        markers
    ):
        return None
    first_match = min(
        (match for _name, match in matches if match is not None),
        key=lambda match: match.start(),
    )
    start = max(0, first_match.start() - 160)
    excerpt = re.sub(
        r"\s+", " ", redacted_combined[start : first_match.start() + 320]
    ).strip()
    return PlanQuotaPatternMiss(backend.name, markers, excerpt)


def observe_plan_quota_pattern_miss(
    failure: ClaudeFailure,
    *,
    repo_root: Optional[Path],
    phase: str,
    notify: Callable[..., None],
) -> bool:
    """Persist and surface one terminal provider quota-banner near miss."""
    miss = failure.plan_quota_pattern_miss
    if miss is None:
        return False
    if repo_root is not None:
        try:
            record_backend_pattern_miss(
                repo_root,
                plan_slug="",
                backend=miss.backend,
                classified_as=failure.kind.value,
                markers=miss.markers,
                excerpt=miss.excerpt,
                phase=phase,
            )
        except Exception:  # noqa: BLE001 — observational logging only
            pass
        message = (
            f"possible {miss.backend} monthly-plan-quota banner drift: "
            f"classified as {failure.kind.value}, not a terminal plan quota; "
            "recorded a redacted excerpt in .plan-tool/telemetry/decisions.jsonl"
        )
    else:
        message = (
            f"possible {miss.backend} monthly-plan-quota banner drift: "
            f"classified as {failure.kind.value}, not a terminal plan quota; "
            f"redacted excerpt: {miss.excerpt}"
        )
    notify(message, kind="info")
    return True


def make_plan_quota_pattern_miss_observer(
    *,
    repo_root: Callable[[], Optional[Path]],
    phase: str,
    notify: Callable[..., None],
) -> Callable[..., bool]:
    """Build the shared terminal-only quota-banner observer seam."""

    def observer(
        _outcome,
        failure: ClaudeFailure,
        will_retry: bool,
        _recovery_reinvoke_predicted: bool,
    ) -> bool:
        if will_retry:
            return False
        return observe_plan_quota_pattern_miss(
            failure,
            repo_root=repo_root(),
            phase=phase,
            notify=notify,
        )

    return observer


def classify(
    rc: int,
    stdout: str,
    stderr: str,
    *,
    empty_response_is_failure: bool = True,
) -> ClaudeFailure:
    """Bucket a claude subprocess outcome.

    ``BACKEND_TIMEOUT_SENTINEL`` on stderr is checked first and yields
    terminal :data:`ClaudeFailureKind.TIMEOUT`. A provider-confirmed monthly
    plan quota outranks a generic rate limit. The remaining priority is
    RATE_LIMIT > AUTH > CONTEXT_OVERFLOW > TRANSIENT > UNKNOWN_NONZERO.
    Rate-limit wins over transient when a request both 429s and also
    carries a reset time — waiting until the explicit reset is more
    accurate than a generic backoff. AUTH ranks below RATE_LIMIT (an
    auth-expired message that also 429s should still wait) but above the
    rest, and only fires when the active backend supplies an
    ``auth_pattern``.

    Returns ``SUCCESS`` with no hint when ``rc == 0`` and stdout contains a
    non-whitespace response; a successful body that happens to mention "rate
    limit" (e.g. a step about rate limiting) is not a failure. By default an
    empty stdout despite ``rc == 0`` is a retryable transport/protocol failure.
    Streaming implementation callers can opt out because their result may be
    wholly expressed as workspace edits.
    """
    if rc == 0:
        if empty_response_is_failure and not stdout.strip():
            return ClaudeFailure(
                kind=ClaudeFailureKind.TRANSIENT,
                hint="backend exited successfully but returned an empty response",
            )
        return ClaudeFailure(kind=ClaudeFailureKind.SUCCESS)

    # A call killed by the scoped/env timeout is terminal under the same
    # budget: retrying almost always burns another full wait for another empty
    # kill. Checked before backend patterns — the synthetic stderr carries no
    # provider text to match. Network blips still route via transient_pattern.
    if BACKEND_TIMEOUT_SENTINEL in stderr:
        return ClaudeFailure(
            kind=ClaudeFailureKind.TIMEOUT,
            hint="backend call timed out; not retrying under the same budget",
        )

    backend = get_active_backend()
    combined = f"{stdout}\n{stderr}"

    # A provider-confirmed monthly quota is terminal even when its copy lacks
    # the generic rate-limit vocabulary used for recoverable limits.
    if (
        backend.plan_quota_pattern is not None
        and backend.plan_quota_pattern.search(combined) is not None
    ):
        return ClaudeFailure(
            kind=ClaudeFailureKind.PLAN_QUOTA,
            hint=f"{backend.name} monthly plan quota reached",
            plan_quota_reset_date=parse_plan_quota_reset_date(combined),
        )

    plan_quota_pattern_miss = _plan_quota_pattern_miss(backend, combined)

    def _failure_with_pattern_miss(**kwargs) -> ClaudeFailure:
        return ClaudeFailure(
            plan_quota_pattern_miss=plan_quota_pattern_miss, **kwargs
        )

    # Rate limit (Claude- or Codex-style copy) takes precedence over the
    # remaining non-terminal classifications.
    if backend.provider_limit_pattern.search(
        combined
    ) or backend.rate_limit_pattern.search(combined):

        epoch = parse_reset_epoch(combined)
        if epoch is not None:
            hint_time = _format_local_hhmm(epoch)
            hint = f"{backend.name} rate limit reached; reset at {hint_time}"
        else:
            hint = f"{backend.name} rate limit reached; no reset time found in output"
        return _failure_with_pattern_miss(
            kind=ClaudeFailureKind.RATE_LIMIT,
            reset_epoch=epoch,
            hint=hint,
        )

    # Auth failure (codex's missing/invalid credentials). Backend-gated:
    # only fires when the active backend defines an ``auth_pattern``, so
    # claude (which has none today) is unaffected. Not retried/waited —
    # falls through to the surface-and-return arm like CONTEXT_OVERFLOW.
    if (
        backend.auth_pattern is not None
        and backend.auth_pattern.search(combined)
    ):
        return _failure_with_pattern_miss(
            kind=ClaudeFailureKind.AUTH,
            hint=f"{backend.name} not authenticated; check credentials and re-login",
        )
    if backend.context_overflow_pattern.search(combined):
        return _failure_with_pattern_miss(
            kind=ClaudeFailureKind.CONTEXT_OVERFLOW,
            hint=(
                f"{backend.name} context window exceeded; "
                "narrow the scope — a smaller --step, or split a large seed "
                "into multiple plans"
            ),
        )

    if backend.transient_pattern.search(combined):
        return _failure_with_pattern_miss(
            kind=ClaudeFailureKind.TRANSIENT,
            hint="transient failure (network or temporary 429)",
        )

    return _failure_with_pattern_miss(
        kind=ClaudeFailureKind.UNKNOWN_NONZERO,
        hint=f"{get_active_backend().name} exited with code {rc}",
    )


# Reset-epoch patterns. Order matters: the more specific "with date"
# variant must come before the bare HH:MM variant or the latter would
# eat the time portion of the former.

_RESET_PATTERNS = [
    # "try again at January 5, 2026 9:30pm" / "try again at Jan 5 9pm"
    re.compile(
        r"try again at\s+([A-Za-z]{3,9})\s+([0-9]{1,2})(?:st|nd|rd|th)?"
        r"(?:,\s*([0-9]{4}))?\s+([0-9]{1,2})(?::([0-9]{2}))?\s*([ap]m)\b",
        re.IGNORECASE,
    ),
    # "resets 3am" / "resets 3:30pm"
    re.compile(
        r"resets?\s+([0-9]{1,2})(?::([0-9]{2}))?\s*([ap]m)\b",
        re.IGNORECASE,
    ),
    # "try again at 9pm" / "try again at 9:30pm"
    re.compile(
        r"try again at\s+([0-9]{1,2})(?::([0-9]{2}))?\s*([ap]m)\b",
        re.IGNORECASE,
    ),
]

_MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

# Buffer added after the parsed reset moment. Matches the reference
# script (+120s) — covers clock skew + propagation delay between the
# rate-limit window closing and Claude actually accepting requests again.
_RESET_BUFFER_SECONDS = 120

_PLAN_QUOTA_RESET_DATE_PATTERN = re.compile(
    r"monthly cycle ends on\s+([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})\b",
    re.IGNORECASE,
)


def parse_plan_quota_reset_date(text: str) -> Optional[date]:
    """Extract Cursor's stated monthly-cycle reset date without adding a time."""
    match = _PLAN_QUOTA_RESET_DATE_PATTERN.search(text)
    if match is None:
        return None
    try:
        month, day, year = (int(value) for value in match.groups())
        return date(year=year, month=month, day=day)
    except ValueError:
        return None


def parse_reset_epoch(
    text: str,
    *,
    now: Optional[datetime] = None,
) -> Optional[int]:
    """Extract a unix epoch for when the rate limit resets.

    Ported from ``run-validation-dataset.sh:parse_reset_epoch`` (the
    inline Python heredoc). Supports three formats:

    - ``try again at <Mon> <DD>[, YYYY] <HH>[:MM]<am|pm>`` — absolute,
      year-optional (defaults to current).
    - ``resets <HH>[:MM]<am|pm>`` — local time of day; rolls forward
      one day if the parsed time is already in the past.
    - ``try again at <HH>[:MM]<am|pm>`` — local time of day; same
      forward-roll behavior.

    Returns the first match's epoch + a 120s buffer, or ``None`` when
    no pattern matches. ``now`` is injectable for deterministic tests.
    """
    if now is None:
        now = datetime.now()
    now = now.replace(second=0, microsecond=0)

    for pat in _RESET_PATTERNS:
        m = pat.search(text)
        if m is None:
            continue
        target = _parse_match(m, now)
        if target is None:
            continue
        if target <= now:
            target += timedelta(days=1)
        target += timedelta(seconds=_RESET_BUFFER_SECONDS)
        return int(target.timestamp())
    return None


def _parse_match(m: re.Match, now: datetime) -> Optional[datetime]:
    """Build a ``datetime`` from one of the three reset-pattern matches.

    Branches on group count rather than which pattern matched —
    keeps the regex-to-parser coupling loose so adding a fourth
    variant later only requires extending ``_RESET_PATTERNS``.
    """
    groups = m.groups()
    if len(groups) >= 6 and groups[0] and not groups[0].isdigit():
        # Month-name variant.
        month_raw = groups[0].lower()
        month = _MONTH_MAP.get(month_raw)
        if month is None:
            return None
        try:
            day = int(groups[1])
            year = int(groups[2] or now.year)
            hour = int(groups[3])
            minute = int(groups[4] or "00")
            ampm = groups[5].lower()
        except (TypeError, ValueError):
            return None
        hour = _to_24h(hour, ampm)
        try:
            return datetime(year=year, month=month, day=day, hour=hour, minute=minute)
        except ValueError:
            return None

    # Bare HH:MM am/pm variant.
    try:
        hour = int(groups[0])
        minute = int(groups[1] or "00")
        ampm = groups[2].lower()
    except (TypeError, ValueError):
        return None
    hour = _to_24h(hour, ampm)
    return now.replace(hour=hour, minute=minute)


def _to_24h(hour: int, ampm: str) -> int:
    """12-hour → 24-hour conversion handling the noon/midnight edges."""
    if ampm == "pm" and hour != 12:
        return hour + 12
    if ampm == "am" and hour == 12:
        return 0
    return hour


def _format_local_hhmm(epoch: int) -> str:
    """Format a unix epoch as local ``HH:MM`` for terminal display.

    Returns the bare epoch string on formatter failure rather than
    raising — the caller embeds this in a user message and a missing
    time is preferable to a crash.
    """
    try:
        return datetime.fromtimestamp(epoch).strftime("%H:%M")
    except (OSError, ValueError, OverflowError):
        return str(epoch)


# Default fallback wait when a RATE_LIMIT is detected without a
# parseable reset time. One hour matches the typical Claude window
# and is also what the reference script falls back to in practice
# (the heuristic surfaces a "no reset time found" warning).
DEFAULT_RATE_LIMIT_FALLBACK_SECONDS = 3600
# Ceiling on a *parsed* reset wait. Provider banners can carry an absolute
# date, so an unclamped parse is an unbounded, uninterruptible sleep in an
# unattended run — while the unparsed path was always bounded by the fallback
# above. 24h matches the widest self-limiting parse (the time-of-day variants
# roll forward at most one day).
MAX_RATE_LIMIT_WAIT_SECONDS = 86400

# How often to update the countdown line. The reference script uses
# 1s; we match it so the UX feels equivalent.
_COUNTDOWN_TICK_SECONDS = 1.0

# Serializes the interactive rate-limit prompt + key-polling wait across
# threads. Parallel workers (`detail --jobs N`) share
# one process-global stdin; concurrent input()/termios access from several
# threads corrupts the terminal. Both invoker seams (`shell.claude_invoke`
# and `launcher.shell_invoker`) acquire this one lock so at most one worker
# drives the terminal at a time. Single-threaded runs never contend. See
# BACKLOG #98.
RATE_LIMIT_PROMPT_LOCK = threading.Lock()


def wait_until_epoch(
    target_epoch: int,
    *,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.time,
    stream=None,
    cancel_check: Optional[Callable[[], bool]] = None,
    key_check: Optional[WaitUntilKeyCheck] = None,
    on_interrupt: Optional[Callable[[], None]] = None,
) -> WaitUntilResult:
    """Block until ``target_epoch`` with a stderr countdown.

    Returns ``WaitUntilResult(RETRY)`` when the wait completed naturally
    and the caller can retry. Returns ``WaitUntilResult(STOP)`` when the
    wait was cancelled (``cancel_check`` returning True, or a stop key from
    ``key_check`` / the TTY poll).

    ``sleep`` / ``clock`` are injectable so tests can run instantly.
    ``key_check`` is an injectable per-tick non-blocking key seam; when
    omitted, TTY stdin is polled without blocking and ``q`` / Esc /
    Ctrl+C stop the wait.
    ``stream`` defaults to ``sys.stderr`` — the countdown intentionally
    goes there so it doesn't interleave with the claude stdout stream
    in the launcher's run command.

    ``on_interrupt`` changes what a ``KeyboardInterrupt`` during the wait
    does: by default (``None``, every caller before this parameter existed)
    it is swallowed and reported as an ordinary ``WaitUntilResult(STOP)`` —
    the same "cancel this wait, fall through" meaning as pressing ``q``.
    When supplied, ``on_interrupt()`` is called first (for a caller that
    wants to record the interrupt) and the ``KeyboardInterrupt`` is then
    re-raised instead of being converted to ``STOP`` — a caller wrapping
    this in its own recovery loop can't observe the interrupt any other
    way, since it never reaches an outer frame otherwise.
    """
    if stream is None:
        stream = sys.stderr

    remaining = int(target_epoch - clock())
    if remaining <= 0:
        return WaitUntilResult(action=WaitUntilAction.RETRY)

    try:
        reset_display = datetime.fromtimestamp(target_epoch).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    except (OSError, ValueError, OverflowError):
        reset_display = str(target_epoch)

    print("", file=stream)
    tool(
        f"waiting until {reset_display} for {get_active_backend().name} quota "
        f"({remaining}s). Press q or Ctrl+C to abort.",
        stream=stream,
    )

    tty_key_check: Optional[WaitUntilKeyCheck] = None
    restore_tty = None
    if key_check is None:
        tty_key_check, restore_tty = _start_tty_keypress_poll()

    try:
        while remaining > 0:
            if cancel_check is not None and cancel_check():
                print("", file=stream)
                tool("wait cancelled.", stream=stream)
                return WaitUntilResult(action=WaitUntilAction.STOP)
            key_action = _check_wait_key(key_check or tty_key_check)
            if key_action is WaitUntilAction.STOP:
                print("", file=stream)
                tool("wait stopped.", stream=stream)
                return WaitUntilResult(action=WaitUntilAction.STOP)
            if key_action is WaitUntilAction.RETRY:
                stream.write("\r" + " " * 60 + "\r")
                stream.flush()
                tool("wait complete, retrying.", stream=stream)
                return WaitUntilResult(action=WaitUntilAction.RETRY)
            hrs = remaining // 3600
            mins = (remaining % 3600) // 60
            secs = remaining % 60
            stream.write(
                f"\rplan-tool: {hrs:02d}:{mins:02d}:{secs:02d} remaining   "
            )
            stream.flush()
            sleep(_COUNTDOWN_TICK_SECONDS)
            remaining = int(target_epoch - clock())
        stream.write("\r" + " " * 60 + "\r")
        stream.flush()
        tool("wait complete, retrying.", stream=stream)
        return WaitUntilResult(action=WaitUntilAction.RETRY)
    except KeyboardInterrupt:
        print("", file=stream)
        tool("wait interrupted.", stream=stream)
        # Re-install the default SIGINT handler in case the caller
        # swallowed the first one — second Ctrl+C should kill.
        try:
            signal.signal(signal.SIGINT, signal.default_int_handler)
        except (ValueError, OSError):
            pass
        if on_interrupt is not None:
            on_interrupt()
            raise
        return WaitUntilResult(action=WaitUntilAction.STOP)
    finally:
        if restore_tty is not None:
            restore_tty()


def _check_wait_key(
    key_check: Optional[WaitUntilKeyCheck],
) -> Optional[WaitUntilAction]:
    """Run one key check and normalize its answer to a wait action."""
    if key_check is None:
        return None
    pressed = key_check()
    if pressed is None:
        return None
    if isinstance(pressed, WaitUntilResult):
        return pressed.action
    if isinstance(pressed, WaitUntilAction):
        return pressed
    if pressed in ("\x03", "\x1b", "q", "Q", "stop"):
        return WaitUntilAction.STOP
    if pressed == "retry":
        return WaitUntilAction.RETRY
    return None


def _start_tty_keypress_poll() -> tuple[
    Optional[WaitUntilKeyCheck], Optional[Callable[[], None]]
]:
    """Put stdin in cbreak mode and return a non-blocking single-key poller."""
    if select is None or termios is None or tty is None:
        return None, None
    stdin = sys.stdin
    try:
        if not getattr(stdin, "isatty", lambda: False)():
            return None, None
        fd = stdin.fileno()
        previous_attrs = termios.tcgetattr(fd)
        tty.setcbreak(fd)
    except (AttributeError, OSError):
        return None, None

    def check() -> Optional[str]:
        try:
            ready, _, _ = select.select([stdin], [], [], 0)
            if not ready:
                return None
            return stdin.read(1)
        except OSError:
            return None

    def restore() -> None:
        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, previous_attrs)
        except OSError:
            pass

    return check, restore


def format_user_hint(failure: ClaudeFailure) -> str:
    """One-line user-facing message describing the failure.

    Stable across kinds so callers can ``print(format_user_hint(...))``
    without branching. Returns empty string on SUCCESS.
    """
    if failure.kind is ClaudeFailureKind.SUCCESS:
        return ""
    if failure.kind is ClaudeFailureKind.PLAN_QUOTA:
        if failure.plan_quota_reset_date is not None:
            return (
                f"{failure.hint}; monthly cycle resets on "
                f"{failure.plan_quota_reset_date.isoformat()}"
            )
        return failure.hint or "monthly plan quota reached"
    return failure.hint or f"claude failed: {failure.kind.value}"


def set_rate_limit_resume_command_provider(
    provider: Optional[ResumeCommandProvider],
) -> Token[Optional[ResumeCommandProvider]]:
    """Bind the command shown when the user stops on a rate limit.

    A ``ContextVar`` keeps the provider scoped to the current run/thread,
    matching the launcher and shell ContextVar plumbing. Callers that need
    strict restoration should keep the returned token and pass it to
    :func:`reset_rate_limit_resume_command_provider`.
    """
    return _resume_command_provider.set(provider)


def reset_rate_limit_resume_command_provider(
    token: Token[Optional[ResumeCommandProvider]],
) -> None:
    """Restore the previously bound resume-command provider."""
    _resume_command_provider.reset(token)


def get_rate_limit_resume_command() -> Optional[str]:
    """Return the current resume command, if one is available."""
    provider = _resume_command_provider.get()
    if provider is None:
        return None
    return provider()


def ask_on_rate_limit_action(
    *,
    current_backend_name: Optional[str] = None,
    input_fn: RateLimitInput = input,
    stream: Optional[TextIO] = None,
) -> OnRateLimitAskResult:
    """Prompt for the shared rate-limit decision: wait, backend, or stop.

    ``w`` waits for the reset and retries the same backend, ``b`` asks for a
    registered backend name to switch to, and ``s`` stops so the user can
    resume later. Backend names are validated against
    :func:`plan_tool.backend.registered_names` at prompt time so newly
    registered integrations are accepted without editing this module.

    ``input_fn`` and ``stream`` are injectable test seams; production callers
    use the defaults.
    """
    if stream is None:
        stream = sys.stderr
    if current_backend_name is None:
        current_backend_name = get_active_backend().name

    resume_command = get_rate_limit_resume_command()
    tool(
        f"{current_backend_name} hit a rate limit. "
        "Choose (w)ait, switch (b)ackend, or (s)top.",
        stream=stream,
    )
    if resume_command:
        tool(f"resume later with: {resume_command}", stream=stream)

    while True:
        try:
            choice = input_fn("rate limit [w/b/s]: ").strip().lower()
        except EOFError:
            return OnRateLimitAskResult(action=OnRateLimitAction.STOP)

        if choice in ("", "w", "wait"):
            return OnRateLimitAskResult(action=OnRateLimitAction.WAIT)
        if choice in ("s", "stop", "save", "q", "quit"):
            return OnRateLimitAskResult(action=OnRateLimitAction.STOP)
        if choice in ("b", "backend", "switch"):
            return _ask_switch_backend(input_fn=input_fn, stream=stream)
        tool("please choose w, b, or s.", stream=stream)


def _ask_switch_backend(
    *,
    input_fn: RateLimitInput,
    stream: TextIO,
) -> OnRateLimitAskResult:
    """Prompt until the operator names a registered backend."""
    from plan_tool.backend import registered_names

    names = registered_names()
    choices = ", ".join(sorted(names))
    while True:
        try:
            name = input_fn("backend name: ").strip()
        except EOFError:
            return OnRateLimitAskResult(action=OnRateLimitAction.STOP)
        if name in names:
            return OnRateLimitAskResult(
                action=OnRateLimitAction.SWITCH,
                switch_backend_name=name,
            )
        if not name:
            tool(f"please enter a backend name ({choices}).", stream=stream)
            continue
        tool(
            f"unknown backend {name!r}; registered: {choices}",
            stream=stream,
        )


# Process-wide default for how claude invokers should handle rate limits.
# Set once by ``cli.main`` from the resolved ``--on-rate-limit`` /
# ``--fallback-backend`` policy. Both ``shell.claude_invoke`` and
# ``launcher.shell_invoker`` read this whole policy (action + fallback
# backend) via ``resolve_on_rate_limit_policy`` when their per-call kwarg
# isn't explicitly set. Module-level rather than threaded through every
# entry point because the policy is a user-level preference for the entire
# CLI invocation, not a per-call decision.
_default_on_rate_limit_policy = OnRateLimitPolicy()


def set_default_wait_on_rate_limit(value: bool) -> None:
    """Legacy boolean view of the process-wide default: ``True`` → WAIT,
    ``False`` → STOP. ``cli.main`` sets the full policy through
    :func:`set_default_on_rate_limit_policy`; this narrower pair has no
    production caller and is kept as the boolean shim matching the invokers'
    per-call ``wait_on_rate_limit`` kwarg (see
    :func:`resolve_on_rate_limit_policy`)."""
    action = OnRateLimitAction.WAIT if value else OnRateLimitAction.STOP
    set_default_on_rate_limit_policy(OnRateLimitPolicy(action=action))


def get_default_wait_on_rate_limit() -> bool:
    """Legacy boolean read of the process-wide default — ``True`` only for
    WAIT, so SWITCH and ASK both read as ``False``. See
    :func:`set_default_wait_on_rate_limit` for why this pair is retained."""
    return get_default_on_rate_limit_policy().action is OnRateLimitAction.WAIT


def set_default_on_rate_limit_policy(policy: OnRateLimitPolicy) -> None:
    """Override the process-wide on-rate-limit policy."""
    global _default_on_rate_limit_policy
    _default_on_rate_limit_policy = policy


def get_default_on_rate_limit_policy() -> OnRateLimitPolicy:
    """Read the process-wide on-rate-limit policy."""
    return _default_on_rate_limit_policy


def resolve_on_rate_limit_policy(
    wait_on_rate_limit: Optional[bool],
) -> OnRateLimitPolicy:
    """Resolve an invoker's per-call ``wait_on_rate_limit`` kwarg to a policy.

    ``None`` → the process-wide default (set by ``cli.main`` from
    ``--on-rate-limit`` / env), so the full SWITCH/ASK/fallback policy
    reaches the invoker. The boolean is the legacy per-call seam and maps
    exactly like :func:`set_default_wait_on_rate_limit`: ``True`` → WAIT,
    ``False`` → STOP. Keeping this the single resolver means both invokers
    agree on what a bare boolean means.
    """
    if wait_on_rate_limit is None:
        return get_default_on_rate_limit_policy()
    action = OnRateLimitAction.WAIT if wait_on_rate_limit else OnRateLimitAction.STOP
    return OnRateLimitPolicy(action=action)
