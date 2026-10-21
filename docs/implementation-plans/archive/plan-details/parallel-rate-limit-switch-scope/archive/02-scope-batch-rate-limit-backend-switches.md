> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Scope Batch Rate-Limit Backend Switches to the Current Invoke

## Summary

This step changes batch rate-limit backend switching in `plan_tool/shell.py` so a fallback backend selected during one `claude_invoke` call is scoped to that call and restored afterward. The main design decision is to consume the scoped active-backend helper produced by step 1 instead of calling the process-wide `select_active_backend` path from the batch retry loop. `tests/test_shell.py` should keep the current retry and switch behavior green while adding focused regressions for restore, parallel isolation, and failed-switch fallback. On green, a rate-limited batch invoke can retry on the fallback backend without changing the backend seen by sibling invokes or later calls.

## Table of Contents

- [Summary](#summary) — The short version of the batch switch scoping change.
- [Why](#why) — The process-wide backend leak this step fixes.
- [Input](#input) — The upstream scoped-backend contract this step consumes.
- [Files creates vs edits](#files-creates-vs-edits) — The files this step changes and what belongs in each.
- [Implementation](#implementation) — The intended behavior, recommended wiring, and invariants to preserve.
- [Tests](#tests) — The regression cases to add or update.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for completion.
- [References](#references) — Primary docs for scoped context and monkeypatch testing.
- [Deferred](#deferred) — Similar streaming work and helper redesign that stay out of this step.

## Why

`plan_tool/shell.py:_select_rate_limit_backend` currently switches the active backend through the process-wide backend selection path, so a batch `claude_invoke` that recovers from a rate limit by switching to a fallback backend can change what unrelated work in the same process sees. That is unsafe for parallel detail/review/create work because every batch caller funnels through `plan_tool/shell.py:claude_invoke`, and the retry loop reads the active backend again through `plan_tool/shell.py:_run_once`. Step 1 provides the scoped active-backend primitive; this step applies it to the batch rate-limit recovery path only.

## Input

- **Step 1 outcome:** step 1 provides a scoped active-backend helper in `plan_tool/backend.py` while preserving the global `get_active_backend`, `set_active_backend`, and `select_active_backend` behavior for existing callers.
- **Batch send seam:** `plan_tool/shell.py:claude_invoke` owns the batch retry loop and calls `plan_tool/shell.py:_run_once`, which reads `plan_tool.backend.get_active_backend` for each subprocess attempt.
- **Current switch seam:** `plan_tool/shell.py:_select_rate_limit_backend` is the batch helper reached from both `OnRateLimitAction.SWITCH` policy handling and the interactive switch path in `plan_tool/shell.py:_ask_rate_limit_action`.
- **Selection config:** fallback backend selection still needs the same project override behavior currently reached through `select_active_backend(name, repo_root=...)`, with `repo_root` based on `get_active_spawn_cwd()` when available.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/shell.py` — Scope successful rate-limit backend switches to the current `claude_invoke` call, keep retry behavior and diagnostics unchanged, and stop using a process-wide backend mutation for batch recovery.
  - `tests/test_shell.py` — Update switch tests that currently monkeypatch `select_active_backend`, and add regressions for restore after success, restore after terminal fallback rate limit, failed-switch wait behavior, and parallel invoke isolation.

## Implementation

- **Foundational logic:** current-invoke scoped backend switch for batch rate-limit recovery.

- **Use the step 1 helper as the boundary:** Import and use the scoped active-backend API produced by step 1 from `plan_tool/backend.py`. Do not redesign backend selection in this step; if the step 1 helper cannot build the same effective backend that `select_active_backend` builds today, treat that as a step 1 contract gap rather than adding new backend APIs from `plan_tool/shell.py`.

- **Keep the scope open for the retry:** The scoped backend must remain active for the subprocess attempt that follows the switch. A context entered and exited entirely inside `plan_tool/shell.py:_select_rate_limit_backend` restores too soon because `plan_tool/shell.py:_run_once` reads `get_active_backend()` later in the `claude_invoke` loop.

- **Recommended shape:** Let `plan_tool/shell.py:claude_invoke` own the lifetime of any scoped backend switch for that invoke. One way is to keep an `ExitStack` or equivalent token holder around the retry loop, and have `plan_tool/shell.py:_select_rate_limit_backend` enter the scoped backend selection into that holder only after successful selection. The exact plumbing can vary, but cleanup must happen in a `finally` tied to the `claude_invoke` call.

- **Preserve existing retry semantics:** A successful switch still resets `rate_limit_retried`, resets `transient_attempts`, increments `current_attempt`, and retries immediately. A fallback backend that is missing, misconfigured, or already active still degrades to the wait path and must not install any scoped backend.

- **Preserve project overrides:** The fallback backend used inside the scoped call must include the same `.plan-tool/backends.json` extra argv/model behavior that the current `select_active_backend(name, repo_root=...)` call applies. Keep `repo_root = get_active_spawn_cwd() or Path.cwd()` as the selection root unless step 1 exposed a stricter equivalent.

- **Do not mutate the process-wide active backend on recovery:** After this step, `plan_tool/shell.py:_select_rate_limit_backend` should not make a successful batch recovery by leaving `select_active_backend`'s global activation in place. Existing CLI startup and tests that call `plan_tool/backend.py:select_active_backend` directly are not part of this step.

- **Keep same-backend detection scoped:** The `already_active` checks in `plan_tool/shell.py:claude_invoke` and `plan_tool/shell.py:_ask_rate_limit_action` should continue to compare against `get_active_backend().name`. Inside a scoped retry, that should see the fallback backend; outside the invoke, it should see the caller's original backend.

- **Keep observability unchanged:** `plan_tool/shell.py:_run_once` should continue to read the active backend for each subprocess attempt, so the first attempt uses the original backend and the switched retry uses the fallback backend. `plan_tool/shell.py:_maybe_warn_shell_prompt_budget` still runs before the retry loop with the initially active backend, and `plan_tool/shell.py:_emit_call_end` should keep its existing fields unchanged.

- **Respect existing serialization:** Keep `RATE_LIMIT_PROMPT_LOCK` around the switch/menu/wait decision in `plan_tool/shell.py:claude_invoke`. The lock still protects terminal prompting; the scoped backend helper handles backend isolation.

## Tests

- `test_claude_invoke_rate_limit_menu_switches_backend_and_retries` — update to assert the retry uses the switched backend without leaving the fallback globally active after `claude_invoke` returns.
- `test_claude_invoke_switch_policy_switches_backend_without_prompt` — update to assert noninteractive `SWITCH` retries on the fallback backend and restores the original active backend afterward.
- `test_claude_invoke_switch_policy_restores_backend_when_fallback_also_rate_limited` — add coverage that a fallback backend that also rate-limits stays active only inside the current invoke and is restored after the bounded retry returns.
- `test_claude_invoke_switch_policy_degrades_to_wait_when_fallback_bad` — keep or update coverage that failed fallback selection waits and does not install a scoped backend.
- `test_parallel_rate_limit_switches_do_not_clobber_sibling_invokes` — add a thread-based regression where two workers recover with different or staggered backend state and each worker's subprocess attempts see only its own scoped backend.
- `test_interactive_switch_scope_does_not_leak_to_later_invoke` — add coverage for the `ASK`/menu switch path proving a later direct `claude_invoke` starts on the original active backend.

### Test-creation order (feature step)

1. Update the existing switch tests in `tests/test_shell.py` so they fail against process-wide leaking behavior and still pin the current argv/retry shape.
2. Add the restore-after-return tests for both automatic `SWITCH` policy and interactive menu switching.
3. Add the fallback-also-rate-limited bounded retry test with a final assertion that the original backend is active after return.
4. Add the parallel isolation test last, after the simpler lifetime tests are green.

Every new and updated test in `tests/test_shell.py` must be green before this step is considered finished.

## Acceptance criteria

- A batch `claude_invoke` that rate-limits, switches to a fallback backend, and succeeds returns the fallback backend's stdout while `get_active_backend()` is restored to the pre-invoke backend after return.
- A batch `claude_invoke` whose fallback backend also rate-limits remains bounded and restores the pre-invoke backend after returning the terminal rate-limited result.
- A failed fallback selection still degrades to the existing wait-and-retry path and does not install a scoped backend.
- Existing missing-executable, transient retry, wait-on-rate-limit, prompt-budget backstop, and `ClaudeCallEnd` sink tests in `tests/test_shell.py` still pass.
- Parallel batch invokes that switch backends during rate-limit recovery do not change each other's active backend or the backend seen by later invokes in the main thread.

## References

- [Python contextvars — Context Variables](https://docs.python.org/3/library/contextvars.html) — Read for scoped state behavior across concurrent execution.
- [Python threading — Thread-local Data](https://docs.python.org/3/library/threading.html#thread-local-data) — Useful comparison point for worker-local state and why process-wide backend switches leak.
- [Python subprocess — Popen Constructor](https://docs.python.org/3/library/subprocess.html#popen-constructor) — Confirms subprocess invocation reads the command/cwd selected at the call site.
- [pytest — How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Covers the monkeypatch patterns used by `tests/test_shell.py`.

## Deferred

- `plan_tool/launcher.py:_select_rate_limit_backend` — The streaming run path has the same process-wide switch risk, but it is outside this step's declared files and should be handled by the later launcher step.
- `plan_tool/backend.py` scoped-helper redesign — If step 1's helper cannot scope an effective backend with project overrides, fix that in the step 1 backend work rather than expanding this batch wiring step.
- Wrapper-level suppression or prompt-budget changes — `plan_tool/shell.py:suppress_prompt_budget_backstop` and `_maybe_warn_shell_prompt_budget` are unrelated to backend switch scope and should remain behaviorally unchanged here.
