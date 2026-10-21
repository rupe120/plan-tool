"""Shared shell invocation of the ``claude`` CLI.

Several modules (``create``, ``review``, ``jira``, ``detail``) shell out
to ``claude -p`` with identical flags and identical fallback semantics
(missing executable → exit 127 with ``""`` stdout; non-zero exit logs
stderr to the user). Keeping that recipe in one place avoids drift —
e.g. when one module added a `shutil.which` guard and the others didn't,
``create.py`` would raise ``FileNotFoundError`` while the rest returned
``""``.

Public surface:

- :func:`claude_invoke` — returns ``(exit_code, stdout)``. Used directly
  by ``review.shell_review_invoker`` (which surfaces the exit code so the
  semantic-review section can distinguish "claude not on PATH" from
  "claude returned empty").
- :func:`claude_invoke_outcome` — retains the final classified failure for
  callers that need terminal recovery context without parsing output again.
- The ``stdout``-only invokers (``shell_jira_invoker``,
  ``shell_detail_invoker``, ``shell_concept_invoker``,
  ``create.shell_claude_invoker``) wrap this
  function and discard the exit code.

Failure recovery:

When ``claude -p`` exits non-zero, the result is classified via
:mod:`plan_tool.claude_errors` and the call may be retried:

- ``RATE_LIMIT`` — handled per the resolved
  :class:`~plan_tool.claude_errors.OnRateLimitPolicy`: ``STOP`` skips
  recovery; ``SWITCH`` scopes the configured fallback backend to the
  current batch invoke and retries; ``ASK`` asks (when interactive) whether
  to wait, switch backend, or stop; ``WAIT`` — and ``ASK`` with no TTY —
  waits until the parsed reset epoch (or
  :data:`claude_errors.DEFAULT_RATE_LIMIT_FALLBACK_SECONDS` if no time is
  found, capped either way at
  :data:`claude_errors.MAX_RATE_LIMIT_WAIT_SECONDS`) and retries once.
- ``TRANSIENT`` — exponential backoff (``transient_base_delay`` doubled
  per attempt up to ``max_transient_retries``).
- ``PLAN_QUOTA`` — terminal; surfaces the monthly reset date as date-only
  context and bypasses wait, prompt, switch, and retry recovery.
- ``CONTEXT_OVERFLOW`` — no retry; the caller gets a clear hint to
  narrow scope (smaller ``--step``, or split a large seed into plans).
- ``UNKNOWN_NONZERO`` — no retry; preserves the historical
  "print stderr tail and return ``(rc, stdout)``" behavior.

Each attempt emits one :class:`~plan_tool.run_log.ClaudeCallEnd` event
to the active sink so the run log shows retries as distinct rows.

Run-log sink:

- :data:`MetaSink` — the callable type accepted by
  :func:`set_active_sink`. Implementations receive one
  :class:`plan_tool.run_log.ClaudeCallEnd` event per call to
  :func:`claude_invoke` (when a sink is installed) and are expected to
  forward it to the current run's JSONL via ``run_log.append_event``.
- :func:`set_active_sink` / :func:`get_active_sink` — install / read the
  per-process sink. Higher-level entry points (``cli.cmd_create`` in
  step 3, ``cli.cmd_detail`` in step 4, ``cli.cmd_run`` in step 5) bind
  a closure that substitutes the current run id into the event and
  call ``append_event``; they then clear the sink in a ``finally:``
  block. With no sink installed, :func:`claude_invoke` is a pure
  ``(rc, stdout)`` function — the historical behavior.

:func:`claude_invoke` records wall-clock duration (via
``time.monotonic``) and stdout/prompt byte counts on every call that
actually reaches the subprocess. Token / cache / cost / request-id
capture is deferred to a follow-up plan that swaps in
``--output-format json`` with envelope-unwrap handling for the
downstream parsers; the corresponding ``ClaudeCallEnd`` fields land as
``None`` until then. When the executable is missing from PATH no
subprocess runs and no event is emitted (preserves the historical
``(127, "")`` fast-path).
"""

from __future__ import annotations

import contextvars
import contextlib
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    # Structural type only — imported under TYPE_CHECKING so the runtime
    # import stays one-directional (``progress`` imports ``shell``, never
    # the reverse). ``claude_invoke`` duck-types the ``.notice`` call.
    from plan_tool.progress import SupportsNotice
    from plan_tool.backend import ClaudeRunStats
    from plan_tool.run_log import RunLogWriter

from plan_tool import backend_runner
from plan_tool import model_specs
from plan_tool.backend import (
    provisional_backend_warning,
    get_active_backend,
    get_active_spawn_cwd,
    registered_names,
    scoped_active_backend,
    scoped_select_active_backend,
    spawn_cwd,
    structural_codex_backend,
    unknown_backend_override_warning,
)
from plan_tool.backend_config import BackendConfigError
from plan_tool.claude_errors import (
    ACTION_TO_RECOVERY,
    DEFAULT_RATE_LIMIT_FALLBACK_SECONDS,
    MAX_RATE_LIMIT_WAIT_SECONDS,
    RATE_LIMIT_PROMPT_LOCK,
    ClaudeFailure,
    ClaudeFailureKind,
    OnRateLimitAction,
    ask_on_rate_limit_action,
    build_classification_from_outcome,
    make_backend_recovery_sleep_seam,
    make_backend_recovery_wait_seam,
    make_plan_quota_pattern_miss_observer,
    resolve_on_rate_limit_policy,
)
from plan_tool.git_state import make_partial_mutation_retry_guard
from plan_tool.prompt_budget import maybe_warn_prompt_budget
from plan_tool.context_window import active_context_window
from plan_tool.rate_limit_loop import (
    RecoveryAction,
    run_with_rate_limit_recovery,
)
from plan_tool.style import tool, warn
from plan_tool.telemetry import record_prompt_budget
from plan_tool.run_log import (
    RUN_LOG_SCHEMA_VERSION,  # noqa: F401 — re-exported for grep'ability;
                             # signals the schema this module emits against
    ClaudeCallEnd,
    utc_now_iso,
)

# Exit code returned when the executable isn't on PATH. Mirrors the
# convention used by `command -v` / `which` (and the existing
# `shell_review_invoker` behavior, which callers test for explicitly).
EXEC_NOT_FOUND_EXIT = 127

# Synthesized rc when `backend_runner.run_streaming_once` raises a
# non-interrupt exception (spawn_failure / unknown termination) instead of
# returning. Distinct from EXEC_NOT_FOUND_EXIT so classify() still buckets
# this UNKNOWN_NONZERO rather than mistaking it for "executable not on PATH".
_RUNNER_EXCEPTION_RC = 1

# Default retry budget for TRANSIENT failures (total attempts). Two
# attempts gives a single 2s backoff with the default base delay, which
# covers a typical network blip without making the user wait through
# extra long backoffs for a permanent failure to surface.
DEFAULT_MAX_TRANSIENT_RETRIES = 2
DEFAULT_TRANSIENT_BASE_DELAY = 2.0

# Total-bytes backstop labels for the generic shell seam (no per-block
# breakdown here — that comes only from the named-block wiring steps). Kept
# short; the seam has no resolved plan/step to name a sharper remedy.
_BACKSTOP_SURFACE = "claude prompt (backstop)"
_BACKSTOP_REMEDIES = (
    "narrow scope with a smaller --step",
    "split a large seed or plan",
)
_prompt_budget_backstop_suppression: contextvars.ContextVar[bool] = (
    contextvars.ContextVar(
        "plan_tool_prompt_budget_backstop_suppression", default=False
    )
)


MetaSink = Callable[[ClaudeCallEnd], None]


# A ``ContextVar`` rather than a plain module global: it is per-thread by
# construction (a freshly-spawned ``threading.Thread`` starts with the
# default ``None``, not the spawning thread's value), so concurrent runs
# can't clobber each other's sink. That matters because ``bench`` runs each
# cell's ``run_step`` / ``apply_finding`` in a daemon worker thread under a
# wall-clock timeout (see ``bench._run_with_timeout``): a timed-out worker
# keeps running in the background and would otherwise install/restore this
# global out from under the main thread, leaving a dead sink wired up for
# the next run. Within one thread, set → read → clear all see the same
# value, so single-threaded CLI behavior is unchanged.
_active_sink: contextvars.ContextVar[Optional[MetaSink]] = contextvars.ContextVar(
    "plan_tool_active_sink", default=None
)


def set_active_sink(sink: Optional[MetaSink]) -> None:
    """Install (or clear) the per-thread sink that receives one
    ``ClaudeCallEnd`` per ``claude_invoke`` call.

    Callers (``cli.cmd_create`` in step 3, ``cli.cmd_detail`` in step 4,
    ``cli.cmd_run`` in step 5) bind a closure that writes the event to
    the current run's JSONL file, then call ``set_active_sink(None)``
    in a ``finally:`` block to keep test runs (which import the module)
    from leaking events into each other's tmp dirs. Pass ``None`` to
    clear.

    The sink is thread-scoped (a ``ContextVar``): every entry-point has
    exactly one active run *per thread*, and ``bench``'s timeout harness
    runs cells on background threads, so a thread-local sink keeps a
    timed-out worker from corrupting the main thread's state.
    """
    _active_sink.set(sink)


def get_active_sink() -> Optional[MetaSink]:
    """Read-only accessor used by tests; not for production callers."""
    return _active_sink.get()


# A real ``RunLogWriter`` handle, distinct from ``_active_sink`` above.
# ``_active_sink`` is the narrow ``Callable[[ClaudeCallEnd], None]``
# closure the sink installers build — enough to forward one event type,
# not enough for ``claude_invoke`` to emit ``backend_spawn`` /
# ``backend_termination`` / ``backend_recovery_wait`` / ``run_interrupted``
# itself. ``RunLogWriter.bind_shell_sink`` / ``install_call_end_sink`` /
# ``uninstall_call_end_sink`` set and restore this alongside the sink they
# already manage. Thread-scoped for the same ``bench`` worker-thread reason
# as ``_active_sink``.
_active_run_logger: contextvars.ContextVar[Optional["RunLogWriter"]] = (
    contextvars.ContextVar("plan_tool_active_run_logger", default=None)
)


def set_active_run_logger(writer: Optional["RunLogWriter"]) -> None:
    """Install (or clear) the per-thread :class:`RunLogWriter` handle that
    :func:`claude_invoke` reads to emit its own backend-lifecycle events.
    Mirrors :func:`set_active_sink`; pass ``None`` to clear."""
    _active_run_logger.set(writer)


def get_active_run_logger() -> Optional["RunLogWriter"]:
    """Read the per-thread :class:`RunLogWriter` handle, or ``None``
    outside a bound scope."""
    return _active_run_logger.get()


class _ClaudeInvokeRunnerObserver:
    """Adapts the active :class:`RunLogWriter` into the fuller observer
    shape :func:`plan_tool.backend_runner.run_streaming_once` accepts, so a
    batch call gets the full spawn/stream/progress/stall/termination
    *and* interrupt signal.

    Deliberately **not** a :class:`RunLogWriter` subclass, though the
    distinction is now cosmetic: ``backend_runner`` calls every observer
    method uniformly through ``getattr`` (see ``_safe_observer_call``), so a
    bare writer passed directly (``run``'s call sites) gets the same
    ``run_interrupted`` forwarding as this wrapper. Every method here is a
    transparent forward to the wrapped writer's matching method.
    """

    __slots__ = ("_writer", "suppress_error_output")

    def __init__(
        self, writer: "RunLogWriter", *, suppress_error_output: bool = False
    ) -> None:
        self._writer = writer
        self.suppress_error_output = suppress_error_output

    @property
    def log_path(self):
        """The wrapped writer's run-log path, so the runner can place the
        raw stream log beside it (``None`` for a writer without one)."""
        return getattr(self._writer, "log_path", None)

    def backend_spawn(self, **kwargs) -> None:
        self._writer.backend_spawn(**kwargs)

    def backend_termination(self, **kwargs) -> None:
        self._writer.backend_termination(**kwargs)

    def claude_stream_event(self, **kwargs) -> None:
        self._writer.claude_stream_event(**kwargs)

    def claude_call_progress(self, **kwargs) -> None:
        self._writer.claude_call_progress(**kwargs)

    def claude_call_stall_suspected(self, **kwargs) -> None:
        self._writer.claude_call_stall_suspected(**kwargs)

    def run_interrupted(self, **kwargs) -> None:
        self._writer.run_interrupted(**kwargs)


# The progress handle for the step a ``claude_invoke`` call runs under, if
# any. Thread-scoped for the same reason as ``_active_sink`` above (bench
# worker threads). ``progress._StderrStepHandle`` pushes itself here on
# construction and pops on ``complete``/``fail``, so ``claude_invoke``'s
# retry path can route its in-flight notices *through* the live heartbeat
# line (clearing the in-place tick first) instead of printing straight to
# stderr and colliding with it. ``None`` → no live progress line → fall
# back to a plain ``tool()`` diagnostic (the historical behavior, which
# the no-handle unit tests still assert on byte-for-byte).
_active_notifier: contextvars.ContextVar[Optional["SupportsNotice"]] = (
    contextvars.ContextVar("plan_tool_active_notifier", default=None)
)
_rate_limit_backend_scope: contextvars.ContextVar[
    Optional[contextlib.ExitStack]
] = contextvars.ContextVar("plan_tool_rate_limit_backend_scope", default=None)


def push_active_notifier(notifier: "SupportsNotice") -> contextvars.Token:
    """Bind ``notifier`` as the active in-flight diagnostic sink; returns a
    token to pass to :func:`pop_active_notifier`. Token-based (not a bare
    set) so nested/sequential steps restore LIFO-correctly."""
    return _active_notifier.set(notifier)


def pop_active_notifier(token: contextvars.Token) -> None:
    """Restore the notifier bound before the matching :func:`push_active_notifier`."""
    _active_notifier.reset(token)


def get_active_notifier() -> Optional["SupportsNotice"]:
    """The progress handle for the current step, or ``None`` outside one."""
    return _active_notifier.get()


@contextlib.contextmanager
def suppress_prompt_budget_backstop(*, active: bool = True):
    """Skip the generic shell prompt-budget backstop in this context.

    ``active=False`` forces the backstop ON for this scope (not a passthrough):
    scoped surfaces pass it when their own budget accounting did not run (it
    raised and was swallowed), so the backstop stays a fallback net — the
    guarantee holds even inside an enclosing ``active=True`` scope. The token
    reset restores the prior value, so nested/sequential scopes nest LIFO-
    correctly; the reader only tests truthiness."""
    token = _prompt_budget_backstop_suppression.set(active)
    try:
        yield
    finally:
        _prompt_budget_backstop_suppression.reset(token)


def _notify_or_tool(
    notifier: Optional["SupportsNotice"], message: str, *, kind: str
) -> None:
    """Route an in-flight diagnostic through the live progress line when one
    is bound (so it clears the heartbeat tick first), else fall back to a
    plain ``plan-tool: <message>`` line — byte-identical to the historical
    output the no-handle unit tests assert on."""
    if notifier is not None:
        notifier.notice(message, kind=kind)
    else:
        tool(message)


def _can_prompt_on_rate_limit() -> bool:
    """True when the batch invoker can safely ask what to do."""
    return (
        getattr(sys.stdin, "isatty", lambda: False)()
        and getattr(sys.stderr, "isatty", lambda: False)()
    )


def _select_rate_limit_backend(
    name: str,
    *,
    notifier: Optional["SupportsNotice"],
) -> bool:
    """Select a fallback backend for the caller-owned recovery scope."""
    backend_scope = _rate_limit_backend_scope.get()
    if backend_scope is None:
        _notify_or_tool(
            notifier,
            "no active backend switch scope; waiting instead",
            kind="info",
        )
        return False
    repo_root = get_active_spawn_cwd() or Path.cwd()
    try:
        scoped_selection = scoped_select_active_backend(
            name,
            repo_root=repo_root,
            fallback_factory=model_specs.synthesize_model_family_backend,
            known_override_names=model_specs.model_family_backend_names(),
        )
        selection = scoped_selection.__enter__()
    except (BackendConfigError, ValueError) as exc:
        _notify_or_tool(notifier, str(exc), kind="info")
        return False
    known_names = set(registered_names()) | model_specs.model_family_backend_names()
    for key in getattr(selection, "unknown_override_names", ()):
        _notify_or_tool(
            notifier,
            unknown_backend_override_warning(key, known_names),
            kind="info",
        )
    effective_backend = getattr(selection, "effective", get_active_backend())
    if shutil.which(effective_backend.binary) is None:
        scoped_selection.__exit__(None, None, None)
        _notify_or_tool(
            notifier,
            f"`{effective_backend.binary}` executable not found on PATH",
            kind="info",
        )
        return False
    selected_backend = getattr(selection, "selected", None)
    if selected_backend is not None and selected_backend.name not in registered_names():
        _notify_or_tool(
            notifier,
            provisional_backend_warning(selected_backend.name),
            kind="info",
        )
    backend_scope.callback(scoped_selection.__exit__, None, None, None)
    return True


def _ask_rate_limit_action(
    notifier: Optional["SupportsNotice"],
) -> OnRateLimitAction:
    """Ask for a rate-limit action, rejecting same-backend switches here."""
    while True:
        current_backend_name = get_active_backend().name
        choice = ask_on_rate_limit_action(
            current_backend_name=current_backend_name
        )
        if (
            choice.action is OnRateLimitAction.SWITCH
            and choice.switch_backend_name == current_backend_name
        ):
            _notify_or_tool(
                notifier,
                f"{current_backend_name} is already active; "
                "choose a different backend",
                kind="info",
            )
            continue
        if choice.action is OnRateLimitAction.SWITCH:
            if _select_rate_limit_backend(
                choice.switch_backend_name or "",
                notifier=notifier,
            ):
                return OnRateLimitAction.SWITCH
            continue
        return choice.action


# Flags an UNKNOWN_NONZERO whose output smells like a quota banner the
# RATE_LIMIT patterns don't recognize yet — the silent never-wait failure
# mode. The Cursor-specific marker detector lives in ``claude_errors``;
# its shared observer suppresses this generic notice when it already fired.
_MISSED_LIMIT_CANARY = re.compile(
    r"(limit|resets?\b|quota|too many|\b429\b)", re.IGNORECASE
)


def _output_tail(stdout: str, stderr: str, *, limit: int = 320) -> str:
    """Last ``limit`` chars of stdout+stderr (banners ride on stdout, which
    the terminal-failure line doesn't show)."""
    combined = f"{stdout}\n{stderr}".strip()
    if len(combined) <= limit:
        return combined
    return "…" + combined[-limit:]


def _maybe_warn_shell_prompt_budget(prompt: str, backend) -> None:
    """Best-effort total-bytes budget advisory for the generic batch seam."""
    if _prompt_budget_backstop_suppression.get():
        return
    try:
        total_bytes = backend.batch_transport(prompt).prompt_bytes
        # `backend` is the active backend at the one call site, so its window is the active one.
        budget = maybe_warn_prompt_budget(
            total_bytes,
            context_window=active_context_window(),
            blocks=(),
            surface=_BACKSTOP_SURFACE,
            remedies=_BACKSTOP_REMEDIES,
        )
        # Record telemetry only when a repo/spawn cwd is scoped — never fall
        # back to Path.cwd(), which would drop a `.plan-tool/telemetry/` write
        # into a repo-less caller's process cwd on every invoke.
        spawn_cwd = get_active_spawn_cwd()
        if spawn_cwd is not None:
            record_prompt_budget(
                spawn_cwd,
                plan_slug="",
                phase="shell-backstop",
                total_bytes=total_bytes,
                advisory=budget.level,
                estimated_tokens=budget.estimated_tokens,
                context_window=budget.context_window,
                headroom_ratio=budget.headroom_ratio,
            )
    except Exception:  # noqa: BLE001 — best-effort; never break the invoke
        pass


def shell_concept_invoker(prompt: str) -> str:
    """Invoke the active backend for concept enrichment and return stdout."""
    _exit_code, stdout = claude_invoke(prompt, phase="concept_emit")
    return stdout


@dataclass(frozen=True)
class ClaudeInvokeOutcome:
    """The completed batch invocation with its final classified failure."""

    rc: int
    stdout: str
    failure: Optional[ClaudeFailure] = None


def claude_invoke(
    prompt: str,
    *,
    phase: str = "claude_invoke",
    attempt: int = 1,
    wait_on_rate_limit: Optional[bool] = None,
    max_transient_retries: int = DEFAULT_MAX_TRANSIENT_RETRIES,
    transient_base_delay: float = DEFAULT_TRANSIENT_BASE_DELAY,
    _sleep: Callable[[float], None] = time.sleep,
    _clock: Callable[[], float] = time.time,
) -> tuple[int, str]:
    """Run a batch invocation and project its richer outcome to ``(rc, stdout)``."""
    outcome = claude_invoke_outcome(
        prompt,
        phase=phase,
        attempt=attempt,
        wait_on_rate_limit=wait_on_rate_limit,
        max_transient_retries=max_transient_retries,
        transient_base_delay=transient_base_delay,
        _sleep=_sleep,
        _clock=_clock,
    )
    return outcome.rc, outcome.stdout


def claude_invoke_outcome(
    prompt: str,
    *,
    phase: str = "claude_invoke",
    attempt: int = 1,
    wait_on_rate_limit: Optional[bool] = None,
    max_transient_retries: int = DEFAULT_MAX_TRANSIENT_RETRIES,
    transient_base_delay: float = DEFAULT_TRANSIENT_BASE_DELAY,
    _sleep: Callable[[float], None] = time.sleep,
    _clock: Callable[[], float] = time.time,
) -> ClaudeInvokeOutcome:
    """Run ``claude -p`` and retain the final recovery-loop classification.

    Behavior:

    - If ``claude`` isn't on PATH → returns ``(127, "")``, prints a
      stderr warning. Callers that only care about stdout treat ``""``
      as a parse failure; callers that care about the exit code can
      distinguish 127 from a genuine claude exit. No ``ClaudeCallEnd``
      is emitted on this path — no subprocess ran.
    - If ``claude`` exits non-zero → returns ``(rc, stdout)`` and
      prints a tail of stderr so the user can debug. Stdout is still
      returned because partial output is sometimes useful.
    - If ``claude`` exits zero → returns ``(0, stdout)``.

    Failure recovery (only when ``rc != 0``):

    - ``RATE_LIMIT``: recovery is driven by the resolved
      :class:`~plan_tool.claude_errors.OnRateLimitPolicy` (from the
      ``wait_on_rate_limit`` kwarg or the process-wide default). ``STOP``
      returns immediately; ``SWITCH`` scopes ``policy.fallback_backend`` to
      this invoke and retries (degrading to a wait if that backend is unavailable);
      ``ASK`` offers the interactive menu (wait / backend switch / stop)
      when the terminal is interactive; ``WAIT`` never prompts, and ``ASK``
      without a TTY falls through to waiting. Waiting parses the reset time
      from backend output, sleeps until it, then retries once with
      ``attempt`` incremented; if no time can be parsed, fall back to
      :data:`claude_errors.DEFAULT_RATE_LIMIT_FALLBACK_SECONDS`. Either way
      the sleep is capped at
      :data:`claude_errors.MAX_RATE_LIMIT_WAIT_SECONDS`.
    - ``TRANSIENT``: retry with exponential backoff (``transient_base_delay``
      doubled per attempt) up to ``max_transient_retries`` total attempts.
    - ``PLAN_QUOTA`` / ``CONTEXT_OVERFLOW`` / ``UNKNOWN_NONZERO``: no retry;
      the original ``(rc, stdout)`` is returned and a hint is printed to
      stderr.

    Each subprocess invocation (initial + each retry) emits one
    :class:`~plan_tool.run_log.ClaudeCallEnd` event with ``attempt``
    incremented per retry, so the run log shows the full sequence.

    The ``_sleep`` / ``_clock`` kwargs are test seams; production
    callers should never pass them.

    No exceptions are raised for normal subprocess outcomes. ``claude_invoke``
    projects this helper's result back to the public ``(rc, stdout)`` shape.
    """
    backend = get_active_backend()
    if shutil.which(backend.binary) is None:
        warn(f"`{backend.binary}` executable not found on PATH")
        return ClaudeInvokeOutcome(EXEC_NOT_FOUND_EXIT, "")

    # Pre-send total-bytes backstop — fires once per call (not per retry) for
    # every batch caller, including those with no named-block check (jira,
    # lessons, annotate). Reuses the path's canonical prompt-bytes measure so
    # the advisory and the run log agree on one number. Best-effort: swallowed
    # so an advisory slip can never perturb the (rc, stdout) result. Named-block
    # senders also hit this seam — the accepted double-fire is BACKLOG #99.
    _maybe_warn_shell_prompt_budget(prompt, backend)

    policy = resolve_on_rate_limit_policy(wait_on_rate_limit)
    recover_rate_limit = policy.action is not OnRateLimitAction.STOP

    # Partial-mutation retry guard, shared with launcher's streaming path (see
    # plan_tool/git_state.py). This path used to hard-code always-retry on the
    # premise that batch proposal turns never edit the tree; the batch argv
    # carries ``--permission-mode acceptEdits`` and ``detail``'s turn
    # demonstrably authors files, so that premise was false — and an rc=0 empty
    # response is now retryable, which makes a turn that wrote its file and
    # returned no text exactly the case that must not be re-driven. ``None``
    # (no spawn cwd / non-git tree) keeps the loop's always-retry default.
    retry_guard = make_partial_mutation_retry_guard(get_active_spawn_cwd())

    # One-slot cell recording the attempt number `run_once` was most
    # recently called with — the only place the recovery loop's true
    # attempt state is observable from outside (see rate_limit_loop.py's
    # seam contract). The wait/sleep seams below derive `next_attempt`
    # from this cell rather than counting their own calls, since the loop
    # also bumps its internal attempt counter on a SWITCH/ASK-switch
    # retry, which never calls `wait` or `sleep`. Seeded from `attempt`
    # so a wait before any attempt would still resolve.
    _attempt_cell = {"value": attempt}

    def _next_attempt() -> int:
        return _attempt_cell["value"] + 1

    # Built once (not per attempt) from whatever writer is bound when this
    # call starts — the runner's own ``phase``/``attempt`` kwargs (passed
    # per attempt below) are what make the resulting events attempt-correct,
    # not a fresh observer per retry. ``None`` when no writer is bound, so
    # ``run_streaming_once`` sees exactly ``run_logger=None`` and behaves as
    # it did before this step.
    _writer = get_active_run_logger()
    _observer = _ClaudeInvokeRunnerObserver(_writer) if _writer is not None else None

    # Seams handed to the shared recovery loop. Each closure resolves the
    # active notifier at call time (so a notifier bound mid-run is honored),
    # and `run_once` owns the per-attempt ClaudeCallEnd emit — the leaf emits
    # no telemetry. See docs/how-to/pipeline/run.md for the seam-by-seam contract.
    def _run_once_seam(attempt_number: int):
        _attempt_cell["value"] = attempt_number
        backend = get_active_backend()
        prompt_bytes = backend.batch_transport(prompt).prompt_bytes
        started = time.monotonic()
        try:
            rc, stdout_text, stderr_text, stats = backend_runner.run_streaming_once(
                prompt,
                backend.batch_transport,
                run_logger=_observer,
                phase=phase,
                attempt=attempt_number,
                enforce_configured_timeout=True,
                configured_timeout_s=_effective_subprocess_timeout(),
                redaction_ready=True,
            )
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as exc:  # noqa: BLE001 — converted to (rc, stdout)
            rc, stdout_text, stderr_text, stats = (
                _RUNNER_EXCEPTION_RC,
                "",
                f"{type(exc).__name__}: {exc}",
                None,
            )
        duration_ms = int((time.monotonic() - started) * 1000)
        # Collapse rule pinned by step 1: the terminal envelope's final_text
        # alone when one arrived, else the runner's joined stdout_buffer
        # (which already carries the raw-line fallback for a plain-stdout
        # backend).
        response_text = (
            stats.final_text if stats and stats.final_text else stdout_text
        )
        # ``backend_spawn``/``backend_termination`` are no longer emitted
        # here — the runner now emits both itself, sourced from the precise
        # ``get_last_termination_reason()`` classification rather than this
        # module's coarser guess. Emitting both here too would double them.
        _emit_call_end(
            phase=phase,
            attempt=attempt_number,
            rc=rc,
            duration_ms=duration_ms,
            stdout_bytes=len(response_text.encode("utf-8")),
            prompt_bytes=prompt_bytes,
            stats=stats,
        )
        return rc, response_text, stderr_text

    def _notify_seam(message: str, *, kind: str) -> None:
        _notify_or_tool(get_active_notifier(), message, kind=kind)

    def _select_backend_seam(name: str) -> bool:
        return _select_rate_limit_backend(name, notifier=get_active_notifier())

    def _ask_action_seam() -> RecoveryAction:
        return ACTION_TO_RECOVERY[_ask_rate_limit_action(get_active_notifier())]

    _observe_plan_quota_pattern_miss = make_plan_quota_pattern_miss_observer(
        repo_root=get_active_spawn_cwd,
        phase=phase,
        notify=lambda message, *, kind: _notify_or_tool(
            get_active_notifier(), message, kind=kind
        ),
    )

    def _on_nonsuccess_seam(
        outcome, failure, will_retry: bool, recovery_reinvoke_predicted: bool
    ) -> None:
        rc, stdout, stderr_text = outcome
        notifier = get_active_notifier()
        observed_quota_pattern_miss = _observe_plan_quota_pattern_miss(
            outcome, failure, will_retry, recovery_reinvoke_predicted
        )
        # Surface a likely-unrecognized quota banner instead of silently
        # returning it as a "response" (see _MISSED_LIMIT_CANARY).
        if (
            not observed_quota_pattern_miss
            and failure.kind is ClaudeFailureKind.UNKNOWN_NONZERO
            and (
                _MISSED_LIMIT_CANARY.search(stdout)
                or _MISSED_LIMIT_CANARY.search(stderr_text)
            )
        ):
            _notify_or_tool(
                notifier,
                f"possible missed rate-limit: exit {rc} classified "
                f"UNKNOWN_NONZERO but output mentions a limit/reset — "
                f"NOT waiting. Report so the detection pattern can be "
                f"extended. output tail: "
                f"{_output_tail(stdout, stderr_text)}",
                kind="info",
            )
        # Surface the raw nonzero exit. When we're about to cleanly retry, the
        # retry/wait notice already tells the story — emitting this too would
        # collide with the heartbeat tick and double the noise, so fold it in.
        # Keep the established raw-exit suppression for a failure that entered
        # recovery, even when the recovery arm later stops without re-invoking.
        if rc != 0 and not recovery_reinvoke_predicted:
            if notifier is not None:
                stderr_tail = stderr_text.strip()
                tail = f"; stderr:\n{stderr_tail}" if stderr_tail else ""
                notifier.notice(
                    f"{get_active_backend().name} exited with code {rc}{tail}",
                    kind="info",
                )
            else:
                stderr_tail = stderr_text.strip() or "(no stderr)"
                warn(
                    f"{get_active_backend().name} exited with code {rc}; "
                    f"stderr:\n{stderr_tail}"
                )

    final_failure: Optional[ClaudeFailure] = None

    def _classify_seam(outcome):
        nonlocal final_failure
        classification = build_classification_from_outcome(outcome)
        final_failure = classification.failure
        return classification

    with contextlib.ExitStack() as backend_scope:
        scope_token = _rate_limit_backend_scope.set(backend_scope)
        try:
            rc, stdout = run_with_rate_limit_recovery(
                run_once=_run_once_seam,
                classify=_classify_seam,
                notify=_notify_seam,
                select_backend=_select_backend_seam,
                ask_action=_ask_action_seam,
                can_prompt=_can_prompt_on_rate_limit,
                wait=make_backend_recovery_wait_seam(
                    _sleep,
                    _clock,
                    writer=get_active_run_logger,
                    next_attempt=_next_attempt,
                    backend_name=lambda: get_active_backend().name,
                    phase=phase,
                ),
                prompt_lock=RATE_LIMIT_PROMPT_LOCK,
                current_backend_name=lambda: get_active_backend().name,
                recover_rate_limit=recover_rate_limit,
                action=ACTION_TO_RECOVERY[policy.action],
                fallback_backend=policy.fallback_backend,
                fallback_seconds=DEFAULT_RATE_LIMIT_FALLBACK_SECONDS,
                max_wait_seconds=MAX_RATE_LIMIT_WAIT_SECONDS,
                max_transient_retries=max_transient_retries,
                transient_base_delay=transient_base_delay,
                attempt=attempt,
                sleep=make_backend_recovery_sleep_seam(
                    _sleep,
                    writer=get_active_run_logger,
                    next_attempt=_next_attempt,
                    backend_name=lambda: get_active_backend().name,
                    phase=phase,
                ),
                clock=_clock,
                on_nonsuccess=_on_nonsuccess_seam,
                retry_guard=retry_guard,
            )
            assert final_failure is not None
            return ClaudeInvokeOutcome(
                rc=rc,
                stdout=stdout,
                failure=(
                    None
                    if final_failure.kind is ClaudeFailureKind.SUCCESS
                    else final_failure
                ),
            )
        finally:
            _rate_limit_backend_scope.reset(scope_token)


def structural_codex_invoke(
    prompt: str,
    *,
    isolated_root: Path,
    seatbelt_profile: Path,
    phase: str,
    attempt: int = 1,
) -> tuple[int, str]:
    """Run one fixed Codex evaluator call without recovery or diagnostics."""
    evaluator = structural_codex_backend(isolated_root)

    def isolated_transport(value: str):
        inner = evaluator.batch_transport(value)
        return backend_runner.PromptTransport(
            ["/usr/bin/sandbox-exec", "-f", str(seatbelt_profile), *inner.argv],
            inner.stdin_text,
        )

    with scoped_active_backend(evaluator), spawn_cwd(Path(isolated_root)):
        started = time.monotonic()
        writer = get_active_run_logger()
        observer = (
            _ClaudeInvokeRunnerObserver(writer, suppress_error_output=True)
            if writer is not None
            else None
        )
        try:
            rc, stdout, _stderr, stats = backend_runner.run_streaming_once(
                prompt,
                isolated_transport,
                run_logger=observer,
                phase=phase,
                attempt=attempt,
                enforce_configured_timeout=True,
                configured_timeout_s=_effective_subprocess_timeout(),
                redaction_ready=False,
                suppress_content_output=True,
            )
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException:  # The structural caller intentionally gets no detail.
            rc, stdout, stats = _RUNNER_EXCEPTION_RC, "", None
        response = stats.final_text if stats and stats.final_text else stdout
        _emit_call_end(
            phase=phase,
            attempt=attempt,
            rc=rc,
            duration_ms=int((time.monotonic() - started) * 1000),
            stdout_bytes=len(response.encode("utf-8")),
            prompt_bytes=evaluator.batch_transport(prompt).prompt_bytes,
            stats=stats,
            suppress_error_output=True,
        )
        return rc, response


# Per-call timeout scope. A global default is wrong here — authoring calls
# legitimately run for many minutes (a `detail` step can take ~8 min) while a
# bounded probe like the per-step purity check tops out ~3 min — so a caller
# that knows its calls are bounded opts a subtree in via `scoped_claude_timeout`.
# `PLAN_TOOL_CLAUDE_TIMEOUT` is a global override (debugging / operator escape).
#
# The sentinel keeps an unscoped call distinct from a scope which deliberately
# disables timeouts. The latter must not fall back to the global setting.
_NO_CLAUDE_TIMEOUT_SCOPE = object()
_claude_timeout_scope: contextvars.ContextVar[object] = contextvars.ContextVar(
    "plan_tool_claude_timeout", default=_NO_CLAUDE_TIMEOUT_SCOPE
)


@contextlib.contextmanager
def scoped_claude_timeout(seconds: Optional[float]):
    """Bound every backend call in this dynamic scope to ``seconds``. A killed
    call classifies as TIMEOUT (terminal — no same-budget retry) and falls
    through to an empty result. Use for callers whose calls are
    duration-bounded — not global (see the ContextVar note)."""
    token = _claude_timeout_scope.set(seconds if seconds and seconds > 0 else None)
    try:
        yield
    finally:
        _claude_timeout_scope.reset(token)


def _parse_timeout_seconds(raw: Optional[str]) -> Optional[float]:
    """Parse a timeout env/override string: positive float, else ``None``.

    ``None`` / empty / non-positive / unparseable → no timeout. The resolver
    uses this result to honor an explicit disabled timeout setting.
    """
    if not raw:
        return None
    try:
        val = float(raw)
    except ValueError:
        return None
    return val if val > 0 else None


def resolve_claude_timeout(
    default: Optional[float],
    *,
    setting: Optional[str] = None,
    legacy_setting: Optional[str] = "PLAN_TOOL_CLAUDE_TIMEOUT",
) -> Optional[float]:
    """Resolve a caller's timeout setting, then legacy fallback, then default.

    An empty setting is treated as absent. A non-empty setting that parses to
    ``None`` is an explicit no-timeout value, so it masks later fallbacks.
    """
    for name in (setting, legacy_setting):
        if name is None:
            continue
        raw = os.environ.get(name)
        if raw:
            return _parse_timeout_seconds(raw)
    return default


def _effective_subprocess_timeout() -> Optional[float]:
    """Effective per-call timeout in seconds: the ``scoped_claude_timeout`` scope
    wins, else ``PLAN_TOOL_CLAUDE_TIMEOUT``, else ``None`` (no caller-configured
    bound — still backstopped by ``backend_runner``'s own
    ``_KILL_AFTER_SILENCE_S`` silence kill, unlike the pre-runner-swap
    ``subprocess.run`` call this default once meant truly unbounded).
    Malformed env values are ignored. Read per-call."""
    scoped = _claude_timeout_scope.get()
    if scoped is not _NO_CLAUDE_TIMEOUT_SCOPE:
        return float(scoped) if isinstance(scoped, (int, float)) else None
    return resolve_claude_timeout(None)


# One-shot guard for the unsinked-call warning below. Process-wide (not
# thread-scoped like the sink itself): the point is to tell the developer once
# that *some* call went unrecorded, not once per thread. A benign race can
# print twice under `--jobs N`; a lock here would serialize a diagnostic.
_warned_no_sink = False


def _caller_outside_shell() -> str:
    """``file.py:lineno`` of the nearest frame outside this module.

    Names the actual call site in the unsinked-call warning — ``phase`` alone
    is too weak (most unsinked callers never pass one). Only runs on the
    once-per-process warn path, so the stack walk costs nothing in steady
    state; best-effort, since a diagnostic must never perturb the call.
    """
    try:
        import traceback

        here = __file__
        for frame in reversed(traceback.extract_stack()[:-1]):
            if frame.filename != here:
                return f"{Path(frame.filename).name}:{frame.lineno}"
    except Exception:  # noqa: BLE001 — best-effort
        pass
    return "unknown"


def _warn_unsinked_call(phase: str) -> None:
    """Warn once per process that a claude call was made with no sink.

    Run-log coverage is opt-in per call site and silent when absent, so gaps
    are found one incident at a time — the 2026-07 purity-scan failures went
    weeks with no trace for exactly this reason, and a later audit found five
    more sites. This makes the class self-reporting. See BACKLOG #179.

    Not every unsinked call is a defect (``bench``, one-off probes, tests), so
    this is advisory only: it never fails, blocks, or retries the call.
    """
    global _warned_no_sink
    if _warned_no_sink:
        return
    # Flip the guard *before* emitting: a warn that raises must not re-arm the
    # warning and spam every subsequent call.
    _warned_no_sink = True
    try:
        warn(
            f"claude call at {_caller_outside_shell()} (phase={phase!r}) ran "
            "with no run-log sink installed — its duration, tokens and cost "
            "are unrecorded. Later unsinked calls in this process are not "
            "reported. See BACKLOG #176-#178."
        )
    except Exception:  # noqa: BLE001 — a diagnostic must never perturb the call
        pass


def _emit_call_end(
    *,
    phase: str,
    attempt: int,
    rc: int,
    duration_ms: int,
    stdout_bytes: int,
    prompt_bytes: int,
    stats: Optional["ClaudeRunStats"] = None,
    suppress_error_output: bool = False,
) -> None:
    """Forward one ``ClaudeCallEnd`` to the active sink if installed.

    The ``run_id`` field is left empty here: the sink closure installed
    by step 3/4/5 owns the current run id (captured at run-start time)
    and substitutes it before calling ``run_log.append_event``. Pushing
    the run id into ``claude_invoke``'s argument list would force every
    caller to thread it through, which defeats the purpose of the
    module-level sink.

    A sink that raises is best-effort: we log a stderr warning and
    swallow the exception, mirroring the lesson-extraction convention
    in ``detail.py`` — the claude call result must not be perturbed by
    a downstream logging failure.

    With **no** sink installed the event is dropped, which is what makes a
    missing sink invisible; :func:`_warn_unsinked_call` says so once per
    process so the gap reports itself instead of needing an audit to find.
    """
    sink = _active_sink.get()
    if sink is None:
        _warn_unsinked_call(phase)
        return
    event = ClaudeCallEnd(
        ts=utc_now_iso(),
        run_id="",  # set by the caller's run_log wrapper in steps 3/4/5
        phase=phase,
        attempt=attempt,
        rc=rc,
        duration_ms=duration_ms,
        stdout_bytes=stdout_bytes,
        # Usage/cache/cost/request-id from the batch terminal envelope
        # (JSON-output backends). None when the backend emits plain stdout
        # or the terminal envelope didn't parse. See BACKLOG #74.
        tokens_input=stats.tokens_input if stats else None,
        tokens_output=stats.tokens_output if stats else None,
        cache_creation_tokens=stats.cache_creation_tokens if stats else None,
        cache_read_tokens=stats.cache_read_tokens if stats else None,
        request_id=stats.request_id if stats else None,
        cost_usd=stats.cost_usd if stats else None,
        input_includes_cached=stats.input_includes_cached if stats else None,
    )
    try:
        sink(event)
    except Exception as exc:  # noqa: BLE001 — best-effort
        if suppress_error_output:
            return
        warn(
            f"run-log sink raised {type(exc).__name__}: {exc}; "
            "claude call result is unaffected"
        )
