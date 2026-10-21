"""Test harness fixtures shared across the plan-tool test suite.

The :func:`_no_real_claude_subprocess` autouse fixture is the
hermeticity gate that catches the regression class we hit twice while
optimizing the suite: a test forgets to override an ``invoker=``
kwarg, the production default falls through to ``shell_invoker`` /
``shell.claude_invoke`` / ``shell_review_invoker``, and the test
silently shells out to the real ``claude`` CLI for tens of seconds
per call. See TESTING.md "Real-claude fallback seams" for the full
catalog.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

import pytest


def _drop_repo_local_git_env() -> None:
    """Unset git's repo-local variables at import, before any session fixture runs git.

    Inherited ``GIT_DIR`` aims a test's git calls at the real repository; see TESTING.md.
    """
    try:
        names = subprocess.run(
            ["git", "rev-parse", "--local-env-vars"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
    except OSError:
        return  # no git binary: no test can reach a repository through git
    # A git that runs but cannot list them raises here: louder than a partial scrub.
    for name in names:
        os.environ.pop(name, None)


_drop_repo_local_git_env()


_CLAUDE_GATE_HINT = (
    "Test attempted to spawn the real `claude` CLI via subprocess. "
    "Override the relevant `invoker=` kwarg, monkey-patch the call "
    "site's `apply_finding` / `shell_*_invoker`, or pass "
    "`extract_lessons=False` to `generate_detail`. See TESTING.md "
    "\"Real-claude fallback seams\" for the seam-by-seam recipe. "
    "If this test genuinely needs to exercise the subprocess plumbing, "
    "mark it `@pytest.mark.allow_real_claude` and use a local "
    "monkeypatch of `subprocess.run` / `subprocess.Popen` at the "
    "module the production code reads from."
)


def _looks_like_backend_binary(args: object) -> bool:
    """Return True when ``args`` invokes any registered backend's binary.

    Accepts both the list-of-args form (``["claude", ...]``) and the
    bare-string form (``"claude -p ..."``). Tolerates absolute paths
    like ``/Users/.../claude`` so the gate fires regardless of how the
    PATH lookup resolved. Driven by
    :func:`plan_tool.backend.registered_binaries` so a backend added in
    a later step (e.g. codex) is auto-blocked without editing this gate.
    """
    if args is None:
        return False
    if isinstance(args, (list, tuple)):
        if not args:
            return False
        first = args[0]
    else:
        first = args
    if not isinstance(first, str):
        return False

    from plan_tool.backend import registered_binaries

    return any(
        first == binary or first.endswith(f"/{binary}")
        for binary in registered_binaries()
    )


@pytest.fixture(autouse=True)
def _no_real_claude_subprocess(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Block any test from spawning the real ``claude`` CLI.

    Tests that legitimately need to drive the subprocess plumbing
    (e.g. ``test_shell.py``, ``test_launcher.py``) override the
    underlying ``subprocess.run`` / ``subprocess.Popen`` at the
    plan_tool module scope. Those local patches take precedence over
    this gate because they replace the same attribute. Tests that need
    the gate fully out of the way can mark themselves
    ``@pytest.mark.allow_real_claude``.
    """
    if request.node.get_closest_marker("allow_real_claude") is not None:
        return

    real_run = subprocess.run
    real_popen = subprocess.Popen

    def guarded_run(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args")
        if _looks_like_backend_binary(cmd):
            raise RuntimeError(_CLAUDE_GATE_HINT)
        return real_run(*args, **kwargs)

    def guarded_popen(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args")
        if _looks_like_backend_binary(cmd):
            raise RuntimeError(_CLAUDE_GATE_HINT)
        return real_popen(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", guarded_run)
    monkeypatch.setattr(subprocess, "Popen", guarded_popen)


@pytest.fixture(autouse=True)
def _no_real_network_fetch(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Block ``plan_tool.fetch`` from making real network calls.

    ``plan-tool create`` fetches reference-doc content by default
    (``fetch_docs=True``), so any create test that reaches body
    synthesis with references would otherwise hit the live network —
    slow, flaky, and dependent on what a given URL serves that day.
    Patching ``urlopen`` to raise routes every fetch into the
    :class:`~plan_tool.fetch.FetchedDoc` ``error`` path, which renders
    an empty grounding block and falls synthesis back to seed-only —
    exactly the offline behavior the feature guarantees.

    Tests that exercise the fetch path supply their own fake (monkeypatch
    ``plan_tool.fetch.urlopen`` to a stub) — a local patch of the same
    attribute takes precedence over this gate. Tests that genuinely need
    the live network mark themselves ``@pytest.mark.allow_real_network``.
    """
    if request.node.get_closest_marker("allow_real_network") is not None:
        return

    from urllib.error import URLError

    def blocked(*args: object, **kwargs: object) -> object:
        raise URLError("network access is blocked in tests")

    monkeypatch.setattr("plan_tool.fetch.urlopen", blocked)


@pytest.fixture(autouse=True)
def _restore_active_backend() -> object:
    """Restore the process-global active backend after every test.

    ``cli.main`` selects a backend via ``set_active_backend(resolve_backend(
    name))``, mutating a module global; a test that drives ``main`` without
    restoring would leak that selection into the next test. Import-time
    manifest discovery makes ``resolve_backend("claude")`` a distinct object
    from the ``CLAUDE_BACKEND`` literal, so an unrestored leak now also
    breaks the ``get_active_backend() is CLAUDE_BACKEND`` identity assertions.
    Snapshot-and-restore keeps suite ordering hermetic.
    """
    from plan_tool.backend import get_active_backend, set_active_backend

    saved = get_active_backend()
    yield
    set_active_backend(saved)


@pytest.fixture(autouse=True)
def _reset_active_notifier() -> object:
    """Clear the process-global in-flight-notifier binding after every test.

    ``progress._StderrStepHandle`` binds itself as the active notifier on
    construction (so a retry inside ``shell.claude_invoke`` can route through
    the live heartbeat line) and unbinds in ``complete``/``fail``. A test
    that constructs a handle but never closes it leaks that binding into the
    next test's thread — which would make a later ``shell.claude_invoke``
    unit test route through a stale fake instead of the ``tool()`` fallback
    it asserts on. Snapshot-and-restore keeps suite ordering hermetic.
    """
    from plan_tool import shell

    saved = shell.get_active_notifier()
    yield
    # Force the binding back to its pre-test value (normally ``None``); a
    # plain ``set`` is what sticks — ``reset`` would just undo this restore.
    shell._active_notifier.set(saved)


@pytest.fixture(autouse=True)
def _isolate_known_roots_cache(
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Redirect ``~/.plan-tool/git-roots.json`` to a per-test temp HOME.

    The persistent candidate-root cache used by
    ``build_plan_tool_context`` resolves under ``Path.home()`` at call
    time. Without isolation, tests that go through the auto-discovery
    path either pick up entries written by previous test runs (false
    positives) or pollute the real cache with tmp_path directories that
    no longer exist after the test ends. Pinning ``HOME`` to a fresh
    temp dir for every test gives each test a clean slate.
    """
    home = tmp_path_factory.getbasetemp() / "homes" / hashlib.sha256(
        request.node.nodeid.encode()
    ).hexdigest()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))


@pytest.fixture(autouse=True)
def _neutralize_ambient_color(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unset every color-gating env var so tests never inherit the shell.

    Two independent consumers decide on color, and both read the ambient
    environment: Python 3.14's ``_colorize.can_colorize()`` (which argparse
    uses to colorize help/usage) reads ``FORCE_COLOR`` / ``NO_COLOR`` /
    ``PYTHON_COLORS``, and :func:`plan_tool.style.color_enabled` reads
    ``PLAN_TOOL_FORCE_COLOR`` / ``NO_COLOR``. Neither requires a TTY.

    Left inherited, the suite has no single green configuration: a developer
    shell exporting ``FORCE_COLOR`` makes argparse colorize, so the plain-text
    help golden and the generated CLI reference both fail — while running under
    ``NO_COLOR=1`` to fix those instead fails the ten ``test_style.py`` cases
    that drive a fake-TTY stream and expect color. Clearing all four makes the
    decision a property of each test (its own stream, or its own explicit
    setenv) rather than of whoever ran pytest.

    A test that *wants* a specific mode sets it itself — see
    ``tests/test_style.py``, which sets ``NO_COLOR`` / ``PLAN_TOOL_FORCE_COLOR``
    per case.
    """
    for var in (
        "FORCE_COLOR",
        "NO_COLOR",
        "PYTHON_COLORS",
        "PLAN_TOOL_FORCE_COLOR",
    ):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture(autouse=True)
def _isolate_context_window_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every test with no observed model window and no ambient Codex home.

    A window a call reports is process state (`backend.observe_context_window`), so one
    test's observation would otherwise change the next test's prompt-budget verdict, and so
    would a parsed Codex file memoized from a path another test reused.
    `CODEX_HOME` would point the Codex lane at the developer's real models cache.
    """
    monkeypatch.setattr("plan_tool.backend._observed_context_windows", {})
    monkeypatch.setattr("plan_tool.context_window._FILE_MEMO", {})
    monkeypatch.delenv("CODEX_HOME", raising=False)
