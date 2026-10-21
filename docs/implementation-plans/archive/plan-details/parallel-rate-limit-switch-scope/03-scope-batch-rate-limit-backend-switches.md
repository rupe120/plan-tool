> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Scope Batch Rate-Limit Backend Switches to the Current Invoke

## Summary

This step changes batch rate-limit backend switching in `plan_tool/shell.py` so a fallback backend selected during one `claude_invoke` call is scoped to that call and restored afterward. The primary files are `plan_tool/shell.py` and `tests/test_shell.py`. The key design decision is to consume `plan_tool/backend.py:scoped_select_active_backend` across the batch retry loop, instead of mutating the process-wide active backend through `select_active_backend`. On green, a batch invoke can retry on the fallback backend after a rate limit without changing the backend seen by later batch calls, sibling threads, or other callers in the same process.

## Table of Contents

- [Summary](#summary) — The short version of the batch switch scoping change.
- [Why](#why) — The backend leak this step fixes in the batch path.
- [Input](#input) — The upstream scoped-backend contract and shell seams this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The files this step changes and what belongs in each.
- [Implementation](#implementation) — The intended behavior, recommended wiring, and constraints.
- [Tests](#tests) — The regression cases to add or update.
- [Test-creation order (feature step)](#test-creation-order-feature-step) — The order to add tests with the implementation.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for completion.
- [References](#references) — Primary docs for scoped context, subprocesses, and monkeypatch testing.
- [Deferred](#deferred) — Related work that stays outside this step.

## Why

`plan_tool/shell.py:_select_rate_limit_backend` currently reaches `plan_tool.backend:select_active_backend`, which activates the fallback backend as process-wide state. In the batch retry path, `plan_tool/shell.py:claude_invoke` catches a rate limit, calls that selector from either the `OnRateLimitAction.SWITCH` policy branch or the interactive `plan_tool/shell.py:_ask_rate_limit_action` menu path, then retries through `plan_tool/shell.py:_run_once`, which reads `get_active_backend()` later. That lets one batch call recover, but it can leave the fallback active for unrelated later calls or sibling work in the same process. Step 2 provides the scoped backend helper needed to keep the fallback visible only while the current `claude_invoke` retry loop is still running.

## Input

- **Step 2 outcome:** step 2 adds `plan_tool/backend.py:scoped_select_active_backend(name, *, repo_root, model=None, fallback_factory=None)` while keeping `get_active_backend`, `set_active_backend`, and `select_active_backend` as the process-wide fallback and selection APIs.
- **Batch retry seam:** `plan_tool/shell.py:claude_invoke` owns the rate-limit retry loop for batch callers such as create, review, detail, jira, lessons, and annotate.
- **Selection seam:** `plan_tool/shell.py:_select_rate_limit_backend` is reached from both the noninteractive `OnRateLimitAction.SWITCH` branch and the interactive switch choice returned by `plan_tool.claude_errors:ask_on_rate_limit_action`.
- **Backend consumer:** `plan_tool/shell.py:_run_once` reads `get_active_backend()` when it builds the active backend's batch transport and prompt-byte count.
- **Repo-root selection context:** fallback selection still needs project override lookup rooted at `get_active_spawn_cwd()` when available, otherwise `Path.cwd()`.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/shell.py` — Scope successful batch rate-limit backend switches to the current `claude_invoke` call, keep retry behavior and diagnostics the same, and stop using lasting process-wide mutation for batch recovery.
  - `tests/test_shell.py` — Update existing `claude_invoke` switch tests and add regressions for restore after success, restore after fallback rate-limit failure, failed-switch no-install behavior, interactive switch restoration, and parallel invoke isolation.

## Implementation

- **Foundational logic:** current-invoke scoped backend switch for batch rate-limit recovery.

- **Use the step 2 helper as the boundary.** `plan_tool/shell.py` should import and use `scoped_select_active_backend(name, *, repo_root, model=None, fallback_factory=None)` from `plan_tool/backend.py`. Do not redesign backend selection in this step. If that helper cannot select the same effective backend that `select_active_backend(name, repo_root=...)` selects today, treat that as a step 2 contract gap.

- **Keep `claude_invoke` as the lifetime owner.** The scoped fallback must stay active across the later `_run_once` attempts that read `get_active_backend()`. Installing and restoring the scope wholly inside `plan_tool/shell.py:_select_rate_limit_backend` would restore too early, before the retry can see the fallback.

- **Change `_select_rate_limit_backend` from “mutate globally” to “select/validate for this invoke.”** It can still own fallback name validation, project override lookup through `get_active_spawn_cwd() or Path.cwd()`, and user-facing error notices through `_notify_or_tool`. Its successful result should give `claude_invoke` enough information to enter or keep a scoped backend override for the rest of the current invoke. Its failed result should leave no scoped state installed.

- **Cover both switch paths.** The `OnRateLimitAction.SWITCH` policy branch in `plan_tool/shell.py:claude_invoke` and the interactive switch path through `plan_tool/shell.py:_ask_rate_limit_action` must both install the same current-invoke scope on success. Avoid fixing only one branch.

- **Preserve the existing retry rules.** A successful fallback switch still resets the rate-limit wait guard and transient retry count before retrying. A fallback that is missing, misconfigured, or names the already-active backend still degrades to the existing wait path. A fallback that is itself rate-limited still switches only once, waits once, retries on the fallback, and then returns rather than looping.

- **Preserve the process-wide APIs.** Do not replace `set_active_backend` or `select_active_backend` usage outside this batch recovery path. Process-wide backend selection remains the CLI startup and legacy caller behavior from step 1 and step 2.

- **Keep prompt-budget and run-log behavior unchanged.** `plan_tool/shell.py:_maybe_warn_shell_prompt_budget` still fires once per `claude_invoke` call before retries, and `plan_tool/shell.py:_emit_call_end` still emits one event per `_run_once` attempt. This step changes backend state lifetime, not telemetry count or output parsing.

- **Use deterministic concurrency tests.** For sibling-isolation coverage in `tests/test_shell.py`, coordinate overlapping `claude_invoke` calls with `threading.Barrier` or `threading.Event`. Do not rely on sleeps to prove isolation.

## Tests

- `test_claude_invoke_rate_limit_menu_switches_backend_and_retries` — Update the existing interactive switch test to assert the first attempt uses the original backend, the retry uses the fallback backend, and `get_active_backend()` is restored after `claude_invoke` returns.
- `test_claude_invoke_switch_policy_switches_backend_without_prompt` — Update the existing auto-switch test to assert no menu is opened, no wait occurs, retry uses the fallback backend, and the process active backend is restored after return.
- `test_claude_invoke_switch_policy_degrades_to_wait_when_fallback_bad` — Update or keep this test so a failed fallback selection waits and retries without installing scoped fallback state.
- `test_claude_invoke_switch_to_active_backend_does_not_hot_loop` — Keep the no-op fallback behavior pinned: a fallback that names the already-active backend does not install a switch and degrades to the wait path.
- `test_claude_invoke_switch_bounds_when_fallback_also_rate_limited` — Update this test to assert the fallback is used for the switched attempt and the post-wait attempt, then the original active backend is restored after the terminal result.
- `test_claude_invoke_scoped_switch_restores_after_fallback_failure` — Add coverage for a successful switch where the fallback attempt also exits rate-limited and the call returns with the original active backend restored.
- `test_claude_invoke_parallel_switches_do_not_leak_between_threads` — Add coverage for overlapping invokes where one worker switches to a fallback and a sibling still sees its own original active backend view.

### Test-creation order (feature step)

1. Update `test_claude_invoke_switch_policy_switches_backend_without_prompt` first so it fails on the current global mutation and proves the desired retry-plus-restore contract.
2. Update `test_claude_invoke_rate_limit_menu_switches_backend_and_retries` next so the interactive path proves the same scoped lifetime.
3. Update `test_claude_invoke_switch_bounds_when_fallback_also_rate_limited` to pin that the scope remains open across the fallback wait/retry sequence.
4. Add the failed-switch and fallback-failure restore cases to prove no partial scope is left behind.
5. Add the parallel isolation regression last, after the single-thread restore cases are green.

Every new or changed test in `tests/test_shell.py` must be green before this step is considered finished.

## Acceptance criteria

- `plan_tool/shell.py:claude_invoke` retries on the fallback backend after a batch rate-limit switch and restores the original active backend before returning.
- `plan_tool/shell.py:_run_once` observes the scoped fallback backend on switched retry attempts because the scope is owned by the outer `claude_invoke` retry loop.
- `plan_tool/shell.py:_select_rate_limit_backend` no longer leaves a process-wide backend change behind when used for rate-limit recovery.
- Interactive switch handling through `plan_tool/shell.py:_ask_rate_limit_action` and noninteractive `OnRateLimitAction.SWITCH` handling both use the scoped recovery path.
- Failed fallback selection, same-backend fallback, and fallback-rate-limited terminal failure leave `get_active_backend()` equal to the pre-invoke backend after `claude_invoke` returns.
- `tests/test_shell.py` passes, including the updated switch tests and the new parallel isolation regression.

## References

- [Python contextvars — Context Variables](https://docs.python.org/3/library/contextvars.html) — Covers scoped context values and token reset behavior used by the upstream backend helper.
- [Python threading — Thread-local Data](https://docs.python.org/3/library/threading.html#thread-local-data) — Useful for comparing process-wide state, thread-local state, and context-scoped state in worker isolation tests.
- [Python subprocess — Popen Constructor](https://docs.python.org/3/library/subprocess.html#popen-constructor) — Defines subprocess spawning and inherited process state relevant to `_run_once` backend transport calls.
- [pytest — How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Covers monkeypatching shell seams and backend selection helpers in `tests/test_shell.py`.
- [Claude Platform Docs — Rate limits](https://platform.claude.com/docs/en/api/rate-limits) — Provides rate-limit behavior context for why switching is a retry-local recovery action.

## Deferred

- `plan_tool/backend.py` scoped helper implementation — owned by step 2; this step consumes that outcome and should not redesign it.
- `plan_tool/launcher.py` streaming rate-limit switching — covered by the sibling streaming step, because `shell_invoker` and `_run_streaming_once` have their own retry and spawn seams.
- `tests/cli/test_completeness_apply_parallel.py` parallel apply coverage — covered by the later parallel leakage coverage step, which verifies the scoped behavior through the worker fan-out and rerun orchestration.
- Operator and maintainer documentation — covered by the docs step after both batch and streaming scoped switch behavior are implemented.
