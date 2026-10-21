> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Build the evidence-backed low-impact demotion lookup

## Summary

Add a read-only, operation-scoped lookup in `plan_tool/telemetry_analysis.py` that identifies only low-impact, medium-severity recommendations with strong low-confirmation calibration evidence as demotable. Build it from the existing `FindingClassDriftSignal` results and classify live recommendations through `classify_calibration_recommendation`. Keep the lookup immutable and ensure evaluating an individual recommendation does not reload saved history. On green, later reconcile and audit callers can create one lookup per operation and pass its rule to step 1’s optional demotion hook.

## Table of Contents

- [Summary](#summary) — The lookup’s purpose and observable result.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — Why calibration needs a reusable operation-scoped rule.
- [Input](#input) — The saved-finding evidence and live recommendation contract.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two in-scope file changes.
- [Implementation](#implementation) — The eligibility rule, evidence thresholds, and read boundary.
- [Tests](#tests) — Unit coverage for thresholds, safety boundaries, and read behavior.
- [Acceptance criteria](#acceptance-criteria) — Checkable completion conditions.
- [References](#references) — Standard-library and pytest references for the implementation.
- [Deferred](#deferred) — Caller adoption and persistence left to later work.

## Why

`plan_tool/telemetry_analysis.py` can already group persisted audit outcomes into `FindingClassDriftSignal` records, but it does not expose a safe live-decision rule for the calibrated demotion policy. Reconcile and audit materiality need the same evidence interpretation without independently reading report history or reimplementing the threshold logic. This step makes the calibration decision single-sourced while keeping missing or weak evidence non-permissive.

## Input

- **Saved calibration evidence:** Read `FindingDriftAnalysis.signals` and each `FindingClassDriftSignal` produced by `plan_tool/telemetry_analysis.py:analyze_finding_drift`. Use `confirmed`, `cleared`, `unresolved`, `confirmed_rate`, and the `FindingClass` key; unresolved observations must not count toward the resolved-evidence threshold.

- **Live recommendation identity:** Classify each candidate with `plan_tool/telemetry_analysis.py:classify_calibration_recommendation`. Its `FindingClass` vocabulary must remain aligned with `_classify_history_finding`, including the `granularity-split` provenance distinction and the legacy `unknown` cohort.

- **Upstream extension point:** Step 2 supplies the bounded optional demotion rule accepted by `plan_tool/convergence.py:is_blocking_impact`. This step supplies evidence-backed rule construction only; it does not change the shared blocking predicate or adopt it in a loop.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/telemetry_analysis.py` — Add the calibration thresholds and a public operation-scoped lookup or predicate builder based on `FindingDriftAnalysis` and `classify_calibration_recommendation`.
  - `tests/test_telemetry_analysis.py` — Add focused unit tests for the eligibility matrix, class matching, immutable lookup behavior, and one analysis read per constructed operation rule.

## Implementation

- **Foundational logic: calibrated demotion eligibility predicate.** Add one public, dependency-light way to build a rule that accepts a live `plan_tool/review.py:Recommendation` and returns whether it is safe to demote. Keep the evidence read at construction time; calling the returned rule must only inspect the recommendation and the already-built lookup.

- **Require the exact candidate shape.** Return `True` only for a recommendation with explicit `impact == "low"` and `severity == "medium"` whose `FindingClass` has qualifying evidence. Treat missing impact as ineligible. Do not use this rule to promote advisory findings or to classify generic severity; step 1’s `is_blocking_impact` remains the owner of baseline blocking and high-impact promotion.

- **Apply the strict evidence thresholds.** A class qualifies only when `confirmed + cleared >= 10` and `confirmed_rate <= 0.10`. Count neither `unresolved` observations nor `total` toward the resolved threshold. Treat `confirmed_rate is None`, a missing class row, evidence below the threshold, and a rate above `0.10` as `False`.

- **Preserve provenance boundaries.** Use `classify_calibration_recommendation` for lookup keys rather than duplicating `_anchor_category`, `_scope_shape`, or the purity provenance rules. Exclude every class whose provenance is `unknown` or legacy before applying count/rate thresholds. A `granularity-split` recommendation with `purity_verdict_provenance="unknown"` neither borrows known-cohort evidence nor qualifies from its own unknown cohort; non-purity findings keep `purity_verdict_provenance=None`.

- **Keep the lookup read-only and stable.** Represent the qualifying `FindingClass` set or class-to-decision mapping with an immutable value. A `types.MappingProxyType` wrapper is one suitable approach if a mapping is useful; an immutable set is also suitable when it fully represents the rule. Do not mutate `FindingDriftAnalysis`, its signals, saved reports, telemetry, plans, or configuration.

- **Read history once at the operation boundary.** Have the public builder obtain calibration through `analyze_finding_drift(repo_root)` once, then close over or otherwise retain the immutable result. Do not call `locator.list_plans_from_manifest`, `convergence_diagnosis.load_report_history`, or `analyze_finding_drift` while evaluating individual recommendations.

- **Leave analysis reporting intact.** Keep `analyze_finding_drift`, `analyze_telemetry`, `analysis_to_dict`, and `render_analysis` as read-only reporting paths. The new lookup may reuse their typed evidence, but it must not change their outcome accounting or reinterpret unresolved evidence as cleared.

- **Defer loop wiring.** `plan_tool/cli/reconcile.py:_iterate_reconcile_loop` and `plan_tool/review.py:audit_plan_until_stable` are the later consumers in steps 3 and 4. Do not edit them in this step; they will each build one rule per operation and provide it to step 1’s extension point.

## Tests

- `test_low_impact_medium_recommendation_demotes_at_resolved_threshold_and_rate_boundary` — A matching class with exactly 10 resolved observations and a `0.10` confirmed rate is eligible.

- `test_low_impact_medium_recommendation_remains_blocking_below_resolved_threshold` — Fewer than 10 `confirmed + cleared` observations do not qualify, regardless of `total` or unresolved count.

- `test_low_impact_medium_recommendation_remains_blocking_above_confirmed_rate_threshold` — A rate greater than `0.10` does not qualify.

- `test_demotion_lookup_rejects_missing_unknown_and_unresolved_only_evidence` — Missing class rows, `confirmed_rate is None`, legacy or unknown provenance cohorts, and unresolved-only signals remain non-permissive.

- `test_demotion_lookup_matches_live_recommendation_calibration_class` — The builder uses `classify_calibration_recommendation` so matching source, anchor shape, scope shape, and purity provenance select the intended signal only.

- `test_demotion_lookup_rejects_non_low_medium_candidates` — High and critical severities, `nit`, `info`, non-low impact, and missing impact never receive a demotion decision even when their class qualifies.

- `test_demotion_lookup_reads_calibration_once_and_evaluation_reads_no_history` — Patch the analysis seam, construct one rule, evaluate several recommendations, and assert the calibration analysis runs once with no later saved-history reads.

- `test_demotion_lookup_is_immutable` — Callers cannot mutate the returned lookup state to create or remove a qualifying class.

### Test-creation order (feature step)

Add the threshold and candidate-shape tests with the lookup implementation first, then add class-isolation and one-read tests around the chosen public builder. Every new test must be green before this step is considered finished.

## Acceptance criteria

- `plan_tool/telemetry_analysis.py` exposes a public operation-scoped demotion rule or lookup derived from existing `FindingClassDriftSignal` evidence.

- A recommendation is demotable only when `impact == "low"`, `severity == "medium"`, its matching class has at least 10 resolved observations, and its confirmed rate is at most `0.10`.

- The resolved-observation count is exactly `confirmed + cleared`; unresolved observations do not make evidence sufficient.

- Missing, unknown, legacy, unresolved-only, under-sampled, and over-threshold evidence returns no demotion decision.

- High and critical findings cannot be demoted, and `nit` and `info` findings remain outside this rule.

- The rule uses `classify_calibration_recommendation` to select the same `FindingClass` vocabulary used by persisted history.

- Constructing one operation rule reads calibration once; evaluating recommendations through it performs no history reads and writes no persisted state.

- `tests/test_telemetry_analysis.py` passes with the new eligibility, isolation, immutability, and read-count coverage.

## References

- [dataclasses — Python documentation](https://docs.python.org/3/library/dataclasses.html) — Use frozen data structures when exposing calibration inputs that callers must not mutate.

- [types.MappingProxyType — Python documentation](https://docs.python.org/3/library/types.html#types.MappingProxyType) — Review the standard read-only mapping wrapper if the lookup is represented as a mapping.

- [unittest.mock — Python documentation](https://docs.python.org/3/library/unittest.mock.html) — Use call assertions to prove calibration is built once and not reread during predicate evaluation.

- [Parametrizing tests — pytest documentation](https://docs.pytest.org/en/stable/example/parametrize.html) — Use a compact boundary matrix for eligible and ineligible recommendation shapes.

- [Monkeypatching/mocking modules and environments — pytest documentation](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Patch calibration and history seams without changing persisted evidence.

## Deferred

- **Reconcile iteration adoption** — Step 4 owns constructing one lookup in `plan_tool/cli/reconcile.py:_iterate_reconcile_loop` and passing it to the step 2 extension point.

- **Audit materiality adoption** — Step 5 owns constructing one lookup in `plan_tool/review.py:audit_plan_until_stable` and passing it to the step 2 extension point.

- **Persisting calibration across operations** — Keep calibration operation-scoped and read-only; a persisted cache needs a separate design decision.
