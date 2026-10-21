# Step 7 — Stop the reconcile iterate loop on a recurring high-impact seam

## Summary

Wire the impact-recurrence classifier into `plan_tool/cli/reconcile.py`'s `_iterate_reconcile_loop` so the loop stops when the same still-open high-impact seam keeps coming back across the newest three `detail-reconcile` passes for the step being reconciled. Each pass through the `while True:` head refreshes one new `ConvergenceState` field (step 5's) from the saved report history, so `should_continue` can return `"structural_stop"` before the loop spends another `run_step` call. The key decision: refresh the flag at the **top of the loop only**, not beside the three existing `has_blocking_findings` assignments — every `continue` path funnels back through the loop head, so one refresh covers all of them. On green, a qualifying history halts the loop with `structural_stop`, prints step 4's recommended next command, and calls no further `run_step`; a non-qualifying history behaves exactly as it does today.

## Table of Contents

- [Summary](#summary) — what changes and the observable result.
- [Why](#why) — what the reconcile loop can't see today.
- [Input](#input) — the history and classifier contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched.
- [Implementation](#implementation) — where the check runs, how the history is scoped, and what must not move.
- [Tests](#tests) — cases to add in `tests/test_cli.py`.
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes.
- [References](#references) — the docs worth opening for this step.
- [Deferred](#deferred) — what this step leaves to other steps.

## Why

`_iterate_reconcile_loop` decides whether to keep going purely from the current pass's recommendations: it records the finding-id set with `record_iteration` and sets `conv_state.has_blocking_findings` from `is_blocking_impact`. Neither sees across passes. A step whose reconcile findings keep re-raising the same consequential seam therefore burns every pass up to `max_iterations` and exits reporting a plain limit stop, which reads to an operator like "out of rounds" rather than "this step needs re-decomposing". The evidence to tell the difference is already on disk — the loop writes a fresh `detail-reconcile` sidecar with `save_review` before each walk — so the fix is reading it, not producing anything new. Step 6 does the same wiring for the completeness loop; this step is the reconcile half.

## Input

- **Saved `detail-reconcile` sidecars are the evidence.** The loop calls `save_review(..., kind="detail-reconcile", step_id=step_id, ...)` before each walk, and the caller's iteration-0 save landed before the loop started. So by the time the loop head runs, `plan_tool/convergence_diagnosis.py:load_report_history(plan_path)` already includes every completed pass. Unlike the completeness loop, this loop needs **no in-memory current-run snapshot** — do not build one.
- **The normalized history model** — `ReportHistory` / `RunSnapshot` / `RunFinding` in `plan_tool/convergence_diagnosis.py`. `HISTORY_KINDS` already admits `detail-reconcile`, and `series_key` scopes reconcile series per `(kind, step_id)`.
- **The classifier from step 3, plus step 4's recommendation** — step 3 produces `plan_tool/impact_recurrence.py:classify_impact_recurrence(history, *, window=...)` returning a frozen result carrying the trigger flag, the outcome token, the non-trigger reason, and the seam's focus/counts. Step 4 produces the recommend-only next action and its rendered text off that same result. Read both by their landed names; don't re-derive either.
- **The stop reason from step 5** — `ConvergenceState` carries a caller-set boolean and `should_continue` returns `(False, "structural_stop")` when it is set and no earlier stop fired.
- **Verification limit:** impact provenance only lands on sidecars written after step 2, so on a real repo the stop is inert until three new passes accumulate. All coverage here uses stubbed classifier results or synthetic sidecars.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/reconcile.py` — import the classifier and step 4's renderer at module top; refresh the new `ConvergenceState` field at the `while True:` head from the step-scoped history; add a `structural_stop` arm to the existing stop-reason print block.
  - `tests/test_cli.py` — a new `TestIterateReconcileLoopStructuralStop` class beside the existing `_iterate_reconcile_loop` classes.

## Implementation

**What must be true when the step is done**

- Before each `should_continue(conv_state)` call in `_iterate_reconcile_loop`, `conv_state` carries the step-5 recurring-seam boolean, computed from the saved `detail-reconcile` history for **this** `step_id`.
- When the classifier triggers and no earlier stop reason fires, the loop halts with reason `structural_stop`, prints the seam plus step 4's recommended command, and does **not** call `run_step` again.
- When it does not trigger, every existing stop reason, drift path, and triage short-circuit behaves as it does today.

**Where the check runs**

- Put the refresh at the **top of the `while True:` body, immediately before `cont, reason = should_continue(conv_state)`**. This is the part that is not free to vary:
  - It runs **before** the pre-iteration drift check and before `run_step`, so a qualifying seam costs no backend pass — the whole point of the stop.
  - Every `continue` in the loop (the `halt_merged` arm and the collision merge-continue arm) returns to this head, so one refresh covers all of them. Do **not** mirror the three scattered `conv_state.has_blocking_findings = any(is_blocking_impact(...))` assignments; that pattern exists because those sites each have their own `recs` list, and copying it here would give three chances to drift.
  - Returning early from the loop head keeps the existing `if not cont:` arm's `_emit_scope_guard_plan(...)` call and the `iteration_session` context-manager cleanup on the exit path. Never add a bare `return` outside that arm.
- One way to keep the head readable: a small module-level helper in `plan_tool/cli/reconcile.py` (e.g. `_recurring_seam_for_step(plan_path, *, step_id)`) that loads the history, scopes it, calls the classifier, and returns the result. The loop head then assigns the flag and stashes the result for the print. This is a recommendation, not a requirement.

**Scoping the history**

- **Filter to this step's reconcile series before classifying.** Keep only runs whose `kind == "detail-reconcile"` and whose `step_id == step_id`, and hand the classifier a `ReportHistory` built from that subset. The classifier partitions by `series_key` itself, but filtering first is what guarantees a `completeness` series or a sibling step's seam can never stop *this* step's loop.
- **Reuse `load_report_history`; do not re-glob or re-parse sidecars.** It is total by design — an absent reports dir yields an empty history, an unparseable sidecar is skipped — so the refresh needs no try/except of its own.
- Reloading once per pass is cheap and spends no Claude; `max_iterations` bounds the number of reloads. Don't cache across passes — the loop writes a new sidecar every pass and a stale cache would make the stop unreachable.

**Printing the stop**

- Extend the existing reason-specific block inside `if not cont:` — the one already carrying `if reason == "max_iterations" and last_iter_high_critical:` and `elif reason == "time_budget_exceeded":` — with an `elif reason == "structural_stop":` arm. Match those arms' shape: a `plan-tool: …` line on `stderr` naming the step, the seam, and step 4's recommended command.
- **Print step 4's recommendation; never act on it.** The loop must not call `scope_out_step`, `escalate_to_split`, `plan-tool split`, or any other mutator. Recommendation selection and structural mutation have separate owners, and this stop is a safety brake, not an edit.
- **Do not change the return type or any exit code.** `_iterate_reconcile_loop` returns `None`; the caller's rc is unaffected. A structural stop is a completed run, and the tool's convention is that subcommands exit non-zero only on failure-to-complete. The "non-successful outcome" the plan asks for is the printed token and reason, not an rc flip.
- Optional, if it fits the surrounding style: record the stop on `run_logger` the way other terminal branches note their reason. Skip it rather than inventing a new run-log event shape.

**Constraints and gotchas**

- **Import at module top, into this module's namespace.** `plan_tool/cli/reconcile.py` already imports `plan_tool.review_persistence`, `plan_tool.launcher`, and `plan_tool.convergence`, so pulling in `plan_tool.impact_recurrence` (which sits below the CLI and imports `convergence_diagnosis`) adds no cycle. A module-global binding is also what lets tests monkeypatch `plan_tool.cli.reconcile.classify_impact_recurrence` — the same seam the suite already uses for `reconcile_module.run_step` and `reconcile_module.build_low_impact_demotion_lookup`.
- **Leave `is_blocking_impact` and `build_low_impact_demotion_lookup` alone.** The calibrated demotion policy stays scoped to `has_blocking_findings`; the seam flag is a separate field fed by a separate classifier.
- **Don't touch the triage short-circuit or either drift path.** They own their own returns and their own messages.
- **Don't reorder the stop reasons.** `structural_stop` is an otherwise-continuing stop (step 5's ordering rule), so `max_iterations`, `time_budget_exceeded`, `converged`, and the rest still win when they apply.
- **Rejected alternative:** running the classifier after `record_iteration` at the loop tail and stopping there. It reads more naturally next to the other convergence bookkeeping, but the tail is skipped by both `continue` arms, so a seam that recurs across drift-merge passes would be missed — and a tail stop would have to duplicate the `_emit_scope_guard_plan` cleanup the head arm already does.

## Tests

All cases go in `tests/test_cli.py`, in a new `TestIterateReconcileLoopStructuralStop` class placed after `TestIterateReconcileLoopCalibration`. Reuse `TestIterateReconcileLoopTriage()._seed_minimal(tmp_path)` for the plan/args/context fixture (the sibling classes already delegate to it), stub `reconcile_module.run_step` and `reconcile_module._walk_with_reconcile_phase`, and set `args.allow_drift = True` where a case shouldn't exercise the drift paths. Stub the classifier at `reconcile_module.classify_impact_recurrence` rather than writing three real sidecars, except in the one end-to-end case noted below.

- `test_structural_stop_halts_before_the_next_run_step` — classifier returns a triggered result; assert `run_step` is never called and the loop returns.
- `test_structural_stop_reason_is_printed` — stdout carries the halted-after-N-passes line with reason `structural_stop`.
- `test_structural_stop_prints_the_recommended_command` — stderr carries step 4's recommended next command for the seam.
- `test_structural_stop_does_not_mutate_the_plan` — plan file bytes are unchanged across the stopped loop.
- `test_untriggered_classifier_leaves_the_loop_unchanged` — classifier returns not-triggered; the loop still runs its passes and exits on an existing reason.
- `test_classifier_receives_only_this_steps_detail_reconcile_runs` — capture the history handed to the classifier; assert every run has `kind == "detail-reconcile"` and the loop's `step_id`, given a reports dir also holding a `completeness` sidecar and another step's reconcile sidecar.
- `test_classifier_is_refreshed_each_pass` — count classifier calls across a multi-pass loop; assert one per pass, not one per loop.
- `test_classifier_is_refreshed_after_a_merge_continue` — drive the `halt_merged` continue arm and assert the classifier ran again at the loop head.
- `test_max_iterations_outranks_structural_stop` — a triggered classifier plus an exhausted budget still reports `max_iterations`.
- `test_converged_outranks_structural_stop` — an empty rec set after a pass still reports `converged`.
- `test_scope_guard_plan_is_emitted_on_a_structural_stop` — `_emit_scope_guard_plan` runs on the stop path, same as every other loop exit.
- `test_structural_stop_does_not_change_the_exit_path` — the helper returns `None` and the caller's rc is untouched.
- `test_empty_history_does_not_stop_the_loop` — no sidecars on disk; the loop proceeds normally with no exception.
- `test_three_saved_reconcile_passes_trigger_the_real_classifier` — the one end-to-end case: write three real `detail-reconcile` sidecars carrying the same explicit high-impact finding via `save_review`, run the loop with the real classifier, assert it stops with `structural_stop`.

### Test-creation order (feature step)

This is a **feature** step. Write the tests above alongside the implementation, starting with the halt-before-`run_step` case so the placement decision is pinned before the printing and scoping details are tuned. Green-before-done gate: every new test must pass, plus the existing `_iterate_reconcile_loop` classes in `tests/test_cli.py` (`uv run pytest tests/test_cli.py -q`), before this step is finished.

## Acceptance criteria

- `_iterate_reconcile_loop` assigns step 5's recurring-seam field on `ConvergenceState` before every `should_continue` call.
- A triggered classifier result halts the loop with reason `structural_stop` and zero further `run_step` calls.
- The stop path prints the reason to stdout and step 4's recommended command to stderr, and calls `_emit_scope_guard_plan`.
- The history handed to the classifier contains only `detail-reconcile` runs for the loop's `step_id`.
- `_iterate_reconcile_loop` still returns `None` on every path, and no exit code changes.
- `grep -n "scope_out_step\|escalate_to_split" plan_tool/cli/reconcile.py` returns nothing added by this step.
- `is_blocking_impact` and `build_low_impact_demotion_lookup` usage in `plan_tool/cli/reconcile.py` is unchanged.
- `uv run pytest tests/test_cli.py -q` is green, and the full suite (`uv run pytest tests/ -q`) shows no new failures.

## References

- [Python `dataclasses` — Data Classes](https://docs.python.org/3/library/dataclasses.html) — `frozen=True` and `field` semantics for reading the classifier's result record and for building a scoped `ReportHistory`.
- [pytest — How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — the compact way to write the stop-reason precedence cases as a table.
- [pytest — How to use temporary directories and files (`tmp_path`)](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — the hermetic fixture the end-to-end three-sidecar case needs.

## Deferred

- **The classifier itself** — `plan_tool/impact_recurrence.py` is steps 3 and 4's work; this step calls it.
- **The `structural_stop` reason and its ordering** — step 5 owns them in `plan_tool/convergence.py`.
- **The completeness loop's wiring** — step 6 owns `plan_tool/cli/completeness_cmd.py` and `plan_tool/cli/completeness_phases.py`.
- **Documentation and BACKLOG #158 bookkeeping** — step 8.
- **Applying any structural remedy on a stop** — remediation stays recommend-only across this whole plan.
- **The `run-reconcile` series** — only the `detail-reconcile` history this loop writes is read. Wiring the run-reconcile direction needs its own evidence review.
- **The triage-deferred short-circuit's missing `_emit_scope_guard_plan` call** — an existing gap on the all-deferred return path, unrelated to this stop; file it in `BUG_BACKLOG.md` rather than fixing it here.
- **Threading the stop into the `create` and `detail` loops** — the plan defers both.
