> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Move the streaming Popen runner out of launcher.py into a shared module

## Summary

Relocates `plan_tool/launcher.py`'s `_run_streaming_once` — the Popen spawn, the stdout/stderr pump threads, the NDJSON-to-event parsing, the heartbeat daemon, and the stall marker — into a new leaf module, `plan_tool/backend_runner.py`, as its central public function. `launcher.py` keeps a same-named thin wrapper at module scope so `shell_invoker` and every existing test that monkeypatches `launcher._run_streaming_once` or `launcher.get_active_backend` keeps working with no edits. The one behavior-shaping change the move makes: the moved function takes the transport call — today hardcoded as `backend.streaming_transport(prompt)` — as an explicit parameter, so a later batch caller (step 6) can hand it `batch_transport` instead without another change to the runner itself. Everything else — Popen argv, thread model, heartbeat/stall/timing constants, console-verbosity gating, the dormant `sibling_log_dir` transcript writer — moves unchanged; this step introduces no new observable behavior for `run`. Green when `plan_tool/backend_runner.py` exists as a leaf importing only `plan_tool.backend` and `plan_tool.run_log`, the ~20 existing streaming-runner tests pass against it (relocated, and where they exercised the now-parameterized transport call, adapted), and the full suite stays green.

## Table of Contents

- [Summary](#summary) — what moves, what stays put, and the one parameterization change
- [Why](#why) — why the runner can't just become public inside `launcher.py`
- [Input](#input) — the existing contracts this step must not change the shape of
- [Files (creates vs edits)](#files-creates-vs-edits) — new module and test file, plus the doc/test edits the move implies
- [Implementation](#implementation) — the split, the wrapper, and the test migration
- [Tests](#tests) — what moves, what's added, what stays
- [Acceptance criteria](#acceptance-criteria) — observable, checkable facts
- [References](#references) — background reading for the mechanism being moved
- [Applicable guardrails](#applicable-guardrails) — plan fences this step must respect
- [Deferred](#deferred) — what later steps in this plan build on top of this move

## Why

The plan's whole point is to make the run lane's supervisor reachable from the batch lane (`plan_tool/shell.py:claude_invoke`, step 6) so every `claude_invoke` caller gets the heartbeat/stall/silence-kill protection `run` already has. Today that supervisor is private state inside `launcher.py` — module-level constants, a leading-underscore function, console-verbosity globals — and nothing outside `launcher.py` can reach it without importing `launcher.py` directly.

That import is not available to `shell.py`. `plan_tool/launcher.py` already imports from `plan_tool.shell` (`DEFAULT_MAX_TRANSIENT_RETRIES`, `DEFAULT_TRANSIENT_BASE_DELAY`, `get_active_notifier`), so `shell.py` importing back from `launcher.py` would create a cycle. The runner has to move to a third module that sits below both — the same shape `plan_tool/git_state.py` already uses (a leaf below `shell`/`launcher` whose only first-party import is `plan_tool.rate_limit_loop`) for the retry guard both backend callers share. `plan_tool/backend_runner.py` is that module for the Popen supervisor.

## Input

- **Step 1's characterization suite** (`tests/test_shell.py`, `tests/test_roadmap.py`, `tests/test_launcher.py`) pins `claude_invoke`'s today-behavior on the batch side — the `TimeoutExpired` → `ClaudeFailureKind.TIMEOUT` path, `_normalize_batch_stdout`'s collapse rule, and the silent wait/sleep window. This step doesn't touch `claude_invoke` or `shell.py` at all (that's step 6), so none of step 1's pinned facts are exercised directly here — they stay the baseline step 6 diffs against once the batch lane is wired onto the runner this step creates.
- **`plan_tool.backend`'s transport contract** (`CliBackend.streaming_transport`/`batch_transport`, `PromptTransport`) is an existing, unchanged API surface. This step's new `transport` parameter accepts whatever `PromptTransport` either bound method returns (argv-carried or stdin-carried prompt) — it does not add a new transport shape, and `backend.py` itself is not in this step's file list.

## Files (creates vs edits)

**New files:**

- `plan_tool/backend_runner.py` — the relocated Popen supervisor: the moved function, its threading/heartbeat/kill-ladder constants, and the console-verbosity level constants + `set_console_verbosity`/`get_console_verbosity`.
- `tests/test_backend_runner.py` — the relocated `TestRunStreamingOnceStreamJson` roster (retargeted at the new module), plus a leaf-import-discipline test and a byte-compatibility regression test.

**Existing files (edits only):**

- `plan_tool/launcher.py` — remove the relocated function body and its constants; import them from `plan_tool.backend_runner`; keep a same-named thin wrapper (see Implementation) so the monkeypatch seam and `cli/app.py`'s existing import both keep working; re-export the console-verbosity names.
- `tests/test_launcher.py` — remove `TestRunStreamingOnceStreamJson` and `_StreamRecordingLogger` (moved to `tests/test_backend_runner.py`); remove the local `_FakePipe`/`_FakeProc`/`_make_popen_factory` definitions (moved to `tests/subprocess_doubles.py`) and import them from there for the tests that stay (`_popen_factory_with_edits`'s callers, `TestMutatingModes`, the `shell_invoker` retry-loop tests); add or adapt one test proving `launcher._run_streaming_once`'s wrapper still resolves its transport from `get_active_backend()` (the wrapper-level replacement for `test_streaming_routes_through_active_backend_argv`).
- `tests/subprocess_doubles.py` — add `_FakePipe`, `_FakeProc`, and `_make_popen_factory`, relocated from `tests/test_launcher.py`, so both test files share one fixture set instead of duplicating ~80 lines of Popen-fake plumbing.
- `TESTING.md` — update the `Popen` analogue pointer (currently naming only `tests/test_launcher.py::_popen_factory_with_edits`) to also name `tests/subprocess_doubles.py::_make_popen_factory`, and add a short note that `shell_invoker`'s subprocess supervision now lives in `plan_tool/backend_runner.py:run_streaming_once`, reached through `launcher._run_streaming_once`'s forwarding wrapper — the seam a test monkeypatches is unchanged.
- `CLAUDE.md` — add one bullet to "## Architecture" → "Cycle-free import constraints" naming `backend_runner.py` as a leaf below `shell`/`launcher` whose only first-party imports are `plan_tool.backend` and `plan_tool.run_log`, mirroring the existing `git_state.py` bullet.
- `docs/ARCHITECTURE.md` — add a bullet under "## Backend abstraction" describing `backend_runner.py`'s role and its `transport` parameter, mirroring the existing `git_state.py` bullet's format and placement.
- `docs/CODEX_CLI_CONTRACT.md` — update every citation of `plan_tool/launcher.py:_run_streaming_once` (the streaming-invocation section, the stats-envelope correspondence note, and the closing References list) to name `plan_tool/backend_runner.py` as the defining module.

## Implementation

**The split.** Move `_run_streaming_once`'s full body — the `Popen` call, `_pump_stdout`/`_pump_stderr`/`_heartbeat` closures, the `contextvars.copy_context()` thread wiring, the kill ladder, and the sibling-NDJSON writer at the end — into `plan_tool/backend_runner.py`, along with the constants and globals it alone reads: `_PROGRESS_INTERVAL_S`, `_STALL_THRESHOLD_S`, `_KILL_AFTER_SILENCE_S`, `_KILL_GRACE_S`, `_CONSOLE_VERBOSITY_QUIET`/`_VERBOSE`/`_DEBUG`, the module-level `_console_verbosity`, and `set_console_verbosity`/`get_console_verbosity`. `backend_runner.py` needs `plan_tool.backend` for `ClaudeRunStats`, `get_active_backend` (still called directly for `.parse_stream_line` inside the pump and `.name` inside the kill message — only the transport call is parameterized, nothing else about backend resolution changes), `get_active_spawn_cwd`, and `PromptTransport`; and `plan_tool.run_log` for `RunLogLineTooLarge` (the pump's and heartbeat's best-effort emit guards) and, under `TYPE_CHECKING`, `RunLogWriter`. Neither import creates a cycle — `run_log.py` is itself first-party-import-free (json/os/secrets/tempfile/threading/time only), the same property `git_state.py` relies on for `rate_limit_loop.py`.

**The one parameterization.** Today `_run_streaming_once` does `backend = get_active_backend(); transport = backend.streaming_transport(prompt)`. The moved function instead takes `transport` as an explicit parameter — a `Callable[[str], PromptTransport]` — and calls `transport(prompt)` where that line used to sit. One shape: `run_streaming_once(prompt, transport, *, run_logger=None, phase="claude_call", attempt=1, sibling_log_dir=None)`, keeping every other parameter's name, default, and keyword-only-ness unchanged from today's signature. This is the mechanical change the plan's intent names: it's what lets `claude_invoke` pass `batch_transport` in step 6 with no further edit to the runner.

**`_streaming_prompt_bytes` does not move.** It's a separate `launcher.py` helper (`run_step`'s prompt-budget accounting) that also calls `get_active_backend().streaming_transport(prompt)`, but for byte-counting, not spawning — it never calls `_run_streaming_once`. Leave it exactly where it is.

**The wrapper.** `launcher.py` needs a module-level name still called `_run_streaming_once` for two reasons that are both load-bearing, not cosmetic: `shell_invoker`'s `_run_once_seam` calls it as a bare, unqualified reference (the existing comment at that call site says so explicitly — "Bare in-module reference so `launcher._run_streaming_once` monkeypatches... are honored"), and `TestShellInvokerContextVarPlumbing`'s three tests plus `TestShellInvokerStatsHandoff` monkeypatch exactly that name with zero knowledge of where the real implementation lives. One shape: a thin function in `launcher.py` that resolves `get_active_backend().streaming_transport` and forwards everything else to `backend_runner.run_streaming_once`. Because Python resolves a bare name inside a function at call time against the *enclosing module's* namespace, `monkeypatch.setattr(launcher, "_run_streaming_once", fake)` keeps working unchanged regardless of where the real function is defined — verify this holds by running `TestShellInvokerContextVarPlumbing`'s and `TestShellInvokerStatsHandoff`'s existing tests with **no edits** and confirming they stay green.

**The console-verbosity re-export.** `plan_tool/cli/app.py` (not in this step's `files:` — it must stay a zero-diff caller) imports `set_console_verbosity`, `_CONSOLE_VERBOSITY_DEBUG`, `_CONSOLE_VERBOSITY_QUIET`, `_CONSOLE_VERBOSITY_VERBOSE` from `plan_tool.launcher`. Once those move to `backend_runner.py`, `launcher.py` needs to re-export them (a plain `from plan_tool.backend_runner import (...)` at module top) so that import keeps resolving.

**What does not change.** No exception-safety net around `proc.wait()` (that's step 3, which `depends_on: 2`), no configured-timeout kill or termination-reason vocabulary (step 4), no new run-log event types (steps 5/7/9), no batch caller wired onto the runner (step 6), no tool-input redaction (steps 7/10). The moved function's threading model, argv, stdin handling, and heartbeat/stall/kill timings must be identical to today's — this step is `change_type: refactor` for a reason.

## Tests

### Tests for this step

- `test_leaf_has_bounded_first_party_imports` (`tests/test_backend_runner.py`) — source-scans `plan_tool/backend_runner.py` for `^(from|import) plan_tool` lines and asserts the only first-party modules named are `plan_tool.backend` and `plan_tool.run_log` — never `plan_tool.launcher` or `plan_tool.shell`, which is the property that keeps the module acyclic for step 6.
- `test_module_loads_in_isolation_with_no_launcher_or_shell` (`tests/test_backend_runner.py`) — loads `backend_runner.py` via `importlib.util.spec_from_file_location` (bypassing the package `__init__`) and asserts `sys.modules` gained no `plan_tool.launcher`/`plan_tool.shell` entry, mirroring the two-part idiom `tests/test_rate_limit_loop.py:test_leaf_has_no_first_party_runtime_import` uses for a stricter stdlib-only leaf.
- The ~20 existing cases from `tests/test_launcher.py`'s `TestRunStreamingOnceStreamJson` (`test_uses_stream_json_argv`, `test_spawn_closes_stdin`, `test_streaming_supports_stdin_prompt_transport`, `test_non_json_lines_fall_through_to_stdout_buffer`, `test_emits_tool_use_event_with_input_summary`, `test_tool_use_summary_for_bash_picks_command`, `test_tool_use_summary_for_grep_combines_pattern_and_path`, `test_tool_use_summary_truncates_long_inputs`, `test_assistant_text_block_appended_to_stdout_buffer`, `test_result_envelope_populates_stats`, `test_result_is_error_true_surfaces`, `test_request_id_none_when_no_assistant_event`, `test_request_id_uses_last_assistant_on_multi_turn`, `test_kill_on_sustained_silence`, `test_kill_escalates_to_sigkill_when_terminate_ignored`, `test_sibling_ndjson_transcript_written`, `test_sibling_transcript_only_written_when_kwarg_supplied`, `test_returns_default_stats_when_no_result_envelope`, `test_no_progress_events_emitted_for_fast_calls`) move to `tests/test_backend_runner.py`, calling `backend_runner.run_streaming_once(prompt, transport=...)` in place of `launcher._run_streaming_once(prompt)`, and monkeypatching `backend_runner._PROGRESS_INTERVAL_S`/`_STALL_THRESHOLD_S`/`_KILL_AFTER_SILENCE_S`/`_KILL_GRACE_S` in place of `launcher.*` wherever the kill-ladder tests compress those thresholds.
- `test_streaming_routes_through_active_backend_argv` (moved, adapted, `tests/test_backend_runner.py`) — no longer patches `get_active_backend`; instead passes a fake `transport` callable directly to `run_streaming_once` and asserts the Popen argv matches whatever that callable returns, proving the transport call is genuinely parameterized rather than resolved internally.
- `test_run_streaming_once_wrapper_resolves_transport_from_active_backend` (new, `tests/test_launcher.py`) — the wrapper-level replacement for the above: patches `launcher.get_active_backend` to a fake backend and calls `launcher._run_streaming_once("prompt")` (no transport kwarg), asserting the Popen argv reflects the patched backend's `streaming_transport` — this is what actually proves "`run`'s call site passes `streaming_transport`."
- `test_shell_invoker_still_honors_run_streaming_once_monkeypatch` (existing, unedited — `TestShellInvokerContextVarPlumbing`'s three cases plus `TestShellInvokerStatsHandoff`) — green with zero code changes is itself the regression proof that the wrapper preserved the seam.
- `test_backend_runner_matches_pre_move_shell_invoker_behavior` (new, `tests/test_backend_runner.py` or `tests/test_launcher.py`) — drives `launcher.shell_invoker` end-to-end through the same `_make_popen_factory` sequence an existing `shell_invoker` retry test uses, and asserts the captured Popen argv, `stdin` handling, and returned `(rc, stdout)` shape are unchanged — the plan's own step-2 test-strategy line ("a test proving the relocated pump/heartbeat/silence-kill behavior is byte-identical to today's `run`").

Every test above must be green before this step is done, along with the full suite (`uv run pytest tests/ -q -n auto`) — this step's `files:` list touches shared test infrastructure (`tests/subprocess_doubles.py`) that other test files import.

## Acceptance criteria

- `plan_tool/backend_runner.py` exists and defines the moved supervisor as a function taking an explicit `transport` parameter; it imports no first-party module besides `plan_tool.backend` and `plan_tool.run_log`.
- `plan_tool.launcher` still exposes a callable `_run_streaming_once` name at module scope, and `monkeypatch.setattr(launcher, "_run_streaming_once", fake)` still intercepts `shell_invoker`'s call — `TestShellInvokerContextVarPlumbing`'s and `TestShellInvokerStatsHandoff`'s existing tests pass with no edits to their bodies.
- `plan_tool/cli/app.py` continues to import `set_console_verbosity`/`_CONSOLE_VERBOSITY_DEBUG`/`_CONSOLE_VERBOSITY_QUIET`/`_CONSOLE_VERBOSITY_VERBOSE` from `plan_tool.launcher` unchanged (it is not in this step's `files:` list — a zero-diff caller, confirmed by `git diff --stat` showing no change to that path).
- Every threshold constant (`_PROGRESS_INTERVAL_S`, `_STALL_THRESHOLD_S`, `_KILL_AFTER_SILENCE_S`, `_KILL_GRACE_S`) and the console-verbosity level constants live only in `plan_tool/backend_runner.py`; nothing in `plan_tool/launcher.py` duplicates their values.
- A test drives `launcher.shell_invoker` end-to-end (not the raw runner) and asserts the Popen argv, stdin handling, and returned `(rc, stdout)` shape are unchanged from before the move.
- `uv run pytest tests/test_launcher.py tests/test_backend_runner.py tests/test_shell.py tests/test_roadmap.py -q` passes; `uv run pytest tests/ -q -n auto` passes.
- No test in the new or edited rosters spawns a real backend binary (`tests/conftest.py`'s autouse guard stays untripped).
- `docs/CODEX_CLI_CONTRACT.md`'s citations of `_run_streaming_once` name `plan_tool/backend_runner.py`, not `plan_tool/launcher.py`.
- `CLAUDE.md`'s "Cycle-free import constraints" bullets list `backend_runner.py`; `docs/ARCHITECTURE.md`'s "## Backend abstraction" section describes it and its `transport` parameter.
- `git diff --stat` against this step's base commit touches only files in this step's declared `files:`/`creates:` list.

## References

- [Claude Code CLI reference](https://docs.claude.com/en/docs/claude-code/cli-reference) — the `-p --output-format stream-json` invocation this step's Popen argv must keep byte-identical after the move.
- [subprocess — Subprocess management (Python 3.13)](https://docs.python.org/3/library/subprocess.html) — `Popen`, pipe threading, and `terminate`/`kill` semantics for the relocated spawn, pump, and kill-ladder code.

## Applicable guardrails

- **Plan's "## Out of scope" — the silence-based kill is a distinct, not-yet-built mechanism.** This step must not describe or implement any new timeout/kill behavior; the heartbeat and existing kill ladder move unchanged, and the new silence-kill semantics for the batch lane stay entirely out of scope here (that's steps 2–4's later work per step 1's own guardrail, restated at this altitude: this step is the "extract," not the "harden").
- **Architecture's ordering-constraint bullet.** The extraction must land byte-compatible with `run`'s existing behavior *before* the kill-on-any-exception net (step 3) or the batch wiring (step 4/6) — this step must not pull either of those forward into its own scope, even where it would be convenient (e.g., adding the exception net while the code is already open).
- **Architecture's "allowed behavior changes" bullet.** None of that bullet's seven enumerated changes (silence kill for batch, kill-on-any-exception, `run_interrupted`, `backend_spawn`/`backend_termination`, the Ctrl-C exit-code fix, tool-input redaction, or the `_pump_stderr` verbosity gate) belong to this step. If a test in this step's roster would need one of them to pass, that's a signal the test belongs in a later step, not that this step should add the behavior early.

## Deferred

- The kill-on-any-exception safety net around `proc.wait()` — step 3, which `depends_on: 2`.
- The configured-timeout kill and the closed termination-reason vocabulary — step 4.
- Wiring `shell.claude_invoke`/`roadmap`'s batch calls onto the shared runner — step 6; this step only makes the runner reachable from outside `launcher.py`, it does not change any batch caller's behavior.
- Any new run-log event type (`backend_spawn`, `backend_termination`, `run_interrupted`, `backend_recovery_wait`) — steps 5, 7, 9.
- Redaction of tool-input summaries in `_summarize_tool_input` — steps 7 and 10.
- Activating the dormant `sibling_log_dir` NDJSON transcript writer for any production caller — it carries forward unwired, exactly as the plan's own step-2 intent states, through at least step 6.
- Bringing `docs/RUN_FLOW.md`'s "Rate-limit / transient recovery seam" section and source map current with the shared-runner design — step 10 explicitly owns that doc; this step does not touch it.
