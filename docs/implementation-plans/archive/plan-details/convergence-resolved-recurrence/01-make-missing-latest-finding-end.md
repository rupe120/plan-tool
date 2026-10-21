> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Make an absent or applied latest finding end recurrence

## Summary

Make recurrence require an unresolved matching finding in the newest run of each report series. Update `plan_tool/convergence_diagnosis.py` without changing the persisted-history model or public diagnosis/render interfaces. Add focused unit and CLI regressions in the declared test files. On green, an older repeated finding that is absent from the latest audit or applied there produces no spinning verdict or re-decompose command, while a finding that misses an earlier audit or reappears after application can still recur.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the change and its result.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The current false-positive recurrence behavior.
- [Input](#input) — Persisted-history and region-trend contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Required recurrence rule and preservation boundaries.
- [Tests](#tests) — Focused regression coverage for the new rule.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Relevant primary documentation.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this change.
- [Deferred](#deferred) — Related work owned outside this step.

## Why

`plan_tool/convergence_diagnosis.py:_recurs_in_window` currently counts appearances across the trailing window without requiring that the region remains unresolved in the newest series run. With the default two-of-three threshold, findings in the first two audits can still drive `VERDICT_SPINNING` after the latest audit no longer finds them or marks them applied, causing `classify_fork` and `render_diagnosis` to recommend re-decomposition for a resolved problem.

## Input

- **Saved history:** `load_report_history()` produces chronological `ReportHistory.runs`; `partition_series()` separates completeness and per-step reconcile histories before `_series_verdict()` evaluates them.
- **Region presence and current state:** `recurring_regions()` and `_freeze_region()` record observed appearances in `RegionTrend.run_indices` and read raw per-run annotations; an absent run is not stored as a zero count, and an `applied` annotation closes only that latest occurrence.
- **Compatibility boundary:** `RunFinding`, `RunSnapshot`, and persisted `Annotation` data come from `plan_tool/review_persistence.py`; keep their shapes and saved JSON compatibility unchanged.
- **Verification limit:** Tests can prove matching saved findings disappear from the newest run; they cannot make reformulated findings match more accurately, so preserve `_matches()` and `TITLE_SIMILARITY_CUTOFF`.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/convergence_diagnosis.py` — Require newest-run presence in the recurrence predicate used by `_region_spins()`.
  - `tests/test_convergence_diagnosis.py` — Cover newest-run absence, preserved earlier-miss tolerance, and the resulting series verdict.
  - `tests/cli/test_convergence_cmd.py` — Cover saved-sidecar diagnosis through `cmd_convergence` when currently apply-eligible findings are absent from, or applied in, the latest run. Step 2 updates both fixtures to structural evidence with its source-boundary change.

## Implementation

- **Foundational logic:** Treat a region as recurring only when it meets the existing trailing-window count and has an unresolved match in the newest run of its own series.

- **Keep the decision in the verdict path.** Update `_recurs_in_window()` or the private `_region_spins()` call chain so `_series_verdict()` supplies enough series-local context to distinguish an earlier missed run from a missing latest run. One suitable approach is to pass the final series index explicitly rather than infer it from the tolerance.

- **Make “latest” series-local.** Use the final `RunSnapshot` in the `snapshots` list passed to `_series_verdict()`, not `ReportHistory.runs[-1]` across all kinds. A newer completeness report must not make an older `detail-reconcile` series look resolved, or the reverse.

- **Keep the existing tolerance for earlier gaps.** `RECURRENCE_TOLERANCE` still permits a region that appears in the first and newest runs of a three-run window. The new rule only rejects a region whose qualifying appearances end before that series’s newest run or are all marked applied in that newest run.

- **Do not turn absence into a synthetic count.** Preserve `RegionTrend.run_indices`, `open_counts`, and `_windowed_open_counts()` as observed finding data. The recurrence gate decides whether the region is current; `_no_shrinkage()` should not receive invented zeroes for missing runs.

- **Preserve matching and closure rules.** Leave `recurring_regions()` and `_matches()` matching semantics intact. Keep sticky deliberate-decline closure, treat a fully applied latest match as currently closed, and let a later unannotated reappearance reopen recurrence evidence.

- **Preserve consumers and public interfaces.** Keep `diagnose_convergence()`, `render_diagnosis()`, `ConvergenceDiagnosis`, and `SeriesDiagnosis` usable as they are. `plan_tool/cli/convergence_cmd.py:cmd_convergence` should need no production change; its end-to-end test should prove the existing load → diagnose → render path reports the corrected verdict.

## Tests

Green-before-done: every test below must pass, along with the existing convergence diagnosis and CLI suites.

### Tests for this step

- `tests/test_convergence_diagnosis.py:test_recurrence_min_tolerates_one_missed_run` — Keep the positive two-of-three case when the region is present in the newest run and the miss is earlier.
- `tests/test_convergence_diagnosis.py:test_recurs_in_window_requires_latest_run_presence` — Reject a region that meets the count threshold only in older runs and is absent from the final series run.
- `tests/test_convergence_diagnosis.py:test_series_converges_when_matching_finding_is_missing_from_latest_run` — Three runs with a matching region in the first two and no match in the third produce `VERDICT_CONVERGING` with no recurring regions.
- `tests/test_convergence_diagnosis.py:test_series_uses_own_newest_run_not_global_history` — A newer completeness report does not end recurrence in an older `detail-reconcile` series whose own newest report still matches.
- `tests/test_convergence_diagnosis.py:test_applied_latest_finding_converges` — A fully applied latest match ends recurrence without changing persisted shapes.
- `tests/test_convergence_diagnosis.py:test_finding_reappearing_after_applied_latest_can_recur` — A later unannotated reappearance remains recurrence evidence.
- `tests/cli/test_convergence_cmd.py:test_missing_latest_finding_converges_without_redecompose_command` — Real sidecars with medium `plan-correctness` evidence in the first two runs and an empty newest run make `main(... convergence ...)` exit 0, print `converging`, and omit split, scope-out, and re-seed recommendations. Step 2 updates the fixture to structural evidence.
- `tests/cli/test_convergence_cmd.py:test_applied_latest_finding_converges_without_redecompose_command` — Real sidecars with medium `plan-correctness` evidence and a fully applied latest match print a non-spinning result and no re-decompose command. Step 2 updates the fixture to structural evidence.

## Acceptance criteria

- A region appearing in two older runs of a three-run series, but not in the newest run, cannot make that series `VERDICT_SPINNING`.
- A region whose matching findings in the newest run are all marked `applied` cannot make that series `VERDICT_SPINNING`, but a later unannotated match can.
- A region appearing in the first and newest runs of a three-run series still qualifies under `RECURRENCE_TOLERANCE` when its other spinning conditions hold.
- The final-run check uses the newest run within the evaluated series, not the newest report of a different kind.
- A saved-sidecar CLI diagnosis for an absent latest finding prints a non-spinning result and no re-decompose command.
- `RunFinding`, `RunSnapshot`, saved review JSON, `diagnose_convergence()`, and `render_diagnosis()` retain their current interfaces.

## References

- [dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — Preserve the frozen diagnosis-model interfaces while changing only the recurrence rule.
- [difflib — Helpers for computing deltas](https://docs.python.org/3/library/difflib.html) — Keep existing `SequenceMatcher`-based region matching unchanged.
- [json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — Preserve compatibility with persisted review sidecars.
- [pytest tmp_path fixture API](https://docs.pytest.org/en/stable/reference/reference.html#tmp-path) — Use isolated saved-sidecar fixtures where a persistence-path regression is useful.

## Applicable guardrails

- **The plan’s “## Out of scope”, persisted-history compatibility:** Do not add fields, migrate sidecars, or change `plan_tool/review_persistence.py`; derive currentness from existing per-series observations.
- **The plan’s “## Out of scope”, finding-category boundaries:** Do not classify findings as structural, claim, or premise in this step; retain the existing recurrence scope and matching inputs. Step 2 owns the final structural CLI fixture.
- **The plan’s “## Out of scope”, decomposition workflow boundary:** Limit the change to whether the diagnosis is spinning. Do not alter CLI flags, split execution, scope-out execution, or re-decomposition workflow.

## Deferred

- `plan_tool/convergence_diagnosis.py:classify_fork` remedy-category selection and `plan_tool/split_criteria.py:_reference_lines` legend wording — owned by plan step 2, which refines when current recurrence may recommend a destructive remedy.
- Broader cross-run similarity changes in `plan_tool/convergence_diagnosis.py:_matches` — deferred by the plan because this step must preserve existing matching semantics.
