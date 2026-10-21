> **Replaced**: this file has been superseded by `docs/implementation-plans/2-calibrate-impact-drift.md`.
> Preserved here for history; do not edit.

## Overview

Add a read-only calibration analysis that relates historical audit finding classes to later `reconcile-code` and post-run drift. It will expose an advisory per-class signal for operators and a documented consumption point for #152's demote slice, while retaining purity-verdict cache provenance. It computes from existing evidence on read, creates no second persisted store, and does not change gates, thresholds, plans, or config.

## Problem statement

`impact` is currently self-graded by the same Claude pass that raises a finding, without outcome ground truth. This is tolerable for applies and #152's monotonic augment blocking, but using it for a demote-style stop gate could under-rate a real seam and converge early. Existing `reconcile-code` and post-run reconciliation evidence can show which finding classes actually predicted implementation drift, allowing `impact` to be calibrated from observed outcomes rather than per-finding self-report.

## Architecture

Build a read-only correlation leaf that joins saved audit findings, classified by `Recommendation.source`, anchor category, and seam-vs-detail shape, to subsequent `reconcile-code` and post-run drift. Follow the read-on-read resolver pattern in `plan_tool/telemetry_analysis.py:analyze_decisions(repo_root)` and use `plan_tool/convergence_diagnosis.py:load_report_history(plan_path)` plus `.plan-tool/runs/<slug>/*-reconcile.json` and `*-completeness.json` sidecars; unresolved ownerless or legacy rows remain counted-but-unresolved.

Expose a per-finding-class advisory calibration signal to operators and at a clean entry point consumable by #152's `is_blocking_impact`. The signal is advisory only: this plan does not re-key the convergence gate or silently re-weight live findings, and the analysis leaf must not import `plan_tool.cli`.

Preserve purity-cache provenance at the result/provenance boundary as `fresh`, `exact-cache`, `below-floor-reuse`, or legacy `unknown`. Report provenance with class-level results and stratify cohorts where sample size permits, so cache-reused and fresh verdicts are not silently pooled.

## Risks

- Calibration can be biased if cached and fresh purity verdicts are silently pooled; retain `fresh`, `exact-cache`, `below-floor-reuse`, and `unknown` cohorts, and stratify where evidence is sufficient.
- Ownerless or legacy evidence may not be correlatable; keep those rows counted-but-unresolved rather than dropping them.
- A persisted calibration cache or mutation of plans/config would violate the read-only telemetry constraint; compute verdicts on read and add no second store.
- Importing `plan_tool.cli` from the analysis leaf would break the required below-CLI, acyclic import order; preserve the existing dependency boundary.

## Testing

- Add synthetic-history tests showing a class that reliably precedes drift calibrates up and a class that never precedes drift calibrates down.
- Verify ownerless and uncorrelatable rows are counted-but-unresolved rather than dropped.
- Verify fresh and below-floor-reused purity cohorts remain distinguishable, and legacy rows become `unknown` rather than silently becoming fresh.
- Verify the analysis creates no persisted second store and does not mutate plans or config.

## Acceptance criteria

- A read-only analysis correlates historical audit findings by class with subsequent `reconcile-code` / post-run drift and emits a per-class drift-prediction signal computed on read, with no second persisted store.
- #152's demote slice has a documented entry point through which it can consume the signal.
- The analysis performs no threshold auto-tuning and no plan/config mutation; ownerless and legacy rows are counted-but-unresolved rather than dropped.
- Purity findings expose `fresh`, `exact-cache`, `below-floor-reuse`, or legacy `unknown` provenance in the read-only result, without invisibly pooling cache-reused and fresh cohorts.
- The analysis leaf does not import `plan_tool.cli` and preserves acyclic import order.
- `BACKLOG.md` #154 is marked shipped/removed and #152's demote form is noted as unblocked.

## Deferred

- Re-keying the convergence gate through #152's demote form is a separate slice that consumes this plan's calibration signal.
- The live-loop structural escalation in #153 remains separate work.
- Hardening the purity cache or changing its reuse threshold is reserved for #155; this plan only records provenance to measure potential bias.
