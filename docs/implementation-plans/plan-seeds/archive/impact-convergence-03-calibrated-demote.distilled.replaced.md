> **Replaced**: this file has been superseded by `docs/implementation-plans/2-impact-convergence-03-calibrated-demote.md`.
> Preserved here for history; do not edit.

## Overview

Implement #152 as a conservative calibration-based exception to the existing severity floor. An explicit `impact=low`, `severity=medium` recommendation may be demoted only when read-only class-drift evidence meets the required resolved-observation and confirmed-rate thresholds; high-impact promotion remains unchanged. Calibration is read once per operation and supplied to the reachable reconcile and audit-materiality loops without changing their other behavior.

## Problem statement

The remaining #152 demotion needs a narrow, evidence-backed path for low-impact medium-severity recommendations while preserving the current safety floor for all other recommendations. Without this exception, recommendations with sufficiently reliable low-confirmation calibration evidence remain blocking despite their measured class behavior.

## Architecture

Classify each live recommendation with `telemetry_analysis.classify_calibration_recommendation` and evaluate only the existing read-only `FindingClassDriftSignal` evidence. Demotion is allowed exclusively for explicit `impact=low`, `severity=medium` recommendations whose matching class has `confirmed + cleared >= 10` and `confirmed_rate <= 0.10`; all missing, unknown, legacy, insufficient, unresolved-only, or over-threshold evidence remains blocking.

Read calibration once per operation, then pass an immutable lookup or predicate into the existing reachable reconcile and audit-materiality loops. This preserves the existing flow while preventing per-finding history reads or persisted calibration state.

## Risks

- Incorrectly applying the exception outside explicit `impact=low`, `severity=medium` recommendations could weaken the severity floor; `high` and `critical` must always block, while `nit` and `info` retain existing advisory behavior.
- Missing, legacy, or insufficient calibration evidence could be treated as permissive; these cases, including unresolved-only cohorts and rates above the threshold, must remain blocking.
- Repeated calibration reads could add unnecessary history access; calibration must be read once per operation.

## Testing

Required proof covers the strict threshold boundary matrix, high/critical safety, unknown-evidence fallback, one-read-per-operation behavior, stable existing augment behavior, and absence of plan/config/telemetry mutation.

## Acceptance criteria

- Only an explicit `impact=low`, `severity=medium` recommendation is eligible for demotion.
- A matching class is demoted only when `confirmed + cleared >= 10` and `confirmed_rate <= 0.10`.
- `high` and `critical` severity recommendations always block, and `nit` and `info` retain existing advisory behavior.
- Missing class rows, unknown/legacy provenance, insufficient evidence, unresolved-only cohorts, and rates above `0.10` remain blocking.
- Live recommendations are classified with `telemetry_analysis.classify_calibration_recommendation` using only existing read-only `FindingClassDriftSignal` evidence.
- Calibration is read once per operation and supplied to the reachable reconcile and audit-materiality loops without per-finding history reads or persisted cache.
- High-impact promotion, completeness continuation, and #158's separate impact-recurrence structural stop are unchanged.
- The change does not add a CLI flag or mutate plan, config, or telemetry.
