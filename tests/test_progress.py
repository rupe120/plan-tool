"""Tests for plan_tool.progress.

Heartbeat tests use a fast interval and a controllable clock so the
suite never sleeps for the production 15s cadence. No real claude
subprocess is involved here — this module is upstream of every silent
caller.
"""

from __future__ import annotations

import io
import threading
import time

import pytest

from plan_tool.progress import (
    HEARTBEAT_INTERVAL_S,
    NullReporter,
    StderrReporter,
)


class TestNullReporter:
    def test_writes_nothing_and_no_thread(self) -> None:
        active_before = threading.active_count()
        r = NullReporter()
        h = r.start_step(1, 3, "step 1: example")
        h.complete(0.5, response_bytes=1024)
        h.fail(0.5, "ignored anyway")
        # No thread created.
        assert threading.active_count() == active_before


class TestStderrReporterStartLine:
    def test_emits_start_line(self) -> None:
        buf = io.StringIO()
        r = StderrReporter(buf, interval=10.0)
        r.start_step(2, 6, "step 3: Build the parser")
        # Heartbeat won't fire (interval >> any test runtime here).
        # No trailing ellipsis: the heartbeat tick conveys "running"; an
        # unconditional ``…`` here previously produced ``label……`` when
        # the label itself was truncated.
        assert "[2/6] step 3: Build the parser\n" in buf.getvalue()


class TestStderrReporterCompletion:
    def test_complete_writes_done_line(self) -> None:
        buf = io.StringIO()
        r = StderrReporter(buf, interval=10.0)
        h = r.start_step(1, 1, "step 1: x")
        h.complete(elapsed_s=4.0, response_bytes=2048)
        out = buf.getvalue()
        # Singleton (n=1) → the ``[1/1]`` counter is suppressed; the start
        # line is just the full label.
        assert "step 1: x\n" in out
        assert "[1/1]" not in out
        # The done line carries the capped activity label (head before
        # ``": "``) so a single log line identifies the work it covers.
        assert "step 1 · done in 4s" in out
        assert "2.0 KB response" in out

    def test_fail_writes_failed_line(self) -> None:
        buf = io.StringIO()
        r = StderrReporter(buf, interval=10.0)
        h = r.start_step(1, 1, "step 1: x")
        h.fail(elapsed_s=2.0, reason="claude returned an unparseable response")
        out = buf.getvalue()
        assert (
            "step 1 · FAILED in 2s: claude returned an unparseable response"
        ) in out

    def test_response_bytes_zero_renders_zero(self) -> None:
        buf = io.StringIO()
        r = StderrReporter(buf, interval=10.0)
        h = r.start_step(1, 1, "step 1: x")
        h.complete(elapsed_s=0.0, response_bytes=0)
        assert "0.0 KB response" in buf.getvalue()


class TestStderrReporterHeartbeat:
    def test_emits_tick_when_interval_elapses(self) -> None:
        """A short interval and an artificial clock prove the tick fires."""
        buf = io.StringIO()
        # Use a real (short) interval — the heartbeat thread sleeps on a
        # threading.Event with a real timeout. ``clock`` is decoupled so
        # the elapsed values in the tick lines are deterministic.
        ticks = iter([0.0, 7.0, 14.0])

        def clock() -> float:
            try:
                return next(ticks)
            except StopIteration:
                return 14.0

        r = StderrReporter(buf, interval=0.05, clock=clock)
        h = r.start_step(1, 1, "step 1: x")
        # Wait long enough that at least one tick fires.
        time.sleep(0.18)
        h.complete(elapsed_s=14.0, response_bytes=512)
        out = buf.getvalue()
        # At least one heartbeat line landed before completion.
        assert "elapsed" in out
        assert "done in 14s" in out

    def test_heartbeat_thread_is_daemon(self) -> None:
        """SIGINT at the parent must not be blocked by a non-daemon thread."""
        buf = io.StringIO()
        r = StderrReporter(buf, interval=10.0)
        h = r.start_step(1, 1, "step 1: x")
        # Internal: confirm the thread is daemon. A non-daemon heartbeat
        # would prevent process exit on Ctrl-C.
        assert h.thread.daemon is True  # type: ignore[attr-defined]
        h.complete(elapsed_s=0.0, response_bytes=0)

    def test_heartbeat_thread_terminates_on_complete(self) -> None:
        buf = io.StringIO()
        r = StderrReporter(buf, interval=10.0)
        h = r.start_step(1, 1, "step 1: x")
        thread = h.thread  # type: ignore[attr-defined]
        h.complete(elapsed_s=0.0, response_bytes=0)
        # Bounded wait — should be near-instant since complete sets the event.
        thread.join(timeout=2.0)
        assert not thread.is_alive()

    def test_heartbeat_thread_terminates_on_fail(self) -> None:
        buf = io.StringIO()
        r = StderrReporter(buf, interval=10.0)
        h = r.start_step(1, 1, "step 1: x")
        thread = h.thread  # type: ignore[attr-defined]
        h.fail(elapsed_s=0.0, reason="boom")
        thread.join(timeout=2.0)
        assert not thread.is_alive()


def _fixed_clock(values: list[float]):
    """Deterministic clock: yields ``values`` in order, then repeats the last."""
    it = iter(values)
    last = values[-1]

    def clock() -> float:
        nonlocal last
        try:
            last = next(it)
        except StopIteration:
            pass
        return last

    return clock


class _TogglingStream:
    """A non-TTY stream whose ``closed`` flag can be flipped at will.

    Writing while ``closed`` raises ``ValueError`` exactly like a real
    closed file object, so the heartbeat's closed-stream guard can be
    exercised deterministically.
    """

    def __init__(self) -> None:
        self.closed = False
        self.writes: list[str] = []

    def write(self, s: str) -> int:
        if self.closed:
            raise ValueError("I/O operation on closed file")
        self.writes.append(s)
        return len(s)

    def flush(self) -> None:
        if self.closed:
            raise ValueError("I/O operation on closed file")

    def isatty(self) -> bool:
        return False


class TestStderrReporterActivityLabel:
    """The tick and closing lines front a tightly capped activity label."""

    def test_tick_and_done_carry_activity_label_head(self) -> None:
        """The sub-lines show the label head (before ``": "``), not the title."""
        buf = io.StringIO()
        r = StderrReporter(buf, interval=0.02, clock=_fixed_clock([0.0, 7.0]))
        h = r.start_step(1, 1, "iterate step 5: scanning for findings")
        time.sleep(0.12)
        # 4506 / 1024 == 4.4 KB.
        h.complete(elapsed_s=7.0, response_bytes=4506)
        out = buf.getvalue()
        # Tick: head only, joined to the elapsed counter with " · ".
        assert "iterate step 5 · 7s elapsed" in out
        # Done: same head, joined to the completion body.
        assert "iterate step 5 · done in 7s (4.4 KB response)" in out

    def test_fail_carries_activity_label_head(self) -> None:
        buf = io.StringIO()
        r = StderrReporter(buf, interval=10.0)
        h = r.start_step(1, 1, "apply-finding step 2: do the thing")
        h.fail(elapsed_s=3.0, reason="boom")
        assert "apply-finding step 2 · FAILED in 3s: boom" in buf.getvalue()

    def test_label_without_separator_used_whole(self) -> None:
        """A label with no ``": "`` becomes the activity label verbatim (under cap)."""
        buf = io.StringIO()
        r = StderrReporter(buf, interval=10.0)
        h = r.start_step(1, 1, "Distilling lessons from step 5")
        h.complete(elapsed_s=1.0, response_bytes=0)
        assert "Distilling lessons from step 5 · done in 1s" in buf.getvalue()

    def test_activity_label_hard_capped_at_40(self) -> None:
        """A head longer than the cap is truncated to exactly 40 visible chars."""
        buf = io.StringIO()
        # 60-char head, no ": ", so the whole thing is the head and the cap
        # must bite. The start line keeps the full label; only the sub-lines
        # are capped.
        long_head = "Z" * 60
        r = StderrReporter(buf, interval=10.0)
        h = r.start_step(1, 1, long_head)
        h.complete(elapsed_s=1.0, response_bytes=0)
        out = buf.getvalue()
        capped = "Z" * 39 + "…"  # 39 chars + ellipsis == 40 visible chars
        assert f"{capped} · done in 1s" in out
        # The cap is exact: 40 Z's never appears on the done line.
        assert f"{'Z' * 40} · done in" not in out


class TestStderrReporterBracketCounter:
    """``[i/n]`` renders only for a real batch (n>1); singletons drop it."""

    def test_singleton_suppresses_counter(self) -> None:
        buf = io.StringIO()
        r = StderrReporter(buf, interval=10.0)
        r.start_step(1, 1, "step 1: solo")
        out = buf.getvalue()
        # No bracket at all — the start line is just the label.
        assert out == "step 1: solo\n"
        assert "[1/1]" not in out

    def test_batch_renders_counter(self) -> None:
        """A real multi-item sweep keeps ``[4/8]``."""
        buf = io.StringIO()
        r = StderrReporter(buf, interval=10.0)
        r.start_step(4, 8, "step 4: sweep")
        assert "[4/8] step 4: sweep\n" in buf.getvalue()

    def test_two_of_three_renders_counter(self) -> None:
        """Audit-sample style ``[2/3]`` (n>1) still renders."""
        buf = io.StringIO()
        r = StderrReporter(buf, interval=10.0)
        r.start_step(2, 3, "audit sample")
        assert "[2/3] audit sample\n" in buf.getvalue()


class TestStderrReporterStructuredPrefix:
    """A structured ``prefix`` rides the start, tick, and done lines verbatim."""

    def test_prefix_shared_across_start_tick_done(self) -> None:
        buf = io.StringIO()
        r = StderrReporter(buf, interval=0.02, clock=_fixed_clock([0.0, 7.0]))
        h = r.start_step(
            1,
            1,
            "iterate step 8: scanning for findings",
            prefix="step 8 / iter 2-of-3 / scan",
        )
        time.sleep(0.12)
        # 4506 / 1024 == 4.4 KB.
        h.complete(elapsed_s=7.0, response_bytes=4506)
        out = buf.getvalue()
        # Start: the prefix stands in for the label; singleton drops [1/1].
        assert "step 8 / iter 2-of-3 / scan\n" in out
        assert "[1/1]" not in out
        # Tick: same prefix joined to the elapsed counter.
        assert "step 8 / iter 2-of-3 / scan · 7s elapsed" in out
        # Done: same prefix joined to the completion body.
        assert (
            "step 8 / iter 2-of-3 / scan · done in 7s (4.4 KB response)"
        ) in out
        # The verbose label never appears — the prefix subsumed it.
        assert "scanning for findings" not in out

    def test_prefix_on_fail_line(self) -> None:
        buf = io.StringIO()
        r = StderrReporter(buf, interval=10.0)
        h = r.start_step(
            1,
            1,
            "iterate step 8: applying",
            prefix="step 8 / iter 2-of-3 / apply 1-of-3",
        )
        h.fail(elapsed_s=3.0, reason="boom")
        assert (
            "step 8 / iter 2-of-3 / apply 1-of-3 · FAILED in 3s: boom"
        ) in buf.getvalue()

    def test_prefix_and_batch_counter_are_independent(self) -> None:
        """A prefix and a real batch counter both render (n>1)."""
        buf = io.StringIO()
        r = StderrReporter(buf, interval=10.0)
        r.start_step(2, 4, "x", prefix="step 8 / iter 2-of-3 / apply 2-of-4")
        assert (
            "[2/4] step 8 / iter 2-of-3 / apply 2-of-4\n"
        ) in buf.getvalue()


class TestStderrReporterClosedStreamGuard:
    def test_heartbeat_skips_closed_stream_without_raising(self) -> None:
        """A stream closed mid-run must not let the heartbeat thread raise."""
        stream = _TogglingStream()
        raised: list[BaseException] = []

        def hook(args: threading.ExceptHookArgs) -> None:
            if args.exc_value is not None:
                raised.append(args.exc_value)

        original_hook = threading.excepthook
        threading.excepthook = hook
        try:
            r = StderrReporter(stream, interval=0.02)
            h = r.start_step(1, 1, "step 1: x")
            thread = h.thread  # type: ignore[attr-defined]
            # Simulate pytest capture teardown closing the stream under the
            # daemon thread; ticks during this window must be swallowed.
            stream.closed = True
            time.sleep(0.12)
            # Reopen so completion can write its line cleanly (complete runs
            # on the main thread and is outside the guarded heartbeat path).
            stream.closed = False
            h.complete(elapsed_s=0.0, response_bytes=0)
            thread.join(timeout=2.0)
        finally:
            threading.excepthook = original_hook
        assert raised == []
        assert not thread.is_alive()


class TestHeartbeatIntervalConstant:
    def test_default_is_15s(self) -> None:
        """Regression guard: spec calls out 15s as the default cadence."""
        assert HEARTBEAT_INTERVAL_S == 15.0


class _RecordingTee:
    """Structural ``_ClaudeCallStartSink`` for the StderrReporter tee tests.

    Captures arguments rather than persisting; satisfies the protocol via
    duck typing (no subclass needed). The corresponding ClaudeCallEnd is
    emitted by ``shell.claude_invoke``, not by the reporter, so we don't
    record one here.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, int, int]] = []

    def claude_call_start(
        self,
        phase: str,
        attempt: int,
        prompt_bytes: int,
        prompt_sha256: str | None = None,
    ) -> None:
        self.calls.append((phase, attempt, prompt_bytes))


class TestStderrReporterRunLogTee:
    def test_start_step_emits_claude_call_start_when_phase_and_tee_set(self) -> None:
        tee = _RecordingTee()
        r = StderrReporter(io.StringIO(), interval=10.0, run_log=tee)
        h = r.start_step(
            1, 1, "x", phase="propose_steps", attempt=1, prompt_bytes=42
        )
        h.complete(elapsed_s=0.0, response_bytes=0)
        assert tee.calls == [("propose_steps", 1, 42)]

    def test_start_step_no_emit_when_phase_missing(self) -> None:
        tee = _RecordingTee()
        r = StderrReporter(io.StringIO(), interval=10.0, run_log=tee)
        h = r.start_step(1, 1, "x")
        h.complete(elapsed_s=0.0, response_bytes=0)
        assert tee.calls == []

    def test_start_step_no_emit_when_tee_unbound(self) -> None:
        r = StderrReporter(io.StringIO(), interval=10.0)
        # Must not raise even with a phase label and no tee installed.
        h = r.start_step(1, 1, "x", phase="propose_steps")
        h.complete(elapsed_s=0.0, response_bytes=0)

    def test_complete_does_not_emit_call_end(self) -> None:
        """``ClaudeCallEnd`` is owned by ``shell.claude_invoke`` (step 2)."""
        tee = _RecordingTee()
        r = StderrReporter(io.StringIO(), interval=10.0, run_log=tee)
        h = r.start_step(1, 1, "x", phase="propose_steps")
        h.complete(elapsed_s=1.0, response_bytes=10)
        # Still only the one start tap. End would land on the shell sink.
        assert len(tee.calls) == 1


class TestStderrReporterNotice:
    """In-flight ``notice`` advisories land on their own line and feed the
    recovered-after-N annotation — they never splice onto the heartbeat tick
    the way the old straight-to-stderr ``print`` did (``165s elapsedwarning:``).
    """

    def test_notice_writes_clean_subline(self) -> None:
        buf = io.StringIO()
        r = StderrReporter(buf, interval=10.0)
        h = r.start_step(1, 1, "Proposing initial steps")
        h.notice("first attempt failed; retrying once", kind="retry")
        out = buf.getvalue()
        # The advisory fronts the same activity label as the tick / done line.
        assert (
            "Proposing initial steps · first attempt failed; retrying once\n"
        ) in out

    def test_retry_notice_annotates_done_line(self) -> None:
        buf = io.StringIO()
        r = StderrReporter(buf, interval=10.0)
        h = r.start_step(1, 1, "step 3: x")
        h.notice("retrying", kind="retry")
        h.complete(elapsed_s=5.0, response_bytes=2048)
        assert (
            "step 3 · done in 5s — recovered after 1 retry (2.0 KB response)"
        ) in buf.getvalue()

    def test_two_retries_are_pluralized(self) -> None:
        buf = io.StringIO()
        r = StderrReporter(buf, interval=10.0)
        h = r.start_step(1, 1, "step 3: x")
        h.notice("a", kind="retry")
        h.notice("b", kind="retry")
        h.complete(elapsed_s=5.0, response_bytes=0)
        assert "recovered after 2 retries" in buf.getvalue()

    def test_info_notice_does_not_annotate(self) -> None:
        """A ``kind="info"`` advisory prints cleanly but isn't a recovery."""
        buf = io.StringIO()
        r = StderrReporter(buf, interval=10.0)
        h = r.start_step(1, 1, "step 3: x")
        h.notice("waiting on rate limit", kind="info")
        h.complete(elapsed_s=5.0, response_bytes=2048)
        out = buf.getvalue()
        assert "waiting on rate limit" in out
        assert "recovered after" not in out
        # The historical clean-run tail is preserved byte-for-byte.
        assert "step 3 · done in 5s (2.0 KB response)" in out

    def test_clean_run_has_no_recovery_suffix(self) -> None:
        buf = io.StringIO()
        r = StderrReporter(buf, interval=10.0)
        h = r.start_step(1, 1, "step 3: x")
        h.complete(elapsed_s=5.0, response_bytes=2048)
        out = buf.getvalue()
        assert "step 3 · done in 5s (2.0 KB response)" in out
        assert "recovered" not in out


class TestNotifierBinding:
    """``start_step`` binds the handle as the active in-flight notifier (so a
    retry inside ``shell.claude_invoke`` can route through it); ``complete`` /
    ``fail`` unbind so the next step never writes into a finished handle.
    """

    def test_bound_during_step_and_released_on_complete(self) -> None:
        from plan_tool import shell

        buf = io.StringIO()
        r = StderrReporter(buf, interval=10.0)
        assert shell.get_active_notifier() is None
        h = r.start_step(1, 1, "step 1: x")
        assert shell.get_active_notifier() is h
        h.complete(elapsed_s=1.0, response_bytes=0)
        assert shell.get_active_notifier() is None

    def test_released_on_fail(self) -> None:
        from plan_tool import shell

        buf = io.StringIO()
        r = StderrReporter(buf, interval=10.0)
        h = r.start_step(1, 1, "step 1: x")
        assert shell.get_active_notifier() is h
        h.fail(elapsed_s=1.0, reason="boom")
        assert shell.get_active_notifier() is None

    def test_null_handle_does_not_bind(self) -> None:
        from plan_tool import shell

        r = NullReporter()
        h = r.start_step(1, 1, "step 1: x")
        assert shell.get_active_notifier() is None
        # The no-op notice must not raise.
        h.notice("ignored", kind="retry")
        h.complete(0.0, 0)


def test_reporter_forwards_exact_prompt_hash_to_its_run_log() -> None:
    captured = {}

    class Sink:
        def claude_call_start(self, phase, attempt, prompt_bytes, *, prompt_sha256=None):
            captured.update(
                phase=phase, attempt=attempt, prompt_bytes=prompt_bytes,
                prompt_sha256=prompt_sha256,
            )

    reporter = StderrReporter(io.StringIO(), interval=10.0, run_log=Sink())
    handle = reporter.start_step(
        1, 1, "audit", phase="plan_audit", prompt_bytes=4, prompt_sha256="a" * 64,
    )
    handle.complete(0, 0)
    assert captured == {
        "phase": "plan_audit", "attempt": 1, "prompt_bytes": 4,
        "prompt_sha256": "a" * 64,
    }
