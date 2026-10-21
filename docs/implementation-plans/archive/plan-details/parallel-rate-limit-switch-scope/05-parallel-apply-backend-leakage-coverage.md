> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Add Parallel Apply Backend Leakage Coverage

## Summary

This step adds focused regression coverage in `tests/cli/test_completeness_apply_parallel.py` for backend selection leaks during parallel completeness apply. The primary design decision is to keep this step test-only: it should prove that the scoped-switch contract delivered by steps 3 and 4 holds through `apply_finding_in_tree`, `dispatch_parallel`, `run_parallel_apply`, and the serial conflict `_rerun` tail. On green, a worker that switches to a fallback backend during rate-limit recovery does not change the backend seen by sibling workers, later worker work, or the canonical replay tail. Any production behavior failure belongs back to the upstream scoped-switch steps, not to new production logic in this step.

## Table of Contents

- [Summary](#summary) — The short version of the parallel apply leakage coverage.
- [Why](#why) — The concurrency gap this step closes with tests.
- [Input](#input) — The dependency outcomes and existing apply boundaries these tests rely on.
- [Files (creates vs edits)](#files-creates-vs-edits) — The single test file this step changes.
- [Implementation](#implementation) — The intended coverage shape and test-only constraints.
- [Tests](#tests) — The specific regression cases to add.
- [Test-creation order (feature step)](#test-creation-order-feature-step) — The order to add the tests and the green gate.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary docs for context-local state, threads, and monkeypatching.
- [Deferred](#deferred) — Production fixes and broader CLI coverage left to other steps.

## Why

Parallel completeness apply fans saved findings into worker threads, applies them in isolated trees, then replays results serially onto the canonical tree. Steps 3 and 4 own the batch and streaming scoped-switch implementation, but the parallel apply path is where cross-worker leakage is easiest to miss: one worker can hit `--on-rate-limit switch` while another worker is running, and conflict replay can later re-run an apply on the canonical tree. This step adds the missing downstream coverage so `plan_tool/cli/completeness_apply_parallel.py` keeps honoring scoped backend behavior at the worker, fan-out, and serial-tail boundaries.

## Input

- **Step 3 dependency:** batch rate-limit switching in `plan_tool/shell.py:claude_invoke` must provide scoped current-invoke selection and restoration before this downstream coverage can pass.
- **Step 4 dependency:** streaming rate-limit switching in `plan_tool/launcher.py:shell_invoker` must provide scoped current-invoke selection and restoration before this downstream coverage can pass.
- **Worker boundary:** `plan_tool/cli/completeness_apply_parallel.py:apply_finding_in_tree` defaults to `plan_tool.launcher:shell_invoker` and also accepts an injected `invoker`.
- **Fan-out boundary:** `plan_tool/cli/completeness_apply_parallel.py:dispatch_parallel` runs one `apply_one` per recommendation on a `ThreadPoolExecutor` and turns one worker exception into one failed `FindingApplyResult`.
- **Orchestration boundary:** `plan_tool/cli/completeness_apply_parallel.py:run_parallel_apply` fans out through `dispatch_parallel`, then calls `replay_results`.
- **Serial replay boundary:** `plan_tool/cli/completeness_apply_parallel.py:run_parallel_apply` defines the conflict `_rerun` callback that calls `apply_finding_in_tree` against the canonical tree.
- **Test seams:** `tests/cli/test_completeness_apply_parallel.py` already monkeypatches `plan_tool.launcher.apply_finding` and `plan_tool.cli.completeness_apply_parallel.apply_finding_in_tree`; keep using those seams.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `tests/cli/test_completeness_apply_parallel.py` — Add backend leakage regressions for `apply_finding_in_tree`, `dispatch_parallel`, `run_parallel_apply`, and conflict replay. Keep the tests hermetic and avoid subprocess or broad CLI setup.

## Implementation

- **Foundational logic:** parallel apply scoped-backend leakage coverage.

- **Keep the step test-only.** Add tests in `tests/cli/test_completeness_apply_parallel.py`. Do not edit `plan_tool/backend.py`, `plan_tool/shell.py`, `plan_tool/launcher.py`, or `plan_tool/cli/completeness_apply_parallel.py` in this step unless a test exposes a dependency failure and the owning upstream step is being repaired separately.

- **Cover the worker boundary.** Add coverage under `tests/cli/test_completeness_apply_parallel.py:TestApplyFindingInTree` that proves a rate-limit switch inside the default streaming-style `invoker` path is visible during the retry and restored after `apply_finding_in_tree` returns. Also cover the injected `invoker` path, since `apply_finding_in_tree` accepts `invoker=` and `run_parallel_apply` forwards it to both worker applies and conflict reruns.

- **Cover sibling overlap.** Add coverage under `tests/cli/test_completeness_apply_parallel.py:TestDispatchParallel` that runs two or more workers with controlled overlap. Use `threading.Barrier`, `threading.Event`, or explicit capture lists instead of sleeps. The test should capture the backend each worker sees during its switched operation and after its operation, then assert one worker's fallback does not become another worker's active backend.

- **Cover full orchestration.** Add coverage under `tests/cli/test_completeness_apply_parallel.py:TestRunParallelApply` that drives `run_parallel_apply` through its existing `pool_factory` test seam. One way is to use a lightweight fake pool like the existing `TestRunParallelApply.test_merges_worker_changes_onto_canonical` setup, then monkeypatch `plan_tool.cli.completeness_apply_parallel.apply_finding_in_tree` to capture active backend state per worker and after replay.

- **Cover the conflict tail.** Add a regression where one worker result conflicts so `run_parallel_apply` uses its `_rerun` callback against the canonical tree. The test should prove the serial rerun uses the same scoped backend contract as worker applies and leaves the original backend active after `run_parallel_apply` returns.

- **Assert three moments, not just success.** Each leakage test should check state during the scoped operation, state after that operation, and the final active backend after the outer call returns. A green apply result alone is not enough because the bug is leaked mutable backend state.

- **Use real symbolic seams.** Prefer `plan_tool.backend:get_active_backend`, `plan_tool.backend:set_active_backend`, and the scoped backend helper produced by the upstream helper step when asserting active backend state. Prefer `plan_tool.launcher.apply_finding` and `plan_tool.cli.completeness_apply_parallel.apply_finding_in_tree` monkeypatches over CLI-level setup.

- **Keep failure ownership clear.** If the tests show that `plan_tool/shell.py:claude_invoke` or `plan_tool/launcher.py:shell_invoker` still leaks backend state, route the production fix to steps 3 or 4. This step should not add a parallel-apply-specific backend switch, because `plan_tool/cli/completeness_apply_parallel.py` should only consume the invoker behavior it is handed.

## Tests

- `test_default_shell_invoker_rate_limit_switch_restores_backend` — `apply_finding_in_tree` with its default streaming invoker observes the fallback during retry and restores the original backend after return.
- `test_injected_batch_invoker_rate_limit_switch_restores_backend` — `apply_finding_in_tree(..., invoker=...)` preserves the same restoration contract for a batch-style invoker.
- `test_dispatch_parallel_switches_do_not_leak_between_overlapping_workers` — overlapping `dispatch_parallel` workers see their own scoped backend state and do not clobber sibling active backend state.
- `test_run_parallel_apply_restores_backend_after_worker_switches` — `run_parallel_apply` leaves the original active backend after parallel worker applies complete and replay succeeds.
- `test_run_parallel_apply_conflict_rerun_restores_backend_after_serial_tail` — a conflict-triggered `_rerun` in `run_parallel_apply` uses scoped backend state during the rerun and restores the original backend afterward.

### Test-creation order (feature step)

1. Add the `apply_finding_in_tree` default-invoker restoration test first, because it is the smallest downstream proof of step 4 through the worker seam.
2. Add the `apply_finding_in_tree` injected-invoker restoration test next, because it proves callers that pass a batch-style invoker get the step 3 contract through the same worker seam.
3. Add the `dispatch_parallel` overlap test with barriers or events, because sibling isolation is the main parallel leakage risk.
4. Add the `run_parallel_apply` worker restoration test through `pool_factory`, because it proves the fan-out orchestration keeps the worker contract.
5. Add the `run_parallel_apply` conflict rerun test last, because it depends on the replay-tail setup and should make failures point at the serial `_rerun` boundary.
6. Run the new tests with the existing `tests/cli/test_completeness_apply_parallel.py` suite. Every new test must be green before this step is finished.

## Acceptance Criteria

- `tests/cli/test_completeness_apply_parallel.py` contains coverage for `apply_finding_in_tree` with the default `plan_tool.launcher:shell_invoker` path.
- `tests/cli/test_completeness_apply_parallel.py` contains coverage for `apply_finding_in_tree` with an injected batch-style invoker.
- `tests/cli/test_completeness_apply_parallel.py` contains an overlapping-worker `dispatch_parallel` regression that uses deterministic coordination rather than sleeps.
- `tests/cli/test_completeness_apply_parallel.py` contains a `run_parallel_apply` regression proving backend restoration after parallel workers and replay.
- `tests/cli/test_completeness_apply_parallel.py` contains a conflict-rerun regression proving the serial `_rerun` tail does not leak backend state.
- `python -m pytest tests/cli/test_completeness_apply_parallel.py` passes.
- No production file is changed by this step.

## References

- [Python contextvars — Context Variables](https://docs.python.org/3/library/contextvars.html) — Read for how scoped context state behaves across concurrent execution.
- [Python threading — Thread-local Data](https://docs.python.org/3/library/threading.html#thread-local-data) — Read for the thread-local model that helps compare per-worker state with process-wide globals.
- [Python concurrent.futures — ThreadPoolExecutor](https://docs.python.org/3/library/concurrent.futures.html#threadpoolexecutor) — Read for the thread-pool execution semantics behind `dispatch_parallel`.
- [pytest — How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Read for the monkeypatch patterns used by this test file.

## Deferred

- Production scoped-switch fixes in `plan_tool/shell.py` — owned by step 3.
- Production scoped-switch fixes in `plan_tool/launcher.py` — owned by step 4.
- Backend helper API changes in `plan_tool/backend.py` — owned by the upstream scoped backend helper step.
- End-to-end CLI coverage for `completeness-apply --jobs` — not needed here because `tests/cli/test_completeness_apply_parallel.py` already exposes the worker, fan-out, and replay seams directly.
