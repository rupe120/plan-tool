> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Scope Streaming Rate-Limit Backend Switches to the Current Invoke

## Summary

This step changes streaming rate-limit backend switching in `plan_tool/launcher.py` so a fallback backend selected during one `shell_invoker` call is visible to that retry loop only. The primary files are `plan_tool/launcher.py` and `tests/test_launcher.py`. The key design decision is to consume `plan_tool/backend.py:scoped_select_active_backend` across `shell_invoker`'s retry lifetime, rather than using `select_active_backend` as a lasting process-wide switch. On green, a streaming invoke can retry on the fallback backend after a rate limit, then restore the original active backend for later invokes and sibling work.

## Table of Contents

- [Summary](#summary) — The short version of the streaming switch scoping change.
- [Why](#why) — The backend leak this step fixes in the streaming path.
- [Input](#input) — The upstream scoped-backend contract and launcher seams this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The files this step changes and what belongs in each.
- [Implementation](#implementation) — The required behavior, recommended wiring, and constraints.
- [Tests](#tests) — The launcher regressions to add or update.
- [Test-creation order (feature step)](#test-creation-order-feature-step) — The order to add tests with the implementation.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for completion.
- [References](#references) — Primary docs for scoped context, subprocesses, and monkeypatch testing.
- [Deferred](#deferred) — Related work that stays outside this step.

## Why

`plan_tool/launcher.py:_select_rate_limit_backend` currently reaches `plan_tool.backend:select_active_backend`, which activates the fallback backend as process-wide state. In the streaming path, `plan_tool/launcher.py:shell_invoker` catches a rate limit, calls that selector from either the `OnRateLimitAction.SWITCH` policy branch or the interactive `plan_tool/launcher.py:_ask_rate_limit_action` menu path, then retries through `plan_tool/launcher.py:_run_streaming_once`, which reads `get_active_backend()` later when it builds the streaming transport and parses stream lines. That lets one run recover, but it can leave the fallback active for later `shell_invoker` calls, sibling workers, or unrelated callers in the same process.

## Input

- **Step 2 outcome:** step 2 adds `plan_tool/backend.py:scoped_select_active_backend(name, *, repo_root, model=None, fallback_factory=None)` while preserving `get_active_backend`, `set_active_backend`, and `select_active_backend` as the global fallback and selection APIs.
- **Streaming retry seam:** `plan_tool/launcher.py:shell_invoker` owns the rate-limit retry loop for run-path streaming calls.
- **Selection seam:** `plan_tool/launcher.py:_select_rate_limit_backend` is reached from both the noninteractive `OnRateLimitAction.SWITCH` branch and the interactive `OnRateLimitAskResult.action` / `.switch_backend_name` returned by `plan_tool.claude_errors:ask_on_rate_limit_action`.
- **Backend consumer:** `plan_tool/launcher.py:_run_streaming_once` reads `get_active_backend()` when it builds `backend.streaming_transport(prompt)` and again when parsing stream lines.
- **Repo-root selection context:** fallback selection still needs project override lookup rooted at `get_active_spawn_cwd()` when available, otherwise `Path.cwd()`.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/launcher.py` — Scope successful streaming rate-limit backend switches to the current `shell_invoker` call, keep retry behavior and diagnostics the same, and stop using lasting process-wide mutation for streaming recovery.
  - `tests/test_launcher.py` — Update existing `shell_invoker` switch tests and add regressions for restoration after success, restoration after fallback rate-limit failure, failed-switch no-install behavior, interactive switch restoration, and parallel invoke isolation.

## Implementation

- **Foundational logic:** current-invoke scoped backend switch for streaming rate-limit recovery.

- **Own the scope in `shell_invoker`.** Keep the scoped fallback active across the later `_run_streaming_once` retry attempt, because `_run_streaming_once` reads `get_active_backend()` after `_select_rate_limit_backend` returns. A scope opened and closed inside `_select_rate_limit_backend` is too short-lived.

- **Use step 2's scoped helper.** Import and call `scoped_select_active_backend(name, *, repo_root, model=None, fallback_factory=None)` from `plan_tool/backend.py`. Do not reimplement backend name lookup, `.plan-tool/backends.json` override loading, model resolution, or effective-backend construction in `plan_tool/launcher.py`.

- **Change `_select_rate_limit_backend` from “mutate globally” to “validate and prepare a scoped switch.”** One likely shape is for `plan_tool/launcher.py:_select_rate_limit_backend` to return the context manager from `scoped_select_active_backend(...)` so `shell_invoker` can keep it open, while returning a falsy value on `BackendConfigError` or `ValueError` so the existing wait fallback stays intact. The selector must not leave process-wide state changed after a successful selection.

- **Install only after success.** Failed, missing, misconfigured, or already-active fallback choices should leave no scoped override behind. The existing “degrade to waiting” behavior in `plan_tool/launcher.py:shell_invoker` should remain the path for failed switches.

- **Cover both switch paths.** Update the `OnRateLimitAction.SWITCH` policy branch in `plan_tool/launcher.py:shell_invoker` and the interactive branch through `plan_tool/launcher.py:_ask_rate_limit_action`. Both must keep the scoped backend active until the retry attempt that follows the switch has consumed it.

- **Preserve retry guards.** Keep the current one-shot wait/retry behavior: `rate_limit_retried`, `transient_attempts`, and `current_attempt` still reset when a switch succeeds, and the already-active fallback check still prevents a hot loop.

- **Keep process-wide selection APIs intact.** `plan_tool/backend.py:select_active_backend` remains the persistent selection API for CLI startup and other global selection callers. This step should not edit `plan_tool/backend.py`; if `scoped_select_active_backend(name, *, repo_root, model=None, fallback_factory=None)` cannot select the same effective backend shape as `select_active_backend(name, repo_root=...)`, treat that as a step 2 contract gap.

- **Keep streaming subprocess behavior unchanged.** `plan_tool/launcher.py:_run_streaming_once` should still use `backend.streaming_transport(prompt)`, pass `cwd=get_active_spawn_cwd()` to `subprocess.Popen`, support stdin prompt transport, and parse stream lines through the active backend. The only intended behavior change is which active backend is visible during a switched retry and when that visibility ends.

- **Propagate scoped backend state to stdout parsing.** If stream stdout is pumped or parsed in a helper thread such as `plan_tool/launcher.py:_run_streaming_once._pump_stdout`, that thread must capture or run under the same scoped backend context as the switched retry. The fallback backend must be visible both when building `backend.streaming_transport(prompt)` and when parsing stream lines.

- **Respect the prompt lock.** `RATE_LIMIT_PROMPT_LOCK` still protects the switch decision, interactive prompt, and wait path. Do not widen this step into a redesign of the lock or the parallel prompt UX.

## Tests

- `test_shell_invoker_rate_limit_menu_switch_reselects_backend` — update to assert the retry attempt uses the fallback backend for both streaming transport setup and stream-line parsing, and `get_active_backend()` is restored after `shell_invoker` returns.
- `test_shell_invoker_switch_policy_switches_without_prompt` — update to assert the noninteractive switch retries on the fallback backend for both streaming transport setup and stream-line parsing without prompting, and restores the original active backend afterward.
- `test_shell_invoker_switch_policy_degrades_to_wait_when_fallback_bad` — assert a failed fallback selection does not install a scoped backend and the wait retry still uses the original backend.
- `test_shell_invoker_switch_to_active_backend_does_not_hot_loop` — keep the no-self-switch behavior and assert no scoped override is installed for an already-active fallback.
- `test_shell_invoker_rate_limit_switch_resets_wait_budget` — assert the switched backend remains visible for the post-switch rate-limit attempt and the original backend is restored after the later wait retry completes.
- `test_shell_invoker_switch_policy_restores_after_fallback_rate_limit` — add coverage where the fallback retry also rate-limits and `shell_invoker` returns failure with the original backend restored.
- `test_shell_invoker_parallel_switches_are_isolated` — add deterministic overlap coverage with `threading.Barrier` or `threading.Event`, capturing backend names seen inside each retry and after each call.

### Test-creation order (feature step)

1. Update `tests/test_launcher.py:test_shell_invoker_rate_limit_menu_switch_reselects_backend` with per-attempt backend capture for transport setup and stream-line parsing plus post-return restoration. This should fail until the interactive path owns the scoped fallback across the retry and any stdout pump thread sees that context.
2. Update `tests/test_launcher.py:test_shell_invoker_switch_policy_switches_without_prompt` with the same retry/backend/parsing/restoration assertions for the policy path.
3. Add `tests/test_launcher.py:test_shell_invoker_switch_policy_restores_after_fallback_rate_limit` to prove cleanup happens on terminal fallback failure, not only on success.
4. Strengthen `tests/test_launcher.py:test_shell_invoker_switch_policy_degrades_to_wait_when_fallback_bad` and `tests/test_launcher.py:test_shell_invoker_switch_to_active_backend_does_not_hot_loop` so failed or no-op switches leave no scoped state.
5. Add `tests/test_launcher.py:test_shell_invoker_parallel_switches_are_isolated` using explicit barriers/events rather than sleeps, so overlapping invokers cannot see each other's fallback backend.
6. The green-before-done gate is the full `tests/test_launcher.py` launcher subset with every new or changed switch test passing.

## Acceptance criteria

- `plan_tool/launcher.py:shell_invoker` retries a streaming rate-limit failure on the configured fallback backend when `OnRateLimitAction.SWITCH` succeeds.
- `plan_tool/launcher.py:shell_invoker` retries on an interactively selected fallback backend when `ask_on_rate_limit_action` returns `OnRateLimitAskResult` with `.action == OnRateLimitAction.SWITCH` and `.switch_backend_name` set.
- `plan_tool/launcher.py:_run_streaming_once` parses fallback retry stream lines under the same scoped fallback backend, including any stdout pump thread used by `_pump_stdout`.
- `plan_tool/backend.py:get_active_backend` returns the original active backend after `shell_invoker` returns from a switched retry, whether the retry succeeds or fails.
- Failed fallback selection in `plan_tool/launcher.py:_select_rate_limit_backend` degrades to the existing wait path without installing a scoped backend.
- A fallback backend that is already active does not self-switch, does not hot-loop, and leaves active backend state unchanged.
- Overlapping `shell_invoker` calls can switch to different fallback backends without either call changing the backend seen by the other after its own scope ends.
- `pytest tests/test_launcher.py` passes for the launcher rate-limit and streaming transport tests.

## References

- [Python contextvars — Context Variables](https://docs.python.org/3/library/contextvars.html) — Read for the scoped state behavior step 2 exposes and this step consumes.
- [Python subprocess — Popen Constructor](https://docs.python.org/3/library/subprocess.html#popen-constructor) — Read for the streaming subprocess boundary in `plan_tool/launcher.py:_run_streaming_once`.
- [Python concurrent.futures — ThreadPoolExecutor](https://docs.python.org/3/library/concurrent.futures.html#threadpoolexecutor) — Read for thread-pool overlap semantics relevant to leakage regressions.
- [pytest — How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Read for the monkeypatch style used by `tests/test_launcher.py`.
- [Claude Platform Docs — Rate limits](https://platform.claude.com/docs/en/api/rate-limits) — Read for the external rate-limit behavior that motivates retry and fallback semantics.

## Deferred

- `plan_tool/shell.py` batch switching — owned by the batch rate-limit switch step; this step only changes the streaming launcher path.
- `plan_tool/backend.py:scoped_select_active_backend` design — owned by step 2; this step consumes that helper and should not add a second selection implementation.
- `tests/cli/test_completeness_apply_parallel.py` parallel apply coverage — belongs to the downstream parallel leakage coverage step that exercises worker fan-out and replay boundaries.
- Operator and maintainer docs — handled by the later documentation step after both batch and streaming scoped-switch behavior are implemented.
