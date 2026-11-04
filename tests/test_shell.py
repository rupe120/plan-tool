"""Tests for plan_tool.shell.

No real claude shell-out; we monkeypatch ``backend_runner.subprocess.Popen``
and ``shutil.which`` so every test stays hermetic. The module under test is
the wall-clock-timing wrapper around ``claude -p`` plus the module-level
``ClaudeCallEnd`` sink installed by higher-level callers; tests here
pin the ``(rc, stdout)`` contract and the sink-emit / error-swallow
behavior added in the run-log-structured-events step 2, and — since the
batch-authoring-observability plan's step 6 — that ``claude_invoke`` spawns
exclusively through ``backend_runner.run_streaming_once`` rather than
``subprocess.run``.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
import threading
from itertools import repeat
from types import SimpleNamespace
from typing import Callable, Optional

import pytest

from pathlib import Path

from subprocess_doubles import (
    _FakePipe,
    _FakeProc,
    _make_popen_factory,
    claude_result_ndjson,
)
from plan_tool import backend_runner, claude_errors, shell, style
from plan_tool.backend import CLAUDE_BACKEND, observe_context_window, scoped_active_backend
from plan_tool.context_window import active_context_window, context_window_for
from plan_tool.rate_limit_loop import RetryPolicy
from plan_tool.run_log import ClaudeCallEnd
from test_backend_runner import (
    _NeverSilentProc,
    _RaisingWaitProc,
    _SilentUntilKilledProc,
)


_CURSOR_MONTHLY_PLAN_QUOTA = (
    "ActionRequiredError: You've hit your usage limit for Opus. "
    "Switch to a different model or set a Spend Limit. "
    "Your usage limits will reset when your monthly cycle ends on 8/24/2026."
)


@pytest.fixture(autouse=True)
def _no_sink_guard_already_burned(monkeypatch: pytest.MonkeyPatch):
    """Pin ``shell._warned_no_sink`` True so the once-only no-sink warning
    stays off unless a test opts in.

    The flag is a process-global one-shot, so a test asserting "no stderr"
    passed only when an earlier test in the same process happened to burn it
    first — green in a serial full run, red in isolation or whenever
    ``-n auto`` put it at a worker's head, meaning a test added anywhere in
    the suite could flip it. The warning is incidental to almost every test
    here; the few that assert on it set the flag False themselves, which wins
    over this fixture (class-scoped and in-test monkeypatches both apply
    later).
    """
    monkeypatch.setattr(shell, "_warned_no_sink", True)


# ---------- helpers ----------


def _fake_popen_factory(
    *,
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
    on_argv: Optional[Callable[[list[str]], None]] = None,
    on_cwd: Optional[Callable[[object], None]] = None,
) -> Callable:
    """Build a Popen stand-in that yields one canned response every call,
    recording argv/cwd via callback.

    Thin wrapper over ``_make_popen_factory`` (git argv delegates to the
    real Popen so the batch path's retry-guard git read isn't answered
    with backend output).
    """
    response = (
        stdout.splitlines(keepends=True),
        stderr.splitlines(keepends=True),
        returncode,
    )

    def _on_kwargs(kwargs: dict) -> None:
        if on_cwd is not None:
            on_cwd(kwargs.get("cwd"))

    return _make_popen_factory(repeat(response), on_argv=on_argv, on_kwargs=_on_kwargs)


@pytest.fixture(autouse=True)
def _clear_sink_between_tests(monkeypatch: pytest.MonkeyPatch):
    """Each test starts with no sink installed and leaves none behind, and the
    real prompt-budget recorder neutralized so the backstop never writes into
    the repo's ``.plan-tool/telemetry/``. Backstop-recording tests install
    their own spy, which overrides this default."""
    shell.set_active_sink(None)
    shell._prompt_budget_backstop_suppression.set(False)
    monkeypatch.setattr(shell, "record_prompt_budget", lambda *a, **k: None)
    yield
    shell.set_active_sink(None)
    shell._prompt_budget_backstop_suppression.set(False)


# ---------- claude_invoke: PATH guard ----------


def test_invoke_returns_127_when_claude_not_on_path(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(shell.shutil, "which", lambda _name: None)

    called = {"n": 0}

    def explode(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("Popen must not be called on missing exe")

    monkeypatch.setattr(backend_runner.subprocess, "Popen", explode)

    recorded: list[ClaudeCallEnd] = []
    shell.set_active_sink(recorded.append)

    rc, out = shell.claude_invoke("hello")

    assert (rc, out) == (shell.EXEC_NOT_FOUND_EXIT, "")
    assert called["n"] == 0
    assert recorded == []  # no subprocess ran → no event
    assert "not found on PATH" in capsys.readouterr().err


def test_invoke_does_not_emit_on_missing_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shell.shutil, "which", lambda _name: None)
    monkeypatch.setattr(
        backend_runner.subprocess,
        "Popen",
        _fake_popen_factory(stdout="ignored", returncode=0),
    )

    recorded: list[ClaudeCallEnd] = []
    shell.set_active_sink(recorded.append)

    shell.claude_invoke("anything")

    assert recorded == []


# ---------- claude_invoke: argv and return shape ----------


def test_invoke_passes_stream_json_argv_to_subprocess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Batch spawn uses ``stream-json`` so the terminal envelope carries
    usage/cache tokens; ``claude_invoke``'s collapse rule unwraps it back to
    the assistant text the downstream parsers expect (BACKLOG #74)."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")

    seen: dict[str, list[str]] = {}

    def remember(argv: list[str]) -> None:
        seen["argv"] = list(argv)

    monkeypatch.setattr(
        backend_runner.subprocess,
        "Popen",
        _fake_popen_factory(stdout="ok", returncode=0, on_argv=remember),
    )

    shell.claude_invoke("PROMPT")

    assert seen["argv"] == [
        "claude",
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--permission-mode",
        "acceptEdits",
        "PROMPT",
    ]


def test_run_once_spawns_in_active_spawn_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The batch spawn passes ``backend.get_active_spawn_cwd()`` as cwd.

    Default (no scope) is ``None`` — inherit the process cwd, the
    historical behavior. Inside a ``spawn_cwd`` scope the backend runs
    in the scoped tree; without the kwarg a caller whose ``repo_root``
    differs from the process cwd spawns backends against the wrong
    tree (the bench found this live: scratch trials edited the
    invoking repo).
    """
    from plan_tool.backend import spawn_cwd

    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    seen: list[object] = []
    monkeypatch.setattr(
        backend_runner.subprocess,
        "Popen",
        _fake_popen_factory(stdout="ok", returncode=0, on_cwd=seen.append),
    )

    shell.claude_invoke("PROMPT")
    with spawn_cwd(tmp_path):
        shell.claude_invoke("PROMPT")
    shell.claude_invoke("PROMPT")

    assert seen == [None, tmp_path, None]


# ---------- claude_invoke: backend routing ----------


def test_run_once_routes_through_active_backend_argv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``claude_invoke``'s seam builds argv from the active backend, not a literal."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")

    seen: dict[str, list[str]] = {}

    def remember(argv: list[str]) -> None:
        seen["argv"] = list(argv)

    monkeypatch.setattr(
        backend_runner.subprocess,
        "Popen",
        _fake_popen_factory(stdout="ok", returncode=0, on_argv=remember),
    )
    from plan_tool.backend import PromptTransport

    fake_backend = SimpleNamespace(
        binary="claude",
        batch_argv=lambda prompt: ["SENTINEL", prompt],
        batch_transport=lambda prompt: PromptTransport(["SENTINEL", prompt]),
    )
    monkeypatch.setattr(shell, "get_active_backend", lambda: fake_backend)

    shell.claude_invoke("PROMPT")

    assert seen["argv"] == ["SENTINEL", "PROMPT"]


def test_run_once_supports_stdin_prompt_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A backend can carry the prompt on stdin instead of argv.

    ``run_streaming_once`` opens the child's stdin as ``subprocess.PIPE``
    (rather than ``subprocess.run``'s ``input=`` kwarg), writes the prompt,
    then closes it — assert on the fake pipe's recorded write instead of an
    ``input=`` kwarg.
    """
    from plan_tool.backend import PromptTransport

    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/backend")
    seen_argv: list[list[str]] = []
    seen_kwargs: dict[str, object] = {}
    procs: list = []
    monkeypatch.setattr(
        backend_runner.subprocess,
        "Popen",
        _make_popen_factory(
            [(["ok"], [], 0)],
            seen_argv=seen_argv,
            on_kwargs=lambda kw: seen_kwargs.update(kw),
            procs=procs,
        ),
    )
    fake_backend = SimpleNamespace(
        binary="backend",
        batch_output="stdout",
        batch_transport=lambda prompt: PromptTransport(
            ["backend", "--stdin"], stdin_text=prompt
        ),
    )
    monkeypatch.setattr(shell, "get_active_backend", lambda: fake_backend)

    assert shell.claude_invoke("PROMPT") == (0, "ok")
    assert seen_argv == [["backend", "--stdin"]]
    assert seen_kwargs["stdin"] == backend_runner.subprocess.PIPE
    assert len(procs) == 1
    assert procs[0].stdin.written == "PROMPT"
    assert procs[0].stdin.closed is True


def test_path_guard_uses_active_backend_binary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The PATH guard probes the active backend's binary name."""
    probed: list[str] = []

    def fake_which(name: str) -> None:
        probed.append(name)
        return None

    monkeypatch.setattr(shell.shutil, "which", fake_which)
    fake_backend = SimpleNamespace(
        binary="fakebin",
        batch_argv=lambda prompt: ["fakebin", prompt],
    )
    monkeypatch.setattr(shell, "get_active_backend", lambda: fake_backend)

    rc, out = shell.claude_invoke("hi")

    assert (rc, out) == (shell.EXEC_NOT_FOUND_EXIT, "")
    assert probed == ["fakebin"]


def test_invoke_returns_raw_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    monkeypatch.setattr(
        backend_runner.subprocess,
        "Popen",
        _fake_popen_factory(stdout="hello\nworld\n", returncode=0),
    )

    result = shell.claude_invoke("x")

    assert result == (0, "hello\nworld\n")


def test_codex_batch_json_returns_final_agent_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from plan_tool.backend import CODEX_BACKEND, set_active_backend

    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/codex")
    set_active_backend(CODEX_BACKEND)
    stream = (
        '{"type":"thread.started","thread_id":"tid"}\n'
        '{"type":"turn.started"}\n'
        '{"type":"item.completed","item":{"id":"item_0","type":"agent_message",'
        '"text":"intermediate"}}\n'
        '{"type":"item.completed","item":{"id":"item_1","type":"agent_message",'
        '"text":"final answer"}}\n'
        '{"type":"turn.completed","usage":{"input_tokens":1,'
        '"cached_input_tokens":0,"output_tokens":2}}\n'
    )
    monkeypatch.setattr(
        backend_runner.subprocess,
        "Popen",
        _fake_popen_factory(stdout=stream, returncode=0),
    )

    assert shell.claude_invoke("x") == (0, "final answer")


def test_structural_codex_invoker_uses_the_fixed_outer_transport_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[dict] = []

    def invoke(prompt, transport, **kwargs):
        calls.append({"argv": transport(prompt).argv, **kwargs})
        return 0, "ignored", "backend-secret", SimpleNamespace(final_text="closed", tokens_input=None, tokens_output=None, cache_creation_tokens=None, cache_read_tokens=None, request_id=None, cost_usd=None)

    monkeypatch.setattr(backend_runner, "run_streaming_once", invoke)

    assert shell.structural_codex_invoke(
        "P",
        isolated_root=tmp_path / "empty",
        seatbelt_profile=tmp_path / "profile.sb",
        phase="structural",
    ) == (0, "closed")
    assert calls[0]["argv"] == [
        "/usr/bin/sandbox-exec", "-f", str(tmp_path / "profile.sb"),
        "codex", "exec", "--json", "-C", str((tmp_path / "empty").resolve()),
        "-s", "read-only", "--skip-git-repo-check", "--ephemeral",
        "--ignore-user-config", "--ignore-rules", "P",
    ]
    assert calls[0]["suppress_content_output"] is True


def test_claude_invoke_collapses_to_final_text_over_duplicated_stream_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When streamed ``assistant`` text chunks precede a terminal ``result``
    line, ``claude_invoke`` returns the ``result`` line's own text alone —
    never the two concatenated. ``run_streaming_once``'s ``stdout_buffer``
    joins every parsed chunk unconditionally (both the intermediate
    ``assistant`` text and the terminal envelope's own ``final_text``), so
    reusing it as-is would duplicate this text; ``_run_once_seam``'s collapse
    rule (``stats.final_text if stats and stats.final_text else stdout_text``)
    is what prevents that."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    stream = (
        '{"type":"assistant","message":{"content":[{"type":"text",'
        '"text":"first chunk"}]}}\n'
        '{"type":"assistant","message":{"content":[{"type":"text",'
        '"text":"second chunk"}]}}\n'
        '{"type":"result","result":"final answer",'
        '"usage":{"input_tokens":1,"output_tokens":1}}\n'
    )
    monkeypatch.setattr(
        backend_runner.subprocess,
        "Popen",
        _fake_popen_factory(stdout=stream, returncode=0),
    )

    assert shell.claude_invoke("prompt") == (0, "final answer")


def test_claude_invoke_falls_back_to_joined_buffer_for_plain_stdout_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A backend whose lines never parse as JSON (``batch_output="stdout"``)
    falls back to the raw joined buffer, with no special-casing on
    ``batch_output`` — the fallback falls straight out of every line failing
    to parse, matching ``_normalize_batch_stdout``'s old non-JSON branch."""
    from plan_tool.backend import PromptTransport

    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/backend")
    fake_backend = SimpleNamespace(
        name="fakebin",
        binary="backend",
        batch_output="stdout",
        batch_transport=lambda prompt: PromptTransport(["backend", prompt]),
        parse_stream_line=lambda line, *, bytes_in: None,
    )
    monkeypatch.setattr(shell, "get_active_backend", lambda: fake_backend)
    monkeypatch.setattr(backend_runner, "get_active_backend", lambda: fake_backend)
    monkeypatch.setattr(
        backend_runner.subprocess,
        "Popen",
        _fake_popen_factory(stdout="hello\nworld\n", returncode=0),
    )

    assert shell.claude_invoke("prompt") == (0, "hello\nworld\n")


# ---------- claude_invoke: sink emission ----------


def test_invoke_sink_receives_claude_call_end_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    response = "the response text"
    monkeypatch.setattr(
        backend_runner.subprocess,
        "Popen",
        _fake_popen_factory(stdout=response, returncode=0),
    )

    recorded: list[ClaudeCallEnd] = []
    shell.set_active_sink(recorded.append)

    shell.claude_invoke("the prompt", phase="propose_steps", attempt=3)

    assert len(recorded) == 1
    ev = recorded[0]
    assert isinstance(ev, ClaudeCallEnd)
    assert ev.event == "claude_call_end"
    assert ev.run_id == ""  # populated by the caller's wrapper in steps 3/4/5
    assert ev.phase == "propose_steps"
    assert ev.attempt == 3
    assert ev.rc == 0
    assert ev.duration_ms >= 0
    assert ev.stdout_bytes == len(response.encode("utf-8"))
    # Unparseable (non-JSON) batch output → no terminal envelope → usage stays
    # None (graceful fallback). The positive-capture case is the next test.
    assert ev.tokens_input is None
    assert ev.tokens_output is None
    assert ev.cache_creation_tokens is None
    assert ev.cache_read_tokens is None
    assert ev.request_id is None
    assert ev.cost_usd is None


def test_invoke_sink_captures_usage_from_stream_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A claude stream-json terminal ``result`` envelope populates the
    ``ClaudeCallEnd`` usage/cache fields on the batch path (BACKLOG #74)."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    terminal = (
        '{"type":"result","result":"answer",'
        '"usage":{"input_tokens":100,"output_tokens":20,'
        '"cache_creation_input_tokens":30,"cache_read_input_tokens":40},'
        '"total_cost_usd":0.01}\n'
    )
    monkeypatch.setattr(
        backend_runner.subprocess,
        "Popen",
        _fake_popen_factory(stdout=terminal, returncode=0),
    )

    recorded: list[ClaudeCallEnd] = []
    shell.set_active_sink(recorded.append)

    rc, out = shell.claude_invoke("prompt")

    assert (rc, out) == (0, "answer")
    assert len(recorded) == 1
    ev = recorded[0]
    assert ev.tokens_input == 100
    assert ev.tokens_output == 20
    assert ev.cache_creation_tokens == 30
    assert ev.cache_read_tokens == 40
    assert ev.cost_usd == 0.01


def test_invoke_sink_unset_by_default_does_not_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    monkeypatch.setattr(
        backend_runner.subprocess,
        "Popen",
        _fake_popen_factory(stdout="x", returncode=0),
    )

    assert shell.get_active_sink() is None
    rc, out = shell.claude_invoke("y")
    assert (rc, out) == (0, "x")


def test_invoke_sink_exception_does_not_break_caller(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    monkeypatch.setattr(
        backend_runner.subprocess,
        "Popen",
        _fake_popen_factory(stdout="payload", returncode=0),
    )

    def exploding_sink(_event: ClaudeCallEnd) -> None:
        raise RuntimeError("sink kaboom")

    shell.set_active_sink(exploding_sink)

    rc, out = shell.claude_invoke("y")

    assert (rc, out) == (0, "payload")
    err = capsys.readouterr().err
    assert "run-log sink raised" in err
    assert "RuntimeError" in err


def test_structural_call_end_suppresses_sink_exception_detail(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def exploding_sink(_event: ClaudeCallEnd) -> None:
        raise RuntimeError("structural secret")

    shell.set_active_sink(exploding_sink)
    try:
        shell._emit_call_end(
            phase="structural", attempt=1, rc=1, duration_ms=1,
            stdout_bytes=0, prompt_bytes=1, suppress_error_output=True,
        )
    finally:
        shell.set_active_sink(None)

    assert capsys.readouterr().err == ""


def test_invoke_duration_uses_monotonic_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``duration_ms`` is sourced from ``time.monotonic()``.

    ``run_streaming_once`` (the same globally-patched stdlib ``time`` module
    ``shell.py`` imports) also calls ``time.monotonic()`` internally — from
    its own start-timestamp and from its pump threads — so the exact number
    of calls crossing ``_run_once_seam``'s started/end bracket isn't
    deterministic under real threads. Prove the source with a distinctive
    per-call delta and assert the recorded duration is a whole multiple of
    it, rather than pinning an exact call count.
    """
    import threading

    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    monkeypatch.setattr(
        backend_runner.subprocess,
        "Popen",
        _fake_popen_factory(stdout="ok", returncode=0),
    )

    lock = threading.Lock()
    state = {"t": 1000.0}
    delta = 100.0

    def fake_monotonic() -> float:
        with lock:
            state["t"] += delta
            return state["t"]

    monkeypatch.setattr(shell.time, "monotonic", fake_monotonic)

    recorded: list[ClaudeCallEnd] = []
    shell.set_active_sink(recorded.append)

    shell.claude_invoke("p")

    assert len(recorded) == 1
    assert recorded[0].duration_ms > 0
    assert recorded[0].duration_ms % int(delta * 1000) == 0


def test_invoke_non_zero_rc_still_emits_event(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Regression guard: don't gate the emit on ``rc == 0``.

    ``runs diff`` needs to see failed calls in the log; gating would
    silently hide them.
    """
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    monkeypatch.setattr(
        backend_runner.subprocess,
        "Popen",
        _fake_popen_factory(stdout="partial", stderr="boom", returncode=1),
    )

    recorded: list[ClaudeCallEnd] = []
    shell.set_active_sink(recorded.append)

    rc, out = shell.claude_invoke("p")

    assert (rc, out) == (1, "partial")
    assert len(recorded) == 1
    assert recorded[0].rc == 1
    assert recorded[0].duration_ms >= 0
    assert "exited with code 1" in capsys.readouterr().err


# ---------- sink lifecycle ----------


def test_set_active_sink_roundtrip_clears_with_none() -> None:
    def fn(_event: ClaudeCallEnd) -> None:
        return None

    assert shell.get_active_sink() is None
    shell.set_active_sink(fn)
    assert shell.get_active_sink() is fn
    shell.set_active_sink(None)
    assert shell.get_active_sink() is None


# ---------- unsinked-call warning (BACKLOG #179) ----------


class TestUnsinkedCallWarning:
    """A claude call with no sink installed is dropped silently, which is why
    run-log gaps are found one incident at a time. It now says so once."""

    @pytest.fixture(autouse=True)
    def _reset_guard(self, monkeypatch: pytest.MonkeyPatch):
        # Process-wide one-shot guard; reset so each test sees a fresh process.
        monkeypatch.setattr(shell, "_warned_no_sink", False)

    def _emit(self, phase: str = "claude_call") -> None:
        shell._emit_call_end(
            phase=phase, attempt=1, rc=0,
            duration_ms=1, stdout_bytes=2, prompt_bytes=3,
        )

    def test_warns_once_for_two_unsinked_calls(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._emit()
        self._emit()
        err = capsys.readouterr().err
        assert err.count("no run-log sink installed") == 1
        # Names the call site and says the rest of the process stays quiet.
        assert "test_shell.py:" in err
        assert "not reported" in err

    def test_names_the_phase(self, capsys: pytest.CaptureFixture[str]) -> None:
        self._emit(phase="purity_scan")
        assert "phase='purity_scan'" in capsys.readouterr().err

    def test_silent_when_a_sink_is_installed(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        recorded: list[ClaudeCallEnd] = []
        shell.set_active_sink(recorded.append)
        self._emit()
        assert len(recorded) == 1
        assert "no run-log sink" not in capsys.readouterr().err

    def test_warning_never_perturbs_the_call(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # The diagnostic is best-effort: a broken caller-lookup must not
        # escape into the claude call's result path.
        def explode() -> str:
            raise RuntimeError("stack walk failed")

        monkeypatch.setattr(shell, "_caller_outside_shell", explode)
        with pytest.raises(RuntimeError):
            # Guard the assumption: the helper really is what raises, so the
            # swallow below is meaningful rather than vacuous.
            explode()
        monkeypatch.setattr(shell, "_warned_no_sink", False)
        monkeypatch.setattr(shell.shutil, "which", lambda _n: "/usr/bin/claude")
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen", _fake_popen_factory(stdout="ok", returncode=0)
        )
        rc, out = shell.claude_invoke("hello")
        assert (rc, out) == (0, "ok")

    def test_caller_lookup_returns_a_non_shell_frame(self) -> None:
        assert shell._caller_outside_shell().startswith("test_shell.py:")


# ---------- claude_invoke: failure recovery ----------


def test_claude_invoke_routes_through_shared_leaf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The batch recovery cascade is delegated to the shared leaf (not
    re-inlined): ``claude_invoke`` calls ``run_with_rate_limit_recovery`` once,
    wired with shell's seams, and returns its ``(rc, stdout)`` verbatim."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")

    calls: list[dict] = []

    def fake_leaf(**kwargs):
        calls.append(kwargs)
        kwargs["classify"]((0, "delegated", ""))
        return (0, "delegated")

    monkeypatch.setattr(shell, "run_with_rate_limit_recovery", fake_leaf)

    rc, out = shell.claude_invoke("hello")

    assert (rc, out) == (0, "delegated")
    assert len(calls) == 1
    seams = calls[0]
    assert callable(seams["run_once"])
    assert callable(seams["classify"])
    assert callable(seams["notify"])
    assert callable(seams["on_nonsuccess"])
    assert seams["prompt_lock"] is shell.RATE_LIMIT_PROMPT_LOCK


def _capture_loop_kwargs(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Swap the recovery leaf for a recorder and return its captured kwargs."""
    calls: list[dict] = []

    def fake_leaf(**kwargs):
        calls.append(kwargs)
        kwargs["classify"]((0, "delegated", ""))
        return (0, "delegated")

    monkeypatch.setattr(shell, "run_with_rate_limit_recovery", fake_leaf)
    return calls


def test_claude_invoke_guard_is_inert_without_a_spawn_cwd(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No spawn cwd → no baseline → ``None``, the loop's always-retry default.

    Out-of-tree callers keep retrying transients exactly as before.
    """
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    calls = _capture_loop_kwargs(monkeypatch)

    shell.claude_invoke("hello")

    assert calls[0]["retry_guard"] is None


def test_claude_invoke_guard_stops_retry_after_a_batch_turn_edits(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The batch path gets the same partial-mutation guard as the streaming one.

    It used to hard-code always-retry on the premise that "batch proposal
    turns never edit the working tree" — false, since the batch argv carries
    ``--permission-mode acceptEdits`` and ``detail``'s turn authors files.
    With an rc=0 empty response now retryable, a turn that wrote its file and
    returned no text is exactly the case that must not be re-driven.
    """
    from plan_tool.backend import spawn_cwd

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    calls = _capture_loop_kwargs(monkeypatch)

    with spawn_cwd(tmp_path):
        shell.claude_invoke("hello")
        guard = calls[0]["retry_guard"]
        assert callable(guard)
        # Clean tree at baseline and still clean: the retry proceeds.
        assert guard(object()).policy is RetryPolicy.RETRY
        # The turn writes a file, as an acceptEdits detail turn can.
        (tmp_path / "authored.md").write_text("body\n", encoding="utf-8")
        decision = guard(object())

    assert decision.policy is RetryPolicy.STOP
    assert "authored.md" in decision.hint


def _multi_popen_factory(responses: list[SimpleNamespace]):
    """Popen stand-in yielding ``responses`` in order.

    Lets a test simulate "first call rate-limited, second call succeeds"
    without having to mock the whole subprocess module per call. Each
    ``SimpleNamespace(stdout=..., stderr=..., returncode=...)`` is split into
    lines the way a real ``Popen`` pipe yields them.
    """
    converted = [
        (
            r.stdout.splitlines(keepends=True),
            r.stderr.splitlines(keepends=True),
            r.returncode,
        )
        for r in responses
    ]
    return _make_popen_factory(converted)


def _popen_response(resp: SimpleNamespace) -> _FakeProc:
    """Convert a ``SimpleNamespace(stdout=..., stderr=..., returncode=...)``
    into a Popen-shaped fake proc, for tests whose fake needs argv-dependent
    routing beyond what ``_multi_popen_factory``'s fixed in-order sequence
    can express."""
    return _FakeProc(
        resp.stdout.splitlines(keepends=True),
        resp.stderr.splitlines(keepends=True),
        resp.returncode,
    )


@pytest.mark.parametrize(
    "policy",
    [
        claude_errors.OnRateLimitPolicy(claude_errors.OnRateLimitAction.WAIT),
        claude_errors.OnRateLimitPolicy(claude_errors.OnRateLimitAction.ASK),
        claude_errors.OnRateLimitPolicy(
            claude_errors.OnRateLimitAction.SWITCH, fallback_backend="codex"
        ),
    ],
)
def test_claude_invoke_plan_quota_bypasses_every_rate_limit_policy_action(
    monkeypatch: pytest.MonkeyPatch,
    policy: claude_errors.OnRateLimitPolicy,
) -> None:
    """A confirmed quota returns after one batch attempt under every policy."""
    from plan_tool.backend import CURSOR_BACKEND, set_active_backend

    set_active_backend(CURSOR_BACKEND)
    monkeypatch.setattr(claude_errors, "_default_on_rate_limit_policy", policy)
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/agent")

    attempts: list[int] = []

    def fake_run_once(_prompt, _transport, **kwargs):
        attempts.append(kwargs["attempt"])
        return 1, _CURSOR_MONTHLY_PLAN_QUOTA, "", None

    def unexpected_recovery_action(*_args, **_kwargs):
        raise AssertionError("plan quota must not start rate-limit recovery")

    class Guard:
        def __call__(self, _outcome):
            raise AssertionError("plan quota must not consult the retry guard")

    monkeypatch.setattr(backend_runner, "run_streaming_once", fake_run_once)
    monkeypatch.setattr(shell, "_select_rate_limit_backend", unexpected_recovery_action)
    monkeypatch.setattr(shell, "_can_prompt_on_rate_limit", unexpected_recovery_action)
    monkeypatch.setattr(shell, "_ask_rate_limit_action", unexpected_recovery_action)
    monkeypatch.setattr(
        shell, "make_partial_mutation_retry_guard", lambda _path: Guard()
    )

    rc, stdout = shell.claude_invoke(
        "prompt",
        _sleep=unexpected_recovery_action,
    )

    assert (rc, stdout) == (1, _CURSOR_MONTHLY_PLAN_QUOTA)
    assert attempts == [1]


def test_claude_invoke_outcome_retains_final_plan_quota_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The rich helper retains the terminal classification without changing tuples."""
    from plan_tool.backend import CURSOR_BACKEND, set_active_backend

    set_active_backend(CURSOR_BACKEND)
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/agent")
    monkeypatch.setattr(
        backend_runner,
        "run_streaming_once",
        lambda *_args, **_kwargs: (1, _CURSOR_MONTHLY_PLAN_QUOTA, "", None),
    )

    outcome = shell.claude_invoke_outcome("prompt")

    assert outcome.rc == 1
    assert outcome.stdout == _CURSOR_MONTHLY_PLAN_QUOTA
    assert outcome.failure is not None
    assert outcome.failure.kind is claude_errors.ClaudeFailureKind.PLAN_QUOTA
    assert shell.claude_invoke("prompt") == (outcome.rc, outcome.stdout)


def test_claude_invoke_records_cursor_plan_quota_pattern_near_miss(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from plan_tool.backend import CURSOR_BACKEND, set_active_backend, spawn_cwd
    from plan_tool.telemetry import read_decisions

    near_miss = (
        "ActionRequiredError — usage limit reached. Switch models or set a "
        "Spend Limit. The monthly cycle ends on 8/24/2026."
    )
    set_active_backend(CURSOR_BACKEND)
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/agent")
    monkeypatch.setattr(
        backend_runner,
        "run_streaming_once",
        lambda *_args, **_kwargs: (1, near_miss, "", None),
    )
    with spawn_cwd(tmp_path):
        assert shell.claude_invoke("prompt", wait_on_rate_limit=False) == (1, near_miss)

    (event,) = read_decisions(tmp_path)
    assert event.kind == "backend-pattern-miss"
    assert event.plan_slug == ""
    assert event.context == {
        "backend": "cursor",
        "classified_as": "rate_limit",
        "markers": [
            "action-required-error",
            "usage-limit",
            "switch-model",
            "spend-limit",
            "monthly-cycle",
        ],
        "excerpt": near_miss,
        "phase": "claude_invoke",
    }


def test_claude_invoke_skips_quota_near_miss_observer_before_retry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from plan_tool.backend import CURSOR_BACKEND, set_active_backend, spawn_cwd
    from plan_tool.telemetry import read_decisions

    near_miss = (
        "ActionRequiredError — usage limit reached. Switch models or set a "
        "Spend Limit before the monthly cycle ends."
    )
    set_active_backend(CURSOR_BACKEND)
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/agent")

    def fake_leaf(**kwargs):
        classification = kwargs["classify"]((1, near_miss, ""))
        kwargs["on_nonsuccess"](
            (1, near_miss, ""), classification.failure, True, True
        )
        return 1, near_miss

    monkeypatch.setattr(shell, "run_with_rate_limit_recovery", fake_leaf)

    with spawn_cwd(tmp_path):
        assert shell.claude_invoke("prompt") == (1, near_miss)

    assert read_decisions(tmp_path) == []


def test_claude_invoke_suppresses_raw_exit_when_recovery_stops(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")

    def fake_leaf(**kwargs):
        classification = kwargs["classify"]((1, "request timed out", "detail"))
        kwargs["on_nonsuccess"](
            (1, "request timed out", "detail"),
            classification.failure,
            False,
            True,
        )
        return 1, "request timed out"

    monkeypatch.setattr(shell, "run_with_rate_limit_recovery", fake_leaf)

    assert shell.claude_invoke("prompt") == (1, "request timed out")
    assert "exited with code 1" not in capsys.readouterr().err


def test_claude_invoke_deduplicates_quota_near_miss_and_generic_canary(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from plan_tool.backend import CURSOR_BACKEND, set_active_backend

    message = (
        "ActionRequiredError — set a Spend Limit before the monthly cycle "
        "ends; wait for the reset."
    )
    set_active_backend(CURSOR_BACKEND)
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/agent")
    monkeypatch.setattr(
        backend_runner,
        "run_streaming_once",
        lambda *_args, **_kwargs: (1, message, "", None),
    )

    assert shell.claude_invoke("prompt", wait_on_rate_limit=False) == (1, message)

    err = capsys.readouterr().err
    assert err.count("possible ") == 1
    assert "possible missed rate-limit" not in err


def test_claude_invoke_waits_then_retries_on_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rate-limit then success: one wait, two subprocess calls, two events."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    responses = [
        SimpleNamespace(
            stdout="You've hit your limit. resets 3am",
            stderr="",
            returncode=1,
        ),
        SimpleNamespace(stdout="recovered output", stderr="", returncode=0),
    ]
    monkeypatch.setattr(
        backend_runner.subprocess, "Popen", _multi_popen_factory(responses)
    )

    sleeps: list[float] = []
    # Make the wait advance the clock so the countdown exits immediately.
    clock_state = {"t": 1000.0}

    def fake_sleep(secs: float) -> None:
        sleeps.append(secs)
        clock_state["t"] += 10_000  # jump well past any reset

    def fake_clock() -> float:
        return clock_state["t"]

    recorded: list[ClaudeCallEnd] = []
    shell.set_active_sink(recorded.append)

    outcome = shell.claude_invoke_outcome(
        "p", _sleep=fake_sleep, _clock=fake_clock, wait_on_rate_limit=True
    )

    assert (outcome.rc, outcome.stdout) == (0, "recovered output")
    assert outcome.failure is None
    assert len(recorded) == 2
    # Each subprocess call gets its own event with the attempt counter
    # bumped — the run log shows the retry as a distinct row.
    assert recorded[0].attempt == 1
    assert recorded[0].rc == 1
    assert recorded[1].attempt == 2
    assert recorded[1].rc == 0
    # Wait happened (at least one sleep call inside wait_until_epoch).
    assert sleeps, "expected wait_until_epoch to call sleep"


def test_claude_invoke_skips_wait_when_flag_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``wait_on_rate_limit=False`` falls straight through on rate limit."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    responses = [
        SimpleNamespace(
            stdout="You've hit your limit",
            stderr="",
            returncode=1,
        ),
        # Should NOT be consumed — the call returns after the first response.
        SimpleNamespace(stdout="should not run", stderr="", returncode=0),
    ]
    monkeypatch.setattr(
        backend_runner.subprocess, "Popen", _multi_popen_factory(responses)
    )

    sleeps: list[float] = []
    rc, out = shell.claude_invoke(
        "p",
        _sleep=lambda s: sleeps.append(s),
        wait_on_rate_limit=False,
    )

    assert rc == 1
    assert "hit your limit" in out
    assert sleeps == []  # no wait when flag is off


def test_claude_invoke_rate_limit_menu_stop_returns_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Interactive save/stop exits with the rate-limited result."""
    from plan_tool.claude_errors import OnRateLimitAction, OnRateLimitAskResult

    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    responses = [
        SimpleNamespace(stdout="You've hit your limit", stderr="", returncode=1),
        SimpleNamespace(stdout="should not run", stderr="", returncode=0),
    ]
    monkeypatch.setattr(backend_runner.subprocess, "Popen", _multi_popen_factory(responses))
    monkeypatch.setattr(shell, "_can_prompt_on_rate_limit", lambda: True)
    monkeypatch.setattr(
        shell,
        "ask_on_rate_limit_action",
        lambda **_kwargs: OnRateLimitAskResult(action=OnRateLimitAction.STOP),
    )
    monkeypatch.setattr(
        claude_errors,
        "_default_on_rate_limit_policy",
        claude_errors.OnRateLimitPolicy(
            action=claude_errors.OnRateLimitAction.ASK
        ),
    )

    sleeps: list[float] = []
    rc, out = shell.claude_invoke(
        "p",
        _sleep=lambda s: sleeps.append(s),
    )

    assert rc == 1
    assert "hit your limit" in out
    assert sleeps == []


def test_claude_invoke_rate_limit_menu_switches_backend_and_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Interactive backend switch retries immediately through the new backend."""
    from plan_tool.backend import get_active_backend
    from plan_tool.claude_errors import OnRateLimitAction, OnRateLimitAskResult

    original_backend = get_active_backend()
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    responses = [
        SimpleNamespace(stdout="You've hit your limit", stderr="", returncode=1),
        SimpleNamespace(stdout="switched output", stderr="", returncode=0),
    ]
    seen_argv: list[list[str]] = []

    def fake_popen(argv, **kwargs):
        seen_argv.append(list(argv))
        return _popen_response(responses.pop(0))

    monkeypatch.setattr(backend_runner.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(shell, "_can_prompt_on_rate_limit", lambda: True)
    monkeypatch.setattr(
        shell,
        "ask_on_rate_limit_action",
        lambda **_kwargs: OnRateLimitAskResult(
            action=OnRateLimitAction.SWITCH,
            switch_backend_name="codex",
        ),
    )
    monkeypatch.setattr(
        claude_errors,
        "_default_on_rate_limit_policy",
        claude_errors.OnRateLimitPolicy(
            action=claude_errors.OnRateLimitAction.ASK
        ),
    )

    sleeps: list[float] = []
    rc, out = shell.claude_invoke(
        "p",
        _sleep=lambda s: sleeps.append(s),
    )

    assert (rc, out) == (0, "switched output")
    assert [argv[0] for argv in seen_argv] == ["claude", "codex"]
    assert get_active_backend() is original_backend
    assert sleeps == []


def test_claude_invoke_switch_policy_switches_backend_without_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A process-wide SWITCH policy consumes ``fallback_backend`` and retries
    on it non-interactively — no menu, no wait, even on a TTY."""
    from plan_tool import claude_errors
    from plan_tool.backend import get_active_backend
    from plan_tool.claude_errors import OnRateLimitAction, OnRateLimitPolicy

    original_backend = get_active_backend()
    monkeypatch.setattr(claude_errors, "_default_on_rate_limit_policy",
                        OnRateLimitPolicy(action=OnRateLimitAction.SWITCH,
                                          fallback_backend="codex"))
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    responses = [
        SimpleNamespace(stdout="You've hit your limit", stderr="", returncode=1),
        SimpleNamespace(stdout="switched output", stderr="", returncode=0),
    ]
    seen_argv: list[list[str]] = []

    def fake_popen(argv, **kwargs):
        seen_argv.append(list(argv))
        return _popen_response(responses.pop(0))

    def _fail_if_prompted(**_kwargs):  # pragma: no cover - must not run
        raise AssertionError("SWITCH policy must not open the interactive menu")

    monkeypatch.setattr(backend_runner.subprocess, "Popen", fake_popen)
    # TTY available, but the auto-switch must bypass the menu entirely.
    monkeypatch.setattr(shell, "_can_prompt_on_rate_limit", lambda: True)
    monkeypatch.setattr(shell, "ask_on_rate_limit_action", _fail_if_prompted)

    sleeps: list[float] = []
    rc, out = shell.claude_invoke("p", _sleep=lambda s: sleeps.append(s))

    assert (rc, out) == (0, "switched output")
    assert [argv[0] for argv in seen_argv] == ["claude", "codex"]
    assert get_active_backend() is original_backend
    assert sleeps == []  # switched, never waited


def test_claude_invoke_switch_policy_synthesizes_model_family_backend(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A model-family-only backend applies its project switch configuration."""
    from plan_tool import claude_errors
    from plan_tool.backend import (
        CLAUDE_BACKEND,
        get_active_backend,
        set_active_backend,
    )
    from plan_tool.claude_errors import OnRateLimitAction, OnRateLimitPolicy

    config_dir = tmp_path / ".plan-tool"
    config_dir.mkdir()
    (config_dir / "backends.json").write_text(
        '{"backends": {"gemini": {"extra_batch_argv": ["--project"]}, '
        '"typo": {"model": "ignored"}}}',
        encoding="utf-8",
    )
    original_backend = get_active_backend()
    seen_argv: list[list[str]] = []
    responses = [
        SimpleNamespace(stdout="You've hit your limit", stderr="", returncode=1),
        SimpleNamespace(stdout="recovered on gemini", stderr="", returncode=0),
    ]
    monkeypatch.setattr(
        claude_errors,
        "_default_on_rate_limit_policy",
        OnRateLimitPolicy(action=OnRateLimitAction.SWITCH, fallback_backend="gemini"),
    )
    monkeypatch.setattr(shell.shutil, "which", lambda _binary: "/usr/bin/tool")
    monkeypatch.setattr(shell, "get_active_spawn_cwd", lambda: tmp_path)
    monkeypatch.setattr(shell, "make_partial_mutation_retry_guard", lambda _cwd: None)

    def fake_popen(argv, **kwargs):
        seen_argv.append(list(argv))
        return _popen_response(responses.pop(0))

    monkeypatch.setattr(backend_runner.subprocess, "Popen", fake_popen)
    set_active_backend(CLAUDE_BACKEND)
    try:
        assert shell.claude_invoke("p") == (0, "recovered on gemini")
        assert [argv[0] for argv in seen_argv] == ["claude", "gemini"]
        assert seen_argv[1] == ["gemini", "--project", "p"]
        err = capsys.readouterr().err
        assert "unknown backend 'typo'" in err
        assert "provisional descriptor" in err
    finally:
        set_active_backend(original_backend)


def test_claude_invoke_switch_policy_degrades_to_wait_when_fallback_bad(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A SWITCH whose fallback backend can't be selected degrades to waiting
    and retrying rather than aborting the run."""
    from plan_tool import claude_errors
    from plan_tool.backend import get_active_backend
    from plan_tool.claude_errors import OnRateLimitAction, OnRateLimitPolicy

    original_backend = get_active_backend()
    monkeypatch.setattr(claude_errors, "_default_on_rate_limit_policy",
                        OnRateLimitPolicy(action=OnRateLimitAction.SWITCH,
                                          fallback_backend="bogus"))
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    responses = [
        SimpleNamespace(stdout="You've hit your limit. resets 3am",
                        stderr="", returncode=1),
        SimpleNamespace(stdout="recovered output", stderr="", returncode=0),
    ]
    monkeypatch.setattr(backend_runner.subprocess, "Popen", _multi_popen_factory(responses))
    monkeypatch.setattr(shell, "_can_prompt_on_rate_limit", lambda: False)

    sleeps: list[float] = []
    clock_state = {"t": 1000.0}

    def fake_sleep(secs: float) -> None:
        sleeps.append(secs)
        clock_state["t"] += 10_000

    rc, out = shell.claude_invoke(
        "p", _sleep=fake_sleep, _clock=lambda: clock_state["t"]
    )

    assert (rc, out) == (0, "recovered output")
    assert get_active_backend() is original_backend
    assert sleeps, "expected a fallback wait after the failed switch"


def test_claude_invoke_switch_policy_degrades_when_fallback_binary_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A registered fallback with a missing executable must not spawn."""
    from plan_tool import claude_errors
    from plan_tool.backend import get_active_backend
    from plan_tool.claude_errors import OnRateLimitAction, OnRateLimitPolicy

    original_backend = get_active_backend()
    monkeypatch.setattr(
        claude_errors,
        "_default_on_rate_limit_policy",
        OnRateLimitPolicy(
            action=OnRateLimitAction.SWITCH,
            fallback_backend="codex",
        ),
    )
    monkeypatch.setattr(
        shell.shutil,
        "which",
        lambda name: "/usr/bin/claude" if name == "claude" else None,
    )
    responses = [
        SimpleNamespace(
            stdout="You've hit your limit. resets 3am",
            stderr="",
            returncode=1,
        ),
        SimpleNamespace(stdout="recovered output", stderr="", returncode=0),
    ]
    seen_argv: list[list[str]] = []

    def fake_popen(argv, **kwargs):
        seen_argv.append(list(argv))
        return _popen_response(responses.pop(0))

    monkeypatch.setattr(backend_runner.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(shell, "_can_prompt_on_rate_limit", lambda: False)

    sleeps: list[float] = []
    clock_state = {"t": 1000.0}

    def fake_sleep(secs: float) -> None:
        sleeps.append(secs)
        clock_state["t"] += 10_000

    rc, out = shell.claude_invoke(
        "p",
        _sleep=fake_sleep,
        _clock=lambda: clock_state["t"],
    )

    assert (rc, out) == (0, "recovered output")
    assert [argv[0] for argv in seen_argv] == ["claude", "claude"]
    assert get_active_backend() is original_backend
    assert sleeps, "expected a fallback wait after the missing fallback binary"


def test_claude_invoke_ask_policy_reaches_menu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An ASK policy is now reachable: it opens the interactive menu instead
    of collapsing to STOP (the bug). STOP from the menu ends the call."""
    from plan_tool import claude_errors
    from plan_tool.claude_errors import (
        OnRateLimitAction,
        OnRateLimitAskResult,
        OnRateLimitPolicy,
    )

    monkeypatch.setattr(claude_errors, "_default_on_rate_limit_policy",
                        OnRateLimitPolicy(action=OnRateLimitAction.ASK))
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    responses = [
        SimpleNamespace(stdout="You've hit your limit", stderr="", returncode=1),
        SimpleNamespace(stdout="should not run", stderr="", returncode=0),
    ]
    monkeypatch.setattr(backend_runner.subprocess, "Popen", _multi_popen_factory(responses))
    monkeypatch.setattr(shell, "_can_prompt_on_rate_limit", lambda: True)

    asked = {"n": 0}

    def spy_ask(**_kwargs):
        asked["n"] += 1
        return OnRateLimitAskResult(action=OnRateLimitAction.STOP)

    monkeypatch.setattr(shell, "ask_on_rate_limit_action", spy_ask)

    sleeps: list[float] = []
    rc, out = shell.claude_invoke("p", _sleep=lambda s: sleeps.append(s))

    assert asked["n"] == 1, "ASK policy must reach the interactive menu"
    assert rc == 1
    assert "hit your limit" in out
    assert sleeps == []


def test_claude_invoke_switch_to_active_backend_does_not_hot_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A SWITCH whose fallback names the already-active backend must not
    self-switch or hot-loop: it degrades to a single bounded wait and gives
    up, instead of re-selecting the same backend forever with no backoff."""
    from plan_tool import claude_errors
    from plan_tool.backend import get_active_backend
    from plan_tool.claude_errors import OnRateLimitAction, OnRateLimitPolicy

    original_backend = get_active_backend()
    monkeypatch.setattr(claude_errors, "_default_on_rate_limit_policy",
                        OnRateLimitPolicy(action=OnRateLimitAction.SWITCH,
                                          fallback_backend="claude"))
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")

    runs = {"n": 0}

    # No parseable reset time → the wait uses the near-term fallback epoch, so
    # a single big clock jump completes it in one tick.
    def always_rate_limited(argv, **kwargs):
        runs["n"] += 1
        return _popen_response(
            SimpleNamespace(stdout="You've hit your limit", stderr="", returncode=1)
        )

    selected: list[str] = []

    @contextlib.contextmanager
    def spy_select(
        name: str, *, repo_root, fallback_factory=None, known_override_names=()
    ):  # pragma: no cover - must not run
        selected.append(name)
        yield SimpleNamespace()

    monkeypatch.setattr(backend_runner.subprocess, "Popen", always_rate_limited)
    monkeypatch.setattr(shell, "scoped_select_active_backend", spy_select)
    monkeypatch.setattr(shell, "_can_prompt_on_rate_limit", lambda: False)

    sleeps: list[float] = []
    clock_state = {"t": 1000.0}

    def fake_sleep(secs: float) -> None:
        sleeps.append(secs)
        clock_state["t"] += 1_000_000

    rc, _out = shell.claude_invoke(
        "p", _sleep=fake_sleep, _clock=lambda: clock_state["t"]
    )

    assert rc == 1  # bounded — the call returns rather than hanging
    assert selected == []  # never self-switched to the already-active backend
    assert runs["n"] == 2  # initial + one retry after the single wait
    assert get_active_backend() is original_backend
    assert sleeps, "expected a fallback wait before giving up"


def test_claude_invoke_switch_bounds_when_fallback_also_rate_limited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Switching to a *different* fallback that is itself rate-limited must
    still bound: switch once, then (now on the fallback) degrade to one wait,
    then give up — not re-switch to the same backend forever."""
    from plan_tool import claude_errors
    from plan_tool.backend import get_active_backend
    from plan_tool.claude_errors import OnRateLimitAction, OnRateLimitPolicy

    original_backend = get_active_backend()
    monkeypatch.setattr(claude_errors, "_default_on_rate_limit_policy",
                        OnRateLimitPolicy(action=OnRateLimitAction.SWITCH,
                                          fallback_backend="codex"))
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")

    seen: list[str] = []

    def always_rate_limited(argv, **kwargs):
        seen.append(argv[0])
        return _popen_response(
            SimpleNamespace(stdout="You've hit your limit", stderr="", returncode=1)
        )

    selected: list[str] = []
    real_scoped_select = shell.scoped_select_active_backend

    @contextlib.contextmanager
    def spy_select(
        name: str, *, repo_root, fallback_factory=None, known_override_names=()
    ):
        selected.append(name)
        with real_scoped_select(
            name,
            repo_root=repo_root,
            fallback_factory=fallback_factory,
            known_override_names=known_override_names,
        ) as selection:
            yield selection

    monkeypatch.setattr(backend_runner.subprocess, "Popen", always_rate_limited)
    monkeypatch.setattr(shell, "scoped_select_active_backend", spy_select)
    monkeypatch.setattr(shell, "_can_prompt_on_rate_limit", lambda: False)

    sleeps: list[float] = []
    clock_state = {"t": 1000.0}

    def fake_sleep(secs: float) -> None:
        sleeps.append(secs)
        clock_state["t"] += 1_000_000

    rc, _out = shell.claude_invoke(
        "p", _sleep=fake_sleep, _clock=lambda: clock_state["t"]
    )

    assert rc == 1  # bounded — returns rather than hanging
    assert selected == ["codex"]  # switched exactly once, not repeatedly
    assert seen == ["claude", "codex", "codex"]  # initial, switched, post-wait
    assert get_active_backend() is original_backend
    assert sleeps, "expected one fallback wait after the switch"


def test_claude_invoke_scoped_switch_restores_after_fallback_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A successful switch that still terminates rate-limited restores the
    original active backend before returning."""
    from plan_tool import claude_errors
    from plan_tool.backend import get_active_backend
    from plan_tool.claude_errors import OnRateLimitAction, OnRateLimitPolicy

    original_backend = get_active_backend()
    monkeypatch.setattr(claude_errors, "_default_on_rate_limit_policy",
                        OnRateLimitPolicy(action=OnRateLimitAction.SWITCH,
                                          fallback_backend="codex"))
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")

    responses = [
        SimpleNamespace(stdout="You've hit your limit", stderr="", returncode=1),
        SimpleNamespace(stdout="You've hit your limit", stderr="", returncode=1),
    ]
    seen: list[str] = []

    def fake_popen(argv, **kwargs):
        seen.append(argv[0])
        return _popen_response(responses.pop(0))

    monkeypatch.setattr(backend_runner.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(shell, "_can_prompt_on_rate_limit", lambda: False)
    # The wait now happens in the claude_errors seam, so patch it there.
    monkeypatch.setattr(
        claude_errors,
        "wait_until_epoch",
        lambda *a, **k: SimpleNamespace(action=claude_errors.WaitUntilAction.STOP),
    )

    rc, out = shell.claude_invoke("p")

    assert rc == 1
    assert "hit your limit" in out
    assert seen == ["claude", "codex"]
    assert get_active_backend() is original_backend


def test_claude_invoke_parallel_switches_do_not_leak_between_threads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fallback selected in one overlapping invoke is invisible to a
    sibling invoke running in another thread."""
    import threading

    from plan_tool import claude_errors
    from plan_tool.backend import get_active_backend
    from plan_tool.claude_errors import OnRateLimitAction, OnRateLimitPolicy

    original_backend = get_active_backend()
    monkeypatch.setattr(claude_errors, "_default_on_rate_limit_policy",
                        OnRateLimitPolicy(action=OnRateLimitAction.SWITCH,
                                          fallback_backend="codex"))
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    monkeypatch.setattr(shell, "_can_prompt_on_rate_limit", lambda: False)

    switcher_on_fallback = threading.Event()
    sibling_done = threading.Event()
    seen: list[tuple[str, str]] = []
    seen_lock = threading.Lock()

    def fake_popen(argv, **kwargs):
        prompt = argv[-1]
        with seen_lock:
            seen.append((prompt, argv[0]))
        if prompt == "switcher" and argv[0] == "claude":
            return _popen_response(
                SimpleNamespace(
                    stdout="You've hit your limit", stderr="", returncode=1
                )
            )
        if prompt == "switcher" and argv[0] == "codex":
            switcher_on_fallback.set()
            assert sibling_done.wait(2), "sibling did not run during switch"
            return _popen_response(
                SimpleNamespace(stdout="switcher ok", stderr="", returncode=0)
            )
        if prompt == "sibling":
            return _popen_response(
                SimpleNamespace(stdout="sibling ok", stderr="", returncode=0)
            )
        raise AssertionError(f"unexpected subprocess call: {argv!r}")

    monkeypatch.setattr(backend_runner.subprocess, "Popen", fake_popen)
    results: dict[str, tuple[int, str]] = {}
    errors: list[BaseException] = []

    def run_switcher() -> None:
        try:
            results["switcher"] = shell.claude_invoke("switcher")
        except BaseException as exc:  # pragma: no cover - failure path
            errors.append(exc)

    def run_sibling() -> None:
        try:
            assert switcher_on_fallback.wait(2), "switcher did not switch"
            results["sibling"] = shell.claude_invoke("sibling")
        except BaseException as exc:  # pragma: no cover - failure path
            errors.append(exc)
        finally:
            sibling_done.set()

    threads = [
        threading.Thread(target=run_switcher),
        threading.Thread(target=run_sibling),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3)

    assert not any(thread.is_alive() for thread in threads)
    assert errors == []
    assert results == {
        "switcher": (0, "switcher ok"),
        "sibling": (0, "sibling ok"),
    }
    assert seen == [
        ("switcher", "claude"),
        ("switcher", "codex"),
        ("sibling", "claude"),
    ]
    assert get_active_backend() is original_backend


def test_concurrent_rate_limit_prompts_are_serialized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parallel detail workers share one stdin;
    the shared RATE_LIMIT_PROMPT_LOCK must keep at most one thread inside the
    interactive prompt at a time so termios/input() never collide."""
    import threading
    import time

    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")

    # Per-thread: first subprocess call rate-limits, second succeeds.
    calls: dict[int, int] = {}
    calls_lock = threading.Lock()

    def fake_popen(argv, **kwargs):
        ident = threading.get_ident()
        with calls_lock:
            n = calls.get(ident, 0)
            calls[ident] = n + 1
        if n == 0:
            return _popen_response(
                SimpleNamespace(
                    stdout="You've hit your limit", stderr="", returncode=1
                )
            )
        return _popen_response(SimpleNamespace(stdout="ok", stderr="", returncode=0))

    monkeypatch.setattr(backend_runner.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(shell, "_can_prompt_on_rate_limit", lambda: True)
    # Isolate the prompt: make the post-prompt wait an immediate retry.
    # The wait now happens in the claude_errors seam, so patch it there.
    monkeypatch.setattr(
        claude_errors,
        "wait_until_epoch",
        lambda *a, **k: SimpleNamespace(action=claude_errors.WaitUntilAction.RETRY),
    )

    concurrency = {"cur": 0, "max": 0}
    probe_lock = threading.Lock()

    def fake_ask(_notifier: object) -> object:
        with probe_lock:
            concurrency["cur"] += 1
            concurrency["max"] = max(concurrency["max"], concurrency["cur"])
        time.sleep(0.02)  # widen the window so an unguarded overlap would show
        with probe_lock:
            concurrency["cur"] -= 1
        return shell.OnRateLimitAction.WAIT

    monkeypatch.setattr(shell, "_ask_rate_limit_action", fake_ask)
    monkeypatch.setattr(
        claude_errors,
        "_default_on_rate_limit_policy",
        claude_errors.OnRateLimitPolicy(
            action=claude_errors.OnRateLimitAction.ASK
        ),
    )

    results: dict[int, tuple[int, str]] = {}

    def worker(i: int) -> None:
        results[i] = shell.claude_invoke("p")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Every worker recovered, and no two prompts ran at once.
    assert len(results) == 4
    assert all(rc == 0 and out == "ok" for rc, out in results.values())
    assert concurrency["max"] == 1


def test_claude_invoke_retries_transient_with_exponential_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two transient blips then a success: 2s + 4s backoff, three calls.

    Pins the backoff schedule against the default
    ``transient_base_delay=2.0`` — a regression that changed the
    multiplier (e.g. from 2x to 1.5x) would surface here.
    """
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    responses = [
        SimpleNamespace(
            stdout="request timed out",
            stderr="",
            returncode=1,
        ),
        SimpleNamespace(stdout="ECONNRESET", stderr="", returncode=1),
        SimpleNamespace(stdout="finally ok", stderr="", returncode=0),
    ]
    monkeypatch.setattr(
        backend_runner.subprocess, "Popen", _multi_popen_factory(responses)
    )

    sleeps: list[float] = []
    rc, out = shell.claude_invoke(
        "p",
        _sleep=lambda s: sleeps.append(s),
        max_transient_retries=3,
        transient_base_delay=2.0,
    )

    assert (rc, out) == (0, "finally ok")
    assert sleeps == [2.0, 4.0]  # 2 * 2^0, 2 * 2^1


# ---------- backend_spawn / backend_termination / backend_recovery_wait /
# run_interrupted ----------


class _RecordingRunLogger:
    """Minimal fake matching the subset of ``RunLogWriter`` that
    ``shell.claude_invoke`` calls when a writer is bound via
    ``shell.set_active_run_logger``: ``backend_spawn``,
    ``backend_termination``, ``backend_recovery_wait``, ``run_interrupted``,
    and — since step 7's observer wiring routes every batch call through
    the shared runner — ``claude_stream_event``/``claude_call_progress``/
    ``claude_call_stall_suspected`` too.
    """

    def __init__(self) -> None:
        self.spawns: list[dict] = []
        self.terminations: list[dict] = []
        self.recovery_waits: list[dict] = []
        self.interrupts: list[dict] = []
        self.stream_events: list[dict] = []
        self.progress_events: list[dict] = []
        self.stall_events: list[dict] = []

    def backend_spawn(self, *, phase, attempt, backend, **extra):
        self.spawns.append(
            {"phase": phase, "attempt": attempt, "backend": backend, **extra}
        )

    def backend_termination(
        self, *, phase, attempt, backend, reason, duration_ms, **extra
    ):
        self.terminations.append({
            "phase": phase, "attempt": attempt, "backend": backend,
            "reason": reason, "duration_ms": duration_ms, **extra,
        })

    def backend_recovery_wait(
        self, *, phase, attempt, reason, delay_ms, next_attempt, backend, **extra
    ):
        self.recovery_waits.append({
            "phase": phase, "attempt": attempt, "reason": reason,
            "delay_ms": delay_ms, "next_attempt": next_attempt,
            "backend": backend, **extra,
        })

    def run_interrupted(self, *, phase, attempt, source, signal="SIGINT", **extra):
        self.interrupts.append({
            "phase": phase, "attempt": attempt, "source": source,
            "signal": signal, **extra,
        })

    def claude_stream_event(self, *, phase, attempt, kind, **extra):
        self.stream_events.append(
            {"phase": phase, "attempt": attempt, "kind": kind, **extra}
        )

    def claude_call_progress(self, *, phase, attempt, elapsed_ms, silent_ms, **extra):
        self.progress_events.append({
            "phase": phase, "attempt": attempt, "elapsed_ms": elapsed_ms,
            "silent_ms": silent_ms, **extra,
        })

    def claude_call_stall_suspected(
        self, *, phase, attempt, silent_ms, threshold_ms, **extra
    ):
        self.stall_events.append({
            "phase": phase, "attempt": attempt, "silent_ms": silent_ms,
            "threshold_ms": threshold_ms, **extra,
        })


def test_claude_invoke_emits_backend_recovery_wait_on_rate_limit_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Extends ``test_claude_invoke_waits_then_retries_on_rate_limit``: a
    bound writer sees one ``backend_recovery_wait`` row before the retried
    subprocess call fires."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    responses = [
        SimpleNamespace(
            stdout="You've hit your limit. resets 3am",
            stderr="",
            returncode=1,
        ),
        SimpleNamespace(stdout="recovered output", stderr="", returncode=0),
    ]
    monkeypatch.setattr(backend_runner.subprocess, "Popen", _multi_popen_factory(responses))

    clock_state = {"t": 1000.0}

    def fake_sleep(secs: float) -> None:
        clock_state["t"] += 10_000

    def fake_clock() -> float:
        return clock_state["t"]

    logger = _RecordingRunLogger()
    shell.set_active_run_logger(logger)
    try:
        rc, out = shell.claude_invoke(
            "p", _sleep=fake_sleep, _clock=fake_clock, wait_on_rate_limit=True,
        )
    finally:
        shell.set_active_run_logger(None)

    assert (rc, out) == (0, "recovered output")
    assert len(logger.recovery_waits) == 1
    wait_event = logger.recovery_waits[0]
    assert wait_event["reason"] == "rate_limit"
    assert wait_event["attempt"] == 1
    assert wait_event["next_attempt"] == 2
    assert wait_event["phase"] == "claude_invoke"


def test_claude_invoke_emits_backend_recovery_wait_on_transient_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Extends ``test_claude_invoke_retries_transient_with_exponential_backoff``:
    a bound writer sees one ``backend_recovery_wait`` row per transient retry,
    with the pinned 2s/4s backoff schedule as ``delay_ms``."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    responses = [
        SimpleNamespace(stdout="request timed out", stderr="", returncode=1),
        SimpleNamespace(stdout="ECONNRESET", stderr="", returncode=1),
        SimpleNamespace(stdout="finally ok", stderr="", returncode=0),
    ]
    monkeypatch.setattr(backend_runner.subprocess, "Popen", _multi_popen_factory(responses))

    logger = _RecordingRunLogger()
    shell.set_active_run_logger(logger)
    try:
        rc, out = shell.claude_invoke(
            "p",
            _sleep=lambda s: None,
            max_transient_retries=3,
            transient_base_delay=2.0,
        )
    finally:
        shell.set_active_run_logger(None)

    assert (rc, out) == (0, "finally ok")
    assert [e["reason"] for e in logger.recovery_waits] == ["transient", "transient"]
    assert [e["delay_ms"] for e in logger.recovery_waits] == [2000, 4000]
    assert [e["next_attempt"] for e in logger.recovery_waits] == [2, 3]


def test_claude_invoke_recovery_wait_silent_with_no_bound_writer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no writer bound, the existing rate-limit retry behavior is
    unchanged — a regression guard that the wrapping is a no-op absent a
    writer."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    responses = [
        SimpleNamespace(
            stdout="You've hit your limit. resets 3am", stderr="", returncode=1
        ),
        SimpleNamespace(stdout="recovered output", stderr="", returncode=0),
    ]
    monkeypatch.setattr(backend_runner.subprocess, "Popen", _multi_popen_factory(responses))

    clock_state = {"t": 1000.0}

    def fake_sleep(secs: float) -> None:
        clock_state["t"] += 10_000

    def fake_clock() -> float:
        return clock_state["t"]

    assert shell.get_active_run_logger() is None
    rc, out = shell.claude_invoke(
        "p", _sleep=fake_sleep, _clock=fake_clock, wait_on_rate_limit=True,
    )
    assert (rc, out) == (0, "recovered output")


def test_claude_invoke_keyboard_interrupt_during_rate_limit_wait_emits_run_interrupted_and_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fake ``sleep`` raising ``KeyboardInterrupt`` — the countdown-tick
    seam ``wait_until_epoch`` itself calls — exercises the real swallow-and-
    reraise path. A fake top-level ``wait`` raising directly would never
    reach it."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    responses = [
        SimpleNamespace(
            stdout="You've hit your limit. resets 3am", stderr="", returncode=1
        ),
        SimpleNamespace(stdout="should not run", stderr="", returncode=0),
    ]
    monkeypatch.setattr(backend_runner.subprocess, "Popen", _multi_popen_factory(responses))

    def fake_clock() -> float:
        return 1000.0

    def interrupt_sleep(secs: float) -> None:
        raise KeyboardInterrupt

    logger = _RecordingRunLogger()
    shell.set_active_run_logger(logger)
    try:
        with pytest.raises(KeyboardInterrupt):
            shell.claude_invoke(
                "p",
                _sleep=interrupt_sleep,
                _clock=fake_clock,
                wait_on_rate_limit=True,
            )
    finally:
        shell.set_active_run_logger(None)

    assert len(logger.interrupts) == 1
    assert logger.interrupts[0]["source"] == "recovery_wait"


def test_claude_invoke_keyboard_interrupt_during_transient_sleep_emits_run_interrupted_and_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The transient seam calls the injected ``sleep`` directly with no
    wait-loop in between, so a fake ``sleep`` that raises directly does
    exercise the real path (unlike the rate-limit case above)."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    responses = [
        SimpleNamespace(stdout="request timed out", stderr="", returncode=1),
        SimpleNamespace(stdout="should not run", stderr="", returncode=0),
    ]
    monkeypatch.setattr(backend_runner.subprocess, "Popen", _multi_popen_factory(responses))

    def interrupt_sleep(secs: float) -> None:
        raise KeyboardInterrupt

    logger = _RecordingRunLogger()
    shell.set_active_run_logger(logger)
    try:
        with pytest.raises(KeyboardInterrupt):
            shell.claude_invoke("p", _sleep=interrupt_sleep)
    finally:
        shell.set_active_run_logger(None)

    assert len(logger.interrupts) == 1
    assert logger.interrupts[0]["source"] == "recovery_wait"


def test_claude_invoke_emits_backend_spawn_and_termination_per_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A two-attempt rate-limit-then-success run emits one
    ``backend_spawn``/``backend_termination`` pair per attempt, with matching
    ``attempt`` numbers, and the second termination reads ``"completed"``."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    responses = [
        SimpleNamespace(
            stdout="You've hit your limit. resets 3am", stderr="", returncode=1
        ),
        SimpleNamespace(stdout="recovered output", stderr="", returncode=0),
    ]
    monkeypatch.setattr(backend_runner.subprocess, "Popen", _multi_popen_factory(responses))

    clock_state = {"t": 1000.0}

    def fake_sleep(secs: float) -> None:
        clock_state["t"] += 10_000

    def fake_clock() -> float:
        return clock_state["t"]

    logger = _RecordingRunLogger()
    shell.set_active_run_logger(logger)
    try:
        rc, out = shell.claude_invoke(
            "p", _sleep=fake_sleep, _clock=fake_clock, wait_on_rate_limit=True,
        )
    finally:
        shell.set_active_run_logger(None)

    assert (rc, out) == (0, "recovered output")
    assert [e["attempt"] for e in logger.spawns] == [1, 2]
    assert [e["attempt"] for e in logger.terminations] == [1, 2]
    assert logger.terminations[0]["reason"] == "backend_nonzero"
    assert logger.terminations[1]["reason"] == "completed"


def test_claude_invoke_run_end_reflects_terminal_attempt_reason(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """The caller-level half of the multi-spawn bracket proof: after
    ``claude_invoke`` returns, the bound writer's own ``run_end`` reflects
    the *terminal* attempt's reason, not the first attempt's."""
    from plan_tool.run_log import RunLogWriter

    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    responses = [
        SimpleNamespace(
            stdout="You've hit your limit. resets 3am", stderr="", returncode=1
        ),
        SimpleNamespace(stdout="recovered output", stderr="", returncode=0),
    ]
    monkeypatch.setattr(backend_runner.subprocess, "Popen", _multi_popen_factory(responses))

    clock_state = {"t": 1000.0}

    def fake_sleep(secs: float) -> None:
        clock_state["t"] += 10_000

    def fake_clock() -> float:
        return clock_state["t"]

    writer = RunLogWriter.start(
        repo_root=tmp_path,
        slug="demo",
        command="create",
        argv=["plan-tool", "create"],
    )
    shell.set_active_run_logger(writer)
    try:
        rc, out = shell.claude_invoke(
            "p", _sleep=fake_sleep, _clock=fake_clock, wait_on_rate_limit=True,
        )
    finally:
        shell.set_active_run_logger(None)
    assert (rc, out) == (0, "recovered output")

    writer.run_end(outcome="ok", rc=0)
    lines = writer.log_path.read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in lines if line.strip()]
    end = next(e for e in events if e["event"] == "run_end")
    assert end["termination_reason"] == "completed"


def test_claude_invoke_recovery_wait_next_attempt_correct_after_backend_switch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rate-limit resolved by a successful backend SWITCH never calls
    ``wait`` (the loop bumps its attempt counter internally on that path),
    so the subsequent transient sleep's ``next_attempt`` must still equal
    the attempt number the following retry's ``run_once`` actually
    receives — the direct proof that deriving from ``run_once`` (rather
    than a seam-side counter, which would undercount by one across the
    switch) survives this path."""
    from plan_tool import claude_errors
    from plan_tool.claude_errors import OnRateLimitAction, OnRateLimitPolicy

    monkeypatch.setattr(
        claude_errors,
        "_default_on_rate_limit_policy",
        OnRateLimitPolicy(action=OnRateLimitAction.SWITCH, fallback_backend="codex"),
    )
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    responses = [
        SimpleNamespace(stdout="You've hit your limit", stderr="", returncode=1),
        SimpleNamespace(stdout="request timed out", stderr="", returncode=1),
        SimpleNamespace(stdout="finally ok", stderr="", returncode=0),
    ]
    monkeypatch.setattr(backend_runner.subprocess, "Popen", _multi_popen_factory(responses))

    logger = _RecordingRunLogger()
    shell.set_active_run_logger(logger)
    try:
        rc, out = shell.claude_invoke(
            "p", _sleep=lambda s: None, max_transient_retries=3,
        )
    finally:
        shell.set_active_run_logger(None)

    assert (rc, out) == (0, "finally ok")
    # The SWITCH resolved without ever calling wait/sleep — only the
    # transient retry on the switched-to backend fires a recovery wait.
    assert len(logger.recovery_waits) == 1
    assert logger.recovery_waits[0]["reason"] == "transient"
    assert logger.recovery_waits[0]["next_attempt"] == 3


def test_classify_batch_termination_reason_removed() -> None:
    """Step 7 retires the coarse local classifier: the runner now emits
    ``backend_termination`` itself, sourced from
    ``backend_runner.get_last_termination_reason()``'s precise
    classification, so a second, coarser guess in this module would
    double-emit and drift from it."""
    assert not hasattr(shell, "_classify_batch_termination_reason")


def test_claude_invoke_context_overflow_does_not_retry(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Context-overflow surfaces the hint and returns immediately."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    fake_popen = _fake_popen_factory(stdout="prompt is too long", returncode=1)

    call_count = {"n": 0}

    def counting_popen(*args, **kwargs):
        call_count["n"] += 1
        return fake_popen(*args, **kwargs)

    monkeypatch.setattr(backend_runner.subprocess, "Popen", counting_popen)

    rc, out = shell.claude_invoke("p", _sleep=lambda s: None)

    assert rc == 1
    assert call_count["n"] == 1
    err = capsys.readouterr().err
    assert "split a large seed" in err


def test_claude_invoke_transient_gives_up_after_max_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When transient keeps failing, return after the configured budget.

    Default budget is 3 attempts (initial + 2 retries). Pins this so
    the loop can't accidentally become infinite.
    """
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    responses = [
        SimpleNamespace(stdout="timeout", stderr="", returncode=1)
        for _ in range(5)
    ]
    monkeypatch.setattr(
        backend_runner.subprocess, "Popen", _multi_popen_factory(responses)
    )

    recorded: list[ClaudeCallEnd] = []
    shell.set_active_sink(recorded.append)

    rc, _ = shell.claude_invoke(
        "p",
        _sleep=lambda s: None,
        max_transient_retries=3,
    )

    assert rc == 1
    # 3 subprocess calls (initial + 2 retries within budget).
    assert len(recorded) == 3


def test_claude_invoke_unknown_nonzero_no_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Generic non-zero with no recognizable pattern: one call, then bail."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    monkeypatch.setattr(
        backend_runner.subprocess,
        "Popen",
        _fake_popen_factory(stdout="some unrecognized failure", returncode=2),
    )

    recorded: list[ClaudeCallEnd] = []
    shell.set_active_sink(recorded.append)

    rc, _ = shell.claude_invoke("p", _sleep=lambda s: None)
    assert rc == 2
    assert len(recorded) == 1


def test_claude_invoke_honors_module_default_when_kwarg_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``wait_on_rate_limit=None`` (the default) reads the module flag.

    Pins the wiring between the CLI flag and the invoker — without
    this, ``--no-wait-on-rate-limit`` on the top-level parser would
    have no effect.
    """
    from plan_tool import claude_errors

    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    responses = [
        SimpleNamespace(
            stdout="You've hit your limit",
            stderr="",
            returncode=1,
        ),
    ]
    monkeypatch.setattr(
        backend_runner.subprocess, "Popen", _multi_popen_factory(responses)
    )

    original = claude_errors.get_default_wait_on_rate_limit()
    try:
        claude_errors.set_default_wait_on_rate_limit(False)
        sleeps: list[float] = []
        rc, _ = shell.claude_invoke(
            "p", _sleep=lambda s: sleeps.append(s)
        )
        assert rc == 1
        assert sleeps == []  # module flag off → no wait, no retry
    finally:
        claude_errors.set_default_wait_on_rate_limit(original)


# ---------- style routing ----------


def _jump_sleep(clock_state: dict) -> Callable[[float], None]:
    """A ``_sleep`` that advances the shared clock past any reset so
    ``wait_until_epoch`` exits on its next tick."""

    def fake_sleep(_secs: float) -> None:
        clock_state["t"] += 10_000

    return fake_sleep


class TestShellStyleOutput:
    """Pin ``claude_invoke`` / ``_emit_call_end`` diagnostics to
    ``style.tool()`` / ``style.warn()``: plain-mode bytes are unchanged and
    forced color paints only the prefix word."""

    def test_missing_exe_warn_plain(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(shell.shutil, "which", lambda _name: None)
        shell.claude_invoke("p")
        err = capsys.readouterr().err
        assert err == "warning: `claude` executable not found on PATH\n"
        assert "not found on PATH" in err

    def test_missing_codex_exe_warn_names_binary(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.backend import CODEX_BACKEND, set_active_backend

        set_active_backend(CODEX_BACKEND)
        monkeypatch.setattr(shell.shutil, "which", lambda _name: None)

        assert shell.claude_invoke("p")[0] == shell.EXEC_NOT_FOUND_EXIT

        err = capsys.readouterr().err
        assert err == "warning: `codex` executable not found on PATH\n"

    def test_nonzero_rc_warn_plain(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
        monkeypatch.setattr(
            backend_runner.subprocess,
            "Popen",
            _fake_popen_factory(
                stdout="some unrecognized failure", stderr="boom", returncode=2
            ),
        )
        shell.claude_invoke("p", _sleep=lambda s: None)
        err = capsys.readouterr().err
        assert err.startswith("warning: claude exited with code 2; stderr:\nboom\n")

    def test_rate_limit_hint_tool_plain(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
        responses = [
            SimpleNamespace(
                stdout="You've hit your limit. resets 3am", stderr="", returncode=1
            ),
            SimpleNamespace(stdout="recovered", stderr="", returncode=0),
        ]
        monkeypatch.setattr(backend_runner.subprocess, "Popen", _multi_popen_factory(responses))
        clock_state = {"t": 1000.0}
        shell.claude_invoke(
            "p",
            _sleep=_jump_sleep(clock_state),
            _clock=lambda: clock_state["t"],
            wait_on_rate_limit=True,
        )
        lines = capsys.readouterr().err.splitlines()
        hint = next(l for l in lines if l.startswith("plan-tool: claude rate limit"))
        assert "reset at" in hint

    def test_no_reset_fallback_tool_plain(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
        responses = [
            SimpleNamespace(stdout="rate limit reached", stderr="", returncode=1),
            SimpleNamespace(stdout="recovered", stderr="", returncode=0),
        ]
        monkeypatch.setattr(backend_runner.subprocess, "Popen", _multi_popen_factory(responses))
        clock_state = {"t": 1000.0}
        shell.claude_invoke(
            "p",
            _sleep=_jump_sleep(clock_state),
            _clock=lambda: clock_state["t"],
            wait_on_rate_limit=True,
        )
        err = capsys.readouterr().err
        assert (
            f"plan-tool: no reset time in claude output; "
            f"waiting {shell.DEFAULT_RATE_LIMIT_FALLBACK_SECONDS}s as fallback\n"
        ) in err

    def test_transient_retry_tool_plain(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
        responses = [
            SimpleNamespace(stdout="request timed out", stderr="", returncode=1),
            SimpleNamespace(stdout="finally ok", stderr="", returncode=0),
        ]
        monkeypatch.setattr(backend_runner.subprocess, "Popen", _multi_popen_factory(responses))
        shell.claude_invoke(
            "p",
            _sleep=lambda s: None,
            max_transient_retries=3,
            transient_base_delay=2.0,
        )
        err = capsys.readouterr().err
        assert (
            "plan-tool: transient failure (network or temporary 429); "
            "retry 1/2 in 2s\n"
        ) in err

    def test_terminal_failure_tool_plain(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
        monkeypatch.setattr(
            backend_runner.subprocess,
            "Popen",
            _fake_popen_factory(stdout="some unrecognized failure", returncode=2),
        )
        rc, out = shell.claude_invoke("p", _sleep=lambda s: None)
        assert (rc, out) == (2, "some unrecognized failure")
        err = capsys.readouterr().err
        assert "plan-tool: claude exited with code 2\n" in err

    def test_session_limit_banner_waits_and_retries(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Regression: the session-limit banner must wait+retry, not return."""
        monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
        responses = [
            SimpleNamespace(
                stdout="You've hit your session limit · resets 3am",
                stderr="",
                returncode=1,
            ),
            SimpleNamespace(stdout="recovered", stderr="", returncode=0),
        ]
        monkeypatch.setattr(backend_runner.subprocess, "Popen", _multi_popen_factory(responses))
        clock_state = {"t": 1000.0}
        rc, out = shell.claude_invoke(
            "p",
            _sleep=_jump_sleep(clock_state),
            _clock=lambda: clock_state["t"],
            wait_on_rate_limit=True,
        )
        assert (rc, out) == (0, "recovered")
        lines = capsys.readouterr().err.splitlines()
        assert any(l.startswith("plan-tool: claude rate limit") for l in lines)

    def test_missed_limit_canary_on_unknown_nonzero(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """An UNKNOWN_NONZERO that smells like a quota banner is flagged."""
        monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
        monkeypatch.setattr(
            backend_runner.subprocess,
            "Popen",
            _fake_popen_factory(
                stdout="weird new phrasing: you are over your limit", returncode=1
            ),
        )
        shell.claude_invoke("p", _sleep=lambda s: None)
        err = capsys.readouterr().err
        assert "possible missed rate-limit" in err
        assert "output tail:" in err

    def test_sink_raised_warn_plain(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
        monkeypatch.setattr(
            backend_runner.subprocess,
            "Popen",
            _fake_popen_factory(stdout="payload", returncode=0),
        )

        def exploding_sink(_event: ClaudeCallEnd) -> None:
            raise ValueError("boom")

        shell.set_active_sink(exploding_sink)
        shell.claude_invoke("p")
        err = capsys.readouterr().err
        assert err == (
            "warning: run-log sink raised ValueError: boom; "
            "claude call result is unaffected\n"
        )

    def test_missing_exe_warn_color_prefix_only(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_FORCE_COLOR", "1")
        monkeypatch.setattr(shell.shutil, "which", lambda _name: None)
        shell.claude_invoke("p")
        out = capsys.readouterr().err
        prefix = style.BOLD_YELLOW + "warning:" + style.RESET + " "
        assert out.startswith(prefix)
        body = out[len(prefix) :]
        assert "\033[" not in body


class _RecordingNotifier:
    """A minimal :class:`progress.SupportsNotice` that records every call.

    Satisfies the structural protocol ``claude_invoke`` duck-types against,
    without pulling a real ``_StderrStepHandle`` (and its heartbeat thread)
    into a shell-level unit test.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def notice(self, message: str, *, kind: str = "retry") -> None:
        self.calls.append((kind, message))


class TestNotifierRouting:
    """When a progress handle is bound, ``claude_invoke`` routes its retry /
    wait advisories *through* it (clearing the heartbeat tick) instead of
    printing straight to stderr and colliding with it.
    """

    def test_transient_retry_routes_through_bound_notifier(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
        responses = [
            SimpleNamespace(stdout="request timed out", stderr="", returncode=1),
            SimpleNamespace(stdout="finally ok", stderr="", returncode=0),
        ]
        monkeypatch.setattr(backend_runner.subprocess, "Popen", _multi_popen_factory(responses))

        rec = _RecordingNotifier()
        token = shell.push_active_notifier(rec)
        try:
            rc, out = shell.claude_invoke(
                "p",
                _sleep=lambda s: None,
                max_transient_retries=3,
                transient_base_delay=2.0,
            )
        finally:
            shell.pop_active_notifier(token)

        assert (rc, out) == (0, "finally ok")
        # The retry advisory went to the notifier, tagged ``retry`` so the
        # done line can annotate the recovery.
        assert rec.calls == [
            ("retry", "transient failure (network or temporary 429); retry 1/2 in 2s")
        ]
        # Nothing leaked to stderr: neither the retry line nor the redundant
        # ``exited with code`` warn (folded into the single notice).
        err = capsys.readouterr().err
        assert "transient failure" not in err
        assert "exited with code" not in err

    def test_terminal_failure_routes_through_bound_notifier(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
        monkeypatch.setattr(
            backend_runner.subprocess,
            "Popen",
            _fake_popen_factory(stdout="some unrecognized failure", returncode=2),
        )

        rec = _RecordingNotifier()
        token = shell.push_active_notifier(rec)
        try:
            rc, out = shell.claude_invoke("p", _sleep=lambda s: None)
        finally:
            shell.pop_active_notifier(token)

        assert (rc, out) == (2, "some unrecognized failure")
        kinds = [k for k, _ in rec.calls]
        # A terminal failure is surfaced (the raw exit + the hint) but as
        # ``info`` — it is not a recovery, so the done line won't claim one.
        assert kinds and "retry" not in kinds
        assert any("exited with code 2" in m for _, m in rec.calls)
        # The collision-prone straight-to-stderr warn is suppressed.
        assert capsys.readouterr().err == ""


# ---------- claude_invoke: total-bytes prompt-budget backstop ----------


def test_backstop_checks_budget_on_real_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With the binary present, the backstop measures the prompt once against
    the path's canonical ``prompt_bytes`` and passes a non-empty surface."""
    from plan_tool.backend import get_active_backend

    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    monkeypatch.setattr(
        backend_runner.subprocess, "Popen", _fake_popen_factory(stdout="ok", returncode=0)
    )

    prompt = "some prompt body"
    expected_bytes = get_active_backend().batch_transport(prompt).prompt_bytes
    real_maybe_warn = shell.maybe_warn_prompt_budget
    calls: list[tuple[int, dict]] = []

    def spy(total_bytes, **kwargs):
        calls.append((total_bytes, kwargs))
        return real_maybe_warn(total_bytes, **kwargs)

    monkeypatch.setattr(shell, "maybe_warn_prompt_budget", spy)

    assert shell.claude_invoke(prompt) == (0, "ok")
    assert len(calls) == 1
    total_bytes, kwargs = calls[0]
    assert total_bytes == expected_bytes
    assert kwargs["surface"]
    assert kwargs["blocks"] == ()
    assert kwargs["context_window"] is None


def test_backstop_records_telemetry_on_real_send(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """One telemetry event with the fixed backstop slug/phase and the returned
    advisory level — recorded under the scoped spawn cwd."""
    from plan_tool.prompt_budget import estimate_prompt_budget
    from plan_tool.backend import get_active_backend, spawn_cwd

    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    monkeypatch.setattr(
        backend_runner.subprocess, "Popen", _fake_popen_factory(stdout="ok", returncode=0)
    )

    prompt = "small"
    expected_level = estimate_prompt_budget(
        get_active_backend().batch_transport(prompt).prompt_bytes
    ).level

    records: list[dict] = []
    monkeypatch.setattr(
        shell, "record_prompt_budget", lambda *a, **k: records.append((a, k))
    )

    with spawn_cwd(tmp_path):
        shell.claude_invoke(prompt)

    assert len(records) == 1
    args, kwargs = records[0]
    assert args[0] == tmp_path  # recorded under the scoped repo, not process cwd
    assert kwargs["plan_slug"] == ""
    assert kwargs["phase"] == "shell-backstop"
    assert kwargs["advisory"] == expected_level


def test_backstop_suppression_skips_warn_and_record(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from plan_tool.backend import spawn_cwd

    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    monkeypatch.setattr(
        backend_runner.subprocess, "Popen", _fake_popen_factory(stdout="ok", returncode=0)
    )
    warned: list[object] = []
    recorded: list[object] = []
    monkeypatch.setattr(
        shell, "maybe_warn_prompt_budget", lambda *a, **k: warned.append(k)
    )
    monkeypatch.setattr(
        shell, "record_prompt_budget", lambda *a, **k: recorded.append(k)
    )

    with spawn_cwd(tmp_path), shell.suppress_prompt_budget_backstop():
        assert shell.claude_invoke("prompt") == (0, "ok")

    assert warned == []
    assert recorded == []


def test_backstop_suppression_active_false_forces_backstop_on(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``active=False`` keeps the backstop as a fallback net — the scoped
    surfaces pass it when their own budget accounting failed."""
    from plan_tool.backend import spawn_cwd
    from plan_tool.prompt_budget import estimate_prompt_budget

    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    monkeypatch.setattr(
        backend_runner.subprocess, "Popen", _fake_popen_factory(stdout="ok", returncode=0)
    )
    warned: list[object] = []
    recorded: list[object] = []
    monkeypatch.setattr(
        shell,
        "maybe_warn_prompt_budget",
        lambda total_bytes, **k: (
            warned.append(k) or estimate_prompt_budget(total_bytes)
        ),
    )
    monkeypatch.setattr(
        shell, "record_prompt_budget", lambda *a, **k: recorded.append(k)
    )

    with spawn_cwd(tmp_path), shell.suppress_prompt_budget_backstop(active=False):
        assert shell.claude_invoke("prompt") == (0, "ok")

    assert len(warned) == 1
    assert [rec["phase"] for rec in recorded] == ["shell-backstop"]


def test_backstop_active_false_forces_on_inside_enclosing_suppression(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The round-2 guarantee: an inner ``active=False`` scope arms the backstop
    even inside an enclosing ``active=True`` (force-on, not a passthrough), and
    the outer scope's suppression is restored on exit."""
    from plan_tool.backend import spawn_cwd
    from plan_tool.prompt_budget import estimate_prompt_budget

    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    monkeypatch.setattr(
        backend_runner.subprocess, "Popen", _fake_popen_factory(stdout="ok", returncode=0)
    )
    warned: list[object] = []
    monkeypatch.setattr(
        shell,
        "maybe_warn_prompt_budget",
        lambda total_bytes, **k: (
            warned.append(k) or estimate_prompt_budget(total_bytes)
        ),
    )

    with spawn_cwd(tmp_path), shell.suppress_prompt_budget_backstop():
        shell.claude_invoke("outer suppressed")  # no warn
        with shell.suppress_prompt_budget_backstop(active=False):
            shell.claude_invoke("inner forced on")  # warns despite outer
        shell.claude_invoke("outer suppressed again")  # outer restored, no warn

    # Only the inner forced-on send warned.
    assert len(warned) == 1


def test_backstop_still_records_without_suppression(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from plan_tool.backend import spawn_cwd
    from plan_tool.prompt_budget import estimate_prompt_budget

    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    monkeypatch.setattr(
        backend_runner.subprocess, "Popen", _fake_popen_factory(stdout="ok", returncode=0)
    )
    warned: list[object] = []
    recorded: list[object] = []
    monkeypatch.setattr(
        shell,
        "maybe_warn_prompt_budget",
        lambda total_bytes, **k: (
            warned.append(k) or estimate_prompt_budget(total_bytes)
        ),
    )
    monkeypatch.setattr(
        shell, "record_prompt_budget", lambda *a, **k: recorded.append(k)
    )

    with spawn_cwd(tmp_path):
        shell.claude_invoke("unsuppressed")

    assert len(warned) == 1
    assert len(recorded) == 1
    assert recorded[0]["phase"] == "shell-backstop"


def test_backstop_runs_again_after_suppression_scope_exits(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from plan_tool.backend import spawn_cwd
    from plan_tool.prompt_budget import estimate_prompt_budget

    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    monkeypatch.setattr(
        backend_runner.subprocess, "Popen", _fake_popen_factory(stdout="ok", returncode=0)
    )
    warned: list[object] = []
    recorded: list[object] = []
    monkeypatch.setattr(
        shell,
        "maybe_warn_prompt_budget",
        lambda total_bytes, **k: (
            warned.append(k) or estimate_prompt_budget(total_bytes)
        ),
    )
    monkeypatch.setattr(
        shell, "record_prompt_budget", lambda *a, **k: recorded.append(k)
    )

    with spawn_cwd(tmp_path):
        with shell.suppress_prompt_budget_backstop():
            shell.claude_invoke("suppressed")
        shell.claude_invoke("unsuppressed")

    assert len(warned) == 1
    assert [rec["phase"] for rec in recorded] == ["shell-backstop"]


def test_backstop_suppression_is_nested_safe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from plan_tool.backend import spawn_cwd
    from plan_tool.prompt_budget import estimate_prompt_budget

    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    monkeypatch.setattr(
        backend_runner.subprocess, "Popen", _fake_popen_factory(stdout="ok", returncode=0)
    )
    warned: list[object] = []
    monkeypatch.setattr(
        shell,
        "maybe_warn_prompt_budget",
        lambda total_bytes, **k: (
            warned.append(k) or estimate_prompt_budget(total_bytes)
        ),
    )

    with spawn_cwd(tmp_path):
        with shell.suppress_prompt_budget_backstop():
            shell.claude_invoke("outer")
            with shell.suppress_prompt_budget_backstop():
                shell.claude_invoke("inner")
            shell.claude_invoke("still suppressed")
        shell.claude_invoke("unsuppressed")

    assert len(warned) == 1


def test_backstop_suppression_is_thread_scoped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import threading

    from plan_tool.backend import spawn_cwd
    from plan_tool.prompt_budget import estimate_prompt_budget

    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    monkeypatch.setattr(
        backend_runner.subprocess, "Popen", _fake_popen_factory(stdout="ok", returncode=0)
    )
    warned: list[object] = []
    monkeypatch.setattr(
        shell,
        "maybe_warn_prompt_budget",
        lambda total_bytes, **k: (
            warned.append(k) or estimate_prompt_budget(total_bytes)
        ),
    )

    with spawn_cwd(tmp_path), shell.suppress_prompt_budget_backstop():
        shell.claude_invoke("main")
        worker = threading.Thread(target=lambda: shell.claude_invoke("worker"))
        worker.start()
        worker.join()

    assert len(warned) == 1


def test_backstop_skips_telemetry_without_spawn_cwd(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No spawn cwd scoped → the backstop still warns but records nothing, so a
    repo-less caller gets no stray `.plan-tool/telemetry/` write (BACKLOG #99
    review finding). The advisory (which writes nothing) still fires."""
    from plan_tool.backend import get_active_spawn_cwd

    assert get_active_spawn_cwd() is None  # no scope entered

    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    monkeypatch.setattr(
        backend_runner.subprocess, "Popen", _fake_popen_factory(stdout="ok", returncode=0)
    )

    warned = {"n": 0}
    real_maybe_warn = shell.maybe_warn_prompt_budget
    monkeypatch.setattr(
        shell,
        "maybe_warn_prompt_budget",
        lambda total_bytes, **k: (
            warned.__setitem__("n", warned["n"] + 1)
            or real_maybe_warn(total_bytes, **k)
        ),
    )
    records: list[dict] = []
    monkeypatch.setattr(
        shell, "record_prompt_budget", lambda *a, **k: records.append(k)
    )

    shell.claude_invoke("small")

    assert warned["n"] == 1  # advisory still evaluated
    assert records == []  # but nothing written to disk


def test_backstop_reuses_backend_prompt_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stdin-carried backend measures the stdin payload, not the argv tail."""
    from plan_tool.backend import PromptTransport

    prompt = "a much longer stdin-carried prompt body than the argv head"
    fake_backend = SimpleNamespace(
        binary="fakebin",
        batch_transport=lambda p: PromptTransport(["fakebin"], stdin_text=p),
    )
    monkeypatch.setattr(shell, "get_active_backend", lambda: fake_backend)
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/fakebin")
    monkeypatch.setattr(
        backend_runner.subprocess, "Popen", _fake_popen_factory(stdout="ok", returncode=0)
    )

    calls: list[int] = []
    real_maybe_warn = shell.maybe_warn_prompt_budget
    monkeypatch.setattr(
        shell,
        "maybe_warn_prompt_budget",
        lambda total_bytes, **k: (
            calls.append(total_bytes) or real_maybe_warn(total_bytes, **k)
        ),
    )

    shell.claude_invoke(prompt)

    assert calls == [len(prompt.encode("utf-8"))]
    assert calls[0] != len("fakebin".encode("utf-8"))


def test_backstop_fires_once_per_call_not_per_retry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A transient blip forces a retry; the backstop still fires once."""
    from plan_tool.backend import spawn_cwd

    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    responses = [
        SimpleNamespace(stdout="request timed out", stderr="", returncode=1),
        SimpleNamespace(stdout="finally ok", stderr="", returncode=0),
    ]
    monkeypatch.setattr(backend_runner.subprocess, "Popen", _multi_popen_factory(responses))

    warn_calls: list[int] = []
    record_calls: list[dict] = []
    real_maybe_warn = shell.maybe_warn_prompt_budget
    monkeypatch.setattr(
        shell,
        "maybe_warn_prompt_budget",
        lambda total_bytes, **k: (
            warn_calls.append(total_bytes) or real_maybe_warn(total_bytes, **k)
        ),
    )
    monkeypatch.setattr(
        shell, "record_prompt_budget", lambda *a, **k: record_calls.append(k)
    )

    with spawn_cwd(tmp_path):
        rc, out = shell.claude_invoke(
            "p", _sleep=lambda s: None, max_transient_retries=3
        )

    assert (rc, out) == (0, "finally ok")
    assert len(warn_calls) == 1
    assert len(record_calls) == 1


def test_backstop_skipped_on_missing_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing is sent on a missing binary, so no warn/record and no event."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: None)

    warned = {"n": 0}
    monkeypatch.setattr(
        shell,
        "maybe_warn_prompt_budget",
        lambda *a, **k: warned.__setitem__("n", warned["n"] + 1),
    )
    recorded_budget = {"n": 0}
    monkeypatch.setattr(
        shell,
        "record_prompt_budget",
        lambda *a, **k: recorded_budget.__setitem__("n", recorded_budget["n"] + 1),
    )

    events: list[ClaudeCallEnd] = []
    shell.set_active_sink(events.append)

    assert shell.claude_invoke("p") == (shell.EXEC_NOT_FOUND_EXIT, "")
    assert warned["n"] == 0
    assert recorded_budget["n"] == 0
    assert events == []


def test_backstop_silent_at_ok_still_records(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """A small (``ok``) prompt writes nothing to stderr but still records
    (under a scoped spawn cwd)."""
    from plan_tool.backend import spawn_cwd

    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    monkeypatch.setattr(
        backend_runner.subprocess, "Popen", _fake_popen_factory(stdout="ok", returncode=0)
    )

    records: list[dict] = []
    monkeypatch.setattr(
        shell, "record_prompt_budget", lambda *a, **k: records.append(k)
    )

    with spawn_cwd(tmp_path):
        shell.claude_invoke("tiny")

    assert capsys.readouterr().err == ""
    assert len(records) == 1
    assert records[0]["advisory"] == "ok"


def test_backstop_warns_on_large_prompt(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A prompt large enough to cross the warn headroom threshold emits a
    ``warning:`` line to stderr."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    monkeypatch.setattr(
        backend_runner.subprocess, "Popen", _fake_popen_factory(stdout="ok", returncode=0)
    )

    # > 420_000 bytes crosses WARN_HEADROOM_RATIO against DEFAULT_CONTEXT_WINDOW.
    shell.claude_invoke("x" * 500_000)

    assert "warning:" in capsys.readouterr().err


def test_backstop_never_breaks_invoke(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A raising advisory is swallowed; the invoke returns normally."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    monkeypatch.setattr(
        backend_runner.subprocess, "Popen", _fake_popen_factory(stdout="ok", returncode=0)
    )

    def boom(*a, **k):
        raise RuntimeError("advisory blew up")

    monkeypatch.setattr(shell, "maybe_warn_prompt_budget", boom)

    assert shell.claude_invoke("p") == (0, "ok")


def test_backstop_does_not_touch_sink(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The backstop adds no sink event — still exactly one per send."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    monkeypatch.setattr(
        backend_runner.subprocess, "Popen", _fake_popen_factory(stdout="ok", returncode=0)
    )

    events: list[ClaudeCallEnd] = []
    shell.set_active_sink(events.append)

    shell.claude_invoke("p")

    assert len(events) == 1


# ---------- diagnostic timeout: scope precedence + retry-then-empty ----------


def test_effective_subprocess_timeout_precedence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scopes win, including an explicit no-timeout scope, then restore."""
    monkeypatch.delenv("PLAN_TOOL_CLAUDE_TIMEOUT", raising=False)
    assert shell._effective_subprocess_timeout() is None
    monkeypatch.setenv("PLAN_TOOL_CLAUDE_TIMEOUT", "50")
    assert shell._effective_subprocess_timeout() == 50.0
    with shell.scoped_claude_timeout(120.0):
        assert shell._effective_subprocess_timeout() == 120.0
        with shell.scoped_claude_timeout(None):
            assert shell._effective_subprocess_timeout() is None
        assert shell._effective_subprocess_timeout() == 120.0
    assert shell._effective_subprocess_timeout() == 50.0
    monkeypatch.setenv("PLAN_TOOL_CLAUDE_TIMEOUT", "not-a-number")
    assert shell._effective_subprocess_timeout() is None


def test_phase_timeout_resolver_precedence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PLAN_TOOL_PURITY_CLAUDE_TIMEOUT", raising=False)
    monkeypatch.delenv("PLAN_TOOL_CLAUDE_TIMEOUT", raising=False)
    assert shell.resolve_claude_timeout(
        900.0, setting="PLAN_TOOL_PURITY_CLAUDE_TIMEOUT"
    ) == 900.0

    monkeypatch.setenv("PLAN_TOOL_CLAUDE_TIMEOUT", "600")
    assert shell.resolve_claude_timeout(
        900.0, setting="PLAN_TOOL_PURITY_CLAUDE_TIMEOUT"
    ) == 600.0

    monkeypatch.setenv("PLAN_TOOL_PURITY_CLAUDE_TIMEOUT", "300")
    assert shell.resolve_claude_timeout(
        900.0, setting="PLAN_TOOL_PURITY_CLAUDE_TIMEOUT"
    ) == 300.0


@pytest.mark.parametrize("value", ["0", "-1", "not-a-number"])
def test_phase_timeout_resolver_disabled_value_masks_legacy(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("PLAN_TOOL_CLAUDE_TIMEOUT", "600")
    monkeypatch.setenv("PLAN_TOOL_PURITY_CLAUDE_TIMEOUT", value)
    assert shell.resolve_claude_timeout(
        900.0, setting="PLAN_TOOL_PURITY_CLAUDE_TIMEOUT"
    ) is None


def test_claude_invoke_enforces_configured_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A backend call that runs past ``scoped_claude_timeout`` is killed by
    the shared runner's monitor thread — the direct replacement for the
    pre-runner-swap ``subprocess.TimeoutExpired`` test. Classified TIMEOUT
    (terminal) and returned without a same-budget retry."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    proc = _NeverSilentProc()
    monkeypatch.setattr(backend_runner.subprocess, "Popen", lambda *a, **kw: proc)
    monkeypatch.setattr(backend_runner, "_PROGRESS_INTERVAL_S", 0.02)
    monkeypatch.setattr(backend_runner, "_KILL_AFTER_SILENCE_S", 10.0)
    monkeypatch.setattr(backend_runner, "_KILL_GRACE_S", 0.02)

    seen_classifications = []
    original_build = shell.build_classification_from_outcome

    def spy_build(outcome):
        classification = original_build(outcome)
        seen_classifications.append(classification)
        return classification

    monkeypatch.setattr(shell, "build_classification_from_outcome", spy_build)

    sleeps: list[float] = []
    with shell.scoped_claude_timeout(0.06):
        rc, out = shell.claude_invoke("p", _sleep=lambda s: sleeps.append(s))

    assert proc.terminate_called
    assert rc != 0
    assert out == ""
    assert sleeps == []  # no same-budget retry
    assert len(seen_classifications) == 1
    assert seen_classifications[0].failure.kind is claude_errors.ClaudeFailureKind.TIMEOUT
    assert (
        backend_runner.get_last_termination_reason()
        is backend_runner.TerminationReason.CONFIGURED_TIMEOUT
    )


def test_claude_invoke_no_configured_timeout_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no ``scoped_claude_timeout``/``PLAN_TOOL_CLAUDE_TIMEOUT`` set,
    ``claude_invoke`` still passes ``enforce_configured_timeout=True`` (it
    always does) but ``configured_timeout_s=None`` — inert, so a call is
    never killed by the elapsed-time check (only the far longer silence
    default could ever fire)."""
    monkeypatch.delenv("PLAN_TOOL_CLAUDE_TIMEOUT", raising=False)
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    monkeypatch.setattr(
        backend_runner.subprocess, "Popen", _fake_popen_factory(stdout="ok", returncode=0)
    )

    rc, out = shell.claude_invoke("p", _sleep=lambda s: None)

    assert (rc, out) == (0, "ok")


# ---------- claude_invoke: shared-runner wiring (batch-authoring-observability
# plan, step 6) ----------


def test_claude_invoke_spawns_via_backend_runner_popen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``claude_invoke`` no longer imports ``subprocess`` itself — the only
    interception point for its spawn is ``backend_runner.subprocess.Popen``
    (the direct proof ``_run_once`` is gone, not just a name check)."""
    assert not hasattr(shell, "subprocess")
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    called = {"n": 0}

    def fake_popen(*args, **kwargs):
        called["n"] += 1
        return _FakeProc(["intercepted"], [], 0)

    monkeypatch.setattr(backend_runner.subprocess, "Popen", fake_popen)

    rc, out = shell.claude_invoke("p")

    assert called["n"] == 1
    assert (rc, out) == (0, "intercepted")


def test_claude_invoke_passes_batch_transport_not_streaming_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``claude_invoke`` selects ``batch_transport``, never
    ``streaming_transport`` — a project override with different
    ``extra_batch_argv``/``extra_streaming_argv`` must still route batch
    calls through the batch selector."""
    from plan_tool.backend import PromptTransport

    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    fake_backend = SimpleNamespace(
        name="fakebin",
        binary="claude",
        batch_transport=lambda p: PromptTransport(["batch-argv", p]),
        streaming_transport=lambda p: PromptTransport(["streaming-argv", p]),
    )
    monkeypatch.setattr(shell, "get_active_backend", lambda: fake_backend)
    seen_argv: list[list[str]] = []
    monkeypatch.setattr(
        backend_runner.subprocess,
        "Popen",
        _make_popen_factory([(["ok"], [], 0)], seen_argv=seen_argv),
    )

    shell.claude_invoke("PROMPT")

    assert seen_argv == [["batch-argv", "PROMPT"]]


def test_claude_invoke_silence_kill_reaps_a_wedged_batch_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A batch child silent past the shared silence threshold is terminated
    and the call returns rather than hanging — even with no configured
    timeout set, proving the safety net is unconditional for every
    ``claude_invoke`` caller."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    proc = _SilentUntilKilledProc()
    monkeypatch.setattr(backend_runner.subprocess, "Popen", lambda *a, **kw: proc)
    monkeypatch.setattr(backend_runner, "_PROGRESS_INTERVAL_S", 0.02)
    monkeypatch.setattr(backend_runner, "_KILL_AFTER_SILENCE_S", 0.10)
    monkeypatch.setattr(backend_runner, "_KILL_GRACE_S", 0.02)

    rc, out = shell.claude_invoke("p", _sleep=lambda s: None)

    assert proc.terminate_called
    assert rc != 0
    assert out == ""
    assert (
        backend_runner.get_last_termination_reason()
        is backend_runner.TerminationReason.SILENCE_TIMEOUT
    )


def test_claude_invoke_keyboard_interrupt_propagates_with_child_killed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ``KeyboardInterrupt`` raised out of the runner's ``proc.wait()``
    propagates out of ``claude_invoke`` unchanged (not converted to a
    return value), with the child already killed and reaped."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    fake = _RaisingWaitProc(KeyboardInterrupt())
    monkeypatch.setattr(backend_runner.subprocess, "Popen", lambda *a, **kw: fake)

    with pytest.raises(KeyboardInterrupt):
        shell.claude_invoke("p", _sleep=lambda s: None)

    assert fake.kill_called
    assert (
        backend_runner.get_last_termination_reason()
        is backend_runner.TerminationReason.OPERATOR_INTERRUPT
    )


def test_claude_invoke_spawn_failure_returns_unknown_nonzero_not_raised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A spawn-time ``OSError`` is converted to a normal nonzero
    ``(rc, stdout)`` pair — not raised — and, driven through the full
    recovery loop, ``classify()`` buckets it ``UNKNOWN_NONZERO`` with no
    retry attempted."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")

    def raising_popen(*a, **kw):
        raise OSError("binary vanished")

    monkeypatch.setattr(backend_runner.subprocess, "Popen", raising_popen)

    seen_classifications = []
    original_build = shell.build_classification_from_outcome

    def spy_build(outcome):
        classification = original_build(outcome)
        seen_classifications.append(classification)
        return classification

    monkeypatch.setattr(shell, "build_classification_from_outcome", spy_build)

    rc, out = shell.claude_invoke("p", _sleep=lambda s: None)

    assert rc != 0
    assert out == ""
    assert len(seen_classifications) == 1
    assert (
        seen_classifications[0].failure.kind
        is claude_errors.ClaudeFailureKind.UNKNOWN_NONZERO
    )
    assert (
        backend_runner.get_last_termination_reason()
        is backend_runner.TerminationReason.SPAWN_FAILURE
    )


def test_claude_invoke_lets_system_exit_from_runner_propagate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ``SystemExit`` escaping ``run_streaming_once`` must propagate, not
    get folded into a synthesized ``(rc, stdout)`` failure pair like an
    ordinary exception — only ``KeyboardInterrupt``/``SystemExit`` mean
    "the process should actually stop"; everything else is a call failure
    the recovery loop can classify and retry."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")

    def raising_run_streaming_once(prompt, transport, **kwargs):
        raise SystemExit(3)

    monkeypatch.setattr(
        backend_runner, "run_streaming_once", raising_run_streaming_once
    )

    with pytest.raises(SystemExit):
        shell.claude_invoke("p", _sleep=lambda s: None)


def test_claude_invoke_redaction_ready_is_now_true(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """At ``-v`` verbosity, a batch call's ``tool_use`` summary line now
    shows a real (redacted-if-needed) summary, never the literal
    ``[OMITTED]`` — step 7 flips ``claude_invoke``'s call site from step 6's
    fail-closed ``redaction_ready=False`` to ``True`` now that
    ``_summarize_tool_input`` does real redact-then-truncate scrubbing."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    stream = (
        '{"type":"assistant","message":{"content":[{"type":"tool_use",'
        '"name":"Bash","input":{"command":"echo not-a-secret"}}]}}\n'
        + claude_result_ndjson("done")
    )
    monkeypatch.setattr(
        backend_runner.subprocess,
        "Popen",
        _fake_popen_factory(stdout=stream, returncode=0),
    )
    monkeypatch.setattr(
        backend_runner,
        "_console_verbosity",
        backend_runner._CONSOLE_VERBOSITY_VERBOSE,
    )

    shell.claude_invoke("p")

    err = capsys.readouterr().err
    assert "echo not-a-secret" in err
    assert "[OMITTED]" not in err


def test_claude_invoke_backend_spawn_and_termination_still_fire_via_new_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``backend_spawn``/``backend_termination`` still fire once per attempt
    for a batch call — now emitted by ``backend_runner.run_streaming_once``
    itself (step 7), sourced from its own precise
    ``get_last_termination_reason()`` classification, not from a bracket in
    this module. The richer field set (``child_pid``/``transport``/etc.) is
    covered by ``tests/test_backend_runner.py``; this test only pins the
    fields ``claude_invoke``'s caller-facing contract cares about."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    monkeypatch.setattr(
        backend_runner.subprocess, "Popen", _fake_popen_factory(stdout="ok", returncode=0)
    )

    logger = _RecordingRunLogger()
    shell.set_active_run_logger(logger)
    try:
        rc, out = shell.claude_invoke("p", phase="my_phase")
    finally:
        shell.set_active_run_logger(None)

    assert (rc, out) == (0, "ok")
    assert len(logger.spawns) == 1
    spawn = logger.spawns[0]
    assert (spawn["phase"], spawn["attempt"], spawn["backend"]) == (
        "my_phase", 1, "claude",
    )
    assert len(logger.terminations) == 1
    assert logger.terminations[0]["reason"] == "completed"


def test_claude_invoke_passes_an_observer_built_from_the_active_run_logger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``claude_invoke`` builds a distinct observer from the bound writer —
    not the raw writer object — and passes it as ``run_logger`` to the
    shared runner, so the object handed to the runner must not itself be
    a ``RunLogWriter`` (or, here, the raw fake standing in for one)."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    seen_run_loggers: list[object] = []

    def fake_run_streaming_once(prompt, transport, **kwargs):
        seen_run_loggers.append(kwargs.get("run_logger"))
        return (0, "ok", "", None)

    monkeypatch.setattr(backend_runner, "run_streaming_once", fake_run_streaming_once)

    logger = _RecordingRunLogger()
    shell.set_active_run_logger(logger)
    try:
        shell.claude_invoke("p")
    finally:
        shell.set_active_run_logger(None)

    assert len(seen_run_loggers) == 1
    observer = seen_run_loggers[0]
    assert observer is not None
    assert observer is not logger


def test_claude_invoke_no_bound_writer_unaffected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no writer bound, ``claude_invoke`` passes ``run_logger=None``
    straight through — a regression guard that this step's observer
    wiring is unchanged from step 6 when nothing is bound."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    seen_run_loggers: list[object] = []

    def fake_run_streaming_once(prompt, transport, **kwargs):
        seen_run_loggers.append(kwargs.get("run_logger"))
        return (0, "ok", "", None)

    monkeypatch.setattr(backend_runner, "run_streaming_once", fake_run_streaming_once)

    assert shell.get_active_run_logger() is None
    rc, out = shell.claude_invoke("p")

    assert (rc, out) == (0, "ok")
    assert seen_run_loggers == [None]


def test_claude_invoke_batch_call_now_emits_stream_progress_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A batch call gets in-flight signal for the first time: a bound
    writer now receives ``claude_stream_event`` for a ``tool_use`` block
    and ``claude_call_progress`` heartbeats — both previously exclusive to
    ``run``'s streaming lane."""
    import time as _time

    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    monkeypatch.setattr(backend_runner, "_PROGRESS_INTERVAL_S", 0.02)
    tool_use_line = (
        '{"type":"assistant","message":{"content":[{"type":"tool_use",'
        '"name":"Bash","input":{"command":"echo hi"}}]}}\n'
    )

    class _SlowCompletingProc:
        def __init__(self) -> None:
            self.stdout = _FakePipe([tool_use_line])
            self.stderr = _FakePipe([])
            self.stdin = None
            self.returncode = 0

        def wait(self) -> int:
            # Long enough, with the shortened heartbeat interval above, for
            # at least one progress tick before this "completes" normally.
            _time.sleep(0.08)
            return self.returncode

        def poll(self):
            return self.returncode

        def terminate(self) -> None:
            pass

        def kill(self) -> None:
            pass

    monkeypatch.setattr(
        backend_runner.subprocess, "Popen", lambda *a, **kw: _SlowCompletingProc()
    )

    logger = _RecordingRunLogger()
    shell.set_active_run_logger(logger)
    try:
        shell.claude_invoke("p")
    finally:
        shell.set_active_run_logger(None)

    assert any(e["kind"] == "tool_use" for e in logger.stream_events)
    assert logger.progress_events


def test_claude_invoke_emits_exactly_one_backend_spawn_and_termination_per_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Proves the step-5/6 bracket around ``_run_once_seam`` was retired,
    not left running alongside the runner's own: a two-attempt run emits
    exactly one ``backend_spawn``/``backend_termination`` pair per attempt,
    not two — the double-emit this step's retirement exists to prevent."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    responses = [
        SimpleNamespace(stdout="request timed out", stderr="", returncode=1),
        SimpleNamespace(stdout="finally ok", stderr="", returncode=0),
    ]
    monkeypatch.setattr(backend_runner.subprocess, "Popen", _multi_popen_factory(responses))

    logger = _RecordingRunLogger()
    shell.set_active_run_logger(logger)
    try:
        rc, out = shell.claude_invoke(
            "p", _sleep=lambda s: None, max_transient_retries=3,
        )
    finally:
        shell.set_active_run_logger(None)

    assert (rc, out) == (0, "finally ok")
    assert len(logger.spawns) == 2
    assert len(logger.terminations) == 2


def test_claude_invoke_keyboard_interrupt_emits_run_interrupted_source_proc_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ``KeyboardInterrupt`` raised out of the runner's own ``proc.wait()``
    — distinct from step 5's rate-limit-wait ``source="recovery_wait"``
    case — emits one ``run_interrupted(source="proc_wait")`` row through
    ``claude_invoke``'s fuller observer, and the exception still
    propagates out of ``claude_invoke`` unchanged."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    fake = _RaisingWaitProc(KeyboardInterrupt())
    monkeypatch.setattr(backend_runner.subprocess, "Popen", lambda *a, **kw: fake)

    logger = _RecordingRunLogger()
    shell.set_active_run_logger(logger)
    try:
        with pytest.raises(KeyboardInterrupt):
            shell.claude_invoke("p", _sleep=lambda s: None)
    finally:
        shell.set_active_run_logger(None)

    assert len(logger.interrupts) == 1
    assert logger.interrupts[0]["source"] == "proc_wait"
    assert fake.kill_called


def test_shell_run_once_and_normalize_batch_stdout_no_longer_exist() -> None:
    assert not hasattr(shell, "_run_once")
    assert not hasattr(shell, "_normalize_batch_stdout")


def test_plan_tool_shell_debug_env_var_has_no_effect() -> None:
    """The removed ``PLAN_TOOL_SHELL_DEBUG`` debug gate leaves no residue."""
    import inspect

    source = inspect.getsource(shell)
    assert "PLAN_TOOL_SHELL_DEBUG" not in source


# --- the context window a streamed result teaches (see plan_tool/context_window.py) -------------------


def _result_line(model_usage: object) -> str:
    return json.dumps({"type": "result", "result": "ok", "usage": {}, "modelUsage": model_usage})


_SONNET_1M = "claude-sonnet-5-5[1m]"
_SONNET = "claude-sonnet-5-5"
_HAIKU = "claude-haiku-4-5"


def test_a_streamed_result_records_the_selected_models_window_not_a_sub_agents(monkeypatch) -> None:
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    usage = {
        "claude-haiku-4-5": {"inputTokens": 100, "contextWindow": 200_000},
        "claude-opus-5-5": {"inputTokens": 90_000, "outputTokens": 3_000, "contextWindow": 1_000_000},
    }
    monkeypatch.setattr(
        backend_runner.subprocess, "Popen",
        _fake_popen_factory(stdout=_result_line(usage) + "\n", returncode=0),
    )
    selected = CLAUDE_BACKEND.__class__(**{**CLAUDE_BACKEND.__dict__, "resolved_model": "claude-haiku-4-5"})

    with scoped_active_backend(selected):
        shell.claude_invoke("hello")

    assert context_window_for("claude", "claude-haiku-4-5") == 200_000


def test_a_streamed_result_with_no_selected_model_remembers_the_smallest_window(monkeypatch) -> None:
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    usage = {
        _HAIKU: {"inputTokens": 100, "contextWindow": 200_000},
        _SONNET_1M: {"inputTokens": 90_000, "contextWindow": 1_000_000},
    }
    monkeypatch.setattr(
        backend_runner.subprocess, "Popen",
        _fake_popen_factory(stdout=_result_line(usage) + "\n", returncode=0),
    )

    shell.claude_invoke("hello")

    assert context_window_for("claude", None) == 200_000


def test_the_selected_model_is_what_the_pump_matches_on(monkeypatch) -> None:
    """The selected model's window is the LARGER one here, so a pump that passed `None` (or any other
    key) to the rule would store the 200K bound instead."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    usage = {
        _HAIKU: {"inputTokens": 100, "contextWindow": 200_000},
        "claude-opus-5-5": {"inputTokens": 90_000, "contextWindow": 1_000_000},
    }
    monkeypatch.setattr(
        backend_runner.subprocess, "Popen",
        _fake_popen_factory(stdout=_result_line(usage) + "\n", returncode=0),
    )
    selected = CLAUDE_BACKEND.__class__(**{**CLAUDE_BACKEND.__dict__, "resolved_model": "claude-opus-5-5"})

    with scoped_active_backend(selected):
        shell.claude_invoke("hello")

    assert context_window_for("claude", "claude-opus-5-5") == 1_000_000


def test_a_later_lone_entry_result_replaces_an_earlier_exact_window(monkeypatch) -> None:
    """The pump forwards the rule's `exact` flag: a window that fell (the default model changed to a
    smaller one that now runs alone) is followed, which `exact=False` always would never do."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    for window in (1_000_000, 200_000):
        stdout = _result_line({_SONNET: {"inputTokens": 5, "contextWindow": window}}) + "\n"
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen", _fake_popen_factory(stdout=stdout, returncode=0)
        )
        shell.claude_invoke("hello")

    assert context_window_for("claude", None) == 200_000


def test_a_helper_model_in_a_later_result_does_not_flip_an_earlier_exact_window(monkeypatch) -> None:
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    single = _result_line({_SONNET_1M: {"inputTokens": 5, "contextWindow": 1_000_000}}) + "\n"
    mixed = _result_line(
        {_SONNET_1M: {"inputTokens": 5, "contextWindow": 1_000_000}, _HAIKU: {"inputTokens": 1, "contextWindow": 200_000}}
    ) + "\n"

    for stdout in (single, mixed):
        monkeypatch.setattr(
            backend_runner.subprocess, "Popen", _fake_popen_factory(stdout=stdout, returncode=0)
        )
        shell.claude_invoke("hello")

    assert context_window_for("claude", None) == 1_000_000


def test_a_failing_window_bookkeeping_cannot_take_the_pump_down(monkeypatch) -> None:
    """Recording a window is advisory bookkeeping: the call still completes and returns its output."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    stdout = _result_line({"claude-sonnet-5-5": {"contextWindow": 1_000_000}}) + "\n"
    monkeypatch.setattr(
        backend_runner.subprocess, "Popen", _fake_popen_factory(stdout=stdout, returncode=0)
    )

    def boom(*_args, **_kwargs):
        raise RuntimeError("registry blew up")

    monkeypatch.setattr(backend_runner, "observe_context_window", boom)
    died: list[threading.ExceptHookArgs] = []
    monkeypatch.setattr(threading, "excepthook", died.append)

    rc, _output = shell.claude_invoke("hello")

    assert rc == 0
    assert died == [], "the stdout pump thread must survive a failing bookkeeping call"


def test_a_streamed_result_teaches_later_estimates_the_models_window(monkeypatch) -> None:
    """The first call of a process uses the default; the window its result reports serves the rest."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    stdout = _result_line({"claude-sonnet-5-5": {"contextWindow": 1_000_000}}) + "\n"
    monkeypatch.setattr(
        backend_runner.subprocess, "Popen", _fake_popen_factory(stdout=stdout, returncode=0)
    )
    assert active_context_window() is None

    shell.claude_invoke("hello")

    assert active_context_window() == 1_000_000


def test_a_learned_window_silences_the_shell_backstop_for_a_prompt_that_fits_it(monkeypatch, capsys) -> None:
    """500 KB reads `warn` against the 200K default (the existing backstop test) and `ok` against 1M."""
    monkeypatch.setattr(shell.shutil, "which", lambda _name: "/usr/bin/claude")
    monkeypatch.setattr(
        backend_runner.subprocess, "Popen", _fake_popen_factory(stdout="ok", returncode=0)
    )
    observe_context_window("claude", None, 1_000_000)

    shell.claude_invoke("x" * 500_000)

    # Not "warning:" alone: the first unsinked call of a process prints its own one-time warning.
    assert "prompt budget" not in capsys.readouterr().err
