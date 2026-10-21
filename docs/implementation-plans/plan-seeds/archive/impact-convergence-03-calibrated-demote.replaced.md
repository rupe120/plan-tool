> **Replaced**: this file has been superseded by `docs/implementation-plans/2-impact-convergence-03-calibrated-demote.md`.
> Preserved here for history; do not edit.

# Calibrated impact-only demotion (#152)

Implement the remaining #152 demotion as a conservative, evidence-backed
exception to the existing severity floor. Keep high-impact promotion unchanged.

Policy:

- Only an explicit `impact=low`, `severity=medium` recommendation is eligible
  for demotion. `high` and `critical` severity always block; `nit` and `info`
  retain their existing advisory behavior.
- Classify a live recommendation with
  `telemetry_analysis.classify_calibration_recommendation` and use only the
  existing read-only `FindingClassDriftSignal` evidence.
- Demote only when the matching class has at least 10 resolved observations
  (`confirmed + cleared >= 10`) and `confirmed_rate <= 0.10`.
- Missing class rows, unknown/legacy provenance, insufficient evidence,
  unresolved-only cohorts, and any rate above the threshold remain blocking.
- Read calibration once per operation and pass an immutable lookup/predicate to
  the existing reachable reconcile and audit-materiality loops. Do not make a
  per-finding history read, persist a cache, add a CLI flag, change completeness
  continuation, or alter #158's separate impact-recurrence structural stop.

Required proof includes the strict boundary matrix above, high/critical safety,
unknown-evidence fallback, one-read-per-operation behavior, stable existing
augment behavior, and no plan/config/telemetry mutation.
