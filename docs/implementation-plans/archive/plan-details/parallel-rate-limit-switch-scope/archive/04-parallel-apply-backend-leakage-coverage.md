> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Add Parallel Apply Backend Leakage Coverage

## Summary

This step adds test-only coverage in `tests/cli/test_completeness_apply_parallel.py` for backend selection leakage during parallel completeness apply. It should prove that worker-level rate-limit backend switches produced by steps 2 and 3 stay scoped to the worker or invoke that triggered them. The key design decision is to exercise the existing parallel apply seams, not add another backend-switching implementation in the test file. On green, `run_parallel_apply` and conflict reruns can use fallback backends without leaving the process active backend changed for sibling workers, later workers, or the canonical replay tail.

## Table of Contents

- [Summary](#summary) — The short version of the test-only coverage and expected result.
- [Why](#why) — The leakage risk this test step closes.
- [Input](#input) — The upstream scoped-backend behavior this step verifies.
- [Files creates vs edits](#files-creates-vs-edits) — The single test file this step changes.
- [Implementation](#implementation) — The intended coverage shape and anchors to use.
- [Tests](#tests) — The regression cases to add in the parallel apply test module.
- [Verification (non-code step)](#verification-non-code-step) — How to verify this test-only detail artifact.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for completion.
- [References](#references) — Primary docs for the concurrency and scoped-state behavior.
- [Deferred](#deferred) — Related backend-switching work owned by earlier steps.

## Why

Parallel completeness apply runs several `plan_tool/cli/completeness_apply_parallel.py:apply_finding_in_tree` calls at the same time through `plan_tool/cli/completeness_apply_parallel.py:dispatch_parallel`, and each worker eventually invokes backend-facing apply logic. Steps 2 and 3 are responsible for producing scoped rate-limit fallback backend switches for batch and streaming invokes, and the parallel apply path needs its own regression because it combines worker threads, isolated worktrees, and a serial conflict rerun. Without coverage here, a fallback selected by one apply could still change `plan_tool/backend.py:get_active_backend` for a sibling worker or for the canonical replay tail.

## Input

- **Step 2 dependency-produced contract:** batch rate-limit fallback switches in `plan_tool/shell.py:claude_invoke` are not scoped at HEAD; after step 2 lands, confirm they are scoped to the current invoke, including the later `plan_tool/shell.py:_run_once` retry that reads the active backend.
- **Step 3 dependency-produced contract:** streaming rate-limit fallback switches in `plan_tool/launcher.py:shell_invoker` are not scoped at HEAD; after step 3 lands, confirm they are scoped to the current invoke, including the later `plan_tool/launcher.py:_run_streaming_once` retry that reads the active backend.
- **Parallel apply seam:** `plan_tool/cli/completeness_apply_parallel.py:run_parallel_apply` fans out worker applies through `dispatch_parallel`, then serially calls `replay_results`; conflicting findings can rerun through the `_rerun` closure inside `run_parallel_apply`.
- **Worker seam:** `plan_tool/cli/completeness_apply_parallel.py:apply_finding_in_tree` defaults to `plan_tool.launcher.shell_invoker` when no invoker is supplied, and passes the invoker into `plan_tool.launcher.apply_finding`.
- **Backend state dependency-produced contract:** `plan_tool/backend.py:get_active_backend` still reads process-wide state at HEAD; after steps 2 and 3 land, confirm it returns the scoped backend only inside the active fallback scope, then returns the original process active backend after the invoke exits.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `tests/cli/test_completeness_apply_parallel.py` — Add focused regressions that drive `apply_finding_in_tree`, `dispatch_parallel`, and `run_parallel_apply` with fake apply/invoker seams that expose active-backend changes across concurrent workers and serial conflict reruns.

## Implementation

- **Foundational logic:** parallel apply backend-scope isolation.

- **Keep this test-only.** Do not edit `plan_tool/cli/completeness_apply_parallel.py`, `plan_tool/shell.py`, `plan_tool/launcher.py`, or `plan_tool/backend.py` in this step. If the new tests fail because scoped switching is missing or wrong, the fix belongs to steps 2 or 3.

- **Exercise the real parallel apply boundaries.** Put the new tests near the existing `tests/cli/test_completeness_apply_parallel.py:TestApplyFindingInTree`, `TestDispatchParallel`, and `TestRunParallelApply` coverage. The tests should call the same public seams developers rely on:
  - `plan_tool/cli/completeness_apply_parallel.py:apply_finding_in_tree` for one worker apply.
  - `plan_tool/cli/completeness_apply_parallel.py:dispatch_parallel` for sibling thread isolation.
  - `plan_tool/cli/completeness_apply_parallel.py:run_parallel_apply` for worker fan-out plus serial replay and conflict rerun behavior.

- **Assert backend restoration, not just successful apply.** The important observable is that `plan_tool/backend.py:get_active_backend` is the original backend after each worker invoke and after `run_parallel_apply` returns. A test that only checks `ReplayOutcome.applied` can pass while backend state still leaks.

- **Prove sibling isolation under concurrency.** One way is to register or use two distinct `CliBackend` values, set an original backend with `plan_tool/backend.py:set_active_backend`, then use barriers/events inside fake worker apply functions so two `dispatch_parallel` workers overlap. Each worker should record the backend it sees during its fake fallback scope and after leaving it; no worker should observe another worker's fallback outside that worker's scoped invoke.

- **Cover the default streaming path.** Because `apply_finding_in_tree` defaults to `plan_tool.launcher.shell_invoker`, include a regression that lets the worker use that default or a small fake that mirrors the `shell_invoker` active-backend read points. The assertion should tie back to step 3: a fallback visible for the retry must be gone when `apply_finding_in_tree` returns.

- **Cover the injectable batch path.** `apply_finding_in_tree` accepts `invoker`, so add a focused case that supplies an invoker backed by the step 2 batch behavior or a fake with the same contract. This protects callers that route completeness apply through `plan_tool/shell.py:claude_invoke`-style batch invocation.

- **Cover conflict reruns.** Extend or mirror `tests/cli/test_completeness_apply_parallel.py:TestRunParallelApply.test_merges_worker_changes_onto_canonical` so one worker result conflicts in `replay_results` and triggers the `_rerun` closure inside `run_parallel_apply`. The rerun should see the original backend at entry and leave it unchanged at exit, even if a worker used a fallback backend earlier.

- **Keep the tests deterministic.** Prefer `threading.Barrier`, `threading.Event`, and local capture lists over sleeps. The test should fail because backend state leaked, not because thread scheduling happened to differ.

- **Use module-level monkeypatch seams already present.** Existing tests monkeypatch `plan_tool.launcher.apply_finding` and `plan_tool.cli.completeness_apply_parallel.apply_finding_in_tree`; keep that style. Avoid broad CLI tests because this step is about the parallel apply backend boundary, not command parsing.

## Tests

- `test_apply_finding_in_tree_restores_backend_after_streaming_switch` — asserts a worker using the default streaming invoker observes fallback only inside the invoke and leaves `get_active_backend()` at the original backend when it returns.
- `test_apply_finding_in_tree_restores_backend_after_batch_switch_invoker` — asserts an injected batch-style invoker can switch for its retry without leaking the fallback backend out of the worker apply.
- `test_dispatch_parallel_backend_switches_do_not_cross_workers` — runs overlapping workers through `dispatch_parallel` and asserts each worker’s fallback backend is isolated from its sibling.
- `test_run_parallel_apply_conflict_rerun_uses_original_backend_after_worker_switch` — forces a replay conflict and asserts the serial rerun starts and ends on the original backend, not a worker fallback.
- `test_run_parallel_apply_restores_original_backend_after_all_workers` — asserts `run_parallel_apply` returns with the same active backend that was set before the call.

### Verification (non-code step)

This detail file is a non-code artifact. Verify it by checking that every path named as edited is in the step file list, every production path is cited only as an anchor or upstream dependency, and the References list only includes docs relevant to scoped state and thread-pool execution.

## Acceptance criteria

- `tests/cli/test_completeness_apply_parallel.py` contains regression coverage for worker backend restoration, sibling worker isolation, and conflict-rerun restoration.
- The new tests fail if a worker fallback backend remains visible through `plan_tool/backend.py:get_active_backend` after that worker’s invoke returns.
- The new tests fail if one `dispatch_parallel` worker can observe a sibling worker’s fallback backend outside the sibling’s scoped invoke.
- The new tests fail if the `_rerun` closure inside `run_parallel_apply` starts from a fallback backend leaked by a prior worker.
- `pytest tests/cli/test_completeness_apply_parallel.py` passes after steps 2 and 3 are implemented.

## References

- [Python contextvars — Context Variables](https://docs.python.org/3/library/contextvars.html) — Read for how scoped values should restore after a concurrent task leaves its context.
- [Python threading — Thread-local Data](https://docs.python.org/3/library/threading.html#thread-local-data) — Read when comparing thread-local behavior with process-wide backend state in worker tests.
- [Python concurrent.futures — ThreadPoolExecutor](https://docs.python.org/3/library/concurrent.futures.html#threadpoolexecutor) — Read for the thread pool semantics behind `dispatch_parallel`.
- [pytest — How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Read for the monkeypatch patterns used by the existing parallel apply tests.

## Deferred

- Production backend scoping fixes — owned by steps 2 and 3 in `plan_tool/shell.py` and `plan_tool/launcher.py`; this step only adds parallel apply coverage.
- Backend helper design changes — owned by step 1 in `plan_tool/backend.py`; this step should not redesign active-backend selection.
- CLI command parsing and `--jobs` behavior — already covered outside this file; this step targets the worker and replay backend-leakage boundary only.
