# Step 3 — Stop completeness iteration and show the structural recommendation

## Summary

Make `completeness-audit --iterate` stop before another apply round when step 2 identifies a recurring, high-impact structural seam. Update `plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop()` to translate the diagnosis result into the new `should_continue()` stop signal and print the matching recommend-only command. Add focused loop tests in `tests/cli/test_completeness_cmd.py`. On green, a qualifying history stops with `"structural"` and gives the operator the existing localized, scope-out, or re-seed recommendation without changing plan structure.

## Table of Contents

- [Summary](#summary) — The live-loop behavior and visible result.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why the loop needs history-aware stopping.
- [Input](#input) — Upstream diagnosis and fork-selection contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two files this step changes.
- [Implementation](#implementation) — How the loop consumes and presents the structural stop.
- [Tests](#tests) — Regression and feature coverage for the live loop.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Test-isolation and output-capture documentation.
- [Deferred](#deferred) — Work intentionally left to other steps.

## Why

`plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop()` currently decides from the current deterministic finding set and local budget state, so it can spend another round on a seam that saved completeness history already shows is recurring and not shrinking. Step 2 provides the history-derived structural-stop fact, but this loop must consume it and show the operator the diagnosis-owned remedy instead of treating the result like an ordinary stall or budget limit.

## Input

- **Step 1 live history:** Use step 1’s diagnosis-owned operation for the effective completeness history. It must preserve the current-run count-once rule, including replacement of this invocation’s `write_pre_apply_audit_checkpoint()` snapshot.

- **Step 2 stop contract:** Read the caller-supplied structural signal on `plan_tool/convergence.py:ConvergenceState` and the stable `(False, "structural")` result from `should_continue()`.

- **Diagnosis and fork contract:** Use `plan_tool/convergence_diagnosis.py:diagnose_convergence()`, the step-2 high-impact structural-stop predicate, and `classify_fork()` to reuse recurrence and recommendation selection. `ForkRecommendation.command` is the command shown to the operator.

- **Current report inputs:** Build the prospective live completeness snapshot from the same conceptual recommendations that `_run_iterate_convergence_loop()` preserves in `_IterateOutcome.audit_recs`; do not trigger another conceptual audit to decide whether to stop.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/cli/completeness_cmd.py` — translate diagnosis into the loop state and render the recommend-only structural next step.
  - `tests/cli/test_completeness_cmd.py` — add synthetic-history coverage for structural stopping, normal continuation, output, and no-mutation behavior.

## Implementation

- **Foundational logic: live structural-stop translation.** In `plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop()`, derive the step-2 structural-stop fact from the effective completeness history before each decision point that could start another iteration. Set that caller-supplied fact on the existing `ConvergenceState`, then continue to use `should_continue()` as the only loop-stop gate.

- **Scope history to this loop before diagnosis.** Use the step-1 history assembly outcome filtered to completeness reports for this plan before `diagnose_convergence()` and the step-2 predicate. Do not let reconcile history select a completeness-loop remedy, and do not compare titles, anchors, impact values, run counts, or finding counts inside the CLI loop.

- **Use the current audit without another backend call.** The up-front conceptual audit is already held in `_audit_recs` and checkpointed by `write_pre_apply_audit_checkpoint()`. Feed its report-eligible recommendations into the prospective live snapshot so a qualifying seam can stop before `apply_finding` dispatches another deterministic finding.

- **Preserve the checkpoint rule.** The live diagnosis must identify this invocation’s pre-apply checkpoint as transient and replace it with the prospective current run. Do not treat the checkpoint and live result as two recurrence samples.

- **Render the selected recommendation only on a structural stop.** In the `if not cont:` branch of `_run_iterate_convergence_loop()`, when `reason == "structural"`, call `classify_fork()` on the same diagnosis and append its existing recommend-only `ForkRecommendation.command` to the terminal guidance. Keep the command unchanged: localized evidence uses the split recommendation, scope-out evidence uses the scope-out command, and structural evidence uses the existing re-seed command.

- **Keep the stop reason and outcome intact.** Store `"structural"` in `_loop_stop_reason`, preserve the normal `_IterateOutcome` and report-finalization path, and do not turn this advice into an early error exit. The final completeness report should still be persisted through `finalize_completeness_run()`.

- **Do not mutate structure.** This loop only prints advice. It must not call `plan_tool/scope_out.py:scope_out_step` or `plan_tool/launcher.py:escalate_to_split`, and it must not weaken their existing `--apply` and confirmation gates.

- **Keep existing stops higher priority.** The CLI should request the structural signal, not bypass `should_continue()` ordering. Disabled iteration, convergence, iteration limits, deadlines, advisory-only findings, marginal progress, and no-progress retain their current behavior when they win first.

## Tests

- `test_iterate_structural_history_stops_before_apply_and_prints_fork_command` — seed qualifying prior completeness reports plus a high-impact current audit finding; assert `"structural"`, zero `apply_finding` calls, and the selected recommend-only command in captured terminal output.

- `test_iterate_structural_history_uses_effective_current_run_once` — include this invocation’s checkpoint and assert the live diagnosis uses the step-1 count-once history rather than treating the checkpoint as another recurrence pass.

- `test_iterate_nonrecurring_high_impact_finding_continues_normally` — a high-impact finding without qualifying recurrence does not request the structural stop and reaches the normal apply path.

- `test_iterate_structural_stop_preserves_existing_higher_priority_reason` — a state with an existing terminal condition reports that condition instead of structural advice.

- `test_iterate_structural_stop_does_not_call_structure_mutators` — assert the loop prints advice without invoking `scope_out_step` or `escalate_to_split`.

- `test_iterate_structural_stop_persists_final_report` — the standard `finalize_completeness_run()` path still receives and persists the structural-stop outcome.

### Test-creation order (feature step)

1. `test_iterate_structural_history_stops_before_apply_and_prints_fork_command` — add the positive live-loop case and prove the loop avoids another apply pass.

2. `test_iterate_structural_history_uses_effective_current_run_once` — add the checkpoint control so the diagnosis cannot qualify from double-counting.

3. `test_iterate_nonrecurring_high_impact_finding_continues_normally` and `test_iterate_structural_stop_preserves_existing_higher_priority_reason` — add narrow negative and ordering controls.

4. `test_iterate_structural_stop_does_not_call_structure_mutators` and `test_iterate_structural_stop_persists_final_report` — verify recommend-only behavior and normal report completion.

Every new test must be green before this step is considered finished.

## Acceptance criteria

- A qualifying step-2 structural-stop diagnosis makes `_run_iterate_convergence_loop()` stop with `stop_reason == "structural"` before it starts another apply round.

- The terminal guidance includes the unchanged `ForkRecommendation.command` selected by `classify_fork()`.

- The loop derives recurrence through the step-1 history operation and diagnosis APIs, with no CLI-local recurrence heuristic.

- A non-recurring high-impact finding still follows normal completeness iteration.

- Existing higher-priority `should_continue()` reasons remain visible instead of being replaced by `"structural"`.

- The structural stop does not call `plan_tool/scope_out.py:scope_out_step` or `plan_tool/launcher.py:escalate_to_split`.

- `tests/cli/test_completeness_cmd.py` passes.

## References

- [pytest monkeypatch documentation](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Isolate saved-history, diagnosis, and mutation seams in the loop tests.

- [pytest capturing output documentation](https://docs.pytest.org/en/stable/how-to/capture-stdout-stderr.html) — Assert the recommend-only terminal guidance.

## Deferred

- Reconcile-loop integration — step 4 applies the same step-2 stop contract in `plan_tool/cli/reconcile.py`.

- Recurrence-window and fork-classification changes — step 2 and `plan_tool/convergence_diagnosis.py:classify_fork()` remain the owners of those rules.
