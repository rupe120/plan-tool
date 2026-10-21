> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Add Scoped Active Backend Helper APIs

## Summary

This step adds scoped active-backend APIs in `plan_tool/backend.py` and focused coverage in `tests/test_backend.py`. The main design decision is to keep `set_active_backend` and `select_active_backend` as process-wide selection APIs while adding a `ContextVar`-backed override that `get_active_backend` checks first. The scoped selection helper `scoped_select_active_backend(name, *, repo_root, model=None, fallback_factory=None)` must support the same effective-backend selection path as `select_active_backend`, including project overrides from `.plan-tool/backends.json`, without mutating the process-wide active backend. On green, callers can install a backend for one block of work, nested scopes restore correctly, and unrelated threads keep their own active backend view.

## Table of Contents

- [Summary](#summary) — The short version of the scoped backend helper step.
- [Why](#why) — The backend-state gap this step closes before retry-loop wiring.
- [Input](#input) — The upstream characterization and existing backend contracts this step must preserve.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two files this step changes.
- [Implementation](#implementation) — The required helper behavior, recommended API shape, and constraints.
- [Tests](#tests) — The regression cases to add in `tests/test_backend.py`.
- [Test-creation order (feature step)](#test-creation-order-feature-step) — The order to add tests with the implementation.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for completion.
- [References](#references) — Primary docs for scoped context behavior.
- [Deferred](#deferred) — Later consumer wiring that stays out of this step.

## Why

Step 1 pins that `plan_tool/backend.py:_active_backend` is a process-wide fallback used by CLI startup, benchmark trials, and existing call sites. The missing piece is a scoped override that later rate-limit retry loops can use without changing the backend seen by sibling work in the same process. This step adds that backend-layer primitive only: `plan_tool/shell.py:_select_rate_limit_backend` and `plan_tool/launcher.py:_select_rate_limit_backend` still leak globally until their own steps consume the new helper.

## Input

- **Step 1 outcome:** the process-wide behavior of `plan_tool/backend.py:get_active_backend`, `plan_tool/backend.py:set_active_backend`, and `plan_tool/backend.py:select_active_backend` is characterized and must remain valid.
- **Backend descriptor:** `plan_tool/backend.py:CliBackend` remains the value read by callers through `get_active_backend`.
- **Global fallback:** `plan_tool/backend.py:_active_backend` remains the process-wide backend used when no scoped override is active.
- **Selection pipeline:** `plan_tool/backend.py:select_active_backend` owns name lookup, fallback synthesis, project override loading, `build_effective_backend`, and `BackendSelection` return data. `plan_tool/backend.py:scoped_select_active_backend(name, *, repo_root, model=None, fallback_factory=None)` must produce the same selected/effective shape without making `selection.effective` global.
- **Existing scoped pattern:** `plan_tool/backend.py:spawn_cwd` and `plan_tool/backend.py:spawn_cwd_from_repo_root` show the module’s `ContextVar.set()` token-reset style.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/backend.py` — Add a scoped active-backend override, update `get_active_backend` to prefer it over `_active_backend`, and add public helper API(s) for scoped direct backend activation and scoped effective-backend selection.
  - `tests/test_backend.py` — Add unit coverage for scoped restore, exception restore, nesting, same-thread precedence, project override selection without global mutation, and parallel/thread isolation.

## Implementation

- **Foundational logic:** scoped active-backend override with process-wide fallback.

- **Keep the global API unchanged.** `plan_tool/backend.py:set_active_backend` should still mutate `_active_backend`, and `plan_tool/backend.py:select_active_backend` should still activate `selection.effective` globally. Do not convert `_active_backend` itself into a `ContextVar`.

- **Add a scoped override above the global fallback.** One direct approach is a `ContextVar[Optional[CliBackend]]` near `plan_tool/backend.py:_active_backend`, with `get_active_backend()` returning the scoped value when present and `_active_backend` otherwise. Use the token-reset pattern from `plan_tool/backend.py:spawn_cwd` so restoration happens in `finally`.

- **Expose a direct scoped helper.** Add a public context manager `scoped_active_backend(name_or_backend)` that accepts the same shapes as `set_active_backend`: a `CliBackend` instance or a registered backend name. Inside the scope, `get_active_backend()` should return that backend; after the scope exits, it should return the previous scoped value or the current global fallback.

- **Expose an effective-selection scoped helper.** Later steps need fallback backend selection with the same project override behavior as `select_active_backend(name, repo_root=...)`, but without global mutation. Add a public helper `scoped_select_active_backend(name, *, repo_root, model=None, fallback_factory=None)` that returns a context manager yielding `BackendSelection`. The helper should reuse the same selection logic as `select_active_backend` where practical, but the observable rule is the key: it yields the same `BackendSelection.selected`, `BackendSelection.effective`, and `unknown_override_names` values that global selection would produce, while leaving `_active_backend` unchanged.

- **Avoid duplicating selection policy.** If the implementation extracts a private builder from `select_active_backend`, keep it inside `plan_tool/backend.py` and keep the module stdlib-only except for its existing body-local `plan_tool.backend_config` import. The shared path should preserve caller `model` precedence, `.plan-tool/backends.json` extra argv, backend `default_model`, and `fallback_factory` behavior.

- **Preserve scope precedence.** While a scoped override is active, `get_active_backend()` should keep returning that scoped backend even if `set_active_backend()` changes the global fallback. After the scope exits, `get_active_backend()` should reflect whatever global backend is current at that time.

- **Preserve nesting.** A nested scoped backend should override the outer scoped backend only for the nested block. Exiting the nested block restores the outer backend, and exiting the outer block restores the global fallback.

- **Preserve thread isolation.** `ContextVar` is the right fit here because independent workers can install different scoped backends without racing a shared global. Do not use `threading.local` unless the implementation has a specific reason and the tests still prove context restoration and isolation.

- **Update public module docs.** Refresh the public surface comment in `plan_tool/backend.py` so it names `scoped_active_backend` and `scoped_select_active_backend` alongside `get_active_backend`, `set_active_backend`, and `select_active_backend`. Keep the import-topology warning intact: `plan_tool/backend.py` must not import `plan_tool/shell.py`, `plan_tool/launcher.py`, `plan_tool/claude_errors.py`, or CLI modules.

## Tests

- `test_scoped_active_backend_overrides_global_temporarily` — inside the scoped helper, `get_active_backend()` returns the scoped backend; after exit, it returns the original global backend.
- `test_scoped_active_backend_restores_on_exception` — an exception inside the scope still restores the previous active backend view.
- `test_scoped_active_backend_nests` — an inner scoped backend restores to the outer scoped backend, then the outer restores to the global backend.
- `test_set_active_backend_inside_scope_updates_global_after_scope` — global mutation during a scope does not override the scoped value, but it is visible after the scope exits.
- `test_scoped_active_backend_accepts_registered_name` — passing `"claude"` or another registered name scopes to the registered descriptor without calling `set_active_backend`.
- `test_scoped_select_active_backend_applies_project_override_without_global_mutation` — scoped selection applies model and extra argv from `.plan-tool/backends.json`, yields `BackendSelection`, and leaves the prior global backend active after exit.
- `test_scoped_select_active_backend_reports_unknown_override_names` — scoped selection returns the same sorted unknown override names as `select_active_backend`.
- `test_scoped_active_backend_is_thread_isolated` — two overlapping worker threads can each see their scoped backend while the main thread and post-scope checks see the global fallback.

### Test-creation order (feature step)

1. Add direct scoped-helper tests first: restore, exception restore, nesting, and name input. These define the core lifetime contract.
2. Add the global-precedence test next: `set_active_backend` inside a scope should update the fallback for later, not break the active scoped value.
3. Add scoped selection tests after the direct helper exists: project overrides, model/default precedence, and unknown override names.
4. Add the thread-isolation test last, using `threading.Barrier` or `concurrent.futures.ThreadPoolExecutor` plus explicit captured values rather than sleeps.

Every new test in `tests/test_backend.py` must be green before this step is finished, along with the existing backend tests that pin global selection.

## Acceptance criteria

- `plan_tool/backend.py:get_active_backend` returns a scoped backend when one is active and `_active_backend` when no scoped override is active.
- `plan_tool/backend.py:set_active_backend` still mutates the process-wide fallback and still accepts both `CliBackend` and registered-name inputs.
- `plan_tool/backend.py:select_active_backend` still globally activates `BackendSelection.effective`.
- `plan_tool/backend.py:scoped_active_backend` can install a `CliBackend` or registered backend name for one `with` block and restores on normal exit, exception exit, and nested exit.
- `plan_tool/backend.py:scoped_select_active_backend(name, *, repo_root, model=None, fallback_factory=None)` can select an effective backend with `.plan-tool/backends.json` overrides and yield `BackendSelection` without changing the process-wide active backend.
- `tests/test_backend.py` covers restore, exception restore, nesting, project override selection without global mutation, and parallel/thread isolation.
- `pytest tests/test_backend.py` passes.

## References

- [Python contextvars — Context Variables](https://docs.python.org/3/library/contextvars.html) — Use this for `ContextVar` token handling and per-context state semantics.
- [Python threading — Thread-local Data](https://docs.python.org/3/library/threading.html#thread-local-data) — Use this only as comparison context when reasoning about worker-local state versus process-wide globals.
- [Python concurrent.futures — ThreadPoolExecutor](https://docs.python.org/3/library/concurrent.futures.html#threadpoolexecutor) — Use this for deterministic thread-based isolation tests.
- [pytest — How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use this for test setup around registry, config, and environment-sensitive selection behavior.

## Deferred

- `plan_tool/shell.py:_select_rate_limit_backend` and `plan_tool/shell.py:claude_invoke` — step 3 wires batch rate-limit fallback retries to the scoped helper and owns retry-loop lifetime.
- `plan_tool/launcher.py:_select_rate_limit_backend` and `plan_tool/launcher.py:shell_invoker` — step 4 wires streaming rate-limit fallback retries to the scoped helper and owns streaming retry-loop lifetime.
- `tests/test_shell.py` and `tests/test_launcher.py` — consumer-level restore and retry coverage belongs with the shell and launcher wiring steps, not this backend helper step.
- `plan_tool/cli/completeness_apply_parallel.py` and `tests/cli/test_completeness_apply_parallel.py` — parallel apply leakage coverage belongs to the later plan step that verifies the consumers together.
