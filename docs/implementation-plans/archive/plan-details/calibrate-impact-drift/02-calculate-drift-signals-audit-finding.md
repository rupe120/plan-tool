> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Calculate drift signals for audit finding classes

## Summary

Add a read-only audit-finding calibration analysis in `plan_tool/telemetry_analysis.py` that groups saved findings into stable classes and measures whether later history shows related implementation drift. Extend `tests/test_telemetry_analysis.py` with synthetic histories for positive, negative, unresolved, and provenance-separated cohorts. The key design decision is to classify only from persisted, normalized finding fields and leave evidence that cannot be joined counted but unresolved. On green, callers have deterministic per-class drift signals computed from existing sidecars, with no CLI import, persistence, plan mutation, or threshold change.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the new read-only calibration result.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — Why outcome-based calibration is needed before an impact demote policy.
- [Input](#input) — Saved-history and provenance contracts the analysis reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Exact edit footprint.
- [Implementation](#implementation) — Finding classification, outcome joining, and invariants.
- [Tests](#tests) — Unit coverage for drift signals and unresolved evidence.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — File and JSON handling references.
- [Deferred](#deferred) — Work intentionally left to later steps.

## Why

`plan_tool/telemetry_analysis.py:analyze_decisions` currently calibrates recorded decision events, not the saved audit finding classes that supplied an `impact` judgment. A future impact demote must be based on observed later drift, not silently trust the same audit pass that raised the finding. This step adds the evidence calculation while preserving incomplete or legacy evidence as visible unresolved rows instead of treating it as a negative result.

## Input

- **Saved audit history** — Read `plan_tool/convergence_diagnosis.py:load_report_history`, `ReportHistory`, `RunSnapshot`, and `RunFinding` as the normalized saved-report contract. Use only fields available in that contract when assigning a class.
- **Finding provenance** — Step 1 supplies purity-verdict provenance through the normalized saved finding path. Preserve `fresh`, `exact-cache`, `below-floor-reuse`, and legacy `unknown` as separate cohorts when the finding is a purity verdict.
- **Canonical report evidence** — Discover plan paths through `plan_tool.locator.list_plans_from_manifest(repo_root)`, then load each plan's `plan_tool/convergence_diagnosis.py:load_report_history(plan_path)`. The reader already uses `plan_tool.review_persistence:plan_reports_dir` and `list_saved_reviews`; do not glob `.plan-tool/runs`, which contains JSONL execution logs rather than saved review reports.
- **Outcome evidence** — `plan-tool run <name> --reconcile` persists a code-side audit as `kind="run-reconcile"`; that snapshot is the only resolving observation. Resolve an origin's step from its non-null `step_id`, or, for a completeness finding whose `step_id` is intentionally `None`, with `convergence_diagnosis._step_token(anchor)`. Parse both ISO `created_at` values and select the first same-step `run-reconcile` strictly later than the origin. Because persisted timestamps are second-precision, equal timestamps cannot establish causal order and are unresolved; malformed timestamps are also unresolved rather than relying on `load_report_history`'s display-sort fallback. A strict non-placeholder, non-redirect match confirms drift. An absent match clears only when that saved report's `outcome_evidence_valid` marker is true; absent, false, and legacy-unknown validity remains unresolved. Missing ownership, history, focus, an anchor step token for a completeness origin, a parseable strict chronology, or a later same-step code-side reconcile remains unresolved. `read_run_outcome` and `_sidecar_outcome` remain decision-event machinery and are not this join model.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/telemetry_analysis.py` — add typed, deterministic finding-class drift results and the read-on-read analysis that derives them from saved history.
  - `tests/test_telemetry_analysis.py` — add synthetic-history coverage for class signals, provenance cohorts, and non-correlatable evidence.

## Implementation

- **Foundational logic: finding-class reconcile correlation.** Add a focused analysis path beside `analyze_decisions` that discovers manifest plans, reads their saved audit histories, assigns only `completeness` and `detail-reconcile` findings to a stable origin class, and determines whether a later code-side reconcile confirms or clears the same region. `run-reconcile` snapshots are outcome evidence only, never origins. It must work even when there are no decision events.

- **Publish one deterministic class-key helper.** Implement `plan_tool.telemetry_analysis:classify_calibration_recommendation(rec: Recommendation) -> FindingClass` as the public class-key boundary, plus a private adapter from `RunFinding` for history. Both must use the same persisted fields: source; anchor category (`step` for a parseable `step<N>` anchor, `anchored` for another non-empty anchor, or `unanchored`); and scope shape. Scope shape is `cross-boundary` only when lowercased persisted anchor/title contains one of the fixed tokens `seam`, `boundary`, `cross-step`, or `contract`; otherwise it is `step-detail` for a step anchor, `anchored-detail` for another anchor, or `unclassified`. Keep this fixed vocabulary in that helper, return explicit unknowns, and never inspect current plan text or re-run an audit. This gives a later #152 design a documented way to classify a live `Recommendation` without making this plan alter the live gate.

- **Define a calibration-specific region join.** Do not use `_normalized_focus` or `_matches` as equality: their `step<N>` focus is intentionally broad for recurrence diagnosis. Derive the origin's step with `step_id` or `_step_token(anchor)` for completeness rows, then require the later report to have that same step and a parseable, strictly later timestamp. Require equal normalized non-empty anchors only when neither anchor is merely a bare `step<N>` token, or otherwise require title similarity at or above the shared cutoff; an empty or `"(unspecified)"` title is insufficient identity and never matches. Equal step or equal bare-step anchor alone never confirms a finding. Ignore every later outcome finding whose persisted redirect-present bit is true: it identifies a plan-rooted redirect, not code drift. Search the first eligible snapshot only: a non-redirect strict match is `confirmed-drift`; an absent match is `cleared` only when its `outcome_evidence_valid` marker is true; equal/malformed timestamps, invalid/unknown outcome evidence, no eligible snapshot, or insufficient identity fields are unresolved. Do not use `_sidecar_outcome`, plan-fingerprint transitions, run-log completion, finding disappearance, or code-fingerprint movement as a proxy for drift.

- **Count one observation per outcome boundary.** Repeated audit reports can re-state one unchanged semantic origin before the same later reconcile. Group candidate origins by plan, resolved step, strict origin identity, and the selected outcome snapshot; emit at most one observation for each group, choosing the latest origin strictly before that outcome to represent the state the code-side audit actually observed. Do not emit a second confirmed/cleared count merely because an earlier audit repeated the same region. Origins with no valid outcome stay individually unresolved, so incomplete evidence remains visible without inflating a resolved rate.

- **Make the advisory signal falsifiable.** Return `confirmed`, `cleared`, and `unresolved` counts for every class and compute `confirmed_rate = confirmed / (confirmed + cleared)` only when at least one resolved observation exists. Expose `insufficient-evidence` whenever `confirmed + cleared < 3`; do not label a cohort as up/down, set a gate threshold, or infer an outcome from unresolved rows. A later #152 design receives these counts, rate, and evidence state—not a hidden policy decision.

- **Preserve cohort boundaries.** Step 1 makes provenance available for purity findings. Include that provenance in the result’s grouping key or cohort dimension so `fresh`, `exact-cache`, `below-floor-reuse`, and `unknown` are never pooled into one rate. Non-purity findings must not gain fabricated purity provenance.

- **Count incomplete evidence.** Return totals that retain ownerless, legacy, missing-focus, and no-later-history findings as counted-but-unresolved. Do not classify them as no-drift, and do not drop them from the class total.

- **Keep analysis read-only and below the CLI layer.** Follow the `resolve_decisions` and `analyze_decisions` pattern: load sidecars on demand, return immutable analysis values, and write nothing. `plan_tool/telemetry_analysis.py` must continue to avoid importing `plan_tool.cli`.

- **Keep existing decision telemetry stable.** Do not change `ResolvedDecision`, `DecisionAggregate`, `recommend_tuning`, or their current thresholds as part of this step. Step 3 owns presenting the new calibration result in telemetry output.

- **Prefer a separate result contract over overloading decision aggregates.** Audit-finding classes and decision-event signals have different identities and evidence rules. Keep their typed results separate, then let a later presentation layer combine them if needed.

## Tests

`test_finding_class_confirmed_by_later_run_reconcile_has_positive_signal` — a synthetic saved history with a later matching `run-reconcile` finding produces a positive signal for that class.

`test_finding_class_cleared_by_later_run_reconcile_has_negative_signal` — a later `run-reconcile` report that lacks the matching region produces a non-positive, resolved result rather than an unresolved result.

`test_same_step_unrelated_run_reconcile_finding_does_not_confirm_origin` — equal `step_id` alone cannot confirm drift; the later finding must meet the strict anchor/title identity rule.

`test_other_step_run_reconcile_does_not_clear_origin` — a code-side reconcile for another step leaves a step-scoped origin unresolved.

`test_step_anchored_completeness_origin_joins_same_step_run_reconcile` — a completeness origin with `step_id=None` and a `step<N>` anchor derives that step and can be resolved by its later same-step code-side reconcile.

`test_tied_or_malformed_report_timestamps_remain_unresolved` — equal second-precision timestamps and malformed timestamps never establish a calibration outcome.

`test_placeholder_titles_do_not_confirm_drift` — empty and `"(unspecified)"` titles are insufficient identity, not a semantic match.

`test_invalid_or_legacy_run_reconcile_does_not_clear_origin` — an unmatched code-side report clears only with explicit parser-valid evidence; invalid and legacy-unknown rows remain unresolved.

`test_repeated_origin_audits_share_one_outcome_observation` — multiple matching origins before one same-step outcome yield one confirmed/cleared observation, using the latest pre-outcome origin.

`test_plan_rooted_run_reconcile_redirect_does_not_confirm_drift` — a strict-looking outcome finding with `redirect` is excluded from code-drift confirmation.

`test_run_reconcile_findings_are_not_calibration_origins` — outcome snapshots do not recursively enter the historical audit-finding cohort.

`test_calibration_signal_exposes_rate_and_insufficient_evidence` — result counts yield a rate only over resolved observations and report `insufficient-evidence` below three resolved rows.

`test_live_recommendation_and_persisted_finding_share_class_key` — `classify_calibration_recommendation` and the history adapter derive the identical key from equivalent fields.

`test_finding_class_without_owner_or_joinable_history_is_counted_unresolved` — ownerless, legacy, or unmatchable findings remain in totals and do not affect the resolved drift rate.

`test_purity_provenance_cohorts_remain_separate` — otherwise matching purity findings tagged `fresh` and `below-floor-reuse` produce distinct cohorts.

`test_legacy_purity_provenance_is_unknown` — a saved purity finding with no provenance is reported as `unknown`, never as `fresh`.

`test_finding_drift_analysis_is_deterministic_and_read_only` — repeated analysis over the same sidecars yields the same values and does not create calibration files or alter existing inputs.

`test_telemetry_analysis_does_not_import_cli` — retain the existing dependency-boundary assertion while covering the new analysis path.

### Test-creation order (feature step)

1. `test_finding_class_without_owner_or_joinable_history_is_counted_unresolved` — establish the incomplete-evidence contract before adding correlation.
2. `test_finding_class_confirmed_by_later_run_reconcile_has_positive_signal` — add the positive correlation behavior with the implementation.
3. `test_finding_class_cleared_by_later_run_reconcile_has_negative_signal` — add the resolved control case with the implementation.
4. `test_same_step_unrelated_run_reconcile_finding_does_not_confirm_origin`, `test_other_step_run_reconcile_does_not_clear_origin`, `test_step_anchored_completeness_origin_joins_same_step_run_reconcile`, `test_tied_or_malformed_report_timestamps_remain_unresolved`, `test_placeholder_titles_do_not_confirm_drift`, `test_invalid_or_legacy_run_reconcile_does_not_clear_origin`, and `test_repeated_origin_audits_share_one_outcome_observation` — pin the strict identity, same-step, completeness-anchor, chronology, valid-outcome, and observation-unit boundaries.
5. `test_plan_rooted_run_reconcile_redirect_does_not_confirm_drift` and `test_run_reconcile_findings_are_not_calibration_origins` — pin redirect and origin-population boundaries.
6. `test_calibration_signal_exposes_rate_and_insufficient_evidence` — pin the operator-visible evidence contract without a gate policy.
7. `test_live_recommendation_and_persisted_finding_share_class_key` — pin the public #152-facing helper against the persisted-history adapter.
8. `test_purity_provenance_cohorts_remain_separate` — add cohort separation with the implementation.
9. `test_legacy_purity_provenance_is_unknown` — add legacy compatibility with the implementation.
10. `test_finding_drift_analysis_is_deterministic_and_read_only` — add the read-only regression guard with the implementation.

Every new test must be green before this step is considered finished.

## Acceptance criteria

- A typed analysis in `plan_tool/telemetry_analysis.py` discovers manifest plans and returns per-class totals, confirmed/cleared outcomes, unresolved outcomes, and a deterministic advisory signal from saved audit history.
- The class identity includes finding source, anchor category, and the fixed scope-shape taxonomy derived only from persisted normalized fields.
- `classify_calibration_recommendation(Recommendation)` is the documented public class-key helper and agrees with the persisted-history adapter on equivalent fields.
- A synthetic class with a strictly matching later same-step `run-reconcile` finding reports confirmed drift; an unrelated finding on that step does not.
- A synthetic class with the first later same-step `run-reconcile` report lacking the region reports a resolved clearance; a reconcile for another step remains unresolved.
- A completeness origin with `step_id=None` derives its step from a `step<N>` anchor and follows the same same-step outcome rule.
- Tied or malformed persisted timestamps remain unresolved rather than being arbitrarily ordered into a confirmation or clearance.
- Empty/placeholder titles never confirm drift, and an unmatched code-side report clears an origin only when its parser-valid marker is explicitly true.
- Repeated historical audits of one origin contribute at most one resolved observation per selected outcome report.
- Redirect-marked `run-reconcile` findings never confirm code drift, and `run-reconcile` snapshots never contribute origin findings.
- Every class exposes confirmed, cleared, and unresolved counts plus a rate over resolved observations, and reports `insufficient-evidence` below three resolved observations.
- Ownerless, legacy, and unjoinable findings are counted but unresolved rather than dropped or treated as no-drift.
- Purity cohorts for `fresh`, `exact-cache`, `below-floor-reuse`, and `unknown` remain distinguishable in the result.
- `tests/test_telemetry_analysis.py` passes, including the no-CLI-import assertion.
- The analysis creates no persisted calibration store and does not mutate plans, configuration, or saved evidence.

## References

- [Python pathlib documentation](https://docs.python.org/3/library/pathlib.html) — Read sidecar paths deterministically without changing repository state.
- [Python json documentation](https://docs.python.org/3/library/json.html) — Handle legacy and malformed sidecar JSON safely.
- [RFC 8259: JSON Data Interchange Format](https://www.rfc-editor.org/info/rfc8259/) — Preserve compatibility expectations for saved JSON evidence.

## Deferred

- Telemetry command rendering — Step 3 owns exposing the new calibration result to operators.
- Convergence-gate demotion — #152 may consume this advisory signal later; this step must not re-weight live findings.
- Threshold auto-tuning or a persisted calibration cache — outside this read-only analysis step.
- Purity-cache hardening or reuse-threshold changes — #155 owns those policy changes.
