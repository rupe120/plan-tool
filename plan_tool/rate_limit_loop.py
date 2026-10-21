"""Shared rate-limit / transient recovery loop (stdlib-only leaf).

The 429-detect / wait-or-switch / transient-backoff control flow shared by
``shell.claude_invoke`` (batch) and ``launcher.shell_invoker`` (streaming)
lives here once so the two can't diverge (BACKLOG #101). Design is
**inject-don't-unify**: every caller-specific concern is an injected seam, so
the leaf stays stdlib-only with no ``plan_tool`` import and never touches the
first-party types (``ClaudeFailureKind``, ``OnRateLimitAction``, …) — each
caller maps those onto the local :class:`AttemptCategory` / :class:`RecoveryAction`.

See ``docs/how-to/pipeline/run.md`` for the seam-by-seam contract.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, ContextManager, Optional, Tuple


class AttemptCategory(str, Enum):
    """Loop-legible failure buckets. Each caller maps its own
    ``ClaudeFailureKind`` onto these so the leaf stays off that type.

    ``TERMINAL`` collapses every non-retryable outcome (including a
    provider-confirmed plan quota, context overflow, unknown non-zero, and
    auth): surface the hint and return without invoking a recovery seam.
    """

    SUCCESS = "success"
    RATE_LIMIT = "rate_limit"
    TRANSIENT = "transient"
    TERMINAL = "terminal"


class RecoveryAction(str, Enum):
    """Neutral wait-vs-switch vocabulary. The caller narrows its
    first-party ``OnRateLimitAction`` (policy action *and* the ASK menu's
    return) onto these so the leaf never imports that enum.

    ``ASK`` is the policy value only — the interactive menu's *return* is
    always one of ``WAIT`` / ``SWITCH`` / ``STOP``, never ``ASK``. Keeping it
    distinct from ``WAIT`` is what makes ``wait`` non-interactive: collapsing
    the two made every ``wait`` run prompt on a TTY and left ``ask`` with
    nothing to select.
    """

    WAIT = "wait"
    ASK = "ask"
    SWITCH = "switch"
    STOP = "stop"


class RetryPolicy(str, Enum):
    """Whether the injected ``retry_guard`` lets the loop re-drive ``run_once``.

    ``RETRY`` proceeds with the re-invoke (today's unconditional behavior);
    ``STOP`` refuses it — the loop surfaces a hint and returns the just-failed
    attempt as terminal. There is deliberately no ``RESTORE``: the leaf is
    stdlib-only and cannot restore a working tree, so any snapshot-restore
    recovery must live in a caller that has git and still returns ``RETRY``
    from here — the leaf contract stays ``RETRY`` / ``STOP``.
    """

    RETRY = "retry"
    STOP = "stop"


@dataclass(frozen=True)
class RetryDecision:
    """What the injected ``retry_guard`` yields when a re-invoke is predicted.

    ``hint`` carries the caller-authored partial-mutation message (the leaf is
    caller-agnostic and can't author it) surfaced on the ``STOP`` branch.
    """

    policy: RetryPolicy
    hint: str = ""


# Default decision: retry as today. A module-level singleton so the no-guard
# path allocates nothing.
ALWAYS_RETRY = RetryDecision(RetryPolicy.RETRY)


@dataclass(frozen=True)
class AttemptClassification:
    """What ``classify`` yields for one attempt's opaque outcome.

    Everything the loop branches on, plus the caller's ``failure`` object
    carried through untouched to ``on_nonsuccess`` (the loop never inspects
    it — doing so would need a first-party type).
    """

    category: AttemptCategory
    rc: int
    payload: Any
    reset_epoch: Optional[int] = None
    # Pre-formatted user-facing hint (the caller's ``format_user_hint``).
    hint: str = ""
    failure: Any = None


def run_with_rate_limit_recovery(
    *,
    run_once: Callable[[int], Any],
    classify: Callable[[Any], AttemptClassification],
    notify: Callable[..., None],
    select_backend: Callable[[str], bool],
    ask_action: Callable[[], RecoveryAction],
    can_prompt: Callable[[], bool],
    wait: Callable[[int], bool],
    prompt_lock: ContextManager[Any],
    current_backend_name: Callable[[], str],
    recover_rate_limit: bool,
    action: RecoveryAction,
    fallback_backend: Optional[str],
    fallback_seconds: int,
    max_wait_seconds: int,
    max_transient_retries: int,
    transient_base_delay: float,
    attempt: int = 1,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.time,
    on_nonsuccess: Optional[Callable[[Any, Any, bool, bool], None]] = None,
    retry_guard: Optional[Callable[[Any], RetryDecision]] = None,
) -> Tuple[int, Any]:
    """Drive the shared 429 / transient recovery cascade and return ``(rc, payload)``.

    Owns only the control flow identical across both callers (one-shot
    rate-limit guard, SWITCH / ASK / wait fork, transient backoff, honoring
    ``wait``'s RETRY result); every caller-specific piece is an injected seam.
    Two non-obvious contracts: ``select_backend`` fires **only** on the
    auto-SWITCH path (ASK-switch swaps internally), and ``on_nonsuccess``'s
    ``will_retry`` says this failure will re-invoke ``run_once`` while its
    fourth argument preserves the pre-guard recovery candidate.
    See ``docs/how-to/pipeline/run.md`` for the seam-by-seam contract.
    """
    current_attempt = attempt
    transient_attempts = 0
    rate_limit_retried = False

    while True:
        outcome = run_once(current_attempt)
        result = classify(outcome)

        if result.category is AttemptCategory.SUCCESS:
            return result.rc, result.payload

        # These identify the arms that might re-invoke ``run_once``. The guard
        # and a rate-limit recovery choice can still make this terminal.
        will_retry_rate_limit = (
            result.category is AttemptCategory.RATE_LIMIT
            and recover_rate_limit
            and not rate_limit_retried
        )
        will_retry_transient = (
            result.category is AttemptCategory.TRANSIENT
            and transient_attempts + 1 < max_transient_retries
        )

        retry_candidate = will_retry_rate_limit or will_retry_transient

        def _notify_nonsuccess(will_retry: bool) -> None:
            if on_nonsuccess is not None:
                on_nonsuccess(
                    outcome, result.failure, will_retry, retry_candidate
                )

        # One retry-guard consult covers every re-invoke arm. Gating on the
        # already-computed prediction that a re-invoke is coming — and placing
        # it before the recovery arms — means a single check governs the
        # transient backoff *and* the rate-limit wait / switch / ASK-switch
        # paths (all of which loop back to the same ``run_once``), and it
        # refuses *before* paying any backoff or (potentially long) wait. The
        # leaf can't inspect the tree, so the STOP decision is injected: on a
        # partially-mutated tree the caller returns STOP to stop a re-drive
        # that would double-apply the aborted turn's edits. Default preserves
        # today's unconditional retry.
        if retry_candidate:
            decision = (
                retry_guard(outcome) if retry_guard is not None else ALWAYS_RETRY
            )
            if decision.policy is RetryPolicy.STOP:
                _notify_nonsuccess(False)
                notify(decision.hint or result.hint, kind="info")
                return result.rc, result.payload

        if result.category is AttemptCategory.RATE_LIMIT and recover_rate_limit:
            if rate_limit_retried:
                # Already waited once and hit it again — surface and bail
                # rather than loop indefinitely.
                _notify_nonsuccess(False)
                notify(
                    f"{result.hint} (already retried once)", kind="info"
                )
                return result.rc, result.payload
            # The SWITCH swap, the ASK prompt, and the wait all touch
            # invoke-scoped backend state / stdin; hold the lock across all
            # three so at most one worker drives the terminal at a time.
            with prompt_lock:
                # SWITCH: consume the configured fallback backend without a
                # prompt. On success retry on it (resetting the guard +
                # transient counter); on a failed/absent swap degrade to
                # waiting. Switching to the *already-active* backend is a
                # no-op that also degrades to a wait — otherwise a fallback
                # naming the current backend would reset the one-shot guard
                # forever and hot-loop the limit with no backoff.
                if action is RecoveryAction.SWITCH:
                    # Case-normalized: a case-mismatched fallback naming the
                    # active backend now resolves cleanly (model-family
                    # inference), so an exact-string compare would miss it
                    # and hot-loop per the comment above.
                    already_active = (
                        fallback_backend is not None
                        and fallback_backend.strip().lower()
                        == current_backend_name().lower()
                    )
                    if (
                        fallback_backend
                        and not already_active
                        and select_backend(fallback_backend)
                    ):
                        _notify_nonsuccess(True)
                        rate_limit_retried = False
                        transient_attempts = 0
                        current_attempt += 1
                        continue
                    notify(
                        f"fallback backend {fallback_backend!r} is already "
                        "active; waiting for reset instead"
                        if already_active
                        else "could not switch to fallback backend "
                        f"{fallback_backend!r}; waiting instead",
                        kind="info",
                    )
                # ASK: offer the interactive menu when a TTY is present,
                # otherwise fall through to waiting. WAIT never prompts — it is
                # the documented unattended "sleep until reset and retry".
                # (SWITCH reaches here only after a failed swap, and takes the
                # wait path.)
                elif action is RecoveryAction.ASK and can_prompt():
                    chosen = ask_action()
                    if chosen is RecoveryAction.STOP:
                        _notify_nonsuccess(False)
                        return result.rc, result.payload
                    if chosen is RecoveryAction.SWITCH:
                        # ask_action already performed the swap internally;
                        # just reset and retry (re-selecting would double-switch).
                        _notify_nonsuccess(True)
                        rate_limit_retried = False
                        transient_attempts = 0
                        current_attempt += 1
                        continue
                target = result.reset_epoch
                if target is None:
                    target = int(clock()) + fallback_seconds
                    notify(
                        f"no reset time in {current_backend_name()} output; "
                        f"waiting {fallback_seconds}s as fallback",
                        kind="info",
                    )
                else:
                    notify(f"{result.hint}", kind="info")
                # A parsed reset time is provider text, so cap it: without this
                # an absolute far-future date (or a misparse) becomes an
                # unbounded sleep that an unattended run cannot escape, while
                # the *unparsed* path was already bounded by fallback_seconds.
                # On a capped wait the retry lands before the real reset and
                # the one-shot guard then stops — better than sleeping for
                # months.
                ceiling = int(clock()) + max_wait_seconds
                if target > ceiling:
                    notify(
                        f"reset time is beyond the {max_wait_seconds}s cap; "
                        f"waiting {max_wait_seconds}s and retrying once",
                        kind="info",
                    )
                    target = ceiling
                if not wait(target):
                    _notify_nonsuccess(False)
                    return result.rc, result.payload
                _notify_nonsuccess(True)
                rate_limit_retried = True
                current_attempt += 1
                continue

        if will_retry_transient:
            _notify_nonsuccess(True)
            delay = transient_base_delay * (2 ** transient_attempts)
            notify(
                f"{result.hint}; "
                f"retry {transient_attempts + 1}/"
                f"{max_transient_retries - 1} in {delay:.0f}s",
                kind="retry",
            )
            sleep(delay)
            transient_attempts += 1
            current_attempt += 1
            continue

        # TERMINAL outcomes, rate-limit-with-recovery-disabled, or transient
        # past its budget — surface the hint and return.
        _notify_nonsuccess(False)
        notify(f"{result.hint}", kind="info")
        return result.rc, result.payload
