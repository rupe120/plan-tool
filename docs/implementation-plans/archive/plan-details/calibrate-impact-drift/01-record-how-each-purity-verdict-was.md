> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Record how each purity verdict was produced

## Summary

Record provenance on each persisted MIXED-STEP purity finding so later calibration can distinguish a newly computed verdict from cache reuse. Update `plan_tool/review.py`, `plan_tool/detail.py`, and `plan_tool/cli/completeness_phases.py` to attach one of `fresh`, `exact-cache`, or `below-floor-reuse` only to purity findings. Carry that optional field through `plan_tool/convergence_diagnosis.py`, where legacy saved findings without it become `unknown`. On green, saved completeness reports retain the provenance needed by the read-only analysis without changing cache policy, severity gates, or report persistence format.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the provenance contract.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why cache origin must remain visible in history.
- [Input](#input) — Existing purity cache and saved-review contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Exact footprint and intended edits.
- [Implementation](#implementation) — Provenance rules and call-site boundaries.
- [Tests](#tests) — Regression coverage for fresh, reused, and legacy findings.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — JSON compatibility references.
- [Deferred](#deferred) — Work reserved for later calibration steps.

## Why

`plan_tool/detail.py:_cached_purity_findings` already chooses between a live Claude verdict, an exact cache hit, and below-floor reuse, but the resulting saved `Recommendation` data does not say which path produced a purity finding. A later calibration that pools those rows would treat reused evidence as if it were fresh evidence and could draw the wrong conclusion about impact. Preserve the origin at the recommendation boundary now so historical sidecars remain usable by steps 2 and 3 without creating another store or changing the cache’s reuse rules.

## Input

- **Purity cache behavior** — `plan_tool/detail.py:_cached_purity_findings` returns the merged review findings, stores only `GRANULARITY_SPLIT_SOURCE` findings in `plan_tool/purity_cache.py:PurityCacheEntry`, and distinguishes exact read-through hits from live calls.
- **Below-floor reuse** — `plan_tool/cli/completeness_phases.py:_grade_purity_cache_miss` returns the cached purity verdict plus its informational advisory when a changed detail remains below the reuse floor.
- **Saved review compatibility** — `plan_tool/review_persistence.py:save_review` serializes `Recommendation` through `dataclasses.asdict`, while `load_review` rebuilds it with `Recommendation(**r)`; absent optional fields in old sidecars must remain readable.
- **History normalization** — `plan_tool/convergence_diagnosis.py:_finding_from_recommendation` is the boundary that reduces persisted recommendations into `RunFinding` records for later analysis. It must also retain whether a persisted `Recommendation.redirect` was present, so step 2 can exclude plan-rooted run-reconcile redirects from code-drift confirmation.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/review.py` — extend `Recommendation` with an optional, documented purity-verdict provenance field.
  - `plan_tool/detail.py` — tag only structural purity findings returned by `_cached_purity_findings` according to the path that supplied them, without changing cached baseline findings.
  - `plan_tool/cli/completeness_phases.py` — preserve the below-floor reuse distinction while `_collect_purity_split_findings` filters purity findings into `smell_recs`.
  - `plan_tool/cli/reconcile.py` — have `_save_and_walk_run_reconcile` derive the marker from its raw run-reconcile response before it calls `save_review`.
  - `plan_tool/review_persistence.py` — persist the optional code-side outcome-validity marker and preserve it through `update_annotation` rewrites without breaking legacy sidecars.
  - `plan_tool/convergence_diagnosis.py` — retain provenance, the persisted redirect-present bit, and outcome-validity state in normalized history; normalize missing legacy purity provenance to `unknown`.
  - `tests/test_detail.py` — cover provenance assignment at the shared cache boundary.
  - `tests/cli/test_completeness_cmd.py` — cover provenance through exact-cache and below-floor completeness paths.
  - `tests/test_convergence_diagnosis.py` — cover normalized history records for tagged and legacy purity findings.
  - `tests/test_review_persistence.py` — prove the existing generic save/load path preserves the new optional recommendation field and accepts legacy rows without it.

## Implementation

- **Foundational logic: purity-verdict provenance classification.** Add an optional field on `plan_tool/review.py:Recommendation` with a self-describing name such as `purity_verdict_provenance`. Restrict populated values to `fresh`, `exact-cache`, and `below-floor-reuse`; leave it unset for non-purity findings and for legacy data before history normalization.

- **Tag only MIXED-STEP verdict findings.** In `plan_tool/detail.py:_cached_purity_findings`, identify purity findings with `plan_tool/granularity.py:GRANULARITY_SPLIT_SOURCE`. Do not add provenance to Claude grounding findings, deterministic grounding findings, altitude advisories, or the `purity-reuse-advisory` emitted by `plan_tool/cli/completeness_phases.py:_grade_purity_cache_miss`.

- **Keep cached findings as the neutral baseline.** The cache entry must not be rewritten merely to change its reported origin. Return copies or equivalent transient records tagged `exact-cache` on an exact read-through hit, `below-floor-reuse` when the caller accepts the graded reuse result, and `fresh` after a successful live purity call. This prevents a finding first earned live from being incorrectly reported as fresh when a later audit serves it from cache.

- **Preserve existing cache and call behavior.** `plan_tool/detail.py:_cached_purity_findings` must still skip Claude only for the audit read-through paths already allowed by its contract. `generate_detail`’s write-through calls remain live checks, cache success remains gated by `collect_detail_quality_findings(..., return_status=True)`, and an unsuccessful or quiet probe still creates no verdict to label.

- **Keep the completeness filter stable.** `plan_tool/cli/completeness_phases.py:_collect_purity_split_findings` must continue to retain only medium `GRANULARITY_SPLIT_SOURCE` findings plus the separate informational reuse advisory. The provenance field explains how the retained purity finding was obtained; it must not alter severity, source, blocking behavior, or the `smell_recs` routing.

- **Normalize provenance and redirect state at the history boundary.** Extend `plan_tool/convergence_diagnosis.py:RunFinding` and `_finding_from_recommendation` so later analysis can read provenance and whether `Recommendation.redirect` was present without reopening sidecars. For a persisted purity finding with no field, expose `unknown`; retain `None` or an equivalent non-cohort value for non-purity findings so they are not falsely classified as purity evidence. Legacy history has no flattened redirect bit and defaults to `False`; only a positively persisted redirect excludes an outcome finding.

- **Persist code-side outcome validity, not an inferred clean result.** Add optional `outcome_evidence_valid` state to `SavedReview` / `RunSnapshot`. The run-reconcile producer writes true only after recognizing a well-formed findings result or an explicit clean-result sentinel; an unparseable or incomplete response writes false, while legacy and non-run-reconcile history remain unknown. Step 2 may clear an unmatched region only when the marker is true. This records parser completeness, not whether drift was found.

- **Set and preserve the marker at the only authoritative boundary.** `plan_tool/cli/reconcile.py:_save_and_walk_run_reconcile` owns the raw Claude response and must classify parser-validity before calling `save_review`; `review_persistence` must only serialize it. Include the marker in `update_annotation`'s full-sidecar rewrite so walking/annotating a saved valid report cannot silently degrade it to legacy-unknown.

## Tests

- `test_fresh_purity_finding_is_tagged_without_mutating_cached_baseline` — a successful live purity call returns a `fresh` structural finding while the stored cache verdict remains reusable as an unlabelled baseline.
- `test_exact_cache_hit_reports_exact_cache_provenance` — a matching read-through entry skips the producer and returns its purity finding tagged `exact-cache`.
- `test_write_through_detail_scan_reports_fresh_provenance` — the detail-authoring path still invokes the producer and reports a fresh purity finding even when a matching cache entry exists.
- `test_failed_or_quiet_purity_probe_has_no_provenance_verdict` — failed, truncated, or no-detail paths do not create a labelled cached verdict.
- `test_completeness_exact_cache_finding_keeps_exact_cache_provenance` — `_collect_purity_split_findings` carries the exact-hit tag into the advisory report bucket without changing the filter.
- `test_completeness_below_floor_finding_keeps_reuse_provenance` — a below-floor reuse marks the reused structural finding `below-floor-reuse` while the informational advisory remains distinct.
- `test_saved_review_round_trips_purity_verdict_provenance` — the normal saved-review JSON round trip preserves an explicitly tagged recommendation.
- `test_legacy_saved_review_without_purity_provenance_loads` — a legacy recommendation object lacking the optional field remains readable.
- `test_history_normalizes_legacy_purity_provenance_to_unknown` — `_finding_from_recommendation` exposes `unknown` for an untagged persisted purity finding.
- `test_history_keeps_non_purity_findings_out_of_purity_cohorts` — non-purity findings do not receive a synthetic `unknown` cohort value.
- `test_history_retains_run_reconcile_redirect_state` — a persisted recommendation with `redirect` becomes a redirect-marked `RunFinding`, while a legacy/non-redirect row remains eligible outcome evidence.
- `test_saved_run_reconcile_outcome_validity_round_trips_and_legacy_is_unknown` — parser-valid, invalid, and legacy outcome evidence remain distinguishable in normalized history.
- `test_run_reconcile_producer_marks_well_formed_and_explicit_clean_output_valid` — the raw-output producer writes true only for recognized complete findings/clean forms and false for malformed/incomplete output.
- `test_update_annotation_preserves_outcome_evidence_valid` — an annotation rewrite retains the marker in the saved JSON.

### Test-creation order (feature step)

1. `test_exact_cache_hit_reports_exact_cache_provenance` — pins the cache-hit classification before changing the shared helper.
2. `test_fresh_purity_finding_is_tagged_without_mutating_cached_baseline` — pins the live-call classification and cache-baseline invariant.
3. `test_completeness_below_floor_finding_keeps_reuse_provenance` — pins the third provenance path and advisory separation.
4. `test_saved_review_round_trips_purity_verdict_provenance` and `test_legacy_saved_review_without_purity_provenance_loads` — pin sidecar compatibility.
5. `test_history_normalizes_legacy_purity_provenance_to_unknown` and `test_history_keeps_non_purity_findings_out_of_purity_cohorts` — pin the analysis-facing contract.

Every new test must be green before this step is considered finished.

## Acceptance criteria

- A live successful MIXED-STEP purity finding returned by `plan_tool/detail.py:_cached_purity_findings` carries `fresh`.
- A matching audit read-through cache hit returns the same purity finding with `exact-cache` and does not invoke Claude.
- A below-floor reuse returned through `plan_tool/cli/completeness_phases.py:_grade_purity_cache_miss` carries `below-floor-reuse` on the reused purity finding.
- Non-purity findings and the informational `purity-reuse-advisory` do not receive a purity-verdict provenance value.
- Saved review JSON preserves explicit provenance through `plan_tool/review_persistence.py:save_review` and `load_review`.
- A legacy purity recommendation without provenance appears as `unknown` in `plan_tool/convergence_diagnosis.py:RunFinding`.
- A persisted run-reconcile redirect remains identifiable in `RunFinding` so it cannot be mistaken for code-drift confirmation.
- Only parser-valid run-reconcile evidence can clear an unmatched origin; invalid and legacy-unknown evidence remains unresolved.
- `_save_and_walk_run_reconcile` writes the marker before persistence, and `update_annotation` preserves it after a walk.
- Existing cache-hit, write-through, below-floor, and failed-call behavior remains unchanged apart from the reported provenance.

## References

- [Python json documentation](https://docs.python.org/3/library/json.html) — Review compatibility expectations for missing optional fields in persisted JSON.
- [RFC 8259: JSON Data Interchange Format](https://www.rfc-editor.org/info/rfc8259/) — Reference for maintaining valid, backward-compatible sidecar JSON objects.

## Deferred

- Per-class drift calculation and cohort stratification — step 2 consumes this provenance when it analyzes saved history.
- Telemetry presentation of calibration results — step 3 owns the operator-facing output.
- Cache-key changes, cache hardening, and reuse-threshold changes — outside this plan’s provenance-only scope.
