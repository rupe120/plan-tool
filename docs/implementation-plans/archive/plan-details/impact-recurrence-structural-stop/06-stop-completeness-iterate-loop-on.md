# Step 6 — Stop the completeness iterate loop on a recurring high-impact seam

## Summary

Wire the impact-recurrence classifier into `completeness-audit --iterate` so the loop stops before its next Claude pass only after normal apply work and report persistence have completed. `plan_tool/cli/completeness_phases.py` gains a history builder and classifier helper; `_run_iterate_convergence_loop` refreshes the caller-supplied state field at the post-apply/pre-next-pass boundary. On green, a qualifying plan prints a terminal block naming the seam plus step 4's recommend-only next action, stops with `structural_stop`, preserves deterministic fixes and normal report persistence, and exits 0.

## Table of Contents

- [Summary](#summary) — what gets wired where and what an operator sees on a qualifying plan.
- [Why](#why) — why the completeness loop keeps paying for a seam it cannot close.
- [Input](#input) — the classifier, stop reason, and saved history this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — the three declared files and the edits in each.
- [Implementation](#implementation) — where the check runs, how the history is built, and the constraints that are not free to vary.
- [Tests](#tests) — the cases in `tests/cli/test_completeness_cmd.py`.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors.
- [References](#references) — the docs worth reading for this step.
- [Deferred](#deferred) — what this step leaves to step 7 and to follow-up work.

## Why

`_run_iterate_convergence_loop` in `plan_tool/cli/completeness_cmd.py` decides whether to keep going purely from its own round counters: `should_continue(state)` reads iteration count, wall-clock, the open-finding set, and the stall counter. None of those see across invocations. So a plan whose same high-impact region has been rediscovered by the conceptual audit on three straight runs gets a fourth full audit-plus-apply pass, and the loop exits reporting `converged` or `all_auto_apply_findings_deferred` as if the run went fine. The evidence to do better is already on disk — every completeness run persists its recommendations to a sidecar, and step 2 keeps each finding's impact through history normalization — it was just never read by the live loop. This step reads it and stops.

## Input

- **Step 3's classifier** — takes an already-loaded history and returns a frozen result saying whether a still-open, explicitly high-impact region recurred across the newest three consecutive compatible passes, with a machine-readable reason when it did not. It never touches disk, so this step owns assembling the history.
- **Step 4's outcome** — the recommend-only next action and its rendered text for a triggered result. This step prints what step 4 produces; it does not choose or apply a remedy.
- **Step 5's outcome** — `plan_tool/convergence.py:should_continue` returns the `structural_stop` reason from a caller-supplied field on `ConvergenceState`, ordered after every existing stop check. This step sets that field; it does not change the ordering.
- **Saved completeness history** — `plan_tool/convergence_diagnosis.py:load_report_history` yields one `RunSnapshot` per on-disk `kind="completeness"` sidecar, each carrying `plan_fingerprint`, `code_fingerprint`, `code_fingerprint_present`, `findings`, and `annotations`.
- **This invocation's own evidence** — `_audit_recs` (both conceptual sources, `plan-correctness` + `plan-completeness`) inside `_run_iterate_convergence_loop`. These are the only findings carrying an impact tag; the deterministic well-formedness findings from `_open_findings_now` carry none.
- **Verification limit** — impact provenance only exists on sidecars written after step 2 ships, so on a real repo the stop is inert until three new passes accumulate. All coverage here uses synthetic histories written into `tmp_path`, or a stubbed classifier.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/completeness_phases.py` — add a live-history builder for the completeness series and a thin classify helper that runs step 3's entry point over it and returns its result.
  - `plan_tool/cli/completeness_cmd.py` — in `_run_iterate_convergence_loop`, call the classify helper once after `write_pre_apply_audit_checkpoint` and before `while True:`, set the `ConvergenceState` field step 5 added, and add a `structural_stop` branch to the loop's stop-message hint block.
  - `tests/cli/test_completeness_cmd.py` — unit tests for both helpers and for the loop's stop behavior.

## Implementation

**What must be true when the step is done:** a completeness iterate run over a plan whose saved history plus current pass trips step 3's classifier stops before its first `apply_finding` call, reports `structural_stop` as its stop reason, prints the seam and step 4's recommended command, exits 0, and persists a report — and a run over any other plan behaves exactly as it does today.

**Where the check runs — after apply, before the next Claude pass.**

- Refresh the classifier after an apply round has finished and its report/checkpoint is persisted, immediately before the next `should_continue(state)` decision. This is the boundary BACKLOG #158 specifies and leaves deterministic well-formedness convergence intact.
- Build the prospective newest run from the post-apply recommendations through step 2's normalization helper, including impact and provenance. Never hand-build a `RunFinding` that drops those fields.
- Require evidence that the conceptual seam was actually offered to `completeness-apply` or otherwise has a non-open resolution annotation; a recurrence of audit-only, never-attempted conceptual findings is not structural-stop evidence.
- When the classifier trips, set the state field and let `should_continue` preserve its established higher-priority stops; render both the impact result and any ordinary severity/decomposition diagnosis.

**Assembling the history (the helper in `plan_tool/cli/completeness_phases.py`).**

- Model it on `_completeness_convergence_diagnosis` in the same module, which already solves the count-once problem for the report: load with `load_report_history(path)`, keep only `kind == "completeness"` runs, drop this invocation's pre-apply checkpoint (the newest completeness snapshot on disk, because the checkpoint has already been written by the time the loop reaches this point), then append one in-memory `RunSnapshot` built from the current pass.
- Build the current snapshot from `_audit_recs` — the correctness and completeness recommendations carry the impact tag the classifier needs. Include the current deterministic findings too if it keeps the snapshot shape closer to what the final sidecar persists; they are inert to the classifier either way, since it only counts findings with an explicit high impact.
- Fill `plan_fingerprint` from `plan_tool/review_persistence.py:compute_plan_fingerprint` and `code_fingerprint` from `plan_tool/fingerprint.py:compute_code_fingerprint`, with `code_fingerprint_present=True` — both are computed at this call site, and step 3 breaks the streak on a code-fingerprint change, so a wrong or absent value silently makes the stop unreachable. The loop already holds a plan fingerprint in `_apply_verdict_plan_fp`; reuse it rather than re-hashing, but keep the empty-string fallback in mind — an empty fingerprint must not read as drift.
- Carry the post-apply annotations into the in-memory run so the classifier can distinguish an attempted/resolved finding from one that remains open.
- **Keep the helper a builder, not a diagnoser.** It returns a scoped `ReportHistory`. The classify helper beside it calls step 3's entry point and returns that result untouched. Splitting them keeps the history assembly testable without stubbing the classifier.

**Behavior on the stop.**

- Set `_loop_stop_reason` to the reason `should_continue` returned so it flows into `_IterateOutcome.stop_reason` and from there into the persisted report and the console summary.
- Add a `structural_stop` branch beside the existing `deadline_exceeded` / `max_iterations` / `no_progress` branches in the loop's stop-message hint block. Print step 4's rendered text for the seam and its recommended command; the existing `plan-tool reconcile-plan-walk` and diagnostic-remedy hints still apply and should stay.
- **Do not flip the exit code.** This is a completed audit, not a failure to complete. Do not route through `_halt` and do not set `early_exit_code` — the report must still be persisted and the command must still exit 0. `--fail-on-findings` keeps its own separate gate.
- **Recommend only; never mutate.** Print the command step 4 selected. Do not call `scope_out_step`, `escalate_to_split`, or any other structural actuator from this loop.

**Constraints that are not free to vary.**

- **Best-effort, never fatal.** Wrap the history load and classify in a `try/except Exception` and fall through to normal iteration on failure. A malformed sidecar must never break a completeness run. One way: log a one-line stderr note under the existing verbose stderr style and continue.
- **Audit-only mode is untouched.** Everything here lives inside the `if budget.enabled:` phase, so a run without `--iterate` never loads history and never classifies.
- **Do not touch `_completeness_has_blocking_findings`.** The `--json` blocking gate stays severity-only; this stop is a continuation decision, not a reporting gate.
- **Do not touch `convergence.is_blocking_impact`.** The classifier computes its own high-impact predicate; the calibrated demotion policy stays scoped to the callers it has today.
- **Keep `cmd_completeness` orchestration-only.** The history and classify helpers belong in `plan_tool/cli/completeness_phases.py`; the command module holds the wiring and the printed block. Follow the module's body-local domain-import convention (as `_completeness_convergence_diagnosis` does) so the existing monkeypatch seams keep intercepting.
- **`plan_tool/cli/completeness_phases.py` stays a leaf** — it must not import `plan_tool.cli.completeness_cmd`. Importing `plan_tool.impact_recurrence` and `plan_tool.convergence_diagnosis` is fine.

**Shared logic worth naming.** `_completeness_convergence_diagnosis` in the same module implements the same count-once rule (scope to the completeness series, drop this invocation's checkpoint, append the current run) that the new builder needs. This step adds the builder for the loop and leaves that function's body alone, so the step stays a pure wiring change; the new builder's docstring must cite it as the sibling owning the same rule, and a parity test pins that both produce the same scoped run list for the same inputs. Routing the existing function through the builder is a behavior-preserving consolidation — see `## Deferred`.

## Tests

All cases live in `tests/cli/test_completeness_cmd.py`, which already imports `_run_iterate_convergence_loop` and the private phase helpers from their owning modules. Loop tests stub the classify helper at its `plan_tool.cli.completeness_phases` name so no real history read is needed; the two helper tests build sidecars under `tmp_path`.

- `test_live_history_scopes_to_completeness_runs` — a history containing `detail-reconcile` and `run-reconcile` sidecars yields only the completeness runs.
- `test_live_history_drops_this_invocation_checkpoint` — the newest on-disk completeness snapshot is dropped and replaced by the in-memory current run, so the current pass is counted exactly once.
- `test_live_history_current_run_carries_audit_recs_and_fingerprints` — the appended snapshot's findings come from the audit recs, and its plan/code fingerprints and `code_fingerprint_present` are set.
- `test_live_history_matches_report_diagnosis_run_list` — the builder and `_completeness_convergence_diagnosis` produce the same scoped run list for the same inputs; the drift guard between the two copies of the count-once rule.
- `test_classify_helper_returns_classifier_result_unchanged` — the thin helper passes the assembled history through and returns step 3's result as-is.
- `test_loop_stops_before_first_apply_on_qualifying_seam` — a triggered result makes the loop break at the first `should_continue`, with `apply_finding` never called.
- `test_loop_stop_reason_is_structural_stop` — the returned `_IterateOutcome.stop_reason` is the `structural_stop` reason, not `converged`.
- `test_loop_stop_prints_seam_and_recommended_command` — stderr carries the seam description and step 4's recommended command.
- `test_structural_stop_does_not_set_early_exit_code` — the outcome carries no `early_exit_code`, so the command still exits 0 and the report is still persisted.
- `test_loop_never_applies_a_structural_remedy` — no scope-out or split actuator is invoked on the stop path.
- `test_non_qualifying_result_leaves_loop_unchanged` — an untriggered result runs the normal apply rounds and reports the pre-existing stop reason.
- `test_classifier_is_called_once_per_invocation` — across a multi-round loop the classify helper is called exactly once.
- `test_classifier_failure_falls_through_to_normal_iteration` — the helper raising leaves the loop iterating as it does today.
- `test_existing_stop_reasons_still_win` — a run that would stop for `max_iterations` reports `max_iterations` even when the seam also qualifies.
- `test_audit_only_mode_never_classifies` — with the iterate budget disabled, neither helper is called.

### Test-creation order (feature step)

This is a **feature** step. Write the tests above alongside the implementation — start with the two helper tests so the history shape is pinned before the loop wiring is tuned. Green-before-done gate: every test listed here must pass (`uv run pytest tests/cli/test_completeness_cmd.py -q`) and the full suite must stay green before the step is finished.

## Acceptance criteria

- `plan_tool/cli/completeness_phases.py` exposes a live-completeness-history builder and a classify helper; neither imports `plan_tool.cli.completeness_cmd`.
- `_run_iterate_convergence_loop` calls the classify helper exactly once per invocation, after `write_pre_apply_audit_checkpoint` and before `while True:`.
- On a qualifying history the loop breaks at the first `should_continue`, `apply_finding` is never called, and `_IterateOutcome.stop_reason` is the `structural_stop` reason.
- The stop prints the seam and step 4's recommended command to stderr, and applies no structural remedy.
- `completeness-audit --iterate` still exits 0 on the stop path and still writes its report.
- A non-qualifying result, a classifier exception, and audit-only mode all leave loop behavior identical to today.
- `_completeness_has_blocking_findings` and `convergence.is_blocking_impact` are unchanged.
- `uv run pytest tests/cli/test_completeness_cmd.py -q` is green, and no new test carries `@pytest.mark.allow_real_claude`.

## References

- [Python `dataclasses` — Data Classes](https://docs.python.org/3/library/dataclasses.html) — `field` defaults and frozen-record semantics for the snapshot and result types this step passes around.
- [pytest — How to use temporary directories and files (`tmp_path`)](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — the hermetic fixture for the two helper tests that write and re-read completeness sidecars.

## Deferred

- **The reconcile iterate loop** — step 7 wires the same stop into `plan_tool/cli/reconcile.py`.
- **Routing `_completeness_convergence_diagnosis` through the new history builder** — a behavior-preserving consolidation of the count-once rule, left out so this step stays a pure wiring change; the parity test guards the two copies until a follow-up refactor step lands it.
- **Deduping prior invocations' checkpoint-plus-final sidecar pairs** — the existing accepted residual named in `_completeness_convergence_diagnosis`; the shared fix belongs in `plan_tool/convergence_diagnosis.py:load_report_history`, not here.
- **Rendering the seam inside the persisted report body** — the report carries the stop reason; a dedicated seam section would need `plan_tool/completeness_report.py`, which is outside this step's files.
- **An operator flag to disable or tune the stop** — the three-pass threshold stays a module constant in step 3, and no opt-out flag is added.
- **Re-classifying mid-loop** — the impact evidence is audited once per invocation, so a per-iteration re-check would return the same verdict.
