"""Shared streaming subprocess supervisor for backend CLI calls.

:func:`run_streaming_once` owns one Popen call against a backend CLI:
the stdout/stderr pump threads, NDJSON-to-event parsing, the heartbeat
daemon with its stall marker and silence-kill ladder, and the dormant
sibling NDJSON transcript writer. ``launcher.shell_invoker`` reaches it
through ``launcher._run_streaming_once`` (a thin forwarding wrapper that
supplies the active backend's streaming transport); the batch lane
(``shell.claude_invoke``) can hand it ``batch_transport`` instead.

A leaf below ``shell``/``launcher`` — its only first-party imports are
``plan_tool.backend`` and ``plan_tool.run_log`` (same shape as
``git_state.py``), which is what lets both backend callers share the
supervisor without a ``shell`` ↔ ``launcher`` import cycle.
"""

from __future__ import annotations

import contextlib
import contextvars
import itertools
import os
import re
import signal
import subprocess
import sys
import threading
import time
from dataclasses import replace
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

from plan_tool.backend import (
    ClaudeRunStats,
    PromptTransport,
    get_active_backend,
    get_active_spawn_cwd,
    observe_context_window,
    reported_window_for_model,
)
from plan_tool.run_log import RunLogWriter

if TYPE_CHECKING:
    from plan_tool.run_log import RunnerObserver


# Heartbeat cadence and stall threshold for the ``run_streaming_once``
# progress daemon. ~20s gives a fast-enough "subprocess still working"
# signal without flooding the run-log JSONL; ~300s matches the
# motivating-incident silence window where the operator first started
# wondering whether the call had wedged.
_PROGRESS_INTERVAL_S = 20.0
_STALL_THRESHOLD_S = 300.0
# After 15 minutes of continuous silence (no NDJSON activity from
# claude), assume the child is genuinely wedged and terminate it.
# Otherwise ``proc.wait()`` blocks indefinitely and pins plan-tool. The
# kill threshold is well above legitimate long-running tool calls
# (a 10-min pytest sweep still emits stdout each test) so the false-
# positive rate should be low; the threshold is dialable here without a
# CLI surface change.
_KILL_AFTER_SILENCE_S = 900.0
# After ``terminate()``, wait this long for graceful shutdown before
# escalating to ``kill()`` (SIGKILL on POSIX).
_KILL_GRACE_S = 5.0

# Process-wide call counter naming each derived stream log. ``attempt``
# restarts at 1 for every backend call, so it cannot identify a call alone.
_STREAM_LOG_SEQ = itertools.count(1)
_STREAM_LOG_WARNED = [False]  # one open-failure warning per process

# Console verbosity for the stdout pump in ``run_streaming_once``.
# 0 = quiet (default): suppress raw claude stream-json from terminal;
#     the progress reporter's step header + heartbeat + done line carry
#     all the user-visible signal. The live stream log still records
#     every byte for forensics.
# 1 = verbose (``-v``): emit one indented line per ``tool_use`` event on
#     stderr so the operator can see what claude is touching, without
#     drowning them in JSON envelopes.
# 2 = debug (``--debug``): print the stream log's path. Raw NDJSON goes to
#     stdout only when that log cannot be opened.
_CONSOLE_VERBOSITY_QUIET = 0
_CONSOLE_VERBOSITY_VERBOSE = 1
_CONSOLE_VERBOSITY_DEBUG = 2
_console_verbosity: int = _CONSOLE_VERBOSITY_QUIET


def set_console_verbosity(level: int) -> None:
    """Set the per-process console verbosity for the stdout pump.

    Called once from ``cli.main`` based on ``--verbose`` / ``--debug``.
    Callers outside the CLI (tests, direct ``run_streaming_once`` use)
    can leave the default ``QUIET`` in place; behavior matches the
    silent shell-invoker callers (``claude_invoke``) that already use
    ``capture_output=True``.
    """
    global _console_verbosity
    _console_verbosity = level


def get_console_verbosity() -> int:
    """Read-only accessor used by the pumps and tests."""
    return _console_verbosity


# Mirrors ``plan_tool.claude_errors.BACKEND_TIMEOUT_SENTINEL``'s literal value
# rather than importing it — importing ``plan_tool.claude_errors`` would break
# this module's leaf import constraint (see module docstring). A monitor-
# thread kill writes this marker onto the returned stderr so ``classify()``
# recognizes it exactly as it recognizes ``shell._run_once``'s
# ``subprocess.TimeoutExpired`` path, with no change to ``classify()`` itself.
# Pinned equal to the original by
# tests/test_claude_errors.py::test_backend_runner_sentinel_matches_claude_errors_sentinel.
_BACKEND_TIMEOUT_SENTINEL = "__plan_tool_backend_timeout__"


class TerminationReason(str, Enum):
    """Closed set of reasons one ``run_streaming_once`` call can end.

    Strings (not auto-ints), matching ``claude_errors.ClaudeFailureKind``'s
    shape, so the value greps cleanly and survives a JSONL round-trip.
    """

    COMPLETED = "completed"
    CONFIGURED_TIMEOUT = "configured_timeout"
    SILENCE_TIMEOUT = "silence_timeout"
    OPERATOR_INTERRUPT = "operator_interrupt"
    SPAWN_FAILURE = "spawn_failure"
    BACKEND_NONZERO = "backend_nonzero"
    UNKNOWN = "unknown"


class InterruptSource(str, Enum):
    """Closed set of windows a ``KeyboardInterrupt`` can be caught in and
    reported through a ``run_interrupted`` event.

    Mirrors ``TerminationReason``'s shape: a shared, typo-proof vocabulary
    for a value ``claude_errors.py``'s recovery-wait wrappers write too.
    """

    SPAWN = "spawn"
    PROC_WAIT = "proc_wait"
    RECOVERY_WAIT = "recovery_wait"


# Call-scoped termination-reason accessor. The var holds a one-element list
# ("cell") set fresh on the calling thread at each `run_streaming_once` entry
# — not the reason itself — so the pump/heartbeat threads, which run in a
# `contextvars.copy_context()` snapshot taken *after* the cell is set, share
# the same cell object and can mutate its contents. A plain ContextVar value
# would not work in either direction: a shared module value would race across
# concurrent calls (`detail --jobs N`), while a
# monitor thread's own `.set()` would never be visible back to the caller
# (its context is a copy). Mutating a shared cell threads the needle.
_termination_reason_var: contextvars.ContextVar[Optional[list]] = (
    contextvars.ContextVar("plan_tool_backend_runner_termination_reason", default=None)
)


def get_last_termination_reason() -> Optional[TerminationReason]:
    """The calling context's most recent ``run_streaming_once`` outcome.

    Call-scoped (see the ContextVar note above) — safe to call right after a
    call on the same thread even while other threads are mid-call.
    """
    cell = _termination_reason_var.get()
    if cell is None:
        return None
    return cell[0]


def _note_termination_reason(
    cell: list, lock: threading.Lock, reason: TerminationReason
) -> None:
    """Record ``reason`` into ``cell``, honoring the operator-interrupt
    precedence rule: writing ``OPERATOR_INTERRUPT`` always wins; any other
    reason is refused once the cell already holds ``OPERATOR_INTERRUPT``.
    Locked so this holds regardless of which thread — the heartbeat racing
    its kill ladder, or the main thread catching a ``KeyboardInterrupt`` out
    of ``proc.wait()`` — reaches the write first.
    """
    with lock:
        if (
            cell[0] is TerminationReason.OPERATOR_INTERRUPT
            and reason is not TerminationReason.OPERATOR_INTERRUPT
        ):
            return
        cell[0] = reason


# Per-caller silence-threshold override, mirroring `plan_tool/shell.py:
# scoped_claude_timeout`'s shape (sentinel-default-vs-explicit-None scope,
# reset-on-exit) — mirrored rather than imported for the same leaf-boundary
# reason as the sentinel above. Code-level only: no CLI flag, no env var: a
# future caller with a documented, tested need for a non-default silence
# threshold has a mechanism ready rather than inventing another one ad hoc.
_NO_SILENCE_TIMEOUT_SCOPE = object()
_silence_timeout_scope: contextvars.ContextVar[object] = contextvars.ContextVar(
    "plan_tool_backend_runner_silence_timeout", default=_NO_SILENCE_TIMEOUT_SCOPE
)


@contextlib.contextmanager
def scoped_silence_timeout(seconds: Optional[float]):
    """Override the heartbeat's silence-kill threshold for every
    ``run_streaming_once`` call made in this dynamic scope."""
    token = _silence_timeout_scope.set(
        seconds if seconds and seconds > 0 else None
    )
    try:
        yield
    finally:
        _silence_timeout_scope.reset(token)


def _effective_silence_timeout_s() -> Optional[float]:
    """Effective silence-kill threshold: the ``scoped_silence_timeout`` scope
    wins when set, else the module default ``_KILL_AFTER_SILENCE_S``. Read
    per heartbeat tick so a scope entered after the call started still
    applies to any tick that hasn't fired yet."""
    scoped = _silence_timeout_scope.get()
    if scoped is not _NO_SILENCE_TIMEOUT_SCOPE:
        return float(scoped) if isinstance(scoped, (int, float)) else None
    return _KILL_AFTER_SILENCE_S


def _safe_observer_call(observer: Optional[object], method_name: str, **kwargs) -> None:
    """Call ``method_name`` on ``observer`` with ``kwargs``, swallowing any
    exception — including a missing attribute — and printing one line to
    stderr instead of raising. A no-op when ``observer`` is ``None``.

    Every spawn/stream/progress/stall/termination/interrupted signal this
    module emits goes through here: the object being called is no longer
    guaranteed to be a :class:`~plan_tool.run_log.RunLogWriter` — it can be
    a caller-authored observer (see ``shell.claude_invoke``) — so a bug
    there must not be able to kill the pump/heartbeat thread or suppress
    the silence kill.
    """
    if observer is None:
        return
    try:
        getattr(observer, method_name)(**kwargs)
    except Exception as exc:  # noqa: BLE001 — observer bugs must not break the call
        if getattr(observer, "suppress_error_output", False):
            return
        print(
            f"plan-tool: run-log emit skipped ({method_name}: "
            f"{type(exc).__name__}: {exc})",
            file=sys.stderr,
        )


def _finalize_interrupted_call(
    exc: BaseException,
    *,
    proc: Optional[object],
    reason_cell: list,
    reason_lock: threading.Lock,
    run_logger: Optional[object],
    phase: str,
    attempt: int,
    call_start_monotonic: float,
    source: InterruptSource,
) -> None:
    """Shared tail for both windows ``run_streaming_once`` can be
    interrupted in before it returns normally: a spawn-time failure
    (``proc`` is ``None`` — nothing was ever running) and everything from
    a successful ``Popen()`` through ``proc.wait()`` (``proc`` exists and
    must be killed/reaped so the non-daemon pump threads don't wedge
    reading its still-open pipes). Classifies ``exc``, records the
    termination reason (honoring the operator-interrupt precedence rule),
    kills/reaps the child when there is one, and emits the paired
    ``backend_termination`` / ``run_interrupted`` observer calls. Does not
    re-raise ``exc`` — the caller's own ``except`` block does that, so its
    ``raise`` keeps the original traceback.
    """
    reason = (
        TerminationReason.OPERATOR_INTERRUPT
        if isinstance(exc, KeyboardInterrupt)
        else (
            TerminationReason.SPAWN_FAILURE
            if proc is None
            else TerminationReason.UNKNOWN
        )
    )
    _note_termination_reason(reason_cell, reason_lock, reason)
    if proc is not None:
        try:
            proc.kill()
        except (OSError, ProcessLookupError):
            # Already gone — e.g. a race against the heartbeat's own
            # kill ladder. Swallow it so the original exception (not
            # this one) is what propagates from the caller's ``raise``.
            pass
        proc.wait()  # reap; safe even if the heartbeat already killed it
    # Both observer calls below run while `exc` is the exception the
    # caller is about to re-raise. `_safe_observer_call` already
    # swallows an ordinary `Exception` from the observer; wrapping it
    # again here catches anything else — most plausibly a *second*
    # `KeyboardInterrupt` landing mid-call (`RunLogWriter._refresh_in_flight`
    # does file I/O under a lock) — so it can't silently replace `exc`
    # before the caller's `raise` is reached.
    try:
        _safe_observer_call(
            run_logger, "backend_termination",
            phase=phase, attempt=attempt, backend=get_active_backend().name,
            reason=reason.value,
            duration_ms=int((time.monotonic() - call_start_monotonic) * 1000),
        )
    except BaseException:  # noqa: BLE001 — see comment above
        pass
    if isinstance(exc, KeyboardInterrupt):
        try:
            _safe_observer_call(
                run_logger, "run_interrupted",
                phase=phase, attempt=attempt, source=source.value,
            )
        except BaseException:  # noqa: BLE001 — see comment above
            pass


def _resolve_stream_log_path(
    sibling_log_dir: Optional[Path],
    run_logger: Any,
    phase: str,
    attempt: int,
    suppress_content_output: bool,
) -> Optional[Path]:
    """Where the raw backend stream is appended, live, for this call.

    Structural callers that suppress content get no log at all — their
    redaction is not ready and the stream is unredacted. The directory is
    ``sibling_log_dir`` when given, else the run log's own
    ``<run_id>.streams/``; the file is uniquely named per call
    (``attempt`` alone repeats across calls). See docs/how-to/pipeline/run.md.
    """
    if suppress_content_output:
        return None
    if sibling_log_dir is not None:
        directory = sibling_log_dir
    else:
        log_path = getattr(run_logger, "log_path", None)
        if not isinstance(log_path, Path):
            return None
        directory = log_path.with_suffix(".streams")
    safe_phase = re.sub(r"[^A-Za-z0-9_-]+", "-", phase)[:40] or "call"
    seq = next(_STREAM_LOG_SEQ)
    return directory / f"claude-stream.{seq:04d}.{safe_phase}.a{attempt}.ndjson"


def run_streaming_once(
    prompt: str,
    transport: Callable[[str], PromptTransport],
    *,
    run_logger: Optional["RunLogWriter | RunnerObserver"] = None,
    phase: str = "claude_call",
    attempt: int = 1,
    sibling_log_dir: Optional[Path] = None,
    enforce_configured_timeout: bool = False,
    configured_timeout_s: Optional[float] = None,
    redaction_ready: bool = True,
    suppress_content_output: bool = False,
) -> tuple[int, str, str, "ClaudeRunStats"]:
    """One ``claude -p --output-format stream-json --verbose`` Popen call.

    ``transport`` selects how the prompt reaches the backend — the run
    lane passes the active backend's ``streaming_transport`` (via
    ``launcher._run_streaming_once``); a batch caller can pass
    ``batch_transport`` instead without any change here. Backend
    resolution is otherwise unchanged: the pump's per-line parse and the
    kill ladder's messages still read ``get_active_backend()`` directly.

    Same overall shape as the prior ``--verbose`` invocation — Popen,
    pump stdout/stderr to terminal AND a buffer, ``proc.wait()`` then
    ``thread.join()`` — but each stdout line is additionally parsed as
    NDJSON so the call surface is no longer opaque between
    ``claude_call_start`` and ``claude_call_end``:

    - When a line parses as JSON, one :class:`ClaudeStreamEvent` is
      emitted per content block (``tool_use``, ``tool_result``,
      ``assistant_text``, ``system``, ``result``). Text content from
      ``assistant_text`` and the terminal ``result`` envelope is also
      appended to the stdout buffer so the failure classifier — which
      pattern-matches over raw strings — keeps working without
      learning JSON.
    - When parsing fails (transport-layer errors, rate-limit copy
      claude surfaces as raw text on a non-zero exit), the line is
      appended verbatim to the stdout buffer. The classifier walks the
      same buffer as before.

    A daemon thread fires :class:`ClaudeCallProgress` heartbeats every
    ``_PROGRESS_INTERVAL_S`` seconds while the subprocess is alive, and
    a single :class:`ClaudeCallStallSuspected` marker once
    ``silent_ms ≥ _STALL_THRESHOLD_S``. Both are persisted to JSONL
    only when ``run_logger`` is supplied — the heartbeat thread is a
    no-op otherwise, which is what keeps the unit tests fast.

    Raw NDJSON lines are appended live to a per-call stream log (``tail -f``);
    absent when ``suppress_content_output`` is set. See
    docs/how-to/pipeline/run.md "Raw backend stream log".

    Returns ``(returncode, stdout_text, stderr_text, stats)``. The
    caller's failure classifier still needs both ``stdout_text`` and
    ``stderr_text`` because claude surfaces rate-limit copy on either
    (depends on transport layer error vs. in-band SDK message), and
    ``stats`` carries the structured usage / cost / final-text fields
    extracted from the terminal ``{"type": "result"}`` envelope.

    If anything raises between a successful ``Popen()`` and ``proc.wait()``
    returning — most commonly a ``KeyboardInterrupt`` from an operator's
    Ctrl-C, at any point in that window, not only inside ``proc.wait()``
    itself — this function kills and reaps the child, then re-raises the
    same exception instead of returning.

    ``enforce_configured_timeout`` gates a second, elapsed-time kill the
    heartbeat enforces alongside its existing silence kill: when ``True``
    and ``configured_timeout_s`` is set, the call is terminated once total
    elapsed time (not silence) crosses that value. Defaults to ``False`` so
    ``run``'s call sites — which never pass either kwarg — stay exempt from
    ``PLAN_TOOL_CLAUDE_TIMEOUT``/``scoped_claude_timeout`` exactly as today;
    the exemption is this parameter's default, not an inference about which
    caller is asking. Every ending is classified into one
    :class:`TerminationReason`, readable after return (or after the
    exception propagates) via :func:`get_last_termination_reason`.

    ``redaction_ready`` gates only the ``-v`` console print of a
    ``tool_use`` event's ``tool_input_summary``: ``True`` (the default,
    ``run``'s call sites) prints the real summary; ``False`` prints the
    literal ``[OMITTED]`` instead. It does nothing to ``claude_stream_event``
    (a no-op with no ``run_logger`` bound regardless) or to the raw
    NDJSON stream log. A caller whose tool-input redaction isn't wired up
    yet passes ``False`` so its ``-v`` output can never leak an unredacted
    summary.

    ``run_logger`` accepts a bare :class:`~plan_tool.run_log.RunLogWriter`
    (or ``None``), or any other object satisfying
    :class:`~plan_tool.run_log.RunnerObserver`. A bare writer gets
    ``backend_spawn``/``backend_termination`` calls in addition to the
    stream/progress/stall signals it already got, and — like a caller-built
    observer (``shell.claude_invoke`` is the first) — a ``run_interrupted``
    call on a ``KeyboardInterrupt`` caught anywhere between ``Popen()`` and
    ``proc.wait()`` returning. ``None`` still produces no calls at all.
    Every one of these calls is individually swallowed on failure (see
    :func:`_safe_observer_call`) so a bad observer can't kill the
    pump/heartbeat thread or suppress the silence kill; the two calls
    :func:`_finalize_interrupted_call` makes while already unwinding an
    interrupt are guarded a second time so a bad observer can't replace
    the interrupt being re-raised, either.
    """
    # Set before Popen so a spawn-time failure can still be classified, and
    # before the pump/heartbeat threads' `contextvars.copy_context()` below
    # so they capture a reference to this same cell (see the ContextVar note
    # on `_termination_reason_var`).
    reason_cell: list = [None]
    reason_lock = threading.Lock()
    _termination_reason_var.set(reason_cell)
    # Anchors every ``backend_termination`` call's ``duration_ms`` — including
    # a spawn failure, before ``proc`` even exists — so all four exit shapes
    # (clean/nonzero, killed, spawn failure, wait()-exception) report the same
    # wall-clock basis.
    call_start_monotonic = time.monotonic()

    prompt_transport = transport(prompt)
    # CPython's `Popen.__init__` sets `self.pid` before its own blocking
    # read of the child's error-relay pipe, and never kills/reaps it on
    # failure — a `KeyboardInterrupt` there would orphan a live child that
    # nothing can reach, since `proc` is never bound. Ignoring SIGINT for
    # the call's duration (main thread only — see
    # tests/test_backend_runner.py::TestPopenSigintGuard) closes that
    # window instead.
    _guard_sigint = threading.current_thread() is threading.main_thread()
    _prev_sigint_handler = None
    if _guard_sigint:
        try:
            _prev_sigint_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
        except (ValueError, OSError):
            _guard_sigint = False
    try:
        proc = subprocess.Popen(
            prompt_transport.argv,
            # DEVNULL is load-bearing for codex: it reads inherited/piped
            # stdin and appends it to the prompt as a <stdin> block —
            # blocking forever when the parent's stdin never closes (see
            # docs/reference/contracts/codex-cli.md, STATUS note). Harmless for claude.
            stdin=(
                subprocess.PIPE
                if prompt_transport.stdin_text is not None
                else subprocess.DEVNULL
            ),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            # None inherits the process cwd; entrypoints with a repo_root
            # scope this via backend.spawn_cwd so the backend reads/edits
            # the tree the caller named, not wherever the process stands.
            cwd=get_active_spawn_cwd(),
        )
    except BaseException as exc:
        # Nothing was spawned, so there is no child to kill/reap — a real
        # `KeyboardInterrupt` can no longer land mid-fork at all (the
        # SIGINT guard above), though a test double can still raise one
        # directly, which the shared tail below classifies like any other
        # exception here.
        _finalize_interrupted_call(
            exc,
            proc=None,
            reason_cell=reason_cell,
            reason_lock=reason_lock,
            run_logger=run_logger,
            phase=phase,
            attempt=attempt,
            call_start_monotonic=call_start_monotonic,
            source=InterruptSource.SPAWN,
        )
        raise
    finally:
        # `_guard_sigint` alone is the right restore condition — it's
        # only ever True once `signal.signal` above already succeeded.
        # Testing `_prev_sigint_handler is not None` too would skip the
        # restore (leaving SIGINT permanently ignored for the rest of the
        # process) on the rare host where the previous handler wasn't
        # installed from Python, since `signal.signal` reports that case
        # as `None` rather than `SIG_DFL`; fall back to `SIG_DFL` there
        # since `None` isn't a valid handler to pass back in.
        if _guard_sigint:
            signal.signal(
                signal.SIGINT,
                _prev_sigint_handler
                if _prev_sigint_handler is not None
                else signal.SIG_DFL,
            )
    if proc.stdout is None or proc.stderr is None:
        # Unreachable with a real Popen (stdout=PIPE/stderr=PIPE are
        # hardcoded above) — this narrows the type for the pump loops
        # below and guards a non-conforming test double. Reap the already-
        # spawned child before raising so a double that does trip it can't
        # leak a live process.
        try:
            proc.kill()
            proc.wait()
        except (OSError, ProcessLookupError):
            pass
        raise RuntimeError("subprocess pipes are None")

    # Popen succeeded — the one production point that actually knows the
    # child's pid, so ``backend_spawn`` fires here and nowhere else. A spawn
    # failure above never reaches this line, which is why that path emits a
    # termination but no matching spawn.
    _effective_silence_s = _effective_silence_timeout_s()
    if enforce_configured_timeout and configured_timeout_s is not None:
        _effective_timeout_s = (
            min(configured_timeout_s, _effective_silence_s)
            if _effective_silence_s is not None
            else configured_timeout_s
        )
    else:
        _effective_timeout_s = _effective_silence_s

    stdout_buffer: list[str] = []
    stderr_buffer: list[str] = []
    raw_stdout_lines: list[str] = []
    stats_box: dict[str, ClaudeRunStats] = {"v": ClaudeRunStats()}
    # Latest ``request_id`` seen on an ``assistant`` event. Merged into
    # ``stats_box["v"]`` when the result envelope arrives, since the
    # result envelope itself does not carry a per-API-request id.
    last_request_id: dict[str, Optional[str]] = {"v": None}

    # State mutated by the stdout pump and read by the heartbeat
    # daemon. The lock is fine-grained because the daemon's read of
    # ``last_activity_monotonic`` must not race with the pump's update.
    state_lock = threading.Lock()
    start_monotonic = time.monotonic()
    state = {
        "last_activity_monotonic": start_monotonic,
        "last_tool": None,
        "last_activity_kind": None,
    }
    stop = threading.Event()
    stall_fired = [False]
    # One-shot guard so the kill ladder fires at most once even if the
    # heartbeat takes a couple ticks to notice the process hasn't
    # actually exited yet.
    killed_fired = [False]
    # Which OS signal the kill ladder actually used, for the eventual
    # ``backend_termination`` call's ``signal_or_timeout`` field. ``None``
    # until the heartbeat's kill ladder fires; set to ``"SIGKILL"`` if
    # escalation past the grace window happens, overwriting ``"SIGTERM"``.
    kill_signal_used: list[Optional[str]] = [None]

    stream_log_path = _resolve_stream_log_path(
        sibling_log_dir, run_logger, phase, attempt, suppress_content_output
    )
    stream_log_file: list[Any] = [None]

    def _pump_stdout() -> None:
        verbosity = get_console_verbosity()
        for line in proc.stdout:
            # The raw NDJSON goes to the live stream log. Console
            # passthrough survives only at --debug when no log could be
            # opened, so --debug is never silent.
            if stream_log_file[0] is not None:
                # Any failure here must not kill the pump — a dead pump
                # wedges ``proc.wait()`` — so drop the log, keep streaming.
                try:
                    stream_log_file[0].write(
                        line if line.endswith("\n") else line + "\n"
                    )
                except Exception as exc:  # noqa: BLE001
                    dropped, stream_log_file[0] = stream_log_file[0], None
                    try:
                        dropped.close()
                    except Exception:  # noqa: BLE001
                        pass
                    if not suppress_content_output:
                        print(
                            f"plan-tool: raw backend stream log stopped "
                            f"({type(exc).__name__}: {exc})",
                            file=sys.stderr,
                        )
            if (
                stream_log_file[0] is None
                and not suppress_content_output
                and verbosity >= _CONSOLE_VERBOSITY_DEBUG
            ):
                sys.stdout.write(line)
                sys.stdout.flush()
            raw_stdout_lines.append(line)
            bytes_in = len(line.encode("utf-8"))
            # A parser bug must not kill this thread — same principle as
            # _safe_observer_call below: losing the pump wedges proc.wait()
            # until the silence-kill ladder finally notices.
            try:
                parsed = get_active_backend().parse_stream_line(line, bytes_in=bytes_in)
            except Exception as exc:  # noqa: BLE001 — parser bugs must not break the call
                if not suppress_content_output:
                    print(
                        f"plan-tool: stream-line parse failed ({type(exc).__name__}: "
                        f"{exc}); treating as raw output",
                        file=sys.stderr,
                    )
                parsed = None
            if parsed is None:
                stdout_buffer.append(line)
                with state_lock:
                    state["last_activity_monotonic"] = time.monotonic()
                    # Non-JSON output (transport errors, rate-limit copy
                    # mirrored from stderr) is still activity — refresh the
                    # kind so a stall heartbeat doesn't report a stale
                    # last_activity_kind while output is flowing.
                    state["last_activity_kind"] = "non_json"
                continue
            for chunk in parsed.text_chunks:
                stdout_buffer.append(chunk)
            # At -v, render one indented line per tool_use so the
            # operator can see what claude is touching (Edit file paths,
            # Bash commands, Grep patterns). Skip in quiet and debug:
            # quiet stays terse, debug already has the raw line.
            if not suppress_content_output and verbosity == _CONSOLE_VERBOSITY_VERBOSE:
                for ev in parsed.events:
                    if ev.get("kind") == "tool_use":
                        name = ev.get("tool_name") or "?"
                        summary = (
                            "[OMITTED]"
                            if not redaction_ready
                            else (ev.get("tool_input_summary") or "")
                        )
                        sys.stderr.write(
                            f"        → {name}: {summary}\n"
                            if summary else f"        → {name}\n"
                        )
                        sys.stderr.flush()
            if parsed.request_id_hint is not None:
                last_request_id["v"] = parsed.request_id_hint
            if parsed.stats is not None:
                # Merge in the most recent request_id seen on an
                # ``assistant`` event — the result envelope itself only
                # has ``session_id``, which is shared across multi-turn
                # calls and is not what ``ClaudeCallEnd.request_id``
                # records.
                rid = last_request_id["v"]
                stats_box["v"] = (
                    replace(parsed.stats, request_id=rid)
                    if rid is not None
                    else parsed.stats
                )
                try:
                    # Advisory bookkeeping: a parser's odd stats object must not kill the pump.
                    reporting = get_active_backend()
                    reported = reported_window_for_model(
                        reporting.resolved_model, parsed.stats.model_windows
                    )
                    if reported is not None:
                        observe_context_window(
                            reporting.name, reporting.resolved_model, reported[0], exact=reported[1]
                        )
                except Exception:  # noqa: BLE001
                    pass
            for ev_kw in (() if suppress_content_output else parsed.events):
                # Emit failures (oversize lines, IO errors, a buggy caller
                # observer) must not kill the pump thread — losing the pump
                # means the ``result`` envelope never gets parsed and the
                # ClaudeCallEnd event carries empty usage. Log and keep
                # streaming.
                _safe_observer_call(
                    run_logger, "claude_stream_event",
                    phase=phase, attempt=attempt, **ev_kw,
                )
            with state_lock:
                state["last_activity_monotonic"] = time.monotonic()
                if parsed.last_tool is not None:
                    state["last_tool"] = parsed.last_tool
                if parsed.last_activity_kind is not None:
                    state["last_activity_kind"] = parsed.last_activity_kind

    def _pump_stderr() -> None:
        verbosity = get_console_verbosity()
        for line in proc.stderr:
            # Live passthrough only at -v/--debug — raw backend stderr can
            # carry paths or prompt fragments outside _summarize_tool_input's
            # redaction rule. The returned stderr_buffer still accumulates
            # every line at every verbosity, so the failure classifier and
            # claude_invoke's failure-tail warn() see today's exact bytes.
            if not suppress_content_output and verbosity >= _CONSOLE_VERBOSITY_VERBOSE:
                sys.stderr.write(line)
                sys.stderr.flush()
            stderr_buffer.append(line)

    def _heartbeat() -> None:
        while True:
            woke = stop.wait(_PROGRESS_INTERVAL_S)
            if woke:
                return
            now = time.monotonic()
            with state_lock:
                silent = now - state["last_activity_monotonic"]
                lt = state["last_tool"]
                lk = state["last_activity_kind"]
            elapsed_ms = int((now - start_monotonic) * 1000)
            silent_ms = int(silent * 1000)
            # Same defensive pattern as the stdout pump: a single
            # oversize / IO-failing / buggy-observer emit must not kill the
            # heartbeat thread — that would silently disable progress
            # logging for the rest of the call. The kill-on-stall check
            # below is outside this block so the safety net still fires
            # when no observability writer is attached.
            _safe_observer_call(
                run_logger, "claude_call_progress",
                phase=phase, attempt=attempt, elapsed_ms=elapsed_ms,
                silent_ms=silent_ms, last_tool=lt, last_activity_kind=lk,
            )
            # ``proc.poll()`` guards the same staleness race the kill
            # ladder's own check below guards: ``silent`` is a wall-clock
            # read that can go stale in the instant the child exits
            # cleanly right at the stall threshold, which would otherwise
            # emit a spurious stall marker immediately before a clean
            # completion.
            if (
                not stall_fired[0]
                and silent >= _STALL_THRESHOLD_S
                and proc.poll() is None
            ):
                stall_fired[0] = True
                _safe_observer_call(
                    run_logger, "claude_call_stall_suspected",
                    phase=phase, attempt=attempt, silent_ms=silent_ms,
                    threshold_ms=int(_STALL_THRESHOLD_S * 1000), last_tool=lt,
                )
            # Kill ladder: two independent thresholds share one one-shot
            # guard (``killed_fired``) and one terminate/grace/kill
            # sequence. Silence past the stall threshold means a wedged
            # ``claude`` binary — without this, ``proc.wait()`` in the main
            # thread blocks indefinitely and pins plan-tool. Elapsed time
            # past ``configured_timeout_s`` is the caller's own bound
            # (``enforce_configured_timeout`` gates it off by default so
            # ``run``'s call sites stay exempt). Configured-timeout is
            # checked first: it is the caller's explicit, usually-shorter
            # bound, and the two are mutually exclusive within one tick.
            elapsed = now - start_monotonic
            if not killed_fired[0]:
                effective_silence = _effective_silence_timeout_s()
                fire_configured = (
                    enforce_configured_timeout
                    and configured_timeout_s is not None
                    and elapsed >= configured_timeout_s
                )
                fire_silence = (
                    not fire_configured
                    and effective_silence is not None
                    and silent >= effective_silence
                )
                if (fire_configured or fire_silence) and proc.poll() is None:
                    # The elapsed/silent thresholds are wall-clock reads that
                    # can go stale in the instant the child exits on its own
                    # right as a tick crosses the threshold — poll() here
                    # (thread-safe, non-blocking) catches that case without
                    # waiting for the main thread's own proc.wait() to
                    # notice, so a call that just completed successfully
                    # isn't killed and misreported as a timeout.
                    killed_fired[0] = True
                    if fire_configured:
                        reason = TerminationReason.CONFIGURED_TIMEOUT
                        label = (
                            f"has run for {int(elapsed)}s (configured "
                            f"timeout {configured_timeout_s}s)"
                        )
                        sentinel_line = (
                            f"{_BACKEND_TIMEOUT_SENTINEL}: configured "
                            f"timeout exceeded after {int(elapsed)}s "
                            f"(threshold {configured_timeout_s}s)\n"
                        )
                    else:
                        reason = TerminationReason.SILENCE_TIMEOUT
                        label = (
                            f"has been silent for {int(silent)}s (kill "
                            f"threshold {int(effective_silence)}s)"
                        )
                        sentinel_line = (
                            f"{_BACKEND_TIMEOUT_SENTINEL}: no activity for "
                            f"{int(silent)}s (threshold "
                            f"{int(effective_silence)}s)\n"
                        )
                    # Recorded — and the sentinel appended to the returned
                    # stderr — before the kill is actually sent, so the
                    # classification is stable by the time ``proc.wait()``
                    # can observe the child exiting.
                    _note_termination_reason(reason_cell, reason_lock, reason)
                    stderr_buffer.append(sentinel_line)
                    print(
                        f"plan-tool: {get_active_backend().name} {label}; "
                        "sending SIGTERM",
                        file=sys.stderr,
                    )
                    kill_signal_used[0] = "SIGTERM"
                    try:
                        proc.terminate()
                    except (OSError, ProcessLookupError):
                        pass
                    # Brief grace window for graceful shutdown, then SIGKILL.
                    if not stop.wait(_KILL_GRACE_S) and proc.poll() is None:
                        print(
                            f"plan-tool: {get_active_backend().name} did "
                            "not exit after SIGTERM; sending SIGKILL",
                            file=sys.stderr,
                        )
                        kill_signal_used[0] = "SIGKILL"
                        try:
                            proc.kill()
                        except (OSError, ProcessLookupError):
                            pass
                    return

    stdout_context = contextvars.copy_context()
    stderr_context = contextvars.copy_context()
    heartbeat_context = contextvars.copy_context()
    t_out = threading.Thread(target=stdout_context.run, args=(_pump_stdout,))
    t_err = threading.Thread(target=stderr_context.run, args=(_pump_stderr,))
    # Heartbeat is a daemon thread so an exception elsewhere can't
    # leave it pinning the process.
    t_hb = threading.Thread(
        target=heartbeat_context.run, args=(_heartbeat,), daemon=True
    )

    # Everything from the ``backend_spawn`` emit through ``proc.wait()``
    # runs with a live child already spawned, so a ``KeyboardInterrupt``
    # anywhere in this window — the emit itself, thread start, the
    # optional stdin write, or ``proc.wait()`` — must still kill and reap
    # ``proc``: t_out/t_err are non-daemon threads blocked reading its
    # still-open pipes, which would otherwise pin the interpreter on exit
    # with no matching ``backend_termination``/``run_interrupted`` ever
    # emitted for the loss. ``started_threads`` tracks which of the three
    # threads actually started so ``finally`` only joins those — a thread
    # whose own ``.start()`` never ran can't be joined.
    started_threads: list[threading.Thread] = []
    try:
        if stream_log_path is not None:
            try:
                # Unredacted: 0700 dir / 0600 file. See run.md "Raw backend
                # stream log".
                stream_log_path.parent.mkdir(
                    mode=0o700, parents=True, exist_ok=True
                )
                if sibling_log_dir is None:
                    # Derived dir only: it must ignore itself (``git add -A``
                    # under ``run --commit``) or the log is not written.
                    stream_log_path.parent.chmod(0o700)
                    ignore = stream_log_path.parent / ".gitignore"
                    if not ignore.is_file():
                        ignore.write_text("*\n", encoding="utf-8")
                fd = os.open(
                    stream_log_path,
                    os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                    0o600,
                )
                stream_log_file[0] = os.fdopen(
                    fd, "w", encoding="utf-8", buffering=1
                )
            except Exception as exc:  # noqa: BLE001 — never fail the call
                # The child is already running; only the log is lost.
                if not _STREAM_LOG_WARNED[0]:
                    _STREAM_LOG_WARNED[0] = True
                    print(
                        f"plan-tool: raw backend stream log unavailable "
                        f"({stream_log_path}: {exc}); further failures "
                        "are not repeated",
                        file=sys.stderr,
                    )
                stream_log_path = None
        if (
            stream_log_path is not None
            and not suppress_content_output
            and get_console_verbosity() >= _CONSOLE_VERBOSITY_DEBUG
        ):
            print(f"plan-tool: raw backend stream -> {stream_log_path}", file=sys.stderr)
        # Popen succeeded — the one production point that actually knows
        # the child's pid, so ``backend_spawn`` fires here and nowhere
        # else. A spawn failure above never reaches this line, which is
        # why that path emits a termination but no matching spawn.
        _safe_observer_call(
            run_logger, "backend_spawn",
            phase=phase, attempt=attempt, backend=get_active_backend().name,
            transport=getattr(transport, "__name__", None),
            # ``getattr`` rather than ``proc.pid`` directly: a real
            # ``Popen`` always has one, but this is evaluated as a call
            # argument outside ``_safe_observer_call``'s own try/except,
            # so a test double lacking the attribute must not raise here.
            child_pid=getattr(proc, "pid", None),
            effective_timeout_ms=(
                int(_effective_timeout_s * 1000)
                if _effective_timeout_s is not None else None
            ),
            prompt_bytes=prompt_transport.prompt_bytes,
            stream_log=(
                stream_log_path.name if stream_log_path is not None else None
            ),
        )
        t_out.start()
        started_threads.append(t_out)
        t_err.start()
        started_threads.append(t_err)
        t_hb.start()
        started_threads.append(t_hb)
        if prompt_transport.stdin_text is not None:
            if proc.stdin is None:
                raise RuntimeError("subprocess stdin pipe is None")
            proc.stdin.write(prompt_transport.stdin_text)
            proc.stdin.close()
        proc.wait()
    except BaseException as exc:
        # Any exception here — most commonly a KeyboardInterrupt from an
        # operator's Ctrl-C — must not leave the child running. Kill
        # outright rather than terminate-then-wait; the caller is
        # already unwinding, so there's no reason for a grace period.
        # ``run_interrupted`` reaches every bound ``run_logger`` — a bare
        # ``RunLogWriter`` (``run_step``'s direct call, via
        # ``launcher.shell_invoker``) as well as a caller-built full
        # observer (``shell.claude_invoke``'s); ``_safe_observer_call``
        # already no-ops for ``None``. Deliberately reaches only that far:
        # ``run_step`` is the sole setter of ``launcher._run_logger_var``,
        # so no ``apply_finding`` caller can hand this fallback a bare
        # writer today — a future caller that starts binding one opts into
        # this same event by construction, not by a change here.
        _finalize_interrupted_call(
            exc,
            proc=proc,
            reason_cell=reason_cell,
            reason_lock=reason_lock,
            run_logger=run_logger,
            phase=phase,
            attempt=attempt,
            call_start_monotonic=call_start_monotonic,
            source=InterruptSource.PROC_WAIT,
        )
        raise
    finally:
        # Always tell the heartbeat to exit; otherwise an exception
        # anywhere in the try above would leak the thread. Moved into
        # ``finally`` (rather than only running after the whole
        # try/finally) so the pump/heartbeat threads are joined on the
        # exception path too, not just the success path.
        stop.set()
        for t in started_threads:
            t.join(timeout=_PROGRESS_INTERVAL_S + 1.0 if t is t_hb else None)
        # Closed here, not after the success path, so Ctrl-C or a failed
        # stdin write cannot leak the descriptor.
        if stream_log_file[0] is not None:
            try:
                stream_log_file[0].close()
            except Exception:  # noqa: BLE001
                pass

    # A normal return with no kill fired and no exception raised has no
    # reason recorded yet — classify it from the exit code. A kill (either
    # threshold) already recorded its own reason before triggering the
    # terminate/kill sequence above, so this never overwrites one.
    if reason_cell[0] is None:
        _note_termination_reason(
            reason_cell,
            reason_lock,
            TerminationReason.COMPLETED
            if proc.returncode == 0
            else TerminationReason.BACKEND_NONZERO,
        )

    with state_lock:
        _silence_at_end = time.monotonic() - state["last_activity_monotonic"]
    _safe_observer_call(
        run_logger, "backend_termination",
        phase=phase, attempt=attempt, backend=get_active_backend().name,
        reason=reason_cell[0].value,
        duration_ms=int((time.monotonic() - call_start_monotonic) * 1000),
        signal_or_timeout=kill_signal_used[0],
        silent_ms=(
            int(_silence_at_end * 1000)
            if kill_signal_used[0] is not None else None
        ),
    )

    return (
        proc.returncode,
        # A configured-timeout/silence-timeout kill (the only two reasons
        # that set kill_signal_used) can land mid-line on non-JSON noise;
        # the partial buffer isn't a reliable response, so discard it
        # rather than returning garbage as the call's stdout.
        "" if kill_signal_used[0] is not None else "".join(stdout_buffer),
        "".join(stderr_buffer),
        stats_box["v"],
    )
