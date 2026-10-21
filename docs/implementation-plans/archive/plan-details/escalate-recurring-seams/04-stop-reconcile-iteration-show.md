# Step 4 — Stop reconcile iteration and show the structural recommendation

## Summary

Make reconcile iteration stop before another `run_step` call when step 2 identifies a recurring, high-impact structural seam. Update `plan_tool/cli/reconcile.py:_iterate_reconcile_loop()` to pass the diagnosis result through `ConvergenceState` and use the existing `should_continue()` gate. Render the diagnosis-owned recommend-only command when the loop stops for `"structural"`. On green, the loop avoids another Claude pass, preserves already-landed work, and tells the operator which structural action to review.

## Table of Contents

- [Summary](#summary) — The behavior change and green result.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — Why reconcile iteration needs the history-aware stop.
- [Input](#input) — Saved-review and convergence contracts this loop reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two existing files changed by this step.
- [Implementation](#implementation) — The stop decision, recommendation output, and loop constraints.
- [Tests](#tests) — Focused loop coverage for the new behavior.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Test-isolation and captured-output documentation.
- [Deferred](#deferred) — Work intentionally left outside this step.

## Why

`plan_tool/cli/reconcile.py:_iterate_reconcile_loop()` currently decides whether to start another reconcile pass from local finding sets and budget state only. A saved `detail-reconcile` history can show that the same high-impact seam is recurring without shrinking, but the loop still spends another `run_step` pass. Step 2 supplies the structural-stop fact; this step must use it at the loop boundary and show the diagnosis-layer recommendation instead of trying another repair pass or changing the plan automatically.

## Input

- **Step 2 stop contract:** Consume step 2’s caller-supplied structural signal on `plan_tool/convergence.py:ConvergenceState` and preserve `plan_tool/convergence.py:should_continue()` as the only continuation gate.

- **Saved reconcile history:** Read `plan_tool/convergence_diagnosis.py:load_report_history()` for the plan path. Its `HISTORY_KINDS`, `ReportHistory`, and `series_key()` keep `detail-reconcile` findings separate by step.

- **Diagnosis and recommendation:** Use `plan_tool/convergence_diagnosis.py:diagnose_convergence()` plus step 2’s high-impact structural predicate to decide the signal. Use `plan_tool/convergence_diagnosis.py:classify_fork()` and `ForkRecommendation.command` for the operator-facing next step.

- **Current loop evidence:** `plan_tool/cli/reconcile.py:_iterate_reconcile_loop()` saves each `detail-reconcile` report through `save_review()` before walking it. Treat that persisted report, including the caller’s already-saved initial pass, as the history available to the next continuation decision; do not run an extra audit just to diagnose history.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/cli/reconcile.py` — derive the structural-stop fact at reconcile loop decision points and print the diagnosis-selected recommend-only command on a structural stop.
  - `tests/test_cli.py` — add isolated reconcile-loop tests for structural stopping, normal continuation, output, and no extra reconcile call.

## Implementation

- **Scope history to the active reconcile lane.** Before diagnosis, filter persisted history to the active reconcile kind and current step where applicable; a completeness or different-step reconcile series must not stop this loop or select its remedy.

- **Foundational logic — history-aware structural continuation stop.** In `plan_tool/cli/reconcile.py:_iterate_reconcile_loop()`, refresh the structural-stop fact before each `should_continue()` decision that could begin another iteration. Set that fact on the existing `ConvergenceState`, then let `should_continue()` return `(False, "structural")` only after its existing higher-priority terminal reasons have been considered.

- **Use the diagnosis layer as the single rule owner.** Build the effective history with `plan_tool/convergence_diagnosis.py:load_report_history()` and evaluate it with `diagnose_convergence()`. Use the high-impact predicate supplied by step 2 rather than comparing recommendation titles, anchors, impact values, recurrence counts, or finding IDs in the CLI loop.

- **Keep the reconcile series scoped.** The loop runs one `detail-reconcile` step at a time. Ensure a stop is driven by recurring evidence for the relevant reconcile series and step, not an unrelated completeness report or another reconcile step in the same plan history.

- **Present, do not apply.** When `reason == "structural"`, call `classify_fork()` for the same diagnosis and print its non-empty `ForkRecommendation.command` as the next recommend-only action. Do not call `scope_out_step`, create a seed, re-split a step, or otherwise mutate plan structure from this loop.

- **Preserve existing loop cleanup.** Route the structural exit through the same termination path that prints the halt reason and calls `_emit_scope_guard_plan()`. It must not bypass the `iteration_session` cleanup, drift safeguards, saved reviews, or already-applied findings.

- **Avoid an extra backend pass.** Check before the pre-iteration drift check and `run_step()` branch. A qualifying structural stop must make the next reconcile-call count zero while retaining reports and edits from earlier passes.

- **Leave other continuation reasons ordered.** The `"structural"` result is an otherwise-continuing stop supplied by step 2. Disabled iteration, convergence, iteration limits, deadlines, advisory-only findings, marginal overlap, and no-progress behavior must retain their current outcomes when they already stop the loop.

- **Do not expand sibling loops here.** `plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop()` is the separate completeness consumer addressed by step 3. `plan_tool/cli/run_cmd.py:cmd_run` does not own this reconcile loop.

## Tests

`tests/test_cli.py`

- `test_reconcile_loop_stops_for_high_impact_structural_history` — seeds qualifying saved `detail-reconcile` history, runs `_iterate_reconcile_loop()`, and asserts no additional `run_step()` call occurs.

- `test_reconcile_loop_prints_diagnosis_recommendation_on_structural_stop` — asserts the halt output includes `"structural"` and the non-empty command selected by `classify_fork()`.

- `test_reconcile_loop_continues_when_history_is_not_structural` — uses non-qualifying history and asserts the loop reaches its normal reconcile pass.

- `test_reconcile_structural_stop_preserves_existing_termination_cleanup` — asserts scope-guard emission and iteration-session cleanup still run on the structural exit without applying a structural mutation.

- `test_reconcile_structural_stop_does_not_override_existing_terminal_reason` — supplies a condition that already stops through `should_continue()` and asserts the existing reason wins over `"structural"`.

### Test-creation order (feature step)

1. Add `test_reconcile_loop_stops_for_high_impact_structural_history` with the loop wiring so the new stop cannot ship without proving the backend call is skipped.
2. Add `test_reconcile_loop_prints_diagnosis_recommendation_on_structural_stop` with the presentation branch so the displayed command stays diagnosis-owned.
3. Add the normal-continuation and terminal-reason controls before finishing the loop change.
4. Add the cleanup characterization after the structural exit shares the existing return path.

Every new test must be green before this step is considered finished.

## Acceptance criteria

- A qualifying step-2 structural signal causes `plan_tool/convergence.py:should_continue()` to return `(False, "structural")` only when no earlier stop reason applies.

- `plan_tool/cli/reconcile.py:_iterate_reconcile_loop()` stops before its next `run_step()` call when the relevant saved `detail-reconcile` history qualifies.

- A structural reconcile stop prints the non-empty recommend-only `ForkRecommendation.command` chosen by `plan_tool/convergence_diagnosis.py:classify_fork()`.

- The structural stop does not create a seed, call a scope-out operation, or change plan structure.

- Existing reports, prior applied edits, scope-guard emission, and iteration-session cleanup remain intact on the structural exit.

- The new `tests/test_cli.py` coverage passes with the existing reconcile-loop tests.

## References

- [pytest monkeypatch documentation](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use monkeypatching to isolate history loading, diagnosis, and `run_step()` in loop tests.

- [pytest capturing output documentation](https://docs.pytest.org/en/stable/how-to/capture-stdout-stderr.html) — Assert the structural halt reason and recommend-only command without relying on a real terminal.

## Deferred

- Completeness-loop adoption — Step 3 owns `plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop()`.

- Structural plan mutations — This step only presents `classify_fork()` output; executing a scope-out, split, or re-seed remains an operator action.
