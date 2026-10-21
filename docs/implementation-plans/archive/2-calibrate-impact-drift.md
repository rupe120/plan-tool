> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Calibrate Impact Drift
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Record how each purity verdict was produced
  files:
  - plan_tool/review.py
  - plan_tool/detail.py
  - plan_tool/cli/completeness_phases.py
  - plan_tool/convergence_diagnosis.py
  - plan_tool/review_persistence.py
  - plan_tool/cli/reconcile.py
  - plan_tool/launcher.py
  - tests/test_detail.py
  - tests/cli/test_completeness_cmd.py
  - tests/test_convergence_diagnosis.py
  - tests/test_review_persistence.py
  - tests/test_launcher.py
  - tests/cli/test_reconcile_engine.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/calibrate-impact-drift/01-record-how-each-purity-verdict-was.md
  status: done
- id: 2
  title: Calculate drift signals for audit finding classes
  files:
  - plan_tool/telemetry_analysis.py
  - tests/test_telemetry_analysis.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/calibrate-impact-drift/02-calculate-drift-signals-audit-finding.md
  status: done
- id: 3
  title: Show calibration results in telemetry output
  files:
  - plan_tool/telemetry_analysis.py
  - plan_tool/cli/telemetry_cmd.py
  - tests/test_telemetry_analysis.py
  - tests/cli/test_telemetry_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/calibrate-impact-drift/03-show-calibration-results-telemetry.md
  status: done
- id: 4
  title: Document the calibration result and clear its backlog block
  files:
  - DATA_CONTRACT.md
  - BACKLOG.md
  - docs/implementation-plans/2-gate-convergence-by-impact.md
  complexity: low
  change_type: non-code
  depends_on:
  - 3
  detail: docs/implementation-plans/plan-details/calibrate-impact-drift/04-document-calibration-result-clear-its.md
  status: done
---
# Calibrate Impact Drift

## Overview

Add a read-only calibration analysis that relates historical audit finding classes to later code-side `run-reconcile` evidence produced by `plan-tool run <name> --reconcile`. It gives operators an advisory per-class signal and a documented entry point for #152's demote slice, while preserving purity-verdict cache provenance. It computes from existing evidence on read, creates no second persisted store, and does not change gates, thresholds, plans, or config.

## Problem statement

`impact` is currently self-graded by the same Claude pass that raises a finding, without outcome ground truth. This is tolerable for applies and #152's monotonic augment blocking, but using it for a demote-style stop gate could under-rate a real seam and converge early. Existing code-side `run-reconcile` evidence from `plan-tool run <name> --reconcile` can show which finding classes actually predicted implementation drift, allowing `impact` to be calibrated from observed outcomes rather than per-finding self-report.

## Architecture

Build a read-only correlation leaf that joins saved audit findings, classified by `Recommendation.source`, a deterministic anchor category, and a deterministic scope shape, to later code-side reconcile reports. Only `completeness` and `detail-reconcile` reports supply origins; `plan-tool run <name> --reconcile` persists `kind="run-reconcile"` reports as outcome evidence only. Derive an origin's step scope from its non-null `step_id` or, for completeness findings, the existing `step<N>` anchor parser. For a resolved step scope, inspect only the first report for that same step whose parseable `created_at` is strictly later than the origin; tied second-precision timestamps and malformed timestamps are unresolved, never arbitrarily ordered. A report confirms drift only when a non-redirect, non-placeholder finding has a stricter match on a non-bare normalized anchor or reaches the title-similarity cutoff, never merely because the step number matches. It clears an origin only when a new persisted parser-valid marker proves a completed, interpretable code-side audit; legacy, invalid, or unknown-validity reports remain unresolved. Plan-level/unscoped origins remain unresolved rather than borrowing another step's report. This is deliberately not a plan-fingerprint-transition outcome. Discover plans from the manifest, then load each plan's canonical saved-review history through `plan_tool/convergence_diagnosis.py:load_report_history(plan_path)` / `plan_tool.review_persistence:plan_reports_dir`; unresolved ownerless or legacy rows remain counted-but-unresolved.

Expose a per-finding-class advisory calibration result and `plan_tool.telemetry_analysis:classify_calibration_recommendation(rec: Recommendation) -> FindingClass`, the deterministic public helper that derives the same class key for a live recommendation and a persisted history row. The signal is the confirmed rate `confirmed / (confirmed + cleared)` accompanied by confirmed, cleared, and unresolved counts; it is explicitly `insufficient-evidence` below three resolved observations. A later #152 demote design may choose to consume that documented analysis contract, but this plan does not make `is_blocking_impact` consult it, re-key the convergence gate, or silently re-weight live findings. The analysis leaf must not import `plan_tool.cli`.

Preserve purity-cache provenance at the result/provenance boundary as `fresh`, `exact-cache`, `below-floor-reuse`, or legacy `unknown`. Report provenance with class-level results and stratify cohorts where sample size permits, so cache-reused and fresh verdicts are not silently pooled.

## Input

The analysis consumes saved audit findings classified by `Recommendation.source`, anchor category, and scope shape; historical reports loaded through `plan_tool/convergence_diagnosis.py:load_report_history(plan_path)` from the canonical per-plan saved-review directory; and later `kind="run-reconcile"` snapshots in that same history. It discovers candidate plan paths through the manifest independently of decision telemetry, so rows can render when there are zero decision events. Ownerless or legacy rows that cannot be correlated remain counted-but-unresolved.

## References

- [Python pathlib documentation](https://docs.python.org/3/library/pathlib.html) — Covers deterministic filesystem traversal and globbing needed to read run sidecars without mutating the repository.
- [Python json documentation](https://docs.python.org/3/library/json.html) — Defines standard-library JSON parsing behavior and error handling for legacy or malformed evidence files.
- [Pydantic model documentation](https://pydantic.dev/docs/validation/latest/concepts/models/) — Explains model validation patterns useful when adding typed read-only calibration result contracts.
- [Pydantic serialization documentation](https://pydantic.dev/docs/validation/latest/concepts/serialization/) — Covers controlled model serialization for presenting advisory calibration and provenance results.
- [Claude Code CLI reference](https://code.claude.com/docs/en/cli-usage) — Documents Claude Code structured and stream-JSON output that underlies the existing audit evidence being correlated.
- [RFC 8259: JSON Data Interchange Format](https://www.rfc-editor.org/info/rfc8259/) — Specifies the JSON interchange format relevant to compatibility with persisted reconcile and completeness sidecars.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Re-keying the convergence gate or silently re-weighting live findings; #152's separate demote slice may consume the advisory signal.
- Threshold auto-tuning.
- Persisting a calibration cache or mutating plans or config.
- The live-loop impact-recurrence structural stop in #158.
- Hardening the purity cache or changing its reuse threshold; #155 owns that work.

## Risks

- Calibration can be biased if cached and fresh purity verdicts are silently pooled; retain `fresh`, `exact-cache`, `below-floor-reuse`, and `unknown` cohorts, and stratify where evidence is sufficient.
- Ownerless or legacy evidence may not be correlatable; keep those rows counted-but-unresolved rather than dropping them.
- A persisted calibration cache or mutation of plans/config would violate the read-only telemetry constraint; compute verdicts on read and add no second store.
- Importing `plan_tool.cli` from the analysis leaf would break the required below-CLI, acyclic import order; preserve the existing dependency boundary.

## Testing

- Add synthetic-history unit tests showing a class confirmed by a later matching `run-reconcile` report calibrates up and a class explicitly absent from a later `run-reconcile` report calibrates down.
- Verify ownerless and uncorrelatable rows are counted-but-unresolved rather than dropped.
- Verify fresh and below-floor-reused purity cohorts remain distinguishable, and legacy rows become `unknown` rather than silently becoming fresh.
- Verify the analysis creates no persisted second store and does not mutate plans or config.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- A read-only analysis correlates historical audit findings by class with subsequent `run-reconcile` confirmation or clearance and emits a per-class advisory signal computed on read, with no second persisted store.
- The result and `classify_calibration_recommendation(Recommendation)` helper are documented as an advisory contract a later #152 demote slice may consume.
- The analysis performs no threshold auto-tuning and no plan/config mutation; ownerless and legacy rows are counted-but-unresolved rather than dropped.
- Purity findings expose `fresh`, `exact-cache`, `below-floor-reuse`, or legacy `unknown` provenance in the read-only result, without invisibly pooling cache-reused and fresh cohorts.
- The analysis leaf does not import `plan_tool.cli` and preserves acyclic import order.
- `BACKLOG.md` #154 is marked shipped/removed and #152's demote form is noted as unblocked.

## Deferred

- Re-keying the convergence gate through #152's demote form is a separate slice that consumes this plan's calibration signal.
- The live-loop impact-recurrence structural stop in #158 remains separate work.
- Hardening the purity cache or changing its reuse threshold is reserved for #155; this plan only records provenance to measure potential bias.
