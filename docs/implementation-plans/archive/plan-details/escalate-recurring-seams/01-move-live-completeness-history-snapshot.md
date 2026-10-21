# Step 1 — Move the live completeness history snapshot into convergence diagnosis

## Summary

Move the logic that adds the current completeness run to history from `plan_tool/cli/completeness_phases.py:_completeness_convergence_diagnosis()` into `plan_tool/convergence_diagnosis.py`. Keep the CLI phase responsible for collecting the current report inputs and rendering the result, while convergence diagnosis owns the normalized `ReportHistory` and `RunSnapshot` shape. Preserve audit-only and iterate behavior: the current run appears exactly once, and the iterate checkpoint is excluded before the final live run is added. Green behavior produces the same convergence verdicts and report sections as before.

## Table of Contents

- [Summary](#summary) — Short review of the refactor and its unchanged result.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why live history assembly belongs with diagnosis.
- [Input](#input) — Persisted review and live recommendation contracts this reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by the refactor.
- [Implementation](#implementation) — Ownership, count-once rule, and integration constraints.
- [Tests](#tests) — Characterization and diagnosis-level coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable behavior on green.
- [References](#references) — Relevant API and test-isolation documentation.
- [Deferred](#deferred) — Work intentionally left for later steps.

## Why

`plan_tool/cli/completeness_phases.py:_completeness_convergence_diagnosis()` currently reads persisted history, removes an iterate checkpoint, converts live `Recommendation` objects into diagnosis models, and invokes the diagnosis. That duplicates ownership of `RunSnapshot` construction outside `plan_tool/convergence_diagnosis.py`, the module that defines and normalizes the cross-run model. Put the live completeness snapshot rule beside `load_report_history()` so callers cannot drift from the persisted-history contract or accidentally count the current run twice.

## Input

- **Saved report history:** `plan_tool/convergence_diagnosis.py:load_report_history()` reads `SavedReview` records through `plan_tool/review_persistence.py:list_saved_reviews()` and `load_review()`. Preserve its typed `HISTORY_KINDS` filtering and oldest-to-newest ordering.

- **Live completeness inputs:** `plan_tool/cli/completeness_phases.py:_persist_and_present_report()` has the final `sidecar_recs`, plan fingerprint, and code fingerprint before `write_completeness_report()` persists them. The diagnosis-side helper must accept enough of this data to create the same current completeness representation without requiring a CLI import.

- **Checkpoint contract:** `plan_tool/cli/completeness_phases.py:write_pre_apply_audit_checkpoint()` writes an iterate-only completeness sidecar before apply work. The final diagnosis must replace that invocation’s newest checkpoint with the current final snapshot, not retain both.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/cli/completeness_phases.py` — simplify `_completeness_convergence_diagnosis()` so it delegates live-history assembly to convergence diagnosis.
  - `plan_tool/convergence_diagnosis.py` — add the diagnosis-owned live completeness history/snapshot operation next to `RunSnapshot`, `ReportHistory`, and `load_report_history()`.
  - `tests/cli/test_completeness_cmd.py` — keep CLI characterization coverage for report wiring and count-once behavior.
  - `tests/test_convergence_diagnosis.py` — add direct tests for the diagnosis-owned live snapshot operation.

## Implementation

- **Make convergence diagnosis own the live-snapshot rule.** Add a helper near `load_report_history()` that combines saved history with a current completeness run built from the persisted fields available at report time. Keep `load_report_history()` focused on reading disk; do not make it depend on CLI state or `plan_tool.cli`.

- **Preserve the count-once rule.** For audit-only runs, retain all saved completeness runs and append one live current run. For iterate runs, remove only the newest completeness checkpoint for the current invocation before appending the live final run. The resulting history must contain the same number and order of effective completeness runs that `_completeness_convergence_diagnosis()` produces today.

- **Keep the current snapshot shape consistent with saved snapshots.** Use `RunSnapshot` and `RunFinding` fields that match `_snapshot_from_saved_review()`’s normalized model: completeness kind, no step id, current plan/code fingerprints, the live recommendations’ persisted finding fields, no annotations, and the existing unknown-report-size value. Do not add persistence fields or per-finding apply verdicts.

- **Keep scope in the CLI phase.** `plan_tool/cli/completeness_phases.py:_completeness_convergence_diagnosis()` should still request a completeness-only diagnosis before calling `diagnose_convergence()`. It should no longer independently construct `RunSnapshot`, `RunFinding`, or `ReportHistory`.

- **Preserve cross-series isolation.** The report’s convergence section must continue to diagnose only the completeness series. Saved `detail-reconcile` and `run-reconcile` runs remain available to the diagnosis module’s broader consumers but must not alter a completeness report’s verdict.

- **Keep the leaf import boundary.** `plan_tool/convergence_diagnosis.py` must remain independent of `plan_tool.cli`. Accept plain diagnosis inputs or existing domain models; do not import `_IterateOutcome`, CLI helpers, or report-rendering code.

- **Do not change render timing.** `plan_tool/cli/completeness_phases.py:_persist_and_present_report()` must still diagnose before `build_report_md()` and before the final sidecar write, because the live run is not yet on disk.

## Tests

- `test_live_completeness_snapshot_preserves_saved_runs` — diagnosis-level test that prior completeness snapshots remain in chronological order and one live snapshot is appended.

- `test_live_completeness_snapshot_replaces_current_checkpoint` — diagnosis-level test that the iterate flag removes the newest current completeness checkpoint and adds the final live run once.

- `test_live_completeness_snapshot_keeps_non_completeness_history_out_of_completeness_series` — diagnosis-level test that reconcile snapshots are not included in the returned completeness-series history used by the CLI report.

- `test_current_run_counted_once_audit_only` — retain the CLI characterization that two saved runs plus an audit-only live run diagnose as three completeness runs.

- `test_current_run_counted_once_iterate_after_checkpoint` — retain the CLI characterization that two prior runs plus a current checkpoint and final iterate run diagnose as three completeness runs.

- `test_spinning_history_renders_convergence_section` — retain the end-to-end report assertion that the refactored handoff still renders a spinning completeness section.

### Test-creation order (refactor step)

1. `test_live_completeness_snapshot_preserves_saved_runs` — pin the diagnosis module’s normalized live snapshot fields and chronological append behavior.

2. `test_live_completeness_snapshot_replaces_current_checkpoint` — pin the iterate checkpoint replacement rule directly at the new owner.

3. `test_current_run_counted_once_audit_only` and `test_current_run_counted_once_iterate_after_checkpoint` — confirm the CLI-facing behavior before the move.

The diagnosis-level and CLI characterization tests must stay green, unmodified, after the restructuring.

## Acceptance criteria

- `plan_tool/convergence_diagnosis.py` owns construction of the in-memory current completeness `RunSnapshot`.

- `plan_tool/cli/completeness_phases.py:_completeness_convergence_diagnosis()` no longer constructs `RunSnapshot`, `RunFinding`, or `ReportHistory`.

- An audit-only completeness report with two saved completeness runs diagnoses three effective completeness runs.

- An iterate completeness report with two prior runs and one current pre-apply checkpoint diagnoses three effective completeness runs, not four.

- A saved reconcile series does not change the completeness report’s convergence verdict.

- `tests/cli/test_completeness_cmd.py` and `tests/test_convergence_diagnosis.py` pass with the same report rendering behavior.

## References

- [Python dataclasses — Python 3.13 documentation](https://docs.python.org/3.13/library/dataclasses.html) — Use when evolving the frozen `RunSnapshot` and `ReportHistory` model without changing its value contract.

- [pathlib — Python 3.13 documentation](https://docs.python.org/3.13/library/pathlib.html) — Reference for the `Path` contract passed to `load_report_history()`.

- [pytest monkeypatch documentation](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use to isolate report rendering while asserting the diagnosis passed from the CLI phase.

## Deferred

- Full deduplication of checkpoint/final sidecar pairs from earlier iterate invocations — this step only moves the live current-run assembly rule; changing persisted-history cleanup needs separate reconciliation scope.
