> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Pin today's batch-call logging and timeout behavior with tests

## Summary

Adds characterization tests to `tests/test_shell.py`, `tests/test_roadmap.py`, and `tests/test_launcher.py` that lock in exactly what `plan_tool/shell.py`'s `claude_invoke` and its batch callers (`roadmap` first) do today, before the runner move in steps 2–9 touches any of it. Three things get pinned: the `subprocess.TimeoutExpired` → `BACKEND_TIMEOUT_SENTINEL` → terminal classification path for a configured timeout; `_normalize_batch_stdout`'s collapse rule when streamed `assistant` text chunks are followed by a terminal `result` line; and the fact that neither `claude_invoke`'s nor `launcher.shell_invoker`'s rate-limit-wait / transient-sleep window writes anything to the run log today, on either lane. No production code changes — this step adds tests only, against current behavior. The suite this step adds is what steps 2 and 6 diff their own test runs against to prove the runner move and the batch-call swap changed nothing this step didn't call out.

## Table of Contents

- [Summary](#summary) — what this step adds and why it's tests-only
- [Why](#why) — what later steps need a pinned baseline for
- [Files (creates vs edits)](#files-creates-vs-edits) — the three test files this step touches
- [Implementation](#implementation) — what each new test proves and where the gaps are today
- [Tests](#tests) — the test roster
- [Acceptance criteria](#acceptance-criteria) — observable pass/fail facts
- [References](#references) — background reading for the mechanisms under test
- [Applicable guardrails](#applicable-guardrails) — plan-level fences this step must respect
- [Deferred](#deferred) — what later steps in this plan build, not this one

## Why

Steps 2–9 move batch calls off `subprocess.run` and onto the shared streaming runner, and several of them describe themselves as "byte-compatible" with, or explicitly preserving, a behavior this step is supposed to have already pinned:

- Step 4's runner-initiated kill has to reach the same `ClaudeFailureKind.TIMEOUT` classification `subprocess.TimeoutExpired` reaches today via `plan_tool/shell.py:_run_once`'s `except subprocess.TimeoutExpired` handler — there is no test today that names that classification by value through a full `claude_invoke` call, only ones that check the externally-observable `(rc, stdout)` result.
- Step 6 has to replicate `_normalize_batch_stdout`'s final-text-wins-and-discards-the-preceding-chunks behavior against the runner's own already-parsed state, specifically because `launcher.py:_run_streaming_once`'s `stdout_buffer` joins every parsed text chunk unconditionally (`for chunk in parsed.text_chunks: stdout_buffer.append(chunk)`) and would duplicate the terminal `result` line's text if reused as-is. No test today drives more than one streamed `assistant` text chunk before the terminal `result` line through `claude_invoke`, so the "final_text alone, chunks discarded" rule the claude backend actually exercises is unverified.
- Step 5 adds a `backend_recovery_wait` run-log event to close the silent window between one attempt's end and the next attempt's start in the shared `plan_tool/rate_limit_loop.py:run_with_rate_limit_recovery` loop. That step needs an unambiguous before-state: today, on both the batch lane (`claude_invoke`) and the streaming lane (`launcher.py:shell_invoker`), a rate-limit `wait` or transient `sleep` between attempts produces no run-log record at all, on either side of the sleep. This is true for `run` as much as for `roadmap` — the loop and its `wait`/`sleep` seams are shared code (`plan_tool/rate_limit_loop.py`), and the plan's Overview only credits `run` with solving the *in-call* silence problem (via `_run_streaming_once`'s heartbeat), not this separate quiet window between calls.

Without this step, steps 2–6 would have to characterize old behavior retroactively while also changing it — the shape that produces an unverifiable diff and makes it hard to tell a deliberate change from an accidental regression.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `tests/test_shell.py` — add a case driving more than one streamed `assistant` text chunk plus a terminal `result` line through `shell.claude_invoke`, asserting the returned stdout is the `result` line's text alone (see `plan_tool/shell.py:_normalize_batch_stdout`). Confirm (not re-add — see Implementation) that the existing rate-limit and transient-retry tests already establish "one sink event per subprocess attempt, nothing extra for the wait/sleep itself" for the batch lane.
- `tests/test_roadmap.py` — add a case that drives `roadmap.run_roadmap` through the real `roadmap.shell_roadmap_invoker` (today every existing test passes a `_StubInvoker` instead, bypassing `shell_roadmap_invoker` and `claude_invoke` entirely), with `subprocess.run` mocked, and asserts what actually lands in the run log for one stage attempt: a `claude_call_start`, then a `claude_call_end` per internal `claude_invoke` attempt (which can outnumber the roadmap-level attempt when `claude_invoke` retries a rate limit internally), then nothing else — no `claude_call_progress`/`claude_call_stall_suspected` at any point. Add a second case that runs a stage attempt through a mocked `subprocess.TimeoutExpired`, asserting the roadmap-level outcome is `FAILURE_INVOKE` (see `plan_tool/roadmap.py:_run_stage`) with no same-budget retry inside `claude_invoke` itself.
- `tests/test_launcher.py` — add a case binding a real run-log recorder through `launcher._run_logger_var` and driving `launcher.shell_invoker` through a rate-limit-then-success sequence, asserting the recorder sees no `claude_call_progress`/`claude_call_stall_suspected` (or any other event) attributable to the wait window itself — only what each attempt's own `_run_streaming_once` call produces.

## Implementation

This step writes no production code. Its job is to make the current behavior of `plan_tool/shell.py`, `plan_tool/roadmap.py`, `plan_tool/launcher.py`, and `plan_tool/rate_limit_loop.py` explicit and green, so later steps have something concrete to diff against. Two of the three things the step intent names are already substantially pinned by the existing suite; the third has a real gap. Scope the new tests to what's actually missing rather than re-adding coverage that already exists — confirm the existing coverage explicitly in the Tests section instead.

**1. The `TimeoutExpired` → `TIMEOUT` classification path — mostly covered, confirm the gap.**

`tests/test_shell.py:test_claude_invoke_timeout_is_terminal_no_retry` already drives a mocked `subprocess.run` that raises `TimeoutExpired` through `claude_invoke` and asserts `(124, "")`, exactly one subprocess call (no same-budget retry), and no sleep. `tests/test_claude_errors.py` separately pins that `classify()` maps a `BACKEND_TIMEOUT_SENTINEL`-bearing stderr string to `ClaudeFailureKind.TIMEOUT` (`plan_tool/claude_errors.py:classify`). What's missing is a single test that goes through the whole path — `claude_invoke` → `_run_once` → `build_classification_from_outcome` (`plan_tool/claude_errors.py`) — and names `ClaudeFailureKind.TIMEOUT` by value, not just by its externally visible `(rc, stdout)` shape. This is what step 4 needs: proof that its runner-initiated kill reaches the *same classification*, not just the same `(124, "")` numbers.

**2. `_normalize_batch_stdout`'s collapse rule — real gap.**

`plan_tool/backend.py:_claude_parse_stream_line` appends an `assistant` line's text blocks to `text_chunks`, and separately appends the terminal `result` line's own `result` field to `text_chunks` too (plus a trailing newline) while also stashing it on `ClaudeRunStats.final_text`. In `plan_tool/shell.py:_normalize_batch_stdout`, `chunks` accumulates every line's `text_chunks` unconditionally, but the returned text is `final_text if final_text else "".join(chunks)` — when a terminal `result` line supplies `final_text`, everything else that was appended to `chunks`, *including the streamed assistant chunks and the result line's own duplicate append*, is discarded. `tests/test_shell.py`'s existing stream-json tests (`test_invoke_sink_captures_usage_from_stream_json`, `test_codex_batch_json_returns_final_agent_message`) don't exercise this: the claude-backend one sends only a bare terminal `result` line with no preceding `assistant` text, and the codex one exercises a structurally different collapse (codex's own `item.completed`/`agent_message` handling in `plan_tool/backend.py`'s codex parser, not the claude parser). Add a case with two or more `assistant` lines carrying distinct text, followed by a `result` line whose own `result` field is different text again, and assert `claude_invoke` returns only the `result` line's text — proving today's rule is "final_text alone," not "everything joined" and not "chunks joined, then final_text appended."

**3. The silent wait/sleep window — real gap, and it's about `run`, not `claude_invoke`.**

`tests/test_shell.py:test_claude_invoke_waits_then_retries_on_rate_limit` already asserts `len(recorded) == 2` for a rate-limited-then-successful call — one `ClaudeCallEnd` per subprocess attempt and nothing extra for the wait itself — so the batch lane's "no synthetic wait event" fact is already pinned; this step should say so explicitly rather than re-test it. What has no coverage at all is the streaming lane: no existing `shell_invoker` test binds a run-log recorder through `launcher._run_logger_var` while driving a rate-limit-then-success sequence, so nothing today shows what (if anything) lands in the run log during that wait. Two facts make this worth pinning here rather than leaving it to step 5: `launcher.py:shell_invoker` and `shell.py:claude_invoke` both hand `wait`/`sleep` closures straight to `plan_tool/rate_limit_loop.py:run_with_rate_limit_recovery`, and neither closure threads a run-logger reference — the only thing that reads `_run_logger_var` inside `shell_invoker`'s call is the per-attempt `_run_streaming_once` invocation, which starts and stops its heartbeat thread within that single attempt's scope. One way to test this: reuse the `_StreamRecordingLogger` fixture in `tests/test_launcher.py` (it already captures `claude_stream_event`/`claude_call_progress`/`claude_call_stall_suspected`), bind it via `launcher._run_logger_var.set`, and drive `shell_invoker` through the same rate-limited-then-success `_make_popen_factory` sequence `test_shell_invoker_waits_then_retries_on_rate_limit` already uses, then assert `progress_events == []` and `stall_events == []`. Pair it with a source- or spy-level check that the `run_logger` reference *is* reachable at each attempt (so the test proves "unused," not merely "out of scope") — one option is monkeypatching `_run_streaming_once` with a spy that records its `run_logger` kwarg on each of the two calls, the same technique `TestShellInvokerContextVarPlumbing` already uses.

For `roadmap`, the missing piece is different: no existing test drives `run_roadmap` through the real `shell_roadmap_invoker` at all (every `TestRunLog`/`TestInputsAndSeams` case injects `_StubInvoker`, which never touches `claude_invoke` or the shell sink). Add one case that does, with `subprocess.run` mocked to return a rate-limit banner then success, and read back `env.run_log_events()`. This is also where the "internal retry is invisible at the roadmap level" fact belongs: `roadmap.py:_run_stage`'s `bind_shell_sink(phase=phase, attempt=attempt)` wraps the *whole* `invoker(prompt)` call, so if `claude_invoke` retries internally on a rate limit, the roadmap-level run log gets two `claude_call_end` events — one per internal `claude_invoke` attempt — both carrying the *same* roadmap `attempt` number, for a single `claude_call_start`. That's worth asserting explicitly since it's the kind of thing an operator reading the JSONL could otherwise misread as a duplicate or a bug.

**Constraints to respect:**

- Don't write a test that implies today's batch calls have a heartbeat, stall marker, or silence kill — they don't. A test asserting the *absence* of `claude_call_progress`/`claude_call_stall_suspected` events for a roadmap batch call is exactly the right shape; a test written as if those events already fire (even to check their absence "for now") reads as scaffolding for step 7's feature landing early.
- Keep the new roadmap test hermetic the same way the rest of `tests/test_roadmap.py` is: mock `plan_tool.shell.subprocess.run` (or `shell.shutil.which`/`subprocess.run` together, matching `tests/test_shell.py`'s own `_fake_run_factory` pattern), not the real `claude`/`codex` binary. `tests/conftest.py`'s autouse guard will fail the test outright if a real backend binary gets spawned.
- The new `_normalize_batch_stdout` case and the new roadmap real-invoker case both exercise the claude backend's stream-json format directly (`type: "assistant"` / `type: "result"` NDJSON lines) — match the shape `tests/test_shell.py:test_invoke_sink_captures_usage_from_stream_json` and `tests/test_launcher.py`'s `_json_for_streaming_tests` helper already use rather than inventing a new fixture shape.

## Tests

### Tests for this step

- `test_claude_invoke_timeout_classifies_as_timeout_kind` (`tests/test_shell.py`) — drives a mocked `subprocess.run` raising `TimeoutExpired` through `claude_invoke` and asserts the failure that reaches the retry loop's classifier is `ClaudeFailureKind.TIMEOUT`, not just `(124, "")`.
- `test_normalize_batch_stdout_prefers_result_over_preceding_chunks` (`tests/test_shell.py`) — sends two or more claude `assistant` stream-json lines with distinct text, followed by a `result` line with its own distinct text, and asserts `claude_invoke` returns the `result` line's text alone.
- `test_roadmap_real_invoker_records_call_start_and_end_only` (`tests/test_roadmap.py`) — runs a stage through the real `shell_roadmap_invoker` (mocked `subprocess.run`) and asserts the run log carries `claude_call_start` then one `claude_call_end` per subprocess call, with no `claude_call_progress`/`claude_call_stall_suspected` event anywhere in the log.
- `test_roadmap_internal_rate_limit_retry_yields_two_call_end_events_under_one_start` (`tests/test_roadmap.py`) — same setup, with `subprocess.run` returning a rate-limit banner then success, asserting two `claude_call_end` events sharing one `claude_call_start`'s attempt number.
- `test_roadmap_configured_timeout_is_recorded_as_invoke_failure` (`tests/test_roadmap.py`) — same setup, with `subprocess.run` raising `TimeoutExpired`, asserting the stage attempt records `FAILURE_INVOKE` and `claude_invoke` did not retry under the same budget.
- `test_shell_invoker_rate_limit_wait_emits_no_progress_or_stall_event` (`tests/test_launcher.py`) — binds a run-log recorder via `launcher._run_logger_var`, drives `shell_invoker` through a rate-limited-then-successful `_make_popen_factory` sequence, and asserts no `claude_call_progress`/`claude_call_stall_suspected` event is attributable to the wait window.

Every test above must be green before this step is done. This step's entire deliverable is these characterization tests — there is no production-code change to gate them on.

## Acceptance criteria

- `uv run pytest tests/test_shell.py tests/test_roadmap.py tests/test_launcher.py -q` passes with the new tests included, with no change to any file outside those three.
- A test names `ClaudeFailureKind.TIMEOUT` explicitly for a `claude_invoke` call that hits a configured timeout, not only its `(rc, stdout)` shape.
- A test proves `claude_invoke` returns only the terminal `result` line's text when one or more streamed `assistant` chunks preceded it.
- A test drives `roadmap.run_roadmap` through the real `shell_roadmap_invoker` (not `_StubInvoker`) at least once, with a mocked subprocess, and inspects the resulting run-log JSONL.
- A test shows a `shell_invoker` rate-limit wait produces no run-log event beyond what each attempt's own `_run_streaming_once` call already produces.
- No test in the new roster spawns a real `claude`/`codex` binary (`tests/conftest.py`'s allow-real-backend guard stays untripped).

## References

- [subprocess — Subprocess management (Python 3.13)](https://docs.python.org/3/library/subprocess.html) — `TimeoutExpired` semantics and `subprocess.run(timeout=...)`'s kill-then-raise behavior, which `plan_tool/shell.py:_run_once` catches to build the synthetic timeout outcome this step pins.
- [Streaming Messages — Claude API](https://docs.anthropic.com/en/api/messages-streaming) — background on why a terminal envelope (the claude backend's `result` line) is distinct from the incremental content events that precede it, relevant to the `_normalize_batch_stdout` collapse-rule test.
- [JSON Lines specification](https://jsonlines.org/) — the one-JSON-value-per-line format the new test fixtures (multi-line `assistant`/`result` NDJSON strings) must satisfy to parse the same way `plan_tool/backend.py:_claude_parse_stream_line` parses real backend output.

## Applicable guardrails

- **Out of scope — the silence-based kill is a distinct, not-yet-built mechanism.** The plan's "## Out of scope" is explicit that the new silence-based kill must not be described or implemented as part of this plan's earlier steps, and that `run`'s exemption from `PLAN_TOOL_CLAUDE_TIMEOUT`/`scoped_claude_timeout` stays as-is. This step's tests characterize only what exists today (a configured-timeout kill on the batch path, no timeout enforcement at all on the streaming path, no heartbeat/stall/silence-kill on the batch path) — none of the new tests may assert or assume the future silence kill, stall marker, or streaming-side configured-timeout enforcement exists yet.

## Deferred

- Building the heartbeat/stall/silence-kill mechanism for batch calls — steps 2–4's job; this step only proves it doesn't exist yet.
- The `backend_recovery_wait` event and any other new run-log event type — step 5 adds these; this step proves the window they'll fill is currently silent.
- Re-testing `_run_streaming_once`'s in-call heartbeat/stall/kill ladder itself — already covered by the existing `TestRunStreamingOnceStreamJson`/kill-ladder tests in `tests/test_launcher.py`; this step adds only the outer wait-window characterization, not a second pass over that mechanism.
- Any change to `claude_invoke`'s `(rc, stdout)` contract, `_run_once`, or `_normalize_batch_stdout` — production code is untouched this step; step 6 is where `_run_once`/`_normalize_batch_stdout` are eventually deleted.
