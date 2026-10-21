> **Auto-archived**: this plan was swept on 2026-07-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Bind the telemetry `run_id` ContextVar to the run-log `run_id` at both `run` entrypoints, cleared on every exit

## Summary

Wire the `run` command so any `record_decision` call made during a run stamps the same `run_id` the run-log records for that step. The mechanism lives on `RunLogWriter` (`plan_tool/run_log.py`) as a new opt-in scope helper that binds step 1's telemetry `run_id` ContextVar to the writer's own `run_id` and resets it on exit; the two run entrypoints in `plan_tool/cli/run_cmd.py` (`cmd_run` and `_cmd_run_sweep`) call it around their run body so the clear happens in the same `finally` that already calls `run_end`. Keeping the binding opt-in — rather than auto-firing inside `RunLogWriter.start` — is the key decision: it covers only these two `run` entrypoints now and leaves the ~13 other `RunLogWriter.start` sites (create/detail/completeness, plus the `run --reconcile` lane `_cmd_run_reconcile` and the standalone `reconcile`/`reconcile-all`/`reconcile-plan` commands) for the phase-2 backfill. On green, a decision recorded mid-run carries the run's `run_id`, a decision recorded outside any run carries `""`, and no `run_id` leaks into the next run or a non-run command.

## Table of Contents

- [Why](#why) — what the linkage schema can't do until the run entrypoints set the ContextVar
- [Input](#input) — the step-1 telemetry API and the RunLogWriter lifecycle this step builds on
- [Files (creates vs edits)](#files-creates-vs-edits) — the files this step touches
- [Implementation](#implementation) — the writer-owned scope helper, the two entrypoint call sites, and the leaf-import and no-leak constraints
- [Tests](#tests) — unit tests for the scope helper's set/reset and the recorded-decision stamping
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — stdlib docs for the primitives used
- [Deferred](#deferred) — the other RunLogWriter entrypoints and work left to later phases

## Why

Step 1 gives `DecisionEvent` a `run_id` field and has `record_decision` read it from a `telemetry`-owned ContextVar, but nothing sets that ContextVar yet, so every event still records `run_id = ""` and the decision log stays an island from the run log. The whole point of the linkage schema is that a later resolver can tie a heuristic decision back to the run it happened in — impossible while `run_id` is always empty. This step is the producer side for the `run` command: it makes the run entrypoints hand the run-log's `run_id` to telemetry for the duration of the run, so decisions fired by `run_step` / launcher / review during that run carry the join key. It is deliberately narrow to `run` — the plan enriches only what exists in phase 1, and backfilling the other command entrypoints is a later slice.

## Input

This step consumes two existing contracts and must not break either:

- **Step 1's telemetry ContextVar API** (`plan_tool/telemetry.py`). Step 1 ships `_active_run_id` (a `ContextVar[str]` defaulting to `""`), a `set_active_run_id` setter, and a `scoped_run_id` scope contextmanager, and `record_decision` reads the active value. This step only needs to *drive* that API from the run entrypoints — it does not re-specify how step 1 stamps `run_id` onto the event. Follow step 1's shipped names; if the setter/scope helper names differ from those above, follow what step 1 landed.
- **The `RunLogWriter` lifecycle** (`plan_tool/run_log.py`). `RunLogWriter.start` mints the `run_id` (via `new_run_id`) and stores it on the writer's `run_id` slot; every run entrypoint calls `run_logger.run_end(...)` from a `finally` covering all return paths. This step reads `run_logger.run_id` and hangs the bind/clear off that same lifecycle. The writer already manages a process/thread-global side channel this way — see its shell-sink stack (`install_call_end_sink` / `bind_shell_sink`, which lazy-import `plan_tool.shell`) — so a telemetry run_id scope fits the existing shape.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/run_log.py` — add an opt-in scope helper on `RunLogWriter` (recommended: a `@contextmanager` method, e.g. `telemetry_run_id_scope`) that binds the telemetry ContextVar to `self.run_id` on enter and resets it on exit, via a lazy `from plan_tool import telemetry` (matching the existing lazy `plan_tool.shell` imports in the sink methods).
  - `plan_tool/cli/run_cmd.py` — call that helper around the run body at both entrypoints: `cmd_run` (the writer opened just after `resolve_plan_for_context`, with its `finally: run_logger.run_end(...)`) and `_cmd_run_sweep` (the per-iteration writer, with its own per-iteration `finally: run_logger.run_end(...)`).
  - `tests/test_run_log.py` — unit tests for the new scope helper: it sets the active `run_id` to the writer's `run_id` inside the scope, restores the prior value on exit, resets even when the body raises, and a decision recorded inside the scope carries the run's `run_id`.

## Implementation

**Foundational logic:** bind the telemetry `run_id` ContextVar to the active run's `run_id` for the duration of a run, and clear it on every exit path.

**Add the bind/clear as an opt-in helper on `RunLogWriter`, not inside `start`.**
- Put it on the writer because the writer owns `run_id` and is the natural single source; a helper there is unit-testable in `tests/test_run_log.py` (the test file in this step's scope) without driving the CLI.
- Recommended shape: a `@contextmanager` method (e.g. `telemetry_run_id_scope`) whose body is `with telemetry.scoped_run_id(self.run_id): yield` — reusing step 1's scope helper so the reset/token handling lives in one place. Import telemetry lazily inside the method.
- **Do not auto-bind inside `RunLogWriter.start`.** `start` is called from ~15 sites (create/detail via `plan_tool/cli/authoring.py`, `plan_tool/cli/completeness_cmd.py`, the `run --reconcile` lane and standalone `reconcile*` writers in `plan_tool/cli/reconcile.py`, `plan_tool/cli/gates_cmd.py`, `plan_tool/cli/lessons_cmd.py`, `plan_tool/bench.py`, …). Auto-binding would stamp `run_id` on those command families too — that is the phase-2 backfill, out of scope here. An opt-in method keeps phase 1 scoped to just the two `run_cmd.py` entrypoints (`cmd_run`, `_cmd_run_sweep`) that call it. (See the Deferred note on why `_cmd_run_reconcile` is *not* wired in phase 1.)

**Call the helper around the whole run body at both entrypoints in `plan_tool/cli/run_cmd.py`.**
- In `cmd_run`, wrap from just after `run_logger = RunLogWriter.start(...)` through the existing `try:` / `finally: run_logger.run_end(...)` so the scope brackets `run_step` and any decision it triggers. (Note `cmd_run` early-returns into `_cmd_run_reconcile` **before** this writer opens; that lane is a deliberate phase-2 deferral — see Deferred — so `cmd_run`'s scope intentionally does not cover it.)
- In `_cmd_run_sweep`, do the same around each iteration's writer and its per-iteration `try` / `finally: run_logger.run_end(...)`. Because each swept step opens its own writer and closes its own scope, one step's `run_id` is cleared before the next binds — no leak across the sweep.
- One way (cleanest, self-clearing): `with run_logger.telemetry_run_id_scope():` enclosing the existing `try/finally`. The cost is re-indenting an existing block. An acceptable minimal-diff alternative is a token pair — bind right after `start`, reset in the existing `finally` next to `run_end` — but the contextmanager guarantees the reset even if the `try` is never entered, so prefer it unless the re-indent is objectionable.

**Constraints that are not free to vary:**
- **Keep `run_log.py`'s leaf boundary.** Its module docstring states no first-party `plan_tool.*` imports at module top; honor that by importing telemetry lazily inside the helper, exactly as the sink methods lazy-import `plan_tool.shell`. `telemetry.py` is itself a stdlib-only leaf, so this edge creates no cycle — but the module-top rule still holds.
- **Clear on every exit path.** Success, error (`rc = 2`), and `KeyboardInterrupt` (`rc = 130`) all currently flow through the entrypoint's `finally`. The scope must reset on all of them — a contextmanager's exit (or a `finally` reset) covers this; do not reset only on the success return.
- **Restore the prior value, don't hard-set `""`.** Use step 1's scope helper / token reset so a nested or outer binding is restored, mirroring `shell.py`'s `push_active_notifier`/`pop_active_notifier` token pattern rather than a bare `set("")`.
- **`run_id` is `""` when no run is active.** This step wires only the two `run_cmd.py` entrypoints; every other command (including `run --reconcile` and the standalone `reconcile*` commands) leaves the ContextVar at its default, so their decisions keep `run_id = ""`. That is the intended phase-1 state, not a gap.
- **The binding is not inert in phase 1 — a concrete producer exists.** `record_prompt_budget(phase="run-step")` fires from `launcher.py:run_step` (and the run invoker's prompt-budget check in `plan_tool/shell.py`) inside `cmd_run`/`_cmd_run_sweep`'s scope on the main thread, so this step's binding stamps a non-empty `run_id` on those real phase-1 events. Verify that concretely (see Tests), not only via a hand-entered scope. (The #117 `record_code_reveals_split` detector is **not** a phase-1 producer here — it fires only in the standalone review/reconcile-plan lane, deferred to phase 2; see Deferred.)
- **Off-thread caveat (accepted phase-1 limit).** Because `ContextVar` is per-thread and a freshly spawned thread starts with a *clean* context, a `record_decision` fired from a **worker thread** created inside a run reads the default `""` — the parent's binding does not propagate. Phase-1 producers record on the main thread, so this is a known coverage limit (documented in the plan's Risks), not a correctness bug; propagating into worker threads is phase-2 scope.

## Tests

All new tests live in `tests/test_run_log.py` (pure `tmp_path`, no claude shell-out). Add them with the implementation; every one must be green before this step is done.

- `test_telemetry_run_id_scope_binds_writer_run_id` — inside `run_logger.telemetry_run_id_scope()`, the active telemetry `run_id` equals `run_logger.run_id` (assert via step 1's reader, or by recording a decision under `tmp_path` and reading it back with `read_decisions`).
- `test_telemetry_run_id_scope_resets_on_exit` — after the scope exits, the active `run_id` is back to its prior value (`""` by default).
- `test_telemetry_run_id_scope_resets_prior_value` — set an outer `run_id`, enter the scope (inner == writer's `run_id`), exit → the outer value is restored, not `""`.
- `test_telemetry_run_id_scope_resets_on_exception` — a body that raises still resets the ContextVar (the clear is a `finally`/`__exit__`, not tied to the success path).
- `test_recorded_decision_inside_scope_carries_run_id` — record a decision inside the scope and assert the persisted event's `run_id` equals the writer's `run_id`; a decision recorded outside any scope carries `""`.
- `test_two_writers_do_not_leak_run_id` — open two writers with distinct `run_id`s (the sweep shape); each scope binds its own id and clearing one restores `""`, proving no cross-run leak.

### Test-creation order (feature step)

This is a **feature** step. Write the tests above alongside the `RunLogWriter` helper and the two entrypoint call sites. Green-before-done gate: all six new tests pass, and the existing `tests/test_run_log.py` suite stays green.

## Acceptance criteria

- `RunLogWriter` has an opt-in scope helper that, while active, makes the telemetry active `run_id` equal the writer's `run_id`, and resets it to the prior value on exit (including on exception).
- `cmd_run` and `_cmd_run_sweep` in `plan_tool/cli/run_cmd.py` call that helper around their run body; a decision recorded during a `run` carries that run's `run_id`.
- The binding is **demonstrably non-inert in phase 1**: the concrete in-run producer `record_prompt_budget(phase="run-step")` (`launcher.py:run_step`, main thread) fires within the scope and stamps a non-empty `run_id`. The plan names this producer explicitly rather than leaving the effect implicit.
- A decision recorded outside any run carries `run_id = ""`; no `run_id` leaks into a later run or a non-run command.
- `RunLogWriter.start` is unchanged in effect for the other ~13 start sites (create/detail/completeness, the `run --reconcile` lane, and the standalone `reconcile`/`reconcile-all`/`reconcile-plan` writers) — they do not begin stamping `run_id` (still `""`). Only the two `run_cmd.py` entrypoints opt in.
- `plan_tool/run_log.py` keeps its module-top no-first-party-import boundary (telemetry is imported lazily inside the helper).
- The six new `tests/test_run_log.py` cases pass and the existing suite stays green.

## References

- [contextvars — Context Variables — Python 3.13 documentation](https://docs.python.org/3/library/contextvars.html) — `ContextVar.set`/`reset` and `Token` semantics behind the finally-cleared, prior-value-restoring scope this step drives.
- [contextlib — @contextmanager — Python 3.13 documentation](https://docs.python.org/3/library/contextlib.html#contextlib.contextmanager) — for shaping the `RunLogWriter` scope helper as a generator-based context manager whose exit is the clear.

## Deferred

- **Binding at the other `RunLogWriter.start` entrypoints** (create/detail via `plan_tool/cli/authoring.py`, `plan_tool/cli/completeness_cmd.py`, `plan_tool/cli/reconcile.py`, `plan_tool/cli/gates_cmd.py`, `plan_tool/cli/lessons_cmd.py`, `plan_tool/bench.py`) — those also open writers and call `record_decision`-family recorders (`record_create_step_outcome`, `record_plan_criteria_breakdown`, `record_audit_coverage`, `record_convergence`), but wiring them is the phase-2 "backfill everywhere" slice, not phase 1. They opt in later by calling the same helper.
- **The `run --reconcile` lane (`_cmd_run_reconcile`, `plan_tool/cli/reconcile.py`)** is **deliberately deferred to phase 2**, even though `cmd_run` early-returns into it. Rationale: it runs `run_step(mode="run-reconcile")` — a code-editing claude subprocess that never enters the in-process review pipeline — so it does **not** fire `record_code_reveals_split` (that #117 detector fires only inside `review.py:extract_recommendations` via `review_plan_full`, reached from the standalone `reconcile-plan`/`review` commands and `bench.py`). The only phase-1 recorder it would touch is the low-value `run-step` prompt-budget check, so wiring it now buys almost nothing and widens scope into `reconcile.py`. The flagship `record_code_reveals_split` gets its `run_id` when the review-lane entrypoints are wired in phase 2.
- **Adding new decision sites** — this step sets `run_id` on existing decisions during a run; it adds no new `record_decision` calls (plan Out of scope).
- **The resolver that consumes `run_id`** — the `plan-tool telemetry` analysis surface is phase 3; this step only produces the key.
