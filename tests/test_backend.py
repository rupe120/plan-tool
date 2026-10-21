"""Tests for plan_tool.backend.

Direct unit coverage of the :class:`CliBackend` descriptor, the
registry / active-backend accessors, and ``CLAUDE_BACKEND``'s argv
builders + stream-line parser + classification patterns. The argv
assertions are the byte-identity gate that pins the claude command
lines element-for-element after the seam extraction.
"""

from __future__ import annotations

import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest

from plan_tool import backend
from plan_tool.backend import (
    CLAUDE_BACKEND,
    CODEX_BACKEND,
    CURSOR_BACKEND,
    CliBackend,
    ClaudeRunStats,
    PromptTransport,
    build_effective_backend,
    get_active_backend,
    observe_context_window,
    register_backend,
    registered_binaries,
    resolve_backend,
    select_active_backend,
    set_active_backend,
    scoped_active_backend,
    scoped_select_active_backend,
    structural_codex_backend,
    synthesize_backend,
    provisional_backend_warning,
    unknown_backend_override_warning,
)
from plan_tool.claude_errors import ClaudeFailureKind, classify
from plan_tool.context_window import context_window_for
from plan_tool.launcher import run_step
from plan_tool.progress import ProgressReporter, StepHandle

_CODEX_FIXTURES = Path(__file__).parent / "fixtures" / "codex"
_CURSOR_FIXTURES = Path(__file__).parent / "fixtures" / "cursor"


def _parse_cursor_fixture(name: str) -> list:
    """Drive every line of a cursor-agent fixture through the cursor parser."""
    path = _CURSOR_FIXTURES / name
    parsed = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parsed.append(
            CURSOR_BACKEND.parse_stream_line(
                line, bytes_in=len(line.encode("utf-8"))
            )
        )
    return parsed


def _parse_codex_fixture(name: str) -> list:
    """Drive every line of a codex fixture through the codex parser, in order.

    Streaming order matters: ``_codex_parse_stream_line`` accumulates the
    final agent message across lines and resets it on ``thread.started``,
    so the fixtures (which open with ``thread.started``) must be fed whole
    and in sequence — exactly as the launcher pump does.
    """
    path = _CODEX_FIXTURES / name
    parsed = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parsed.append(
            CODEX_BACKEND.parse_stream_line(line, bytes_in=len(line))
        )
    return parsed


@pytest.fixture
def _restore_backend_state():
    """Guarantee the active backend AND the registry are restored.

    Tests that swap the active backend or register a throwaway backend
    run inside this fixture so suite ordering stays hermetic regardless
    of assertion failures — the module-global registry is a process
    singleton other test files' subprocess guard reads from.
    """
    saved_active = get_active_backend()
    saved_registry = dict(backend._REGISTRY)
    yield
    backend._REGISTRY.clear()
    backend._REGISTRY.update(saved_registry)
    set_active_backend(saved_active)


def test_get_active_backend_defaults_to_claude() -> None:
    assert get_active_backend() is CLAUDE_BACKEND
    assert CLAUDE_BACKEND.name == "claude"


def test_backend_diagnostics_share_the_canonical_wording() -> None:
    assert provisional_backend_warning("gemini") == (
        "backend 'gemini' is not a registered integration — using a "
        "provisional descriptor (generic [gemini <prompt>] argv, "
        "claude-shaped stream parser + failure classification). For correct "
        "streaming/classification, add integrations/gemini/backend.json."
    )
    assert unknown_backend_override_warning("typo", ("codex", "claude")) == (
        "unknown backend 'typo' in .plan-tool/backends.json; "
        "known: ['claude', 'codex']"
    )


def test_claude_binary_is_claude() -> None:
    assert CLAUDE_BACKEND.binary == "claude"


def test_claude_batch_argv_byte_identical() -> None:
    # stream-json (not plain -p) so the terminal envelope carries usage/cache
    # tokens for the run-log on the batch authoring/audit path. See BACKLOG #74.
    assert CLAUDE_BACKEND.batch_argv("P") == [
        "claude",
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--permission-mode",
        "acceptEdits",
        "P",
    ]


def test_claude_batch_output_is_json() -> None:
    # Signals shell._normalize_batch_stdout to unwrap the stream-json envelope.
    assert CLAUDE_BACKEND.batch_output == "json"


def test_claude_streaming_argv_byte_identical() -> None:
    assert CLAUDE_BACKEND.streaming_argv("P") == [
        "claude",
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--permission-mode",
        "acceptEdits",
        "P",
    ]


def test_default_prompt_transport_uses_existing_argv_builder() -> None:
    transport = CLAUDE_BACKEND.batch_transport("P")
    assert transport == PromptTransport(CLAUDE_BACKEND.batch_argv("P"))
    assert transport.stdin_text is None
    assert transport.prompt_bytes == 1


def test_prompt_transport_counts_stdin_payload_not_argv_tail() -> None:
    transport = PromptTransport(["backend", "--stdin"], stdin_text="PROMPT")
    assert transport.prompt_bytes == len("PROMPT".encode("utf-8"))


def test_prompt_transport_can_append_flags_to_stdin_prompt() -> None:
    transport = PromptTransport(["backend", "--read-stdin"], stdin_text="P")
    updated = transport.with_args_before_prompt(["--model", "m"])
    assert updated.argv == ["backend", "--read-stdin", "--model", "m"]
    assert updated.stdin_text == "P"
    assert updated.prompt_bytes == 1


def test_registered_binaries_contains_claude() -> None:
    bins = registered_binaries()
    assert "claude" in bins
    assert bins == {"claude", "codex", "agent"}


def test_parse_stream_line_result_envelope_extracts_stats() -> None:
    import json

    line = json.dumps({
        "type": "result",
        "result": "all done",
        "is_error": False,
        "usage": {
            "input_tokens": 11,
            "output_tokens": 22,
            "cache_creation_input_tokens": 3,
            "cache_read_input_tokens": 4,
        },
        "total_cost_usd": 0.5,
    })
    parsed = CLAUDE_BACKEND.parse_stream_line(line, bytes_in=len(line))
    assert parsed is not None
    stats = parsed.stats
    assert isinstance(stats, ClaudeRunStats)
    assert stats.final_text == "all done"
    assert stats.tokens_input == 11
    assert stats.tokens_output == 22
    assert stats.cache_creation_tokens == 3
    assert stats.cache_read_tokens == 4
    # claude reports input EXCLUDING cached tokens; the run log must say so.
    assert stats.input_includes_cached is False
    assert stats.cost_usd == 0.5
    assert stats.is_error is False


def test_parse_stream_line_non_json_returns_none() -> None:
    assert CLAUDE_BACKEND.parse_stream_line("not json\n", bytes_in=8) is None


def test_claude_patterns_match_known_copy() -> None:
    assert CLAUDE_BACKEND.provider_limit_pattern.search("You've hit your limit")
    # Session/usage-qualified banner (the misclassified wording).
    assert CLAUDE_BACKEND.provider_limit_pattern.search("hit your session limit")
    assert CLAUDE_BACKEND.rate_limit_pattern.search("session limit · resets 4:20pm")
    assert CLAUDE_BACKEND.rate_limit_pattern.search("try again at 9pm")
    assert CLAUDE_BACKEND.rate_limit_pattern.search("usage limit reached")
    assert CLAUDE_BACKEND.context_overflow_pattern.search("prompt is too long")
    assert CLAUDE_BACKEND.transient_pattern.search("ECONNRESET")
    assert CLAUDE_BACKEND.transient_pattern.search("socket hang up")
    # "resets" needs a digit — bare prose isn't a rate-limit signal.
    assert not CLAUDE_BACKEND.rate_limit_pattern.search("the loop resets state")


def _make_fake_backend(name: str, binary: str) -> CliBackend:
    """Build a throwaway backend whose argv builders return sentinels."""
    dummy = re.compile(r"(?!x)x")  # matches nothing
    return CliBackend(
        name=name,
        binary=binary,
        batch_argv=lambda prompt: [binary, "BATCH", prompt],
        streaming_argv=lambda prompt: [binary, "STREAM", prompt],
        parse_stream_line=lambda line, *, bytes_in: None,
        rate_limit_pattern=dummy,
        provider_limit_pattern=dummy,
        context_overflow_pattern=dummy,
        transient_pattern=dummy,
    )


def test_set_active_backend_round_trips(_restore_backend_state) -> None:
    fake = _make_fake_backend("fake", "fakebin")
    register_backend(fake)
    set_active_backend(fake)
    assert get_active_backend() is fake
    # Name-based selection also resolves through the registry. Value-equal,
    # not identity: import-time discovery already register-over-replaced the
    # "claude" registry object with the committed manifest's.
    set_active_backend("claude")
    assert get_active_backend() == CLAUDE_BACKEND


def test_set_active_backend_descriptor_is_process_global(
    _restore_backend_state,
) -> None:
    fake = _make_fake_backend("global-fake", "global-fakebin")
    register_backend(fake)

    set_active_backend(fake)

    assert get_active_backend() is fake
    assert get_active_backend() is fake


def test_set_active_backend_name_resolves_registry_globally(
    _restore_backend_state,
) -> None:
    fake = _make_fake_backend("named-fake", "named-fakebin")
    register_backend(fake)

    set_active_backend("named-fake")

    assert get_active_backend() is fake


def test_scoped_active_backend_overrides_global_temporarily(
    _restore_backend_state,
) -> None:
    global_backend = _make_fake_backend("scope-global", "scope-globalbin")
    scoped_backend = _make_fake_backend("scope-local", "scope-localbin")
    set_active_backend(global_backend)

    with scoped_active_backend(scoped_backend):
        assert get_active_backend() is scoped_backend

    assert get_active_backend() is global_backend


def test_scoped_active_backend_restores_on_exception(
    _restore_backend_state,
) -> None:
    global_backend = _make_fake_backend("scope-ex-global", "scope-ex-globalbin")
    scoped_backend = _make_fake_backend("scope-ex-local", "scope-ex-localbin")
    set_active_backend(global_backend)

    with pytest.raises(RuntimeError, match="boom"):
        with scoped_active_backend(scoped_backend):
            assert get_active_backend() is scoped_backend
            raise RuntimeError("boom")

    assert get_active_backend() is global_backend


def test_scoped_active_backend_nests(_restore_backend_state) -> None:
    global_backend = _make_fake_backend("scope-nest-global", "scope-nest-globalbin")
    outer_backend = _make_fake_backend("scope-nest-outer", "scope-nest-outerbin")
    inner_backend = _make_fake_backend("scope-nest-inner", "scope-nest-innerbin")
    set_active_backend(global_backend)

    with scoped_active_backend(outer_backend):
        assert get_active_backend() is outer_backend
        with scoped_active_backend(inner_backend):
            assert get_active_backend() is inner_backend
        assert get_active_backend() is outer_backend

    assert get_active_backend() is global_backend


def test_set_active_backend_inside_scope_updates_global_after_scope(
    _restore_backend_state,
) -> None:
    original_backend = _make_fake_backend("scope-before-global", "before-globalbin")
    scoped_backend = _make_fake_backend("scope-precedence", "scope-precedencebin")
    next_global_backend = _make_fake_backend("scope-after-global", "after-globalbin")
    set_active_backend(original_backend)

    with scoped_active_backend(scoped_backend):
        set_active_backend(next_global_backend)
        assert get_active_backend() is scoped_backend

    assert get_active_backend() is next_global_backend


def test_scoped_active_backend_accepts_registered_name(
    _restore_backend_state,
) -> None:
    global_backend = _make_fake_backend("scope-name-global", "scope-name-globalbin")
    set_active_backend(global_backend)

    with scoped_active_backend("claude"):
        assert get_active_backend() == CLAUDE_BACKEND

    assert get_active_backend() is global_backend


def test_select_active_backend_sets_effective_backend_globally(
    tmp_path: Path, _restore_backend_state
) -> None:
    config_dir = tmp_path / ".plan-tool"
    config_dir.mkdir()
    (config_dir / "backends.json").write_text(
        """
        {
          "backends": {
            "claude": {
              "model": "opus",
              "extra_batch_argv": ["--batch-extra"],
              "extra_streaming_argv": ["--stream-extra"]
            }
          }
        }
        """,
        encoding="utf-8",
    )

    selection = select_active_backend("claude", repo_root=tmp_path)

    assert selection.effective is get_active_backend()
    assert selection.effective.batch_argv("P")[-4:] == [
        "--batch-extra",
        "--model",
        "opus",
        "P",
    ]
    assert selection.effective.streaming_argv("P")[-4:] == [
        "--stream-extra",
        "--model",
        "opus",
        "P",
    ]


def test_select_active_backend_does_not_replace_registry_seed(
    tmp_path: Path, _restore_backend_state
) -> None:
    config_dir = tmp_path / ".plan-tool"
    config_dir.mkdir()
    (config_dir / "backends.json").write_text(
        """
        {
          "backends": {
            "claude": {
              "model": "opus",
              "extra_batch_argv": ["--batch-extra"]
            }
          }
        }
        """,
        encoding="utf-8",
    )
    registered_seed = resolve_backend("claude")

    selection = select_active_backend("claude", repo_root=tmp_path)

    assert selection.selected is registered_seed
    assert resolve_backend("claude") is registered_seed
    assert get_active_backend() is selection.effective
    assert selection.effective is not registered_seed
    assert selection.effective.batch_argv("P")[-4:] == [
        "--batch-extra",
        "--model",
        "opus",
        "P",
    ]


def test_scoped_select_active_backend_applies_project_override_without_global_mutation(
    tmp_path: Path, _restore_backend_state
) -> None:
    config_dir = tmp_path / ".plan-tool"
    config_dir.mkdir()
    (config_dir / "backends.json").write_text(
        """
        {
          "backends": {
            "claude": {
              "model": "sonnet",
              "extra_batch_argv": ["--batch-extra"],
              "extra_streaming_argv": ["--stream-extra"]
            }
          }
        }
        """,
        encoding="utf-8",
    )
    set_active_backend(CODEX_BACKEND)

    with scoped_select_active_backend(
        "claude", repo_root=tmp_path, model="opus"
    ) as selection:
        assert selection.selected == CLAUDE_BACKEND
        assert selection.effective is get_active_backend()
        assert backend._active_backend is CODEX_BACKEND
        assert selection.effective.batch_argv("P")[-4:] == [
            "--batch-extra",
            "--model",
            "opus",
            "P",
        ]
        assert selection.effective.streaming_argv("P")[-4:] == [
            "--stream-extra",
            "--model",
            "opus",
            "P",
        ]

    assert get_active_backend() is CODEX_BACKEND


def test_scoped_select_active_backend_applies_override_for_case_mismatched_fallback(
    tmp_path: Path, _restore_backend_state
) -> None:
    """A fallback name that resolves to a registered backend only via a
    normalized retry (e.g. ``Claude`` -> ``claude``) must still pick up
    that backend's project override -- keyed on the resolved name, not the
    raw selection string."""
    from plan_tool import model_specs

    config_dir = tmp_path / ".plan-tool"
    config_dir.mkdir()
    (config_dir / "backends.json").write_text(
        """
        {
          "backends": {
            "claude": {
              "extra_batch_argv": ["--batch-extra"]
            }
          }
        }
        """,
        encoding="utf-8",
    )
    set_active_backend(CODEX_BACKEND)

    with scoped_select_active_backend(
        "Claude",
        repo_root=tmp_path,
        fallback_factory=model_specs.synthesize_model_family_backend,
    ) as selection:
        assert selection.selected == CLAUDE_BACKEND
        assert selection.effective.batch_argv("P")[-2:] == ["--batch-extra", "P"]


def test_scoped_select_active_backend_reports_unknown_override_names(
    tmp_path: Path, _restore_backend_state
) -> None:
    config_dir = tmp_path / ".plan-tool"
    config_dir.mkdir()
    (config_dir / "backends.json").write_text(
        """
        {
          "backends": {
            "zeta": {"model": "ignored"},
            "claude": {"model": "opus"},
            "alpha": {"model": "ignored"}
          }
        }
        """,
        encoding="utf-8",
    )

    with scoped_select_active_backend("claude", repo_root=tmp_path) as selection:
        assert selection.unknown_override_names == ("alpha", "zeta")


def test_scoped_selection_accepts_config_for_allowed_provisional_backend(
    tmp_path: Path, _restore_backend_state
) -> None:
    config_dir = tmp_path / ".plan-tool"
    config_dir.mkdir()
    (config_dir / "backends.json").write_text(
        '{"backends": {"gemini": {"extra_streaming_argv": ["--project"]}}}',
        encoding="utf-8",
    )

    with scoped_select_active_backend(
        "gemini",
        repo_root=tmp_path,
        fallback_factory=synthesize_backend,
        known_override_names=("gemini",),
    ) as selection:
        assert selection.unknown_override_names == ()
        assert "--project" in selection.effective.streaming_argv("P")


def test_scoped_active_backend_is_thread_isolated(
    _restore_backend_state,
) -> None:
    from threading import Barrier

    left_backend = _make_fake_backend("thread-left", "thread-leftbin")
    right_backend = _make_fake_backend("thread-right", "thread-rightbin")
    global_backend = _make_fake_backend("thread-global", "thread-globalbin")
    set_active_backend(global_backend)
    entered = Barrier(3)
    release = Barrier(3)

    def worker(scoped_backend: CliBackend) -> tuple[CliBackend, CliBackend]:
        with scoped_active_backend(scoped_backend):
            entered.wait()
            inside = get_active_backend()
            release.wait()
        return inside, get_active_backend()

    with ThreadPoolExecutor(max_workers=2) as executor:
        left_future = executor.submit(worker, left_backend)
        right_future = executor.submit(worker, right_backend)
        entered.wait()
        main_during_workers = get_active_backend()
        release.wait()
        left_inside, left_after = left_future.result()
        right_inside, right_after = right_future.result()

    assert main_during_workers is global_backend
    assert left_inside is left_backend
    assert right_inside is right_backend
    assert left_after is global_backend
    assert right_after is global_backend
    assert get_active_backend() is global_backend


def test_active_backend_global_visible_to_worker_thread(
    _restore_backend_state,
) -> None:
    set_active_backend(CODEX_BACKEND)

    with ThreadPoolExecutor(max_workers=1) as executor:
        worker_backend = executor.submit(get_active_backend).result()

    assert worker_backend is CODEX_BACKEND


def test_restore_backend_state_restores_registry_and_active_backend() -> None:
    restore = _restore_backend_state.__wrapped__()
    saved_active = get_active_backend()
    saved_registry = dict(backend._REGISTRY)
    fake = _make_fake_backend("restore-fake", "restore-fakebin")

    next(restore)
    register_backend(fake)
    set_active_backend(fake)
    with pytest.raises(StopIteration):
        next(restore)

    assert backend._REGISTRY == saved_registry
    assert get_active_backend() is saved_active


# ---------------------------------------------------------------------------
# Codex backend (step 3). All cases are fixture-driven — no real codex
# subprocess; tests/conftest.py's guard blocks one via registered_binaries().
# ---------------------------------------------------------------------------


def _first_stats(parsed: list) -> ClaudeRunStats:
    """Return the single terminal-envelope stats from a parsed fixture."""
    with_stats = [p for p in parsed if p is not None and p.stats is not None]
    assert len(with_stats) == 1
    return with_stats[0].stats


def _all_events(parsed: list) -> list[dict]:
    out: list[dict] = []
    for p in parsed:
        if p is not None:
            out.extend(p.events)
    return out


def test_codex_backend_registered() -> None:
    assert "codex" in registered_binaries()
    # Value-equal, not identity: import-time discovery register-over-replaced
    # the registry object with the committed manifest's.
    assert backend._REGISTRY["codex"] == CODEX_BACKEND
    assert CODEX_BACKEND.name == "codex"


def test_codex_binary_is_codex() -> None:
    assert CODEX_BACKEND.binary == "codex"
    assert CODEX_BACKEND.auth_pattern is not None


def test_codex_active_backend_unchanged() -> None:
    # Step 3 only registers codex; the active backend stays claude.
    assert get_active_backend() is CLAUDE_BACKEND


def test_codex_batch_argv_shape() -> None:
    argv = CODEX_BACKEND.batch_argv("P")
    assert argv[:2] == ["codex", "exec"]
    assert "-s" in argv and "workspace-write" in argv
    assert "--skip-git-repo-check" in argv
    assert "--json" in argv  # batch is JSONL, normalized by shell._run_once
    assert argv[-1] == "P"


def test_codex_streaming_argv_uses_json() -> None:
    argv = CODEX_BACKEND.streaming_argv("P")
    assert argv[:2] == ["codex", "exec"]
    assert "--json" in argv
    assert "-s" in argv and "workspace-write" in argv
    assert argv[-1] == "P"


def test_codex_argv_skip_git_repo_check() -> None:
    # The captured contract supplies --skip-git-repo-check unconditionally
    # (plan-tool scratch contexts may lack a .git dir).
    assert "--skip-git-repo-check" in CODEX_BACKEND.batch_argv("P")
    assert "--skip-git-repo-check" in CODEX_BACKEND.streaming_argv("P")


def test_structural_codex_backend_uses_only_the_captured_read_only_argv(
    tmp_path: Path,
) -> None:
    evaluator = structural_codex_backend(tmp_path / "empty")

    assert evaluator.name == "codex-structural-read-only"
    assert evaluator.batch_argv("P") == [
        "codex", "exec", "--json", "-C", str((tmp_path / "empty").resolve()),
        "-s", "read-only", "--skip-git-repo-check", "--ephemeral",
        "--ignore-user-config", "--ignore-rules", "P",
    ]


def test_codex_command_event_maps_to_tool_use() -> None:
    events = _all_events(_parse_codex_fixture("exec-command-execution.jsonl"))
    tool_uses = [e for e in events if e.get("kind") == "tool_use"]
    assert len(tool_uses) == 1
    assert tool_uses[0]["tool_name"] == "command"
    # The fixture's command is benign, so it passes through unredacted —
    # real redaction of codex's native producer (batch-authoring-observability
    # step 10) doesn't touch text that carries no secret shape.
    assert "hello-from-codex" in tool_uses[0]["tool_input_summary"]
    # The matching item.completed maps to a tool_result.
    assert any(e.get("kind") == "tool_result" for e in events)


def test_codex_patch_event_maps_to_tool_use() -> None:
    events = _all_events(_parse_codex_fixture("exec-stream-sample.jsonl"))
    tool_uses = [e for e in events if e.get("kind") == "tool_use"]
    assert len(tool_uses) == 1
    assert tool_uses[0]["tool_name"] == "edit"
    assert tool_uses[0]["tool_input_summary"] == "/scratch/note.txt (add)"


def test_codex_agent_message_maps_to_assistant_text() -> None:
    parsed = _parse_codex_fixture("exec-result-envelope.jsonl")
    assert any("backend probe ok" in c for p in parsed for c in p.text_chunks)
    events = _all_events(parsed)
    assert any(e.get("kind") == "assistant_text" for e in events)


def test_codex_terminal_envelope_extracts_stats() -> None:
    stats = _first_stats(_parse_codex_fixture("exec-result-envelope.jsonl"))
    assert stats.tokens_input == 26844
    assert stats.tokens_output == 7
    assert stats.cache_read_tokens == 24448  # codex's cached_input_tokens
    # codex input INCLUDES cached tokens (cached <= input on every logged event).
    assert stats.input_includes_cached is True
    assert stats.final_text == "backend probe ok"
    assert stats.is_error is False


def test_codex_stats_cost_and_cache_are_none() -> None:
    stats = _first_stats(_parse_codex_fixture("exec-result-envelope.jsonl"))
    assert stats.cost_usd is None
    assert stats.cache_creation_tokens is None


def test_codex_thread_id_surfaces_as_request_id_hint() -> None:
    parsed = _parse_codex_fixture("exec-result-envelope.jsonl")
    hints = [p.request_id_hint for p in parsed if p.request_id_hint is not None]
    assert hints == ["00000000-0000-4000-8000-000000000003"]


def test_codex_non_json_line_returns_none() -> None:
    assert CODEX_BACKEND.parse_stream_line("not json\n", bytes_in=8) is None
    assert CODEX_BACKEND.parse_stream_line("   \n", bytes_in=4) is None


def test_codex_stream_sample_round_trips() -> None:
    parsed = _parse_codex_fixture("exec-stream-sample.jsonl")
    assert all(p is not None for p in parsed)
    with_stats = [p for p in parsed if p.stats is not None]
    assert len(with_stats) == 1  # exactly the terminal envelope


def test_codex_turn_failed_sets_is_error_and_surfaces_message() -> None:
    parsed = _parse_codex_fixture("exec-turn-failed.jsonl")
    stats = _first_stats(parsed)
    assert stats.is_error is True
    # The provider error message reaches the buffer for the classifier.
    buffer = "".join(c for p in parsed for c in p.text_chunks)
    assert "bogus-model-xyz" in buffer


@pytest.fixture
def _codex_active(_restore_backend_state):
    """Activate CODEX_BACKEND for classify cases; teardown restores claude."""
    set_active_backend(CODEX_BACKEND)
    yield


def test_codex_classify_auth_failure(_codex_active) -> None:
    failure = classify(1, "Error: not logged in. Run `codex login`.", "")
    assert failure.kind is ClaudeFailureKind.AUTH
    assert "codex" in failure.hint


def test_codex_classify_captured_auth_failure(_codex_active) -> None:
    parsed = _parse_codex_fixture("exec-auth-failed.jsonl")
    buffer = "".join(c for p in parsed if p is not None for c in p.text_chunks)
    assert "401 Unauthorized" in buffer
    assert classify(1, buffer, "").kind is ClaudeFailureKind.AUTH


def test_codex_classify_rate_limit(_codex_active) -> None:
    failure = classify(1, "usage limit reached; try again at 9pm", "")
    assert failure.kind is ClaudeFailureKind.RATE_LIMIT
    assert failure.hint.startswith("codex rate limit")


def test_codex_classify_transient(_codex_active) -> None:
    assert classify(1, "", "ECONNRESET while contacting provider").kind is (
        ClaudeFailureKind.TRANSIENT
    )


def test_codex_classify_context_overflow(_codex_active) -> None:
    failure = classify(1, "prompt is too long", "")
    assert failure.kind is ClaudeFailureKind.CONTEXT_OVERFLOW
    assert failure.hint.startswith("codex context window")


def test_codex_classify_invalid_request_is_unknown(_codex_active) -> None:
    # The captured invalid-request envelope has no recoverable pattern.
    parsed = _parse_codex_fixture("exec-turn-failed.jsonl")
    buffer = "".join(c for p in parsed for c in p.text_chunks)
    assert classify(1, buffer, "").kind is ClaudeFailureKind.UNKNOWN_NONZERO


def test_claude_has_no_auth_pattern() -> None:
    # claude's backend defines no auth_pattern, so an auth-flavored string
    # under claude stays UNKNOWN_NONZERO.
    assert CLAUDE_BACKEND.auth_pattern is None
    assert classify(1, "not logged in", "").kind is (
        ClaudeFailureKind.UNKNOWN_NONZERO
    )


# ---------------------------------------------------------------------------
# Cursor Agent backend. Fixture-driven — no real agent subprocess.
# ---------------------------------------------------------------------------


def test_cursor_backend_registered() -> None:
    assert "agent" in registered_binaries()
    assert backend._REGISTRY["cursor"] == CURSOR_BACKEND
    assert CURSOR_BACKEND.name == "cursor"


def test_cursor_binary_is_agent() -> None:
    assert CURSOR_BACKEND.binary == "agent"
    assert CURSOR_BACKEND.auth_pattern is not None


def test_cursor_plan_quota_pattern_matches_confirmed_monthly_quota_copy() -> None:
    pattern = CURSOR_BACKEND.plan_quota_pattern
    assert pattern is not None
    assert pattern.search(
        "ActionRequiredError: You've hit your usage limit for Opus. "
        "Switch to a different model or set a Spend Limit. "
        "Your usage limits will reset when your monthly cycle ends on 8/24/2026."
    )


def test_cursor_plan_quota_pattern_rejects_unrelated_marker_fragments() -> None:
    pattern = CURSOR_BACKEND.plan_quota_pattern
    assert pattern is not None

    transcript = (
        "ordinary rate limit hit; ActionRequiredError appeared in a log; "
        "later Switch to a different model was suggested; after unrelated "
        "text set a Spend Limit for the project; monthly cycle ends on "
        "another account"
    )

    assert pattern.search(transcript) is None


def test_non_cursor_backends_have_no_plan_quota_pattern() -> None:
    assert CLAUDE_BACKEND.plan_quota_pattern is None
    assert CODEX_BACKEND.plan_quota_pattern is None
    assert backend.synthesize_backend("generic").plan_quota_pattern is None
    assert _make_fake_backend("fake", "fakebin").plan_quota_pattern is None


def test_cursor_batch_argv_shape() -> None:
    argv = CURSOR_BACKEND.batch_argv("P")
    assert argv[0] == "agent"
    assert "-p" in argv
    assert "--output-format" in argv and "stream-json" in argv
    assert "--force" in argv and "--trust" in argv
    assert argv[-1] == "P"


def test_cursor_streaming_argv_matches_batch() -> None:
    assert CURSOR_BACKEND.streaming_argv("P") == CURSOR_BACKEND.batch_argv("P")


def test_cursor_command_event_maps_to_tool_use() -> None:
    events = _all_events(_parse_cursor_fixture("agent-command-execution.jsonl"))
    tool_uses = [e for e in events if e.get("kind") == "tool_use"]
    assert len(tool_uses) == 1
    assert tool_uses[0]["tool_name"] == "command"
    # The fixture's command is benign, so it passes through unredacted —
    # real redaction of cursor's native producer (batch-authoring-observability
    # step 10) doesn't touch text that carries no secret shape.
    assert tool_uses[0]["tool_input_summary"] == "echo tool_probe_ok"
    assert any(e.get("kind") == "tool_result" for e in events)


def test_cursor_assistant_text_and_terminal_stats() -> None:
    parsed = _parse_cursor_fixture("agent-result-envelope.jsonl")
    assert any("backend probe ok" in c for p in parsed for c in p.text_chunks)
    stats = _first_stats(parsed)
    assert stats.tokens_input == 48299
    assert stats.tokens_output == 40
    assert stats.cache_read_tokens == 1152
    # Deliberately not asserted for cursor: its input accounting is unmeasured.
    assert stats.input_includes_cached is None
    assert stats.cache_creation_tokens == 0
    assert stats.final_text == "backend probe ok"
    assert stats.request_id == "00000000-0000-4000-8000-00000000000a"
    assert stats.is_error is False
    assert stats.cost_usd is None


def test_cursor_non_json_line_returns_none() -> None:
    assert CURSOR_BACKEND.parse_stream_line("not json\n", bytes_in=8) is None


@pytest.fixture
def _cursor_active(_restore_backend_state):
    set_active_backend(CURSOR_BACKEND)
    yield


def test_cursor_classify_auth_failure(_cursor_active) -> None:
    failure = classify(
        1,
        "Authentication required. Please run 'agent login' first.",
        "",
    )
    assert failure.kind is ClaudeFailureKind.AUTH
    assert "cursor" in failure.hint


def test_resolve_backend_cursor() -> None:
    assert resolve_backend("cursor") == CURSOR_BACKEND


# ---------------------------------------------------------------------------
# Tool-input summary redaction (batch-authoring-observability steps 7 and 10).
# ---------------------------------------------------------------------------


def test_summarize_tool_input_redacts_bearer_and_known_prefix_tokens() -> None:
    from plan_tool.backend import _summarize_tool_input

    summary = _summarize_tool_input(
        "Bash", {"command": "curl -H 'Authorization: Bearer abc123XYZtoken' url"}
    )
    assert "abc123XYZtoken" not in summary
    assert "[REDACTED]" in summary

    for token in (
        "sk-abcdefghijklmnopqrstuvwxyz",
        "ghp_abcdefghijklmnopqrstuvwxyz",
        "gho_abcdefghijklmnopqrstuvwxyz",
        "AKIAIOSFODNN7EXAMPLE",
        "xoxb-1234567890-abcdefghijklmnop",
    ):
        summary = _summarize_tool_input("Bash", {"command": f"echo {token}"})
        assert token not in summary, token
        assert "[REDACTED]" in summary, token


def test_summarize_tool_input_redacts_high_entropy_run() -> None:
    from plan_tool.backend import _summarize_tool_input

    mixed = "aB3" * 10  # 30 chars, mixes upper/lower/digit
    summary = _summarize_tool_input("Bash", {"command": f"echo {mixed}"})
    assert mixed not in summary
    assert "[REDACTED]" in summary

    single_class = "a" * 25  # past the length threshold, only one char class
    summary = _summarize_tool_input("Bash", {"command": f"echo {single_class}"})
    assert single_class in summary
    assert "[REDACTED]" not in summary

    short_mixed = "aB3aB3aB3"  # mixed classes, but under the 20-char floor
    summary = _summarize_tool_input("Bash", {"command": f"echo {short_mixed}"})
    assert short_mixed in summary
    assert "[REDACTED]" not in summary


def test_summarize_tool_input_redacts_before_truncating() -> None:
    from plan_tool.backend import _TOOL_INPUT_SUMMARY_CAP, _summarize_tool_input

    secret = "sk-" + "A1b2C3d4E5f6G7h8I9j0" * 3
    padding = "x" * (_TOOL_INPUT_SUMMARY_CAP - 10)  # secret straddles the cap
    summary = _summarize_tool_input("Bash", {"command": f"{padding} {secret}"})
    assert secret not in summary
    assert "A1b2C3d4E5f6G7h8I9j0" not in summary


def test_summarize_tool_input_all_five_branches_redact() -> None:
    from plan_tool.backend import _summarize_tool_input

    secret = "sk-abcdefghijklmnopqrstuvwxyz"

    non_dict = _summarize_tool_input("Anything", secret)
    assert secret not in non_dict and "[REDACTED]" in non_dict

    edit_family = _summarize_tool_input("Edit", {"file_path": f"/tmp/{secret}/f.py"})
    assert secret not in edit_family and "[REDACTED]" in edit_family

    bash = _summarize_tool_input("Bash", {"command": f"echo {secret}"})
    assert secret not in bash and "[REDACTED]" in bash

    grep = _summarize_tool_input("Grep", {"pattern": secret, "path": "src/"})
    assert secret not in grep and "[REDACTED]" in grep

    unmatched = _summarize_tool_input("SomeOtherTool", {"value": secret})
    assert secret not in unmatched and "[REDACTED]" in unmatched


def test_codex_tool_use_summary_result_is_not_omitted_in_the_event() -> None:
    """A ``command_execution`` item's benign command string reaches the
    event unredacted — no more literal ``"[OMITTED]"`` placeholder now
    that codex's native producer (``_codex_tool_use_summary``) redacts for
    real."""
    events = _all_events(_parse_codex_fixture("exec-command-execution.jsonl"))
    tool_uses = [e for e in events if e.get("kind") == "tool_use"]
    assert len(tool_uses) == 1
    assert tool_uses[0]["tool_input_summary"] != "[OMITTED]"
    assert "hello-from-codex" in tool_uses[0]["tool_input_summary"]


def test_cursor_native_tool_call_result_is_not_omitted_in_the_event() -> None:
    """Same as the codex case, for cursor's own native ``tool_call``
    producer (``_cursor_parse_stream_line``'s ``subtype == "started"``
    branch) — distinct from the claude-shaped ``tool_use`` blocks cursor
    also emits, covered by
    ``test_cursor_assistant_block_tool_use_is_redacted_not_omitted``."""
    events = _all_events(_parse_cursor_fixture("agent-command-execution.jsonl"))
    tool_uses = [e for e in events if e.get("kind") == "tool_use"]
    assert len(tool_uses) == 1
    assert tool_uses[0]["tool_input_summary"] != "[OMITTED]"
    assert tool_uses[0]["tool_input_summary"] == "echo tool_probe_ok"


def test_cursor_assistant_block_tool_use_is_redacted_not_omitted() -> None:
    """``_cursor_parse_assistant_blocks``'s claude-shaped ``tool_use``
    branch goes through ``_summarize_tool_input`` and gets real redaction,
    matching claude's own path and cursor's own native ``tool_call``
    producer."""
    line = (
        '{"type":"assistant","message":{"content":[{"type":"tool_use",'
        '"name":"Bash","input":{"command":'
        '"echo sk-abcdefghijklmnopqrstuvwxyz"}}]}}'
    )
    parsed = CURSOR_BACKEND.parse_stream_line(line, bytes_in=len(line.encode("utf-8")))
    assert parsed is not None
    tool_uses = [e for e in parsed.events if e.get("kind") == "tool_use"]
    assert len(tool_uses) == 1
    summary = tool_uses[0]["tool_input_summary"]
    assert summary != "[OMITTED]"
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in summary
    assert "[REDACTED]" in summary


def test_codex_command_summary_redacts_known_prefix_token() -> None:
    from plan_tool.backend import _codex_tool_use_summary

    item = {"command": "curl -H 'Authorization: Bearer abc123XYZtoken' url"}
    name, summary = _codex_tool_use_summary("command_execution", item)
    assert name == "command"
    assert "abc123XYZtoken" not in summary
    assert "[REDACTED]" in summary
    assert "curl -H" in summary  # benign text survives


def test_codex_file_change_summary_redacts_secret_segment() -> None:
    from plan_tool.backend import _codex_tool_use_summary

    secret = "aB3" * 10  # 30 chars, mixes upper/lower/digit
    item = {"changes": [{"path": f"/scratch/{secret}/note.txt", "kind": "add"}]}
    name, summary = _codex_tool_use_summary("file_change", item)
    assert name == "edit"
    assert secret not in summary
    assert "[REDACTED]" in summary
    assert "(add)" in summary  # benign text survives


def test_codex_summary_redacts_before_truncating() -> None:
    from plan_tool.backend import _TOOL_INPUT_SUMMARY_CAP, _codex_tool_use_summary

    secret = "sk-" + "A1b2C3d4E5f6G7h8I9j0" * 3
    padding = "x" * (_TOOL_INPUT_SUMMARY_CAP - 10)  # secret straddles the cap
    item = {"command": f"{padding} {secret}"}
    _name, summary = _codex_tool_use_summary("command_execution", item)
    assert secret not in summary
    assert "A1b2C3d4E5f6G7h8I9j0" not in summary


@pytest.mark.parametrize(
    "tool_call_key,args_key,expected_name",
    [
        ("shellToolCall", "command", "command"),
        ("readToolCall", "path", "edit"),
        ("someToolCall", "target", "edit"),
    ],
)
def test_cursor_native_tool_call_summary_redacts_all_three_branches(
    tool_call_key, args_key, expected_name
) -> None:
    from plan_tool.backend import _cursor_tool_use_summary

    secret = "sk-abcdefghijklmnopqrstuvwxyz"
    tool_call = {tool_call_key: {"args": {args_key: f"prefix {secret} suffix"}}}
    name, summary = _cursor_tool_use_summary(tool_call)
    assert name == expected_name
    assert secret not in summary
    assert "[REDACTED]" in summary
    assert "prefix" in summary and "suffix" in summary  # benign text survives


def test_cursor_summary_redacts_before_truncating() -> None:
    from plan_tool.backend import _TOOL_INPUT_SUMMARY_CAP, _cursor_tool_use_summary

    secret = "sk-" + "A1b2C3d4E5f6G7h8I9j0" * 3
    padding = "x" * (_TOOL_INPUT_SUMMARY_CAP - 10)  # secret straddles the cap
    tool_call = {"shellToolCall": {"args": {"command": f"{padding} {secret}"}}}
    _name, summary = _cursor_tool_use_summary(tool_call)
    assert secret not in summary
    assert "A1b2C3d4E5f6G7h8I9j0" not in summary


def test_all_three_backends_redact_the_same_input_identically() -> None:
    """A future pattern edit reaching only one producer would fail this
    guard loudly instead of leaking through the other two."""
    from plan_tool.backend import (
        _codex_tool_use_summary,
        _cursor_tool_use_summary,
        _summarize_tool_input,
    )

    secret = "sk-abcdefghijklmnopqrstuvwxyz"
    command = f"echo {secret}"

    claude_summary = _summarize_tool_input("Bash", {"command": command})
    _codex_name, codex_summary = _codex_tool_use_summary(
        "command_execution", {"command": command}
    )
    _cursor_name, cursor_summary = _cursor_tool_use_summary(
        {"shellToolCall": {"args": {"command": command}}}
    )

    assert claude_summary == codex_summary == cursor_summary
    assert secret not in claude_summary
    assert "[REDACTED]" in claude_summary


def test_benign_summaries_pass_through_unredacted() -> None:
    """Guards against over-redaction of the ordinary commands and paths
    the fixture roster already exercises."""
    from plan_tool.backend import _codex_tool_use_summary, _cursor_tool_use_summary

    _name, codex_command_summary = _codex_tool_use_summary(
        "command_execution", {"command": "printf 'hello-from-codex'"}
    )
    assert codex_command_summary == "printf 'hello-from-codex'"

    _name, codex_edit_summary = _codex_tool_use_summary(
        "file_change",
        {"changes": [{"path": "/scratch/note.txt", "kind": "add"}]},
    )
    assert codex_edit_summary == "/scratch/note.txt (add)"

    _name, cursor_summary = _cursor_tool_use_summary(
        {"shellToolCall": {"args": {"command": "echo tool_probe_ok"}}}
    )
    assert cursor_summary == "echo tool_probe_ok"


# ---------------------------------------------------------------------------
# resolve_backend — name → descriptor view used by ``cli.main``.
# ---------------------------------------------------------------------------


def test_resolve_backend_claude() -> None:
    # Value-equal, not identity: import-time discovery already replaced the
    # registry object with the committed manifest's (the manifest reproduces
    # the literal, so they compare ``==``).
    assert resolve_backend("claude") == CLAUDE_BACKEND


def test_resolve_backend_codex() -> None:
    assert resolve_backend("codex") == CODEX_BACKEND


def test_resolve_backend_unknown_raises() -> None:
    with pytest.raises(ValueError) as excinfo:
        resolve_backend("bogus")
    message = str(excinfo.value)
    assert "bogus" in message
    assert "claude" in message and "codex" in message


# ---------------------------------------------------------------------------
# Backend-aware run-path copy: ``run_step`` failure reasons name the active
# backend, not a hardcoded "claude".
# ---------------------------------------------------------------------------

_RUN_STEP_PLAN = """---
title: Backend Copy Test
status: in-progress
priority: medium
steps:
  - id: 1
    title: First
    status: current
---

# Backend Copy Test
"""


class _RecordingStepHandle(StepHandle):
    """Captures the ``fail`` reason for assertion."""

    def __init__(self) -> None:
        self.fail_reason: str | None = None

    def complete(self, elapsed_s: float, response_bytes: int) -> None:
        return None

    def fail(self, elapsed_s: float, reason: str) -> None:
        self.fail_reason = reason


class _RecordingReporter(ProgressReporter):
    def __init__(self) -> None:
        self.handle = _RecordingStepHandle()

    def start_step(self, idx, total, label, **kwargs) -> StepHandle:
        return self.handle


def test_run_step_failure_names_active_backend(
    tmp_path: Path, _codex_active
) -> None:
    plan_path = tmp_path / "plan.md"
    plan_path.write_text(_RUN_STEP_PLAN, encoding="utf-8")
    reporter = _RecordingReporter()

    # Fake invoker returns a non-zero exit; never a real subprocess (the
    # conftest guard blocks registered binaries regardless).
    result = run_step(
        plan_path,
        repo_root=tmp_path,
        invoker=lambda _prompt: (1, ""),
        reporter=reporter,
    )

    assert result.exit_code == 1
    assert reporter.handle.fail_reason == "codex exited with code 1"


# ---------------------------------------------------------------------------
# Spawn-cwd context: get_active_spawn_cwd / spawn_cwd / spawn_cwd_from_repo_root
# ---------------------------------------------------------------------------


def test_spawn_cwd_defaults_to_none_and_restores() -> None:
    """No scope → ``None`` (inherit the process cwd, the historical
    behavior); the context manager restores the prior value, including
    across nesting."""
    from plan_tool.backend import get_active_spawn_cwd, spawn_cwd

    assert get_active_spawn_cwd() is None
    outer = Path("/outer")
    inner = Path("/inner")
    with spawn_cwd(outer):
        assert get_active_spawn_cwd() == outer
        with spawn_cwd(inner):
            assert get_active_spawn_cwd() == inner
        assert get_active_spawn_cwd() == outer
    assert get_active_spawn_cwd() is None


def test_spawn_cwd_restores_on_exception() -> None:
    from plan_tool.backend import get_active_spawn_cwd, spawn_cwd

    with pytest.raises(RuntimeError):
        with spawn_cwd(Path("/x")):
            raise RuntimeError("boom")
    assert get_active_spawn_cwd() is None


def test_spawn_cwd_from_repo_root_scopes_the_call(tmp_path: Path) -> None:
    """The decorator reads ``repo_root`` (keyword or positional) and
    scopes backend spawns to it for the duration of the call.

    This is how every ``repo_root``-bearing entrypoint (run_step,
    apply_finding, create_plan, generate_detail, review_plan_full)
    guarantees its backends run in the named tree — without it, a
    caller whose ``repo_root`` differs from the process cwd (the bench;
    a CLI invocation from a repo subdirectory) spawns backends against
    the wrong tree.
    """
    from plan_tool.backend import (
        get_active_spawn_cwd,
        spawn_cwd_from_repo_root,
    )

    seen: list[object] = []

    @spawn_cwd_from_repo_root
    def entrypoint(*, repo_root: Path) -> None:
        seen.append(get_active_spawn_cwd())

    entrypoint(repo_root=tmp_path)
    assert seen == [tmp_path]
    assert get_active_spawn_cwd() is None


def test_spawn_cwd_from_repo_root_tolerates_missing_repo_root() -> None:
    """A call that never binds ``repo_root`` scopes to inherit (None)."""
    from plan_tool.backend import (
        get_active_spawn_cwd,
        spawn_cwd_from_repo_root,
    )

    seen: list[object] = []

    @spawn_cwd_from_repo_root
    def entrypoint(prompt: str, *, repo_root=None) -> None:
        seen.append(get_active_spawn_cwd())

    entrypoint("p")
    assert seen == [None]


# ---------------------------------------------------------------------------
# load_backend_from_dir — manifest → CliBackend round-trip + loader errors.
#
# Round-trip goldens read the real committed integrations/<backend>/backend.json
# (this step's input via depends_on: 2); loader-error cases write crafted
# manifests under tmp_path for hermeticity. The argv builders and the
# compiled patterns are ``field(compare=False)`` on CliBackend, so the
# round-trip asserts whole-object ``==`` for the compared fields, argv
# fidelity by builder *output*, and pattern fidelity by ``.pattern`` /
# ``.flags`` value (re.Pattern has no value equality).
# ---------------------------------------------------------------------------

from plan_tool.backend import (  # noqa: E402
    BackendManifestError,
    load_backend_from_dir,
)

_INTEGRATIONS = Path(__file__).parents[1] / "integrations"

_PATTERN_FIELDS = (
    "rate_limit_pattern",
    "provider_limit_pattern",
    "context_overflow_pattern",
    "transient_pattern",
    "auth_pattern",
    "plan_quota_pattern",
)


def _assert_patterns_value_equal(loaded: CliBackend, literal: CliBackend) -> None:
    for fld in _PATTERN_FIELDS:
        lp = getattr(loaded, fld)
        lit = getattr(literal, fld)
        assert (lp is None) == (lit is None), fld
        if lp is None:
            continue
        assert lp.pattern == lit.pattern, fld
        assert lp.flags == lit.flags, fld


def _write_manifest(tmp_path: Path, payload: dict | str) -> Path:
    import json as _json

    text = payload if isinstance(payload, str) else _json.dumps(payload)
    (tmp_path / "backend.json").write_text(text, encoding="utf-8")
    return tmp_path


def _claude_manifest_dict() -> dict:
    import json as _json

    return _json.loads(
        (_INTEGRATIONS / "claude" / "backend.json").read_text(encoding="utf-8")
    )


def test_load_backend_from_dir_claude_round_trips() -> None:
    loaded = load_backend_from_dir(_INTEGRATIONS / "claude")
    assert loaded == CLAUDE_BACKEND
    assert loaded.batch_argv("P") == CLAUDE_BACKEND.batch_argv("P")
    assert loaded.streaming_argv("P") == CLAUDE_BACKEND.streaming_argv("P")
    _assert_patterns_value_equal(loaded, CLAUDE_BACKEND)
    assert loaded.auth_pattern is None and CLAUDE_BACKEND.auth_pattern is None


def test_load_backend_from_dir_codex_round_trips() -> None:
    loaded = load_backend_from_dir(_INTEGRATIONS / "codex")
    assert loaded == CODEX_BACKEND
    assert loaded.batch_argv("P") == CODEX_BACKEND.batch_argv("P")
    assert loaded.streaming_argv("P") == CODEX_BACKEND.streaming_argv("P")
    _assert_patterns_value_equal(loaded, CODEX_BACKEND)
    assert loaded.auth_pattern is not None
    assert loaded.auth_pattern.pattern == CODEX_BACKEND.auth_pattern.pattern
    assert loaded.auth_pattern.flags == CODEX_BACKEND.auth_pattern.flags


def test_load_backend_from_dir_cursor_round_trips() -> None:
    loaded = load_backend_from_dir(_INTEGRATIONS / "cursor")
    assert loaded == CURSOR_BACKEND
    assert loaded.batch_argv("P") == CURSOR_BACKEND.batch_argv("P")
    assert loaded.streaming_argv("P") == CURSOR_BACKEND.streaming_argv("P")
    _assert_patterns_value_equal(loaded, CURSOR_BACKEND)
    assert loaded.auth_pattern is not None
    assert loaded.auth_pattern.pattern == CURSOR_BACKEND.auth_pattern.pattern
    assert loaded.auth_pattern.flags == CURSOR_BACKEND.auth_pattern.flags


def test_cursor_manifest_plan_quota_pattern_round_trips() -> None:
    loaded = load_backend_from_dir(_INTEGRATIONS / "cursor")
    assert loaded.plan_quota_pattern is not None
    assert CURSOR_BACKEND.plan_quota_pattern is not None
    assert (
        loaded.plan_quota_pattern.pattern == CURSOR_BACKEND.plan_quota_pattern.pattern
    )
    assert loaded.plan_quota_pattern.flags == CURSOR_BACKEND.plan_quota_pattern.flags


def test_load_backend_malformed_json_raises(tmp_path: Path) -> None:
    d = _write_manifest(tmp_path, "{ not valid json")
    with pytest.raises(BackendManifestError) as excinfo:
        load_backend_from_dir(d)
    assert "backend.json" in str(excinfo.value)


def test_load_backend_unknown_parser_raises(tmp_path: Path) -> None:
    manifest = _claude_manifest_dict()
    manifest["parser"] = "bogus"
    d = _write_manifest(tmp_path, manifest)
    with pytest.raises(BackendManifestError) as excinfo:
        load_backend_from_dir(d)
    msg = str(excinfo.value)
    assert "claude" in msg and "codex" in msg and "cursor" in msg


def test_load_backend_missing_required_field_raises(tmp_path: Path) -> None:
    manifest = _claude_manifest_dict()
    del manifest["binary"]
    d = _write_manifest(tmp_path, manifest)
    with pytest.raises(BackendManifestError) as excinfo:
        load_backend_from_dir(d)
    assert "binary" in str(excinfo.value)


def test_load_backend_missing_classification_subkey_raises(tmp_path: Path) -> None:
    manifest = _claude_manifest_dict()
    del manifest["classification"]["rate_limit"]
    d = _write_manifest(tmp_path, manifest)
    with pytest.raises(BackendManifestError) as excinfo:
        load_backend_from_dir(d)
    assert "classification.rate_limit" in str(excinfo.value)


def test_load_backend_null_auth_yields_none(tmp_path: Path) -> None:
    manifest = _claude_manifest_dict()
    manifest["classification"]["auth"] = None
    d = _write_manifest(tmp_path, manifest)
    assert load_backend_from_dir(d).auth_pattern is None


def test_load_backend_string_auth_compiles(tmp_path: Path) -> None:
    manifest = _claude_manifest_dict()
    manifest["classification"]["auth"] = "not logged in"
    d = _write_manifest(tmp_path, manifest)
    pattern = load_backend_from_dir(d).auth_pattern
    assert pattern is not None
    assert pattern.search("Error: NOT LOGGED IN")  # IGNORECASE applied


def test_parser_registry_keys() -> None:
    assert backend._PARSER_REGISTRY["claude"] is backend._claude_parse_stream_line
    assert backend._PARSER_REGISTRY["codex"] is backend._codex_parse_stream_line
    assert backend._PARSER_REGISTRY["cursor"] is backend._cursor_parse_stream_line


def test_claude_backend_model_fields() -> None:
    assert CLAUDE_BACKEND.model_flag == "--model"
    assert CLAUDE_BACKEND.default_model is None


def test_codex_backend_model_fields() -> None:
    assert CODEX_BACKEND.model_flag == "-m"
    assert CODEX_BACKEND.default_model is None


def test_load_omits_default_model_from_closure(tmp_path: Path) -> None:
    manifest = _claude_manifest_dict()
    manifest["default_model"] = "claude-opus"
    d = _write_manifest(tmp_path, manifest)
    loaded = load_backend_from_dir(d)
    # The closure emits [binary, *flags, prompt] with no [model_flag, model]
    # pair — model injection is the --model step's job, keeping argv[:-1]
    # exactly [binary, *flags].
    assert loaded.default_model == "claude-opus"
    assert "claude-opus" not in loaded.batch_argv("P")
    assert "--model" not in loaded.batch_argv("P")
    assert loaded.batch_argv("P") == CLAUDE_BACKEND.batch_argv("P")


# ---------------------------------------------------------------------------
# discover_and_register_backends — iterate integrations/*/backend.json and
# register each manifest over the in-code seed.
#
# Crafted manifests are built under tmp_path for hermeticity and reuse
# ``parser: "claude"`` so they resolve through _PARSER_REGISTRY without a
# real binary. All cases run under _restore_backend_state, which snapshots
# and restores _REGISTRY + the active backend.
# ---------------------------------------------------------------------------

from plan_tool.backend import (  # noqa: E402
    discover_and_register_backends,
    _packaged_integrations_dir,
)


def _write_backend_dir(root: Path, name: str, manifest: dict | str) -> Path:
    """Create ``root/<name>/backend.json`` from a manifest dict or raw string."""
    import json as _json

    backend_dir = root / name
    backend_dir.mkdir(parents=True, exist_ok=True)
    text = manifest if isinstance(manifest, str) else _json.dumps(manifest)
    (backend_dir / "backend.json").write_text(text, encoding="utf-8")
    return backend_dir


def test_discover_registers_new_backend(
    tmp_path: Path, _restore_backend_state
) -> None:
    manifest = _claude_manifest_dict()
    manifest["name"] = "fake"
    manifest["binary"] = "fakebin"
    _write_backend_dir(tmp_path, "fake", manifest)
    discover_and_register_backends(tmp_path)
    assert resolve_backend("fake").binary == "fakebin"
    assert "fakebin" in registered_binaries()


def test_discover_replaces_seed_when_manifest_differs(
    tmp_path: Path, _restore_backend_state
) -> None:
    manifest = _claude_manifest_dict()
    manifest["binary"] = "claude-custom"
    _write_backend_dir(tmp_path, "claude", manifest)
    discover_and_register_backends(tmp_path)
    # binary is a compared field — register-over replaces the seed.
    assert resolve_backend("claude").binary == "claude-custom"


def test_discover_broken_manifest_keeps_seed(
    tmp_path: Path, _restore_backend_state
) -> None:
    before = resolve_backend("claude")
    _write_backend_dir(tmp_path, "claude", "{ not valid json")
    with pytest.warns(UserWarning) as record:
        discover_and_register_backends(tmp_path)
    assert any("claude" in str(w.message) for w in record)
    # Per-directory isolation: the seed survives the broken same-name manifest.
    assert resolve_backend("claude") is before
    assert resolve_backend("claude") == CLAUDE_BACKEND


def test_discover_regex_malformed_manifest_keeps_seed(
    tmp_path: Path, _restore_backend_state
) -> None:
    before = resolve_backend("claude")
    manifest = _claude_manifest_dict()
    manifest["classification"]["rate_limit"] = "("  # unbalanced → re.error
    _write_backend_dir(tmp_path, "claude", manifest)
    with pytest.warns(UserWarning) as record:
        discover_and_register_backends(tmp_path)
    assert any("claude" in str(w.message) for w in record)
    # The broadened except catches re.error; the seed survives.
    assert resolve_backend("claude") is before
    assert resolve_backend("claude") == CLAUDE_BACKEND


def test_discover_skips_directory_without_backend_json(
    tmp_path: Path, _restore_backend_state
) -> None:
    (tmp_path / "claude").mkdir()
    (tmp_path / "claude" / "SKILL.md").write_text("docs only", encoding="utf-8")
    snapshot = dict(backend._REGISTRY)
    discover_and_register_backends(tmp_path)
    assert backend._REGISTRY == snapshot


def test_discover_missing_root_is_noop(
    tmp_path: Path, _restore_backend_state
) -> None:
    discover_and_register_backends(tmp_path / "nope")
    assert registered_binaries() == {"claude", "codex", "agent"}


def test_discover_iterates_multiple_dirs(
    tmp_path: Path, _restore_backend_state
) -> None:
    alpha = _claude_manifest_dict()
    alpha["name"], alpha["binary"] = "alpha", "alphabin"
    beta = _claude_manifest_dict()
    beta["name"], beta["binary"] = "beta", "betabin"
    _write_backend_dir(tmp_path, "alpha", alpha)
    _write_backend_dir(tmp_path, "beta", beta)
    discover_and_register_backends(tmp_path)
    assert resolve_backend("alpha").binary == "alphabin"
    assert resolve_backend("beta").binary == "betabin"


def test_packaged_integrations_dir_finds_real_manifests() -> None:
    root = _packaged_integrations_dir()
    assert root is not None
    assert (root / "claude" / "backend.json").is_file()
    assert (root / "shared" / "DIRECTIVES.md").is_file()


def test_import_time_discovery_keeps_claude_runnable() -> None:
    # The committed manifest reproduces the literal, so the run path is
    # byte-identical after import-time register-over.
    assert resolve_backend("claude").batch_argv("P") == CLAUDE_BACKEND.batch_argv("P")


# ---------------------------------------------------------------------------
# build_effective_backend — argv splice / short-circuit / guard.
#
# Fidelity is asserted by builder *output*, never dataclass equality:
# ``batch_argv`` / ``streaming_argv`` are ``field(compare=False)`` and a
# requested model leaves the effective backend ``==`` its base.
# ---------------------------------------------------------------------------


def test_build_effective_backend_no_overrides_returns_base() -> None:
    effective = build_effective_backend(
        CLAUDE_BACKEND, model=None, extra_batch_argv=[], extra_streaming_argv=[]
    )
    assert effective is CLAUDE_BACKEND


def test_build_effective_backend_inserts_claude_model_pair() -> None:
    effective = build_effective_backend(
        CLAUDE_BACKEND, model="opus", extra_batch_argv=[], extra_streaming_argv=[]
    )
    assert effective.batch_argv("P") == [
        "claude",
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--permission-mode",
        "acceptEdits",
        "--model",
        "opus",
        "P",
    ]
    assert effective.streaming_argv("P")[-5:] == [
        "--permission-mode",
        "acceptEdits",
        "--model",
        "opus",
        "P",
    ]


def test_build_effective_backend_inserts_codex_model_pair() -> None:
    effective = build_effective_backend(
        CODEX_BACKEND, model="o3", extra_batch_argv=[], extra_streaming_argv=[]
    )
    assert effective.batch_argv("P") == [
        "codex",
        "exec",
        "--json",
        "-s",
        "workspace-write",
        "--skip-git-repo-check",
        "--ephemeral",
        "-m",
        "o3",
        "P",
    ]


def test_build_effective_backend_appends_extra_before_model() -> None:
    effective = build_effective_backend(
        CLAUDE_BACKEND,
        model="opus",
        extra_batch_argv=["--foo"],
        extra_streaming_argv=[],
    )
    assert effective.batch_argv("P") == [
        "claude",
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--permission-mode",
        "acceptEdits",
        "--foo",
        "--model",
        "opus",
        "P",
    ]


def test_build_effective_backend_extra_only_no_model() -> None:
    effective = build_effective_backend(
        CLAUDE_BACKEND,
        model=None,
        extra_batch_argv=[],
        extra_streaming_argv=["--bar"],
    )
    argv = effective.streaming_argv("P")
    assert "--bar" in argv
    assert "--model" not in argv
    assert argv[-1] == "P"
    assert argv[-2] == "--bar"


def test_build_effective_backend_preserves_stdin_prompt_transport() -> None:
    base = replace(
        CLAUDE_BACKEND,
        batch_argv=lambda _prompt: ["stdin-backend", "--read-prompt"],
        batch_prompt_transport=lambda prompt: PromptTransport(
            ["stdin-backend", "--read-prompt"], stdin_text=prompt
        ),
    )
    effective = build_effective_backend(
        base,
        model="opus",
        extra_batch_argv=["--foo"],
        extra_streaming_argv=[],
    )
    transport = effective.batch_transport("PROMPT")
    assert transport.argv == [
        "stdin-backend",
        "--read-prompt",
        "--foo",
        "--model",
        "opus",
    ]
    assert transport.stdin_text == "PROMPT"
    assert effective.batch_argv("PROMPT") == transport.argv


def test_build_effective_backend_model_without_flag_raises() -> None:
    flagless = replace(CLAUDE_BACKEND, model_flag=None)
    with pytest.raises(ValueError, match="claude"):
        build_effective_backend(
            flagless, model="x", extra_batch_argv=[], extra_streaming_argv=[]
        )


def test_build_effective_backend_preserves_parser_and_patterns() -> None:
    effective = build_effective_backend(
        CLAUDE_BACKEND, model="opus", extra_batch_argv=[], extra_streaming_argv=[]
    )
    assert effective.parse_stream_line is CLAUDE_BACKEND.parse_stream_line
    assert effective.binary == CLAUDE_BACKEND.binary
    assert effective.rate_limit_pattern is CLAUDE_BACKEND.rate_limit_pattern
    assert effective.transient_pattern is CLAUDE_BACKEND.transient_pattern


def test_build_effective_backend_eq_base_under_dataclass_eq() -> None:
    effective = build_effective_backend(
        CLAUDE_BACKEND, model="opus", extra_batch_argv=[], extra_streaming_argv=[]
    )
    # argv builders are ``compare=False``, so the effective backend stays
    # value-equal to its base — fidelity is output-asserted, not eq-asserted.
    assert effective == CLAUDE_BACKEND


def test_build_effective_backend_exposes_resolved_model() -> None:
    base = replace(CLAUDE_BACKEND, default_model="manifest-model")

    effective = build_effective_backend(
        base,
        model="selected-model",
        extra_batch_argv=[],
        extra_streaming_argv=[],
    )

    assert effective.default_model == "manifest-model"
    assert effective.resolved_model == "selected-model"


def test_effective_backend_model_field_preserves_descriptor_contracts() -> None:
    unchanged = build_effective_backend(
        CLAUDE_BACKEND,
        model=None,
        extra_batch_argv=[],
        extra_streaming_argv=[],
    )
    selected = build_effective_backend(
        CLAUDE_BACKEND,
        model="selected-model",
        extra_batch_argv=[],
        extra_streaming_argv=[],
    )

    assert unchanged is CLAUDE_BACKEND
    assert unchanged.resolved_model is None
    assert selected == CLAUDE_BACKEND
    assert selected.resolved_model == "selected-model"
    assert selected.batch_argv("P")[-3:] == ["--model", "selected-model", "P"]


def test_backend_selection_sequence_applies_project_override_and_sets_active(
    tmp_path: Path, _restore_backend_state
) -> None:
    from plan_tool.backend_config import load_backend_overrides

    config_dir = tmp_path / ".plan-tool"
    config_dir.mkdir()
    (config_dir / "backends.json").write_text(
        """
        {
          "backends": {
            "claude": {
              "model": "opus",
              "extra_batch_argv": ["--batch-extra"],
              "extra_streaming_argv": ["--stream-extra"]
            }
          }
        }
        """,
        encoding="utf-8",
    )

    selected = resolve_backend("claude")
    overrides = load_backend_overrides(tmp_path)
    override = overrides["claude"]
    effective = build_effective_backend(
        selected,
        model=override.model or selected.default_model,
        extra_batch_argv=override.extra_batch_argv,
        extra_streaming_argv=override.extra_streaming_argv,
    )
    set_active_backend(effective)

    active = get_active_backend()
    assert active.batch_argv("P")[-4:] == ["--batch-extra", "--model", "opus", "P"]
    assert active.streaming_argv("P")[-4:] == [
        "--stream-extra",
        "--model",
        "opus",
        "P",
    ]


def test_select_active_backend_applies_project_override_and_sets_active(
    tmp_path: Path, _restore_backend_state
) -> None:
    config_dir = tmp_path / ".plan-tool"
    config_dir.mkdir()
    (config_dir / "backends.json").write_text(
        """
        {
          "backends": {
            "claude": {
              "model": "opus",
              "extra_batch_argv": ["--batch-extra"],
              "extra_streaming_argv": ["--stream-extra"]
            },
            "typo": {
              "model": "ignored"
            }
          }
        }
        """,
        encoding="utf-8",
    )

    selection = select_active_backend("claude", repo_root=tmp_path)

    assert selection.selected == CLAUDE_BACKEND
    assert selection.effective is get_active_backend()
    assert selection.unknown_override_names == ("typo",)
    assert selection.effective.resolved_model == "opus"
    assert selection.effective.batch_argv("P")[-4:] == [
        "--batch-extra",
        "--model",
        "opus",
        "P",
    ]
    assert selection.effective.streaming_argv("P")[-4:] == [
        "--stream-extra",
        "--model",
        "opus",
        "P",
    ]


# --- context windows a result envelope reports (moved from the window feature's tests) ----------------


_REAL_CLAUDE_MODEL_USAGE = {
    "claude-sonnet-5-5": {
        "inputTokens": 2,
        "outputTokens": 4,
        "cacheReadInputTokens": 10873,
        "cacheCreationInputTokens": 26765,
        "webSearchRequests": 0,
        "costUSD": 0.1092786,
        "contextWindow": 1000000,
    }
}


def _result_line(model_usage: object) -> str:
    return json.dumps({"type": "result", "result": "ok", "usage": {}, "modelUsage": model_usage})


_SONNET_1M = "claude-sonnet-5-5[1m]"


_SONNET = "claude-sonnet-5-5"


_HAIKU = "claude-haiku-4-5"


def test_the_result_envelope_reports_every_models_window() -> None:
    line = _result_line({"a": {"contextWindow": 200_000}, "b": {"contextWindow": 1_000_000}})

    parsed = CLAUDE_BACKEND.parse_stream_line(line, bytes_in=len(line))

    assert parsed is not None and parsed.stats is not None
    assert parsed.stats.model_windows == (("a", 200_000), ("b", 1_000_000))


@pytest.mark.parametrize(
    ("selected", "windows", "expected"),
    [
        # An id equal to the selection is exact, even beside an id that merely contains or is contained.
        (_SONNET_1M, ((_SONNET_1M, 1_000_000), (_SONNET, 200_000)), (1_000_000, True)),
        (_SONNET, ((_SONNET_1M, 1_000_000), (_SONNET, 200_000)), (200_000, True)),
        (_HAIKU, ((_HAIKU, 200_000), ("claude-opus-5-5", 1_000_000)), (200_000, True)),
        ("claude-opus-5-5", ((_HAIKU, 200_000), ("claude-opus-5-5", 1_000_000)), (1_000_000, True)),
        # No exact id: a single-entry envelope serves any alias exactly...
        ("sonnet[1m]", ((_SONNET_1M, 1_000_000),), (1_000_000, True)),
        (None, ((_SONNET_1M, 1_000_000),), (1_000_000, True)),
        # ...and a mixed one gives only the smallest window, a lower bound that errs toward warning.
        ("sonnet[1m]", ((_SONNET_1M, 1_000_000), (_HAIKU, 200_000)), (200_000, False)),
        ("claude", ((_SONNET, 200_000), ("claude-opus-5-5", 1_000_000)), (200_000, False)),  # no substring match
        (None, ((_SONNET_1M, 1_000_000), (_HAIKU, 200_000)), (200_000, False)),
        ("", ((_SONNET_1M, 1_000_000), (_HAIKU, 200_000)), (200_000, False)),
        (None, (), None),
    ],
)
def test_the_remembered_window_is_the_exact_models_else_a_lower_bound(selected, windows, expected) -> None:
    """The whole case matrix of one rule: exact id or a lone entry is exact, else the smallest is a bound."""
    assert backend.reported_window_for_model(selected, windows) == expected


@pytest.mark.parametrize(
    ("held", "window", "exact", "expected"),
    [
        (None, 200_000, False, (200_000, False)),
        (None, 1_000_000, True, (1_000_000, True)),
        ((200_000, False), 150_000, False, (200_000, False)),   # a bound only rises
        ((200_000, False), 300_000, False, (300_000, False)),
        ((200_000, False), 500_000, True, (500_000, True)),     # exact replaces a bound
        ((1_000_000, True), 200_000, False, (1_000_000, True)),  # a bound never replaces exact
        ((1_000_000, True), 250_000, True, (250_000, True)),     # a later exact replaces exact
    ],
)
def test_the_merge_rule_for_a_reported_window(held, window, exact, expected) -> None:
    assert backend._merged_observation(held, window, exact) == expected


def test_concurrent_pumps_cannot_lose_an_exact_window_to_a_stale_lower_bound() -> None:
    """Each in-flight call has its own pump thread, so the read-modify-write must be one step: with an
    exact write in the mix the final state is exact whatever the interleaving."""
    key_args = ("claude", "stress")
    gate = threading.Barrier(6)

    def writer(exact: bool) -> None:
        gate.wait()
        for i in range(3000):
            observe_context_window(*key_args, 200_000 + (i % 7), exact=exact and i == 1500)

    threads = [threading.Thread(target=writer, args=(n == 0,)) for n in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert backend._observed_context_windows[("claude", "stress")][1] is True


def test_a_lower_bound_never_replaces_an_exact_window_and_only_rises() -> None:
    """Two calls of identical size must not be judged differently because the latest one used a helper."""
    observe_context_window("claude", None, 1_000_000, exact=True)
    observe_context_window("claude", None, 200_000, exact=False)  # a mixed envelope later
    assert context_window_for("claude", None) == 1_000_000

    observe_context_window("claude", "m", 150_000, exact=False)
    observe_context_window("claude", "m", 200_000, exact=False)
    observe_context_window("claude", "m", 100_000, exact=False)
    assert context_window_for("claude", "m") == 200_000  # a bound is raised, never lowered by a later one

    observe_context_window("claude", "m", 300_000, exact=True)
    assert context_window_for("claude", "m") == 300_000  # an exact window replaces a bound
    observe_context_window("claude", "m", 250_000, exact=True)
    assert context_window_for("claude", "m") == 250_000  # and a later exact window replaces an exact one


@pytest.mark.parametrize(
    "model_usage", [None, [], {}, {"a": {}}, {"a": {"contextWindow": 0}}, {"a": {"contextWindow": "1000000"}}, {"a": 5}]
)
def test_an_envelope_without_a_usable_window_reports_no_windows(model_usage: object) -> None:
    line = _result_line(model_usage)

    parsed = CLAUDE_BACKEND.parse_stream_line(line, bytes_in=len(line))

    assert parsed is not None and parsed.stats is not None
    assert parsed.stats.model_windows == ()


def test_a_recorded_real_claude_model_usage_yields_its_window() -> None:
    line = _result_line(_REAL_CLAUDE_MODEL_USAGE)

    parsed = CLAUDE_BACKEND.parse_stream_line(line, bytes_in=len(line))

    assert parsed is not None and parsed.stats is not None
    assert backend.reported_window_for_model("claude-sonnet-5-5", parsed.stats.model_windows) == (1_000_000, True)
