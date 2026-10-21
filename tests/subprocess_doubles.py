"""Shared ``subprocess.run`` and ``subprocess.Popen`` double helpers.

Its own module rather than ``conftest`` because ``tests/cli/conftest.py``
shadows the top-level one on the import path, so ``from conftest import …``
resolves to whichever pytest collected first.
"""

from __future__ import annotations

import json
import subprocess
from typing import Callable, Optional


# Captured at import, before any fixture or test patches ``subprocess.run``.
_REAL_SUBPROCESS_RUN = subprocess.run


def delegate_git_to_real_subprocess(fake_run):
    """Wrap a ``subprocess.run`` double so ``git`` argv still reaches real git.

    Both backend callers read git state for the partial-mutation retry guard
    (``plan_tool/git_state.py``) on every invocation. A double installed to
    script *backend* responses also intercepts that read — swallowing a
    scripted response, answering the guard with backend output, or raising on
    a signature mismatch. Doubles that only care about the backend wrap
    themselves in this. A test that wants to control the git read patches
    ``launcher._git_changed_paths_or_none`` instead, which is the seam for it.
    """

    def run(argv, **kwargs):
        if argv and argv[0] == "git":
            return _REAL_SUBPROCESS_RUN(argv, **kwargs)
        return fake_run(argv, **kwargs)

    return run


class _FakePipe:
    """Minimal Popen.stdout / Popen.stderr stand-in.

    Yields lines on iteration so the streaming runner's pump threads can
    drain them. Closes after the last line so the loop terminates
    naturally.
    """

    def __init__(self, lines: list[str]) -> None:
        self._lines = list(lines)

    def __iter__(self):
        return iter(self._lines)


class _FakeStdin:
    """Minimal Popen.stdin stand-in for a stdin-carried prompt.

    ``run_streaming_once`` writes the transport's ``stdin_text`` then closes
    the pipe; this records both so a test can assert on what was sent.
    """

    def __init__(self) -> None:
        self.written = ""
        self.closed = False

    def write(self, text: str) -> None:
        self.written += text

    def close(self) -> None:
        self.closed = True


class _FakeProc:
    """Popen stand-in. Constructed via :func:`_make_popen_factory`."""

    def __init__(
        self, stdout_lines: list[str], stderr_lines: list[str], returncode: int
    ) -> None:
        self.stdout = _FakePipe(stdout_lines)
        self.stderr = _FakePipe(stderr_lines)
        self.returncode = returncode
        self.stdin = None

    def wait(self) -> int:
        return self.returncode

    def __enter__(self) -> "_FakeProc":
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def _make_popen_factory(
    responses: list[tuple[list[str], list[str], int]],
    *,
    seen_argv: Optional[list[list[str]]] = None,
    on_argv: Optional[Callable[[list[str]], None]] = None,
    on_kwargs: Optional[Callable[[dict], None]] = None,
    procs: Optional[list["_FakeProc"]] = None,
):
    """Build a Popen replacement that yields the given responses in order.

    Each response is ``(stdout_lines, stderr_lines, returncode)``. The
    factory raises if more calls are made than responses provided — a
    test that fails this assertion has a real retry-loop bug.

    Real ``git`` argv is delegated to the actual ``Popen`` (captured before the
    monkeypatch): with the retry-guard, any ``shell_invoker``/``claude_invoke``
    under an active spawn cwd runs ``_git_changed_paths`` (a real ``git
    status``) to snapshot its baseline, and that call must not consume a
    canned backend response.

    ``on_argv``/``on_kwargs`` are per-call hooks (argv list, full Popen kwargs
    dict — ``cwd``, ``stdin`` (``PIPE``/``DEVNULL``), etc.); ``seen_argv``/
    ``procs`` accumulate argv lists / constructed procs across every call.
    When the caller passes ``stdin=subprocess.PIPE`` (a stdin-carried prompt),
    the returned proc's ``.stdin`` is a :class:`_FakeStdin` recording what
    ``run_streaming_once`` writes to it.
    """
    real_popen = subprocess.Popen
    it = iter(responses)

    def fake_popen(_argv, **kwargs):
        if _argv and _argv[0] == "git":
            return real_popen(_argv, **kwargs)
        # Contract pin for the backend spawn: production streams NDJSON and so
        # must pass text=True with piped stdout/stderr (backend_runner.py).
        # Asserting it here keeps this fake from silently green-lighting a
        # regression that drops text=True (which would break the stream decode
        # at runtime).
        assert kwargs.get("text") is True, "backend Popen must pass text=True"
        assert "stdout" in kwargs and "stderr" in kwargs
        if seen_argv is not None:
            seen_argv.append(list(_argv))
        if on_argv is not None:
            on_argv(list(_argv))
        if on_kwargs is not None:
            on_kwargs(kwargs)
        try:
            stdout_lines, stderr_lines, rc = next(it)
        except StopIteration:
            raise AssertionError("Popen called more times than expected")
        proc = _FakeProc(stdout_lines, stderr_lines, rc)
        if kwargs.get("stdin") == subprocess.PIPE:
            proc.stdin = _FakeStdin()
        if procs is not None:
            procs.append(proc)
        return proc

    return fake_popen


def claude_result_ndjson(text: str, *, usage: Optional[dict] = None) -> str:
    """One-line claude ``stream-json`` terminal ``result`` envelope carrying
    ``text`` — the shape ``run_streaming_once`` collapses back to
    ``final_text`` alone, so single-response fixtures don't each hand-write
    the JSON envelope."""
    payload = {"type": "result", "result": text, "usage": usage or {}}
    return json.dumps(payload) + "\n"
