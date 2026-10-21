> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Use one calibration lookup for audit materiality

## Summary

Update `plan_tool/review.py:audit_plan_until_stable` to create the step-3 calibration lookup once per audit invocation and use its rule when deciding whether newly found audit recommendations are material. Keep `plan_tool/convergence.py:is_blocking_impact` as the owner of the final blocking decision. This deliberately changes continuation only for a qualifying demoted recommendation; deduplication, low-yield confirmation, budgets, and every non-qualifying outcome remain unchanged.

## Table of Contents

- [Summary](#summary) — The audit materiality behavior this step adds.
- [Table of Contents](#table-of-contents) — Links to every section.
- [Why](#why) — Why audit passes need one shared calibration decision.
- [Input](#input) — The upstream lookup and blocking-policy contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two in-scope file edits.
- [Implementation](#implementation) — How to apply one lookup across audit passes.
- [Tests](#tests) — Coverage for reuse, demotion, and safety boundaries.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Test seams relevant to this change.
- [Deferred](#deferred) — Related callers outside this step.

## Why

`plan_tool/review.py:audit_plan_until_stable` currently evaluates each new audit finding with `is_blocking_impact` without calibration evidence, so a low-impact medium finding that historical evidence supports demoting remains material and keeps sampling productive. The audit loop runs multiple passes over the same plan, making per-finding or per-pass history reads both wasteful and capable of changing the decision mid-operation. This step gives the audit loop the same calibrated materiality policy as reconcile while preserving the shared safety rules.

## Input

- **Step 2 blocking contract:** Use the bounded optional demotion rule accepted by `plan_tool/convergence.py:is_blocking_impact`; high impact and `high`/`critical` severity remain blocking.
- **Step 3 lookup contract:** Consume the public operation-scoped calibration lookup produced by step 3 in `plan_tool/telemetry_analysis.py`. Treat its rule as read-only and build it from `repo_root` once for this audit invocation.
- **Audit materiality seam:** `plan_tool/review.py:audit_plan_until_stable` decides productivity from newly deduplicated recommendations at its `material_new` calculation. Preserve its existing deduplication, count threshold, low-yield floor, and budget-report behavior.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/review.py` — Construct the step-3 lookup once and pass its rule to the audit loop’s materiality check.
  - `tests/test_review.py` — Add audit-loop coverage for one lookup, qualifying demotion, and non-demotable safety cases.

## Implementation

- **Foundational logic: operation-scoped calibrated audit materiality.** Build the step-3 calibration lookup once before `plan_tool/review.py:audit_plan_until_stable` evaluates pass-level materiality. Retain its rule for every pass rather than constructing a lookup in the pass loop or in the `material_new` comprehension.

- **Apply the rule only at the materiality decision.** Route the `material_new` evaluation through `plan_tool/convergence.py:is_blocking_impact(rec, demotion_rule=...)`. Keep the existing `new_recs_this_pass` collection and `count_ok` logic unchanged so calibration affects only whether a threshold-clearing finding is material.

- **Keep policy single-sourced.** Do not repeat the low-impact, medium-severity, finding-class, or evidence-threshold checks in `plan_tool/review.py`. Step 3 owns the evidence decision; `plan_tool/convergence.py:is_blocking_impact` owns high-impact promotion and severity safety.

- **Keep one stable decision for the operation.** A multi-pass audit must use the same lookup for every continuation decision, including the low-yield confirmation path. Missing, weak, or nonmatching evidence must leave the current materiality behavior unchanged.

- **Preserve audit outcomes.** The returned union, stable-ID deduplication, carried-findings prompt context, `budget_report` fields, and the two-pass low-yield floor in `plan_tool/review.py:audit_plan_until_stable` must continue to reflect the post-calibration materiality result without changing parsing or persistence formats.

## Tests

- `test_audit_materiality_builds_calibration_lookup_once_per_invocation` — A multi-pass audit constructs the step-3 lookup once and reuses its rule across all materiality checks.
- `test_qualifying_low_impact_medium_audit_finding_is_low_yield` — A calibrated low-impact medium finding does not count as material, so the audit follows the existing low-yield behavior.
- `test_calibration_does_not_demote_high_impact_audit_finding` — A high-impact finding remains material even when the supplied lookup would otherwise classify it as demotable.
- `test_calibration_does_not_demote_high_severity_audit_finding` — A `high` or `critical` finding remains material despite a demotion-rule match.

### Test-creation order (feature step)

1. `test_audit_materiality_builds_calibration_lookup_once_per_invocation` — Add with the lookup wiring to prove the history-backed rule is not rebuilt per pass.
2. `test_qualifying_low_impact_medium_audit_finding_is_low_yield` — Add with the materiality change to prove the audit consumes the lookup result.
3. `test_calibration_does_not_demote_high_impact_audit_finding` and `test_calibration_does_not_demote_high_severity_audit_finding` — Add with the integration to pin the shared predicate’s safety ordering.

Every new test must be green before this step is considered finished.

## Acceptance criteria

- `plan_tool/review.py:audit_plan_until_stable` builds the step-3 calibration lookup no more than once per invocation.
- Every `material_new` decision in one audit invocation uses that lookup’s rule through `plan_tool/convergence.py:is_blocking_impact`.
- A qualifying low-impact, medium-severity recommendation is treated as non-material by the audit loop.
- High-impact recommendations and `high` or `critical` severities remain material even if the lookup rule returns true.
- `tests/test_review.py:TestAuditPlanUntilStable` passes the new lookup-count, demotion, and safety-boundary coverage.

## References

- [unittest.mock — Python documentation](https://docs.python.org/3/library/unittest.mock.html) — Use call assertions to prove the lookup is built once.
- [Monkeypatching/mocking modules and environments — pytest documentation](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use scoped replacement of the calibration builder in audit-loop tests.

## Deferred

- `plan_tool/cli/reconcile.py:_iterate_reconcile_loop` adoption — Step 4 owns reconcile-loop lookup construction and refresh coverage.
- Calibration evidence thresholds and lookup construction — Step 3 owns the `plan_tool/telemetry_analysis.py` decision contract.
