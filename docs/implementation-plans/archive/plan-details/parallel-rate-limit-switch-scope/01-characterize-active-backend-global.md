> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Characterize Active Backend Global Selection Behavior

## Summary

This step adds focused characterization coverage for the current active-backend selection contract in `tests/test_backend.py`. The production surface under observation is `plan_tool/backend.py:get_active_backend`, `plan_tool/backend.py:set_active_backend`, and `plan_tool/backend.py:select_active_backend`. The most important design decision is to pin today’s process-wide global behavior before later steps introduce scoped fallback behavior. On green, the suite proves that global backend selection still works for CLI startup, registry lookup, project overrides, and worker-thread visibility.

## Table of Contents

- [Summary](#summary) — The short version of the characterization step and expected result.
- [Why](#why) — The backend-state behavior this step pins before later scoped changes.
- [Input](#input) — The existing backend contracts the tests read and preserve.
- [Files creates vs edits](#files-creates-vs-edits) — The files this step changes and what belongs in each.
- [Implementation](#implementation) — The intended characterization boundary and the invariants to preserve.
- [Tests](#tests) — The regression cases to add or keep in `tests/test_backend.py`.
- [Test-creation order refactor step](#test-creation-order-refactor-step) — The characterization-first order and unchanged-after gate.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for completion.
- [References](#references) — Primary docs for the global-vs-scoped state behavior.
- [Deferred](#deferred) — Follow-up scoped switching work owned by later steps.

## Why

`plan_tool/backend.py:_active_backend` is a process-wide global today, and several callers depend on that behavior: `plan_tool/cli/app.py:main` selects once before dispatch, `plan_tool/bench.py:_run_cell_trial` switches before work that may run under a timeout worker, and failure/reporting paths read `get_active_backend()` later. Before later steps add scoped rate-limit recovery, this step must make the current global behavior explicit in tests so the scoped layer can be added without accidentally replacing the global fallback or breaking legacy callers.

## Input

- **Backend descriptors:** `plan_tool/backend.py:CliBackend` is the value passed through all active-backend APIs.
- **Global state:** `plan_tool/backend.py:_active_backend` is the current process-wide backend used by `get_active_backend()`.
- **Registry:** `plan_tool/backend.py:_REGISTRY`, `plan_tool/backend.py:register_backend`, `plan_tool/backend.py:resolve_backend`, `plan_tool/backend.py:registered_binaries`, and `plan_tool/backend.py:registered_names` remain the source for registered backend lookup.
- **Selection path:** `plan_tool/backend.py:select_active_backend` resolves the backend, applies `.plan-tool/backends.json` overrides through `build_effective_backend`, and activates `selection.effective`.
- **Existing scoped pattern:** `plan_tool/backend.py:spawn_cwd` and `plan_tool/backend.py:spawn_cwd_from_repo_root` show the local `ContextVar` token-reset style, but this step only characterizes active backend globals.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `tests/test_backend.py` — Add characterization tests for process-wide active backend state, name-based activation, effective-backend activation, registry restoration, and worker-thread visibility.
  - `plan_tool/backend.py` — No behavior change expected. Touch only if the public docstring for `get_active_backend`, `set_active_backend`, or `select_active_backend` needs a small clarification to match the characterized contract.

## Implementation

- **Foundational logic:** active-backend global contract characterization.

- **Pin the current global contract first.** Add tests that show `set_active_backend(CliBackend)` and `set_active_backend(name)` mutate the same process-wide state read by `get_active_backend()`. Keep the existing `tests/test_backend.py:_restore_backend_state` fixture as the cleanup boundary because it restores both `backend._REGISTRY` and the active backend.

- **Cover effective selection, not only raw selection.** `plan_tool/backend.py:select_active_backend` does more than look up a registered backend: it loads project overrides, calls `build_effective_backend`, calls `set_active_backend(effective)`, and returns `BackendSelection`. Characterization should assert that `selection.effective is get_active_backend()` after a project override, and that the registry seed from `resolve_backend("claude")` remains separate from the transient effective backend when overrides are present.

- **Keep thread visibility explicit.** Add a small worker-thread test that sets the active backend in the main thread, starts a worker, and has the worker read `get_active_backend()`. The expected current behavior is that the worker sees the process-wide active backend. Use `threading.Thread` or `concurrent.futures.ThreadPoolExecutor` with an explicit result capture; avoid sleeps.

- **Preserve import direction.** Do not make `plan_tool/backend.py` import `plan_tool/shell.py`, `plan_tool/launcher.py`, `plan_tool/claude_errors.py`, or CLI modules. `plan_tool/backend.py` is still the low-level backend descriptor and registry module.

- **Do not introduce scoped active-backend behavior here.** A later step can add a `ContextVar` override layer modeled on `spawn_cwd`, but this step should not add a context manager, alter `get_active_backend()` lookup precedence, or update rate-limit switch callers.

- **Use real local anchors.** Tests should exercise `CLAUDE_BACKEND`, `CODEX_BACKEND`, `CURSOR_BACKEND`, `_make_fake_backend`, `register_backend`, `set_active_backend`, `get_active_backend`, `select_active_backend`, and `build_effective_backend` as needed. Keep assertions at the backend API level rather than routing through `plan_tool/shell.py` or `plan_tool/launcher.py`.

## Tests

- `test_set_active_backend_descriptor_is_process_global` — registers a fake backend, activates it by descriptor, and asserts repeated `get_active_backend()` calls return that descriptor.
- `test_set_active_backend_name_resolves_registry_globally` — registers a fake backend, activates it by name, and asserts `get_active_backend()` returns the registered object.
- `test_select_active_backend_sets_effective_backend_globally` — writes a `.plan-tool/backends.json` override, calls `select_active_backend("claude", repo_root=tmp_path)`, and asserts `selection.effective is get_active_backend()`.
- `test_select_active_backend_does_not_replace_registry_seed` — after selecting an effective backend with overrides, asserts `resolve_backend("claude")` still returns the registered seed while `get_active_backend()` returns the effective descriptor.
- `test_active_backend_global_visible_to_worker_thread` — sets a backend in the main thread and asserts a worker thread reading `get_active_backend()` sees the same backend.
- `test_restore_backend_state_restores_registry_and_active_backend` — keep or strengthen the existing fixture-backed pattern so characterization tests do not leak active backend or registry changes across the suite.

### Test-creation order (refactor step)

Write the characterization tests before any production edit:

1. `test_set_active_backend_descriptor_is_process_global` — pins descriptor activation through the process-wide active backend.
2. `test_set_active_backend_name_resolves_registry_globally` — pins name-based activation through `_REGISTRY`.
3. `test_select_active_backend_sets_effective_backend_globally` — pins project override selection and activation.
4. `test_select_active_backend_does_not_replace_registry_seed` — pins transient effective descriptors as active-only, not registry replacements.
5. `test_active_backend_global_visible_to_worker_thread` — pins current worker-thread visibility.

Pass-unchanged-after gate: these same characterization tests must stay green, without rewriting their expected behavior, after any later restructuring of active backend selection.

## Acceptance criteria

- `tests/test_backend.py` contains characterization coverage for descriptor activation, name activation, effective activation, registry seed preservation, and worker-thread visibility.
- `get_active_backend()` still defaults to `CLAUDE_BACKEND` when no test has changed the active backend.
- `set_active_backend(CODEX_BACKEND)` makes later `get_active_backend()` calls return `CODEX_BACKEND`.
- `set_active_backend("claude")` resolves through `plan_tool/backend.py:_REGISTRY`.
- `select_active_backend("claude", repo_root=tmp_path)` returns a `BackendSelection` whose `effective` descriptor is the active backend.
- A worker thread started after `set_active_backend(CODEX_BACKEND)` sees `CODEX_BACKEND` through `get_active_backend()`.
- `pytest tests/test_backend.py` passes.

## References

- [Python contextvars — Context Variables](https://docs.python.org/3/library/contextvars.html) — Use for understanding the later scoped-state option and why it differs from today’s global behavior.
- [Python threading — Thread-local Data](https://docs.python.org/3/library/threading.html#thread-local-data) — Use when comparing process-wide globals, thread-local state, and worker visibility.
- [Python concurrent.futures — ThreadPoolExecutor](https://docs.python.org/3/library/concurrent.futures.html#threadpoolexecutor) — Use for deterministic worker-thread characterization without timing assumptions.
- [pytest — How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use for test isolation patterns around registry and backend state.

## Deferred

- `plan_tool/backend.py` scoped active-backend helper — left to the later refactor step that adds scoped override behavior while preserving this global fallback.
- `plan_tool/shell.py:_select_rate_limit_backend` — later batch rate-limit work should consume the scoped helper after this characterization is pinned.
- `plan_tool/launcher.py:_select_rate_limit_backend` — later streaming rate-limit work should consume the scoped helper after this characterization is pinned.
- `tests/test_shell.py` and `tests/test_launcher.py` rate-limit switch coverage — those tests belong with the steps that change batch and streaming fallback lifetime.
