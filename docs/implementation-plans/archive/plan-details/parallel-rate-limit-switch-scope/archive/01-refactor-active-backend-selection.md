> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Refactor Active Backend Selection Behind Scoped Helpers

## Summary

This step moves active backend selection in `plan_tool/backend.py` behind scoped helper APIs while preserving the existing `get_active_backend`, `set_active_backend`, and `select_active_backend` behavior for current callers. The primary design choice is to keep the process-wide active backend contract intact and add a `ContextVar`-backed scoped override on top of it, rather than replacing the global selection outright. `tests/test_backend.py` should characterize the current global behavior first, then add focused coverage for scoped restore, nesting, exception handling, and parallel worker isolation. On green, existing callers still see the same active backend, and later steps have a safe helper to switch backends for one rate-limit recovery scope without clobbering sibling work.

## Table of Contents

- [Summary](#summary) — The short version of the refactor and its expected result.
- [Why](#why) — The backend-state problem this step prepares to solve.
- [Input](#input) — The existing backend contracts this refactor must preserve.
- [Files creates vs edits](#files-creates-vs-edits) — The files this step changes and what belongs in each.
- [Implementation](#implementation) — The intended helper shape, invariants, and out-of-scope consumers.
- [Tests](#tests) — The regression cases to add or preserve.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for completion.
- [References](#references) — Primary docs for scoped context and parallel execution.
- [Deferred](#deferred) — Follow-up wiring that belongs to later steps.

## Why

`plan_tool/backend.py:_active_backend` is process-wide today, so any caller that switches the active backend during rate-limit handling can affect unrelated work running in the same process. That is risky for parallel runs because `plan_tool/shell.py:_select_rate_limit_backend` and `plan_tool/launcher.py:_select_rate_limit_backend` both route through the shared selection API. This step creates the scoped backend-selection primitive that later wiring can use, while keeping the current global selection behavior stable for CLI startup, tests, and bench execution.

## Input

- **Backend descriptors:** `plan_tool/backend.py:CliBackend` remains the value type passed through the active-backend APIs.
- **Registry contract:** `plan_tool/backend.py:_REGISTRY`, `plan_tool/backend.py:register_backend`, and `plan_tool/backend.py:resolve_backend` remain the source for name-based backend lookup.
- **Current active API:** `plan_tool/backend.py:get_active_backend`, `plan_tool/backend.py:set_active_backend`, and `plan_tool/backend.py:select_active_backend` keep their public contracts for existing callers.
- **Existing scoped pattern:** `plan_tool/backend.py:spawn_cwd` and `plan_tool/backend.py:spawn_cwd_from_repo_root` are the local model for token-based context restore.
- **Parallel risk surface:** `plan_tool/bench.py:_run_cell_trial` still relies on process-wide `set_active_backend` before a timeout worker runs, so this refactor must not replace global backend state with a bare `ContextVar` that worker threads cannot see.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/backend.py` — Add the scoped active-backend helper layer, route `get_active_backend` through it, and preserve existing global activation semantics.
  - `tests/test_backend.py` — Add characterization-first tests for existing global behavior and scoped tests for restore, nesting, exception handling, and parallel isolation.

## Implementation

- **Foundational logic:** scoped active-backend override.

- **Keep the global contract:** `plan_tool/backend.py:set_active_backend` should continue to set the process-wide active backend used when no scoped override is present. Existing callers such as `plan_tool/cli/app.py:main`, `plan_tool/bench.py:_run_cell_trial`, and tests that activate `CODEX_BACKEND` or `CURSOR_BACKEND` depend on that behavior.

- **Add a scoped override layer:** Use a `ContextVar[Optional[CliBackend]]` in `plan_tool/backend.py` for the current task/thread override. `plan_tool/backend.py:get_active_backend` should return the scoped value when one is set, otherwise return the process-wide backend.

- **Expose a small context manager:** Add a helper with a direct name such as `scoped_active_backend(name_or_backend)` that accepts the same input shape as `set_active_backend`: either a registered backend name or a `CliBackend`. It should resolve names through `plan_tool/backend.py:_REGISTRY`, set the scoped override for the block, and restore the previous scoped value with the token in `finally`.

- **Do not make scoped selection the default yet:** `plan_tool/backend.py:select_active_backend` should keep activating the effective backend globally, because current CLI startup and existing callers expect that configured selection installs the effective backend process-wide. If the implementation needs a shared internal helper, one way is to split “build the `BackendSelection`” from “activate it,” then have `select_active_backend` call the shared builder and `set_active_backend(selection.effective)`.

- **Support later configured scoped selection:** If useful, add a second context manager such as `scoped_backend_selection(name, repo_root=..., model=..., fallback_factory=...)` that reuses the same selection-building path as `select_active_backend` but scopes `selection.effective` instead of setting it globally. Keep the return/inspection contract simple: later rate-limit code needs to know whether selection succeeded and what effective backend was scoped, not a new backend registry shape.

- **Preserve import boundaries:** `plan_tool/backend.py` must stay stdlib-only. Do not import `plan_tool.shell`, `plan_tool.launcher`, `plan_tool.claude_errors`, or CLI modules from it.

- **Preserve registry behavior:** `plan_tool/backend.py:resolve_backend`, `plan_tool/backend.py:registered_binaries`, `plan_tool/backend.py:registered_names`, and `plan_tool/backend.py:discover_and_register_backends` should keep reading the registry, not the scoped active backend.

- **Preserve effective backend behavior:** `plan_tool/backend.py:build_effective_backend` should still return the base object unchanged when there are no overrides, and should still preserve parser, patterns, transports, and model flag behavior.

- **Avoid replacing `_active_backend` with only a `ContextVar`:** A pure context variable would isolate worker threads from process-wide CLI or bench selection unless every caller copied context explicitly. This step should add scoped override behavior on top of the current global fallback.

- **Leave consumers alone:** Do not edit `plan_tool/shell.py:_select_rate_limit_backend`, `plan_tool/launcher.py:_select_rate_limit_backend`, or other backend switch call sites in this step. Later steps can consume the scoped helper once its behavior is pinned.

## Tests

- `test_get_active_backend_defaults_to_claude` — Existing default active backend remains `CLAUDE_BACKEND` when no global or scoped override is active.
- `test_set_active_backend_round_trips` — Existing descriptor and name-based global activation still work.
- `test_select_active_backend_applies_project_override_and_sets_active` — Existing configured selection still installs the effective backend globally.
- `test_scoped_active_backend_restores_previous_backend` — A scoped override changes `get_active_backend` only inside the block and restores the prior value after it exits.
- `test_scoped_active_backend_restores_on_exception` — A scoped override is cleared even when the block raises.
- `test_scoped_active_backend_nests` — Inner scoped overrides restore to the outer scoped backend, then back to the global backend.
- `test_scoped_active_backend_accepts_registered_name` — Name-based scoped activation resolves through the registry and reports unknown names the same way as the global setter.
- `test_scoped_active_backend_does_not_mutate_process_backend` — Exiting a scoped override leaves the process-wide value set by `set_active_backend` unchanged.
- `test_scoped_active_backend_is_thread_isolated` — Two worker threads can set different scoped backends and observe their own values without changing the main thread’s active backend.

### Test-creation order (refactor step)

Write the characterization tests first and keep them unchanged through the refactor:

- `test_get_active_backend_defaults_to_claude` — Pins the no-selection default.
- `test_set_active_backend_round_trips` — Pins existing global mutation by descriptor and by name.
- `test_select_active_backend_applies_project_override_and_sets_active` — Pins configured effective backend activation.
- `test_run_step_failure_names_active_backend` — Pins that existing readers of `get_active_backend` still see the active backend selected for the call.

After those are green, add the scoped-helper tests listed above. The pass-unchanged-after gate is strict: the characterization tests should stay green without rewriting their assertions after the scoped layer is introduced.

## Acceptance criteria

- `plan_tool/backend.py:get_active_backend` returns the scoped backend inside a scoped helper block.
- `plan_tool/backend.py:get_active_backend` returns the process-wide backend outside any scoped helper block.
- `plan_tool/backend.py:set_active_backend` still changes the process-wide backend for existing callers.
- `plan_tool/backend.py:select_active_backend` still applies project overrides and activates the effective backend globally.
- A scoped helper block restores the previous scoped value after normal exit and after an exception.
- Nested scoped helper blocks restore in stack order.
- Parallel worker tests in `tests/test_backend.py` show scoped backend values do not clobber each other or the main thread.
- Existing backend tests in `tests/test_backend.py` still pass.

## References

- [Python contextvars — Context Variables](https://docs.python.org/3/library/contextvars.html) — Read for `ContextVar` token set/reset behavior and context-local state.
- [Python threading — Thread-local Data](https://docs.python.org/3/library/threading.html#thread-local-data) — Read for the thread-local comparison when reasoning about worker isolation.
- [Python concurrent.futures — ThreadPoolExecutor](https://docs.python.org/3/library/concurrent.futures.html#threadpoolexecutor) — Read for thread pool execution behavior relevant to parallel backend switching tests.
- [pytest — How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Read for test isolation patterns around module-level backend state.
- [Claude Platform Docs — Rate limits](https://platform.claude.com/docs/en/api/rate-limits) — Read for the rate-limit behavior that makes scoped backend switching necessary.

## Deferred

- `plan_tool/shell.py:_select_rate_limit_backend` — Later steps should switch this rate-limit recovery path to the scoped helper after the helper contract is pinned.
- `plan_tool/launcher.py:_select_rate_limit_backend` — Later steps should apply the same scoped switch to the streaming run path.
- `plan_tool/bench.py:_run_cell_trial` — Keep its process-wide `set_active_backend` behavior in this step; any migration to scoped selection needs its own audit because timeout workers are involved.
