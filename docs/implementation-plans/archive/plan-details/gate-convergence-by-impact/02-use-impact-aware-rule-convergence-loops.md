> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Use the impact-aware rule in reachable convergence paths

## Summary

Adopt `is_blocking_impact()` only where traced conceptual advisory recommendations can affect continuation: every reconcile state refresh and audit materiality in `audit_plan_until_stable`. Do not add an impact-aware completeness-loop change, because its open-finding collection does not receive these candidates.

## Table of Contents

- [Summary](#summary) — Wiring outcome.
- [Why](#why) — Why adoption is limited.
- [Input](#input) — Predicate and reachability evidence.
- [Files (creates vs edits)](#files-creates-vs-edits) — Source and test files.
- [Implementation](#implementation) — Required wiring.
- [Tests](#tests) — Regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable checks.
- [Deferred](#deferred) — Severity-only and unrelated work.

## Why

The trace distinguishes paths that can observe a high-impact advisory recommendation from look-alike severity checks. `plan_tool/cli/reconcile.py:_iterate_reconcile_loop` and `plan_tool/review.py:audit_plan_until_stable` receive the relevant recommendations. `plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop` does not, so changing it would not implement the evidenced behavior.

## Input

- Step 1 provides `plan_tool/convergence.py:is_blocking_impact` and preserves the severity floor.
- Step 2 reachability evidence identifies all reconcile `ConvergenceState.has_blocking_findings` refreshes, including resume paths, and `audit_plan_until_stable`’s `material_new` calculation.
- `partition_findings_for_triage` remains the existing decision for apply/defer handling; it is not a continuation promise.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/cli/reconcile.py` — Use the shared predicate at every `_iterate_reconcile_loop` blocking-state refresh.
  - `plan_tool/review.py` — Use the shared predicate when `audit_plan_until_stable` builds `material_new`.
  - `tests/test_cli.py` — Cover reconcile initial, later, and resume refresh behavior.
  - `tests/test_review.py` — Cover audit materiality for high-impact advisory recommendations.

## Implementation

- Import and call `is_blocking_impact`; do not duplicate its expression in callers.
- In `_iterate_reconcile_loop`, replace every finding-level severity check that assigns `ConvergenceState.has_blocking_findings`, including initial findings, normal later refreshes, and each drift-sidecar resume path.
- In `audit_plan_until_stable`, use the predicate for `new_recs_this_pass` when constructing `material_new`, so a threshold-clearing high-impact `nit` or `info` finding is productive.
- Preserve triage behavior. A finding deferred by `partition_findings_for_triage` does not by itself prove an additional reconcile iteration.
- Leave `_run_iterate_convergence_loop`, `_completeness_has_blocking_findings`, deterministic/reporting gates, and `convergence_diagnosis.py` on severity-only behavior. Do not add conceptual-finding plumbing to completeness.

## Tests

- `test_reconcile_initial_refresh_keeps_high_impact_advisory_blocking` — A high-impact `nit` or `info` that reaches the initial refresh sets blocking state.
- `test_reconcile_later_and_resume_refreshes_keep_high_impact_advisory_blocking` — Normal and resume refreshes do not revert to severity-only behavior.
- `test_reconcile_triage_defer_does_not_promise_iteration` — Preserve the existing partition/defer outcome.
- `test_high_impact_advisory_pass_is_productive` — A threshold-clearing high-impact `nit` or `info` contributes to `material_new`, resets the dry streak, and samples again.
- `test_untagged_advisory_pass_remains_low_yield` — Advisory findings without high impact retain the existing result.
- `test_medium_or_higher_remains_material_without_impact` — The severity floor remains intact.

## Acceptance criteria

- All `_iterate_reconcile_loop` blocking-state refreshes, including resume paths, use `is_blocking_impact`.
- `audit_plan_until_stable` uses the predicate for `material_new`.
- No impact-aware behavior change is required in `plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop`.
- Triage deferral and severity-only deterministic/reporting behavior remain unchanged.
- The focused reconcile and review tests cover promotion and the severity floor.

## Deferred

- Completeness impact plumbing requires separate scope and evidence.
- `plan_tool/convergence_diagnosis.py` and other reporting gates retain severity-only semantics.
- Impact-only demotion, recurrence routing, and calibration remain separate work.
