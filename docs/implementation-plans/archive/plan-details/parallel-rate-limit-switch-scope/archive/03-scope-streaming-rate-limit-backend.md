> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Scope Streaming Rate-Limit Backend Switches to the Current Invoke

## Summary

This step changes streaming rate-limit backend switching in `plan_tool/launcher.py` so a fallback backend selected during one `shell_invoker` call is scoped to that call and restored afterward. The primary files are `plan_tool/launcher.py` and `tests/test_launcher.py`. The key design decision is to consume the scoped active-backend helper from step 1 across the streaming retry loop, instead of mutating the process-wide active backend through `select_active_backend`. On green, a streaming run can retry on the fallback backend after a rate limit without changing the backend seen by later `shell_invoker` calls, sibling threads, or `run_step` status handling.

## Table of Contents

- [Summary](#summary) — The short version of the streaming switch scoping change.
- [Why](#why) — The backend leak this step fixes in the run path.
- [Input](#input) — The upstream scoped-backend contract and launcher seams this step consumes.
- [Files creates vs edits](#files-creates-vs-edits) — The files this step changes and what belongs in each.
- [Implementation](#implementation) — The intended behavior, recommended wiring, and constraints.
- [Tests](#tests) — The regression cases to add or update.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for completion.
- [References](#references) — Primary docs for scoped context, subprocesses, and monkeypatch testing.
- [Deferred](#deferred) — Related work that stays outside this step.

## Why

`plan_tool/launcher.py:_select_rate_limit_backend` currently switches the active backend through the same process-wide selection path used by CLI startup. In the streaming path, `plan_tool/launcher.py:shell_invoker` catches a rate limit, calls that selector, and then the next `plan_tool/launcher.py:_run_streaming_once` attempt reads `get_active_backend()` later when building its `Popen` transport. That works for a single call, but it can clobber the active backend for unrelated streaming work in the same process. Step 1 provides scoped backend selection, so this step applies it to the streaming retry path only.

## Input

- **Step 1 outcome:** step 1 provides a scoped active-backend helper in `plan_tool/backend.py` while preserving `get_active_backend`, `set_active_backend`, and `select_active_backend` for existing global selection.
- **Streaming retry seam:** `plan_tool/launcher.py:shell_invoker` owns the rate-limit and transient retry loop for `plan-tool run`.
- **Selection seam:** `plan_tool/launcher.py:_select_rate_limit_backend` is reached from both `OnRateLimitAction.SWITCH` policy handling and the interactive menu path in `plan_tool/launcher.py:_ask_rate_limit_action`.
- **Backend consumer:** `plan_tool/launcher.py:_run_streaming_once` reads `get_active_backend()` when it builds the active backend's streaming transport and parses stream lines.
- **Repo-root selection context:** fallback selection still needs project override lookup rooted at `get_active_spawn_cwd()` when available, otherwise `Path.cwd()`.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/launcher.py` — Scope successful streaming rate-limit backend switches to the current `shell_invoker` call, keep retry behavior and diagnostics unchanged, and stop using lasting process-wide mutation for streaming recovery.
  - `tests/test_launcher.py` — Update existing `shell_invoker` switch tests and add regressions for restore after success, restore after fallback rate-limit failure, failed-switch no-install behavior, and parallel invoke isolation.

## Implementation

- **Foundational logic:** current-invoke scoped backend switch for streaming rate-limit recovery.

- **Use the step 1 helper as the boundary.** `plan_tool/launcher.py` should import and use the scoped active-backend API produced by step 1. Do not redesign backend selection here. If the step 1 helper cannot select the same effective backend that `select_active_backend(name, repo_root=...)` selects today, treat that as a step 1 contract gap.

- **Keep the scope alive across the retry.** The scoped backend must be active while the later `_run_streaming_once` attempt runs, because `_run_streaming_once` is where `get_active_backend()` is read. Do not enter and exit the scoped helper entirely inside `plan_tool/launcher.py:_select_rate_limit_backend`; that restores too early and the retry will not see the fallback.

- **Let `shell_invoker` own the lifetime.** One likely approach is for `plan_tool/launcher.py:_select_rate_limit_backend` to return enough information for `plan_tool/launcher.py:shell_invoker` to install the scoped backend and keep the context open until `shell_invoker` returns. An `ExitStack` or a small held context object are both reasonable. The invariant matters more than the exact shape: every retry attempt caused by this one invoke sees the selected fallback, and the original active backend is restored on every return path.

- **Install only after a successful switch.** Failed, missing, bogus, or same-backend fallback choices should keep the current degradation behavior: notify, wait, and retry without installing scoped backend state. `plan_tool/launcher.py:_select_rate_limit_backend` currently catches `BackendConfigError` and `ValueError`; preserve that user-facing path.

- **Preserve same-backend protection.** `plan_tool/launcher.py:shell_invoker` already checks `policy.fallback_backend == get_active_backend().name` before switching, and `plan_tool/launcher.py:_ask_rate_limit_action` rejects interactive switches to the current backend. Keep those guards so a fallback that names the active backend still waits instead of resetting retry guards forever.

- **Preserve retry counters.** Successful switch handling should still reset `rate_limit_retried`, reset `transient_attempts`, increment `current_attempt`, and continue. Bad fallback handling should still degrade to wait. A fallback that also rate-limits should stay bounded by the existing "already retried once" logic.

- **Keep run-step plumbing unchanged.** `plan_tool/launcher.py:run_step` sets `_run_logger_var` around `invoker(prompt)` and reads `shell_invoker._last_stats` after the call. This step should not widen the `Invoker` signature or move run-log behavior. The backend scope should sit inside the production `shell_invoker` retry loop, not around `run_step` broadly.

- **Keep streaming subprocess behavior unchanged.** `plan_tool/launcher.py:_run_streaming_once` should continue to build `backend.streaming_transport(prompt)`, pass `cwd=get_active_spawn_cwd()` to `subprocess.Popen`, and parse stream lines through the active backend. The only behavior change is which active backend is visible during fallback retry attempts and when it is restored.

- **Mirror the batch path conceptually, not by moving code.** `plan_tool/shell.py:claude_invoke` is the sibling batch path covered by step 2. This step should keep launcher-specific progress, streaming stats, and `shell_invoker._last_stats` behavior local to `plan_tool/launcher.py`.

## Tests

- `test_shell_invoker_rate_limit_menu_switch_scoped_to_call` — interactive SWITCH retries on the fallback backend and `get_active_backend()` is restored after `shell_invoker` returns.
- `test_shell_invoker_switch_policy_scoped_to_call` — noninteractive SWITCH policy retries on the fallback backend without prompting and restores the original backend afterward.
- `test_shell_invoker_switch_policy_restores_when_fallback_also_rate_limited` — fallback selection is restored even when the fallback attempt also rate-limits and the invoke returns a failure.
- `test_shell_invoker_switch_policy_bad_fallback_does_not_install_scope` — a bad fallback still degrades to wait and never leaves a scoped fallback active.
- `test_shell_invoker_parallel_switches_do_not_clobber_sibling_backend` — two concurrent `shell_invoker` calls can switch or retry independently without one call's fallback changing what the other call sees.
- `test_shell_invoker_rate_limit_switch_resets_wait_budget` — existing wait-budget reset behavior remains intact after the scoped switch change.

### Test-creation order (feature step)

This is a **feature** step — new behavior. Add or update the focused `tests/test_launcher.py` switch tests with the implementation, and keep the existing success, bad fallback, same-backend, and wait-budget tests green. The green-before-done gate is: every new regression above passes, and the existing `shell_invoker` retry tests still pass.

## Acceptance criteria

- `plan_tool/launcher.py:shell_invoker` retries a streaming rate-limited call on the selected fallback backend.
- `plan_tool/launcher.py:shell_invoker` restores the original active backend after a successful fallback retry.
- `plan_tool/launcher.py:shell_invoker` restores the original active backend after a fallback retry returns rate-limited or otherwise fails.
- Failed fallback selection does not install scoped backend state.
- Interactive SWITCH and configured `OnRateLimitAction.SWITCH` use the same scoped restore behavior.
- `plan_tool/launcher.py:_run_streaming_once` still reads the active backend for each subprocess attempt and still uses `get_active_spawn_cwd()` for `cwd`.
- `tests/test_launcher.py` passes for the `shell_invoker` switch and retry cases.

## References

- [Python contextvars — Context Variables](https://docs.python.org/3/library/contextvars.html) — Read for scoped state that avoids leaking values across concurrent execution.
- [Python threading — Thread-local Data](https://docs.python.org/3/library/threading.html#thread-local-data) — Read when comparing worker-local state with process-wide globals in parallel tests.
- [Python subprocess — Popen Constructor](https://docs.python.org/3/library/subprocess.html#popen-constructor) — Read for the streaming subprocess spawn contract that `_run_streaming_once` must preserve.
- [Python concurrent.futures — ThreadPoolExecutor](https://docs.python.org/3/library/concurrent.futures.html#threadpoolexecutor) — Read for parallel worker behavior used to reproduce backend leakage.
- [pytest — How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Read for patching launcher selectors, subprocess spawns, and backend state in tests.
- [Claude Platform Docs — Rate limits](https://platform.claude.com/docs/en/api/rate-limits) — Read for 429 and reset semantics that explain why fallback retry behavior exists.

## Deferred

- `plan_tool/shell.py` batch switching — owned by step 2; this step should not edit the batch `claude_invoke` path.
- `plan_tool/backend.py` scoped helper design — owned by step 1; this step consumes the helper and should not change its contract.
- Run-log schema or event changes — backend scoping should not add persisted fields or change `ClaudeCallEnd`.
- Prompt-budget advisory behavior — `plan_tool/launcher.py:run_step` prompt-budget warning and telemetry are unrelated to rate-limit backend scope.
