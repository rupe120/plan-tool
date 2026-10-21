"""Tests for plan_tool.backend_runner — the shared streaming Popen supervisor.

``run_streaming_once`` moved here from ``launcher._run_streaming_once``;
the roster below is the relocated streaming-runner suite plus the leaf
import-discipline tests that keep the module reachable from both the run
lane (``launcher``) and the batch lane (``shell``) without a cycle. No
real backend subprocess is ever spawned.
"""

from __future__ import annotations

import json
import re
import subprocess as _real_subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import pytest

from plan_tool import backend_runner
from plan_tool.backend import (
    ClaudeRunStats,
    PromptTransport,
    _claude_parse_stream_line,
    get_active_backend,
)
from subprocess_doubles import (
    _FakePipe,
    _FakeProc,
    _make_popen_factory,
    claude_result_ndjson,
)


class _StreamRecordingLogger:
    """Captures the subset of ``RunLogWriter`` methods that
    ``run_streaming_once`` calls: ``claude_stream_event``,
    ``claude_call_progress``, ``claude_call_stall_suspected``.

    Also records ``backend_recovery_wait`` / ``run_interrupted`` — not
    called by ``run_streaming_once`` itself, but by the
    ``claude_errors.py`` wait/sleep wrappers ``launcher.shell_invoker``
    threads through its recovery loop, which read this same fake off
    ``launcher._run_logger_var`` in tests that bind it there (see
    ``test_shell_invoker_rate_limit_wait_emits_backend_recovery_wait`` in
    tests/test_launcher.py). Without these, any such test raises
    ``AttributeError`` instead of exercising the real wrapping.

    Kept separate from tests/test_launcher.py's broader
    ``_RecordingLogger`` (which imports this class) so streaming tests
    can assert on these methods without coupling to
    phase_start/phase_end events.
    """

    def __init__(self) -> None:
        self.stream_events: list[dict] = []
        self.progress_events: list[dict] = []
        self.stall_events: list[dict] = []
        self.recovery_wait_events: list[dict] = []
        self.interrupted_events: list[dict] = []
        self.spawn_events: list[dict] = []
        self.termination_events: list[dict] = []

    def backend_recovery_wait(self, *, phase, attempt, reason, delay_ms,
                              next_attempt, backend, **extra):
        self.recovery_wait_events.append({
            "phase": phase, "attempt": attempt, "reason": reason,
            "delay_ms": delay_ms, "next_attempt": next_attempt,
            "backend": backend, **extra,
        })

    def run_interrupted(self, *, phase, attempt, source, signal="SIGINT",
                        **extra):
        self.interrupted_events.append({
            "phase": phase, "attempt": attempt, "source": source,
            "signal": signal, **extra,
        })

    def backend_spawn(self, *, phase, attempt, backend, transport=None,
                      child_pid=None, effective_timeout_ms=None,
                      prompt_bytes=None, **extra):
        self.spawn_events.append({
            "phase": phase, "attempt": attempt, "backend": backend,
            "transport": transport, "child_pid": child_pid,
            "effective_timeout_ms": effective_timeout_ms,
            "prompt_bytes": prompt_bytes, **extra,
        })

    def backend_termination(self, *, phase, attempt, backend, reason,
                            duration_ms, signal_or_timeout=None,
                            silent_ms=None, **extra):
        self.termination_events.append({
            "phase": phase, "attempt": attempt, "backend": backend,
            "reason": reason, "duration_ms": duration_ms,
            "signal_or_timeout": signal_or_timeout, "silent_ms": silent_ms,
            **extra,
        })

    def claude_stream_event(self, *, phase, attempt, kind,
                            tool_name=None, tool_input_summary=None,
                            bytes_in_delta=0, **extra):
        self.stream_events.append({
            "phase": phase, "attempt": attempt, "kind": kind,
            "tool_name": tool_name,
            "tool_input_summary": tool_input_summary,
            "bytes_in_delta": bytes_in_delta,
            **extra,
        })

    def claude_call_progress(self, *, phase, attempt, elapsed_ms,
                             silent_ms, last_tool=None,
                             last_activity_kind=None, **extra):
        self.progress_events.append({
            "phase": phase, "attempt": attempt,
            "elapsed_ms": elapsed_ms, "silent_ms": silent_ms,
            "last_tool": last_tool,
            "last_activity_kind": last_activity_kind,
            **extra,
        })

    def claude_call_stall_suspected(self, *, phase, attempt,
                                    silent_ms, threshold_ms,
                                    last_tool=None, **extra):
        self.stall_events.append({
            "phase": phase, "attempt": attempt,
            "silent_ms": silent_ms, "threshold_ms": threshold_ms,
            "last_tool": last_tool,
            **extra,
        })


def _run_streaming(prompt: str = "p", **kwargs):
    """Call the runner the way the run lane does: active backend's
    ``streaming_transport`` as the transport selector."""
    return backend_runner.run_streaming_once(
        prompt, get_active_backend().streaming_transport, **kwargs
    )


class TestLeafImportDiscipline:
    """``backend_runner`` must stay importable from both ``shell`` and
    ``launcher`` — its only first-party imports are ``plan_tool.backend``
    and ``plan_tool.run_log``, the property step 6's batch wiring
    relies on."""

    def test_leaf_has_bounded_first_party_imports(self) -> None:
        src = Path(backend_runner.__file__)
        text = src.read_text(encoding="utf-8")
        modules = re.findall(
            r"(?m)^(?:from|import)\s+(plan_tool(?:\.\w+)*)", text
        )
        assert modules, "expected first-party imports to be present"
        assert set(modules) == {"plan_tool.backend", "plan_tool.run_log"}

    def test_module_loads_in_isolation_with_no_launcher_or_shell(self) -> None:
        """Loading the file with a stub ``plan_tool`` package (bypassing
        the package ``__init__``, which eagerly imports shell/launcher)
        pulls in neither ``plan_tool.launcher`` nor ``plan_tool.shell``.
        Mirrors tests/test_rate_limit_loop.py's idiom for a stricter
        stdlib-only leaf."""
        src = Path(backend_runner.__file__)
        pkg_dir = str(src.parent)
        code = (
            "import importlib.util, sys\n"
            # A package stub built from the real spec (so
            # ``importlib.resources.files('plan_tool')`` in backend.py
            # still resolves) whose ``__init__`` body is never executed.
            "pkg_spec = importlib.util.spec_from_file_location("
            f"'plan_tool', {pkg_dir!r} + '/__init__.py', "
            f"submodule_search_locations=[{pkg_dir!r}])\n"
            "pkg = importlib.util.module_from_spec(pkg_spec)\n"
            "sys.modules['plan_tool'] = pkg\n"
            "spec = importlib.util.spec_from_file_location("
            f"'plan_tool.backend_runner', {str(src)!r})\n"
            "mod = importlib.util.module_from_spec(spec)\n"
            # Register before exec_module — a @dataclass under `from
            # __future__ import annotations` resolves names via
            # sys.modules[__module__] during class creation.
            "sys.modules['plan_tool.backend_runner'] = mod\n"
            "spec.loader.exec_module(mod)\n"
            "leaked = [m for m in sys.modules "
            "if m in ('plan_tool.launcher', 'plan_tool.shell')]\n"
            "assert not leaked, leaked\n"
        )
        proc = _real_subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True
        )
        assert proc.returncode == 0, proc.stderr


class _RaisingWaitProc:
    """Popen stand-in whose ``wait()`` raises once, then reaps cleanly.

    Mirrors ``_HangingProc``/``_StubbornProc`` below but exercises the
    kill-on-any-exception net around the main thread's own
    ``proc.wait()`` call rather than the heartbeat's silence-kill
    ladder — ``terminate()`` is never called here, only ``kill()``.
    """

    def __init__(
        self, exc: BaseException, *, kill_exc: Optional[BaseException] = None
    ) -> None:
        self.stdout = _FakePipe([])
        self.stderr = _FakePipe([])
        self.stdin = None
        self.returncode = None
        self.terminate_called = False
        self.kill_called = False
        self.wait_calls = 0
        self._exc = exc
        self._kill_exc = kill_exc

    def wait(self) -> int:
        self.wait_calls += 1
        if self.wait_calls == 1:
            raise self._exc
        self.returncode = -9
        return self.returncode

    def poll(self):
        return self.returncode

    def terminate(self) -> None:
        self.terminate_called = True

    def kill(self) -> None:
        self.kill_called = True
        if self._kill_exc is not None:
            raise self._kill_exc
        self.returncode = -9


class _SilentUntilKilledProc:
    """Popen stand-in: silent from the start (empty stdout/stderr), blocks
    ``wait()`` until ``terminate()``/``kill()`` flips an internal Event.
    Shared by every test in this module that needs to exercise the
    heartbeat's silence-kill ladder — the same shape as the ``_HangingProc``
    fakes in ``test_kill_on_sustained_silence`` /
    ``test_kill_escalates_to_sigkill_when_terminate_ignored``, factored out
    here so this step's new tests don't each redefine it.
    """

    def __init__(self, returncode: int = -15) -> None:
        self.stdout = _FakePipe([])
        self.stderr = _FakePipe([])
        self.stdin = None
        self.returncode = returncode
        self._dead = threading.Event()
        self.terminate_called = False
        self.kill_called = False

    def wait(self) -> int:
        self._dead.wait(timeout=5.0)
        return self.returncode

    def poll(self):
        return self.returncode if self._dead.is_set() else None

    def terminate(self) -> None:
        self.terminate_called = True
        self._dead.set()

    def kill(self) -> None:
        self.kill_called = True
        self._dead.set()


class _NeverSilentProc:
    """Popen stand-in whose stdout keeps emitting fresh lines until
    ``terminate()``/``kill()`` fires, and whose ``wait()`` otherwise blocks
    forever. Proves a configured-timeout kill is genuinely elapsed-time-
    based rather than an alias for the silence check — continuous activity
    here would keep resetting a silence clock.
    """

    class _Pipe:
        def __init__(self, dead: threading.Event) -> None:
            self._dead = dead

        def __iter__(self):
            while not self._dead.is_set():
                self._dead.wait(timeout=0.005)
                if self._dead.is_set():
                    return
                yield "tick\n"

    def __init__(self, returncode: int = -15) -> None:
        self._dead = threading.Event()
        self.stdout = self._Pipe(self._dead)
        self.stderr = _FakePipe([])
        self.stdin = None
        self.returncode = returncode
        self.terminate_called = False
        self.kill_called = False

    def wait(self) -> int:
        self._dead.wait(timeout=5.0)
        return self.returncode

    def poll(self):
        return self.returncode if self._dead.is_set() else None

    def terminate(self) -> None:
        self.terminate_called = True
        self._dead.set()

    def kill(self) -> None:
        self.kill_called = True
        self._dead.set()


class TestRunStreamingOnceStreamJson:
    """``run_streaming_once`` spawns ``--output-format stream-json
    --verbose`` and parses each NDJSON line into a structured event.
    These tests use the shared ``_FakeProc`` / ``_make_popen_factory``
    doubles (tests/subprocess_doubles.py) and call the runner directly
    so the assertions live close to the NDJSON parser they exercise."""

    def test_uses_stream_json_argv(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured_argv: list[list[str]] = []

        def fake_popen(argv, *, stdout, stderr, text, stdin=None, cwd=None):
            captured_argv.append(list(argv))
            return _FakeProc([], [], 0)

        monkeypatch.setattr(backend_runner.subprocess, "Popen", fake_popen)
        _run_streaming("the prompt")
        assert captured_argv, "Popen should have been called"
        argv = captured_argv[0]
        assert "--output-format" in argv
        assert argv[argv.index("--output-format") + 1] == "stream-json"
        assert "--verbose" in argv
        # Prompt is still the trailing positional.
        assert argv[-1] == "the prompt"

    def test_spawn_closes_stdin(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The streaming spawn passes ``stdin=DEVNULL``.

        Load-bearing for the codex backend: codex reads inherited/piped
        stdin and appends it to the prompt as a ``<stdin>`` block,
        blocking forever when the parent's stdin never closes. Pinned
        after a live 900s silence-watchdog kill (codex-cli-backend
        smoke test, 2026-06-06); see docs/reference/contracts/codex-cli.md.
        """
        captured_stdin: list[object] = []

        def fake_popen(argv, *, stdout, stderr, text, stdin=None, cwd=None):
            captured_stdin.append(stdin)
            return _FakeProc([], [], 0)

        monkeypatch.setattr(backend_runner.subprocess, "Popen", fake_popen)
        _run_streaming("the prompt")
        assert captured_stdin == [backend_runner.subprocess.DEVNULL]

    def test_streaming_routes_through_passed_transport_argv(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The transport call is genuinely parameterized: the Popen argv
        is whatever the passed ``transport`` callable returns — no
        internal ``get_active_backend().streaming_transport`` resolution
        (that selection lives in ``launcher._run_streaming_once``)."""
        captured_argv: list[list[str]] = []

        def fake_popen(argv, *, stdout, stderr, text, stdin=None, cwd=None):
            captured_argv.append(list(argv))
            return _FakeProc([], [], 0)

        monkeypatch.setattr(backend_runner.subprocess, "Popen", fake_popen)
        backend_runner.run_streaming_once(
            "the prompt",
            lambda prompt: PromptTransport(["SENTINEL", prompt]),
        )
        assert captured_argv == [["SENTINEL", "the prompt"]]

    def test_streaming_supports_stdin_prompt_transport(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A streaming backend can receive the prompt through stdin."""

        class _RecordingStdin:
            def __init__(self) -> None:
                self.writes: list[str] = []
                self.closed = False

            def write(self, text: str) -> None:
                self.writes.append(text)

            def close(self) -> None:
                self.closed = True

        captured: dict[str, object] = {}

        def fake_popen(argv, *, stdout, stderr, text, stdin=None, cwd=None):
            proc = _FakeProc([], [], 0)
            proc.stdin = _RecordingStdin()
            captured["argv"] = list(argv)
            captured["stdin_arg"] = stdin
            captured["stdin_obj"] = proc.stdin
            return proc

        monkeypatch.setattr(backend_runner.subprocess, "Popen", fake_popen)
        backend_runner.run_streaming_once(
            "PROMPT",
            lambda prompt: PromptTransport(
                ["backend", "--stdin"], stdin_text=prompt
            ),
        )

        stdin_obj = captured["stdin_obj"]
        assert captured["argv"] == ["backend", "--stdin"]
        assert captured["stdin_arg"] is backend_runner.subprocess.PIPE
        assert stdin_obj.writes == ["PROMPT"]
        assert stdin_obj.closed is True

    def test_non_json_lines_fall_through_to_stdout_buffer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Transport-layer errors and rate-limit copy reach the
        failure classifier as plain text — non-JSON lines must be
        preserved verbatim in the stdout buffer."""
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([
                (["hello\n", "world\n"], [], 0),
            ]),
        )
        rc, stdout_text, stderr_text, stats = _run_streaming("p")
        assert rc == 0
        assert stdout_text == "hello\nworld\n"
        assert stderr_text == ""
        # No JSON content → stats stay at defaults.
        assert stats.final_text == ""
        assert stats.tokens_input is None

    def test_emits_tool_use_event_with_input_summary(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        line = json.dumps({
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Edit",
                        "input": {
                            "file_path": "apps/web/src/App.tsx",
                            "old_string": "x", "new_string": "y",
                        },
                    }
                ]
            },
        }) + "\n"
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([([line], [], 0)]),
        )
        logger = _StreamRecordingLogger()
        _run_streaming(
            "p", run_logger=logger, phase="claude_call", attempt=1,
        )
        assert len(logger.stream_events) == 1
        ev = logger.stream_events[0]
        assert ev["kind"] == "tool_use"
        assert ev["tool_name"] == "Edit"
        assert ev["tool_input_summary"] == "apps/web/src/App.tsx"
        assert ev["phase"] == "claude_call"
        assert ev["attempt"] == 1

    def test_tool_use_summary_for_bash_picks_command(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        line = json.dumps({
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Bash",
                        "input": {"command": "ls -la /tmp"},
                    }
                ]
            },
        }) + "\n"
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([([line], [], 0)]),
        )
        logger = _StreamRecordingLogger()
        _run_streaming("p", run_logger=logger)
        assert logger.stream_events[0]["tool_input_summary"] == "ls -la /tmp"

    def test_tool_use_summary_for_grep_combines_pattern_and_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        line = json.dumps({
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Grep",
                        "input": {"pattern": "def foo", "path": "src/"},
                    }
                ]
            },
        }) + "\n"
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([([line], [], 0)]),
        )
        logger = _StreamRecordingLogger()
        _run_streaming("p", run_logger=logger)
        assert logger.stream_events[0]["tool_input_summary"] == "def foo in src/"

    def test_tool_use_summary_truncates_long_inputs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A 1KB ``command`` payload must not push the JSONL event over
        the per-line cap — the summary is bounded at 200 chars in the
        parser regardless of what the input contains."""
        long_command = "echo " + ("x" * 1500)
        line = json.dumps({
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use", "name": "Bash",
                        "input": {"command": long_command},
                    }
                ]
            },
        }) + "\n"
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([([line], [], 0)]),
        )
        logger = _StreamRecordingLogger()
        _run_streaming("p", run_logger=logger)
        summary = logger.stream_events[0]["tool_input_summary"]
        assert summary is not None and len(summary) <= 200

    def test_assistant_text_block_appended_to_stdout_buffer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Text content from ``assistant`` blocks must reach the stdout
        buffer so the failure classifier (which scans plain strings)
        keeps working under the stream-json transport."""
        line = json.dumps({
            "type": "assistant",
            "message": {
                "content": [{"type": "text", "text": "hello from claude"}],
            },
        }) + "\n"
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([([line], [], 0)]),
        )
        logger = _StreamRecordingLogger()
        rc, stdout_text, _, _ = _run_streaming("p", run_logger=logger)
        assert rc == 0
        assert "hello from claude" in stdout_text
        assert logger.stream_events[0]["kind"] == "assistant_text"

    def test_result_envelope_populates_stats(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Real claude stream-json output carries ``request_id`` on the
        # ``assistant`` event, not the result envelope; the parser
        # captures it across lines and merges it into the stats when the
        # result envelope arrives.
        assistant_line = json.dumps({
            "type": "assistant",
            "request_id": "req_xyz",
            "message": {"content": [{"type": "text", "text": "the final assistant text"}]},
        }) + "\n"
        result_line = json.dumps({
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": "the final assistant text",
            "usage": {
                "input_tokens": 12,
                "output_tokens": 34,
                "cache_creation_input_tokens": 5,
                "cache_read_input_tokens": 6,
            },
            "total_cost_usd": 0.0123,
            "session_id": "sess-abc",
        }) + "\n"
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([([assistant_line, result_line], [], 0)]),
        )
        logger = _StreamRecordingLogger()
        rc, stdout_text, _, stats = _run_streaming("p", run_logger=logger)
        assert rc == 0
        assert stats.final_text == "the final assistant text"
        assert stats.tokens_input == 12
        assert stats.tokens_output == 34
        assert stats.cache_creation_tokens == 5
        assert stats.cache_read_tokens == 6
        assert stats.cost_usd == pytest.approx(0.0123)
        # request_id comes from the assistant event, not session_id.
        assert stats.request_id == "req_xyz"
        assert stats.is_error is False
        # Final text reaches the stdout buffer so the existing
        # extract_summary call site keeps working.
        assert "the final assistant text" in stdout_text
        # And one ``result`` stream event was emitted.
        assert any(e["kind"] == "result" for e in logger.stream_events)

    def test_result_is_error_true_surfaces(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result_line = json.dumps({
            "type": "result",
            "is_error": True,
            "result": "",
            "usage": {},
        }) + "\n"
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([([result_line], [], 1)]),
        )
        _, _, _, stats = _run_streaming("p")
        assert stats.is_error is True

    def test_request_id_none_when_no_assistant_event(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A result envelope on its own (no preceding ``assistant``)
        produces ``request_id=None`` — we do NOT fall back to the
        session_id, which is shared across multi-turn calls and is the
        wrong identifier for per-API-request observability."""
        result_line = json.dumps({
            "type": "result", "is_error": False, "result": "ok",
            "usage": {"input_tokens": 1, "output_tokens": 1},
            "session_id": "sess-only",
        }) + "\n"
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([([result_line], [], 0)]),
        )
        _, _, _, stats = _run_streaming("p")
        assert stats.request_id is None

    def test_request_id_uses_last_assistant_on_multi_turn(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Multi-turn calls emit multiple ``assistant`` events; the
        result envelope's stats should carry the most recent
        ``request_id`` so callers can correlate the final API call."""
        a1 = json.dumps({
            "type": "assistant", "request_id": "req_first",
            "message": {"content": [{"type": "text", "text": "t1"}]},
        }) + "\n"
        a2 = json.dumps({
            "type": "assistant", "request_id": "req_last",
            "message": {"content": [{"type": "text", "text": "t2"}]},
        }) + "\n"
        result_line = json.dumps({
            "type": "result", "is_error": False, "result": "t2",
            "usage": {"input_tokens": 1, "output_tokens": 1},
            "session_id": "sess",
        }) + "\n"
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([([a1, a2, result_line], [], 0)]),
        )
        _, _, _, stats = _run_streaming("p")
        assert stats.request_id == "req_last"

    def test_kill_on_sustained_silence(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A claude binary that emits no NDJSON and never exits must be
        killed by the heartbeat after ``_KILL_AFTER_SILENCE_S`` so the
        main thread's ``proc.wait()`` returns. Otherwise plan-tool is
        pinned to a wedged child."""

        # Fake Popen that drains stdout immediately (empty pipes) and
        # blocks ``wait()`` on an internal Event until ``terminate()``
        # or ``kill()`` flips it.
        class _HangingProc:
            def __init__(self) -> None:
                self.stdout = _FakePipe([])
                self.stderr = _FakePipe([])
                self.returncode = -15  # SIGTERM-equivalent
                self._dead = threading.Event()
                self.terminate_called = False
                self.kill_called = False

            def wait(self) -> int:
                # Block until terminate/kill flips the event.
                self._dead.wait(timeout=5.0)
                return self.returncode

            def poll(self):
                return self.returncode if self._dead.is_set() else None

            def terminate(self) -> None:
                self.terminate_called = True
                self._dead.set()

            def kill(self) -> None:
                self.kill_called = True
                self._dead.set()

        hanging = _HangingProc()
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            lambda *a, **kw: hanging,
        )
        # Compress thresholds so the test runs in well under a second.
        monkeypatch.setattr(backend_runner, "_PROGRESS_INTERVAL_S", 0.02)
        monkeypatch.setattr(backend_runner, "_STALL_THRESHOLD_S", 0.05)
        monkeypatch.setattr(backend_runner, "_KILL_AFTER_SILENCE_S", 0.10)
        monkeypatch.setattr(backend_runner, "_KILL_GRACE_S", 0.05)

        rc, _, _, _ = _run_streaming("p")
        assert hanging.terminate_called, (
            "heartbeat must terminate the child after sustained silence"
        )
        # SIGTERM was sufficient (the fake exits immediately on
        # terminate), so the kill escalation should not have fired.
        assert hanging.kill_called is False
        assert rc == -15

    def test_kill_escalates_to_sigkill_when_terminate_ignored(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If the child ignores SIGTERM, the heartbeat must escalate to
        SIGKILL after the grace window. Otherwise a misbehaving claude
        binary still pins the parent."""

        class _StubbornProc:
            def __init__(self) -> None:
                self.stdout = _FakePipe([])
                self.stderr = _FakePipe([])
                self.returncode = -9
                self._dead = threading.Event()
                self.terminate_called = False
                self.kill_called = False

            def wait(self) -> int:
                self._dead.wait(timeout=5.0)
                return self.returncode

            def poll(self):
                # Stays alive until ``kill()`` — terminate is ignored.
                return self.returncode if self._dead.is_set() else None

            def terminate(self) -> None:
                self.terminate_called = True
                # Intentionally NOT setting _dead — simulates a child
                # that ignores SIGTERM.

            def kill(self) -> None:
                self.kill_called = True
                self._dead.set()

        stubborn = _StubbornProc()
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            lambda *a, **kw: stubborn,
        )
        monkeypatch.setattr(backend_runner, "_PROGRESS_INTERVAL_S", 0.02)
        monkeypatch.setattr(backend_runner, "_STALL_THRESHOLD_S", 0.05)
        monkeypatch.setattr(backend_runner, "_KILL_AFTER_SILENCE_S", 0.10)
        monkeypatch.setattr(backend_runner, "_KILL_GRACE_S", 0.05)

        _run_streaming("p")
        assert stubborn.terminate_called
        assert stubborn.kill_called, (
            "must escalate to SIGKILL when SIGTERM is ignored"
        )

    def test_keyboard_interrupt_during_wait_kills_and_reaps_the_child(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A ``KeyboardInterrupt`` (Ctrl-C) raised while blocked in
        ``proc.wait()`` must kill and reap the child before propagating
        — the safety net this step adds."""
        fake = _RaisingWaitProc(KeyboardInterrupt())
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen", lambda *a, **kw: fake
        )
        with pytest.raises(KeyboardInterrupt):
            _run_streaming("p")
        assert fake.kill_called
        assert fake.wait_calls == 2, "must reap after killing"

    def test_non_keyboard_interrupt_exception_during_wait_also_kills_the_child(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The net isn't ``KeyboardInterrupt``-specific — any exception
        raised from ``proc.wait()`` kills the child."""
        fake = _RaisingWaitProc(OSError("boom"))
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen", lambda *a, **kw: fake
        )
        with pytest.raises(OSError, match="boom"):
            _run_streaming("p")
        assert fake.kill_called

    def test_kill_guards_against_already_exited_child(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``proc.kill()`` raising because the child is already gone
        (e.g. a race against the heartbeat's own kill ladder) must not
        mask the original exception."""
        fake = _RaisingWaitProc(
            KeyboardInterrupt(), kill_exc=ProcessLookupError()
        )
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen", lambda *a, **kw: fake
        )
        with pytest.raises(KeyboardInterrupt):
            _run_streaming("p")
        assert fake.kill_called

    def test_exception_during_wait_still_joins_pump_and_heartbeat_threads(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The three ``join()`` calls must run on the exception path too
        — today they only run after a normal return, which is the
        second half of the leaked-thread failure this step closes."""
        fake = _RaisingWaitProc(KeyboardInterrupt())
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen", lambda *a, **kw: fake
        )
        joined: list[threading.Thread] = []
        real_join = threading.Thread.join

        def recording_join(self, *a, **kw):
            joined.append(self)
            return real_join(self, *a, **kw)

        monkeypatch.setattr(threading.Thread, "join", recording_join)

        with pytest.raises(KeyboardInterrupt):
            _run_streaming("p")

        assert len(joined) == 3, "expected t_out, t_err, and t_hb all joined"

    def test_sibling_ndjson_transcript_written(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        l1 = json.dumps({"type": "system"}) + "\n"
        l2 = json.dumps({
            "type": "result", "is_error": False, "result": "done",
            "usage": {},
        }) + "\n"
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([([l1, l2], [], 0)]),
        )
        sibling = tmp_path / "run-id.streams"
        _run_streaming("p", attempt=3, sibling_log_dir=sibling)
        (transcript,) = sibling.glob("claude-stream.*.a3.ndjson")
        assert transcript.is_file()
        text = transcript.read_text(encoding="utf-8")
        # Both raw lines were written, each terminated by a newline.
        assert text == l1 + l2

    def test_sibling_transcript_only_written_when_kwarg_supplied(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([(["raw\n"], [], 0)]),
        )
        _run_streaming("p")
        # No sibling dir was passed — no transcript anywhere under
        # ``tmp_path``.
        assert not any(tmp_path.rglob("claude-stream*.ndjson"))

    def test_stream_log_defaults_to_streams_dir_beside_run_log(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The raw stream is always logged beside the run log, so a tail
        needs no flag; the derived dir is ``<run_id>.streams``."""
        line = '{"type":"item.completed","item":{"type":"web_search"}}\n'
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([([line], [], 0)]),
        )
        logger = _StreamRecordingLogger()
        logger.log_path = tmp_path / "runs" / "slug" / "rid.jsonl"
        _run_streaming("p", run_logger=logger, attempt=2)
        (transcript,) = (tmp_path / "runs" / "slug" / "rid.streams").glob(
            "claude-stream.*.a2.ndjson"
        )
        assert transcript.read_text(encoding="utf-8") == line

    def test_calls_under_one_run_log_never_share_a_stream_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """``attempt`` restarts at 1 per call, so a name built from it alone
        would let the second call truncate the first call's transcript."""
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([(["one\n"], [], 0), (["two\n"], [], 0)]),
        )
        logger = _StreamRecordingLogger()
        logger.log_path = tmp_path / "rid.jsonl"
        _run_streaming("p", run_logger=logger, attempt=1)
        _run_streaming("p", run_logger=logger, attempt=1)
        texts = sorted(
            f.read_text(encoding="utf-8")
            for f in (tmp_path / "rid.streams").glob("claude-stream.*.ndjson")
        )
        assert texts == ["one\n", "two\n"]

    def test_batch_observer_forwards_run_log_path(self, tmp_path: Path) -> None:
        """The batch lane wraps the writer; without ``log_path`` forwarded,
        create/detail/audit calls would get no stream log."""
        from plan_tool.shell import _ClaudeInvokeRunnerObserver

        class _Writer:
            log_path = tmp_path / "rid.jsonl"

        obs = _ClaudeInvokeRunnerObserver(_Writer())
        assert obs.log_path == tmp_path / "rid.jsonl"

    def test_suppressed_content_wins_over_explicit_sibling_dir(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([(["secret\n"], [], 0)]),
        )
        _run_streaming(
            "p", sibling_log_dir=tmp_path / "s", suppress_content_output=True
        )
        assert not any(tmp_path.rglob("claude-stream*.ndjson"))

    def test_stream_log_write_failure_does_not_kill_the_pump(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A non-OSError from the log write must not wedge ``proc.wait()``;
        the call still returns its stdout, the operator is told the log
        stopped, and the handle is still closed."""
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([(["a\n", "b\n"], [], 0)]),
        )
        closed: list[bool] = []

        class _Boom:
            def write(self, _s):
                raise ValueError("closed")

            def close(self):
                closed.append(True)

        monkeypatch.setattr(
            backend_runner, "_resolve_stream_log_path",
            lambda *a, **k: tmp_path / "s" / "claude-stream.test.ndjson",
        )
        monkeypatch.setattr(backend_runner.os, "fdopen", lambda *a, **k: _Boom())
        rc, out, _err, _stats = _run_streaming("p")
        assert rc == 0
        assert "a" in out and "b" in out
        assert closed == [True]
        assert "raw backend stream log stopped" in capsys.readouterr().err

    def test_stream_log_is_private_to_the_owner(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The stream is unredacted; it must not be world-readable."""
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([(["x\n"], [], 0)]),
        )
        sibling = tmp_path / "s"
        _run_streaming("p", sibling_log_dir=sibling)
        (written,) = sibling.glob("claude-stream.*.ndjson")
        assert written.stat().st_mode & 0o077 == 0
        assert sibling.stat().st_mode & 0o077 == 0

    def test_caller_supplied_dir_never_gets_an_ignore_rule(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Only the directory the runner derives ignores itself; dropping a
        ``*`` rule into a caller's directory would hide its other files."""
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([(["x\n"], [], 0)]),
        )
        sibling = tmp_path / "s"
        _run_streaming("p", sibling_log_dir=sibling)
        assert not (sibling / ".gitignore").exists()

    def test_derived_dir_ignores_itself(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([(["x\n"], [], 0)]),
        )
        logger = _StreamRecordingLogger()
        logger.log_path = tmp_path / "rid.jsonl"
        _run_streaming("p", run_logger=logger)
        assert (tmp_path / "rid.streams" / ".gitignore").read_text() == "*\n"

    def test_non_oserror_opening_the_log_does_not_fail_the_call(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The child is already spawned when the log opens; an unexpected
        error there must cost only the log, never the call."""
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([(["ok\n"], [], 0)]),
        )

        class _BadPath:
            @property
            def parent(self):
                raise ValueError("odd path")

            def __str__(self):
                return "bad"

        monkeypatch.setattr(
            backend_runner, "_resolve_stream_log_path", lambda *a, **k: _BadPath()
        )
        rc, out, _e, _s = _run_streaming("p")
        assert rc == 0 and "ok" in out

    def test_open_failure_warns_once_per_process(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Hundreds of calls under an unwritable runs dir must not each print
        the same warning."""
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([(["x\n"], [], 0), (["y\n"], [], 0)]),
        )
        monkeypatch.setattr(backend_runner, "_STREAM_LOG_WARNED", [False])
        blocker = tmp_path / "file"
        blocker.write_text("x")
        _run_streaming("p", sibling_log_dir=blocker / "a")
        _run_streaming("p", sibling_log_dir=blocker / "b")
        assert capsys.readouterr().err.count("stream log unavailable") == 1

    def test_derived_dir_without_ignore_rule_gets_no_log(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Fail closed: if the self-ignore cannot be written, the unredacted
        stream must not be written where ``git add -A`` could stage it."""
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([(["secret\n"], [], 0)]),
        )
        monkeypatch.setattr(backend_runner, "_STREAM_LOG_WARNED", [False])
        streams = tmp_path / "rid.streams"
        streams.mkdir()
        (streams / ".gitignore").mkdir()  # unwritable and not a file
        logger = _StreamRecordingLogger()
        logger.log_path = tmp_path / "rid.jsonl"
        _run_streaming("p", run_logger=logger)
        assert list(streams.glob("claude-stream.*")) == []

    def test_existing_derived_dir_is_tightened_to_owner_only(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([(["x\n"], [], 0)]),
        )
        streams = tmp_path / "rid.streams"
        streams.mkdir(mode=0o755)
        streams.chmod(0o755)
        logger = _StreamRecordingLogger()
        logger.log_path = tmp_path / "rid.jsonl"
        _run_streaming("p", run_logger=logger)
        assert streams.stat().st_mode & 0o077 == 0

    def test_long_phase_name_is_capped_in_stream_log_filename(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([(["x\n"], [], 0)]),
        )
        _run_streaming("p", sibling_log_dir=tmp_path / "s", phase="p" * 400)
        (written,) = (tmp_path / "s").glob("claude-stream.*.ndjson")
        assert len(written.name) < 100

    def test_roadmap_observer_forwards_run_log_path(self, tmp_path: Path) -> None:
        """Materialization wraps the writer in its own observer; without
        ``log_path`` forwarded those backend calls would get no stream log."""
        from plan_tool.roadmap import _MaterializationObserver

        class _Writer:
            log_path = tmp_path / "rid.jsonl"

        obs = _MaterializationObserver(_Writer(), plan_id="p", phase="ph")
        assert obs.log_path == tmp_path / "rid.jsonl"

    def test_unopenable_stream_log_warns_operator(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([(["x\n"], [], 0)]),
        )
        monkeypatch.setattr(backend_runner, "_STREAM_LOG_WARNED", [False])
        blocker = tmp_path / "file"
        blocker.write_text("x")
        _run_streaming("p", sibling_log_dir=blocker / "sub")
        assert "raw backend stream log unavailable" in capsys.readouterr().err

    def test_backend_spawn_names_the_stream_log_file_or_none_when_suppressed(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The run log must say which stream file a call wrote (file name in
        the sibling ``.streams`` dir), and ``None`` when it wrote none."""
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([(["x\n"], [], 0), (["y\n"], [], 0)]),
        )
        logger = _StreamRecordingLogger()
        logger.log_path = tmp_path / "rid.jsonl"
        _run_streaming("p", run_logger=logger)
        _run_streaming("p", run_logger=logger, suppress_content_output=True)
        named, suppressed = logger.spawn_events
        written = list((tmp_path / "rid.streams").glob("claude-stream*.ndjson"))
        assert [named["stream_log"]] == [w.name for w in written]
        assert suppressed["stream_log"] is None

    def test_suppressed_content_gets_no_derived_stream_log(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Structural callers whose redaction is not ready must not leave an
        unredacted transcript behind via the derived path."""
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([(["secret\n"], [], 0)]),
        )
        logger = _StreamRecordingLogger()
        logger.log_path = tmp_path / "rid.jsonl"
        _run_streaming("p", run_logger=logger, suppress_content_output=True)
        assert not any(tmp_path.rglob("claude-stream*.ndjson"))

    def test_debug_routes_raw_stream_to_log_not_console(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        line = '{"type":"item.completed","item":{"type":"web_search"}}\n'
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([([line], [], 0)]),
        )
        sibling = tmp_path / "rid.streams"
        old = backend_runner.get_console_verbosity()
        backend_runner.set_console_verbosity(2)
        try:
            _run_streaming("p", sibling_log_dir=sibling)
        finally:
            backend_runner.set_console_verbosity(old)
        captured = capsys.readouterr()
        assert "item.completed" not in captured.out + captured.err
        (written,) = sibling.glob("claude-stream.*.a1.ndjson")
        assert str(written) in captured.err
        assert written.read_text() == line

    def test_debug_falls_back_to_stdout_when_log_cannot_open(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--debug must never be silent: an unwritable log keeps the old
        stdout passthrough."""
        line = '{"type":"item.completed"}\n'
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([([line], [], 0)]),
        )
        blocker = tmp_path / "file"
        blocker.write_text("x")
        old = backend_runner.get_console_verbosity()
        backend_runner.set_console_verbosity(2)
        try:
            _run_streaming("p", sibling_log_dir=blocker / "sub")
        finally:
            backend_runner.set_console_verbosity(old)
        assert line in capsys.readouterr().out

    def test_returns_default_stats_when_no_result_envelope(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([(["plain text\n"], [], 0)]),
        )
        _, _, _, stats = _run_streaming("p")
        # Default sentinel — every field at its dataclass default.
        assert stats == ClaudeRunStats()

    def test_no_progress_events_emitted_for_fast_calls(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The 20s heartbeat must not fire under a fast-completing
        fake subprocess — every test in this suite finishes in
        milliseconds. A spurious heartbeat would mean the daemon
        thread is racing the shutdown signal."""
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([(["x\n"], [], 0)]),
        )
        logger = _StreamRecordingLogger()
        _run_streaming("p", run_logger=logger)
        assert logger.progress_events == []
        assert logger.stall_events == []


class TestConfiguredTimeout:
    """``enforce_configured_timeout`` gates a second, elapsed-time kill the
    heartbeat enforces alongside its existing silence kill."""

    def test_configured_timeout_kills_after_elapsed_seconds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        proc = _NeverSilentProc()
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen", lambda *a, **kw: proc
        )
        monkeypatch.setattr(backend_runner, "_PROGRESS_INTERVAL_S", 0.02)
        monkeypatch.setattr(backend_runner, "_KILL_AFTER_SILENCE_S", 10.0)
        monkeypatch.setattr(backend_runner, "_KILL_GRACE_S", 0.02)

        rc, _, _, _ = _run_streaming(
            "p", enforce_configured_timeout=True, configured_timeout_s=0.06
        )
        assert proc.terminate_called, (
            "elapsed time must kill the child even while it keeps "
            "producing fresh output that would otherwise reset the "
            "silence clock"
        )
        assert rc == -15
        assert (
            backend_runner.get_last_termination_reason()
            is backend_runner.TerminationReason.CONFIGURED_TIMEOUT
        )

    def test_configured_timeout_not_enforced_by_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A short ``configured_timeout_s`` is inert unless
        ``enforce_configured_timeout=True`` — the boolean gates
        enforcement, not the presence of a value. The fake here is silent
        from the start, so elapsed time and silent time grow together; if
        the (much shorter) configured threshold had fired, the recorded
        reason would read CONFIGURED_TIMEOUT rather than SILENCE_TIMEOUT."""
        proc = _SilentUntilKilledProc()
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen", lambda *a, **kw: proc
        )
        monkeypatch.setattr(backend_runner, "_PROGRESS_INTERVAL_S", 0.02)
        monkeypatch.setattr(backend_runner, "_KILL_AFTER_SILENCE_S", 0.10)
        monkeypatch.setattr(backend_runner, "_KILL_GRACE_S", 0.02)

        _run_streaming("p", configured_timeout_s=0.02)
        assert proc.terminate_called
        assert (
            backend_runner.get_last_termination_reason()
            is backend_runner.TerminationReason.SILENCE_TIMEOUT
        )

    def test_configured_timeout_kill_writes_the_same_sentinel_as_silence_kill(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        proc = _NeverSilentProc()
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen", lambda *a, **kw: proc
        )
        monkeypatch.setattr(backend_runner, "_PROGRESS_INTERVAL_S", 0.02)
        monkeypatch.setattr(backend_runner, "_KILL_AFTER_SILENCE_S", 10.0)
        monkeypatch.setattr(backend_runner, "_KILL_GRACE_S", 0.02)

        _, _, stderr_text, _ = _run_streaming(
            "p", enforce_configured_timeout=True, configured_timeout_s=0.06
        )
        assert backend_runner._BACKEND_TIMEOUT_SENTINEL in stderr_text

    def test_termination_reason_accessor_reports_configured_timeout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        proc = _NeverSilentProc()
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen", lambda *a, **kw: proc
        )
        monkeypatch.setattr(backend_runner, "_PROGRESS_INTERVAL_S", 0.02)
        monkeypatch.setattr(backend_runner, "_KILL_AFTER_SILENCE_S", 10.0)
        monkeypatch.setattr(backend_runner, "_KILL_GRACE_S", 0.02)

        _run_streaming(
            "p", enforce_configured_timeout=True, configured_timeout_s=0.06
        )
        assert (
            backend_runner.get_last_termination_reason()
            is backend_runner.TerminationReason.CONFIGURED_TIMEOUT
        )

    def test_child_exiting_successfully_right_at_the_threshold_is_not_killed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A child whose ``poll()`` already shows a clean exit by the time
        a heartbeat tick crosses the elapsed/silent threshold must not be
        killed and misclassified as a timeout — the wall-clock thresholds
        are stale reads that can lag a child that finished on its own in
        the same instant. ``wait()`` is delayed slightly past the
        compressed threshold so the heartbeat gets a tick with ``poll()``
        already non-``None`` before the main thread reaps the child."""

        class _CompletesRightAtThresholdProc:
            def __init__(self) -> None:
                self.stdout = _FakePipe([])
                self.stderr = _FakePipe([])
                self.stdin = None
                self.returncode = 0
                self.terminate_called = False
                self.kill_called = False

            def poll(self):
                return self.returncode

            def wait(self) -> int:
                time.sleep(0.08)
                return self.returncode

            def terminate(self) -> None:
                self.terminate_called = True

            def kill(self) -> None:
                self.kill_called = True

        proc = _CompletesRightAtThresholdProc()
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen", lambda *a, **kw: proc
        )
        monkeypatch.setattr(backend_runner, "_PROGRESS_INTERVAL_S", 0.02)
        monkeypatch.setattr(backend_runner, "_KILL_AFTER_SILENCE_S", 0.02)
        monkeypatch.setattr(backend_runner, "_KILL_GRACE_S", 0.02)

        rc, _, _, _ = _run_streaming("p")

        assert not proc.terminate_called
        assert not proc.kill_called
        assert rc == 0
        assert (
            backend_runner.get_last_termination_reason()
            is backend_runner.TerminationReason.COMPLETED
        )


class TestStallSuspectedStaleness:
    def test_stall_not_reported_when_child_already_exited_at_the_threshold(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Same staleness race as
        ``test_child_exiting_successfully_right_at_the_threshold_is_not_killed``
        above, applied to the stall marker rather than the kill ladder: a
        child whose ``poll()`` already shows a clean exit by the time a
        heartbeat tick crosses the stall threshold must not get a spurious
        ``claude_call_stall_suspected`` row immediately preceding its clean
        completion. ``wait()`` is delayed past the compressed threshold so
        the heartbeat gets a tick with ``poll()`` already non-``None``
        before the main thread reaps the child."""

        class _CompletesRightAtStallThresholdProc:
            def __init__(self) -> None:
                self.stdout = _FakePipe([])
                self.stderr = _FakePipe([])
                self.stdin = None
                self.returncode = 0

            def poll(self):
                return self.returncode

            def wait(self) -> int:
                time.sleep(0.08)
                return self.returncode

            def terminate(self) -> None:
                pass

            def kill(self) -> None:
                pass

        proc = _CompletesRightAtStallThresholdProc()
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen", lambda *a, **kw: proc
        )
        monkeypatch.setattr(backend_runner, "_PROGRESS_INTERVAL_S", 0.02)
        monkeypatch.setattr(backend_runner, "_STALL_THRESHOLD_S", 0.02)
        # Kept well above the stall threshold so only the stall check —
        # not the kill ladder — is under test here.
        monkeypatch.setattr(backend_runner, "_KILL_AFTER_SILENCE_S", 999.0)

        logger = _StreamRecordingLogger()
        rc, _, _, _ = _run_streaming("p", run_logger=logger)

        assert rc == 0
        assert logger.stall_events == []


class TestSilenceKillSentinelAndReason:
    def test_silence_kill_writes_the_backend_timeout_sentinel(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Today's ``test_kill_on_sustained_silence`` only checks
        ``terminate_called``/``kill_called``/``rc`` — this extends the same
        fixture shape to also assert the returned ``stderr`` carries the
        sentinel the classification bridge depends on."""
        proc = _SilentUntilKilledProc()
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen", lambda *a, **kw: proc
        )
        monkeypatch.setattr(backend_runner, "_PROGRESS_INTERVAL_S", 0.02)
        monkeypatch.setattr(backend_runner, "_STALL_THRESHOLD_S", 0.05)
        monkeypatch.setattr(backend_runner, "_KILL_AFTER_SILENCE_S", 0.10)
        monkeypatch.setattr(backend_runner, "_KILL_GRACE_S", 0.05)

        _, _, stderr_text, _ = _run_streaming("p")
        assert proc.terminate_called
        assert backend_runner._BACKEND_TIMEOUT_SENTINEL in stderr_text

    def test_termination_reason_accessor_reports_silence_timeout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        proc = _SilentUntilKilledProc()
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen", lambda *a, **kw: proc
        )
        monkeypatch.setattr(backend_runner, "_PROGRESS_INTERVAL_S", 0.02)
        monkeypatch.setattr(backend_runner, "_KILL_AFTER_SILENCE_S", 0.10)
        monkeypatch.setattr(backend_runner, "_KILL_GRACE_S", 0.05)

        _run_streaming("p")
        assert (
            backend_runner.get_last_termination_reason()
            is backend_runner.TerminationReason.SILENCE_TIMEOUT
        )


class TestTerminationReasonBasics:
    def test_termination_reason_accessor_reports_completed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([(["ok\n"], [], 0)]),
        )
        rc, _, _, _ = _run_streaming("p")
        assert rc == 0
        assert (
            backend_runner.get_last_termination_reason()
            is backend_runner.TerminationReason.COMPLETED
        )

    def test_termination_reason_accessor_reports_backend_nonzero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([(["fail\n"], [], 1)]),
        )
        rc, _, _, _ = _run_streaming("p")
        assert rc == 1
        assert (
            backend_runner.get_last_termination_reason()
            is backend_runner.TerminationReason.BACKEND_NONZERO
        )

    def test_run_streaming_once_default_call_shape_is_unchanged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A call using none of this step's new parameters — ``run``'s
        existing call shape — returns the same 4-tuple, completes
        normally, and reads the unscoped, unchanged silence threshold."""
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([(["hello\n"], [], 0)]),
        )
        result = _run_streaming("p")
        assert len(result) == 4
        rc, stdout_text, stderr_text, _stats = result
        assert (rc, stdout_text, stderr_text) == (0, "hello\n", "")
        assert (
            backend_runner.get_last_termination_reason()
            is backend_runner.TerminationReason.COMPLETED
        )
        assert (
            backend_runner._effective_silence_timeout_s()
            == backend_runner._KILL_AFTER_SILENCE_S
        )


class TestExceptionClassification:
    def test_keyboard_interrupt_during_wait_is_classified_operator_interrupt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake = _RaisingWaitProc(KeyboardInterrupt())
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen", lambda *a, **kw: fake
        )
        with pytest.raises(KeyboardInterrupt):
            _run_streaming("p")
        assert fake.kill_called
        assert fake.wait_calls == 2, "must reap after killing"
        assert (
            backend_runner.get_last_termination_reason()
            is backend_runner.TerminationReason.OPERATOR_INTERRUPT
        )

    def test_non_keyboard_interrupt_exception_during_wait_is_classified_unknown(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake = _RaisingWaitProc(OSError("boom"))
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen", lambda *a, **kw: fake
        )
        with pytest.raises(OSError, match="boom"):
            _run_streaming("p")
        assert fake.kill_called
        assert (
            backend_runner.get_last_termination_reason()
            is backend_runner.TerminationReason.UNKNOWN
        )

    def test_popen_failure_is_classified_spawn_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def raising_popen(*_a, **_kw):
            raise OSError("binary vanished")

        monkeypatch.setattr(backend_runner.subprocess, "Popen", raising_popen)
        with pytest.raises(OSError, match="binary vanished"):
            _run_streaming("p")
        assert (
            backend_runner.get_last_termination_reason()
            is backend_runner.TerminationReason.SPAWN_FAILURE
        )

    def test_keyboard_interrupt_during_popen_is_classified_operator_interrupt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def raising_popen(*_a, **_kw):
            raise KeyboardInterrupt()

        monkeypatch.setattr(backend_runner.subprocess, "Popen", raising_popen)
        with pytest.raises(KeyboardInterrupt):
            _run_streaming("p")
        assert (
            backend_runner.get_last_termination_reason()
            is backend_runner.TerminationReason.OPERATOR_INTERRUPT
        )

    def test_keyboard_interrupt_during_popen_emits_run_interrupted_source_spawn(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Mirrors the ``proc.wait()`` arm's pairing: an
        ``operator_interrupt`` termination without a matching
        ``run_interrupted`` row would break the 1:1 pairing every other
        interrupt source in this module keeps."""

        def raising_popen(*_a, **_kw):
            raise KeyboardInterrupt()

        monkeypatch.setattr(backend_runner.subprocess, "Popen", raising_popen)
        logger = _StreamRecordingLogger()
        with pytest.raises(KeyboardInterrupt):
            _run_streaming("p", run_logger=logger)

        assert len(logger.interrupted_events) == 1
        assert logger.interrupted_events[0]["source"] == "spawn"
        assert logger.termination_events
        assert logger.termination_events[-1]["reason"] == "operator_interrupt"


class TestPopenSigintGuard:
    """A ``KeyboardInterrupt`` landing inside real CPython's
    ``Popen.__init__`` — after it has already forked/exec'd the child but
    while it's still blocked reading the child's error-relay pipe — would
    orphan a live process with no ``proc`` reference anything can reach.
    ``run_streaming_once`` closes that window by ignoring SIGINT for the
    duration of the ``Popen()`` call and restoring the previous handler
    right after, on the main thread only."""

    def test_sigint_ignored_around_popen_and_restored_after_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _PREV = object()
        calls: list[tuple[int, object]] = []

        def fake_signal(sig, handler):
            calls.append((sig, handler))
            return _PREV

        monkeypatch.setattr(backend_runner.signal, "signal", fake_signal)
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([(["ok\n"], [], 0)]),
        )

        _run_streaming("p")

        assert calls == [
            (backend_runner.signal.SIGINT, backend_runner.signal.SIG_IGN),
            (backend_runner.signal.SIGINT, _PREV),
        ]

    def test_sigint_falls_back_to_sig_dfl_when_previous_handler_was_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``signal.signal`` returns ``None`` (not ``SIG_DFL``) as the
        previous handler when SIGINT wasn't installed from Python — real
        under some embeddings, though not under plan-tool's own CLI
        startup. The restore must still fire (using ``SIG_DFL``, since
        ``None`` isn't a valid handler to pass back in) rather than being
        skipped — skipping it would leave SIGINT permanently ignored for
        the rest of the process, not just around this ``Popen()`` call."""
        calls: list[tuple[int, object]] = []

        def fake_signal(sig, handler):
            calls.append((sig, handler))
            return None

        monkeypatch.setattr(backend_runner.signal, "signal", fake_signal)
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([(["ok\n"], [], 0)]),
        )

        _run_streaming("p")

        assert calls == [
            (backend_runner.signal.SIGINT, backend_runner.signal.SIG_IGN),
            (backend_runner.signal.SIGINT, backend_runner.signal.SIG_DFL),
        ]

    def test_sigint_handler_restored_even_when_popen_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _PREV = object()
        calls: list[tuple[int, object]] = []

        def fake_signal(sig, handler):
            calls.append((sig, handler))
            return _PREV

        monkeypatch.setattr(backend_runner.signal, "signal", fake_signal)

        def raising_popen(*_a, **_kw):
            raise OSError("binary vanished")

        monkeypatch.setattr(backend_runner.subprocess, "Popen", raising_popen)

        with pytest.raises(OSError, match="binary vanished"):
            _run_streaming("p")

        assert calls == [
            (backend_runner.signal.SIGINT, backend_runner.signal.SIG_IGN),
            (backend_runner.signal.SIGINT, _PREV),
        ]

    def test_sigint_guard_skipped_off_the_main_thread(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``signal.signal`` only works on the main thread; a call made
        from a worker thread (e.g. a ``--jobs N`` fan-out) must not try it
        — such a thread can never receive a spontaneous
        ``KeyboardInterrupt`` in the first place, so nothing is lost."""
        calls: list[tuple[int, object]] = []

        def fake_signal(sig, handler):
            calls.append((sig, handler))
            return None

        monkeypatch.setattr(backend_runner.signal, "signal", fake_signal)
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([(["ok\n"], [], 0)]),
        )

        errors: list[BaseException] = []

        def worker() -> None:
            try:
                _run_streaming("p")
            except BaseException as exc:  # pragma: no cover - failure path
                errors.append(exc)

        t = threading.Thread(target=worker)
        t.start()
        t.join()

        assert not errors
        assert calls == []


class TestInterruptWindowCoversThreadStartAndStdinWrite:
    """The KeyboardInterrupt-safe window covers everything from the
    ``backend_spawn`` emit through ``proc.wait()`` — not just
    ``proc.wait()`` itself. The stdin write is the one piece of that
    window easy to exercise deterministically through a test double;
    thread-start and the ``backend_spawn`` emit share the same ``try`` and
    the same ``_finalize_interrupted_call`` tail, already covered by
    ``TestExceptionClassification``'s ``proc.wait()`` tests and
    ``test_exception_during_wait_still_joins_pump_and_heartbeat_threads``
    above."""

    def test_keyboard_interrupt_during_stdin_write_kills_and_reaps_the_child(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class _RaisingStdin:
            def write(self, text: str) -> None:
                raise KeyboardInterrupt()

            def close(self) -> None:
                pass

        class _StdinRaisingProc:
            def __init__(self) -> None:
                self.stdout = _FakePipe([])
                self.stderr = _FakePipe([])
                self.stdin = _RaisingStdin()
                self.returncode = None
                self.kill_called = False
                self.wait_calls = 0

            def poll(self):
                return self.returncode

            def wait(self) -> int:
                self.wait_calls += 1
                self.returncode = -9
                return self.returncode

            def kill(self) -> None:
                self.kill_called = True

        fake = _StdinRaisingProc()
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen", lambda *a, **kw: fake
        )

        logger = _StreamRecordingLogger()
        with pytest.raises(KeyboardInterrupt):
            backend_runner.run_streaming_once(
                "PROMPT",
                lambda prompt: PromptTransport(
                    ["backend", "--stdin"], stdin_text=prompt
                ),
                run_logger=logger,
            )

        assert fake.kill_called
        assert fake.wait_calls == 1, "must reap after killing"
        assert (
            backend_runner.get_last_termination_reason()
            is backend_runner.TerminationReason.OPERATOR_INTERRUPT
        )
        assert len(logger.interrupted_events) == 1
        assert logger.interrupted_events[0]["source"] == "proc_wait"
        assert logger.termination_events
        assert logger.termination_events[-1]["reason"] == "operator_interrupt"


class TestInterruptSourceVocabulary:
    def test_interrupt_source_values_match_the_persisted_strings(self) -> None:
        """Closed vocabulary backing every ``run_interrupted.source``
        producer (this module's two, plus ``claude_errors.py``'s
        recovery-wait wrappers) — pinned so a typo'd or renamed member is
        caught here rather than silently changing a persisted event's
        field value."""
        assert backend_runner.InterruptSource.SPAWN.value == "spawn"
        assert backend_runner.InterruptSource.PROC_WAIT.value == "proc_wait"
        assert (
            backend_runner.InterruptSource.RECOVERY_WAIT.value
            == "recovery_wait"
        )

    def test_claude_errors_recovery_wait_seams_use_the_shared_enum(self) -> None:
        """``claude_errors.py``'s two producer call sites import and use
        ``InterruptSource.RECOVERY_WAIT`` rather than a re-typed string
        literal — a source-level check (the persisted-event shape is
        already covered by tests/test_launcher.py and tests/test_shell.py)
        so a future site that reverts to a bare string literal fails here
        instead of only being caught by eyeballing a diff."""
        from plan_tool import claude_errors

        src = Path(claude_errors.__file__).read_text(encoding="utf-8")
        assert src.count("InterruptSource.RECOVERY_WAIT") == 2
        assert 'source="recovery_wait"' not in src


class _KillLadderThenInterruptProc:
    """``wait()`` blocks until the heartbeat's kill ladder has already
    fired (``terminate()`` called), then raises ``KeyboardInterrupt`` —
    deterministically sequences a monitor-thread kill *before* the operator
    interrupt so the precedence rule (interrupt always wins) is exercised
    without depending on real-time timing luck.
    """

    def __init__(self) -> None:
        self.stdout = _FakePipe([])
        self.stderr = _FakePipe([])
        self.stdin = None
        self.returncode = None
        self.terminate_called = False
        self.kill_called = False
        self._wait_calls = 0

    def wait(self) -> int:
        self._wait_calls += 1
        if self._wait_calls == 1:
            while not self.terminate_called:
                time.sleep(0.005)
            raise KeyboardInterrupt()
        self.returncode = -9
        return self.returncode

    def poll(self):
        return self.returncode

    def terminate(self) -> None:
        self.terminate_called = True

    def kill(self) -> None:
        self.kill_called = True
        self.returncode = -9


class TestOperatorInterruptPrecedence:
    def test_operator_interrupt_wins_race_against_monitor_thread_kill(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake = _KillLadderThenInterruptProc()
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen", lambda *a, **kw: fake
        )
        monkeypatch.setattr(backend_runner, "_PROGRESS_INTERVAL_S", 0.02)
        monkeypatch.setattr(backend_runner, "_KILL_AFTER_SILENCE_S", 0.02)
        monkeypatch.setattr(backend_runner, "_KILL_GRACE_S", 0.02)

        with pytest.raises(KeyboardInterrupt):
            _run_streaming("p")
        assert fake.terminate_called, (
            "the heartbeat's kill ladder must have fired first for this "
            "test to actually exercise the race"
        )
        assert (
            backend_runner.get_last_termination_reason()
            is backend_runner.TerminationReason.OPERATOR_INTERRUPT
        )

    def test_note_termination_reason_refuses_to_downgrade_from_operator_interrupt(
        self,
    ) -> None:
        """Direct, deterministic proof of the precedence primitive itself:
        ``OPERATOR_INTERRUPT`` always overwrites, and nothing else can
        overwrite it once recorded — regardless of write order."""
        cell = [None]
        lock = threading.Lock()
        backend_runner._note_termination_reason(
            cell, lock, backend_runner.TerminationReason.SILENCE_TIMEOUT
        )
        backend_runner._note_termination_reason(
            cell, lock, backend_runner.TerminationReason.OPERATOR_INTERRUPT
        )
        assert cell[0] is backend_runner.TerminationReason.OPERATOR_INTERRUPT

        backend_runner._note_termination_reason(
            cell, lock, backend_runner.TerminationReason.CONFIGURED_TIMEOUT
        )
        assert cell[0] is backend_runner.TerminationReason.OPERATOR_INTERRUPT


class TestTerminationReasonConcurrency:
    def test_termination_reason_is_call_scoped_under_concurrent_calls(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_popen(argv, *, stdout, stderr, text, stdin=None, cwd=None):
            rc = 0 if argv[-1] == "prompt-a" else 1
            return _FakeProc([], [], rc)

        monkeypatch.setattr(backend_runner.subprocess, "Popen", fake_popen)

        results: dict[str, object] = {}

        def worker(name: str, prompt: str) -> None:
            backend_runner.run_streaming_once(
                prompt, get_active_backend().streaming_transport
            )
            results[name] = backend_runner.get_last_termination_reason()

        t_a = threading.Thread(target=worker, args=("a", "prompt-a"))
        t_b = threading.Thread(target=worker, args=("b", "prompt-b"))
        t_a.start()
        t_b.start()
        t_a.join()
        t_b.join()

        assert results["a"] is backend_runner.TerminationReason.COMPLETED
        assert results["b"] is backend_runner.TerminationReason.BACKEND_NONZERO


class TestScopedSilenceTimeout:
    def test_scoped_silence_timeout_overrides_the_global_threshold_for_one_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        proc = _SilentUntilKilledProc()
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen", lambda *a, **kw: proc
        )
        monkeypatch.setattr(backend_runner, "_PROGRESS_INTERVAL_S", 0.02)
        # Deliberately much larger than the scope below — proves the
        # override, not the global default, is what actually fired.
        monkeypatch.setattr(backend_runner, "_KILL_AFTER_SILENCE_S", 5.0)
        monkeypatch.setattr(backend_runner, "_KILL_GRACE_S", 0.02)

        with backend_runner.scoped_silence_timeout(0.06):
            _run_streaming("p")

        assert proc.terminate_called
        assert (
            backend_runner.get_last_termination_reason()
            is backend_runner.TerminationReason.SILENCE_TIMEOUT
        )

    def test_scoped_silence_timeout_is_call_scoped_not_global(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(backend_runner, "_KILL_AFTER_SILENCE_S", 999.0)
        with backend_runner.scoped_silence_timeout(0.05):
            assert backend_runner._effective_silence_timeout_s() == 0.05
        # Outside the scope, the resolver reverts to the (unrelated, much
        # larger) global default — proving the override doesn't leak.
        assert backend_runner._effective_silence_timeout_s() == 999.0


def test_backend_runner_matches_pre_move_shell_invoker_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``launcher.shell_invoker`` end-to-end through the relocated
    runner: the Popen argv, stdin handling, and returned ``(rc, stdout)``
    shape are unchanged from before the move — the run lane still
    spawns the active backend's stream-json argv with a closed stdin."""
    from plan_tool import launcher

    seen_argv: list[list[str]] = []
    seen_stdin: list[object] = []
    factory = _make_popen_factory(
        [(["hello\n", "world\n"], [], 0)], seen_argv=seen_argv
    )

    def recording_popen(argv, **kwargs):
        if not (argv and argv[0] == "git"):
            seen_stdin.append(kwargs.get("stdin"))
        return factory(argv, **kwargs)

    monkeypatch.setattr(backend_runner.subprocess, "Popen", recording_popen)
    rc, out = launcher.shell_invoker("the prompt")
    assert (rc, out) == (0, "hello\nworld\n")
    argv = seen_argv[0]
    assert argv[0] == get_active_backend().binary
    assert "--output-format" in argv
    assert argv[argv.index("--output-format") + 1] == "stream-json"
    assert "--verbose" in argv
    assert argv[-1] == "the prompt"
    assert seen_stdin == [backend_runner.subprocess.DEVNULL]


def test_shell_invoker_propagates_keyboard_interrupt_with_child_killed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The kill-on-any-exception net also protects ``run``'s actual call
    path, not just the raw runner: a ``KeyboardInterrupt`` raised from
    ``run_streaming_once`` must still reach ``shell_invoker``'s caller
    unchanged — ``rate_limit_loop.run_with_rate_limit_recovery`` has no
    exception handling around its ``run_once`` call, so nothing between
    here and there may swallow or retry it — with the child killed."""
    from plan_tool import launcher

    fake = _RaisingWaitProc(KeyboardInterrupt())
    monkeypatch.setattr(
        backend_runner.subprocess, "Popen", lambda *a, **kw: fake
    )
    with pytest.raises(KeyboardInterrupt):
        launcher.shell_invoker("the prompt")
    assert fake.kill_called


def _tool_use_ndjson_line() -> str:
    return json.dumps({
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "name": "Bash",
                    "input": {"command": "echo secret-path"},
                }
            ]
        },
    }) + "\n"


class TestRedactionReady:
    """``redaction_ready`` gates only the ``-v`` console print of a
    ``tool_use`` event's ``tool_input_summary`` — batch-authoring-
    observability plan step 6."""

    def test_default_redaction_ready_prints_real_summary(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The default (``True``, ``run``'s call sites) is unchanged from
        before this step: the real summary prints."""
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([([_tool_use_ndjson_line()], [], 0)]),
        )
        monkeypatch.setattr(
            backend_runner, "_console_verbosity",
            backend_runner._CONSOLE_VERBOSITY_VERBOSE,
        )
        _run_streaming("p")
        err = capsys.readouterr().err
        assert "echo secret-path" in err
        assert "[OMITTED]" not in err

    def test_redaction_ready_false_prints_omitted(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([([_tool_use_ndjson_line()], [], 0)]),
        )
        monkeypatch.setattr(
            backend_runner, "_console_verbosity",
            backend_runner._CONSOLE_VERBOSITY_VERBOSE,
        )
        _run_streaming("p", redaction_ready=False)
        err = capsys.readouterr().err
        assert "[OMITTED]" in err
        assert "echo secret-path" not in err

    def test_redaction_ready_does_not_affect_claude_stream_event_or_debug_passthrough(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``redaction_ready=False`` gates only the console ``-v`` print: a
        bound ``run_logger``'s ``claude_stream_event`` still carries the real
        (unredacted) summary, and ``--debug``'s raw NDJSON passthrough is
        unaffected either way."""
        line = _tool_use_ndjson_line()
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([([line], [], 0)]),
        )
        logger = _StreamRecordingLogger()
        monkeypatch.setattr(
            backend_runner, "_console_verbosity",
            backend_runner._CONSOLE_VERBOSITY_DEBUG,
        )
        _run_streaming("p", run_logger=logger, redaction_ready=False)
        assert logger.stream_events[0]["tool_input_summary"] == "echo secret-path"
        out = capsys.readouterr().out
        assert line.strip() in out


class TestStderrVerbosityGate:
    """``_pump_stderr``'s live passthrough is gated behind ``-v``/``--debug``
    (Architecture's allowed-changes item 7); the returned ``stderr_buffer``
    always carries every line at every verbosity."""

    def test_stderr_stays_silent_at_default_verbosity(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([([], ["a stderr line\n"], 0)]),
        )
        _rc, _stdout, stderr_text, _stats = _run_streaming("p")
        assert capsys.readouterr().err == ""
        assert stderr_text == "a stderr line\n"

    def test_stderr_streams_live_at_verbose(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([([], ["a stderr line\n"], 0)]),
        )
        monkeypatch.setattr(
            backend_runner, "_console_verbosity",
            backend_runner._CONSOLE_VERBOSITY_VERBOSE,
        )
        _rc, _stdout, stderr_text, _stats = _run_streaming("p")
        err = capsys.readouterr().err
        assert "a stderr line" in err
        assert stderr_text == "a stderr line\n"


class _PidTrackingProc:
    """Popen stand-in carrying a real ``.pid`` — the shared ``_FakeProc``
    (tests/subprocess_doubles.py) has none, since nothing needed one before
    ``backend_spawn``'s ``child_pid`` field. Local to this file rather than
    added to the shared double: only this step's spawn-event test cares."""

    def __init__(
        self, stdout_lines: list[str], *, pid: int, returncode: int = 0
    ) -> None:
        self.stdout = _FakePipe(stdout_lines)
        self.stderr = _FakePipe([])
        self.stdin = None
        self.returncode = returncode
        self.pid = pid

    def wait(self) -> int:
        return self.returncode


class _ToolUseThenSilentProc:
    """Emits one NDJSON line immediately, then goes silent (blocking
    ``wait()``) until ``terminate()``/``kill()`` fires — for tests proving
    ``claude_stream_event`` and the progress/stall/kill signals all still
    fire off the same writer in one call."""

    def __init__(self, line: str, *, returncode: int = -15) -> None:
        self._dead = threading.Event()
        self.stdout = self._Pipe([line], self._dead)
        self.stderr = _FakePipe([])
        self.stdin = None
        self.returncode = returncode
        self.terminate_called = False
        self.kill_called = False

    class _Pipe:
        def __init__(self, lines: list[str], dead: threading.Event) -> None:
            self._lines = lines
            self._dead = dead

        def __iter__(self):
            yield from self._lines
            self._dead.wait(timeout=5.0)
            return

    def wait(self) -> int:
        self._dead.wait(timeout=5.0)
        return self.returncode

    def poll(self):
        return self.returncode if self._dead.is_set() else None

    def terminate(self) -> None:
        self.terminate_called = True
        self._dead.set()

    def kill(self) -> None:
        self.kill_called = True
        self._dead.set()


class TestRunnerObserverWidening:
    """Batch-authoring-observability plan, steps 7–8: ``run_logger``'s
    accepted shape widens from a bare ``RunLogWriter`` to any object
    providing the wider observer contract. A bare fake writer (the
    existing shape from steps 2–4) keeps the stream/progress/stall
    signal it already had and gains spawn/termination (step 7) and
    ``run_interrupted`` (step 8) — the same call a caller-built full
    observer (``shell.claude_invoke``'s) gets; ``run_logger=None`` still
    produces no calls at all; and a buggy observer callback can't kill the
    pump/heartbeat thread or suppress the silence kill."""

    def test_suppressed_observer_error_does_not_echo_its_detail(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        class _StructuralObserver:
            suppress_error_output = True

            def claude_stream_event(self, **_kwargs) -> None:
                raise RuntimeError("structural secret")

        backend_runner._safe_observer_call(
            _StructuralObserver(), "claude_stream_event"
        )

        assert capsys.readouterr().err == ""

    def test_bare_run_logger_still_receives_stream_progress_stall_events(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        proc = _ToolUseThenSilentProc(_tool_use_ndjson_line())
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen", lambda *a, **kw: proc
        )
        monkeypatch.setattr(backend_runner, "_PROGRESS_INTERVAL_S", 0.02)
        monkeypatch.setattr(backend_runner, "_STALL_THRESHOLD_S", 0.05)
        monkeypatch.setattr(backend_runner, "_KILL_AFTER_SILENCE_S", 0.10)
        monkeypatch.setattr(backend_runner, "_KILL_GRACE_S", 0.05)

        logger = _StreamRecordingLogger()
        _run_streaming("p", run_logger=logger)

        assert any(e["kind"] == "tool_use" for e in logger.stream_events)
        assert logger.progress_events
        assert logger.stall_events

    def test_bare_run_logger_now_also_receives_backend_spawn_and_termination(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([(["ok\n"], [], 0)]),
        )
        logger = _StreamRecordingLogger()
        _run_streaming("p", run_logger=logger)

        assert len(logger.spawn_events) == 1
        assert logger.spawn_events[0]["backend"] == get_active_backend().name
        assert len(logger.termination_events) == 1
        assert logger.termination_events[0]["reason"] == "completed"

    @pytest.mark.parametrize(
        "setup_kind",
        [
            "completed",
            "backend_nonzero",
            "configured_timeout",
            "spawn_failure",
            "operator_interrupt",
        ],
    )
    def test_backend_termination_reason_matches_get_last_termination_reason(
        self, monkeypatch: pytest.MonkeyPatch, setup_kind: str
    ) -> None:
        logger = _StreamRecordingLogger()
        if setup_kind == "completed":
            monkeypatch.setattr(
                backend_runner.subprocess, "Popen",
                _make_popen_factory([(["ok\n"], [], 0)]),
            )
            _run_streaming("p", run_logger=logger)
        elif setup_kind == "backend_nonzero":
            monkeypatch.setattr(
                backend_runner.subprocess, "Popen",
                _make_popen_factory([(["fail\n"], [], 1)]),
            )
            _run_streaming("p", run_logger=logger)
        elif setup_kind == "configured_timeout":
            proc = _NeverSilentProc()
            monkeypatch.setattr(
                backend_runner.subprocess, "Popen", lambda *a, **kw: proc
            )
            monkeypatch.setattr(backend_runner, "_PROGRESS_INTERVAL_S", 0.02)
            monkeypatch.setattr(backend_runner, "_KILL_AFTER_SILENCE_S", 10.0)
            monkeypatch.setattr(backend_runner, "_KILL_GRACE_S", 0.02)
            _run_streaming(
                "p", run_logger=logger,
                enforce_configured_timeout=True, configured_timeout_s=0.06,
            )
        elif setup_kind == "spawn_failure":
            def raising_popen(*_a, **_kw):
                raise OSError("binary vanished")

            monkeypatch.setattr(backend_runner.subprocess, "Popen", raising_popen)
            with pytest.raises(OSError):
                _run_streaming("p", run_logger=logger)
        else:  # operator_interrupt
            fake = _RaisingWaitProc(KeyboardInterrupt())
            monkeypatch.setattr(
                backend_runner.subprocess, "Popen", lambda *a, **kw: fake
            )
            with pytest.raises(KeyboardInterrupt):
                _run_streaming("p", run_logger=logger)

        expected_reason = backend_runner.get_last_termination_reason().value
        assert logger.termination_events
        assert logger.termination_events[-1]["reason"] == expected_reason

    def test_backend_spawn_carries_child_pid_transport_and_prompt_bytes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake = _PidTrackingProc(["ok\n"], pid=424242)
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen", lambda *a, **kw: fake
        )
        logger = _StreamRecordingLogger()
        _run_streaming("hello world", run_logger=logger)

        spawn = logger.spawn_events[0]
        assert spawn["child_pid"] == 424242
        assert spawn["transport"] == "streaming_transport"
        assert spawn["prompt_bytes"] == len("hello world".encode("utf-8"))

    def test_backend_spawn_effective_timeout_ms_reports_the_earlier_threshold(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(backend_runner, "_KILL_AFTER_SILENCE_S", 900.0)

        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([(["ok\n"], [], 0)]),
        )
        logger = _StreamRecordingLogger()
        _run_streaming(
            "p", run_logger=logger,
            enforce_configured_timeout=True, configured_timeout_s=30.0,
        )
        assert logger.spawn_events[0]["effective_timeout_ms"] == 30_000

        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([(["ok\n"], [], 0)]),
        )
        logger2 = _StreamRecordingLogger()
        _run_streaming("p", run_logger=logger2)
        assert logger2.spawn_events[0]["effective_timeout_ms"] == 900_000

    def test_backend_termination_carries_signal_or_timeout_and_silent_ms_on_a_kill(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        proc = _SilentUntilKilledProc()
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen", lambda *a, **kw: proc
        )
        monkeypatch.setattr(backend_runner, "_PROGRESS_INTERVAL_S", 0.02)
        monkeypatch.setattr(backend_runner, "_KILL_AFTER_SILENCE_S", 0.05)
        monkeypatch.setattr(backend_runner, "_KILL_GRACE_S", 0.02)

        logger = _StreamRecordingLogger()
        _run_streaming("p", run_logger=logger)

        term = logger.termination_events[-1]
        assert term["reason"] == "silence_timeout"
        assert term["signal_or_timeout"] == "SIGTERM"
        assert isinstance(term["silent_ms"], int) and term["silent_ms"] >= 0

        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([(["ok\n"], [], 0)]),
        )
        logger2 = _StreamRecordingLogger()
        _run_streaming("p", run_logger=logger2)
        assert logger2.termination_events[-1]["signal_or_timeout"] is None

    def test_bare_run_logger_receives_run_interrupted_on_keyboard_interrupt(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A bare :class:`RunLogWriter` — the shape ``run``'s
        ``shell_invoker`` passes via ``run_step``'s ContextVar plumbing —
        now gets the same ``run_interrupted`` call a caller-built full
        observer already got (batch-authoring-observability step 8's
        fallback widening), alongside the matching ``operator_interrupt``
        termination. The child is still killed and reaped through step 3's
        net, and the exception still propagates."""
        from plan_tool.run_log import RunLogWriter, read_run_events

        fake = _RaisingWaitProc(KeyboardInterrupt())
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen", lambda *a, **kw: fake
        )

        writer = RunLogWriter.start(
            repo_root=tmp_path, slug="demo", command="run",
            argv=["plan-tool", "run"],
        )

        with pytest.raises(KeyboardInterrupt):
            _run_streaming("p", run_logger=writer)

        assert fake.kill_called
        assert fake.wait_calls == 2

        events = read_run_events(writer.log_path)
        interrupted = [e for e in events if e.get("event") == "run_interrupted"]
        assert len(interrupted) == 1
        assert interrupted[0]["source"] == "proc_wait"
        terminations = [e for e in events if e.get("event") == "backend_termination"]
        assert len(terminations) == 1
        assert terminations[0]["reason"] == "operator_interrupt"

    def test_run_logger_none_gets_no_events_on_keyboard_interrupt(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``run_logger=None`` on the same interrupt: no observer calls at
        all (``_safe_observer_call`` no-ops), and the child is still killed
        and reaped — callers without a writer keep today's behavior."""
        fake = _RaisingWaitProc(KeyboardInterrupt())
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen", lambda *a, **kw: fake
        )

        with pytest.raises(KeyboardInterrupt):
            _run_streaming("p", run_logger=None)

        assert fake.kill_called
        assert fake.wait_calls == 2
        assert capsys.readouterr().err == ""

    def test_bare_writer_interrupt_callback_exception_does_not_break_the_unwind(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A writer whose ``run_interrupted`` itself raises must not
        surface that exception in place of the ``KeyboardInterrupt``, and
        must not skip the reap: ``_safe_observer_call`` swallows this call
        exactly like every other observer call."""

        class _RaisingInterruptWriter:
            def claude_stream_event(self, **kwargs):
                pass

            def claude_call_progress(self, **kwargs):
                pass

            def claude_call_stall_suspected(self, **kwargs):
                pass

            def backend_spawn(self, **kwargs):
                pass

            def backend_termination(self, **kwargs):
                pass

            def run_interrupted(self, **kwargs):
                raise RuntimeError("writer boom")

        fake = _RaisingWaitProc(KeyboardInterrupt())
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen", lambda *a, **kw: fake
        )

        with pytest.raises(KeyboardInterrupt):
            _run_streaming("p", run_logger=_RaisingInterruptWriter())

        assert fake.kill_called
        assert fake.wait_calls == 2
        err = capsys.readouterr().err
        assert "run_interrupted" in err
        assert "RuntimeError" in err

    def test_second_keyboard_interrupt_from_observer_does_not_replace_the_first(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A *second* ``KeyboardInterrupt`` landing inside the observer's
        own ``run_interrupted`` call (plausible:
        ``RunLogWriter._refresh_in_flight`` does file I/O under a lock)
        must not silently replace the first interrupt this function is
        already unwinding for. ``_safe_observer_call`` only swallows a
        plain ``Exception``, not a ``BaseException`` like this one, so
        ``_finalize_interrupted_call`` guards the call a second time."""

        class _SecondInterruptWriter:
            def claude_stream_event(self, **kwargs):
                pass

            def claude_call_progress(self, **kwargs):
                pass

            def claude_call_stall_suspected(self, **kwargs):
                pass

            def backend_spawn(self, **kwargs):
                pass

            def backend_termination(self, **kwargs):
                pass

            def run_interrupted(self, **kwargs):
                raise KeyboardInterrupt("second")

        first = KeyboardInterrupt("first")
        fake = _RaisingWaitProc(first)
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen", lambda *a, **kw: fake
        )

        with pytest.raises(KeyboardInterrupt) as excinfo:
            _run_streaming("p", run_logger=_SecondInterruptWriter())

        assert excinfo.value is first
        assert fake.kill_called
        assert fake.wait_calls == 2

    def test_full_observer_receives_interrupted_with_source_proc_wait_on_keyboard_interrupt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A caller-supplied observer — anything other than a bare
        ``RunLogWriter``/``None``, the shape ``shell.claude_invoke``
        builds — receives one interrupt call with ``source="proc_wait"``
        alongside the matching ``operator_interrupt``-reasoned termination
        call, on the same ``KeyboardInterrupt``."""
        fake = _RaisingWaitProc(KeyboardInterrupt())
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen", lambda *a, **kw: fake
        )

        logger = _StreamRecordingLogger()
        with pytest.raises(KeyboardInterrupt):
            _run_streaming("p", run_logger=logger)

        assert len(logger.interrupted_events) == 1
        assert logger.interrupted_events[0]["source"] == "proc_wait"
        assert logger.termination_events
        assert logger.termination_events[-1]["reason"] == "operator_interrupt"

    def test_observer_callback_exception_does_not_kill_the_pump_thread(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        class _RaisingObserver:
            def claude_stream_event(self, **kwargs):
                raise RuntimeError("boom")

            def claude_call_progress(self, **kwargs):
                pass

            def claude_call_stall_suspected(self, **kwargs):
                pass

            def backend_spawn(self, **kwargs):
                pass

            def backend_termination(self, **kwargs):
                pass

            def run_interrupted(self, **kwargs):
                pass

        lines = [_tool_use_ndjson_line(), claude_result_ndjson("final answer")]
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([(lines, [], 0)]),
        )

        rc, _stdout, _stderr, stats = _run_streaming(
            "p", run_logger=_RaisingObserver()
        )

        assert rc == 0
        assert stats is not None and stats.final_text == "final answer"
        err = capsys.readouterr().err
        assert "claude_stream_event" in err
        assert "RuntimeError" in err

    def test_parse_stream_line_exception_does_not_kill_the_pump_thread(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A buggy backend parser must not wedge the call the way a dead
        pump thread would (proc.wait() blocks until the silence-kill
        ladder finally notices) — the offending line falls back to raw
        stdout and the pump keeps draining subsequent lines."""
        import dataclasses

        real_backend = get_active_backend()

        def _raising_parse(line: str, *, bytes_in: int):
            if "BOOM" in line:
                raise RuntimeError("boom")
            return real_backend.parse_stream_line(line, bytes_in=bytes_in)

        fake_backend = dataclasses.replace(
            real_backend, parse_stream_line=_raising_parse
        )
        monkeypatch.setattr(
            backend_runner, "get_active_backend", lambda: fake_backend
        )
        lines = ["BOOM\n", claude_result_ndjson("final answer")]
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([(lines, [], 0)]),
        )

        rc, stdout_text, _stderr, stats = _run_streaming("p")

        assert rc == 0
        assert stats is not None and stats.final_text == "final answer"
        assert "BOOM" in stdout_text
        err = capsys.readouterr().err
        assert "stream-line parse failed" in err
        assert "RuntimeError" in err

    def test_observer_callback_exception_does_not_suppress_the_silence_kill(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class _RaisingObserver:
            def claude_stream_event(self, **kwargs):
                pass

            def claude_call_progress(self, **kwargs):
                raise RuntimeError("boom")

            def claude_call_stall_suspected(self, **kwargs):
                raise RuntimeError("boom")

            def backend_spawn(self, **kwargs):
                pass

            def backend_termination(self, **kwargs):
                pass

            def run_interrupted(self, **kwargs):
                pass

        proc = _SilentUntilKilledProc()
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen", lambda *a, **kw: proc
        )
        monkeypatch.setattr(backend_runner, "_PROGRESS_INTERVAL_S", 0.02)
        monkeypatch.setattr(backend_runner, "_STALL_THRESHOLD_S", 0.05)
        monkeypatch.setattr(backend_runner, "_KILL_AFTER_SILENCE_S", 0.10)
        monkeypatch.setattr(backend_runner, "_KILL_GRACE_S", 0.05)

        rc, _, _, _ = _run_streaming("p", run_logger=_RaisingObserver())

        assert proc.terminate_called
        assert rc == -15

    def test_run_logger_none_produces_no_observer_calls(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen",
            _make_popen_factory([(["ok\n"], [], 0)]),
        )
        rc, stdout_text, _stderr, _stats = _run_streaming("p", run_logger=None)
        assert (rc, stdout_text) == (0, "ok\n")
        assert capsys.readouterr().err == ""

    def test_none_pipes_reaps_the_spawned_child_before_raising(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A ``Popen`` double that doesn't set ``.stdout``/``.stderr``
        (unreachable with a real ``Popen``, since ``stdout=PIPE``/
        ``stderr=PIPE`` are hardcoded) must not leak the already-spawned
        child — the pipes-None guard kills and reaps it before raising."""

        class _NoPipesProc:
            def __init__(self) -> None:
                self.stdout = None
                self.stderr = None
                self.kill_called = False
                self.wait_called = False

            def kill(self) -> None:
                self.kill_called = True

            def wait(self) -> int:
                self.wait_called = True
                return 0

        fake = _NoPipesProc()
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen", lambda *a, **kw: fake
        )

        with pytest.raises(RuntimeError, match="subprocess pipes are None"):
            _run_streaming("p")

        assert fake.kill_called
        assert fake.wait_called


def test_ndjson_response_builder_produces_a_parseable_result_envelope() -> None:
    """``claude_result_ndjson`` (tests/subprocess_doubles.py) builds a line
    ``_claude_parse_stream_line`` parses back into the expected
    ``final_text``/stats — the shared helper single-response fixtures use
    instead of hand-writing the JSON envelope."""
    line = claude_result_ndjson("the answer", usage={"input_tokens": 3})
    parsed = _claude_parse_stream_line(line, bytes_in=len(line.encode("utf-8")))
    assert parsed is not None
    assert parsed.stats is not None
    assert parsed.stats.final_text == "the answer"
    assert parsed.stats.tokens_input == 3


def test_structural_profile_suppresses_debug_stream_and_tool_records(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tool_line = (
        '{"type":"assistant","message":{"content":[{"type":"tool_use",'
        '"name":"Bash","input":{"command":"secret command"}}]}}\n'
    )
    monkeypatch.setattr(
        backend_runner.subprocess, "Popen",
        _make_popen_factory([([tool_line, claude_result_ndjson("secret reply")], [], 0)]),
    )
    logger = _StreamRecordingLogger()
    old_verbosity = backend_runner.get_console_verbosity()
    backend_runner.set_console_verbosity(2)
    try:
        rc, stdout, _stderr, _stats = _run_streaming(
            "prompt", run_logger=logger, suppress_content_output=True
        )
    finally:
        backend_runner.set_console_verbosity(old_verbosity)

    assert rc == 0
    assert "secret reply" in stdout
    assert logger.stream_events == []
    captured = capsys.readouterr()
    assert "secret command" not in captured.out + captured.err
    assert "secret reply" not in captured.out + captured.err
