> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Use one calibration lookup in reconcile iteration

## Summary

Adopt the calibrated low-impact demotion rule in `plan_tool/cli/reconcile.py:_iterate_reconcile_loop`. Build the operation-scoped lookup supplied by step 3 once for a reconcile-loop invocation, then use its rule at every reconcile continuation refresh. Update `tests/test_cli.py` to prove qualifying low-impact medium findings stop as non-blocking while high-impact and high-severity findings remain blocking. On green, repeated iterations do not reread calibration history for each recommendation or refresh point.

## Table of Contents

- [Summary](#summary) — The reconcile-loop behavior this step adds.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why reconcile needs one shared calibration decision for the whole operation.
- [Input](#input) — The upstream predicate and lookup contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two in-scope file edits.
- [Implementation](#implementation) — How to apply one lookup across all continuation checks.
- [Tests](#tests) — Regression coverage for one lookup and safe demotion.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Test tools relevant to the new coverage.
- [Deferred](#deferred) — Other convergence callers left outside this step.

## Why

`plan_tool/cli/reconcile.py:_iterate_reconcile_loop` currently calls `is_blocking_impact` separately at each continuation refresh, so it has no operation-scoped calibration rule from step 2. Reconcile can therefore keep iterating on a low-impact medium finding even when saved evidence says that finding class is safe to demote. The loop needs one stable lookup for its whole invocation so every refresh makes the same decision without repeated saved-history reads.

## Input

- **Step 2 contract:** Use step 2’s bounded `plan_tool/convergence.py:is_blocking_impact` contract to supply the optional demotion rule; retain its fixed candidate guard and safety ordering.
- **Step 3 outcome:** Construct the public operation-scoped lookup added in `plan_tool/telemetry_analysis.py` by step 3, using `ctx.repo_root` once per enabled reconcile-loop invocation.
- **Live findings:** Classify the `Recommendation` objects from `plan_tool/review.py:extract_reconcile_recommendations`, including the caller-provided `initial_recs`.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/cli/reconcile.py` — Build one step-3 calibration lookup and apply its rule to every `_iterate_reconcile_loop` blocking-findings refresh.
  - `tests/test_cli.py` — Extend `TestIterateReconcileLoopHighImpactAdvisories` or a focused sibling class with lookup-count, demotion, and safety-boundary coverage.

## Implementation

- **Foundational logic: operation-scoped calibrated blocking check.** Build the step-3 lookup once before `_iterate_reconcile_loop` begins making continuation decisions, then retain its recommendation rule for the full invocation. Do not build it inside the `while True` body or inside an `any(...)` classification.

- **Apply the same rule at every refresh.** Route the initial `initial_recs` assignment and each later `conv_state.has_blocking_findings` assignment through `is_blocking_impact(rec, demotion_rule=...)` using that one rule. This includes the ordinary post-walk refresh and the refreshes following merged drift-halt or change-collision paths; otherwise those paths can disagree about whether the same finding blocks.

- **Keep the shared predicate as the policy owner.** Do not repeat low-impact, medium-severity, finding-class, or evidence-threshold checks in `plan_tool/cli/reconcile.py`. The CLI should only construct the step-3 lookup and pass its decision into `plan_tool/convergence.py:is_blocking_impact`.

- **Preserve safety behavior.** High-impact recommendations and `high` or `critical` severities must remain blocking even if the supplied rule returns true. Missing, weak, or nonmatching calibration evidence must leave the existing medium-severity behavior unchanged.

- **Avoid unnecessary reads.** A disabled iteration budget should not trigger calibration analysis merely because `_iterate_reconcile_loop` was entered. When iteration is enabled, use one lookup for the invocation rather than one lookup per finding, pass, or refresh.

- **Keep existing loop control intact.** Continue to use `ConvergenceState.has_blocking_findings` and `should_continue` for stop reasons, iteration limits, drift handling, scope-guard emission, and cleanup. This step changes only the input used to decide whether current findings are blocking.

## Tests

- `test_reconcile_calibration_lookup_is_built_once_per_enabled_loop` — Forces multiple continuation refreshes and asserts the step-3 lookup builder runs once, not once per finding or iteration.
- `test_reconcile_qualifying_low_impact_medium_finding_stops_as_non_blocking` — Uses qualifying calibration evidence and confirms the loop reaches the existing `no_blocking_findings` outcome after its required first pass.
- `test_reconcile_unqualified_low_impact_medium_finding_remains_blocking` — Confirms missing or nonmatching evidence retains normal medium-severity continuation behavior.
- `test_reconcile_calibrated_rule_cannot_demote_high_impact_or_high_severity` — Confirms high-impact advisory, high, and critical controls remain blocking even when the supplied rule would otherwise return true.
- `test_reconcile_merged_refresh_reuses_the_same_calibration_rule` — Exercises a merged refresh path and confirms it uses the invocation’s existing lookup rather than rebuilding or bypassing it.

### Test-creation order (feature step)

- Add the one-lookup construction test with the implementation, then add qualifying and unqualified low-impact medium cases.
- Add the high-impact and high/critical safety controls, then cover a merged refresh path.
- Every new test must be green before this step is considered finished.

## Acceptance criteria

- `_iterate_reconcile_loop` constructs the step-3 calibration lookup no more than once for an enabled invocation.
- Every assignment to `ConvergenceState.has_blocking_findings` in `_iterate_reconcile_loop` uses the same lookup rule through `is_blocking_impact`.
- A qualifying low-impact medium recommendation no longer keeps reconcile iteration open after the loop’s first-pass rule.
- Missing or nonqualifying evidence leaves a low-impact medium recommendation blocking.
- High-impact, high, and critical recommendations remain blocking regardless of lookup output.
- The new `tests/test_cli.py` coverage passes.

## References

- [unittest.mock — Python documentation](https://docs.python.org/3/library/unittest.mock.html) — Use call assertions to prove the lookup is built once.
- [Monkeypatching/mocking modules and environments — pytest documentation](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use scoped replacements for lookup construction and reconcile-loop seams.

## Deferred

- `plan_tool/review.py:audit_plan_until_stable` adoption — Audit materiality uses `is_blocking_impact` but is a separate caller and belongs to a later step.
- Calibration threshold and class-eligibility changes — Step 3 owns the lookup’s evidence policy; this step only consumes its rule.
