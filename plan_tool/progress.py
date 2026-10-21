"""Lightweight progress reporting for backend-invoking subcommands.

The silent backend-invoking subcommands (``detail``, ``jira``, ``review``,
``create --from*``) call ``shell.claude_invoke``, which buffers stdout
until the subprocess exits. Without a separate channel a user sees no
output for the duration of each claude call (often minutes per step).

This module gives each silent caller a thin reporter that emits
human-readable status lines on **stderr** while the structured stdout
parsers receive byte-identical input. A daemon heartbeat thread emits a
periodic ``Ns elapsed`` line so the user can tell the call is alive
even when it runs much longer than expected.

Stdout is left untouched on purpose: callers like
``plan-tool jira --format json`` pipe stdout into ``jq``. Putting
progress on stderr keeps those pipelines clean.

Public surface:

- :class:`ProgressReporter` — abstract reporter, ``start_step`` returns a
  :class:`StepHandle`.
- :class:`StepHandle` — abstract per-step handle, ``complete`` /
  ``fail`` close out the step and stop the heartbeat thread.
- :class:`StderrReporter` — production reporter (writes to stderr,
  spins up a daemon heartbeat thread).
- :class:`NullReporter` — no-op reporter for tests / dry-run paths.
"""

from __future__ import annotations

import sys
import threading
import time
from abc import ABC, abstractmethod
from typing import Callable, Optional, Protocol, TextIO

from .shell import pop_active_notifier, push_active_notifier
from .style import (
    BOLD,
    BOLD_CYAN,
    BOLD_GREEN,
    BOLD_RED,
    DIM,
    RED,
    YELLOW,
    color_enabled,
    paint,
)


# Cadence at which the production heartbeat thread emits ``Ns elapsed`` lines.
# Module-level so callers don't pass it through; tunable from one place.
HEARTBEAT_INTERVAL_S: float = 15.0

# Static "still working" glyph fronting each heartbeat tick. A rotating
# spinner is pointless here — the heartbeat only redraws every
# ``HEARTBEAT_INTERVAL_S`` (15s), so any animation would read as frozen.
# The elapsed counter is the live signal; this glyph just marks the line as
# an in-progress sub-line under the start line.
_WORKING_GLYPH = "⋯"

# Glyph fronting an in-flight ``notice`` sub-line (a retry / wait advisory
# emitted mid-step). A circular-arrow reads as "trying again" and the
# yellow keeps it visible-but-not-alarming — distinct from the failure ✗
# (red) so a recovered hiccup never looks like a dead step.
_NOTICE_GLYPH = "↻"


class _ClaudeCallStartSink(Protocol):
    """Run-log tee target. ``_RunLogger`` in ``cli.py`` satisfies it.

    Kept structural (Protocol, not ABC) so callers don't have to import
    a class from ``cli``/``run_log`` just to construct a reporter, and
    so tests can pass a recording fake without subclassing. Underscore
    name signals "implementation detail of progress.py", not a public
    API anyone outside this module should depend on.
    """

    def claude_call_start(
        self,
        phase: str,
        attempt: int,
        prompt_bytes: int,
        prompt_sha256: Optional[str] = None,
    ) -> None: ...


class SupportsNotice(Protocol):
    """Structural type for an in-flight diagnostic sink.

    :class:`StepHandle` satisfies it. Lower layers that retry mid-step
    (``shell.claude_invoke``, the launcher streaming loop) accept this
    rather than importing :class:`StepHandle` so a retry advisory clears
    the in-place heartbeat tick before printing — the historical
    straight-to-stderr ``print`` collided with it (``165s elapsedwarning:
    …``). Kept a ``Protocol`` (not the ABC) so ``shell`` stays decoupled
    and tests can pass a recording fake.
    """

    def notice(self, message: str, *, kind: str = "retry") -> None: ...


class StepHandle(ABC):
    """Outcome callbacks for one claude call."""

    @abstractmethod
    def complete(self, elapsed_s: float, response_bytes: int) -> None:
        """Mark the step finished. Stops the heartbeat thread."""

    @abstractmethod
    def fail(self, elapsed_s: float, reason: str) -> None:
        """Mark the step failed with a short human-readable reason. Stops the heartbeat."""

    def notice(self, message: str, *, kind: str = "retry") -> None:
        """Emit an in-flight advisory (a retry / wait notice) without
        colliding with the heartbeat tick. ``kind="retry"`` also marks the
        step recovered-on-success, so :meth:`complete` annotates its done
        line; other kinds (``"info"``) print cleanly but don't.

        Concrete (not abstract): the advisory channel is optional, so a
        handle that doesn't render in-flight notices — the null handle, a
        test fake — inherits this no-op rather than being forced to stub it.
        :class:`_StderrStepHandle` overrides it with the real rendering.
        """
        return None


class ProgressReporter(ABC):
    """Per-call progress reporting. ``start_step`` yields a :class:`StepHandle`."""

    @abstractmethod
    def start_step(
        self,
        idx: int,
        total: int,
        label: str,
        *,
        prefix: Optional[str] = None,
        phase: Optional[str] = None,
        attempt: int = 1,
        prompt_bytes: int = 0,
        prompt_sha256: Optional[str] = None,
    ) -> StepHandle:
        """Open a new step. ``label`` is a short human description (e.g. ``"step 3: Wire …"``).

        ``prefix`` is an optional structured at-a-glance descriptor (e.g.
        ``"step 8 / iter 2-of-3 / scan"``) rendered verbatim and identically
        on the start, tick, and done lines so an operator reads the phase /
        iteration position off any single line. When set it stands in for
        the start line's label and the sub-lines' activity label; when
        ``None`` the activity label is derived from ``label`` as before.

        ``phase`` / ``attempt`` / ``prompt_bytes`` / ``prompt_sha256`` are advisory metadata
        used by reporters that tee into a run-log writer; ABC default of
        ``phase=None`` keeps the no-run-log path a no-op.
        """


# --- Null implementation ----------------------------------------------------


class _NullStepHandle(StepHandle):
    # ``notice`` is inherited: ``StepHandle`` defines it concretely as a
    # no-op precisely so the null handle need not stub it. Only the two
    # abstract callbacks require an implementation here.
    def complete(self, elapsed_s: float, response_bytes: int) -> None:
        return None

    def fail(self, elapsed_s: float, reason: str) -> None:
        return None


class NullReporter(ProgressReporter):
    """Silent reporter. Use in tests and ``--dry-run`` paths."""

    def start_step(
        self,
        idx: int,
        total: int,
        label: str,
        *,
        prefix: Optional[str] = None,
        phase: Optional[str] = None,
        attempt: int = 1,
        prompt_bytes: int = 0,
        prompt_sha256: Optional[str] = None,
    ) -> StepHandle:
        return _NullStepHandle()


# --- Stderr implementation --------------------------------------------------


class _StderrStepHandle(StepHandle):
    """One step's lifecycle on stderr, with a daemon heartbeat thread.

    Lifecycle: writes the start line during construction, spawns a daemon
    thread that emits an elapsed-time tick every ``interval`` seconds, and
    tears the thread down when ``complete`` or ``fail`` runs. The thread is
    daemonic so a SIGINT at the parent kills it without ceremony; the
    explicit ``join`` on completion just guarantees the elapsed line lands
    before the closing line.

    Output shape (color TTY) — a status glyph fronts every line so the
    eye locks onto state (running ▸, done ✓, failed ✗) before reading. The
    ``[i/n]`` counter renders only for a real multi-item batch (``n>1`` —
    a step sweep, audit passes); a singleton ``[1/1]`` carried no
    information and is dropped:

        ▸ [4/8] step 4: Add DeleteUserEnqueueResult custom type…
          ⋯ step 4 · 45s elapsed                           ← elapsed updates in place
          ✓ step 4 · done in 75s (9.4 KB response)

    With styling off (non-TTY, ``NO_COLOR``) the layout falls back to the
    glyph-free, 8-space-indent form so piped logs and tests stay
    byte-stable:

        [4/8] step 4: Add DeleteUserEnqueueResult custom type…
                step 4 · 45s elapsed
                step 4 · done in 75s (9.4 KB response)

    When a ``prefix`` is supplied (e.g. the convergence loop passes
    ``"step 8 / iter 2-of-3 / scan"``) it becomes the single at-a-glance
    identifier shared verbatim by all three line kinds, so phase /
    iteration transitions read off any one line:

        ▸ step 8 / iter 2-of-3 / scan
          ⋯ step 8 / iter 2-of-3 / scan · 45s elapsed
          ✓ step 8 / iter 2-of-3 / scan · done in 75s (9.4 KB response)

    Without a prefix the start line carries the full (truncated) label,
    and the heartbeat tick + closing line carry a tightly capped *activity
    label* (``_ACTIVITY_LABEL_CAP`` chars — the label's head up to the
    first ``": "``, e.g. ``iterate step 5``) instead of the full title, so
    any single sub-line still identifies the work yet stays short. Keeping
    the sub-lines compact preserves the no-flood rationale: when the
    operator's terminal preserves bytes across ``\\r`` (iTerm scrollback,
    Claude Code transcript capture) the title isn't repeated on every tick.

    On a non-TTY (CI logs, redirected output) each tick lands on its own
    line so timing data isn't lost in pipelines.
    """

    # Indent for sub-lines (heartbeat / done / FAILED) when styling is off.
    # The styled layout uses a tighter 2-space indent plus a status glyph.
    _SUBLINE_INDENT = " " * 8
    _STYLED_INDENT = " " * 2
    # Label cap for the start line. Long apply-finding labels otherwise
    # wrap and bury the line under multiple terminal rows; the full label
    # is still captured in the run log for forensics. 90 chars fits a
    # standard 100-col terminal after the ``[i/n] `` prefix.
    _LABEL_CAP = 90
    # Hard cap for the *activity label* fronting each heartbeat tick and the
    # closing line. Deliberately tight: the sub-line repeats on every tick,
    # so a long label would re-flood the terminal across ``\r`` — the exact
    # noise the tick was kept short to avoid. The head before the first
    # ``": "`` (e.g. ``iterate step 5``) is almost always well under this;
    # the cap only bites pathological labels.
    _ACTIVITY_LABEL_CAP = 40

    def __init__(
        self,
        stream: TextIO,
        idx: int,
        total: int,
        label: str,
        *,
        prefix: Optional[str] = None,
        interval: float,
        clock: Callable[[], float],
    ) -> None:
        self._stream = stream
        self._interval = interval
        self._clock = clock
        self._start = clock()
        self._done = threading.Event()
        # ``isatty`` may be absent on some stream types (StringIO buffers
        # used by tests); treat absent / raising as non-TTY so the
        # deterministic line-per-tick path runs in tests.
        try:
            self._tty = bool(getattr(stream, "isatty", lambda: False)())
        except (ValueError, OSError):
            self._tty = False
        # Whether to emit ANSI styling + status glyphs. Decoupled from
        # ``_tty`` (in-place \\r updates) so ``NO_COLOR`` / ``FORCE_COLOR``
        # and non-TTY test buffers pick the plain layout regardless.
        self._color = color_enabled(stream)
        # Track how many *visible* columns the most recent in-place tick
        # used so ``complete`` / ``fail`` can clear the line before printing
        # the final status. Visible (not byte) length keeps the math right
        # when the styled tick carries zero-width ANSI escapes.
        self._last_tick_len = 0
        # How many ``kind="retry"`` notices fired during this step. Drives
        # the "recovered after N retr(y/ies)" annotation on the done line so
        # a call that only succeeded on a retry is self-documenting (rather
        # than indistinguishable from a clean first-try run).
        self._retry_count = 0
        self._idx = idx
        self._total = total
        self._prefix = prefix
        # Single-ellipsis truncation. Building the start-line label exactly
        # once avoids the ``label……`` doubling a previous unconditional
        # trailing ``…`` produced when the label was already truncated.
        self._short_label = self._truncate(label, self._LABEL_CAP)

        # Activity label shared by the heartbeat tick and closing line.
        # With a structured ``prefix`` the prefix IS the identifier — cap
        # it once here and reuse the same capped value on the start line so
        # all three line kinds carry a byte-identical descriptor. Without a
        # prefix, fall back to the label's head up to the first ``": "``
        # (e.g. ``iterate step 5`` from ``iterate step 5: scanning for
        # findings``); ``partition`` returns the whole string as the head
        # when there's no ``": "`` separator.
        if prefix is not None:
            self._activity_label = self._truncate(prefix, self._ACTIVITY_LABEL_CAP)
        else:
            head = label.partition(": ")[0]
            self._activity_label = self._truncate(head, self._ACTIVITY_LABEL_CAP)

        self._stream.write(self._start_line())
        self._stream.flush()

        self._thread = threading.Thread(target=self._heartbeat, daemon=True)
        self._thread.start()

        # Bind this handle as the active in-flight diagnostic sink so a
        # retry deep inside ``shell.claude_invoke`` (which has no direct
        # reference to the handle) routes its advisory through ``notice``
        # and clears the tick. Popped in ``complete``/``fail``. Token-based
        # so sequential steps restore LIFO-correctly.
        self._notifier_token = push_active_notifier(self)

    @staticmethod
    def _truncate(text: str, cap: int) -> str:
        """Cap ``text`` at ``cap`` visible chars, ellipsizing the overflow."""
        if len(text) <= cap:
            return text
        return text[: cap - 1] + "…"

    def _counter_prefix(self) -> str:
        """``[i/n] `` (trailing space, dimmed when styled) for a real batch.

        Returns ``""`` for a singleton (``total <= 1``): a ``[1/1]`` told
        the operator nothing, so suppressing it means a bracket on screen
        always signals genuine batch progress (a step sweep, audit
        samples).
        """
        if self._total <= 1:
            return ""
        return paint(f"[{self._idx}/{self._total}]", DIM, enabled=self._color) + " "

    def _start_line(self) -> str:
        """Build the start line: ``▸ [i/n] step N: <title>`` (or a prefix).

        When styled, a cyan ▸ marks "running" and the identifier is bolded
        so it pops. The ``[i/n]`` counter only appears for a real batch
        (see :meth:`_counter_prefix`). With a structured ``prefix`` the
        whole prefix is the identifier; otherwise the ``step N:`` head is
        bolded and the title stays plain. Plain mode drops the glyph and
        styling.
        """
        counter = self._counter_prefix()
        if not self._color:
            body = (
                self._activity_label
                if self._prefix is not None
                else self._short_label
            )
            return f"{counter}{body}\n"
        marker = paint("▸", BOLD_CYAN, enabled=True)
        if self._prefix is not None:
            label = paint(self._activity_label, BOLD, enabled=True)
        else:
            # Bold the ``step N:`` head (everything up to and including the
            # first ``: ``) and leave the title plain; cosmetic only.
            head, sep, tail = self._short_label.partition(": ")
            label = (
                paint(head + sep, BOLD, enabled=True) + tail
                if sep
                else self._short_label
            )
        return f"{marker} {counter}{label}\n"

    @property
    def thread(self) -> threading.Thread:
        """Test-only handle on the heartbeat thread (daemon flag, alive state)."""
        return self._thread

    def _tick_text(self, elapsed_s: float) -> tuple[str, int]:
        """Render one heartbeat tick: ``(styled_text, visible_len)``.

        Format: ``  ⋯ <activity> · Ns elapsed`` (styled) or ``        <activity>
        · Ns elapsed`` (plain). The capped activity label identifies the
        work without repeating the full title that sits on the start line —
        repeating the title on every tick produces a wall of bytes when the
        terminal preserves output across ``\\r`` (iTerm scrollback, Claude
        Code transcript capture). ``visible_len`` is the printed-column
        count (ANSI escapes excluded) so the in-place overwrite pads
        correctly.
        """
        secs = f"{int(elapsed_s)}s elapsed"
        body_text = f"{self._activity_label} · {secs}"
        if not self._color:
            body = f"{self._SUBLINE_INDENT}{body_text}"
            return body, len(body)
        plain = f"{self._STYLED_INDENT}{_WORKING_GLYPH} {body_text}"
        styled = (
            f"{self._STYLED_INDENT}{paint(_WORKING_GLYPH, DIM, enabled=True)} "
            f"{paint(body_text, DIM, enabled=True)}"
        )
        return styled, len(plain)

    def _heartbeat(self) -> None:
        # ``Event.wait`` returns True when the event is set, False on timeout.
        # Looping while the wait times out emits a tick line and continues;
        # once the event is set, the loop exits cleanly.
        while not self._done.wait(self._interval):
            elapsed = self._clock() - self._start
            tick, visible = self._tick_text(elapsed)
            # During pytest capture teardown the captured stream can close
            # while this daemon thread is still mid-loop, so a write raises
            # ``ValueError: I/O operation on closed file`` — benign but it
            # spams every full-suite run. The tick is advisory, so skip a
            # stream that's already closed and swallow the race where the
            # close lands between this check and the write below.
            if getattr(self._stream, "closed", False):
                return
            try:
                if self._tty:
                    # Pad with spaces to overwrite any tail from a longer
                    # previous tick (e.g. ``99s`` → ``100s`` widens by one,
                    # but ``999s`` → ``1000s`` widens again — defensive).
                    pad = max(0, self._last_tick_len - visible)
                    self._stream.write("\r" + tick + (" " * pad))
                    self._stream.flush()
                    self._last_tick_len = visible
                else:
                    self._stream.write(tick + "\n")
                    self._stream.flush()
            except ValueError:
                return

    def _stop_heartbeat(self) -> None:
        self._done.set()
        # Short bounded join: the heartbeat thread blocks in Event.wait, so
        # setting the event wakes it immediately. A small timeout keeps a
        # buggy thread from stalling completion forever.
        self._thread.join(timeout=1.0)

    def _finalize_inplace_tick(self) -> None:
        """End the in-place tick line so the next line starts fresh.

        On TTY we want the final ``done``/``FAILED`` line to land on its
        own row, not overwrite the tick at column 0. Writing ``\\r`` +
        spaces clears the tick visually; the trailing ``\\n`` then moves
        the cursor down so the subsequent write doesn't merge into the
        cleared row. No-op on non-TTY (each tick already ended with
        ``\\n``).
        """
        if self._tty and self._last_tick_len > 0:
            self._stream.write("\r" + (" " * self._last_tick_len) + "\r")
            self._stream.flush()
            self._last_tick_len = 0

    def _release_notifier(self) -> None:
        """Unbind this handle as the active in-flight sink (idempotent).

        Called from both ``complete`` and ``fail`` — whichever closes the
        step — so the next step's ``claude_invoke`` doesn't route notices
        into a finished handle.
        """
        token = self._notifier_token
        if token is not None:
            self._notifier_token = None
            pop_active_notifier(token)

    def notice(self, message: str, *, kind: str = "retry") -> None:
        # Clear the in-place heartbeat tick first so the advisory lands on
        # its own row instead of splicing onto ``…165s elapsed`` — the exact
        # collision this method exists to prevent. The heartbeat redraws a
        # fresh tick on its next interval (``_last_tick_len`` was reset).
        if kind == "retry":
            self._retry_count += 1
        self._finalize_inplace_tick()
        body_text = f"{self._activity_label} · {message}"
        if self._color:
            line = (
                f"{self._STYLED_INDENT}{paint(_NOTICE_GLYPH, YELLOW, enabled=True)} "
                f"{paint(body_text, DIM, enabled=True)}\n"
            )
        else:
            line = f"{self._SUBLINE_INDENT}{body_text}\n"
        if getattr(self._stream, "closed", False):
            return
        try:
            self._stream.write(line)
            self._stream.flush()
        except ValueError:
            return

    def _recovered_suffix(self) -> str:
        """`` — recovered after N retr(y/ies)`` when the step retried, else ``""``."""
        if self._retry_count <= 0:
            return ""
        plural = "retry" if self._retry_count == 1 else "retries"
        return f" — recovered after {self._retry_count} {plural}"

    def complete(self, elapsed_s: float, response_bytes: int) -> None:
        self._stop_heartbeat()
        self._finalize_inplace_tick()
        kb = response_bytes / 1024
        # Carry the capped activity label into the closing line so a single
        # log line — start, tick, or done — identifies the work it covers.
        # The recovered-suffix (empty on a clean run) keeps the historical
        # ``done in Ns (X KB response)`` tail intact so existing assertions
        # and log greps don't shift.
        body = (
            f"{self._activity_label} · done in {int(elapsed_s)}s"
            f"{self._recovered_suffix()} ({kb:.1f} KB response)"
        )
        if self._color:
            line = (
                f"{self._STYLED_INDENT}{paint('✓', BOLD_GREEN, enabled=True)} "
                f"{paint(body, DIM, enabled=True)}\n"
            )
        else:
            line = f"{self._SUBLINE_INDENT}{body}\n"
        self._stream.write(line)
        self._stream.flush()
        self._release_notifier()

    def fail(self, elapsed_s: float, reason: str) -> None:
        self._stop_heartbeat()
        self._finalize_inplace_tick()
        body = f"{self._activity_label} · FAILED in {int(elapsed_s)}s: {reason}"
        if self._color:
            line = (
                f"{self._STYLED_INDENT}{paint('✗', BOLD_RED, enabled=True)} "
                f"{paint(body, RED, enabled=True)}\n"
            )
        else:
            line = f"{self._SUBLINE_INDENT}{body}\n"
        self._stream.write(line)
        self._stream.flush()
        self._release_notifier()


class StderrReporter(ProgressReporter):
    """Production reporter. Writes to stderr; spins up one daemon heartbeat thread per step.

    ``stream`` is resolved at ``start_step`` time (not construction) so a
    test that captures ``sys.stderr`` after the reporter is built still
    intercepts the output. ``interval`` and ``clock`` are tunable for
    deterministic tests.
    """

    def __init__(
        self,
        stream: Optional[TextIO] = None,
        *,
        interval: float = HEARTBEAT_INTERVAL_S,
        clock: Callable[[], float] = time.monotonic,
        run_log: Optional[_ClaudeCallStartSink] = None,
    ) -> None:
        self._stream = stream
        self._interval = interval
        self._clock = clock
        self._run_log = run_log

    def start_step(
        self,
        idx: int,
        total: int,
        label: str,
        *,
        prefix: Optional[str] = None,
        phase: Optional[str] = None,
        attempt: int = 1,
        prompt_bytes: int = 0,
        prompt_sha256: Optional[str] = None,
    ) -> StepHandle:
        stream = self._stream if self._stream is not None else sys.stderr
        handle = _StderrStepHandle(
            stream,
            idx,
            total,
            label,
            prefix=prefix,
            interval=self._interval,
            clock=self._clock,
        )
        # Tee into the run log only when both a sink is bound and the
        # caller actually labels the step with a phase. ``ClaudeCallEnd``
        # lives in ``shell.claude_invoke`` (step 2), not here — emitting
        # it from ``complete`` / ``fail`` would either double-count or
        # lack the rc / tokens envelope.
        if self._run_log is not None and phase is not None:
            self._run_log.claude_call_start(
                phase, attempt, prompt_bytes, prompt_sha256=prompt_sha256
            )
        return handle
